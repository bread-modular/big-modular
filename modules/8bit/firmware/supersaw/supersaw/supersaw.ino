#include <Arduino.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include "SimpleMIDI.h"
#include "CvRecorder.h"
#include "SoftwareSerial.h"

// JP1 on the 8bit carrier picks the MIDI input path (set by ../jumper.sh):
//   P (protected) = MIDI V2 NPN front end, which inverts the UART data -> 1
//   D (direct)    = jack tip straight to PB3, as Bread Modular       -> 0
#ifndef MIDI_RX_INVERT
#error "MIDI_RX_INVERT must be set: build with ../compile.sh <firmware> p|d"
#endif

#define GATE_PIN PIN_PA7
#define LOGGER_PIN_TX PIN_PB4
#define PIN_CV1 PIN_PA1
#define PIN_CV2 PIN_PA2
#define TOGGLE_PIN PIN_PA4
#define TOGGLE_LED PIN_PA5

// Sawtooth wave parameters
#define DEFAULT_SAWTOOTH_FREQ 100 // Default sawtooth wave frequency
#define DAC_MAX_VALUE 255 // 8-bit DAC max value
#define TIMER_FREQ 10000000 // 10MHz (20MHz / 2)
#define MAX_FREQ 500 // Maximum frequency in Hz
#define MIN_FREQ 20  // Minimum frequency in Hz
#define OCTAVE_DIVIDER 2 // Divider for one octave down

// CV control parameters
#define CV_THRESHOLD 5 // Threshold for CV value changes (0-1023)

// Envelope (P1): note-on restarts it at a level set by the MIDI
// velocity (127 = full, linear), then it decays
// exponentially with a time constant set by P1. P1 at 0 = short pulse,
// P1 at full = hold until the next note-on. Note-off is ignored.
#define ENV_MAX 65535
#define ENV_TAU_MIN_MS 5.0    // P1 at 0: pulse
#define ENV_TAU_MAX_MS 3000.0 // P1 just below the hold zone
#define ENV_HOLD_CV 1000      // P1 at or above this: hold

SimpleMIDI MIDI;
// MODE = 4-bar P1/P2 motion recorder on MIDI clock (crash's, plus offset)
CvRecorder recorder(TOGGLE_PIN, TOGGLE_LED);
// TODO: Change this to real serial port. (We need to update the schematic for that)
SoftwareSerial logger(-1, LOGGER_PIN_TX);

// Variables for main sawtooth wave generation (TCB0)
volatile uint16_t sawtoothStep = 0;
volatile uint16_t sawtoothMaxStep = DAC_MAX_VALUE;
volatile uint16_t currentFrequency = DEFAULT_SAWTOOTH_FREQ;
volatile uint16_t pendingFrequency = 0; // New frequency to be applied at the next cycle
volatile bool frequencyChangeRequested = false; // Flag for frequency change

// Variables for octave-down sawtooth wave generation (TCB1)
volatile uint16_t sawtoothStepOctaveDown = 0;
volatile uint16_t sawtoothStepOctaveDownWithVolume = 0;
volatile uint16_t sawtoothMaxStepOctaveDown = DAC_MAX_VALUE;
volatile uint16_t currentFrequencyOctaveDown = DEFAULT_SAWTOOTH_FREQ / OCTAVE_DIVIDER;

// Variables for CV control
uint16_t lastCV2Value = 0xFFFF;
uint16_t liveCV1 = 0;  // deadbanded knob readings (recorder input)
uint16_t liveCV2 = 0;
uint8_t octaveDownVolume = 128; // Default volume (0-255, where 255 is full volume)

// Keep the current note for gate handling
uint8_t currentNote = 0;

// Envelope state: envValue in loop(), envLevel (0-255) read by the TCB0 ISR
volatile uint8_t envLevel = 0;
volatile bool envTrigger = false;
volatile uint8_t envVelocity = 127; // velocity of the last note-on (1-127)
uint16_t envValue = 0;
uint16_t envDecayCoef = 0; // per-ms multiplier (Q16); 0 = hold
uint16_t lastCV1Value = 0xFFFF;
uint32_t lastEnvMillis = 0;

