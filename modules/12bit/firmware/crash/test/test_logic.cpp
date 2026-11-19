// Host tests for src/crash_logic.h. With a directory argument it also writes
// preview WAVs there (the DAC codes of a few knob settings, and the voice next
// to ../clapsnare), see ../test.sh.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <string>
#include <vector>
#include "clapsnare_logic.h"
#include "crash_logic.h"
#include "loudness.h"

using namespace crash;

static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); failures++; } } while (0)

static Tables T;

static Params params(uint16_t morph, uint16_t tone, uint16_t filter) { return makeParams(T, morph, tone, filter); }

// One hit: the Q15 samples until the voice goes idle (gate held, or released
// after `gateSamples`); linear = before the soft clipper.
static std::vector<int32_t> hit(uint16_t morph, uint16_t tone, uint16_t filter, uint8_t velocity = 127,
                                uint32_t seed = 0x2F6E2B1Du, uint32_t gateSamples = UINT32_MAX, bool linear = false) {
    Voice v;
    v.noise = seed;
    v.p = params(morph, tone, filter);
    v.trigger(velocity);
    std::vector<int32_t> out;
    while (v.active && out.size() < 10 * SAMPLE_RATE_HZ) {
        if (out.size() == gateSamples) v.release();
        out.push_back(linear ? v.renderLinear() : v.render());
    }
    return out;
}

static int32_t peak(const std::vector<int32_t> &s, size_t from = 0, size_t to = SIZE_MAX) {
    int32_t m = 0;
    for (size_t i = from; i < s.size() && i < to; i++) m = std::abs(s[i]) > m ? std::abs(s[i]) : m;
    return m;
}

// Over a fixed window: a hit that ended earlier counts as silence.
static double rms(const std::vector<int32_t> &s, size_t from, size_t to) {
    double sum = 0;
    for (size_t i = from; i < s.size() && i < to; i++) sum += (double)s[i] * s[i];
    return sqrt(sum / (double)(to - from));
}

// Power at one frequency over a window (Goertzel).
static double tonePower(const std::vector<int32_t> &s, size_t from, size_t to, double hz) {
    const double c = 2 * cos(6.283185307 * hz / SAMPLE_RATE_HZ);
    double s1 = 0, s2 = 0;
    for (size_t i = from; i < s.size() && i < to; i++) {
        const double s0 = s[i] + c * s1 - s2;
        s2 = s1;
        s1 = s0;
    }
    return s1 * s1 + s2 * s2 - c * s1 * s2;
}

// Power per 50 Hz bin over a window: 20 ms Hann frames, half overlapped (the
// bins of their DFT, so tones between the bins count too).
static const int BINS = 400;                    // up to 20 kHz
static std::vector<double> spectrum(const std::vector<int32_t> &s, size_t from, size_t to) {
    static const size_t FRAME = SAMPLE_RATE_HZ / 50;
    std::vector<double> bins(BINS, 0.0), frame(FRAME);
    for (size_t at = from; at + FRAME <= to; at += FRAME / 2) {
        for (size_t i = 0; i < FRAME; i++) {
            const double x = at + i < s.size() ? s[at + i] : 0;
            frame[i] = x * (0.5 - 0.5 * cos(6.283185307 * i / FRAME));
        }
        for (int k = 1; k < BINS; k++) {
            const double c = 2 * cos(6.283185307 * k / FRAME);
            double s1 = 0, s2 = 0;
            for (size_t i = 0; i < FRAME; i++) {
                const double s0 = frame[i] + c * s1 - s2;
                s2 = s1;
                s1 = s0;
            }
            bins[k] += s1 * s1 + s2 * s2 - c * s1 * s2;
        }
    }
    return bins;
}

// Power in a band, from a spectrum().
static double band(const std::vector<double> &bins, double loHz, double hiHz) {
    double sum = 0;
    for (int k = (int)(loHz / 50); k < BINS && k * 50 < hiHz; k++) sum += bins[k];
    return sum;
}

static double bandPower(const std::vector<int32_t> &s, size_t from, size_t to, double loHz, double hiHz) {
    return band(spectrum(s, from, to), loHz, hiHz);
}

// Spectral centroid over a window, Hz.
static double centroid(const std::vector<int32_t> &s, size_t from, size_t to) {
    const std::vector<double> bins = spectrum(s, from, to);
    double sum = 0, weighted = 0;
    for (int k = 4; k < BINS; k++) {
        sum += bins[k];
        weighted += bins[k] * k * 50;
    }
    return weighted / sum;
}

// 4-pole Butterworth low-pass at 12 kHz: the band the levels are matched in
// (as tools/calibrate.cpp; the hiss above it adds to the RMS, not to what is
// heard).
struct AudibleBand {
    double z[2][2] = {{0, 0}, {0, 0}};
    double run(double x) {
        static const double Q[2] = {0.54119610, 1.30656296};
        const double w = 6.283185307 * 12000.0 / SAMPLE_RATE_HZ;
        for (int i = 0; i < 2; i++) {
            const double alpha = sin(w) / (2 * Q[i]), a0 = 1 + alpha;
            const double b1 = (1 - cos(w)) / a0, a1 = -2 * cos(w) / a0, a2 = (1 - alpha) / a0;
            const double y = b1 / 2 * x + z[i][0];
            z[i][0] = b1 * x - a1 * y + z[i][1];
            z[i][1] = b1 / 2 * x - a2 * y;
            x = y;
        }
        return x;
    }
};

// Level of a setting as the level tables take it: RMS of the first 100 ms at
// the DAC below 12 kHz, dB re full scale, over a few hits (the crash differs
// from hit to hit).
static double levelDb(uint16_t morph, uint16_t tone, uint16_t filter) {
    double sum = 0;
    for (uint32_t seed = 1; seed <= 4; seed++) {
        const std::vector<int32_t> s = hit(morph, tone, filter, 127, seed * 0x9E3779B9u);
        AudibleBand band;
        for (size_t i = 0; i < SAMPLE_RATE_HZ / 10; i++) {
            const double y = band.run(i < s.size() ? s[i] : 0);
            sum += y * y;
        }
    }
    return 10 * log10(sum / (4 * (SAMPLE_RATE_HZ / 10) * 32768.0 * 32768.0));
}

