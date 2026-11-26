#pragma once

#include <stdint.h>

// MotionRecorder — the MOTION take recorder (four knobs, four tracks).
//
// The modules/16bit cpx4 FreeMotionRecorder behaviour, in integer maths, with
// the frames in a store (the MB85RC256V FRAM on the board, an array on the
// host) instead of RAM, so every take survives power-off. Everything runs in
// output codes (MCP4728: 0 = -5 V, ZERO = 0 V, 4095 = +5 V); a knob always
// spans -5..+5 V (no range, user 2026-11-26).
//
//   * LIVE: a knob without a take drives its output directly.
//   * RECORD (REC only records): hold REC and move a knob. From its first
//     move (more than MOVE_THRESHOLD counts away from where it was at the
//     press) until REC is released that knob is recorded, a frame every
//     FRAME_MS, straight into the store; its output follows the knob. Every
//     knob moved during the hold gets its own take, from its own first move.
//   * LOOP: at the release each take loops on its own: the take, then a
//     glide from its last value back to its first one (a quarter of the take,
//     TAIL_MIN_MS..TAIL_MAX_MS, shorter in proportion when the step is under
//     TAIL_FULL_STEP), so the loop never steps. Tracks of different lengths
//     drift against each other.
//   * RE-RECORD: moving a knob that has a track during a hold replaces the
//     track: no overdub, the new take holds the knob only. The output glides
//     from the value that sounded to the knob over GLIDE_MS; that glide is
//     heard, not recorded.
//   * ATTENUATE (the knob, no button): for ATT_IGNORE_MS after its take
//     closes the knob does nothing (the hand leaves it); after that it scales
//     the take towards 0 V. From the knob's first move (MOVE_THRESHOLD) its
//     travel each way from there maps onto the gain left that way (knob
//     fully down = 0, fully up = 1), so the gain never jumps. Once the knob
//     rests ATT_REST_MS the gain is saved and the next move starts from
//     there again.
//   * DELETE ONE: hold DEL and move a knob: its take is deleted and the
//     output glides to the knob over RETURN_MS.
//   * ERASE: DEL held ERASE_HOLD_MS with no knob moved erases every take,
//     the same way. Knobs moved later in that hold do nothing.
//   * REC and DEL: the button pressed first owns the hold; the other one is
//     ignored until it is pressed again with the first one up.
//   * A take shorter than MIN_TAKE_MS is dropped (the knob glides back to
//     live). A take reaching MAX_TAKE_MS closes itself and loops while REC is
//     still held; that knob records nothing more in this hold.
//
// Store (template parameter) layout contract: MAX_FRAMES frames per track,
// and
//   uint16_t readFrame(uint8_t track, uint16_t frame);
//   void writeFrame(uint8_t track, uint16_t frame, uint16_t value);
//   void writeHeader(uint8_t track, uint16_t frames, uint16_t gain);
// The header is the take length in frames (0 = no take) and its gain
// (0..GAIN_ONE). A take is written as it is recorded and its header follows
// each frame, so a power cut mid-take keeps what was recorded until then.
//
// Times are milliseconds on a free-running uint32_t clock (wrap-safe).
// No Arduino dependency: motion.ino passes the time, the knobs, REC and DEL.
template <class Store>
class MotionRecorder {
public:
    enum State : uint8_t {
        LIVE = 0,    // no track: output = knob
        RECORDING,   // REC held, the knob moved
        PLAYING,     // looping
        RETURNING,   // deleted or dropped: gliding to the knob
    };

    // Who owns the current button hold.
    enum Hold : uint8_t { HOLD_NONE = 0, HOLD_REC, HOLD_DEL };

