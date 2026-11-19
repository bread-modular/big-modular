#!/usr/bin/env python3
"""Long play + record run over USB for the Bread Modular 6x8 (Linux, ALSA).

Plays a sine on each of OUT 1-8 (half scale, 300 / 500 / 700 / 1100 / 1300 /
1700 / 1900 / 2300 Hz: whole cycles in every 10 ms) and records IN 1-6 at the
same time. Every 10 ms window of every input is fitted against the sine of the
output patched to it (found at the start); a click, a dropped or repeated
sample or a level change shows as a residual peak, a phase step or an
amplitude step. Every minute (--poll) it prints the window statistics and the
firmware's `status` counters.

  tools/longrun.py --minutes 60 --out ../research/longrun
"""
import argparse
import os
import queue
import re
import subprocess
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import console  # noqa: E402
import serial  # noqa: E402

RATE = 48000
WIN = 480                       # 10 ms
FREQS = [300, 500, 700, 1100, 1300, 1700, 1900, 2300]
AMP = 0.5                       # of full scale
N_OUT, N_IN = 8, 6
SKIP_S = 3.0                    # stream start: fill, fade-in, level settling

# Event thresholds per window (full scale = 1.0)
RES_PEAK = 5e-4                 # residual peak, -66 dBFS: a click / glitch (a lost sample: > -40 dBFS)
PHASE_DEG = 0.5                 # step of the fitted phase against the run's reference
AMP_REL = 2e-3                  # step of the fitted amplitude


def card_index():
    for line in open("/proc/asound/cards"):
        if "Bread Modular 6x8" in line:
            return int(line.split()[0])
    for line in open("/proc/asound/cards"):
        m = re.match(r"\s*(\d+)\s+\[B6x8", line)
        if m:
            return int(m.group(1))
    sys.exit("no Bread Modular 6x8 card")


def period_block():
    n = np.arange(WIN)
    x = np.zeros((WIN, N_OUT), dtype=np.int32)
    for o, f in enumerate(FREQS):
        s = np.round(AMP * (1 << 23) * np.sin(2 * np.pi * f * n / RATE)).astype(np.int32)
        x[:, o] = s << 8
    return x


def player(dev, stop, errs):
    blk = np.tile(period_block(), (100, 1)).tobytes()   # 1 s
    p = subprocess.Popen(["aplay", "-q", "-D", dev, "-t", "raw", "-f", "S32_LE", "-c", str(N_OUT),
                          "-r", str(RATE), "--buffer-time=40000", "--period-time=10000"],
                         stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    threading.Thread(target=lambda: [errs.append(("aplay", time.time(), l.decode().strip()))
                                     for l in p.stderr], daemon=True).start()
    try:
        while not stop.is_set():
            p.stdin.write(blk)
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass
        p.terminate()


class Analyzer:
    def __init__(self):
        n = np.arange(WIN)
        self.basis = {}
        for f in FREQS:
            b = np.stack([np.sin(2 * np.pi * f * n / RATE), np.cos(2 * np.pi * f * n / RATE), np.ones(WIN)], 1)
            self.basis[f] = (b, np.linalg.pinv(b))
        self.src = None             # output index per input
        self.ref_amp = None
        self.ref_ph = None
        self.events = []
        self.reset_minute()
        self.windows = 0
        self.res_rms_sum = np.zeros(N_IN)    # windows without an event only
        self.res_n = np.zeros(N_IN)
        self.amp_hist, self.dc_hist = [], []
        self.rebases = 0

    def reset_minute(self):
        self.m_windows = 0
        self.m_res_peak = np.zeros(N_IN)
        self.m_res_sq = np.zeros(N_IN)
        self.m_events = 0

    def find_sources(self, x):
        """Which output's frequency dominates each input."""
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))[:, None], axis=0))
        freqs = np.fft.rfftfreq(len(x), 1 / RATE)
        src = []
        for i in range(N_IN):
            mags = [spec[np.argmin(np.abs(freqs - f)), i] for f in FREQS]
            src.append(int(np.argmax(mags)))
        return src

    def feed(self, x, t_sec):
        """x: (k * WIN, 6) float, full scale 1.0; t_sec: time of its first sample."""
        nwin = len(x) // WIN
        xs = x[: nwin * WIN].reshape(nwin, WIN, N_IN)
        amps = np.zeros((nwin, N_IN))
        phs = np.zeros((nwin, N_IN))
        dcs = np.zeros((nwin, N_IN))
        peaks = np.zeros((nwin, N_IN))
        rms = np.zeros((nwin, N_IN))
        for i in range(N_IN):
            b, pinv = self.basis[FREQS[self.src[i]]]
            y = xs[:, :, i].T                      # (WIN, nwin)
            c = pinv @ y                           # (3, nwin)
            r = y - b @ c
            amps[:, i] = np.hypot(c[0], c[1])
            phs[:, i] = np.degrees(np.arctan2(c[1], c[0]))
            dcs[:, i] = c[2]
            peaks[:, i] = np.abs(r).max(0)
            rms[:, i] = np.sqrt((r ** 2).mean(0))
        if self.ref_amp is None:
            self.ref_amp = np.median(amps, 0)
            self.ref_ph = np.median(phs, 0)
        dph = (phs - self.ref_ph + 180) % 360 - 180
        damp = amps / self.ref_amp - 1
        bad = (peaks > RES_PEAK) | (np.abs(dph) > PHASE_DEG) | (np.abs(damp) > AMP_REL)
        for w, i in zip(*np.nonzero(bad)):
            self.events.append((t_sec + w * WIN / RATE, i, peaks[w, i], dph[w, i], damp[w, i]))
            self.m_events += 1
        self.windows += nwin
        self.m_windows += nwin
        self.m_res_peak = np.maximum(self.m_res_peak, peaks.max(0))
        self.m_res_sq += (rms ** 2).sum(0)
        self.res_rms_sum += np.where(bad, 0, rms ** 2).sum(0)
        self.res_n += (~bad).sum(0)
        self.amp_hist.append(amps.mean(0))
        self.dc_hist.append(dcs.mean(0))
        # A lasting step (a dropped or repeated sample) moves the reference, so
        # it is counted for this chunk only.
        med_ph = np.median(dph, 0)
        moved = np.abs(med_ph) > PHASE_DEG
        if moved.any():
            self.ref_ph = np.where(moved, np.median(phs, 0), self.ref_ph)
            self.rebases += int(moved.sum())
        return bad.any()


