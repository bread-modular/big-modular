// Host test of the polysynth ladder filter (includes/audio/apps/polysynth/
// poly_filter.h): MCC bank folding, approximations, cutoff tuning, flat
// passband at every resonance, level as the cutoff comes down, stability at
// full resonance, envelope. Run through ../test.sh.

#include <cmath>
#include <cstdio>

#include "audio/apps/polysynth/poly_filter.h"

static int checks = 0;
static int failures = 0;

#define CHECK(cond, ...)                                  \
    do {                                                  \
        checks++;                                         \
        if (!(cond)) {                                    \
            failures++;                                   \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);   \
            printf(__VA_ARGS__);                          \
            printf("\n");                                 \
        }                                                 \
    } while (0)

static const float SR = 44100.0f;

static float db(double ratio) {
    return (float)(10.0 * log10(ratio));
}

// A filter with the envelope off (depth 0) at cutoff / resonance CC values.
static void setup(PolyFilter& filter, int cutoffCc, int resonanceCc) {
    filter.setParameter(1, 0.0f);
    filter.setParameter(2, resonanceCc / 127.0f);
    filter.setParameter(3, cutoffCc / 127.0f);
    filter.init(SR);
}

// Power gain (dB) of a 0.25-peak sine at hz through the filter.
static float sineGain(PolyFilter& filter, float hz) {
    double in = 0.0, out = 0.0;
    int n = (int)(SR * 1.0f);
    for (int i = 0; i < n; i++) {
        float x = 0.25f * sinf(2.0f * (float)M_PI * hz * i / SR);
        float y = filter.process(x);
        if (i > n / 2) {
            in += x * x;
            out += y * y;
        }
    }
    return db(out / in);
}

// RMS level (dB, relative to the input) of a 0.25-peak saw at hz.
static float sawLevel(PolyFilter& filter, float hz, float* peakOut = nullptr) {
    double in = 0.0, out = 0.0;
    float peak = 0.0f;
    float phase = 0.0f;
    int n = (int)(SR * 1.5f);
    for (int i = 0; i < n; i++) {
        phase += hz / SR;
        if (phase >= 1.0f) phase -= 1.0f;
        float x = 0.25f * (2.0f * phase - 1.0f);
        float y = filter.process(x);
        if (i > n / 3) {
            in += x * x;
            out += y * y;
            peak = fmaxf(peak, fabsf(y));
        }
    }
    if (peakOut != nullptr) *peakOut = peak;
    return db(out / in);
}

static void testBankFolding() {
    for (int p = 0; p < 4; p++) {
        CHECK(PolyFilter::bankAParameter(20 + p) == p, "bank A CC%d", 20 + p);
        CHECK(PolyFilter::bankAParameter(27 + p) == p, "bank B CC%d", 27 + p);
        CHECK(PolyFilter::bankAParameter(85 + p) == p, "bank C CC%d", 85 + p);
    }
    const int outside[] = {0, 1, 19, 24, 26, 31, 84, 89, 127};
    for (int cc : outside) {
        CHECK(PolyFilter::bankAParameter(cc) == -1, "CC%d not MCC", cc);
    }
}

static void testApproximations() {
    float worstExp = 0.0f;
    for (float x = 0.0f; x < 9.0f; x += 0.001f) {
        worstExp = fmaxf(worstExp, fabsf(PolyFilter::fastExp2(x) / exp2f(x) - 1.0f));
    }
    CHECK(worstExp < 2e-4f, "fastExp2 error %g", worstExp);

    float worstTan = 0.0f;
    for (float w = 0.0001f; w <= 1.26f; w += 0.0001f) {
        worstTan = fmaxf(worstTan, fabsf(PolyFilter::fastTan(w) / tanf(w) - 1.0f));
    }
    CHECK(worstTan < 1e-3f, "fastTan error %g", worstTan);
    printf("  approximations: exp2 %.2g, tan %.2g\n", worstExp, worstTan);
}

// No resonance: four matched poles give -12 dB at the cutoff.
static void testCutoffTuning() {
    const int ccs[] = {0, 32, 64, 96, 120};
    for (int cc : ccs) {
        PolyFilter filter;
        setup(filter, cc, 0);
        float hz = PolyFilter::cutoffHz(cc / 127.0f);
        float gain = sineGain(filter, hz);
        printf("  cutoff CC %3d = %7.1f Hz: %.2f dB at the cutoff\n", cc, hz, gain);
        CHECK(fabsf(gain + 12.04f) < 0.5f, "CC %d: %.2f dB at the cutoff", cc, gain);
    }
    CHECK(fabsf(PolyFilter::cutoffHz(0.0f) - PolyFilter::CUTOFF_MAX_HZ) < 1.0f, "CC 0 open");
    CHECK(fabsf(PolyFilter::cutoffHz(1.0f) - PolyFilter::CUTOFF_MIN_HZ) < 0.1f, "CC 127 closed");
}

// Resonance makeup: the passband stays at 0 dB for every resonance below
// self-oscillation, at any cutoff.
static void testFlatPassband() {
    const int resonances[] = {0, 27, 64, 100, 120};
    const int cutoffs[] = {32, 64, 96};
    for (int rc : resonances) {
        for (int cc : cutoffs) {
            PolyFilter filter;
            setup(filter, cc, rc);
            float hz = PolyFilter::cutoffHz(cc / 127.0f) / 16.0f;
            float gain = sineGain(filter, hz);
            CHECK(fabsf(gain) < 0.5f, "res CC %d cutoff CC %d: passband %.2f dB", rc, cc, gain);
        }
    }
}

