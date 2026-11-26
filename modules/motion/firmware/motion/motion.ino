// MOTION firmware (ATtiny1616 at 5 V, 20 MHz internal)
//
// Four knobs, four CV outputs, each -5..+5 V. Hold REC and move a knob: its
// motion is recorded straight into the MB85RC256V FRAM and loops on that
// knob's output (MotionRecorder.h). 1 s after the take the knob attenuates
// it. Hold DEL (the second button, labelled RANGE on the S1 schematic) and
// move a knob = delete that take; hold DEL 5 s without moving a knob = erase
// every take. Takes and gains are kept in the FRAM.
//
// Pin map (modules/motion/tools/build_schematic.py, S1):
//   PA1 / PA2 / PA6 / PA7  knobs 1-4 (ADC0, VDD reference)
//   PB0 / PB1              SCL / SDA (TWI0, 400 kHz): FRAM 0x50, DAC 0x60
//   PB2 / PA3 / PA4 / PA5  motion LEDs 1-4 (TCA0 split WO2..WO5)
//   PB3 / PB4              REC / DEL LEDs (TCA0 WO0 / WO1 on PORTMUX alternates;
//                          schematic LED_REC / LED_RANGE)
//   PC0 / PC1              REC / DEL buttons to GND (internal pull-ups;
//                          schematic REC_BTN / RANGE_BTN)
//   PB5, PC2, PC3          spare (pull-ups)
// millis() runs on TCD0 (megaTinyCore default on the 1-series); TCA0 is ours.

#include <Wire.h>

#include "MotionIo.h"
#include "MotionRecorder.h"

using namespace motion;

static const uint8_t KNOB_PIN[4] = {PIN_PA1, PIN_PA2, PIN_PA6, PIN_PA7};
static const uint8_t REC_PIN = PIN_PC0;
static const uint8_t DEL_PIN = PIN_PC1;
static const uint32_t ERASE_FLASH_MS = 600;  // three flashes of every LED

// LEDs: 0..3 motion 1-4, 4 REC, 5 DEL.
enum { LED_REC = 4, LED_DEL = 5 };

// ---- FRAM ------------------------------------------------------------------
static bool framOk = false;

static bool framWrite(uint16_t addr, const uint8_t* data, uint8_t n) {
    Wire.beginTransmission(FRAM_I2C);
    Wire.write((uint8_t)(addr >> 8));
    Wire.write((uint8_t)addr);
    Wire.write(data, n);
    return Wire.endTransmission() == 0;
}

static bool framRead(uint16_t addr, uint8_t* data, uint8_t n) {
    Wire.beginTransmission(FRAM_I2C);
    Wire.write((uint8_t)(addr >> 8));
    Wire.write((uint8_t)addr);
    if (Wire.endTransmission(false) != 0) {
        return false;
    }
    if (Wire.requestFrom(FRAM_I2C, n) != n) {
        return false;
    }
    for (uint8_t i = 0; i < n; ++i) {
        data[i] = (uint8_t)Wire.read();
    }
    return true;
}

struct FramStore {
    static constexpr uint16_t MAX_FRAMES = motion::MAX_FRAMES;

    uint16_t readFrame(uint8_t track, uint16_t frame) {
        uint8_t b[2];
        if (!framOk || !framRead(frameAddr(track, frame), b, 2)) {
            return DAC_ZERO;
        }
        return (uint16_t)(b[0] | (b[1] << 8));
    }
    void writeFrame(uint8_t track, uint16_t frame, uint16_t value) {
        if (!framOk) return;
        const uint8_t b[2] = {(uint8_t)value, (uint8_t)(value >> 8)};
        framWrite(frameAddr(track, frame), b, 2);
    }
    void writeHeader(uint8_t track, uint16_t frames, uint16_t gain) {
        if (!framOk) return;
        const uint8_t b[4] = {(uint8_t)frames, (uint8_t)(frames >> 8),
                              (uint8_t)gain, (uint8_t)(gain >> 8)};
        framWrite(headerAddr(track), b, 4);
    }
};

static FramStore store;
typedef MotionRecorder<FramStore> Rec;
static Rec recorder(store);

// Present: check the magic; a blank (or other) FRAM gets empty takes, magic
// last.
static bool framInit() {
    Wire.beginTransmission(FRAM_I2C);
    if (Wire.endTransmission() != 0) {
        return false;
    }
    uint8_t magic[4];
    if (!framRead(0, magic, 4)) {
        return false;
    }
    if (magic[0] == 'M' && magic[1] == 'O' && magic[2] == 'T' &&
        magic[3] == FRAM_VERSION) {
        return true;
    }
    uint8_t zero[16] = {0};
    if (!framWrite(FRAM_HEADERS, zero, sizeof(zero))) {
        return false;
    }
    const uint8_t m[4] = {'M', 'O', 'T', FRAM_VERSION};
    return framWrite(0, m, 4);
}

