// Host render of the master chain: runs the firmware DSP (../main/src/ms_dsp.c,
// ms_params.c) over two WAV files, to hear settings without the module.
//
//   ms_render [-s settings.txt] kick.wav mix.wav out.wav
//
// kick.wav / mix.wav: 16 / 24 / 32-bit PCM or 32-bit float, mono or stereo (stereo
// is summed to mono), the same sample rate. settings.txt: `set <id> <value>` lines,
// the page's export file; without it the factory settings. out.wav: 24-bit mono.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ms_dsp.h"
#include "ms_params.h"

#define BLOCK 16

typedef struct {
    float *x;
    long n;
    int fs;
} wav_t;

static uint32_t rd32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static int wav_read(const char *path, wav_t *w) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "%s: cannot open\n", path);
        return -1;
    }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *d = malloc((size_t)size);
    if (!d || fread(d, 1, (size_t)size, f) != (size_t)size) {
        fclose(f);
        free(d);
        fprintf(stderr, "%s: cannot read\n", path);
        return -1;
    }
    fclose(f);
    int fmt = 0, ch = 0, bits = 0;
    const uint8_t *data = NULL;
    uint32_t data_len = 0;
    if (size < 12 || memcmp(d, "RIFF", 4) || memcmp(d + 8, "WAVE", 4)) goto bad;
    for (long p = 12; p + 8 <= size;) {
        uint32_t len = rd32(d + p + 4);
        if (len > (uint32_t)(size - p - 8)) len = (uint32_t)(size - p - 8);
        if (!memcmp(d + p, "fmt ", 4) && len >= 16) {
            fmt = d[p + 8] | d[p + 9] << 8;
            ch = d[p + 10] | d[p + 11] << 8;
            w->fs = (int)rd32(d + p + 12);
            bits = d[p + 22] | d[p + 23] << 8;
            if (fmt == 0xFFFE && len >= 26) fmt = d[p + 32] | d[p + 33] << 8;  // extensible: sub-format
        } else if (!memcmp(d + p, "data", 4)) {
            data = d + p + 8;
            data_len = len;
        }
        p += 8 + len + (len & 1);
    }
    if (!data || ch < 1 || !((fmt == 1 && (bits == 16 || bits == 24 || bits == 32)) || (fmt == 3 && bits == 32)))
        goto bad;
    int bytes = bits / 8;
    w->n = (long)(data_len / (uint32_t)(bytes * ch));
    w->x = malloc(sizeof(float) * (size_t)(w->n + BLOCK));
    if (!w->x) goto bad;
    for (long i = 0; i < w->n; i++) {
        float sum = 0;
        for (int c = 0; c < ch; c++) {
            const uint8_t *s = data + (i * ch + c) * bytes;
            float v;
            if (fmt == 3) {
                memcpy(&v, s, 4);
            } else if (bits == 16) {
                v = (float)(int16_t)(s[0] | s[1] << 8) / 32768.0f;
            } else if (bits == 24) {
                v = (float)((int32_t)((uint32_t)s[0] << 8 | (uint32_t)s[1] << 16 | (uint32_t)s[2] << 24) >> 8) /
                    8388608.0f;
            } else {
                v = (float)(int32_t)rd32(s) / 2147483648.0f;
            }
            sum += v;
        }
        w->x[i] = sum / (float)ch;
    }
    free(d);
    return 0;
bad:
    free(d);
    fprintf(stderr, "%s: not a PCM 16 / 24 / 32-bit or float WAV file\n", path);
    return -1;
}

static int wav_write(const char *path, const float *x, long n, int fs) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "%s: cannot write\n", path);
        return -1;
    }
    uint32_t bytes = (uint32_t)n * 3;
    uint8_t h[44] = "RIFF....WAVEfmt ";
    uint32_t v[] = {36 + bytes, 16, (uint32_t)fs, (uint32_t)fs * 3, bytes};
    memcpy(h + 4, &v[0], 4);
    memcpy(h + 16, &v[1], 4);
    h[20] = 1, h[22] = 1;  // PCM, mono
    memcpy(h + 24, &v[2], 4);
    memcpy(h + 28, &v[3], 4);
    h[32] = 3, h[34] = 24;
    memcpy(h + 36, "data", 4);
    memcpy(h + 40, &v[4], 4);
    fwrite(h, 1, 44, f);
    for (long i = 0; i < n; i++) {
        float s = x[i] > 1.0f ? 1.0f : (x[i] < -1.0f ? -1.0f : x[i]);
        int32_t q = (int32_t)lrintf(s * 8388607.0f);
        uint8_t b[3] = {(uint8_t)q, (uint8_t)(q >> 8), (uint8_t)(q >> 16)};
        fwrite(b, 1, 3, f);
    }
    fclose(f);
    return 0;
}

