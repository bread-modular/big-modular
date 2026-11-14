#pragma once

// LYRA4 drone voice (this module, not BM): four oscillators in two pairs with
// SHARP and cross-FM, two cross-fed delay lines, drive, a ladder low-pass and
// an output limiter. Our own design after the features of the SOMA Lyra-8
// (pairs, SHARP, MOD, FM routing, MOD DELAY, drive after the delay); none of
// its circuits. Pico-free, shared with the host test tools/sim_lyra4.cpp.
//
//   4 voices -> SHARP -> cross-FM -> mix (2x oversampled, half-band down)
//     -> delay (2 lines, cross-fed, loop: damping + DC block + knee clip)
//     -> DRIVE -> DC block -> ladder LPF (poly_filter.h) -> limiter
//     -> OUT 1 (dry + line 1) / OUT 2 (dry + line 2)
//   TOTAL FB (routing 2): the post-drive mix back into the FM.
//
// Every setter takes 0..1 (CC / 127, knob position) and is called from the
// main core; process() runs on the audio core and smooths the targets.

#include <math.h>
#include <stdint.h>
#include <string.h>

#include "audio/apps/polysynth/poly_filter.h"
#include "audio/apps/polysynth/poly_level.h"

class Lyra4Dsp {
    public:
        static constexpr int VOICES = 4;
        static constexpr int OVERSAMPLE = 2;

        // TUNE: as on Lyra, every voice covers the full range, A0..A7
        // (27.5..3520 Hz, seven octaves); what differs is the knob curve.
        // Each voice's curve is a loaded-pot (bilinear) taper
        //   c(t) = t / (t + k (1 - t)),  octaves = c(t) * TUNE_OCTAVES
        // that spends most of the travel in its own register and runs through
        // the rest quickly: voice 1 (k 3) dwells in the bass and only reaches
        // the treble near the end stop, voice 4 (k 1/3) the other way round.
        // Knob centre: voice 1 ~92 Hz, 2 ~191 Hz, 3 ~508 Hz, 4 ~1046 Hz.
        static constexpr float TUNE_OCTAVES = 7.0f;
        static constexpr float TUNE_MIN_HZ = 27.5f;
        static constexpr float TUNE_CURVE_K[VOICES] = {3.0f, 1.5f, 1.0f / 1.5f, 1.0f / 3.0f};
        static constexpr float MAX_HZ = 8000.0f;
        static constexpr float TUNE_SMOOTH_MS = 20.0f;

        // Knob at 0 = voice off. The bottom of the knob travel is a mute zone
        // with hysteresis (off below MUTE_OFF, on again above MUTE_ON); the
        // pitch range starts at MUTE_ON. On / off is a short linear fade, so
        // it never clicks; it also takes the voice out of the FM.
        static constexpr float MUTE_OFF = 0.03f;
        static constexpr float MUTE_ON = 0.05f;
        static constexpr float VOICE_FADE_MS = 15.0f;
        static constexpr int TRANSPOSE_ROOT = 60;       // MIDI C4 = no transpose

        // Slow random drift per voice (always on).
        static constexpr float DRIFT_CENTS = 4.0f;
        static constexpr float DRIFT_SECONDS = 1.5f;     // new target every ...
        static constexpr float DRIFT_SMOOTH_S = 1.0f;

        // SHARP: triangle -> tanh(g tri) / tanh(g) -> square, g exponential
        // over the knob (0.3 .. 40). g is capped so the edge stays two
        // oversampled samples wide (anti-alias).
        static constexpr float SHARP_G_MIN = 0.3f;
        static constexpr float SHARP_G_MAX = 40.0f;

        // MOD: linear through-zero FM, frequency deviation = depth x carrier.
        // depth = MOD_DEPTH_MAX x MOD^2: growl, then sidebands, chaos from
        // about MOD 0.7 (depth ~1).
        static constexpr float MOD_DEPTH_MAX = 2.0f;
        static constexpr float MOD_CROSS_SHARE = 0.5f;   // routing 1 / 2 share

