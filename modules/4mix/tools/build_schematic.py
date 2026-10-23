"""Generate the S2 4MIX schematic (hierarchical) and its pinned symbols.

Run from modules/4mix:
  python3 -B tools/build_schematic.py

Writes hardware/4MIX.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the 4MIX library), hardware/sym-lib-table, the root sheet
hardware/4mix.kicad_sch and one channel sheet hardware/channel.kicad_sch that the root
instantiates four times (CH1..CH4), then lets `kicad-cli sch upgrade --force` re-save them
natively. root() and channel() below are the circuit intent of docs/research.md section 3
(pin -> net) drawn as wires, stock power symbols (GND/+12V/-12V, global nets), one local
label per signal net and three hierarchical labels (MAIN_SUM, SENDA_SUM, SENDB_SUM) that
tie each channel onto the root summing buses. build() exports the native netlist and
asserts it equals the intent, so a misdrawn wire fails the build. Multi-unit symbols (the
TL072s) are placed one instance per unit.

Channel n's parts are numbered n01.. (CH1: J101, RV101-RV103, U101, R101-R108,
C101-C103); the root parts keep low numbers.

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
PROJECT = '4mix'
LIBNAME = '4MIX'
CHANNELS = (1, 2, 3, 4)
SHEET_FILE = 'channel.kicad_sch'
HIER = ('MAIN_SUM', 'SENDA_SUM', 'SENDB_SUM')  # channel -> root bus nets

FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
    'Conn_02x03_Odd_Even': '*_2x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'Conn_02x03_Odd_Even': ('Connector_Generic', 'Conn_02x03_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R2512': 'R_2512_6332Metric', 'C0603': 'C_0603_1608Metric',
    'C0805': 'C_0805_2012Metric', 'SOD123': 'D_SOD-123', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'RV09': 'Potentiometer_RV09', 'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'H2x5': 'PinHeader_2x05_P2.54mm_Vertical', 'H2x3': 'PinHeader_2x03_P2.54mm_Vertical',
}

POTNOTE = ('RV09 50k B (linear), user stock (no bushing/nut), on the Bread Modular RV09 footprint, '
           'hand-soldered. Pin 3 (CW) = drive, pin 1 (CCW) = GND')
JACKNOTE = 'QingPu WQP-PJ301M-12, hand-soldered'

# TL072 unit -> (inverting, non-inverting, output) pin numbers
OPAMP = {1: ('2', '3', '1'), 2: ('6', '5', '7')}

C_RIGHT = ((3.81, -1.27), (3.81, 1.27))  # texts beside a vertical capacitor
FB_TEXT = ((0, -2.54), (0, 2.54))        # texts above/below a horizontal feedback resistor
CF_TEXT = ((0, -5.08), (0, -2.54))       # both texts above the feedback capacitor
OPAMP_TEXT = ((0, 7.62), (0, 10.16))     # op-amp unit texts below the body
FOLLOW_TEXT = ((0, -7.62), (0, -5.08))   # follower texts above the body (loop below)


def r(v):
    return round(v, 2)


class Sheet:
    """Parts (pin -> net), wire segments, local labels and hierarchical labels of one sheet."""

    def __init__(self):
        self.parts, self.segs, self.labels, self.hlabels, self.texts = [], [], [], [], []
        self.npwr = 0

    def part(self, ref, sym, value, fp, at, rot, pins, unit=1, mirror=None, text=None, **fields):
        assert mirror is None or rot == 0, (ref, 'mirror only with rot 0')
        p = dict(ref=ref, sym=sym, value=value, fp=fp, at=(r(at[0]), r(at[1])), rot=rot, pins=pins,
                 unit=unit, mirror=mirror, text=text, fields=fields)
        self.parts.append(p)
        return p

    def psym(self, net, at, rot=0):
        """Stock power symbol (GND / +12V / -12V) with its pin at `at`.
        GND: rot 0 points down, 90 right, 180 up. +12V: rot 0 up. -12V: rot 180 down."""
        self.npwr += 1
        self.part(f'#PWR{self.npwr:02d}', net, net, None, at, rot, {'1': net})

    def wire(self, *pts):
        pts = [(r(x), r(y)) for x, y in pts]
        self.segs += list(zip(pts, pts[1:]))

    def label(self, net, at, ang=0):
        self.labels.append((net, (r(at[0]), r(at[1])), ang))

    def text(self, at, s, size=1.27):
        self.texts.append(((r(at[0]), r(at[1])), s, size))

    # ---- circuit macros -------------------------------------------------------------------
    def inverting(self, u, unit, xo, y, inv, out, rf, cf, note, rin=None, rin_net=None, rf_value='100k',
                  utext=OPAMP_TEXT):
        """Inverting stage: (-) on the line y at xo - 7.62, (+) to GND, output at (xo + 7.62, y + 2.54).
        Rf on y - 5.08, Cf on y - 12.7, both between the node x (xo - 10.16) and the output x
        (xo + 10.16). With rin, the input resistor ends at (xo - 20.32, y). Returns the output node."""
        neg, pos, o = OPAMP[unit]
        xn, xq = xo - 10.16, xo + 10.16
        self.part(u, 'TL072', 'TL072CDT', 'SOIC8', (xo, y + 2.54), 0, {neg: inv, pos: 'GND', o: out},
                  unit=unit, mirror='x', text=utext, Note=note)
        self.part(rf[0], 'R', rf_value, 'R0603', (xo, y - 5.08), 90, {'1': inv, '2': out}, text=FB_TEXT, Note=rf[1])
        self.part(cf[0], 'C', '20p', 'C0603', (xo, y - 12.7), 90, {'1': inv, '2': out}, text=CF_TEXT,
                  Voltage='50V', Note=cf[1])
        self.wire((xn, y), (xo - 7.62, y))
        self.wire((xn, y), (xn, y - 12.7))
        self.wire((xn, y - 5.08), (xo - 3.81, y - 5.08))
        self.wire((xn, y - 12.7), (xo - 3.81, y - 12.7))
        self.wire((xo + 3.81, y - 5.08), (xq, y - 5.08))
        self.wire((xo + 3.81, y - 12.7), (xq, y - 12.7))
        self.wire((xq, y - 12.7), (xq, y + 2.54))
        self.wire((xo + 7.62, y + 2.54), (xq, y + 2.54))
        self.wire((xo - 7.62, y + 5.08), (xn, y + 5.08))
        self.psym('GND', (xn, y + 5.08))
        if rin:
            self.part(rin[0], 'R', '100k', 'R0603', (xn - 6.35, y), 90, {'1': rin_net, '2': inv}, Note=rin[1])
            self.wire((xn - 2.54, y), (xn, y))
        return (xq, y + 2.54)

    def follower(self, u, unit, xo, y, inp, out, note):
        """Unity follower: (+) on the line y at xo - 7.62, (-) tied to the output below,
        output at (xo + 7.62, y + 2.54). Returns the output node."""
        neg, pos, o = OPAMP[unit]
        self.part(u, 'TL072', 'TL072CDT', 'SOIC8', (xo, y + 2.54), 0, {pos: inp, neg: out, o: out},
                  unit=unit, text=FOLLOW_TEXT, Note=note)
        xn, xq = xo - 10.16, xo + 10.16
        self.wire((xo - 7.62, y + 5.08), (xn, y + 5.08), (xn, y + 10.16), (xq, y + 10.16), (xq, y + 2.54))
        self.wire((xo + 7.62, y + 2.54), (xq, y + 2.54))
        return (xq, y + 2.54)

    def pot(self, ref, x, y, top, wiper, note, value='50k'):
        """Pot (mirror x): pin 3 (CW) at (x, y), pin 1 = GND at (x, y + 7.62), wiper at (x + 3.81, y + 3.81)."""
        self.part(ref, 'R_Potentiometer', value, 'RV09', (x, y + 3.81), 0, {'3': top, '1': 'GND', '2': wiper},
                  mirror='x', Taper='B (linear)', Note=note)
        self.psym('GND', (x, y + 7.62))
        return (x + 3.81, y + 3.81)

    def res(self, ref, value, x0, y, n1, n2, note, fp='R0603', **f):
        """Horizontal resistor with pin 1 at (x0, y), pin 2 at (x0 + 7.62, y)."""
        self.part(ref, 'R', value, fp, (x0 + 3.81, y), 90, {'1': n1, '2': n2}, Note=note, **f)
        return (x0 + 7.62, y)

    def shunt(self, ref, sym, value, x, y, net, note, **f):
        """Vertical R/C from the line point (x, y) down to GND (pin 2 at y + 7.62)."""
        self.part(ref, sym, value, 'R0603' if sym == 'R' else 'C0603', (x, y + 3.81), 0, {'1': net, '2': 'GND'},
                  text=C_RIGHT, Note=note, **f)
        self.psym('GND', (x, y + 7.62))

    def in_jack(self, ref, x, y, tip, note, text=None):
        """Input jack (mirror x): T at (x + 5.08, y); S and TN to GND (TN grounds an unpatched input)."""
        self.part(ref, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x, y), 0, {'T': tip, 'S': 'GND', 'TN': 'GND'},
                  mirror='x', text=text, Note=note)
        self.wire((x + 5.08, y + 2.54), (x + 7.62, y + 2.54))
        self.wire((x + 5.08, y - 2.54), (x + 7.62, y - 2.54))
        self.psym('GND', (x + 7.62, y + 2.54))
        self.psym('GND', (x + 7.62, y - 2.54), 90)
        return (x + 5.08, y)

    def out_jack(self, ref, x, y, tip, note):
        """Output jack (rot 180): T at (x - 5.08, y); S to GND; TN unused."""
        self.part(ref, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x, y), 180, {'T': tip, 'S': 'GND', 'TN': None},
                  Note=note)
        self.wire((x - 5.08, y + 2.54), (x - 7.62, y + 2.54))
        self.psym('GND', (x - 7.62, y + 2.54))
        return (x - 5.08, y)

    def opamp_power(self, u, x, y, caps, note):
        """TL072 power unit at (x, y) with V+ (pin 8) and V- (pin 4) on +12V / -12V rails at y -/+ 12.7
        and their 100n to GND at x + 10.16 (the rails are drawn by the caller)."""
        self.part(u, 'TL072', 'TL072CDT', 'SOIC8', (x, y), 0, {'4': '-12V', '8': '+12V'}, unit=3,
                  text=((-6.35, -1.27), (-6.35, 1.27)), Note=note)
        xc = x + 10.16
        self.part(caps[0], 'C', '100n', 'C0603', (xc, y - 8.89), 0, {'1': '+12V', '2': 'GND'},
                  text=C_RIGHT, Voltage='50V', Note=f'{u} V+ (pin 8) decoupling')
        self.part(caps[1], 'C', '100n', 'C0603', (xc, y + 8.89), 0, {'1': 'GND', '2': '-12V'},
                  text=C_RIGHT, Voltage='50V', Note=f'{u} V- (pin 4) decoupling')
        self.wire((xc, y - 5.08), (xc, y + 5.08))
        self.wire((xc, y), (xc + 5.08, y))
        self.psym('GND', (xc + 5.08, y))
        self.wire((x - 2.54, y - 12.7), (x - 2.54, y - 7.62))
        self.wire((x - 2.54, y + 7.62), (x - 2.54, y + 12.7))


def channel():
    """One mixer channel strip (Bread Modular 4mix channel on +/-12 V)."""
    s = Sheet()
    y = 60.96
    # Input: jack -> 100k -> inverting buffer (gain -1, 100k || 20p) -> 100R -> VOL pot.
    tip = s.in_jack('J01', 25.4, y, 'IN', 'Channel audio input (AC-coupled by C04); ' + JACKNOTE +
                    '; TN grounds the unpatched input')
    s.part('C04', 'C', '10u', 'C0805', (40.64, y), 90, {'1': 'IN', '2': '~IN_AC'}, text=FB_TEXT, Voltage='25V',
           Note='Input AC coupling (Bread Modular 10u): into the 100k R01, -3 dB at 0.16 Hz')
    s.wire(tip, (36.83, y))
    s.wire((44.45, y), (48.26, y))
    s.label('IN', (31.75, y))
    buf = s.inverting('U01', 1, 68.58, y, '~INV', 'BUF', ('R02', 'Input buffer feedback (gain -1)'),
                      ('C01', 'Input buffer HF roll-off / stability (~80 kHz with 100k)'),
                      'Channel inverting input buffer', rin=('R01', 'Input resistor: 100k Eurorack input impedance'),
                      rin_net='~IN_AC')
    end = s.res('R03', '100', 85.09, buf[1], 'BUF', '~VOL_TOP', 'Buffer output isolation into the VOL pot')
    s.wire(buf, (85.09, buf[1]))
    s.label('BUF', (80.01, buf[1]))
    s.wire(end, (101.6, end[1]))
    w = s.pot('RV01', 101.6, end[1], '~VOL_TOP', 'VOL_W', 'Channel VOL: ' + POTNOTE)
    # VOL wiper -> 100k -> MAIN_SUM (root main summer); the post-fader follower drives both sends.
    s.res('R04', '100k', 118.11, w[1], 'VOL_W', 'MAIN_SUM', 'Main summing resistor (unity at full CW)')
    s.wire(w, (118.11, w[1]))
    s.label('VOL_W', (106.68, w[1]))
    s.wire((125.73, w[1]), (190.5, w[1]))
    yb = 86.36
    s.wire((110.49, w[1]), (110.49, yb + 5.08), (119.38, yb + 5.08))
    post = s.follower('U01', 2, 127.0, yb + 5.08, 'VOL_W', 'POST', 'Post-fader buffer for the sends (Bread Modular 4mix)')
    s.label('POST', (138.43, post[1]))
    # Send A and send B: POST -> 100R -> send pot -> wiper -> 100k -> SENDx_SUM.
    for k, (yy, rr, rv, rs, top, wip, bus) in enumerate((
            (post[1], 'R05', 'RV02', 'R06', '~SA_TOP', '~SA_W', 'SENDA_SUM'),
            (post[1] + 20.32, 'R07', 'RV03', 'R08', '~SB_TOP', '~SB_W', 'SENDB_SUM'))):
        name = 'A' if k == 0 else 'B'
        e = s.res(rr, '100', 143.51, yy, 'POST', top, f'Send {name} pot drive isolation')
        s.wire(e, (157.48, yy))
        wi = s.pot(rv, 157.48, yy, top, wip, f'Channel SEND {name} (post-fader): ' + POTNOTE)
        s.res(rs, '100k', 168.91, wi[1], wip, bus, f'Send {name} summing resistor')
        s.wire(wi, (168.91, wi[1]))
        s.wire((176.53, wi[1]), (190.5, wi[1]))
        s.hlabels.append((bus, (190.5, r(wi[1]))))
    s.wire(post, (143.51, post[1]))
    s.wire((140.97, post[1]), (140.97, post[1] + 20.32), (143.51, post[1] + 20.32))
    s.hlabels.insert(0, ('MAIN_SUM', (190.5, r(w[1]))))
    # Power: U01 supply pins on the global +12V / -12V rails, 100n each.
    x, yp = 38.1, 106.68
    s.opamp_power('U01', x, yp, ('C02', 'C03'), 'Dual JFET op-amp on +/-12 V (after D1/D2 on the root sheet)')
    s.wire((x - 2.54, yp - 12.7), (x + 10.16, yp - 12.7))
    s.wire((x - 2.54, yp + 12.7), (x + 10.16, yp + 12.7))
    s.psym('+12V', (x - 2.54, yp - 12.7))
    s.psym('-12V', (x - 2.54, yp + 12.7), 180)
    s.text((20.32, 22.86), 'CHANNEL STRIP (one sheet, used 4 times: CH1..CH4; parts n01.. per channel)', 2.0)
    s.text((20.32, 30.48),
           'Bread Modular 4mix channel on +/-12 V: jack -> 10u -> 100k -> inverting buffer (100k || 20p, gain -1) -> 100R -> VOL (CW = pin 3).\n'
           'VOL wiper -> 100k -> MAIN_SUM. A unity follower buffers the wiper (post-fader) and drives SEND A / SEND B through 100R;\n'
           'each send wiper -> 100k -> SENDA_SUM / SENDB_SUM. Audio only: AC-coupled (10u into 100k, -3 dB at 0.16 Hz), 100k input\n'
           'impedance at any knob position; TN grounds an unpatched input. Full CW = unity gain (the root summers invert again, so MAIN/SEND outputs keep the input polarity).', 1.27)
    s.text((20.32, 132.08),
           'Taper: each wiper sees 100k to a virtual ground (as Bread Modular 4mix/imix), so the 50k B pots run slightly\n'
           'below linear (about 44 % at mid rotation).', 1.27)
    return s


def root():
    s = Sheet()
    # ---- Power: Eurorack +/-12 V -> series Schottky per rail -> +12V / -12V rails (as modules/imix).
    s.part('J8', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (45.72, 58.42), 180,
           {'1': '-12V_IN', '2': '-12V_IN', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
            '7': 'GND', '8': 'GND', '9': '+12V_IN', '10': '+12V_IN'},
           Note='Unshrouded vertical header on B, pin 1 (-12 V) at the board bottom; '
                'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)')
    s.psym('GND', (33.02, 59.69), 270)
    s.psym('GND', (55.88, 59.69), 90)
    s.part('D1', 'D_Schottky', 'B5819W', 'SOD123', (71.12, 45.72), 180, {'1': '+12V', '2': '+12V_IN'},
           Note='Series reverse-polarity protection, +12 V rail')
    s.part('D2', 'D_Schottky', 'B5819W', 'SOD123', (71.12, 71.12), 0, {'1': '-12V_IN', '2': '-12V'},
           Note='Series reverse-polarity protection, -12 V rail')
    s.part('C1', 'C', '10u', 'C0805', (86.36, 49.53), 0, {'1': '+12V', '2': 'GND'}, text=C_RIGHT,
           Voltage='25V', Note='+12 V bulk')
    s.part('C2', 'C', '10u', 'C0805', (86.36, 67.31), 0, {'1': 'GND', '2': '-12V'}, text=C_RIGHT,
           Voltage='25V', Note='-12 V bulk')
    s.part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (91.44, 58.42), 0, {'1': 'GND'})
    s.psym('GND', (91.44, 58.42))
    s.part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (96.52, 45.72), 0, {'1': '+12V'})
    s.part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (96.52, 71.12), 0, {'1': '-12V'})
    s.psym('+12V', (106.68, 45.72))
    s.psym('-12V', (106.68, 71.12), 180)
    for x0, x1, xg in ((38.1, 35.56, 33.02), (50.8, 53.34, 55.88)):
        for yy in (55.88, 58.42, 60.96):
            s.wire((x0, yy), (x1, yy))
        s.wire((x1, 55.88), (x1, 60.96))
        s.wire((x1, 59.69), (xg, 59.69))
    s.wire((38.1, 53.34), (30.48, 53.34), (30.48, 45.72), (67.31, 45.72))
    s.wire((50.8, 53.34), (60.96, 53.34), (60.96, 45.72))
    s.wire((38.1, 63.5), (30.48, 63.5), (30.48, 71.12), (67.31, 71.12))
    s.wire((50.8, 63.5), (60.96, 63.5), (60.96, 71.12))
    s.label('+12V_IN', (40.64, 45.72))
    s.label('-12V_IN', (40.64, 71.12))
    s.wire((74.93, 45.72), (236.22, 45.72))
    s.wire((74.93, 71.12), (236.22, 71.12))
    s.wire((86.36, 53.34), (86.36, 63.5))
    s.wire((86.36, 58.42), (91.44, 58.42))
    roles = {'U1': 'EXP MAIN inverter (A) + main summer (B)', 'U2': 'RETURN A / B buffers',
             'U3': 'output summer (A) + output inverter (B)', 'U4': 'EXP SEND A / B inverters',
             'U5': 'SEND A / SEND B summers'}
    for i, u in enumerate(('U1', 'U2', 'U3', 'U4', 'U5')):
        s.opamp_power(u, 124.46 + 25.4 * i, 58.42, (f'C{3 + 2 * i}', f'C{4 + 2 * i}'),
                      f'Dual JFET op-amp on +/-12 V (after D1/D2): {roles[u]}')

    # ---- Channel sheets CH1..CH4 and the three summing buses.
    xm, xa, xb = 88.9, 96.52, 104.14   # MAIN_SUM, SENDA_SUM, SENDB_SUM bus x
    tops = [101.6 + 25.4 * i for i in range(4)]
    sheets = []
    for n, top in zip(CHANNELS, tops):
        pins = {'MAIN_SUM': top + 5.08, 'SENDA_SUM': top + 10.16, 'SENDB_SUM': top + 15.24}
        sheets.append(dict(n=n, at=(25.4, top), size=(50.8, 20.32), pins=pins))
        for net, x in (('MAIN_SUM', xm), ('SENDA_SUM', xa), ('SENDB_SUM', xb)):
            s.wire((76.2, pins[net]), (x, pins[net]))
    ye = (215.9, 241.3, 266.7)          # EXP inverter input lines (MAIN, SEND A, SEND B)
    s.wire((xm, tops[0] + 5.08), (xm, ye[0] + 2.54))
    s.wire((xa, tops[0] + 10.16), (xa, ye[1] + 2.54))
    s.wire((xb, tops[0] + 15.24), (xb, ye[2] + 2.54))

    # ---- Summers: MAIN (U1B), SEND A (U5A), SEND B (U5B), inverting, 100k || 20p.
    ym, ya, yb = tops[0] + 5.08, 152.4, 198.12
    s.wire((xm, ym), (129.54, ym))
    s.wire((xa, tops[0] + 10.16), (114.3, tops[0] + 10.16), (114.3, ya), (129.54, ya))
    s.wire((xb, tops[0] + 15.24), (109.22, tops[0] + 15.24), (109.22, yb), (129.54, yb))
    s.label('MAIN_SUM', (116.84, ym))
    s.label('SENDA_SUM', (116.84, ya))
    s.label('SENDB_SUM', (111.76, yb))
    mix = s.inverting('U1', 2, 139.7, ym, 'MAIN_SUM', 'MAIN_MIX', ('R5', 'Main summer feedback (unity per channel)'),
                      ('C14', 'Main summer HF roll-off / stability'), 'Main summer (channels + EXP MAIN)')
    sa = s.inverting('U5', 1, 139.7, ya, 'SENDA_SUM', 'SENDA_MIX', ('R29', 'SEND A summer feedback'),
                     ('C19', 'SEND A summer HF roll-off / stability'), 'SEND A summer (channels + EXP SEND A)')
    sb = s.inverting('U5', 2, 139.7, yb, 'SENDB_SUM', 'SENDB_MIX', ('R32', 'SEND B summer feedback'),
                     ('C20', 'SEND B summer HF roll-off / stability'), 'SEND B summer (channels + EXP SEND B)')
    # MAIN_MIX -> 100R -> MASTER pot -> wiper -> 100k -> OUT_SUM; MAIN_MIX -> 1k -> EXP OUT pin 1.
    e = s.res('R7', '100', 153.67, mix[1], 'MAIN_MIX', '~MASTER_TOP', 'Main summer output isolation into the MAIN pot')
    s.wire(mix, (153.67, mix[1]))
    s.label('MAIN_MIX', (151.13, 121.92), 90)
    s.wire(e, (170.18, e[1]))
    mw = s.pot('RV1', 170.18, e[1], '~MASTER_TOP', '~MASTER_W', 'MAIN (master) volume, big-knob position: ' + POTNOTE)
    s.res('R8', '100k', 177.8, mw[1], '~MASTER_W', 'OUT_SUM', 'Master summing resistor into the output summer')
    s.wire(mw, (177.8, mw[1]))
    xbus, xsum = 299.72, 304.8    # OUT_SUM bus x, output summer node x
    s.wire((185.42, mw[1]), (xsum, mw[1]))
    s.wire((151.13, mix[1]), (151.13, 124.46), (153.67, 124.46))
    s.res('R6', '1k', 153.67, 124.46, 'MAIN_MIX', 'EXP_MAIN_OUT', 'EXP OUT main series resistor')
    s.wire((161.29, 124.46), (189.23, 124.46), (189.23, 160.02), (182.88, 160.02), (182.88, 165.1), (185.42, 165.1))
    s.label('EXP_MAIN_OUT', (163.83, 124.46))
    # SEND A / B -> 1k (2512) -> jacks; -> 1k -> EXP OUT pins 3 / 5.
    for k, (o, rj, rx, j, jn, xn, tipn, expn, yx) in enumerate((
            (sa, 'R30', 'R31', 'J1', 'SENDA_MIX', 'SENDA_OUT', 'SENDA_OUT', 'EXP_SA_OUT', 167.64),
            (sb, 'R33', 'R34', 'J2', 'SENDB_MIX', 'SENDB_OUT', 'SENDB_OUT', 'EXP_SB_OUT', 215.9))):
        name = 'A' if k == 0 else 'B'
        e = s.res(rj, '1k', 153.67, o[1], jn, tipn,
                  f'SEND {name} output series / mis-patch protection; 2512 (1 W): ~0.51 W with -12 V on +10.5 V', fp='R2512')
        s.wire(o, (153.67, o[1]))
        s.label(jn, (151.13, yx - 1.27), 90)
        t = s.out_jack(j, 179.07, o[1], tipn, f'SEND {name} output; ' + JACKNOTE)
        s.wire(e, t)
        s.label(tipn, (162.56, o[1]))
        xb_ = 151.13
        s.wire((xb_, o[1]), (xb_, yx), (153.67, yx))
        s.res(rx, '1k', 153.67, yx, jn, expn, f'EXP OUT send {name} series resistor')
        s.label(expn, (163.83, yx))
    s.wire((161.29, 167.64), (185.42, 167.64))
    s.wire((161.29, 215.9), (182.88, 215.9), (182.88, 170.18), (185.42, 170.18))
    s.part('J7', 'Conn_02x03_Odd_Even', 'EXP_OUT', 'H2x3', (190.5, 167.64), 0,
           {'1': 'EXP_MAIN_OUT', '2': 'GND', '3': 'EXP_SA_OUT', '4': 'GND', '5': 'EXP_SB_OUT', '6': 'GND'},
           Note='Expansion OUT (back of the board, no jack): pre-master MAIN mix and SEND A/B mixes, '
                'each with a GND neighbour; cable to the next module\'s EXP IN (J6)')
    s.wire((198.12, 165.1), (198.12, 172.72))
    s.psym('GND', (198.12, 172.72))

    # ---- EXP IN: J6 -> 1M pull-down -> inverting stage (100k / 100k || 20p) -> 100k -> bus.
    s.part('J6', 'Conn_02x03_Odd_Even', 'EXP_IN', 'H2x3', (20.32, ye[1]), 0,
           {'1': 'EXP_MAIN_IN', '2': 'GND', '3': 'EXP_SA_IN', '4': 'GND', '5': 'EXP_SB_IN', '6': 'GND'},
           mirror='y', Note='Expansion IN (back of the board, no jack): MAIN / SEND A / SEND B mixes from '
                            'another module\'s EXP OUT (J7), each with a GND neighbour')
    s.wire((12.7, ye[1] - 2.54), (12.7, ye[1] + 5.08))
    s.psym('GND', (12.7, ye[1] + 5.08))
    s.wire((25.4, ye[1] - 2.54), (30.48, ye[1] - 2.54), (30.48, ye[0]), (35.56, ye[0]))
    s.wire((25.4, ye[1]), (35.56, ye[1]))
    s.wire((25.4, ye[1] + 2.54), (30.48, ye[1] + 2.54), (30.48, ye[2]), (35.56, ye[2]))
    for k, (yy, u, unit, rpd, cac, rin, rf, cf, ro, bus, nin, ninv, nbuf, name, lab) in enumerate((
            (ye[0], 'U1', 1, 'R1', 'C25', 'R2', 'R3', 'C13', 'R4', xm, 'EXP_MAIN_IN', '~EXP_MAIN_INV', '~EXP_MAIN_BUF',
             'MAIN', ((30.48, ye[0] + 20.32), 90)),
            (ye[1], 'U4', 1, 'R21', 'C26', 'R22', 'R23', 'C17', 'R24', xa, 'EXP_SA_IN', '~EXP_SA_INV', '~EXP_SA_BUF',
             'SEND A', ((26.67, ye[1]), 0)),
            (ye[2], 'U4', 2, 'R25', 'C27', 'R26', 'R27', 'C18', 'R28', xb, 'EXP_SB_IN', '~EXP_SB_INV', '~EXP_SB_BUF',
             'SEND B', ((30.48, ye[2] - 2.54), 90)))):
        s.label(nin, *lab)
        s.part(rpd, 'R', '1M', 'R0603', (33.02, yy + 3.81), 0, {'1': nin, '2': 'GND'}, text=((2.54, 0), (2.54, 2.54)),
               Note=f'EXP {name} pull-down (open header = 0 V)')
        s.psym('GND', (33.02, yy + 7.62))
        s.part(cac, 'C', '10u', 'C0805', (39.37, yy), 90, {'1': nin, '2': f'~EXP_{name.replace(" ", "")}_AC'},
               text=FB_TEXT, Voltage='25V', Note=f'EXP {name} AC coupling: into the 100k, -3 dB at 0.16 Hz')
        s.wire((43.18, yy), (48.26, yy))
        o = s.inverting(u, unit, 68.58, yy, ninv, nbuf, (rf, f'EXP {name} inverter feedback'),
                        (cf, f'EXP {name} inverter HF roll-off'), f'EXP {name} inverter (keeps the expander polarity)',
                        rin=(rin, f'EXP {name} input resistor'), rin_net=f'~EXP_{name.replace(" ", "")}_AC',
                        utext=((-16.51, 7.62), (-16.51, 10.16)))
        bus_net = {'MAIN': 'MAIN_SUM', 'SEND A': 'SENDA_SUM', 'SEND B': 'SENDB_SUM'}[name]
        e = s.res(ro, '100k', o[0] + 2.54, o[1], nbuf, bus_net, f'EXP {name} summing resistor')
        s.wire(o, (o[0] + 2.54, o[1]))
        if e[0] != bus:
            s.wire(e, (bus, e[1]))

    # ---- Returns A / B: jack -> 10k -> follower (+) with 1M || 100p to GND -> 100R -> level pot -> 100k -> OUT_SUM.
    for k, (yy, j, cac, rs, rpd, cflt, u, unit, rd, rv, rsum, pre) in enumerate((
            (152.4, 'J3', 'C23', 'R9', 'R10', 'C21', 'U2', 1, 'R11', 'RV2', 'R12', 'RTNA'),
            (187.96, 'J4', 'C24', 'R13', 'R14', 'C22', 'U2', 2, 'R15', 'RV3', 'R16', 'RTNB'))):
        name = 'A' if k == 0 else 'B'
        t = s.in_jack(j, 198.12, yy, f'{pre}_IN', f'RETURN {name} audio input (AC-coupled by {cac}); ' + JACKNOTE +
                      '; TN grounds the unpatched input', text=((0, -8.89), (0, -6.35)))
        s.part(cac, 'C', '1u', 'C0603', (215.9, yy), 90, {'1': f'{pre}_IN', '2': f'~{pre}_AC'}, text=FB_TEXT,
               Voltage='25V', Note=f'RETURN {name} AC coupling: into the 1M bias, -3 dB at 0.16 Hz')
        s.res(rs, '10k', 220.98, yy, f'~{pre}_AC', f'~{pre}_P', f'RETURN {name} input series (op-amp input protection)')
        s.wire(t, (212.09, yy))
        s.wire((219.71, yy), (220.98, yy))
        s.label(f'{pre}_IN', (204.47, yy))
        s.wire((228.6, yy), (246.38, yy))
        s.shunt(rpd, 'R', '1M', 231.14, yy, f'~{pre}_P', f'RETURN {name} bias to GND (input impedance ~1M)')
        s.shunt(cflt, 'C', '100p', 238.76, yy, f'~{pre}_P', f'RETURN {name} RF filter', Voltage='50V')
        o = s.follower(u, unit, 254.0, yy, f'~{pre}_P', f'~{pre}_BUF', f'RETURN {name} buffer')
        e = s.res(rd, '100', 267.97, o[1], f'~{pre}_BUF', f'~{pre}_TOP', f'RETURN {name} pot drive isolation')
        s.wire(o, (267.97, o[1]))
        s.wire(e, (284.48, e[1]))
        w = s.pot(rv, 284.48, e[1], f'~{pre}_TOP', f'~{pre}_W', f'RETURN {name} level: ' + POTNOTE)
        s.res(rsum, '100k', 290.83, w[1], f'~{pre}_W', 'OUT_SUM', f'RETURN {name} summing resistor')
        s.wire(w, (290.83, w[1]))
        s.wire((298.45, w[1]), (xbus, w[1]))
    # ---- Output: OUT_SUM bus -> U3A summer -> R18 -> U3B inverter -> 1k (2512) -> MAIN OUT jack.
    y_rb = 187.96 + 2.54 + 3.81   # RETURN B wiper line
    s.wire((xbus, mw[1]), (xbus, y_rb))
    ys = mw[1]
    o1 = s.inverting('U3', 1, xsum + 10.16, ys, 'OUT_SUM', '~OUT_INV', ('R17', 'Output summer feedback (unity)'),
                     ('C15', 'Output summer HF roll-off / stability'), 'Output summer: master + RETURN A + RETURN B')
    s.label('OUT_SUM', (287.02, ys))
    o2 = s.inverting('U3', 2, o1[0] + 22.86, o1[1], '~OUT_INV2', '~OUT_BUF', ('R19', 'Output inverter feedback (gain -1)'),
                     ('C16', 'Output inverter HF roll-off / stability'), 'Output inverter (restores the input polarity)',
                     rin=('R18', 'Output inverter input resistor'), rin_net='~OUT_INV')
    s.wire(o1, (o1[0] + 2.54, o1[1]))
    e = s.res('R20', '1k', o2[0] + 2.54, o2[1], '~OUT_BUF', 'MAIN_OUT',
              'MAIN OUT series / mis-patch protection; 2512 (1 W): ~0.51 W with -12 V on +10.5 V', fp='R2512')
    s.wire(o2, (o2[0] + 2.54, o2[1]))
    t = s.out_jack('J5', e[0] + 17.78, o2[1], 'MAIN_OUT', 'MAIN output; ' + JACKNOTE)
    s.wire(e, t)
    s.label('MAIN_OUT', (e[0] + 1.27, e[1]))

    s.text((20.32, 20.32), 'BIG MODULAR 4MIX - S2 schematic: 4-channel mixer with 2 sends / 2 returns, +/-12 V, 18HP '
                           '(Bread Modular 4mix, no overdrive). Circuit intent: docs/research.md', 2.0)
    s.text((20.32, 25.4), 'AUDIO MIXER: every input (channel, return, EXP IN) is AC-coupled; outputs are DC from the op-amps.', 1.4)
    s.text((20.32, 30.48), 'POWER: Eurorack +12V / -12V -> B5819W per rail -> +12V / -12V (about +/-11.6 V). J8 +5V unused.\n'
                           'C3..C12 (root) and Cn02/Cn03 (channels): 100n at every op-amp supply pin; C1/C2: 10u bulk.', 1.4)
    s.text((20.32, 86.36), 'CHANNELS: sheet channel.kicad_sch x 4. Each channel ties onto MAIN_SUM / SENDA_SUM / SENDB_SUM\n'
                           '(virtual-ground summing nodes of U1B / U5A / U5B) through its own 100k resistors.', 1.27)
    s.text((109.22, 243.84), 'EXPANSION (no jacks, back of the board): J7 EXP OUT carries this module\'s pre-master MAIN mix and SEND A/B mixes\n'
                           '(1k each); J6 EXP IN takes another module\'s J7 and sums it into the buses with the input polarity (1M pull-downs:\n'
                           'open header = silent; 10u AC coupling). Chain: expander J7 -> master J6 (6-way 2x3 ribbon, every signal beside a GND).', 1.27)
    s.text((203.2, 215.9), 'RETURNS: jack -> 1u -> 10k -> unity follower (1M || 100p to GND) -> 100R -> level pot -> 100k -> OUT_SUM.\n'
                             'Returns are summed after the MAIN pot (Bread Modular 4mix), so MAIN does not change them.', 1.27)
    s.text((200.66, 91.44), 'OUTPUT: OUT = MAIN wiper + RETURN A + RETURN B (U3A sum, U3B invert), 1k series.\n'
                            'Unity end to end at full CW; TL072 on +/-11.6 V clips near +/-10 V.', 1.27)
    return s, sheets


# JLCPCB parts for every assembled (SMD) part, keyed (symbol, value, footprint). The codes
# repeat the modules/imix live-audited set plus the common JLCPCB Basic 0603 parts for the new
# values (1M, 10k, 1k, 100p); this module has no live audit yet (docs/research.md).
SOURCING = {
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1M', 'R0603'): dict(LCSC='C22935', MPN='0603WAF1004T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R2512'): dict(LCSC='C54315', MPN='25121WF1001T4E', Manufacturer='UNI-ROYAL'),
    ('C', '20p', 'C0603'): dict(LCSC='C1648', MPN='CL10C200JB8NNNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0603'): dict(LCSC='C15849', MPN='CL10A105KB8NNNC', Manufacturer='Samsung'),
    ('C', '100p', 'C0603'): dict(LCSC='C14858', MPN='CL10C101JB8NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('TL072', 'TL072CDT', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
}

TEXT_AT = {
    'J8': ((-1.27, -8.89), (-1.27, 8.89)),
    'TL072': ((0, -7.62), (0, 7.62)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 8.89)),
    'R_Potentiometer': ((-5.08, -1.27), (-5.08, 1.27)),
    'Conn_02x03_Odd_Even': ((1.27, -6.35), (1.27, 6.35)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '+12V': ((0, -6.35), (0, -3.81)),
    '-12V': ((0, 6.35), (0, 3.81)),
}
SHOW_VALUE = {'+12V', '-12V'}


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
    `(mirror x)` flips about the horizontal axis, `(mirror y)` about the vertical (rot 0 only)."""
    x, y = (-px if mirror == 'y' else px), (py if mirror == 'x' else -py)
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