static float db(float lin) {
    return lin > 1e-6f ? 20.0f * log10f(lin) : -120.0f;
}

int main(int argc, char **argv) {
    const char *settings = NULL;
    int a = 1;
    if (argc > 2 && strcmp(argv[1], "-s") == 0) {
        settings = argv[2];
        a = 3;
    }
    if (argc - a != 3) {
        fprintf(stderr, "usage: %s [-s settings.txt] kick.wav mix.wav out.wav\n", argv[0]);
        return 2;
    }
    static float values[MS_P_COUNT];
    ms_params_defaults(values);
    if (settings) {
        FILE *f = fopen(settings, "rb");
        static char text[16384];
        if (!f) {
            fprintf(stderr, "%s: cannot open\n", settings);
            return 1;
        }
        size_t len = fread(text, 1, sizeof(text) - 1, f);
        fclose(f);
        text[len] = 0;
        // The setup aids are not part of a settings file, but a render may want them.
        int set = ms_params_import(values, text);
        for (char *line = strtok(text, "\n"); line; line = strtok(NULL, "\n")) {
            char id[40];
            float v;
            if (sscanf(line, " set %39s %f", id, &v) != 2) continue;
            int index = ms_param_find(id);
            if (index >= 0 && ms_param_defs[index].not_saved) values[index] = ms_param_clamp(index, v);
        }
        printf("%s: %d settings\n", settings, set);
    }
    wav_t kick = {0}, mix = {0};
    if (wav_read(argv[a], &kick) || wav_read(argv[a + 1], &mix)) return 1;
    if (kick.fs != mix.fs) {
        fprintf(stderr, "sample rates differ: %d and %d Hz\n", kick.fs, mix.fs);
        return 1;
    }
    long n = kick.n > mix.n ? kick.n : mix.n;
    float *k = calloc((size_t)(n + BLOCK), sizeof(float)), *m = calloc((size_t)(n + BLOCK), sizeof(float));
    float *out = calloc((size_t)(n + BLOCK), sizeof(float));
    if (!k || !m || !out) return 1;
    memcpy(k, kick.x, sizeof(float) * (size_t)kick.n);
    memcpy(m, mix.x, sizeof(float) * (size_t)mix.n);

    static ms_dsp_t dsp;
    ms_coefs_t c;
    ms_coefs_from_params(values, (float)kick.fs, BLOCK, &c);
    ms_dsp_init(&dsp, &c);
    for (long i = 0; i < n; i += BLOCK) ms_dsp_process(&dsp, k + i, m + i, out + i, BLOCK);
    if (wav_write(argv[a + 2], out, n, kick.fs)) return 1;

    ms_meters_t mt;
    ms_dsp_take_meters(&dsp, &mt);
    printf("%ld frames at %d Hz, chain delay %.2f ms\n", n, kick.fs, 1000.0 * ms_coefs_latency(&c) / kick.fs);
    printf("peaks (dB): kick in %.1f, mix in %.1f, kick %.1f, mix %.1f, parallel %.1f, out %.1f\n",
           (double)db(mt.in_k), (double)db(mt.in_m), (double)db(mt.kick), (double)db(mt.mix), (double)db(mt.par),
           (double)db(mt.out));
    printf("most gain reduction (dB): kick limiter %.1f, bands %.1f / %.1f / %.1f, parallel %.1f, glue %.1f, "
           "limiter %.1f\n",
           (double)mt.gr_klim, (double)mt.gr_mb[0], (double)mt.gr_mb[1], (double)mt.gr_mb[2], (double)mt.gr_par,
           (double)mt.gr_glue, (double)mt.gr_lim);
    return 0;
}
