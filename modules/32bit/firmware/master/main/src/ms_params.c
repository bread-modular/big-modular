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
    {"k_flt", "Kick filter"},
    {"mix", "Mix (IN R)"},
    {"m_flt", "Mix filter"},
    {"mb", "Multiband dynamics on the mix"},
    {"mb_lo", "Low band"},
    {"mb_mid", "Mid band"},
    {"mb_hi", "High band"},
    {"par", "Parallel compression"},
    {"glue", "Glue compressor"},
    {"o_flt", "Master filter"},
    {"lim", "Limiter"},
    {"out", "Output"},
    {"led", "MODE button and LED"},
};
const int ms_group_count = (int)(sizeof(ms_group_defs) / sizeof(ms_group_defs[0]));

static const float glue_ratio[] = {2.0f, 4.0f, 10.0f};
// Width of the bend in the curve, in dB of input level: softest at 2:1.
static const float glue_knee_db[] = {6.0f, 4.0f, 4.0f};
static const float glue_attack_ms[] = {0.01f, 0.1f, 0.3f, 1.0f, 3.0f, 10.0f, 30.0f};
static const float glue_release_s[] = {0.1f, 0.2f, 0.4f, 0.6f, 0.8f, 1.2f};
#define GLUE_REL_AUTO 6
// Release A: the two RC pairs of the G series network, 91k x 0.47 uF and
// 750k x 6.8 uF in series.
#define GLUE_AUTO_FAST_S 0.0428f
#define GLUE_AUTO_SLOW_S 5.1f
#define GLUE_AUTO_CAP_RATIO (0.47f / 6.8f)

// Limiter auto release (ms_lim_coef_t): fast stage, slow stage attack / release.
#define LIM_AUTO_FAST_S 0.030f
#define LIM_AUTO_SLOW_ATT_S 0.100f
#define LIM_AUTO_SLOW_REL_S 1.0f

// Order settings: MS_DEV_* in signal order for each option of k_order, m_order, o_order.
static const uint8_t order_k[][2] = {{MS_DEV_FLT, MS_DEV_LIM}, {MS_DEV_LIM, MS_DEV_FLT}};
static const uint8_t order_m[][2] = {{MS_DEV_FLT, MS_DEV_MB}, {MS_DEV_MB, MS_DEV_FLT}};
static const uint8_t order_o[][3] = {
    {MS_DEV_GLUE, MS_DEV_FLT, MS_DEV_LIM}, {MS_DEV_GLUE, MS_DEV_LIM, MS_DEV_FLT}, {MS_DEV_FLT, MS_DEV_GLUE, MS_DEV_LIM},
    {MS_DEV_FLT, MS_DEV_LIM, MS_DEV_GLUE}, {MS_DEV_LIM, MS_DEV_GLUE, MS_DEV_FLT}, {MS_DEV_LIM, MS_DEV_FLT, MS_DEV_GLUE},
};

// Names of firmware 0.2 in stored settings and exported files: the cuts that are
// now the filters (same values, the slopes keep their numbers).
static const char *const old_ids[][2] = {
    {"k_hp_on", "k_flt_lc_on"}, {"k_hp_f", "k_flt_lc_f"}, {"k_hp_slope", "k_flt_lc_slope"},
    {"m_hp_on", "m_flt_lc_on"}, {"m_hp_f", "m_flt_lc_f"}, {"m_hp_slope", "m_flt_lc_slope"},
    {"eq_lo_on", "o_flt_lc_on"}, {"eq_lo_f", "o_flt_lc_f"}, {"eq_lo_slope", "o_flt_lc_slope"},
    {"eq_hi_on", "o_flt_hc_on"}, {"eq_hi_f", "o_flt_hc_f"}, {"eq_hi_slope", "o_flt_hc_slope"},
};

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

