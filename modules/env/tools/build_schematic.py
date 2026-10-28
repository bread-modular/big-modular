"""Generate the ENV S3 schematic (hardware/env.kicad_sch) and its pinned symbols.

Run from modules/env:
  python3 -B tools/build_schematic.py

Writes hardware/ENV.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the ENV library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
of docs/research.md section 3: the ACID envelope block taken out on its own 6HP module.
The 8bit / ACID MIDI input drives one ATtiny1616 at 3.3 V running the Bread Modular ENV
models (HR / AR / ASR, MODE button + three LEDs), a REC button + LED that records the
knob positions, ATTACK / RELEASE knobs and the PA6 DAC envelope, which one TL072 stage
maps from 0..3.3 V to a protected 0..5 V ENV OUT with an envelope-level LED.

Placement (LAYOUT) is by hand. Signal wires are found by route_wires(): a small grid
router (1.27 mm) that draws every signal net as axis-aligned wires, never touching a
pin, stub, symbol body or wire end of another net (perpendicular crossings without a
junction are allowed). LABEL_NETS are the only signal nets joined by name labels.
Supply pins get a stub and a stock power symbol. The build exports the native netlist
and fails unless it equals circuit(). The router and writer are modules/acid's, unchanged.
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
PROJECT = 'env'
LIB = 'ENV'
STUB = 2.54

FILTER_EDITS = {
    'Conn_01x02': '*_1x??_*',
    'Conn_02x05_Odd_Even': '*_2x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LED': ('Device', 'LED'),
    'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'ATtiny1616-M': ('MCU_Microchip_ATtiny', 'ATtiny1616-M'),
    'HT75xx-1-SOT89': ('Regulator_Linear', 'HT75xx-1-SOT89'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_01x02': ('Connector_Generic', 'Conn_01x02'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'MMBT3904': ('Transistor_BJT', 'MMBT3904'),
    '1N4148W': ('Diode', '1N4148W'),
    'SW_Push': ('Switch', 'SW_Push'),
    'GND': ('power', 'GND'), '+3V3': ('power', '+3V3'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric', 'C1206': 'C_1206_3216Metric',
    'SOD123': 'D_SOD-123', 'SOT23': 'SOT-23', 'SOT89': 'SOT-89-3',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
    'LED3': 'LED_D3.0mm', 'SW6': 'SW_PUSH_6mm_H7.3mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# Supply nets are drawn with power symbols (net name = symbol value).
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Signal nets joined by name labels instead of wires: none, every signal net is wired.
LABEL_NETS = set()

# ATtiny1616-M (VQFN-20) pin numbers: the ACID map without the MCO. Bread Modular ENV map
# (PA1/PA2 time knobs, PC0 algorithm button, PC1 its LED, PC2 second button, PC3 its LED),
# PB3 MIDI RX, PA6 DAC, PA0 UPDI; PA4/PA5 drive the two extra envelope-mode LEDs (as ACID).
# S3: PB2 GATE (Q2, inverted), PB1 GATE_SENSE (J6 jack detect, high = patched = MIDI bypassed).
# PA3, PA7, PB0, PB4, PB5 are unused (no-connect).
MCU = {'11': 'RX', '7': 'DAC', '19': 'UPDI_PA0',
       '20': 'ENV_A', '1': 'ENV_R', '15': 'MODE_SW', '16': 'LED_HR', '5': 'LED_AR', '6': 'LED_ASR',
       '17': 'REC_SW', '18': 'LED_REC',
       '4': '+3V3', '3': 'GND', '21': 'GND',
       '12': 'GATE', '13': 'GATE_SENSE',
       '2': None, '8': None, '9': None, '10': None, '14': None}

GRID = 2.54
OFFSET = (4, 4)  # LAYOUT / TEXTS origin inside the A3 frame, grid units
DEBUG_PLACEMENT = bool(__import__('os').environ.get('ENV_PLACEMENT_ONLY'))


def part(ref, sym, value, fp, pins, unit=1, **fields):
    key = ref if unit == 1 else f'{ref}.{unit}'
    x, y, rot, *mirror = LAYOUT[key]
    x, y = x + OFFSET[0], y + OFFSET[1]
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(round(x * GRID, 2), round(y * GRID, 2)), rot=rot,
                mirror=bool(mirror), pins=pins, unit=unit, fields=fields)


# Symbol placement in 2.54 mm grid units: ref (unit 1) or ref.unit -> (x, y, rotation[, 'mirror']).
# The ACID MIDI / MCU / envelope-UI placement, then the CV output stage right of the MCU;
# power and supply pins at the bottom.
LAYOUT = {
    # MIDI input (as ACID / modules/low)
    'J1': (6, 22, 0), 'R1': (12, 20.5, 180), 'R2': (16.5, 22, 90), 'D3': (20, 24.5, 270),
    'Q1': (23, 22, 0), 'R3': (24, 16.5, 180), 'JP1': (33, 18, 0),
    'J5': (6, 31, 0),
    # GATE IN (S3): the MIDI front end again, plus the J6 jack detect
    'J6': (6, 44, 0), 'R14': (11, 47.5, 0), 'R15': (15.5, 44, 90), 'R16': (19, 47.5, 0),
    'D9': (21.5, 47.5, 270), 'Q2': (27, 44, 0), 'R17': (28, 38.5, 180),
    'R18': (12, 55, 90), 'R19': (16, 53, 180),
    # MCU, UPDI
    'U2': (40, 52, 0), 'C6': (32.5, 40, 0), 'R4': (50, 36, 180), 'J4': (58, 32, 0),
    # Envelope UI, left of the MCU: PC0..PC3 fan out to four columns
    'SW1': (14, 66, 270), 'R5': (19, 65.5, 0), 'D4': (19, 70.5, 90),
    'SW2': (24, 66, 270), 'R8': (29, 65.5, 0), 'D7': (29, 70.5, 90),
    # Envelope UI, right of the MCU: knobs, mode LEDs AR / ASR, DAC
    'RV1': (60, 40, 180), 'RV2': (68, 42, 180),
    'R6': (54, 49, 90), 'D5': (60, 49, 180), 'R7': (54, 54, 90), 'D6': (60, 54, 180),
    'R9': (70, 51, 90),
    # ENV OUT stage (ACID U11B), envelope LED, U3B tied off
    'U3': (82, 52, 0), 'R10': (81.5, 57, 90), 'R11': (78, 61.5, 0), 'R12': (92, 52, 90),
    'J2': (104, 52, 0, 'mirror'), 'R13': (96, 58, 0), 'D8': (96, 63, 90),
    'U3.2': (82, 72, 0),
    # Power entry
    'J3': (9, 92, 0), 'D1': (21, 89, 180), 'D2': (21, 97, 0), 'C1': (28, 91.5, 0), 'C2': (32, 91.5, 0),
    'U1': (40, 90, 0), 'C3': (47, 91.5, 0), 'C4': (51, 91.5, 0), 'C5': (55, 91.5, 0),
    '#FLG01': (6, 103, 0), '#FLG02': (12, 103, 0), '#FLG03': (18, 103, 0), '#FLG04': (24, 103, 0),
    '#FLG05': (30, 103, 0),
    # Op-amp supply unit and its decoupling
    'U3.3': (70, 90, 0), 'C7': (74, 90.5, 0), 'C8': (79, 90.5, 0),
}

# Hand-drawn polylines for nets the router should not choose itself (same format as
# modules/low WIRES: 'REF/pin' pin ends and (x, y) grid points). Everything else is routed.
WIRES = {}

LABEL_AT = {}


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7533-1 -> +3V3 (as ACID)
    c.append(part('J3', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5',
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header on B, pin 1 (-12 V) at the bottom (as modules/audio-out); '
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
                  Note='3.3 V LDO, 30 V max input, 100 mA. Load ~20 mA (MCU, 4 LEDs at 4 mA): ~0.17 W at 11.6 V in'))
    c.append(part('C3', 'C', '1u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805',
                  {'1': '+3V3', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C5', 'C', '100u', 'C1206',
                  {'1': '+3V3', '2': 'GND'}, Voltage='6.3V', Note='+3V3 bulk (Bread Modular ENV C1 100uF 1206)'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V'}))

    # ---- MIDI input (TS modular MIDI): the 8bit / LOW / ACID NPN front end with its JP1 bypass
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(part('J5', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None},
                  Note='MIDI out: passive thru, wired in parallel with J1 (daisy chain); no buffer'))
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

    # ---- GATE IN (S3): the MIDI NPN front end for a gate, plus a jack detect. Patched (TN open,
    # GATE_SENSE high) the firmware takes the gate from J6 and ignores MIDI notes (MIDI bypassed);
    # unpatched TN ties GATE_SENSE to the R14 pull-down (low) and MIDI drives the envelope.
    c.append(part('J6', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'GATE_IN', 'S': 'GND', 'TN': 'GATE_TN'},
                  Note='GATE IN (gate / trigger, threshold ~1.9 V). Patched: MIDI notes are bypassed (TN switch '
                       'opens, GATE_SENSE high)'))
    c.append(part('R14', 'R', '100k', 'R0603', {'1': 'GATE_IN', '2': 'GND'},
                  Note='Input pull-down: unpatched keeps Q2 off and pulls GATE_SENSE low through TN'))
    c.append(part('R15', 'R', '100k', 'R0603', {'1': 'GATE_IN', '2': 'Q2_B'},
                  Note='Base resistor: 0.11 mA at +/-12 V'))
    c.append(part('R16', 'R', '51k', 'R0603', {'1': 'Q2_B', '2': 'GND'},
                  Note='Base pull-down: threshold 0.65 V x (1 + 100k / 51k) = ~1.9 V'))
    c.append(part('D9', '1N4148W', '1N4148W', 'SOD123', {'1': 'Q2_B', '2': 'GND'},
                  Note='Clamps Q2 B-E to -0.7 V for a negative input (as D3)'))
    c.append(part('Q2', 'MMBT3904', 'MMBT3904', 'SOT23', {'1': 'Q2_B', '2': 'GND', '3': 'GATE'},
                  Note='Inverting gate buffer: gate high = PB2 low. Firmware: PORT_INVEN on PB2'))
    c.append(part('R17', 'R', '22k', 'R0603', {'1': 'GATE', '2': '+3V3'}, Note='Q2 collector pull-up (as R3)'))
    c.append(part('R18', 'R', '51k', 'R0603', {'1': 'GATE_TN', '2': 'GATE_SENSE'},
                  Note='Jack-detect series R: limits the PB1 clamp current to 0.24 mA while a +/-12 V plug '
                       'touches TN on insertion'))
    c.append(part('R19', 'R', '1M', 'R0603', {'1': 'GATE_SENSE', '2': '+3V3'},
                  Note='Jack-detect pull-up (as ACID R20): patched = TN open = 3.3 V; unpatched 0.33 V '
                       '(R18 + R14 || R15-R16 to GND)'))

    # ---- MCU: one ATtiny1616 at 3.3 V runs the ENV firmware (the ENV half of the ACID firmware)
    c.append(part('U2', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', MCU,
                  Note='3.3 V, as Bread Modular ENV. Firmware: MIDI note on/off = gate (PB2 GATE IN instead while '
                       'PB1 GATE_SENSE is high), 3 envelope models '
                       '(HR / AR / ASR, saved in EEPROM), REC knob recording, envelope on the PA6 DAC'))
    c.append(part('C6', 'C', '100n', 'C0603',
                  {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U2 decoupling (Bread Modular ENV C2)'))
    c.append(part('R4', 'R', '4.7k', 'R0603',
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular R17)'))
    c.append(part('J4', 'Conn_01x02', 'UPDI', 'H1x2',
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power (3.3 V target)'))

    # ---- Envelope UI (Bread Modular ENV knobs, buttons and LEDs; ACID values)
    c.append(part('R9', 'R', '1k', 'R0603',
                  {'1': 'DAC', '2': 'ENV_CV'},
                  Note='DAC series R (Bread Modular ENV R2 / ACID R12)'))
    c.append(part('RV1', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'GND', '2': 'ENV_A', '3': '+3V3'},
                  Note='ATTACK (Bread Modular ENV CV1, PA1): attack / hold time. CW = longer. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))
    c.append(part('RV2', 'R_Potentiometer', '50k', 'RV09',
                  {'1': 'GND', '2': 'ENV_R', '3': '+3V3'},
                  Note='RELEASE (Bread Modular ENV CV2, PA2): release time. CW = longer. '
                       'RV09 9 mm vertical, linear (user stock). Hand-soldered'))
    c.append(part('SW1', 'SW_Push', 'MODE', 'SW6',
                  {'1': 'MODE_SW', '2': 'GND'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Envelope model select HR -> AR -> ASR (Bread Modular ENV algo button, PC0 internal '
                       'pull-up): generic 6 x 6 mm THT tact as modules/8bit, pressed through the panel by the printed cap'))
    c.append(part('SW2', 'SW_Push', 'REC', 'SW6',
                  {'1': 'REC_SW', '2': 'GND'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Record knob positions (8bit crash style; PC2 internal pull-up): generic 6 x 6 mm THT tact'))
    for ref, rref, net, role in (('D4', 'R5', 'LED_HR', 'Mode LED HR (hold-release), PC1'),
                                 ('D5', 'R6', 'LED_AR', 'Mode LED AR (attack-release), PA4'),
                                 ('D6', 'R7', 'LED_ASR', 'Mode LED ASR (attack-sustain-release), PA5'),
                                 ('D7', 'R8', 'LED_REC', 'Record LED, PC3')):
        c.append(part(rref, 'R', '330', 'R0603', {'1': net, '2': net + '_A'},
                      Note='LED current ~4 mA at 3.3 V (Bread Modular ENV R6/R9 330R)'))
        c.append(part(ref, 'LED', 'LED_3mm_red', 'LED3', {'2': net + '_A', '1': 'GND'},
                      Note=role + '. Hand-soldered 3 mm THT, dome flush with the panel (as modules/8bit)'))

    # ---- ENV OUT: DAC envelope 0..3.3 V -> 0..5.0 V, DC coupled, protected (ACID U11B)
    uout = 'TL072, +/-12 V. A: envelope CV output x1.51 + level LED; B: unused, tied off as a grounded follower'
    c.append(part('U3', 'TL072', 'TL072', 'SOIC8',
                  {'3': 'ENV_CV', '2': 'CVO_FB', '1': 'CVO_AMP'}, unit=1, Note=uout))
    c.append(part('R10', 'R', '51k', 'R0603', {'1': 'CVO_FB', '2': 'CVO_AMP'},
                  Note='Rf: gain 1 + 51k / 100k = 1.51: 3.30 V -> 4.98 V'))
    c.append(part('R11', 'R', '100k', 'R0603', {'1': 'CVO_FB', '2': 'GND'}, Note='Rg to GND'))
    c.append(part('R12', 'R', '1k', 'R1206', {'1': 'CVO_AMP', '2': 'ENV_OUT'},
                  Power='0.5W', Note='Output series: short / +/-12 V mis-patch protection (TL072 output '
                                     'current-limited, 12 mA max through 1k)'))
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'ENV_OUT', 'S': 'GND', 'TN': None}, Note='Envelope CV out, 0..5 V'))
    c.append(part('R13', 'R', '1k', 'R0603', {'1': 'CVO_AMP', '2': 'ENV_LED_A'},
                  Note='Envelope LED: ~3 mA at the 5 V peak, lights above ~1.8 V'))
    c.append(part('D8', 'LED', 'LED_3mm_red', 'LED3', {'2': 'ENV_LED_A', '1': 'GND'},
                  Note='Envelope level LED (Bread Modular ENV envelope LED), driven by U3A before R12 so a '
                       'patched load does not dim it. Hand-soldered 3 mm THT'))
    c.append(part('U3', 'TL072', 'TL072', 'SOIC8',
                  {'5': 'GND', '6': 'U3B_OUT', '7': 'U3B_OUT'}, unit=2, Note=uout))
    c.append(part('U3', 'TL072', 'TL072', 'SOIC8', {'4': '-12V_F', '8': '+12V_F'}, unit=3, Note=uout))
    c.append(part('C7', 'C', '100n', 'C0603',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U3 V+ decoupling'))
    c.append(part('C8', 'C', '100n', 'C0603',
                  {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U3 V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts: the ACID SOURCING rows this circuit uses (re-checked live for ACID 2026-10-22;
# not re-checked for ENV, see docs/research.md). All Basic except the 0.5 W 1206 1k (no Basic
# 0.5 W 1206 exists) and the ATtiny1616. Stock is a dated observation, not a guarantee. THT
# parts carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM'),
    ('R', '330', 'R0603'): dict(LCSC='C23138', MPN='0603WAF3300T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1M', 'R0603'): dict(LCSC='C22935', MPN='0603WAF1004T5E', Manufacturer='UNI-ROYAL'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '100u', 'C1206'): dict(LCSC='C15008', MPN='CL31A107MQHNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7533-1', 'SOT89'): dict(LCSC='C14289', MPN='HT7533-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR', Manufacturer='Microchip'),
    ('TL072', 'TL072', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
}


def T(x, y):
    return (round((x + OFFSET[0]) * GRID, 2), round((y + OFFSET[1]) * GRID, 2))


# Block notes: (grid position, text, size). route_wires() keeps wires out of their boxes.
TEXTS = [
    (T(4, 4), 'BIG MODULAR ENV - S3 schematic: the ACID envelope (Bread Modular ENV on one ATtiny1616) as its own '
              '6HP MIDI + GATE module, 3.3 V internal signals. Circuit intent: docs/research.md', 2.0),
    (T(4, 6.5), 'Every signal net is wired; supplies use power symbols.', 1.27),
    (T(4, 10), 'MIDI IN (TS): 8bit / LOW / ACID NPN front end, pull-ups on +3V3; J5 MIDI OUT = passive thru of J1. '
               'JP1 shipped OPEN: 1-2 = protected (PORT_INVEN on PB3), 2-3 = direct.\n'
               'GATE IN (J6): NPN gate buffer -> PB2 (inverted); TN jack detect -> PB1: patched = high = '
               'MIDI notes bypassed, the gate drives the envelope.', 1.27),
    (T(4, 76), 'ENVELOPE UI (Bread Modular ENV): MODE (PC0) + LEDs HR/AR/ASR (PC1, PA4, PA5);\n'
               'REC (PC2) + LED (PC3) records the knob positions (8bit crash style). Internal pull-ups.', 1.27),
    (T(48, 26), 'ATTACK (PA1) / RELEASE (PA2). DAC PA6 -> R9 -> ENV_CV (0..3.3 V).', 1.27),
    (T(76, 40), 'ENV OUT: U3A x1.51: envelope 0..3.3 V -> 0..5.0 V,\n'
                'DC coupled, 1k 0.5 W to J2; D8 shows the level.', 1.27),
    (T(4, 83), 'POWER: +12V -> D1 -> +12V_F (U3, U1 HT7533-1 -> +3V3); -12V -> D2 -> -12V_F (U3).', 1.27),
    (T(68, 83), 'SUPPLY PINS + DECOUPLING', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/env/schematic/' + key))


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
TEXT_SIDE = {'R16': ((-1.905, -0.635), (-1.905, 1.27), 'right'),
             'D9': ((1.905, -0.635), (1.905, 1.27), 'left')}


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
SHEET = (420.0, 297.0)  # A3


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
        '(options "") (descr "ENV pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - ENV") (rev "S3") (company "Big Modular")
        (comment 1 "SCHEMATIC S3 - MIDI envelope (Bread Modular ENV from ACID), 3.3 V signals, 0..5 V out, wired nets")
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
    assert multi == {'U3': {1, 2, 3}}, multi
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
