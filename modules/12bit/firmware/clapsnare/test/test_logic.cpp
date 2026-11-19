// Host tests for src/clapsnare_logic.h. With a directory argument it also
// writes preview WAVs there (the DAC codes of a few knob settings), see
// ../test.sh.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "clapsnare_logic.h"

using namespace clapsnare;

static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); failures++; } } while (0)

static Tables tables;

// One hit at the given knobs: the Q15 samples until the voice goes idle.
static std::vector<int32_t> hit(uint16_t morph, uint16_t tone, uint16_t decay, uint8_t velocity,
                                uint32_t seed = 0x2F6E2B1Du, Voice *keep = nullptr) {
    Voice v;
    v.noise = seed;
    v.p = makeParams(tables, morph, tone, decay);
    v.trigger(velocity);
    std::vector<int32_t> out;
    while (v.active && out.size() < 20 * SAMPLE_RATE_HZ) out.push_back(v.render(tables.sine));
    if (keep) *keep = v;
    return out;
}

static int32_t peak(const std::vector<int32_t> &s, size_t from = 0, size_t to = SIZE_MAX) {
    int32_t m = 0;
    for (size_t i = from; i < s.size() && i < to; i++) m = std::abs(s[i]) > m ? std::abs(s[i]) : m;
    return m;
}

static double rms(const std::vector<int32_t> &s, size_t from, size_t to) {
    double sum = 0;
    size_t n = 0;
    for (size_t i = from; i < s.size() && i < to; i++, n++) sum += (double)s[i] * s[i];
    return n ? sqrt(sum / n) : 0;
}

// Power at one frequency over a window (Goertzel).
static double tonePower(const std::vector<int32_t> &s, size_t from, size_t to, double hz) {
    const double c = 2 * cos(6.283185307 * hz / SAMPLE_RATE_HZ);
    double s1 = 0, s2 = 0;
    for (size_t i = from; i < s.size() && i < to; i++) {
        const double s0 = s[i] + c * s1 - s2;
        s2 = s1;
        s1 = s0;
    }
    return s1 * s1 + s2 * s2 - c * s1 * s2;
}

// Zero crossings per second over a window: the pitch of a clean tone.
static double zeroCrossRate(const std::vector<int32_t> &s, size_t from, size_t to) {
    size_t n = 0;
    for (size_t i = from + 1; i < s.size() && i < to; i++) n += (s[i - 1] < 0) != (s[i] < 0);
    return (double)n * SAMPLE_RATE_HZ / (double)(to - from);
}

static void testTables() {
    CHECK(tables.sine[0] == 0 && tables.sine[SINE_SIZE / 4] == 32767 && tables.sine[3 * SINE_SIZE / 4] == -32767);
    CHECK(tables.ratio(0) == 65536);
    CHECK(tables.ratio(65536) == 131072);
    CHECK(std::abs((int32_t)tables.ratio(32768) - 92682) < 8);          // sqrt(2)
    CHECK(tables.knobRatio(0, 3 * 65536) == 65536);
    CHECK(std::abs((int32_t)tables.knobRatio(KNOB_MAX, 3 * 65536) - 8 * 65536) < 64);
    CHECK(tables.knobRatio(9999, 65536) == tables.knobRatio(KNOB_MAX, 65536));
    for (uint16_t k = 1; k <= KNOB_MAX; k++) CHECK(tables.knobRatio(k, 4 * 65536) >= tables.knobRatio(k - 1, 4 * 65536));
}

