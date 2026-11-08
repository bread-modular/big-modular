#pragma once

#include <algorithm>
#include "io.h"
#include "midi.h"
#include "fs/FS.h"
#include "psram.h"
#include "audio/manager.h"
#include "audio/samples/s01.h"
#include "audio/mod/Biquad.h"
#include "audio/apps/sampler/sampler_dsp.h"
#include "audio/tools/sample_player.h"
#include "api/web_serial.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/motion_recorder.h"

#include "audio/apps/fx/delay_fx.h"
#include "audio/apps/fx/rumble_fx.h"
#include "audio/apps/fx/noop_fx.h"
#include "audio/apps/fx/metalverb_fx.h"

#define TOTAL_SAMPLE_PLAYERS 12

#define CONFIG_FX1_INDEX 0
#define CONFIG_FX2_INDEX 1
#define CONFIG_FX3_INDEX 2
#define CONFIG_SPLIT_AUDIO_INDEX 3

#define CONFIG_FX_NOOP 0
#define CONFIG_FX_DELAY 1
#define CONFIG_FX_METALVERB 2
#define CONFIG_FX_RUMBLE 3

// P1 / P2 (this module, not BM): P1 = group A drive, P2 = resonance of the
// group A highpass (P4); see audio/apps/sampler/sampler_dsp.h. They arrive on
// ADC0 / ADC1 through the CV1 / CV2 jacks. Unpatched, a knob gives 0..+5 V,
// which the level shift puts at 1.63..3.01 V = ADC ~2020..3735 (patched, the
// knob scales the CV; negative CV clamps to off).
#define KNOB_P12_ADC_ZERO 2020
#define KNOB_P12_ADC_FULL 3735
#define KNOB_P12_ADC_DIFF_THRESHOLD 20
#define KNOB_P12_READ_INTERVAL_MS 2

// MODE = 4-bar motion recorder (this module, not BM: BM's MODE stopped the
// audio while held and replayed the kick on release). It records P1..P4 and
// the twelve MCC CCs (FX1 CC20..23, FX2 CC27..30, FX3 CC85..88) on MIDI clock;
// see motion_recorder.h. CC71 / CC74 (P3 / P4 over MIDI) are not recorded.

class SamplerApp : public AudioApp {
    private:
        static SamplerApp* instance;
        FS *fs = FS::getInstance();
        IO *io = IO::getInstance();
        PSRAM *psram = PSRAM::getInstance();
        AudioManager *audioManager = AudioManager::getInstance();
        MIDI *midi = MIDI::getInstance();
        WebSerial* webSerial = WebSerial::getInstance();
        Biquad lowpassFilter{Biquad::FilterType::LOWPASS};
        Biquad highpassFilter{Biquad::FilterType::HIGHPASS};
        DjHighpass djHighpass;
        KickDrive drive;
        OutputGuard outputGuard;
        volatile bool driveOn = false;
        volatile bool resonanceOn = false;
        uint16_t p1Value = 0;
        uint16_t p2Value = 0;
        MotionRecorder recorder;
        // Last values sent to the filters / FX, so playback only touches a
        // parameter when its recorded (or offset) value changes.
        MotionRecorder::Frame appliedFrame = {};
        bool frameApplied = false;
        bool knobsFirstRead = true;
        uint32_t lastKnobsReadMs = 0;
        // FX1 starts empty (BM 1.6.0 started Rumble, while get-fx1 reported
        // noop); Rumble runs only when picked with set-fx1 rumble.
        AudioFX* fx1 = new NoopFX;
        AudioFX* fx2 = new MetalVerbFX;
        AudioFX* fx3 = new NoopFX;

        uint16_t currentBPM = 120;

        // Default sample
        int16_t* defaultSample = (int16_t*)s01_wav;
        uint32_t defaultSampleLen = s01_wav_len / 2;
        uint32_t defaultSamplePlayhead = defaultSampleLen;
        uint32_t lastKickPlayhead = defaultSampleLen;
        float velocityOfDefaultSample = 1.0f;

