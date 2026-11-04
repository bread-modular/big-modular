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
// Measure the input DC offsets again (IN 1/2 unpatched): 0.3 s settle, 0.5 s average.
void audio_calibrate(void);
// Restart codec + I2S from scratch.
void audio_restart(void);
// 1 kHz test tone at half scale on OUT 1 and OUT 2 instead of the USB data.
void audio_set_tone(bool on);
bool audio_tone(void);

typedef struct {
  uint32_t rate_host;        // rate requested by the host (clock SET_CUR)
  uint32_t rate_codec;       // rate the codec is configured for (0: not running)
  bool out_streaming, in_streaming;
  bool out_primed;
  bool dc_calibrated;
  int32_t dc_offset[2];      // input offsets subtracted, 24-bit codes (IN 1, IN 2)
  uint32_t out_underruns, in_overruns;
  uint32_t feedback;         // 16.16 samples per microframe
  uint16_t out_fifo, in_fifo;   // bytes
  uint32_t restarts;
  const char *last_error;
} audio_status_t;

void audio_get_status(audio_status_t *st);

// Completed iso transactions per endpoint (OUT data, IN data, feedback) and
// the packets missing between them, counted from the microframe number.
typedef struct {
  uint32_t packets[3], missed[3];
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
