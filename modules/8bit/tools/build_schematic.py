"""Generate the 8bit S5 schematic (hardware/8bit.kicad_sch) and its pinned symbols.

Run from modules/8bit:
  python3 -B tools/build_schematic.py

Writes hardware/8BIT.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the 8BIT library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. CIRCUIT below is the
circuit of docs/research.md section 3: Bread Modular 8bit (ATtiny1616, DAC on PA6,
knobs on PA1/PA2, mode button PA4, LED PA5, MIDI RX on PB3) moved to Eurorack with
the MIDI V2 protected input (JP1 bypass), a protected CV input, a passive
low-pass on knob 3 (as Bread Modular) and a +/-12 V output stage.
Every pin gets a short stub and a local net label (as modules/midi), so connectivity
is explicit by name. Multi-unit symbols (the TL072) get one placed unit per entry.

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
PROJECT = '8bit'
LIB = '8BIT'
STUB = 2.54

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the 8BIT library, so the copies
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
    'TL072': ('Amplifier_Operational', 'TL072'),
    'MCP6001-OT': ('Amplifier_Operational', 'MCP6001-OT'),
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
    'SOD123': 'D_SOD-123', 'LED3': 'LED_D3.0mm', 'SOT23': 'SOT-23', 'SOT23-5': 'SOT-23-5', 'SOT323': 'SOT-323_SC-70',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'SOT89': 'SOT-89-3', 'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'RV09': 'Potentiometer_RV09', 'SW6': 'SW_PUSH_6mm_H7.3mm',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# ATtiny1616-M (VQFN-20) pin numbers. Bread Modular 8bit pins are kept so its firmware
# ports: PA1/PA2 knobs (BM CV1/CV2), PA4 mode button, PA5 LED, PA6 DAC, PB3 MIDI RX.
# The new CV input uses an ADC0 pin no BM 8bit firmware touches: PB0 (AIN11), on the left side
# of the QFN next to the CV parts. Knob 3 is the passive filter (no MCU pin), as BM.
# PA7 (BM gate out) and PB4 (BM logger TX) are driven by BM firmware and stay unconnected; PB5 is spare.
MCU = {'20': 'POT1', '1': 'POT2', '14': 'CV_ADC', '9': None, '5': 'BUTTON', '6': 'LED_DRV',
       '7': 'DAC', '11': 'RX', '19': 'UPDI_PA0', '4': '+5V', '3': 'GND', '21': 'GND',
       '2': None, '8': None, '10': None, '12': None, '13': None,
       '15': None, '16': None, '17': None, '18': None}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7550 -> +5V
    c.append(part('J4', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (35.56, 55.88), 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(part('D4', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 66.04), 180,
                  {'1': '+12V_F', '2': '+12V'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D5', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 45.72), 0,
                  {'1': '-12V', '2': '-12V_F'}, Note='-12 V series reverse-polarity protection'))
    c.append(part('C5', 'C', '10u', 'C0805', (76.2, 69.85), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='25V', Note='+12V_F bulk'))
    c.append(part('C6', 'C', '10u', 'C0805', (76.2, 49.53), 180,
                  {'1': 'GND', '2': '-12V_F'}, Voltage='25V', Note='-12V_F bulk'))
    c.append(part('U2', 'HT75xx-1-SOT89', 'HT7550-1', 'SOT89', (106.68, 68.58), 0,
                  {'1': 'GND', '2': '+12V_F', '3': '+5V'},
                  Note='30 V max input, 100 mA. ~15 mA load: ~0.1 W at 11.6 V in'))
    c.append(part('C4', 'C', '1u', 'C0805', (93.98, 69.85), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C3', 'C', '10u', 'C0805', (119.38, 69.85), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C2', 'C', '10u', 'C0805', (129.54, 69.85), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='+5V bulk at the MCU'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (25.4, 58.42), 0, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (71.12, 66.04), 0, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (71.12, 45.72), 0, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, (48.26, 45.72), 0, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, (48.26, 66.04), 180, {'1': '+12V'}))

    # ---- MIDI input (TS modular MIDI): the MIDI V2 NPN front end with its JP1 bypass
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (25.4, 121.92), 0,
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(part('R3', 'R', '100k', 'R0603', (43.18, 118.11), 180,
                  {'1': 'MIDI_IN', '2': '+5V'},
                  Note='Idle pull-up: no cable turns Q1 on = UART idle'))
    c.append(part('R1', 'R', '10k', 'R0603', (53.34, 121.92), 90,
                  {'1': 'MIDI_IN', '2': 'Q1_B'},
                  Note='Base resistor: ~1.1 mA at +/-12 V; 0.26 mA from a 3.3 V sender'))
    c.append(part('D2', '1N4148W', '1N4148W', 'SOD123', (59.69, 125.73), 270,
                  {'1': 'Q1_B', '2': 'GND'},
                  Note='Clamps Q1 B-E to -0.7 V for a negative input (VEBO 6 V)'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23', (68.58, 121.92), 0,
                  {'1': 'Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting input buffer: input high = RX low. Firmware: PORT_INVEN on PB3'))
    c.append(part('R2', 'R', '22k', 'R0603', (71.12, 107.95), 180,
                  {'1': 'RX_Q', '2': '+5V'},
                  Note='Q1 collector pull-up, on RX_Q so the JP1 direct path leaves PB3 unloaded'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3', (86.36, 114.3), 0,
                  {'1': 'RX_Q', '2': 'RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. Solder 1-2 = protected '
                       '(Q1 drives PB3, PORT_INVEN on). Solder 2-3 = direct/unprotected '
                       '(MIDI_IN to PB3, PORT_INVEN off, stock BM 8bit firmware). Never both'))

    # ---- CV input: bipolar level shift R4 56k / R13 51k to +5V / R14 510k to GND maps
    # -5.5..+5.5 V onto 0..5 V (input impedance ~102k), Schottky clamp to +5V/GND, 1n,
    # MCP6001 rail-to-rail follower on +5V -> ADC pin (low source impedance, output within 0..5 V)
    c.append(part('J2', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (25.4, 175.26), 0,
                  {'T': 'CV_IN', 'S': 'GND', 'TN': 'GND'},
                  Note='CV in, -5.5..+5.5 V. Tip normalled to GND: unpatched reads mid-scale (0 V)'))
    c.append(part('R4', 'R', '56k', 'R0603', (50.8, 175.26), 90,
                  {'1': 'CV_IN', '2': 'CV_BUF'},
                  Note='Level-shift input resistor. Input impedance R4 + R13||R14 = 102k. '
                       'Clamp current <= 0.21 mA at +/-12 V'))
    c.append(part('R13', 'R', '51k', 'R0603', (86.36, 167.64), 0,
                  {'1': '+5V', '2': 'CV_BUF'},
                  Note='Level-shift offset: 0 V CV -> 2.49 V (mid-scale). +5V is also the ADC reference'))
    c.append(part('R14', 'R', '510k', 'R0603', (93.98, 182.88), 0,
                  {'1': 'CV_BUF', '2': 'GND'},
                  Note='Level-shift trim: with R4/R13 maps -5.49..+5.55 V to 0..5 V (gain 0.453)'))
    c.append(part('D3', 'BAT54SW', 'BAT54SW', 'SOT323', (63.5, 170.18), 0,
                  {'1': 'GND', '2': '+5V', '3': 'CV_BUF'},
                  Note='CV clamp: holds the U4 input within -0.3..+5.3 V'))
    c.append(part('C9', 'C', '1n', 'C0603', (76.2, 179.07), 0,
                  {'1': 'CV_BUF', '2': 'GND'}, Voltage='50V', Note='With R4||R13||R14 (25.4k): 6.3 kHz CV low-pass'))
    c.append(part('U4', 'MCP6001-OT', 'MCP6001', 'SOT23-5', (114.3, 177.8), 0,
                  {'3': 'CV_BUF', '4': 'CV_ADC', '1': 'CV_ADC', '2': 'GND', '5': '+5V'},
                  Note='CV buffer: unity follower, rail-to-rail in/out on +5V, so PB0 only ever sees 0..5 V. '
                       'Same family as Bread Modular 8bit MCP6002'))
    c.append(part('C15', 'C', '100n', 'C0603', (134.62, 190.5), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U4 decoupling'))

    # ---- MCU and programming
    c.append(part('U1', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', (165.1, 114.3), 0, MCU,
                  Note='5 V, 20 MHz as Bread Modular 8bit'))
    c.append(part('C1', 'C', '100n', 'C0603', (144.78, 92.71), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U1 decoupling'))
    c.append(part('R5', 'R', '4.7k', 'R0603', (195.58, 96.52), 90,
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular)'))
    c.append(part('J5', 'Conn_01x02', 'UPDI', 'H1x2', (213.36, 96.52), 0,
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power'))
    c.append(part('SW1', 'SW_Push', 'MODE', 'SW6', (213.36, 111.76), 270,
                  {'1': 'BUTTON', '2': 'GND'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Mode button (as Bread Modular SW1, PA4 internal pull-up): generic 6 x 6 mm THT '
                       'tact, 7 mm tall, Ø3.5 round stem, pins 6.5 x 4.5 mm. Hand-soldered on the F side; '
                       'pressed through the panel by the printed cap (panels/button-actuator)'))
    c.append(part('R6', 'R', '1k', 'R0603', (203.2, 113.03), 0,
                  {'1': 'LED_DRV', '2': 'LED_A'}, Note='Mode LED current'))
    c.append(part('D1', 'LED', 'LED_3mm_red', 'LED3', (203.2, 127.0), 90,
                  {'2': 'LED_A', '1': 'GND'}, Note='Mode LED (Bread Modular D1). Hand-soldered 3 mm THT'))

    # ---- Knobs 1 and 2: plain voltage dividers into ADC pins (Bread Modular CV1/CV2 pins)
    for i, (rv, cap, x) in enumerate((('RV1', 'C10', 149.86), ('RV2', 'C11', 185.42)), 1):
        c.append(part(rv, 'R_Potentiometer', '50k', 'RV09', (x, 170.18), 0,
                      {'1': 'GND', '2': f'POT{i}', '3': '+5V'},
                      Note=f'Knob {i}: RV09 9 mm vertical, linear (user stock, as audio-out). CW = +5V. '
                           'Hand-soldered'))
        c.append(part(cap, 'C', '10n', 'C0603', (x + 10.16, 173.99), 0,
                      {'1': f'POT{i}', '2': 'GND'}, Voltage='50V', Note='ADC hold / noise filter'))

    # ---- Knob 3: passive low-pass only, as Bread Modular: DAC -> R7 -> RV3 rheostat (pin 1
    # open) -> FILT, C13 to GND. CW (wiper to pin 3) = less R = brighter.
    c.append(part('R7', 'R', '10k', 'R0603', (256.54, 73.66), 90,
                  {'1': 'DAC', '2': 'DAC_R'},
                  Note='DAC series R: >= 10k DAC load, isolates the DAC from C13, sets fc max 15.9 kHz'))
    c.append(part('RV3', 'R_Potentiometer', '1M', 'RV09', (279.4, 83.82), 0,
                  {'1': None, '2': 'FILT', '3': 'DAC_R'},
                  Note='Knob 3: low-pass cutoff, rheostat (pin 1 open, as Bread Modular). RV09 9 mm '
                       'vertical, linear (user stock, as audio-out)'))
    c.append(part('C13', 'C', '1n', 'C0603', (304.8, 90.17), 0,
                  {'1': 'FILT', '2': 'GND'}, Voltage='50V',
                  Note='Filter C: fc 158 Hz (R7 + RV3 1M) .. 15.9 kHz (R7 only)'))

    # ---- Output: U3A non-inverting gain 2.2 with -1.2 x VOFF offset: 0..4.34 V -> +/-4.8 V
    c.append(part('U3', 'TL072', 'TL072', 'SOIC8', (279.4, 160.02), 0,
                  {'3': 'FILT', '2': 'OUT_FB', '1': 'AMP_OUT'}, unit=1,
                  Note='+/-12 V. High-Z + input keeps the passive filter unloaded'))
    c.append(part('U3', 'TL072', 'TL072', 'SOIC8', (256.54, 187.96), 0,
                  {'5': 'VREF_DIV', '6': 'VOFF', '7': 'VOFF'}, unit=2,
                  Note='+/-12 V. High-Z + input keeps the passive filter unloaded'))
    c.append(part('U3', 'TL072', 'TL072', 'SOIC8', (345.44, 185.42), 0,
                  {'4': '-12V_F', '8': '+12V_F'}, unit=3,
                  Note='+/-12 V. High-Z + input keeps the passive filter unloaded'))
    c.append(part('R9', 'R', '12k', 'R0603', (281.94, 170.18), 90,
                  {'1': 'OUT_FB', '2': 'AMP_OUT'}, Note='Rf: gain 1 + 12k/10k = 2.2'))
    c.append(part('R8', 'R', '10k', 'R0603', (269.24, 173.99), 0,
                  {'1': 'OUT_FB', '2': 'VOFF'}, Note='Rg to the offset reference'))
    c.append(part('R10', 'R', '10k', 'R0603', (238.76, 179.07), 0,
                  {'1': '+5V', '2': 'VREF_DIV'}, Note='Offset divider top'))
    c.append(part('R11', 'R', '39k', 'R0603', (238.76, 191.77), 0,
                  {'1': 'VREF_DIV', '2': 'GND'},
                  Note='Offset divider bottom: 3.98 V = mid-scale 2.17 V x 2.2 / 1.2'))
    c.append(part('C14', 'C', '10u', 'C0805', (231.14, 191.77), 0,
                  {'1': 'VREF_DIV', '2': 'GND'}, Voltage='25V', Note='Filters +5V noise off the offset (2 Hz)'))
    c.append(part('R12', 'R', '1k', 'R1206', (304.8, 160.02), 90,
                  {'1': 'AMP_OUT', '2': 'AUDIO_OUT'}, Power='0.5W',
                  Note='Output series: short / mis-patch current limit (op-amp also current-limits); 0.5 W for a permanent +/-12 V mis-patch (0.28 W)'))
    c.append(part('J3', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (330.2, 160.02), 180,
                  {'T': 'AUDIO_OUT', 'S': 'GND', 'TN': None}, Note='Audio out, Eurorack level (~10 Vpp)'))
    c.append(part('C7', 'C', '100n', 'C0603', (355.6, 176.53), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U3 V+ decoupling'))
    c.append(part('C8', 'C', '100n', 'C0603', (355.6, 194.31), 0,
                  {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U3 V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Live strict lookups 2026-10-19, recorded in docs/sourcing-candidates.json. Codes shared
# with modules/midi are the same parts. All R/C are JLCPCB Basic except R12 (0.5 W 1206, no
# Basic exists); U1 and U2 are Extended.
# The THT jacks, pots, LED, switch and headers are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM Semicon'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '12k', 'R0603'): dict(LCSC='C22790', MPN='0603WAF1202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '39k', 'R0603'): dict(LCSC='C23153', MPN='0603WAF3902T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('R', '510k', 'R0603'): dict(LCSC='C23192', MPN='0603WAF5103T5E', Manufacturer='UNI-ROYAL'),
    ('C', '1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7550-1', 'SOT89'): dict(LCSC='C16106', MPN='HT7550-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR',
                                                       Manufacturer='Microchip'),
    ('TL072', 'TL072', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
    ('MCP6001-OT', 'MCP6001', 'SOT23-5'): dict(LCSC='C29429', MPN='MCP6001T-E/OT', Manufacturer='Microchip'),
}


# Reference / value text offsets from the symbol origin (centred). Parts not listed: see text_at.
TEXT_AT = {
    'U1': ((10.16, -25.4), (10.16, 25.4)),
    'U2': ((0, -7.62), (8.89, 7.62)),
    'J4': ((1.27, -12.7), (1.27, 12.7)),
    'J5': ((0, -3.81), (0, 5.08)),
    'D1': ((-3.81, -1.27), (-7.62, 1.27)),
    'D2': ((2.54, -1.27), (2.54, 1.27), 'left'),
    '#FLG04': ((-5.08, -5.08), (0, -2.54)),
    'SW1': ((7.62, -1.27), (7.62, 1.27)),
    'SolderJumper_3_Open': ((0, -6.35), (0, -3.81)),
    'MMBT3904': ((10.16, -1.27), (10.16, 1.27)),
    'BAT54SW': ((0, -6.35), (0, -3.81)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 6.35)),
    'R_Potentiometer': ((-5.08, -1.27), (-5.08, 1.27)),
    'TL072': ((2.54, -10.16), (2.54, -7.62)),
    'MCP6001-OT': ((5.08, -7.62), (5.08, 7.62), 'left'),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '#FLG05': ((0, 5.08), (0, 2.54)),
}

def text_at(p):
    """(reference offset, value offset, justify) from the symbol origin."""
    if p['ref'] in TEXT_AT or p['sym'] in TEXT_AT:
        t = TEXT_AT.get(p['ref'], TEXT_AT.get(p['sym']))
        return t if len(t) == 3 else (*t, None)
    if p['sym'] in ('R', 'C') and p['rot'] in (0, 180):      # vertical: right of the body
        # KiCad mirrors the justification with the symbol rotation
        return (2.54, -1.27), (2.54, 1.27), 'left' if p['rot'] == 0 else 'right'
    return (0, -2.54), (0, 2.54), None                      # horizontal: above / below


# Symbols drawn mirrored (only at rotation 0): the pots, so CW (+5V) is up and the wiper right.
MIRROR_X = {'RV1', 'RV2', 'RV3'}

# Supply nets are drawn with power symbols (net name = symbol value); every other net
# carries a local label, so all net names are explicit (the routed PCB names them).
RAIL_SYMBOL = {'GND': 'GND', '+5V': '+5V', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Schematic drawing, block by block. Wires are polylines whose points are (x, y) or
# 'REF.PIN' (that pin's end). Power symbols: (net, point, rotation). Labels: (net, point,
# side the text runs). build() splits wires at every connection point, adds the junction
# dots, checks that nothing dangles and compares the exported netlist with CIRCUIT.
WIRES = [
    # Power entry: J4 pin pairs tied left/right, series Schottkys, bulk, HT7550-1
    ['J4.1', (27.94, 50.8), (27.94, 45.72), (45.72, 45.72), (45.72, 50.8), 'J4.2'],
    [(45.72, 45.72), 'D5.1'], ['D5.2', (83.82, 45.72)],
    ['J4.3', (27.94, 53.34), (27.94, 58.42), 'J4.7'], ['J4.5', (27.94, 55.88)], [(27.94, 58.42), (22.86, 58.42)],
    ['J4.4', (45.72, 53.34), (45.72, 58.42), 'J4.8'], ['J4.6', (45.72, 55.88)], [(45.72, 58.42), (48.26, 58.42)],
    ['J4.9', (27.94, 60.96), (27.94, 66.04), (45.72, 66.04), (45.72, 60.96), 'J4.10'],
    [(45.72, 66.04), 'D4.2'], ['D4.1', 'U2.2'], ['U2.3', 'C2.1'],
    # MIDI in
    ['J1.S', (33.02, 119.38)], ['J1.T', 'R1.1'],
    [(46.99, 121.92), (46.99, 137.16), (99.06, 137.16), (99.06, 114.3), 'JP1.3'],
    ['R1.2', 'Q1.1'], ['Q1.3', 'R2.1'], [(71.12, 114.3), 'JP1.1'], ['JP1.2', (86.36, 121.92), (91.44, 121.92)],
    # CV in
    ['J2.S', (33.02, 172.72)], ['J2.TN', (33.02, 177.8), (33.02, 180.34)], ['J2.T', 'R4.1'],
    ['R4.2', 'U4.3'], ['R13.2', (86.36, 175.26)], ['R14.1', (93.98, 175.26)], ['U4.1', (129.54, 177.8)],
    ['U4.4', (104.14, 180.34), (104.14, 190.5), (124.46, 190.5), (124.46, 177.8)],
    # MCU, UPDI, mode button and LED
    ['C1.1', (165.1, 88.9), 'U1.4'], ['U1.19', 'R5.1'], ['R5.2', 'J5.1'],
    ['J5.2', (205.74, 99.06), (205.74, 101.6)],
    ['U1.20', (182.88, 99.06)], ['U1.1', (182.88, 101.6)], ['U1.5', 'SW1.1'], ['U1.6', 'R6.1'],
    ['R6.2', 'D1.2'], ['U1.7', (182.88, 111.76)], ['U1.14', (182.88, 119.38)], ['U1.11', (182.88, 127.0)],
    # Knobs 1 and 2
    ['RV1.2', (167.64, 170.18)], ['RV2.2', (203.2, 170.18)],
    # Knob 3 passive low-pass: DAC -> R7 -> RV3 (rheostat) -> FILT / C13
    [(246.38, 73.66), 'R7.1'], ['R7.2', (279.4, 73.66), 'RV3.3'],
    ['RV3.2', (304.8, 83.82), 'C13.1'], [(304.8, 83.82), (317.5, 83.82)],
    # Output stage
    [(264.16, 157.48), 'U3.3'], ['U3.2', (269.24, 162.56), 'R8.1'], [(269.24, 170.18), 'R9.1'],
    ['R9.2', (289.56, 170.18), (289.56, 160.02)], ['U3.1', 'R12.1'], ['R12.2', 'J3.T'],
    ['J3.S', (322.58, 162.56), (322.58, 165.1)],
    ['U3.7', (269.24, 187.96), 'R8.2'], [(266.7, 187.96), (266.7, 198.12), (246.38, 198.12), (246.38, 190.5), 'U3.6'],
    ['R10.2', 'R11.1'], [(238.76, 185.42), 'U3.5'], [(238.76, 187.96), 'C14.1'],
    ['U3.8', (342.9, 172.72), (355.6, 172.72)], ['U3.4', (342.9, 198.12), (355.6, 198.12)],
    ['C7.2', 'C8.1'], [(355.6, 185.42), (360.68, 185.42)],
]

POWER = [
    ('-12V', (53.34, 45.72), 0), ('-12V_F', (83.82, 45.72), 0), ('GND', (22.86, 58.42), 0),
    ('GND', (48.26, 58.42), 0), ('+12V', (53.34, 66.04), 0), ('+12V_F', (86.36, 66.04), 0),
    ('+5V', (124.46, 66.04), 0),
    ('GND', 'C6.1', 0), ('GND', 'C5.2', 0), ('GND', 'C4.2', 0), ('GND', 'U2.1', 0),
    ('GND', 'C3.2', 0), ('GND', 'C2.2', 0),
    ('GND', (33.02, 119.38), 90), ('+5V', 'R3.2', 0), ('GND', 'D2.2', 0), ('GND', 'Q1.2', 0),
    ('+5V', 'R2.2', 0),
    ('GND', (33.02, 172.72), 90), ('GND', (33.02, 180.34), 0), ('GND', 'D3.1', 270), ('+5V', 'D3.2', 0),
    ('GND', 'C9.2', 0), ('+5V', 'R13.1', 0), ('GND', 'R14.2', 0), ('+5V', 'U4.5', 0), ('GND', 'U4.2', 0), ('+5V', 'C15.1', 0), ('GND', 'C15.2', 0),
    ('+5V', (154.94, 88.9), 0), ('GND', 'C1.2', 0), ('GND', 'U1.3', 0), ('GND', (205.74, 101.6), 0),
    ('GND', 'SW1.2', 0), ('GND', 'D1.1', 0),
    ('+5V', 'RV1.3', 0), ('GND', 'RV1.1', 0), ('GND', 'C10.2', 0),
    ('+5V', 'RV2.3', 0), ('GND', 'RV2.1', 0), ('GND', 'C11.2', 0),
    ('GND', 'C13.2', 0),
    ('+5V', 'R10.1', 0), ('GND', 'R11.2', 0), ('GND', 'C14.2', 0), ('GND', (322.58, 165.1), 0),
    ('+12V_F', (349.25, 172.72), 0), ('-12V_F', (349.25, 198.12), 180), ('GND', (360.68, 185.42), 0),
]

LABELS = [
    ('MIDI_IN', (60.96, 137.16), 'R'), ('Q1_B', (57.15, 121.92), 'R'), ('RX_Q', (73.66, 114.3), 'R'),
    ('RX', (91.44, 121.92), 'R'),
    ('CV_IN', (39.37, 175.26), 'R'), ('CV_BUF', (99.06, 175.26), 'R'), ('CV_ADC', (129.54, 177.8), 'R'),
    ('UPDI_PA0', (180.34, 96.52), 'R'), ('UPDI', (200.66, 96.52), 'R'),
    ('POT1', (182.88, 99.06), 'R'), ('POT2', (182.88, 101.6), 'R'), ('BUTTON', (182.88, 106.68), 'R'),
    ('LED_DRV', (182.88, 109.22), 'R'), ('DAC', (182.88, 111.76), 'R'), ('CV_ADC', (182.88, 119.38), 'R'),
    ('RX', (182.88, 127.0), 'R'), ('LED_A', (203.2, 121.92), 'U'),
    ('POT1', (167.64, 170.18), 'R'), ('POT2', (203.2, 170.18), 'R'),
    ('DAC', (246.38, 73.66), 'L'), ('DAC_R', (266.7, 73.66), 'R'), ('FILT', (317.5, 83.82), 'R'),
    ('FILT', (264.16, 157.48), 'L'), ('OUT_FB', (270.51, 170.18), 'R'), ('AMP_OUT', (290.83, 160.02), 'R'),
    ('AUDIO_OUT', (309.88, 160.02), 'R'), ('VOFF', (269.24, 186.69), 'U'), ('VREF_DIV', (240.03, 185.42), 'R'),
]

TEXTS = [
    ((20.32, 17.78), 'BIG MODULAR 8BIT - S5 schematic (Bread Modular 8bit for Eurorack, 4HP). '
                     'Circuit intent: docs/research.md', 2.0),
    ((20.32, 30.48), 'POWER: +12V -> B5819W -> +12V_F (U3 V+, HT7550-1 -> +5V); '
                     '-12V -> B5819W -> -12V_F (U3 V-).', 1.4),
    ((20.32, 82.55), 'PWR_FLAG: #FLG01/#FLG04/#FLG05 mark the Eurorack GND/-12V/+12V entry at J4; #FLG02/#FLG03 mark the\n'
                     'protected rails, fed only through D4/D5, which ERC cannot see through.', 1.1),
    ((20.32, 99.06), 'MIDI IN (TS): MIDI V2 NPN front end (3.3 V and 5 V senders, +/-12 V tolerant), no opto', 1.4),
    ((20.32, 143.51), 'JP1 RX SOURCE (solder jumper on the back, shipped OPEN: bridge one pair by hand):\n'
                      'Solder 1-2 = PROTECTED (Q1 drives PB3; firmware PORT_INVEN on PB3).\n'
                      'Solder 2-3 = DIRECT (MIDI_IN to PB3, unprotected; stock BM 8bit firmware).\n'
                      'Exactly one bridge: never both, and open = PB3 floats.', 1.1),
    ((20.32, 156.21), 'CV IN: R4/R13/R14 level shift, D3 clamp, C9 -> U4 MCP6001 follower (+5V) -> PB0 (AIN11)', 1.4),
    ((20.32, 194.31), 'Input impedance 102k. -5.5..+5.5 V -> 0..5 V (0 V CV = mid-scale, ~509). +/-12 V tolerant (clamped).', 1.1),
    ((139.7, 72.39), 'MCU: ATtiny1616 at 5 V; Bread Modular 8bit pin map (PA1/PA2 knobs, PA4 button,\n'
                     'PA5 LED, PA6 DAC, PB3 RX). New: PB0 CV in. PB5 spare.\n'
                     'UPDI J5: pin 1 UPDI, pin 2 GND (2.54 mm). Power the module from Eurorack while programming.', 1.1),
    ((139.7, 157.48), 'KNOBS 1/2: 50k linear dividers +5V..GND into PA1/PA2 (BM CV1/CV2).', 1.1),
    ((241.3, 50.8), 'KNOB 3 = PASSIVE LOW-PASS (as Bread Modular): DAC -> R7 10k -> RV3 1M rheostat -> FILT, C13 1n.\n'
                    'CW = brighter: 158 Hz .. 15.9 kHz. RV3 pin 1 open. U3A + input is high-Z, so the filter is unloaded.', 1.1),
    ((241.3, 143.51), 'OUTPUT: U3A gain 2.2 with -1.2 x VOFF (3.98 V): DAC 0..4.34 V -> -4.8..+4.8 V,\n'
                      '1k series to the jack. DC coupled (LFO firmware works).', 1.1),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/8bit/schematic/' + key))


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
        '(options "") (descr "8bit pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - 8bit") (rev "S5") (company "Big Modular")
        (comment 1 "SCHEMATIC S5 - Bread Modular 8bit for Eurorack: protected MIDI in, bipolar buffered CV in, knob 3 passive LPF, +/-5 V out")
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
            ox, oy = xform(px, -py if p['ref'] in MIRROR_X else py, p['rot'])
            ex, ey = r(x + ox), r(y + oy)
            key = f"{p['ref']}/{n}"
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                continue
            nets.setdefault(net, []).append(key)
            ends[f"{p['ref']}.{n}"] = (ex, ey, net)
    multi = {ref: u for ref, u in units.items() if len(u) > 1}
    assert multi == {'U3': {1, 2, 3}}, multi
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