        // FM routing (MCC-1 button).
        static constexpr int ROUTING_PAIRS = 0;     // 1 <-> 2, 3 <-> 4
        static constexpr int ROUTING_LOOP = 1;      // + pair A <-> pair B
        static constexpr int ROUTING_TOTAL_FB = 2;  // + the post-drive output
        static constexpr int ROUTING_COUNT = 3;

        // Delay: two lines, line 2 at a fixed ratio of line 1 so they beat.
        static constexpr float DELAY_MIN_S = 0.001f;
        static constexpr float DELAY_MAX_S = 1.0f;
        static constexpr float TIME2_RATIO = 0.97f;
        static constexpr float DELAY_SMOOTH_MS = 120.0f;  // tape-like glide
        static constexpr float DELAY_SEND = 0.7f;        // dry into the lines
        static constexpr float DELAY_CROSS = 0.3f;       // cross-feed share
        static constexpr float FEEDBACK_MAX = 1.1f;      // past 100 %
        static constexpr float DAMP_MAX_HZ = 12000.0f;   // feedback 0
        static constexpr float DAMP_MIN_HZ = 2500.0f;    // feedback full
        static constexpr float LOOP_KNEE = 0.6f;         // loop clip knee
        static constexpr float LOOP_DC_HZ = 20.0f;
        static constexpr float OUT_DC_HZ = 5.0f;         // after the drive bias

        // DRIVE: 0..+30 dB into tanh with a bias (even harmonics), makeup.
        // DRIVE_PRE keeps the stage linear at DRIVE 0 (0.25 x full scale
        // into the tanh: 2 % compression at the peak).
        static constexpr float DRIVE_GAIN_MAX = 31.6f;
        static constexpr float DRIVE_PRE = 0.25f;
        static constexpr float DRIVE_BIAS_MAX = 0.2f;
        static constexpr float DRIVE_MAKEUP_EXP = 0.5f;

        // RESONANCE button: Off / Peak / Sing (self-oscillation).
        static constexpr int RESONANCE_STEPS = 3;
        static constexpr float RESONANCE_K[RESONANCE_STEPS] = {0.0f, 3.0f, PolyFilter::RESONANCE_MAX};
        // Level into the ladder: 0.25 keeps its input tanh nearly linear
        // (Off / Peak). Sing is trimmed 6 dB, so its tone sits ~-6.5 dBFS
        // rms at every cutoff (the oscillation level is set inside the loop).
        static constexpr float FILTER_DRIVE = 0.25f;
        static constexpr float RESONANCE_TRIM[RESONANCE_STEPS] = {1.0f, 1.0f, 0.5f};

        static constexpr float OUTPUT_GAIN = 0.8f;
        static constexpr float SMOOTH_MS = 10.0f;        // CC parameter glide
        static constexpr int CONTROL_BLOCK = 16;

    private:
        // Half-band decimator (2x -> 1x), windowed sinc.
        static constexpr int HB_TAPS = 23;
        static constexpr int HB_CENTER = HB_TAPS / 2;
        static constexpr int HB_SIDE = (HB_CENTER + 1) / 2;  // odd-offset pairs

        float sampleRate = 44100.0f;
        float fs2 = 88200.0f;

