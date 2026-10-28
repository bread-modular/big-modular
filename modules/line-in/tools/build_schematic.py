"""Generate the S2 LINE IN schematic (hardware/line-in.kicad_sch) and its pinned symbols.

Run from modules/line-in:
  python3 -B tools/build_schematic.py

Writes hardware/LineIn.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the LineIn library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() below is the
circuit intent of docs/research.md section 3 (pin -> net); wiring() draws it as wires,
stock power symbols (GND/+12V/-12V, global nets) and one local label per signal net.
build() exports the native netlist and asserts it equals circuit(), so a misdrawn wire
fails the build. Multi-unit symbols (the TL072s) are placed one instance per unit.
The generic part of this script (symbol pinning, wire splitting, junctions, netlist
check) is modules/imix's.

The PCB never reads this table: tools/build_layout.py takes nets, values and
footprints from the native netlist that kicad-cli exports from this schematic.
"""
import copy
import hashlib
import json
import math
import subprocess
import uuid
from pathlib import Path

from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
STOCK = Path('/usr/share/kicad/symbols')
PROJECT = 'line-in'
LIBNAME = 'LineIn'

# Footprint filters of these stock symbols are qualified with stock library names;
# the pinned footprints live in the LineIn library, so the copies drop the library part.
FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'AudioJack3': ('Connector_Audio', 'AudioJack3'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'SOD123': 'D_SOD-123', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'RV09': 'Potentiometer_RV09', 'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'PJ366ST': 'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical',
    'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
}


def part(ref, sym, value, fp, at, rot, pins, unit=1, mirror=None, text=None, **fields):
    assert mirror is None or rot == 0, (ref, 'mirror only with rot 0')
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit,
                mirror=mirror, text=text, fields=fields)


PWR = []  # running #PWR numbering


def psym(c, net, at, rot=0):
    """Stock power symbol (GND / +12V / -12V) with its pin at `at`.
    GND: rot 0 points down, 90 right, 270 left. +12V: rot 0 up. -12V: rot 180 down."""
    PWR.append(net)
    c.append(part(f'#PWR{len(PWR):02d}', net, net, None, (r(at[0]), r(at[1])), rot, {'1': net}))


C_RIGHT = ((3.81, -1.27), (3.81, 1.27))    # texts beside a vertical part, right
R_LEFT = ((-3.81, -1.27), (-3.81, 1.27))   # ... left
FB_TEXT = ((0, -2.54), (0, 2.54))          # texts above/below a horizontal feedback resistor
CF_TEXT = ((0, -3.81), (0, 3.81))          # ... and its feedback capacitor
CF = 16.51                                 # feedback capacitor height above the input line
OPAMP_TEXT = ((0, 7.62), (0, 10.16))       # op-amp unit texts below the body
ROW = {'L': 129.54, 'R': 180.34}           # channel signal lines (pot pin 3 / IN wire)
JIN = (30.48, 154.94)                      # J1 (stereo IN) between the rows
TAP = 142.24                               # mono taps on the GAIN lines
YS = 158.75                                # mono summer inverting-input line
# Channel -> (index, op-amp). Bread Modular line_in: U1 left, U2 right, U3 mono.
CH = {'L': (0, 'U1'), 'R': (1, 'U2')}
POTNOTE = ('RV09 50k linear (user stock: no bushing, 16 mm knurled shaft) on the Bread Modular '
           'RV09 footprint, hand-soldered. Pin 3 (CW) = jack, pin 1 (CCW) = GND, wiper = level')


