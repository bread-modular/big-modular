// Host test of the cpx4 app DSP (includes/audio/apps/cpx4/cpx4_dsp.h) and
// its control map (cpx4_controls.h): every control is driven the way the app
// drives it (knob ADC value or MCC CC) and checked for doing what it is for,
// and only that, on the rendered output. Run through ../test.sh.
//
//   ./.build/host/sim_cpx4 --wav <dir>   # also write listening WAVs to <dir>

#include <cmath>
#include <complex>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "audio/apps/cpx4/cpx4_controls.h"
#include "audio/apps/motion_recorder.h"

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

namespace lc = cpx4_controls;
using Buf = std::vector<float>;

static const float SR = 44100.0f;
static const int LINE_SIZE = 44100 + 64;
static int16_t line1[LINE_SIZE];
static int16_t line2[LINE_SIZE];

// Button CC value of step 0..2, as the MCC sends it.
static uint8_t routingCc(int step) { return step == 0 ? 0 : step == 1 ? 64 : 127; }

static double dbp(double powerRatio) { return 10.0 * log10(powerRatio + 1e-30); }

// --- rig ------------------------------------------------------------------

// A DSP in a known state: every control set as the app sets it (CC values,
// knob ADC values), then init (as app init(): controls first).
struct Rig {
    Cpx4Dsp dsp;
    uint8_t cc[8];
    Rig() {
        for (int i = 0; i < 8; i++) cc[i] = lc::SEED_CC[i];
        // Neutral test state: clean, dry, open.
        set(lc::CC_SHARP_A, 0);
        set(lc::CC_SHARP_B, 0);
        set(lc::CC_MOD, 0);
        set(lc::CC_DRIVE, 0);
        set(lc::CC_DELAY_MIX, 0);
        set(lc::CC_FEEDBACK, 0);
        set(lc::CC_CUTOFF, 0);  // inverted: open
        set(lc::CC_ROUTING, 0);
        set(lc::CC_RESONANCE, 0);
        // About 57 / 162 / 272 / 837 Hz.
        tune(0, 0.38f); tune(1, 0.49f); tune(2, 0.405f); tune(3, 0.47f);
        dsp.init(SR, line1, line2, LINE_SIZE);
    }
    void set(uint8_t c, uint8_t v) { lc::apply(dsp, c, v); }
    // Knob position 0..1 through the knob's ADC range.
    void tune(int knob, float pos) {
        float adc = knob < 2 ? lc::TOP_KNOB_ADC_ZERO + pos * (lc::TOP_KNOB_ADC_FULL - lc::TOP_KNOB_ADC_ZERO)
                             : lc::KNOB_ADC_END + pos * (4095 - 2 * lc::KNOB_ADC_END);
        dsp.setTune(knob, lc::knobToTune(knob, adc));
    }
    void reinit() { dsp.init(SR, line1, line2, LINE_SIZE); }
    void run(int n, Buf* l = nullptr, Buf* r = nullptr, const Buf* in = nullptr,
             bool voices = true, Buf* voice0 = nullptr) {
        for (int i = 0; i < n; i++) {
            float a, b;
            dsp.process(a, b, in ? (*in)[i] : 0.0f, voices);
            if (l) l->push_back(a);
            if (r) r->push_back(b);
            if (voice0) voice0->push_back(dsp.getVoiceOutput(0));
        }
    }
};

// --- analysis -------------------------------------------------------------

static void fft(std::vector<std::complex<double>>& a) {
    size_t n = a.size();
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (size_t len = 2; len <= n; len <<= 1) {
        double ang = -2.0 * M_PI / len;
        std::complex<double> wl(cos(ang), sin(ang));
        for (size_t i = 0; i < n; i += len) {
            std::complex<double> w(1.0);
            for (size_t j = 0; j < len / 2; j++) {
                auto u = a[i + j], v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= wl;
            }
        }
    }
}

// Blackman-Harris windowed power spectrum of the last 2^16 samples
// (bin = SR / 65536; sidelobes under -92 dB).
static const int NFFT = 65536;
static std::vector<double> spectrum(const Buf& x) {
    std::vector<std::complex<double>> a(NFFT);
    size_t off = x.size() - NFFT;
    for (int i = 0; i < NFFT; i++) {
        double t = 2.0 * M_PI * i / NFFT;
        double w = 0.35875 - 0.48829 * cos(t) + 0.14128 * cos(2 * t) - 0.01168 * cos(3 * t);
        a[i] = x[off + i] * w;
    }
    fft(a);
    std::vector<double> p(NFFT / 2);
    for (int i = 0; i < NFFT / 2; i++) p[i] = std::norm(a[i]);
    return p;
}
static double binHz() { return SR / NFFT; }

// Power in [lo, hi] Hz.
static double band(const std::vector<double>& p, double lo, double hi) {
    int a = std::max(1, (int)(lo / binHz())), b = std::min((int)p.size() - 1, (int)(hi / binHz()));
    double s = 0.0;
    for (int i = a; i <= b; i++) s += p[i];
    return s;
}

// Strongest frequency in [lo, hi] Hz (parabolic interpolation).
static double peakHz(const std::vector<double>& p, double lo, double hi) {
    int a = std::max(2, (int)(lo / binHz())), b = std::min((int)p.size() - 2, (int)(hi / binHz()));
    int best = a;
    for (int i = a; i <= b; i++) if (p[i] > p[best]) best = i;
    double l = log(p[best - 1] + 1e-30), c = log(p[best] + 1e-30), r = log(p[best + 1] + 1e-30);
    double d = 0.5 * (l - r) / (l - 2 * c + r);
    return (best + d) * binHz();
}

// Power of a harmonic: band +-1.5 % around h * f0.
static double harmonic(const std::vector<double>& p, double f0, int h) {
    return band(p, h * f0 * 0.985, h * f0 * 1.015);
}

static double rms(const Buf& x, size_t from = 0, size_t to = 0) {
    if (to == 0 || to > x.size()) to = x.size();
    double s = 0.0;
    for (size_t i = from; i < to; i++) s += (double)x[i] * x[i];
    return sqrt(s / std::max<size_t>(1, to - from));
}

static float peakAbs(const Buf& x, size_t from = 0, size_t to = 0) {
    if (to == 0 || to > x.size()) to = x.size();
    float m = 0.0f;
    for (size_t i = from; i < to; i++) m = std::max(m, std::fabs(x[i]));
    return m;
}

// Fraction of the power that is not on a harmonic of any voice (dB).
static double inharmonicDb(const std::vector<double>& p, const double f0[4]) {
    std::vector<char> on(p.size(), 0);
    for (int v = 0; v < 4; v++) {
        for (int h = 1; h * f0[v] < SR / 2; h++) {
            double f = h * f0[v];
            int a = (int)(f * 0.99 / binHz()) - 3, b = (int)(f * 1.01 / binHz()) + 3;
            for (int i = std::max(0, a); i <= b && i < (int)p.size(); i++) on[i] = 1;
        }
    }
    double inh = 0.0, all = 0.0;
    for (size_t i = 3; i < p.size(); i++) {
        all += p[i];
        if (!on[i]) inh += p[i];
    }
    return dbp(inh / all);
}

// A 64-sample click with no DC (four cycles under a Hann window), so the
// output DC blocker leaves no tail that would read as an echo.
static Buf burst(int n, int at, float amp = 0.5f) {
    Buf x(n, 0.0f);
    for (int i = 0; i < 64; i++) {
        x[at + i] = amp * (float)(sin(M_PI * i / 64.0) * sin(M_PI * i / 64.0) * sin(2.0 * M_PI * 4 * i / 64.0));
    }
    return x;
}

