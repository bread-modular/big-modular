#!/usr/bin/env python3
"""Build the polysynth wavetables (includes/audio/gen/wavetable_data.h).

The 17 tables come from two places:

  * generated shapes (Classic: square -> saw -> triangle -> sine, Basic: sine ->
    triangle -> saw -> square -> pulse, and a PWM sweep), computed here;
  * the Adventure Kid single-cycle waveforms (AKWF-FREE, CC0 1.0,
    https://github.com/KristofferKarlAxelEkstrand/AKWF-FREE, commit 8de90bf),
    16 waves picked evenly from one or more AKWF folders and sorted dark ->
    bright (spectral centroid), so the position knob sweeps the brightness.

A table can also be a Serum-format wavetable WAV (frames of 2048 samples, or
the size in its `clm ` chunk): `--serum NAME=path.wav` replaces the table of
that name (16 frames are picked evenly across the file, in order). Serum's own
factory tables are Xfer's and not redistributable, so none are shipped.

Every frame is phase-aligned on its fundamental (AKWF only; Serum frames keep
their phase), DC-free, and band-limited into one mip level per octave: level l
keeps harmonics 1..H[l] (128 down to 1) and holds N[l] = max(64, 8 * H[l])
samples, so the oscillator's cubic interpolation has at least eight points
per period of the top harmonic (tools/sim_wavetable.cpp: aliases and images
<= -40 dB). The firmware picks the level whose H[l] * f stays under 20 kHz.

Usage (the AKWF checkout is untrusted data: run with -I):
  git clone --depth 1 --filter=blob:none --sparse \\
      https://github.com/KristofferKarlAxelEkstrand/AKWF-FREE /tmp/wt-src/akwf
  git -C /tmp/wt-src/akwf sparse-checkout set AKWF
  python3 -I tools/build_wavetables.py --akwf /tmp/wt-src/akwf/AKWF
"""

import argparse
import os
import struct
import sys

import numpy as np

FRAMES = 16
HARMONICS = [128, 64, 32, 16, 8, 4, 2, 1]
SIZES = [max(64, 8 * h) for h in HARMONICS]
PEAK = 0.95
RENDER = 8192  # naive render size for the generated shapes

# (name, kind, source): kind "gen" = generated here, "akwf" = AKWF folders.
TABLES = [
    ("Classic", "gen", "classic"),
    ("Basic", "gen", "basic"),
    ("PWM", "gen", "pwm"),
    ("Harmonics", "akwf", ["AKWF_sinharm"]),
    ("Overtone", "akwf", ["AKWF_overtone"]),
    ("FM", "akwf", ["AKWF_fmsynth"]),
    ("Blended", "akwf", ["AKWF_bw_blended"]),
    ("Vocal", "akwf", ["AKWF_hvoice"]),
    ("Organ", "akwf", ["AKWF_eorgan"]),
    ("E-Piano", "akwf", ["AKWF_epiano"]),
    ("Strings", "akwf", ["AKWF_cello", "AKWF_violin"]),
    ("Reed", "akwf", ["AKWF_clarinett", "AKWF_oboe", "AKWF_altosax"]),
    ("Chip", "akwf", ["AKWF_oscchip"]),
    ("Game", "akwf", ["AKWF_vgame"]),
    ("Bitcrush", "akwf", ["AKWF_bitreduced"]),
    ("Distorted", "akwf", ["AKWF_distorted"]),
    ("Raw", "akwf", ["AKWF_raw"]),
]


