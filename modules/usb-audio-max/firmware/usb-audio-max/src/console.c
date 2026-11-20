#include "console.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "audio.h"
#include "board.h"
#include "boot.h"
#include "cal.h"
#include "ch32_usbhs_reg.h"
#include "codec.h"
#include "dcd_capture.h"
#include "tdm.h"
#include "tusb.h"

static char line[64];
static size_t line_len;
static bool meter_on;
static uint32_t meter_at;

// `blwrite <bytes> <crc32 hex>`: the next <bytes> raw bytes are a DFU bootloader
// image (../flash.sh --bootloader). Written only when the CRC-32 matches.
// The image is received into the audio's IN ring (audio_scratch): the audio
// stops for the transfer.
static uint8_t *bl_buf;
static uint32_t bl_len, bl_got, bl_crc, bl_deadline;
static bool bl_active;

static bool in_callback;   // inside tud_task(): no nested tud_task() in vout()

static void vout(const char *fmt, va_list ap) {
  char buf[512];
  int n = vsnprintf(buf, sizeof(buf), fmt, ap);
  if (n <= 0) return;
  if (n > (int) sizeof(buf) - 1) n = sizeof(buf) - 1;
  // Wait up to 100 ms for room in the CDC FIFO (the audio runs in interrupts),
  // then drop rather than block.
  uint32_t const t0 = board_millis();
  while (!in_callback && tud_cdc_write_available() < (uint32_t) n && tud_cdc_connected() &&
         board_millis() - t0 < 100) {
    tud_task();
  }
  tud_cdc_write(buf, (uint32_t) n);
  tud_cdc_write_flush();
}

static void out(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  vout(fmt, ap);
  va_end(ap);
}

void console_printf(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  vout(fmt, ap);
  va_end(ap);
}

static void print_v(const char *label, int32_t mv) {
  out("%s%c%ld.%03ld", label, mv < 0 ? '-' : '+', (long) (mv < 0 ? -mv : mv) / 1000,
      (long) (mv < 0 ? -mv : mv) % 1000);
}

// Buffer level now and its range since the previous status, in frames.
static void print_stream(const char *label, audio_stream_t const *s, const char *rate_label) {
  out("%s %s%s, buffer %u frames (%u..%u, held at %u), %s%lu.%04lu samples/uframe", label,
      s->streaming ? "streaming" : "idle", s->streaming && !s->primed ? " (filling)" : "", s->level, s->level_min,
      s->level_max, s->target, rate_label, (unsigned long) (s->rate >> 16),
      (unsigned long) (((s->rate & 0xFFFF) * 10000) >> 16));
}

