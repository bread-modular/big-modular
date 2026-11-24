#include "ms_ctl.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

const char *const ms_src_names[MS_SRC_COUNT] = {"cv1", "cv2", "mode"};

// CV: one-pole smoothing per call (~30 ms at the 10 ms tick), the settings follow
// a move of at least CV_STEP of the travel (the ADC's noise stays below it), and
// the last CV_END at each end is the end stop.
#define CV_SMOOTH 0.3f
#define CV_STEP 0.004f
#define CV_END 0.003f

// LED
#define LED_IDLE 0.3f        // status: running
#define LED_BYPASS 0.6f      // status: bypass blinks at this level
#define LED_MODE_IDLE 0.08f  // MODE: not switched over
#define LED_CLIP_LEVEL 0.99f
#define LED_CLIP_MS 300
#define LED_VU_DB 48.0f      // VU: -48..0 dB = dark .. full
#define LED_VU_FALL 1.5f     // of the travel per second
#define LED_KICK_FALL 4.0f   // kick: short flashes on the hits
#define LED_GR_DB 12.0f      // gain reduction: 0..12 dB = dark .. full

void ms_ctl_init(ms_ctl_t *c) {
    memset(c, 0, sizeof(*c));
}

int ms_src_find(const char *name) {
    for (int i = 0; i < MS_SRC_COUNT; i++) {
        if (strcmp(ms_src_names[i], name) == 0) return i;
    }
    // firmware 0.4.0 had a list per way of pressing
    if (!strcmp(name, "click") || !strcmp(name, "hold") || !strcmp(name, "push")) return MS_SRC_MODE;
    return -1;
}

const char *ms_ctl_refuse(int src, int param) {
    if (src < 0 || src >= MS_SRC_COUNT) return "unknown control";
    if (param < 0 || param >= MS_P_COUNT) return "unknown setting";
    if (MS_SRC_IS_CV(src)) {
        // Each new look-ahead length restarts that limiter: a knob would cut the sound.
        if (param == MS_P_K_LIM_LA || param == MS_P_LIM_LA) return "a look-ahead change restarts the limiter";
        if (param == MS_P_LED_MODE || param == MS_P_MODE_ACT) return "not on a knob";
    } else if (ms_param_defs[param].kind != MS_KIND_BOOL) {
        return "MODE switches on / off settings only";
    }
    return NULL;
}

const char *ms_ctl_map(ms_ctl_t *c, int src, int param, float a, float b) {
    const char *why = ms_ctl_refuse(src, param);
    if (why) return why;
    a = ms_param_clamp(param, a);
    b = MS_SRC_IS_CV(src) ? ms_param_clamp(param, b) : 0.0f;
    ms_map_t *m = c->map[src];
    int i = 0;
    while (i < c->count[src] && m[i].param != param) i++;
    if (i == c->count[src]) {
        if (i == MS_CTL_MAPS) return "full";
        c->count[src]++;
    }
    m[i] = (ms_map_t){(int16_t)param, a, b};
    if (MS_SRC_IS_CV(src)) c->cv_valid[src] = false;
    return NULL;
}

bool ms_ctl_unmap(ms_ctl_t *c, int src, int param) {
    if (src < 0 || src >= MS_SRC_COUNT) return false;
    ms_map_t *m = c->map[src];
    for (int i = 0; i < c->count[src]; i++) {
        if (m[i].param != param) continue;
        memmove(&m[i], &m[i + 1], (size_t)(c->count[src] - i - 1) * sizeof(*m));
        c->count[src]--;
        return true;
    }
    return false;
}

void ms_ctl_clear(ms_ctl_t *c) {
    memset(c->count, 0, sizeof(c->count));
    ms_ctl_resync(c);
}

void ms_ctl_resync(ms_ctl_t *c) {
    c->cv_valid[0] = c->cv_valid[1] = false;
}

size_t ms_ctl_export(const ms_ctl_t *c, char *text, size_t cap) {
    size_t len = 0;
    for (int s = 0; s < MS_SRC_COUNT; s++) {
        for (int i = 0; i < c->count[s]; i++) {
            const ms_map_t *m = &c->map[s][i];
            int n = MS_SRC_IS_CV(s) ? snprintf(text + len, cap - len, "map %s %s %.6g %.6g\n", ms_src_names[s],
                                               ms_param_defs[m->param].id, (double)m->a, (double)m->b)
                                    : snprintf(text + len, cap - len, "map %s %s %.6g\n", ms_src_names[s],
                                               ms_param_defs[m->param].id, (double)m->a);
            if (n < 0 || (size_t)n >= cap - len) return 0;
            len += (size_t)n;
        }
    }
    if (len == 0 && cap) text[0] = 0;
    return len;
}

int ms_ctl_import(ms_ctl_t *c, const char *text) {
    int count = 0;
    while (*text) {
        const char *end = strchr(text, '\n');
        size_t len = end ? (size_t)(end - text) : strlen(text);
        char line[96], src[16], id[40];
        float a, b = 0.0f;
        if (len < sizeof(line)) {
            memcpy(line, text, len);
            line[len] = 0;
            if (sscanf(line, " map %15s %39s %f %f", src, id, &a, &b) >= 3 &&
                !ms_ctl_map(c, ms_src_find(src), ms_param_lookup(id), a, b)) {
                count++;
            }
        }
        if (!end) break;
        text = end + 1;
    }
    return count;
}

static bool put(ms_ctl_t *c, int param, float v, float values[MS_P_COUNT]) {
    v = ms_param_clamp(param, v);
    if (v == values[param]) return false;
    values[param] = v;
    c->dirty[param] = true;
    return true;
}

