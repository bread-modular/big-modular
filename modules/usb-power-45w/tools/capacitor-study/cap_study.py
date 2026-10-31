#!/usr/bin/env python3
"""usb-power-45w capacitor study (C5/C34/C35/C36 electrolytic vs MLCC banks).

RESEARCH SCREENING ONLY. Passive ladder networks plus an averaged constant-power
load and assumed converter current trajectories. It is NOT a closed-loop model of
TPS62933F / LMR38020F / TPS16630 / LM5067 (their compensators are internal and
are not invented here) and it is not manufacturing or bench qualification.

Every capacitor value is a bounded sensitivity: no exact Samsung/SamYoung DC-bias,
100 kHz ESR or aging curves were obtained for the fitted parts (see the note in
docs/capacitor-study/README.md). Change BOUNDS below and rerun.

Usage (repository root):
  python3 -B modules/usb-power-45w/tools/capacitor-study/cap_study.py --selftest
  python3 -B modules/usb-power-45w/tools/capacitor-study/cap_study.py \
      --out modules/usb-power-45w/docs/capacitor-study/generated
Only the Python standard library and numpy are used.
"""
import argparse
import itertools
import json
import math
import pathlib

import numpy as np

# --------------------------------------------------------------------------------------
# Capacitor bounds (engineering sensitivities, NOT manufacturer minima)
# --------------------------------------------------------------------------------------
# MLCC DC-bias retention bands. Anchor: TI SLUSEA4D 10.2.2.9 quotes a TDK 1206 10uF/50V
# X7R at 3.45 uF under 24 V (0.345). Others are typical X5R 1206 bands, to be replaced
# by Samsung component-library curves for CL31A226KAHNNNE / CL31A106KBHNNNE.
BIAS = {
    ('22u25V_1206', 5.0): (0.55, 0.80),
    ('22u25V_1206', 12.2): (0.30, 0.50),
    ('10u50V_1206', 20.0): (0.35, 0.60),
    ('10u50V_1206', 32.0): (0.20, 0.40),
}
MLCC_TOL, MLCC_TEMP_LO, MLCC_AGE_LO = 0.10, 0.85, 0.93   # +-10 %, X5R 0..70 C, ~10 kh aging
MLCC_ESR = 0.005                                          # ohm each, 100 kHz-2 MHz class
# SamYoung MVK, 105 C / 1000 h (JLC C350012 listing). 100 kHz ESR not published in the
# sources obtained: bracket from general-purpose tan-delta class, x2 for cold start.
CAN = {
    'C5': dict(c=47e-6, esr=(0.5, 2.0, 4.0)),          # (warm low, warm high, cold high)
    'C34_36': dict(c=100e-6, esr=(0.3, 1.5, 3.0)),
}
CAN_C_LO, CAN_C_HI = 0.8 * 0.85 * 0.85, 1.2          # tol x cold x end-of-life


def mlcc(n, nom_uF, key, v):
    lo_b, hi_b = BIAS[(key, v)]
    lo = n * nom_uF * 1e-6 * lo_b * (1 - MLCC_TOL) * MLCC_TEMP_LO * MLCC_AGE_LO
    hi = n * nom_uF * 1e-6 * hi_b * (1 + MLCC_TOL)
    return lo, hi, MLCC_ESR / n


# --------------------------------------------------------------------------------------
# Ladder network: [Vs] -series- node0 -series- node1 ... ; shunt R-C branches per node
# --------------------------------------------------------------------------------------
class Ladder:
    def __init__(self, nodes, series, source=True):
        """nodes: list of dicts {shunts: [(C, R)], g: conductance}.
        series: list of dicts {R, L, diode(bool), vf}; len == len(nodes) if source else len-1."""
        self.nodes, self.series, self.source = nodes, series, source
        self.ns = len(series)
        self.shunts = [(k, c, r) for k, n in enumerate(nodes) for (c, r) in n['shunts']]
        self.n = self.ns + len(self.shunts)

    def _node_v(self, x, vs, inj, g_override=None):
        i_ser = x[:self.ns]
        vc = x[self.ns:]
        num = np.zeros(len(self.nodes))
        den = np.zeros(len(self.nodes))
        for k, n in enumerate(self.nodes):
            den[k] += n.get('g', 0.0) if g_override is None else g_override[k]
            num[k] -= inj[k]
        for s in range(self.ns):
            prv = s - 1 if self.source else s
            nxt = s if self.source else s + 1
            num[nxt] += i_ser[s]
            if prv >= 0:
                num[prv] -= i_ser[s]
        for j, (k, c, r) in enumerate(self.shunts):
            num[k] += vc[j] / r
            den[k] += 1 / r
        return num, den

    def deriv(self, x, vs, inj, cpl=None):
        """cpl: (node, P) constant-power sink solved exactly at that node."""
        num, den = self._node_v(x, vs, inj)
        v = num / den
        if cpl is not None:
            k, p = cpl
            disc = num[k] ** 2 - 4 * den[k] * p
            v[k] = (num[k] + math.sqrt(max(disc, 0.0))) / (2 * den[k])
        dx = np.zeros(self.n)
        for s, br in enumerate(self.series):
            vp = (vs if s == 0 else v[s - 1]) if self.source else v[s]
            vn = v[s] if self.source else v[s + 1]
            di = (vp - vn - br['R'] * x[s] - br.get('vf', 0.0)) / br['L']
            if br.get('diode') and x[s] <= 0 and di < 0:
                di = 0.0
            dx[s] = di
        for j, (k, c, r) in enumerate(self.shunts):
            dx[self.ns + j] = (v[k] - x[self.ns + j]) / (r * c)
        return dx, v

    def linear(self, g):
        """State matrix with node conductances g (linearised CPL), inputs zero."""
        A = np.zeros((self.n, self.n))
        z = np.zeros(len(self.nodes))
        for i in range(self.n):
            e = np.zeros(self.n)
            e[i] = 1.0
            A[:, i] = self._lin_deriv(e, g)
        return A

    def _lin_deriv(self, x, g):
        num, den = self._node_v(x, 0.0, np.zeros(len(self.nodes)), g_override=g)
        v = num / den
        dx = np.zeros(self.n)
        for s, br in enumerate(self.series):
            vp = (0.0 if s == 0 else v[s - 1]) if self.source else v[s]
            vn = v[s] if self.source else v[s + 1]
            dx[s] = (vp - vn - br['R'] * x[s]) / br['L']
        for j, (k, c, r) in enumerate(self.shunts):
            dx[self.ns + j] = (v[k] - x[self.ns + j]) / (r * c)
        return dx

    def impedance(self, node, freqs, g=None):
        """|Z| seen by a 1 A injection at `node`, sources shorted, optional g."""
        g = np.zeros(len(self.nodes)) if g is None else g
        A = self.linear(g)
        # input vector for injection and output row for node voltage
        inj = np.zeros(len(self.nodes))
        inj[node] = -1.0                       # inj is a sink; -1 => 1 A into node
        x0 = np.zeros(self.n)
        num, den = self._node_v(x0, 0.0, inj, g_override=g)
        Dv = (num / den)[node]
        B = self._lin_input(inj, g)
        Cr = np.array([self._node_row(i, node, g) for i in range(self.n)])
        out = []
        for f in freqs:
            s = 2j * math.pi * f
            xs = np.linalg.solve(s * np.eye(self.n) - A, B)
            out.append(Cr @ xs + Dv)
        return np.array(out)

    def _lin_input(self, inj, g):
        num, den = self._node_v(np.zeros(self.n), 0.0, inj, g_override=g)
        v = num / den
        dx = np.zeros(self.n)
        for s, br in enumerate(self.series):
            vp = (0.0 if s == 0 else v[s - 1]) if self.source else v[s]
            vn = v[s] if self.source else v[s + 1]
            dx[s] = (vp - vn) / br['L']
        for j, (k, c, r) in enumerate(self.shunts):
            dx[self.ns + j] = v[k] / (r * c)
        return dx

    def _node_row(self, i, node, g):
        e = np.zeros(self.n)
        e[i] = 1.0
        num, den = self._node_v(e, 0.0, np.zeros(len(self.nodes)), g_override=g)
        return (num / den)[node]

    def simulate(self, x0, t_end, dt, vs_f, inj_f, cpl_f=None, rec=()):
        steps = int(round(t_end / dt))
        x = x0.copy()
        t_out, v_out = [], []
        for i in range(steps + 1):
            t = i * dt
            if i % 10 == 0:
                _, v = self.deriv(x, vs_f(t), inj_f(t), cpl_f(t) if cpl_f else None)
                t_out.append(t)
                v_out.append([v[k] for k in rec])
            def f(xx, tt):
                return self.deriv(xx, vs_f(tt), inj_f(tt), cpl_f(tt) if cpl_f else None)[0]
            k1 = f(x, t)
            k2 = f(x + dt / 2 * k1, t + dt / 2)
            k3 = f(x + dt / 2 * k2, t + dt / 2)
            k4 = f(x + dt * k3, t + dt)
            x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            for s, br in enumerate(self.series):
                if br.get('diode') and x[s] < 0:
                    x[s] = 0.0
        return np.array(t_out), np.array(v_out)


