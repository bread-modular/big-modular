// Host tests for src/osc3_logic.h.
#include <cstdio>
#include <cstdlib>
#include "osc3_logic.h"

static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); failures++; } } while (0)

int main() {
    using namespace osc3;
    static int16_t sine[SINE_SIZE];
    fillSine(sine);

    // Knob range: 20 Hz .. 2560 Hz, exponential (one octave per 1/7 turn).
    CHECK(fabsf(knobHz(0) - 20.0f) < 0.01f);
    CHECK(fabsf(knobHz(4095) - 2560.0f) < 0.5f);
    CHECK(fabsf(knobHz(5000) - 2560.0f) < 0.5f);
    CHECK(fabsf(knobHz(585) / knobHz(0) - 2.0f) < 0.01f);

    // Phase increment: 1 kHz -> 1000 cycles per 48000 samples.
    uint32_t inc = phaseInc(1000.0f), phase = 0, wraps = 0;
    for (uint32_t i = 0; i < SAMPLE_RATE_HZ; i++) {
        uint32_t next = phase + inc;
        if (next < phase) wraps++;
        phase = next;
    }
    CHECK(wraps >= 999 && wraps <= 1001);

    // Every waveform stays inside +-32767 and the mix inside the DAC window.
    uint16_t lo = 4095, hi = 0;
    for (int w = 0; w < WAVE_COUNT; w++) {
        for (uint64_t p = 0; p < 0x100000000ull; p += 0x00100001ull) {
            int32_t s = wave((Wave)w, (uint32_t)p, sine);
            CHECK(s >= -32767 && s <= 32767);
            uint16_t d = mixToDac(s, s, s);
            if (d < lo) lo = d;
            if (d > hi) hi = d;
        }
    }
    CHECK(lo >= DAC_MID - DAC_SWING && hi <= DAC_MID + DAC_SWING);
    CHECK(mixToDac(0, 0, 0) == DAC_MID);
    CHECK(mixToDac(32767, 32767, 32767) == DAC_MID + DAC_SWING);

    // Knob filter: starts at the first value, settles on a step.
    KnobFilter f;
    CHECK(f.update(1000) == 1000);
    uint16_t v = 0;
    for (int i = 0; i < 200; i++) v = f.update(3000);
    CHECK(v >= 2990 && v <= 3000);
    for (int i = 0; i < 200; i++) v = f.update(0);
    CHECK(v <= 10);

    std::printf(failures ? "%d failure(s)\n" : "all tests passed\n", failures);
    return failures ? 1 : 0;
}
