#include "audio.h"

#include <string.h>

#include "audio_config.h"
#include "board.h"
#include "codec.h"
#include "i2s.h"
#include "dcd_capture.h"
#include "device/dcd.h"
#include "tusb.h"
#include "usb_descriptors.h"

#define BLOCK_BYTES (AUDIO_BLOCK_FRAMES * AUDIO_FRAME_BYTES)

static uint32_t const rates[] = {48000, 96000, 192000};

static volatile uint32_t rate_host = AUDIO_RATE_DEFAULT;
static volatile uint32_t rate_codec;
static uint32_t codec_retry_at, restarts;
static const char *last_error = "";

// Both streams hold their buffer at a target level with a slow proportional
// loop on the low-passed level (frames << 16): LOOP_GAIN_SHIFT 14 is 0.5
// frames/s per frame of error (2 s time constant) at every rate, clamped to
// +-1/128 of the nominal rate. Slow on purpose: the host sees a nearly constant
// feedback value and nearly constant IN packet sizes, and the loop stays stable
// whatever delay or smoothing the host applies to the feedback.
#define LOOP_GAIN_SHIFT 14
#define LOOP_CLAMP_SHIFT 7

typedef struct {
  volatile bool streaming, primed;
  int32_t lvl_lp;                      // buffer level, frames << 16, low-passed
  uint16_t lvl, lvl_min, lvl_max;      // frames; min / max since the last status
  volatile uint32_t rate;              // 16.16 samples per microframe
  volatile uint32_t underruns, overruns;
} stream_t;

// OUT (USB -> DAC): buffer = TinyUSB OUT FIFO, level taken after each block
// read, rate = the explicit feedback value. The target grows by 1 ms per
// underrun (up to AUDIO_TARGET_MS_MAX, until the next reset).
static stream_t out;
static uint32_t out_target_ms = AUDIO_TARGET_MS;
static bool out_udr_pending;           // counted when the stream refills (not at its end)
static bool out_fade_in;
static int32_t out_last[2];            // last samples sent to the DAC, for the fade to silence

// IN (ADC -> USB): buffer = in_ring, level taken after each block write,
// rate = frames per IN packet. in_stage() loads one packet at a time into
// TinyUSB's IN FIFO: silence at the nominal rate until the ring is primed.
#define IN_RING_MASK (AUDIO_IN_RING_FRAMES - 1u)
static stream_t in;
static uint32_t in_ring[AUDIO_IN_RING_FRAMES * AUDIO_CHANNELS];
static uint32_t in_wr, in_rd;          // frames, free running
static uint32_t in_acc;                // packet size accumulator, 16.16 frames
static uint32_t in_taken;              // packets the host took since the last I2S block
static bool in_ovr_pending;            // counted when the host polls again (not at the stream's end)
static bool in_adc_live;               // the ADC has sent a sample since the codec started

// Input DC offset, 24-bit codes per input (IN 1, IN 2), subtracted from every
// sample. `cal` measures it with IN 1/2 unpatched (0 V) and saves it in the
// settings page; without saved offsets it is measured after every power-up.
// A measurement averages CAL_WINDOW_MS windows until CAL_WINDOWS in a row are
// quiet (peak to peak <= CAL_NOISE) and agree (means within CAL_STABLE), so it
// waits for the analog stage to settle and does not take a signal for an offset.
#define CAL_SETTLE_MS   100
#define CAL_WINDOW_MS   100
#define CAL_WINDOWS     4
#define CAL_TIMEOUT_MS  10000
#define CAL_STABLE      764            // 0.5 mV at the jack (5.49 V full scale)
#define CAL_NOISE       15280          // 10 mV
#define CAL_LIMIT       152800         // 100 mV: more is not an offset
#define SETTINGS_MAGIC  0x32583243u    // "C2X2"

typedef struct {
  uint32_t magic;
  int32_t dc_offset[2];
  uint32_t crc;                        // of the fields before it
} settings_t;

static int32_t dc_offset[2];
static audio_cal_t cal_result = AUDIO_CAL_NONE;
static enum { CAL_IDLE, CAL_SETTLE, CAL_RUN } cal_state;
static bool cal_save;
static uint32_t cal_at, cal_deadline, cal_windows;
static int32_t cal_hist[CAL_WINDOWS][2];
static volatile uint32_t cal_left;     // frames still to sum (interrupt side)
static int64_t cal_sum[2];
static int32_t cal_min[2], cal_max[2];
static uint32_t cal_n;