        // --- voices
        float tuneTarget[VOICES] = {0.5f, 0.5f, 0.5f, 0.5f};
        float tuneNow[VOICES] = {0.5f, 0.5f, 0.5f, 0.5f};
        float ampTarget[VOICES] = {1.0f, 1.0f, 1.0f, 1.0f};  // voice on / off
        float amp[VOICES] = {1.0f, 1.0f, 1.0f, 1.0f};
        float ampStep = 0.0f;          // fade per oversampled step
        float transpose = 0.0f;        // semitones
        float phase[VOICES] = {0.0f, 0.25f, 0.5f, 0.75f};
        float y[VOICES] = {};          // last voice outputs
        float inc[VOICES] = {};        // phase increment per oversampled step
        float gain[VOICES] = {};       // SHARP gain
        float norm[VOICES] = {};       // 1 / tanh(gain)
        float drift[VOICES] = {};
        float driftTarget[VOICES] = {};
        uint32_t rng = 0x1234567u;
        uint32_t driftCounter = 0;
        uint32_t driftPeriod = 0;
        float driftRate = 0.0f;
        float tuneRate = 0.0f;
        float hb[HB_SIDE + 1] = {};    // hb[0] centre, hb[k] offset 2k - 1
        float hbHistory[2 * HB_TAPS] = {};
        int hbPos = 0;

        // --- controls: targets (main core) and smoothed values (audio core)
        float sharpTarget[2] = {};
        float sharpNow[2] = {};
        float modTarget = 0.0f;
        float modNow = 0.0f;
        int routing = ROUTING_PAIRS;
        float driveTarget = 0.0f;
        float driveNow = 0.0f;
        float delayTimeTarget = 0.5f;
        float feedbackTarget = 0.0f;
        float feedbackNow = 0.0f;
        float mixTarget = 0.0f;
        float mixNow = 0.0f;
        float smoothRate = 0.0f;
        int resonanceStep = 0;

        // --- delay
        int16_t* line[2] = {nullptr, nullptr};
        int lineSize = 0;
        int writePos = 0;
        float delaySamplesTarget[2] = {};
        float delaySamples[2] = {};
        float delaySmooth = 0.0f;
        float dampCoeff = 1.0f;
        float damp[2] = {};
        float loopDcCoeff = 0.0f;
        float outDcCoeff = 0.0f;
        float loopDcX[2] = {};
        float loopDcY[2] = {};
        volatile int flushSamples = 0;

        // --- drive / output
        float driveGain = 1.0f;
        float driveBias = 0.0f;
        float driveBiasOut = 0.0f;
        float driveMakeup = 1.0f;
        float outDcX[2] = {};
        float outDcY[2] = {};
        float totalFb = 0.0f;
        float mixDry = 1.0f;
        float mixWet = 0.0f;
        float trimNow = 1.0f;
        PolyFilter filter[2];
        PolyLevel level;

        int control = 0;

        static inline float fastTanh(float x) {
            return PolyFilter::fastTanh(x);
        }

        // Linear up to the knee, then a tanh knee into +-1.
        static inline float kneeClip(float x) {
            float a = fabsf(x);
            if (a <= LOOP_KNEE) return x;
            float k = 1.0f - LOOP_KNEE;
            float v = LOOP_KNEE + k * fastTanh((a - LOOP_KNEE) / k);
            return x < 0.0f ? -v : v;
        }

        float random() {  // -1..1
            rng = rng * 1664525u + 1013904223u;
            return (float)(int32_t)rng / 2147483648.0f;
        }

        float voiceHz(int v) const {
            float oct = tuneOctaves(v, tuneNow[v]) + transpose / 12.0f + drift[v] / 1200.0f;
            float hz = TUNE_MIN_HZ * powf(2.0f, oct);
            return fminf(hz, MAX_HZ);
        }