def font(size=1.27):
    return [atom('font'), [atom('size'), size, size]]


def sheet_items(sh, lib_syms, paths, sheet_key):
    """S-expression items of one sheet. paths: [(instance path, ref function)]; returns
    (items, {instance index: {net: {ref/pin}}}, nc pins)."""
    items, nets, pin_pts, ncs = [], [dict() for _ in paths], [], set()
    for p in sh.parts:
        sym = lib_syms[p['sym']]
        unit = p['unit']
        pins = pin_table(sym, unit)
        assert set(p['pins']) == set(pins), (p['ref'], unit, sorted(pins), sorted(p['pins']))
        x, y = p['at']
        is_flag = p['ref'].startswith('#')
        dr, dv = p['text'] or TEXT_AT.get(p['ref'], TEXT_AT.get(p['sym'], ((0, -3.81), (0, 3.81))))
        ref0 = paths[0][1](p['ref'])
        props = [('Reference', ref0, (x + dr[0], y + dr[1]), is_flag),
                 ('Value', p['value'], (x + dv[0], y + dv[1]), is_flag and p['sym'] not in SHOW_VALUE),
                 ('Footprint', f"{LIBNAME}:{FP[p['fp']]}" if p['fp'] else '', (x, y), True),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''), (x, y), True),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''), (x, y), True)]
        props += [(k, v, (x, y), True) for k, v in p['fields'].items()]
        fang = 90 if p['rot'] in (90, 270) else 0
        key = f"{sheet_key}/{p['ref']}" + ('' if unit == 1 else f'/u{unit}')
        node = [atom('symbol'), [atom('lib_id'), f'{LIBNAME}:' + p['sym']], [atom('at'), x, y, p['rot']]]
        if p['mirror']:
            node.append([atom('mirror'), atom(p['mirror'])])
        node += [[atom('unit'), unit], [atom('exclude_from_sim'), atom('no')],
                 [atom('in_bom'), atom('no' if is_flag else 'yes')],
                 [atom('on_board'), atom('no' if is_flag else 'yes')],
                 [atom('in_pos_files'), atom('no' if is_flag else 'yes')], [atom('dnp'), atom('no')],
                 [atom('uuid'), uid('sym/' + key)]]
        for name, value, (px, py), hide in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), fang], [atom('effects'), font()]]
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{key}/{n}")]] for n in sorted(pins)]
        node.append([atom('instances'), [atom('project'), PROJECT] +
                     [[atom('path'), path, [atom('reference'), fref(p['ref'])], [atom('unit'), unit]]
                      for path, fref in paths]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, py, p['rot'], p['mirror'])
            ex, ey = r(x + ox), r(y + oy)
            pin_pts.append((ex, ey))
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid(f"nc/{key}/{n}")]])
                for i, (_, fref) in enumerate(paths):
                    ncs.add(f"{fref(p['ref'])}/{n}")
            elif not is_flag:
                for i, (_, fref) in enumerate(paths):
                    nets[i].setdefault(net, set()).add(f"{fref(p['ref'])}/{n}")
    segs = sh.segs
    ends = [pt for seg in segs for pt in seg]
    lab_pts = [at for _, at, _ in sh.labels] + [at for _, at in sh.hlabels]
    segs = split(segs, ends + pin_pts + lab_pts)
    for pt in lab_pts:
        assert any(pt in seg or on_seg(pt, *seg) for seg in segs), ('label off a wire', pt)
    degree = {}
    for pt in [pt for seg in segs for pt in seg] + pin_pts:
        degree[pt] = degree.get(pt, 0) + 1
    for a, b in sorted(set(segs)):
        items.append([atom('wire'), [atom('pts'), [atom('xy'), *a], [atom('xy'), *b]],
                      [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                      [atom('uuid'), uid(f'{sheet_key}/wire/{a}/{b}')]])
    for pt in sorted(pt for pt, k in degree.items() if k >= 3):
        items.append([atom('junction'), [atom('at'), *pt], [atom('diameter'), 0],
                      [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'{sheet_key}/junction/{pt}')]])
    for net, (lx, ly), ang in sh.labels:
        items.append([atom('label'), net, [atom('at'), lx, ly, ang],
                      [atom('effects'), font(), [atom('justify'), atom('right' if ang == 180 else 'left'), atom('bottom')]],
                      [atom('uuid'), uid(f'{sheet_key}/label/{net}/{lx}/{ly}')]])
    for net, (lx, ly) in sh.hlabels:
        items.append([atom('hierarchical_label'), net, [atom('shape'), atom('passive')], [atom('at'), lx, ly, 0],
                      [atom('effects'), font(), [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'{sheet_key}/hlabel/{net}')]])
    for i, ((x, y), s, size) in enumerate(sh.texts):
        items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                      [atom('effects'), font(size), [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'{sheet_key}/text/{i}')]])
    return items, nets, ncs


