// Host tests for the 32bit master chain: ../main/src/ms_dsp.c, ms_params.c, ms_proto.c.
#define _GNU_SOURCE
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
    P[MS_P_K_HP_ON] = 0;
    P[MS_P_K_LIM_ON] = 0;
    P[MS_P_M_HP_ON] = 0;
    P[MS_P_MB_ON] = 0;
    P[MS_P_PAR_ON] = 0;
    P[MS_P_GLUE_ON] = 0;
    P[MS_P_EQ_LO_ON] = 0;
    P[MS_P_EQ_HI_ON] = 0;
    P[MS_P_LIM_ON] = 0;
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

static void test_cuts(void) {
    // Kick sub cut: -3 dB at the set frequency, 12 / 24 dB per octave below it.
    for (int slope = 0; slope < 2; slope++) {
        neutral();
        P[MS_P_K_HP_ON] = 1;
        P[MS_P_K_HP_F] = 25;
        P[MS_P_K_HP_SLOPE] = (float)slope;
        start();
        float at = gain_at(25, 0.5f, true);
        start();
        float below = gain_at(12.5f, 0.5f, true);
        start();
        float pass = gain_at(200, 0.5f, true);
        float want = slope ? -24.1f : -12.3f;
        CHECK(NEAR(at, -3.01f, 0.15f), "sub cut %d: %.2f dB at 25 Hz", slope, at);
        CHECK(NEAR(below, want, 0.4f), "sub cut %d: %.2f dB an octave below", slope, below);
        CHECK(NEAR(pass, 0.0f, 0.05f), "sub cut %d: %.3f dB at 200 Hz", slope, pass);
        printf("kick sub cut 25 Hz, %d dB/oct: %.2f dB at 25 Hz, %.2f dB at 12.5 Hz, %.3f dB at 200 Hz\n",
               slope ? 24 : 12, at, below, pass);
    }
    // The lowest setting still works in single precision.
    neutral();
    P[MS_P_K_HP_ON] = 1;
    P[MS_P_K_HP_F] = 10;
    start();
    float at10 = gain_at(10, 0.5f, true);
    CHECK(NEAR(at10, -3.01f, 0.2f), "10 Hz sub cut: %.2f dB at 10 Hz", at10);

    // Mix low cut and the main cuts.
    neutral();
    P[MS_P_M_HP_ON] = 1;
    P[MS_P_M_HP_F] = 80;
    start();
    float m80 = gain_at(80, 0.5f, false);
    CHECK(NEAR(m80, -3.01f, 0.1f), "mix low cut: %.2f dB at 80 Hz", m80);

    neutral();
    P[MS_P_EQ_HI_ON] = 1;
    P[MS_P_EQ_HI_F] = 8000;
    P[MS_P_EQ_HI_SLOPE] = 1;
    start();
    float h8 = gain_at(8000, 0.5f, false);
    start();
    float h16 = gain_at(16000, 0.5f, false);
    CHECK(NEAR(h8, -3.01f, 0.1f), "high cut: %.2f dB at 8 kHz", h8);
    CHECK(h16 < -24.0f, "high cut 24 dB/oct: %.1f dB at 16 kHz", h16);
    neutral();
    P[MS_P_EQ_LO_ON] = 1;
    P[MS_P_EQ_LO_F] = 30;
    start();
    float l30 = gain_at(30, 0.5f, false);
    CHECK(NEAR(l30, -3.01f, 0.1f), "main low cut: %.2f dB at 30 Hz", l30);
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
    static const float las[] = {0, 0.5f, 1.5f, 5.0f};
    for (size_t l = 0; l < sizeof(las) / sizeof(las[0]); l++) {
        neutral();
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
            if (P[MS_P_LIM_ON] >= 0.5f && i >= 512 && fabsf(buf_o[i]) > ceil) over++;
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
    CHECK(ms_param_clamp(MS_P_K_HP_F, 5) == 10 && ms_param_clamp(MS_P_K_HP_F, 1e9f) == 120, "clamp");
    CHECK(ms_param_clamp(MS_P_GLUE_ATT, 2.6f) == 3 && ms_param_clamp(MS_P_GLUE_ON, 0.4f) == 0, "snap");
    CHECK(ms_param_clamp(MS_P_K_HP_F, NAN) == 25, "NaN -> default");

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
    count = ms_params_import(w, "# old file\nset nothing 3\nset k_hp_f 999\n\nset bypass 1\nfoo\nset m_hp_f 40");
    CHECK(count == 2 && w[MS_P_K_HP_F] == 120 && w[MS_P_M_HP_F] == 40 && w[MS_P_BYPASS] == 0, "import skips junk");
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
    CHECK(applied == 1 && pr.values[MS_P_K_HP_F] == 25 && !pr.unsaved, "init with nothing stored");

    send(&pr, "hello");
    CHECK(n_lines == 1 && strncmp(lines[0], "hello|master|", 13) == 0 && strstr(lines[0], "|proto=1|fs=44100|block=16|io_ms=2.50"),
          "hello: %s", lines[0]);

    send(&pr, "desc");
    CHECK(n_lines == ms_group_count + MS_P_COUNT + 2 && strcmp(lines[n_lines - 1], "ok|desc") == 0, "desc: %d lines",
          n_lines);
    CHECK(strcmp(lines[0], "g|in|Inputs") == 0, "desc group: %s", lines[0]);
    CHECK(strcmp(lines[ms_group_count + MS_P_K_HP_F], "d|k_hp_f|kick|log|10|120|25|0|Hz|1|Sub cut frequency|") == 0,
          "desc line: %s", lines[ms_group_count + MS_P_K_HP_F]);
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
                           "41 57 4.99 0") == 0,
          "meter line: %s", lines[0]);

    send(&pr, "get");
    CHECK(n_lines == MS_P_COUNT + 1 && strcmp(lines[MS_P_K_HP_F], "p|k_hp_f|25") == 0, "get: %s", lines[MS_P_K_HP_F]);

    // set: clamps, answers with the value, marks unsaved, applies.
    int before = applied;
    send(&pr, "set k_hp_f 31.5");
    CHECK(n_lines == 1 && strcmp(lines[0], "p|k_hp_f|31.5") == 0 && pr.unsaved && applied == before + 1 &&
              P[MS_P_K_HP_F] == 31.5f,
          "set: %s", lines[0]);
    send(&pr, "set  k_hp_f   500\r");
    CHECK(strcmp(lines[0], "p|k_hp_f|120") == 0, "set clamps: %s", lines[0]);
    send(&pr, "set nope 1");
    CHECK(strncmp(lines[0], "err|", 4) == 0, "unknown parameter: %s", lines[0]);
    send(&pr, "set k_hp_f abc");
    CHECK(strncmp(lines[0], "err|", 4) == 0 && pr.values[MS_P_K_HP_F] == 120, "bad number: %s", lines[0]);
    send(&pr, "frobnicate");
    CHECK(strncmp(lines[0], "err|", 4) == 0, "unknown command: %s", lines[0]);
    send(&pr, "");
    CHECK(n_lines == 0, "empty line answered");

    // Bypass is a setup aid: it does not make the settings unsaved and is not stored.
    send(&pr, "save");
    CHECK(strcmp(lines[0], "ok|save") == 0 && !pr.unsaved && strstr(stored, "set k_hp_f 120\n"), "save: %s", lines[0]);
    send(&pr, "set bypass 1");
    CHECK(!pr.unsaved && P[MS_P_BYPASS] == 1, "bypass marks unsaved");

    // defaults, then load brings the saved value back and keeps bypass.
    send(&pr, "defaults");
    CHECK(strcmp(lines[n_lines - 1], "ok|defaults") == 0 && pr.values[MS_P_K_HP_F] == 25 && pr.unsaved, "defaults");
    send(&pr, "set bypass 1");
    send(&pr, "load");
    CHECK(strcmp(lines[n_lines - 1], "ok|load") == 0 && n_lines == MS_P_COUNT + 1 && pr.values[MS_P_K_HP_F] == 120 &&
              !pr.unsaved && pr.values[MS_P_BYPASS] == 1,
          "load");

    // A failing store is reported and the settings stay unsaved.
    send(&pr, "set m_hp_f 55");
    fail_save = true;
    send(&pr, "save");
    CHECK(strncmp(lines[0], "err|", 4) == 0 && pr.unsaved, "failed save: %s", lines[0]);
    fail_save = false;

    // Power-up with stored settings: they are applied, bypass is off again.
    ms_proto_t pr2;
    ms_proto_init(&pr2, &host);
    CHECK(pr2.values[MS_P_K_HP_F] == 120 && pr2.values[MS_P_M_HP_F] == ms_param_defs[MS_P_M_HP_F].def && pr2.values[MS_P_BYPASS] == 0 &&
              !pr2.unsaved,
          "power-up from stored settings");
}

int main(void) {
    test_fast_math();
    test_cuts();
    test_crossover_flat();
    test_compressor_curve();
    test_multiband_duck();
    test_limiter();
    test_latency();
    test_glue();
    test_glue_circuit();
    test_parallel();
    test_chain();
    test_fuzz();
    test_params();
    test_protocol();
    printf("%d checks, %d failed\n", checks, failures);
    return failures ? 1 : 0;
}
