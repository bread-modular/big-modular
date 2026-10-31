#!/usr/bin/env python3
"""Generate the polysynth wavetables (main/src/ps_dsp.c, waveform positions 1..7).

Run by the build (main/CMakeLists.txt) and the host tests (tests/Makefile); the
output is a generated C file, never edited by hand. Pure Python, no numpy.

Each waveform is one cycle, defined as a harmonic spectrum or in the time domain
(then analysed with an FFT). It is stored band-limited as an octave mipmap:
level l keeps harmonics 1 .. 1024 >> l, so the synth picks the level per note
and nothing above Nyquist is played. Table sizes shrink with the harmonic count
(>= 8 samples per top harmonic, min 256), each table has one guard sample for
linear interpolation. Every waveform is scaled to the RMS of the saw (1 / sqrt 3)
unless that would put a peak above PEAK_MAX, then to that peak.

usage: gen_wavetables.py OUT.c
"""
import cmath
import math
import random
import sys

LEVELS = 11            # max harmonics 1024, 512, ..., 1
TOP_HARMONICS = 1024
MAX_SIZE = 2048
MIN_SIZE = 256
ANALYSIS_SIZE = 32768  # time-domain waveforms are sampled at this size
PEAK_MAX = 0.98
SAW_RMS = 1.0 / math.sqrt(3.0)


