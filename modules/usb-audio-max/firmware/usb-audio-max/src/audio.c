#include "audio.h"

#include <string.h>

#include "board.h"
#include "codec.h"
#include "dcd_capture.h"
#include "device/dcd.h"
#include "tusb.h"
#include "usb_descriptors.h"

// The ADC sends zeros until tADCDLY1 + its fade-in after the clocks start
// (SBAS452A 8.7, up to ~250 ms at 48 kHz): measure the frame position after that.
#define SETTLE_MS      400
#define ALIGN_FRAMES   4800    // 100 ms
#define ALIGN_RETRIES  5

#define OUT_BLOCK_BYTES (TDM_BLOCK_FRAMES * AUDIO_OUT_FRAME_BYTES)

static audio_state_t state = AUDIO_STOPPED;
static uint32_t retry_at, settle_at, restarts;
static int align_tries;
static const char *last_error = "";
// Audio passes between USB and the codec (frame position known).
static volatile bool live;

// Both streams hold their buffer at a target level with a slow proportional
// loop on the low-passed level (frames << 16), as modules/usb-audio:
// LOOP_GAIN_SHIFT 14 is 0.5 frames/s per frame of error (2 s time constant),
// clamped to +-1/128 of the nominal rate. Slow on purpose: the host sees a
// nearly constant feedback value and nearly constant IN packet sizes.
#define LOOP_GAIN_SHIFT  14
#define LOOP_CLAMP_SHIFT 7
#define LVL_LP_SHIFT     6     // level low-pass: 64 ms (one step per 1 ms TDM block)
#define NOMINAL_RATE     ((uint32_t) (AUDIO_RATE / 8000) << 16)   // samples per microframe, 16.16
#define MS_FRAMES(ms)    ((uint32_t) (AUDIO_RATE / 1000 * (ms)))

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
static int32_t out_last[AUDIO_OUT_CHANNELS];   // last samples played, for the fade to silence

// IN (ADC -> USB): buffer = in_ring, level taken after each block write,
// rate = frames per IN packet. in_stage() loads one packet at a time into
// TinyUSB's IN FIFO: silence at the nominal rate until the ring is primed.
#define IN_RING_MASK (AUDIO_IN_RING_FRAMES - 1u)
static stream_t in;
static uint32_t in_ring[AUDIO_IN_RING_FRAMES * AUDIO_IN_CHANNELS];
static uint32_t in_wr, in_rd;          // frames, free running
static uint32_t in_acc;                // packet size accumulator, 16.16 frames
static uint32_t in_taken;              // packets the host took since the last TDM block
static bool in_ovr_pending;            // counted when the host polls again (not at the stream's end)

// Calibration in use (worker side reads it; set under board_irq_mask)
static audio_coef_t coef;

// Output sources
static volatile uint8_t gen_mode[AUDIO_OUT_CHANNELS];
static volatile int32_t gen_val[AUDIO_OUT_CHANNELS];
static uint32_t tone_phase;
static int32_t sine_tab[960];          // one period at 960 kHz, peak 2^22 (half scale)

// Meters (worker side)
static int64_t m_in_sum[AUDIO_IN_CHANNELS];
static int32_t m_in_min[AUDIO_IN_CHANNELS], m_in_max[AUDIO_IN_CHANNELS];
static uint32_t m_in_frames;

static inline int32_t clamp24(int32_t v) {
  return v > 0x7FFFFF ? 0x7FFFFF : v < -0x800000 ? -0x800000 : v;
}

static inline __attribute__((always_inline)) int32_t clamp24_64(int64_t v) {
  return v > 0x7FFFFF ? 0x7FFFFF : v < -0x800000 ? -0x800000 : (int32_t) v;
}

static inline __attribute__((always_inline)) int32_t in_cal(int ch, int32_t code) {
  return clamp24_64((((int64_t) (code - coef.in_zero[ch]) * coef.in_gain[ch]) + (1 << 29)) >> 30);
}

static inline __attribute__((always_inline)) int32_t out_cal(int ch, int32_t sample) {
  return clamp24_64(((((int64_t) sample * coef.out_gain[ch]) + (1 << 29)) >> 30) + coef.out_zero[ch]);
}

