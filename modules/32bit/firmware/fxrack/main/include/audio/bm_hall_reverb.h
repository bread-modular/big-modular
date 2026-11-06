#pragma once

// bm_hall_reverb: a big mono hall reverb (replaces the BM classic Schroeder
// reverb in the fxrack app).
//
//   in -> tone (HP 90 Hz, LP 9 kHz) -> pre-delay 22 ms -> 8 channels
//      -> diffuser: 4 stages of (8 delays, polarity flips, 8x8 Hadamard)
//      -> 8-line feedback delay network (Householder matrix, 50..92 ms lines,
//         slow sine modulation, per-line one-pole damping set from the RT60)
//      -> out = late tail + a little of the diffused early sound
//
// The diffuser builds the echo density in the first ~50 ms, the FDN gives the
// smooth exponential tail; the modulation stops it ringing on fixed modes.

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BM_HALL_REVERB_CHANNELS 8
#define BM_HALL_REVERB_DIFFUSER_STAGES 4
#define BM_HALL_REVERB_LFOS (BM_HALL_REVERB_CHANNELS / 2)
#define BM_HALL_REVERB_RT60_MIN 0.3f
#define BM_HALL_REVERB_RT60_MAX 20.0f

typedef struct {
    float* data;
    int32_t size;
    int32_t pos;
} bm_hall_delay_t;

typedef struct {
    bm_hall_delay_t predelay;
    int32_t predelay_samples;
    bm_hall_delay_t diffuser[BM_HALL_REVERB_DIFFUSER_STAGES][BM_HALL_REVERB_CHANNELS];
    int32_t diffuser_samples[BM_HALL_REVERB_DIFFUSER_STAGES][BM_HALL_REVERB_CHANNELS];
    float diffuser_sign[BM_HALL_REVERB_DIFFUSER_STAGES][BM_HALL_REVERB_CHANNELS];
    bm_hall_delay_t late[BM_HALL_REVERB_CHANNELS];
    float late_samples[BM_HALL_REVERB_CHANNELS];

    // Quadrature LFOs: line 2k reads the cosine, line 2k + 1 the sine of LFO k.
    float lfo_cos[BM_HALL_REVERB_LFOS];
    float lfo_sin[BM_HALL_REVERB_LFOS];
    float lfo_step_cos[BM_HALL_REVERB_LFOS];
    float lfo_step_sin[BM_HALL_REVERB_LFOS];
    float mod_depth;

    // Per-line damping H(z) = gain (1 - pole) / (1 - pole z^-1), glided to the targets.
    float gain[BM_HALL_REVERB_CHANNELS];
    float gain_target[BM_HALL_REVERB_CHANNELS];
    float pole[BM_HALL_REVERB_CHANNELS];
    float pole_target[BM_HALL_REVERB_CHANNELS];
    float damp_state[BM_HALL_REVERB_CHANNELS];
    int32_t glide_samples;

    float hp_coeff, hp_state, hp_last_in;
    float lp_coeff, lp_state;
    float late_level, late_level_target;
    float early_level;
    float rt60;
} bm_hall_reverb_t;

void bm_hall_reverb_init(bm_hall_reverb_t* reverb);
void bm_hall_reverb_destroy(bm_hall_reverb_t* reverb);
float bm_hall_reverb_process(bm_hall_reverb_t* reverb, float input);
// Decay time at low/mid frequencies, clamped to RT60_MIN..RT60_MAX seconds.
void bm_hall_reverb_set_rt60(bm_hall_reverb_t* reverb, float rt60);

#ifdef __cplusplus
}
#endif
