// Host test of the sampler P1 / P2 DSP (includes/audio/apps/sampler/
// sampler_dsp.h): P1 kick drive on group A, P2 resonance of the group A
// highpass (P4, the DjHighpass) with its peak guard. Renders the baked-in kick
// (s01.h), and a groove (the kick + noise hats + clap) for the P2 highs,
// through the same group A chain as sampler_app.h (drive -> P3
// lowpass -> FX -> P4 highpass -> guard -> clip; FX1 / FX2 left out) and
// checks it against the earlier chain (P3 lowpass -> P4 highpass, Biquad
// Q 0.707). Run through ../test.sh.
//
//   ./.build/host/sim_sampler --wav <dir>   # also write listening WAVs to <dir>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "audio/mod/Biquad.h"
#include "audio/apps/sampler/sampler_dsp.h"
#include "audio/samples/s01.h"

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
static const float P4_TOP = SamplerDsp::P4_MAX_HZ;  // P4 fully up

static float db(double ratio) {
    return (float)(20.0 * log10(ratio));
}

// The kick as the app plays it (raw s01_wav bytes from offset 0, as BM),
// at a velocity, followed by silence; repeated every `period` samples.
static std::vector<float> kickPattern(int hits, int period, float velocity) {
    const int16_t* kick = (const int16_t*)s01_wav;
    int len = (int)(s01_wav_len / 2);
    std::vector<float> out((size_t)hits * period, 0.0f);
    for (int h = 0; h < hits; h++) {
        for (int i = 0; i < len && i < period; i++) {
            out[(size_t)h * period + i] = (kick[i] / 32768.0f) * velocity;
        }
    }
    return out;
}

// A DJ-filter test loop: the kick on the beat plus noise hats on every 16th
// (open on the off-beat) and a noise clap on 2 and 4, as an uploaded group A
// kit or the Rumble burst would add the highs a DJ highpass sweeps over.
static std::vector<float> groove(int beats, int beat) {
    std::vector<float> out = kickPattern(beats, beat, 0.8f);
    uint32_t seed = 12345;
    auto noise = [&seed]() {
        seed = seed * 1664525u + 1013904223u;
        return (float)(int32_t)seed / 2147483648.0f;
    };
    int step = beat / 4;
    float lastN = 0.0f, bp1 = 0.0f, bp2 = 0.0f;
    for (size_t i = 0; i < out.size(); i++) {
        int pos = (int)(i % (size_t)step);
        int sixteenth = (int)(i / (size_t)step) % 16;
        float n = noise();
        // Hat: differenced noise (bright), 25 ms closed / 90 ms open.
        float hatMs = sixteenth % 4 == 2 ? 90.0f : 25.0f;
        float hatLevel = sixteenth % 4 == 2 ? 0.22f : 0.12f;
        float hat = hatLevel * 0.5f * (n - lastN) * expf(-1000.0f * pos / (hatMs * SR));
        lastN = n;
        // Clap: noise through a ~1.2 kHz resonator, 2 and 4.
        float clap = 0.0f;
        int quarter = (int)(i / (size_t)beat) % 4;
        int inBeat = (int)(i % (size_t)beat);
        const float w = 2.0f * (float)M_PI * 1200.0f / SR;
        float bp = 2.0f * 0.96f * cosf(w) * bp1 - 0.96f * 0.96f * bp2 + n;
        bp2 = bp1;
        bp1 = bp;
        if (quarter == 1 || quarter == 3) {
            clap = 0.03f * bp * expf(-1000.0f * inBeat / (120.0f * SR));
        }
        out[i] += hat + clap;
    }
    return out;
}

static std::vector<float> sine(float hz, float amp, int n) {
    std::vector<float> out(n);
    for (int i = 0; i < n; i++) {
        out[i] = amp * sinf(2.0f * (float)M_PI * hz * i / SR);
    }
    return out;
}

static float peak(const std::vector<float>& x, size_t from = 0) {
    float p = 0.0f;
    for (size_t i = from; i < x.size(); i++) p = fmaxf(p, fabsf(x[i]));
    return p;
}

static float rms(const std::vector<float>& x, size_t from = 0, size_t to = 0) {
    if (to == 0) to = x.size();
    double s = 0.0;
    for (size_t i = from; i < to; i++) s += (double)x[i] * x[i];
    return (float)sqrt(s / (double)(to - from));
}

// Amplitude of harmonic k of hz in x[from..] (single-bin DFT, whole periods).
static float harmonic(const std::vector<float>& x, float hz, int k, size_t from) {
    double re = 0.0, im = 0.0;
    size_t n = x.size() - from;
    for (size_t i = 0; i < n; i++) {
        double ph = 2.0 * M_PI * hz * k * (double)i / SR;
        re += x[from + i] * cos(ph);
        im += x[from + i] * sin(ph);
    }
    return (float)(2.0 * sqrt(re * re + im * im) / (double)n);
}

// Group A chain, as sampler_app.h. p1 / p2 are the 0..1 knob values;
// lpHz / hpHz the P3 / P4 cutoffs.
struct GroupA {
    KickDrive drive;
    Biquad lowpass{Biquad::LOWPASS};
    Biquad highpass{Biquad::HIGHPASS};
    DjHighpass dj;
    OutputGuard guard;
    bool driveOn = false;
    bool resonanceOn = false;

    GroupA(float p1, float p2, float lpHz, float hpHz) {
        driveOn = drive.setDrive(p1);
        drive.init(SR);
        lowpass.init(SR);
        highpass.init(SR);
        guard.init(SR);
        lowpass.setCutoff(lpHz);
        setP4(hpHz);
        setP2(p2);
        dj.init(SR);
    }

    // applyP4 / applyP2 of sampler_app.h.
    void setP4(float hz) {
        highpass.setCutoff(hz);
        dj.setCutoff(hz);
    }

    void setP2(float p2) {
        resonanceOn = dj.setResonance(p2);
    }

    float process(float x) {
        x = drive.process(x);
        x = lowpass.process(x);
        x = dj.process(x, highpass.process(x));
        x = guard.process(x, resonanceOn);
        return driveOn ? SamplerDsp::outputClip(x) : x;
    }
};