static void cmd_status(void) {
  static uint32_t last_ms, last_blocks;
  audio_status_t st;
  audio_get_status(&st);
  tdm_align_info_t al;
  tdm_align_get(&al);
  uint32_t const now = board_millis(), blocks = tdm_rx_blocks;
  uint32_t const dt = now - last_ms;
  uint32_t const rate = dt && last_ms ? (uint32_t) ((uint64_t) (blocks - last_blocks) * TDM_BLOCK_FRAMES * 1000 / dt) : 0;
  last_ms = now;
  last_blocks = blocks;

  out("\r\nBread Modular 6x8 firmware %s (%s)\r\n", FW_VERSION, FW_GIT);
  out("MCU:   up %lu s, last reset: %s\r\n", (unsigned long) (now / 1000), board_reset_cause());
  out("USB:   %s, %s speed, VBUS dips %lu (< %u ms, ignored), unplugs %lu\r\n",
      tud_mounted() ? "configured" : "not configured", tud_speed_get() == TUSB_SPEED_HIGH ? "high" : "full",
      (unsigned long) board_vbus_dips, BOARD_VBUS_OFF_MS, (unsigned long) board_vbus_offs);
  out("Codec: %s", codec_state_name(codec_state()));
  switch (codec_address()) {
    case 0x47: out(", I2C 0x47 (S3 carrier, CLK IN open: clock master)"); break;
    case 0x45: out(", I2C 0x45 (S3 carrier, CLK IN connected: clock slave)"); break;
    case 0x44: out(", I2C 0x44 (S2 carrier, no clock link)"); break;
    default: break;
  }
  if (codec_state() == CODEC_BAD_REGS) {
    uint8_t r, g, w;
    codec_bad_reg(&r, &g, &w);
    out(" (%02Xh = 0x%02X, expected 0x%02X)", r, g, w);
  }
  out("\r\nAudio: %s, restarts %lu", audio_state_name(st.state), (unsigned long) st.restarts);
  if (rate) out(", frames %lu/s since the last status", (unsigned long) rate);
  out("\r\n");
  if (al.offset >= 0) {
    out("TDM:   slot 1 at stream bit %d (word %d, bit %d), %d of 6 LSBs toggling, slots 7/8 %s\r\n", al.offset,
        al.offset / 32, al.offset % 32, al.lsb_toggling, al.slots78_zero ? "zero" : "NOT zero");
  } else {
    out("TDM:   frame position %s\r\n", al.state == TDM_ALIGN_MEASURING ? "being measured"
                                        : al.state == TDM_ALIGN_FAILED  ? "not found (see `align`)"
                                                                        : "not measured");
  }
  cal_print_summary();
  print_stream("OUT:  ", &st.out, "feedback ");
  out(", target %u ms\r\n", st.out_target_ms);
  print_stream("IN:   ", &st.in, "packets ");
  out("\r\n");
  out("Count: OUT underruns %lu overruns %lu, IN underruns %lu overruns %lu\r\n", (unsigned long) st.out.underruns,
      (unsigned long) st.out.overruns, (unsigned long) st.in.underruns, (unsigned long) st.in.overruns);
  out("       TDM ovr %lu udr %lu slip %lu stall %lu late %lu\r\n", (unsigned long) tdm_err_ovr,
      (unsigned long) tdm_err_udr, (unsigned long) tdm_err_slip, (unsigned long) tdm_err_stall,
      (unsigned long) tdm_err_late);
  if (st.last_error[0]) out("Last:  %s\r\n", st.last_error);

  static uint32_t iso_ms;
  audio_iso_stats_t iso;
  audio_take_iso_stats(&iso);
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
  out("       iso OUT packets flagged NAK %lu (taken; %lu with the previous packet's bytes)\r\n",
      (unsigned long) dcd_iso_out_nak, (unsigned long) dcd_iso_out_nak_stale);
  out("       processing delay: worst %lu us, over 100 us %lu\r\n",
      (unsigned long) (dcd_delay_max / (SystemCoreClock / 1000000u)), (unsigned long) dcd_delay_late);
  dcd_delay_max = 0;
  uint32_t const us = SystemCoreClock / 1000000u;
  out("       worker: longest stretch without USB service %lu us, longest half RX %lu / TX %lu us\r\n",
      (unsigned long) (tdm_gap_max / us), (unsigned long) (tdm_half_max[0] / us), (unsigned long) (tdm_half_max[1] / us));
  tdm_gap_max = tdm_half_max[0] = tdm_half_max[1] = 0;
  out("OUT:  ");
  for (int c = 0; c < TDM_OUT_CHANNELS; c++) {
    gen_mode_t const m = audio_gen_mode(c);
    out(" %d:", c + 1);
    if (m == GEN_SINE) {
      out("sine");
    } else if (m == GEN_DC) {
      print_v("", audio_sample_to_mv(audio_gen_value(c)));
    } else if (m == GEN_RAW) {
      out("raw");
    } else {
      out("usb");
    }
  }
  out("\r\n");
}

static void print_meter(void) {
  static uint32_t last_ms;
  audio_meter_t m;
  audio_take_meter(&m);
  uint32_t const now = board_millis();
  uint32_t const dt = now - last_ms;
  last_ms = now;
  out("%5lu Hz |", dt ? (unsigned long) ((uint64_t) m.frames * 1000 / dt) : 0UL);
  for (int c = 0; c < TDM_IN_CHANNELS; c++) {
    int32_t const lo = audio_in_sample(c, m.in_min[c]), hi = audio_in_sample(c, m.in_max[c]);
    out(" IN%d", c + 1);
    print_v(" ", audio_sample_to_mv(audio_in_sample(c, m.in_mean[c])));
    print_v(" pp ", audio_sample_to_mv(hi - lo));
    out(c == TDM_IN_CHANNELS - 1 ? " V\r\n" : " |");
  }
}

