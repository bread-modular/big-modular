// Host tests for the polysynth DSP. Run: make (in this directory).
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ps_dsp.h"
#include "ps_wavetables.h"

#define FS 44100.0f
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static int failures = 0;
#define CHECK(cond, ...) do { \
    if (!(cond)) { failures++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } \
} while (0)

// Steady-state gain (dB) of the ladder at freq for a small sine (linear region).
static float ladder_gain_db(float cutoff, float k, float freq) {
    ps_ladder_t f;
    ps_ladder_reset(&f, cutoff, k);
    const float amp = 0.05f;
    int settle = (int)(FS * 0.3f), n = (int)(FS * 0.2f);
    double in2 = 0, out2 = 0;
    for (int i = 0; i < settle + n; i++) {
        float x = amp * sinf(2.0f * (float)M_PI * freq * i / FS);
        float y = ps_ladder_process(&f, x, FS);
        if (i >= settle) { in2 += x * x; out2 += y * y; }
    }
    return 10.0f * log10f((float)(out2 / in2));
}

// Peak gain over a log sweep around the cutoff.
static float ladder_peak_db(float cutoff, float k, float *peak_hz) {
    float best = -200.0f, best_f = 0;
    for (float f = cutoff * 0.5f; f < fminf(cutoff * 2.0f, FS * 0.45f); f *= 1.03f) {
        float g = ladder_gain_db(cutoff, k, f);
        if (g > best) { best = g; best_f = f; }
    }
    if (peak_hz) *peak_hz = best_f;
    return best;
}

static void test_filter_map(void) {
    float fc, k, wet, prev_fc = 1e9f;
    ps_filter_map(0.0f, &fc, &k, &wet);
    CHECK(wet == 0.0f, "knob 0 must bypass (wet %f)", wet);
    CHECK(k == 0.0f, "knob 0 has no resonance (k %f)", k);
    ps_filter_map(PS_BYPASS_FADE, NULL, NULL, &wet);
    CHECK(wet == 1.0f, "wet reaches 1 at the end of the fade");
    printf("knob  cutoff_Hz   k     wet\n");
    for (int i = 0; i <= 20; i++) {
        float x = i / 20.0f;
        ps_filter_map(x, &fc, &k, &wet);
        printf("%.2f  %8.1f  %.3f  %.2f\n", x, fc, k, wet);
        CHECK(fc < prev_fc, "cutoff must fall as the knob rises");
        prev_fc = fc;
        if (fc <= PS_RES_FADE_LO_HZ) CHECK(k == 0.0f, "no resonance at %.0f Hz (k %f)", fc, k);
        CHECK(k <= PS_RES_MAX + 1e-6f, "k above max");
    }
    ps_filter_map(1.0f, &fc, NULL, NULL);
    CHECK(fabsf(fc - PS_CUTOFF_MIN_HZ) < 0.5f, "knob 1 cutoff %f", fc);
}

static void test_ladder_response(void) {
    printf("knob  cutoff_Hz   k     peak_dB @Hz   dc_dB\n");
    for (int i = 1; i <= 20; i++) {
        float x = i / 20.0f, fc, k, peak_hz;
        ps_filter_map(x, &fc, &k, NULL);
        float peak = ladder_peak_db(fc, k, &peak_hz);
        float dc = ladder_gain_db(fc, k, 20.0f);
        printf("%.2f  %8.1f  %.3f  %6.1f @%6.0f  %5.1f\n", x, fc, k, peak, peak_hz, dc);
        CHECK(peak < 24.0f, "resonance peak %.1f dB too high at knob %.2f", peak, x);
        if (fc <= PS_RES_FADE_LO_HZ) CHECK(peak - dc < 1.0f, "resonant bump below 200 Hz (%.1f dB)", peak - dc);
    }
    // Stopband at the most closed position: 2 kHz well down.
    float fc;
    ps_filter_map(1.0f, &fc, NULL, NULL);
    CHECK(ladder_gain_db(fc, 0.0f, 2000.0f) < -60.0f, "closed filter must attenuate 2 kHz");
}

