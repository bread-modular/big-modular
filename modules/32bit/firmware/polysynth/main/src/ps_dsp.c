#include "ps_dsp.h"
#include "ps_wavetables.h"

#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Knob 2 is mapped to cutoff / resonance at this control rate (samples); the
// ladder smooths both per sample, as BM Ladder.h.
#define PS_CONTROL_BLOCK 16
// BM Ladder.h: per-sample parameter smoothing and the resonance clamp.
#define PS_LADDER_SMOOTHING 0.01f
#define PS_LADDER_K_MAX 1.2f
// Knob smoothing time constant.
#define PS_KNOB_SMOOTH_MS 20.0f
// Output level. BM divides the voice sum by 4 (polysynth_app.cpp), so one
// full-velocity voice peaks at only -12 dBFS. Here one voice peaks at
// PS_VOICE_GAIN, chords are turned down by the polyphony gain (ps_dsp.h) and the
// look-ahead limiter only catches what is left (resonant peaks, phase-aligned
// chords) under PS_LIMIT, ahead of a soft clip.
// The ladder runs at BM's level (one voice ~0.25 peak), so its tanh stages
// saturate as in BM; the output is scaled back up.
#define PS_LADDER_DRIVE 0.3f

// Wavetables keep harmonics up to this frequency (aliases of anything above
// fold back above 20 kHz at 44.1 kHz).
#define PS_WT_MAX_HZ 24000.0f

static float note_inc[128];
static uint8_t note_mip[128];
static float note_inc_rate = 0.0f;

static inline float clamp01(float x) {
    return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x);
}

// BM Ladder.h fast_tanh (also the output soft clip).
static inline float fast_tanh(float x) {
    if (x < -3.0f) return -1.0f;
    if (x > 3.0f) return 1.0f;
    float x2 = x * x;
    return x * (27.0f + x2) / (27.0f + 9.0f * x2);
}

// Linear up to PS_LIMIT, then a tanh knee into +-1 (catches the little the
// limiter's gain ramp lets through).
static inline float soft_clip(float x) {
    float a = fabsf(x);
    if (a <= PS_LIMIT) return x;
    float knee = 1.0f - PS_LIMIT;
    float y = PS_LIMIT + knee * fast_tanh((a - PS_LIMIT) / knee);
    return x < 0.0f ? -y : y;
}

// PolyBLEP residual for a unit step at phase 0 (t, dt in cycles).
static inline float poly_blep(float t, float dt) {
    if (t < dt) {
        t /= dt;
        return t + t - t * t - 1.0f;
    }
    if (t > 1.0f - dt) {
        t = (t - 1.0f) / dt;
        return t * t + t + t + 1.0f;
    }
    return 0.0f;
}

float ps_release_ms(float knob) {
    return PS_RELEASE_MIN_MS * powf(PS_RELEASE_MAX_MS / PS_RELEASE_MIN_MS, clamp01(knob));
}

void ps_filter_map(float knob, float *cutoff_hz, float *k, float *wet) {
    knob = clamp01(knob);
    float fc = PS_CUTOFF_MAX_HZ * powf(PS_CUTOFF_MIN_HZ / PS_CUTOFF_MAX_HZ, knob);

    // Resonance rises with the knob ...
    float rise = clamp01(knob / PS_RES_FULL_KNOB);
    // ... and fades out (smoothstep on a log-frequency axis) as the cutoff
    // falls from 400 Hz to 200 Hz: no resonance in the sub/bass range.
    float t = clamp01(log2f(fc / PS_RES_FADE_LO_HZ) / log2f(PS_RES_FADE_HI_HZ / PS_RES_FADE_LO_HZ));
    float fade = t * t * (3.0f - 2.0f * t);

    if (cutoff_hz) *cutoff_hz = fc;
    if (k) *k = PS_RES_MAX * rise * fade;
    if (wet) *wet = clamp01(knob / PS_BYPASS_FADE);
}

void ps_ladder_reset(ps_ladder_t *f, float cutoff, float k) {
    memset(f->z, 0, sizeof(f->z));
    f->cutoff = f->s_cutoff = cutoff;
    f->k = f->s_k = k;
}