// Test tone (console `tone`): 1 kHz sine at half scale on both outputs instead of the USB data.
static volatile bool tone_on;
static uint32_t tone_phase;
static int32_t sine_tab[960];          // one period at 960 kHz, peak 2^22

// Meters (interrupt side)
static int32_t m_in_peak[2], m_out_peak[2];
static int64_t m_in_sum[2], m_out_sum[2];
static uint32_t m_frames;

static inline uint32_t ms_frames(uint32_t rate, uint32_t ms) {
  return rate / 1000 * ms;
}

static inline uint32_t nominal_rate(uint32_t rate) {
  return (rate / 8000) << 16;   // samples per 125 us microframe, 16.16
}

// Level low-pass: 64 ms at every rate (one step per I2S block).
static inline int lvl_lp_shift(uint32_t rate) {
  return rate >= 192000 ? 8 : rate >= 96000 ? 7 : 6;
}

// One step of a stream's loop: `level` frames in the buffer against `target`.
// `sign` +1: a fuller buffer raises the rate (IN packets), -1: lowers it (OUT feedback).
static void stream_loop(stream_t *st, uint32_t rate, uint32_t level, uint32_t target, int sign) {
  st->lvl = (uint16_t) level;
  if (level < st->lvl_min) st->lvl_min = (uint16_t) level;
  if (level > st->lvl_max) st->lvl_max = (uint16_t) level;
  st->lvl_lp += ((int32_t) (level << 16) - st->lvl_lp) >> lvl_lp_shift(rate);
  int32_t const nominal = (int32_t) nominal_rate(rate);
  int32_t const clamp = nominal >> LOOP_CLAMP_SHIFT;
  int32_t d = (st->lvl_lp - (int32_t) (target << 16)) >> LOOP_GAIN_SHIFT;
  if (d > clamp) d = clamp;
  if (d < -clamp) d = -clamp;
  st->rate = (uint32_t) (nominal + sign * d);
}

static void stream_prime(stream_t *st, uint32_t rate, uint32_t target) {
  st->lvl_lp = (int32_t) (target << 16);
  st->rate = nominal_rate(rate);
  st->primed = true;
}

static inline int32_t iabs(int32_t v) {
  return v < 0 ? -v : v;
}

static inline int32_t clamp24(int32_t v) {
  return v > 0x7FFFFF ? 0x7FFFFF : v < -0x800000 ? -0x800000 : v;
}

static inline uint32_t rx_word(const uint16_t *src, int i) {
  return ((uint32_t) src[2 * i] << 16) | src[2 * i + 1];
}

// A block takes about 40 us to convert, and an iso endpoint has to be served
// before its next packet, 125 us after the one captured (the receive buffer is
// overwritten, the sent packet goes out again): the USB transfers are processed
// between the quarters of a block as well as between the blocks (board.c).
#define USB_SERVICE_FRAMES (AUDIO_BLOCK_FRAMES / 4)

static inline void usb_service(int frame) {
  if (frame % USB_SERVICE_FRAMES == USB_SERVICE_FRAMES - 1) tud_int_handler(0);
}

//--------------------------------------------------------------------+
// I2S interrupt side
//--------------------------------------------------------------------+

// Loads the next IN packet into TinyUSB's IN FIFO, which holds nothing else:
// called once when the stream opens and then each time TinyUSB has moved the
// loaded packet to the endpoint. The packet size comes from the accumulated
// rate, so the sizes are the nominal one with a single +-1 now and then.
static void in_stage(void) {
  bool const live = in.primed && rate_codec == rate_host;
  in_acc += live ? in.rate : nominal_rate(rate_host);
  uint32_t const n = in_acc >> 16;
  in_acc &= 0xFFFFu;

  if (live && in_wr - in_rd >= n) {
    uint32_t const at = in_rd & IN_RING_MASK;
    uint32_t const first = TU_MIN(n, AUDIO_IN_RING_FRAMES - at);
    tud_audio_write(&in_ring[at * AUDIO_CHANNELS], (uint16_t) (first * AUDIO_FRAME_BYTES));
    if (n > first) tud_audio_write(in_ring, (uint16_t) ((n - first) * AUDIO_FRAME_BYTES));
    in_rd += n;
  } else {
    static uint32_t const silence[AUDIO_EP_SIZE / AUDIO_SUBSLOT_BYTES];
    if (live) in.underruns++;
    in.primed = false;   // refill to the target (audio_i2s_rx)
    tud_audio_write(silence, (uint16_t) (n * AUDIO_FRAME_BYTES));
  }
}

