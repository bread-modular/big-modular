#ifndef ENVELOPEGENERATOR_H
#define ENVELOPEGENERATOR_H

// ACID: the DAC runs on the 4.34 V reference at VDD = 3.3 V, so codes above
// ~194 (3.3 / 4.34 x 256) sit at the rail. Scale the 0..255 envelope to
// 0..ENV_DAC_MAX so the top is not flat (../../docs/research.md 3.2).
#define ENV_DAC_MAX 194

// ACID: shared envelope timing. Each phase level is computed from the elapsed
// time (not one step per loop pass), so short phases are not stretched by the
// loop rate, and the bottom of each knob reads as 0. With the knobs at 0 an
// envelope is an ENV_MIN_PULSE_US pulse at full level with an instant drop.
#define ENV_KNOB_ZERO     8      // knob values <= this count as 0
#define ENV_MIN_PULSE_US  1000UL // shortest pulse (knobs at 0)

// Knob (0..1023) to a phase time of 0..maxUs, the bottom ENV_KNOB_ZERO = 0.
static inline unsigned long envKnobTime(int cv, unsigned long maxUs) {
    return cv <= ENV_KNOB_ZERO ? 0 : map(cv, 0, 1023, 0, maxUs);
}

// Linear ramp position 0..255 after elapsed of duration (duration > elapsed).
static inline int envRamp(unsigned long elapsed, unsigned long duration) {
    return (int)(255UL * elapsed / duration);
}

class EnvelopeGenerator {
public:
    virtual ~EnvelopeGenerator() = default;
    virtual void update(bool gate, int cv1, int cv2) = 0;

    void setEnvelopeValue(uint8_t value) {
        level = value;
        DAC0.DATA = ((uint16_t)value * ENV_DAC_MAX + 127) / 255;
    }

    // Last envelope value written to the DAC, 0..255 (0 = silent).
    uint8_t getLevel() const {
        return level;
    }

private:
    uint8_t level = 0;

};

#endif // ENVELOPEGENERATOR_H
