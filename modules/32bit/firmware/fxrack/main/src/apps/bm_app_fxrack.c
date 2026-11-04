// Bread Modular 32bit-5v fxrack app, ported to the 32bit module. Changes vs BM:
// the CV values are the 32bit knob positions (bm_cv.c: 0..1 = 0..+5 V), a MIDI
// clock BPM change re-applies the CV1 delay time (the CV driver only reports
// changes), the BPM range is clamped to the left delay buffer, the pipe-delay
// option is removed (the reverb gets the input only, BM's default), and MODE runs
// the 4-bar CV1/CV2 + CC 20..23 motion recorder (lib/bm_motion_recorder.h, as the
// 8bit/16bit recorders).
#include "apps/bm_app_fxrack.h"
#include "lib/bm_utils.h"
#include "lib/bm_param.h"
#include "bm_led.h"
#include "bm_button.h"
#include "bm_midi.h"
#include "bm_audio.h"
#include "audio/bm_comb_filter.h"
#include "audio/bm_classic_reverb.h"
#include "lib/bm_motion_recorder.h"
#include "esp_timer.h"
#include <stddef.h>

#ifdef ESP_PLATFORM
#include "freertos/FreeRTOS.h"
// The recorder is reached from the MIDI, CV, button and main tasks.
static portMUX_TYPE rec_mux = portMUX_INITIALIZER_UNLOCKED;
#define REC_LOCK() portENTER_CRITICAL(&rec_mux)
#define REC_UNLOCK() portEXIT_CRITICAL(&rec_mux)
#else
#define REC_LOCK()
#define REC_UNLOCK()
#endif

#define MAX_BUFFER_LEN_LEFT bmMS_TO_SAMPLES(2000)
#define MAX_BUFFER_LEN_RIGHT bmMS_TO_SAMPLES(50)
#define BUTTON_DEBOUNCE_US 30000
#define REC_BLINK_MS 150

static bm_comb_filter_t delay_left;
static bm_classic_reverb_t reverb_left;
static float delay_mix;
static float reverb_mix;
static bm_comb_filter_t delay_right;

static size_t sample_rate;
static float delay_left_cv = 0.0f;

static bm_motion_recorder_t recorder;
static bool button_down = false;
static int64_t button_edge_us = 0;
static uint32_t rec_blink_start_ms = 0;
static bool rec_blink_restart = false;
static float led_level = -1.0f;


static void apply_cv(uint8_t index, float value);
static void apply_cc(uint8_t control, uint8_t value);

// MODE press: the recorder. Leaving PLAYBACK re-applies the live values.
static void on_recorder_press(void) {
    float live_cv[BM_REC_CV_COUNT];
    uint8_t live_cc[BM_REC_CC_COUNT];
    REC_LOCK();
    bool was_playback = recorder.state == BM_REC_PLAYBACK;
    bm_rec_press(&recorder);
    for (int i = 0; i < BM_REC_CV_COUNT; i++) live_cv[i] = recorder.live_cv[i];
    for (int i = 0; i < BM_REC_CC_COUNT; i++) live_cc[i] = recorder.live_cc[i];
    REC_UNLOCK();
    rec_blink_restart = true;

    if (!was_playback) return;
    for (int i = 0; i < BM_REC_CV_COUNT; i++) apply_cv(i, live_cv[i]);
    for (int i = 0; i < BM_REC_CC_COUNT; i++) {
        if (live_cc[i] != BM_REC_CC_UNSET) apply_cc(BM_REC_FIRST_CC + i, live_cc[i]);
    }
}

// Every button edge (task context). Edges within 30 ms of the last accepted one
// are contact bounce. A press runs the recorder.
static void on_button_event(bool pressed) {
    int64_t now = esp_timer_get_time();
    if (pressed == button_down || now - button_edge_us < BUTTON_DEBOUNCE_US) {
        return;
    }
    button_down = pressed;
    button_edge_us = now;
    if (pressed) on_recorder_press();
}

static void apply_cc(uint8_t control, uint8_t value) {
    // for left channel
    if (control == BM_MCC_BANK_A_CV1) {
        float rt60 = bm_utils_map_range(value, 0.0, 127.0, 0.1, 3.0);
        bm_classic_reverb_set_rt60(&reverb_left, rt60);
        return;
    }

    if (control == BM_MCC_BANK_A_CV2) {
        reverb_mix = (float)value / 127.0;
        return;
    }

    // for right channel
    if (control == BM_MCC_BANK_A_CV3) {
        float cc_norm = (float)value / 127.0f;
        float delay_samples = bm_utils_map_range(cc_norm, 0.0, 1.0, bmMS_TO_SAMPLES(1), MAX_BUFFER_LEN_RIGHT -1);
        bm_param_set(&delay_right.delay_length, delay_samples);
        return;
    }

    if (control == BM_MCC_BANK_A_CV4) {
        float cc_norm = (float)value / 127.0f;
        float feedback = 0.5 + cc_norm * 0.5;
        bm_param_set(&delay_right.feedback, feedback);
        return;
    }
}

static void apply_cv(uint8_t index, float value) {
    if (index == 0) {
        delay_left_cv = value;
        bm_comb_filter_set_delay_length(&delay_left, value);
        return;
    }

    if (index == 1) {
        bm_comb_filter_set_feedback(&delay_left, value);
        return;
    }
}

static void on_midi_cc(uint8_t channel, uint8_t control, uint8_t value) {
    REC_LOCK();
    bm_rec_set_live_cc(&recorder, control, value);
    bool owned = bm_rec_owns_cc(&recorder, control);
    REC_UNLOCK();
    if (!owned) apply_cc(control, value);
}

