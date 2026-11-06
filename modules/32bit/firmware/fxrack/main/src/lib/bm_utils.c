#include <math.h>
#include "lib/bm_utils.h"
#include "esp_heap_caps.h"

int16_t bm_audio_clamp(int32_t value) {
    value = value >  INT16_MAX? INT16_MAX : value;
    value = value < INT16_MIN? INT16_MIN : value;

    return value;
}

float bm_audio_norm(int16_t value) {
    return (float)value / 32768.0f;
}

int16_t bm_audio_denorm(float value) {
    float scaled = value * 32768.0f;
    int32_t temp = lrintf(scaled);                // round to nearest
    if (temp > INT16_MAX) temp = INT16_MAX;
    if (temp < INT16_MIN) temp = INT16_MIN;
    return (int16_t)temp;
}

void* allocate_psram(size_t size) {
    return heap_caps_calloc(1, size, MALLOC_CAP_SPIRAM);
}

// Internal SRAM first (no PSRAM cache misses in the reverb's many delay taps),
// PSRAM once less than 64 KB would be left for the drivers and tasks started
// after the app's init. free_psram() frees either.
#define FAST_RESERVE_BYTES (64 * 1024)
void* allocate_fast(size_t size) {
    void* ptr = NULL;
    if (heap_caps_get_free_size(MALLOC_CAP_INTERNAL) > size + FAST_RESERVE_BYTES) {
        ptr = heap_caps_calloc(1, size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    }
    return ptr != NULL ? ptr : allocate_psram(size);
}

void free_psram(void *ptr) {
    heap_caps_free(ptr);
}

float bm_utils_map_range(float value, float in_min, float in_max, float out_min, float out_max) {
    float t = (value - in_min) / (in_max - in_min);
    return out_min + t * (out_max - out_min);
}
