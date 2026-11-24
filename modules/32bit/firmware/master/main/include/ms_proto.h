#pragma once

// Text protocol of the master firmware on the USB serial port (web/index.html
// talks it over Web Serial). One command per line, answers are lines too, fields
// split by '|'. Lines that start otherwise (ESP-IDF log) are not protocol.
//
//   hello            hello|master|<version>|proto=3|fs=<Hz>|block=<frames>|io_ms=<ms>
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
//                    (load and defaults answer the mappings too, as ctl)
//
// The panel's own controls (ms_ctl.h), saved with the settings:
//   ctl              c|<src>|<id>|<a>|<b> per mapping, src = cv1 cv2 mode, then ok|ctl
//                    (mode_act = how the button works them: click, hold or push)
//   map <src> <id> <a> [<b>]   add or change a mapping; answers as ctl  or  err|map: <why>
//   unmap <src> <id> / unmap all   answers as ctl
//   fire [on|off]    MODE over / back (none: the other way round, a click): p|... lines, then ok|fire
// The settings the knobs and the button move come as p|<id>|<value> lines without
// a command (ms_proto_push), a few times a second at most.

#include <stdbool.h>
#include <stddef.h>

#include "ms_ctl.h"
#include "ms_params.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MS_PROTO_VERSION 3
#define MS_SETTINGS_TEXT_MAX 8192

typedef struct {
    float fs;
    int block;          // frames per audio block
    float io_ms;        // converter + buffer delay without the look-aheads (estimate)
    float cpu, cpu_max; // audio block time in % of its period: mean and worst since the last call
    float led;          // MODE LED brightness now, 0..1
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
    ms_ctl_t ctl;
} ms_proto_t;

// Factory settings, then the stored ones on top, then host.apply.
void ms_proto_init(ms_proto_t *pr, const ms_host_t *host);
// One received line (no line end). The text may be modified.
void ms_proto_line(ms_proto_t *pr, char *line);
// The knobs (0..1 each) and the MODE button (debounced inside) every few ms;
// applies what they change (host.apply).
void ms_proto_controls(ms_proto_t *pr, const float cv[2], bool pressed, uint32_t now_ms);
// p|<id>|<value> for every setting the controls changed since the last call.
void ms_proto_push(ms_proto_t *pr);

extern const char ms_meter_names[];

#ifdef __cplusplus
}
#endif
