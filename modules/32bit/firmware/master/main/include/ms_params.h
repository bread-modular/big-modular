#pragma once

// Settings of the master chain: one table drives the DSP coefficients, the USB
// protocol, the saved settings and the web page (which builds itself from `desc`).

#include <stdbool.h>
#include <stddef.h>

#include "ms_dsp.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { MS_KIND_LIN, MS_KIND_LOG, MS_KIND_BOOL, MS_KIND_ENUM } ms_kind_t;

//   X(NAME, id, group, label, kind, min, max, default, step, unit, options, not_saved)
// Levels in dB with a -60 minimum are off (silent) at the minimum.
#define MS_PARAMS(X)                                                                                              \
    X(IN_K_TRIM, "in_k_trim", "in", "Kick trim", LIN, -24, 24, 0, 0.5f, "dB", "", 0)                              \
    X(IN_M_TRIM, "in_m_trim", "in", "Mix trim", LIN, -24, 24, 0, 0.5f, "dB", "", 0)                               \
    /* Kick */                                                                                                    \
    X(K_HP_ON, "k_hp_on", "kick", "Sub cut", BOOL, 0, 1, 1, 1, "", "", 0)                                         \
    X(K_HP_F, "k_hp_f", "kick", "Sub cut frequency", LOG, 10, 120, 25, 0, "Hz", "", 0)                            \
    X(K_HP_SLOPE, "k_hp_slope", "kick", "Sub cut slope", ENUM, 0, 1, 1, 1, "", "12 dB/oct,24 dB/oct", 0)          \
    X(K_LIM_ON, "k_lim_on", "kick", "Limiter", BOOL, 0, 1, 1, 1, "", "", 0)                                       \
    X(K_LIM_GAIN, "k_lim_gain", "kick", "Limiter gain", LIN, 0, 24, 0, 0.1f, "dB", "", 0)                         \
    X(K_LIM_CEIL, "k_lim_ceil", "kick", "Limiter ceiling", LIN, -24, 0, -3, 0.1f, "dB", "", 0)                    \
    X(K_LIM_REL, "k_lim_rel", "kick", "Limiter release", LOG, 1, 1000, 60, 0, "ms", "", 0)                        \
    X(K_LIM_LA, "k_lim_la", "kick", "Limiter look-ahead", LIN, 0, 5, 1, 0.1f, "ms", "", 0)                        \
    X(K_LVL, "k_lvl", "kick", "Kick level", LIN, -60, 12, 0, 0.1f, "dB", "", 0)                                   \
    /* Mix */                                                                                                     \
    X(M_HP_ON, "m_hp_on", "mix", "Low cut", BOOL, 0, 1, 1, 1, "", "", 0)                                          \
    X(M_HP_F, "m_hp_f", "mix", "Low cut frequency", LOG, 20, 500, 40, 0, "Hz", "", 0)                             \
    X(M_HP_SLOPE, "m_hp_slope", "mix", "Low cut slope", ENUM, 0, 1, 0, 1, "", "12 dB/oct,24 dB/oct", 0)           \
    X(M_LVL, "m_lvl", "mix", "Mix level", LIN, -60, 12, 0, 0.1f, "dB", "", 0)                                     \
    /* Multiband dynamics */                                                                                      \
    X(MB_ON, "mb_on", "mb", "Multiband", BOOL, 0, 1, 1, 1, "", "", 0)                                             \
    X(MB_SC, "mb_sc", "mb", "Sidechain", ENUM, 0, 1, 0, 1, "", "Kick,Self", 0)                                    \
    X(MB_SC_GAIN, "mb_sc_gain", "mb", "Sidechain gain", LIN, -24, 24, 0, 0.5f, "dB", "", 0)                       \
    X(MB_F1, "mb_f1", "mb", "Low / mid split", LOG, 40, 800, 120, 0, "Hz", "", 0)                                 \
    X(MB_F2, "mb_f2", "mb", "Mid / high split", LOG, 1000, 10000, 2500, 0, "Hz", "", 0)                           \
    X(MB_MODE, "mb_mode", "mb", "Detector", ENUM, 0, 1, 0, 1, "", "Peak,RMS", 0)                                  \
    X(MB_KNEE, "mb_knee", "mb", "Soft knee", BOOL, 0, 1, 1, 1, "", "", 0)                                         \
    X(MB_AMOUNT, "mb_amount", "mb", "Amount", LIN, 0, 100, 100, 1, "%", "", 0)                                    \
    X(MB_OUT, "mb_out", "mb", "Output", LIN, -24, 12, 0, 0.1f, "dB", "", 0)                                       \
    X(MB_SOLO, "mb_solo", "mb", "Solo band", ENUM, 0, 3, 0, 1, "", "Off,Low,Mid,High", 1)                         \
    X(MB_LO_ON, "mb_lo_on", "mb_lo", "Low band", BOOL, 0, 1, 1, 1, "", "", 0)                                     \
    X(MB_LO_THR, "mb_lo_thr", "mb_lo", "Threshold", LIN, -60, 0, -24, 0.5f, "dB", "", 0)                          \
    X(MB_LO_RATIO, "mb_lo_ratio", "mb_lo", "Ratio", LOG, 1, 20, 3, 0, ":1", "", 0)                                \
    X(MB_LO_ATT, "mb_lo_att", "mb_lo", "Attack", LOG, 0.1f, 200, 1, 0, "ms", "", 0)                               \
    X(MB_LO_REL, "mb_lo_rel", "mb_lo", "Release", LOG, 5, 2000, 120, 0, "ms", "", 0)                              \
    X(MB_LO_GAIN, "mb_lo_gain", "mb_lo", "Gain", LIN, -24, 12, 0, 0.1f, "dB", "", 0)                              \
    X(MB_MID_ON, "mb_mid_on", "mb_mid", "Mid band", BOOL, 0, 1, 1, 1, "", "", 0)                                  \
    X(MB_MID_THR, "mb_mid_thr", "mb_mid", "Threshold", LIN, -60, 0, -24, 0.5f, "dB", "", 0)                       \
    X(MB_MID_RATIO, "mb_mid_ratio", "mb_mid", "Ratio", LOG, 1, 20, 1.5f, 0, ":1", "", 0)                          \
    X(MB_MID_ATT, "mb_mid_att", "mb_mid", "Attack", LOG, 0.1f, 200, 3, 0, "ms", "", 0)                            \
    X(MB_MID_REL, "mb_mid_rel", "mb_mid", "Release", LOG, 5, 2000, 100, 0, "ms", "", 0)                           \
    X(MB_MID_GAIN, "mb_mid_gain", "mb_mid", "Gain", LIN, -24, 12, 0, 0.1f, "dB", "", 0)                           \
    X(MB_HI_ON, "mb_hi_on", "mb_hi", "High band", BOOL, 0, 1, 1, 1, "", "", 0)                                    \
    X(MB_HI_THR, "mb_hi_thr", "mb_hi", "Threshold", LIN, -60, 0, -24, 0.5f, "dB", "", 0)                          \
    X(MB_HI_RATIO, "mb_hi_ratio", "mb_hi", "Ratio", LOG, 1, 20, 1, 0, ":1", "", 0)                                \
    X(MB_HI_ATT, "mb_hi_att", "mb_hi", "Attack", LOG, 0.1f, 200, 5, 0, "ms", "", 0)                               \
    X(MB_HI_REL, "mb_hi_rel", "mb_hi", "Release", LOG, 5, 2000, 80, 0, "ms", "", 0)                               \
    X(MB_HI_GAIN, "mb_hi_gain", "mb_hi", "Gain", LIN, -24, 12, 0, 0.1f, "dB", "", 0)                              \
    /* Parallel compression */                                                                                    \
    X(PAR_ON, "par_on", "par", "Parallel bus", BOOL, 0, 1, 1, 1, "", "", 0)                                       \
    X(PAR_SEND_K, "par_send_k", "par", "Kick send", LIN, -60, 0, -6, 0.1f, "dB", "", 0)                           \
    X(PAR_SEND_M, "par_send_m", "par", "Mix send", LIN, -60, 0, -6, 0.1f, "dB", "", 0)                            \
    X(PAR_THR, "par_thr", "par", "Threshold", LIN, -60, 0, -35, 0.5f, "dB", "", 0)                                \
    X(PAR_RATIO, "par_ratio", "par", "Ratio", LOG, 1.5f, 20, 10, 0, ":1", "", 0)                                  \
    X(PAR_ATT, "par_att", "par", "Attack", LOG, 0.1f, 100, 2, 0, "ms", "", 0)                                     \
    X(PAR_REL, "par_rel", "par", "Release", LOG, 10, 2000, 150, 0, "ms", "", 0)                                   \
    X(PAR_MAKEUP, "par_makeup", "par", "Make-up", LIN, 0, 36, 20, 0.1f, "dB", "", 0)                              \
    X(PAR_RET, "par_ret", "par", "Return", LIN, -60, 12, -6, 0.1f, "dB", "", 0)                                   \
    /* Glue compressor */                                                                                         \
    X(GLUE_ON, "glue_on", "glue", "Glue compressor", BOOL, 0, 1, 1, 1, "", "", 0)                                 \
    X(GLUE_THR, "glue_thr", "glue", "Threshold", LIN, -40, 0, -10, 0.1f, "dB", "", 0)                             \
    X(GLUE_RATIO, "glue_ratio", "glue", "Ratio", ENUM, 0, 2, 0, 1, "", "2,4,10", 0)                               \
    X(GLUE_ATT, "glue_att", "glue", "Attack (ms)", ENUM, 0, 6, 5, 1, "", ".01,.1,.3,1,3,10,30", 0)                \
    X(GLUE_REL, "glue_rel", "glue", "Release (s)", ENUM, 0, 6, 6, 1, "", ".1,.2,.4,.6,.8,1.2,A", 0)               \
    X(GLUE_MAKEUP, "glue_makeup", "glue", "Make-up", LIN, 0, 20, 0, 0.1f, "dB", "", 0)                            \
    X(GLUE_RANGE, "glue_range", "glue", "Range (max reduction)", LIN, 1, 40, 40, 0.5f, "dB", "", 0)               \
    X(GLUE_WET, "glue_wet", "glue", "Dry / wet", LIN, 0, 100, 100, 1, "%", "", 0)                                 \
    X(GLUE_SC_HP, "glue_sc_hp", "glue", "SC high pass (20 = off)", LOG, 20, 500, 20, 0, "Hz", "", 0)              \
    X(GLUE_CLIP, "glue_clip", "glue", "Soft clip", BOOL, 0, 1, 0, 1, "", "", 0)                                   \
    /* Main cuts */                                                                                               \
    X(EQ_LO_ON, "eq_lo_on", "eq", "Low cut", BOOL, 0, 1, 1, 1, "", "", 0)                                         \
    X(EQ_LO_F, "eq_lo_f", "eq", "Low cut frequency", LOG, 15, 300, 30, 0, "Hz", "", 0)                            \
    X(EQ_LO_SLOPE, "eq_lo_slope", "eq", "Low cut slope", ENUM, 0, 1, 0, 1, "", "12 dB/oct,24 dB/oct", 0)          \
    X(EQ_HI_ON, "eq_hi_on", "eq", "High cut", BOOL, 0, 1, 0, 1, "", "", 0)                                        \
    X(EQ_HI_F, "eq_hi_f", "eq", "High cut frequency", LOG, 2000, 20000, 16000, 0, "Hz", "", 0)                    \
    X(EQ_HI_SLOPE, "eq_hi_slope", "eq", "High cut slope", ENUM, 0, 1, 0, 1, "", "12 dB/oct,24 dB/oct", 0)         \
    /* Limiter */                                                                                                 \
    X(LIM_ON, "lim_on", "lim", "Limiter", BOOL, 0, 1, 1, 1, "", "", 0)                                            \
    X(LIM_GAIN, "lim_gain", "lim", "Gain", LIN, 0, 24, 0, 0.1f, "dB", "", 0)                                      \
    X(LIM_CEIL, "lim_ceil", "lim", "Ceiling", LIN, -24, 0, -1, 0.1f, "dB", "", 0)                                 \
    X(LIM_REL, "lim_rel", "lim", "Release", LOG, 1, 1000, 100, 0, "ms", "", 0)                                    \
    X(LIM_LA, "lim_la", "lim", "Look-ahead", LIN, 0, 5, 1.5f, 0.1f, "ms", "", 0)                                  \
    /* Output */                                                                                                  \
    X(OUT_LVL, "out_lvl", "out", "Output level", LIN, -60, 0, 0, 0.1f, "dB", "", 0)                               \
    X(BYPASS, "bypass", "out", "Bypass", BOOL, 0, 1, 0, 1, "", "", 1)

