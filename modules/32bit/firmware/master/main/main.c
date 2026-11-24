// 32bit master: end-of-chain processor for a live set, in place of a DAW.
//
//   IN L  kick   -> filter -> limiter
//   IN R  mix    -> filter -> 3-band dynamics keyed by the kick
//   both         -> send -> parallel compressor -> return
//   sum          -> glue compressor -> filter -> limiter -> OUT L = OUT R (mono)
//   (the effects of each strip in any order, set from the page)
//
// Every setting is made from web/index.html over the USB-C port (Web Serial,
// text protocol in ms_proto.h) and saved in flash; at power-up the module runs
// alone with the saved settings. The chain is src/ms_dsp.c (host-tested).
//
// The panel (ms_ctl.h, set up from the page and saved with the settings):
//   CV1 / CV2  each moves the settings mapped to it, each between its own two values
//   MODE       click / hold / push actions switch on / off settings (bypass,
//              channel off / solo, an effect's switch)
//   LED        led_mode: status (dim = running, slow blink = bypass), output or
//              kick level, gain reduction, MODE actions, or off; bright while an
//              input clips the converter
// They only change settings, like the page does: the audio task gets new
// coefficients at a block boundary and runs nothing more. The knobs and the
// button are polled here on core 0 every 10 ms; MIDI in is not used.

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "bm_audio.h"
#include "bm_led.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ms_dsp.h"
#include "ms_io.h"
#include "ms_params.h"
#include "ms_proto.h"
#include "nvs.h"
#include "nvs_flash.h"

#define TAG "master"

// Converter filters of the ES8388 (ADC + DAC). Not in the data used here: an
// estimate until the in -> out delay is measured on the module.
#define CODEC_DELAY_MS 1.0f
// Buffers: bm_audio.h (DMA_DESC_NUM blocks, + up to one more by the start phase).
#define BUFFER_DELAY_MS (1000.0f * (BM_AUDIO_DMA_DESC_NUM + 0.5f) * BM_AUDIO_FRAMES / bm_SAMPLE_RATE)
#define BLOCK_US (1000000.0f * BM_AUDIO_FRAMES / bm_SAMPLE_RATE)

#define NVS_NAMESPACE "master"
#define NVS_KEY "settings"

#define TICK_US 10000
#define PUSH_US 50000      // settings moved by the panel go to the page at most this often,
#define PAGE_IDLE_US 1000000  // and only while it polls (it asks for the meters every 50 ms)

static ms_dsp_t dsp;
static ms_proto_t proto;

// New coefficients from the protocol task to the audio task.
static ms_coefs_t coefs_next;
static volatile bool coefs_new;
static portMUX_TYPE coefs_mux = portMUX_INITIALIZER_UNLOCKED;

static volatile uint32_t block_us_sum, block_us_max, block_count;

// Largest meter values since the page last asked.
static ms_meters_t page_meters;
static float led_level;
static ms_led_t led;

// ---------------------------------------------------------------- audio (core 1)

static void audio_loop(size_t frames, const int32_t *in, int32_t *out) {
    int64_t start_us = esp_timer_get_time();
    if (coefs_new) {
        static ms_coefs_t c;
        portENTER_CRITICAL(&coefs_mux);
        c = coefs_next;
        coefs_new = false;
        portEXIT_CRITICAL(&coefs_mux);
        ms_dsp_set_coefs(&dsp, &c);
    }

    float kick[BM_AUDIO_FRAMES], mix[BM_AUDIO_FRAMES], y[BM_AUDIO_FRAMES];
    if (frames > BM_AUDIO_FRAMES) frames = BM_AUDIO_FRAMES;
    for (size_t i = 0; i < frames; i++) {
        kick[i] = (float)(in[2 * i] >> 8) * (1.0f / 8388608.0f);
        mix[i] = (float)(in[2 * i + 1] >> 8) * (1.0f / 8388608.0f);
    }
    ms_dsp_process(&dsp, kick, mix, y, (int)frames);
    for (size_t i = 0; i < frames; i++) {
        int32_t q = (int32_t)(y[i] * 8388607.0f) * 256;
        out[2 * i] = q;
        out[2 * i + 1] = q;
    }

    uint32_t used_us = (uint32_t)(esp_timer_get_time() - start_us);
    block_us_sum += used_us;
    block_count++;
    if (used_us > block_us_max) block_us_max = used_us;
}

// ---------------------------------------------------------------- protocol host

static void host_out(void *ctx, const char *line) {
    if (!usb_serial_jtag_is_connected()) return;
    usb_serial_jtag_write_bytes(line, strlen(line), pdMS_TO_TICKS(100));
    usb_serial_jtag_write_bytes("\n", 1, pdMS_TO_TICKS(100));
}

// A flash write stops the audio for a moment: saving is a setup step.
static bool host_save(void *ctx, const char *text) {
    nvs_handle_t nvs;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs) != ESP_OK) return false;
    esp_err_t err = nvs_set_blob(nvs, NVS_KEY, text, strlen(text) + 1);
    if (err == ESP_OK) err = nvs_commit(nvs);
    nvs_close(nvs);
    return err == ESP_OK;
}

