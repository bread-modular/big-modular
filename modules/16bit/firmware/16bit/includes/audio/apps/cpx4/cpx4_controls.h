#pragma once

// CPX4 control map (this module, not BM). Pico-free, shared with the host
// test tools/sim_cpx4.cpp.
//
//   16bit knobs          P1 TUNE 1   P2 TUNE 2   P3 TUNE 3   P4 TUNE 4
//   MCC-1 (Bank A)       CC20 SHARP A  CC21 SHARP B  CC22 MOD  CC23 DRIVE
//                        button CC102: FM routing PAIRS / LOOP / TOTAL FB
//   MCC-2 (Bank B)       CC27 DELAY TIME  CC28 FEEDBACK  CC29 DELAY MIX
//                        CC30 CUTOFF (inverted: 0 = open, 127 = 55 Hz);
//                        button CC103: RESONANCE Off / Peak / Sing
//   any MIDI note        PITCH: transposes all four voices (C4 = 0)
//   CC120 All Sound Off  clears the delay lines
//
// The MCCs run the cpx4 MCC firmware (modules/16bit/firmware/mcc/, bank
// fixed at build time). Their button CCs send 0 / 64 / 127 for steps 1 / 2 / 3
// and are not recorded (outside the recorder's twelve MCC slots).

#include <stdint.h>

#include "audio/apps/cpx4/cpx4_dsp.h"

namespace cpx4_controls {

constexpr uint8_t CC_SHARP_A = 20;
constexpr uint8_t CC_SHARP_B = 21;
constexpr uint8_t CC_MOD = 22;
constexpr uint8_t CC_DRIVE = 23;
constexpr uint8_t CC_DELAY_TIME = 27;
constexpr uint8_t CC_FEEDBACK = 28;
constexpr uint8_t CC_DELAY_MIX = 29;
constexpr uint8_t CC_CUTOFF = 30;
constexpr uint8_t CC_ROUTING = 102;    // MCC-1 button
constexpr uint8_t CC_RESONANCE = 103;  // MCC-2 button
constexpr uint8_t CC_ALL_SOUND_OFF = 120;

// The eight recorded MCC knobs, in recorder frame order (Bank A, Bank B).
constexpr uint8_t RECORDED_CCS[8] = {
    CC_SHARP_A, CC_SHARP_B, CC_MOD, CC_DRIVE,
    CC_DELAY_TIME, CC_FEEDBACK, CC_DELAY_MIX, CC_CUTOFF};

// Power-on values until the MCCs send theirs (they resend every second).
constexpr uint8_t SEED_CC[8] = {
    24,   // SHARP A: a little rounder than a triangle's corners
    24,   // SHARP B
    0,    // MOD: clean
    0,    // DRIVE: clean
    64,   // DELAY TIME: 31 ms
    40,   // FEEDBACK
    32,   // DELAY MIX
    0,    // CUTOFF: open (inverted)
};

// P1 / P2 arrive on ADC0 / ADC1: unpatched a knob gives 0..+5 V = ADC
// ~2020..3735 (polysynth / sampler); P3 / P4 use the whole 0..4095.
constexpr uint16_t TOP_KNOB_ADC_ZERO = 2020;
constexpr uint16_t TOP_KNOB_ADC_FULL = 3735;
constexpr uint16_t KNOB_ADC_END = 16;  // end dead band of P3 / P4

// Button CC value -> step 0..2 (0..42, 43..85, 86..127).
inline int buttonStep(uint8_t value) {
    return (value & 0x7F) * 3 / 128;
}

// Knob 0..3 (P1..P4) raw ADC -> knob position 0..1 (Cpx4Dsp::setTune: the
// bottom few percent mute the voice, the rest is its pitch).
inline float knobToTune(int knob, float adc) {
    float v;
    if (knob < 2) {
        v = (adc - TOP_KNOB_ADC_ZERO) / (float)(TOP_KNOB_ADC_FULL - TOP_KNOB_ADC_ZERO);
    } else {
        v = (adc - KNOB_ADC_END) / (float)(4095 - 2 * KNOB_ADC_END);
    }
    return v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v);
}

// Apply one CC. Returns true if it is a CPX4 control.
inline bool apply(Cpx4Dsp& dsp, uint8_t cc, uint8_t value) {
    const float v = (value & 0x7F) / 127.0f;
    switch (cc) {
        case CC_SHARP_A: dsp.setSharp(0, v); return true;
        case CC_SHARP_B: dsp.setSharp(1, v); return true;
        case CC_MOD: dsp.setMod(v); return true;
        case CC_DRIVE: dsp.setDrive(v); return true;
        case CC_DELAY_TIME: dsp.setDelayTime(v); return true;
        case CC_FEEDBACK: dsp.setFeedback(v); return true;
        case CC_DELAY_MIX: dsp.setDelayMix(v); return true;
        case CC_CUTOFF: dsp.setCutoff(1.0f - v); return true;  // knob at 0 = no filtering
        case CC_ROUTING: dsp.setRouting(buttonStep(value)); return true;
        case CC_RESONANCE: dsp.setResonanceStep(buttonStep(value)); return true;
        case CC_ALL_SOUND_OFF: dsp.panic(); return true;
        default: return false;
    }
}

}  // namespace cpx4_controls
