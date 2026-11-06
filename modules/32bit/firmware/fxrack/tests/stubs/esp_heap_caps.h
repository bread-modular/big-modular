#pragma once

#include <stddef.h>

#define MALLOC_CAP_SPIRAM 0x0001
#define MALLOC_CAP_INTERNAL 0x0002
#define MALLOC_CAP_8BIT 0x0004

void *heap_caps_calloc(size_t n, size_t size, int caps);
void heap_caps_free(void *ptr);
size_t heap_caps_get_free_size(int caps);
