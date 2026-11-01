"""S8.3 single-board circuit: common input protection plus a fast +5 V series eFuse.

User-authorized replacement of the S8.2 crowbar (2026-11-01): U23 TPS259470ARPWR,
C3662799, independent adjustable OVLO, current limit and true reverse blocking.
The A variant is deliberately selected for stock/cost; the common retained latch
owns system restart. AUXOFF + FLT join delivered-voltage P5_OK (startup qualified).
U20 still provides unmasked severe-OV shutdown, now sensing P5_RAW before U23.

Q11/Q12/Q13/U22 and SCR-only resistors are gone. R101/R102 are reused as the
precision eFuse divider, R103/R104 as ILM programming, C68 as dVdt. D21 moves
upstream: a transient energy clamp protecting U23, NOT a 5 V rack clamp.
C20-C23 and six new 22u capacitors remain upstream with buck feedback; C35/C60
and C73/C74 are downstream. The extra upstream bank creates normal-release
headroom without changing the original nominal regulator voltage/current target.

U18/U20 keep LM2901B, but their supplies and 50 V bypasses now use always-on VPD
instead of V3V3 (before U5, after F1, clamped by D1). Outputs still pull up only to V3V3. At qualified 20 V operation
this fixes both U20 full-temperature common-mode headroom and its >=5 V offset
specification condition. D22 and the separate REF_OV reference are retained.
No ±12 V rail switches/LEDs are restored. Original S7 circuit45 is untouched.
"""
import copy

import circuit45
from circuit45 import UNIROYAL, cap, part, res, two

PROJECT = 'usb-power-45w-single'

# Every S7 ref the single board drops, with the reason (checked by tools/verify_s8.py).
S8_REMOVED = {
    **{r: '+12V rail eFuse U6 and its setting network' for r in
       ('U6', 'R30', 'R31', 'R32', 'R33', 'R34', 'R36', 'R37', 'R38', 'C37', 'C38', 'C39', 'D12')},
    **{r: '+5V rail eFuse U7 and its setting network' for r in
       ('U7', 'R39', 'R40', 'R41', 'R42', 'R43', 'R45', 'R46', 'C40', 'C41', 'C42', 'D13')},
    **{r: '-12V LM5067/Q4 series switch, shunt, VCC feed, timer, pin clamps and output parts' for r in
       ('U8', 'Q4', 'R48', 'R49', 'R50', 'R51', 'C43', 'R52', 'R53', 'R54', 'R55', 'R56', 'C44', 'R57',
        'C45', 'R58', 'R89', 'R90', 'D19', 'D20', 'D14', '#FLG08', '#FLG09')},
    **{r: 'LM5067 optical OFF command / PGD level shift' for r in ('U16', 'Q5', 'R59', 'R60', 'U17', 'R61')},
    'U19': 'Schmitt buffer for the slow opto pull-up; N12_OK is now the comparator output itself',
    'C58': 'U19 decoupling',
    # S8 final (user, 2026-11-01): "Remove each rail LEDs too." D8 MAIN (+ R22, Q6, Q10) stays.
    **{r: '+12V panel LED, its 1k and 2N7002 driver (rail LEDs removed; D8 MAIN is the only LED)'
       for r in ('D16', 'R86', 'Q7')},
    **{r: '+5V panel LED, its 1k and 2N7002 driver (rail LEDs removed; D8 MAIN is the only LED)'
       for r in ('D17', 'R87', 'Q8')},
    **{r: '-12V panel LED, its 1k and 2N7002 driver (rail LEDs removed; D8 MAIN is the only LED)'
       for r in ('D18', 'R88', 'Q9')},
    **{r: 'local SMD rail presence LED and its resistor (rail LEDs removed)'
       for r in ('D5', 'R19', 'D6', 'R20', 'D7', 'R21')},
}
LED_REMOVED = ('D16', 'R86', 'Q7', 'D17', 'R87', 'Q8', 'D18', 'R88', 'Q9', 'D5', 'R19', 'D6', 'R20', 'D7', 'R21')
NET_RENAME = {'P12_RAW': '+12V', 'N12_RAW': '-12V', 'N12_STATUS': 'N12_OK'}

