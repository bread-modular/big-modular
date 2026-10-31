// 32bit polysynth: 9-voice MIDI poly synth after the Bread Modular 16bit
// polysynth (see include/ps_dsp.h), on the BM 32bit-5v ESP32-S3 drivers.
//
//   MIDI in (any channel)  notes -> 9 voices, oldest voice stolen when full
//   CV1 (knob 1)           release time 10 ms .. 4 s (attack 5 ms, hold = gate)
//   CV2 (knob 2)           0 = filter bypassed; up = ladder low pass closing
//                          18 kHz -> 50 Hz with rising resonance, none below 200 Hz
//   CC64 sustain pedal     note-offs held while down; CC120/123 all notes off
//   MODE button            next waveform position: saw, then 7 wavetables (vox,
//                          organ, reed, fm, sync, metal, fold), wrapping; the
//                          position is saved in NVS and restored at power-up
//   LED                    flashes on every MIDI message, brightness = waveform
//                          position (dim = saw .. bright = fold); shown steady
//                          for 0.6 s after a button press
//   OUT L / OUT R          the same mono synth signal
//
// Audio runs on core 1 (bm_audio.c). MIDI and button events reach it through a
// queue that the audio task drains every 64-frame block (1.45 ms); knob values
// are plain floats. The synth state is only touched by the audio task.

#include <stdbool.h>
#include <stdint.h>

#include "bm_audio.h"
#include "bm_button.h"
#include "bm_cv.h"
#include "bm_led.h"
#include "bm_midi.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "ps_dsp.h"

#define TAG "polysynth"

#define EVENT_QUEUE_LEN 64
#define BUTTON_DEBOUNCE_US 200000
#define OUTPUT_SCALE 32000.0f
#define LED_FLASH_US 40000
#define LED_WAVE_SHOW_US 600000
#define LED_MIN_BRIGHTNESS 0.15f
// The waveform is saved once the button has rested this long and no voice is
// sounding: an NVS write stalls flash (and so the audio task) for a moment.
#define SAVE_DELAY_US 2000000
#define NVS_NAMESPACE "polysynth"
#define NVS_KEY_WAVE "wave"
// bm_audio.c reads 128 int16 (64 stereo frames) per block.
#define BUFF_FRAMES 64

typedef enum {
    EV_NOTE_ON,
    EV_NOTE_OFF,
    EV_ALL_NOTES_OFF,
    EV_SUSTAIN,
    EV_NEXT_WAVE,
} event_type_t;

typedef struct {
    uint8_t type;
    uint8_t note;
    uint8_t velocity;
} event_t;

static ps_synth_t synth;
static QueueHandle_t events;
static volatile float knob[2] = {0.5f, 0.0f};
static volatile int64_t midi_led_until_us = 0;
static volatile ps_wave_t wave_pos = PS_WAVE_SAW;  // written by the audio task
static volatile int64_t block_us_max = 0;
static TaskHandle_t main_task;

static void push_event(uint8_t type, uint8_t note, uint8_t velocity) {
    event_t ev = {.type = type, .note = note, .velocity = velocity};
    xQueueSend(events, &ev, 0);
}

static void audio_loop(size_t n_samples, const int16_t *input, int16_t *output) {
    (void)input;
    int64_t start_us = esp_timer_get_time();

    event_t ev;
    while (xQueueReceive(events, &ev, 0) == pdTRUE) {
        switch (ev.type) {
            case EV_NOTE_ON:
                ps_note_on(&synth, ev.note, ev.velocity);
                break;
            case EV_NOTE_OFF:
                ps_note_off(&synth, ev.note);
                break;
            case EV_ALL_NOTES_OFF:
                ps_all_notes_off(&synth);
                break;
            case EV_SUSTAIN:
                ps_sustain(&synth, ev.velocity >= 64);
                break;
            case EV_NEXT_WAVE:
                ps_set_wave(&synth, (ps_wave_t)((synth.wave + 1) % PS_WAVE_COUNT));
                wave_pos = synth.wave;
                break;
        }
    }

    ps_set_release_knob(&synth, knob[0]);
    ps_set_filter_knob(&synth, knob[1]);

    for (size_t i = 0; i + 1 < n_samples; i += 2) {
        int16_t y = (int16_t)(ps_process(&synth) * OUTPUT_SCALE);
        output[i] = y;
        output[i + 1] = y;
    }

    int64_t used_us = esp_timer_get_time() - start_us;
    if (used_us > block_us_max) block_us_max = used_us;
}

static void on_note_on(uint8_t channel, uint8_t note, uint8_t velocity) {
    push_event(EV_NOTE_ON, note, velocity);
}

static void on_note_off(uint8_t channel, uint8_t note, uint8_t velocity) {
    push_event(EV_NOTE_OFF, note, 0);
}

static void on_cc(uint8_t channel, uint8_t control, uint8_t value) {
    // 64 Sustain pedal (>= 64 down), 120 All Sound Off, 123 All Notes Off
    if (control == 64) {
        push_event(EV_SUSTAIN, 0, value);
    } else if (control == 120 || control == 123) {
        push_event(EV_ALL_NOTES_OFF, 0, 0);
    }
}

