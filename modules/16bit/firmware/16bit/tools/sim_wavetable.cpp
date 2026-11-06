// Host test of the polysynth wavetables (includes/audio/gen/wavetable_osc.h +
// wavetable_data.h): table data, mip level choice, aliasing, morph
// continuity, the Noise step and the P1 zone hysteresis. Run through
// ../test.sh.

#include <cmath>
#include <complex>
#include <cstdio>
#include <vector>

#include "audio/gen/wavetable_osc.h"

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
static const int ZONES = WAVETABLE_ZONE_COUNT;  // tables + Noise

// MIDI::midiNoteToHz (exact, as Voice passes it to the Wavetable).
static float noteHz(int note) {
    return 440 * pow(2, (note - 69) / 12.0);
}

// BM MIDI::midiNoteToFrequency (whole hertz).
static uint16_t noteHzBm(int note) {
    return 440 * pow(2, (note - 69) / 12.0);
}

static void fft(std::vector<std::complex<double>>& a) {
    const size_t n = a.size();
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (size_t len = 2; len <= n; len <<= 1) {
        std::complex<double> w(cos(-2 * M_PI / len), sin(-2 * M_PI / len));
        for (size_t i = 0; i < n; i += len) {
            std::complex<double> u(1);
            for (size_t k = 0; k < len / 2; k++) {
                auto x = a[i + k], y = a[i + k + len / 2] * u;
                a[i + k] = x + y;
                a[i + k + len / 2] = x - y;
                u *= w;
            }
        }
    }
}

static void checkData() {
    for (int t = 0; t < WAVETABLE_COUNT; t++) {
        for (int f = 0; f < WAVETABLE_FRAMES; f++) {
            int framePeak = 0;
            for (int l = 0; l < WAVETABLE_LEVELS; l++) {
                const int16_t* s = WAVETABLE_DATA + (t * WAVETABLE_FRAMES + f) * WAVETABLE_FRAME_STRIDE
                    + WAVETABLE_LEVEL_OFFSET[l];
                const int n = WAVETABLE_LEVEL_SIZE[l];
                CHECK((1u << (32 - WAVETABLE_LEVEL_SHIFT[l])) == (unsigned)n, "level %d size", l);
                int peak = 0;
                double dc = 0;
                for (int i = 0; i < n; i++) {
                    peak = std::max(peak, abs((int)s[i]));
                    dc += s[i];
                }
                dc /= n * 32768.0;
                CHECK(peak <= 31130, "%s f%d l%d peak %d", WAVETABLE_NAMES[t], f, l, peak);
                CHECK(fabs(dc) < 0.002, "%s f%d l%d dc %f", WAVETABLE_NAMES[t], f, l, dc);
                framePeak = std::max(framePeak, peak);
            }
            // Normalised on the loudest level (band-limiting overshoots).
            CHECK(framePeak > 31000, "%s f%d not normalised (%d)", WAVETABLE_NAMES[t], f, framePeak);
        }
    }
}

static void checkLevels() {
    for (int note = 0; note < 128; note++) {
        float hz = noteHz(note);
        if (hz < 1) continue;
        uint8_t l = WavetableOsc::levelFor(hz);
        if (l < WAVETABLE_LEVELS - 1) {
            CHECK(WAVETABLE_LEVEL_HARMONICS[l] * hz <= 20000.0f, "note %d level %d", note, l);
        }
        if (l > 0) {
            CHECK(WAVETABLE_LEVEL_HARMONICS[l - 1] * hz > 20000.0f, "note %d not the richest level", note);
        }
    }
}

// One sample as the app makes it: the shared control first, then the voice.
static float tickSample(WavetableOsc& osc, WavetableControl& control) {
    control.tick();
    return osc.getSample();
}

// Energy away from the harmonics of `hz` (aliases, interpolation images)
// relative to the total, in dB.
static double aliasDb(int table, float position, float hz) {
    WavetableControl control;
    control.frames = wavetableFrames(table);
    control.position = position;
    WavetableOsc osc;
    control.init(SR);
    osc.init(&control, SR);
    osc.setFrequency(hz);
    const int n = 32768;
    for (int i = 0; i < 2000; i++) tickSample(osc, control);
    std::vector<std::complex<double>> a(n);
    for (int i = 0; i < n; i++) {
        double w = 0.5 - 0.5 * cos(2 * M_PI * i / n);
        a[i] = tickSample(osc, control) * w;
    }
    fft(a);
    double total = 0, alias = 0;
    const double binHz = SR / n;
    for (int k = 1; k < n / 2; k++) {
        double p = std::norm(a[k]);
        double f = k * binHz;
        double h = f / hz;
        double dist = fabs(h - round(h)) * hz / binHz;  // bins from a harmonic
        total += p;
        if (dist > 4 && f < 20000) alias += p;
    }
    return 10 * log10(alias / total + 1e-30);
}

