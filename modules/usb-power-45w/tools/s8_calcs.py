#!/usr/bin/env python3
"""S8 single-board pre-calculations: ceramic banks, VIN damper, soft start into rack capacitance,
overvoltage guard and VPD-powered comparators, V3V3-loss comparator state, -12V start-up per the LMR38020 hiccup rule, the published conservative
continuous rating, input and connector budgets, board area (S8.4); S8.5: the one-shot arming (required
behaviour, STARTED latch topology, V20_OK status floor over tolerance/temperature, U5 window, startup budget)
and the replug / power-on-reset race of the U20 -12V channel (an explicit OPEN item). S9.0 step 1: the +5V subsystem is gone,
so every +5V section (U23 disconnect, OVLO release, failed-high-side screen, TP18 bring-up, D21 TVS) left with it.
S9.0 step 2: 15 V PD input (13.5-16.5 V at the module) and the TPS552892-Q1 four-switch buck-boost on +12V: the duty
proof that the S8 TPS62933F buck cannot regulate at 15 V and that the buck-boost does (plus12_buckboost), its current
limit, thermal and compensation screens, the PD contract and the 3 A input budget (pd_contract, rating), the two
accepted residuals with their bench-test conditions (residuals) and what changes for the later 20 V retarget
(retarget_20v).

  python3 -B tools/s8_calcs.py --out docs/s8-single     (numpy; pcbnew for the area section)

SCREENING ONLY. Every value comes from the S8 circuit table (tools/circuit_s8.py) and the cited
datasheet figures; MLCC DC-bias retention, ESR and the VIN source corners reuse the bounded
assumptions of the capacitor study (tools/capacitor-study/cap_study.py, docs/capacitor-study/).
The VIN and rail-release models are passive ladders with an averaged constant-power load or an
imposed converter current; no TPS552892/LMR38020F control loop is modelled. Not a closed-loop
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
    'cap_study': 'docs/capacitor-study/README.md bounds (BIAS, tol/temp/aging, ESR, source grid)',
    'LMR38020_hiccup': 'TI SNVSC40E 8.3.8/8.3.9: hiccup only if FB < 40 % of VREF while ILS limits for 256 consecutive '
                       'cycles; disabled for TOCP_BLK 18 ms typ (no min) from power-up; IOUTMAX = ILS + ripple/2 (Eq. 7)',
    'TPS62933F_IOMAX': 'TI SLUSEA4D 9.3.12 Eq. 11/12: IOMAX ~ (IHS + ILS)/2, or IHS - ripple/2 if ripple is large; '
                       'UVP hiccup if FB < 65 % with current limit for 256 us after soft start',
    'TPS1663_UVLO': 'TI SLVSET9G: UVLO rising 1.176/1.2/1.224 V, falling 1.09/1.122/1.15 V, leakage +/-150 nA; '
                    'PGOOD deglitch 8-13 ms',
    'LM2901B_inputs': 'TI SLCS006Z 6.1/6.4: inputs -0.3..38 V abs (independent of supply), input current -50 mA abs; '
                      'recommended input (V-)-0.1..(V+)-2 V; one input in range gives a proper output state',
    'SN74LVC1G17': 'TI SCES351Y Table 5-1: VT+ 1.48-1.92 V at VCC 3 V (2.19-2.74 V at 4.5 V)',
    'USB_PD_input': 'assumption: 20 V PD source -5 % (19.0 V) minus <=0.75 V cable/connector drop = 18.25 V minimum '
                    'loaded VPD; not a measured cable',
    'TPS1663_PGOOD': 'TI SLVSET9G (https://www.ti.com/lit/ds/symlink/tps1663.pdf): PGOOD high when the FET is enhanced, low '
                     'when the FET turns off on a fault or SHDN low; deglitch tPGOODR 11.5 ms typ rising, tPGOODF 10 ms typ '
                     'falling; operating IN 4.5-60 V (status outputs unspecified below)',
    'USB_PD_vSafe5V': 'USB PD 3.x vSafe5V 4.75-5.5 V: the source starts at 5 V and moves to the negotiated PDO only after the '
                      'contract (the 5 V phase can last from ~100 ms to seconds, e.g. after a hard reset)',
    'TPS552892': 'TI SLVSGT7 (https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf): VIN 3-36 V (abs 42 V), VOUT 0.8-22 V, VREF '
                 '1.188/1.2/1.212 V, fSW = 1000 / (0.05 x RFSW + 35) MHz (Eq. 3; 180-220 kHz at 100k, 2.0-2.4 MHz at 8.4k), '
                 'tON_min 130 ns max (buck), tOFF_min 145 ns max (boost), ILIM_AVG 7/8/9 A, VSNS 48/50/52 mV, tSS '
                 '2.5/3.6/5 ms, VOVP 22.5/23.5/24.5 V (absolute), RDS(on) typ 14/22 mOhm (buck HS/LS) and 11/11 mOhm '
                 '(boost HS/LS), IVOUT_LKG <= 20 uA disabled, RthetaJA 43.4 C/W (JEDEC) / 27.5 C/W (EVM), effective L 1-10 uH '
                 '(L > 1.2/fSW), CIN >= 4.7 uF effective, COUT 10-1000 uF effective, < 500 kHz advised at high power, '
                 'hiccup only for VOUT < 0.8 V with the average inductor limit for 2 ms, FPWM passes reverse power at light '
                 'load, Eq. 19-26 compensation (RSENSE 55 mOhm, GEA 190 uA/V)',
    'TPS62933F_RDS': 'TI SLUSEA4D: integrated 76 mOhm (high side) / 32 mOhm (low side) MOSFETs, 98 % maximum duty (the user '
                     'brief and the S8 review figure)',
    'LMR38020_backfeed': 'TI SNVSC40E 7.5 / 8.3.8 / 8.4.2: VIN to start 4.2 V max, EN high 1.1-1.4 V, IL-NEG -0.9 A typical '
                         '(FPWM, no limits given), pre-biased start-up supported, FPWM passes power from output to input',
    'USB_PD_power_rules': 'USB PD 3.x power rules: a 45 W PDP source offers 5/9/15 V at 3 A and 20 V at 2.25 A; 15 V fixed '
                          'PDOs never exceed 3 A; a 27 W source offers 15 V at 1.8 A; vSrcNew +-5 %',
    'CH224A_CFG': 'WCH CH224 datasheet V2.x: CFG1 resistor to GND selects the request: 6.8k 9 V, 24k 12 V, 56k 15 V, '
                  '120k 20 V (no current-contract tracking)',
}


def table():
    parts = {p['ref']: p for p in circuit_s8.circuit() if not p['ref'].startswith('#')}

    def val(ref):
        s = parts[ref]['value']
        return float(s[:-1]) * {'k': 1e3, 'u': 1e-6, 'n': 1e-9}[s[-1]] if s[-1] in 'kun' else float(s)
    return parts, val


R01 = (.999 * .9975, 1.001 * 1.0025)     # 0.1 % + 25 ppm/C x 100 C
R1 = (.99 * .99, 1.01 * 1.01)            # 1 % + 1 % TCR drift (S6 screens)


def corners(ref):
    """(low, high) resistance factors of a divider resistor from its circuit-table Tolerance field."""
    global _PARTS
    if _PARTS is None:
        _PARTS = table()[0]
    return R01 if _PARTS[ref]['fields'].get('Tolerance') == '0.1%' else R1


_PARTS = None


def setpoint(val, top, bot, vfb):
    """Converter setpoint (min, nom, max) over VFB (min, typ, max) and each resistor's own tolerance corners."""
    (tl, th), (bl, bh) = corners(top), corners(bot)
    return [vfb[0] * (1 + val(top) * tl / (val(bot) * bh)), vfb[1] * (1 + val(top) / val(bot)),
            vfb[2] * (1 + val(top) * th / (val(bot) * bl))]


# S9.0: TPS552892-Q1 datasheet constants (SOURCES TPS552892) and the +12V operating point from the circuit table.
TPS552892_DS = dict(vref=(1.188, 1.2, 1.212), ilim_avg=(7.0, 8.0, 9.0), vsns=(0.048, 0.050, 0.052),
                    tss_ms=(2.5, 3.6, 5.0), ovp=(22.5, 23.5, 24.5), rds=dict(hs1=0.014, ls1=0.022, ls2=0.011, hs2=0.011),
                    ton_min=130e-9, toff_min=145e-9, rth_ja=(43.4, 27.5), vin_abs=42.0, vin_max=36.0, fsw_tol=0.10,
                    rsense_int=0.055, gea=190e-6, ifb_lkg=100e-9, ivout_lkg=20e-6, cout_eff_max_uF=1000.0,
                    ieff_vcc_A=0.010, l_min_x_fsw=1.2)
R109_TOL = (0.99 * (1 - 75e-6 * 100), 1.01 * (1 + 75e-6 * 100))      # 1 % + 75 ppm/C x 100 C (HoLR1206)
ETA_ASSUMED = {'+12V': .93, '-12V': .85}      # planning efficiencies (datasheet curves), not measurements
FC_SCREEN_HZ = 10e3                           # +12V crossover screen (COMP R111/C83)


def p12(val):
    """+12V operating point from the circuit table: FB setpoint corners (R8/R9 1 % + 1 % TCR, VREF), fSW (R110, Eq. 3,
    +-10 % screen), output constant-current limit (R109 1 % + 75 ppm, VSNS) and the published current."""
    ds = TPS552892_DS
    fsw = 1e6 * 1000 / (0.05 * val('R110') + 35)
    r = val('R109')
    return dict(setpoint_V=setpoint(val, 'R8', 'R9', ds['vref']), vo_nom=round(ds['vref'][1] * (1 + val('R8') / val('R9')), 3),
                fsw_Hz=[fsw * (1 - ds['fsw_tol']), fsw, fsw * (1 + ds['fsw_tol'])], L=val('L1'),
                icc_A=[ds['vsns'][0] / (r * R109_TOL[1]), ds['vsns'][1] / r, ds['vsns'][2] / (r * R109_TOL[0])],
                r_sense=r, dcr=0.022, i_pub=PUBLISHED_A['+12V'])


PUBLISHED_A = {'+12V': 2.4, '-12V': 0.8}      # S9.0 published per-rail continuous rating (rating() re-derives it)


BANK_COUNTS = {'+12V': 8, '-12V': 7, 'VIN': 5, 'damper': 2}
P12_SPLIT = {'converter_P12_VOUT': 6, 'headers_+12V': 2}      # S9.0: 6 x 22u before R109, 2 at J2/J3


def banks(parts):
    """Effective capacitance bounds (uF) per bank under the capacitor-study bias bands. S9.0: the +12V bank is the 6 x 22u
    at the TPS552892 VOUT (P12_VOUT, before the R109 sense resistor) plus the 2 x 22u at the headers (+12V); 15 mOhm
    between them is ignored. The VIN bank is the TPS552892 4 x 10u plus the LMR38020 C24 (VIN to GND)."""
    def count(net, value):
        return sum(1 for p in parts.values() if p['value'] == value and p['fp'] == 'C1206'
                   and net in p['pins'].values() and 'GND' in p['pins'].values())
    split = {'converter_P12_VOUT': count('P12_VOUT', '22u'), 'headers_+12V': count('+12V', '22u')}
    assert split == P12_SPLIT, split
    n = {'+12V': sum(split.values()), '-12V': count('-12V', '22u'),
         'VIN': count('VIN', '10u'), 'damper': count('_VIN_DAMP', '10u')}
    assert n == BANK_COUNTS, n
    eff = {'+12V': cs.mlcc(n['+12V'], 22, '22u25V_1206', 12.2),
           '-12V': cs.mlcc(n['-12V'], 22, '22u25V_1206', 12.2), 'VIN': cs.mlcc(n['VIN'], 10, '10u50V_1206', 20.0),
           'damper': cs.mlcc(n['damper'], 10, '10u50V_1206', 20.0)}
    s7 = {'+12V': cs.mlcc(4, 22, '22u25V_1206', 12.2), '-12V': cs.mlcc(5, 22, '22u25V_1206', 12.2)}
    ti = {'+12V': 'TPS552892-Q1 (SLVSGT7 6.3): COUT 10-1000 uF effective, 100 uF nominal; TI example 4 x 22u. S9.0: 6 x 22u '
                  'at VOUT before R109 + 2 at the headers',
          '-12V': 'LMR38020 Table 9-1 is a BUCK guide in rated C (12 V/1 MHz 2 x 10u, 12 V/400 kHz 1 x 22u); '
                  'IBB: no TI table; max ~10 x design or 1000 uF incl. the rack',
          'VIN': 'TPS552892-Q1: CIN >= 4.7 uF effective (TI example ~20 uF) + 0.1 uF at VIN: C6, C7, C77, C78 + C8; LMR38020 '
                 'CIN >= 4.7 uF effective (C25 + C26 VIN to -12V, unchanged) and C24. Bias band 20 V (covers 16.5 V and the '
                 'later 20 V retarget)',
          'damper': 'series-R damper branch, capacitor study option B_RCx2'}
    out = {k: dict(parts=n[k], eff_uF=[round(v[0] * 1e6, 1), round(v[1] * 1e6, 1)], bank_esr_mohm=round(v[2] * 1e3, 2),
                   reference=ti[k]) for k, v in eff.items()}
    out['+12V']['split'] = split
    for k, v in s7.items():
        out[k]['S7_ceramic_only_eff_uF'] = [round(v[0] * 1e6, 1), round(v[1] * 1e6, 1)]
        out[k]['S7_can'] = '100u 35V can (57.8-120 uF, ESR 0.3-3 ohm, removed)'
    return out, eff


