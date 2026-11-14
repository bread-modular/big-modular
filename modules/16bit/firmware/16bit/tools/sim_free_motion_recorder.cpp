// Host self-tests for the free-running (no MIDI clock) motion recorder used by
// the cpx4 app: hold MODE + move records a control on its own track, tracks
// loop independently (take + glide back to its first value), re-record, click
// removes every track, joins (largest step bounded), offset, MODE contact
// bounce, MCC banks and CC flicker, LED. No Pico SDK or hardware.

#include "audio/apps/free_motion_recorder.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
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
static int ledChanges = 0;
static void ledCallback(bool on) {
    ledState = on;
    ++ledChanges;
}

// Params: P1..P4 = 0..3, then the MCC slots.
static constexpr uint8_t P1 = 0;
static constexpr uint8_t P2 = 1;
static constexpr uint8_t SLOT_CC[R::CC_COUNT] = {20, 21, 22, 23, 27, 28,
                                                 29, 30, 85, 86, 87, 88};
static uint8_t paramOf(uint8_t cc) { return (uint8_t)R::paramOfCc(cc); }

struct Probe {
    int count[R::PARAM_COUNT] = {};
    int value[R::PARAM_COUNT] = {};
    int total = 0;
};

static void applyCallback(void* context, uint8_t param, uint16_t value) {
    Probe* probe = static_cast<Probe*>(context);
    ++probe->count[param];
    ++probe->total;
    probe->value[param] = value;
}

// A small rig: a millisecond clock, the four knobs, the MCC values and the
// main-loop call. sounding() is what the app plays: the recorder's value for
// a control it owns, the control itself otherwise.
struct Rig {
    R recorder{&ledCallback};
    uint32_t now = 0;
    uint16_t knobs[R::KNOB_COUNT] = {1000, 2000, 3000, 4000};
    Probe probe;

    explicit Rig(uint32_t start = 0) : now(start) {
        recorder.begin(now);
        for (uint8_t cc : {20, 21, 22, 23, 27, 28, 29, 30}) {
            recorder.setCurrentCc(cc, 24);  // as the app seeds them
        }
        step();
    }

    void step(uint32_t ms = 1) {
        for (uint32_t i = 0; i < ms; ++i) {
            ++now;
            recorder.update(now, knobs, &applyCallback, &probe);
        }
    }
    void press() { recorder.buttonChanged(true, now); }
    void release() { recorder.buttonChanged(false, now); }
    void click() { press(); step(50); release(); }
    // The same edges as IO reports them from a bouncing contact (1 ms).
    void bouncyPress() { press(); step(); release(); step(); press(); }
    void bouncyRelease() { release(); step(); press(); step(); release(); }
    void cc(uint8_t number, uint8_t value) {
        recorder.setCurrentCc(number, value);
    }

    int live(uint8_t param) const {
        return param < R::KNOB_COUNT
            ? knobs[param]
            : recorder.getCurrentCc(SLOT_CC[param - R::KNOB_COUNT]);
    }
    int sounding(uint8_t param) const {
        return recorder.ownsParam(param) ? probe.value[param] : live(param);
    }

    // Largest change of what sounds on `param` from one update to the next
    // over `ms`; set(t) moves the controls before update t (0-based).
    template <typename Set>
    int maxStep(uint8_t param, uint32_t ms, Set set) {
        int worst = 0;
        int prev = sounding(param);
        for (uint32_t t = 0; t < ms; ++t) {
            set(t);
            step();
            const int value = sounding(param);
            if (std::abs(value - prev) > worst) worst = std::abs(value - prev);
            prev = value;
        }
        return worst;
    }
    int maxStep(uint8_t param, uint32_t ms) {
        return maxStep(param, ms, [](uint32_t) {});
    }
};

// Hold MODE, wait `leadMs`, then move for `takeMs`: set(t) puts the controls
// where they are t ms after the first move (set(0) must be a move). MODE is
// released takeMs after the first move. Returns the time of the first move.
template <typename Set>
static uint32_t recordGesture(Rig& rig, uint32_t takeMs, Set set,
                              uint32_t leadMs = 10) {
    rig.press();
    rig.step(leadMs);
    uint32_t start = 0;
    for (uint32_t t = 0; t <= takeMs; ++t) {
        set(t);
        rig.step();
        if (t == 0) start = rig.now;
    }
    rig.release();
    return start;
}