static void on_cv_change(uint8_t index, float value) {
    REC_LOCK();
    bm_rec_set_live_cv(&recorder, index, value);
    bool owned = bm_rec_owns_cv(&recorder);
    REC_UNLOCK();
    if (!owned) apply_cv(index, value);
}

void bm_app_fxrack_on_midi_realtime(uint8_t message) {
    if (message == 0xF8) {  // timing clock
        bm_rec_frame_t frame;
        REC_LOCK();
        bool play = bm_rec_clock(&recorder, &frame);
        REC_UNLOCK();
        if (!play) return;
        for (int i = 0; i < BM_REC_CV_COUNT; i++) apply_cv(i, frame.cv[i]);
        for (int i = 0; i < BM_REC_CC_COUNT; i++) {
            if (frame.cc[i] != BM_REC_CC_UNSET) apply_cc(BM_REC_FIRST_CC + i, frame.cc[i]);
        }
    } else if (message == 0xFA) {  // start
        REC_LOCK();
        bm_rec_start(&recorder);
        REC_UNLOCK();
    }
}

// LED from one task: RECORDING blinks, PLAYBACK solid, LIVE off.
void bm_app_fxrack_update(uint32_t now_ms) {
    bm_rec_state_t state = recorder.state;
    if (rec_blink_restart) {
        rec_blink_restart = false;
        rec_blink_start_ms = now_ms;
    }
    float level;
    if (state == BM_REC_RECORDING) {
        level = ((now_ms - rec_blink_start_ms) / REC_BLINK_MS) % 2 == 0 ? 1.0f : 0.0f;
    } else if (state == BM_REC_PLAYBACK) {
        level = 1.0f;
    } else {
        level = 0.0f;
    }
    if (level != led_level) {
        led_level = level;
        bm_set_led_brightness(level);
    }
}

static void on_midi_bpm(uint16_t bpm) {
    // for the left channel
    float beats_per_sec = (float)bpm / 60.0f;
    float samples_per_beat = (float) sample_rate / beats_per_sec;
    float range = samples_per_beat * 0.5f; //1/2 a beat range
    if (range > MAX_BUFFER_LEN_LEFT) {
        range = MAX_BUFFER_LEN_LEFT; // below 15 BPM: keep it inside the buffer
    }
    delay_left.max_delay_length = (size_t)range;
    bm_comb_filter_set_delay_length(&delay_left, delay_left_cv);

    // ESP_LOGI("midi", "bpm: %u, bps: %f, sb: %f, final:%f", bpm, beats_per_sec, samples_per_beat, left_delay_range_in_samples);
}

inline static void process_audio(size_t n_samples, const int16_t* input, int16_t* output) {
    for (size_t lc=0; lc<n_samples; lc += 2) {
        // if (bypassed) {
        //     output[lc] = input[lc];
        //     output[lc+1] = input[lc+1];
        //     continue;
        // }

        // 1. for the left channel
        float curr = bm_audio_norm(input[lc]);
        float delayed = bm_comb_filter_process(&delay_left, curr);

        float left_output = bm_classic_reverb_process(&reverb_left, curr);
        output[lc] = bm_audio_denorm((1 - reverb_mix) * delayed + reverb_mix * left_output);

        // 2. for the right channel
        curr = bm_audio_norm(input[lc + 1]);
        delayed = bm_comb_filter_process(&delay_right, curr);
        float right_output = delayed;
        output[lc + 1] = bm_audio_denorm(right_output);
    }
}

static void init(bm_app_host_t host) {
    sample_rate = host.sample_rate;
    bm_rec_init(&recorder);
    button_down = false;
    button_edge_us = 0;
    led_level = -1.0f;
    bm_app_fxrack_update(0);

    // 1. setup delay for the left channel
    bm_comb_filter_init(&delay_left, MAX_BUFFER_LEN_LEFT, 0.0f);
    bm_param_set(&delay_left.delay_length, 1.0f);
    delay_left.delay_length.smoothing_factor = 0.0001f;
    delay_left.feedback.smoothing_factor = 0.01f;
    delay_mix = 0.0;
    reverb_mix = 0.0;

    // 2. setup reverb for the left channel
    bm_classic_reverb_init(&reverb_left);
    
    // 3. setup state for the right channel
    bm_comb_filter_init(&delay_right, MAX_BUFFER_LEN_RIGHT, 0.0f);
    bm_param_set(&delay_right.delay_length, 1.0f);
    delay_right.delay_length.smoothing_factor = 0.0001f;
    delay_right.feedback.smoothing_factor = 0.01f;
}

static void on_midi_note_on(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_midi_note_off(uint8_t channel, uint8_t control, uint8_t value) {
    
}

static void on_usb_serial_message(const char* message, size_t len) {

}

static void destroy() {
    bm_comb_filter_destroy(&delay_left);
    bm_comb_filter_destroy(&delay_right);
    bm_classic_reverb_destroy(&reverb_left);
}

bm_app_t bm_load_app_fxrack() {
    bm_app_t app = {
        .init = init,
        .process_audio = process_audio,
        .on_button_event = on_button_event,
        .on_midi_note_on = on_midi_note_on,
        .on_midi_note_off = on_midi_note_off,
        .on_midi_cc = on_midi_cc,
        .on_midi_bpm = on_midi_bpm,
        .on_cv_change = on_cv_change,
        .on_usb_serial_message = on_usb_serial_message,
        .destroy = destroy,
    };

    return app;
}
