#include "ms_dsp.h"

#include <math.h>
#include <string.h>

#define DB_PER_LOG2 6.0205999f
#define LOG2_PER_DB 0.16609640f
#define GQ 4194304.0f  // limiter gain 1.0 in Q22
#define GQ_ONE (1 << 22)
#define LA_MASK (MS_LA_SIZE - 1)

// Glue soft clip: linear to -6 dB, then bends towards -0.5 dB.
#define CLIP_KNEE 0.5f
#define CLIP_MAX 0.944f

// Glue rectifier: its two halves are 2.8 % apart (resistor tolerance, as measured
// on a G series unit), which leaves ripple at the signal frequency on the timing
// capacitor: a little second harmonic under gain reduction.
#define GLUE_RECT_SKEW_DB 0.25f
// Glue gain cell: second and third harmonic that grow with the level into it,
// about 0.05 % and 0.03 % at -6 dB. A choice within what such VCAs do, not a
// measurement. Above +-COLOUR_MAX the curve goes on straight.
#define GLUE_COLOUR_2 0.002f
#define GLUE_COLOUR_3 0.005f
#define GLUE_COLOUR_MAX 2.0f

// ---------------------------------------------------------------- fast math

// Cubic through the ends of each octave: continuous, no table.
float ms_fast_log2(float x) {
    union {
        float f;
        uint32_t i;
    } u = {x};
    int e = (int)((u.i >> 23) & 0xFF) - 127;
    u.i = (u.i & 0x007FFFFFu) | 0x3F800000u;
    float t = u.f - 1.0f;
    return (float)e + t * (1.0f + (t - 1.0f) * (-0.42286531f + 0.15922010f * t));
}

float ms_fast_exp2(float x) {
    int i = (int)x;
    if ((float)i > x) i--;
    float t = x - (float)i;
    union {
        float f;
        uint32_t u;
    } s;
    s.u = (uint32_t)(i + 127) << 23;
    return s.f * (1.0f + t * (1.0f + (t - 1.0f) * (0.30410988f + 0.07924493f * t)));
}

float ms_db_to_lin(float db) {
    return powf(10.0f, db * 0.05f);
}

float ms_time_coef(float fs, float seconds) {
    if (seconds <= 0.0f) return 1.0f;
    return 1.0f - expf(-1.0f / (fs * seconds));
}

// ---------------------------------------------------------------- filters

void ms_svf_set(ms_svf_coef_t *c, float fs, float f, float q) {
    if (f > 0.45f * fs) f = 0.45f * fs;
    if (f < 1.0f) f = 1.0f;
    float g = tanf(3.14159265f * f / fs);
    c->k = 1.0f / q;
    c->a1 = 1.0f / (1.0f + g * (g + c->k));
    c->a2 = g * c->a1;
    c->a3 = g * c->a2;
}

int ms_cut_set(ms_svf_coef_t c[MS_CUT_MAX], int slope, float fs, float f, float q) {
    // Butterworth section Qs, the sharpest last.
    static const float q2[] = {0.70710678f};
    static const float q4[] = {0.54119610f, 1.30656296f};
    static const float q8[] = {0.50979558f, 0.60134489f, 0.89997622f, 2.56291545f};
    const float *bq = slope >= 2 ? q8 : slope == 1 ? q4 : q2;
    const int n = slope >= 2 ? 4 : slope == 1 ? 2 : 1;
    for (int i = 0; i < n; i++) {
        float qi = bq[i];
        if (i == n - 1) qi *= q * 1.41421356f;
        ms_svf_set(&c[i], fs, f, qi);
    }
    for (int i = n; i < MS_CUT_MAX; i++) c[i] = c[0];
    return n;
}

#define SVF_TICK(x)                                    \
    float v3 = (x) - ic2;                              \
    float v1 = c->a1 * ic1 + c->a2 * v3;               \
    float v2 = ic2 + c->a2 * ic1 + c->a3 * v3;         \
    ic1 = 2.0f * v1 - ic1;                             \
    ic2 = 2.0f * v2 - ic2;

