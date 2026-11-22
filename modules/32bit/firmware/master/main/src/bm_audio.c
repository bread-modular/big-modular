#include "bm_audio.h"

#include <string.h>

#include "bm_es8388.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/projdefs.h"
#include "freertos/task.h"

// The fxrack / polysynth bm_audio.c with 24-bit samples (codec word length 24,
// 32-bit I2S slots) and 16-frame blocks.

#define LOG_TAG "bm_audio"
#define BUFF_LEN (2 * BM_AUDIO_FRAMES)

static i2s_chan_handle_t tx_chan = NULL;
static i2s_chan_handle_t rx_chan = NULL;

static int32_t rxbuf[BUFF_LEN];
static int32_t txbuf[BUFF_LEN];

static bm_audio_loop_t audio_loop = NULL;

static void default_audio_loop(size_t n_frames, const int32_t *input, int32_t *output) {
    memcpy(output, input, 2 * n_frames * sizeof(int32_t));
}

static void audio_task(void *arg) {
    size_t n = 0;

    // Small delay so clocks settle after enable
    vTaskDelay(pdMS_TO_TICKS(10));

    for (;;) {
        ESP_ERROR_CHECK(i2s_channel_read(rx_chan, rxbuf, sizeof(rxbuf), &n, portMAX_DELAY));

        audio_loop(n / (2 * sizeof(int32_t)), rxbuf, txbuf);

        size_t written = 0;
        ESP_ERROR_CHECK(i2s_channel_write(tx_chan, txbuf, n, &written, portMAX_DELAY));
    }
}

void bm_setup_audio(bm_audio_config_t config) {
    if (config.audio_loop == NULL) {
        ESP_LOGW(LOG_TAG, "No audio_loop provided. assigning default io pipe.");
        audio_loop = default_audio_loop;
    } else {
        audio_loop = config.audio_loop;
    }

    // 1) setup es8388
    bm_es8388_t es = {0};
    // 32bit R1: SDA IO39, SCL IO38 (BM 32bit-5v: IO48 / IO47), docs/firmware-pins.md
    ESP_ERROR_CHECK(bm_es8388_init_new_bus(&es, I2C_NUM_0, GPIO_NUM_39, GPIO_NUM_38, 400000));
    ESP_ERROR_CHECK(bm_es8388_init_sequence(&es));
    // 24-bit I2S words on both converters (the init sequence sets 16: 0x0C / 0x18).
    // ADCCONTROL4 bits 4:2 and DACCONTROL1 bits 5:3 = 000, format bits = I2S.
    ESP_ERROR_CHECK(bm_es8388_write_reg(&es, ES8388_ADCCONTROL4, 0x00));
    ESP_ERROR_CHECK(bm_es8388_write_reg(&es, ES8388_DACCONTROL1, 0x00));

    bm_es8388_output_select(&es, OUT1);
    // 32bit R1: audio inputs on LIN2/RIN2 (BM: LIN1/RIN1)
    bm_es8388_input_select(&es, IN2);
    // Volume 30 is 0 dB. Max is 33 (+4.5 dB), but ~0.9 Vrms full scale on 3.3 V
    // has only ~2 dB to the rail: keep 0 dB, the level is made digitally.
    bm_es8388_set_output_volume(&es, 30);
    bm_es8388_set_input_gain(&es, 0);
    bm_es8388_set_alc_mode(&es, DISABLE);
    bm_es8388_mixer_source_select(&es, MIXADC, MIXADC);
    bm_es8388_mixer_source_control_combined(&es, DACOUT);

    // 2) Allocate a full-duplex pair on I2S0 as master
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    // Latency: a block is read when its last frame has arrived and is played
    // dma_desc_num - 1 buffers after it is written: 3 x 16 frames = 1.1 ms at
    // 44.1 kHz (fxrack / polysynth: 3 x 64 = 4.4 ms).
    chan_cfg.dma_desc_num = BM_AUDIO_DMA_DESC_NUM;
    chan_cfg.dma_frame_num = BM_AUDIO_FRAMES;
    // A late block plays as silence, not as the old buffer again.
    chan_cfg.auto_clear = true;
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_chan, &rx_chan));

    // 3) Configure std (Philips) mode for BOTH channels: 32-bit slots, the codec
    //    takes / fills the upper 24 bits. BCLK = 64 fs, MCLK = 256 fs as before.
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(bm_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = GPIO_NUM_21,
            .bclk = GPIO_NUM_14,
            .ws = GPIO_NUM_12,
            .dout = GPIO_NUM_13,
            .din = GPIO_NUM_11,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };

    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_chan, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_chan, &std_cfg));

    // 4) Enable both channels (starts the clocks)
    ESP_ERROR_CHECK(i2s_channel_enable(tx_chan));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_chan));

    // 5) Run audio loop in core 1 at the highest priority to avoid underruns
    const UBaseType_t audio_task_priority = configMAX_PRIORITIES - 1;
    xTaskCreatePinnedToCore(audio_task, "audio_task", 12288, NULL, audio_task_priority, NULL, APP_CPU_NUM);
}
