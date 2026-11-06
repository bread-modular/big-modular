#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/gen/Wavetable.h"
#include "audio/env/AttackHoldRelease.h"
#include "audio/env/Envelope.h"
#include "audio/tools/Voice.h"
#include "audio/apps/motion_recorder.h"
#include "audio/apps/polysynth/poly_level.h"
#include "audio/apps/polysynth/poly_filter.h"

#define TOTAL_VOICES 6  // BM: 9; 6 leaves the audio core headroom with wavetables

// Wavetables on the top knobs (this module, not BM): P1 picks the table, P2
// moves the position (both with their CV jacks). P1 has one zone per table
// plus Noise at the top; fully down is Classic, P2 morphing square -> saw ->
// tri -> sine. On Noise P2 sweeps the noise types. P1 / P2
// arrive on ADC0 / ADC1: unpatched a knob gives 0..+5 V = ADC ~2020..3735 (as in the sampler); patched, the knob
// scales the CV and negative CV clamps to the bottom.
#define TOP_KNOB_ADC_ZERO 2020
#define TOP_KNOB_ADC_FULL 3735
#define TOP_KNOB_ADC_DIFF_THRESHOLD 12
#define TOP_KNOB_READ_INTERVAL_MS 2
#define WAVETABLE_ZONES WAVETABLE_ZONE_COUNT  // tables + Noise
#define WAVETABLE_NOISE_ZONE WAVETABLE_COUNT
#define WAVETABLE_ZONE_HYSTERESIS 0.15f

class PolySynthApp : public AudioApp {
private:
    static PolySynthApp* instance;
    IO *io = IO::getInstance();
    WebSerial *webSerial = WebSerial::getInstance();
    AudioManager *audioManager = AudioManager::getInstance();
    Wavetable wavetableGenerators[TOTAL_VOICES];
    WavetableControl wavetableControl;
    PolyFilter filter;  // BM: FilterFX (Ladder.h); see poly_filter.h
    MotionRecorder recorder;
    PolyLevel outputLevel;

    Voice* voices[TOTAL_VOICES];

    int8_t totalNotesOn = 0;

    uint8_t wavetableZone = 0;  // wavetable index (0 = Classic, last = Noise)
    uint16_t p1Value = 0;
    uint16_t p2Value = 0;
    bool topKnobsFirstRead = true;
    uint32_t lastTopKnobsReadMs = 0;

    Voice* findFreeVoice() {
        for (int i = 0; i < TOTAL_VOICES; i++) {
            if (!voices[i]->getAmpEnvelope()->isActive()) {
                return voices[i];
            }
        }
        return nullptr;
    }

    void applyLiveCv(uint16_t cv1, uint16_t cv2);
    void applyCc(uint8_t parameter, uint8_t value);
    static float topKnobNormalize(uint16_t value);
    void readTopKnobs();
    void applyP1(uint16_t p1);
    void applyP2(uint16_t p2);
    void loadWavetable(uint8_t table);
    static void setRecorderLed(bool on);
    void readKnobs(uint16_t knobs[MotionRecorder::KNOB_COUNT]);
    static void applyRecordedFrame(void* context,
                                    const MotionRecorder::Frame& frame);

public:
    void init() override;
    void audioCallback(AudioInput *input, AudioOutput *output) override;
    void update() override;
    void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) override;
    void ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) override;
    void bpmChangeCallback(int bpm) override;
    void realtimeCallback(uint8_t realtimeType) override;
    void cv1UpdateCallback(uint16_t cv1) override;
    void cv2UpdateCallback(uint16_t cv2) override;
    void buttonPressedCallback(bool pressed) override;
    bool onCommandCallback(const char* cmd) override;
    static PolySynthApp* getInstance();
}; 