static void meter_clear(void) {
  for (int c = 0; c < AUDIO_IN_CHANNELS; c++) {
    m_in_sum[c] = 0;
    m_in_min[c] = INT32_MAX;
    m_in_max[c] = INT32_MIN;
  }
  m_in_frames = 0;
}

const char *audio_state_name(audio_state_t s) {
  switch (s) {
    case AUDIO_STOPPED: return "stopped";
    case AUDIO_SETTLING: return "clocks running, waiting for ADC data";
    case AUDIO_ALIGNING: return "finding the TDM frame position";
    case AUDIO_RUNNING: return "running";
  }
  return "?";
}

int32_t audio_mv_to_sample(int32_t mv) {
  return clamp24_64(((int64_t) mv * AUDIO_FS_CODE) / AUDIO_FS_MV);
}

int32_t audio_sample_to_mv(int32_t sample) {
  return (int32_t) (((int64_t) sample * AUDIO_FS_MV) / AUDIO_FS_CODE);
}

int32_t audio_in_sample(int ch, int32_t code) {
  return in_cal(ch, code);
}

int32_t audio_out_code(int ch, int32_t sample) {
  return out_cal(ch, sample);
}

//--------------------------------------------------------------------+
// Stream level loops
//--------------------------------------------------------------------+

// One step of a stream's loop: `level` frames in the buffer against `target`.
// `sign` +1: a fuller buffer raises the rate (IN packets), -1: lowers it (OUT feedback).
static void stream_loop(stream_t *st, uint32_t level, uint32_t target, int sign) {
  st->lvl = (uint16_t) level;
  if (level < st->lvl_min) st->lvl_min = (uint16_t) level;
  if (level > st->lvl_max) st->lvl_max = (uint16_t) level;
  st->lvl_lp += ((int32_t) (level << 16) - st->lvl_lp) >> LVL_LP_SHIFT;
  int32_t const clamp = (int32_t) NOMINAL_RATE >> LOOP_CLAMP_SHIFT;
  int32_t d = (st->lvl_lp - (int32_t) (target << 16)) >> LOOP_GAIN_SHIFT;
  if (d > clamp) d = clamp;
  if (d < -clamp) d = -clamp;
  st->rate = (uint32_t) ((int32_t) NOMINAL_RATE + sign * d);
}

static void stream_prime(stream_t *st, uint32_t target) {
  st->lvl_lp = (int32_t) (target << 16);
  st->rate = NOMINAL_RATE;
  st->primed = true;
}

//--------------------------------------------------------------------+
// Audio worker side (TDM blocks, USB transfers)
//--------------------------------------------------------------------+

void audio_usb_service(void) {
  tdm_service_mark();
  tud_int_handler(0);
  tdm_service_mark();
}

// Loads the next IN packet into TinyUSB's IN FIFO, which holds nothing else:
// called once when the stream opens and then each time TinyUSB has moved the
// loaded packet to the endpoint. The packet size comes from the accumulated
// rate, so the sizes are the nominal one with a single +-1 now and then.
static void in_stage(void) {
  bool const ok = in.primed && live;
  in_acc += ok ? in.rate : NOMINAL_RATE;
  uint32_t const n = in_acc >> 16;
  in_acc &= 0xFFFFu;

  if (ok && in_wr - in_rd >= n) {
    uint32_t const at = in_rd & IN_RING_MASK;
    uint32_t const first = TU_MIN(n, AUDIO_IN_RING_FRAMES - at);
    tud_audio_write(&in_ring[at * AUDIO_IN_CHANNELS], (uint16_t) (first * AUDIO_IN_FRAME_BYTES));
    if (n > first) tud_audio_write(in_ring, (uint16_t) ((n - first) * AUDIO_IN_FRAME_BYTES));
    in_rd += n;
  } else {
    static uint32_t const silence[AUDIO_EP_IN_SIZE / AUDIO_SUBSLOT_BYTES];
    if (ok) in.underruns++;
    in.primed = false;   // refill to the target (audio_tdm_rx)
    tud_audio_write(silence, (uint16_t) (n * AUDIO_IN_FRAME_BYTES));
  }
}

