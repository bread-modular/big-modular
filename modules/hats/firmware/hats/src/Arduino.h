#ifndef HATS_ARDUINO_SHIM_H
#define HATS_ARDUINO_SHIM_H

// ============================================================================
// Minimal Arduino API on the STM32G071 for the shared CvRecorder.h
// (opt/attiny1616-tools/lib/CvRecorder), which only needs GPIO and millis().
// Pin numbers: PIN_PA(n) / PIN_PB(n). millis() counts the 1 ms SysTick in
// main.cpp.
// ============================================================================

#include <stdint.h>
#include "stm32g0xx.h"

#define HIGH 1
#define LOW  0

#define INPUT        0
#define OUTPUT       1
#define INPUT_PULLUP 2

#define PIN_PA(n) ((uint8_t)(n))
#define PIN_PB(n) ((uint8_t)(16 + (n)))

extern volatile uint32_t g_millis;

inline unsigned long millis() { return g_millis; }

inline GPIO_TypeDef *pinPort(uint8_t pin) { return pin < 16 ? GPIOA : GPIOB; }

inline void pinMode(uint8_t pin, uint8_t mode) {
    GPIO_TypeDef *port = pinPort(pin);
    uint32_t n = pin & 15;
    port->MODER = (port->MODER & ~(3u << (2 * n))) | ((mode == OUTPUT ? 1u : 0u) << (2 * n));
    port->PUPDR = (port->PUPDR & ~(3u << (2 * n))) | ((mode == INPUT_PULLUP ? 1u : 0u) << (2 * n));
}

inline void digitalWrite(uint8_t pin, uint8_t val) {
    pinPort(pin)->BSRR = val ? (1u << (pin & 15)) : (1u << ((pin & 15) + 16));
}

inline int digitalRead(uint8_t pin) {
    return (pinPort(pin)->IDR >> (pin & 15)) & 1u ? HIGH : LOW;
}

#endif  // HATS_ARDUINO_SHIM_H
