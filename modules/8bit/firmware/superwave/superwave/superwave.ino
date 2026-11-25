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
#define PIN_CV3 PIN_PB5 // P3 on the S6 carrier; not connected on the 4HP S5 carrier
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

// Wave select (P3), CCW -> CW: saw (the supersaw ramp), then a square
// around the middle, then pulse width modulation that grows to the end.
// PB5 has its pull-up on, so a carrier without P3 on PB5 reads 1023 (full
// PWM). The pull-up lifts the knob curve; for a 35k pull-up the saw ends at
// about 28 % of the travel and PWM starts at about 56 %.
#define WAVE_SQUARE_EDGE 445 // saw below, square / PWM above (with hysteresis)
#define WAVE_HYST 30
#define PWM_START 690        // PWM depth 0 here ...
#define PWM_FULL 990         // ... and full from here
#define WAVE_READ_MS 10
// PWM: a triangle LFO narrows the high part of the pulse from 50 % (start
// step 128) down to 8.2 % (start step 235) at full depth and back. The LFO
// runs at 0.5 Hz at the start of the PWM zone and 1.5 Hz at full depth.
#define PULSE_START_MIN 128
#define PULSE_START_SPAN 108
#define PWM_RATE_MIN 33      // LFO phase step per ms (65536 = one cycle): 0.5 Hz
#define PWM_RATE_SPAN 65     // + this at full depth: 1.5 Hz
// Pulse levels per start step 128..236: keep the saw's mean (127.5) and RMS
// (73.6), so square and pulses are as loud as the saw. Below 25 % the high
// level would pass 255, so it stays at 255 with the mean kept and the
// narrowest pulse is 5.7 dB quieter.
const uint8_t PULSE_LOW[PULSE_START_SPAN + 1] = {
     54,  54,  55,  56,  56,  57,  57,  58,  58,  59,  59,  60,  61,  61,  62,  62,
     63,  63,  64,  64,  65,  65,  66,  66,  67,  67,  68,  68,  69,  69,  70,  70,
     70,  71,  71,  72,  72,  73,  73,  74,  74,  75,  75,  76,  76,  77,  77,  77,
     78,  78,  79,  79,  80,  80,  81,  81,  81,  82,  82,  83,  83,  84,  84,  85,
     85,  86,  87,  88,  88,  89,  90,  91,  92,  93,  93,  94,  95,  96,  97,  97,
     98,  99, 100, 100, 101, 102, 102, 103, 104, 105, 105, 106, 107, 107, 108, 109,
    109, 110, 111, 111, 112, 112, 113, 114, 114, 115, 116, 116, 117
};
const uint8_t PULSE_HIGH[PULSE_START_SPAN + 1] = {
    201, 202, 202, 203, 203, 204, 205, 205, 206, 206, 207, 208, 208, 209, 210, 210,
    211, 212, 212, 213, 214, 214, 215, 216, 216, 217, 218, 219, 219, 220, 221, 222,
    223, 223, 224, 225, 226, 227, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236,
    237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 249, 250, 251, 252, 254,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255
};

// Envelope (P1): note-on restarts it at a level set by the MIDI
// velocity (127 = full, linear), then it decays
// exponentially with a time constant set by P1. P1 at 0 = short pulse,
// P1 at full = hold until the next note-on. Note-off is ignored.
#define ENV_MAX 65535
#define ENV_TAU_MIN_MS 5.0    // P1 at 0: pulse
#define ENV_TAU_MAX_MS 3000.0 // P1 just below the hold zone
#define ENV_HOLD_CV 1000      // P1 at or above this: hold

SimpleMIDI MIDI;
// MODE = 4-bar P1/P2 motion recorder on MIDI clock (crash's, plus offset and
// overdub: hold MODE while looping + turn a knob)
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
bool waveSquare = false;  // P3 past the saw zone: square / PWM
uint8_t pwmDepth = 0;     // 0 = plain square, 255 = full PWM
uint16_t pwmPhase = 0;    // triangle LFO phase
uint32_t lastWaveMillis = 0;
uint32_t lastPwmMillis = 0;
volatile uint8_t pulseWave = 0;  // 1 = pulse, 0 = saw (read by both ISRs)
volatile uint8_t pulseStart = 128;
volatile uint8_t pulseLow = 54;
volatile uint8_t pulseHigh = 201;

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

// P3 wave select, read every WAVE_READ_MS (not recorded): saw or square,
// and the PWM depth.
void readWave() {
    uint32_t now = millis();
    if (now - lastWaveMillis < WAVE_READ_MS) {
        return;
    }
    lastWaveMillis = now;
    uint16_t cv3 = analogRead(PIN_CV3);
    if (waveSquare && cv3 + WAVE_HYST < WAVE_SQUARE_EDGE) {
        waveSquare = false;
    } else if (!waveSquare && cv3 > WAVE_SQUARE_EDGE + WAVE_HYST) {
        waveSquare = true;
    }
    if (cv3 <= PWM_START) {
        pwmDepth = 0;
    } else if (cv3 >= PWM_FULL) {
        pwmDepth = 255;
    } else {
        pwmDepth = ((uint32_t)(cv3 - PWM_START) * 255) / (PWM_FULL - PWM_START);
    }
}

// Run the PWM LFO once per millisecond and hand the pulse to the ISRs.
void updateWave() {
    uint32_t now = millis();
    while (now - lastPwmMillis >= 1) {
        lastPwmMillis++;
        pwmPhase += PWM_RATE_MIN + (((uint16_t)pwmDepth * PWM_RATE_SPAN) >> 8);
    }

    if (!waveSquare) {
        pulseWave = 0;
        return;
    }
    // Triangle 0..65534 from the phase
    uint16_t tri = (pwmPhase & 0x8000) ? (uint16_t)(~pwmPhase << 1) : (uint16_t)(pwmPhase << 1);
    uint8_t offset = ((((uint32_t)tri * pwmDepth) >> 16) * PULSE_START_SPAN) >> 8;
    uint8_t start = PULSE_START_MIN + offset;
    if (pulseWave && start == pulseStart) {
        return;
    }
    // Change the whole set at once so no sample mixes two widths
    noInterrupts();
    pulseStart = start;
    pulseLow = PULSE_LOW[offset];
    pulseHigh = PULSE_HIGH[offset];
    pulseWave = 1;
    interrupts();
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
    
    // P3: saw, or a pulse from the ramp
    uint8_t mainValue = sawtoothStep;
    if (pulseWave) {
        mainValue = (mainValue >= pulseStart) ? pulseHigh : pulseLow;
    }

    // Mix the main sawtooth with the volume-adjusted octave-down sawtooth
    uint16_t combinedValue = (mainValue + sawtoothStepOctaveDownWithVolume) / 2;

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
    uint8_t octaveValue = sawtoothStepOctaveDown;
    if (pulseWave) {
        octaveValue = (octaveValue >= pulseStart) ? pulseHigh : pulseLow;
    }
    sawtoothStepOctaveDownWithVolume = ((uint16_t)octaveValue * octaveDownVolume) >> 8;

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
  pinMode(PIN_CV3, INPUT_PULLUP);
 
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
  (void)analogRead(PIN_CV3);
  lastWaveMillis = millis() - WAVE_READ_MS;
  readWave();
  lastPwmMillis = millis();
  updateWave();

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
  readWave();
  updateWave();
  updateEnvelope();
}