static double incHz(uint32_t inc) { return inc * (double)SAMPLE_RATE_HZ / 4294967296.0; }
static double filterHz(const Params &p) { return atan(p.filterG / 32768.0) * SAMPLE_RATE_HZ / 3.14159265; }
static double filterQ(const Params &p) {
    const double g = p.filterG / 32768.0;
    return 1.0 / ((32768.0 / p.filterA1 - 1.0) / g - g);
}

static double bandHz(const Band &b) { return atan(b.g / 8192.0) * SAMPLE_RATE_HZ / 3.14159265; }
static double bandQ(const Band &b) {
    const double g = b.g / 8192.0;
    return 1.0 / ((8192.0 / b.a1 - 1.0) / g - g);
}

static void testParams() {
    // TONE fully left, crash: the TR-808 oscillator bank, noise low-pass
    // 3 kHz, high-pass 2 kHz, bands 3.6 and 7.1 kHz; fully right: all of it
    // x1.5; in between every part by the same ratio
    Params lo = params(0, 0, 0), hi = params(0, KNOB_MAX, 0);
    const double bank[PARTIALS] = {205.3, 304.4, 369.6, 522.7, 540.0, 800.0};
    for (int i = 0; i < PARTIALS; i++) {
        CHECK(fabs(incHz(lo.inc[i]) / bank[i] - 1) < 0.001);
        CHECK(fabs(incHz(hi.inc[i]) / (bank[i] * 1.5) - 1) < 0.002);
    }
    auto corner = [](int32_t a) { return -log(1.0 - a / 32768.0) * SAMPLE_RATE_HZ / 6.2831853; };
    CHECK(fabs(corner(lo.crashNoiseA) - 3000) < 8 && fabs(corner(lo.crashHpA) - 2000) < 5);
    CHECK(fabs(bandHz(lo.crashLow) - 3600) < 10 && fabs(bandHz(lo.crashHigh) - 7100) < 15);
    for (uint16_t t = 0; t <= KNOB_MAX; t += 15) {
        const Params p = params(0, t, 0);
        const double r = incHz(p.inc[0]) / 205.3;
        CHECK(fabs(incHz(p.inc[5]) / (800 * r) - 1) < 0.001);
        CHECK(fabs(corner(p.crashNoiseA) / (3000 * r) - 1) < 0.01 && fabs(corner(p.crashHpA) / (2000 * r) - 1) < 0.01);
        CHECK(fabs(bandHz(p.crashLow) / (3600 * r) - 1) < 0.01 && fabs(bandHz(p.crashHigh) / (7100 * r) - 1) < 0.01);
        CHECK(fabs(bandQ(p.crashLow) - 1) < 0.02 && fabs(bandQ(p.crashHigh) - 1.5) < 0.03);
        if (t) CHECK(p.inc[0] >= params(0, t - 15, 0).inc[0]);
    }
    // TONE, cowbell: 540 + 800 Hz fully left (TR-808), an octave up fully right
    Params bell = params(KNOB_MAX, 0, 0);
    CHECK(fabs(incHz(bell.bellInc[0]) - 540) < 0.5 && fabs(incHz(bell.bellInc[1]) - 800) < 1);
    CHECK(fabs(incHz(params(KNOB_MAX, 2048, 0).bellInc[0]) - 763.8) < 1);
    CHECK(fabs(incHz(params(KNOB_MAX, KNOB_MAX, 0).bellInc[0]) - 1080) < 1);
    for (uint16_t t = 0; t <= KNOB_MAX; t += 15) {
        const Params p = params(KNOB_MAX, t, 0);
        CHECK(fabs(incHz(p.bellInc[1]) / incHz(p.bellInc[0]) - 800.0 / 540.0) < 0.001);
        // band-pass at 1.67 x the first tone (2 sin(pi fc / fs), Q15)
        const double fc = asin(p.bellF / 65536.0) * SAMPLE_RATE_HZ / 3.14159265;
        CHECK(fabs(fc / (incHz(p.bellInc[0]) * 900 / 540) - 1) < 0.01);
    }
    // MORPH: the ends are the pure sounds, equal power in between
    for (uint16_t m = 0; m <= MORPH_DEAD; m++) {
        CHECK(params(m, 2048, 0).bellLevel == 0 && params(m, 2048, 0).crashLevel == params(0, 2048, 0).crashLevel);
        CHECK(params(KNOB_MAX - m, 2048, 0).crashLevel == 0);
    }
    const double crashFull = params(0, 2048, 0).crashLevel, bellFull = params(KNOB_MAX, 2048, 0).bellLevel;
    int32_t lastBell = -1;
    for (uint16_t m = 0; m <= KNOB_MAX; m += 5) {
        const Params p = params(m, 2048, 0);
        const double c = p.crashLevel / crashFull, b = p.bellLevel / bellFull;
        CHECK(fabs(c * c + b * b - 1) < 0.01);
        CHECK(p.bellLevel >= lastBell);
        lastBell = p.bellLevel;
    }
    CHECK(fabs(params(2048, 2048, 0).crashLevel / crashFull - 0.7071) < 0.005);
    // FILTER: off at the bottom of the travel, 16 kHz .. 400 Hz above it,
    // the resonance in over the first 30 %
    for (uint16_t f = 0; f <= FILTER_DEAD; f++) CHECK(!params(2048, 2048, f).filterOn);
    Params f1 = params(2048, 2048, FILTER_DEAD + 1), fMax = params(2048, 2048, KNOB_MAX);
    CHECK(f1.filterOn && fabs(filterHz(f1) - 16000) < 50 && fabs(filterQ(f1) - 0.7071) < 0.01);
    CHECK(fMax.filterOn && fabs(filterHz(fMax) - 400) < 2 && fabs(filterQ(fMax) - 4) < 0.05);
    CHECK(fabs(filterHz(params(2048, 2048, (FILTER_DEAD + KNOB_MAX) / 2)) - 2530) < 30);   // sqrt(16k x 400)
    CHECK(fabs(filterQ(params(2048, 2048, FILTER_DEAD + 4055 * 3 / 20)) - 1.68) < 0.05);   // half way in
    CHECK(fabs(filterQ(params(2048, 2048, 1500)) - 4) < 0.05);
    for (uint16_t f = FILTER_DEAD + 2; f <= KNOB_MAX; f++) {
        CHECK(params(0, 0, f).filterG <= params(0, 0, f - 1).filterG);
    }
    // Nothing patched: the CV leaves FILTER off
    CHECK(!params(2048, 2048, applyCv(0, CV_ZERO + CV_DEAD)).filterOn);
}

