// ============================================================================
// 12bit crash: synthesized crash cymbal + cowbell, behaviour only (no hardware
// access, so test/test_logic.cpp runs it on the host).
//
// Two engines, no samples, both at their classic sound with TONE fully left:
//   CRASH    the TR-808 cymbal structure with the wash and the length of a
//            TR-909 crash: the six square oscillators of the 808 (205 ..
//            800 Hz) + noise, high-passed (no fundamentals, only the
//            shimmer), then two band-passes: 3.6 kHz with the long ring and
//            7.1 kHz, brighter at the start.
//   COWBELL  the TR-808 cowbell: two band-limited pulses 540 + 800 Hz through
//            a band-pass at 900 Hz (the 800 Hz tone leads), a hard strike
//            and a quieter tail.
// Both were set against recordings of the machines (spectrum, how tonal,
// decay), not by ear.
//
//   P1 MORPH   crash -> crash + cowbell layered -> cowbell (equal power)
//   P2 TONE    the colour, fully left = the classic sounds, then both are
//              tuned up: the crash by a fifth (oscillators and filters
//              together: a smaller, brighter cymbal), the cowbell by an
//              octave, to 1080 + 1600 Hz
//   P3 FILTER  resonant low-pass on the whole voice: fully left = no filter
//              at all (bypassed), then the corner falls from 16 kHz to 400 Hz
//              while the resonance comes in (Q 0.7 -> 4 over the first 30 %)
//   CV         added to FILTER: 5 V = the whole knob travel, bipolar
//
// Every setting plays at the same level: both engines are brought to one
// level over TONE and the FILTER output is made up for what it took away
// (tables in crash_levels.h, measured by tools/calibrate.cpp). That level is
// the one of ../clapsnare: the sum is driven into the soft clipper (the
// `drive` of the tables) until the classic crash sounds as loud as the clap
// with its knobs at noon, by a loudness model (tools/loudness.h): the ear is
// less sensitive where a crash sits, so on a meter it reads 3 dB more.
//
// Note-on fires the voice (velocity = level, the clapsnare curve), note-off
// switches its ring to the fast release (23 ms), so the gate length is the
// length of the sound.
//
// Integer maths in render() and makeParams() (Cortex-M0+: no FPU, no 64-bit
// multiply); floats only fill the tables at boot.
// ============================================================================
#pragma once

#include <math.h>
#include <stdint.h>