def db(v):
    return 20 * np.log10(max(v, 1e-12))


def status_counters(con):
    """con: a port name (opened and closed for this call) or an open serial.Serial."""
    try:
        r = console.run(con, ["status"], wait=3)[0] if isinstance(con, str) else console.talk(con, "status", wait=3)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}, ""
    keys = {
        "out_udr": r"OUT underruns (\d+)", "out_ovr": r"OUT underruns \d+ overruns (\d+)",
        "in_udr": r"IN underruns (\d+)", "in_ovr": r"IN underruns \d+ overruns (\d+)",
        "tdm": r"TDM ovr (\d+ udr \d+ slip \d+ stall \d+ late \d+)", "restarts": r"restarts (\d+)",
        "missed": r"since the reset: missed (OUT \d+, IN \d+, feedback \d+)",
        "delay": r"processing delay: worst (\d+) us", "over100": r"over 100 us (\d+)",
        "dcd": r"capture overflows (\d+), iso waits timed out (\d+)", "up": r"up (\d+) s",
        "worker": r"worker: (.*)\n", "vbus": r"VBUS dips (\d+) .*unplugs (\d+)",
        "out_buf": r"OUT:\s+(\w+), buffer (\d+) frames \((\d+)\.\.(\d+)", "fb": r"feedback ([\d.]+)",
        "in_buf": r"IN:\s+(\w+), buffer (\d+) frames \((\d+)\.\.(\d+)", "pk": r"packets ([\d.]+)",
    }
    out = {}
    for k, p in keys.items():
        m = re.search(p, r)
        out[k] = m.groups() if m and len(m.groups()) > 1 else (m.group(1) if m else None)
    return out, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "../../research/longrun"))
    ap.add_argument("--port")
    ap.add_argument("--poll", type=float, default=60, help="seconds between the firmware status reads")
    ap.add_argument("--keep-open", action="store_true",
                    help="keep the console port open for the whole run instead of opening it for each read")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    port = a.port or console.find_port()
    dev = f"hw:{card_index()},0"
    log = open(os.path.join(a.out, "longrun.log"), "a")

    def say(s):
        line = time.strftime("%H:%M:%S ") + s
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    con = port
    if a.keep_open:
        con = serial.Serial(port, 115200, timeout=0.05)
        time.sleep(0.2)
        con.reset_input_buffer()
    _, st0 = status_counters(con)
    say(f"start: {dev}, {a.minutes} min, OUT 1-8 sines {FREQS} Hz at {AMP} FS")
    log.write(st0 + "\n")

    stop = threading.Event()
    errs = []
    rec = subprocess.Popen(["arecord", "-q", "-D", dev, "-t", "raw", "-f", "S32_LE", "-c", str(N_IN),
                            "-r", str(RATE), "--buffer-time=40000", "--period-time=10000"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    threading.Thread(target=lambda: [errs.append(("arecord", time.time(), l.decode().strip()))
                                     for l in rec.stderr], daemon=True).start()
    pt = threading.Thread(target=player, args=(dev, stop, errs), daemon=True)
    pt.start()

    an = Analyzer()
    chunk_bytes = RATE * N_IN * 4          # 1 s
    # arecord's buffer is 40 ms: read it in its own thread, analyse and talk to
    # the console in this one.
    chunks = queue.Queue()

    def reader():
        while True:
            raw = rec.stdout.read(chunk_bytes)
            chunks.put(raw)
            if len(raw) < chunk_bytes:
                return

    threading.Thread(target=reader, daemon=True).start()
    t_start = time.time()
    t_audio = 0.0                          # seconds of recording read
    next_min = t_start + a.poll
    saved = 0
    try:
        while time.time() - t_start < a.minutes * 60:
            raw = chunks.get()
            if len(raw) < chunk_bytes:
                say("arecord stopped")
                break
            x = (np.frombuffer(raw, dtype="<i4").reshape(-1, N_IN) >> 8).astype(np.float64) / (1 << 23)
            t0 = t_audio
            t_audio += len(x) / RATE
            if t_audio <= SKIP_S:
                continue
            if an.src is None:
                an.src = an.find_sources(x)
                say("patch found: " + ", ".join(f"IN{i + 1} <- OUT{o + 1}" for i, o in enumerate(an.src)))
            if an.feed(x, t0) and saved < 20:
                np.save(os.path.join(a.out, f"event_{t0:08.1f}s.npy"), x.astype(np.float32))
                saved += 1
            if time.time() >= next_min:
                next_min += a.poll
                c, _ = status_counters(con)
                n = max(an.m_windows, 1)
                say(f"{t_audio / 60:5.1f} min: windows {an.windows}, events since the last {an.m_events}, total "
                    f"{len(an.events)}, phase steps {an.rebases}; residual rms dBFS " +
                    " ".join(f"{db(np.sqrt(an.m_res_sq[i] / n)):.0f}" for i in range(N_IN)) +
                    "; peak " + " ".join(f"{db(an.m_res_peak[i]):.0f}" for i in range(N_IN)))
                say(f"           fw: OUT udr/ovr {c.get('out_udr')}/{c.get('out_ovr')}, IN udr/ovr "
                    f"{c.get('in_udr')}/{c.get('in_ovr')}, TDM ovr {c.get('tdm')}, restarts {c.get('restarts')}, "
                    f"missed {c.get('missed')}, worst delay {c.get('delay')} us (>100: {c.get('over100')}), "
                    f"OUT buf {c.get('out_buf')} fb {c.get('fb')}, IN buf {c.get('in_buf')} pk {c.get('pk')}, "
                    f"VBUS dips/unplugs {c.get('vbus')}, up {c.get('up')} s; host errors {len(errs)}")
                say(f"           worker: {c.get('worker')}")
                an.reset_minute()
    except KeyboardInterrupt:
        say("interrupted")
    finally:
        stop.set()
        rec.terminate()
        pt.join(timeout=3)

    c, st1 = status_counters(con)
    log.write(st1 + "\n")
    n = max(an.windows, 1)
    say(f"done: {t_audio / 60:.1f} min recorded, {an.windows} windows x {N_IN} inputs, {len(an.events)} events, "
        f"host errors {len(errs)}")
    if an.src is not None:
        amps = np.mean(an.amp_hist, 0)
        dcs = np.mean(an.dc_hist, 0)
        for i in range(N_IN):
            say(f"  IN{i + 1} <- OUT{an.src[i] + 1} ({FREQS[an.src[i]]} Hz): gain {amps[i] / AMP:.5f}, "
                f"DC {dcs[i] * 5.87 * 1000:+.2f} mV, residual (THD+N) {db(np.sqrt(an.res_rms_sum[i] / max(an.res_n[i], 1)) / (AMP / np.sqrt(2))):.1f} dB (windows without an event)")
    for e in an.events[:50]:
        say(f"  event at {e[0]:.3f} s IN{e[1] + 1}: residual peak {db(e[2]):.0f} dBFS, phase {e[3]:+.2f} deg, "
            f"amplitude {e[4] * 100:+.3f} %")
    for e in errs[:20]:
        say(f"  host {e[0]}: {e[2]}")
    say("firmware at the end: " + str(c))


if __name__ == "__main__":
    main()