// dB between the RMS of two windows of a hit.
static double dbBetween(const std::vector<int32_t> &s, size_t a, size_t b, size_t len) {
    return 20 * log10(rms(s, b, b + len) / rms(s, a, a + len));
}

// TONE fully left = the classic sounds (measured on TR-808 / TR-909 samples).
static void testClassic() {
    // Crash: the energy between 3 and 9 kHz (808: around 7 kHz, 909: 3 ..
    // 8 kHz), next to nothing below 1.5 kHz, not much air above 12 kHz
    double all = 0, mid = 0, low = 0, air = 0;
    for (uint32_t seed = 1; seed <= 4; seed++) {
        const std::vector<int32_t> s = hit(0, 0, 0, 127, seed, UINT32_MAX, true);
        all += bandPower(s, 0, 9600, 100, 20000);
        mid += bandPower(s, 0, 9600, 3000, 9000);
        low += bandPower(s, 0, 9600, 100, 1500);
        air += bandPower(s, 0, 9600, 12000, 20000);
    }
    CHECK(mid > 0.6 * all && low < 0.01 * all && air < 0.12 * all);
    // ... a long ring with the gate held: -10 dB in 0.25 .. 0.55 s, -20 dB
    // in 0.6 .. 1 s (808 long decay: 0.17 / 0.57 s, 909: 0.5 / 0.95 s)
    const std::vector<int32_t> c = hit(0, 0, 0, 127, 1, UINT32_MAX, true);
    CHECK(dbBetween(c, 0, 12000, 2400) > -10 && dbBetween(c, 0, 26400, 2400) < -10);
    CHECK(dbBetween(c, 0, 28800, 2400) > -20 && dbBetween(c, 0, 48000, 2400) < -20);
    // ... brighter at the start than in the tail
    auto bright = [&](size_t from, size_t to) { return bandPower(c, from, to, 5500, 9000) / bandPower(c, from, to, 2500, 5000); };
    CHECK(bright(0, 4800) > 1.3 * bright(24000, 48000));
    // Cowbell: the 800 Hz tone leads, the 540 Hz one and its octave are
    // about 12 dB under it and the higher partials fall away (808: -19 ..
    // -25 dB at 2.4 kHz)
    const std::vector<int32_t> b = hit(KNOB_MAX, 0, 0, 127, 1, UINT32_MAX, true);
    const double p800 = tonePower(b, 0, 9600, 800);
    auto rel = [&](double hz) { return 10 * log10(tonePower(b, 0, 9600, hz) / p800); };
    CHECK(rel(540) < -8 && rel(540) > -16 && rel(1080) < -8 && rel(1080) > -16);
    CHECK(rel(2400) < -17 && rel(1600) < -17 && rel(3200) < -24);
    // ... a hard strike (-10 dB after 20 ms) on a tail of 110 ms
    CHECK(dbBetween(b, 0, 960, 480) < -7 && dbBetween(b, 0, 960, 480) > -14);
    CHECK(fabs(dbBetween(b, 2400, 7680, 480) + 8.686 * 110.0 / 110.0) < 1.5);
}

static void testEnvelope() {
    // Crash, gate held: rings for 1.5 s; released at once: as long as the
    // 8bit envelope after note-off (16 bit at 22 kHz, env -= (env >> 9) + 1,
    // ends below 0x100)
    auto bmLength = [](int shift) {
        uint32_t env = 0xFFFF, n = 0;
        while (env >= 0x100) { env -= (env >> shift) + 1; n++; }
        return n / 22000.0;
    };
    const double ring = (double)hit(0, 2048, 0).size() / SAMPLE_RATE_HZ;
    const double tap = (double)hit(0, 2048, 0, 127, 1, 0).size() / SAMPLE_RATE_HZ;
    CHECK(ring > 1.35 && ring < 1.65);
    CHECK(fabs(tap / bmLength(9) - 1) < 0.15);
    // Released after 100 ms: in between
    const double held = (double)hit(0, 2048, 0, 127, 1, 4800).size() / SAMPLE_RATE_HZ;
    CHECK(held > 0.1 && held < 0.1 + tap);
    // Cowbell: shorter than the crash, and the gate cuts it too
    const double bell = (double)hit(KNOB_MAX, 2048, 0).size() / SAMPLE_RATE_HZ;
    const double bellTap = (double)hit(KNOB_MAX, 2048, 0, 127, 1, 0).size() / SAMPLE_RATE_HZ;
    CHECK(bell > 0.35 && bell < 0.6 && bellTap > 0.05 && bellTap < 0.13);
    // Layered: as long as the crash
    CHECK(fabs((double)hit(2048, 2048, 0).size() / SAMPLE_RATE_HZ - ring) < 0.01);
    // Velocity scales the level before the clipper, on the clapsnare curve
    // (100 = -3 dB, 64 = -8 dB); full velocity = the drive of the tables
    for (uint16_t m : {(uint16_t)0, KNOB_MAX}) {
        const double full = rms(hit(m, 2048, 0, 127, 1, UINT32_MAX, true), 0, 4800);
        const double half = rms(hit(m, 2048, 0, 64, 1, UINT32_MAX, true), 0, 4800);
        CHECK(fabs(half / full - 64.0 * 191.0 / (2 * 127.0 * 127.0)) < 0.02);
    }
    for (int vel = 1; vel <= 127; vel++) {
        Voice a;
        clapsnare::Voice b;
        a.p = params(2048, 2048, 0);
        a.trigger((uint8_t)vel);
        b.trigger((uint8_t)vel);
        CHECK(fabs(a.velGain * 256.0 / LEVELS.drive - b.velGain) < 1.5);
    }
    Voice loud;
    loud.p = params(2048, 2048, 0);
    loud.trigger(200);                                       // clamped to 127
    CHECK(loud.velGain == LEVELS.drive && LEVELS.drive <= DRIVE_MAX);
    CHECK(toDac(0) == DAC_MID && toDac(32767) <= DAC_MID + DAC_SWING && toDac(-32767) >= DAC_MID - DAC_SWING - 1);
    CHECK(softClip(40000) == 32767 && softClip(-40000) == -32767 && softClip(1000) == 1499);
    // Idle = 0 V; retrigger while sounding restarts it
    Voice v;
    CHECK(v.render() == 0);
    v.p = params(2048, 2048, 0);
    v.trigger(127);
    for (int i = 0; i < 9000; i++) v.render();
    v.release();
    v.render();
    v.trigger(100);
    CHECK(v.active && v.gate && v.ringEnv == ENV_FULL && v.sizzleEnv == ENV_FULL && v.tailEnv == ENV_FULL);
    // An engine that MORPH has faded out is not started
    v.p = params(0, 2048, 0);
    v.trigger(127);
    CHECK(v.ringEnv == ENV_FULL && v.tailEnv == 0);
    v.p = params(KNOB_MAX, 2048, 0);
    v.trigger(127);
    CHECK(v.ringEnv == 0 && v.tailEnv == ENV_FULL);
}

