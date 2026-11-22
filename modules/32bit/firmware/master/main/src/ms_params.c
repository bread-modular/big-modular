#include "ms_params.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const ms_param_def_t ms_param_defs[MS_P_COUNT] = {
#define X(name, id, group, label, kind, min, max, def, step, unit, options, not_saved) \
    {id, group, label, MS_KIND_##kind, min, max, def, step, unit, options, not_saved},
    MS_PARAMS(X)
#undef X
};

const ms_group_def_t ms_group_defs[] = {
    {"in", "Inputs"},
    {"kick", "Kick (IN L)"},
    {"mix", "Mix (IN R)"},
    {"mb", "Multiband dynamics on the mix"},
    {"mb_lo", "Low band"},
    {"mb_mid", "Mid band"},
    {"mb_hi", "High band"},
    {"par", "Parallel compression"},
    {"glue", "Glue compressor"},
    {"eq", "Main cuts"},
    {"lim", "Limiter"},
    {"out", "Output"},
};
const int ms_group_count = (int)(sizeof(ms_group_defs) / sizeof(ms_group_defs[0]));

static const float glue_ratio[] = {2.0f, 4.0f, 10.0f};
// The knee widens as the ratio falls, as on the bus compressors the Glue follows.
static const float glue_knee_db[] = {12.0f, 8.0f, 4.0f};
static const float glue_attack_ms[] = {0.01f, 0.1f, 0.3f, 1.0f, 3.0f, 10.0f, 30.0f};
static const float glue_release_s[] = {0.1f, 0.2f, 0.4f, 0.6f, 0.8f, 1.2f};
#define GLUE_REL_AUTO 6
#define GLUE_AUTO_FAST_S 0.1f
#define GLUE_AUTO_CHARGE_S 0.5f
#define GLUE_AUTO_SLOW_S 2.0f

#define COMP_KNEE_DB 6.0f
#define COMP_RANGE_DB 60.0f
#define RMS_WINDOW_S 0.010f
#define GAIN_SMOOTH_S 0.010f
#define LEVEL_OFF_DB -59.95f

void ms_params_defaults(float values[MS_P_COUNT]) {
    for (int i = 0; i < MS_P_COUNT; i++) values[i] = ms_param_defs[i].def;
}

int ms_param_find(const char *id) {
    for (int i = 0; i < MS_P_COUNT; i++) {
        if (strcmp(ms_param_defs[i].id, id) == 0) return i;
    }
    return -1;
}

float ms_param_clamp(int index, float value) {
    const ms_param_def_t *d = &ms_param_defs[index];
    if (!(value == value)) return d->def;  // NaN
    if (d->kind == MS_KIND_BOOL || d->kind == MS_KIND_ENUM) value = floorf(value + 0.5f);
    if (value < d->min) value = d->min;
    if (value > d->max) value = d->max;
    return value;
}

size_t ms_params_export(const float values[MS_P_COUNT], char *text, size_t cap) {
    size_t len = 0;
    for (int i = 0; i < MS_P_COUNT; i++) {
        if (ms_param_defs[i].not_saved) continue;
        int n = snprintf(text + len, cap - len, "set %s %.6g\n", ms_param_defs[i].id, (double)values[i]);
        if (n < 0 || (size_t)n >= cap - len) return 0;
        len += (size_t)n;
    }
    return len;
}

int ms_params_import(float values[MS_P_COUNT], const char *text) {
    int count = 0;
    while (*text) {
        const char *end = strchr(text, '\n');
        size_t len = end ? (size_t)(end - text) : strlen(text);
        char line[96];
        if (len < sizeof(line)) {
            memcpy(line, text, len);
            line[len] = 0;
            char id[40];
            float v;
            if (sscanf(line, " set %39s %f", id, &v) == 2) {
                int index = ms_param_find(id);
                if (index >= 0 && !ms_param_defs[index].not_saved) {
                    values[index] = ms_param_clamp(index, v);
                    count++;
                }
            }
        }
        if (!end) break;
        text = end + 1;
    }
    return count;
}

