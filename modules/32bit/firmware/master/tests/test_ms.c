// Host tests for the 32bit master chain: ../main/src/ms_dsp.c, ms_params.c, ms_proto.c.
#define _GNU_SOURCE
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ms_ctl.h"
#include "ms_dsp.h"
#include "ms_params.h"
#include "ms_proto.h"

#define FS 44100.0f
#define BLOCK 16

static int failures = 0;
static int checks = 0;

#define CHECK(cond, ...)                             \
    do {                                             \
        checks++;                                    \
        if (!(cond)) {                               \
            failures++;                              \
            printf("FAIL %s:%d: ", __FILE__, __LINE__); \
            printf(__VA_ARGS__);                     \
            printf("\n");                            \
        }                                            \
    } while (0)

#define NEAR(a, b, tol) (fabs((double)(a) - (double)(b)) <= (double)(tol))

static float db(float lin) {
    return 20.0f * log10f(lin + 1e-30f);
}

static uint32_t rng_state = 12345;
static float rnd(void) {  // -1..1
    rng_state = rng_state * 1664525u + 1013904223u;
    return (float)(int32_t)rng_state / 2147483648.0f;
}

// ------------------------------------------------------------ chain helpers

static ms_dsp_t dsp;
static float P[MS_P_COUNT];

// Everything off / neutral: the chain is then kick + mix.
static void neutral(void) {
    ms_params_defaults(P);
    P[MS_P_K_FLT_ON] = 0;
    P[MS_P_K_LIM_ON] = 0;
    P[MS_P_M_FLT_ON] = 0;
    P[MS_P_MB_ON] = 0;
    P[MS_P_PAR_ON] = 0;
    P[MS_P_GLUE_ON] = 0;
    P[MS_P_O_FLT_ON] = 0;
    P[MS_P_LIM_ON] = 0;
    P[MS_P_LIM_AUTO] = 0;  // the tests set the release they want
}

static void start(void) {
    ms_coefs_t c;
    ms_coefs_from_params(P, FS, BLOCK, &c);
    ms_dsp_init(&dsp, &c);
}

static void update(void) {
    ms_coefs_t c;
    ms_coefs_from_params(P, FS, BLOCK, &c);
    ms_dsp_set_coefs(&dsp, &c);
}

// Runs the chain over whole buffers (any length) in BLOCK-frame calls.
static void run(const float *k, const float *m, float *out, int n) {
    static const float zeros[BLOCK] = {0};
    for (int i = 0; i < n; i += BLOCK) {
        int len = n - i < BLOCK ? n - i : BLOCK;
        ms_dsp_process(&dsp, k ? k + i : zeros, m ? m + i : zeros, out + i, len);
    }
}

#define N_MAX (4 * 44100)
static float buf_k[N_MAX], buf_m[N_MAX], buf_o[N_MAX];

static void sine(float *x, int n, float freq, float amp) {
    for (int i = 0; i < n; i++) x[i] = amp * sinf(2.0f * (float)M_PI * freq * (float)i / FS);
}

static float rms(const float *x, int from, int to) {
    double s = 0;
    for (int i = from; i < to; i++) s += (double)x[i] * x[i];
    return (float)sqrt(s / (to - from));
}

static float peak(const float *x, int from, int to) {
    float pk = 0;
    for (int i = from; i < to; i++) {
        if (fabsf(x[i]) > pk) pk = fabsf(x[i]);
    }
    return pk;
}

// Steady-state gain in dB of the chain for a sine on the mix (or kick) input.
static float gain_at(float freq, float amp, bool on_kick) {
    int n = 44100;
    sine(buf_k, n, freq, amp);
    run(on_kick ? buf_k : NULL, on_kick ? NULL : buf_k, buf_o, n);
    return db(rms(buf_o, n / 2, n) / (amp * 0.70710678f));
}

// ------------------------------------------------------------ tests

static void test_fast_math(void) {
    float worst_log = 0, worst_exp = 0;
    for (float x = 1e-9f; x < 100.0f; x *= 1.0137f) {
        float e = fabsf(ms_fast_log2(x) - log2f(x)) * 6.0206f;
        if (e > worst_log) worst_log = e;
    }
    for (float x = -20.0f; x < 6.0f; x += 0.00731f) {
        float e = fabsf(db(ms_fast_exp2(x) / exp2f(x)));
        if (e > worst_exp) worst_exp = e;
    }
    CHECK(worst_log < 0.006f, "fast log2 error %.4f dB", worst_log);
    CHECK(worst_exp < 0.0015f, "fast exp2 error %.5f dB", worst_exp);
    CHECK(ms_fast_log2(1.0f) == 0.0f && ms_fast_exp2(0.0f) == 1.0f, "exact at 1 / 0");
    printf("fast math: log2 within %.4f dB, exp2 within %.5f dB\n", worst_log, worst_exp);
}

// One cut of a filter on: the device's switch on, every other cut off.
static void one_cut(int flt_on, int cut_on, float f, int slope, float q) {
    neutral();
    P[MS_P_K_FLT_LC_ON] = P[MS_P_K_FLT_HC_ON] = 0;
    P[MS_P_M_FLT_LC_ON] = P[MS_P_M_FLT_HC_ON] = 0;
    P[MS_P_O_FLT_LC_ON] = P[MS_P_O_FLT_HC_ON] = 0;
    P[flt_on] = 1;
    P[cut_on] = 1;
    P[cut_on + 1] = f;
    P[cut_on + 2] = q;
    P[cut_on + 3] = (float)slope;
}

static void test_filters(void) {
    // Kick low cut: -3 dB at the set frequency, 12 / 24 / 48 dB per octave below it.
    static const float want_below[] = {-12.3f, -24.1f, -48.2f};
    for (int slope = 0; slope < 3; slope++) {
        one_cut(MS_P_K_FLT_ON, MS_P_K_FLT_LC_ON, 25, slope, 0.7071f);
        start();
        float at = gain_at(25, 0.5f, true);
        start();
        float below = gain_at(12.5f, 0.5f, true);
        start();
        float pass = gain_at(200, 0.5f, true);
        CHECK(NEAR(at, -3.01f, 0.15f), "low cut %d: %.2f dB at 25 Hz", slope, at);
        CHECK(NEAR(below, want_below[slope], 0.5f), "low cut %d: %.2f dB an octave below", slope, below);
        CHECK(NEAR(pass, 0.0f, 0.05f), "low cut %d: %.3f dB at 200 Hz", slope, pass);
        printf("kick low cut 25 Hz, %d dB/oct: %.2f dB at 25 Hz, %.2f dB at 12.5 Hz, %.3f dB at 200 Hz\n",
               12 << slope, at, below, pass);
    }
    // The lowest setting still works in single precision.
    one_cut(MS_P_K_FLT_ON, MS_P_K_FLT_LC_ON, 10, 0, 0.7071f);
    start();
    float at10 = gain_at(10, 0.5f, true);
    CHECK(NEAR(at10, -3.01f, 0.2f), "10 Hz low cut: %.2f dB at 10 Hz", at10);

    // Resonance: a 12 dB/oct cut peaks by Q at its frequency; on 24 dB/oct it lifts
    // the sharpest section (Butterworth x Q / 0.707).
    one_cut(MS_P_M_FLT_ON, MS_P_M_FLT_LC_ON, 1000, 0, 2.0f);
    start();
    float q2 = gain_at(1000, 0.1f, false);
    CHECK(NEAR(q2, 6.02f, 0.1f), "low cut Q 2: %.2f dB at 1 kHz", q2);
    one_cut(MS_P_M_FLT_ON, MS_P_M_FLT_HC_ON, 1000, 1, 2.0f);
    start();
    float q24 = gain_at(1000, 0.1f, false);
    float want24 = 20.0f * log10f(0.54119610f * 1.30656296f * 2.0f * 1.41421356f);
    CHECK(NEAR(q24, want24, 0.15f), "high cut 24 dB/oct, Q 2: %.2f dB at 1 kHz, want %.2f", q24, want24);

    // Mix and master cuts.
    one_cut(MS_P_M_FLT_ON, MS_P_M_FLT_LC_ON, 80, 0, 0.7071f);
    start();
    float m80 = gain_at(80, 0.5f, false);
    CHECK(NEAR(m80, -3.01f, 0.1f), "mix low cut: %.2f dB at 80 Hz", m80);

    one_cut(MS_P_O_FLT_ON, MS_P_O_FLT_HC_ON, 8000, 1, 0.7071f);
    start();
    float h8 = gain_at(8000, 0.5f, false);
    start();
    float h16 = gain_at(16000, 0.5f, false);
    CHECK(NEAR(h8, -3.01f, 0.1f), "high cut: %.2f dB at 8 kHz", h8);
    CHECK(h16 < -24.0f, "high cut 24 dB/oct: %.1f dB at 16 kHz", h16);
    one_cut(MS_P_O_FLT_ON, MS_P_O_FLT_LC_ON, 30, 0, 0.7071f);
    start();
    float l30 = gain_at(30, 0.5f, false);
    CHECK(NEAR(l30, -3.01f, 0.1f), "main low cut: %.2f dB at 30 Hz", l30);

    // Both cuts at once (a band pass), and the device switch.
    one_cut(MS_P_O_FLT_ON, MS_P_O_FLT_LC_ON, 100, 1, 0.7071f);
    P[MS_P_O_FLT_HC_ON] = 1;
    P[MS_P_O_FLT_HC_F] = 5000;
    start();
    float mid = gain_at(700, 0.5f, false);
    start();
    float lo = gain_at(50, 0.5f, false);
    start();
    float hi = gain_at(10000, 0.5f, false);
    CHECK(NEAR(mid, 0.0f, 0.05f) && lo < -20.0f && hi < -10.0f, "band pass: %.2f / %.1f / %.1f dB", mid, lo, hi);
    P[MS_P_O_FLT_ON] = 0;
    start();
    float off = gain_at(50, 0.5f, false);
    CHECK(NEAR(off, 0.0f, 0.01f), "filter switched off: %.3f dB", off);
}

