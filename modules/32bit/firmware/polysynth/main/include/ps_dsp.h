#pragma once

// Polysynth DSP: a C port of the Bread Modular 16bit polysynth
// (bread-modular/modules/16bit/code/16bit: polysynth_app.cpp, Voice.h,
// AttackHoldRelease.h, Saw/Square/Tri.h, fx/filter_fx.h, mod/Ladder.h).
//
// Pure C, no ESP-IDF headers, so tests/ builds it on the host. Not thread-safe:
// call everything from the audio task (main.c queues MIDI / button events).

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PS_VOICES 9

// Amp envelope: attack (fixed) -> hold while the gate is high -> release (knob 1).
#define PS_ATTACK_MS 5.0f
#define PS_RELEASE_MIN_MS 10.0f
#define PS_RELEASE_MAX_MS 4000.0f

// Filter knob (knob 2): 0 = bypass, then a ladder low pass that closes from
// PS_CUTOFF_MAX_HZ to PS_CUTOFF_MIN_HZ (exponential) while the resonance rises.
// The resonance fades out between PS_RES_FADE_HI_HZ and PS_RES_FADE_LO_HZ, so
// there is none below 200 Hz.
#define PS_CUTOFF_MAX_HZ 18000.0f
#define PS_CUTOFF_MIN_HZ 50.0f
#define PS_BYPASS_FADE 0.1f     // knob travel of the dry -> filtered crossfade
#define PS_RES_MAX 0.95f         // ladder k at full resonance (strong, not self-oscillating)
#define PS_RES_FULL_KNOB 0.6f    // knob position where the resonance is at maximum
#define PS_RES_FADE_HI_HZ 400.0f
#define PS_RES_FADE_LO_HZ 200.0f

// Waveform positions (MODE button steps through them): 0 = PolyBLEP saw (the
// default), 1 .. PS_WT_COUNT = band-limited wavetables (ps_wavetables.h,
// generated offline). A change crossfades over PS_WAVE_FADE_MS.
#define PS_WAVE_SAW 0
#define PS_WAVE_COUNT 8
#define PS_WAVE_FADE_MS 20.0f
typedef uint8_t ps_wave_t;

// Output: one full-velocity voice peaks at PS_VOICE_GAIN; a look-ahead peak
// limiter keeps the output under PS_LIMIT (then a soft clip). The limiter
// holds its gain for PS_LIMIT_HOLD_MS, longer than a waveform cycle, so it
// turns the level down smoothly instead of flattening each peak (which sounds
// like clipping).
#define PS_VOICE_GAIN 0.8f
#define PS_LIMIT 0.9f
#define PS_LIMIT_LOOKAHEAD 32       // samples (0.7 ms, added latency)
#define PS_LIMIT_HOLD_MS 60.0f
#define PS_LIMIT_RELEASE_MS 250.0f

// Polyphony gain: the summed voice level L = sum(envelope x velocity), tracked
// instantly up / slowly down, sets the mix gain PS_VOICE_GAIN / max(1, L)^PS_POLY_EXP,
// so one voice is at full level and chords are turned down before they clip.
#define PS_POLY_EXP 0.8f
#define PS_POLY_RELEASE_MS 300.0f

typedef enum {
    PS_ENV_IDLE = 0,
    PS_ENV_ATTACK,
    PS_ENV_HOLD,
    PS_ENV_RELEASE
} ps_env_state_t;

typedef struct {
    float phase;        // 0..1
    float inc;          // f / fs
    float level;        // envelope 0..1
    float velocity;     // (v / 127)^2, as BM
    uint8_t mip;        // wavetable mipmap level for this note
    uint32_t age;       // note-on order, for voice stealing
    uint8_t note;
    bool gate;          // envelope held (key down, or key up under the sustain pedal)
    bool sustained;     // key released while the pedal is down: gate drops on pedal up
    ps_env_state_t state;
} ps_voice_t;

typedef struct {
    float z[4];
    float cutoff;       // target Hz
    float k;            // target resonance
    float s_cutoff;     // smoothed
    float s_k;
} ps_ladder_t;

typedef struct {
    float sample_rate;
    ps_voice_t voices[PS_VOICES];
    uint32_t age_counter;
    ps_wave_t wave;
    ps_wave_t wave_prev;    // crossfading from this one while wave_fade < 1
    float wave_fade;
    float wave_fade_inc;
    bool pedal;         // CC64 sustain pedal down

    float attack_inc;
    float release_inc;

    float filter_knob;      // target 0..1
    float s_filter_knob;    // smoothed per sample
    float knob_smooth;      // one-pole coefficient
    float wet;              // dry -> filtered crossfade
    uint32_t control;       // control-rate counter
    float poly_level;       // tracked summed voice level L
    float poly_release;     // one-pole coefficient for L going down
    float poly_gain;        // PS_VOICE_GAIN / max(1, L)^PS_POLY_EXP
    float limit_env;        // held output peak (>= PS_LIMIT); gain target PS_LIMIT / limit_env
    float limit_gain;       // smoothed limiter gain
    float limit_attack;     // gain coefficient: settles within the look-ahead
    float limit_release;    // held peak decay after the hold
    uint32_t limit_hold_samples;
    uint32_t limit_hold;    // samples left in the hold
    uint32_t limit_pos;
    float limit_delay[PS_LIMIT_LOOKAHEAD];
    ps_ladder_t ladder;
} ps_synth_t;

void ps_init(ps_synth_t *s, float sample_rate);
void ps_note_on(ps_synth_t *s, uint8_t note, uint8_t velocity);
void ps_note_off(ps_synth_t *s, uint8_t note);
void ps_all_notes_off(ps_synth_t *s);
// CC64 sustain pedal: while down, note-offs keep their voices held; pedal up
// releases them. All notes off also lifts the pedal.
void ps_sustain(ps_synth_t *s, bool down);
// Crossfades to the new waveform; ps_set_wave_now switches at once (boot).
void ps_set_wave(ps_synth_t *s, ps_wave_t wave);
void ps_set_wave_now(ps_synth_t *s, ps_wave_t wave);
const char *ps_wave_name(ps_wave_t wave);

// Knob 1 (0..1): release time. Knob 2 (0..1): filter (see above).
void ps_set_release_knob(ps_synth_t *s, float knob);
void ps_set_filter_knob(ps_synth_t *s, float knob);

// One mono output sample, peak-limited and soft-clipped to -1..1.
float ps_process(ps_synth_t *s);

bool ps_any_gate(const ps_synth_t *s);
int ps_active_voices(const ps_synth_t *s);

// Knob mappings, exposed for tests and docs.
float ps_release_ms(float knob);
void ps_filter_map(float knob, float *cutoff_hz, float *k, float *wet);

// Ladder filter alone (tests).
void ps_ladder_reset(ps_ladder_t *f, float cutoff, float k);
float ps_ladder_process(ps_ladder_t *f, float input, float sample_rate);

#ifdef __cplusplus
}
#endif
