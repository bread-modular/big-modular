#ifndef ENVATTACKSUSTAINRELEASE_H
#define ENVATTACKSUSTAINRELEASE_H

#include "EnvelopeGenerator.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This is a very typical attack sustain release envelope generator.
//
// ACID: timed phases and knob zero as in EnvelopeGenerator.h. An instant
// attack (ATTACK at 0) holds full level for at least ENV_MIN_PULSE_US, so a
// very short gate with both knobs at 0 gives the same 1 ms pulse with an
// instant drop as HR; a longer gate sustains as before.
class EnvAttackSustainRelease : public EnvelopeGenerator {
public:
    enum EnvelopeState { IDLE, ATTACK, TOP, SUSTAIN, RELEASE };

    EnvAttackSustainRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), attackDuration(0), releaseDuration(0),
        envelopeValue(0)
    { }

    // update() takes the effective knob values (0–1023: knob or recorded take, + MIDI CC)
    void update(bool gate, int cv1, int cv2) {
        unsigned long now = micros();

        // Trigger new envelope on rising edge
        if (gate && !lastGateState) {
            attackDuration = envKnobTime(cv1, 500000UL);
            phaseStartTime = now;
            if (attackDuration == 0) {
                setLevel(255);  // Instant attack: full level for the min pulse
                state = TOP;
            } else {
                setLevel(0);
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
            endAttack(gate, cv2, now);
            return;
        }

        // TOP phase (instant attack only): hold full level for the min pulse
        if (state == TOP) {
            if (now - phaseStartTime >= ENV_MIN_PULSE_US) {
                endAttack(gate, cv2, now);
            }
            return;
        }

        // SUSTAIN phase: maintain full level until gate goes low
        if (state == SUSTAIN) {
            if (!gate) {
                startRelease(cv2, now);
            }
            return;
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
    void endAttack(bool gate, int cv2, unsigned long now) {
        if (gate) {
            state = SUSTAIN;
        } else {
            startRelease(cv2, now);
        }
    }

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

#endif // ENVATTACKSUSTAINRELEASE_H
