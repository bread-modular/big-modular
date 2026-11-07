// Host self-tests for the 16bit RAM-only P1..P4 / MCC motion recorder shared
// by the sampler, fxrack, polysynth and monosynth apps. This exercises the same clocked state machine
// used by the firmware without requiring Pico SDK or hardware.

#include "audio/apps/motion_recorder.h"

#include <cstdio>
#include <vector>

static int failures = 0;
static int checks = 0;

#define CHECK(condition, message) do { \
    ++checks; \
    if (!(condition)) { \
        std::printf("  FAIL: %s (line %d)\n", message, __LINE__); \
        ++failures; \
    } else { \
        std::printf("  ok  : %s\n", message); \
    } \
} while (0)

// Count without printing (used inside loops).
#define CHECK_QUIET(condition) do { \
    ++checks; \
    if (!(condition)) { \
        std::printf("  FAIL: %s (line %d)\n", #condition, __LINE__); \
        ++failures; \
    } \
} while (0)

struct LedProbe {
    bool state = false;
    std::vector<bool> history;
};

static LedProbe* activeLedProbe = nullptr;

static void ledCallback(bool on) {
    if (activeLedProbe != nullptr) {
        activeLedProbe->state = on;
        activeLedProbe->history.push_back(on);
    }
}

struct FrameProbe {
    int count = 0;
    std::vector<MotionRecorder::Frame> frames;
};

static void frameCallback(void* context, const MotionRecorder::Frame& frame) {
    FrameProbe* probe = static_cast<FrameProbe*>(context);
    ++probe->count;
    probe->frames.push_back(frame);
}

static void press(MotionRecorder& recorder, uint32_t nowMs) {
    recorder.buttonChanged(true, nowMs);
    recorder.buttonChanged(false, nowMs + 1);
}

static void clock(MotionRecorder& recorder, uint16_t p1, uint16_t p2,
                  uint16_t p3, uint16_t p4, FrameProbe* probe = nullptr) {
    const uint16_t knobs[MotionRecorder::KNOB_COUNT] = {p1, p2, p3, p4};
    recorder.onClock(knobs, probe ? &frameCallback : nullptr, probe);
}

static bool sameFrame(const MotionRecorder::Frame& a, const MotionRecorder::Frame& b) {
    for (uint8_t i = 0; i < MotionRecorder::KNOB_COUNT; ++i) {
        if (a.knobs[i] != b.knobs[i]) return false;
    }
    for (uint8_t i = 0; i < MotionRecorder::CC_COUNT; ++i) {
        if (a.ccs[i] != b.ccs[i]) return false;
    }
    return true;
}

static void testLifecycleAndLed() {
    std::printf("\n[Test 1] MODE lifecycle and LED states\n");
    LedProbe led;
    activeLedProbe = &led;
    MotionRecorder recorder(&ledCallback);
    recorder.begin(0);

    CHECK(recorder.isLive(), "starts in LIVE");
    CHECK(!led.state, "LED is off in LIVE");

    press(recorder, 100);
    CHECK(recorder.isRecording(), "MODE starts RECORDING");
    CHECK(!led.state, "LED starts the recording phase off");

    recorder.update(250);
    CHECK(led.state, "LED blinks on while recording");
    recorder.update(400);
    CHECK(!led.state, "LED blinks off again while recording");

    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, i, i + 1, i + 2, i + 3);
    }
    CHECK(recorder.isPlayingBack(), "384 clocks switch to PLAYBACK");
    CHECK(led.state, "LED is solid in PLAYBACK");

    press(recorder, 1000);
    CHECK(recorder.isLive(), "MODE stops PLAYBACK and returns to LIVE");
    CHECK(!led.state, "LED is off after returning to LIVE");
    activeLedProbe = nullptr;
}

