// Implementation split from header; mark realtime hot
#include "audio/apps/polysynth_app.h"

PolySynthApp* PolySynthApp::instance = nullptr;

namespace {
// Filter power-on values (poly_filter.h), also used to seed the recorder's
// MCC snapshot, so a take recorded without touching a knob plays back the
// startup sound:
//   CC20 -> env attack = release, 5 ms * 400^v: CC 15 = 10 ms (BM 10 ms)
//   CC21 -> env depth, v * 8.3 octaves: CC 127 = wide open while held (BM
//          +10 kHz)
//   CC22 -> resonance k = 4.1 v: CC 27 = 0.87
//   CC23 -> cutoff, inverted: CC 0 = 17.6 kHz (open)
constexpr uint8_t SEED_CC_ENV_TIME = 15;
constexpr uint8_t SEED_CC_MOD_DEPTH = 127;
constexpr uint8_t SEED_CC_RESONANCE = 27;
constexpr uint8_t SEED_CC_CUTOFF = 0;

// RAM copies of the selected wavetable (2 x 68 KB): P1 fills the idle one,
// then the oscillators switch to it. The tables themselves stay in flash.
int16_t wavetableRam[2][WAVETABLE_TABLE_SAMPLES];
uint8_t wavetableRamActive = 0;
}  // namespace


void PolySynthApp::init() {
    audioManager->setAdcEnabled(false);

    // Every voice plays a wavetable (P1 table 0 = Classic: square / saw / tri /
    // sine); the shared control must be set before Voice::init() inits it.
    for (int i = 0; i < TOTAL_VOICES; i++) {
        wavetableGenerators[i].setControl(&wavetableControl);
        wavetableGenerators[i].init(audioManager);
    }
    wavetableControl.init(audioManager->getDac()->getSampleRate());

    for (int i = 0; i < TOTAL_VOICES; i++) {
        Voice* oldVoice = voices[i];
        voices[i] = new Voice(
            1, // total generators
            (AudioGenerator*[]){ &wavetableGenerators[i] }, // generators
            new AttackHoldReleaseEnvelope(10.0f, 500.0f), // amp envelope
            new AttackHoldReleaseEnvelope(10.0f, 500.0f) // filter envelope
        );
        voices[i]->init(audioManager); // init voice

        if (oldVoice != nullptr) {
            delete oldVoice->getAmpEnvelope();
            delete oldVoice->getFilterEnvelope();
            delete oldVoice;
        }
    }

    applyCc(0, SEED_CC_ENV_TIME);
    applyCc(1, SEED_CC_MOD_DEPTH);
    applyCc(2, SEED_CC_RESONANCE);
    applyCc(3, SEED_CC_CUTOFF);
    filter.init(audioManager->getDac()->getSampleRate());
    outputLevel.init(audioManager->getDac()->getSampleRate());

    // The voices start on Classic; the first readTopKnobs() picks the P1
    // table and the P2 position.
    wavetableZone = 0;
    loadWavetable(0);
    wavetableControl.noise = false;
    wavetableControl.tick();
    topKnobsFirstRead = true;

    // The motion recorder is intentionally volatile (RAM only, never FS/flash).
    // Seed the MCC snapshot with the FX power-on values above so a take that
    // does not touch a knob still loops back the sound it was recorded with.
    recorder.setLedCallback(&PolySynthApp::setRecorderLed);
    recorder.begin(time_us_32() / 1000);
    recorder.setCurrentCc(20, SEED_CC_ENV_TIME);
    recorder.setCurrentCc(21, SEED_CC_MOD_DEPTH);
    recorder.setCurrentCc(22, SEED_CC_RESONANCE);
    recorder.setCurrentCc(23, SEED_CC_CUTOFF);
}

__attribute__((hot))
void PolySynthApp::audioCallback(AudioInput *input, AudioOutput *output) {
    wavetableControl.tick();  // shared by the voices' wavetables
    float sumVoice = 0.0f;
    float level = 0.0f;
    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (voices[i] != nullptr) {
            sumVoice += voices[i]->process();
            level += voices[i]->getLevel();
        }
    }

    // Auto level (poly_level.h) instead of BM's fixed sum / 4: one voice at
    // 0.8, chords turned down by the number of sounding notes, then a limiter.
    float dry = sumVoice * outputLevel.gain(level);
    float voiceWithFx = filter.process(dry * PolyLevel::LADDER_DRIVE) / PolyLevel::LADDER_DRIVE;
    outputLevel.limit(voiceWithFx, dry);

    output->left = voiceWithFx;
    output->right = dry;
}

void PolySynthApp::update() {
    readTopKnobs();
    recorder.update(time_us_32() / 1000);
}