// Impulse into the ladder at every knob position: no self-oscillation.
static void test_ladder_decays(void) {
    for (int i = 0; i <= 20; i++) {
        float fc, k;
        ps_filter_map(i / 20.0f, &fc, &k, NULL);
        ps_ladder_t f;
        ps_ladder_reset(&f, fc, k);
        float tail = 0;
        for (int n = 0; n < (int)FS; n++) {
            float y = ps_ladder_process(&f, n == 0 ? 1.0f : 0.0f, FS);
            CHECK(isfinite(y), "non-finite ladder output");
            if (n > (int)FS - 4410) tail = fmaxf(tail, fabsf(y));
        }
        CHECK(tail < 1e-4f, "ladder rings at knob %.2f (tail %g)", i / 20.0f, tail);
    }
}

static int samples_until_idle(ps_synth_t *s) {
    for (int n = 0; n < (int)(FS * 10); n++) {
        ps_process(s);
        if (ps_active_voices(s) == 0) return n;
    }
    return -1;
}

static void test_envelope(void) {
    ps_synth_t s;
    float knobs[] = {0.0f, 0.5f, 1.0f};
    for (int i = 0; i < 3; i++) {
        ps_init(&s, FS);
        ps_set_release_knob(&s, knobs[i]);
        ps_note_on(&s, 60, 127);
        for (int n = 0; n < (int)(FS * 0.1f); n++) ps_process(&s);  // past attack, holding
        CHECK(s.voices[0].state == PS_ENV_HOLD && s.voices[0].level == 1.0f, "hold at full level while gated");
        ps_note_off(&s, 60);
        float ms = samples_until_idle(&s) * 1000.0f / FS;
        float want = ps_release_ms(knobs[i]);
        printf("release knob %.1f: %.1f ms (want %.1f)\n", knobs[i], ms, want);
        CHECK(fabsf(ms - want) < 0.02f * want + 0.2f, "release time %.1f vs %.1f", ms, want);
    }
    // Attack time and a short tap still reaching full level (BM: attack runs out).
    ps_init(&s, FS);
    ps_note_on(&s, 60, 127);
    int n = 0;
    while (s.voices[0].state == PS_ENV_ATTACK) { ps_process(&s); n++; }
    float ms = n * 1000.0f / FS;
    CHECK(fabsf(ms - PS_ATTACK_MS) < 0.1f, "attack %.2f ms", ms);
}

static void test_voices(void) {
    ps_synth_t s;
    ps_init(&s, FS);
    for (int i = 0; i < PS_VOICES + 1; i++) ps_note_on(&s, (uint8_t)(48 + i), 100);
    CHECK(ps_active_voices(&s) == PS_VOICES, "voice count %d", ps_active_voices(&s));
    int found_last = 0, found_first = 0;
    for (int i = 0; i < PS_VOICES; i++) {
        if (s.voices[i].note == 48 + PS_VOICES) found_last = 1;
        if (s.voices[i].note == 48) found_first = 1;
    }
    CHECK(found_last && !found_first, "oldest voice is stolen for the 10th note");
    // Same note again retriggers, does not take a second voice.
    ps_init(&s, FS);
    ps_note_on(&s, 60, 100);
    ps_note_on(&s, 60, 100);
    CHECK(ps_active_voices(&s) == 1, "retrigger uses one voice");
    CHECK(ps_any_gate(&s), "gate on");
    ps_note_off(&s, 60);
    CHECK(!ps_any_gate(&s), "gate off");
}

static void test_sustain(void) {
    ps_synth_t s;
    ps_init(&s, FS);
    ps_note_on(&s, 60, 100);
    ps_sustain(&s, true);
    ps_note_off(&s, 60);
    CHECK(ps_any_gate(&s), "pedal holds a released key");
    ps_note_on(&s, 64, 100);
    ps_note_off(&s, 64);
    CHECK(ps_active_voices(&s) == 2, "pedal holds both notes");
    // Key down again under the pedal: retrigger, then pedal up keeps it held.
    ps_note_on(&s, 60, 100);
    ps_sustain(&s, false);
    CHECK(s.voices[0].gate && !s.voices[1].gate, "pedal up releases only the sustained note");
    ps_note_off(&s, 60);
    CHECK(!ps_any_gate(&s), "key up after the pedal releases");
    // Note held before and after the pedal: the pedal does not release it.
    ps_init(&s, FS);
    ps_note_on(&s, 60, 100);
    ps_sustain(&s, true);
    ps_sustain(&s, false);
    CHECK(ps_any_gate(&s), "pedal tap keeps a held key");
    ps_sustain(&s, true);
    ps_all_notes_off(&s);
    CHECK(!ps_any_gate(&s) && !s.pedal, "all notes off lifts the pedal");
}