static Buf noise(int n, float amp, uint32_t seed = 1) {
    Buf x(n);
    for (int i = 0; i < n; i++) {
        seed = seed * 1664525u + 1013904223u;
        x[i] = amp * ((float)(int32_t)seed / 2147483648.0f);
    }
    return x;
}

// A 20 ms noise click (broadband: low frequencies too, for the loop).
static Buf noiseBurst(int n, int at, float amp = 0.5f) {
    Buf x(n, 0.0f);
    uint32_t seed = 7;
    for (int i = 0; i < 882; i++) {
        seed = seed * 1664525u + 1013904223u;
        x[at + i] = amp * (float)sin(M_PI * i / 882.0) * ((float)(int32_t)seed / 2147483648.0f);
    }
    return x;
}

// Start of the 64-sample window with the most energy in [from, to).
static size_t energyPeak(const Buf& x, size_t from, size_t to) {
    size_t best = from;
    double bestE = -1.0, e = 0.0;
    to = std::min(to, x.size());
    for (size_t i = from; i < from + 64 && i < to; i++) e += (double)x[i] * x[i];
    for (size_t i = from; i + 64 < to; i++) {
        if (e > bestE) { bestE = e; best = i; }
        e += (double)x[i + 64] * x[i + 64] - (double)x[i] * x[i];
    }
    return best;
}

// --- tests ----------------------------------------------------------------

static void testControlMap() {
    // The recorded MCC knobs are recorder slots 0..7 (Bank A, Bank B).
    for (int i = 0; i < 8; i++) {
        CHECK(MotionRecorder::ccIndex(lc::RECORDED_CCS[i]) == i, "CC%d recorder slot", lc::RECORDED_CCS[i]);
    }
    // The button CCs are outside the recorder.
    CHECK(MotionRecorder::ccIndex(lc::CC_ROUTING) < 0 && MotionRecorder::ccIndex(lc::CC_RESONANCE) < 0,
          "button CCs not recorded");
    CHECK(lc::buttonStep(0) == 0 && lc::buttonStep(64) == 1 && lc::buttonStep(127) == 2, "button steps");
    CHECK(lc::buttonStep(42) == 0 && lc::buttonStep(43) == 1 && lc::buttonStep(85) == 1 && lc::buttonStep(86) == 2,
          "button step edges");
    // Knob ranges.
    CHECK(lc::knobToTune(0, 2020) == 0.0f && lc::knobToTune(0, 3735) == 1.0f && lc::knobToTune(1, 1000) == 0.0f,
          "P1 / P2 0..+5 V range");
    CHECK(lc::knobToTune(2, 16) == 0.0f && lc::knobToTune(3, 4095) == 1.0f && fabsf(lc::knobToTune(2, 2047.5f) - 0.5f) < 1e-3f,
          "P3 / P4 full range");

    // Each CC moves its own parameter and nothing else.
    struct Snap {
        float sharp0, sharp2, mod, drive, delay, fb, mix, cutoff, k; int routing;
    };
    auto snap = [](Rig& r) {
        r.run(4000);
        Snap s;
        s.sharp0 = r.dsp.getSharpGain(0); s.sharp2 = r.dsp.getSharpGain(2);
        s.mod = r.dsp.getMod(); s.drive = r.dsp.getDriveGain();
        s.delay = r.dsp.getDelaySeconds(0); s.fb = r.dsp.getFeedbackGain();
        s.mix = r.dsp.getMix(); s.cutoff = r.dsp.getCutoffHz();
        s.k = r.dsp.getResonanceK(); s.routing = r.dsp.getRouting();
        return s;
    };
    struct Case { uint8_t cc; uint8_t value; const char* name; int field; };
    const Case cases[] = {
        {lc::CC_SHARP_A, 127, "SHARP A", 0}, {lc::CC_SHARP_B, 127, "SHARP B", 1},
        {lc::CC_MOD, 127, "MOD", 2}, {lc::CC_DRIVE, 127, "DRIVE", 3},
        {lc::CC_DELAY_TIME, 127, "DELAY TIME", 4}, {lc::CC_FEEDBACK, 127, "FEEDBACK", 5},
        {lc::CC_DELAY_MIX, 127, "DELAY MIX", 6}, {lc::CC_CUTOFF, 127, "CUTOFF", 7},
        {lc::CC_RESONANCE, 127, "RESONANCE", 8}, {lc::CC_ROUTING, 127, "ROUTING", 9},
    };
    for (const Case& c : cases) {
        Rig base;
        Snap a = snap(base);
        Rig moved;
        moved.set(c.cc, c.value);
        Snap b = snap(moved);
        float fa[10] = {a.sharp0, a.sharp2, a.mod, a.drive, a.delay, a.fb, a.mix, a.cutoff, a.k, (float)a.routing};
        float fbv[10] = {b.sharp0, b.sharp2, b.mod, b.drive, b.delay, b.fb, b.mix, b.cutoff, b.k, (float)b.routing};
        for (int f = 0; f < 10; f++) {
            bool changed = fabsf(fa[f] - fbv[f]) > 1e-4f * (1.0f + fabsf(fa[f]));
            CHECK(changed == (f == c.field), "%s: parameter %d %s (%.4f -> %.4f)", c.name, f,
                  changed ? "changed" : "unchanged", fa[f], fbv[f]);
        }
    }
    Rig r;
    CHECK(!lc::apply(r.dsp, 24, 64) && !lc::apply(r.dsp, 85, 64) && !lc::apply(r.dsp, 101, 64) &&
          !lc::apply(r.dsp, 123, 0), "other CCs ignored");
    printf("  control map: 8 recorded CCs, 2 buttons, each moves only its parameter\n");
}

// The cpx4 MCC firmware (../mcc/cpx4_mcc/cpx4_mcc.ino) sends what this
// map reads: unit 1 Bank A + CC102, unit 2 Bank B + CC103, steps 0 / 64 / 127.
static void testMccFirmwareContract() {
    std::ifstream f("../mcc/cpx4_mcc/cpx4_mcc.ino");
    CHECK(f.good(), "cpx4_mcc.ino not found (run from 16bit/)");
    if (!f.good()) return;
    std::stringstream ss;
    ss << f.rdbuf();
    std::string ino = ss.str();
    auto has = [&](const std::string& text) { return ino.find(text) != std::string::npos; };
    char unit1[160], unit2[160];
    snprintf(unit1, sizeof unit1, "#if MCC_UNIT == 1\n#define CC_BASE %d       // Bank A\n#define BUTTON_CC %d",
             lc::CC_SHARP_A, lc::CC_ROUTING);
    snprintf(unit2, sizeof unit2, "#elif MCC_UNIT == 2\n#define CC_BASE %d       // Bank B\n#define BUTTON_CC %d",
             lc::CC_DELAY_TIME, lc::CC_RESONANCE);
    CHECK(has(unit1), "MCC-1: CC20-23 + CC102");
    CHECK(has(unit2), "MCC-2: CC27-30 + CC103");
    CHECK(has("const uint8_t STEP_CC_VALUE[STEPS] = {0, 64, 127};"), "MCC step values");
    CHECK(lc::CC_SHARP_B == lc::CC_SHARP_A + 1 && lc::CC_MOD == lc::CC_SHARP_A + 2 && lc::CC_DRIVE == lc::CC_SHARP_A + 3 &&
          lc::CC_FEEDBACK == lc::CC_DELAY_TIME + 1 && lc::CC_DELAY_MIX == lc::CC_DELAY_TIME + 2 &&
          lc::CC_CUTOFF == lc::CC_DELAY_TIME + 3, "knob CCs are CC_BASE + 0..3");
    printf("  MCC firmware: unit 1 sends CC20-23 + CC102, unit 2 CC27-30 + CC103, steps 0 / 64 / 127\n");
}