__attribute__((cold, noinline))
void PolySynthApp::noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    float velocityNorm = velocity / 127.0f;
    float realVelocity = powf(velocityNorm, 2.0f);

    if (++totalNotesOn == 1) {
        filter.setGate(true);
        io->setGate1(true);
    }

    Voice* voice = findFreeVoice();
    if (voice == nullptr) {
        return;
    }

    uint8_t generatorNotes[] = { static_cast<uint8_t>(note) };
    voice->setNoteOn(realVelocity, note, generatorNotes);
}

__attribute__((cold, noinline))
void PolySynthApp::noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
    if (totalNotesOn > 0) --totalNotesOn;
    if (totalNotesOn == 0) {
        filter.setGate(false);
        io->setGate1(false);
    }

    for (int i = 0; i < TOTAL_VOICES; i++) {
        if (voices[i]->getCurrentNote() == note) {
            voices[i]->setNoteOff(note);
        }
    }
}

__attribute__((cold, noinline))
void PolySynthApp::ccChangeCallback(uint8_t channel, uint8_t cc, uint8_t value) {
    // One set of filter parameters: Banks B (CC27..30) and C (CC85..88) are
    // folded onto Bank A (CC20..23), so any MCC bank page drives the filter,
    // and the recorder sees them as Bank A.
    int parameter = PolyFilter::bankAParameter(cc);
    if (parameter < 0) {
        return;
    }
    cc = MotionRecorder::MCC_BANK_A_FIRST_CC + parameter;

    // During playback a recorded CC is owned by the loop: keep its latest
    // value (the recorder turns moves into an offset) but don't apply it. In
    // live and recording modes apply the CC immediately and retain its latest
    // value so every clock frame gets a complete Bank A snapshot.
    if (!recorder.ownsCc(cc)) {
        applyCc(parameter, value);
    }
    recorder.setCurrentCc(cc, value);
}

void PolySynthApp::applyCc(uint8_t parameter, uint8_t value) {
    filter.setParameter(parameter, value / 127.0f);
}

void PolySynthApp::bpmChangeCallback(int bpm) {}

void PolySynthApp::realtimeCallback(uint8_t realtimeType) {
    switch (realtimeType) {
        case MIDI_REALTIME_CLOCK:
        {
            uint16_t knobs[MotionRecorder::KNOB_COUNT];
            readKnobs(knobs);
            recorder.onClock(knobs, &PolySynthApp::applyRecordedFrame, this);
            break;
        }
        case MIDI_REALTIME_START:
            recorder.onStart();
            break;
        default:
            // STOP/CONTINUE do not destroy or advance the take. With no clock
            // pulses the playhead naturally holds.
            break;
    }
}

__attribute__((cold, noinline))
void PolySynthApp::cv1UpdateCallback(uint16_t cv1) {
    if (!recorder.isPlayingBack()) {
        applyLiveCv(cv1, io->getCV2());
    }
}

__attribute__((cold, noinline))
void PolySynthApp::cv2UpdateCallback(uint16_t cv2) {
    if (!recorder.isPlayingBack()) {
        applyLiveCv(io->getCV1(), cv2);
    }
}

__attribute__((cold, noinline))
void PolySynthApp::buttonPressedCallback(bool pressed) {
    const MotionRecorder::State before = recorder.getState();
    const uint32_t nowMs = time_us_32() / 1000;
    recorder.buttonChanged(pressed, nowMs);

    // IO can keep sampling knobs while a loop plays, but their callbacks are
    // intentionally ignored. Restore the current live controls when MODE leaves
    // playback so LIVE really is live again.
    if (pressed && before == MotionRecorder::STATE_PLAYBACK &&
        recorder.isLive()) {
        applyLiveCv(io->getCV1(), io->getCV2());
        applyP1(p1Value);
        applyP2(p2Value);
        for (uint8_t i = 0; i < MotionRecorder::MCC_BANK_A_COUNT; i++) {
            applyCc(i, recorder.getCurrentCc(MotionRecorder::MCC_BANK_A_FIRST_CC + i));
        }
    }
}

void PolySynthApp::setRecorderLed(bool on) {
    IO::getInstance()->setLED(on);
}

void PolySynthApp::applyLiveCv(uint16_t cv1, uint16_t cv2) {
    // CV1 -> attack time (1..500 ms), CV2 -> release time (10..1000 ms).
    float holdTime = MAX(1, IO::normalizeCV(cv1) * 500);
    float releaseTime = MAX(10, IO::normalizeCV(cv2) * 1000);
    for (int i = 0; i < TOTAL_VOICES; i++) {
        voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::ATTACK, holdTime);
        voices[i]->getAmpEnvelope()->setTime(AttackHoldReleaseEnvelope::RELEASE, releaseTime);
    }
}

