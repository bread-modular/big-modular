#pragma once

#include "bm_app.h"

#ifdef __cplusplus
extern "C" {
#endif

bm_app_t bm_load_app_fxrack();

// MIDI realtime bytes (0xF8 clock, 0xFA start) for the motion recorder.
void bm_app_fxrack_on_midi_realtime(uint8_t message);
// Call every ~10 ms from one task: drives the LED.
void bm_app_fxrack_update(uint32_t now_ms);

#ifdef __cplusplus
}
#endif