static void testTune() {
    // Every TUNE knob covers the full A0..A7 range (as on the Lyra-8); the
    // curves differ: at each knob position voice 1 is lowest, voice 4
    // highest, and each voice spends most of its travel in its own register.
    const double centreHz[4] = {92.5, 191.5, 505.4, 1046.5};
    for (int k = 0; k < 4; k++) {
        Rig r;
        r.tune(k, Cpx4Dsp::MUTE_ON); r.run(20000);
        double f0 = r.dsp.getVoiceHz(k);
        r.tune(k, 1.0f); r.run(20000);
        double f1 = r.dsp.getVoiceHz(k);
        r.tune(k, Cpx4Dsp::MUTE_ON + 0.5f * (1.0f - Cpx4Dsp::MUTE_ON)); r.run(20000);
        double fc = r.dsp.getVoiceHz(k);
        // Within the drift (4 cents = 0.23 %).
        CHECK(fabs(f0 / 27.5 - 1.0) < 0.003 && fabs(f1 / 3520.0 - 1.0) < 0.003,
              "TUNE %d range %.2f..%.1f Hz", k + 1, f0, f1);
        CHECK(fabs(fc / centreHz[k] - 1.0) < 0.004, "TUNE %d centre %.1f Hz", k + 1, fc);
        printf("  TUNE %d range %.1f..%.0f Hz, knob centre %.0f Hz\n", k + 1, f0, f1, fc);
    }
    // Curve order: at every position voice 1 < 2 < 3 < 4 (ends excepted).
    {
        bool ordered = true;
        for (int i = 1; i < 100; i++) {
            float t = i / 100.0f;
            for (int v = 0; v < 3; v++) {
                if (Cpx4Dsp::tuneOctaves(v, t) >= Cpx4Dsp::tuneOctaves(v + 1, t)) ordered = false;
            }
        }
        CHECK(ordered, "TUNE curves ordered voice 1 < 2 < 3 < 4");
        // Dwell: share of the travel each voice spends below 220 Hz (A3) and
        // above 880 Hz (A5).
        for (int v = 0; v < 4; v++) {
            int low = 0, high = 0;
            for (int i = 0; i < 1000; i++) {
                double hz = 27.5 * pow(2.0, Cpx4Dsp::tuneOctaves(v, (i + 0.5f) / 1000.0f));
                if (hz < 220.0) low++;
                if (hz > 880.0) high++;
            }
            printf("  TUNE %d: %4.1f %% of the travel below 220 Hz, %4.1f %% above 880 Hz\n",
                   v + 1, low / 10.0, high / 10.0);
            if (v == 0) CHECK(low > 650 && high < 150, "TUNE 1 dwells in the bass (%d / %d)", low, high);
            if (v == 3) CHECK(high > 500 && low < 250, "TUNE 4 dwells in the treble (%d / %d)", low, high);
        }
    }
    // Black box: set one voice, find its line in the output; move only that
    // knob and the line moves there, the other three stay.
    for (int k = 0; k < 4; k++) {
        Rig r;
        Buf before, after;
        r.run(NFFT + 8000, &before);
        double fOthers[4], fMoved[4];
        for (int v = 0; v < 4; v++) fOthers[v] = r.dsp.getVoiceHz(v);
        r.tune(k, k == 2 ? 0.52f : k < 2 ? 0.55f : 0.62f);
        r.run(NFFT + 8000, &after);
        for (int v = 0; v < 4; v++) fMoved[v] = r.dsp.getVoiceHz(v);
        auto pb = spectrum(before), pa = spectrum(after);
        double heard = peakHz(pa, fMoved[k] * 0.97, fMoved[k] * 1.03);
        double cents = 1200.0 * log2(heard / fMoved[k]);
        CHECK(fabs(cents) < 10.0, "TUNE %d heard %.2f Hz, set %.2f Hz (%.1f cents)", k + 1, heard, fMoved[k], cents);
        CHECK(dbp(harmonic(pa, fOthers[k], 1) / harmonic(pb, fOthers[k], 1)) < -20.0,
              "TUNE %d: old line gone", k + 1);
        for (int v = 0; v < 4; v++) {
            if (v == k) continue;
            double drift = 1200.0 * log2(fMoved[v] / fOthers[v]);
            double h = peakHz(pa, fOthers[v] * 0.97, fOthers[v] * 1.03);
            CHECK(fabs(drift) < 2.0 * Cpx4Dsp::DRIFT_CENTS && fabs(1200.0 * log2(h / fOthers[v])) < 10.0,
                  "TUNE %d moved voice %d (%.1f cents)", k + 1, v + 1, drift);
        }
        printf("  TUNE %d: voice %d heard at %.2f Hz (set %.2f, %+.1f cents), others unchanged\n",
               k + 1, k + 1, heard, fMoved[k], cents);
    }
    // Steps: cents per ADC step at the fine and the fast end of each curve
    // (P1 / P2 see only part of the ADC range).
    const float pitchTravel = 1.0f - Cpx4Dsp::MUTE_ON;
    const float steps[4] = {(float)(lc::TOP_KNOB_ADC_FULL - lc::TOP_KNOB_ADC_ZERO),
                            (float)(lc::TOP_KNOB_ADC_FULL - lc::TOP_KNOB_ADC_ZERO),
                            (float)(4095 - 2 * lc::KNOB_ADC_END), (float)(4095 - 2 * lc::KNOB_ADC_END)};
    for (int v = 0; v < 4; v++) {
        double fine = 1e9, fast = 0.0;
        for (int i = 0; i < 1000; i++) {
            double dt = 1.0 / 1000.0, t = i * dt;
            double c = 1200.0 * (Cpx4Dsp::tuneOctaves(v, (float)(t + dt)) - Cpx4Dsp::tuneOctaves(v, (float)t)) / dt;
            fine = std::min(fine, c);
            fast = std::max(fast, c);
        }
        double perStep = 1.0 / (pitchTravel * steps[v]);
        CHECK(fine * perStep < (v < 2 ? 3.5 : 1.5) && fast * perStep < 16.0, "TUNE %d steps %.2f..%.1f cents", v + 1,
              fine * perStep, fast * perStep);
        printf("  TUNE %d: %.2f cents per ADC step at its fine end, %.1f at its fast end\n", v + 1,
               fine * perStep, fast * perStep);
    }
    // Drift stays within its bound over a minute.
    Rig r;
    double f0 = r.dsp.getVoiceHz(0), worst = 0.0;
    for (int s = 0; s < 60; s++) {
        r.run(44100);
        worst = std::max(worst, fabs(1200.0 * log2(r.dsp.getVoiceHz(0) / f0)));
    }
    CHECK(worst <= Cpx4Dsp::DRIFT_CENTS + 0.01 && worst > 0.5, "drift %.2f cents", worst);
    printf("  drift: voice 1 wandered up to %.2f cents over 60 s\n", worst);
}

// Voice 1 alone: 3rd / 1st harmonic (dB) and crest factor (peak / rms).
static void voiceShape(Rig& r, double* h3, double* crest) {
    Buf v0;
    r.run(NFFT + 4000, nullptr, nullptr, nullptr, true, &v0);
    auto p = spectrum(v0);
    double f = r.dsp.getVoiceHz(0);
    *h3 = dbp(harmonic(p, f, 3) / harmonic(p, f, 1));
    *crest = peakAbs(v0, 4000) / rms(v0, 4000);
}