static void test_crossover_flat(void) {
    // Multiband on with ratio 1 in every band: the three bands must add up flat.
    neutral();
    P[MS_P_MB_ON] = 1;
    P[MS_P_MB_SC] = 1;
    P[MS_P_MB_LO_RATIO] = P[MS_P_MB_MID_RATIO] = P[MS_P_MB_HI_RATIO] = 1;
    static const float freqs[] = {30, 60, 100, 120, 150, 300, 1000, 2000, 2500, 3200, 6000, 12000, 18000};
    float worst = 0;
    for (size_t i = 0; i < sizeof(freqs) / sizeof(freqs[0]); i++) {
        start();
        float g = gain_at(freqs[i], 0.25f, false);
        if (fabsf(g) > worst) worst = fabsf(g);
    }
    CHECK(worst < 0.05f, "band sum off flat by %.3f dB", worst);
    printf("multiband: three bands add up flat within %.3f dB (30 Hz .. 18 kHz)\n", worst);

    // Each solo band peaks in its own range.
    static const float probe[3] = {50, 600, 8000};
    for (int b = 0; b < 3; b++) {
        P[MS_P_MB_SOLO] = (float)(b + 1);
        for (int f = 0; f < 3; f++) {
            start();
            float g = gain_at(probe[f], 0.25f, false);
            if (f == b) CHECK(g > -1.0f, "solo band %d at %.0f Hz: %.1f dB", b, probe[f], g);
            else CHECK(g < -18.0f, "solo band %d leaks %.1f dB at %.0f Hz", b, g, probe[f]);
        }
    }
}

static void test_compressor_curve(void) {
    // Parallel compressor alone: sends open, dry mix muted, so out = compressed signal.
    neutral();
    P[MS_P_PAR_ON] = 1;
    P[MS_P_M_LVL] = -60;
    P[MS_P_K_LVL] = -60;
    P[MS_P_PAR_SEND_M] = 0;
    P[MS_P_PAR_MAKEUP] = 0;
    P[MS_P_PAR_RET] = 0;
    P[MS_P_PAR_THR] = -30;
    P[MS_P_PAR_RATIO] = 4;
    P[MS_P_PAR_ATT] = 1;
    P[MS_P_PAR_REL] = 2000;  // long release: the gain sits at the peak value
    // input peak level -> expected gain: over x (1 - 1/ratio), knee 6 dB around -30
    static const float levels[] = {-50, -36, -30, -24, -12, 0};
    for (size_t i = 0; i < sizeof(levels) / sizeof(levels[0]); i++) {
        start();
        float over = levels[i] + 30.0f, want;
        if (over <= -3) want = 0;
        else if (over >= 3) want = 0.75f * over;
        else want = 0.75f * (over + 3) * (over + 3) / 12.0f;
        float g = gain_at(1000, powf(10.0f, levels[i] / 20.0f), false);
        CHECK(NEAR(g, -want, 0.35f), "comp curve at %.0f dB: gain %.2f, want %.2f", levels[i], g, -want);
    }
    printf("compressor curve (thr -30, 4:1, 6 dB knee): within 0.35 dB at -50 .. 0 dB\n");

    // Attack and release: a step from -40 to -10 dB and back.
    P[MS_P_PAR_ATT] = 10;
    P[MS_P_PAR_REL] = 100;
    P[MS_P_PAR_RATIO] = 20;
    start();
    int n = 3 * 44100 / 2, a = 44100 / 2, b = 44100;
    for (int i = 0; i < n; i++) {
        float amp = (i >= a && i < b) ? 0.316f : 0.01f;
        buf_m[i] = amp * sinf(2.0f * (float)M_PI * 3000.0f * (float)i / FS);
    }
    run(NULL, buf_m, buf_o, n);
    // Gain reduction from the output envelope (short windows of the 3 kHz sine).
    float final_gr = db(0.316f * 0.7071f / rms(buf_o, b - 2000, b));
    float t63 = -1, t_rel = -1;
    for (int i = a; i < b; i += 15) {
        float gr = db(0.316f * 0.7071f / rms(buf_o, i, i + 15 * 3));
        if (gr >= 0.632f * final_gr) {
            t63 = (float)(i - a) * 1000.0f / FS;
            break;
        }
    }
    // After the step down the detector sees -40 dB: the reduction falls back.
    for (int i = b; i < n - 45; i += 15) {
        float gr = db(0.01f * 0.7071f / rms(buf_o, i, i + 15 * 3));
        if (gr <= 0.368f * final_gr) {
            t_rel = (float)(i - b) * 1000.0f / FS;
            break;
        }
    }
    CHECK(final_gr > 15.0f, "step: reduction %.1f dB", final_gr);
    CHECK(t63 > 5.0f && t63 < 16.0f, "attack 10 ms: 63 %% after %.1f ms", t63);
    CHECK(t_rel > 80.0f && t_rel < 125.0f, "release 100 ms: 37 %% after %.1f ms", t_rel);
    printf("compressor timing: attack 10 ms -> 63 %% after %.1f ms, release 100 ms -> 37 %% after %.1f ms\n",
           t63, t_rel);
}

static void make_kick(float *x, int n, int period, float amp) {
    // 55 Hz body with a short click, 150 ms long.
    for (int i = 0; i < n; i++) {
        int t = i % period;
        float sec = (float)t / FS;
        float body = sinf(2.0f * (float)M_PI * (55.0f * sec + 40.0f * 0.03f * (1.0f - expf(-sec / 0.03f)))) *
                     expf(-sec / 0.06f);
        float click = (t < 60 ? rnd() * (1.0f - (float)t / 60.0f) : 0.0f) * 0.3f;
        x[i] = amp * (body + click);
    }
}

static void test_multiband_duck(void) {
    // A 70 Hz + 4.9 kHz mix, kick every 0.5 s: the low band ducks on each kick and
    // comes back before the next one; the high band (hardly any kick energy) stays.
    neutral();
    P[MS_P_MB_ON] = 1;
    P[MS_P_MB_LO_THR] = -30;
    P[MS_P_MB_LO_RATIO] = 4;
    P[MS_P_MB_LO_ATT] = 1;
    P[MS_P_MB_LO_REL] = 80;
    P[MS_P_MB_MID_ON] = 0;
    P[MS_P_MB_HI_THR] = -10;
    P[MS_P_K_LVL] = -60;  // listen to the mix only
    start();
    int n = 2 * 44100, period = 22050;
    make_kick(buf_k, n, period, 0.7f);
    for (int i = 0; i < n; i++) {
        buf_m[i] = 0.2f * sinf(2.0f * (float)M_PI * 70.0f * (float)i / FS) +
                   0.05f * sinf(2.0f * (float)M_PI * 4900.0f * (float)i / FS);
    }
    run(buf_k, buf_m, buf_o, n);
    // Level of each tone around a point in time (correlation over 1260 samples =
    // 2 cycles of 70 Hz, 140 of 4.9 kHz).
    #define TONE(freq, at, res)                                                \
        do {                                                                   \
            double re = 0, im = 0;                                             \
            int w = 1260;                                                      \
            for (int i = (at); i < (at) + w; i++) {                            \
                double ph = 2.0 * M_PI * (freq) * i / FS;                      \
                re += buf_o[i] * cos(ph);                                      \
                im += buf_o[i] * sin(ph);                                      \
            }                                                                  \
            res = (float)(2.0 * sqrt(re * re + im * im) / w);                  \
        } while (0)
    float lo_hit, lo_late, hi_hit;
    TONE(70.0, period + 441, lo_hit);          // 10..39 ms into the second kick
    TONE(70.0, period + 19000, lo_late);       // just before the third
    TONE(4900.0, period + 441, hi_hit);
    float duck = db(lo_hit / 0.2f), back = db(lo_late / 0.2f), hi = db(hi_hit / 0.05f);
    CHECK(duck < -12.0f, "low band ducks %.1f dB on the kick", duck);
    CHECK(back > -0.5f, "low band back to %.1f dB before the next kick", back);
    CHECK(hi > -0.5f, "high band moved %.1f dB", hi);
    ms_meters_t mt;
    ms_dsp_take_meters(&dsp, &mt);
    CHECK(mt.gr_mb[0] > 12.0f && mt.gr_mb[1] == 0.0f, "meters: low %.1f dB, mid %.1f dB", mt.gr_mb[0], mt.gr_mb[1]);
    printf("multiband sidechain: 70 Hz ducks %.1f dB on the kick, back at %.1f dB after 430 ms; 4.9 kHz %.1f dB\n",
           duck, back, hi);

    // Amount 50 % halves the duck (in dB); sidechain "Self" does not react to the kick.
    P[MS_P_MB_AMOUNT] = 50;
    start();
    run(buf_k, buf_m, buf_o, n);
    float half;
    TONE(70.0, period + 441, half);
    CHECK(NEAR(db(half / 0.2f), 0.5f * duck, 1.5f), "amount 50 %%: %.1f dB vs %.1f dB", db(half / 0.2f), duck);
    P[MS_P_MB_AMOUNT] = 100;
    P[MS_P_MB_SC] = 1;
    P[MS_P_MB_LO_THR] = -6;
    start();
    run(buf_k, buf_m, buf_o, n);
    float self;
    TONE(70.0, period + 441, self);
    CHECK(NEAR(db(self / 0.2f), 0.0f, 0.3f), "self sidechain: %.2f dB", db(self / 0.2f));
    #undef TONE
}

static void test_limiter(void) {
    // Hot noise and bursts: never above the ceiling, at every look-ahead.
    static const float las[] = {0, 0.5f, 1.5f, 5.0f, 0, 1.5f};
    for (size_t l = 0; l < sizeof(las) / sizeof(las[0]); l++) {
        neutral();
        P[MS_P_LIM_AUTO] = l >= 4;
        P[MS_P_LIM_ON] = 1;
        P[MS_P_LIM_CEIL] = -1;
        P[MS_P_LIM_LA] = las[l];
        P[MS_P_LIM_REL] = 30;
        start();
        int n = 44100;
        for (int i = 0; i < n; i++) {
            float env = (i / 3000) % 3 == 0 ? 2.5f : 0.3f;
            buf_m[i] = env * rnd() + (i % 7001 == 0 ? 3.0f : 0.0f);
        }
        run(NULL, buf_m, buf_o, n);
        float pk = peak(buf_o, 0, n), ceil = powf(10.0f, -1.0f / 20.0f);
        CHECK(pk <= ceil * 1.000001f, "limiter %.1f ms: peak %.6f over ceiling %.6f", las[l], pk, ceil);
        CHECK(pk > ceil * 0.98f, "limiter %.1f ms: peak %.4f, expected it to reach the ceiling", las[l], pk);
    }

    // Below the ceiling it is a pure delay of the look-ahead.
    neutral();
    P[MS_P_LIM_ON] = 1;
    P[MS_P_LIM_LA] = 1.5f;
    start();
    int la = (int)(0.0015f * FS + 0.5f), n = 4410;
    for (int i = 0; i < n; i++) buf_m[i] = 0.5f * rnd();
    run(NULL, buf_m, buf_o, n);
    float worst = 0;
    for (int i = la; i < n; i++) {
        float e = fabsf(buf_o[i] - buf_m[i - la]);
        if (e > worst) worst = e;
    }
    CHECK(worst < 1e-6f, "limiter idle: delayed copy differs by %g", worst);

    // The gain moves smoothly into a peak with look-ahead: a 1 kHz sine 6 dB over
    // the ceiling keeps most of its shape (low distortion), unlike with none.
    for (int mode = 0; mode < 2; mode++) {
        neutral();
        P[MS_P_LIM_ON] = 1;
        P[MS_P_LIM_CEIL] = -6;
        P[MS_P_LIM_LA] = mode ? 1.5f : 0.0f;
        P[MS_P_LIM_REL] = 200;
        start();
        n = 44100;
        sine(buf_m, n, 1000, 1.0f);
        run(NULL, buf_m, buf_o, n);
        // Harmonic content: remove the fundamental by projection.
        double re = 0, im = 0, tot = 0;
        for (int i = n / 2; i < n; i++) {
            double ph = 2.0 * M_PI * 1000.0 * i / FS;
            re += buf_o[i] * cos(ph);
            im += buf_o[i] * sin(ph);
            tot += (double)buf_o[i] * buf_o[i];
        }
        double fund = 2.0 * (re * re + im * im) / (n / 2);
        double thd = sqrt(fabs(tot - fund) / tot);
        if (mode) CHECK(thd < 0.01, "limiter look-ahead: THD %.3f %%", thd * 100);
        printf("limiter, 1 kHz sine 6 dB over the ceiling, look-ahead %s: THD %.2f %%\n", mode ? "1.5 ms" : "off",
               thd * 100);
    }

    // Kick limiter gain drives into its ceiling.
    neutral();
    P[MS_P_K_LIM_ON] = 1;
    P[MS_P_K_LIM_GAIN] = 12;
    P[MS_P_K_LIM_CEIL] = -3;
    start();
    n = 44100;
    make_kick(buf_k, n, 22050, 0.5f);
    run(buf_k, NULL, buf_o, n);
    CHECK(NEAR(db(peak(buf_o, 0, n)), -3.0f, 0.05f), "kick limiter peak %.2f dB", db(peak(buf_o, 0, n)));
}

