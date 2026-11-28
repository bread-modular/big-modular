#pragma once

// CPX4 TUNE knob filter (this module, not BM). Pico-free, shared with the
// host test tools/sim_cpx4.cpp.
//
// The app reads each knob every 2 ms: one settling conversion after the
// input switch (discarded), then CONVERSIONS conversions. Per read:
//   trimmed mean (the TRIM lowest and TRIM highest dropped, so one stray
//   conversion can't move the pitch) -> one-pole SMOOTH -> backlash: the
//   knob position follows the smoothed reading with +-BACKLASH counts of
//   play, like a gear with a little slack.
// At rest the ADC noise (single conversions +-3 counts on the board,
// 2026-11-28) stays inside the play, so the TUNE doesn't move at all; a
// turned knob moves it continuously (by the reading's change), never in
// re-centring steps. The old filter (4 conversions averaged, re-centred on
// the reading after every 0.75-count change) re-tuned a resting voice 3..8
// times a second, up to 15 cents a step on P1 (1715 counts for 7 octaves).

#include <stdint.h>

namespace cpx4_knob {

constexpr int CONVERSIONS = 8;
constexpr int TRIM = 2;
constexpr float SMOOTH = 0.15f;    // one-pole per 2 ms read (~12 ms)
constexpr float BACKLASH = 1.5f;   // ADC counts of play each way

// Trimmed mean of CONVERSIONS raw conversions (sorts `v` in place).
inline float trimmedMean(uint16_t* v) {
    for (int i = 1; i < CONVERSIONS; i++) {
        uint16_t x = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > x) {
            v[j + 1] = v[j];
            j--;
        }
        v[j + 1] = x;
    }
    uint32_t sum = 0;
    for (int i = TRIM; i < CONVERSIONS - TRIM; i++) sum += v[i];
    return sum / (float)(CONVERSIONS - 2 * TRIM);
}

class KnobFilter {
    public:
        // One read (trimmed mean, ADC counts) -> knob position (ADC counts).
        // The first read after reset() starts there.
        float update(float reading) {
            if (!started) {
                started = true;
                smooth = position = reading;
                return position;
            }
            smooth += SMOOTH * (reading - smooth);
            if (smooth > position + BACKLASH) {
                position = smooth - BACKLASH;
            } else if (smooth < position - BACKLASH) {
                position = smooth + BACKLASH;
            }
            return position;
        }
        void reset() { started = false; }
        float getPosition() const { return position; }
        float getSmooth() const { return smooth; }

    private:
        bool started = false;
        float smooth = 0.0f;
        float position = 0.0f;
};

}  // namespace cpx4_knob
