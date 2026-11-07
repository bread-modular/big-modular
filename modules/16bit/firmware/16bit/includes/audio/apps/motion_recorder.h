#pragma once

#include <stdint.h>

// MotionRecorder — MIDI-clock-synchronised, RAM-only automation recorder.
//
// One take is four bars of 4/4 at MIDI's 24 PPQN: 384 frames. Each frame holds
// the four panel knobs P1..P4 (raw 12-bit ADC values, not reduced to the 8-bit
// storage used by the ATtiny firmware) and the twelve MCC CCs (Bank A
// CC20..23, Bank B CC27..30, Bank C CC85..88), so knob and MIDI automation
// stay phase aligned.
//
// MODE cycles LIVE -> RECORDING -> PLAYBACK -> LIVE, as the 8bit CvRecorder
// (opt/attiny1616-tools/lib/CvRecorder):
//
//   * RECORDING: LED blinks; every clock pulse stores the live frame. Live
//     controls keep driving the sound. MODE aborts the take.
//   * PLAYBACK (automatic after 384 clocks): LED solid; every clock pulse
//     replays the frame at the playhead. A MODE click (press and release
//     without moving anything) returns to LIVE on the release.
//   * OVERDUB (big-modular): hold MODE in PLAYBACK and move any knob or MCC
//     control. From its first move until MODE is released, that parameter's
//     live value replaces the recorded one at the playhead (other parameters
//     keep playing back) and the LED blinks. Releasing MODE keeps the loop
//     playing; its new curve plays back with no offset until the control
//     moves again. A CC that wasn't in the take joins it: the frames outside
//     the overdubbed span carry its value from before the hold.
//   * OFFSET (big-modular, as the 8bit recorder): for the first 4-bar pass of
//     PLAYBACK the knobs and MCC are ignored, so the hand that just finished
//     the take can't nudge it. At the end of that pass their positions are
//     latched as the reference; from then on moving a knob or an MCC control
//     shifts its whole recorded curve by (live - reference), clamped.
//   * MIDI Start rewinds an active take or loop.
//
// A CC that never arrived before or during the take is not recorded (its frame
// value is CC_UNSET) and stays live in PLAYBACK. A CC first moved part-way
// through the take is back-filled with its first value, so every recorded CC
// has a value in every frame.
//
// The class deliberately has no Pico/IO dependency. The app supplies a small
// LED callback and forwards the debounced button edge from IO. This keeps the
// state machine host-testable and makes it impossible for a recording to touch
// the filesystem or flash.
//
// Shared by every 16bit app that drives its MODE button this way (sampler,
// monosynth and polysynth); apps own what the recorded values mean.
class MotionRecorder {
public:
    static constexpr uint16_t MIDI_PPQN = 24;
    static constexpr uint16_t BEATS_PER_BAR = 4;
    static constexpr uint16_t BARS = 4;
    static constexpr uint16_t LOOP_TICKS = MIDI_PPQN * BEATS_PER_BAR * BARS;
    static constexpr uint16_t GUARD_TICKS = LOOP_TICKS;  // knobs ignored 1 pass
    static constexpr uint32_t LED_BLINK_HALF_PERIOD_MS = 150;
    // A knob counts as moved during an overdub hold once it leaves its
    // position at the start of the hold by more than this (ADC noise guard).
    static constexpr uint16_t OVERDUB_KNOB_THRESHOLD = 48;

    static constexpr uint8_t KNOB_P1 = 0;
    static constexpr uint8_t KNOB_P2 = 1;
    static constexpr uint8_t KNOB_P3 = 2;
    static constexpr uint8_t KNOB_P4 = 3;
    static constexpr uint8_t KNOB_COUNT = 4;
    static constexpr uint16_t KNOB_MAX = 4095;

    static constexpr uint8_t MCC_BANK_A_FIRST_CC = 20;
    static constexpr uint8_t MCC_BANK_B_FIRST_CC = 27;
    static constexpr uint8_t MCC_BANK_C_FIRST_CC = 85;
    static constexpr uint8_t MCC_CCS_PER_BANK = 4;
    static constexpr uint8_t MCC_BANK_A_COUNT = MCC_CCS_PER_BANK;
    static constexpr uint8_t CC_COUNT = 3 * MCC_CCS_PER_BANK;
    static constexpr uint8_t CC_UNSET = 0xFF;
    static constexpr uint8_t CC_MAX = 127;

    struct Frame {
        uint16_t knobs[KNOB_COUNT];
        uint8_t ccs[CC_COUNT];  // CC_UNSET = not recorded, leave it live
    };