// The USB events captured up to the first missed iso packet since the last
// `misses`: time since the previous event, microframe, event, INT_FG at the
// capture, token / endpoint, length.
static void cmd_misses(void) {
  dcd_trace_t t[AUDIO_MISS_TRACE];
  int ep;
  uint16_t step;
  if (!audio_take_miss_trace(t, &ep, &step)) {
    out("no missed iso packet since the last `misses`\r\n");
    return;
  }
  static const char *const ep_name[] = {"OUT", "IN", "feedback"};
  static const char *const tok[] = {"OUT", "SOF", "IN", "SETUP"};
  out("first missed %s packet: %u microframes since the previous one; events up to it:\r\n", ep_name[ep], step);
  uint32_t const period = (uint32_t) SysTick->CMP + 1u, us = SystemCoreClock / 1000000u;
  for (int k = 0; k < AUDIO_MISS_TRACE; k++) {
    uint16_t const uf = (uint16_t) (((t[k].frame & 0x7FFu) << 3) | (t[k].frame >> 13));
    uint32_t const dt = k ? (t[k].t + period - t[k - 1].t) % period / us : 0;
    out("  %+6lu us  uf %5u  ", (unsigned long) dt, uf);
    if (t[k].flags & USBHS_TRANSFER_FLAG) {
      out("%-5s EP%u%s len %3u", tok[(t[k].status & MASK_UIS_TOKEN) >> 4], t[k].status & MASK_UIS_ENDP,
          (t[k].status & USBHS_DEV_UIS_IS_NAK) ? " NAK" : "", t[k].len);
    } else {
      out("%s", (t[k].flags & USBHS_SETUP_FLAG)     ? "SETUP"
                : (t[k].flags & USBHS_BUS_RST_FLAG) ? "bus reset"
                                                    : "suspend");
    }
    out("  INT_FG %02X\r\n", t[k].fg);
  }
}

static void cmd_regs(void) {
  for (uint8_t r = PCM_REG_FIRST; r <= PCM_REG_LAST; r++) {
    uint8_t v;
    if (codec_read(r, &v)) {
      out("  %02Xh = 0x%02X%s", r, v, (r & 3) == 3 ? "\r\n" : "");
    } else {
      out("  %02Xh: ----%s", r, (r & 3) == 3 ? "\r\n" : "");
    }
  }
  out("\r\n");
}

static void print_bits(uint32_t w) {
  for (int i = 31; i >= 0; i--) {
    out("%c", (w >> i) & 1u ? '1' : '.');
    if (i && !(i & 7)) out(" ");
  }
}

static void cmd_raw(void) {
  uint32_t w[24];
  if (!tdm_raw_capture(w, 24, 50)) {
    out("raw: TDM not running\r\n");
    return;
  }
  out("raw: 3 frames of stream words (word 0 = first after the DMA start)\r\n");
  for (int i = 0; i < 24; i++) out("%08lX%s", (unsigned long) w[i], (i & 7) == 7 ? "\r\n" : " ");
}

static void cmd_align(bool measure) {
  if (measure) {
    tdm_align_start(4800);
    uint32_t const t0 = board_millis();
    tdm_align_info_t al;
    do {
      tud_task();
      tdm_align_task();
      tdm_align_get(&al);
    } while (al.state == TDM_ALIGN_MEASURING && board_millis() - t0 < 500);
  }
  tdm_align_info_t al;
  tdm_align_get(&al);
  out("frame period, 8 words of 32 bits (1 = ever set / ever toggled over 4800 frames):\r\n");
  for (int j = 0; j < TDM_SLOTS; j++) {
    out("  w%d set ", j);
    print_bits(al.ones[j]);
    out("  toggled ");
    print_bits(al.toggled[j]);
    out("\r\n");
  }
  if (al.state == TDM_ALIGN_OK) {
    out("slot 1 at stream bit %d (word %d, bit %d): %d of 6 LSBs toggling, slots 7/8 %s\r\n", al.offset,
        al.offset / 32, al.offset % 32, al.lsb_toggling, al.slots78_zero ? "zero" : "NOT zero");
  } else {
    out("no unique slot position (%d candidates)\r\n", al.candidates);
  }
}