// BM Ladder.h (Moog ladder, tanh stages), low-pass output; only the cutoff
// calibration differs.
float ps_ladder_process(ps_ladder_t *f, float input, float sample_rate) {
    float target_cutoff = fmaxf(10.0f, fminf(f->cutoff, sample_rate * 0.45f));
    f->s_cutoff += PS_LADDER_SMOOTHING * (target_cutoff - f->s_cutoff);
    float target_k = fmaxf(0.0f, fminf(f->k, PS_LADDER_K_MAX));
    f->s_k += PS_LADDER_SMOOTHING * (target_k - f->s_k);

    // Stage coefficient from the real cutoff (impulse invariant). BM uses
    // p = f * (1.8 - 0.8 f), f = fc / (fs / 2), which puts the -3 dB point near
    // fc / 4; this way the knob's Hz are the filter's Hz (resonant peak ~ fc).
    float p = 1.0f - expf(-2.0f * (float)M_PI * f->s_cutoff / sample_rate);
    float k = f->s_k;
    float scale = expf((1.0f - p) * 1.386249f);
    float r = fminf(k * scale, 3.99f);

    float *z = f->z;
    float x = input - r * z[3];
    z[0] += p * (fast_tanh(x) - fast_tanh(z[0]));
    z[1] += p * (fast_tanh(z[0]) - fast_tanh(z[1]));
    z[2] += p * (fast_tanh(z[1]) - fast_tanh(z[2]));
    z[3] += p * (fast_tanh(z[2]) - fast_tanh(z[3]));

    for (int i = 0; i < 4; i++) {
        if (fabsf(z[i]) < 1e-15f) z[i] = 0.0f;
    }

    // Moog ladders lose pass-band level as the resonance rises (DC gain
    // 1 / (1 + r)); BM makes up only (1 + k / 2), about -10 dB at full
    // resonance. Make it up fully, so closing the filter keeps the level.
    return z[3] * (1.0f + r);
}

void ps_init(ps_synth_t *s, float sample_rate) {
    memset(s, 0, sizeof(*s));
    s->sample_rate = sample_rate;
    s->wave = PS_WAVE_SAW;

    if (note_inc_rate != sample_rate) {
        for (int n = 0; n < 128; n++) {
            float hz = 440.0f * powf(2.0f, (n - 69) / 12.0f);
            note_inc[n] = hz / sample_rate;
            // Lowest mip level whose top harmonic stays under PS_WT_MAX_HZ.
            int level = 0;
            while (level < PS_WT_LEVELS - 1 && (PS_WT_TOP_HARMONICS >> level) * hz > PS_WT_MAX_HZ) level++;
            note_mip[n] = (uint8_t)level;
        }
        note_inc_rate = sample_rate;
    }

    s->attack_inc = 1000.0f / (PS_ATTACK_MS * sample_rate);
    s->knob_smooth = 1.0f - expf(-1000.0f / (PS_KNOB_SMOOTH_MS * sample_rate));
    s->limit_release = 1.0f - expf(-1000.0f / (PS_LIMIT_RELEASE_MS * sample_rate));
    s->poly_release = 1.0f - expf(-1000.0f / (PS_POLY_RELEASE_MS * sample_rate));
    s->poly_gain = PS_VOICE_GAIN;
    s->wave_fade = 1.0f;
    s->wave_fade_inc = 1000.0f / (PS_WAVE_FADE_MS * sample_rate);
    s->limit_env = PS_LIMIT;
    s->limit_gain = 1.0f;
    // Time constant a quarter of the look-ahead: 98 % settled when the peak leaves the delay.
    s->limit_attack = 1.0f - expf(-4.0f / PS_LIMIT_LOOKAHEAD);
    s->limit_hold_samples = (uint32_t)(PS_LIMIT_HOLD_MS * sample_rate / 1000.0f);
    ps_set_release_knob(s, 0.5f);

    float fc, k;
    ps_filter_map(0.0f, &fc, &k, NULL);
    ps_ladder_reset(&s->ladder, fc, k);
}

void ps_set_wave(ps_synth_t *s, ps_wave_t wave) {
    if (wave >= PS_WAVE_COUNT || wave == s->wave) return;
    // A change during a crossfade continues from the waveform being faded to.
    s->wave_prev = s->wave;
    s->wave = wave;
    s->wave_fade = 0.0f;
}

