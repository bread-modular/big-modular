#pragma once

// Sampler P1 / P2 DSP (this module, not BM). Pico-free, shared with the host
// test tools/sim_sampler.cpp.
//
// P1 = KickDrive on group A (notes 0-5, the kick and its neighbours), ahead of
// the P3 lowpass, so P3 also tames the fizz:
//   - pre-gain 0 .. +DRIVE_DB_MAX dB (linear in dB over the knob) into an
//     asymmetric soft clip, fastTanh(g x + b) - fastTanh(b): the body of the
//     kick flattens toward a square and its tail comes up (the techno
//     "clipped kick"); the bias b adds even harmonics (warm) in the middle of
//     the knob, BIAS_MAX at half way, and fades out toward the top, where the
//     clip is symmetric and hard; it is DC-blocked at DC_HZ;
//   - makeup so a full-scale input swings +-CEILING, so the knob trades
//     dynamics for density and loudness instead of just level;
//   - the wet path fades in over the first FADE_IN of the knob; fully down
//     (under DEAD_ZONE) the drive is bypassed exactly (BM / earlier builds).
// P2 = resonance of the group A end-of-chain highpass (P4 cutoff), a DJ
// filter (DjHighpass):
//   - fully down (under DEAD_ZONE) the earlier Biquad highpass (12 dB/oct,
//     Q 0.707) plays alone, bit for bit;
//   - turned up, it crossfades (over the first FADE_IN of the knob) to a
//     24 dB/oct highpass: a Butterworth stage, then a resonant TPT SVF stage
//     whose Q rises fast, Q_BASE .. Q_MAX on an exponential of sqrt(knob):
//     the peak at the cutoff (Q x Q_BUTTER1, the first stage's gain there)
//     is +11.5 dB at a quarter, +17.5 dB half way and +26 dB at the top;
//   - the resonance only lives in the high mids and highs, as on a Pioneer
//     DJM filter: under RES_START_HZ the second stage stays a flat
//     Butterworth (no peak, so the kick, the bass and the low mids stay
//     clean, no mud), from there the peak (in dB) fades in over log f and is
//     full from RES_FULL_HZ to the top of the P4 sweep; the P4 knob curve
//     puts RES_FULL_HZ at its 25 % mark (SamplerDsp::p4Cutoff), so most of
//     the knob zings;
//   - the resonant stage saturates: past KNEE its damping grows with the
//     square of the bandpass overshoot, so a loud tone on the cutoff
//     squelches at a bounded level instead of ringing up to ~30x, and the
//     click or a quiet hit rings clean; the passband stays at 0 dB;
//   - OutputGuard, a peak limiter with an instant attack after the highpass,
//     holds the kick + ring under GUARD_LIMIT.
// While P1 is up, group A then ends in outputClip, a soft knee from
// CLIP_KNEE to GUARD_LIMIT: the driven kick's square body overshoots ~2x
// through the P4 highpass (already at its 20 Hz minimum), and clipping those
// edges keeps the drive's loudness where a limiter would turn it back down.
// With both knobs fully down the guard (once its gain has recovered), the DJ
// stages (once faded out) and the clip are out of the path, so the output is
// the earlier one bit for bit.

#include <math.h>
#include <stdint.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace SamplerDsp {

    static constexpr float DEAD_ZONE = 0.02f;

    // P4 highpass cutoff, 20 Hz .. 20 kHz in two exponential segments: the
    // first P4_KNEE of the knob climbs to P4_KNEE_HZ (DjHighpass::
    // RES_FULL_HZ), so full P2 resonance arrives at the 25 % mark, and the
    // rest sweeps the resonant high mids and highs (user, 2026-11-08).
    static constexpr float P4_MIN_HZ = 20.0f;
    static constexpr float P4_MAX_HZ = 20000.0f;
    static constexpr float P4_KNEE = 0.25f;
    static constexpr float P4_KNEE_HZ = 1200.0f;
    static inline float p4Cutoff(float norm) {
        if (norm <= P4_KNEE) {
            return P4_MIN_HZ * powf(P4_KNEE_HZ / P4_MIN_HZ, norm / P4_KNEE);
        }
        return P4_KNEE_HZ * powf(P4_MAX_HZ / P4_KNEE_HZ, (norm - P4_KNEE) / (1.0f - P4_KNEE));
    }

    // Knob 0..1 with the bottom DEAD_ZONE folded to 0, then rescaled to 0..1.
    static inline float knobAmount(float norm) {
        if (norm <= DEAD_ZONE) {
            return 0.0f;
        }
        float amount = (norm - DEAD_ZONE) / (1.0f - DEAD_ZONE);
        return amount > 1.0f ? 1.0f : amount;
    }

    // BM Ladder.h fast_tanh (as poly_level.h): C1-continuous at +-3.
    static inline float fastTanh(float x) {
        if (x < -3.0f) return -1.0f;
        if (x > 3.0f) return 1.0f;
        float x2 = x * x;
        return x * (27.0f + x2) / (27.0f + 9.0f * x2);
    }

    static constexpr float GUARD_LIMIT = 0.95f;
    static constexpr float CLIP_KNEE = 0.7f;

    // Unity up to CLIP_KNEE, then a tanh knee (slope 1 at the knee) that
    // never reaches GUARD_LIMIT.
    static inline float outputClip(float x) {
        float a = fabsf(x);
        if (a <= CLIP_KNEE) {
            return x;
        }
        const float span = GUARD_LIMIT - CLIP_KNEE;
        float y = CLIP_KNEE + span * fastTanh((a - CLIP_KNEE) / span);
        return x < 0.0f ? -y : y;
    }
}