    static const uint8_t TRACKS = 4;
    static const uint16_t KNOB_MAX = 4095;
    static const uint16_t CODE_MAX = 4095;
    static const uint16_t ZERO = 2048;                   // 0 V
    static const uint16_t GAIN_ONE = 4096;               // gain 1 (Q12)
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
    static const uint32_t ATT_IGNORE_MS = 1000;          // knob ignored after a take
    static const uint32_t ATT_REST_MS = 1000;            // knob still: gain saved
    static const uint16_t ATT_REST_COUNTS = 8;           // "still" = within this
    static const uint32_t TAIL_TAKE_DIVISOR = 4;
    static const uint32_t TAIL_MIN_MS = 250;
    static const uint32_t TAIL_MAX_MS = 2000;
    static const uint32_t TAIL_FULL_STEP = (CODE_MAX + 1) / 4;  // 2.5 V

    explicit MotionRecorder(Store& store) : store_(store) {}

    // Every knob live, no tracks; REC and DEL up.
    void begin(uint32_t nowMs) {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            tracks_[i] = Track();
        }
        rec_ = Button();
        del_ = Button();
        hold_ = HOLD_NONE;
        moved_ = false;
        erased_ = false;
        eraseEvent_ = false;
        (void)nowMs;
    }

    // A take found in the store at power-up (its header): loops from its
    // start with its gain; the knob attenuates it from its first move.
    // Fewer than two frames is no take.
    void load(uint8_t i, uint16_t frames, uint16_t gain, uint32_t nowMs) {
        if (i >= TRACKS || frames < 2 || frames > MAX_FRAMES) {
            return;
        }
        Track& t = tracks_[i];
        t.frames = frames;
        t.first = clampCode(store_.readFrame(i, 0));
        t.last = clampCode(store_.readFrame(i, (uint16_t)(frames - 1)));
        t.takeMs = (uint32_t)(frames - 1) * FRAME_MS;
        t.tailMs = tailOf(t);
        t.gain = gain > GAIN_ONE ? GAIN_ONE : gain;
        t.startMs = nowMs;
        t.cached = NO_FRAME;
        t.state = PLAYING;
        t.ignoring = false;
        t.attActive = false;
        t.holdSet = false;  // the knob position comes with the first update
    }

    // Recording on or off (off: no FRAM on the bus). Off does not stop a take.
    void setRecordEnabled(bool on) { recordEnabled_ = on; }

    // Call every millisecond with the conditioned knobs (0..KNOB_MAX) and the
    // raw REC and DEL levels (true = pressed, bounce included).
    void update(uint32_t nowMs, const uint16_t live[TRACKS], bool recDown,
                bool delDown) {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            live_[i] = live[i] > KNOB_MAX ? KNOB_MAX : live[i];
        }
        if (rec_.step(recDown, nowMs)) {
            recEdge(nowMs);
        }
        if (del_.step(delDown, nowMs)) {
            delEdge(nowMs);
        }
        if (hold_ != HOLD_NONE && !erased_) {
            detectMoves(nowMs);
            if (hold_ == HOLD_DEL && !moved_ &&
                (uint32_t)(nowMs - pressMs_) >= ERASE_HOLD_MS) {
                eraseAll(nowMs);
            }
        }
        if (hold_ == HOLD_NONE) {
            attenuate(nowMs);
        }
        for (uint8_t i = 0; i < TRACKS; ++i) {
            run(i, nowMs);
        }
    }

    // Output code each output plays, 0..CODE_MAX (ZERO = 0 V).
    uint16_t out(uint8_t i) const { return i < TRACKS ? tracks_[i].out : ZERO; }
    State state(uint8_t i) const { return i < TRACKS ? tracks_[i].state : LIVE; }
    uint16_t frames(uint8_t i) const {
        return i < TRACKS && tracks_[i].state == PLAYING ? tracks_[i].frames : 0;
    }
    uint16_t gain(uint8_t i) const { return i < TRACKS ? tracks_[i].gain : 0; }
    uint32_t loopMs(uint8_t i) const {
        return i < TRACKS && tracks_[i].state == PLAYING
            ? tracks_[i].takeMs + tracks_[i].tailMs : 0;
    }

    Hold hold() const { return hold_; }
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
    // DEL held with no knob moved (the erase countdown): ms since the press,
    // 0 otherwise.
    uint32_t eraseHoldMs(uint32_t nowMs) const {
        if (hold_ != HOLD_DEL || moved_ || erased_) {
            return 0;
        }
        const uint32_t ms = nowMs - pressMs_;
        return ms == 0 ? 1 : ms;
    }
    // True once after an erase of every take.
    bool takeEraseEvent() {
        const bool e = eraseEvent_;
        eraseEvent_ = false;
        return e;
    }

