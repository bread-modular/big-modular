#!/usr/bin/env python3
"""Render and measure the fxrack reverbs (old BM classic vs hall).

Synthesises test signals (impulse, clap, drum loop, synth stabs, plucks, a
full-scale pad), runs them through `render_reverb`, then writes:

  wav/<signal>_<reverb>.wav   dry + wet at the fxrack mix 0.4 (and *_wet.wav)
  metrics.md                  RT60 per octave band, echo density, colouration,
                              levels, host cost
  *.png                       energy decay, echo density, IR spectrograms,
                              late-tail spectra

Usage: reverb_sim.py --render ./render_reverb --out <dir>
"""
import argparse
import os
import subprocess
import tempfile
import wave

import numpy as np
from scipy import signal
from scipy.special import erfc

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FS = 44100
SERIES = {"classic": "#2a78d6", "hall": "#eb6834"}
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"

# (name, reverb, rt60 seconds)
CASES = [
    ("classic 3 s (old max)", "classic", 3.0),
    ("hall 2 s", "hall", 2.0),
    ("hall 4 s", "hall", 4.0),
    ("hall 8 s", "hall", 8.0),
    ("hall 20 s (max)", "hall", 20.0),
]


def tag(reverb, rt60):
    return f"{reverb}_{rt60:g}s"


# ---------------------------------------------------------------- signals

def env(n, attack, decay):
    t = np.arange(n) / FS
    return np.minimum(t / max(attack, 1e-4), 1.0) * np.exp(-t / decay)


def kick(n):
    t = np.arange(n) / FS
    f = 45 + 110 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / FS) * env(n, 0.001, 0.18)


def snare(n, rng):
    t = np.arange(n) / FS
    tone = np.sin(2 * np.pi * 185 * t) * env(n, 0.001, 0.05)
    noise = signal.lfilter(*signal.butter(2, [1500, 9000], "band", fs=FS), rng.standard_normal(n))
    return 0.5 * tone + 0.9 * noise * env(n, 0.001, 0.09)


def hat(n, rng):
    noise = signal.lfilter(*signal.butter(2, 7000, "high", fs=FS), rng.standard_normal(n))
    return 0.35 * noise * env(n, 0.0005, 0.025)


def clap(n, rng):
    x = np.zeros(n)
    noise = signal.lfilter(*signal.butter(2, [900, 5000], "band", fs=FS), rng.standard_normal(n))
    for k, dt in enumerate([0.0, 0.011, 0.022, 0.031]):
        i = int(dt * FS)
        e = env(n - i, 0.0003, 0.008 if k < 3 else 0.12)
        x[i:] += noise[i:] * e
    return x


def saw(freq, n):
    t = np.arange(n) / FS
    # band-limited by summing harmonics under 16 kHz
    y = np.zeros(n)
    for h in range(1, int(16000 / freq) + 1):
        y += np.sin(2 * np.pi * h * freq * t) / h
    return y


def norm(x, peak_db=-6.0):
    return x / np.max(np.abs(x)) * 10 ** (peak_db / 20)