def circuit():
    PWR.clear()
    c = []
    # ---- Power (modules/imix): Eurorack +/-12 V -> series Schottky per rail -> +12V / -12V.
    # J10 is drawn rotated 180 so +12 V (pins 9/10) is on top and -12 V (pins 1/2) below.
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (45.72, 58.42), 180,
                  {'1': '-12V_IN', '2': '-12V_IN', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V_IN', '10': '+12V_IN'},
                  Note='Unshrouded vertical 2x5 header, pin 1 (-12 V) at the board bottom; '
                       '10-pin cable (as modules/audio-out)'))
    psym(c, 'GND', (33.02, 59.69), 270)
    psym(c, 'GND', (55.88, 59.69), 90)
    c.append(part('D1', 'D_Schottky', 'B5819W', 'SOD123', (71.12, 45.72), 180,
                  {'1': '+12V', '2': '+12V_IN'}, Note='Series reverse-polarity protection, +12 V rail'))
    c.append(part('D2', 'D_Schottky', 'B5819W', 'SOD123', (71.12, 71.12), 0,
                  {'1': '-12V_IN', '2': '-12V'}, Note='Series reverse-polarity protection, -12 V rail'))
    c.append(part('C1', 'C', '10u', 'C0805', (86.36, 49.53), 0, {'1': '+12V', '2': 'GND'},
                  text=C_RIGHT, Voltage='25V', Note='+12 V bulk'))
    c.append(part('C2', 'C', '10u', 'C0805', (86.36, 67.31), 0, {'1': 'GND', '2': '-12V'},
                  text=C_RIGHT, Voltage='25V', Note='-12 V bulk'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (91.44, 58.42), 0, {'1': 'GND'}))
    psym(c, 'GND', (91.44, 58.42))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (96.52, 45.72), 0, {'1': '+12V'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (96.52, 71.12), 0, {'1': '-12V'}))
    psym(c, '+12V', (106.68, 45.72))
    psym(c, '-12V', (106.68, 71.12), 180)
    # One 100n per supply pin, at each op-amp (C3..C8).
    for i, (u, x) in enumerate((('U1', 124.46), ('U2', 162.56), ('U3', 200.66))):
        c.append(part(u, 'TL072', 'TL072CDT', 'SOIC8', (x, 58.42), 0,
                      {'4': '-12V', '8': '+12V'}, unit=3, text=((-6.35, -1.27), (-6.35, 1.27)),
                      Note='Dual JFET op-amp on +/-12 V (after D1/D2)'))
        c.append(part(f'C{3 + 2 * i}', 'C', '100n', 'C0603', (x + 10.16, 49.53), 0, {'1': '+12V', '2': 'GND'},
                      text=C_RIGHT, Voltage='50V', Note=f'{u} V+ (pin 8) decoupling'))
        c.append(part(f'C{4 + 2 * i}', 'C', '100n', 'C0603', (x + 10.16, 67.31), 0, {'1': 'GND', '2': '-12V'},
                      text=C_RIGHT, Voltage='50V', Note=f'{u} V- (pin 4) decoupling'))
        psym(c, 'GND', (x + 15.24, 58.42))

    # ---- Stereo input: one TRS jack, tip = left, ring = right, sleeve = GND.
    c.append(part('J1', 'AudioJack3', 'PJ366ST', 'PJ366ST', JIN, 0,
                  {'T': 'IN_L', 'R': 'IN_R', 'S': 'GND'}, mirror='x',
                  Note='Stereo line input (TRS: tip L, ring R); a mono TS plug grounds the ring, so R stays silent'))
    psym(c, 'GND', (JIN[0] + 7.62, JIN[1] + 2.54))

    # ---- Channels (Bread Modular line_in topology on +/-12 V, ground-referenced):
    # jack -> RV (50k level, pin 3) -> wiper -> 1u -> 1M to GND -> follower ->
    # 5.1k -> inverting gain (100k || 20p, x-19.6, Doepfer A-119 style x20) -> 1k -> OUT jack.
    for ch, y in ROW.items():
        n, u = CH[ch]
        c.append(part(f'RV{1 + n}', 'R_Potentiometer', '50k', 'RV09', (55.88, y + 3.81), 0,
                      {'3': f'IN_{ch}', '1': 'GND', '2': f'LVL_{ch}'}, mirror='x',
                      Taper='B (linear)', Note=f'LEVEL {ch}: ' + POTNOTE))
        psym(c, 'GND', (55.88, y + 7.62))
        c.append(part(f'C{9 + n}', 'C', '1u', 'C0805', (68.58, y + 3.81), 90,
                      {'1': f'LVL_{ch}', '2': f'AC_{ch}'}, text=FB_TEXT, Voltage='25V',
                      Note=f'{ch} input coupling (BM 100n; 1u with 1M: 0.16 Hz corner, less signal across the X7R)'))
        c.append(part(f'R{1 + n}', 'R', '1M', 'R0603', (77.47, y + 8.89), 0,
                      {'1': f'AC_{ch}', '2': 'GND'}, text=R_LEFT,
                      Note=f'{ch} follower bias to GND (BM: to V_MID)'))
        psym(c, 'GND', (77.47, y + 12.7))
        c.append(part(u, 'TL072', 'TL072CDT', 'SOIC8', (88.9, y + 1.27), 0,
                      {'2': f'BUF_{ch}', '3': f'AC_{ch}', '1': f'BUF_{ch}'}, unit=1, mirror='x',
                      text=OPAMP_TEXT, Note=f'{ch} input follower'))
        c.append(part(f'R{3 + n}', 'R', '5.1k', 'R0603', (106.68, y + 1.27), 90,
                      {'1': f'BUF_{ch}', '2': f'INV_{ch}'}, Note=f'{ch} gain input resistor (BM 22k): gain -100k/5.1k = -19.6 (S2, user: x20 as Doepfer A-119)'))
        c.append(part(u, 'TL072', 'TL072CDT', 'SOIC8', (127.0, y + 3.81), 0,
                      {'6': f'INV_{ch}', '5': 'GND', '7': f'GAIN_{ch}'}, unit=2, mirror='x',
                      text=OPAMP_TEXT, Note=f'{ch} inverting gain stage'))
        psym(c, 'GND', (116.84, y + 6.35))
        c.append(part(f'R{5 + n}', 'R', '100k', 'R0603', (127.0, y - 6.35), 90,
                      {'1': f'INV_{ch}', '2': f'GAIN_{ch}'}, text=FB_TEXT, Note=f'{ch} gain feedback'))
        c.append(part(f'C{11 + n}', 'C', '20p', 'C0603', (127.0, y - CF), 90,
                      {'1': f'INV_{ch}', '2': f'GAIN_{ch}'}, text=CF_TEXT, Voltage='50V',
                      Note=f'{ch} HF roll-off / stability (~80 kHz with 100k)'))
        c.append(part(f'R{7 + n}', 'R', '1k', 'R1206', (149.86, y + 3.81), 90,
                      {'1': f'GAIN_{ch}', '2': f'OUT_{ch}'},
                      Note='Output series / short-circuit and mis-patch protection; 1206 0.5 W '
                           '(~0.5 W with a -12 V source against +10.5 V)'))
        c.append(part(f'J{2 + n}', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (167.64, y + 3.81), 180,
                      {'T': f'OUT_{ch}', 'S': 'GND', 'TN': None}, Note=f'OUT {ch}'))
        psym(c, 'GND', (160.02, y + 6.35))

    # ---- Mono: U3A inverting summer of the two op-amp outputs (BM sums after the 1k),
    # gain -51k/100k per side -> 1k -> MONO jack. U3B unused (BM leaves it floating).
    c.append(part('R9', 'R', '100k', 'R0603', (190.5, 149.86), 90, {'1': 'GAIN_L', '2': 'SUM'},
                  Note='Mono summing resistor, left'))
    c.append(part('R10', 'R', '100k', 'R0603', (190.5, 167.64), 90, {'1': 'GAIN_R', '2': 'SUM'},
                  Note='Mono summing resistor, right'))
    c.append(part('U3', 'TL072', 'TL072CDT', 'SOIC8', (215.9, YS + 2.54), 0,
                  {'2': 'SUM', '3': 'GND', '1': 'MIX'}, unit=1, mirror='x',
                  text=OPAMP_TEXT, Note='Mono inverting summer'))
    psym(c, 'GND', (205.74, YS + 5.08))
    c.append(part('R11', 'R', '51k', 'R0603', (215.9, YS - 6.35), 90,
                  {'1': 'SUM', '2': 'MIX'}, text=FB_TEXT, Note='Mono feedback: -0.51 per side'))
    c.append(part('C13', 'C', '20p', 'C0603', (215.9, YS - CF), 90,
                  {'1': 'SUM', '2': 'MIX'}, text=CF_TEXT, Voltage='50V', Note='Mono HF roll-off / stability'))
    c.append(part('R12', 'R', '1k', 'R1206', (236.22, YS + 2.54), 90, {'1': 'MIX', '2': 'MONO'},
                  Note='Output series / short-circuit and mis-patch protection; 1206 0.5 W'))
    c.append(part('J4', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (256.54, YS + 2.54), 180,
                  {'T': 'MONO', 'S': 'GND', 'TN': None}, Note='MONO out'))
    psym(c, 'GND', (248.92, YS + 5.08))
    c.append(part('U3', 'TL072', 'TL072CDT', 'SOIC8', (215.9, YS + 25.4), 0,
                  {'6': 'SPARE', '5': 'GND', '7': 'SPARE'}, unit=2, mirror='x',
                  text=OPAMP_TEXT, Note='Unused section, tied off as a grounded follower'))
    psym(c, 'GND', (205.74, YS + 27.94))
    for p in c:
        if p['ref'].startswith('#'):
            continue
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def wiring():
    """Wire polylines and one label per signal net (keeps the native net names).
    build() splits T-joints, adds junction dots and checks the native netlist."""
    w, lab = [], []
    # Power entry (modules/imix): J10 GND pins bussed per side, +12V_IN / -12V_IN pin pairs joined.
    for x0, x1, xg in ((38.1, 35.56, 33.02), (50.8, 53.34, 55.88)):
        w += [[(x0, yy), (x1, yy)] for yy in (55.88, 58.42, 60.96)]
        w += [[(x1, 55.88), (x1, 60.96)], [(x1, 59.69), (xg, 59.69)]]  # tap off-row: no 4-way
    w += [[(38.1, 53.34), (30.48, 53.34), (30.48, 45.72), (67.31, 45.72)],
          [(50.8, 53.34), (60.96, 53.34), (60.96, 45.72)],
          [(38.1, 63.5), (30.48, 63.5), (30.48, 71.12), (67.31, 71.12)],
          [(50.8, 63.5), (60.96, 63.5), (60.96, 71.12)]]
    lab += [('+12V_IN', (40.64, 45.72), 0), ('-12V_IN', (40.64, 71.12), 0)]
    # Rails, bulk caps, and each op-amp's supply pins with their decoupling pair.
    w += [[(74.93, 45.72), (210.82, 45.72)], [(74.93, 71.12), (210.82, 71.12)],
          [(86.36, 53.34), (86.36, 63.5)], [(86.36, 58.42), (91.44, 58.42)]]
    for x in (124.46, 162.56, 200.66):
        xc = x + 10.16
        w += [[(xc, 53.34), (xc, 63.5)], [(xc, 58.42), (xc + 5.08, 58.42)],
              [(x - 2.54, 45.72), (x - 2.54, 50.8)], [(x - 2.54, 66.04), (x - 2.54, 71.12)]]
    # Stereo jack: tip up to the L row, ring down to the R row, sleeve to GND.
    jx, jy = JIN
    yl, yr = ROW['L'], ROW['R']
    w += [[(jx + 5.08, jy - 2.54), (jx + 10.16, jy - 2.54), (jx + 10.16, yl), (55.88, yl)],
          [(jx + 5.08, jy), (jx + 12.7, jy), (jx + 12.7, yr), (55.88, yr)],
          [(jx + 5.08, jy + 2.54), (jx + 7.62, jy + 2.54)]]
    # Channels: pot -> coupling cap -> follower (loop above) -> 10k -> inverting gain
    # (feedback loop above) -> 1k -> OUT jack; GAIN tapped at TAP for the mono summer.
    for ch, y in ROW.items():
        w += [[(59.69, y + 3.81), (64.77, y + 3.81)],                                     # LVL
              [(72.39, y + 3.81), (81.28, y + 3.81)], [(77.47, y + 3.81), (77.47, y + 5.08)],  # AC
              [(81.28, y - 1.27), (78.74, y - 1.27), (78.74, y - 6.35), (99.06, y - 6.35),
               (99.06, y + 1.27)],                                                         # follower loop
              [(96.52, y + 1.27), (102.87, y + 1.27)],                                    # BUF
              [(110.49, y + 1.27), (119.38, y + 1.27)],                                   # INV
              [(119.38, y + 6.35), (116.84, y + 6.35)],
              [(114.3, y + 1.27), (114.3, y - CF)],
              [(114.3, y - 6.35), (123.19, y - 6.35)], [(114.3, y - CF), (123.19, y - CF)],
              [(130.81, y - 6.35), (137.16, y - 6.35)],
              [(130.81, y - CF), (137.16, y - CF), (137.16, y + 3.81)],
              [(134.62, y + 3.81), (146.05, y + 3.81)],                                   # GAIN
              [(153.67, y + 3.81), (162.56, y + 3.81)],                                   # OUT
              [(162.56, y + 6.35), (160.02, y + 6.35)]]
        lab += [(f'IN_{ch}', (45.72, y), 0), (f'LVL_{ch}', (60.96, y + 3.81), 0),
                (f'AC_{ch}', (73.66, y + 3.81), 0), (f'BUF_{ch}', (100.33, y + 1.27), 0),
                (f'INV_{ch}', (111.76, y + 1.27), 0), (f'GAIN_{ch}', (138.43, y + 3.81), 0),
                (f'OUT_{ch}', (154.94, y + 3.81), 0)]
    w += [[(TAP, yl + 3.81), (TAP, 149.86), (186.69, 149.86)],
          [(TAP, yr + 3.81), (TAP, 167.64), (186.69, 167.64)]]
    # Mono: summing bus -> U3A(-), R11 || C13 feedback, (+) to GND, R12 -> J4.
    w += [[(194.31, 149.86), (198.12, 149.86), (198.12, 167.64), (194.31, 167.64)],
          [(198.12, YS), (208.28, YS)],
          [(203.2, YS), (203.2, YS - CF)],
          [(203.2, YS - 6.35), (212.09, YS - 6.35)], [(203.2, YS - CF), (212.09, YS - CF)],
          [(219.71, YS - 6.35), (228.6, YS - 6.35)],
          [(219.71, YS - CF), (228.6, YS - CF), (228.6, YS + 2.54)],
          [(223.52, YS + 2.54), (232.41, YS + 2.54)],
          [(208.28, YS + 5.08), (205.74, YS + 5.08)],
          [(240.03, YS + 2.54), (251.46, YS + 2.54)],
          [(251.46, YS + 5.08), (248.92, YS + 5.08)]]
    lab += [('SUM', (199.39, YS), 0), ('MIX', (224.79, YS + 2.54), 0), ('MONO', (241.3, YS + 2.54), 0)]
    # U3B tie-off: output -> (-), (+) -> GND.
    w += [[(223.52, YS + 25.4), (226.06, YS + 25.4), (226.06, YS + 17.78), (205.74, YS + 17.78),
           (205.74, YS + 22.86), (208.28, YS + 22.86)],
          [(208.28, YS + 27.94), (205.74, YS + 27.94)]]
    lab.append(('SPARE', (210.82, YS + 17.78), 0))
    w = [[(r(x), r(y)) for x, y in line] for line in w]
    lab = [(n, (r(x), r(y)), a) for n, (x, y), a in lab]
    return [(a, b) for line in w for a, b in zip(line, line[1:])], lab


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Reused from modules/imix, audio-out and acid (their live strict lookups); re-audit
# before export. All Basic except the ROHM ESR18 1206 1k (Extended, as acid).
# The THT jacks, pots and header are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '1M', 'R0603'): dict(LCSC='C22935', MPN='0603WAF1004T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0603'): dict(LCSC='C23186', MPN='0603WAF5101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM'),
    ('C', '20p', 'C0603'): dict(LCSC='C1648', MPN='CL10C200JB8NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('TL072', 'TL072CDT', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
}