// The level tables: every setting plays at the same level, the cowbell
// BELL_LIFT_Q8 above the crash.
static void testLevels() {
    CHECK(LEVELS.drive > 256 && LEVELS.crashNorm[0] > 256 && LEVELS.bellNorm[0] > 256 && LEVELS.bellWeight > 0);   // not the stub
    const double lift = 20 * log10(BELL_LIFT_Q8 / 256.0);
    CHECK(fabs(lift - 1.5) < 0.05);
    const uint16_t morphs[] = {0, 700, 1400, 2048, 2700, 3400, KNOB_MAX};
    const uint16_t filters[] = {0, FILTER_DEAD + 1, 400, 800, 1200, 1600, 2000, 2400, 2800, 3200, 3600, KNOB_MAX};
    double lo = 1e9, hi = -1e9;
    for (uint16_t m : morphs) {
        double mLo = 1e9, mHi = -1e9;
        for (uint16_t t = 0; t <= KNOB_MAX; t += 315) {
            for (uint16_t f : filters) {
                const double db = levelDb(m, t, f);
                mLo = db < mLo ? db : mLo;
                mHi = db > mHi ? db : mHi;
            }
        }
        CHECK(mHi - mLo < 2.0);                  // over TONE x FILTER at one MORPH
        lo = mLo < lo ? mLo : lo;
        hi = mHi > hi ? mHi : hi;
    }
    // Everything: from the crash, 6 dB under full scale (driven into the
    // clipper: 4 dB above the level before the 2026-11-19 loudness match), up
    // to the cowbell
    CHECK(hi - lo < 2.5 + lift && lo > -7.5 && hi < -3.5);
    // The classic crash and cowbell and their brightest settings
    const double crashDb = levelDb(0, 0, 0);
    CHECK(fabs(crashDb - levelDb(0, KNOB_MAX, 0)) < 0.5);
    CHECK(fabs(crashDb + lift - levelDb(KNOB_MAX, 0, 0)) < 0.5);
    CHECK(fabs(crashDb + lift - levelDb(KNOB_MAX, KNOB_MAX, 0)) < 0.5);
    // Inside Q15 at every corner, the voice ends
    for (uint16_t m : {(uint16_t)0, (uint16_t)2048, KNOB_MAX}) {
        for (uint16_t t : {(uint16_t)0, (uint16_t)2048, KNOB_MAX}) {
            for (uint16_t f : {(uint16_t)0, (uint16_t)2048, KNOB_MAX}) {
                for (uint32_t seed = 1; seed <= 8; seed++) {
                    const std::vector<int32_t> s = hit(m, t, f, 127, seed * 0x9E3779B9u);
                    CHECK(peak(s) <= 32767 && peak(s) > 16000 && s.size() < 2 * SAMPLE_RATE_HZ);
                }
            }
        }
    }
}

// How loud it sounds, by the loudness model (tools/loudness.h): as the
// clapsnare clap with TONE and DECAY at noon, at every velocity.
static void testLoudness() {
    static const loudness::Model ear;
    static clapsnare::Tables tables;
    tables.fill();
    const uint32_t samples = 3 * SAMPLE_RATE_HZ / 10;
    auto clapsnarePhon = [&](uint16_t morph, uint8_t velocity) {
        double sum = 0;
        for (uint32_t seed = 1; seed <= 4; seed++) {
            clapsnare::Voice v;
            v.noise = seed * 0x9E3779B9u;
            v.p = clapsnare::makeParams(tables, morph, 2048, 2048);
            for (int n = 0; n < 100; n++) v.render(tables.sine);
            v.trigger(velocity);
            std::vector<double> s;
            for (uint32_t n = 0; n < samples; n++) s.push_back(v.render(tables.sine) / 32768.0);
            sum += ear.phon(s) / 4;
        }
        return sum;
    };
    auto phon = [&](uint16_t morph, uint16_t tone, uint8_t velocity) {
        double sum = 0;
        for (uint32_t seed = 1; seed <= 4; seed++) {
            Voice v;
            v.noise = seed * 0x9E3779B9u;
            v.p = params(morph, tone, 0);
            v.trigger(velocity);
            std::vector<double> s;
            for (uint32_t n = 0; n < samples; n++) s.push_back(v.render() / 32768.0);
            sum += ear.phon(s) / 4;
        }
        return sum;
    };
    const double clap = clapsnarePhon(0, 127), snare = clapsnarePhon(KNOB_MAX, 127);
    // The classic crash = the clap (fails after a change to the level of
    // either firmware: ../test.sh cal)
    CHECK(fabs(phon(0, 0, 127) - clap) < 0.5);
    CHECK(fabs(phon(0, 0, 100) - clapsnarePhon(0, 100)) < 1.0 && fabs(phon(0, 0, 64) - clapsnarePhon(0, 64)) < 1.0);
    // The cowbell: a short tonal hit, as loud as the snare, within 2 phon of
    // the clap (on a meter it reads 5 dB above the clap)
    const double bell = phon(KNOB_MAX, 0, 127);
    CHECK(bell > snare - 0.7 && bell > clap - 2.2 && bell < clap + 0.5);
    // Everything else stays near them
    for (uint16_t m : {(uint16_t)0, (uint16_t)1024, (uint16_t)2048, (uint16_t)3072, KNOB_MAX}) {
        for (uint16_t t : {(uint16_t)2048, KNOB_MAX}) {
            const double p = phon(m, t, 127);
            CHECK(p > clap - 3.7 && p < clap + 2.2);
        }
    }
    // The model itself: 1 kHz at 40 and 80 dB SPL is 40 and 80 phon, tones
    // on the 80 phon contour of ISO 226 are equally loud (6.3 kHz needs
    // 10 dB more than 3.15 kHz), noise is louder than a tone at the same
    // level
    auto tone = [](double hz, double spl) {
        std::vector<double> s(SAMPLE_RATE_HZ / 4);
        const double amp = pow(10, (spl - loudness::FULL_SCALE_SPL) / 20);
        for (size_t i = 0; i < s.size(); i++) s[i] = amp * sin(6.283185307 * hz * i / SAMPLE_RATE_HZ);
        return s;
    };
    CHECK(fabs(ear.phon(tone(1000, 40)) - 40) < 0.5 && fabs(ear.phon(tone(1000, 80)) - 80) < 1.5);
    for (double hz : {250.0, 3150.0, 6300.0}) CHECK(fabs(ear.phon(tone(hz, 80 - loudness::earWeightDb(hz))) - 80) < 2.5);
    CHECK(fabs(loudness::earWeightDb(3150) - loudness::earWeightDb(6300) - 9.7) < 0.2);
    std::vector<double> noise(SAMPLE_RATE_HZ / 4);
    uint32_t n = 0x2F6E2B1Du;
    for (double &x : noise) {
        n ^= n << 13;
        n ^= n >> 17;
        n ^= n << 5;
        x = (double)(int32_t)n / 2147483648.0 * 0.01732 * 0.7071;   // white, RMS = a sine of 60 dB SPL
    }
    CHECK(ear.phon(noise) > ear.phon(tone(1000, 60)) + 8);
}