// The ADC sends zeros for about 20 ms after the codec has started (after one
// stray word from I2S): the input is held at zero until a block without an
// all-zero frame, or it would sit at minus the offset meanwhile, a step each way.
static bool adc_muted(const uint16_t *src) {
  if (in_adc_live) return false;
  for (int i = 0; i < AUDIO_BLOCK_FRAMES; i++) {
    if (!(rx_word(src, 2 * i) | rx_word(src, 2 * i + 1))) return true;
  }
  in_adc_live = true;
  return false;
}

// ADC -> USB: samples MSB-justified in 32 bits (UAC2 24-in-32), IN 1 first.
void audio_i2s_rx(const uint16_t *src) {
  uint32_t zero = 0;
  bool const muted = adc_muted(src);
  for (int i = 0; i < AUDIO_BLOCK_FRAMES; i++) {
    uint32_t const w[2] = {rx_word(src, 2 * i + I2S_SLOT_A), rx_word(src, 2 * i + I2S_SLOT_B)};
    uint32_t *const dst = &in_ring[((in_wr + (uint32_t) i) & IN_RING_MASK) * AUDIO_CHANNELS];
    zero |= w[0] | w[1];
    for (int ch = 0; ch < 2; ch++) {
      int32_t const raw = (int32_t) i2s_rx_to_sample(w[ch]) >> 8;
      if (cal_left && !muted) {
        cal_sum[ch] += raw;
        if (raw < cal_min[ch]) cal_min[ch] = raw;
        if (raw > cal_max[ch]) cal_max[ch] = raw;
      }
      int32_t const s = muted ? 0 : clamp24(raw - dc_offset[ch]);
      dst[ch] = (uint32_t) s << 8;
      int32_t const a = iabs(s);
      if (a > m_in_peak[ch]) m_in_peak[ch] = a;
      m_in_sum[ch] += s;
    }
    if (cal_left && !muted) {
      cal_n++;
      cal_left--;
    }
    usb_service(i);   // may send from the ring: in_wr moves after the block
  }
  m_frames += AUDIO_BLOCK_FRAMES;
  if (zero & I2S_RX_ZERO_BITS) i2s_report_slip();
  in_wr += AUDIO_BLOCK_FRAMES;

  // The packets of one block period leave before the next block arrives, so
  // the level after a write is held one block above the target.
  uint32_t const rate = rate_codec ? rate_codec : rate_host;
  uint32_t const target = ms_frames(rate, AUDIO_TARGET_MS) + AUDIO_BLOCK_FRAMES;
  uint32_t level = in_wr - in_rd;
  if (!in.primed) {
    if (level > target) {   // idle: keep the newest audio only
      in_rd = in_wr - target;
      level = target;
    }
    // The host starts to poll some time after it has opened the stream.
    if (in.streaming && in_taken && rate_codec == rate_host && level == target) {
      stream_prime(&in, rate, target);
      if (in_ovr_pending) in.overruns++;
      in_ovr_pending = false;
    }
  } else if (level > target + ms_frames(rate, 2)) {
    // The host stopped polling: silence until it takes packets again, then
    // start over from the newest audio.
    in.primed = false;
    in_ovr_pending = true;
  }
  if (in.primed) stream_loop(&in, rate, level, target, +1);
  in_taken = 0;
}

