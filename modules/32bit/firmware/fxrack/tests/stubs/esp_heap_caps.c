#include "esp_heap_caps.h"

#include <stdlib.h>

void *heap_caps_calloc(size_t n, size_t size, int caps) {
    (void)caps;
    return calloc(n, size);
}

void heap_caps_free(void *ptr) {
    free(ptr);
}

size_t heap_caps_get_free_size(int caps) {
    (void)caps;
    return 256 * 1024;
}
