// Host tests for the 32bit fxrack: BM comb / all-pass / classic reverb, the hall
// reverb and the fxrack app's audio path, with the board drivers stubbed.

#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "apps/bm_app_fxrack.h"
#include "audio/bm_all_pass_filter.h"
#include "audio/bm_classic_reverb.h"
#include "audio/bm_comb_filter.h"
#include "audio/bm_hall_reverb.h"
#include "bm_audio.h"
#include "bm_midi.h"
#include "lib/bm_motion_recorder.h"

static int failures = 0;

#define CHECK(cond, ...)                          \
    do {                                          \
        if (!(cond)) {                            \
            printf("FAIL %s:%d: ", __FILE__, __LINE__); \
            printf(__VA_ARGS__);                  \
            printf("\n");                         \
            failures++;                           \
        }                                         \
    } while (0)

// Driver stubs used by bm_app_fxrack.c.
static float led_level = -1.0f;
static int64_t now_us = 1000000;
int64_t esp_timer_get_time(void) { return now_us; }
void bm_set_led_brightness(float level) { led_level = level; }

static void test_comb(void) {
    bm_comb_filter_t c;
    bm_comb_filter_init(&c, 100, 0.5f);
    c.delay_length.smoothing_factor = 0.0f;
    c.feedback.smoothing_factor = 0.0f;
    bm_param_set(&c.delay_length, 10.0f);
    float y[40];
    for (int i = 0; i < 40; i++) y[i] = bm_comb_filter_process(&c, i == 0 ? 1.0f : 0.0f);
    // Impulse returns after 10 samples, then x0.5 every 10.
    CHECK(fabsf(y[10] - 1.0f) < 1e-6f && fabsf(y[20] - 0.5f) < 1e-6f && fabsf(y[30] - 0.25f) < 1e-6f,
          "comb echoes %f %f %f", y[10], y[20], y[30]);
    CHECK(y[0] == 0.0f && y[9] == 0.0f && y[11] == 0.0f, "comb silent between echoes");
    bm_comb_filter_destroy(&c);
}

static void test_all_pass(void) {
    // Unity energy gain is the all-pass property; ASan checks the buffer size.
    bm_all_pass_filter_t a;
    bm_all_pass_filter_init(&a, 56, 0.8f);
    double energy = 0.0;
    for (int i = 0; i < 20000; i++) {
        float y = bm_all_pass_filter_process(&a, i == 0 ? 1.0f : 0.0f);
        energy += (double)y * y;
    }
    CHECK(fabs(energy - 1.0) < 1e-3, "all-pass energy %f", energy);
    bm_all_pass_filter_destroy(&a);
}

static double rms(const float *x, int n) {
    double s = 0.0;
    for (int i = 0; i < n; i++) s += (double)x[i] * x[i];
    return sqrt(s / n);
}

static void test_reverb_rt60(void) {
    bm_classic_reverb_t r;
    bm_classic_reverb_init(&r);
    bm_classic_reverb_set_rt60(&r, 1.0f);
    // Let the feedback smoothing settle before the impulse.
    for (int i = 0; i < 2000; i++) bm_classic_reverb_process(&r, 0.0f);
    const int n = bm_SAMPLE_RATE * 2;
    float *y = malloc(sizeof(float) * n);
    for (int i = 0; i < n; i++) y[i] = bm_classic_reverb_process(&r, i == 0 ? 1.0f : 0.0f);
    const int w = 2205;  // 50 ms windows
    double early = rms(y + 2205, w), late = rms(y + bm_SAMPLE_RATE + 2205, w);
    double drop_db = 20.0 * log10(early / late);
    printf("reverb rt60 1 s: %.1f dB drop over 1 s\n", drop_db);
    CHECK(drop_db > 50.0 && drop_db < 70.0, "rt60 1 s drop %.1f dB", drop_db);
    free(y);
    bm_classic_reverb_destroy(&r);
}