static void svf_hp(const ms_svf_coef_t *c, ms_svf_state_t *s, const float *in, float *out, int n) {
    float ic1 = s->ic1, ic2 = s->ic2;
    for (int i = 0; i < n; i++) {
        float x = in[i];
        SVF_TICK(x)
        out[i] = x - c->k * v1 - v2;
    }
    s->ic1 = ic1;
    s->ic2 = ic2;
}

static void svf_lp(const ms_svf_coef_t *c, ms_svf_state_t *s, const float *in, float *out, int n) {
    float ic1 = s->ic1, ic2 = s->ic2;
    for (int i = 0; i < n; i++) {
        SVF_TICK(in[i])
        (void)v1;
        out[i] = v2;
    }
    s->ic1 = ic1;
    s->ic2 = ic2;
}

static void svf_ap(const ms_svf_coef_t *c, ms_svf_state_t *s, const float *in, float *out, int n) {
    float ic1 = s->ic1, ic2 = s->ic2;
    const float k2 = 2.0f * c->k;
    for (int i = 0; i < n; i++) {
        float x = in[i];
        SVF_TICK(x)
        (void)v2;
        out[i] = x - k2 * v1;
    }
    s->ic1 = ic1;
    s->ic2 = ic2;
}

// Low and high pass of the same input from one filter.
static void svf_split(const ms_svf_coef_t *c, ms_svf_state_t *s, const float *in, float *lo, float *hi, int n) {
    float ic1 = s->ic1, ic2 = s->ic2;
    for (int i = 0; i < n; i++) {
        float x = in[i];
        SVF_TICK(x)
        lo[i] = v2;
        hi[i] = x - c->k * v1 - v2;
    }
    s->ic1 = ic1;
    s->ic2 = ic2;
}

// Linkwitz-Riley 24 dB/oct split (two Butterworth sections each way). lo + hi is
// an all pass of the input. st[0] is shared, st[1] low, st[2] high.
static void lr4_split(const ms_svf_coef_t *c, ms_svf_state_t st[3], const float *in, float *lo, float *hi, int n) {
    svf_split(c, &st[0], in, lo, hi, n);
    svf_lp(c, &st[1], lo, lo, n);
    svf_hp(c, &st[2], hi, hi, n);
}

static void three_bands(const ms_coefs_t *c, ms_svf_state_t x1[3], ms_svf_state_t x2[3], ms_svf_state_t *ap,
                        const float *in, float *lo, float *mid, float *hi, int n) {
    float rest[MS_BLOCK_MAX];
    lr4_split(&c->x1, x1, in, lo, rest, n);
    // The low band takes the phase of the upper crossover, so the three bands add up flat.
    if (ap) svf_ap(&c->x2, ap, lo, lo, n);
    lr4_split(&c->x2, x2, rest, mid, hi, n);
}

static void flt_run(const ms_flt_coef_t *c, ms_flt_state_t *s, float *x, int n) {
    for (int i = 0; i < c->lc_n; i++) svf_hp(&c->lc[i], &s->lc[i], x, x, n);
    for (int i = 0; i < c->hc_n; i++) svf_lp(&c->hc[i], &s->hc[i], x, x, n);
}

// ---------------------------------------------------------------- dynamics