// P1 from its rest at 1000: 1100 + t counts, for takeMs.
static uint32_t recordP1Ramp(Rig& rig, uint32_t takeMs) {
    return recordGesture(rig, takeMs, [&rig](uint32_t t) {
        rig.knobs[P1] = (uint16_t)(1100 + t);
    });
}

static float ease(float s) { return s * s * (3.0f - 2.0f * s); }

// A track that recorded from + t for takeMs and glides back over tailMs.
static int rampLoopValue(uint32_t pos, int from, uint32_t takeMs,
                         uint32_t tailMs) {
    if (pos <= takeMs) {
        return from + (int)pos;
    }
    const float end = (float)(from + (int)takeMs);
    return (int)std::lround(end + ((float)from - end) *
                                  ease((float)(pos - takeMs) / (float)tailMs));
}

static bool sawBlink(Rig& rig, uint32_t ms) {
    bool sawOn = false, sawOff = false;
    for (uint32_t i = 0; i < ms; ++i) {
        rig.step();
        sawOn |= ledState;
        sawOff |= !ledState;
    }
    return sawOn && sawOff;
}

static void testLifecycle() {
    std::printf("\n[Test 1] hold + move records, release loops, click removes\n");
    Rig rig(5000);
    CHECK(rig.recorder.isLive() && !ledState, "starts live, LED off");

    rig.click();
    rig.step(100);
    CHECK(rig.recorder.isLive() && !ledState && rig.probe.total == 0,
          "a click with no tracks does nothing");

    rig.press();
    rig.step(300);
    CHECK(rig.recorder.isHolding() && !rig.recorder.isRecording() && !ledState,
          "holding MODE alone records nothing, LED off");

    bool blinked = false;
    int moved = 0;
    for (uint32_t t = 0; t <= 1000; ++t) {
        rig.knobs[P1] = (uint16_t)(1100 + t);
        rig.step();
        if (t == 0) {
            CHECK(rig.recorder.getTrackState(P1) == R::TRACK_RECORDING && ledState,
                  "the first move starts the take, LED on at once");
        }
        blinked |= !ledState;
        moved += rig.sounding(P1) == rig.knobs[P1];
    }
    CHECK(blinked, "LED blinks while recording");
    CHECK(moved == 1001, "the control drives the sound while it is recorded");
    CHECK(rig.recorder.ownsKnob(P1) && !rig.recorder.ownsKnob(P2),
          "only the moved control belongs to the recorder");

    rig.release();
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_PLAYING,
          "releasing MODE loops the take");
    CHECK(rig.recorder.getTakeMs(P1) == 1000,
          "take = first move to release (1000 ms)");
    CHECK(ledState, "LED solid from the first recording on");
    bool solid = true;
    for (int i = 0; i < 5000; ++i) {
        rig.step();
        solid &= ledState;
    }
    CHECK(solid, "LED stays solid while the track plays");

    rig.click();
    CHECK(!rig.recorder.isPlayingBack() && !ledState,
          "one click removes the recording, LED off");
    rig.step(R::RETURN_MS + 1);
    CHECK(rig.recorder.isLive() && !rig.recorder.ownsKnob(P1),
          "the control is live again after the glide");
    CHECK(rig.probe.count[P2] == 0 && rig.probe.count[paramOf(27)] == 0,
          "controls that were never recorded are never applied");
}

static void testPlayback() {
    std::printf("\n[Test 2] a track replays its take, then glides back: no drift\n");
    Rig rig;
    const uint32_t start = recordP1Ramp(rig, 2000);
    CHECK(rig.recorder.getTakeMs(P1) == 2000 && rig.recorder.getLoopMs(P1) == 2500,
          "2000 ms take + 500 ms glide back = 2500 ms loop");

    // The knob rests where the take ended (3100): no offset.
    bool exact = true;
    for (uint32_t pass = 1; pass <= 40; ++pass) {
        for (uint32_t pos : {0u, 100u, 510u, 1234u, 1999u, 2000u, 2250u, 2400u}) {
            rig.step(start + pass * 2500 + pos - rig.now);
            const int want = rampLoopValue(pos, 1100, 2000, 500);
            if (std::abs(rig.sounding(P1) - want) > 1) {
                if (exact) {
                    std::printf("    pass %u at %u ms: P1 %d (want %d)\n", pass,
                                pos, rig.sounding(P1), want);
                }
                exact = false;
            }
        }
    }
    CHECK(exact, "40 passes (100 s): every probe plays its loop position");

    rig.step(start + 41 * 2500 + 2000 - rig.now);
    CHECK(rig.sounding(P1) == 3100, "the take keeps its last value (3100)");
    rig.step(250);
    CHECK(std::abs(rig.sounding(P1) - 2100) <= 1, "half-way through the glide back: 2100");
    rig.step(250);
    CHECK(rig.sounding(P1) == 1100, "the loop restarts on the first value (1100)");

    // Between two 20 ms frames the value is interpolated: single counts.
    CHECK(rig.maxStep(P1, 1900) == 1, "the take plays back in single counts (1 per ms)");
}

