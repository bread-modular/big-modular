#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "MIDI.h"
#include "tones.h"
#include "utils.h"
#include "EnvelopeGenerator.h"
#include "EnvHoldRelease.h"
#include "EnvAttackRelease.h"
#include "EnvAttackSustainRelease.h"
#include "ToggleMode.h"
#include "CvRecorder.h"

// ----------------------------------------------------------------------------
// ACID — Bread Modular MCO + ENV on one ATtiny1616 (../../docs/research.md 3).
//
//   * MCO (BM 1.0.1, as modules/low): MIDI note-on sets tone 1 (PB4) and the
//     detuned tone 2 (PB5); DETUNE (PB0) puts tone 2 0..12 semitones below.
//   * ENV (BM 1.2.1): MIDI note on/off is the gate of the envelope on the DAC
//     (PA6 -> ENV_CV: SVF CV normal and ENV OUT). ATTACK (PA1, hold in HR) and
//     RELEASE (PA2) set the times, plus MIDI CC22 / CC75 as BM. MODE (PC0,
//     a click) cycles HR / AR / ASR, stored in EEPROM; the selected model's
//     LED (PC1 / PA4 / PA5) follows the envelope: its brightness tracks the
//     envelope level, up to 10 %; after power-up or a MODE change it is lit
//     at 10 % for 1 s to show the selection.
//   * REC (PC2 / LED PC3): 4-bar ATTACK/RELEASE motion recorder on MIDI clock
//     (shared lib/CvRecorder, as the 8bit crash): click to record (LED blinks),
//     after 4 bars it loops (LED solid), click again for the live knobs.
// ----------------------------------------------------------------------------

// JP1 on the ACID carrier picks the MIDI input path (set by ../../jumper.sh):
//   P (protected) = 8bit / MIDI V2 NPN front end, which inverts the UART data -> 1
//   D (direct)    = jack tip straight to PB3, as Bread Modular             -> 0
#ifndef MIDI_RX_INVERT
#error "MIDI_RX_INVERT must be set: build with ../../compile.sh p|d"
#endif

#define DETUNE_INPUT_PIN PIN_PB0
#define PIN_CV1          PIN_PA1   // ATTACK knob (hold time in HR)
#define PIN_CV2          PIN_PA2   // RELEASE knob
#define MODE_BUTTON_PIN  PIN_PC0   // envelope model (BM ENV algo button)
#define LED_HR           PIN_PC1
#define LED_AR           PIN_PA4
#define LED_ASR          PIN_PA5
#define REC_BUTTON_PIN   PIN_PC2   // BM ENV gate-mode button
#define REC_LED_PIN      PIN_PC3

#define ALGO_HOLD_RELEASE 0
#define ALGO_ATTACK_RELEASE 1
#define ALGO_ATTACK_SUSTAIN_RELEASE 2

#define MODE_SHOW_MS 1000          // selected LED lit after power-up / MODE
#define LED_MIN_FLASH_MS 30        // shortest visible LED flash per trigger
#define KNOB_READ_MS 2             // knob reads off the envelope's hot loop

// MODE LED brightness: TCA0 in split mode (TCB0/TCB1 are the tones, TCD0 is
// millis), 20 MHz / 256 / 256 = 305 Hz, duty = count / 256. PA4 (WO4, HCMP1)
// and PA5 (WO5, HCMP2) are hardware PWM. PC1 has no TCA output, so the low
// counter switches it in software (LCMP0 on, LUNF off); those two interrupts
// run only while the HR LED is lit.
#define LED_MAX_PERCENT 10         // brightness at full envelope level
constexpr uint8_t LED_PWM_PER = 255;
constexpr uint8_t LED_MAX_DUTY = (256 * LED_MAX_PERCENT + 50) / 100;  // 26

MIDI_CREATE_INSTANCE(HardwareSerial, Serial, MIDI);

EnvHoldRelease envHoldRelease;
EnvAttackRelease envAttackRelease;
EnvAttackSustainRelease envAttackSustainRelease;
EnvelopeGenerator *envelope;

ToggleMode algoMode(MODE_BUTTON_PIN, 1, 3);        // EEPROM index 1, as BM
CvRecorder recorder(REC_BUTTON_PIN, REC_LED_PIN);

const uint8_t modeLeds[3] = {LED_HR, LED_AR, LED_ASR};

