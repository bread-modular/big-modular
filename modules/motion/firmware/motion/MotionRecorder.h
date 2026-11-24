#pragma once

#include <stdint.h>

// MotionRecorder — the MOTION take recorder (four knobs, four tracks).
//
// The modules/16bit cpx4 FreeMotionRecorder behaviour, in integer maths, with
// the frames in a store (the MB85RC256V FRAM on the board, an array on the
// host) instead of RAM, so every take survives power-off:
//
//   * LIVE: a knob without a take drives its output directly.
//   * RECORD: hold REC and move a knob. From its first move (more than
//     MOVE_THRESHOLD counts away from where it was at the press) until REC is
//     released that knob is recorded, a frame every FRAME_MS, straight into
//     the store; its output follows the knob. Every knob moved during the
//     hold gets its own take, from its own first move.
//   * LOOP: at the release each take loops on its own: the take, then a
//     glide from its last value back to its first one (a quarter of the take,
//     TAIL_MIN_MS..TAIL_MAX_MS, shorter in proportion when the step is under
//     a quarter of the range), so the loop never steps. Tracks of different
//     lengths drift against each other.
//   * RE-RECORD: moving a knob that has a track during a hold replaces the
//     track. The output takes over from the value that sounded; the
//     difference fades out over GLIDE_MS and is recorded.
//   * OFFSET: OFFSET_GUARD_MS after the release the knob's position becomes
//     the track's reference; moving the knob then shifts the whole take by
//     (position - reference), clamped to 0..KNOB_MAX. The reference is kept
//     in the store, so after power-up the shift is the knob's distance from
//     where it was then.
//   * ERASE: REC held ERASE_HOLD_MS with no knob moved erases every take;
//     each output glides to its knob over RETURN_MS and is live again. Knobs
//     moved later in that hold are not recorded.
//   * A take shorter than MIN_TAKE_MS is dropped (the knob glides back to
//     live). A take reaching MAX_TAKE_MS closes itself and loops while REC is
//     still held; that knob records nothing more in this hold.
//
// Store (template parameter) layout contract: MAX_FRAMES frames per track,
// and
//   uint16_t readFrame(uint8_t track, uint16_t frame);
//   void writeFrame(uint8_t track, uint16_t frame, uint16_t value);
//   void writeHeader(uint8_t track, uint16_t frames, uint16_t ref);
// The header is the take length in frames (0 = no take) and the offset
// reference. A take is written as it is recorded and its header follows each
// frame, so a power cut mid-take keeps what was recorded until then.
//
// Times are milliseconds on a free-running uint32_t clock (wrap-safe).
// No Arduino dependency: motion.ino passes the time, the knobs and REC.
template <class Store>
class MotionRecorder {
public:
    enum State : uint8_t {
        LIVE = 0,    // no track: output = knob
        RECORDING,   // REC held, the knob moved
        PLAYING,     // looping
        RETURNING,   // erased or dropped: gliding to the knob
    };

    static const uint8_t TRACKS = 4;
    static const uint16_t KNOB_MAX = 4095;
    static const uint16_t MAX_FRAMES = Store::MAX_FRAMES;
    static const uint32_t FRAME_MS = 20;                 // 50 frames per second
    // Frames 0..MAX_FRAMES - 2 every FRAME_MS, then the value at the end.
    static const uint32_t MAX_TAKE_MS = (uint32_t)(MAX_FRAMES - 2) * FRAME_MS;
    static const uint32_t MIN_TAKE_MS = 200;
    static const uint32_t ERASE_HOLD_MS = 5000;
    static const uint32_t DEBOUNCE_MS = 30;
    static const uint16_t MOVE_THRESHOLD = 48;           // as cpx4 (12-bit)
    static const uint32_t GLIDE_MS = 300;
    static const uint32_t RETURN_MS = 600;
    static const uint32_t TAIL_TAKE_DIVISOR = 4;
    static const uint32_t TAIL_MIN_MS = 250;
    static const uint32_t TAIL_MAX_MS = 2000;
    static const uint32_t TAIL_FULL_STEP = (KNOB_MAX + 1) / 4;
    static const uint32_t OFFSET_GUARD_MS = 500;

    explicit MotionRecorder(Store& store) : store_(store) {}