def ripple_and_steps(val, eff):
    """Switching ripple (CCM, ideal waveforms) and load-step deviation estimates at the LOW C corner. S9.0: +12V is the
    TPS552892-Q1 buck-boost (mode from VIN vs VOUT; buck Eq. 9, boost Eq. 12/17), the step deviation a loop-bandwidth screen
    dV ~ dI / (2 pi fc C) at the ~10 kHz crossover of the COMP screen (plus12_buckboost); -12V is the unchanged LMR38020
    IBB at the S9.0 converter inputs and the published 0.8 A."""
    res = {}
    c_lo, _, esr = eff['+12V']
    op = p12(val)
    vo, L, fsw, fc = op['vo_nom'], op['L'], op['fsw_Hz'][1], FC_SCREEN_HZ
    rows = []
    for vin in (10.55, 12.5, 15.0, 16.5, 21.0):
        if vin > vo:
            mode, d = 'buck', vo / vin
            dil = (vin - vo) * d / (L * fsw)
            v_c = dil / (8 * fsw * c_lo)
        else:
            mode, d = 'boost', 1 - vin / vo
            dil = vin * (vo - vin) / (L * fsw * vo)
            v_c = op['i_pub'] * (1 - vin / vo) / (c_lo * fsw)                      # TI Eq. 17
        rows.append(dict(vin=vin, mode=mode if abs(vin - vo) > 0.6 else 'buck-boost (alternating)', D=round(d, 3),
                         dIL_A=round(dil, 3), ripple_C_mV=round(v_c * 1e3, 2), ripple_ESR_mV=round(dil * esr * 1e3, 2),
                         step_1A_dev_mV=round(1.0 / (2 * math.pi * fc * c_lo) * 1e3)))
    res['+12V'] = dict(L_uH=L * 1e6, fsw_kHz=round(fsw / 1e3), rows=rows,
                       note='TPS552892-Q1; 10.55 V = converter input at the U5 turn-off minimum, 21 V = the later 20 V '
                            'retarget. Step: 1 A load step against the low-C bank at the ~10 kHz crossover screen')
    c_lo, _, esr = eff['-12V']
    rows = []
    for vin in (12.5, 15.0, 16.5):
        vo, L, fsw, io = 11.989, 15e-6, 0.79e6, 0.8
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
    res['-12V'] = dict(L_uH=15, fsw_kHz=790, io_A=0.8, rows=rows,
                       note='IBB at the S9.0 converter inputs (15 V nominal: D = 0.444): the output bank carries the full '
                            'load during the on time; per-part rms <= 2 x share of cout_rms (imbalance x2) -> well below '
                            '1206 heating limits')
    return res


def vin_damper(rd, n_vin, v_min=None, p_max=None):
    """Middlebrook screen of the all-ceramic VIN bus with the series-R damper (study option B_RCx2). S9.0: the VIN ceramic
    count (n_vin x 10u) and the constant-power load (p_max at v_min) are this design's, not the study's 5 x 10u / 72 W."""
    import numpy as np
    v_min = cs.V_MIN if v_min is None else v_min
    p_max = cs.P_MAX if p_max is None else p_max
    zin = v_min ** 2 / p_max
    cer_lo, cer_hi, _ = cs.mlcc(n_vin, 10, '10u50V_1206', 20.0)
    freqs = np.logspace(3, 6, 240)
    out = {}
    for opt in ('B0', 'B_RCx2'):
        worst = dict(zeta=9.0, zmax=0.0, unstable=0, n=0)
        for c in cs.vin_grid():
            if c['esr_i'] != 0 or c['c5c'] != 'lo':
                continue
            cer = cer_lo if c['cer'] == 'lo' else cer_hi
            lad, k = cs.vin_ladder(opt, c['L'], c['R'], c['Rb'], c['Ron'], cer, 0.0, cs.CSRC[c['csrc']], rd, c['c5c'])
            g = np.zeros(len(lad.nodes)); g[k] = -p_max / v_min ** 2
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
    out['VIN_ceramics'] = f'{n_vin} x 10u/50V 1206 ({cer_lo * 1e6:.1f}-{cer_hi * 1e6:.1f} uF effective at the 20 V bias band)'
    out['load'] = f'{p_max:.0f} W constant power at {v_min} V (upper estimate, linearised)'
    c_d_hi = cs.mlcc(2, 10, '10u50V_1206', 20.0)[1]
    sr = 2.225e-6 * 26 / (22e-9 * 0.9)                       # U5 dVdt fastest corner (cap study inrush())
    out['R92_stress'] = dict(ripple_rms_mA_from_study=26.7, ripple_P_mW=round(0.0267 ** 2 * rd * 1e3, 2),
                             inrush_mA=round(c_d_hi * sr * 1e3, 1),
                             step_energy_uJ=round(0.5 * c_d_hi * 1.5 ** 2 * 1e6, 1),
                             note='1.5 V VIN dip assumed for the step energy; 1206 250 mW part')
    return out


def rail_release(val=None):
    """Imposed-trajectory load release (study model) with the S8 banks (study option B_x2) and the rack directly on the
    rail, against the guard minimum. S9.0: the study's +12V entry describes the removed TPS62933F, so the +12V run
    substitutes the TPS552892-Q1 cell for its duration (setpoint maximum from R8/R9 and VREF, L1, the LOWEST fSW of the
    R110 screen, 6 x 22u at VOUT + the 2 header parts of option B_x2) and releases the published 2.4 A; the R109 limit
    maximum (3.53 A, an overload being released) is a sensitivity. -12V keeps the study entry (unchanged hardware, its
    0.8 A release = the S9.0 published rating)."""
    if val is None:
        val = table()[1]
    op = p12(val)
    rack = dict(R=0.08, L=0.5e-6, C=470e-6, esr=0.1)
    saved = dict(cs.RAILS['P12_RAW'])
    res = {}
    try:
        for rail, i_rel, key in (('P12_RAW', op['i_pub'], '+12V'), ('P12_RAW', op['icc_A'][2], '+12V_from_R109_limit_max'),
                                 ('N12_RAW', None, '-12V')):
            if rail == 'P12_RAW':
                cs.RAILS['P12_RAW'] = dict(saved, vo=op['vo_nom'], vo_hi=round(op['setpoint_V'][2], 3), L=op['L'],
                                           fsw=op['fsw_Hz'][0], cer=(P12_SPLIT['converter_P12_VOUT'], 22, 12.2),
                                           i_rel=round(i_rel, 3))
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
            rr['i_release_A'] = p['i_rel']
            rr['fsw_kHz'] = round(p['fsw'] / 1e3, 1)
            res[key] = rr
    finally:
        cs.RAILS['P12_RAW'] = saved
    res['note'] = ('N cycles of unchanged converter current, then -Vo/L (no loop model, no sink). +12V: TPS552892-Q1 at '
                   'the lowest fSW corner and the setpoint maximum; the R109-limit row releases an overload (sensitivity)')
    return res


def soft_start(val, eff):
    """Start-up into rack capacitance. S9.0 +12V: the TPS552892-Q1 ramps its reference in tSS 2.5-5 ms (fixed); with a large
    rail capacitance the R109 constant-current loop takes over and charges it at the limit (3.14 A minimum) minus the
    load. Hiccup needs VOUT < 0.8 V AND the 7-9 A average inductor limit for 2 ms, which the R109 limit keeps the inductor
    far below (buck mode IL = IOUT; boost corner in plus12_buckboost), so a large rack does not hiccup: the allowance is
    TI's 1000 uF effective COUT ceiling minus the onboard bank, and the start-up time is checked against the window.
    -12V: the LMR38020 hiccup rule (minus12_startup)."""
    op = p12(val)
    ds = TPS552892_DS
    bank_hi = eff['+12V'][1]
    icc_min, vmax = op['icc_A'][0], op['setpoint_V'][2]
    ss_ramp = vmax / (ds['tss_ms'][0] * 1e-3)                       # fastest reference ramp, V/s
    c_track_full = (icc_min - op['i_pub']) / ss_ramp                # largest C that still follows the reference at full load
    rack_ti = ds['cout_eff_max_uF'] * 1e-6 - bank_hi
    t_charge = (ds['cout_eff_max_uF'] * 1e-6) * vmax / (icc_min - op['i_pub'])
    out = {'+12V': dict(tSS_ms=list(ds['tss_ms']), cc_limit_A=[round(x, 3) for x in op['icc_A']],
                        tracks_reference_up_to_mF={'full_load': round(c_track_full * 1e3, 3),
                                                   'no_load': round(icc_min / ss_ramp * 1e3, 3)},
                        onboard_bank_high_mF=round(bank_hi * 1e3, 3),
                        rack_allowance_mF=round(rack_ti * 1e3, 3),
                        allowance_basis='TI effective COUT ceiling 1000 uF (SLVSGT7 6.3) minus the onboard bank high corner; '
                                        'above the tracking limit the rail charges at the R109 limit (no hiccup)',
                        time_to_full_at_allowance_full_load_ms=round(t_charge * 1e3, 1),
                        hiccup='only if VOUT < 0.8 V with the average inductor limit for 2 ms after tSS: a short circuit, '
                               'not a capacitive start (R109 holds IL near IOUT)')}
    m12 = minus12_startup(val, eff)
    out['-12V'] = dict(blank_ms=18, onboard_bank_high_mF=round(eff['-12V'][1] * 1e3, 3),
                       rack_allowance_full_load_mF=m12['published_allowance_mF'],
                       allowance_basis=m12['published_basis'],
                       ti_limit='<= ~10 x design COUT or 1000 uF, whichever is smaller (SNVSC40E 9.2.2.5)')
    out['rack_reference'] = ('Typical Eurorack module: 10-47 uF per rail; 20 modules x 22 uF = 0.44 mF per rail. '
                             'S9.0: +12V charges through the R109 constant-current loop; -12V per the LMR38020 hiccup rule')
    out['note'] = ('Allowances are rack capacitance on top of the onboard bank (high corner). Loads that draw less than the '
                   'full rating during start-up leave more room. Bench item: start-up into the real rack at 13.5 V.')
    return out