// ADC -> USB: calibrated samples MSB-justified in 32 bits (UAC2 24-in-32), IN 1 first.
void audio_tdm_rx(int32_t const blk[][TDM_IN_CHANNELS]) {
  for (int f = 0; f < TDM_BLOCK_FRAMES; f++) {
    uint32_t *const dst = &in_ring[((in_wr + (uint32_t) f) & IN_RING_MASK) * AUDIO_IN_CHANNELS];
    for (int c = 0; c < AUDIO_IN_CHANNELS; c++) {
      int32_t const raw = blk[f][c];
      m_in_sum[c] += raw;
      if (raw < m_in_min[c]) m_in_min[c] = raw;
      if (raw > m_in_max[c]) m_in_max[c] = raw;
      dst[c] = (uint32_t) in_cal(c, raw) << 8;
    }
    // may send from the ring: in_wr moves after the block
    if (f % TDM_SERVICE_FRAMES == TDM_SERVICE_FRAMES - 1) audio_usb_service();
  }
  m_in_frames += TDM_BLOCK_FRAMES;
  in_wr += TDM_BLOCK_FRAMES;

  // The packets of one block period leave before the next block arrives, so
  // the level after a write is held one block above the target.
  uint32_t const target = MS_FRAMES(AUDIO_TARGET_MS) + TDM_BLOCK_FRAMES;
  uint32_t level = in_wr - in_rd;
  if (!in.primed) {
    if (level > target) {   // idle: keep the newest audio only
      in_rd = in_wr - target;
      level = target;
    }
    // The host starts to poll some time after it has opened the stream.
    if (in.streaming && in_taken && live && level == target) {
      stream_prime(&in, target);
      if (in_ovr_pending) in.overruns++;
      in_ovr_pending = false;
    }
  } else if (level > target + MS_FRAMES(2)) {
    // The host stopped polling: silence until it takes packets again, then
    // start over from the newest audio.
    in.primed = false;
    in_ovr_pending = true;
  }
  if (in.primed) stream_loop(&in, level, target, +1);
  in_taken = 0;
}

// USB -> DAC (through the output calibration and the test sources), and the
// explicit feedback that holds the OUT FIFO at the target level.
// The USB block is read into `blk` and replaced by the DAC codes frame by frame.
void audio_tdm_tx(int32_t blk[][TDM_OUT_CHANNELS]) {
  bool have = false;
  tu_fifo_t *const ff = tud_audio_get_ep_out_ff();

  if (out.streaming && ff) {
    uint32_t const target = MS_FRAMES(out_target_ms);
    uint32_t avail = tu_fifo_count(ff) / AUDIO_OUT_FRAME_BYTES;

    if (!out.primed && avail >= target + TDM_BLOCK_FRAMES) {
      // Start on the target: drop what came in beyond it while filling.
      tu_fifo_discard_n(ff, (uint16_t) ((avail - target - TDM_BLOCK_FRAMES) * AUDIO_OUT_FRAME_BYTES));
      avail = target + TDM_BLOCK_FRAMES;
      stream_prime(&out, target);
      out_fade_in = true;
      if (out_udr_pending) {   // the stream went on after an underrun
        out_udr_pending = false;
        out.underruns++;
        if (out_target_ms < AUDIO_TARGET_MS_MAX) out_target_ms++;
      }
    }
    if (out.primed) {
      if (avail >= TDM_BLOCK_FRAMES) {
        tu_fifo_read_n(ff, blk, OUT_BLOCK_BYTES);
        have = true;
        avail -= TDM_BLOCK_FRAMES;
        if (avail > target + MS_FRAMES(3)) {
          // The host sent more than the feedback asked for: drop the oldest audio.
          tu_fifo_discard_n(ff, (uint16_t) ((avail - target) * AUDIO_OUT_FRAME_BYTES));
          avail = target;
          out.lvl_lp = (int32_t) (target << 16);
          out.overruns++;
        }
        stream_loop(&out, avail, target, -1);
      } else {
        out.primed = false;   // refill to the target before playing again
        out_udr_pending = true;
      }
    }
    if (!out.primed) out.rate = NOMINAL_RATE;
    tud_audio_fb_set(out.rate);
  }

  // USB samples: fade in over the first block of a stream (or after an
  // underrun), fade to silence over one block when the audio ends.
  int32_t fade_from[AUDIO_OUT_CHANNELS];
  bool fade_out = false;
  if (have) {
    for (int c = 0; c < AUDIO_OUT_CHANNELS; c++) {
      out_last[c] = blk[TDM_BLOCK_FRAMES - 1][c] >> 8;
    }
  } else {
    for (int c = 0; c < AUDIO_OUT_CHANNELS; c++) {
      fade_from[c] = out_last[c];
      if (out_last[c]) fade_out = true;
      out_last[c] = 0;
    }
  }
  bool const fade_in = have && out_fade_in;
  if (have) out_fade_in = false;

  for (int f = 0; f < TDM_BLOCK_FRAMES; f++) {
    int32_t const sine = sine_tab[tone_phase];
    tone_phase += 960000u / AUDIO_RATE;
    if (tone_phase >= 960) tone_phase -= 960;
    for (int c = 0; c < AUDIO_OUT_CHANNELS; c++) {
      int32_t s, code;
      switch (gen_mode[c]) {
        case GEN_DC: s = gen_val[c]; break;
        case GEN_SINE: s = sine; break;
        case GEN_RAW: s = 0; break;
        default:
          if (have) {
            s = blk[f][c] >> 8;
            if (fade_in) s = s * (f + 1) / TDM_BLOCK_FRAMES;   // |s| * 48 < 2^31
          } else if (fade_out) {
            s = fade_from[c] * (TDM_BLOCK_FRAMES - 1 - f) / TDM_BLOCK_FRAMES;
          } else {
            s = 0;
          }
          break;
      }
      code = gen_mode[c] == GEN_RAW ? gen_val[c] : out_cal(c, s);
      blk[f][c] = code;
    }
    if (f % TDM_SERVICE_FRAMES == TDM_SERVICE_FRAMES - 1) audio_usb_service();
  }
}

