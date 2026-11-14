#pragma once

#include <stdint.h>

#include "audio/apps/motion_recorder.h"

// FreeMotionRecorder — free-running, RAM-only automation recorder (lyra4).
//
// The same frames, MCC slots, overdub hold and loop offset as MotionRecorder
// (motion_recorder.h), but no MIDI timing: the loop length is the time
// between two MODE presses, and frames are taken every FRAME_MS from the
// main loop's millisecond clock.
//
//   * LIVE: a MODE press starts RECORDING.
//   * RECORDING: LED blinks; every FRAME_MS the live P1..P4 and MCC values
//     are stored. Live controls keep driving the sound. The next MODE press
//     closes the loop: its length is the time between the two presses (to
//     the millisecond, not rounded to frames, so the loop doesn't drift
//     against the tempo it was tapped to), and playback starts from the
//     first frame at that press. A take reaching MAX_LOOP_MS closes itself.
//     A second press within MIN_LOOP_MS drops the take (back to LIVE).
//   * PLAYBACK: LED solid, with a short dark mark each time the loop
//     restarts. A MODE click (press and release without moving anything)
//     returns to LIVE on the release.
//   * OVERDUB: hold MODE in PLAYBACK and move any knob or MCC control. From
//     its first move until MODE is released, that parameter's live value
//     replaces the recorded one (the others keep playing back) and the LED
//     blinks. Releasing MODE keeps the loop playing with the new curve, no
//     offset until the control moves again. A CC that wasn't in the take
//     joins it; the frames outside the overdubbed span carry its value from
//     before the hold.
//   * OFFSET: for the first pass of PLAYBACK the knobs and MCC are ignored,
//     so the hand that just closed the loop can't nudge it. Their positions
//     at the end of that pass become the reference; from then on moving a
//     knob or MCC control shifts its whole curve by (live - reference),
//     clamped.
//
// A CC that never arrived before or during the take is not recorded and stays
// live in PLAYBACK; one first moved part-way through is back-filled with its
// first value.
//
// Times are milliseconds on a free-running uint32_t clock (wraps after 49
// days; all arithmetic is wrap-safe). No Pico/IO dependency: the app passes
// the time, the live knobs and an apply callback, so it is host-testable.
class FreeMotionRecorder {
public:
    using Frame = MotionRecorder::Frame;
    using LedCallback = MotionRecorder::LedCallback;
    using PlaybackCallback = MotionRecorder::PlaybackCallback;
    using State = MotionRecorder::State;

    static constexpr uint8_t KNOB_COUNT = MotionRecorder::KNOB_COUNT;
    static constexpr uint8_t CC_COUNT = MotionRecorder::CC_COUNT;
    static constexpr uint8_t CC_UNSET = MotionRecorder::CC_UNSET;
    static constexpr uint16_t KNOB_MAX = MotionRecorder::KNOB_MAX;
    static constexpr uint8_t CC_MAX = MotionRecorder::CC_MAX;

    static constexpr uint32_t FRAME_MS = 20;          // 50 frames per second
    static constexpr uint32_t MAX_LOOP_MS = 60000;    // one minute
    static constexpr uint16_t MAX_FRAMES = MAX_LOOP_MS / FRAME_MS;
    static constexpr uint32_t MIN_LOOP_MS = 200;      // shorter: take dropped
    static constexpr uint32_t LED_BLINK_HALF_PERIOD_MS = 150;
    static constexpr uint32_t LED_LOOP_MARK_MS = 80;  // dark at each restart
    // A knob counts as moved during an overdub hold once it leaves its
    // position at the press by more than this (ADC noise guard).
    static constexpr uint16_t OVERDUB_KNOB_THRESHOLD =
        MotionRecorder::OVERDUB_KNOB_THRESHOLD;

    explicit FreeMotionRecorder(LedCallback led = nullptr,
                                uint32_t debounceMs = 30)
        : ledCallback_(led), debounceMs_(debounceMs) {
        clearCurrentCcs();
    }