class KickDrive {
    public:
        static constexpr float DRIVE_DB_MAX = 36.0f;
        static constexpr float BIAS_MAX = 0.2f;
        static constexpr float FADE_IN = 0.15f;
        static constexpr float CEILING = 0.9f;
        static constexpr float SMOOTH_MS = 10.0f;
        static constexpr float DC_HZ = 5.0f;

    private:
        float smoothRate = 0.0f;
        float dcPole = 0.0f;

        // Targets (set from the main loop) and their smoothed values.
        float gainT = 1.0f, biasT = 0.0f, offsetT = 0.0f, makeupT = 1.0f, wetT = 0.0f;
        float gain = 1.0f, bias = 0.0f, offset = 0.0f, makeup = 1.0f, wet = 0.0f;
        float dcX = 0.0f, dcY = 0.0f;

        static float shape(float x, float b, float off) {
            return SamplerDsp::fastTanh(x + b) - off;
        }

    public:
        void init(float sampleRate) {
            smoothRate = 1.0f - expf(-1000.0f / (SMOOTH_MS * sampleRate));
            dcPole = 1.0f - 2.0f * (float)M_PI * DC_HZ / sampleRate;
            gain = gainT;
            bias = biasT;
            offset = offsetT;
            makeup = makeupT;
            wet = wetT;
            dcX = dcY = 0.0f;
        }

        // P1 knob 0..1 (main loop). Returns whether the drive is on.
        bool setDrive(float norm) {
            float amount = SamplerDsp::knobAmount(norm);
            float g = powf(10.0f, DRIVE_DB_MAX * amount / 20.0f);
            float b = BIAS_MAX * 4.0f * amount * (1.0f - amount);
            float off = SamplerDsp::fastTanh(b);
            // Mean of the two sides: the DC blocker centres the swing.
            float swing = 0.5f * (shape(g, b, off) - shape(-g, b, off));
            gainT = g;
            biasT = b;
            offsetT = off;
            makeupT = CEILING / swing;
            wetT = fminf(1.0f, amount / FADE_IN);
            return amount > 0.0f;
        }

        __attribute__((always_inline)) inline float process(float x) {
            if (wetT == 0.0f && wet < 1.0e-5f) {
                // Fully down: exact bypass, the DC blocker restarts clean.
                wet = 0.0f;
                dcX = dcY = 0.0f;
                return x;
            }
            gain += (gainT - gain) * smoothRate;
            bias += (biasT - bias) * smoothRate;
            offset += (offsetT - offset) * smoothRate;
            makeup += (makeupT - makeup) * smoothRate;
            wet += (wetT - wet) * smoothRate;

            float driven = shape(gain * x, bias, offset) * makeup;
            // One-pole DC blocker for the asymmetric clip.
            float blocked = driven - dcX + dcPole * dcY;
            dcX = driven;
            dcY = blocked;
            return x + (blocked - x) * wet;
        }
};

// P2 DJ highpass (see the top of this file). process() takes the earlier
// Biquad highpass output too and returns it exactly while P2 is fully down.
class DjHighpass {
    public:
        static constexpr float Q_BUTTER1 = 0.5412f; // 4th-order Butterworth stages
        static constexpr float Q_BASE = 1.3066f;
        static constexpr float Q_MAX = 37.0f;       // x Q_BUTTER1: +26 dB at the cutoff
        static constexpr float RES_START_HZ = 500.0f; // no peak below
        static constexpr float RES_FULL_HZ = SamplerDsp::P4_KNEE_HZ;  // full peak above (P4 25 %)
        static constexpr float KNEE = 1.5f;        // bandpass level the squelch starts at
        static constexpr float SATURATION = 0.3f;  // damping per (|bandpass| - KNEE)^2
        static constexpr float FADE_IN = 0.05f;
        static constexpr float SMOOTH_MS = 5.0f;
        static constexpr float MAX_HZ_RATIO = 0.45f; // of the sample rate

    private:
        float sampleRate = 48000.0f;
        float smoothRate = 0.0f;
        float cutoff = 20.0f;
        float amount = 0.0f;

        // Targets (set from the main loop) and their smoothed values.
        float gT = 0.0f, kT = 1.0f / Q_BASE, wetT = 0.0f;
        float g = 0.0f, k = 1.0f / Q_BASE, wet = 0.0f;
        // TPT SVF integrator states (Cytomic ic1eq / ic2eq), two stages.
        float s1a = 0.0f, s2a = 0.0f, s1b = 0.0f, s2b = 0.0f;
        float bandB = 0.0f;