// ---------------------------------------------------------------- coefficients

static float level_gain(float db) {
    return db <= LEVEL_OFF_DB ? 0.0f : ms_db_to_lin(db);
}

static void comp_set(ms_comp_coef_t *c, float fs, float thr_db, float ratio, float knee_db, float att_s,
                     float rel_s, float range_db) {
    memset(c, 0, sizeof(*c));
    c->thr_db = thr_db;
    c->slope = 1.0f - 1.0f / ratio;
    c->half_knee = 0.5f * knee_db;
    c->inv_2knee = knee_db > 0.01f ? 1.0f / (2.0f * knee_db) : 0.0f;
    c->range_db = range_db;
    c->att = ms_time_coef(fs, att_s);
    c->rel = ms_time_coef(fs, rel_s);
    c->rms_coef = ms_time_coef(fs, RMS_WINDOW_S);
}

static void lim_set(ms_lim_coef_t *c, float fs, bool on, float gain_db, float ceil_db, float rel_ms,
                    float la_ms) {
    c->on = on;
    c->drive = ms_db_to_lin(gain_db);
    c->ceil = ms_db_to_lin(ceil_db);
    c->rel = ms_time_coef(fs, rel_ms * 0.001f);
    int la = (int)(la_ms * 0.001f * fs + 0.5f);
    if (la < 0) la = 0;
    if (la > MS_LA_SIZE - 2) la = MS_LA_SIZE - 2;
    c->la = la;
}

