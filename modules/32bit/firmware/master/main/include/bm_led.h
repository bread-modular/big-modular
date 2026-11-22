#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void bm_setup_led(void);
void bm_set_led_state(bool on);
// 0..1 perceived brightness (PWM, gamma corrected). Call from one task only.
void bm_set_led_brightness(float level);

#ifdef __cplusplus
}
#endif
