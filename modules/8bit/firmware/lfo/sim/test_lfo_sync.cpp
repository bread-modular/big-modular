// ============================================================================
// Host self-tests for the 8bit lfo MIDI clock sync (lfo/LfoSync.h) — plain
// c++, NO hardware and NO arduino-cli.
//
// Covers:
//   1. RATE zones: knob CCW = 8 bars, CW = 1/16, one step per zone, hysteresis
//   1b. CV in steps: 1 V = one length step, borders at ±0.5, ±1.5 V, 0 V =
//      the knob's length, hysteresis, clamped to 8 bars .. 1/16
//   2. Tick phases/budgets: a cycle's budgets add up to one whole cycle and
//      never wrap before the downbeat
//   3. Increment maths against double precision
//   4. A 40 kHz sample loop as in the ISR, fed MIDI clock with loop() latency
//      jitter, for every length and several tempos (and a tempo change): the
//      cycle starts on the clock's downbeat (MIDI Start = bar 1), runs one
//      cycle per length, the phase never steps back inside a cycle and jumps
//      at most a little at a tick
//
// Run via ./sim.sh
// ============================================================================

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "LfoSync.h"

using namespace LfoSync;

static int failures = 0;
static int checks = 0;

#define CHECK(cond, ...)                         \
  do {                                           \
    checks++;                                    \
    if (!(cond)) {                               \
      failures++;                                \
      printf("FAIL %s:%d: ", __FILE__, __LINE__); \
      printf(__VA_ARGS__);                       \
      printf("\n");                              \
    }                                            \
  } while (0)

static const double kRate = 40000.0;

static void testZones() {
  CHECK(divisionFromKnob(0, 0xFF) == 0, "knob CCW not 8 bars");
  CHECK(divisionFromKnob(1023, 0xFF) == 7, "knob CW not 1/16");
  CHECK(divisionTicks(0) == 768 && divisionTicks(3) == 96 && divisionTicks(7) == 6, "ticks table");
  for (uint8_t z = 0; z < kDivisionCount; z++) {
    uint16_t centre = z * kZoneCounts + kZoneCounts / 2;
    CHECK(divisionFromKnob(centre, 0xFF) == z, "zone %u centre", z);
    // Resting next to a border keeps the current zone from either side.
    if (z > 0) {
      uint16_t border = z * kZoneCounts;
      CHECK(divisionFromKnob(border + kKnobHysteresis - 1, z - 1) == z - 1, "zone %u up hysteresis", z);
      CHECK(divisionFromKnob(border + kKnobHysteresis, z - 1) == z, "zone %u up step", z);
      CHECK(divisionFromKnob(border - kKnobHysteresis, z) == z, "zone %u down hysteresis", z);
      CHECK(divisionFromKnob(border - kKnobHysteresis - 1, z) == z - 1, "zone %u down step", z);
    }
  }
  // Sweeping up and down: never moves the wrong way, never skips a zone.
  uint8_t d = 0xFF;
  uint8_t last = 0;
  for (int k = 0; k <= 1023; k++) {
    d = divisionFromKnob(k, d);
    CHECK(d >= last && d - last <= 1, "sweep up at %d", k);
    last = d;
  }
  for (int k = 1023; k >= 0; k--) {
    d = divisionFromKnob(k, d);
    CHECK(d <= last && last - d <= 1, "sweep down at %d", k);
    last = d;
  }
  CHECK(d == 0, "sweep down does not end at 8 bars");
}

// ADC reading for a CV in voltage (LfoMath scale).
static uint16_t cvCounts(double volts) {
  double c = LfoMath::kCvInZero + volts * 92.75;
  return c < 0 ? 0 : c > 1023 ? 1023 : (uint16_t)lround(c);
}

