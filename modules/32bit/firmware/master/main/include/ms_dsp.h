#pragma once

// 32bit master: end-of-chain processor (kick + mix -> mono main). Plain C, no
// ESP-IDF: the same file runs in the firmware, the host tests and the WAV render.
//
//   IN L kick -> trim -> filter -> limiter ------------------+--> kick level --+
//                          |                                 |                 |
//                          | key (at the limiter's input)    +-> send -+       |
//                          v                                           v       v
//   IN R mix  -> trim -> filter -> 3-band dynamics ---------+--> send -> parallel compressor -> return
//                                                            |                                    |
//                                                            +--> mix level ---------------------(+)
//                                                                                                 |
//   OUT L = OUT R <- output level <- limiter <- filter <- glue compressor <-----------------------+
//
// The effects of each strip run in the order the settings give (k_order, m_order,
// o_order); the drawing is the factory order. A filter is a low cut and a high cut.
//
// Coefficients (ms_coefs_t) are a pure function of the parameter values and are
// computed outside the audio thread (ms_params.c); the audio thread only copies
// them in at a block boundary (ms_dsp_set_coefs).

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MS_BLOCK_MAX 64  // most frames per ms_dsp_process call
#define MS_LA_SIZE 256   // look-ahead / delay rings (power of two); the longest look-ahead is MS_LA_SIZE - 1 samples
#define MS_BANDS 3       // multiband: 0 low, 1 mid, 2 high
#define MS_CUT_MAX 4     // second-order sections of the steepest cut (48 dB/oct)

// The effects that can change places on a strip.
enum { MS_DEV_FLT, MS_DEV_LIM, MS_DEV_MB, MS_DEV_GLUE };

// Second-order state-variable filter (trapezoidal, Zavalishin / Simper): one
// kernel gives the low pass, high pass and all pass, and its coefficients stay
// well conditioned in single precision down to the 10 Hz sub cut.
typedef struct {
    float a1, a2, a3;
    float k;  // 1 / Q
} ms_svf_coef_t;

typedef struct {
    float ic1, ic2;
} ms_svf_state_t;

// Filter device: low cut (high pass) and high cut (low pass), each 0 (off), 1, 2
// or 4 second-order sections.
typedef struct {
    int lc_n, hc_n;
    ms_svf_coef_t lc[MS_CUT_MAX], hc[MS_CUT_MAX];
} ms_flt_coef_t;

typedef struct {
    ms_svf_state_t lc[MS_CUT_MAX], hc[MS_CUT_MAX];
} ms_flt_state_t;

// Downward compressor: gain computer in dB, attack / release on the gain reduction.
typedef struct {
    float thr_db;
    float slope;      // 1 - 1 / ratio
    float half_knee;  // dB, 0 = hard knee
    float inv_2knee;  // 1 / (2 x knee), 0 = hard knee
    float range_db;   // most gain reduction
    float att, rel;   // one-pole coefficients per sample
    bool rms;         // detector: mean square over ~10 ms instead of the peak
    float rms_coef;
} ms_comp_coef_t;

typedef struct {
    float gr;  // gain reduction, dB >= 0
    float ms;  // mean square
} ms_comp_state_t;