// Largest sample-to-sample step of a buffer slice (a click is a jump).
static float maxStep(const Buf& x, size_t from, size_t to) {
    float m = 0.0f;
    for (size_t i = from + 1; i < to && i < x.size(); i++) m = fmaxf(m, fabsf(x[i] - x[i - 1]));
    return m;
}

static void testVoiceMute() {
    // Knob at 0 silences its voice: its line goes, the others stay.
    for (int k = 0; k < 4; k++) {
        Rig r;
        Buf before, after;
        r.run(NFFT + 8000, &before);
        double f[4];
        for (int v = 0; v < 4; v++) f[v] = r.dsp.getVoiceHz(v);
        r.tune(k, 0.0f);
        r.run(NFFT + 8000, &after);
        auto pb = spectrum(before), pa = spectrum(after);
        double gone = dbp(harmonic(pa, f[k], 1) / harmonic(pb, f[k], 1));
        // What is left in the bin is the other voices' intermodulation
        // (DRIVE 0 still compresses 2 %); the voice itself outputs 0.
        CHECK(!r.dsp.isVoiceOn(k) && r.dsp.getVoiceLevel(k) == 0.0f && r.dsp.getVoiceOutput(k) == 0.0f &&
              gone < -50.0,
              "TUNE %d at 0: voice line %.1f dB", k + 1, gone);
        for (int v = 0; v < 4; v++) {
            if (v == k) continue;
            double change = dbp(harmonic(pa, r.dsp.getVoiceHz(v), 1) / harmonic(pb, f[v], 1));
            CHECK(r.dsp.isVoiceOn(v) && fabs(change) < 1.0, "TUNE %d at 0 changed voice %d by %.2f dB",
                  k + 1, v + 1, change);
        }
        printf("  TUNE %d at 0: voice %d line %.0f dB, others unchanged\n", k + 1, k + 1, gone);
    }

    // All four at 0: silence.
    {
        Rig r;
        for (int k = 0; k < 4; k++) r.tune(k, 0.0f);
        Buf o;
        r.run(22050, &o);
        double db = 20.0 * log10(rms(o, 11025) + 1e-30);
        CHECK(db < -90.0, "all TUNEs at 0: %.1f dBFS", db);
        printf("  all four TUNEs at 0: %.0f dBFS\n", db);
    }

    // Hysteresis: off below MUTE_OFF, on above MUTE_ON, in between it stays.
    {
        Rig r;
        const float mid = 0.5f * (Cpx4Dsp::MUTE_OFF + Cpx4Dsp::MUTE_ON);
        r.tune(0, mid);
        bool a = r.dsp.isVoiceOn(0);
        r.tune(0, Cpx4Dsp::MUTE_OFF - 0.005f);
        bool b = r.dsp.isVoiceOn(0);
        r.tune(0, mid);
        bool c = r.dsp.isVoiceOn(0);
        r.tune(0, Cpx4Dsp::MUTE_ON + 0.005f);
        bool d = r.dsp.isVoiceOn(0);
        r.tune(0, mid);
        bool e = r.dsp.isVoiceOn(0);
        CHECK(a && !b && !c && d && e, "mute hysteresis %d %d %d %d %d", a, b, c, d, e);
        printf("  mute zone: off below %.0f %%, on above %.0f %%, no flicker in between\n",
               100.0f * Cpx4Dsp::MUTE_OFF, 100.0f * Cpx4Dsp::MUTE_ON);
    }

    // No pop: a voice alone, turned on from 0 to just above the zone and off
    // again. Its fade-in / fade-out steps no more than its steady waveform
    // plus the fade's own slope; switched with no fade, the same take jumps
    // far more.
    for (int k = 0; k < 4; k += 3) {
        Rig r;
        for (int v = 0; v < 4; v++) r.tune(v, 0.0f);
        r.run(22050);
        Buf o;
        const int fade = (int)(0.05f * SR);
        r.tune(k, Cpx4Dsp::MUTE_ON + 0.01f);
        r.run(22050, &o);
        float lvl5 = 0.0f;
        {
            Rig t;
            for (int v = 0; v < 4; v++) t.tune(v, 0.0f);
            t.run(22050);
            t.tune(k, Cpx4Dsp::MUTE_ON + 0.01f);
            t.run((int)(0.005f * SR));
            lvl5 = t.dsp.getVoiceLevel(k);
        }
        float steady = maxStep(o, 11025, 22050);
        float onStep = maxStep(o, 0, fade);
        size_t offAt = o.size();
        r.tune(k, 0.0f);
        r.run(22050, &o);
        float offStep = maxStep(o, offAt - 1, offAt + fade);
        // The same waveform switched hard at its peak.
        float hard = peakAbs(o, 11025, 22050);
        // The fade itself may add at most level / fade length per sample
        // (at a slow 28 Hz wave that is about as much as the wave's own
        // slope, so where in the cycle the fade lands matters).
        const float fadeSlope = hard / (Cpx4Dsp::VOICE_FADE_MS * 0.001f * SR);
        const float limit = 1.2f * (steady + fadeSlope);
        CHECK(onStep < limit && offStep < limit && hard > 50.0f * limit,
              "TUNE %d on / off steps %.5f / %.5f, steady %.5f, hard switch %.4f", k + 1, onStep, offStep, steady, hard);
        CHECK(lvl5 > 0.2f && lvl5 < 0.5f, "TUNE %d fade at 5 ms %.2f", k + 1, lvl5);
        printf("  TUNE %d 0 -> %.0f %% -> 0: largest step %.5f / %.5f vs steady %.5f "
               "(a hard switch would jump %.4f); level %.2f after 5 ms\n",
               k + 1, 100.0f * (Cpx4Dsp::MUTE_ON + 0.01f), onStep, offStep, steady, hard, lvl5);
    }

    // A muted voice leaves the FM: with voice 2 off, MOD doesn't touch voice 1.
    {
        Rig a, b;
        a.tune(1, 0.0f); b.tune(1, 0.0f);
        a.set(lc::CC_MOD, 0); b.set(lc::CC_MOD, 127);
        a.reinit(); b.reinit();  // voice 2 off from the start, no fade-out
        Buf va, vb;
        a.run(44100, nullptr, nullptr, nullptr, true, &va);
        b.run(44100, nullptr, nullptr, nullptr, true, &vb);
        float diff = 0.0f;
        for (size_t i = 22050; i < va.size(); i++) diff = fmaxf(diff, fabsf(va[i] - vb[i]));
        CHECK(diff < 1e-5f, "muted voice 2 still modulates voice 1 (%.6f)", diff);
        printf("  voice 2 muted: MOD 0 vs 127 leaves voice 1 unchanged (%.1e)\n", diff);
    }
}