static void test_level_and_tuning(void) {
    ps_synth_t s;
    for (int w = 0; w < PS_WAVE_COUNT; w++) {
        ps_init(&s, FS);
        ps_set_wave(&s, (ps_wave_t)w);
        ps_set_filter_knob(&s, 0.55f);  // resonant
        for (int i = 0; i < PS_VOICES; i++) ps_note_on(&s, (uint8_t)(36 + 5 * i), 127);
        float peak = 0;
        for (int n = 0; n < (int)FS; n++) {
            float y = ps_process(&s);
            CHECK(isfinite(y) && fabsf(y) <= 1.0f, "output out of range");
            peak = fmaxf(peak, fabsf(y));
        }
        printf("wave %d, 9 voices, knob 0.55: peak %.2f\n", w, peak);
    }
    // A4 (69) at 440 Hz: count rising zero crossings over 1 s, filter bypassed.
    ps_init(&s, FS);
    ps_note_on(&s, 69, 127);
    for (int n = 0; n < 2000; n++) ps_process(&s);
    float prev = ps_process(&s);
    int crossings = 0;
    for (int n = 0; n < (int)FS; n++) {
        float y = ps_process(&s);
        if (prev < 0 && y >= 0) crossings++;
        prev = y;
    }
    CHECK(abs(crossings - 440) <= 1, "A4 at %d Hz", crossings);
    CHECK(s.wet == 0.0f, "filter knob 0 keeps the filter out of the path");
}

// One full-velocity saw, 0.5 s settle then 0.5 s measured: RMS (dB) and peak.
static float voice_level_db(float filter_knob, uint8_t note, float *peak) {
    ps_synth_t s;
    ps_init(&s, FS);
    ps_set_filter_knob(&s, filter_knob);
    s.s_filter_knob = filter_knob;
    ps_note_on(&s, note, 127);
    double acc = 0;
    *peak = 0;
    int n_total = (int)FS;
    for (int n = 0; n < n_total; n++) {
        float y = ps_process(&s);
        if (n >= n_total / 2) {
            acc += (double)y * y;
            *peak = fmaxf(*peak, fabsf(y));
        }
    }
    return 10.0f * log10f((float)(acc / (n_total / 2)));
}

static void test_output_level(void) {
    float peak;
    float dry = voice_level_db(0.0f, 57, &peak);
    printf("one voice, filter open: %.1f dB RMS, peak %.2f\n", dry, peak);
    CHECK(peak > 0.75f, "full-velocity voice peak %.2f (want near full scale)", peak);
    // Cutoff above the note's harmonics of interest: the level must hold.
    for (int i = 1; i <= 6; i++) {
        float x = i / 10.0f;
        float db = voice_level_db(x, 57, &peak);
        printf("  knob %.1f: %+.1f dB vs open\n", x, db - dry);
        CHECK(db - dry > -4.0f, "filter knob %.1f drops the level %.1f dB", x, db - dry);
    }
}