def ov_guard(val, release):
    """S8.1 guard thresholds over every corner: REF_OV = U21 TLV431BI 1.224-1.259 V (IK 10 mA, -40..85 C) and up to
    3.6 mV lower at ~1 mA (|zKA| <= 0.4 ohm), LM2901B offset 5.5 mV and bias 50 nA out of the pin (-40..125 C),
    divider resistors 0.1 % + 25 ppm/C x 100 C. The converter setpoints keep the S8 1 % + 1 % TCR corners. Each
    band is checked against the capacitor-study release peak (study vo_hi + N=16 release), the stricter stacked
    peak (setpoint corner + N=16 release) and the downstream limit (16 V module capacitors). S9.0: two channels
    (+12V, -12V); each converter setpoint uses its own feedback-resistor tolerance. S9.0 step 2: +12V setpoint from the
    TPS552892-Q1 VREF (1.188-1.212 V) and R8/R9; its OVP is absolute (22.5-24.5 V)."""
    vref, vio, ib_max = (1.224 - 0.0036, 1.24, 1.259), 0.0055, 50e-9
    rlo, rhi = R01
    limit = {'+12V': 16.0, '-12V': 16.0}

    def band(f):
        vals = [f(v, a, b, e, ib) for v in (vref[0], vref[2]) for a in (rlo, rhi) for b in (rlo, rhi)
                for e in (-vio, vio) for ib in (0.0, ib_max)]
        return [min(vals), f(vref[1], 1, 1, 0, 0), max(vals)]

    def positive(top, bot):
        def f(v, a, b, e, ib):
            rt, rb = val(top) * a, val(bot) * b
            return (v + e - ib * rt * rb / (rt + rb)) * (rt + rb) / rb
        return band(f)

    def negative(v, a, b, e, ib):
        r98, r99 = val('R98') * a, val('R99') * b
        return (v * r99 + (ib * r98 * r99 / (r98 + r99) - e) * (r98 + r99)) / r98
    out = {}
    for rail, top, bot, fbt, fbb, vfb, ovp in (('+12V', 'R93', 'R94', 'R8', 'R9', TPS552892_DS['vref'], True),
                                                ('-12V', 'R99', 'R98', 'R14', 'R15', (.985, 1.0, 1.015), False)):
        g = band(negative) if rail == '-12V' else positive(top, bot)
        sp = setpoint(val, fbt, fbb, vfb)          # R8/R9/R14/R15 1 % + 1 % TCR
        study_peak = release[rail]['N=16'][1] + release[rail]['vo_hi_V']
        stacked_peak = sp[2] + release[rail]['N=16'][1]
        tau = (val(top) * val(bot) / (val(top) + val(bot))) * val({'+12V': 'C63', '-12V': 'C66'}[rail])
        row = dict(guard_V=[round(x, 3) for x in g], setpoint_V=[round(x, 3) for x in sp],
                   worst_imposed_release_peak_V=round(study_peak, 2),
                   release_margin_to_guard_min_V=round(g[0] - study_peak, 3),
                   stacked_setpoint_plus_release_V=round(stacked_peak, 3),
                   stacked_margin_to_guard_min_V=round(g[0] - stacked_peak, 3),
                   downstream_limit_V=limit[rail], margin_guard_max_to_limit_V=round(limit[rail] - g[2], 3),
                   filter_us=round(tau * 1e6, 1))
        if ovp:
            row.update(converter_OVP_V=list(TPS552892_DS['ovp']),
                       converter_OVP_note='TPS552892-Q1 VOVP is absolute (22.5-24.5 V), not relative to the 12 V setpoint: '
                                          'it is not a 12 V protection; the U20 guard is',
                       sensitivity_release_from_R109_limit_max={
                           'peak_V': round(sp[2] + release['+12V_from_R109_limit_max']['N=16'][1], 3),
                           'margin_to_guard_min_V': round(g[0] - sp[2] - release['+12V_from_R109_limit_max']['N=16'][1], 3),
                           'note': 'an overload at the R109 limit being released (N=16, low C): a negative margin means a '
                                   'possible nuisance latch-off (fail-safe), not a hazard'})
        else:
            row.update(converter_OVP_V='none (LMR38020 has no output OVP)')
        out[rail] = row
    out['previous'] = {'S8.5_TPS62933F_setpoint_V': [11.51, 12.194, 12.91],
                       'S8_nominal_V': {'+12V': 16.58, '-12V': 15.1},
                       'S8_corners_V': {'+12V': [14.86, 18.45], '-12V': [13.92, 16.36]},
                       'S7_eFuse_OV_nominal_V': {'+12V': 14.4, '-12V': 14.25}}
    out['response_us'] = dict(filter='8-9 (RC)', comparator=1.0, hc74_preset=0.05, tps1663_shdn=1.5,
                              total_after_crossing='~3 us + RC; then U5 off, rails decay')
    out['note'] = ('The bands are threshold screens, not a peak-voltage guarantee: opening U5 does not stop the energy '
                   'already stored behind it. A false trip latches every rail off (MAIN off, press RESET). Common-mode: '
                   'both comparator inputs sit at ~1.24 V at a positive trip, inside VPD-2 V at full temperature; -12V '
                   'compares near 0 V.')
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
    out['note'] = ('BAT54SL VF <= 0.24 V at 0.1 mA is a 25 C limit only: U20 pin 9 stays above -0.3 V at room '
                   'temperature; cold (VF ~+2 mV/C) or at -16 V it can go below -0.3 V (not a guaranteed clamp). Since S8.3 '
                   'U20 runs from VPD, so it MAY be powered in this state (S8.4 review M3, see v3v3_loss): the protection '
                   'argument is that R99 limits the node current to <= 0.15 mA (LM2901B abs max -50 mA into an input) and '
                   'that an incorrect U20 output cannot enable anything while V3V3 is gone (R64 holds RUN low). In normal '
                   'operation the diode is reverse biased by 0.14 V and by ~0 V at the trip point, so its leakage does not '
                   'move the threshold.')
    return out


def v3v3_loss(val):
    """S8.4 (review M3): U20/U18 on always-on VPD when V3V3 (U9) collapses or is not yet up. States, not a transient
    simulation. REF_OV follows V3V3 through R100 (U21 cannot hold it), REF_GOOD = 0, logic U10-U15 unpowered."""
    r98, r99, r100, c67 = val('R98'), val('R99'), val('R100'), val('C67')
    rows = {}
    for vneg in (12.0, 12.624, 16.0):                       # rack -12V held by another supply, incl. a -16 V fault
        voc = -vneg * r98 / (r98 + r99)                      # MON_OVN with REF_OV = 0 and no clamp
        node_bound = vneg / r99                               # all of R99's current, node at 0 V: upper bound
        clamp_i = max(0.0, (vneg - 0.24) / r99 - 0.24 / r98)  # D22 at its 0.1 mA / 25 C VF
        rows[f'-{vneg:g}V'] = dict(MON_OVN_open_circuit_V=round(voc, 3), node_current_bound_uA=round(node_bound * 1e6, 1),
                                   D22_current_25C_uA=round(clamp_i * 1e6, 1), pin_V_25C=-0.24,
                                   pin_V_cold_minus40C_screen=round(-0.24 - 0.002 * 65, 2))
    # Replug into a rack that already holds -12V: S8.5 moved this screen to replug_por() (R98 loads REF_OV while D22
    # clamps MON_OVN; the S8.4 estimate here ignored that load and claimed ~1 ms margin).
    return dict(
        states={'U20 powered (VPD up, V3V3 lost or not yet up)': 'positive channels: REF_OV ~0 V, taps >= 0 V, output '
                'state undefined/low; -12V channel: MON_OVN negative if the rack holds -12V, D22 clamps',
                'U20 unpowered (VPD gone)': 'inputs see the same divider; only the bounded input current matters',
                'logic': 'U10-U15 unpowered, all pull-ups (R97 OV_N, R35/R62 status, R63 MAIN_OK) go to the dead '
                         'V3V3; R64 holds RUN low -> U5 SHDN low, U2 EN (MAIN_OK) low, U4 follows +12V: nothing can be '
                         'enabled by any comparator output'},
        minus12_held=rows, LM2901B_input_abs_max='-0.3 V; input current -50 mA max (SLCS006Z 6.1); footnote: '
        'current through the parasitic input diode can make the output incorrect, normal operation resumes after',
        common_mode='inputs 0..VPD-2 V while VPD >= 15 V except MON_OVN (-0.24 V at 25 C, ~-0.37 V cold screen)',
        D1='SMBJ22A on VPD does not conduct in these states (stand-off 22 V); its 35.5 V rated clamp leaves 0.5 V to '
           'the LM2901B 36 V recommended maximum (38 V abs max): VPD ringing at U18/U20 is a bench gate',
        replug='see replug_por (S8.5): the S8.4 ~1 ms replug margin ignored the R98 load on REF_OV and is withdrawn',
        verdict='No enable path exists while V3V3 is gone; the input current is bounded far below the abs-max. The '
                'D22 clamp is NOT a guaranteed -0.3 V clamp when cold. Replug into a rack holding -12V: OPEN item '
                '(replug_por), not a margin.')


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
    """Headroom while the input-qualified system can run; not power-down qualification. S9.0: the lowest VPD with the
    converters running is the U5 turn-off minimum at the 15 V input (R3 10k)."""
    vpd_min, vpd_clamp = round(u5_window(val)[1][0], 2), 35.5
    margin = vpd_min - 2.0 - (1.259 + 0.0055)
    return dict(supply='VPD before U5, after F1; D1 transient clamp', logic_pullups='V3V3 only',
                qualified_VPD_min_screen_V=vpd_min, common_mode_full_temp_upper_V=vpd_min - 2.0,
                REF_OV_plus_offset_max_V=1.259 + 0.0055, input_headroom_V=round(margin, 3),
                offset_spec_supply_min_V=5, operating_max_V=36, absolute_max_V=38,
                D1_rated_clamp_V=vpd_clamp, rated_clamp_margin_to_operating_max_V=36-vpd_clamp,
                note='Positive headroom during qualified operation. D1 rated clamp is NOT a measured ringing bound. '
                     'Verify VPD spikes <36V at both comparator ICs; V3V3-loss states are in v3v3_loss; cold '
                     'negative-input clamp and replug remain bench gates.')


def basic_only_counterfactual(val, eff, release):
    """S8.4 (review M8): the same threshold screens with every 0.1 % / 25 ppm divider replaced by a 1 % + 1 % TCR Basic
    part. S9.0: the precision dividers left are the U20 guard pairs R93/R94 (+12V) and R98/R99 (-12V). Shows why the
    Extended precision parts are kept."""
    global R01, _PARTS
    saved = R01, _PARTS
    try:
        R01 = R1
        _PARTS = {r: {**q, 'fields': {**q['fields'], 'Tolerance': '1%'}} for r, q in table()[0].items()}
        ov = ov_guard(val, release)
    finally:
        R01, _PARTS = saved
    checks = {}
    for rail in ('+12V', '-12V'):
        checks[f'{rail}_guard_min_above_stacked_peak_V'] = ov[rail]['stacked_margin_to_guard_min_V']
        checks[f'{rail}_guard_max_below_limit_V'] = ov[rail]['margin_guard_max_to_limit_V']
    return dict(guard_V={k: ov[k]['guard_V'] for k in ('+12V', '-12V')},
                margins_V={k: round(v, 3) for k, v in checks.items()},
                failing=sorted(k for k, v in checks.items() if v <= 0),
                precision_refs=PRECISION_REFS,
                note='Every precision divider at 1 % + 1 % TCR (Basic). Any failing entry is a screen the design '
                     'no longer passes; hence the documented Extended exception (sourcing.json basic_only_policy).')


PRECISION_REFS = ['R93', 'R94', 'R98', 'R99']     # S9.0: the 0.1 % / 25 ppm guard dividers (Extended exception)


TYPICAL_RACK_MF = 0.44          # 20 modules x 22 uF per rail (soft_start rack_reference)


INPUT_PATH = {'D10_V': 0.75, 'U5_RON_max_ohm': 0.053, 'I_A': 4.698,
              'basis': 'R2 senses VPD before D10; converter VIN = VPD - D10 (0.75 V S5 screen at 5 A) - U5 RON max '
                       '(53 mOhm, S5) x its 4.698 A high-corner current limit (input_budget U5_limit_screen_A): no steady '
                       'input current can exceed the actual U5 limit, so this is a conservative drop, not a typical one. S9.0: '
                       'unchanged (12.5 V converter input at the 13.5 V rated minimum)'}
INPUT_DROP_V = INPUT_PATH['D10_V'] + INPUT_PATH['U5_RON_max_ohm'] * INPUT_PATH['I_A']      # ~1.0 V
VPD_RATED_MIN = 13.5            # S9.0: minimum loaded 15 V PD input at the module (15 V -5 % = 14.25 V less 0.75 V cable)
VPD_UNLOADED_MIN = 14.25         # 15 V PDO at -5 % (vSrcNew), before any load current flows
VPD_RANGE = (13.5, 16.5)         # S9.0 stated input range at the module (loaded minimum .. +10 % ceiling)
PD_CONTRACT = dict(V=15.0, A=3.0, PDP_W=45.0)   # fixed 15 V PDO ceiling: 3.0 A (SOURCES USB_PD_power_rules)
CABLE_DROP_V = 0.75              # cable/connector allowance at 3 A (as S8: 0.75 V)