static void testExactFrames() {
    std::printf("\n[Test 2] exact P1..P4 + MCC bank A/B/C frame storage\n");
    MotionRecorder recorder;
    recorder.begin();
    press(recorder, 100);

    std::vector<MotionRecorder::Frame> expected;
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        MotionRecorder::Frame f;
        f.knobs[0] = (uint16_t)(0x0100u + i * 7u);
        f.knobs[1] = (uint16_t)(0x0A00u - i * 3u);
        f.knobs[2] = (uint16_t)(i * 5u);
        f.knobs[3] = (uint16_t)(4095u - i * 9u);
        for (uint8_t c = 0; c < MotionRecorder::CC_COUNT; ++c) {
            f.ccs[c] = (uint8_t)((i * (c + 3u) + c) & 0x7F);
            CHECK_QUIET(recorder.setCurrentCc(MotionRecorder::ccNumber(c), f.ccs[c]));
        }
        CHECK_QUIET(!recorder.setCurrentCc(74, 99)); // not an MCC CC
        clock(recorder, f.knobs[0], f.knobs[1], f.knobs[2], f.knobs[3]);
        expected.push_back(f);
    }

    CHECK(recorder.isPlayingBack(), "complete take is available for playback");
    CHECK(recorder.ownsCc(20) && recorder.ownsCc(30) && recorder.ownsCc(88),
          "every MCC bank CC is owned by the loop");
    CHECK(!recorder.ownsCc(71) && !recorder.ownsCc(24) && !recorder.ownsCc(89),
          "non-MCC CCs are never owned");

    FrameProbe probe;
    recorder.onStart();
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 1, 2, 3, 4, &probe);
    }

    CHECK(probe.count == MotionRecorder::LOOP_TICKS,
          "playback emits one frame per MIDI clock");
    bool exact = probe.frames.size() == expected.size();
    for (size_t i = 0; exact && i < expected.size(); ++i) {
        exact = sameFrame(probe.frames[i], expected[i]);
    }
    CHECK(exact, "guard pass replays P1..P4 and all 12 MCC CCs exactly, knobs ignored");

    FrameProbe loopProbe;
    clock(recorder, 1, 2, 3, 4, &loopProbe);
    CHECK(loopProbe.count == 1 && sameFrame(loopProbe.frames[0], expected[0]),
          "playback loops back to frame zero (knobs at the reference)");
}

static void testStartAndAbort() {
    std::printf("\n[Test 3] MIDI Start rewind and incomplete-take abort\n");
    MotionRecorder recorder;
    recorder.begin();
    press(recorder, 100);
    for (int i = 0; i < 7; ++i) clock(recorder, 1, 2, 3, 4);
    CHECK(recorder.getTick() == 7, "recording playhead advances with clocks");
    recorder.onStart();
    CHECK(recorder.getTick() == 0, "MIDI Start rewinds an active recording");

    press(recorder, 200);
    CHECK(recorder.isLive(), "MODE aborts an incomplete recording");

    press(recorder, 300);
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 3, 4, 5, 6);
    }
    CHECK(recorder.isPlayingBack(), "a later full take can be recorded after abort");
    recorder.onStart();
    clock(recorder, 0, 0, 0, 0);
    CHECK(recorder.getTick() == 1, "MIDI Start also rewinds playback before next frame");
}

static void testKnobAndCcOffset() {
    std::printf("\n[Test 4] knobs and MCC offset the loop after the guard pass\n");
    MotionRecorder recorder;
    recorder.begin();
    press(recorder, 100);
    recorder.setCurrentCc(21, 60);
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 1000, 2000, 3000, 100 + i);
    }

    // Guard pass: knobs end at new positions, MCC moved; nothing changes.
    FrameProbe guard;
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        recorder.setCurrentCc(21, 90);
        clock(recorder, 1500, 2000, 3000, 4000, &guard);
    }
    bool untouched = true;
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        untouched = untouched && guard.frames[i].knobs[0] == 1000 &&
                    guard.frames[i].knobs[3] == 100 + i &&
                    guard.frames[i].ccs[1] == 60;
    }
    CHECK(untouched, "knob / MCC moves during the guard pass are ignored");
    CHECK(recorder.isOffsetArmed(), "offset arms after one full loop");

    FrameProbe armed;
    recorder.setCurrentCc(21, 100);                    // +10 from reference 90
    clock(recorder, 1600, 1900, 3000, 4000, &armed);   // P1 +100, P2 -100
    CHECK(armed.frames[0].knobs[0] == 1100, "P1 turned up shifts its curve up");
    CHECK(armed.frames[0].knobs[1] == 1900, "P2 turned down shifts its curve down");
    CHECK(armed.frames[0].knobs[2] == 3000, "P3 left at the reference plays as recorded");
    CHECK(armed.frames[0].knobs[3] == 100, "P4 left at the reference plays as recorded");
    CHECK(armed.frames[0].ccs[1] == 70, "MCC moved after the guard shifts its curve");

    FrameProbe clamp;
    recorder.setCurrentCc(21, 0);                      // -90: below 0
    clock(recorder, 1500, 2000, 4095, 4000, &clamp);   // P3 +1095 -> clamp
    CHECK(clamp.frames[0].knobs[2] == MotionRecorder::KNOB_MAX, "knob offset clamps at 4095");
    CHECK(clamp.frames[0].ccs[1] == 0, "MCC offset clamps at 0");

    press(recorder, 1000);
    press(recorder, 2000);
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 0, 0, 0, 0);
    }
    CHECK(!recorder.isOffsetArmed(), "a new take starts with a fresh guard pass");
}