// USB -> DAC, and the explicit feedback that holds the OUT FIFO at the target level.
void audio_i2s_tx(uint16_t *dst) {
  uint32_t buf[AUDIO_BLOCK_FRAMES * 2];
  bool have = false;
  tu_fifo_t *const ff = tud_audio_get_ep_out_ff();

  if (out.streaming && ff) {
    uint32_t const rate = rate_codec ? rate_codec : rate_host;
    uint32_t const target = ms_frames(rate, out_target_ms);
    uint32_t avail = tu_fifo_count(ff) / AUDIO_FRAME_BYTES;

    if (!out.primed && rate_codec == rate_host && avail >= target + AUDIO_BLOCK_FRAMES) {
      // Start on the target: drop what came in beyond it while filling.
      tu_fifo_discard_n(ff, (uint16_t) ((avail - target - AUDIO_BLOCK_FRAMES) * AUDIO_FRAME_BYTES));
      avail = target + AUDIO_BLOCK_FRAMES;
      stream_prime(&out, rate, target);
      out_fade_in = true;
      if (out_udr_pending) {   // the stream went on after an underrun
        out_udr_pending = false;
        out.underruns++;
        if (out_target_ms < AUDIO_TARGET_MS_MAX) out_target_ms++;
      }
    }
    if (out.primed) {
      if (avail >= AUDIO_BLOCK_FRAMES) {
        tu_fifo_read_n(ff, buf, BLOCK_BYTES);
        have = true;
        avail -= AUDIO_BLOCK_FRAMES;
        if (avail > target + ms_frames(rate, 3)) {
          // The host sent more than the feedback asked for: drop the oldest audio.
          tu_fifo_discard_n(ff, (uint16_t) ((avail - target) * AUDIO_FRAME_BYTES));
          avail = target;
          out.lvl_lp = (int32_t) (target << 16);
          out.overruns++;
        }
        stream_loop(&out, rate, avail, target, -1);
      } else {
        out.primed = false;   // refill to the target before playing again
        out_udr_pending = true;
      }
    }
    if (!out.primed) out.rate = nominal_rate(rate_host);
    tud_audio_fb_set(out.rate);
  }

  if (tone_on) {
    uint32_t const step = 960000u / (rate_codec ? rate_codec : rate_host);
    for (int i = 0; i < AUDIO_BLOCK_FRAMES; i++) {
      buf[2 * i] = buf[2 * i + 1] = (uint32_t) sine_tab[tone_phase] << 8;
      tone_phase += step;
      if (tone_phase >= 960) tone_phase -= 960;
    }
  } else if (have) {
    if (out_fade_in) {   // first block of a stream or after an underrun
      for (int i = 0; i < AUDIO_BLOCK_FRAMES * 2; i++) {
        buf[i] = (uint32_t) (((int32_t) buf[i] >> 8) * (i / 2 + 1) / AUDIO_BLOCK_FRAMES) << 8;
      }
      out_fade_in = false;
    }
    out_last[0] = (int32_t) buf[2 * AUDIO_BLOCK_FRAMES - 2] >> 8;
    out_last[1] = (int32_t) buf[2 * AUDIO_BLOCK_FRAMES - 1] >> 8;
  } else if (out_last[0] | out_last[1]) {
    // The audio ended (stream closed or underrun): one block from the last sample to silence.
    for (int i = 0; i < AUDIO_BLOCK_FRAMES * 2; i++) {
      buf[i] = (uint32_t) (out_last[i & 1] * (AUDIO_BLOCK_FRAMES - 1 - i / 2) / AUDIO_BLOCK_FRAMES) << 8;
    }
    out_last[0] = out_last[1] = 0;
  } else {
    memset(buf, 0, sizeof(buf));
  }

  for (int i = 0; i < AUDIO_BLOCK_FRAMES; i++) {
    for (int ch = 0; ch < 2; ch++) {
      uint32_t const w = i2s_sample_to_tx(buf[2 * i + ch]);
      int const k = 2 * i + (ch ? I2S_SLOT_B : I2S_SLOT_A);
      dst[2 * k] = (uint16_t) (w >> 16);
      dst[2 * k + 1] = (uint16_t) w;
      int32_t const s = (int32_t) buf[2 * i + ch] >> 8;
      int32_t const a = iabs(s);
      if (a > m_out_peak[ch]) m_out_peak[ch] = a;
      m_out_sum[ch] += s;
    }
    usb_service(i);
  }
}

//--------------------------------------------------------------------+
// Main-loop side
//--------------------------------------------------------------------+

static void cal_start(bool save);