        Config config{4, "/sampler_config.dat"};

        // Uploadable samples
        SamplePlayer players[TOTAL_SAMPLE_PLAYERS] = {
            SamplePlayer(0), SamplePlayer(1), SamplePlayer(2), SamplePlayer(3), SamplePlayer(4), SamplePlayer(5),
            SamplePlayer(6), SamplePlayer(7), SamplePlayer(8), SamplePlayer(9), SamplePlayer(10),
            SamplePlayer(11)
        };

    public:
        SamplerApp() {

        }
        
        static AudioApp* getInstance() {
            if (!instance) {
                instance = new SamplerApp();
            }
            return instance;
        }

        void init() override {
            audioManager->setAdcEnabled(false);
            psram->freeall();
            lowpassFilter.init(audioManager);
            highpassFilter.init(audioManager);
            djHighpass.init((float)audioManager->getDac()->getSampleRate());
            drive.init((float)audioManager->getDac()->getSampleRate());
            outputGuard.init((float)audioManager->getDac()->getSampleRate());
            knobsFirstRead = true;
            fx1->init(audioManager);
            fx2->init(audioManager);
            fx3->init(audioManager);

            for (int i=0; i<TOTAL_SAMPLE_PLAYERS; i++) {
                players[i].init();
            }

            config.load();
            uint8_t fx1Value = config.get(CONFIG_FX1_INDEX, CONFIG_FX_NOOP);
            uint8_t fx2Value = config.get(CONFIG_FX2_INDEX, CONFIG_FX_METALVERB);
            uint8_t fx3Value = config.get(CONFIG_FX3_INDEX, CONFIG_FX_NOOP);

            setFX(CONFIG_FX1_INDEX, fx1Value);
            setFX(CONFIG_FX2_INDEX, fx2Value);
            setFX(CONFIG_FX3_INDEX, fx3Value);

            // Every audio start (boot, set-fx, sample upload) re-creates the
            // FX at their defaults, so earlier CC values no longer apply. The
            // take is RAM only and is dropped too.
            recorder.setLedCallback(&SamplerApp::setRecorderLed);
            recorder.begin(time_us_32() / 1000);
            recorder.clearCurrentCcs();
        }

        __attribute__((hot)) void audioCallback(AudioInput *input, AudioOutput *output) override {
            audioManager->startAudioLock();

            // first 6 samples has FX support & others are just playing (no fx)
            float sumGroupA = 0.0f;

            // Detect a fresh kick onset (the default sample was just retriggered).
            // We sample the playhead BEFORE it advances, so an onset is a reset
            // to 0 (either from idle, or a retrigger while still playing).
            uint32_t playheadOnEntry = defaultSamplePlayhead;
            bool kickOnset = (playheadOnEntry == 0 && lastKickPlayhead != 0);
            lastKickPlayhead = playheadOnEntry;

            if (defaultSamplePlayhead < defaultSampleLen) {
                sumGroupA += (defaultSample[defaultSamplePlayhead++] / 32768.0f) * velocityOfDefaultSample;
            }

            // Uploaded samples also retrigger the rumble: consume their onset
            // flags (set by SamplePlayer::play) alongside the default sample's.
            bool uploadedOnset = false;
            for (int i = 0; i < 6; ++i) {
                sumGroupA += players[i].process() / 32768.0f;
                if (players[i].consumeOnset()) {
                    uploadedOnset = true;
                }
            }
            
            // Kick-onset pulse for FX1 (Rumble).
            // This is a one-sample trigger (not a level): the FX retriggers its
            // one-beat noise burst on every fresh kick hit — from the flash
            // default sample OR any uploaded sample in group A.
            fx1->setGate(kickOnset || uploadedOnset);

            float sumGroupB = 0.0f;
            for (int i = 6; i < TOTAL_SAMPLE_PLAYERS; ++i) {
                sumGroupB += players[i].process() / 32768.0f;
            }

            audioManager->endAudioLock();

            // P1 drive first, so the P3 lowpass after it shapes its tone.
            sumGroupA = drive.process(sumGroupA);
            sumGroupA = lowpassFilter.process(sumGroupA);

            // Apply FX to group A
            sumGroupA = fx1->process(sumGroupA);
            sumGroupA = fx2->process(sumGroupA);

            // End-of-chain highpass (CV2). Runs AFTER the FX so it also shapes
            // the rumble noise burst generated inside FX1 — previously the
            // highpass ran pre-FX and the rumble bypassed it completely.
            // P2 turns it into the resonant 24 dB/oct DJ highpass (fully
            // down: this Biquad alone); the guard holds the ring under full
            // scale, then (P1 up) the clip catches the driven kick's
            // overshoot. Both are out of the path with P1 / P2 fully down.
            sumGroupA = djHighpass.process(sumGroupA, highpassFilter.process(sumGroupA));
            sumGroupA = outputGuard.process(sumGroupA, resonanceOn);
            if (driveOn) {
                sumGroupA = SamplerDsp::outputClip(sumGroupA);
            }

            // Apply FX to group B (no filters, as in BM)
            sumGroupB = fx3->process(sumGroupB);

            float sampleSum = sumGroupB + sumGroupA;

            output->left = sampleSum;
            output->right = sampleSum;
        }

