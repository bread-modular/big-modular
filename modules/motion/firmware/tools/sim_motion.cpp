// Host test of the MOTION recorder (motion/MotionRecorder.h) and the board
// helpers (motion/MotionIo.h). The FRAM is an array with the same layout
// rules (MAX_FRAMES per track, headers); every access is bounds-checked.
//
//   ./test.sh      (exit 0 = pass)

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "MotionIo.h"
#include "MotionRecorder.h"

using namespace motion;

static int failures = 0;
static int checks = 0;

#define CHECK(cond, ...)                                              \
    do {                                                              \
        ++checks;                                                     \
        if (!(cond)) {                                                \
            ++failures;                                               \
            std::printf("FAIL %s:%d: ", __FILE__, __LINE__);          \
            std::printf(__VA_ARGS__);                                 \
            std::printf("\n");                                        \
        }                                                             \
    } while (0)

struct RamStore {
    static constexpr uint16_t MAX_FRAMES = motion::MAX_FRAMES;
    uint16_t data[4][MAX_FRAMES];
    uint16_t hdrFrames[4];
    uint16_t hdrGain[4];
    long reads = 0, writes = 0, headerWrites = 0;
    bool oob = false;

    RamStore() { clear(); }
    void clear() {
        std::memset(data, 0xEE, sizeof(data));
        std::memset(hdrFrames, 0, sizeof(hdrFrames));
        std::memset(hdrGain, 0, sizeof(hdrGain));
    }
    uint16_t readFrame(uint8_t t, uint16_t f) {
        ++reads;
        if (t >= 4 || f >= MAX_FRAMES) { oob = true; return 0; }
        return data[t][f];
    }
    void writeFrame(uint8_t t, uint16_t f, uint16_t v) {
        ++writes;
        if (t >= 4 || f >= MAX_FRAMES || v > KNOB_MAX) { oob = true; return; }
        data[t][f] = v;
    }
    void writeHeader(uint8_t t, uint16_t frames, uint16_t gain) {
        ++headerWrites;
        if (t >= 4 || frames > MAX_FRAMES || gain > 4096) { oob = true; return; }
        hdrFrames[t] = frames;
        hdrGain[t] = gain;
    }
};

typedef MotionRecorder<RamStore> Rec;

// A small rig: time, knobs, REC, DEL; tick() advances one millisecond.
// Output codes equal knob positions (-5..+5 V).
struct Rig {
    RamStore& store;
    Rec rec;
    uint32_t now = 1000;
    uint16_t knobs[4] = {2048, 2048, 2048, 2048};
    bool recDown = false;
    bool delDown = false;
    int maxStep[4] = {0, 0, 0, 0};
    uint16_t prev[4] = {0, 0, 0, 0};
    bool havePrev = false;

    explicit Rig(RamStore& s) : store(s), rec(s) { rec.begin(now); }
    void tick(uint32_t ms = 1) {
        for (uint32_t k = 0; k < ms; ++k) {
            ++now;
            rec.update(now, knobs, recDown, delDown);
            for (int i = 0; i < 4; ++i) {
                int d = (int)rec.out(i) - (int)prev[i];
                if (d < 0) d = -d;
                if (havePrev && d > maxStep[i]) maxStep[i] = d;
                prev[i] = rec.out(i);
            }
            havePrev = true;
        }
    }
    void resetSteps() { for (int i = 0; i < 4; ++i) maxStep[i] = 0; }
};

// Record knob 0 as a ramp lo -> hi over rampMs, then hold, release.
static void recordRamp(Rig& r, int knob, uint16_t lo, uint16_t hi, uint32_t rampMs) {
    r.knobs[knob] = lo;
    r.tick(50);
    r.recDown = true;
    r.tick(50);
    for (uint32_t t = 0; t <= rampMs; ++t) {
        r.knobs[knob] = (uint16_t)(lo + (int32_t)(hi - lo) * (int32_t)t / (int32_t)rampMs);
        r.tick();
    }
    r.recDown = false;
    r.tick();
}

