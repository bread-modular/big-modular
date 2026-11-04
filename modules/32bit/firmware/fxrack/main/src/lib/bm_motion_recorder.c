#include "lib/bm_motion_recorder.h"

#include <string.h>

static int cc_index(uint8_t cc) {
    if (cc >= BM_REC_FIRST_CC && cc < BM_REC_FIRST_CC + BM_REC_CC_COUNT) {
        return cc - BM_REC_FIRST_CC;
    }
    return -1;
}

static float clamp01(float v) {
    return v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v);
}

static uint8_t shifted_cc(uint8_t stored, int offset) {
    int v = (int)stored + offset;
    if (v < 0) return 0;
    if (v > BM_REC_CC_MAX) return BM_REC_CC_MAX;
    return (uint8_t)v;
}

void bm_rec_init(bm_motion_recorder_t *rec) {
    memset(rec, 0, sizeof(*rec));
    rec->state = BM_REC_LIVE;
    memset(rec->live_cc, BM_REC_CC_UNSET, sizeof(rec->live_cc));
}

void bm_rec_press(bm_motion_recorder_t *rec) {
    // An aborted take is never exposed as a loop.
    rec->state = rec->state == BM_REC_LIVE ? BM_REC_RECORDING : BM_REC_LIVE;
    rec->tick = 0;
}

void bm_rec_set_live_cv(bm_motion_recorder_t *rec, uint8_t index, float value) {
    if (index < BM_REC_CV_COUNT) {
        rec->live_cv[index] = clamp01(value);
    }
}

bool bm_rec_set_live_cc(bm_motion_recorder_t *rec, uint8_t cc, uint8_t value) {
    int i = cc_index(cc);
    if (i < 0) {
        return false;
    }
    rec->live_cc[i] = value & 0x7F;
    return true;
}

bool bm_rec_owns_cv(const bm_motion_recorder_t *rec) {
    return rec->state == BM_REC_PLAYBACK;
}

bool bm_rec_owns_cc(const bm_motion_recorder_t *rec, uint8_t cc) {
    int i = cc_index(cc);
    return rec->state == BM_REC_PLAYBACK && i >= 0 && (rec->recorded_ccs & (1u << i)) != 0;
}

// Take complete: back-fill CCs first moved part-way through, remember which
// CCs the loop owns, then loop with the guard pass.
static void finish_take(bm_motion_recorder_t *rec) {
    rec->recorded_ccs = 0;
    for (int i = 0; i < BM_REC_CC_COUNT; i++) {
        int first = 0;
        while (first < BM_REC_LOOP_TICKS && rec->frames[first].cc[i] == BM_REC_CC_UNSET) {
            first++;
        }
        if (first == BM_REC_LOOP_TICKS) {
            continue;  // never arrived: stays live
        }
        for (int t = 0; t < first; t++) {
            rec->frames[t].cc[i] = rec->frames[first].cc[i];
        }
        rec->recorded_ccs |= (uint8_t)(1u << i);
    }
    rec->state = BM_REC_PLAYBACK;
    rec->guard_ticks = 0;
}

static void advance(bm_motion_recorder_t *rec) {
    if (++rec->tick >= BM_REC_LOOP_TICKS) {
        rec->tick = 0;
    }
}

bool bm_rec_clock(bm_motion_recorder_t *rec, bm_rec_frame_t *out) {
    if (rec->state == BM_REC_RECORDING) {
        bm_rec_frame_t *frame = &rec->frames[rec->tick];
        memcpy(frame->cv, rec->live_cv, sizeof(frame->cv));
        memcpy(frame->cc, rec->live_cc, sizeof(frame->cc));
        advance(rec);
        if (rec->tick == 0) {
            finish_take(rec);
        }
        return false;
    }

    if (rec->state != BM_REC_PLAYBACK) {
        return false;  // LIVE: playhead idle
    }

    const bm_rec_frame_t *stored = &rec->frames[rec->tick];
    if (rec->guard_ticks < BM_REC_GUARD_TICKS) {
        // First pass: live controls ignored, latched as the reference (the
        // last guard tick wins).
        rec->guard_ticks++;
        memcpy(rec->cv_ref, rec->live_cv, sizeof(rec->cv_ref));
        memcpy(rec->cc_ref, rec->live_cc, sizeof(rec->cc_ref));
        *out = *stored;
    } else {
        for (int i = 0; i < BM_REC_CV_COUNT; i++) {
            out->cv[i] = clamp01(stored->cv[i] + rec->live_cv[i] - rec->cv_ref[i]);
        }
        for (int i = 0; i < BM_REC_CC_COUNT; i++) {
            // A recorded CC always has a live value (it arrived by the take's end).
            out->cc[i] = stored->cc[i] == BM_REC_CC_UNSET
                ? BM_REC_CC_UNSET
                : shifted_cc(stored->cc[i], (int)rec->live_cc[i] - (int)rec->cc_ref[i]);
        }
    }
    advance(rec);
    return true;
}

void bm_rec_start(bm_motion_recorder_t *rec) {
    if (rec->state != BM_REC_LIVE) {
        rec->tick = 0;
    }
}