def min_damping(A):
    ev = np.linalg.eigvals(A)
    worst, unstable = 1.0, False
    for e in ev:
        if e.real >= 0:
            unstable = True
        if abs(e.imag) > 1e-3 * abs(e) and abs(e.imag) / (2 * math.pi) < 2e6:
            worst = min(worst, -e.real / abs(e))
    return worst, unstable


# --------------------------------------------------------------------------------------
# Input bus VIN (after U5): source corners and options
# --------------------------------------------------------------------------------------
VIN_CER_LO, VIN_CER_HI, VIN_CER_ESR = mlcc(5, 10, '10u50V_1206', 20.0)   # C6 C7 C15 C16 C24


def vin_ladder(opt, L_src, R_src, R_board, R_on, cer, can_esr, csrc, rd=1.0, c5c='lo'):
    nodes, series = [], []
    if csrc:                                   # charger-side bulk before the cable (unknown)
        nodes.append({'shunts': [csrc]})
        series.append({'R': 0.01, 'L': 50e-9})
        series.append({'R': R_src, 'L': L_src})
    else:
        series.append({'R': R_src, 'L': L_src})
    nodes.append({'shunts': [(0.4e-6, 0.05)]})                     # VPD: C46 1u @20V
    series.append({'R': R_board, 'L': 15e-9, 'diode': True, 'vf': 0.5})  # F1 + D10
    nodes.append({'shunts': [(0.4e-6, 0.05)]})                     # EF_IN: C2 1u
    series.append({'R': R_on, 'L': 10e-9})                        # U5
    sh = [(cer, VIN_CER_ESR)]
    if opt == 'A':                             # C5 corner: tol x cold x EOL low, or +20 % high
        sh.append((CAN['C5']['c'] * (CAN_C_LO if c5c == 'lo' else CAN_C_HI), can_esr))
    elif opt.startswith('B_RC'):                                   # n x 10u/50V + Rd damper
        n = int(opt.split('x')[1])
        lo, hi, esr = mlcc(n, 10, '10u50V_1206', 20.0)
        sh.append(((lo if cer == VIN_CER_LO else hi), rd + esr))
    elif opt.startswith('B_C'):                                    # n x 10u/50V, no damper
        n = int(opt.split('x')[1])
        lo, hi, esr = mlcc(n, 10, '10u50V_1206', 20.0)
        sh.append(((lo if cer == VIN_CER_LO else hi), esr))
    nodes.append({'shunts': sh})
    return Ladder(nodes, series), len(nodes) - 1


VIN_OPTS = ['A', 'B0', 'B_Cx2', 'B_RCx2', 'B_RCx4']
P_MAX, V_MIN = 72.0, 17.2       # input power upper estimate, near U5 UVLO-rising


def vin_grid():
    for L, R, Rb, Ron, cer, esr_i, csrc, c5c in itertools.product(
            (0.4e-6, 1.0e-6, 2.0e-6), (0.02, 0.10, 0.20), (0.02, 0.06), (0.019, 0.053),
            ('lo', 'hi'), (0, 1, 2), ('none', 'cer10u', 'bulk100u'), ('lo', 'hi')):
        yield dict(L=L, R=R, Rb=Rb, Ron=Ron, cer=cer, esr_i=esr_i, csrc=csrc, c5c=c5c)


CSRC = {'none': None, 'cer10u': (10e-6, 0.005), 'bulk100u': (100e-6, 0.02)}


def vin_study(rd):
    freqs = np.logspace(3, 6, 240)
    res = {}
    for opt in VIN_OPTS:
        worst = dict(zeta=9, zmax=0, unstable=0, n=0)
        for c in vin_grid():
            if opt != 'A' and (c['esr_i'] != 0 or c['c5c'] != 'lo'):
                continue
            cer = VIN_CER_LO if c['cer'] == 'lo' else VIN_CER_HI
            lad, k = vin_ladder(opt, c['L'], c['R'], c['Rb'], c['Ron'], cer,
                                CAN['C5']['esr'][c['esr_i']], CSRC[c['csrc']], rd, c['c5c'])
            g = np.zeros(len(lad.nodes))
            g[k] = -P_MAX / V_MIN ** 2
            z, uns = min_damping(lad.linear(g))
            worst['n'] += 1
            worst['unstable'] += int(uns)
            if z < worst['zeta']:
                worst.update(zeta=z, zeta_case=c)
            if c['L'] == 2.0e-6 or c['csrc'] != 'none':
                zm = float(np.max(np.abs(lad.impedance(k, freqs))))
                if zm > worst['zmax']:
                    worst.update(zmax=zm, zmax_case=c)
        res[opt] = worst
    return res


def vin_transient(opt, rd, case, p0, p1, edge=10e-6, t_end=400e-6, dt=10e-9, vs=20.0):
    cer = VIN_CER_LO if case['cer'] == 'lo' else VIN_CER_HI
    lad, k = vin_ladder(opt, case['L'], case['R'], case['Rb'], case['Ron'], cer,
                        CAN['C5']['esr'][case['esr_i']], CSRC[case['csrc']], rd, case['c5c'])
    # DC operating point at p0
    rt = sum(b['R'] for b in lad.series)
    veff = vs - 0.5
    i0 = (veff - math.sqrt(veff ** 2 - 4 * rt * p0)) / (2 * rt)
    x0 = np.zeros(lad.n)
    x0[:lad.ns] = i0
    vnode, acc = [], vs
    for s, b in enumerate(lad.series):
        acc -= b['R'] * i0 + b.get('vf', 0.0)
        vnode.append(acc)
    for j, (kk, c, r) in enumerate(lad.shunts):
        x0[lad.ns + j] = vnode[kk]
    t0 = 20e-6

    def pw(t):
        if t < t0:
            return p0
        if t > t0 + edge:
            return p1
        return p0 + (p1 - p0) * (t - t0) / edge

    zero = np.zeros(len(lad.nodes))
    t, v = lad.simulate(x0, t_end, dt, lambda tt: vs, lambda tt: zero,
                        lambda tt: (k, pw(tt)), rec=(k,))
    return t, v[:, 0], vnode[k]


