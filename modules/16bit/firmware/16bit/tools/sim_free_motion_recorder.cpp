// Host self-tests for the free-running (no MIDI clock) motion recorder used by
// the lyra4 app: loop length from two MODE presses, playback timing, overdub
// hold, loop offset, LED. No Pico SDK or hardware.

#include "audio/apps/free_motion_recorder.h"

#include <cstdio>
#include <vector>

using R = FreeMotionRecorder;

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

static bool ledState = false;
static void ledCallback(bool on) { ledState = on; }

struct Probe {
    int count = 0;
    R::Frame last = {};
};

static void frameCallback(void* context, const R::Frame& frame) {
    Probe* probe = static_cast<Probe*>(context);
    ++probe->count;
    probe->last = frame;
}

// A small rig: a millisecond clock, the four knobs and the main-loop call.
struct Rig {
    R recorder{&ledCallback};
    uint32_t now = 0;
    uint16_t knobs[R::KNOB_COUNT] = {1000, 2000, 3000, 4000};
    Probe probe;

    explicit Rig(uint32_t start = 0) : now(start) { recorder.begin(now); }

    void step(uint32_t ms = 1) {
        for (uint32_t i = 0; i < ms; ++i) {
            ++now;
            recorder.update(now, knobs, &frameCallback, &probe);
        }
    }
    void press() { recorder.buttonChanged(true, now); }
    void release() { recorder.buttonChanged(false, now); }
    void click() { press(); step(50); release(); }
};

// Record a take where P1 = elapsed ms / 4 and CC20 = elapsed ms / 100
// (frame k: P1 = 5k, CC20 = k / 5),
// closed by a press `lengthMs` after the first one.
static void recordRamp(Rig& rig, uint32_t lengthMs) {
    rig.knobs[0] = 0;
    rig.step();  // the recorder sees P1 = 0 before the press
    rig.recorder.setCurrentCc(20, 0);
    rig.press();
    rig.release();
    const uint32_t start = rig.now;
    while (rig.now - start < lengthMs) {
        const uint32_t t = rig.now + 1 - start;  // elapsed at the next update
        rig.knobs[0] = (uint16_t)(t / 4 > R::KNOB_MAX ? R::KNOB_MAX : t / 4);
        rig.recorder.setCurrentCc(20, (uint8_t)(t / 100 > 127 ? 127 : t / 100));
        rig.step();
    }
    rig.press();  // close the loop
}

static void testLifecycle() {
    std::printf("\n[Test 1] press / press sets the loop, click returns to LIVE\n");
    Rig rig(5000);
    CHECK(rig.recorder.isLive() && !ledState, "starts in LIVE, LED off");

    rig.press();
    rig.release();
    CHECK(rig.recorder.isRecording(), "first press starts RECORDING");
    bool sawOn = false, sawOff = false;
    for (int i = 0; i < 600; ++i) {
        rig.step();
        sawOn |= ledState;
        sawOff |= !ledState;
    }
    CHECK(sawOn && sawOff, "LED blinks while recording");
    rig.step(634);  // 1234 ms after the first press
    rig.press();
    CHECK(rig.recorder.isPlayingBack(), "second press closes the loop: PLAYBACK");
    CHECK(rig.recorder.getLoopMs() == 1234, "loop length = time between the presses (1234 ms)");
    CHECK(rig.recorder.getLoopFrames() == 62, "1234 ms = 62 frames of 20 ms");
    rig.step(10);
    rig.release();
    CHECK(rig.recorder.isPlayingBack(), "releasing the closing press keeps PLAYBACK");
    CHECK(ledState, "LED solid in PLAYBACK");

    rig.step(100);
    rig.click();
    CHECK(rig.recorder.isLive() && !ledState, "a click (nothing moved) returns to LIVE, LED off");

    rig.step(100);
    rig.press();
    rig.release();
    rig.step(150);
    rig.press();
    rig.release();
    CHECK(rig.recorder.isLive(), "a second press within 200 ms drops the take");
}