static void testLoopJoin() {
    std::printf("\n[Test 3] loop end -> start is a glide\n");
    {
        Rig rig;
        recordP1Ramp(rig, 2000);
        // 2000 counts back in 500 ms: smoothstep peaks at 1.5 x 4 per ms.
        const int worst = rig.maxStep(P1, 3 * 2500);
        std::printf("    P1 1100 -> 3100: largest step over 3 loops %d counts\n", worst);
        CHECK(worst >= 5 && worst <= 7, "knob: no step at the join (2000 without the glide)");
    }
    {
        Rig rig;
        rig.cc(27, 8);
        rig.step();
        recordGesture(rig, 2000, [&rig](uint32_t t) {
            rig.cc(27, (uint8_t)(10 + t / 20));  // 10 -> 110
        });
        CHECK(rig.recorder.getLoopMs(paramOf(27)) == 2500, "CC: 2000 ms take + 500 ms glide");
        CHECK(rig.maxStep(paramOf(27), 3 * 2500) == 1, "CC: one step at a time through the join");
    }
    {
        // Up and back down to the start: nothing to glide.
        Rig rig;
        recordGesture(rig, 1000, [&rig](uint32_t t) {
            rig.knobs[P1] = (uint16_t)(1100 + (t <= 500 ? t : 1000 - t));
        });
        CHECK(rig.recorder.getLoopMs(P1) == 1000,
              "a take that ends where it began loops with no glide (loop = take)");
        CHECK(rig.maxStep(P1, 3000) == 1, "and still never steps");
    }
    {
        // Ends 100 counts from the start: 250 ms x 100 / 1024.
        Rig rig;
        recordGesture(rig, 900, [&rig](uint32_t t) {
            rig.knobs[P1] = (uint16_t)(1100 + (t <= 500 ? t : 1000 - t));
        });
        CHECK(rig.recorder.getLoopMs(P1) == 924, "a small step gets a short glide (24 ms)");
    }
    {
        Rig rig;
        recordGesture(rig, 400, [&rig](uint32_t t) {
            rig.knobs[P1] = (uint16_t)(1100 + 4 * t);
        });
        CHECK(rig.recorder.getLoopMs(P1) == 650, "short take: the glide is at least 250 ms");
    }
    {
        Rig rig;
        recordGesture(rig, 20000, [&rig](uint32_t t) {
            rig.knobs[P1] = (uint16_t)(1100 + t / 10);
        });
        CHECK(rig.recorder.getLoopMs(P1) == 22000, "long take: the glide is at most 2 s");
    }
}

static void testIndependentTracks() {
    std::printf("\n[Test 4] every control has its own track and loop length\n");
    Rig rig;
    rig.cc(27, 18);
    rig.step();
    const uint8_t cc27 = paramOf(27);
    const uint32_t startP1 = recordP1Ramp(rig, 1200);  // loop 1500
    CHECK(rig.recorder.getLoopMs(P1) == 1500, "P1: 1200 ms take, 1500 ms loop");
    CHECK(!rig.recorder.ownsCc(27), "CC27 is still live");

    rig.step(700);
    // The second hold, 700 ms later: CC27 20 -> 100 over 1700 ms. P1 keeps
    // looping all the way through it.
    bool p1Kept = true;
    rig.press();
    rig.step(10);
    for (uint32_t t = 0; t <= 1700; ++t) {
        rig.cc(27, (uint8_t)(20 + t * 80 / 1700));
        rig.step();
        const int want = rampLoopValue((rig.now - startP1) % 1500, 1100, 1200, 300);
        p1Kept &= std::abs(rig.sounding(P1) - want) <= 1;
    }
    rig.release();
    CHECK(p1Kept, "recording CC27 leaves the P1 track playing, untouched");
    CHECK(rig.recorder.getTakeMs(cc27) == 1700 && rig.recorder.getLoopMs(cc27) == 2125,
          "CC27: its own 1700 ms take, 2125 ms loop");
    CHECK(rig.recorder.getLoopMs(P1) == 1500, "P1 keeps its own length");
    CHECK(rig.recorder.countTracks(R::TRACK_PLAYING) == 2, "two tracks play");
    CHECK(ledState, "LED solid");

    // Each one repeats with its own period.
    std::vector<int> p1, cc;
    for (int i = 0; i < 3 * 2125 + 3 * 1500; ++i) {
        rig.step();
        p1.push_back(rig.sounding(P1));
        cc.push_back(rig.sounding(cc27));
    }
    bool p1Periodic = true, ccPeriodic = true, p1NotCc = false, ccNotP1 = false;
    for (size_t i = 0; i + 2125 < p1.size(); ++i) {
        p1Periodic &= i + 1500 >= p1.size() || p1[i] == p1[i + 1500];
        ccPeriodic &= cc[i] == cc[i + 2125];
        p1NotCc |= p1[i] != p1[i + 2125];
        ccNotP1 |= i + 1500 < cc.size() && cc[i] != cc[i + 1500];
    }
    CHECK(p1Periodic, "P1 repeats every 1500 ms");
    CHECK(ccPeriodic, "CC27 repeats every 2125 ms");
    CHECK(p1NotCc && ccNotP1, "neither follows the other's loop");
    CHECK(!rig.recorder.ownsKnob(P2) && !rig.recorder.ownsCc(28) &&
          rig.probe.count[P2] == 0 && rig.probe.count[paramOf(28)] == 0,
          "the other controls stay live");
}

