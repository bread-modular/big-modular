#pragma once

// bm_motion_recorder: MIDI-clock-synced, RAM-only 4-bar recorder for CV1/CV2
// and the four fxrack MIDI CCs (MCC bank A, CC 20..23). Same behaviour as the
// 8bit CvRecorder (opt/attiny1616-tools/lib/CvRecorder) and the 16bit
// MotionRecorder:
//
//   LIVE --press--> RECORDING --(384 clocks = 4 bars of 4/4)--> PLAYBACK
//     ^                                                            |
//     +------- click in PLAYBACK / press (aborts) in RECORDING ----+
//
//   * RECORDING: every MIDI clock stores the live CV1/CV2 and CC values; the
//     live controls keep driving the sound.
//   * PLAYBACK: every MIDI clock replays the frame at the playhead. For the
//     first 4-bar pass the live controls are ignored; at the end of that pass
//     they are latched as the reference, then moving one shifts its whole
//     recorded curve by (live - reference), clamped.
//   * OVERDUB (as the 16bit MotionRecorder): hold MODE in PLAYBACK and move a
//     CV or MCC control. From its first move (CV more than
//     BM_REC_OVERDUB_CV_THRESHOLD, a CC any change from its value at the
//     press) until MODE is released, that value replaces the recording at the
//     playhead; the others keep playing. Releasing MODE keeps the loop with
//     the new curve, no offset until the control moves again. A CC that
//     wasn't in the take joins it, keeping its pre-hold value outside the
//     overdubbed span. A click (press and release, nothing moved) returns to
//     LIVE on the release.
//   * A CC that never arrived before or during the take is not recorded and
//     stays live in PLAYBACK; one first moved part-way through is back-filled
//     with its first value.
//   * MIDI Start rewinds an active take or loop.
//
// No locking, no IO: the app serialises the calls and applies the frames.

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BM_REC_PPQN 24
#define BM_REC_BEATS_PER_BAR 4
#define BM_REC_BARS 4
#define BM_REC_LOOP_TICKS (BM_REC_PPQN * BM_REC_BEATS_PER_BAR * BM_REC_BARS)  // 384
#define BM_REC_GUARD_TICKS BM_REC_LOOP_TICKS  // live controls ignored for 1 pass
#define BM_REC_CV_COUNT 2
#define BM_REC_FIRST_CC 20                    // BM_MCC_BANK_A_CV1
#define BM_REC_CC_COUNT 4                     // CC 20..23
#define BM_REC_CC_UNSET 0xFF
#define BM_REC_CC_MAX 127
#define BM_REC_OVERDUB_CV_THRESHOLD 0.012f   // ~48 of 4095 ADC steps (noise)

typedef enum {
    BM_REC_LIVE = 0,
    BM_REC_RECORDING,
    BM_REC_PLAYBACK,
} bm_rec_state_t;

typedef struct {
    float cv[BM_REC_CV_COUNT];      // 0..1
    uint8_t cc[BM_REC_CC_COUNT];    // 0..127, BM_REC_CC_UNSET = not recorded
} bm_rec_frame_t;

typedef struct {
    bm_rec_state_t state;
    uint16_t tick;
    uint16_t guard_ticks;
    uint8_t recorded_ccs;           // bit i: cc[i] recorded in the take
    float live_cv[BM_REC_CV_COUNT];
    uint8_t live_cc[BM_REC_CC_COUNT];
    float cv_ref[BM_REC_CV_COUNT];  // live values latched after the guard pass
    uint8_t cc_ref[BM_REC_CC_COUNT];
    // Overdub hold (MODE held in PLAYBACK).
    bool holding;
    uint8_t overdub_cvs;            // bit i: cv[i] overdubbed
    uint8_t overdub_ccs;            // bit i: cc[i] overdubbed
    float hold_cv[BM_REC_CV_COUNT]; // live values at the press
    uint8_t hold_cc[BM_REC_CC_COUNT];
    bm_rec_frame_t frames[BM_REC_LOOP_TICKS];  // 4.6 KB
} bm_motion_recorder_t;

void bm_rec_init(bm_motion_recorder_t *rec);

// MODE press edge: LIVE -> RECORDING, RECORDING (abort) -> LIVE; in PLAYBACK
// it starts an overdub hold.
void bm_rec_press(bm_motion_recorder_t *rec);

// MODE release edge: ends an overdub hold; nothing moved -> LIVE.
void bm_rec_release(bm_motion_recorder_t *rec);

// MODE held in PLAYBACK and at least one value moved.
bool bm_rec_overdubbing(const bm_motion_recorder_t *rec);

// Latest live values. The CC setter returns false for CCs outside 20..23.
void bm_rec_set_live_cv(bm_motion_recorder_t *rec, uint8_t index, float value);
bool bm_rec_set_live_cc(bm_motion_recorder_t *rec, uint8_t cc, uint8_t value);

// True while PLAYBACK drives the value: the app must not apply it live.
bool bm_rec_owns_cv(const bm_motion_recorder_t *rec);
bool bm_rec_owns_cc(const bm_motion_recorder_t *rec, uint8_t cc);

// One MIDI timing clock. Returns true in PLAYBACK with the frame to apply in
// *out (an unrecorded CC is BM_REC_CC_UNSET: leave it live).
bool bm_rec_clock(bm_motion_recorder_t *rec, bm_rec_frame_t *out);

// MIDI Start: the next clock records or plays frame 0.
void bm_rec_start(bm_motion_recorder_t *rec);

#ifdef __cplusplus
}
#endif