static void testMorph() {
    // The cowbell tones come in with MORPH, the hiss of the crash goes
    double lastTone = 0, lastHiss = 1e30;
    for (uint16_t m : {(uint16_t)0, (uint16_t)1000, (uint16_t)2048, (uint16_t)3100, KNOB_MAX}) {
        double tone = 0, hiss = 0;
        for (uint32_t seed = 1; seed <= 4; seed++) {
            const std::vector<int32_t> s = hit(m, 0, 0, 127, seed);
            tone += tonePower(s, 0, 4800, 800) + tonePower(s, 0, 4800, 540);
            hiss += bandPower(s, 0, 4800, 6000, 9000);
        }
        CHECK(tone > lastTone && hiss < lastHiss);
        lastTone = tone;
        lastHiss = hiss;
    }
    // The pure cowbell: its two tones and their harmonics, nothing in between
    const std::vector<int32_t> bell = hit(KNOB_MAX, 0, 0, 127, 1, UINT32_MAX, true);
    const double p800 = tonePower(bell, 0, 9600, 800);
    for (double hz : {300.0, 670.0, 940.0, 1340.0, 1900.0}) CHECK(tonePower(bell, 0, 9600, hz) < 0.01 * p800);
    // ... the same every time, the crash never
    CHECK(hit(KNOB_MAX, 2048, 0, 127, 1) == hit(KNOB_MAX, 2048, 0, 127, 2));
    CHECK(hit(0, 2048, 0, 127, 1) != hit(0, 2048, 0, 127, 2));
}

static void testTone() {
    // TONE colours the crash: tuned up step by step, 6 kHz -> 9 kHz
    double lastCentre = 0;
    for (uint16_t t : {(uint16_t)0, (uint16_t)1365, (uint16_t)2730, KNOB_MAX}) {
        double centre = 0;
        for (uint32_t seed = 1; seed <= 4; seed++) centre += centroid(hit(0, t, 0, 127, seed, UINT32_MAX, true), 0, 9600) / 4;
        if (t == 0) CHECK(centre > 5000 && centre < 7500);
        CHECK(centre > lastCentre + 400);
        lastCentre = centre;
    }
    CHECK(lastCentre > 8000 && lastCentre < 10500);
    // ... and tunes the cowbell: its leading tone moves with it
    for (uint16_t t : {(uint16_t)0, (uint16_t)2048, KNOB_MAX}) {
        const std::vector<int32_t> s = hit(KNOB_MAX, t, 0, 127, 1, UINT32_MAX, true);
        const double f2 = incHz(params(KNOB_MAX, t, 0).bellInc[1]);
        CHECK(tonePower(s, 0, 9600, f2) > 30 * tonePower(s, 0, 9600, f2 * 1.2));
        CHECK(tonePower(s, 0, 9600, f2) > 30 * tonePower(s, 0, 9600, f2 / 1.2));
    }
}

// The filters of the crash stay far inside 32 bit: Q13 coefficients x states.
static void testCrashHeadroom() {
    int32_t worst = 0;
    for (uint16_t t = 0; t <= KNOB_MAX; t += 273) {
        for (uint32_t seed = 1; seed <= 4; seed++) {
            Voice v;
            v.noise = seed * 0x9E3779B9u;
            v.p = params(0, t, 0);
            v.trigger(127);
            for (uint32_t n = 0; n < 24000; n++) {
                v.render();
                for (int32_t st : {v.lowS1, v.lowS2, v.highS1, v.highS2, v.hp1, v.hp2}) worst = abs(st) > worst ? abs(st) : worst;
            }
        }
    }
    CHECK(worst < (1 << 16));   // x 8192 x 2 (the sums in band()) < 2^31
}

// The cowbell pulses are band-limited: what folds back from above 24 kHz is
// far below a plain pulse's.
static void testBandLimit() {
    const Params p = params(KNOB_MAX, KNOB_MAX, 0);   // 1080 Hz: harmonic 45 = 48.6 kHz folds to 600 Hz
    std::vector<int32_t> plain, clean;
    uint32_t phase = 0;
    int32_t top = 0;
    for (uint32_t i = 0; i < SAMPLE_RATE_HZ; i++) {
        phase += p.bellInc[0];
        plain.push_back(phase < BELL_WIDTH[0] ? 2048 : -2048);
        clean.push_back(blepPulse(phase, BELL_WIDTH[0], p.bellInc[0], p.bellRinc[0]));
        top = abs(clean.back()) > top ? abs(clean.back()) : top;
    }
    const double hz = 45 * incHz(p.bellInc[0]) - SAMPLE_RATE_HZ;
    CHECK(tonePower(clean, 0, SAMPLE_RATE_HZ, hz) < 0.01 * tonePower(plain, 0, SAMPLE_RATE_HZ, hz));
    const double f = incHz(p.bellInc[0]);
    CHECK(fabs(tonePower(clean, 0, SAMPLE_RATE_HZ, f) / tonePower(plain, 0, SAMPLE_RATE_HZ, f) - 1) < 0.05);
    CHECK(top <= 2048);
}