namespace crash {

static const uint32_t SAMPLE_RATE_HZ = 48000;   // TIM6 tick (64 MHz / 1333 = 48.012 kHz)
static const uint16_t KNOB_MAX = 4095;          // 12-bit ADC

// DAC: mid-scale = 0 V at the jack (VOFF), +-DAC_SWING codes = +-4.7 V after
// the x3.4 stage, inside the buffered DAC range (0.2 .. 3.1 V).
static const int32_t DAC_MID = 2048;
static const int32_t DAC_SWING = 1700;

// ---- tuning constants --------------------------------------------------------

// Envelopes are Q24 (ENV_FULL = 1.0); a decay constant k is the fraction lost
// per sample in Q24: k = 2^24 / (tau x 48000). Each step also takes a small
// fixed amount (as the 8bit's "+ 1"), which ends the sound: 0.1 of full scale
// per second.
static const uint32_t ENV_FULL = 1u << 24;
constexpr uint32_t decayK(float tauMs) { return (uint32_t)(16777216.0f / (tauMs * 48.0f)); }
static const uint32_t ENV_LINEAR = 35;
static const uint32_t RELEASE_K = decayK(23.3f);   // after note-off: the 8bit release (env >> 9 at 22 kHz)
static const uint32_t ENV_END = ENV_FULL >> 8;     // 8bit: env < 0x100 of 0xFFFF

// P1 MORPH: a little dead travel at both ends, so the ends are the pure sounds.
static const uint16_t MORPH_DEAD = 120;

// Level of the classic crash in the mix, before the FILTER and the drive: RMS
// below 12 kHz of its first 100 ms, Q15. The drive (Levels) then takes it
// into the soft clipper; every other setting is brought to its level after
// the clipper.
static const int32_t LEVEL_RMS = 4800;
// ... but the cowbell this much above it (Q8, x1.19 = +1.5 dB on a meter): a
// short tonal hit sounds quieter than a noisy one at the same reading (to
// match the clap by the loudness model it would take 3.2 dB, which turns its
// strike into a tone burst: full level for 80 ms).
static const int32_t BELL_LIFT_Q8 = 304;
static const int32_t MIX_MAX = 65535;           // into the FILTER (bounds its states)
static const int32_t FILTER_OUT_MAX = 131071;   // out of it, before the make-up gain

// Crash. The oscillator bank of the TR-808 (its cymbal and hi-hats); 540 and
// 800 Hz are the cowbell pair.
static const uint8_t PARTIALS = 6;
static const float METAL_HZ[PARTIALS] = {205.3f, 304.4f, 369.6f, 522.7f, 540.0f, 800.0f};
static const int32_t METAL_GAIN = 640;          // per square: sum +-3840
// The wash under the metal: noise (+-4096) through a one-pole low-pass, so
// it falls towards the top as the harmonics of the squares do.
static const float CRASH_NOISE_LP_HZ = 3000.0f;
static const int32_t CRASH_NOISE_Q8 = 72;
static const float CRASH_HP_HZ = 2000.0f;       // two one-poles: takes the fundamentals out
static const float CRASH_LOW_HZ = 3600.0f;      // low band (TR-808: 3.44 kHz)
static const float CRASH_HIGH_HZ = 7100.0f;     // high band (TR-808: 7.1 kHz)
static const int32_t CRASH_LOW_DAMP_Q13 = 8192; // 1 / Q, Q = 1
static const int32_t CRASH_HIGH_DAMP_Q13 = 5461;   // Q = 1.5
static const float CRASH_OCT = 0.585f;          // TONE: all of it tuned up, x1 .. x1.5
// The ring, gate held: over at 1.5 s. The high band has a second, shorter
// envelope on top of it, bright at the start and darker in the tail (TR-808),
// so the whole is -10 dB after 0.35 s and -20 dB after 0.8 s (808 long decay:
// 0.17 / 0.57 s, 909: 0.5 / 0.95 s).
static const uint32_t CRASH_RING_K = decayK(500.0f);
static const uint32_t CRASH_SIZZLE_K = decayK(150.0f);
static const int32_t CRASH_LOW_Q8 = 256;        // low band x the ring
static const int32_t CRASH_HIGH_Q8 = 112;       // high band x the ring
static const int32_t CRASH_SIZZLE_Q8 = 320;     // high band x the sizzle
// A little of the source from between the two high-passes, under the bands:
// the low end of a real cymbal, and what a closed FILTER still finds.
static const int32_t CRASH_BODY_Q8 = 48;

// Cowbell (TR-808, two recordings measured: the 800 Hz tone leads, the 540 Hz
// one and its octave are 12 dB below it, the rest falls away; a strike of
// about 10 ms on a tail of 110 ms that starts 12 dB down).
static const float BELL_HZ = 540.0f;            // first tone, TONE fully left
static const float BELL_OCT = 1.0f;             // TONE: up to 1080 + 1600 Hz
static const uint32_t BELL_RATIO_Q12 = 6068;    // second tone x1.4815 (800 / 540)
static const uint32_t BELL_WIDTH[2] = {1546188227u, 1889785610u};   // pulse widths 0.36 and 0.44 of the period
static const int32_t BELL_FIRST_Q8 = 179;       // the first tone x0.7
static const float BELL_BAND_RATIO = 900.0f / 540.0f;    // band-pass centre / first tone
static const int32_t BELL_DAMP_Q15 = 16384;     // 1 / Q, Q = 2
static const int32_t BELL_AMP_BITS = 11;        // each pulse +-2048
static const uint32_t BELL_SNAP_K = decayK(9.0f);    // the strike ...
static const int32_t BELL_SNAP_Q8 = 194;        // ... 76 % of the level
static const uint32_t BELL_TAIL_K = decayK(110.0f);  // gate held

// P3 FILTER: the bottom of the travel is a bypass, so tolerances and the CV
// dead band can't leave a filter in; above it the corner starts where two
// flat poles are close to nothing (-0.2 dB at 10 kHz) and falls.
static const uint16_t FILTER_DEAD = 40;
static const float FILTER_HZ_HI = 16000.0f;
static const float FILTER_HZ_LO = 400.0f;
static const float FILTER_Q_LO = 0.7071f;       // where it comes in: flat
static const float FILTER_Q_HI = 4.0f;          // +12 dB at the corner ...
static const float FILTER_Q_TRAVEL = 0.3f;      // ... from here on (5.3 kHz)
static const int32_t FILTER_GAIN_MAX = 64 << 8; // make-up gain limit, Q8 (+36 dB)

// CV in -> FILTER. The input stage (R4 100k, R5 56k to +3V3, R6 120k to GND)
// maps the jack to 1.628 V + 0.2763 x Vcv at PA0: 342.9 ADC codes per volt.
static const int32_t CV_ZERO = 2021;            // 0 V, and nothing patched (tip normalled to GND)
static const int32_t CV_DEAD = 24;              // +-0.07 V: part tolerances don't move FILTER
static const int32_t CV_FULL = 1714;            // 5 V = the whole knob travel

// ---- tables --------------------------------------------------------------------

static const uint32_t TONE_PTS = 33;            // knob laws over TONE
static const uint32_t FILT_PTS = 65;            // knob laws over FILTER, above the bypass
static const uint32_t FADE_PTS = 33;            // MORPH: a quarter sine
static const uint32_t POW2_SIZE = 256;

// One-pole y += a (x - y) with a corner of hz: a = 1 - exp(-2 pi hz / fs).
inline int32_t onePoleQ15(float hz) {
    const float a = 1.0f - expf(-6.2831853f * hz / (float)SAMPLE_RATE_HZ);
    return a >= 1.0f ? 32767 : (int32_t)(a * 32768.0f);
}

// State-variable filter coefficient for a centre of hz: f = 2 sin(pi fc / fs).
inline float svfF(float hz) { return 2.0f * sinf(3.14159265f * hz / (float)SAMPLE_RATE_HZ); }

// Corner and Q of the FILTER at x = 0 .. 1 of its travel above the bypass.
inline float filterHzAt(float x) { return FILTER_HZ_HI * exp2f(-log2f(FILTER_HZ_HI / FILTER_HZ_LO) * x); }
inline float filterQAt(float x) {
    const float r = x < FILTER_Q_TRAVEL ? x / FILTER_Q_TRAVEL : 1.0f;
    return FILTER_Q_LO * exp2f(log2f(FILTER_Q_HI / FILTER_Q_LO) * r);
}

// Position in a table of `points` entries: index and 8-bit fraction.
struct Pos {
    uint32_t i;
    uint32_t frac;
};

// value 0 .. span -> position (span x points x 256 must fit 32 bit).
inline Pos tablePos(uint32_t value, uint32_t span, uint32_t points) {
    if (value > span) value = span;
    const uint32_t x = value * (points - 1) * 256 / span;
    Pos p = {x >> 8, x & 0xFF};
    if (p.i >= points - 1) {
        p.i = points - 2;
        p.frac = 256;
    }
    return p;
}

template <typename T>
inline int32_t lerp(const T *tab, Pos p) {
    return (int32_t)tab[p.i] + ((((int32_t)tab[p.i + 1] - (int32_t)tab[p.i]) * (int32_t)p.frac) >> 8);
}

inline uint32_t isqrt(uint32_t v) {
    uint32_t r = 0;
    for (uint32_t bit = 1u << 30; bit; bit >>= 2) {
        if (v >= r + bit) {
            v -= r + bit;
            r = (r >> 1) + bit;
        } else {
            r >>= 1;
        }
    }
    return r;
}

inline float toneAt(uint32_t node) { return (float)node / (float)(TONE_PTS - 1); }   // 0 .. 1 of the knob
inline Pos tonePos(uint16_t tone) { return tablePos(tone, KNOB_MAX, TONE_PTS); }

struct Tables {
    uint16_t crashNoiseA[TONE_PTS];  // crash noise low-pass, Q15
    uint16_t crashHpA[TONE_PTS];     // crash high-passes, Q15
    uint16_t crashLowG[TONE_PTS];    // crash low band g = tan(pi fc / fs), Q13
    uint16_t crashHighG[TONE_PTS];   // crash high band g, Q13
    uint16_t bellF[TONE_PTS];        // cowbell band-pass coefficient, Q15
    uint16_t filterG[FILT_PTS];      // FILTER g = tan(pi fc / fs), Q15 (below 2.0: fc < 16.9 kHz)
    uint16_t filterA1[FILT_PTS];     // 1 / (1 + g (g + 1 / Q)), Q15
    uint16_t filterA2[FILT_PTS];     // g x that, Q15
    uint16_t fade[FADE_PTS];         // sin(0 .. 90 deg), Q15
    uint32_t pow2[POW2_SIZE + 1];    // 2^(i / 256), Q16

