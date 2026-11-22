#include "console.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "audio.h"
#include "audio_config.h"
#include "board.h"
#include "boot.h"
#include "codec.h"
#include "dcd_capture.h"
#include "i2s.h"
#include "tusb.h"

// Jack levels at full scale (docs/research.md section 2), millivolts, pots fully up.
#define IN_FS_MV   5490
#define OUT_FS_MV  5200

static char line[64];
static size_t line_len;
static bool meter_on, cal_wait;
static uint32_t meter_at;

// `blwrite <bytes> <crc32 hex>`: the next <bytes> raw bytes are a DFU bootloader
// image (../flash.sh --bootloader). Written only when the CRC-32 matches.
static uint8_t bl_buf[BOOT_APP_BASE] __attribute__((aligned(4)));
static uint32_t bl_len, bl_got, bl_crc, bl_deadline;
static bool bl_active;

static void out(const char *fmt, ...) {
  char buf[160];
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  if (n <= 0) return;
  if (n > (int) sizeof(buf) - 1) n = sizeof(buf) - 1;
  // The CDC FIFO is large; drop rather than block the audio main loop.
  tud_cdc_write(buf, (uint32_t) n);
  tud_cdc_write_flush();
}

static int32_t to_mv(int32_t code, int32_t fs_mv) {
  return (int32_t) (((int64_t) code * fs_mv) / (1 << 23));
}

static void print_mv(const char *label, int32_t mv) {
  out("%s%c%ld.%03ld V", label, mv < 0 ? '-' : '+', (long) (mv < 0 ? -mv : mv) / 1000,
      (long) (mv < 0 ? -mv : mv) % 1000);
}

static void print_cal(audio_status_t const *st) {
  print_mv("IN DC: offsets IN 1 ", to_mv(st->dc_offset[0], IN_FS_MV));
  print_mv(", IN 2 ", to_mv(st->dc_offset[1], IN_FS_MV));
  switch (st->cal) {
    case AUDIO_CAL_MEASURING: out(" subtracted, measuring (IN 1/2 unpatched)\r\n"); break;
    case AUDIO_CAL_MEASURED: out(" subtracted, measured at power-up: `cal` saves them\r\n"); break;
    case AUDIO_CAL_SAVED: out(" subtracted (saved)\r\n"); break;
    case AUDIO_CAL_NOT_SAVED: out(" subtracted, NOT saved: flash write failed\r\n"); break;
    case AUDIO_CAL_UNSTEADY: out(" kept: the inputs did not hold still, unpatch IN 1/2\r\n"); break;
    case AUDIO_CAL_RANGE: out(" kept: more than 0.1 V measured, unpatch IN 1/2\r\n"); break;
    default: out(" subtracted\r\n"); break;
  }
}

// Buffer level now and its range since the previous status, in frames.
static void print_stream(const char *label, audio_stream_t const *s, const char *rate_label) {
  out("%s %s%s, buffer %u frames (%u..%u, held at %u), %s%lu.%04lu samples/uframe", label,
      s->streaming ? "streaming" : "idle", s->streaming && !s->primed ? " (filling)" : "", s->level, s->level_min,
      s->level_max, s->target, rate_label, (unsigned long) (s->rate >> 16),
      (unsigned long) (((s->rate & 0xFFFF) * 10000) >> 16));
}

