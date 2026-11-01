"""usb-power-45w S8 single-board circuit table and flat drawing (user direction, 2026-11-01). FINAL.

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
- Overvoltage guard: U20 LM2901 (+12V > ~16.6 V, +5V > ~6.5 V, -12V < ~-15.1 V) pulls OV_N low =
  U12 2PRE_N, which sets FAULT at once (no startup mask) -> RUN low -> U5 off; D21 SMAJ5.0A clamps
  +5V transients.
  U14's second NAND (was NOT_RUN for the removed opto) has its inputs tied to GND.

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
    by['U18']['fields']['Note'] = ('Output-valid comparators on the delivered rails. +12/+5/input use signal on + '
                                   'input; -12V uses the offset negative sense on - input. Clamp negative sense.')

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
                      '10/1000 us). Sustained overvoltage is cut by the U20 guard + U5, not by this part'))

    # ---- VIN: series-R damper replaces the 47u can (capacitor study B_RCx2)
    c[c.index(by['C5'])] = cap('C5', '10u', 'C1206', (243.84, 60.96), '_VIN_DAMP', 'GND',
                               Note='VIN damper capacitor 1 of 2, in series with R92 (replaces the S7 47u can)')
    c.append(cap('C62', '10u', 'C1206', (254.0, 60.96), '_VIN_DAMP', 'GND',
                 Note='VIN damper capacitor 2 of 2, in series with R92'))
    c.append(two('R92', 'R', '1', 'R1206', (243.84, 49.53), 'VIN', '_VIN_DAMP',
                 LCSC='C17928', MPN='1206W4F100KT5E', Manufacturer=UNIROYAL, Tolerance='1%',
                 Note='VIN damper: 1 ohm in series with C5 + C62 (2 x 10u/50V). Damps cable inductance against '
                      'the all-ceramic VIN bank (Middlebrook margin, docs/s8-single-board.md)'))

    # ---- Overvoltage guard: three open-collector comparators wired-AND onto OV_N (same LM2901 as U18)
    c.append(part('U20', 'LM2901_QUAD', 'LM2901DR', 'SO14', m(205.74, 83.82), 0,
                  {'4': 'MON_OV12', '5': 'REF_GOOD', '2': 'OV_N',      # +12V: low when MON_OV12 > REF
                   '6': 'MON_OV5', '7': 'REF_GOOD', '1': 'OV_N',       # +5V: low when MON_OV5 > REF
                   '8': 'REF_GOOD', '9': 'MON_OVN', '14': 'OV_N',      # -12V: low when MON_OVN < REF (|V| high)
                   '10': 'REF_GOOD', '11': 'GND', '13': None,          # spare: output held low, unconnected
                   '3': 'V3V3', '12': 'GND'},
                  LCSC='C7932', MPN='LM2901DR', Manufacturer='Texas Instruments',
                  Note='Overvoltage guard on the always-on 3.3 V: +12V, +5V or |-12V| above its threshold pulls OV_N '
                       'low (U12 2PRE_N) -> FAULT -> RUN low -> U5 off. Last resort for a shorted high-side FET or an '
                       'open feedback resistor; the TPS62933F own OVP (112-118 %) acts first on +12/+5. Comparator 4 '
                       'spare (+ to GND, - to REF_GOOD)'))
    c.append(res('R93', '68k', m(281.94, 66.04), '+12V', 'MON_OV12',
                 Note='+12V OV divider top: 0.767 V x (1 + 68k/3.3k) = 16.6 V nominal, above the converter OVP'))
    c.append(res('R94', '3.3k', m(281.94, 83.82), 'MON_OV12', 'GND', Note='+12V OV divider bottom'))
    c.append(cap('C63', '1n', 'C0603', m(292.1, 83.82), 'MON_OV12', 'GND',
                 Note='~3 us filter: ignores switching spikes, not a real overvoltage'))
    c.append(res('R95', '68k', m(304.8, 66.04), '+5V', 'MON_OV5',
                 Note='+5V OV divider top: 0.767 V x (1 + 68k/9.1k) = 6.50 V nominal, above the converter OVP'))
    c.append(res('R96', '9.1k', m(304.8, 83.82), 'MON_OV5', 'GND', Note='+5V OV divider bottom'))
    c.append(cap('C64', '1n', 'C0603', m(314.96, 83.82), 'MON_OV5', 'GND', Note='~8 us filter'))
    c.append(res('R98', '7.5k', m(304.8, 109.22), 'V3V3', 'MON_OVN',
                 Note='-12V OV offset divider top: MON_OVN = (3.3 x 47k + V x 7.5k) / 54.5k, 1.19 V at -12 V'))
    c.append(res('R99', '47k', m(304.8, 127.0), 'MON_OVN', '-12V',
                 Note='-12V OV divider: trips at -15.1 V nominal (LMR38020 has no output OVP; open R14 runs away)'))
    c.append(cap('C66', '1n', 'C0603', m(314.96, 127.0), 'MON_OVN', 'GND', Note='~6 us filter'))
    c.append(res('R97', '10k', m(231.14, 67.31), 'V3V3', 'OV_N', Note='OV_N pull-up (wired-AND of the U20 outputs)'))
    c.append(cap('C65', '100n', 'C0603', m(241.3, 99.06), 'V3V3', 'GND', Note='U20 decoupling'))
    return c


def drawing():
    """S7 drawing() without the removed parts' wires/symbols/labels, RAW names restored to the
    delivered rails, plus J3 (as J2), the VIN damper and the overvoltage guard."""
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
    return W, P, L


TEXTS = []   # page notes live in tools/hierarchy_s8.py; the flat intermediate is replaced by the root
