#pragma once

// Rate and shape maths for the 8bit LFO, kept free of AVR registers so the host
// simulator (../sim) runs the same code.
//
// RATE: exponential, as most Eurorack LFOs (Doepfer A-147-2, Tides, Batumi): the
// P1 knob spans 12 octaves, 0.01 Hz (100 s) .. 40.6 Hz, and CV in adds about
// 1 V/oct on top (-5.5..+5.5 V), so FM reaches audio rate: knob CW + 5 V ~ 1.3 kHz.
// The sum is clamped to 0.01 Hz / 64 (~107 min) .. 2 kHz.
//
// WAVE: seven shapes, neighbours crossfaded; each one holds pure over a short
// stretch of the pot so it is easy to land on.

#include <stdint.h>

namespace LfoMath {

constexpr uint32_t kSampleRateHz = 40000;

// Rate pitch: Q8 octaves (256 = one octave) above kRateFloorHz = 0.01 Hz / 64.
// Pitch kKnobBase = 6 octaves up = 0.01 Hz, the knob fully CCW with no CV.
constexpr int16_t kOctave = 256;
constexpr int16_t kKnobBase = 6 * kOctave;
constexpr uint8_t kKnobPitchPerCount = 3;      // 1023 counts -> 11.99 octaves
constexpr int16_t kPitchMax = 24 * kOctave - 1;
// Phase increment of the floor rate in Q8: 0.01 / 64 * 2^32 / 40 kHz * 256.
constexpr uint32_t kFloorIncrementQ8 = 4295;
constexpr uint32_t kMaxIncrement = 214748365;  // 2 kHz: 2000 * 2^32 / 40 kHz

// CV in: -5.5..+5.5 V -> ADC 0..1023, 0 V ~ 509, 92.75 counts/V (docs/research.md
// §3.2b). 1 V/oct = 256 / 92.75 pitch per count = 707 / 256.
constexpr int16_t kCvInZero = 509;             // calibrate per unit (docs/research.md)
constexpr int16_t kCvInDeadband = 3;           // counts around 0 V treated as 0 V
constexpr int32_t kCvPitchPerCountQ8 = 707;

// 2^(i/16) in Q16, i = 0..16.
constexpr uint32_t kExp2Q16[17] = {
  65536, 68438, 71468, 74632, 77936, 81386, 84990, 88752, 92682,
  96785, 101070, 105545, 110218, 115098, 120194, 125515, 131072,
};

// CV in offset from 0 V in ADC counts, with the deadband.
inline int16_t cvInOffset(uint16_t cvIn) {
  int16_t offset = (int16_t)cvIn - kCvInZero;
  if (offset >= -kCvInDeadband && offset <= kCvInDeadband) {
    return 0;
  }
  return offset;
}

// P1 knob (0..1023) + CV in (ADC 0..1023) -> rate pitch, clamped 0..kPitchMax.
inline int16_t ratePitch(uint16_t knob, uint16_t cvIn) {
  int16_t cvPitch = ((int32_t)cvInOffset(cvIn) * kCvPitchPerCountQ8) / 256;
  int16_t pitch = kKnobBase + (int16_t)(knob * kKnobPitchPerCount) + cvPitch;
  if (pitch < 0) {
    return 0;
  }
  if (pitch > kPitchMax) {
    return kPitchMax;
  }
  return pitch;
}

// Rate pitch -> 32-bit phase increment per sample (2^frac by table + linear
// interpolation, < 0.03 % error), capped at 2 kHz. 32-bit maths only.
inline uint32_t phaseIncrement(int16_t pitch) {
  uint8_t octave = (uint16_t)pitch >> 8;
  uint8_t frac = pitch & 0xFF;
  uint8_t i = frac >> 4;
  uint8_t f = frac & 0x0F;
  uint32_t mantissa = kExp2Q16[i] + (((kExp2Q16[i + 1] - kExp2Q16[i]) * f) >> 4);
  uint32_t increment = (kFloorIncrementQ8 * mantissa) >> (24 - octave);
  return increment > kMaxIncrement ? kMaxIncrement : increment;
}

// Frequency in mHz for a phase increment (host checks and docs only).
inline uint32_t incrementToMilliHz(uint32_t increment) {
  return (uint32_t)(((uint64_t)increment * kSampleRateHz * 1000ULL) >> 32);
}

enum Shape : uint8_t {
  Sine = 0,
  Triangle,
  Saw,
  Square,
  Complex1,
  Complex2,
  Random,        // sample & hold: a new value at every cycle start
  kShapeCount,
};

// Pure stretch at each end of a crossfade segment, out of 256 (48 + 48 of the
// ~171 counts between two shapes, so each shape holds pure for ~64 counts).
constexpr uint8_t kShapeHold = 48;

struct ShapeMix {
  uint8_t a;
  uint8_t b;
  uint8_t blend;  // 0 = all a .. 255 = almost all b
};

// P2 knob (0..1023) -> the two neighbouring shapes and their crossfade.
inline ShapeMix shapeMix(uint16_t knob) {
  const uint8_t maxShape = kShapeCount - 1;
  uint32_t scaled = ((uint32_t)knob * ((uint32_t)maxShape << 8)) / 1023UL;
  uint8_t segment = scaled >> 8;
  uint8_t pos = scaled & 0xFF;
  if (segment >= maxShape) {
    return {maxShape, maxShape, 0};
  }
  if (pos < kShapeHold) {
    return {segment, segment, 0};
  }
  if (pos >= 256 - kShapeHold) {
    return {(uint8_t)(segment + 1), (uint8_t)(segment + 1), 0};
  }
  uint8_t blend = ((uint16_t)(pos - kShapeHold) * 255) / (256 - 2 * kShapeHold);
  return {segment, (uint8_t)(segment + 1), blend};
}

// Linear interpolation between two 8-bit samples, weight 0..255 towards b.
inline uint8_t lerp8(uint8_t a, uint8_t b, uint8_t weight) {
  return ((uint16_t)a * (uint16_t)(256 - weight) + (uint16_t)b * weight) >> 8;
}

// 16-bit xorshift (7, 9, 8) for the sample & hold shape; state never 0.
inline uint16_t nextRandom(uint16_t x) {
  x ^= x << 7;
  x ^= x >> 9;
  x ^= x << 8;
  return x;
}

} // namespace LfoMath