void audio_init(void) {
  double x = 1.0, y = 0.0;   // rotation by 2 pi / 960 per entry (no libm)
  for (int i = 0; i < 960; i++) {
    sine_tab[i] = (int32_t) (y * (double) (1 << 22));
    double const nx = x * 0.9999785816641292 - y * 0.006544937967351858;
    y = x * 0.006544937967351858 + y * 0.9999785816641292;
    x = nx;
  }
  rate_host = AUDIO_RATE_DEFAULT;
  codec_retry_at = board_millis();
  out.lvl_min = in.lvl_min = UINT16_MAX;

  settings_t const *const set = board_settings();
  if (set->magic == SETTINGS_MAGIC && set->crc == board_crc32(set, offsetof(settings_t, crc))) {
    dc_offset[0] = set->dc_offset[0];
    dc_offset[1] = set->dc_offset[1];
    cal_result = AUDIO_CAL_SAVED;
  } else {
    cal_start(false);   // nothing saved: measure now, inputs assumed unpatched
  }
}

// Both streams start over: the buffered audio is dropped and the IN packets
// carry silence until the ring is filled again.
static void streams_flush(void) {
  uint32_t const irq = board_irq_mask();
  out.primed = in.primed = false;
  out_udr_pending = in_ovr_pending = false;
  in_rd = in_wr;
  board_irq_restore(irq);
}

// Codec reset + configuration with the clocks held, both I2S slaves armed,
// then the clocks start (i2s.h: the only start that aligns the slaves).
static void streams_start(uint32_t rate) {
  i2s_stop();
  rate_codec = 0;
  streams_flush();
  codec_state_t const s = codec_prepare(rate);
  if (s != CODEC_READY) {
    last_error = codec_state_name(s);
    codec_retry_at = board_millis() + 2000;
    return;
  }
  in_adc_live = false;
  i2s_start();
  // The clocks have started within 1 ms of PDN on the board; allow 50 ms.
  if (!codec_run() || !i2s_lrck_toggling(50000)) {
    i2s_stop();
    codec_stop();
    last_error = "no LRCK from the codec";
    codec_retry_at = board_millis() + 1000;
    return;
  }
  rate_codec = rate;
  restarts++;
  if (cal_state != CAL_IDLE) cal_start(cal_save);   // a calibration in progress starts over
}

void audio_restart(uint32_t hold_ms) {
  i2s_stop();
  codec_stop();
  rate_codec = 0;
  streams_flush();
  codec_retry_at = board_millis() + hold_ms;
}

static void cal_start(bool save) {
  uint32_t const now = board_millis();
  cal_left = 0;
  cal_save = save;
  cal_windows = 0;
  cal_state = CAL_SETTLE;
  cal_at = now + CAL_SETTLE_MS;
  cal_deadline = now + CAL_TIMEOUT_MS;
  cal_result = AUDIO_CAL_MEASURING;
}

void audio_calibrate(void) {
  cal_start(true);
}

static void cal_window(void) {
  uint32_t const irq = board_irq_mask();
  for (int c = 0; c < 2; c++) {
    cal_sum[c] = 0;
    cal_min[c] = INT32_MAX;
    cal_max[c] = INT32_MIN;
  }
  cal_n = 0;
  cal_left = rate_codec / 1000 * CAL_WINDOW_MS;
  board_irq_restore(irq);
}

static bool settings_save(void) {
  settings_t set = {.magic = SETTINGS_MAGIC, .dc_offset = {dc_offset[0], dc_offset[1]}};
  set.crc = board_crc32(&set, offsetof(settings_t, crc));
  if (!memcmp(&set, board_settings(), sizeof(set))) return true;
  i2s_stop();
  codec_stop();
  bool const ok = board_settings_write(&set, sizeof(set));
  audio_restart(0);
  return ok;
}

bool audio_calibration_erase(void) {
  i2s_stop();
  codec_stop();
  bool const ok = board_settings_write(NULL, 0);
  audio_restart(0);
  if (ok && cal_result == AUDIO_CAL_SAVED) cal_result = AUDIO_CAL_MEASURED;
  return ok;
}