# Flat-sheet anchors of the S8 additions (page offsets: page 01 (0, 0); page 06 header group
# (0, -86.36); page 06 monitor group (-599.44, -508)).
J3_AT = (101.6, 335.28)          # S6 position of the second header (page 06: 101.6, 248.92)
CAP_Y = 365.76                   # header-side ceramics row under J2 / J3 (page 06: y 279.4)
MON = (599.44, 508.0)            # page 06 monitor group offset

# S8.1 overvoltage guard parts, live-checked 2026-11-01 (tools/s8_sourcing.py; all Extended except R100/C67).
LM2901B = dict(LCSC='C22427890', MPN='LM2901BIDR', Manufacturer='Texas Instruments')
R0603_01 = {  # 0.1 %, 25 ppm/C thin film: (LCSC, MPN, manufacturer)
    '10k': ('C95204', 'RT0603BRD0710KL', 'YAGEO'),
    '110k': ('C326736', 'RT0603BRD07110KL', 'YAGEO'),
    '37k': ('C1694418', 'TNPW060337K0BEEA', 'Vishay'),
}
# Symbol of U21: KiCad stock Reference_Voltage:TL431DBZ drawing, pins renumbered to the TI TLV431 DBZ
# package (SLVS139Z Table 4-1: REF 1, CATHODE 2, ANODE 3; the TL431 DBZ order differs). See build_s8.py.
TLV431_DBZ_PINS = {'REF': '1', 'K': '2', 'A': '3'}
TEXT_POS_S8 = {'U21': ((-6.35, -1.27), (-6.35, 1.27), 'left')}
TPS259470A = dict(LCSC='C3662799', MPN='TPS259470ARPWR', Manufacturer='Texas Instruments')
CROWBAR_REMOVED = ('Q11', 'U22', 'Q12', 'Q13', 'R105', 'R106')
DISCONNECT = ('U23', 'R101', 'R102', 'R103', 'R104', 'R107', 'C68',
              'C69', 'C70', 'C71', 'C72', 'C73', 'C74', 'C75', 'C76', 'D23', 'TP18')
HDR = (0.0, 86.36)
MIRROR_S8 = set()


def basic_res(ref, value, at, a, b, rot=0, **kw):
    # New S8.3 values, exact-code live Basic+Economy evidence in docs/s8-single/s83-sourcing.json.
    code, mpn = {'100': ('C22775', '0603WAF1000T5E'),
                 '510': ('C23193', '0603WAF5100T5E')}[value]
    return two(ref, 'R', value, 'R0603', at, a, b, rot, LCSC=code, MPN=mpn,
               Manufacturer=UNIROYAL, Tolerance='1%', **kw)


def hp(x, y):
    """Page-06 header-group coordinates -> flat sheet."""
    return (round(x + HDR[0], 2), round(y + HDR[1], 2))


def res01(ref, value, at, a, b, rot=0, **kw):
    code, mpn, maker = R0603_01[value]
    return two(ref, 'R', value, 'R0603', at, a, b, rot, LCSC=code, MPN=mpn, Manufacturer=maker, Tolerance='0.1%',
               TCR='25ppm', **kw)


def m(x, y):
    """Page-06 monitor coordinates -> flat sheet."""
    return (round(x + MON[0], 2), round(y + MON[1], 2))


