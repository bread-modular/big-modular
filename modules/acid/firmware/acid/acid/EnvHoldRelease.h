#ifndef ENVHOLDRELEASE_H
#define ENVHOLDRELEASE_H

#include "EnvelopeGenerator.h"
#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// This class implements a 0‑attack envelope generator with a hold phase
// and a release phase. The hold time is determined by CV1 (plus modulation from MIDI CC22),
// and the release time is determined by CV2 (plus modulation from MIDI CC75).
// The envelope drives the DAC output. (LED flashing has been removed.)
//
// ACID: timed release and knob zero as in EnvelopeGenerator.h; with both
// knobs at 0 the envelope is an ENV_MIN_PULSE_US pulse with an instant drop.

class EnvHoldRelease : public EnvelopeGenerator {
public:
    enum EnvelopeState { IDLE, HOLD, RELEASE };

    EnvHoldRelease()
      : state(IDLE), lastGateState(false),
        phaseStartTime(0), holdDuration(0), releaseDuration(0),
        envelopeValue(0)
    { }

    // update() takes the effective knob values (0–1023: knob or recorded take, + MIDI CC)
    void update(bool gate, int cv1, int cv2) {
        unsigned long now = micros();

        // Trigger a new envelope on rising edge.
        if (gate && !lastGateState) {
            envelopeValue = 255; // Instant attack: full amplitude.
            setEnvelopeValue(envelopeValue);            

            // Map CV1 to a hold time between 0 and 100,000 µs.
            holdDuration = envKnobTime(cv1, 100000UL);
            if (holdDuration < ENV_MIN_PULSE_US) holdDuration = ENV_MIN_PULSE_US;

            phaseStartTime = now;
            state = HOLD;

            lastGateState = gate;
            return;
        }

        lastGateState = gate;

        // HOLD phase: wait until hold time elapses.
        if (state == HOLD) {
            // do nothing if we are still in the hold phase
            if (now - phaseStartTime < holdDuration) {
                return;
            }
            
            // Map CV2 to a release time between 0 and 100,000 µs.
            releaseDuration = envKnobTime(cv2, 100000UL);
            phaseStartTime = now;
            state = RELEASE;
        }

        // RELEASE phase: ramp down linearly over releaseDuration.
        if (state == RELEASE) {
            unsigned long elapsed = now - phaseStartTime;
            if (elapsed >= releaseDuration) {
                envelopeValue = 0;
                setEnvelopeValue(envelopeValue);
                state = IDLE;
                return;
            }

            int value = 255 - envRamp(elapsed, releaseDuration);
            if (value != envelopeValue) {
                envelopeValue = value;
                setEnvelopeValue(envelopeValue);
            }
            return;
        }
    }

private:
    EnvelopeState state;
    bool lastGateState;
    unsigned long phaseStartTime;
    unsigned long holdDuration;
    unsigned long releaseDuration;
    int envelopeValue;
};

#endif // ENVHOLDRELEASE_H
