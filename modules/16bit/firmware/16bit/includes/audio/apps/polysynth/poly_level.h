#pragma once

// Polysynth output level (this module, not BM), after the 32bit polysynth
// (modules/32bit/firmware/polysynth/main/src/ps_dsp.c). Pico-free, shared with
// the host test tools/sim_poly_level.cpp.
//
// BM divides the voice sum by 4: one voice peaks at -12 dBFS and four or more
// in-phase voices hard-clip at the DAC. Here one full-velocity voice peaks at
// VOICE_GAIN. The polyphony gain follows the summed voice level
// L = sum(envelope x velocity), instantly up and over POLY_RELEASE_MS down (so
// releasing notes don't pump the others), and sets the mix gain to
// VOICE_GAIN / max(1, L)^POLY_EXP. A look-ahead peak limiter, linked over both
// outputs, catches what is left (resonant peaks, phase-aligned chords) under
// LIMIT, ahead of a soft clip.

#include <math.h>
#include <stdint.h>

class PolyLevel {
    public:
        static constexpr float VOICE_GAIN = 0.8f;
        static constexpr float POLY_EXP = 0.8f;
        static constexpr float POLY_RELEASE_MS = 300.0f;
        static constexpr float LIMIT = 0.9f;
        static constexpr int LIMIT_LOOKAHEAD = 32;  // samples (0.7 ms latency)
        static constexpr float LIMIT_HOLD_MS = 60.0f;
        static constexpr float LIMIT_RELEASE_MS = 250.0f;
        static constexpr uint32_t CONTROL_BLOCK = 16;
        // The ladder keeps BM's input level (one voice peaks at 0.25), so its
        // tanh stages saturate as in BM; the FX output is scaled back up.
        static constexpr float LADDER_DRIVE = 0.25f / VOICE_GAIN;

    private:
        float polyRelease = 0.0f;
        float polyLevel = 0.0f;
        float polyGain = VOICE_GAIN;
        uint32_t control = 0;

        float limitRelease = 0.0f;
        float limitAttack = 0.0f;
        uint32_t limitHoldSamples = 0;
        uint32_t limitHold = 0;
        float limitEnv = LIMIT;
        float limitGain = 1.0f;
        float delayLeft[LIMIT_LOOKAHEAD] = {};
        float delayRight[LIMIT_LOOKAHEAD] = {};
        int limitPos = 0;

        // BM Ladder.h fast_tanh.
        static inline float fastTanh(float x) {
            if (x < -3.0f) return -1.0f;
            if (x > 3.0f) return 1.0f;
            float x2 = x * x;
            return x * (27.0f + x2) / (27.0f + 9.0f * x2);
        }

    public:
        void init(float sampleRate) {
            polyRelease = 1.0f - expf(-1000.0f / (POLY_RELEASE_MS * sampleRate));
            limitRelease = 1.0f - expf(-1000.0f / (LIMIT_RELEASE_MS * sampleRate));
            // Time constant a quarter of the look-ahead: 98 % settled when
            // the peak leaves the delay.
            limitAttack = 1.0f - expf(-4.0f / LIMIT_LOOKAHEAD);
            limitHoldSamples = (uint32_t)(LIMIT_HOLD_MS * sampleRate / 1000.0f);
            polyLevel = 0.0f;
            polyGain = VOICE_GAIN;
            control = 0;
            limitHold = 0;
            limitEnv = LIMIT;
            limitGain = 1.0f;
            limitPos = 0;
            for (int i = 0; i < LIMIT_LOOKAHEAD; i++) {
                delayLeft[i] = 0.0f;
                delayRight[i] = 0.0f;
            }
        }

        // Summed voice level of this sample -> gain for the raw voice sum.
        float gain(float level) {
            if (level > polyLevel) {
                polyLevel = level;
            } else {
                polyLevel += polyRelease * (level - polyLevel);
            }
            if (control++ % CONTROL_BLOCK == 0) {
                polyGain = VOICE_GAIN / powf(fmaxf(1.0f, polyLevel), POLY_EXP);
            }
            return polyGain;
        }

        // Linear up to LIMIT, then a tanh knee into +-1.
        static inline float softClip(float x) {
            float a = fabsf(x);
            if (a <= LIMIT) return x;
            float knee = 1.0f - LIMIT;
            float y = LIMIT + knee * fastTanh((a - LIMIT) / knee);
            return x < 0.0f ? -y : y;
        }

        // Look-ahead limiter, one gain for both outputs: the held peak jumps
        // to a new peak, holds, then decays (never below LIMIT, so the gain
        // is 1 until the output would pass it); the gain glides to
        // LIMIT / peak while the samples wait in the delay.
        void limit(float& left, float& right) {
            float a = fmaxf(fabsf(left), fabsf(right));
            if (a >= limitEnv) {
                limitEnv = a;
                limitHold = limitHoldSamples;
            } else if (limitHold > 0) {
                limitHold--;
            } else {
                limitEnv += limitRelease * (fmaxf(a, LIMIT) - limitEnv);
            }
            limitGain += limitAttack * (LIMIT / limitEnv - limitGain);

            float delayedLeft = delayLeft[limitPos];
            float delayedRight = delayRight[limitPos];
            delayLeft[limitPos] = left;
            delayRight[limitPos] = right;
            limitPos = (limitPos + 1) % LIMIT_LOOKAHEAD;
            left = softClip(delayedLeft * limitGain);
            right = softClip(delayedRight * limitGain);
        }

        float getPolyGain() const {
            return polyGain;
        }
};