// Writes the linear gain for each sample of the detector signal; returns the
// largest gain reduction (dB) of the block. `amount` scales the reduction.
static float comp_run(const ms_comp_coef_t *c, ms_comp_state_t *s, const float *det, float *gain, int n,
                      float amount) {
    float gr = s->gr, ms = s->ms, gr_max = 0.0f;
    const float scale = -amount * LOG2_PER_DB;
    for (int i = 0; i < n; i++) {
        float lvl;
        if (c->rms) {
            ms += c->rms_coef * (det[i] * det[i] + 1e-20f - ms);
            lvl = (0.5f * DB_PER_LOG2) * ms_fast_log2(ms);
        } else {
            lvl = DB_PER_LOG2 * ms_fast_log2(fabsf(det[i]) + 1e-10f);
        }
        float over = lvl - c->thr_db;
        float want;
        if (over <= -c->half_knee) {
            want = 0.0f;
        } else if (over >= c->half_knee) {
            want = c->slope * over;
        } else {
            float q = over + c->half_knee;
            want = c->slope * q * q * c->inv_2knee;
        }
        if (want > c->range_db) want = c->range_db;
        gr += (want > gr ? c->att : c->rel) * (want - gr);
        if (gr < 1e-9f) gr = 0.0f;
        if (gr > gr_max) gr_max = gr;
        gain[i] = ms_fast_exp2(gr * scale);
    }
    s->gr = gr;
    s->ms = ms;
    return gr_max * amount;
}

// The glue's sidechain (see ms_glue_coef_t). Writes the linear gain for each
// sample of the detector input; returns the largest gain reduction (dB).
static float glue_run(const ms_glue_coef_t *c, ms_glue_state_t *s, const float *det, float *gain, int n) {
    float v1 = s->v1, v2 = s->v2, cv = s->cv, gr_max = 0.0f;
    for (int i = 0; i < n; i++) {
        float d = det[i];
        float lvl = DB_PER_LOG2 * ms_fast_log2(fabsf(d) + 1e-10f);
        if (d < 0.0f) lvl -= GLUE_RECT_SKEW_DB;
        const float v = v1 + v2;
        // Level behind the sidechain gain cell, over the threshold.
        const float over = lvl - c->thr_db - v;
        v1 *= c->keep1;
        v2 *= c->keep2;
        if (over > -c->half_knee) {
            float want, slope, inv;
            if (over >= c->half_knee) {
                want = c->fb * over;
                slope = c->fb;
                inv = c->inv_lin;
            } else {
                float q = over + c->half_knee;
                slope = c->fb * q * c->inv_knee;
                want = 0.5f * q * slope;
                inv = 1.0f / (1.0f + c->chg * (1.0f + slope));
            }
            if (want > v) {
                // The diode conducts. The new capacitor voltage vn solves
                //   vn = rest + chg x (want + slope x (v - vn) - vn)
                // where the middle term is how the detector falls as vn rises.
                const float rest = v1 + v2;
                float vn = (rest + c->chg * (want + slope * v)) * inv;
                if (vn > c->range_db) vn = c->range_db;
                float across = (vn - rest) * c->inv_chg;
                if (across > 0.0f) {
                    v1 += c->chg1 * across;
                    v2 += c->chg2 * across;
                }
            }
        }
        if (v1 < 1e-9f) v1 = 0.0f;
        if (v2 < 1e-9f) v2 = 0.0f;
        // The audio gain cell follows the capacitor through its control low pass.
        cv += c->cv_coef * (v1 + v2 - cv);
        if (cv < 1e-9f) cv = 0.0f;
        if (cv > gr_max) gr_max = cv;
        gain[i] = ms_fast_exp2(-LOG2_PER_DB * cv);
    }
    s->v1 = v1;
    s->v2 = v2;
    s->cv = cv;
    return gr_max;
}

static void lim_reset(ms_lim_state_t *s, int la) {
    memset(s, 0, sizeof(*s));
    for (int i = 0; i < MS_LA_SIZE; i++) s->g[i] = GQ_ONE;
    s->g_sum = la * GQ_ONE;
    s->g_rel = 1.0f;
    s->g_slow = 1.0f;
    s->la = la;
}