// Glue compressor: the sidechain of an analog VCA bus compressor (SSL G series),
// as a circuit model and not a copy of one unit.
//
//   in --+------------------------------> audio gain cell --> out
//        |                                      ^
//        +--> sidechain gain cell --> rectifier, threshold, ratio --> diode --> attack R --+--> buffer
//                    ^                                                                     |      |
//                    |                                                       timing capacitor     |
//                    +----------------------------------------------------- (gain reduction) <----+
//
// - Feedback: the detector reads the signal behind a second gain cell that follows
//   the audio one, so it sees the compressed level. The gain behind the threshold
//   is ratio - 1, which closes to the ratio on the switch; the loop makes the
//   attack faster the harder it works.
// - Timing: the capacitor voltage is the gain reduction in dB. The attack resistor
//   charges it through a diode, the release resistor across it discharges it all
//   the time, so a slow attack with a fast release compresses less. Release A is
//   two capacitors in series, each with its own resistor: a small fast one that
//   takes a short peak and a large slow one that fills while the compressor works.
// - Each sample is one implicit step of that network, loop included: no delay in
//   the feedback, stable at the fastest attack.
typedef struct {
    float thr_db;
    float fb;            // gain behind the threshold: ratio - 1
    float half_knee;     // dB at the detector
    float inv_knee;      // 1 / knee
    float range_db;      // most gain reduction
    float keep1, keep2;  // what the release resistors leave on each capacitor per sample
    float chg1, chg2;    // charge per sample and dB across the attack resistor
    float chg;           // chg1 + chg2
    float inv_chg;
    float inv_lin;       // 1 / (1 + chg x ratio): the step above the knee
} ms_glue_coef_t;

typedef struct {
    float v1, v2;  // capacitor voltages, dB of gain reduction; v2 only charges in release A
} ms_glue_state_t;

// Look-ahead peak limiter: sliding minimum of the wanted gain over the look-ahead,
// release, then a moving average as long as the look-ahead. Output = input delayed
// by `la` samples and never above `ceil`.
//
// Auto release (program dependent, two stages): the gain is the lower of a fast
// stage (takes every peak, lets go in ~30 ms) and a slow stage that follows the
// wanted gain with a ~100 ms attack and lets go in ~1 s. A lone peak hardly moves
// the slow stage, so the gain comes back quickly (punch, little pumping); while
// the limiter works all the time, the slow stage sits at the average reduction
// and the fast one only returns to it (less distortion than a fast release, less
// pumping than a slow one).
typedef struct {
    bool on;
    float drive;  // input gain
    float ceil;   // linear
    float rel;    // release coefficient per sample (the fast stage in auto)
    bool auto_rel;
    float slow_att, slow_rel;  // auto: the slow stage's coefficients per sample
    int la;       // look-ahead in samples, 0 .. MS_LA_SIZE - 1
} ms_lim_coef_t;

typedef struct {
    float x[MS_LA_SIZE];
    int32_t g[MS_LA_SIZE];  // released gain, Q22 (integer: the running sum never drifts)
    float dq_val[MS_LA_SIZE];
    uint32_t dq_idx[MS_LA_SIZE];
    uint32_t dq_head, dq_tail;  // sliding-minimum queue: [head, tail)
    uint32_t pos;
    int32_t g_sum;
    float g_rel;
    float g_slow;  // auto release: the slow stage
    int la;  // look-ahead the state was set up for
} ms_lim_state_t;

// Gains that are smoothed (per block) when a setting moves.
enum {
    MS_G_TRIM_K,
    MS_G_TRIM_M,
    MS_G_LVL_K,
    MS_G_LVL_M,
    MS_G_SEND_K,
    MS_G_SEND_M,
    MS_G_PAR_RET,  // parallel make-up x return
    MS_G_MB_LO,    // band gain x multiband output
    MS_G_MB_MID,
    MS_G_MB_HI,
    MS_G_GLUE_MAKEUP,
    MS_G_OUT,
    MS_G_BYP_K,  // bypass: kick and mix straight out (channel off / solo, master off)
    MS_G_BYP_M,
    MS_G_COUNT
};

