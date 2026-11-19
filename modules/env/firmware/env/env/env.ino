#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "MIDI.h"
#include "EnvelopeGenerator.h"
#include "EnvHoldRelease.h"
#include "EnvAttackRelease.h"
#include "EnvAttackSustainRelease.h"
#include "ToggleMode.h"
#include "CvRecorder.h"

// ----------------------------------------------------------------------------
// ENV — Bread Modular ENV on one ATtiny1616 at 5 V (../../../docs/research.md
// 2 and 6). The ACID envelope (modules/acid/firmware) without the MCO, plus
// GATE IN:
//
//   * Gate: MIDI note on/off (channel 1), or GATE IN when a cable is patched
//     (PB1 jack detect high): then MIDI notes are bypassed and the jack gate
//     (PB2, inverted by Q2) drives the envelope.
//   * Envelope (BM ENV 1.2.1) on the DAC (PA6 -> TL072 x1.51 -> ENV OUT
//     0..5 V). ATTACK (PA1, hold in HR) and RELEASE (PA2) set the times, plus
//     MIDI CC22 / CC75 as BM. MODE (PC0, a click) cycles HR / AR / ASR, stored
//     in EEPROM; the selected model's LED (PC1 / PA4 / PA5) stays lit at
//     10 % (the ENV LED at the jack shows the envelope level).
//   * REC (PC2 / LED PC3): 4-bar ATTACK/RELEASE motion recorder on MIDI clock
//     (shared lib/CvRecorder, as ACID): click to record (LED blinks), after
//     4 bars it loops (LED solid), hold REC + turn a knob to overdub it,
//     click again for the live knobs.
//
// The USART runs receive-only: its TX pin PB2 is GATE IN on this board.
// ----------------------------------------------------------------------------

// JP1 on the ENV carrier picks the MIDI input path (set by ../../jumper.sh):
//   P (protected) = NPN front end (Q1), which inverts the UART data -> 1
//   D (direct)    = jack tip straight to PB3, 5 V logic senders only -> 0
#ifndef MIDI_RX_INVERT
#error "MIDI_RX_INVERT must be set: build with ../../compile.sh p|d"
#endif

#define PIN_CV1          PIN_PA1   // ATTACK knob (hold time in HR)
#define PIN_CV2          PIN_PA2   // RELEASE knob
#define MODE_BUTTON_PIN  PIN_PC0   // envelope model (BM ENV algo button)
#define LED_HR           PIN_PC1
#define LED_AR           PIN_PA4
#define LED_ASR          PIN_PA5
#define REC_BUTTON_PIN   PIN_PC2
#define REC_LED_PIN      PIN_PC3
#define GATE_IN_PIN      PIN_PB2   // Q2 collector: LOW = gate high at the jack
#define GATE_SENSE_PIN   PIN_PB1   // HIGH = GATE IN patched (TN open)

#define ALGO_HOLD_RELEASE 0
#define ALGO_ATTACK_RELEASE 1
#define ALGO_ATTACK_SUSTAIN_RELEASE 2

#define KNOB_READ_MS 2             // knob reads off the envelope's hot loop
#define GATE_SENSE_MS 20           // jack detect must hold this long to switch

// MODE LED brightness: TCA0 in split mode (TCD0 is millis), 20 MHz / 256 /
// 256 = 305 Hz, duty = count / 256. PA4 (WO4, HCMP1) and PA5 (WO5, HCMP2)
// are hardware PWM. PC1 has no TCA output, so the low counter switches it in
// software (LCMP0 on, LUNF off); those two interrupts run only while the HR
// LED is lit.
#define LED_PERCENT 10             // brightness of the selected MODE LED
constexpr uint8_t LED_PWM_PER = 255;
constexpr uint8_t LED_DUTY = (256 * LED_PERCENT + 50) / 100;  // 26

MIDI_CREATE_INSTANCE(HardwareSerial, Serial, MIDI);

EnvHoldRelease envHoldRelease;
EnvAttackRelease envAttackRelease;
EnvAttackSustainRelease envAttackSustainRelease;
EnvelopeGenerator *envelope;

