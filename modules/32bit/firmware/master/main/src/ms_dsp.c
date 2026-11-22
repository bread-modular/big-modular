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

void ms_butter_set(ms_svf_coef_t c[2], int n, float fs, float f) {
    if (n >= 2) {
        ms_svf_set(&c[0], fs, f, 0.54119610f);
        ms_svf_set(&c[1], fs, f, 1.30656296f);
    } else {
        ms_svf_set(&c[0], fs, f, 0.70710678f);
        c[1] = c[0];
    }
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

static void cut_hp(const ms_svf_coef_t c[2], ms_svf_state_t s[2], int sections, float *x, int n) {
    for (int i = 0; i < sections; i++) svf_hp(&c[i], &s[i], x, x, n);
}

static void cut_lp(const ms_svf_coef_t c[2], ms_svf_state_t s[2], int sections, float *x, int n) {
    for (int i = 0; i < sections; i++) svf_lp(&c[i], &s[i], x, x, n);
}

// ---------------------------------------------------------------- dynamics

// Writes the linear gain for each sample of the detector signal; returns the
// largest gain reduction (dB) of the block. `amount` scales the reduction.
static float comp_run(const ms_comp_coef_t *c, ms_comp_state_t *s, const float *det, float *gain, int n,
                      float amount) {
    float gr = s->gr, slow = s->slow, ms = s->ms, gr_max = 0.0f;
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
        float g = gr;
        if (c->auto_rel) {
            // The slow stage charges while the compressor works, so a long loud
            // passage recovers slowly and a single hit quickly.
            slow += (gr > slow ? c->slow_att : c->slow_rel) * (gr - slow);
            if (slow < 1e-9f) slow = 0.0f;
            if (slow > g) g = slow;
        }
        if (g > gr_max) gr_max = g;
        gain[i] = ms_fast_exp2(g * scale);
    }
    s->gr = gr;
    s->slow = slow;
    s->ms = ms;
    return gr_max * amount;
}

static void lim_reset(ms_lim_state_t *s, int la) {
    memset(s, 0, sizeof(*s));
    for (int i = 0; i < MS_LA_SIZE; i++) s->g[i] = GQ_ONE;
    s->g_sum = la * GQ_ONE;
    s->g_rel = 1.0f;
    s->la = la;
}

// Returns the smallest gain of the block.
static float lim_run(const ms_lim_coef_t *c, ms_lim_state_t *s, const float *in, float *out, int n) {
    const uint32_t la = (uint32_t)s->la;
    const float norm = la ? 1.0f / ((float)la * GQ) : 0.0f;
    const float ceil = c->ceil;
    uint32_t pos = s->pos, head = s->dq_head, tail = s->dq_tail;
    int32_t g_sum = s->g_sum;
    float g_rel = s->g_rel, g_min = 1.0f;
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
    return c->bypass ? 0 : lim_delay(&c->k_lim) + lim_delay(&c->lim);
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
            float y = k[i] + m[i];
            out[i] = y > 1.0f ? 1.0f : (y < -1.0f ? -1.0f : y);
        }
        peak_into(&mt->out, out, n);
        return;
    }

    // Kick: sub cut, then the limiter. The multiband key is taken before the
    // limiter, so it leads the delayed audio by the kick look-ahead.
    cut_hp(c->k_hp, d->k_hp, c->k_hp_n, k, n);
    for (int i = 0; i < n; i++) key[i] = k[i] * c->mb_sc_gain;
    if (c->k_lim.on) max_into(&mt->gr_klim, gain_to_gr_db(lim_run(&c->k_lim, &d->k_lim, k, k, n)));
    peak_into(&mt->kick, k, n);

    // Mix: low cut, the same delay as the kick limiter, multiband dynamics.
    cut_hp(c->m_hp, d->m_hp, c->m_hp_n, m, n);
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
    if (c->mb_on) {
        float band[MS_BANDS][MS_BLOCK_MAX], det[MS_BANDS][MS_BLOCK_MAX];
        three_bands(c, d->m_x1, d->m_x2, &d->m_x2_ap, m, band[0], band[1], band[2], n);
        if (c->mb_sc_kick) three_bands(c, d->k_x1, d->k_x2, NULL, key, det[0], det[1], det[2], n);
        for (int i = 0; i < n; i++) m[i] = 0.0f;
        for (int b = 0; b < MS_BANDS; b++) {
            float bg = g[MS_G_MB_LO + b];
            if (c->mb_solo && c->mb_solo != b + 1) bg = 0.0f;
            if (c->mb_band_on[b]) {
                const float *dsrc = c->mb_sc_kick ? det[b] : band[b];
                max_into(&mt->gr_mb[b], comp_run(&c->mb[b], &d->mb[b], dsrc, gain, n, c->mb_amount));
                for (int i = 0; i < n; i++) m[i] += band[b][i] * gain[i] * bg;
            } else {
                for (int i = 0; i < n; i++) m[i] += band[b][i] * bg;
            }
        }
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

    if (c->glue_on) {
        const float *dsrc = x;
        float sc[MS_BLOCK_MAX];
        if (c->glue_sc_hp_on) {
            svf_hp(&c->glue_sc_hp, &d->glue_sc_hp, x, sc, n);
            dsrc = sc;
        }
        max_into(&mt->gr_glue, comp_run(&c->glue, &d->glue, dsrc, gain, n, 1.0f));
        const float makeup = g[MS_G_GLUE_MAKEUP], wet = c->glue_wet;
        for (int i = 0; i < n; i++) x[i] += wet * (x[i] * gain[i] * makeup - x[i]);
        if (c->glue_clip) {
            for (int i = 0; i < n; i++) x[i] = soft_clip(x[i]);
        }
    }

    cut_hp(c->eq_lo, d->eq_lo, c->eq_lo_n, x, n);
    cut_lp(c->eq_hi, d->eq_hi, c->eq_hi_n, x, n);
    if (c->lim.on) max_into(&mt->gr_lim, gain_to_gr_db(lim_run(&c->lim, &d->lim, x, x, n)));

    for (int i = 0; i < n; i++) {
        float y = x[i] * g[MS_G_OUT];
        out[i] = y > 1.0f ? 1.0f : (y < -1.0f ? -1.0f : y);
    }
    peak_into(&mt->out, out, n);
}
