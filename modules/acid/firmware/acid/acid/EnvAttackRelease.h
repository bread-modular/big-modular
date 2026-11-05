#ifndef ENVATTACKRELEASE_H
#define ENVATTACKRELEASE_H

#include "EnvelopeGenerator.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This is a very typical attack release envelope generator.
//
// ACID: timed phases and knob zero as in EnvelopeGenerator.h. An instant
// attack (ATTACK at 0) holds full level for ENV_MIN_PULSE_US, so both knobs
// at 0 give the same 1 ms pulse with an instant drop as HR.
class EnvAttackRelease : public EnvelopeGenerator {
public:
    enum EnvelopeState { IDLE, ATTACK, TOP, RELEASE };

    EnvAttackRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), attackDuration(0), releaseDuration(0),
        envelopeValue(0)
    { }

    // update() takes the effective knob values (0–1023: knob or recorded take, + MIDI CC)
    void update(bool gate, int cv1, int cv2) override {
        unsigned long now = micros();

        // Trigger new envelope on rising edge
        if (gate && !lastGateState) {
            attackDuration = envKnobTime(cv1, 1000000UL);
            phaseStartTime = now;
            if (attackDuration == 0) {
                setLevel(255);  // Instant attack: full level for the min pulse
                state = TOP;
            } else {
                setLevel(0);    // Start from silence
                state = ATTACK;
            }
        }

        lastGateState = gate;

        // ATTACK phase: ramp up linearly over attackDuration
        if (state == ATTACK) {
            unsigned long elapsed = now - phaseStartTime;
            if (elapsed < attackDuration) {
                setLevel(envRamp(elapsed, attackDuration));
                return;
            }
            setLevel(255);
            startRelease(cv2, now);  // Auto-transition to release
        }

        // TOP phase (instant attack only): hold full level for the min pulse
        if (state == TOP) {
            if (now - phaseStartTime < ENV_MIN_PULSE_US) {
                return;
            }
            startRelease(cv2, now);
        }

        // RELEASE phase: ramp down linearly over releaseDuration
        if (state == RELEASE) {
            unsigned long elapsed = now - phaseStartTime;
            if (elapsed >= releaseDuration) {
                setLevel(0);
                state = IDLE;  // Release complete
                return;
            }
            setLevel(255 - envRamp(elapsed, releaseDuration));
            return;
        }
    }

private:
    void startRelease(int cv2, unsigned long now) {
        releaseDuration = envKnobTime(cv2, 1000000UL);
        phaseStartTime = now;
        state = RELEASE;
    }

    void setLevel(int value) {
        if (value != envelopeValue) {
            envelopeValue = value;
            setEnvelopeValue(envelopeValue);
        }
    }

    EnvelopeState state;
    bool lastGateState;
    unsigned long phaseStartTime;
    unsigned long attackDuration;
    unsigned long releaseDuration;
    int envelopeValue;
};

#endif // ENVATTACKRELEASE_H
