#pragma once

// Pico-free wavetable oscillator core (this module, not BM), shared by the
// polysynth's Wavetable generator and the host test tools/sim_wavetable.cpp.
// Tables: wavetable_data.h (tools/build_wavetables.py). One mip level per
// octave, picked from the frequency so the top harmonic stays under 20 kHz;
// the position morphs linearly between neighbouring frames. P1's last step,
// Noise, has no table: each oscillator makes noise itself and the position
// crossfades its types (WavetableNoise).

#include <stdint.h>
#include <math.h>
#include "audio/gen/wavetable_data.h"

// Frame 0 of a table in WAVETABLE_DATA (flash on the board).
static inline const int16_t* wavetableFrames(uint8_t table) {
    if (table >= WAVETABLE_COUNT) {
        table = WAVETABLE_COUNT - 1;
    }
    return WAVETABLE_DATA + table * WAVETABLE_TABLE_SAMPLES;
}

// `frames` and `position` are written by the app (main core): an aligned
// pointer and float, so no lock is needed. On the board `frames` points to
// the app's RAM copy of the table: voices reading the 1.1 MB in flash miss
// the XIP cache and overrun the audio core. The audio core calls tick() once
// a sample, before the voices: the smoothed position, its frame pair and
// morph are the same for every voice, so they are worked out once.
struct WavetableControl {
    static constexpr float SMOOTH_TIME_S = 0.005f;
    // Noise types along the position: brown, pink, white, blue, digital
    // (sample and hold), crackle.
    static constexpr int NOISE_TYPES = 6;

    const int16_t* volatile frames = WAVETABLE_DATA;  // WAVETABLE_TABLE_SAMPLES
    volatile float position = 0.0f;  // 0 .. WAVETABLE_FRAMES - 1
    volatile bool noise = false;     // P1 on Noise: `frames` is not read

    float smooth = 0.0045f;
    float smoothed = 0.0f;
    const int16_t* frameA = WAVETABLE_DATA;  // frame floor(smoothed), level 0
    float morph = 0.0f;                      // towards frameA + 1 frame
    uint8_t noiseType = 0;                   // floor of the noise position
    float noiseMorph = 0.0f;                 // towards noiseType + 1

    // Before the audio core runs; jumps straight to `position`.
    void init(float sampleRate) {
        smooth = 1.0f - expf(-1.0f / (SMOOTH_TIME_S * sampleRate));
        smoothed = position;
        tick();
    }

    void tick() {
        smoothed += (position - smoothed) * smooth;
        int frame = (int)smoothed;
        if (frame < 0) {
            frame = 0;
        } else if (frame > WAVETABLE_FRAMES - 2) {
            frame = WAVETABLE_FRAMES - 2;
        }
        morph = smoothed - frame;
        frameA = frames + frame * WAVETABLE_FRAME_STRIDE;

        float n = smoothed * ((NOISE_TYPES - 1) / (float)(WAVETABLE_FRAMES - 1));
        int type = (int)n;
        if (type < 0) {
            type = 0;
        } else if (type > NOISE_TYPES - 2) {
            type = NOISE_TYPES - 2;
        }
        noiseType = (uint8_t)type;
        noiseMorph = n - type;
        if (noiseMorph < 0.0f) {
            noiseMorph = 0.0f;
        } else if (noiseMorph > 1.0f) {
            noiseMorph = 1.0f;
        }
    }
};

// One oscillator's noise (P1 on Noise). Every type runs each sample from one
// xorshift white source, so a crossfade never meets a cold filter. Each is
// scaled to ~0.3 RMS. Digital holds a random level for 1 / (8 f) and Crackle
// fires ~f / 2 decaying clicks a second, so the keys still change them; the
// colours ignore the pitch. Voices get different seeds (a chord would
// otherwise play the same noise louder).
class WavetableNoise {
    private:
        static constexpr float WHITE_GAIN = 0.52f;
        static constexpr float PINK_GAIN = 0.175f;
        static constexpr float BROWN_GAIN = 1.04f;
        static constexpr float BLUE_GAIN = 0.367f;
        static constexpr float DIGITAL_GAIN = 0.52f;
        static constexpr float CRACKLE_DECAY = 0.98f;  // ~1 ms click

        // One counter for every TU (an inline function's static).
        static uint32_t nextSeed() {
            static uint32_t counter = 0x12345678u;
            counter += 0x9E3779B9u;
            return counter | 1u;
        }

        uint32_t rng;
        float pink0 = 0.0f, pink1 = 0.0f, pink2 = 0.0f;
        float brown = 0.0f;
        float lastWhite = 0.0f;
        float held = 0.0f;
        uint32_t holdPhase = 0;
        uint32_t holdInc = 0;
        uint32_t crackleChance = 0;  // per sample, of 2^32
        float crackle = 0.0f;

        uint32_t next() {
            rng ^= rng << 13;
            rng ^= rng >> 17;
            rng ^= rng << 5;
            return rng;
        }

        // -1 .. 1
        float white() {
            return (int32_t)next() * (1.0f / 2147483648.0f);
        }

    public:
        WavetableNoise() : rng(nextSeed()) {}

        void setFrequency(float frequency, float sampleRate) {
            float hold = 8.0f * frequency / sampleRate;
            if (hold > 0.99f) {
                hold = 0.99f;
            }
            holdInc = (uint32_t)(hold * 4294967296.0f);
            float chance = 0.5f * frequency / sampleRate;
            if (chance > 0.5f) {
                chance = 0.5f;
            }
            crackleChance = (uint32_t)(chance * 4294967296.0f);
        }

