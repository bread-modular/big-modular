#include "audio/bm_hall_reverb.h"

#include <math.h>

#include "bm_audio.h"
#include "lib/bm_utils.h"

#define CH BM_HALL_REVERB_CHANNELS
#define STAGES BM_HALL_REVERB_DIFFUSER_STAGES

#define PREDELAY_MS 22.0f
#define MOD_DEPTH_SAMPLES 10.0f   // +-0.23 ms, ~3 cents of drift at 1 Hz
#define HP_HZ 90.0f
#define LP_HZ 9000.0f
#define HF_RT60_RATIO 0.25f       // RT60 at Nyquist / RT60 at DC
#define EARLY_LEVEL 0.25f
#define GLIDE 0.002f              // gain / pole glide per sample ...
#define GLIDE_SAMPLES 4096        // ... for 93 ms after a change, then snapped
#define TWO_PI 6.28318531f
#define SOFT_KNEE 0.7f

// Each diffuser stage spreads its 8 delays over 0..range ms; the ranges double.
static const float diffuser_range_ms[STAGES] = {4.0f, 9.0f, 18.0f, 36.0f};
// Polarity flips per stage (bit c set: channel c inverted).
static const uint8_t diffuser_flips[STAGES] = {0x5A, 0x33, 0x96, 0x69};
// FDN lines: primes near 50 ms x 2^(i/8) at 44.1 kHz (50..92 ms).
static const int32_t late_samples[CH] = {2207, 2411, 2621, 2861, 3119, 3407, 3709, 4049};
static const float lfo_hz[BM_HALL_REVERB_LFOS] = {0.31f, 0.47f, 0.67f, 0.89f};
// Output tap signs: decorrelates the mono sum of the lines.
static const float late_out_sign[CH] = {1.0f, -1.0f, 1.0f, -1.0f, -1.0f, 1.0f, -1.0f, 1.0f};

static void delay_init(bm_hall_delay_t* d, int32_t size) {
    d->size = size;
    d->pos = 0;
    d->data = (float*)allocate_fast(sizeof(float) * (size_t)size);
}

static void delay_destroy(bm_hall_delay_t* d) {
    if (d->data != NULL) {
        free_psram(d->data);
        d->data = NULL;
    }
}

// Sample written `k` samples ago, 1 <= k <= size (read before the write).
static inline float delay_read(const bm_hall_delay_t* d, int32_t k) {
    int32_t i = d->pos - k;
    if (i < 0) i += d->size;
    return d->data[i];
}

static inline float delay_read_frac(const bm_hall_delay_t* d, float k) {
    int32_t k0 = (int32_t)k;
    float frac = k - (float)k0;
    float a = delay_read(d, k0);
    float b = delay_read(d, k0 + 1);
    return a + (b - a) * frac;
}

static inline void delay_write(bm_hall_delay_t* d, float x) {
    d->data[d->pos] = x;
    if (++d->pos == d->size) d->pos = 0;
}

// Fixed delay of exactly `size` samples: the oldest sample is the one the write
// replaces (no read index to compute).
static inline float delay_swap(bm_hall_delay_t* d, float x) {
    float out = d->data[d->pos];
    d->data[d->pos] = x;
    if (++d->pos == d->size) d->pos = 0;
    return out;
}

// 8x8 Hadamard, in place, unnormalised (gain sqrt(8)): the four stages'
// 1 / sqrt(8) are one 1 / 64 on the input.
#define BUTTERFLY(a, b) do { float t_ = x[a]; x[a] = t_ + x[b]; x[b] = t_ - x[b]; } while (0)
static inline void hadamard8(float* x) {
    BUTTERFLY(0, 1); BUTTERFLY(2, 3); BUTTERFLY(4, 5); BUTTERFLY(6, 7);
    BUTTERFLY(0, 2); BUTTERFLY(1, 3); BUTTERFLY(4, 6); BUTTERFLY(5, 7);
    BUTTERFLY(0, 4); BUTTERFLY(1, 5); BUTTERFLY(2, 6); BUTTERFLY(3, 7);
}
#define HADAMARD_INPUT_GAIN (1.0f / 64.0f)