// The earlier group A chain: P3 lowpass -> P4 highpass at Biquad's own Q.
static std::vector<float> earlierChain(const std::vector<float>& in, float lpHz, float hpHz) {
    Biquad lowpass{Biquad::LOWPASS};
    Biquad highpass{Biquad::HIGHPASS};
    lowpass.init(SR);
    highpass.init(SR);
    lowpass.setCutoff(lpHz);
    highpass.setCutoff(hpHz);
    std::vector<float> out(in.size());
    for (size_t i = 0; i < in.size(); i++) {
        out[i] = highpass.process(lowpass.process(in[i]));
    }
    return out;
}

static std::vector<float> run(GroupA& chain, const std::vector<float>& in) {
    std::vector<float> out(in.size());
    for (size_t i = 0; i < in.size(); i++) out[i] = chain.process(in[i]);
    return out;
}

static std::vector<float> driveOnly(float p1, const std::vector<float>& in) {
    KickDrive drive;
    drive.setDrive(p1);
    drive.init(SR);
    std::vector<float> out(in.size());
    for (size_t i = 0; i < in.size(); i++) out[i] = drive.process(in[i]);
    return out;
}

// P3 / P4 knob curves of sampler_app.h (applyP3 / applyP4), knob 0..1.
static float p3Cutoff(float knob) {
    float n = 1.0f - knob;
    return 50.0f * powf(20000.0f / 50.0f, n * n);
}

static float p4Cutoff(float knob) {
    return SamplerDsp::p4Cutoff(knob);
}

// --- tests ----------------------------------------------------------------

// P1 / P2 fully down (and inside the dead zone): bit-exact earlier chain.
static void testZeroIsEarlier() {
    std::vector<float> kick = kickPattern(3, 22050, 1.0f);
    const float lps[] = {p3Cutoff(0.0f), p3Cutoff(0.5f), p3Cutoff(0.9f)};
    const float hps[] = {p4Cutoff(0.0f), p4Cutoff(0.2f), p4Cutoff(0.5f), p4Cutoff(0.8f)};
    const float zeros[] = {0.0f, 0.01f, SamplerDsp::DEAD_ZONE};
    for (float lp : lps) {
        for (float hp : hps) {
            std::vector<float> ref = earlierChain(kick, lp, hp);
            for (float z : zeros) {
                GroupA chain(z, z, lp, hp);
                std::vector<float> out = run(chain, kick);
                bool same = memcmp(out.data(), ref.data(), out.size() * sizeof(float)) == 0;
                CHECK(same, "P1 = P2 = %.3f, LP %.0f Hz, HP %.0f Hz differs from the earlier chain", z, lp, hp);
            }
        }
    }
    DjHighpass dj;
    CHECK(!dj.setResonance(0.0f) && !dj.setResonance(SamplerDsp::DEAD_ZONE), "P2 in the dead zone is on");
}

// P2 knob curve: Q rises monotonically and fast (an aggressive DJ-filter
// curve: +20 dB by half way, +30 dB at the top). Over cutoff (Pioneer DJM
// style): no peak (flat Butterworth) up to RES_START_HZ, so no mud, rising
// through the high mids, full from RES_FULL_HZ to the top of the sweep. The
// P4 knob reaches RES_FULL_HZ at its 25 % mark.
// Peak at the cutoff = Q x Q_BUTTER1.
static void testCurves() {
    auto qAt = [](float hz, float p2) {
        DjHighpass dj;
        dj.init(SR);
        dj.setCutoff(hz);
        dj.setResonance(p2);
        return dj.getQ();
    };
    float lastQ = 0.0f;
    for (int i = 0; i <= 100; i++) {
        float q = qAt(P4_TOP, i / 100.0f);
        CHECK(q >= lastQ, "Q not monotonic in P2 at %d", i);
        lastQ = q;
    }
    lastQ = 0.0f;
    for (int i = 0; i <= 100; i++) {
        float q = qAt(p4Cutoff(i / 100.0f), 1.0f);
        CHECK(q >= lastQ - 1e-4f, "Q not monotonic in P4 at %d", i);
        lastQ = q;
    }
    printf("  P2 curve at the top of P4 (%.0f Hz): Q (dB at the cutoff)\n   ", P4_TOP);
    for (float p2 : {0.1f, 0.25f, 0.5f, 0.75f, 1.0f}) {
        printf("  %.2f: %4.1f (%+.0f)", p2, qAt(P4_TOP, p2), db(DjHighpass::Q_BUTTER1 * qAt(P4_TOP, p2)));
    }
    printf("\n  P2 = 1 vs cutoff, dB at the cutoff:\n   ");
    for (float hz : {20.0f, 100.0f, 250.0f, 500.0f, 600.0f, 700.0f, 775.0f, 900.0f, 1200.0f, 3000.0f, P4_TOP}) {
        printf("  %.0f Hz %+.1f", hz, db(DjHighpass::Q_BUTTER1 * qAt(hz, 1.0f)));
    }
    printf("\n  P4 knob vs cutoff:");
    for (float k : {0.0f, 0.1f, 0.2f, 0.25f, 0.5f, 0.75f, 1.0f}) {
        printf("  %.2f %.0f Hz", k, p4Cutoff(k));
    }
    printf("\n  P2 = 1 vs P4 knob, dB at the cutoff:\n   ");
    for (float k : {0.15f, 0.18f, 0.2f, 0.22f, 0.24f, 0.25f, 0.3f}) {
        printf("  %.2f %+.1f", k, db(DjHighpass::Q_BUTTER1 * qAt(p4Cutoff(k), 1.0f)));
    }
    printf("\n");
    // P4: 20 Hz .. 20 kHz, two exponential segments meeting at the 25 %
    // mark on RES_FULL_HZ, so full P2 resonance arrives there.
    CHECK(p4Cutoff(0.0f) == 20.0f, "P4 bottom %.2f Hz", p4Cutoff(0.0f));
    CHECK(fabsf(p4Cutoff(1.0f) - 20000.0f) < 1.0f && P4_TOP == 20000.0f, "P4 top %.1f Hz", p4Cutoff(1.0f));
    CHECK(fabsf(p4Cutoff(0.25f) - DjHighpass::RES_FULL_HZ) < 0.1f, "P4 25 %% %.1f Hz", p4Cutoff(0.25f));
    for (int i = 0; i <= 100; i++) {
        float k = i / 100.0f;
        float ref = k <= 0.25f ? 20.0f * powf(1200.0f / 20.0f, k / 0.25f)
                               : 1200.0f * powf(20000.0f / 1200.0f, (k - 0.25f) / 0.75f);
        CHECK(fabsf(p4Cutoff(k) / ref - 1.0f) < 1e-4f, "P4 %d: %.2f Hz vs %.2f Hz", i, p4Cutoff(k), ref);
        if (i > 0) CHECK(p4Cutoff(k) > p4Cutoff((i - 1) / 100.0f), "P4 not rising at %d", i);
        float q = qAt(p4Cutoff(k), 1.0f);
        if (i >= 25) CHECK(fabsf(q - DjHighpass::Q_MAX) < 1e-2f, "P4 %d: Q %.2f, not full", i, q);
        if (p4Cutoff(k) <= DjHighpass::RES_START_HZ) CHECK(fabsf(q - DjHighpass::Q_BASE) < 1e-3f, "P4 %d: Q %.3f, peak", i, q);
    }
    // Continuous at the 25 % mark (no jump in the cutoff).
    CHECK(fabsf(p4Cutoff(0.2501f) / p4Cutoff(0.2499f) - 1.0f) < 5e-3f, "P4 jumps at 25 %%");
    for (float hz : {20.0f, 60.0f, 150.0f, 300.0f, DjHighpass::RES_START_HZ}) {
        CHECK(fabsf(qAt(hz, 1.0f) - DjHighpass::Q_BASE) < 1e-3f, "Q at %.0f Hz %.3f (no peak expected)", hz, qAt(hz, 1.0f));
    }
    for (float hz : {DjHighpass::RES_FULL_HZ, 1500.0f, 3000.0f, 12000.0f, P4_TOP}) {
        CHECK(fabsf(qAt(hz, 1.0f) - DjHighpass::Q_MAX) < 1e-2f, "Q max at %.0f Hz %.2f", hz, qAt(hz, 1.0f));
    }
    float mid = db(DjHighpass::Q_BUTTER1 * qAt(775.0f, 1.0f));
    CHECK(mid > 10.0f && mid < 22.0f, "P2 1 at 775 Hz %.1f dB (fade-in)", mid);
    CHECK(db(DjHighpass::Q_BUTTER1 * qAt(P4_TOP, 0.25f)) > 12.0f, "P2 0.25 Q only %.2f", qAt(P4_TOP, 0.25f));
    CHECK(db(DjHighpass::Q_BUTTER1 * qAt(P4_TOP, 0.5f)) > 20.0f, "P2 0.5 Q only %.2f", qAt(P4_TOP, 0.5f));
    CHECK(db(DjHighpass::Q_BUTTER1 * DjHighpass::Q_MAX) > 30.0f, "P2 1 peak only %.1f dB", db(DjHighpass::Q_BUTTER1 * DjHighpass::Q_MAX));
    CHECK(qAt(P4_TOP, 1.5f) <= DjHighpass::Q_MAX + 1e-3f, "Q clamps");
}