static void testSharp() {
    // White box: voice 1 alone. SHARP rounds the triangle's corners, then
    // squares it up: the crest factor falls from the triangle's sqrt(3)
    // through a sine's sqrt(2) to a square's 1 (H3 passes a null on the
    // way: +1/9 for the triangle, -1/3 for the square).
    double prev = 10.0;
    double h3[5], crest[5];
    for (int i = 0; i <= 4; i++) {
        Rig r;
        r.tune(0, 0.36f);  // ~95 Hz
        r.set(lc::CC_SHARP_A, (uint8_t)(i * 127 / 4));
        r.reinit();
        voiceShape(r, &h3[i], &crest[i]);
        CHECK(crest[i] < prev, "SHARP A %d: crest %.3f not falling", i, crest[i]);
        prev = crest[i];
    }
    CHECK(fabs(h3[0] + 19.1) < 1.5 && fabs(crest[0] - 1.732) < 0.03, "SHARP 0 = triangle (H3 %.1f dB, crest %.3f)",
          h3[0], crest[0]);
    CHECK(fabs(h3[4] + 9.5) < 1.0 && crest[4] < 1.05, "SHARP full = square (H3 %.1f dB, crest %.3f)", h3[4], crest[4]);
    printf("  SHARP A: voice 1 crest %.2f / %.2f / %.2f / %.2f / %.2f (triangle 1.73, square 1.00), "
           "H3 %.1f / %.1f / %.1f / %.1f / %.1f dB\n",
           crest[0], crest[1], crest[2], crest[3], crest[4], h3[0], h3[1], h3[2], h3[3], h3[4]);

    // SHARP A only shapes pair A, SHARP B only pair B (white-box gains).
    Rig a; a.set(lc::CC_SHARP_A, 127); a.run(4000);
    Rig b; b.set(lc::CC_SHARP_B, 127); b.run(4000);
    Rig n; n.run(4000);
    CHECK(a.dsp.getSharpGain(0) > 10.0f && a.dsp.getSharpGain(1) > 10.0f &&
          a.dsp.getSharpGain(2) == n.dsp.getSharpGain(2) && a.dsp.getSharpGain(3) == n.dsp.getSharpGain(3),
          "SHARP A shapes voices 1 + 2 only");
    CHECK(b.dsp.getSharpGain(2) > 10.0f && b.dsp.getSharpGain(3) > 10.0f &&
          b.dsp.getSharpGain(0) == n.dsp.getSharpGain(0) && b.dsp.getSharpGain(1) == n.dsp.getSharpGain(1),
          "SHARP B shapes voices 3 + 4 only");

    // Black box: SHARP B raises the odd harmonics of voices 3 / 4 in the mix
    // and leaves voices 1 / 2 alone.
    Buf o0, o1;
    Rig r0; r0.run(NFFT + 4000, &o0);
    Rig r1; r1.set(lc::CC_SHARP_B, 127); r1.reinit(); r1.run(NFFT + 4000, &o1);
    auto p0 = spectrum(o0), p1 = spectrum(o1);
    double f3 = r0.dsp.getVoiceHz(2), f1 = r0.dsp.getVoiceHz(0);
    double rise3 = dbp(harmonic(p1, f3, 3) / harmonic(p0, f3, 3));
    double rise1 = dbp(harmonic(p1, f1, 3) / harmonic(p0, f1, 3));
    CHECK(rise3 > 6.0 && fabs(rise1) < 1.0, "SHARP B in the mix: voice 3 H3 %+.1f dB, voice 1 H3 %+.1f dB", rise3, rise1);
    printf("  SHARP B in the mix: voice 3 H3 %+.1f dB, voice 1 H3 %+.1f dB\n", rise3, rise1);

    // Anti-alias cap: at the top of pair B the edge stays 2 samples wide.
    Rig hi; hi.tune(3, 1.0f); hi.set(lc::CC_SHARP_B, 127); hi.run(8000);
    CHECK(hi.dsp.getSharpGain(3) <= 2.0f * SR / (4.0f * hi.dsp.getVoiceHz(3)) + 1e-3f, "SHARP gain capped");
}

static void testMod() {
    // MOD: from clean lines to FM sidebands to noise, in both pairs.
    double inh[5];
    for (int i = 0; i <= 4; i++) {
        Rig r;
        r.set(lc::CC_MOD, (uint8_t)(i * 127 / 4));
        r.reinit();
        Buf o;
        r.run(NFFT + 8000, &o);
        double f0[4];
        for (int v = 0; v < 4; v++) f0[v] = r.dsp.getVoiceHz(v);
        inh[i] = inharmonicDb(spectrum(o), f0);
    }
    CHECK(inh[0] < -40.0, "MOD 0 clean (%.1f dB off-harmonic)", inh[0]);
    // Rises until most of the power is off the harmonics (chaos), then stays.
    for (int i = 1; i <= 4; i++) {
        CHECK(inh[i] > inh[i - 1] || (inh[i - 1] > -4.0 && inh[i] > -4.0), "MOD step %d not rising (%.1f)", i, inh[i]);
    }
    CHECK(inh[1] < -10.0 && inh[2] < -4.0, "MOD low / mid not yet chaos (%.1f / %.1f dB)", inh[1], inh[2]);
    CHECK(inh[4] > -4.0, "MOD full noisy (%.1f dB)", inh[4]);
    printf("  MOD: off-harmonic power %.1f / %.1f / %.1f / %.1f / %.1f dB at 0 / 25 / 50 / 75 / 100 %%\n",
           inh[0], inh[1], inh[2], inh[3], inh[4]);
}

// Voice 1's output under a change of `cc` (or TUNE 3) at a routing.
static bool voice1Changes(int routing, int what) {
    Buf a, b;
    for (int pass = 0; pass < 2; pass++) {
        Rig r;
        r.set(lc::CC_MOD, 90);
        r.set(lc::CC_ROUTING, routingCc(routing));
        r.set(lc::CC_DELAY_MIX, 64);
        r.set(lc::CC_FEEDBACK, 60);
        if (pass == 1) {
            if (what == 0) r.tune(2, 0.7f);
            if (what == 1) r.set(lc::CC_DELAY_MIX, 127);
            if (what == 2) r.set(lc::CC_DRIVE, 127);
        }
        r.reinit();
        r.run(20000, nullptr, nullptr, nullptr, true, pass ? &b : &a);
    }
    double d = 0.0;
    for (size_t i = 0; i < a.size(); i++) d = std::max(d, (double)fabsf(a[i] - b[i]));
    return d > 1e-3;
}

static void testRouting() {
    // PAIRS: voice 1 only hears voice 2. LOOP: also pair B. TOTAL FB: also
    // the output (delay, drive).
    CHECK(!voice1Changes(0, 0) && !voice1Changes(0, 1) && !voice1Changes(0, 2), "PAIRS: voice 1 isolated");
    CHECK(voice1Changes(1, 0) && !voice1Changes(1, 1) && !voice1Changes(1, 2), "LOOP: voice 1 hears pair B only");
    CHECK(voice1Changes(2, 1) && voice1Changes(2, 2), "TOTAL FB: voice 1 hears the output (delay, drive)");
    // With MOD at 0 no routing modulates anything.
    for (int routing = 0; routing < 3; routing++) {
        Rig r;
        r.set(lc::CC_ROUTING, routingCc(routing));
        r.reinit();
        Buf o;
        r.run(NFFT + 8000, &o);
        double f0[4];
        for (int v = 0; v < 4; v++) f0[v] = r.dsp.getVoiceHz(v);
        CHECK(inharmonicDb(spectrum(o), f0) < -40.0, "routing %d at MOD 0 clean", routing);
    }
    printf("  FM routing: PAIRS isolates the pairs, LOOP couples pair A <-> B, TOTAL FB feeds the output back\n");
}

