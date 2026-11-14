#pragma once

#include <stdint.h>

#include "audio/apps/motion_recorder.h"

// FreeMotionRecorder — free-running, RAM-only automation recorder (cpx4).
//
// No MIDI timing and no common loop: every control has its own track, with
// its own length and its own start. The controls ("params") are the knobs
// P1..P4 (param 0..3, 0..KNOB_MAX) and the twelve MCC slots of
// MotionRecorder (param 4 + MotionRecorder::ccIndex(cc), 0..CC_MAX).
//
//   * RECORD: hold MODE and move a control. From its first move until MODE
//     is released that control is recorded (LED blinks); it keeps driving
//     the sound. Every control moved during the hold gets its own take, from
//     its own first move. A move is more than MOVE_KNOB_THRESHOLD ADC counts
//     or more than MOVE_CC_THRESHOLD CC steps away from the position at the
//     press: an MCC knob resting between two steps flickers by one, and that
//     must not start a take.
//   * LOOP: at the release each take becomes a track that loops on its own
//     (LED solid while any track plays): the take, then a glide from its
//     last value back to its first one, so loop end -> start never steps and
//     the take keeps every value it recorded. The glide lasts a quarter of
//     the take (TAIL_MIN_MS..TAIL_MAX_MS), less in proportion when the step
//     is under a quarter of the range (none if the take ends where it
//     began). The track's loop is take + glide; tracks of different lengths
//     drift against each other.
//   * RE-RECORD: hold MODE and move a control that has a track: the new take
//     replaces the track (new length). It takes over from the value that
//     sounded; the difference fades out over GLIDE_MS (and is recorded, the
//     take stores what it plays). The other tracks keep playing.
//   * REMOVE: a MODE click (shorter than CLICK_MAX_MS, no take kept) removes
//     every track: each control glides from its track's last value to the
//     control's position over RETURN_MS, then it is live again (LED off). A
//     longer hold with nothing moved changes nothing.
//   * A take shorter than MIN_TAKE_MS (the control moved just before the
//     release) is dropped: that control goes back to live, with a glide.
//     A take reaching MAX_TAKE_MS closes itself and loops while MODE is
//     still held.
//   * OFFSET (as the other recorders): OFFSET_GUARD_MS after the release the
//     control's position becomes the reference; moving it then (MODE not
//     held) shifts its whole track by (position - reference), clamped. So a
//     CV into an MCC keeps modulating a recorded control.
//
// A control without a track is never touched: the app applies it live
// (ownsKnob(), ownsCc()). The recorder applies an owned control through the
// callback whenever its value changes: frames are FRAME_MS apart and
// interpolated in between, so playback moves in single counts.
//
// Times are milliseconds on a free-running uint32_t clock (wraps after 49
// days; all arithmetic is wrap-safe). No Pico/IO dependency: the app passes
// the time, the live knobs and an apply callback, so it is host-testable.
class FreeMotionRecorder {
public:
    using LedCallback = MotionRecorder::LedCallback;
    using ApplyCallback = void (*)(void* context, uint8_t param,
                                   uint16_t value);

    enum TrackState : uint8_t {
        TRACK_LIVE = 0,    // no track: the app applies the control
        TRACK_RECORDING,   // MODE held, the control moved
        TRACK_PLAYING,     // looping
        TRACK_RETURNING,   // removed or dropped: gliding to the control
    };

    static constexpr uint8_t KNOB_COUNT = MotionRecorder::KNOB_COUNT;
    static constexpr uint8_t CC_COUNT = MotionRecorder::CC_COUNT;
    static constexpr uint8_t PARAM_COUNT = KNOB_COUNT + CC_COUNT;
    static constexpr uint8_t CC_UNSET = MotionRecorder::CC_UNSET;
    static constexpr uint16_t KNOB_MAX = MotionRecorder::KNOB_MAX;
    static constexpr uint8_t CC_MAX = MotionRecorder::CC_MAX;

