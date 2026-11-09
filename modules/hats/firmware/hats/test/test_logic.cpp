// Host tests for src/hats_logic.h (no hardware): ../test.sh
#include <stdio.h>
#include <stdlib.h>
#include <initializer_list>
#include "hats_logic.h"

using namespace hats;

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

static void testNoise() {
    // BM curve: linear tone / 2 below half, 512 + 2^((tone - 512) / 30) above
    CHECK(noiseHoldTicks(0) == BASE_TICKS);
    CHECK(noiseHoldTicks(511) == BASE_TICKS + 255);
    CHECK(noiseHoldTicks(512) == BASE_TICKS + 513);
    CHECK(noiseHoldTicks(1023) == BASE_TICKS + 512 + (1UL << 17));
    CHECK(noiseHoldTicks(5000) == noiseHoldTicks(1023));
    for (uint16_t t = 1; t < 1024; t++) CHECK(noiseHoldTicks(t) >= noiseHoldTicks(t - 1));
    // CC 74 x 8 adds, clamped at 1023
    CHECK(noiseTone(100, 10) == 180);
    CHECK(noiseTone(1000, 127) == 1023);
    // BM LFSRs: first output of the seeds, recomputed by hand
    WhiteNoise n;
    uint16_t a = 0xACE1, b = 0xBEEF, c = 0xCAFE;
    for (int i = 0; i < 1000; i++) {
        uint8_t oa = WhiteNoise::step(a), ob = WhiteNoise::step(b), oc = WhiteNoise::step(c);
        CHECK(n.next() == (uint8_t)((oa ^ (ob >> 1)) ^ (oc >> 2)));
    }
    // swing: mix 0 = unchanged, 255 = nearly full swing
    CHECK(boostSwing(100, 0) == 100);
    CHECK(boostSwing(200, 255) >= 254);
    CHECK(boostSwing(20, 255) <= 1);
    CHECK(dac12(0) == 0 && dac12(255) == 4095 && dac12(128) == 0x808);
}

static void testCutoff() {
    CHECK(cutoffDuty(0) == PWM_FULL);
    for (uint16_t k = 1; k < 1024; k++) CHECK(cutoffDuty(k) <= cutoffDuty(k - 1));  // knob up = darker
    CHECK(cutoffDuty(1023) > 0 && cutoffDuty(1023) < 64);    // < 2 counts: needs the dither
    // Model check: LDR || 51k equals knob x 50k
    for (uint16_t k = 64; k < 1024; k += 64) {
        double d = (double)cutoffDuty(k) / PWM_FULL;
        double rLdr = LDR_R_ON / pow(d, LDR_GAMMA);
        double rPar = 1.0 / (1.0 / rLdr + 1.0 / CUT_R50);
        double want = CUT_POT_MAX * k / 1023.0;
        CHECK(fabs(rPar - want) / want < 0.01);
    }
    // Dither: the average over many periods equals the fractional duty
    for (uint32_t duty : {1u, 17u, 31u, 33u, 1000u, 40000u, 65535u}) {
        PwmDither dth;
        uint64_t sum = 0;
        const int N = 32 * 1000;
        for (int i = 0; i < N; i++) {
            uint16_t ccr = dth.next(duty);
            CHECK(ccr <= PWM_PERIOD);
            sum += ccr;
        }
        double avg = (double)sum / N * 32.0;
        CHECK(fabs(avg - duty) < 1.0);
    }
    PwmDither full;
    CHECK(full.next(PWM_FULL) == PWM_PERIOD);
}

static MidiParser::Event feedAll(MidiParser &p, std::initializer_list<uint8_t> bytes, int *count = nullptr) {
    MidiParser::Event last = {MidiParser::NONE, 0, 0};
    int n = 0;
    for (uint8_t b : bytes) {
        MidiParser::Event e = p.feed(b);
        if (e.kind != MidiParser::NONE) { last = e; n++; }
    }
    if (count) *count = n;
    return last;
}

static void testMidi() {
    MidiParser p;
    MidiParser::Event e = feedAll(p, {0x95, 61, 100});
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 61 && e.data2 == 100);
    int n = 0;
    e = feedAll(p, {62, 90, 63, 80}, &n);                       // running status
    CHECK(n == 2 && e.kind == MidiParser::NOTE_ON && e.data1 == 63 && e.data2 == 80);
    e = feedAll(p, {0x90, 60, 0xF8, 70}, &n);                   // clock inside a message
    CHECK(n == 2 && e.kind == MidiParser::NOTE_ON && e.data1 == 60 && e.data2 == 70);
    e = feedAll(p, {0xB3, 74, 127});
    CHECK(e.kind == MidiParser::CONTROL_CHANGE && e.data1 == 74 && e.data2 == 127);
    e = feedAll(p, {0xC0, 5, 0x80, 60, 0});                     // program change is 1 byte
    CHECK(e.kind == MidiParser::NOTE_OFF && e.data1 == 60);
    e = feedAll(p, {0xF0, 1, 2, 3, 0xF7, 10, 20}, &n);          // SysEx then stray data
    CHECK(n == 0);
    CHECK(feedAll(p, {0xFA}).kind == MidiParser::START);
    CHECK(feedAll(p, {0xF8}).kind == MidiParser::CLOCK);
}

static void testHihat() {
    HihatOut h;
    CHECK(h.velocity == 255 && !h.gate);
    h.noteOn(60, 100);
    CHECK(h.gate && !h.open && h.velocity == 200);
    h.noteOn(61, 127);
    CHECK(h.gate && h.open && h.velocity == 254);
    h.noteOff(64);
    CHECK(!h.gate && h.velocity == 128 && h.open);
}

int main() {
    testNoise();
    testCutoff();
    testMidi();
    testHihat();
    if (failures) {
        printf("%d check(s) failed\n", failures);
        return 1;
    }
    printf("all HATS logic tests passed\n");
    printf("cutoff duty (%% of full) at knob 0/256/512/768/1023: %.2f %.3f %.4f %.5f %.6f\n",
           100.0 * cutoffDuty(0) / PWM_FULL, 100.0 * cutoffDuty(256) / PWM_FULL, 100.0 * cutoffDuty(512) / PWM_FULL,
           100.0 * cutoffDuty(768) / PWM_FULL, 100.0 * cutoffDuty(1023) / PWM_FULL);
    printf("noise sample rate at TONE 0/256/511/600/1023 (Hz): %.0f %.0f %.0f %.1f %.2f\n",
           (double)NOISE_TICK_HZ / noiseHoldTicks(0), (double)NOISE_TICK_HZ / noiseHoldTicks(256),
           (double)NOISE_TICK_HZ / noiseHoldTicks(511), (double)NOISE_TICK_HZ / noiseHoldTicks(600),
           (double)NOISE_TICK_HZ / noiseHoldTicks(1023));
    return 0;
}
