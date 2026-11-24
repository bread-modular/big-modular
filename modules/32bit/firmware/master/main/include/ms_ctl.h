#pragma once

// The module's own controls on top of the settings: the two CV knobs, the MODE
// button and the MODE LED. Plain C, no ESP-IDF (host-tested); main.c reads the
// hardware (ms_io.c) and ms_proto.c owns the mappings.
//
//   CV1 / CV2   each moves up to MS_CTL_MAPS settings, every one between its own
//               two values (`a` at the knob's bottom, `b` at its top; b < a turns
//               it round). Log settings (frequencies, times) move on a log scale.
//   MODE        switches up to MS_CTL_MAPS on / off settings to their `a` value
//               (0 or 1) and back to the other one, in one of three ways (the
//               mode_act setting):
//                 click  a press switches them over, the next one back
//                 hold   as click, after the button is held MS_CTL_HOLD_MS
//                 push   over while the button is down (momentary)
//   LED         led_mode / led_bright / led_clip (ms_params.h).
//
// Only the settings change: the audio thread gets new coefficients as for a
// change from the page, nothing runs in the audio path.

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ms_dsp.h"
#include "ms_params.h"

#ifdef __cplusplus
extern "C" {
#endif

enum { MS_SRC_CV1, MS_SRC_CV2, MS_SRC_MODE, MS_SRC_COUNT };
#define MS_SRC_IS_CV(src) ((src) <= MS_SRC_CV2)
#define MS_CTL_MAPS 8          // per source
#define MS_CTL_HOLD_MS 500
#define MS_CTL_DEBOUNCE_MS 20

enum { MS_ACT_CLICK, MS_ACT_HOLD, MS_ACT_PUSH };  // mode_act
enum { MS_LED_STATUS, MS_LED_OUT, MS_LED_KICK, MS_LED_GR, MS_LED_MODE, MS_LED_OFF };

typedef struct {
    int16_t param;
    float a, b;  // CV: value at the bottom / top; MODE: the value the action switches to (b unused)
} ms_map_t;

typedef struct {
    ms_map_t map[MS_SRC_COUNT][MS_CTL_MAPS];
    uint8_t count[MS_SRC_COUNT];

    // CV: smoothed position, the position the settings were last set from
    float cv_pos[2], cv_set[2];
    bool cv_seen[2], cv_valid[2];

    // MODE button (debounced)
    bool raw, down;
    uint32_t raw_ms, down_ms;
    bool held, pushed;  // this press: the hold has acted / push switched over

    // settings changed by the controls, not yet sent to the page
    bool dirty[MS_P_COUNT];
} ms_ctl_t;

typedef struct {
    uint32_t clip_until_ms;
    float level;  // follower of the VU modes, 0..1
} ms_led_t;

extern const char *const ms_src_names[MS_SRC_COUNT];

void ms_ctl_init(ms_ctl_t *c);
// -1 = unknown; the names of firmware 0.4.0 (click, hold, push) give "mode".
int ms_src_find(const char *name);

// Why a setting cannot be mapped to a source, or NULL if it can.
const char *ms_ctl_refuse(int src, int param);
// Adds the mapping, or updates it if the setting is mapped to that source already.
// Returns NULL or the reason it was refused (as ms_ctl_refuse, or full).
const char *ms_ctl_map(ms_ctl_t *c, int src, int param, float a, float b);
bool ms_ctl_unmap(ms_ctl_t *c, int src, int param);
void ms_ctl_clear(ms_ctl_t *c);
// The knobs set their settings again at the next ms_ctl_cv (after a load or a new mapping).
void ms_ctl_resync(ms_ctl_t *c);

// `map <src> <id> <a> <b>` lines (the USB command, the stored text, the page's file).
size_t ms_ctl_export(const ms_ctl_t *c, char *text, size_t cap);  // 0 if `cap` is too small or no mappings
int ms_ctl_import(ms_ctl_t *c, const char *text);                 // mappings read

// Hardware in, settings out; true if a setting changed.
// cv: 0 / 1 = CV1 / CV2, norm = the knob x CV, 0..1, called every few ms.
bool ms_ctl_cv(ms_ctl_t *c, int cv, float norm, float values[MS_P_COUNT]);
bool ms_ctl_button(ms_ctl_t *c, bool pressed, uint32_t now_ms, float values[MS_P_COUNT]);
// MODE from the page: on = 1 over, 0 back, -1 the other way round (a click).
bool ms_ctl_fire(ms_ctl_t *c, int on, float values[MS_P_COUNT]);
// True while the MODE settings are all switched over.
bool ms_ctl_engaged(const ms_ctl_t *c, const float values[MS_P_COUNT]);

// LED brightness 0..1 (perceptual) for this moment; dt_s since the last call.
float ms_led_run(ms_led_t *s, const float values[MS_P_COUNT], const ms_meters_t *m, bool engaged, uint32_t now_ms,
                 float dt_s);

#ifdef __cplusplus
}
#endif