private:
    static const uint16_t NO_FRAME = 0xFFFF;

    // Debounced button: a level change within DEBOUNCE_MS of the last edge is
    // ignored.
    struct Button {
        bool down = false;
        bool haveEdge = false;
        uint32_t edgeMs = 0;

        // True when the debounced level changed.
        bool step(bool raw, uint32_t nowMs) {
            if (raw == down) {
                return false;
            }
            if (haveEdge && (uint32_t)(nowMs - edgeMs) < DEBOUNCE_MS) {
                return false;
            }
            haveEdge = true;
            edgeMs = nowMs;
            down = raw;
            return true;
        }
    };

    struct Track {
        State state = LIVE;
        bool sealed = false;       // closed itself at MAX_TAKE_MS in this hold
        bool ignoring = false;     // the take just closed: knob ignored
        bool holdSet = false;      // hold holds a knob position
        bool attActive = false;    // the knob is acting on the gain
        bool gainDirty = false;    // gain changed, header not written yet
        uint16_t frames = 0;       // frames stored
        uint16_t hold = 0;         // knob where move detection starts
        uint16_t out = ZERO;       // value that plays
        uint16_t first = 0;        // frame 0
        uint16_t last = 0;         // last frame
        uint16_t cached = NO_FRAME;  // frame of a / b
        uint16_t a = 0, b = 0;     // frames cached and cached + 1
        uint16_t gain = GAIN_ONE;
        uint16_t attKnob = 0;      // knob where it started to act on the gain
        uint16_t attGain = 0;      // gain then
        uint16_t restKnob = 0;     // knob at its last move (rest detection)
        int16_t glide = 0;         // join difference, faded out (heard only)
        uint32_t startMs = 0;      // RECORDING: first move; PLAYING: this pass
        uint32_t takeMs = 0;       // (frames - 1) * FRAME_MS
        uint32_t tailMs = 0;       // glide back to the first frame
        uint32_t glideStartMs = 0;
        uint32_t ignoreMs = 0;     // when the take closed
        uint32_t restMs = 0;       // the knob's last move
    };

    static uint16_t clampCode(int32_t v) {
        if (v <= 0) return 0;
        if (v >= CODE_MAX) return CODE_MAX;
        return (uint16_t)v;
    }

    static bool within(int32_t d, int32_t n) { return d <= n && d >= -n; }

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

    // Move detection starts again from where the knobs are now.
    void snapshotHolds() {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            tracks_[i].hold = live_[i];
            tracks_[i].holdSet = true;
        }
    }

    // A hold starts: the knobs stop attenuating (gains saved), moves are
    // counted from here.
    void startHold(Hold h, uint32_t nowMs) {
        endAttenuation();
        hold_ = h;
        pressMs_ = nowMs;
        moved_ = false;
        erased_ = false;
        snapshotHolds();
        for (uint8_t i = 0; i < TRACKS; ++i) {
            tracks_[i].sealed = false;
        }
    }

    // A hold ends: attenuation starts again from where the knobs are (a take
    // that just closed keeps ignoring its knob first).
    void endHold() {
        hold_ = HOLD_NONE;
        snapshotHolds();
    }

    void recEdge(uint32_t nowMs) {
        if (rec_.down) {
            if (hold_ == HOLD_NONE) {
                startHold(HOLD_REC, nowMs);
            }
            return;
        }
        if (hold_ != HOLD_REC) {
            return;
        }
        for (uint8_t i = 0; i < TRACKS; ++i) {
            if (tracks_[i].state == RECORDING) {
                closeTake(i, nowMs);
            }
        }
        endHold();
    }

    void delEdge(uint32_t nowMs) {
        if (del_.down) {
            if (hold_ == HOLD_NONE) {
                startHold(HOLD_DEL, nowMs);
            }
            return;
        }
        if (hold_ == HOLD_DEL) {
            endHold();
        }
    }

    // REC held: a knob moved starts its take. DEL held: a knob moved deletes
    // its take. Any move stops the DEL erase countdown.
    void detectMoves(uint32_t nowMs) {
        if (hold_ == HOLD_REC && !recordEnabled_) {
            return;
        }
        for (uint8_t i = 0; i < TRACKS; ++i) {
            Track& t = tracks_[i];
            if (t.state == RECORDING || t.sealed) {
                continue;
            }
            if (within((int32_t)live_[i] - (int32_t)t.hold, MOVE_THRESHOLD)) {
                continue;
            }
            moved_ = true;
            if (hold_ == HOLD_REC) {
                startTake(i, nowMs);
            } else {
                t.hold = live_[i];
                if (t.state == PLAYING) {
                    deleteTake(i, nowMs);
                }
            }
        }
    }

    // The knob takes over; the difference to what played (an old take)
    // fades out. The old take is gone from here on.
    void startTake(uint8_t i, uint32_t nowMs) {
        Track& t = tracks_[i];
        const int32_t code = live_[i];
        t.glide = (int16_t)((int32_t)t.out - code);
        t.glideStartMs = nowMs;
        t.state = RECORDING;
        t.startMs = nowMs;
        t.frames = 0;
        t.gain = GAIN_ONE;
        t.gainDirty = false;
        t.attActive = false;
        t.ignoring = false;
        store_.writeHeader(i, 0, GAIN_ONE);
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

    // The take ended at endMs: frames up to there, then the knob at the end;
    // it loops from its glide back to the first frame and ignores its knob
    // for ATT_IGNORE_MS. Too short: dropped. A join glide still fading goes
    // on fading over the loop.
    void closeTake(uint8_t i, uint32_t endMs) {
        Track& t = tracks_[i];
        uint32_t ms = endMs - t.startMs;
        if (ms > MAX_TAKE_MS) {  // a stalled loop saw the release late
            ms = MAX_TAKE_MS;
            endMs = t.startMs + MAX_TAKE_MS;
        }
        if (ms < MIN_TAKE_MS) {
            store_.writeHeader(i, 0, GAIN_ONE);
            t.frames = 0;
            startReturn(i, endMs);
            return;
        }
        const uint16_t knob = live_[i];
        const uint16_t lastFrame = (uint16_t)(ms / FRAME_MS);
        while (t.frames <= lastFrame) {
            put(i, knob);
        }
        put(i, knob);
        t.takeMs = (uint32_t)(t.frames - 1) * FRAME_MS;
        t.tailMs = tailOf(t);
        t.state = PLAYING;
        t.startMs = endMs - t.takeMs;  // at the end of the take: the tail next
        t.cached = NO_FRAME;
        t.ignoring = true;
        t.ignoreMs = endMs;
        t.attActive = false;
        store_.writeHeader(i, t.frames, t.gain);
    }

    void startReturn(uint8_t i, uint32_t nowMs) {
        Track& t = tracks_[i];
        t.gain = GAIN_ONE;
        t.gainDirty = false;
        t.attActive = false;
        t.ignoring = false;
        const int32_t code = live_[i];
        if (t.out == code) {
            t.state = LIVE;
            return;
        }
        t.state = RETURNING;
        t.glide = (int16_t)((int32_t)t.out - code);
        t.glideStartMs = nowMs;
    }

    void deleteTake(uint8_t i, uint32_t nowMs) {
        store_.writeHeader(i, 0, GAIN_ONE);
        tracks_[i].frames = 0;
        startReturn(i, nowMs);
    }

    void eraseAll(uint32_t nowMs) {
        erased_ = true;
        eraseEvent_ = true;
        for (uint8_t i = 0; i < TRACKS; ++i) {
            if (tracks_[i].state == PLAYING) {
                deleteTake(i, nowMs);
            } else {
                store_.writeHeader(i, 0, GAIN_ONE);
            }
        }
    }

    void saveGain(uint8_t i) {
        Track& t = tracks_[i];
        if (t.gainDirty && t.state == PLAYING) {
            store_.writeHeader(i, t.frames, t.gain);
        }
        t.gainDirty = false;
    }

    void endAttenuation() {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            saveGain(i);
            tracks_[i].attActive = false;
        }
    }

    // No button held: the knob of a playing take, ATT_IGNORE_MS after the
    // take closed, acts on its gain from its first move (MOVE_THRESHOLD):
    // down to the knob's end = gain 0, up to the other end = gain 1, in
    // proportion in between, so the gain follows without a jump. Still for
    // ATT_REST_MS: the gain is saved and the next move maps from there.
    void attenuate(uint32_t nowMs) {
        for (uint8_t i = 0; i < TRACKS; ++i) {
            Track& t = tracks_[i];
            if (t.state != PLAYING) {
                continue;
            }
            const int32_t k = live_[i];
            if (t.ignoring) {
                if ((uint32_t)(nowMs - t.ignoreMs) < ATT_IGNORE_MS) {
                    continue;
                }
                t.ignoring = false;
                t.holdSet = false;
            }
            if (!t.holdSet) {
                t.hold = (uint16_t)k;
                t.holdSet = true;
            }
            if (!t.attActive) {
                if (within(k - (int32_t)t.hold, MOVE_THRESHOLD)) {
                    continue;
                }
                t.attActive = true;
                t.attKnob = (uint16_t)k;
                t.attGain = t.gain;
                t.restKnob = (uint16_t)k;
                t.restMs = nowMs;
            }
            const int32_t k0 = t.attKnob;
            const int32_t g0 = t.attGain;
            int32_t g = g0;
            if (k < k0) {
                g = g0 * k / k0;
            } else if (k > k0) {
                g = g0 + ((int32_t)GAIN_ONE - g0) * (k - k0) / ((int32_t)KNOB_MAX - k0);
            }
            if (g != t.gain) {
                t.gain = (uint16_t)g;
                t.gainDirty = true;
            }
            if (!within(k - (int32_t)t.restKnob, ATT_REST_COUNTS)) {
                t.restKnob = (uint16_t)k;
                t.restMs = nowMs;
            } else if ((uint32_t)(nowMs - t.restMs) >= ATT_REST_MS) {
                saveGain(i);
                t.attActive = false;
                t.hold = (uint16_t)k;
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
            t.a = clampCode(store_.readFrame(i, f));
        }
        t.b = clampCode(store_.readFrame(i, (uint16_t)(f + 1)));
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
                t.out = clampCode(live + (t.glide * fade(t, nowMs, GLIDE_MS)) / ONE);
                // The knob is recorded, not the glide. A main-loop stall
                // leaves no gaps in the frames.
                const uint16_t f = (uint16_t)(elapsed / FRAME_MS);
                if (t.frames <= f) {
                    while (t.frames <= f) {
                        put(i, (uint16_t)live);
                    }
                    store_.writeHeader(i, t.frames, GAIN_ONE);
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
            const int32_t v = curve(i, pos) - (int32_t)ZERO;
            int32_t o = (int32_t)ZERO + v * (int32_t)t.gain / ONE;
            if (t.glide != 0) {  // a take shorter than GLIDE_MS
                const int32_t share = fade(t, nowMs, GLIDE_MS);
                o += (t.glide * share) / ONE;
                if (share == 0) {
                    t.glide = 0;
                }
            }
            t.out = clampCode(o);
            return;
        }
        // RETURNING
        const int32_t share = fade(t, nowMs, RETURN_MS);
        t.out = clampCode(live + (t.glide * share) / ONE);
        if (share == 0) {
            t.state = LIVE;
        }
    }

    Store& store_;
    Track tracks_[TRACKS];
    uint16_t live_[TRACKS] = {0, 0, 0, 0};
    Button rec_;
    Button del_;
    bool recordEnabled_ = true;
    Hold hold_ = HOLD_NONE;
    bool moved_ = false;           // a knob moved in this hold
    bool erased_ = false;          // this hold erased the takes
    bool eraseEvent_ = false;
    uint32_t pressMs_ = 0;
};