static void testCvSteps() {
  CHECK(cvSteps(cvCounts(0), kNoCvSteps) == 0, "0 V not 0 steps");
  for (int v = -5; v <= 5; v++) {
    CHECK(cvSteps(cvCounts(v), kNoCvSteps) == v, "%d V not %d steps", v, v);
    CHECK(cvSteps(cvCounts(v + 0.4), kNoCvSteps) == v, "%d.4 V", v);
    CHECK(cvSteps(cvCounts(v - 0.4), kNoCvSteps) == v, "%d-0.4 V", v);
  }
  CHECK(cvSteps(0, kNoCvSteps) == -5 && cvSteps(1023, kNoCvSteps) == 6, "ADC ends not -5 / +6 steps");
  // 0 V and small wobble never move the knob's length.
  int8_t s = kNoCvSteps;
  for (int i = 0; i < 1000; i++) {
    s = cvSteps(cvCounts(0.35 * sin(i * 0.05)), s);
    CHECK(s == 0, "±0.35 V wobble moved the length");
  }
  // Resting on a border keeps the current step from either side.
  for (int v = -4; v <= 5; v++) {
    uint16_t border = cvCounts(v - 0.5);
    CHECK(cvSteps(border, v - 1) == v - 1, "border %d-0.5 V up hysteresis", v);
    CHECK(cvSteps(border, v) == v, "border %d-0.5 V down hysteresis", v);
    CHECK(cvSteps(cvCounts(v - 0.5 + 0.15), v - 1) == v, "%d-0.35 V up step", v);
    CHECK(cvSteps(cvCounts(v - 0.5 - 0.15), v) == v - 1, "%d-0.65 V down step", v);
  }
  // Sweeps: monotonic, one step at a time.
  s = kNoCvSteps;
  for (int c = 0; c <= 1023; c++) {
    int8_t n = cvSteps(c, s);
    CHECK(s == kNoCvSteps || n == s || n == s + 1, "up sweep at %d", c);
    s = n;
  }
  for (int c = 1023; c >= 0; c--) {
    int8_t n = cvSteps(c, s);
    CHECK(n == s || n == s - 1, "down sweep at %d", c);
    s = n;
  }
  // Knob division + steps, clamped.
  CHECK(applyCvSteps(3, 0) == 3 && applyCvSteps(3, 2) == 5 && applyCvSteps(3, -2) == 1, "apply steps");
  CHECK(applyCvSteps(6, 5) == 7 && applyCvSteps(1, -5) == 0, "apply steps clamp");
  CHECK(applyCvSteps(4, kNoCvSteps) == 4, "no CV reading changes the length");
}

static void testBudgets() {
  for (uint8_t z = 0; z < kDivisionCount; z++) {
    uint16_t ticks = divisionTicks(z);
    uint64_t total = 0;
    bool ok = true;
    for (uint16_t c = 0; c < ticks; c++) {
      uint64_t end = (uint64_t)tickPhase(c, ticks) + tickBudget(c, ticks);
      ok = ok && end <= 0xFFFFFFFFULL;
      total += tickBudget(c, ticks) + 1;
    }
    CHECK(ok, "%u ticks: a budget wraps", ticks);
    CHECK(total == 0x100000000ULL, "%u ticks: budgets add to %llu", ticks, (unsigned long long)total);
    CHECK(tickPhase(0, ticks) == 0 && tickPhase(ticks, ticks) == 0 && tickPhase(767, ticks) == tickPhase(ticks - 1, ticks),
          "%u ticks: phase of the count", ticks);
  }
}

static void testIncrement() {
  for (uint8_t z = 0; z < kDivisionCount; z++) {
    for (int samples = 300; samples <= 12000; samples += 37) {
      uint32_t inc = syncIncrement(tickStep(divisionTicks(z)), (uint32_t)samples << kPeriodFrac);
      double want = 4294967296.0 / divisionTicks(z) / samples;
      CHECK(fabs(inc - want) <= 1.0 + want * 1e-6, "inc %u ticks / %d samples: %u want %.1f", divisionTicks(z), samples, inc, want);
    }
  }
}

// ISR + loop() model. Clock bytes arrive at exact times; loop() handles them
// up to `maxLatency` samples later (MIDI.update() once per loop pass).
struct Model {
  Clock clock;
  uint16_t sampleClock = 0;
  uint32_t phase = 0, lastPhase = 0, increment = 0, budget = 0;
  bool synced = false;
  uint8_t division = 0xFF;

  void onTick(uint16_t knob) {
    if (!clock.tick(sampleClock, true)) {
      return;
    }
    division = divisionFromKnob(knob, division);
    uint16_t ticks = divisionTicks(division);
    phase = tickPhase(clock.count, ticks);
    budget = tickBudget(clock.count, ticks);
    increment = syncIncrement(tickStep(ticks), clock.periodQ4);
    synced = true;
  }

  // One ISR sample; true = new cycle (as the firmware's S&H check).
  bool sample() {
    sampleClock++;
    phase = synced ? advance(phase, increment, budget) : phase + increment;
    bool wrapped = phase < lastPhase;
    lastPhase = phase;
    return wrapped;
  }
};

struct RunResult {
  int cycles = 0;
  double worstStartError = 0;  // samples between a downbeat tick and the cycle start
  double worstJump = 0;        // largest phase step at a tick, in ticks
  bool steppedBack = false;
};