float detunedSemitones = 0;
uint16_t liveCV1 = 0;              // ATTACK / RELEASE knobs (recorder input)
uint16_t liveCV2 = 0;
uint16_t playCV1 = 0;              // recorded take (PLAYBACK)
uint16_t playCV2 = 0;
int modCV1 = 0;                    // MIDI CC22 (attack / hold time)
int modCV2 = 0;                    // MIDI CC75 (release time)

bool midiGate = false;
byte gateNote = 0;                 // note that holds the gate
byte selectedLed = 0;              // index into modeLeds
unsigned long modeShownAt = 0;     // millis() of the last selection change

void handleAlgoModeChange(byte newMode) {
  if (newMode == ALGO_HOLD_RELEASE) {
    envelope = &envHoldRelease;
  } else if (newMode == ALGO_ATTACK_RELEASE) {
    envelope = &envAttackRelease;
  } else {
    envelope = &envAttackSustainRelease;
  }

  selectedLed = newMode;
  modeShownAt = millis();
}

void setupLedPwm() {
  takeOverTCA0();                      // megaTinyCore: TCA0 off analogWrite
  TCA0.SPLIT.CTRLD = TCA_SPLIT_SPLITM_bm;
  TCA0.SPLIT.LPER = LED_PWM_PER;
  TCA0.SPLIT.HPER = LED_PWM_PER;
  TCA0.SPLIT.CTRLB = 0;                // outputs off until a LED is lit
  TCA0.SPLIT.INTCTRL = 0;
  TCA0.SPLIT.CTRLA = TCA_SPLIT_CLKSEL_DIV256_gc | TCA_SPLIT_ENABLE_bm;
}

// PC1 (HR) software PWM: the down-counting low counter matches LCMP0 =
// duty - 1, so PC1 is high for duty counts until the underflow.
ISR(TCA0_LCMP0_vect) {
  PORTC.OUTSET = PIN1_bm;
  TCA0.SPLIT.INTFLAGS = TCA_SPLIT_LCMP0_bm;
}

ISR(TCA0_LUNF_vect) {
  PORTC.OUTCLR = PIN1_bm;
  TCA0.SPLIT.INTFLAGS = TCA_SPLIT_LUNF_bm;
}

// Lights MODE LED `led` at `duty` / 256 (0 = all LEDs off).
void setLedDuty(byte led, uint8_t duty) {
  TCA0.SPLIT.HCMP1 = duty;
  TCA0.SPLIT.HCMP2 = duty;
  TCA0.SPLIT.LCMP0 = duty ? duty - 1 : 0;

  uint8_t outputs = 0;
  if (duty && led == 1) {
    outputs = TCA_SPLIT_HCMP1EN_bm;    // PA4 (AR)
  } else if (duty && led == 2) {
    outputs = TCA_SPLIT_HCMP2EN_bm;    // PA5 (ASR)
  }
  TCA0.SPLIT.CTRLB = outputs;

  const bool soft = duty && led == 0;  // PC1 (HR)
  TCA0.SPLIT.INTCTRL = soft ? TCA_SPLIT_LUNF_bm | TCA_SPLIT_LCMP0_bm : 0;
  if (!soft) {
    PORTC.OUTCLR = PIN1_bm;
  }
}

// The selected model's LED follows the envelope: its brightness tracks the
// level (any non-zero level lights it, so the release tail shows), except for
// MODE_SHOW_MS after a selection change, when it stays at full brightness.
// For LED_MIN_FLASH_MS after each trigger it shows the peak level so far, so
// a short HR pulse (1 ms at knobs 0) still gives a visible flash.
void updateModeLed() {
  static byte lastLed = 0xff;
  static uint8_t lastDuty = 0xff;
  static unsigned long flashAt = 0;
  static uint8_t flashPeak = 0;
  static bool wasLit = false;

  const unsigned long now = millis();
  const uint8_t envLevel = envelope->getLevel();
  if (envLevel && !wasLit) {
    flashAt = now;
    flashPeak = 0;
  }
  wasLit = envLevel != 0;
  const bool flashing = now - flashAt < LED_MIN_FLASH_MS;
  if (flashing && envLevel > flashPeak) flashPeak = envLevel;

  const bool showing = now - modeShownAt < MODE_SHOW_MS;
  const uint8_t level = showing ? 255
                      : (flashing && flashPeak > envLevel) ? flashPeak
                      : envLevel;
  const uint8_t duty = level ? ((uint16_t)level * LED_MAX_DUTY + 254) / 255 : 0;
  if (duty != lastDuty || selectedLed != lastLed) {
    setLedDuty(selectedLed, duty);
    lastDuty = duty;
    lastLed = selectedLed;
  }
}

