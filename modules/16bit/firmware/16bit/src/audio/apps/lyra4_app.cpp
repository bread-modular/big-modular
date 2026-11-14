// Implementation split from header.
#include "audio/apps/lyra4_app.h"

#include <cmath>
#include <cstdio>
#include <cstring>

namespace lc = lyra4_controls;

Lyra4App* Lyra4App::instance = nullptr;

namespace {
// The two delay lines (2 x 88 KB, 16-bit). Static RAM: the audio core reads
// them every sample (PSRAM is too slow for that).
int16_t lyra4Lines[2][LYRA4_DELAY_LINE_SAMPLES];
}  // namespace

void Lyra4App::init() {
    // ADC0 / ADC1 carry P1 / P2 here, read from the main loop (as the
    // polysynth), not audio inputs.
    audioManager->setAdcEnabled(false);

    // Power-on values until the MCCs send theirs (they resend every second).
    // The controls are set before dsp.init(), which starts from them.
    for (uint8_t i = 0; i < 8; i++) {
        lc::apply(dsp, lc::RECORDED_CCS[i], lc::SEED_CC[i]);
    }
    dsp.setRouting(Lyra4Dsp::ROUTING_PAIRS);
    dsp.setResonanceStep(0);
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        dsp.setTune(k, 0.5f);
    }
    dsp.init(audioManager->getDac()->getSampleRate(), lyra4Lines[0], lyra4Lines[1],
             LYRA4_DELAY_LINE_SAMPLES);
    // The first readKnobs() (main loop, after the audio core set up ADC0 /
    // ADC1) sets the four TUNEs.
    knobsFirstRead = true;

    // The recorder is volatile (RAM only). Seed the MCC snapshot with the
    // power-on values, so a take that doesn't move a CC replays this sound.
    recorder.setLedCallback(&Lyra4App::setRecorderLed);
    recorder.begin(nowMs());
    recorder.clearCurrentCcs();
    for (uint8_t i = 0; i < 8; i++) {
        recorder.setCurrentCc(lc::RECORDED_CCS[i], lc::SEED_CC[i]);
    }
}

__attribute__((hot))
void Lyra4App::audioCallback(AudioInput *input, AudioOutput *output) {
    (void)input;
    dsp.process(output->left, output->right);
}

void Lyra4App::update() {
    readKnobs();
    uint16_t knobs[MotionRecorder::KNOB_COUNT];
    recorderKnobs(knobs);
    recorder.update(nowMs(), knobs, &Lyra4App::applyRecordedFrame, this);
}

// Milliseconds from the 64-bit timer: wraps at 2^32 ms (49 days), as the
// recorder's arithmetic expects (time_us_32() / 1000 jumps back after 71 min).
uint32_t Lyra4App::nowMs() {
    return (uint32_t)(time_us_64() / 1000);
}

// P1..P4 = ADC0..3, read every 2 ms under the ADC lock IO uses, four
// conversions averaged, then smoothed. A TUNE is set once its knob moves by
// LYRA4_KNOB_APPLY_STEP counts. During playback the loop owns the knobs;
// they're still tracked for the recorder's offset.
void Lyra4App::readKnobs() {
    uint32_t now = nowMs();
    if (!knobsFirstRead && (now - lastKnobReadMs) < LYRA4_KNOB_READ_INTERVAL_MS) {
        return;
    }
    lastKnobReadMs = now;

    uint32_t sum[MotionRecorder::KNOB_COUNT] = {};
    audioManager->startAdcLock();
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        adc_select_input(k);
        for (uint8_t i = 0; i < LYRA4_KNOB_OVERSAMPLE; i++) {
            sum[k] += adc_read();
        }
    }
    audioManager->endAdcLock();

    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        float raw = sum[k] / (float)LYRA4_KNOB_OVERSAMPLE;
        if (knobsFirstRead) {
            knobSmooth[k] = raw;
        } else {
            knobSmooth[k] += LYRA4_KNOB_SMOOTH * (raw - knobSmooth[k]);
        }
        if (recorder.isPlayingBack()) {
            continue;
        }
        if (knobsFirstRead || fabsf(knobSmooth[k] - knobApplied[k]) > LYRA4_KNOB_APPLY_STEP) {
            applyKnob(k, knobSmooth[k]);
        }
    }
    knobsFirstRead = false;
}

