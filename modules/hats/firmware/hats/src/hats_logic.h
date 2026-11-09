#ifndef HATS_LOGIC_H
#define HATS_LOGIC_H

// ============================================================================
// HATS S4 firmware logic with no hardware access, shared by main.cpp and the
// host tests (test/test_logic.cpp). Bread Modular NOISE + HIHAT behaviour
// (BM VERSION 0.1.0, ../../README.md), ported from the two ATtiny1616 loops
// to timer ticks on the STM32G071.
// ============================================================================

#include <stdint.h>
#include <math.h>

namespace hats {

// ---- NOISE (BM noise.ino) --------------------------------------------------

// The BM loop waits `timeToDelay` units between noise samples; one unit is a
// countdown pass (float compare + subtract + _delay_us(1) + MIDI poll) on the
// 20 MHz ATtiny, about 10 us by instruction count (not measured). The STM32
// noise timer runs at one tick per unit, and a BM sample pass (MIDI poll,
// LFSRs, DAC, analogRead) is about BASE_TICKS units.
static const uint32_t NOISE_TICK_HZ = 100000;  // 10 us per BM delay unit
static const uint32_t BASE_TICKS = 3;          // ~30 us BM sample pass

// TONE 0..1023 -> ticks between noise samples. BM: linear below half
// (tone / 2), exponential above (512 + 2^((tone - 512) / 30), integer
// division as in BM), so TONE 1023 holds each sample ~1.3 s.
inline uint32_t noiseHoldTicks(uint16_t tone) {
    if (tone > 1023) tone = 1023;
    uint32_t units;
    if (tone < 512) {
        units = tone / 2;
    } else {
        units = 512 + (1UL << ((tone - 512) / 30));
    }
    return BASE_TICKS + units;
}

// TONE = knob (or recorded take) + MIDI CC 74 x 8, as BM. HATS clamps the sum
// to 1023: BM let it reach 2039, which held one sample for hours.
inline uint16_t noiseTone(uint16_t knob, uint8_t cc74) {
    uint16_t t = knob + (uint16_t)cc74 * 8;
    return t > 1023 ? 1023 : t;
}

// HATS S3 addition (kept): push each sample towards the rail on its side of
// mid-scale as TONE rises, so the blue high-pass loses less level.
inline uint8_t boostSwing(uint8_t value, uint8_t mix) {
    int16_t s = (int16_t)value - 128;
    int16_t target = (s >= 0) ? 127 : -128;
    s += ((target - s) * mix) >> 8;
    return (uint8_t)(s + 128);
}

// BM: three 16-bit LFSRs (taps 0, 1, 2, 5), XOR-mixed.
struct WhiteNoise {
    uint16_t lfsr1 = 0xACE1;
    uint16_t lfsr2 = 0xBEEF;
    uint16_t lfsr3 = 0xCAFE;

    static uint8_t step(uint16_t &lfsr) {
        uint16_t bit = (lfsr & 1) ^ ((lfsr >> 1) & 1) ^ ((lfsr >> 2) & 1) ^ ((lfsr >> 5) & 1);
        lfsr = (lfsr >> 1) | (uint16_t)(bit << 15);
        return (uint8_t)(lfsr & 0xFF);
    }

    uint8_t next() {
        uint8_t a = step(lfsr1);
        uint8_t b = step(lfsr2);
        uint8_t c = step(lfsr3);
        return (uint8_t)((a ^ (b >> 1)) ^ (c >> 2));
    }
};

// BM 8-bit DAC value -> 12-bit DAC code, full scale on full scale. The BM
// ATtinys select the 4.34 V DAC reference at VDD = 3.3 V, which their author
// notes ends up as VDD; VREF+ here is +3V3, so the output levels match.
inline uint16_t dac12(uint8_t v) {
    return (uint16_t)(((uint16_t)v << 4) | (v >> 4));
}

// ---- CUTOFF vactrol (U11) --------------------------------------------------

// The knob replaces the S3 50k rheostat (R17 1k -> RV3 pin 1..wiper ->
// VMID_H). Same direction: knob up = more resistance = lower cutoff. U11's
// LDR with R50 across it must equal knob x 50k, so the LED is driven to
//   R_ldr = 1 / (1 / R_knob - 1 / R50).
// LDR model (not measured, generic VTL5C, re-fit on the bench):
//   R_ldr = LDR_R_ON x duty^-LDR_GAMMA, R_ON at 100 % (R51 330R, ~4 mA).
static const float CUT_POT_MAX = 50000.0f;
static const float CUT_R50 = 51000.0f;
static const float LDR_R_ON = 300.0f;
static const float LDR_GAMMA = 1.0f;

// PWM: 64 MHz / 2048 = 31.25 kHz on TIM3_CH3; the duty carries 5 extra
// fraction bits that the TIM3 update interrupt dithers in, since the top of
// the knob needs well under one 11-bit count.
static const uint16_t PWM_PERIOD = 2048;
static const uint8_t PWM_FRAC_BITS = 5;
static const uint32_t PWM_FULL = (uint32_t)PWM_PERIOD << PWM_FRAC_BITS;  // 65536

// Knob 0..1023 -> duty in PWM_FULL units.
inline uint32_t cutoffDuty(uint16_t knob) {
    if (knob > 1023) knob = 1023;
    float rKnob = CUT_POT_MAX * (float)knob / 1023.0f;
    if (rKnob <= LDR_R_ON) return PWM_FULL;
    float rLdr = 1.0f / (1.0f / rKnob - 1.0f / CUT_R50);
    float duty = powf(LDR_R_ON / rLdr, 1.0f / LDR_GAMMA);
    if (duty >= 1.0f) return PWM_FULL;
    return (uint32_t)(duty * (float)PWM_FULL + 0.5f);
}

// First-order sigma-delta: one PWM period's compare value from the
// fractional duty, carrying the remainder to the next period.
struct PwmDither {
    uint32_t acc = 0;

