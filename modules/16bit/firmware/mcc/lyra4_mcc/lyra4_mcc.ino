#include <Arduino.h>
#include <avr/io.h>
#include "SimpleMIDI.h"
#include "ModeHandler.h"

// MCC firmware for the 16bit lyra4 app: modules/mcc/firmware/mcc/mcc.ino with
// the bank fixed at build time and the BANK button + LEDs turned into a
// 3-step selector that sends its own CC. SimpleMIDI.h and ModeHandler.h are
// the MCC firmware's files (symlinks); ModeHandler keeps the step in EEPROM.
//
//   MCC_UNIT=1  "VOICE": knobs CC20-23 (SHARP A, SHARP B, MOD, DRIVE),
//               button CC102 = FM routing PAIRS / LOOP / TOTAL FB
//   MCC_UNIT=2  "FX":    knobs CC27-30 (DELAY TIME, FEEDBACK, DELAY MIX,
//               CUTOFF), button CC103 = RESONANCE Off / Peak / Sing
//
// The button CC sends 0 / 64 / 127 for steps 1 / 2 / 3 (LED A / B / C).

#ifndef MIDI_RX_INVERT
#error "MIDI_RX_INVERT must be set: build with ../compile.sh p|d 1|2"
#endif
#ifndef MCC_UNIT
#error "MCC_UNIT must be set: build with ../compile.sh p|d 1|2"
#endif

#if MCC_UNIT == 1
#define CC_BASE 20       // Bank A
#define BUTTON_CC 102
#elif MCC_UNIT == 2
#define CC_BASE 27       // Bank B
#define BUTTON_CC 103
#else
#error "MCC_UNIT must be 1 or 2"
#endif

#define AI_PIN PIN_PA4      // knobs 1-4 on PA4-PA7 (AI_PIN .. AI_PIN + 3), as Bread Modular

// Big Modular MCC: CV 1-4 in (8bit CV stage: -5.5..+5.5 V -> 0..1023, 0 V ~ 509)
// on their own ADC pins. Each CV adds to its knob (ADC counts, ~10.8 mV each):
// +5 V ~ +463 counts, close to half the knob travel. Unpatched (tip grounded) =
// 0 V, so the knob alone sets the CC, as Bread Modular.
const uint8_t CV_PINS[4] = {PIN_PB0, PIN_PB1, PIN_PA2, PIN_PA3};
constexpr int16_t CV_IN_ZERO = 509;      // calibrate per unit (as modules/8bit lfo)
constexpr int16_t CV_IN_DEADBAND = 3;    // counts around 0 V treated as 0 V

#define STEP_BUTTON_PIN PIN_PC0
#define STEP_1_LED_PIN PIN_PC1
#define STEP_2_LED_PIN PIN_PC2
#define STEP_3_LED_PIN PIN_PC3
#define STEPS 3
const uint8_t STEP_CC_VALUE[STEPS] = {0, 64, 127};
// A plain tap steps: the press counts on release and only has to last 20 ms
// (contact bounce). The stock MCC's 200 ms (ModeHandler default) is for BANK.
#define STEP_MIN_PRESS_MS 20

// Step LED brightness: software PWM on PC1-PC3 (no hardware PWM there).
// TCB0 ticks at 20 kHz; LED_PWM_STEPS ticks = 200 Hz PWM, LED_ON_STEPS of them on.
#define LED_PWM_STEPS 100
#define LED_ON_STEPS 1      // 1 % brightness
#define LED_PORT_MASK (PIN1_bm | PIN2_bm | PIN3_bm)
constexpr uint16_t LED_TCB_COMPARE = (F_CPU / 2) / 20000 - 1;
volatile uint8_t ledMask = 0;   // PORTC bit of the lit step LED

SimpleMIDI midi;
ModeHandler stepHandler(STEP_BUTTON_PIN, STEPS, STEP_MIN_PRESS_MS);

// Knob n + CV n offset, clamped to 0..1023, as a 0..127 CC value.
uint8_t readCc(uint8_t n) {
  int16_t offset = (int16_t)analogRead(CV_PINS[n]) - CV_IN_ZERO;
  if (offset >= -CV_IN_DEADBAND && offset <= CV_IN_DEADBAND) {
    offset = 0;
  }
  int16_t v = (int16_t)analogRead(AI_PIN + n) + offset;
  if (v < 0) {
    v = 0;
  } else if (v > 1023) {
    v = 1023;
  }
  return v / 8;
}

// Simply pipe the incoming MIDI messages to the output
void noteOnCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
  midi.sendNoteOn(channel, note, velocity);
}

void noteOffCallback(uint8_t channel, uint8_t note, uint8_t velocity) {
  midi.sendNoteOff(channel, note, velocity);
}