        __attribute__((cold, noinline)) void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {
            uint8_t sampleToPlay = note % 12;
            // Keep current playback method for sampleId 0
            float velocityNorm = velocity / 127.0f;
            float realVelocity = powf(velocityNorm, 2.0f);
            if (sampleToPlay == 0) {
                audioManager->startAudioLock();
                defaultSamplePlayhead = 0;
                velocityOfDefaultSample = realVelocity;
                audioManager->endAudioLock();
            } else if (sampleToPlay <= 11) {
                // Use SamplePlayer for sampleId 1 to 11
                audioManager->startAudioLock();
                players[sampleToPlay].play(realVelocity);
                audioManager->endAudioLock();
            }
        }

        __attribute__((cold, noinline)) void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override {   
    
        }

        __attribute__((cold, noinline)) void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override {
            // During playback a recorded MCC CC is owned by the loop: keep its
            // latest value (the recorder turns moves into an offset) but don't
            // apply it. MCC CCs missing from the take stay live.
            if (recorder.ownsCc(cc)) {
                recorder.setCurrentCc(cc, value);
                return;
            }

            // Filter Controls (the loop owns P3 / P4 during playback)
            if (cc == 71) {
                cv1UpdateCallback(value * 32);
            } else if (cc == 74) {
                cv2UpdateCallback(value * 32);
            }

            if (applyFxCc(cc, value)) {
                recorder.setCurrentCc(cc, value);
            }
        }

        // MCC CC -> FX parameter: Bank A CC20..23 -> FX1, Bank B CC27..30 ->
        // FX2, Bank C CC85..88 -> FX3. Returns false for any other CC.
        bool applyFxCc(uint8_t cc, uint8_t value) {
            int index = MotionRecorder::ccIndex(cc);
            if (index < 0) {
                return false;
            }
            AudioFX* bankFx[3] = {fx1, fx2, fx3};
            bankFx[index / MotionRecorder::MCC_CCS_PER_BANK]->setParameter(
                index % MotionRecorder::MCC_CCS_PER_BANK, value / 127.0f);
            return true;
        }

        __attribute__((cold, noinline)) void cv1UpdateCallback(uint16_t cv1) override {
            if (!recorder.isPlayingBack()) {
                applyP3(cv1);
            }
        }

        __attribute__((cold, noinline)) void cv2UpdateCallback(uint16_t cv2) override {
            if (!recorder.isPlayingBack()) {
                applyP4(cv2);
            }
        }

        void applyP3(uint16_t cv1) {
            float cv1Norm = 1.0 - IO::normalizeCV(cv1);
            float cutoff = 50.0f * powf(20000.0f / 50.0f, cv1Norm * cv1Norm);
            lowpassFilter.setCutoff(cutoff);
        }

