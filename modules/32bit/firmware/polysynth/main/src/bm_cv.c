// CV inputs for the 32bit module (BM 32bit-5v bm_cv.c, reworked for R1).
//
// R1 moved the CV ADCs to IO1 / IO2 (ADC1 CH0 / CH1; BM IO9 / IO10) and each CV
// goes through a +-12 V follower and level shift (docs/firmware-pins.md):
//   V_adc = 0.276 x V_cv + 1.628 V
// The jack is normalled to +5 V through the attenuator, so unpatched the knob
// spans 0..+5 V = 1.63..3.01 V at the ADC. That range maps to 0..1 here, with a
// small dead zone at both ends so the knob reliably reaches 0 and 1. Patched CV
// below 0 V reads 0, above +5 V reads 1.
#include "bm_cv.h"

#include <math.h>
#include <stdbool.h>

#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define CV_ADC_UNIT ADC_UNIT_1
#define CV1_ADC_CHANNEL ADC_CHANNEL_0  // GPIO1
#define CV2_ADC_CHANNEL ADC_CHANNEL_1  // GPIO2
#define CV_ATTEN ADC_ATTEN_DB_12
#define CV_NUM_CHANNELS 2

#define CV_GAIN 0.276f          // V_adc per V_cv
#define CV_OFFSET_MV 1628.0f    // V_adc at 0 V CV
#define CV_FULL_SCALE_V 5.0f    // knob fully up, unpatched
#define CV_DEAD_ZONE 0.02f      // of the 0..1 range, at each end

#define CV_POLL_MS 5
#define CV_AVERAGE 4
#define CV_CHANGE_THRESHOLD 0.004f

static const char *TAG = "bm_cv";

static const adc_channel_t channels[CV_NUM_CHANNELS] = {CV1_ADC_CHANNEL, CV2_ADC_CHANNEL};
static adc_oneshot_unit_handle_t adc_handle;
static adc_cali_handle_t cali_handle;
static bool cali_ok = false;
static bm_cv_change_callback_t cv_change_callback = NULL;
static volatile float cv_volts[CV_NUM_CHANNELS];
static volatile float cv_norm[CV_NUM_CHANNELS];

static float read_mv(adc_channel_t channel) {
    int sum = 0;
    for (int i = 0; i < CV_AVERAGE; i++) {
        int value = 0;
        if (cali_ok) {
            adc_oneshot_get_calibrated_result(adc_handle, cali_handle, channel, &value);
        } else {
            // Uncalibrated fallback: ~3100 mV full scale at 12 dB.
            adc_oneshot_read(adc_handle, channel, &value);
            value = value * 3100 / 4095;
        }
        sum += value;
    }
    return (float)sum / CV_AVERAGE;
}

static float volts_to_norm(float volts) {
    float x = volts / CV_FULL_SCALE_V;
    x = (x - CV_DEAD_ZONE) / (1.0f - 2.0f * CV_DEAD_ZONE);
    return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x);
}

static void cv_poll_task(void *args) {
    float last[CV_NUM_CHANNELS] = {-1.0f, -1.0f};
    while (1) {
        for (uint8_t i = 0; i < CV_NUM_CHANNELS; i++) {
            float volts = (read_mv(channels[i]) - CV_OFFSET_MV) / CV_GAIN / 1000.0f;
            float norm = volts_to_norm(volts);
            cv_volts[i] = volts;
            cv_norm[i] = norm;
            // Emit on change; always emit the end stops so 0 and 1 are exact.
            bool at_end = (norm == 0.0f || norm == 1.0f) && norm != last[i];
            if (last[i] < 0.0f || fabsf(norm - last[i]) >= CV_CHANGE_THRESHOLD || at_end) {
                last[i] = norm;
                if (cv_change_callback) cv_change_callback(i, norm);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(CV_POLL_MS));
    }
}

void bm_setup_cv(bm_cv_config_t config) {
    cv_change_callback = config.on_change;

    adc_oneshot_unit_init_cfg_t init_config = {.unit_id = CV_ADC_UNIT};
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config, &adc_handle));
    adc_oneshot_chan_cfg_t channel_config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = CV_ATTEN,
    };
    for (int i = 0; i < CV_NUM_CHANNELS; i++) {
        ESP_ERROR_CHECK(adc_oneshot_config_channel(adc_handle, channels[i], &channel_config));
    }

    adc_cali_curve_fitting_config_t cali_config = {
        .unit_id = CV_ADC_UNIT,
        .atten = CV_ATTEN,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    cali_ok = adc_cali_create_scheme_curve_fitting(&cali_config, &cali_handle) == ESP_OK;
    if (!cali_ok) {
        ESP_LOGW(TAG, "ADC calibration unavailable, using raw scaling");
    }

    xTaskCreatePinnedToCore(cv_poll_task, "bm_cv_poll_task", 4096, NULL, 5, NULL, PRO_CPU_NUM);
}

float bm_cv_get_norm(uint8_t index) {
    return index < CV_NUM_CHANNELS ? cv_norm[index] : 0.0f;
}

float bm_cv_get_volts(uint8_t index) {
    return index < CV_NUM_CHANNELS ? cv_volts[index] : 0.0f;
}
