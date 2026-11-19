// memcpy / memset by words. The ones in newlib-nano go byte by byte (about 8
// CPU cycles a byte here), and the audio path copies every sample three times
// between the USB endpoint buffers, the FIFOs and I2S: at 192 kHz that was a
// third of the CPU and most of the time an iso endpoint waited to be served.
#include <stddef.h>
#include <stdint.h>

typedef uint32_t __attribute__((may_alias)) word_t;

// No loop-to-libcall conversion: these loops are the library calls.
#define MEM_FN __attribute__((optimize("O2", "no-tree-loop-distribute-patterns")))

MEM_FN void *memcpy(void *restrict dst, const void *restrict src, size_t n) {
  uint8_t *d = dst;
  const uint8_t *s = src;
  if (n >= 8 && (((uintptr_t) d ^ (uintptr_t) s) & 3u) == 0) {
    while ((uintptr_t) d & 3u) {
      *d++ = *s++;
      n--;
    }
    word_t *dw = (word_t *) d;
    const word_t *sw = (const word_t *) s;
    for (; n >= 16; n -= 16) {
      uint32_t const a = sw[0], b = sw[1], c = sw[2], e = sw[3];
      dw[0] = a;
      dw[1] = b;
      dw[2] = c;
      dw[3] = e;
      dw += 4;
      sw += 4;
    }
    for (; n >= 4; n -= 4) *dw++ = *sw++;
    d = (uint8_t *) dw;
    s = (const uint8_t *) sw;
  }
  while (n--) *d++ = *s++;
  return dst;
}

MEM_FN void *memset(void *dst, int value, size_t n) {
  uint8_t *d = dst;
  if (n >= 8) {
    while ((uintptr_t) d & 3u) {
      *d++ = (uint8_t) value;
      n--;
    }
    word_t *dw = (word_t *) d;
    uint32_t const w = (uint8_t) value * 0x01010101u;
    for (; n >= 16; n -= 16) {
      dw[0] = w;
      dw[1] = w;
      dw[2] = w;
      dw[3] = w;
      dw += 4;
    }
    for (; n >= 4; n -= 4) *dw++ = w;
    d = (uint8_t *) dw;
  }
  while (n--) *d++ = (uint8_t) value;
  return dst;
}