static void testParams() {
    // MORPH: pure clap at the bottom, pure snare at the top, both in the middle
    Params lo = makeParams(tables, 0, 2048, 2048);
    Params mid = makeParams(tables, 2048, 2048, 2048);
    Params hi = makeParams(tables, KNOB_MAX, 2048, 2048);
    CHECK(lo.clapGain == 256 && lo.snareGain == 0);
    CHECK(hi.clapGain == 0 && hi.snareGain == 256);
    CHECK(mid.clapGain > 180 && mid.clapGain < 256 && std::abs(mid.clapGain - mid.snareGain) <= 2);
    CHECK(makeParams(tables, MORPH_DEAD, 0, 0).snareGain == 0);
    CHECK(makeParams(tables, KNOB_MAX - MORPH_DEAD, 0, 0).clapGain == 0);
    for (uint16_t k = 1; k <= KNOB_MAX; k++) {
        Params a = makeParams(tables, k - 1, 0, 0), b = makeParams(tables, k, 0, 0);
        CHECK(b.clapGain <= a.clapGain + 1 && b.snareGain + 1 >= a.snareGain);   // no jumps back
        CHECK(std::abs(b.clapGain - a.clapGain) <= 2 && std::abs(b.snareGain - a.snareGain) <= 2);
    }

    // TONE: clap band 650 Hz .. 2.43 kHz, snare 135 .. 300 Hz
    const double fClapLo = makeParams(tables, 0, 0, 0).clapF / 32768.0 * 48000 / 6.2831853;
    const double fClapHi = makeParams(tables, 0, KNOB_MAX, 0).clapF / 32768.0 * 48000 / 6.2831853;
    CHECK(fabs(fClapLo - 650) < 2 && fabs(fClapHi - 2426) < 10);
    const double hzLo = makeParams(tables, 0, 0, 0).bodyInc * 48000.0 / 4294967296.0;
    const double hzHi = makeParams(tables, 0, KNOB_MAX, 0).bodyInc * 48000.0 / 4294967296.0;
    CHECK(fabs(hzLo - 135) < 0.5 && fabs(hzHi - 300) < 1.5);

    // DECAY: time constants = 2^24 / (k x 48000)
    auto tauMs = [](uint32_t k) { return 16777216.0 / k / 48.0; };
    Params shortP = makeParams(tables, 0, 0, 0), longP = makeParams(tables, 0, 0, KNOB_MAX);
    CHECK(fabs(tauMs(shortP.clapTailK) - 30) < 0.5 && fabs(tauMs(longP.clapTailK) - 500) < 10);
    CHECK(fabs(tauMs(shortP.noiseK) - 30) < 0.5 && fabs(tauMs(longP.noiseK) - 400) < 8);
    CHECK(fabs(tauMs(shortP.bodyK) - 25) < 0.5 && fabs(tauMs(longP.bodyK) - 110) < 3);
}

static void testEnvelope() {
    // decayStep follows exp(-t / tau) and reaches zero
    uint32_t env = ENV_FULL;
    const uint32_t k = decayK(50.0f);
    for (int i = 0; i < 2400; i++) env = decayStep(env, k);                 // one tau
    CHECK(fabs((double)env / ENV_FULL - 0.3679) < 0.01);
    for (int i = 0; i < 48000 && env; i++) env = decayStep(env, k);
    CHECK(env == 0);

    // soft clipper: odd, monotonic, x1.5 for small signals, +-32767 at the rails
    CHECK(softClip(0) == 0 && softClip(32767) >= 32764 && softClip(1000000) == softClip(32767));
    CHECK(softClip(-12345) == -softClip(12345));
    CHECK(abs(softClip(1000) - 1500) <= 2);
    for (int32_t x = -40000; x < 40000; x += 7) CHECK(softClip(x + 7) >= softClip(x));
    CHECK(toDac(0) == DAC_MID && toDac(32767) <= DAC_MID + DAC_SWING && toDac(-32767) >= DAC_MID - DAC_SWING - 1);
}

static void testClap() {
    Voice v;
    std::vector<int32_t> s = hit(0, 2048, 2048, 127, 0x2F6E2B1Du, &v);
    CHECK(!v.active && v.render(tables.sine) == 0);

    // Four hits: each one is louder than the gap before it.
    const size_t SP = CLAP_SPACING;
    for (int h = 1; h <= 3; h++) {
        const double before = rms(s, h * SP - 120, h * SP);
        const double after = rms(s, h * SP + 24, h * SP + 144);
        CHECK(after > 2.0 * before);
    }
    // The tail outlasts the bursts and has decayed by 3 tau.
    Params p = makeParams(tables, 0, 2048, 2048);
    const size_t tau = (size_t)(16777216.0 / p.clapTailK);
    CHECK(rms(s, 3 * SP + tau, 3 * SP + tau + 480) < 0.6 * rms(s, 3 * SP + 24, 3 * SP + 504));
    CHECK(rms(s, 3 * SP + 4 * tau, 3 * SP + 4 * tau + 480) < 0.05 * rms(s, 3 * SP + 24, 3 * SP + 504));

    // DECAY sets the length, TONE the brightness
    CHECK(hit(0, 2048, KNOB_MAX, 127).size() > 5 * hit(0, 2048, 0, 127).size());
    std::vector<int32_t> dark = hit(0, 0, 3000, 127), bright = hit(0, KNOB_MAX, 3000, 127);
    auto bandRatio = [&](const std::vector<int32_t> &x) {     // 2.4 kHz band over 650 Hz band
        double hi = 0, lo = 0;
        for (double d = -100; d <= 100; d += 20) {
            hi += tonePower(x, 3 * SP, 3 * SP + 9600, 2400 + d);
            lo += tonePower(x, 3 * SP, 3 * SP + 9600, 650 + d);
        }
        return hi / lo;
    };
    CHECK(bandRatio(dark) < 0.5 && bandRatio(bright) > 4.0);
    // ... at about the same loudness
    const double ld = rms(dark, 3 * SP, 3 * SP + 9600), lb = rms(bright, 3 * SP, 3 * SP + 9600);
    CHECK(lb / ld > 0.7 && lb / ld < 1.4);
}

