#!/usr/bin/env python3
"""Build the polysynth wavetables (includes/audio/gen/wavetable_data.h).

P1 has 17 steps: 16 wavetables here, then Noise (no table: the oscillator
makes it, wavetable_osc.h). The tables come from two places:

  * generated shapes (Classic: square -> saw -> triangle -> sine, and a PWM
    sweep), computed here;
  * Kimura Taro's free wavetables (CC0 1.0 Universal, 2021 release, made by
    programming and resampling for Serum / Vital), in the Vital `.vitaltable`
    conversion of atsushieno/open-vital-resources (commit 8c31ac1, the
    `KimuraTaroFreeWavetables/` folder, CC0 too): classic synths, FM and
    complex waves. No brightness-sorted or filter-sweep tables: the
    polysynth has its own filter.

A Kimura table holds 32..258 frames of 2048 samples; 16 are picked evenly
across it, in order, keeping their phase. A table can also be a Serum-format
wavetable WAV (frames of 2048 samples, or the size in its `clm ` chunk):
`--serum NAME=path.wav` replaces the table of that name the same way. Serum's
and Vital's own factory tables are not redistributable, so none are shipped.

Every frame is DC-free, normalised to the same peak and band-limited into one
mip level per octave: level l keeps harmonics 1..H[l] (128 down to 1) and
holds N[l] = max(64, 8 * H[l]) samples, so the oscillator's cubic
interpolation has at least eight points per period of the top harmonic
(tools/sim_wavetable.cpp: aliases and images <= -40 dB). The firmware picks
the level whose H[l] * f stays under 20 kHz.

Usage (the checkout is untrusted data: run with -I):
  git clone --filter=blob:none --no-checkout \\
      https://github.com/atsushieno/open-vital-resources /tmp/wt-src/ovr
  git -C /tmp/wt-src/ovr sparse-checkout set '/KimuraTaroFreeWavetables/'
  git -C /tmp/wt-src/ovr checkout 8c31ac1940173bb89ea342293236a6a96f8c97d0
  python3 -I tools/build_wavetables.py \\
      --kimura /tmp/wt-src/ovr/KimuraTaroFreeWavetables/Wavetables
"""

import argparse
import base64
import json
import os
import struct
import sys

import numpy as np

FRAMES = 16
HARMONICS = [128, 64, 32, 16, 8, 4, 2, 1]
SIZES = [max(64, 8 * h) for h in HARMONICS]
PEAK = 0.95
RENDER = 8192  # naive render size for the generated shapes

# (name, kind, source): kind "gen" = generated here, "kimura" = a Kimura Taro
# table (folder/name under --kimura, without .vitaltable).
TABLES = [
    ("Classic", "gen", "classic"),
    ("PWM", "gen", "pwm"),
    ("Sync", "kimura", "OSC Sync+PWM/SawSync4"),
    ("MS-20", "kimura", "Korg Analog  Synth PhaseShift2/MS 20 Square-PS2"),
    ("Analog", "kimura", "AnalogFour/A4TriSawPWM"),
    ("PPG", "kimura", "PPG Wave/PPG05"),
    ("VS", "kimura", "Prophet VS Wave/VS VMorph3"),
    ("CZ", "kimura", "Phase Distortion/PD1"),
    ("FM", "kimura", "PM[Simple]/PMSimple4"),
    ("FM Bright", "kimura", "PM[Simple]/PMSimple3"),
    ("FM Feedback", "kimura", "FM Feedback/FM FB2"),
    ("Hard FM", "kimura", "Hardcore FM/Hardcore FM1"),
    ("Fold", "kimura", "Folding/Folding6"),
    ("Walsh", "kimura", "Walsh Function/WHTHad Dy-"),
    ("Modulo", "kimura", "Modulo/Modulo10"),
    ("Digital", "kimura", "TE OP-1/OP1 Digital06"),
]
# The P1 step after the tables: noise made by the oscillator.
EXTRA_ZONES = ["Noise"]


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
    if kind == "pwm":
        widths = np.linspace(0.5, 0.03, FRAMES)
        return [align(spectrum(naive("pulse", w))) for w in widths]
    raise ValueError(kind)


def kimura(root, name):
    """16 frames of a Vital `.vitaltable` holding one Audio File Source."""
    path = os.path.join(root, name + ".vitaltable")
    with open(path) as f:
        table = json.load(f)
    comps = [c for g in table["groups"] for c in g["components"]]
    if len(comps) != 1 or comps[0].get("type") != "Audio File Source":
        raise ValueError(f"{path}: not a single Audio File Source")
    size = int(comps[0]["window_size"])
    x = np.frombuffer(base64.b64decode(comps[0]["audio_file"]), "<i2") / 32768.0
    count = len(x) // size
    if count < FRAMES:
        raise ValueError(f"{path}: {count} frames, need {FRAMES}")
    idx = [round(i * (count - 1) / (FRAMES - 1)) for i in range(FRAMES)]
    return [spectrum(x[i * size:(i + 1) * size]) for i in idx]


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
    ap.add_argument("--kimura", required=True,
                    help="KimuraTaroFreeWavetables/Wavetables of an open-vital-resources checkout")
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
            tables.append(kimura(args.kimura, source))
            notes.append(f"{name}: Kimura Taro {source}")

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
        f.write("// Polysynth wavetables: Kimura Taro free wavetables (CC0 1.0, 2021 release;\n")
        f.write("// Vital conversion github.com/atsushieno/open-vital-resources @ 8c31ac1)\n")
        f.write("// and generated shapes. P1's last step, Noise, has no table.\n")
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
        f.write(f"#define WAVETABLE_ZONE_COUNT {len(TABLES) + len(EXTRA_ZONES)}  // P1 steps: tables + Noise\n\n")
        f.write("static const char* const WAVETABLE_NAMES[WAVETABLE_ZONE_COUNT] = {\n")
        f.write("".join(f'    "{n}",\n' for n in [t[0] for t in TABLES] + EXTRA_ZONES) + "};\n\n")
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