static void checkAliasing() {
    const int notes[] = {36, 60, 84, 96, 108};
    double worst = -1000;
    for (int t = 0; t < WAVETABLE_COUNT; t++) {
        for (int note : notes) {
            for (float pos : {0.0f, 7.5f, 15.0f}) {
                double db = aliasDb(t, pos, noteHz(note));
                worst = std::max(worst, db);
                CHECK(db < -40, "%s note %d pos %.1f alias %.1f dB", WAVETABLE_NAMES[t], note, pos, db);
            }
        }
    }
    printf("  worst alias / image energy: %.1f dB\n", worst);
}

static float maxStep(WavetableOsc& osc, WavetableControl& control, int n, bool sweep) {
    float prev = tickSample(osc, control);
    float worst = 0;
    for (int i = 0; i < n; i++) {
        if (sweep) {
            control.position = (WAVETABLE_FRAMES - 1) * (float)i / n;
        }
        float s = tickSample(osc, control);
        worst = std::max(worst, fabsf(s - prev));
        prev = s;
    }
    return worst;
}

// A one-second position sweep must not step further sample to sample than
// the steepest of the table's own frames does.
static void checkMorph() {
    for (int t = 0; t < WAVETABLE_COUNT; t++) {
        WavetableControl control;
        control.frames = wavetableFrames(t);
        float frames = 0;
        for (int f = 0; f < WAVETABLE_FRAMES; f++) {
            control.position = f;
            WavetableOsc osc;
            control.init(SR);
            osc.init(&control, SR);
            osc.setFrequency(110);
            frames = std::max(frames, maxStep(osc, control, 4096, false));
        }
        control.position = 0;
        WavetableOsc osc;
        control.init(SR);
        osc.init(&control, SR);
        osc.setFrequency(110);
        float sweep = maxStep(osc, control, (int)SR, true);
        CHECK(sweep <= frames * 1.05f + 0.01f, "%s morph step %.3f > frames %.3f",
              WAVETABLE_NAMES[t], sweep, frames);
    }
}

static void checkPitch() {
    WavetableControl control;
    WavetableOsc osc;
    control.init(SR);
    osc.init(&control, SR);
    osc.setFrequency(440);
    // Count rising zero crossings of Classic frame 0 (square).
    int crossings = 0;
    float prev = tickSample(osc, control);
    for (int i = 0; i < (int)SR; i++) {
        float s = tickSample(osc, control);
        if (prev < 0 && s >= 0) crossings++;
        prev = s;
    }
    CHECK(abs(crossings - 440) <= 1, "440 Hz gave %d cycles", crossings);

    // Every note on its equal-tempered pitch (whole-hertz notes were up to
    // 18 cents flat, so chords beat like detuned voices on long notes): the
    // period from interpolated rising zero crossings over 4 s.
    double worst = 0;
    for (int note = 24; note <= 108; note++) {
        WavetableOsc n;
        n.init(&control, SR);
        n.setFrequency(noteHz(note));
        double first = -1, last = -1;
        int cycles = -1;
        float p = n.getSample();
        for (int i = 1; i < 4 * (int)SR; i++) {
            float s = n.getSample();
            if (p < 0 && s >= 0) {
                last = i - 1 + p / (double)(p - s);
                if (first < 0) first = last;
                cycles++;
            }
            p = s;
        }
        double hz = cycles * SR / (last - first);
        double cents = 1200 * log2(hz / (440 * pow(2, (note - 69) / 12.0)));
        worst = std::max(worst, fabs(cents));
        CHECK(fabs(cents) < 0.1, "note %d %.3f Hz off by %.3f cents", note, hz, cents);
    }
    printf("pitch: worst note error %.4f cents (notes 24..108)\n", worst);

    // setFrequencyHz() default: the BM generators still get whole hertz.
    for (int note = 0; note < 128; note++) {
        CHECK((uint16_t)noteHz(note) == noteHzBm(note), "note %d BM rounding", note);
    }
}