    static constexpr uint32_t FRAME_MS = 20;          // 50 frames per second
    static constexpr uint32_t MAX_TAKE_MS = 60000;    // one minute per track
    // Frames every FRAME_MS from the first move, plus the value at the
    // release.
    static constexpr uint16_t MAX_FRAMES = MAX_TAKE_MS / FRAME_MS + 2;
    static constexpr uint32_t MIN_TAKE_MS = 200;      // shorter: take dropped
    static constexpr uint32_t CLICK_MAX_MS = 700;     // longer: not a click
    static constexpr uint32_t LED_BLINK_HALF_PERIOD_MS = 150;
    // A knob counts as moved during a hold once it leaves its position at
    // the press by more than this (ADC noise guard).
    static constexpr uint16_t MOVE_KNOB_THRESHOLD =
        MotionRecorder::OVERDUB_KNOB_THRESHOLD;
    // The same for an MCC control, in CC steps (one step = knob noise).
    static constexpr uint16_t MOVE_CC_THRESHOLD = 1;
    // Joins. Take-over glide of a re-recorded control; glide back to the
    // controls when the tracks are removed; glide from a take's last value
    // back to its first one (take / TAIL_TAKE_DIVISOR, clamped, for a step
    // of at least the range / TAIL_FULL_STEP_DIVISOR).
    static constexpr uint32_t GLIDE_MS = 300;
    static constexpr uint32_t RETURN_MS = 600;
    static constexpr uint32_t TAIL_TAKE_DIVISOR = 4;
    static constexpr uint32_t TAIL_MIN_MS = 250;
    static constexpr uint32_t TAIL_MAX_MS = 2000;
    static constexpr uint32_t TAIL_FULL_STEP_DIVISOR = 4;
    // After the release the hand may still be on the control: its position
    // becomes the offset reference this much later.
    static constexpr uint32_t OFFSET_GUARD_MS = 500;

    explicit FreeMotionRecorder(LedCallback led = nullptr,
                                uint32_t debounceMs = 30)
        : ledCallback_(led), debounceMs_(debounceMs) {
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            live_[i] = LIVE_UNSET;
        }
    }

    void setLedCallback(LedCallback led) {
        ledCallback_ = led;
    }

    // Every control live, no tracks. Live values are kept (they mirror the
    // app's state).
    void begin(uint32_t nowMs = 0) {
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            tracks_[i] = Track();
        }
        buttonRaw_ = false;
        buttonDown_ = false;
        haveLastEdge_ = false;
        holding_ = false;
        ledBlinking_ = false;
        lastBlinkMs_ = nowMs;
        setLed(false);
    }

    // Call from the main loop with the live knobs P1..P4. Starts takes
    // (MODE held and a control moved), records, plays every track at its
    // own position and animates the LED. apply gets each owned control
    // whenever its value changes.
    void update(uint32_t nowMs, const uint16_t liveKnobs[KNOB_COUNT],
                ApplyCallback apply = nullptr, void* context = nullptr) {
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            live_[i] = liveKnobs[i];
        }
        settleButton(nowMs);
        if (holding_) {
            detectMoves(nowMs);
        }
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            run(i, nowMs, apply, context);
        }
        updateLed(nowMs);
    }

    // IO reports every edge of the MODE switch, contact bounce included (the
    // pin is read each millisecond, unfiltered). An edge acts at once; for
    // debounceMs after it the level is only remembered and taken again from
    // update(). A bounce is therefore neither a release (which would close
    // the takes) nor a click (which would remove the tracks).
    void buttonChanged(bool pressed, uint32_t nowMs) {
        buttonRaw_ = pressed;
        settleButton(nowMs);
        updateLed(nowMs);
    }

    // Keep the latest live MCC value. Returns false (and ignores the value)
    // for CCs outside the three MCC banks.
    bool setCurrentCc(uint8_t cc, uint8_t value) {
        const int param = paramOfCc(cc);
        if (param < 0) {
            return false;
        }
        live_[param] = value & 0x7F;
        return true;
    }

    void clearCurrentCcs() {
        for (uint8_t i = KNOB_COUNT; i < PARAM_COUNT; ++i) {
            live_[i] = LIVE_UNSET;
        }
    }

    uint8_t getCurrentCc(uint8_t cc) const {
        const int param = paramOfCc(cc);
        return param >= 0 && live_[param] != LIVE_UNSET
            ? (uint8_t)live_[param] : CC_UNSET;
    }

    // Param of an MCC CC (KNOB_COUNT + its slot), -1 outside the banks.
    static int paramOfCc(uint8_t cc) {
        const int index = MotionRecorder::ccIndex(cc);
        return index >= 0 ? KNOB_COUNT + index : -1;
    }

    // True while the recorder drives this control (recording, playing or
    // gliding back to it): the app must not apply it live.
    bool ownsParam(uint8_t param) const {
        return param < PARAM_COUNT && tracks_[param].state != TRACK_LIVE;
    }
    bool ownsKnob(uint8_t knob) const {
        return knob < KNOB_COUNT && ownsParam(knob);
    }
    bool ownsCc(uint8_t cc) const {
        const int param = paramOfCc(cc);
        return param >= 0 && ownsParam((uint8_t)param);
    }

    TrackState getTrackState(uint8_t param) const {
        return param < PARAM_COUNT ? tracks_[param].state : TRACK_LIVE;
    }
    // Recorded length of the track, and its loop (take + glide back).
    uint32_t getTakeMs(uint8_t param) const {
        return hasTrack(param) ? tracks_[param].takeMs : 0;
    }
    uint32_t getLoopMs(uint8_t param) const {
        return hasTrack(param)
            ? tracks_[param].takeMs + tracks_[param].tailMs : 0;
    }
    bool isHolding() const { return holding_; }
    bool isRecording() const { return countTracks(TRACK_RECORDING) != 0; }
    bool isPlayingBack() const { return countTracks(TRACK_PLAYING) != 0; }
    // No control owned: every one is applied by the app.
    bool isLive() const {
        return countTracks(TRACK_LIVE) == PARAM_COUNT;
    }
    uint8_t countTracks(TrackState state) const {
        uint8_t count = 0;
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            if (tracks_[i].state == state) {
                ++count;
            }
        }
        return count;
    }