    // Every knob live, no tracks; REC up.
    void begin(uint32_t nowMs) {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            tracks_[i] = Track();
        }
        down_ = false;
        haveEdge_ = false;
        holding_ = false;
        moved_ = false;
        erased_ = false;
        eraseEvent_ = false;
        (void)nowMs;
    }

    // A take found in the store at power-up (its header): loops from its
    // start, shifted by the knob's distance from ref. Fewer than two frames
    // is no take.
    void load(uint8_t i, uint16_t frames, uint16_t ref, uint32_t nowMs) {
        if (i >= TRACKS || frames < 2 || frames > MAX_FRAMES) {
            return;
        }
        Track& t = tracks_[i];
        t.frames = frames;
        t.first = clampKnob(store_.readFrame(i, 0));
        t.last = clampKnob(store_.readFrame(i, (uint16_t)(frames - 1)));
        t.takeMs = (uint32_t)(frames - 1) * FRAME_MS;
        t.tailMs = tailOf(t);
        t.ref = ref > KNOB_MAX ? KNOB_MAX : ref;
        t.refLatched = true;
        t.startMs = nowMs;
        t.closedMs = nowMs;
        t.cached = NO_FRAME;
        t.state = PLAYING;
    }

    // Recording on or off (off: no FRAM on the bus). Off does not stop a take.
    void setRecordEnabled(bool on) { recordEnabled_ = on; }

    // Call every millisecond with the conditioned knobs (0..KNOB_MAX) and the
    // raw REC level (true = pressed, bounce included).
    void update(uint32_t nowMs, const uint16_t live[TRACKS], bool recDown) {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            live_[i] = live[i] > KNOB_MAX ? KNOB_MAX : live[i];
        }
        button(recDown, nowMs);
        if (holding_ && !erased_) {
            detectMoves(nowMs);
            if (!moved_ && (uint32_t)(nowMs - pressMs_) >= ERASE_HOLD_MS) {
                eraseAll(nowMs);
            }
        }
        for (uint8_t i = 0; i < TRACKS; ++i) {
            run(i, nowMs);
        }
    }

    // Value each output plays, 0..KNOB_MAX.
    uint16_t out(uint8_t i) const { return i < TRACKS ? tracks_[i].out : 0; }
    State state(uint8_t i) const { return i < TRACKS ? tracks_[i].state : LIVE; }
    uint16_t frames(uint8_t i) const {
        return i < TRACKS && tracks_[i].state == PLAYING ? tracks_[i].frames : 0;
    }
    uint16_t ref(uint8_t i) const { return i < TRACKS ? tracks_[i].ref : 0; }
    uint32_t loopMs(uint8_t i) const {
        return i < TRACKS && tracks_[i].state == PLAYING
            ? tracks_[i].takeMs + tracks_[i].tailMs : 0;
    }

    bool holding() const { return holding_; }
    bool recording() const { return count(RECORDING) != 0; }
    uint8_t count(State s) const {
        uint8_t n = 0;
        for (uint8_t i = 0; i < TRACKS; ++i) {
            if (tracks_[i].state == s) {
                ++n;
            }
        }
        return n;
    }
    // REC held with no knob moved yet (the erase countdown): ms since the
    // press, 0 otherwise.
    uint32_t idleHoldMs(uint32_t nowMs) const {
        if (!holding_ || moved_ || erased_) {
            return 0;
        }
        const uint32_t ms = nowMs - pressMs_;
        return ms == 0 ? 1 : ms;
    }
    // True once after an erase.
    bool takeEraseEvent() {
        const bool e = eraseEvent_;
        eraseEvent_ = false;
        return e;
    }

