#!/usr/bin/env python3
"""Measures the glue compressor on test signals (host render of the firmware C).

Renders tone steps, bursts, steady tones and the demo loop through ms_render with
only the glue on, and writes glue.png + glue.md to --out. With --old (an ms_render
built from another version of the firmware) the same signals go through that one
too, for a comparison. Models only: nothing here was heard on the module.
"""
import argparse
import os
import subprocess
import wave

import numpy as np

from demo import FS, db, make_loop, read_wav

OFF = ["k_hp_on", "k_lim_on", "m_hp_on", "mb_on", "par_on", "eq_lo_on", "eq_hi_on", "lim_on"]
ATTACK = [0.01, 0.1, 0.3, 1, 3, 10, 30]  # ms, the glue_att choices
RELEASE = [0.1, 0.2, 0.4, 0.6, 0.8, 1.2, "A"]  # s, the glue_rel choices
RATIO = [2, 4, 10]


def write_wav24(path, x):
    q = np.clip(np.round(x * 8388607.0), -8388608, 8388607).astype("<i4")
    raw = q.astype("<i4").tobytes()
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 4)[:, :3]
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(3)
        w.setframerate(FS)
        w.writeframes(b.tobytes())


class Bench:
    def __init__(self, render, out, tag):
        self.render, self.out, self.tag = render, out, tag
        self.count = 0
        self.silence = os.path.join(out, "silence.wav")
        write_wav24(self.silence, np.zeros(64))

    def run(self, x, kick=None, name=None, **glue):
        """x on the mix input (kick: optional kick input); glue settings by short name."""
        self.count += 1
        base = os.path.join(self.out, name or "tmp-%s" % self.tag)
        settings = {k: 0 for k in OFF}
        settings.update(glue_on=1, k_lvl=0, m_lvl=0)
        settings.update({"glue_" + k: v for k, v in glue.items()})
        with open(base + ".txt", "w") as f:
            f.write("".join("set %s %s\n" % kv for kv in settings.items()))
        write_wav24(base + "-in.wav", x)
        kp = self.silence
        if kick is not None:
            kp = base + "-kick.wav"
            write_wav24(kp, kick)
        subprocess.run([self.render, "-s", base + ".txt", kp, base + "-in.wav", base + ".wav"], check=True,
                       capture_output=True)
        y = read_wav(base + ".wav")[: len(x)]
        if name is None:
            for ext in (".txt", "-in.wav", ".wav"):
                os.remove(base + ext)
        return y


def tone(freq, amps_and_seconds):
    parts = [np.full(int(sec * FS), amp) for amp, sec in amps_and_seconds]
    env = np.concatenate(parts)
    return env * np.sin(2 * np.pi * freq * np.arange(len(env)) / FS)


def envelope(x, freq):
    """Amplitude of a tone at `freq`: quadrature demodulation, averaged over two periods."""
    t = np.arange(len(x)) / FS
    z = x * np.exp(-2j * np.pi * freq * t)
    w = int(round(2 * FS / freq))
    return 2 * np.abs(np.convolve(z, np.ones(w) / w, mode="same"))


def reduction(bench, x, freq, **glue):
    """Gain of the glue over time in dB for a tone signal."""
    y = bench.run(x, **glue)
    return db(envelope(y, freq)) - db(np.maximum(envelope(x, freq), 1e-9))