// The order settings move the effects. A resonant cut (Q 6, +15.6 dB at 1 kHz)
// before a limiter is caught by it; after the limiter it lifts the output over
// the ceiling.
static void test_order(void) {
    float pk[2][2];
    for (int strip = 0; strip < 2; strip++) {
        for (int order = 0; order < 2; order++) {
            if (strip == 0) {
                one_cut(MS_P_K_FLT_ON, MS_P_K_FLT_LC_ON, 1000, 0, 6.0f);
                P[MS_P_K_LIM_ON] = 1;
                P[MS_P_K_LIM_CEIL] = -12;
                P[MS_P_K_ORDER] = (float)order;  // 0 filter > limiter, 1 limiter > filter
            } else {
                one_cut(MS_P_O_FLT_ON, MS_P_O_FLT_LC_ON, 1000, 0, 6.0f);
                P[MS_P_LIM_ON] = 1;
                P[MS_P_LIM_CEIL] = -12;
                P[MS_P_O_ORDER] = order ? 5.0f : 0.0f;  // glue > filter > limiter / limiter > filter > glue
            }
            start();
            int n = 22050;
            sine(buf_k, n, 1000, 0.5f);
            run(strip ? NULL : buf_k, strip ? buf_k : NULL, buf_o, n);
            pk[strip][order] = db(peak(buf_o, n / 2, n));
        }
        CHECK(NEAR(pk[strip][0], -12.0f, 0.1f) && pk[strip][1] > -1.0f, "%s order: filter first %.2f dB, limiter first %.2f dB",
              strip ? "master" : "kick", pk[strip][0], pk[strip][1]);
    }
    // Mix: a resonant cut before or after self-keyed dynamics.
    float mix[2];
    for (int order = 0; order < 2; order++) {
        one_cut(MS_P_M_FLT_ON, MS_P_M_FLT_LC_ON, 1000, 0, 6.0f);
        P[MS_P_MB_ON] = 1;
        P[MS_P_MB_SC] = 1;
        P[MS_P_MB_MID_RATIO] = 10;
        P[MS_P_MB_MID_THR] = -30;
        P[MS_P_M_ORDER] = (float)order;
        start();
        mix[order] = gain_at(1000, 0.05f, false);
    }
    CHECK(mix[1] > mix[0] + 6.0f, "mix order: filter first %.2f dB, multiband first %.2f dB", mix[0], mix[1]);
    printf("order: kick %.1f / %.1f dB, master %.1f / %.1f dB, mix %.1f / %.1f dB\n", pk[0][0], pk[0][1], pk[1][0],
           pk[1][1], mix[0], mix[1]);
}

// Auto release: a lone short peak lets go fast; after seconds of limiting the
// gain comes back slower (the slow stage sits at the average reduction).
static void test_auto_release(void) {
    float left[2];
    for (int dense = 0; dense < 2; dense++) {
        neutral();
        P[MS_P_LIM_ON] = 1;
        P[MS_P_LIM_CEIL] = -12;
        P[MS_P_LIM_LA] = 1.5f;
        P[MS_P_LIM_AUTO] = 1;
        P[MS_P_LIM_REL] = 1000;  // not used in auto
        start();
        int burst = dense ? 3 * 44100 : 441;  // 3 s or 10 ms, 12 dB over
        int n = burst + 44100;
        for (int i = 0; i < n; i++) buf_m[i] = i < burst ? 1.0f * (i % 2 ? 1.0f : -1.0f) : 0.0f;
        // a quiet probe tone after the burst shows the gain
        for (int i = burst; i < n; i++) buf_m[i] = 0.01f * sinf(2.0f * (float)M_PI * 1000.0f * (float)i / FS);
        run(NULL, buf_m, buf_o, n);
        int at = burst + (int)(0.15f * FS);
        left[dense] = -db(peak(buf_o, at, at + 441) / 0.01f);
    }
    CHECK(left[0] < 2.0f, "auto release after a 10 ms peak: %.2f dB left at 150 ms", left[0]);
    CHECK(left[1] > 4.0f && left[1] > 3.0f * left[0], "auto release after 3 s: %.2f dB left at 150 ms", left[1]);
    printf("limiter auto release: %.2f dB left 150 ms after a 10 ms peak, %.2f dB after 3 s of limiting\n", left[0],
           left[1]);
}

static void test_latency(void) {
    // An impulse comes out after the two look-aheads, on both inputs.
    neutral();
    P[MS_P_K_LIM_ON] = 1;
    P[MS_P_K_LIM_LA] = 1.0f;
    P[MS_P_LIM_ON] = 1;
    P[MS_P_LIM_LA] = 1.5f;
    ms_coefs_t c;
    ms_coefs_from_params(P, FS, BLOCK, &c);
    int want = (int)(0.001f * FS + 0.5f) + (int)(0.0015f * FS + 0.5f);
    CHECK(ms_coefs_latency(&c) == want, "latency %d, want %d", ms_coefs_latency(&c), want);
    for (int ch = 0; ch < 2; ch++) {
        start();
        int n = 1024;
        memset(buf_k, 0, sizeof(float) * n);
        buf_k[100] = 0.5f;
        run(ch ? NULL : buf_k, ch ? buf_k : NULL, buf_o, n);
        int at = -1;
        for (int i = 0; i < n; i++) {
            if (fabsf(buf_o[i]) > 0.25f) {
                at = i;
                break;
            }
        }
        CHECK(at == 100 + want, "input %d: impulse at %d, want %d", ch, at, 100 + want);
    }
    printf("latency of the chain: %d samples = %.2f ms (kick look-ahead 1.0 + main look-ahead 1.5)\n", want,
           1000.0f * want / FS);
}

static void test_glue(void) {
    // Ratios: 1 kHz sine 20 dB over the threshold, well past the knee.
    static const float ratios[] = {2, 4, 10};
    for (int r = 0; r < 3; r++) {
        neutral();
        P[MS_P_GLUE_ON] = 1;
        P[MS_P_GLUE_THR] = -30;
        P[MS_P_GLUE_RATIO] = (float)r;
        P[MS_P_GLUE_ATT] = 3;
        P[MS_P_GLUE_REL] = 5;  // 1.2 s
        start();
        float g = gain_at(1000, 0.316f, false);  // -10 dB peak
        float want = -20.0f * (1.0f - 1.0f / ratios[r]);
        CHECK(NEAR(g, want, 0.5f), "glue %g:1: gain %.2f dB, want %.2f", ratios[r], g, want);
    }
    // Range caps the reduction; dry / wet 0 is the input; make-up adds.
    P[MS_P_GLUE_RANGE] = 6;
    start();
    float capped = gain_at(1000, 0.316f, false);
    CHECK(NEAR(capped, -6.0f, 0.3f), "glue range 6 dB: %.2f dB", capped);
    P[MS_P_GLUE_WET] = 0;
    start();
    float dry = gain_at(1000, 0.316f, false);
    CHECK(NEAR(dry, 0.0f, 0.01f), "glue dry: %.3f dB", dry);
    P[MS_P_GLUE_WET] = 100;
    P[MS_P_GLUE_MAKEUP] = 4;
    start();
    float made = gain_at(1000, 0.316f, false);
    CHECK(NEAR(made, -2.0f, 0.3f), "glue make-up: %.2f dB", made);

    // Sidechain high pass: a loud 50 Hz tone no longer drives the compressor.
    neutral();
    P[MS_P_GLUE_ON] = 1;
    P[MS_P_GLUE_THR] = -30;
    P[MS_P_GLUE_RATIO] = 1;
    P[MS_P_GLUE_REL] = 5;
    start();
    float bass_full = gain_at(50, 0.5f, false);
    P[MS_P_GLUE_SC_HP] = 400;
    start();
    float bass_hp = gain_at(50, 0.5f, false);
    CHECK(bass_full < -12.0f && bass_hp > bass_full + 10.0f, "glue sidechain HP: %.1f -> %.1f dB", bass_full, bass_hp);

    // Soft clip: never above -0.5 dB, and transparent below -6 dB.
    neutral();
    P[MS_P_GLUE_ON] = 1;
    P[MS_P_GLUE_THR] = 0;
    P[MS_P_GLUE_CLIP] = 1;
    start();
    int n = 22050;
    sine(buf_m, n, 200, 3.0f);
    run(NULL, buf_m, buf_o, n);
    float pk = db(peak(buf_o, 0, n));
    CHECK(pk <= -0.5f && pk > -1.5f, "soft clip peak %.2f dB", pk);
    sine(buf_m, n, 200, 0.4f);
    start();
    run(NULL, buf_m, buf_o, n);
    P[MS_P_GLUE_CLIP] = 0;
    start();
    run(NULL, buf_m, buf_k, n);
    float err = 0;
    for (int i = 0; i < n; i++) err = fmaxf(err, fabsf(buf_o[i] - buf_k[i]));
    CHECK(err < 1e-6f, "soft clip below the knee changes the signal by %g", err);

    // Auto release: after a short hit the gain is back much sooner than after a
    // long loud passage.
    float left[2];
    for (int mode = 0; mode < 2; mode++) {
        neutral();
        P[MS_P_GLUE_ON] = 1;
        P[MS_P_GLUE_THR] = -30;
        P[MS_P_GLUE_RATIO] = 1;
        P[MS_P_GLUE_ATT] = 1;
        P[MS_P_GLUE_REL] = 6;  // A
        start();
        int loud = mode ? 3 * 44100 : 2205;  // 3 s or 50 ms
        n = loud + 44100 / 2;
        for (int i = 0; i < n; i++) {
            buf_m[i] = (i < loud ? 0.316f : 0.003f) * sinf(2.0f * (float)M_PI * 1000.0f * (float)i / FS);
        }
        run(NULL, buf_m, buf_o, n);
        int at = loud + 13230;  // 300 ms after the loud part
        left[mode] = -db(rms(buf_o, at, at + 441) / (0.003f * 0.7071f));
    }
    CHECK(left[0] < 4.0f, "auto release after a 50 ms hit: %.2f dB left at 300 ms", left[0]);
    CHECK(left[1] > 3.0f * left[0], "auto release after 3 s: %.2f dB left at 300 ms", left[1]);
    printf("glue auto release, reduction left 300 ms later: %.2f dB after a 50 ms hit, %.2f dB after 3 s\n", left[0],
           left[1]);
}