def circuit():
    c = [p for p in circuit45.circuit() if p['ref'] not in S8_REMOVED]
    by = {p['ref']: p for p in c}
    for p in c:
        p['pins'] = {n: NET_RENAME.get(v, v) for n, v in p['pins'].items()}

    # ---- Converters: soft start 22n -> 100n (TPS62933F tSS = CSS x 0.8 V / 5.5 uA)
    for ref, u in (('C9', 'U2'), ('C18', 'U3')):
        by[ref].update(value='100n')
        by[ref]['fields'] = {**circuit45.CAPS[('100n', 'C0603')],
                             'Note': f'{u} soft start ~14.5 ms (100n x 0.8 V / 5.5 uA; 11-20 ms over CSS/ISS '
                                     f'corners): charges rack capacitance on the unswitched rail. S7 had 22n'}
    by['U5']['fields']['Note'] = by['U5']['fields']['Note'].replace(
        '; S6 FLT + PGOOD wired-AND at 3.3 V; common RUN disconnect.',
        '. FLT + PGOOD wired-AND (MAIN_OK) at 3.3 V. S8.3: common input switch; RUN also disables U23 on +5V')
    by['U2']['fields']['Note'] += '. S8: output is the delivered +12V (no rail eFuse); hiccup/OVP/TSD are its own'
    by['U3']['fields']['Note'] += '. S8.3: P5_RAW stays upstream of U23, including local output capacitors and feedback'
    by['U18']['pins']['3'] = 'VPD'
    by['C57']['pins']['1'] = 'VPD'
    by['C57']['fields']['Note'] = 'U18 always-on VPD bypass, 50 V rated; logic outputs still pull up to V3V3'
    by['U4']['fields']['Note'] = by['U4']['fields']['Note'].replace(
        'Pins 1 and pad are the -12V node, not GND.', 'Pins 1 and pad are the delivered -12V node (S8: no '
        'series switch), not GND; 18 ms OCP blanking at start-up charges the rack capacitance.')
    for ref, rail in (('D2', '+12V'), ('D3', 'P5_RAW'), ('D4', '-12V')):
        by[ref]['fields']['Note'] = f'{rail} polarity clamp at the converter output (P5_RAW is before U23)'
    # ---- Status LED: D8 MAIN is the only LED left (S8 final)
    by['D8']['fields']['Note'] = ('Hand-soldered 3 mm horizontal panel LED (manual part, user stock 3 mm red), the only '
                                  'status LED: MAIN = input valid AND U5 FLT/PGOOD AND RUN. Any latched fault (bad rail '
                                  'after the startup window, or overvoltage) turns it off')
    by['Q6']['fields']['Note'] = 'MAIN LED switch: gate = MAIN_LED_OK (U13), source to the RUN-gated return Q10'
    by['Q10']['fields']['Note'] = 'MAIN LED enable: D8 off whenever RESET/FAULT has turned the rails off (RUN low)'

    # ---- Status: comparator outputs only; pull-ups moved next to U18 (page 06)
    for ref, net, at in (('R35', 'P12_OK', m(248.92, 72.39)), ('R44', 'P5_OK', m(259.08, 72.39)),
                         ('R62', 'N12_OK', m(269.24, 72.39))):
        p = by[ref]
        p['at'] = at
        p['pins'] = {'1': 'V3V3', '2': net}
        if p['value'] != '10k':
            p.update(value='10k')
            p['fields'].update(LCSC=circuit45.R0603['10k'], MPN=circuit45.R_MPN['10k'])
        p['fields']['Note'] = f'{net} pull-up: delivered-voltage monitor; P5_OK additionally includes U23 AUXOFF and FLT (S8.3)'
    by['U18']['value'] = LM2901B['MPN']
    by['U18']['fields'] = {**LM2901B, 'Note': 'Output-valid comparators on the delivered rails. +12/+5/input use '
                                              'signal on + input; -12V uses the offset negative sense on - input. Clamp '
                                              'negative sense. S8.1: LM2901B (drop-in for LM2901, same part as U20)'}

    # ---- Fault latch: OV guard on the spare preset; unused NAND inputs to GND
    by['U12']['pins']['10'] = 'OV_N'
    by['U12']['fields']['Note'] += (' S8: 2PRE_N = OV_N, so the overvoltage guard sets FAULT at once, '
                                    'also during the startup window.')
    by['U14']['pins'].update({'8': None, '9': 'GND', '10': 'GND', '12': 'GND', '13': 'GND'})
    by['U14']['fields']['Note'] = ('Four-input NAND combines the four good signals (ANY_BAD). Second NAND unused '
                                   '(S8 has no negative-switch opto): inputs tied to GND, output open.')
    by['C49'].update(value='100n')
    by['C49']['fields'] = {**circuit45.CAPS[('100n', 'C0603')],
                           'Note': 'Startup qualification ~0.57 s typical (TPS3808: CT nF / 175 + 0.5 ms). '
                                   'S7 had 1u (5.7 s) for the removed LM5067 insertion delay'}
    by['U11']['fields']['Note'] = ('Timer begins only at RUN and >=20-V-class input. 100n gives ~0.57 s '
                                   'qualification, not reset by individual bad rails.')
    tp6 = by['TP6']
    tp6.update(value='OV_N', at=(309.88, 721.36))   # end of the page-05 test-pad row (was FAULT_LATCH twice)
    tp6['pins'] = {'1': 'OV_N'}

    # ---- Outputs: J2 + J3 in parallel (Doepfer pinout), header-side ceramics
    j2 = by['J2']
    j2['fields']['Note'] = ('Hand-soldered shrouded 16-pin box header, pin 1 = -12V (red stripe). One of two '
                            'parallel outputs (J2/J3, S8). Each cable carries 2 contacts per rail: above ~2 A '
                            'per rail use both headers. CV/GATE (13-16) open')
    j3 = copy.deepcopy(j2)
    j3.update(ref='J3', at=J3_AT)
    c.append(j3)
    for (ref, x, rail), hdr in zip((('C34', 30.48, '+12V'), ('C35', 40.64, '+5V'), ('C36', 50.8, '-12V'),
                                    ('C59', 86.36, '+12V'), ('C60', 96.52, '+5V'), ('C61', 106.68, '-12V')),
                                   ('J2',) * 3 + ('J3',) * 3):
        a, b = ('GND', '-12V') if rail == '-12V' else (rail, 'GND')
        new = cap(ref, '22u', 'C1206', (x, CAP_Y), a, b,
                  Note=f'{rail} ceramic at the {hdr} {rail} pins: with its twin at the other header it replaces '
                       f'the S7 100u can (rail bank 4/4/5 x 22u at the converter + 2). See docs/s8-single-board.md')
        if ref in by:
            c[c.index(by[ref])] = new
        else:
            c.append(new)
    c.append(two('D21', 'D_Zener', 'SMAJ5.0A', 'SMA', hp(259.08, 248.92), 'P5_RAW', 'GND', rot=270,
                 LCSC='C113952', MPN='SMAJ5.0A', Manufacturer='MDD(Microdiode Semiconductor)',
                 Note='S8.3 moved BEFORE U23 to P5_RAW: 5 V stand-off, 6.4-7.0 V breakdown, 9.2 V at 43.5 A. '
                      'Absorbs failed-buck stored energy until U20 latches U5 off; keep beside U23 IN/GND. '
                      'Not a rack voltage limit or a sustained-fault clamp. Qualify pulse energy/ringing/temperature.'))

    # ---- VIN: series-R damper replaces the 47u can (capacitor study B_RCx2)
    c[c.index(by['C5'])] = cap('C5', '10u', 'C1206', (243.84, 60.96), '_VIN_DAMP', 'GND',
                               Note='VIN damper capacitor 1 of 2, in series with R92 (replaces the S7 47u can)')
    c.append(cap('C62', '10u', 'C1206', (254.0, 60.96), '_VIN_DAMP', 'GND',
                 Note='VIN damper capacitor 2 of 2, in series with R92'))
    c.append(two('R92', 'R', '1', 'R1206', (243.84, 49.53), 'VIN', '_VIN_DAMP',
                 LCSC='C17928', MPN='1206W4F100KT5E', Manufacturer=UNIROYAL, Tolerance='1%',
                 Note='VIN damper: 1 ohm in series with C5 + C62 (2 x 10u/50V). Damps cable inductance against '
                      'the all-ceramic VIN bank (Middlebrook margin, docs/s8-single-board.md)'))

    # ---- Overvoltage guard: three open-collector comparators wired-AND onto OV_N. S8.1: own precision reference
    # REF_OV, LM2901B, 0.1 % dividers; the -12V channel compares a REF_OV-offset divider with GND (no V3V3 term).
    c.append(part('U20', 'LM2901_QUAD', LM2901B['MPN'], 'SO14', m(205.74, 83.82), 0,
                  {'4': 'MON_OV12', '5': 'REF_OV', '2': 'OV_N',        # +12V: low when MON_OV12 > REF_OV
                   '6': 'MON_OV5', '7': 'REF_OV', '1': 'OV_N',         # +5V: low when MON_OV5 > REF_OV
                   '8': 'GND', '9': 'MON_OVN', '14': 'OV_N',           # -12V: low when MON_OVN < 0 V (|V| high)
                   '10': 'REF_OV', '11': 'GND', '13': None,            # spare: output held low, unconnected
                   '3': 'VPD', '12': 'GND'},
                  **LM2901B,
                  Note='S8.3: always-on VPD supply (not V3V3), V3V3 pull-up on OV_N. Full-temperature input '
                       'ceiling VPD-2 V; qualified input is >=15 V, REF_OV <=1.259 V. U20 senses +12V, P5_RAW and -12V; '
                       'severe OV presets FAULT even before ARMED. Opening U5 alone cannot isolate stored energy; U23 '
                       'disconnects +5V independently. Clamp D22 retained. Cold shutdown/replug remains a bench gate.'))
    c.append(part('U21', 'TLV431_DBZ', 'TLV431BIDBZR', 'SOT23', m(210.82, 134.62), 90,
                  {TLV431_DBZ_PINS['REF']: 'REF_OV', TLV431_DBZ_PINS['K']: 'REF_OV', TLV431_DBZ_PINS['A']: 'GND'},
                  LCSC='C398375', MPN='TLV431BIDBZR', Manufacturer='Texas Instruments',
                  Note='Guard reference REF_OV (REF tied to CATHODE): 1.224-1.259 V at -40..85 C, 0.4 ohm max (SLVS139Z). '
                       'DBZ pins REF 1, CATHODE 2, ANODE 3. ~0.9 mA from R100; C67 keeps it stable (Fig. 5-18/5-19)'))
    c.append(res('R100', '2.2k', m(210.82, 119.38), 'V3V3', 'REF_OV',
                 Note='U21 bias: (3.3 - 1.24 V) / 2.2k = 0.94 mA; >= 0.7 mA stays in U21 with the -12V divider at '
                      '-20 V (TLV431 needs 0.1 mA)'))
    c.append(two('C67', 'C', '10u', 'C0603', m(220.98, 134.62), 'REF_OV', 'GND',
                 LCSC='C19702', MPN='CL10A106KP8NNNC', Manufacturer='Samsung', Voltage='10V',
                 Note='REF_OV hold capacitor at U21: >= ~1 uF is right of the TLV431 instability region at ~1 mA '
                      '(SLVS139Z Fig. 5-18). With R100 REF_OV settles in 9-12 ms, before any rail can rise (POR >= 12 ms, '
                      'then the U5 ramp and the soft starts)'))
    c.append(part('TP17', 'TestPoint', 'REF_OV', 'TP', m(231.14, 127.0), 0, {'1': 'REF_OV'},
                  Note='Copper-only diagnostic; no assembly component. Bench: REF_OV 1.22-1.26 V'))
    c.append(res01('R93', '110k', m(281.94, 66.04), '+12V', 'MON_OV12',
                   Note='+12V OV divider top: 1.24 V x (1 + 110k/10k) = 14.88 V nominal (14.48-15.27 V over corners)'))
    c.append(res01('R94', '10k', m(281.94, 83.82), 'MON_OV12', 'GND', Note='+12V OV divider bottom'))
    c.append(cap('C63', '1n', 'C0603', m(292.1, 83.82), 'MON_OV12', 'GND',
                 Note='~9 us filter: ignores switching spikes, not a real overvoltage'))
    c.append(res01('R95', '37k', m(304.8, 66.04), 'P5_RAW', 'MON_OV5',
                   Note='+5V OV divider top: 1.24 V x (1 + 37k/10k) = 5.83 V nominal (5.68-5.98 V over corners)'))
    c.append(res01('R96', '10k', m(304.8, 83.82), 'MON_OV5', 'GND', Note='+5V OV divider bottom'))
    c.append(cap('C64', '1n', 'C0603', m(314.96, 83.82), 'MON_OV5', 'GND', Note='~8 us filter'))
    c.append(res01('R98', '10k', m(304.8, 109.22), 'REF_OV', 'MON_OVN',
                   Note='-12V OV offset divider top from REF_OV: MON_OVN = (1.24 x 110k + V x 10k) / 120k, 0.14 V at '
                        '-12 V, 0 V at -13.64 V'))
    c.append(res01('R99', '110k', m(304.8, 127.0), 'MON_OVN', '-12V',
                   Note='-12V OV divider: trips at -13.64 V nominal (13.27-14.02 V; LMR38020 has no output OVP, '
                        'an open R14 runs away)'))
    c.append(cap('C66', '1n', 'C0603', m(314.96, 127.0), 'MON_OVN', 'GND', Note='~9 us filter'))
    c.append(part('D22', 'BAT54S', 'BAT54SLT1G', 'SOT23', m(289.56, 120.65), 0,
                  {'1': 'GND', '2': 'MON_OVN', '3': 'MON_OVN'}, LCSC='C19726', MPN='BAT54SLT1G', Manufacturer='onsemi',
                  Note='MON_OVN clamp (review): diode 1 GND -> MON_OVN holds U20 pin 9 near -0.24 V (0.1 mA, BAT54 '
                       'VF max) when V3V3 is gone and the rack keeps -12V; diode 2 shorted. ~0 V across it at the trip'))
    c.append(res('R97', '10k', m(231.14, 67.31), 'V3V3', 'OV_N',
                 Note='OV_N pull-up (wired-AND of the U20 guard outputs)'))
    c.append(cap('C65', '100n', 'C0603', m(241.3, 99.06), 'VPD', 'GND', Note='U20 always-on VPD decoupling, 50 V; do not reconnect to V3V3'))

    # ---- S8.3: self-powered series disconnect. Do NOT put buck FB after the switch.
    c.append(part('U23', 'TPS259470_RPW', TPS259470A['MPN'], 'RPW10', hp(205.74, 269.24), 0,
                  {'1': 'RUN', '2': 'P5_OVLO', '3': 'P5_OK', '4': 'P5_OK', '5': 'P5_RAW',
                   '6': '+5V', '7': 'P5_DVDT', '8': 'GND', '9': 'P5_ILM', '10': None}, **TPS259470A,
                  Note='TPS259470A: adjustable OVLO (~5.70 V nominal), 1.2 us TYP (no max specified), '
                       '2.7-23 V operation / 28 V abs max, true reverse blocking, 28 mOhm typ. '
                       'IN protected by D21 on P5_RAW. 1k+100 sets ~3.03 A nominal (not a guaranteed load rating). '
                       'AUXOFF + FLT + U18 wire-AND into P5_OK: common latch after startup; U20 severe OV unmasked. '
                       'FLT alone does NOT report OVLO. Auto-retry is suppressed once common FAULT is latched.'))
    c.append(res01('R101', '37k', hp(154.94, 264.16), 'P5_OV_TOP', 'P5_OVLO',
                   Note='Reused precision divider, now U23 OVLO. With R107 510R and R102 10k: 1.2*(1+37.51/10)=5.7012 V.'))
    c.append(res01('R102', '10k', hp(154.94, 281.94), 'P5_OVLO', 'GND', Note='U23 OVLO bottom; no intentional RC delay'))
    c.append(basic_res('R107', '510', hp(154.94, 246.38), 'P5_RAW', 'P5_OV_TOP', Note='Basic series trim in OVLO top'))
    c.append(res('R103', '1k', hp(236.22, 264.16), 'P5_ILM', 'P5_ILM_SER', Note='ILM series with R104 100R'))
    c.append(basic_res('R104', '100', hp(236.22, 281.94), 'P5_ILM_SER', 'GND',
                       Note='ILM total 1.1k: 3334/1100=3.031 A nominal; +/-10% IC plus resistor/tcr screen'))
    c.append(cap('C68', '10n', 'C0603', hp(220.98, 297.18), 'P5_DVDT', 'GND',
                 Note='U23 dVdt ~0.2 V/ms typical, ~25 ms 5V ramp. 50 V cap exceeds IN+5 V. No ITIMER capacitor.'))
    for ref, x in (('C69', 177.8), ('C70', 187.96), ('C71', 198.12), ('C72', 208.28), ('C75', 218.44), ('C76', 228.6)):
        c.append(cap(ref, '22u', 'C1206', hp(x, 226.06), 'P5_RAW', 'GND',
                     Note='S8.3 upstream 22u bank: C20-C23 + C69-C72/C75/C76 = 10. Retains load-release margin before U23; '
                          'DC bias and converter-loop stability require validation.'))
    for ref, x in (('C73', 274.32), ('C74', 284.48)):
        c.append(cap(ref, '22u', 'C1206', hp(x, 279.4), '+5V', 'GND',
                     Note='S8.3 local delivered-side capacitor, next to U23 OUT/GND. With C35/C60 gives 4 x 22u; '
                          'minimum effective C and layout set fault peak, not nominal capacitance alone.'))
    c.append(two('D23', 'D_Schottky', 'SS34', 'SMA', hp(297.18, 279.4), '+5V', 'GND', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD',
                 Note='U23 OUT negative-transient clamp, cathode +5V / anode GND. Keep close to OUT/GND.'))
    c.append(part('TP18', 'TestPoint', 'P5_RAW', 'TP', hp(177.8, 248.92), 0, {'1': 'P5_RAW'},
                  Note='Raw +5V before U23; header +5V is isolated. No assembly part.'))
    return c


