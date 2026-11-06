"""Generate the 12bit S2 schematic (hardware/12bit.kicad_sch) and its pinned symbols.

Run from modules/12bit:
  python3 -B tools/build_schematic.py

Writes hardware/12BIT.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the 12BIT library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. circuit() is the circuit
of docs/research.md section 3: modules/8bit moved from the ATtiny1616 (low stock) to an
STM32G071C8T6 with its two 12-bit DAC channels, on a 6HP module: the 8bit MIDI input
(JP1 bypass) and bipolar CV input at 3.3 V, three 50k knobs read by the ADC (knob 3 no
longer the passive low-pass), the 8bit MODE switch + LED and two DC-coupled +/-5 V
outputs (TL074). S2 (user, 2026-11-06): the S1 gate output is removed; its TL074 section is
a grounded follower.

Placement (LAYOUT) is by hand. Signal wires are found by route_wires() (as modules/hats):
a small grid router (1.27 mm) that draws every signal net as axis-aligned wires, never
touching a pin, stub, symbol body or wire end of another net (perpendicular crossings
without a junction are allowed). LABEL_NETS are the only signal nets joined by name
labels. Supply pins get a stub and a stock power symbol. The build exports the native
netlist and fails unless it equals circuit().
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
PROJECT = '12bit'
LIB = '12BIT'
STUB = 2.54

FILTER_EDITS = {
    'Conn_01x05': '*_1x??_*',
    'Conn_02x05_Odd_Even': '*_2x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LED': ('Device', 'LED'),
    'FerriteBead': ('Device', 'FerriteBead'),
    'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    # KiCad 10 ships no STM32G071CxT (LQFP-48) symbol. STM32G081CBTx is the same STM32G0x1
    # LQFP-48 die and pinout (G081 = G071 + AES); it is copied and renamed (RENAME below).
    'STM32G071C8Tx': ('MCU_ST_STM32G0', 'STM32G081CBTx'),
    'HT75xx-1-SOT89': ('Regulator_Linear', 'HT75xx-1-SOT89'),
    'TL074': ('Amplifier_Operational', 'TL074'),
    'MCP6001-OT': ('Amplifier_Operational', 'MCP6001-OT'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_01x05': ('Connector_Generic', 'Conn_01x05'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'SW_Push': ('Switch', 'SW_Push'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'MMBT3904': ('Transistor_BJT', 'MMBT3904'),
    '1N4148W': ('Diode', '1N4148W'),
    'BAT54SW': ('Diode', 'BAT54SW'),
    'GND': ('power', 'GND'), '+3V3': ('power', '+3V3'), '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
}

# Library key != stock name: the copy gets the key as its name and these properties.
RENAME = {
    'STM32G071C8Tx': {
        'Value': 'STM32G071C8Tx',
        'Datasheet': 'https://www.st.com/resource/en/datasheet/stm32g071c8.pdf',
        'Description': 'STMicroelectronics Arm Cortex-M0+ MCU, 64KB flash, 36KB RAM, 64 MHz, 1.7-3.6V, '
                       '44 GPIO, 2 x 12-bit DAC, LQFP48 (stock STM32G081CBTx body/pins: same STM32G0x1 LQFP-48 pinout)',
    },
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric', 'L0603': 'L_0603_1608Metric',
    'SOD123': 'D_SOD-123', 'SOT23': 'SOT-23', 'SOT23-5': 'SOT-23-5', 'SOT323': 'SOT-323_SC-70',
    'SOT89': 'SOT-89-3', 'LQFP48': 'LQFP-48_7x7mm_P0.5mm', 'SOIC14': 'SOIC-14_3.9x8.7mm_P1.27mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'H1x5': 'PinHeader_1x05_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
    'LED3': 'LED_D3.0mm', 'SW6': 'SW_PUSH_6mm_H7.3mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# Supply nets are drawn with power symbols (net name = symbol value).
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Signal nets joined by name labels instead of wires (none planned; the router adds any it
# cannot draw and the build then fails, so the list stays explicit).
LABEL_NETS = set()

# STM32G071C8T6 LQFP-48 pin numbers (DS12232 / stock STM32G0x1 LQFP-48 symbol).
#  DAC1_OUT1 PA4 / DAC1_OUT2 PA5 -> OUT 1 / OUT 2 (the two 12-bit audio channels)
#  ADC: PA0 (IN0) CV, PA1 (IN1) knob 1, PA6 (IN6) knob 2, PA7 (IN7) knob 3
#  USART1_RX PB7 (AF0) MIDI in: not PA10, whose UCPD1 dead-battery pull-down (DBCC2) is on
#  at reset. RX polarity is a USART setting (CR2.RXINV) for JP1 = protected.
#  PB4 MODE button (internal pull-up), PB5 LED (TIM3_CH2 PWM)
#  PA13 SWDIO / PA14 SWCLK (J6), PF2 NRST. VBAT tied to +3V3 (no battery). VREF+ from
#  +3V3 through FB1 (DAC/ADC reference = VDDA rail, ratiometric with the knobs and VOFF).
#  No crystal: HSI16 (+/-1 %) clocks the 31.25 kbaud MIDI UART and the sample timer.
MCU_PINS = {'4': '+3V3', '5': 'VREFP', '6': '+3V3', '7': 'GND', '10': 'NRST',
            '11': 'CV_ADC', '12': 'POT1', '15': 'DAC1', '16': 'DAC2', '17': 'POT2', '18': 'POT3',
            '35': 'SWDIO', '36': 'SWCLK', '43': 'BUTTON', '44': 'LED_DRV', '46': 'MIDI_RX'}
MCU = {str(n): MCU_PINS.get(str(n)) for n in range(1, 49)}

GRID = 2.54
OFFSET = (4, 4)  # LAYOUT / TEXTS origin inside the A2 frame, grid units
DEBUG_PLACEMENT = bool(__import__('os').environ.get('B12_PLACEMENT_ONLY'))


def part(ref, sym, value, fp, pins, unit=1, **fields):
    key = ref if unit == 1 else f'{ref}.{unit}'
    x, y, rot, *mirror = LAYOUT[key]
    x, y = x + OFFSET[0], y + OFFSET[1]
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=(round(x * GRID, 2), round(y * GRID, 2)), rot=rot,
                mirror=bool(mirror), pins=pins, unit=unit, fields=fields)


# Symbol placement in 2.54 mm grid units: ref (unit 1) or ref.unit -> (x, y, rotation[, 'mirror']).
# Centre: the MCU U3 (PA/PB pins on its right). Left: CV input (top), VREF / NRST, MIDI input
# (bottom). Right: knobs (top), SWD, OUT 1 / OUT 2 / VOFF output stages, the spare U4D, MODE
# button and LED. Bottom: power entry and the supply units with their decoupling.
LAYOUT = {
    # CV input (8bit S4 / 16bit D5 at 3.3 V)
    'J2': (6, 26, 0), 'R4': (14.5, 26, 90), 'R5': (19, 20.5, 0), 'R6': (23, 30.5, 0),
    'D5': (28, 19, 0), 'C5': (32, 30.5, 0), 'U2': (42, 27, 0),
    # MCU, VREF+ filter, NRST, decoupling
    'U3': (70, 62, 0), 'FB1': (54, 40.5, 0), 'C10': (50, 44.5, 0), 'C11': (46, 44.5, 0),
    'C14': (52, 54.5, 0), 'C12': (77, 40.5, 0), 'C13': (81, 40.5, 0),
    # SWD header (right of the MCU, beside PA13/PA14)
    'J6': (90, 61, 0),
    # Knobs 1-3: +3V3 dividers, wiper caps
    'RV1': (98, 21, 180), 'C7': (94, 24.5, 0), 'RV2': (110, 21, 180), 'C8': (106, 24.5, 0),
    'RV3': (122, 21, 180), 'C9': (118, 24.5, 0),
    # OUT 1: R8 + C15 smoothing -> U4A x3.4 with -2.4 x VOFF -> R16 -> J3
    'R8': (100.5, 41, 90), 'C15': (104, 44.5, 0), 'U4': (114, 42, 0), 'R10': (114.5, 37, 90),
    'R11': (108, 47.5, 0), 'R16': (124.5, 42, 90), 'J3': (134, 42, 0, 'mirror'),
    # OUT 2
    'R9': (100.5, 55, 90), 'C16': (104, 58.5, 0), 'U4.2': (114, 56, 0), 'R12': (114.5, 51, 90),
    'R13': (108, 61.5, 0), 'R17': (124.5, 56, 90), 'J4': (134, 56, 0, 'mirror'),
    # VOFF reference: R14 / R15 divider + C17, U4C follower
    'R14': (100, 66.5, 0), 'R15': (100, 72.5, 0), 'C17': (104, 72.5, 0), 'U4.3': (114, 70, 0),
    # Spare U4D: grounded follower
    'U4.4': (114, 84, 0),
    # MODE button and LED
    'SW1': (94, 92, 0), 'R7': (91.5, 98, 90), 'D1': (98, 98, 180),
    # MIDI input (as modules/hats / modules/low)
    'J1': (6, 94, 0), 'R1': (12, 92.5, 180), 'R2': (16.5, 94, 90), 'D4': (20, 96.5, 270),
    'Q1': (23, 94, 0), 'R3': (24, 88.5, 180), 'JP1': (33, 90, 0),
    # Power entry
    'J5': (9, 117, 0), 'D2': (21, 114, 180), 'D3': (21, 122, 0), 'C1': (28, 116.5, 0), 'C2': (32, 116.5, 0),
    'U1': (40, 115, 0), 'C3': (47, 116.5, 0), 'C4': (51, 116.5, 0),
    '#FLG01': (6, 128, 0), '#FLG02': (12, 128, 0), '#FLG03': (18, 128, 0), '#FLG04': (24, 128, 0),
    '#FLG05': (30, 128, 0),
    # Op-amp supply unit and decoupling
    'C6': (60, 116.5, 0), 'U4.5': (70, 115, 0), 'C18': (74, 115.5, 0), 'C19': (78, 115.5, 0),
}

# Hand-drawn polylines for nets the router should not choose itself ('REF/pin' pin ends and
# (x, y) grid points). Everything else is routed.
WIRES = {
    # VBAT (pin 4) joins the VDD (pin 6) supply stub: one +3V3 symbol for both top pins.
    '+3V3': [['U3/4', (74, 46), (75, 46)]],
}

LABEL_AT = {}


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7533-1 -> +3V3 (as modules/hats)
    c.append(part('J5', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5',
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header on B, upright at the right edge, pin 1 (-12 V) at the bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang upward, unused)'))
    c.append(part('D2', 'D_Schottky', 'B5819W', 'SOD123',
                  {'1': '+12V_F', '2': '+12V'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D3', 'D_Schottky', 'B5819W', 'SOD123',
                  {'1': '-12V', '2': '-12V_F'}, Note='-12 V series reverse-polarity protection'))
    c.append(part('C1', 'C', '10u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='25V', Note='+12V_F bulk'))
    c.append(part('C2', 'C', '10u', 'C0805',
                  {'1': 'GND', '2': '-12V_F'}, Voltage='25V', Note='-12V_F bulk'))
    c.append(part('U1', 'HT75xx-1-SOT89', 'HT7533-1', 'SOT89',
                  {'1': 'GND', '2': '+12V_F', '3': '+3V3'},
                  Note='3.3 V LDO (as modules/hats), 100 mA. Load ~20 mA (MCU ~8 mA at 64 MHz, DAC, LED, '
                       'MCP6001, knobs): ~0.17 W at 11.7 V in'))
    c.append(part('C3', 'C', '1u', 'C0805',
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805',
                  {'1': '+3V3', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, {'1': '+12V'}))

    # ---- MIDI input (TS modular MIDI): the 8bit / MIDI V2 NPN front end with its JP1 bypass, at 3.3 V
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(part('R1', 'R', '100k', 'R0603',
                  {'1': 'MIDI_IN', '2': '+3V3'}, Note='Idle pull-up: no cable turns Q1 on = UART idle'))
    c.append(part('R2', 'R', '10k', 'R0603',
                  {'1': 'MIDI_IN', '2': 'Q1_B'},
                  Note='Base resistor: ~1.1 mA at +/-12 V; 0.26 mA from a 3.3 V sender'))
    c.append(part('D4', '1N4148W', '1N4148W', 'SOD123',
                  {'1': 'Q1_B', '2': 'GND'},
                  Note='Clamps Q1 B-E to -0.7 V for a negative input (VEBO 6 V)'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23',
                  {'1': 'Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting input buffer: input high = RX low. Firmware: USART1 CR2.RXINV = 1 for JP1 = P'))
    c.append(part('R3', 'R', '22k', 'R0603',
                  {'1': 'RX_Q', '2': '+3V3'},
                  Note='Q1 collector pull-up, on RX_Q so the JP1 direct path leaves PB7 unloaded'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3',
                  {'1': 'RX_Q', '2': 'MIDI_RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. Solder 1-2 = protected '
                       '(Q1 drives PB7, firmware RXINV = 1). Solder 2-3 = direct/unprotected '
                       '(MIDI_IN to PB7, RXINV = 0). Never both'))

    # ---- CV input: 8bit S4 topology at 3.3 V (16bit D5 values): R4 100k in, R5 56k to +3V3,
    # R6 120k to GND map -5.9..+6.0 V onto 0..3.3 V (Zin 138k), BAT54SW clamp, 1n, MCP6001 follower
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M',
                  {'T': 'CV_IN', 'S': 'GND', 'TN': 'GND'},
                  Note='CV in, -5.9..+6.0 V. Tip normalled to GND: unpatched reads mid-scale (0 V)'))
    c.append(part('R4', 'R', '100k', 'R0603', {'1': 'CV_IN', '2': 'CV_BUF'},
                  Note='Level-shift input R. Input impedance R4 + R5||R6 = 138k. Clamp current <= 0.1 mA at +/-12 V'))
    c.append(part('R5', 'R', '56k', 'R0603', {'1': '+3V3', '2': 'CV_BUF'},
                  Note='Level-shift offset: 0 V CV -> 1.63 V (mid-scale). +3V3 is also the ADC reference (VREF+)'))
    c.append(part('R6', 'R', '120k', 'R0603', {'1': 'CV_BUF', '2': 'GND'},
                  Note='Level-shift trim: gain 0.276, -5.9 V -> 0 V, +6.05 V -> 3.3 V'))
    c.append(part('D5', 'BAT54SW', 'BAT54SW', 'SOT323', {'1': 'GND', '2': '+3V3', '3': 'CV_BUF'},
                  Note='CV clamp: holds the U2 input within -0.3..+3.6 V'))
    c.append(part('C5', 'C', '1n', 'C0603', {'1': 'CV_BUF', '2': 'GND'}, Voltage='50V',
                  Note='With R4||R5||R6 (27.6k): 5.8 kHz CV low-pass'))
    c.append(part('U2', 'MCP6001-OT', 'MCP6001', 'SOT23-5',
                  {'3': 'CV_BUF', '4': 'CV_ADC', '1': 'CV_ADC', '2': 'GND', '5': '+3V3'},
                  Note='CV buffer: unity follower, rail-to-rail on +3V3, so PA0 only ever sees 0..3.3 V (as modules/8bit U4)'))
    c.append(part('C6', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V', Note='U2 decoupling'))

    # ---- MCU
    c.append(part('U3', 'STM32G071C8Tx', 'STM32G071C8T6', 'LQFP48', MCU,
                  Note='3.3 V, HSI16 (no crystal). DAC1_OUT1 PA4 / DAC1_OUT2 PA5 = OUT 1 / OUT 2; '
                       'ADC PA0 CV, PA1/PA6/PA7 knobs; USART1_RX PB7 MIDI; PB4 button; PB5 LED; SWD'))
    c.append(part('C12', 'C', '100n', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='50V',
                  Note='U3 VDD/VDDA decoupling (pin 6)'))
    c.append(part('C13', 'C', '4.7u', 'C0603', {'1': '+3V3', '2': 'GND'}, Voltage='16V',
                  Note='U3 VDD bulk (ST: 4.7 uF + 100 nF per VDD pin)'))
    c.append(part('FB1', 'FerriteBead', '600R@100MHz', 'L0603', {'1': '+3V3', '2': 'VREFP'},
                  Note='VREF+ filter from +3V3 (DCR ~0.45 R: <0.5 mV at the DAC reference current)'))
    c.append(part('C10', 'C', '1u', 'C0805', {'1': 'VREFP', '2': 'GND'}, Voltage='50V',
                  Note='VREF+ decoupling (ST: 1 uF + 100 nF)'))
    c.append(part('C11', 'C', '100n', 'C0603', {'1': 'VREFP', '2': 'GND'}, Voltage='50V',
                  Note='VREF+ decoupling at pin 5'))
    c.append(part('C14', 'C', '100n', 'C0603', {'1': 'NRST', '2': 'GND'}, Voltage='50V',
                  Note='NRST filter (ST recommendation)'))
    c.append(part('J6', 'Conn_01x05', 'SWD', 'H1x5',
                  {'1': '+3V3', '2': 'SWDIO', '3': 'SWCLK', '4': 'GND', '5': 'NRST'},
                  Note='SWD for an ST-Link: 1 +3V3 (VTref sense: program with the module on Eurorack power), '
                       '2 SWDIO, 3 SWCLK, 4 GND (pins 1-4 as modules/usb-audio J8), 5 NRST. Hand-soldered, B side'))

    # ---- Knobs 1-3: 50k linear +3V3..GND dividers into ADC pins, 10n at each wiper.
    # Knob 3 is a plain ADC knob (modules/8bit used it as the passive low-pass).
    for i, (rv, cap) in enumerate((('RV1', 'C7'), ('RV2', 'C8'), ('RV3', 'C9')), 1):
        c.append(part(rv, 'R_Potentiometer', '50k', 'RV09',
                      {'1': 'GND', '2': f'POT{i}', '3': '+3V3'},
                      Note=f'Knob P{i}: RV09 9 mm vertical, linear (user stock). CW = +3V3. Hand-soldered'))
        c.append(part(cap, 'C', '10n', 'C0603', {'1': f'POT{i}', '2': 'GND'}, Voltage='50V',
                      Note='ADC hold / noise filter'))

    # ---- Outputs: U4 TL074 on +/-12 V. A/B: OUT 1 / OUT 2 from DAC1_OUT1 / DAC1_OUT2, non-inverting
    # x3.4 with -2.4 x VOFF: buffered DAC 0.2..3.1 V -> -4.9..+4.9 V (0..3.3 V unbuffered -> -5.6..+5.6 V),
    # DC coupled (audio, CV, LFO). C: VOFF follower. D: spare (the S1 gate is removed), grounded follower.
    uo = ('+/-12 V. A: OUT 1 (DAC1_OUT1) x3.4; B: OUT 2 (DAC1_OUT2) x3.4; C: VOFF follower (2.33 V); '
          'D: spare, grounded follower')
    for n, (u, rs, cs, rf, rg, ro, j) in enumerate((('U4', 'R8', 'C15', 'R10', 'R11', 'R16', 'J3'),
                                                    ('U4', 'R9', 'C16', 'R12', 'R13', 'R17', 'J4')), 1):
        pins = {1: ('3', '2', '1'), 2: ('5', '6', '7')}[n]
        c.append(part(rs, 'R', '1k', 'R0603', {'1': f'DAC{n}', '2': f'DAC{n}_F'},
                      Note=f'DAC{n} series R: with C{14 + n} smooths the DAC steps at 34 kHz (above audio, '
                           'not a tone filter)'))
        c.append(part(cs, 'C', '4.7n', 'C0603', {'1': f'DAC{n}_F', '2': 'GND'}, Voltage='50V',
                      Note='DAC step smoothing: 1k / 4.7n = 34 kHz'))
        c.append(part(u, 'TL074', 'TL074', 'SOIC14',
                      {pins[0]: f'DAC{n}_F', pins[1]: f'OUT{n}_FB', pins[2]: f'OUT{n}_AMP'}, unit=n, Note=uo))
        c.append(part(rf, 'R', '24k', 'R0603', {'1': f'OUT{n}_FB', '2': f'OUT{n}_AMP'},
                      Note='Rf: gain 1 + 24k / 10k = 3.4'))
        c.append(part(rg, 'R', '10k', 'R0603', {'1': f'OUT{n}_FB', '2': 'VOFF'}, Note='Rg to the offset reference'))
        c.append(part(ro, 'R', '1k', 'R1206', {'1': f'OUT{n}_AMP', '2': f'OUT{n}'}, Power='0.5W',
                      Note='Output series: short / +/-12 V mis-patch current limit; 0.5 W for a permanent '
                           'mis-patch (as modules/8bit R12)'))
        c.append(part(j, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', {'T': f'OUT{n}', 'S': 'GND', 'TN': None},
                      Note=f'OUT {n}, Eurorack level (~10 Vpp), DC coupled'))
    c.append(part('R14', 'R', '10k', 'R0603', {'1': '+3V3', '2': 'VOFF_DIV'}, Note='Offset divider top'))
    c.append(part('R15', 'R', '24k', 'R0603', {'1': 'VOFF_DIV', '2': 'GND'},
                  Note='Offset divider bottom: 2.33 V = DAC mid-scale 1.64 V x 3.4 / 2.4'))
    c.append(part('C17', 'C', '10u', 'C0805', {'1': 'VOFF_DIV', '2': 'GND'}, Voltage='25V',
                  Note='Filters +3V3 noise off the offset (2.3 Hz)'))
    c.append(part('U4', 'TL074', 'TL074', 'SOIC14', {'10': 'VOFF_DIV', '9': 'VOFF', '8': 'VOFF'}, unit=3, Note=uo))
    c.append(part('U4', 'TL074', 'TL074', 'SOIC14', {'12': 'GND', '13': 'U4D_OUT', '14': 'U4D_OUT'},
                  unit=4, Note=uo))
    c.append(part('U4', 'TL074', 'TL074', 'SOIC14', {'4': '+12V_F', '11': '-12V_F'}, unit=5, Note=uo))
    c.append(part('C18', 'C', '100n', 'C0603', {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U4 V+ decoupling'))
    c.append(part('C19', 'C', '100n', 'C0603', {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U4 V- decoupling'))

    # ---- MODE button and LED (modules/8bit SW1 / D1)
    c.append(part('SW1', 'SW_Push', 'MODE', 'SW6', {'1': 'BUTTON', '2': 'GND'},
                  MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Mode button on PB4 (internal pull-up): generic 6 x 6 mm THT tact, 7 mm tall, as modules/8bit '
                       'SW1, pressed through the panel by the 8bit printed cap'))
    c.append(part('R7', 'R', '1k', 'R0603', {'1': 'LED_DRV', '2': 'LED_A'}, Note='Mode LED current (~1.4 mA)'))
    c.append(part('D1', 'LED', 'LED_3mm_red', 'LED3', {'2': 'LED_A', '1': 'GND'},
                  Note='Mode LED on PB5 (TIM3_CH2 PWM = brightness). Hand-soldered 3 mm THT (as modules/8bit D1)'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts. Codes reused from modules/8bit, modules/16bit and modules/hats; every code was
# looked up live (strict) on 2026-11-06 (docs/sourcing-candidates.json). Stock is a dated
# observation, not a guarantee. THT parts carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '24k', 'R0603'): dict(LCSC='C23352', MPN='0603WAF2402T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '120k', 'R0603'): dict(LCSC='C25808', MPN='0603WAF1203T5E', Manufacturer='UNI-ROYAL'),
    ('C', '1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung'),
    ('C', '4.7n', 'C0603'): dict(LCSC='C53987', MPN='0603B472K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '4.7u', 'C0603'): dict(LCSC='C19666', MPN='CL10A475KO8NNNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('FerriteBead', '600R@100MHz', 'L0603'): dict(LCSC='C1002', MPN='GZ1608D601TF', Manufacturer='Sunlord'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7533-1', 'SOT89'): dict(LCSC='C14289', MPN='HT7533-1', Manufacturer='Holtek'),
    ('MCP6001-OT', 'MCP6001', 'SOT23-5'): dict(LCSC='C29429', MPN='MCP6001T-E/OT', Manufacturer='Microchip'),
    ('TL074', 'TL074', 'SOIC14'): dict(LCSC='C12594', MPN='TL074CDR', Manufacturer='Texas Instruments'),
    ('STM32G071C8Tx', 'STM32G071C8T6', 'LQFP48'): dict(LCSC='C529341', MPN='STM32G071C8T6',
                                                       Manufacturer='STMicroelectronics'),
}


def T(x, y):
    return (round((x + OFFSET[0]) * GRID, 2), round((y + OFFSET[1]) * GRID, 2))


# Block notes: (grid position, text, size). route_wires() keeps wires out of their boxes.
TEXTS = [
    (T(2, 2), 'BIG MODULAR 12BIT - S2 schematic: modules/8bit on an STM32G071C8T6 (two 12-bit DAC channels), 6HP. '
              'Circuit intent: docs/research.md', 2.0),
    (T(2, 5), 'Signal nets are wired; supplies use power symbols.', 1.27),
    (T(2, 9), 'CV IN: R4/R5/R6 level shift (-5.9..+6.0 V -> 0..3.3 V, Zin 138k), D5 clamp, C5 -> U2 MCP6001 follower -> PA0.', 1.27),
    (T(44, 33), 'MCU U3 STM32G071C8T6 at 3.3 V, HSI16, no crystal.\n'
                'VREF+ = +3V3 through FB1 (ADC/DAC reference).\n'
                'J6 SWD: 1 +3V3 sense, 2 SWDIO, 3 SWCLK, 4 GND, 5 NRST.', 1.27),
    (T(90, 11), 'KNOBS P1/P2/P3: 50k linear +3V3 dividers -> PA1 / PA6 / PA7 (knob 3 is no longer the low-pass).', 1.27),
    (T(96, 31), 'OUT 1 / OUT 2: DAC1_OUT1 (PA4) / DAC1_OUT2 (PA5) -> 1k/4.7n (34 kHz step smoothing) -> TL074 x3.4 - 2.4 x VOFF\n'
                '(buffered DAC 0.2..3.1 V -> +/-4.9 V), 1k 0.5 W to the jack. DC coupled: audio, CV or LFO.', 1.27),
    (T(104, 79.5), 'U4D spare: + to GND, output to - (grounded follower).', 1.27),
    (T(86, 103), 'MODE: SW1 to GND on PB4 (pull-up); LED on PB5 (PWM) via R7 1k.', 1.27),
    (T(2, 82), 'MIDI IN (TS): 8bit NPN front end, pull-ups on +3V3. JP1 shipped OPEN:\n'
               '1-2 = protected (USART1 RXINV = 1), 2-3 = direct.', 1.27),
    (T(2, 108), 'POWER: +12V -> D2 -> +12V_F (U4, U1 HT7533-1 -> +3V3); -12V -> D3 -> -12V_F (U4).', 1.27),
    (T(58, 108), 'SUPPLY PINS + DECOUPLING', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/12bit/schematic/' + key))


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
        return (0, -4.45), (0, -2.54), None
    if sym == 'TL074':
        return ((-3.81, -0.635), (-3.81, 1.27), 'right') if unit == 5 else ((0, -7.62), (0, -5.715), None)
    if sym == 'MCP6001-OT':  # top right: the V+ pin and its +3V3 stub sit above the body centre
        return (2.54, -5.08), (2.54, -3.175), 'left'
    if sym == 'STM32G071C8Tx':
        return (10.16, 51.435), (10.16, 53.34), 'left'
    if sym == 'FerriteBead':
        return right
    if sym in ('AudioJack2_SwitchT', 'Conn_02x05_Odd_Even'):
        return (0, -8.89), (0, 8.89), None
    if sym == 'Conn_01x05':
        return (0, -8.89), (0, 8.89), None
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
        if key in RENAME:  # stock body/pins under this module's name (recorded as an edit)
            old = sym[1]
            sym[1] = key
            for u in nodes(sym, 'symbol'):
                u[1] = u[1].replace(old, key, 1)
            for pp in nodes(sym, 'property'):
                if pp[1] in RENAME[key]:
                    pp[2] = RENAME[key][pp[1]]
            edit = (edit + '; ' if edit else '') + f'renamed {old} -> {key}; ' + ', '.join(
                f'{k} -> {v!r}' for k, v in RENAME[key].items())
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
        '(options "") (descr "12BIT pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A2")
      (title_block (title "Big Modular - 12bit") (rev "S2") (company "Big Modular")
        (comment 1 "SCHEMATIC S2 - modules/8bit on an STM32G071C8T6: MIDI + CV in, 3 knobs, MODE, 2 x 12-bit DAC outs")
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
                continue  # stacked pins of one symbol: one stub serves both
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
                if other == net:  # a drawn rail wire may end on its own rail's stub (WIRES '+3V3')
                    continue
                assert not on_segment(pt, a, b, ends=True), f'{net} wire {a}-{b} touches {key} ({other}) at {pt}'
        for i, (a, b) in enumerate(segs):
            items.append([atom('wire'), [atom('pts'), [atom('xy'), *a], [atom('xy'), *b]],
                          [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                          [atom('uuid'), uid(f'net/{net}/{i}')]])
        if net in RAIL_SYMBOL:  # rails are named by their power symbols
            continue
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
    assert multi == {'U4': {1, 2, 3, 4, 5}}, multi
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