// Amplitude of the `freq` component of x[from .. to) (a whole number of periods).
static float tone_amp(const float *x, int from, int to, float freq) {
    double re = 0, im = 0;
    for (int i = from; i < to; i++) {
        double ph = 2.0 * M_PI * (double)freq * i / (double)FS;
        re += x[i] * cos(ph);
        im += x[i] * sin(ph);
    }
    return (float)(2.0 * sqrt(re * re + im * im) / (to - from));
}

// The glue as a circuit: feedback detector, timing capacitor, gain cell colour.
static void test_glue_circuit(void) {
    // A level step (DC, so the detector has no ripple) at every attack and ratio:
    // the reduction rises without overshoot, also at the fastest attack where a
    // loop with a sample of delay would oscillate, and settles on the ratio.
    static const float ratios[] = {2, 4, 10};
    const int quiet = 4410, n = 44100;
    float t63[3] = {0};
    for (int r = 0; r < 3; r++) {
        for (int att = 0; att <= 6; att++) {
            neutral();
            P[MS_P_GLUE_ON] = 1;
            P[MS_P_GLUE_THR] = -30;
            P[MS_P_GLUE_RATIO] = (float)r;
            P[MS_P_GLUE_ATT] = (float)att;
            P[MS_P_GLUE_REL] = 5;  // 1.2 s
            start();
            for (int i = 0; i < n; i++) buf_m[i] = i < quiet ? 0.001f : 0.5f;
            run(NULL, buf_m, buf_o, n);
            float rise = 0;
            for (int i = quiet + 1; i < n; i++) rise = fmaxf(rise, buf_o[i] - buf_o[i - 1]);
            CHECK(rise < 1e-6f, "glue %g:1, attack %d: the gain comes back up by %g during the attack", ratios[r], att,
                  rise);
            // The attack resistor against the release resistor is a divider: 30 ms
            // against 1.2 s leaves 2.4 % of the detector's wish unused.
            static const float att_s[] = {0.00001f, 0.0001f, 0.0003f, 0.001f, 0.003f, 0.01f, 0.03f};
            float fb = (ratios[r] - 1.0f) * 1.2f / (1.2f + att_s[att]);
            float want = -(20.0f * log10f(0.5f) + 30.0f) * fb / (1.0f + fb);
            float got = db(buf_o[n - 1] / 0.5f);
            CHECK(NEAR(got, want, 0.15f), "glue %g:1, attack %d: settles at %.2f dB, want %.2f", ratios[r], att, got,
                  want);
            if (att == 5) {
                for (int i = quiet; i < n; i++) {
                    if (db(buf_o[i] / 0.5f) < 0.632f * want) {
                        t63[r] = 1000.0f * (float)(i - quiet) / FS;
                        break;
                    }
                }
            }
        }
    }
    // Feedback: the 10 ms attack acts in about 10 ms / ratio.
    CHECK(NEAR(t63[0], 5.0f, 1.5f) && NEAR(t63[2], 1.0f, 0.4f), "glue feedback attack: %.2f / %.2f / %.2f ms",
          t63[0], t63[1], t63[2]);
    printf("glue, attack 10 ms on a 24 dB step: 63 %% of the reduction after %.1f / %.1f / %.1f ms at 2 / 4 / 10:1\n",
           t63[0], t63[1], t63[2]);

    // A slow attack with a fast release compresses a steady tone less.
    float held[2];
    for (int slow = 0; slow < 2; slow++) {
        neutral();
        P[MS_P_GLUE_ON] = 1;
        P[MS_P_GLUE_THR] = -30;
        P[MS_P_GLUE_RATIO] = 1;
        P[MS_P_GLUE_ATT] = slow ? 6 : 1;  // 30 ms or 0.1 ms
        P[MS_P_GLUE_REL] = 0;             // 0.1 s
        start();
        held[slow] = gain_at(1000, 0.316f, false);
    }
    CHECK(NEAR(held[0], -15.0f, 0.5f) && held[1] > held[0] + 2.0f && held[1] < -6.0f,
          "glue, release 0.1 s: %.2f dB at attack 0.1 ms, %.2f dB at 30 ms", held[0], held[1]);
    printf("glue 4:1 on a tone 20 dB over, release 0.1 s: %.1f dB at attack 0.1 ms, %.1f dB at 30 ms\n", held[0],
           held[1]);

    // Gain cell colour without any reduction: 1 kHz at -6 dB.
    neutral();
    P[MS_P_GLUE_ON] = 1;
    P[MS_P_GLUE_THR] = 0;
    start();
    sine(buf_m, n, 1000, 0.5f);
    run(NULL, buf_m, buf_o, n);
    float h1 = tone_amp(buf_o, n / 2, n, 1000);
    float h2 = 100.0f * tone_amp(buf_o, n / 2, n, 2000) / h1, h3 = 100.0f * tone_amp(buf_o, n / 2, n, 3000) / h1;
    CHECK(NEAR(db(h1 / 0.5f), 0.0f, 0.02f), "glue colour: level %.3f dB", db(h1 / 0.5f));
    CHECK(h2 > 0.03f && h2 < 0.08f && h3 > 0.02f && h3 < 0.05f, "glue colour: H2 %.3f %%, H3 %.3f %%", h2, h3);
    printf("glue gain cell, 1 kHz at -6 dB, no reduction: second harmonic %.3f %%, third %.3f %%\n", h2, h3);

    // Under reduction the ripple on the timing capacitor adds to it: more on bass
    // and at a short release, as on the circuit.
    float thd[2];
    for (int bass = 0; bass < 2; bass++) {
        neutral();
        P[MS_P_GLUE_ON] = 1;
        P[MS_P_GLUE_THR] = -26;
        P[MS_P_GLUE_RATIO] = 1;
        P[MS_P_GLUE_ATT] = 5;  // 10 ms
        P[MS_P_GLUE_REL] = 0;  // 0.1 s
        start();
        float f = bass ? 100 : 1000;
        sine(buf_m, n, f, 0.5f);
        run(NULL, buf_m, buf_o, n);
        double sum = 0;
        for (int h = 2; h <= 9; h++) {
            double a = tone_amp(buf_o, n / 2, n, f * (float)h);
            sum += a * a;
        }
        thd[bass] = 100.0f * (float)sqrt(sum) / tone_amp(buf_o, n / 2, n, f);
    }
    CHECK(thd[1] > 3.0f * thd[0] && thd[1] < 5.0f, "glue ripple distortion: %.3f %% at 1 kHz, %.3f %% at 100 Hz",
          thd[0], thd[1]);
    printf("glue 4:1, attack 10 ms, release 0.1 s, tone 20 dB over: THD %.3f %% at 1 kHz, %.2f %% at 100 Hz\n",
           thd[0], thd[1]);
}

static void test_parallel(void) {
    // Parallel compression (factory settings, send open) lifts quiet material more
    // than loud material.
    float lift[2];
    for (int loud = 0; loud < 2; loud++) {
        float amp = loud ? 0.5f : 0.01f;
        neutral();
        start();
        float base = gain_at(1000, amp, false);
        P[MS_P_PAR_ON] = 1;
        P[MS_P_PAR_SEND_M] = 0;
        start();
        lift[loud] = gain_at(1000, amp, false) - base;
    }
    CHECK(lift[0] > 6.0f, "parallel: quiet signal lifted %.1f dB", lift[0]);
    CHECK(lift[1] < 3.0f && lift[1] > 0.0f, "parallel: loud signal lifted %.1f dB", lift[1]);
    printf("parallel compression (defaults, send 0 dB): -40 dB signal +%.1f dB, -6 dB signal +%.1f dB\n", lift[0],
           lift[1]);
    // Sends closed = nothing added.
    neutral();
    P[MS_P_PAR_ON] = 1;
    P[MS_P_PAR_SEND_M] = -60;
    P[MS_P_PAR_SEND_K] = -60;
    start();
    float off = gain_at(1000, 0.1f, false);
    CHECK(NEAR(off, 0.0f, 0.001f), "parallel with closed sends: %.4f dB", off);
}