// Drive on the kick: denser (lower crest factor) and louder (RMS) as P1 goes
// up, the tail comes up. The drive stage alone stays bounded; the full chain
// (P3 open, P4 at its 20 Hz minimum, where the square body overshoots) stays
// under the guard limit and gets louder than the dry kick.
static void testDriveOnKick() {
    std::vector<float> kick = kickPattern(1, 22050, 1.0f);
    const int body = (int)(0.25f * SR);       // first 250 ms
    const int tailFrom = (int)(0.25f * SR);   // 250..450 ms
    const int tailTo = (int)(0.45f * SR);
    float lastRms = rms(kick, 0, body);
    float lastCrest = peak(kick) / lastRms;
    float dryTail = rms(kick, tailFrom, tailTo);
    std::vector<float> dryChain = earlierChain(kick, p3Cutoff(0.0f), p4Cutoff(0.0f));
    float dryChainRms = rms(dryChain, 0, body);
    float dryChainHit = rms(dryChain, 0, tailTo);
    printf("  drive on the kick (velocity 1); stage alone | full chain (P3 open, P4 20 Hz):\n");
    printf("    P1    peak   body RMS dB  crest dB  tail dB | peak   body dB  hit dB vs dry\n");
    printf("    0.00  %.3f  %+6.2f       %5.2f     %+6.2f  | %.3f  %+6.2f   %+6.2f\n",
           peak(kick), db(lastRms), db(lastCrest), 0.0f, peak(dryChain), 0.0f, 0.0f);
    for (int step = 1; step <= 10; step++) {
        float p1 = step / 10.0f;
        std::vector<float> out = driveOnly(p1, kick);
        float r = rms(out, 0, body);
        float p = peak(out);
        float crest = p / r;
        float tail = rms(out, tailFrom, tailTo);
        GroupA chain(p1, 0.0f, p3Cutoff(0.0f), p4Cutoff(0.0f));
        std::vector<float> full = run(chain, kick);
        float fullPeak = peak(full);
        float fullRms = rms(full, 0, body);
        float fullHit = rms(full, 0, tailTo);
        printf("    %.2f  %.3f  %+6.2f       %5.2f     %+6.2f  | %.3f  %+6.2f   %+6.2f\n",
               p1, p, db(r), db(crest), db(tail / dryTail), fullPeak, db(fullRms / dryChainRms),
               db(fullHit / dryChainHit));
        // The DC blocker tilts the square body a little past the ceiling.
        CHECK(p < 1.2f, "P1 %.1f drive stage peak %.3f", p1, p);
        CHECK(fullPeak <= OutputGuard::GUARD_LIMIT + 1e-6f, "P1 %.1f chain peak %.3f over the guard", p1, fullPeak);
        CHECK(fullRms > dryChainRms, "P1 %.1f chain quieter than dry (%.2f dB)", p1, db(fullRms / dryChainRms));
        CHECK(db(r) >= db(lastRms) - 0.1f, "P1 %.1f body RMS fell", p1);
        // Denser up to the middle; past it the bias fades and the square's
        // edges sharpen, which lifts the crest a little again.
        if (step <= 5) {
            CHECK(db(crest) <= db(lastCrest) + 0.1f, "P1 %.1f crest factor rose", p1);
        }
        lastRms = r;
        lastCrest = crest;
        if (step == 10) {
            CHECK(db(crest) < db(peak(kick) / rms(kick, 0, body)) - 2.5f, "full drive crest %.2f dB: not square-ish", db(crest));
            CHECK(db(fullRms / dryChainRms) > 2.0f, "full drive chain body only %+.2f dB", db(fullRms / dryChainRms));
            CHECK(db(fullHit / dryChainHit) > 3.0f, "full drive chain hit only %+.2f dB", db(fullHit / dryChainHit));
            CHECK(db(tail / dryTail) > 12.0f, "full drive tail +%.1f dB only", db(tail / dryTail));
        }
    }
}

