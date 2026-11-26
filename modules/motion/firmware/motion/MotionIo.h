#pragma once

#include <stdint.h>

// MOTION board constants and the pure helpers motion.ino uses around the
// recorder (knob conditioning, LED brightness, FRAM layout).
// No Arduino dependency, so the host test checks them too.
namespace motion {

static const uint16_t KNOB_MAX = 4095;

// ---- FRAM (MB85RC256V, 32 KB, I2C 0x50) ------------------------------------
// 0x0000  'M' 'O' 'T' FRAM_VERSION
// 0x0004  reserved (was the range byte; ignored since the range was removed)
// 0x0008  track t header at 0x0008 + 4 t: frames (u16 LE, 0 = no take),
//         gain (u16 LE, 0..4096 = 0..1)
// 0x0040  track t frames at 0x0040 + t * MAX_FRAMES * 2 (u16 LE, DAC codes
//         0..4095, 2048 = 0 V)
static const uint8_t FRAM_I2C = 0x50;
static const uint16_t FRAM_SIZE = 32768u;
static const uint8_t FRAM_VERSION = 2;  // 1: knob positions + offset reference
static const uint16_t FRAM_HEADERS = 0x0008;
static const uint16_t FRAM_DATA = 0x0040;
// (32768 - 64) / 4 tracks / 2 bytes: 4088 frames = 81.7 s at 50 frames/s.
static const uint16_t MAX_FRAMES = (FRAM_SIZE - FRAM_DATA) / 4 / 2;

inline uint16_t headerAddr(uint8_t track) {
    return (uint16_t)(FRAM_HEADERS + 4u * track);
}
inline uint16_t frameAddr(uint8_t track, uint16_t frame) {
    return (uint16_t)(FRAM_DATA + (uint16_t)track * MAX_FRAMES * 2u +
                      2u * frame);
}

// ---- DAC (MCP4728, I2C 0x60, VREF = VDD = +5VA) ----------------------------
// Output stage: Vout = 2 x Vdac - (+5VA), so code 0 = -5 V, 2048 = 0 V,
// 4095 = +5 V. The recorder works in these codes; a knob maps 1:1.
static const uint8_t DAC_I2C = 0x60;
static const uint16_t DAC_ZERO = 2048;

// ---- Knobs -----------------------------------------------------------------
// 12-bit ADC reading (16x accumulated) -> one-pole low-pass (a quarter per
// reading, each knob read every 4 ms: ~16 ms) -> KNOB_END counts of dead zone
// at each end so the knob reaches 0 and 4095 -> 2-count hysteresis so a
// resting knob does not flicker the output.
static const uint16_t KNOB_END = 16;
static const uint16_t KNOB_HYST = 2;

struct KnobFilter {
    uint16_t acc = 0;       // 4 x filtered reading
    uint16_t value = 0;     // conditioned 0..KNOB_MAX
    bool primed = false;

    uint16_t step(uint16_t raw) {
        if (raw > KNOB_MAX) raw = KNOB_MAX;
        if (!primed) {
            acc = (uint16_t)(raw << 2);
        } else {
            acc = (uint16_t)((int32_t)acc + (int32_t)raw - (int32_t)(acc >> 2));
        }
        const int32_t f = (acc + 2) >> 2;
        int32_t v = (f - KNOB_END) * KNOB_MAX / (KNOB_MAX - 2 * KNOB_END);
        if (v < 0) v = 0;
        if (v > KNOB_MAX) v = KNOB_MAX;
        const int32_t d = v - (int32_t)value;
        if (!primed || v == 0 || v == KNOB_MAX || d >= KNOB_HYST ||
            d <= -(int32_t)KNOB_HYST) {
            value = (uint16_t)v;
        }
        primed = true;
        return value;
    }
};

// ---- LEDs ------------------------------------------------------------------
// TCA0 split-mode PWM, 0..254 (LPER / HPER 254). Motion LED: brightness =
// output voltage, 0 V off, 5 V full, squared so it looks even; a negative
// voltage blinks (blinkOn = the lit half of the blink). 0 = off.
static const uint8_t LED_FULL = 254;
static const uint32_t LED_BLINK_MS = 125;  // half period: 4 blinks a second

inline uint8_t motionLed(uint16_t code, bool blinkOn) {
    if (code > KNOB_MAX) code = KNOB_MAX;
    int32_t v = (int32_t)code - DAC_ZERO;  // -2048..2047
    if (v < 0) {
        if (!blinkOn) return 0;
        v = v < -2047 ? 2047 : -v;
    }
    const uint32_t v8 = (uint32_t)v >> 3;  // 0..255
    return (uint8_t)(v8 * v8 * LED_FULL / (255u * 255u));
}

}  // namespace motion
