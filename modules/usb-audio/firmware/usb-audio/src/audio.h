// USB audio <-> I2S data path, sample rate, feedback and meters.
#ifndef AUDIO_H_
#define AUDIO_H_

#include <stdbool.h>
#include <stdint.h>

// I2S DMA half-buffer callbacks (audio worker, interrupt context).
void audio_i2s_rx(const uint16_t *src);
void audio_i2s_tx(uint16_t *dst);

void audio_init(void);
// Main loop: applies host sample-rate changes, (re)starts the codec and I2S,
// recovers from I2S errors and runs the input DC-offset calibration.
void audio_task(void);
// Measure the input DC offsets (IN 1/2 unpatched) and save them in the settings
// page; the result is in audio_status_t.cal. Saving restarts codec + I2S.
void audio_calibrate(void);
// Forget the saved offsets: they are measured after every power-up again.
bool audio_calibration_erase(void);
// Restart codec + I2S from scratch, with the codec held in reset for `hold_ms` first.
void audio_restart(uint32_t hold_ms);
// 1 kHz test tone at half scale on OUT 1 and OUT 2 instead of the USB data.
void audio_set_tone(bool on);
bool audio_tone(void);

typedef enum {
  AUDIO_CAL_NONE,
  AUDIO_CAL_MEASURING,
  AUDIO_CAL_MEASURED,        // in use, not saved (power-up measurement)
  AUDIO_CAL_SAVED,           // in use, from the settings page
  AUDIO_CAL_NOT_SAVED,       // in use, the flash write failed
  AUDIO_CAL_UNSTEADY,        // failed: the inputs did not hold still (signal patched?)
  AUDIO_CAL_RANGE,           // failed: more than 0.1 V is not an offset (CV patched?)
} audio_cal_t;

typedef struct {
  bool streaming;
  bool primed;               // playing / sending audio (not filling)
  uint16_t level, target;    // buffer, frames
  uint16_t level_min, level_max;   // since the previous audio_get_status()
  uint32_t rate;             // 16.16 samples per microframe: OUT feedback, IN packet size
  uint32_t underruns, overruns;
} audio_stream_t;

typedef struct {
  uint32_t rate_host;        // rate requested by the host (clock SET_CUR)
  uint32_t rate_codec;       // rate the codec is configured for (0: not running)
  audio_stream_t out, in;
  uint8_t out_target_ms;     // AUDIO_TARGET_MS, more after OUT underruns
  audio_cal_t cal;
  int32_t dc_offset[2];      // input offsets subtracted, 24-bit codes (IN 1, IN 2)
  uint32_t restarts;
  const char *last_error;
} audio_status_t;

void audio_get_status(audio_status_t *st);

// Completed iso transactions per endpoint (OUT data, IN data, feedback) and
// the packets missing between them, counted from the microframe number, since
// the previous call; missed_total since the reset.
typedef struct {
  uint32_t packets[3], missed[3], missed_total[3];
} audio_iso_stats_t;

void audio_take_iso_stats(audio_iso_stats_t *s);

// Meters since the previous call: peak |sample| and mean, full scale = 1 << 23.
typedef struct {
  int32_t in_peak[2], out_peak[2];
  int32_t in_mean[2], out_mean[2];
  uint32_t frames;
} audio_meter_t;

void audio_take_meter(audio_meter_t *m);

#endif
