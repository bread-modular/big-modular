// USB audio <-> TDM data path: codec + TDM start / recovery, the UAC2 streams
// with their buffers and feedback, the per-channel calibration applied to every
// sample, test signals on the outputs and meters.
#ifndef AUDIO_H_
#define AUDIO_H_

#include <stdbool.h>
#include <stdint.h>

#include "audio_config.h"
#include "dcd_capture.h"
#include "tdm.h"

// Jack level at full scale, millivolts (docs/research.md section 2). Nominal:
// IN +/-5.89 V, OUT +/-5.87 V. The calibration (cal.c) makes both exactly
// AUDIO_FS_MV, so a sample played on OUT n comes back the same on an IN.
#define AUDIO_IN_FS_MV   5890
#define AUDIO_OUT_FS_MV  5870
#define AUDIO_FS_MV      5870
#define AUDIO_FS_CODE    (1 << 23)   // 24-bit full scale

void audio_init(void);
// Main loop: (re)starts codec + TDM, finds the frame position, recovers from errors.
void audio_task(void);
// Restart codec + TDM from scratch, with the codec held in reset for `hold_ms` first.
void audio_restart(uint32_t hold_ms);
// The IN ring as scratch memory (console `blwrite`): with `len` set only its
// size; with NULL the audio stops for up to a minute (audio_restart(0) ends it)
// and the memory is returned.
void *audio_scratch(uint32_t *len);

typedef enum {
  AUDIO_STOPPED,     // codec not running (see last_error), retrying
  AUDIO_SETTLING,    // clocks running, waiting for the ADC to send data
  AUDIO_ALIGNING,    // measuring the frame position
  AUDIO_RUNNING,     // frame position known: audio passes
} audio_state_t;

const char *audio_state_name(audio_state_t s);

typedef struct {
  bool streaming;
  bool primed;                     // playing / sending audio (not filling)
  uint16_t level, target;          // buffer, frames
  uint16_t level_min, level_max;   // since the previous audio_get_status()
  uint32_t rate;                   // 16.16 samples per microframe: OUT feedback, IN packet size
  uint32_t underruns, overruns;
} audio_stream_t;

typedef struct {
  audio_state_t state;
  uint32_t restarts;
  const char *last_error;
  audio_stream_t out, in;
  uint8_t out_target_ms;           // AUDIO_TARGET_MS, more after OUT underruns
} audio_status_t;

// Stream levels min / max restart with every call.
void audio_get_status(audio_status_t *st);
audio_state_t audio_get_state(void);

// Calibration coefficients applied to every sample (cal.c computes them):
//   IN:  sample = (code - in_zero) * in_gain
//   OUT: code = sample * out_gain + out_zero
// Gains Q30 (1 << 30 = 1.0), zeros 24-bit codes.
typedef struct {
  int32_t in_zero[AUDIO_IN_CHANNELS], in_gain[AUDIO_IN_CHANNELS];
  int32_t out_zero[AUDIO_OUT_CHANNELS], out_gain[AUDIO_OUT_CHANNELS];
} audio_coef_t;

#define AUDIO_Q30 (1 << 30)
void audio_set_coef(audio_coef_t const *c);
void audio_get_coef(audio_coef_t *c);
// Calibrated sample <-> raw code, with the coefficients in use.
int32_t audio_in_sample(int ch, int32_t code);
int32_t audio_out_code(int ch, int32_t sample);

// Output sources, per output (0..7): the USB stream (default), a DC level as a
// calibrated sample, a raw DAC code (calibration bypassed), or a 1 kHz sine at
// half scale.
typedef enum { GEN_USB, GEN_DC, GEN_RAW, GEN_SINE } gen_mode_t;
void audio_gen_set(int ch, gen_mode_t mode, int32_t value);
gen_mode_t audio_gen_mode(int ch);
int32_t audio_gen_value(int ch);

// Input meters since the previous call, raw ADC codes (before the calibration).
typedef struct {
  int32_t in_mean[AUDIO_IN_CHANNELS], in_min[AUDIO_IN_CHANNELS], in_max[AUDIO_IN_CHANNELS];
  uint32_t frames;
} audio_meter_t;

void audio_take_meter(audio_meter_t *m);

// Completed iso transactions per endpoint (OUT data, IN data, feedback) and
// the packets missing between them, counted from the microframe number, since
// the previous call; missed_total since the reset.
typedef struct {
  uint32_t packets[3], missed[3], missed_total[3];
} audio_iso_stats_t;

void audio_take_iso_stats(audio_iso_stats_t *s);
// Diagnostics (console `misses`): the captured USB events up to the first
// missed iso packet since the last call (AUDIO_MISS_TRACE entries, oldest
// first), its endpoint (0 OUT, 1 IN, 2 feedback) and the microframe step.
#define AUDIO_MISS_TRACE 16
bool audio_take_miss_trace(dcd_trace_t *t, int *ep, uint16_t *step);

// Sample (full scale AUDIO_FS_CODE = AUDIO_FS_MV) <-> millivolts at the jack.
int32_t audio_mv_to_sample(int32_t mv);
int32_t audio_sample_to_mv(int32_t sample);

#endif
