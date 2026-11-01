#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SoftwareSerial.h"
#include "WaveTables.h"
#include <avr/pgmspace.h>
#include <util/atomic.h>

// No MIDI: the LFO free-runs from P1/P2 and CV in (the LFO panel has no MIDI
// jack). MODE (PA4) runs a free-time P1/P2 recorder (no MIDI clock):
//
//   LIVE --press--> RECORDING --press--> LOOP --press--> LIVE
//
//   * RECORDING: P1/P2 drive the LFO live and are sampled into RAM until the
//     next press, so the take is as long as you hold it open. Every time the
//     buffer fills, it keeps every second sample and the sample period doubles
//     (10 ms -> 20 -> 40 ... -> 640 ms), so long takes cost resolution, not
//     length. At the 640 ms period (~6.8 min) a full buffer ends the take.
//   * LOOP: the take replays with its recorded timing (linear interpolation
//     between samples, including the wrap back to the start). For the first
//     pass the knobs are ignored; then their positions are latched and turning
//     a knob shifts its whole recorded curve (clamped 0..1023).
//   * A press with less than two samples (< 20 ms) is discarded -> LIVE.
//   * CV in is never recorded: it adds to the rate live in every state.
//   * LED follows the LFO level: dim in LIVE, full in LOOP, full + blinking
//     while RECORDING.

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4   // MODE button, to GND
#define TOGGLE_LED PIN_PA5
#define PIN_CV_IN PIN_PB0   // 8bit CV in: -5.5..+5.5 V -> 0..1023, 0 V ~ 509

// CV in adds to the P1 rate knob before the rate curve (ADC counts, ~10.8 mV each):
// +5 V ~ +463 counts, close to half the knob travel. Unpatched (tip grounded) = 0 V.
constexpr int16_t CV_IN_ZERO = 509;      // calibrate per unit (docs/research.md)
constexpr int16_t CV_IN_DEADBAND = 3;    // counts around 0 V treated as 0 V

constexpr uint16_t REC_SAMPLES = 640;          // per knob, 8-bit (1280 B RAM)
constexpr uint16_t REC_FIRST_PERIOD_MS = 10;
constexpr uint16_t REC_MAX_PERIOD_MS = 640;    // 640 x 640 ms ~ 6.8 min max take
constexpr uint8_t BUTTON_DEBOUNCE_MS = 30;
constexpr uint8_t REC_BLINK_MS = 150;          // LED blink half-period
constexpr uint8_t LED_LIVE_SHIFT = 3;          // LIVE LED = level / 8

#ifndef F_CPU
#define F_CPU 20000000UL
#endif

constexpr uint16_t LFO_SAMPLE_RATE_HZ = 1000;
constexpr uint32_t LFO_MIN_FREQ_MILLIHZ = 100;   // 0.1 Hz
constexpr uint32_t LFO_MAX_FREQ_MILLIHZ = 20000; // 20 Hz
constexpr uint32_t TCB_CLOCK_HZ = F_CPU / 2;
constexpr uint16_t TCB_COMPARE_VALUE = TCB_CLOCK_HZ / LFO_SAMPLE_RATE_HZ;

// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);

volatile uint32_t phaseAccumulator = 0;
volatile uint32_t phaseIncrement = 0;
volatile uint8_t waveformIndexA = WaveTables::Sine;
volatile uint8_t waveformIndexB = WaveTables::Sine;
volatile uint8_t waveformBlend = 0;
volatile uint8_t latestLfoSample = 0;

uint32_t mapCvToFrequencyCurve(uint16_t cvValue) {
  uint32_t range = LFO_MAX_FREQ_MILLIHZ - LFO_MIN_FREQ_MILLIHZ;
  uint32_t normalized = ((uint32_t)cvValue << 16) / 1023UL; // Q16 0-1
  uint32_t normalizedSq = ((uint64_t)normalized * normalized) >> 16; // Q16
  uint32_t normalizedCube = ((uint64_t)normalizedSq * normalized) >> 16; // Q16
  uint32_t curve = (normalized + normalizedSq + normalizedCube) / 3;
  uint32_t freqMilliHz = LFO_MIN_FREQ_MILLIHZ + (((uint64_t)range * curve) >> 16);
  if (freqMilliHz > LFO_MAX_FREQ_MILLIHZ) {
    freqMilliHz = LFO_MAX_FREQ_MILLIHZ;
  }
  return freqMilliHz;
}

uint32_t calculatePhaseIncrement(uint32_t freqMilliHz) {
  if (freqMilliHz < LFO_MIN_FREQ_MILLIHZ) {
    freqMilliHz = LFO_MIN_FREQ_MILLIHZ;
  }
  uint64_t numerator = (uint64_t)freqMilliHz << 32;
  return numerator / (1000ULL * LFO_SAMPLE_RATE_HZ);
}