static void cmd_status(void) {
  audio_status_t st;
  audio_get_status(&st);
  out("\r\nBread Modular 2X2 firmware %s (%s)\r\n", FW_VERSION, FW_GIT);
  out("USB:   %s, %s speed\r\n", tud_mounted() ? "configured" : "not configured",
      tud_speed_get() == TUSB_SPEED_HIGH ? "high" : "full");
  out("Codec: %s", codec_state_name(codec_state()));
  if (codec_state() == CODEC_RUNNING) out(", ID 0x%02X, %lu Hz", codec_chip_id(), (unsigned long) st.rate_codec);
  out(", host rate %lu Hz\r\n", (unsigned long) st.rate_host);
  print_cal(&st);
  out("I2S:   %s, %lu frames/half%s\r\n", i2s_running() ? "running" : "stopped", (unsigned long) AUDIO_BLOCK_FRAMES,
      audio_tone() ? ", test tone on" : "");
  print_stream("OUT:  ", &st.out, "feedback ");
  out(", target %u ms\r\n", st.out_target_ms);
  print_stream("IN:   ", &st.in, "packets ");
  out("\r\n");
  out("Count: restarts %lu, OUT underruns %lu overruns %lu, IN underruns %lu overruns %lu\r\n",
      (unsigned long) st.restarts, (unsigned long) st.out.underruns, (unsigned long) st.out.overruns,
      (unsigned long) st.in.underruns, (unsigned long) st.in.overruns);
  out("       I2S ovr %lu udr %lu slip %lu stall %lu late %lu\r\n", (unsigned long) i2s_err_ovr,
      (unsigned long) i2s_err_udr, (unsigned long) i2s_err_slip, (unsigned long) i2s_err_stall,
      (unsigned long) i2s_err_late);
  if (st.last_error[0]) out("Last:  %s\r\n", st.last_error);

  static uint32_t iso_ms;
  audio_iso_stats_t iso;
  audio_take_iso_stats(&iso);
  uint32_t const now = board_millis();
  out("ISO:   %lu ms: OUT %lu packets (%lu missed), IN %lu (%lu missed), feedback %lu (%lu missed)\r\n",
      (unsigned long) (now - iso_ms), (unsigned long) iso.packets[0], (unsigned long) iso.missed[0],
      (unsigned long) iso.packets[1], (unsigned long) iso.missed[1], (unsigned long) iso.packets[2],
      (unsigned long) iso.missed[2]);
  iso_ms = now;
  out("       since the reset: missed OUT %lu, IN %lu, feedback %lu\r\n", (unsigned long) iso.missed_total[0],
      (unsigned long) iso.missed_total[1], (unsigned long) iso.missed_total[2]);
  out("DCD:   capture overflows %lu, iso waits timed out %lu, empty OUT packets %lu\r\n",
      (unsigned long) dcd_capture_overflows, (unsigned long) dcd_capture_iso_timeouts,
      (unsigned long) dcd_iso_out_empty);
  out("       processing delay: worst %lu us, over 100 us %lu\r\n",
      (unsigned long) (dcd_delay_max / (SystemCoreClock / 1000000u)), (unsigned long) dcd_delay_late);
  dcd_delay_max = 0;
}

static void print_meter(void) {
  static uint32_t last_ms;
  audio_meter_t m;
  audio_take_meter(&m);
  uint32_t const now = board_millis();
  uint32_t const dt = now - last_ms;
  last_ms = now;
  out("rate %6lu Hz |", dt ? (unsigned long) ((uint64_t) m.frames * 1000 / dt) : 0UL);
  for (int c = 0; c < 2; c++) {
    out(" IN%d", c + 1);
    print_mv(" dc ", to_mv(m.in_mean[c], IN_FS_MV));
    print_mv(" pk ", to_mv(m.in_peak[c], IN_FS_MV));
    out(" |");
  }
  for (int c = 0; c < 2; c++) {
    out(" OUT%d", c + 1);
    print_mv(" dc ", to_mv(m.out_mean[c], OUT_FS_MV));
    print_mv(" pk ", to_mv(m.out_peak[c], OUT_FS_MV));
    out(c ? "\r\n" : " |");
  }
}

static void cmd_regs(void) {
  for (uint8_t r = CS4270_CHIPID; r <= CS4270_VOLB; r++) {
    uint8_t v;
    if (codec_read(r, &v)) {
      out("  %02Xh = 0x%02X\r\n", r, v);
    } else {
      out("  %02Xh: no answer\r\n", r);
    }
  }
}

