#!/usr/bin/env python3
"""S8 single-board pre-calculations: ceramic banks, VIN damper, soft start into rack capacitance,
overvoltage guard, startup window, input and connector budgets, board area.

  python3 -B tools/s8_calcs.py --out docs/s8-single     (numpy; pcbnew for the area section)

SCREENING ONLY. Every value comes from the S8 circuit table (tools/circuit_s8.py) and the cited
datasheet figures; MLCC DC-bias retention, ESR and the VIN source corners reuse the bounded
assumptions of the capacitor study (tools/capacitor-study/cap_study.py, docs/capacitor-study/).
The VIN and rail-release models are passive ladders with an averaged constant-power load or an
imposed converter current; no TPS62933F/LMR38020F control loop is modelled. Not a closed-loop
forecast, a thermal proof or a bench qualification.
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'capacitor-study'))
import cap_study as cs  # noqa: E402
import circuit_s8  # noqa: E402

MODULE = HERE.parent
SOURCES = {
    'TPS62933F': 'TI SLUSEA4D (https://www.ti.com/lit/ds/symlink/tps62933f.pdf): IHS_LIMIT 4.2/5/5.8 A, '
                 'ILS_LIMIT 2.9/3.8/4.5 A, ISS 4.5/5.5/6.5 uA, tSS = CSS x 0.8 V / ISS, OVP 112/115/118 %, UVP 65 % '
                 '+ 256 us then hiccup 10.5 x tSS, VFB 784-816 mV (-40..150 C), Table 10-2 effective COUT, Eq. 21',
    'LMR38020': 'TI SNVSC40E (https://www.ti.com/lit/ds/symlink/lmr38020.pdf): IHS 2.6/3.2/3.8 A, ILS 1.8/2.3/2.8 A, '
                'tSS 4 ms, OCP blanking 18 ms typ at power-up, hiccup 76 ms, COUT <= ~10 x design value or 1000 uF',
    'TPS1663': 'TI SLVSET9G (https://www.ti.com/lit/ds/symlink/tps1663.pdf): tSD(dly) SHDN -> FET off 0.8-1.5 us, '
               'I(dVdT) 1.775/2/2.225 uA, GAIN(dVdT) 23.5/25/26',
    'TPS3808': 'TI SBVS050N (https://www.ti.com/lit/ds/symlink/tps3808.pdf): delay (s) = CT (nF) / 175 + 0.5 ms; '
               'open-CT delay 12/20/28 ms (+-40 %)',
    'TPS7A16': 'TI SBVS171F (https://www.ti.com/lit/ds/symlink/tps7a16.pdf): overall accuracy +-2 %',
    'LM2901': 'TI SLCS006Z (https://www.ti.com/lit/ds/symlink/lm2901.pdf): VIO 7 mV (25 C) / 15 mV (-40..125 C), '
              'input bias -500 nA, common mode 0..VCC-2 V (one input in range gives a proper output state)',
    'SMAJ5.0A': 'JLC/LCSC C113952 listing (MDD): VRWM 5.0 V, VBR 6.4-7.0 V class, VC 9.2 V at 43.5 A (10/1000 us), '
                'IR <= 800 uA at VRWM',
    'cap_study': 'docs/capacitor-study/README.md bounds (BIAS, tol/temp/aging, ESR, source grid)',
}


def table():
    parts = {p['ref']: p for p in circuit_s8.circuit() if not p['ref'].startswith('#')}

    def val(ref):
        s = parts[ref]['value']
        return float(s[:-1]) * {'k': 1e3, 'u': 1e-6, 'n': 1e-9}[s[-1]] if s[-1] in 'kun' else float(s)
    return parts, val


def banks(parts):
    """Effective capacitance bounds (uF) per bank under the capacitor-study bias bands."""
    def count(net, value):
        return sum(1 for p in parts.values() if p['value'] == value and p['fp'] == 'C1206'
                   and net in p['pins'].values() and 'GND' in p['pins'].values())
    n = {'+12V': count('+12V', '22u'), '+5V': count('+5V', '22u'), '-12V': count('-12V', '22u'),
         'VIN': count('VIN', '10u'), 'damper': count('_VIN_DAMP', '10u')}
    assert n == {'+12V': 6, '+5V': 6, '-12V': 7, 'VIN': 5, 'damper': 2}, n
    eff = {'+12V': cs.mlcc(n['+12V'], 22, '22u25V_1206', 12.2), '+5V': cs.mlcc(n['+5V'], 22, '22u25V_1206', 5.0),
           '-12V': cs.mlcc(n['-12V'], 22, '22u25V_1206', 12.2), 'VIN': cs.mlcc(n['VIN'], 10, '10u50V_1206', 20.0),
           'damper': cs.mlcc(n['damper'], 10, '10u50V_1206', 20.0)}
    s7 = {'+12V': cs.mlcc(4, 22, '22u25V_1206', 12.2), '+5V': cs.mlcc(4, 22, '22u25V_1206', 5.0),
          '-12V': cs.mlcc(5, 22, '22u25V_1206', 12.2)}
    ti = {'+12V': 'TPS62933 Table 10-2 (12 V): typ 15 / min 10 uF effective',
          '+5V': 'TPS62933 Table 10-2 (5 V, 1.2 MHz): typ 20 / min 10 uF effective',
          '-12V': 'LMR38020 Table 9-1 is a BUCK guide in rated C (12 V/1 MHz 2 x 10u, 12 V/400 kHz 1 x 22u); '
                  'IBB: no TI table; max ~10 x design or 1000 uF incl. the rack',
          'VIN': 'TPS62933: 10 uF + 100 nF per converter; LMR38020 CIN >= 4.7 uF effective (C25 + C26, unchanged)',
          'damper': 'series-R damper branch, capacitor study option B_RCx2'}
    out = {k: dict(parts=n[k], eff_uF=[round(v[0] * 1e6, 1), round(v[1] * 1e6, 1)], bank_esr_mohm=round(v[2] * 1e3, 2),
                   reference=ti[k]) for k, v in eff.items()}
    for k, v in s7.items():
        out[k]['S7_ceramic_only_eff_uF'] = [round(v[0] * 1e6, 1), round(v[1] * 1e6, 1)]
        out[k]['S7_can'] = '100u 35V can (57.8-120 uF, ESR 0.3-3 ohm, removed)'
    return out, eff


def ripple_and_steps(eff):
    """Switching ripple (CCM, ideal waveforms) and load-step deviation estimates at the LOW C corner."""
    res = {}
    for rail, vo, L, fsw in (('+12V', 12.194, 6.8e-6, 1.2e6), ('+5V', 4.985, 3.3e-6, 1.977e6)):
        c_lo, _, esr = eff[rail]
        rows = []
        for vin in (17.2, 20.0, 24.1):
            D = vo / vin
            dil = (vin - vo) * D / (L * fsw)
            v_c = dil / (8 * fsw * c_lo)
            v_esr = dil * esr
            K = dil / 3.0                                     # TI Eq. 21 ripple ratio vs 3 A device rating
            dv_step = 1.5 / (fsw * c_lo * K) * ((1 - D) * (1 + K) + K * K / 12 * (2 - D))
            rows.append(dict(vin=vin, D=round(D, 3), dIL_A=round(dil, 3), ripple_C_mV=round(v_c * 1e3, 2),
                             ripple_ESR_mV=round(v_esr * 1e3, 2), step_1A5_dev_mV=round(dv_step * 1e3)))
        res[rail] = dict(L_uH=L * 1e6, fsw_kHz=fsw / 1e3, rows=rows,
                         note='Eq. 21 inverted for a 1.5 A step at the low-C corner (TI: ~8 cycles to respond)')
    c_lo, _, esr = eff['-12V']
    rows = []
    for vin in (17.2, 20.0, 24.1):
        vo, L, fsw, io = 11.989, 15e-6, 0.79e6, 1.0
        D = vo / (vin + vo)
        il = io / (1 - D)
        dil = vin * D / (L * fsw)
        v_c = io * D / (fsw * c_lo)
        v_esr = (il + dil / 2) * esr
        dv_step = 0.5 * 8 / (fsw * c_lo)                       # 0.5 A step, 8 cycles uncovered (rule of thumb)
        rows.append(dict(vin=vin, D=round(D, 3), IL_avg_A=round(il, 3), IL_pk_A=round(il + dil / 2, 3),
                         ripple_C_mV=round(v_c * 1e3, 1), ripple_ESR_mV=round(v_esr * 1e3, 2),
                         step_0A5_dev_mV=round(dv_step * 1e3), cout_rms_A=round(io * math.sqrt(D / (1 - D)), 3),
                         rhpz_kHz=round((vo / io) * (1 - D) ** 2 / (2 * math.pi * D * L) / 1e3, 1)))
    res['-12V'] = dict(L_uH=15, fsw_kHz=790, io_A=1.0, rows=rows,
                       note='IBB: the output bank carries the full load during the on time; per-part rms '
                            '<= 2 x share of cout_rms (imbalance x2) -> well below 1206 heating limits')
    return res


def vin_damper(rd):
    """Middlebrook screen of the all-ceramic VIN bus with the series-R damper (study option B_RCx2)."""
    import numpy as np
    zin = cs.V_MIN ** 2 / cs.P_MAX
    freqs = np.logspace(3, 6, 240)
    out = {}
    for opt in ('B0', 'B_RCx2'):
        worst = dict(zeta=9.0, zmax=0.0, unstable=0, n=0)
        for c in cs.vin_grid():
            if c['esr_i'] != 0 or c['c5c'] != 'lo':
                continue
            cer = cs.VIN_CER_LO if c['cer'] == 'lo' else cs.VIN_CER_HI
            lad, k = cs.vin_ladder(opt, c['L'], c['R'], c['Rb'], c['Ron'], cer, 0.0, cs.CSRC[c['csrc']], rd, c['c5c'])
            g = np.zeros(len(lad.nodes)); g[k] = -cs.P_MAX / cs.V_MIN ** 2
            z, uns = cs.min_damping(lad.linear(g))
            worst['n'] += 1; worst['unstable'] += int(uns)
            if z < worst['zeta']:
                worst.update(zeta=z, zeta_case=c)
            if c['L'] == 2.0e-6 or c['csrc'] != 'none':
                zm = float(np.max(np.abs(lad.impedance(k, freqs))))
                if zm > worst['zmax']:
                    worst.update(zmax=zm, zmax_case=c)
        worst['margin_dB'] = round(20 * math.log10(zin / worst['zmax']), 1)
        worst['zeta'] = round(worst['zeta'], 3); worst['zmax'] = round(worst['zmax'], 3)
        out[opt] = worst
    study = json.loads((MODULE / 'docs/capacitor-study/generated/results.json').read_text())['vin_stability']['A']
    out['S7_can_reference'] = dict(zeta=round(study['zeta'], 3), zmax=round(study['zmax'], 3), margin_dB=study['margin_dB'])
    out['Zin_ohm'] = round(zin, 3)
    out['load'] = f'{cs.P_MAX:.0f} W constant power at {cs.V_MIN} V (upper estimate, linearised)'
    c_d_hi = cs.mlcc(2, 10, '10u50V_1206', 20.0)[1]
    sr = 2.225e-6 * 26 / (22e-9 * 0.9)                       # U5 dVdt fastest corner (cap study inrush())
    out['R92_stress'] = dict(ripple_rms_mA_from_study=26.7, ripple_P_mW=round(0.0267 ** 2 * rd * 1e3, 2),
                             inrush_mA=round(c_d_hi * sr * 1e3, 1),
                             step_energy_uJ=round(0.5 * c_d_hi * 1.5 ** 2 * 1e6, 1),
                             note='1.5 V VIN dip assumed for the step energy; 1206 250 mW part')
    return out


def rail_release():
    """Imposed-trajectory load release (study model) with the S8 banks (study option B_x2) and the
    rack directly on the rail, against the new overvoltage-guard minimum."""
    rack = dict(R=0.08, L=0.5e-6, C=470e-6, esr=0.1)
    res = {}
    for rail in ('P12_RAW', 'P5_RAW', 'N12_RAW'):
        p = cs.RAILS[rail]
        rr = {}
        for nd in (2, 8, 16):
            peaks = []
            for corner in ('lo', 'hi'):
                t, v = cs.raw_release(rail, 'B_x2', corner, cs.CAN['C34_36']['esr'][0], nd)
                peaks.append(float(v.max()) - p['vo_hi'])
            rr[f'N={nd}'] = [round(min(peaks), 3), round(max(peaks), 3)]
        t, v = cs.raw_release(rail, 'B_x2', 'lo', cs.CAN['C34_36']['esr'][0], 8, rack=rack, at_rack=True)
        rr['rack-side release N=8'] = round(float(v.max()) - p['vo_hi'], 3)
        rr['vo_hi_V'] = p['vo_hi']
        res[{'P12_RAW': '+12V', 'P5_RAW': '+5V', 'N12_RAW': '-12V'}[rail]] = rr
    return res


def soft_start(val):
    css = val('C9')
    assert css == val('C18')
    tss = {'min_ms': css * 0.9 * 0.8 / 6.5e-6 * 1e3, 'typ_ms': css * 0.8 / 5.5e-6 * 1e3,
           'max_ms': css * 1.1 * 0.8 / 4.5e-6 * 1e3}
    s7 = 22e-9 * 0.9 * 0.8 / 6.5e-6
    out = {'tSS_ms': {k: round(v, 2) for k, v in tss.items()}, 'S7_tSS_min_ms': round(s7 * 1e3, 2)}
    for rail, vo, L, fsw, iload in (('+12V', 12.194, 6.8e-6, 1.2e6, 2.5), ('+5V', 4.985, 3.3e-6, 1.977e6, 2.5)):
        dil = (24.1 - vo) * (vo / 24.1) / (L * fsw)
        avail = 4.2 - dil / 2                                  # IHS_LIMIT min minus half ripple
        t = tss['min_ms'] / 1e3
        out[rail] = dict(avail_A=round(avail, 2),
                         track_ramp_max_C_mF={'full_load': round((avail - iload) * t / vo * 1e3, 2),
                                              'no_load': round(avail * t / vo * 1e3, 2),
                                              'S7_22n_full_load': round((avail - iload) * s7 / vo * 1e3, 2)},
                         reach_65pct_before_hiccup_max_C_mF=round((avail - iload) * (t + 256e-6) / (0.65 * vo) * 1e3, 2))
    # LMR38020 IBB: valley limit ILS min + half ripple, output share (1 - D), within the 18 ms OCP blanking
    vin, vo, L, fsw = 20.0, 11.989, 15e-6, 0.79e6
    D = vo / (vin + vo)
    il = 1.8 + vin * D / (L * fsw) / 2
    io_max = il * (1 - D)
    out['-12V'] = dict(io_max_A=round(io_max, 2), blank_ms=18,
                       max_C_mF={'full_load_1A': round((io_max - 1.0) * 0.018 / vo * 1e3, 2),
                                 'no_load': round(io_max * 0.018 / vo * 1e3, 2)},
                       ti_limit='<= ~10 x design COUT or 1000 uF, whichever is smaller (SNVSC40E 9.2.2.5)')
    out['rack_reference'] = ('Typical Eurorack module: 10-47 uF per rail; 20 modules x 22 uF = 0.44 mF per rail. '
                             'S7 isolated this through the eFuse/LM5067 dV/dt; S8 relies on the converter soft start')
    return out


def ov_guard(val, release):
    """Guard thresholds over every corner (V3V3 +-2 %, resistors 1 % + 1 % TCR, LM2901 offset 15 mV)."""
    lo, hi = .99 * .99, 1.01 * 1.01

    def corners(f):
        vals = [f(v3, a, b, c, d, e) for v3 in (3.3 * .98, 3.3 * 1.02) for a in (lo, hi) for b in (lo, hi)
                for c in (lo, hi) for d in (lo, hi) for e in (-.015, .015)]
        return [min(vals), f(3.3, 1, 1, 1, 1, 0), max(vals)]

    def ref(v3, a, b):
        return v3 * val('R74') * b / (val('R73') * a + val('R74') * b)
    out = {}
    for rail, top, bot, fbt, fbb, vref, ovp in (('+12V', 'R93', 'R94', 'R8', 'R9', (.784, .8, .816), True),
                                                 ('+5V', 'R95', 'R96', 'R11', 'R12', (.784, .8, .816), True),
                                                 ('-12V', 'R98', 'R99', 'R14', 'R15', (.985, 1.0, 1.015), False)):
        if rail == '-12V':
            g = corners(lambda v3, a, b, c, d, e: (v3 * val(bot) * d - (ref(v3, a, b) + e) * (val(top) * c + val(bot) * d))
                        / (val(top) * c))
        else:
            g = corners(lambda v3, a, b, c, d, e, t=top, u=bot: (ref(v3, a, b) + e) * (1 + val(t) * c / (val(u) * d)))
        sp = [v * (1 + val(fbt) * f1 / (val(fbb) * f2)) for v, f1, f2 in ((vref[0], lo, hi), (vref[1], 1, 1), (vref[2], hi, lo))]
        worst_release = release[rail]['N=16'][1] + release[rail]['vo_hi_V']
        tau = (val(top) * val(bot) / (val(top) + val(bot))) * val({'+12V': 'C63', '+5V': 'C64', '-12V': 'C66'}[rail])
        row = dict(guard_V=[round(x, 2) for x in g], setpoint_V=[round(x, 3) for x in sp],
                   worst_imposed_release_peak_V=round(worst_release, 2),
                   release_margin_to_guard_min_V=round(g[0] - worst_release, 2), filter_us=round(tau * 1e6, 1))
        if ovp:
            o = [1.12 * sp[0], 1.15 * sp[1], 1.18 * sp[2]]
            row.update(converter_OVP_V=[round(x, 2) for x in o], margin_nominal_V=round(g[1] - o[1], 2),
                       margin_worst_V=round(g[0] - o[2], 2))
        else:
            row.update(converter_OVP_V='none (LMR38020 has no output OVP)', margin_to_setpoint_max_V=round(g[0] - sp[2], 2))
        out[rail] = row
    out['response_us'] = dict(filter='3-8 (RC)', comparator=1.3, hc74_preset=0.05, tps1663_shdn=1.5,
                              total_after_crossing='~5-15 us + RC; then U5 off, rails decay')
    out['note'] = ('Nominal guard is ~2.5 V (+12) / ~0.8 V (+5) above the converter OVP; at the stacked worst '
                   'corner the bands touch, so a false trip (safe: latched off, press RESET) is a bench item. '
                   'A shorted high side or an open feedback resistor drives the rail toward VIN (~20 V) or, for the '
                   'inverting stage, beyond -15 V: all three trip with margin.')
    return out


def startup_window(val):
    t = val('C49') * 1e9 / 175 + .0005
    budget = dict(U5_ramp_ms=round(20 / (1.775e-6 * 23.5 / (22e-9 * 1.1)) * 1e3, 1), PGOOD_deglitch_ms=13,
                  TPS62933F_SS_max_ms=round(val('C9') * 1.1 * 0.8 / 4.5e-6 * 1e3, 1), LMR38020_SS_plus_blank_ms=18 + 4)
    total = sum(budget.values())
    return dict(typ_s=round(t, 3), min_s_screen=round(t * .6 * .9, 3), S7_typ_s=round(1e-6 * 1e9 / 175 + .0005, 2),
                rail_up_budget_ms=budget, rail_up_total_ms=round(total, 1),
                ratio_min_window_to_budget=round(t * .6 * .9 / (total / 1e3), 1))


def input_budget():
    out_w = {'+12V': 12.194 * 2.5, '+5V': 4.985 * 2.5, '-12V': 11.989 * 1.0}
    eff = {'+12V': .93, '+5V': .88, '-12V': .85}            # assumed from datasheet efficiency curves
    conv_in = sum(out_w[k] / eff[k] for k in out_w)
    i = conv_in / 19.2
    losses = {'D10_0.75V': 0.75 * i, 'U5_31mohm': 0.031 * i * i, 'aux_logic_LEDs': 0.5}
    p_in = conv_in + sum(losses.values())
    removed = {'U6_U7_2x31mohm_at_2.5A': 2 * 0.031 * 2.5 ** 2, 'LM5067_path_50mohm+Q4_at_1A': 1.0 * (0.05 + 0.1)}
    return dict(outputs_W=round(sum(out_w.values()), 1), converter_input_W=round(conv_in, 1),
                losses_W={k: round(v, 2) for k, v in losses.items()}, input_W=round(p_in, 1),
                input_A_at_20V=round(p_in / 20, 2), U5_limit_screen_A=[3.693, 4.186, 4.698],
                margin_to_U5_min_A=round(3.693 - p_in / 20, 2),
                eFuse_losses_removed_W={k: round(v, 2) for k, v in removed.items()},
                efficiency_assumption=eff, note='planning estimate; efficiencies are assumptions, not measurements')


def connectors():
    targets = {'+12V': 2.5, '+5V': 2.5, '-12V': 1.0}
    gnd = sum(targets.values())
    one = {k: round(v / 2, 3) for k, v in targets.items()}; one['GND (no cancellation)'] = round(gnd / 6, 3)
    two = {k: round(v / 4, 3) for k, v in targets.items()}; two['GND (no cancellation)'] = round(gnd / 12, 3)
    return dict(per_contact_A_one_header=one, per_contact_A_two_headers_equal_split=two,
                contacts_per_header={'+12V': 2, '+5V': 2, '-12V': 2, 'GND': 6},
                guidance='typical 2.54 mm IDC/ribbon contact ~1 A: use both headers above ~2 A per rail; '
                         'unequal cable lengths/loads do not split equally')


def tvs(eff):
    c_hi = eff['VIN'][1] + eff['damper'][1]
    e = 0.5 * c_hi * (20 ** 2 - 7 ** 2)
    return dict(part='SMAJ5.0A', vrwm=5.0, vbr_min_1mA=6.4, vc_at_43A5=9.2, ir_max_at_vrwm_uA=800,
                rail_max_setpoint_V=5.26, vin_cap_dump_mJ=round(e * 1e3, 1), rating_J_10_1000us=0.4,
                note='Above VRWM only at the stacked worst-case setpoint; <= ~5 mW even at 1 mA. Transient clamp '
                     'only; sustained overvoltage is removed by U20 -> FAULT -> U5')


def area(parts):
    try:
        import pcbnew
    except ImportError:
        return {'skipped': 'pcbnew not importable'}
    lib = str(MODULE / 'hardware' / 'USBPOWER45.pretty')
    fpmap = {'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric', 'C0603': 'C_0603_1608Metric',
             'C1206': 'C_1206_3216Metric', 'F1206': 'Fuse_1206_3216Metric', 'SMA': 'D_SMA', 'SMB': 'D_SMB',
             'SMC': 'D_SMC', 'LED0603': 'LED_0603_1608Metric', 'SOT89': 'SOT-89-3', 'SOT23': 'SOT-23',
             'USBC': 'HRO-TYPE-C-31-M-12', 'SSOP10': 'SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm', 'SOT583': 'SOT-583-8',
             'PPAD8': 'TI_SO-PowerPAD-8_ThermalVias',
             'PWP20': 'HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm_Mask2.96x2.96mm_ThermalVias',
             'TP': 'TestPoint_Pad_D1.0mm', 'DGN8': 'TPS7A16_DGN0008C', 'SOT235': 'SOT-23-5', 'SOT236': 'SOT-23-6',
             'SO14': 'SOIC-14_3.9x8.7mm_P1.27mm', 'SLO1040': 'L_SLO1040H6R8MTT',
             'IDC16': 'IDC-Header_2x08_P2.54mm_Vertical_Wurth_61201621621', 'TL3340': 'SW_TL3340AF160QG_HandSolder',
             'LED3EDGE': 'LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge'}
    cache = {}

    def cy(fp):
        if fp not in cache:
            f = pcbnew.FootprintLoad(lib, fpmap[fp])
            poly = f.GetCourtyard(pcbnew.F_CrtYd)
            cache[fp] = poly.Area() / 1e12
        return cache[fp]
    s8 = sum(cy(p['fp']) for p in parts.values())
    big = {'J2+J3': 2 * cy('IDC16'), 'L1-L3': 3 * cy('SLO1040'), 'panel J1/SW1/D8': cy('USBC') + cy('TL3340') + cy('LED3EDGE'),
           'test pads': sum(cy(p['fp']) for r, p in parts.items() if r.startswith('TP'))}
    import mechanics_s8
    from mechanics45 import carrier_outline, carrier_xy
    g = mechanics_s8.geometry()
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for y, z in carrier_outline(g):
        poly.Append(*(pcbnew.FromMM(v) for v in carrier_xy(y, z)))
    poly.Deflate(pcbnew.FromMM(1.0), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
    inset = poly.Area() / 1e12     # S8 outline Y14..114.5 x Z2..50 with both bracket cutbacks, 1 mm edge rule
    return dict(S8_courtyard_mm2=round(s8), board_inset_mm2=round(inset), fill=round(s8 / inset, 3),
                outline=f'Y{g["carrier_Y_mm"][0]:g}..{g["carrier_Y_mm"][1]:g} x Z{g["carrier_Z_mm"][0]:g}..{g["carrier_Z_mm"][1]:g}',
                routed_R3_fill={'base': 0.637, 'top': 0.645}, groups_mm2={k: round(v) for k, v in big.items()},
                note='courtyard polygons from the pinned footprints, panel parts counted whole (they overhang the '
                     'front edge by design). The placed P1 board record is docs/s8-single/board-p1.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--skip-sim', action='store_true', help='skip the VIN grid and rail-release simulations')
    a = ap.parse_args()
    parts, val = table()
    R = {'status': 'S8 pre-calculation screen, not a closed-loop or bench qualification', 'sources': SOURCES}
    R['banks'], eff = banks(parts)
    R['ripple_and_steps'] = ripple_and_steps(eff)
    if not a.skip_sim:
        R['vin_damper'] = vin_damper(val('R92'))
        R['rail_release'] = rail_release()
    else:
        R['rail_release'] = json.loads((a.out / 'calcs.json').read_text())['rail_release']
    R['soft_start'] = soft_start(val)
    R['ov_guard'] = ov_guard(val, R['rail_release'])
    R['startup_window'] = startup_window(val)
    R['input_budget'] = input_budget()
    R['connectors'] = connectors()
    R['tvs'] = tvs(eff)
    R['area'] = area(parts)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'calcs.json').write_text(json.dumps(R, indent=2) + '\n')
    print(json.dumps({k: R[k] for k in R if k not in ('sources', 'ripple_and_steps', 'banks')}, indent=1)[:6000])


if __name__ == '__main__':
    main()