void updateLfoPhaseIncrement(uint32_t freqMilliHz) {
  static uint32_t lastIncrement = 0;
  uint32_t newIncrement = calculatePhaseIncrement(freqMilliHz);
  if (newIncrement == lastIncrement) {
    return;
  }
  lastIncrement = newIncrement;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    phaseIncrement = newIncrement;
  }
}

uint16_t clampCv(int16_t v) {
  if (v < 0) {
    return 0;
  }
  if (v > 1023) {
    return 1023;
  }
  return (uint16_t)v;
}

// P1 knob + CV in offset, clamped to the 0..1023 range of the rate curve.
uint16_t rateControl(uint16_t knob, uint16_t cvIn) {
  int16_t offset = (int16_t)cvIn - CV_IN_ZERO;
  if (offset >= -CV_IN_DEADBAND && offset <= CV_IN_DEADBAND) {
    offset = 0;
  }
  return clampCv((int16_t)knob + offset);
}

void updateWaveformMix(uint16_t cvValue) {
  const uint8_t maxIndex = WaveTables::kWaveformCount - 1;
  const uint32_t scale = (uint32_t)maxIndex << 8;
  uint32_t scaled = ((uint32_t)cvValue * scale) / 1023UL;
  uint8_t segment = scaled >> 8;
  uint8_t blend = scaled & 0xFF;

  uint8_t wfA = segment;
  uint8_t wfB;
  if (segment >= maxIndex) {
    wfA = maxIndex;
    wfB = maxIndex;
    blend = 0;
  } else {
    wfB = segment + 1;
  }

  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    waveformIndexA = wfA;
    waveformIndexB = wfB;
    waveformBlend = blend;
  }
}


// ---- Free-time P1/P2 recorder ------------------------------------------------

enum RecState : uint8_t { REC_LIVE = 0, REC_RECORDING, REC_LOOP };

RecState recState = REC_LIVE;
uint8_t recBuf1[REC_SAMPLES];
uint8_t recBuf2[REC_SAMPLES];
uint16_t recCount = 0;         // samples in the buffer
uint16_t recPeriodMs = REC_FIRST_PERIOD_MS;
uint32_t recStartMs = 0;       // take start (RECORDING) or loop start (LOOP)
uint32_t recLengthMs = 0;      // loop length = recCount * recPeriodMs
bool recOffsetArmed = false;   // first loop pass done, knob offsets active
uint16_t recRef1 = 0;          // knob positions latched after the first pass
uint16_t recRef2 = 0;

void startLoop(uint32_t now) {
  recLengthMs = (uint32_t)recCount * recPeriodMs;
  recStartMs = now;
  recOffsetArmed = false;
  recState = REC_LOOP;
}

void onModePress(uint32_t now) {
  switch (recState) {
    case REC_LIVE:
      recCount = 0;
      recPeriodMs = REC_FIRST_PERIOD_MS;
      recStartMs = now;
      recState = REC_RECORDING;
      break;
    case REC_RECORDING:
      if (recCount < 2) {
        recState = REC_LIVE;           // too short to loop: discard
      } else {
        startLoop(now);
      }
      break;
    case REC_LOOP:
      recState = REC_LIVE;
      break;
  }
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
      onModePress(now);
    }
  }
}

// Store a P1/P2 pair whenever the take's clock passes the next sample slot.
void recordSample(uint32_t now, uint16_t knob1, uint16_t knob2) {
  if ((now - recStartMs) < (uint32_t)recCount * recPeriodMs) {
    return;
  }
  if (recCount >= REC_SAMPLES) {
    if (recPeriodMs >= REC_MAX_PERIOD_MS) {
      startLoop(now);                  // longest take reached: loop it
      return;
    }
    // Keep every second sample at twice the period: count * period, the
    // time of the next slot, stays the same.
    for (uint16_t i = 0; i < REC_SAMPLES / 2; i++) {
      recBuf1[i] = recBuf1[2 * i];
      recBuf2[i] = recBuf2[2 * i];
    }
    recCount = REC_SAMPLES / 2;
    recPeriodMs *= 2;
  }
  recBuf1[recCount] = knob1 >> 2;      // 10-bit -> 8-bit storage
  recBuf2[recCount] = knob2 >> 2;
  recCount++;
}

// Recorded value at loop position `pos`, interpolated, plus the knob offset.
uint16_t playbackValue(const uint8_t* buf, uint32_t pos, int16_t offset) {
  uint16_t index = pos / recPeriodMs;
  uint16_t frac = pos % recPeriodMs;
  uint16_t next = (index + 1 < recCount) ? index + 1 : 0;
  uint32_t a = (uint32_t)buf[index] << 2;
  uint32_t b = (uint32_t)buf[next] << 2;
  uint16_t value = (a * (recPeriodMs - frac) + b * frac) / recPeriodMs;
  return clampCv((int16_t)value + offset);
}

