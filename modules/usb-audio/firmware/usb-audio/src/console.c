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
static bool meter_on;
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

static void cmd_status(void) {
  audio_status_t st;
  audio_get_status(&st);
  out("\r\nBread Modular 2X2 firmware %s (%s)\r\n", FW_VERSION, FW_GIT);
  out("USB:   %s, %s speed\r\n", tud_mounted() ? "configured" : "not configured",
      tud_speed_get() == TUSB_SPEED_HIGH ? "high" : "full");
  out("Codec: %s", codec_state_name(codec_state()));
  if (codec_state() == CODEC_RUNNING) out(", ID 0x%02X, %lu Hz", codec_chip_id(), (unsigned long) st.rate_codec);
  out(", host rate %lu Hz\r\n", (unsigned long) st.rate_host);
  if (st.dc_calibrated) {
    print_mv("IN DC: offsets IN 1 ", to_mv(st.dc_offset[0], IN_FS_MV));
    print_mv(", IN 2 ", to_mv(st.dc_offset[1], IN_FS_MV));
    out(" subtracted\r\n");
  } else {
    out("IN DC: measuring the offsets (IN 1/2 unpatched)\r\n");
  }
  out("I2S:   %s, %lu frames/half%s\r\n", i2s_running() ? "running" : "stopped", (unsigned long) AUDIO_BLOCK_FRAMES,
      audio_tone() ? ", test tone on" : "");
  out("OUT:   %s%s, FIFO %u B, feedback %lu.%04lu samples/uframe\r\n",
      st.out_streaming ? "streaming" : "idle", st.out_streaming && !st.out_primed ? " (filling)" : "",
      st.out_fifo, (unsigned long) (st.feedback >> 16), (unsigned long) (((st.feedback & 0xFFFF) * 10000) >> 16));
  out("IN:    %s, FIFO %u B\r\n", st.in_streaming ? "streaming" : "idle", st.in_fifo);
  out("Count: restarts %lu, OUT underruns %lu, IN overruns %lu, I2S ovr %lu udr %lu slip %lu stall %lu late %lu\r\n",
      (unsigned long) st.restarts, (unsigned long) st.out_underruns, (unsigned long) st.in_overruns,
      (unsigned long) i2s_err_ovr, (unsigned long) i2s_err_udr, (unsigned long) i2s_err_slip,
      (unsigned long) i2s_err_stall, (unsigned long) i2s_err_late);
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
  out("DCD:   capture overflows %lu, iso waits timed out %lu\r\n", (unsigned long) dcd_capture_overflows,
      (unsigned long) dcd_capture_iso_timeouts);
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

static uint32_t crc32(uint8_t const *p, uint32_t n) {
  uint32_t c = 0xFFFFFFFFu;
  while (n--) {
    c ^= *p++;
    for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
  }
  return ~c;
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
  uint32_t const crc = crc32(bl_buf, bl_len);
  if (crc != bl_crc) {
    out("blwrite: FAIL CRC %08lX, expected %08lX\r\n> ", (unsigned long) crc, (unsigned long) bl_crc);
    return;
  }
  i2s_stop();
  codec_stop();
  bool const ok = board_write_bootloader(bl_buf, bl_len);
  audio_restart();
  out(ok ? "blwrite: OK, bootloader written and verified (%lu bytes)\r\n> "
         : "blwrite: FAIL flash write/verify (%lu bytes): retry before any reset\r\n> ",
      (unsigned long) bl_len);
}

static void cmd_help(void) {
  out("\r\ncommands:\r\n"
      "  status   firmware, USB, codec, I2S and stream state (also: Enter)\r\n"
      "  meter    toggle a 2 Hz line: measured LRCK, DC and peak per jack (pots up)\r\n");
  out("  cal      measure the input DC offsets again: unpatch IN 1/2 first\r\n"
      "  tone     toggle a 1 kHz test tone (half scale) on OUT 1/2 instead of the USB audio\r\n"
      "  regs     dump CS4270 registers 01h-08h\r\n"
      "  restart  reset and restart codec + I2S\r\n"
      "  reboot   reset the MCU\r\n"
      "  dfu      reset into the DFU bootloader (../flash.sh uses a 1200 baud touch)\r\n"
      "  blwrite  <bytes> <crc32>: rewrite the DFU bootloader (../flash.sh --bootloader)\r\n");
}

static void run(char *cmd) {
  if (cmd[0] == 0 || !strcmp(cmd, "status") || !strcmp(cmd, "s")) {
    cmd_status();
  } else if (!strcmp(cmd, "meter") || !strcmp(cmd, "m")) {
    meter_on = !meter_on;
    if (meter_on) {
      audio_meter_t m;
      audio_take_meter(&m);
      meter_at = board_millis() + 500;
    }
  } else if (!strcmp(cmd, "cal")) {
    audio_calibrate();
    out("measuring the input DC offsets (0.8 s)\r\n");
  } else if (!strcmp(cmd, "regs")) {
    cmd_regs();
  } else if (!strcmp(cmd, "tone")) {
    audio_set_tone(!audio_tone());
    out("test tone %s\r\n", audio_tone() ? "on" : "off");
  } else if (!strncmp(cmd, "blwrite ", 8)) {
    cmd_blwrite(cmd + 8);
  } else if (!strcmp(cmd, "restart")) {
    audio_restart();
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
    out("\r\nBread Modular 2X2 console. Type help.\r\n> ");
  } else {
    // 1200 baud touch (as Arduino / Pico): ../flash.sh opens the port at
    // 1200 baud and closes it to restart into the DFU bootloader.
    cdc_line_coding_t coding;
    tud_cdc_get_line_coding(&coding);
    if (coding.bit_rate == 1200) board_reset_to_dfu();
  }
}