    void setLedCallback(LedCallback led) {
        ledCallback_ = led;
    }

    // Back to LIVE. Live CC values are kept (they mirror the app's state).
    void begin(uint32_t nowMs = 0) {
        state_ = MotionRecorder::STATE_LIVE;
        buttonDown_ = false;
        haveLastPress_ = false;
        holding_ = false;
        lastBlinkMs_ = nowMs;
        setLed(false);
    }

    // Call from the main loop with the live knobs P1..P4. Records, plays back
    // (apply gets the frame at the playhead, plus the offset once armed,
    // whenever the playhead moves to a new frame) and animates the LED.
    void update(uint32_t nowMs, const uint16_t liveKnobs[KNOB_COUNT],
                PlaybackCallback apply = nullptr, void* context = nullptr) {
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            liveKnobs_[i] = liveKnobs[i];
        }
        haveLiveKnobs_ = true;

        if (state_ == MotionRecorder::STATE_RECORDING) {
            const uint32_t elapsed = nowMs - startMs_;
            if (elapsed >= MAX_LOOP_MS) {
                closeLoop(startMs_ + MAX_LOOP_MS, MAX_LOOP_MS);
            } else {
                recordUpTo((uint16_t)(elapsed / FRAME_MS));
                blink(nowMs);
                return;
            }
        }
        if (state_ == MotionRecorder::STATE_PLAYBACK) {
            play(nowMs, apply, context);
        }
    }

    // IO already reports button edges; this guard keeps a bouncing button
    // from closing a take right after starting it.
    void buttonChanged(bool pressed, uint32_t nowMs) {
        if (!pressed) {
            buttonDown_ = false;
            if (holding_) {
                releaseHold(nowMs);
            }
            return;
        }
        if (buttonDown_) {
            return;
        }
        buttonDown_ = true;

        if (haveLastPress_ &&
            (uint32_t)(nowMs - lastPressMs_) < debounceMs_) {
            return;
        }
        haveLastPress_ = true;
        lastPressMs_ = nowMs;
        switch (state_) {
            case MotionRecorder::STATE_LIVE:
                startTake(nowMs);
                break;
            case MotionRecorder::STATE_RECORDING:
                stopTake(nowMs);
                break;
            case MotionRecorder::STATE_PLAYBACK:
                startHold();
                break;
        }
    }

    bool isRecording() const {
        return state_ == MotionRecorder::STATE_RECORDING;
    }
    bool isPlayingBack() const {
        return state_ == MotionRecorder::STATE_PLAYBACK;
    }
    bool isLive() const { return state_ == MotionRecorder::STATE_LIVE; }
    bool isOffsetArmed() const { return isPlayingBack() && offsetArmed_; }
    // MODE held in PLAYBACK and at least one parameter moved.
    bool isOverdubbing() const {
        return holding_ && (overdubKnobs_ != 0 || overdubCcs_ != 0);
    }
    State getState() const { return state_; }
    uint32_t getLoopMs() const { return loopMs_; }
    uint16_t getLoopFrames() const { return loopFrames_; }
    // Frame at the playhead (PLAYBACK) or the last one written (RECORDING).
    uint16_t getFrameIndex() const { return frameIndex_; }

    // Keep the latest live MCC value. Returns false (and ignores the value)
    // for CCs outside the three MCC banks.
    bool setCurrentCc(uint8_t cc, uint8_t value) {
        int index = MotionRecorder::ccIndex(cc);
        if (index < 0) {
            return false;
        }
        currentCc_[index] = value & 0x7F;
        return true;
    }

    void clearCurrentCcs() {
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            currentCc_[i] = CC_UNSET;
        }
    }

    uint8_t getCurrentCc(uint8_t cc) const {
        int index = MotionRecorder::ccIndex(cc);
        return index >= 0 ? currentCc_[index] : CC_UNSET;
    }

    // True while PLAYBACK drives this CC: the app must not apply it live.
    bool ownsCc(uint8_t cc) const {
        int index = MotionRecorder::ccIndex(cc);
        return isPlayingBack() && index >= 0 &&
               (recordedCcs_ & (1u << index)) != 0;
    }

