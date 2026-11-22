#pragma once

// Text protocol of the master firmware on the USB serial port (web/index.html
// talks it over Web Serial). One command per line, answers are lines too, fields
// split by '|'. Lines that start otherwise (ESP-IDF log) are not protocol.
//
//   hello            hello|master|<version>|proto=1|fs=<Hz>|block=<frames>|io_ms=<ms>
//   desc             g|<group>|<title>            one per group, in page order
//                    d|<id>|<group>|<kind>|<min>|<max>|<default>|<step>|<unit>|<saved 0/1>|<label>|<options>
//                    n|<meter names, space separated>
//                    ok|desc
//   get              p|<id>|<value> for every parameter, then ok|get
//   set <id> <value> p|<id>|<value>  (the value after clamping)  or  err|<text>
//   m                m|<meter values, space separated, in the `n` order>
//   save             ok|save  or  err|...     settings to flash
//   load             as get, then ok|load     back to the saved settings
//   defaults         as get, then ok|defaults factory settings (not saved yet)

#include <stdbool.h>
#include <stddef.h>

#include "ms_params.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MS_PROTO_VERSION 1
#define MS_SETTINGS_TEXT_MAX 4096

typedef struct {
    float fs;
    int block;          // frames per audio block
    float io_ms;        // converter + buffer delay without the look-aheads (estimate)
    float cpu, cpu_max; // audio block time in % of its period: mean and worst since the last call
} ms_status_t;

// Everything the protocol needs from the firmware around it.
typedef struct {
    void *ctx;
    void (*out)(void *ctx, const char *line);                // one answer line, no line end
    bool (*save)(void *ctx, const char *text);               // store the settings text
    bool (*load)(void *ctx, char *text, size_t cap);         // false = nothing stored
    void (*apply)(void *ctx, const float values[MS_P_COUNT]); // parameters changed
    void (*meters)(void *ctx, ms_meters_t *m);               // largest values since the last call
    void (*status)(void *ctx, ms_status_t *st);
} ms_host_t;

typedef struct {
    ms_host_t host;
    float values[MS_P_COUNT];
    bool unsaved;
} ms_proto_t;

// Factory settings, then the stored ones on top, then host.apply.
void ms_proto_init(ms_proto_t *pr, const ms_host_t *host);
// One received line (no line end). The text may be modified.
void ms_proto_line(ms_proto_t *pr, char *line);

extern const char ms_meter_names[];

#ifdef __cplusplus
}
#endif
