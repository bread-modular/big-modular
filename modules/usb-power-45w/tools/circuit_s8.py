"""S9.1 / P2.1: own-input U4 enable, VIN pulse clamps, precision UVLO, 18mR R109,
separate AGND_U2 with sole C82 star link, 175-Hz compensation zero. S7 untouched.
Historical revision notes follow (superseded by implementation below).
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
TEXT_POS_S8 = {'U21': ((-6.35, -1.27), (-6.35, 1.27), 'left'),
               # S9.0 page 02: texts clear of the BOOT/SW wires, the VCC node and the FB/COMP network
               'U2': ((0, 27.94), (0, 30.48)), 'L1': ((0, -5.08), (0, -2.54)),
               'C10': ((-5.08, -1.27), (-5.08, 1.27), 'left'), 'C9': ((5.08, -1.27), (5.08, 1.27), 'right'),
               'C82': ((-2.54, -1.27), (-2.54, 1.27), 'right'), 'R8': ((0, -5.08), (0, -2.54)),
               'R111': ((-2.54, 1.27), (-2.54, 3.81), 'right')}
CROWBAR_REMOVED = ('Q11', 'U22', 'Q12', 'Q13', 'R105', 'R106')
# S9.0 step 2: +12V buck-boost U2 and the parts it adds (S7 refs U2, L1, R8, R9, C6-C14 keep their roles; C9 is BOOT2).
TPS552892 = dict(LCSC='C22375748', MPN='TPS552892QWRYQRQ1', Manufacturer='Texas Instruments')
R_SENSE = dict(LCSC='', MPN='WSLP1206R0180FEA', Manufacturer='Vishay Dale', Tolerance='1%', TCR='75ppm',
               Power='1W')
S91_ADDED = ('Q14', 'Q15', 'R112', 'R113', 'R114', 'D24', 'D25', 'D26')
BUCKBOOST_ADDED = ('C77', 'C78', 'C79', 'C80', 'C81', 'C82', 'C83', 'R109', 'R110', 'R111')
U2_AT = (381.0, 78.74)            # flat sheet (page 02 offset -276.86, 0); S7 U2 sat at (368.3, 71.12)
U2_BLOCK = ((320.0, 435.0), (50.0, 98.0))     # flat-sheet box of the removed S7 +12V buck drawing (coordinate wires)
R0603_S9 = {'56k': ('C23206', '0603WAF5602T5E')}      # S9.0 Basic code not in the S7 table (live evidence s90-sourcing)
# S8.5 arming (item B): the one-shot latch STARTED (U12 flip-flop A, set by START_N from the spare U14 gate) and its pad
# TP19. S8.5 set R83 120k (20 V input); S9.0 uses 100k at 15 V (the Basic 100k line of R2, no new code).
ARMING_ADDED = ('TP19',)
MIRROR_S8 = set()


def res01(ref, value, at, a, b, rot=0, **kw):
    code, mpn, maker = R0603_01[value]
    return two(ref, 'R', value, 'R0603', at, a, b, rot, LCSC=code, MPN=mpn, Manufacturer=maker, Tolerance='0.1%',
               TCR='25ppm', **kw)


def m(x, y):
    """Page-05 monitor coordinates -> flat sheet."""
    return (round(x + MON[0], 2), round(y + MON[1], 2))


def _plus12_buckboost(c, by):
    """S9.0 step 2: replace the TPS62933F buck (U2) by the TPS552892-Q1 four-switch buck-boost, re-using the S7 refs of
    the +12V cell where the role survives (L1, C6/C7 VIN, C8 VIN HF, C10 BOOT1, C9 BOOT2, R8/R9 FB, C11-C14 output).
    Page-02 drawing (flat sheet, page offset -276.86): VIN bank on a rail top-left, L1 above the IC between SW1 and SW2
    with the BOOT capacitors on BOOT1/BOOT2, MODE/EXTVCC/VCC one node with C82, FSW/R110 bottom-left, the VOUT/ISP node
    feeding the output bank rail and R109 top-right, FB divider and COMP network bottom-right (circuit_s8.drawing)."""
    u2 = by['U2']
    u2.update(sym='TPS552892_RYQ', value=TPS552892['MPN'], fp='RYQ21', at=U2_AT, rot=0, unit=1)
    u2['pins'] = {'7': 'VIN', '1': 'MAIN_OK', '2': '_VCC_U2', '21': '_VCC_U2', '18': '_VCC_U2', '5': 'AGND_U2',
                  '6': '_FSW_U2', '11': 'P12_VOUT', '12': 'P12_VOUT', '13': '+12V', '3': None, '4': None, '16': None,
                  '14': '_FB_U2', '15': '_COMP_U2', '8': '_SW1_U2', '20': '_BST1_U2', '19': '_BST2_U2', '10': '_SW2_U2',
                  '9': 'GND', '17': 'AGND_U2'}
    u2['fields'] = {**TPS552892, 'Note': (
        '+12V four-switch buck-boost (S9.0, SLVSGT7): 3-36 V in, average inductor limit 7-9 A, VREF 1.188-1.212 V, '
        '966 kHz (R110 20k), FPWM (MODE = VCC), internal LDO (EXTVCC = VCC), no dithering (DITH = GND), CDC open (no '
        'droop compensation), PG/CC open. Regulates 12.08 V from the whole 12.5-16.5 V converter input (buck, buck-boost '
        'and boost modes; the S8 TPS62933F buck needed 0.995-1.053 duty at low line against its 98 % maximum). EN/UVLO = '
        'MAIN_OK. Its output OVP (22.5-24.5 V) is not a 12 V protection: the U20 guard watches the rail')}
    cells = (('C6', 304.8, 1), ('C7', 314.96, 2), ('C77', 325.12, 3), ('C78', 335.28, 4))
    for ref, x, k in cells:
        note = f'U2 VIN ceramic {k} of 4 (TI: ~20 uF effective; 10u/50V 1206 at the 12.5-16.5 V input)'
        if ref in by:
            by[ref].update(at=(x, 52.07), rot=0)
            by[ref]['fields']['Note'] = note
        else:
            c.append(cap(ref, '10u', 'C1206', (x, 52.07), 'VIN', 'GND', Note=note))
    by['C8'].update(at=(345.44, 52.07), rot=0)
    by['C8']['fields']['Note'] = 'U2 VIN HF bypass at the VIN/PGND lands (TI 0.1 uF; contract <= 4.5 mm)'
    by['L1'].update(at=(381.0, 40.64), rot=90)
    by['L1']['pins'] = {'1': '_SW1_U2', '2': '_SW2_U2'}
    by['L1']['fields']['Note'] = ('Molded 10.8 x 10 mm, Isat 10 A, Irms 7 A, DCR 22 mOhm. S9.0: buck-boost inductor SW1-SW2, '
                                  '6.8 uH (TI 1-10 uH effective, inner loop needs > 1.2/fSW = 1.24 uH); ripple 0.49 A '
                                  'p-p at 16.5 V / 966 kHz, peak at the R109 limit 3.8 A')
    by['C10'].update(at=(375.92, 57.15), rot=180)
    by['C10']['pins'] = {'1': '_BST1_U2', '2': '_SW1_U2'}
    by['C10']['fields']['Note'] = 'U2 BOOT1 bootstrap (BOOT1-SW1), 0.1 uF (TI)'
    by['C9'].update(value='100n', at=(386.08, 57.15), rot=180)
    by['C9']['pins'] = {'1': '_BST2_U2', '2': '_SW2_U2'}
    by['C9']['fields'] = {**circuit45.CAPS[('100n', 'C0603')],
                          'Note': 'U2 BOOT2 bootstrap (BOOT2-SW2), 0.1 uF (TI). S8: the TPS62933F soft-start capacitor'}
    c.append(two('C82', 'C', '10u', 'C1206', (350.52, 85.09), '_VCC_U2', 'AGND_U2', **circuit45.CAPS[('10u', 'C1206')],
                 Note='U2 VCC LDO output, TI > 4.7 uF: 10u/50V 1206 keeps ~8 uF at 5.2 V bias. MODE and EXTVCC tie here '
                      '(FPWM, internal LDO)'))
    c.append(res('R110', '20k', (358.14, 92.71), '_FSW_U2', 'AGND_U2',
                 Note='U2 FSW: fSW = 1000 / (0.05 x 20000 + 35) MHz = 0.966 MHz (TI Eq. 3; 0.87-1.06 MHz screen); above '
                      'TI\'s <500 kHz high-power advice: thermal bench gate. R109 is a SLOW output CC loop, NOT a switch-current limit'))
    for i, ref in enumerate(('C81', 'C11', 'C12', 'C13', 'C14', 'C79', 'C80')):
        at = (round(403.86 + 10.16 * i, 2), 52.07)
        if ref == 'C81':
            c.append(cap(ref, '100n', 'C0603', at, 'P12_VOUT', 'GND',
                         Note='U2 VOUT HF bypass at the VOUT/PGND lands (TI 0.1 uF; contract <= 4.5 mm)'))
        elif ref in by:
            by[ref].update(at=at, rot=0)
            by[ref]['pins'] = {'1': 'P12_VOUT', '2': 'GND'}
            by[ref]['fields']['Note'] = 'U2 VOUT bank, 6 x 22u before the R109 sense resistor'
        else:
            c.append(cap(ref, '22u', 'C1206', at, 'P12_VOUT', 'GND',
                         Note='U2 VOUT bank, 6 x 22u before the R109 sense resistor'))
    c.append(two('R109', 'R', '0.018', 'WSLP1206', (474.98, 48.26), 'P12_VOUT', '+12V', rot=90, **R_SENSE,
                 Note='U2 output current limit ISP/ISN: VSNS 48-52 mV / 18 mR (1 % + 75 ppm) = 2.62-2.94 A constant-current '
                      'loop. Sets the +12V capability (rating basis) and charges rack capacitance without hiccup; FB '
                      'senses after it. 1 W part: <= 0.16 W at the limit; procurement/PCBA qualification OPEN (no invented C-code)'))
    by['R9'].update(value='7.5k', at=(408.94, 90.17), rot=0)
    by['R9']['pins'] = {'1': '_FB_U2', '2': 'AGND_U2'}
    by['R9']['fields'].update(LCSC=circuit45.R0603['7.5k'], MPN=circuit45.R_MPN['7.5k'],
                              Note='FB bottom: 1.2 V x (1 + 68k/7.5k) = 12.08 V nominal (11.54-12.65 V over VREF and 1 % '
                                   '+ 1 % TCR)')
    by['R8'].update(value='68k', at=(416.56, 86.36), rot=90)
    by['R8']['pins'] = {'1': '_FB_U2', '2': '+12V'}
    by['R8']['fields'].update(LCSC=circuit45.R0603['68k'], MPN=circuit45.R_MPN['68k'],
                              Note='FB top from the regulated side of R109 (CDC open: <= 0.3 uA x 68k = 20 mV)')
    c.append(res('R111', '6.8k', (398.78, 92.71), '_COMP_U2', '_COMPRC_U2',
                 Note='S9.1 COMP: R111 6.8k / C83 100n; full complex loop sweep incl. R109 and rack branch in calcs.json. '
                      'Published +12V rack envelope 0..0.44 mF; no arbitrary-impedance rack stability guarantee'))
    c.append(cap('C83', '100n', 'C0603', (398.78, 100.33), '_COMPRC_U2', 'AGND_U2',
                 Note='S9.1: 100n lowers the COMP zero to 234 Hz. Ground is the quiet AGND_U2 island, joined only at C82 via R113'))
    c.append(two('D26', 'D_Zener', 'SMBJ14A', 'SMB', (474.98, 69.85), 'P12_VOUT', 'GND', rot=270,
                 LCSC='', MPN='SMBJ14A', Manufacturer='Littelfuse',
                 Note='S9.1 U2 VOUT transient backstop: 14 V stand-off, breakdown 15.6-17.2 V, 23.2 V at 25.9 A, '
                      '600 W 10/1000 us. Absorbs VIN-bank energy after U20 opens U5; NOT a continuous rail crowbar. '
                      'Procurement/PCBA qualification OPEN.'))
    by['#FLG04'].update(at=(482.6, 48.26))


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

    # ---- S9.0 step 2: 15 V input (CH224A request, U5 UVLO) and the +12V four-switch buck-boost
    by['R1'].update(value='56k')
    by['R1']['fields'].update(LCSC=R0603_S9['56k'][0], MPN=R0603_S9['56k'][1],
                              Note='CFG1: 56k = 15 V request (WCH CH224 V2.0 Table 5-1; 120k = 20 V for the later retarget)')
    by['U1']['fields']['Note'] = ('Fixed 15 V request (S9.0), independently current-limited/zener-protected supply. Needs a '
                                  'source with a 15 V / 3 A fixed PDO (>= 45 W PD class). No current-contract tracking; PG is '
                                  'not a current guarantee')
    # S9.1: precision upper / principal lower, Basic 510R trim in series with R3.
    # Wider TPS16630 internal threshold tolerances prevent simultaneously guaranteeing <=13.0 V rising
    # and >=11.8 V falling with ANY passive divider (see calcs input_qualification).
    by['R2']['fields'].update(LCSC='C122538', MPN='RT0603BRD07100KL', Manufacturer='YAGEO',
                              Tolerance='0.1%', TCR='25ppm', Note='S9.1 UVLO top, precision 100k; senses own VPD before D10')
    by['R3'].update(value='10k')
    by['R3']['pins']['2'] = 'UV_TRIM'
    by['R3']['fields'].update(LCSC='C95204', MPN='RT0603BRD0710KL', Manufacturer='YAGEO',
                              Tolerance='0.1%', TCR='25ppm', Note='S9.1 UVLO bottom: 10k precision + R114 510R Basic in series')
    c.append(two('R114', 'R', '510', 'R0603', (154.94, 134.62), 'UV_TRIM', 'GND',
                 LCSC='C23193', MPN='0603WAF5100T5E', Manufacturer=UNIROYAL, Tolerance='1%', TCR='100ppm',
                 Note='S9.1 UVLO trim; do not bypass. Worst-case turn-on <13.0 V; calcs includes all three resistor corners'))
    _plus12_buckboost(c, by)
    by['U5']['fields']['Note'] = ('S9.1 common input switch, SHDN = RUN. UVLO R2 100k precision / '
        '(R3 10k precision + R114 510R): <13.0 V worst-case start. OVP unchanged (24.1 V nominal). '
        'FLT/PGOOD = MAIN_OK. U4 independently requires RUN AND MAIN_LED_OK and derives EN drive from own VPD.')
    by['U18']['pins']['3'] = 'VPD'
    by['C57']['pins']['1'] = 'VPD'
    by['C57']['fields']['Note'] = 'U18 always-on VPD bypass, 50 V rated; logic outputs still pull up to V3V3'
    by['U4']['fields']['Note'] = by['U4']['fields']['Note'].replace(
        'Pins 1 and pad are the -12V node, not GND.', 'Pins 1 and pad are the delivered -12V node (S8: no '
        'series switch), not GND; 18 ms OCP blanking at start-up charges the rack capacitance.')
    # S9.1 C1: NO output-derived enable supply. VPD is upstream of reverse-blocking D10.
    # Q14/Q15 form a series AND sink: RUN AND MAIN_LED_OK. R112 holds Q1 off if either is off.
    by['Q1']['pins']['2'] = 'VPD'
    by['Q1']['pins']['1'] = 'N_EN_BASE'
    by['R16']['pins']['2'] = 'N_EN_BASE'
    by['Q1']['fields']['Note'] = ('S9.1: emitter = own VPD, NOT +12V or VIN. Q14/Q15 qualify base sink with RUN AND '
        'MAIN_LED_OK (MAIN_OK AND V20_OK); R112 pulls base to emitter when disabled. Bus alone cannot enable U4.')
    by['R16'].update(value='33k')
    by['R16']['fields'].update(LCSC=circuit45.R0603['33k'], MPN=circuit45.R_MPN['33k'])
    by['R16']['pins']['1'] = 'N_EN_SINK'
    by['R16']['fields']['Note'] = 'Q1 base sink through BOTH Q14 (RUN) and Q15 (MAIN_LED_OK); never direct to GND'
    c.append(res('R112', '5.1k', (66.04, 269.24), 'VPD', 'N_EN_BASE',
                 Note='S9.1 Q1 base-emitter pull-up; off-state leakage cannot turn on Q1'))
    for ref, gate, source, drain, at in (
            ('Q14', 'RUN', 'GND', 'N_EN_RETURN', (45.72, 269.24)),
            ('Q15', 'MAIN_LED_OK', 'N_EN_RETURN', 'N_EN_SINK', (45.72, 246.38))):
        c.append(part(ref, '2N7002', '2N7002', 'SOT23', at, 0,
                      {'1': gate, '2': source, '3': drain}, **{k:v for k,v in by['Q10']['fields'].items() if k != 'Note'},
                      Note='S9.1 U4 enable qualification, series NMOS sink; no output-rail gate or supply'))
    c.append(two('R113', 'R', '0', 'R0603', (350.52, 105.41), 'AGND_U2', 'GND',
                 LCSC='C21189', MPN='0603WAF0000T5E', Manufacturer=UNIROYAL,
                 Note='ONLY AGND_U2/PGND connection, at C82 ground terminal. Route no other bridge; 3-4 GND vias at C82'))
    c.append(part('#FLG10', 'PWR_FLAG', 'PWR_FLAG', None, (340.36, 105.41), 0, {'1':'AGND_U2'},
                  Note='Ground supplied through populated R113 0R; not an independent supply'))
    c.append(two('D24', 'D_Zener', 'SMBJ16A', 'SMB', (330.2, 119.38), 'VIN', 'GND', rot=270,
                 LCSC='C151254', MPN='SMBJ16A', Manufacturer='Littelfuse',
                 Note='S9.1 VIN TVS: 16 V stand-off, 17.8-19.7 V breakdown, 26 V at 23.1 A (600 W 10/1000 us). '
                      'Finite bus-injection pulses ONLY, not continuous reverse-power absorption. 20 V retarget must change D24.'))
    c.append(part('D25', 'BAT54S', 'BAT54SLT1G', 'SOT23', (355.6, 119.38), 0,
                  {'1':'GND', '2':'VIN', '3':'VIN'}, LCSC='C19726', MPN='BAT54SLT1G', Manufacturer='onsemi',
                  Note='S9.1 low-current VIN negative clamp for slew-limited bus tests: VF <=0.24 V at <=0.1 mA, 25 C. '
                       'Not a hard-hotplug/cold absolute-minimum guarantee; 30 V reverse rating. 20 V retarget changes D25.'))
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
    # ---- S8.5 (B): V20_OK is a U5 status-validity floor, not an input-good threshold (the U5 UVLO is). S9.0: 100k.
    by['R83'].update(value='100k')
    by['R83']['fields'].update(LCSC=circuit45.R0603['100k'], MPN=circuit45.R_MPN['100k'],
                               Note='MON_20 top. S9.0: 100k (S8.5 120k at 20 V): V20_OK = VPD > 7.67-9.27 V (8.44 V nominal), '
                                    'above the PD 5 V phase where U5 FLT/PGOOD may be undefined and below the U5 turn-off '
                                    'minimum (11.55 V), so it validates MAIN_OK and never drops first while U5 is on. Not an '
                                    'input-good threshold: the input qualification is the U5 UVLO. Net name kept from S7')
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
    redrawn = {'U2', 'L1', 'R8', 'R9', *(f'C{i}' for i in range(6, 15))}      # S9.0 step 2: +12V cell redrawn below
    gone = set(S8_REMOVED) | set(S9_REMOVED) | {'R35', 'R62'} | redrawn   # moved refs: S7 lines at their old spots

    def ref_of(pt):
        if isinstance(pt, str):
            return pt.split('.')[0]
        if isinstance(pt[0], str):
            return pt[0].split('.')[0]
        return None

    def in_box(pt, box):
        (bx0, bx1), (by0, by1) = box
        return not isinstance(pt, str) and not isinstance(pt[0], str) and bx0 <= pt[0] <= bx1 and by0 <= pt[1] <= by1

    def removed_block(pt):
        return in_box(pt, U3_BLOCK) or in_box(pt, U2_BLOCK)
    W = [w for w in W if not any(ref_of(pt) in gone for pt in w) and not all(removed_block(pt) for pt in w)
         and not any(pt in ('J2.11', 'J2.12') for pt in w)]
    P = [(NET_RENAME.get(n, n), pt, rot) for n, pt, rot in P
         if ref_of(pt) not in gone and not removed_block(pt) and n != '+5V']
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
    # S9.0 step 2: +12V buck-boost cell (U2 TPS552892-Q1, circuit_s8._plus12_buckboost). VIN rail with the four 10u + 100n;
    # L1 above the IC between SW1 and SW2 with the BOOT capacitors on BOOT1/BOOT2; MODE/EXTVCC/VCC one node with C82; FSW
    # to R110; the VOUT/ISP node rises to the output bank rail ending in the R109 sense resistor; FB divider and COMP
    # network bottom-right. ISN (Kelvin to +12V) and DITH (GND) use the automatic rail stubs.
    W += [[(297.18, 48.26), (355.6, 48.26), (355.6, 66.04), 'U2.7'],
          ['U2.8', (373.38, 40.64), 'L1.1'], ['U2.10', (388.62, 40.64), 'L1.2'], ['C10.2', (373.38, 53.34)], ['C9.2', (388.62, 53.34)],
          ['U2.2', (363.22, 76.2), (363.22, 81.28), 'U2.18'], ['U2.21', (363.22, 78.74)], [(363.22, 81.28), 'C82.1'],
          ['U2.6', 'R110.1'],
          ['U2.11', (398.78, 66.04)], ['U2.12', (398.78, 68.58), (398.78, 66.04), (398.78, 48.26), 'R109.1'],
          ['R109.2', (487.68, 48.26)],
          ['U2.14', 'R9.1'], ['R9.1', 'R8.1'], ['U2.15', 'R111.1']]
    P += [('VIN', (297.18, 48.26), 90), ('+12V', (487.68, 48.26), 270)]
    L += [('P12_VOUT', (467.36, 48.26), 'U')]
    return W, P, L


TEXTS = []   # page notes live in tools/hierarchy_s8.py; the flat intermediate is replaced by the root
