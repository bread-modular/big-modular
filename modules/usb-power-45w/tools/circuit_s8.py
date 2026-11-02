"""S8.5 single-board circuit: common input protection plus a fast +5 V series eFuse, one-shot arming latch.

User-authorized replacement of the S8.2 crowbar (2026-11-01): U23 TPS259470ARPWR,
C3662799, independent adjustable OVLO, current limit and true reverse blocking.
The A variant is deliberately selected for stock/cost; the common retained latch
owns system restart. U20 still provides unmasked severe-OV shutdown, sensing P5_RAW before U23.

S8.4 (2026-11-02, fixes of the three S8.3 reviews, docs/s8-single-board.md changelog):
- C1: U23 FLT (pin 4) is OFF P5_OK. TI SLVSFC9C Table 7-3 asserts FLT on reverse-current
  blocking, persistent current limit, ILM faults and over-temperature, so a hot plug into a
  live +5V bus or a large +5V load release (U23 holding the overshoot downstream) latched
  every rail off. FLT now has its own pull-up R108 and test pad TP21 (diagnostic only).
  P5_OK = U23 AUXOFF (input valid + inrush done; Table 7-4: NOT asserted by load-side events)
  wire-AND U18 delivered-voltage comparator, unchanged.
- M1: TIMER_GO = RUN AND MAIN_OK (U13 pin 10 was V20_OK). MAIN_OK is the net that enables
  U2/U3, so the startup qualification window starts with the converters and ARMED cannot be
  masked while they run. V20_OK stays in MAIN_LED_OK / ANY_BAD; R83 220k -> 200k re-centres it
  (16.1 V nominal, 17.7 V high corner) below the 18.25 V minimum loaded PD input so the new
  arming path cannot latch off a legitimate 20 V source.
- M2: R11/R12 (U3 feedback) are 0.1 % / 25 ppm: setpoint 4.856-5.114 V. In the imposed-current release
  screen (s8_calcs ovlo_release) any release from within U23's current limit stays below the OVLO minimum;
  a loop-level load-release test is still open, as is the -35 mV OVLO reconnect corner.
U18/U20 keep LM2901B on always-on VPD (before U5, after F1, clamped by D1) with V3V3 output
pull-ups. No +/-12V rail switches/LEDs are restored. Original S7 circuit45 is untouched.

S8.5 (2026-11-02, the arming blocker of all three S8.4 reviews; U23 and every other S8.4 decision unchanged):
- B: TIMER_GO = RUN AND MAIN_OK (S8.4) restarted the qualification window whenever a fault cycled MAIN_OK
  and armed during the PD 5 V phase when U5's status floated high. S8.5: U12 flip-flop A becomes the one-shot latch
  STARTED (PRE_N = START_N = NAND(MAIN_LED_OK, RUN) on the spare U14 gate, CLR_N = RESET_N, CLK tied low), so the
  first converter enable after RESET sets it and only RESET clears it. TIMER_GO = RUN AND STARTED feeds U11, whose
  output IS ARMED (held because its input is latched). R83 120k moves V20_OK to a 9.06-10.96 V status floor: above
  the PD 5 V phase (U5 FLT/PGOOD valid) and below the U5 turn-off minimum, so V20_OK can never be the first status
  to drop while U5 is on; the input qualification is U5's own UVLO (MAIN_OK). TP19 = STARTED.
- C: MAIN_LED_OK / ANY_BAD now mean "U5 on with valid FLT/PGOOD" (V20_OK only validates U5's status); the replug /
  power-on-reset race of the U20 -12V channel (REF_OV via R100/C67 against the TPS3808 POR) is an explicit OPEN
  item (s8_calcs replug_por), not a margin.

S9.0 (2026-11-02, major revision; docs/s8-single-board.md S9.0 / P2.0 section):
- Step 1, +5V removed: the module is +/-12V only. U3 (TPS62933F +5V buck) and everything that only served +5V
  is gone: U23 TPS259470A with R108/TP21 (P5_FLT_N), OVLO R107/R101/R102, ILM R103/R104, dVdt C68, L2 and the U3
  network (R10-R12, C15-C19), the 10 x 22u raw bank (C20-C23, C69-C72, C75, C76) and the 4 x 22u delivered bank
  (C35, C60, C73, C74), D3/D21/D23, the U20 +5V guard channel (R95, R96, C64), the U18 +5V monitor (R77-R79,
  R44) with TP13 (P5_OK), TP18 (P5_RAW) and J2/J3 pins 11/12 (now open). U14 gate 1 keeps its fourth input high
  (ANY_BAD = NOT(MAIN_LED_OK AND P12_OK AND N12_OK)); the freed U18/U20 comparators are spares with defined inputs
  and open outputs. The main eFuse (U5) nets keep their function and are renamed EF_* -> MAIN_* on the single board
  (they never belonged to +5V); S7 is untouched.
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
# S9.0 step 1: every S7 ref that only served +5V (checked by tools/verify_s8.py; the S8-added +5V refs are S8_PLUS5_DROPPED).
S9_REMOVED = {
    **{r: '+5V TPS62933F converter U3 and its network (VIN, HF, soft-start, bootstrap, RT, feedback, output bank)'
       for r in ('U3', 'L2', 'R10', 'R11', 'R12', 'C15', 'C16', 'C17', 'C18', 'C19', 'C20', 'C21', 'C22', 'C23',
                 '#FLG05')},
    'D3': '+5V converter-output polarity clamp',
    'C35': '+5V ceramic at the J2 +5V pins (J2/J3 pins 11/12 are open in S9)',
    **{r: 'U18 +5V delivered-voltage monitor divider (MON_P5)' for r in ('R77', 'R78', 'R79')},
    'R44': 'P5_OK pull-up (P5_OK removed; U14 gate 1 input 4 tied high)',
    'TP13': 'P5_OK test pad',
}
# S8-added parts that only served +5V (not S7 refs): they must not come back (tests/verify regressions).
S8_PLUS5_DROPPED = ('U23', 'R101', 'R102', 'R103', 'R104', 'R107', 'R108', 'C68', 'C69', 'C70', 'C71', 'C72', 'C73',
                    'C74', 'C75', 'C76', 'D21', 'D23', 'TP18', 'TP21', 'C60', 'R95', 'R96', 'C64')
PLUS5_NETS = ('+5V', 'P5_RAW', 'P5_OK', 'P5_FLT_N', 'P5_OVLO', 'P5_OV_TOP', 'P5_DVDT', 'P5_ILM', 'P5_ILM_SER',
              'MON_P5', 'MON_P5_SER', 'MON_OV5')
# S9.0: the main eFuse U5 nets are not +5V nets; on the single board they are renamed EF_* -> MAIN_* (S7 untouched).
MAIN_RENAME = {'EF_IN': 'MAIN_IN', 'EF_UV': 'MAIN_UV', 'EF_OV': 'MAIN_OV', 'EF_DVDT': 'MAIN_DVDT',
               'EF_ILM': 'MAIN_ILM', 'EF_IMON': 'MAIN_IMON'}
NET_RENAME = {'P12_RAW': '+12V', 'N12_RAW': '-12V', 'N12_STATUS': 'N12_OK', **MAIN_RENAME}

# Flat-sheet anchors of the S8 additions (page offsets: page 01 (0, 0); page 05 header group
# (0, -86.36); page 05 monitor group (-599.44, -508)).
J3_AT = (101.6, 335.28)          # S6 position of the second header (page 05: 101.6, 248.92)
CAP_Y = 365.76                   # header-side ceramics row under J2 / J3 (page 05: y 279.4)
MON = (599.44, 508.0)            # page 05 monitor group offset
U3_BLOCK = ((320.0, 435.0), (178.0, 225.0))   # flat-sheet box of the removed S7 +5V buck drawing (coordinate wires)

# S8.1 overvoltage guard parts, live-checked 2026-11-01 (tools/s8_sourcing.py; all Extended except R100/C67).
LM2901B = dict(LCSC='C22427890', MPN='LM2901BIDR', Manufacturer='Texas Instruments')
R0603_01 = {  # 0.1 %, 25 ppm/C thin film: (LCSC, MPN, manufacturer)
    '10k': ('C95204', 'RT0603BRD0710KL', 'YAGEO'),
    '110k': ('C326736', 'RT0603BRD07110KL', 'YAGEO'),
}
# Symbol of U21: KiCad stock Reference_Voltage:TL431DBZ drawing, pins renumbered to the TI TLV431 DBZ
# package (SLVS139Z Table 4-1: REF 1, CATHODE 2, ANODE 3; the TL431 DBZ order differs). See build_s8.py.
TLV431_DBZ_PINS = {'REF': '1', 'K': '2', 'A': '3'}
TEXT_POS_S8 = {'U21': ((-6.35, -1.27), (-6.35, 1.27), 'left')}
CROWBAR_REMOVED = ('Q11', 'U22', 'Q12', 'Q13', 'R105', 'R106')
# S8.5 arming (item B): the one-shot latch STARTED (U12 flip-flop A, set by START_N from the spare U14 gate), its pad
# TP19, and R83 120k (V20_OK status floor; same Basic line as R75, no new code).
ARMING_ADDED = ('TP19',)
R83_S85 = dict(LCSC=circuit45.R0603['120k'], MPN=circuit45.R_MPN['120k'])
MIRROR_S8 = set()


def res01(ref, value, at, a, b, rot=0, **kw):
    code, mpn, maker = R0603_01[value]
    return two(ref, 'R', value, 'R0603', at, a, b, rot, LCSC=code, MPN=mpn, Manufacturer=maker, Tolerance='0.1%',
               TCR='25ppm', **kw)


def m(x, y):
    """Page-05 monitor coordinates -> flat sheet."""
    return (round(x + MON[0], 2), round(y + MON[1], 2))


def circuit():
    gone = set(S8_REMOVED) | set(S9_REMOVED)
    c = [p for p in circuit45.circuit() if p['ref'] not in gone]
    by = {p['ref']: p for p in c}
    for p in c:
        p['pins'] = {n: NET_RENAME.get(v, v) for n, v in p['pins'].items()}
        if p['ref'].startswith('TP') and p['value'] in MAIN_RENAME:       # test-pad values carry the net name
            p['value'] = MAIN_RENAME[p['value']]
        if 'Note' in p['fields']:
            for old, new in MAIN_RENAME.items():
                p['fields']['Note'] = p['fields']['Note'].replace(old, new)

    # ---- Converters: soft start 22n -> 100n (TPS62933F tSS = CSS x 0.8 V / 5.5 uA)
    by['C9'].update(value='100n')
    by['C9']['fields'] = {**circuit45.CAPS[('100n', 'C0603')],
                          'Note': 'U2 soft start ~14.5 ms (100n x 0.8 V / 5.5 uA; 11-20 ms over CSS/ISS corners): charges '
                                  'rack capacitance on the unswitched rail. S7 had 22n'}
    by['U5']['fields']['Note'] = by['U5']['fields']['Note'].replace(
        '; S6 FLT + PGOOD wired-AND at 3.3 V; common RUN disconnect.',
        '. FLT + PGOOD wired-AND (MAIN_OK) at 3.3 V; common input switch for both rails (RUN). S8.5: its UVLO (16.23-18.23 V '
        'on, 15.04-17.12 V off) is the input qualification of the one-shot arming latch').replace(
        'PGOOD gates U2/U3', 'PGOOD gates U2 (U4 follows +12V via Q1)')
    by['U2']['fields']['Note'] += '. S8: output is the delivered +12V (no rail eFuse); hiccup/OVP/TSD are its own'
    by['U18']['pins']['3'] = 'VPD'
    by['C57']['pins']['1'] = 'VPD'
    by['C57']['fields']['Note'] = 'U18 always-on VPD bypass, 50 V rated; logic outputs still pull up to V3V3'
    by['U4']['fields']['Note'] = by['U4']['fields']['Note'].replace(
        'Pins 1 and pad are the -12V node, not GND.', 'Pins 1 and pad are the delivered -12V node (S8: no '
        'series switch), not GND; 18 ms OCP blanking at start-up charges the rack capacitance.')
    for ref, rail in (('D2', '+12V'), ('D4', '-12V')):
        by[ref]['fields']['Note'] = f'{rail} polarity clamp at the header strip (rack-side reversal enters here)'
    # ---- Status LED: D8 MAIN is the only LED left (S8 final)
    by['D8']['fields']['Note'] = ('Hand-soldered 3 mm horizontal panel LED (manual part, user stock 3 mm red), the only '
                                  'status LED: MAIN = MAIN_LED_OK (U5 on: FLT/PGOOD good, validated by the V20_OK status '
                                  'floor) AND RUN. Any latched fault (bad status after ARMED, or overvoltage) turns it off')
    by['Q6']['fields']['Note'] = 'MAIN LED switch: gate = MAIN_LED_OK (U13), source to the RUN-gated return Q10'
    by['Q10']['fields']['Note'] = 'MAIN LED enable: D8 off whenever RESET/FAULT has turned the rails off (RUN low)'

    # ---- Status: comparator outputs only; pull-ups moved next to U18 (page 05). S9.0: no P5_OK (R44 gone).
    for ref, net, at in (('R35', 'P12_OK', m(248.92, 72.39)), ('R62', 'N12_OK', m(269.24, 72.39))):
        p = by[ref]
        p['at'] = at
        p['pins'] = {'1': 'V3V3', '2': net}
        if p['value'] != '10k':
            p.update(value='10k')
            p['fields'].update(LCSC=circuit45.R0603['10k'], MPN=circuit45.R_MPN['10k'])
        p['fields']['Note'] = f'{net} pull-up: delivered-voltage monitor'
    # ---- S8.5 (B): V20_OK is a U5 status-validity floor, not an input-good threshold (the U5 UVLO is).
    by['R83'].update(value='120k')
    by['R83']['fields'].update(**R83_S85, Note='MON_20 top. S8.5: 120k (S8.4 200k): V20_OK = VPD > 9.06-10.96 V '
                                               '(9.98 V nominal), above the PD 5 V phase where U5 FLT/PGOOD may be '
                                               'undefined and below the U5 turn-off minimum (15.04 V), so it validates '
                                               'MAIN_OK and never drops first while U5 is on. Not an input-good '
                                               'threshold: the input qualification is the U5 UVLO')
    by['U18']['value'] = LM2901B['MPN']
    # S9.0: comparator B (out 2, -4 / +5) was the +5V monitor; it is a spare with defined inputs and an open output.
    by['U18']['pins'].update({'2': None, '4': 'REF_GOOD', '5': 'GND'})
    by['U18']['fields'] = {**LM2901B, 'Note': 'Output-valid comparators on the delivered rails. +12V and the input floor '
                                              'use signal on + input; -12V uses the offset negative sense on - input. Clamp '
                                              'negative sense. S9.0: the former +5V channel (pins 2/4/5) is a spare: - at '
                                              'REF_GOOD, + at GND, output open. S8.1: LM2901B (same part as U20)'}

    # ---- Fault latch: OV guard on the spare preset. S8.5 (B): flip-flop A = one-shot STARTED latch.
    by['U12']['pins'].update({'10': 'OV_N', '3': 'GND', '4': 'START_N', '5': 'STARTED'})
    by['U12']['fields']['Note'] = ('A = STARTED (S8.5): asynchronous set by START_N (first converter enable after RESET), '
                                   'cleared only by RESET_N, clock tied low, so no fault can restart arming. B = FAULT: '
                                   'clocked by ARMED & filtered bad, preset by OV_N (U20 guard) at any time, also before '
                                   'ARMED, cleared by RESET_N. No firmware.')
    # S9.0: gate 1 input 4 (was P5_OK) tied high: ANY_BAD = NOT(MAIN_LED_OK AND P12_OK AND N12_OK).
    by['U14']['pins'].update({'4': 'V3V3', '8': 'START_N', '9': 'MAIN_LED_OK', '10': 'RUN', '12': 'V3V3', '13': 'V3V3'})
    by['U14']['fields']['Note'] = ('Gate 1: ANY_BAD = NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3) (S9.0: the +5V input is tied '
                                   'high). Gate 2 (S8.5): START_N = NAND(MAIN_LED_OK, RUN): low once U5 is on with valid '
                                   'status while RUN, presets the STARTED latch (U12 A); RUN in the gate keeps PRE_N high '
                                   'while RESET clears it.')
    by['U13']['pins']['10'] = 'STARTED'
    by['U13']['fields']['Note'] = ('RUN=RESET_N & NOT_FAULT; fault clock=ARMED & filtered bad; S8.5 timer=RUN & STARTED '
                                   '(the latched first converter enable: only RESET or a latched FAULT stops it); '
                                   'MAIN_LED_OK=MAIN_OK & V20_OK (U5 on with validated status).')
    by['C49'].update(value='100n')
    by['C49']['fields'] = {**circuit45.CAPS[('100n', 'C0603')],
                           'Note': 'Startup qualification ~0.57 s typical (TPS3808: CT nF / 175 + 0.5 ms). '
                                   'S7 had 1u (5.7 s) for the removed LM5067 insertion delay'}
    by['U11']['pins']['1'] = 'ARMED'
    by['U11']['fields']['Note'] = ('S8.5 one-shot qualification timer: SENSE = TIMER_GO = RUN AND STARTED (latched), MR = '
                                   'RESET_N; its RESET output IS ARMED, high 0.31-0.88 s (100n, ~0.57 s) after the first '
                                   'converter enable and held until RESET/FAULT because its input cannot drop otherwise.')
    by['R71']['pins']['2'] = 'ARMED'
    by['R71']['fields']['Note'] = 'ARMED pull-up (U11 open-drain RESET output, S8.5)'
    tp6 = by['TP6']
    tp6.update(value='OV_N', at=(309.88, 721.36))   # end of the page-04 test-pad row (was FAULT_LATCH twice)
    tp6['pins'] = {'1': 'OV_N'}
    c.append(part('TP19', 'TestPoint', 'STARTED', 'TP', (345.44, 721.36), 0, {'1': 'STARTED'},
                  Note='S8.5 STARTED (U12 Q1): low until the first converter enable after RESET, then high until RESET. '
                       'Copper-only diagnostic; no assembly component'))

    # ---- Outputs: J2 + J3 in parallel (Doepfer pinout), header-side ceramics. S9.0: pins 11/12 (+5V) are open.
    j2 = by['J2']
    j2['pins'].update({'11': None, '12': None})
    j2['fields']['Note'] = ('Hand-soldered shrouded 16-pin box header, pin 1 = -12V (red stripe). One of two '
                            'parallel outputs (J2/J3, S8). Each cable carries 2 contacts per rail: above ~2 A '
                            'per rail use both headers. S9.0: +/-12V only, pins 11/12 (+5V) and CV/GATE (13-16) open')
    j3 = copy.deepcopy(j2)
    j3.update(ref='J3', at=J3_AT)
    c.append(j3)
    for (ref, x, rail), hdr in zip((('C34', 30.48, '+12V'), ('C36', 50.8, '-12V'),
                                    ('C59', 86.36, '+12V'), ('C61', 106.68, '-12V')),
                                   ('J2',) * 2 + ('J3',) * 2):
        a, b = ('GND', '-12V') if rail == '-12V' else (rail, 'GND')
        new = cap(ref, '22u', 'C1206', (x, CAP_Y), a, b,
                  Note=f'{rail} ceramic at the {hdr} {rail} pins: with its twin at the other header it replaces '
                       f'the S7 100u can (rail bank 4/5 x 22u at the converter + 2). See docs/s8-single-board.md')
        if ref in by:
            c[c.index(by[ref])] = new
        else:
            c.append(new)

    # ---- VIN: series-R damper replaces the 47u can (capacitor study B_RCx2)
    c[c.index(by['C5'])] = cap('C5', '10u', 'C1206', (243.84, 60.96), '_VIN_DAMP', 'GND',
                               Note='VIN damper capacitor 1 of 2, in series with R92 (replaces the S7 47u can)')
    c.append(cap('C62', '10u', 'C1206', (254.0, 60.96), '_VIN_DAMP', 'GND',
                 Note='VIN damper capacitor 2 of 2, in series with R92'))
    c.append(two('R92', 'R', '1', 'R1206', (243.84, 49.53), 'VIN', '_VIN_DAMP',
                 LCSC='C17928', MPN='1206W4F100KT5E', Manufacturer=UNIROYAL, Tolerance='1%',
                 Note='VIN damper: 1 ohm in series with C5 + C62 (2 x 10u/50V). Damps cable inductance against '
                      'the all-ceramic VIN bank (Middlebrook margin, docs/s8-single-board.md)'))

    # ---- Overvoltage guard: open-collector comparators wired-AND onto OV_N. S8.1: own precision reference REF_OV,
    # LM2901B, 0.1 % dividers; the -12V channel compares a REF_OV-offset divider with GND (no V3V3 term). S9.0: two
    # channels (+12V, -12V); the former +5V channel (pins 1/6/7) is a second spare like pins 10/11/13.
    c.append(part('U20', 'LM2901_QUAD', LM2901B['MPN'], 'SO14', m(205.74, 83.82), 0,
                  {'4': 'MON_OV12', '5': 'REF_OV', '2': 'OV_N',        # +12V: low when MON_OV12 > REF_OV
                   '6': 'REF_OV', '7': 'GND', '1': None,               # spare (S9.0, was +5V): output low, unconnected
                   '8': 'GND', '9': 'MON_OVN', '14': 'OV_N',           # -12V: low when MON_OVN < 0 V (|V| high)
                   '10': 'REF_OV', '11': 'GND', '13': None,            # spare: output held low, unconnected
                   '3': 'VPD', '12': 'GND'},
                  **LM2901B,
                  Note='Always-on VPD supply (not V3V3), V3V3 pull-up on OV_N. Full-temperature input ceiling VPD-2 V; '
                       'REF_OV <=1.259 V. Senses +12V and -12V (S9.0: two channels, two spares); severe OV presets FAULT '
                       'even before ARMED. S8.4: with V3V3 lost but VPD present U20 may stay powered; its outputs then '
                       'drive dead pull-ups and R64 holds RUN low, so it cannot enable anything (s8_calcs v3v3_loss).'))
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
                      '(SLVS139Z Fig. 5-18). REF_OV settles in ~9-14 ms; replug into a rack holding -12V can race the '
                      '>=12 ms POR (S8.5 OPEN item, calcs replug_por)'))
    c.append(part('TP17', 'TestPoint', 'REF_OV', 'TP', m(231.14, 127.0), 0, {'1': 'REF_OV'},
                  Note='Copper-only diagnostic; no assembly component. Bench: REF_OV 1.22-1.26 V'))
    c.append(res01('R93', '110k', m(281.94, 66.04), '+12V', 'MON_OV12',
                   Note='+12V OV divider top: 1.24 V x (1 + 110k/10k) = 14.88 V nominal (14.48-15.27 V over corners)'))
    c.append(res01('R94', '10k', m(281.94, 83.82), 'MON_OV12', 'GND', Note='+12V OV divider bottom'))
    c.append(cap('C63', '1n', 'C0603', m(292.1, 83.82), 'MON_OV12', 'GND',
                 Note='~9 us filter: ignores switching spikes, not a real overvoltage'))
    c.append(res01('R98', '10k', m(304.8, 109.22), 'REF_OV', 'MON_OVN',
                   Note='-12V OV offset divider top from REF_OV: MON_OVN = (1.24 x 110k + V x 10k) / 120k, 0.14 V at '
                        '-12 V, 0 V at -13.64 V'))
    c.append(res01('R99', '110k', m(304.8, 127.0), 'MON_OVN', '-12V',
                   Note='-12V OV divider: trips at -13.64 V nominal (13.27-14.02 V; LMR38020 has no output OVP, '
                        'an open R14 runs away)'))
    c.append(cap('C66', '1n', 'C0603', m(314.96, 127.0), 'MON_OVN', 'GND', Note='~9 us filter'))
    c.append(part('D22', 'BAT54S', 'BAT54SLT1G', 'SOT23', m(289.56, 120.65), 0,
                  {'1': 'GND', '2': 'MON_OVN', '3': 'MON_OVN'}, LCSC='C19726', MPN='BAT54SLT1G', Manufacturer='onsemi',
                  Note='MON_OVN clamp: diode 1 GND -> MON_OVN, diode 2 shorted. With V3V3 gone and -12V held it keeps U20 '
                       'pin 9 near -0.24 V at 25 C only (0.1 mA VF max); cold it can pass -0.3 V. Not a guaranteed input '
                       'clamp: R99 limits the node current to <=0.15 mA at -16 V (input rating 50 mA). ~0 V across it at the trip'))
    c.append(res('R97', '10k', m(231.14, 67.31), 'V3V3', 'OV_N',
                 Note='OV_N pull-up (wired-AND of the U20 guard outputs)'))
    c.append(cap('C65', '100n', 'C0603', m(241.3, 99.06), 'VPD', 'GND',
                 Note='U20 always-on VPD decoupling, 50 V, at U20 pin 3 (S8.4 placement contract <=4.5 mm); not V3V3'))
    return c


def drawing():
    """S7 drawing() without the removed parts' wires/symbols/labels, RAW names restored to the delivered rails, plus
    J3, the VIN damper and the OV guard. S9.0: the +5V converter block, the J2/J3 +5V pins and the U23 cell are gone."""
    W, P, L = circuit45.drawing()
    gone = set(S8_REMOVED) | set(S9_REMOVED) | {'R35', 'R62'}   # moved refs: S7 lines at their old spots
    (bx0, bx1), (by0, by1) = U3_BLOCK

    def ref_of(pt):
        if isinstance(pt, str):
            return pt.split('.')[0]
        if isinstance(pt[0], str):
            return pt[0].split('.')[0]
        return None

    def in_u3(pt):
        return not isinstance(pt, str) and not isinstance(pt[0], str) and bx0 <= pt[0] <= bx1 and by0 <= pt[1] <= by1
    W = [w for w in W if not any(ref_of(pt) in gone for pt in w) and not all(in_u3(pt) for pt in w)
         and not any(pt in ('J2.11', 'J2.12') for pt in w)]
    P = [(NET_RENAME.get(n, n), pt, rot) for n, pt, rot in P
         if ref_of(pt) not in gone and not in_u3(pt) and n != '+5V']
    L = [(NET_RENAME.get(n, n), pt, side) for n, pt, side in L if ref_of(pt) not in gone]

    # J3: same wiring as J2 in circuit45.drawing() (S9.0: pins 11/12 open, no +5V symbols)
    hx, hy = J3_AT
    lx, rx = hx - 5.08 - 5.08, hx + 7.62 + 5.08
    j = 'J3'
    W += [[f'{j}.1', (lx, hy - 7.62)], [f'{j}.2', (rx, hy - 7.62)],
          [f'{j}.3', (lx + 2.54, hy - 5.08), (lx + 2.54, hy), f'{j}.7'], [f'{j}.5', (lx + 2.54, hy - 2.54)],
          [(lx + 2.54, hy - 5.08), (lx, hy - 5.08)],
          [f'{j}.4', (rx - 2.54, hy - 5.08), (rx - 2.54, hy), f'{j}.8'], [f'{j}.6', (rx - 2.54, hy - 2.54)],
          [(rx - 2.54, hy - 5.08), (rx, hy - 5.08)],
          [f'{j}.9', (lx, hy + 2.54)], [f'{j}.10', (rx, hy + 2.54)]]
    P += [('-12V', (lx, hy - 7.62), 90), ('-12V', (rx, hy - 7.62), 270),
          ('GND', (lx, hy - 5.08), 270), ('GND', (rx, hy - 5.08), 90),
          ('+12V', (lx, hy + 2.54), 90), ('+12V', (rx, hy + 2.54), 270)]
    # VIN damper: R92 hangs off the VIN wire and feeds C5 and C62
    W += [['R92.2', 'C5.1'], ['C5.1', 'C62.1']]
    # OV guard: both outputs and the pull-up on one wire; divider taps wired to their filter caps. S9.0: the OV_N wire
    # jogs 2.54 mm right of the output pins so it does not pass the now-open spare output pin 1.
    W += [['U20.2', ('U20.2', 2.54, 0), ('U20.14', 2.54, 0), 'U20.14'], ['U20.2', 'R97.2'],
          ['R93.2', 'R94.1'], ['R94.1', 'C63.1'],
          ['R98.2', 'R99.1'], ['R99.1', 'C66.1']]
    L += [('OV_N', ('U20.2', 2.54, 0), 'U'), ('MON_OV12', ('R93.2', 0, 3.81), 'R'),
          ('MON_OVN', ('R98.2', 0, 3.81), 'R')]
    # S8.1 reference: R100 feeds U21 (REF tied to CATHODE), C67 and TP17 on one REF_OV node; D22 hangs on MON_OVN
    W += [['R100.2', 'U21.2'], ['U21.1', m(205.74, 134.62), m(205.74, 129.54), m(210.82, 129.54)],
          [m(210.82, 127.0), m(220.98, 127.0), 'C67.1'], [m(220.98, 127.0), 'TP17.1'],
          ['D22.3', m(297.18, 125.73), 'D22.2'], ['D22.2', m(304.8, 120.65)]]
    L += [('REF_OV', m(214.63, 127.0), 'R')]
    return W, P, L


TEXTS = []   # page notes live in tools/hierarchy_s8.py; the flat intermediate is replaced by the root