    uint16_t next(uint32_t duty) {
        if (duty >= PWM_FULL) return PWM_PERIOD;       // 100 %
        acc += duty & ((1u << PWM_FRAC_BITS) - 1);
        uint16_t ccr = (uint16_t)(duty >> PWM_FRAC_BITS);
        if (acc >= (1u << PWM_FRAC_BITS)) {
            acc -= 1u << PWM_FRAC_BITS;
            ccr++;
        }
        return ccr;
    }
};

// ---- MIDI ------------------------------------------------------------------

// Byte-stream MIDI parser: running status, real-time bytes anywhere (they do
// not break a message, unlike BM's SimpleMIDI), all channels as BM.
struct MidiParser {
    enum Kind : uint8_t { NONE = 0, NOTE_ON, NOTE_OFF, CONTROL_CHANGE, CLOCK, START, CONTINUE, STOP };

    struct Event {
        Kind kind;
        uint8_t data1;
        uint8_t data2;
    };

    uint8_t status = 0;
    uint8_t data[2] = {0, 0};
    uint8_t count = 0;

    static uint8_t dataLength(uint8_t st) {
        switch (st & 0xF0) {
            case 0xC0: case 0xD0: return 1;
            case 0xF0:
                if (st == 0xF1 || st == 0xF3) return 1;
                if (st == 0xF2) return 2;
                return 0;
            default: return 2;
        }
    }

    // Feed one byte; returns the completed event (kind NONE if none).
    Event feed(uint8_t b) {
        Event ev = {NONE, 0, 0};
        if (b >= 0xF8) {                              // real-time: no state change
            if (b == 0xF8) ev.kind = CLOCK;
            else if (b == 0xFA) ev.kind = START;
            else if (b == 0xFB) ev.kind = CONTINUE;
            else if (b == 0xFC) ev.kind = STOP;
            return ev;
        }
        if (b & 0x80) {
            // Channel messages set the running status; system common and
            // SysEx cancel it (their data is skipped).
            status = (b < 0xF0) ? b : 0;
            count = 0;
            return ev;
        }
        if (status == 0) return ev;
        data[count++] = b;
        if (count < dataLength(status)) return ev;
        count = 0;
        switch (status & 0xF0) {
            case 0x90: ev.kind = NOTE_ON; break;      // velocity 0 stays a note-on (BM)
            case 0x80: ev.kind = NOTE_OFF; break;
            case 0xB0: ev.kind = CONTROL_CHANGE; break;
            default: return ev;
        }
        ev.data1 = data[0];
        ev.data2 = data[1];
        return ev;
    }
};

// ---- HIHAT (BM hihat.ino) --------------------------------------------------

static const uint8_t MIDDLE_C_MIDI_NOTE = 60;

struct HihatOut {
    bool gate = false;
    bool open = false;
    uint8_t velocity = 255;  // BM boots at full velocity

    // Notes <= middle C are closed hat, above it open hat; the DAC gets
    // velocity x 2. Note-off drops the gate and also writes its velocity.
    void noteOn(uint8_t note, uint8_t vel) {
        gate = true;
        velocity = (uint8_t)(vel * 2);
        open = note > MIDDLE_C_MIDI_NOTE;
    }

    void noteOff(uint8_t vel) {
        gate = false;
        velocity = (uint8_t)(vel * 2);
    }
};

}  // namespace hats

#endif  // HATS_LOGIC_H