def read_wav(path):
    """Mono float samples and the Serum `clm ` frame size (or None)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a RIFF/WAVE file")
    pos, fmt, samples, clm = 12, None, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = list(struct.unpack("<HHIIHH", body[:16]))
            if fmt[0] == 0xFFFE and len(body) >= 26:  # WAVE_FORMAT_EXTENSIBLE
                fmt[0] = struct.unpack("<H", body[24:26])[0]
        elif cid == b"data":
            samples = body
        elif cid == b"clm ":
            text = body.decode("ascii", "replace")
            if text.startswith("<!>"):
                clm = int(text[3:7])
        pos += 8 + size + (size & 1)
    if fmt is None or samples is None:
        raise ValueError(f"{path}: no fmt/data chunk")
    tag, channels, _, _, _, bits = fmt
    if tag == 3 and bits == 32:
        x = np.frombuffer(samples, "<f4").astype(np.float64)
    elif tag == 1 and bits == 16:
        x = np.frombuffer(samples, "<i2") / 32768.0
    elif tag == 1 and bits == 24:
        b = np.frombuffer(samples, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v) / float(1 << 23)
    elif tag == 1 and bits == 32:
        x = np.frombuffer(samples, "<i4") / float(1 << 31)
    else:
        raise ValueError(f"{path}: unsupported format tag {tag} / {bits} bit")
    return x.reshape(-1, channels).mean(axis=1), clm


def spectrum(cycle):
    """Harmonics 1..max of one cycle (complex, DC dropped)."""
    s = np.fft.rfft(cycle) / len(cycle)
    return s[1:]


def align(spec):
    """Rotate the cycle so the fundamental starts like a sine (phase -pi/2)."""
    if abs(spec[0]) < 1e-9:
        return spec
    shift = np.angle(spec[0]) + np.pi / 2
    k = np.arange(1, len(spec) + 1)
    return spec * np.exp(-1j * k * shift)


def render(spec, harmonics, size):
    full = np.zeros(size // 2 + 1, complex)
    n = min(harmonics, len(spec), size // 2 - 1)
    full[1:n + 1] = spec[:n]
    return np.fft.irfft(full * size, size)


def centroid(spec):
    mag = np.abs(spec[:HARMONICS[0]])
    k = np.arange(1, len(mag) + 1)
    return float((mag * k).sum() / max(mag.sum(), 1e-12))


def naive(shape, width=0.5):
    x = (np.arange(RENDER) + 0.5) / RENDER
    if shape == "sine":
        return np.sin(2 * np.pi * x)
    if shape == "tri":
        return 1 - 4 * np.abs(((x + 0.25) % 1.0) - 0.5)
    if shape == "saw":
        return 1 - 2 * ((x + 0.5) % 1.0)
    if shape == "pulse":
        return np.where(x < width, 1.0, -1.0)
    raise ValueError(shape)


def generated(kind):
    if kind == "classic":
        # P1 fully down: the basic shapes, crossfaded square -> saw -> tri ->
        # sine. Each pure shape sits on a frame (0, 5, 10, 15) and the frames
        # between are evenly spaced crossfades, so P2 morphs smoothly.
        keys = [align(spectrum(naive(k))) for k in ("pulse", "saw", "tri", "sine")]
        frames = []
        for i in range(FRAMES):
            p = i * (len(keys) - 1) / (FRAMES - 1)
            a = min(int(p), len(keys) - 2)
            t = p - a
            frames.append((1 - t) * keys[a] + t * keys[a + 1])
        return frames
    if kind == "basic":
        keys = [naive("sine"), naive("tri"), naive("saw"),
                naive("pulse", 0.5), naive("pulse", 0.25), naive("pulse", 0.1)]
        keys = [align(spectrum(k)) for k in keys]
        frames = []
        for i in range(FRAMES):
            p = i * (len(keys) - 1) / (FRAMES - 1)
            a = min(int(p), len(keys) - 2)
            t = p - a
            frames.append((1 - t) * keys[a] + t * keys[a + 1])
        return frames
    if kind == "pwm":
        widths = np.linspace(0.5, 0.03, FRAMES)
        return [align(spectrum(naive("pulse", w))) for w in widths]
    raise ValueError(kind)


def akwf(root, folders):
    files = []
    for folder in folders:
        d = os.path.join(root, folder)
        files += [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.lower().endswith(".wav")]
    if len(files) < FRAMES:
        raise ValueError(f"{folders}: {len(files)} waves, need {FRAMES}")
    picks = [files[round(i * (len(files) - 1) / (FRAMES - 1))] for i in range(FRAMES)]
    specs = []
    for path in picks:
        x, _ = read_wav(path)
        specs.append(align(spectrum(x)))
    order = sorted(range(FRAMES), key=lambda i: centroid(specs[i]))
    return [specs[i] for i in order], [os.path.basename(picks[i]) for i in order]


def serum(path):
    x, clm = read_wav(path)
    size = clm or 2048
    count = len(x) // size
    if count < 1:
        raise ValueError(f"{path}: shorter than one {size}-sample frame")
    idx = [round(i * (count - 1) / (FRAMES - 1)) for i in range(FRAMES)]
    return [spectrum(x[i * size:(i + 1) * size]) for i in idx]


def levels(spec):
    out = [render(spec, h, n) for h, n in zip(HARMONICS, SIZES)]
    peak = max(np.max(np.abs(lv)) for lv in out)
    gain = PEAK / peak if peak > 1e-9 else 0.0
    return [np.round(lv * gain * 32767).astype(np.int16) for lv in out]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--akwf", required=True, help="AKWF folder of an AKWF-FREE checkout")
    ap.add_argument("--serum", action="append", default=[], metavar="NAME=WAV",
                    help="replace table NAME with a Serum-format wavetable WAV")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "..", "includes", "audio", "gen", "wavetable_data.h"))
    args = ap.parse_args()

    serums = dict(s.split("=", 1) for s in args.serum)
    unknown = set(serums) - {t[0] for t in TABLES}
    if unknown:
        sys.exit(f"unknown table(s): {', '.join(sorted(unknown))}")

    tables, notes = [], []
    for name, kind, source in TABLES:
        if name in serums:
            tables.append(serum(serums[name]))
            notes.append(f"{name}: Serum WAV {os.path.basename(serums[name])}")
        elif kind == "gen":
            tables.append(generated(source))
            notes.append(f"{name}: generated ({source})")
        else:
            specs, names = akwf(args.akwf, source)
            tables.append(specs)
            notes.append(f"{name}: AKWF {', '.join(source)}: " + " ".join(n[:-4] for n in names))

    stride = sum(SIZES)
    offsets = np.cumsum([0] + SIZES[:-1]).tolist()
    data = []
    for frames in tables:
        for spec in frames:
            for lv in levels(spec):
                data.extend(lv.tolist())
    assert len(data) == len(TABLES) * FRAMES * stride

    with open(args.out, "w") as f:
        f.write("// Generated by tools/build_wavetables.py: do not edit.\n")
        f.write("// Polysynth wavetables: AKWF-FREE single cycles (CC0 1.0, Adventure Kid,\n")
        f.write("// github.com/KristofferKarlAxelEkstrand/AKWF-FREE @ 8de90bf) and generated shapes.\n")
        f.write("// Layout: [table][frame][level][sample], level l = harmonics 1..H[l], N[l] samples.\n//\n")
        for n in notes:
            f.write(f"// {n}\n")
        f.write("\n#pragma once\n\n#include <stdint.h>\n\n")
        f.write(f"#define WAVETABLE_COUNT {len(TABLES)}\n")
        f.write(f"#define WAVETABLE_FRAMES {FRAMES}\n")
        f.write(f"#define WAVETABLE_LEVELS {len(HARMONICS)}\n")
        f.write(f"#define WAVETABLE_FRAME_STRIDE {stride}\n")
        f.write("#define WAVETABLE_TABLE_SAMPLES (WAVETABLE_FRAMES * WAVETABLE_FRAME_STRIDE)\n\n")
        f.write("// On the board the data stays in flash (.flashdata) while the polysynth\n")
        f.write("// runs from RAM (copy_to_ram); the app copies the selected table to RAM.\n")
        f.write("#if defined(PICO_ON_DEVICE) && PICO_ON_DEVICE\n")
        f.write('#define WAVETABLE_FLASH __attribute__((section(".flashdata.wavetables")))\n')
        f.write("#else\n#define WAVETABLE_FLASH\n#endif\n\n")
        f.write("static const char* const WAVETABLE_NAMES[WAVETABLE_COUNT] = {\n")
        f.write("".join(f'    "{t[0]}",\n' for t in TABLES) + "};\n\n")
        f.write("// Top harmonic, size and offset in the frame of each mip level.\n")
        f.write("static const uint16_t WAVETABLE_LEVEL_HARMONICS[WAVETABLE_LEVELS] = {"
                + ", ".join(map(str, HARMONICS)) + "};\n")
        f.write("static const uint16_t WAVETABLE_LEVEL_SIZE[WAVETABLE_LEVELS] = {"
                + ", ".join(map(str, SIZES)) + "};\n")
        f.write("static const uint8_t WAVETABLE_LEVEL_SHIFT[WAVETABLE_LEVELS] = {"
                + ", ".join(str(32 - int(np.log2(n))) for n in SIZES) + "};\n")
        f.write("static const uint16_t WAVETABLE_LEVEL_OFFSET[WAVETABLE_LEVELS] = {"
                + ", ".join(map(str, offsets)) + "};\n\n")
        f.write(f"static const int16_t WAVETABLE_DATA[{len(data)}] WAVETABLE_FLASH = {{\n")
        for i in range(0, len(data), 16):
            f.write("  " + ",".join(map(str, data[i:i + 16])) + ",\n")
        f.write("};\n")
    print(f"{args.out}: {len(TABLES)} tables x {FRAMES} frames x {stride} samples = "
          f"{len(data) * 2} bytes")


if __name__ == "__main__":
    main()