// Gain of the FILTER alone for a sine, at its make-up gain of 1.
static double filterGain(const Params &p, double hz) {
    Voice v;
    v.p = p;
    double in = 0, out = 0;
    for (uint32_t n = 0; n < 24000; n++) {
        const int32_t x = (int32_t)lrint(8000 * sin(6.283185307 * hz * n / SAMPLE_RATE_HZ));
        const int32_t y = v.filter(x);
        if (n < 12000) continue;
        in += (double)x * x;
        out += (double)y * y;
    }
    return sqrt(out / in);
}

static void testFilter() {
    // Fully left = no filter: the same samples as with it disabled by hand
    for (uint16_t f : {(uint16_t)0, FILTER_DEAD}) {
        Voice a, b;
        a.p = params(1500, 3000, f);
        b.p = params(1500, 3000, 0);
        b.p.filterOn = false;
        a.trigger(127);
        b.trigger(127);
        bool same = true;
        while (a.active || b.active) same &= a.render() == b.render();
        CHECK(same && a.s1 == 0);
    }
    // Just above the bypass: nothing to hear of it coming in (spectrum up to
    // 10 kHz within 0.5 dB), bright crash and cowbell
    for (uint16_t m : {(uint16_t)0, KNOB_MAX}) {
        CHECK(abs(params(m, KNOB_MAX, FILTER_DEAD + 1).filterGain - 256) <= 2);
        double off[4] = {0, 0, 0, 0}, on[4] = {0, 0, 0, 0};
        for (uint32_t seed = 1; seed <= 8; seed++) {
            const std::vector<int32_t> a = hit(m, KNOB_MAX, 0, 127, seed, UINT32_MAX, true);
            const std::vector<int32_t> b = hit(m, KNOB_MAX, FILTER_DEAD + 1, 127, seed, UINT32_MAX, true);
            for (int band = 0; band < 4; band++) {
                off[band] += bandPower(a, 0, 9600, 500 + 2500 * band, 2950 + 2500 * band);
                on[band] += bandPower(b, 0, 9600, 500 + 2500 * band, 2950 + 2500 * band);
            }
        }
        for (int band = 0; band < 4; band++) CHECK(fabs(10 * log10(on[band] / off[band])) < 0.5);
    }
    // The filter itself: flat below the corner, the resonance at it (Q 4 =
    // x4), 12 dB / octave above
    for (uint16_t f : {(uint16_t)1500, (uint16_t)2500, (uint16_t)3500, KNOB_MAX}) {
        const Params p = params(0, 2048, f);
        const double fc = filterHz(p);
        CHECK(fabs(filterGain(p, fc / 8) - 1) < 0.05);
        CHECK(fabs(filterGain(p, fc) / 4 - 1) < 0.08);
        if (fc < 1500) CHECK(fabs(filterGain(p, 4 * fc) * 15 - 1) < 0.15);   // higher up the top of the band bends it
    }
    const Params top = params(0, 2048, FILTER_DEAD + 1);   // where it comes in: no resonance
    CHECK(fabs(filterGain(top, 2000) - 1) < 0.01 && fabs(filterGain(top, 10000) - 1) < 0.03);
    // Turning it up takes the highs off, step by step (their share of the
    // sound: the make-up gain lifts everything) ...
    double last = 1e30;
    for (uint16_t f : {(uint16_t)0, (uint16_t)1000, (uint16_t)2000, (uint16_t)3000, KNOB_MAX}) {
        double high = 0, all = 0;
        for (uint32_t seed = 1; seed <= 4; seed++) {
            const std::vector<int32_t> s = hit(0, KNOB_MAX, f, 127, seed, UINT32_MAX, true);
            high += bandPower(s, 0, 9600, 9000, 12000);
            all += bandPower(s, 0, 9600, 100, 12000);
        }
        CHECK(high / all < (f <= 2000 ? 0.25 : 2) * last);     // down to a few 1 / 1000 by the middle, then it stays
        last = high / all;
    }
    CHECK(last < 5e-3);
    // ... and the make-up gain follows what the filter takes: a lot at the
    // bottom of a bright crash, below 1 where the resonance adds to a cowbell
    CHECK(params(0, KNOB_MAX, KNOB_MAX).filterGain > 8 * 256 && params(0, KNOB_MAX, KNOB_MAX).filterGain <= FILTER_GAIN_MAX);
    int32_t least = FILTER_GAIN_MAX;
    for (uint16_t f = FILTER_DEAD + 1; f <= KNOB_MAX; f += 5) {
        least = params(KNOB_MAX, 0, f).filterGain < least ? params(KNOB_MAX, 0, f).filterGain : least;
    }
    CHECK(least < 128);
    // Stable with headroom at every setting: the loudest input (a full-scale
    // square at the corner) and the voice itself
    int32_t worst = 0;
    for (uint16_t f = FILTER_DEAD + 1; f <= KNOB_MAX; f += 7) {
        Voice v;
        v.p = params(2048, 2048, f);
        const uint32_t half = (uint32_t)(SAMPLE_RATE_HZ / filterHz(v.p) / 2) + 1;
        for (uint32_t n = 0; n < 4000; n++) {
            v.filter((n / half) & 1 ? MIX_MAX : -MIX_MAX);
            worst = abs(v.s1) > worst ? abs(v.s1) : worst;
            worst = abs(v.s2) > worst ? abs(v.s2) : worst;
        }
    }
    CHECK(worst < (1 << 28));
    for (uint16_t f : {(uint16_t)500, (uint16_t)2000, KNOB_MAX}) {
        for (uint16_t m : {(uint16_t)0, (uint16_t)2048, KNOB_MAX}) {
            Voice v;
            v.p = params(m, KNOB_MAX, f);
            v.trigger(127);
            worst = 0;
            while (v.active) {
                v.render();
                worst = abs(v.s1) > worst ? abs(v.s1) : worst;
                worst = abs(v.s2) > worst ? abs(v.s2) : worst;
            }
            CHECK(worst < (1 << 24));
        }
    }
}

