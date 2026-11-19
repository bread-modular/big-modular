// ============================================================================
// 12bit osc3: three-oscillator mixer, behaviour only (no hardware access, so
// test/test_logic.cpp runs it on the host).
//
// Each knob sets one oscillator's frequency (exponential, FREQ_MIN_HZ ..
// FREQ_MIN_HZ x 2^OCTAVES); the three are summed at equal level and the mix
// goes to both DAC channels. MODE picks the waveform shared by all three.
// ============================================================================
#pragma once

#include <math.h>
#include <stdint.h>

namespace osc3 {

static const uint32_t SAMPLE_RATE_HZ = 48000;   // TIM6 tick (64 MHz / 1333 = 48.012 kHz)
static const float FREQ_MIN_HZ = 20.0f;         // knob fully down
static const float OCTAVES = 7.0f;              // knob fully up: 2560 Hz
static const uint16_t KNOB_MAX = 4095;          // 12-bit ADC

// DAC: mid-scale = 0 V at the jack (VOFF), +-DAC_SWING codes = +-4.7 V after
// the x3.4 stage, inside the buffered DAC range (0.2 .. 3.1 V).
static const int32_t DAC_MID = 2048;
static const int32_t DAC_SWING = 1700;

enum Wave : uint8_t { SINE, TRIANGLE, SAW, SQUARE, WAVE_COUNT };

static const uint32_t SINE_BITS = 10;
static const uint32_t SINE_SIZE = 1u << SINE_BITS;

inline void fillSine(int16_t *table) {
    for (uint32_t i = 0; i < SINE_SIZE; i++) {
        table[i] = (int16_t)lrintf(32767.0f * sinf(6.2831853f * (float)i / (float)SINE_SIZE));
    }
}

inline float knobHz(uint16_t knob) {
    if (knob > KNOB_MAX) knob = KNOB_MAX;
    return FREQ_MIN_HZ * exp2f(OCTAVES * (float)knob / (float)KNOB_MAX);
}

// Phase increment per sample for a 32-bit phase accumulator.
inline uint32_t phaseInc(float hz) {
    return (uint32_t)(hz * (4294967296.0f / (float)SAMPLE_RATE_HZ));
}

// One sample of the waveform at a 32-bit phase, -32767 .. +32767.
inline int32_t wave(Wave w, uint32_t phase, const int16_t *sine) {
    switch (w) {
        case SINE:
            return sine[phase >> (32 - SINE_BITS)];
        case TRIANGLE: {
            int32_t p = (int32_t)(phase >> 16);           // 0 .. 65535
            int32_t t = p < 32768 ? p : 65535 - p;        // 0 .. 32767 .. 0
            return 2 * t - 32767;
        }
        case SAW: {
            int32_t s = (int32_t)(phase >> 16) - 32768;   // -32768 .. 32767
            return s < -32767 ? -32767 : s;
        }
        case SQUARE:
        default:
            return phase < 0x80000000u ? 32767 : -32767;
    }
}

// Equal-level mix of the three -> 12-bit DAC code.
inline uint16_t mixToDac(int32_t a, int32_t b, int32_t c) {
    int32_t sum = a + b + c;                              // +-98301
    return (uint16_t)(DAC_MID + sum * DAC_SWING / (3 * 32767));
}

// One-pole knob smoothing in x16 fixed point: kills ADC jitter (audible as
// pitch wobble) and still follows a turn within a few ms.
struct KnobFilter {
    uint32_t acc = 0;   // value << 4
    bool primed = false;
    uint16_t update(uint16_t raw) {
        if (!primed) {
            acc = (uint32_t)raw << 4;
            primed = true;
        } else {
            acc += (int32_t)(((int32_t)raw << 4) - (int32_t)acc) >> 4;
        }
        return (uint16_t)(acc >> 4);
    }
};

}  // namespace osc3