static int parse_ch(const char *s, int n) {
  if (!strncmp(s, "all", 3)) return 0;
  int const c = atoi(s);
  return c >= 1 && c <= n ? c : -1;
}

// "1.25", "-3", "+0.5" -> millivolts
static bool parse_mv(const char *s, int32_t *mv) {
  char *end;
  long const whole = strtol(s, &end, 10);
  bool const neg = s[strspn(s, " ")] == '-';
  int32_t frac = 0, scale = 100;
  if (*end == '.') {
    for (end++; *end >= '0' && *end <= '9'; end++) {
      frac += (*end - '0') * scale;
      scale /= 10;
    }
  }
  if (end == s) return false;
  *mv = (int32_t) (labs(whole) * 1000 + frac) * (neg ? -1 : 1);
  return true;
}

static void cmd_blwrite(char *args) {
  char *end;
  unsigned long const len = strtoul(args, &end, 10);
  unsigned long const crc = strtoul(end, &end, 16);
  uint32_t room;
  audio_scratch(&room);
  if (room > BOOT_APP_BASE) room = BOOT_APP_BASE;
  if (len < 8 || len > room) {
    out("blwrite: size must be 8..%lu bytes\r\n", (unsigned long) room);
    return;
  }
  bl_buf = audio_scratch(NULL);   // stops the audio
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
      audio_restart(0);
      out("blwrite: FAIL timeout, %lu of %lu bytes\r\n> ", (unsigned long) bl_got, (unsigned long) bl_len);
    }
    return;
  }
  bl_active = false;
  uint32_t const crc = board_crc32(bl_buf, bl_len);
  if (crc != bl_crc) {
    audio_restart(0);
    out("blwrite: FAIL CRC %08lX, expected %08lX\r\n> ", (unsigned long) crc, (unsigned long) bl_crc);
    return;
  }
  bool const ok = board_write_bootloader(bl_buf, bl_len);
  audio_restart(0);
  out(ok ? "blwrite: OK, bootloader written and verified (%lu bytes)\r\n> "
         : "blwrite: FAIL flash write/verify (%lu bytes): retry before any reset\r\n> ",
      (unsigned long) bl_len);
}

static void cmd_help(void) {
  out("\r\ncommands:\r\n"
      "  status        firmware, USB, codec, TDM, stream state and error counters (also: Enter)\r\n"
      "  meter         toggle a 2 Hz line: frame rate, IN 1-6 mean and peak-to-peak volts\r\n"
      "  regs          PCM3168A registers 40h-5Eh\r\n"
      "  raw           24 received TDM words as they come\r\n"
      "  align         measure the TDM frame position again and show the bit maps\r\n");
  out("  tone [n|all]  1 kHz sine, half scale, on OUT n (default all) instead of USB\r\n"
      "  dc <n|all> <volts>  DC level on OUT n instead of USB, e.g. `dc 3 -2.5`\r\n"
      "  off           every OUT back to the USB audio\r\n"
      "  looptest      step every OUT, find the IN it is patched to, check gain / offset\r\n");
  out("  cal           show the calibration\r\n"
      "  cal in        input offsets: unpatch IN 1-6 first (every OUT goes to +2 V meanwhile)\r\n"
      "  cal out       output offsets + loop gains: patch OUTs to INs first, any pairing\r\n"
      "  cal ref <n> <volts>  after `dc <n> 4`: the meter reading at OUT n (optional)\r\n"
      "  cal erase     forget the calibration\r\n");
  out("  misses        USB events captured up to the first missed iso packet since the last `misses`\r\n");
  out("  restart [s]   reset + restart codec and TDM (codec held in reset s seconds)\r\n"
      "  reboot        reset the MCU\r\n"
      "  dfu           reset into the DFU bootloader (../flash.sh uses a 1200 baud touch)\r\n"
      "  blwrite       <bytes> <crc32>: rewrite the DFU bootloader (../flash.sh --bootloader)\r\n");
}