def harmonics(x, freq, count=9):
    """Harmonic amplitudes relative to the fundamental, from the last second (whole periods for a whole Hz)."""
    n = FS
    seg = x[len(x) - n :]
    t = np.arange(len(x) - n, len(x)) / FS
    amp = [2 * abs(np.mean(seg * np.exp(-2j * np.pi * freq * h * t))) for h in range(1, count + 1)]
    return np.array(amp[1:]) / amp[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--old", help="ms_render of another firmware version, for a comparison")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    new = Bench(args.render, args.out, "new")
    old = Bench(args.old, args.out, "old") if args.old else None
    both = [("this firmware", new)] + ([("--old", old)] if old else [])
    lines = ["# glue compressor, host render of the firmware C", ""]

    # 1. Static curve: 1 kHz in 2 dB steps, each long enough to settle.
    levels = np.arange(-40, 1, 2.0)
    step = 0.6
    x = tone(1000, [(10 ** (lv / 20), step) for lv in levels])
    curve = {}
    for label, b in both:
        for r in range(3):
            y = b.run(x, thr=-20, ratio=r, att=3, rel=1)
            out = []
            for i in range(len(levels)):
                seg = y[int((i + 0.6) * step * FS) : int((i + 1) * step * FS)]
                out.append(db(np.sqrt(2 * np.mean(seg * seg))))
            curve[label, r] = np.array(out)
    lines += ["## Curve (threshold -20 dB, attack 1 ms, release 0.2 s, 1 kHz)", "",
              "| input dB | " + " | ".join("%d:1" % r for r in RATIO) + " |", "|---|---|---|---|"]
    for i, lv in enumerate(levels):
        if lv >= -30 and lv % 4 == 0:
            lines.append("| %d | " % lv + " | ".join("%.2f" % curve["this firmware", r][i] for r in range(3)) + " |")
    lines.append("")

    # 2. Attack and release on a 5 kHz burst, 24 dB up and down.
    burst = [(0.0316, 0.2), (0.5, 0.5), (0.0316, 2.0)]
    xb = tone(5000, burst)
    t0 = int(0.2 * FS)
    t1 = int(0.7 * FS)
    att_curves = {a: reduction(new, xb, 5000, thr=-26, ratio=1, att=a, rel=2) for a in (1, 3, 5, 6)}
    ratio_curves = {r: reduction(new, xb, 5000, thr=-26, ratio=r, att=5, rel=2) for r in range(3)}
    rel_curves = {r: reduction(new, xb, 5000, thr=-26, ratio=1, att=3, rel=r) for r in (0, 2, 5, 6)}
    old_att = reduction(old, xb, 5000, thr=-26, ratio=1, att=5, rel=2) if old else None

    def time_to(g, start, frac, rising):
        ref = g[t1 - 200] if rising else g[t1 - 200]
        seg = g[start:]
        hit = np.nonzero(seg <= frac * ref)[0] if rising else np.nonzero(seg >= frac * ref)[0]
        return 1000.0 * hit[0] / FS if len(hit) else float("nan")

    lines += ["## Timing (5 kHz burst 20 dB over the threshold, 4:1 unless said)", "",
              "| setting | reduction held | 63 % of it after | back to 37 % after |", "|---|---|---|---|"]
    for a, g in att_curves.items():
        lines.append("| attack %g ms, release 0.4 s | %.1f dB | %.2f ms | %.0f ms |"
                     % (ATTACK[a], -g[t1 - 200], time_to(g, t0, 0.632, True), time_to(g, t1, 0.368, False)))
    for r, g in ratio_curves.items():
        lines.append("| %d:1, attack 10 ms, release 0.4 s | %.1f dB | %.2f ms | %.0f ms |"
                     % (RATIO[r], -g[t1 - 200], time_to(g, t0, 0.632, True), time_to(g, t1, 0.368, False)))
    if old:
        lines.append("| --old, 4:1, attack 10 ms, release 0.4 s | %.1f dB | %.2f ms | %.0f ms |"
                     % (-old_att[t1 - 200], time_to(old_att, t0, 0.632, True), time_to(old_att, t1, 0.368, False)))
    lines.append("")

    # 3. Release A after loud passages of different lengths.
    auto = {}
    for label, b in both:
        for sec in (0.02, 0.2, 2.0, 8.0):
            xa = tone(5000, [(0.0316, 0.1), (0.5, sec), (0.0316, 6.0)])
            g = reduction(b, xa, 5000, thr=-26, ratio=1, att=3, rel=6)
            end = int((0.1 + sec) * FS)
            auto[label, sec] = g[end - 200 :]
    lines += ["## Release A (4:1, attack 1 ms): reduction left after the loud part ends", "",
              "| loud for | at the end | 0.1 s later | 0.5 s | 2 s | 5 s |", "|---|---|---|---|---|---|"]
    for (label, sec), g in auto.items():
        at = [g[200 + int(s * FS)] for s in (0, 0.1, 0.5, 2, 5)]
        lines.append("| %s, %g s | " % (label, sec) + " | ".join("%.1f dB" % -v for v in at) + " |")
    lines.append("")

    # 4. Harmonics of steady tones.
    lines += ["## Harmonics (steady tone at -6 dB)", "",
              "| signal | reduction | H2 | H3 | H4 | H5 |", "|---|---|---|---|---|---|"]
    spectra = {}
    cases = [("1 kHz, no reduction", 1000, dict(thr=0)),
             ("1 kHz, 4:1, attack 10 ms, release A", 1000, dict(thr=-26, ratio=1, att=5, rel=6)),
             ("100 Hz, 4:1, attack 10 ms, release A", 100, dict(thr=-26, ratio=1, att=5, rel=6)),
             ("100 Hz, 4:1, attack 10 ms, release 0.1 s", 100, dict(thr=-26, ratio=1, att=5, rel=0)),
             ("50 Hz, 2:1, attack 10 ms, release A", 50, dict(thr=-16, ratio=0, att=5, rel=6))]
    for label, b in both:
        for name, f, glue in cases:
            xs = tone(f, [(0.5, 4.0)])
            y = b.run(xs, **glue)
            h = harmonics(y, f)
            gr = db(envelope(y, f)[-FS]) - db(0.5)
            spectra[label, name] = (f, y)
            lines.append("| %s: %s | %.1f dB | " % (label, name, -gr) + " | ".join("%.3f %%" % (100 * v) for v in h[:4])
                         + " |")
    lines.append("")

    # 5. The demo loop through the glue alone (factory glue settings), and pushed.
    kick, mix, beat = make_loop(bars=8)
    dry = kick + mix
    music = {}
    lines += ["## Demo loop, kick + mix into the glue alone", "",
              "| render | peak dB | RMS dB | crest dB | reduction mean / most dB |", "|---|---|---|---|---|"]
    w = int(0.005 * FS)
    env_dry = np.sqrt(np.convolve(dry * dry, np.ones(w) / w, mode="same") + 1e-12)
    for label, b in both:
        for name, glue in (("factory", {}), ("pushed (-20 dB, 4:1, attack 3 ms)", dict(thr=-20, ratio=1, att=4))):
            y = b.run(mix, kick=kick, name="loop-%s-%s" % (name.split()[0], b.tag), **glue)
            env = np.sqrt(np.convolve(y * y, np.ones(w) / w, mode="same") + 1e-12)
            g = db(env) - db(env_dry)
            g[env_dry < 0.01] = np.nan
            music[label, name] = (y, g)
            sl = slice(4 * 4 * beat, None)
            pk, r = db(np.max(np.abs(y[sl]))), db(np.sqrt(np.mean(y[sl] ** 2)))
            lines.append("| %s, %s | %.2f | %.2f | %.1f | %.1f / %.1f |"
                         % (label, name, pk, r, pk - r, -np.nanmean(g[sl]), -np.nanmin(g[sl])))
    sl = slice(4 * 4 * beat, None)
    lines.append("| dry | %.2f | %.2f | %.1f | |" % (db(np.max(np.abs(dry[sl]))), db(np.sqrt(np.mean(dry[sl] ** 2))),
                                                   db(np.max(np.abs(dry[sl]))) - db(np.sqrt(np.mean(dry[sl] ** 2)))))
    lines.append("")
    with open(os.path.join(args.out, "glue.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing: no plot")
        return
    fig, ax = plt.subplots(3, 2, figsize=(14, 13))
    a = ax[0][0]
    a.plot(levels, levels, color="0.7", lw=0.8, label="1:1")
    for r in range(3):
        a.plot(levels, curve["this firmware", r], marker=".", label="%d:1" % RATIO[r])
        if old:
            a.plot(levels, curve["--old", r], ls=":", color="C%d" % r, label="%d:1, --old" % RATIO[r])
    a.axvline(-20, color="0.7", lw=0.8)
    a.set_title("curve: 1 kHz, threshold -20 dB")
    a.set_xlabel("input dB")
    a.set_ylabel("output dB")

    a = ax[0][1]
    tt = (np.arange(len(xb)) - t0) / FS * 1000
    win = slice(t0 - int(0.005 * FS), t0 + int(0.08 * FS))
    for k, g in att_curves.items():
        a.plot(tt[win], g[win], label="4:1, attack %g ms" % ATTACK[k])
    for r in (0, 2):
        a.plot(tt[win], ratio_curves[r][win], ls="--", label="%d:1, attack 10 ms" % RATIO[r])
    if old:
        a.plot(tt[win], old_att[win], ls=":", color="k", label="--old, 4:1, attack 10 ms")
    a.set_title("attack: 5 kHz burst, 24 dB up (20 dB over the threshold)")
    a.set_xlabel("ms")
    a.set_ylabel("gain dB")

    a = ax[1][0]
    tr = (np.arange(len(xb)) - t1) / FS
    win = slice(t1 - int(0.05 * FS), t1 + int(1.8 * FS))
    for k, g in rel_curves.items():
        a.plot(tr[win], g[win], label="release %s%s" % (RELEASE[k], "" if k == 6 else " s"))
    a.set_title("release after 0.5 s of the burst (4:1, attack 1 ms)")
    a.set_xlabel("s")
    a.set_ylabel("gain dB")

    a = ax[1][1]
    for (label, sec), g in auto.items():
        ts = (np.arange(len(g)) - 200) / FS
        a.plot(ts, g, ls="-" if label == "this firmware" else ":", color="C%d" % [0.02, 0.2, 2.0, 8.0].index(sec),
               label="%s, loud for %g s" % (label, sec))
    a.set_xlim(-0.05, 5.5)
    a.set_title("release A after loud passages of different length")
    a.set_xlabel("s after the loud part")
    a.set_ylabel("gain dB")

    a = ax[2][0]
    for label, b in both:
        f, y = spectra[label, "100 Hz, 4:1, attack 10 ms, release A"]
        seg = y[-2 * FS :] * np.hanning(2 * FS)
        spec = db(np.abs(np.fft.rfft(seg)) / (FS / 2))
        a.plot(np.fft.rfftfreq(2 * FS, 1 / FS), spec - spec.max(), lw=0.7, label=label,
               ls="-" if label == "this firmware" else ":")
    a.set_xlim(0, 1200)
    a.set_ylim(-130, 5)
    a.set_title("100 Hz under 4:1 reduction (attack 10 ms, release A): spectrum, dB below the tone")
    a.set_xlabel("Hz")

    a = ax[2][1]
    bar = slice(4 * 4 * beat, 5 * 4 * beat)
    tm = np.arange(bar.stop - bar.start) / FS
    for (label, name), (y, g) in music.items():
        a.plot(tm, g[bar], lw=0.8, ls="-" if label == "this firmware" else ":", label="%s, %s" % (label, name))
    a.set_title("demo loop, one bar: gain of the glue alone (5 ms RMS of out / in)")
    a.set_xlabel("s")
    a.set_ylabel("gain dB")
    for row in ax:
        for a in row:
            a.legend(fontsize=7, loc="best")
            a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "glue.png"), dpi=100)


if __name__ == "__main__":
    main()
