"""Generate the ACID S2 schematic (hardware/acid.kicad_sch) and its pinned symbols.

Run from modules/acid:
  python3 -B tools/build_schematic.py

Writes hardware/ACID.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the ACID library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
of docs/research.md section 3: Bread Modular MCO + ENV (one ATtiny1616) -> SVF (two
vactrol integrators; LP, HP and BP outputs, each one TL072 gain stage) on one 8HP Eurorack module,
all on Bread Modular's 3.3 V signal level, with the 8bit MIDI input, level-mapped AUDIO
and CV bypass inputs normalled (TS5A23157, as modules/low) to the MCO square mix and the
envelope DAC, three +/-12 V audio outputs and a protected 0..5 V envelope CV output.

Placement (LAYOUT) is by hand. Signal wires are found by route_wires(): a small grid
router (1.27 mm) that draws every signal net as axis-aligned wires, never touching a
pin, stub, symbol body or wire end of another net (perpendicular crossings without a
junction are allowed). LABEL_NETS are the only signal nets joined by name labels.
Supply pins get a stub and a stock power symbol. The build exports the native netlist
and fails unless it equals circuit().
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
PROJECT = 'acid'
LIB = 'ACID'
STUB = 2.54

FILTER_EDITS = {
    'Conn_01x02': '*_1x??_*',
    'Conn_02x05_Odd_Even': '*_2x??_*',
    'VTL5C': 'PerkinElmer*VTL5C* VTL5C',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LED': ('Device', 'LED'),
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
    'SW_Push': ('Switch', 'SW_Push'),
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
    'LED3': 'LED_D3.0mm', 'SW6': 'SW_PUSH_6mm_H7.3mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# Supply nets are drawn with power symbols (net name = symbol value).
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Signal nets joined by name labels (a stub + label on every pin) instead of wires: the
# envelope CV leaves the MCU block for the normal switch and the CV output stage.
LABEL_NETS = {'ENV_CV'}

# ATtiny1616-M (VQFN-20) pin numbers. Bread Modular MCO map unchanged (PB3 MIDI RX, PB4/PB5
# tones, PB0 DETUNE, PA6 DAC, PA0 UPDI) plus the Bread Modular ENV map (PA1/PA2 time knobs,
# PC0 algorithm button, PC1 its LED, PC2 second button, PC3 its LED). New: PA4/PA5 drive
# the two extra envelope-mode LEDs. PA3, PA7 (MCO gate), PB1, PB2 (MCO TX / ENV gate in)
# are unused.
MCU = {'11': 'RX', '10': 'TONE1', '9': 'TONE2', '14': 'DETUNE', '7': 'DAC', '19': 'UPDI_PA0',
       '20': 'ENV_A', '1': 'ENV_R', '15': 'MODE_SW', '16': 'LED_HR', '5': 'LED_AR', '6': 'LED_ASR',
       '17': 'REC_SW', '18': 'LED_REC',
       '4': '+3V3', '3': 'GND', '21': 'GND',
       '2': None, '8': None, '12': None, '13': None}

GRID = 2.54
OFFSET = (4, 4)  # LAYOUT / TEXTS origin inside the A2 frame, grid units
DEBUG_PLACEMENT = bool(__import__('os').environ.get('ACID_PLACEMENT_ONLY'))


def part(ref, sym, value, fp, pins, unit=1, **fields):
    key = ref if unit == 1 else f'{ref}.{unit}'
    x, y, rot, *mirror = LAYOUT[key]
    x, y = x + OFFSET[0], y + OFFSET[1]
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(round(x * GRID, 2), round(y * GRID, 2)), rot=rot,
                mirror=bool(mirror), pins=pins, unit=unit, fields=fields)


# Symbol placement in 2.54 mm grid units: ref (unit 1) or ref.unit -> (x, y, rotation[, 'mirror']).
# Rows, left to right: MIDI -> MCU (+ envelope buttons/LEDs left, knobs right) -> MCO mix;
# AUDIO / CV bypass -> U4 normals -> SVF -> LP / HP / BP outputs + CV out; power and supply pins at the bottom.
LAYOUT = {
    # MIDI input (as modules/low)
    'J1': (6, 22, 0), 'R1': (12, 20.5, 180), 'R2': (16.5, 22, 90), 'D3': (20, 24.5, 270),
    'Q1': (23, 22, 0), 'R3': (24, 16.5, 180), 'JP1': (33, 18, 0),
    # MCU, UPDI
    'U2': (40, 52, 0), 'C6': (30, 40, 0), 'R4': (50, 36, 180), 'J11': (58, 32, 0),
    # Envelope UI, left of the MCU: PC0..PC3 fan out to four columns
    'SW1': (14, 66, 270), 'R13': (19, 65.5, 0), 'D4': (19, 70.5, 90),
    'SW2': (24, 66, 270), 'R16': (29, 65.5, 0), 'D7': (29, 70.5, 90),
    # Envelope UI, right of the MCU: knobs, mode LEDs AR / ASR, DAC
    'RV3': (60, 40, 180), 'RV4': (68, 42, 180),
    'R14': (54, 49, 90), 'D5': (60, 49, 180), 'R15': (54, 54, 90), 'D6': (60, 54, 180),
    'R12': (70, 51, 90),
    # MCO mix (Bread Modular MCO)
    'RV1': (54, 62, 0, 'mirror'), 'RV2': (64, 72, 0), 'R5': (66, 62, 90), 'R6': (70, 72, 90),
    'U3': (82, 63, 0), 'R7': (79.5, 68, 90), 'R8': (85.5, 68, 90), 'R9': (92, 63, 90),
    'R10': (70, 56, 0), 'R11': (74, 56, 0),
    # AUDIO bypass (U3B)
    'J2': (50, 90, 0), 'R17': (56, 93, 0), 'C8': (60, 90, 90), 'R18': (66, 90, 90),
    'U3.2': (80, 89, 0), 'R19': (79.5, 94, 90), 'R20': (60, 98, 0),
    # CV bypass
    'J3': (50, 108, 0), 'R21': (58, 108, 90), 'R22': (62, 111, 0), 'D8': (73, 112, 180),
    'R23': (58, 116, 0),
    # Normals
    'U4': (102, 82, 0, 'mirror'), 'U4.2': (102, 108, 0, 'mirror'),
    # SVF input + summer / integrators (Bread Modular SVF), left to right
    'R24': (121, 41, 90), 'R25': (117, 45, 0),
    'U5': (128, 40, 0), 'R27': (128, 34, 90), 'R28': (128, 30, 90), 'R26': (128, 26, 90),
    'U8': (136, 45, 90, 'mirror'), 'U5.2': (146, 40, 0), 'C10': (146, 34, 90),
    'U7': (154, 45, 90, 'mirror'), 'U6': (164, 40, 0), 'C11': (164, 34, 90),
    'R29': (172, 40, 90),
    'RV5': (154, 29, 0), 'R32': (154, 23.5, 0), 'U6.2': (144, 22, 0, 'mirror'), 'R33': (144, 17, 90),
    'R30': (114, 48, 0), 'R31': (114, 54, 0),
    # SVF vactrol driver
    'RV6': (114, 108, 0), 'U9': (124, 107, 0), 'R34': (132, 107, 90), 'R35': (138, 107, 90),
    'R36': (142, 111, 0), 'U9.2': (152, 106, 0), 'RV7': (158, 116, 0), 'R37': (162, 120, 0),
    # SVF output resistors
    'R38': (172, 46, 90), 'R39': (172, 52, 90),
    # Outputs: LP / HP / BP stages, then the envelope CV output
    'C15': (180, 61, 90), 'R40': (186, 65, 0), 'U10': (194, 62, 0), 'R41': (193.5, 67, 90),
    'R42': (190, 71.5, 0), 'R43': (204, 62, 90), 'R44': (209, 66, 0), 'J4': (216, 62, 0, 'mirror'),
    'C16': (180, 79, 90), 'R45': (186, 83, 0), 'U10.2': (194, 80, 0), 'R46': (193.5, 85, 90),
    'R47': (190, 89.5, 0), 'R48': (204, 80, 90), 'R49': (209, 84, 0), 'J6': (216, 80, 0, 'mirror'),
    'C17': (180, 97, 90), 'R50': (186, 101, 0), 'U11': (194, 98, 0), 'R51': (193.5, 103, 90),
    'R52': (190, 107.5, 0), 'R53': (204, 98, 90), 'R54': (209, 102, 0), 'J7': (216, 98, 0, 'mirror'),
    'U11.2': (194, 118, 0), 'R55': (193.5, 123, 90), 'R56': (190, 127.5, 0), 'R57': (204, 118, 90),
    'J5': (216, 118, 0, 'mirror'),
    # Power entry
    'J10': (9, 137, 0), 'D1': (21, 134, 180), 'D2': (21, 142, 0), 'C1': (28, 136.5, 0), 'C2': (32, 136.5, 0),
    'U1': (40, 135, 0), 'C3': (47, 136.5, 0), 'C4': (51, 136.5, 0), 'C5': (55, 136.5, 0),
    '#FLG01': (6, 148, 0), '#FLG02': (12, 148, 0), '#FLG03': (18, 148, 0), '#FLG04': (24, 148, 0),
    '#FLG05': (30, 148, 0),
    # Op-amp / switch supply units and their decoupling
    'U3.3': (70, 135, 0), 'C7': (74, 135.5, 0), 'U4.3': (84, 135, 0), 'C9': (88, 135.5, 0),
    'U5.3': (98, 135, 0), 'C12': (102, 135.5, 0), 'U6.3': (112, 135, 0), 'C13': (116, 135.5, 0),
    'U9.3': (126, 135, 0), 'C14': (130, 135.5, 0), 'U10.3': (140, 135, 0), 'C18': (144, 135.5, 0),
    'C19': (149, 135.5, 0), 'U11.3': (156, 135, 0), 'C20': (160, 135.5, 0), 'C21': (165, 135.5, 0),
}

# Hand-drawn polylines for nets the router should not choose itself (same format as
# modules/low WIRES: 'REF/pin' pin ends and (x, y) grid points). Everything else is routed.
WIRES = {}

LABEL_AT = {}


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7533-1 -> +3V3
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5',
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header on B, pin 1 (-12 V) at the bottom (as modules/low); '
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
                  Note='3.3 V LDO, 30 V max input, 100 mA. Load ~30 mA (MCU, 4 x MCP6002, 4 LEDs at 4 mA): '
                       '~0.25 W at 11.6 V in'))
    c.append(part('C3', 'C', '1u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805',
                  {'1': '+3V3', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C5', 'C', '100u', 'C1206',
                  {'1': '+3V3', '2': 'GND'}, Voltage='6.3V', Note='+3V3 bulk (Bread Modular MCO/ENV C1 100uF 1206)'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V'}))

    # ---- MIDI input (TS modular MIDI): the 8bit / LOW NPN front end with its JP1 bypass
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
                       '(MIDI_IN to PB3, PORT_INVEN off; 3.3 V senders only). Never both'))

    # ---- MCU: one ATtiny1616 at 3.3 V runs the MCO and the ENV firmware
    c.append(part('U2', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', MCU,
                  Note='3.3 V, as Bread Modular MCO/ENV. Firmware: MCO (two tones, DETUNE) + ENV '
                       '(3 envelope models, record), envelope on the PA6 DAC'))
    c.append(part('C6', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U2 decoupling (Bread Modular MCO C2)'))
    c.append(part('R4', 'R', '4.7k', 'R0603',
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular R17)'))
    c.append(part('J11', 'Conn_01x02', 'UPDI', 'H1x2',
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power (3.3 V target)'))

    # ---- Envelope UI (Bread Modular ENV knobs, buttons and LEDs; no CV/gate inputs)
    c.append(part('R12', 'R', '1k', 'R0603',
                  {'1': 'DAC', '2': 'ENV_CV'},
                  Note='DAC series R (Bread Modular MCO R1 / ENV R2): the envelope, SVF CV normal and CV OUT source'))
    c.append(part('RV3', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'GND', '2': 'ENV_A', '3': '+3V3'},
                  Note='ENV knob 1 (Bread Modular ENV CV1, PA1): attack / hold time. CW = longer. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))
    c.append(part('RV4', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'GND', '2': 'ENV_R', '3': '+3V3'},
                  Note='ENV knob 2 (Bread Modular ENV CV2, PA2): release time. CW = longer. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))
    c.append(part('SW1', 'SW_Push', 'MODE', 'SW6',
                  {'1': 'MODE_SW', '2': 'GND'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Envelope model select (Bread Modular ENV algo button, PC0 internal pull-up): '
                       'generic 6 x 6 mm THT tact as modules/8bit, pressed through the panel by the printed cap'))
    c.append(part('SW2', 'SW_Push', 'REC', 'SW6',
                  {'1': 'REC_SW', '2': 'GND'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Record knob positions (8bit crash style; PC2 internal pull-up): generic 6 x 6 mm THT tact'))
    for ref, rref, net, role in (('D4', 'R13', 'LED_HR', 'Mode LED HR (hold-release), PC1'),
                                 ('D5', 'R14', 'LED_AR', 'Mode LED AR (attack-release), PA4'),
                                 ('D6', 'R15', 'LED_ASR', 'Mode LED ASR (attack-sustain-release), PA5'),
                                 ('D7', 'R16', 'LED_REC', 'Record LED, PC3')):
        c.append(part(rref, 'R', '330', 'R0603', {'1': net, '2': net + '_A'},
                      Note='LED current ~4 mA at 3.3 V (Bread Modular ENV R6/R9 330R)'))
        c.append(part(ref, 'LED', 'LED_3mm_red', 'LED3', {'2': net + '_A', '1': 'GND'},
                      Note=role + '. Hand-soldered 3 mm THT, dome flush with the panel (as modules/8bit)'))

    # ---- MCO mix: Bread Modular MCO, unchanged
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
                  Note='MCO output resistor (Bread Modular R8): the SVF audio normal'))
    c.append(part('R10', 'R', '1k', 'R0603', {'1': '+3V3', '2': 'VMID_MCO'},
                  Note='V_MID divider (Bread Modular MCO R3)'))
    c.append(part('R11', 'R', '1k', 'R0603', {'1': 'VMID_MCO', '2': 'GND'},
                  Note='V_MID divider (Bread Modular MCO R4)'))
    u3 = 'MCP6002, 3.3 V rail-to-rail. A: MCO summer (Bread Modular MCO U3A); B: AUDIO bypass input stage'
    c.append(part('U3', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'VMID_MCO', '2': 'MCO_SUM', '1': 'MCO_AMP'}, unit=1, Note=u3))
    c.append(part('U3', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'VMID_MCO', '6': 'AIN_SUM', '7': 'AIN_BUF'}, unit=2, Note=u3))
    c.append(part('U3', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=u3))
    c.append(part('C7', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U3 decoupling'))

    # ---- AUDIO bypass in (as modules/low): AC coupled, inverting x0.33 around V_MID, clips at the rails
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'AIN', 'S': 'GND', 'TN': 'AIN_SENSE'},
                  Note='AUDIO bypass in. Unpatched: the SVF filters the MCO (TN switch -> U4)'))
    c.append(part('R17', 'R', '100k', 'R0603', {'1': 'AIN', '2': 'GND'},
                  Note='Input bias (keeps C8 discharged) and the jack-detect low level: 0.3 V with R20'))
    c.append(part('C8', 'C', '1u', 'C0805', {'1': 'AIN', '2': 'AIN_AC'},
                  Voltage='50V', Note='AC coupling: 1.6 Hz with R18 (removes the Eurorack DC reference)'))
    c.append(part('R18', 'R', '100k', 'R0603', {'1': 'AIN_AC', '2': 'AIN_SUM'},
                  Note='Input resistor; virtual ground at V_MID, so +/-12 V in stays within the U3 rails'))
    c.append(part('R19', 'R', '33k', 'R0603', {'1': 'AIN_SUM', '2': 'AIN_BUF'},
                  Note='Feedback: gain -0.33 (10 Vpp -> 3.3 Vpp around V_MID; hotter clips = character)'))
    c.append(part('R20', 'R', '1M', 'R0603', {'1': '+3V3', '2': 'AIN_SENSE'},
                  Note='Jack-detect pull-up: plugged = TN open = high = external audio'))

    # ---- CV bypass in: 0..5 V -> 0..3.3 V (as modules/low S3, research.md 3.2), clamp
    c.append(part('J3', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'CVIN', 'S': 'GND', 'TN': 'CV_SENSE'},
                  Note='CV bypass in, 0..5 V (e.g. Bread Modular ENV via a 0..5 V Eurorack envelope). '
                       'Unpatched: the internal envelope (TN switch -> U4)'))
    c.append(part('R21', 'R', '47k', 'R0603', {'1': 'CVIN', '2': 'CVIN_DIV'},
                  Note='CV divider top; input impedance 147k. Limits the clamp current to 0.26 mA at -12 V'))
    c.append(part('R22', 'R', '100k', 'R0603', {'1': 'CVIN_DIV', '2': 'GND'},
                  Note='CV divider bottom: 100k || RV6 1M = 90.9k -> 5.0 V in = 3.30 V = the DAC envelope peak (as modules/low)'))
    c.append(part('D8', 'BAT54SW', 'BAT54SW', 'SOT323',
                  {'1': 'GND', '2': '+3V3', '3': 'CVIN_DIV'},
                  Note='CV clamp: holds U4 / U9 within -0.3..+3.6 V for a +/-12 V mis-patch'))
    c.append(part('R23', 'R', '1M', 'R0603', {'1': '+3V3', '2': 'CV_SENSE'},
                  Note='Jack-detect pull-up: unplugged 0.43 V (R21 + R22 to GND), plugged = high = external CV'))

    # ---- Normals: TS5A23157 dual SPDT (as modules/low). IN low (jack empty) -> COM = NC = internal.
    u4 = ('Dual 10R SPDT on +3V3: the AUDIO / CV normals. Pin map TI DGS: 1 IN1, 2 NO1, 3 GND, '
          '4 NO2, 5 IN2, 6 COM2, 7 NC2, 8 V+, 9 NC1, 10 COM1')
    c.append(part('U4', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'1': 'AIN_SENSE', '2': 'AIN_BUF', '9': 'MCO_OUT', '10': 'SVF_IN'}, unit=1, Note=u4))
    c.append(part('U4', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'4': 'CVIN_DIV', '5': 'CV_SENSE', '6': 'SVF_CV', '7': 'ENV_CV'}, unit=2, Note=u4))
    c.append(part('U4', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10', {'3': 'GND', '8': '+3V3'}, unit=3, Note=u4))
    c.append(part('C9', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U4 decoupling'))

    # ---- SVF: Bread Modular SVF 1.0.0. U5A summer (BM U4A), U5B integrator 1 (BM U4B, vactrol U8),
    # U6A integrator 2 (BM U3A, vactrol U7), U6B damping (BM U3B). LP, HP and BP outputs.
    c.append(part('R24', 'R', '51k', 'R0603', {'1': 'SVF_IN', '2': 'SVF_SUM'},
                  Note='SVF input (Bread Modular SVF R1): passband gain 10k/51k = 0.2'))
    c.append(part('R25', 'R', '22k', 'R0603', {'1': 'SVF_IN', '2': 'GND'},
                  Note='Input load (Bread Modular SVF R2)'))
    usvf1 = 'MCP6002, 3.3 V. A: SVF summer (Bread Modular SVF U4A); B: integrator 1 HP -> BP (U4B)'
    c.append(part('U5', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'VMID_SVF', '2': 'SVF_SUM', '1': 'SVF_HP'}, unit=1, Note=usvf1))
    c.append(part('U5', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'VMID_SVF', '6': 'SVF_I1', '7': 'SVF_BP'}, unit=2, Note=usvf1))
    c.append(part('U5', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=usvf1))
    c.append(part('R26', 'R', '10k', 'R0603', {'1': 'SVF_LP', '2': 'SVF_SUM'},
                  Note='LP feedback to the summer (Bread Modular SVF R6)'))
    c.append(part('R27', 'R', '10k', 'R0603', {'1': 'SVF_SUM', '2': 'SVF_HP'},
                  Note='Summer feedback (Bread Modular SVF R7)'))
    c.append(part('R28', 'R', '10k', 'R0603', {'1': 'SVF_DMP', '2': 'SVF_SUM'},
                  Note='Damping feedback (Bread Modular SVF R8)'))
    c.append(part('U8', 'VTL5C', 'VTL5C', 'VTL5C',
                  {'1': 'VAC_NEG', '2': 'VAC_POS', '3': 'SVF_I1', '4': 'SVF_HP'},
                  Note='Vactrol, integrator 1 R (Bread Modular SVF U2, Chinese VTL5C type). Hand-soldered THT on B'))
    c.append(part('C10', 'C', '10n', 'C0603', {'1': 'SVF_I1', '2': 'SVF_BP'},
                  Voltage='50V', Note='Integrator 1 C (Bread Modular SVF C2)'))
    c.append(part('U7', 'VTL5C', 'VTL5C', 'VTL5C',
                  {'1': 'VAC_NEG', '2': 'VAC_POS', '3': 'SVF_I2', '4': 'SVF_BP'},
                  Note='Vactrol, integrator 2 R (Bread Modular SVF U1, Chinese VTL5C type). Hand-soldered THT on B'))
    usvf2 = 'MCP6002, 3.3 V. A: integrator 2 BP -> LP (Bread Modular SVF U3A); B: resonance damping amp (U3B)'
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'VMID_SVF', '2': 'SVF_I2', '1': 'SVF_LP'}, unit=1, Note=usvf2))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'VMID_SVF', '6': 'SVF_DN', '7': 'SVF_DMP'}, unit=2, Note=usvf2))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=usvf2))
    c.append(part('C11', 'C', '10n', 'C0603', {'1': 'SVF_I2', '2': 'SVF_LP'},
                  Voltage='50V', Note='Integrator 2 C (Bread Modular SVF C1)'))
    c.append(part('R29', 'R', '1k', 'R0603', {'1': 'SVF_LP', '2': 'SVF_LPO'},
                  Note='LP output resistor (Bread Modular SVF R5, LF out)'))
    c.append(part('RV5', 'R_Potentiometer', '500k', 'RV09',
                  {'1': 'SVF_RQ', '2': 'SVF_BP', '3': None},
                  Note='RESONANCE (Bread Modular SVF RV1 500k): rheostat, pin 3 open; Q = 1..11. RV09 9 mm '
                       'vertical, linear (user stock). Hand-soldered'))
    c.append(part('R32', 'R', '51k', 'R0603', {'1': 'SVF_DN', '2': 'SVF_RQ'},
                  Note='Damping input (Bread Modular SVF R11)'))
    c.append(part('R33', 'R', '51k', 'R0603', {'1': 'SVF_DMP', '2': 'SVF_DN'},
                  Note='Damping feedback (Bread Modular SVF R12): gain 51k / (51k + RES)'))
    c.append(part('R30', 'R', '1k', 'R0603', {'1': '+3V3', '2': 'VMID_SVF'},
                  Note='V_MID divider (Bread Modular SVF R9)'))
    c.append(part('R31', 'R', '1k', 'R0603', {'1': 'VMID_SVF', '2': 'GND'},
                  Note='V_MID divider (Bread Modular SVF R10)'))
    c.append(part('C12', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V',
                  Note='U5 decoupling (Bread Modular SVF C3)'))
    c.append(part('C13', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V',
                  Note='U6 decoupling (Bread Modular SVF C4)'))

    # ---- SVF vactrol driver (Bread Modular SVF U5): FREQ attenuates the CV, U9A buffers it,
    # R34-R36 halve it, U9B forces the LED cathodes to CV/2: I_LED = (CV/2) / (CURVE + 5.1k).
    # BM R13 (100k CV pull-up to V_SUPPLY) is left out: U4 always drives SVF_CV.
    c.append(part('RV6', 'R_Potentiometer', '1M', 'RV09',
                  {'1': 'GND', '2': 'FREQ_W', '3': 'SVF_CV'},
                  Note='FREQ (Bread Modular SVF RV2 1M): CV attenuator. RV09 9 mm vertical, linear (user stock). '
                       'Hand-soldered'))
    udrv = 'MCP6002, 3.3 V. A: CV follower; B: vactrol LED driver (Bread Modular SVF U5)'
    c.append(part('U9', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'FREQ_W', '2': 'CV_BUF', '1': 'CV_BUF'}, unit=1, Note=udrv))
    c.append(part('U9', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'CV_HALF', '6': 'VAC_NEG', '7': 'VAC_POS'}, unit=2, Note=udrv))
    c.append(part('U9', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=udrv))
    c.append(part('R34', 'R', '1k', 'R0603', {'1': 'CV_BUF', '2': 'CV_R'},
                  Note='Bread Modular SVF R14'))
    c.append(part('R35', 'R', '1M', 'R0603', {'1': 'CV_HALF', '2': 'CV_R'},
                  Note='CV / 2 (Bread Modular SVF R15)'))
    c.append(part('R36', 'R', '1M', 'R0603', {'1': 'GND', '2': 'CV_HALF'},
                  Note='CV / 2 (Bread Modular SVF R16)'))
    c.append(part('RV7', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'VAC_NEG', '2': 'CURVE_R', '3': None},
                  Note='CURVE (Bread Modular SVF RV3 50k, FREQ CURVE): LED current rheostat, pin 3 open. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))
    c.append(part('R37', 'R', '5.1k', 'R0603', {'1': 'GND', '2': 'CURVE_R'},
                  Note='LED current limit (Bread Modular SVF R17): <= 0.32 mA at CV 3.3 V'))
    c.append(part('C14', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V',
                  Note='U9 decoupling (Bread Modular SVF C5)'))

    # ---- Outputs (research.md 3.4): no DRIVE. Each SVF output (LP, HP, BP) leaves through its
    # Bread Modular 1k, is AC coupled and gets one TL072 stage: x22.3 (1 + 100k / 4.7k), clipping
    # at the TL072 rails (the DRIVE's rail clipping, now on +/-12 V), then the 1k series + 1k shunt
    # halve it: x11.1 small signal (DRIVE at 75 % x OUT x3 = x11.7) and a ~10 Vpp ceiling.
    stages = (('LP', 'SVF_LPO', 'U10', ('3', '2', '1'), 'J4', 'C15', 'R40', 'R41', 'R42', 'R43', 'R44'),
              ('HP', 'SVF_HPO', 'U10', ('5', '6', '7'), 'J6', 'C16', 'R45', 'R46', 'R47', 'R48', 'R49'),
              ('BP', 'SVF_BPO', 'U11', ('3', '2', '1'), 'J7', 'C17', 'R50', 'R51', 'R52', 'R53', 'R54'))
    c.append(part('R38', 'R', '1k', 'R0603', {'1': 'SVF_HP', '2': 'SVF_HPO'},
                  Note='HP output resistor (Bread Modular SVF R3, HF out)'))
    c.append(part('R39', 'R', '1k', 'R0603', {'1': 'SVF_BP', '2': 'SVF_BPO'},
                  Note='BP output resistor (Bread Modular SVF R4, BF out)'))
    uout = {'U10': '+/-12 V. A: LP output x22.3; B: HP output x22.3',
            'U11': '+/-12 V. A: BP output x22.3; B: envelope CV output x1.51'}
    for name, src, u, (pin, pinv, pout), jack, cc, rb, rf, rg, rs, rsh in stages:
        unit = 1 if pin == '3' else 2
        c.append(part(cc, 'C', '1u', 'C0805', {'1': src, '2': name + '_IN'},
                      Voltage='25V', Note=f'{name} AC coupling (removes V_MID 1.65 V)'))
        c.append(part(rb, 'R', '100k', 'R0603', {'1': name + '_IN', '2': 'GND'},
                      Note='Bias to 0 V: 1u x 100k = 1.6 Hz high-pass'))
        c.append(part(u, 'TL072', 'TL072', 'SOIC8',
                      {pin: name + '_IN', pinv: name + '_FB', pout: name + '_AMP'}, unit=unit, Note=uout[u]))
        c.append(part(rf, 'R', '100k', 'R0603', {'1': name + '_FB', '2': name + '_AMP'},
                      Note='Rf: gain 1 + 100k / 4.7k = 22.3; hot signals clip at the TL072 rails (~+/-10 V)'))
        c.append(part(rg, 'R', '4.7k', 'R0603', {'1': name + '_FB', '2': 'GND'}, Note='Rg to GND'))
        c.append(part(rs, 'R', '1k', 'R1206', {'1': name + '_AMP', '2': name + '_OUT'},
                      Power='0.5W', Note='Output series: with the 1k shunt halves the stage (x11.1, ~10 Vpp '
                                         'ceiling); short / +/-12 V mis-patch current limit (as modules/low R30)'))
        c.append(part(rsh, 'R', '1k', 'R1206', {'1': name + '_OUT', '2': 'GND'},
                      Power='0.5W', Note='Output shunt: 500R output impedance; 1206 for a +12 V mis-patch'))
        c.append(part(jack, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                      {'T': name + '_OUT', 'S': 'GND', 'TN': None},
                      Note=f'SVF {name} out, Eurorack level (~10 Vpp ceiling)'))

    # ---- Envelope CV output: DAC envelope 0..3.3 V -> 0..5.0 V, DC coupled, protected
    c.append(part('U11', 'TL072', 'TL072', 'SOIC8',
                  {'5': 'ENV_CV', '6': 'CVO_FB', '7': 'CVO_AMP'}, unit=2, Note=uout['U11']))
    c.append(part('R55', 'R', '51k', 'R0603', {'1': 'CVO_FB', '2': 'CVO_AMP'},
                  Note='Rf: gain 1 + 51k / 100k = 1.51: 3.30 V -> 4.98 V'))
    c.append(part('R56', 'R', '100k', 'R0603', {'1': 'CVO_FB', '2': 'GND'}, Note='Rg to GND'))
    c.append(part('R57', 'R', '1k', 'R1206', {'1': 'CVO_AMP', '2': 'CV_OUT'},
                  Power='0.5W', Note='Output series: short / +/-12 V mis-patch protection (TL072 output '
                                     'current-limited, 12 mA max through 1k)'))
    c.append(part('J5', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'CV_OUT', 'S': 'GND', 'TN': None}, Note='Envelope CV out, 0..5 V'))
    for u, (cp, cn) in (('U10', ('C18', 'C19')), ('U11', ('C20', 'C21'))):
        c.append(part(u, 'TL072', 'TL072', 'SOIC8', {'4': '-12V_F', '8': '+12V_F'}, unit=3, Note=uout[u]))
        c.append(part(cp, 'C', '100n', 'C0603',
                      {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note=f'{u} V+ decoupling'))
        c.append(part(cn, 'C', '100n', 'C0603',
                      {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note=f'{u} V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts, every code re-checked live for ACID 2026-10-22 (assembly lookup --strict-live:
# MPN, value, package, rating). All Basic except the 0.5 W 1206 1k (no Basic 0.5 W 1206 exists;
# C4410 from modules/low is 250 mW), BAT54SW, ATtiny1616, MCP6002 and TS5A23157. Stock is a dated
# observation, not a guarantee. THT parts carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM'),
    ('R', '330', 'R0603'): dict(LCSC='C23138', MPN='0603WAF3300T5E', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0603'): dict(LCSC='C23186', MPN='0603WAF5101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '12k', 'R0603'): dict(LCSC='C22790', MPN='0603WAF1202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0603'): dict(LCSC='C4184', MPN='0603WAF2002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '33k', 'R0603'): dict(LCSC='C4216', MPN='0603WAF3302T5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '200k', 'R0603'): dict(LCSC='C25811', MPN='0603WAF2003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1M', 'R0603'): dict(LCSC='C22935', MPN='0603WAF1004T5E', Manufacturer='UNI-ROYAL'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '100u', 'C1206'): dict(LCSC='C15008', MPN='CL31A107MQHNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7533-1', 'SOT89'): dict(LCSC='C14289', MPN='HT7533-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR', Manufacturer='Microchip'),
    ('MCP6002-xSN', 'MCP6002', 'SOIC8'): dict(LCSC='C7377', MPN='MCP6002T-I/SN', Manufacturer='Microchip'),
    ('TL072', 'TL072', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
    ('TS5A23157DGS', 'TS5A23157', 'TSSOP10'): dict(LCSC='C11133', MPN='TS5A23157DGSR', Manufacturer='Texas Instruments'),
}


def T(x, y):
    return (round((x + OFFSET[0]) * GRID, 2), round((y + OFFSET[1]) * GRID, 2))


# Block notes: (grid position, text, size). route_wires() keeps wires out of their boxes.
TEXTS = [
    (T(4, 4), 'BIG MODULAR ACID - S2 schematic: Bread Modular MCO + ENV (one ATtiny1616) -> SVF (LP / HP / BP outs) on one 8HP '
              'module, 3.3 V internal signals as Bread Modular. Circuit intent: docs/research.md', 2.0),
    (T(4, 6.5), 'Signal nets are wired; supplies use power symbols. ENV_CV (R12 -> U4B NC2, U11B +) is joined by '
                'its net labels.', 1.27),
    (T(4, 10), 'MIDI IN (TS): 8bit / LOW NPN front end, pull-ups on +3V3. '
               'JP1 shipped OPEN: 1-2 = protected (PORT_INVEN on PB3), 2-3 = direct.', 1.27),
    (T(4, 76), 'ENVELOPE UI (Bread Modular ENV): MODE (PC0) + LEDs HR/AR/ASR (PC1, PA4, PA5);\n'
               'REC (PC2) + LED (PC3) records the knob positions (8bit crash style). Internal pull-ups.', 1.27),
    (T(48, 26), 'ENV knobs ATTACK (PA1) / RELEASE (PA2). DAC PA6 -> R12 -> ENV_CV (0..3.3 V).', 1.27),
    (T(52, 78), 'MCO MIX (Bread Modular MCO): U3A inverting summer around VMID_MCO.', 1.27),
    (T(44, 84), 'AUDIO BYPASS: AC coupled, x -0.33 around V_MID (10 Vpp -> 0..3.3 V, hotter clips).', 1.27),
    (T(44, 103), 'CV BYPASS: 0..5 V -> 0..3.3 V (R21/R22 with RV6), BAT54SW clamp.', 1.27),
    (T(92, 124), 'NORMALS (U4 TS5A23157): jack empty -> TN = T pulls IN low -> COM = NC (MCO_OUT / ENV_CV);\n'
                 'patched -> TN open, 1M pulls IN high -> COM = NO (AIN_BUF / CVIN_DIV).', 1.27),
    (T(110, 10), 'SVF (Bread Modular SVF 1.0.0): U5A summer, U5B + U8 and U6A + U7 vactrol integrators, U6B damping '
                 '(RESONANCE 500k, R32/R33 51k: Q 1..11). LP / HP / BP outs via R29 / R38 / R39.', 1.27),
    (T(110, 96), 'SVF VACTROL DRIVER: FREQ attenuates the CV, U9A follower, R35/R36 halve it,\n'
                 'U9B holds the LED cathodes at CV/2: I = (CV/2) / (CURVE + 5.1k). BM R13 pull-up omitted.', 1.27),
    (T(176, 50), 'OUTPUTS LP (J4) / HP (J6) / BP (J7), no DRIVE: AC coupled (1.6 Hz), TL072 x22.3 clips at\n'
                 'its rails, 1k series + 1k shunt: x11.1, ~10 Vpp ceiling, 500R out.', 1.27),
    (T(176, 112), 'CV OUT: U11B x1.51: envelope 0..3.3 V -> 0..5.0 V, DC coupled, 1k to J5.', 1.27),
    (T(4, 128), 'POWER: +12V -> D1 -> +12V_F (U10, U11, U1 HT7533-1 -> +3V3); -12V -> D2 -> -12V_F (U10, U11).', 1.27),
    (T(68, 128), 'SUPPLY PINS + DECOUPLING', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/acid/schematic/' + key))


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
    if sym == 'LED':
        return ((0, -3.175), (0, 3.175), None) if rot in (0, 180) else right
    if sym == 'SW_Push':
        return ((0, -3.81), (0, 3.81), None) if rot in (0, 180) else left
    if sym == 'R_Potentiometer':
        if rot in (90, 270):
            return (0, -4.45), (0, -2.54), None
        return ((2.54, 2.29), (2.54, 4.19), 'left') if not p['mirror'] else ((-2.54, 2.29), (-2.54, 4.19), 'right')
    if sym == 'BAT54SW':
        return (0, 2.54), (0, 4.45), None
    if sym in ('MCP6002-xSN', 'TL072'):
        return ((-3.81, -0.635), (-3.81, 1.27), 'right') if unit == 3 else ((0, -7.62), (0, -5.715), None)
    if sym == 'TS5A23157DGS':
        return ((-6.35, -0.635), (-6.35, 1.27), 'right') if unit == 3 else ((0, -10.16), (0, -8.255), None)
    if sym == 'ATtiny1616-M':
        return (10.16, -25.4), (10.16, 25.4), None
    if sym == 'VTL5C':
        return ((0, -6.35), (0, 6.35), None) if rot in (0, 180) else ((-3.81, -0.635), (-3.81, 1.27), 'right')
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
        '(options "") (descr "ACID pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A2")
      (title_block (title "Big Modular - ACID") (rev "S2") (company "Big Modular")
        (comment 1 "SCHEMATIC S2 - Bread Modular MCO + ENV + SVF (LP/HP/BP outs), 3.3 V signals, wired nets")
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
    assert multi == {k: {1, 2, 3} for k in ('U3', 'U4', 'U5', 'U6', 'U9', 'U10', 'U11')}, multi
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
