#pragma once

// Polysynth ladder filter (this module, not BM): replaces BM's FilterFX +
// Ladder.h for the polysynth. Pico-free, shared with the host test
// tools/sim_poly_filter.cpp.
//
// BM's ladder lost level as the cutoff came down: its feedback grows up to 4x
// toward low cutoffs and the passband of a ladder falls as 1 / (1 + feedback),
// so the power-on resonance cost ~6 dB as soon as the cutoff moved (and its
// Euler stages sat about an octave below the set cutoff; the top 60 % of the
// resonance CC was clamped). After Vital's ladder (mtytel/vital
// src/synthesis/filters/ladder_filter.cpp, GPLv3, ideas only, no code):
//   - four zero-delay-feedback (TPT) one-pole stages with the loop solved
//     exactly, so the cutoff is where it is set and the resonance does not
//     depend on it; tanh on the stage input (Vital: the input drive) keeps
//     the loop bounded at full resonance;
//   - resonance makeup: Vital lifts the input by 1 + resonance %; here the
//     output is lifted by the whole 1 + k, so the passband stays at 0 dB at
//     every resonance and the level only falls once the cutoff reaches the
//     notes;
//   - cutoff and envelope depth in octaves (Vital: MIDI-note cutoff), smoothed.
//
// MCC Bank A (CC20..23); Banks B (CC27..30) and C (CC85..88) are folded onto
// the same four parameters (bankAParameter):
//   0 CC20 envelope attack = release, 5 ms .. 2 s (exponential)
//   1 CC21 envelope depth, 0 .. +CUTOFF_OCTAVES octaves over the cutoff
//   2 CC22 resonance k = 0 .. RESONANCE_MAX (self-oscillates from ~CC 124)
//   3 CC23 cutoff, inverted as in BM: CC 0 = CUTOFF_MAX_HZ (open) ..
//          CC 127 = CUTOFF_MIN_HZ, exponential
// The envelope is BM's: one attack / release follower for all voices, up
// while any note is held.

#include <math.h>
#include <stdint.h>

class PolyFilter {
    public:
        static constexpr float CUTOFF_MIN_HZ = 55.0f;
        static constexpr float CUTOFF_MAX_HZ = 17600.0f;
        static constexpr float CUTOFF_OCTAVES = 8.32193f;  // log2(MAX / MIN)
        static constexpr float RESONANCE_MAX = 4.1f;       // Vital kMaxResonance
        static constexpr float ENV_TIME_MIN_S = 0.005f;
        static constexpr float ENV_TIME_RATIO = 400.0f;    // 5 ms .. 2 s
        static constexpr float SMOOTH_MS = 5.0f;           // cutoff / resonance glide
        static constexpr uint8_t BANK_A_FIRST_CC = 20;
        static constexpr uint8_t BANK_B_FIRST_CC = 27;
        static constexpr uint8_t BANK_C_FIRST_CC = 85;
        static constexpr uint8_t PARAMETER_COUNT = 4;

    private:
        float sampleRate = 44100.0f;
        float maxW = 1.25f;          // pi * fc / fs ceiling (0.4 fs)
        float piOverFs = 0.0f;
        float smoothRate = 0.0f;

        // Targets (set from the main loop) and their smoothed values.
        float cutoffOct = CUTOFF_OCTAVES;  // octaves over CUTOFF_MIN_HZ
        float depthOct = CUTOFF_OCTAVES;
        float k = 0.0f;
        float cutoffOctNow = CUTOFF_OCTAVES;
        float depthOctNow = CUTOFF_OCTAVES;
        float kNow = 0.0f;

        float envelope = 0.0f;
        float envTarget = 0.0f;
        float envAttack = 0.0f;
        float envRelease = 0.0f;
        float envTime = 0.01f;

        float s[4] = {0.0f, 0.0f, 0.0f, 0.0f};  // TPT stage states

        void updateEnvRates() {
            envAttack = 1.0f - expf(-1.0f / (envTime * sampleRate));
            envRelease = envAttack;
        }

    public:
        // 2^x for 0 <= x < 128, within 0.02 % (0.3 cents).
        static inline float fastExp2(float x) {
            int i = (int)x;
            float f = x - (float)i;
            float p = 1.0f + f * (0.6960656f + f * (0.224494f + f * 0.0794402f));
            union { float f; int32_t i; } u = {p};
            u.i += i << 23;
            return u.f;
        }