static void cmd_blwrite(char *args) {
  char *end;
  unsigned long const len = strtoul(args, &end, 10);
  unsigned long const crc = strtoul(end, &end, 16);
  if (len < 8 || len > sizeof(bl_buf)) {
    out("blwrite: size must be 8..%u bytes\r\n", (unsigned) sizeof(bl_buf));
    return;
  }
  bl_len = len;
  bl_crc = crc;
  bl_got = 0;
  bl_deadline = board_millis() + 10000;
  bl_active = true;
  out("blwrite: send %lu bytes\r\n", len);
}

static void blwrite_task(void) {
  uint32_t const avail = tud_cdc_available();
  if (avail) {
    uint32_t const want = bl_len - bl_got;
    bl_got += tud_cdc_read(bl_buf + bl_got, avail < want ? avail : want);
  }
  if (bl_got < bl_len) {
    if ((int32_t) (board_millis() - bl_deadline) >= 0) {
      bl_active = false;
      out("blwrite: FAIL timeout, %lu of %lu bytes\r\n> ", (unsigned long) bl_got, (unsigned long) bl_len);
    }
    return;
  }
  bl_active = false;
  uint32_t const crc = board_crc32(bl_buf, bl_len);
  if (crc != bl_crc) {
    out("blwrite: FAIL CRC %08lX, expected %08lX\r\n> ", (unsigned long) crc, (unsigned long) bl_crc);
    return;
  }
  i2s_stop();
  codec_stop();
  bool const ok = board_write_bootloader(bl_buf, bl_len);
  audio_restart(0);
  out(ok ? "blwrite: OK, bootloader written and verified (%lu bytes)\r\n> "
         : "blwrite: FAIL flash write/verify (%lu bytes): retry before any reset\r\n> ",
      (unsigned long) bl_len);
}

static void cmd_help(void) {
  out("\r\ncommands:\r\n"
      "  status   firmware, USB, codec, I2S and stream state (also: Enter)\r\n"
      "  meter    toggle a 2 Hz line: measured LRCK, DC and peak per jack (pots up)\r\n");
  out("  cal      measure the input DC offsets and save them: unpatch IN 1/2 first\r\n"
      "           (the audio stops for a moment); `cal erase` forgets the saved offsets\r\n"
      "  tone     toggle a 1 kHz test tone (half scale) on OUT 1/2 instead of the USB audio\r\n"
      "  regs     dump CS4270 registers 01h-08h\r\n");
  out("  restart  reset and restart codec + I2S; `restart <s>` holds the codec in reset first\r\n"
      "  reboot   reset the MCU\r\n"
      "  dfu      reset into the DFU bootloader (../flash.sh uses a 1200 baud touch)\r\n"
      "  blwrite  <bytes> <crc32>: rewrite the DFU bootloader (../flash.sh --bootloader)\r\n");
}