static void testUnrecordedAndBackfill() {
    std::printf("\n[Test 5] unrecorded CCs stay live, late CCs are back-filled\n");
    MotionRecorder recorder;
    recorder.begin();
    CHECK(recorder.getCurrentCc(27) == MotionRecorder::CC_UNSET, "CCs start unset");
    press(recorder, 100);
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        if (i == 100) recorder.setCurrentCc(86, 42);   // FX3 moved part-way
        clock(recorder, 0, 0, 0, 0);
    }
    CHECK(recorder.ownsCc(86), "a CC moved during the take is owned by the loop");
    CHECK(!recorder.ownsCc(27), "a CC never sent stays live in PLAYBACK");

    FrameProbe probe;
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 0, 0, 0, 0, &probe);
    }
    const int i86 = MotionRecorder::ccIndex(86);
    const int i27 = MotionRecorder::ccIndex(27);
    CHECK(probe.frames[0].ccs[i86] == 42 && probe.frames[99].ccs[i86] == 42,
          "frames before the first move carry its first value");
    CHECK(probe.frames[0].ccs[i27] == MotionRecorder::CC_UNSET,
          "unrecorded CC frames are CC_UNSET");

    press(recorder, 1000);
    CHECK(!recorder.ownsCc(86), "LIVE owns no CC");
    recorder.clearCurrentCcs();
    CHECK(recorder.getCurrentCc(86) == MotionRecorder::CC_UNSET, "clearCurrentCcs forgets live values");
}

static void testCcMap() {
    std::printf("\n[Test 6] MCC CC map\n");
    bool ok = true;
    for (uint8_t i = 0; i < MotionRecorder::CC_COUNT; ++i) {
        ok = ok && MotionRecorder::ccIndex(MotionRecorder::ccNumber(i)) == i;
    }
    CHECK(ok, "ccIndex(ccNumber(i)) == i for all 12");
    CHECK(MotionRecorder::ccNumber(0) == 20 && MotionRecorder::ccNumber(4) == 27 &&
          MotionRecorder::ccNumber(11) == 88, "banks A/B/C start at CC20/27/85");
    CHECK(MotionRecorder::ccIndex(19) < 0 && MotionRecorder::ccIndex(24) < 0 &&
          MotionRecorder::ccIndex(26) < 0 && MotionRecorder::ccIndex(31) < 0 &&
          MotionRecorder::ccIndex(84) < 0 && MotionRecorder::ccIndex(89) < 0,
          "neighbours of the banks are not MCC CCs");
}

