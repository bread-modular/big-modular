"""Generate the LADDER S5 schematic (hardware/ladder.kicad_sch) and its pinned symbols.

Run from modules/ladder:
  python3 -B tools/build_schematic.py

Writes hardware/LADDER.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the LADDER library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
of docs/research.md section 3: a pure-analog 6HP transistor ladder filter (S4 / S5, user
2026-11-15: no MIDI, no MCU, no envelope, no VCA). A classic Moog 4-pole ladder
(DMMT3904W matched pairs, 47n NP0), an exponential cutoff converter summing CUTOFF and
the CV input x DEPTH (buffered, bipolar, analog all the way; the buffer carries two dim panel
LEDs anti-parallel in its loop that show the positive and the negative CV after DEPTH, three
solder jumpers set their brightness), resonance by an LM13700 OTA in the feedback path (S5:
RES knob + RES CV set its bias current) with the modules/16bit PolyFilter (1 + k) passband
makeup. AUDIO IN, CV and RES CV in, one OUT.

The drawing machinery (pinned stock symbols, a 1.27 mm grid wire router, the native
netlist assertion) is modules/acid's build_schematic.py; only the circuit, placement,
sourcing, notes and one symbol edit are new here. Placement (LAYOUT) is by hand; signal
nets are wired by route_wires(); LABEL_NETS are the only signal nets joined by name labels.
Supply pins get a stub and a stock power symbol. The build exports the native netlist and
fails unless it equals circuit().
"""
import copy
import hashlib
import heapq
import json
import math
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/sexp.py
from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
STOCK = Path('/usr/share/kicad/symbols')
PROJECT = 'ladder'
LIB = 'LADDER'
STUB = 2.54

FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LED': ('Device', 'LED'),
    'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'HT75xx-1-SOT89': ('Regulator_Linear', 'HT75xx-1-SOT89'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'LM13700': ('Amplifier_Operational', 'LM13700'),
    'Q_PNP_BEC': ('Transistor_BJT', 'Q_PNP_BEC'),
    'SolderJumper_2_Open': ('Jumper', 'SolderJumper_2_Open'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'DMMT3904W': ('Transistor_BJT', 'MMDT3904'),
    '1N4148W': ('Diode', '1N4148W'),
    'GND': ('power', 'GND'), '+5V': ('power', '+5V'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

# Symbol edits beyond the footprint filters. DMMT3904W: the stock MMDT3904 body (two NPN units)
# renamed, with the pin numbers of the Diodes DMMT3904W SOT-363 pin-out (DS30311 Rev. 15, page 1,
# top view: 1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2). MMDT3904 is 1 E1, 2 B1, 6 C1 / 3 C2, 4 E2, 5 B2.
RENAME = {'DMMT3904W': {'1': {'1': '4', '2': '2', '6': '3'}, '2': {'3': '6', '4': '5', '5': '1'}}}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric', 'C1206': 'C_1206_3216Metric',
    'SOD123': 'D_SOD-123', 'SOT363': 'SOT-363_SC-70-6',
    'SOT89': 'SOT-89-3', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm', 'SOIC16': 'SOIC-16_3.9x9.9mm_P1.27mm',
    'SOT23': 'SOT-23', 'SJ2': 'SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'H2x5': 'PinHeader_2x05_P2.54mm_Vertical', 'LED3': 'LED_D3.0mm',
}

# Copper-only parts (no BOM row, no CPL row): the CV LED brightness solder jumpers.
NOT_ASSEMBLED = {'JP1', 'JP2', 'JP3'}

# Supply nets are drawn with power symbols (net name = symbol value).
RAIL_SYMBOL = {'GND': 'GND', '+5V': '+5V', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Signal nets joined by name labels (a stub + label on every pin) instead of wires: the ladder
# base bias rails (each feeds both transistors of a rung from the bias-chain block).
LABEL_NETS = {'LB0', 'LB1', 'LB2', 'LB3', 'LB4'}

# Multi-unit symbols and the units placed (build() asserts it).
MULTI = {**{u: {1, 2, 3} for u in ('U4', 'U5', 'U6', 'U7', 'U9')},
         **{q: {1, 2} for q in ('Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8')}, 'U8': {1, 2, 3, 4, 5}}

GRID = 2.54
OFFSET = (4, 4)  # LAYOUT / TEXTS origin inside the A2 frame, grid units
DEBUG_PLACEMENT = bool(__import__('os').environ.get('LADDER_PLACEMENT_ONLY'))


def part(ref, sym, value, fp, pins, unit=1, **fields):
    key = ref if unit == 1 else f'{ref}.{unit}'
    x, y, rot, *mirror = LAYOUT[key]
    x, y = x + OFFSET[0], y + OFFSET[1]
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(round(x * GRID, 2), round(y * GRID, 2)), rot=rot,
                mirror=bool(mirror), pins=pins, unit=unit, fields=fields)


# Symbol placement in 2.54 mm grid units: ref (unit 1) or ref.unit -> (x, y, rotation[, 'mirror']).
# Top: power entry and the supply pins. Middle: AUDIO IN -> ladder (B = input side on the left,
# A = feedback side on the right) -> followers -> difference amp -> output stage -> OUT. Below:
# CUTOFF + CV summer -> expo under the ladder; resonance feedback summer + OTA beside the driver
# pair; RES knob + RES CV -> OTA bias current. Bottom left: CV in -> DEPTH -> buffer with the two
# CV LEDs in its loop and the brightness jumpers.
LAYOUT = {
    # Power entry
    'J10': (9, 20, 0), 'D1': (21, 17, 180), 'D2': (21, 25, 0), 'C1': (28, 19.5, 0), 'C2': (32, 19.5, 0),
    'U1': (42, 18, 0), 'C3': (50, 19.5, 0), 'C4': (54, 19.5, 0),
    '#FLG01': (6, 31, 0), '#FLG02': (12, 31, 0), '#FLG03': (18, 31, 0), '#FLG04': (24, 31, 0),
    '#FLG05': (30, 31, 0),
    # supply units and decoupling
    'U4.3': (84, 19, 0), 'C24': (88, 19.5, 0), 'C25': (92, 19.5, 0),
    'U5.3': (99, 19, 0), 'C26': (103, 19.5, 0), 'C27': (107, 19.5, 0),
    'U6.3': (114, 19, 0), 'C28': (118, 19.5, 0), 'C29': (122, 19.5, 0),
    'U7.3': (129, 19, 0), 'C30': (133, 19.5, 0), 'C31': (137, 19.5, 0),
    'U9.3': (144, 19, 0), 'C32': (148, 19.5, 0), 'C33': (152, 19.5, 0),
    'U8.5': (162, 19, 0), 'C5': (166, 19.5, 0), 'C6': (170, 19.5, 0),
    # AUDIO IN buffer
    'J4': (5, 90, 0), 'R30': (14, 90, 90), 'U5.2': (25, 91, 0), 'R31': (25, 96, 90), 'C19': (25, 100, 90),
    # bias chain (labels)
    'R20': (30, 53, 0), 'R21': (30, 63, 0), 'R22': (30, 73, 0), 'R23': (37, 53, 0), 'R24': (37, 63, 0),
    'R25': (37, 73, 0), 'C18': (44, 53, 0), 'C17': (44, 63, 0), 'C16': (44, 73, 0), 'C15': (51, 53, 0),
    'C14': (51, 63, 0),
    # ladder: B side (input) left column, A side (feedback) right column, rung 4 on top
    'Q8': (62, 60, 0), 'Q8.2': (78, 60, 0, 'mirror'), 'Q7': (62, 70, 0), 'Q7.2': (78, 70, 0, 'mirror'),
    'Q6': (62, 80, 0), 'Q6.2': (78, 80, 0, 'mirror'), 'Q5': (62, 90, 0), 'Q5.2': (78, 90, 0, 'mirror'),
    'Q4': (62, 100, 0), 'Q4.2': (78, 100, 0, 'mirror'),
    'C13': (70, 65, 90), 'C12': (70, 75, 90), 'C11': (70, 85, 90), 'C10': (70, 95, 90),
    'R28': (50, 100, 90), 'R26': (56, 104, 0), 'R27': (84, 104, 0), 'R29': (88, 104, 0),
    # followers + difference amp
    'U6': (95, 60, 0), 'U6.2': (95, 72, 0), 'R34': (104, 60, 90), 'R35': (108, 56, 0),
    'R32': (104, 72, 90), 'U7': (116, 66, 0), 'R33': (116, 72, 90),
    # resonance feedback summer (U9B) -> C20 -> 10k / 1k -> OTA U8A -> C22 -> LFB
    'R36': (104, 101, 90), 'R37': (104, 104, 90), 'U9.2': (112, 100, 0), 'R38': (112, 105, 90),
    'C21': (112, 108, 90), 'C20': (119, 100, 90), 'R39': (125, 100, 90), 'R42': (129, 104, 0),
    'R43': (129, 96, 180), 'U8.3': (136, 99, 0), 'R48': (142, 103, 0), 'C22': (146, 99, 90),
    # unused LM13700 half and the two Darlington buffers
    'U8': (170, 99, 0), 'U8.2': (170, 108, 0), 'U8.4': (170, 115, 0),
    # output stage -> OUT
    'C23': (126, 65, 90), 'R44': (130, 62, 0), 'U9': (136, 66, 0), 'R45': (136, 72, 90), 'R46': (131, 72, 0),
    'R47': (145, 66, 90), 'J6': (153, 66, 0, 'mirror'),
    # CUTOFF + CV summer, divider
    'RV3': (15, 119, 180, 'mirror'), 'R13': (25, 123, 90), 'R14': (25, 127, 90), 'R15': (25, 131, 90),
    'U4.2': (35, 122, 0), 'R12': (35, 127, 90), 'C8': (35, 131, 90), 'D6': (35, 135, 180),
    'R16': (44, 122, 90), 'R17': (48, 125, 0),
    # expo converter
    'Q3': (54, 122, 0), 'Q3.2': (70, 122, 0, 'mirror'), 'R18': (55, 116, 0), 'U5': (64, 134, 0),
    'C9': (64, 139, 90), 'D7': (71, 134, 0), 'R19': (74, 130, 0),
    # RES knob + RES CV -> U7B + Q9 -> OTA bias current
    'RV4': (115, 122, 180, 'mirror'), 'R40': (121, 122, 90), 'J5': (110, 132, 0), 'R41': (121, 132, 90),
    'U7.2': (134, 123, 0), 'C7': (134, 128, 90), 'D8': (134, 132, 0), 'R49': (134, 117, 90),
    'Q9': (144, 123, 180, 'mirror'), 'R50': (151, 119, 90),
    # CV in -> DEPTH -> U4A (CV LEDs D11 / D12 anti-parallel in the loop) -> CV_S -> R14;
    # brightness loads R6 / R7 / R8 behind the solder jumpers JP1..JP3
    'J3': (6, 143, 0), 'R9': (14, 143, 90), 'RV2': (22, 146, 180, 'mirror'), 'U4': (34, 147, 0),
    'D11': (44, 147, 180), 'D12': (44, 142, 0),
    'R6': (53, 146, 90), 'JP1': (60, 146, 0), 'R7': (53, 150, 90), 'JP2': (60, 150, 0),
    'R8': (53, 154, 90), 'JP3': (60, 154, 0),
}

# Hand-drawn polylines for nets the router should not choose itself (same format as
# modules/low WIRES: 'REF/pin' pin ends and (x, y) grid points). Everything else is routed.
WIRES = {}

LABEL_AT = {}

R_NOTE_POT = 'RV09 9 mm vertical, linear (user stock). Hand-soldered'


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7550-1 -> +5V
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5',
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header on B, pin 1 (-12 V) at the bottom (as modules/acid); '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(part('D1', 'D_Schottky', 'B5819W', 'SOD123',
                  {'1': '+12V_F', '2': '+12V'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D2', 'D_Schottky', 'B5819W', 'SOD123',
                  {'1': '-12V', '2': '-12V_F'}, Note='-12 V series reverse-polarity protection'))
    c.append(part('C1', 'C', '10u', 'C0805', {'1': '+12V_F', '2': 'GND'}, Voltage='25V', Note='+12V_F bulk'))
    c.append(part('C2', 'C', '10u', 'C0805', {'1': 'GND', '2': '-12V_F'}, Voltage='25V', Note='-12V_F bulk'))
    c.append(part('U1', 'HT75xx-1-SOT89', 'HT7550-1', 'SOT89',
                  {'1': 'GND', '2': '+12V_F', '3': '+5V'},
                  Note='5 V LDO, 30 V max input, 100 mA: the reference of the CUTOFF knob and the expo current. '
                       'Load ~0.7 mA (CUTOFF knob 0.1 mA, expo reference 0.55 mA)'))
    c.append(part('C3', 'C', '1u', 'C0805', {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805', {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V'}))

    # ---- CV in x DEPTH (S4, all analog): J3 -> R9 -> DEPTH pot -> U4A. U4A is a follower with the two
    # panel LEDs anti-parallel in its feedback path: V(CV_S) = V(CV_W), and everything CV_S sources or
    # sinks (R14, plus R6 / R7 / R8 behind closed jumpers) flows through one LED: D11 for a positive CV,
    # D12 for a negative one. I_LED = |V(CV_S)| x (1 / 47k + jumpered loads): proportional to CV x DEPTH
    # from 0 V, no dead band.
    c.append(part('J3', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'CVIN', 'S': 'GND', 'TN': 'GND'},
                  Note='CV in (cutoff modulation), DC coupled, bipolar: positive opens the filter. '
                       'Unpatched = GND. Input impedance 89k'))
    c.append(part('R9', 'R', '39k', 'R0603', {'1': 'CVIN', '2': 'CV_TOP'},
                  Note='CV series resistor: DEPTH full = 0.56 x CV, so a +/-12 V mis-patch stays inside the '
                       'TL072 common-mode range (+/-6.7 V, +/-7.3 V with a +20 % pot: no phase reversal); '
                       'limits the input current of an unpowered module to 0.3 mA'))
    c.append(part('RV2', 'R_Potentiometer', '50k', 'RV09', {'1': 'GND', '2': 'CV_W', '3': 'CV_TOP'},
                  Note='DEPTH: CV attenuator, 0..+8.3 octaves for a 5 V CV (0.56 x 5 V = 2.81 V at CV_S). '
                       + R_NOTE_POT))
    c.append(part('D11', 'LED', 'LED_3mm_red', 'LED3', {'2': 'CV_O', '1': 'CV_S'},
                  Note='CV LED, positive CV (after DEPTH), in the U4A loop: 21 uA per volt at CV_S with JP1..JP3 '
                       'open = 0.06 mA at 5 V CV / DEPTH full (the modules/mcc LEDs run 3 mA: too bright, user '
                       '2026-11-15). JP1..JP3 raise it. Hand-soldered 3 mm THT, dome flush with the panel'))
    c.append(part('D12', 'LED', 'LED_3mm', 'LED3', {'2': 'CV_S', '1': 'CV_O'},
                  Note='CV LED, negative CV (user 2026-11-15): anti-parallel to D11 in the U4A loop, same '
                       'current per volt. Second colour of the user\'s choice. Each LED sees the other one\'s '
                       'forward voltage in reverse (2..3.3 V, below the 5 V rating). Hand-soldered 3 mm THT'))
    steps = (('R6', 'JP1', '47k', 'LED_J1', 'x2 (0.12 mA at 5 V CV / DEPTH full)'),
             ('R7', 'JP2', '22k', 'LED_J2', 'x3.1 alone; JP1 + JP2 x4.1'),
             ('R8', 'JP3', '10k', 'LED_J3', 'x5.7 alone; JP1 + JP2 + JP3 x8.8 (0.53 mA)'))
    for i, (r_, jp, val, net, what) in enumerate(steps, 1):
        c.append(part(r_, 'R', val, 'R0603', {'1': 'CV_S', '2': net},
                      Note=f'CV LED brightness step {i}: an extra load on CV_S behind {jp}; its current flows '
                           f'through the lit LED. {jp} closed = {what}'))
        c.append(part(jp, 'SolderJumper_2_Open', f'LED_BRIGHT_{i}', 'SJ2', {'1': net, '2': 'GND'},
                      Note=f'CV LED brightness (user 2026-11-15), open as shipped (dimmest: R14 alone, 21 uA / V). '
                           f'Bridge with solder: {what}. Both LEDs follow'))

    tl = {'U4': 'A: CV x DEPTH buffer with the CV LEDs in its loop; B: CUTOFF + CV summer, clamped at -0.6 V',
          'U5': 'A: expo reference loop (I_ref 0.55 mA); B: AUDIO IN inverting buffer',
          'U6': 'A / B: ladder top followers (JFET inputs, pA bias: the top cap nodes are 0.2..30k)',
          'U7': 'A: ladder difference amp x10; B: resonance control current (RES knob + RES CV -> I_ABC)',
          'U9': 'A: output stage x20.6 (OUT); B: resonance feedback summer'}

    def opamp(u, unit, plus, minus, out):
        pins = {'3': plus, '2': minus, '1': out} if unit == 1 else {'5': plus, '6': minus, '7': out}
        return part(u, 'TL072', 'TL072', 'SOIC8', pins, unit=unit, Note='TL072, +/-12 V. ' + tl[u])

    # ---- CV buffer / LED driver (see the CV block above)
    c.append(opamp('U4', 1, 'CV_W', 'CV_S', 'CV_O'))

    # ---- CUTOFF + CV summer (inverting) -> divider -> expo (docs/research.md 3.3).
    # V_S = 12 V x 100k/200k - 100k x (V_CUT/82k + V_CVS/47k): 6.0 V (55 Hz) .. -0.10 V (17.6 kHz) by
    # CUTOFF; CV x DEPTH adds up to -6.0 V (8.3 octaves) for a 5 V CV, a negative CV closes the filter.
    # D6 clamps V_S at -0.6 V = ~31 kHz (ladder <= 1 mA).
    c.append(part('RV3', 'R_Potentiometer', '50k', 'RV09', {'1': 'GND', '2': 'CUT_W', '3': '+5V'},
                  Note='CUTOFF: 55 Hz..17.6 kHz (8.3 octaves), CW = open. ' + R_NOTE_POT))
    c.append(part('R13', 'R', '82k', 'R0603', {'1': 'CUT_W', '2': 'CUT_SUM'},
                  Note='CUTOFF input: 5 V = -6.1 V at V_S = 8.5 octaves'))
    c.append(part('R14', 'R', '47k', 'R0603', {'1': 'CV_S', '2': 'CUT_SUM'},
                  Note='CV x DEPTH input: 2.81 V at CV_S (5 V CV, DEPTH full) = -6.0 V at V_S = 8.3 octaves. '
                       'Its current also flows through the CV LEDs (the base brightness, 21 uA / V)'))
    c.append(part('R15', 'R', '200k', 'R0603', {'1': '-12V_F', '2': 'CUT_SUM'},
                  Note='Offset: V_S = +6.0 V with CUTOFF at 0 and no CV (55 Hz)'))
    c.append(opamp('U4', 2, 'GND', 'CUT_SUM', 'CUT_S'))
    c.append(part('R12', 'R', '100k', 'R0603', {'1': 'CUT_SUM', '2': 'CUT_S'}, Note='Summer feedback'))
    c.append(part('C8', 'C', '100p', 'C0603', {'1': 'CUT_SUM', '2': 'CUT_S'}, Voltage='50V',
                  Note='Summer HF roll-off (16 kHz): stability, CV noise'))
    c.append(part('D6', '1N4148W', '1N4148W', 'SOD123', {'1': 'CUT_S', '2': 'CUT_SUM'},
                  Note='Top-end clamp: V_S >= -0.6 V, so CUTOFF + a large CV stays near 31 kHz (ladder <= 1 mA)'))
    c.append(part('R16', 'R', '3.9k', 'R0603', {'1': 'CUT_S', '2': 'EXP_B'},
                  Note='Expo divider 100R / 4.0k = 1/40: 0.717 V at V_S per octave (17.9 mV at the base)'))
    c.append(part('R17', 'R', '100', 'R0603', {'1': 'EXP_B', '2': 'GND'},
                  Note='Expo divider bottom; low so Q3A base current (5 uA) shifts it by only 0.5 mV'))

    # ---- Expo converter: Q3A reference (I_C held at I_REF by U5A), Q3B sinks the ladder tail
    # current I = I_REF x exp(-V(EXP_B) / VT). Uncompensated tempco: a filter, not a V/oct source.
    q3 = ('Matched NPN pair (2 mV VBE, 2 % hFE), one die pair = one thermal block. A: expo reference; '
          'B: expo output, sinks the ladder tail')
    c.append(part('Q3', 'DMMT3904W', 'DMMT3904W', 'SOT363', {'2': 'EXP_B', '3': 'EXP_C', '4': 'EXP_E'},
                  unit=1, Note=q3))
    c.append(part('Q3', 'DMMT3904W', 'DMMT3904W', 'SOT363', {'1': 'GND', '6': 'LTAIL', '5': 'EXP_E'},
                  unit=2, Note=q3))
    c.append(part('R18', 'R', '9.1k', 'R0603', {'1': '+5V', '2': 'EXP_C'},
                  Note='I_REF = 5 V / 9.1k = 0.55 mA = the ladder current at V_S = 0 (~16 kHz)'))
    c.append(opamp('U5', 1, 'GND', 'EXP_C', 'EXP_O'))
    c.append(part('C9', 'C', '100p', 'C0603', {'1': 'EXP_C', '2': 'EXP_O'}, Voltage='50V',
                  Note='Reference loop compensation'))
    c.append(part('D7', '1N4148W', '1N4148W', 'SOD123', {'1': 'EXP_O', '2': 'EXP_D'},
                  Note='Keeps U5A from pulling the expo emitters positive (reverse VBE) at power-up'))
    c.append(part('R19', 'R', '4.7k', 'R0603', {'1': 'EXP_E', '2': 'EXP_D'},
                  Note='Expo emitter resistor: U5A sinks I_REF + I_ladder (<= 1.6 mA, output >= -9 V)'))

    # ---- AUDIO IN: inverting unity buffer (AIN_BUF = -IN), DC coupled
    c.append(part('J4', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', {'T': 'AIN', 'S': 'GND', 'TN': 'GND'},
                  Note='AUDIO IN, 10 Vpp; unpatched = GND'))
    c.append(part('R30', 'R', '100k', 'R0603', {'1': 'AIN', '2': 'AIN_SUM'},
                  Note='Input resistor: 100k input impedance'))
    c.append(opamp('U5', 2, 'GND', 'AIN_SUM', 'AIN_BUF'))
    c.append(part('R31', 'R', '100k', 'R0603', {'1': 'AIN_SUM', '2': 'AIN_BUF'}, Note='Feedback: gain -1'))
    c.append(part('C19', 'C', '20p', 'C0603', {'1': 'AIN_SUM', '2': 'AIN_BUF'}, Voltage='50V',
                  Note='HF roll-off / stability (80 kHz)'))

    # ---- Ladder bias chain: +12V_F -> 4.7k -> LB4 7.4 V, 1.5k steps -> LB0 1.48 V (0.98 mA)
    chain = (('R20', '4.7k', '+12V_F', 'LB4'), ('R21', '1.5k', 'LB4', 'LB3'), ('R22', '1.5k', 'LB3', 'LB2'),
             ('R23', '1.5k', 'LB2', 'LB1'), ('R24', '1.5k', 'LB1', 'LB0'), ('R25', '1.5k', 'LB0', 'GND'))
    for ref, val, a, b in chain:
        c.append(part(ref, 'R', val, 'R0603', {'1': a, '2': b},
                      Note='Ladder base bias chain (~1 mA, 1.47 V per rung = VCE of each rung transistor)'))
    for ref, net in (('C14', 'LB0'), ('C15', 'LB1'), ('C16', 'LB2'), ('C17', 'LB3'), ('C18', 'LB4')):
        c.append(part(ref, 'C', '10u', 'C0805', {'1': net, '2': 'GND'}, Voltage='25V',
                      Note=f'{net} bypass: the rung bases are AC ground'))

    # ---- Ladder: driver pair Q4 + four rungs Q5..Q8 (unit 1 = B / input side, unit 2 = A / feedback
    # side), 47n NP0 across each stage: fc = I / (8 pi VT C) = 3.3 Hz per uA (55 Hz at 1.7 uA,
    # 17.6 kHz at 0.55 mA). Output across C13 (top of rung 3), read by U6A / U6B.
    lq = 'Matched NPN pair (2 mV VBE, 2 % hFE): one ladder rung, B side (unit 1) and A side (unit 2)'
    rungs = (('Q4', 'LIN', 'LFB', 'LTAIL', 'LTAIL', 'LAD_B0', 'LAD_A0'),
             ('Q5', 'LB1', 'LB1', 'LAD_B0', 'LAD_A0', 'LAD_B1', 'LAD_A1'),
             ('Q6', 'LB2', 'LB2', 'LAD_B1', 'LAD_A1', 'LAD_B2', 'LAD_A2'),
             ('Q7', 'LB3', 'LB3', 'LAD_B2', 'LAD_A2', 'LAD_B3', 'LAD_A3'),
             ('Q8', 'LB4', 'LB4', 'LAD_B3', 'LAD_A3', '+12V_F', '+12V_F'))
    for q, bb, ba, eb, ea, cb, ca in rungs:
        note = ('Matched NPN pair: ladder driver (differential input pair), B = audio base, A = feedback base'
                if q == 'Q4' else lq)
        c.append(part(q, 'DMMT3904W', 'DMMT3904W', 'SOT363', {'2': bb, '4': eb, '3': cb}, unit=1, Note=note))
        c.append(part(q, 'DMMT3904W', 'DMMT3904W', 'SOT363', {'1': ba, '5': ea, '6': ca}, unit=2, Note=note))
    for ref, k in (('C10', '0'), ('C11', '1'), ('C12', '2'), ('C13', '3')):
        c.append(part(ref, 'C', '47n', 'C1206', {'1': 'LAD_B' + k, '2': 'LAD_A' + k}, Voltage='100V',
                      Note=f'Ladder pole {int(k) + 1}: NP0 (C0G), 5 %'))
    c.append(part('R28', 'R', '200k', 'R0603', {'1': 'AIN_BUF', '2': 'LIN'},
                  Note='Input attenuator 200k / 1k: 10 Vpp -> +/-25 mV at the driver (warm, not clipped)'))
    c.append(part('R26', 'R', '1k', 'R0603', {'1': 'LIN', '2': 'LB0'},
                  Note='Driver base bias from LB0; low so the driver input current (r_pi) barely loads it'))
    c.append(part('R27', 'R', '1k', 'R0603', {'1': 'LFB', '2': 'LB0'},
                  Note='Feedback base bias from LB0 and the load of the resonance OTA: V = I_out x 1k'))
    c.append(part('R29', 'R', '200k', 'R0603', {'1': 'LFB', '2': 'GND'},
                  Note='Mirrors R28 to GND: both driver bases sit 7 mV below LB0 (no DC offset)'))

    # ---- Ladder output: followers on the top nodes -> difference amp x10: LAD_DIF = 10 x (B3 - A3)
    c.append(opamp('U6', 1, 'LAD_B3', 'LAD_BF', 'LAD_BF'))
    c.append(opamp('U6', 2, 'LAD_A3', 'LAD_AF', 'LAD_AF'))
    c.append(part('R34', 'R', '10k', 'R0603', {'1': 'LAD_BF', '2': 'DIF_P'}, Note='Difference amp, B input'))
    c.append(part('R35', 'R', '100k', 'R0603', {'1': 'DIF_P', '2': 'GND'}, Note='Difference amp, B divider'))
    c.append(part('R32', 'R', '10k', 'R0603', {'1': 'LAD_AF', '2': 'DIF_N'}, Note='Difference amp, A input'))
    c.append(part('R33', 'R', '100k', 'R0603', {'1': 'DIF_N', '2': 'LAD_DIF'},
                  Note='Difference amp feedback: x10, passband LAD_DIF = 0.050 x IN (in phase)'))
    c.append(opamp('U7', 1, 'DIF_P', 'DIF_N', 'LAD_DIF'))

    # ---- Resonance (S5, user 2026-11-15: an OTA is fine if it is the standard design): U9B sums
    # -(LAD_DIF - 0.05 x IN) x 1.42, C20 AC couples it, R39 / R42 divide it by 11 into the + input of one
    # LM13700 half; its output current drives the feedback base node (R27 1k to LB0) through C22. In the
    # passband the two summer inputs cancel, so the output keeps the dry level at any resonance: the
    # 16bit's (1 + k) makeup, H = (1 + k) L / (1 + k L). k = 10 x 1.42 / 11 x gm x 0.99k, gm = I_ABC / 2 VT
    # = 19.3 mS per mA: k = 25 per mA, self-oscillation (k = 4) at ~0.17 mA.
    c.append(part('R36', 'R', '3.3k', 'R0603', {'1': 'LAD_DIF', '2': 'FB_SUM'},
                  Note='Feedback summer, ladder input: gain -4.7k / 3.3k = -1.42'))
    c.append(part('R37', 'R', '68k', 'R0603', {'1': 'AIN_BUF', '2': 'FB_SUM'},
                  Note='Makeup: 3.3k / 68k = 0.0485 ~ the 0.0498 passband ratio, cancels LAD_DIF in the passband'))
    c.append(opamp('U9', 2, 'GND', 'FB_SUM', 'FB_O'))
    c.append(part('R38', 'R', '4.7k', 'R0603', {'1': 'FB_SUM', '2': 'FB_O'}, Note='Feedback summer Rf'))
    c.append(part('C21', 'C', '100p', 'C0603', {'1': 'FB_SUM', '2': 'FB_O'}, Voltage='50V',
                  Note='Summer HF roll-off (340 kHz): stability'))
    c.append(part('C20', 'C', '10u', 'C0805', {'1': 'FB_O', '2': 'FB_AC'}, Voltage='25V',
                  Note='AC coupling (1.4 Hz into 11k): no ladder / summer DC into the OTA input'))
    c.append(part('R39', 'R', '10k', 'R0603', {'1': 'FB_AC', '2': 'OTA_P'},
                  Note='OTA input divider 10k / 1k = 1/11: +/-12..20 mV at the OTA input in self-oscillation, so '
                       'the ladder limits the amplitude before the OTA does'))
    c.append(part('R42', 'R', '1k', 'R0603', {'1': 'OTA_P', '2': 'GND'}, Note='OTA input divider bottom / + input bias'))
    c.append(part('R43', 'R', '1k', 'R0603', {'1': 'OTA_N', '2': 'GND'},
                  Note='- input bias, matches R42: the input bias currents (up to 5 uA) cancel'))
    ota = ('LM13700 dual OTA, +/-12 V. A: resonance VCA in the ladder feedback path (gm = I_ABC / 2 VT, no '
           'linearizing diodes); B and both Darlington buffers unused')
    c.append(part('U8', 'LM13700', 'LM13700', 'SOIC16',
                  {'3': 'OTA_P', '4': 'OTA_N', '2': None, '1': 'RES_ABC', '5': 'OTA_O'}, unit=3, Note=ota))
    c.append(part('U8', 'LM13700', 'LM13700', 'SOIC16',
                  {'14': 'GND', '13': 'GND', '15': None, '16': None, '12': None}, unit=1, Note=ota))
    c.append(part('U8', 'LM13700', 'LM13700', 'SOIC16', {'10': None, '9': None}, unit=2, Note=ota))
    c.append(part('U8', 'LM13700', 'LM13700', 'SOIC16', {'7': None, '8': None}, unit=4, Note=ota))
    c.append(part('U8', 'LM13700', 'LM13700', 'SOIC16', {'11': '+12V_F', '6': '-12V_F'}, unit=5, Note=ota))
    c.append(part('C5', 'C', '100n', 'C0603', {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U8 V+ decoupling'))
    c.append(part('C6', 'C', '100n', 'C0603', {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U8 V- decoupling'))
    c.append(part('R48', 'R', '100k', 'R0603', {'1': 'OTA_O', '2': 'GND'},
                  Note='DC path of the OTA output: its offset current (gm x V_os, 2 uA typ at RES full) settles '
                       'here (0.2 V typ, 2.4 V at the 4 mV limit) and not on the ladder base'))
    c.append(part('C22', 'C', '10u', 'C0805', {'1': 'OTA_O', '2': 'LFB'}, Voltage='25V',
                  Note='AC coupling of the OTA output current into the feedback base (0.16 Hz with R48): the '
                       'driver pair stays balanced at any resonance'))

    # ---- RES knob + RES CV -> OTA bias current. U7B sums both into its virtual ground (I_in = V_knob /
    # 100k + V_cv / 100k); Q9's emitter sits on the T-network node RES_E = -I_in x 47k, R50 adds
    # V(RES_E) / 9.1k: I_ABC = I_in x (1 + 47k / 9.1k) = 6.16 x I_in. Knob full 0.31 mA (k ~ 7.7),
    # +5 V CV alone the same; knob full + 12 V CV 1.04 mA (LM13700 limit 2 mA). D8 takes over when the
    # sum is negative (Q9 off, k = 0). With U7B railed, R50 still limits I_ABC to ~1.2 mA.
    c.append(part('RV4', 'R_Potentiometer', '50k', 'RV09', {'1': 'GND', '2': 'RES_W', '3': '+5V'},
                  Note='RESONANCE: OTA bias 0..0.31 mA = k 0..7.7; self-oscillation (k = 4, ~0.17 mA) at about '
                       '60 % of the travel, 45..90 % over the LM13700 gm limits. ' + R_NOTE_POT))
    c.append(part('R40', 'R', '100k', 'R0603', {'1': 'RES_W', '2': 'RES_X'}, Note='RES knob into the sum: 50 uA at full'))
    c.append(part('J5', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', {'T': 'RES_CV', 'S': 'GND', 'TN': 'GND'},
                  Note='RES CV in, adds to the knob (no attenuator): +5 V = the knob\'s full range; negative CV '
                       'subtracts. Audio rate works (OTA). Input impedance 100k'))
    c.append(part('R41', 'R', '100k', 'R0603', {'1': 'RES_CV', '2': 'RES_X'},
                  Note='RES CV into the sum: 10 uA per volt; 100k input impedance'))
    c.append(opamp('U7', 2, 'GND', 'RES_X', 'RES_O'))
    c.append(part('C7', 'C', '100p', 'C0603', {'1': 'RES_X', '2': 'RES_O'}, Voltage='50V',
                  Note='Converter loop compensation'))
    c.append(part('D8', '1N4148W', '1N4148W', 'SOD123', {'1': 'RES_X', '2': 'RES_O'},
                  Note='Closes the U7B loop when knob + CV is negative: Q9 off (0.6 V reverse VBE), no resonance'))
    c.append(part('R49', 'R', '47k', 'R0603', {'1': 'RES_X', '2': 'RES_E'},
                  Note='T-network: V(RES_E) = -I_in x 47k (-2.35 V at knob full, -8 V at knob full + 12 V CV)'))
    c.append(part('R50', 'R', '9.1k', 'R0603', {'1': 'RES_E', '2': 'GND'},
                  Note='Current gain 1 + 47k / 9.1k = 6.16; limits I_ABC to ~1.2 mA whatever U7B does'))
    c.append(part('Q9', 'Q_PNP_BEC', 'MMBT5401', 'SOT23', {'1': 'RES_O', '2': 'RES_E', '3': 'RES_ABC'},
                  Note='PNP current source into the LM13700 bias pin (two diode drops above -12V_F)'))

    # ---- Output stage: AC coupled, x20.6 -> 1k -> OUT (IN x 1.03, in phase)
    c.append(part('C23', 'C', '1u', 'C0805', {'1': 'LAD_DIF', '2': 'OUT_IN'}, Voltage='50V',
                  Note='AC coupling, 1.6 Hz: removes the ladder offset'))
    c.append(part('R44', 'R', '100k', 'R0603', {'1': 'GND', '2': 'OUT_IN'}, Note='Bias to 0 V'))
    c.append(opamp('U9', 1, 'OUT_IN', 'OUT_FB', 'FILT_AMP'))
    c.append(part('R45', 'R', '100k', 'R0603', {'1': 'OUT_FB', '2': 'FILT_AMP'}, Note='Rf: gain 1 + 100k / 5.1k = 20.6'))
    c.append(part('R46', 'R', '5.1k', 'R0603', {'1': 'OUT_FB', '2': 'GND'}, Note='Rg'))
    c.append(part('R47', 'R', '1k', 'R1206', {'1': 'FILT_AMP', '2': 'FILT_OUT'}, Power='0.5W',
                  Note='Output series: short / +/-12 V mis-patch protection (as modules/acid)'))
    c.append(part('J6', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', {'T': 'FILT_OUT', 'S': 'GND', 'TN': None},
                  Note='OUT: the ladder filter output, 10 Vpp for 10 Vpp in'))

    # ---- op-amp supply units and decoupling
    caps = {'U4': ('C24', 'C25'), 'U5': ('C26', 'C27'), 'U6': ('C28', 'C29'), 'U7': ('C30', 'C31'),
            'U9': ('C32', 'C33')}
    for u, (cp, cn) in caps.items():
        c.append(part(u, 'TL072', 'TL072', 'SOIC8', {'4': '-12V_F', '8': '+12V_F'}, unit=3, Note='TL072, +/-12 V. ' + tl[u]))
        c.append(part(cp, 'C', '100n', 'C0603', {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note=f'{u} V+ decoupling'))
        c.append(part(cn, 'C', '100n', 'C0603', {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note=f'{u} V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts, keyed (symbol, value, footprint). Every code looked up live for LADDER 2026-11-08
# (assembly.py lookup/search --strict-live); 39k added 2026-11-15 (S4); 22k, LM13700MX/NOPB and MMBT5401
# added 2026-11-15 (S5). Basic unless noted: Extended are the 0.5 W 1206 1k, the 47n NP0 1206, DMMT3904W,
# HT7550-1 and the LM13700. Stock is a dated observation, not a guarantee. THT parts and the solder
# jumpers carry no LCSC field.
SOURCING = {
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM'),
    ('R', '1.5k', 'R0603'): dict(LCSC='C22843', MPN='0603WAF1501T5E', Manufacturer='UNI-ROYAL'),
    ('R', '3.3k', 'R0603'): dict(LCSC='C22978', MPN='0603WAF3301T5E', Manufacturer='UNI-ROYAL'),
    ('R', '3.9k', 'R0603'): dict(LCSC='C23018', MPN='0603WAF3901T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0603'): dict(LCSC='C23186', MPN='0603WAF5101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '9.1k', 'R0603'): dict(LCSC='C23260', MPN='0603WAF9101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '39k', 'R0603'): dict(LCSC='C23153', MPN='0603WAF3902T5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '68k', 'R0603'): dict(LCSC='C23231', MPN='0603WAF6802T5E', Manufacturer='UNI-ROYAL'),
    ('R', '82k', 'R0603'): dict(LCSC='C23254', MPN='0603WAF8202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '200k', 'R0603'): dict(LCSC='C25811', MPN='0603WAF2003T5E', Manufacturer='UNI-ROYAL'),
    ('C', '20p', 'C0603'): dict(LCSC='C1648', MPN='CL10C200JB8NNNC', Manufacturer='Samsung'),
    ('C', '100p', 'C0603'): dict(LCSC='C14858', MPN='CL10C101JB8NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '47n', 'C1206'): dict(LCSC='C20617849', MPN='C1206N473J101T', Manufacturer='Holy Stone (IHHEC)'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('DMMT3904W', 'DMMT3904W', 'SOT363'): dict(LCSC='C155305', MPN='DMMT3904W-7-F',
                                               Manufacturer='Diodes Incorporated'),
    ('HT75xx-1-SOT89', 'HT7550-1', 'SOT89'): dict(LCSC='C16106', MPN='HT7550-1', Manufacturer='Holtek'),
    ('TL072', 'TL072', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
    ('LM13700', 'LM13700', 'SOIC16'): dict(LCSC='C174050', MPN='LM13700MX/NOPB', Manufacturer='Texas Instruments'),
    ('Q_PNP_BEC', 'MMBT5401', 'SOT23'): dict(LCSC='C8326', MPN='MMBT5401', Manufacturer='CJ (Jiangsu Changjing)'),
}


def T(x, y):
    return (round((x + OFFSET[0]) * GRID, 2), round((y + OFFSET[1]) * GRID, 2))


# Block notes: (grid position, text, size). route_wires() keeps wires out of their boxes.
TEXTS = [
    (T(4, 2), 'BIG MODULAR LADDER - S5 schematic: pure-analog 6HP transistor ladder filter (no MIDI, no MCU, no VCA). '
              'Circuit intent and numbers: docs/research.md', 2.0),
    (T(4, 4.5), 'Signal nets are wired; supplies use power symbols. LB0..LB4 (ladder base bias) are joined by their '
                'net labels.', 1.27),
    (T(4, 12), 'POWER: +12V -> D1 -> +12V_F (op amps, ladder, U1 HT7550-1 -> +5V reference); -12V -> D2 -> -12V_F.', 1.27),
    (T(80, 12), 'SUPPLY PINS + DECOUPLING', 1.27),
    (T(4, 106), 'AUDIO IN: U5B x -1. LADDER: 200k / 1k into the driver (+/-25 mV); 4 rungs, 47n NP0;\n'
                'bias chain LB0..LB4 1.5 V steps.', 1.27),
    (T(92, 48), 'OUTPUT: U6 followers on the top nodes, U7A x10 difference amp (LAD_DIF = 0.05 x IN),\n'
                'U9A AC coupled x20.6 -> 1k -> OUT (IN x 1.03, in phase).', 1.27),
    (T(92, 86), 'RESONANCE: U9B x -1.42 (LAD_DIF - 0.05 x IN) -> C20 -> 1/11 -> OTA U8A -> C22 -> feedback base (1k):\n'
                'k = 25 x I_ABC [mA], self-oscillation (k = 4) at ~0.17 mA; dry level kept at any k = the 16bit\n'
                '(1 + k) makeup.', 1.27),
    (T(108, 138), 'RES knob (on +5V) + RES CV -> U7B virtual ground (10 uA / V each) -> Q9: I_ABC = 6.16 x I_in.\n'
                  'Knob full or +5 V CV = 0.31 mA (k ~ 7.7); negative sum: D8, Q9 off. R50 caps I_ABC at ~1.2 mA.', 1.27),
    (T(160, 90), 'Unused LM13700 half (inputs to GND, bias open = off) and buffers.', 1.27),
    (T(4, 112), 'CUTOFF + CV summer -> 1/40 divider -> expo (Q3A reference at 0.55 mA, Q3B = ladder tail).\n'
                'D6 clamps V_S at -0.6 V (~31 kHz).', 1.27),
    (T(68, 146), 'CV x DEPTH: J3 -> R9 -> DEPTH pot (0.56 x CV at full) -> U4A -> CV_S -> R14: 5 V = +8.3 octaves.\n'
                 'CV LEDs anti-parallel in the U4A loop: D11 lights for a positive CV, D12 for a negative one,\n'
                 'I_LED = |V(CV_S)| x (1 / R14 + closed steps), linear from 0 V.\n'
                 'Brightness at 5 V CV / DEPTH full: JP1..JP3 open 0.06 mA; JP1 0.12; JP2 0.19; JP1+2 0.25;\n'
                 'JP3 0.34; JP1+3 0.40; JP2+3 0.47; all 0.53 mA.', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/ladder/schematic/' + key))


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
    """Pins of one unit (body style 1) plus the pins common to all units:
    number -> (x, y, angle, name, length)."""
    out = {}
    for u in nodes(sym, 'symbol'):
        num = u[1].rsplit('_', 2)[-2]
        if num not in ('0', str(unit)):
            continue
        for p in walk(u, 'pin'):
            at = one(p, 'at')
            out[one(p, 'number')[1]] = (float(at[1]), float(at[2]), float(at[3]), p[1], float(one(p, 'length')[1]))
    return out


def body_points(sym, unit):
    """Library-frame points of the body graphics (rectangles, polylines, circles, arcs) of one unit."""
    out = []
    for u in nodes(sym, 'symbol'):
        num = u[1].rsplit('_', 2)[-2]
        if num not in ('0', str(unit)):
            continue
        for g in u:
            if not isinstance(g, list) or not g or g[0] not in ('rectangle', 'polyline', 'circle', 'arc'):
                continue
            if g[0] == 'circle':
                (cx, cy), rad = one(g, 'center')[1:3], float(one(g, 'radius')[1])
                out += [(float(cx) - rad, float(cy) - rad), (float(cx) + rad, float(cy) + rad)]
                continue
            for key in ('start', 'end', 'mid'):
                k = one(g, key)
                if k:
                    out.append((float(k[1]), float(k[2])))
            pts_ = one(g, 'pts')
            if pts_:
                out += [(float(q[1]), float(q[2])) for q in nodes(pts_, 'xy')]
    return out


def xform(px, py, rot):
    """Library XY (Y up) -> schematic offset (Y down) for a CCW symbol rotation."""
    x, y = px, -py
    a = math.radians(rot)
    return (round(x * math.cos(a) + y * math.sin(a), 4), round(-x * math.sin(a) + y * math.cos(a), 4))


def outward(angle, rot):
    """Unit vector from the pin end away from the body, schematic coordinates."""
    dx, dy = xform(math.cos(math.radians(angle)), math.sin(math.radians(angle)), rot)
    return (-round(dx), -round(dy))


def r(v):
    return round(v, 2)


def net_name(net):
    """Exported name: power-symbol nets keep their value, labelled nets are sheet-local."""
    return net if net in RAIL_SYMBOL else '/' + net


def text_at(p):
    """(reference offset, value offset, justify) from the symbol origin, mm. Texts sit beside
    the body on the side the wires leave free."""
    sym, rot, unit, mir = p['sym'], p['rot'], p['unit'], p['mirror']
    left = ((-1.905, -0.635), (-1.905, 1.27), 'right')
    right = ((1.905, -0.635), (1.905, 1.27), 'left')
    if p['ref'] in TEXT_SIDE:
        return TEXT_SIDE[p['ref']]
    if sym == 'C' and rot in (90, 270):
        return (0, -3.81), (0, 3.81), None
    if sym in ('R', 'C'):
        return ((0, -2.54), (0, 2.54), None) if rot in (90, 270) else right
    if sym in ('D_Schottky', '1N4148W'):
        return ((0, -2.54), (0, 2.54), None) if rot in (0, 180) else left
    if sym == 'LED':
        return ((0, -3.175), (0, 3.175), None) if rot in (0, 180) else right
    if sym == 'R_Potentiometer':
        if rot in (90, 270):
            return (0, -4.45), (0, -2.54), None
        return ((2.54, 2.29), (2.54, 4.19), 'left') if not mir else ((-2.54, 2.29), (-2.54, 4.19), 'right')
    if sym == 'TL072':
        return ((-3.81, -0.635), (-3.81, 1.27), 'right') if unit == 3 else ((0, -7.62), (0, -5.715), None)
    if sym == 'DMMT3904W':
        return ((5.08, -0.635), (5.08, 1.27), 'left') if not mir else ((-5.08, -0.635), (-5.08, 1.27), 'right')
    if sym == 'LM13700':
        return ((-3.81, -0.635), (-3.81, 1.27), 'right') if unit == 5 else ((0, -7.62), (0, -5.715), None)
    if sym == 'Q_PNP_BEC':
        return (5.08, -0.635), (5.08, 1.27), 'left'
    if sym == 'SolderJumper_2_Open':
        return (0, -2.54), (0, 2.54), None
    if sym in ('AudioJack2_SwitchT', 'Conn_02x05_Odd_Even'):
        return (0, -8.89), (0, 8.89), None
    if sym == 'HT75xx-1-SOT89':
        return (0, -7.62), (0, -6.35), None
    if sym == 'PWR_FLAG':
        return (0, -5.08), (0, -2.54), None
    return left


# Per-part text placement overrides (reference offset, value offset, justify), mm.
TEXT_SIDE = {}


def power_symbol(net, x, y, d, key, root):
    """Stock power symbol whose pin sits at (x, y) and whose body points along d."""
    sym = RAIL_SYMBOL[net]
    body = (0, -1) if sym == 'GND' else (0, 1)          # library direction pin -> body
    rot = next(a for a in (0, 90, 180, 270) if tuple(round(v) for v in xform(*body, a)) == d)
    dx, dy = d
    just = [atom('justify'), atom('left' if (dx > 0) != (rot == 90) else 'right')] if dx else None
    vx, vy = r(x + dx * 3.81), r(y + dy * 3.81)
    ref = '#PWR' + key
    effects = [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]
    fa = 90 if rot in (90, 270) else 0
    props = [[atom('property'), 'Reference', ref, [atom('at'), x, y, 0],
              [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('hide'), atom('yes')]]],
             [atom('property'), 'Value', net, [atom('at'), vx, vy, fa], effects + ([just] if just else [])]]
    for name in ('Footprint', 'Datasheet', 'Description'):
        props.append([atom('property'), name, '', [atom('at'), x, y, 0],
                      [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('hide'), atom('yes')]]])
    return [atom('symbol'), [atom('lib_id'), f'{LIB}:{sym}'], [atom('at'), x, y, rot], [atom('unit'), 1],
            [atom('exclude_from_sim'), atom('no')], [atom('in_bom'), atom('no')], [atom('on_board'), atom('no')],
            [atom('in_pos_files'), atom('no')], [atom('dnp'), atom('no')], [atom('uuid'), uid('pwr/' + key)],
            *props, [atom('pin'), '1', [atom('uuid'), uid(f'pwr/{key}/pin')]],
            [atom('instances'), [atom('project'), PROJECT,
             [atom('path'), '/' + root, [atom('reference'), ref], [atom('unit'), 1]]]]]


def check_netlist(sch, nets, no_connects):
    """The native netlist must equal circuit() exactly: same net names, same pins."""
    import xml.etree.ElementTree as ET
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml), str(sch)],
                       check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(xml).getroot()
    got = {n.get('name'): {f"{d.get('ref')}/{d.get('pin')}" for d in n.findall('node')
                           if not d.get('ref').startswith('#')}
           for n in root.find('nets')}
    got = {k: v for k, v in got.items() if v}
    nc = {next(iter(v)) for k, v in got.items() if k.startswith('unconnected-') and len(v) == 1}
    assert nc == no_connects, f'no-connect pins differ: {sorted(nc ^ no_connects)}'
    got = {k: v for k, v in got.items() if not k.startswith('unconnected-')}
    want = {net_name(n): {k for k in keys if not k.startswith('#')} for n, keys in nets.items()}
    want = {k: v for k, v in want.items() if v}
    bad = {k: (sorted(got.get(k, ())), sorted(want.get(k, ()))) for k in set(got) | set(want)
           if got.get(k) != want.get(k)}
    assert not bad, 'netlist differs from circuit() (net: got, want):\n' + '\n'.join(
        f'  {k}: {v}' for k, v in sorted(bad.items()))


def on_segment(pt, a, b, ends=False):
    """pt on the axis-aligned segment a-b (interior only unless ends)."""
    (x, y), (x0, y0), (x1, y1) = pt, a, b
    inside = (x0 == x1 == x and min(y0, y1) <= y <= max(y0, y1)) or \
             (y0 == y1 == y and min(x0, x1) <= x <= max(x0, x1))
    return inside and (ends or pt not in (a, b))


# ---------------------------------------------------------------------------------------------
# Schematic wire router: 1.27 mm grid, A* with bend and crossing costs.
H = 1.27  # router pitch, mm
SHEET = (594.0, 420.0)  # A2


def node(x, y):
    return (round(x / H), round(y / H))


def text_box(x, y, s, size, just):
    """Rough box of a text (mm): (x0, y0, x1, y1)."""
    lines = s.split('\n')
    w = max(len(line) for line in lines) * size * 0.75
    h = len(lines) * size * 1.6
    if just == 'right':
        return (x - w, y - h / 2, x, y + h / 2)
    if just == 'left':
        return (x, y - h / 2, x + w, y + h / 2)
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


DEBUG = {}


class Unroutable(Exception):
    pass


def route_wires(parts, ends, lib_syms):
    """Route every signal net not in WIRES / LABEL_NETS. Returns {net: [path, ...]} in grid units
    (2.54 mm), the WIRES format."""
    blocked = set()

    src = DEBUG.setdefault('src', {})

    def block_box(x0, y0, x1, y1, tag=''):
        for i in range(math.floor(x0 / H + 1e-6), math.ceil(x1 / H - 1e-6) + 1):
            for j in range(math.floor(y0 / H + 1e-6), math.ceil(y1 / H - 1e-6) + 1):
                blocked.add((i, j))
                src.setdefault((i, j), []).append(tag)

    pin_nodes = {}
    for p in parts:
        pins = pin_table(lib_syms[p['sym']], p['unit'])
        if p['sym'] in ('PWR_FLAG',):
            continue
        pts = []
        for n in p['pins']:  # pin roots
            ex, ey, d, _ = ends[f"{p['ref']}/{n}"]
            L = pins[n][4]
            pts.append((ex - d[0] * L, ey - d[1] * L))
        x, y = p['at']
        for gx, gy in body_points(lib_syms[p['sym']], p['unit']):
            ox, oy = xform(gx, gy, p['rot'])
            pts.append((x + (-ox if p['mirror'] else ox), y + oy))
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        # one router node of clearance around the body
        block_box(x0 - H, y0 - H, x1 + H, y1 + H, p['ref'] + ' body')
        for n, net in p['pins'].items():  # pin lines
            ex, ey, d, _ = ends[f"{p['ref']}/{n}"]
            for k in range(1, round(pins[n][4] / H) + 1):
                blocked.add(node(ex - d[0] * k * H, ey - d[1] * k * H))
        # reference / value texts
        dr, dv, just = text_at(p)
        x, y = p['at']
        for (ox, oy), s in ((dr, p['ref']), (dv, p['value'])):
            block_box(*text_box(x + ox, y + oy, s, 1.27, just), p['ref'] + ' text')
    for (x, y), s, size in TEXTS:
        block_box(*text_box(x, y, s, size, 'left'), 'note')
    # every pin end: owned by its net; stubs + power symbols / labels of non-routed pins
    for k, (ex, ey, d, net) in ends.items():
        pin_nodes[node(ex, ey)] = (net, d)
        if net is None or net in RAIL_SYMBOL or net in LABEL_NETS:
            for s in range(0, 6 if net else 1):
                c = node(ex + d[0] * s * H, ey + d[1] * s * H)
                blocked.add(c)
                if s >= 2:
                    blocked.add((c[0] + d[1], c[1] + d[0]))
                    blocked.add((c[0] - d[1], c[1] - d[0]))
            if net in LABEL_NETS:
                for s in range(2, 2 + len(net)):
                    blocked.add(node(ex + d[0] * s * H, ey + d[1] * s * H))
    for c in pin_nodes:
        blocked.discard(c)
    # a body box wider than its pins (the LED's arrows reach past the cathode pin end): free the
    # lane straight out of a wired pin, as far as only that part's own body blocks it
    for k, (ex, ey, d, net) in ends.items():
        if net is None or net in RAIL_SYMBOL or net in LABEL_NETS:
            continue
        c = node(ex, ey)
        for s in range(1, 4):
            lane = (c[0] + d[0] * s, c[1] + d[1] * s)
            if set(src.get(lane, ())) != {k.split('/')[0] + ' body'}:
                break
            blocked.discard(lane)

    DEBUG["blocked"] = blocked
    occ = {}      # node -> {net: set of axes ('h', 'v')}
    points = {}   # node -> net (wire ends / bends / pins: nothing of another net may touch them)
    for c, (net, d) in pin_nodes.items():
        points[c] = net

    def cost_ok(c, net, axis):
        if c in blocked:
            return None
        if c in points and points[c] != net:
            return None
        o = occ.get(c, {})
        extra = 0
        for other, axes in o.items():
            if other == net:
                continue
            if axis in axes:
                return None
            extra += 6  # crossing
        # keep a free track beside other nets' parallel wires and points
        side = ((0, 1), (0, -1)) if axis == 'h' else ((1, 0), (-1, 0))
        for dx, dy in side:
            nb = (c[0] + dx, c[1] + dy)
            if any(k != net and axis in a for k, a in occ.get(nb, {}).items()):
                extra += 3
            if nb in points and points[nb] != net:
                extra += 3
        # prefer the 2.54 mm grid
        if (axis == 'h' and c[1] % 2) or (axis == 'v' and c[0] % 2):
            extra += 1
        return extra

    def astar(start, start_dir, targets, net):
        """targets: {node: required arrival direction or None}."""
        sx, sy = start
        first = (sx + start_dir[0], sy + start_dir[1])
        axis0 = 'h' if start_dir[0] else 'v'
        if cost_ok(first, net, axis0) is None and first not in targets:
            return None
        tx = [t for t in targets]
        def hcost(c):
            return min(abs(c[0] - t[0]) + abs(c[1] - t[1]) for t in tx)
        openq = [(hcost(first), 1, first, start_dir, (start, ))]
        best = {(first, start_dir): 1}
        W, Hh = round(SHEET[0] / H), round(SHEET[1] / H)
        while openq:
            f, g, c, d, path = heapq.heappop(openq)
            if c in targets:
                need = targets[c]
                # never make a four-way junction (ERC four_way_junction)
                if (need is None or need == (-d[0], -d[1])) and len(arms.get(c, set()) | {(-d[0], -d[1])}) < 4:
                    return list(path) + [c]
                continue
            if g > best.get((c, d), 1e9):
                continue
            for nd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if nd == (-d[0], -d[1]):
                    continue
                if nd != d:  # bending at c: c becomes a point; it must be free of other nets
                    o = occ.get(c, {})
                    if any(k != net for k in o) or (c in points and points[c] != net):
                        continue
                nc = (c[0] + nd[0], c[1] + nd[1])
                if not (0 < nc[0] < W and 0 < nc[1] < Hh):
                    continue
                axis = 'h' if nd[0] else 'v'
                if nc in targets:
                    if nc in occ and any(k != net for k in occ[nc]):
                        continue
                    extra = 0
                else:
                    extra = cost_ok(nc, net, axis)
                    if extra is None:
                        continue
                ng = g + 1 + extra + (4 if nd != d else 0)
                if ng < best.get((nc, nd), 1e9):
                    best[(nc, nd)] = ng
                    heapq.heappush(openq, (ng + hcost(nc), ng, nc, nd, path + (c, )))
        return None

    def simplify(path):
        out = [path[0]]
        for a, b, c in zip(path, path[1:], path[2:]):
            if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                out.append(b)
        out.append(path[-1])
        return out

    nets = {}
    for k, (ex, ey, d, net) in ends.items():
        if net is None or net in RAIL_SYMBOL or net in LABEL_NETS or net in WIRES:
            continue
        nets.setdefault(net, []).append((k, node(ex, ey), d))

    def span(item):
        pts = [q[1] for q in item[1]]
        return (max(q[0] for q in pts) - min(q[0] for q in pts)) + (max(q[1] for q in pts) - min(q[1] for q in pts))

    result = {}
    arms = {}  # node -> directions of the same-net wires and pin stubs that meet there
    for net, pins in sorted(nets.items(), key=span):
        for _, c, d in pins:
            arms.setdefault(c, set()).add((-d[0], -d[1]))
        pins = sorted(pins, key=lambda q: (q[1][0], q[1][1]))
        # target -> the pin's outward vector (a wire must arrive from outside) or None (wire node)
        targets = {pins[0][1]: (pins[0][2][0], pins[0][2][1])}
        paths = []
        rest = pins[1:]
        while rest:
            rest.sort(key=lambda q: min(abs(q[1][0] - t[0]) + abs(q[1][1] - t[1]) for t in targets))
            k, start, d = rest.pop(0)
            path = astar(start, d, targets, net)
            if path is None:
                raise Unroutable(net, k)
            path = simplify(path)
            paths.append(path)
            full = []
            for a, b in zip(path, path[1:]):
                n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
                step = ((b[0] - a[0]) // n, (b[1] - a[1]) // n)
                axis = 'h' if step[0] else 'v'
                arms.setdefault(a, set()).add(step)
                arms.setdefault(b, set()).add((-step[0], -step[1]))
                for i in range(n + 1):
                    c = (a[0] + step[0] * i, a[1] + step[1] * i)
                    if 0 < i < n:
                        arms.setdefault(c, set()).update({step, (-step[0], -step[1])})
                    occ.setdefault(c, {}).setdefault(net, set()).add(axis)
                    full.append(c)
            for c in path:
                points[c] = net
            for c in full:
                if c not in targets:
                    targets[c] = None
            targets[start] = None
        # arrival constraint applies only to bare pin ends; wire nodes accept any direction
        result[net] = [[(c[0] * H / GRID, c[1] * H / GRID) for c in path] for path in paths]
    return result


def wire_segments(ends, wires):
    """wires -> {net: [(a, b)]} split at every connection point, and the set of wired pins."""
    segments, wired = {}, set()
    for net, paths in wires.items():
        segs = []
        for path in paths:
            pts = []
            for tok in path:
                if isinstance(tok, str):
                    ex, ey, _, pin_net = ends[tok]
                    assert pin_net == net, f'{tok} is on {pin_net}, not {net}'
                    wired.add(tok)
                    pts.append((ex, ey))
                else:
                    pts.append((r(tok[0] * GRID), r(tok[1] * GRID)))
            for a, b in zip(pts, pts[1:]):
                assert a != b and (a[0] == b[0] or a[1] == b[1]), f'{net}: bad step {a} -> {b}'
                segs.append((a, b))
        nodes_ = {p for s in segs for p in s} | {e[:2] for e in ends.values() if e[3] == net}
        for k, e in ends.items():
            if e[3] == net and any(on_segment(e[:2], a, b, ends=True) for a, b in segs):
                wired.add(k)
        split = []
        for a, b in segs:
            cuts = sorted({p for p in nodes_ if on_segment(p, a, b)} | {a, b},
                          key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
            split += list(zip(cuts, cuts[1:]))
        segments[net] = split
    # no wire may touch a pin or wire end of another net
    allpts = {}
    for net, segs in segments.items():
        for s in segs:
            for q in s:
                allpts.setdefault(q, set()).add(net)
    for net, segs in segments.items():
        for a, b in segs:
            for p, owners in allpts.items():
                if net not in owners and on_segment(p, a, b, ends=True):
                    raise AssertionError(f'{net} {a}-{b} touches {owners} at {p}')
        for k, e in ends.items():
            if e[3] != net:
                for a, b in segs:
                    assert not on_segment(e[:2], a, b, ends=True), f'{net} {a}-{b} touches {k} ({e[3]})'
    return segments, wired


def name_spot(net, segs):
    """Label anchor: LABEL_AT override (grid units) or the left end of the longest horizontal run."""
    if net in LABEL_AT:
        x, y, *ang = LABEL_AT[net]
        return r(x * GRID), r(y * GRID), (ang[0] if ang else 0)
    horiz = [(a, b) for a, b in segs if a[1] == b[1]]
    if horiz:
        a, b = max(horiz, key=lambda s: abs(s[1][0] - s[0][0]))
        return r(min(a[0], b[0]) + 0.635), a[1], 0
    a, b = max(segs, key=lambda s: abs(s[1][1] - s[0][1]))
    return a[0], r(max(a[1], b[1]) - 0.635), 90


def junctions(segs, pin_pts):
    count = {}
    for a, b in segs:
        for p in (a, b):
            count[p] = count.get(p, 0) + 1
    for p in pin_pts:
        if p in count:
            count[p] += 1
    return sorted(p for p, n in count.items() if n >= 3)


def build():
    lib_syms, sources = {}, {}
    for key, (lib, name) in SYMBOLS.items():
        sym, src, parent = stock_symbol(lib, name)
        edit = None
        if key in FILTER_EDITS:
            prop = next(pp for pp in nodes(sym, 'property') if pp[1] == 'ki_fp_filters')
            edit = f'ki_fp_filters {prop[2]!r} -> {FILTER_EDITS[key]!r}'
            prop[2] = FILTER_EDITS[key]
        if key in RENAME:  # renamed stock body with re-numbered pins (see RENAME)
            old = sym[1]
            sym[1] = key
            for u in nodes(sym, 'symbol'):
                u[1] = u[1].replace(old, key, 1)
                unit = u[1].rsplit('_', 2)[-2]
                for pin in walk(u, 'pin'):
                    num = one(pin, 'number')
                    num[1] = RENAME[key][unit][num[1]]
            for prop in nodes(sym, 'property'):
                if prop[1] == 'Value':
                    prop[2] = key
                elif prop[1] == 'Footprint':
                    prop[2] = ''
                elif prop[1] == 'Datasheet':
                    prop[2] = 'https://www.diodes.com/assets/Datasheets/DMMT3904W.pdf'
                elif prop[1] == 'Description':
                    prop[2] = '40V matched pair NPN (2 mV VBE, 2 % hFE), SOT-363: 1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2'
            edit = f'renamed {old} -> {key}, pins re-numbered {RENAME[key]}'
        lib_syms[key] = sym
        sources[key] = {'library': f'{lib}:{name}', 'source': str(src).replace(str(Path.home()), '~', 1),
                        'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                        'flattened_from': parent, 'edits': edit}
    stock_header = parse((STOCK / 'Device.kicad_sym').read_text())
    lib = [atom('kicad_symbol_lib'), one(stock_header, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(lib_syms[k]) for k in sorted(lib_syms)]
    (HW / f'{LIB}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") '
        '(options "") (descr "LADDER pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A2")
      (title_block (title "Big Modular - LADDER") (rev "S5") (company "Big Modular")
        (comment 1 "SCHEMATIC S5 - pure-analog 6HP ladder filter: OTA resonance, bipolar CV LEDs")
        (comment 2 "Circuit intent: docs/research.md; ngspice check: tools/sim_ladder.py"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIB}:' + k
        embedded.append(s)

    items, nets, units, taken = [], {}, {}, {}
    parts = circuit()
    ends = {}  # 'REF/pin' -> (x, y, outward direction, net) in mm
    for p in parts:
        pins = pin_table(lib_syms[p['sym']], p['unit'])
        assert set(p['pins']) == set(pins), (p['ref'], p['unit'], sorted(pins), sorted(p['pins']))
        for n, net in p['pins'].items():
            px, py, ang, *_ = pins[n]
            ox, oy = xform(px, py, p['rot'])
            d = outward(ang, p['rot'])
            if p['mirror']:
                ox, d = -ox, (-d[0], d[1])
            ends[f"{p['ref']}/{n}"] = (r(p['at'][0] + ox), r(p['at'][1] + oy), d, net)
    if DEBUG_PLACEMENT:  # placement preview: every signal net label-joined, nothing routed
        LABEL_NETS.update(e[3] for e in ends.values() if e[3] and e[3] not in RAIL_SYMBOL)
    failed = []
    while True:
        try:
            routed = route_wires(parts, ends, lib_syms)
            break
        except Unroutable as e:  # fall back to labels for that net, report it, keep going
            failed.append(e.args)
            LABEL_NETS.add(e.args[0])
    wires = dict(WIRES)
    wires.update(routed)
    segments, wired = wire_segments(ends, wires)
    for p in parts:
        sym = lib_syms[p['sym']]
        units.setdefault(p['ref'], set()).add(p['unit'])
        x, y = p['at']
        is_flag = p['ref'].startswith('#')
        assembled = not is_flag and p['ref'] not in NOT_ASSEMBLED
        dr, dv, just = text_at(p)
        props = [('Reference', p['ref'], (x + dr[0], y + dr[1]), False, just),
                 ('Value', p['value'], (x + dv[0], y + dv[1]), is_flag, just),
                 ('Footprint', f"{LIB}:{FP[p['fp']]}" if p['fp'] else '', (x, y), True),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''), (x, y), True),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''), (x, y), True)]
        props += [(k, v, (x, y), True) for k, v in p['fields'].items()]
        ukey = p['ref'] if p['unit'] == 1 else f"{p['ref']}/{p['unit']}"
        node_ = [atom('symbol'), [atom('lib_id'), f'{LIB}:' + p['sym']], [atom('at'), x, y, p['rot']]]
        if p['mirror']:
            node_.append([atom('mirror'), atom('y')])
        node_ += [[atom('unit'), p['unit']], [atom('exclude_from_sim'), atom('no')],
                  [atom('in_bom'), atom('yes' if assembled else 'no')],
                  [atom('on_board'), atom('no' if is_flag else 'yes')],
                  [atom('in_pos_files'), atom('yes' if assembled else 'no')], [atom('dnp'), atom('no')],
                  [atom('uuid'), uid('sym/' + ukey)]]
        for name, value, (px, py), hide, *jst in props:
            # Field angle and justification are symbol-local in KiCad: undo the symbol
            # rotation so every text reads horizontally on the side text_at() chose.
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), 90 if p['rot'] in (90, 270) else 0],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if jst and jst[0]:
                flip = (p['rot'] in (90, 180)) != p['mirror']
                prop[-1].append([atom('justify'), atom({'left': 'right', 'right': 'left'}[jst[0]] if flip else jst[0])])
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node_.append(prop)
        all_pins = set().union(*(pin_table(sym, u) for u in range(1, 10)))
        node_ += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{ukey}/{n}")]] for n in sorted(all_pins)]
        node_.append([atom('instances'), [atom('project'), PROJECT,
                      [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), p['unit']]]]])
        items.append(node_)
        for n, net in sorted(p['pins'].items()):
            key = f"{p['ref']}/{n}"
            ex, ey, d, _ = ends[key]
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                continue
            nets.setdefault(net, []).append(key)
            if key in wired:
                continue
            sx, sy = r(ex + d[0] * STUB), r(ey + d[1] * STUB)
            stacked = taken.get((ex, ey))
            if stacked and stacked[0].split('/')[0] == p['ref'] and stacked[1] == net:
                continue  # stacked pins of one symbol (U2 GND 3 / EP 21): one stub serves both
            for pt in ((ex, ey), (sx, sy)):
                assert taken.setdefault(pt, (key, net))[1] == net, f'{key} touches {taken[pt]} at {pt}'
            items.append([atom('wire'), [atom('pts'), [atom('xy'), ex, ey], [atom('xy'), sx, sy]],
                          [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                          [atom('uuid'), uid('wire/' + key)]])
            if net in RAIL_SYMBOL:
                items.append(power_symbol(net, sx, sy, d, key.replace('/', '_').replace('#', ''), root))
            else:
                lang, lj = {(1, 0): (0, 'left'), (-1, 0): (180, 'right'),
                            (0, -1): (90, 'left'), (0, 1): (270, 'right')}[d]
                items.append([atom('label'), net, [atom('at'), sx, sy, lang],
                              [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                               [atom('justify'), atom(lj), atom('bottom')]],
                              [atom('uuid'), uid('label/' + key)]])
    unrouted = {k for k, e in ends.items() if e[3] and e[3] not in RAIL_SYMBOL and e[3] not in LABEL_NETS} - wired
    assert not unrouted, f'signal pins without a wire: {sorted(unrouted)}'
    stub_pts = {pt: v for pt, v in taken.items()}
    for net, segs in segments.items():
        for (a, b) in segs:
            for pt, (key, other) in stub_pts.items():
                assert not on_segment(pt, a, b, ends=True), f'{net} wire {a}-{b} touches {key} ({other}) at {pt}'
        for i, (a, b) in enumerate(segs):
            items.append([atom('wire'), [atom('pts'), [atom('xy'), *a], [atom('xy'), *b]],
                          [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                          [atom('uuid'), uid(f'net/{net}/{i}')]])
        # one name label per wired net, on its longest horizontal run (vertical if none)
        lx, ly, lang = name_spot(net, segs)
        items.append([atom('label'), net, [atom('at'), lx, ly, lang],
                      [atom('effects'), [atom('font'), [atom('size'), 1.0, 1.0]],
                       [atom('justify'), atom('left'), atom('bottom')]],
                      [atom('uuid'), uid('name/' + net)]])
        for pt in junctions(segs, [e[:2] for k, e in ends.items() if k in wired and e[3] == net]):
            items.append([atom('junction'), [atom('at'), *pt], [atom('diameter'), 0],
                          [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'junction/{net}/{pt}')]])
    multi = {ref: u for ref, u in units.items() if len(u) > 1}
    assert multi == MULTI, multi
    single = {n: k for n, k in nets.items() if len([x for x in k if not x.startswith('#')]) < 2}
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
    check_netlist(out, nets, {f"{p['ref']}/{n}" for p in parts for n, net in p['pins'].items()
                              if net is None})
    # The project file names the root sheet by its UUID.
    pro = HW / f'{PROJECT}.kicad_pro'
    if pro.exists():
        data = json.loads(pro.read_text())
        data['schematic']['top_level_sheets'][0]['uuid'] = root
        data['sheets'][0][0] = root
        pro.write_text(json.dumps(data, indent=2) + '\n')
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbols in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    print(out, f'{len(nets)} nets')
    if failed:
        raise SystemExit(f'router failed (label-joined in this build): {failed}')


if __name__ == '__main__':
    build()