ToggleMode algoMode(MODE_BUTTON_PIN, 1, 3);        // EEPROM index 1, as BM
CvRecorder recorder(REC_BUTTON_PIN, REC_LED_PIN);

const uint8_t modeLeds[3] = {LED_HR, LED_AR, LED_ASR};

uint16_t liveCV1 = 0;              // ATTACK / RELEASE knobs (recorder input)
uint16_t liveCV2 = 0;
uint16_t playCV1 = 0;              // recorded take (PLAYBACK)
uint16_t playCV2 = 0;
int modCV1 = 0;                    // MIDI CC22 (attack / hold time)
int modCV2 = 0;                    // MIDI CC75 (release time)

bool midiGate = false;
byte gateNote = 0;                 // note that holds the gate
bool gatePatched = false;          // debounced PB1 jack detect
byte selectedLed = 0;              // index into modeLeds

void handleAlgoModeChange(byte newMode) {
  if (newMode == ALGO_HOLD_RELEASE) {
    envelope = &envHoldRelease;
  } else if (newMode == ALGO_ATTACK_RELEASE) {
    envelope = &envAttackRelease;
  } else {
    envelope = &envAttackSustainRelease;
  }

  selectedLed = newMode;
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

// The selected model's LED stays lit at LED_PERCENT (the ENV LED at the
// jack shows the envelope level).
void updateModeLed() {
  static byte lastLed = 0xff;

  if (selectedLed != lastLed) {
    setLedDuty(selectedLed, LED_DUTY);
    lastLed = selectedLed;
  }
}

void handleNoteOn(byte channel, byte note, byte velocity) {
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
}

// PB1 jack detect, debounced: the TN contact opens / closes while a plug
// slides in, so the new state must hold GATE_SENSE_MS before it switches.
void updateGateSense() {
  static bool lastRaw = false;
  static unsigned long changedAt = 0;

  const bool raw = VPORTB.IN & PIN1_bm;
  const unsigned long now = millis();
  if (raw != lastRaw) {
    lastRaw = raw;
    changedAt = now;
  } else if (raw != gatePatched && now - changedAt >= GATE_SENSE_MS) {
    gatePatched = raw;
  }
}

// Envelope gate: GATE IN when patched (MIDI notes bypassed), else MIDI.
bool currentGate() {
  if (gatePatched) {
    return !(VPORTB.IN & PIN2_bm);     // Q2 inverts: PB2 low = gate high
  }
  return midiGate;
}

// Knob (or recorded take) plus the MIDI CC offset, 0..1023.
int effectiveCV(uint16_t knob, int mod) {
  return constrain((int)knob + (int)map(mod, 0, 127, 0, 1023), 0, 1023);
}

void setup() {
  // Unused pins (no-connect on the carrier): pulled up, not floating.
  pinMode(PIN_PA3, INPUT_PULLUP);
  pinMode(PIN_PA7, INPUT_PULLUP);
  pinMode(PIN_PB0, INPUT_PULLUP);
  pinMode(PIN_PB4, INPUT_PULLUP);
  pinMode(PIN_PB5, INPUT_PULLUP);

  // GATE IN: R17 22k pull-up and R19 1M jack-detect pull-up on the board.
  pinMode(GATE_IN_PIN, INPUT);
  pinMode(GATE_SENSE_PIN, INPUT);
  gatePatched = VPORTB.IN & PIN1_bm;

  // MIDI, receive only (serialMIDI.h): listen to channel 1 only.
  MIDI.begin(1);
  MIDI.turnThruOff();
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

  // Knobs span VDD, so VDD is the ADC reference.
  analogReference(VDD);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);
  (void)analogRead(PIN_CV1);       // throwaway warm-up read
  readKnobs();

  // DAC0 on PA6 with the internal 4.34 V reference (needs VDD >= 4.75 V,
  // research.md 6); EnvelopeGenerator scales the envelope to 0..194.
  VREF.CTRLA = (VREF.CTRLA & ~VREF_DAC0REFSEL_gm) | VREF_DAC0REFSEL_4V34_gc;
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.DATA = 0;
  EnvelopeGenerator::envDacPin(false);  // idle: PA6 held at 0 V

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
  updateGateSense();

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

  envelope->update(currentGate(), cv1, cv2);
  updateModeLed();
}