def drawing():
    """S7 drawing() without the removed parts' wires/symbols/labels, RAW names restored to the
    delivered rails except P5_RAW, plus J3, the VIN damper, OV guard and U23 disconnect."""
    W, P, L = circuit45.drawing()
    gone = set(S8_REMOVED) | {'R35', 'R44', 'R62'}   # moved refs: S7 lines at their old spots

    def ref_of(pt):
        if isinstance(pt, str):
            return pt.split('.')[0]
        if isinstance(pt[0], str):
            return pt[0].split('.')[0]
        return None
    W = [w for w in W if not any(ref_of(pt) in gone for pt in w)]
    P = [(NET_RENAME.get(n, n), pt, rot) for n, pt, rot in P if ref_of(pt) not in gone]
    L = [(NET_RENAME.get(n, n), pt, side) for n, pt, side in L if ref_of(pt) not in gone]

    # J3: same wiring as J2 in circuit45.drawing()
    hx, hy = J3_AT
    lx, rx = hx - 5.08 - 5.08, hx + 7.62 + 5.08
    j = 'J3'
    W += [[f'{j}.1', (lx, hy - 7.62)], [f'{j}.2', (rx, hy - 7.62)],
          [f'{j}.3', (lx + 2.54, hy - 5.08), (lx + 2.54, hy), f'{j}.7'], [f'{j}.5', (lx + 2.54, hy - 2.54)],
          [(lx + 2.54, hy - 5.08), (lx, hy - 5.08)],
          [f'{j}.4', (rx - 2.54, hy - 5.08), (rx - 2.54, hy), f'{j}.8'], [f'{j}.6', (rx - 2.54, hy - 2.54)],
          [(rx - 2.54, hy - 5.08), (rx, hy - 5.08)],
          [f'{j}.9', (lx, hy + 2.54)], [f'{j}.10', (rx, hy + 2.54)],
          [f'{j}.11', (lx, hy + 5.08)], [f'{j}.12', (rx, hy + 5.08)]]
    P += [('-12V', (lx, hy - 7.62), 90), ('-12V', (rx, hy - 7.62), 270),
          ('GND', (lx, hy - 5.08), 270), ('GND', (rx, hy - 5.08), 90),
          ('+12V', (lx, hy + 2.54), 90), ('+12V', (rx, hy + 2.54), 270),
          ('+5V', (lx, hy + 5.08), 90), ('+5V', (rx, hy + 5.08), 270)]
    # VIN damper: R92 hangs off the VIN wire and feeds C5 and C62
    W += [['R92.2', 'C5.1'], ['C5.1', 'C62.1']]
    # OV guard: both outputs and the pull-up on one wire; divider taps wired to their filter caps
    W += [['U20.2', 'U20.14'], ['U20.2', 'R97.2'],
          ['R93.2', 'R94.1'], ['R94.1', 'C63.1'], ['R95.2', 'R96.1'], ['R96.1', 'C64.1'],
          ['R98.2', 'R99.1'], ['R99.1', 'C66.1']]
    L += [('OV_N', ('U20.2', 2.54, 0), 'U'), ('MON_OV12', ('R93.2', 0, 3.81), 'R'), ('MON_OV5', ('R95.2', 0, 3.81), 'R'),
          ('MON_OVN', ('R98.2', 0, 3.81), 'R')]
    # S8.1 reference: R100 feeds U21 (REF tied to CATHODE), C67 and TP17 on one REF_OV node; D22 hangs on MON_OVN
    W += [['R100.2', 'U21.2'], ['U21.1', m(205.74, 134.62), m(205.74, 129.54), m(210.82, 129.54)],
          [m(210.82, 127.0), m(220.98, 127.0), 'C67.1'], [m(220.98, 127.0), 'TP17.1'],
          ['D22.3', m(297.18, 125.73), 'D22.2'], ['D22.2', m(304.8, 120.65)]]
    L += [('REF_OV', m(214.63, 127.0), 'R')]
    # S8.3 U23 settings; power and logic pins get named stubs from the common drawing engine.
    W += [['R107.2', 'R101.1'], ['R101.2', 'R102.1'], ['R103.2', 'R104.1'],
          ['U23.7', hp(208.28, 289.56), hp(220.98, 289.56), 'C68.1']]
    L += [('P5_OVLO', ('R101.2', 0, 3.81), 'R'), ('P5_ILM', ('R103.1', 0, -2.54), 'U')]
    return W, P, L


TEXTS = []   # page notes live in tools/hierarchy_s8.py; the flat intermediate is replaced by the root
