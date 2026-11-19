// ============================================================================
// 12bit clapsnare: synthesized hand clap + snare (side) drum, behaviour only
// (no hardware access, so test/test_logic.cpp runs it on the host).
//
// Two engines, both from one free-running noise source, no samples:
//   CLAP   noise -> band-pass -> three short bursts 10.5 ms apart, then a
//          fourth hit with the long tail (TR-808 / 909 structure).
//   SNARE  two short sine partials (1 : 1.83) with a fast pitch drop + noise
//          through a resonant high-pass, a snappy and a long envelope.
// The noise is low-passed at ~9 kHz first (no digital fizz up to 24 kHz).
// The sum goes through a soft clipper, so hard hits and the layered middle
// of the MORPH knob saturate instead of clipping.
//
//   P1 MORPH  clap -> clap + snare layered -> snare
//   P2 TONE   clap band 650 Hz .. 2.4 kHz, snare tuning 135 .. 300 Hz and
//             noise high-pass 0.8 .. 3.2 kHz
//   CV        added to TONE: 5 V = the whole knob travel, bipolar
//   P3 DECAY  clap tail 30 .. 500 ms, snare noise 30 .. 400 ms, body
//             25 .. 110 ms (time constants)
//
// Integer maths only in render() (Cortex-M0+: no FPU, no 64-bit multiply);
// floats only fill the tables at boot.
// ============================================================================
#pragma once

#include <math.h>
#include <stdint.h>

namespace clapsnare {

static const uint32_t SAMPLE_RATE_HZ = 48000;   // TIM6 tick (64 MHz / 1333 = 48.012 kHz)
static const uint16_t KNOB_MAX = 4095;          // 12-bit ADC

// DAC: mid-scale = 0 V at the jack (VOFF), +-DAC_SWING codes = +-4.7 V after
// the x3.4 stage, inside the buffered DAC range (0.2 .. 3.1 V).
static const int32_t DAC_MID = 2048;
static const int32_t DAC_SWING = 1700;

// ---- tuning constants --------------------------------------------------------

// Envelopes are Q24 (ENV_FULL = 1.0); a decay constant k is the fraction lost
// per sample in Q24: k = 2^24 / (tau x 48000).
static const uint32_t ENV_FULL = 1u << 24;
constexpr uint32_t decayK(float tauMs) { return (uint32_t)(16777216.0f / (tauMs * 48.0f)); }

// P1 MORPH: a little dead travel at both ends, so the ends are the pure sounds.
static const uint16_t MORPH_DEAD = 120;
static const uint16_t LAYER_TRIM = 56;          // of 256: each engine -22 % when both are full

static const int32_t NOISE_LP_Q15 = 22680;      // one-pole low-pass ~9 kHz on the noise

// CV in -> TONE. The input stage (R4 100k, R5 56k to +3V3, R6 120k to GND)
// maps the jack to 1.628 V + 0.2763 x Vcv at PA0: 342.9 ADC codes per volt.
static const int32_t CV_ZERO = 2021;            // 0 V, and nothing patched (tip normalled to GND)
static const int32_t CV_DEAD = 24;              // +-0.07 V: part tolerances don't move TONE
static const int32_t CV_FULL = 1714;            // 5 V = the whole knob travel

// Clap
static const float CLAP_FC_LO_HZ = 650.0f;      // TONE fully down
static const uint32_t CLAP_FC_OCT_Q16 = 124518; // 1.9 octaves -> 2.43 kHz
static const int32_t CLAP_DAMP_Q15 = 18022;     // 1 / Q, Q = 1.82
static const uint32_t CLAP_SPACING = 504;       // 10.5 ms between the hits
static const uint32_t CLAP_BURST_K = decayK(4.5f);
static const uint32_t CLAP_TAIL_START = (ENV_FULL / 100) * 80;
static const float CLAP_TAIL_SHORT_MS = 30.0f;  // DECAY fully down
static const uint32_t CLAP_TAIL_OCT_Q16 = 266003;   // 4.06 octaves -> 500 ms
static const int32_t CLAP_LEVEL = 5500;         // Q8, at TONE fully down

// Snare
static const float BODY_HZ_LO = 135.0f;         // TONE fully down
static const uint32_t BODY_OCT_Q16 = 75500;     // 1.152 octaves -> 300 Hz
static const uint32_t BODY_RATIO_Q8 = 469;      // second partial x1.83 (180 / 330 Hz)
static const uint32_t PITCH_DEPTH_Q8 = 154;     // starts 60 % sharp ...
static const uint32_t PITCH_K = decayK(10.0f);  // ... and drops in ~10 ms
static const float BODY_SHORT_MS = 25.0f;
static const uint32_t BODY_OCT_DECAY_Q16 = 140084;  // 2.14 octaves -> 110 ms
static const float SNARE_FC_LO_HZ = 800.0f;     // noise high-pass, TONE fully down
static const uint32_t SNARE_FC_OCT_Q16 = 131072;    // 2 octaves -> 3.2 kHz
static const int32_t SNARE_DAMP_Q15 = 26214;    // 1 / Q, Q = 1.25
static const uint32_t SNAP_K = decayK(22.0f);   // snappy part of the noise
static const int32_t SNAP_PART_Q8 = 115;        // 45 % snap, 55 % tail
static const float NOISE_SHORT_MS = 30.0f;
static const uint32_t NOISE_OCT_Q16 = 244908;   // 3.74 octaves -> 400 ms
static const int32_t BODY_LEVEL_Q8 = 82;       // first partial
static const int32_t BODY2_LEVEL_Q8 = 38;       // second partial
static const int32_t NOISE_LEVEL = 1560;        // Q8

// ---- tables --------------------------------------------------------------------

static const uint32_t SINE_BITS = 10;
static const uint32_t SINE_SIZE = 1u << SINE_BITS;
static const uint32_t POW2_SIZE = 256;

struct Tables {
    int16_t sine[SINE_SIZE];
    uint32_t pow2[POW2_SIZE + 1];   // 2^(i / 256), Q16