        // Once per CONTROL_BLOCK samples: smooth the targets, recompute the
        // oscillator, SHARP, delay and drive coefficients.
        void controlUpdate() {
            const float blockSmooth = 1.0f - powf(1.0f - smoothRate, (float)CONTROL_BLOCK);
            const float blockTune = 1.0f - powf(1.0f - tuneRate, (float)CONTROL_BLOCK);
            for (int p = 0; p < 2; p++) {
                sharpNow[p] += blockSmooth * (sharpTarget[p] - sharpNow[p]);
            }
            modNow += blockSmooth * (modTarget - modNow);
            driveNow += blockSmooth * (driveTarget - driveNow);
            feedbackNow += blockSmooth * (feedbackTarget - feedbackNow);
            mixNow += blockSmooth * (mixTarget - mixNow);
            trimNow += blockSmooth * (RESONANCE_TRIM[resonanceStep] - trimNow);

            driftCounter += CONTROL_BLOCK;
            if (driftCounter >= driftPeriod) {
                driftCounter = 0;
                for (int v = 0; v < VOICES; v++) {
                    driftTarget[v] = DRIFT_CENTS * random();
                }
            }
            const float blockDrift = 1.0f - powf(1.0f - driftRate, (float)CONTROL_BLOCK);
            for (int v = 0; v < VOICES; v++) {
                tuneNow[v] += blockTune * (tuneTarget[v] - tuneNow[v]);
                drift[v] += blockDrift * (driftTarget[v] - drift[v]);
                float hz = voiceHz(v);
                inc[v] = hz / fs2;
                float s = sharpNow[v / 2];
                float g = SHARP_G_MIN * powf(SHARP_G_MAX / SHARP_G_MIN, s);
                g = fminf(g, fmaxf(SHARP_G_MIN, fs2 / (4.0f * hz)));
                gain[v] = g;
                norm[v] = 1.0f / tanhf(g);
            }

            float t1 = DELAY_MIN_S * powf(DELAY_MAX_S / DELAY_MIN_S, delayTimeTarget);
            float maxDelay = (float)(lineSize - 2);
            delaySamplesTarget[0] = fminf(t1 * sampleRate, maxDelay);
            delaySamplesTarget[1] = fminf(t1 * TIME2_RATIO * sampleRate, maxDelay);

            float fbv = feedbackNow;
            float dampHz = DAMP_MAX_HZ * powf(DAMP_MIN_HZ / DAMP_MAX_HZ, fbv);
            dampCoeff = 1.0f - expf(-2.0f * 3.14159265f * dampHz / sampleRate);

            float d = driveNow;
            driveGain = 1.0f + (DRIVE_GAIN_MAX - 1.0f) * d * d;
            driveBias = DRIVE_BIAS_MAX * d;
            driveBiasOut = fastTanh(driveBias);
            driveMakeup = 1.0f / (DRIVE_PRE * powf(driveGain, DRIVE_MAKEUP_EXP));

            mixDry = cosf(mixNow * 1.5707963f);
            mixWet = sinf(mixNow * 1.5707963f) / DELAY_SEND;
        }

        // One oversampled oscillator step; returns the voice mix.
        inline float oscStep(float fm, float depth) {
            float m[VOICES];
            if (routing == ROUTING_PAIRS) {
                m[0] = y[1]; m[1] = y[0]; m[2] = y[3]; m[3] = y[2];
            } else if (routing == ROUTING_LOOP) {
                float a = 0.5f * (y[0] + y[1]);
                float b = 0.5f * (y[2] + y[3]);
                m[0] = MOD_CROSS_SHARE * (y[1] + b);
                m[1] = MOD_CROSS_SHARE * (y[0] + b);
                m[2] = MOD_CROSS_SHARE * (y[3] + a);
                m[3] = MOD_CROSS_SHARE * (y[2] + a);
            } else {
                m[0] = MOD_CROSS_SHARE * (y[1] + fm);
                m[1] = MOD_CROSS_SHARE * (y[0] + fm);
                m[2] = MOD_CROSS_SHARE * (y[3] + fm);
                m[3] = MOD_CROSS_SHARE * (y[2] + fm);
            }
            float sum = 0.0f;
            for (int v = 0; v < VOICES; v++) {
                float i = inc[v] * (1.0f + depth * m[v]);
                i = fminf(fmaxf(i, -0.45f), 0.45f);
                float p = phase[v] + i;
                if (p >= 1.0f) p -= 1.0f;
                else if (p < 0.0f) p += 1.0f;
                phase[v] = p;
                float tri = 4.0f * fabsf(p - 0.5f) - 1.0f;
                float a = amp[v], t = ampTarget[v];
                if (a != t) {
                    a = a < t ? fminf(a + ampStep, t) : fmaxf(a - ampStep, t);
                    amp[v] = a;
                }
                y[v] = fastTanh(gain[v] * tri) * norm[v] * a;
                sum += y[v];
            }
            return 0.25f * sum;
        }

