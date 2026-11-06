// Host render for listening / analysis: runs a mono float32 file through the
// old BM classic reverb or the hall reverb at a given RT60.
//   render_reverb classic|hall <rt60 s> in.f32 out.f32
// Prints the time per sample (host CPU, for a relative cost only).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "audio/bm_classic_reverb.h"
#include "audio/bm_hall_reverb.h"

int main(int argc, char** argv) {
    if (argc != 5) {
        fprintf(stderr, "usage: %s classic|hall rt60 in.f32 out.f32\n", argv[0]);
        return 2;
    }
    int hall = strcmp(argv[1], "hall") == 0;
    float rt60 = (float)atof(argv[2]);
    FILE* f = fopen(argv[3], "rb");
    if (!f) return 1;
    fseek(f, 0, SEEK_END);
    long n = ftell(f) / (long)sizeof(float);
    fseek(f, 0, SEEK_SET);
    float* x = malloc(sizeof(float) * (size_t)n);
    if (fread(x, sizeof(float), (size_t)n, f) != (size_t)n) return 1;
    fclose(f);

    static bm_classic_reverb_t classic;
    static bm_hall_reverb_t hr;
    if (hall) {
        bm_hall_reverb_init(&hr);
        bm_hall_reverb_set_rt60(&hr, rt60);
        for (int i = 0; i < 20000; i++) bm_hall_reverb_process(&hr, 0.0f);  // settle the glides
    } else {
        bm_classic_reverb_init(&classic);
        bm_classic_reverb_set_rt60(&classic, rt60);
        for (int i = 0; i < 20000; i++) bm_classic_reverb_process(&classic, 0.0f);
    }
    clock_t t0 = clock();
    for (long i = 0; i < n; i++) {
        x[i] = hall ? bm_hall_reverb_process(&hr, x[i]) : bm_classic_reverb_process(&classic, x[i]);
    }
    double ns = (double)(clock() - t0) / CLOCKS_PER_SEC * 1e9 / (double)n;
    fprintf(stderr, "%s rt60 %.2f: %.1f ns/sample\n", argv[1], rt60, ns);
    f = fopen(argv[4], "wb");
    fwrite(x, sizeof(float), (size_t)n, f);
    fclose(f);
    if (hall) bm_hall_reverb_destroy(&hr); else bm_classic_reverb_destroy(&classic);
    free(x);
    return 0;
}