static void testOneHoldTwoControls() {
    std::printf("\n[Test 5] two controls in one hold: each from its own first move\n");
    Rig rig;
    const uint8_t cc20 = paramOf(20);
    recordGesture(rig, 1500, [&rig](uint32_t t) {
        rig.knobs[P2] = (uint16_t)(2100 + t);
        if (t >= 600) {
            rig.cc(20, (uint8_t)(30 + (t - 600) / 20));
        }
    });
    CHECK(rig.recorder.getTakeMs(P2) == 1500, "P2 moved first: 1500 ms take");
    CHECK(rig.recorder.getTakeMs(cc20) == 900, "CC20 moved 600 ms later: 900 ms take");
    CHECK(rig.recorder.getTrackState(P2) == R::TRACK_PLAYING &&
          rig.recorder.getTrackState(cc20) == R::TRACK_PLAYING,
          "both loop after the release");
    CHECK(rig.sounding(cc20) == 75 && rig.sounding(P2) == 3600,
          "both start from their last value (the glide back)");
    rig.step(rig.recorder.getLoopMs(cc20) - 900);
    CHECK(rig.sounding(cc20) == 30, "CC20 restarts on its first value");
}

static void testReRecord() {
    std::printf("\n[Test 6] hold + move a recorded control: the new take replaces its track\n");
    Rig rig;
    const uint32_t start = recordP1Ramp(rig, 1200);  // 1100..2300, loop 1500
    rig.step(start + 3 * 1500 + 190 - rig.now);
    rig.press();
    rig.step(10);  // the track is at 200 ms: 1300; the knob rests at 2300
    CHECK(rig.sounding(P1) == 1300, "the track plays 1300 as the hold starts");
    CHECK(ledState && !rig.recorder.isRecording(), "holding alone: still playback, LED solid");

    // Grab the knob: 2400 + t / 2. The 1100 counts between the track and the
    // knob fade out over 300 ms (peak 5.5 per ms) on top of the move.
    int worst = 0;
    int prev = rig.sounding(P1);
    bool blinked = false;
    for (uint32_t t = 0; t <= 800; ++t) {
        rig.knobs[P1] = (uint16_t)(2400 + t / 2);
        rig.step();
        if (t == 0) {
            CHECK(rig.recorder.getTrackState(P1) == R::TRACK_RECORDING && !ledState,
                  "the move starts a new take, LED goes dark first (blink)");
        }
        blinked |= ledState;
        const int value = rig.sounding(P1);
        if (std::abs(value - prev) > worst) worst = std::abs(value - prev);
        prev = value;
        if (t == 300) {
            CHECK(value == rig.knobs[P1], "after 300 ms the knob has the sound");
        }
    }
    std::printf("    take-over from 1300 to the knob at 2400: largest step %d counts\n", worst);
    CHECK(worst <= 7, "the take-over glides (1100 without it)");
    CHECK(blinked, "LED blinks during the new take");
    rig.release();
    CHECK(rig.recorder.getTakeMs(P1) == 800 && rig.recorder.getLoopMs(P1) == 1050,
          "new track: 800 ms take + 250 ms glide");
    CHECK(ledState, "LED solid again");

    rig.step(250);  // the glide back to the first value
    CHECK(std::abs(rig.sounding(P1) - 1300) <= 6,
          "the take stores what it played: it starts where the old track was");
    rig.step(400);
    CHECK(rig.sounding(P1) == 2600, "400 ms in: the new curve (2600), not the old one (1500)");
    CHECK(rig.maxStep(P1, 3 * 1050) <= 12, "the new loop has no step either");
}