static void testOverdub() {
    std::printf("\n[Test 7] hold MODE in PLAYBACK and move a parameter to overdub\n");
    LedProbe led;
    activeLedProbe = &led;
    MotionRecorder recorder(&ledCallback);
    recorder.begin(0);
    press(recorder, 100);
    recorder.setCurrentCc(21, 60);
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 1000, 2000, 3000, 4000);
    }
    // Guard pass with the knobs at the recorded positions.
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 1000, 2000, 3000, 4000);
    }
    CHECK(recorder.isOffsetArmed(), "loop armed before the overdub");

    // Hold MODE; P1 jitters within the noise guard, then moves at tick 10.
    recorder.buttonChanged(true, 1000);
    CHECK(recorder.isPlayingBack() && !recorder.isOverdubbing(),
          "pressing MODE in PLAYBACK keeps looping, no overdub yet");
    FrameProbe hold;
    for (uint16_t i = 0; i < 10; ++i) {
        clock(recorder, 1000 + 20, 2000, 3000, 4000, &hold);
    }
    CHECK(!recorder.isOverdubbing(), "knob noise below the threshold doesn't overdub");
    for (uint16_t i = 10; i < 20; ++i) {
        clock(recorder, 3000, 2000, 3000, 4000, &hold);
    }
    CHECK(recorder.isOverdubbing(), "moving P1 while MODE is held starts the overdub");
    CHECK(hold.frames[10].knobs[0] == 3000, "overdubbed P1 plays its live value");
    recorder.update(1200);
    recorder.update(1400);
    CHECK(led.history.size() >= 2, "LED blinks while overdubbing");

    // MCC CC21 (recorded) and CC27 (not in the take) moved during the hold.
    recorder.setCurrentCc(27, 5);   // first value
    clock(recorder, 3000, 2000, 3000, 4000, &hold);  // tick 20: CC27 first seen
    recorder.setCurrentCc(21, 99);
    recorder.setCurrentCc(27, 77);
    for (uint16_t i = 21; i < 30; ++i) {
        clock(recorder, 3000, 2000, 3000, 4000, &hold);
    }
    CHECK(recorder.ownsCc(27), "a CC overdubbed into the take joins the loop");
    recorder.buttonChanged(false, 1500);
    CHECK(recorder.isPlayingBack(), "releasing MODE after an overdub keeps PLAYBACK");
    CHECK(!recorder.isOverdubbing(), "the overdub ends on release");
    CHECK(led.state, "LED solid again after the overdub");

    // Next pass from tick 0, controls left where they were released.
    for (uint16_t i = 30; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 3000, 2000, 3000, 4000);
    }
    FrameProbe next;
    for (uint16_t i = 0; i < MotionRecorder::LOOP_TICKS; ++i) {
        clock(recorder, 3000, 2000, 3000, 4000, &next);
    }
    const int i21 = MotionRecorder::ccIndex(21);
    const int i27 = MotionRecorder::ccIndex(27);
    CHECK(next.frames[5].knobs[0] == 1000 && next.frames[15].knobs[0] == 3000 &&
          next.frames[29].knobs[0] == 3000 && next.frames[30].knobs[0] == 1000,
          "P1 replays the overdubbed span with no offset, the rest as recorded");
    CHECK(next.frames[15].knobs[1] == 2000, "P2 (not moved) keeps its recording");
    CHECK(next.frames[20].ccs[i21] == 60 && next.frames[25].ccs[i21] == 99 &&
          next.frames[30].ccs[i21] == 60, "MCC CC21 overdubbed only while held");
    CHECK(next.frames[0].ccs[i27] == 5 && next.frames[20].ccs[i27] == 5 &&
          next.frames[25].ccs[i27] == 77 && next.frames[100].ccs[i27] == 5,
          "new CC27 replays its overdub, its pre-hold value elsewhere");

    // A plain click (nothing moved) still returns to LIVE on release.
    recorder.buttonChanged(true, 3000);
    clock(recorder, 3000, 2000, 3000, 4000);
    CHECK(recorder.isPlayingBack(), "still looping while MODE is held");
    recorder.buttonChanged(false, 3100);
    CHECK(recorder.isLive(), "MODE click without moves returns to LIVE");
    CHECK(!led.state, "LED off in LIVE");
    activeLedProbe = nullptr;
}

int main() {
    testLifecycleAndLed();
    testExactFrames();
    testStartAndAbort();
    testKnobAndCcOffset();
    testUnrecordedAndBackfill();
    testCcMap();
    testOverdub();

    std::printf("\n=== %d checks, %d failures ===\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
