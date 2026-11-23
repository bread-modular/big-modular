#pragma once

// MIDI clock sync for the 8bit LFO, kept free of AVR registers so the host
// simulator (../sim) runs the same code.
//
// While MIDI clock (24 PPQN) arrives, P1 RATE picks a musical cycle length
// instead of a free rate, 8 bars (CCW) .. 1/16 note (CW), one octave per step:
//
//   index    0       1       2       3      4      5      6      7
//   cycle    8 bars  4 bars  2 bars  1 bar  1/2    1/4    1/8    1/16
//   ticks    768     384     192     96     48     24     12     6
//
// The phase is locked to the clock count, not just the tempo: on every clock
// tick it is set to (tick in the cycle) / (cycle ticks), and between ticks it
// runs at the measured tick period but never past the next tick's phase (if a
// tick is late the wave waits instead of overshooting). MIDI Start makes the
// next clock the downbeat, so cycles start on bar 1; without a Start the count
// starts at the first clock seen. No clock for kClockTimeoutMs = free-running
// rate again. CV in moves the length by whole steps (1 V = one step, see
// cvSteps()).

#include <stdint.h>

#include "LfoMath.h"

namespace LfoSync {

constexpr uint8_t kDivisionCount = 8;
constexpr uint16_t kTicksPerBar = 96;          // 4/4, 24 PPQN
constexpr uint16_t kCountWrap = 8 * kTicksPerBar;  // 768: every cycle length divides it
constexpr uint16_t kClockTimeoutMs = 300;      // > one tick at 10 BPM (250 ms)

// Cycle length in clock ticks for division index 0 (8 bars) .. 7 (1/16).
inline uint16_t divisionTicks(uint8_t index) {
  return kCountWrap >> index;
}

// RATE knob zones: 8 equal zones of 128 counts; a change needs the knob
// kKnobHysteresis counts into the neighbouring zone, so a knob resting on a
// border doesn't flicker between two lengths.
constexpr uint16_t kZoneCounts = 128;
constexpr uint8_t kKnobHysteresis = 12;

inline uint8_t divisionFromKnob(uint16_t knob, uint8_t current) {
  uint8_t zone = knob / kZoneCounts;
  if (zone >= kDivisionCount) {
    zone = kDivisionCount - 1;
  }
  if (current >= kDivisionCount || zone == current) {
    return zone;
  }
  uint16_t zoneStart = (uint16_t)zone * kZoneCounts;
  if (zone > current) {
    return (knob >= zoneStart + kKnobHysteresis) ? zone : current;
  }
  return (knob + kKnobHysteresis < zoneStart + kZoneCounts) ? zone : current;
}

// CV in while synced: whole length steps, 1 V = one step, + = shorter
// (towards 1/16), as the free-running CV makes it faster. Steps change at
// ±0.5, ±1.5, .. V, so 0 V always gives the knob's length; a change needs the
// CV kCvHysteresis counts past the border. ADC scale as LfoMath (0 V ~ 509,
// 92.75 counts/V; the ADC ends are -5 / +6 steps).
constexpr int8_t kNoCvSteps = -128;            // no reading yet
constexpr int16_t kCvCountsPerVoltQ2 = 371;    // 92.75 counts/V, Q2
constexpr int16_t kCvHysteresis = 9;           // ~0.1 V

inline int8_t roundCvSteps(int16_t offset) {
  int16_t q2 = offset * 4;
  int16_t half = kCvCountsPerVoltQ2 / 2;
  return (q2 >= 0) ? (int8_t)((q2 + half) / kCvCountsPerVoltQ2)
                   : (int8_t)-((half - q2) / kCvCountsPerVoltQ2);
}

inline int8_t cvSteps(uint16_t cvIn, int8_t current) {
  int16_t offset = (int16_t)cvIn - LfoMath::kCvInZero;
  int8_t steps = roundCvSteps(offset);
  if (current != kNoCvSteps && steps != current) {
    steps = roundCvSteps(steps > current ? offset - kCvHysteresis : offset + kCvHysteresis);
  }
  return steps;
}

// Knob division + CV steps, clamped to 8 bars .. 1/16.
inline uint8_t applyCvSteps(uint8_t division, int8_t steps) {
  if (steps == kNoCvSteps) {
    return division;
  }
  int16_t d = (int16_t)division + steps;
  if (d < 0) {
    return 0;
  }
  return (d >= kDivisionCount) ? kDivisionCount - 1 : (uint8_t)d;
}

// Phase step of one clock tick in a cycle of `ticks` ticks (2^32 / ticks).
inline uint32_t tickStep(uint16_t ticks) {
  return 0xFFFFFFFFUL / ticks + 1;
}

// Phase at the start of tick `count` (0..kCountWrap-1) in a cycle of `ticks`.
inline uint32_t tickPhase(uint16_t count, uint16_t ticks) {
  return (uint32_t)(count % ticks) * tickStep(ticks);
}

// Phase the wave may run from the start of tick `count` until the next tick:
// up to one count below the next tick's phase, so the last tick of a cycle
// stops at 0xFFFFFFFF and the cycle only wraps when the next downbeat sets 0.
inline uint32_t tickBudget(uint16_t count, uint16_t ticks) {
  uint16_t next = (count % ticks) + 1;
  uint32_t nextPhase = (next >= ticks) ? 0 : (uint32_t)next * tickStep(ticks);
  return nextPhase - tickPhase(count, ticks) - 1;
}

// Tick period smoothing: Q4 samples, 1/4 of each new period.
constexpr uint8_t kPeriodFrac = 4;

inline uint32_t smoothPeriodQ4(uint32_t periodQ4, uint16_t samples) {
  uint32_t sampleQ4 = (uint32_t)samples << kPeriodFrac;
  if (periodQ4 == 0) {
    return sampleQ4;
  }
  return periodQ4 - (periodQ4 >> 2) + (sampleQ4 >> 2);
}

// Per-sample phase increment for a tick step spread over periodQ4 samples
// (Q4), 32-bit maths only: step * 16 / periodQ4 by quotient + remainder.
inline uint32_t syncIncrement(uint32_t step, uint32_t periodQ4) {
  if (periodQ4 == 0) {
    return 0;
  }
  uint32_t q = step / periodQ4;
  uint32_t r = step % periodQ4;
  // r < periodQ4 <= 2^28 (a 300 ms tick is 12000 samples = 192000 Q4), so r * 16 fits.
  return (q << kPeriodFrac) + ((r << kPeriodFrac) / periodQ4);
}

// Clock state, updated from loop() on each MIDI clock / Start. On every locked
// tick the firmware hands the ISR the tick's phase, budget and increment.
struct Clock {
  uint16_t count = kCountWrap - 1;  // clock count of the last tick, 0 = downbeat
  uint16_t lastTickSample = 0;      // sample counter at the last tick
  uint32_t periodQ4 = 0;            // smoothed tick period, 0 = not measured yet
  bool running = false;             // a previous tick within the timeout

  // MIDI Start: the next clock is the downbeat.
  void start() {
    count = kCountWrap - 1;
  }

  // A MIDI clock at sample `now` (the ISR's free-running 16-bit counter).
  // `fresh` = the previous tick is within the timeout (else the period is
  // re-measured from this tick). Returns true once the clock is locked
  // (two ticks seen), so the caller can apply the phase.
  bool tick(uint16_t now, bool fresh) {
    count = (count + 1) % kCountWrap;
    if (fresh && running) {
      periodQ4 = smoothPeriodQ4(periodQ4, (uint16_t)(now - lastTickSample));
    } else {
      periodQ4 = 0;
    }
    running = true;
    lastTickSample = now;
    return periodQ4 != 0;
  }

  void stop() {
    running = false;
    periodQ4 = 0;
  }
};

// One synced sample in the ISR: advance by `increment`, but not past the
// budget left until the next tick's phase.
inline uint32_t advance(uint32_t phase, uint32_t increment, uint32_t &budget) {
  if (increment > budget) {
    increment = budget;
  }
  budget -= increment;
  return phase + increment;
}

} // namespace LfoSync