        inline float readLine(int l, float delay) const {
            float pos = (float)writePos - delay;
            if (pos < 0.0f) pos += (float)lineSize;
            int i0 = (int)pos;
            float frac = pos - (float)i0;
            int i1 = i0 + 1;
            if (i1 >= lineSize) i1 -= lineSize;
            const float scale = 1.0f / 32767.0f;
            return (line[l][i0] + frac * (float)(line[l][i1] - line[l][i0])) * scale;
        }

    public:
        // Two delay buffers of `size` samples each (the app's static RAM;
        // >= DELAY_MAX_S x sample rate + 2).
        void init(float sr, int16_t* line1, int16_t* line2, int size) {
            sampleRate = sr;
            fs2 = sr * OVERSAMPLE;
            line[0] = line1;
            line[1] = line2;
            lineSize = size;
            memset(line1, 0, sizeof(int16_t) * size);
            memset(line2, 0, sizeof(int16_t) * size);
            writePos = 0;

            smoothRate = 1.0f - expf(-1000.0f / (SMOOTH_MS * sampleRate));
            tuneRate = 1.0f - expf(-1000.0f / (TUNE_SMOOTH_MS * sampleRate));
            ampStep = 1000.0f / (VOICE_FADE_MS * fs2);
            driftRate = 1.0f - expf(-1.0f / (DRIFT_SMOOTH_S * sampleRate));
            driftPeriod = (uint32_t)(DRIFT_SECONDS * sampleRate);
            delaySmooth = 1.0f - expf(-1000.0f / (DELAY_SMOOTH_MS * sampleRate));
            loopDcCoeff = expf(-2.0f * 3.14159265f * LOOP_DC_HZ / sampleRate);
            outDcCoeff = expf(-2.0f * 3.14159265f * OUT_DC_HZ / sampleRate);

            // Half-band: h(n) = 0.5 sinc(n / 2), Blackman window.
            float sum = 0.5f;
            hb[0] = 0.5f;
            for (int k = 1; k <= HB_SIDE; k++) {
                int n = 2 * k - 1;
                float x = 3.14159265f * n / 2.0f;
                float w = 0.42f + 0.5f * cosf(3.14159265f * n / (HB_CENTER + 1))
                        + 0.08f * cosf(2.0f * 3.14159265f * n / (HB_CENTER + 1));
                hb[k] = 0.5f * sinf(x) / x * w;
                sum += 2.0f * hb[k];
            }
            for (int k = 0; k <= HB_SIDE; k++) hb[k] /= sum;
            memset(hbHistory, 0, sizeof(hbHistory));
            hbPos = 0;

            for (int f = 0; f < 2; f++) {
                filter[f].setParameter(0, 0.0f);
                filter[f].setParameter(1, 0.0f);  // no envelope
                filter[f].setParameter(2, RESONANCE_K[resonanceStep] / PolyFilter::RESONANCE_MAX);
                filter[f].init(sr);
            }
            level.init(sr);

            for (int v = 0; v < VOICES; v++) {
                tuneNow[v] = tuneTarget[v];
                amp[v] = ampTarget[v];
                drift[v] = 0.0f;
                driftTarget[v] = 0.0f;
                y[v] = 0.0f;
            }
            for (int p = 0; p < 2; p++) sharpNow[p] = sharpTarget[p];
            modNow = modTarget;
            driveNow = driveTarget;
            feedbackNow = feedbackTarget;
            mixNow = mixTarget;
            trimNow = RESONANCE_TRIM[resonanceStep];
            control = 0;
            controlUpdate();
            for (int l = 0; l < 2; l++) {
                delaySamples[l] = delaySamplesTarget[l];
                damp[l] = loopDcX[l] = loopDcY[l] = 0.0f;
                outDcX[l] = outDcY[l] = 0.0f;
            }
            totalFb = 0.0f;
            flushSamples = 0;
        }