// ---- DAC -------------------------------------------------------------------
static uint16_t dacLast[4] = {0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF};

// Fast write: all four channels, power-down bits 00. LDAC is tied low, so
// each output updates as its bytes are acknowledged.
static void dacWrite(const uint16_t code[4]) {
    Wire.beginTransmission(DAC_I2C);
    for (uint8_t i = 0; i < 4; ++i) {
        Wire.write((uint8_t)((code[i] >> 8) & 0x0F));
        Wire.write((uint8_t)code[i]);
        dacLast[i] = code[i];
    }
    Wire.endTransmission();
}

// The MCP4728 starts each output from its EEPROM before the MCU runs: make
// that VREF = VDD, gain 1, mid-scale (0 V out), once per chip.
// Then select VREF = VDD for the running registers and write 0 V.
static void dacInit() {
    uint8_t reg[24];
    bool readOk = Wire.requestFrom(DAC_I2C, (uint8_t)24) == 24;
    for (uint8_t i = 0; i < 24; ++i) {
        reg[i] = readOk ? (uint8_t)Wire.read() : 0;
    }
    bool program = false;
    for (uint8_t ch = 0; readOk && ch < 4; ++ch) {
        if (reg[6 * ch + 4] != 0x08 || reg[6 * ch + 5] != 0x00) {
            program = true;
        }
    }
    if (program) {
        Wire.beginTransmission(DAC_I2C);
        Wire.write((uint8_t)0x50);  // sequential write from A, input + EEPROM
        for (uint8_t ch = 0; ch < 4; ++ch) {
            Wire.write((uint8_t)0x08);  // VREF VDD, PD 00, gain 1, D11..D8
            Wire.write((uint8_t)0x00);
        }
        Wire.endTransmission();
        delay(60);  // EEPROM write (50 ms max)
    }
    Wire.beginTransmission(DAC_I2C);
    Wire.write((uint8_t)0x80);  // VREF = VDD on A..D
    Wire.endTransmission();
    const uint16_t zero[4] = {DAC_ZERO, DAC_ZERO, DAC_ZERO, DAC_ZERO};
    dacWrite(zero);
}

// ---- LEDs: TCA0 split mode, 20 MHz / 64 / 255 = 1.2 kHz ----------------------
static volatile uint8_t* ledCmp[6];
static const uint8_t LED_EN[6] = {
    TCA_SPLIT_LCMP2EN_bm, TCA_SPLIT_HCMP0EN_bm, TCA_SPLIT_HCMP1EN_bm,
    TCA_SPLIT_HCMP2EN_bm, TCA_SPLIT_LCMP0EN_bm, TCA_SPLIT_LCMP1EN_bm};

static void ledsInit() {
    takeOverTCA0();
    ledCmp[0] = &TCA0.SPLIT.LCMP2;  // PB2
    ledCmp[1] = &TCA0.SPLIT.HCMP0;  // PA3
    ledCmp[2] = &TCA0.SPLIT.HCMP1;  // PA4
    ledCmp[3] = &TCA0.SPLIT.HCMP2;  // PA5
    ledCmp[4] = &TCA0.SPLIT.LCMP0;  // PB3 (alternate)
    ledCmp[5] = &TCA0.SPLIT.LCMP1;  // PB4 (alternate)
    PORTMUX.CTRLC = PORTMUX_TCA00_bm | PORTMUX_TCA01_bm;
    const uint8_t pins[6] = {PIN_PB2, PIN_PA3, PIN_PA4, PIN_PA5, PIN_PB3, PIN_PB4};
    for (uint8_t i = 0; i < 6; ++i) {
        digitalWrite(pins[i], LOW);
        pinMode(pins[i], OUTPUT);
    }
    TCA0.SPLIT.CTRLA = 0;
    TCA0.SPLIT.CTRLESET = TCA_SPLIT_CMD_RESET_gc | 0x03;
    TCA0.SPLIT.CTRLD = TCA_SPLIT_SPLITM_bm;
    TCA0.SPLIT.LPER = 254;
    TCA0.SPLIT.HPER = 254;
    TCA0.SPLIT.CTRLB = 0;
    TCA0.SPLIT.CTRLA = TCA_SPLIT_CLKSEL_DIV64_gc | TCA_SPLIT_ENABLE_bm;
}