def u5_window(val):
    """U5 TPS16630 UVLO on/off thresholds referred to VPD (R2/R3 1 % + 1 % TCR, UVLO 1.176/1.2/1.224 V rising,
    1.09/1.122/1.15 V falling). The +/-150 nA pin leakage flows through the top resistor, so it shifts the VPD
    threshold by I x R2 (S8.4 review fix; S8.3-era screens used R2 || R3). The converters can only start above
    the rising band and keep running down to the falling one."""
    lo, hi = R1
    leak = 150e-9 * val('R2') * hi

    def band(vmin, vtyp, vmax):
        return [vmin * (1 + val('R2') * lo / (val('R3') * hi)) - leak, vtyp * (1 + val('R2') / val('R3')),
                vmax * (1 + val('R2') * hi / (val('R3') * lo)) + leak]
    return band(1.176, 1.2, 1.224), band(1.09, 1.122, 1.15)


def converter_vin(vpd):
    """Converter input (VIN) for a given VPD after the D10 + U5 drop screen."""
    return round(vpd - INPUT_DROP_V, 2)


def minus12_startup(val, eff):
    """S8.4 (review M6): -12V start-up into rack capacitance per the LMR38020 rule (SNVSC40E 8.3.8/8.3.9): hiccup
    needs FB < 40 % of VREF (|Vout| < 0.4 x 11.99 V = 4.8 V) WHILE the low-side limit acts for 256 cycles, and is
    disabled for TOCP_BLK (18 ms typical, no minimum) from power-up. So the rail only has to pass 4.8 V inside the
    blanking time; above that it keeps charging at the current limit without hiccup. Output current in limit:
    (ILS_min 1.8 A + ripple/2) x (1 - D), D = V / (VIN + V), integrated from 0 V with a constant load current from
    0 V (conservative: real modules draw less at low voltage). S8.3 required the full 12 V within 18 ms."""
    vref_mag = 1.0 * (1 + val('R14') / val('R15'))
    v40 = 0.4 * vref_mag
    inductance, fsw, ils = 15e-6, 0.79e6, 1.8
    bank_hi = eff['-12V'][1]
    on, off = u5_window(val)
    vin_floor, vin_sag = converter_vin(on[0]), converter_vin(off[0])     # converter VIN, not VPD (review fix)
    vin_rated = converter_vin(VPD_RATED_MIN)
    n_bank = sum(1 for p in table()[0].values() if p['value'] == '22u' and '-12V' in p['pins'].values())
    design_mF = n_bank * 22e-3                       # rated onboard -12V bank (7 x 22 uF)
    ti_total_mF = min(10 * design_mF, 1.0)           # SNVSC40E 9.2.2.5: ~10 x design value or 1000 uF, smaller

    def io(v, vin):
        d = v / (vin + v)
        return (ils + vin * d / (inductance * fsw) / 2) * (1 - d)

    def seconds_per_farad(v_to, vin, iload, steps=4000):
        acc = 0.0
        for k in range(steps):
            v = (k + 0.5) * v_to / steps
            net = io(v, vin) - iload
            if net <= 0:
                return None
            acc += v_to / steps / net
        return acc
    cases = {}
    for vin in (vin_sag, vin_floor, vin_rated, converter_vin(PD_CONTRACT['V'])):
        for iload in (PUBLISHED_A['-12V'], 0.9):          # S9.0: the published 0.8 A and the S8.5 rating
            for blank in (18e-3, 9e-3):
                k = seconds_per_farad(v40, vin, iload)
                c_max = blank / k
                k_full = seconds_per_farad(vref_mag, vin, iload)
                assert k_full is not None, ('-12V cannot reach regulation at this load', vin, iload)
                t_full = c_max * k_full
                cases[f'VIN{vin:g}_I{iload:g}A_blank{blank*1e3:g}ms'] = dict(
                    total_C_max_mF=round(c_max * 1e3, 3), rack_allowance_mF=round((c_max - bank_hi) * 1e3, 3),
                    time_to_full_12V_at_that_C_ms=round(t_full * 1e3, 1), io_at_12V_A=round(io(vref_mag, vin), 3))
    key = f'VIN{vin_floor:g}_I{PUBLISHED_A["-12V"]:g}A_blank9ms'
    model = cases[key]['rack_allowance_mF']
    ti_rack = round(ti_total_mF - design_mF, 3)
    pub = round(min(model, ti_rack), 3)
    return dict(rule=f'hiccup only if |Vout| < 40 % ({v40:.2f} V) with ILS limiting for 256 cycles after TOCP_BLK',
                v40_V=round(v40, 3), onboard_bank_high_mF=round(bank_hi * 1e3, 3), cases=cases,
                vin_floor_V=vin_floor,
                vin_floor_basis=f'converter VIN at the U5 turn-on minimum (VPD {on[0]:.2f} V) minus the {INPUT_DROP_V:.2f} V '
                                'D10 + U5 drop: the converters cannot start below it',
                vin_sag_sensitivity_V=vin_sag,
                vin_sag_basis=f'converter VIN at the U5 turn-off minimum (VPD {off[0]:.2f} V): a source sagging during '
                              'start-up can hold the converters this low',
                input_path=INPUT_PATH,
                hiccup_model_allowance_mF=model,
                hiccup_model_basis=f'{key}: converter VIN at the U5 turn-on minimum, the published 0.8 A from 0 V, half the typical-only '
                                   '18 ms blanking (TI gives no minimum)',
                TI_COUT_guidance={'design_value_mF': round(design_mF, 3), 'total_limit_mF': ti_total_mF,
                                  'rack_allowance_mF': ti_rack,
                                  'text': 'limit total output capacitance to ~10 x the design value or 1000 uF, whichever '
                                          'is smaller (SNVSC40E 9.2.2.5); beyond it start-up at full load and loop '
                                          'stability need a dedicated study'},
                published_allowance_mF=pub,
                published_basis='min(hiccup model, TI output-capacitance guidance minus the rated onboard bank)',
                typical_rack_mF=TYPICAL_RACK_MF, typical_rack_starts=pub > TYPICAL_RACK_MF,
                margin_to_typical_rack_mF=round(pub - TYPICAL_RACK_MF, 3),
                model_covers_published_at_sag=cases[f'VIN{vin_sag:g}_I{PUBLISHED_A["-12V"]:g}A_blank9ms']['rack_allowance_mF'] >= pub,
                window_check='time to full 12 V at the allowance stays far below the 309 ms startup-window minimum',
                note='Analytic screen, not a guarantee: TOCP_BLK has no specified minimum and the hiccup restart '
                     'behaviour is not specified. The rack capacitance sits behind cables, but TI\'s total-COUT guidance '
                     'is applied anyway. Bench gate: start into the real rack at the lowest input.')


def n12_capability(vin):
    """LMR38020 IBB output capability (ILS min 1.8 A + ripple/2)(1 - D) at a converter input (SNVSC40E Eq. 7)."""
    d = 11.989 / (vin + 11.989)
    return (1.8 + vin * d / (15e-6 * 0.79e6) / 2) * (1 - d)


def p12_capability(val, vin):
    """TPS552892-Q1 +12V output capability at a converter input: the R109 constant-current minimum, unless the average
    inductor limit (7 A min) binds first in boost mode (IL = IOUT x VOUT / (VIN x eta), eta 0.9 screen)."""
    op = p12(val)
    vo = op['setpoint_V'][2]
    il_cap = TPS552892_DS['ilim_avg'][0] * (min(1.0, vin * 0.9 / vo) if vin < vo else 1.0)
    return min(op['icc_A'][0], il_cap)


def input_power(amps, vpd, eta=None, u5_ron=INPUT_PATH['U5_RON_max_ohm']):
    """Module input power and current for per-rail output currents at a VPD: converter input (planning efficiencies)
    plus the D10 drop (0.75 V screen), U5 RON and 0.5 W auxiliary logic/LDO, solved for the input current."""
    eta = eta or ETA_ASSUMED
    vo = {'+12V': 12.08, '-12V': 11.989}
    conv = sum(vo[k] * amps[k] / eta[k] for k in amps)
    i = conv / vpd
    for _ in range(30):
        i = (conv + INPUT_PATH['D10_V'] * i + u5_ron * i * i + 0.5) / vpd
    return conv + INPUT_PATH['D10_V'] * i + u5_ron * i * i + 0.5, i


def delivered_at_input_limit(vpd, i_in=PD_CONTRACT['A'], eta=None, ratings=None):
    """Largest simultaneous delivered power at an input-current limit, worst efficiency mix: -12V at its published
    rating first (lower efficiency), +12V takes the rest (capped at its rating). ratings: per-rail A (default S9.0)."""
    eta = eta or ETA_ASSUMED
    ratings = ratings or PUBLISHED_A
    p_in = vpd * i_in
    conv = p_in - INPUT_PATH['D10_V'] * i_in - INPUT_PATH['U5_RON_max_ohm'] * i_in ** 2 - 0.5
    n12_out = 11.989 * ratings['-12V']
    p12_out = min(12.08 * ratings['+12V'], (conv - n12_out / eta['-12V']) * eta['+12V'])
    best = min(12.08 * ratings['+12V'], conv * eta['+12V']) + max(0.0, min(n12_out, (conv - 12.08 *
                                                                            ratings['+12V'] / eta['+12V']) * eta['-12V']))
    return dict(input_W=round(p_in, 2), converter_input_W=round(conv, 2), worst_mix_delivered_W=round(n12_out + p12_out, 2),
                best_mix_delivered_W=round(best, 2))


def rating(val, eff):
    """S8.4 (review M5) rule, S9.0 values: published conservative continuous rating (prototype, unqualified), valid for the
    stated input range (VPD >= 13.5 V loaded; converter VIN after D10 + U5). Per rail: 75 % of the minimum current-limited
    capability there, to the nearest 0.1 A, capped at the S7 target. +12V capability is the R109 constant-current minimum
    (the TPS552892 inductor limit is far above it at every input); -12V the LMR38020 Eq. 7 at the 12.5 V converter input.
    S9.0: the 15 V / 3 A contract caps the SIMULTANEOUS total below the sum of the per-rail ratings (published_total_W)."""
    vin_floor = converter_vin(VPD_RATED_MIN)
    vin_run = converter_vin(u5_window(val)[1][0])     # sensitivity: U5 keeps running down to its turn-off minimum
    cap = {'+12V': p12_capability(val, vin_floor), '-12V': n12_capability(vin_floor)}
    target = {'+12V': 2.5, '-12V': 1.0}
    rule = {k: min(target[k], round(0.75 * cap[k], 1)) for k in cap}
    assert PUBLISHED_A == rule, (PUBLISHED_A, rule)
    run = {'+12V': p12_capability(val, vin_run), '-12V': n12_capability(vin_run)}
    vo = {'+12V': 12.08, '-12V': 11.989}
    per_rail_sum = sum(vo[k] * PUBLISHED_A[k] for k in vo)
    w_min = delivered_at_input_limit(VPD_RATED_MIN)
    w_nom = delivered_at_input_limit(PD_CONTRACT['V'] - CABLE_DROP_V)
    total = math.floor(w_min['worst_mix_delivered_W'])
    p_all, i_all = input_power(PUBLISHED_A, VPD_RATED_MIN)
    return dict(
        published_A=PUBLISHED_A, rule=f'75 % of the minimum current-limited capability at the {vin_floor:g} V converter '
        f'input (rated minimum VPD {VPD_RATED_MIN:g} V minus the {INPUT_DROP_V:.2f} V D10 + U5 drop), to the NEAREST 0.1 A, '
        'capped at the S7 target', vin_floor_V=vin_floor, vpd_rated_min_V=VPD_RATED_MIN,
        input_path=INPUT_PATH,
        capability_min_A={k: round(v, 3) for k, v in cap.items()},
        capability_basis={'+12V': 'R109 constant-current minimum 48 mV / (15 mOhm x 1.01 x 1.0075)',
                          '-12V': 'LMR38020 (ILS min + ripple/2)(1 - D), SNVSC40E Eq. 7'},
        fraction_of_capability={k: round(PUBLISHED_A[k] / cap[k], 3) for k in cap},
        headroom_to_capability_A={k: round(cap[k] - PUBLISHED_A[k], 3) for k in cap},
        published_total_W=total,
        total_basis=f'the 15 V / 3.0 A contract at the {VPD_RATED_MIN:g} V rated minimum: {w_min["input_W"]} W in, '
                    f'{w_min["converter_input_W"]} W after D10/U5/aux, worst efficiency mix (-12V at its rating first) '
                    f'{w_min["worst_mix_delivered_W"]} W delivered, rounded DOWN to the watt',
        per_rail_ratings_sum_W=round(per_rail_sum, 1),
        per_rail_ratings_at_once={'input_W': round(p_all, 1), 'input_A_at_13V5': round(i_all, 2),
                                  'exceeds_3A_contract': i_all > PD_CONTRACT['A']},
        at_nominal_15V_source={'VPD_V': PD_CONTRACT['V'] - CABLE_DROP_V, **w_nom},
        below_rated_range={'converter_VIN_V': vin_run, 'basis': 'U5 keeps the converters running down to its turn-off '
                           'minimum (sagging source); the rating is NOT specified there',
                           'capability_min_A': {k: round(v, 3) for k, v in run.items()},
                           'fraction_of_capability': {k: round(PUBLISHED_A[k] / run[k], 3) for k in run}},
        simultaneous={'delivered_W_at_all_ratings': round(per_rail_sum, 1), 'published_total_W': total,
                      'U5_limit_min_A': 3.693, 'contract_A': PD_CONTRACT['A'],
                      'note': 'U5 (3.69-4.70 A) does not enforce the 3 A contract: above the published total the source '
                              'decides (current limit or a PD hard reset; a brown-out after ARMED latches FAULT)'},
        S85_rating_A={'+12V': 2.5, '+5V': 2.0, '-12V': 0.9, 'total_W': 45, 'input': '20 V, VPD >= 18.25 V'},
        headers='above ~2 A per rail use both J2 and J3 (2 contacts per rail per header, ~1 A IDC contact screen)',
        note='Prototype rating from datasheet minimum limits and assumed efficiencies, not a measured or thermal-qualified '
             'rating.')