// Drive on a 55 Hz sine: harmonics grow with P1, even ones from the bias,
// no DC left after the blocker.
static void testDriveHarmonics() {
    const float hz = 55.0f;
    const int n = (int)SR * 2;
    std::vector<float> in = sine(hz, 0.5f, n);
    size_t from = (size_t)SR;  // settled, 55 whole periods
    float lastThd = 0.0f;
    printf("  drive on a 0.5 sine at 55 Hz:\n");
    printf("    P1    H1     H2 dB    H3 dB    THD %%   DC\n");
    for (int step = 0; step <= 10; step += 2) {
        float p1 = step / 10.0f;
        std::vector<float> out = driveOnly(p1, in);
        float h1 = harmonic(out, hz, 1, from);
        float h2 = harmonic(out, hz, 2, from);
        float h3 = harmonic(out, hz, 3, from);
        double hs = 0.0;
        for (int k = 2; k <= 15; k++) {
            float h = harmonic(out, hz, k, from);
            hs += (double)h * h;
        }
        float thd = (float)sqrt(hs) / h1;
        double mean = 0.0;
        for (size_t i = from; i < out.size(); i++) mean += out[i];
        mean /= (double)(out.size() - from);
        printf("    %.1f   %.3f  %+7.1f  %+7.1f  %6.2f  %+.4f\n", p1, h1, db(h2 / h1 + 1e-9), db(h3 / h1 + 1e-9), 100.0f * thd, mean);
        if (step == 0) {
            CHECK(thd < 1e-4f, "P1 0 THD %.5f", thd);
        } else {
            CHECK(thd > lastThd, "P1 %.1f THD did not rise", p1);
            if (step <= 6) {
                CHECK(db(h2 / h1) > -40.0f, "P1 %.1f no even harmonic (H2 %.1f dB)", p1, db(h2 / h1));
            }
            CHECK(fabs(mean) < 0.003, "P1 %.1f DC %.4f", p1, mean);
        }
        lastThd = thd;
    }
    CHECK(lastThd > 0.25f, "full drive THD %.2f", lastThd);
}

// Turning P1 while a 55 Hz tone plays: smoothed, so no step bigger than the
// tone's own slope allows; the level follows the knob without a jump at the
// bottom of the knob (wet fade-in).
static void testDriveSweepSmooth() {
    const float hz = 55.0f;
    const int n = (int)(SR * 2.0f);
    std::vector<float> in = sine(hz, 0.5f, n);
    KickDrive drive;
    drive.setDrive(0.0f);
    drive.init(SR);
    float maxStep = 0.0f;
    float last = 0.0f;
    for (int i = 0; i < n; i++) {
        // ADC-like steps every 2 ms (88 samples), 0 -> 1 over 1 s, back down.
        if (i % 88 == 0) {
            float t = (float)i / SR;
            float knob = t < 1.0f ? t : 2.0f - t;
            drive.setDrive(knob);
        }
        float y = drive.process(in[i]);
        if (i > 0) maxStep = fmaxf(maxStep, fabsf(y - last));
        last = y;
    }
    // A full-scale square-ish 55 Hz tone has steep edges after the clip; a
    // click would be a step near the full range.
    printf("  P1 sweep on a 55 Hz tone: biggest sample step %.3f\n", maxStep);
    CHECK(maxStep < 0.25f, "P1 sweep step %.3f (click)", maxStep);
    CHECK(std::isfinite(last), "P1 sweep not finite");

    // Level just above the dead zone is close to the dry level.
    std::vector<float> kick = kickPattern(1, 22050, 1.0f);
    float dry = rms(kick);
    float justOn = rms(driveOnly(SamplerDsp::DEAD_ZONE + 0.005f, kick));
    printf("  P1 just above the dead zone: %+.2f dB vs off\n", db(justOn / dry));
    CHECK(fabsf(db(justOn / dry)) < 0.5f, "P1 just above off jumps %.2f dB", db(justOn / dry));
}

// Gain (dB) of the P4 highpass at hz (small sine, settled), as the app runs it.
static float hpGain(float cut, float p2, float hz, float amp = 0.0005f) {
    Biquad flat{Biquad::HIGHPASS};
    flat.init(SR);
    flat.setCutoff(cut);
    DjHighpass dj;
    dj.setCutoff(cut);
    dj.setResonance(p2);
    dj.init(SR);
    // Long enough for the Q 40 ring at the lowest cutoff to settle.
    int n = (int)(SR * 3.0f);
    std::vector<float> in = sine(hz, amp, n);
    std::vector<float> out(n);
    for (int i = 0; i < n; i++) out[i] = dj.process(in[i], flat.process(in[i]));
    return db(rms(out, n / 2) / rms(in, n / 2));
}