// Function to update the main sawtooth wave frequency
void setSawtoothFrequency(uint16_t frequency) {
    // Ensure frequency is within reasonable bounds (MIN_FREQ to MAX_FREQ Hz)
    if (frequency < MIN_FREQ) frequency = MIN_FREQ;
    if (frequency > MAX_FREQ) frequency = MAX_FREQ;
    
    // Store the current frequency
    currentFrequency = frequency;
    
    // Simple direct calculation for timer period
    // One complete cycle needs 256 steps (just the ramp up)
    // At frequency F, we need F * 256 steps per second
    // With timer running at TIMER_FREQ, each step needs TIMER_FREQ / (F * 256) ticks
    uint32_t timerPeriod = TIMER_FREQ / (frequency * 256UL);
    
    // Ensure timer period is at least 1 to prevent timer from getting stuck
    if (timerPeriod < 1) timerPeriod = 1;
    
    // We'll just update the CCMP value without disabling/enabling the timer
    // This reduces potential timing glitches
    TCB0.CCMP = (uint16_t)timerPeriod;
    
    // Also update the octave-down frequency
    currentFrequencyOctaveDown = frequency / OCTAVE_DIVIDER;
    uint32_t timerPeriodOctaveDown = TIMER_FREQ / (currentFrequencyOctaveDown * 256UL);
    
    // Ensure timer period is at least 1 to prevent timer from getting stuck
    if (timerPeriodOctaveDown < 1) timerPeriodOctaveDown = 1;
    
    TCB1.CCMP = (uint16_t)timerPeriodOctaveDown;
}

// Get the current sawtooth wave frequency
uint16_t getSawtoothFrequency() {
    return currentFrequency;
}

// Set the octave-down volume from a CV2 value (0-1023)
void setVolumeFromCV2(uint16_t cv2) {
    if (cv2 == lastCV2Value) {
        return;
    }
    lastCV2Value = cv2;

    // Map the CV2 value (0-1023) to volume range (0-255)
    octaveDownVolume = map(cv2, 0, 1023, 0, 255);
}

// Map a CV1 value (0-1023) to the envelope decay: exponential knob law from
// ENV_TAU_MIN_MS to ENV_TAU_MAX_MS, hold at the top of the travel.
void setDecayFromCV1(uint16_t rawCV1) {
    if (rawCV1 == lastCV1Value) {
        return;
    }
    lastCV1Value = rawCV1;

    if (rawCV1 >= ENV_HOLD_CV) {
        envDecayCoef = 0;
        return;
    }
    float x = rawCV1 / (float)ENV_HOLD_CV;
    float tauMs = ENV_TAU_MIN_MS * pow(ENV_TAU_MAX_MS / ENV_TAU_MIN_MS, x);
    envDecayCoef = (uint16_t)(65536.0 * exp(-1.0 / tauMs));
}

// Read P1/P2 with the deadband into liveCV1/2. In LIVE and RECORDING they
// drive the sound directly; in PLAYBACK the recorder owns the sound and uses
// them as the offset for the whole loop (after its one-pass guard).
void readKnobs() {
    uint16_t cv1 = analogRead(PIN_CV1);
    if (abs((int)cv1 - (int)liveCV1) > CV_THRESHOLD) {
        liveCV1 = cv1;
    }
    uint16_t cv2 = analogRead(PIN_CV2);
    if (abs((int)cv2 - (int)liveCV2) > CV_THRESHOLD) {
        liveCV2 = cv2;
    }
    if (!recorder.isPlayingBack()) {
        setDecayFromCV1(liveCV1);
        setVolumeFromCV2(liveCV2);
    }
}