def startup_window(val):
    """Qualification window (U11, C49) against the rail-up budget. S9.0: U5 dVdt ramp to the 16.5 V input maximum, PGOOD
    deglitch, the TPS552892-Q1 fixed soft start (max) plus charging TI's 1000 uF effective COUT ceiling at the R109 limit
    minimum less the full published load, the LMR38020 soft start + OCP blanking (no U23 ramp, no TPS62933F CSS)."""
    t = val('C49') * 1e9 / 175 + .0005
    op = p12(val)
    budget = dict(U5_ramp_ms=round(VPD_RANGE[1] / (1.775e-6 * 23.5 / (val('C3') * 1.1)) * 1e3, 1), PGOOD_deglitch_ms=13,
                  TPS552892_SS_max_ms=TPS552892_DS['tss_ms'][2],
                  P12_rack_charge_at_R109_limit_ms=round(1e-3 * op['setpoint_V'][2] / (op['icc_A'][0] - op['i_pub']) * 1e3, 1),
                  LMR38020_SS_plus_blank_ms=18 + 4)
    total = sum(budget.values())
    return dict(typ_s=round(t, 3), min_s_screen=round(t * .6 * .9, 3), max_s_screen=round(t * 1.4 * 1.1, 3),
                S7_typ_s=round(1e-6 * 1e9 / 175 + .0005, 2),
                rail_up_budget_ms=budget, rail_up_total_ms=round(total, 1),
                ratio_min_window_to_budget=round(t * .6 * .9 / (total / 1e3), 1),
                arming='S8.5: one-shot, see arming (TIMER_GO = RUN AND STARTED; S8.4 RUN AND MAIN_OK was restartable)')


VSAFE5V_MAX = 5.5                # USB PD vSafe5V maximum (SOURCES USB_PD_vSafe5V)
V20_MARGIN_MIN_V = 2.0           # required V20_OK band clearance to vSafe5V max and to the U5 turn-off minimum


def v20_band(val, r83=None):
    """V20_OK trip (VPD) over V3V3 +-2 %, R73/R74 and R83/R84 at 1 % + 1 % TCR, LM2901B VIO 5.5 mV and IB 0-50 nA out
    of the pin (it lowers the trip by up to IB x R83, so it only widens the minimum; same model as S8.4)."""
    lo, hi = R1
    r83 = val('R83') if r83 is None else r83

    def ref_good(v3, a, b, e):
        return v3 * val('R74') * b / (val('R73') * a + val('R74') * b) + e
    return [ref_good(3.3 * .98, hi, lo, -0.0055) * (1 + r83 * lo / (val('R84') * hi)) - 50e-9 * r83,
            ref_good(3.3, 1, 1, 0) * (1 + r83 / val('R84')),
            ref_good(3.3 * 1.02, lo, hi, 0.0055) * (1 + r83 * hi / (val('R84') * lo))]


def v20_floor_ok(band, off):
    """S8.5 rule for V20_OK as a U5 status-validity floor: clear of the PD 5 V phase and below the U5 turn-off minimum."""
    return band[0] >= VSAFE5V_MAX + V20_MARGIN_MIN_V and band[2] <= off[0] - V20_MARGIN_MIN_V


def arming(val):
    """S8.5 (item B) one-shot arming, S9.0 values: required behaviour, the topology that delivers it (unchanged), the
    V20_OK divider with tolerance/temperature at the 15 V input (R83 100k) and the windows it replaces. The +5V input of
    the bad-status NAND is tied high (ANY_BAD without P5_OK). Timelines: validation.json startup_arming (verify_s8)."""
    win = startup_window(val)
    on, off = u5_window(val)
    v20 = v20_band(val)
    v20_s85, v20_s84, v20_s83 = v20_band(val, 120e3), v20_band(val, 200e3), v20_band(val, 220e3)
    return dict(
        required=['R1 bounded: ARMED within the U11 delay (0.31-0.88 s) of the first converter enable after RESET, and '
                  'held until RESET/FAULT: the converters can never run unarmed for longer',
                  'R2 no restart: nothing a fault can toggle (MAIN_OK, PGOOD, VPD, V20_OK, the rails) restarts or extends '
                  'the window; only RESET (or a power-on reset) does',
                  'R3 no early arming: the window starts only at a genuine converter enable, i.e. U5 on through its own '
                  'UVLO with valid status; the PD 5 V phase or an intermediate PDO cannot start it, so no threshold below '
                  'the converter enable point can arm',
                  'R4 fail-safe: after ARMED any bad status > ~1 ms latches FAULT; FAULT holds RUN low until RESET; OV_N '
                  '(U20 guard: +12V and -12V channels) presets FAULT at any time'],
        topology={'STARTED': 'U12 flip-flop A used as a set/reset latch: PRE_N = START_N, CLR_N = RESET_N, CLK = GND '
                             '(no clock edges), D = V3V3, Q = STARTED (TP19)',
                  'START_N': 'U14 gate 2: NAND(MAIN_LED_OK, RUN, V3V3, V3V3); low once U5 is on with PGOOD and FLT good, '
                             'its status validated by V20_OK, while RUN. Level-sensitive, so a MAIN_OK that is already high '
                             'at RESET release (PGOOD deglitch) still starts it; RUN in the gate keeps PRE_N high while '
                             'RESET clears the latch',
                  'TIMER_GO': 'U13 gate 3 = RUN AND STARTED -> R69/R70 -> U11 SENSE (unchanged divider)',
                  'ARMED': 'U11 RESET output (R71 pull-up) = ARMED directly; it stays high because its input is latched',
                  'ANY_BAD': 'U14 gate 1 = NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3): S9.0 ties the former P5_OK input high',
                  'FAULT': 'U12 flip-flop B: CLK = ARMED AND BAD_FILTERED (U13 gate 2, R72/C51 + U15), PRE_N = OV_N, '
                           'CLR_N = RESET_N; RUN = RESET_N AND NOT_FAULT (U5 SHDN; U2 EN = MAIN_OK; U4 via Q1)',
                  'parts': 'no new IC: the spare U14 gate and U12 flip-flop A re-used; S9.0 R83 120k -> 100k (Basic, the '
                           '100k line of R2/R6/R14/R16/R17, no new code), TP19 (copper)'},
        V20_OK={'role': 'U5 status-validity floor: masks U5 FLT/PGOOD (MAIN_OK, R63 pull-up) where U5 is below its '
                        '4.5 V operating minimum (PD 5 V phase); NOT an input-good threshold',
                'band_V': [round(v, 3) for v in v20], 'R83': val('R83'),
                'rule': f'band minimum >= vSafe5V max {VSAFE5V_MAX} V + {V20_MARGIN_MIN_V} V and band maximum <= U5 '
                        f'turn-off minimum - {V20_MARGIN_MIN_V} V',
                'rule_holds': v20_floor_ok(v20, off),
                'margin_above_vSafe5V_max_V': round(v20[0] - VSAFE5V_MAX, 3),
                'margin_below_U5_off_min_V': round(off[0] - v20[2], 3),
                'consequence': f'whenever U5 can be on (VPD >= its {off[0]:.2f} V turn-off minimum) V20_OK is high, so '
                               'MAIN_LED_OK = MAIN_OK there and V20_OK can never be the first status to drop; ANY_BAD = '
                               'NOT(MAIN_LED_OK AND P12_OK AND N12_OK) means "U5 not on with valid status, or a rail below '
                               'its monitor threshold"',
                'S8.5_120k_band_V': [round(v, 3) for v in v20_s85], 'S8.5_120k_rule_holds_at_15V': v20_floor_ok(v20_s85, off),
                'S8.4_200k_band_V': [round(v, 3) for v in v20_s84], 'S8.4_200k_rule_holds': v20_floor_ok(v20_s84, off),
                'S8.3_220k_band_V': [round(v, 3) for v in v20_s83],
                'history': 'S8.5 (20 V input): R83 120k, 9.06-10.96 V. At the 15 V input its maximum sits above the U5 '
                           'turn-off minimum less 2 V, so S9.0 uses 100k. S8.4 200k / S8.3 220k tripped inside the U5 band '
                           '(they meant neither "input good" nor "status valid")'},
        U5_on_V=[round(v, 3) for v in on], U5_off_V=[round(v, 3) for v in off],
        U5_turn_on_margin_unloaded_V=round(VPD_UNLOADED_MIN - on[2], 3),
        U5_running_margin_loaded_V=round(VPD_RATED_MIN - off[2], 3),
        input_qualification=f'U5 UVLO through MAIN_OK (R2/R3 100k/10k): on {on[0]:.2f}-{on[2]:.2f} V (unloaded source: '
                            f'15 V -5 % = {VPD_UNLOADED_MIN} V, {VPD_UNLOADED_MIN - on[2]:.2f} V margin), off '
                            f'{off[0]:.2f}-{off[2]:.2f} V (loaded minimum {VPD_RATED_MIN} V, {VPD_RATED_MIN - off[2]:.2f} V '
                            'margin). Start-up needs an unloaded source >= the turn-on maximum: any compliant 15 V PDO',
        window=win,
        sequence=['USB-C attach: VPD = vSafe5V; U9 makes V3V3; U10 holds RESET_N low >= 12 ms (clears STARTED, FAULT)',
                  'RESET_N high: RUN high (U5 SHDN released); U5 in UVLO, START_N high (V20_OK low in the 5 V phase)',
                  f'PD contract: VPD -> 15 V; V20_OK high at {v20[0]:.2f}-{v20[2]:.2f} V (U5 status valid, PGOOD low)',
                  f'VPD >= U5 turn-on ({on[0]:.2f}-{on[2]:.2f} V): U5 ramps (dVdt, <= ~10 ms to 16.5 V), PGOOD 11.5 ms typ '
                  '-> MAIN_OK enables U2 (EN/UVLO) (U4 follows +12V via Q1) -> MAIN_LED_OK -> START_N low -> STARTED '
                  '(latched)',
                  'TIMER_GO = RUN AND STARTED -> U11 -> ARMED after 0.31-0.88 s; rails are up within ~%.0f ms' % (
                      win['rail_up_total_ms']),
                  'ARMED: any bad status (MAIN_LED_OK, P12_OK, N12_OK) > ~1 ms -> FAULT -> RUN low -> all off until '
                  'RESET; OV_N (+12V > 14.48-15.27 V, -12V beyond 13.27-14.02 V) presets FAULT at any time'],
        timelines='validation.json startup_arming.timelines (verify_s8 arming_timelines: cold start at the worst loaded '
                  '15 V minimum, slow PD contract, brown-out after/inside the window, input overload chatter, hot plug '
                  'into a live bus, load release, U20 guard before ARMED, short RESET), checked against R1-R4 from the '
                  'native gate wiring; the S8.4 wiring fails them (test_s8 regression)')