static void testDrive() {
    // A 0.5 sine into the drive (voices off, dry only): harmonics rise with
    // DRIVE, the level stays usable.
    const float f = 220.0f;
    Buf in(NFFT + 8000);
    for (size_t i = 0; i < in.size(); i++) in[i] = 0.5f * (float)sin(2.0 * M_PI * f * i / SR);
    double thd[5], lvl[5], h2[5];
    for (int i = 0; i <= 4; i++) {
        Rig r;
        r.set(lc::CC_DRIVE, (uint8_t)(i * 127 / 4));
        r.reinit();
        Buf o;
        r.run((int)in.size(), &o, nullptr, &in, false);
        auto p = spectrum(o);
        double fund = harmonic(p, f, 1), dist = 0.0;
        for (int h = 2; h <= 9; h++) dist += harmonic(p, f, h);
        thd[i] = 100.0 * sqrt(dist / fund);
        h2[i] = dbp(harmonic(p, f, 2) / fund);
        lvl[i] = 20.0 * log10(rms(o, 8000) / (0.5 / sqrt(2.0)));
    }
    CHECK(thd[0] < 2.0, "DRIVE 0 clean (THD %.2f %%)", thd[0]);
    for (int i = 1; i <= 4; i++) CHECK(thd[i] > thd[i - 1], "DRIVE step %d THD not rising", i);
    CHECK(thd[4] > 30.0, "DRIVE full THD %.1f %%", thd[4]);
    CHECK(h2[2] > -40.0, "DRIVE adds even harmonics (H2 %.1f dB)", h2[2]);
    for (int i = 0; i <= 4; i++) CHECK(lvl[i] > -3.0 && lvl[i] < 9.0, "DRIVE %d level %.1f dB", i, lvl[i]);
    printf("  DRIVE: THD %.1f / %.1f / %.1f / %.1f / %.1f %%, level %+.1f / %+.1f / %+.1f / %+.1f / %+.1f dB\n",
           thd[0], thd[1], thd[2], thd[3], thd[4], lvl[0], lvl[1], lvl[2], lvl[3], lvl[4]);
}

static void testDelayTime() {
    // A burst, DELAY MIX full (wet only), no feedback: the echo arrives after
    // the set time on OUT 1, after 0.97 x on OUT 2.
    const uint8_t values[] = {0, 32, 64, 96, 127};
    for (uint8_t v : values) {
        Rig r;
        r.set(lc::CC_DELAY_TIME, v);
        r.set(lc::CC_DELAY_MIX, 127);
        r.reinit();
        double t = Cpx4Dsp::DELAY_MIN_S * pow(Cpx4Dsp::DELAY_MAX_S / Cpx4Dsp::DELAY_MIN_S, v / 127.0);
        int at = 1000, n = at + (int)(t * SR) + 4000;
        Buf in = burst(n, at), l, rr;
        r.run(n, &l, &rr, &in, false);
        // Echo window start - burst start - the limiter look-ahead.
        size_t skip = at + PolyLevel::LIMIT_LOOKAHEAD + 16;
        double e1 = ((double)energyPeak(l, skip, n) - at - PolyLevel::LIMIT_LOOKAHEAD) / SR;
        double e2 = ((double)energyPeak(rr, skip, n) - at - PolyLevel::LIMIT_LOOKAHEAD) / SR;
        CHECK(fabs(e1 - t) < 0.01 * t + 2.0 / SR, "DELAY TIME CC %d: OUT 1 echo %.4f s, set %.4f", v, e1, t);
        CHECK(fabs(e2 - 0.97 * t) < 0.01 * t + 2.0 / SR, "DELAY TIME CC %d: OUT 2 echo %.4f s", v, e2);
        printf("  DELAY TIME CC %3d: echo %.1f ms (set %.1f), OUT 2 %.1f ms\n", v, e1 * 1000, t * 1000, e2 * 1000);
    }
    // A time change glides (tape): the read position moves gradually.
    Rig r;
    r.set(lc::CC_DELAY_TIME, 100);
    r.reinit();
    r.set(lc::CC_DELAY_TIME, 110);
    r.run(441);  // 10 ms
    CHECK(r.dsp.getDelaySeconds(0) > 0.0f, "delay glide");
}

// Echo energy after the first echo (tail) for a feedback CC.
static double tailDb(uint8_t fbCc, double* lastSecondDb = nullptr, float* peak = nullptr) {
    Rig r;
    r.set(lc::CC_DELAY_TIME, 80);  // ~78 ms
    r.set(lc::CC_DELAY_MIX, 127);
    r.set(lc::CC_FEEDBACK, fbCc);
    r.reinit();
    int n = (int)(4.0f * SR);
    Buf in = noiseBurst(n, 1000), l;
    r.run(n, &l, nullptr, &in, false);
    double t = r.dsp.getDelaySeconds(0);
    size_t firstEnd = 1000 + 882 + (size_t)(1.5 * t * SR);
    double first = rms(l, 1000, firstEnd);
    double tail = rms(l, firstEnd, n);
    if (lastSecondDb) *lastSecondDb = 20.0 * log10(rms(l, n - (int)SR, n) / first + 1e-12);
    if (peak) *peak = peakAbs(l);
    return 20.0 * log10(tail / first + 1e-12);
}

static void testFeedback() {
    double tails[5];
    for (int i = 0; i <= 4; i++) tails[i] = tailDb((uint8_t)(i * 127 / 4));
    // No second echo: what is left is the output DC blocker settling.
    CHECK(tails[0] < -50.0, "FEEDBACK 0: one echo (tail %.1f dB)", tails[0]);
    for (int i = 1; i <= 4; i++) CHECK(tails[i] > tails[i - 1], "FEEDBACK step %d tail not rising", i);
    double last;
    float peak;
    tailDb(127, &last, &peak);
    CHECK(last > -20.0, "FEEDBACK full sustains (last second %.1f dB)", last);
    CHECK(peak < 0.96f, "FEEDBACK full bounded (peak %.3f)", peak);
    double lastHalf;
    tailDb(64, &lastHalf);
    CHECK(lastHalf < -30.0, "FEEDBACK half dies away (last second %.1f dB)", lastHalf);
    printf("  FEEDBACK: tail %.0f / %.1f / %.1f / %.1f / %.1f dB; full: last second %.1f dB, peak %.2f\n",
           tails[0], tails[1], tails[2], tails[3], tails[4], last, peak);
    // Damping follows FEEDBACK (darker repeats).
    Rig a; a.run(1000);
    Rig b; b.set(lc::CC_FEEDBACK, 127); b.run(20000);
    CHECK(a.dsp.getDampHz() > 11000.0f && b.dsp.getDampHz() < 2600.0f, "damping %.0f -> %.0f Hz",
          a.dsp.getDampHz(), b.dsp.getDampHz());
    printf("  FEEDBACK damping: %.0f Hz at 0 -> %.0f Hz at full\n", a.dsp.getDampHz(), b.dsp.getDampHz());
}