// DJ highpass response (small signal, no squelch): flat 24 dB/oct
// Butterworth (-3 dB at the cutoff, no peak) under RES_START_HZ, peak at the
// cutoff = Q in the high mids and highs, passband at 0 dB.
static void testResonanceResponse() {
    printf("  P4 highpass response (dB, small sines):\n");
    printf("    cutoff  P2    peak   f/4      f/2      f        2f       10f\n");
    for (float cut : {40.0f, 150.0f, 500.0f, 650.0f, 900.0f, 1200.0f, 3000.0f, 6000.0f}) {
        float lastPeak = -100.0f;
        for (float p2 : {0.0f, 0.25f, 0.5f, 1.0f}) {
            DjHighpass dj;
            dj.init(SR);
            dj.setCutoff(cut);
            dj.setResonance(p2);
            // Peak at the cutoff: Q, or the two stages' Q_BUTTER1 x Q.
            float q = p2 == 0.0f ? 0.707f : DjHighpass::Q_BUTTER1 * dj.getQ();
            bool resonant = p2 > 0.0f && DjHighpass::focus(cut) > 0.0f;
            const float mult[] = {0.25f, 0.5f, 1.0f, 2.0f, 10.0f};
            float g[5];
            for (int m = 0; m < 4; m++) g[m] = hpGain(cut, p2, cut * mult[m]);
            // 10f only while it is under 16 kHz (the passband).
            bool pass = cut * mult[4] < 16000.0f;
            g[4] = pass ? hpGain(cut, p2, cut * mult[4]) : 0.0f;
            printf("    %5.0f   %.2f  %5.2f  %+7.1f  %+7.1f  %+7.1f  %+7.1f  ", cut, p2, q, g[0], g[1], g[2], g[3]);
            if (pass) printf("%+7.2f\n", g[4]); else printf("    -\n");
            if (p2 == 0.0f) {
                // The earlier 12 dB/oct Biquad.
                CHECK(fabsf(g[2] + 3.01f) < 0.2f, "P2 0 at %.0f Hz: %.2f dB at the cutoff", cut, g[2]);
                CHECK(g[0] < -20.0f && g[0] > -28.0f, "P2 0 at %.0f Hz: f/4 %.1f dB", cut, g[0]);
            } else {
                CHECK(fabsf(g[2] - db(q)) < 0.5f, "P2 %.2f at %.0f Hz: %.2f dB at the cutoff, Q %.2f dB", p2, cut, g[2], db(q));
                CHECK(g[0] < -44.0f, "P2 %.2f at %.0f Hz: f/4 only %.1f dB (not 24 dB/oct)", p2, cut, g[0]);
                CHECK(g[1] < -18.0f, "P2 %.2f at %.0f Hz: f/2 only %.1f dB", p2, cut, g[1]);
                if (resonant) {
                    CHECK(g[2] > lastPeak, "P2 %.2f at %.0f Hz: peak not rising", p2, cut);
                } else {
                    // No peak anywhere: the flat 4th-order Butterworth.
                    CHECK(fabsf(g[2] + 3.01f) < 0.2f && g[3] < 0.1f, "P2 %.2f at %.0f Hz: %.2f / %.2f dB, not flat", p2, cut, g[2], g[3]);
                }
            }
            if (pass) {
                CHECK(fabsf(g[4]) < 0.2f, "P2 %.2f at %.0f Hz: passband %.2f dB", p2, cut, g[4]);
            }
            lastPeak = g[2];
        }
    }
    CHECK(hpGain(12000.0f, 1.0f, 12000.0f) > 29.5f, "full P2 at 12 kHz: %.1f dB", hpGain(12000.0f, 1.0f, 12000.0f));
    CHECK(hpGain(DjHighpass::RES_FULL_HZ, 1.0f, DjHighpass::RES_FULL_HZ) > 29.5f, "full P2 at RES_FULL_HZ: %.1f dB",
          hpGain(DjHighpass::RES_FULL_HZ, 1.0f, DjHighpass::RES_FULL_HZ));
}

// Squelch: a big tone on the cutoff rings at a bounded level (not Q times
// the input), a quiet one stays clean, and the ring dies out after the input
// stops (no self-oscillation).
static void testSquelch() {
    printf("  P2 = 1, tone on the cutoff: output peak vs input (linear would be x32)\n");
    for (float cut : {DjHighpass::RES_FULL_HZ, 3000.0f, 6000.0f}) {
        printf("    %5.0f Hz:", cut);
        for (float amp : {0.01f, 0.05f, 0.2f, 0.5f, 1.0f}) {
            Biquad flat{Biquad::HIGHPASS};
            flat.init(SR);
            flat.setCutoff(cut);
            DjHighpass dj;
            dj.setCutoff(cut);
            dj.setResonance(1.0f);
            dj.init(SR);
            int n = (int)(SR * 1.0f);
            std::vector<float> in = sine(cut, amp, n);
            in.resize((size_t)n * 2, 0.0f);  // then 1 s of silence
            std::vector<float> out(in.size());
            for (size_t i = 0; i < in.size(); i++) out[i] = dj.process(in[i], flat.process(in[i]));
            float p = peak(out, (size_t)n / 2);
            float settled = 0.0f;
            for (int i = n / 2; i < n; i++) settled = fmaxf(settled, fabsf(out[i]));
            // Decaying ring after the tone stops (no self-oscillation),
            // counted in periods (the Q_MAX 60 stage decays by e^-pi every
            // Q periods, linear x0.21 over 30): under 0.3 from 10 to 40
            // periods (sample peaks read a few % off at 6 kHz, ~7 samples a
            // period), gone after 300.
            float period = SR / cut;
            float early = peak(out, (size_t)n + (size_t)(10.0f * period));
            float late = peak(out, (size_t)n + (size_t)(40.0f * period));
            float gone = peak(out, (size_t)n + (size_t)(300.0f * period));
            printf("  %.2f -> %.2f", amp, settled);
            CHECK(std::isfinite(p), "squelch %.0f Hz %.2f not finite", cut, amp);
            CHECK(settled < 3.5f, "squelch %.0f Hz in %.2f: %.2f", cut, amp, settled);
            if (amp >= 0.2f) {
                // Bounded: under half the linear x32.
                CHECK(settled < 16.0f * amp, "squelch %.0f Hz in %.2f: %.2f not squelched", cut, amp, settled);
            } else {
                // Quiet: clean, close to the linear peak.
                CHECK(settled > 0.7f * DjHighpass::Q_BUTTER1 * DjHighpass::Q_MAX * amp, "%.0f Hz in %.2f: %.2f squelched", cut, amp, settled);
            }
            CHECK(late < 0.3f * early && gone < 1e-3f, "%.0f Hz in %.2f: ring %.4f -> %.4f -> %.5f not decaying", cut, amp, early, late, gone);
        }
        printf("\n");
    }
}

// Amplitude of the hz component of x[from..to) (single-bin DFT).
static float toneAt(const std::vector<float>& x, float hz, size_t from, size_t to) {
    double re = 0.0, im = 0.0;
    for (size_t i = from; i < to; i++) {
        double ph = 2.0 * M_PI * hz * (double)i / SR;
        re += x[i] * cos(ph);
        im += x[i] * sin(ph);
    }
    return (float)(2.0 * sqrt(re * re + im * im) / (double)(to - from));
}