// Run `bars` bars at `bpm` (optionally `bpm2` for the second half) with the
// knob at `knob`; MIDI Start first, then 24 PPQN clock.
static RunResult run(double bpm, double bpm2, uint16_t knob, int bars, int maxLatency, unsigned seed) {
  srand(seed);
  Model m;
  m.clock.start();
  RunResult r;
  uint16_t ticksPerCycle = divisionTicks(divisionFromKnob(knob, 0xFF));
  int totalTicks = bars * kTicksPerBar;
  double t = 0;  // sample time of the next clock byte
  long n = 0;
  int tick = 0;
  long pendingAt = -1;
  long lastDownbeatHandled = -1;
  while (tick < totalTicks || pendingAt >= 0) {
    if (pendingAt < 0 && tick < totalTicks && n >= (long)t) {
      pendingAt = n + (maxLatency ? rand() % (maxLatency + 1) : 0);
      double tempo = (tick < totalTicks / 2) ? bpm : bpm2;
      t += kRate * 60.0 / tempo / 24.0;
      tick++;
    }
    if (pendingAt >= 0 && n >= pendingAt) {
      uint32_t before = m.phase;
      bool wasSynced = m.synced;
      m.onTick(knob);
      pendingAt = -1;
      if (wasSynced && m.clock.count % ticksPerCycle != 0) {
        double jump = ((double)m.phase - before) / (4294967296.0 / ticksPerCycle);
        if (jump < -1e-9) {
          r.steppedBack = true;
        }
        if (tick > 2 * 24 && fabs(jump) > r.worstJump) {  // after the first beats
          r.worstJump = fabs(jump);
        }
      }
      if (m.synced && m.clock.count % ticksPerCycle == 0) {
        lastDownbeatHandled = n;
      }
    }
    if (m.sample()) {
      r.cycles++;
      if (lastDownbeatHandled >= 0) {
        double err = (double)(n - lastDownbeatHandled);
        if (err > r.worstStartError) {
          r.worstStartError = err;
        }
      }
    }
    n++;
  }
  return r;
}

static void testRun() {
  const double tempos[] = {60, 90, 120, 133, 174, 240};
  for (uint8_t z = 0; z < kDivisionCount; z++) {
    uint16_t knob = z * kZoneCounts + kZoneCounts / 2;
    uint16_t ticks = divisionTicks(z);
    int bars = (ticks / kTicksPerBar) * 2 + 2;  // at least two whole cycles
    if (bars < 4) {
      bars = 4;
    }
    for (double bpm : tempos) {
      RunResult r = run(bpm, bpm, knob, bars, 8, 1 + z);
      int want = (bars * kTicksPerBar - 1) / ticks;  // downbeats after the first
      // The lock needs two ticks, so the first downbeat (Start) is not a
      // cycle start; every later downbeat is one.
      CHECK(r.cycles == want, "%u ticks @ %.0f BPM: %d cycles, want %d", ticks, bpm, r.cycles, want);
      CHECK(r.worstStartError <= 1, "%u ticks @ %.0f BPM: cycle start %.0f samples after the downbeat", ticks, bpm, r.worstStartError);
      CHECK(!r.steppedBack, "%u ticks @ %.0f BPM: phase steps back at a tick", ticks, bpm);
      CHECK(r.worstJump < 0.03, "%u ticks @ %.0f BPM: phase jumps %.3f ticks at a tick", ticks, bpm, r.worstJump);
    }
  }
  // Tempo change mid-run (120 -> 90 and 120 -> 150): still on the downbeats.
  const double changes[] = {90.0, 150.0};
  for (double bpm2 : changes) {
    RunResult r = run(120, bpm2, 5 * kZoneCounts + 64, 8, 8, 7);
    CHECK(r.worstStartError <= 1 && !r.steppedBack, "tempo 120 -> %.0f: start error %.0f", bpm2, r.worstStartError);
    printf("   1/4 note, 120 -> %.0f BPM: worst jump at a tick %.3f ticks\n", bpm2, r.worstJump);
  }
  RunResult r = run(120, 120, 7 * kZoneCounts + 64, 4, 8, 3);
  printf("   1/16 @ 120 BPM, 0..8 samples loop latency: %d cycles, worst jump %.4f ticks\n", r.cycles, r.worstJump);
}

static void testClockState() {
  Clock c;
  CHECK(!c.tick(100, true), "first tick locks without a period");
  CHECK(c.count == 0, "first clock after power-up is not count 0");
  CHECK(c.tick(933, true) && c.periodQ4 == (833u << kPeriodFrac), "second tick period");
  c.start();
  c.tick(1766, true);
  CHECK(c.count == 0, "clock after Start is not the downbeat");
  c.stop();
  CHECK(!c.tick(5000, false), "tick after a timeout locks at once");
  CHECK(c.tick(5833, true), "second tick after a timeout does not lock");
  // 16-bit sample counter wrap.
  Clock w;
  w.tick(65000, true);
  w.tick((uint16_t)(65000 + 833), true);
  CHECK(w.periodQ4 == (833u << kPeriodFrac), "period across the counter wrap");
}

int main() {
  printf("== RATE zones\n");
  testZones();
  printf("== CV steps\n");
  testCvSteps();
  printf("== tick budgets\n");
  testBudgets();
  printf("== increment\n");
  testIncrement();
  printf("== clock state\n");
  testClockState();
  printf("== clocked runs\n");
  testRun();
  printf("%d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