void ps_set_wave_now(ps_synth_t *s, ps_wave_t wave) {
    if (wave >= PS_WAVE_COUNT) return;
    s->wave = s->wave_prev = wave;
    s->wave_fade = 1.0f;
}

const char *ps_wave_name(ps_wave_t wave) {
    if (wave == PS_WAVE_SAW) return "saw";
    if (wave < PS_WAVE_COUNT) return ps_wt_names[wave - 1];
    return "?";
}

void ps_set_release_knob(ps_synth_t *s, float knob) {
    s->release_inc = 1000.0f / (ps_release_ms(knob) * s->sample_rate);
}

void ps_set_filter_knob(ps_synth_t *s, float knob) {
    s->filter_knob = clamp01(knob);
}

static ps_voice_t *pick_voice(ps_synth_t *s, uint8_t note) {
    ps_voice_t *v = s->voices;
    // 1. the same note still held: retrigger it
    for (int i = 0; i < PS_VOICES; i++) {
        if (v[i].state != PS_ENV_IDLE && v[i].gate && v[i].note == note) return &v[i];
    }
    // 2. a free voice
    for (int i = 0; i < PS_VOICES; i++) {
        if (v[i].state == PS_ENV_IDLE) return &v[i];
    }
    // 3. steal the oldest released voice, then the oldest pedal-sustained one,
    //    else the oldest voice (BM drops the note)
    ps_voice_t *oldest = NULL;
    for (int i = 0; i < PS_VOICES; i++) {
        if (!v[i].gate && (!oldest || v[i].age < oldest->age)) oldest = &v[i];
    }
    if (oldest) return oldest;
    for (int i = 0; i < PS_VOICES; i++) {
        if (v[i].sustained && (!oldest || v[i].age < oldest->age)) oldest = &v[i];
    }
    if (oldest) return oldest;
    for (int i = 0; i < PS_VOICES; i++) {
        if (!oldest || v[i].age < oldest->age) oldest = &v[i];
    }
    return oldest;
}

void ps_note_on(ps_synth_t *s, uint8_t note, uint8_t velocity) {
    note &= 0x7F;
    float vn = (velocity & 0x7F) / 127.0f;
    ps_voice_t *v = pick_voice(s, note);
    if (v->state == PS_ENV_IDLE) {
        v->phase = 0.0f;
        v->level = 0.0f;
    }
    // A retriggered / stolen voice ramps up from its current level (no reset click).
    v->note = note;
    v->inc = note_inc[note];
    v->mip = note_mip[note];
    v->velocity = vn * vn;
    v->age = ++s->age_counter;
    v->gate = true;
    v->sustained = false;
    v->state = PS_ENV_ATTACK;
}

void ps_note_off(ps_synth_t *s, uint8_t note) {
    for (int i = 0; i < PS_VOICES; i++) {
        ps_voice_t *v = &s->voices[i];
        if (!v->gate || v->sustained || v->note != (note & 0x7F)) continue;
        if (s->pedal) {
            v->sustained = true;
        } else {
            v->gate = false;
        }
    }
}

void ps_all_notes_off(ps_synth_t *s) {
    s->pedal = false;
    for (int i = 0; i < PS_VOICES; i++) {
        s->voices[i].gate = false;
        s->voices[i].sustained = false;
    }
}

void ps_sustain(ps_synth_t *s, bool down) {
    s->pedal = down;
    if (down) return;
    for (int i = 0; i < PS_VOICES; i++) {
        ps_voice_t *v = &s->voices[i];
        if (v->sustained) {
            v->sustained = false;
            v->gate = false;
        }
    }
}

static inline float osc(ps_wave_t wave, const ps_voice_t *v) {
    if (wave == PS_WAVE_SAW) return 2.0f * v->phase - 1.0f - poly_blep(v->phase, v->inc);
    // Wavetable: the note's mip level, linear interpolation (guard sample at the end).
    const int16_t *t = &ps_wt_data[ps_wt_offset[wave - 1][v->mip]];
    float pos = v->phase * ps_wt_size[v->mip];
    int i = (int)pos;
    float a = t[i], b = t[i + 1];
    return (a + (pos - i) * (b - a)) * (1.0f / 32767.0f);
}