float PolySynthApp::topKnobNormalize(uint16_t value) {
    float norm = (value - (float)TOP_KNOB_ADC_ZERO) / (float)(TOP_KNOB_ADC_FULL - TOP_KNOB_ADC_ZERO);
    return std::clamp(norm, 0.0f, 1.0f);
}

// The audio core leaves ADC0 / ADC1 alone here (setAdcEnabled(false)), so
// read P1 / P2 from the main loop, under the same lock IO uses. During
// playback the loop owns them; keep tracking them for the knob offset.
void PolySynthApp::readTopKnobs() {
    uint32_t now = time_us_32() / 1000;
    if (!topKnobsFirstRead && (now - lastTopKnobsReadMs) < TOP_KNOB_READ_INTERVAL_MS) {
        return;
    }
    lastTopKnobsReadMs = now;

    audioManager->startAdcLock();
    adc_select_input(A0);
    uint16_t newP1 = adc_read();
    adc_select_input(A1);
    uint16_t newP2 = adc_read();
    audioManager->endAdcLock();

    if (topKnobsFirstRead || abs(p1Value - newP1) > TOP_KNOB_ADC_DIFF_THRESHOLD) {
        p1Value = newP1;
        if (!recorder.isPlayingBack()) {
            applyP1(p1Value);
        }
    }
    if (topKnobsFirstRead || abs(p2Value - newP2) > TOP_KNOB_ADC_DIFF_THRESHOLD) {
        p2Value = newP2;
        if (!recorder.isPlayingBack()) {
            applyP2(p2Value);
        }
    }
    topKnobsFirstRead = false;
}

// P1 -> wavetable, 0 = Classic, the top step Noise (hysteresis:
// wavetableZoneFor).
void PolySynthApp::applyP1(uint16_t p1) {
    uint8_t candidate = wavetableZoneFor(topKnobNormalize(p1), wavetableZone,
                                         WAVETABLE_ZONES, WAVETABLE_ZONE_HYSTERESIS);
    if (candidate == wavetableZone) {
        return;
    }

    wavetableZone = candidate;
    if (wavetableZone == WAVETABLE_NOISE_ZONE) {
        wavetableControl.noise = true;
        return;
    }
    loadWavetable(wavetableZone);
    wavetableControl.noise = false;
}

// Copy a table from flash to the idle RAM buffer (~2 ms), then point the
// oscillators at it. The audio core is off the other buffer long before the
// next table change refills it.
void PolySynthApp::loadWavetable(uint8_t table) {
    uint8_t next = wavetableRamActive ^ 1;
    memcpy(wavetableRam[next], wavetableFrames(table), sizeof(wavetableRam[next]));
    __dmb();
    wavetableControl.frames = wavetableRam[next];
    wavetableRamActive = next;
}

// P2 -> position across the table's frames, morphed and smoothed
// (WavetableControl): on Classic a continuous square -> saw -> tri -> sine,
// on Noise brown -> pink -> white -> blue -> digital -> crackle.
void PolySynthApp::applyP2(uint16_t p2) {
    wavetableControl.position = topKnobNormalize(p2) * (WAVETABLE_FRAMES - 1);
}

void PolySynthApp::readKnobs(uint16_t knobs[MotionRecorder::KNOB_COUNT]) {
    knobs[MotionRecorder::KNOB_P1] = p1Value;
    knobs[MotionRecorder::KNOB_P2] = p2Value;
    knobs[MotionRecorder::KNOB_P3] = io->getCV1();
    knobs[MotionRecorder::KNOB_P4] = io->getCV2();
}

void PolySynthApp::applyRecordedFrame(void* context,
                                      const MotionRecorder::Frame& frame) {
    PolySynthApp* self = static_cast<PolySynthApp*>(context);
    if (self == nullptr) {
        return;
    }

    self->applyLiveCv(frame.knobs[MotionRecorder::KNOB_P3],
                      frame.knobs[MotionRecorder::KNOB_P4]);
    self->applyP1(frame.knobs[MotionRecorder::KNOB_P1]);
    self->applyP2(frame.knobs[MotionRecorder::KNOB_P2]);
    for (uint8_t i = 0; i < MotionRecorder::MCC_BANK_A_COUNT; i++) {
        if (frame.ccs[i] != MotionRecorder::CC_UNSET) {
            self->applyCc(i, frame.ccs[i]);
        }
    }
}

// No polysynth commands: the BM set-waveform / get-waveform are gone, the
// basic shapes are the Classic wavetable (P1 fully down, P2 morphs
// square -> saw -> tri -> sine).
bool PolySynthApp::onCommandCallback(const char* cmd) {
    (void)cmd;
    return false;
}

PolySynthApp* PolySynthApp::getInstance() {
    if (!instance) {
        instance = new PolySynthApp();
    }
    return instance;
}
