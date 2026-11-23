// Runs the master chain over one second of a hot kick + mix in 16-frame blocks
// and prints the time per sample. Under QEMU with `-icount shift=0` one
// instruction takes 1 ns of virtual time, so ns per sample = instructions per
// sample (the first line checks that against a loop of known length).
//
// Built with MS_BENCH_AUDIO (audio.sh) it runs a loop of audio through the chain
// instead and prints the output samples, to compare with the host render.
#include <math.h>
#include <stdint.h>
#include <stdio.h>

#include "esp_timer.h"
#include "ms_dsp.h"
#include "ms_params.h"

#ifdef MS_BENCH_AUDIO
// audio.sh: the loop and the settings to run it through, written by audio.py.
#include "audio_in.h"
#endif

#define FS 44100
#define BLOCK 16
#define LOOP 11024  // 0.25 s, a whole number of blocks

static float kick[LOOP], mix[LOOP];
static ms_dsp_t dsp;
static float values[MS_P_COUNT];

static void fill(void) {
    uint32_t r = 1;
    for (int i = 0; i < LOOP; i++) {
        float t = (float)i / FS;
        r = r * 1664525u + 1013904223u;
        float noise = (float)(int32_t)r / 2147483648.0f;
        kick[i] = 0.9f * sinf(6.2832f * (50.0f * t + 3.0f * (1.0f - expf(-t / 0.03f)))) * expf(-t / 0.1f) +
                  (i < 80 ? 0.3f * noise : 0.0f);
        mix[i] = 0.35f * sinf(6.2832f * 110.0f * t) + 0.3f * noise;
    }
}

static void measure(const char *name) {
    ms_coefs_t c;
    ms_coefs_from_params(values, FS, BLOCK, &c);
    ms_dsp_init(&dsp, &c);
    float out[BLOCK];
    for (int i = 0; i < LOOP; i += BLOCK) ms_dsp_process(&dsp, kick + i, mix + i, out, BLOCK);  // warm up
    int64_t worst = 0, start = esp_timer_get_time();
    for (int pass = 0; pass < 4; pass++) {
        for (int i = 0; i < LOOP; i += BLOCK) {
            int64_t t0 = esp_timer_get_time();
            ms_dsp_process(&dsp, kick + i, mix + i, out, BLOCK);
            int64_t used = esp_timer_get_time() - t0;
            if (used > worst) worst = used;
        }
    }
    int64_t total = esp_timer_get_time() - start;
    ms_meters_t m;
    ms_dsp_take_meters(&dsp, &m);
    printf("BENCH %s: %.0f ns per sample, worst block %.0f ns per sample (reduction: klim %.1f, bands %.1f %.1f %.1f, "
           "par %.1f, glue %.1f, lim %.1f dB)\n",
           name, 1000.0 * (double)total / (4.0 * LOOP), 1000.0 * (double)worst / BLOCK, (double)m.gr_klim,
           (double)m.gr_mb[0], (double)m.gr_mb[1], (double)m.gr_mb[2], (double)m.gr_par, (double)m.gr_glue,
           (double)m.gr_lim);
}

#ifdef MS_BENCH_AUDIO
// Runs the loop through the chain as the firmware does (16-frame blocks) and
// prints every output sample as the 24-bit word the codec would get.
static void audio(const char *name, const char *settings) {
    ms_coefs_t c;
    ms_params_defaults(values);
    ms_params_import(values, settings);
    ms_coefs_from_params(values, FS, BLOCK, &c);
    ms_dsp_init(&dsp, &c);
    int64_t worst = 0, total = 0;
    for (int i = 0; i + BLOCK <= AUDIO_N; i += BLOCK) {
        float k[BLOCK], m[BLOCK], out[BLOCK];
        for (int j = 0; j < BLOCK; j++) {
            k[j] = (float)audio_kick[i + j] / 32768.0f;
            m[j] = (float)audio_mix[i + j] / 32768.0f;
        }
        int64_t t0 = esp_timer_get_time();
        ms_dsp_process(&dsp, k, m, out, BLOCK);
        int64_t used = esp_timer_get_time() - t0;
        total += used;
        if (used > worst) worst = used;
        char line[6 * BLOCK + 1];
        for (int j = 0; j < BLOCK; j++) {
            float s = out[j] > 1.0f ? 1.0f : (out[j] < -1.0f ? -1.0f : out[j]);
            snprintf(line + 6 * j, 7, "%06x", (unsigned)(lrintf(s * 8388607.0f) & 0xFFFFFF));
        }
        printf("AUD %s %s\n", name, line);
    }
    ms_meters_t m;
    ms_dsp_take_meters(&dsp, &m);
    printf("BENCH loop, %s: %.0f ns per sample, worst block %.0f ns per sample (reduction: klim %.1f, bands %.1f %.1f "
           "%.1f, par %.1f, glue %.1f, lim %.1f dB)\n",
           name, 1000.0 * (double)total / (double)(AUDIO_N / BLOCK * BLOCK), 1000.0 * (double)worst / BLOCK,
           (double)m.gr_klim, (double)m.gr_mb[0], (double)m.gr_mb[1], (double)m.gr_mb[2], (double)m.gr_par,
           (double)m.gr_glue, (double)m.gr_lim);
}
#endif

void app_main(void) {
    // Calibration: see run.sh, which reads this loop's length from the disassembly.
    volatile uint32_t sink = 0;
    int64_t t0 = esp_timer_get_time();
    for (uint32_t i = 0; i < 1000000; i++) sink = i;
    int64_t t1 = esp_timer_get_time();
    printf("BENCH calibration: %.2f ns per loop pass\n", 1000.0 * (double)(t1 - t0) / 1e6);

#ifdef MS_BENCH_AUDIO
    for (int i = 0; i < AUDIO_SETS; i++) audio(audio_sets[i][0], audio_sets[i][1]);
    printf("BENCH done\n");
    return;
#endif

    fill();
    ms_params_defaults(values);
    measure("factory settings");

    // Everything on at its costliest: 48 dB/oct low and high cuts, RMS detectors,
    // glue sidechain filter + soft clip, longest look-aheads, limiters driven hard
    // with auto release.
    values[MS_P_K_FLT_LC_SLOPE] = 2;
    values[MS_P_K_FLT_HC_ON] = 1;
    values[MS_P_K_FLT_HC_SLOPE] = 2;
    values[MS_P_M_FLT_LC_SLOPE] = 2;
    values[MS_P_M_FLT_HC_ON] = 1;
    values[MS_P_M_FLT_HC_SLOPE] = 2;
    values[MS_P_K_LIM_AUTO] = 1;
    values[MS_P_MB_MODE] = 1;
    values[MS_P_MB_HI_RATIO] = 4;
    values[MS_P_GLUE_SC_HP] = 100;
    values[MS_P_GLUE_CLIP] = 1;
    values[MS_P_O_FLT_LC_SLOPE] = 2;
    values[MS_P_O_FLT_HC_ON] = 1;
    values[MS_P_O_FLT_HC_SLOPE] = 2;
    values[MS_P_K_LIM_GAIN] = 12;
    values[MS_P_K_LIM_LA] = 5;
    values[MS_P_LIM_GAIN] = 12;
    values[MS_P_LIM_LA] = 5;
    measure("everything on");

    ms_params_defaults(values);
    values[MS_P_BYPASS] = 1;
    measure("bypass");
    printf("BENCH done\n");
}
