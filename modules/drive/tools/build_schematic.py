"""Generate the S1 DRIVE schematic (hardware/drive.kicad_sch) and its pinned symbols.

Run from modules/drive:
  python3 -B tools/build_schematic.py

modules/vca-mix's generator (pinned stock KiCad 10 symbols, explicit wires between the computed
pin ends, native netlist assertion) with this module's circuit: an OTA overdrive + wavefolder.
Writes hardware/DRIVE.kicad_sym, hardware/sym-lib-table and the flat root schematic, then lets
`kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit intent of
docs/research.md section 3; tools/sim_drive.py takes its values from circuit().

Every net is drawn as wires. Four nets also join two blocks by a label: DRY (input buffer ->
VCA and MIX), X (VCA -> cells), Y (cells -> TONE) and IABC_A (DRIVE converter -> VCA).

The PCB never reads this table: tools/build_layout.py takes nets, values and footprints from
the native netlist that kicad-cli exports from this schematic.
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
PROJECT = 'drive'
LIBNAME = 'DRIVE'
REV = 'S1'

# Footprint filters of this stock symbol are qualified with a stock library name; the pinned
# footprints live in the DRIVE library, so the copy gets the same pattern without the library.
FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
}

# Pin-type edits (docs/schematic-symbols.json). The stock LM13700 types its amplifier outputs
# (pins 5 and 12) as voltage outputs; they are current outputs, and this circuit sums five of
# them on one node (YS), which ERC would report as output-to-output conflicts. They are typed
# passive here: the electrical truth of a current source, not an ERC waiver.
PIN_TYPE_EDITS = {'LM13700': {'5': 'passive', '12': 'passive'}}

# lib symbol -> (stock library, stock name). Q_PNP_BEC is the generic SOT-23 PNP (1 B, 2 E, 3 C),
# the SS8550 pin-out (CJ datasheet).
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'),
    'D_Schottky': ('Device', 'D_Schottky'), '1N4148W': ('Diode', '1N4148W'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'Q_PNP_BEC': ('Transistor_BJT', 'Q_PNP_BEC'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'LM13700': ('Amplifier_Operational', 'LM13700'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R2512': 'R_2512_6332Metric', 'C0603': 'C_0603_1608Metric',
    'C0805': 'C_0805_2012Metric', 'SOD123': 'D_SOD-123', 'SOT23': 'SOT-23',
    'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm', 'SOIC16': 'SOIC-16_3.9x9.9mm_P1.27mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
}

# Multi-unit symbols and the units placed (build() asserts it). LM13700: 1 = OTA on pins 12-16,
# 3 = OTA on pins 1-5, 2 / 4 = the Darlington buffers (unused), 5 = supply.
MULTI = {**{u: {1, 2, 3} for u in ('U1', 'U2', 'U3', 'U4')},
         **{u: {1, 2, 3, 4, 5} for u in ('U5', 'U6', 'U7')}}

POTNOTE = ('Song Huei R0904N 50k linear tall trimmer (the pot Bread Modular uses) on the unchanged '
           'Bread Modular RV09 footprint, hand-soldered')

# Sheet layout (A3, mm, 1.27 grid). Top: input buffer -> drive VCA -> X. Middle: the five tanh
# cells in a row under the X bus, YS bus -> sum amplifier -> Y, fold bias resistors under the
# cells. Below: FOLD converter (left), DRIVE converter (right). Bottom: TONE -> MIX -> OUT.
# Right: power entry, supply pins, unused buffers, notes.
X0 = 25.4
YA = 43.18               # input / VCA line
YB = 111.76              # cell centres
CX = [50.8 + 50.8 * i for i in range(5)]   # cells B, C, D, E, F
YF = 187.96              # FOLD / DRIVE converter lines
XD = 165.1               # DRIVE converter origin
YE = 246.38              # TONE / MIX / OUT line
DXP = 279.4              # power entry (modules/vca-mix drawing)
XU, YU1, YU2 = 292.1, 193.04, 226.06   # supply-pin cells: TL072 row, LM13700 row
XBUF, YBUF = 335.28, 149.86             # unused buffers

R_RIGHT = ((3.81, -1.27), (3.81, 1.27))    # texts beside a vertical R / C / D
R_LEFT = ((-3.81, -1.27), (-3.81, 1.27))
FB_TEXT = ((0, -2.54), (0, 2.54))          # texts above/below a horizontal feedback R
CF_TEXT = ((-2.54, -3.81), (2.54, -3.81))  # ... and its feedback C (both above)
OPAMP_BELOW = ((0, 7.62), (0, 10.16))
OPAMP_ABOVE = ((0, -10.16), (0, -7.62))
OTA_ABOVE = ((-2.54, -10.16), (-2.54, -7.62))
PWR_UNIT_TEXT = ((-10.16, -1.27), (-10.16, 1.27))
JACK_TEXT = ((0, -6.35), (0, 8.89))
UP = ((0, -6.35), (0, -3.81))              # value text of a rail symbol drawn upward


def r(v):
    return round(v, 2)


def part(ref, sym, value, fp, at, rot, pins, unit=1, mirror=None, text=None, **fields):
    assert mirror is None or rot == 0, (ref, 'mirror only with rot 0')
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(r(at[0]), r(at[1])), rot=rot, pins=pins,
                unit=unit, mirror=mirror, text=text, fields=fields)


PWR = []  # running #PWR numbering


def psym(c, net, at, rot=0, text=None):
    """Stock power symbol (GND / +12V / -12V) with its pin at `at`.
    GND: rot 0 points down, 90 right, 270 left. +12V: rot 0 up. -12V: rot 180 down, rot 0 up."""
    PWR.append(net)
    c.append(part(f'#PWR{len(PWR):02d}', net, net, None, at, rot, {'1': net}, text=text))


def R(c, ref, value, at, rot, n1, n2, note, text=None, fp='R0603'):
    c.append(part(ref, 'R', value, fp, at, rot, {'1': n1, '2': n2},
                  text=text or (R_RIGHT if rot in (0, 180) else None), Note=note))


def C(c, ref, value, at, rot, n1, n2, note, text=None, fp='C0603', volt='50V'):
    c.append(part(ref, 'C', value, fp, at, rot, {'1': n1, '2': n2},
                  text=text or (R_RIGHT if rot in (0, 180) else None), Voltage=volt, Note=note))


def opamp(c, ref, unit, at, out, inv, noninv, mirror='x', text=OPAMP_BELOW, note=''):
    o, m, p_ = {1: ('1', '2', '3'), 2: ('7', '6', '5')}[unit]
    c.append(part(ref, 'TL072', 'TL072CDT', 'SOIC8', at, 0, {o: out, m: inv, p_: noninv}, unit=unit,
                  mirror=mirror, text=text, Note=note))


def ota(c, ref, unit, at, out, inv, noninv, iabc, bias=None, mirror=None, note=''):
    """One LM13700 amplifier. unit 3 = pins 1-5, unit 1 = pins 12-16. Without a mirror the
    (-) input is the upper left pin and I_ABC the lower right one; mirror='x' swaps them."""
    i, b, p_, m, o = {3: ('1', '2', '3', '4', '5'), 1: ('16', '15', '14', '13', '12')}[unit]
    c.append(part(ref, 'LM13700', 'LM13700', 'SOIC16', at, 0, {i: iabc, b: bias, p_: noninv, m: inv, o: out},
                  unit=unit, mirror=mirror, text=OTA_ABOVE, Note=note))


def jack(c, ref, at, tip, note, rot=0, tn='GND'):
    c.append(part(ref, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', at, rot, {'T': tip, 'S': 'GND', 'TN': tn},
                  mirror='x' if rot == 0 else None, text=JACK_TEXT if rot == 0 else ((0, -6.35), (0, 6.35)),
                  Note=note))


def power_cell(c, ref, sym, value, fp, xu, yu, note):
    """Supply unit with one 100n per supply pin (V+ top, V- bottom), GND between."""
    unit, vp, vn = {'TL072': (3, '8', '4'), 'LM13700': (5, '11', '6')}[sym]
    cp, cm = CELL_CAPS[ref]
    c.append(part(ref, sym, value, fp, (xu, yu), 0, {vn: '-12V', vp: '+12V'}, unit=unit,
                  text=PWR_UNIT_TEXT, Note=note))
    C(c, cp, '100n', (xu + 7.62, yu - 6.35), 0, '+12V', 'GND', f'{ref} V+ (pin {vp}) decoupling')
    C(c, cm, '100n', (xu + 7.62, yu + 6.35), 0, 'GND', '-12V', f'{ref} V- (pin {vn}) decoupling')
    psym(c, '+12V', (xu + 2.54, yu - 10.16))
    psym(c, '-12V', (xu + 2.54, yu + 10.16), 180)
    psym(c, 'GND', (xu + 12.7, yu))


# IC -> (+12 V cap, -12 V cap): C16 .. C29
CELL_CAPS = {f'U{n}': (f'C{14 + 2 * n}', f'C{15 + 2 * n}') for n in range(1, 8)}
CELLS = ([(f'U{n}', 'TL072', XU + (n - 1) * 30.48, YU1) for n in (1, 2, 3, 4)]
         + [(f'U{n}', 'LM13700', XU + (n - 5) * 30.48, YU2) for n in (5, 6, 7)])

# Tanh cells in drawing order: (ref, unit, name, mirror, signal on (+)?, reference net, top R,
# bottom R, cap, rail, I_ABC net, I_ABC resistor).
CELL = [
    ('U5', 1, 'B', 'x', True, 'XB', None, 'R11', None, None, 'IABC_B', 'R20'),
    ('U6', 3, 'C', None, False, 'THP1', 'R12', 'R13', 'C6', '+12V', 'IF_C', 'R27'),
    ('U6', 1, 'D', None, False, 'THN1', 'R14', 'R15', 'C7', '-12V', 'IF_D', 'R28'),
    ('U7', 3, 'E', 'x', True, 'THP2', 'R16', 'R17', 'C8', '+12V', 'IF_E', 'R29'),
    ('U7', 1, 'F', 'x', True, 'THN2', 'R18', 'R19', 'C9', '-12V', 'IF_F', 'R30'),
]


def circuit():
    PWR.clear()
    c = []
    # ---- Power entry (modules/vca-mix drawing): Eurorack +/-12 V -> series Schottky per rail
    d = DXP
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (d + 45.72, 58.42), 180,
                  {'1': '-12V_IN', '2': '-12V_IN', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V_IN', '10': '+12V_IN'}, text=((-1.27, -8.89), (-1.27, 8.89)),
                  Note='Unshrouded header upright at the right board edge, pin 1 (-12 V) at the bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    psym(c, 'GND', (d + 33.02, 59.69), 270)
    psym(c, 'GND', (d + 55.88, 59.69), 90)
    c.append(part('D1', 'D_Schottky', 'B5819W', 'SOD123', (d + 71.12, 45.72), 180,
                  {'1': '+12V', '2': '+12V_IN'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D2', 'D_Schottky', 'B5819W', 'SOD123', (d + 71.12, 71.12), 0,
                  {'1': '-12V_IN', '2': '-12V'}, Note='-12 V series reverse-polarity protection'))
    C(c, 'C1', '10u', (d + 86.36, 49.53), 0, '+12V', 'GND', '+12 V bulk', fp='C0805', volt='25V')
    C(c, 'C2', '10u', (d + 86.36, 67.31), 0, 'GND', '-12V', '-12 V bulk', fp='C0805', volt='25V')
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (d + 91.44, 58.42), 0, {'1': 'GND'}))
    psym(c, 'GND', (d + 91.44, 58.42))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (d + 96.52, 45.72), 0, {'1': '+12V'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (d + 96.52, 71.12), 0, {'1': '-12V'}))
    psym(c, '+12V', (d + 106.68, 45.72))
    psym(c, '-12V', (d + 106.68, 71.12), 180)

    # ---- Input buffer (Bread Modular DRIVE 0.2.0: inverting, no RF pick-up) and the drive VCA:
    # OTA U5 (pins 1-5) with its linearizing diodes, I_out = I_s x 2 I_ABC / I_D, into U1B.
    x, y = X0, YA
    jack(c, 'J1', (x, y), 'IN', 'Audio in (TS); TN grounds the unpatched input')
    psym(c, 'GND', (x + 7.62, y + 2.54))
    psym(c, 'GND', (x + 7.62, y - 2.54), 90)
    R(c, 'R1', '100k', (x + 17.78, y), 90, 'IN', 'INV', 'Input resistor: 100k input impedance; limits a +/-12 V mis-patch to 0.12 mA')
    R(c, 'R2', '100k', (x + 33.02, y - 7.62), 90, 'INV', 'DRY', 'Input buffer feedback (gain -1)', text=FB_TEXT)
    C(c, 'C3', '20p', (x + 33.02, y - 15.24), 90, 'INV', 'DRY', 'Input buffer HF roll-off (~80 kHz)', text=CF_TEXT)
    opamp(c, 'U1', 1, (x + 33.02, y + 2.54), 'DRY', 'INV', 'GND', note='Input buffer (inverting): DRY = -IN')
    psym(c, 'GND', (x + 22.86, y + 5.08))
    R(c, 'R3', '15k', (x + 53.34, y + 2.54), 90, 'DRY', 'VAP',
      'VCA signal current: I_s = DRY / 15k, linear to +/-I_D / 2 = 0.53 mA (+/-8 V in)')
    R(c, 'R4', '1k', (x + 60.96, y + 6.35), 0, 'VAP', 'GND', 'VCA (+) input load: carries I_D / 2 (0.5 V)', text=R_LEFT)
    psym(c, 'GND', (x + 60.96, y + 10.16))
    R(c, 'R7', '10k', (x + 71.12, y - 5.08), 0, '+12V', 'DBA', 'Linearizing-diode bias: I_D = (11.6 V - 1.1 V) / 10k = 1.05 mA',
      text=R_LEFT)
    psym(c, '+12V', (x + 71.12, y - 8.89))
    ota(c, 'U5', 3, (x + 86.36, y + 5.08), 'VSUM', 'VAN', 'VAP', 'IABC_A', bias='DBA', mirror='x',
        note='DRIVE VCA: linearized OTA, gain = 2 x I_ABC / I_D x R8 / R3')
    R(c, 'R5', '1k', (x + 68.58, y + 16.51), 0, 'VAN', 'GND', 'VCA (-) input load (= R4)', text=R_LEFT)
    R(c, 'R6', '15k', (x + 76.2, y + 16.51), 0, 'VAN', 'GND', 'Balances R3 at the (-) input: no systematic VCA offset')
    psym(c, 'GND', (x + 68.58, y + 20.32))
    psym(c, 'GND', (x + 76.2, y + 20.32))
    R(c, 'R8', '120k', (x + 111.76, y - 2.54), 90, 'VSUM', 'U', 'VCA current-to-voltage: U = -I_out x 120k', text=FB_TEXT)
    C(c, 'C4', '22p', (x + 111.76, y - 10.16), 90, 'VSUM', 'U', 'VCA I-V roll-off (60 kHz)', text=CF_TEXT)
    opamp(c, 'U1', 2, (x + 111.76, y + 7.62), 'U', 'VSUM', 'GND', note='VCA current-to-voltage converter')
    psym(c, 'GND', (x + 101.6, y + 10.16))
    C(c, 'C5', '10u', (x + 132.08, y + 7.62), 90, 'U', 'UA', 'AC coupling (7 Hz): keeps the VCA offset (x drive gain) out of the cells',
      fp='C0805', volt='25V')
    R(c, 'R9', '2k', (x + 144.78, y + 7.62), 90, 'UA', 'X', 'Cell input divider top: X = U / 11')
    R(c, 'R10', '200', (x + 152.4, y + 11.43), 0, 'X', 'GND', 'Cell input divider bottom: 182R source for the five cell inputs')
    psym(c, 'GND', (x + 152.4, y + 15.24))

    # ---- Tanh cells: I = I_ABC x tanh(V_d / 2 V_T). B is the soft clipper (fixed I_0); C / D
    # (thresholds +/-theta, inverted) and E / F (+/-2 theta) are the fold pairs, all at f x I_0.
    y = YB
    for (ref, unit, name, mirror, sig_plus, refnet, rt, rb, cap, rail, inet, ri), cx in zip(CELL, CX):
        if sig_plus:
            ota(c, ref, unit, (cx, y), 'YS', refnet, 'X', inet, mirror=mirror,
                note=f'Cell {name}: ' + ('soft clipper, I_0 = 0.52 mA' if name == 'B' else f'fold cell, +tanh at {refnet}'))
        else:
            ota(c, ref, unit, (cx, y), 'YS', 'X', refnet, inet, mirror=mirror,
                note=f'Cell {name}: fold cell, -tanh at {refnet}')
        if rt is None:   # cell B: (-) input to GND through the X source resistance
            R(c, rb, '200', (cx - 10.16, y + 11.43), 0, refnet, 'GND', 'Cell B (-) input: matches the X divider source resistance',
              text=R_LEFT)
            psym(c, 'GND', (cx - 10.16, y + 15.24))
            R(c, ri, '20k', (cx + 21.59, y - 7.62), 90, inet, 'GND',
              'Cell B bias from GND: I_0 = (0 V - V(I_ABC pin, about -10.3 V)) / 20k = 0.52 mA', text=CF_TEXT)
            psym(c, 'GND', (cx + 25.4, y - 7.62), 90)
            continue
        top = '27k' if refnet[-1] == '1' else '13k'
        mv = {'27k': 198, '13k': 405}[top]
        R(c, rt, top, (cx - 25.4, y + 3.81), 0, rail, refnet, f'Fold threshold {refnet}: {rail} x 470 / ({top} + 470) = {mv} mV',
          text=R_LEFT)
        psym(c, rail, (cx - 25.4, y), 0, text=UP)
        R(c, rb, '470', (cx - 17.78, y + 11.43), 0, refnet, 'GND', f'Fold threshold {refnet} divider bottom', text=R_LEFT)
        psym(c, 'GND', (cx - 17.78, y + 15.24))
        C(c, cap, '10u', (cx - 10.16, y + 11.43), 0, refnet, 'GND', f'{refnet} supply-noise filter (34 Hz)',
          fp='C0805', volt='25V')
        psym(c, 'GND', (cx - 10.16, y + 15.24))
        xr = cx + (17.78 if mirror else 7.62)
        R(c, ri, '9.1k', (xr, y + 36.83), 0, inet, 'FC',
          f'Cell {name} bias share: a quarter of the FOLD current; with R24 / R25 it limits f to 1.06')
    xs = CX[4] + 40.64
    R(c, 'R21', '10k', (xs, y + 15.24), 90, 'YS', 'Y', 'Cell sum: Y = -I x 10k, +/-5.2 V at I_0', text=FB_TEXT)
    C(c, 'C10', '100p', (xs, y + 7.62), 90, 'YS', 'Y', 'Cell sum roll-off (160 kHz)', text=CF_TEXT)
    opamp(c, 'U2', 1, (xs, y + 25.4), 'Y', 'YS', 'GND', note='Cell current sum (transimpedance)')
    psym(c, 'GND', (xs - 10.16, y + 27.94))

    # ---- FOLD converter: I = (knob + CV) x (1 + R24 / R25) = x42.7, shared by the four fold cells.
    x, y = X0, YF
    jack(c, 'J3', (x, y), 'FCV', 'FOLD CV in (TS), 0..5 V = fold 0..1, adds to the knob; TN grounds the unpatched input')
    psym(c, 'GND', (x + 7.62, y + 2.54))
    psym(c, 'GND', (x + 7.62, y - 2.54), 90)
    c.append(part('RV2', 'R_Potentiometer', '50k', 'RV09', (x + 12.7, y - 17.78), 0,
                  {'3': '+12V', '1': 'GND', '2': 'FW'}, mirror='x', text=((-6.35, -1.27), (-6.35, 1.27)),
                  Taper='B (linear)', Note='FOLD: pin 3 (CW) = +12V, pin 1 (CCW) = GND. ' + POTNOTE))
    psym(c, '+12V', (x + 12.7, y - 21.59))
    psym(c, 'GND', (x + 12.7, y - 13.97))
    R(c, 'R22', '240k', (x + 24.13, y - 17.78), 90, 'FW', 'FSUM', 'FOLD knob: 11.6 V / 240k = 48 uA at max = fold 1.0')
    R(c, 'R23', '100k', (x + 17.78, y), 90, 'FCV', 'FSUM', 'FOLD CV: 5 V / 100k = 50 uA = fold 1.0; 100k input impedance')
    opamp(c, 'U4', 2, (x + 48.26, y + 2.54), 'FB', 'FSUM', 'GND', note='FOLD voltage-to-current converter')
    psym(c, 'GND', (x + 38.1, y + 5.08))
    c.append(part('D3', '1N4148W', '1N4148W', 'SOD123', (x + 48.26, y - 7.62), 0, {'1': 'FSUM', '2': 'FB'},
                  text=FB_TEXT, Note='Holds U4B at +0.5 V for a negative sum: Q3 base-emitter never reverse-biased'))
    C(c, 'C11', '100p', (x + 48.26, y - 15.24), 90, 'FSUM', 'FB', 'FOLD converter compensation', text=CF_TEXT)
    R(c, 'R24', '100k', (x + 48.26, y - 25.4), 90, 'FSUM', 'FE', 'FOLD converter feedback: V(FE) = -I_in x 100k', text=FB_TEXT)
    R(c, 'R25', '2.4k', (x + 95.25, y - 25.4), 90, 'FE', 'GND', 'Current gain 1 + R24 / R25 = 42.7: 50 uA in = 4 x 0.53 mA out')
    psym(c, 'GND', (x + 99.06, y - 25.4), 90)
    R(c, 'R26', '47k', (x + 66.04, y + 2.54), 90, 'FB', 'FBB', 'Q3 base resistor: no bias fold-back when Q3 saturates at the limit')
    c.append(part('Q3', 'Q_PNP_BEC', 'SS8550', 'SOT23', (x + 82.55, y + 2.54), 0, {'1': 'FBB', '2': 'FE', '3': 'FC'},
                  mirror='x', text=((7.62, -1.27), (7.62, 1.27)), Note='FOLD current source into the four fold cells'))

    # ---- DRIVE converter: exponential, I_ABC = I_ref x exp(V(DVC) / V_T), 6.5 dB / V at the jack.
    x = XD
    jack(c, 'J2', (x, y), 'DCV', 'DRIVE CV in (TS), +6.5 dB / V, adds to the knob; TN grounds the unpatched input')
    psym(c, 'GND', (x + 7.62, y + 2.54))
    psym(c, 'GND', (x + 7.62, y - 2.54), 90)
    c.append(part('RV1', 'R_Potentiometer', '50k', 'RV09', (x + 12.7, y - 17.78), 0,
                  {'3': '+12V', '1': 'GND', '2': 'DW'}, mirror='x', text=((-6.35, -1.27), (-6.35, 1.27)),
                  Taper='B (linear)', Note='DRIVE: pin 3 (CW) = +12V, pin 1 (CCW) = GND. ' + POTNOTE))
    psym(c, '+12V', (x + 12.7, y - 21.59))
    psym(c, 'GND', (x + 12.7, y - 13.97))
    R(c, 'R31', '240k', (x + 24.13, y - 17.78), 90, 'DW', 'DVC', 'DRIVE knob: 0..94 mV at DVC = x39 (32 dB)')
    R(c, 'R32', '100k', (x + 17.78, y), 90, 'DCV', 'DVC', 'DRIVE CV: 19.4 mV / V at DVC = 6.5 dB / V; 102k input impedance')
    R(c, 'R33', '2k', (x + 35.56, y + 3.81), 0, 'DVC', 'GND', 'DVC divider bottom')
    psym(c, 'GND', (x + 35.56, y + 7.62))
    c.append(part('Q1', 'Q_PNP_BEC', 'SS8550', 'SOT23', (x + 50.8, y), 0, {'1': 'DVC', '2': 'DE', '3': 'DREF'},
                  mirror='x', text=((-2.54, -8.89), (-2.54, -6.35)), Note='Expo pair, reference side: U4A holds I_C = I_ref. Place against Q2'))
    c.append(part('Q2', 'Q_PNP_BEC', 'SS8550', 'SOT23', (x + 76.2, y), 0, {'1': 'GND', '2': 'DE', '3': 'IABC_A'},
                  mirror='x', text=((7.62, -1.27), (7.62, 1.27)), Note='Expo pair, output side: I_C = I_ref x exp(V(DVC) / V_T) into the VCA'))
    psym(c, 'GND', (x + 68.58, y), 270)
    R(c, 'R35', '10k', (x + 66.04, y - 13.97), 0, 'DO', 'DE', 'Emitter feed: limits I_ABC to about (10.2 V - 0.7 V) / 10k = 0.95 mA')
    c.append(part('D4', '1N4148W', '1N4148W', 'SOD123', (x + 86.36, y - 6.35), 270, {'1': 'DE', '2': 'GND'},
                  text=((6.35, -1.27), (8.89, 1.27)), Note='Keeps DE above -0.6 V: Q1 / Q2 base-emitter never reverse-biased'))
    psym(c, 'GND', (x + 86.36, y - 2.54))
    R(c, 'R34', '1M', (x + 53.34, y + 19.05), 0, 'DREF', '-12V', 'I_ref = 11.6 V / 1M = 11.6 uA', text=R_LEFT)
    psym(c, '-12V', (x + 53.34, y + 22.86), 180)
    opamp(c, 'U4', 1, (x + 71.12, y + 17.78), 'DO', 'DREF', 'GND', text=((2.54, 7.62), (2.54, 10.16)),
          note='DRIVE exponential converter: servo of the reference transistor')
    psym(c, 'GND', (x + 60.96, y + 20.32))
    C(c, 'C12', '100p', (x + 71.12, y + 38.1), 90, 'DREF', 'DO', 'Expo converter compensation', text=FB_TEXT)

    # ---- TONE (wet only) -> MIX -> output inverter -> OUT
    x, y = X0, YE
    s = x + 5.08
    C(c, 'C13', '10u', (x + 11.43, y), 90, 'Y', 'YA', 'AC coupling of the wet path (0.02 Hz): removes the cell offset',
      fp='C0805', volt='25V')
    R(c, 'R36', '2k', (x + 24.13, y), 90, 'YA', 'TA', 'TONE end stop: 17 kHz at max')
    c.append(part('RV3', 'R_Potentiometer', '50k', 'RV09', (x + 38.1, y), 270,
                  {'3': 'TA', '1': 'TN', '2': 'TN'}, text=((0, -6.35), (0, -3.81)),
                  Taper='B (linear)', Note='TONE: rheostat pin 3 (CW) to the wiper, 0 Ohm at max = bright; '
                                           'pin 1 tied to the wiper. ' + POTNOTE))
    C(c, 'C14', '4.7n', (x + 49.53, y + 3.81), 0, 'TN', 'GND', 'TONE low-pass: 17 kHz (2k) .. 650 Hz (52k)')
    psym(c, 'GND', (x + 49.53, y + 7.62))
    R(c, 'R37', '1M', (s + 57.15, y + 3.81), 0, 'TN', 'GND', 'DC return of the tone buffer')
    psym(c, 'GND', (s + 57.15, y + 7.62))
    opamp(c, 'U2', 2, (s + 71.12, y + 2.54), 'WET', 'WET', 'TN', mirror=None, text=OPAMP_ABOVE, note='Tone buffer: WET')
    c.append(part('RV4', 'R_Potentiometer', '50k', 'RV09', (s + 91.44, y - 1.27), 0,
                  {'1': 'DRY', '3': 'WET', '2': 'MW'}, text=((-6.35, -6.35), (-6.35, -3.81)),
                  Taper='B (linear)', Note='MIX: pin 1 (CCW) = DRY, pin 3 (CW) = WET, both inverted. ' + POTNOTE))
    opamp(c, 'U3', 1, (s + 109.22, y + 1.27), 'MB', 'MB', 'MW', mirror=None, text=OPAMP_ABOVE, note='Mix follower')
    R(c, 'R38', '100k', (s + 127, y + 1.27), 90, 'MB', 'OINV', 'Output inverter input')
    R(c, 'R39', '100k', (s + 142.24, y - 6.35), 90, 'OINV', 'OA', 'Output inverter feedback (gain -1): OUT has the input polarity',
      text=FB_TEXT)
    C(c, 'C15', '47p', (s + 142.24, y - 13.97), 90, 'OINV', 'OA', 'Output roll-off (34 kHz)', text=CF_TEXT)
    opamp(c, 'U3', 2, (s + 142.24, y + 3.81), 'OA', 'OINV', 'GND', note='Output inverter')
    psym(c, 'GND', (s + 132.08, y + 6.35))
    R(c, 'R40', '1k', (s + 162.56, y + 3.81), 90, 'OA', 'OUT',
      'Output series / short-circuit and mis-patch protection, 1 W 2512 (as modules/vca-mix): '
      '~0.51 W with a -12 V source patched in against +10.5 V', fp='R2512')
    jack(c, 'J4', (s + 177.8, y + 3.81), 'OUT', 'Audio out (TS)', rot=180, tn=None)
    psym(c, 'GND', (s + 170.18, y + 6.35))

    # ---- Supply pins with their decoupling; unused Darlington buffers (open)
    for ref, sym, xu, yu in CELLS:
        if sym == 'TL072':
            power_cell(c, ref, sym, 'TL072CDT', 'SOIC8', xu, yu, 'Dual JFET op amp on +/-12 V (after D1 / D2)')
        else:
            power_cell(c, ref, sym, 'LM13700', 'SOIC16', xu, yu, 'Dual OTA on +/-12 V (after D1 / D2); buffers unused')
    for k, ref in enumerate(('U5', 'U6', 'U7')):
        for j, (unit, pi, po) in enumerate(((4, '7', '8'), (2, '10', '9'))):
            c.append(part(ref, 'LM13700', 'LM13700', 'SOIC16', (XBUF + k * 25.4, YBUF + j * 15.24), 0,
                          {pi: None, po: None}, unit=unit, text=((-2.54, -8.89), (-2.54, -6.35)),
                          Note='Unused Darlington buffer: input and output left open (LM13700 datasheet)'))
    for p in c:
        if not p['ref'].startswith('#'):
            p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def line(*pts):
    """Polyline without repeated points."""
    out = []
    for pt in pts:
        if not out or out[-1] != pt:
            out.append(pt)
    return out


def wiring(P):
    """Wire polylines between pin ends and the labels. build() splits T-joints, adds junction
    dots and checks the netlist."""
    w, lab = [], []
    d = DXP
    # Power entry (modules/vca-mix): J10 GND pins bussed per side, +12V_IN / -12V_IN pairs joined.
    for xa, xb, xg in ((d + 38.1, d + 35.56, d + 33.02), (d + 50.8, d + 53.34, d + 55.88)):
        w += [[(xa, yy), (xb, yy)] for yy in (55.88, 58.42, 60.96)]
        w += [[(xb, 55.88), (xb, 60.96)], [(xb, 59.69), (xg, 59.69)]]
    w += [[(d + 38.1, 53.34), (d + 30.48, 53.34), (d + 30.48, 45.72), (d + 67.31, 45.72)],
          [(d + 50.8, 53.34), (d + 60.96, 53.34), (d + 60.96, 45.72)],
          [(d + 38.1, 63.5), (d + 30.48, 63.5), (d + 30.48, 71.12), (d + 67.31, 71.12)],
          [(d + 50.8, 63.5), (d + 60.96, 63.5), (d + 60.96, 71.12)],
          [(d + 74.93, 45.72), (d + 106.68, 45.72)], [(d + 74.93, 71.12), (d + 106.68, 71.12)],
          [(d + 86.36, 53.34), (d + 86.36, 63.5)], [(d + 86.36, 58.42), (d + 91.44, 58.42)]]
    lab += [('+12V_IN', (d + 40.64, 45.72)), ('-12V_IN', (d + 40.64, 71.12))]

    # ---- input buffer + VCA
    x, y = X0, YA
    w += [
        [P('J1', 'S'), (x + 7.62, y + 2.54)], [P('J1', 'TN'), (x + 7.62, y - 2.54)],
        [P('J1', 'T'), P('R1', '1')],
        [P('R1', '2'), P('U1', '2')],
        [(x + 22.86, y), (x + 22.86, y - 15.24), P('C3', '1')], [(x + 22.86, y - 7.62), P('R2', '1')],
        [P('R2', '2'), (x + 43.18, y - 7.62)],
        [P('C3', '2'), (x + 43.18, y - 15.24), (x + 43.18, y + 2.54)],
        [P('U1', '3'), (x + 22.86, y + 5.08)],
        [P('U1', '1'), P('R3', '1')],
        [P('R3', '2'), P('U5', '3')],                                   # VAP (R4 hangs on it)
        [P('R7', '2'), (x + 71.12, y + 5.08), P('U5', '2')],            # DBA
        [P('U5', '4'), (x + 68.58, y + 7.62), P('R5', '1')],            # VAN
        [(x + 68.58, y + 12.7), P('R6', '1')],
        [P('U5', '5'), P('U1', '6')],                                   # VSUM
        [(x + 99.06, y + 5.08), (x + 99.06, y - 10.16), P('C4', '1')], [(x + 99.06, y - 2.54), P('R8', '1')],
        [P('R8', '2'), (x + 121.92, y - 2.54)],
        [P('C4', '2'), (x + 121.92, y - 10.16), (x + 121.92, y + 7.62)],
        [P('U1', '5'), (x + 101.6, y + 10.16)],
        [P('U1', '7'), P('C5', '1')],                                   # U
        [P('C5', '2'), P('R9', '1')],                                   # UA
        [P('R9', '2'), (x + 160.02, y + 7.62)],                         # X (R10 hangs on it)
        [P('U5', '1'), (x + 93.98, y - 17.78)],                         # IABC_A up to its label
    ]
    lab += [('IN', (x + 8.89, y)), ('INV', (x + 22.86, y - 3.81)), ('DRY', (x + 44.45, y + 2.54)),
            ('VAP', (x + 63.5, y + 2.54)), ('DBA', (x + 72.39, y + 5.08)), ('VAN', (x + 69.85, y + 12.7)),
            ('VSUM', (x + 99.06, y - 5.08)), ('U', (x + 123.19, y + 7.62)), ('UA', (x + 137.16, y + 7.62)),
            ('X', (x + 160.02, y + 7.62)), ('IABC_A', (x + 93.98, y - 17.78))]

    # ---- cells
    y = YB
    yx, yys, yfc = y - 17.78, y + 22.86, y + 40.64
    w += [[(CX[0] - 20.32, yx), (CX[4] - 12.7, yx)]]                    # X bus
    lab += [('X', (CX[0] - 20.32, yx))]
    for (ref, unit, name, mirror, sig_plus, refnet, rt, rb, cap, rail, inet, ri), cx in zip(CELL, CX):
        i, b, p_, m, o = {3: ('1', '2', '3', '4', '5'), 1: ('16', '15', '14', '13', '12')}[unit]
        top, bot = (p_, m) if mirror else (m, p_)
        w += [[(cx - 12.7, yx), (cx - 12.7, y - 2.54), P(ref, top)],    # X drop to the upper input
              [P(ref, o), (cx + 12.7, y), (cx + 12.7, yys)]]            # output down to the YS bus
        if rt is None:
            w += [[P(ref, bot), (cx - 10.16, y + 2.54), P(rb, '1')],
                  [P(ref, i), (cx + 7.62, y - 7.62), P(ri, '1')]]
            lab += [(refnet, (cx - 10.16, y + 5.08)), (inet, (cx + 10.16, y - 7.62))]
            continue
        w += [[P(ref, bot), (cx - 10.16, y + 2.54), P(cap, '1')],        # reference node
              [P(cap, '1'), P(rt, '2')]]
        if mirror:
            xr = cx + 17.78
            w += [[P(ref, i), (cx + 7.62, y - 7.62), (xr, y - 7.62), P(ri, '1')]]
        else:
            w += [[P(ref, i), P(ri, '1')]]
        lab += [(refnet, (cx - 22.86, y + 7.62)), (inet, (P(ri, '1')[0], y + 30.48))]
    xs = CX[4] + 40.64
    w += [[(CX[0] + 12.7, yys), P('U2', '2')],                          # YS bus
          [(xs - 12.7, yys), (xs - 12.7, y + 7.62), P('C10', '1')], [(xs - 12.7, y + 15.24), P('R21', '1')],
          [P('R21', '2'), (xs + 10.16, y + 15.24)],
          [P('C10', '2'), (xs + 10.16, y + 7.62), (xs + 10.16, y + 25.4)],
          [P('U2', '3'), (xs - 10.16, y + 27.94)],
          [P('U2', '1'), (xs + 15.24, y + 25.4)],                       # Y to its label
          [P('R27', '2'), P('R30', '2')]]                               # FC bus
    lab += [('YS', (CX[4] + 21.59, yys)), ('Y', (xs + 15.24, y + 25.4)), ('FC', (CX[2] + 12.7, yfc))]

    # ---- FOLD converter
    x, y = X0, YF
    w += [
        [P('J3', 'S'), (x + 7.62, y + 2.54)], [P('J3', 'TN'), (x + 7.62, y - 2.54)],
        [P('J3', 'T'), P('R23', '1')],
        [P('R23', '2'), P('U4', '6')],                                  # FSUM line
        [P('RV2', '2'), P('R22', '1')],
        [P('R22', '2'), (x + 30.48, y - 17.78), (x + 30.48, y)],
        [(x + 35.56, y), (x + 35.56, y - 25.4), P('R24', '1')],
        [(x + 35.56, y - 15.24), P('C11', '1')], [(x + 35.56, y - 7.62), P('D3', '1')],
        [P('D3', '2'), (x + 58.42, y - 7.62)],
        [P('C11', '2'), (x + 58.42, y - 15.24), (x + 58.42, y + 2.54)],
        [P('U4', '5'), (x + 38.1, y + 5.08)],
        [P('U4', '7'), P('R26', '1')],                                  # FB
        [P('R26', '2'), P('Q3', '1')],                                  # FBB
        [P('R24', '2'), P('R25', '1')],                                 # FE
        [P('Q3', '2'), (x + 85.09, y - 25.4)],
        [P('Q3', '3'), (x + 85.09, y + 10.16), (x + 106.68, y + 10.16), (x + 106.68, YB + 40.64)],   # FC up to the bus
    ]
    lab += [('FCV', (x + 8.89, y)), ('FW', (x + 16.51, y - 17.78)), ('FSUM', (x + 30.48, y - 5.08)),
            ('FB', (x + 58.42, y - 2.54)), ('FBB', (x + 71.12, y + 2.54)), ('FE', (x + 66.04, y - 25.4))]

    # ---- DRIVE converter
    x = XD
    w += [
        [P('J2', 'S'), (x + 7.62, y + 2.54)], [P('J2', 'TN'), (x + 7.62, y - 2.54)],
        [P('J2', 'T'), P('R32', '1')],
        [P('R32', '2'), P('Q1', '1')],                                  # DVC line (R33 hangs on it)
        [P('RV1', '2'), P('R31', '1')],
        [P('R31', '2'), (x + 30.48, y - 17.78), (x + 30.48, y)],
        [P('Q1', '2'), (x + 53.34, y - 10.16), (x + 86.36, y - 10.16)],  # DE (R35, Q2, D4 on it)
        [P('Q2', '2'), (x + 78.74, y - 10.16)],
        [P('Q2', '1'), (x + 68.58, y)],
        [P('Q1', '3'), P('R34', '1')],                                  # DREF
        [(x + 53.34, y + 15.24), P('U4', '2')],
        [(x + 58.42, y + 15.24), (x + 58.42, y + 38.1), P('C12', '1')],
        [P('U4', '3'), (x + 60.96, y + 20.32)],
        [P('U4', '1'), (x + 101.6, y + 17.78), (x + 101.6, y - 17.78), P('R35', '1')],   # DO
        [P('C12', '2'), (x + 83.82, y + 38.1), (x + 83.82, y + 17.78)],
        [P('Q2', '3'), (x + 78.74, y + 7.62), (x + 88.9, y + 7.62)],     # IABC_A to its label
    ]
    lab += [('DCV', (x + 8.89, y)), ('DW', (x + 16.51, y - 17.78)), ('DVC', (x + 38.1, y)),
            ('DE', (x + 55.88, y - 10.16)), ('DREF', (x + 53.34, y + 12.7)), ('DO', (x + 86.36, y + 17.78)),
            ('IABC_A', (x + 88.9, y + 7.62))]

    # ---- TONE, MIX, output
    x, y = X0, YE
    s = x + 5.08
    w += [
        [(x, y), P('C13', '1')],                                        # Y from its label
        [P('C13', '2'), P('R36', '1')],
        [P('R36', '2'), P('RV3', '3')],
        [P('RV3', '1'), P('U2', '5')],                                  # TN line (C14, R37 hang on it)
        [P('RV3', '2'), (x + 38.1, y + 6.35), (x + 44.45, y + 6.35), (x + 44.45, y)],
        [P('U2', '6'), (s + 63.5, y + 12.7), (s + 81.28, y + 12.7), (s + 81.28, y + 2.54)],
        [P('U2', '7'), P('RV4', '3')],                                  # WET
        [P('RV4', '1'), (s + 91.44, y - 10.16)],                        # DRY to its label
        [P('RV4', '2'), P('U3', '3')],                                  # MW
        [P('U3', '2'), (s + 101.6, y + 8.89), (s + 119.38, y + 8.89), (s + 119.38, y + 1.27)],
        [P('U3', '1'), P('R38', '1')],                                  # MB
        [P('R38', '2'), P('U3', '6')],                                  # OINV
        [(s + 132.08, y + 1.27), (s + 132.08, y - 13.97), P('C15', '1')], [(s + 132.08, y - 6.35), P('R39', '1')],
        [P('R39', '2'), (s + 152.4, y - 6.35)],
        [P('C15', '2'), (s + 152.4, y - 13.97), (s + 152.4, y + 3.81)],
        [P('U3', '5'), (s + 132.08, y + 6.35)],
        [P('U3', '7'), P('R40', '1')],                                  # OA
        [P('R40', '2'), P('J4', 'T')],                                  # OUT
        [P('J4', 'S'), (s + 170.18, y + 6.35)],
    ]
    lab += [('Y', (x, y)), ('YA', (x + 16.51, y)), ('TA', (x + 29.21, y)), ('TN', (x + 50.8, y)),
            ('WET', (s + 82.55, y + 2.54)), ('DRY', (s + 91.44, y - 10.16)), ('MW', (s + 96.52, y - 1.27)),
            ('MB', (s + 120.65, y + 1.27)), ('OINV', (s + 132.08, y - 2.54)), ('OA', (s + 153.67, y + 3.81)),
            ('OUT', (s + 167.64, y + 3.81))]

    # ---- supply pins
    for ref, sym, xu, yu in CELLS:
        vp, vn = {'TL072': ('8', '4'), 'LM13700': ('11', '6')}[sym]
        cp, cm = CELL_CAPS[ref]
        w += [[P(ref, vp), (xu - 2.54, yu - 10.16), P(cp, '1')],
              [P(ref, vn), (xu - 2.54, yu + 10.16), P(cm, '2')],
              [P(cp, '2'), P(cm, '1')], [(xu + 7.62, yu), (xu + 12.7, yu)]]
    w = [[(r(xx), r(yy)) for xx, yy in line(*ln)] for ln in w]
    lab = [(nm, (r(xx), r(yy)), 0) for nm, (xx, yy) in lab]
    return [(a, b) for ln in w for a, b in zip(ln, ln[1:])], lab


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Live strict lookups, 2026-11-15 (docs/sourcing-candidates.json). Basic except: LM13700MX/NOPB
# and the 1 W 2512 1k (Extended), 240k (Preferred Extended: no feeder fee).
# The THT jacks, pots and the power header are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '200', 'R0603'): dict(LCSC='C8218', MPN='0603WAF2000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '470', 'R0603'): dict(LCSC='C23179', MPN='0603WAF4700T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2k', 'R0603'): dict(LCSC='C22975', MPN='0603WAF2001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2.4k', 'R0603'): dict(LCSC='C22940', MPN='0603WAF2401T5E', Manufacturer='UNI-ROYAL'),
    ('R', '9.1k', 'R0603'): dict(LCSC='C23260', MPN='0603WAF9101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '13k', 'R0603'): dict(LCSC='C22797', MPN='0603WAF1302T5E', Manufacturer='UNI-ROYAL'),
    ('R', '15k', 'R0603'): dict(LCSC='C22809', MPN='0603WAF1502T5E', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0603'): dict(LCSC='C4184', MPN='0603WAF2002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '27k', 'R0603'): dict(LCSC='C22967', MPN='0603WAF2702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '120k', 'R0603'): dict(LCSC='C25808', MPN='0603WAF1203T5E', Manufacturer='UNI-ROYAL'),
    ('R', '240k', 'R0603'): dict(LCSC='C4197', MPN='0603WAF2403T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1M', 'R0603'): dict(LCSC='C22935', MPN='0603WAF1004T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R2512'): dict(LCSC='C54315', MPN='25121WF1001T4E', Manufacturer='UNI-ROYAL'),
    ('C', '20p', 'C0603'): dict(LCSC='C1648', MPN='CL10C200JB8NNNC', Manufacturer='Samsung'),
    ('C', '22p', 'C0603'): dict(LCSC='C1653', MPN='CL10C220JB8NNNC', Manufacturer='Samsung'),
    ('C', '47p', 'C0603'): dict(LCSC='C1671', MPN='CL10C470JB8NNNC', Manufacturer='Samsung'),
    ('C', '100p', 'C0603'): dict(LCSC='C14858', MPN='CL10C101JB8NNNC', Manufacturer='Samsung'),
    ('C', '4.7n', 'C0603'): dict(LCSC='C53987', MPN='0603B472K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('Q_PNP_BEC', 'SS8550', 'SOT23'): dict(LCSC='C8542', MPN='SS8550 Y2', Manufacturer='CJ (Jiangsu Changjing)'),
    ('TL072', 'TL072CDT', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
    ('LM13700', 'LM13700', 'SOIC16'): dict(LCSC='C174050', MPN='LM13700MX/NOPB', Manufacturer='Texas Instruments'),
}

TEXT_AT = {
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '+12V': ((0, -6.35), (0, -3.81)),
    '-12V': ((0, 6.35), (0, 3.81)),
}
SHOW_VALUE = {'+12V', '-12V'}  # power symbols whose value text is drawn

TEXTS = [
    ((20.32, 15.24), f'BIG MODULAR DRIVE - {REV} schematic: OTA overdrive + wavefolder (3 x LM13700), DRIVE and FOLD under CV, TONE, dry / wet MIX. '
                     'Circuit intent and ngspice results: docs/research.md', 2.0),
    ((X0, YA + 30.48), 'INPUT + DRIVE VCA: IN -> -1 buffer (DRY) -> 15k -> OTA U5 (pins 1-5) with its linearizing diodes (I_D 1.05 mA):\n'
                       'I_out = I_s x 2 I_ABC / I_D -> U1B (120k) -> U. Gain IN -> U = 0.11 (DRIVE min) .. 4.2 (max), exponential in the knob.\n'
                       'U -> 10u -> 2k / 200R -> X (U / 11): the cells see 52 mV (2 V_T) per 0.57 V of U.', 1.27),
    ((CX[0] - 22.86, YB - 26.67), 'TANH CELLS (one LM13700 half each, no linearizing diodes): I = I_ABC x tanh(V_d / 2 V_T). Outputs summed on YS -> U2A (10k) -> Y.\n'
                                  'B: soft clipper at I_0 = 0.52 mA. C / D: -tanh at X = +/-198 mV. E / F: +tanh at X = +/-405 mV. C..F run at f x I_0 (FOLD):\n'
                                  'Y / 5.2 V = -[tanh(x) - f (tanh(x - t) + tanh(x + t)) + f (tanh(x - 2t) + tanh(x + 2t))], x = X / 52 mV, t = 3.8.\n'
                                  'f = 0: plain tanh overdrive. f = 1: two folds per side; the outer level stays at +/-5.2 V for every f.', 1.27),
    ((X0, YF + 20.32), 'FOLD: knob (0..48 uA) + CV (10 uA / V) -> U4B / Q3, current gain 42.7 -> four fold cells through 9.1k each.\n'
                       'f = 1.0 at knob max or 5 V CV; limited to f = 1.06 (Q3 saturates, R26 stops the fold-back).\n'
                       'Negative sums switch the fold cells off (D3).', 1.27),
    ((XD + 25.4, YF - 26.67), 'DRIVE: exponential converter (Q1 / Q2, same reel, side by side on the board).\n'
                              'V(DVC) = knob x 94 mV + CV x 19.4 mV / V; I_ABC = I_ref x exp(V(DVC) / 25.9 mV):\n'
                              'about 15 uA .. 0.59 mA over the knob (32 dB), 6.5 dB / V at the jack, limit about 0.95 mA (R35).\n'
                              'Small-signal gain IN -> OUT (wet): about x1 at DRIVE min, x35 at max.', 1.27),
    ((X0, YE + 20.32), 'WET PATH: Y -> 10u -> TONE (2k + 50k rheostat, 4.7n: 17 kHz .. 650 Hz) -> U2B (WET). MIX crossfades DRY (-IN) and WET (both inverted)\n'
                       '-> follower -> inverter -> 1k (2512) -> OUT: the output has the input polarity for dry and wet.', 1.27),
    ((DXP + 20.32, 86.36), 'POWER: Eurorack +12V / -12V -> B5819W per rail -> +12V / -12V (about +/-11.6 V).\n+5V and pins 11-16 unused. '
                           '100n at every IC supply pin, 10u bulk per rail.\n15 .. 22 mA per rail (4 x TL072, 3 x LM13700; ngspice models).', 1.27),
    ((DXP + 20.32, 101.6), 'PWR_FLAG: #FLG01 marks the Eurorack GND; #FLG02/#FLG03 mark the +12V/-12V rails,\n'
                           'fed from the header only through D1/D2, which ERC cannot see through.', 1.1),
    ((XBUF - 12.7, YBUF - 12.7), 'Unused LM13700 Darlington buffers: left open.', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/drive/schematic/' + key))


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
        for num, kind in PIN_TYPE_EDITS.get(key, {}).items():
            pin = next(pp for pp in walk(sym, 'pin') if one(pp, 'number')[1] == num)
            edit = (edit + '; ' if edit else '') + f'pin {num} type {pin[1]} -> {kind}'
            pin[1] = atom(kind)
        lib_syms[key] = sym
        sources[key] = {'library': f'{lib}:{name}', 'source': str(src).replace(str(Path.home()), '~', 1),
                        'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                        'flattened_from': parent, 'edits': edit}
    stock_header = parse((STOCK / 'Device.kicad_sym').read_text())
    lib = [atom('kicad_symbol_lib'), one(stock_header, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(lib_syms[k]) for k in sorted(lib_syms)]
    HW.mkdir(exist_ok=True)
    (HW / f'{LIBNAME}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIBNAME}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIBNAME}.kicad_sym") '
        '(options "") (descr "DRIVE module pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - DRIVE") (rev "{REV}") (company "Big Modular")
        (comment 1 "SCHEMATIC {REV} - OTA overdrive + wavefolder, 3 x LM13700, +-12 V, 6HP - not released")
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
    for ref, want in MULTI.items():
        assert units[ref] == want, (ref, units[ref])
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
    nparts = len({p['ref'] for p in parts if not p['ref'].startswith('#')})
    print(out, f'{nparts} parts, {len(nets)} nets, native netlist equals circuit()')


if __name__ == '__main__':
    build()