static void testMix() {
    double dryDb[3], wetDb[3];
    const uint8_t values[3] = {0, 64, 127};
    for (int i = 0; i < 3; i++) {
        Rig r;
        r.set(lc::CC_DELAY_TIME, 80);
        r.set(lc::CC_DELAY_MIX, values[i]);
        r.reinit();
        int n = (int)(0.5f * SR);
        Buf in = burst(n, 1000), l;
        r.run(n, &l, nullptr, &in, false);
        size_t dryAt = 1000 + PolyLevel::LIMIT_LOOKAHEAD;
        size_t echoAt = dryAt + (size_t)(r.dsp.getDelaySeconds(0) * SR);
        dryDb[i] = 20.0 * log10(rms(l, dryAt, dryAt + 64) / (0.5 / sqrt(2.0)) + 1e-12);
        wetDb[i] = 20.0 * log10(rms(l, echoAt, echoAt + 64) / (0.5 / sqrt(2.0)) + 1e-12);
    }
    // Levels relative to the dry burst at MIX 0 (the output gain is common).
    double ref = dryDb[0];
    CHECK(wetDb[0] - ref < -80.0, "MIX 0: dry only (%.1f / %.1f dB)", dryDb[0], wetDb[0]);
    CHECK(fabs(wetDb[2] - ref) < 0.5 && dryDb[2] - ref < -60.0, "MIX full: wet only, echo at the dry level (%.1f / %.1f dB)",
          dryDb[2], wetDb[2]);
    CHECK(fabs(dryDb[1] - wetDb[1]) < 0.5 && fabs(dryDb[1] - ref + 3.0) < 0.5, "MIX half: equal power (%.1f / %.1f dB)",
          dryDb[1], wetDb[1]);
    printf("  DELAY MIX (dB re dry at 0): dry / echo %.1f / %.0f at 0, %.1f / %.1f at half, %.0f / %.1f at full\n",
           0.0, wetDb[0] - ref, dryDb[1] - ref, wetDb[1] - ref, dryDb[2] - ref, wetDb[2] - ref);
}

static void testCutoff() {
    // Inverted: CC 0 = open (no filtering), CC 127 = 55 Hz.
    Rig lo; lo.set(lc::CC_CUTOFF, 127); lo.run(20000);
    Rig hi; hi.set(lc::CC_CUTOFF, 0); hi.run(20000);
    CHECK(fabsf(lo.dsp.getCutoffHz() - 55.0f) < 1.0f && fabsf(hi.dsp.getCutoffHz() - 17600.0f) < 200.0f,
          "CUTOFF range %.1f .. %.0f Hz", lo.dsp.getCutoffHz(), hi.dsp.getCutoffHz());
    // Noise in, voices off. Four one-pole stages at the cutoff: -12 dB there,
    // -28 dB an octave above (re the passband, as tools/sim_poly_filter.cpp).
    const uint8_t values[] = {107, 77, 47, 17};
    double prevRms = 0.0;
    for (uint8_t v : values) {
        Rig r;
        r.set(lc::CC_CUTOFF, v);
        r.reinit();
        Buf in = noise(NFFT + 20000, 0.2f), o;
        r.run((int)in.size(), &o, nullptr, &in, false);
        double fc = r.dsp.getCutoffHz();
        auto pi = spectrum(in), po = spectrum(o);
        auto gainAt = [&](double f) { return dbp(band(po, f * 0.97, f * 1.03) / band(pi, f * 0.97, f * 1.03)); };
        double pass = gainAt(fc / 4), atFc = gainAt(fc) - pass, stop = gainAt(fc * 2) - pass;
        CHECK(fabs(atFc + 12.0) < 1.5 && stop < -24.0,
              "CUTOFF CC %d (%.0f Hz): %.1f / %.1f / %.1f dB", v, fc, pass, atFc, stop);
        double level = rms(o, 20000);
        CHECK(level > prevRms, "CUTOFF CC %d not brighter than the CC above", v);
        prevRms = level;
        printf("  CUTOFF CC %3d = %6.0f Hz: re fc/4: fc %+.1f dB, 2 fc %+.1f dB\n", v, fc, atFc, stop);
    }
}

static void testResonance() {
    Rig r0; r0.run(1000);
    Rig r1; r1.set(lc::CC_RESONANCE, 64); r1.run(20000);
    Rig r2; r2.set(lc::CC_RESONANCE, 127); r2.run(20000);
    CHECK(r0.dsp.getResonanceK() == 0.0f && fabsf(r1.dsp.getResonanceK() - 3.0f) < 1e-3f &&
          fabsf(r2.dsp.getResonanceK() - 4.1f) < 1e-3f, "RESONANCE steps k");

    // Peak at the cutoff over the passband, noise in.
    double peak[2];
    for (int s = 0; s < 2; s++) {
        Rig r;
        r.set(lc::CC_CUTOFF, 57);
        r.set(lc::CC_RESONANCE, routingCc(s));
        r.reinit();
        Buf in = noise(NFFT + 20000, 0.2f), o;
        r.run((int)in.size(), &o, nullptr, &in, false);
        double fc = r.dsp.getCutoffHz();
        auto pi = spectrum(in), po = spectrum(o);
        auto gainAt = [&](double f) { return dbp(band(po, f * 0.95, f * 1.05) / band(pi, f * 0.95, f * 1.05)); };
        peak[s] = gainAt(fc) - gainAt(fc / 4);
    }
    CHECK(peak[0] < -10.0 && peak[1] > 9.0, "RESONANCE Off %.1f dB, Peak %+.1f dB at the cutoff", peak[0], peak[1]);
    printf("  RESONANCE: cutoff vs passband %+.1f dB (Off), %+.1f dB (Peak)\n", peak[0], peak[1]);

    // Sing: a click, then silence: the filter keeps ringing at the cutoff.
    const uint8_t cutoffs[] = {107, 87, 67, 47, 27, 12};
    for (uint8_t c : cutoffs) {
        Rig r;
        r.set(lc::CC_CUTOFF, c);
        r.set(lc::CC_RESONANCE, 127);
        r.reinit();
        int n = NFFT + (int)(2.0f * SR);
        Buf in = burst(n, 100, 0.05f), o;
        r.run(n, &o, nullptr, &in, false);
        double fc = r.dsp.getCutoffHz();
        auto p = spectrum(o);
        double f = peakHz(p, 20.0, 20000.0);
        double level = rms(o, n - NFFT);
        CHECK(fabs(1200.0 * log2(f / fc)) < 100.0 && level > 0.05 && peakAbs(o) < 0.96f,
              "Sing at CUTOFF CC %d: %.1f Hz (fc %.1f), rms %.3f", c, f, fc, level);
        printf("  RESONANCE Sing, CUTOFF CC %3d: sings %.1f Hz (cutoff %.1f, %+.0f cents), %.1f dBFS rms\n",
               c, f, fc, 1200.0 * log2(f / fc), 20.0 * log10(level));
    }
    // Sing with the drone and drive: the tone stays on top.
    Rig r;
    r.set(lc::CC_CUTOFF, 37);
    r.set(lc::CC_RESONANCE, 127);
    r.set(lc::CC_DRIVE, 80);
    r.reinit();
    Buf o;
    r.run(NFFT + 40000, &o);
    auto p = spectrum(o);
    double fc = r.dsp.getCutoffHz();
    double tone = band(p, fc * 0.97, fc * 1.03), all = band(p, 20.0, 20000.0);
    CHECK(dbp(tone / all) > -10.0, "Sing over the drone: tone %.1f dB of the output", dbp(tone / all));
    printf("  RESONANCE Sing over the driven drone: tone at the cutoff = %.1f dB of the output\n", dbp(tone / all));
}

static void testPitchAndPanic() {
    Rig r;
    double f = r.dsp.getVoiceHz(0);
    r.dsp.setTransposeNote(72);
    r.run(8000);
    CHECK(fabs(1200.0 * log2(r.dsp.getVoiceHz(0) / f) - 1200.0) < 2.0 * Cpx4Dsp::DRIFT_CENTS, "note 72 = +1 octave");
    r.dsp.setTransposeNote(48);
    r.run(8000);
    CHECK(fabs(1200.0 * log2(r.dsp.getVoiceHz(2) / Rig().dsp.getVoiceHz(2)) + 1200.0) < 2.0 * Cpx4Dsp::DRIFT_CENTS,
          "note 48 = -1 octave");
    printf("  PITCH: note 72 / 48 transpose all voices +1 / -1 octave\n");

    // All Sound Off empties a self-sustaining delay.
    Rig s;
    s.set(lc::CC_DELAY_MIX, 127);
    s.set(lc::CC_FEEDBACK, 127);
    s.reinit();
    s.run((int)(3 * SR));
    s.set(lc::CC_ALL_SOUND_OFF, 0);
    Buf o;
    s.run(LINE_SIZE + 4000, nullptr, nullptr, nullptr, false);
    s.run(8000, &o, nullptr, nullptr, false);
    CHECK(peakAbs(o) < 1e-3f, "All Sound Off clears the delay (peak %.5f)", peakAbs(o));
    printf("  CC120 All Sound Off: delay empty after one line length (peak %.5f)\n", peakAbs(o));
}