        // tan(w) for 0 <= w <= 1.26 (continued fraction to x^2 / 7),
        // within 0.06 % at the top.
        static inline float fastTan(float w) {
            float w2 = w * w;
            return w * (105.0f - 10.0f * w2) / (105.0f + w2 * (w2 - 45.0f));
        }

        // BM Ladder.h fast_tanh.
        static inline float fastTanh(float x) {
            if (x < -3.0f) return -1.0f;
            if (x > 3.0f) return 1.0f;
            float x2 = x * x;
            return x * (27.0f + x2) / (27.0f + 9.0f * x2);
        }

        // MCC CC -> parameter 0..3; Banks B and C fold onto Bank A. -1 for
        // any other CC.
        static int bankAParameter(uint8_t cc) {
            const uint8_t first[3] = {BANK_A_FIRST_CC, BANK_B_FIRST_CC, BANK_C_FIRST_CC};
            for (uint8_t bank = 0; bank < 3; bank++) {
                if (cc >= first[bank] && cc < first[bank] + PARAMETER_COUNT) {
                    return cc - first[bank];
                }
            }
            return -1;
        }

        static float envTimeSeconds(float value) {
            return ENV_TIME_MIN_S * powf(ENV_TIME_RATIO, value);
        }

        static float cutoffHz(float value) {
            return CUTOFF_MAX_HZ * powf(2.0f, -value * CUTOFF_OCTAVES);
        }

        void init(float sr) {
            sampleRate = sr;
            piOverFs = 3.14159265f / sampleRate;
            maxW = fminf(0.4f * 3.14159265f, piOverFs * CUTOFF_MAX_HZ);
            smoothRate = 1.0f - expf(-1000.0f / (SMOOTH_MS * sampleRate));
            updateEnvRates();
            cutoffOctNow = cutoffOct;
            depthOctNow = depthOct;
            kNow = k;
            reset();
        }

        void reset() {
            for (int i = 0; i < 4; i++) {
                s[i] = 0.0f;
            }
            envelope = 0.0f;
        }

        void setGate(bool gate) {
            envTarget = gate ? 1.0f : 0.0f;
        }

        // value 0..1 (CC / 127).
        void setParameter(uint8_t parameter, float value) {
            value = fminf(fmaxf(value, 0.0f), 1.0f);
            switch (parameter) {
                case 0:
                    envTime = envTimeSeconds(value);
                    updateEnvRates();
                    break;
                case 1:
                    depthOct = value * CUTOFF_OCTAVES;
                    break;
                case 2:
                    k = value * RESONANCE_MAX;
                    break;
                case 3:
                    cutoffOct = (1.0f - value) * CUTOFF_OCTAVES;
                    break;
            }
        }

        float getEnvTime() const { return envTime; }
        float getResonance() const { return k; }

        // Cutoff of this sample (Hz), after the envelope.
        float currentCutoffHz() const {
            float oct = fminf(cutoffOctNow + envelope * depthOctNow, CUTOFF_OCTAVES);
            return CUTOFF_MIN_HZ * fastExp2(oct);
        }

        float process(float input) {
            envelope += (envTarget - envelope) * (envTarget > envelope ? envAttack : envRelease);
            cutoffOctNow += smoothRate * (cutoffOct - cutoffOctNow);
            depthOctNow += smoothRate * (depthOct - depthOctNow);
            kNow += smoothRate * (k - kNow);

            float w = fminf(piOverFs * currentCutoffHz(), maxW);
            float g = fastTan(w);
            float G = g / (1.0f + g);
            float hold = 1.0f - G;  // 1 / (1 + g)

            // Loop solved for the stage input u: y4 = G^4 u + S.
            float S = (((s[0] * G + s[1]) * G + s[2]) * G + s[3]) * hold;
            float G2 = G * G;
            float u = fastTanh((input - kNow * S) / (1.0f + kNow * G2 * G2));

            float y = u;
            for (int i = 0; i < 4; i++) {
                float v = (y - s[i]) * G;
                y = v + s[i];
                s[i] = y + v;
                // Flush denormals as the tail dies out.
                if (fabsf(s[i]) < 1e-15f) {
                    s[i] = 0.0f;
                }
            }
            return y * (1.0f + kNow);
        }
};