typedef enum {
#define X(name, ...) MS_P_##name,
    MS_PARAMS(X)
#undef X
    MS_P_COUNT
} ms_param_t;

typedef struct {
    const char *id;
    const char *group;
    const char *label;
    ms_kind_t kind;
    float min, max, def;
    float step;  // 0 = continuous
    const char *unit;
    const char *options;  // enum names, comma separated
    bool not_saved;       // setup aid: back at its default after power-up
} ms_param_def_t;

typedef struct {
    const char *id;
    const char *title;
} ms_group_def_t;

extern const ms_param_def_t ms_param_defs[MS_P_COUNT];
extern const ms_group_def_t ms_group_defs[];
extern const int ms_group_count;

void ms_params_defaults(float values[MS_P_COUNT]);
int ms_param_find(const char *id);  // -1 = unknown
// Into the range; switches and lists snap to a whole number.
float ms_param_clamp(int index, float value);

// Settings as text, one `set <id> <value>` line per saved parameter (the format
// of the USB `set` command, the stored blob and the page's export file).
// Returns the length, 0 if `cap` is too small.
size_t ms_params_export(const float values[MS_P_COUNT], char *text, size_t cap);
// Applies every `set` line of a text; unknown names and other lines are skipped.
// Returns how many parameters were set.
int ms_params_import(float values[MS_P_COUNT], const char *text);

// `block` = frames per ms_dsp_process call (sets the gain smoothing).
void ms_coefs_from_params(const float values[MS_P_COUNT], float fs, int block, ms_coefs_t *c);

#ifdef __cplusplus
}
#endif