static void testStability() {
    // Everything up, TOTAL FB, Sing: bounded, finite, for a minute.
    Rig r;
    for (uint8_t c : lc::RECORDED_CCS) r.set(c, 127);
    r.set(lc::CC_CUTOFF, 0);  // inverted: fully open
    r.set(lc::CC_ROUTING, 127);
    r.set(lc::CC_RESONANCE, 127);
    r.tune(0, 1.0f); r.tune(1, 0.0f); r.tune(2, 1.0f); r.tune(3, 0.0f);
    r.reinit();
    bool finite = true;
    float peak = 0.0f;
    double sum = 0.0;
    for (int i = 0; i < (int)(60 * SR); i++) {
        float a, b;
        r.dsp.process(a, b);
        if (!std::isfinite(a) || !std::isfinite(b)) finite = false;
        peak = std::max(peak, std::max(fabsf(a), fabsf(b)));
        sum += (double)a * a;
    }
    CHECK(finite && peak <= 1.0f, "all-max stability: finite %d, peak %.3f", finite, peak);
    CHECK(sum > 0.0, "all-max makes sound");
    printf("  all controls up, TOTAL FB, Sing, 60 s: finite, peak %.3f, rms %.1f dBFS\n", peak,
           10.0 * log10(sum / (60 * SR)));
}

// --- listening WAVs -------------------------------------------------------

static void writeWav(const std::string& path, const Buf& l, const Buf& r) {
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) { printf("  cannot write %s\n", path.c_str()); return; }
    uint32_t n = (uint32_t)l.size(), data = n * 4, riff = 36 + data, fmtLen = 16, rate = 44100, bps = rate * 4;
    uint16_t fmt = 1, ch = 2, align = 4, bits = 16;
    fwrite("RIFF", 1, 4, f); fwrite(&riff, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
    fwrite(&fmtLen, 4, 1, f); fwrite(&fmt, 2, 1, f); fwrite(&ch, 2, 1, f); fwrite(&rate, 4, 1, f);
    fwrite(&bps, 4, 1, f); fwrite(&align, 2, 1, f); fwrite(&bits, 2, 1, f);
    fwrite("data", 1, 4, f); fwrite(&data, 4, 1, f);
    for (uint32_t i = 0; i < n; i++) {
        int16_t s[2] = {(int16_t)lrintf(fmaxf(-1.0f, fminf(1.0f, l[i])) * 32767.0f),
                        (int16_t)lrintf(fmaxf(-1.0f, fminf(1.0f, r[i])) * 32767.0f)};
        fwrite(s, 2, 2, f);
    }
    fclose(f);
}

// Render `seconds` while sweeping one CC 0 -> 127 (or a TUNE knob 0 -> 1).
static void sweep(const std::string& dir, const char* name, Rig& r, int cc, float seconds) {
    Buf l, rr;
    int n = (int)(seconds * SR);
    for (int i = 0; i < n; i += 441) {
        float pos = (float)i / n;
        if (cc >= 0) r.set((uint8_t)cc, (uint8_t)lrintf(pos * 127));
        else r.tune(-cc - 1, pos);
        r.run(441, &l, &rr);
    }
    writeWav(dir + "/" + name, l, rr);
}

static Rig defaultRig() {
    Rig r;
    for (int i = 0; i < 8; i++) r.set(lc::RECORDED_CCS[i], lc::SEED_CC[i]);
    r.reinit();
    return r;
}

static void writeWavs(const std::string& dir) {
    { Rig r = defaultRig(); Buf l, rr; r.run((int)(10 * SR), &l, &rr); writeWav(dir + "/drone_poweron.wav", l, rr); }
    { Rig r = defaultRig(); sweep(dir, "sweep_tune1.wav", r, -1, 10); }
    { Rig r = defaultRig(); sweep(dir, "sweep_tune4.wav", r, -4, 10); }
    {
        // Each knob in turn: 0 -> 6 % and back, 1 s apart (listen for pops).
        Rig r = defaultRig();
        Buf l, rr;
        for (int k = 0; k < 4; k++) {
            r.tune(k, 0.0f); r.run((int)SR, &l, &rr);
            r.tune(k, 0.06f); r.run((int)SR, &l, &rr);
            r.tune(k, 0.3f + 0.1f * k); r.run((int)SR, &l, &rr);
        }
        writeWav(dir + "/voice_mute_toggle.wav", l, rr);
    }
    { Rig r = defaultRig(); sweep(dir, "sweep_sharp_a.wav", r, lc::CC_SHARP_A, 10); }
    for (int routing = 0; routing < 3; routing++) {
        Rig r = defaultRig();
        r.set(lc::CC_ROUTING, routingCc(routing));
        r.set(lc::CC_DRIVE, 40);
        char name[64];
        snprintf(name, sizeof name, "sweep_mod_routing%d.wav", routing + 1);
        sweep(dir, name, r, lc::CC_MOD, 16);
    }
    { Rig r = defaultRig(); r.set(lc::CC_DELAY_MIX, 70); r.set(lc::CC_FEEDBACK, 100); sweep(dir, "sweep_delay_time.wav", r, lc::CC_DELAY_TIME, 16); }
    { Rig r = defaultRig(); r.set(lc::CC_DELAY_MIX, 70); r.set(lc::CC_DELAY_TIME, 90); sweep(dir, "sweep_feedback.wav", r, lc::CC_FEEDBACK, 16); }
    { Rig r = defaultRig(); r.set(lc::CC_DELAY_MIX, 70); sweep(dir, "sweep_drive.wav", r, lc::CC_DRIVE, 10); }
    for (int s = 0; s < 3; s++) {
        Rig r = defaultRig();
        r.set(lc::CC_DRIVE, 50); r.set(lc::CC_DELAY_MIX, 60); r.set(lc::CC_FEEDBACK, 70); r.set(lc::CC_MOD, 40);
        r.set(lc::CC_RESONANCE, routingCc(s));
        const char* names[3] = {"sweep_cutoff_res_off.wav", "sweep_cutoff_res_peak.wav", "sweep_cutoff_res_sing.wav"};
        sweep(dir, names[s], r, lc::CC_CUTOFF, 16);
    }
    printf("\n  wrote listening WAVs to %s\n", dir.c_str());
}

int main(int argc, char** argv) {
    std::string wavDir;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--wav") == 0 && i + 1 < argc) wavDir = argv[++i];
    }
    printf("cpx4 DSP host test\n");
    testControlMap();
    testMccFirmwareContract();
    testTune();
    testVoiceMute();
    testSharp();
    testMod();
    testRouting();
    testDrive();
    testDelayTime();
    testFeedback();
    testMix();
    testCutoff();
    testResonance();
    testPitchAndPanic();
    testStability();
    if (!wavDir.empty()) writeWavs(wavDir);
    printf("\n%d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