// Playback consumer: push a recorded (+ offset) CV pair into the voice.
void applyRecorded(uint16_t cv1, uint16_t cv2) {
    setDecayFromCV1(cv1);
    setVolumeFromCV2(cv2);
}

// MIDI clock tick: advance the 4-bar playhead, record or replay.
void onMidiClock() {
    recorder.onClock(liveCV1, liveCV2, applyRecorded);
}

// MIDI Start: rewind the loop to bar 1.
void onMidiStart() {
    recorder.onStart();
}

// Run the envelope once per millisecond.
void updateEnvelope() {
    if (envTrigger) {
        noInterrupts();
        envTrigger = false;
        uint8_t velocity = envVelocity;
        interrupts();
        envValue = ((uint32_t)ENV_MAX * velocity) / 127;
        lastEnvMillis = millis();
    }

    uint32_t now = millis();
    while (now - lastEnvMillis >= 1) {
        lastEnvMillis++;
        if (envDecayCoef == 0 || envValue == 0) {
            continue; // hold, or already silent
        }
        uint16_t next = ((uint32_t)envValue * envDecayCoef) >> 16;
        // Always fall by at least 1 so long tails still reach 0.
        envValue = (next < envValue) ? next : envValue - 1;
    }

    envLevel = envValue >> 8;
}

void setupTimers() {
    // Configure TCB0 for main sawtooth wave generation
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // Clock div by 2 (10MHz)
    TCB0.CTRLB = TCB_CNTMODE_INT_gc;    // Timer interrupt mode
    TCB0.INTCTRL = TCB_CAPT_bm;         // Enable capture interrupt
    
    // Set initial frequency directly for TCB0
    uint32_t timerPeriod = TIMER_FREQ / (DEFAULT_SAWTOOTH_FREQ * 256UL);
    TCB0.CCMP = (uint16_t)timerPeriod;
    currentFrequency = DEFAULT_SAWTOOTH_FREQ;
    
    // Configure TCB1 for octave-down sawtooth wave generation
    TCB1.CTRLA = TCB_CLKSEL_CLKDIV2_gc; // Clock div by 2 (10MHz)
    TCB1.CTRLB = TCB_CNTMODE_INT_gc;    // Timer interrupt mode
    TCB1.INTCTRL = TCB_CAPT_bm;         // Enable capture interrupt
    
    // Set initial frequency for TCB1 (one octave down)
    currentFrequencyOctaveDown = DEFAULT_SAWTOOTH_FREQ / OCTAVE_DIVIDER;
    uint32_t timerPeriodOctaveDown = TIMER_FREQ / (currentFrequencyOctaveDown * 256UL);
    TCB1.CCMP = (uint16_t)timerPeriodOctaveDown;
    
    // Reset sawtooth wave states
    sawtoothStep = 0;
    sawtoothStepOctaveDown = 0;
    
    // Enable the timers
    TCB0.CTRLA |= TCB_ENABLE_bm;
    TCB1.CTRLA |= TCB_ENABLE_bm;
    
    sei(); // Enable global interrupts
}

// TCB0 Interrupt Service Routine (Main sawtooth wave)
ISR(TCB0_INT_vect) {
    // First, clear the interrupt flag immediately to reduce jitter
    TCB0.INTFLAGS = TCB_CAPT_bm;
    
    // At the reset point is the best time to change frequency
    // This happens when we're at step 0
    if (sawtoothStep == 0 && frequencyChangeRequested) {
        if (pendingFrequency > 0) {
            // Apply the new frequency
            setSawtoothFrequency(pendingFrequency);
            // Reset the pending frequency and flag
            pendingFrequency = 0;
            frequencyChangeRequested = false;
        }
    }
    
    // Update sawtooth wave value
    sawtoothStep++;
    if (sawtoothStep > sawtoothMaxStep) {
        sawtoothStep = 0; // Reset to start a new ramp
    }
    
    // Mix the main sawtooth with the volume-adjusted octave-down sawtooth
    uint16_t combinedValue = (sawtoothStep + sawtoothStepOctaveDownWithVolume) / 2;

    // Apply the P1 envelope
    combinedValue = (combinedValue * envLevel) >> 8;
    
    // Update DAC directly from the ISR for consistent timing
    DAC0.DATA = combinedValue;
}