def replug_por(val):
    """S8.4 Astra MAJOR-1: replug into a rack that holds -12V. The U20 -12V channel reads OV until REF_OV exceeds
    |V| x R98/R99 (+ offset/bias); REF_OV charges through R100 into C67 while R98 already draws current toward the
    clamped MON_OVN node (D22 ~ -0.24 V), so the Thevenin source is V3V3 x R98 / (R98 + R100) behind R100 || R98. If
    REF_OV is still below the clear level when U10 releases RESET (>= 12 ms), OV_N presets FAULT: nuisance latch-off."""
    r98n, r99n, r100n, c67n = val('R98'), val('R99'), val('R100'), val('C67')
    rows = {}
    for vneg in (12.0, 12.624):
        for name, (k100, k67, v3, k98, k99, e) in {'nominal': (1, 1, 3.3, 1, 1, 0.0),
                                                   'worst': (R1[1], 1.10 * 1.15, 3.3 * .98, R01[1], R01[0], 0.0055)}.items():
            r98, r99, r100, c67 = r98n * k98, r99n * k99, r100n * k100, c67n * k67
            need = (vneg * r98 + (e + 50e-9 * r98 * r99 / (r98 + r99)) * (r98 + r99)) / r99 if name == 'worst' \
                else vneg * r98 / r99
            vth = (v3 * r98 + (-0.24) * r100) / (r98 + r100)
            rth = r98 * r100 / (r98 + r100)
            t = rth * c67 * math.log(vth / (vth - need)) if vth > need else float('inf')
            rows[f'-{vneg:g}V_{name}'] = dict(REF_OV_needed_V=round(need, 4), thevenin_V=round(vth, 3),
                                              thevenin_kohm=round(rth / 1e3, 3), C67_uF=round(c67 * 1e6, 2),
                                              settle_ms=round(t * 1e3, 2))
    por_min_ms = 12.0
    worst = max(r['settle_ms'] for r in rows.values())
    return dict(cases=rows, POR_RESET_release_min_ms=por_min_ms, worst_settle_ms=worst,
                margin_ms=round(por_min_ms - worst, 2), established=worst < por_min_ms,
                corners='worst: R100 +2 % (1 % + 1 % TCR), C67 +10 % tolerance x +15 % X5R temperature (12.65 uF), V3V3 -2 %, '
                        'R98/R99 0.1 % corners, LM2901B 5.5 mV offset and 50 nA bias; V3V3 rise time ignored (it only '
                        'helps: REF_OV starts charging before the POR delay starts)',
                S84_screen='S8.4 v3v3_loss: 8.2-10.7 ms, ~1 ms margin; it charged C67 from V3V3 through R100 alone and '
                           'ignored the R98 current into the D22-clamped MON_OVN node. Withdrawn',
                consequence='OV_N low at RESET release presets FAULT: MAIN stays off until RESET is pressed (fail-safe '
                            'nuisance latch, no damage). Only when the -12V bus is held by something else at power-up '
                            '(second supply, or a quick replug while the rack capacitance still holds -12V).',
                status='OPEN: the margin is not established; candidate fixes (not implemented in S8.5): C67 4.7 uF '
                       '(still right of the TLV431 instability region) roughly halves the settle time, or a CT capacitor '
                       'on U10 lengthens the POR delay (both also change the RESET timing).')


def input_budget():
    """S9.0 input budget at the 15 V / 3 A contract: the per-rail ratings at once against the contract, and the U5 limit."""
    p_all, i_all = input_power(PUBLISHED_A, VPD_RATED_MIN)
    p_nom, i_nom = input_power(PUBLISHED_A, PD_CONTRACT['V'] - CABLE_DROP_V)
    removed = {'U6_U7_2x31mohm_at_2.5A': 2 * 0.031 * 2.5 ** 2, 'LM5067_path_50mohm+Q4_at_1A': 1.0 * (0.05 + 0.1)}
    return dict(contract=PD_CONTRACT, per_rail_ratings_outputs_W=round(12.08 * PUBLISHED_A['+12V'] + 11.989 *
                                                                       PUBLISHED_A['-12V'], 1),
                at_13V5={'input_W': round(p_all, 1), 'input_A': round(i_all, 2)},
                at_14V25={'input_W': round(p_nom, 1), 'input_A': round(i_nom, 2)},
                losses_at_3A_W={'D10_0.75V': round(0.75 * 3.0, 2), 'U5_53mohm_max': round(0.053 * 9, 2),
                                'aux_logic_LDO': 0.5},
                U5_limit_screen_A=[3.693, 4.186, 4.698],
                margin_U5_min_to_contract_A=round(3.693 - PD_CONTRACT['A'], 3),
                eFuse_losses_removed_W={k: round(v, 2) for k, v in removed.items()},
                efficiency_assumption=ETA_ASSUMED,
                note='planning estimate; efficiencies are assumptions. The per-rail ratings at once exceed the 3 A contract '
                     'at the 13.5 V minimum, hence the published simultaneous total (rating.published_total_W)')


def connectors():
    targets = dict(PUBLISHED_A)
    gnd = sum(targets.values())
    one = {k: round(v / 2, 3) for k, v in targets.items()}; one['GND (no cancellation)'] = round(gnd / 6, 3)
    two = {k: round(v / 4, 3) for k, v in targets.items()}; two['GND (no cancellation)'] = round(gnd / 12, 3)
    return dict(per_contact_A_one_header=one, per_contact_A_two_headers_equal_split=two,
                contacts_per_header={'+12V': 2, '-12V': 2, 'GND': 6, 'pins 11/12': 'open (S9.0, no +5V)'},
                guidance='typical 2.54 mm IDC/ribbon contact ~1 A: use both headers above ~2 A per rail; '
                         'unequal cable lengths/loads do not split equally')


def plus12_buckboost(val, eff):
    """S9.0 step 2, the +12V duty-cycle problem and its resolution. (1) The S8 TPS62933F buck cannot regulate at the 15 V
    input: its required duty at the 12.5 V low-line converter input exceeds the 98 % maximum even unloaded at the setpoint
    maximum, and the minimum converter input it would need lies above every compliant 15 V source; a lower +12V current
    or a higher minimum input therefore cannot fix it. (2) The TPS552892-Q1 four-switch buck-boost regulates over the whole
    range (buck above VOUT, alternating buck/boost near it, boost below), checked against its minimum on/off times and its
    average inductor limit, from the U5 turn-off sag (10.55 V) to the later 20 V retarget (21 V). (3) Losses/thermal,
    current limit and compensation screens."""
    op = p12(val)
    ds = TPS552892_DS
    rds = ds['rds']
    vin_lo, vin_hi = converter_vin(VPD_RATED_MIN), VPD_RANGE[1]
    vin_sag = converter_vin(u5_window(val)[1][0])
    lo, hi = R1
    sp8 = [0.784 * (1 + 47e3 * lo / (3.3e3 * hi)), 0.8 * (1 + 47 / 3.3), 0.816 * (1 + 47e3 * hi / (3.3e3 * lo))]

    def s8_duty(vin, vo, i):        # buck in CCM incl. L1 DCR and the 76 mOhm high-side switch (SLUSEA4D)
        return (vo + i * 0.022) / (vin - i * 0.076)
    s8 = {'setpoint_V': [round(v, 3) for v in sp8], 'D_max': 0.98,
          'required_duty': {f'VIN{vin_lo:g}_I{i:g}A_{name}': round(s8_duty(vin_lo, vo, i), 3)
                            for i in (0.0, 2.5) for name, vo in (('nom', sp8[1]), ('max', sp8[2]))}}
    vin_need = (sp8[2] + 2.5 * 0.022) / 0.98 + 2.5 * 0.076
    s8.update(min_converter_VIN_for_regulation_V=round(vin_need, 2),
              min_VPD_for_regulation_V=round(vin_need + INPUT_DROP_V, 2),
              regulates_at_rated_min=s8_duty(vin_lo, sp8[2], 2.5) <= 0.98,
              regulates_unloaded_at_rated_min=s8_duty(vin_lo, sp8[2], 0.0) <= 0.98,
              verdict=f'out of regulation: needs VPD >= {vin_need + INPUT_DROP_V:.2f} V at 2.5 A and the setpoint maximum, '
                      f'above the {VPD_UNLOADED_MIN} V unloaded minimum of a compliant 15 V source; it fails even at 0 A '
                      f'({s8_duty(vin_lo, sp8[2], 0.0):.3f} > 0.98), so neither a lower +12V current nor a higher minimum '
                      'input inside the USB PD tolerance can fix it')
    rows = {}
    f_lo, f_nom, f_hi = op['fsw_Hz']
    d_on_min, d_boost_max = ds['ton_min'] * f_hi, 1 - ds['toff_min'] * f_hi
    for vin in (vin_sag, vin_lo, converter_vin(PD_CONTRACT['V']), vin_hi, 21.0):
        for i in (op['i_pub'], op['icc_A'][2]):
            vo_lo, vo_hi = op['setpoint_V'][0], op['setpoint_V'][2]
            if vin > vo_hi + 0.5:
                mode = 'buck'
            elif vin < vo_lo - 0.5:
                mode = 'boost'
            else:
                mode = 'buck-boost (alternating cycles)'
            d_buck = min((vo_lo + i * (rds['hs2'] + op['dcr'] + op['r_sense'])) / max(vin - i * rds['hs1'], 1e-6), 1.0)
            d_boost = max(0.0, 1 - (vin - i * (rds['hs1'] + op['dcr'])) / (vo_hi + i * (rds['hs2'] + op['r_sense'])))
            il = i if vin >= vo_hi else i * vo_hi / (vin * 0.9)
            ripple = ((vin - vo_hi) * vo_hi / (op['L'] * f_lo * vin) if vin > vo_hi
                      else vin * (vo_hi - vin) / (op['L'] * f_lo * vo_hi))
            ok = (d_buck >= d_on_min if mode == 'buck' else True) and d_boost <= d_boost_max \
                and il + ripple / 2 < ds['ilim_avg'][0]
            rows[f'VIN{vin:g}_I{i:.2f}A'] = dict(
                mode=mode, buck_duty_at_setpoint_min=round(d_buck, 3), boost_duty_at_setpoint_max=round(d_boost, 3),
                IL_avg_A=round(il, 3), ripple_pp_A=round(abs(ripple), 3), IL_peak_A=round(il + abs(ripple) / 2, 3),
                margin_to_ILIM_AVG_min_A=round(ds['ilim_avg'][0] - il - abs(ripple) / 2, 3), regulates=ok)
    # losses at the near-unity worst point (both legs switching) and the R109 limit; assumptions stated in 'loss_model'
    loss = {}
    for i in (op['i_pub'], op['icc_A'][2]):
        il = i / 0.95
        cond = il ** 2 * (rds['hs1'] + rds['hs2'] + max(rds['ls1'], rds['ls2'])) * 1.5
        sw = 2 * 0.5 * vin_lo * il * 10e-9 * f_nom
        dead = 2 * 2 * 0.7 * il * 20e-9 * f_nom
        vcc = vin_lo * ds['ieff_vcc_A']
        p_ic = cond + sw + dead + vcc
        p_l = il ** 2 * 0.022 * 1.3
        p_r = i ** 2 * op['r_sense'] * R109_TOL[1]
        pout = op['vo_nom'] * i
        loss[f'I{i:.2f}A'] = dict(P_IC_W=round(p_ic, 3), P_L1_DCR_W=round(p_l, 3), P_R109_W=round(p_r, 3),
                                  efficiency_screen=round(pout / (pout + p_ic + p_l + p_r), 3),
                                  Tj_rise_C_JEDEC=round(p_ic * ds['rth_ja'][0], 1), Tj_rise_C_EVM=round(p_ic * ds['rth_ja'][1], 1),
                                  Tj_at_50C_ambient_JEDEC_C=round(50 + p_ic * ds['rth_ja'][0], 1))
    sw_400 = 2 * 0.5 * vin_lo * (op['i_pub'] / 0.95) * 10e-9 * 400e3
    # compensation (TI Eq. 19-26), boost corner (most restrictive), R111/C83 as fitted
    rload = op['vo_nom'] / op['i_pub']
    d_b = max(0.0, 1 - vin_sag / op['vo_nom'])

    def fc(cout):
        return val('R111') * (1 - d_b) * ds['vref'][1] * ds['gea'] / (2 * math.pi * op['vo_nom'] * ds['rsense_int'] * cout)
    c_lo, c_hi = eff['+12V'][0], eff['+12V'][1]
    comp = dict(R111_ohm=val('R111'), C83_F=val('C83'), zero_Hz=round(1 / (2 * math.pi * val('R111') * val('C83'))),
                crossover_Hz={'bank_low_C': round(fc(c_lo)), 'bank_high_C': round(fc(c_hi)),
                              'bank_high_plus_typical_rack': round(fc(c_hi + TYPICAL_RACK_MF * 1e-3))},
                RHPZ_boost_corner_Hz=round(rload * (1 - d_b) ** 2 / (2 * math.pi * op['L'])),
                fc_limit_Hz=round(min(op['fsw_Hz'][0] / 10, rload * (1 - d_b) ** 2 / (2 * math.pi * op['L']) / 5)),
                CC_from_Eq25_nF=round(rload * c_lo / (2 * val('R111')) * 1e9, 1),
                note='TI Eq. 24-26 with the internal 55 mOhm current-sense equivalent and GEA 190 uA/V. With the rack '
                     'capacitance behind the cables the crossover falls below the 1.7 kHz zero: loop stability with the '
                     'real rack is a bench Bode gate, not established here')
    return dict(
        S8_TPS62933F_at_15V=s8,
        TPS552892_operation=rows,
        regulates_everywhere=all(r['regulates'] for r in rows.values()),
        limits={'buck_D_min_from_tON_min': round(d_on_min, 3), 'boost_D_max_from_tOFF_min': round(d_boost_max, 3),
                'ILIM_AVG_A': list(ds['ilim_avg']), 'L1_Isat_A': 10.0, 'L_min_from_inner_loop_uH': round(
                    ds['l_min_x_fsw'] / op['fsw_Hz'][0] * 1e6, 2), 'L1_uH': op['L'] * 1e6},
        setpoint_V=[round(v, 3) for v in op['setpoint_V']], fsw_kHz=[round(f / 1e3) for f in op['fsw_Hz']],
        R109_cc_limit_A=[round(x, 3) for x in op['icc_A']],
        losses=loss,
        loss_model='conduction = IL^2 x (RDS HS1 + HS2 + max LS) x 1.5 (hot), switching 2 legs x 0.5 V I x 10 ns x fSW, '
                   'dead time 2 legs x 2 x 0.7 V x I x 20 ns x fSW, VCC LDO VIN x 10 mA; L1 DCR x 1.3 (hot); assumptions, '
                   'not TI data: bench thermal gate',
        frequency_choice=dict(fsw_kHz=round(f_nom / 1e3), TI_advice='< 500 kHz for high power, or a lower switch current '
                              'limit above it (SLVSGT7 8.1)',
                              switching_loss_W={'966kHz': round(2 * 0.5 * vin_lo * (op['i_pub'] / 0.95) * 10e-9 * f_nom, 3),
                                                '400kHz': round(sw_400, 3)},
                              why='kept from the prior S9.0 step: the R109 limit (<= 3.53 A) keeps the inductor and switch '
                                  'currents at ~half the 7 A average limit, the switching penalty is ~0.3 W, the N=16 '
                                  'release screen halves against 400 kHz, and the fundamental stays clear of the '
                                  '790 kHz -12V converter at nominal (beat tones with the wide RT tolerance are a bench '
                                  'item, as in S8)'),
        compensation=comp,
        resolution='TPS552892-Q1 four-switch buck-boost (pin-compatible role, new footprint, +10 parts): regulates 12.08 V '
                   'from 10.55 V (U5 sag) to 21 V (20 V retarget) at the published 2.4 A and at the R109 limit')