# Reference / value text offsets from the symbol origin (default: just above/below).
TEXT_AT = {
    'J10': ((-1.27, -8.89), (-1.27, 8.89)),
    'TL072': ((0, -7.62), (0, 7.62)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 8.89)),
    'AudioJack3': ((0, -6.35), (0, 6.35)),
    'R_Potentiometer': ((-5.08, -1.27), (-5.08, 1.27)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '+12V': ((0, -6.35), (0, -3.81)),
    '-12V': ((0, 6.35), (0, 3.81)),
}
SHOW_VALUE = {'+12V', '-12V'}  # power symbols whose value text is drawn

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR LINE IN - S2 schematic: stereo line input to Eurorack level '
                     '(Bread Modular line_in on +/-12 V). Circuit intent: docs/research.md', 2.0),
    ((20.32, 33.02), 'POWER: Eurorack +12V / -12V -> B5819W per rail -> +12V / -12V (about +/-11.6 V). J10 +5V unused.\n'
                     'C3..C8: 100n at every op-amp supply pin; C1/C2: 10u bulk.', 1.4),
    ((20.32, 86.36), 'PWR_FLAG: #FLG01 marks the Eurorack GND; #FLG02/#FLG03 mark the +12V/-12V rails,\n'
                     'fed from the header only through D1/D2, which ERC cannot see through.', 1.1),
    ((20.32, 96.52), 'CHANNELS L/R (Bread Modular line_in, ground-referenced): J1 tip/ring -> 50k LEVEL pot -> 1u -> 1M bias\n'
                     '-> follower -> 5.1k -> inverting gain (100k || 20p) = -19.6 (~x20, Doepfer A-119) -> 1k -> OUT jack.\n'
                     'Consumer line (-10 dBV, 0.9 Vpp) reaches ~10 Vpp near half LEVEL; hotter sources: turn LEVEL down.', 1.4),
    ((190.5, 118.11), 'MONO: U3A sums the two gain-stage outputs (before the 1k, so a load on OUT L/R\n'
                      'does not move MONO): MONO = -0.51 x (GAIN_L + GAIN_R) = +10 x (L + R) at the inputs.\n'
                      'OUT L/R are inverted (BM topology); MONO is in phase. U3B unused: grounded follower.', 1.4),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/{PROJECT}/schematic/' + key))