    using LedCallback = void (*)(bool on);
    using PlaybackCallback = void (*)(void* context, const Frame& frame);

    enum State : uint8_t {
        STATE_LIVE = 0,
        STATE_RECORDING,
        STATE_PLAYBACK,
    };

    explicit MotionRecorder(LedCallback led = nullptr,
                            uint32_t debounceMs = 30)
        : ledCallback_(led), debounceMs_(debounceMs) {
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            currentCc_[i] = CC_UNSET;
        }
    }

    void setLedCallback(LedCallback led) {
        ledCallback_ = led;
    }

    // Back to LIVE. Live CC values are kept (they mirror the app's state).
    void begin(uint32_t nowMs = 0) {
        state_ = STATE_LIVE;
        tick_ = 0;
        ledOn_ = false;
        lastBlinkMs_ = nowMs;
        buttonDown_ = false;
        haveLastPress_ = false;
        holding_ = false;
        setLed(false);
    }

    // Call from the firmware's main loop. LED animation is non-blocking.
    void update(uint32_t nowMs) {
        if (state_ != STATE_RECORDING && !isOverdubbing()) {
            return;
        }

        if ((uint32_t)(nowMs - lastBlinkMs_) >= LED_BLINK_HALF_PERIOD_MS) {
            lastBlinkMs_ = nowMs;
            ledOn_ = !ledOn_;
            setLed(ledOn_);
        }
    }

    // IO already reports button edges, but this small guard prevents a noisy
    // button from starting multiple takes. The press edge cycles LIVE and
    // RECORDING; in PLAYBACK the press starts an overdub hold and the release
    // either keeps the overdub or, if nothing moved, returns to LIVE.
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
        if (state_ == STATE_PLAYBACK) {
            startHold();
            return;
        }
        cycleState(nowMs);
    }

    bool isRecording() const { return state_ == STATE_RECORDING; }
    bool isPlayingBack() const { return state_ == STATE_PLAYBACK; }
    bool isLive() const { return state_ == STATE_LIVE; }
    bool isOffsetArmed() const {
        return state_ == STATE_PLAYBACK && guardTicks_ >= GUARD_TICKS;
    }
    // MODE held in PLAYBACK and at least one parameter moved.
    bool isOverdubbing() const {
        return holding_ && (overdubKnobs_ != 0 || overdubCcs_ != 0);
    }
    State getState() const { return state_; }
    uint16_t getTick() const { return tick_; }

    // Keep the latest live MCC value. Returns false (and ignores the value)
    // for CCs outside the three MCC banks.
    bool setCurrentCc(uint8_t cc, uint8_t value) {
        int index = ccIndex(cc);
        if (index < 0) {
            return false;
        }
        currentCc_[index] = value & 0x7F;
        return true;
    }

    // Forget the live MCC values (the app reset its parameters to defaults).
    void clearCurrentCcs() {
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            currentCc_[i] = CC_UNSET;
        }
    }

    // Latest live value, CC_UNSET if it never arrived (or not an MCC CC).
    uint8_t getCurrentCc(uint8_t cc) const {
        int index = ccIndex(cc);
        return index >= 0 ? currentCc_[index] : CC_UNSET;
    }

    // True while PLAYBACK drives this CC: the app must not apply it live.
    bool ownsCc(uint8_t cc) const {
        int index = ccIndex(cc);
        return state_ == STATE_PLAYBACK && index >= 0 &&
               (recordedCcs_ & (1u << index)) != 0;
    }

    // Feed one MIDI timing-clock pulse with the live knob values (P1..P4).
    // During recording the live knobs and MCC values are copied into RAM.
    // During playback the frame at the old playhead (plus the knob/MCC offset
    // once armed) is delivered to the app before the playhead advances; while
    // MODE is held, moved parameters are overdubbed into that frame first.
    void onClock(const uint16_t liveKnobs[KNOB_COUNT],
                 PlaybackCallback apply = nullptr,
                 void* context = nullptr) {
        if (state_ == STATE_RECORDING) {
            Frame& frame = frames_[tick_];
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                frame.knobs[i] = liveKnobs[i];
            }
            for (uint8_t i = 0; i < CC_COUNT; ++i) {
                frame.ccs[i] = currentCc_[i];
            }
            advancePlayhead();
            if (tick_ == 0) {
                finishTake();
            }
            return;
        }

        if (state_ != STATE_PLAYBACK) {
            return;  // LIVE: keep the playhead idle
        }

        if (holding_) {
            overdub(liveKnobs);
        }

        const Frame& stored = frames_[tick_];
        Frame out;
        if (guardTicks_ < GUARD_TICKS) {
            // First pass after the take: knobs and MCC ignored. Latch them as
            // the offset reference on every guard tick (the last one wins).
            ++guardTicks_;
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                knobRef_[i] = liveKnobs[i];
            }
            for (uint8_t i = 0; i < CC_COUNT; ++i) {
                ccRef_[i] = currentCc_[i];
            }
            out = stored;
        } else {
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                out.knobs[i] = (overdubKnobs_ & (1u << i))
                    ? stored.knobs[i]
                    : shifted(stored.knobs[i],
                              (int32_t)liveKnobs[i] - knobRef_[i],
                              KNOB_MAX);
            }
            for (uint8_t i = 0; i < CC_COUNT; ++i) {
                out.ccs[i] = stored.ccs[i] == CC_UNSET ||
                                     (overdubCcs_ & (1u << i))
                    ? stored.ccs[i]
                    : (uint8_t)shifted(stored.ccs[i],
                                       (int32_t)currentCc_[i] - ccRef_[i],
                                       CC_MAX);
            }
        }
        if (apply != nullptr) {
            apply(context, out);
        }
        advancePlayhead();
    }

    // MIDI Start rewinds an active take/loop. The next clock pulse records or
    // plays frame zero, matching the 8bit recorder's behaviour.
    void onStart() {
        if (state_ != STATE_LIVE) {
            tick_ = 0;
        }
    }

    // MCC CC number -> frame index 0..11, or -1 outside the three banks.
    static int ccIndex(uint8_t cc) {
        if (cc >= MCC_BANK_A_FIRST_CC &&
            cc < MCC_BANK_A_FIRST_CC + MCC_CCS_PER_BANK) {
            return cc - MCC_BANK_A_FIRST_CC;
        }
        if (cc >= MCC_BANK_B_FIRST_CC &&
            cc < MCC_BANK_B_FIRST_CC + MCC_CCS_PER_BANK) {
            return MCC_CCS_PER_BANK + (cc - MCC_BANK_B_FIRST_CC);
        }
        if (cc >= MCC_BANK_C_FIRST_CC &&
            cc < MCC_BANK_C_FIRST_CC + MCC_CCS_PER_BANK) {
            return 2 * MCC_CCS_PER_BANK + (cc - MCC_BANK_C_FIRST_CC);
        }
        return -1;
    }

    // Frame index 0..11 -> MCC CC number.
    static uint8_t ccNumber(uint8_t index) {
        static const uint8_t firstCc[3] = {
            MCC_BANK_A_FIRST_CC, MCC_BANK_B_FIRST_CC, MCC_BANK_C_FIRST_CC};
        return firstCc[index / MCC_CCS_PER_BANK] + index % MCC_CCS_PER_BANK;
    }