static void testPlaybackTiming() {
    std::printf("\n[Test 2] playback replays the take on its own clock, no drift\n");
    Rig rig;
    rig.recorder.setCurrentCc(27, 99);  // never moved: recorded flat
    recordRamp(rig, 1999);
    rig.release();
    const uint32_t loopStart = rig.now;
    CHECK(rig.recorder.getLoopMs() == 1999, "loop length 1999 ms");
    CHECK(rig.recorder.ownsCc(20) && rig.recorder.ownsCc(27), "recorded CCs are owned by the loop");
    CHECK(!rig.recorder.ownsCc(21), "a CC that never arrived stays live");

    // The knobs are somewhere else now: ignored during the guard pass.
    rig.knobs[0] = 4000;
    bool exact = true;
    for (uint32_t pass = 0; pass < 50; ++pass) {
        for (uint32_t probeMs : {10u, 500u, 1200u, 1990u}) {
            const uint32_t target = loopStart + pass * 1999 + probeMs;
            rig.step(target - rig.now);
            const uint32_t frameT = (probeMs / R::FRAME_MS) * R::FRAME_MS;
            // P1 held still since the guard pass: no offset.
            const uint16_t expectedP1 = (uint16_t)(frameT / 4);
            if (rig.probe.last.knobs[0] != expectedP1 ||
                rig.probe.last.ccs[0] != (uint8_t)(frameT / 100) ||
                rig.probe.last.ccs[4] != 99) {
                if (exact) {
                    std::printf("    pass %u at %u ms: P1 %u (want %u), CC20 %u (want %u)\n",
                                pass, probeMs, rig.probe.last.knobs[0], expectedP1,
                                rig.probe.last.ccs[0], frameT / 100);
                }
                exact = false;
            }
        }
    }
    CHECK(exact, "50 passes (100 s): every probe plays the frame of its loop position");
    CHECK(rig.recorder.isOffsetArmed(), "offset armed after the first pass");

    // Frames are only delivered when the playhead moves to a new frame.
    const int before = rig.probe.count;
    rig.step(1000);
    CHECK(rig.probe.count - before >= 49 && rig.probe.count - before <= 51,
          "about one apply per 20 ms frame");
}

static void testOffset() {
    std::printf("\n[Test 3] loop offset after the guard pass\n");
    Rig rig;
    recordRamp(rig, 1000);
    rig.release();
    rig.knobs[0] = 3000;  // hand moved right after closing the loop
    rig.step(1100);       // guard pass over, reference = 3000
    CHECK(rig.recorder.isOffsetArmed(), "offset armed");
    rig.step(1000 - (rig.now % 1000) + 500);  // mid loop, frame ~500 ms
    const uint16_t base = rig.probe.last.knobs[0];
    rig.knobs[0] = 3100;
    rig.step(40);
    CHECK(rig.probe.last.knobs[0] >= base + 100 - 1 && rig.probe.last.knobs[0] <= base + 100 + 12,
          "moving P1 by +100 shifts its curve by +100");
    rig.recorder.setCurrentCc(20, 127);  // reference 10 (the take's last value)
    rig.step(40);
    const int storedCc = rig.recorder.getFrameIndex() * (int)R::FRAME_MS / 100;
    CHECK(rig.probe.last.ccs[0] == (storedCc + 117 > 127 ? 127 : storedCc + 117),
          "moving CC20 by +117 shifts its curve, clamped at 127");
}

