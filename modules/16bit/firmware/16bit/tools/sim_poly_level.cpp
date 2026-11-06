// Host test of the polysynth output level (includes/audio/apps/polysynth/
// poly_level.h): one voice level, chord gain, release recovery, limiter
// ceiling. Run through ../test.sh.

#include <cmath>
#include <cstdio>

#include "audio/apps/polysynth/poly_level.h"

static int checks = 0;
static int failures = 0;

#define CHECK(cond, ...)                                  \
    do {                                                  \
        checks++;                                         \
        if (!(cond)) {                                    \
            failures++;                                   \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);   \
            printf(__VA_ARGS__);                          \
            printf("\n");                                 \
        }                                                 \
    } while (0)

static const float SR = 44100.0f;

// `voices` in-phase full-velocity saws (the worst case: peaks add up) for
// `seconds`; returns the output peak of the last half.
static float render(PolyLevel& level, int voices, float seconds, float hz = 110.0f) {
    float peak = 0.0f;
    int n = (int)(seconds * SR);
    for (int i = 0; i < n; i++) {
        float saw = 2.0f * fmodf(i * hz / SR, 1.0f) - 1.0f;
        float dry = voices * saw * level.gain((float)voices);
        float left = dry;
        level.limit(left, dry);
        CHECK(fabsf(left) <= 1.0f && fabsf(dry) <= 1.0f, "%d voices clip %f", voices, left);
        if (i > n / 2) peak = fmaxf(peak, fabsf(left));
    }
    return peak;
}

int main() {
    PolyLevel level;
    level.init(SR);

    // One voice: VOICE_GAIN, untouched by the limiter.
    float one = render(level, 1, 0.5f);
    CHECK(fabsf(one - PolyLevel::VOICE_GAIN) < 0.01f, "one voice peak %f", one);
    CHECK(fabsf(level.getPolyGain() - PolyLevel::VOICE_GAIN) < 1e-6f, "one voice gain");

    // Chords: turned down by L^0.8, the limiter keeps 9 in-phase voices
    // under LIMIT (soft clip above).
    for (int v = 2; v <= 9; v++) {
        level.init(SR);
        float peak = render(level, v, 0.5f);
        float expect = PolyLevel::VOICE_GAIN / powf((float)v, PolyLevel::POLY_EXP);
        CHECK(fabsf(level.getPolyGain() - expect) < 1e-4f, "%d voices gain %f", v, level.getPolyGain());
        CHECK(peak <= PolyLevel::LIMIT + 0.01f, "%d voices peak %f", v, peak);
        printf("%d voices: gain %.3f, peak %.3f\n", v, level.getPolyGain(), peak);
    }

    // Release: from 4 notes to 1 the gain recovers over ~300 ms, not at once
    // (no pumping of the held note).
    level.init(SR);
    render(level, 4, 0.5f);
    float g4 = level.getPolyGain();
    for (int i = 0; i < (int)(0.03f * SR); i++) level.gain(1.0f);
    CHECK(level.getPolyGain() < g4 * 1.25f, "gain jumped back %f -> %f", g4, level.getPolyGain());
    for (int i = 0; i < (int)(2.0f * SR); i++) level.gain(1.0f);
    CHECK(fabsf(level.getPolyGain() - PolyLevel::VOICE_GAIN) < 0.01f, "gain did not recover %f",
          level.getPolyGain());

    // New notes: the gain drops within one control block.
    level.init(SR);
    level.gain(1.0f);
    for (uint32_t i = 0; i < PolyLevel::CONTROL_BLOCK; i++) level.gain(3.0f);
    CHECK(level.getPolyGain() < PolyLevel::VOICE_GAIN / 2.0f, "gain slow on new notes %f",
          level.getPolyGain());

    // Limiter: a 2.0 overload settles to LIMIT; silence stays silent.
    level.init(SR);
    float peak = 0.0f;
    for (int i = 0; i < (int)SR; i++) {
        float l = (i & 1) ? 2.0f : -2.0f, r = 0.0f;
        level.limit(l, r);
        CHECK(fabsf(l) <= 1.0f, "limiter output %f", l);
        if (i > SR / 2) peak = fmaxf(peak, fabsf(l));
    }
    CHECK(fabsf(peak - PolyLevel::LIMIT) < 0.01f, "limited peak %f", peak);
    level.init(SR);
    for (int i = 0; i < 1000; i++) {
        float l = 0.0f, r = 0.0f;
        level.limit(l, r);
        CHECK(l == 0.0f && r == 0.0f, "silence");
    }

    printf("sim_poly_level: %d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