    void fill() {
        for (uint32_t i = 0; i < TONE_PTS; i++) {
            const float band = exp2f(CRASH_OCT * toneAt(i));
            crashNoiseA[i] = (uint16_t)onePoleQ15(CRASH_NOISE_LP_HZ * band);
            crashHpA[i] = (uint16_t)onePoleQ15(CRASH_HP_HZ * band);
            crashLowG[i] = (uint16_t)lrintf(8192.0f * tanf(3.14159265f * CRASH_LOW_HZ * band / (float)SAMPLE_RATE_HZ));
            crashHighG[i] = (uint16_t)lrintf(8192.0f * tanf(3.14159265f * CRASH_HIGH_HZ * band / (float)SAMPLE_RATE_HZ));
            bellF[i] = (uint16_t)lrintf(32768.0f * svfF(BELL_HZ * BELL_BAND_RATIO * exp2f(BELL_OCT * toneAt(i))));
        }
        for (uint32_t i = 0; i < FILT_PTS; i++) {
            const float x = (float)i / (float)(FILT_PTS - 1);
            const float g = tanf(3.14159265f * filterHzAt(x) / (float)SAMPLE_RATE_HZ);
            const float a1 = 1.0f / (1.0f + g * (g + 1.0f / filterQAt(x)));
            filterG[i] = (uint16_t)lrintf(32768.0f * g);
            filterA1[i] = (uint16_t)lrintf(32768.0f * a1);
            filterA2[i] = (uint16_t)lrintf(32768.0f * g * a1);
        }
        for (uint32_t i = 0; i < FADE_PTS; i++) {
            fade[i] = (uint16_t)lrintf(32768.0f * sinf(1.57079633f * (float)i / (float)(FADE_PTS - 1)));
        }
        for (uint32_t i = 0; i <= POW2_SIZE; i++) {
            pow2[i] = (uint32_t)lrintf(65536.0f * exp2f((float)i / (float)POW2_SIZE));
        }
    }

    // 2^octaves in Q16, octaves in Q16 (0 .. 15.99).
    uint32_t ratio(uint32_t octQ16) const {
        const uint32_t idx = (octQ16 >> 8) & 0xFF;
        const uint32_t frac = octQ16 & 0xFF;
        const uint32_t r = pow2[idx] + (((pow2[idx + 1] - pow2[idx]) * frac) >> 8);
        return r << (octQ16 >> 16);
    }
};

// ---- level tables (crash_levels.h) -------------------------------------------------

// Measured by tools/calibrate.cpp on this voice (`../test.sh cal` rewrites
// crash_levels.h; run it after a change to the sound).
struct Levels {
    // Q8: the gain into the soft clipper at full velocity, which makes the
    // classic crash as loud as the clapsnare clap (TONE and DECAY at noon)
    uint16_t drive;
    uint16_t crashNorm[TONE_PTS];   // Q8: the crash -> the level of the classic crash, over TONE
    uint16_t bellNorm[TONE_PTS];    // Q8: the cowbell -> BELL_LIFT_Q8 above the crash, over TONE
    uint16_t bellWeight;            // Q8: cowbell / crash energy of a hit at equal MORPH gains
    // What the FILTER lets through of each engine, over TONE x FILTER: the
    // power ratio in 0.5 dB (PASS_MIN .. PASS_MAX), 0 where it comes in.
    int8_t crashPass[TONE_PTS][FILT_PTS];
    int8_t bellPass[TONE_PTS][FILT_PTS];
};
static const int32_t PASS_MIN = -72;            // -36 dB
static const int32_t PASS_MAX = 24;             // +12 dB
static const int32_t DRIVE_MAX = 2047;          // Q8: MIX_MAX x velocity gain stays inside 32 bit

}  // namespace crash