static void run(char *cmd) {
  if (cmd[0] == 0 || !strcmp(cmd, "status") || !strcmp(cmd, "s")) {
    cmd_status();
  } else if (!strcmp(cmd, "noslip")) {
    extern volatile uint32_t dbg_noslip;
    dbg_noslip = !dbg_noslip;
    out("noslip %lu\r\n", (unsigned long) dbg_noslip);
  } else if (!strncmp(cmd, "runat ", 6)) {
    // Codec started at a rate with the I2S slaves armed (original start), then LRCK polled.
    uint32_t const r = (uint32_t) atoi(cmd + 6);
    i2s_stop();
    out("prepare %d\r\n", (int) codec_prepare(r));
    i2s_start();
    out("run %d\r\n", (int) codec_run());
    board_delay_ms(30);
    uint32_t edges = 0, cyc = 0, guard = 0, period = (uint32_t) SysTick->CMP + 1u;
    uint32_t const irq = board_irq_mask();
    uint32_t lt = SysTick->CNT;
    bool ws = (GPIOB->INDR & GPIO_Pin_12) != 0;
    uint16_t const c0 = DMA1_Channel4->CNTR, t0 = DMA2_Channel2->CNTR;
    while (cyc < SystemCoreClock / 100u && guard < 100000000u) {   // 10 ms
      guard++;
      bool const w = (GPIOB->INDR & GPIO_Pin_12) != 0;
      if (w && !ws) edges++;
      ws = w;
      uint32_t const now = SysTick->CNT;
      cyc += now >= lt ? now - lt : now + period - lt;
      lt = now;
    }
    uint16_t const c1 = DMA1_Channel4->CNTR, t1 = DMA2_Channel2->CNTR;
    board_irq_restore(irq);
    out("10 ms: LRCK rising %lu (%lu Hz); RX CNTR %u->%u TX %u->%u; SPI2 %04X SPI3 %04X\r\n", (unsigned long) edges,
        (unsigned long) edges * 100u, c0, c1, t0, t1, SPI2->STATR, SPI3->STATR);
  } else if (!strcmp(cmd, "clk")) {
    // 1000 LRCK periods polled with interrupts off vs DMA half-words and SysTick cycles.
    uint32_t const n_hw = 2u * AUDIO_BLOCK_FRAMES * 4u, period = (uint32_t) SysTick->CMP + 1u;
    uint32_t edges = 0, hw = 0, cyc = 0, guard = 0;
    uint32_t const irq = board_irq_mask();
    uint16_t last = DMA1_Channel4->CNTR;
    uint16_t const tx0 = DMA2_Channel2->CNTR;
    uint32_t lt = SysTick->CNT;
    bool ws = (GPIOB->INDR & GPIO_Pin_12) != 0;
    while (edges < 10000 && guard < 400000000u) {
      guard++;
      bool const w = (GPIOB->INDR & GPIO_Pin_12) != 0;
      if (w && !ws) edges++;
      ws = w;
      uint16_t const c = DMA1_Channel4->CNTR;
      if (c != last) {
        hw += ((uint32_t) last + n_hw - c) % n_hw;
        last = c;
      }
      uint32_t const now = SysTick->CNT;
      cyc += now >= lt ? now - lt : now + period - lt;
      lt = now;
    }
    uint16_t const tx1 = DMA2_Channel2->CNTR;
    board_irq_restore(irq);
    out("TX DMA CNTR %u -> %u\r\n", tx0, tx1);
    uint32_t const us = cyc / (SystemCoreClock / 1000000u);
    out("LRCK %lu periods in %lu us (%lu Hz), DMA half-words %lu (x1000 per period %lu, expect 4000, 10000 periods)\r\n",
        (unsigned long) edges, (unsigned long) us, us ? (unsigned long) ((uint64_t) edges * 1000000u / us) : 0UL,
        (unsigned long) hw, edges ? (unsigned long) (hw * 1000 / edges) : 0UL);
  } else if (!strcmp(cmd, "quiet")) {
    // Clocks while the codec is held (reset, then configured with PDN): they must stay still.
    for (int phase = 0; phase < 2; phase++) {
      i2s_stop();
      if (phase == 0) codec_stop();
      else if (codec_prepare(48000) != CODEC_READY) out("prepare failed\r\n");
      board_delay_ms(5);
      i2s_start();
      uint32_t sck = 0, ws = 0, sd = 0;
      uint32_t p = GPIOB->INDR;
      uint32_t const t0 = board_millis();
      uint32_t const irq = board_irq_mask();
      for (uint32_t i = 0; i < 2000000u; i++) {
        uint32_t const v = GPIOB->INDR;
        uint32_t const d = v ^ p;
        p = v;
        if (d & GPIO_Pin_13) sck++;
        if (d & GPIO_Pin_12) ws++;
        if (d & GPIO_Pin_15) sd++;
      }
      board_irq_restore(irq);
      uint16_t const cnt = DMA1_Channel4->CNTR;
      uint16_t const st = SPI2->STATR;
      out("%s: SCLK toggles %lu, LRCK %lu, SDOUT %lu, pins now %s%s%s, DMA left %u of %u, SPI2 STATR %04X (%lu ms)\r\n",
          phase ? "PDN held" : "RST low", (unsigned long) sck, (unsigned long) ws, (unsigned long) sd,
          (p & GPIO_Pin_13) ? "SCLK=1 " : "SCLK=0 ", (p & GPIO_Pin_12) ? "LRCK=1 " : "LRCK=0 ",
          (p & GPIO_Pin_15) ? "SD=1" : "SD=0", cnt, 2u * AUDIO_BLOCK_FRAMES * 4u, st,
          (unsigned long) (board_millis() - t0));
    }
    i2s_stop();
    codec_stop();
  } else if (!strncmp(cmd, "sclktest", 8)) {
    uint32_t const settle = (uint32_t) atoi(cmd + 8);
    // SCLK rising edges before the first LRCK edge and between the next ones, right after PDN clears.
    i2s_stop();
    if (codec_prepare(48000) != CODEC_READY) out("prepare failed\r\n");
    board_delay_ms(5);
    uint32_t cnt[12] = {0};
    int idx = 0;
    uint32_t polls = 0;
    bool ok = codec_run();
    board_delay_ms(settle);
    uint32_t const irq = board_irq_mask();
    uint32_t p = GPIOB->INDR;
    uint32_t const ws0 = p & GPIO_Pin_12, sck0 = p & GPIO_Pin_13;
    while (ok && idx < 12 && polls < 50000000u) {
      polls++;
      uint32_t const v = GPIOB->INDR;
      uint32_t const d = v ^ p;
      p = v;
      if ((d & GPIO_Pin_13) && (v & GPIO_Pin_13)) cnt[idx]++;
      if (d & GPIO_Pin_12) idx++;
    }
    board_irq_restore(irq);
    out("start levels LRCK %d SCLK %d; SCLK rising per LRCK half:", ws0 != 0, sck0 != 0);
    for (int k = 0; k < 12; k++) out(" %lu", (unsigned long) cnt[k]);
    out(" (polls %lu)\r\n", (unsigned long) polls);
    i2s_stop();
    codec_stop();
  } else if (!strncmp(cmd, "sync ", 5)) {
    extern volatile uint32_t dbg_sync_mode;
    dbg_sync_mode = (uint32_t) atoi(cmd + 5);
    out("sync mode %lu\r\n", (unsigned long) dbg_sync_mode);
  } else if (!strcmp(cmd, "vdd")) {
    // VDD from VREFINT (1.2 V typical) on ADC1 channel 17, 16 readings.
    RCC->CFGR0 = (RCC->CFGR0 & ~RCC_ADCPRE_DIV8) | RCC_ADCPRE_DIV8;
    RCC->APB2PCENR |= RCC_APB2Periph_ADC1;
    ADC1->CTLR1 = 0;
    ADC1->CTLR2 = ADC_ADON | ADC_TSVREFE | ADC_EXTSEL | ADC_EXTTRIG;
    board_delay_ms(2);
    ADC1->CTLR2 |= ADC_RSTCAL;
    while (ADC1->CTLR2 & ADC_RSTCAL) {}
    ADC1->CTLR2 |= ADC_CAL;
    while (ADC1->CTLR2 & ADC_CAL) {}
    ADC1->SAMPTR1 = 7u << 21;   // channel 17: 239.5 cycles
    ADC1->RSQR1 = 0;
    ADC1->RSQR3 = 17;
    uint32_t mn = 4095, mx = 0, sum = 0;
    for (int k = 0; k < 64; k++) {
      ADC1->STATR = 0;
      ADC1->CTLR2 |= ADC_SWSTART;
      while (!(ADC1->STATR & ADC_EOC)) {}
      uint32_t const v = ADC1->RDATAR & 0xFFF;
      sum += v;
      if (v < mn) mn = v;
      if (v > mx) mx = v;
      board_delay_us(200);
    }
    uint32_t const avg = sum / 64;
    out("VREFINT raw avg %lu (min %lu max %lu): VDD = %lu mV (if VREFINT = 1200 mV)\r\n", (unsigned long) avg,
        (unsigned long) mn, (unsigned long) mx, avg ? (unsigned long) (1200u * 4095u / avg) : 0UL);
  } else if (!strcmp(cmd, "slipdump")) {
    extern volatile uint32_t dbg_slip_words[96];
    extern volatile uint32_t dbg_slip_n, dbg_slip_at;
    out("block %lu after start\r\n", (unsigned long) dbg_slip_at);
    for (int k = 0; k < 96; k++) out("%08lX%s", (unsigned long) dbg_slip_words[k], (k & 7) == 7 ? "\r\n" : " ");
    dbg_slip_n = 0;
  } else if (!strcmp(cmd, "meter") || !strcmp(cmd, "m")) {
    meter_on = !meter_on;
    if (meter_on) {
      audio_meter_t m;
      audio_take_meter(&m);
      meter_at = board_millis() + 500;
    }
  } else if (!strcmp(cmd, "cal")) {
    audio_calibrate();
    cal_wait = true;
    out("measuring the input DC offsets\r\n");
  } else if (!strcmp(cmd, "cal erase")) {
    out(audio_calibration_erase() ? "saved offsets erased\r\n" : "FAIL flash erase\r\n");
  } else if (!strcmp(cmd, "regs")) {
    cmd_regs();
  } else if (!strcmp(cmd, "tone")) {
    audio_set_tone(!audio_tone());
    out("test tone %s\r\n", audio_tone() ? "on" : "off");
  } else if (!strncmp(cmd, "blwrite ", 8)) {
    cmd_blwrite(cmd + 8);
  } else if (!strcmp(cmd, "restart") || !strncmp(cmd, "restart ", 8)) {
    unsigned long const hold = strtoul(cmd + 7, NULL, 10);
    audio_restart((uint32_t) (hold > 60 ? 60 : hold) * 1000);
    out("codec restart\r\n");
  } else if (!strcmp(cmd, "reboot")) {
    out("rebooting\r\n");
    board_delay_ms(20);
    board_reset();
  } else if (!strcmp(cmd, "dfu")) {
    out("DFU bootloader\r\n");
    board_delay_ms(20);
    board_reset_to_dfu();
  } else {
    cmd_help();
  }
}

