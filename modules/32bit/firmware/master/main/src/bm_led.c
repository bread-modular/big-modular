#include "bm_led.h"

#include <math.h>

#include "driver/ledc.h"
#include "esp_err.h"

#define LED_PIN GPIO_NUM_18
// 13-bit PWM at 5 kHz (no flicker, no audible coil / supply noise).
#define LED_MODE LEDC_LOW_SPEED_MODE
#define LED_CHANNEL LEDC_CHANNEL_0
#define LED_RES LEDC_TIMER_13_BIT
#define LED_MAX_DUTY ((1u << 13) - 1)

void bm_setup_led(void) {
    ledc_timer_config_t timer = {
        .speed_mode = LED_MODE,
        .duty_resolution = LED_RES,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 5000,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer));
    ledc_channel_config_t channel = {
        .gpio_num = LED_PIN,
        .speed_mode = LED_MODE,
        .channel = LED_CHANNEL,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&channel));
}

void bm_set_led_brightness(float level) {
    if (level < 0.0f) level = 0.0f;
    if (level > 1.0f) level = 1.0f;
    // Perceptual (gamma 2.2) brightness to PWM duty.
    float duty = powf(level, 2.2f) * LED_MAX_DUTY;
    ledc_set_duty(LED_MODE, LED_CHANNEL, (uint32_t)(duty + 0.5f));
    ledc_update_duty(LED_MODE, LED_CHANNEL);
}

void bm_set_led_state(bool on) {
    bm_set_led_brightness(on ? 1.0f : 0.0f);
}