static void testCv() {
    // 0 V (and the tolerance band around it) leaves the FILTER knob alone
    for (uint16_t k : {(uint16_t)0, (uint16_t)1234, KNOB_MAX}) {
        CHECK(applyCv(k, CV_ZERO) == k);
        CHECK(applyCv(k, CV_ZERO + CV_DEAD) == k && applyCv(k, CV_ZERO - CV_DEAD) == k);
    }
    // 342.9 ADC codes per volt: +5 V from the bottom = the top, -5 V back down
    auto code = [](double volts) { return (uint16_t)lrint(CV_ZERO + 342.9 * volts); };
    CHECK(applyCv(0, code(5.0)) >= KNOB_MAX - 8);
    CHECK(applyCv(KNOB_MAX, code(-5.0)) <= 8);
    CHECK(abs((int)applyCv(2048, code(2.5)) - KNOB_MAX) < 80);
    CHECK(abs((int)applyCv(2048, code(1.0)) - (2048 + 819)) < 80);
    CHECK(abs((int)applyCv(2048, code(-1.0)) - (2048 - 819)) < 80);
    // Clamped at the ends, the whole ADC range
    CHECK(applyCv(3000, 4095) == KNOB_MAX && applyCv(1000, 0) == 0);
    // No jump at the dead band, never backwards
    for (uint16_t c = 1; c <= 4095; c++) {
        const int a = applyCv(2048, c - 1), b = applyCv(2048, c);
        CHECK(b >= a && b - a <= 3);
    }
    // The fast CV filter settles in a few scans, the knob one is slower
    KnobFilter fast, slow;
    fast.rate = 2;
    fast.update(0);
    slow.update(0);
    uint16_t f = 0, sl = 0;
    for (int i = 0; i < 12; i++) { f = fast.update(4000); sl = slow.update(4000); }
    CHECK(f > 3800 && sl < 2400);
    for (int i = 0; i < 200; i++) f = fast.update(4000);
    CHECK(f >= 3999);
    // set() jumps (the first read after the scan was off), then it glides again
    CHECK(slow.set(1000) == 1000);
    sl = slow.update(3000);
    CHECK(sl > 1000 && sl < 1300);
}

static void testRecorder() {
    static MotionRecorder r;
    uint16_t live[3] = {100, 200, 300}, out[3] = {9, 9, 9};
    CHECK(!r.onClock(live, out) && out[0] == 9);             // LIVE: nothing
    r.press();
    CHECK(r.state == MotionRecorder::RECORDING);
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) {
        live[0] = t; live[1] = 1000 + t; live[2] = 4000;
        CHECK(r.onClock(live, out) && out[0] == t && out[2] == 4000);   // hears the knobs
    }
    CHECK(r.state == MotionRecorder::PLAYBACK && r.tick == 0);
    // First pass: knobs ignored, whatever they do
    live[0] = 3000; live[1] = 0; live[2] = 2000;
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) {
        CHECK(r.onClock(live, out) && out[0] == t && out[1] == 1000 + t && out[2] == 4000);
    }
    // Then a knob move shifts its lane, clamped to the knob range
    live[0] = 3010; live[1] = 0; live[2] = 2500;
    CHECK(r.onClock(live, out) && out[0] == 10 && out[1] == 1000 && out[2] == KNOB_MAX);
    live[0] = 2000;
    CHECK(r.onClock(live, out) && out[0] == 0 && out[1] == 1001);
    r.onStart();
    CHECK(r.tick == 0);
    r.press();                                               // a click: LIVE on the release
    CHECK(r.state == MotionRecorder::PLAYBACK);
    r.release();
    CHECK(r.state == MotionRecorder::LIVE && !r.onClock(live, out));
    // A press while recording discards the take
    r.press();
    r.onClock(live, out);
    r.press();
    CHECK(r.state == MotionRecorder::LIVE);
    r.onStart();                                             // no effect in LIVE
    CHECK(!r.onClock(live, out));
}

static void testOverdub() {
    static MotionRecorder r;
    uint16_t live[3] = {1000, 2000, 3000}, out[3];
    r.press();
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) r.onClock(live, out);
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) r.onClock(live, out);   // guard pass
    // Hold: nothing moved yet, a wobble inside the threshold doesn't count
    r.press();
    live[1] = 2000 + MotionRecorder::OVERDUB_THRESHOLD;
    r.onClock(live, out);                                    // tick 0, snapshot
    r.onClock(live, out);                                    // tick 1
    CHECK(!r.overdubbing() && out[1] == 2000 + MotionRecorder::OVERDUB_THRESHOLD);
    // P2 moves: ticks 10..109 overdubbed with 500, P1 / P3 keep playing
    for (uint16_t t = 2; t < 10; t++) r.onClock(live, out);
    live[1] = 500;
    for (uint16_t t = 10; t < 110; t++) {
        r.onClock(live, out);
        CHECK(out[0] == 1000 && out[1] == 500 && out[2] == 3000);
    }
    CHECK(r.overdubbing());
    r.release();
    CHECK(r.state == MotionRecorder::PLAYBACK && !r.overdubbing());
    // Release at 500 = the new reference: the loop plays the new curve exactly
    for (uint16_t t = 110; t < MotionRecorder::LOOP_TICKS; t++) {
        r.onClock(live, out);
        CHECK(out[1] == 2000);
    }
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) {
        r.onClock(live, out);
        CHECK(out[0] == 1000 && out[1] == (t >= 10 && t < 110 ? 500 : 2000) && out[2] == 3000);
    }
    // The overdubbed lane still takes the offset afterwards
    live[1] = 600;
    for (uint16_t t = 0; t < 20; t++) r.onClock(live, out);
    CHECK(out[1] == 600);                                    // tick 19: 500 + 100
    r.press();
    r.release();
    CHECK(r.state == MotionRecorder::LIVE);
}

static void testMidi() {
    MidiParser m;
    auto feed = [&](std::initializer_list<uint8_t> bytes) {
        MidiParser::Event last = {MidiParser::NONE, 0, 0};
        for (uint8_t b : bytes) last = m.feed(b);
        return last;
    };
    MidiParser::Event e = feed({0x99, 38, 100});
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 38 && e.data2 == 100);
    e = feed({40, 64});                                      // running status
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 40 && e.data2 == 64);
    e = feed({40, 0});                                       // velocity 0 = note-off
    CHECK(e.kind == MidiParser::NOTE_OFF);
    CHECK(m.feed(0x90).kind == MidiParser::NONE);
    CHECK(m.feed(60).kind == MidiParser::NONE);
    CHECK(m.feed(0xF8).kind == MidiParser::CLOCK);           // clock inside a message
    e = m.feed(127);
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 60 && e.data2 == 127);
    CHECK(m.feed(0xFA).kind == MidiParser::START);
    CHECK(feed({0x80, 60, 0}).kind == MidiParser::NOTE_OFF);
    CHECK(feed({0xF0, 1, 2, 3, 0xF7, 5, 6}).kind == MidiParser::NONE);   // SysEx cancels running status
}