#include "crash_levels.h"

namespace crash {

// ---- knobs -> synthesis parameters -----------------------------------------------

// A band-pass of the crash (state-variable, trapezoidal form): Q13.
struct Band {
    int32_t g = 0;             // tan(pi fc / fs)
    int32_t a1 = 0;            // 1 / (1 + g (g + 1 / Q))
    int32_t a2 = 0;            // g x that
    void set(int32_t gQ13, int32_t dampQ13) {
        g = gQ13;
        a1 = (1 << 26) / ((1 << 13) + ((g * (g + dampQ13)) >> 13));
        a2 = (g * a1) >> 13;
    }
};

struct Params {
    // crash
    uint32_t inc[PARTIALS] = {0, 0, 0, 0, 0, 0};   // phase increments per sample
    int32_t crashNoiseA = 0;   // noise low-pass, Q15
    int32_t crashHpA = 0;      // high-passes, Q15
    Band crashLow;             // low band
    Band crashHigh;            // high band
    int32_t crashLevel = 0;    // Q8, to LEVEL_RMS x the MORPH gain
    // cowbell
    uint32_t bellInc[2] = {0, 0};
    uint32_t bellRinc[2] = {0, 0};   // 2^31 / (increment >> 8), for the band-limited edges
    int32_t bellF = 0;         // band-pass coefficient, Q15
    int32_t bellLevel = 0;     // Q8
    // FILTER
    bool filterOn = false;     // P3 above FILTER_DEAD
    uint32_t filterG = 0;      // Q15
    uint32_t filterA1 = 0;     // Q15
    uint32_t filterA2 = 0;     // Q15
    int32_t filterGain = 256;  // make-up, Q8
    int32_t drive = 256;       // into the soft clipper at full velocity, Q8
};

// Phase increment per sample of hz, >> 12 (x a Q16 ratio >> 4 = the increment).
constexpr uint32_t incQ20(float hz) { return (uint32_t)(hz * (1048576.0f / (float)SAMPLE_RATE_HZ)); }
static const uint32_t METAL_INC[PARTIALS] = {incQ20(METAL_HZ[0]), incQ20(METAL_HZ[1]), incQ20(METAL_HZ[2]),
                                             incQ20(METAL_HZ[3]), incQ20(METAL_HZ[4]), incQ20(METAL_HZ[5])};
static const uint32_t BELL_INC = incQ20(BELL_HZ);
static const uint32_t CRASH_OCT_Q16 = (uint32_t)(CRASH_OCT * 65536.0f);
static const uint32_t BELL_OCT_Q16 = (uint32_t)(BELL_OCT * 65536.0f);

// A pass table entry (0.5 dB steps x 256) -> power ratio, Q24.
inline uint32_t passPowerAt(const Tables &t, int32_t stepsQ8) {
    // 0.5 dB = 0.166096 octaves of power; + 12 octaves keeps it positive
    return t.ratio((uint32_t)((stepsQ8 * 10885) / 256 + (12 << 16))) >> 4;
}

// A pass table at a TONE x FILTER position -> power ratio, Q24.
inline uint32_t passPower(const Tables &t, const int8_t tab[][FILT_PTS], Pos tone, Pos filter) {
    const int32_t a = tab[tone.i][filter.i] * 256 + (tab[tone.i][filter.i + 1] - tab[tone.i][filter.i]) * (int32_t)filter.frac;
    const int32_t b = tab[tone.i + 1][filter.i] * 256 +
                      (tab[tone.i + 1][filter.i + 1] - tab[tone.i + 1][filter.i]) * (int32_t)filter.frac;
    return passPowerAt(t, a + (((b - a) * (int32_t)tone.frac) >> 8));
}

// The make-up gain for a pass power ratio (Q24): 1 / sqrt(pass), Q8.
inline int32_t makeUpGain(uint32_t passQ24) {
    const uint32_t root = isqrt(passQ24);             // Q12
    const int32_t gain = (int32_t)((1u << 20) / (root ? root : 1));
    return gain > FILTER_GAIN_MAX ? FILTER_GAIN_MAX : gain;
}

// Parameters at table positions (the calibration measures at the nodes).
// crashFade and bellFade: the MORPH gains, Q15.
inline Params paramsAt(const Tables &t, const Levels &lv, int32_t crashFade, int32_t bellFade, uint16_t tone, Pos tp,
                       bool filterOn, Pos fp) {
    Params p;

    // TONE, crash: the oscillators and every filter go up together
    const uint32_t metal = t.ratio(CRASH_OCT_Q16 * tone / KNOB_MAX) >> 4;
    for (uint8_t i = 0; i < PARTIALS; i++) p.inc[i] = METAL_INC[i] * metal;
    p.crashNoiseA = lerp(t.crashNoiseA, tp);
    p.crashHpA = lerp(t.crashHpA, tp);
    p.crashLow.set(lerp(t.crashLowG, tp), CRASH_LOW_DAMP_Q13);
    p.crashHigh.set(lerp(t.crashHighG, tp), CRASH_HIGH_DAMP_Q13);

    // TONE, cowbell: tuning
    p.bellInc[0] = BELL_INC * (t.ratio(BELL_OCT_Q16 * tone / KNOB_MAX) >> 4);
    p.bellInc[1] = (p.bellInc[0] >> 12) * BELL_RATIO_Q12;
    for (uint8_t i = 0; i < 2; i++) p.bellRinc[i] = 0x80000000u / (p.bellInc[i] >> 8);
    p.bellF = lerp(t.bellF, tp);

    // MORPH + the level tables
    p.crashLevel = (lerp(lv.crashNorm, tp) * crashFade) >> 15;
    p.bellLevel = (lerp(lv.bellNorm, tp) * bellFade) >> 15;
    p.drive = lv.drive;

    // FILTER, and the gain that brings its output back to the level it had
    // going in: the engines' shares of the energy, each through its table.
    p.filterOn = filterOn;
    if (filterOn) {
        p.filterG = (uint32_t)lerp(t.filterG, fp);
        p.filterA1 = (uint32_t)lerp(t.filterA1, fp);
        p.filterA2 = (uint32_t)lerp(t.filterA2, fp);
        const uint32_t wc = (uint32_t)(crashFade * crashFade) >> 22;                      // Q8
        const uint32_t wb = (((uint32_t)(bellFade * bellFade) >> 22) * lv.bellWeight) >> 8;
        const uint32_t share = wc + wb ? wc * 256 / (wc + wb) : 256;                      // the crash's, Q8
        p.filterGain = makeUpGain((passPower(t, lv.crashPass, tp, fp) >> 8) * share +
                                  (passPower(t, lv.bellPass, tp, fp) >> 8) * (256 - share));
    }
    return p;
}

// filter = P3 + CV (applyCv), 0 .. KNOB_MAX.
inline Params makeParams(const Tables &t, uint16_t morph, uint16_t tone, uint16_t filter, const Levels &lv = LEVELS) {
    // MORPH: equal-power fade, so the layered middle is as loud as the ends.
    const uint32_t span = KNOB_MAX - 2 * MORPH_DEAD;
    const uint32_t m = morph <= MORPH_DEAD ? 0 : (uint32_t)(morph - MORPH_DEAD);
    const int32_t bellFade = lerp(t.fade, tablePos(m, span, FADE_PTS));
    const int32_t crashFade = lerp(t.fade, tablePos(m >= span ? 0 : span - m, span, FADE_PTS));

    if (tone > KNOB_MAX) tone = KNOB_MAX;
    const bool filterOn = filter > FILTER_DEAD;
    const Pos fp = tablePos(filterOn ? (uint32_t)(filter - FILTER_DEAD) : 0, KNOB_MAX - FILTER_DEAD, FILT_PTS);
    return paramsAt(t, lv, crashFade, bellFade, tone, tonePos(tone), filterOn, fp);
}

// FILTER knob + CV: the knob sets the centre, the CV moves it both ways
// (+-5 V = +-the whole travel), clamped at the ends of the knob range.
inline uint16_t applyCv(uint16_t knob, uint16_t cvAdc) {
    int32_t d = (int32_t)cvAdc - CV_ZERO;
    if (d > CV_DEAD) d -= CV_DEAD;
    else if (d < -CV_DEAD) d += CV_DEAD;
    else d = 0;
    const int32_t v = (int32_t)knob + d * KNOB_MAX / (CV_FULL - CV_DEAD);
    return (uint16_t)(v < 0 ? 0 : (v > KNOB_MAX ? KNOB_MAX : v));
}

// ---- voice ---------------------------------------------------------------------

// One decay step of a Q24 envelope: exponential plus the 8bit's linear term.
inline uint32_t decayStep(uint32_t env, uint32_t k) {
    const uint32_t dec = (((env >> 12) * k) >> 12) + ENV_LINEAR;
    return env > dec ? env - dec : 0;
}

// 1.5 x - 0.5 x^3 on +-1.0 (Q15), flat beyond: small signals x1.5.
inline int32_t softClip(int32_t x) {
    const bool neg = x < 0;
    if (neg) x = -x;
    if (x > 32767) x = 32767;
    const int32_t x2 = (x * x) >> 15;
    int32_t y = (x * (49152 - (x2 >> 1))) >> 15;
    if (y > 32767) y = 32767;
    return neg ? -y : y;
}

inline uint16_t toDac(int32_t sample) {       // Q15 -> 12-bit DAC code
    return (uint16_t)(DAC_MID + ((sample * DAC_SWING) >> 15));
}

// s x a / 2^15 without a 64-bit product: |s| < 2^29, a <= 65535.
inline int32_t mulQ15(int32_t s, uint32_t a) {
    return (s >> 15) * (int32_t)a + (int32_t)(((uint32_t)(s & 0x7FFF) * a) >> 15);
}

// What a square edge within one sample of now adds or takes (2-sample
// polyBLEP), so the cowbell tones don't alias. d = phase past the point one
// sample before the edge, 0 .. 2 inc.
inline int32_t blepStep(uint32_t d, uint32_t inc, uint32_t rinc) {
    const bool after = d >= inc;
    const uint32_t t = (((after ? d - inc : inc - d) >> 8) * rinc) >> 16;   // distance to the edge / inc, Q15
    const int32_t w = t >= 32768 ? 0 : 32768 - (int32_t)t;
    const int32_t c = (w * w) >> (30 - BELL_AMP_BITS);
    return after ? c : -c;
}

// Band-limited pulse, +-2048: high over the first `width` of the phase.
inline int32_t blepPulse(uint32_t phase, uint32_t width, uint32_t inc, uint32_t rinc) {
    int32_t s = phase < width ? (1 << BELL_AMP_BITS) : -(1 << BELL_AMP_BITS);
    uint32_t d = phase + inc;                 // rising edge at phase 0
    if (d < 2 * inc) s -= blepStep(d, inc, rinc);
    d -= width;                               // falling edge at width
    if (d < 2 * inc) s += blepStep(d, inc, rinc);
    return s;
}

struct Voice {
    Params p;