private:
    static uint16_t shifted(uint16_t stored, int32_t offset, uint16_t max) {
        int32_t v = (int32_t)stored + offset;
        if (v < 0) return 0;
        if (v > max) return max;
        return (uint16_t)v;
    }

    // Take complete: back-fill CCs first moved part-way through, remember
    // which CCs the loop owns, then start looping with the guard pass.
    void finishTake() {
        recordedCcs_ = 0;
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            uint16_t first = 0;
            while (first < LOOP_TICKS && frames_[first].ccs[i] == CC_UNSET) {
                ++first;
            }
            if (first == LOOP_TICKS) {
                continue;  // never arrived: stays live in PLAYBACK
            }
            for (uint16_t t = 0; t < first; ++t) {
                frames_[t].ccs[i] = frames_[first].ccs[i];
            }
            recordedCcs_ |= (uint16_t)(1u << i);
        }
        state_ = STATE_PLAYBACK;
        guardTicks_ = 0;
        ledOn_ = true;
        setLed(true);
    }

    // MODE pressed in PLAYBACK: snapshot the controls; a parameter is
    // overdubbed once it leaves its snapshot. The knob snapshot is taken on
    // the first clock of the hold (the button edge carries no knob values).
    void startHold() {
        holding_ = true;
        holdKnobsLatched_ = false;
        overdubKnobs_ = 0;
        overdubCcs_ = 0;
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            holdCc_[i] = currentCc_[i];
        }
    }

    // Write the moved parameters' live values into the frame at the playhead.
    void overdub(const uint16_t liveKnobs[KNOB_COUNT]) {
        if (!holdKnobsLatched_) {
            holdKnobsLatched_ = true;
            for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
                holdKnobs_[i] = liveKnobs[i];
            }
        }
        Frame& frame = frames_[tick_];
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            const uint16_t bit = (uint16_t)(1u << i);
            if (!(overdubKnobs_ & bit)) {
                const int32_t moved = (int32_t)liveKnobs[i] - holdKnobs_[i];
                if (moved <= OVERDUB_KNOB_THRESHOLD &&
                    moved >= -(int32_t)OVERDUB_KNOB_THRESHOLD) {
                    continue;
                }
                overdubKnobs_ |= bit;
            }
            frame.knobs[i] = liveKnobs[i];
            lastLiveKnobs_[i] = liveKnobs[i];
        }
        for (uint8_t i = 0; i < CC_COUNT; ++i) {
            const uint16_t bit = (uint16_t)(1u << i);
            if (currentCc_[i] == CC_UNSET) {
                continue;
            }
            if (!(overdubCcs_ & bit)) {
                if (currentCc_[i] == holdCc_[i]) {
                    continue;
                }
                overdubCcs_ |= bit;
                if (!(recordedCcs_ & bit)) {
                    // New to the take: the rest of the loop keeps the value
                    // it had before the hold (or the first move's value).
                    const uint8_t fill = holdCc_[i] != CC_UNSET
                        ? holdCc_[i] : currentCc_[i];
                    for (uint16_t t = 0; t < LOOP_TICKS; ++t) {
                        frames_[t].ccs[i] = fill;
                    }
                    recordedCcs_ |= bit;
                }
            }
            frame.ccs[i] = currentCc_[i];
        }
    }

    // MODE released in PLAYBACK. Nothing moved: a click, back to LIVE.
    // Otherwise keep looping; the overdubbed curves restart with no offset
    // (reference = control position at the release).
    void releaseHold(uint32_t nowMs) {
        holding_ = false;
        if (overdubKnobs_ == 0 && overdubCcs_ == 0) {
            cycleState(nowMs);
            return;
        }
        for (uint8_t i = 0; i < KNOB_COUNT; ++i) {
            if (overdubKnobs_ & (1u << i)) {
                knobRef_[i] = lastLiveKnobs_[i];
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

    void cycleState(uint32_t nowMs) {
        switch (state_) {
            case STATE_LIVE:
                state_ = STATE_RECORDING;
                tick_ = 0;
                ledOn_ = false;
                lastBlinkMs_ = nowMs;
                setLed(false);
                break;
            case STATE_RECORDING:
                // An incomplete take is inaccessible after abort; the old RAM
                // contents are intentionally not exposed as a valid loop.
                state_ = STATE_LIVE;
                tick_ = 0;
                ledOn_ = false;
                setLed(false);
                break;
            case STATE_PLAYBACK:
                state_ = STATE_LIVE;
                tick_ = 0;
                ledOn_ = false;
                setLed(false);
                break;
        }
    }

    void advancePlayhead() {
        ++tick_;
        if (tick_ >= LOOP_TICKS) {
            tick_ = 0;
        }
    }

    void setLed(bool on) {
        if (ledCallback_ != nullptr) {
            ledCallback_(on);
        }
    }

    LedCallback ledCallback_ = nullptr;
    uint32_t debounceMs_ = 30;

    State state_ = STATE_LIVE;
    uint16_t tick_ = 0;
    uint16_t guardTicks_ = 0;
    uint16_t recordedCcs_ = 0;           // bit i: ccs[i] recorded in the take
    uint8_t currentCc_[CC_COUNT];        // latest live MCC values
    uint16_t knobRef_[KNOB_COUNT] = {};  // positions latched after the guard
    uint8_t ccRef_[CC_COUNT] = {};

    // Overdub hold (MODE held in PLAYBACK).
    bool holding_ = false;
    bool holdKnobsLatched_ = false;
    uint8_t overdubKnobs_ = 0;                // bit i: knob i overdubbed
    uint16_t overdubCcs_ = 0;                 // bit i: ccs[i] overdubbed
    uint16_t holdKnobs_[KNOB_COUNT] = {};     // knobs at the start of the hold
    uint8_t holdCc_[CC_COUNT] = {};           // MCC values at the press
    uint16_t lastLiveKnobs_[KNOB_COUNT] = {};

    bool ledOn_ = false;
    uint32_t lastBlinkMs_ = 0;
    bool buttonDown_ = false;
    bool haveLastPress_ = false;
    uint32_t lastPressMs_ = 0;

    // Four bars of P1..P4 plus twelve 7-bit MCC values per clock (7.5 KB).
    // This is volatile runtime state only; nothing is persisted.
    Frame frames_[LOOP_TICKS] = {};
};