        // --- controls (0..1) ---------------------------------------------
        // Knob position 0..1: the mute zone, then the voice's curve over
        // the seven octaves.
        // Pitch travel 0..1 (above the mute zone) -> octaves above A0.
        static float tuneOctaves(int voice, float t) {
            const float k = TUNE_CURVE_K[voice];
            return TUNE_OCTAVES * t / (t + k * (1.0f - t));
        }
        void setTune(int voice, float pos) {
            if (voice < 0 || voice >= VOICES) return;
            if (pos < MUTE_OFF) ampTarget[voice] = 0.0f;
            else if (pos > MUTE_ON) ampTarget[voice] = 1.0f;
            float t = (pos - MUTE_ON) / (1.0f - MUTE_ON);
            tuneTarget[voice] = fminf(fmaxf(t, 0.0f), 1.0f);
        }
        void setSharp(int pair, float v) {
            if (pair >= 0 && pair < 2) sharpTarget[pair] = fminf(fmaxf(v, 0.0f), 1.0f);
        }
        void setMod(float v) { modTarget = fminf(fmaxf(v, 0.0f), 1.0f); }
        void setDrive(float v) { driveTarget = fminf(fmaxf(v, 0.0f), 1.0f); }
        void setDelayTime(float v) { delayTimeTarget = fminf(fmaxf(v, 0.0f), 1.0f); }
        void setFeedback(float v) { feedbackTarget = fminf(fmaxf(v, 0.0f), 1.0f); }
        void setDelayMix(float v) { mixTarget = fminf(fmaxf(v, 0.0f), 1.0f); }
        // Exponential, as the polysynth: 0 = 55 Hz .. 1 = 17.6 kHz.
        void setCutoff(float v) {
            v = fminf(fmaxf(v, 0.0f), 1.0f);
            filter[0].setParameter(3, 1.0f - v);
            filter[1].setParameter(3, 1.0f - v);
        }
        void setResonanceStep(int step) {
            if (step < 0 || step >= RESONANCE_STEPS) return;
            resonanceStep = step;
            float value = RESONANCE_K[step] / PolyFilter::RESONANCE_MAX;
            filter[0].setParameter(2, value);
            filter[1].setParameter(2, value);
        }
        void setRouting(int r) {
            if (r >= 0 && r < ROUTING_COUNT) routing = r;
        }
        void setTransposeNote(int note) {
            int semis = note - TRANSPOSE_ROOT;
            if (semis < -36) semis = -36;
            if (semis > 36) semis = 36;
            transpose = (float)semis;
        }
        // All Sound Off: the lines are rewritten with silence over one
        // delay length (no 176 KB clear in one sample period).
        void panic() { flushSamples = lineSize; }

        // --- state (tests, serial debug) ---------------------------------
        float getVoiceHz(int v) const { return voiceHz(v); }
        float getVoiceOutput(int v) const { return y[v]; }
        bool isVoiceOn(int v) const { return ampTarget[v] > 0.0f; }
        float getVoiceLevel(int v) const { return amp[v]; }
        float getSharpGain(int v) const { return gain[v]; }
        float getDelaySeconds(int l) const { return delaySamplesTarget[l] / sampleRate; }
        float getFeedbackGain() const { return FEEDBACK_MAX * feedbackTarget; }
        float getDampHz() const { return DAMP_MAX_HZ * powf(DAMP_MIN_HZ / DAMP_MAX_HZ, feedbackNow); }
        float getDriveGain() const { return driveGain; }
        float getMod() const { return modTarget; }
        float getModDepth() const { return MOD_DEPTH_MAX * modTarget * modTarget; }
        float getMix() const { return mixTarget; }
        float getCutoffHz() const { return filter[0].currentCutoffHz(); }
        float getResonanceK() const { return filter[0].getResonance(); }
        int getResonanceStep() const { return resonanceStep; }
        int getRouting() const { return routing; }
        float getTranspose() const { return transpose; }
        bool isFlushing() const { return flushSamples > 0; }