// T30 (RT60 from the -5..-35 dB part of the Schroeder curve), seconds.
static double t30(const float *h, int n) {
    double *e = malloc(sizeof(double) * n);
    double acc = 0.0;
    for (int i = n - 1; i >= 0; i--) {
        acc += (double)h[i] * h[i];
        e[i] = acc;
    }
    int i5 = -1, i35 = -1;
    for (int i = 0; i < n; i++) {
        double db = 10.0 * log10(e[i] / e[0] + 1e-30);
        if (i5 < 0 && db <= -5.0) i5 = i;
        if (db <= -35.0) {
            i35 = i;
            break;
        }
    }
    free(e);
    if (i5 < 0 || i35 <= i5) return -1.0;
    return 60.0 / 30.0 * (i35 - i5) / (double)bm_SAMPLE_RATE;
}

static float *hall_ir(bm_hall_reverb_t *r, float rt60, int n) {
    bm_hall_reverb_set_rt60(r, rt60);
    for (int i = 0; i < 2 * bm_SAMPLE_RATE; i++) bm_hall_reverb_process(r, 0.0f);  // glide, flush
    float *y = malloc(sizeof(float) * n);
    for (int i = 0; i < n; i++) y[i] = bm_hall_reverb_process(r, i == 0 ? 1.0f : 0.0f);
    return y;
}

static void test_hall_reverb(void) {
    static bm_hall_reverb_t r;
    bm_hall_reverb_init(&r);

    // Decay at low/mid frequencies follows the setting; the treble decays faster.
    const float settings[] = {0.3f, 1.0f, 4.0f, 20.0f};
    for (int k = 0; k < 4; k++) {
        float rt = settings[k];
        int n = (int)(bm_SAMPLE_RATE * (rt * 1.2f + 0.5f));
        float *y = hall_ir(&r, rt, n);
        // Low/mid: two one-pole low passes at ~800 Hz.
        float *lo = malloc(sizeof(float) * n);
        float a = 0.0f, b = 0.0f;
        for (int i = 0; i < n; i++) {
            a += (y[i] - a) * 0.107f;
            b += (a - b) * 0.107f;
            lo[i] = b;
        }
        double t = t30(lo, n);
        free(lo);
        // Treble: first difference (+6 dB/oct) weights the 5..20 kHz band.
        float *d = malloc(sizeof(float) * n);
        d[0] = y[0];
        for (int i = 1; i < n; i++) d[i] = y[i] - y[i - 1];
        double t_hf = t30(d, n);
        printf("hall rt60 %.1f s: T30 < 800 Hz %.2f s, treble %.2f s\n", rt, t, t_hf);
        CHECK(t > rt * 0.85 && t < rt * 1.15, "hall T30 %.2f for %.1f", t, rt);
        CHECK(t_hf > 0.0 && t_hf < t * 0.8, "hall treble T30 %.2f vs %.2f", t_hf, t);
        free(d);
        free(y);
    }

    // Echo density: a dense tail has ~0.32 of its samples beyond one sigma
    // (Gaussian); the BM classic reverb stays near 0.2. 20 ms windows, 0.1..0.5 s.
    float *y = hall_ir(&r, 4.0f, bm_SAMPLE_RATE / 2);
    double ned_sum = 0.0;
    int windows = 0;
    for (int w0 = bm_SAMPLE_RATE / 10; w0 + 882 <= bm_SAMPLE_RATE / 2; w0 += 882, windows++) {
        double var = 0.0;
        for (int i = 0; i < 882; i++) var += (double)y[w0 + i] * y[w0 + i];
        double sd = sqrt(var / 882);
        int outside = 0;
        for (int i = 0; i < 882; i++) outside += fabs(y[w0 + i]) > sd;
        ned_sum += outside / 882.0 / 0.3173;
    }
    printf("hall echo density 0.1..0.5 s: %.2f\n", ned_sum / windows);
    CHECK(ned_sum / windows > 0.85, "hall echo density %.2f", ned_sum / windows);
    free(y);

    // Clamped settings; loud noise at the longest decay stays bounded and finite.
    bm_hall_reverb_set_rt60(&r, 100.0f);
    CHECK(r.rt60 == BM_HALL_REVERB_RT60_MAX, "rt60 clamp high");
    bm_hall_reverb_set_rt60(&r, 0.0f);
    CHECK(r.rt60 == BM_HALL_REVERB_RT60_MIN, "rt60 clamp low");
    bm_hall_reverb_set_rt60(&r, 20.0f);
    uint32_t seed = 1;
    float peak = 0.0f;
    bool finite = true;
    for (int i = 0; i < bm_SAMPLE_RATE * 30; i++) {
        seed = seed * 1664525u + 1013904223u;
        float in = i < bm_SAMPLE_RATE * 20 ? ((float)(seed >> 8) / 8388608.0f - 1.0f) : 0.0f;
        float out = bm_hall_reverb_process(&r, in);
        finite &= isfinite(out);
        if (fabsf(out) > peak) peak = fabsf(out);
    }
    // The wet soft limit keeps even this inside full scale.
    printf("hall 20 s, 20 s of full-scale noise: peak %.3f\n", peak);
    CHECK(finite && peak <= 1.0f, "hall noise peak %.3f", peak);
    bm_hall_reverb_destroy(&r);
}