// Share of x[from..to) at hz: the hz component over the whole output (1 = a
// pure sine at hz).
static float prominence(const std::vector<float>& x, float hz, size_t from, size_t to) {
    return toneAt(x, hz, from, to) / (sqrtf(2.0f) * rms(x, from, to));
}

// Share of the energy of x[from..to) within a 1/6 octave band around hz
// (RBJ bandpass, 0 dB peak, run from the start): noise rings at the cutoff
// as a narrow band, not a single tone.
static float bandShare(const std::vector<float>& x, float hz, size_t from, size_t to) {
    double w = 2.0 * M_PI * hz / SR, q = 8.6;
    double alpha = sin(w) / (2.0 * q), a0 = 1.0 + alpha;
    double b0 = alpha / a0, b2 = -alpha / a0, a1 = -2.0 * cos(w) / a0, a2 = (1.0 - alpha) / a0;
    double x1 = 0, x2 = 0, y1 = 0, y2 = 0, band = 0, all = 0;
    for (size_t i = 0; i < to; i++) {
        double y = b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2;
        x2 = x1; x1 = x[i]; y2 = y1; y1 = y;
        if (i >= from) {
            band += y * y;
            all += (double)x[i] * x[i];
        }
    }
    return (float)(band / all);
}

// Renders `in` through group A, returning the guard gain just before `mark`.
static std::vector<float> runMarked(GroupA& chain, const std::vector<float>& in, size_t mark, float& gainAtMark) {
    std::vector<float> out(in.size());
    gainAtMark = 1.0f;
    for (size_t i = 0; i < in.size(); i++) {
        out[i] = chain.process(in[i]);
        if (i + 1 == mark) gainAtMark = chain.guard.getGain();
    }
    return out;
}

// Low cutoffs (the kick, the bass, the low mids): P2 adds no ring, no boom
// and no level, only the steeper slope, so the low end does not get muddy.
static void testNoMud() {
    const int beat = 22050;  // 120 BPM
    std::vector<float> kick = kickPattern(4, beat, 1.0f);
    const size_t last = (size_t)3 * beat;
    const size_t win = (size_t)(0.3f * SR);
    printf("  kick through P4 + P2 (open P3, no drive), 4th hit, first 300 ms:\n");
    printf("    HP Hz  share at the cutoff (%%) P2 0 / 1 | level P2 1 vs 0 | late tail P2 1 vs 0 | peak\n");
    for (float hp : {40.0f, 60.0f, 90.0f, 150.0f, 200.0f, 300.0f, DjHighpass::RES_START_HZ}) {
        GroupA flat(0.0f, 0.0f, p3Cutoff(0.0f), hp);
        GroupA dj(0.0f, 1.0f, p3Cutoff(0.0f), hp);
        std::vector<float> a = run(flat, kick);
        std::vector<float> b = run(dj, kick);
        float s0 = prominence(a, hp, last, last + win);
        float s1 = prominence(b, hp, last, last + win);
        float level = db(rms(b, last, last + win) / rms(a, last, last + win));
        size_t from = last + (size_t)(0.3f * SR), to = last + (size_t)(0.48f * SR);
        float tail = db(rms(b, from, to) / rms(a, from, to));
        printf("    %5.0f  %4.0f / %4.0f                  | %+5.1f dB        | %+5.1f dB            | %.3f\n",
               hp, 100 * s0, 100 * s1, level, tail, peak(b));
        // Only the steeper (Butterworth) knee: within a few % and ~1 dB of
        // P2 0, no ring (the previous build's ring at 60 Hz: +23.7 dB late).
        CHECK(s1 < s0 + 0.05f, "HP %.0f: P2 1 share at the cutoff %.2f vs %.2f (ring)", hp, s1, s0);
        CHECK(level < 1.0f, "HP %.0f: P2 1 adds %.2f dB", hp, level);
        CHECK(tail < 2.0f, "HP %.0f: P2 1 tail %+.1f dB (boom)", hp, tail);
        CHECK(peak(b) <= OutputGuard::GUARD_LIMIT, "HP %.0f: P2 1 peak %.3f", hp, peak(b));
    }
}

// High mids and highs on the groove (kick + hats + clap): the ring at the
// cutoff grows with P2 and takes over the hits (the DJ-filter zing), the
// guard keeps it under full scale and lets go between the hits.
static void testResonanceHighs() {
    const int beat = 22050;
    std::vector<float> loop = groove(8, beat);
    const size_t from = (size_t)4 * beat, to = (size_t)8 * beat;
    printf("  groove through P4 + P2: energy in 1/6 oct at the cutoff (%%) P2 0 / .25 / .5 / 1 | peak | guard gain mean\n");
    for (float hp : {650.0f, 900.0f, DjHighpass::RES_FULL_HZ, 3000.0f, 6000.0f, 12000.0f}) {
        float shares[4];
        float p = 0.0f, gainMean = 1.0f;
        int idx = 0;
        for (float p2 : {0.0f, 0.25f, 0.5f, 1.0f}) {
            GroupA chain(0.0f, p2, p3Cutoff(0.0f), hp);
            std::vector<float> out(loop.size());
            double gsum = 0.0;
            for (size_t i = 0; i < loop.size(); i++) {
                out[i] = chain.process(loop[i]);
                if (i >= from) gsum += chain.guard.getGain();
            }
            shares[idx++] = bandShare(out, hp, from, to);
            CHECK(std::isfinite(peak(out)), "HP %.0f P2 %.2f not finite", hp, p2);
            // P2 0 is the earlier chain, no guard (the groove alone peaks ~1.01 around 800 Hz).
            CHECK(p2 == 0.0f || peak(out) <= OutputGuard::GUARD_LIMIT + 1e-6f, "HP %.0f P2 %.2f peak %.3f over the guard", hp, p2, peak(out));
            if (p2 == 1.0f) {
                p = peak(out);
                gainMean = (float)(gsum / (double)(to - from));
            }
        }
        printf("    %5.0f Hz  %4.0f / %4.0f / %4.0f / %4.0f | %.3f | %.2f\n", hp,
               100 * shares[0], 100 * shares[1], 100 * shares[2], 100 * shares[3], p, gainMean);
        CHECK(shares[1] > shares[0] && shares[2] > shares[1] && shares[3] > shares[2], "HP %.0f: share not rising with P2", hp);
        // Full peak: the ring takes over; the fade-in: less, its edge least.
        float focus = DjHighpass::focus(hp);
        float need = focus >= 1.0f ? 0.5f : focus >= 0.5f ? 0.2f : 0.05f;
        CHECK(shares[3] > shares[0] + need, "HP %.0f: P2 1 share %.2f vs P2 0 %.2f", hp, shares[3], shares[0]);
        CHECK(gainMean > 0.8f, "HP %.0f: guard mean gain %.2f (pumping)", hp, gainMean);
    }

    // The kick alone at the resonant cutoffs: it pings, the guard lets go by
    // the next beat.
    std::vector<float> kick = kickPattern(4, beat, 1.0f);
    for (float hp : {DjHighpass::RES_START_HZ * 1.2f, DjHighpass::RES_FULL_HZ, 3000.0f}) {
        GroupA chain(0.0f, 1.0f, p3Cutoff(0.0f), hp);
        float nextGain = 1.0f;
        std::vector<float> out = runMarked(chain, kick, (size_t)3 * beat, nextGain);
        printf("  kick alone, P2 1, HP %.0f Hz: peak %.3f, guard %.3f at the next beat\n", hp, peak(out), nextGain);
        CHECK(peak(out) <= OutputGuard::GUARD_LIMIT + 1e-6f, "kick at %.0f Hz peak %.3f", hp, peak(out));
        CHECK(nextGain > 0.99f, "kick at %.0f Hz: guard %.2f at the next beat", hp, nextGain);
    }
}