        void applyP4(uint16_t cv2) {
            float cv2Norm = IO::normalizeCV(cv2);
            float cutoff = SamplerDsp::p4Cutoff(cv2Norm);
            highpassFilter.setCutoff(cutoff);
            djHighpass.setCutoff(cutoff);
        }

        // P1 / P2 knob range rescaled to 0..1 (fully down = 0 = off).
        static float knobNormalize(uint16_t value) {
            float norm = (value - (float)KNOB_P12_ADC_ZERO) / (float)(KNOB_P12_ADC_FULL - KNOB_P12_ADC_ZERO);
            return std::clamp(norm, 0.0f, 1.0f);
        }

        void applyP1(uint16_t p1) {
            driveOn = drive.setDrive(knobNormalize(p1));
        }

        void applyP2(uint16_t p2) {
            resonanceOn = djHighpass.setResonance(knobNormalize(p2));
        }

        // The audio core leaves ADC0 / ADC1 alone here (setAdcEnabled(false)),
        // so read P1 / P2 from the main loop, under the same lock IO uses.
        void readP1P2Knobs() {
            uint32_t now = time_us_32() / 1000;
            if (!knobsFirstRead && (now - lastKnobsReadMs) < KNOB_P12_READ_INTERVAL_MS) {
                return;
            }
            lastKnobsReadMs = now;

            audioManager->startAdcLock();
            adc_select_input(A0);
            uint16_t newP1 = adc_read();
            adc_select_input(A1);
            uint16_t newP2 = adc_read();
            audioManager->endAdcLock();

            // The loop owns P1 / P2 during playback; keep tracking them for
            // the knob offset.
            if (knobsFirstRead || abs(p1Value - newP1) > KNOB_P12_ADC_DIFF_THRESHOLD) {
                p1Value = newP1;
                if (!recorder.isPlayingBack()) {
                    applyP1(p1Value);
                }
            }
            if (knobsFirstRead || abs(p2Value - newP2) > KNOB_P12_ADC_DIFF_THRESHOLD) {
                p2Value = newP2;
                if (!recorder.isPlayingBack()) {
                    applyP2(p2Value);
                }
            }
            knobsFirstRead = false;
        }

        __attribute__((cold, noinline)) void buttonPressedCallback(bool pressed) override {
            const MotionRecorder::State before = recorder.getState();
            recorder.buttonChanged(pressed, time_us_32() / 1000);

            // Knob moves were only tracked while the loop played: hand the
            // filters and FX back to the live controls.
            if (!pressed && before == MotionRecorder::STATE_PLAYBACK && recorder.isLive()) {
                applyLiveControls();
            }
        }

        void readKnobs(uint16_t knobs[MotionRecorder::KNOB_COUNT]) {
            knobs[MotionRecorder::KNOB_P1] = p1Value;
            knobs[MotionRecorder::KNOB_P2] = p2Value;
            knobs[MotionRecorder::KNOB_P3] = io->getCV1();
            knobs[MotionRecorder::KNOB_P4] = io->getCV2();
        }

        void applyLiveControls() {
            uint16_t knobs[MotionRecorder::KNOB_COUNT];
            readKnobs(knobs);
            applyP1(knobs[MotionRecorder::KNOB_P1]);
            applyP2(knobs[MotionRecorder::KNOB_P2]);
            applyP3(knobs[MotionRecorder::KNOB_P3]);
            applyP4(knobs[MotionRecorder::KNOB_P4]);
            for (uint8_t i = 0; i < MotionRecorder::CC_COUNT; i++) {
                uint8_t cc = MotionRecorder::ccNumber(i);
                uint8_t value = recorder.getCurrentCc(cc);
                if (value != MotionRecorder::CC_UNSET) {
                    applyFxCc(cc, value);
                }
            }
        }

        static void setRecorderLed(bool on) {
            IO::getInstance()->setLED(on);
        }

