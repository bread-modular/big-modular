#pragma once

// Pico-free wavetable oscillator core (this module, not BM), shared by the
// polysynth's Wavetable generator and the host test tools/sim_wavetable.cpp.
// Tables: wavetable_data.h (tools/build_wavetables.py). One mip level per
// octave, picked from the frequency so the top harmonic stays under 20 kHz;
// the position morphs linearly between neighbouring frames.

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

    const int16_t* volatile frames = WAVETABLE_DATA;  // WAVETABLE_TABLE_SAMPLES
    volatile float position = 0.0f;  // 0 .. WAVETABLE_FRAMES - 1

    float smooth = 0.0045f;
    float smoothed = 0.0f;
    const int16_t* frameA = WAVETABLE_DATA;  // frame floor(smoothed), level 0
    float morph = 0.0f;                      // towards frameA + 1 frame

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
        }

        void reset() {
            phase = 0;
        }

        uint8_t getLevel() const {
            return level;
        }

        // After control->tick() for this sample.
        float getSample() {
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