def fft(a, inverse=False):
    """Iterative radix-2 FFT (len(a) a power of two)."""
    n = len(a)
    a = list(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    sign = 1.0 if inverse else -1.0
    length = 2
    while length <= n:
        w_len = cmath.exp(sign * 2j * math.pi / length)
        half = length // 2
        ws = [w_len ** k for k in range(half)]
        for start in range(0, n, length):
            for k in range(half):
                u = a[start + k]
                v = a[start + k + half] * ws[k]
                a[start + k] = u + v
                a[start + k + half] = u - v
        length <<= 1
    return a


def spectrum_of(samples):
    """Complex harmonics 1..TOP_HARMONICS of one sampled cycle (sine amplitude units)."""
    n = len(samples)
    x = fft([complex(s, 0.0) for s in samples])
    return [2.0 * x[h] / n for h in range(1, TOP_HARMONICS + 1)]


def from_partials(partials):
    """partials: {harmonic: (amplitude, phase)} of sin(2 pi h t + phase)."""
    spec = [0j] * TOP_HARMONICS
    for h, (amp, ph) in partials.items():
        if 1 <= h <= TOP_HARMONICS:
            # sin(w + ph) = Im(e^{i(w + ph)}): coefficient c with x = Re(c e^{iw}), c = -i e^{i ph}
            spec[h - 1] = amp * cmath.exp(1j * (ph - math.pi / 2))
    return spec


def low_crest(amps, trials=96):
    """Partials {h: amp} with the phases (seeded random search) that give the
    lowest peak: a static spectrum sounds the same with any phases, and a low
    crest factor lets the waveform reach the saw's RMS under PEAK_MAX."""
    best, best_peak = None, None
    for seed in range(trials):
        rng = random.Random(seed)
        spec = from_partials({h: (a, rng.uniform(0.0, 2.0 * math.pi)) for h, a in amps.items()})
        peak = max(abs(v) for v in render(spec, TOP_HARMONICS, MAX_SIZE))
        if best_peak is None or peak < best_peak:
            best, best_peak = spec, peak
    return best


def sampled(fn):
    n = ANALYSIS_SIZE
    return spectrum_of([fn(i / n) for i in range(n)])


def frac(x):
    return x - math.floor(x)


# --- waveforms --------------------------------------------------------------

def vox():
    """Vowel 'ah' on a 110 Hz reference: 1 / h saw spectrum under formants."""
    formants = [(700.0, 1.0, 0.22), (1220.0, 0.55, 0.2), (2600.0, 0.3, 0.18)]
    p = {}
    for h in range(1, 120):
        f = 110.0 * h
        env = 0.08 + 0.5 * math.exp(-(h - 1) / 1.5)  # body: fundamental and 2nd
        for fc, gain, width in formants:
            env += gain * math.exp(-0.5 * (math.log2(f / fc) / width) ** 2)
        p[h] = env / h ** 0.6
    return low_crest(p)


def organ():
    """Drawbar organ: 8' 4' 2 2/3' 2' 1 3/5' 1 1/3' 1'."""
    bars = {1: 1.0, 2: 0.75, 3: 0.55, 4: 0.5, 5: 0.22, 6: 0.3, 8: 0.32, 10: 0.12, 12: 0.1, 16: 0.08}
    return low_crest(bars)


def reed():
    """12 % pulse blended with a saw: nasal, hollow reed."""
    spec = sampled(lambda t: 0.55 * ((1.0 if t < 0.12 else 0.0) - 0.12) * 2.2 + 0.45 * (1.0 - 2.0 * t))
    return low_crest({h + 1: abs(c) for h, c in enumerate(spec) if abs(c) > 1e-6})


def fm():
    """2-operator FM, ratio 2, index 2.4, with a little feedback-like 3rd."""
    return sampled(lambda t: math.sin(2 * math.pi * t + 2.4 * math.sin(4 * math.pi * t)
                                      + 0.6 * math.sin(6 * math.pi * t)))


def sync():
    """Hard-synced saw, slave at 2.7 x the master, faded across the cycle."""
    spec = sampled(lambda t: (2.0 * frac(2.7 * t) - 1.0) * (1.0 - 0.6 * t))
    return low_crest({h + 1: abs(c) for h, c in enumerate(spec) if abs(c) > 1e-6})


def metal():
    """Sparse odd/prime partials: hard, bell-like."""
    parts = {1: 1.0, 3: 0.25, 7: 0.6, 9: 0.4, 13: 0.5, 17: 0.38, 19: 0.3, 23: 0.28, 29: 0.2,
             31: 0.16, 37: 0.12, 41: 0.1, 47: 0.08}
    return low_crest(parts)


def fold():
    """Sine through a triangle wavefolder at 3.4 x drive."""
    def tri_fold(x):
        return 4.0 * abs(frac((x + 1.0) / 4.0) - 0.5) - 1.0
    return sampled(lambda t: tri_fold(3.4 * math.sin(2 * math.pi * t)))


WAVES = [("vox", vox), ("organ", organ), ("reed", reed), ("fm", fm),
         ("sync", sync), ("metal", metal), ("fold", fold)]

# --- tables -----------------------------------------------------------------


def level_size(level):
    h = TOP_HARMONICS >> level
    return max(MIN_SIZE, min(MAX_SIZE, 8 * h))


def render(spec, max_h, size):
    buf = [0j] * size
    for h in range(1, min(max_h, size // 2 - 1) + 1):
        buf[h] = spec[h - 1] / 2.0
        buf[size - h] = spec[h - 1].conjugate() / 2.0
    return [v.real for v in fft(buf, inverse=True)]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sizes = [level_size(l) for l in range(LEVELS)]
    tables = []
    for name, fn in WAVES:
        spec = fn()
        levels = [render(spec, TOP_HARMONICS >> l, sizes[l]) for l in range(LEVELS)]
        rms = math.sqrt(sum(v * v for v in levels[0]) / sizes[0])
        peak = max(max(abs(v) for v in t) for t in levels)
        scale = min(SAW_RMS / rms, PEAK_MAX / peak)
        tables.append((name, [[v * scale for v in t] for t in levels], rms * scale))

    offsets = []
    data = []
    for name, levels, _ in tables:
        row = []
        for t in levels:
            row.append(len(data))
            data.extend(int(round(v * 32767.0)) for v in t)
            data.append(int(round(t[0] * 32767.0)))  # guard sample
        offsets.append(row)

    out = []
    out.append("// GENERATED by tools/gen_wavetables.py; do not edit.")
    out.append('#include "ps_wavetables.h"')
    out.append("")
    out.append("#if PS_WT_COUNT != %d || PS_WT_LEVELS != %d" % (len(WAVES), LEVELS))
    out.append('#error "ps_wavetables.h does not match tools/gen_wavetables.py"')
    out.append("#endif")
    out.append("")
    out.append("// " + ", ".join("%d %s (RMS %.3f)" % (i + 1, n, r) for i, (n, _, r) in enumerate(tables)))
    out.append("const char *const ps_wt_names[PS_WT_COUNT] = {%s};" %
               ", ".join('"%s"' % n for n, _, _ in tables))
    out.append("const uint16_t ps_wt_size[PS_WT_LEVELS] = {%s};" % ", ".join(str(s) for s in sizes))
    out.append("const uint32_t ps_wt_offset[PS_WT_COUNT][PS_WT_LEVELS] = {")
    for row in offsets:
        out.append("    {%s}," % ", ".join(str(o) for o in row))
    out.append("};")
    out.append("const int16_t ps_wt_data[%d] = {" % len(data))
    for i in range(0, len(data), 16):
        out.append("    " + ",".join(str(v) for v in data[i:i + 16]) + ",")
    out.append("};")
    with open(sys.argv[1], "w") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