# --------------------------------------------------------------------------------------
# RAW converter outputs (before U6/U7/LM5067): load-release overshoot, passive |Z|
# --------------------------------------------------------------------------------------
RAILS = {
    # vo_hi: FB reference at its full-temperature maximum (TPS62933F SLUSEA4D: 816 mV,
    # TJ -40..150 C; 812 mV at 0..85 C. LMR38020 SNVSC40E: 1.015 V, FPWM) with 1 % divider
    # corners. ov_lo: TPS16630 V(OVPR) 1.176 V min with 1 % divider corners.
    'P12_RAW': dict(vo=12.194, vo_hi=round(0.816 * (1 + 47.47 / 3.267), 3),
                    vo_hi_0_85C=round(0.812 * (1 + 47.47 / 3.267), 3), L=6.8e-6, fsw=1.2e6,
                    cer=(4, 22, 12.2), i_rel=2.2, ov_lo=13.85, ov_note='U6 OVP 1.176 V min, 110k/10k 1 %'),
    'P5_RAW': dict(vo=4.985, vo_hi=round(0.816 * (1 + 68.68 / 12.87), 3),
                   vo_hi_0_85C=round(0.812 * (1 + 68.68 / 12.87), 3), L=3.3e-6, fsw=1.977e6,
                   cer=(4, 22, 5.0), i_rel=2.2, ov_lo=5.356, ov_note='U7 OVP 1.176 V min, 33k/9.1k 1 %'),
    'N12_RAW': dict(vo=11.989, vo_hi=round(1.015 * (1 + 101.0 / 9.009), 3),
                    vo_hi_0_85C=round(1.015 * (1 + 101.0 / 9.009), 3), L=15e-6, fsw=0.79e6,
                    cer=(5, 22, 12.2), i_rel=0.8, ov_lo=14.25, ov_note='LM5067 OV ~14.25 V magnitude nominal only'),
}
RAW_OPTS = ['A', 'B0', 'B_x2']           # can kept / can removed / can -> +2 x 22u 1206


def raw_ladder(rail, opt, corner, can_esr, rack):
    p = RAILS[rail]
    n, nom, v = p['cer']
    lo, hi, esr = mlcc(n + (2 if opt == 'B_x2' else 0), nom, '22u25V_1206', v)
    sh = [((lo if corner == 'lo' else hi), esr)]
    if opt == 'A':
        sh.append(((CAN['C34_36']['c'] * (CAN_C_LO if corner == 'lo' else CAN_C_HI)), can_esr))
    nodes = [{'shunts': sh}]
    series = []
    if rack:                                   # eFuse/LM5067 path + header + ribbon to rack
        series.append({'R': rack['R'], 'L': rack['L']})
        nodes.append({'shunts': [(rack['C'], rack['esr'])]})
    else:
        nodes.append({'shunts': [(1e-6, 0.01)]})                 # C38/C41/C45 only
        series.append({'R': 0.04, 'L': 20e-9})
    return Ladder(nodes, series, source=False)


def raw_release(rail, opt, corner, can_esr, n_delay, rack=None, at_rack=False,
                t_end=40e-6, dt=5e-9):
    """Load steps from i_rel to 0 in 0.5 us; converter delivers i_rel for n_delay switching
    cycles then slews at -Vo/L (FCCM can go negative, but this model stops at 0 A: no sink,
    conservative). This replaces, and does not represent, the real control loop."""
    p = RAILS[rail]
    lad = raw_ladder(rail, opt, corner, can_esr, rack)
    I0 = p['i_rel']
    x0 = np.zeros(lad.n)
    x0[0] = I0 if at_rack else 0.0
    vo = p['vo_hi']
    for j, (k, c, r) in enumerate(lad.shunts):
        x0[lad.ns + j] = vo - (I0 * lad.series[0]['R'] if (k == 1 and at_rack) else 0.0)
    td = n_delay / p['fsw']
    slew = p['vo'] / p['L']
    load_node = 1 if at_rack else 0

    def conv(t):
        return I0 if t < td else max(I0 - slew * (t - td), 0.0)

    def load(t):
        return I0 * max(0.0, 1 - t / 0.5e-6)

    def inj(t):
        a = np.zeros(2)
        a[0] = -conv(t)
        a[load_node] += load(t)
        return a

    t, v = lad.simulate(x0, t_end, dt, lambda tt: 0.0, inj, rec=(0,))
    return t, v[:, 0]


def raw_impedance(rail, opt, corner, can_esr, rack):
    lad = raw_ladder(rail, opt, corner, can_esr, rack)
    f = np.logspace(3, 6.3, 200)
    return f, lad.impedance(0, f)


# --------------------------------------------------------------------------------------
# Closed-form screens
# --------------------------------------------------------------------------------------
def ibb_screens():
    out = []
    for vin in (17.2, 20.0, 24.1):
        for io in (0.8, 1.0, 1.143):
            vo, L = 11.989, 15e-6
            D = vo / (vin + vo)
            R = vo / io
            frhpz = R * (1 - D) ** 2 / (2 * math.pi * D * L)
            il = io / (1 - D)
            dil = vin * D / (L * 0.79e6)
            i_cout_rms = io * math.sqrt(D / (1 - D))
            i_cin_rms = il * math.sqrt(D * (1 - D))
            out.append(dict(vin=vin, io=io, D=round(D, 3), f_rhpz_kHz=round(frhpz / 1e3, 1),
                            il_avg=round(il, 3), il_pk=round(il + dil / 2, 3),
                            i_cout_rms=round(i_cout_rms, 3), i_cin_rms=round(i_cin_rms, 3)))
    return out


def tps62933_eq21(vo, vin, L, fsw, di, dv):
    D = vo / vin
    dil = vo * (1 - D) / (L * fsw)
    K = dil / 2.5
    return di / (fsw * dv * K) * ((1 - D) * (1 - K) + K * K / 12 * (2 - D))


def input_ripple():
    v = 20.0
    r12 = 2.5 * math.sqrt(12.194 / v * (1 - 12.194 / v))
    r5 = 2.5 * math.sqrt(4.985 / v * (1 - 4.985 / v))
    return dict(i_cin_rms_U2=round(r12, 3), i_cin_rms_U3=round(r5, 3))


def inrush():
    out = {}
    for name, c in (('A', 47e-6 * CAN_C_HI + VIN_CER_HI), ('B0', VIN_CER_HI)):
        sr_nom = 2e-6 * 25 / 22e-9
        sr_max = 2.225e-6 * 26 / (22e-9 * 0.9)
        out[name] = dict(sr_V_per_ms=(round(sr_nom / 1e3, 2), round(sr_max / 1e3, 2)),
                         i_inrush_A_max=round(c * sr_max, 3))
    return out


def can_life():
    return {f'{tc} C': round(1000 * 2 ** ((105 - tc) / 10)) for tc in (45, 55, 65, 75)}


def stress():
    return dict(C25_C26_normal=round(20 + 11.989, 2), C25_C26_ovp_hi=round(24.9 + 14.25, 2),
                C25_C26_tvs_window=round(35.5 + 12.2, 2), rating=50,
                C25_C26_eff_lo_uF=round(mlcc(2, 10, '10u50V_1206', 32.0)[0] * 1e6, 2),
                C25_C26_eff_hi_uF=round(mlcc(2, 10, '10u50V_1206', 32.0)[1] * 1e6, 2),
                lmr38020_min_cin_eff_uF=4.7)


# --------------------------------------------------------------------------------------
# Ripple-current split between dielectrics (frequency domain, ideal CCM waveforms)
# --------------------------------------------------------------------------------------
# Steady-state switching ripple only (no load transients). Each bank is lumped: C, ESR/n,
# ESL/n plus a route inductance to the can. Equal sharing inside a bank is assumed, so a
# x2 imbalance screen is applied to the per-part figure. ESL/route values are engineering
# brackets, not manufacturer data.
MLCC_ESL = (0.6e-9, 1.5e-9)            # per 1206 part incl. mounting
MLCC_ESR_HF = (0.003, 0.010)           # per part at 0.8-2 MHz (Samsung curve not obtained)
CAN_ESL = (5e-9, 15e-9)                # 6.3 mm SMD can incl. pads
ROUTE_L = (0.0, 3e-9)                  # ceramic bank -> can copper
# MVK frequency multiplier: SamYoung BDS(MVK).pdf (found by panel review, 2026-10-31) gives
# 1.08 @ 100 kHz for the family but does not list our 6.3x8 47u50V/100u35V variants, so it
# is NOT applied as exact evidence; the model keeps the proxy below. Proxy: SamYoung MVG (same
# vertical-SMD family) table, 10-1000 uF: 1.30-1.80 at 10-100 kHz. Bounded 1.0-1.8.
CAN_RIPPLE_120HZ = dict(C5=0.070, C34_36=0.052)    # A rms, 105 C, 120 Hz (LCSC C165527/C350012 listings)
CAN_FMULT = (1.0, 1.8)
IMBALANCE = 2.0


