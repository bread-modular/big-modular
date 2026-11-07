// Implementation split from header; annotate hot/cold paths
#include "audio/apps/fxrack_app.h"

FXRackApp* FXRackApp::instance = nullptr;

AudioApp* FXRackApp::getInstance() {
    if (!instance) {
        instance = new FXRackApp();
    }
    return instance;
}

void FXRackApp::init() {
    audioManager->setAdcEnabled(true);
    psram->freeall();
    lowpassFilterA.init(audioManager);
    lowpassFilterB.init(audioManager);
    fx1->init(audioManager);
    fx2->init(audioManager);
    fx3->init(audioManager);

    config.load();
    uint8_t fx1Value = config.get(CONFIG_FX1_INDEX, CONFIG_FX_DELAY);
    uint8_t fx2Value = config.get(CONFIG_FX2_INDEX, CONFIG_FX_NOOP);
    uint8_t fx3Value = config.get(CONFIG_FX3_INDEX, CONFIG_FX_METALVERB);

    setFX(CONFIG_FX1_INDEX, fx1Value);
    setFX(CONFIG_FX2_INDEX, fx2Value);
    setFX(CONFIG_FX3_INDEX, fx3Value);

    // Every audio start (boot, set-fx) re-creates the FX at their defaults,
    // so earlier CC values no longer apply. The take is RAM only and is
    // dropped too.
    recorder.setLedCallback(&FXRackApp::setRecorderLed);
    recorder.begin(time_us_32() / 1000);
    recorder.clearCurrentCcs();
}

__attribute__((hot))
void FXRackApp::audioCallback(AudioInput *input, AudioOutput *output) {
    float sumGroupA = input->left;
    float sumGroupB = input->right;

    sumGroupA = lowpassFilterA.process(sumGroupA);
    sumGroupB = lowpassFilterB.process(sumGroupB);

    // Apply FX to group A
    sumGroupA = fx1->process(sumGroupA);
    sumGroupA = fx2->process(sumGroupA);

    // Apply FX to group B
    sumGroupB = fx3->process(sumGroupB);

    output->left = sumGroupA;
    output->right = sumGroupB;
}

__attribute__((cold, noinline))
void FXRackApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {}

__attribute__((cold, noinline))
void FXRackApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {}

__attribute__((cold, noinline))
void FXRackApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    // During playback a recorded MCC CC is owned by the loop: keep its latest
    // value (the recorder turns moves into an offset) but don't apply it. MCC
    // CCs missing from the take stay live.
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

// MCC CC -> FX parameter: Bank A CC20..23 -> FX1, Bank B CC27..30 -> FX2,
// Bank C CC85..88 -> FX3. Returns false for any other CC.
bool FXRackApp::applyFxCc(uint8_t cc, uint8_t value) {
    int index = MotionRecorder::ccIndex(cc);
    if (index < 0) {
        return false;
    }
    AudioFX* bankFx[3] = {fx1, fx2, fx3};
    bankFx[index / MotionRecorder::MCC_CCS_PER_BANK]->setParameter(
        index % MotionRecorder::MCC_CCS_PER_BANK, value / 127.0f);
    return true;
}

__attribute__((cold, noinline))
void FXRackApp::cv1UpdateCallback(uint16_t cv1) {
    if (!recorder.isPlayingBack()) {
        applyP3(cv1);
    }
}

__attribute__((cold, noinline))
void FXRackApp::cv2UpdateCallback(uint16_t cv2) {
    if (!recorder.isPlayingBack()) {
        applyP4(cv2);
    }
}

void FXRackApp::applyP3(uint16_t cv1) {
    float cv1Norm = 1.0 - IO::normalizeCV(cv1);
    float cutoff = 1000.0f * powf(20000.0f / 1000.0f, cv1Norm * cv1Norm);
    lowpassFilterA.setCutoff(cutoff);
}

void FXRackApp::applyP4(uint16_t cv2) {
    float cv2Norm = 1.0 - IO::normalizeCV(cv2);
    float cutoff = 1000.0f * powf(20000.0f / 1000.0f, cv2Norm * cv2Norm);
    lowpassFilterB.setCutoff(cutoff);
}

