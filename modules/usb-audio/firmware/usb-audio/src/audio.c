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
static volatile bool out_streaming, in_streaming, out_primed;
static volatile uint32_t out_underruns, in_overruns;
static volatile uint32_t feedback_value;
static int32_t fifo_avg;               // OUT FIFO level, frames x 256 (low-passed)
static uint32_t codec_retry_at, restarts;
static const char *last_error = "";

// Input DC offset, 24-bit codes per input (IN 1, IN 2), subtracted from every
// sample. Measured by audio_calibrate(): wait CAL_SETTLE_MS after the request
// (or a restart), then average CAL_MS with the inputs unpatched (0 V).
#define CAL_SETTLE_MS 300
#define CAL_MS        500
static int32_t dc_offset[2];
static enum { CAL_IDLE, CAL_SETTLE, CAL_SUM } cal_state;
static bool cal_valid;
static uint32_t cal_at;
static volatile uint32_t cal_left;     // frames still to sum (interrupt side)
static int64_t cal_sum[2];
static uint32_t cal_n;

// Test tone (console `tone`): 1 kHz sine at half scale on both outputs instead of the USB data.
static volatile bool tone_on;
static uint32_t tone_phase;
static int32_t sine_tab[960];          // one period at 960 kHz, peak 2^22

// Meters (interrupt side)
static int32_t m_in_peak[2], m_out_peak[2];
static int64_t m_in_sum[2], m_out_sum[2];
static uint32_t m_frames;

static inline uint32_t target_frames(uint32_t rate) {
  return rate / 1000 * AUDIO_TARGET_MS;
}