int ms_param_lookup(const char *id) {
    int index = ms_param_find(id);
    for (size_t a = 0; index < 0 && a < sizeof(old_ids) / sizeof(old_ids[0]); a++) {
        if (strcmp(old_ids[a][0], id) == 0) index = ms_param_find(old_ids[a][1]);
    }
    return index;
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
                int index = ms_param_lookup(id);
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

// Attack and release are the RC products of the timing network (ms_glue_coef_t);
// release_s <= 0 is release A.
static void glue_set(ms_glue_coef_t *c, float fs, float thr_db, float ratio, float knee_in_db, float att_s,
                     float rel_s, float range_db) {
    c->thr_db = thr_db;
    c->fb = ratio - 1.0f;
    // A bend `knee` wide at the detector is knee x (1 + ratio) / 2 wide at the input.
    float knee = 2.0f * knee_in_db / (1.0f + ratio);
    c->half_knee = 0.5f * knee;
    c->inv_knee = 1.0f / knee;
    c->range_db = range_db;
    // expm1 makes a step of the open network the exact exponential.
    float att = expm1f(1.0f / (fs * att_s));
    if (rel_s > 0.0f) {
        c->keep1 = c->keep2 = expf(-1.0f / (fs * rel_s));
        c->chg1 = att * c->keep1;
        c->chg2 = 0.0f;
    } else {
        c->keep1 = expf(-1.0f / (fs * GLUE_AUTO_FAST_S));
        c->keep2 = expf(-1.0f / (fs * GLUE_AUTO_SLOW_S));
        c->chg1 = att * c->keep1;
        c->chg2 = att * GLUE_AUTO_CAP_RATIO * c->keep2;
    }
    c->chg = c->chg1 + c->chg2;
    c->inv_chg = 1.0f / c->chg;
    c->inv_lin = 1.0f / (1.0f + c->chg * ratio);
}

static void lim_set(ms_lim_coef_t *c, float fs, bool on, float gain_db, float ceil_db, float rel_ms, bool auto_rel,
                    float la_ms) {
    c->on = on;
    c->drive = ms_db_to_lin(gain_db);
    c->ceil = ms_db_to_lin(ceil_db);
    c->auto_rel = auto_rel;
    c->rel = ms_time_coef(fs, auto_rel ? LIM_AUTO_FAST_S : rel_ms * 0.001f);
    c->slow_att = ms_time_coef(fs, LIM_AUTO_SLOW_ATT_S);
    c->slow_rel = ms_time_coef(fs, LIM_AUTO_SLOW_REL_S);
    int la = (int)(la_ms * 0.001f * fs + 0.5f);
    if (la < 0) la = 0;
    if (la > MS_LA_SIZE - 2) la = MS_LA_SIZE - 2;
    c->la = la;
}

// The filter whose first parameter (its switch) is at `p`, laid out as MS_FILTER.
static void flt_set(ms_flt_coef_t *c, const float *p, float fs) {
    memset(c, 0, sizeof(*c));
    if (p[0] < 0.5f) return;
    if (p[1] >= 0.5f) c->lc_n = ms_cut_set(c->lc, (int)p[4], fs, p[2], p[3]);
    if (p[5] >= 0.5f) c->hc_n = ms_cut_set(c->hc, (int)p[8], fs, p[6], p[7]);
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

    // Channel off / solo: only gains, so they fade in 10 ms like a fader. Off takes
    // the channel's send too; solo leaves the others' sends, so a soloed parallel
    // bus is still fed. The multiband key stays (a kick that is off still ducks).
    const bool k_off = v[MS_P_K_OFF] >= 0.5f, m_off = v[MS_P_M_OFF] >= 0.5f, p_off = v[MS_P_PAR_OFF] >= 0.5f;
    const bool k_solo = v[MS_P_K_SOLO] >= 0.5f, m_solo = v[MS_P_M_SOLO] >= 0.5f, p_solo = v[MS_P_PAR_SOLO] >= 0.5f;
    const bool solo = k_solo || m_solo || p_solo, master = v[MS_P_OUT_OFF] < 0.5f;
    const float k_hear = !k_off && (!solo || k_solo), m_hear = !m_off && (!solo || m_solo);
    c->g[MS_G_LVL_K] *= k_hear;
    c->g[MS_G_LVL_M] *= m_hear;
    c->g[MS_G_SEND_K] *= !k_off;
    c->g[MS_G_SEND_M] *= !m_off;
    c->g[MS_G_PAR_RET] *= !p_off && (!solo || p_solo);
    c->g[MS_G_OUT] *= master;
    // Bypass: kick + mix straight out, still with off / solo and the master switch.
    c->g[MS_G_BYP_K] = k_hear * master;
    c->g[MS_G_BYP_M] = m_hear * master;

    memcpy(c->k_order, order_k[(int)v[MS_P_K_ORDER]], sizeof(c->k_order));
    memcpy(c->m_order, order_m[(int)v[MS_P_M_ORDER]], sizeof(c->m_order));
    memcpy(c->o_order, order_o[(int)v[MS_P_O_ORDER]], sizeof(c->o_order));

    // Kick
    flt_set(&c->k_flt, &v[MS_P_K_FLT_ON], fs);
    lim_set(&c->k_lim, fs, v[MS_P_K_LIM_ON] >= 0.5f, v[MS_P_K_LIM_GAIN], v[MS_P_K_LIM_CEIL], v[MS_P_K_LIM_REL],
            v[MS_P_K_LIM_AUTO] >= 0.5f, v[MS_P_K_LIM_LA]);

    // Mix
    flt_set(&c->m_flt, &v[MS_P_M_FLT_ON], fs);

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
    glue_set(&c->glue, fs, v[MS_P_GLUE_THR], glue_ratio[ratio], glue_knee_db[ratio],
             glue_attack_ms[(int)v[MS_P_GLUE_ATT]] * 0.001f, rel >= GLUE_REL_AUTO ? 0.0f : glue_release_s[rel],
             v[MS_P_GLUE_RANGE]);
    c->glue_wet = v[MS_P_GLUE_WET] * 0.01f;
    c->glue_clip = v[MS_P_GLUE_CLIP] >= 0.5f;
    c->glue_sc_hp_on = v[MS_P_GLUE_SC_HP] > 20.5f;
    ms_svf_set(&c->glue_sc_hp, fs, v[MS_P_GLUE_SC_HP], 0.70710678f);

    // Master filter and limiter
    flt_set(&c->o_flt, &v[MS_P_O_FLT_ON], fs);
    lim_set(&c->lim, fs, v[MS_P_LIM_ON] >= 0.5f, v[MS_P_LIM_GAIN], v[MS_P_LIM_CEIL], v[MS_P_LIM_REL],
            v[MS_P_LIM_AUTO] >= 0.5f, v[MS_P_LIM_LA]);
}
