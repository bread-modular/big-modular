#include "ms_proto.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef FIRMWARE_VERSION
#define FIRMWARE_VERSION "host"
#endif

// Levels in dB (full scale = 0), gain reductions in dB, cpu in %, latency in ms.
const char ms_meter_names[] =
    "raw_k raw_m in_k in_m kick mix par out gr_klim gr_lo gr_mid gr_hi gr_par gr_glue gr_lim "
    "cpu cpu_max lat_ms unsaved";

static const char *const kind_names[] = {"lin", "log", "bool", "enum"};

static char settings_text[MS_SETTINGS_TEXT_MAX];

static void out(ms_proto_t *pr, const char *line) {
    pr->host.out(pr->host.ctx, line);
}

static void out_param(ms_proto_t *pr, int index) {
    char line[80];
    snprintf(line, sizeof(line), "p|%s|%.6g", ms_param_defs[index].id, (double)pr->values[index]);
    out(pr, line);
}

static void out_all(ms_proto_t *pr, const char *done) {
    for (int i = 0; i < MS_P_COUNT; i++) out_param(pr, i);
    out(pr, done);
}

static void apply(ms_proto_t *pr) {
    pr->host.apply(pr->host.ctx, pr->values);
}

// Stored settings over the defaults; false if nothing is stored.
static bool load_stored(ms_proto_t *pr) {
    ms_params_defaults(pr->values);
    if (!pr->host.load || !pr->host.load(pr->host.ctx, settings_text, sizeof(settings_text))) return false;
    ms_params_import(pr->values, settings_text);
    return true;
}

void ms_proto_init(ms_proto_t *pr, const ms_host_t *host) {
    pr->host = *host;
    load_stored(pr);
    pr->unsaved = false;
    apply(pr);
}

static float peak_db(float lin) {
    return lin > 1e-6f ? 20.0f * log10f(lin) : -120.0f;
}

static void cmd_meters(ms_proto_t *pr) {
    ms_meters_t m;
    ms_status_t st = {0};
    pr->host.meters(pr->host.ctx, &m);
    pr->host.status(pr->host.ctx, &st);
    ms_coefs_t c;
    ms_coefs_from_params(pr->values, st.fs, st.block, &c);
    float lat_ms = st.io_ms + 1000.0f * (float)ms_coefs_latency(&c) / st.fs;
    char line[256];
    snprintf(line, sizeof(line),
             "m|%.1f %.1f %.1f %.1f %.1f %.1f %.1f %.1f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.0f %.0f %.2f %d",
             (double)peak_db(m.raw_k), (double)peak_db(m.raw_m), (double)peak_db(m.in_k), (double)peak_db(m.in_m),
             (double)peak_db(m.kick), (double)peak_db(m.mix), (double)peak_db(m.par), (double)peak_db(m.out),
             (double)m.gr_klim, (double)m.gr_mb[0], (double)m.gr_mb[1], (double)m.gr_mb[2], (double)m.gr_par,
             (double)m.gr_glue, (double)m.gr_lim, (double)st.cpu, (double)st.cpu_max, (double)lat_ms,
             pr->unsaved ? 1 : 0);
    out(pr, line);
}

static void cmd_desc(ms_proto_t *pr) {
    char line[224];
    for (int i = 0; i < ms_group_count; i++) {
        snprintf(line, sizeof(line), "g|%s|%s", ms_group_defs[i].id, ms_group_defs[i].title);
        out(pr, line);
    }
    for (int i = 0; i < MS_P_COUNT; i++) {
        const ms_param_def_t *d = &ms_param_defs[i];
        snprintf(line, sizeof(line), "d|%s|%s|%s|%.6g|%.6g|%.6g|%.6g|%s|%d|%s|%s", d->id, d->group,
                 kind_names[d->kind], (double)d->min, (double)d->max, (double)d->def, (double)d->step, d->unit,
                 d->not_saved ? 0 : 1, d->label, d->options);
        out(pr, line);
    }
    snprintf(line, sizeof(line), "n|%s", ms_meter_names);
    out(pr, line);
    out(pr, "ok|desc");
}

static void cmd_set(ms_proto_t *pr, char *args) {
    char *id = strtok(args, " \t");
    char *text = strtok(NULL, " \t");
    int index = id ? ms_param_find(id) : -1;
    if (index < 0 || !text) {
        out(pr, "err|set: unknown parameter or no value");
        return;
    }
    char *end;
    float v = strtof(text, &end);
    if (end == text) {
        out(pr, "err|set: not a number");
        return;
    }
    v = ms_param_clamp(index, v);
    if (v != pr->values[index]) {
        pr->values[index] = v;
        if (!ms_param_defs[index].not_saved) pr->unsaved = true;
        apply(pr);
    }
    out_param(pr, index);
}

void ms_proto_line(ms_proto_t *pr, char *line) {
    while (*line == ' ' || *line == '\t') line++;
    size_t len = strlen(line);
    while (len && (line[len - 1] == '\r' || line[len - 1] == ' ' || line[len - 1] == '\t')) line[--len] = 0;
    if (!len) return;

    if (strcmp(line, "m") == 0) {
        cmd_meters(pr);
    } else if (strncmp(line, "set ", 4) == 0) {
        cmd_set(pr, line + 4);
    } else if (strcmp(line, "hello") == 0) {
        ms_status_t st = {0};
        pr->host.status(pr->host.ctx, &st);
        char text[128];
        snprintf(text, sizeof(text), "hello|master|%s|proto=%d|fs=%.0f|block=%d|io_ms=%.2f", FIRMWARE_VERSION,
                 MS_PROTO_VERSION, (double)st.fs, st.block, (double)st.io_ms);
        out(pr, text);
    } else if (strcmp(line, "desc") == 0) {
        cmd_desc(pr);
    } else if (strcmp(line, "get") == 0) {
        out_all(pr, "ok|get");
    } else if (strcmp(line, "save") == 0) {
        size_t n = ms_params_export(pr->values, settings_text, sizeof(settings_text));
        if (n && pr->host.save && pr->host.save(pr->host.ctx, settings_text)) {
            pr->unsaved = false;
            out(pr, "ok|save");
        } else {
            out(pr, "err|save failed");
        }
    } else if (strcmp(line, "load") == 0) {
        // The setup aids (bypass, solo) stay as they are.
        float keep[MS_P_COUNT];
        memcpy(keep, pr->values, sizeof(keep));
        load_stored(pr);
        for (int i = 0; i < MS_P_COUNT; i++) {
            if (ms_param_defs[i].not_saved) pr->values[i] = keep[i];
        }
        pr->unsaved = false;
        apply(pr);
        out_all(pr, "ok|load");
    } else if (strcmp(line, "defaults") == 0) {
        ms_params_defaults(pr->values);
        pr->unsaved = true;
        apply(pr);
        out_all(pr, "ok|defaults");
    } else {
        out(pr, "err|unknown command");
    }
}
