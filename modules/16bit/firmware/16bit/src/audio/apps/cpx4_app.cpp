// Implementation split from header.
#include "audio/apps/cpx4_app.h"

#include <cmath>
#include <cstdio>
#include <cstring>

namespace lc = cpx4_controls;

Cpx4App* Cpx4App::instance = nullptr;

namespace {
// The two delay lines (2 x 88 KB, 16-bit). Static RAM: the audio core reads
// them every sample (PSRAM is too slow for that).
int16_t cpx4Lines[2][CPX4_DELAY_LINE_SAMPLES];
}  // namespace

void Cpx4App::init() {
    // ADC0 / ADC1 carry P1 / P2 here, read from the main loop (as the
    // polysynth), not audio inputs.
    audioManager->setAdcEnabled(false);

    // Power-on values until the MCCs send theirs (they resend every second).
    // The controls are set before dsp.init(), which starts from them.
    for (uint8_t i = 0; i < 8; i++) {
        lc::apply(dsp, lc::RECORDED_CCS[i], lc::SEED_CC[i]);
    }
    dsp.setRouting(Cpx4Dsp::ROUTING_PAIRS);
    dsp.setResonanceStep(0);
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        dsp.setTune(k, 0.5f);
    }
    dsp.init(audioManager->getDac()->getSampleRate(), cpx4Lines[0], cpx4Lines[1],
             CPX4_DELAY_LINE_SAMPLES);
    // The first readKnobs() (main loop, after the audio core set up ADC0 /
    // ADC1) sets the four TUNEs.
    knobsFirstRead = true;

    // The recorder is volatile (RAM only). Seed the MCC snapshot with the
    // power-on values, so a take that doesn't move a CC replays this sound.
    recorder.setLedCallback(&Cpx4App::setRecorderLed);
    recorder.begin(nowMs());
    recorder.clearCurrentCcs();
    for (uint8_t i = 0; i < 8; i++) {
        recorder.setCurrentCc(lc::RECORDED_CCS[i], lc::SEED_CC[i]);
    }
}

__attribute__((hot))
void Cpx4App::audioCallback(AudioInput *input, AudioOutput *output) {
    (void)input;
    dsp.process(output->left, output->right);
}

void Cpx4App::update() {
    readKnobs();
    recorder.update(nowMs(), knobCounts, &Cpx4App::applyRecorded, this);
}

// Milliseconds from the 64-bit timer: wraps at 2^32 ms (49 days), as the
// recorder's arithmetic expects (time_us_32() / 1000 jumps back after 71 min).
uint32_t Cpx4App::nowMs() {
    return (uint32_t)(time_us_64() / 1000);
}

// P1..P4 = ADC0..3, read every 2 ms under the ADC lock IO uses, four
// conversions averaged, then smoothed. A TUNE is set once its knob moves by
// CPX4_KNOB_APPLY_STEP counts. A knob with a track (recording, playing or
// gliding back) belongs to the recorder; it's still tracked for the
// recorder, in whole counts with the same hysteresis, so a resting knob
// can't flicker by a count in a take or its offset.
void Cpx4App::readKnobs() {
    uint32_t now = nowMs();
    if (!knobsFirstRead && (now - lastKnobReadMs) < CPX4_KNOB_READ_INTERVAL_MS) {
        return;
    }
    lastKnobReadMs = now;

    uint32_t sum[MotionRecorder::KNOB_COUNT] = {};
    audioManager->startAdcLock();
    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        adc_select_input(k);
        for (uint8_t i = 0; i < CPX4_KNOB_OVERSAMPLE; i++) {
            sum[k] += adc_read();
        }
    }
    audioManager->endAdcLock();

    for (uint8_t k = 0; k < MotionRecorder::KNOB_COUNT; k++) {
        float raw = sum[k] / (float)CPX4_KNOB_OVERSAMPLE;
        if (knobsFirstRead) {
            knobSmooth[k] = raw;
        } else {
            knobSmooth[k] += CPX4_KNOB_SMOOTH * (raw - knobSmooth[k]);
        }
        if (knobsFirstRead || fabsf(knobSmooth[k] - knobCounts[k]) > CPX4_KNOB_APPLY_STEP) {
            knobCounts[k] = (uint16_t)(knobSmooth[k] + 0.5f);
        }
        if (recorder.ownsKnob(k)) {
            continue;
        }
        if (knobsFirstRead || fabsf(knobSmooth[k] - knobApplied[k]) > CPX4_KNOB_APPLY_STEP) {
            applyKnob(k, knobSmooth[k]);
        }
    }
    knobsFirstRead = false;
}

void Cpx4App::applyKnob(uint8_t knob, float adc) {
    knobApplied[knob] = adc;
    dsp.setTune(knob, lc::knobToTune(knob, adc));
}

// Any channel: a note sets PITCH (velocity 0 is a note-off).
__attribute__((cold, noinline))
void Cpx4App::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    if (velocity > 0) {
        dsp.setTransposeNote(note);
    }
}

void Cpx4App::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    (void)channel;
    (void)note;
    (void)velocity;
}

__attribute__((cold, noinline))
void Cpx4App::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    (void)channel;
    // A CC with a track belongs to the recorder: keep its latest value for
    // it (re-record, offset), don't apply it.
    if (recorder.ownsCc(cc)) {
        recorder.setCurrentCc(cc, value);
        return;
    }
    if (lc::apply(dsp, cc, value)) {
        recorder.setCurrentCc(cc, value);  // ignored for the button CCs
    }
}

void Cpx4App::bpmChangeCallback(int bpm) {
    (void)bpm;
}

// No MIDI timing: the recorder runs on its own clock (update()).
void Cpx4App::realtimeCallback(uint8_t realtimeType) {
    (void)realtimeType;
}

// P3 / P4 are read in readKnobs(), not through IO's callbacks.
void Cpx4App::cv1UpdateCallback(uint16_t cv1) {
    (void)cv1;
}

void Cpx4App::cv2UpdateCallback(uint16_t cv2) {
    (void)cv2;
}

// Removing the tracks needs nothing here: the recorder glides each control
// from its track to the knob or the MCC value last received
// (applyRecorded()).
__attribute__((cold, noinline))
void Cpx4App::buttonPressedCallback(bool pressed) {
    recorder.buttonChanged(pressed, nowMs());
}

void Cpx4App::setRecorderLed(bool on) {
    IO::getInstance()->setLED(on);
}

// One recorder-owned control: P1..P4, then the MCC slots (Bank A, Bank B).
void Cpx4App::applyRecorded(void* context, uint8_t param, uint16_t value) {
    Cpx4App* self = static_cast<Cpx4App*>(context);
    if (self == nullptr) {
        return;
    }
    if (param < MotionRecorder::KNOB_COUNT) {
        self->applyKnob(param, value);
        return;
    }
    const uint8_t slot = param - MotionRecorder::KNOB_COUNT;
    if (slot < 8) {
        lc::apply(self->dsp, lc::RECORDED_CCS[slot], (uint8_t)value);
    }
}

// get-cpx4-params: the live DSP state over serial (bench checks).
bool Cpx4App::onCommandCallback(const char* cmd) {
    if (strncmp(cmd, "get-cpx4-params", 16) == 0) {
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

Cpx4App* Cpx4App::getInstance() {
    if (!instance) {
        instance = new Cpx4App();
    }
    return instance;
}