// The user's complaint: a C3 saw at the power-on resonance (CC 27) held its
// level as the cutoff came down only to drop ~6 dB as soon as it moved (BM).
// Here it stays within 1 dB until the cutoff is near the note (CC 96 =
// 225 Hz for a 131 Hz note), then falls like any 24 dB lowpass.
static void testLevelVsCutoff() {
    printf("  C3 saw, RMS dB vs open, resonance CC 0 / 27 / 64 / 100:\n");
    const int resonances[] = {0, 27, 64, 100};
    for (int cc = 0; cc <= 112; cc += 16) {
        printf("    cutoff CC %3d (%6.0f Hz):", cc, PolyFilter::cutoffHz(cc / 127.0f));
        for (int rc : resonances) {
            PolyFilter filter;
            setup(filter, cc, rc);
            float level = sawLevel(filter, 130.81f);
            printf(" %6.1f", level);
            if (rc == 27 && cc <= 96) {
                CHECK(level > -1.0f && level < 1.0f, "res 27 cutoff CC %d: %.1f dB", cc, level);
            }
            if (rc == 0 && cc <= 64) {
                CHECK(level > -1.5f, "res 0 cutoff CC %d: %.1f dB", cc, level);
            }
        }
        printf("\n");
    }
}

// Full resonance self-oscillates but stays bounded (the input tanh); below
// it the ring dies out once the input stops. Parameter jumps stay finite.
static void testStability() {
    PolyFilter filter;
    setup(filter, 64, 127);
    float peak = 0.0f;
    sawLevel(filter, 65.41f, &peak);
    CHECK(std::isfinite(peak) && peak < 6.0f, "full resonance peak %f", peak);
    float ring = 0.0f;
    for (int i = 0; i < (int)SR; i++) {
        float y = filter.process(0.0f);
        if (i > SR / 2) ring = fmaxf(ring, fabsf(y));
    }
    CHECK(ring > 0.05f && ring < 6.0f, "full resonance self-oscillates: %f", ring);

    setup(filter, 64, 110);
    sawLevel(filter, 65.41f);
    float tail = 0.0f;
    for (int i = 0; i < (int)SR; i++) {
        float y = filter.process(0.0f);
        if (i > SR / 2) tail = fmaxf(tail, fabsf(y));
    }
    CHECK(tail < 1e-4f, "resonance CC 110 rings out: %g", tail);

    // Jumps: every corner of cutoff x resonance, envelope fully open.
    filter.init(SR);
    filter.setParameter(1, 1.0f);
    filter.setGate(true);
    float worst = 0.0f;
    bool finite = true;
    for (int step = 0; step < 64; step++) {
        filter.setParameter(2, (step & 1) ? 1.0f : 0.0f);
        filter.setParameter(3, (step & 2) ? 1.0f : 0.0f);
        filter.setGate(step & 4);
        for (int i = 0; i < 400; i++) {
            float x = (i % 50 < 25) ? 0.5f : -0.5f;
            float y = filter.process(x);
            finite = finite && std::isfinite(y);
            worst = fmaxf(worst, fabsf(y));
        }
    }
    CHECK(finite && worst < 8.0f, "parameter jumps: finite %d peak %f", finite, worst);
}

static void testEnvelope() {
    CHECK(fabsf(PolyFilter::envTimeSeconds(0.0f) - 0.005f) < 1e-5f, "CC20 0 = 5 ms");
    CHECK(fabsf(PolyFilter::envTimeSeconds(1.0f) - 2.0f) < 1e-3f, "CC20 127 = 2 s");

    // Closed cutoff, full depth: the gate opens the filter within ~5 time
    // constants and closes it again on release.
    PolyFilter filter;
    filter.setParameter(0, 0.0f);   // 5 ms
    filter.setParameter(1, 1.0f);
    filter.setParameter(2, 0.0f);
    filter.setParameter(3, 1.0f);
    filter.init(SR);
    for (int i = 0; i < (int)(0.05f * SR); i++) filter.process(0.0f);
    CHECK(fabsf(filter.currentCutoffHz() - PolyFilter::CUTOFF_MIN_HZ) < 1.0f,
          "gate off: %f Hz", filter.currentCutoffHz());
    filter.setGate(true);
    for (int i = 0; i < (int)(0.05f * SR); i++) filter.process(0.0f);
    CHECK(filter.currentCutoffHz() > 0.95f * PolyFilter::CUTOFF_MAX_HZ,
          "gate on: %f Hz", filter.currentCutoffHz());
    filter.setGate(false);
    for (int i = 0; i < (int)(0.1f * SR); i++) filter.process(0.0f);
    CHECK(filter.currentCutoffHz() < 1.1f * PolyFilter::CUTOFF_MIN_HZ,
          "released: %f Hz", filter.currentCutoffHz());

    // Half depth from the bottom: + CUTOFF_OCTAVES / 2.
    filter.setParameter(1, 0.5f);
    filter.setGate(true);
    for (int i = 0; i < (int)(0.1f * SR); i++) filter.process(0.0f);
    float expected = PolyFilter::CUTOFF_MIN_HZ * exp2f(0.5f * PolyFilter::CUTOFF_OCTAVES);
    CHECK(fabsf(filter.currentCutoffHz() / expected - 1.0f) < 0.01f,
          "half depth %f Hz, expected %f", filter.currentCutoffHz(), expected);
}

int main() {
    testBankFolding();
    testApproximations();
    testCutoffTuning();
    testFlatPassband();
    testLevelVsCutoff();
    testStability();
    testEnvelope();
    printf("sim_poly_filter: %d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