void console_task(void) {
  if (!tud_cdc_connected()) {
    meter_on = false;
    return;
  }

  if (bl_active) {
    blwrite_task();
    return;
  }

  while (tud_cdc_available() && !bl_active) {
    char c = (char) tud_cdc_read_char();
    if (c == '\r' || c == '\n') {
      if (c == '\n' && line_len == 0) continue;   // CRLF
      line[line_len] = 0;
      out("\r\n");
      run(line);
      line_len = 0;
      if (!bl_active) out("> ");   // blwrite: raw bytes follow, no prompt
    } else if ((c == 8 || c == 127) && line_len) {
      line_len--;
      out("\b \b");
    } else if (c >= ' ' && line_len < sizeof(line) - 1) {
      line[line_len++] = c;
      tud_cdc_write_char(c);
      tud_cdc_write_flush();
    }
  }

  if (cal_wait) {
    audio_status_t st;
    audio_get_status(&st);
    if (st.cal != AUDIO_CAL_MEASURING) {
      cal_wait = false;
      out("\r\n");
      print_cal(&st);
      out("> ");
    }
  }

  if (meter_on && (int32_t) (board_millis() - meter_at) >= 0) {
    meter_at += 500;
    print_meter();
  }
}

void tud_cdc_line_state_cb(uint8_t itf, bool dtr, bool rts) {
  (void) itf;
  (void) rts;
  if (dtr) {
    line_len = 0;
    out("\r\nBread Modular 2X2 console. Type help.\r\n> ");
  } else {
    // 1200 baud touch (as Arduino / Pico): ../flash.sh opens the port at
    // 1200 baud and closes it to restart into the DFU bootloader.
    cdc_line_coding_t coding;
    tud_cdc_get_line_coding(&coding);
    if (coding.bit_rate == 1200) board_reset_to_dfu();
  }
}