void ms_coefs_from_params(const float v[MS_P_COUNT], float fs, int block, ms_coefs_t *c) {
    memset(c, 0, sizeof(*c));
    c->bypass = v[MS_P_BYPASS] >= 0.5f;
    c->g_smooth = 1.0f - expf(-(float)block / (fs * GAIN_SMOOTH_S));

    c->g[MS_G_TRIM_K] = ms_db_to_lin(v[MS_P_IN_K_TRIM]);
    c->g[MS_G_TRIM_M] = ms_db_to_lin(v[MS_P_IN_M_TRIM]);
    c->g[MS_G_LVL_K] = level_gain(v[MS_P_K_LVL]);
    c->g[MS_G_LVL_M] = level_gain(v[MS_P_M_LVL]);
    c->g[MS_G_SEND_K] = level_gain(v[MS_P_PAR_SEND_K]);
    c->g[MS_G_SEND_M] = level_gain(v[MS_P_PAR_SEND_M]);
    c->g[MS_G_PAR_RET] = level_gain(v[MS_P_PAR_RET]) * ms_db_to_lin(v[MS_P_PAR_MAKEUP]);
    c->g[MS_G_GLUE_MAKEUP] = ms_db_to_lin(v[MS_P_GLUE_MAKEUP]);
    c->g[MS_G_OUT] = level_gain(v[MS_P_OUT_LVL]);

    // Kick
    c->k_hp_n = v[MS_P_K_HP_ON] >= 0.5f ? 1 + (int)v[MS_P_K_HP_SLOPE] : 0;
    ms_butter_set(c->k_hp, c->k_hp_n, fs, v[MS_P_K_HP_F]);
    lim_set(&c->k_lim, fs, v[MS_P_K_LIM_ON] >= 0.5f, v[MS_P_K_LIM_GAIN], v[MS_P_K_LIM_CEIL], v[MS_P_K_LIM_REL],
            v[MS_P_K_LIM_LA]);

    // Mix
    c->m_hp_n = v[MS_P_M_HP_ON] >= 0.5f ? 1 + (int)v[MS_P_M_HP_SLOPE] : 0;
    ms_butter_set(c->m_hp, c->m_hp_n, fs, v[MS_P_M_HP_F]);

    // Multiband
    c->mb_on = v[MS_P_MB_ON] >= 0.5f;
    c->mb_sc_kick = v[MS_P_MB_SC] < 0.5f;
    c->mb_sc_gain = ms_db_to_lin(v[MS_P_MB_SC_GAIN]);
    c->mb_amount = v[MS_P_MB_AMOUNT] * 0.01f;
    c->mb_solo = (int)v[MS_P_MB_SOLO];
    ms_svf_set(&c->x1, fs, v[MS_P_MB_F1], 0.70710678f);
    ms_svf_set(&c->x2, fs, v[MS_P_MB_F2], 0.70710678f);
    const float mb_knee = v[MS_P_MB_KNEE] >= 0.5f ? COMP_KNEE_DB : 0.0f;
    const float mb_out = ms_db_to_lin(v[MS_P_MB_OUT]);
    for (int b = 0; b < MS_BANDS; b++) {
        const float *p = &v[MS_P_MB_LO_ON + b * (MS_P_MB_MID_ON - MS_P_MB_LO_ON)];
        c->mb_band_on[b] = p[0] >= 0.5f;
        comp_set(&c->mb[b], fs, p[1], p[2], mb_knee, p[3] * 0.001f, p[4] * 0.001f, COMP_RANGE_DB);
        c->mb[b].rms = v[MS_P_MB_MODE] >= 0.5f;
        c->g[MS_G_MB_LO + b] = ms_db_to_lin(p[5]) * mb_out;
    }

    // Parallel compressor
    c->par_on = v[MS_P_PAR_ON] >= 0.5f;
    comp_set(&c->par, fs, v[MS_P_PAR_THR], v[MS_P_PAR_RATIO], COMP_KNEE_DB, v[MS_P_PAR_ATT] * 0.001f,
             v[MS_P_PAR_REL] * 0.001f, COMP_RANGE_DB);

    // Glue
    c->glue_on = v[MS_P_GLUE_ON] >= 0.5f;
    int ratio = (int)v[MS_P_GLUE_RATIO], rel = (int)v[MS_P_GLUE_REL];
    bool auto_rel = rel >= GLUE_REL_AUTO;
    comp_set(&c->glue, fs, v[MS_P_GLUE_THR], glue_ratio[ratio], glue_knee_db[ratio],
             glue_attack_ms[(int)v[MS_P_GLUE_ATT]] * 0.001f, auto_rel ? GLUE_AUTO_FAST_S : glue_release_s[rel],
             v[MS_P_GLUE_RANGE]);
    c->glue.auto_rel = auto_rel;
    c->glue.slow_att = ms_time_coef(fs, GLUE_AUTO_CHARGE_S);
    c->glue.slow_rel = ms_time_coef(fs, GLUE_AUTO_SLOW_S);
    c->glue_wet = v[MS_P_GLUE_WET] * 0.01f;
    c->glue_clip = v[MS_P_GLUE_CLIP] >= 0.5f;
    c->glue_sc_hp_on = v[MS_P_GLUE_SC_HP] > 20.5f;
    ms_svf_set(&c->glue_sc_hp, fs, v[MS_P_GLUE_SC_HP], 0.70710678f);

    // Main cuts and limiter
    c->eq_lo_n = v[MS_P_EQ_LO_ON] >= 0.5f ? 1 + (int)v[MS_P_EQ_LO_SLOPE] : 0;
    ms_butter_set(c->eq_lo, c->eq_lo_n, fs, v[MS_P_EQ_LO_F]);
    c->eq_hi_n = v[MS_P_EQ_HI_ON] >= 0.5f ? 1 + (int)v[MS_P_EQ_HI_SLOPE] : 0;
    ms_butter_set(c->eq_hi, c->eq_hi_n, fs, v[MS_P_EQ_HI_F]);
    lim_set(&c->lim, fs, v[MS_P_LIM_ON] >= 0.5f, v[MS_P_LIM_GAIN], v[MS_P_LIM_CEIL], v[MS_P_LIM_REL],
            v[MS_P_LIM_LA]);
}