        void updateTargets() {
            float fc = fminf(fmaxf(cutoff, 10.0f), MAX_HZ_RATIO * sampleRate);
            gT = tanf((float)M_PI * fc / sampleRate);
            // Peak in dB = log Q: knob curve x high-mid focus.
            float lift = sqrtf(amount) * focus(fc);
            kT = 1.0f / (Q_BASE * powf(Q_MAX / Q_BASE, lift));
            wetT = fminf(1.0f, amount / FADE_IN);
        }

    public:
        // 0 under RES_START_HZ, 1 over RES_FULL_HZ, smoothstep over log f.
        static float focus(float hz) {
            float t = logf(hz / RES_START_HZ) / logf(RES_FULL_HZ / RES_START_HZ);
            t = fminf(fmaxf(t, 0.0f), 1.0f);
            return t * t * (3.0f - 2.0f * t);
        }

        void init(float sampleRate_) {
            sampleRate = sampleRate_;
            smoothRate = 1.0f - expf(-1000.0f / (SMOOTH_MS * sampleRate));
            updateTargets();
            g = gT;
            k = kT;
            wet = wetT;
            s1a = s2a = s1b = s2b = bandB = 0.0f;
        }

        // P4 cutoff in Hz (main loop).
        void setCutoff(float hz) {
            cutoff = hz;
            updateTargets();
        }

        // P2 knob 0..1 (main loop). Returns whether the resonance is on.
        bool setResonance(float norm) {
            amount = SamplerDsp::knobAmount(norm);
            updateTargets();
            return amount > 0.0f;
        }

        // Small-signal Q at the current cutoff (tests).
        float getQ() const {
            return 1.0f / kT;
        }

        // x = highpass input, flat = the earlier Biquad highpass of x.
        __attribute__((always_inline)) inline float process(float x, float flat) {
            if (wetT == 0.0f && wet < 1.0e-5f) {
                // Fully down: the earlier highpass, the DJ stages restart clean.
                wet = 0.0f;
                s1a = s2a = s1b = s2b = bandB = 0.0f;
                g = gT;
                k = kT;
                return flat;
            }
            g += (gT - g) * smoothRate;
            k += (kT - k) * smoothRate;
            wet += (wetT - wet) * smoothRate;

            // Stage 1: Butterworth highpass, linear.
            const float k1 = 1.0f / Q_BUTTER1;
            float a1 = 1.0f / (1.0f + g * (g + k1));
            float v1 = a1 * (s1a + g * (x - s2a));
            float v2 = s2a + g * v1;
            s1a = 2.0f * v1 - s1a;
            s2a = 2.0f * v2 - s2a;
            float hpA = x - k1 * v1 - v2;

            // Stage 2: resonant, damping k + SATURATION * band^2 (last
            // sample's bandpass), so the ring squelches instead of growing.
            float over = fmaxf(fabsf(bandB) - KNEE, 0.0f);
            float kEff = k + SATURATION * over * over;
            float b1 = 1.0f / (1.0f + g * (g + kEff));
            float w1 = b1 * (s1b + g * (hpA - s2b));
            float w2 = s2b + g * w1;
            s1b = 2.0f * w1 - s1b;
            s2b = 2.0f * w2 - s2b;
            bandB = w1;
            float y = hpA - kEff * w1 - w2;

            return flat + (y - flat) * wet;
        }
};

// Resonance peak guard: instant attack (the output never
// exceeds GUARD_LIMIT), hold, then exponential release back to unity.
class OutputGuard {
    public:
        static constexpr float GUARD_LIMIT = SamplerDsp::GUARD_LIMIT;
        static constexpr float HOLD_MS = 25.0f;     // > one period at 40 Hz
        static constexpr float RELEASE_MS = 60.0f;  // back to unity between beats

    private:
        float release = 0.0f;
        uint32_t holdSamples = 0;
        uint32_t hold = 0;
        // Gain reduction 1 - gain: decays to 0 without stalling at float
        // resolution just under 1.
        float reduction = 0.0f;

    public:
        void init(float sampleRate) {
            release = expf(-1000.0f / (RELEASE_MS * sampleRate));
            holdSamples = (uint32_t)(HOLD_MS * sampleRate / 1000.0f);
            hold = 0;
            reduction = 0.0f;
        }

        float getGain() const {
            return 1.0f - reduction;
        }

        // enabled = P2 up. Disabled, it only finishes its release.
        __attribute__((always_inline)) inline float process(float x, bool enabled) {
            if (!enabled && reduction == 0.0f) {
                return x;
            }
            if (hold > 0) {
                hold--;
            } else {
                reduction *= release;
                if (reduction < 1.0e-6f) {
                    reduction = 0.0f;
                }
            }
            float level = fabsf(x);
            if (enabled && level * (1.0f - reduction) > GUARD_LIMIT) {
                reduction = 1.0f - GUARD_LIMIT / level;
                hold = holdSamples;
            }
            return x * (1.0f - reduction);
        }
};