    uint32_t noise = 0x2F6E2B1Du;   // xorshift32
    bool active = false;
    bool gate = false;              // note held: ring; released: fast decay
    int32_t velGain = 0;            // Q8: velocity x the drive into the soft clipper

    // crash
    uint32_t ringEnv = 0;           // both bands
    uint32_t sizzleEnv = 0;         // more of the high band at the start
    uint32_t phase[PARTIALS] = {0, 0, 0, 0, 0, 0};
    int32_t noiseLp = 0;            // noise low-pass state
    int32_t hp1 = 0;                // high-passes (their low-pass states)
    int32_t hp2 = 0;
    int32_t lowS1 = 0;              // low band states
    int32_t lowS2 = 0;
    int32_t highS1 = 0;             // high band states
    int32_t highS2 = 0;

    // cowbell
    uint32_t snapEnv = 0;
    uint32_t tailEnv = 0;
    uint32_t bellPhase[2] = {0, 0};
    int32_t bellLow = 0;
    int32_t bellBand = 0;

    // FILTER states, x64
    int32_t s1 = 0;
    int32_t s2 = 0;

    // MIDI note-on: velocity 1 .. 127 -> level, the clapsnare curve (halfway
    // between linear and squared: 100 = -3 dB, 64 = -8 dB), so both firmwares
    // follow a sequencer alike. The crash gets random oscillator phases, so
    // no two hits are alike; the cowbell always starts the same way. An
    // engine that MORPH has faded out is not started.
    void trigger(uint8_t velocity) {
        if (velocity > 127) velocity = 127;
        // velocity (127 + velocity) / (2 x 127^2) in Q16, without a division
        velGain = ((((int32_t)velocity * (127 + velocity) * 2081) >> 10) * p.drive) >> 16;
        ringEnv = sizzleEnv = 0;
        if (p.crashLevel) {
            for (uint8_t i = 0; i < PARTIALS; i++) phase[i] = nextNoise();
            noiseLp = hp1 = hp2 = lowS1 = lowS2 = highS1 = highS2 = 0;
            ringEnv = sizzleEnv = ENV_FULL;
        }
        snapEnv = tailEnv = 0;
        if (p.bellLevel) {
            bellPhase[0] = bellPhase[1] = 0;
            bellLow = bellBand = 0;
            snapEnv = tailEnv = ENV_FULL;
        }
        gate = true;
        active = true;
    }