static inline uint32_t nominal_feedback(uint32_t rate) {
  return (rate / 8000) << 16;   // samples per 125 us microframe, 16.16
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

//--------------------------------------------------------------------+
// I2S interrupt side
//--------------------------------------------------------------------+

// ADC -> USB: samples MSB-justified in 32 bits (UAC2 24-in-32), IN 1 first.
void audio_i2s_rx(const uint16_t *src) {
  uint32_t buf[AUDIO_BLOCK_FRAMES * 2];
  uint32_t zero = 0;
  for (int i = 0; i < AUDIO_BLOCK_FRAMES; i++) {
    uint32_t const w[2] = {rx_word(src, 2 * i + I2S_SLOT_A), rx_word(src, 2 * i + I2S_SLOT_B)};
    zero |= w[0] | w[1];
    for (int ch = 0; ch < 2; ch++) {
      int32_t const raw = (int32_t) i2s_rx_to_sample(w[ch]) >> 8;
      if (cal_left) cal_sum[ch] += raw;
      int32_t const s = clamp24(raw - dc_offset[ch]);
      buf[2 * i + ch] = (uint32_t) s << 8;
      int32_t const a = iabs(s);
      if (a > m_in_peak[ch]) m_in_peak[ch] = a;
      m_in_sum[ch] += s;
    }
    if (cal_left) {
      cal_n++;
      cal_left--;
    }
  }
  m_frames += AUDIO_BLOCK_FRAMES;
  if (zero & I2S_RX_ZERO_BITS) i2s_report_slip();

  if (in_streaming) {
    if (tud_audio_write(buf, BLOCK_BYTES) < BLOCK_BYTES) in_overruns++;
  }
}

// USB -> DAC, and the explicit feedback that holds the OUT FIFO at the target level.
void audio_i2s_tx(uint16_t *dst) {
  uint32_t buf[AUDIO_BLOCK_FRAMES * 2];
  bool have = false;

  if (out_streaming) {
    uint32_t const rate = rate_codec ? rate_codec : rate_host;
    uint32_t const target = target_frames(rate);
    uint16_t const avail = tud_audio_available();

    if (!out_primed && avail >= target * AUDIO_FRAME_BYTES) out_primed = true;
    if (out_primed) {
      if (avail >= BLOCK_BYTES) {
        tud_audio_read(buf, BLOCK_BYTES);
        have = true;
      } else {
        out_underruns++;
        out_primed = false;   // refill to the target before playing again
      }
    }

    // Proportional control on the low-passed FIFO level: 1 sample/microframe
    // per 256 frames of error, clamped to +-1/8 sample/microframe.
    int32_t const level = (int32_t) (tud_audio_available() / AUDIO_FRAME_BYTES) << 8;
    fifo_avg += (level - fifo_avg) / 16;
    int32_t const err = ((int32_t) target << 8) - fifo_avg;
    int32_t const nominal = (int32_t) nominal_feedback(rate);
    int32_t fb = nominal + err;
    if (fb > nominal + (1 << 13)) fb = nominal + (1 << 13);
    if (fb < nominal - (1 << 13)) fb = nominal - (1 << 13);
    feedback_value = (uint32_t) fb;
    tud_audio_fb_set((uint32_t) fb);
  }

  if (tone_on) {
    uint32_t const step = 960000u / (rate_codec ? rate_codec : rate_host);
    for (int i = 0; i < AUDIO_BLOCK_FRAMES; i++) {
      buf[2 * i] = buf[2 * i + 1] = (uint32_t) sine_tab[tone_phase] << 8;
      tone_phase += step;
      if (tone_phase >= 960) tone_phase -= 960;
    }
  } else if (!have) {
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
  rate_host = AUDIO_RATE_DEFAULT;
  codec_retry_at = board_millis();
  audio_calibrate();   // inputs assumed unpatched at power-up
}

// Codec reset + configuration with the clocks held, both I2S slaves armed,
// then the clocks start (i2s.h: the only start that aligns the slaves).
static void streams_start(uint32_t rate) {
  i2s_stop();
  rate_codec = 0;
  out_primed = false;
  codec_state_t const s = codec_prepare(rate);
  if (s != CODEC_READY) {
    last_error = codec_state_name(s);
    codec_retry_at = board_millis() + 2000;
    return;
  }
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
  if (cal_state != CAL_IDLE) audio_calibrate();   // a calibration in progress starts over
}

void audio_restart(void) {
  i2s_stop();
  codec_stop();
  rate_codec = 0;
  codec_retry_at = board_millis();
}

void audio_calibrate(void) {
  cal_left = 0;
  cal_state = CAL_SETTLE;
  cal_at = board_millis() + CAL_SETTLE_MS;
}

static void cal_task(uint32_t now) {
  if (cal_state == CAL_SETTLE && (int32_t) (now - cal_at) >= 0) {
    uint32_t const irq = board_irq_mask();
    cal_sum[0] = cal_sum[1] = 0;
    cal_n = 0;
    cal_left = rate_codec / 1000 * CAL_MS;
    board_irq_restore(irq);
    cal_state = CAL_SUM;
  } else if (cal_state == CAL_SUM && !cal_left && cal_n) {
    for (int c = 0; c < 2; c++) dc_offset[c] = (int32_t) (cal_sum[c] / (int32_t) cal_n);
    cal_state = CAL_IDLE;
    cal_valid = true;
  }
}

void audio_task(void) {
  uint32_t const now = board_millis();

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

void audio_get_status(audio_status_t *st) {
  st->rate_host = rate_host;
  st->rate_codec = rate_codec;
  st->out_streaming = out_streaming;
  st->in_streaming = in_streaming;
  st->out_primed = out_primed;
  st->dc_calibrated = cal_valid && cal_state == CAL_IDLE;
  st->dc_offset[0] = dc_offset[0];
  st->dc_offset[1] = dc_offset[1];
  st->out_underruns = out_underruns;
  st->in_overruns = in_overruns;
  st->feedback = feedback_value;
  st->out_fifo = out_streaming ? tud_audio_available() : 0;
  tu_fifo_t *ff = tud_audio_get_ep_in_ff();
  st->in_fifo = (in_streaming && ff) ? tu_fifo_count(ff) : 0;
  st->restarts = restarts;
  st->last_error = last_error;
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
        if (step > interval && step < 64) iso_stats.missed[i] += step / interval - 1u;
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

  if (itf == ITF_NUM_AUDIO_STREAMING_OUT) {
    fifo_avg = 0;
    out_primed = false;
    feedback_value = nominal_feedback(rate_host);
    tud_audio_fb_set(feedback_value);
    out_streaming = (alt != 0);
  } else if (itf == ITF_NUM_AUDIO_STREAMING_IN) {
    tud_audio_set_ep_in_fifo_threshold((uint16_t) (target_frames(rate_host) * AUDIO_FRAME_BYTES));
    in_streaming = (alt != 0);
  }
  return true;
}

bool tud_audio_set_itf_close_ep_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
  (void) rhport;
  uint8_t const itf = tu_u16_low(p_request->wIndex);
  if (itf == ITF_NUM_AUDIO_STREAMING_OUT) {
    out_streaming = false;
    out_primed = false;
  } else if (itf == ITF_NUM_AUDIO_STREAMING_IN) {
    in_streaming = false;
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