// Chords of n full-velocity notes (random notes 36..84, a few chords each, all
// waveforms, filter open and resonant): worst limiter gain reduction, and the
// chord RMS against one voice. The polyphony gain should leave the limiter
// almost idle.
static void test_polyphony_level(void) {
    srand(1);
    float one_db = 0.0f;
    printf("notes  rms_dB(vs 1)  limiter_dB open / resonant  limited_%% open / resonant\n");
    for (int n = 1; n <= PS_VOICES; n++) {
        float worst[2] = {0.0f, 0.0f};
        double acc = 0.0, limited[2] = {0.0, 0.0}, count = 0.0;
        for (int trial = 0; trial < 16; trial++) {
            ps_synth_t s;
            ps_init(&s, FS);
            ps_set_wave_now(&s, (ps_wave_t)(trial % PS_WAVE_COUNT));
            float knob = (trial & 1) ? 0.45f : 0.0f;
            ps_set_filter_knob(&s, knob);
            s.s_filter_knob = knob;
            for (int i = 0; i < n; i++) ps_note_on(&s, (uint8_t)(36 + rand() % 49), 127);
            for (int k = 0; k < (int)(FS * 0.5f); k++) {
                float y = ps_process(&s);
                CHECK(isfinite(y) && fabsf(y) <= 1.0f, "output out of range");
                if (k < (int)(FS * 0.1f)) continue;
                if (!(trial & 1)) { acc += (double)y * y; count += 1.0; }
                if (s.limit_gain < 0.97f) limited[trial & 1] += 1.0;
                worst[trial & 1] = fmaxf(worst[trial & 1], -20.0f * log10f(s.limit_gain));
            }
        }
        float db = 10.0f * log10f((float)(acc / count));
        if (n == 1) one_db = db;
        float pct0 = (float)(100.0 * limited[0] / (8 * FS * 0.4f));
        float pct1 = (float)(100.0 * limited[1] / (8 * FS * 0.4f));
        printf("%5d  %+11.1f  %10.1f / %4.1f  %14.1f / %4.1f\n", n, db - one_db, worst[0], worst[1], pct0, pct1);
        CHECK(worst[0] < 2.0f && worst[1] < 5.0f, "%d notes: limiter takes %.1f / %.1f dB", n, worst[0], worst[1]);
        CHECK(db - one_db < 9.0f, "%d notes much louder than one (%.1f dB)", n, db - one_db);
    }
}

// Every waveform: in range, level within a few dB of the saw, and the
// wavetable mip level keeps a high note's harmonics under Nyquist.
static void test_waves(void) {
    float saw_db = 0.0f;
    for (int w = 0; w < PS_WAVE_COUNT; w++) {
        ps_synth_t s;
        ps_init(&s, FS);
        ps_set_wave_now(&s, (ps_wave_t)w);
        ps_note_on(&s, 57, 127);
        double acc = 0;
        for (int n = 0; n < (int)FS; n++) {
            float y = ps_process(&s);
            if (n >= (int)FS / 2) acc += (double)y * y;
        }
        float db = 10.0f * log10f((float)(acc / (FS / 2)));
        if (w == 0) saw_db = db;
        printf("wave %d %-6s %+.1f dB vs saw\n", w, ps_wave_name((ps_wave_t)w), db - saw_db);
        CHECK(fabsf(db - saw_db) < 4.0f, "wave %d level %.1f dB off the saw", w, db - saw_db);
    }
    for (int note = 0; note < 128; note++) {
        ps_synth_t s;
        ps_init(&s, FS);
        ps_note_on(&s, (uint8_t)note, 127);
        float hz = s.voices[0].inc * FS;
        int top = PS_WT_TOP_HARMONICS >> s.voices[0].mip;
        CHECK(top * hz <= 24000.0f || s.voices[0].mip == PS_WT_LEVELS - 1,
              "note %d: %d harmonics x %.0f Hz alias", note, top, hz);
    }
    // A waveform change mid-note crossfades: no step bigger than the waves' own.
    ps_synth_t s;
    ps_init(&s, FS);
    ps_note_on(&s, 45, 127);
    for (int n = 0; n < 4410; n++) ps_process(&s);
    float prev = ps_process(&s), worst = 0.0f;
    for (int w = 1; w < PS_WAVE_COUNT; w++) {
        ps_set_wave(&s, (ps_wave_t)w);
        for (int n = 0; n < 2205; n++) {
            float y = ps_process(&s);
            if (s.wave_fade < 1.0f) worst = fmaxf(worst, fabsf(y - prev));
            prev = y;
        }
        CHECK(s.wave == w && s.wave_fade == 1.0f, "crossfade to wave %d finished", w);
    }
    printf("waveform crossfade: largest step %.3f\n", worst);
    CHECK(worst < 0.9f, "waveform change steps %.3f (a click)", worst);
}

int main(void) {
    test_filter_map();
    test_ladder_response();
    test_ladder_decays();
    test_envelope();
    test_voices();
    test_sustain();
    test_level_and_tuning();
    test_output_level();
    test_waves();
    test_polyphony_level();
    if (failures) {
        printf("%d check(s) FAILED\n", failures);
        return 1;
    }
    printf("All polysynth DSP tests passed.\n");
    return 0;
}