static void test_chain(void) {
    // Bypass and the neutral chain pass kick + mix.
    neutral();
    start();
    int n = 4410;
    for (int i = 0; i < n; i++) {
        buf_k[i] = 0.3f * rnd();
        buf_m[i] = 0.3f * rnd();
    }
    run(buf_k, buf_m, buf_o, n);
    float err = 0;
    for (int i = 0; i < n; i++) err = fmaxf(err, fabsf(buf_o[i] - (buf_k[i] + buf_m[i])));
    CHECK(err < 1e-6f, "neutral chain differs from kick + mix by %g", err);
    ms_params_defaults(P);
    P[MS_P_BYPASS] = 1;
    start();
    run(buf_k, buf_m, buf_o, n);
    err = 0;
    for (int i = 0; i < n; i++) err = fmaxf(err, fabsf(buf_o[i] - (buf_k[i] + buf_m[i])));
    CHECK(err < 1e-6f, "bypass differs from kick + mix by %g", err);

    // Levels: -60 dB is off, the trims and levels are plain gains.
    neutral();
    P[MS_P_M_LVL] = -60;
    start();
    run(NULL, buf_m, buf_o, n);
    CHECK(peak(buf_o, 2000, n) == 0.0f, "mix level off still passes %g", peak(buf_o, 2000, n));
    neutral();
    P[MS_P_IN_M_TRIM] = -6;
    P[MS_P_M_LVL] = 3;
    P[MS_P_OUT_LVL] = -2;
    start();
    float g = gain_at(1000, 0.25f, false);
    CHECK(NEAR(g, -5.0f, 0.02f), "trim -6 + level +3 + out -2: %.3f dB", g);

    // Factory settings with a hot kick and mix: finite, under the ceiling, meters move.
    ms_params_defaults(P);
    start();
    n = 2 * 44100;
    make_kick(buf_k, n, 21000, 0.95f);
    for (int i = 0; i < n; i++) {
        buf_m[i] = 0.4f * sinf(2.0f * (float)M_PI * 110.0f * (float)i / FS) + 0.25f * rnd();
    }
    run(buf_k, buf_m, buf_o, n);
    float pk = peak(buf_o, 0, n), ceil = powf(10.0f, -1.0f / 20.0f);
    bool finite = true;
    for (int i = 0; i < n; i++) finite = finite && isfinite(buf_o[i]);
    CHECK(finite, "factory chain: output not finite");
    CHECK(pk <= ceil * 1.000001f && pk > 0.3f, "factory chain: peak %.4f, ceiling %.4f", pk, ceil);
    ms_meters_t mt;
    ms_dsp_take_meters(&dsp, &mt);
    CHECK(mt.raw_k > 0.9f && mt.gr_klim > 1.0f && mt.gr_mb[0] > 3.0f && mt.gr_par > 6.0f && mt.out > 0.3f,
          "factory chain meters: raw_k %.2f klim %.1f mb lo %.1f par %.1f out %.2f", mt.raw_k, mt.gr_klim,
          mt.gr_mb[0], mt.gr_par, mt.out);
    printf("factory settings, hot kick + mix: out peak %.2f dB; reduction kick limiter %.1f, bands %.1f / %.1f / "
           "%.1f, parallel %.1f, glue %.1f, limiter %.1f dB\n",
           db(pk), mt.gr_klim, mt.gr_mb[0], mt.gr_mb[1], mt.gr_mb[2], mt.gr_par, mt.gr_glue, mt.gr_lim);
    // Taking the meters restarts them.
    run(NULL, NULL, buf_o, BLOCK);
    ms_dsp_take_meters(&dsp, &mt);
    CHECK(mt.raw_k == 0.0f && mt.in_m == 0.0f && mt.gr_mb[0] < 20.0f, "meters not restarted: raw_k %g", mt.raw_k);
}

static void test_fuzz(void) {
    // Random settings changed on the fly over loud noise: always finite, and under
    // the ceiling whenever the limiter is on (after its look-ahead has refilled).
    ms_params_defaults(P);
    start();
    int bad = 0, over = 0;
    for (int round = 0; round < 400; round++) {
        for (int i = 0; i < MS_P_COUNT; i++) {
            const ms_param_def_t *d = &ms_param_defs[i];
            if (rnd() > -0.5f) continue;  // change a quarter of them
            P[i] = ms_param_clamp(i, d->min + (d->max - d->min) * (0.5f + 0.5f * rnd()));
        }
        P[MS_P_BYPASS] = 0;
        P[MS_P_OUT_LVL] = 0;
        update();
        int n = 2048;
        float amp = 0.05f + 1.5f * fabsf(rnd());
        for (int i = 0; i < n; i++) {
            buf_k[i] = amp * rnd();
            buf_m[i] = amp * sinf(0.01f * (float)i * (1.0f + (float)round)) + 0.2f * rnd();
            if (buf_k[i] > 1.0f) buf_k[i] = 1.0f;  // converter range
            if (buf_k[i] < -1.0f) buf_k[i] = -1.0f;
        }
        run(buf_k, buf_m, buf_o, n);
        float ceil = powf(10.0f, P[MS_P_LIM_CEIL] / 20.0f) * 1.000001f;
        for (int i = 0; i < n; i++) {
            if (!isfinite(buf_o[i])) bad++;
            // orders 0 and 2 have the limiter last
            bool lim_last = P[MS_P_O_ORDER] == 0 || P[MS_P_O_ORDER] == 2;
            if (P[MS_P_LIM_ON] >= 0.5f && lim_last && i >= 512 && fabsf(buf_o[i]) > ceil) over++;
            if (fabsf(buf_o[i]) > 1.0f) over++;
        }
    }
    CHECK(bad == 0, "fuzz: %d non-finite samples", bad);
    CHECK(over == 0, "fuzz: %d samples over the ceiling", over);
}

// ------------------------------------------------------------ parameters, protocol

static void test_params(void) {
    float v[MS_P_COUNT];
    ms_params_defaults(v);
    for (int i = 0; i < MS_P_COUNT; i++) {
        const ms_param_def_t *d = &ms_param_defs[i];
        CHECK(d->min < d->max && d->def >= d->min && d->def <= d->max, "%s: range / default", d->id);
        CHECK(ms_param_find(d->id) == i, "%s: duplicate id", d->id);
        CHECK(d->kind != MS_KIND_LOG || d->min > 0, "%s: log scale needs min > 0", d->id);
        bool group_ok = false;
        for (int g = 0; g < ms_group_count; g++) group_ok = group_ok || strcmp(ms_group_defs[g].id, d->group) == 0;
        CHECK(group_ok, "%s: unknown group %s", d->id, d->group);
        if (d->kind == MS_KIND_ENUM) {
            int commas = 0;
            for (const char *p = d->options; *p; p++) commas += *p == ',';
            CHECK(commas == (int)d->max, "%s: %d options for max %g", d->id, commas + 1, (double)d->max);
        }
        CHECK(!strchr(d->label, '|') && !strchr(d->options, '|'), "%s: '|' in a text", d->id);
    }
    // The three bands are laid out alike (ms_coefs_from_params relies on it).
    CHECK(MS_P_MB_MID_ON - MS_P_MB_LO_ON == 6 && MS_P_MB_HI_ON - MS_P_MB_MID_ON == 6 &&
              MS_P_MB_HI_GAIN - MS_P_MB_HI_ON == 5,
          "band parameter layout");
    // The three filters are laid out alike (flt_set relies on it).
    CHECK(MS_P_K_FLT_HC_SLOPE - MS_P_K_FLT_ON == 8 && MS_P_M_FLT_HC_SLOPE - MS_P_M_FLT_ON == 8 &&
              MS_P_O_FLT_HC_SLOPE - MS_P_O_FLT_ON == 8 && MS_P_O_FLT_LC_Q - MS_P_O_FLT_ON == 3,
          "filter parameter layout");
    CHECK(ms_param_clamp(MS_P_K_FLT_LC_F, 5) == 10 && ms_param_clamp(MS_P_K_FLT_LC_F, 1e9f) == 20000, "clamp");
    CHECK(ms_param_clamp(MS_P_GLUE_ATT, 2.6f) == 3 && ms_param_clamp(MS_P_GLUE_ON, 0.4f) == 0, "snap");
    CHECK(ms_param_clamp(MS_P_K_FLT_LC_F, NAN) == 25, "NaN -> default");

    // Export / import round trip; setup aids are not stored; unknown lines are skipped.
    for (int i = 0; i < MS_P_COUNT; i++) {
        const ms_param_def_t *d = &ms_param_defs[i];
        v[i] = ms_param_clamp(i, d->min + (d->max - d->min) * 0.37f);
    }
    char text[MS_SETTINGS_TEXT_MAX];
    size_t len = ms_params_export(v, text, sizeof(text));
    CHECK(len > 500 && len < sizeof(text) / 2, "export length %zu", len);
    CHECK(!strstr(text, "bypass") && !strstr(text, "mb_solo"), "setup aids exported");
    float w[MS_P_COUNT];
    ms_params_defaults(w);
    int count = ms_params_import(w, text);
    int saved = 0;
    float worst = 0;
    for (int i = 0; i < MS_P_COUNT; i++) {
        if (ms_param_defs[i].not_saved) {
            CHECK(w[i] == ms_param_defs[i].def, "%s imported", ms_param_defs[i].id);
            continue;
        }
        saved++;
        float tol = fabsf(v[i]) * 2e-6f;
        if (fabsf(w[i] - v[i]) > tol) worst = fabsf(w[i] - v[i]);
    }
    CHECK(count == saved && worst == 0.0f, "round trip: %d of %d, worst %g", count, saved, worst);
    ms_params_defaults(w);
    count = ms_params_import(w, "# old file\nset nothing 3\nset k_flt_lc_f 99999\n\nset bypass 1\nfoo\nset m_flt_lc_f 40");
    CHECK(count == 2 && w[MS_P_K_FLT_LC_F] == 20000 && w[MS_P_M_FLT_LC_F] == 40 && w[MS_P_BYPASS] == 0,
          "import skips junk");
    // Settings of firmware 0.2: the cuts land in the filters.
    ms_params_defaults(w);
    count = ms_params_import(w, "set k_hp_on 0\nset k_hp_f 31\nset m_hp_slope 1\nset eq_lo_f 45\nset eq_hi_on 1\n"
                                "set eq_hi_f 12000\nset eq_hi_slope 1\nset glue_thr -12\n");
    CHECK(count == 8 && w[MS_P_K_FLT_LC_ON] == 0 && w[MS_P_K_FLT_LC_F] == 31 && w[MS_P_M_FLT_LC_SLOPE] == 1 &&
              w[MS_P_O_FLT_LC_F] == 45 && w[MS_P_O_FLT_HC_ON] == 1 && w[MS_P_O_FLT_HC_F] == 12000 &&
              w[MS_P_O_FLT_HC_SLOPE] == 1 && w[MS_P_GLUE_THR] == -12,
          "firmware 0.2 settings: %d read", count);
    char small[64];
    CHECK(ms_params_export(v, small, sizeof(small)) == 0, "export into a small buffer");

    // Coefficients: every look-ahead fits the ring at both sample rates.
    for (float fs = 44100; fs <= 48000; fs += 3900) {
        ms_params_defaults(v);
        v[MS_P_LIM_LA] = v[MS_P_K_LIM_LA] = ms_param_defs[MS_P_LIM_LA].max;
        ms_coefs_t c;
        ms_coefs_from_params(v, fs, BLOCK, &c);
        CHECK(c.lim.la <= MS_LA_SIZE - 2 && c.lim.la == (int)(0.005f * fs + 0.5f), "look-ahead %d at %g", c.lim.la,
              (double)fs);
    }
}

static char lines[400][224];
static int n_lines;
static char stored[MS_SETTINGS_TEXT_MAX];
static bool have_stored, fail_save;
static int applied;