typedef struct {
    bool bypass;
    float g[MS_G_COUNT];
    float g_smooth;  // per-block smoothing coefficient

    // Order of the effects per strip: MS_DEV_* in signal order
    uint8_t k_order[2];  // filter, limiter
    uint8_t m_order[2];  // filter, multiband
    uint8_t o_order[3];  // glue, filter, limiter

    // Kick
    ms_flt_coef_t k_flt;
    ms_lim_coef_t k_lim;

    // Mix
    ms_flt_coef_t m_flt;

    // Multiband dynamics (Linkwitz-Riley 24 dB/oct crossovers)
    bool mb_on;
    bool mb_sc_kick;  // key from the kick bands, else from the mix bands
    float mb_sc_gain;
    float mb_amount;  // 0..1 scales the gain reduction
    int mb_solo;      // 0 off, 1..3 = only this band
    ms_svf_coef_t x1, x2;  // Butterworth sections at the two crossover frequencies
    bool mb_band_on[MS_BANDS];
    ms_comp_coef_t mb[MS_BANDS];

    // Parallel compressor
    bool par_on;
    ms_comp_coef_t par;

    // Glue compressor
    bool glue_on;
    ms_glue_coef_t glue;
    float glue_wet;  // 0..1
    bool glue_clip;
    bool glue_sc_hp_on;
    ms_svf_coef_t glue_sc_hp;

    // Master filter and limiter
    ms_flt_coef_t o_flt;
    ms_lim_coef_t lim;
} ms_coefs_t;

// Peaks are linear, gain reductions in dB (>= 0); all are the largest value since
// the last ms_dsp_take_meters.
typedef struct {
    float raw_k, raw_m;  // converter level before the trims (1.0 = clipping)
    float in_k, in_m;    // after the trims
    float kick;          // after the kick limiter
    float mix;           // after the multiband
    float par;           // parallel return
    float out;
    float gr_klim;
    float gr_mb[MS_BANDS];
    float gr_par;
    float gr_glue;
    float gr_lim;
} ms_meters_t;

typedef struct {
    ms_coefs_t c;
    float g_cur[MS_G_COUNT];

    ms_flt_state_t k_flt, m_flt, o_flt;
    ms_lim_state_t k_lim;
    float m_delay[MS_LA_SIZE];
    uint32_t m_delay_pos;

    // Crossover: mix path and key path
    ms_svf_state_t m_x1[3], m_x2[3], m_x2_ap;  // [0] split, [1] low pass, [2] high pass
    ms_svf_state_t k_x1[3], k_x2[3];
    ms_comp_state_t mb[MS_BANDS];

    ms_comp_state_t par;
    ms_glue_state_t glue;
    ms_svf_state_t glue_sc_hp;
    ms_lim_state_t lim;

    ms_meters_t meters;
    volatile bool meters_reset;
} ms_dsp_t;

void ms_dsp_init(ms_dsp_t *d, const ms_coefs_t *c);
// Audio thread, between blocks.
void ms_dsp_set_coefs(ms_dsp_t *d, const ms_coefs_t *c);
// n <= MS_BLOCK_MAX frames; in_k / in_m / out are +-1.0 full scale. out may alias an input.
void ms_dsp_process(ms_dsp_t *d, const float *in_k, const float *in_m, float *out, int n);
// Other thread: copy the meters and restart them.
void ms_dsp_take_meters(ms_dsp_t *d, ms_meters_t *out);
// Delay of the chain in samples (the two look-aheads).
int ms_coefs_latency(const ms_coefs_t *c);

// Coefficient helpers (used by ms_params.c and the tests).
void ms_svf_set(ms_svf_coef_t *c, float fs, float f, float q);
// Sections of a cut: slope 0 / 1 / 2 = 12 / 24 / 48 dB/oct (1 / 2 / 4 sections,
// Butterworth at q = 1 / sqrt(2); q scales the sharpest one). Returns the count.
int ms_cut_set(ms_svf_coef_t c[MS_CUT_MAX], int slope, float fs, float f, float q);
float ms_time_coef(float fs, float seconds);
float ms_db_to_lin(float db);

// log2 / 2^x approximations (errors < 0.006 dB / 0.0015 dB), exposed for the tests.
float ms_fast_log2(float x);
float ms_fast_exp2(float x);

#ifdef __cplusplus
}
#endif