void controlChangeCallback(uint8_t channel, uint8_t controller, uint8_t value) {
  midi.sendControlChange(channel, controller, value);
}

void realtimeCallback(uint8_t realtimeType) {
  midi.sendRealtime(realtimeType);
}

void setupLedPwm() {
  TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc;  // 10 MHz
  TCB0.CTRLB = TCB_CNTMODE_INT_gc;     // periodic interrupt
  TCB0.CCMP = LED_TCB_COMPARE;
  TCB0.INTCTRL = TCB_CAPT_bm;
  TCB0.CTRLA |= TCB_ENABLE_bm;
}

ISR(TCB0_INT_vect) {
  static uint8_t step = 0;
  if (++step >= LED_PWM_STEPS) {
    step = 0;
  }
  if (step < LED_ON_STEPS) {
    PORTC.OUTSET = ledMask;
  } else {
    PORTC.OUTCLR = LED_PORT_MASK;
  }
  TCB0.INTFLAGS = TCB_CAPT_bm;
}

void showStep(uint8_t step) {
  PORTC.OUTCLR = LED_PORT_MASK;
  ledMask = step == 0 ? PIN1_bm : step == 1 ? PIN2_bm : step == 2 ? PIN3_bm : 0;
}

void sendStep() {
  midi.sendControlChange(1, BUTTON_CC, STEP_CC_VALUE[stepHandler.getMode()]);
}

void setup() {
  pinMode(STEP_1_LED_PIN, OUTPUT);
  pinMode(STEP_2_LED_PIN, OUTPUT);
  pinMode(STEP_3_LED_PIN, OUTPUT);
  digitalWrite(STEP_1_LED_PIN, LOW);
  digitalWrite(STEP_2_LED_PIN, LOW);
  digitalWrite(STEP_3_LED_PIN, LOW);
  setupLedPwm();

  pinMode(AI_PIN, INPUT);
  pinMode(AI_PIN + 1, INPUT);
  pinMode(AI_PIN + 2, INPUT);
  pinMode(AI_PIN + 3, INPUT);
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(CV_PINS[i], INPUT);
  }

  analogReference(VDD);

  midi.begin();
#if MIDI_RX_INVERT
  // JP1 = P: the NPN input stage inverts the MIDI UART data, so invert
  // PB3 (RX) in the port before the USART samples it.
  PORTB.PIN3CTRL |= PORT_INVEN_bm;
#endif
  midi.setNoteOnCallback(noteOnCallback);
  midi.setNoteOffCallback(noteOffCallback);
  midi.setControlChangeCallback(controlChangeCallback);
  midi.setRealtimeCallback(realtimeCallback);

  stepHandler.begin();
  showStep(stepHandler.getMode());
}

void loop() {
  midi.update();
  if (stepHandler.update()) {
    showStep(stepHandler.getMode());
    sendStep();
  }

  static uint8_t lastCv1 = 0;
  static uint8_t lastCv2 = 0;
  static uint8_t lastCv3 = 0;
  static uint8_t lastCv4 = 0;
  static unsigned long lastCheck = 0;
  static unsigned long lastForceSend = 0;

  unsigned long now = millis();

  // Force send all CC values and the step every 1 second
  if (now - lastForceSend >= 1000) {
    lastForceSend = now;
    lastCv1 = readCc(0);
    lastCv2 = readCc(1);
    lastCv3 = readCc(2);
    lastCv4 = readCc(3);
    midi.sendControlChange(1, CC_BASE, lastCv1);
    midi.sendControlChange(1, CC_BASE + 1, lastCv2);
    midi.sendControlChange(1, CC_BASE + 2, lastCv3);
    midi.sendControlChange(1, CC_BASE + 3, lastCv4);
    sendStep();
  }

  // Send CC on value change (checked every 10ms)
  if (now - lastCheck >= 10) {
    lastCheck = now;
    uint8_t cv1 = readCc(0);
    uint8_t cv2 = readCc(1);
    uint8_t cv3 = readCc(2);
    uint8_t cv4 = readCc(3);

    if (cv1 != lastCv1) {
      midi.sendControlChange(1, CC_BASE, cv1);
      lastCv1 = cv1;
    }
    if (cv2 != lastCv2) {
      midi.sendControlChange(1, CC_BASE + 1, cv2);
      lastCv2 = cv2;
    }
    if (cv3 != lastCv3) {
      midi.sendControlChange(1, CC_BASE + 2, cv3);
      lastCv3 = cv3;
    }
    if (cv4 != lastCv4) {
      midi.sendControlChange(1, CC_BASE + 3, cv4);
      lastCv4 = cv4;
    }
  }
}
