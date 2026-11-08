#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SoftwareSerial.h"
#include "WaveTables.h"
#include "LfoMath.h"
#include <avr/pgmspace.h>
#include <util/atomic.h>

// No MIDI: the LFO free-runs from P1/P2 and CV in (the LFO panel has no MIDI
// jack). P1 = RATE (+ CV in, exponential FM), P2 = WAVE. MODE (PA4) toggles the
// output range:
//
//   * BIPOLAR (default, at power-up): full DAC 0..255 -> about -5..+5 V; LED dim.
//   * UNIPOLAR: wave scaled into the upper half, DAC 128..255 -> about 0..+5 V;
//     LED bright.
//
// The LED follows the wave's position within the active range (bottom = off,
// top = its maximum brightness); the range picks the maximum.
//
// Rate and shape maths: LfoMath.h (0.01 Hz .. 40.6 Hz on the knob, ~1 V/oct CV
// up to 2 kHz; sine, triangle, saw, square, complex 1, complex 2, random S&H).

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4   // MODE button, to GND
#define TOGGLE_LED PIN_PA5
#define PIN_CV_IN PIN_PB0   // 8bit CV in: -5.5..+5.5 V -> 0..1023, 0 V ~ 509

constexpr uint8_t BUTTON_DEBOUNCE_MS = 30;
constexpr uint8_t LED_BIPOLAR_SHIFT = 3;       // BIPOLAR LED = wave / 8 (dim)
constexpr uint8_t UNIPOLAR_ZERO = 128;         // DAC code for ~0 V at the output

#ifndef F_CPU
#define F_CPU 20000000UL
#endif

// 40 kHz sample rate (BM: 1 kHz) so FM can push the LFO to audio rate.
// TCB periodic interrupt: CCMP + 1 clocks per period.
constexpr uint32_t TCB_CLOCK_HZ = F_CPU / 2;
constexpr uint16_t TCB_COMPARE_VALUE = TCB_CLOCK_HZ / LfoMath::kSampleRateHz - 1;

// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);

uint32_t phaseAccumulator = 0;          // ISR only
volatile uint32_t phaseIncrement = 0;
volatile uint8_t shapeA = LfoMath::Sine;
volatile uint8_t shapeB = LfoMath::Sine;
volatile uint8_t shapeBlend = 0;
volatile uint8_t latestLfoSample = 0;   // last wave sample, 0..255 (before range scaling)
volatile bool unipolar = false;          // MODE: false = -5..+5 V, true = 0..+5 V
uint16_t randomState = 0xACE1;          // ISR only after setup()
uint8_t randomHeld = 128;               // ISR only: the S&H value of this cycle
uint16_t rateKnob = 0;                  // last P1 reading

void updateLfoPhaseIncrement(uint32_t newIncrement) {
  static uint32_t lastIncrement = 0;
  if (newIncrement == lastIncrement) {
    return;
  }
  lastIncrement = newIncrement;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    phaseIncrement = newIncrement;
  }
}

void updateRate(uint16_t cvIn) {
  updateLfoPhaseIncrement(LfoMath::phaseIncrement(LfoMath::ratePitch(rateKnob, cvIn)));
}

void updateWaveformMix(uint16_t cvValue) {
  LfoMath::ShapeMix mix = LfoMath::shapeMix(cvValue);
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    shapeA = mix.a;
    shapeB = mix.b;
    shapeBlend = mix.blend;
  }
}

// One shape at a phase. Tables are read with linear interpolation between
// entries (phase bits 23..16), so slow rates move in single DAC steps instead
// of the 256-entry staircase.
static inline uint8_t readShape(uint8_t shape, uint32_t phase) {
  uint8_t index = phase >> 24;
  uint8_t frac = phase >> 16;
  WaveTables::Waveform table;
  switch (shape) {
    case LfoMath::Sine: table = WaveTables::Sine; break;
    case LfoMath::Triangle: table = WaveTables::Triangle; break;
    case LfoMath::Saw: table = WaveTables::Saw; break;
    case LfoMath::Square: return (index < 128) ? 255 : 0;
    case LfoMath::Complex1: table = WaveTables::Complex1; break;
    case LfoMath::Complex2: table = WaveTables::Complex2; break;
    default: return randomHeld;
  }
  uint8_t a = WaveTables::readSample(table, index);
  uint8_t b = WaveTables::readSample(table, (uint8_t)(index + 1));
  return LfoMath::lerp8(a, b, frac);
}