static void testSnare() {
    Voice v;
    std::vector<int32_t> s = hit(KNOB_MAX, 2048, 2048, 127, 0x2F6E2B1Du, &v);
    CHECK(!v.active);

    // TONE tunes the body: count the cycles of a noise-free voice
    for (uint16_t tone : {(uint16_t)0, (uint16_t)KNOB_MAX}) {
        Voice b;
        b.p = makeParams(tables, KNOB_MAX, tone, KNOB_MAX);
        b.trigger(127);
        b.noiseEnv = b.snapEnv = 0;            // body only
        b.body2Env = 0;
        std::vector<int32_t> o;
        for (int i = 0; i < 9600; i++) o.push_back(b.render(tables.sine));
        const double hz = zeroCrossRate(o, 4800, 9600) / 2;   // after the pitch drop
        CHECK(fabs(hz - (tone ? 300.0 : 135.0)) < 6.0);
        // pitch drop: over the first 10 ms the phase runs 1 + 0.6 (1 - 1/e) = 1.38 x ahead
        Voice d;
        d.p = b.p;
        d.trigger(127);
        uint64_t advance = 0;
        for (int i = 0; i < 480; i++) {
            const uint32_t before = d.phase1;
            d.render(tables.sine);
            advance += (uint32_t)(d.phase1 - before);
        }
        CHECK(fabs((double)advance / (480.0 * d.p.bodyInc) - 1.379) < 0.02);
    }
    CHECK(hit(KNOB_MAX, 2048, KNOB_MAX, 127).size() > 5 * hit(KNOB_MAX, 2048, 0, 127).size());
}

static void testLevels() {
    // Every corner of the knobs: output inside the clipper, filters far from
    // their 32-bit limits, the voice ends, and a full hit is loud enough.
    for (uint16_t morph : {(uint16_t)0, (uint16_t)1024, (uint16_t)2048, (uint16_t)3072, (uint16_t)KNOB_MAX}) {
        for (uint16_t tone : {(uint16_t)0, (uint16_t)2048, (uint16_t)KNOB_MAX}) {
            for (uint16_t decay : {(uint16_t)0, (uint16_t)2048, (uint16_t)KNOB_MAX}) {
                int32_t worst = 0, quietest = 32767, bandMax = 0;
                size_t longest = 0;
                for (uint32_t seed = 1; seed <= 24; seed++) {
                    Voice v;
                    v.noise = seed * 0x9E3779B9u;
                    v.p = makeParams(tables, morph, tone, decay);
                    v.trigger(127);
                    int32_t pk = 0;
                    size_t n = 0;
                    while (v.active && n < 20 * SAMPLE_RATE_HZ) {
                        int32_t s = v.render(tables.sine);
                        n++;
                        if (abs(s) > pk) pk = abs(s);
                        if (abs(v.cBand) > bandMax) bandMax = abs(v.cBand);
                        if (abs(v.sBand) > bandMax) bandMax = abs(v.sBand);
                        if (abs(v.cLow) > bandMax) bandMax = abs(v.cLow);
                        if (abs(v.sLow) > bandMax) bandMax = abs(v.sLow);
                    }
                    if (pk > worst) worst = pk;
                    if (pk < quietest) quietest = pk;
                    if (n > longest) longest = n;
                }
                CHECK(worst <= 32767);
                CHECK(quietest > 22000);                       // > -3.5 dBFS at full velocity
                CHECK(bandMax < 60000);                        // x coefficient stays inside int32
                CHECK(longest < 6 * SAMPLE_RATE_HZ);
            }
        }
    }
    // Velocity scales the level; a soft hit is not driven into the clipper.
    CHECK(peak(hit(2048, 2048, 2048, 32)) < peak(hit(2048, 2048, 2048, 127)) / 2);
    CHECK(peak(hit(2048, 2048, 2048, 1)) < 600);
    // Retrigger while sounding restarts the hit.
    Voice v;
    v.p = makeParams(tables, 0, 2048, KNOB_MAX);
    v.trigger(127);
    for (int i = 0; i < 30000; i++) v.render(tables.sine);
    v.trigger(100);
    CHECK(v.active && v.clapCount == 0 && v.burstEnv == ENV_FULL && v.tailEnv == 0);
}