    // MIDI note-off: the ring goes into its release.
    void release() { gate = false; }

    // One band-pass of the crash.
    static int32_t band(const Band &c, int32_t x, int32_t &s1, int32_t &s2) {
        const int32_t v1 = (c.a1 * s1 + c.a2 * (x - s2)) >> 13;   // band
        const int32_t v2 = s2 + ((c.g * v1) >> 13);               // low
        s1 = 2 * v1 - s1;
        s2 = 2 * v2 - s2;
        return v1;
    }

    // The crash: the low band rings, the high band starts brighter.
    int32_t crashSample() {
        // the metal: six square oscillators, and the noise under it
        noiseLp += ((((int32_t)(int16_t)(nextNoise() >> 16) >> 3) - noiseLp) * p.crashNoiseA) >> 15;
        int32_t x = (noiseLp * CRASH_NOISE_Q8) >> 8;
        for (uint8_t i = 0; i < PARTIALS; i++) {
            phase[i] += p.inc[i];
            x += (phase[i] & 0x80000000u) ? METAL_GAIN : -METAL_GAIN;
        }
        // no fundamentals: 12 dB / octave high-pass
        hp1 += ((x - hp1) * p.crashHpA) >> 15;
        x -= hp1;
        const int32_t body = x;
        hp2 += ((x - hp2) * p.crashHpA) >> 15;
        x -= hp2;
        // the two bands, each with its envelope
        const int32_t low = band(p.crashLow, x, lowS1, lowS2);
        const int32_t high = band(p.crashHigh, x, highS1, highS2);
        const int32_t ring = (int32_t)(ringEnv >> 9), sizzle = (int32_t)(sizzleEnv >> 9);   // Q15
        const int32_t out = ((low + ((body * CRASH_BODY_Q8) >> 8)) * ((ring * CRASH_LOW_Q8) >> 8) +
                             high * ((ring * CRASH_HIGH_Q8 + sizzle * CRASH_SIZZLE_Q8) >> 8)) >> 15;
        ringEnv = decayStep(ringEnv, gate ? CRASH_RING_K : RELEASE_K);
        sizzleEnv = decayStep(sizzleEnv, gate ? CRASH_SIZZLE_K : RELEASE_K);
        if (ringEnv < ENV_END) ringEnv = sizzleEnv = 0;
        return out;
    }

    // The cowbell before its envelope: two pulses through the band-pass.
    int32_t bellRaw() {
        bellPhase[0] += p.bellInc[0];
        bellPhase[1] += p.bellInc[1];
        const int32_t tones = ((blepPulse(bellPhase[0], BELL_WIDTH[0], p.bellInc[0], p.bellRinc[0]) * BELL_FIRST_Q8) >> 8) +
                              blepPulse(bellPhase[1], BELL_WIDTH[1], p.bellInc[1], p.bellRinc[1]);
        bellLow += (p.bellF * bellBand) >> 15;
        const int32_t high = tones - bellLow - ((BELL_DAMP_Q15 * bellBand) >> 15);
        bellBand += (p.bellF * high) >> 15;
        return bellBand;
    }