def sch_head(key, paper, title, comments, lib_syms):
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(uid(key))}) (paper "{paper}")
      (title_block (title {q(title)}) (rev "S2") (company "Big Modular")
        (comment 1 {q(comments[0])}) (comment 2 {q(comments[1])}))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIBNAME}:' + k
        embedded.append(s)
    return sch


def sheet_symbol(sh, root_uuid, page):
    (x, y), (w, h) = sh['at'], sh['size']
    n = sh['n']
    node = [atom('sheet'), [atom('at'), x, y], [atom('size'), w, h], [atom('exclude_from_sim'), atom('no')],
            [atom('in_bom'), atom('yes')], [atom('on_board'), atom('yes')], [atom('dnp'), atom('no')],
            [atom('stroke'), [atom('width'), 0.1524], [atom('type'), atom('solid')]],
            [atom('fill'), [atom('color'), 0, 0, 0, 0]], [atom('uuid'), uid(f'sheet/CH{n}')],
            [atom('property'), 'Sheetname', f'CH{n}', [atom('at'), x, r(y - 0.71), 0],
             [atom('effects'), font(), [atom('justify'), atom('left'), atom('bottom')]]],
            [atom('property'), 'Sheetfile', SHEET_FILE, [atom('at'), x, r(y + h + 0.59), 0],
             [atom('effects'), font(), [atom('justify'), atom('left'), atom('top')]]]]
    for net, py in sh['pins'].items():
        node.append([atom('pin'), net, atom('passive'), [atom('at'), r(x + w), r(py), 0],
                     [atom('uuid'), uid(f'sheet/CH{n}/pin/{net}')],
                     [atom('effects'), font(), [atom('justify'), atom('right')]]])
    node.append([atom('instances'), [atom('project'), PROJECT, [atom('path'), '/' + root_uuid, [atom('page'), str(page)]]]])
    return node


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
        '(options "") (descr "4MIX module pinned stock symbols; see tools/build_schematic.py")))\n')

    root_uuid = uid('root')
    rs, sheets = root()
    cs = channel()
    for sh, src in ((rs, 'root'), (cs, 'channel')):  # SOURCING fields on assembled parts
        for p in sh.parts:
            if not p['ref'].startswith('#'):
                p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))

    # Root sheet.
    sch = sch_head('root', 'A3', 'Big Modular - 4MIX', [
        'SCHEMATIC S2 - 4-channel audio mixer (AC-coupled inputs), 2 sends / 2 returns, expansion, +/-12 V, 18HP - not released',
        'Circuit intent: docs/research.md; placement: docs/geometry.json'], lib_syms)
    items, root_nets, ncs = sheet_items(rs, lib_syms, [('/' + root_uuid, lambda ref: ref)], 'root')
    for i, sh in enumerate(sheets):
        items.append(sheet_symbol(sh, root_uuid, i + 2))
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])
    out = HW / f'{PROJECT}.kicad_sch'
    out.write_text(dump(sch) + '\n')

    # Channel sheet, one file, four instances (CH1..CH4).
    def chref(n):
        def f(ref):
            if ref.startswith('#PWR'):
                return f'#PWR{n}{ref[4:]}'
            pre = ref.rstrip('0123456789')
            return f'{pre}{n}{ref[len(pre):]}'
        return f
    paths = [(f'/{root_uuid}/{uid(f"sheet/CH{n}")}', chref(n)) for n in CHANNELS]
    csch = sch_head('channel', 'A4', 'Big Modular - 4MIX channel strip (CH1..CH4)', [
        'SCHEMATIC S2 - one channel: AC-coupled input, input buffer, VOL, post-fader SEND A / SEND B',
        'Instantiated 4 times by 4mix.kicad_sch; parts numbered n01.. per channel'], lib_syms)
    citems, ch_nets, cncs = sheet_items(cs, lib_syms, paths, 'channel')
    csch += citems
    csch.append([atom('embedded_fonts'), atom('no')])
    (HW / SHEET_FILE).write_text(dump(csch) + '\n')
    for f in (out, HW / SHEET_FILE):
        subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(f)], check=True, stdout=subprocess.DEVNULL)

    # Expected nets: root nets, plus each channel's nets (local -> /CHn/NET, buses and power global).
    nets = {k: set(v) for k, v in root_nets[0].items()}
    for n, cn in zip(CHANNELS, ch_nets):
        for net, members in cn.items():
            name = net if net in HIER or net in ('GND', '+12V', '-12V') else f'CH{n}/{net}'
            nets.setdefault(name, set()).update(members)
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    # The project file names the root and channel sheets by UUID.
    pro = HW / f'{PROJECT}.kicad_pro'
    data = json.loads(pro.read_text())
    data['schematic']['top_level_sheets'] = [{'filename': f'{PROJECT}.kicad_sch', 'name': PROJECT, 'uuid': root_uuid}]
    data['sheets'] = [[root_uuid, 'Root']] + [[uid(f'sheet/CH{n}'), f'CH{n}'] for n in CHANNELS]
    pro.write_text(json.dumps(data, indent=2) + '\n')
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbols in hardware/{LIBNAME}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources}, indent=2) + '\n')
    native = netlist_nets(out)
    native_nc = {n: k for n, k in native.items() if n.startswith('unconnected-')}
    native = {n: k for n, k in native.items() if not n.startswith('unconnected-')}
    assert set().union(*native_nc.values()) == ncs | cncs if native_nc else not (ncs | cncs), \
        ('no-connect pins differ', native_nc, ncs | cncs)
    # '~' nets carry no label: KiCad names them Net-(...); compare those by membership only.
    anon = sorted(sorted(k) for n, k in nets.items() if '~' in n)
    native_anon = sorted(sorted(k) for n, k in native.items() if 'Net-(' in n)
    assert anon == native_anon, ('unlabelled nets differ', [a for a in anon if a not in native_anon],
                                 [a for a in native_anon if a not in anon])
    nets = {n: k for n, k in nets.items() if '~' not in n}
    native = {n: k for n, k in native.items() if 'Net-(' not in n}
    assert native == nets, ('native netlist differs from the intent',
                            {n: (native.get(n), nets.get(n)) for n in set(native) | set(nets)
                             if native.get(n) != nets.get(n)})
    print(out, f'{len(nets) + len(anon)} nets ({len(anon)} unlabelled), native netlist equals the intent')


if __name__ == '__main__':
    build()