static void testCv() {
    // 0 V (and the tolerance band around it) leaves the knob alone
    for (uint16_t k : {(uint16_t)0, (uint16_t)1234, KNOB_MAX}) {
        CHECK(applyCv(k, CV_ZERO) == k);
        CHECK(applyCv(k, CV_ZERO + CV_DEAD) == k && applyCv(k, CV_ZERO - CV_DEAD) == k);
    }
    // 342.9 ADC codes per volt: +5 V from the bottom = the top, -5 V back down
    auto code = [](double volts) { return (uint16_t)lrint(CV_ZERO + 342.9 * volts); };
    CHECK(applyCv(0, code(5.0)) >= KNOB_MAX - 8);
    CHECK(applyCv(KNOB_MAX, code(-5.0)) <= 8);
    CHECK(abs((int)applyCv(2048, code(2.5)) - KNOB_MAX) < 80);
    CHECK(abs((int)applyCv(2048, code(1.0)) - (2048 + 819)) < 80);
    CHECK(abs((int)applyCv(2048, code(-1.0)) - (2048 - 819)) < 80);
    // Clamped at the ends, the whole ADC range
    CHECK(applyCv(3000, 4095) == KNOB_MAX && applyCv(1000, 0) == 0);
    // No jump at the dead band, never backwards
    for (uint16_t c = 1; c <= 4095; c++) {
        const int a = applyCv(2048, c - 1), b = applyCv(2048, c);
        CHECK(b >= a && b - a <= 3);
    }
    // The fast CV filter settles in a few scans, the knob one is slower
    KnobFilter fast, slow;
    fast.rate = 2;
    fast.update(0);
    slow.update(0);
    uint16_t f = 0, sl = 0;
    for (int i = 0; i < 12; i++) { f = fast.update(4000); sl = slow.update(4000); }
    CHECK(f > 3800 && sl < 2400);
    for (int i = 0; i < 200; i++) f = fast.update(4000);
    CHECK(f >= 3999);
    // set() jumps (the first read after the scan was off), then it glides again
    CHECK(slow.set(1000) == 1000);
    sl = slow.update(3000);
    CHECK(sl > 1000 && sl < 1300);
}

static void testRecorder() {
    static MotionRecorder r;
    uint16_t live[3] = {100, 200, 300}, out[3] = {9, 9, 9};
    CHECK(!r.onClock(live, out) && out[0] == 9);             // LIVE: nothing
    r.press();
    CHECK(r.state == MotionRecorder::RECORDING);
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) {
        live[0] = t; live[1] = 1000 + t; live[2] = 4000;
        CHECK(r.onClock(live, out) && out[0] == t && out[2] == 4000);   // hears the knobs
    }
    CHECK(r.state == MotionRecorder::PLAYBACK && r.tick == 0);
    // First pass: knobs ignored, whatever they do
    live[0] = 3000; live[1] = 0; live[2] = 2000;
    for (uint16_t t = 0; t < MotionRecorder::LOOP_TICKS; t++) {
        CHECK(r.onClock(live, out) && out[0] == t && out[1] == 1000 + t && out[2] == 4000);
    }
    // Then a knob move shifts its lane, clamped to the knob range
    live[0] = 3010; live[1] = 0; live[2] = 2500;
    CHECK(r.onClock(live, out) && out[0] == 10 && out[1] == 1000 && out[2] == KNOB_MAX);
    live[0] = 2000;
    CHECK(r.onClock(live, out) && out[0] == 0 && out[1] == 1001);
    r.onStart();
    CHECK(r.tick == 0);
    r.press();
    CHECK(r.state == MotionRecorder::LIVE && !r.onClock(live, out));
    // A press while recording discards the take
    r.press();
    r.onClock(live, out);
    r.press();
    CHECK(r.state == MotionRecorder::LIVE);
    r.onStart();                                             // no effect in LIVE
    CHECK(!r.onClock(live, out));
}