// MODE press toggles the output range.
void onModePress() {
  unipolar = !unipolar;
}

// Debounced press edge on MODE.
void updateButton(uint32_t now) {
  static bool lastReading = HIGH;
  static bool stable = HIGH;
  static uint32_t lastChangeMs = 0;
  bool reading = digitalRead(TOGGLE_PIN);
  if (reading != lastReading) {
    lastReading = reading;
    lastChangeMs = now;
  }
  if ((now - lastChangeMs) >= BUTTON_DEBOUNCE_MS && reading != stable) {
    stable = reading;
    if (stable == LOW) {
      onModePress();
    }
  }
}

// LED = wave position in the active range: dim maximum in BIPOLAR, full in UNIPOLAR.
uint8_t ledLevel(uint8_t sample) {
  return unipolar ? sample : (sample >> LED_BIPOLAR_SHIFT);
}

void setupTimer() {
    // Uses 20Mhz clock & divide it by 2
    // So, 1 tick is 0.1us
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // clock div by 2

    // Configure compare value for the sample rate (40 kHz)
    TCB0.CCMP = TCB_COMPARE_VALUE;
  
    // Enabling inturrupts
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB0.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    TCB0.CTRLA |= TCB_ENABLE_bm; // start timer
    sei();
}


// TCB0 Interrupt Service Routine
ISR(TCB0_INT_vect) {
  uint32_t previous = phaseAccumulator;
  uint32_t phase = previous + phaseIncrement;
  phaseAccumulator = phase;
  if (phase < previous) {
    // New cycle: next sample & hold value.
    randomState = LfoMath::nextRandom(randomState);
    randomHeld = randomState >> 8;
  }
  uint8_t wfA = shapeA;
  uint8_t wfB = shapeB;
  uint8_t blend = shapeBlend;

  uint8_t sample = readShape(wfA, phase);
  if (wfA != wfB) {
    sample = LfoMath::lerp8(sample, readShape(wfB, phase), blend);
  }
  DAC0.DATA = unipolar ? (UNIPOLAR_ZERO + (sample >> 1)) : sample;
  latestLfoSample = sample;

  // Clear the interrupt flag
  TCB0.INTFLAGS = TCB_CAPT_bm;
}

void setup() {
  // define the gate pin
  pinMode(GATE_PIN, OUTPUT);
  digitalWrite(GATE_PIN, LOW);

  // Setup Logger
  pinMode(LOGGER_PIN_TX, OUTPUT);
  logger.begin(9600);
  
  // Set the analog reference for ADC with supply voltage.
  analogReference(VDD);
  pinMode(PIN_CV1, INPUT);
  pinMode(PIN_CV2, INPUT);
  pinMode(PIN_CV_IN, INPUT);
  pinMode(TOGGLE_PIN, INPUT_PULLUP);
 
  // DAC0 setup for sending velocity via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;

  // Prime the phase increment and waveform so the LFO starts immediately
  // (first ADC read discarded). The knob noise seeds the S&H shape.
  (void)analogRead(PIN_CV1);
  rateKnob = analogRead(PIN_CV1);
  uint16_t waveKnob = analogRead(PIN_CV2);
  updateRate(analogRead(PIN_CV_IN));
  updateWaveformMix(waveKnob);
  randomState ^= (rateKnob << 6) ^ waveKnob;
  if (randomState == 0) {
    randomState = 0xACE1;
  }

  // Timer related
  setupTimer();
  
  // LED setup
  pinMode(TOGGLE_LED, OUTPUT);
  analogWrite(TOGGLE_LED, 0);

  logger.println("8Bit LFO Started!");
}

void loop() {
  updateButton(millis());

  uint8_t sample = latestLfoSample;

  // Update the LED
  analogWrite(TOGGLE_LED, ledLevel(sample));

  // Write to the GATE
  digitalWrite(GATE_PIN, sample > 127);

  // CV in every pass, so FM follows it at the loop rate (several kHz); the
  // knobs take turns. RATE = P1 (+ CV in), WAVE = P2.
  static bool readRateKnob = true;
  if (readRateKnob) {
    rateKnob = analogRead(PIN_CV1);
  } else {
    updateWaveformMix(analogRead(PIN_CV2));
  }
  readRateKnob = !readRateKnob;
  updateRate(analogRead(PIN_CV_IN));
}