def pd_contract(val):
    """S9.0 USB PD contract: 15 V fixed PDO (CH224A CFG1 R1 56k), 3.0 A ceiling, stated input range, required adapter
    class and the resulting maximum module output."""
    on, off = u5_window(val)
    w_min = delivered_at_input_limit(VPD_RATED_MIN)
    w_nom = delivered_at_input_limit(PD_CONTRACT['V'] - CABLE_DROP_V)
    return dict(
        request=f'15 V fixed PDO, CH224A CFG1 = R1 {val("R1") / 1e3:g}k (120k = 20 V for the retarget); no current-contract '
                'tracking, PG is not a current guarantee',
        source_tolerance_V=[VPD_UNLOADED_MIN, 15.75], contract_A=PD_CONTRACT['A'],
        contract_note='45 W at 15 V is 3.0 A, the fixed-PDO ceiling: no standard source offers more than 3 A at 15 V',
        stated_input_range_V=list(VPD_RANGE),
        range_basis=f'{VPD_RANGE[0]} V = 15 V -5 % less the {CABLE_DROP_V} V cable/connector allowance at 3 A; '
                    f'{VPD_RANGE[1]} V = +10 % ceiling (converters and guards rated far above it; U5 OVP 24.1 V nominal)',
        U5_window_V={'on': [round(v, 2) for v in on], 'off': [round(v, 2) for v in off]},
        required_adapter='USB PD source with a 15 V / 3 A fixed PDO, i.e. a >= 45 W PDP adapter (a 27 W source offers '
                         'only 15 V / 1.8 A and will trip or cycle under load); a non-PD or 5 V-only source never turns U5 '
                         'on',
        max_module_output_W={'nominal_15V_source_worst_mix': w_nom['worst_mix_delivered_W'],
                             'nominal_15V_source_best_mix': w_nom['best_mix_delivered_W'],
                             'rated_min_13V5_worst_mix': w_min['worst_mix_delivered_W']},
        published_total_W=math.floor(w_min['worst_mix_delivered_W']),
        U5_limit_vs_contract='U5 3.69-4.70 A is above the 3 A contract: it protects the board, it does not enforce the '
                             'contract; overload beyond the published total is handled by the source',
        input_power_at_contract_W={'13.5V': round(VPD_RATED_MIN * 3.0, 2), '14.25V': round(14.25 * 3.0, 2)})