def make_signals():
    rng = np.random.default_rng(7)
    sig = {}
    imp = np.zeros(FS * 24)
    imp[0] = 1.0
    sig["impulse"] = imp

    x = np.zeros(FS * 6)
    x[: FS] += clap(FS, rng)
    sig["clap"] = norm(x)

    # 2 bars at 110 BPM: kick 1 / 3, snare 2 / 4, eighth hats, then a tail.
    beat = 60.0 / 110
    x = np.zeros(int(FS * (8 * beat + 6)))
    for b in range(8):
        i = int(b * beat * FS)
        n = int(0.5 * FS)
        if b % 2 == 0:
            x[i:i + n] += kick(n)
        else:
            x[i:i + n] += snare(n, rng)
        for h in (0, 0.5):
            j = int((b + h) * beat * FS)
            x[j:j + n] += hat(n, rng)
    sig["drums"] = norm(x)

    # C minor stabs: short, then a held one.
    x = np.zeros(FS * 9)
    chord = [261.63, 311.13, 392.0]
    for k, (start, dur) in enumerate([(0.0, 0.18), (0.6, 0.18), (1.2, 1.0)]):
        n = int(dur * FS)
        y = sum(saw(f * (1 + 0.003 * (j - 1)), n) for j, f in enumerate(chord))
        y *= env(n, 0.004, dur * 3) * np.minimum(1.0, (n - np.arange(n)) / (0.01 * FS))
        i = int(start * FS)
        x[i:i + n] += y
    sig["stabs"] = norm(x)

    # Karplus-Strong plucked arpeggio (A minor).
    notes = [220.0, 261.63, 329.63, 440.0, 329.63, 261.63]
    x = np.zeros(FS * 8)
    for k, f in enumerate(notes):
        p = int(FS / f)
        n = int(0.9 * FS)
        buf = rng.uniform(-1, 1, p)
        y = np.zeros(n)
        for i in range(n):
            y[i] = buf[i % p]
            buf[i % p] = 0.996 * 0.5 * (buf[i % p] + buf[(i + 1) % p])
        i0 = int(k * 0.25 * FS)
        x[i0:i0 + n] += y
    sig["plucks"] = norm(x)

    # Worst case for level: a full-scale 4 s saw pad.
    n = 4 * FS
    y = sum(saw(f, n) for f in (130.81, 196.0, 261.63))
    y *= np.minimum(1.0, np.arange(n) / (0.2 * FS)) * np.minimum(1.0, (n - np.arange(n)) / (0.2 * FS))
    x = np.zeros(FS * 10)
    x[:n] = y
    sig["pad_fullscale"] = norm(x, -0.5)
    return sig


# ---------------------------------------------------------------- render

def render(tool, reverb, rt60, x):
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.f32"), os.path.join(d, "out.f32")
        x.astype(np.float32).tofile(src)
        res = subprocess.run([tool, reverb, str(rt60), src, dst], check=True, capture_output=True, text=True)
        y = np.fromfile(dst, dtype=np.float32).astype(np.float64)
    ns = float(res.stderr.split(":")[1].split("ns")[0])
    return y, ns


def write_wav(path, x):
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- metrics

OCTAVES = [125, 250, 500, 1000, 2000, 4000, 8000]


def edc_db(h):
    e = np.cumsum((h ** 2)[::-1])[::-1]
    return 10 * np.log10(e / e[0] + 1e-30)


def t30(h):
    """RT60 from the -5..-35 dB part of the Schroeder curve, and its fit r^2."""
    d = edc_db(h)
    i5 = np.argmax(d <= -5)
    i35 = np.argmax(d <= -35)
    if i35 <= i5:
        return float("nan"), float("nan")
    t = np.arange(i5, i35) / FS
    slope, icpt = np.polyfit(t, d[i5:i35], 1)
    fit = slope * t + icpt
    r2 = 1 - np.sum((d[i5:i35] - fit) ** 2) / np.sum((d[i5:i35] - d[i5:i35].mean()) ** 2)
    return -60.0 / slope, r2


def band(h, fc):
    lo, hi = fc / np.sqrt(2), min(fc * np.sqrt(2), FS / 2 * 0.95)
    sos = signal.butter(4, [lo, hi], "band", fs=FS, output="sos")
    return signal.sosfiltfilt(sos, h)


def echo_density(h, win_ms=20):
    """Abel-Huang normalised echo density (1 = Gaussian, i.e. fully dense)."""
    h = np.where(np.abs(h) < 1e-9, 0.0, h)  # the 1e-20 anti-denormal offset
    n = int(win_ms * FS / 1000)
    w = np.hanning(n)
    w /= w.sum()
    hop = n // 4
    out_t, out = [], []
    for i in range(0, len(h) - n, hop):
        seg = h[i:i + n]
        sd = np.sqrt(np.sum(w * seg ** 2))
        if sd <= 0:
            out_t.append((i + n / 2) / FS)
            out.append(0.0)
            continue
        out_t.append((i + n / 2) / FS)
        out.append(np.sum(w * (np.abs(seg) > sd)) / erfc(1 / np.sqrt(2)))
    return np.array(out_t), np.array(out)