def zbr(c, r, l, f):
    w = 2 * math.pi * f
    return r + 1j * w * l + 1 / (1j * w * c)


def fourier(wave, nh=80, npts=8192):
    """One-sided complex peak amplitudes of harmonics 1..nh of a periodic sampled wave."""
    t = np.arange(npts) / npts
    X = np.fft.rfft(wave(t)) / npts * 2
    return X[1:nh + 1]


def ccm(vin, vo, L, fsw, io, topo):
    """Return (D, wave_out(t), wave_in(t)) as functions of normalised time t in [0,1)."""
    if topo == 'buck':
        D = vo / vin
        il = io
        dil = vo * (1 - D) / (L * fsw)
    else:                                   # inverting buck-boost, |vo|
        D = vo / (vin + vo)
        il = io / (1 - D)
        dil = vin * D / (L * fsw)

    def iL(t):
        return np.where(t < D, il - dil / 2 + dil * t / D, il + dil / 2 - dil * (t - D) / (1 - D))

    if topo == 'buck':
        return D, (lambda t: iL(t) - io), (lambda t: np.where(t < D, iL(t), 0.0))
    return D, (lambda t: np.where(t < D, 0.0, iL(t))), (lambda t: np.where(t < D, iL(t), 0.0))


def synth_pp(V, npts=8192):
    """True peak-to-peak of the band-limited periodic waveform sum Re(V_k exp(j2pi k t)).
    With ideal (zero-rise-time) current edges the ESL part is an impulse, so this value is
    set by the harmonic count; see ripple_checks() for the nh sensitivity."""
    t = np.arange(npts) / npts
    k = np.arange(1, len(V) + 1)
    w = (V[None, :] * np.exp(2j * math.pi * np.outer(t, k))).real.sum(axis=1)
    return float(w.max() - w.min())


def split_one_node(I, fsw, branches):
    """I: harmonic currents into a node; branches: {name: (C, R, L)}. Returns rms per branch,
    the synthesised node ripple Vpp (band-limited) and the same Vpp with ESL removed."""
    f = fsw * np.arange(1, len(I) + 1)
    Z = {k: zbr(c, r, l, f) for k, (c, r, l) in branches.items()}
    Y = sum(1 / z for z in Z.values())
    V = I / Y
    out = {k: float(np.sqrt(np.sum(np.abs(V / z) ** 2) / 2)) for k, z in Z.items()}
    out['vpp_synth'] = synth_pp(V)
    Y0 = sum(1 / zbr(c, r, 0.0, f) for c, r, l in branches.values())
    out['vpp_synth_noESL'] = synth_pp(I / Y0)
    return out


def ripple_banks(n, nom, key, v, corner, esl_i, esr_i):
    lo, hi, _ = mlcc(n, nom, key, v)
    return ((lo if corner == 'lo' else hi), MLCC_ESR_HF[esr_i] / n, MLCC_ESL[esl_i] / n)


def ripple_outputs(nh=80):
    """Single-node output ripple split, options A (can) / B (+2 x 22u). Primary for
    P12_RAW / P5_RAW. For N12_RAW this is a DIAGNOSTIC only: it ignores the C25/C26 coupling
    to VIN; the primary N12_RAW/C36 result is ripple_ibb_input() (two-node, same source)."""
    res = {}
    cases = dict(P12_RAW=('buck', 12.194, 6.8e-6, 1.2e6, 2.5, (4, 22, 12.2)),
                 P5_RAW=('buck', 4.985, 3.3e-6, 1.977e6, 2.5, (4, 22, 5.0)),
                 N12_RAW=('ibb', 11.989, 15e-6, 0.79e6, 1.143, (5, 22, 12.2)))
    for rail, (topo, vo, L, fsw, io, (n, nom, vb)) in cases.items():
        r = {}
        for opt in ('A', 'B_x2'):
            worst = dict(can_rms=0.0, part_rms=0.0, vpp_synth=0.0, vpp_synth_noESL=0.0)
            for vin, corner, esl_i, esr_i, can_esr, can_l, rl in itertools.product(
                    (17.2, 24.1), ('lo', 'hi'), (0, 1), (0, 1), CAN['C34_36']['esr'], CAN_ESL, ROUTE_L):
                if opt != 'A' and (can_esr, can_l, rl) != (CAN['C34_36']['esr'][0], CAN_ESL[0], 0.0):
                    continue
                nn = n + (2 if opt == 'B_x2' else 0)
                _, wout, _ = ccm(vin, vo, L, fsw, io, topo)
                I = fourier(wout, nh)
                br = {'cer': ripple_banks(nn, nom, '22u25V_1206', vb, corner, esl_i, esr_i)}
                if opt == 'A':
                    cc = CAN['C34_36']['c'] * (CAN_C_LO if corner == 'lo' else CAN_C_HI)
                    br['can'] = (cc, can_esr, can_l + rl)
                s = split_one_node(I, fsw, br)
                tot = float(np.sqrt(np.sum(np.abs(I) ** 2) / 2))
                worst['total_rms'] = round(max(worst.get('total_rms', 0), tot), 3)
                worst['can_rms'] = max(worst['can_rms'], s.get('can', 0.0))
                worst['part_rms'] = max(worst['part_rms'], s['cer'] / nn * IMBALANCE)
                worst['vpp_synth'] = max(worst['vpp_synth'], s['vpp_synth'])
                worst['vpp_synth_noESL'] = max(worst['vpp_synth_noESL'], s['vpp_synth_noESL'])
                worst['part_mW_at_ESRmax'] = round(1e3 * worst['part_rms'] ** 2 * MLCC_ESR_HF[1], 2)
            if opt == 'A':
                lim = (CAN_RIPPLE_120HZ['C34_36'] * CAN_FMULT[0], CAN_RIPPLE_120HZ['C34_36'] * CAN_FMULT[1])
                worst['can_limit_A_rms_105C'] = [round(x, 3) for x in lim]
                worst['can_P_mW_max'] = round(1e3 * worst['can_rms'] ** 2 * CAN['C34_36']['esr'][2], 2)
            r[opt] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in worst.items()}
        if rail == 'N12_RAW':
            r['role'] = 'diagnostic single-node (no C25/C26 coupling); not combined with ripple_ibb_input'
        res[rail] = r
    return res


def ibb_cell(opt, vin, corner, esl_i, esr_i, can_esr_i=0, can_l=CAN_ESL[0], rl=0.0, nh=80):
    """U4 switching cell, two-node nodal solve per harmonic. Nodes VIN and N12_RAW vs GND.
    Branches: VIN-GND bank (5 x 10u + C5 or 2 x 10u + 1 ohm damper), VIN-N12 C25/C26,
    N12-GND bank (5 or 7 x 22u + C36 in A). Injections: VIN loses iL during on-time,
    N12_RAW loses iL during off-time (U4 output current), GND gains iL. Both injections come
    from one inductor current, so every branch current is the coherent sum of both."""
    D, wout, win = ccm(vin, 11.989, 15e-6, 0.79e6, 1.143, 'ibb')
    Ivin = -fourier(win, nh)
    In12 = -fourier(wout, nh)
    f = 0.79e6 * np.arange(1, nh + 1)
    vlo = corner == 'lo'
    nng = 5 + (2 if opt == 'B' else 0)
    cvg = ripple_banks(5, 10, '10u50V_1206', 20.0, corner, esl_i, esr_i)
    cvn = ripple_banks(2, 10, '10u50V_1206', 32.0, corner, esl_i, esr_i)
    cng = ripple_banks(nng, 22, '22u25V_1206', 12.2, corner, esl_i, esr_i)
    Zvg = [zbr(*cvg, f)]
    Zng = [zbr(*cng, f)]
    if opt == 'A':
        Zvg.append(zbr(CAN['C5']['c'] * (CAN_C_LO if vlo else CAN_C_HI), CAN['C5']['esr'][can_esr_i],
                       can_l + rl, f))
        Zng.append(zbr(CAN['C34_36']['c'] * (CAN_C_LO if vlo else CAN_C_HI), CAN['C34_36']['esr'][can_esr_i],
                       can_l + rl, f))
    else:
        lo, hi, esr = mlcc(2, 10, '10u50V_1206', 20.0)
        Zvg.append(zbr(lo if vlo else hi, 1.0 + esr, 2e-9, f))
    Yvg = sum(1 / z for z in Zvg)
    Yng = sum(1 / z for z in Zng)
    Yvn = 1 / zbr(*cvn, f)
    # nodal: [Yvg+Yvn, -Yvn; -Yvn, Yng+Yvn] [Vv; Vn] = [Ivin; In12]
    det = (Yvg + Yvn) * (Yng + Yvn) - Yvn ** 2
    Vv = (Ivin * (Yng + Yvn) + Yvn * In12) / det
    Vn = ((Yvg + Yvn) * In12 + Yvn * Ivin) / det
    Ivn = (Vv - Vn) * Yvn
    kcl = max(float(np.max(np.abs(Vv * Yvg + Ivn - Ivin))), float(np.max(np.abs(Vn * Yng - Ivn - In12))))
    return dict(D=D, win=win, wout=wout, Ivin=Ivin, In12=In12, Vv=Vv, Vn=Vn, Ivn=Ivn, Zvg=Zvg, Zng=Zng,
                Yvg=Yvg, Yng=Yng, nng=nng, kcl_residual_A=kcl, f=f)