def residuals(val, eff, ov):
    """S9.0 owner decisions (2026-11-02): NO reverse-current blocking and NO voltage-triggered rail fuse/crowbar. Both
    are ACCEPTED residuals, each framed as a bench-test event with exact conditions and pass criteria; downstream modules
    must be qualified against them. Screens only: paths, worst-case current/energy, stressed parts."""
    op = p12(val)
    lo, hi = R1
    c_p12 = eff['+12V']
    c_vg = [a + b for a, b in zip(cs.mlcc(BANK_COUNTS['VIN'], 10, '10u50V_1206', 20.0)[:2],
                                  cs.mlcc(2, 10, '10u50V_1206', 20.0)[:2])]          # VIN to GND incl. the damper branch
    c_vn = cs.mlcc(2, 10, '10u50V_1206', 20.0)[:2]                                  # C25/C26: VIN to -12V
    dv_neg = [-12.6 * c_vn[0] / (c_vn[0] + c_vg[1]), -12.6 * c_vn[1] / (c_vn[1] + c_vg[0])]
    sp4 = [0.985 * (1 + val('R14') * lo / (val('R15') * hi)), 1.0 * (1 + val('R14') / val('R15')),
           1.015 * (1 + val('R14') * hi / (val('R15') * lo))]
    en4 = (12.0 - 0.2 + 12.0) * val('R18') / (val('R17') + val('R18'))
    p_pump = 12.6 * 0.9
    c_vin = [c_vg[0] + c_vn[0], c_vg[1] + c_vn[1]]
    t_42 = [0.5 * c * 42.0 ** 2 / p_pump * 1e3 for c in c_vin]
    dc_load_mA = {'R8+R9 (FB)': 12.6 / (val('R8') + val('R9')) * 1e3, 'R93+R94 (guard)': 12.6 / (val('R93') + val('R94')) * 1e3,
                  'R75+R76 (monitor)': 12.6 / (val('R75') + val('R76')) * 1e3, 'Q1 base R16': (12.6 - 0.7) / val('R16') * 1e3,
                  'U2 VOUT leakage (disabled)': ds_leak_mA()}
    e_p12 = [0.5 * c * 12.6 ** 2 * 1e3 for c in c_p12[:2]]
    backfeed = dict(
        decision='ACCEPTED (owner, 2026-11-02): no series reverse-blocking element on +12V or -12V',
        rule='Never connect an unpowered or latched-off module to a live bus; power the rack down before plugging or '
             'unplugging; never parallel J2/J3 with another supply on the same bus',
        plus12_path=dict(
            power_stage='blocked: with U2 disabled (EN = MAIN_OK low) the boost high-side FET body diode (anode SW2, cathode '
                        'VOUT) is reverse biased by the bus, so the four-switch stage has no conduction path from +12V to '
                        'VIN (the S8 TPS62933F buck did: output inductor + high-side body diode)',
            dc_load_from_bus_mA={k: round(v, 3) for k, v in dc_load_mA.items()},
            dc_total_mA=round(sum(dc_load_mA.values()), 3),
            hot_plug_bank_charge_mJ=[round(x, 2) for x in e_p12],
            hot_plug_note='the 8 x 22u +12V bank (+ C81) charges from the bus; the peak current is set by the bus/cable '
                          'impedance (tens of A for microseconds, as for any capacitive module), R109 sees part of it'),
        minus12_passive=dict(
            path='C25/C26 (VIN to -12V) form a divider with the VIN-to-GND caps: a -12.6 V step pulls VIN negative',
            VIN_step_V=[round(x, 2) for x in dv_neg],
            clamp='TPS552892 internal body diodes PGND -> SW1 -> VIN (~ -1.4 V) and the TPS16630 output structure: VIN '
                  'briefly below the TPS552892 -0.3 V absolute minimum',
            stresses=['U2 VIN/SW1 (-0.3 V abs min)', 'U5 OUT', 'C25/C26/C24 and the VIN bank (charge pulse)']),
        minus12_active=dict(
            path='with the +12 V bus also live, Q1 (emitter on +12V) enables U4 from the bus: EN_N = (V+12 - V-12) x R18 / '
                 '(R17 + R18); U4 itself runs from the -12 V bus (VIN pin at the 0 V VIN node, IC ground at -12 V)',
            EN_N_V=round(en4, 2), EN_high_max_V=1.4, U4_supply_V=12.0, U4_start_max_V=4.2,
            setpoint_band_V=[round(v, 3) for v in sp4],
            mechanism='pre-biased start-up: no sinking during the 4 ms soft start; afterwards, whenever |V(-12 V bus)| '
                      'exceeds U4\'s setpoint, FPWM regulation sinks up to |IL-NEG| = 0.9 A (typical, no limits) and passes '
                      'that power from the bus into the unloaded VIN node (U5 off, D10 blocks, U2 disabled)',
            pumped_power_upper_W=round(p_pump, 1),
            VIN_capacitance_uF=[round(c * 1e6, 1) for c in c_vin],
            time_to_42V_ms=[round(x, 1) for x in t_42],
            stresses=['U2 VIN/SW1 42 V absolute maximum (36 V operating)', 'C25/C26 see VIN + 12 V (50 V parts)',
                      'VIN bank C6/C7/C77/C78/C24/C8 and the damper C5/C62 (50 V)', 'U5 OUT (60 V)'],
            also_applies='a powered module that is latched off (RUN low) on a live bus, and a running module paralleled with '
                         'another supply that holds -12 V above U4\'s setpoint',
            finding='S9.0 analysis: this is an ACTIVE energy path, not a leakage: the procedural rule is mandatory. A '
                    'candidate hardware mitigation that is not reverse blocking (gate the Q1 / U4 enable with RUN or '
                    'MAIN_OK so a bus-fed +12V cannot enable U4) is listed as an open owner decision; NOT implemented'),
        bench_test=dict(
            conditions=['T1-A: module unpowered (no USB-C), J2 hot-plugged onto a live bus: +12.0 V and -12.0 V, then '
                        '+/-12.6 V, 1 A current limit per rail, 0.44 mF per rail; hold 10 s; monitor VIN (TP4), both rail '
                        'currents and U4 SW',
                        'T1-B: as T1-A with the module powered and latched off (FAULT, RUN low)',
                        'T1-C: as T1-A with only the -12 V rail live',
                        'abort and power down if VIN exceeds 30 V'],
            pass_criteria=['no damage (module restarts normally after power-up + RESET)',
                           'VIN stays within -0.3 V .. 36 V; bus current back into the module < 10 mA after the plug '
                           'transient (DC dividers ~0.6 mA)',
                           'record the plug-in charge pulse on both rails'],
            expected_by_analysis='T1-C and T1-A at a bus magnitude below U4\'s setpoint: pass apart from the brief VIN dip '
                                 'below -0.3 V. T1-A/T1-B with |V(-12 V bus)| above U4\'s setpoint: VIN can exceed 36-42 V '
                                 'within milliseconds - expected to FAIL; hence the procedural rule',
            status='proposed bench acceptance, not performed'))
    g12, gn = ov['+12V']['guard_V'], ov['-12V']['guard_V']
    e_vin = [0.5 * c * (VPD_RANGE[1] ** 2 - 4.0 ** 2) for c in c_vg]
    c_n12 = eff['-12V']
    p12_peak_bank = min(math.sqrt(g12[2] ** 2 + 2 * e_vin[1] / c_p12[0]), TPS552892_DS['ovp'][2])
    p12_peak_rack = math.sqrt(g12[2] ** 2 + 2 * e_vin[1] / (c_p12[1] + TYPICAL_RACK_MF * 1e-3))
    n12_peak_bank = math.sqrt(gn[2] ** 2 + 2 * e_vin[1] / c_n12[0])
    n12_peak_rack = math.sqrt(gn[2] ** 2 + 2 * e_vin[1] / (c_n12[1] + TYPICAL_RACK_MF * 1e-3))
    overvoltage = dict(
        decision='ACCEPTED (owner, 2026-11-02): no voltage-triggered fuse or crowbar on +/-12V (the crowbar stays excluded; '
                 'crowbar vs eFuse is a deferred, open decision); the U20 guard + FAULT latch is the only response',
        guard_V={'+12V': g12, '-12V_magnitude': gn},
        response_us='~3 (comparator, HC74 preset) + 8-9 (RC filter) + 0.8-1.5 (U5 tSD) after the crossing; it opens U5, '
                    'it does NOT discharge the rails',
        why_no_fuse=['a fuse/PTC opens on current, not voltage: in series with +12V it must carry 2.4 A continuously and '
                     'the 3.53 A R109 limit without nuisance, so a rail at 15-24 V with a normal load never blows it',
                     'making overvoltage create overcurrent needs a crowbar (SCR/TVS) across the rail plus a fuse sized '
                     'below the source limit: that is the excluded crowbar architecture',
                     'a TVS alone (e.g. 13 V stand-off: 14.4-15.9 V breakdown) sits inside the 14.48-15.27 V guard band and '
                     'would have to absorb the converter limit (3.5 A x ~15 V = ~53 W) continuously: it fails, usually '
                     'short, which is a crowbar by failure',
                     'a series eFuse with OVP per rail is the removed S7 rail-eFuse architecture (U6/U7/LM5067), not a fuse'],
        cases={'P12_pass_through': 'failed U2 switches pass VIN to +12V: the rail follows VIN, <= 16.5 V in the stated '
                                   'range (up to the U5 OVP ~24-26 V if the source itself fails high); the guard opens U5 '
                                   'but the rail keeps its charge (load-dependent decay)',
               'P12_control_failure': 'FB open (R8 open): the buck-boost drives the R109 limit into the rail; after the '
                                      'guard opens U5 it keeps converting the VIN bank energy until VIN collapses',
               'N12_control_failure': 'FB open (R14 open): the LMR38020 (no output OVP) drives the rail beyond the -12V '
                                      'guard and dumps the VIN bank energy into it after U5 opens',
               'sub_threshold': 'a failure that settles just inside the guard band never trips: +12V up to 15.27 V and '
                                '-12V down to -14.02 V indefinitely'},
        VIN_bank_energy_mJ=[round(e * 1e3, 2) for e in e_vin],
        peak_screens_V={'+12V_bank_only_no_load': round(p12_peak_bank, 1), '+12V_with_typical_rack': round(p12_peak_rack, 1),
                        '-12V_bank_only_no_load': round(n12_peak_bank, 1), '-12V_with_typical_rack': round(n12_peak_rack, 1)},
        peak_model='guard maximum plus the VIN bank energy (16.5 V -> 4 V, high-C corner) dumped into the rail bank (low C) '
                   'or bank + 0.44 mF rack, no load; +12V capped by the TPS552892 absolute OVP 24.5 V. Energy screen, not a '
                   'transient simulation',
        bench_test=dict(
            conditions=['T2-A pass-through: module running at 16.5 V input into 0.44 mF + 0.5 A per rail; +12V driven to '
                        '16.5 V from a current-limited (3.5 A) supply through a diode; hold 10 s',
                        'T2-B +12V control failure: R8 lifted (FB open), start at 13.5 V and 16.5 V input, once with no '
                        'rack and no load, once with 0.44 mF + 0.5 A',
                        'T2-C -12V control failure: R14 lifted (FB open), same two loads',
                        'T2-D sub-threshold: +12V held at 15.2 V and -12V at -13.9 V from external supplies for 10 min'],
            pass_criteria_this_module=['OV_N low and FAULT latched within 20 us of the guard crossing (T2-A..C); MAIN LED '
                                       'off; rails stay off until RESET; no damage to the module',
                                       'T2-D: no trip (inside the guard band), no damage',
                                       'record the peak and decay of both rails; compare with peak_screens_V'],
            downstream_qualification=['every module intended for this rack must survive, unpowered and powered: +12V at '
                                      '16.5 V and -12V at -16.5 V for 10 s; +12V at 15.3 V and -12V at -14.1 V '
                                      'continuously; the measured T2-B/T2-C peaks (screens up to ~24.5 V / ~26 V with no '
                                      'rack, ~16 V with a typical rack) for 100 ms',
                                      'qualify the modules against these conditions; do not rely on this supply to '
                                      'prevent them'],
            status='proposed bench acceptance, not performed'))
    return dict(reverse_current=backfeed, rail_overvoltage=overvoltage)


def ds_leak_mA():
    return TPS552892_DS['ivout_lkg'] * 1e3


def retarget_20v(val):
    """What changes when the input moves back to 20 V (not done in S9.0): three resistors and the rated minimum; every
    part behind U5 is already rated for it (U5 OVP keeps the 20 V setting)."""
    swap = {'R1': 120e3, 'R3': 7.5e3, 'R83': 120e3}

    def val20(ref):
        return swap.get(ref, val(ref))
    on, off = u5_window(val20)
    v20 = v20_band(val20)
    vpd_min20 = 18.25
    vin20 = converter_vin(vpd_min20)
    n12 = n12_capability(vin20)
    p12c = p12_capability(val, vin20)
    op = p12(val)
    r20 = {'+12V': min(2.5, round(0.75 * p12c, 1)), '-12V': min(1.0, round(0.75 * n12, 1))}
    return dict(
        changes={'R1': '56k -> 120k (CH224A 20 V request)', 'R3': '10k -> 7.5k (U5 UVLO)',
                 'R83': '100k -> 120k (V20_OK status floor)',
                 'docs': 'rated minimum VPD 18.25 V (20 V -5 % less 0.75 V), input budget at 20 V'},
        U5_window_V={'on': [round(v, 2) for v in on], 'off': [round(v, 2) for v in off]},
        V20_OK_band_V=[round(v, 3) for v in v20], V20_OK_rule_holds=v20_floor_ok(v20, off),
        converter_VIN_V=[vin20, 21.0],
        plus12={'mode': 'buck only', 'D': [round(op['setpoint_V'][0] / 21.0, 3), round(op['setpoint_V'][2] / vin20, 3)],
                'D_min_tON': round(TPS552892_DS['ton_min'] * op['fsw_Hz'][2], 3),
                'capability_A': round(p12c, 3), 'rating_A': min(2.5, round(0.75 * p12c, 1))},
        minus12={'capability_A': round(n12, 3), 'rating_A': min(1.0, round(0.75 * n12, 1)), 'D_at_20V': round(11.989 / 31.989, 3)},
        input={'45W_adapter_20V_A': 2.25, 'ratings_A': r20,
               'delivered_W_45W_20V_worst_mix': delivered_at_input_limit(vpd_min20, 2.25, ratings=r20)['worst_mix_delivered_W'],
               'delivered_W_60W_20V_3A_worst_mix': delivered_at_input_limit(vpd_min20, 3.0, ratings=r20)['worst_mix_delivered_W'],
               'per_rail_sum_W': round(12.08 * r20['+12V'] + 11.989 * r20['-12V'], 2)},
        unchanged=['TPS552892-Q1 cell, R109 limit and compensation (buck mode only)', 'LMR38020 (VIN + 12 V = 33 V, 80 V part)',
                   'U5 OVP 24.1 V nominal, D1 SMBJ22A, 50 V VIN/C25/C26 parts', 'guard thresholds and the arming chain'],
        note='not a corner: S9.0 already carries every part rated for 20 V; the retarget is a three-resistor change plus '
             'the doc/rating update. D10/U5 dissipation fall (2.25 A instead of 3 A at 45 W)')


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
             'SO14': 'SOIC-14_3.9x8.7mm_P1.27mm', 'SLO1040': 'L_SLO1040H6R8MTT', 'RYQ21': 'TI_RYQ0021B_VQFN-HR-21_3x5mm',
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
    big = {'J2+J3': 2 * cy('IDC16'), 'L1+L3': 2 * cy('SLO1040'), 'panel J1/SW1/D8': cy('USBC') + cy('TL3340') + cy('LED3EDGE'),
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
    R = {'status': 'S9.0 pre-calculation screen, not a closed-loop or bench qualification', 'sources': SOURCES}
    R['banks'], eff = banks(parts)
    R['ripple_and_steps'] = ripple_and_steps(val, eff)
    op = p12(val)
    p_conv = op['setpoint_V'][2] * PUBLISHED_A['+12V'] / ETA_ASSUMED['+12V'] + 12.624 * PUBLISHED_A['-12V'] / ETA_ASSUMED['-12V']
    if not a.skip_sim:
        R['vin_damper'] = vin_damper(val('R92'), BANK_COUNTS['VIN'], v_min=converter_vin(VPD_RATED_MIN),
                                     p_max=math.ceil(p_conv))
        R['rail_release'] = rail_release(val)
    else:
        prev = json.loads((a.out / 'calcs.json').read_text())
        R['vin_damper'], R['rail_release'] = prev['vin_damper'], prev['rail_release']
    R['soft_start'] = soft_start(val, eff)
    R['ov_guard'] = ov_guard(val, R['rail_release'])
    R['ov_reference'] = reference(val)
    R['ov_clamp'] = clamp(val)
    R['comparator_supply'] = comparator_supply(val)
    R['v3v3_loss'] = v3v3_loss(val)
    R['minus12_startup'] = minus12_startup(val, eff)
    R['plus12_buckboost'] = plus12_buckboost(val, eff)
    R['rating'] = rating(val, eff)
    R['pd_contract'] = pd_contract(val)
    R['basic_only_counterfactual'] = basic_only_counterfactual(val, eff, R['rail_release'])
    R['startup_window'] = startup_window(val)
    R['arming'] = arming(val)
    R['replug_por'] = replug_por(val)
    R['input_budget'] = input_budget()
    R['connectors'] = connectors()
    R['residuals'] = residuals(val, eff, R['ov_guard'])
    R['retarget_20v'] = retarget_20v(val)
    R['area'] = area(parts)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'calcs.json').write_text(json.dumps(R, indent=2) + '\n')
    print(json.dumps({k: R[k] for k in R if k not in ('sources', 'ripple_and_steps', 'banks')}, indent=1)[:6000])


if __name__ == '__main__':
    main()