    // The cowbell: a strike on a tail.
    int32_t bellSample() {
        const int32_t env = ((int32_t)(snapEnv >> 9) * BELL_SNAP_Q8 + (int32_t)(tailEnv >> 9) * (256 - BELL_SNAP_Q8)) >> 8;
        const int32_t out = (bellRaw() * env) >> 15;
        snapEnv = decayStep(snapEnv, BELL_SNAP_K);
        tailEnv = decayStep(tailEnv, gate ? BELL_TAIL_K : RELEASE_K);
        if (tailEnv < ENV_END) snapEnv = tailEnv = 0;
        return out;
    }

    // FILTER: state-variable low-pass in the trapezoidal form (stable and
    // true to its corner up to 16 kHz). Q15 in, states and output with 6
    // extra bits and exact products, so a low corner has no dead band and the
    // make-up gain has something to work on.
    int32_t filterWide(int32_t x) {
        const int32_t v3 = (x << 6) - s2;
        const int32_t v1 = mulQ15(s1, p.filterA1) + mulQ15(v3, p.filterA2);   // band
        const int32_t v2 = s2 + mulQ15(v1, p.filterG);                        // low
        s1 = 2 * v1 - s1;
        s2 = 2 * v2 - s2;
        return v2;
    }
    int32_t filter(int32_t x) { return filterWide(x) >> 6; }                  // Q15 out

    // FILTER and its make-up gain, Q15 in and out.
    int32_t filterMakeUp(int32_t x) {
        int32_t wide = filterWide(x);
        if (wide > FILTER_OUT_MAX << 6) wide = FILTER_OUT_MAX << 6;
        else if (wide < -(FILTER_OUT_MAX << 6)) wide = -(FILTER_OUT_MAX << 6);
        const int32_t y = mulQ15(wide, (uint32_t)p.filterGain << 1);          // / 64 x gain / 256
        return y > MIX_MAX ? MIX_MAX : (y < -MIX_MAX ? -MIX_MAX : y);
    }

    // Both engines at their levels, before the FILTER: one sample, Q15.
    int32_t mixSample() {
        int32_t mix = 0;
        if (ringEnv) mix = (crashSample() * p.crashLevel) >> 8;
        if (tailEnv) mix += (bellSample() * p.bellLevel) >> 8;
        if (!(ringEnv | tailEnv)) active = false;
        if (mix > MIX_MAX) mix = MIX_MAX;
        else if (mix < -MIX_MAX) mix = -MIX_MAX;
        return mix;
    }

    // One sample before the soft clipper, Q15 (driven into it: up to
    // MIX_MAX x the drive).
    int32_t renderLinear() {
        if (!active) return 0;
        int32_t mix = mixSample();

        // FILTER and its make-up gain; fully left it is skipped.
        if (p.filterOn) {
            mix = filterMakeUp(mix);
        } else {
            s1 = 0;           // no jump when it comes in
            s2 = mix << 6;
        }
        return (mix * velGain) >> 8;
    }

    // One sample, Q15.
    int32_t render() { return softClip(renderLinear()); }

private:
    uint32_t nextNoise() {
        uint32_t n = noise;
        n ^= n << 13;
        n ^= n >> 17;
        n ^= n << 5;
        noise = n;
        return n;
    }
};

// ---- knob smoothing ---------------------------------------------------------------

// One-pole smoothing in x16 fixed point (~16 ms at the 1 kHz scan): kills ADC
// jitter and turns the recorder's 24 PPQN steps into glides. rate 2 = ~4 ms,
// for the CV.
struct KnobFilter {
    uint32_t acc = 0;   // value << 4
    uint8_t rate = 4;
    bool primed = false;
    uint16_t update(uint16_t raw) {
        if (!primed) {
            acc = (uint32_t)raw << 4;
            primed = true;
        } else {
            acc += (int32_t)(((int32_t)raw << 4) - (int32_t)acc) >> rate;
        }
        return (uint16_t)(acc >> 4);
    }
    // Jumps to raw, no glide: the first reading after the scan was off.
    uint16_t set(uint16_t raw) {
        primed = false;
        return update(raw);
    }
};

// ---- MODE: 4-bar knob recorder on MIDI clock ----------------------------------------

// As ../clapsnare: the shared CvRecorder (opt/attiny1616-tools/lib/CvRecorder,
// used by the 8bit crash) with three 12-bit lanes instead of two 8-bit ones;
// button and LED are handled in main.cpp.
//
//   LIVE --press--> RECORDING --(384 clocks = 4 bars)--> PLAYBACK --click--> LIVE
//
// RECORDING stores the three knobs on every MIDI clock (a press discards the
// take). PLAYBACK replays them; the knobs are ignored for the first pass,
// then latched as the reference, and from there turning a knob shifts its
// whole recorded curve. MIDI Start rewinds to bar 1.
//
// OVERDUB (as the 16bit MotionRecorder): hold MODE in PLAYBACK and turn a
// knob. From its first move (more than OVERDUB_THRESHOLD from where it was at
// the press) until MODE is released, that knob's live value replaces the
// recording at the playhead; the others keep playing. Releasing MODE keeps
// the loop with the new curve, no offset until the knob moves again. A click
// (press and release, nothing moved) returns to LIVE on the release.
struct MotionRecorder {
    static const uint16_t LOOP_TICKS = 24 * 4 * 4;
    static const uint8_t LANES = 3;
    static const int32_t OVERDUB_THRESHOLD = 48;    // ADC codes (noise guard)
    enum State : uint8_t { LIVE, RECORDING, PLAYBACK };

    State state = LIVE;
    uint16_t tick = 0;
    uint16_t guardTicks = 0;
    uint16_t ref[LANES] = {0, 0, 0};
    uint16_t buf[LANES][LOOP_TICKS];