// Turning P2 while the kick plays (P4 at 100 Hz): smoothed, no click, and
// just above the dead zone the level is close to off; on the groove at
// 1 kHz the ring comes in without breaking up.
static void testResonanceSweepSmooth() {
    std::vector<float> kick = kickPattern(8, 11025, 0.7f);
    GroupA chain(0.0f, 0.0f, p3Cutoff(0.0f), 100.0f);
    GroupA flat(0.0f, 0.0f, p3Cutoff(0.0f), 100.0f);
    float maxStep = 0.0f, last = 0.0f;
    float maxStepFlat = 0.0f, lastFlat = 0.0f;
    for (size_t i = 0; i < kick.size(); i++) {
        if (i % 88 == 0) {
            float t = (float)i / (float)kick.size();
            chain.setP2(t < 0.5f ? 2.0f * t : 2.0f - 2.0f * t);
        }
        float y = chain.process(kick[i]);
        float f = flat.process(kick[i]);
        if (i > 0) {
            maxStep = fmaxf(maxStep, fabsf(y - last));
            maxStepFlat = fmaxf(maxStepFlat, fabsf(f - lastFlat));
        }
        last = y;
        lastFlat = f;
    }
    printf("  P2 swept 0 -> 1 -> 0 on the kick (HP 100 Hz): biggest sample step %.3f (P2 0: %.3f)\n", maxStep, maxStepFlat);
    CHECK(maxStep < 1.5f * maxStepFlat, "P2 sweep step %.3f (click)", maxStep);

    std::vector<float> loop = groove(8, 11025);
    GroupA hi(0.0f, 0.0f, p3Cutoff(0.0f), 1000.0f);
    float p = 0.0f;
    bool finite = true;
    for (size_t i = 0; i < loop.size(); i++) {
        if (i % 88 == 0) {
            float t = (float)i / (float)loop.size();
            hi.setP2(t < 0.5f ? 2.0f * t : 2.0f - 2.0f * t);
        }
        float y = hi.process(loop[i]);
        finite = finite && std::isfinite(y);
        p = fmaxf(p, fabsf(y));
    }
    printf("  P2 swept 0 -> 1 -> 0 on the groove (HP 1 kHz): peak %.3f\n", p);
    CHECK(finite && p <= OutputGuard::GUARD_LIMIT + 1e-6f, "P2 sweep at 1 kHz peak %.3f", p);

    std::vector<float> one = kickPattern(1, 22050, 1.0f);
    for (float hp : {20.0f, 60.0f, 200.0f}) {
        GroupA off(0.0f, 0.0f, p3Cutoff(0.0f), hp);
        GroupA on(0.0f, SamplerDsp::DEAD_ZONE + 0.005f, p3Cutoff(0.0f), hp);
        float jump = db(rms(run(on, one)) / rms(run(off, one)));
        printf("  P2 just above the dead zone, HP %.0f Hz: %+.2f dB vs off\n", hp, jump);
        CHECK(fabsf(jump) < 1.5f, "P2 just above off at %.0f Hz jumps %.2f dB", hp, jump);
    }
}

// P2 back to zero while the guard is holding (groove at 1 kHz): it releases
// and the chain returns to the earlier output bit for bit.
static void testResonanceReturnsToEarlier() {
    std::vector<float> loop = groove(8, 22050);
    float hp = 1000.0f;
    GroupA chain(0.0f, 1.0f, p3Cutoff(0.0f), hp);
    std::vector<float> out(loop.size());
    float minGain = 1.0f;
    size_t off = 0;
    for (size_t i = 0; i < loop.size(); i++) {
        out[i] = chain.process(loop[i]);
        minGain = fminf(minGain, chain.guard.getGain());
        if (off == 0 && minGain < 0.99f) {
            off = i;  // P2 off while the guard holds
            chain.setP2(0.0f);
        }
    }
    CHECK(off > 0, "guard never engaged");
    CHECK(chain.guard.getGain() == 1.0f, "guard gain %.6f after P2 back to 0", chain.guard.getGain());
    // The earlier Biquad runs all along, so once the DJ stages have faded
    // out and the guard let go, the output is the earlier chain's bit for bit.
    std::vector<float> ref = earlierChain(loop, p3Cutoff(0.0f), hp);
    size_t from = (off / 22050 + 2) * 22050;
    CHECK(from < loop.size(), "guard engaged too late (%zu)", off);
    if (from >= loop.size()) return;
    bool same = memcmp(out.data() + from, ref.data() + from, (loop.size() - from) * sizeof(float)) == 0;
    printf("  P2 1 -> 0 with the guard at %.2f: guard back at 1, later beats %s the earlier chain\n", minGain, same ? "bit-exact with" : "DIFFER from");
    CHECK(same, "P2 back to 0: later beats differ from the earlier chain");
}