// TCB1 Interrupt Service Routine (Octave-down sawtooth wave)
ISR(TCB1_INT_vect) {
    // Clear the interrupt flag immediately
    TCB1.INTFLAGS = TCB_CAPT_bm;
    
    // Update octave-down sawtooth wave value
    sawtoothStepOctaveDown++;
    if (sawtoothStepOctaveDown > sawtoothMaxStepOctaveDown) {
        sawtoothStepOctaveDown = 0; // Reset to start a new ramp
    }
    
    // Combine both waveforms and send to DAC
    // Apply volume control to octave-down sawtooth using integer math
    // Scale octaveDownVolume from 0-255 to 0-1 fraction using integer division
   sawtoothStepOctaveDownWithVolume = (sawtoothStepOctaveDown * octaveDownVolume) >> 8;

    // Note: We don't update the DAC here, that's done in the TCB0 ISR
}

// Callback functions for MIDI events
void onNoteOn(uint8_t channel, uint8_t note, uint8_t velocity) {
  digitalWrite(GATE_PIN, HIGH);

  if (note > 65) {
    return;
  }

  // Set frequency based on MIDI note using SimpleMIDI's midiToFrequency function
  float rawFrequency = MIDI.midiToFrequency(note);
  uint16_t frequency = (uint16_t)rawFrequency;

  // Set the pending frequency to be applied at the next cycle
  noInterrupts();
  currentNote = note;
  pendingFrequency = frequency;
  frequencyChangeRequested = true;
  envVelocity = velocity;
  envTrigger = true;
  interrupts();
}

void onNoteOff(uint8_t channel, uint8_t note, uint8_t velocity) {
  if (note == currentNote) {
    digitalWrite(GATE_PIN, LOW);
  }
}

void onControlChange(uint8_t channel, uint8_t control, uint8_t value) {  

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
 
  // DAC0 setup for sending velocity via the PA6 pin
  VREF.CTRLA |= VREF_DAC0REFSEL_4V34_gc; //this will force it to use VDD as the VREF
  VREF.CTRLB |= VREF_DAC0REFEN_bm;
  DAC0.CTRLA = DAC_ENABLE_bm | DAC_OUTEN_bm;
  DAC0.DATA = 0;

  // Setup MIDI
  MIDI.begin(31250);
#if MIDI_RX_INVERT
  // JP1 = P: the NPN input stage inverts the MIDI UART data, so invert
  // PB3 (RX) in the port before the USART samples it.
  PORTB.PIN3CTRL |= PORT_INVEN_bm;
#endif

  // Timer related - this will start both sawtooth wave generators
  setupTimers();
  
  // MODE + LED: P1/P2 motion recorder (LED off = live, blink = recording,
  // solid = looping the take).
  recorder.begin();

  // Start from the real knob positions (first ADC read discarded).
  (void)analogRead(PIN_CV1);
  (void)analogRead(PIN_CV2);
  liveCV1 = analogRead(PIN_CV1);
  liveCV2 = analogRead(PIN_CV2);
  setDecayFromCV1(liveCV1);
  setVolumeFromCV2(liveCV2);

  // Register MIDI callbacks
  MIDI.setNoteOnCallback(onNoteOn);
  MIDI.setNoteOffCallback(onNoteOff);
  MIDI.setControlChangeCallback(onControlChange);
  MIDI.setClockCallback(onMidiClock);
  MIDI.setStartCallback(onMidiStart);
}

void loop() {
  // Process MIDI messages
  MIDI.update();

  // MODE button + LED
  recorder.update();

  // P1 envelope decay and P2 octave-down level (live or recorded + offset)
  readKnobs();
  updateEnvelope();
}