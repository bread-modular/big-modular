// ============================================================================
// Host self-tests for the shared CvRecorder (crash's recorder plus the
// whole-loop knob offset). Plain c++, no hardware: uses the Arduino shim in
// this folder (copied from the 8bit crash firmware). Run via ../sim.sh
//
// Covers: LIVE -> RECORDING (blink) -> PLAYBACK (solid) -> LIVE, the 4-bar
// take, knobs ignored for the first playback pass, then the knob offset
// shifting the whole recorded curve (clamped), and the offset reset.
// ============================================================================

#include <stdio.h>

#include "Arduino.h"

#include "../CvRecorder.h"

unsigned long g_millis = 0;
uint8_t g_pinModes[64] = {0};
uint8_t g_pinStates[64] = {0};
uint8_t g_buttonPressed = 0;
FakeSerial Serial;

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        ++g_checks;                                                     \
        if (!(cond)) {                                                  \
            ++g_failures;                                               \
            printf("  FAIL line %d: %s\n", __LINE__, #cond);            \
        }                                                               \
    } while (0)

static const uint8_t BTN_PIN = 4;    // PA4
static const uint8_t LED_PIN = 5;    // PA5

static uint16_t s_last1 = 0, s_last2 = 0;
static int s_applyCount = 0;

static void applyCapture(uint16_t cv1, uint16_t cv2) {
    s_last1 = cv1;
    s_last2 = cv2;
    ++s_applyCount;
}

static bool ledOn() { return g_pinStates[LED_PIN] == HIGH; }

static void click(CvRecorder& rec) {
    g_buttonPressed = 1;
    advanceMs(1);  rec.update();
    advanceMs(40); rec.update();
    g_buttonPressed = 0;
    advanceMs(1);  rec.update();
    advanceMs(40); rec.update();
}

static void feedTicks(CvRecorder& rec, int n, uint16_t cv1, uint16_t cv2) {
    for (int i = 0; i < n; ++i) rec.onClock(cv1, cv2, applyCapture);
}

// Record a flat take of (v1, v2), ending with the knobs at (v1, v2).
static void recordFlat(CvRecorder& rec, uint16_t v1, uint16_t v2) {
    click(rec);
    feedTicks(rec, REC_LOOP_TICKS, v1, v2);
}

static void test_lifecycle_and_led() {
    printf("[1] LIVE -> RECORDING (blink) -> PLAYBACK (solid) -> LIVE\n");
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
    CHECK(!ledOn());

    click(rec);
    CHECK(rec.isRecording());
    bool sawOn = false, sawOff = false;
    for (int i = 0; i < 20; ++i) {
        advanceMs(50); rec.update();
        if (ledOn()) sawOn = true; else sawOff = true;
    }
    CHECK(sawOn && sawOff);

    feedTicks(rec, REC_LOOP_TICKS - 1, 400, 800);
    CHECK(rec.isRecording());
    feedTicks(rec, 1, 400, 800);
    CHECK(rec.isPlayingBack());
    CHECK(ledOn());
    for (int i = 0; i < 20; ++i) { advanceMs(50); rec.update(); CHECK(ledOn()); }

    click(rec);
    CHECK(rec.getState() == CvRecorder::STATE_LIVE);
    CHECK(!ledOn());
}

static void test_guard_ignores_knobs() {
    printf("[2] first playback pass ignores the knobs\n");
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();
    recordFlat(rec, 400, 800);
    CHECK(!rec.isOffsetArmed());

    // Knobs wiggled hard during the guard pass: replay stays exact.
    int wrong = 0;
    s_applyCount = 0;
    for (int i = 0; i < (int)REC_LOOP_TICKS; ++i) {
        uint16_t k = (i & 1) ? 0 : 1023;
        rec.onClock(k, 1023 - k, applyCapture);
        if (s_last1 != 400 || s_last2 != 800) ++wrong;
    }
    CHECK(s_applyCount == (int)REC_LOOP_TICKS);
    CHECK(wrong == 0);
    CHECK(rec.isOffsetArmed());
}

static void test_offset_shifts_whole_loop() {
    printf("[3] after the guard, knob moves shift the whole loop\n");
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();

    // A ramp take, knobs end at (300, 600).
    click(rec);
    for (int k = 0; k < (int)REC_LOOP_TICKS; ++k) {
        uint16_t v1 = (uint16_t)(200 + k);     // 200..583
        uint16_t v2 = (uint16_t)(700 - k);     // 700..317
        rec.onClock(v1, v2, applyCapture);
    }
    CHECK(rec.isPlayingBack());

    // Guard pass with the knobs parked at (300, 600) -> reference.
    feedTicks(rec, REC_LOOP_TICKS, 300, 600);
    CHECK(rec.isOffsetArmed());

    // Knobs untouched: exact replay.
    feedTicks(rec, 1, 300, 600);
    CHECK(s_last1 == (200 >> 2 << 2));
    CHECK(s_last2 == (700 >> 2 << 2));

    // +100 on P1, -200 on P2: every frame moves by that amount.
    int wrong = 0;
    for (int k = 1; k < (int)REC_LOOP_TICKS; ++k) {
        rec.onClock(400, 400, applyCapture);
        int e1 = (((200 + k) >> 2) << 2) + 100;
        int e2 = (((700 - k) >> 2) << 2) - 200;
        if (s_last1 != e1 || s_last2 != e2) ++wrong;
    }
    CHECK(wrong == 0);

    // Big moves clamp to 0..1023 (last frame: 580 + 723, 316 - 600).
    feedTicks(rec, REC_LOOP_TICKS - 1, 300, 600);
    feedTicks(rec, 1, 1023, 0);
    CHECK(s_last1 == 1023);
    CHECK(s_last2 == 0);

    // Back to the reference: offset gone.
    feedTicks(rec, 1, 300, 600);
    CHECK(s_last1 == (200 >> 2 << 2));
    CHECK(s_last2 == (700 >> 2 << 2));
}

static void test_offset_reset() {
    printf("[4] LIVE and a new take clear the offset and restart the guard\n");
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();
    recordFlat(rec, 500, 500);
    feedTicks(rec, REC_LOOP_TICKS, 500, 500);
    CHECK(rec.isOffsetArmed());
    feedTicks(rec, 1, 600, 600);
    CHECK(s_last1 == 600);

    click(rec);                       // -> LIVE
    s_applyCount = 0;
    feedTicks(rec, 10, 900, 900);
    CHECK(s_applyCount == 0);

    recordFlat(rec, 200, 200);        // new take
    CHECK(rec.isPlayingBack());
    CHECK(!rec.isOffsetArmed());
    feedTicks(rec, 1, 1023, 1023);    // guard again: knobs ignored
    CHECK(s_last1 == 200 && s_last2 == 200);
}

static void test_start_rewinds_keeps_offset() {
    printf("[5] MIDI Start rewinds the loop, offset kept\n");
    CvRecorder rec(BTN_PIN, LED_PIN);
    rec.begin();
    click(rec);
    for (int k = 0; k < (int)REC_LOOP_TICKS; ++k) rec.onClock(k < 10 ? 100 : 500, 0, applyCapture);
    feedTicks(rec, REC_LOOP_TICKS, 500, 0);
    feedTicks(rec, 20, 550, 0);
    rec.onStart();
    CHECK(rec.getTick() == 0);
    feedTicks(rec, 1, 550, 0);
    CHECK(s_last1 == 150);
}

int main() {
    test_lifecycle_and_led();
    test_guard_ignores_knobs();
    test_offset_shifts_whole_loop();
    test_offset_reset();
    test_start_rewinds_keeps_offset();
    printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}