def _rms(a):
    return float(np.sqrt(np.sum(np.abs(a) ** 2) / 2))


def ripple_ibb_input(nh=80):
    """Primary U4 result (input cell and N12_RAW incl. C36), coherent two-node model."""
    out = {}
    for opt in ('A', 'B'):
        w = dict(c25_rms=0.0, c25_vpp_synth=0.0, c25_vpp_synth_noESL=0.0, gnd_path_rms=0.0,
                 can_c5_rms=0.0, can_c36_rms=0.0, damper_rms=0.0, n12_cer_rms=0.0, kcl_residual_A=0.0)
        axes = ((17.2, 24.1), ('lo', 'hi'), (0, 1), (0, 1))
        can_axes = ((0, 1, 2), CAN_ESL, ROUTE_L) if opt == 'A' else ((0,), (CAN_ESL[0],), (0.0,))
        for vin, corner, esl_i, esr_i, ce, cl, rl in itertools.product(*axes, *can_axes):
            c = ibb_cell(opt, vin, corner, esl_i, esr_i, ce, cl, rl, nh)
            w['c25_rms'] = max(w['c25_rms'], _rms(c['Ivn']))
            w['gnd_path_rms'] = max(w['gnd_path_rms'], _rms(c['Vv'] * c['Yvg']))
            w['c25_vpp_synth'] = max(w['c25_vpp_synth'], synth_pp(c['Vv'] - c['Vn']))
            Yvn0 = 1 / zbr(*ripple_banks(2, 10, '10u50V_1206', 32.0, corner, esl_i, esr_i)[:2], 0.0, c['f'])
            w['c25_vpp_synth_noESL'] = max(w['c25_vpp_synth_noESL'], synth_pp(c['Ivn'] / Yvn0))
            w['n12_cer_rms'] = max(w['n12_cer_rms'], _rms(c['Vn'] / c['Zng'][0]))
            if opt == 'A':
                w['can_c5_rms'] = max(w['can_c5_rms'], _rms(c['Vv'] / c['Zvg'][1]))
                w['can_c36_rms'] = max(w['can_c36_rms'], _rms(c['Vn'] / c['Zng'][1]))
            else:
                w['damper_rms'] = max(w['damper_rms'], _rms(c['Vv'] / c['Zvg'][1]))
            w['total_in_rms'] = round(max(w.get('total_in_rms', 0), _rms(c['Ivin'])), 3)
            w['total_out_rms'] = round(max(w.get('total_out_rms', 0), _rms(c['In12'])), 3)
            w['kcl_residual_A'] = max(w['kcl_residual_A'], c['kcl_residual_A'])
            n_ng = c['nng']
        w['c25_part_rms_x2imb'] = w['c25_rms'] / 2 * IMBALANCE
        w['n12_cer_part_rms_x2imb'] = w['n12_cer_rms'] / n_ng * IMBALANCE
        w['n12_cer_part_mW_at_ESRmax'] = 1e3 * w['n12_cer_part_rms_x2imb'] ** 2 * MLCC_ESR_HF[1]
        w['damper_mW_1ohm'] = 1e3 * w['damper_rms'] ** 2 * 1.0
        out[opt] = {k: (round(v, 4) if abs(v) > 1e-6 else float(f'{v:.3g}')) for k, v in w.items()}
    out['role'] = 'primary for C25/C26, C36, N12_RAW ceramics and the U4 share of C5'
    return out


def ripple_checks():
    """Current-sum and harmonic-convergence check of the changed ripple models (worst corner
    for C36: low C, low ESL, low ESR, warm-low can ESR, no route L)."""
    out = {}
    for vin in (17.2, 24.1):
        D, wout, win = ccm(vin, 11.989, 15e-6, 0.79e6, 1.143, 'ibb')
        t = np.arange(1 << 16) / (1 << 16)
        io, ii = float(wout(t).mean()), float(win(t).mean())
        il = float((wout(t) + win(t)).mean())
        ac_out = float(np.sqrt(np.mean((wout(t) - io) ** 2)))
        ac_in = float(np.sqrt(np.mean((win(t) - ii) ** 2)))
        row = dict(D=round(D, 4), mean_out_A=round(io, 4), mean_in_A=round(ii, 4),
                   power_balance_W=[round(vin * ii, 3), round(11.989 * io, 3)], mean_iL=round(il, 4),
                   iL_eq_in_plus_out=abs(il - io - ii) < 1e-9,
                   ac_rms_out_time=round(ac_out, 4), ac_rms_in_time=round(ac_in, 4))
        for nh in (80, 160, 320):
            c = ibb_cell('A', vin, 'lo', 0, 0, 0, CAN_ESL[0], 0.0, nh)
            row[f'nh{nh}'] = dict(
                parseval_out_frac=round(_rms(c['In12']) / ac_out, 4),
                parseval_in_frac=round(_rms(c['Ivin']) / ac_in, 4),
                C36_rms=round(_rms(c['Vn'] / c['Zng'][1]), 5),
                C25_C26_rms=round(_rms(c['Ivn']), 4),
                C25_C26_vpp_synth=round(synth_pp(c['Vv'] - c['Vn']), 4),
                C25_C26_vpp_synth_noESL=round(synth_pp(c['Ivn'] / (1 / zbr(*ripple_banks(
                    2, 10, '10u50V_1206', 32.0, 'lo', 0, 0)[:2], 0.0, c['f']))), 4),
                kcl_residual_A=float(f"{c['kcl_residual_A']:.2e}"))
        out[f'vin_{vin}'] = row
    return out