static void cal_task(uint32_t now) {
  if (cal_state == CAL_IDLE) return;
  if ((int32_t) (now - cal_deadline) >= 0) {
    cal_left = 0;
    cal_state = CAL_IDLE;
    cal_result = AUDIO_CAL_UNSTEADY;   // the offsets stay as they were
  } else if (cal_state == CAL_SETTLE && (int32_t) (now - cal_at) >= 0) {
    cal_window();
    cal_state = CAL_RUN;
  } else if (cal_state == CAL_RUN && !cal_left && cal_n) {
    int32_t *const mean = cal_hist[cal_windows % CAL_WINDOWS];
    bool quiet = true;
    for (int c = 0; c < 2; c++) {
      mean[c] = (int32_t) (cal_sum[c] / (int32_t) cal_n);
      if (cal_max[c] - cal_min[c] > CAL_NOISE) quiet = false;
    }
    cal_windows = quiet ? cal_windows + 1 : 0;

    int32_t offset[2];
    bool steady = cal_windows >= CAL_WINDOWS;
    for (int c = 0; steady && c < 2; c++) {
      int32_t lo = INT32_MAX, hi = INT32_MIN, sum = 0;
      for (int k = 0; k < CAL_WINDOWS; k++) {
        if (cal_hist[k][c] < lo) lo = cal_hist[k][c];
        if (cal_hist[k][c] > hi) hi = cal_hist[k][c];
        sum += cal_hist[k][c];
      }
      offset[c] = sum / CAL_WINDOWS;
      steady = hi - lo <= CAL_STABLE;
    }
    if (!steady) {
      cal_window();
      return;
    }
    cal_state = CAL_IDLE;
    if (iabs(offset[0]) > CAL_LIMIT || iabs(offset[1]) > CAL_LIMIT) {
      cal_result = AUDIO_CAL_RANGE;
      return;
    }
    dc_offset[0] = offset[0];
    dc_offset[1] = offset[1];
    cal_result = !cal_save ? AUDIO_CAL_MEASURED : settings_save() ? AUDIO_CAL_SAVED : AUDIO_CAL_NOT_SAVED;
  }
}

void audio_task(void) {
  uint32_t const now = board_millis();

  // A bus reset or an unplug closes the streams without the interface callbacks.
  if (!tud_mounted() && (out.streaming || in.streaming)) {
    out.streaming = in.streaming = false;
    streams_flush();
  }

  if (codec_state() != CODEC_RUNNING || !i2s_running()) {
    if ((int32_t) (now - codec_retry_at) >= 0) streams_start(rate_host);
    return;
  }
  if (rate_host != rate_codec) {
    streams_start(rate_host);
    return;
  }
  if (!i2s_check()) {
    last_error = "I2S overrun / underrun / slip / stall, restarted";
    streams_start(rate_codec);
    return;
  }
  cal_task(now);
}

void audio_set_tone(bool on) {
  tone_on = on;
}

bool audio_tone(void) {
  return tone_on;
}

static void stream_status(stream_t *st, audio_stream_t *o, uint32_t target) {
  o->streaming = st->streaming;
  o->primed = st->primed;
  o->level = st->primed ? st->lvl : 0;
  o->level_min = st->lvl_min == UINT16_MAX ? o->level : st->lvl_min;
  o->level_max = st->lvl_min == UINT16_MAX ? o->level : st->lvl_max;
  o->target = (uint16_t) target;
  o->rate = st->primed ? st->rate : nominal_rate(rate_host);
  o->underruns = st->underruns;
  o->overruns = st->overruns;
  st->lvl_min = UINT16_MAX;
  st->lvl_max = 0;
}

void audio_get_status(audio_status_t *st) {
  uint32_t const irq = board_irq_mask();
  uint32_t const rate = rate_codec ? rate_codec : rate_host;
  st->rate_host = rate_host;
  st->rate_codec = rate_codec;
  stream_status(&out, &st->out, ms_frames(rate, out_target_ms));
  stream_status(&in, &st->in, ms_frames(rate, AUDIO_TARGET_MS) + AUDIO_BLOCK_FRAMES);
  st->out_target_ms = (uint8_t) out_target_ms;
  st->cal = cal_result;
  st->dc_offset[0] = dc_offset[0];
  st->dc_offset[1] = dc_offset[1];
  st->restarts = restarts;
  st->last_error = last_error;
  board_irq_restore(irq);
}

