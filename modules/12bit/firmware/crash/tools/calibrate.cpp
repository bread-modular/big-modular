// Measures the level tables of the 12bit crash voice and writes them as
// src/crash_levels.h (run by ../test.sh cal, after a change to the sound, or
// to the level of ../clapsnare):
//   1. the drive into the soft clipper that makes the classic crash (TONE
//      fully left, at LEVEL_RMS in the mix) sound as loud as the clapsnare
//      clap with TONE and DECAY at noon, by the loudness model (loudness.h);
//   2. each engine alone at every TONE node: the gain that brings a hit to
//      the level of that crash (the cowbell BELL_LIFT_Q8 above it);
//   3. what the FILTER lets through of each engine at every TONE x FILTER
//      node: the make-up gain that keeps a hit at the level it has where the
//      filter comes in (no step in level at the bypass);
//   4. the cowbell / crash energy of a hit at equal MORPH gains.
// The level of a hit in 2 .. 4: the RMS below 12 kHz (AudibleBand) of its
// first 100 ms after the soft clipper, at full velocity. The hiss above
// 12 kHz adds to the RMS, not to what is heard.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <vector>
#include "clapsnare_logic.h"
#include "crash_logic.h"
#include "loudness.h"

using namespace crash;

static Tables T;
static Levels L;
static const loudness::Model EAR;

static const uint32_t SEEDS = 8;
static const uint32_t WINDOW = SAMPLE_RATE_HZ / 10;

// 4-pole Butterworth low-pass at 12 kHz.
struct AudibleBand {
    double z[2][2] = {{0, 0}, {0, 0}};
    double run(double x) {
        static const double Q[2] = {0.54119610, 1.30656296};
        const double w = 6.283185307 * 12000.0 / SAMPLE_RATE_HZ;
        for (int i = 0; i < 2; i++) {
            const double alpha = sin(w) / (2 * Q[i]), a0 = 1 + alpha;
            const double b1 = (1 - cos(w)) / a0, a1 = -2 * cos(w) / a0, a2 = (1 - alpha) / a0;
            const double y = b1 / 2 * x + z[i][0];   // transposed direct form II
            z[i][0] = b1 * x - a1 * y + z[i][1];
            z[i][1] = b1 / 2 * x - a2 * y;
            x = y;
        }
        return x;
    }
};

static Pos node(uint32_t i, uint32_t points) {
    return i < points - 1 ? Pos{i, 0} : Pos{points - 2, 256};
}

static uint16_t toneKnob(uint32_t i) { return (uint16_t)lrintf(toneAt(i) * KNOB_MAX); }

// The first 100 ms of one engine at gain 1, before the FILTER: a hit per
// seed (the cowbell has no random part: one).
typedef std::vector<std::vector<int32_t>> Hits;

static Hits engineHits(uint32_t ti, bool bell) {
    Levels unity;
    for (uint32_t i = 0; i < TONE_PTS; i++) unity.crashNorm[i] = unity.bellNorm[i] = 256;
    Hits hits(bell ? 1 : SEEDS);
    for (uint32_t seed = 0; seed < hits.size(); seed++) {
        Voice v;
        v.noise = (seed + 1) * 0x9E3779B9u;
        v.p = paramsAt(T, unity, bell ? 0 : 32768, bell ? 32768 : 0, toneKnob(ti), node(ti, TONE_PTS), false, Pos{0, 0});
        v.trigger(127);
        for (uint32_t n = 0; n < WINDOW; n++) hits[seed].push_back(v.active ? v.mixSample() : 0);
    }
    return hits;
}

// The level of the hits at an engine gain (Q8), as the voice computes it:
// through the FILTER with its make-up gain if `filter` is given, then with
// the drive into the soft clipper (clip = false: the level in the mix).
static double level(const Hits &hits, int32_t gainQ8, const Params *filter = nullptr, bool clip = true) {
    double sum = 0;
    for (const std::vector<int32_t> &hit : hits) {
        Voice v;
        if (filter) v.p = *filter;
        AudibleBand band;
        for (int32_t raw : hit) {
            int32_t mix = (raw * gainQ8) >> 8;
            mix = mix > MIX_MAX ? MIX_MAX : (mix < -MIX_MAX ? -MIX_MAX : mix);
            if (filter) mix = v.filterMakeUp(mix);
            const double y = band.run(clip ? softClip((mix * L.drive) >> 8) : mix);
            sum += y * y;
        }
    }
    return sqrt(sum / (double)(hits.size() * WINDOW));
}

// The engine gain (Q8) that brings the hits to `target`.
static int32_t gainFor(const Hits &hits, double target) {
    int32_t lo = 1, hi = 65535;
    while (hi - lo > 1) {
        const int32_t mid = (lo + hi) / 2;
        (level(hits, mid) < target ? lo : hi) = mid;
    }
    return target - level(hits, lo) < level(hits, hi) - target ? lo : hi;
}