def ripple_vin_bucks(nh=80):
    """U2+U3 pulsed input current into the VIN bank (+C5 or damper). U2 (1.2 MHz), U3
    (~1.98 MHz) and U4 (790 kHz) are free-running, unsynchronised sources at different
    frequencies, so their long-term rms values add in quadrature (not coherent terms)."""
    out = {}
    for opt in ('A', 'B'):
        w = dict(can_rms=0.0, damper_rms=0.0, part_rms=0.0, vpp_synth_U2=0.0, vpp_synth_noESL_U2=0.0)
        can_axes = ((0, 1, 2), CAN_ESL) if opt == 'A' else ((0,), (CAN_ESL[0],))
        for vin, corner, esl_i, ce, cl in itertools.product((17.2, 24.1), ('lo', 'hi'), (0, 1), *can_axes):
            tot = dict(can=0.0, dmp=0.0, cer=0.0)
            for vo, L, fsw in ((12.194, 6.8e-6, 1.2e6), (4.985, 3.3e-6, 1.977e6)):
                _, _, win = ccm(vin, vo, L, fsw, 2.5, 'buck')
                I = fourier(win, nh)
                br = {'cer': ripple_banks(5, 10, '10u50V_1206', 20.0, corner, esl_i, 1)}
                if opt == 'A':
                    br['can'] = (CAN['C5']['c'] * (CAN_C_LO if corner == 'lo' else CAN_C_HI),
                                 CAN['C5']['esr'][ce], cl)
                else:
                    lo, hi, esr = mlcc(2, 10, '10u50V_1206', 20.0)
                    br['dmp'] = ((lo if corner == 'lo' else hi), 1.0 + esr, 2e-9)
                s = split_one_node(I, fsw, br)
                for k in ('can', 'dmp', 'cer'):
                    tot[k] += s.get(k, 0.0) ** 2
                if vo > 10:
                    w['vpp_synth_U2'] = max(w['vpp_synth_U2'], s['vpp_synth'])
                    w['vpp_synth_noESL_U2'] = max(w['vpp_synth_noESL_U2'], s['vpp_synth_noESL'])
            w['can_rms'] = max(w['can_rms'], math.sqrt(tot['can']))
            w['damper_rms'] = max(w['damper_rms'], math.sqrt(tot['dmp']))
            w['part_rms'] = max(w['part_rms'], math.sqrt(tot['cer']) / 5 * IMBALANCE)
        w['damper_mW_1ohm'] = 1e3 * w['damper_rms'] ** 2
        out[opt] = {k: round(v, 4) for k, v in w.items()}
    return out


# --------------------------------------------------------------------------------------
# Cost cross-check (inputs are the panel's preliminary LCSC quotes, not verified here)
# --------------------------------------------------------------------------------------
# Panel (DeepSeek) live per-unit quotes, observed 2026-10-31 ~04:37 UTC, USD, likely at the
# minimum 5-piece step per code. Not re-verified in this study. Damper R, Extended loading
# fees, setup, attrition and placement were NOT quoted, so every total below is parts-only.
PRICE_OBSERVED = '2026-10-31 ~04:37 UTC (panel live quote, not re-verified here)'
PANEL_PRICE = dict(C165527=0.1267, C350012=0.1173, C13585=0.2115, C12891=0.1180)  # USD per unit
HYPOTHETICAL_EXT_FEE = (1.0, 3.0)    # USD per Extended code per order: sensitivity only, NOT a quote


def cost_delta():
    cans = PANEL_PRICE['C165527'] + 3 * PANEL_PRICE['C350012']
    opts = {
        'A (retain C5 + C34/C35/C36)': 0.0,
        'B_full (C5 -> 2x C13585 + R; C34/35/36 -> 2x C12891 each)':
            2 * PANEL_PRICE['C13585'] + 6 * PANEL_PRICE['C12891'],
        'B_min (C5 -> 2x C13585 + R; C35 -> 2x C12891; C34/C36 removed)':
            2 * PANEL_PRICE['C13585'] + 2 * PANEL_PRICE['C12891'],
        'B_bare (C5 -> 2x C13585 + R; C34/C35/C36 removed)': 2 * PANEL_PRICE['C13585'],
    }
    out = {'observed': PRICE_OBSERVED, 'unit_usd': dict(PANEL_PRICE),
           'removed_cans_usd_per_board': round(cans, 4),
           'excluded': 'damper R (new code, unquoted), Extended fees, setup, attrition, placement, MOQ remainder'}
    for k, add in opts.items():
        removed = 0.0 if k.startswith('A ') else cans
        d = add - removed
        row = dict(added_usd=round(add, 4), removed_usd=round(removed, 4),
                   net_parts_usd_per_board=round(d, 4))
        if d > 0 and not k.startswith('A '):
            # B removes the two Extended codes (C165527, C350012); A keeps them.
            row['breakeven_boards_if_ext_fee_usd'] = {
                f'{f:.0f} (hypothetical)': round(2 * f / d, 1) for f in HYPOTHETICAL_EXT_FEE}
        out[k] = row
    out['note'] = ('B removes two Extended codes; breakeven batch = 2 x fee / net delta, i.e. B is '
                   'cheaper only for batches below that size. Fee not quoted: no cost claim either way.')
    return out


def screens(R):
    """Classify each concern and state its pass/fail condition (no new physics)."""
    st = R['stress']
    lo_factor = (1 - MLCC_TOL) * MLCC_TEMP_LO * MLCC_AGE_LO
    need_eff = st['lmr38020_min_cin_eff_uF']
    p5 = R['raw_release']['P5_RAW']
    marg = R['vo_hi']['P5_RAW']['margin_full']
    over = {k: v['overshoot_V'] for k, v in p5.items() if isinstance(v, dict)}
    return {
        'P5_RAW_OV_margin': dict(
            classification='conditional screening risk (static stack passes; dynamic part is model-dependent)',
            static_known=dict(vo_hi=R['vo_hi']['P5_RAW']['full_temp'], ov_lo=R['vo_hi']['P5_RAW']['ov_lo'],
                              margin_V=marg, source='SLUSEA4D VFB 816 mV max; SLVSET9G OVPR 1.176 V min; 1 % divider'),
            imposed_model='converter current held N cycles after a 2.2 A release, then slews at Vo/L; '
                          'no FCCM sinking, no compensator. N=2/8/16 is an assumption, not TPS62933F data',
            overshoot_V_by_option_and_N=over,
            exceeds_static_margin_under_assumed_N={k: v[1] > marg for k, v in over.items()},
            pass_condition=f'bench: P5_RAW peak during 0->2.2 A->0 steps (cold/hot, min/max VIN) stays below '
                           f'U7 OVPR trip with U7 FLT never asserted; static margin {marg} V is the budget',
            not_claimed='no closed-loop overshoot forecast'),
        'C25_C26_effective_C': dict(
            classification='conditional screening risk (guessed bias band, not a measured violation)',
            known='2 x 10 uF/50 V X5R 1206 at ~32 V DC; LMR38020 SNVSC40E CIN >= 4.7 uF effective',
            bounded_eff_uF=[st['C25_C26_eff_lo_uF'], st['C25_C26_eff_hi_uF']],
            required_bias_retention_at_32V=dict(
                nominal_only=round(need_eff / 20.0, 3),
                with_tol_temp_aging_low_corner=round(need_eff / (20.0 * lo_factor), 3)),
            pass_condition='Samsung curve or measured C at 32 V/25 C >= the retention above for CL31A106KBHNNNE '
                           '(and U4 input ripple/temperature on bench); otherwise review needed'),
        'C25_C26_voltage_in_TVS_window': dict(
            classification='conditional screening risk (needs verified source surge spec and U5 dynamics)',
            normal_V=st['C25_C26_normal'], ovp_hi_V=st['C25_C26_ovp_hi'],
            if_vin_reaches_clamp_V=st['C25_C26_tvs_window'], rating_V=st['rating'],
            pass_condition='measured VIN-to-N12_RAW peak during defined surge/hot-plug tests < 50 V'),
        'VIN_above_TPS62933_abs_max': dict(
            classification='conditional screening risk, pre-existing, not capacitor-driven',
            known='SMBJ22A Vc 35.5 V at its rated Ipp; TPS62933F VIN abs max 32 V (SLUSEA4D 8.1); '
                  'U5 OVP response delay per SLVSET9G',
            not_established='actual downstream VIN peak: depends on source surge energy/current, cable, '
                            'F1/D10, U5 turn-off dynamics; none verified here',
            pass_condition='measured VIN peak < 32 V under the chosen surge/hot-plug test set'),
        'ceramic_only_bank_sufficiency': dict(
            classification='not established',
            evidence='passive |Z| with bracketed can ESR; ceramic counts meet TI minimum tables under bounded '
                     'bias. Neither shows actual loop margin with or without the cans',
            pass_condition='Bode (phase margin/gain margin per TI guidance) and load-step on built boards for '
                           'every option kept'),
    }


# --------------------------------------------------------------------------------------
# Minimal SVG plotter (no matplotlib dependency)
# --------------------------------------------------------------------------------------
PAL = ['#2a6fdb', '#d9480f', '#2b8a3e', '#7048e8', '#868e96', '#c2255c']