        float getSample(uint8_t type, float morph) {
            const float w = white();
            // Paul Kellet's economy pink filter (-3 dB / octave).
            pink0 = 0.99765f * pink0 + w * 0.0990460f;
            pink1 = 0.96300f * pink1 + w * 0.2965164f;
            pink2 = 0.57000f * pink2 + w * 1.0526913f;
            brown = 0.995f * brown + w * 0.05f;  // leaky integrator, ~35 Hz
            const float blue = w - lastWhite;
            lastWhite = w;
            const uint32_t hold = holdPhase + holdInc;
            if (hold < holdPhase) {
                held = white();
            }
            holdPhase = hold;
            crackle *= CRACKLE_DECAY;
            if (next() < crackleChance) {
                const float r = white();
                crackle = r < 0.0f ? r - 0.6f : r + 0.6f;  // 0.6 .. 1.6
                crackle *= 0.62f;
            }

            float v[WavetableControl::NOISE_TYPES] = {
                brown * BROWN_GAIN,
                (pink0 + pink1 + pink2 + w * 0.1848f) * PINK_GAIN,
                w * WHITE_GAIN,
                blue * BLUE_GAIN,
                held * DIGITAL_GAIN,
                crackle,
            };
            float out = v[type] + (v[type + 1] - v[type]) * morph;
            if (out > 1.0f) {
                out = 1.0f;
            } else if (out < -1.0f) {
                out = -1.0f;
            }
            return out;
        }
};

// Knob (0..1) -> zone 0..zones - 1. A new zone is taken only `hysteresis`
// (of a zone) past its boundary, so a knob or CV resting on a boundary
// doesn't flip between two zones.
static inline uint8_t wavetableZoneFor(float norm, uint8_t current, uint8_t zones,
                                       float hysteresis) {
    float z = norm * zones;
    int candidate = (int)z;
    if (candidate < 0) {
        candidate = 0;
    } else if (candidate > zones - 1) {
        candidate = zones - 1;
    }
    if (candidate > current && z < candidate + hysteresis) {
        return current;
    }
    if (candidate < current && z > candidate + 1 - hysteresis) {
        return current;
    }
    return (uint8_t)candidate;
}

class WavetableOsc {
    private:
        static constexpr float MAX_HARMONIC_HZ = 20000.0f;

        const WavetableControl* control = nullptr;
        float sampleRate = 44100.0f;
        uint32_t phase = 0;
        uint32_t phaseInc = 0;
        uint8_t level = 0;
        WavetableNoise noise;

    public:
        void init(const WavetableControl* control, float sampleRate) {
            this->control = control;
            this->sampleRate = sampleRate;
        }

        static uint8_t levelFor(float frequency) {
            for (uint8_t l = 0; l < WAVETABLE_LEVELS - 1; l++) {
                if (WAVETABLE_LEVEL_HARMONICS[l] * frequency <= MAX_HARMONIC_HZ) {
                    return l;
                }
            }
            return WAVETABLE_LEVELS - 1;
        }

        void setFrequency(float frequency) {
            phaseInc = (uint32_t)(frequency / sampleRate * 4294967296.0f);
            level = levelFor(frequency);
            noise.setFrequency(frequency, sampleRate);
        }

        void reset() {
            phase = 0;
        }

        uint8_t getLevel() const {
            return level;
        }

        // After control->tick() for this sample.
        float getSample() {
            if (control->noise) {
                return noise.getSample(control->noiseType, control->noiseMorph);
            }
            const uint8_t level = this->level;  // one read: setFrequency() runs on the other core
            const int16_t* a = control->frameA + WAVETABLE_LEVEL_OFFSET[level];
            const int16_t* b = a + WAVETABLE_FRAME_STRIDE;
            const float morph = control->morph;

            const uint8_t shift = WAVETABLE_LEVEL_SHIFT[level];
            const uint32_t mask = WAVETABLE_LEVEL_SIZE[level] - 1;
            const uint32_t i1 = phase >> shift;
            const uint32_t i0 = (i1 - 1) & mask;
            const uint32_t i2 = (i1 + 1) & mask;
            const uint32_t i3 = (i1 + 2) & mask;
            // Fraction from the top 24 bits below the index (no divide).
            const float t = (float)((phase << (32 - shift)) >> 8) * (1.0f / 16777216.0f);
            phase += phaseInc;

            // Morph the four points, then one Catmull-Rom (cubic Hermite)
            // step: its interpolation images sit ~30 dB under linear's.
            const float x0 = a[i0] + (b[i0] - a[i0]) * morph;
            const float x1 = a[i1] + (b[i1] - a[i1]) * morph;
            const float x2 = a[i2] + (b[i2] - a[i2]) * morph;
            const float x3 = a[i3] + (b[i3] - a[i3]) * morph;
            const float c1 = 0.5f * (x2 - x0);
            const float c2 = x0 - 2.5f * x1 + 2.0f * x2 - 0.5f * x3;
            const float c3 = 0.5f * (x3 - x0) + 1.5f * (x1 - x2);
            return (((c3 * t + c2) * t + c1) * t + x1) * (1.0f / 32768.0f);
        }
};