static void host_out(void *ctx, const char *line) {
    if (n_lines < 400) snprintf(lines[n_lines++], sizeof(lines[0]), "%s", line);
}
static bool host_save(void *ctx, const char *text) {
    if (fail_save) return false;
    snprintf(stored, sizeof(stored), "%s", text);
    have_stored = true;
    return true;
}
static bool host_load(void *ctx, char *text, size_t cap) {
    if (!have_stored) return false;
    snprintf(text, cap, "%s", stored);
    return true;
}
static void host_apply(void *ctx, const float values[MS_P_COUNT]) {
    applied++;
    memcpy(P, values, sizeof(P));
}
static void host_meters(void *ctx, ms_meters_t *m) {
    memset(m, 0, sizeof(*m));
    m->raw_k = 1.0f;
    m->in_m = 0.1f;
    m->gr_mb[1] = 3.25f;
}
static void host_status(void *ctx, ms_status_t *st) {
    st->fs = FS;
    st->block = BLOCK;
    st->io_ms = 2.5f;
    st->cpu = 41;
    st->cpu_max = 57;
}

static void send(ms_proto_t *pr, const char *text) {
    char line[128];
    snprintf(line, sizeof(line), "%s", text);
    n_lines = 0;
    ms_proto_line(pr, line);
}

static void test_protocol(void) {
    ms_host_t host = {NULL, host_out, host_save, host_load, host_apply, host_meters, host_status};
    ms_proto_t pr;
    have_stored = false;
    ms_proto_init(&pr, &host);
    CHECK(applied == 1 && pr.values[MS_P_K_FLT_LC_F] == 25 && !pr.unsaved, "init with nothing stored");

    send(&pr, "hello");
    CHECK(n_lines == 1 && strncmp(lines[0], "hello|master|", 13) == 0 && strstr(lines[0], "|proto=3|fs=44100|block=16|io_ms=2.50"),
          "hello: %s", lines[0]);

    send(&pr, "desc");
    CHECK(n_lines == ms_group_count + MS_P_COUNT + 2 && strcmp(lines[n_lines - 1], "ok|desc") == 0, "desc: %d lines",
          n_lines);
    CHECK(strcmp(lines[0], "g|in|Inputs") == 0, "desc group: %s", lines[0]);
    CHECK(strcmp(lines[ms_group_count + MS_P_K_FLT_LC_F], "d|k_flt_lc_f|k_flt|log|10|20000|25|0|Hz|1|Low cut frequency|") == 0,
          "desc line: %s", lines[ms_group_count + MS_P_K_FLT_LC_F]);
    CHECK(strcmp(lines[ms_group_count + MS_P_MB_SOLO], "d|mb_solo|mb|enum|0|3|0|1||0|Solo band|Off,Low,Mid,High") == 0,
          "desc enum: %s", lines[ms_group_count + MS_P_MB_SOLO]);
    for (int i = 0; i < n_lines; i++) CHECK(strlen(lines[i]) < 200, "desc line too long: %s", lines[i]);
    // The meter line has one value per name.
    int names = 1;
    for (const char *p = ms_meter_names; *p; p++) names += *p == ' ';
    send(&pr, "m");
    int values = 1;
    for (const char *p = lines[0] + 2; *p; p++) values += *p == ' ';
    CHECK(n_lines == 1 && values == names, "meters: %d values for %d names: %s", values, names, lines[0]);
    // io 2.5 ms + factory look-aheads 1.0 + 1.5 ms (44 + 66 samples)
    CHECK(strcmp(lines[0], "m|0.0 -120.0 -120.0 -20.0 -120.0 -120.0 -120.0 -120.0 0.00 0.00 3.25 0.00 0.00 0.00 0.00 "
                           "41 57 4.99 0 0.000 0.000 0 0 0.00") == 0,
          "meter line: %s", lines[0]);

    send(&pr, "get");
    CHECK(n_lines == MS_P_COUNT + 1 && strcmp(lines[MS_P_K_FLT_LC_F], "p|k_flt_lc_f|25") == 0, "get: %s",
          lines[MS_P_K_FLT_LC_F]);

    // set: clamps, answers with the value, marks unsaved, applies.
    int before = applied;
    send(&pr, "set k_flt_lc_f 31.5");
    CHECK(n_lines == 1 && strcmp(lines[0], "p|k_flt_lc_f|31.5") == 0 && pr.unsaved && applied == before + 1 &&
              P[MS_P_K_FLT_LC_F] == 31.5f,
          "set: %s", lines[0]);
    send(&pr, "set  k_flt_lc_f   50000\r");
    CHECK(strcmp(lines[0], "p|k_flt_lc_f|20000") == 0, "set clamps: %s", lines[0]);
    send(&pr, "set k_hp_f 33");  // a firmware 0.2 name: the kick filter's low cut
    CHECK(strcmp(lines[0], "p|k_flt_lc_f|33") == 0, "old name: %s", lines[0]);
    send(&pr, "set k_flt_lc_f 50000");
    send(&pr, "set nope 1");
    CHECK(strncmp(lines[0], "err|", 4) == 0, "unknown parameter: %s", lines[0]);
    send(&pr, "set k_flt_lc_f abc");
    CHECK(strncmp(lines[0], "err|", 4) == 0 && pr.values[MS_P_K_FLT_LC_F] == 20000, "bad number: %s", lines[0]);
    send(&pr, "frobnicate");
    CHECK(strncmp(lines[0], "err|", 4) == 0, "unknown command: %s", lines[0]);
    send(&pr, "");
    CHECK(n_lines == 0, "empty line answered");

    // Bypass is a setup aid: it does not make the settings unsaved and is not stored.
    send(&pr, "save");
    CHECK(strcmp(lines[0], "ok|save") == 0 && !pr.unsaved && strstr(stored, "set k_flt_lc_f 20000\n"), "save: %s", lines[0]);
    send(&pr, "set bypass 1");
    CHECK(!pr.unsaved && P[MS_P_BYPASS] == 1, "bypass marks unsaved");

    // defaults, then load brings the saved value back and keeps bypass.
    send(&pr, "defaults");
    CHECK(strcmp(lines[n_lines - 2], "ok|defaults") == 0 && strcmp(lines[n_lines - 1], "ok|ctl") == 0 &&
              pr.values[MS_P_K_FLT_LC_F] == 25 && pr.unsaved,
          "defaults");
    send(&pr, "set bypass 1");
    send(&pr, "load");
    CHECK(strcmp(lines[n_lines - 2], "ok|load") == 0 && n_lines == MS_P_COUNT + 2 && pr.values[MS_P_K_FLT_LC_F] == 20000 &&
              !pr.unsaved && pr.values[MS_P_BYPASS] == 1,
          "load");

    // A failing store is reported and the settings stay unsaved.
    send(&pr, "set m_flt_lc_f 55");
    fail_save = true;
    send(&pr, "save");
    CHECK(strncmp(lines[0], "err|", 4) == 0 && pr.unsaved, "failed save: %s", lines[0]);
    fail_save = false;

    // Power-up with stored settings: they are applied, bypass is off again.
    ms_proto_t pr2;
    ms_proto_init(&pr2, &host);
    CHECK(pr2.values[MS_P_K_FLT_LC_F] == 20000 &&
              pr2.values[MS_P_M_FLT_LC_F] == ms_param_defs[MS_P_M_FLT_LC_F].def && pr2.values[MS_P_BYPASS] == 0 &&
              !pr2.unsaved,
          "power-up from stored settings");
}

// ------------------------------------------------------------ channel off / solo, the panel controls

// Steady level (dB) of the chain's output with a 1 kHz tone on the kick and a 3 kHz
// tone on the mix: [0] the kick's tone, [1] the mix's, by correlation.
static void tones_out(float out_db[2]) {
    int n = 8820;
    for (int i = 0; i < n; i++) {
        buf_k[i] = 0.2f * sinf(2.0f * (float)M_PI * 1000.0f * (float)i / FS);
        buf_m[i] = 0.2f * sinf(2.0f * (float)M_PI * 3000.0f * (float)i / FS);
    }
    run(buf_k, buf_m, buf_o, n);
    double ck = 0, cm = 0, kk = 0, mm = 0;
    for (int i = n / 2; i < n; i++) {
        ck += (double)buf_o[i] * buf_k[i];
        cm += (double)buf_o[i] * buf_m[i];
        kk += (double)buf_k[i] * buf_k[i];
        mm += (double)buf_m[i] * buf_m[i];
    }
    out_db[0] = db((float)fabs(ck / kk));
    out_db[1] = db((float)fabs(cm / mm));
}

static void test_mute_solo(void) {
    struct {
        int param;
        bool bypass;
        float kick, mix;  // expected: 0 = heard (0 dB), 1 = silent
    } cases[] = {
        {-1, false, 0, 0},           {MS_P_K_OFF, false, 1, 0},  {MS_P_M_OFF, false, 0, 1},
        {MS_P_K_SOLO, false, 0, 1},  {MS_P_M_SOLO, false, 1, 0}, {MS_P_OUT_OFF, false, 1, 1},
        {MS_P_PAR_SOLO, false, 1, 1}, {MS_P_K_SOLO, true, 0, 1},  {MS_P_M_OFF, true, 0, 1},
        {MS_P_OUT_OFF, true, 1, 1},
    };
    for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); c++) {
        neutral();
        P[MS_P_BYPASS] = cases[c].bypass;
        start();
        if (cases[c].param >= 0) P[cases[c].param] = 1;
        update();
        float o[2];
        tones_out(o);
        for (int ch = 0; ch < 2; ch++) {
            float want = ch ? cases[c].mix : cases[c].kick;
            bool ok = want ? o[ch] < -100.0f : NEAR(o[ch], 0.0f, 0.001f);
            CHECK(ok, "off / solo case %zu (%s%s): %s at %.2f dB", c,
                  cases[c].param >= 0 ? ms_param_defs[cases[c].param].id : "none", cases[c].bypass ? ", bypass" : "",
                  ch ? "mix" : "kick", o[ch]);
        }
    }

    // A parallel bus that is soloed is still fed by both sends; a kick that is off feeds it no more.
    neutral();
    P[MS_P_PAR_ON] = 1;
    P[MS_P_PAR_SEND_K] = P[MS_P_PAR_SEND_M] = 0;
    P[MS_P_PAR_RATIO] = 1.5f;
    P[MS_P_PAR_THR] = 0;
    P[MS_P_PAR_MAKEUP] = 0;
    P[MS_P_PAR_RET] = 0;
    P[MS_P_PAR_SOLO] = 1;
    start();
    float o[2];
    tones_out(o);
    CHECK(NEAR(o[0], 0.0f, 0.05f) && NEAR(o[1], 0.0f, 0.05f), "parallel solo: kick %.2f, mix %.2f dB", o[0], o[1]);
    P[MS_P_K_OFF] = 1;
    update();
    tones_out(o);
    CHECK(o[0] < -100.0f && NEAR(o[1], 0.0f, 0.05f), "parallel solo, kick off: kick %.2f, mix %.2f dB", o[0], o[1]);

    // Off fades like a fader (the 10 ms gain smoothing, stepped per block): no
    // step near the 0.5 a hard cut would make; -60 dB within 100 ms.
    neutral();
    start();
    int n = 8820;
    sine(buf_k, n, 100, 0.5f);
    run(buf_k, NULL, buf_o, 512);
    P[MS_P_K_OFF] = 1;
    update();
    run(buf_k + 512, NULL, buf_o + 512, n - 512);
    float step = 0;
    for (int i = 1; i < n; i++) step = fmaxf(step, fabsf(buf_o[i] - buf_o[i - 1]));
    CHECK(step < 0.025f && peak(buf_o, 512 + 4410, n) < 5e-4f, "kick off: largest step %.4f, end %.6f", step,
          peak(buf_o, 512 + 4410, n));

    // The factory bypass is still kick + mix, bit for bit.
    neutral();
    P[MS_P_BYPASS] = 1;
    start();
    for (int i = 0; i < 1024; i++) {
        buf_k[i] = 0.4f * rnd();
        buf_m[i] = 0.4f * rnd();
    }
    run(buf_k, buf_m, buf_o, 1024);
    int diff = 0;
    for (int i = 0; i < 1024; i++) diff += buf_o[i] != buf_k[i] + buf_m[i];
    CHECK(diff == 0, "bypass: %d samples differ from kick + mix", diff);
}

