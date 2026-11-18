#ifndef ENVELOPEGENERATOR_H
#define ENVELOPEGENERATOR_H

// ENV: the DAC runs on the 4.34 V reference (VDD = 5 V, HT7550-1), and the
// TL072 output stage (x1.51) turns code 194 (3.29 V) into ~5 V at ENV OUT;
// full 0..255 would give ~6.5 V. Scale the 0..255 envelope to 0..ENV_DAC_MAX
// (../../../docs/research.md 6).
#define ENV_DAC_MAX 194

// ACID (as modules/acid): shared envelope timing. Each phase level is computed from the elapsed
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
        const uint8_t code = ((uint16_t)value * ENV_DAC_MAX + 127) / 255;
        DAC0.DATA = code;
        envDacPin(code != 0);
    }

    // At code 0 the DAC still outputs its zero-scale offset (tens of mV after
    // the x1.51 stage), enough to open a vactrol VCA with no dead zone
    // (modules/vca-mix). Silent = DAC output off and PA6 driven low as a GPIO,
    // a hard 0 V at ENV_CV; any other code hands the pin back to the DAC.
    static void envDacPin(bool dacOn) {
        if (dacOn) {
            PORTA.DIRCLR = PIN6_bm;
            DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
        } else {
            DAC0.CTRLA = DAC_ENABLE_bm;
            PORTA.OUTCLR = PIN6_bm;
            PORTA.DIRSET = PIN6_bm;
        }
    }

    // Last envelope value written to the DAC, 0..255 (0 = silent).
    uint8_t getLevel() const {
        return level;
    }

private:
    uint8_t level = 0;

};

#endif // ENVELOPEGENERATOR_H