static void testRemove() {
    std::printf("\n[Test 7] a click removes every track, gliding to the controls\n");
    Rig rig;
    rig.cc(27, 18);
    rig.step();
    const uint8_t cc27 = paramOf(27);
    const uint32_t start = recordP1Ramp(rig, 1200);
    rig.step(300);
    recordGesture(rig, 1700, [&rig](uint32_t t) {
        rig.cc(27, (uint8_t)(20 + t * 80 / 1700));
    });
    // Click where both tracks are far from their controls (the P1 knob rests
    // at 2300, the MCC knob at 100).
    rig.step(start + 6 * 1500 - rig.now);
    for (int i = 0; i < 20000; ++i) {
        if (std::abs(rig.sounding(P1) - 2300) > 500 &&
            std::abs(rig.sounding(cc27) - 100) > 40) {
            break;
        }
        rig.step();
    }
    const int before = rig.sounding(P1);
    const int beforeCc = rig.sounding(cc27);
    std::printf("    at the click: P1 %d (knob 2300), CC27 %d (control 100)\n",
                before, beforeCc);
    CHECK(std::abs(before - 2300) > 500 && std::abs(beforeCc - 100) > 40,
          "both tracks are far from their controls");
    rig.press();
    rig.step(50);
    const int atClick = rig.sounding(P1), atClickCc = rig.sounding(cc27);
    rig.release();
    CHECK(!rig.recorder.isPlayingBack() && !ledState, "click: no track plays, LED off");
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_RETURNING && rig.recorder.ownsKnob(P1),
          "the recorder keeps the control while it glides back");
    rig.step();
    CHECK(std::abs(rig.sounding(P1) - atClick) <= 3 &&
          std::abs(rig.sounding(cc27) - atClickCc) <= 1,
          "nothing jumps at the click");

    int worstKnob = 0, worstCc = 0;
    int prevKnob = rig.sounding(P1), prevCc = rig.sounding(cc27);
    for (uint32_t t = 0; t < R::RETURN_MS + 5; ++t) {
        rig.step();
        const int knob = rig.sounding(P1), cc = rig.sounding(cc27);
        if (std::abs(knob - prevKnob) > worstKnob) worstKnob = std::abs(knob - prevKnob);
        if (std::abs(cc - prevCc) > worstCc) worstCc = std::abs(cc - prevCc);
        prevKnob = knob;
        prevCc = cc;
    }
    std::printf("    back to the controls: largest step P1 %d counts, CC27 %d\n",
                worstKnob, worstCc);
    CHECK(worstKnob <= 3 && worstCc <= 1, "the way back is a glide (600 ms)");
    CHECK(rig.recorder.isLive(), "then every control is live");
    CHECK(rig.probe.value[P1] == 2300 && rig.probe.value[cc27] == 100,
          "the last values applied are the controls' own");

    // The next recording starts clean.
    recordP1Ramp(rig, 600);
    CHECK(rig.recorder.countTracks(R::TRACK_PLAYING) == 1 && rig.recorder.getTakeMs(P1) == 600,
          "a new take after the removal: one track, 600 ms");
}