def colouration(h, rt60):
    """Late-tail spectral roughness: decay-compensated 0.5..1.5 s spectrum,
    deviation (dB) from its 1/3-octave smoothed trend, 200 Hz..8 kHz.
    A dense, uncoloured tail is Rayleigh-like (~5.6 dB std); ringing modes
    show up as a heavier upper tail (95th percentile of the peaks)."""
    i0, i1 = int(0.5 * FS), int(1.5 * FS)
    seg = h[i0:i1] * np.exp(6.91 * np.arange(i1 - i0) / FS / rt60)
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + 1e-20
    f = np.fft.rfftfreq(len(seg), 1 / FS)
    db = 20 * np.log10(spec)
    sel = (f > 200) & (f < 8000)
    power = spec ** 2
    smooth = np.empty_like(db)
    for k, fk in enumerate(f):
        if not sel[k]:
            continue
        m = (f > fk / 2 ** (1 / 6)) & (f < fk * 2 ** (1 / 6))
        smooth[k] = 10 * np.log10(power[m].mean())
    dev = db[sel] - smooth[sel]
    return float(np.std(dev)), float(np.percentile(dev, 99)), f[sel], dev


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


# ---------------------------------------------------------------- plots

def style(ax, title, xlabel, ylabel):
    ax.set_title(title, color=TEXT, fontsize=11, loc="left")
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.tick_params(colors=MUTED)
    ax.grid(True, color=GRID, linewidth=0.8)
    for s in ax.spines.values():
        s.set_visible(False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "wav"), exist_ok=True)

    sig = make_signals()
    irs, ns = {}, {}
    lines = ["# fxrack reverb simulation (host render, models only)", ""]

    # Impulse responses and metrics.
    lines += ["## Impulse response", "",
              "| case | T30 125 | 250 | 500 | 1k | 2k | 4k | 8k Hz | EDC r^2 (1k) | dense (NED>=0.9) after first echo | tail roughness std / p99 dB | host ns/sample |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ned = {}
    col = {}
    for name, rev, rt in CASES:
        h, cost = render(args.render, rev, rt, sig["impulse"])
        irs[name], ns[name] = h, cost
        bands = []
        r2_1k = float("nan")
        for fc in OCTAVES:
            t, r2 = t30(band(h, fc))
            bands.append(t)
            if fc == 1000:
                r2_1k = r2
        tt, nd = echo_density(h)
        ned[name] = (tt, nd)
        start = np.argmax(np.abs(h) > 1e-6) / FS
        ok = (nd >= 0.9) & (tt > start)
        dense = tt[np.argmax(ok)] - start if np.any(ok) else float("nan")
        std, p99, f, dev = colouration(h, rt)
        col[name] = (f, dev)
        lines.append(f"| {name} | " + " | ".join(f"{b:.2f}" for b in bands) +
                     f" | {r2_1k:.4f} | {dense * 1000:.0f} ms | {std:.1f} / {p99:.1f} | {cost:.0f} |")
        print(name, [round(b, 2) for b in bands], f"r2 {r2_1k:.4f} dense {dense * 1000:.0f} ms col {std:.1f}/{p99:.1f}")

    # Program material.
    lines += ["", "## Program material (wet only, input peak -6 dBFS; pad -0.5 dBFS)", "",
              "| signal | case | wet RMS vs dry dB | wet peak | clipped samples at mix 0.4 / 1.0 |", "|---|---|---|---|---|"]
    for sname in ["clap", "drums", "stabs", "plucks", "pad_fullscale"]:
        x = sig[sname]
        for name, rev, rt in CASES:
            y, _ = render(args.render, rev, rt, x)
            t = tag(rev, rt)
            mix = 0.6 * x + 0.4 * y
            write_wav(os.path.join(args.out, "wav", f"{sname}_{t}.wav"), mix)
            write_wav(os.path.join(args.out, "wav", f"{sname}_{t}_wet.wav"), y)
            clip04 = int(np.sum(np.abs(mix) >= 1.0))
            clip10 = int(np.sum(np.abs(y) >= 1.0))
            lines.append(f"| {sname} | {name} | {rms_db(y[:len(x)]) - rms_db(x):+.1f} | {np.max(np.abs(y)):.2f} | {clip04} / {clip10} |")
        write_wav(os.path.join(args.out, "wav", f"{sname}_dry.wav"), x)

    with open(os.path.join(args.out, "metrics.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    # Energy decay curves (1 kHz band).
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    shades = {"hall 2 s": 0.45, "hall 4 s": 0.65, "hall 8 s": 0.85, "hall 20 s (max)": 1.0}
    for name, rev, rt in CASES:
        d = edc_db(band(irs[name], 1000))
        t = np.arange(len(d)) / FS
        alpha = 1.0 if rev == "classic" else shades[name]
        ax.plot(t, d, color=SERIES[rev], alpha=alpha, linewidth=2)
        k = np.argmax(d < -50) if np.any(d < -50) else len(d) - 1
        ax.annotate(name, (t[k], d[k]), color=TEXT, fontsize=8, xytext=(4, 0), textcoords="offset points")
    ax.set_ylim(-70, 2)
    ax.set_xlim(0, 24)
    style(ax, "Energy decay, 1 kHz octave (Schroeder integral)", "time (s)", "level (dB)")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "edc.png"))
    plt.close(fig)

    # Echo density.
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=120)
    for name in ["classic 3 s (old max)", "hall 4 s"]:
        tt, nd = ned[name]
        ax.plot(tt * 1000, nd, color=SERIES["classic" if "classic" in name else "hall"], linewidth=2, label=name)
    ax.axhline(1.0, color=MUTED, linewidth=1, linestyle="--")
    ax.set_xlim(0, 400)
    ax.legend(frameon=False, labelcolor=TEXT)
    style(ax, "Echo density (Abel-Huang, 20 ms window; 1 = fully dense)", "time (ms)", "normalised echo density")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "echo_density.png"))
    plt.close(fig)

    # IR spectrograms.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=120, sharey=True)
    for ax, name, dur in [(axes[0], "classic 3 s (old max)", 3.5), (axes[1], "hall 4 s", 5.0)]:
        h = irs[name][: int(dur * FS)]
        f, t, s = signal.spectrogram(h, FS, nperseg=2048, noverlap=1792, window="hann")
        sdb = 10 * np.log10(s + 1e-20)
        sdb -= sdb.max()
        im = ax.pcolormesh(t, f, sdb, vmin=-80, vmax=0, cmap="Blues", shading="auto")
        ax.set_yscale("symlog", linthresh=500)
        ax.set_ylim(50, 20000)
        style(ax, f"Impulse response spectrogram: {name}", "time (s)", "frequency (Hz)")
        ax.grid(False)
    fig.colorbar(im, ax=axes, label="dB")
    fig.savefig(os.path.join(args.out, "spectrogram.png"))
    plt.close(fig)

    # Tail colouration.
    fig, axes = plt.subplots(2, 1, figsize=(8, 5), dpi=120, sharex=True, sharey=True)
    for ax, name in [(axes[0], "classic 3 s (old max)"), (axes[1], "hall 4 s")]:
        f, dev = col[name]
        ax.plot(f, dev, color=SERIES["classic" if "classic" in name else "hall"], linewidth=0.6)
        ax.set_xscale("log")
        style(ax, f"Late-tail spectrum minus 1/3-oct trend: {name}", "frequency (Hz)" if ax is axes[1] else "", "dB")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "tail_spectrum.png"))
    plt.close(fig)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
