#!/usr/bin/env python3
"""Synthetic kick + mix loop through the master chain (host render of the firmware C).

Writes kick.wav / mix.wav (the two inputs), bypass.wav (kick + mix), master.wav
(factory settings), stage renders, a plot and metrics.md to --out. Models only: the
loop is synthetic and nothing here was heard on the module.
"""
import argparse
import os
import subprocess
import wave

import numpy as np

FS = 44100
BPM = 128


def write_wav(path, x):
    q = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(q.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        assert w.getsampwidth() == 3 and w.getnchannels() == 1
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
    v = np.where(v >= 1 << 23, v - (1 << 24), v)
    return v / 8388608.0


def one_pole_lp(x, f):
    a = 1.0 - np.exp(-2 * np.pi * f / FS)
    y = np.empty_like(x)
    s = 0.0
    for i, v in enumerate(x):
        s += a * (v - s)
        y[i] = s
    return y


def make_loop(bars=4):
    rng = np.random.default_rng(7)
    beat = int(FS * 60 / BPM)
    n = beat * 4 * bars
    t = np.arange(n) / FS
    kick = np.zeros(n)
    kt = np.arange(int(0.35 * FS)) / FS
    # 808 / 909-like kick: pitch sweep 160 -> 48 Hz, 180 ms body, click, some 20 Hz rumble under it
    phase = 2 * np.pi * (48 * kt + (160 - 48) * 0.025 * (1 - np.exp(-kt / 0.025)))
    one = np.sin(phase) * np.exp(-kt / 0.11) + 0.25 * rng.standard_normal(len(kt)) * np.exp(-kt / 0.002)
    one += 0.15 * np.sin(2 * np.pi * 18 * kt) * np.exp(-kt / 0.2)
    for b in range(4 * bars):
        seg = kick[b * beat : b * beat + len(one)]
        seg += one[: len(seg)]
    kick *= 0.8 / np.max(np.abs(kick))

    # Bass: sustained 55 Hz saw through a low pass, playing right through the kicks
    saw = 2 * ((55 * t) % 1.0) - 1
    bass = one_pole_lp(one_pole_lp(saw, 300), 300) * 0.5
    # Pad: three detuned saws, mid range
    pad = sum(2 * ((f * t) % 1.0) - 1 for f in (220.0, 277.2, 329.6, 221.1)) * 0.06
    pad = one_pole_lp(pad, 2500)
    # Hats: noise bursts on the off-beat 8ths and 16ths
    hats = np.zeros(n)
    step = beat // 4
    for s in range(16 * bars):
        if s % 4 == 0:
            continue
        ln = int(0.03 * FS) if s % 4 != 2 else int(0.09 * FS)
        burst = rng.standard_normal(ln) * np.exp(-np.arange(ln) / (ln / 4))
        hats[s * step : s * step + ln] += burst[: n - s * step] * (0.12 if s % 4 != 2 else 0.2)
    hats = hats - one_pole_lp(hats, 6000)
    mix = bass + pad + hats
    mix *= 0.6 / np.max(np.abs(mix))
    return kick, mix, beat


def band_env(x, lo, hi, win=0.01):
    """Envelope of a band (FFT brick filter + RMS over `win`)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / FS)
    spec[(f < lo) | (f >= hi)] = 0
    y = np.fft.irfft(spec, len(x))
    w = int(win * FS)
    return np.sqrt(np.convolve(y * y, np.ones(w) / w, mode="same") + 1e-12)


def db(v):
    return 20 * np.log10(np.maximum(v, 1e-9))


def lufs_ish(x):
    """RMS in dB after a rough K-weighting (high shelf + 38 Hz high pass), not a calibrated LUFS."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / FS)
    shelf = 1 + (10 ** (4 / 20) - 1) / (1 + (1500 / np.maximum(f, 1)) ** 2)
    hp = 1 / np.sqrt(1 + (38 / np.maximum(f, 1)) ** 4)
    y = np.fft.irfft(spec * shelf * hp, len(x))
    return db(np.sqrt(np.mean(y * y)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    kick, mix, beat = make_loop()
    kp, mp = os.path.join(args.out, "kick.wav"), os.path.join(args.out, "mix.wav")
    write_wav(kp, kick)
    write_wav(mp, mix)

    off = ["k_flt_on", "k_lim_on", "m_flt_on", "mb_on", "par_on", "glue_on", "o_flt_on", "lim_on"]

    def render(name, settings):
        sp = os.path.join(args.out, name + ".txt")
        with open(sp, "w") as f:
            f.write("".join("set %s %s\n" % kv for kv in settings.items()))
        op = os.path.join(args.out, name + ".wav")
        res = subprocess.run([args.render, "-s", sp, kp, mp, op], check=True, capture_output=True, text=True)
        return read_wav(op), res.stdout

    def only(*keep, **extra):
        s = {k: 0 for k in off if k not in keep}
        s.update(extra)
        return s

    runs = {
        "bypass": {"bypass": 1},
        "master": {},
        "only-filters": only("k_flt_on", "m_flt_on", "o_flt_on"),
        "only-multiband": only("mb_on"),
        "mix-alone": only(k_lvl=-60),
        "mix-alone-multiband": only("mb_on", k_lvl=-60),
        "only-parallel": only("par_on"),
        "only-glue": only("glue_on"),
        "only-limiters": only("k_lim_on", "lim_on"),
    }
    out = {}
    log = {}
    for name, settings in runs.items():
        out[name], log[name] = render(name, settings)

    lines = ["# master chain, synthetic %d BPM loop (host render, factory settings)\n" % BPM, ""]
    lines.append("| render | peak dB | RMS dB | weighted RMS dB | crest dB |")
    lines.append("|---|---|---|---|---|")
    for name, x in out.items():
        pk, r = db(np.max(np.abs(x))), db(np.sqrt(np.mean(x * x)))
        lines.append("| %s | %.2f | %.2f | %.2f | %.1f |" % (name, pk, r, lufs_ish(x), pk - r))
    lines.append("")
    # Ducking, heard on the mix alone (kick level off, the kick still keys the bands)
    x = out["mix-alone-multiband"]
    ref = out["mix-alone"]
    for label, lo, hi in (("low < 120 Hz", 20, 120), ("mid 120 Hz .. 2.5 kHz", 120, 2500), ("high > 2.5 kHz", 2500, 20000)):
        e, e0 = band_env(x, lo, hi), band_env(ref, lo, hi)
        hit, late = [], []
        for b in range(2, 14):
            a = b * beat
            hit.append(np.mean(db(e[a + 500 : a + 3000]) - db(e0[a + 500 : a + 3000])))
            late.append(np.mean(db(e[a + beat - 3000 : a + beat - 500]) - db(e0[a + beat - 3000 : a + beat - 500])))
        lines.append("- mix alone, %s: %.1f dB 11..68 ms after a kick, %.1f dB before the next"
                     % (label, np.mean(hit), np.mean(late)))
    lines.append("")
    for name in runs:
        lines.append("## %s\n\n```\n%s```\n" % (name, log[name]))
    with open(os.path.join(args.out, "metrics.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:16]))

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing: no plot")
        return
    fig, ax = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    sl = slice(4 * beat, 8 * beat)
    t = np.arange(sl.stop - sl.start) / FS
    ax[0].plot(t, kick[sl], lw=0.5, label="kick in")
    ax[0].plot(t, mix[sl], lw=0.5, label="mix in")
    ax[0].set_title("inputs (one bar)")
    ax[1].plot(t, out["bypass"][sl], lw=0.5, label="bypass (kick + mix)")
    ax[1].plot(t, out["master"][sl], lw=0.5, label="master, factory settings")
    ax[1].set_title("output")
    for name in ("mix-alone", "mix-alone-multiband"):
        ax[2].plot(t, db(band_env(out[name], 20, 120)[sl]), label=name + ", below 120 Hz")
        ax[2].plot(t, db(band_env(out[name], 120, 2500)[sl]), label=name + ", 120 Hz .. 2.5 kHz", ls="--")
    ax[2].set_title("mix without the kick: band levels (dB)")
    for name in ("bypass", "only-parallel", "only-glue", "master"):
        ax[3].plot(t, db(band_env(out[name], 20, 20000, 0.02)[sl]), label=name)
    ax[3].set_title("level, 20 ms RMS (dB)")
    ax[3].set_xlabel("s")
    for a in ax:
        a.legend(loc="upper right", fontsize=8)
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "master-demo.png"), dpi=110)


if __name__ == "__main__":
    main()