static void testHoldsThatRecordNothing() {
    std::printf("\n[Test 8] long holds, short takes and clicks\n");
    Rig rig;
    const uint8_t cc21 = paramOf(21);
    recordP1Ramp(rig, 1200);
    rig.step(1000);

    rig.press();
    rig.step(R::CLICK_MAX_MS);
    rig.release();
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_PLAYING && ledState,
          "a long hold with nothing moved removes nothing");

    // CC21 moves 100 ms before the release of a long hold.
    rig.press();
    rig.step(900);
    rig.cc(21, 40);
    rig.step(100);
    CHECK(rig.recorder.getTrackState(cc21) == R::TRACK_RECORDING, "a take starts");
    rig.release();
    rig.step();
    CHECK(rig.recorder.getTrackState(cc21) == R::TRACK_LIVE && !rig.recorder.ownsCc(21),
          "a take under 200 ms is dropped: the control stays live");
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_PLAYING, "and the other track keeps playing");

    // A click that bumps a control is still a click.
    rig.press();
    rig.step(20);
    rig.cc(21, 45);
    rig.step(60);
    rig.release();
    CHECK(!rig.recorder.isPlayingBack() && !ledState,
          "a click with a bumped control still removes the tracks");
    rig.step(R::RETURN_MS + 1);
    CHECK(rig.recorder.isLive(), "everything live afterwards");

    // A quick but real take: 300 ms inside a 400 ms press is kept.
    rig.press();
    rig.step(100);
    for (uint32_t t = 0; t <= 300; ++t) {
        rig.cc(21, (uint8_t)(50 + t / 10));
        rig.step();
    }
    rig.release();
    CHECK(rig.recorder.getTrackState(cc21) == R::TRACK_PLAYING &&
          rig.recorder.getTakeMs(cc21) == 300,
          "a 300 ms take in a short press is a recording, not a click");

    // MODE pressed before the knobs were ever read: no phantom move.
    R bare(&ledCallback);
    Probe probe;
    const uint16_t knobs[R::KNOB_COUNT] = {1000, 2000, 3000, 4000};
    bare.begin(0);
    bare.buttonChanged(true, 0);
    for (uint32_t t = 1; t <= 100; ++t) {
        bare.update(t, knobs, &applyCallback, &probe);
    }
    CHECK(!bare.isRecording() && probe.total == 0,
          "a press before the first knob read records nothing");

    // begin() drops everything.
    rig.recorder.begin(rig.now);
    CHECK(rig.recorder.isLive() && !ledState, "begin(): no tracks, LED off");
}

static void testMccBanks() {
    std::printf("\n[Test 9] MCC Bank A and Bank B, CC flicker\n");
    Rig rig;
    const uint8_t cc20 = paramOf(20), cc22 = paramOf(22), cc27 = paramOf(27);
    CHECK(cc20 == 4 && cc27 == 8, "Bank A and Bank B have their own slots (CC20 = 4, CC27 = 8)");
    CHECK(R::paramOfCc(102) < 0 && !rig.recorder.setCurrentCc(102, 64),
          "the button CCs are outside the recorder");

    // Bank A up, then (another hold) Bank B down, with different lengths.
    const uint32_t startA = recordGesture(rig, 1000, [&rig](uint32_t t) {
        rig.cc(20, (uint8_t)(30 + t / 20));   // 30 -> 80
    });
    rig.step(333);
    const uint32_t startB = recordGesture(rig, 1600, [&rig](uint32_t t) {
        rig.cc(27, (uint8_t)(120 - t / 20));  // 120 -> 40
    });
    CHECK(rig.recorder.ownsCc(20) && rig.recorder.ownsCc(27), "both banks recorded");
    const uint32_t loopA = rig.recorder.getLoopMs(cc20);
    const uint32_t loopB = rig.recorder.getLoopMs(cc27);
    CHECK(loopA == 1250 && loopB == 2000, "CC20 loops in 1250 ms, CC27 in 2000 ms");

    bool aRight = true, bRight = true;
    for (int i = 0; i < 12000; ++i) {
        rig.step();
        const uint32_t posA = (rig.now - startA) % loopA;
        const uint32_t posB = (rig.now - startB) % loopB;
        if (posA < 1000) {
            aRight &= std::abs(rig.sounding(cc20) - (int)(30 + posA / 20)) <= 1;
        }
        if (posB < 1600) {
            bRight &= std::abs(rig.sounding(cc27) - (int)(120 - posB / 20)) <= 1;
        }
    }
    CHECK(aRight, "Bank A plays its own curve (30 -> 80) for 12 s");
    CHECK(bRight, "Bank B plays its own curve (120 -> 40) for 12 s");

    // An MCC knob resting between two steps flickers by one.
    rig.cc(22, 50);
    rig.step();
    rig.press();
    for (int i = 0; i < 1000; ++i) {
        rig.cc(22, (uint8_t)(50 + (i / 7) % 2));
        rig.step();
    }
    CHECK(!rig.recorder.isRecording() && !rig.recorder.ownsCc(22),
          "one step of flicker during a hold is not a move");
    rig.release();
    CHECK(rig.recorder.countTracks(R::TRACK_PLAYING) == 2, "the long hold removed nothing");

    rig.press();
    for (int i = 0; i < 60; ++i) {
        rig.cc(22, (uint8_t)(50 + (i / 7) % 2));
        rig.step();
    }
    rig.release();
    CHECK(!rig.recorder.isPlayingBack(), "a click while a knob flickers still removes the tracks");
    CHECK(rig.probe.count[cc22] == 0, "the flickering control was never taken over");

    // A recorded control at rest applies nothing new.
    rig.step(R::RETURN_MS + 1);
    recordGesture(rig, 1000, [&rig](uint32_t t) {
        rig.cc(28, (uint8_t)(t < 200 ? 30 + t / 10 : 50));  // moves, then rests
    });
    rig.step(rig.recorder.getLoopMs(paramOf(28)) - 1000 + 300);
    const int applied = rig.probe.count[paramOf(28)];
    rig.step(600);
    CHECK(rig.probe.count[paramOf(28)] == applied,
          "the flat part of a track applies nothing (values only when they change)");
}

