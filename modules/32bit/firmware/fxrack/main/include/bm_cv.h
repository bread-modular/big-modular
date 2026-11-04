#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

// CV1 / CV2 (knob x CV, normalled to +5 V) on the 32bit module.
// value: 0..1 knob position (0..+5 V at the jack); see bm_cv.c for the scaling.
typedef void (*bm_cv_change_callback_t)(uint8_t cv_index, float value);

typedef struct {
    bm_cv_change_callback_t on_change;
} bm_cv_config_t;

void bm_setup_cv(bm_cv_config_t config);

// Latest values (index 0 = CV1, 1 = CV2).
float bm_cv_get_norm(uint8_t index);
float bm_cv_get_volts(uint8_t index);

#ifdef __cplusplus
}
#endif