static float V[MS_P_COUNT];

// Runs the CV for `ms` of 10 ms ticks at a fixed position.
static bool cv_hold(ms_ctl_t *c, int cv, float norm, int ms) {
    bool changed = false;
    for (int t = 0; t < ms; t += 10) changed |= ms_ctl_cv(c, cv, norm, V);
    return changed;
}

static uint32_t now_ms;
static bool button(ms_ctl_t *c, bool down, int ms) {
    bool changed = false;
    for (int t = 0; t < ms; t += 10, now_ms += 10) changed |= ms_ctl_button(c, down, now_ms, V);
    return changed;
}

static void test_ctl(void) {
    ms_ctl_t c;
    ms_ctl_init(&c);
    ms_params_defaults(V);

    // What may be mapped where.
    CHECK(ms_ctl_refuse(MS_SRC_CV1, MS_P_GLUE_THR) == NULL && ms_ctl_refuse(MS_SRC_CV2, MS_P_BYPASS) == NULL,
          "CV takes any setting");
    CHECK(ms_ctl_refuse(MS_SRC_CV1, MS_P_LIM_LA) && ms_ctl_refuse(MS_SRC_CV2, MS_P_K_LIM_LA), "CV refuses look-aheads");
    CHECK(ms_ctl_refuse(MS_SRC_MODE, MS_P_GLUE_THR) && ms_ctl_refuse(MS_SRC_MODE, MS_P_MB_SOLO) &&
              !ms_ctl_refuse(MS_SRC_MODE, MS_P_K_SOLO) && ms_ctl_refuse(MS_SRC_MODE, MS_P_MODE_ACT),
          "MODE takes switches only");
    CHECK(ms_ctl_refuse(MS_SRC_CV1, MS_P_MODE_ACT) && ms_ctl_refuse(MS_SRC_CV2, MS_P_LED_MODE), "not on a knob");
    CHECK(ms_src_find("mode") == MS_SRC_MODE && ms_src_find("click") == MS_SRC_MODE && ms_src_find("hold") == MS_SRC_MODE &&
              ms_src_find("push") == MS_SRC_MODE && ms_src_find("cv3") == -1,
          "0.4.0 source names read as mode");
    CHECK(ms_ctl_refuse(MS_SRC_COUNT, 0) && ms_ctl_refuse(MS_SRC_CV1, -1), "unknown source / setting");
    for (int i = 0; i < MS_CTL_MAPS; i++) CHECK(!ms_ctl_map(&c, MS_SRC_CV2, i, 0, 1), "map %d", i);
    CHECK(ms_ctl_map(&c, MS_SRC_CV2, MS_P_GLUE_THR, 0, 1) != NULL && !ms_ctl_map(&c, MS_SRC_CV2, 3, 0, 1) &&
              c.count[MS_SRC_CV2] == MS_CTL_MAPS,
          "full; an existing mapping is updated");
    ms_ctl_clear(&c);

    // A linear setting over part of its range, a log one turned round, a list.
    CHECK(!ms_ctl_map(&c, MS_SRC_CV1, MS_P_GLUE_THR, -30, 0), "map glue threshold");
    CHECK(!ms_ctl_map(&c, MS_SRC_CV1, MS_P_O_FLT_HC_F, 20000, 200), "map high cut");
    CHECK(!ms_ctl_map(&c, MS_SRC_CV1, MS_P_GLUE_RATIO, 0, 7), "map ratio (clamped)");
    CHECK(c.map[MS_SRC_CV1][2].b == 2, "range clamped: %g", (double)c.map[MS_SRC_CV1][2].b);
    CHECK(cv_hold(&c, 0, 0.5f, 10) && c.dirty[MS_P_GLUE_THR], "first position applied at once");
    CHECK(NEAR(V[MS_P_GLUE_THR], -15, 1e-4) && NEAR(V[MS_P_O_FLT_HC_F], 2000, 0.5) && V[MS_P_GLUE_RATIO] == 1,
          "half way: %g dB, %g Hz, ratio %g", (double)V[MS_P_GLUE_THR], (double)V[MS_P_O_FLT_HC_F],
          (double)V[MS_P_GLUE_RATIO]);
    // Noise under the step does not move the settings; the end stops are exact.
    memset(c.dirty, 0, sizeof(c.dirty));
    bool moved = false;
    for (int t = 0; t < 200; t++) moved |= ms_ctl_cv(&c, 0, 0.5f + 0.003f * rnd(), V);
    CHECK(!moved && !c.dirty[MS_P_GLUE_THR], "ADC noise moves nothing");
    cv_hold(&c, 0, 1.0f, 300);
    CHECK(V[MS_P_GLUE_THR] == 0 && V[MS_P_O_FLT_HC_F] == 200 && V[MS_P_GLUE_RATIO] == 2, "top: %g dB, %g Hz",
          (double)V[MS_P_GLUE_THR], (double)V[MS_P_O_FLT_HC_F]);
    cv_hold(&c, 0, 0.0f, 300);
    CHECK(V[MS_P_GLUE_THR] == -30 && V[MS_P_O_FLT_HC_F] == 20000 && V[MS_P_GLUE_RATIO] == 0, "bottom: %g dB, %g Hz",
          (double)V[MS_P_GLUE_THR], (double)V[MS_P_O_FLT_HC_F]);
    // A jump is smoothed: the first tick goes ~30 % of the way.
    ms_ctl_cv(&c, 0, 1.0f, V);
    CHECK(V[MS_P_GLUE_THR] > -22 && V[MS_P_GLUE_THR] < -20, "smoothing: %g dB after one tick", (double)V[MS_P_GLUE_THR]);
    // A value set from the page stays until the knob moves; a resync sets it again.
    cv_hold(&c, 0, 1.0f, 300);
    V[MS_P_GLUE_THR] = -7;
    CHECK(!cv_hold(&c, 0, 1.0f, 100) && V[MS_P_GLUE_THR] == -7, "page value kept while the knob rests");
    ms_ctl_resync(&c);
    CHECK(cv_hold(&c, 0, 1.0f, 10) && V[MS_P_GLUE_THR] == 0, "resync");
    CHECK(ms_ctl_unmap(&c, MS_SRC_CV1, MS_P_O_FLT_HC_F) && c.count[MS_SRC_CV1] == 2 &&
              c.map[MS_SRC_CV1][1].param == MS_P_GLUE_RATIO && !ms_ctl_unmap(&c, MS_SRC_CV1, MS_P_O_FLT_HC_F),
          "unmap");

    // MODE, click (the default): over on a press, back on the next.
    ms_params_defaults(V);
    ms_ctl_clear(&c);
    now_ms = 1000;
    ms_ctl_map(&c, MS_SRC_MODE, MS_P_BYPASS, 1, 0);
    ms_ctl_map(&c, MS_SRC_MODE, MS_P_GLUE_ON, 0, 0);
    CHECK(V[MS_P_MODE_ACT] == MS_ACT_CLICK && !ms_ctl_engaged(&c, V), "click, nothing engaged");
    button(&c, true, 10);
    CHECK(V[MS_P_BYPASS] == 0, "a 10 ms bounce does nothing");
    button(&c, false, 50);
    button(&c, true, 30);
    CHECK(V[MS_P_BYPASS] == 1 && V[MS_P_GLUE_ON] == 0 && ms_ctl_engaged(&c, V), "click on the press");
    button(&c, false, 50);
    CHECK(V[MS_P_BYPASS] == 1, "the release keeps it");
    button(&c, true, 800);
    CHECK(V[MS_P_BYPASS] == 0 && V[MS_P_GLUE_ON] == 1 && !ms_ctl_engaged(&c, V), "second press back, a long one too");
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 0, "long press: once");
    // A setting that went elsewhere from the page: the press switches all over.
    V[MS_P_BYPASS] = 1;
    button(&c, true, 30);
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 1 && V[MS_P_GLUE_ON] == 0, "a half-switched MODE switches all over");
    ms_params_defaults(V);

    // Hold: a short press does nothing, a long one switches while still down.
    V[MS_P_MODE_ACT] = MS_ACT_HOLD;
    button(&c, true, 300);
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 0, "hold: short press does nothing");
    button(&c, true, 600);
    CHECK(V[MS_P_BYPASS] == 1 && ms_ctl_engaged(&c, V), "hold: over after 0.5 s, still down");
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 1, "hold: the release keeps it");
    button(&c, true, 600);
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 0 && !ms_ctl_engaged(&c, V), "hold: the next hold back");

    // Push: over only while down, back even if the way changed meanwhile.
    V[MS_P_MODE_ACT] = MS_ACT_PUSH;
    button(&c, true, 200);
    CHECK(V[MS_P_BYPASS] == 1 && V[MS_P_GLUE_ON] == 0, "push: over while down");
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 0 && V[MS_P_GLUE_ON] == 1, "push: back on the release");
    button(&c, true, 30);
    V[MS_P_MODE_ACT] = MS_ACT_CLICK;
    button(&c, false, 30);
    CHECK(V[MS_P_BYPASS] == 0, "push: back after a change to click while down");

    // From the page.
    CHECK(ms_ctl_fire(&c, -1, V) && V[MS_P_BYPASS] == 1 && !ms_ctl_fire(&c, 1, V) && ms_ctl_fire(&c, 0, V) &&
              V[MS_P_BYPASS] == 0,
          "fire from the page");

    // Export / import.
    ms_ctl_clear(&c);
    ms_ctl_map(&c, MS_SRC_CV1, MS_P_GLUE_THR, -30, 0);
    ms_ctl_map(&c, MS_SRC_CV2, MS_P_O_FLT_HC_F, 20000, 200.5f);
    ms_ctl_map(&c, MS_SRC_MODE, MS_P_K_OFF, 1, 0);
    char text[512];
    size_t len = ms_ctl_export(&c, text, sizeof(text));
    CHECK(len && strcmp(text, "map cv1 glue_thr -30 0\nmap cv2 o_flt_hc_f 20000 200.5\nmap mode k_off 1\n") == 0,
          "export: %s", text);
    ms_ctl_t d;
    ms_ctl_init(&d);
    int count = ms_ctl_import(&d, "set glue_thr 3\nmap cv9 glue_thr 1 2\nmap cv1 nope 1 2\nmap click glue_thr 1\n"
                                  "map cv1 k_hp_f 30 60\n");
    count += ms_ctl_import(&d, text);
    CHECK(count == 4 && d.count[MS_SRC_CV1] == 2 && d.count[MS_SRC_MODE] == 1 && d.map[MS_SRC_CV1][0].param == MS_P_K_FLT_LC_F,
          "import: %d", count);
    char small[16];
    CHECK(ms_ctl_export(&c, small, sizeof(small)) == 0, "export into a small buffer");

    // LED.
    ms_led_t led = {0};
    ms_meters_t m = {0};
    ms_params_defaults(V);
    CHECK(ms_led_run(&led, V, &m, 0, 100, 0.01f) == 0.3f, "status: running");
    V[MS_P_BYPASS] = 1;
    CHECK(ms_led_run(&led, V, &m, 0, 100, 0.01f) == 0.6f && ms_led_run(&led, V, &m, 0, 600, 0.01f) == 0.0f, "status: bypass");
    V[MS_P_BYPASS] = 0;
    m.raw_m = 1.0f;
    CHECK(ms_led_run(&led, V, &m, 0, 700, 0.01f) == 1.0f, "clip");
    m.raw_m = 0;
    CHECK(ms_led_run(&led, V, &m, 0, 900, 0.01f) == 1.0f && ms_led_run(&led, V, &m, 0, 1001, 0.01f) == 0.3f, "clip held 300 ms");
    V[MS_P_LED_MODE] = MS_LED_OUT;
    m.out = 0.5f;  // -6 dB
    float x = ms_led_run(&led, V, &m, 0, 2000, 0.01f);
    CHECK(NEAR(x, 1.0f - 6.02f / 48.0f, 0.001f), "output VU at -6 dB: %g", (double)x);
    m.out = 0;
    x = ms_led_run(&led, V, &m, 0, 2100, 0.1f);
    CHECK(NEAR(x, 1.0f - 6.02f / 48.0f - 0.15f, 0.001f), "VU falls 1.5 / s: %g", (double)x);
    V[MS_P_LED_MODE] = MS_LED_GR;
    led.level = 0;
    m.gr_lim = 6;
    m.gr_glue = 3;
    CHECK(ms_led_run(&led, V, &m, 0, 2200, 0.01f) == 0.5f, "gain reduction 6 dB = half");
    V[MS_P_LED_MODE] = MS_LED_MODE;
    V[MS_P_LED_BRIGHT] = 50;
    CHECK(ms_led_run(&led, V, &m, 0, 2300, 0.01f) == 0.04f && ms_led_run(&led, V, &m, true, 2300, 0.01f) == 0.5f,
          "MODE, half brightness");
    V[MS_P_LED_MODE] = MS_LED_OFF;
    m.raw_k = 1;
    CHECK(ms_led_run(&led, V, &m, 1, 2400, 0.01f) == 0.0f, "off, even on clip");
    V[MS_P_LED_MODE] = MS_LED_STATUS;
    V[MS_P_LED_CLIP] = 0;
    CHECK(ms_led_run(&led, V, &m, 0, 2500, 0.01f) == 0.15f, "no clip flash when off");
}