private:
    static uint16_t shifted(uint16_t stored, int32_t offset, uint16_t max) {
        int32_t v = (int32_t)stored + offset;
        if (v < 0) return 0;
        if (v > max) return max;
        return (uint16_t)v;
    }

    void writeLiveFrame(uint16_t index) {
        Frame& frame = frames_[index];
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            frame.knobs[i] = liveKnobs_[i];
        }
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            frame.ccs[i] = currentCc_[i];
        }
    }

    // Fill every frame up to and including `last` with the live values (a
    // main-loop stall leaves no gaps).
    void recordUpTo(uint16_t last) {
        if (last >= MAX_FRAMES) {
            last = MAX_FRAMES - 1;
        }
        while (framesWritten_ <= last) {
            writeLiveFrame(framesWritten_);
            ++framesWritten_;
        }
        frameIndex_ = last;
    }

    void startTake(uint32_t nowMs) {
        state_ = MotionRecorder::STATE_RECORDING;
        startMs_ = nowMs;
        framesWritten_ = 0;
        frameIndex_ = 0;
        if (haveLiveKnobs_) {
            recordUpTo(0);  // the controls as they are at the press
        }
        lastBlinkMs_ = nowMs;
        ledOn_ = false;
        setLed(false);
    }

    void stopTake(uint32_t nowMs) {
        const uint32_t elapsed = nowMs - startMs_;
        if (elapsed < MIN_LOOP_MS) {
            // An incomplete take is never exposed as a loop.
            state_ = MotionRecorder::STATE_LIVE;
            ledOn_ = false;
            setLed(false);
            return;
        }
        closeLoop(nowMs, elapsed < MAX_LOOP_MS ? elapsed : MAX_LOOP_MS);
    }

    // The take is complete: fill the last frames, back-fill CCs first moved
    // part-way through, remember which CCs the loop owns, then play from the
    // first frame with the guard pass.
    void closeLoop(uint32_t loopStartMs, uint32_t lengthMs) {
        loopMs_ = lengthMs;
        loopFrames_ = (uint16_t)((lengthMs + FRAME_MS - 1) / FRAME_MS);
        if (loopFrames_ > MAX_FRAMES) {
            loopFrames_ = MAX_FRAMES;
        }
        recordUpTo((uint16_t)(loopFrames_ - 1));

        recordedCcs_ = 0;
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            uint16_t first = 0;
            while (first < loopFrames_ && frames_[first].ccs[i] == CC_UNSET) {
                ++first;
            }
            if (first == loopFrames_) {
                continue;  // never arrived: stays live in PLAYBACK
            }
            for (uint16_t t = 0; t < first; ++t) {
                frames_[t].ccs[i] = frames_[first].ccs[i];
            }
            recordedCcs_ |= (uint16_t)(1u << i);
        }

        state_ = MotionRecorder::STATE_PLAYBACK;
        loopStartMs_ = loopStartMs;
        offsetArmed_ = false;
        frameIndex_ = 0;
        haveApplied_ = false;
        markUntilMs_ = loopStartMs;
        ledOn_ = true;
        setLed(true);
    }

    void play(uint32_t nowMs, PlaybackCallback apply, void* context) {
        uint32_t pos = nowMs - loopStartMs_;
        if (pos >= loopMs_) {
            const uint32_t passes = pos / loopMs_;
            loopStartMs_ += passes * loopMs_;
            pos -= passes * loopMs_;
            if (!offsetArmed_) {
                // End of the guard pass: the reference was latched below.
                offsetArmed_ = true;
            }
            markUntilMs_ = nowMs + LED_LOOP_MARK_MS;
        }
        uint16_t index = (uint16_t)(pos / FRAME_MS);
        if (index >= loopFrames_) {
            index = (uint16_t)(loopFrames_ - 1);
        }

        if (!offsetArmed_) {
            // First pass after the take: knobs and MCC ignored. Latch them
            // as the offset reference on every update (the last one wins).
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                knobRef_[i] = liveKnobs_[i];
            }
            for (uint8_t i = 0; i < CC_COUNT; ++i) {
                ccRef_[i] = currentCc_[i];
            }
        }

        if (holding_) {
            overdub(index);
        }
        updatePlaybackLed(nowMs);

        if (haveApplied_ && index == frameIndex_) {
            return;
        }
        frameIndex_ = index;
        haveApplied_ = true;
        if (apply == nullptr) {
            return;
        }

        const Frame& stored = frames_[index];
        Frame out = stored;
        if (offsetArmed_) {
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                if (!(overdubKnobs_ & (1u << i))) {
                    out.knobs[i] = shifted(stored.knobs[i],
                                           (int32_t)liveKnobs_[i] - knobRef_[i],
                                           KNOB_MAX);
                }
            }
            for (uint8_t i = 0; i < CC_COUNT; ++i) {
                if (stored.ccs[i] != CC_UNSET &&
                    !(overdubCcs_ & (1u << i))) {
                    out.ccs[i] = (uint8_t)shifted(
                        stored.ccs[i], (int32_t)currentCc_[i] - ccRef_[i],
                        CC_MAX);
                }
            }
        }
        apply(context, out);
    }

    // MODE pressed in PLAYBACK: snapshot the controls; a parameter is
    // overdubbed once it leaves its snapshot.
    void startHold() {
        holding_ = true;
        overdubKnobs_ = 0;
        overdubCcs_ = 0;
        haveOverdubIndex_ = false;
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            holdKnobs_[i] = liveKnobs_[i];
        }
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            holdCc_[i] = currentCc_[i];
        }
    }

    // Detect the moved parameters, then write their live values into every
    // frame from the last overdubbed one up to the playhead (wrapping).
    void overdub(uint16_t index) {
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            const uint16_t bit = (uint16_t)(1u << i);
            if (overdubKnobs_ & bit) {
                continue;
            }
            const int32_t moved = (int32_t)liveKnobs_[i] - holdKnobs_[i];
            if (moved > OVERDUB_KNOB_THRESHOLD ||
                moved < -(int32_t)OVERDUB_KNOB_THRESHOLD) {
                overdubKnobs_ |= bit;
            }
        }
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            const uint16_t bit = (uint16_t)(1u << i);
            if ((overdubCcs_ & bit) || currentCc_[i] == CC_UNSET ||
                currentCc_[i] == holdCc_[i]) {
                continue;
            }
            overdubCcs_ |= bit;
            if (!(recordedCcs_ & bit)) {
                // New to the take: the rest of the loop keeps the value it
                // had before the hold (or the first move's value).
                const uint8_t fill = holdCc_[i] != CC_UNSET
                    ? holdCc_[i] : currentCc_[i];
                for (uint16_t t = 0; t < loopFrames_; ++t) {
                    frames_[t].ccs[i] = fill;
                }
                recordedCcs_ |= bit;
            }
        }
        if (overdubKnobs_ == 0 && overdubCcs_ == 0) {
            return;
        }

        uint16_t t = index;
        if (haveOverdubIndex_ && overdubIndex_ != index) {
            t = (uint16_t)((overdubIndex_ + 1) % loopFrames_);
        }
        for (;;) {
            Frame& frame = frames_[t];
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                if (overdubKnobs_ & (1u << i)) {
                    frame.knobs[i] = liveKnobs_[i];
                }
            }
            for (uint8_t i = 0; i < CC_COUNT; ++i) {
                if (overdubCcs_ & (1u << i)) {
                    frame.ccs[i] = currentCc_[i];
                }
            }
            if (t == index) {
                break;
            }
            t = (uint16_t)((t + 1) % loopFrames_);
        }
        overdubIndex_ = index;
        haveOverdubIndex_ = true;
    }

    // MODE released in PLAYBACK. Nothing moved: a click, back to LIVE.
    // Otherwise keep looping; the overdubbed curves restart with no offset
    // (reference = control position at the release).
    void releaseHold(uint32_t nowMs) {
        (void)nowMs;
        holding_ = false;
        if (overdubKnobs_ == 0 && overdubCcs_ == 0) {
            state_ = MotionRecorder::STATE_LIVE;
            ledOn_ = false;
            setLed(false);
            return;
        }
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            if (overdubKnobs_ & (1u << i)) {
                knobRef_[i] = liveKnobs_[i];
            }
        }
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            if (overdubCcs_ & (1u << i)) {
                ccRef_[i] = currentCc_[i];
            }
        }
        overdubKnobs_ = 0;
        overdubCcs_ = 0;
        ledOn_ = true;
        setLed(true);
    }

    void blink(uint32_t nowMs) {
        if ((uint32_t)(nowMs - lastBlinkMs_) >= LED_BLINK_HALF_PERIOD_MS) {
            lastBlinkMs_ = nowMs;
            ledOn_ = !ledOn_;
            setLed(ledOn_);
        }
    }

    // Overdubbing: blink. Otherwise solid, dark for LED_LOOP_MARK_MS after
    // each loop restart.
    void updatePlaybackLed(uint32_t nowMs) {
        if (isOverdubbing()) {
            blink(nowMs);
            return;
        }
        const bool on = (int32_t)(nowMs - markUntilMs_) >= 0;
        if (on != ledOn_) {
            ledOn_ = on;
            setLed(on);
        }
    }

    void setLed(bool on) {
        if (ledCallback_ != nullptr) {
            ledCallback_(on);
        }
    }

    LedCallback ledCallback_ = nullptr;
    uint32_t debounceMs_ = 30;

    State state_ = MotionRecorder::STATE_LIVE;
    uint32_t startMs_ = 0;         // RECORDING: time of the start press
    uint16_t framesWritten_ = 0;   // RECORDING: frames 0..n-1 stored
    uint32_t loopMs_ = 0;          // loop length (time between the presses)
    uint16_t loopFrames_ = 0;
    uint32_t loopStartMs_ = 0;     // PLAYBACK: start of the current pass
    uint16_t frameIndex_ = 0;
    bool haveApplied_ = false;
    bool offsetArmed_ = false;
    uint16_t recordedCcs_ = 0;     // bit i: ccs[i] recorded in the take
    uint8_t currentCc_[CC_COUNT];  // latest live MCC values
    uint16_t liveKnobs_[KNOB_COUNT] = {};
    bool haveLiveKnobs_ = false;
    uint16_t knobRef_[KNOB_COUNT] = {};
    uint8_t ccRef_[CC_COUNT] = {};

    // Overdub hold (MODE held in PLAYBACK).
    bool holding_ = false;
    uint8_t overdubKnobs_ = 0;     // bit i: knob i overdubbed
    uint16_t overdubCcs_ = 0;      // bit i: ccs[i] overdubbed
    uint16_t holdKnobs_[KNOB_COUNT] = {};
    uint8_t holdCc_[CC_COUNT] = {};
    uint16_t overdubIndex_ = 0;    // last frame overdubbed in this hold
    bool haveOverdubIndex_ = false;

    bool ledOn_ = false;
    uint32_t lastBlinkMs_ = 0;
    uint32_t markUntilMs_ = 0;
    bool buttonDown_ = false;
    bool haveLastPress_ = false;
    uint32_t lastPressMs_ = 0;

    // One minute of P1..P4 plus twelve 7-bit MCC values every 20 ms (60 KB).
    // Volatile runtime state only; nothing is persisted.
    Frame frames_[MAX_FRAMES] = {};
};
