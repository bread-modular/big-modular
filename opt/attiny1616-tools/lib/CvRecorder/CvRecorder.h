#ifndef CV_RECORDER_H
#define CV_RECORDER_H

#include <Arduino.h>

// ============================================================================
// CvRecorder — MIDI-clock-synced CV motion recorder (one-shot 4-bar take).
//
// Shared ATtiny1616 library (opt/attiny1616-tools/lib/CvRecorder). Bread
// Modular crash recorder plus the loop offset below. Sketches symlink this
// file into their sketch folder; host tests: lib/CvRecorder/sim.sh.
//
// MODE button cycles through three states:
//
//   LIVE --press--> RECORDING --(384 clock ticks = 4 bars)--> PLAYBACK
//     ^                                                            |
//     +-------------------------- press ---------------------------+
//
//   * RECORDING: LED BLINKS. Every MIDI clock tick snapshots the live CV1/CV2
//     into RAM (24 PPQN -> 96 ticks/bar -> exactly 4 bars = 384 ticks,
//     768 bytes SRAM). Live CV keeps driving the synth so you hear what you
//     record. The take always lasts a full 4 bars from the press.
//   * PLAYBACK (automatic after 4 bars): LED SOLID. Every clock tick replays
//     the stored CV pair at the playhead.
//   * OFFSET (big-modular addition, not in Bread Modular): for the first
//     4-bar pass of PLAYBACK the knobs are ignored, so the hand that just
//     finished the take can't nudge it by accident. At the end of that pass
//     the knob positions are latched as the reference; from then on turning a
//     knob shifts its whole recorded curve by (knob - reference), clamped to
//     0..1023. A new take or a press back to LIVE clears the offset.
//   * Pressing MODE again (in PLAYBACK, or during RECORDING to abort/discard)
//     returns to LIVE — stock behaviour, knobs drive the sound directly.
//   * MIDI Start rewinds the playhead to bar 1 while recording or looping.
//
// Storage: one 8-bit sample per CV per tick (10-bit ADC >> 2), shifted back
// << 2 on replay — plenty of resolution for colour changes.
// ============================================================================

#define REC_PPQN            24UL                       // MIDI clocks per beat
#define REC_BEATS_PER_BAR   4UL                        // 4/4 assumed
#define REC_BARS            4UL
#define REC_LOOP_TICKS      (REC_PPQN * REC_BEATS_PER_BAR * REC_BARS) // 384
#define REC_BLINK_MS        150UL                      // LED blink half-period
#define REC_GUARD_TICKS     REC_LOOP_TICKS             // knobs ignored for 1 pass
#define REC_CV_MAX          1023

class CvRecorder {
public:
    // Playback consumer: called with a recorded CV pair (0..1023) each tick.
    typedef void (*ApplyCallback)(uint16_t cv1, uint16_t cv2);

    enum State : uint8_t { STATE_LIVE = 0, STATE_RECORDING, STATE_PLAYBACK };

    CvRecorder(uint8_t modePin, uint8_t ledPin, unsigned long debounceMs = 30)
        : modePin(modePin), ledPin(ledPin), debounceMs(debounceMs) {}

    void begin() {
        pinMode(modePin, INPUT_PULLUP);   // button pulls to GND when pressed
        pinMode(ledPin, OUTPUT);
        digitalWrite(ledPin, LOW);
        lastButtonState = digitalRead(modePin);
        stableState = lastButtonState;
        lastChangeMs = millis();
        lastBlinkMs = lastChangeMs;
        ledOn = false;
    }

    // Call every loop() iteration: debounced click detection + LED animation.
    void update() {
        bool reading = digitalRead(modePin);
        if (reading != lastButtonState) {
            lastChangeMs = millis();
            lastButtonState = reading;
        }
        if ((millis() - lastChangeMs) >= debounceMs && reading != stableState) {
            stableState = reading;
            if (stableState == LOW) {              // click edge -> cycle state
                onPress();
            }
        }

        // Non-blocking LED blink while recording.
        if ((millis() - lastBlinkMs) >= REC_BLINK_MS) {
            lastBlinkMs = millis();
            ledOn = !ledOn;
            refreshLed();
        }
    }