// How loud hits are at the DAC (300 ms of each, a hit per seed), phon.
template <typename Hit>
static double loudnessOf(Hit hit) {
    double sum = 0;
    for (uint32_t seed = 1; seed <= SEEDS; seed++) sum += EAR.phon(hit(seed * 0x9E3779B9u));
    return sum / SEEDS;
}

// The clapsnare clap: MORPH fully left, TONE and DECAY at noon, full velocity.
static std::vector<double> clapHit(uint32_t seed) {
    static clapsnare::Tables tables;
    static bool filled = false;
    if (!filled) {
        tables.fill();
        filled = true;
    }
    clapsnare::Voice v;
    v.noise = seed;
    v.p = clapsnare::makeParams(tables, 0, 2048, 2048);
    for (uint32_t n = 0; n < 100; n++) v.render(tables.sine);   // its noise runs freely
    v.trigger(127);
    std::vector<double> out;
    for (uint32_t n = 0; n < 3 * WINDOW; n++) out.push_back(v.render(tables.sine) / 32768.0);
    return out;
}

// One engine of this voice at a TONE node with the tables so far, FILTER off.
static std::vector<double> voiceHit(uint32_t ti, bool bell, uint32_t seed) {
    Voice v;
    v.noise = seed;
    v.p = paramsAt(T, L, bell ? 0 : 32768, bell ? 32768 : 0, toneKnob(ti), node(ti, TONE_PTS), false, Pos{0, 0});
    v.trigger(127);
    std::vector<double> out;
    for (uint32_t n = 0; n < 3 * WINDOW; n++) out.push_back(v.render() / 32768.0);
    return out;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::printf("usage: calibrate <crash_levels.h>\n");
        return 1;
    }
    T.fill();

    Hits crashHits[TONE_PTS], bellHits[TONE_PTS];
    for (uint32_t i = 0; i < TONE_PTS; i++) {
        crashHits[i] = engineHits(i, false);
        bellHits[i] = engineHits(i, true);
    }

    // 1. the drive: the classic crash, at LEVEL_RMS in the mix, as loud as
    // the clap
    const double clapPhon = loudnessOf(clapHit);
    L.crashNorm[0] = L.crashNorm[1] = (uint16_t)lrint(256.0 * LEVEL_RMS / level(crashHits[0], 256, nullptr, false));
    auto crashPhon = [&](int32_t drive) {
        L.drive = (uint16_t)drive;
        return loudnessOf([](uint32_t seed) { return voiceHit(0, false, seed); });
    };
    int32_t driveLo = 64, driveHi = DRIVE_MAX;
    if (crashPhon(driveHi) < clapPhon) {
        std::printf("the crash does not get as loud as the clap (%.1f of %.1f phon)\n", crashPhon(driveHi), clapPhon);
        return 1;
    }
    while (driveHi - driveLo > 1) {
        const int32_t mid = (driveLo + driveHi) / 2;
        (crashPhon(mid) < clapPhon ? driveLo : driveHi) = mid;
    }
    L.drive = (uint16_t)driveHi;

    // 2. engine levels over TONE. The target: that crash after the clipper,
    // the cowbell BELL_LIFT_Q8 above it.
    const double target = level(crashHits[0], L.crashNorm[0]);
    for (uint32_t i = 0; i < TONE_PTS; i++) {
        const int32_t crash = gainFor(crashHits[i], target), bell = gainFor(bellHits[i], target * BELL_LIFT_Q8 / 256.0);
        if (crash >= 65535 || bell >= 65535) {
            std::printf("norm out of range at tone node %u\n", i);
            return 1;
        }
        L.crashNorm[i] = (uint16_t)crash;
        L.bellNorm[i] = (uint16_t)bell;
    }

    // 3. the FILTER over TONE x FILTER: the table entry whose make-up gain
    // comes closest to the level where the filter comes in
    int clamped = 0, loud = 0;
    for (uint32_t i = 0; i < TONE_PTS; i++) {
        for (int bell = 0; bell < 2; bell++) {
            const Hits &hits = bell ? bellHits[i] : crashHits[i];
            const int32_t norm = bell ? L.bellNorm[i] : L.crashNorm[i];
            int8_t *row = bell ? L.bellPass[i] : L.crashPass[i];
            double first = 0;
            for (uint32_t j = 0; j < FILT_PTS; j++) {
                Params p = paramsAt(T, L, 32768, 0, toneKnob(i), node(i, TONE_PTS), true, node(j, FILT_PTS));
                auto at = [&](int32_t steps) {
                    p.filterGain = makeUpGain(passPowerAt(T, steps * 256));
                    return level(hits, norm, &p);
                };
                if (j == 0) {
                    row[0] = 0;
                    first = at(0);
                    continue;
                }
                int32_t lo = PASS_MIN, hi = PASS_MAX;   // more pass = less gain = quieter
                while (hi - lo > 1) {
                    const int32_t mid = (lo + hi) / 2;
                    (at(mid) > first ? lo : hi) = mid;
                }
                row[j] = (int8_t)(at(lo) - first < first - at(hi) ? lo : hi);
                if (row[j] == PASS_MIN && at(PASS_MIN) < 0.94 * first) clamped++;   // more than 0.5 dB short
                if (row[j] == PASS_MAX && at(PASS_MAX) > 1.06 * first) loud++;      // ... or over
            }
        }
    }

    // 4. cowbell / crash energy of a hit before the clipper
    const uint32_t mid = TONE_PTS / 2;
    const double crashE = level(crashHits[mid], L.crashNorm[mid], nullptr, false);
    const double bellE = level(bellHits[mid], L.bellNorm[mid], nullptr, false);
    const long weight = lrint(256.0 * bellE * bellE / (crashE * crashE));
    L.bellWeight = (uint16_t)(weight < 1 ? 1 : (weight > 65535 ? 65535 : weight));

    FILE *f = std::fopen(argv[1], "w");
    if (!f) {
        std::printf("cannot write %s\n", argv[1]);
        return 1;
    }
    std::fprintf(f, "// Level tables of the 12bit crash voice: generated by tools/calibrate.cpp\n"
                    "// (../test.sh cal), do not edit. See struct Levels in crash_logic.h.\n"
                    "#pragma once\n\nnamespace crash {\n\nstatic const Levels LEVELS = {\n");
    std::fprintf(f, "    // drive: x%.2f, the classic crash at %.1f phon (clapsnare clap, knobs at noon: %.1f phon)\n    %u,\n",
                 L.drive / 256.0, crashPhon(L.drive), clapPhon, L.drive);
    auto row16 = [&](const char *name, const uint16_t *tab) {
        std::fprintf(f, "    // %s\n    {", name);
        for (uint32_t i = 0; i < TONE_PTS; i++) std::fprintf(f, "%u%s", tab[i], i + 1 < TONE_PTS ? ", " : "},\n");
    };
    row16("crashNorm", L.crashNorm);
    row16("bellNorm", L.bellNorm);
    std::fprintf(f, "    // bellWeight\n    %u,\n", L.bellWeight);
    auto pass = [&](const char *name, const int8_t tab[][FILT_PTS]) {
        std::fprintf(f, "    // %s\n    {\n", name);
        for (uint32_t i = 0; i < TONE_PTS; i++) {
            std::fprintf(f, "        {");
            for (uint32_t j = 0; j < FILT_PTS; j++) std::fprintf(f, "%d%s", tab[i][j], j + 1 < FILT_PTS ? "," : "},\n");
        }
        std::fprintf(f, "    },\n");
    };
    pass("crashPass", L.crashPass);
    pass("bellPass", L.bellPass);
    std::fprintf(f, "};\n\n}  // namespace crash\n");
    std::fclose(f);

    int lo[2] = {127, 127}, hi[2] = {-128, -128};
    for (uint32_t i = 0; i < TONE_PTS; i++) {
        for (uint32_t j = 0; j < FILT_PTS; j++) {
            const int8_t q[2] = {L.crashPass[i][j], L.bellPass[i][j]};
            for (int e = 0; e < 2; e++) {
                lo[e] = q[e] < lo[e] ? q[e] : lo[e];
                hi[e] = q[e] > hi[e] ? q[e] : hi[e];
            }
        }
    }
    std::printf("clapsnare clap %.1f phon; drive %u (x%.2f): crash %.1f .. %.1f phon, cowbell %.1f .. %.1f phon over TONE\n", clapPhon,
                L.drive, L.drive / 256.0, loudnessOf([](uint32_t seed) { return voiceHit(0, false, seed); }),
                loudnessOf([](uint32_t seed) { return voiceHit(TONE_PTS - 1, false, seed); }),
                loudnessOf([](uint32_t seed) { return voiceHit(0, true, seed); }),
                loudnessOf([](uint32_t seed) { return voiceHit(TONE_PTS - 1, true, seed); }));
    std::printf("target %.1f dB re full scale; crashNorm %u .. %u, bellNorm %u .. %u, bellWeight %u\n",
                20 * log10(target / 32768.0), L.crashNorm[0], L.crashNorm[TONE_PTS - 1], L.bellNorm[0],
                L.bellNorm[TONE_PTS - 1], L.bellWeight);
    std::printf("pass: crash %.1f .. %.1f dB, cowbell %.1f .. %.1f dB (table %.0f .. %.0f dB), %d node(s) short of gain, %d too loud\n",
                lo[0] / 2.0, hi[0] / 2.0, lo[1] / 2.0, hi[1] / 2.0, PASS_MIN / 2.0, PASS_MAX / 2.0, clamped, loud);
    std::printf("wrote %s\n", argv[1]);
    return 0;
}