void audio_take_meter(audio_meter_t *m) {
  uint32_t const irq = board_irq_mask();
  uint32_t const n = m_frames;
  for (int c = 0; c < 2; c++) {
    m->in_peak[c] = m_in_peak[c];
    m->out_peak[c] = m_out_peak[c];
    m->in_mean[c] = n ? (int32_t) (m_in_sum[c] / (int32_t) n) : 0;
    m->out_mean[c] = n ? (int32_t) (m_out_sum[c] / (int32_t) n) : 0;
    m_in_peak[c] = m_out_peak[c] = 0;
    m_in_sum[c] = m_out_sum[c] = 0;
  }
  m->frames = n;
  m_frames = 0;
  board_irq_restore(irq);
}

//--------------------------------------------------------------------+
// Iso transaction statistics
//--------------------------------------------------------------------+

// Every transfer completion the DCD reports passes here
// (-Wl,--wrap=dcd_event_handler). Iso endpoints complete once per interval,
// so a larger step of the microframe counter is a missed packet.
void __real_dcd_event_handler(dcd_event_t const *event, bool in_isr);

static audio_iso_stats_t iso_stats;
static uint32_t iso_missed_total[3];
static uint16_t iso_last[3];
static bool iso_seen[3];

void __wrap_dcd_event_handler(dcd_event_t const *event, bool in_isr) {
  if (event->event_id == DCD_EVENT_XFER_COMPLETE) {
    uint8_t const ep = event->xfer_complete.ep_addr;
    int const i = ep == EPNUM_AUDIO_OUT ? 0 : ep == EPNUM_AUDIO_IN ? 1 : ep == EPNUM_AUDIO_FB ? 2 : -1;
    if (i >= 0) {
      uint16_t const fn = dcd_ch32_event_frame();
      // Frame number in bits 10:0, microframe in bits 15:13 (read on the board).
      uint16_t const uf = (uint16_t) (((fn & 0x7FFu) << 3) | (fn >> 13));   // 14-bit microframe count
      uint16_t const interval = i == 2 ? 8 : 1;
      if (iso_seen[i]) {
        uint16_t const step = (uint16_t) ((uf - iso_last[i]) & 0x3FFFu);
        if (step > interval && step < 64) {
          iso_stats.missed[i] += step / interval - 1u;
          iso_missed_total[i] += step / interval - 1u;
        }
      }
      iso_seen[i] = true;
      iso_last[i] = uf;
      iso_stats.packets[i]++;
    }
  }
  __real_dcd_event_handler(event, in_isr);
}

void audio_take_iso_stats(audio_iso_stats_t *s) {
  uint32_t const irq = board_irq_mask();
  *s = iso_stats;
  memcpy(s->missed_total, iso_missed_total, sizeof(s->missed_total));
  memset(&iso_stats, 0, sizeof(iso_stats));
  memset(iso_seen, 0, sizeof(iso_seen));
  board_irq_restore(irq);
}

//--------------------------------------------------------------------+
// TinyUSB audio class callbacks
//--------------------------------------------------------------------+

static bool rate_supported(uint32_t rate) {
  for (size_t i = 0; i < TU_ARRAY_SIZE(rates); i++) {
    if (rates[i] == rate) return true;
  }
  return false;
}

bool tud_audio_set_itf_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
  (void) rhport;
  uint8_t const itf = tu_u16_low(p_request->wIndex);
  uint8_t const alt = tu_u16_low(p_request->wValue);

  uint32_t const irq = board_irq_mask();
  if (itf == ITF_NUM_AUDIO_STREAMING_OUT) {
    out.primed = false;
    out_udr_pending = false;
    out.rate = nominal_rate(rate_host);
    tud_audio_fb_set(out.rate);
    out.lvl_min = UINT16_MAX;
    out.lvl_max = 0;
    iso_seen[0] = iso_seen[2] = false;
    out.streaming = (alt != 0);
  } else if (itf == ITF_NUM_AUDIO_STREAMING_IN) {
    in.primed = false;
    in_ovr_pending = false;
    in.lvl_min = UINT16_MAX;
    in.lvl_max = 0;
    iso_seen[1] = false;
    in.streaming = (alt != 0);
    if (alt != 0) {
      // TinyUSB has queued an empty first packet; load the one after it.
      tud_audio_clear_ep_in_ff();
      in_acc = 0;
      in_stage();
    }
  }
  board_irq_restore(irq);
  return true;
}

