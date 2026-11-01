#!/usr/bin/env python3
"""S8 single-board pre-calculations: ceramic banks, VIN damper, soft start into rack capacitance,
overvoltage guard and VPD-powered comparators, S8.3 +5V series disconnect (OVLO/current/ramp corners,
shorted-high-side delay sensitivity, split banks and thermal screens), startup window, input and
connector budgets, board area.

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
    'LM2901B': 'TI SLCS006Z 6.8 (https://www.ti.com/lit/ds/symlink/lm2901b.pdf): VIO 3.5 mV (25 C) / 5.5 mV '
               '(-40..125 C), IB -25 nA / -50 nA, common mode (V-) to (V+) - 1.5 V at 25 C, (V+) - 2.0 V full range; '
               'input below -0.3 V: output can be incorrect and excessive input current can flow (footnote 1)',
    'TLV431B': 'TI SLVS139Z (https://www.ti.com/lit/ds/symlink/tlv431.pdf): TLV431BI VREF 1.234-1.246 V (25 C), '
               '1.224-1.259 V (-40..85 C) at IK 10 mA, |zKA| 0.25/0.4 ohm, IK(min) 55/100 uA, IK 0.1-15 mA; stable '
               'without a capacitor, Fig. 5-18/5-19: oscillation region about 3 nF..1 uF at VKA = VREF; DBZ pins REF 1, '
               'CATHODE 2, ANODE 3 (Table 4-1)',
    'BAT54SL': 'onsemi BAT54SLT1/D rev 17: VF 0.24 V max at 0.1 mA, 0.32 V at 1 mA; IR 2 uA max at 25 V (25 C); '
               'pin 1 anode, 2 cathode, 3 cathode-anode',
    'SMAJ5.0A': 'JLC/LCSC C113952 listing (MDD): VRWM 5.0 V, VBR 6.4-7.0 V class, VC 9.2 V at 43.5 A (10/1000 us), '
                'IR <= 800 uA at VRWM',
    'cap_study': 'docs/capacitor-study/README.md bounds (BIAS, tol/temp/aging, ESR, source grid)',
    'TPS25947': 'TI SLVSFC9C (https://www.ti.com/lit/ds/symlink/tps25947.pdf): TPS259470A adjustable OVLO, '
                 'VOV(R) 1.183/1.20/1.223 V; IOVLKG +/-0.1 uA; tOVLO 1.2 us TYP only; RON 28.2 typ / 45 max mOhm; '
                 'RILM = 3334/ILIM; +/-10% ILIM above 1 A; CdVdt(pF)=2000/SR(V/ms), IdVdt 0.81/2.21/3.82 uA. '
                 'IN 2.7-23 V operating / 28 V absolute; SRIN rising/falling 100/10 V/us; OUT >= -0.3 V '
                 '(-0.8 V <1us). AUXOFF deasserts on OVLO, FLT does NOT. See tables 7-3/7-4.',

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
    n = {'+12V': count('+12V', '22u'), '+5V': count('+5V', '22u'), 'P5_RAW': count('P5_RAW', '22u'), '-12V': count('-12V', '22u'),
         'VIN': count('VIN', '10u'), 'damper': count('_VIN_DAMP', '10u')}
    assert n == {'+12V': 6, '+5V': 4, 'P5_RAW': 10, '-12V': 7, 'VIN': 5, 'damper': 2}, n
    eff = {'+12V': cs.mlcc(n['+12V'], 22, '22u25V_1206', 12.2), '+5V': cs.mlcc(n['+5V'], 22, '22u25V_1206', 5.0),
           'P5_RAW': cs.mlcc(n['P5_RAW'], 22, '22u25V_1206', 5.0),
           '-12V': cs.mlcc(n['-12V'], 22, '22u25V_1206', 12.2), 'VIN': cs.mlcc(n['VIN'], 10, '10u50V_1206', 20.0),
           'damper': cs.mlcc(n['damper'], 10, '10u50V_1206', 20.0)}
    s7 = {'+12V': cs.mlcc(4, 22, '22u25V_1206', 12.2), '+5V': cs.mlcc(4, 22, '22u25V_1206', 5.0),
          '-12V': cs.mlcc(5, 22, '22u25V_1206', 12.2)}
    ti = {'+12V': 'TPS62933 Table 10-2 (12 V): typ 15 / min 10 uF effective',
          '+5V': 'U23 delivered bank only: C35/C60/C73/C74, no buck feedback here',
          'P5_RAW': 'U3 feedback/local bank BEFORE U23: TPS62933 Table 10-2 typ 20 / min 10 uF',
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
        c_lo, _, esr = eff['P5_RAW' if rail == '+5V' else rail]
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
    # S8.3 +5V: full 2.5 A load release into ONLY the upstream bank. No help from
    # the downstream bank/rack and no 0.5us load-fall credit. Same imposed 2/8/16
    # cycle delay + -Vo/L current slew as the study, integrated analytically.
    _, eff = banks(table()[0])
    c_lo, c_hi, esr = eff['P5_RAW']
    vo, current, inductance, fsw = 4.985, 2.5, 3.3e-6, 1.977e6
    row = {}
    for nd in (2, 8, 16):
        charge = current * nd / fsw + 0.5 * inductance * current**2 / vo
        row[f'N={nd}'] = [round(charge / c_hi + current * esr, 3),
                          round(charge / c_lo + current * esr, 3)]
    row.update(vo_hi_V=cs.RAILS['P5_RAW']['vo_hi'],
               model='2.5A release into upstream bank only; Q=I*N/fsw+L*I^2/(2*Vo); includes I*ESR; no loop model',
               upstream_parts=10, rack_credit=False)
    res['+5V'] = row
    return res


def soft_start(val, eff):
    """Largest TOTAL rail capacitance (onboard bank + rack) the soft start can charge at full load before the
    current limit; rack_allowance = that total minus the onboard bank at its high corner (review finding 4)."""
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
        bank = eff['P5_RAW' if rail == '+5V' else rail]
        full = (avail - iload) * t / vo
        out[rail] = dict(avail_A=round(avail, 2),
                         track_ramp_max_C_mF={'full_load': round(full * 1e3, 2),
                                              'no_load': round(avail * t / vo * 1e3, 2),
                                              'S7_22n_full_load': round((avail - iload) * s7 / vo * 1e3, 2)},
                         onboard_bank_high_mF=round(bank[1] * 1e3, 3),
                         rack_allowance_full_load_mF=round((full - bank[1]) * 1e3, 2),
                         reach_65pct_before_hiccup_max_C_mF=round((avail - iload) * (t + 256e-6) / (0.65 * vo) * 1e3, 2))
    # LMR38020 IBB: valley limit ILS min + half ripple, output share (1 - D), within the 18 ms OCP blanking
    vin, vo, L, fsw = 20.0, 11.989, 15e-6, 0.79e6
    D = vo / (vin + vo)
    il = 1.8 + vin * D / (L * fsw) / 2
    io_max = il * (1 - D)
    full = (io_max - 1.0) * 0.018 / vo
    out['-12V'] = dict(io_max_A=round(io_max, 2), blank_ms=18,
                       max_C_mF={'full_load_1A': round(full * 1e3, 2),
                                 'no_load': round(io_max * 0.018 / vo * 1e3, 2)},
                       onboard_bank_high_mF=round(eff['-12V'][1] * 1e3, 3),
                       rack_allowance_full_load_mF=round((full - eff['-12V'][1]) * 1e3, 2),
                       ti_limit='<= ~10 x design COUT or 1000 uF, whichever is smaller (SNVSC40E 9.2.2.5)')
    out['rack_reference'] = ('Typical Eurorack module: 10-47 uF per rail; 20 modules x 22 uF = 0.44 mF per rail. '
                             'S8.3 +/-12V rely on converter soft start; +5V also has U23 inrush control' )
    out['+5V']['scope'] = 'Upstream converter-only screen, NOT rack allowance; U23 sets delivered inrush (see disconnect)'
    out['+5V'].pop('rack_allowance_full_load_mF')
    out['note'] = ('track_ramp_max_C / max_C are TOTAL capacitance (onboard + rack); rack_allowance subtracts the '
                   'onboard bank at its high corner. Loads that draw less than the full target during start-up leave '
                   'more room (no_load column). Bench item: -12V start-up into the real rack.')
    return out


def ov_guard(val, release):
    """S8.1 guard thresholds over every corner: REF_OV = U21 TLV431BI 1.224-1.259 V (IK 10 mA, -40..85 C) and up to
    3.6 mV lower at ~1 mA (|zKA| <= 0.4 ohm), LM2901B offset 5.5 mV and bias 50 nA out of the pin (-40..125 C),
    divider resistors 0.1 % + 25 ppm/C x 100 C. The converter setpoints keep the S8 1 % + 1 % TCR corners. Each
    band is checked against the capacitor-study release peak (study vo_hi + N=16 release), the stricter stacked
    peak (setpoint corner + N=16 release) and the downstream limit (16 V module capacitors, 6.0 V 5 V logic)."""
    vref, vio, ib_max = (1.224 - 0.0036, 1.24, 1.259), 0.0055, 50e-9
    rlo, rhi = 0.999 * 0.9975, 1.001 * 1.0025
    lo, hi = .99 * .99, 1.01 * 1.01
    limit = {'+12V': 16.0, '+5V': 6.0, '-12V': 16.0}

    def corners(f):
        vals = [f(v, a, b, e, ib) for v in (vref[0], vref[2]) for a in (rlo, rhi) for b in (rlo, rhi)
                for e in (-vio, vio) for ib in (0.0, ib_max)]
        return [min(vals), f(vref[1], 1, 1, 0, 0), max(vals)]

    def positive(top, bot):
        def f(v, a, b, e, ib):
            rt, rb = val(top) * a, val(bot) * b
            return (v + e - ib * rt * rb / (rt + rb)) * (rt + rb) / rb
        return corners(f)

    def negative(v, a, b, e, ib):
        r98, r99 = val('R98') * a, val('R99') * b
        return (v * r99 + (ib * r98 * r99 / (r98 + r99) - e) * (r98 + r99)) / r98
    out = {}
    for rail, top, bot, fbt, fbb, vfb, ovp in (('+12V', 'R93', 'R94', 'R8', 'R9', (.784, .8, .816), True),
                                                ('+5V', 'R95', 'R96', 'R11', 'R12', (.784, .8, .816), True),
                                                ('-12V', 'R99', 'R98', 'R14', 'R15', (.985, 1.0, 1.015), False)):
        g = corners(negative) if rail == '-12V' else positive(top, bot)
        sp = [v * (1 + val(fbt) * f1 / (val(fbb) * f2)) for v, f1, f2 in ((vfb[0], lo, hi), (vfb[1], 1, 1), (vfb[2], hi, lo))]
        study_peak = release[rail]['N=16'][1] + release[rail]['vo_hi_V']
        stacked_peak = sp[2] + release[rail]['N=16'][1]
        tau = (val(top) * val(bot) / (val(top) + val(bot))) * val({'+12V': 'C63', '+5V': 'C64', '-12V': 'C66'}[rail])
        row = dict(guard_V=[round(x, 3) for x in g], setpoint_V=[round(x, 3) for x in sp],
                   worst_imposed_release_peak_V=round(study_peak, 2),
                   release_margin_to_guard_min_V=round(g[0] - study_peak, 3),
                   stacked_setpoint_plus_release_V=round(stacked_peak, 3),
                   stacked_margin_to_guard_min_V=round(g[0] - stacked_peak, 3),
                   downstream_limit_V=limit[rail], margin_guard_max_to_limit_V=round(limit[rail] - g[2], 3),
                   filter_us=round(tau * 1e6, 1))
        if ovp:
            o = [1.12 * sp[0], 1.15 * sp[1], 1.18 * sp[2]]
            row.update(converter_OVP_V=[round(x, 2) for x in o])
        else:
            row.update(converter_OVP_V='none (LMR38020 has no output OVP)')
        out[rail] = row
    out['previous'] = {'S8_nominal_V': {'+12V': 16.58, '+5V': 6.5, '-12V': 15.1},
                       'S8_corners_V': {'+12V': [14.86, 18.45], '+5V': [5.84, 7.22], '-12V': [13.92, 16.36]},
                       'S7_eFuse_OV_nominal_V': {'+12V': 14.4, '+5V': 5.55, '-12V': 14.25}}
    out['response_us'] = dict(filter='8-9 (RC)', comparator=1.0, hc74_preset=0.05, tps1663_shdn=1.5,
                              total_after_crossing='~3 us + RC; then U5 off, rails decay')
    out['note'] = ('The bands are threshold screens, not a peak-voltage guarantee: opening U5 does not stop the energy '
                   'already stored behind it (hs_short). The +5V band overlaps the TPS62933F OVP band (non-latching, '
                   'stops the high side); either may act first on a slow excursion. A false trip latches every rail '
                   'off (MAIN off, press RESET). Common-mode: both comparator inputs sit at ~1.24 V at a positive trip, '
                   'inside VPD-2 V at full temperature (S8.3, >=15V qualified supply); -12V compares near 0 V.')
    return out


def clamp(val):
    """MON_OVN when V3V3 is gone while the rack still holds -12V (review finding 1). REF_OV then sits near 0 V
    (R100 to the collapsed V3V3), so MON_OVN is driven from -12V through R99 against R98: D22 takes the current."""
    r98, r99 = val('R98'), val('R99')
    out = {}
    for vneg in (12.0, 12.624, 16.0):
        thev = -vneg * r98 / (r98 + r99)
        rth = r98 * r99 / (r98 + r99)
        i = max(0.0, (-thev - 0.24) / rth)                 # D22 at its 0.1 mA maximum VF
        out[f'-{vneg:g}V'] = dict(open_circuit_V=round(thev, 3), clamp_current_uA=round(i * 1e6, 1),
                                  pin_V_max=-0.24 if i <= 1e-4 else -0.32)
    out['S8_without_clamp'] = dict(open_circuit_V=round(-12.0 * 7.5 / 54.5, 3),
                                   note='S8: R98 7.5k to V3V3, R99 47k to -12V, no clamp')
    out['note'] = ('BAT54SL VF <= 0.24 V at 0.1 mA (25 C): U20 pin 9 stays above the -0.3 V input limit at room '
                   'temperature (VF rises ~2 mV/C when cold); U20 is unpowered in this state, so its output state does '
                   'not matter, only the input current (tens of uA, limit -50 mA). In normal operation the diode is '
                   'reverse biased by 0.14 V and by ~0 V at the trip point, so its leakage does not move the threshold.')
    return out


def reference(val):
    """REF_OV: U21 cathode-current budget, settling at power-up against the earliest rail rise, stability."""
    r100, rdiv, c67 = val('R100'), val('R98') + val('R99'), val('C67')
    ik_min = (3.3 * .98 - 1.259) / (r100 * 1.01) - (1.259 + 20.0) / (rdiv * 0.999 * 0.9975) - 4 * 50e-9
    ik_max = (3.3 * 1.02 - 1.2204) / (r100 * .99) - 1.2204 / (rdiv * 1.001 * 1.0025)
    settle = [r100 * k1 * c67 * k2 * math.log(v3 / (v3 - 1.259)) for k1, k2, v3 in ((.99, .9, 3.366), (1.01, 1.1, 3.234))]
    return dict(R100_ohm=r100, IK_min_mA=round(ik_min * 1e3, 3), IK_max_mA=round(ik_max * 1e3, 3),
                IK_required_mA=0.1, divider_load_at_minus20V_mA=round((1.259 + 20.0) / rdiv * 1e3, 3),
                C67_uF=c67 * 1e6, settle_to_1V259_ms=[round(t * 1e3, 1) for t in settle],
                earliest_rail_rise_ms='> 12 (TPS3808 open-CT POR minimum) + U5 ramp + converter soft start',
                stability=('TLV431 is stable without a capacitor; 10u X5R (~9 uF at 1.24 V) is right of the '
                           'oscillation region (~3 nF..1 uF at VKA = VREF, SLVS139Z Fig. 5-18; Fig. 5-19 phase margin '
                           '~25-40 deg at 0.4-1.5 mA)'),
                ldo_extra_mW=round(0.94e-3 * 20 * 1e3, 1))


def comparator_supply(val):
    """Headroom while the input-qualified system can run; not power-down qualification."""
    vpd_min, vpd_clamp = 15.0, 35.5
    margin = vpd_min - 2.0 - (1.259 + 0.0055)
    return dict(supply='VPD before U5, after F1; D1 transient clamp', logic_pullups='V3V3 only',
                qualified_VPD_min_screen_V=vpd_min, common_mode_full_temp_upper_V=vpd_min - 2.0,
                REF_OV_plus_offset_max_V=1.259 + 0.0055, input_headroom_V=round(margin, 3),
                offset_spec_supply_min_V=5, operating_max_V=36, absolute_max_V=38,
                D1_rated_clamp_V=vpd_clamp, rated_clamp_margin_to_operating_max_V=36-vpd_clamp,
                note='Positive headroom during qualified operation. D1 rated clamp is NOT a measured ringing bound. '
                     'Verify VPD spikes <36V at both comparator ICs; power loss/cold negative-input clamp remain gates.')


def disconnect_settings(val):
    """Independent eFuse divider and programming tolerance screen, SLVSFC9C."""
    import itertools
    rlo, rhi = .999*.9975, 1.001*1.0025
    slo, shi = .99*.99, 1.01*1.01
    top, trim, bot = val('R101'), val('R107'), val('R102')
    thresholds = []
    for ref, a, b, c, leak in itertools.product((1.183, 1.223), (rlo, rhi), (slo, shi),
                                               (rlo, rhi), (-.1e-6, .1e-6)):
        rt, rb = top*a + trim*b, bot*c
        thresholds.append(ref*(1+rt/rb) + leak*rt)
    band = [min(thresholds), 1.2*(1+(top+trim)/bot), max(thresholds)]
    resistance = val('R103') + val('R104')
    ilim = [3334*.9/(resistance*shi), 3334/resistance, 3334*1.1/(resistance*slo)]
    return dict(trip_min_nom_max_V=band, current_min_nom_max_A=ilim,
                divider_ohm=[top, trim, bot], ILM_ohm=resistance,
                OVLO_response_typ_us=1.2, OVLO_response_max_us=None,
                OVLO_fault_latched_internally=False, FLT_reports_OVLO=False, AUXOFF_reports_OVLO=True)


def _disconnect_run(c_in, c_raw, c_out, trip, delay, *, inductance=3.3e-6, vin0=20.0,
                    ron=.0282, i0=2.5, v0=5.259, guard_trip=5.976, dt=5e-9, t_end=200e-6):
    """Screen, not an IC macromodel. Shorted U3 high side -> L2 -> raw bank/TVS ->
    U23 Ron -> delivered bank (no load). U5 supplies its high current-limit corner
    until U20 RC + assumed 2.6us logic/SHDN delay. No credit for U23 current limit
    or short-circuit trip. Ideal reverse block. U23 opens after a chosen delay,
    no intentional OVLO filter. Capacitance held constant, no wiring inductance,
    TVS is 7V+0.05ohm, low-side body diode -0.7V, raw negative clamp -0.3V.
    The separate post-interruption LC estimate covers selected local output-L.
    This is NOT a maximum peak prediction or a guaranteed protection envelope.
    """
    vin, raw, out, il, fg = vin0, v0, v0, i0, v0
    t_trip = t_guard = t_off = t_u5 = None
    res = dict(header_peak_V=v0, raw_peak_V=v0, switch_peak_A=0., switch_current_at_open_A=0.,
               tvs_peak_A=0., tvs_energy_mJ=0., header_time_above_6V_us=0., raw_slew_rise_V_us=0.,
               raw_slew_fall_V_us=0., VIN_min_V=vin0)
    for k in range(int(t_end/dt)):
        t = k*dt
        if t_trip is None and raw >= trip:
            t_trip, t_off = t, t+delay
        if t_guard is None and fg >= guard_trip:
            t_guard, t_u5 = t, t+2.6e-6
        on = t_off is None or t < t_off
        isw = max(0., (raw-out)/ron) if on else 0.
        if on:
            res['switch_current_at_open_A'] = isw
        itvs = max(0., (raw-7.)/.05)
        v_sw, ifet = vin-il*.02, il
        if v_sw < -.7:
            v_sw, ifet = -.7, (vin+.7)/.02
        id3 = max(0., (-raw-.3)/.05)
        feed = 4.698 if t_u5 is None or t < t_u5 else 0.
        dvin = (feed-ifet)/c_in
        if vin >= vin0 and dvin > 0: dvin = 0.
        dr = (il-isw-itvs+id3)/c_raw
        vin, raw, out, il = (vin+dvin*dt, raw+dr*dt, out+isw/c_out*dt,
                              il+(v_sw-il*.012-raw)/inductance*dt)
        fg += (raw-fg)*dt/7.87e-6
        res['header_peak_V'] = max(res['header_peak_V'], out)
        res['raw_peak_V'] = max(res['raw_peak_V'], raw)
        res['switch_peak_A'] = max(res['switch_peak_A'], isw)
        res['tvs_peak_A'] = max(res['tvs_peak_A'], itvs)
        res['tvs_energy_mJ'] += raw*itvs*dt*1e3
        res['header_time_above_6V_us'] += dt*1e6 if out > 6 else 0.
        res['raw_slew_rise_V_us'] = max(res['raw_slew_rise_V_us'], dr*1e-6)
        res['raw_slew_fall_V_us'] = max(res['raw_slew_fall_V_us'], -dr*1e-6)
        res['VIN_min_V'] = min(res['VIN_min_V'], vin)
    res.update(t_trip_us=t_trip*1e6 if t_trip is not None else None,
               t_disconnect_us=t_off*1e6 if t_off is not None else None,
               t_U5_off_us=t_u5*1e6 if t_u5 is not None else None)
    res['local_L_energy_peak_100nH_V'] = math.sqrt(res['header_peak_V']**2+
                                                   100e-9*res['switch_current_at_open_A']**2/c_out)
    return {k: round(v, 4) if v is not None else None for k, v in res.items()}


def disconnect(val, eff, ov, simulate=True):
    settings = disconnect_settings(val)
    trip = settings['trip_min_nom_max_V']
    c_up, c_down = eff['P5_RAW'], eff['+5V']
    # Eq.4 is typical; scale by tabulated IdVdt extremes for sensitivity, NOT a
    # guaranteed complete slew-rate spec. Include cap +/-10%.
    slope = 2000/(val('C68')*1e12)
    slopes = [slope*.81/2.21/1.1, slope, slope*3.82/2.21/.9]
    ilim = settings['current_min_nom_max_A']
    allowed = (ilim[0]-2.5)/(slopes[2]*1000)-c_down[1]
    out = dict(**settings,
               C_raw_low_high_uF=[v*1e6 for v in c_up[:2]], C_out_low_high_uF=[v*1e6 for v in c_down[:2]],
               normal_raw_peak_screen_V=ov['+5V']['stacked_setpoint_plus_release_V'],
               normal_margin_to_OVLO_min_V=trip[0]-ov['+5V']['stacked_setpoint_plus_release_V'],
               threshold_margin_to_6V_V=6-trip[2],
               ramp_V_ms_sensitivity=slopes, ramp_5V_ms_sensitivity=[5/slopes[2],5/slope,5/slopes[0]],
               rack_C_allowance_full_load_mF_sensitivity=allowed*1e3,
               conduction_W_at_2A5_typ_max=[2.5**2*.0282,2.5**2*.045],
               drop_V_at_2A5_typ_max=[2.5*.0282,2.5*.045],
               thermal_no_vias_dT_C_screen=2.5**2*.045*74.5,
               startup_thermal_note='Full constant 2.5 A from 0 V dissipates ~6.25 W average during a 25 ms ramp; '
                                    'startup foldback below 1.9 V and thermal shutdown may prevent start. '
                                    'No full-load capacitance rating; qualify actual load current vs voltage.',
               latch='AUXOFF/FLT wire-AND with U18 on P5_OK. Existing filtered latch acts after ARMED. '
                     'U20 watches raw OV even during startup. Brief OVLO-only events before ARMED or shorter '
                     'than the bad-status filter can auto-recover. Do not call every event manually latched.',
               qualification='No guaranteed <6V peak: 1.2us is typical only, parasitics/loop/DC bias uncertain; '
                             '6V is a screen, not a universal module rating. Do not connect valuable modules before fault tests.')
    if simulate:
        cin = eff['VIN'][1]+eff['damper'][1]
        cases = {}
        for l in (3.3e-6, 1e-6):
            for delay in (1.2e-6, 3e-6, 5e-6):
                key = f'L{l*1e6:g}uH_delay{delay*1e6:g}us'
                cases[key] = _disconnect_run(cin,c_up[0],c_down[0],trip[2],delay,inductance=l)
        cases['half_C_VIN26_L1uH_3us'] = _disconnect_run(cin,c_up[0]/2,c_down[0]/2,trip[2],3e-6,
                                                         inductance=1e-6,vin0=26.)
        out['fault_delay_sensitivity'] = dict(cases=cases, model=_disconnect_run.__doc__, guaranteed_bound=False)
    return out


def startup_window(val):
    t = val('C49') * 1e9 / 175 + .0005
    budget = dict(U5_ramp_ms=round(20 / (1.775e-6 * 23.5 / (22e-9 * 1.1)) * 1e3, 1), PGOOD_deglitch_ms=13,
                  TPS62933F_SS_max_ms=round(val('C9') * 1.1 * 0.8 / 4.5e-6 * 1e3, 1), LMR38020_SS_plus_blank_ms=18 + 4,
                  U23_ramp_5V_sensitivity_ms=round(5/(2000/(val("C68")*1e12)*.81/2.21/1.1),1))
    total = sum(budget.values())
    return dict(typ_s=round(t, 3), min_s_screen=round(t * .6 * .9, 3), S7_typ_s=round(1e-6 * 1e9 / 175 + .0005, 2),
                rail_up_budget_ms=budget, rail_up_total_ms=round(total, 1),
                ratio_min_window_to_budget=round(t * .6 * .9 / (total / 1e3), 1))


def input_budget():
    out_w = {'+12V': 12.194 * 2.5, '+5V': 4.985 * 2.5, '-12V': 11.989 * 1.0}
    eff = {'+12V': .93, '+5V': .88, '-12V': .85}            # assumed from datasheet efficiency curves
    conv_in = sum(out_w[k] / eff[k] for k in out_w)
    i = conv_in / 19.2
    losses = {'D10_0.75V': 0.75 * i, 'U5_31mohm': 0.031 * i * i, 'aux_logic_LEDs': 0.5, 'U23_28m2_at_2A5': .0282*2.5**2}
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
                rail_max_setpoint_V=5.26, vin_cap_dump_mJ=round(e * 1e3, 1), rated_peak_W_10_1000us=400,
                note='Above VRWM only at the stacked worst-case setpoint; <= ~5 mW even at 1 mA. Transient clamp '
                     'only (not a 5 V limit): upstream overvoltage drives U20 -> FAULT -> U5 off; '
                     'U23 isolates delivered +5V. D21 is on P5_RAW, not the headers. TVS transient rating depends on '
                     'pulse duration and temperature; never infer a universal joule rating from peak watts.')


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
             'LED3EDGE': 'LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge', 'RPW10': 'TI_RPW0010A_VQFN-HR-10_2x2mm'}
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
    R['soft_start'] = soft_start(val, eff)
    R['ov_guard'] = ov_guard(val, R['rail_release'])
    R['ov_reference'] = reference(val)
    R['ov_clamp'] = clamp(val)
    R['comparator_supply'] = comparator_supply(val)
    R['disconnect'] = disconnect(val, eff, R['ov_guard'])
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