static bool audio_ready(const char *cmd) {
  if (audio_get_state() == AUDIO_RUNNING) return true;
  out("%s: audio not running (%s)\r\n", cmd, audio_state_name(audio_get_state()));
  return false;
}

static void run(char *cmd) {
  if (cmd[0] == 0 || !strcmp(cmd, "status") || !strcmp(cmd, "s")) {
    cmd_status();
    return;
  }
  if (!strcmp(cmd, "meter") || !strcmp(cmd, "m")) {
    meter_on = !meter_on;
    if (meter_on) {
      audio_meter_t m;
      audio_take_meter(&m);
      meter_at = board_millis() + 500;
    }
    return;
  }
  if (cal_busy()) {
    out("busy: a calibration / looptest is running\r\n");
    return;
  }
  if (!strcmp(cmd, "misses")) {
    cmd_misses();
  } else if (!strcmp(cmd, "regs")) {
    cmd_regs();
  } else if (!strcmp(cmd, "raw")) {
    cmd_raw();
  } else if (!strcmp(cmd, "align")) {
    cmd_align(true);
  } else if (!strcmp(cmd, "tone") || !strncmp(cmd, "tone ", 5)) {
    int const c = cmd[4] ? parse_ch(cmd + 5, TDM_OUT_CHANNELS) : 0;
    if (c < 0) {
      out("tone: OUT 1-%d or all\r\n", TDM_OUT_CHANNELS);
      return;
    }
    for (int i = 0; i < TDM_OUT_CHANNELS; i++) {
      if (!c || i == c - 1) audio_gen_set(i, GEN_SINE, 0);
    }
  } else if (!strncmp(cmd, "dc ", 3)) {
    char *arg = cmd + 3;
    int const c = parse_ch(arg, TDM_OUT_CHANNELS);
    char *v = strchr(arg, ' ');
    int32_t mv;
    if (c < 0 || !v || !parse_mv(v + 1, &mv)) {
      out("dc: dc <1-%d|all> <volts>\r\n", TDM_OUT_CHANNELS);
      return;
    }
    for (int i = 0; i < TDM_OUT_CHANNELS; i++) {
      if (!c || i == c - 1) audio_gen_set(i, GEN_DC, audio_mv_to_sample(mv));
    }
  } else if (!strcmp(cmd, "off")) {
    for (int i = 0; i < TDM_OUT_CHANNELS; i++) audio_gen_set(i, GEN_USB, 0);
  } else if (!strcmp(cmd, "looptest")) {
    if (audio_ready("looptest")) cal_start_looptest();
  } else if (!strcmp(cmd, "cal")) {
    cal_print();
  } else if (!strcmp(cmd, "cal in")) {
    if (audio_ready("cal in")) cal_start_inputs();
  } else if (!strcmp(cmd, "cal out")) {
    if (audio_ready("cal out")) cal_start_outputs();
  } else if (!strncmp(cmd, "cal ref ", 8)) {
    char *end;
    long const n = strtol(cmd + 8, &end, 10);
    int32_t mv;
    if (*end != ' ' || !parse_mv(end + 1, &mv)) {
      out("cal ref: cal ref <1-8> <volts measured>\r\n");
      return;
    }
    cal_ref((int) n, mv);
  } else if (!strcmp(cmd, "cal erase")) {
    out(cal_erase() ? "cal erase: done, uncalibrated\r\n" : "cal erase: flash erase FAILED\r\n");
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
    in_callback = true;
    out("\r\nBread Modular 6x8 console. Type help.\r\n> ");
    in_callback = false;
  } else {
    // 1200 baud touch (as Arduino / Pico): ../flash.sh opens the port at
    // 1200 baud and closes it to restart into the DFU bootloader.
    cdc_line_coding_t coding;
    tud_cdc_get_line_coding(&coding);
    if (coding.bit_rate == 1200) board_reset_to_dfu();
  }
}