// Returns the smallest gain of the block.
static float lim_run(const ms_lim_coef_t *c, ms_lim_state_t *s, const float *in, float *out, int n) {
    const uint32_t la = (uint32_t)s->la;
    const float norm = la ? 1.0f / ((float)la * GQ) : 0.0f;
    const float ceil = c->ceil;
    uint32_t pos = s->pos, head = s->dq_head, tail = s->dq_tail;
    int32_t g_sum = s->g_sum;
    float g_rel = s->g_rel, g_slow = s->g_slow, g_min = 1.0f;
    for (int i = 0; i < n; i++) {
        float x = in[i] * c->drive;
        float a = fabsf(x);
        float want = a > ceil ? ceil / a : 1.0f;

        // Smallest wanted gain of the last la + 1 samples (monotonic queue).
        if (head != tail && pos - s->dq_idx[head & LA_MASK] > la) head++;
        while (tail != head && s->dq_val[(tail - 1) & LA_MASK] >= want) tail--;
        s->dq_val[tail & LA_MASK] = want;
        s->dq_idx[tail & LA_MASK] = pos;
        tail++;
        float hold = s->dq_val[head & LA_MASK];

        g_rel += c->rel * (1.0f - g_rel);
        if (g_rel > hold) g_rel = hold;
        if (c->auto_rel) {
            // The slow stage never goes below the wanted gain: it only holds back
            // the fast stage's release.
            g_slow += (hold < g_slow ? c->slow_att : c->slow_rel) * (hold - g_slow);
            if (g_rel > g_slow) g_rel = g_slow;
        }

        float g, y;
        if (la) {
            // Average of the last la gains: each already covers the sample that
            // leaves the delay now, so the ramp ends exactly at the peak.
            int32_t gq = (int32_t)(g_rel * GQ);
            g_sum += gq - s->g[(pos - la) & LA_MASK];
            s->g[pos & LA_MASK] = gq;
            g = (float)g_sum * norm;
            s->x[pos & LA_MASK] = x;
            y = s->x[(pos - la) & LA_MASK] * g;
        } else {
            g = g_rel;
            y = x * g;
        }
        if (y > ceil) y = ceil;
        if (y < -ceil) y = -ceil;
        if (g < g_min) g_min = g;
        out[i] = y;
        pos++;
    }
    s->pos = pos;
    s->dq_head = head;
    s->dq_tail = tail;
    s->g_sum = g_sum;
    s->g_rel = g_rel;
    s->g_slow = g_slow;
    return g_min;
}

static inline float soft_clip(float x) {
    float a = fabsf(x);
    if (a <= CLIP_KNEE) return x;
    float u = (a - CLIP_KNEE) * (1.0f / (CLIP_MAX - CLIP_KNEE));
    float y = CLIP_KNEE + (CLIP_MAX - CLIP_KNEE) * u / (1.0f + u);
    return x < 0.0f ? -y : y;
}

// ---------------------------------------------------------------- meters

static inline void peak_into(float *meter, const float *x, int n) {
    float pk = *meter;
    for (int i = 0; i < n; i++) {
        float a = fabsf(x[i]);
        if (a > pk) pk = a;
    }
    *meter = pk;
}

static inline void max_into(float *meter, float v) {
    if (v > *meter) *meter = v;
}

static inline float gain_to_gr_db(float g) {
    return g < 1.0f ? -DB_PER_LOG2 * ms_fast_log2(g + 1e-10f) : 0.0f;
}

void ms_dsp_take_meters(ms_dsp_t *d, ms_meters_t *out) {
    *out = d->meters;
    d->meters_reset = true;
}

// ---------------------------------------------------------------- chain

static int lim_delay(const ms_lim_coef_t *c) {
    return c->on ? c->la : 0;
}

int ms_coefs_latency(const ms_coefs_t *c) {
    return c->bypass ? 0 : lim_delay(&c->k_lim) + lim_delay(&c->lim) + (c->glue_on ? (int)c->glue.dly : 0);
}

void ms_dsp_init(ms_dsp_t *d, const ms_coefs_t *c) {
    memset(d, 0, sizeof(*d));
    d->c = *c;
    for (int i = 0; i < MS_G_COUNT; i++) d->g_cur[i] = c->g[i];
    lim_reset(&d->k_lim, c->k_lim.la);
    lim_reset(&d->lim, c->lim.la);
}

