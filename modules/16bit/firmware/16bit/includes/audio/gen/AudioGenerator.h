#pragma once

#include "audio/manager.h"

class AudioGenerator {
public:

    virtual void init(AudioManager *audioManager) = 0;
    
    virtual void setFrequency(uint16_t frequency) = 0;

    // Exact pitch. The BM generators keep their whole-hertz setFrequency();
    // Wavetable overrides this with the unrounded frequency.
    virtual void setFrequencyHz(float frequency) {
        setFrequency((uint16_t)frequency);
    }

    virtual void reset() = 0;

    virtual float getSample() = 0;
};