void bm_hall_reverb_init(bm_hall_reverb_t* reverb) {
    const float fs = (float)bm_SAMPLE_RATE;

    reverb->predelay_samples = (int32_t)(PREDELAY_MS * fs / 1000.0f);
    delay_init(&reverb->predelay, reverb->predelay_samples);

    // Fixed pseudo-random spread: channel c of a stage sits in slot c of 8.
    uint32_t seed = 0x2545F491u;
    for (int s = 0; s < STAGES; ++s) {
        float slot = diffuser_range_ms[s] * fs / 1000.0f / (float)CH;
        for (int c = 0; c < CH; ++c) {
            seed = seed * 1664525u + 1013904223u;
            float jitter = 0.15f + 0.7f * (float)(seed >> 8) / 16777216.0f;
            int32_t n = (int32_t)(slot * ((float)c + jitter)) + 1;
            reverb->diffuser_samples[s][c] = n;
            reverb->diffuser_sign[s][c] = (diffuser_flips[s] >> c) & 1 ? -1.0f : 1.0f;
            delay_init(&reverb->diffuser[s][c], n);
        }
    }

    reverb->mod_depth = MOD_DEPTH_SAMPLES;
    for (int c = 0; c < CH; ++c) {
        reverb->late_samples[c] = (float)late_samples[c];
        delay_init(&reverb->late[c], late_samples[c] + (int32_t)MOD_DEPTH_SAMPLES + 2);
        reverb->damp_state[c] = 0.0f;
    }
    for (int k = 0; k < BM_HALL_REVERB_LFOS; ++k) {
        float w = TWO_PI * lfo_hz[k] / fs;
        reverb->lfo_step_cos[k] = cosf(w);
        reverb->lfo_step_sin[k] = sinf(w);
        float phase = (float)k * 1.3f;
        reverb->lfo_cos[k] = cosf(phase);
        reverb->lfo_sin[k] = sinf(phase);
    }

    reverb->hp_coeff = expf(-TWO_PI * HP_HZ / fs);
    reverb->hp_state = 0.0f;
    reverb->hp_last_in = 0.0f;
    reverb->lp_coeff = 1.0f - expf(-TWO_PI * LP_HZ / fs);
    reverb->lp_state = 0.0f;
    reverb->early_level = EARLY_LEVEL;

    bm_hall_reverb_set_rt60(reverb, 3.0f);
    reverb->glide_samples = 1;  // the next sample snaps to the targets
}

void bm_hall_reverb_destroy(bm_hall_reverb_t* reverb) {
    delay_destroy(&reverb->predelay);
    for (int s = 0; s < STAGES; ++s) {
        for (int c = 0; c < CH; ++c) delay_destroy(&reverb->diffuser[s][c]);
    }
    for (int c = 0; c < CH; ++c) delay_destroy(&reverb->late[c]);
}

void bm_hall_reverb_set_rt60(bm_hall_reverb_t* reverb, float rt60) {
    if (rt60 < BM_HALL_REVERB_RT60_MIN) rt60 = BM_HALL_REVERB_RT60_MIN;
    if (rt60 > BM_HALL_REVERB_RT60_MAX) rt60 = BM_HALL_REVERB_RT60_MAX;
    reverb->rt60 = rt60;

    // Jot: a line of d samples loses 60 dB in rt60 seconds at DC and in
    // rt60 x HF_RT60_RATIO at Nyquist.
    const float fs = (float)bm_SAMPLE_RATE;
    for (int c = 0; c < CH; ++c) {
        float d = reverb->late_samples[c];
        float g_dc = powf(10.0f, -3.0f * d / (fs * rt60));
        float g_ny = powf(10.0f, -3.0f * d / (fs * rt60 * HF_RT60_RATIO));
        float r = g_ny / g_dc;
        reverb->gain_target[c] = g_dc;
        reverb->pole_target[c] = (1.0f - r) / (1.0f + r);
    }
    // The tail energy grows with the decay time: keep long settings from
    // swamping the mix (-3 dB per doubling above ~1 s).
    reverb->late_level_target = 0.5f / sqrtf(1.0f + rt60);
    reverb->glide_samples = GLIDE_SAMPLES;
}