#define REC_TEST_BLINK_MS 150

// Press and release the MODE button for hold_ms.
static void press(bm_app_t *app, int hold_ms) {
    app->on_button_event(true);
    now_us += (int64_t)hold_ms * 1000;
    app->on_button_event(false);
    now_us += 100000;
}

static void test_recorder(void) {
    static bm_motion_recorder_t rec;
    bm_rec_frame_t f;
    bm_rec_init(&rec);
    CHECK(!bm_rec_clock(&rec, &f) && rec.tick == 0, "LIVE: clock idle");
    CHECK(!bm_rec_set_live_cc(&rec, 24, 5) && bm_rec_set_live_cc(&rec, 23, 5), "CC range 20..23");

    bm_rec_press(&rec);
    CHECK(rec.state == BM_REC_RECORDING, "press -> RECORDING");
    for (int t = 0; t < BM_REC_LOOP_TICKS; t++) {
        bm_rec_set_live_cv(&rec, 0, t / (float)BM_REC_LOOP_TICKS);
        bm_rec_set_live_cv(&rec, 1, 0.5f);
        if (t == 100) bm_rec_set_live_cc(&rec, 20, 64);
        if (t == 200) bm_rec_set_live_cc(&rec, 20, 10);
        CHECK(!bm_rec_clock(&rec, &f), "recording does not play");
    }
    CHECK(rec.state == BM_REC_PLAYBACK, "384 clocks -> PLAYBACK");
    CHECK(bm_rec_owns_cv(&rec) && bm_rec_owns_cc(&rec, 20) && bm_rec_owns_cc(&rec, 23) &&
          !bm_rec_owns_cc(&rec, 21) && !bm_rec_owns_cc(&rec, 22), "owned values");

    // Guard pass: live moves ignored.
    bm_rec_set_live_cv(&rec, 1, 1.0f);
    bool ok = true;
    for (int t = 0; t < BM_REC_LOOP_TICKS; t++) {
        bool play = bm_rec_clock(&rec, &f);
        uint8_t want20 = t < 200 ? 64 : 10;  // back-filled before tick 100
        ok &= play && fabsf(f.cv[0] - t / (float)BM_REC_LOOP_TICKS) < 1e-6f &&
              f.cv[1] == 0.5f && f.cc[0] == want20 && f.cc[1] == BM_REC_CC_UNSET && f.cc[3] == 5;
    }
    CHECK(ok, "guard pass replays the take");

    // After the guard: offsets from the latched reference (CV2 1.0, CC 20 = 10).
    bm_rec_set_live_cv(&rec, 1, 0.8f);  // -0.2
    bm_rec_set_live_cc(&rec, 20, 0);    // -10
    bm_rec_clock(&rec, &f);
    CHECK(fabsf(f.cv[1] - 0.3f) < 1e-6f && f.cc[0] == 54 && f.cv[0] == 0.0f, "offset cv2 %f cc20 %u", f.cv[1], f.cc[0]);
    bm_rec_set_live_cv(&rec, 0, 0.0f);  // -1 on CV1 clamps at 0
    bm_rec_clock(&rec, &f);
    CHECK(f.cv[0] == 0.0f, "offset clamps");

    bm_rec_start(&rec);
    CHECK(rec.tick == 0, "MIDI Start rewinds");
    bm_rec_press(&rec);
    CHECK(rec.state == BM_REC_LIVE && !bm_rec_owns_cv(&rec) && !bm_rec_owns_cc(&rec, 20), "press -> LIVE");

    // Abort a take part-way.
    bm_rec_press(&rec);
    for (int t = 0; t < 100; t++) bm_rec_clock(&rec, &f);
    bm_rec_press(&rec);
    CHECK(rec.state == BM_REC_LIVE && !bm_rec_clock(&rec, &f), "abort -> LIVE");
}