//--------------------------------------------------------------------+
// Main-loop side
//--------------------------------------------------------------------+

void audio_init(void) {
  double x = 1.0, y = 0.0;   // rotation by 2 pi / 960 per entry (no libm)
  for (int i = 0; i < 960; i++) {
    sine_tab[i] = (int32_t) (y * (double) (1 << 22));
    double const nx = x * 0.9999785816641292 - y * 0.006544937967351858;
    y = x * 0.006544937967351858 + y * 0.9999785816641292;
    x = nx;
  }
  for (int c = 0; c < AUDIO_IN_CHANNELS; c++) coef.in_gain[c] = AUDIO_Q30;
  for (int c = 0; c < AUDIO_OUT_CHANNELS; c++) coef.out_gain[c] = AUDIO_Q30;
  out.lvl_min = in.lvl_min = UINT16_MAX;
  meter_clear();
  retry_at = board_millis();
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

static void go_stopped(void) {
  live = false;
  streams_flush();
  state = AUDIO_STOPPED;
}

// Codec reset + configuration with BCK held low, both slaves armed, then the
// ADC becomes the clock master (tdm.h: the start that aligns both slaves).
static void streams_start(void) {
  tdm_stop();
  go_stopped();
  codec_state_t const s = codec_prepare(AUDIO_RATE);
  if (s != CODEC_READY) {
    last_error = codec_state_name(s);
    retry_at = board_millis() + 2000;
    return;
  }
  if (codec_linked()) {
    // Clock slave: BCK / LRCK from the link run already, so the two TDM slaves
    // cannot be armed on a still BCK (tdm.h). Not started by this firmware: the
    // codec goes back into reset and the address is probed again every 2 s.
    codec_stop();
    last_error = "clock slave (CLK IN connected): not supported by this firmware yet";
    retry_at = board_millis() + 2000;
    return;
  }
  tdm_start();
  if (!codec_run() || !tdm_lrck_toggling(50000)) {
    tdm_stop();
    codec_stop();
    last_error = "no LRCK from the codec";
    retry_at = board_millis() + 1000;
    return;
  }
  restarts++;
  align_tries = 0;
  state = AUDIO_SETTLING;
  settle_at = board_millis() + SETTLE_MS;
}

void audio_restart(uint32_t hold_ms) {
  tdm_stop();
  codec_stop();
  go_stopped();
  retry_at = board_millis() + hold_ms;
}

void *audio_scratch(uint32_t *len) {
  if (len) {
    *len = sizeof(in_ring);
    return NULL;
  }
  audio_restart(60000);
  return in_ring;
}

void audio_task(void) {
  uint32_t const now = board_millis();

  // A bus reset or an unplug closes the streams without the interface callbacks.
  if (!tud_mounted() && (out.streaming || in.streaming)) {
    out.streaming = in.streaming = false;
    streams_flush();
  }

  if (state == AUDIO_STOPPED) {
    if ((int32_t) (now - retry_at) >= 0) streams_start();
    return;
  }
  if (!tdm_check()) {
    last_error = "TDM overrun / underrun / slip / stall, restarted";
    codec_stop();
    go_stopped();
    retry_at = now + 200;
    return;
  }
  // The codec address follows the clock link (ADR1 = LINK_N): once a second,
  // see that it still answers where it was found. A ribbon plugged into CLK IN
  // moves it, and the restart then finds the unit a clock slave.
  static uint32_t alive_at;
  if ((int32_t) (now - alive_at) >= 0) {
    alive_at = now + 1000;
    if (!codec_alive()) {
      last_error = "codec address changed (clock link plugged / unplugged?), restarted";
      tdm_stop();
      codec_stop();
      go_stopped();
      retry_at = now + 200;
      return;
    }
  }
  tdm_align_task();
  tdm_align_info_t info;
  tdm_align_get(&info);

  switch (state) {
    case AUDIO_SETTLING:
      if ((int32_t) (now - settle_at) >= 0) {
        tdm_align_start(ALIGN_FRAMES);
        state = AUDIO_ALIGNING;
      }
      break;
    case AUDIO_ALIGNING:
      if (info.state == TDM_ALIGN_OK) {
        uint32_t const irq = board_irq_mask();
        meter_clear();
        streams_flush();
        live = true;
        board_irq_restore(irq);
        state = AUDIO_RUNNING;
      } else if (info.state == TDM_ALIGN_FAILED) {
        if (++align_tries >= ALIGN_RETRIES) {
          last_error = "no TDM frame position found, restarted";
          audio_restart(500);
        } else {
          tdm_align_start(ALIGN_FRAMES);
        }
      }
      break;
    default:
      break;
  }
}

static void stream_status(stream_t *st, audio_stream_t *o, uint32_t target) {
  o->streaming = st->streaming;
  o->primed = st->primed;
  o->level = st->primed ? st->lvl : 0;
  o->level_min = st->lvl_min == UINT16_MAX ? o->level : st->lvl_min;
  o->level_max = st->lvl_min == UINT16_MAX ? o->level : st->lvl_max;
  o->target = (uint16_t) target;
  o->rate = st->primed ? st->rate : NOMINAL_RATE;
  o->underruns = st->underruns;
  o->overruns = st->overruns;
  st->lvl_min = UINT16_MAX;
  st->lvl_max = 0;
}

void audio_get_status(audio_status_t *st) {
  uint32_t const irq = board_irq_mask();
  st->state = state;
  st->restarts = restarts;
  st->last_error = last_error;
  stream_status(&out, &st->out, MS_FRAMES(out_target_ms));
  stream_status(&in, &st->in, MS_FRAMES(AUDIO_TARGET_MS) + TDM_BLOCK_FRAMES);
  st->out_target_ms = (uint8_t) out_target_ms;
  board_irq_restore(irq);
}

audio_state_t audio_get_state(void) {
  return state;
}

void audio_set_coef(audio_coef_t const *c) {
  uint32_t const irq = board_irq_mask();
  coef = *c;
  board_irq_restore(irq);
}

void audio_get_coef(audio_coef_t *c) {
  uint32_t const irq = board_irq_mask();
  *c = coef;
  board_irq_restore(irq);
}

void audio_gen_set(int ch, gen_mode_t mode, int32_t value) {
  if (ch < 0 || ch >= AUDIO_OUT_CHANNELS) return;
  uint32_t const irq = board_irq_mask();
  gen_val[ch] = value;
  gen_mode[ch] = (uint8_t) mode;
  board_irq_restore(irq);
}

gen_mode_t audio_gen_mode(int ch) {
  return (gen_mode_t) gen_mode[ch];
}

int32_t audio_gen_value(int ch) {
  return gen_val[ch];
}

void audio_take_meter(audio_meter_t *m) {
  uint32_t const irq = board_irq_mask();
  uint32_t const ni = m_in_frames;
  for (int c = 0; c < AUDIO_IN_CHANNELS; c++) {
    m->in_mean[c] = ni ? (int32_t) (m_in_sum[c] / (int32_t) ni) : 0;
    m->in_min[c] = ni ? m_in_min[c] : 0;
    m->in_max[c] = ni ? m_in_max[c] : 0;
  }
  m->frames = ni;
  meter_clear();
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
static dcd_trace_t miss_trace[AUDIO_MISS_TRACE];
static int miss_ep;
static uint16_t miss_step;
static volatile bool miss_held;

void __wrap_dcd_event_handler(dcd_event_t const *event, bool in_isr) {
  if (event->event_id == DCD_EVENT_XFER_COMPLETE) {
    uint8_t const ep = event->xfer_complete.ep_addr;
    int const i = ep == EPNUM_AUDIO_OUT ? 0 : ep == EPNUM_AUDIO_IN ? 1 : ep == EPNUM_AUDIO_FB ? 2 : -1;
    if (i >= 0) {
      uint16_t const fn = dcd_ch32_event_frame();
      // Frame number in bits 10:0, microframe in bits 15:13 (modules/usb-audio).
      uint16_t const uf = (uint16_t) (((fn & 0x7FFu) << 3) | (fn >> 13));   // 14-bit microframe count
      uint16_t const interval = i == 2 ? 8 : 1;
      if (iso_seen[i]) {
        uint16_t const step = (uint16_t) ((uf - iso_last[i]) & 0x3FFFu);
        if (step > interval && step < 64) {
          iso_stats.missed[i] += step / interval - 1u;
          iso_missed_total[i] += step / interval - 1u;
          if (!miss_held) {
            dcd_ch32_trace(miss_trace, AUDIO_MISS_TRACE);
            miss_ep = i;
            miss_step = step;
            miss_held = true;
          }
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

bool audio_take_miss_trace(dcd_trace_t *t, int *ep, uint16_t *step) {
  if (!miss_held) return false;
  memcpy(t, miss_trace, sizeof(miss_trace));
  *ep = miss_ep;
  *step = miss_step;
  miss_held = false;
  return true;
}

//--------------------------------------------------------------------+
// TinyUSB audio class callbacks
//--------------------------------------------------------------------+

bool tud_audio_set_itf_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
  (void) rhport;
  uint8_t const itf = tu_u16_low(p_request->wIndex);
  uint8_t const alt = tu_u16_low(p_request->wValue);

  uint32_t const irq = board_irq_mask();
  if (itf == ITF_NUM_AUDIO_STREAMING_OUT) {
    out.primed = false;
    out_udr_pending = false;
    out.rate = NOMINAL_RATE;
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
    tud_audio_fb_set(NOMINAL_RATE);
  } else if (itf == ITF_NUM_AUDIO_STREAMING_IN) {
    in.streaming = false;
    in.primed = false;
  }
  return true;
}

void tud_audio_feedback_params_cb(uint8_t func_id, uint8_t alt_itf, audio_feedback_params_t *feedback_param) {
  (void) func_id;
  (void) alt_itf;
  // Feedback is computed in audio_tdm_tx() from the FIFO level.
  feedback_param->method = AUDIO_FEEDBACK_METHOD_DISABLED;
  feedback_param->sample_freq = AUDIO_RATE;
}

bool tud_audio_get_req_entity_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
  uint8_t const entity = TU_U16_HIGH(p_request->wIndex);
  uint8_t const ctrl = TU_U16_HIGH(p_request->wValue);

  if (entity != UAC2_ENTITY_CLOCK) return false;

  if (ctrl == AUDIO20_CS_CTRL_SAM_FREQ) {
    if (p_request->bRequest == AUDIO20_CS_REQ_CUR) {
      audio20_control_cur_4_t cur = {.bCur = (int32_t) tu_htole32(AUDIO_RATE)};
      return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, &cur, sizeof(cur));
    }
    if (p_request->bRequest == AUDIO20_CS_REQ_RANGE) {
      audio20_control_range_4_n_t(1) range = {.wNumSubRanges = tu_htole16(1)};
      range.subrange[0].bMin = AUDIO_RATE;
      range.subrange[0].bMax = AUDIO_RATE;
      range.subrange[0].bRes = 0;
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
  // One rate: accept it again, refuse any other.
  return (uint32_t) ((audio20_control_cur_4_t const *) buf)->bCur == AUDIO_RATE;
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
  // Nothing consumes the FIFO while TDM is down: keep it from holding stale audio.
  if (!live) tud_audio_clear_ep_out_ff();
  return true;
}