static void testButtonBounce() {
    std::printf("\n[Test 10] MODE contact bounce\n");
    Rig rig;
    rig.bouncyPress();
    rig.step(10);
    for (uint32_t t = 0; t <= 1000; ++t) {
        rig.knobs[P1] = (uint16_t)(1100 + t);
        rig.step();
    }
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_RECORDING,
          "a bouncing press is one hold: the take runs");
    rig.bouncyRelease();
    rig.step(100);
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_PLAYING && ledState,
          "a bouncing release closes the take once (no click that removes it)");
    CHECK(rig.recorder.getTakeMs(P1) == 1000, "take length from the first release edge");

    rig.step(1000);
    rig.bouncyPress();
    rig.step(40);
    rig.bouncyRelease();
    rig.step(100);
    CHECK(!rig.recorder.isPlayingBack() && !rig.recorder.isHolding(),
          "a bouncing click removes the tracks once and leaves no hold");

    // A click shorter than the debounce time still counts.
    recordP1Ramp(rig, 500);
    rig.step(1000);
    rig.press();
    rig.step(10);
    rig.release();
    rig.step(40);
    CHECK(!rig.recorder.isPlayingBack(), "a 10 ms click is taken after the debounce time");
}

static void testOffset() {
    std::printf("\n[Test 11] moving a recorded control (MODE not held) shifts its track\n");
    Rig rig;
    rig.cc(27, 18);
    rig.step();
    const uint8_t cc27 = paramOf(27);
    const uint32_t start = recordP1Ramp(rig, 1200);  // 1100..2300, loop 1500
    auto track = [&](uint32_t now) {
        return rampLoopValue((now - start) % 1500, 1100, 1200, 300);
    };

    // The hand is still on the knob right after the release: ignored.
    rig.step(100);
    rig.knobs[P1] = 2500;
    bool ignored = true;
    for (int i = 0; i < 350; ++i) {
        rig.step();
        ignored &= std::abs(rig.sounding(P1) - track(rig.now)) <= 1;
    }
    CHECK(ignored, "for 500 ms after the release the knob doesn't shift the track");
    rig.step(100);

    rig.knobs[P1] = 2700;  // +200 from where it came to rest
    bool shifted = true;
    for (int i = 0; i < 3000; ++i) {
        rig.step();
        shifted &= std::abs(rig.sounding(P1) - (track(rig.now) + 200)) <= 1;
    }
    CHECK(shifted, "then the knob shifts the whole track (+200)");
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_PLAYING, "no take without MODE");

    rig.knobs[P1] = 500;  // -2000: the bottom of the track clamps
    bool clamped = true, sawBottom = false, sawAbove = false;
    for (int i = 0; i < 3000; ++i) {
        rig.step();
        int want = track(rig.now) - 2000;
        if (want < 0) {
            want = 0;
            sawBottom = true;
        } else if (want > 100) {
            sawAbove = true;
        }
        clamped &= std::abs(rig.sounding(P1) - want) <= 1;
    }
    CHECK(clamped && sawBottom && sawAbove, "the shifted track is clamped at 0");

    const uint32_t startCc = recordGesture(rig, 1000, [&rig](uint32_t t) {
        rig.cc(27, (uint8_t)(20 + t / 20));  // 20 -> 70
    });
    rig.step(700);
    rig.cc(27, 60);  // -10
    bool ccShifted = true;
    for (int i = 0; i < 3000; ++i) {
        rig.step();
        const uint32_t pos = (rig.now - startCc) % rig.recorder.getLoopMs(cc27);
        if (pos < 1000) {
            ccShifted &= std::abs(rig.sounding(cc27) - (int)(20 + pos / 20 - 10)) <= 1;
        }
    }
    CHECK(ccShifted, "an MCC control shifts its track too (-10)");
}