def stock_symbol(lib, name):
    tree = parse((STOCK / f'{lib}.kicad_sym').read_text())
    syms = {s[1]: s for s in nodes(tree, 'symbol')}
    sym = copy.deepcopy(syms[name])
    ext = one(sym, 'extends')
    if ext:  # flatten: parent body/pins, child properties
        parent = copy.deepcopy(syms[ext[1]])
        props = {p[1]: p for p in nodes(sym, 'property')}
        for i, item in enumerate(parent):
            if isinstance(item, list) and item[0] == 'property' and item[1] in props:
                parent[i] = props.pop(item[1])
            elif isinstance(item, list) and item[0] == 'symbol':
                item[1] = item[1].replace(ext[1], name, 1)
        parent[1] = name
        insert = max(i for i, item in enumerate(parent) if isinstance(item, list) and item[0] == 'property') + 1
        parent[insert:insert] = list(props.values())
        sym = parent
    return sym, (STOCK / f'{lib}.kicad_sym'), ext[1] if ext else None


def pin_table(sym, unit):
    """Pins of one unit: sub-symbols NAME_<unit>_<style>, plus the common NAME_0_<style>."""
    out = {}
    for sub in nodes(sym, 'symbol'):
        u = int(sub[1].rsplit('_', 2)[1])
        if u not in (0, unit):
            continue
        for p in walk(sub, 'pin'):
            at = one(p, 'at')
            out[one(p, 'number')[1]] = (float(at[1]), float(at[2]), float(at[3]), p[1])
    return out