// Gains, poles and the output level move to their targets over GLIDE_SAMPLES
// (no zipper steps on a CC sweep) and are then left alone.
static void glide(bm_hall_reverb_t* reverb) {
    if (--reverb->glide_samples == 0) {
        for (int c = 0; c < CH; ++c) {
            reverb->gain[c] = reverb->gain_target[c];
            reverb->pole[c] = reverb->pole_target[c];
        }
        reverb->late_level = reverb->late_level_target;
        return;
    }
    for (int c = 0; c < CH; ++c) {
        reverb->gain[c] += (reverb->gain_target[c] - reverb->gain[c]) * GLIDE;
        reverb->pole[c] += (reverb->pole_target[c] - reverb->pole[c]) * GLIDE;
    }
    reverb->late_level += (reverb->late_level_target - reverb->late_level) * GLIDE;
}

float bm_hall_reverb_process(bm_hall_reverb_t* reverb, float input) {
    // Tone: one-pole high pass, one-pole low pass.
    float hp = reverb->hp_coeff * (reverb->hp_state + input - reverb->hp_last_in);
    reverb->hp_last_in = input;
    reverb->hp_state = hp;
    reverb->lp_state += (hp - reverb->lp_state) * reverb->lp_coeff;

    float pre = delay_swap(&reverb->predelay, reverb->lp_state + 1e-20f);  // + no denormals

    if (reverb->glide_samples > 0) glide(reverb);

    float x[CH];
    pre *= HADAMARD_INPUT_GAIN;
    for (int c = 0; c < CH; ++c) x[c] = pre;

    // The early tap sums the last stage before its Hadamard: a sum after it
    // would be a Hadamard row, i.e. one channel only (the diffusion would end
    // ~30 ms early, leaving a hole before the tail).
    float early = 0.0f;
    for (int s = 0; s < STAGES; ++s) {
        for (int c = 0; c < CH; ++c) {
            x[c] = delay_swap(&reverb->diffuser[s][c], x[c]) * reverb->diffuser_sign[s][c];
        }
        if (s == STAGES - 1) {
            for (int c = 0; c < CH; ++c) early += x[c];
        }
        hadamard8(x);
    }

    // LFOs: rotate, then pull the radius back to 1.
    for (int k = 0; k < BM_HALL_REVERB_LFOS; ++k) {
        float co = reverb->lfo_cos[k], si = reverb->lfo_sin[k];
        float nc = co * reverb->lfo_step_cos[k] - si * reverb->lfo_step_sin[k];
        float ns = si * reverb->lfo_step_cos[k] + co * reverb->lfo_step_sin[k];
        float fix = 1.5f - 0.5f * (nc * nc + ns * ns);
        reverb->lfo_cos[k] = nc * fix;
        reverb->lfo_sin[k] = ns * fix;
    }

    float y[CH];
    float late = 0.0f, sum = 0.0f;
    for (int c = 0; c < CH; ++c) {
        float lfo = (c & 1) ? reverb->lfo_sin[c >> 1] : reverb->lfo_cos[c >> 1];
        float tap = delay_read_frac(&reverb->late[c], reverb->late_samples[c] + reverb->mod_depth * lfo);

        float p = reverb->pole[c];
        float damped = reverb->gain[c] * (1.0f - p) * tap + p * reverb->damp_state[c];
        reverb->damp_state[c] = damped;

        y[c] = damped;
        sum += damped;
        late += late_out_sign[c] * damped;
    }

    // Householder feedback (I - 2/N 11^T), plus the diffused input.
    float fold = sum * (2.0f / (float)CH);
    for (int c = 0; c < CH; ++c) {
        delay_write(&reverb->late[c], y[c] - fold + x[c]);
    }

    float out = late * reverb->late_level + early * reverb->early_level;

    // Soft limit above 0.7 towards 1.0 (only very loud input at long decays
    // gets there): the fully wet output never hard-clips in bm_audio_denorm.
    float mag = fabsf(out);
    if (mag > SOFT_KNEE) {
        mag = SOFT_KNEE + (1.0f - SOFT_KNEE) * tanhf((mag - SOFT_KNEE) / (1.0f - SOFT_KNEE));
        out = out < 0.0f ? -mag : mag;
    }
    return out;
}