static void testHelpers() {
    CHECK(MAX_FRAMES == 4088, "MAX_FRAMES %u", MAX_FRAMES);
    CHECK(frameAddr(3, MAX_FRAMES - 1) + 1 == FRAM_SIZE - 1,
          "last frame byte 0x%x", frameAddr(3, MAX_FRAMES - 1) + 1);
    CHECK(frameAddr(0, 0) == FRAM_DATA && headerAddr(3) + 4 <= FRAM_DATA, "layout");
    CHECK(Rec::MAX_TAKE_MS == 81720, "max take %u ms", (unsigned)Rec::MAX_TAKE_MS);

    // LED: 0 V off, +5 V full and steady, -5 V full and blinking.
    CHECK(motionLed(DAC_ZERO, true) == 0 && motionLed(DAC_ZERO, false) == 0, "LED off at 0 V");
    CHECK(motionLed(4095, true) == LED_FULL && motionLed(4095, false) == LED_FULL,
          "LED +5 V steady full %u %u", motionLed(4095, true), motionLed(4095, false));
    CHECK(motionLed(0, true) == LED_FULL && motionLed(0, false) == 0, "LED -5 V blinks %u %u",
          motionLed(0, true), motionLed(0, false));
    for (uint16_t v = DAC_ZERO + 1; v <= 4095; ++v) {
        if (motionLed(v, false) < motionLed(v - 1, false)) {
            CHECK(false, "LED not monotonic up at %u", v); break;
        }
    }
    for (int v = DAC_ZERO - 1; v >= 0; --v) {
        if (motionLed((uint16_t)v, true) < motionLed((uint16_t)(v + 1), true) ||
            motionLed((uint16_t)v, false) != 0) {
            CHECK(false, "LED not monotonic / blinking down at %d", v); break;
        }
    }

    KnobFilter f;
    CHECK(f.step(0) == 0, "knob 0");
    for (int i = 0; i < 100; ++i) f.step(4095);
    CHECK(f.value == 4095, "knob reaches 4095 (%u)", f.value);
    for (int i = 0; i < 100; ++i) f.step(10);
    CHECK(f.value == 0, "knob end dead zone (%u)", f.value);
    // A resting knob with +-1 count of noise does not move the output.
    KnobFilter g;
    for (int i = 0; i < 200; ++i) g.step(2000);
    const uint16_t rest = g.value;
    int changes = 0;
    for (int i = 0; i < 1000; ++i) {
        const uint16_t before = g.value;
        g.step((uint16_t)(2000 + ((i * 7) % 3) - 1));
        if (g.value != before) ++changes;
    }
    CHECK(changes == 0, "resting knob flickers %d times (rest %u)", changes, rest);
}

static void testLive() {
    RamStore s;
    Rig r(s);
    r.knobs[0] = 0;
    r.knobs[1] = 4095;
    r.knobs[2] = 1234;
    r.tick(10);
    CHECK(r.rec.out(0) == 0 && r.rec.out(1) == 4095 && r.rec.out(2) == 1234 &&
          r.rec.state(2) == Rec::LIVE, "live -5..+5 V %u %u %u", r.rec.out(0), r.rec.out(1),
          r.rec.out(2));
    CHECK(s.writes == 0 && s.headerWrites == 0, "live writes nothing");
}

