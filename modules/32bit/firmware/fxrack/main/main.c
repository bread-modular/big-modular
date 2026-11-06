// 32bit fxrack: the Bread Modular 32bit-5v fxrack app (main/src/apps/bm_app_fxrack.c)
// on the 32bit module drivers (R1 pins, docs/firmware-pins.md).
//
//   IN L -> delay (CV1 time, CV2 feedback) -> hall reverb (MIDI CC 20 decay, CC 21 mix) -> OUT L
//   IN R -> short comb delay (MIDI CC 22 time 1..50 ms, CC 23 feedback) -> OUT R
//   MODE press                   4-bar motion recorder on MIDI clock: CV1, CV2 and
//                                CC 20..23 (LED blinks, then solid while looping)
//   MIDI clock                   delay range = half a beat (120 BPM until a clock arrives)
//
// As BM main.c, except: no BM web-installer USB serial commands (the USB port
// carries the log), 64-frame audio blocks (bm_audio.c), and a 5 s log line with
// the worst audio block time, BPM and the CV voltages.

#include <stdbool.h>
#include <stdint.h>

#include "apps/bm_app_fxrack.h"
#include "bm_app.h"
#include "bm_audio.h"
#include "bm_button.h"
#include "bm_cv.h"
#include "bm_led.h"
#include "bm_midi.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define TAG "fxrack"

// bm_audio.c reads 128 int16 (64 stereo frames) per block.
#define BUFF_FRAMES 64

static bm_app_t current_app;
static volatile int64_t block_us_max = 0;
static volatile uint16_t last_bpm = 120;

static void audio_loop(size_t n_samples, const int16_t *input, int16_t *output) {
    int64_t start_us = esp_timer_get_time();
    current_app.process_audio(n_samples, input, output);
    int64_t used_us = esp_timer_get_time() - start_us;
    if (used_us > block_us_max) block_us_max = used_us;
}

static void on_midi_bpm(uint16_t bpm) {
    last_bpm = bpm;
    current_app.on_midi_bpm(bpm);
}

static void on_midi_note_on(uint8_t channel, uint8_t note, uint8_t velocity) {
    current_app.on_midi_note_on(channel, note, velocity);
}

static void on_midi_note_off(uint8_t channel, uint8_t note, uint8_t velocity) {
    current_app.on_midi_note_off(channel, note, velocity);
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    current_app.on_midi_cc(channel, control, value);
}

static void on_midi_realtime(uint8_t message) {
    bm_app_fxrack_on_midi_realtime(message);
}

static void on_cv_change(uint8_t index, float value) {
    current_app.on_cv_change(index, value);
}

static void on_button(void) {
    current_app.on_button_event(bm_is_button_pressed());
}

void app_main(void) {
    current_app = bm_load_app_fxrack();
    ESP_LOGI(TAG, "Starting %s_%s", FIRMWARE_NAME, FIRMWARE_VERSION);

    bm_button_config_t button_config = {
        .trigger_mode = BM_BUTTON_TRIGGER_ON_ANY,
        .callback = on_button,
    };
    bm_setup_button(button_config);
    bm_setup_led();

    bm_app_host_t host = {.sample_rate = bm_SAMPLE_RATE};
    current_app.init(host);
    // Initial BPM sets the delay range until a MIDI clock arrives.
    on_midi_bpm(120);

    // CV after init: the first reading reaches the initialised delay.
    bm_cv_config_t cv_config = {.on_change = on_cv_change};
    bm_setup_cv(cv_config);

    bm_midi_config_t midi_config = {
        .on_note_on = on_midi_note_on,
        .on_note_off = on_midi_note_off,
        .on_cc_change = on_midi_cc,
        .on_bpm = on_midi_bpm,
        .on_realtime = on_midi_realtime,
    };
    bm_setup_midi(midi_config);

    bm_audio_config_t audio_config = {
        .buffer_size = BUFF_FRAMES,
        .audio_loop = audio_loop,
    };
    bm_setup_audio(audio_config);

    // Every 10 ms the LED; every 5 s the worst audio block time is logged as a
    // CPU load (USB serial).
    const int64_t block_budget_us = (int64_t)(BUFF_FRAMES * 1000000LL / bm_SAMPLE_RATE);
    int64_t next_log_us = esp_timer_get_time() + 5000000;
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10));
        int64_t now_us = esp_timer_get_time();
        bm_app_fxrack_update((uint32_t)(now_us / 1000));
        if (now_us < next_log_us) continue;
        next_log_us += 5000000;
        ESP_LOGI(TAG, "worst block %lld / %lld us, BPM %u, CV1 %.2f V, CV2 %.2f V",
                 block_us_max, block_budget_us, last_bpm,
                 bm_cv_get_volts(0), bm_cv_get_volts(1));
        block_us_max = 0;
    }
}
