"""Generate the MCC S4 schematic (hardware/mcc.kicad_sch) and its pinned symbols.

Run from modules/mcc:
  python3 -B tools/build_schematic.py

Writes hardware/MCC.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the MCC library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. CIRCUIT below is the
circuit of docs/research.md section 3: Bread Modular MCC (ATtiny1616 -> MIDI CC:
four knobs on PA4-PA7, bank button PC0, bank LEDs PC1-PC3, MIDI RX PB3 / TX PB2)
moved to Eurorack, plus four CV inputs read on their own ADC pins (PB0, PB1, PA2, PA3).
Knobs are plain dividers into the MCU; each CV input is the 8bit CV stage (bipolar
level shift, clamp, MCP6002 follower on +5V). The firmware decides how knob and CV
combine. MIDI in has the 8bit/MIDI V2 protected front end and MIDI out the MIDI V2
clamp, each with a 3-pad solder jumper (JP1/JP2) that bypasses the protection.

Parts are joined by drawn wires, junctions and power symbols; every block is wired to the
MCU (labels only name the nets). The build asserts that nothing dangles and that the exported
netlist equals CIRCUIT. Multi-unit symbols (MCP6002) are placed per unit.

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
PROJECT = 'mcc'
LIB = 'MCC'
REV = 'S4'

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the MCC library, so the copies
# get the same patterns without the library part.
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
    'MCP6002-xSN': ('Amplifier_Operational', 'MCP6002-xSN'),
    # CJ431 SOT-23 pinout is 1 REF, 2 K, 3 A: that is TL432DBZ, not TL431DBZ (as modules/midi V2).
    'TL432DBZ': ('Reference_Voltage', 'TL432DBZ'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_01x02': ('Connector_Generic', 'Conn_01x02'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'SW_Push': ('Switch', 'SW_Push'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'MMBT3904': ('Transistor_BJT', 'MMBT3904'),
    '1N4148W': ('Diode', '1N4148W'),
    'BAT54SW': ('Diode', 'BAT54SW'),
    'GND': ('power', 'GND'), '+5V': ('power', '+5V'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'SOD123': 'D_SOD-123', 'LED3': 'LED_D3.0mm', 'SOT23': 'SOT-23', 'SOT323': 'SOT-323_SC-70',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'SOT89': 'SOT-89-3', 'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'RV09': 'Potentiometer_RV09', 'SW6': 'SW_PUSH_6mm_H7.3mm',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1', 'JP2'}

# ATtiny1616-M (VQFN-20) pin numbers. The Bread Modular MCC pin map is kept so its firmware
# ports: PA4-PA7 the four knobs (AI_PIN .. AI_PIN + 3), PC0 bank button, PC1-PC3 bank A/B/C
# LEDs, PB3 MIDI RX, PB2 MIDI TX, PA0 UPDI. The four CV inputs are new and use spare ADC0 pins
# no BM MCC firmware touches: PB0, PB1 (AIN11/10) and PA2, PA3 (AIN2/3). They are picked by
# the carrier: with U1 turned, PB0/PB1 face U4 (CV1/CV2, above) and PA2/PA3 face U5 (CV3/CV4,
# below). Knobs and CVs are read separately; the firmware decides how they combine. PA1, PB4,
# PB5 stay spare.
MCU = {'14': 'CV1_ADC', '13': 'CV2_ADC', '1': 'CV3_ADC', '2': 'CV4_ADC',
       '5': 'POT1', '6': 'POT2', '7': 'POT3', '8': 'POT4',
       '15': 'BANK_SW', '16': 'LED_A', '17': 'LED_B', '18': 'LED_C',
       '11': 'RX', '12': 'TX', '19': 'UPDI_PA0', '4': '+5V', '3': 'GND', '21': 'GND',
       '20': None, '10': None, '9': None}

CHANNELS = 4
MX, MY = 200.66, 259.08     # MIDI out block (below the bank LEDs, TX in from the left)
IX, IY = 0.0, 142.24        # MIDI in block (bottom left, RX climbs to PB3)
PX = 170.18                 # power entry block, top right (shifted from the 8bit position)


def r(v):
    return round(v, 2)


def pw(x, y):
    """Power-block coordinates (drawn at the 8bit position, shifted right by PX)."""
    return (r(x + PX), y)


# U1 is drawn mirrored (PA/PB on the left, facing the CV, knob and MIDI blocks). Pin-end Y
# of the analog pins on the left side (sheet mm).
U1_AT = (175.26, 134.62)
MCU_PIN_Y = {'1': 121.92, '2': 124.46, '5': 127.0, '6': 129.54, '7': 132.08, '8': 134.62,
             '14': 139.7, '13': 142.24}
CV_PIN = {1: '14', 2: '13', 3: '1', 4: '2'}       # PB0, PB1, PA2, PA3 (ADC0 AIN11/10/2/3)
POT_PIN = {1: '5', 2: '6', 3: '7', 4: '8'}        # PA4-PA7: the Bread Modular MCC knob pins
# CV channel n: jack J1n, level shift R1n 56k / R2n 51k to +5V / R3n 510k to GND, clamp D1n,
# filter C1n, follower = one half of a MCP6002 (U4: CV1 A, CV2 B; U5: CV3 A, CV4 B).
# Each block is drawn next to the MCU pin it feeds: CV3/CV4 above U1 drop into PA2/PA3, CV1/CV2
# below the knobs climb to PB0/PB1.
CH_ORIGIN = {3: (25.4, 53.34), 4: (25.4, 81.28), 1: (25.4, 205.74), 2: (25.4, 233.68)}
# Fan column of each wire into U1. Dropping wires (CV3, CV4) nest with the lower pin further
# left; climbing wires (knobs, CV1, CV2, TX, RX) nest with the higher pin further left, so no
# two wires cross (the TX/RX pair still crosses once, see the MIDI note).
CV_FAN_X = {3: 137.16, 4: 134.62, 1: 142.24, 2: 144.78}
POT_FAN_X = {1: 132.08, 2: 134.62, 3: 137.16, 4: 139.7}
# Knob n: RVn plain divider +5V..GND, wiper straight into its pin with C3n 10n (as 8bit).
POT_ORIGIN = {n: (114.3, r(139.7 + 17.78 * (n - 1))) for n in (1, 2, 3, 4)}
OPAMP = {1: ('U4', 1), 2: ('U4', 2), 3: ('U5', 1), 4: ('U5', 2)}   # (package, unit)
OPAMP_PINS = {1: ('3', '2', '1'), 2: ('5', '6', '7')}                # unit: (+in, -in, out)
# Op-amp supply units (MCP6002 unit C) and their decoupling, next to the power entry.
SUPPLY = {'U4': ((345.44, 58.42), 'C6'), 'U5': ((368.3, 58.42), 'C7')}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


# One Note for every MCP6002 unit, so the PCB footprint field matches whichever unit it takes.
U_NOTE = {'U4': 'A: CV1 follower, B: CV2 follower. Rail-to-rail in/out on +5V: low source impedance for the ADC, '
                'never outside 0..5 V (as 8bit U4)',
          'U5': 'A: CV3 follower, B: CV4 follower. Rail-to-rail in/out on +5V: low source impedance for the ADC, '
                'never outside 0..5 V (as 8bit U4)'}


def channel(n):
    """One CV channel (8bit CV input): parts, wires, power symbols and labels (block-relative)."""
    bx, by = CH_ORIGIN[n]

    def p(dx, dy):
        return (r(bx + dx), r(by + dy))

    net = lambda s: f'CV{n}_{s}'
    J, RI, RO, RG, D, C = (f'J1{n}', f'R1{n}', f'R2{n}', f'R3{n}', f'D1{n}', f'C1{n}')
    U, unit = OPAMP[n]
    pin_p, pin_n, pin_o = OPAMP_PINS[unit]
    pin = CV_PIN[n]
    parts = [
        part(J, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', p(0, 0), 0,
             {'T': net('IN'), 'S': 'GND', 'TN': 'GND'},
             Note=f'CV {n} in, -5.5..+5.5 V. Tip normalled to GND: unpatched reads mid-scale (0 V), as 8bit'),
        part(RI, 'R', '56k', 'R0603', p(17.78, 0), 90, {'1': net('IN'), '2': net('SH')},
             Note='Level-shift input resistor. Input impedance R1n + R2n||R3n = 102k. '
                  'Clamp current <= 0.21 mA at +/-12 V'),
        part(RO, 'R', '51k', 'R0603', p(25.4, -3.81), 0, {'1': '+5V', '2': net('SH')},
             Note='Level-shift offset: 0 V CV -> 2.49 V (mid-scale). +5V is also the ADC reference'),
        part(RG, 'R', '510k', 'R0603', p(30.48, 3.81), 0, {'1': net('SH'), '2': 'GND'},
             Note='Level-shift trim: with R1n/R2n maps -5.49..+5.55 V to 0..5 V (gain 0.453)'),
        part(C, 'C', '1n', 'C0603', p(40.64, 3.81), 0, {'1': net('SH'), '2': 'GND'}, Voltage='50V',
             Note='With R1n||R2n||R3n (25.4k): 6.3 kHz CV low-pass'),
        part(D, 'BAT54SW', 'BAT54SW', 'SOT323', p(50.8, -7.62), 0, {'1': 'GND', '2': '+5V', '3': net('SH')},
             Note=f'CV clamp: holds the {U} input within -0.3..+5.3 V on a +/-12 V mis-patch'),
        part(U, 'MCP6002-xSN', 'MCP6002', 'SOIC8', p(60.96, 2.54), 0,
             {pin_p: net('SH'), pin_n: net('ADC'), pin_o: net('ADC')}, unit=unit, Note=U_NOTE[U]),
    ]
    fan = CV_FAN_X[n]
    wires = [
        [f'{J}.S', p(7.62, -2.54), p(7.62, -5.08)], [f'{J}.TN', p(7.62, 2.54), p(7.62, 5.08)],
        [f'{J}.T', f'{RI}.1'], [f'{RI}.2', f'{U}.{pin_p}'], [f'{D}.3', p(50.8, 0)],
        [f'{U}.{pin_o}', (fan, r(by + 2.54)), (fan, MCU_PIN_Y[pin]), f'U1.{pin}'],
        [p(71.12, 2.54), p(71.12, 10.16), p(50.8, 10.16), p(50.8, 5.08), f'{U}.{pin_n}'],
    ]
    power = [('GND', p(7.62, -5.08), 180), ('GND', p(7.62, 5.08), 0), ('+5V', f'{RO}.1', 0),
             ('GND', f'{RG}.2', 0), ('GND', f'{C}.2', 0), ('GND', f'{D}.1', 0), ('+5V', f'{D}.2', 0)]
    labels = [(net('IN'), p(8.89, 0), 'R'), (net('SH'), p(33.02, 0), 'R'), (net('ADC'), p(73.66, 2.54), 'R')]
    return parts, wires, power, labels


def knob(n):
    """Knob n: RVn divider +5V..GND, wiper (with C3n) wired straight into PA4..PA7."""
    x, y = POT_ORIGIN[n]
    RV, C, pin = f'RV{n}', f'C3{n}', POT_PIN[n]
    parts = [
        part(RV, 'R_Potentiometer', '50k', 'RV09', (x, y), 0, {'3': '+5V', '2': f'POT{n}', '1': 'GND'},
             Note=f'Knob {n} -> PA{3 + n} (Bread Modular MCC knob pin). RV09 9 mm vertical, linear '
                  '(user stock, as audio-out). CW = +5V. Hand-soldered'),
        part(C, 'C', '10n', 'C0603', (r(x + 7.62), r(y + 3.81)), 0, {'1': f'POT{n}', '2': 'GND'}, Voltage='50V',
             Note='ADC hold / noise filter (as 8bit)'),
    ]
    wires = [[f'{RV}.2', (POT_FAN_X[n], y), (POT_FAN_X[n], MCU_PIN_Y[pin]), f'U1.{pin}']]
    power = [('+5V', f'{RV}.3', 0), ('GND', f'{RV}.1', 0), ('GND', f'{C}.2', 0)]
    labels = [(f'POT{n}', (r(x + 10.16), y), 'R')]
    return parts, wires, power, labels


def supply():
    """MCP6002 unit C (supply pins) of U4 and U5, each with its 100n."""
    parts, power = [], []
    for u, ((x, y), cd) in SUPPLY.items():
        parts += [part(u, 'MCP6002-xSN', 'MCP6002', 'SOIC8', (x, y), 0, {'8': '+5V', '4': 'GND'}, unit=3,
                       Note=U_NOTE[u]),
                  part(cd, 'C', '100n', 'C0603', (r(x + 10.16), y), 0, {'1': '+5V', '2': 'GND'}, Voltage='50V',
                       Note=f'{u} decoupling')]
        power += [('+5V', f'{u}.8', 0), ('GND', f'{u}.4', 0), ('+5V', f'{cd}.1', 0), ('GND', f'{cd}.2', 0)]
    return parts, power


def circuit():
    c = []
    # ---- Power: Eurorack +12 V -> series Schottky -> +12V_F -> HT7550-1 -> +5V. -12 V is unused.
    c.append(part('J3', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', pw(35.56, 55.88), 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused). -12 V is not used'))
    c.append(part('D3', 'D_Schottky', 'B5819W', 'SOD123', pw(63.5, 66.04), 180,
                  {'1': '+12V_F', '2': '+12V'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('C5', 'C', '10u', 'C0805', pw(76.2, 69.85), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='25V', Note='+12V_F bulk'))
    c.append(part('U2', 'HT75xx-1-SOT89', 'HT7550-1', 'SOT89', pw(106.68, 68.58), 0,
                  {'1': 'GND', '2': '+12V_F', '3': '+5V'},
                  Note='30 V max input, 100 mA. ~20 mA load: ~0.14 W at 11.6 V in'))
    c.append(part('C4', 'C', '1u', 'C0805', pw(93.98, 69.85), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C3', 'C', '10u', 'C0805', pw(119.38, 69.85), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C2', 'C', '10u', 'C0805', pw(129.54, 69.85), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='+5V bulk'))
    # +5V shunt clamp (as MIDI V2): clamp current from a mis-patched input/output can't pump +5V
    c.append(part('U3', 'TL432DBZ', 'CJ431', 'SOT23', pw(157.48, 76.2), 90,
                  {'1': 'SHUNT_REF', '2': '+5V', '3': 'GND'},
                  Note='+5V shunt clamp, 2.495 V x (1 + R9/R10) = 5.49 V nominal. '
                       'CJ431 SOT-23: 1 REF, 2 K, 3 A (TL432DBZ pinout), as MIDI V2 U2'))
    c.append(part('R9', 'R', '12k', 'R0603', pw(139.7, 69.85), 0,
                  {'1': '+5V', '2': 'SHUNT_REF'}, Note='Shunt divider top'))
    c.append(part('R10', 'R', '10k', 'R0603', pw(139.7, 80.01), 0,
                  {'1': 'SHUNT_REF', '2': 'GND'}, Note='Shunt divider bottom'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, pw(25.4, 58.42), 0, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, pw(71.12, 66.04), 0, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, pw(48.26, 45.72), 0, {'1': '-12V'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, pw(48.26, 66.04), 180, {'1': '+12V'}))

    # ---- MCU and programming
    c.append(part('U1', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', U1_AT, 0, MCU,
                  Note='5 V, 20 MHz as Bread Modular MCC'))
    c.append(part('C1', 'C', '100n', 'C0603', (203.2, 107.95), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U1 decoupling'))
    c.append(part('R5', 'R', '4.7k', 'R0603', (157.48, 110.49), 180,
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular)'))
    c.append(part('J4', 'Conn_01x02', 'UPDI', 'H1x2', (165.1, 96.52), 0,
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power'))

    # ---- Bank selector (Bread Modular MCC): SW1 to GND on PC0 (internal pull-up), LEDs A/B/C
    c.append(part('SW1', 'SW_Push', 'BANK', 'SW6', (210.82, 139.7), 180,
                  {'1': 'GND', '2': 'BANK_SW'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Bank button (as Bread Modular MCC SW1, PC0 internal pull-up): generic 6 x 6 mm THT '
                       'tact, 7 mm tall, Ø3.5 round stem, pins 6.5 x 4.5 mm (as modules/8bit S5). '
                       'Hand-soldered on the F side; pressed through the panel by a printed cap'))
    for i, (bank, y) in enumerate((('A', 157.48), ('B', 167.64), ('C', 177.8))):
        c.append(part(f'R{6 + i}', 'R', '1k', 'R0603', (210.82, y), 90,
                      {'1': f'LED_{bank}', '2': f'LED_{bank}_AN'},
                      Note=f'Bank {bank} LED current (~3 mA). On the MCU side (BM has it on the cathode): '
                           'same current, and the cathode goes straight to the GND pour'))
        c.append(part(f'D{4 + i}', 'LED', 'LED_3mm', 'LED3', (231.14, y), 180,
                      {'2': f'LED_{bank}_AN', '1': 'GND'},
                      Note=f'Bank {bank} LED (Bread Modular D{1 + i}). Hand-soldered 3 mm THT'))

    # ---- MIDI input (TS modular MIDI): the 8bit / MIDI V2 NPN front end with its JP1 bypass
    ox, oy = IX, IY
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (ox + 25.4, oy + 121.92), 0,
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(part('R3', 'R', '100k', 'R0603', (ox + 43.18, oy + 118.11), 180,
                  {'1': 'MIDI_IN', '2': '+5V'},
                  Note='Idle pull-up: no cable turns Q1 on = UART idle'))
    c.append(part('R1', 'R', '10k', 'R0603', (ox + 53.34, oy + 121.92), 90,
                  {'1': 'MIDI_IN', '2': 'Q1_B'},
                  Note='Base resistor: ~1.1 mA at +/-12 V; 0.26 mA from a 3.3 V sender'))
    c.append(part('D1', '1N4148W', '1N4148W', 'SOD123', (ox + 59.69, oy + 125.73), 270,
                  {'1': 'Q1_B', '2': 'GND'},
                  Note='Clamps Q1 B-E to -0.7 V for a negative input (VEBO 6 V)'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23', (ox + 68.58, oy + 121.92), 0,
                  {'1': 'Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting input buffer: input high = RX low. Firmware: PORT_INVEN on PB3'))
    c.append(part('R2', 'R', '22k', 'R0603', (ox + 71.12, oy + 107.95), 180,
                  {'1': 'RX_Q', '2': '+5V'},
                  Note='Q1 collector pull-up, on RX_Q so the JP1 direct path leaves PB3 unloaded'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3', (ox + 86.36, oy + 114.3), 0,
                  {'1': 'RX_Q', '2': 'RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. Solder 1-2 = protected '
                       '(Q1 drives PB3, PORT_INVEN on). Solder 2-3 = direct/unprotected '
                       '(MIDI_IN to PB3, PORT_INVEN off, stock BM MCC firmware). Never both'))

    # ---- MIDI output (TS): the MIDI V2 output clamp (1k + BAT54SW) with its JP2 bypass; 1k is 0.5 W 1206
    mx, my = MX, MY
    c.append(part('JP2', 'SolderJumper_3_Open', 'TX_PROT/DIRECT', 'SJ3', (mx + 7.62, my + 5.08), 0,
                  {'1': 'TX_P', '2': 'TX', '3': 'MIDI_OUT'},
                  Note='Solder jumper, copper only, shipped open. Solder 1-2 = protected '
                       '(PB2 -> clamp -> 1k -> jack). Solder 2-3 = direct (PB2 straight to the jack, as BM MCC). '
                       'Never both'))
    c.append(part('D2', 'BAT54SW', 'BAT54SW', 'SOT323', (mx + 12.7, my - 12.7), 0,
                  {'1': 'GND', '2': '+5V', '3': 'TX_P'},
                  Note='Output clamp to +5V/GND on the GPIO side of R4 (MIDI V2)'))
    c.append(part('R4', 'R', '1k', 'R1206', (mx + 25.4, my - 5.08), 90,
                  {'1': 'TX_P', '2': 'MIDI_OUT'}, Power='0.5W',
                  Note='Output series 1k, 0.5 W 1206 (as 8bit R12): a permanent -12 V on the tip against '
                       'PB2 idling high is ~17 V / 0.29 W (+12 V into the +5V clamp: 45 mW)'))
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (mx + 53.34, my - 5.08), 180,
                  {'T': 'MIDI_OUT', 'S': 'GND', 'TN': None}, Note='MIDI out (TS: tip = 5 V logic-level MIDI)'))

    for n in range(1, CHANNELS + 1):
        c += channel(n)[0] + knob(n)[0]
    c += supply()[0]
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Codes shared with modules/8bit and modules/midi V2 are the same parts; live lookups are
# recorded in docs/sourcing-candidates.json. All R/C are JLCPCB Basic except R4 (0.5 W 1206,
# no Basic exists; the same part as modules/8bit R12 and modules/16bit).
# The THT jacks, pots, LEDs and headers and the THT SW1 are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM Semicon'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '12k', 'R0603'): dict(LCSC='C22790', MPN='0603WAF1202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('R', '510k', 'R0603'): dict(LCSC='C23192', MPN='0603WAF5103T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('C', '1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7550-1', 'SOT89'): dict(LCSC='C16106', MPN='HT7550-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR',
                                                       Manufacturer='Microchip'),
    ('MCP6002-xSN', 'MCP6002', 'SOIC8'): dict(LCSC='C7377', MPN='MCP6002T-I/SN', Manufacturer='Microchip Tech'),
    ('TL432DBZ', 'CJ431', 'SOT23'): dict(LCSC='C3113', MPN='CJ431', Manufacturer='CJ (Jiangsu Changjing)'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
}


# Reference / value text offsets from the symbol origin (centred). Parts not listed: see text_at.
TEXT_AT = {
    'U1': ((15.24, -26.67), (15.24, -24.13)),
    'R5': ((-2.54, -1.27), (-2.54, 1.27), 'left'),
    'U2': ((-5.08, -7.62), (5.08, -7.62)),
    'U3': ((3.81, -3.81), (3.81, -1.27), 'left'),
    'J3': ((1.27, -12.7), (1.27, 12.7)),
    'J4': ((3.81, -1.27), (3.81, 1.27), 'left'),
    'D1': ((2.54, -1.27), (2.54, 1.27), 'left'),
    '#FLG03': ((-5.08, -5.08), (0, -2.54)),
    'SW1': ((0, -3.81), (0, 3.81)),
    'SolderJumper_3_Open': ((0, -6.35), (0, -3.81)),
    'MMBT3904': ((10.16, -1.27), (10.16, 1.27)),
    'BAT54SW': ((0, -6.35), (0, -3.81)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 6.35)),
    'R_Potentiometer': ((-5.08, -1.27), (-5.08, 1.27)),
    'MCP6002-xSN': ((2.54, -10.16), (2.54, -7.62)),
    'LED': ((0, -3.81), (0, 3.81)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '#FLG04': ((0, 5.08), (0, 2.54)),
}

def text_at(p):
    """(reference offset, value offset, justify) from the symbol origin."""
    if p['sym'] == 'MCP6002-xSN' and p['unit'] == 3:     # power unit: right of the pins
        return (1.27, -1.27), (1.27, 1.27), 'left'
    if p['ref'] in TEXT_AT or p['sym'] in TEXT_AT:
        t = TEXT_AT.get(p['ref'], TEXT_AT.get(p['sym']))
        return t if len(t) == 3 else (*t, None)
    if p['sym'] in ('R', 'C') and p['rot'] in (0, 180):      # vertical: right of the body
        # KiCad mirrors the justification with the symbol rotation
        return (2.54, -1.27), (2.54, 1.27), 'left' if p['rot'] == 0 else 'right'
    return (0, -2.54), (0, 2.54), None                      # horizontal: above / below


# Symbols drawn mirrored (only at rotation 0): the pots, so CW (pin 3, the signal) is up and the wiper right.
MIRROR_X = {f'RV{n}' for n in range(1, CHANNELS + 1)}
# Drawn mirrored left-right: U1, so PA4-PA7 (CV) and PB2/PB3 (MIDI) face the blocks on its left.
MIRROR_Y = {'U1'}

# Supply nets are drawn with power symbols (net name = symbol value); every other net
# carries a local label, so all net names are explicit (the routed PCB names them).
RAIL_SYMBOL = {'GND': 'GND', '+5V': '+5V', '+12V': '+12V', '-12V': '-12V', '+12V_F': '+12V'}

# Schematic drawing, block by block. Wires are polylines whose points are (x, y) or
# 'REF.PIN' (that pin's end). Power symbols: (net, point, rotation). Labels: (net, point,
# side the text runs). build() splits wires at every connection point, adds the junction
# dots, checks that nothing dangles and compares the exported netlist with CIRCUIT.
WIRES = [
    # Power entry: J3 pin pairs tied left/right, series Schottky, bulk, HT7550-1, shunt clamp
    ['J3.1', pw(27.94, 50.8), pw(27.94, 45.72), pw(45.72, 45.72), pw(45.72, 50.8), 'J3.2'],
    [pw(45.72, 45.72), pw(53.34, 45.72)],
    ['J3.3', pw(27.94, 53.34), pw(27.94, 58.42), 'J3.7'], ['J3.5', pw(27.94, 55.88)], [pw(27.94, 58.42), pw(22.86, 58.42)],
    ['J3.4', pw(45.72, 53.34), pw(45.72, 58.42), 'J3.8'], ['J3.6', pw(45.72, 55.88)], [pw(45.72, 58.42), pw(48.26, 58.42)],
    ['J3.9', pw(27.94, 60.96), pw(27.94, 66.04), pw(45.72, 66.04), pw(45.72, 60.96), 'J3.10'],
    [pw(45.72, 66.04), 'D3.2'], ['D3.1', 'U2.2'], ['U2.3', 'C2.1'],
    ['C2.1', pw(157.48, 66.04), 'U3.2'], ['R9.2', 'R10.1'], ['U3.1', pw(139.7, 76.2)],
    # MCU, UPDI (PA0 -> R5 -> J4, above U1's left side)
    ['U1.4', (175.26, 104.14), 'C1.1'],
    ['U1.19', (157.48, 116.84), 'R5.1'], ['R5.2', (157.48, 96.52), 'J4.1'], ['J4.2', (160.02, 101.6)],
    # Bank button and LEDs, wired straight from PC0-PC3 (nested jogs, no crossings)
    ['U1.15', 'SW1.2'], ['SW1.1', (218.44, 139.7), (218.44, 142.24)],
    ['U1.16', (198.12, 142.24), (198.12, 157.48), 'R6.1'],
    ['U1.17', (195.58, 144.78), (195.58, 167.64), 'R7.1'],
    ['U1.18', (193.04, 147.32), (193.04, 177.8), 'R8.1'],
    ['D4.2', 'R6.2'], ['D5.2', 'R7.2'], ['D6.2', 'R8.2'],
    ['D4.1', (237.49, 157.48), (237.49, 160.02)], ['D5.1', (237.49, 167.64), (237.49, 170.18)],
    ['D6.1', (237.49, 177.8), (237.49, 180.34)],
    # MIDI in (8bit block); RX climbs to PB3
    ['J1.S', (IX + 33.02, IY + 119.38)], ['J1.T', 'R1.1'],
    [(IX + 46.99, IY + 121.92), (IX + 46.99, IY + 137.16), (IX + 99.06, IY + 137.16), (IX + 99.06, IY + 114.3), 'JP1.3'],
    ['R1.2', 'Q1.1'], ['Q1.3', 'R2.1'], [(IX + 71.12, IY + 114.3), 'JP1.1'],
    ['JP1.2', (IX + 86.36, IY + 121.92), (152.4, IY + 121.92), (152.4, 147.32), 'U1.11'],
    # MIDI out; TX drops from PB2 (crosses the RX wire once, no junction)
    ['JP2.2', (MX + 7.62, MY + 12.7), (147.32, MY + 12.7), (147.32, 144.78), 'U1.12'],
    ['JP2.1', (MX + 2.54, MY - 5.08), 'R4.1'], ['D2.3', (MX + 12.7, MY - 5.08)],
    ['R4.2', 'J2.T'], ['JP2.3', (MX + 33.02, MY + 5.08), (MX + 33.02, MY - 5.08)],
    ['J2.S', (MX + 45.72, MY - 2.54), (MX + 45.72, MY)],
]

POWER = [
    ('-12V', pw(53.34, 45.72), 0), ('GND', pw(22.86, 58.42), 0),
    ('GND', pw(48.26, 58.42), 0), ('+12V', pw(53.34, 66.04), 0), ('+12V_F', pw(86.36, 66.04), 0),
    ('+5V', pw(124.46, 66.04), 0),
    ('GND', 'C5.2', 0), ('GND', 'C4.2', 0), ('GND', 'U2.1', 0), ('GND', 'C3.2', 0), ('GND', 'C2.2', 0),
    ('GND', 'U3.3', 0), ('GND', 'R10.2', 0),
    ('+5V', (175.26, 104.14), 0), ('GND', 'C1.2', 0), ('GND', 'U1.3', 0), ('GND', (160.02, 101.6), 0),
    ('GND', (218.44, 142.24), 0), ('GND', (237.49, 160.02), 0), ('GND', (237.49, 170.18), 0), ('GND', (237.49, 180.34), 0),
    ('GND', (IX + 33.02, IY + 119.38), 90), ('+5V', 'R3.2', 0), ('GND', 'D1.2', 0), ('GND', 'Q1.2', 0),
    ('+5V', 'R2.2', 0),
    ('GND', 'D2.1', 0), ('+5V', 'D2.2', 0), ('GND', (MX + 45.72, MY), 0),
]

LABELS = [
    ('SHUNT_REF', pw(149.86, 76.2), 'U'),
    ('UPDI_PA0', (157.48, 116.84), 'L'), ('UPDI', (157.48, 96.52), 'L'),
    ('BANK_SW', (191.77, 139.7), 'R'),
    ('LED_A', (198.12, 157.48), 'R'), ('LED_B', (195.58, 167.64), 'R'), ('LED_C', (193.04, 177.8), 'R'),
    ('LED_A_AN', (215.9, 157.48), 'R'), ('LED_B_AN', (215.9, 167.64), 'R'), ('LED_C_AN', (215.9, 177.8), 'R'),
    ('MIDI_IN', (IX + 60.96, IY + 137.16), 'R'), ('Q1_B', (IX + 57.15, IY + 121.92), 'R'),
    ('RX_Q', (IX + 73.66, IY + 114.3), 'R'), ('RX', (IX + 91.44, IY + 121.92), 'R'),
    ('TX', (MX - 12.7, MY + 12.7), 'R'), ('TX_P', (MX + 13.97, MY - 5.08), 'R'), ('MIDI_OUT', (MX + 34.29, MY - 5.08), 'R'),
]

for _n in range(1, CHANNELS + 1):
    for _blk in (channel, knob):
        _, _w, _p, _l = _blk(_n)
        WIRES += _w
        POWER += _p
        LABELS += _l
POWER += supply()[1]

TEXTS = [
    ((20.32, 17.78), 'BIG MODULAR MCC - S4 schematic (Bread Modular MCC for Eurorack, 6HP): 4 knobs + 4 CV in -> MIDI CC. '
                     'Circuit intent: docs/research.md', 2.0),
    ((190.5, 30.48), 'POWER: +12V -> B5819W -> +12V_F -> HT7550-1 -> +5V (MCU, op-amps). -12V is not used.\n'
                     'U3 CJ431 shunt clamps +5V at 5.49 V, so clamp current from a mis-patched jack cannot pump the rail.', 1.4),
    ((340.36, 40.64), 'OP-AMP SUPPLY: MCP6002 unit C of U4/U5\non +5V, with C6/C7 100n at each package.', 1.1),
    ((190.5, 87.63), 'PWR_FLAG: #FLG01/#FLG03/#FLG04 mark the Eurorack GND/-12V/+12V entry at J3; #FLG02 marks +12V_F,\n'
                     'fed only through D3, which ERC cannot see through.', 1.1),
    ((246.38, 99.06), 'MCU (U1, drawn mirrored): ATtiny1616 at 5 V. Bread Modular MCC pin map kept:\n'
                      'PA4-PA7 = knobs 1-4 (AI_PIN..AI_PIN+3), PC0 bank button, PC1-PC3 bank LEDs A/B/C,\n'
                      'PB3 MIDI RX, PB2 MIDI TX. New: PB0/PB1/PA2/PA3 = CV 1-4 (ADC0 AIN11/10/2/3).\n'
                      'Knobs and CVs are separate ADC inputs; the firmware decides how they combine.\n'
                      'Spare: PA1, PB4, PB5. UPDI J4: pin 1 UPDI, pin 2 GND; power from Eurorack while programming.', 1.1),
    ((246.38, 124.46), 'CV 1-4 (8bit CV input, one block each): J1n tip -> R1n 56k / R2n 51k to +5V / R3n 510k to GND:\n'
                       '-5.5..+5.5 V -> 0..5 V (Zin 102k; unpatched tip normalled to GND = mid-scale, as 8bit).\n'
                       'D1n BAT54SW clamp, C1n 1n, then a MCP6002 follower on +5V (U4 A/B = CV1/CV2,\n'
                       'U5 A/B = CV3/CV4), so the MCU pin never leaves 0..5 V. CV1/2 -> PB0/PB1, CV3/4 -> PA2/PA3.\n'
                       'KNOBS 1-4: RVn 50k linear divider +5V..GND, wiper + C3n 10n straight into PA4-PA7 (as 8bit).', 1.1),
    ((246.38, 157.48), 'BANK: SW1 to GND on PC0 (internal pull-up); LEDs on PC1-PC3 through 1k\n'
                       '(on the MCU side; BM has it on the cathode).', 1.1),
    ((246.38, 195.58), 'MIDI IN (TS, J1 bottom left): 8bit / MIDI V2 NPN front end (3.3 V and 5 V senders,\n'
                       '+/-12 V tolerant), no opto. JP1 (back, shipped OPEN, bridge one pair):\n'
                       '1-2 = PROTECTED (Q1 drives PB3; firmware PORT_INVEN on PB3),\n'
                       '2-3 = DIRECT (MIDI_IN to PB3, unprotected; stock BM MCC firmware).\n'
                       'Never both; open = PB3 floats.', 1.1),
    ((246.38, 223.52), 'MIDI OUT (TS, J2 bottom right): PB2 -> JP2 -> [D2 clamp, R4 1k] -> J2 tip\n'
                       '(MIDI V2 output protection). JP2 (back, shipped OPEN, bridge one pair):\n'
                       '1-2 = PROTECTED, 2-3 = DIRECT (PB2 to the tip, as BM).\n'
                       'The TX and RX wires cross once without a junction.', 1.1),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/mcc/schematic/' + key))


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


def draw(ends, lib_syms, root):
    """Wires, power symbols, labels and junctions from WIRES / POWER / LABELS.

    Every wire segment is axis-aligned and split at each connection point it passes, so
    all connections are endpoint-to-endpoint. Asserts that nothing dangles: each wire end
    meets another wire end, a pin, a power symbol or a label, and each connected pin is
    reached. The exported netlist is compared with CIRCUIT afterwards (check_netlist)."""
    def at(pt):
        if isinstance(pt, str):
            assert pt in ends, f'unknown or unconnected pin {pt}'
            return ends[pt][:2]
        return (r(pt[0]), r(pt[1]))

    out, segs = [], []
    for line in WIRES:
        pts = [at(pt) for pt in line]
        for a_, b_ in zip(pts, pts[1:]):
            assert a_ != b_ and (a_[0] == b_[0] or a_[1] == b_[1]), f'wire {line}: {a_} -> {b_} not axis-aligned'
            segs.append((a_, b_))
    pin_pts = {v[:2] for v in ends.values()}
    power_pts = {at(pt) for _, pt, _ in POWER}
    label_pts = {at(pt) for _, pt, _ in LABELS}
    anchors = pin_pts | power_pts | label_pts | {e for s_ in segs for e in s_}

    def inside(pt, a_, b_):
        if a_[0] == b_[0] == pt[0]:
            return min(a_[1], b_[1]) < pt[1] < max(a_[1], b_[1])
        if a_[1] == b_[1] == pt[1]:
            return min(a_[0], b_[0]) < pt[0] < max(a_[0], b_[0])
        return False

    split = []
    for a_, b_ in segs:
        cuts = sorted((pt for pt in anchors if inside(pt, a_, b_)),
                      key=lambda pt: abs(pt[0] - a_[0]) + abs(pt[1] - a_[1]))
        chain = [a_] + cuts + [b_]
        split += list(zip(chain, chain[1:]))
    degree = {}
    for a_, b_ in split:
        for e in (a_, b_):
            degree[e] = degree.get(e, 0) + 1
    for e, n in degree.items():
        assert n > 1 or e in pin_pts | power_pts | label_pts, f'dangling wire end at {e}'
    for ref, (x, y, net) in ends.items():
        touching = degree.get((x, y), 0) + ((x, y) in power_pts) + ((x, y) in label_pts)
        others = sum(1 for k, v in ends.items() if k != ref and v[:2] == (x, y))
        assert touching or others, f'pin {ref} ({net}) is not wired'
    for pt in label_pts:
        assert pt in degree or pt in pin_pts, f'label at {pt} touches nothing'
    for pt in power_pts:
        assert pt in degree or pt in pin_pts, f'power symbol at {pt} touches nothing'
    for i, (a_, b_) in enumerate(sorted(set(split))):
        out.append([atom('wire'), [atom('pts'), [atom('xy'), *a_], [atom('xy'), *b_]],
                    [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                    [atom('uuid'), uid(f'wire/{a_}/{b_}')]])
    # Junction dots where three or more wires/pins meet.
    for pt in sorted(set(degree) | pin_pts):
        n = degree.get(pt, 0) + sum(1 for v in ends.values() if v[:2] == pt) + (pt in power_pts)
        if n >= 3:
            out.append([atom('junction'), [atom('at'), *pt], [atom('diameter'), 0],
                        [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'junction/{pt}')]])
    for i, (net, pt, rot) in enumerate(POWER):
        x, y = at(pt)
        sym = RAIL_SYMBOL[net]
        body = (0, -1) if sym == 'GND' else (0, 1)          # library direction pin -> body
        dx, dy = xform(*body, rot)
        # KiCad mirrors the justification of a symbol at 90 degrees (not at 270)
        just = [atom('justify'), atom('left' if (dx > 0) != (rot == 90) else 'right')] if dx else None
        vx, vy = r(x + dx * 3.81), r(y + dy * 3.81)
        ref = f'#PWR{i + 1:03d}'
        effects = [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]
        fa = 90 if rot in (90, 270) else 0
        props = [[atom('property'), 'Reference', ref, [atom('at'), x, y, 0],
                  [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('hide'), atom('yes')]]],
                 [atom('property'), 'Value', net, [atom('at'), vx, vy, fa], effects + ([just] if just else [])]]
        for name in ('Footprint', 'Datasheet', 'Description'):
            props.append([atom('property'), name, '', [atom('at'), x, y, 0],
                          [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('hide'), atom('yes')]]])
        out.append([atom('symbol'), [atom('lib_id'), f'{LIB}:{sym}'], [atom('at'), x, y, rot], [atom('unit'), 1],
                    [atom('exclude_from_sim'), atom('no')], [atom('in_bom'), atom('no')], [atom('on_board'), atom('no')],
                    [atom('in_pos_files'), atom('no')], [atom('dnp'), atom('no')], [atom('uuid'), uid(f'pwr/{i}')],
                    *props, [atom('pin'), '1', [atom('uuid'), uid(f'pwr/{i}/pin')]],
                    [atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), ref], [atom('unit'), 1]]]]])
    for i, (net, pt, side) in enumerate(LABELS):
        x, y = at(pt)
        lang, just = {'R': (0, 'left'), 'L': (180, 'right'), 'U': (90, 'left'), 'D': (270, 'right')}[side]
        out.append([atom('label'), net, [atom('at'), x, y, lang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                     [atom('justify'), atom(just), atom('bottom')]],
                    [atom('uuid'), uid(f'label/{i}')]])
    return out


def check_netlist(sch, nets, no_connects):
    """The native netlist must equal CIRCUIT exactly: same net names, same pins."""
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
    assert not bad, 'netlist differs from CIRCUIT (net: got, want):\n' + '\n'.join(
        f'  {k}: {v}' for k, v in sorted(bad.items()))


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
    (HW / f'{LIB}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") '
        '(options "") (descr "mcc pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - MCC") (rev {q(REV)}) (company "Big Modular")
        (comment 1 "SCHEMATIC S4 - BM MCC for Eurorack: 4 knobs + 4 CV in -> MIDI CC")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIB}:' + k
        embedded.append(s)

    items, nets, ends = [], {}, {}
    units = {}
    for p in circuit():
        sym = lib_syms[p['sym']]
        pins = pin_table(sym, p['unit'])
        assert set(p['pins']) == set(pins), (p['ref'], p['unit'], sorted(pins), sorted(p['pins']))
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
        fang = 90 if p['rot'] in (90, 270) else 0
        ukey = p['ref'] if p['unit'] == 1 else f"{p['ref']}/{p['unit']}"
        node = [atom('symbol'), [atom('lib_id'), f'{LIB}:' + p['sym']], [atom('at'), x, y, p['rot']],
                *([[atom('mirror'), atom('x')]] if p['ref'] in MIRROR_X else []),
                *([[atom('mirror'), atom('y')]] if p['ref'] in MIRROR_Y else []),
                [atom('unit'), p['unit']], [atom('exclude_from_sim'), atom('no')],
                [atom('in_bom'), atom('yes' if assembled else 'no')],
                [atom('on_board'), atom('no' if is_flag else 'yes')],
                [atom('in_pos_files'), atom('yes' if assembled else 'no')], [atom('dnp'), atom('no')],
                [atom('uuid'), uid('sym/' + ukey)]]
        for name, value, (px, py), hide, *jst in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), fang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if jst and jst[0]:
                prop[-1].append([atom('justify'), atom(jst[0])])
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        # KiCad lists every pin of the symbol on each placed unit: give them all stable UUIDs.
        all_pins = set().union(*(pin_table(sym, u) for u in range(1, 10)))
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{ukey}/{n}")]] for n in sorted(all_pins)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), p['unit']]]]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(-px if p['ref'] in MIRROR_Y else px, -py if p['ref'] in MIRROR_X else py, p['rot'])
            ex, ey = r(x + ox), r(y + oy)
            key = f"{p['ref']}/{n}"
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                continue
            nets.setdefault(net, []).append(key)
            ends[f"{p['ref']}.{n}"] = (ex, ey, net)
    multi = {ref: u for ref, u in units.items() if len(u) > 1}
    assert multi == {'U4': {1, 2, 3}, 'U5': {1, 2, 3}}, multi
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    items += draw(ends, lib_syms, root)
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
    check_netlist(out, nets, {f"{p['ref']}/{n}" for p in circuit() for n, net in p['pins'].items()
                              if net is None})
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbols in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    print(out, f'{len(nets)} nets')


if __name__ == '__main__':
    build()
