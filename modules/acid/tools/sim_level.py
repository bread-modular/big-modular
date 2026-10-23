"""ACID output-level simulation (no SPICE on this host): Bread Modular SVF -> LP / HP / BP outs.

Run from modules/acid:  python3 -B tools/sim_level.py

Time-domain model (forward Euler, 192 kHz x 4 oversampled) of the circuit in docs/research.md 3.4:
- Sources: the MCO square mix (one or two 3.3 V squares into the BM MCO summer, each x0.4
  around V_MID) or a 10 Vpp square on the AUDIO bypass (x0.33, clipped at the rails).
- BM SVF: summer U5A (R24 51k in, R26-R28 10k), integrators U5B / U6A (vactrol LDR R + 10n),
  damping U6B gain 51k / (51k + RES), RES 0..500k. Each MCP6002 output clips at 0.02..3.28 V.
- Each output stage: AC coupled, TL072 x22.3 clipping at ~+/-10.3 V, then 1k / 1k: x11.1.
  For comparison 'x3' is the modules/low stage (no extra gain).
Prints the SVF and OUT peak-to-peak voltages for LP / BP / HP over cutoff and RES.
"""
import numpy as np

VDD, VMID = 3.3, 1.65
FS = 192000 * 4
DUR = 0.2
G_OUT = 1 + 100 / 4.7
CLIP = 10.3


def rail(v):
    return min(max(v, 0.02), VDD - 0.02)


def source(t, kind):
    sq = lambda f: np.where((t * f) % 1 < 0.5, VDD, 0.0)
    if kind == 'two tones':
        v = VMID - 0.4 * (sq(110) - VMID) - 0.4 * (sq(110 * 1.4983) - VMID)
    elif kind == 'one tone':
        v = VMID - 0.4 * (sq(110) - VMID)
    else:  # 10 Vpp square on AUDIO
        v = VMID - 0.33 * 5 * np.sign(np.sin(2 * np.pi * 110 * t))
    return np.clip(v, 0.02, VDD - 0.02)


def svf(vin, r_ldr, res, c=10e-9):
    g = 51e3 / (51e3 + res)
    k = 1 / (FS * r_ldr * c)
    bp = lp = VMID
    hp_o, bp_o, lp_o = (np.empty_like(vin) for _ in range(3))
    for i, x in enumerate(vin):
        hp = rail(VMID - (10 / 51) * (x - VMID) - (lp - VMID) + g * (bp - VMID))
        bp = rail(bp - k * (hp - VMID))      # U5B inverting integrator
        lp = rail(lp - k * (bp - VMID))      # U6A inverting integrator
        hp_o[i], bp_o[i], lp_o[i] = hp, bp, lp
    return lp_o, bp_o, hp_o


def out_pp(v, gain, div):
    s = v[len(v) // 2:]
    return np.ptp(np.clip(gain * (s - s.mean()), -CLIP, CLIP) * div)


if __name__ == '__main__':
    t = np.arange(int(DUR * FS)) / FS
    for kind in ('two tones', 'one tone', '10 Vpp AUDIO'):
        print(f'== {kind}: LDR R, fc, RES | SVF LP/BP/HP Vpp | OUT x11.1 LP/BP/HP | x3 LP/BP/HP')
        for r_ldr in (100e3, 10e3, 3e3):
            for res in (0, 100e3, 250e3, 500e3):
                outs = svf(source(t, kind), r_ldr, res)
                svf_pp = '/'.join(f'{np.ptp(v[len(v) // 2:]):.2f}' for v in outs)
                acid = '/'.join(f'{out_pp(v, G_OUT, 0.5):.1f}' for v in outs)
                low = '/'.join(f'{out_pp(v, 3, 1):.1f}' for v in outs)
                print(f'{r_ldr / 1e3:4.0f}k {1 / (2 * np.pi * r_ldr * 10e-9):5.0f} Hz {res / 1e3:4.0f}k | '
                      f'{svf_pp} | {acid} | {low}')