def svg_plot(path, series, title, xlabel, ylabel, logx=False, logy=False, hlines=()):
    W, H, ml, mr, mt, mb = 760, 420, 70, 190, 40, 50
    xs = np.concatenate([s[1] for s in series])
    ys = np.concatenate([s[2] for s in series] + [np.array([h[0] for h in hlines])] if hlines else
                        [s[2] for s in series])
    fx = (lambda a: np.log10(a)) if logx else (lambda a: a)
    fy = (lambda a: np.log10(a)) if logy else (lambda a: a)
    x0, x1 = fx(xs.min()), fx(xs.max())
    y0, y1 = fy(ys.min()), fy(ys.max())
    pad = (y1 - y0) * 0.06 or 1
    y0, y1 = y0 - pad, y1 + pad
    px = lambda a: ml + (fx(a) - x0) / (x1 - x0) * (W - ml - mr)
    py = lambda a: H - mb - (fy(a) - y0) / (y1 - y0) * (H - mt - mb)
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
          f'font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="white"/>',
          f'<text x="{ml}" y="22" font-size="14" font-weight="bold">{title}</text>',
          f'<rect x="{ml}" y="{mt}" width="{W-ml-mr}" height="{H-mt-mb}" fill="none" stroke="#adb5bd"/>']
    for i in range(6):
        yv = y0 + (y1 - y0) * i / 5
        yy = H - mb - (H - mt - mb) * i / 5
        lab = f'{10**yv:.3g}' if logy else f'{yv:.3g}'
        el.append(f'<line x1="{ml}" x2="{W-mr}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#f1f3f5"/>'
                  f'<text x="{ml-6}" y="{yy+4:.1f}" text-anchor="end">{lab}</text>')
        xv = x0 + (x1 - x0) * i / 5
        xx = ml + (W - ml - mr) * i / 5
        labx = f'{10**xv:.3g}' if logx else f'{xv:.3g}'
        el.append(f'<text x="{xx:.1f}" y="{H-mb+16}" text-anchor="middle">{labx}</text>')
    for yv, lab in hlines:
        yy = py(yv)
        el.append(f'<line x1="{ml}" x2="{W-mr}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#495057" '
                  f'stroke-dasharray="5,4"/><text x="{ml+6}" y="{yy-5:.1f}" fill="#495057">{lab}</text>')
    for i, (name, x, y) in enumerate(series):
        pts = ' '.join(f'{px(a):.1f},{py(b):.1f}' for a, b in zip(x, y))
        col = PAL[i % len(PAL)]
        el.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{pts}"/>')
        el.append(f'<rect x="{W-mr+8}" y="{mt+18*i}" width="12" height="3" fill="{col}"/>'
                  f'<text x="{W-mr+24}" y="{mt+18*i+5}">{name}</text>')
    el.append(f'<text x="{(W-mr+ml)/2}" y="{H-12}" text-anchor="middle">{xlabel}</text>'
              f'<text x="16" y="{(H)/2}" transform="rotate(-90 16 {H/2})" text-anchor="middle">{ylabel}</text></svg>')
    pathlib.Path(path).write_text('\n'.join(el))