def xform(px, py, rot, mirror=None):
    """Library XY (Y up) -> schematic offset (Y down) for a CCW symbol rotation;
    `(mirror x)` (rot 0 only) flips about the horizontal axis."""
    x, y = px, (py if mirror == 'x' else -py)
    a = math.radians(rot)
    return (round(x * math.cos(a) + y * math.sin(a), 4), round(-x * math.sin(a) + y * math.cos(a), 4))


def on_seg(pt, a, b):
    """pt strictly inside the axis-aligned segment a-b."""
    (x, y), (x1, y1), (x2, y2) = pt, a, b
    if x1 == x2 == x:
        return min(y1, y2) < y < max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) < x < max(x1, x2)
    return False


def split(segs, points):
    """Split segments at any wire end, pin or label lying strictly inside them."""
    for a, b in segs:
        assert a[0] == b[0] or a[1] == b[1], ('diagonal wire', a, b)
        assert a != b, ('zero-length wire', a)
    out = list(segs)
    for pt in points:
        nxt = []
        for a, b in out:
            nxt += [(a, pt), (pt, b)] if on_seg(pt, a, b) else [(a, b)]
        out = nxt
    return out


def netlist_nets(sch):
    """{net name: {ref/pin}} from the native kicad-cli netlist, power/flag refs dropped."""
    tmp = MODULE / 'research' / 'schematic-netlist.net'
    tmp.parent.mkdir(exist_ok=True)
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', str(tmp), str(sch)], check=True,
                   stdout=subprocess.DEVNULL)
    out = {}
    for net in walk(parse(tmp.read_text()), 'net'):
        refs = {f"{one(nd, 'ref')[1]}/{one(nd, 'pin')[1]}" for nd in nodes(net, 'node')
                if not one(nd, 'ref')[1].startswith('#')}
        if refs:
            out[one(net, 'name')[1].lstrip('/')] = refs
    return out