private:
    static const uint16_t NO_FRAME = 0xFFFF;

    struct Track {
        State state = LIVE;
        bool sealed = false;       // closed itself at MAX_TAKE_MS in this hold
        bool refLatched = false;
        uint16_t frames = 0;       // frames stored
        uint16_t hold = 0;         // knob at the REC press
        uint16_t ref = 0;          // knob position the offset starts from
        uint16_t out = 0;          // value that plays
        uint16_t first = 0;        // frame 0
        uint16_t last = 0;         // last frame
        uint16_t cached = NO_FRAME;  // frame of a / b
        uint16_t a = 0, b = 0;     // frames cached and cached + 1
        int16_t glide = 0;         // join difference, faded out
        uint32_t startMs = 0;      // RECORDING: first move; PLAYING: this pass
        uint32_t takeMs = 0;       // (frames - 1) * FRAME_MS
        uint32_t tailMs = 0;       // glide back to the first frame
        uint32_t closedMs = 0;
        uint32_t glideStartMs = 0;
    };

    static uint16_t clampKnob(int32_t v) {
        if (v <= 0) return 0;
        if (v >= KNOB_MAX) return KNOB_MAX;
        return (uint16_t)v;
    }

    // Glide shares are Q12: 0..ONE.
    static const int32_t ONE = 4096;

    // 0..ONE -> 0..ONE, no slope at either end (smoothstep).
    static int32_t ease(int32_t s) {
        if (s <= 0) return 0;
        if (s >= ONE) return ONE;
        return (((s * s) >> 12) * (3 * ONE - 2 * s)) >> 12;
    }

    // Share (0..ONE) of a join difference still added: ONE at the join, 0
    // from lengthMs on.
    static int32_t fade(const Track& t, uint32_t nowMs, uint32_t lengthMs) {
        const uint32_t e = nowMs - t.glideStartMs;
        if (e >= lengthMs) {
            return 0;
        }
        return ONE - ease((int32_t)(e * ONE / lengthMs));
    }

    static uint32_t tailOf(const Track& t) {
        const int32_t step = (int32_t)t.last - (int32_t)t.first;
        const uint32_t size = (uint32_t)(step < 0 ? -step : step);
        uint32_t tail = t.takeMs / TAIL_TAKE_DIVISOR;
        if (tail < TAIL_MIN_MS) tail = TAIL_MIN_MS;
        if (tail > TAIL_MAX_MS) tail = TAIL_MAX_MS;
        if (size < TAIL_FULL_STEP) {
            tail = tail * size / TAIL_FULL_STEP;
        }
        return tail;
    }

    void button(bool raw, uint32_t nowMs) {
        if (raw == down_) {
            return;
        }
        if (haveEdge_ && (uint32_t)(nowMs - edgeMs_) < DEBOUNCE_MS) {
            return;
        }
        haveEdge_ = true;
        edgeMs_ = nowMs;
        down_ = raw;
        if (down_) {
            holding_ = true;
            pressMs_ = nowMs;
            moved_ = false;
            erased_ = false;
            for (uint8_t i = 0; i < TRACKS; ++i) {
                tracks_[i].hold = live_[i];
                tracks_[i].sealed = false;
            }
        } else if (holding_) {
            holding_ = false;
            for (uint8_t i = 0; i < TRACKS; ++i) {
                if (tracks_[i].state == RECORDING) {
                    closeTake(i, nowMs);
                }
            }
        }
    }

    void detectMoves(uint32_t nowMs) {
        if (!recordEnabled_) {
            return;
        }
        for (uint8_t i = 0; i < TRACKS; ++i) {
            Track& t = tracks_[i];
            if (t.state == RECORDING || t.sealed) {
                continue;
            }
            const int32_t d = (int32_t)live_[i] - (int32_t)t.hold;
            if (d > (int32_t)MOVE_THRESHOLD || d < -(int32_t)MOVE_THRESHOLD) {
                startTake(i, nowMs);
            }
        }
    }

    // The knob takes over; if the recorder drove the output, the difference
    // to what played fades out. The old take is gone from here on.
    void startTake(uint8_t i, uint32_t nowMs) {
        Track& t = tracks_[i];
        moved_ = true;
        if (t.state == LIVE) {
            t.out = live_[i];
            t.glide = 0;
        } else {
            t.glide = (int16_t)((int32_t)t.out - (int32_t)live_[i]);
        }
        t.glideStartMs = nowMs;
        t.state = RECORDING;
        t.startMs = nowMs;
        t.frames = 0;
        store_.writeHeader(i, 0, live_[i]);
    }

    void put(uint8_t i, uint16_t value) {
        Track& t = tracks_[i];
        store_.writeFrame(i, t.frames, value);
        if (t.frames == 0) {
            t.first = value;
        }
        t.last = value;
        ++t.frames;
    }

    // The take ended at endMs: frames up to there, then the value at the end;
    // it loops from its glide back to the first frame. Too short: dropped.
    void closeTake(uint8_t i, uint32_t endMs) {
        Track& t = tracks_[i];
        uint32_t ms = endMs - t.startMs;
        if (ms > MAX_TAKE_MS) {  // a stalled loop saw the release late
            ms = MAX_TAKE_MS;
            endMs = t.startMs + MAX_TAKE_MS;
        }
        if (ms < MIN_TAKE_MS) {
            store_.writeHeader(i, 0, 0);
            t.frames = 0;
            startReturn(i, endMs);
            return;
        }
        const uint16_t lastFrame = (uint16_t)(ms / FRAME_MS);
        while (t.frames <= lastFrame) {
            put(i, t.out);
        }
        put(i, t.out);
        t.takeMs = (uint32_t)(t.frames - 1) * FRAME_MS;
        t.tailMs = tailOf(t);
        t.glide = 0;
        t.state = PLAYING;
        t.startMs = endMs - t.takeMs;  // at the end of the take: the tail next
        t.closedMs = endMs;
        t.refLatched = false;
        t.ref = live_[i];
        t.cached = NO_FRAME;
        store_.writeHeader(i, t.frames, t.ref);
    }

    void startReturn(uint8_t i, uint32_t nowMs) {
        Track& t = tracks_[i];
        if (t.out == live_[i]) {
            t.state = LIVE;
            return;
        }
        t.state = RETURNING;
        t.glide = (int16_t)((int32_t)t.out - (int32_t)live_[i]);
        t.glideStartMs = nowMs;
    }

    void eraseAll(uint32_t nowMs) {
        erased_ = true;
        eraseEvent_ = true;
        for (uint8_t i = 0; i < TRACKS; ++i) {
            store_.writeHeader(i, 0, 0);
            if (tracks_[i].state == PLAYING) {
                tracks_[i].frames = 0;
                startReturn(i, nowMs);
            }
        }
    }

    // Frames f and f + 1 into a / b; one read per frame while playing on.
    void fetch(uint8_t i, uint16_t f) {
        Track& t = tracks_[i];
        if (t.cached == f) {
            return;
        }
        if (t.cached != NO_FRAME && (uint16_t)(t.cached + 1) == f) {
            t.a = t.b;
        } else {
            t.a = clampKnob(store_.readFrame(i, f));
        }
        t.b = clampKnob(store_.readFrame(i, (uint16_t)(f + 1)));
        t.cached = f;
    }

    // The track `pos` ms into its loop: the take (frames interpolated), then
    // the glide from its last frame to its first.
    int32_t curve(uint8_t i, uint32_t pos) {
        Track& t = tracks_[i];
        if (pos >= t.takeMs) {
            const int32_t s = (int32_t)((pos - t.takeMs) * ONE / t.tailMs);
            return (int32_t)t.last +
                   (((int32_t)t.first - (int32_t)t.last) * ease(s)) / ONE;
        }
        const uint16_t f = (uint16_t)(pos / FRAME_MS);
        fetch(i, f);
        const int32_t into = (int32_t)(pos - (uint32_t)f * FRAME_MS);
        return (int32_t)t.a +
               (((int32_t)t.b - (int32_t)t.a) * into) / (int32_t)FRAME_MS;
    }

    void run(uint8_t i, uint32_t nowMs) {
        Track& t = tracks_[i];
        const int32_t live = live_[i];
        if (t.state == LIVE) {
            t.out = (uint16_t)live;
            return;
        }
        if (t.state == RECORDING) {
            const uint32_t elapsed = nowMs - t.startMs;
            if (elapsed >= MAX_TAKE_MS) {
                closeTake(i, t.startMs + MAX_TAKE_MS);  // full: loop it now
                t.sealed = true;
            } else {
                t.out = clampKnob(live + (t.glide * fade(t, nowMs, GLIDE_MS)) / ONE);
                // A main-loop stall leaves no gaps in the frames.
                const uint16_t f = (uint16_t)(elapsed / FRAME_MS);
                if (t.frames <= f) {
                    while (t.frames <= f) {
                        put(i, t.out);
                    }
                    store_.writeHeader(i, t.frames, (uint16_t)live);
                }
                return;
            }
        }
        if (t.state == PLAYING) {
            const uint32_t loop = t.takeMs + t.tailMs;
            uint32_t pos = nowMs - t.startMs;
            if (pos >= loop) {
                const uint32_t passes = pos / loop;
                t.startMs += passes * loop;
                pos -= passes * loop;
            }
            if (!t.refLatched) {
                t.ref = (uint16_t)live;
                if ((uint32_t)(nowMs - t.closedMs) >= OFFSET_GUARD_MS) {
                    t.refLatched = true;
                    store_.writeHeader(i, t.frames, t.ref);
                }
            }
            t.out = clampKnob(curve(i, pos) + live - (int32_t)t.ref);
            return;
        }
        // RETURNING
        const int32_t share = fade(t, nowMs, RETURN_MS);
        t.out = clampKnob(live + (t.glide * share) / ONE);
        if (share == 0) {
            t.state = LIVE;
        }
    }

    Store& store_;
    Track tracks_[TRACKS];
    uint16_t live_[TRACKS] = {0, 0, 0, 0};
    bool recordEnabled_ = true;
    bool down_ = false;            // debounced REC
    bool haveEdge_ = false;
    uint32_t edgeMs_ = 0;
    bool holding_ = false;
    bool moved_ = false;           // a take started in this hold
    bool erased_ = false;          // this hold erased the takes
    bool eraseEvent_ = false;
    uint32_t pressMs_ = 0;
};
