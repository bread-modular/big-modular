"""Generate the LOW S2 schematic (hardware/low.kicad_sch) and its pinned symbols.

Run from modules/low:
  python3 -B tools/build_schematic.py

Writes hardware/LOW.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the LOW library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
of docs/research.md section 3: Bread Modular MCO + LOW (LPG) on one 6HP Eurorack
module, both kept on their original 3.3 V signal level, with the 8bit MIDI input,
level-mapped AUDIO and CV bypass inputs that are normalled (through a TS5A23157 switch
driven by the jack switch contacts) to the MCO square mix and the MCO velocity DAC,
and a +/-12 V output stage.

Every pin gets a short stub and either a local net label or, for the supply nets, a
stock power symbol (as modules/midi), so connectivity is explicit by name. Multi-unit
symbols get one placed unit per entry. The build exports the native netlist and fails
unless it equals circuit().

The PCB never reads this table: tools/build_layout.py takes nets, values and
footprints from the native netlist that kicad-cli exports from this schematic.
"""
import copy
import hashlib
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
PROJECT = 'low'
LIB = 'LOW'
STUB = 2.54

FILTER_EDITS = {
    'Conn_01x02': '*_1x??_*',
    'Conn_02x05_Odd_Even': '*_2x??_*',
    'VTL5C': 'PerkinElmer*VTL5C* VTL5C',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'),
    'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'ATtiny1616-M': ('MCU_Microchip_ATtiny', 'ATtiny1616-M'),
    'HT75xx-1-SOT89': ('Regulator_Linear', 'HT75xx-1-SOT89'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'MCP6002-xSN': ('Amplifier_Operational', 'MCP6002-xSN'),
    'TS5A23157DGS': ('Analog_Switch', 'TS5A23157DGS'),
    'VTL5C': ('Isolator', 'VTL5C'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_01x02': ('Connector_Generic', 'Conn_01x02'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'MMBT3904': ('Transistor_BJT', 'MMBT3904'),
    '1N4148W': ('Diode', '1N4148W'),
    'BAT54SW': ('Diode', 'BAT54SW'),
    'GND': ('power', 'GND'), '+3V3': ('power', '+3V3'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric', 'C1206': 'C_1206_3216Metric',
    'SOD123': 'D_SOD-123', 'SOT23': 'SOT-23', 'SOT323': 'SOT-323_SC-70', 'SOT89': 'SOT-89-3',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'TSSOP10': 'TSSOP-10_3x3mm_P0.5mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09', 'VTL5C': 'VTL5C',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# Supply nets are drawn with power symbols (net name = symbol value); every other net
# carries a local label.
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# ATtiny1616-M (VQFN-20) pin numbers: the Bread Modular MCO pin map, unchanged, so its
# firmware runs as is. PB3 MIDI RX, PB4 tone 1 (TCB0), PB5 tone 2 (TCB1, detuned),
# PB0 DETUNE knob (ADC), PA6 velocity DAC, PA0 UPDI. PA7 (BM gate out) and PB2 (BM TX to
# the bus) are driven by the firmware but have no destination here: unconnected.
MCU = {'11': 'RX', '10': 'TONE1', '9': 'TONE2', '14': 'DETUNE', '7': 'DAC', '19': 'UPDI_PA0',
       '4': '+3V3', '3': 'GND', '21': 'GND',
       '8': None, '12': None, '1': None, '2': None, '5': None, '6': None, '13': None,
       '15': None, '16': None, '17': None, '18': None, '20': None}


def part(ref, sym, value, fp, pins, unit=1, **fields):
    key = ref if unit == 1 else f'{ref}.{unit}'
    x, y, rot, *mirror = LAYOUT[key]
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(round(x * GRID, 2), round(y * GRID, 2)), rot=rot,
                mirror=bool(mirror), pins=pins, unit=unit, fields=fields)


GRID = 2.54
# Symbol placement in 2.54 mm grid units: ref (unit 1) or ref.unit -> (x, y, rotation[, 'mirror']).
# 'mirror' flips the symbol left-right (used at rotation 0 only), so the U4 switches take
# their inputs on the left and the OUT jack its plug from the left. Signal flow runs left to
# right: MIDI -> MCU -> MCO mix (top left), AUDIO / CV bypass (middle left) -> U4 normals ->
# LOW driver + vactrol poles (top right) -> output (middle right); supplies along the bottom.
LAYOUT = {
    # MIDI input
    'J1': (6, 22, 0), 'R1': (12, 20.5, 180), 'R2': (16.5, 22, 90), 'D3': (20, 24.5, 270),
    'Q1': (23, 22, 0), 'R3': (24, 16.5, 180), 'JP1': (33, 18, 0),
    # MCU
    'U2': (18, 38, 0), 'C6': (8, 35.5, 0), 'R4': (27, 28.5, 180), 'J11': (27, 23, 90),
    'R12': (35.5, 37, 90), 'RV1': (38, 41.5, 90),
    # MCO mix
    'R5': (52.5, 44, 90), 'RV2': (48, 50, 0), 'R6': (54.5, 50, 90), 'U3': (66, 43, 0),
    'R7': (63.5, 48, 90), 'R8': (67.5, 48, 90), 'R9': (73.5, 43, 90),
    'R10': (53.5, 38, 90), 'R11': (58.5, 38, 90),
    # AUDIO bypass
    'J2': (44, 62, 0), 'R13': (48, 64.5, 0), 'C8': (51.5, 62, 90), 'R14': (56.5, 62, 90),
    'U3.2': (64, 61, 0), 'R15': (63.5, 66, 90), 'R16': (52, 68.5, 0),
    # CV bypass
    'J3': (44, 78, 0), 'R17': (51.5, 78, 90), 'R18': (53, 80.5, 0), 'D4': (65, 80, 180),
    'R19': (49, 83.5, 0),
    # Normals
    'U4': (90, 52, 0, 'mirror'), 'U4.2': (90, 78, 0, 'mirror'),
    # LOW driver
    'R23': (98, 17.5, 0), 'U8.2': (106, 16, 0), 'R24': (113.5, 16, 90), 'R25': (117, 18.5, 0),
    'U8': (124, 17, 0), 'RV3': (115, 24, 0), 'R26': (112.5, 27, 270),
    # LOW poles
    'U5': (106, 35, 270), 'C11': (110, 41.5, 0), 'U6': (116, 40, 0), 'U7': (126, 35, 270),
    'C12': (130, 41.5, 0), 'U6.2': (136, 40, 0), 'R20': (143.5, 40, 90),
    'R21': (107.5, 47, 90), 'R22': (112.5, 47, 90),
    # Output
    'U9': (130, 56, 0), 'R27': (129.5, 60, 90), 'R28': (126, 64.5, 0), 'R30': (137.5, 56, 90),
    'J4': (147, 56, 0, 'mirror'), 'U9.2': (118, 67, 0), 'C15': (120.5, 55, 90), 'R29': (124, 58.5, 0),
    # Power entry
    'J10': (9, 97, 0), 'D1': (21, 94, 180), 'D2': (21, 102, 0), 'C1': (28, 96.5, 0), 'C2': (32, 96.5, 0),
    'U1': (40, 95, 0), 'C3': (47, 96.5, 0), 'C4': (51, 96.5, 0), 'C5': (55, 96.5, 0),
    '#FLG01': (6, 108, 0), '#FLG02': (12, 108, 0), '#FLG03': (18, 108, 0), '#FLG04': (24, 108, 0),
    '#FLG05': (30, 108, 0),
    # Op-amp / switch supply units and their decoupling
    'U3.3': (64, 93, 0), 'C7': (68, 93.5, 0), 'U6.3': (77, 93, 0), 'C13': (81, 93.5, 0),
    'U8.3': (90, 93, 0), 'C14': (94, 93.5, 0), 'U4.3': (105, 93, 0), 'C9': (109, 93.5, 0),
    'U9.3': (119, 93, 0), 'C16': (123, 93.5, 0), 'C17': (128, 93.5, 0),
}

# Signal wiring: per net, polylines of 'REF/pin' pin ends and (x, y) grid points (axis-aligned
# steps). Junction dots are added where three or more wire ends / pins meet. A signal pin
# that no polyline reaches gets a stub and a net label instead (only VEL_CV, which would
# otherwise cross the whole sheet). Supply pins always get a stub and a power symbol.
# Net-name label positions (grid units, optional rotation) where the default spot is crowded.
LABEL_AT = {}

WIRES = {
    'MIDI_IN': [['J1/T', 'R1/1', 'R2/1'], ['R2/1', (15, 12), (37, 12), (37, 18), 'JP1/3']],
    'Q1_B': [['R2/2', (20, 22), 'Q1/1'], [(20, 22), 'D3/1']],
    'RX_Q': [['Q1/3', 'R3/1', 'JP1/1']],
    'RX': [['JP1/2', (33, 43), 'U2/11']],
    'UPDI_PA0': [['U2/19', (27, 31), 'R4/1']],
    'UPDI': [['R4/2', 'J11/1']],
    'DAC': [['U2/7', 'R12/1']],
    'DETUNE': [['U2/14', 'RV1/2']],
    'TONE1': [['U2/10', 'R5/1']],
    'TONE2': [['U2/9', (46, 45), (46, 53), (48, 53), 'RV2/3']],
    'MIX_W': [['RV2/2', 'R6/1']],
    'MCO_SUM': [['R5/2', (60, 44), (61, 44), 'U3/2'], ['R6/2', (60, 50), (60, 44)],
                [(61, 44), (61, 48), 'R7/1']],
    'MCO_FB': [['R7/2', 'R8/1']],
    'MCO_AMP': [['R8/2', (71, 48), (71, 43)], ['U3/1', (71, 43), 'R9/1']],
    'MCO_OUT': [['R9/2', (84, 43), (84, 51), 'U4/9']],
    'VMID_MCO': [['U3/3', (48, 42), 'RV2/1'], ['R10/2', (56, 38), 'R11/1'], [(56, 38), (56, 42)],
                 [(48, 47), (59, 47), (59, 60), 'U3/5']],
    'AIN': [['J2/T', (48, 62), 'C8/1'], [(48, 62), 'R13/1']],
    'AIN_AC': [['C8/2', 'R14/1']],
    'AIN_SUM': [['R14/2', (60, 62), 'U3/6'], [(60, 62), (60, 66), 'R15/1']],
    'AIN_BUF': [['R15/2', (69, 66), (69, 61)], ['U3/7', (69, 61), (85, 61), (85, 53), 'U4/2']],
    'AIN_SENSE': [['J2/TN', (47, 63), (47, 70), (90, 70), 'U4/1']],
    'CVIN': [['J3/T', 'R17/1']],
    'CVIN_DIV': [['R17/2', 'D4/3', (84, 78), (84, 79), 'U4/4'], ['R17/2', 'R18/1']],
    'CV_SENSE': [['J3/TN', (47, 79), (47, 86), (90, 86), 'U4/5'], [(49, 86), 'R19/2']],
    'LPG_IN': [['U4/10', (98, 52), (98, 40), (105, 40), 'U5/4']],
    'LPG_CV': [['U4/6', (96, 78), (96, 15), 'U8/5'], [(98, 15), 'R23/1']],
    'CV_F': [['U8/6', (102, 17), (102, 20), (110, 20), (110, 16)], ['U8/7', (110, 16), 'R24/1']],
    'CV_HALF': [['R24/2', (117, 16), 'U8/3'], [(117, 16), 'R25/1']],
    'VAC_POS': [['U8/1', (128, 17), (128, 29), (105, 29), 'U5/2'], [(125, 29), 'U7/2']],
    'VAC_NEG': [['U8/2', (120, 18), (120, 30), (107, 30), 'U5/1'], [(120, 30), (127, 30), 'U7/1'],
                ['RV3/2', (120, 24)]],
    'CUT_R': [['RV3/3', (115, 27), 'R26/1']],
    'LPF1': [['U5/3', (107, 39), (110, 39), 'U6/3'], [(110, 39), 'C11/1']],
    'LPG_B1': [['U6/2', (112, 41), (112, 43), (120, 43), (120, 40)], ['U6/1', (120, 40), (125, 40), 'U7/4']],
    'LPF2': [['U7/3', (127, 39), (130, 39), 'U6/5'], [(130, 39), 'C12/1']],
    'LPG_AMP': [['U6/6', (132, 41), (132, 43), (140, 43), (140, 40)], ['U6/7', (140, 40), 'R20/1']],
    'VMID_LPG': [['C11/2', (110, 45), (130, 45), 'C12/2'], [(110, 45), (110, 47)], ['R21/2', 'R22/1']],
    'LPG_OUT': [['R20/2', (146, 40), (146, 48), (118, 48), (118, 55), 'C15/1']],
    'OUT_IN': [['C15/2', 'U9/3'], [(124, 55), 'R29/1']],
    'OUT_FB': [['U9/2', (126, 57), (126, 60), 'R27/1'], [(126, 60), 'R28/1']],
    'OUT_AMP': [['R27/2', (134, 60), (134, 56)], ['U9/1', (134, 56), 'R30/1']],
    'AUDIO_OUT': [['R30/2', 'J4/T']],
    'U9B_FB': [['U9/6', (114, 68), (114, 70), (122, 70), (122, 67), 'U9/7']],
}


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7533-1 -> +3V3
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5',
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header on B, pin 1 (-12 V) at the left (as modules/vca-mix); '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(part('D1', 'D_Schottky', 'B5819W', 'SOD123',
                  {'1': '+12V_F', '2': '+12V'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D2', 'D_Schottky', 'B5819W', 'SOD123',
                  {'1': '-12V', '2': '-12V_F'}, Note='-12 V series reverse-polarity protection'))
    c.append(part('C1', 'C', '10u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='25V', Note='+12V_F bulk'))
    c.append(part('C2', 'C', '10u', 'C0805',
                  {'1': 'GND', '2': '-12V_F'}, Voltage='25V', Note='-12V_F bulk'))
    c.append(part('U1', 'HT75xx-1-SOT89', 'HT7533-1', 'SOT89',
                  {'1': 'GND', '2': '+12V_F', '3': '+3V3'},
                  Note='3.3 V LDO, 30 V max input, 100 mA (HT7550-1 family of modules/8bit). '
                       '~20 mA load: ~0.2 W at 11.6 V in'))
    c.append(part('C3', 'C', '1u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805',
                  {'1': '+3V3', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C5', 'C', '100u', 'C1206',
                  {'1': '+3V3', '2': 'GND'}, Voltage='6.3V', Note='+3V3 bulk (Bread Modular MCO C1 100uF 1206)'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V'}))

    # ---- MIDI input (TS modular MIDI): the 8bit / MIDI V2 NPN front end with its JP1 bypass,
    # pull-ups on +3V3 (the MCO runs at 3.3 V, as Bread Modular)
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(part('R1', 'R', '100k', 'R0603',
                  {'1': 'MIDI_IN', '2': '+3V3'}, Note='Idle pull-up: no cable turns Q1 on = UART idle'))
    c.append(part('R2', 'R', '10k', 'R0603',
                  {'1': 'MIDI_IN', '2': 'Q1_B'},
                  Note='Base resistor: ~1.1 mA at +/-12 V; 0.26 mA from a 3.3 V sender'))
    c.append(part('D3', '1N4148W', '1N4148W', 'SOD123',
                  {'1': 'Q1_B', '2': 'GND'},
                  Note='Clamps Q1 B-E to -0.7 V for a negative input (VEBO 6 V)'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23',
                  {'1': 'Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting input buffer: input high = RX low. Firmware: PORT_INVEN on PB3'))
    c.append(part('R3', 'R', '22k', 'R0603',
                  {'1': 'RX_Q', '2': '+3V3'},
                  Note='Q1 collector pull-up, on RX_Q so the JP1 direct path leaves PB3 unloaded'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3',
                  {'1': 'RX_Q', '2': 'RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. Solder 1-2 = protected '
                       '(Q1 drives PB3, PORT_INVEN on). Solder 2-3 = direct/unprotected '
                       '(MIDI_IN to PB3, PORT_INVEN off, stock BM MCO firmware; 3.3 V senders only). '
                       'Never both'))

    # ---- MCO: Bread Modular MCO, unchanged (ATtiny1616 at 3.3 V, two square tones mixed by
    # an inverting summer around V_MID; DETUNE knob on PB0, detuned-tone level knob)
    c.append(part('U2', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', MCU,
                  Note='3.3 V, as Bread Modular MCO'))
    c.append(part('C6', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U2 decoupling (Bread Modular MCO C2)'))
    c.append(part('R4', 'R', '4.7k', 'R0603',
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular R17)'))
    c.append(part('J11', 'Conn_01x02', 'UPDI', 'H1x2',
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power (3.3 V target)'))
    c.append(part('R12', 'R', '1k', 'R0603',
                  {'1': 'DAC', '2': 'VEL_CV'},
                  Note='Velocity DAC series R (Bread Modular R1): the LPG CV normal'))
    c.append(part('RV1', 'R_Potentiometer', '50k', 'RV09',
                  {'1': '+3V3', '2': 'DETUNE', '3': 'GND'},
                  Note='DETUNE (Bread Modular MCO RV1): 0..12 semitones on PB0. RV09 9 mm vertical, linear '
                       '(user stock). Hand-soldered'))

    c.append(part('RV2', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'VMID_MCO', '2': 'MIX_W', '3': 'TONE2'},
                  Note='MIX: detuned tone level (Bread Modular MCO RV2), CCW = V_MID = silent. RV09 9 mm '
                       'vertical, linear (user stock). Hand-soldered'))
    c.append(part('R5', 'R', '1M', 'R0603', {'1': 'TONE1', '2': 'MCO_SUM'},
                  Note='Tone 1 summing resistor (Bread Modular R6)'))
    c.append(part('R6', 'R', '1M', 'R0603', {'1': 'MIX_W', '2': 'MCO_SUM'},
                  Note='Tone 2 summing resistor (Bread Modular R10)'))
    c.append(part('R7', 'R', '200k', 'R0603', {'1': 'MCO_SUM', '2': 'MCO_FB'},
                  Note='Summer feedback, 2 x 200k (Bread Modular R11)'))
    c.append(part('R8', 'R', '200k', 'R0603', {'1': 'MCO_FB', '2': 'MCO_AMP'},
                  Note='Summer feedback, 2 x 200k (Bread Modular R12)'))
    c.append(part('R9', 'R', '1k', 'R0603', {'1': 'MCO_AMP', '2': 'MCO_OUT'},
                  Note='MCO output resistor (Bread Modular R8): the LPG audio normal'))
    c.append(part('R10', 'R', '1k', 'R0603', {'1': '+3V3', '2': 'VMID_MCO'},
                  Note='V_MID divider (Bread Modular MCO R3)'))
    c.append(part('R11', 'R', '1k', 'R0603', {'1': 'VMID_MCO', '2': 'GND'},
                  Note='V_MID divider (Bread Modular MCO R4)'))
    c.append(part('U3', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'VMID_MCO', '2': 'MCO_SUM', '1': 'MCO_AMP'}, unit=1,
                  Note='3.3 V rail-to-rail. A: MCO summer (Bread Modular U3A); B: AUDIO bypass input stage'))
    c.append(part('U3', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'VMID_MCO', '6': 'AIN_SUM', '7': 'AIN_BUF'}, unit=2,
                  Note='3.3 V rail-to-rail. A: MCO summer (Bread Modular U3A); B: AUDIO bypass input stage'))
    c.append(part('U3', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'8': '+3V3', '4': 'GND'}, unit=3,
                  Note='3.3 V rail-to-rail. A: MCO summer (Bread Modular U3A); B: AUDIO bypass input stage'))
    c.append(part('C7', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U3 decoupling'))

    # ---- AUDIO bypass in: AC coupled, inverting x0.33 around V_MID: +/-5 V (10 Vpp) -> 0..3.3 V;
    # hotter signals clip at the MCP6002 rails (intended: Bread Modular level character).
    # Jack switch: unplugged, TN = T = R13 to GND -> AIN_SENSE low -> U4 selects the MCO.
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'AIN', 'S': 'GND', 'TN': 'AIN_SENSE'},
                  Note='AUDIO bypass in. Unpatched: the LPG plays the MCO (TN switch -> U4)'))
    c.append(part('R13', 'R', '100k', 'R0603', {'1': 'AIN', '2': 'GND'},
                  Note='Input bias (keeps C8 discharged) and the jack-detect low level: 0.3 V with R16'))
    c.append(part('C8', 'C', '1u', 'C0805', {'1': 'AIN', '2': 'AIN_AC'},
                  Voltage='50V', Note='AC coupling: 1.6 Hz with R14 (removes the Eurorack DC reference)'))
    c.append(part('R14', 'R', '100k', 'R0603', {'1': 'AIN_AC', '2': 'AIN_SUM'},
                  Note='Input resistor; virtual ground at V_MID, so +/-12 V in stays within the U3 rails'))
    c.append(part('R15', 'R', '33k', 'R0603', {'1': 'AIN_SUM', '2': 'AIN_BUF'},
                  Note='Feedback: gain -0.33 (10 Vpp -> 3.3 Vpp around V_MID)'))
    c.append(part('R16', 'R', '1M', 'R0603', {'1': '+3V3', '2': 'AIN_SENSE'},
                  Note='Jack-detect pull-up: plugged = TN open = high = external audio'))

    # ---- CV bypass in: 0..5 V -> 0..3.3 V (R17/R18, loaded by R24 through U4), BAT54SW clamp.
    c.append(part('J3', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'CVIN', 'S': 'GND', 'TN': 'CV_SENSE'},
                  Note='CV bypass in, 0..5 V. Unpatched: the LPG follows the MCO velocity DAC (TN switch -> U4)'))
    c.append(part('R17', 'R', '51k', 'R0603', {'1': 'CVIN', '2': 'CVIN_DIV'},
                  Note='CV divider top; input impedance 161k. Limits the clamp current to 0.23 mA at -12 V'))
    c.append(part('R18', 'R', '110k', 'R0603', {'1': 'CVIN_DIV', '2': 'GND'},
                  Note='CV divider bottom: 110k || R24 1M = 99.1k -> 5.0 V in = 3.30 V at the LPG'))
    c.append(part('D4', 'BAT54SW', 'BAT54SW', 'SOT323',
                  {'1': 'GND', '2': '+3V3', '3': 'CVIN_DIV'},
                  Note='CV clamp: holds U4 / U8 within -0.3..+3.6 V for a +/-12 V mis-patch'))
    c.append(part('R19', 'R', '1M', 'R0603', {'1': '+3V3', '2': 'CV_SENSE'},
                  Note='Jack-detect pull-up: unplugged 0.46 V (R17 + R18 to GND), plugged = high = external CV'))

    # ---- Normals: TS5A23157 dual SPDT. IN low (jack empty) -> COM = NC = the MCO signal;
    # IN high (jack patched) -> COM = NO = the bypass input. Pins as TI SCDS175 (DGS).
    c.append(part('U4', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'1': 'AIN_SENSE', '2': 'AIN_BUF', '9': 'MCO_OUT', '10': 'LPG_IN'}, unit=1,
                  Note='Dual 10R SPDT on +3V3: the AUDIO / CV normals. Pin map TI DGS: 1 IN1, 2 NO1, 3 GND, '
                       '4 NO2, 5 IN2, 6 COM2, 7 NC2, 8 V+, 9 NC1, 10 COM1'))
    c.append(part('U4', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'4': 'CVIN_DIV', '5': 'CV_SENSE', '6': 'LPG_CV', '7': 'VEL_CV'}, unit=2,
                  Note='Dual 10R SPDT on +3V3: the AUDIO / CV normals. Pin map TI DGS: 1 IN1, 2 NO1, 3 GND, '
                       '4 NO2, 5 IN2, 6 COM2, 7 NC2, 8 V+, 9 NC1, 10 COM1'))
    c.append(part('U4', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'3': 'GND', '8': '+3V3'}, unit=3,
                  Note='Dual 10R SPDT on +3V3: the AUDIO / CV normals. Pin map TI DGS: 1 IN1, 2 NO1, 3 GND, '
                       '4 NO2, 5 IN2, 6 COM2, 7 NC2, 8 V+, 9 NC1, 10 COM1'))
    c.append(part('C9', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U4 decoupling'))

    # ---- LOW: Bread Modular LOW, unchanged: two vactrol RC poles (LDR + 10n to V_MID, MCP6002
    # followers); driver U8B CV follower, R22/R23 halve it, U8A forces the LED cathodes to CV/2,
    # so the LED current = (CV/2) / (CUTOFF rheostat + 330R). No BLAST button (user brief).
    c.append(part('U5', 'VTL5C', 'VTL5C', 'VTL5C',
                  {'1': 'VAC_NEG', '2': 'VAC_POS', '3': 'LPF1', '4': 'LPG_IN'},
                  Note='Vactrol 1 (Chinese VTL5C type, Bread Modular LOW U1), hand-soldered THT on B behind '
                       'the CUTOFF pot (as modules/vca-mix)'))
    c.append(part('C11', 'C', '10n', 'C0603', {'1': 'LPF1', '2': 'VMID_LPG'},
                  Voltage='50V', Note='Pole 1 C (Bread Modular LOW C2)'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'LPF1', '2': 'LPG_B1', '1': 'LPG_B1'}, unit=1,
                  Note='3.3 V. A/B: pole followers (Bread Modular LOW U2)'))
    c.append(part('U7', 'VTL5C', 'VTL5C', 'VTL5C',
                  {'1': 'VAC_NEG', '2': 'VAC_POS', '3': 'LPF2', '4': 'LPG_B1'},
                  Note='Vactrol 2 (Chinese VTL5C type, Bread Modular LOW U3), hand-soldered THT on B behind '
                       'the CUTOFF pot (as modules/vca-mix)'))
    c.append(part('C12', 'C', '10n', 'C0603', {'1': 'LPF2', '2': 'VMID_LPG'},
                  Voltage='50V', Note='Pole 2 C (Bread Modular LOW C3)'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'LPF2', '6': 'LPG_AMP', '7': 'LPG_AMP'}, unit=2,
                  Note='3.3 V. A/B: pole followers (Bread Modular LOW U2)'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'8': '+3V3', '4': 'GND'}, unit=3,
                  Note='3.3 V. A/B: pole followers (Bread Modular LOW U2)'))
    c.append(part('C13', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U6 decoupling (Bread Modular LOW C1)'))
    c.append(part('R20', 'R', '1k', 'R0603', {'1': 'LPG_AMP', '2': 'LPG_OUT'},
                  Note='LOW output resistor (Bread Modular R5)'))
    c.append(part('R21', 'R', '1k', 'R0603', {'1': '+3V3', '2': 'VMID_LPG'},
                  Note='V_MID divider (Bread Modular LOW R1)'))
    c.append(part('R22', 'R', '1k', 'R0603', {'1': 'VMID_LPG', '2': 'GND'},
                  Note='V_MID divider (Bread Modular LOW R2)'))

    c.append(part('U8', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'LPG_CV', '6': 'CV_F', '7': 'CV_F'}, unit=2,
                  Note='3.3 V. B: CV follower; A: vactrol LED driver (Bread Modular LOW U5)'))
    c.append(part('U8', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'CV_HALF', '2': 'VAC_NEG', '1': 'VAC_POS'}, unit=1,
                  Note='3.3 V. B: CV follower; A: vactrol LED driver (Bread Modular LOW U5)'))
    c.append(part('U8', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'8': '+3V3', '4': 'GND'}, unit=3,
                  Note='3.3 V. B: CV follower; A: vactrol LED driver (Bread Modular LOW U5)'))
    c.append(part('R23', 'R', '1M', 'R0603', {'1': 'LPG_CV', '2': 'GND'},
                  Note='CV pull-down (Bread Modular LOW R11)'))
    c.append(part('R24', 'R', '1M', 'R0603', {'1': 'CV_F', '2': 'CV_HALF'},
                  Note='CV / 2 (Bread Modular LOW R3)'))
    c.append(part('R25', 'R', '1M', 'R0603', {'1': 'CV_HALF', '2': 'GND'},
                  Note='CV / 2 (Bread Modular LOW R4)'))
    c.append(part('RV3', 'R_Potentiometer', '50k', 'RV09',
                  {'1': None, '2': 'VAC_NEG', '3': 'CUT_R'},
                  Note='CUTOFF (Bread Modular LOW RV1): LED current rheostat, pin 1 open, as Bread Modular. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))
    c.append(part('R26', 'R', '330', 'R0603', {'1': 'CUT_R', '2': 'GND'},
                  Note='LED current limit (Bread Modular LOW R6): <= 5 mA at CV 3.3 V'))
    c.append(part('C14', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U8 decoupling (Bread Modular LOW C4)'))

    # ---- Output: AC coupled (C15 + R29, 1.6 Hz) so OUT centres on 0 V whatever the LOW's
    # resting level; U9A non-inverting gain 3: 3.3 Vpp -> 9.9 Vpp (+/-4.95 V). 1k series to the jack.
    c.append(part('C15', 'C', '1u', 'C0805', {'1': 'LPG_OUT', '2': 'OUT_IN'},
                  Voltage='25V', Note='Output AC coupling (sees V_MID 1.65 V DC)'))
    c.append(part('R29', 'R', '100k', 'R0603', {'1': 'OUT_IN', '2': 'GND'},
                  Note='AC coupling bias to 0 V: 1u x 100k = 1.6 Hz high-pass'))
    c.append(part('U9', 'TL072', 'TL072', 'SOIC8',
                  {'3': 'OUT_IN', '2': 'OUT_FB', '1': 'OUT_AMP'}, unit=1,
                  Note='+/-12 V. A: output amplifier; B: unused, follower tied to GND'))
    c.append(part('U9', 'TL072', 'TL072', 'SOIC8',
                  {'5': 'GND', '6': 'U9B_FB', '7': 'U9B_FB'}, unit=2,
                  Note='+/-12 V. A: output amplifier; B: unused, follower tied to GND'))
    c.append(part('U9', 'TL072', 'TL072', 'SOIC8',
                  {'4': '-12V_F', '8': '+12V_F'}, unit=3,
                  Note='+/-12 V. A: output amplifier; B: unused, follower tied to GND'))
    c.append(part('R27', 'R', '20k', 'R0603', {'1': 'OUT_FB', '2': 'OUT_AMP'},
                  Note='Rf: gain 1 + 20k/10k = 3'))
    c.append(part('R28', 'R', '10k', 'R0603', {'1': 'OUT_FB', '2': 'GND'},
                  Note='Rg to GND'))
    c.append(part('R30', 'R', '1k', 'R1206', {'1': 'OUT_AMP', '2': 'AUDIO_OUT'},
                  Power='0.5W', Note='Output series: short / mis-patch current limit; 0.5 W for a permanent '
                                     '+/-12 V mis-patch (as modules/8bit R12)'))
    c.append(part('J4', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'AUDIO_OUT', 'S': 'GND', 'TN': None}, Note='Audio out, Eurorack level (~10 Vpp)'))
    c.append(part('C16', 'C', '100n', 'C0603',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U9 V+ decoupling'))
    c.append(part('C17', 'C', '100n', 'C0603',
                  {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U9 V- decoupling'))
    return c


def T(x, y):
    return (round(x * GRID, 2), round(y * GRID, 2))


TEXTS = [
    (T(4, 6), 'BIG MODULAR LOW - S2 schematic: Bread Modular MCO + LOW (LPG) on one 6HP module, '
              '3.3 V internal signals as Bread Modular. Circuit intent: docs/research.md', 2.0),
    (T(4, 7.5), 'Signal nets are wired; supplies use power symbols. VEL_CV (U2 DAC -> U4B NC2) is joined by '
              'its two net labels.', 1.27),
    (T(39, 14.5), 'MIDI IN (TS): 8bit / MIDI V2 NPN front end, pull-ups on +3V3.\n'
              'JP1 shipped OPEN: 1-2 = protected (PORT_INVEN on PB3), 2-3 = direct (BM firmware).', 1.27),
    (T(6, 52), 'MCO MCU: ATtiny1616 at 3.3 V, Bread Modular\nMCO pin map: PB3 RX, PB4/PB5 tones,\n'
               'PB0 DETUNE, PA6 velocity DAC.\nPA7 gate, PB2 TX unused.', 1.27),
    (T(44, 34.5), 'MCO MIX (Bread Modular MCO): U3A inverting summer around VMID_MCO.', 1.27),
    (T(36, 55.5), 'AUDIO BYPASS: AC coupled, x -0.33 around V_MID (10 Vpp -> 0..3.3 V, hotter clips).', 1.27),
    (T(36, 74), 'CV BYPASS: 0..5 V -> 0..3.3 V (R17/R18 with R23), BAT54SW clamp.', 1.27),
    (T(99, 81), 'NORMALS (U4 TS5A23157): jack empty -> TN = T pulls IN low -> COM = NC (MCO_OUT / VEL_CV);\n'
                  'patched -> TN open, 1M pulls IN high -> COM = NO (AIN_BUF / CVIN_DIV).', 1.27),
    (T(98, 7.5), 'LOW (Bread Modular LOW, no BLAST button): U8B CV follower, R24/R25 halve it, U8A holds the\n'
                 'LED cathodes at CV/2; CUTOFF rheostat + 330R set the LED current. Two vactrol poles, U6 followers.', 1.27),
    (T(100, 73), 'OUTPUT: C15/R29 AC coupling (1.6 Hz), U9A x3:\n3.3 Vpp -> +/-4.95 V around 0 V, 1k to J4.', 1.27),
    (T(4, 90.5), 'POWER: +12V -> D1 -> +12V_F (U9, U1 HT7533-1 -> +3V3); -12V -> D2 -> -12V_F (U9).', 1.27),
    (T(58, 101), 'SUPPLY PINS + DECOUPLING', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/low/schematic/' + key))


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
    """Pins of one unit (body style 1) plus the pins common to all units."""
    out = {}
    for u in nodes(sym, 'symbol'):
        num = u[1].rsplit('_', 2)[-2]
        if num not in ('0', str(unit)):
            continue
        for p in walk(u, 'pin'):
            at = one(p, 'at')
            out[one(p, 'number')[1]] = (float(at[1]), float(at[2]), float(at[3]), p[1])
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
    sym, rot, unit = p['sym'], p['rot'], p['unit']
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
    if sym == 'R_Potentiometer':
        return ((2.54, 2.29), (2.54, 4.19), 'left') if rot == 0 else ((2.54, -4.45), (2.54, -2.54), 'left')
    if sym == 'BAT54SW':
        return (0, 2.54), (0, 4.45), None
    if sym in ('MCP6002-xSN', 'TL072'):
        return ((-3.81, -0.635), (-3.81, 1.27), 'right') if unit == 3 else ((0, -10.16), (0, -7.62), None)
    if sym == 'TS5A23157DGS':
        return ((-6.35, -0.635), (-6.35, 1.27), 'right') if unit == 3 else ((0, -10.16), (0, -7.62), None)
    if sym == 'ATtiny1616-M':
        return (10.16, -25.4), (10.16, 25.4), None
    if sym == 'VTL5C':
        return ((-5.08, -0.635), (-5.08, 1.27), 'right')
    if sym in ('AudioJack2_SwitchT', 'Conn_02x05_Odd_Even'):
        return (0, -8.89), (0, 8.89), None
    if sym == 'Conn_01x02':
        return ((5.08, -0.635), (5.08, 1.27), 'left')
    if sym == 'MMBT3904':
        return ((-2.54, -6.35), (-2.54, -4.7), 'right')
    if sym == 'SolderJumper_3_Open':
        return (0, -5.08), (0, -3.175), None
    if sym == 'HT75xx-1-SOT89':
        return (0, -7.62), (0, -6.35), None
    if sym == 'PWR_FLAG':
        return (0, -5.08), (0, -2.54), None
    return left


# Per-part text placement overrides (reference offset, value offset, justify), mm.
TEXT_SIDE = {'RV3': ((-2.54, -0.635), (-2.54, 1.27), 'right'),
             'C11': ((-1.905, -0.635), (-1.905, 1.27), 'right'),
             'C12': ((-1.905, -0.635), (-1.905, 1.27), 'right')}


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


def wire_segments(ends):
    """WIRES -> {net: [(a, b)]} split at every connection point, and the set of wired pins."""
    segments, wired = {}, set()
    for net, paths in WIRES.items():
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
        # every pin end of this net (wired or lying on a wire) and every wire end is a node
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
    # no wire may touch a pin or wire of another net
    for net, segs in segments.items():
        for other, osegs in segments.items():
            if other == net:
                continue
            for a, b in segs:
                for p in {q for s in osegs for q in s}:
                    assert not on_segment(p, a, b, ends=True), f'{net} {a}-{b} touches {other} at {p}'
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
        '(options "") (descr "LOW pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - LOW") (rev "S2") (company "Big Modular")
        (comment 1 "SCHEMATIC S2 - Bread Modular MCO + LOW (LPG), 3.3 V signals, wired nets")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
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
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, py, p['rot'])
            d = outward(ang, p['rot'])
            if p['mirror']:
                ox, d = -ox, (-d[0], d[1])
            ends[f"{p['ref']}/{n}"] = (r(p['at'][0] + ox), r(p['at'][1] + oy), d, net)
    segments, wired = wire_segments(ends)
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
        node = [atom('symbol'), [atom('lib_id'), f'{LIB}:' + p['sym']], [atom('at'), x, y, p['rot']]]
        if p['mirror']:
            node.append([atom('mirror'), atom('y')])
        node += [[atom('unit'), p['unit']], [atom('exclude_from_sim'), atom('no')],
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
            node.append(prop)
        all_pins = set().union(*(pin_table(sym, u) for u in range(1, 10)))
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{ukey}/{n}")]] for n in sorted(all_pins)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), p['unit']]]]])
        items.append(node)
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
                assert taken.setdefault(pt, (key, net))[0] == key, f'{key} touches {taken[pt]} at {pt}'
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
    assert multi == {k: {1, 2, 3} for k in ('U3', 'U4', 'U6', 'U8', 'U9')}, multi
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
    data = json.loads(pro.read_text())
    data['schematic']['top_level_sheets'][0]['uuid'] = root
    data['sheets'][0][0] = root
    pro.write_text(json.dumps(data, indent=2) + '\n')
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbols in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    print(out, f'{len(nets)} nets')


if __name__ == '__main__':
    build()
