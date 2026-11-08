// ============================================================================
// Host self-tests for the 8bit lfo rate/shape maths (lfo/LfoMath.h) — plain
// c++, NO hardware and NO arduino-cli.
//
// Covers:
//   1. Rate: knob CCW = 0.01 Hz, CW ~ 40.6 Hz, exponential (equal knob steps =
//      equal ratios), monotonic over the whole travel
//   2. CV in: unpatched/deadband = knob only, ~1 V/oct both ways, +5 V lifts
//      the knob top into audio rate, clamps (floor, 2 kHz cap)
//   3. 2^x mantissa: < 0.05 % error against exp2 over every pitch
//   4. WAVE: pure shapes at the ends of the travel and in a hold zone around
//      each detent, crossfade monotonic between neighbours
//   5. lerp8 end points, xorshift never reaches 0 and covers the byte range
//
// Run via ./sim.sh
// ============================================================================

#include <math.h>
#include <stdio.h>

#include "LfoMath.h"

using namespace LfoMath;

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

static double hz(uint16_t knob, uint16_t cvIn) {
  return incrementToMilliHz(phaseIncrement(ratePitch(knob, cvIn))) / 1000.0;
}

// Exact frequency of an increment (incrementToMilliHz truncates to 1 mHz).
static double exactHz(uint32_t inc) { return inc * (double)kSampleRateHz / 4294967296.0; }

// CV in ADC count for a jack voltage (docs/research.md §3.2b, ideal parts).
static uint16_t cvCounts(double volts) {
  double v = 0.4529 * volts + 2.487;
  int c = (int)lround(v * 1024.0 / 5.0);
  return c < 0 ? 0 : (c > 1023 ? 1023 : c);
}

static void testRate() {
  double lo = exactHz(phaseIncrement(ratePitch(0, kCvInZero)));
  double hi = exactHz(phaseIncrement(ratePitch(1023, kCvInZero)));
  printf("   knob CCW %.4f Hz (%.0f s), CW %.2f Hz\n", lo, 1.0 / lo, hi);
  CHECK(fabs(lo - 0.01) < 0.0001, "knob CCW %.5f Hz, want 0.01", lo);
  CHECK(hi > 40.0 && hi < 41.0, "knob CW %.3f Hz, want ~40.6", hi);

  double mid = exactHz(phaseIncrement(ratePitch(512, kCvInZero)));
  CHECK(fabs(mid - sqrt(lo * hi)) / mid < 0.01, "knob centre %.3f Hz not the geometric mean", mid);

  uint32_t last = 0;
  int notRising = 0;
  for (uint16_t k = 0; k <= 1023; k++) {
    uint32_t inc = phaseIncrement(ratePitch(k, kCvInZero));
    notRising += !(inc > last);
    last = inc;
  }
  CHECK(notRising == 0, "rate not rising at %d knob steps", notRising);
}

static void testCv() {
  for (int16_t d = -kCvInDeadband; d <= kCvInDeadband; d++) {
    CHECK(ratePitch(400, kCvInZero + d) == ratePitch(400, kCvInZero), "deadband offset %d moves the rate", d);
  }
  // ~1 V/oct around the knob centre.
  double base = hz(512, cvCounts(0));
  for (int v = -5; v <= 5; v++) {
    double f = hz(512, cvCounts(v));
    double octaves = log2(f / base);
    CHECK(fabs(octaves - v) < 0.05, "%+d V -> %.3f oct, want %d", v, octaves, v);
  }
  double top = hz(1023, cvCounts(5.0));
  double topMax = hz(1023, 1023);
  printf("   knob CW + 5 V %.0f Hz, + full CV %.0f Hz\n", top, topMax);
  CHECK(top > 1000.0, "knob CW + 5 V only %.1f Hz, want audio rate", top);
  CHECK(topMax <= 2000.0, "cap broken: %.1f Hz", topMax);
  CHECK(phaseIncrement(kPitchMax) == kMaxIncrement, "2 kHz cap not hit at the top pitch");

  double floorHz = exactHz(phaseIncrement(ratePitch(0, 0)));
  printf("   knob CCW + full negative CV %.6f Hz (%.0f min)\n", floorHz, 1.0 / floorHz / 60.0);
  CHECK(phaseIncrement(ratePitch(0, 0)) > 0, "floor rate stops the LFO");
  CHECK(ratePitch(0, 0) >= 0, "pitch below 0");
}

static void testExp() {
  for (int16_t p = 0; p <= kPitchMax; p++) {
    double want = kFloorIncrementQ8 / 256.0 * exp2(p / 256.0);
    if (want > kMaxIncrement || want < 2000.0) {
      continue;  // capped / integer-step dominated
    }
    double err = fabs(phaseIncrement(p) - want) / want;
    if (err > 0.0005) {
      CHECK(false, "pitch %d increment error %.5f", p, err);
      return;
    }
  }
  checks++;
}

static void testShapes() {
  ShapeMix m0 = shapeMix(0);
  CHECK(m0.a == Sine && m0.b == Sine && m0.blend == 0, "knob 0 not pure sine");
  ShapeMix mTop = shapeMix(1023);
  CHECK(mTop.a == Random && mTop.b == Random, "knob 1023 not pure random");

  // Each inner detent holds pure over a stretch of counts.
  for (uint8_t s = 1; s + 1 < kShapeCount; s++) {
    uint16_t centre = (uint16_t)lround(s * 1023.0 / (kShapeCount - 1));
    int pure = 0;
    for (int k = centre - 60; k <= centre + 60; k++) {
      ShapeMix m = shapeMix(k);
      if (m.a == s && m.b == s) {
        pure++;
      }
    }
    CHECK(pure >= 55, "shape %u holds pure for only %d counts", s, pure);
  }

  // Walking the knob: shape weight only moves forward, no jumps.
  double last = 0.0;
  for (uint16_t k = 0; k <= 1023; k++) {
    ShapeMix m = shapeMix(k);
    double pos = m.a + (m.b != m.a ? m.blend / 256.0 : 0.0);
    CHECK(pos + 1e-9 >= last, "shape position goes back at knob %u", k);
    CHECK(pos - last < 0.05, "shape jumps at knob %u (%.3f -> %.3f)", k, last, pos);
    CHECK(m.b == m.a || m.b == m.a + 1, "non-neighbour mix at knob %u", k);
    last = pos;
  }
}

static void testHelpers() {
  CHECK(lerp8(10, 200, 0) == 10, "lerp8 w=0");
  CHECK(lerp8(255, 255, 128) == 255, "lerp8 keeps 255");
  CHECK(lerp8(0, 255, 255) == 254, "lerp8 w=255");
  CHECK(lerp8(0, 255, 128) == 127, "lerp8 half");

  uint16_t x = 0xACE1;
  bool seen[256] = {false};
  bool zero = false;
  for (long i = 0; i < 65535 && !zero; i++) {
    x = nextRandom(x);
    zero = (x == 0);
    seen[x >> 8] = true;
  }
  CHECK(!zero, "xorshift reached 0");
  int distinct = 0;
  for (int i = 0; i < 256; i++) {
    distinct += seen[i];
  }
  CHECK(distinct == 256, "S&H covers %d of 256 values", distinct);
  CHECK(x == 0xACE1, "xorshift period is not 65535");
}

int main() {
  printf("== rate\n");
  testRate();
  printf("== CV in\n");
  testCv();
  printf("== 2^x\n");
  testExp();
  printf("== WAVE\n");
  testShapes();
  printf("== helpers\n");
  testHelpers();
  printf("%d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