def r(v):
    return round(v, 2)


def build():
    lib_syms, sources = {}, {}
    for key, (lib, name) in SYMBOLS.items():
        sym, src, parent = stock_symbol(lib, name)
        edit = None
        if key in FILTER_EDITS:
            prop = next(pp for pp in nodes(sym, 'property') if pp[1] == 'ki_fp_filters')
            edit = f'ki_fp_filters {prop[2]!r} -> {FILTER_EDITS[key]!r}'
            prop[2] = FILTER_EDITS[key]
        lib_syms[key] = sym
        sources[key] = {'library': f'{lib}:{name}', 'source': str(src).replace(str(Path.home()), '~', 1),
                        'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                        'flattened_from': parent, 'edits': edit}
    # Local pinned symbol library (names unprefixed inside the library file).
    stock_header = parse((STOCK / 'Device.kicad_sym').read_text())
    lib = [atom('kicad_symbol_lib'), one(stock_header, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(lib_syms[k]) for k in sorted(lib_syms)]
    (HW / f'{LIBNAME}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIBNAME}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIBNAME}.kicad_sym") '
        '(options "") (descr "LINE IN module pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - LINE IN") (rev "S2") (company "Big Modular")
        (comment 1 "S2 - stereo line in, OUT L/R + MONO, +/-12 V, 4HP - not released")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIBNAME}:' + k
        embedded.append(s)

    items, nets, pin_pts = [], {}, []
    segs, labels = wiring()
    for p in circuit():
        sym = lib_syms[p['sym']]
        unit = p['unit']
        pins = pin_table(sym, unit)
        assert set(p['pins']) == set(pins), (p['ref'], unit, sorted(pins), sorted(p['pins']))
        x, y = p['at']
        is_flag = p['ref'].startswith('#')
        dr, dv = p['text'] or TEXT_AT.get(p['ref'], TEXT_AT.get(p['sym'], ((0, -3.81), (0, 3.81))))
        props = [('Reference', p['ref'], (x + dr[0], y + dr[1]), is_flag),
                 ('Value', p['value'], (x + dv[0], y + dv[1]), is_flag and p['sym'] not in SHOW_VALUE),
                 ('Footprint', f"{LIBNAME}:{FP[p['fp']]}" if p['fp'] else '', (x, y), True),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''), (x, y), True),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''), (x, y), True)]
        props += [(k, v, (x, y), True) for k, v in p['fields'].items()]
        fang = 90 if p['rot'] in (90, 270) else 0
        key = p['ref'] if unit == 1 else f"{p['ref']}/u{unit}"
        node = [atom('symbol'), [atom('lib_id'), f'{LIBNAME}:' + p['sym']], [atom('at'), x, y, p['rot']]]
        if p['mirror']:
            node.append([atom('mirror'), atom(p['mirror'])])
        node += [[atom('unit'), unit], [atom('exclude_from_sim'), atom('no')],
                 [atom('in_bom'), atom('no' if is_flag else 'yes')],
                 [atom('on_board'), atom('no' if is_flag else 'yes')],
                 [atom('in_pos_files'), atom('no' if is_flag else 'yes')], [atom('dnp'), atom('no')],
                 [atom('uuid'), uid('sym/' + key)]]
        for name, value, (px, py), hide in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), fang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{key}/{n}")]] for n in sorted(pins)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), unit]]]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, py, p['rot'], p['mirror'])
            ex, ey = r(x + ox), r(y + oy)
            pin_pts.append((ex, ey))
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid(f"nc/{p['ref']}/{n}")]])
            elif not is_flag:
                nets.setdefault(net, set()).add(f"{p['ref']}/{n}")
    ends = [pt for seg in segs for pt in seg]
    segs = split(segs, ends + pin_pts + [at for _, at, _ in labels])
    degree = {}
    for pt in [pt for seg in segs for pt in seg] + pin_pts:
        degree[pt] = degree.get(pt, 0) + 1
    for i, (a, b) in enumerate(sorted(segs)):
        items.append([atom('wire'), [atom('pts'), [atom('xy'), *a], [atom('xy'), *b]],
                      [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                      [atom('uuid'), uid(f'wire/{a}/{b}')]])
    for pt in sorted(pt for pt, k in degree.items() if k >= 3):
        items.append([atom('junction'), [atom('at'), *pt], [atom('diameter'), 0],
                      [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'junction/{pt}')]])
    for net, (lx, ly), ang in labels:
        items.append([atom('label'), net, [atom('at'), lx, ly, ang],
                      [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                       [atom('justify'), atom('right' if ang == 180 else 'left'), atom('bottom')]],
                      [atom('uuid'), uid(f'label/{net}/{lx}/{ly}')]])
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    for i, ((x, y), s, size) in enumerate(TEXTS):
        items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                      [atom('effects'), [atom('font'), [atom('size'), size, size]], [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'text/{i}')]])
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])
    out = HW / f'{PROJECT}.kicad_sch'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True,
                   stdout=subprocess.DEVNULL)
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbols in hardware/{LIBNAME}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    native = netlist_nets(out)
    native = {n: k for n, k in native.items() if not n.startswith('unconnected-')}
    assert native == nets, ('native netlist differs from circuit()',
                            {n: (native.get(n), nets.get(n)) for n in set(native) | set(nets)
                             if native.get(n) != nets.get(n)})
    print(out, f'{len(nets)} nets, native netlist equals circuit()')


if __name__ == '__main__':
    build()