static void testMaxLengthAndWrap() {
    std::printf("\n[Test 12] 60 s limit and clock wrap\n");
    Rig rig(0xFFFFFFFFu - 30000u);
    rig.press();
    rig.step(10);
    uint32_t start = 0;
    bool sealedWhileHeld = false;
    for (uint32_t t = 0; t < 65000; ++t) {
        rig.knobs[P1] = (uint16_t)(1100 + (t < 60000 ? t : 60000) / 25);
        rig.step();
        if (t == 0) start = rig.now;
        if (t == 60000) {
            sealedWhileHeld = rig.recorder.getTrackState(P1) == R::TRACK_PLAYING &&
                              rig.recorder.isHolding();
        }
    }
    CHECK(sealedWhileHeld, "a take reaching 60 s loops while MODE is still held");
    CHECK(rig.recorder.getTakeMs(P1) == R::MAX_TAKE_MS, "take = 60000 ms");
    CHECK(ledState, "LED solid once the take is full");
    rig.release();
    CHECK(rig.recorder.getTrackState(P1) == R::TRACK_PLAYING,
          "the release after a full take is not a click");
    CHECK(rig.recorder.getLoopMs(P1) == 62000, "loop = 60 s + 2 s glide");
    CHECK(rig.now < start, "the millisecond clock wrapped during the take");

    bool exact = true;
    for (uint32_t pos : {1000u, 30010u, 59990u}) {
        rig.step(start + 2 * 62000 + pos - rig.now);
        exact &= std::abs(rig.sounding(P1) - (int)(1100 + pos / 25)) <= 1;
    }
    CHECK(exact, "the second pass plays the take across the wrap");
}

static void testStall() {
    std::printf("\n[Test 13] a main-loop stall leaves no gaps in a take\n");
    Rig rig;
    rig.press();
    rig.step(10);
    uint32_t start = 0;
    for (uint32_t t = 0; t < 400; ++t) {
        rig.knobs[P1] = (uint16_t)(1100 + t);
        rig.step();
        if (t == 0) start = rig.now;
    }
    rig.now += 500;  // no update() for 500 ms
    for (uint32_t t = 900; t <= 1200; ++t) {
        rig.knobs[P1] = (uint16_t)(1100 + t);
        rig.step();
    }
    rig.release();
    CHECK(rig.recorder.getTakeMs(P1) == 1200, "the take spans the stall");
    const uint32_t loop = rig.recorder.getLoopMs(P1);
    bool filled = true;
    for (uint32_t pos : {420u, 600u, 880u}) {
        rig.step(start + 2 * loop + pos - rig.now);
        filled &= rig.sounding(P1) == 2000;  // the first value after the stall
    }
    CHECK(filled, "the frames inside the stall carry the value read after it");
    rig.step(start + 3 * loop + 1000 - rig.now);
    CHECK(std::abs(rig.sounding(P1) - 2100) <= 1, "after the stall the take is in time");
}

static void testLed() {
    std::printf("\n[Test 14] LED: off live, blink recording, solid playback\n");
    Rig rig;
    ledChanges = 0;
    rig.step(2000);
    CHECK(!ledState && ledChanges == 0, "live: off, never written");
    rig.press();
    rig.step(500);
    CHECK(!ledState && ledChanges == 0, "MODE held, nothing moved: off");
    rig.knobs[P1] = 1100;
    CHECK(sawBlink(rig, 400), "recording: blinks");
    rig.release();
    ledChanges = 0;
    rig.step(4000);
    CHECK(ledState && ledChanges == 0, "playback: solid (no dark marks)");

    // A second take while the first track plays.
    rig.press();
    rig.step(100);
    CHECK(ledState, "MODE held over a playing track: still solid");
    rig.cc(27, 60);
    CHECK(sawBlink(rig, 400), "recording another control: blinks");
    rig.release();
    CHECK(ledState, "released: solid");
    rig.step(500);
    rig.click();
    CHECK(!ledState, "tracks removed: off");
    ledChanges = 0;
    rig.step(2000);
    CHECK(!ledState && ledChanges == 0, "and it stays off through the glide back");
}

int main() {
    std::printf("FreeMotionRecorder self-tests\n");
    testLifecycle();
    testPlayback();
    testLoopJoin();
    testIndependentTracks();
    testOneHoldTwoControls();
    testReRecord();
    testRemove();
    testHoldsThatRecordNothing();
    testMccBanks();
    testButtonBounce();
    testOffset();
    testMaxLengthAndWrap();
    testStall();
    testLed();

    std::printf("\n%d checks, %d failure(s)\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