static void testRecordAndLoop() {
    RamStore s;
    Rig r(s);
    recordRamp(r, 0, 1000, 3000, 1000);
    CHECK(r.rec.state(0) == Rec::PLAYING, "playing after release (%d)", r.rec.state(0));
    CHECK(r.rec.state(1) == Rec::LIVE, "other knob live");
    const uint16_t frames = r.rec.frames(0);
    CHECK(frames >= 50 && frames <= 53, "frames %u", frames);
    CHECK(s.hdrFrames[0] == frames, "header frames %u vs %u", s.hdrFrames[0], frames);
    CHECK(!s.oob, "store bounds");
    // Release value = last frame; loop = take + tail (a quarter, step 2000 >= 1024).
    const uint32_t take = (uint32_t)(frames - 1) * Rec::FRAME_MS;
    CHECK(r.rec.loopMs(0) == take + 250, "loop %u, take %u", (unsigned)r.rec.loopMs(0), (unsigned)take);
    // Right after the release the output is still at the end of the take and
    // glides back to the start; nothing steps for whole loops.
    CHECK(r.rec.out(0) >= 2990, "out at release %u", r.rec.out(0));
    r.resetSteps();
    uint16_t lo = 4095, hi = 0;
    for (int k = 0; k < 4000; ++k) {
        const uint16_t before = r.rec.out(0);
        r.tick();
        if (std::abs((int)r.rec.out(0) - (int)before) > 20) {
            std::printf("  step %d at loop pos %u (loop %u)\n", (int)r.rec.out(0) - (int)before,
                        (unsigned)(k % r.rec.loopMs(0)), (unsigned)r.rec.loopMs(0));
        }
        if (r.rec.out(0) < lo) lo = r.rec.out(0);
        if (r.rec.out(0) > hi) hi = r.rec.out(0);
    }
    CHECK(r.maxStep[0] <= 20, "max step while looping %d", r.maxStep[0]);
    // The take starts at the first move (MOVE_THRESHOLD past the press).
    CHECK(lo <= 1000 + Rec::MOVE_THRESHOLD + 5 && hi >= 2990, "loop range %u..%u", lo, hi);
    // Reads: one per frame while playing, not one per millisecond.
    const long reads = s.reads;
    r.tick(1000);
    CHECK(s.reads - reads < 120, "reads per second %ld", s.reads - reads);
}

static uint16_t loopPeak(Rig& r, int i) {
    uint16_t peak = 0;
    const uint32_t loop = r.rec.loopMs(i);
    for (uint32_t k = 0; k < loop; ++k) { r.tick(); if (r.rec.out(i) > peak) peak = r.rec.out(i); }
    return peak;
}