// MIDI task: wake the main loop, which lights the LED at once and turns it off
// LED_FLASH_US after the last message.
static void on_midi_message(uint8_t status) {
    midi_led_until_us = esp_timer_get_time() + LED_FLASH_US;
    xTaskNotifyGive(main_task);
}

static float wave_brightness(ps_wave_t wave) {
    return LED_MIN_BRIGHTNESS + (1.0f - LED_MIN_BRIGHTNESS) * wave / (PS_WAVE_COUNT - 1);
}

static ps_wave_t load_wave(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "NVS init failed (%s): waveform not saved", esp_err_to_name(err));
        return PS_WAVE_SAW;
    }
    uint8_t wave = PS_WAVE_SAW;
    nvs_handle_t nvs;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs) == ESP_OK) {
        if (nvs_get_u8(nvs, NVS_KEY_WAVE, &wave) != ESP_OK) wave = PS_WAVE_SAW;
        nvs_close(nvs);
    }
    return wave < PS_WAVE_COUNT ? wave : PS_WAVE_SAW;
}

static void save_wave(ps_wave_t wave) {
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs);
    if (err == ESP_OK) {
        err = nvs_set_u8(nvs, NVS_KEY_WAVE, wave);
        if (err == ESP_OK) err = nvs_commit(nvs);
        nvs_close(nvs);
    }
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "waveform %d (%s) saved", wave, ps_wave_name(wave));
    } else {
        ESP_LOGW(TAG, "waveform save failed (%s)", esp_err_to_name(err));
    }
}

static void on_cv_change(uint8_t index, float value) {
    if (index < 2) knob[index] = value;
}

static void on_button(void) {
    static int64_t last_us = 0;
    int64_t now = esp_timer_get_time();
    if (now - last_us < BUTTON_DEBOUNCE_US) return;
    last_us = now;
    if (bm_is_button_pressed()) push_event(EV_NEXT_WAVE, 0, 0);
}

void app_main(void) {
    ESP_LOGI(TAG, "Starting %s_%s", FIRMWARE_NAME, FIRMWARE_VERSION);

    main_task = xTaskGetCurrentTaskHandle();
    events = xQueueCreate(EVENT_QUEUE_LEN, sizeof(event_t));
    ps_init(&synth, bm_SAMPLE_RATE);
    ps_wave_t saved_wave = load_wave();
    ps_set_wave_now(&synth, saved_wave);
    wave_pos = saved_wave;
    ESP_LOGI(TAG, "waveform %d (%s)", saved_wave, ps_wave_name(saved_wave));

    bm_setup_led();
    bm_button_config_t button_config = {
        .trigger_mode = BM_BUTTON_TRIGGER_ON_PRESS,
        .callback = on_button,
    };
    bm_setup_button(button_config);

    bm_cv_config_t cv_config = {.on_change = on_cv_change};
    bm_setup_cv(cv_config);

    bm_midi_config_t midi_config = {
        .on_note_on = on_note_on,
        .on_note_off = on_note_off,
        .on_cc_change = on_cc,
        .on_message = on_midi_message,
    };
    bm_setup_midi(midi_config);

    bm_audio_config_t audio_config = {
        .buffer_size = BUFF_FRAMES,
        .audio_loop = audio_loop,
    };
    bm_setup_audio(audio_config);

    // LED: MIDI activity flash at the waveform's brightness, shown steady after a
    // waveform change. The waveform is saved when the button and the voices rest.
    // Every 5 s the worst audio block time is logged as a CPU load (USB serial).
    const int64_t block_budget_us = (int64_t)(BUFF_FRAMES * 1000000LL / bm_SAMPLE_RATE);
    int64_t next_log_us = esp_timer_get_time() + 5000000;
    ps_wave_t shown_wave = saved_wave, saved = saved_wave;
    int64_t wave_show_until_us = 0, save_at_us = 0;
    float led = -1.0f;
    while (1) {
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(5));
        int64_t now = esp_timer_get_time();
        if (now >= next_log_us) {
            next_log_us += 5000000;
            ESP_LOGI(TAG, "voices %d, worst block %lld / %lld us, CV1 %.2f V, CV2 %.2f V",
                     ps_active_voices(&synth), block_us_max, block_budget_us,
                     bm_cv_get_volts(0), bm_cv_get_volts(1));
            block_us_max = 0;
        }

        ps_wave_t wave = wave_pos;
        if (wave != shown_wave) {
            shown_wave = wave;
            wave_show_until_us = now + LED_WAVE_SHOW_US;
            save_at_us = now + SAVE_DELAY_US;
            ESP_LOGI(TAG, "waveform %d (%s)", wave, ps_wave_name(wave));
        }
        if (wave != saved && now >= save_at_us && ps_active_voices(&synth) == 0) {
            save_wave(wave);
            saved = wave;
        }

        bool lit = now < wave_show_until_us || now < midi_led_until_us;
        float want = lit ? wave_brightness(wave) : 0.0f;
        if (want != led) {
            bm_set_led_brightness(want);
            led = want;
        }
    }
}
