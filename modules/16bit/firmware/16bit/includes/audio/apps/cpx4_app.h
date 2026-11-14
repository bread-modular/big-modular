#pragma once

#include "midi.h"
#include "io.h"
#include "api/web_serial.h"
#include "audio/manager.h"
#include "audio/apps/interfaces/audio_app.h"
#include "audio/apps/free_motion_recorder.h"
#include "audio/apps/cpx4/cpx4_dsp.h"
#include "audio/apps/cpx4/cpx4_controls.h"

// CPX4 (this module, not BM): a four-voice drone inspired by the SOMA
// Lyra-8, played from the 16bit knobs and two MCCs running the cpx4 MCC
// firmware (../mcc/). DSP: audio/apps/cpx4/cpx4_dsp.h, control map:
// audio/apps/cpx4/cpx4_controls.h.
//
//   P1..P4      TUNE 1..4 (read here at 12 bits, smoothed; not through IO's
//               50-count CV callbacks, too coarse for beating)
//   MCC-1       CC20 SHARP A, CC21 SHARP B, CC22 MOD, CC23 DRIVE,
//               button CC102 FM routing
//   MCC-2       CC27 DELAY TIME, CC28 FEEDBACK, CC29 DELAY MIX, CC30 CUTOFF,
//               button CC103 RESONANCE
//   MIDI notes  PITCH (transpose all voices, C4 = 0)
//   MODE        free-running motion recorder (free_motion_recorder.h, no
//               MIDI clock): press to record, press again to close the loop;
//               hold + move to overdub. P1..P4 + the eight MCC knobs
#define CPX4_KNOB_READ_INTERVAL_MS 2
#define CPX4_KNOB_OVERSAMPLE 4
#define CPX4_KNOB_SMOOTH 0.3f        // one-pole per read (~6 ms)
#define CPX4_KNOB_APPLY_STEP 0.75f   // ADC counts before a new TUNE is set
#define CPX4_DELAY_LINE_SAMPLES (44100 + 64)  // 1 s at 44.1 kHz + margin

class Cpx4App : public AudioApp {
private:
    static Cpx4App* instance;
    IO *io = IO::getInstance();
    WebSerial *webSerial = WebSerial::getInstance();
    AudioManager *audioManager = AudioManager::getInstance();
    Cpx4Dsp dsp;
    FreeMotionRecorder recorder;

    float knobSmooth[MotionRecorder::KNOB_COUNT] = {};
    float knobApplied[MotionRecorder::KNOB_COUNT] = {};
    bool knobsFirstRead = true;
    uint32_t lastKnobReadMs = 0;

    void readKnobs();
    void applyKnob(uint8_t knob, float adc);
    void applyLiveControls();
    static void setRecorderLed(bool on);
    void recorderKnobs(uint16_t knobs[MotionRecorder::KNOB_COUNT]);
    static uint32_t nowMs();
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
    static Cpx4App* getInstance();
};