        static void applyRecordedFrame(void* context, const MotionRecorder::Frame& frame) {
            SamplerApp* self = static_cast<SamplerApp*>(context);
            if (self == nullptr) {
                return;
            }

            // The first frame of a loop applies everything; later frames only
            // what changed.
            bool all = !self->frameApplied;
            self->frameApplied = true;
            MotionRecorder::Frame& last = self->appliedFrame;
            void (SamplerApp::*knobApply[MotionRecorder::KNOB_COUNT])(uint16_t) = {
                &SamplerApp::applyP1, &SamplerApp::applyP2,
                &SamplerApp::applyP3, &SamplerApp::applyP4,
            };
            for (uint8_t i = 0; i < MotionRecorder::KNOB_COUNT; i++) {
                if (all || frame.knobs[i] != last.knobs[i]) {
                    (self->*knobApply[i])(frame.knobs[i]);
                }
            }
            for (uint8_t i = 0; i < MotionRecorder::CC_COUNT; i++) {
                if (frame.ccs[i] != MotionRecorder::CC_UNSET &&
                    (all || frame.ccs[i] != last.ccs[i])) {
                    self->applyFxCc(MotionRecorder::ccNumber(i), frame.ccs[i]);
                }
            }
            last = frame;
        }

        void realtimeCallback(uint8_t realtimeType) override {
            switch (realtimeType) {
                case MIDI_REALTIME_CLOCK: {
                    if (!recorder.isPlayingBack()) {
                        frameApplied = false;
                    }
                    uint16_t knobs[MotionRecorder::KNOB_COUNT];
                    readKnobs(knobs);
                    recorder.onClock(knobs, &SamplerApp::applyRecordedFrame, this);
                    break;
                }
                case MIDI_REALTIME_START:
                    recorder.onStart();
                    break;
                default:
                    // STOP/CONTINUE keep the take; with no clock the playhead holds.
                    break;
            }
        }

        __attribute__((cold, noinline)) void bpmChangeCallback(int bpm) override {
            currentBPM = bpm;
            fx1->setBPM(bpm);
            fx2->setBPM(bpm);
            fx3->setBPM(bpm);
        }

        void setFX(int8_t index, int8_t value) {
            AudioFX** targetFx = nullptr;
            switch (index) {
                case CONFIG_FX1_INDEX:
                    targetFx = &fx1;
                    break;
                case CONFIG_FX2_INDEX:
                    targetFx = &fx2;
                    break;
                case CONFIG_FX3_INDEX:
                    targetFx = &fx3;
                    break;
                default:
                    return;
            }

            AudioFX* newFx = nullptr;
            switch (value) {
                case CONFIG_FX_NOOP:
                    newFx = new NoopFX;
                    break;
                case CONFIG_FX_DELAY:
                    newFx = new DelayFX;
                    break;
                case CONFIG_FX_METALVERB:
                    newFx = new MetalVerbFX;
                    break;
                case CONFIG_FX_RUMBLE:
                    newFx = new RumbleFX;
                    break;
                default:
                    return;
            }

            newFx->init(audioManager);
            newFx->setBPM(currentBPM);
            AudioFX* fxToDelete = *targetFx;
            *targetFx = newFx;
            delete fxToDelete;
        }