void handleNoteOn(byte channel, byte note, byte velocity) {
  const int freq = midiToFrequency(note);
  setTone1Frequency(freq);

  const int detunedFreq = midiToFrequency(note - detunedSemitones);
  setTone2Frequency(detunedFreq);

  midiGate = true;
  gateNote = note;
}

void handleNoteOff(byte channel, byte note, byte velocity) {
  // Only the latest note closes the gate: an overlapping (legato) note keeps
  // the envelope open instead of releasing it under the held note.
  if (note == gateNote) {
    midiGate = false;
  }
}

void handleControlChange(byte channel, byte number, byte value) {
  if (number == 22) {
    modCV1 = value;
  } else if (number == 75) {
    modCV2 = value;
  }
}

void applyRecorded(uint16_t cv1, uint16_t cv2) {
  playCV1 = cv1;
  playCV2 = cv2;
}

void handleClock() {
  if (recorder.isRecording()) {
    applyRecorded(liveCV1, liveCV2);   // the take starts where it was played
  }
  recorder.onClock(liveCV1, liveCV2, applyRecorded);
}

void handleStart() {
  recorder.onStart();
}

void readKnobs() {
  liveCV1 = analogRead(PIN_CV1);
  liveCV2 = analogRead(PIN_CV2);
  detunedSemitones = (analogRead(DETUNE_INPUT_PIN) / 1023.0) * 12;
}

// Knob (or recorded take) plus the MIDI CC offset, 0..1023.
int effectiveCV(uint16_t knob, int mod) {
  return constrain((int)knob + (int)map(mod, 0, 127, 0, 1023), 0, 1023);
}

void setup() {
  // Setup tones
  setupTone1();
  setupTone2();

  // Setup Serial Comm
  Serial.begin(31250);

  // Initialize the MIDI library
  // Listen to only the channel 1
  MIDI.begin(1);
#if MIDI_RX_INVERT
  // JP1 = P: the NPN input stage inverts the MIDI UART data, so invert
  // PB3 (RX) in the port before the USART samples it.
  PORTB.PIN3CTRL |= PORT_INVEN_bm;
#endif
  MIDI.setHandleNoteOn(handleNoteOn);
  MIDI.setHandleNoteOff(handleNoteOff);
  MIDI.setHandleControlChange(handleControlChange);
  MIDI.setHandleClock(handleClock);
  MIDI.setHandleStart(handleStart);
  Serial.println("ACID Started!");

  setTone1Frequency(20);
  setTone2Frequency(20);

  // Set the analog reference for ADC with supply voltage.
  analogReference(VDD);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);
  (void)analogRead(PIN_CV1);       // throwaway warm-up read
  readKnobs();

  // DAC0 setup for the envelope via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;

  // Envelope model selector (MODE + three LEDs)
  for (byte i = 0; i < 3; i++) {
    pinMode(modeLeds[i], OUTPUT);
    digitalWrite(modeLeds[i], LOW);
  }
  algoMode.begin();
  algoMode.registerModeChangeCallback(handleAlgoModeChange);
  handleAlgoModeChange(algoMode.getMode());
  setupLedPwm();

  // ATTACK / RELEASE motion recorder (REC + LED)
  recorder.begin();
}

void loop() {
  // parse incoming MIDI messages
  MIDI.read();

  algoMode.update();
  recorder.update();

  static unsigned long lastKnobRead = 0;
  if (millis() - lastKnobRead >= KNOB_READ_MS) {
    lastKnobRead = millis();
    readKnobs();
  }

  // In PLAYBACK the recorded take (shifted by the knobs after its first
  // pass, inside CvRecorder) sets the times; otherwise the knobs do.
  const bool playing = recorder.isPlayingBack();
  const int cv1 = effectiveCV(playing ? playCV1 : liveCV1, modCV1);
  const int cv2 = effectiveCV(playing ? playCV2 : liveCV2, modCV2);

  envelope->update(midiGate, cv1, cv2);
  updateModeLed();
}