static bool host_load(void *ctx, char *text, size_t cap) {
    nvs_handle_t nvs;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs) != ESP_OK) return false;
    size_t len = cap;
    esp_err_t err = nvs_get_blob(nvs, NVS_KEY, text, &len);
    nvs_close(nvs);
    if (err != ESP_OK || len == 0) return false;
    text[len - 1] = 0;
    return true;
}

static void host_apply(void *ctx, const float values[MS_P_COUNT]) {
    static ms_coefs_t c;
    ms_coefs_from_params(values, (float)bm_SAMPLE_RATE, BM_AUDIO_FRAMES, &c);
    portENTER_CRITICAL(&coefs_mux);
    coefs_next = c;
    coefs_new = true;
    portEXIT_CRITICAL(&coefs_mux);
}

static void merge_meters(ms_meters_t *into, const ms_meters_t *from) {
    const float *src = (const float *)from;
    float *dst = (float *)into;
    for (size_t i = 0; i < sizeof(ms_meters_t) / sizeof(float); i++) {
        if (src[i] > dst[i]) dst[i] = src[i];
    }
}

static void host_meters(void *ctx, ms_meters_t *m) {
    *m = page_meters;
    memset(&page_meters, 0, sizeof(page_meters));
}

static void host_status(void *ctx, ms_status_t *st) {
    st->fs = (float)bm_SAMPLE_RATE;
    st->block = BM_AUDIO_FRAMES;
    st->io_ms = CODEC_DELAY_MS + BUFFER_DELAY_MS;
    uint32_t sum = block_us_sum, count = block_count, max = block_us_max;
    block_us_sum = 0;
    block_count = 0;
    block_us_max = 0;
    st->cpu = count ? 100.0f * (float)sum / ((float)count * BLOCK_US) : 0.0f;
    st->cpu_max = 100.0f * (float)max / BLOCK_US;
    st->led = led_level;
}

// ---------------------------------------------------------------- main task

static void setup_storage(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

static void setup_serial(void) {
    // Room for the whole `desc` answer; the log goes through the same driver.
    usb_serial_jtag_driver_config_t config = {.tx_buffer_size = 12288, .rx_buffer_size = 1024};
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&config));
    usb_serial_jtag_vfs_use_driver();
}

static void update_led(int64_t now_us, float dt_s, const ms_meters_t *m) {
    float level = ms_led_run(&led, proto.values, m, ms_ctl_engaged(&proto.ctl, proto.values),
                             (uint32_t)(now_us / 1000), dt_s);
    if (level != led_level) bm_set_led_brightness(level);
    led_level = level;
}

void app_main(void) {
    ESP_LOGI(TAG, "Starting %s_%s", FIRMWARE_NAME, FIRMWARE_VERSION);
    bm_setup_led();
    led_level = -1.0f;
    ms_io_setup();
    setup_storage();
    setup_serial();

    // Saved settings (or the factory ones) into the chain, then start the audio.
    ms_host_t host = {
        .out = host_out,
        .save = host_save,
        .load = host_load,
        .apply = host_apply,
        .meters = host_meters,
        .status = host_status,
    };
    ms_proto_init(&proto, &host);
    ms_dsp_init(&dsp, &coefs_next);
    coefs_new = false;
    bm_audio_config_t audio_config = {.audio_loop = audio_loop};
    bm_setup_audio(audio_config);

    static char line[160];
    size_t line_len = 0;
    bool line_overflow = false;
    int64_t next_tick_us = 0, next_push_us = 0, last_tick_us = esp_timer_get_time(), last_rx_us = -PAGE_IDLE_US;
    while (1) {
        uint8_t rx[64];
        int n = usb_serial_jtag_read_bytes(rx, sizeof(rx), pdMS_TO_TICKS(10));
        if (n > 0) last_rx_us = esp_timer_get_time();
        for (int i = 0; i < n; i++) {
            if (rx[i] != '\n' && rx[i] != '\r') {
                if (line_len < sizeof(line) - 1) line[line_len++] = (char)rx[i];
                else line_overflow = true;
                continue;
            }
            line[line_len] = 0;
            if (line_overflow) host_out(NULL, "err|line too long");
            else if (line_len) ms_proto_line(&proto, line);
            line_len = 0;
            line_overflow = false;
        }

        int64_t now_us = esp_timer_get_time();
        if (now_us < next_tick_us) continue;
        next_tick_us = now_us + TICK_US;
        float dt_s = (float)(now_us - last_tick_us) * 1e-6f;
        last_tick_us = now_us;

        // The panel: knobs and button into the settings (applied like a `set`).
        float cv[2];
        ms_io_read_cv(cv);
        ms_proto_controls(&proto, cv, ms_io_button(), (uint32_t)(now_us / 1000));
        if (now_us >= next_push_us && now_us - last_rx_us < PAGE_IDLE_US) {
            next_push_us = now_us + PUSH_US;
            ms_proto_push(&proto);
        }

        ms_meters_t fresh;
        ms_dsp_take_meters(&dsp, &fresh);
        merge_meters(&page_meters, &fresh);
        update_led(now_us, dt_s, &fresh);
    }
}