// For 1 s after the release the knob does nothing; after that it scales the
// take towards 0 V: from where it first moves, down to 0 = gain 0, up to 4095
// = gain 1, no jump; the gain is saved once the knob rests 1 s.
static void testIgnoreThenAttenuate() {
    RamStore s;
    Rig r(s);
    recordRamp(r, 2, 2048, 4000, 1000);  // 0 .. +4.8 V, knob left at 4000
    const uint32_t loop = r.rec.loopMs(2);
    static uint16_t base[4000];
    for (uint32_t k = 0; k < 900 && k < loop; ++k) { r.tick(); base[k] = r.rec.out(2); }
    // Within the first second the knob is ignored (the hand leaves it).
    RamStore s2;
    Rig q(s2);
    recordRamp(q, 2, 2048, 4000, 1000);
    q.knobs[2] = 500;
    int bad = 0;
    for (uint32_t k = 0; k < 900 && k < loop; ++k) { q.tick(); if (q.rec.out(2) != base[k]) ++bad; }
    CHECK(bad == 0 && q.rec.gain(2) == Rec::GAIN_ONE, "knob ignored in the first second (%d, %u)",
          bad, q.rec.gain(2));
    // ... and where it was left at the end of that second is the start: no jump.
    q.tick(200);
    CHECK(q.rec.gain(2) == Rec::GAIN_ONE, "no gain jump after the second (%u)", q.rec.gain(2));
    q.resetSteps();
    for (int k = 500; k >= 300; k -= 2) { q.knobs[2] = (uint16_t)k; q.tick(); }
    CHECK(q.rec.gain(2) < Rec::GAIN_ONE * 7 / 10 && q.rec.gain(2) > Rec::GAIN_ONE / 2,
          "knob attenuates after the second (%u)", q.rec.gain(2));
    CHECK(q.maxStep[2] <= 30, "attenuation steps %d", q.maxStep[2]);

    r.tick(1000);
    CHECK(r.rec.gain(2) == Rec::GAIN_ONE, "resting knob: gain 1");
    uint16_t peak = loopPeak(r, 2);
    CHECK(peak >= 3990, "peak before %u", peak);
    // Knob from 4000 down to 1000: from the knob at 4000 - 49 the gain goes
    // to 1000 / 3951 of 1.
    r.resetSteps();
    for (int k = 4000; k >= 1000; k -= 5) { r.knobs[2] = (uint16_t)k; r.tick(); }
    r.tick(5);
    const int g = r.rec.gain(2);
    CHECK(g > 1000 && g < 1080, "gain at knob 1000: %d", g);
    CHECK(r.maxStep[2] <= 30, "attenuation steps %d", r.maxStep[2]);
    CHECK(s.hdrGain[2] == Rec::GAIN_ONE, "gain not saved while turning");
    r.tick(1100);
    CHECK(s.hdrGain[2] == g, "gain saved at rest %u vs %d", s.hdrGain[2], g);
    peak = 0;
    uint16_t low = 4095;
    for (uint32_t k = 0; k < loop; ++k) {
        r.tick();
        if (r.rec.out(2) > peak) peak = r.rec.out(2);
        if (r.rec.out(2) < low) low = r.rec.out(2);
    }
    const int want = 2048 + (4000 - 2048) * g / 4096;
    CHECK(std::abs((int)peak - want) <= 4 && low >= 2048, "attenuated peak %u (want %d), low %u",
          peak, want, low);
    // Knob down to 0: silent (0 V); back up to the top: full again.
    for (int k = 1000; k >= 0; k -= 5) { r.knobs[2] = (uint16_t)k; r.tick(); }
    r.tick(5);
    CHECK(r.rec.gain(2) == 0 && r.rec.out(2) == 2048, "gain 0 -> 0 V (%u, %u)", r.rec.gain(2),
          r.rec.out(2));
    r.tick(1500);  // rest, the next move starts from gain 0 at knob 0
    for (int k = 0; k <= 4095; k += 5) { r.knobs[2] = (uint16_t)k; r.tick(); }
    r.knobs[2] = 4095;
    r.tick(5);
    CHECK(r.rec.gain(2) == Rec::GAIN_ONE, "gain back to 1 (%u)", r.rec.gain(2));
    r.tick(1100);
    CHECK(s.hdrGain[2] == Rec::GAIN_ONE, "gain 1 saved");
    // The other tracks and the live knobs are not touched.
    CHECK(r.rec.state(0) == Rec::LIVE && r.rec.out(0) == r.knobs[0], "live knob unchanged");

    // A take that ends with the knob at 0: turn it up (gain stays 1), let it
    // rest, then down attenuates from there.
    RamStore s3;
    Rig e(s3);
    recordRamp(e, 1, 3000, 0, 800);
    e.tick(1100);
    for (int k = 0; k <= 3000; k += 5) { e.knobs[1] = (uint16_t)k; e.tick(); }
    CHECK(e.rec.gain(1) == Rec::GAIN_ONE, "up from 0 keeps gain 1 (%u)", e.rec.gain(1));
    e.tick(1100);
    for (int k = 3000; k >= 1500; k -= 5) { e.knobs[1] = (uint16_t)k; e.tick(); }
    CHECK(std::abs((int)e.rec.gain(1) - 2048) < 60, "then down to half (%u)", e.rec.gain(1));

    // A take loaded at power-up: the knob attenuates from its first move.
    RamStore s4 = s;
    s4.hdrGain[2] = Rec::GAIN_ONE;
    Rec p(s4);
    p.begin(0);
    p.load(2, s4.hdrFrames[2], s4.hdrGain[2], 0);
    uint16_t knobs[4] = {2048, 2048, 2000, 2048};
    uint32_t t = 0;
    for (; t < 100; ++t) p.update(t, knobs, false, false);
    CHECK(p.gain(2) == Rec::GAIN_ONE, "loaded take: knob at rest does nothing (%u)", p.gain(2));
    for (int k = 2000; k >= 1000; k -= 5) { knobs[2] = (uint16_t)k; p.update(++t, knobs, false, false); }
    CHECK(p.gain(2) < 2300 && p.gain(2) > 2000, "loaded take attenuates (%u)", p.gain(2));
}