static void writeWav(const std::string &path, const std::vector<int16_t> &pcm) {
    FILE *f = std::fopen(path.c_str(), "wb");
    if (!f) { std::printf("cannot write %s\n", path.c_str()); failures++; return; }
    const uint32_t bytes = (uint32_t)pcm.size() * 2, rate = SAMPLE_RATE_HZ;
    auto u32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, f); };
    auto u16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, f); };
    std::fwrite("RIFF", 1, 4, f); u32(36 + bytes); std::fwrite("WAVEfmt ", 1, 8, f);
    u32(16); u16(1); u16(1); u32(rate); u32(rate * 2); u16(2); u16(16);
    std::fwrite("data", 1, 4, f); u32(bytes);
    std::fwrite(pcm.data(), 2, pcm.size(), f);
    std::fclose(f);
}

// What the DAC plays (12-bit codes around mid-scale, scaled to 16 bit).
static void append(std::vector<int16_t> &pcm, Voice &v, uint32_t samples, uint32_t gate = UINT32_MAX) {
    for (uint32_t i = 0; i < samples; i++) {
        if (i == gate) v.release();
        const int32_t code = (int32_t)toDac(v.render()) - DAC_MID;
        pcm.push_back((int16_t)(code * 32767 / DAC_SWING));
    }
}

static void writePreviews(const std::string &dir) {
    // Four hits each (the third softer). The crash is held for two bars, so
    // it rings out; `-short` = notes of an eighth, which cut it.
    struct Preset { const char *name; uint16_t morph, tone, filter; uint32_t beats, gateEighths; };
    const Preset presets[] = {
        {"crash", 0, 0, 0, 4, 8},                       {"crash-short", 0, 0, 0, 2, 1},
        {"crash-tone-mid", 0, 2048, 0, 4, 8},           {"crash-tone-full", 0, KNOB_MAX, 0, 4, 8},
        {"crash-filter", 0, 0, 2300, 4, 8},             {"crash-filter-closed", 0, 0, 3600, 4, 8},
        {"cowbell", KNOB_MAX, 0, 0, 1, 2},              {"cowbell-short", KNOB_MAX, 0, 0, 1, 1},
        {"cowbell-tone-mid", KNOB_MAX, 2048, 0, 1, 2},  {"cowbell-tone-full", KNOB_MAX, KNOB_MAX, 0, 1, 2},
        {"cowbell-filter", KNOB_MAX, 0, 2700, 1, 2},    {"crash-cowbell", 2048, 0, 0, 4, 8},
    };
    const uint32_t beat = SAMPLE_RATE_HZ * 60 / 126;     // 126 BPM
    for (const Preset &p : presets) {
        Voice v;
        v.p = params(p.morph, p.tone, p.filter);
        std::vector<int16_t> pcm;
        for (uint8_t vel : {(uint8_t)127, (uint8_t)127, (uint8_t)90, (uint8_t)127}) {
            v.trigger(vel);
            append(pcm, v, p.beats * beat, p.gateEighths * beat / 2);
        }
        writeWav(dir + "/" + p.name + ".wav", pcm);
    }
    // Sweeps, a hit per beat: MORPH (TONE and FILTER fully left), then TONE
    // on the crash, on the cowbell and on both layered ...
    std::vector<int16_t> pcm;
    Voice v;
    for (int step = 0; step <= 16; step++) {
        v.p = params((uint16_t)(step * KNOB_MAX / 16), 0, 0);
        v.trigger(127);
        append(pcm, v, beat);
    }
    writeWav(dir + "/sweep-morph.wav", pcm);
    for (uint16_t morph : {(uint16_t)0, KNOB_MAX, (uint16_t)2048}) {
        pcm.clear();
        for (int step = 0; step <= 16; step++) {
            v.p = params(morph, (uint16_t)(step * KNOB_MAX / 16), 0);
            v.trigger(127);
            append(pcm, v, beat);
        }
        writeWav(dir + (morph == 0 ? "/sweep-tone-crash.wav" : morph == 2048 ? "/sweep-tone-both.wav" : "/sweep-tone-cowbell.wav"), pcm);
    }
    // ... and FILTER on the crash and on the cowbell
    for (uint16_t morph : {(uint16_t)0, KNOB_MAX}) {
        pcm.clear();
        for (int step = 0; step <= 24; step++) {
            v.p = params(morph, 0, (uint16_t)(step * KNOB_MAX / 24));
            v.trigger(127);
            append(pcm, v, beat);
        }
        writeWav(dir + (morph ? "/sweep-filter-cowbell.wav" : "/sweep-filter-crash.wav"), pcm);
    }
    // Next to ../clapsnare (knobs at noon), to compare the levels: clap,
    // crash, snare, cowbell, twice
    static clapsnare::Tables tables;
    tables.fill();
    clapsnare::Voice other;
    pcm.clear();
    for (int step = 0; step < 8; step++) {
        const bool cowbell = (step & 3) == 3;
        if (step & 1) {
            v.p = params(cowbell ? KNOB_MAX : 0, 0, 0);
            v.trigger(127);
            append(pcm, v, 2 * beat);
        } else {
            other.p = clapsnare::makeParams(tables, (step & 3) ? clapsnare::KNOB_MAX : 0, 2048, 2048);
            other.trigger(127);
            for (uint32_t i = 0; i < 2 * beat; i++) {
                const int32_t code = (int32_t)clapsnare::toDac(other.render(tables.sine)) - clapsnare::DAC_MID;
                pcm.push_back((int16_t)(code * 32767 / clapsnare::DAC_SWING));
            }
        }
    }
    writeWav(dir + "/level-vs-clapsnare.wav", pcm);
    std::printf("preview WAVs in %s\n", dir.c_str());
}

int main(int argc, char **argv) {
    T.fill();
    testParams();
    testClassic();
    testEnvelope();
    testLevels();
    testLoudness();
    testMorph();
    testTone();
    testCrashHeadroom();
    testBandLimit();
    testFilter();
    testCv();
    testRecorder();
    testOverdub();
    testMidi();
    if (argc > 1) writePreviews(argv[1]);
    std::printf(failures ? "%d failure(s)\n" : "all tests passed\n", failures);
    return failures ? 1 : 0;
}