static void checkZones() {
    const float hyst = 0.15f;
    uint8_t z = 0;
    // Sweep up and down: every zone reached, in order, no flip-flops.
    int changes = 0;
    for (int i = 0; i <= 1000; i++) {
        uint8_t next = wavetableZoneFor(i / 1000.0f, z, ZONES, hyst);
        if (next != z) {
            CHECK(next == z + 1, "up sweep jumped %d -> %d", z, next);
            changes++;
        }
        z = next;
    }
    CHECK(z == ZONES - 1 && changes == ZONES - 1, "up sweep ended at %d after %d", z, changes);
    for (int i = 1000; i >= 0; i--) {
        uint8_t next = wavetableZoneFor(i / 1000.0f, z, ZONES, hyst);
        if (next != z) {
            CHECK(next + 1 == z, "down sweep jumped %d -> %d", z, next);
        }
        z = next;
    }
    CHECK(z == 0, "down sweep ended at %d", z);
    // Noise of +-0.1 zone around a boundary never changes the zone.
    for (uint8_t start : {(uint8_t)3, (uint8_t)4}) {
        z = start;
        for (int i = 0; i < 200; i++) {
            float norm = (4.0f + 0.1f * sinf(i * 0.7f)) / ZONES;
            z = wavetableZoneFor(norm, z, ZONES, hyst);
        }
        CHECK(z == start, "boundary noise moved zone %d -> %d", start, z);
    }
    // Recorded jumps land directly.
    CHECK(wavetableZoneFor(12.5f / ZONES, 2, ZONES, hyst) == 12, "jump to 12");
}

// Band power (dB) of a Hann-windowed FFT between lo and hi Hz, averaged.
static double bandDb(const std::vector<std::complex<double>>& a, double lo, double hi) {
    const double binHz = SR / a.size();
    double p = 0;
    int n = 0;
    for (size_t k = (size_t)(lo / binHz); k <= (size_t)(hi / binHz); k++) {
        p += std::norm(a[k]);
        n++;
    }
    return 10 * log10(p / n + 1e-30);
}

static std::vector<std::complex<double>> noiseSpectrum(WavetableOsc& osc, WavetableControl& control,
                                                       int frames, double* rms, float* peak) {
    const int n = 4096;
    std::vector<std::complex<double>> sum(n);
    double e = 0;
    *peak = 0;
    for (int f = 0; f < frames; f++) {
        std::vector<std::complex<double>> a(n);
        for (int i = 0; i < n; i++) {
            float s = tickSample(osc, control);
            CHECK(std::isfinite(s), "noise not finite");
            e += s * s;
            *peak = std::max(*peak, fabsf(s));
            a[i] = s * (0.5 - 0.5 * cos(2 * M_PI * i / n));
        }
        fft(a);
        for (int k = 0; k < n; k++) sum[k] += std::norm(a[k]);
    }
    for (auto& v : sum) v = sqrt(v.real());  // so bandDb's norm() is the power
    *rms = sqrt(e / ((double)frames * n));
    return sum;
}