    // Overdub hold (MODE held in PLAYBACK).
    bool holding = false;
    bool holdLatched = false;
    uint8_t overdubMask = 0;                // bit i: lane i overdubbed
    uint16_t holdKnob[LANES] = {0, 0, 0};   // knobs at the first clock of the hold
    uint16_t lastLive[LANES] = {0, 0, 0};

    // MODE press edge: LIVE -> RECORDING, RECORDING -> LIVE (discard),
    // PLAYBACK: starts an overdub hold (or a click).
    void press() {
        if (state == PLAYBACK) {
            holding = true;
            holdLatched = false;
            overdubMask = 0;
        } else if (state == LIVE) {
            state = RECORDING;
            tick = 0;
        } else {
            state = LIVE;
        }
    }

    // MODE release edge. Nothing moved during the hold: back to LIVE.
    // Otherwise keep looping; the overdubbed lanes restart with no offset.
    void release() {
        if (!holding) return;
        holding = false;
        if (overdubMask == 0) {
            state = LIVE;
            return;
        }
        for (uint8_t i = 0; i < LANES; i++) {
            if (overdubMask & (1u << i)) ref[i] = lastLive[i];
        }
        overdubMask = 0;
    }

    bool overdubbing() const { return holding && overdubMask != 0; }

    void onStart() {
        if (state != LIVE) tick = 0;
    }

    // One MIDI clock. `out` gets the values to play (the knobs while
    // recording, so the loop starts from what was heard); false in LIVE.
    bool onClock(const uint16_t *live, uint16_t *out) {
        if (state == LIVE) return false;
        if (state == RECORDING) {
            for (uint8_t i = 0; i < LANES; i++) out[i] = buf[i][tick] = live[i];
        } else {
            if (holding) overdub(live);
            play(live, out);
        }
        if (++tick >= LOOP_TICKS) {
            tick = 0;
            if (state == RECORDING) {
                state = PLAYBACK;
                guardTicks = 0;
            }
        }
        return true;
    }

private:
    // Write the moved knobs into the frame at the playhead.
    void overdub(const uint16_t *live) {
        if (!holdLatched) {
            holdLatched = true;
            for (uint8_t i = 0; i < LANES; i++) holdKnob[i] = live[i];
        }
        for (uint8_t i = 0; i < LANES; i++) {
            const uint8_t bit = (uint8_t)(1u << i);
            if (!(overdubMask & bit)) {
                const int32_t moved = (int32_t)live[i] - (int32_t)holdKnob[i];
                if (moved <= OVERDUB_THRESHOLD && moved >= -OVERDUB_THRESHOLD) continue;
                overdubMask |= bit;
            }
            buf[i][tick] = lastLive[i] = live[i];
        }
    }

    void play(const uint16_t *live, uint16_t *out) {
        if (guardTicks < LOOP_TICKS) {
            guardTicks++;
            for (uint8_t i = 0; i < LANES; i++) {
                ref[i] = live[i];
                out[i] = buf[i][tick];
            }
        } else {
            for (uint8_t i = 0; i < LANES; i++) {
                if (overdubMask & (1u << i)) {   // plays what was just written
                    out[i] = buf[i][tick];
                    continue;
                }
                int32_t v = (int32_t)buf[i][tick] + (int32_t)live[i] - (int32_t)ref[i];
                out[i] = (uint16_t)(v < 0 ? 0 : (v > KNOB_MAX ? KNOB_MAX : v));
            }
        }
    }
};

// ---- MIDI ------------------------------------------------------------------------

// Byte-stream MIDI parser (as ../clapsnare): running status, real-time bytes
// anywhere, all channels.
struct MidiParser {
    enum Kind : uint8_t { NONE = 0, NOTE_ON, NOTE_OFF, CONTROL_CHANGE, CLOCK, START, CONTINUE, STOP };

    struct Event {
        Kind kind;
        uint8_t data1;
        uint8_t data2;
    };

    uint8_t status = 0;
    uint8_t data[2] = {0, 0};
    uint8_t count = 0;

    static uint8_t dataLength(uint8_t st) {
        switch (st & 0xF0) {
            case 0xC0: case 0xD0: return 1;
            case 0xF0:
                if (st == 0xF1 || st == 0xF3) return 1;
                if (st == 0xF2) return 2;
                return 0;
            default: return 2;
        }
    }

    // Feed one byte; returns the completed event (kind NONE if none).
    Event feed(uint8_t b) {
        Event ev = {NONE, 0, 0};
        if (b >= 0xF8) {                              // real-time: no state change
            if (b == 0xF8) ev.kind = CLOCK;
            else if (b == 0xFA) ev.kind = START;
            else if (b == 0xFB) ev.kind = CONTINUE;
            else if (b == 0xFC) ev.kind = STOP;
            return ev;
        }
        if (b & 0x80) {
            // Channel messages set the running status; system common and
            // SysEx cancel it (their data is skipped).
            status = (b < 0xF0) ? b : 0;
            count = 0;
            return ev;
        }
        if (status == 0) return ev;
        data[count++] = b;
        if (count < dataLength(status)) return ev;
        count = 0;
        switch (status & 0xF0) {
            case 0x90: ev.kind = data[1] ? NOTE_ON : NOTE_OFF; break;   // velocity 0 = note-off
            case 0x80: ev.kind = NOTE_OFF; break;
            case 0xB0: ev.kind = CONTROL_CHANGE; break;
            default: return ev;
        }
        ev.data1 = data[0];
        ev.data2 = data[1];
        return ev;
    }
};

}  // namespace crash
