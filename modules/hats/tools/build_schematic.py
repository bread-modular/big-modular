"""Generate the HATS S3 schematic (hardware/hats.kicad_sch) and its pinned symbols.

Run from modules/hats:
  python3 -B tools/build_schematic.py

Writes hardware/HATS.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the HATS library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
of docs/research.md section 3: Bread Modular NOISE (blue noise only, its own ATtiny1616)
-> Bread Modular HIHAT (its own ATtiny1616) on one 6HP Eurorack module, all on Bread
Modular's 3.3 V signal level, with the 8bit MIDI input feeding both MCUs, a level-mapped
NOISE input normalled (TS5A23157, as modules/low) to the internal blue noise, a +/-12 V
audio output and a protected 0..5 V hi-hat CV output with a panel LED.

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
PROJECT = 'hats'
LIB = 'HATS'
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
    'SS8050': ('Transistor_BJT', 'SS8050'),
    'Q_PNP_BEC': ('Transistor_BJT', 'Q_PNP_BEC'),
    '1N4148W': ('Diode', '1N4148W'),
    'GND': ('power', 'GND'), '+3V3': ('power', '+3V3'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
    'D_Dual_Series_AKC': ('Device', 'D_Dual_Series_AKC'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric', 'C1206': 'C_1206_3216Metric',
    'SOD123': 'D_SOD-123', 'SOT23': 'SOT-23', 'SOT89': 'SOT-89-3',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'TSSOP10': 'TSSOP-10_3x3mm_P0.5mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09', 'VTL5C': 'VTL5C',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
    'LED3': 'LED_D3.0mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# Supply nets are drawn with power symbols (net name = symbol value).
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Signal nets joined by name labels (a stub + label on every pin) instead of wires: the hi-hat
# V_MID reference reaches the NOISE IN stage, the comparator, the filter and the VCA (a local rail).
LABEL_NETS = {'VMID_H'}

# ATtiny1616-M (VQFN-20) pin numbers. Two MCUs, each running its Bread Modular firmware
# unchanged. U2 = Bread Modular NOISE 1.0.1 (PB3 MIDI RX, PA6 DAC = white noise, PA7 TONE knob).
# U3 = Bread Modular HIHAT 1.0.0 (PB3 MIDI RX, PA5 gate, PA7 open-hat select, PA6 DAC = velocity).
# PA0 = UPDI on both. PB2 (BM TX / MIDI THRU) is not used: both MCUs listen to one RX net.
# S3: no recording controls. PC2/PC3 are explicitly no-connects.
MCU_NOISE = {'11': 'RX', '7': 'N_DAC', '8': 'NOISE_TONE', '19': 'N_UPDI_PA0', '17': None,
             '4': '+3V3', '3': 'GND', '21': 'GND',
             '1': None, '2': None, '5': None, '6': None, '9': None, '10': None, '12': None, '13': None,
             '14': None, '15': None, '16': None, '18': None, '20': None}
MCU_HIHAT = {'11': 'RX', '6': 'MIDI_GATE', '7': 'H_DAC', '8': 'MIDI_OPEN', '19': 'H_UPDI_PA0',
             '17': None, '18': None,
             '4': '+3V3', '3': 'GND', '21': 'GND',
             '1': None, '2': None, '5': None, '9': None, '10': None, '12': None, '13': None,
             '14': None, '15': None, '16': None, '20': None}

GRID = 2.54
OFFSET = (4, 4)  # LAYOUT / TEXTS origin inside the A2 frame, grid units
DEBUG_PLACEMENT = bool(__import__('os').environ.get('HATS_PLACEMENT_ONLY'))


def part(ref, sym, value, fp, pins, unit=1, **fields):
    key = ref if unit == 1 else f'{ref}.{unit}'
    x, y, rot, *mirror = LAYOUT[key]
    x, y = x + OFFSET[0], y + OFFSET[1]
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(round(x * GRID, 2), round(y * GRID, 2)), rot=rot,
                mirror=bool(mirror), pins=pins, unit=unit, fields=fields)


# Symbol placement in 2.54 mm grid units: ref (unit 1) or ref.unit -> (x, y, rotation[, 'mirror']).
# Top band: MIDI -> noise MCU U2 -> white / blue noise -> NOISE IN bypass -> U5 normal ->
# hi-hat filter -> vactrol VCA. Middle band: hi-hat MCU U3 -> trigger / accent / envelope ->
# vactrol LED drive. Right: AUDIO and CV outputs. Bottom: power and supply pins.
LAYOUT = {
    # MIDI input (as modules/low / modules/acid)
    'J1': (6, 22, 0), 'R1': (12, 20.5, 180), 'R2': (16.5, 22, 90), 'D3': (20, 24.5, 270),
    'Q1': (23, 22, 0), 'R3': (24, 16.5, 180), 'JP1': (33, 18, 0),
    # Noise MCU + UPDI
    'U2': (44, 42, 0), 'C6': (34, 30, 0), 'R4': (56, 35, 90), 'J11': (62, 35, 0),
    # Noise: white buffer, blue high-pass, blue buffer, V_MID
    'RV1': (60, 44, 0, 'mirror'), 'R6': (60, 40, 90),
    'U4': (70, 39, 0), 'C8': (77, 39, 90), 'RV2': (81, 45, 0), 'R7': (86, 47, 90),
    'U4.2': (90, 40, 0), 'R8': (97, 40, 90), 'R9': (92, 51, 0), 'R10': (92, 56, 0),
    # NOISE IN bypass (U9B), as modules/low AUDIO
    'J2': (100, 20, 0), 'R11': (107, 25, 0), 'C10': (110, 20, 90), 'R12': (115, 20, 90),
    'U9.2': (124, 21, 0), 'R13': (123, 15, 90), 'R14': (106, 12, 0),
    'R49': (104, 25, 90), 'D7': (117, 32, 270),
    # Normal: U5 TS5A23157 (channel 2 unused)
    'U5': (136, 40, 0, 'mirror'), 'U5.2': (136, 56, 0, 'mirror'),
    # Hi-hat filter (Bread Modular HIHAT U2A)
    'C12': (146, 40, 90), 'R15': (151, 40, 90), 'U6': (162, 40, 0, 'mirror'), 'R16': (162, 34, 90),
    'C13': (158, 48, 90), 'C14': (166, 48, 90), 'R17': (162, 52, 0), 'RV3': (162, 58, 0),
    # Vactrol VCA (U7 LDR, U6B), HIHAT_OUT
    'U7': (178, 44, 0), 'R18': (184, 50, 0), 'R19': (188, 50, 0), 'R23': (170, 52, 0),
    'U6.2': (196, 44, 0), 'R20': (196, 38, 90), 'R21': (192, 52, 0), 'R22': (203, 44, 90),
    # Hi-hat V_MID
    'R24': (150, 60, 0), 'R25': (150, 65, 0), 'C15': (154, 63, 0),
    # Hi-hat MCU + UPDI
    'U3': (44, 90, 0), 'C7': (34, 78, 0), 'R5': (56, 83, 90), 'J12': (62, 83, 0),
    # Trigger: MIDI gate -> 10n differentiator -> U8A comparator -> Q2 switch
    'R26': (60, 88, 90), 'C17': (66, 88, 90), 'R27': (70, 92, 0), 'U8': (78, 89, 0), 'R28': (85, 89, 90),
    'Q2': (92, 89, 0),
    # Accent: DAC -> R29 -> divider -> U8B follower -> Q2 collector
    'R29': (60, 76, 90), 'R30': (66, 76, 90), 'R31': (70, 80, 0), 'R33': (76, 76, 90), 'R32': (80, 71, 0),
    'U8.2': (88, 77, 0),
    # Envelope: D4 -> C18 (decay R34, R35 + DECAY via Q3 when closed) -> Q4 follower -> U9A x2
    'D4': (98, 93, 180), 'C18': (104, 97, 0), 'R34': (108, 97, 0), 'R35': (113, 93, 90), 'RV4': (120, 95, 0),
    'Q3': (126, 100, 0), 'R36': (118, 104, 90),
    'Q4': (110, 106, 0), 'R37': (113, 113, 0), 'U9': (124, 111, 0, 'mirror'), 'R38': (124, 117, 90),
    'R39': (129, 120, 0),
    # Outputs: AUDIO (U10A x3, AC coupled) and HAT CV (U10B x1.51) + LED
    'C21': (190, 66, 90), 'R40': (195, 70, 0), 'U10': (202, 67, 0), 'R41': (201.5, 72, 90),
    'R42': (198, 76.5, 0), 'R43': (210, 67, 90), 'J3': (222, 67, 0, 'mirror'),
    'U10.2': (202, 92, 0), 'R44': (201.5, 97, 90), 'R45': (198, 101.5, 0), 'R46': (210, 92, 90),
    'J4': (222, 92, 0, 'mirror'), 'R47': (214, 100, 0), 'D5': (214, 106, 90),
    # Power entry
    'J10': (9, 137, 0), 'D1': (21, 134, 180), 'D2': (21, 142, 0), 'C1': (28, 136.5, 0), 'C2': (32, 136.5, 0),
    'U1': (40, 135, 0), 'C3': (47, 136.5, 0), 'C4': (51, 136.5, 0), 'C5': (55, 136.5, 0),
    '#FLG01': (6, 148, 0), '#FLG02': (12, 148, 0), '#FLG03': (18, 148, 0), '#FLG04': (24, 148, 0),
    '#FLG05': (30, 148, 0),
    # Op-amp / switch supply units and their decoupling
    'U4.3': (70, 135, 0), 'C9': (74, 135.5, 0), 'U5.3': (84, 135, 0), 'C11': (88, 135.5, 0),
    'U6.3': (98, 135, 0), 'C16': (102, 135.5, 0), 'U8.3': (112, 135, 0), 'C19': (116, 135.5, 0),
    'U9.3': (126, 135, 0), 'C20': (130, 135.5, 0), 'U10.3': (140, 135, 0), 'C22': (144, 135.5, 0),
    'C23': (149, 135.5, 0),
}

# Hand-drawn polylines for nets the router should not choose itself (same format as
# modules/low WIRES: 'REF/pin' pin ends and (x, y) grid points). Everything else is routed.
WIRES = {}

LABEL_AT = {}


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7533-1 -> +3V3 (as modules/low)
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
                  Note='3.3 V LDO, 30 V max input, 100 mA. Load ~35 mA (2 MCUs, 4 x MCP6002, vactrol LED, '
                       '2 V_MID dividers): ~0.3 W at 11.6 V in'))
    c.append(part('C3', 'C', '1u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805',
                  {'1': '+3V3', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C5', 'C', '100u', 'C1206',
                  {'1': '+3V3', '2': 'GND'}, Voltage='6.3V',
                  Note='+3V3 bulk (Bread Modular NOISE C1 / HIHAT C9 100uF 1206)'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V'}))

    # ---- MIDI input (TS modular MIDI): the 8bit / LOW NPN front end with its JP1 bypass; RX feeds both MCUs
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
                  Note='Inverting input buffer: input high = RX low. Firmware: PORT_INVEN on PB3 (both MCUs)'))
    c.append(part('R3', 'R', '22k', 'R0603',
                  {'1': 'RX_Q', '2': '+3V3'},
                  Note='Q1 collector pull-up, on RX_Q so the JP1 direct path leaves PB3 unloaded'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3',
                  {'1': 'RX_Q', '2': 'RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. Solder 1-2 = protected '
                       '(Q1 drives PB3 of U2 and U3, PORT_INVEN on in both firmwares). Solder 2-3 = '
                       'direct/unprotected (stock Bread Modular firmware; 3.3 V senders only). Never both'))

    # ---- Noise MCU: Bread Modular NOISE 1.0.1 firmware unchanged
    c.append(part('U2', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', MCU_NOISE,
                  Note='NOISE MCU, 3.3 V, Bread Modular NOISE firmware: LFSR white noise on the PA6 DAC, '
                       'TONE knob on PA7 (+ MIDI CC74)'))
    c.append(part('C6', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U2 decoupling (Bread Modular NOISE C3)'))
    c.append(part('R4', 'R', '4.7k', 'R0603',
                  {'1': 'N_UPDI_PA0', '2': 'N_UPDI'}, Note='UPDI series resistor (Bread Modular NOISE R1)'))
    c.append(part('J11', 'Conn_01x02', 'UPDI_NOISE', 'H1x2',
                  {'1': 'N_UPDI', '2': 'GND'},
                  Note='NOISE MCU (U2) UPDI: pin 1 UPDI, pin 2 GND. Program on Eurorack power (3.3 V target)'))

    # ---- Noise: Bread Modular NOISE white buffer + blue high-pass (pink section not built)
    c.append(part('R6', 'R', '1k', 'R0603', {'1': 'N_DAC', '2': 'WHITE'},
                  Note='DAC series R (Bread Modular NOISE R2)'))
    c.append(part('RV1', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'GND', '2': 'NOISE_TONE', '3': '+3V3'},
                  Note='NOISE TONE (Bread Modular NOISE RV1, PA7): noise sample rate. RV09 9 mm vertical, '
                       'linear (user stock). Hand-soldered'))
    un = 'MCP6002, 3.3 V. A: white noise follower (Bread Modular NOISE U2A); B: blue noise follower (U2B)'
    c.append(part('U4', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'WHITE', '2': 'WHITE_BUF', '1': 'WHITE_BUF'}, unit=1, Note=un))
    c.append(part('U4', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'BLUE_HP', '6': 'BLUE_BUF', '7': 'BLUE_BUF'}, unit=2, Note=un))
    c.append(part('U4', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=un))
    c.append(part('C8', 'C', '100p', 'C0603', {'1': 'WHITE_BUF', '2': 'BLUE_HP'},
                  Voltage='50V', Note='Blue high-pass C (Bread Modular NOISE C2): 1.6 kHz at BLUE TONE max'))
    c.append(part('RV2', 'R_Potentiometer', '1M', 'RV09',
                  {'1': 'BLUE_HP', '2': 'BLUE_W', '3': None},
                  Note='BLUE TONE (Bread Modular NOISE RV2 1M): high-pass rheostat, pin 3 open. RV09 9 mm '
                       'vertical, linear (user stock). Hand-soldered'))
    c.append(part('R7', 'R', '330', 'R0603', {'1': 'BLUE_W', '2': 'VMID_N'},
                  Note='High-pass minimum R (Bread Modular NOISE R6)'))
    c.append(part('R8', 'R', '1k', 'R0603', {'1': 'BLUE_BUF', '2': 'BLUE_NOISE'},
                  Note='Blue noise output resistor (Bread Modular NOISE R5): the NOISE IN normal'))
    c.append(part('R9', 'R', '1k', 'R0603', {'1': '+3V3', '2': 'VMID_N'},
                  Note='Noise V_MID divider (Bread Modular NOISE R3)'))
    c.append(part('R10', 'R', '1k', 'R0603', {'1': 'VMID_N', '2': 'GND'},
                  Note='Noise V_MID divider (Bread Modular NOISE R4)'))
    c.append(part('C9', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V',
                  Note='U4 decoupling (Bread Modular NOISE C4)'))

    # ---- NOISE IN bypass (as modules/low AUDIO): AC coupled, inverting x0.33 around V_MID, clips at the rails
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'NIN', 'S': 'GND', 'TN': 'NIN_SENSE_RAW'},
                  Note='NOISE in. Unpatched: the hi-hat gets the internal blue noise (TN switch -> U5)'))
    c.append(part('R11', 'R', '100k', 'R0603', {'1': 'NIN', '2': 'GND'},
                  Note='Input bias (keeps C10 discharged) and the jack-detect low level: about 0.68 V with R14/R49'))
    c.append(part('C10', 'C', '1u', 'C0805', {'1': 'NIN', '2': 'NIN_AC'},
                  Voltage='50V', Note='AC coupling: 1.6 Hz with R12 (removes the Eurorack DC reference)'))
    c.append(part('R12', 'R', '100k', 'R0603', {'1': 'NIN_AC', '2': 'NIN_SUM'},
                  Note='Input resistor; virtual ground at V_MID, so +/-12 V in stays within the U9 rails'))
    c.append(part('R13', 'R', '33k', 'R0603', {'1': 'NIN_SUM', '2': 'NIN_BUF'},
                  Note='Feedback: gain -0.33 (10 Vpp -> 3.3 Vpp around V_MID; hotter clips)'))
    c.append(part('R14', 'R', '470k', 'R0603', {'1': '+3V3', '2': 'NIN_SENSE'},
                  Note='Jack-detect pull-up: 470k with 100k R11 + 22k R49. Plugged high; empty about 0.68 V'))
    c.append(part('R49', 'R', '22k', 'R0603', {'1': 'NIN_SENSE_RAW', '2': 'NIN_SENSE'},
                  Power='0.1W', Note='Sense-only series protection: limits +/-12 V jack-contact fault current to <0.6 mA'))
    c.append(part('D7', 'D_Dual_Series_AKC', 'BAV199', 'SOT23',
                  {'1': 'GND', '2': '+3V3', '3': 'NIN_SENSE'},
                  Note='Low-leakage dual rail clamp: 1 anode GND, 2 cathode +3V3, 3 common sense. Negative faults also current-limited into U5 internal clamp; see docs/noise-in-protection.md'))

    # ---- Normal: TS5A23157 (as modules/low). IN1 low (jack empty) -> COM1 = NC1 = internal blue noise.
    u5 = ('Dual 10R SPDT on +3V3: the NOISE IN normal (channel 2 unused, IN2 tied low). Pin map TI DGS: '
          '1 IN1, 2 NO1, 3 GND, 4 NO2, 5 IN2, 6 COM2, 7 NC2, 8 V+, 9 NC1, 10 COM1')
    c.append(part('U5', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'1': 'NIN_SENSE', '2': 'NIN_BUF', '9': 'BLUE_NOISE', '10': 'HH_IN'}, unit=1, Note=u5))
    c.append(part('U5', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10',
                  {'4': None, '5': 'GND', '6': None, '7': None}, unit=2, Note=u5))
    c.append(part('U5', 'TS5A23157DGS', 'TS5A23157', 'TSSOP10', {'3': 'GND', '8': '+3V3'}, unit=3, Note=u5))
    c.append(part('C11', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U5 decoupling'))

    # ---- Hi-hat filter: Bread Modular HIHAT U2A. 100p / 100k input high-pass into an inverting
    # stage with a bridged-T (C13, C14, R17 + CUTOFF to V_MID) in its feedback.
    c.append(part('C12', 'C', '100p', 'C0603', {'1': 'HH_IN', '2': 'HH_INC'},
                  Voltage='50V', Note='Input high-pass C (Bread Modular HIHAT C1)'))
    c.append(part('R15', 'R', '100k', 'R0603', {'1': 'HH_INC', '2': 'HPF_SUM'},
                  Note='Input R (Bread Modular HIHAT R2)'))
    uh1 = 'MCP6002, 3.3 V. A: hi-hat filter (Bread Modular HIHAT U2A); B: VCA amp x3.2 (U2B)'
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'VMID_H', '2': 'HPF_SUM', '1': 'FILTERED'}, unit=1, Note=uh1))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'VCA_IN', '6': 'VCA_FB', '7': 'VCA_AMP'}, unit=2, Note=uh1))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=uh1))
    c.append(part('R16', 'R', '200k', 'R0603', {'1': 'HPF_SUM', '2': 'FILTERED'},
                  Note='Filter DC feedback (Bread Modular HIHAT R4)'))
    c.append(part('C13', 'C', '1n', 'C0603', {'1': 'HPF_SUM', '2': 'HPF_T'},
                  Voltage='50V', Note='Bridged-T C (Bread Modular HIHAT C2)'))
    c.append(part('C14', 'C', '1n', 'C0603', {'1': 'HPF_T', '2': 'FILTERED'},
                  Voltage='50V', Note='Bridged-T C (Bread Modular HIHAT C3)'))
    c.append(part('R17', 'R', '1k', 'R0603', {'1': 'HPF_T', '2': 'CUT_R'},
                  Note='Bridged-T minimum R (Bread Modular HIHAT R11)'))
    c.append(part('RV3', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'CUT_R', '2': 'VMID_H', '3': None},
                  Note='CUTOFF (Bread Modular HIHAT RV1 50k): bridged-T rheostat to V_MID, pin 3 open. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))

    # ---- Vactrol VCA: Bread Modular HIHAT U1 (LDR in series, 2 x 330R to V_MID) + U2B x3.2
    c.append(part('U7', 'VTL5C', 'VTL5C', 'VTL5C',
                  {'1': 'VAC_K', '2': 'HAT_CV', '3': 'VCA_IN', '4': 'FILTERED'},
                  Note='Vactrol VCA (Bread Modular HIHAT U1, Chinese VTL5C type). Hand-soldered THT on B'))
    c.append(part('R18', 'R', '330', 'R0603', {'1': 'VCA_IN', '2': 'VMID_H'},
                  Note='VCA shunt (Bread Modular HIHAT R5)'))
    c.append(part('R19', 'R', '330', 'R0603', {'1': 'VCA_IN', '2': 'VMID_H'},
                  Note='VCA shunt (Bread Modular HIHAT R6)'))
    c.append(part('R20', 'R', '22k', 'R0603', {'1': 'VCA_FB', '2': 'VCA_AMP'},
                  Note='VCA amp feedback (Bread Modular HIHAT R9): 1 + 22k / 10k = 3.2'))
    c.append(part('R21', 'R', '10k', 'R0603', {'1': 'VCA_FB', '2': 'VMID_H'},
                  Note='VCA amp gain R (Bread Modular HIHAT R10)'))
    c.append(part('R22', 'R', '1k', 'R0603', {'1': 'VCA_AMP', '2': 'HH_OUT'},
                  Note='Hi-hat output resistor (Bread Modular HIHAT R3)'))
    c.append(part('R23', 'R', '330', 'R0603', {'1': 'VAC_K', '2': 'GND'},
                  Note='Vactrol LED current R (Bread Modular HIHAT R1): ~5 mA at HAT_CV 3.3 V'))
    c.append(part('R24', 'R', '1k', 'R0603', {'1': '+3V3', '2': 'VMID_H'},
                  Note='Hi-hat V_MID divider (Bread Modular HIHAT R7)'))
    c.append(part('R25', 'R', '1k', 'R0603', {'1': 'VMID_H', '2': 'GND'},
                  Note='Hi-hat V_MID divider (Bread Modular HIHAT R8)'))
    c.append(part('C15', 'C', '47u', 'C0805', {'1': 'VMID_H', '2': 'GND'}, Voltage='6.3V',
                  Note='Hi-hat V_MID reservoir (Bread Modular HIHAT C6 47uF 0805)'))
    c.append(part('C16', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V',
                  Note='U6 decoupling (Bread Modular HIHAT C4)'))

    # ---- Hi-hat MCU: Bread Modular HIHAT 1.0.0 firmware unchanged
    c.append(part('U3', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', MCU_HIHAT,
                  Note='HIHAT MCU, 3.3 V, Bread Modular HIHAT firmware: note on -> PA5 gate, note > 60 -> '
                       'PA7 open hat, velocity on the PA6 DAC (accent)'))
    c.append(part('C7', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U3 decoupling (Bread Modular HIHAT C5)'))
    c.append(part('R5', 'R', '4.7k', 'R0603',
                  {'1': 'H_UPDI_PA0', '2': 'H_UPDI'}, Note='UPDI series resistor (Bread Modular HIHAT R26)'))
    c.append(part('J12', 'Conn_01x02', 'UPDI_HIHAT', 'H1x2',
                  {'1': 'H_UPDI', '2': 'GND'},
                  Note='HIHAT MCU (U3) UPDI: pin 1 UPDI, pin 2 GND. Program on Eurorack power (3.3 V target)'))

    # ---- Trigger (Bread Modular HIHAT): gate edge -> 10n / 100k differentiator -> U8A comparator
    # against V_MID -> Q2 passes the accent level (U8B) to the envelope capacitor through D4.
    c.append(part('R26', 'R', '10k', 'R0603', {'1': 'MIDI_GATE', '2': 'GATE'},
                  Note='MIDI gate series R (Bread Modular HIHAT R27; the BM external gate input is not built)'))
    c.append(part('C17', 'C', '10n', 'C0603', {'1': 'GATE', '2': 'TRIG'},
                  Voltage='50V', Note='Gate differentiator (Bread Modular HIHAT C7)'))
    c.append(part('R27', 'R', '100k', 'R0603', {'1': 'TRIG', '2': 'GND'},
                  Note='Differentiator R: ~1 ms trigger (Bread Modular HIHAT R13)'))
    uh2 = 'MCP6002, 3.3 V. A: trigger comparator (Bread Modular HIHAT U3A); B: accent follower (U3B)'
    c.append(part('U8', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'TRIG', '2': 'VMID_H', '1': 'TRIG_CMP'}, unit=1, Note=uh2))
    c.append(part('U8', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'ACCENT_SET', '6': 'ACCENT_BUF', '7': 'ACCENT_BUF'}, unit=2, Note=uh2))
    c.append(part('U8', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=uh2))
    c.append(part('R28', 'R', '330', 'R0603', {'1': 'TRIG_CMP', '2': 'Q2_B'},
                  Note='Q2 base R (Bread Modular HIHAT R12)'))
    c.append(part('Q2', 'SS8050', 'SS8050', 'SOT23', {'1': 'Q2_B', '2': 'PULSE', '3': 'ACCENT_BUF'},
                  Note='Trigger switch (Bread Modular HIHAT D3 SS8050): passes the accent level while triggered. '
                       'SOT-23 1 B, 2 E, 3 C'))
    c.append(part('R29', 'R', '10k', 'R0603', {'1': 'H_DAC', '2': 'ACCENT_CV'},
                  Note='Velocity DAC series R (Bread Modular HIHAT R19; the BM accent CV input is not built)'))
    c.append(part('R30', 'R', '100k', 'R0603', {'1': 'ACCENT_CV', '2': 'ACCENT_DIV'},
                  Note='Accent divider (Bread Modular HIHAT R21)'))
    c.append(part('R31', 'R', '100k', 'R0603', {'1': 'ACCENT_DIV', '2': 'GND'},
                  Note='Accent divider (Bread Modular HIHAT R24)'))
    c.append(part('R32', 'R', '1M', 'R0603', {'1': '+3V3', '2': 'ACCENT_SET'},
                  Note='Accent offset from +3V3 (Bread Modular HIHAT R22)'))
    c.append(part('R33', 'R', '1M', 'R0603', {'1': 'ACCENT_DIV', '2': 'ACCENT_SET'},
                  Note='Accent mix (Bread Modular HIHAT R23)'))

    # ---- Envelope (Bread Modular HIHAT): C18 holds the hit; R34 22k always discharges it (open hat);
    # with PA7 low (closed hat) Q3 adds R35 + DECAY. Q4 buffers it, U9A x2 -> HAT_CV drives the vactrol LED.
    c.append(part('D4', 'D_Schottky', 'B5819W', 'SOD123', {'1': 'ENV_CAP', '2': 'PULSE'},
                  Note='Envelope charge diode (Bread Modular HIHAT D2 SS14; B5819W is the same 1 A / 40 V '
                       'Schottky class, already in this BOM)'))
    c.append(part('C18', 'C', '4.7u', 'C0603', {'1': 'ENV_CAP', '2': 'GND'}, Voltage='16V',
                  Note='Envelope capacitor (Bread Modular HIHAT C8 4.7uF 0603)'))
    c.append(part('R34', 'R', '22k', 'R0603', {'1': 'ENV_CAP', '2': 'GND'},
                  Note='Open-hat decay (Bread Modular HIHAT R14): ~100 ms'))
    c.append(part('R35', 'R', '330', 'R0603', {'1': 'ENV_CAP', '2': 'DECAY_R'},
                  Note='Closed-hat decay minimum R (Bread Modular HIHAT R15)'))
    c.append(part('RV4', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'DECAY_R', '2': 'DECAY_W', '3': None},
                  Note='DECAY (Bread Modular HIHAT RV2 50k): closed-hat decay rheostat, pin 3 open. RV09 9 mm '
                       'vertical, linear (user stock). Hand-soldered'))
    c.append(part('Q3', 'Q_PNP_BEC', 'SS8550', 'SOT23', {'1': 'GATE_OPEN', '2': 'DECAY_W', '3': 'GND'},
                  Note='Closed-hat switch (Bread Modular HIHAT D4 SS8550): on while PA7 is low. SOT-23 1 B, 2 E, 3 C'))
    c.append(part('R36', 'R', '200k', 'R0603', {'1': 'MIDI_OPEN', '2': 'GATE_OPEN'},
                  Note='Q3 base R (Bread Modular HIHAT R20; the BM open-gate input is not built)'))
    c.append(part('Q4', 'SS8050', 'SS8050', 'SOT23', {'1': 'ENV_CAP', '2': 'ENV_BUF', '3': '+3V3'},
                  Note='Envelope emitter follower (Bread Modular HIHAT D1 SS8050). SOT-23 1 B, 2 E, 3 C'))
    c.append(part('R37', 'R', '10k', 'R0603', {'1': 'ENV_BUF', '2': 'GND'},
                  Note='Emitter load (Bread Modular HIHAT R16)'))
    uh3 = ('MCP6002, 3.3 V. A: envelope amp x2 -> HAT_CV (Bread Modular HIHAT U4A); '
           'B: NOISE IN bypass stage (BM U4B CV-out follower not needed: U10B buffers HAT_CV)')
    c.append(part('U9', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'3': 'ENV_BUF', '2': 'ENV_FB', '1': 'HAT_CV'}, unit=1, Note=uh3))
    c.append(part('U9', 'MCP6002-xSN', 'MCP6002', 'SOIC8',
                  {'5': 'VMID_H', '6': 'NIN_SUM', '7': 'NIN_BUF'}, unit=2, Note=uh3))
    c.append(part('U9', 'MCP6002-xSN', 'MCP6002', 'SOIC8', {'8': '+3V3', '4': 'GND'}, unit=3, Note=uh3))
    c.append(part('R38', 'R', '100k', 'R0603', {'1': 'ENV_FB', '2': 'HAT_CV'},
                  Note='Envelope amp feedback (Bread Modular HIHAT R17): x2'))
    c.append(part('R39', 'R', '100k', 'R0603', {'1': 'ENV_FB', '2': 'GND'},
                  Note='Envelope amp gain R (Bread Modular HIHAT R18)'))
    c.append(part('C19', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U8 decoupling'))
    c.append(part('C20', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U9 decoupling'))

    # ---- Outputs: U10 TL072 on +/-12 V. A: AUDIO (as modules/low OUT: AC coupled, x3, 1k);
    # B: HAT CV 0..3.3 V -> 0..5 V (as modules/acid ENV OUT) + the panel LED.
    uo = '+/-12 V. A: AUDIO output x3 (AC coupled); B: HAT CV output x1.51 + CV LED'
    c.append(part('C21', 'C', '1u', 'C0805', {'1': 'HH_OUT', '2': 'OUT_IN'},
                  Voltage='25V', Note='AC coupling (removes V_MID 1.65 V): 1.6 Hz with R40'))
    c.append(part('R40', 'R', '100k', 'R0603', {'1': 'OUT_IN', '2': 'GND'}, Note='Bias to 0 V'))
    c.append(part('U10', 'TL072', 'TL072', 'SOIC8', {'3': 'OUT_IN', '2': 'OUT_FB', '1': 'OUT_AMP'}, unit=1, Note=uo))
    c.append(part('R41', 'R', '20k', 'R0603', {'1': 'OUT_FB', '2': 'OUT_AMP'},
                  Note='Rf: gain 1 + 20k / 10k = 3: 3.3 Vpp -> ~10 Vpp (as modules/low)'))
    c.append(part('R42', 'R', '10k', 'R0603', {'1': 'OUT_FB', '2': 'GND'}, Note='Rg to GND'))
    c.append(part('R43', 'R', '1k', 'R1206', {'1': 'OUT_AMP', '2': 'AUDIO_OUT'}, Power='0.5W',
                  Note='Output series: short / +/-12 V mis-patch current limit (as modules/acid)'))
    c.append(part('J3', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'AUDIO_OUT', 'S': 'GND', 'TN': None}, Note='Hi-hat AUDIO out, Eurorack level'))
    c.append(part('U10', 'TL072', 'TL072', 'SOIC8', {'5': 'HAT_CV', '6': 'CVO_FB', '7': 'CVO_AMP'}, unit=2, Note=uo))
    c.append(part('R44', 'R', '51k', 'R0603', {'1': 'CVO_FB', '2': 'CVO_AMP'},
                  Note='Rf: gain 1 + 51k / 100k = 1.51: 3.30 V -> 4.98 V'))
    c.append(part('R45', 'R', '100k', 'R0603', {'1': 'CVO_FB', '2': 'GND'}, Note='Rg to GND'))
    c.append(part('R46', 'R', '1k', 'R1206', {'1': 'CVO_AMP', '2': 'CV_OUT'}, Power='0.5W',
                  Note='Output series: short / +/-12 V mis-patch protection (TL072 output current-limited)'))
    c.append(part('J4', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'CV_OUT', 'S': 'GND', 'TN': None}, Note='HAT CV out (the vactrol envelope), 0..5 V'))
    c.append(part('R47', 'R', '1k', 'R0603', {'1': 'CVO_AMP', '2': 'LED_A'},
                  Note='CV LED current: ~3 mA at 5 V'))
    c.append(part('D5', 'LED', 'LED_3mm_red', 'LED3', {'2': 'LED_A', '1': 'GND'},
                  Note='HAT CV LED (follows the envelope). Hand-soldered 3 mm THT, dome flush with the panel '
                       '(as modules/8bit)'))
    c.append(part('U10', 'TL072', 'TL072', 'SOIC8', {'4': '-12V_F', '8': '+12V_F'}, unit=3, Note=uo))
    c.append(part('C22', 'C', '100n', 'C0603', {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U10 V+ decoupling'))
    c.append(part('C23', 'C', '100n', 'C0603', {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U10 V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts. Codes reused from modules/acid (checked live 2026-10-22) plus the new HATS parts
# (100p, 1n, 4.7u, 47u, SS8050, SS8550; assembly search 2026-10-23). Stock is a dated observation,
# not a guarantee. THT parts carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM'),
    ('R', '330', 'R0603'): dict(LCSC='C23138', MPN='0603WAF3300T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0603'): dict(LCSC='C4184', MPN='0603WAF2002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '33k', 'R0603'): dict(LCSC='C4216', MPN='0603WAF3302T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '200k', 'R0603'): dict(LCSC='C25811', MPN='0603WAF2003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '470k', 'R0603'): dict(LCSC='C23178', MPN='0603WAF4703T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1M', 'R0603'): dict(LCSC='C22935', MPN='0603WAF1004T5E', Manufacturer='UNI-ROYAL'),
    ('C', '100p', 'C0603'): dict(LCSC='C14858', MPN='CL10C101JB8NNNC', Manufacturer='Samsung'),
    ('C', '1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '4.7u', 'C0603'): dict(LCSC='C19666', MPN='CL10A475KO8NNNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '47u', 'C0805'): dict(LCSC='C16780', MPN='CL21A476MQYNNNE', Manufacturer='Samsung'),
    ('C', '100u', 'C1206'): dict(LCSC='C15008', MPN='CL31A107MQHNNNE', Manufacturer='Samsung'),
    ('D_Dual_Series_AKC', 'BAV199', 'SOT23'): dict(LCSC='C40919', MPN='BAV199,215', Manufacturer='Nexperia'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('SS8050', 'SS8050', 'SOT23'): dict(LCSC='C431710', MPN='SS8050', Manufacturer='MDD(Microdiode Semiconductor)'),
    ('Q_PNP_BEC', 'SS8550', 'SOT23'): dict(LCSC='C364314', MPN='SS8550', Manufacturer='MDD(Microdiode Semiconductor)'),
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
    (T(4, 2), 'BIG MODULAR HATS - S3 schematic: Bread Modular NOISE (blue) -> HIHAT on one 6HP module, two ATtiny1616 '
              '(each runs its Bread Modular firmware), 3.3 V internal signals. Circuit intent: docs/research.md', 2.0),
    (T(4, 5), 'Signal nets are wired; supplies use power symbols. VMID_H (hi-hat V_MID, R24/R25/C15) is joined by its net labels.', 1.27),
    (T(4, 9), 'MIDI IN (TS): 8bit / LOW NPN front end, pull-ups on +3V3; RX feeds both MCUs. '
              'JP1 shipped OPEN: 1-2 = protected (PORT_INVEN on PB3), 2-3 = direct.', 1.27),
    (T(36, 58), 'NOISE MCU U2 (Bread Modular NOISE): PA6 DAC white noise, PA7 TONE.', 1.27),
    (T(66, 30), 'NOISE (Bread Modular NOISE, pink not built): U4A white follower, C8 + BLUE TONE high-pass, U4B blue follower.', 1.27),
    (T(98, 6), 'NOISE IN: AC coupled, x -0.33 around VMID_H (10 Vpp -> 3.3 Vpp, hotter clips), as modules/low AUDIO.', 1.27),
    (T(112, 74), 'NORMAL (U5 TS5A23157): jack empty -> TN = T pulls IN1 low -> COM1 = NC1 = BLUE_NOISE;\n'
                 'patched -> TN open, R14 pulls IN1 high -> COM1 = NO1 = NIN_BUF.', 1.27),
    (T(142, 28), 'HI-HAT FILTER + VCA (Bread Modular HIHAT): U6A bridged-T filter (CUTOFF), U7 vactrol VCA, U6B x3.2.', 1.27),
    (T(36, 106), 'HIHAT MCU U3 (Bread Modular HIHAT): PA5 gate, PA7 open hat (note > 60), PA6 velocity DAC.', 1.27),
    (T(58, 66), 'TRIGGER + ACCENT: gate edge (C17/R27) -> U8A comparator -> Q2 passes the U8B accent level.', 1.27),
    (T(96, 86), 'ENVELOPE: D4 charges C18; R34 decays (open hat), Q3 adds R35 + DECAY (closed hat); Q4 + U9A x2 -> HAT_CV.', 1.27),
    (T(186, 58), 'AUDIO OUT: AC coupled, U10A x3 (3.3 Vpp -> ~10 Vpp), 1k to J3 (as modules/low).', 1.27),
    (T(186, 84), 'HAT CV OUT: U10B x1.51: 0..3.3 V -> 0..5 V, 1k to J4; D5 LED shows it.', 1.27),
    (T(4, 128), 'POWER: +12V -> D1 -> +12V_F (U10, U1 HT7533-1 -> +3V3); -12V -> D2 -> -12V_F (U10).', 1.27),
    (T(68, 128), 'SUPPLY PINS + DECOUPLING', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/hats/schematic/' + key))


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
    if sym in ('MMBT3904', 'SS8050', 'Q_PNP_BEC'):
        return ((-2.54, -6.35), (-2.54, -4.7), 'right')
    if sym == 'SolderJumper_3_Open':
        return (0, -5.08), (0, -3.175), None
    if sym == 'HT75xx-1-SOT89':
        return (0, -7.62), (0, -6.35), None
    if sym == 'PWR_FLAG':
        return (0, -5.08), (0, -2.54), None
    return left


# Per-part text placement overrides (reference offset, value offset, justify), mm.
TEXT_SIDE = {'J2': ((0, -8.89), (-3.81, 8.89), None), 'D7': ((7.62, -1.27), (7.62, 1.27), 'left')}


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
        '(options "") (descr "HATS pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A2")
      (title_block (title "Big Modular - HATS") (rev "S3") (company "Big Modular")
        (comment 1 "SCHEMATIC S3 - Bread Modular NOISE (blue) + HIHAT, two ATtiny1616, 3.3 V signals, wired nets")
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
    assert multi == {k: {1, 2, 3} for k in ('U4', 'U5', 'U6', 'U8', 'U9', 'U10')}, multi
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
