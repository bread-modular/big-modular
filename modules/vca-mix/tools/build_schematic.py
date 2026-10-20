"""Generate the S4 VCA-MIX schematic (hardware/vca-mix.kicad_sch) and its pinned symbols.

Run from modules/vca-mix:
  python3 -B tools/build_schematic.py

Writes hardware/VCA_MIX.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the VCA-MIX library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
intent of docs/research.md section 3; wiring() draws every net as wires between the
computed pin ends (as modules/imix), with one local label per signal net (two where a
net joins blocks: SUM) and stock GND/+12V/-12V power symbols. The build exports the
native netlist and fails unless it equals circuit().

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
PROJECT = 'vca-mix'
LIBNAME = 'VCA_MIX'

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the VCA-MIX library, so the copies
# get the same patterns without the library part. The vactrol uses the Bread Modular
# V2CA footprint (VTL5C), so its filter also names that footprint.
FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
    'VTL5C': 'PerkinElmer*VTL5C* VTL5C',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'D': ('Device', 'D'),
    'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'VTL5C': ('Isolator', 'VTL5C'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R2512': 'R_2512_6332Metric', 'C0603': 'C_0603_1608Metric',
    'C0805': 'C_0805_2012Metric', 'SOD123': 'D_SOD-123', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'VTL5C': 'VTL5C', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
}

# Channel n: jacks (IN, CV, OUT). Each channel has three TL072s, so every op amp sits in
# its channel's row on the board (docs/geometry.json):
#   Un01 A input buffer, B VCA stage;  Un02 A CV buffer, B vactrol driver;
#   Un03 A volume follower (OUT + mix feed), B spare;  Un04 = the vactrol.
# U401 holds the mix bus (A summer, B inverter).
JACKS = {1: ('J1', 'J2', 'J3'), 2: ('J4', 'J5', 'J6'), 3: ('J7', 'J8', 'J9')}
POTNOTE = ('Song Huei R0904N 50k linear tall trimmer (the pot Bread Modular uses) on the unchanged '
           'Bread Modular RV09 footprint, hand-soldered. Pin 3 (CW) = VCA out via 100R, pin 1 (CCW) = GND')
OUTNOTE = ('Output series / short-circuit and mis-patch protection, 1 W 2512 (as imix R18): '
           '~0.51 W with a -12 V source patched in against +10.5 V')

# Sheet layout (A3, mm). Channel blocks stacked down the left; power entry, mix and the
# notes on the right. In a block the CV line (YC) runs above the audio line (YA = YC + 38.1),
# the vactrol stands between them (LED up to the driver, LDR down in the audio line).
X0 = 25.4
YC = {1: 45.72, 2: 127.0, 3: 208.28}
DA = 38.1
MX, YS = 312.42, 140.97  # mix block origin / SUM line
DXP = 279.4              # power entry: modules/imix S3 power drawing shifted right

R_RIGHT = ((3.81, -1.27), (3.81, 1.27))   # texts beside a vertical R / C / D
FB_TEXT = ((0, -2.54), (0, 2.54))         # texts above/below a horizontal feedback R
CF_TEXT = ((-2.54, -3.81), (2.54, -3.81))  # ... and its feedback C (both above)
OPAMP_BELOW = ((0, 7.62), (0, 10.16))
OPAMP_ABOVE = ((0, -10.16), (0, -7.62))
PWR_UNIT_TEXT = ((-6.35, -1.27), (-6.35, 1.27))


def r(v):
    return round(v, 2)


def part(ref, sym, value, fp, at, rot, pins, unit=1, mirror=None, text=None, **fields):
    assert mirror is None or rot == 0, (ref, 'mirror only with rot 0')
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(r(at[0]), r(at[1])), rot=rot, pins=pins,
                unit=unit, mirror=mirror, text=text, fields=fields)


PWR = []  # running #PWR numbering


def psym(c, net, at, rot=0):
    """Stock power symbol (GND / +12V / -12V) with its pin at `at`.
    GND: rot 0 points down, 90 right, 270 left. +12V: rot 0 up. -12V: rot 180 down."""
    PWR.append(net)
    c.append(part(f'#PWR{len(PWR):02d}', net, net, None, at, rot, {'1': net}))


def opamp(ref, unit, at, out, inv, noninv, mirror='x', text=OPAMP_BELOW, note=''):
    o, m, p_ = {1: ('1', '2', '3'), 2: ('7', '6', '5')}[unit]
    return part(ref, 'TL072', 'TL072CDT', 'SOIC8', at, 0, {o: out, m: inv, p_: noninv}, unit=unit,
                mirror=mirror, text=text, Note=note)


def power_cell(c, ref, xu, yu):
    """TL072 power unit with one 100n per supply pin (V+ top, V- bottom), GND between."""
    n = int(ref[1:])
    c.append(part(ref, 'TL072', 'TL072CDT', 'SOIC8', (xu, yu), 0, {'4': '-12V', '8': '+12V'}, unit=3,
                  text=PWR_UNIT_TEXT, Note='Dual JFET op amp on +/-12 V (after D501/D502)'))
    cp, cm = CELL_CAPS[ref]
    c.append(part(cp, 'C', '100n', 'C0603', (xu + 7.62, yu - 6.35), 0, {'1': '+12V', '2': 'GND'},
                  text=R_RIGHT, Voltage='50V', Note=f'{ref} V+ (pin 8) decoupling'))
    c.append(part(cm, 'C', '100n', 'C0603', (xu + 7.62, yu + 6.35), 0, {'1': 'GND', '2': '-12V'},
                  text=R_RIGHT, Voltage='50V', Note=f'{ref} V- (pin 4) decoupling'))
    psym(c, '+12V', (xu + 2.54, yu - 10.16))
    psym(c, '-12V', (xu + 2.54, yu + 10.16), 180)
    psym(c, 'GND', (xu + 12.7, yu))


# op amp -> (+12 V cap, -12 V cap)
CELL_CAPS = {f'U{n}0{k}': (f'C{n}{2 * k + 1:02d}', f'C{n}{2 * k + 2:02d}') for n in (1, 2, 3) for k in (1, 2, 3)}
CELL_CAPS['U401'] = ('C403', 'C404')


def cells(n):
    x, y = X0 + 205.74, YC[n] + 15.24
    return [(f'U{n}0{k}', x + (k - 1) * 25.4, y) for k in (1, 2, 3)]


def channel(c, n):
    """Channel n: CV line (CV buffer -> vactrol driver) above the audio line (input buffer
    -> vactrol LDR -> VCA stage -> 100R -> VOL n -> follower -> 1k 2512 -> OUT n, and
    100k -> SUM)."""
    x0, yc = X0, YC[n]
    ya = yc + DA
    yi = ya - 2.54
    j_in, j_cv, j_out = JACKS[n]
    R = lambda k: f'R{n}{k:02d}'  # noqa: E731
    C = lambda k: f'C{n}{k:02d}'  # noqa: E731
    u1, u2, u3, v = f'U{n}01', f'U{n}02', f'U{n}03', f'U{n}04'
    # ---- CV: jack -> 100k -> inverting buffer (51k || 20p, gain -0.51) -> driver
    c.append(part(j_cv, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0, yc), 0,
                  {'T': f'CV{n}', 'S': 'GND', 'TN': f'CVN{n}'}, mirror='x', text=((0, -6.35), (0, 8.89)),
                  Note=f'Channel {n} CV in (TS); with no plug TN normals CV to +12V via R{n}07 (VCA open)'))
    psym(c, 'GND', (x0 + 7.62, yc + 2.54))
    c.append(part(R(7), 'R', '56k', 'R0603', (x0 + 10.16, yc - 8.89), 0, {'1': '+12V', '2': f'CVN{n}'},
                  text=R_RIGHT, Note='CV normal: no plug -> CVB = -12V x 51k / 156k = -3.9V, I_LED ~12 mA (VCA open)'))
    psym(c, '+12V', (x0 + 10.16, yc - 12.7))
    c.append(part(R(8), 'R', '100k', 'R0603', (x0 + 17.78, yc), 90, {'1': f'CV{n}', '2': f'CVI{n}'},
                  Note='CV input resistor: 100k Eurorack input impedance'))
    c.append(part(R(6), 'R', '51k', 'R0603', (x0 + 33.02, yc - 7.62), 90, {'1': f'CVI{n}', '2': f'CVB{n}'},
                  text=FB_TEXT, Note='CV buffer feedback: CVB = -0.51 x CV'))
    c.append(part(C(2), 'C', '20p', 'C0603', (x0 + 33.02, yc - 15.24), 90, {'1': f'CVI{n}', '2': f'CVB{n}'},
                  text=CF_TEXT, Voltage='50V', Note='CV buffer HF roll-off / stability (~156 kHz)'))
    c.append(opamp(u2, 1, (x0 + 33.02, yc + 2.54), f'CVB{n}', f'CVI{n}', 'GND', note=f'Channel {n} CV buffer (inverting)'))
    psym(c, 'GND', (x0 + 22.86, yc + 5.08))
    # driver (Bread Modular LOW/SVF, referenced to the negative CVB): V(LEDA) = CVB,
    # I_LED = -CVB / 330R = 0.51 x CV / 330R, flowing GND -> R -> LED anode -> cathode -> out.
    c.append(opamp(u2, 2, (x0 + 58.42, yc + 5.08), f'LEDK{n}', f'LEDA{n}', f'CVB{n}', mirror=None,
                   text=OPAMP_ABOVE, note=f'Channel {n} vactrol driver: LED in the feedback loop'))
    c.append(part(R(9), 'R', '330', 'R0603', (x0 + 60.96, yc + 16.51), 0, {'1': f'LEDA{n}', '2': 'GND'},
                  text=R_RIGHT, Note='LED current sense: I_LED = 0.51 x CV / 330R (5V: 7.7 mA, 10V: 15.5 mA)'))
    psym(c, 'GND', (x0 + 60.96, yc + 20.32))
    c.append(part(f'D{n}01', 'D', '1N4148W', 'SOD123', (x0 + 68.58, yc + 8.89), 90,
                  {'1': f'LEDA{n}', '2': f'LEDK{n}'}, text=((-6.35, -1.27), (-6.35, 1.27)),
                  Note='Anti-parallel to the LED: negative CV keeps the loop closed, LED reverse voltage ~0.7 V'))
    c.append(part(v, 'VTL5C', 'VTL5C', 'VTL5C', (x0 + 76.2, yc + 30.48), 270,
                  {'1': f'LEDK{n}', '2': f'LEDA{n}', '3': f'LDR{n}', '4': f'BUF{n}'},
                  text=((8.89, -1.27), (8.89, 1.27)),
                  Note='Vactrol (Chinese VTL5C type), hand-soldered THT on B behind its pot (Bread Modular VTL5C footprint)'))
    # ---- audio: jack -> 100k -> inverting buffer (100k || 20p) -> LDR -> 10k -> VCA stage
    c.append(part(j_in, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0, yi), 0,
                  {'T': f'IN{n}', 'S': 'GND', 'TN': 'GND'}, mirror='x', text=((0, -6.35), (0, 8.89)),
                  Note=f'Channel {n} audio in (TS); TN grounds the unpatched input'))
    psym(c, 'GND', (x0 + 7.62, yi + 2.54))
    psym(c, 'GND', (x0 + 7.62, yi - 2.54), 90)
    c.append(part(R(1), 'R', '100k', 'R0603', (x0 + 17.78, yi), 90, {'1': f'IN{n}', '2': f'INV{n}'},
                  Note='Input resistor: 100k Eurorack input impedance'))
    c.append(part(R(2), 'R', '100k', 'R0603', (x0 + 33.02, yi - 7.62), 90, {'1': f'INV{n}', '2': f'BUF{n}'},
                  text=FB_TEXT, Note='Input buffer feedback (gain -1)'))
    c.append(part(C(1), 'C', '20p', 'C0603', (x0 + 33.02, yi - 15.24), 90, {'1': f'INV{n}', '2': f'BUF{n}'},
                  text=CF_TEXT, Voltage='50V', Note='Input buffer HF roll-off / stability (~80 kHz)'))
    c.append(opamp(u1, 1, (x0 + 33.02, ya), f'BUF{n}', f'INV{n}', 'GND', note=f'Channel {n} input buffer (inverting)'))
    psym(c, 'GND', (x0 + 22.86, ya + 2.54))
    c.append(part(R(3), 'R', '10k', 'R0603', (x0 + 86.36, ya), 90, {'1': f'LDR{n}', '2': f'VSUM{n}'},
                  Note='VCA input (V2CA R3)'))
    c.append(part(R(4), 'R', '10k', 'R0603', (x0 + 101.6, ya - 7.62), 90, {'1': f'VSUM{n}', '2': f'VCA{n}'},
                  text=FB_TEXT, Note='VCA feedback (V2CA R4): gain = -10k / (10k + R_LDR)'))
    c.append(opamp(u1, 2, (x0 + 101.6, ya + 2.54), f'VCA{n}', f'VSUM{n}', 'GND', note=f'Channel {n} VCA stage'))
    psym(c, 'GND', (x0 + 91.44, ya + 5.08))
    # ---- volume after the VCA, follower -> 1k (2512) -> OUT, and 100k -> SUM
    c.append(part(R(10), 'R', '100', 'R0603', (x0 + 119.38, ya + 2.54), 90, {'1': f'VCA{n}', '2': f'VOLT{n}'},
                  Note='Pot feed / isolation (Bread Modular imix)'))
    c.append(part(f'RV{n}', 'R_Potentiometer', '50k', 'RV09', (x0 + 132.08, ya + 6.35), 0,
                  {'3': f'VOLT{n}', '1': 'GND', '2': f'VOLW{n}'}, mirror='x', text=((-6.35, -1.27), (-6.35, 1.27)),
                  Taper='B (linear)', Note=f'Channel {n} volume: ' + POTNOTE))
    psym(c, 'GND', (x0 + 132.08, ya + 10.16))
    c.append(opamp(u3, 1, (x0 + 149.86, ya + 8.89), f'CHO{n}', f'CHO{n}', f'VOLW{n}', mirror=None,
                   note=f'Channel {n} volume follower: drives OUT {n} and the mix bus'))
    c.append(part(R(5), 'R', '1k', 'R2512', (x0 + 170.18, ya + 8.89), 90, {'1': f'CHO{n}', '2': f'OUT{n}'},
                  Note=OUTNOTE))
    c.append(part(j_out, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0 + 185.42, ya + 8.89), 180,
                  {'T': f'OUT{n}', 'S': 'GND', 'TN': None}, text=((0, -6.35), (0, 6.35)),
                  Note=f'Channel {n} out, after VOL{n} (TS)'))
    psym(c, 'GND', (x0 + 177.8, ya + 11.43))
    c.append(part(R(11), 'R', '100k', 'R0603', (x0 + 162.56, ya + 12.7), 0, {'1': f'CHO{n}', '2': 'SUM'},
                  text=R_RIGHT, Note='Mix bus input (unity per channel)'))
    # ---- spare U n03 B: grounded follower; power units with their decoupling
    c.append(opamp(u3, 2, (x0 + 215.9, ya + 5.08), f'SPARE{n}', f'SPARE{n}', 'GND', note='Unused section, grounded follower'))
    psym(c, 'GND', (x0 + 205.74, ya + 7.62))
    for ref, xu, yu in cells(n):
        power_cell(c, ref, xu, yu)


def circuit():
    PWR.clear()
    c = []
    # ---- Power entry (modules/imix S3 drawing, shifted DXP right): Eurorack +/-12 V ->
    # series Schottky per rail -> +12V / -12V. J10 drawn rotated 180 (+12 V on top).
    d = DXP
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (d + 45.72, 58.42), 180,
                  {'1': '-12V_IN', '2': '-12V_IN', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V_IN', '10': '+12V_IN'}, text=((-1.27, -8.89), (-1.27, 8.89)),
                  Note='Unshrouded header across the top edge, pin 1 (-12 V) at the left; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    psym(c, 'GND', (d + 33.02, 59.69), 270)
    psym(c, 'GND', (d + 55.88, 59.69), 90)
    c.append(part('D501', 'D_Schottky', 'B5819W', 'SOD123', (d + 71.12, 45.72), 180,
                  {'1': '+12V', '2': '+12V_IN'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D502', 'D_Schottky', 'B5819W', 'SOD123', (d + 71.12, 71.12), 0,
                  {'1': '-12V_IN', '2': '-12V'}, Note='-12 V series reverse-polarity protection'))
    c.append(part('C501', 'C', '10u', 'C0805', (d + 86.36, 49.53), 0, {'1': '+12V', '2': 'GND'},
                  text=R_RIGHT, Voltage='25V', Note='+12 V bulk'))
    c.append(part('C502', 'C', '10u', 'C0805', (d + 86.36, 67.31), 0, {'1': 'GND', '2': '-12V'},
                  text=R_RIGHT, Voltage='25V', Note='-12 V bulk'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (d + 91.44, 58.42), 0, {'1': 'GND'}))
    psym(c, 'GND', (d + 91.44, 58.42))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (d + 96.52, 45.72), 0, {'1': '+12V'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (d + 96.52, 71.12), 0, {'1': '-12V'}))
    psym(c, '+12V', (d + 106.68, 45.72))
    psym(c, '-12V', (d + 106.68, 71.12), 180)

    for n in (1, 2, 3):
        channel(c, n)

    # ---- Mix bus (modules/imix): SUM -> summer (100k || 20p) -> inverter (100k / 100k || 20p)
    # -> 1k (2512) -> MIX. MIX = CHO1 + CHO2 + CHO3, input polarity.
    m, y = MX, YS
    c.append(part('R401', 'R', '100k', 'R0603', (m + 20.32, y - 7.62), 90, {'1': 'SUM', '2': 'SUMO'},
                  text=FB_TEXT, Note='Summer feedback: unity per channel'))
    c.append(part('C401', 'C', '20p', 'C0603', (m + 20.32, y - 15.24), 90, {'1': 'SUM', '2': 'SUMO'},
                  text=CF_TEXT, Voltage='50V', Note='Summer HF roll-off / stability'))
    c.append(opamp('U401', 1, (m + 20.32, y + 2.54), 'SUMO', 'SUM', 'GND', note='Inverting summer'))
    psym(c, 'GND', (m + 10.16, y + 5.08))
    c.append(part('R402', 'R', '100k', 'R0603', (m + 38.1, y + 2.54), 90, {'1': 'SUMO', '2': 'MINV'},
                  Note='Inverter input'))
    c.append(part('R403', 'R', '100k', 'R0603', (m + 53.34, y - 5.08), 90, {'1': 'MINV', '2': 'MIXO'},
                  text=FB_TEXT, Note='Inverter feedback (gain -1): MIX has the input polarity'))
    c.append(part('C402', 'C', '20p', 'C0603', (m + 53.34, y - 12.7), 90, {'1': 'MINV', '2': 'MIXO'},
                  text=CF_TEXT, Voltage='50V', Note='Inverter HF roll-off / stability'))
    c.append(opamp('U401', 2, (m + 53.34, y + 5.08), 'MIXO', 'MINV', 'GND', note='Mix inverter'))
    psym(c, 'GND', (m + 43.18, y + 7.62))
    c.append(part('R404', 'R', '1k', 'R2512', (m + 72.39, y + 5.08), 90, {'1': 'MIXO', '2': 'MIX'},
                  Note=OUTNOTE))
    c.append(part('J11', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (m + 86.36, y + 5.08), 180,
                  {'T': 'MIX', 'S': 'GND', 'TN': None}, text=((0, -6.35), (0, 6.35)), Note='Mix out (TS)'))
    psym(c, 'GND', (m + 78.74, y + 7.62))
    power_cell(c, 'U401', m + 20.32, y + 33.02)
    for p in c:
        if not p['ref'].startswith('#'):
            p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def channel_wiring(n, P):
    x0, yc = X0, YC[n]
    ya = yc + DA
    yi = ya - 2.54
    J = JACKS[n]
    R = lambda k: f'R{n}{k:02d}'  # noqa: E731
    u1, u2, u3, v = f'U{n}01', f'U{n}02', f'U{n}03', f'U{n}04'
    w = [
        # CV jack: S -> GND, TN -> R n07 (CVN), T -> R n08
        [P(J[1], 'S'), (x0 + 7.62, yc + 2.54)],
        [P(J[1], 'TN'), (x0 + 10.16, yc - 2.54), P(R(7), '2')],
        [P(J[1], 'T'), P(R(8), '1')],
        # CV buffer: input node, feedback loop above, (+) -> GND, out -> driver (+)
        [P(R(8), '2'), P(u2, '2')],
        [(x0 + 22.86, yc), (x0 + 22.86, yc - 15.24), P(f'C{n}02', '1')],
        [(x0 + 22.86, yc - 7.62), P(R(6), '1')],
        [P(R(6), '2'), (x0 + 43.18, yc - 7.62)],
        [P(f'C{n}02', '2'), (x0 + 43.18, yc - 15.24), (x0 + 43.18, yc + 2.54)],
        [P(u2, '3'), (x0 + 22.86, yc + 5.08)],
        [P(u2, '1'), P(u2, '5')],
        # driver: out (LEDK) -> D anode -> vactrol pin 1; (-) (LEDA) -> R n09 / D cathode -> pin 2
        [P(u2, '7'), (x0 + 78.74, yc + 5.08), P(v, '1')],
        [P(u2, '6'), (x0 + 50.8, yc + 12.7), (x0 + 73.66, yc + 12.7), P(v, '2')],
        # audio input: S/TN -> GND, T -> R n01 -> buffer (-), feedback above
        [P(J[0], 'S'), (x0 + 7.62, yi + 2.54)],
        [P(J[0], 'TN'), (x0 + 7.62, yi - 2.54)],
        [P(J[0], 'T'), P(R(1), '1')],
        [P(R(1), '2'), P(u1, '2')],
        [(x0 + 22.86, yi), (x0 + 22.86, yi - 15.24), P(f'C{n}01', '1')],
        [(x0 + 22.86, yi - 7.62), P(R(2), '1')],
        [P(R(2), '2'), (x0 + 43.18, yi - 7.62)],
        [P(f'C{n}01', '2'), (x0 + 43.18, yi - 15.24), (x0 + 43.18, ya)],
        [P(u1, '3'), (x0 + 22.86, ya + 2.54)],
        [P(u1, '1'), P(v, '4')],
        # LDR -> R n03 -> VCA stage (-), feedback R n04 above, out -> R n10
        [P(v, '3'), P(R(3), '1')],
        [P(R(3), '2'), P(u1, '6')],
        [(x0 + 91.44, ya), (x0 + 91.44, ya - 7.62), P(R(4), '1')],
        [P(R(4), '2'), (x0 + 111.76, ya - 7.62), (x0 + 111.76, ya + 2.54)],
        [P(u1, '5'), (x0 + 91.44, ya + 5.08)],
        [P(u1, '7'), P(R(10), '1')],
        # pot, follower (feedback below), CHO -> 2512 -> OUT jack; CHO -> R n11 -> SUM
        [P(R(10), '2'), P(f'RV{n}', '3')],
        [P(f'RV{n}', '2'), P(u3, '3')],
        [P(u3, '2'), (x0 + 142.24, ya + 15.24), (x0 + 160.02, ya + 15.24), (x0 + 160.02, ya + 8.89)],
        [P(u3, '1'), P(R(5), '1')],
        [P(R(5), '2'), P(J[2], 'T')],
        [P(J[2], 'S'), (x0 + 177.8, ya + 11.43)],
        [P(R(11), '2'), (x0 + 162.56, ya + 19.05)],
        # spare follower
        [P(u3, '7'), (x0 + 226.06, ya + 5.08), (x0 + 226.06, ya - 2.54), (x0 + 205.74, ya - 2.54),
         (x0 + 205.74, ya + 2.54), P(u3, '6')],
        [P(u3, '5'), (x0 + 205.74, ya + 7.62)],
    ]
    for ref, xu, yu in cells(n):
        w += cell_wiring(ref, xu, yu, P)
    lab = [(f'CVN{n}', (x0 + 6.35, yc - 2.54)), (f'CV{n}', (x0 + 8.89, yc)), (f'CVI{n}', (x0 + 22.86, yc - 3.81)),
           (f'CVB{n}', (x0 + 45.72, yc + 2.54)), (f'LEDK{n}', (x0 + 71.12, yc + 5.08)),
           (f'LEDA{n}', (x0 + 53.34, yc + 12.7)),
           (f'IN{n}', (x0 + 10.16, yi)), (f'INV{n}', (x0 + 22.86, yi - 3.81)), (f'BUF{n}', (x0 + 48.26, ya)),
           (f'LDR{n}', (x0 + 80.01, ya)), (f'VSUM{n}', (x0 + 91.44, ya - 3.81)), (f'VCA{n}', (x0 + 113.03, ya + 2.54)),
           (f'VOLT{n}', (x0 + 125.73, ya + 2.54)), (f'VOLW{n}', (x0 + 137.16, ya + 6.35)),
           (f'CHO{n}', (x0 + 163.83, ya + 8.89)), (f'OUT{n}', (x0 + 175.26, ya + 8.89)),
           ('SUM', (x0 + 162.56, ya + 19.05)), (f'SPARE{n}', (x0 + 210.82, ya - 2.54))]
    return w, lab


def cell_wiring(ref, xu, yu, P):
    cp, cm = CELL_CAPS[ref]
    return [[P(ref, '8'), (xu - 2.54, yu - 10.16), P(cp, '1')],
            [P(ref, '4'), (xu - 2.54, yu + 10.16), P(cm, '2')],
            [P(cp, '2'), P(cm, '1')], [(xu + 7.62, yu), (xu + 12.7, yu)]]


def wiring(P):
    """Wire polylines between pin ends and the labels (one per signal net, SUM also at
    each channel). build() splits T-joints, adds junction dots and checks the netlist."""
    w, lab = [], []
    d = DXP
    # Power entry (modules/imix): J10 GND pins bussed per side, +12V_IN / -12V_IN pairs joined.
    for x0, x1, xg in ((d + 38.1, d + 35.56, d + 33.02), (d + 50.8, d + 53.34, d + 55.88)):
        w += [[(x0, yy), (x1, yy)] for yy in (55.88, 58.42, 60.96)]
        w += [[(x1, 55.88), (x1, 60.96)], [(x1, 59.69), (xg, 59.69)]]
    w += [[(d + 38.1, 53.34), (d + 30.48, 53.34), (d + 30.48, 45.72), (d + 67.31, 45.72)],
          [(d + 50.8, 53.34), (d + 60.96, 53.34), (d + 60.96, 45.72)],
          [(d + 38.1, 63.5), (d + 30.48, 63.5), (d + 30.48, 71.12), (d + 67.31, 71.12)],
          [(d + 50.8, 63.5), (d + 60.96, 63.5), (d + 60.96, 71.12)],
          [(d + 74.93, 45.72), (d + 106.68, 45.72)], [(d + 74.93, 71.12), (d + 106.68, 71.12)],
          [(d + 86.36, 53.34), (d + 86.36, 63.5)], [(d + 86.36, 58.42), (d + 91.44, 58.42)]]
    lab += [('+12V_IN', (d + 40.64, 45.72)), ('-12V_IN', (d + 40.64, 71.12))]
    for n in (1, 2, 3):
        cw, cl = channel_wiring(n, P)
        w += cw
        lab += cl
    m, y = MX, YS
    w += [[(m + 2.54, y), P('U401', '2')],                                     # SUM in
          [(m + 10.16, y), (m + 10.16, y - 15.24), P('C401', '1')], [(m + 10.16, y - 7.62), P('R401', '1')],
          [P('R401', '2'), (m + 30.48, y - 7.62)],
          [P('C401', '2'), (m + 30.48, y - 15.24), (m + 30.48, y + 2.54)],
          [P('U401', '3'), (m + 10.16, y + 5.08)],
          [P('U401', '1'), P('R402', '1')],                               # SUMO
          [P('R402', '2'), P('U401', '6')],                               # MINV
          [(m + 43.18, y + 2.54), (m + 43.18, y - 12.7), P('C402', '1')], [(m + 43.18, y - 5.08), P('R403', '1')],
          [P('R403', '2'), (m + 63.5, y - 5.08)],
          [P('C402', '2'), (m + 63.5, y - 12.7), (m + 63.5, y + 5.08)],
          [P('U401', '5'), (m + 43.18, y + 7.62)],
          [P('U401', '7'), P('R404', '1')],                               # MIXO
          [P('R404', '2'), P('J11', 'T')],                                # MIX
          [P('J11', 'S'), (m + 78.74, y + 7.62)]]
    w += cell_wiring('U401', m + 20.32, y + 33.02, P)
    lab += [('SUM', (m + 2.54, y)), ('SUMO', (m + 31.75, y + 2.54)), ('MINV', (m + 44.45, y + 2.54)),
            ('MIXO', (m + 64.77, y + 5.08)), ('MIX', (m + 77.47, y + 5.08))]
    w = [[(r(x), r(yy)) for x, yy in line] for line in w]
    lab = [(nm, (r(x), r(yy)), 0) for nm, (x, yy) in lab]
    return [(a, b) for line in w for a, b in zip(line, line[1:])], lab


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Live strict lookups (docs/sourcing-candidates.json). All Basic except the 1 W 2512 output
# resistors (Extended, as imix R18 / 8bit R12: no Basic 1 W 1k exists).
# The THT jacks, pots, vactrols and the power header are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '330', 'R0603'): dict(LCSC='C23138', MPN='0603WAF3300T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R2512'): dict(LCSC='C54315', MPN='25121WF1001T4E', Manufacturer='UNI-ROYAL'),
    ('C', '20p', 'C0603'): dict(LCSC='C1648', MPN='CL10C200JB8NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST (Semtech)'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('TL072', 'TL072CDT', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
}

TEXT_AT = {
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '+12V': ((0, -6.35), (0, -3.81)),
    '-12V': ((0, 6.35), (0, 3.81)),
}
SHOW_VALUE = {'+12V', '-12V'}  # power symbols whose value text is drawn

TEXTS = [
    ((20.32, 17.78), 'BIG MODULAR VCA-MIX - S4 schematic: 3 x vactrol VCA (Bread Modular V2CA at CURVE 0, LOW/SVF vactrol driver) '
                    '+ post-VCA volume + 3-channel mixer (modules/imix). Circuit intent: docs/research.md', 2.0),
    ((DXP + 20.32, 203.2), 'CHANNEL n (n = 1..3; refs Rn01..Rn11, Cn01..Cn08, Dn01, Un01..Un04):\n'
                     'every input buffered at a fixed 100k.\n'
                     'IN -> -1 buffer -> LDR + 10k -> -1 VCA stage (gain 10k / (10k + R_LDR)) -> 100R -> VOL n ->\nfollower -> 1k -> OUT n, and 100k -> SUM (OUT is post-volume).\n'
                     'CV -> 100k -> -0.51 buffer (CVB) -> vactrol driver, LED in the op-amp loop:\n'
                     'I_LED = 0.51 x CV / 330R, linear from 0 V.\nNo CV plug: TN normals CV to +12V via 56k (~12 mA, VCA open).', 1.27),
    ((DXP + 20.32, 86.36), 'POWER: Eurorack +12V / -12V -> B5819W per rail -> +12V / -12V (about +/-11.6 V).\n+5V and pins 11-16 unused. '
                           '100n at every op-amp supply pin, 10u bulk per rail.', 1.27),
    ((DXP + 20.32, 96.52), 'PWR_FLAG: #FLG01 marks the Eurorack GND; #FLG02/#FLG03 mark the +12V/-12V rails,\n'
                           'fed from the header only through D501/D502, which ERC cannot see through.', 1.1),
    ((MX - 2.54, YS - 30.48), 'MIX (modules/imix): CHO n -> 100k -> SUM -> summer (100k || 20p) ->\ninverter -> 1k (2512) -> MIX. '
                              'MIX = CHO1 + CHO2 + CHO3 with the input polarity.\nAll outputs 1k / 1 W 2512.', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/vca-mix/schematic/' + key))


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
    stock_header = parse((STOCK / 'Device.kicad_sym').read_text())
    lib = [atom('kicad_symbol_lib'), one(stock_header, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(lib_syms[k]) for k in sorted(lib_syms)]
    (HW / f'{LIBNAME}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIBNAME}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIBNAME}.kicad_sym") '
        '(options "") (descr "VCA-MIX module pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - VCA-MIX") (rev "S4") (company "Big Modular")
        (comment 1 "SCHEMATIC S4 - 3 x vactrol VCA + mixer, buffered inputs/CV, +-12 V, 6HP - not released")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIBNAME}:' + k
        embedded.append(s)

    parts = circuit()
    pinpos, items, nets, pin_pts, units = {}, [], {}, [], {}
    for p in parts:
        pins = pin_table(lib_syms[p['sym']], p['unit'])
        assert set(p['pins']) == set(pins), (p['ref'], p['unit'], sorted(pins), sorted(p['pins']))
        assert p['unit'] not in units.setdefault(p['ref'], set()), (p['ref'], p['unit'])
        units[p['ref']].add(p['unit'])
        for n in pins:
            ox, oy = xform(pins[n][0], pins[n][1], p['rot'], p['mirror'])
            pinpos[(p['ref'], n)] = (r(p['at'][0] + ox), r(p['at'][1] + oy))

    def P(ref, pin):
        return pinpos[(ref, pin)]

    segs, labels = wiring(P)
    for p in parts:
        sym = lib_syms[p['sym']]
        unit = p['unit']
        pins = pin_table(sym, unit)
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
            ex, ey = pinpos[(p['ref'], n)]
            pin_pts.append((ex, ey))
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid(f"nc/{p['ref']}/{n}")]])
            elif not is_flag:
                nets.setdefault(net, set()).add(f"{p['ref']}/{n}")
    for ref in [k for k in units if k.startswith('U') and k[-1] != '4']:
        assert units[ref] == {1, 2, 3}, (ref, units[ref])
    ends = [pt for seg in segs for pt in seg]
    segs = split(segs, ends + pin_pts + [at for _, at, _ in labels])
    degree = {}
    for pt in [pt for seg in segs for pt in seg] + pin_pts:
        degree[pt] = degree.get(pt, 0) + 1
    for a, b in sorted(segs):
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