        // One output sample. `inject` adds to the voice mix (host tests;
        // the firmware passes 0); `voices` false mutes the oscillators.
        inline void process(float& outL, float& outR, float inject = 0.0f, bool voices = true) {
            if (control++ % CONTROL_BLOCK == 0) {
                controlUpdate();
            }

            // Voices, 2x oversampled, half-band decimated.
            const float depth = MOD_DEPTH_MAX * modNow * modNow;
            const float fm = totalFb;
            float a = oscStep(fm, depth);
            float b = oscStep(fm, depth);
            hbHistory[hbPos] = hbHistory[hbPos + HB_TAPS] = a;
            hbPos = hbPos + 1 == HB_TAPS ? 0 : hbPos + 1;
            hbHistory[hbPos] = hbHistory[hbPos + HB_TAPS] = b;
            hbPos = hbPos + 1 == HB_TAPS ? 0 : hbPos + 1;
            // hbHistory[hbPos .. hbPos + HB_TAPS - 1] = oldest .. newest
            const float* h = &hbHistory[hbPos];
            float dry = hb[0] * h[HB_CENTER];
            for (int k = 1; k <= HB_SIDE; k++) {
                int n = 2 * k - 1;
                dry += hb[k] * (h[HB_CENTER - n] + h[HB_CENTER + n]);
            }
            if (!voices) dry = 0.0f;
            dry += inject;

            // Delay: two lines, cross-fed, loop damped, DC-blocked, clipped.
            const float fbGain = FEEDBACK_MAX * feedbackNow;
            float wet[2];
            for (int l = 0; l < 2; l++) {
                delaySamples[l] += delaySmooth * (delaySamplesTarget[l] - delaySamples[l]);
                wet[l] = readLine(l, fmaxf(delaySamples[l], 1.0f));
            }
            for (int l = 0; l < 2; l++) {
                float fb = (1.0f - DELAY_CROSS) * wet[l] + DELAY_CROSS * wet[l ^ 1];
                damp[l] += dampCoeff * (fb - damp[l]);
                float hp = damp[l] - loopDcX[l] + loopDcCoeff * loopDcY[l];
                loopDcX[l] = damp[l];
                loopDcY[l] = hp;
                float in = kneeClip(DELAY_SEND * dry + fbGain * hp);
                if (flushSamples > 0) in = 0.0f;
                line[l][writePos] = (int16_t)(in * 32767.0f);
            }
            if (flushSamples > 0) {
                flushSamples = flushSamples - 1;
                wet[0] = wet[1] = 0.0f;
            }
            writePos = writePos + 1 == lineSize ? 0 : writePos + 1;

            // Mix -> DRIVE -> DC block -> TOTAL FB tap -> ladder -> limiter.
            float out[2];
            for (int c = 0; c < 2; c++) {
                float x = mixDry * dry + mixWet * wet[c];
                float d = (fastTanh(DRIVE_PRE * driveGain * x + driveBias) - driveBiasOut) * driveMakeup;
                float hp = d - outDcX[c] + outDcCoeff * outDcY[c];
                outDcX[c] = d;
                outDcY[c] = hp;
                out[c] = hp;
            }
            totalFb = fminf(fmaxf(0.5f * (out[0] + out[1]), -1.0f), 1.0f);
            const float outGain = OUTPUT_GAIN * trimNow / FILTER_DRIVE;
            for (int c = 0; c < 2; c++) {
                out[c] = outGain * filter[c].process(out[c] * FILTER_DRIVE);
            }
            level.limit(out[0], out[1]);
            outL = out[0];
            outR = out[1];
        }
};
