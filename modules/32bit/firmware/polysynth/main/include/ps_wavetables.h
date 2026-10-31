#pragma once

// Band-limited wavetables, generated at build time by tools/gen_wavetables.py
// (octave mipmaps: level l holds harmonics 1 .. 1024 >> l; each table has
// ps_wt_size[l] samples plus one guard sample).

#include <stdint.h>

#define PS_WT_COUNT 7
#define PS_WT_LEVELS 11
#define PS_WT_TOP_HARMONICS 1024

extern const char *const ps_wt_names[PS_WT_COUNT];
extern const uint16_t ps_wt_size[PS_WT_LEVELS];
extern const uint32_t ps_wt_offset[PS_WT_COUNT][PS_WT_LEVELS];
extern const int16_t ps_wt_data[];