// Runs the app for n frames of a constant input; returns the last output frame.
static void run_app(bm_app_t *app, int frames, int16_t in_l, int16_t in_r, int16_t *out_l, int16_t *out_r) {
    int16_t in[128], out[128];
    for (int i = 0; i < 128; i += 2) {
        in[i] = in_l;
        in[i + 1] = in_r;
    }
    for (int f = 0; f < frames; f += 64) {
        app->process_audio(128, in, out);
    }
    *out_l = out[126];
    *out_r = out[127];
}

static void test_app(void) {
    bm_app_t app = bm_load_app_fxrack();
    bm_app_host_t host = {.sample_rate = bm_SAMPLE_RATE};
    app.init(host);
    app.on_midi_bpm(120);
    app.on_cv_change(0, 0.0f);
    app.on_cv_change(1, 0.0f);

    // Reverb mix 0, delay feedback 0: both outputs follow the input (delayed).
    int16_t l, r;
    run_app(&app, 44100 * 3, 10000, -8000, &l, &r);
    CHECK(abs(l - 10000) <= 2 && abs(r + 8000) <= 2, "dry path L %d R %d", l, r);

    // MIDI clock below 15 BPM: the half-beat range (3 s at 10 BPM) is clamped to
    // the 2 s buffer, so a burst comes back after ~2 s (unclamped it wrapped to ~1 s).
    app.on_cv_change(0, 1.0f);
    app.on_midi_bpm(10);
    run_app(&app, 44100 * 6, 0, 0, &l, &r);  // let the delay time glide, clear the buffer
    run_app(&app, 64, 10000, 0, &l, &r);
    int first_echo = -1;
    for (int block = 0; block < 44100 * 3 / 64 && first_echo < 0; block++) {
        int16_t in[128] = {0}, out[128];
        app.process_audio(128, in, out);
        for (int i = 0; i < 128; i += 2) {
            if (abs(out[i]) > 1000) {
                first_echo = (block + 1) * 64 + i / 2;
                break;
            }
        }
    }
    printf("slow BPM echo after %.3f s\n", first_echo / 44100.0);
    CHECK(first_echo > 88000 && first_echo < 88300, "slow BPM echo at %d samples", first_echo);

    // Reverb fully wet: the left output is the hall reverb. It blocks DC (90 Hz
    // high pass), so a constant input dies away; a 1 s burst of a 441 Hz square
    // rings on after the input stops (CC 20 = 64: ~2.5 s decay).
    app.on_midi_bpm(120);
    app.on_midi_cc(0, BM_MCC_BANK_A_CV2, 127);
    app.on_midi_cc(0, BM_MCC_BANK_A_CV1, 64);
    run_app(&app, 44100 * 4, 4000, 0, &l, &r);
    CHECK(abs(l) < 20, "wet reverb blocks DC: %d", l);
    for (int block = 0; block < 44100 / 64; block++) {
        int16_t in[128], out[128];
        for (int i = 0; i < 128; i += 2) {
            in[i] = ((block * 64 + i / 2) / 50) % 2 ? 8000 : -8000;
            in[i + 1] = 0;
        }
        app.process_audio(128, in, out);
    }
    int wet_peak = 0;
    for (int block = 0; block < 44100 / 2 / 64; block++) {  // 0..0.5 s after the burst
        int16_t in[128] = {0}, out[128];
        app.process_audio(128, in, out);
        for (int i = 0; i < 128; i += 2) {
            if (abs(out[i]) > wet_peak) wet_peak = abs(out[i]);
        }
    }
    printf("wet reverb tail peak after a 1 s burst: %d\n", wet_peak);
    CHECK(wet_peak > 1000 && wet_peak < 32767, "wet reverb tail peak %d", wet_peak);

    app.on_midi_cc(0, BM_MCC_BANK_A_CV2, 0);  // dry delay on the left again
    bm_app_fxrack_update(0);
    CHECK(led_level == 0.0f, "LIVE LED off: %f", led_level);
    // Contact bounce (edges within 30 ms) is not a press.
    app.on_button_event(true);
    now_us += 5000;
    app.on_button_event(false);
    now_us += 5000;
    app.on_button_event(true);
    now_us += 100000;
    app.on_button_event(false);
    now_us += 100000;
    bm_app_fxrack_update(0);
    CHECK(led_level == 1.0f, "debounced press starts recording (LED %f)", led_level);
    bm_app_fxrack_update(REC_TEST_BLINK_MS);
    CHECK(led_level == 0.0f, "recording LED blinks");
    press(&app, 50);  // abort
    bm_app_fxrack_update(0);
    CHECK(led_level == 0.0f, "abort back to LIVE");

    // Record a CV1 ramp over 4 bars: delay time follows the recording in PLAYBACK.
    app.on_cv_change(1, 0.0f);
    press(&app, 50);
    for (int t = 0; t < BM_REC_LOOP_TICKS; t++) {
        app.on_cv_change(0, t < BM_REC_LOOP_TICKS / 2 ? 0.0f : 1.0f);
        if (t == 10) app.on_midi_cc(0, BM_MCC_BANK_A_CV3, 100);
        bm_app_fxrack_on_midi_realtime(0xF8);
    }
    bm_app_fxrack_update(0);
    CHECK(led_level == 1.0f, "PLAYBACK LED solid");
    // Live CV ignored in PLAYBACK; the first half of the loop plays CV1 = 0.
    app.on_cv_change(0, 1.0f);
    bm_app_fxrack_on_midi_realtime(0xF8);
    run_app(&app, 44100 * 2, 0, 0, &l, &r);
    // CV1 = 0 is a 10-sample delay: the burst is out by the block's end (the live
    // CV1 = 1, 250 ms, would still be silent).
    run_app(&app, 64, 10000, 0, &l, &r);
    CHECK(abs(l - 10000) <= 50, "playback CV1 = 0 (out %d)", l);

    // CC 22 recorded from tick 10, back-filled: live CC 22 is ignored in PLAYBACK.
    app.on_midi_cc(0, BM_MCC_BANK_A_CV3, 0);
    press(&app, 50);  // back to LIVE: live CV1 (1.0) and CC 22 (0) re-applied
    bm_app_fxrack_update(0);
    CHECK(led_level == 0.0f, "PLAYBACK -> LIVE");

    app.destroy();
}

int main(void) {
    test_comb();
    test_all_pass();
    test_reverb_rt60();
    test_hall_reverb();
    test_recorder();
    test_app();
    if (failures) {
        printf("%d failure(s)\n", failures);
        return 1;
    }
    printf("all fxrack tests passed\n");
    return 0;
}