// Replace the live knobs with the loop (plus knob offsets after the first pass).
void playback(uint32_t now, uint16_t& knob1, uint16_t& knob2) {
  uint32_t elapsed = now - recStartMs;
  int16_t offset1 = 0;
  int16_t offset2 = 0;
  if (!recOffsetArmed && elapsed >= recLengthMs) {
    recOffsetArmed = true;             // first pass done: latch the knobs
    recRef1 = knob1;
    recRef2 = knob2;
  }
  if (recOffsetArmed) {
    offset1 = (int16_t)knob1 - (int16_t)recRef1;
    offset2 = (int16_t)knob2 - (int16_t)recRef2;
  }
  uint32_t pos = elapsed % recLengthMs;
  knob1 = playbackValue(recBuf1, pos, offset1);
  knob2 = playbackValue(recBuf2, pos, offset2);
}

uint8_t ledLevel(uint32_t now, uint8_t sample) {
  switch (recState) {
    case REC_RECORDING:
      return ((now / REC_BLINK_MS) & 1) ? sample : 0;
    case REC_LOOP:
      return sample;
    default:
      return sample >> LED_LIVE_SHIFT;
  }
}

void setupTimer() {
    // Uses 20Mhz clock & divide it by 2
    // So, 1 tick is 0.1us
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // clock div by 2

    // Configure compare value for the desired sample rate (1 kHz for the LFO)
    TCB0.CCMP = TCB_COMPARE_VALUE;
  
    // Enabling inturrupts
    TCB0.CTRLB |= TCB_CNTMODE_INT_gc; // Timer interrupt mode (periodic interrupts)
    TCB0.INTCTRL = TCB_CAPT_bm; // Enable Capture interrupt
    TCB0.CTRLA |= TCB_ENABLE_bm; // start timer
    sei();
}


// TCB0 Interrupt Service Routine
ISR(TCB0_INT_vect) {
  phaseAccumulator += phaseIncrement;
  uint8_t tableIndex = phaseAccumulator >> 24; // use the top 8 bits as the table index
  uint8_t wfA = waveformIndexA;
  uint8_t wfB = waveformIndexB;
  uint8_t blend = waveformBlend;

  uint8_t sampleA = WaveTables::readSample(static_cast<WaveTables::Waveform>(wfA), tableIndex);
  uint8_t sample = sampleA;
  if (blend != 0 && wfA != wfB) {
    uint8_t sampleB = WaveTables::readSample(static_cast<WaveTables::Waveform>(wfB), tableIndex);
    uint16_t weightA = 256 - blend;
    uint16_t weightB = blend;
    sample = ((uint32_t)sampleA * weightA + (uint32_t)sampleB * weightB) >> 8;
  }
  DAC0.DATA = sample;
  latestLfoSample = sample;

  // Clear the interrupt flag∫
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
  // (first ADC read discarded).
  (void)analogRead(PIN_CV1);
  uint16_t initialRate = analogRead(PIN_CV1);
  uint16_t initialCvIn = analogRead(PIN_CV_IN);
  updateLfoPhaseIncrement(mapCvToFrequencyCurve(rateControl(initialRate, initialCvIn)));
  updateWaveformMix(analogRead(PIN_CV2));

  // Timer related
  setupTimer();
  
  // LED setup
  pinMode(TOGGLE_LED, OUTPUT);
  analogWrite(TOGGLE_LED, 0);

  logger.println("8Bit LFO Started!");
}

void loop() {
  uint32_t now = millis();
  updateButton(now);

  // Update the LED
  analogWrite(TOGGLE_LED, ledLevel(now, latestLfoSample));

  // Write to the GATE
  digitalWrite(GATE_PIN, latestLfoSample > 127);

  // RATE = P1 (+ CV in, never recorded), WAVE = P2
  uint16_t rateKnob = analogRead(PIN_CV1);
  uint16_t waveKnob = analogRead(PIN_CV2);
  uint16_t cvIn = analogRead(PIN_CV_IN);
  if (recState == REC_RECORDING) {
    recordSample(now, rateKnob, waveKnob);
  }
  if (recState == REC_LOOP) {
    playback(now, rateKnob, waveKnob);
  }
  uint32_t freqMilliHz = mapCvToFrequencyCurve(rateControl(rateKnob, cvIn));
  updateLfoPhaseIncrement(freqMilliHz);
  updateWaveformMix(waveKnob);
}