// Attack -> hold (gate) -> release, linear segments as BM AttackHoldRelease.h.
static inline float envelope(ps_synth_t *s, ps_voice_t *v) {
    switch (v->state) {
        case PS_ENV_ATTACK:
            v->level += s->attack_inc;
            if (v->level >= 1.0f) {
                v->level = 1.0f;
                v->state = PS_ENV_HOLD;
            }
            break;
        case PS_ENV_HOLD:
            if (!v->gate) v->state = PS_ENV_RELEASE;
            break;
        case PS_ENV_RELEASE:
            v->level -= s->release_inc;
            if (v->level <= 0.0f) {
                v->level = 0.0f;
                v->state = PS_ENV_IDLE;
            }
            break;
        case PS_ENV_IDLE:
        default:
            break;
    }
    return v->level;
}

float ps_process(ps_synth_t *s) {
    float sum = 0.0f, level = 0.0f;
    bool fading = s->wave_fade < 1.0f;
    for (int i = 0; i < PS_VOICES; i++) {
        ps_voice_t *v = &s->voices[i];
        if (v->state == PS_ENV_IDLE) continue;
        float y = osc(s->wave, v);
        if (fading) {
            float y0 = osc(s->wave_prev, v);
            y = y0 + s->wave_fade * (y - y0);
        }
        v->phase += v->inc;
        if (v->phase >= 1.0f) v->phase -= 1.0f;
        float amp = envelope(s, v) * v->velocity;
        sum += y * amp;
        level += amp;
    }
    if (fading) {
        s->wave_fade += s->wave_fade_inc;
        if (s->wave_fade >= 1.0f) {
            s->wave_fade = 1.0f;
            s->wave_prev = s->wave;
        }
    }

    // Polyphony gain from the summed voice level: follows new notes at once (the
    // 5 ms envelope attack keeps that smooth), recovers over PS_POLY_RELEASE_MS
    // so releasing notes do not pump the others.
    if (level > s->poly_level) {
        s->poly_level = level;
    } else {
        s->poly_level += s->poly_release * (level - s->poly_level);
    }
    float dry = sum * s->poly_gain;

    s->s_filter_knob += s->knob_smooth * (s->filter_knob - s->s_filter_knob);
    if (s->control++ % PS_CONTROL_BLOCK == 0) {
        ps_filter_map(s->s_filter_knob, &s->ladder.cutoff, &s->ladder.k, &s->wet);
        s->poly_gain = PS_VOICE_GAIN / powf(fmaxf(1.0f, s->poly_level), PS_POLY_EXP);
    }

    float lp = ps_ladder_process(&s->ladder, dry * PS_LADDER_DRIVE, s->sample_rate) / PS_LADDER_DRIVE;
    float y = dry + s->wet * (lp - dry);

    // Look-ahead limiter: the held peak jumps to a new peak, holds, then decays
    // (never below PS_LIMIT, so the gain is 1 until the output would pass it);
    // the gain glides to PS_LIMIT / peak while the sample waits in the delay.
    float a = fabsf(y);
    if (a >= s->limit_env) {
        s->limit_env = a;
        s->limit_hold = s->limit_hold_samples;
    } else if (s->limit_hold > 0) {
        s->limit_hold--;
    } else {
        s->limit_env += s->limit_release * (fmaxf(a, PS_LIMIT) - s->limit_env);
    }
    s->limit_gain += s->limit_attack * (PS_LIMIT / s->limit_env - s->limit_gain);
    float delayed = s->limit_delay[s->limit_pos];
    s->limit_delay[s->limit_pos] = y;
    s->limit_pos = (s->limit_pos + 1) % PS_LIMIT_LOOKAHEAD;
    return soft_clip(delayed * s->limit_gain);
}

bool ps_any_gate(const ps_synth_t *s) {
    for (int i = 0; i < PS_VOICES; i++) {
        if (s->voices[i].gate) return true;
    }
    return false;
}

int ps_active_voices(const ps_synth_t *s) {
    int n = 0;
    for (int i = 0; i < PS_VOICES; i++) {
        if (s->voices[i].state != PS_ENV_IDLE) n++;
    }
    return n;
}