__attribute__((cold, noinline))
void FXRackApp::buttonPressedCallback(bool pressed) {
    const MotionRecorder::State before = recorder.getState();
    recorder.buttonChanged(pressed, time_us_32() / 1000);

    // Knob and MCC moves were only tracked while the loop played: hand the
    // filters and FX back to the live controls.
    if (!pressed && before == MotionRecorder::STATE_PLAYBACK &&
        recorder.isLive()) {
        applyLiveControls();
    }
}

// P3 / P4 are this app's knobs (BM CV1 / CV2); P1 / P2 are audio inputs.
void FXRackApp::readKnobs(uint16_t knobs[MotionRecorder::KNOB_COUNT]) {
    knobs[MotionRecorder::KNOB_P1] = 0;
    knobs[MotionRecorder::KNOB_P2] = 0;
    knobs[MotionRecorder::KNOB_P3] = io->getCV1();
    knobs[MotionRecorder::KNOB_P4] = io->getCV2();
}

void FXRackApp::applyLiveControls() {
    applyP3(io->getCV1());
    applyP4(io->getCV2());
    for (uint8_t i = 0; i < MotionRecorder::CC_COUNT; i++) {
        uint8_t cc = MotionRecorder::ccNumber(i);
        uint8_t value = recorder.getCurrentCc(cc);
        if (value != MotionRecorder::CC_UNSET) {
            applyFxCc(cc, value);
        }
    }
}

void FXRackApp::setRecorderLed(bool on) {
    IO::getInstance()->setLED(on);
}

void FXRackApp::applyRecordedFrame(void* context,
                                   const MotionRecorder::Frame& frame) {
    FXRackApp* self = static_cast<FXRackApp*>(context);
    if (self == nullptr) {
        return;
    }

    // The first frame of a loop applies everything; later frames only what
    // changed.
    bool all = !self->frameApplied;
    self->frameApplied = true;
    MotionRecorder::Frame& last = self->appliedFrame;
    if (all || frame.knobs[MotionRecorder::KNOB_P3] !=
                   last.knobs[MotionRecorder::KNOB_P3]) {
        self->applyP3(frame.knobs[MotionRecorder::KNOB_P3]);
    }
    if (all || frame.knobs[MotionRecorder::KNOB_P4] !=
                   last.knobs[MotionRecorder::KNOB_P4]) {
        self->applyP4(frame.knobs[MotionRecorder::KNOB_P4]);
    }
    for (uint8_t i = 0; i < MotionRecorder::CC_COUNT; i++) {
        if (frame.ccs[i] != MotionRecorder::CC_UNSET &&
            (all || frame.ccs[i] != last.ccs[i])) {
            self->applyFxCc(MotionRecorder::ccNumber(i), frame.ccs[i]);
        }
    }
    last = frame;
}

void FXRackApp::realtimeCallback(uint8_t realtimeType) {
    switch (realtimeType) {
        case MIDI_REALTIME_CLOCK: {
            if (!recorder.isPlayingBack()) {
                frameApplied = false;
            }
            uint16_t knobs[MotionRecorder::KNOB_COUNT];
            readKnobs(knobs);
            recorder.onClock(knobs, &FXRackApp::applyRecordedFrame, this);
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

void FXRackApp::bpmChangeCallback(int bpm) {
    currentBPM = bpm;
    fx1->setBPM(bpm);
    fx2->setBPM(bpm);
    fx3->setBPM(bpm);
}

void FXRackApp::setFX(int8_t index, int8_t value) {
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
        default:
            return;
    }

    newFx->init(audioManager);
    newFx->setBPM(currentBPM);
    AudioFX* fxToDelete = *targetFx;
    *targetFx = newFx;
    delete fxToDelete;
}

__attribute__((cold, noinline))
bool FXRackApp::onCommandCallback(const char* cmd) {
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
        } else {
            printf("No such fx found: %s\n", fxName);
            return true;
        }

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
        }
        return true;
    }

    return false;
}

void FXRackApp::update() {
    recorder.update(time_us_32() / 1000);
}