// DEL + a knob: that take is deleted, the other takes play on; DEL alone and
// REC have nothing to do with each other.
static void testDeleteOne() {
    RamStore s;
    Rig r(s);
    recordRamp(r, 0, 500, 3500, 800);
    recordRamp(r, 1, 3500, 500, 800);
    r.tick(1500);
    CHECK(r.rec.count(Rec::PLAYING) == 2, "two takes");
    // A DEL click with no knob: nothing changes.
    const long hw = s.headerWrites;
    r.delDown = true; r.tick(100); r.delDown = false; r.tick(100);
    CHECK(r.rec.count(Rec::PLAYING) == 2 && s.headerWrites == hw, "DEL click alone does nothing");
    r.delDown = true;
    r.tick(60);
    r.resetSteps();
    for (int k = 0; k < 300; ++k) { r.knobs[0] = (uint16_t)(3500 - k * 5); r.tick(); }
    CHECK(s.hdrFrames[0] == 0 && s.hdrFrames[1] != 0, "take 0 deleted only (%u, %u)",
          s.hdrFrames[0], s.hdrFrames[1]);
    CHECK(r.rec.state(0) != Rec::RECORDING && r.rec.state(1) == Rec::PLAYING, "not recorded");
    CHECK(r.rec.eraseHoldMs(r.now) == 0, "a knob move stops the erase countdown");
    r.tick(5000);
    CHECK(r.rec.state(1) == Rec::PLAYING, "no erase after a knob move in the hold");
    r.delDown = false;
    r.tick(700);
    CHECK(r.rec.state(0) == Rec::LIVE && r.rec.out(0) == r.knobs[0], "knob 0 live (%d, %u)",
          r.rec.state(0), r.rec.out(0));
    CHECK(r.maxStep[0] <= 30, "delete glide step %d", r.maxStep[0]);
    CHECK(r.rec.state(1) == Rec::PLAYING, "take 1 plays on");
    // DEL first, then REC pressed in it: the knob deletes, nothing records.
    r.delDown = true; r.tick(60);
    r.recDown = true; r.tick(60);
    for (int k = 0; k < 200; ++k) { r.knobs[1] = (uint16_t)(1000 + k * 5); r.tick(); }
    CHECK(r.rec.count(Rec::RECORDING) == 0, "REC ignored in a DEL hold");
    r.delDown = false; r.tick(60);
    for (int k = 0; k < 200; ++k) { r.knobs[1] = (uint16_t)(2000 - k * 5); r.tick(); }
    CHECK(r.rec.count(Rec::RECORDING) == 0, "REC still held from the DEL hold: no take");
    r.recDown = false; r.tick(60);
    CHECK(s.hdrFrames[1] == 0 && r.rec.count(Rec::PLAYING) == 0, "DEL then REC deletes");
    // REC first, then DEL pressed in it: the knob records.
    r.recDown = true; r.tick(60);
    r.delDown = true; r.tick(60);
    for (int k = 0; k < 300; ++k) { r.knobs[2] = (uint16_t)(1000 + k * 5); r.tick(); }
    r.delDown = false; r.tick(60);
    r.recDown = false; r.tick(60);
    CHECK(r.rec.state(2) == Rec::PLAYING, "REC then DEL records (%d)", r.rec.state(2));
}