void ms_dsp_set_coefs(ms_dsp_t *d, const ms_coefs_t *c) {
    d->c = *c;
    // A new look-ahead length restarts that limiter (a short gap in its output).
    if (d->k_lim.la != c->k_lim.la) lim_reset(&d->k_lim, c->k_lim.la);
    if (d->lim.la != c->lim.la) lim_reset(&d->lim, c->lim.la);
}

// Three-band dynamics on the mix (in place), keyed by the kick or by itself.
static void multiband(ms_dsp_t *d, const float *key, float *m, int n) {
    const ms_coefs_t *c = &d->c;
    float band[MS_BANDS][MS_BLOCK_MAX], det[MS_BANDS][MS_BLOCK_MAX], gain[MS_BLOCK_MAX];
    three_bands(c, d->m_x1, d->m_x2, &d->m_x2_ap, m, band[0], band[1], band[2], n);
    if (c->mb_sc_kick) three_bands(c, d->k_x1, d->k_x2, NULL, key, det[0], det[1], det[2], n);
    for (int i = 0; i < n; i++) m[i] = 0.0f;
    for (int b = 0; b < MS_BANDS; b++) {
        float bg = d->g_cur[MS_G_MB_LO + b];
        if (c->mb_solo && c->mb_solo != b + 1) bg = 0.0f;
        if (c->mb_band_on[b]) {
            const float *dsrc = c->mb_sc_kick ? det[b] : band[b];
            max_into(&d->meters.gr_mb[b], comp_run(&c->mb[b], &d->mb[b], dsrc, gain, n, c->mb_amount));
            for (int i = 0; i < n; i++) m[i] += band[b][i] * gain[i] * bg;
        } else {
            for (int i = 0; i < n; i++) m[i] += band[b][i] * bg;
        }
    }
}

// Glue compressor on the main sum (in place). The audio waits for the gain
// cell's control (ms_glue_coef_t); the wait is filled also with the glue off, so
// switching it on does not play old samples.
static void glue(ms_dsp_t *d, float *x, int n) {
    const ms_coefs_t *c = &d->c;
    ms_glue_state_t *s = &d->glue;
    float a_dly[MS_BLOCK_MAX];
    uint32_t pos = s->dly_pos;
    for (int i = 0; i < n; i++) {
        s->dly[pos & (MS_GLUE_DLY_SIZE - 1)] = x[i];
        a_dly[i] = s->dly[(pos - c->glue.dly) & (MS_GLUE_DLY_SIZE - 1)];
        pos++;
    }
    s->dly_pos = pos;
    if (!c->glue_on) return;
    float gain[MS_BLOCK_MAX];
    const float *dsrc = x;
    float sc[MS_BLOCK_MAX];
    if (c->glue_sc_hp_on) {
        svf_hp(&c->glue_sc_hp, &d->glue_sc_hp, x, sc, n);
        dsrc = sc;
    }
    max_into(&d->meters.gr_glue, glue_run(&c->glue, s, dsrc, gain, n));
    const float makeup = d->g_cur[MS_G_GLUE_MAKEUP], wet = c->glue_wet;
    for (int i = 0; i < n; i++) {
        float a = a_dly[i];
        float lim = a > GLUE_COLOUR_MAX ? GLUE_COLOUR_MAX : (a < -GLUE_COLOUR_MAX ? -GLUE_COLOUR_MAX : a);
        float vca = (a + lim * lim * (GLUE_COLOUR_2 - GLUE_COLOUR_3 * lim)) * gain[i];
        x[i] = a + wet * (vca * makeup - a);
    }
    if (c->glue_clip) {
        for (int i = 0; i < n; i++) x[i] = soft_clip(x[i]);
    }
}