bool tud_audio_set_itf_close_ep_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
  (void) rhport;
  uint8_t const itf = tu_u16_low(p_request->wIndex);
  if (itf == ITF_NUM_AUDIO_STREAMING_OUT) {
    out.streaming = false;
    out.primed = false;
    out_udr_pending = false;
    // The first feedback packet of the next stream is loaded before
    // tud_audio_set_itf_cb(): leave the nominal value for it.
    tud_audio_fb_set(nominal_rate(rate_host));
  } else if (itf == ITF_NUM_AUDIO_STREAMING_IN) {
    in.streaming = false;
    in.primed = false;
  }
  return true;
}

void tud_audio_feedback_params_cb(uint8_t func_id, uint8_t alt_itf, audio_feedback_params_t *feedback_param) {
  (void) func_id;
  (void) alt_itf;
  // Feedback is computed in audio_i2s_tx() from the FIFO level and the current
  // rate (the host may set the rate after the interface).
  feedback_param->method = AUDIO_FEEDBACK_METHOD_DISABLED;
  feedback_param->sample_freq = rate_host;
}

bool tud_audio_get_req_entity_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
  uint8_t const entity = TU_U16_HIGH(p_request->wIndex);
  uint8_t const ctrl = TU_U16_HIGH(p_request->wValue);

  if (entity != UAC2_ENTITY_CLOCK) return false;

  if (ctrl == AUDIO20_CS_CTRL_SAM_FREQ) {
    if (p_request->bRequest == AUDIO20_CS_REQ_CUR) {
      audio20_control_cur_4_t cur = {.bCur = (int32_t) tu_htole32(rate_host)};
      return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, &cur, sizeof(cur));
    }
    if (p_request->bRequest == AUDIO20_CS_REQ_RANGE) {
      audio20_control_range_4_n_t(TU_ARRAY_SIZE(rates)) range = {.wNumSubRanges = tu_htole16(TU_ARRAY_SIZE(rates))};
      for (size_t i = 0; i < TU_ARRAY_SIZE(rates); i++) {
        range.subrange[i].bMin = (int32_t) rates[i];
        range.subrange[i].bMax = (int32_t) rates[i];
        range.subrange[i].bRes = 0;
      }
      return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, &range, sizeof(range));
    }
  } else if (ctrl == AUDIO20_CS_CTRL_CLK_VALID && p_request->bRequest == AUDIO20_CS_REQ_CUR) {
    audio20_control_cur_1_t valid = {.bCur = 1};
    return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, &valid, sizeof(valid));
  }
  return false;
}

bool tud_audio_set_req_entity_cb(uint8_t rhport, tusb_control_request_t const *p_request, uint8_t *buf) {
  (void) rhport;
  uint8_t const entity = TU_U16_HIGH(p_request->wIndex);
  uint8_t const ctrl = TU_U16_HIGH(p_request->wValue);

  if (entity != UAC2_ENTITY_CLOCK || ctrl != AUDIO20_CS_CTRL_SAM_FREQ ||
      p_request->bRequest != AUDIO20_CS_REQ_CUR || p_request->wLength != sizeof(audio20_control_cur_4_t)) {
    return false;
  }
  uint32_t const rate = (uint32_t) ((audio20_control_cur_4_t const *) buf)->bCur;
  TU_VERIFY(rate_supported(rate));
  rate_host = rate;   // applied to the codec by audio_task()
  tud_audio_fb_set(nominal_rate(rate));
  return true;
}

bool tud_audio_tx_done_isr(uint8_t rhport, uint16_t n_bytes_sent, uint8_t func_id, uint8_t ep_in,
                           uint8_t cur_alt_setting) {
  (void) rhport;
  (void) n_bytes_sent;
  (void) func_id;
  (void) ep_in;
  (void) cur_alt_setting;
  in_taken++;
  in_stage();
  return true;
}

bool tud_audio_rx_done_isr(uint8_t rhport, uint16_t n_bytes_received, uint8_t func_id, uint8_t ep_out,
                           uint8_t cur_alt_setting) {
  (void) rhport;
  (void) n_bytes_received;
  (void) func_id;
  (void) ep_out;
  (void) cur_alt_setting;
  // Nothing consumes the FIFO while I2S is down: keep it from holding stale audio.
  if (!i2s_running()) tud_audio_clear_ep_out_ff();
  return true;
}