        bool onCommandCallback(const char* cmd) override {

            // Parse: play-sample <sample-id>
            if (strncmp(cmd, "play-sample", 11) == 0) {
                int sampleId = -1;
                if (!sscanf(cmd + 11, "%d", &sampleId)) {
                    printf("Usage: play-sample <sample-id 0-11>\n");
                    return true;
                }   

                if (sampleId < 0 || sampleId > 11) {
                    printf("Usage: play-sample <sample-id 0-11>\n");
                    return true;
                }

                audioManager->startAudioLock();
                if (sampleId == 0) {
                    defaultSamplePlayhead = 0;
                    velocityOfDefaultSample = 0.8f;
                } else {
                    players[sampleId].play(0.8f);
                }
                audioManager->endAudioLock();

                return true;
            }


            // Parse: set-fx<fx-id> <fx-name>  
            if (strncmp(cmd, "set-fx", 6) == 0) {
                uint8_t fxIndex = -1;
                char fxId = cmd[6];
                if (fxId == '1') {
                    fxIndex = CONFIG_FX1_INDEX;
                } else if (fxId == '2') {
                    fxIndex = CONFIG_FX2_INDEX;
                } else if (fxId == '3') {
                    fxIndex = CONFIG_FX3_INDEX;
                } else {
                    printf("Usage: set-fx<fx-id> <fx-name>\n");
                    return true;
                }

                const char* fxName = cmd + 8;
                uint8_t newFx = -1;
                if (strncmp(fxName, "noop", 4) == 0) {
                    newFx = CONFIG_FX_NOOP;
                } else if (strncmp(fxName, "delay", 5) == 0) {
                    newFx = CONFIG_FX_DELAY;
                } else if (strncmp(fxName, "metalverb", 9) == 0) {
                    newFx = CONFIG_FX_METALVERB;
                } else if (strncmp(fxName, "rumble", 6) == 0) {
                    newFx = CONFIG_FX_RUMBLE;
                } else {
                    printf("No such fx found: %s\n", fxName);
                    return true;
                }

                // Stop the audio manager & save the config
                // Once we start the audio manager, it will reload this app
                // So it will load the fx from the config
                audioManager->stop();
                config.set(fxIndex, newFx);
                config.save();
                audioManager->start();
                return true;
            }

            // Parse: get-fx<fx-id>
            if (strncmp(cmd, "get-fx", 6) == 0) {
                uint8_t fxIndex = -1;
                char fxId = cmd[6];
                if (fxId == '1') {
                    fxIndex = CONFIG_FX1_INDEX;
                } else if (fxId == '2') {   
                    fxIndex = CONFIG_FX2_INDEX;
                } else if (fxId == '3') {
                    fxIndex = CONFIG_FX3_INDEX;
                } else {
                    printf("Usage: get-fx<fx-id>\n");
                    return true;
                }

                uint8_t fxValue = config.get(fxIndex, CONFIG_FX_NOOP);
                if (fxValue == CONFIG_FX_NOOP) {
                    webSerial->sendValue("noop");
                } else if (fxValue == CONFIG_FX_DELAY) {
                    webSerial->sendValue("delay");
                } else if (fxValue == CONFIG_FX_METALVERB) {
                    webSerial->sendValue("metalverb");
                } else if (fxValue == CONFIG_FX_RUMBLE) {
                    webSerial->sendValue("rumble");
                }
                return true;
            }

            // Parse: write-sample-base64 <sample-id> <original-size> <base64-length>
            if (strncmp(cmd, "write-sample-base64 ", 20) == 0) {
                int sampleId = -1, originalSize = -1, base64Size = -1;
                if (!sscanf(cmd + 20, "%d %d %d", &sampleId, &originalSize, &base64Size)) {
                    printf("Usage: write-sample-base64 <sample-id 0-11> <original-size> <base64-length>\n");
                    return false;
                }

                if (!(sampleId >= 0 && sampleId <= 11 && originalSize > 0 && base64Size > 0)) {
                    printf("Usage: write-sample-base64 <sample-id 0-11> <original-size> <base64-length>\n");
                    return false;
                }

                bool accepted = webSerial->acceptBinary(originalSize, base64Size, [sampleId](uint8_t* data, int size) {
                    if(SamplePlayer::saveSample(sampleId, data, size)) {
                        printf("Sample %02d saved\n", sampleId);
                    } else {
                        printf("Failed to save sample %02d\n", sampleId);
                    }
                });

                if (!accepted) {
                    return false;
                }

                printf("Ready to receive %d Base64 chars for sample %02d (original %d bytes)\n", base64Size, sampleId, originalSize);
                return true;
            }

            return false;
        }

        void update() override {
            readP1P2Knobs();
            recorder.update(time_us_32() / 1000);
        }
};

SamplerApp* SamplerApp::instance = nullptr;
