#pragma once

#include "pico/stdlib.h"
#include "audio/manager.h"
#include "./AudioGenerator.h"
#include "./wavetable_osc.h"

// AudioGenerator wrapper of WavetableOsc (polysynth P1 / P2 wavetables).
class Wavetable: public AudioGenerator {
    private:
        const WavetableControl* control;
        WavetableOsc osc;

    public:
        explicit Wavetable(const WavetableControl* control = nullptr) : control(control) {}

        void setControl(const WavetableControl* control) {
            this->control = control;
        }

        void init(AudioManager* audioManager) {
            osc.init(control, audioManager->getDac()->getSampleRate());
        }

        void setFrequency(uint16_t frequency) {
            osc.setFrequency(frequency);
        }

        void setFrequencyHz(float frequency) override {
            osc.setFrequency(frequency);
        }

        void reset() {
            osc.reset();
        }

        float getSample() {
            return osc.getSample();
        }
};
