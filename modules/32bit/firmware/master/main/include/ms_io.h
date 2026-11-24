#pragma once

// The panel's CV knobs and MODE button, read by polling from the main task (no
// task, no interrupt of its own). The LED is bm_led.h.

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void ms_io_setup(void);
// CV1 / CV2 as 0..1 (knob x CV, 0..+5 V at the jack; unpatched the knob alone).
void ms_io_read_cv(float cv[2]);
bool ms_io_button(void);  // true while MODE is pressed (not debounced)

#ifdef __cplusplus
}
#endif