static void testEraseAndNoErase() {
    RamStore s;
    Rig r(s);
    recordRamp(r, 0, 500, 3500, 800);
    recordRamp(r, 3, 3500, 100, 800);
    CHECK(r.rec.count(Rec::PLAYING) == 2, "two tracks");
    // REC held still for 6 s: REC only records, never erases.
    r.recDown = true;
    r.tick(6000);
    CHECK(r.rec.count(Rec::PLAYING) == 2 && !r.rec.takeEraseEvent(), "REC hold does not erase");
    CHECK(r.rec.eraseHoldMs(r.now) == 0, "no countdown on REC");
    r.recDown = false;
    r.tick(100);
    // 4.9 s of DEL with no move: nothing erased.
    r.delDown = true;
    r.tick(4900);
    CHECK(r.rec.count(Rec::PLAYING) == 2 && s.hdrFrames[0] != 0, "no erase at 4.9 s");
    CHECK(r.rec.eraseHoldMs(r.now) >= 4800, "countdown %u", (unsigned)r.rec.eraseHoldMs(r.now));
    r.delDown = false;
    r.tick(100);
    // DEL held 5 s still: every take erased, outputs glide back to their knobs.
    r.delDown = true;
    r.tick(4999);
    CHECK(!r.rec.takeEraseEvent(), "no erase before 5 s");
    r.tick(2);
    CHECK(r.rec.takeEraseEvent(), "erase event");
    CHECK(s.hdrFrames[0] == 0 && s.hdrFrames[3] == 0, "headers cleared");
    r.resetSteps();
    r.tick(700);
    r.delDown = false;
    r.tick(10);
    for (int i = 0; i < 4; ++i) {
        CHECK(r.rec.state(i) == Rec::LIVE && r.rec.out(i) == r.knobs[i],
              "track %d live after erase (%d, %u)", i, r.rec.state(i), r.rec.out(i));
    }
    CHECK(r.maxStep[0] <= 30 && r.maxStep[3] <= 30, "erase glide steps %d %d", r.maxStep[0], r.maxStep[3]);
}

static void testShortTakeAndBounce() {
    RamStore s;
    Rig r(s);
    r.recDown = true;
    r.tick(100);
    r.knobs[0] = 3000;  // moved 100 ms before the release
    r.tick(100);
    r.recDown = false;
    r.tick(700);
    CHECK(r.rec.state(0) == Rec::LIVE && s.hdrFrames[0] == 0, "short take dropped");

    // Bounce on the press and on the release: one take, not cut short.
    Rig b(s);
    b.recDown = true; b.tick(2); b.recDown = false; b.tick(3); b.recDown = true;
    b.tick(50);
    for (int k = 0; k < 500; ++k) { b.knobs[1] = (uint16_t)(2048 + k * 3); b.tick(); }
    b.recDown = false; b.tick(3); b.recDown = true; b.tick(3); b.recDown = false;
    b.tick(50);
    CHECK(b.rec.state(1) == Rec::PLAYING, "bounced release closes once (%d)", b.rec.state(1));
    CHECK(b.rec.frames(1) >= 25, "take kept its length (%u)", b.rec.frames(1));
}

static void testReRecordJoin() {
    RamStore s;
    Rig r(s);
    recordRamp(r, 0, 1000, 3000, 1000);
    r.tick(1500);
    // Re-record: the knob is far from what plays; the join fades, no step.
    r.resetSteps();
    r.recDown = true;
    r.tick(50);
    r.knobs[0] = 300;  // a jump of the knob itself
    r.tick();
    const int jumpAtTakeover = r.maxStep[0];
    r.tick(1000);
    r.recDown = false;
    r.tick(10);
    CHECK(jumpAtTakeover <= 40, "take-over step %d", jumpAtTakeover);
    CHECK(r.rec.state(0) == Rec::PLAYING, "re-recorded");
    // Replaced, not overdubbed: the new take holds the knob only (the join
    // glide is heard, not recorded), so the loop is flat at the knob.
    const uint16_t frames = r.rec.frames(0);
    int other = 0;
    for (uint16_t f = 0; f < frames; ++f) if (s.data[0][f] != 300) ++other;
    CHECK(frames >= 50 && other == 0, "new take = knob only (%u frames, %d others)", frames, other);
    r.tick(400);
    int off = 0;
    for (uint32_t k = 0; k < 3000; ++k) { r.tick(); if (r.rec.out(0) != 300) ++off; }
    CHECK(off == 0, "loop plays the new take only (%d samples off)", off);
    // A take shorter than the join glide: no step into the loop.
    r.resetSteps();
    r.recDown = true;
    r.tick(50);
    r.knobs[0] = 3800;
    r.tick(250);
    r.recDown = false;
    r.tick(1000);
    CHECK(r.rec.state(0) == Rec::PLAYING && r.maxStep[0] <= 40, "short re-take step %d",
          r.maxStep[0]);
}