static void testMidi() {
    MidiParser m;
    auto feed = [&](std::initializer_list<uint8_t> bytes) {
        MidiParser::Event last = {MidiParser::NONE, 0, 0};
        for (uint8_t b : bytes) last = m.feed(b);
        return last;
    };
    MidiParser::Event e = feed({0x99, 38, 100});
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 38 && e.data2 == 100);
    e = feed({40, 64});                                      // running status
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 40 && e.data2 == 64);
    e = feed({40, 0});                                       // velocity 0 = note-off
    CHECK(e.kind == MidiParser::NOTE_OFF);
    CHECK(m.feed(0x90).kind == MidiParser::NONE);
    CHECK(m.feed(60).kind == MidiParser::NONE);
    CHECK(m.feed(0xF8).kind == MidiParser::CLOCK);           // clock inside a message
    e = m.feed(127);
    CHECK(e.kind == MidiParser::NOTE_ON && e.data1 == 60 && e.data2 == 127);
    CHECK(m.feed(0xFA).kind == MidiParser::START);
    CHECK(feed({0x80, 60, 0}).kind == MidiParser::NOTE_OFF);
    CHECK(feed({0xF0, 1, 2, 3, 0xF7, 5, 6}).kind == MidiParser::NONE);   // SysEx cancels running status
}

static void writeWav(const std::string &path, const std::vector<int16_t> &pcm) {
    FILE *f = std::fopen(path.c_str(), "wb");
    if (!f) { std::printf("cannot write %s\n", path.c_str()); failures++; return; }
    const uint32_t bytes = (uint32_t)pcm.size() * 2, rate = SAMPLE_RATE_HZ;
    auto u32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, f); };
    auto u16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, f); };
    std::fwrite("RIFF", 1, 4, f); u32(36 + bytes); std::fwrite("WAVEfmt ", 1, 8, f);
    u32(16); u16(1); u16(1); u32(rate); u32(rate * 2); u16(2); u16(16);
    std::fwrite("data", 1, 4, f); u32(bytes);
    std::fwrite(pcm.data(), 2, pcm.size(), f);
    std::fclose(f);
}

// What the DAC plays (12-bit codes around mid-scale, scaled to 16 bit).
static void append(std::vector<int16_t> &pcm, Voice &v, uint32_t samples) {
    for (uint32_t i = 0; i < samples; i++) {
        const int32_t code = (int32_t)toDac(v.render(tables.sine)) - DAC_MID;
        pcm.push_back((int16_t)(code * 32767 / DAC_SWING));
    }
}

static void writePreviews(const std::string &dir) {
    struct Preset { const char *name; uint16_t morph, tone, decay; };
    const Preset presets[] = {
        {"clap-dark-short", 0, 600, 1200},      {"clap-mid", 0, 2048, 2048},
        {"clap-bright-long", 0, 3600, 3300},    {"layer-mid", 2048, 2048, 2048},
        {"layer-clap-over-snare", 2800, 1600, 1800}, {"snare-low-long", KNOB_MAX, 500, 3000},
        {"snare-mid", KNOB_MAX, 2048, 2048},    {"snare-high-tight", KNOB_MAX, 3600, 900},
    };
    const uint32_t beat = SAMPLE_RATE_HZ * 60 / 126;     // 126 BPM
    for (const Preset &p : presets) {
        Voice v;
        v.p = makeParams(tables, p.morph, p.tone, p.decay);
        std::vector<int16_t> pcm;
        for (uint8_t vel : {(uint8_t)127, (uint8_t)127, (uint8_t)90, (uint8_t)127}) {
            v.trigger(vel);
            append(pcm, v, 2 * beat);                    // on 2 and 4
        }
        writeWav(dir + "/" + p.name + ".wav", pcm);
    }
    // One long file: the three knobs swept one after the other, a hit per beat.
    std::vector<int16_t> pcm;
    Voice v;
    for (int knob = 0; knob < 3; knob++) {
        for (int step = 0; step <= 16; step++) {
            uint16_t k[3] = {(uint16_t)(knob == 0 ? 0 : 2048), 2048, 2048};
            k[knob] = (uint16_t)(step * KNOB_MAX / 16);
            v.p = makeParams(tables, k[0], k[1], k[2]);
            v.trigger(127);
            append(pcm, v, beat);
        }
    }
    writeWav(dir + "/sweep-morph-tone-decay.wav", pcm);
    std::printf("preview WAVs in %s\n", dir.c_str());
}

int main(int argc, char **argv) {
    tables.fill();
    testTables();
    testParams();
    testEnvelope();
    testClap();
    testSnare();
    testLevels();
    testCv();
    testRecorder();
    testMidi();
    if (argc > 1) writePreviews(argv[1]);
    std::printf(failures ? "%d failure(s)\n" : "all tests passed\n", failures);
    return failures ? 1 : 0;
}