bool ms_ctl_cv(ms_ctl_t *c, int cv, float norm, float values[MS_P_COUNT]) {
    if (cv < 0 || cv > 1) return false;
    if (!(norm >= 0.0f)) norm = 0.0f;  // NaN too
    if (norm > 1.0f) norm = 1.0f;
    float pos = c->cv_seen[cv] ? c->cv_pos[cv] + CV_SMOOTH * (norm - c->cv_pos[cv]) : norm;
    c->cv_seen[cv] = true;
    c->cv_pos[cv] = pos;
    float q = pos < CV_END ? 0.0f : (pos > 1.0f - CV_END ? 1.0f : pos);
    if (c->cv_valid[cv]) {
        bool end_stop = (q == 0.0f || q == 1.0f) && q != c->cv_set[cv];
        if (fabsf(q - c->cv_set[cv]) < CV_STEP && !end_stop) return false;
    }
    c->cv_valid[cv] = true;
    c->cv_set[cv] = q;
    bool changed = false;
    for (int i = 0; i < c->count[cv]; i++) {
        const ms_map_t *m = &c->map[cv][i];
        float v = ms_param_defs[m->param].kind == MS_KIND_LOG && m->a > 0.0f && m->b > 0.0f
                      ? m->a * powf(m->b / m->a, q)
                      : m->a + (m->b - m->a) * q;
        changed |= put(c, m->param, v, values);
    }
    return changed;
}

bool ms_ctl_engaged(const ms_ctl_t *c, const float values[MS_P_COUNT]) {
    const ms_map_t *m = c->map[MS_SRC_MODE];
    if (!c->count[MS_SRC_MODE]) return false;
    for (int i = 0; i < c->count[MS_SRC_MODE]; i++) {
        if (values[m[i].param] != m[i].a) return false;
    }
    return true;
}

bool ms_ctl_fire(ms_ctl_t *c, int on, float values[MS_P_COUNT]) {
    if (on < 0) on = !ms_ctl_engaged(c, values);
    bool changed = false;
    for (int i = 0; i < c->count[MS_SRC_MODE]; i++) {
        const ms_map_t *m = &c->map[MS_SRC_MODE][i];
        changed |= put(c, m->param, on ? m->a : 1.0f - m->a, values);
    }
    return changed;
}

bool ms_ctl_button(ms_ctl_t *c, bool pressed, uint32_t now_ms, float values[MS_P_COUNT]) {
    if (pressed != c->raw) {
        c->raw = pressed;
        c->raw_ms = now_ms;
    }
    int act = (int)values[MS_P_MODE_ACT];
    bool changed = false;
    if (c->raw != c->down && now_ms - c->raw_ms >= MS_CTL_DEBOUNCE_MS) {
        c->down = c->raw;
        if (c->down) {
            c->down_ms = now_ms;
            c->held = false;
            if (act == MS_ACT_CLICK) changed |= ms_ctl_fire(c, -1, values);
            if (act == MS_ACT_PUSH) {
                c->pushed = true;
                changed |= ms_ctl_fire(c, 1, values);
            }
        } else if (c->pushed) {
            // back even if mode_act changed while the button was down
            c->pushed = false;
            changed |= ms_ctl_fire(c, 0, values);
        }
    }
    if (c->down && !c->held && act == MS_ACT_HOLD && now_ms - c->down_ms >= MS_CTL_HOLD_MS) {
        c->held = true;
        changed |= ms_ctl_fire(c, -1, values);
    }
    return changed;
}

// ---------------------------------------------------------------- LED

static float vu(float peak) {
    float x = peak > 1e-6f ? 1.0f + 20.0f * log10f(peak) / LED_VU_DB : 0.0f;
    return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x);
}

// Up at once, down at `fall` of the travel per second.
static float follow(ms_led_t *s, float target, float fall, float dt_s) {
    s->level -= fall * dt_s;
    if (s->level < target) s->level = target;
    return s->level;
}

float ms_led_run(ms_led_t *s, const float values[MS_P_COUNT], const ms_meters_t *m, bool engaged, uint32_t now_ms,
                 float dt_s) {
    int mode = (int)values[MS_P_LED_MODE];
    if (m->raw_k >= LED_CLIP_LEVEL || m->raw_m >= LED_CLIP_LEVEL) s->clip_until_ms = now_ms + LED_CLIP_MS;
    float x;
    switch (mode) {
        case MS_LED_OUT:
            x = follow(s, vu(m->out), LED_VU_FALL, dt_s);
            break;
        case MS_LED_KICK:
            x = follow(s, vu(m->kick), LED_KICK_FALL, dt_s);
            break;
        case MS_LED_GR: {
            float gr = m->gr_glue > m->gr_lim ? m->gr_glue : m->gr_lim;
            gr = gr / LED_GR_DB;
            x = follow(s, gr > 1.0f ? 1.0f : gr, LED_VU_FALL, dt_s);
            break;
        }
        case MS_LED_MODE:
            x = engaged ? 1.0f : LED_MODE_IDLE;
            break;
        case MS_LED_OFF:
            return 0.0f;
        default:
            x = values[MS_P_BYPASS] >= 0.5f ? ((now_ms / 500) % 2 ? 0.0f : LED_BYPASS) : LED_IDLE;
            break;
    }
    x *= values[MS_P_LED_BRIGHT] * 0.01f;
    if (values[MS_P_LED_CLIP] >= 0.5f && (int32_t)(s->clip_until_ms - now_ms) > 0) x = 1.0f;
    return x;
}