static void testMaxTakeAndPersistence() {
    RamStore s;
    Rig r(s);
    r.recDown = true;
    r.tick(20);
    for (uint32_t k = 0; k < Rec::MAX_TAKE_MS + 5000; ++k) {
        r.knobs[2] = (uint16_t)(100 + (k / 10) % 3000);
        r.tick();
    }
    CHECK(r.rec.state(2) == Rec::PLAYING, "sealed at the maximum (%d)", r.rec.state(2));
    CHECK(r.rec.frames(2) == MAX_FRAMES && s.hdrFrames[2] == MAX_FRAMES, "full take %u / %u",
          r.rec.frames(2), s.hdrFrames[2]);
    CHECK(!s.oob, "store bounds at the maximum");
    r.recDown = false;
    r.tick(1000);

    // Power cycle: a new recorder loads the headers and plays the same loop
    // (same knob = no shift). Compare one loop sample by sample after aligning
    // the start.
    RamStore copy = s;
    Rec again(copy);
    uint32_t t0 = 50000;
    again.begin(t0);
    copy.hdrGain[2] = Rec::GAIN_ONE / 2;
    for (int i = 0; i < 4; ++i) again.load((uint8_t)i, copy.hdrFrames[i], copy.hdrGain[i], t0);
    CHECK(again.state(2) == Rec::PLAYING && again.state(0) == Rec::LIVE, "loaded");
    uint16_t knobs[4] = {2048, 2048, 77, 2048};
    // Half gain: the take scaled towards 0 V (2048).
    const auto half = [](uint16_t c) { return (int)(2048 + ((int)c - 2048) / 2); };
    again.update(t0, knobs, false, false);
    CHECK(std::abs((int)again.out(2) - half(copy.data[2][0])) <= 1, "first frame after load %u vs %d",
          again.out(2), half(copy.data[2][0]));
    again.update(t0 + 20 * 100, knobs, false, false);
    CHECK(std::abs((int)again.out(2) - half(copy.data[2][100])) <= 1, "frame 100 after load %u vs %d",
          again.out(2), half(copy.data[2][100]));
}

static void testPowerCutMidTake() {
    RamStore s;
    Rig r(s);
    r.recDown = true;
    r.tick(20);
    for (int k = 0; k < 1000; ++k) { r.knobs[3] = (uint16_t)(1000 + k); r.tick(); }
    // Power cut now: the header already covers what was recorded.
    CHECK(s.hdrFrames[3] >= 49, "header follows the take (%u)", s.hdrFrames[3]);
    Rec again(s);
    again.begin(0);
    again.load(3, s.hdrFrames[3], s.hdrGain[3], 0);
    CHECK(again.state(3) == Rec::PLAYING, "partial take loads");
}

int main() {
    testHelpers();
    testLive();
    testRecordAndLoop();
    testIgnoreThenAttenuate();
    testDeleteOne();
    testEraseAndNoErase();
    testShortTakeAndBounce();
    testReRecordJoin();
    testMaxTakeAndPersistence();
    testPowerCutMidTake();
    std::printf("%d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