// P1 on Noise: each P2 type at its level, with its spectral slope; the
// digital hold and the crackle follow the note; voices are uncorrelated.
static void checkNoise() {
    const char* names[] = {"brown", "pink", "white", "blue", "digital", "crackle"};
    const int types = WavetableControl::NOISE_TYPES;
    for (int t = 0; t < types; t++) {
        WavetableControl control;
        control.noise = true;
        control.position = t * (WAVETABLE_FRAMES - 1) / (float)(types - 1);
        control.init(SR);
        CHECK(control.noiseType + control.noiseMorph == t || (t == types - 1 && control.noiseType == types - 2
              && control.noiseMorph == 1.0f), "%s position -> type %d + %.3f", names[t],
              control.noiseType, control.noiseMorph);
        WavetableOsc osc;
        osc.init(&control, SR);
        osc.setFrequency(noteHz(60));
        double rms;
        float peak;
        auto a = noiseSpectrum(osc, control, 64, &rms, &peak);
        double low = bandDb(a, 200, 400), high = bandDb(a, 3200, 6400);
        printf("noise %-7s rms %.3f peak %.2f  3.2-6.4 kHz vs 200-400 Hz %+.1f dB\n",
               names[t], rms, peak, high - low);
        CHECK(peak <= 1.0f, "%s peak %.3f", names[t], peak);
        if (t < 5) {
            CHECK(rms > 0.2 && rms < 0.42, "%s rms %.3f", names[t], rms);
        } else {
            CHECK(rms > 0.05 && rms < 0.42, "%s rms %.3f", names[t], rms);
        }
        // 4 octaves: brown -6 dB / oct, pink -3, white 0, blue up.
        if (t == 0) CHECK(high - low < -18, "brown slope %.1f", high - low);
        if (t == 1) CHECK(high - low < -9 && high - low > -15, "pink slope %.1f", high - low);
        if (t == 2) CHECK(fabs(high - low) < 1.5, "white slope %.1f", high - low);
        if (t == 3) CHECK(high - low > 12, "blue slope %.1f", high - low);
    }

    // Digital: a held level every 1 / (8 f), so its first spectral null
    // moves with the note.
    for (int note : {48, 60}) {
        WavetableControl control;
        control.noise = true;
        control.position = 4 * (WAVETABLE_FRAMES - 1) / (float)(types - 1);
        control.init(SR);
        WavetableOsc osc;
        osc.init(&control, SR);
        const double hold = 8 * noteHz(note);
        osc.setFrequency(noteHz(note));
        double rms;
        float peak;
        auto a = noiseSpectrum(osc, control, 64, &rms, &peak);
        double nul = bandDb(a, hold * 0.97, hold * 1.03), lobe = bandDb(a, hold * 0.2, hold * 0.4);
        CHECK(nul < lobe - 15, "digital note %d: null at %.0f Hz only %.1f dB down", note, hold, lobe - nul);
    }

    // Crackle: about f / 2 clicks a second.
    for (int note : {48, 72}) {
        WavetableControl control;
        control.noise = true;
        control.position = WAVETABLE_FRAMES - 1;
        control.init(SR);
        WavetableOsc osc;
        osc.init(&control, SR);
        osc.setFrequency(noteHz(note));
        int clicks = 0;
        float prev = 0;
        for (int i = 0; i < 10 * (int)SR; i++) {
            float s = tickSample(osc, control);
            if (fabsf(s) > fabsf(prev) * 1.5f + 0.05f) clicks++;
            prev = s;
        }
        double expect = 10 * 0.5 * noteHz(note);
        CHECK(fabs(clicks - expect) < expect * 0.15, "crackle note %d: %d clicks, expected ~%.0f",
              note, clicks, expect);
    }

    // Two voices on one note don't play the same noise.
    {
        WavetableControl control;
        control.noise = true;
        control.position = 2 * (WAVETABLE_FRAMES - 1) / (float)(types - 1);
        control.init(SR);
        WavetableOsc a, b;
        a.init(&control, SR);
        b.init(&control, SR);
        a.setFrequency(220);
        b.setFrequency(220);
        double ab = 0, aa = 0, bb = 0;
        for (int i = 0; i < 44100; i++) {
            control.tick();
            float x = a.getSample(), y = b.getSample();
            ab += x * y;
            aa += x * x;
            bb += y * y;
        }
        double corr = ab / sqrt(aa * bb);
        CHECK(fabs(corr) < 0.05, "two voices' noise correlate %.3f", corr);
    }

    // A one-second P2 sweep across all types stays continuous (no jumps
    // beyond what the noise itself does).
    {
        WavetableControl control;
        control.noise = true;
        control.init(SR);
        WavetableOsc osc;
        osc.init(&control, SR);
        osc.setFrequency(220);
        float worst = 0;
        for (int i = 0; i < (int)SR; i++) {
            control.position = (WAVETABLE_FRAMES - 1) * (float)i / SR;
            float s = tickSample(osc, control);
            CHECK(std::isfinite(s) && fabsf(s) <= 1.0f, "sweep sample %f", s);
            worst = std::max(worst, fabsf(s));
        }
        CHECK(worst > 0.3f, "sweep silent (%f)", worst);
    }
}

int main() {
    checkData();
    checkLevels();
    checkPitch();
    checkMorph();
    checkZones();
    checkNoise();
    checkAliasing();
    printf("sim_wavetable: %d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