// 0 = compare output off, the pin is driven low by its port.
static void ledSet(uint8_t led, uint8_t duty) {
    if (duty > LED_FULL) duty = LED_FULL;
    if (duty == 0) {
        TCA0.SPLIT.CTRLB &= (uint8_t)~LED_EN[led];
    } else {
        *ledCmp[led] = duty;
        TCA0.SPLIT.CTRLB |= LED_EN[led];
    }
}

// ---- State -----------------------------------------------------------------
static KnobFilter knobFilter[4];
static uint16_t knobs[4];
static uint8_t knobNext = 0;
static bool eraseFlash = false;
static uint32_t eraseMs = 0;
static uint32_t lastMs = 0;

static void readKnob(uint8_t i) {
    const int32_t raw = analogReadEnh(KNOB_PIN[i], 12, 0);
    if (raw >= 0) {
        knobs[i] = knobFilter[i].step((uint16_t)raw);
    }
}

// REC LED: on while REC is held, blinking while a knob records.
static uint8_t recLed(uint32_t now) {
    if (recorder.recording()) {
        return ((now / 150) & 1) ? 0 : LED_FULL;
    }
    return recorder.hold() == Rec::HOLD_REC ? LED_FULL : 0;
}

// DEL LED: on while DEL is held; held with no knob moved: on for 1 s, then a
// countdown that blinks faster each second until the erase at 5 s.
static uint8_t delLed(uint32_t now) {
    if (recorder.hold() != Rec::HOLD_DEL) {
        return 0;
    }
    const uint32_t idle = recorder.eraseHoldMs(now);
    if (idle < 1000) {
        return LED_FULL;
    }
    static const uint16_t HALF[4] = {250, 170, 110, 60};
    uint8_t second = (uint8_t)(idle / 1000 - 1);
    if (second > 3) second = 3;
    return (((idle % 1000) / HALF[second]) & 1) ? 0 : LED_FULL;
}

static void updateLeds(uint32_t now) {
    if (recorder.takeEraseEvent()) {
        eraseFlash = true;
        eraseMs = now;
    }
    if (eraseFlash) {
        const uint32_t e = now - eraseMs;
        if (e < ERASE_FLASH_MS) {
            const uint8_t duty = ((e / 100) & 1) ? 0 : LED_FULL;
            for (uint8_t i = 0; i < 6; ++i) {
                ledSet(i, duty);
            }
            return;
        }
        eraseFlash = false;
    }
    const bool blinkOn = ((now / LED_BLINK_MS) & 1) == 0;
    for (uint8_t i = 0; i < 4; ++i) {
        ledSet(i, motionLed(recorder.out(i), blinkOn));
    }
    ledSet(LED_REC, recLed(now));
    ledSet(LED_DEL, delLed(now));
}

void setup() {
    pinMode(REC_PIN, INPUT_PULLUP);
    pinMode(DEL_PIN, INPUT_PULLUP);
    pinMode(PIN_PB5, INPUT_PULLUP);
    pinMode(PIN_PC2, INPUT_PULLUP);
    pinMode(PIN_PC3, INPUT_PULLUP);
    ledsInit();

    Wire.begin();
    Wire.setClock(400000);
    delay(10);
    dacInit();
    framOk = framInit();

    if (!framOk) {
        // No FRAM: knobs live only. Flash the REC LED five times.
        for (uint8_t i = 0; i < 10; ++i) {
            ledSet(LED_REC, (i & 1) ? 0 : LED_FULL);
            delay(80);
        }
    }

    for (uint8_t n = 0; n < 8; ++n) {
        for (uint8_t i = 0; i < 4; ++i) {
            readKnob(i);
        }
    }

    const uint32_t now = millis();
    recorder.begin(now);
    recorder.setRecordEnabled(framOk);
    for (uint8_t t = 0; framOk && t < 4; ++t) {
        uint8_t h[4];
        if (framRead(headerAddr(t), h, 4)) {
            recorder.load(t, (uint16_t)(h[0] | (h[1] << 8)),
                          (uint16_t)(h[2] | (h[3] << 8)), now);
        }
    }
    lastMs = now;
}

// One pass per millisecond: one knob (each read every 4 ms), the recorder
// with both buttons, the DAC (only when a code changed) and the LEDs.
void loop() {
    const uint32_t now = millis();
    if (now == lastMs) {
        return;
    }
    lastMs = now;

    readKnob(knobNext);
    knobNext = (uint8_t)((knobNext + 1) & 3);
    recorder.update(now, knobs, digitalRead(REC_PIN) == LOW,
                    digitalRead(DEL_PIN) == LOW);

    uint16_t code[4];
    bool changed = false;
    for (uint8_t i = 0; i < 4; ++i) {
        code[i] = recorder.out(i);
        changed |= code[i] != dacLast[i];
    }
    if (changed) {
        dacWrite(code);
    }
    updateLeds(now);
}