    bool isRecording() const { return state == STATE_RECORDING; }
    bool isPlayingBack() const { return state == STATE_PLAYBACK; }
    bool isOffsetArmed() const { return guardTicks >= REC_GUARD_TICKS; }

    State getState() const { return state; }
    uint16_t getTick() const { return tick; }      // 0..REC_LOOP_TICKS-1

    // ---- MIDI clock interface -------------------------------------------

    // MIDI Start: rewind the playhead to bar 1, beat 1 (when active).
    void onStart() {
        if (state != STATE_LIVE) {
            tick = 0;
        }
    }

    // Advance by one clock tick. Pass the live 10-bit ADC reads; while
    // recording they are stored into RAM, while playing back the stored pair
    // at the old playhead is replayed via `apply`. Completing 384 recorded
    // ticks switches RECORDING -> PLAYBACK automatically.
    void onClock(uint16_t liveCv1, uint16_t liveCv2, ApplyCallback apply) {
        if (state == STATE_RECORDING) {
            buf1[tick] = liveCv1 >> 2;             // 10-bit -> 8-bit storage
            buf2[tick] = liveCv2 >> 2;
        } else if (state == STATE_PLAYBACK && apply) {
            int16_t offset1 = 0;
            int16_t offset2 = 0;
            if (guardTicks < REC_GUARD_TICKS) {
                // First pass after the take: knobs ignored. Latch them as
                // the offset reference on the last guard tick.
                guardTicks++;
                ref1 = liveCv1;
                ref2 = liveCv2;
            } else {
                offset1 = (int16_t)liveCv1 - (int16_t)ref1;
                offset2 = (int16_t)liveCv2 - (int16_t)ref2;
            }
            apply(shifted(buf1[tick], offset1),    // 8-bit -> 10-bit + offset
                  shifted(buf2[tick], offset2));
        } else {
            return;                                // LIVE: keep playhead idle
        }

        tick++;
        if (tick >= REC_LOOP_TICKS) {              // 4 bars done
            tick = 0;
            if (state == STATE_RECORDING) {
                state = STATE_PLAYBACK;            // take complete -> loop it
                guardTicks = 0;                    // knobs ignored for 1 pass
                refreshLed();
            }
        }
    }

private:
    static uint16_t shifted(uint8_t stored, int16_t offset) {
        int16_t v = (int16_t)((uint16_t)stored << 2) + offset;
        if (v < 0) return 0;
        if (v > REC_CV_MAX) return REC_CV_MAX;
        return (uint16_t)v;
    }

    void onPress() {
        switch (state) {
            case STATE_LIVE:
                state = STATE_RECORDING;           // start a fresh 4-bar take
                tick = 0;
                break;
            case STATE_RECORDING:
                state = STATE_LIVE;                // abort & discard the take
                break;
            case STATE_PLAYBACK:
                state = STATE_LIVE;                // stop looping, back to live
                break;
        }
        lastBlinkMs = millis();                    // restart blink phase
        refreshLed();
    }

    void refreshLed() {
        switch (state) {
            case STATE_RECORDING:
                digitalWrite(ledPin, ledOn ? HIGH : LOW);   // blink
                break;
            case STATE_PLAYBACK:
                digitalWrite(ledPin, HIGH);                 // solid
                break;
            default:
                digitalWrite(ledPin, LOW);                  // off (live)
                break;
        }
    }

    uint8_t modePin;
    uint8_t ledPin;
    unsigned long debounceMs;

    bool stableState = HIGH;
    bool lastButtonState = HIGH;
    unsigned long lastChangeMs = 0;

    State state = STATE_LIVE;
    bool ledOn = false;
    unsigned long lastBlinkMs = 0;
    uint16_t tick = 0;
    uint16_t guardTicks = 0;                       // PLAYBACK ticks so far
    uint16_t ref1 = 0;                             // knob positions latched
    uint16_t ref2 = 0;                             // at the end of the guard

    uint8_t buf1[REC_LOOP_TICKS];                  // CV1 motion, 384 bytes
    uint8_t buf2[REC_LOOP_TICKS];                  // CV2 motion, 384 bytes
};

#endif // CV_RECORDER_H
