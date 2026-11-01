"""usb-power-45w S8 single-board circuit table and flat drawing (user direction, 2026-11-01). S8.1.

"Design new schematics for a single board which remove all these three eFuse but keep the LEDs
for each rail. Also replace big caps with ceramic ones (only if possible, so we save space). But
do any pre-calculations etc." + "In this board add space for two IDC sockets."
Earlier answer in the same thread ("Yes") to: C9/C18 22n -> 100n, C49 1u -> 100n and the
optional overvoltage guard (comparator into the spare fault-latch preset + TVS on +5V).
Then: "Remove each rail LEDs too. [...] Make the schematic final." -> the three panel rail LEDs
(D16/D17/D18 with R86-R88 and drivers Q7-Q9) and the local SMD rail LEDs (D5/D6/D7 with R19-R21)
are removed; D8 MAIN (Q6 + the RUN-gated return Q10) is the only status LED. Any bad rail after
the startup window, or any overvoltage, latches every rail off, so MAIN off = not working.

Derived from the S7 table (tools/circuit45.py + tools/protection6.py), which stays untouched:

- Removed: U6/U7 TPS16630 rail eFuses with their setting parts, the LM5067/Q4 negative switch with
  its Kelvin shunt, VCC feed, optocouplers, clamps and timer, the delivered-side clamps D12-D14,
  bleeders/output caps after the switches and the U19 Schmitt buffer (S8_REMOVED gives every ref).
- Each converter output is now the delivered rail: P12_RAW -> +12V, P5_RAW -> +5V,
  N12_RAW -> -12V. The voltage monitors (U18) are unchanged; P12_OK, P5_OK and N12_OK are now the
  comparator outputs alone (R35/R44/R62 10k pull-ups) and feed only the fault logic (+ test pads).
- Rail LEDs removed (panel D16-D18 + R86-R88 + Q7-Q9, local D5-D7 + R19-R21); D8 MAIN kept.
- The four electrolytic cans become ceramics: C5 (47u VIN) -> C5 + C62 10u/50V behind R92 1R
  (series-R damper, capacitor study option B_RCx2); C34/C35/C36 (100u at the rails) -> one 22u/25V
  per rail at J2 plus C59/C60/C61 at J3 (option B_x2). Calculations: tools/s8_calcs.py.
- Two parallel 16-pin outputs again: J3 = J2 (Wurth 61201621621, pin 1 = -12V).
- Startup: C9/C18 100n (~14.5 ms soft start into rack capacitance), C49 100n (~0.57 s window).
- Overvoltage guard: U20 pulls OV_N low = U12 2PRE_N, which sets FAULT at once (no startup mask)
  -> RUN low -> U5 off; D21 SMAJ5.0A clamps +5V transients.
  U14's second NAND (was NOT_RUN for the removed opto) has its inputs tied to GND.

S8.1 (review a9d257b6, 2026-11-01, user: "try to improve the board based on its suggestion"):
- The guard thresholds (S8: 16.6 / 6.5 / 15.1 V nominal, stacked corners up to 18.45 / 7.22 / 16.36 V)
  came from REF_GOOD = V3V3 / 4.3 (TPS7A16 +-2 % and two 1 % resistors) and an LM2901 with 15 mV offset.
  U20 now has its own reference REF_OV = U21 TLV431B (1.224-1.259 V, -40..85 C) fed by R100 with C67
  10u (stable region of SLVS139Z Fig. 5-18), U18 and U20 are the drop-in LM2901B (5.5 mV), and the six
  divider resistors are 0.1 % / 25 ppm: +12V > 14.88 V, +5V > 5.83 V, -12V < -13.64 V nominal.
- The -12V sense no longer depends on V3V3: R98 runs from REF_OV, comparator 3 compares MON_OVN with
  GND (trip |V| = REF_OV x R99 / R98). D22 (BAT54S, one diode used, the other shorted, as S7 D19/D20)
  clamps MON_OVN at GND when V3V3 is gone and the rack still holds -12V (review finding 1).
- U18 keeps REF_GOOD and its thresholds; only its part number changes (one comparator BOM line).

S8.2 (user, 2026-11-01, after S8.1 left it open: "A crowbar would short +5V to ground instead, so it stays near
1 V." -> "yeah. Do that"): +5V crowbar on page 06 beside D21.
- Q11 TS1220-600B-TR (12 A DPAK SCR, IGT 200 uA, VT0 0.85 V + 30 mOhm) across +5V: once fired it holds the rail
  at ~1-3.5 V until the energy behind it (VIN ceramics through a shorted high side, rail and rack capacitance) is
  gone, then drops out below its 5 mA holding current.
- Trigger powered by +5V itself, not by V3V3: U22 TLVH432B (1.24 V, 18 V cathode) on its own 0.1 % 37k/10k divider
  with a 1n filter (same 5.83 V nominal and ~8 us as the U20 guard) pulls the Q12 AO3401A gate; Q12 drives the SCR
  gate through R104 2.2k (R105 1k gate-cathode). A trigger fed from V3V3 / U20 could misfire at power-down while
  V3V3 collapses before the rack's +5V; this one cannot fire below its threshold.
- Latch link: Q13 MMBT3904 (base from the Q12 drain through R106) pulls OV_N low whenever the trigger drives the
  gate, so FAULT is set and U5 opens even when the crowbar collapses +5V before the guard comparator trips. R104
  keeps the drain >= ~1 V before the SCR can fire; Q13 conducts from ~0.5-0.8 V.
- U20 comparator 4 stays spare. D21 stays: it clamps the first microseconds before the SCR fires.

Positions are flat-sheet coordinates (page = flat - hierarchy offset, tools/hierarchy_s8.py).
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
NET_RENAME = {'P12_RAW': '+12V', 'P5_RAW': '+5V', 'N12_RAW': '-12V', 'N12_STATUS': 'N12_OK'}

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
TEXT_POS_S8 = {'U21': ((-6.35, -1.27), (-6.35, 1.27), 'left'),    # U21 texts left of the REF tie (build_s8.py)
               'U22': ((2.54, -1.27), (2.54, 1.27), 'right'),   # rot 90: KiCad shows 'right' as left-aligned
               'Q11': ((3.81, -1.27), (3.81, 1.27), 'left'), 'R106': ((-2.54, -1.27), (-2.54, 1.27), 'right'),
               'Q12': ((5.08, -1.27), (5.08, 1.27), 'left'), 'Q13': ((5.08, -1.27), (5.08, 1.27), 'left')}

# S8.2 +5V crowbar, live-checked 2026-11-01 (tools/s8_sourcing.py): TS1220 and TLVH432B Extended, AO3401A and
# MMBT3904 Basic, the 0.1 % 37k/10k pair and the 1n/1k/2.2k/3.3k/10k parts reuse S8.1 BOM lines.
TS1220 = dict(LCSC='C222165', MPN='TS1220-600B-TR', Manufacturer='STMicroelectronics')
TLVH432B = dict(LCSC='C2156793', MPN='TLVH432BIDBZR', Manufacturer='Texas Instruments')
AO3401A = dict(LCSC='C15127', MPN='AO3401A', Manufacturer='Alpha & Omega Semicon')
MMBT3904 = dict(LCSC='C20526', MPN='MMBT3904', Manufacturer='Jiangsu Changjing Electronics Technology Co., Ltd.')
# Symbol of U22: KiCad stock Reference_Voltage:TL431DBZ unchanged; its numbers (K 1, REF 2, A 3) are the TI TLVH432
# DBZ pinout (SLVS555N Pin Functions: CATHODE 1, REF 2, ANODE 3). See build_s8.py.
TLVH432_DBZ_PINS = {'K': '1', 'REF': '2', 'A': '3'}
CROWBAR = ('Q11', 'U22', 'Q12', 'Q13', 'R101', 'R102', 'R103', 'R104', 'R105', 'R106', 'C68')
HDR = (0.0, 86.36)               # page 06 header group offset (tools/hierarchy_s8.py)
MIRROR_S8 = {'Q12'}              # P-MOSFET drawn source up, gate left (build_s8.py)


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
        '. FLT + PGOOD wired-AND (MAIN_OK) at 3.3 V. S8: the ONLY switch; RUN low turns every rail off')
    by['U2']['fields']['Note'] += '. S8: output is the delivered +12V (no rail eFuse); hiccup/OVP/TSD are its own'
    by['U3']['fields']['Note'] += '. S8: output is the delivered +5V (no rail eFuse); hiccup/OVP/TSD are its own'
    by['U4']['fields']['Note'] = by['U4']['fields']['Note'].replace(
        'Pins 1 and pad are the -12V node, not GND.', 'Pins 1 and pad are the delivered -12V node (S8: no '
        'series switch), not GND; 18 ms OCP blanking at start-up charges the rack capacitance.')
    for ref, rail in (('D2', '+12V'), ('D3', '+5V'), ('D4', '-12V')):
        by[ref]['fields']['Note'] = f'{rail} polarity clamp at the converter output = delivered rail (S8)'
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
        p['fields']['Note'] = f'{net} pull-up: U18 open-collector output only (S8: no eFuse FLT/PGOOD, no opto)'
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
    c.append(two('D21', 'D_Zener', 'SMAJ5.0A', 'SMA', (127.0, CAP_Y), '+5V', 'GND', rot=270,
                 LCSC='C113952', MPN='SMAJ5.0A', Manufacturer='MDD(Microdiode Semiconductor)',
                 Note='+5V transient clamp at the headers (5.0 V stand-off, 6.4 V min breakdown, 9.2 V at 43.5 A '
                      '10/1000 us): holds the first microseconds until the Q11 crowbar fires (S8.2). Sustained '
                      'overvoltage is cut by the U20 guard + U5 and shorted by Q11, not by this part'))

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
                   '3': 'V3V3', '12': 'GND'},
                  **LM2901B,
                  Note='Overvoltage guard on the always-on 3.3 V: +12V, +5V or |-12V| above its threshold pulls OV_N '
                       'low (U12 2PRE_N) -> FAULT -> RUN low -> U5 off. Last resort for a shorted high-side FET or an '
                       'open feedback resistor. LM2901B: offset 5.5 mV max over temperature. Comparator 4 spare (+ to '
                       'GND, - to REF_OV). Common-mode limit VCC - 1.5 V at 25 C (1.73 V at 3.23 V): REF_OV 1.24 V'))
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
    c.append(res01('R95', '37k', m(304.8, 66.04), '+5V', 'MON_OV5',
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
                 Note='OV_N pull-up (wired-AND of the U20 outputs and the Q13 crowbar latch link)'))
    c.append(cap('C65', '100n', 'C0603', m(241.3, 99.06), 'V3V3', 'GND', Note='U20 decoupling'))

    # ---- S8.2 +5V crowbar: self-powered TLVH432B trigger -> AO3401A -> TS1220 SCR gate; Q13 sets FAULT (OV_N)
    c.append(part('Q11', 'Q_SCR_KAG', TS1220['MPN'], 'DPAK', hp(231.14, 279.4), 0,
                  {'1': 'GND', '2': '+5V', '3': 'CROW_GATE'}, **TS1220,
                  Note='+5V crowbar SCR: shorts +5V to ~1-3.5 V (VT0 0.85 V + 30 mOhm x up to ~75 A) once U22 trips, until the energy '
                       'behind it is gone (IH 5 mA max). 12 A DPAK, ITSM 110 A / I2t 60 A2s, IGT 200 uA. DPAK pin 1 K, '
                       'pin 2 and tab A (+5V), pin 3 G (ST DocID027645). Shorting a second supply on the bus is not rated'))
    c.append(part('U22', 'TLVH432_DBZ', TLVH432B['MPN'], 'SOT23', hp(175.26, 279.4), 90,
                  {TLVH432_DBZ_PINS['K']: 'CROW_TRIP_N', TLVH432_DBZ_PINS['REF']: 'CROW_SENSE',
                   TLVH432_DBZ_PINS['A']: 'GND'}, **TLVH432B,
                  Note='Crowbar trigger, powered by +5V itself (no V3V3): sinks when CROW_SENSE > 1.24 V, +5V > 5.83 V '
                       'nominal (5.70-5.98 V over corners). TLVH432B: 18 V cathode (+5V can reach ~10 V in D21 before '
                       'the SCR fires; TLV431 is 7 V max). DBZ pins CATHODE 1, REF 2, ANODE 3 (SLVS555N)'))
    c.append(res01('R101', '37k', hp(152.4, 271.78), '+5V', 'CROW_SENSE',
                   Note='Crowbar divider top: 1.24 V x (1 + 37k/10k) = 5.83 V nominal, the U20 +5V guard ratio'))
    c.append(res01('R102', '10k', hp(152.4, 287.02), 'CROW_SENSE', 'GND', Note='Crowbar divider bottom'))
    c.append(cap('C68', '1n', 'C0603', hp(162.56, 287.02), 'CROW_SENSE', 'GND',
                 Note='~8 us filter, as the guard: ignores switching spikes and short ringing on +5V'))
    c.append(res('R103', '3.3k', hp(185.42, 267.97), '+5V', 'CROW_TRIP_N',
                 Note='Q12 gate pull-up: Q12 off while U22 is off; ~1.4 mA through U22 once it trips'))
    c.append(part('Q12', 'AO3401A', AO3401A['MPN'], 'SOT23', hp(195.58, 271.78), 0,
                  {'1': 'CROW_TRIP_N', '2': '+5V', '3': 'CROW_DRV'}, **AO3401A,
                  Note='Crowbar gate driver: U22 pulls the gate low, +5V drives the SCR gate through R104 (~1.5-2.5 mA, '
                       '7-12 x IGT max) and the Q13 latch link through R106'))
    c.append(res('R104', '2.2k', hp(213.36, 281.94), 'CROW_DRV', 'CROW_GATE', rot=90,
                 Note='SCR gate series: limits the gate current and keeps CROW_DRV >= ~1 V before the SCR can fire, '
                      'so Q13 has already pulled OV_N low'))
    c.append(res('R105', '1k', hp(220.98, 288.29), 'CROW_GATE', 'GND',
                 Note='SCR gate-cathode resistor (TS1220 IH / IL condition, dV/dt immunity)'))
    c.append(res('R106', '10k', hp(198.12, 290.83), 'CROW_DRV', '_CROW_LATCH', Note='Q13 base resistor'))
    c.append(part('Q13', 'MMBT3904', MMBT3904['MPN'], 'SOT23', hp(203.2, 297.18), 0,
                  {'1': '_CROW_LATCH', '2': 'GND', '3': 'OV_N'}, **MMBT3904,
                  Note='Crowbar -> fault latch: pulls OV_N low (wired-AND with U20) whenever Q12 drives the SCR gate, '
                       'so FAULT is set and U5 opens even if the crowbar collapses +5V before the guard comparator trips'))
    return c


def drawing():
    """S7 drawing() without the removed parts' wires/symbols/labels, RAW names restored to the
    delivered rails, plus J3 (as J2), the VIN damper, the overvoltage guard with its S8.1 reference and the
    S8.2 +5V crowbar."""
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
    # S8.2 crowbar (page 06 beside D21): divider -> U22 REF; U22 cathode, R103 and the Q12 gate on one row; Q12 drain
    # -> R104 -> SCR gate (R105 to GND) and -> R106 -> Q13 base; Q13 collector gets an OV_N stub label.
    W += [['R101.2', 'R102.1'], [hp(152.4, 279.4), hp(162.56, 279.4), 'C68.1'], [hp(162.56, 279.4), 'U22.2'],
          ['U22.1', hp(175.26, 271.78), 'R103.2'], ['R103.2', 'Q12.1'],
          ['Q12.3', hp(198.12, 281.94), 'R104.1'], [hp(198.12, 281.94), 'R106.1'],
          ['R104.2', hp(220.98, 281.94), 'R105.1'], [hp(220.98, 281.94), 'Q11.3'], ['R106.2', 'Q13.1']]
    L += [('CROW_SENSE', hp(167.64, 279.4), 'U'), ('CROW_TRIP_N', hp(180.34, 271.78), 'U'),
          ('CROW_DRV', hp(198.12, 279.4), 'R'), ('CROW_GATE', hp(223.52, 281.94), 'U')]
    return W, P, L


TEXTS = []   # page notes live in tools/hierarchy_s8.py; the flat intermediate is replaced by the root