static void test_protocol_ctl(void) {
    ms_host_t host = {NULL, host_out, host_save, host_load, host_apply, host_meters, host_status};
    ms_proto_t pr;
    have_stored = false;
    ms_proto_init(&pr, &host);

    send(&pr, "ctl");
    CHECK(n_lines == 1 && strcmp(lines[0], "ok|ctl") == 0, "no mappings at first");
    send(&pr, "map cv1 glue_thr -30 0");
    CHECK(n_lines == 2 && strcmp(lines[0], "c|cv1|glue_thr|-30|0") == 0 && strcmp(lines[1], "ok|ctl") == 0 && pr.unsaved,
          "map: %s", lines[0]);
    send(&pr, "map mode bypass 1");
    send(&pr, "map hold k_solo 1");
    CHECK(n_lines == 4 && strcmp(lines[1], "c|mode|bypass|1|0") == 0 && strcmp(lines[2], "c|mode|k_solo|1|0") == 0,
          "mode map (0.4.0's hold too): %s", lines[2]);
    const char *bad[] = {"map cv1 glue_thr", "map cv1 glue_thr -30", "map cv3 glue_thr 1 2", "map cv1 nope 1 2",
                         "map mode glue_thr 1", "map cv1 lim_la 0 5", "map cv1 glue_thr x 1"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
        send(&pr, bad[i]);
        CHECK(n_lines == 1 && strncmp(lines[0], "err|map: ", 9) == 0, "%s: %s", bad[i], lines[0]);
    }

    // The knob moves the setting; it reaches the page as a p| line, once.
    float cv[2] = {0.5f, 0.0f};
    int before = applied;
    ms_proto_controls(&pr, cv, false, 0);
    CHECK(applied == before + 1 && P[MS_P_GLUE_THR] == -15, "knob applied: %g", (double)P[MS_P_GLUE_THR]);
    n_lines = 0;
    ms_proto_push(&pr);
    CHECK(n_lines == 1 && strcmp(lines[0], "p|glue_thr|-15") == 0, "push: %s", lines[0]);
    n_lines = 0;
    ms_proto_controls(&pr, cv, false, 10);
    ms_proto_push(&pr);
    CHECK(applied == before + 1 && n_lines == 0, "a knob at rest sends nothing");
    // MODE from the page
    send(&pr, "fire");
    CHECK(n_lines == 3 && strcmp(lines[0], "p|k_solo|1") == 0 && strcmp(lines[1], "p|bypass|1") == 0 &&
              strcmp(lines[2], "ok|fire") == 0,
          "fire: %s", lines[0]);
    send(&pr, "m");
    CHECK(strstr(lines[0], " 0.500 0.000 0 1 0.00") != NULL, "meters show the knobs and MODE engaged: %s", lines[0]);
    send(&pr, "fire off");
    CHECK(n_lines == 3 && strcmp(lines[1], "p|bypass|0") == 0, "fire off: %s", lines[0]);
    send(&pr, "fire click");
    CHECK(n_lines == 3 && strcmp(lines[1], "p|bypass|1") == 0, "0.4.0's fire click: %s", lines[0]);
    send(&pr, "fire on");
    CHECK(n_lines == 1 && strcmp(lines[0], "ok|fire") == 0, "fire on, already on: %s", lines[0]);
    send(&pr, "fire off");
    // The button, set to hold from the page.
    send(&pr, "set mode_act 1");
    CHECK(strcmp(lines[0], "p|mode_act|1") == 0, "mode_act: %s", lines[0]);
    for (uint32_t t = 100; t < 400; t += 10) ms_proto_controls(&pr, cv, true, t);
    CHECK(P[MS_P_K_SOLO] == 0, "hold: not yet at 0.3 s");
    for (uint32_t t = 400; t < 800; t += 10) ms_proto_controls(&pr, cv, true, t);
    CHECK(P[MS_P_K_SOLO] == 1 && P[MS_P_BYPASS] == 1, "hold from the button");

    // Saved with the settings, read back at power-up; the knob sets its setting again.
    send(&pr, "save");
    CHECK(strcmp(lines[0], "ok|save") == 0 && strstr(stored, "set glue_thr -15\n") && strstr(stored, "set mode_act 1\n") &&
              strstr(stored, "map cv1 glue_thr -30 0\nmap mode bypass 1\nmap mode k_solo 1\n"),
          "saved: %s", lines[0]);
    send(&pr, "unmap cv1 glue_thr");
    CHECK(n_lines == 3 && pr.unsaved, "unmap");
    send(&pr, "load");
    CHECK(strcmp(lines[n_lines - 1], "ok|ctl") == 0 && pr.ctl.count[MS_SRC_CV1] == 1 && !pr.unsaved, "load brings it back");
    ms_proto_t pr2;
    ms_proto_init(&pr2, &host);
    CHECK(pr2.ctl.count[MS_SRC_CV1] == 1 && pr2.ctl.count[MS_SRC_MODE] == 2 && pr2.values[MS_P_BYPASS] == 0 &&
              pr2.values[MS_P_K_SOLO] == 0,
          "power-up: mappings back, the switches they moved are not saved");
    cv[0] = 1.0f;
    ms_proto_controls(&pr2, cv, false, 0);
    CHECK(pr2.values[MS_P_GLUE_THR] == 0, "power-up: the knob sets its setting");
    send(&pr, "unmap all");
    CHECK(n_lines == 1 && pr.ctl.count[MS_SRC_MODE] == 0 && pr.unsaved, "unmap all");
    send(&pr, "map cv2 o_flt_hc_f 200 2000");
    send(&pr, "defaults");
    CHECK(pr.ctl.count[MS_SRC_CV2] == 0, "defaults: no mappings");

    // Everything mapped still fits the stored text.
    for (int s = 0; s < MS_SRC_COUNT; s++) {
        for (int i = 0, p = 0; i < MS_CTL_MAPS && p < MS_P_COUNT; p++) {
            if (!ms_ctl_map(&pr.ctl, s, p, 0, 1)) i++;
        }
    }
    send(&pr, "save");
    CHECK(strcmp(lines[0], "ok|save") == 0 && strlen(stored) < MS_SETTINGS_TEXT_MAX * 3 / 4, "all mapped: %zu bytes",
          strlen(stored));
    printf("stored settings, every control mapped full: %zu of %d bytes\n", strlen(stored), MS_SETTINGS_TEXT_MAX);
}

int main(void) {
    test_fast_math();
    test_filters();
    test_order();
    test_crossover_flat();
    test_compressor_curve();
    test_multiband_duck();
    test_limiter();
    test_auto_release();
    test_latency();
    test_glue();
    test_glue_circuit();
    test_parallel();
    test_chain();
    test_fuzz();
    test_params();
    test_protocol();
    test_mute_solo();
    test_ctl();
    test_protocol_ctl();
    printf("%d checks, %d failed\n", checks, failures);
    return failures ? 1 : 0;
}