private:
    static constexpr uint16_t LIVE_UNSET = 0xFFFF;  // CC not received yet

    struct Track {
        TrackState state = TRACK_LIVE;
        bool sealed = false;       // closed itself at MAX_TAKE_MS in this hold
        bool applied = false;      // `out` was handed to the app
        bool refLatched = false;   // PLAYING: offset reference fixed
        uint16_t frames = 0;       // values stored
        uint16_t hold = LIVE_UNSET;  // control position at the MODE press
        uint16_t ref = 0;          // control position the offset starts from
        uint16_t out = 0;          // value that sounds
        uint32_t startMs = 0;      // RECORDING: first move; PLAYING: this pass
        uint32_t takeMs = 0;       // recorded length
        uint32_t tailMs = 0;       // glide back to the first value
        uint32_t closedMs = 0;     // PLAYING: when the take was closed
        // Join: difference between what sounded and the control at
        // glideStartMs, added to the control and faded out.
        float glide = 0.0f;
        uint32_t glideStartMs = 0;
    };

    static uint16_t maxOf(uint8_t param) {
        return param < KNOB_COUNT ? KNOB_MAX : CC_MAX;
    }

    static uint16_t moveThreshold(uint8_t param) {
        return param < KNOB_COUNT ? MOVE_KNOB_THRESHOLD : MOVE_CC_THRESHOLD;
    }

    // Rounded and clamped to the param's range.
    static uint16_t bent(float value, uint16_t max) {
        if (value <= 0.0f) return 0;
        if (value >= (float)max) return max;
        return (uint16_t)(value + 0.5f);
    }

    // 0..1 with no slope at either end (smoothstep).
    static float ease(float s) {
        if (s <= 0.0f) return 0.0f;
        if (s >= 1.0f) return 1.0f;
        return s * s * (3.0f - 2.0f * s);
    }

    // Share of the track's join difference still added: 1 at the join, 0
    // from lengthMs on.
    static float fade(const Track& track, uint32_t nowMs, uint32_t lengthMs) {
        const uint32_t elapsed = nowMs - track.glideStartMs;
        if (elapsed >= lengthMs) {
            return 0.0f;
        }
        return 1.0f - ease((float)elapsed / (float)lengthMs);
    }

    bool hasTrack(uint8_t param) const {
        return param < PARAM_COUNT && tracks_[param].state == TRACK_PLAYING;
    }

    uint16_t stored(uint8_t param, uint16_t frame) const {
        return param < KNOB_COUNT ? knobFrames_[param][frame]
                                  : ccFrames_[param - KNOB_COUNT][frame];
    }

    void store(uint8_t param, uint16_t frame, uint16_t value) {
        if (param < KNOB_COUNT) {
            knobFrames_[param][frame] = value;
        } else {
            ccFrames_[param - KNOB_COUNT][frame] = (uint8_t)value;
        }
    }

    void settleButton(uint32_t nowMs) {
        if (buttonRaw_ == buttonDown_) {
            return;
        }
        if (haveLastEdge_ &&
            (uint32_t)(nowMs - lastEdgeMs_) < debounceMs_) {
            return;
        }
        haveLastEdge_ = true;
        lastEdgeMs_ = nowMs;
        buttonDown_ = buttonRaw_;
        if (buttonDown_) {
            startHold(nowMs);
        } else if (holding_) {
            releaseHold(nowMs);
        }
    }

    // MODE pressed: snapshot the controls; a control is recorded once it
    // leaves its snapshot.
    void startHold(uint32_t nowMs) {
        holding_ = true;
        pressMs_ = nowMs;
        keptTake_ = false;
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            tracks_[i].hold = live_[i];
            tracks_[i].sealed = false;
        }
    }

    // Start a take for every control that left its snapshot.
    void detectMoves(uint32_t nowMs) {
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            Track& track = tracks_[i];
            if (track.state == TRACK_RECORDING || track.sealed ||
                live_[i] == LIVE_UNSET) {
                continue;
            }
            if (track.hold == LIVE_UNSET) {
                track.hold = live_[i];  // first value: nothing to compare
                continue;
            }
            const int32_t moved = (int32_t)live_[i] - (int32_t)track.hold;
            const int32_t threshold = moveThreshold(i);
            if (moved <= threshold && moved >= -threshold) {
                continue;
            }
            startTake(i, nowMs);
        }
    }

    // The control takes over from here. If the recorder was driving it (its
    // track, or a glide back), the difference to what sounded fades out.
    void startTake(uint8_t param, uint32_t nowMs) {
        Track& track = tracks_[param];
        if (track.state == TRACK_LIVE) {
            track.out = live_[param];
            track.applied = false;
            track.glide = 0.0f;
        } else {
            track.glide = (float)track.out - (float)live_[param];
        }
        track.glideStartMs = nowMs;
        track.state = TRACK_RECORDING;
        track.startMs = nowMs;
        track.frames = 0;
    }

    // MODE released: every take becomes a track. A click removes them all.
    void releaseHold(uint32_t nowMs) {
        holding_ = false;
        for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
            if (tracks_[i].state == TRACK_RECORDING && closeTake(i, nowMs)) {
                keptTake_ = true;
            }
        }
        if (!keptTake_ && (uint32_t)(nowMs - pressMs_) < CLICK_MAX_MS) {
            for (uint8_t i = 0; i < PARAM_COUNT; ++i) {
                if (tracks_[i].state == TRACK_PLAYING) {
                    startReturn(i, nowMs);
                }
            }
        }
    }

    // The take ended at endMs: loop it from here, starting with the glide
    // back to its first value. Too short: dropped (false).
    bool closeTake(uint8_t param, uint32_t endMs) {
        Track& track = tracks_[param];
        const uint32_t takeMs = endMs - track.startMs;
        if (takeMs < MIN_TAKE_MS) {
            startReturn(param, endMs);
            return false;
        }
        // Frames up to the release, then the value at the release itself.
        const uint16_t last = (uint16_t)(takeMs / FRAME_MS);
        while (track.frames <= last) {
            store(param, track.frames++, track.out);
        }
        store(param, (uint16_t)(last + 1), track.out);
        track.frames = (uint16_t)(last + 2);
        track.takeMs = takeMs;

        const int32_t step = (int32_t)track.out - (int32_t)stored(param, 0);
        const uint32_t size = (uint32_t)(step < 0 ? -step : step);
        const uint32_t full =
            ((uint32_t)maxOf(param) + 1) / TAIL_FULL_STEP_DIVISOR;
        uint32_t tailMs = takeMs / TAIL_TAKE_DIVISOR;
        if (tailMs < TAIL_MIN_MS) {
            tailMs = TAIL_MIN_MS;
        }
        if (tailMs > TAIL_MAX_MS) {
            tailMs = TAIL_MAX_MS;
        }
        if (size < full) {
            tailMs = tailMs * size / full;
        }
        track.tailMs = tailMs;

        // What is left of a take-over glide is in the frames.
        track.glide = 0.0f;
        track.state = TRACK_PLAYING;
        track.closedMs = endMs;
        track.refLatched = false;
        track.ref = live_[param];
        return true;
    }

    // Give the control back: glide from what sounds to its position.
    void startReturn(uint8_t param, uint32_t nowMs) {
        Track& track = tracks_[param];
        if (track.out == live_[param]) {
            track.state = TRACK_LIVE;  // already there
            return;
        }
        track.state = TRACK_RETURNING;
        track.glide = (float)track.out - (float)live_[param];
        track.glideStartMs = nowMs;
    }

    // The track's value `pos` ms into its loop: the take (frames FRAME_MS
    // apart, the last one at the release, interpolated), then the glide from
    // its last value to its first.
    float curve(uint8_t param, const Track& track, uint32_t pos) const {
        if (pos >= track.takeMs) {
            const float from = stored(param, (uint16_t)(track.frames - 1));
            const float to = stored(param, 0);
            return from + (to - from) * ease((float)(pos - track.takeMs) /
                                             (float)track.tailMs);
        }
        const uint16_t frame = (uint16_t)(pos / FRAME_MS);
        const uint32_t at = (uint32_t)frame * FRAME_MS;
        uint32_t span = track.takeMs - at;
        if (span > FRAME_MS) {
            span = FRAME_MS;
        }
        const float a = stored(param, frame);
        const float b = stored(param, (uint16_t)(frame + 1));
        return a + (b - a) * (float)(pos - at) / (float)span;
    }

    void emit(uint8_t param, uint16_t value, ApplyCallback apply,
              void* context) {
        Track& track = tracks_[param];
        if (track.applied && track.out == value) {
            return;
        }
        track.out = value;
        track.applied = true;
        if (apply != nullptr) {
            apply(context, param, value);
        }
    }

    void run(uint8_t param, uint32_t nowMs, ApplyCallback apply,
             void* context) {
        Track& track = tracks_[param];
        if (track.state == TRACK_LIVE || live_[param] == LIVE_UNSET) {
            return;
        }
        const uint16_t max = maxOf(param);
        if (track.state == TRACK_RECORDING) {
            const uint32_t elapsed = nowMs - track.startMs;
            if (elapsed >= MAX_TAKE_MS) {
                // Full: loop it now, no new take until the next press.
                closeTake(param, track.startMs + MAX_TAKE_MS);
                track.sealed = true;
                keptTake_ = true;
            } else {
                // The control, plus what is left of the take-over glide.
                // A main-loop stall leaves no gaps in the frames.
                emit(param,
                     bent((float)live_[param] +
                          track.glide * fade(track, nowMs, GLIDE_MS), max),
                     apply, context);
                const uint16_t frame = (uint16_t)(elapsed / FRAME_MS);
                while (track.frames <= frame) {
                    store(param, track.frames++, track.out);
                }
                return;
            }
        }
        if (track.state == TRACK_PLAYING) {
            const uint32_t loopMs = track.takeMs + track.tailMs;
            uint32_t pos = nowMs - track.startMs;
            if (pos >= loopMs) {
                const uint32_t passes = pos / loopMs;
                track.startMs += passes * loopMs;
                pos -= passes * loopMs;
            }
            if (!track.refLatched) {
                track.ref = live_[param];
                track.refLatched =
                    (uint32_t)(nowMs - track.closedMs) >= OFFSET_GUARD_MS;
            }
            const float offset = (float)live_[param] - (float)track.ref;
            emit(param, bent(curve(param, track, pos) + offset, max), apply,
                 context);
            return;
        }
        if (track.state == TRACK_RETURNING) {
            const float share = fade(track, nowMs, RETURN_MS);
            emit(param, bent((float)live_[param] + track.glide * share, max),
                 apply, context);
            if (share <= 0.0f) {
                track.state = TRACK_LIVE;  // the last value applied is live
            }
        }
    }

    // Recording: blink, starting with a change. Otherwise solid while any
    // track plays.
    void updateLed(uint32_t nowMs) {
        if (isRecording()) {
            if (!ledBlinking_ ||
                (uint32_t)(nowMs - lastBlinkMs_) >= LED_BLINK_HALF_PERIOD_MS) {
                ledBlinking_ = true;
                lastBlinkMs_ = nowMs;
                setLed(!ledOn_);
            }
            return;
        }
        ledBlinking_ = false;
        const bool on = isPlayingBack();
        if (on != ledOn_) {
            setLed(on);
        }
    }

    void setLed(bool on) {
        ledOn_ = on;
        if (ledCallback_ != nullptr) {
            ledCallback_(on);
        }
    }

    LedCallback ledCallback_ = nullptr;
    uint32_t debounceMs_ = 30;

    Track tracks_[PARAM_COUNT];
    uint16_t live_[PARAM_COUNT];   // latest knobs and MCC values

    // MODE hold.
    bool holding_ = false;
    bool keptTake_ = false;        // a take of this hold became a track
    uint32_t pressMs_ = 0;

    bool ledOn_ = false;
    bool ledBlinking_ = false;
    uint32_t lastBlinkMs_ = 0;
    bool buttonRaw_ = false;       // level IO last reported
    bool buttonDown_ = false;      // debounced level
    bool haveLastEdge_ = false;
    uint32_t lastEdgeMs_ = 0;

    // One minute per track every 20 ms: P1..P4 at 12 bits, the twelve MCC
    // slots at 7 (60 KB). Volatile runtime state only; nothing is persisted.
    uint16_t knobFrames_[KNOB_COUNT][MAX_FRAMES] = {};
    uint8_t ccFrames_[CC_COUNT][MAX_FRAMES] = {};
};