static void testOverdub() {
    std::printf("\n[Test 4] hold MODE + move = overdub\n");
    Rig rig;
    recordRamp(rig, 2000);
    rig.release();
    rig.step(2100);  // guard pass done

    // Hold, move P2 (never moved in the take) and CC21 (never sent) for ~half a loop.
    rig.press();
    rig.step(30);
    CHECK(!rig.recorder.isOverdubbing(), "holding without moving is not an overdub yet");
    rig.knobs[1] = 100;  // moved > 48 from 2000
    rig.recorder.setCurrentCc(21, 77);
    rig.step(1000);
    CHECK(rig.recorder.isOverdubbing(), "moving a knob while holding overdubs");
    CHECK(rig.probe.last.knobs[1] == 100, "the overdubbed knob plays its live value");
    CHECK(rig.recorder.ownsCc(21), "a CC new to the take joins the loop");
    rig.release();
    CHECK(rig.recorder.isPlayingBack(), "release after a move keeps PLAYBACK");

    // Put the hand back where it was: the overdubbed span must replay 100,
    // the rest 2000 (the knob's value before the hold), with no offset.
    rig.knobs[1] = 100;  // reference = position at release
    int inSpan = 0, outSpan = 0, bad = 0;
    for (int i = 0; i < 2000; ++i) {
        rig.step();
        const uint16_t p2 = rig.probe.last.knobs[1];
        if (p2 == 100) ++inSpan;
        else if (p2 == 2000) ++outSpan;
        else ++bad;
    }
    CHECK(bad == 0, "P2 plays only the overdubbed or the original value");
    CHECK(inSpan > 900 && inSpan < 1150 && outSpan > 850,
          "about half the loop overdubbed, the rest untouched");
    CHECK(rig.probe.last.ccs[1] == 77,
          "the new CC plays its value across the whole loop (none before the hold)");

    // P1's ramp (not touched) still plays.
    bool rampOk = true;
    uint16_t prev = 0;
    for (int i = 0; i < 2000; ++i) {
        rig.step();
        const uint16_t p1 = rig.probe.last.knobs[0];
        if (p1 + 10 < prev && prev < 400) rampOk = false;  // only the wrap may go down
        prev = p1;
    }
    CHECK(rampOk, "an untouched knob keeps its recorded curve");

    // Overdub during a main-loop stall leaves no gaps.
    rig.press();
    rig.step(5);
    rig.knobs[3] = 10;
    rig.step();
    rig.now += 300;  // 300 ms with no update
    rig.step();
    rig.release();
    rig.knobs[3] = 10;
    int lowFrames = 0;
    for (int i = 0; i < 2000; ++i) {
        rig.step();
        if (rig.probe.last.knobs[3] == 10) ++lowFrames;
    }
    CHECK(lowFrames >= 300, "frames skipped by a stall are overdubbed too");

    rig.click();
    CHECK(rig.recorder.isLive(), "a later click still returns to LIVE");
}

static void testMaxLengthAndWrap() {
    std::printf("\n[Test 5] max length and clock wrap\n");
    Rig rig(0xFFFFFFFFu - 30000);  // the ms clock wraps during the take
    rig.press();
    rig.release();
    rig.step(R::MAX_LOOP_MS + 5);
    CHECK(rig.recorder.isPlayingBack(), "a take closes itself at 60 s");
    CHECK(rig.recorder.getLoopMs() == R::MAX_LOOP_MS && rig.recorder.getLoopFrames() == R::MAX_FRAMES,
          "max loop = 60 s / 3000 frames");
    rig.step(10);
    CHECK(rig.recorder.getFrameIndex() < 2, "playback starts from the first frame");
    rig.step(R::MAX_LOOP_MS);
    CHECK(rig.recorder.isPlayingBack() && rig.recorder.getFrameIndex() < 2,
          "loops across the clock wrap");
}

static void testLoopMarkLed() {
    std::printf("\n[Test 6] LED mark at each loop restart\n");
    Rig rig;
    recordRamp(rig, 500);
    rig.release();
    int darkRuns = 0;
    bool prev = true;
    for (int i = 0; i < 2600; ++i) {
        rig.step();
        if (!ledState && prev) ++darkRuns;
        prev = ledState;
    }
    CHECK(darkRuns == 5, "LED goes dark once per loop (5 restarts in 2.6 s of a 0.5 s loop)");
}

int main() {
    std::printf("FreeMotionRecorder self-tests\n");
    testLifecycle();
    testPlaybackTiming();
    testOffset();
    testOverdub();
    testMaxLengthAndWrap();
    testLoopMarkLed();
    std::printf("\n%d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