# --------------------------------------------------------------------------------------
def selftest():
    # series RLC from a source into a C: damping must equal R/2*sqrt(C/L)
    L, C, R = 1e-6, 10e-6, 0.05
    lad = Ladder([{'shunts': [(C, 1e-6)]}], [{'R': R, 'L': L}])
    z, uns = min_damping(lad.linear(np.zeros(1)))
    ana = R / 2 * math.sqrt(C / L)
    assert abs(z - ana) / ana < 0.01 and not uns, (z, ana)
    # negative conductance: stability boundary R > L/(C*Rn)
    rn = 4.0
    g = np.array([-1 / rn])
    z2, uns2 = min_damping(lad.linear(g))
    assert (R > L / (C * rn)) == (not uns2)
    f = np.array([1 / (2 * math.pi * math.sqrt(L * C))])
    zf = abs(lad.impedance(0, f)[0])
    assert abs(zf - L / (C * R)) / (L / (C * R)) < 0.05, zf
    # changed ripple model: KCL closes, injections conserve U4 charge/power, Parseval converges
    rc = ripple_checks()
    for row in rc.values():
        assert row['iL_eq_in_plus_out'] and abs(row['mean_out_A'] - 1.143) < 1e-3
        assert abs(row['power_balance_W'][0] - row['power_balance_W'][1]) < 0.01
        for nh in (80, 160, 320):
            assert row[f'nh{nh}']['kcl_residual_A'] < 1e-9 and row[f'nh{nh}']['parseval_out_frac'] > 0.99
        assert abs(row['nh320']['C36_rms'] / row['nh80']['C36_rms'] - 1) < 0.01
    print('selftest ok: zeta', round(z, 4), 'analytic', round(ana, 4), '|Z|peak', round(zf, 3),
          '| ripple KCL/charge/Parseval ok')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=pathlib.Path)
    ap.add_argument('--rd', type=float, default=1.0, help='VIN damper resistor (ohm)')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    selftest()
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    R = dict(assumption_level='passive/averaged screening only; not closed-loop qualification',
             bias_bounds={f'{k[0]}@{k[1]}V': v for k, v in BIAS.items()})
    R['banks_uF'] = {
        'VIN ceramics C6/C7/C15/C16/C24 @20V': [round(VIN_CER_LO * 1e6, 1), round(VIN_CER_HI * 1e6, 1)],
        'P12_RAW 4x22u @12.2V': [round(x * 1e6, 1) for x in mlcc(4, 22, '22u25V_1206', 12.2)[:2]],
        'P5_RAW 4x22u @5V': [round(x * 1e6, 1) for x in mlcc(4, 22, '22u25V_1206', 5.0)[:2]],
        'N12_RAW 5x22u @12V': [round(x * 1e6, 1) for x in mlcc(5, 22, '22u25V_1206', 12.2)[:2]],
        'C34-36 can 100u': [round(100 * CAN_C_LO, 1), round(100 * CAN_C_HI, 1)],
        'C5 can 47u': [round(47 * CAN_C_LO, 1), round(47 * CAN_C_HI, 1)]}
    R['datasheet_cap_figures_uF'] = {
        'TPS62933 12V/500k table min': 10, 'TPS62933 5V/1.2M table min': 10,
        # SNVSC40E Table 9-1 columns: NOMINAL COUT (RATED CAPACITANCE) / MINIMUM COUT (RATED
        # CAPACITANCE). Buck-topology guide only: rated, not effective, not an IBB minimum.
        'LMR38020 Table 9-1 buck guide, RATED (not effective, not IBB min)': {
            '12V 400kHz': {'nominal': '1x22', 'minimum_rated': '1x15'},
            '12V 1MHz': {'nominal': '2x10', 'minimum_rated': '1x10'}},
        'LMR38020 CIN min (effective)': 4.7}
    R['eq21_cout_min_uF'] = {
        'P12 dI=1A dV=3%': round(tps62933_eq21(12.194, 20, 6.8e-6, 1.2e6, 1.0, 0.366) * 1e6, 1),
        'P5 dI=1A dV=3%': round(tps62933_eq21(4.985, 20, 3.3e-6, 1.977e6, 1.0, 0.15) * 1e6, 1)}
    R['vin_stability'] = vin_study(a.rd)
    zin = V_MIN ** 2 / P_MAX
    R['middlebrook_zin_ohm'] = round(zin, 3)
    for o, w in R['vin_stability'].items():
        w['margin_dB'] = round(20 * math.log10(zin / w['zmax']), 1)
    R['rd_sweep'] = {}
    for rd in (0.1, 0.33, 0.5, 1.0, 2.0):
        st = vin_study(rd)
        R['rd_sweep'][rd] = {o: dict(zeta=round(st[o]['zeta'], 3),
                                     margin_dB=round(20 * math.log10(zin / st[o]['zmax']), 1))
                             for o in ('B_RCx2', 'B_RCx4')}
    R['zratio_no_can_vs_can'] = {}
    for rail in RAILS:
        fz = np.array([10e3, 30e3, 60e3, 100e3])
        za = raw_ladder(rail, 'A', 'lo', 0.3, None).impedance(0, fz)
        zb = raw_ladder(rail, 'B0', 'lo', 0.3, None).impedance(0, fz)
        zc = raw_ladder(rail, 'A', 'lo', 3.0, None).impedance(0, fz)
        R['zratio_no_can_vs_can'][rail] = {f'{int(f/1e3)}kHz': [round(abs(b / a), 2), round(abs(b / c), 2)]
                                           for f, a, b, c in zip(fz, za, zb, zc)}
    R['ibb'] = ibb_screens()
    R['input_ripple'] = input_ripple()
    R['inrush'] = inrush()
    R['can_life_h'] = can_life()
    R['stress'] = stress()
    R['ripple_outputs'] = ripple_outputs()
    R['ripple_ibb_input'] = ripple_ibb_input()
    R['ripple_vin_bucks'] = ripple_vin_bucks()
    R['cost_panel_quotes'] = cost_delta()
    R['ripple_checks'] = ripple_checks()
    # C5: U2+U3 (bucks) and U4 shares are unsynchronised, different-frequency sources -> quadrature.
    # C36: taken ONLY from the coherent two-node U4 model (it already contains the U4 output
    # injection); the single-node N12_RAW split in ripple_outputs is a diagnostic, not added.
    c5 = math.hypot(R['ripple_vin_bucks']['A']['can_rms'], R['ripple_ibb_input']['A']['can_c5_rms'])
    R['can_ripple_screen'] = dict(
        C5_rms_A=round(c5, 4), C5_limit_A=[round(CAN_RIPPLE_120HZ['C5'] * m, 3) for m in CAN_FMULT],
        C36_rms_A=R['ripple_ibb_input']['A']['can_c36_rms'],
        C36_rms_A_single_node_diagnostic=R['ripple_outputs']['N12_RAW']['A']['can_rms'],
        C34_rms_A=R['ripple_outputs']['P12_RAW']['A']['can_rms'],
        C35_rms_A=R['ripple_outputs']['P5_RAW']['A']['can_rms'],
        C34_36_limit_A=[round(CAN_RIPPLE_120HZ['C34_36'] * m, 3) for m in CAN_FMULT],
        can_P_mW_model={k: round(1e3 * v ** 2 * e, 2) for k, v, e in (
            ('C5', c5, CAN['C5']['esr'][2]),
            ('C36', R['ripple_ibb_input']['A']['can_c36_rms'], CAN['C34_36']['esr'][2]))},
        note='max over swept corners under assumed ESR/ESL brackets; equal sharing inside a bank; '
             'HF multiplier is an MVG-family proxy; dissipation uses cold-high ESR with the max current '
             '(not a coincident corner): assumed-model figures, not a thermal measurement')
    R['vo_hi'] = {k: dict(full_temp=v['vo_hi'], tj_0_85C=v['vo_hi_0_85C'], ov_lo=v['ov_lo'],
                          margin_full=round(v['ov_lo'] - v['vo_hi'], 3),
                          margin_0_85C=round(v['ov_lo'] - v['vo_hi_0_85C'], 3)) for k, v in RAILS.items()}

    # VIN transients at the worst-damped grid corner (lowest R, highest L, low C)
    worst = dict(L=2.0e-6, R=0.02, Rb=0.02, Ron=0.019, cer='lo', esr_i=1, csrc='none', c5c='lo')
    R['vin_transient_case'] = worst
    fz = np.logspace(3, 6, 240)
    zp = []
    for opt in VIN_OPTS:
        lad, k = vin_ladder(opt, worst['L'], worst['R'], worst['Rb'], worst['Ron'], VIN_CER_LO,
                            CAN['C5']['esr'][2], None, a.rd, 'lo')
        zp.append((opt + (' (C5 low C, cold ESR)' if opt == 'A' else ''), fz, np.abs(lad.impedance(k, fz))))
    svg_plot(out / 'vin_zs.svg', zp, 'VIN source impedance seen by converters, worst corner (2 uH, 0.08 ohm)',
             'frequency (Hz)', '|Zs| (ohm)', logx=True, logy=True,
             hlines=((V_MIN ** 2 / P_MAX, '|Zin| 17.2V/72W'), (V_MIN ** 2 / P_MAX / 2, '6 dB screen')))
    tr = {}
    plots_step, plots_rel = [], []
    for opt in VIN_OPTS:
        t, v, vdc = vin_transient(opt, a.rd, worst, 20.0, P_MAX)
        tr[opt] = dict(step_up_min=round(float(v.min()), 3), step_up_dc=round(vdc, 3))
        plots_step.append((opt, t * 1e6, v))
        t2, v2, _ = vin_transient(opt, a.rd, worst, P_MAX, 5.0, vs=21.0)
        tr[opt]['release_peak_vs21'] = round(float(v2.max()), 3)
        plots_rel.append((opt, t2 * 1e6, v2))
    R['vin_transient'] = tr
    svg_plot(out / 'vin_step.svg', plots_step, 'VIN: 20 -> 72 W input step (10 us), worst source corner',
             'time (us)', 'VIN (V)')
    svg_plot(out / 'vin_release.svg', plots_rel, 'VIN: 72 -> 5 W release, 21 V source (D10 blocks reverse)',
             'time (us)', 'VIN (V)', hlines=((23.21, 'U5 OVP low corner'),))

    raw = {}
    rack = dict(R=0.08, L=0.5e-6, C=470e-6, esr=0.1)
    for rail in RAILS:
        p = RAILS[rail]
        rr = {}
        pl = []
        for opt in RAW_OPTS:
            for nd in (2, 8, 16):
                peaks = []
                for corner in ('lo', 'hi'):
                    for esr in CAN['C34_36']['esr']:
                        if opt != 'A' and esr != CAN['C34_36']['esr'][0]:
                            continue
                        t, v = raw_release(rail, opt, corner, esr, nd)
                        peaks.append(float(v.max()) - p['vo_hi'])
                        if nd == 8 and corner == 'lo' and esr == CAN['C34_36']['esr'][1]:
                            pl.append((opt, t * 1e6, v))
                        if nd == 8 and corner == 'lo' and opt != 'A':
                            pl.append((opt, t * 1e6, v))
                rr[f'{opt} N={nd}'] = dict(overshoot_V=[round(min(peaks), 3), round(max(peaks), 3)],
                                           ov_margin_V=round(p['ov_lo'] - p['vo_hi'], 3))
            t, v = raw_release(rail, opt, 'lo', CAN['C34_36']['esr'][1], 8, rack=rack, at_rack=True)
            rr[f'{opt} rack-side release N=8'] = round(float(v.max()) - p['vo_hi'], 3)
        raw[rail] = rr
        svg_plot(out / f'{rail}_release.svg', pl, f'{rail}: {p["i_rel"]} A release at RAW, N=8, low-C corner',
                 'time (us)', 'V (magnitude)', hlines=((p['ov_lo'], 'protection OV low'),))
        zs = []
        for opt in RAW_OPTS:
            for esr in ((CAN['C34_36']['esr'][0], CAN['C34_36']['esr'][1]) if opt == 'A' else (0.3,)):
                f, z = raw_impedance(rail, opt, 'lo', esr, rack)
                lab = f'{opt} ESR {esr}' if opt == 'A' else opt
                zs.append((lab, f, np.abs(z)))
                raw[rail][f'Zpk {lab}'] = round(float(np.abs(z).max()), 4)
        svg_plot(out / f'{rail}_zout.svg', zs, f'{rail}: passive |Z| with 470 uF rack behind 0.08 ohm/0.5 uH',
                 'frequency (Hz)', '|Z| (ohm)', logx=True, logy=True)
    R['raw_release'] = raw
    R['screens'] = screens(R)
    (out / 'results.json').write_text(json.dumps(R, indent=1, default=float))
    print(json.dumps(R, indent=1, default=float))


if __name__ == '__main__':
    main()