    void fill() {
        for (uint32_t i = 0; i < SINE_SIZE; i++) {
            sine[i] = (int16_t)lrintf(32767.0f * sinf(6.2831853f * (float)i / (float)SINE_SIZE));
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

    // Exponential knob law: 2^(octaves x knob / KNOB_MAX), Q16.
    uint32_t knobRatio(uint16_t knob, uint32_t octQ16) const {
        if (knob > KNOB_MAX) knob = KNOB_MAX;
        return ratio(octQ16 * knob / KNOB_MAX);   // octaves < 16: fits 32 bit
    }
};

// ---- knobs -> synthesis parameters -----------------------------------------------

struct Params {
    int32_t clapGain = 0;      // Q8, MORPH
    int32_t snareGain = 0;     // Q8, MORPH
    int32_t clapF = 0;         // band-pass coefficient, Q15
    int32_t clapLevel = 0;     // Q8, level-compensated for the band width
    uint32_t clapTailK = 0;
    uint32_t bodyInc = 0;      // first partial, phase increment per sample
    uint32_t bodyK = 0;
    int32_t snareF = 0;        // noise high-pass coefficient, Q15
    uint32_t noiseK = 0;
};

// Filter coefficient of the state-variable filters for a corner in Hz:
// f = 2 sin(pi fc / fs), close enough to 2 pi fc / fs below 4 kHz.
constexpr int32_t svfCoeff(float hz) { return (int32_t)(hz * (6.2831853f * 32768.0f / 48000.0f)); }

inline Params makeParams(const Tables &t, uint16_t morph, uint16_t tone, uint16_t decay) {
    Params p;

    // MORPH: clap full over the first half and fading over the second, snare
    // the other way round; both trimmed where they overlap.
    int32_t m = (int32_t)morph - MORPH_DEAD;
    const int32_t span = KNOB_MAX - 2 * MORPH_DEAD;
    if (m < 0) m = 0;
    if (m > span) m = span;
    int32_t gs = (m * 512) / span;              // 0 .. 512
    int32_t gc = 512 - gs;
    if (gs > 256) gs = 256;
    if (gc > 256) gc = 256;
    const int32_t trim = 256 - (((gs < gc ? gs : gc) * LAYER_TRIM) >> 8);
    p.clapGain = (gc * trim) >> 8;
    p.snareGain = (gs * trim) >> 8;

    // TONE
    const uint32_t clapR = t.knobRatio(tone, CLAP_FC_OCT_Q16);
    p.clapF = (int32_t)(((uint32_t)svfCoeff(CLAP_FC_LO_HZ) * clapR) >> 16);
    // The band widens with its centre, so the noise power rises with it:
    // level / sqrt(ratio) keeps the loudness even over the knob.
    p.clapLevel = (int32_t)(((uint32_t)CLAP_LEVEL << 16) / t.knobRatio(tone, CLAP_FC_OCT_Q16 / 2));
    p.bodyInc = (uint32_t)(((uint64_t)(uint32_t)(BODY_HZ_LO * (4294967296.0f / 48000.0f)) *
                            t.knobRatio(tone, BODY_OCT_Q16)) >> 16);
    p.snareF = (int32_t)(((uint32_t)svfCoeff(SNARE_FC_LO_HZ) * t.knobRatio(tone, SNARE_FC_OCT_Q16)) >> 16);

    // DECAY: knob up = longer = smaller k (k of 25 ms << 16 still fits 32 bit)
    p.clapTailK = (decayK(CLAP_TAIL_SHORT_MS) << 16) / t.knobRatio(decay, CLAP_TAIL_OCT_Q16);
    p.bodyK = (decayK(BODY_SHORT_MS) << 16) / t.knobRatio(decay, BODY_OCT_DECAY_Q16);
    p.noiseK = (decayK(NOISE_SHORT_MS) << 16) / t.knobRatio(decay, NOISE_OCT_Q16);
    return p;
}

// TONE knob + CV: the knob sets the centre, the CV moves it both ways
// (+-5 V = +-the whole travel), clamped at the ends of the knob range.
inline uint16_t applyCv(uint16_t tone, uint16_t cvAdc) {
    int32_t d = (int32_t)cvAdc - CV_ZERO;
    if (d > CV_DEAD) d -= CV_DEAD;
    else if (d < -CV_DEAD) d += CV_DEAD;
    else d = 0;
    const int32_t v = (int32_t)tone + d * KNOB_MAX / (CV_FULL - CV_DEAD);
    return (uint16_t)(v < 0 ? 0 : (v > KNOB_MAX ? KNOB_MAX : v));
}

// ---- voice ---------------------------------------------------------------------

// One exponential decay step of a Q24 envelope; the constant term ends it.
inline uint32_t decayStep(uint32_t env, uint32_t k) {
    const uint32_t dec = (((env >> 12) * k) >> 12) + 16;
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

struct Voice {
    Params p;

    uint32_t noise = 0x2F6E2B1Du;   // free-running xorshift32
    int32_t white = 0;              // low-passed noise, +-4096
    bool active = false;
    int32_t velGain = 0;            // Q8

    // clap
    uint32_t clapCount = 3 * CLAP_SPACING;
    uint32_t burstEnv = 0;
    uint32_t tailEnv = 0;
    int32_t cLow = 0;
    int32_t cBand = 0;

    // snare
    uint32_t phase1 = 0;
    uint32_t phase2 = 0;
    uint32_t pitchEnv = 0;
    uint32_t bodyEnv = 0;
    uint32_t body2Env = 0;
    uint32_t snapEnv = 0;
    uint32_t noiseEnv = 0;
    int32_t sLow = 0;
    int32_t sBand = 0;

    // MIDI note-on: velocity 1 .. 127 -> level (and how hard the clipper is
    // hit), halfway between linear and squared: 100 = -3 dB, 64 = -8 dB.
    void trigger(uint8_t velocity) {
        if (velocity > 127) velocity = 127;
        velGain = ((int32_t)velocity * (127 + velocity) * 256) / (2 * 127 * 127);
        clapCount = 0;
        burstEnv = ENV_FULL;
        tailEnv = 0;
        phase1 = 0;
        phase2 = 0;
        pitchEnv = ENV_FULL;
        bodyEnv = ENV_FULL;
        body2Env = ENV_FULL;
        snapEnv = ENV_FULL;
        noiseEnv = ENV_FULL;
        active = true;
    }

    // One sample, Q15 (+-32767 after the soft clipper).
    int32_t render(const int16_t *sine) {
        uint32_t n = noise;
        n ^= n << 13;
        n ^= n >> 17;
        n ^= n << 5;
        noise = n;
        white += ((((int32_t)(int16_t)(n >> 16) >> 3) - white) * NOISE_LP_Q15) >> 15;
        if (!active) return 0;

        // ---- clap: hits at 0, 1 and 2 spacings, the tail starts at 3
        if (clapCount < 3 * CLAP_SPACING) {
            clapCount++;
            if (clapCount == CLAP_SPACING || clapCount == 2 * CLAP_SPACING) burstEnv = ENV_FULL;
            else if (clapCount == 3 * CLAP_SPACING) tailEnv = CLAP_TAIL_START;
        }
        int32_t clap = 0;
        uint32_t clapEnv = burstEnv + tailEnv;
        if (clapEnv) {
            if (clapEnv > ENV_FULL) clapEnv = ENV_FULL;
            cLow += (p.clapF * cBand) >> 15;
            const int32_t high = white - cLow - ((CLAP_DAMP_Q15 * cBand) >> 15);
            cBand += (p.clapF * high) >> 15;
            clap = ((cBand + (high >> 3)) * (int32_t)(clapEnv >> 9)) >> 15;
            clap = (clap * p.clapLevel) >> 8;
            burstEnv = decayStep(burstEnv, CLAP_BURST_K);
            tailEnv = decayStep(tailEnv, p.clapTailK);
        }

        // ---- snare body: two partials, pitch dropping to the tuning
        int32_t snare = 0;
        if (bodyEnv) {
            const uint32_t bend = ((pitchEnv >> 9) * PITCH_DEPTH_Q8) >> 8;   // Q15
            const uint32_t inc = p.bodyInc + (p.bodyInc >> 15) * bend;
            phase1 += inc;
            phase2 += (inc >> 8) * BODY_RATIO_Q8;
            const int32_t s1 = (sine[phase1 >> (32 - SINE_BITS)] * (int32_t)(bodyEnv >> 9)) >> 15;
            const int32_t s2 = (sine[phase2 >> (32 - SINE_BITS)] * (int32_t)(body2Env >> 9)) >> 15;
            snare = (s1 * BODY_LEVEL_Q8 + s2 * BODY2_LEVEL_Q8) >> 8;
            pitchEnv = decayStep(pitchEnv, PITCH_K);
            bodyEnv = decayStep(bodyEnv, p.bodyK);
            body2Env = decayStep(body2Env, 2 * p.bodyK);
        }

        // ---- snare noise: resonant high-pass
        if (noiseEnv) {
            sLow += (p.snareF * sBand) >> 15;
            const int32_t high = white - sLow - ((SNARE_DAMP_Q15 * sBand) >> 15);
            sBand += (p.snareF * high) >> 15;
            const int32_t env = ((int32_t)(snapEnv >> 9) * SNAP_PART_Q8 +
                                 (int32_t)(noiseEnv >> 9) * (256 - SNAP_PART_Q8)) >> 8;   // Q15
            snare += ((((high + (sBand >> 1)) * env) >> 15) * NOISE_LEVEL) >> 8;
            snapEnv = decayStep(snapEnv, SNAP_K);
            noiseEnv = decayStep(noiseEnv, p.noiseK);
        }

        if (!(clapEnv | bodyEnv | noiseEnv) && clapCount >= 3 * CLAP_SPACING) active = false;

        const int32_t mix = (clap * p.clapGain + snare * p.snareGain) >> 8;
        return softClip((mix * velGain) >> 8);
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

// The shared CvRecorder (opt/attiny1616-tools/lib/CvRecorder) behaviour with
// three 12-bit lanes instead of two 8-bit ones; button and LED are handled in
// main.cpp.
//
//   LIVE --press--> RECORDING --(384 clocks = 4 bars)--> PLAYBACK --press--> LIVE
//
// RECORDING stores the three knobs on every MIDI clock (a press discards the
// take). PLAYBACK replays them; the knobs are ignored for the first pass,
// then latched as the reference, and from there turning a knob shifts its
// whole recorded curve. MIDI Start rewinds to bar 1.
struct MotionRecorder {
    static const uint16_t LOOP_TICKS = 24 * 4 * 4;
    static const uint8_t LANES = 3;
    enum State : uint8_t { LIVE, RECORDING, PLAYBACK };

    State state = LIVE;
    uint16_t tick = 0;
    uint16_t guardTicks = 0;
    uint16_t ref[LANES] = {0, 0, 0};
    uint16_t buf[LANES][LOOP_TICKS];

    void press() {
        if (state == LIVE) {
            state = RECORDING;
            tick = 0;
        } else {
            state = LIVE;
        }
    }

    void onStart() {
        if (state != LIVE) tick = 0;
    }

    // One MIDI clock. `out` gets the values to play (the knobs while
    // recording, so the loop starts from what was heard); false in LIVE.
    bool onClock(const uint16_t *live, uint16_t *out) {
        if (state == LIVE) return false;
        if (state == RECORDING) {
            for (uint8_t i = 0; i < LANES; i++) out[i] = buf[i][tick] = live[i];
        } else if (guardTicks < LOOP_TICKS) {
            guardTicks++;
            for (uint8_t i = 0; i < LANES; i++) {
                ref[i] = live[i];
                out[i] = buf[i][tick];
            }
        } else {
            for (uint8_t i = 0; i < LANES; i++) {
                int32_t v = (int32_t)buf[i][tick] + (int32_t)live[i] - (int32_t)ref[i];
                out[i] = (uint16_t)(v < 0 ? 0 : (v > KNOB_MAX ? KNOB_MAX : v));
            }
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
};

// ---- MIDI ------------------------------------------------------------------------

// Byte-stream MIDI parser (as modules/hats): running status, real-time bytes
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

}  // namespace clapsnare
