#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define bm_SAMPLE_RATE 44100

// Small blocks for a short way through the module: the output lags the input
// by BM_AUDIO_DMA_DESC_NUM (+ up to 1) blocks of BM_AUDIO_FRAMES frames, plus
// the codec's own converter filters.
#define BM_AUDIO_FRAMES 16
#define BM_AUDIO_DMA_DESC_NUM 3

/**
 * @brief The main audio_loop callback, on core 1
 * @note  24-bit samples, left-justified in 32 bits, left and right interleaved:
 *          t1_left, t1_right, t2_left, t2_right
 *
 * @param[in]   n_frames        Number of stereo frames (BM_AUDIO_FRAMES)
 * @param[in]   input           Input samples (IN L, IN R)
 * @param[out]  output          Output samples (OUT L, OUT R)
 */
typedef void (*bm_audio_loop_t)(size_t n_frames, const int32_t *input, int32_t *output);

typedef struct {
    bm_audio_loop_t audio_loop;
} bm_audio_config_t;

void bm_setup_audio(bm_audio_config_t config);

#ifdef __cplusplus
}
#endif