void ms_dsp_process(ms_dsp_t *d, const float *in_k, const float *in_m, float *out, int n) {
    const ms_coefs_t *c = &d->c;
    ms_meters_t *mt = &d->meters;
    float k[MS_BLOCK_MAX], m[MS_BLOCK_MAX], key[MS_BLOCK_MAX], x[MS_BLOCK_MAX], gain[MS_BLOCK_MAX];
    float *g = d->g_cur;

    if (n <= 0 || n > MS_BLOCK_MAX) return;
    if (d->meters_reset) {
        memset(mt, 0, sizeof(*mt));
        d->meters_reset = false;
    }
    for (int i = 0; i < MS_G_COUNT; i++) g[i] += c->g_smooth * (c->g[i] - g[i]);

    peak_into(&mt->raw_k, in_k, n);
    peak_into(&mt->raw_m, in_m, n);
    for (int i = 0; i < n; i++) {
        k[i] = in_k[i] * g[MS_G_TRIM_K];
        m[i] = in_m[i] * g[MS_G_TRIM_M];
    }
    peak_into(&mt->in_k, k, n);
    peak_into(&mt->in_m, m, n);

    if (c->bypass) {
        for (int i = 0; i < n; i++) {
            float y = k[i] * g[MS_G_BYP_K] + m[i] * g[MS_G_BYP_M];
            out[i] = y > 1.0f ? 1.0f : (y < -1.0f ? -1.0f : y);
        }
        peak_into(&mt->out, out, n);
        return;
    }

    // Kick: filter and limiter in either order. The multiband key is the kick at
    // the limiter's input, so it leads the delayed audio by the kick look-ahead.
    for (int j = 0; j < 2; j++) {
        if (c->k_order[j] == MS_DEV_FLT) {
            flt_run(&c->k_flt, &d->k_flt, k, n);
        } else {
            for (int i = 0; i < n; i++) key[i] = k[i] * c->mb_sc_gain;
            if (c->k_lim.on) max_into(&mt->gr_klim, gain_to_gr_db(lim_run(&c->k_lim, &d->k_lim, k, k, n)));
        }
    }
    peak_into(&mt->kick, k, n);

    // Mix: the same delay as the kick limiter, then filter and multiband dynamics
    // in either order.
    uint32_t delay = (uint32_t)lim_delay(&c->k_lim);
    if (delay) {
        uint32_t pos = d->m_delay_pos;
        for (int i = 0; i < n; i++) {
            d->m_delay[pos & LA_MASK] = m[i];
            m[i] = d->m_delay[(pos - delay) & LA_MASK];
            pos++;
        }
        d->m_delay_pos = pos;
    }
    for (int j = 0; j < 2; j++) {
        if (c->m_order[j] == MS_DEV_FLT) flt_run(&c->m_flt, &d->m_flt, m, n);
        else if (c->mb_on) multiband(d, key, m, n);
    }
    peak_into(&mt->mix, m, n);

    // Main sum, with the parallel compressor fed from both channels.
    for (int i = 0; i < n; i++) x[i] = k[i] * g[MS_G_LVL_K] + m[i] * g[MS_G_LVL_M];
    if (c->par_on) {
        float p[MS_BLOCK_MAX];
        for (int i = 0; i < n; i++) p[i] = k[i] * g[MS_G_SEND_K] + m[i] * g[MS_G_SEND_M];
        max_into(&mt->gr_par, comp_run(&c->par, &d->par, p, gain, n, 1.0f));
        for (int i = 0; i < n; i++) {
            p[i] *= gain[i] * g[MS_G_PAR_RET];
            x[i] += p[i];
        }
        peak_into(&mt->par, p, n);
    }

    for (int j = 0; j < 3; j++) {
        switch (c->o_order[j]) {
            case MS_DEV_GLUE:
                glue(d, x, n);
                break;
            case MS_DEV_FLT:
                flt_run(&c->o_flt, &d->o_flt, x, n);
                break;
            default:
                if (c->lim.on) max_into(&mt->gr_lim, gain_to_gr_db(lim_run(&c->lim, &d->lim, x, x, n)));
                break;
        }
    }

    for (int i = 0; i < n; i++) {
        float y = x[i] * g[MS_G_OUT];
        out[i] = y > 1.0f ? 1.0f : (y < -1.0f ? -1.0f : y);
    }
    peak_into(&mt->out, out, n);
}
