// CV knobs and MODE button of the S3 / ES1 board (docs/firmware-pins.md): CV1 on
// GPIO1 (ADC1 CH0), CV2 on GPIO2 (ADC1 CH1), MODE on GPIO8 to GND. The S4 board
// has them elsewhere (POT1 GPIO7, POT2 GPIO6, MODE GPIO38, LED GPIO39) and no
// CS4272 driver in this firmware yet.
//
// Each CV goes through a +-12 V follower and level shift:
//   V_adc = 0.276 x V_cv + 1.628 V
// unpatched the jack is normalled to +5 V through the knob, so the knob spans
// 0..+5 V = 1.63..3.01 V at the ADC; that maps to 0..1, with a 2 % dead zone at
// each end so the knob reaches 0 and 1 (as polysynth's bm_cv.c).
#include "ms_io.h"

#include "driver/gpio.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"

#define TAG "ms_io"

#define CV_ADC_UNIT ADC_UNIT_1
#define CV_ATTEN ADC_ATTEN_DB_12
#define CV_GAIN 0.276f        // V_adc per V_cv
#define CV_OFFSET_MV 1628.0f  // V_adc at 0 V CV
#define CV_FULL_SCALE_V 5.0f
#define CV_DEAD_ZONE 0.02f
#define CV_AVERAGE 4
#define BUTTON_PIN GPIO_NUM_8

static const adc_channel_t channels[2] = {ADC_CHANNEL_0, ADC_CHANNEL_1};
static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t cali;
static bool adc_ok, cali_ok;

void ms_io_setup(void) {
    gpio_config_t button = {
        .pin_bit_mask = 1ULL << BUTTON_PIN,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&button);

    adc_oneshot_unit_init_cfg_t unit = {.unit_id = CV_ADC_UNIT};
    adc_ok = adc_oneshot_new_unit(&unit, &adc) == ESP_OK;
    if (!adc_ok) {
        ESP_LOGW(TAG, "no ADC: the CV knobs are not read");
        return;
    }
    adc_oneshot_chan_cfg_t chan = {.bitwidth = ADC_BITWIDTH_DEFAULT, .atten = CV_ATTEN};
    for (int i = 0; i < 2; i++) adc_oneshot_config_channel(adc, channels[i], &chan);
    adc_cali_curve_fitting_config_t cal = {.unit_id = CV_ADC_UNIT, .atten = CV_ATTEN, .bitwidth = ADC_BITWIDTH_DEFAULT};
    cali_ok = adc_cali_create_scheme_curve_fitting(&cal, &cali) == ESP_OK;
    if (!cali_ok) ESP_LOGW(TAG, "ADC calibration unavailable, using raw scaling");
}

static float read_mv(adc_channel_t channel) {
    int sum = 0;
    for (int i = 0; i < CV_AVERAGE; i++) {
        int value = 0;
        if (cali_ok) {
            adc_oneshot_get_calibrated_result(adc, cali, channel, &value);
        } else {
            adc_oneshot_read(adc, channel, &value);
            value = value * 3100 / 4095;  // ~3100 mV full scale at 12 dB
        }
        sum += value;
    }
    return (float)sum / CV_AVERAGE;
}

void ms_io_read_cv(float cv[2]) {
    for (int i = 0; i < 2; i++) {
        if (!adc_ok) {
            cv[i] = 0.0f;
            continue;
        }
        float volts = (read_mv(channels[i]) - CV_OFFSET_MV) / CV_GAIN / 1000.0f;
        float x = (volts / CV_FULL_SCALE_V - CV_DEAD_ZONE) / (1.0f - 2.0f * CV_DEAD_ZONE);
        cv[i] = x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x);
    }
}

bool ms_io_button(void) {
    return gpio_get_level(BUTTON_PIN) == 0;  // pulled up, to GND when pressed
}