void Lyra4App::applyKnob(uint8_t knob, float adc) {
    knobApplied[knob] = adc;
    dsp.setTune(knob, lc::knobToTune(knob, adc));
}

// Back to LIVE after a loop: the knobs where they are, the MCC values last
// received.
void Lyra4App::applyLiveControls() {
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        applyKnob(k, knobSmooth[k]);
    }
    for (uint8_t i = 0; i < 8; i++) {
        uint8_t value = recorder.getCurrentCc(lc::RECORDED_CCS[i]);
        if (value != MotionRecorder::CC_UNSET) {
            lc::apply(dsp, lc::RECORDED_CCS[i], value);
        }
    }
}

// Any channel: a note sets PITCH (velocity 0 is a note-off).
__attribute__((cold, noinline))
void Lyra4App::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    if (velocity > 0) {
        dsp.setTransposeNote(note);
    }
}

void Lyra4App::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    (void)note;
    (void)velocity;
}

__attribute__((cold, noinline))
void Lyra4App::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    (void)channel;
    // During playback a recorded CC belongs to the loop: keep its latest
    // value for the offset, don't apply it.
    if (recorder.ownsCc(cc)) {
        recorder.setCurrentCc(cc, value);
        return;
    }
    if (lc::apply(dsp, cc, value)) {
        recorder.setCurrentCc(cc, value);  // ignored for the button CCs
    }
}

void Lyra4App::bpmChangeCallback(int bpm) {
    (void)bpm;
}

// No MIDI timing: the recorder runs on its own clock (update()).
void Lyra4App::realtimeCallback(uint8_t realtimeType) {
    (void)realtimeType;
}

// P3 / P4 are read in readKnobs(), not through IO's callbacks.
void Lyra4App::cv1UpdateCallback(uint16_t cv1) {
    (void)cv1;
}

void Lyra4App::cv2UpdateCallback(uint16_t cv2) {
    (void)cv2;
}

__attribute__((cold, noinline))
void Lyra4App::buttonPressedCallback(bool pressed) {
    const MotionRecorder::State before = recorder.getState();
    recorder.buttonChanged(pressed, nowMs());
    if (!pressed && before == MotionRecorder::STATE_PLAYBACK && recorder.isLive()) {
        applyLiveControls();
    }
}

void Lyra4App::setRecorderLed(bool on) {
    IO::getInstance()->setLED(on);
}

void Lyra4App::recorderKnobs(uint16_t knobs[MotionRecorder::KNOB_COUNT]) {
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        knobs[k] = (uint16_t)(knobSmooth[k] + 0.5f);
    }
}

void Lyra4App::applyRecordedFrame(void* context, const MotionRecorder::Frame& frame) {
    Lyra4App* self = static_cast<Lyra4App*>(context);
    if (self == nullptr) {
        return;
    }
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        self->applyKnob(k, frame.knobs[k]);
    }
    for (uint8_t i = 0; i < 8; i++) {
        if (frame.ccs[i] != MotionRecorder::CC_UNSET) {
            lc::apply(self->dsp, lc::RECORDED_CCS[i], frame.ccs[i]);
        }
    }
}

// get-lyra4-params: the live DSP state over serial (bench checks).
bool Lyra4App::onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "get-lyra4-params", 16) == 0) {
        printf("tune_hz %.2f %.2f %.2f %.2f transpose %d\n",
               dsp.getVoiceHz(0), dsp.getVoiceHz(1), dsp.getVoiceHz(2), dsp.getVoiceHz(3),
               (int)dsp.getTranspose());
        printf("sharp_gain %.2f %.2f mod_depth %.3f routing %d drive_gain %.2f\n",
               dsp.getSharpGain(0), dsp.getSharpGain(2), dsp.getModDepth(), dsp.getRouting() + 1,
               dsp.getDriveGain());
        printf("delay_ms %.1f %.1f feedback %.3f damp_hz %.0f mix %.2f cutoff_hz %.0f resonance %d k %.2f\n",
               dsp.getDelaySeconds(0) * 1000.0f, dsp.getDelaySeconds(1) * 1000.0f, dsp.getFeedbackGain(),
               dsp.getDampHz(), dsp.getMix(), dsp.getCutoffHz(), dsp.getResonanceStep() + 1,
               dsp.getResonanceK());
        return true;
    }
    return false;
}

Lyra4App* Lyra4App::getInstance() {
    if (!instance) {
        instance = new Lyra4App();
    }
    return instance;
}