// Full chain at the extremes with a P4 sweep: bounded and finite.
static void testStability() {
    std::vector<float> kick = kickPattern(8, 11025, 1.0f);
    GroupA chain(1.0f, 1.0f, p3Cutoff(0.0f), 20.0f);
    float p = 0.0f;
    bool finite = true;
    for (size_t i = 0; i < kick.size(); i++) {
        if (i % 88 == 0) {
            float t = (float)i / (float)kick.size();
            chain.setP4(p4Cutoff(t < 0.5f ? 2.0f * t : 2.0f - 2.0f * t));
        }
        float y = chain.process(kick[i]);
        finite = finite && std::isfinite(y);
        p = fmaxf(p, fabsf(y));
    }
    printf("  P1 = P2 = 1, P4 swept 20 Hz .. %.0f Hz .. 20 Hz: peak %.3f\n", P4_TOP, p);
    CHECK(finite, "full P1 / P2 with a P4 sweep: not finite");
    CHECK(p <= OutputGuard::GUARD_LIMIT + 1e-6f, "full P1 / P2 sweep peak %.3f", p);
}

// --- listening WAVs -------------------------------------------------------

static bool writeWav(const std::string& path, const std::vector<float>& x) {
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return false;
    uint32_t dataBytes = (uint32_t)x.size() * 2;
    uint32_t riff = 36 + dataBytes;
    uint32_t sr = (uint32_t)SR, byteRate = sr * 2, fmtLen = 16;
    uint16_t pcm = 1, ch = 1, align = 2, bits = 16;
    fwrite("RIFF", 1, 4, f); fwrite(&riff, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
    fwrite(&fmtLen, 4, 1, f); fwrite(&pcm, 2, 1, f); fwrite(&ch, 2, 1, f);
    fwrite(&sr, 4, 1, f); fwrite(&byteRate, 4, 1, f); fwrite(&align, 2, 1, f); fwrite(&bits, 2, 1, f);
    fwrite("data", 1, 4, f); fwrite(&dataBytes, 4, 1, f);
    for (float v : x) {
        // The DAC path of manager.h: hard clip to int16.
        float s = fminf(fmaxf(v * 32768.0f, -32768.0f), 32767.0f);
        int16_t i = (int16_t)s;
        fwrite(&i, 2, 1, f);
    }
    fclose(f);
    return true;
}

static void writeWavs(const std::string& dir) {
    // 125 BPM four-on-the-floor, 8 hits per setting.
    const int beat = (int)(SR * 60.0f / 125.0f);
    std::vector<float> kick = kickPattern(8, beat, 1.0f);
    for (float p1 : {0.0f, 0.25f, 0.5f, 0.75f, 1.0f}) {
        GroupA chain(p1, 0.0f, p3Cutoff(0.0f), p4Cutoff(0.0f));
        char name[64];
        snprintf(name, sizeof name, "/drive_p1_%03d.wav", (int)lroundf(p1 * 100));
        writeWav(dir + name, run(chain, kick));
    }
    // Drive with P3 taming the top end.
    {
        GroupA chain(1.0f, 0.0f, p3Cutoff(0.55f), p4Cutoff(0.0f));
        writeWav(dir + "/drive_p1_100_p3_055.wav", run(chain, kick));
    }
    // The kick at a low cutoff: P2 adds no boom.
    for (float p2 : {0.0f, 1.0f}) {
        GroupA chain(0.0f, p2, p3Cutoff(0.0f), 60.0f);
        char name[64];
        snprintf(name, sizeof name, "/kick_hp60_p2_%03d.wav", (int)lroundf(p2 * 100));
        writeWav(dir + name, run(chain, kick));
    }
    // The groove (kick + hats + clap) dry and at fixed cutoffs.
    std::vector<float> loop = groove(8, beat);
    writeWav(dir + "/groove_dry.wav", loop);
    for (float hz : {500.0f, 800.0f, 1200.0f, 3000.0f, 6000.0f}) {
        for (float p2 : {0.0f, 0.5f, 1.0f}) {
            GroupA chain(0.0f, p2, p3Cutoff(0.0f), hz);
            char name[64];
            snprintf(name, sizeof name, "/groove_hp%.0f_p2_%03d.wav", hz, (int)lroundf(p2 * 100));
            writeWav(dir + name, run(chain, loop));
        }
    }
    // DJ sweep: P4 from 20 Hz over the whole knob (20 kHz) and back over 32
    // beats on the groove, at P2 = 0 / 0.5 / 1, and with P1 drive.
    std::vector<float> longLoop = groove(32, beat);
    auto sweepHz = [&](size_t i) {
        float t = (float)i / (float)longLoop.size();
        return p4Cutoff(t < 0.5f ? 2.0f * t : 2.0f - 2.0f * t);
    };
    auto sweep = [&](float p1, float p2, const char* name) {
        GroupA chain(p1, p2, p3Cutoff(0.0f), 20.0f);
        std::vector<float> out(longLoop.size());
        for (size_t i = 0; i < longLoop.size(); i++) {
            if (i % 88 == 0) chain.setP4(sweepHz(i));
            out[i] = chain.process(longLoop[i]);
        }
        writeWav(dir + name, out);
    };
    sweep(0.0f, 0.0f, "/groove_sweep_p2_000.wav");
    sweep(0.0f, 0.5f, "/groove_sweep_p2_050.wav");
    sweep(0.0f, 1.0f, "/groove_sweep_p2_100.wav");
    sweep(0.6f, 1.0f, "/groove_sweep_p2_100_p1_060.wav");
    printf("\n  wrote listening WAVs to %s\n", dir.c_str());
}

int main(int argc, char** argv) {
    std::string wavDir;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--wav") == 0 && i + 1 < argc) wavDir = argv[++i];
    }

    testZeroIsEarlier();
    testCurves();
    testDriveOnKick();
    testDriveHarmonics();
    testDriveSweepSmooth();
    testResonanceResponse();
    testSquelch();
    testNoMud();
    testResonanceHighs();
    testResonanceSweepSmooth();
    testResonanceReturnsToEarlier();
    testStability();

    if (!wavDir.empty()) writeWavs(wavDir);

    printf("\n%d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
