"""Generate the MOTION S1 schematic (hardware/motion.kicad_sch) and its pinned symbols.

Run from modules/motion:
  python3 -B tools/build_schematic.py

Writes hardware/MOTION.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the MOTION library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. CIRCUIT below is the
circuit of docs/research.md section 3: an ATtiny1616 reads four knobs, records their
motion straight into an MB85RC256V I2C FRAM and plays the four tracks through an
MCP4728 quad 12-bit I2C DAC; a TL074 maps each DAC channel (0..+5VA) to -5..+5 V.
REC and RANGE buttons, six LEDs (four motion LEDs on hardware PWM pins, REC, RANGE).
Signal nets are drawn as wires (WIRES below) with one label per net; supply nets use
power symbols. Multi-unit symbols (the TL074) get one placed unit per entry.

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
PROJECT = 'motion'
LIB = 'MOTION'
STUB = 2.54

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the MOTION library, so the copies
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
    'TL074': ('Amplifier_Operational', 'TL074'),
    'MCP4728': ('Analog_DAC', 'MCP4728'),
    'MB85RC256V': ('Memory_NVRAM', 'FM24C64B'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_01x02': ('Connector_Generic', 'Conn_01x02'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'SW_Push': ('Switch', 'SW_Push'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+5V': ('power', '+5V'), '+5VA': ('power', '+5VA'),
    '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

# Stock symbols reused under another name (same package and pinout): the copy is renamed
# and gets these properties. KiCad ships no MB85RC256V; the FM24C64B symbol is the same
# 8-pin I2C FRAM pinout (A0 A1 A2 VSS SDA SCL WP VDD).
RENAMED = {
    'MB85RC256V': {
        'Value': 'MB85RC256V',
        'Datasheet': 'https://www.ramxeed.com/assets/images/products/datasheet/FeRAM/i3/MB85RC256V-DS11v2-E.pdf',
        'Description': '256-Kbit (32 K x 8) I2C FRAM, 2.7-5.5 V, 1 MHz, SOP-8 150 mil',
    },
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'SOD123': 'D_SOD-123', 'LED3': 'LED_D3.0mm',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'SOIC14': 'SOIC-14_3.9x8.7mm_P1.27mm', 'TSSOP10': 'TSSOP-10_3x3mm_P0.5mm',
    'SOT89': 'SOT-89-3', 'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'RV09': 'Potentiometer_RV09', 'SW6': 'SW_PUSH_6mm_H7.3mm',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
}

# Copper-only parts: no BOM row, no CPL row (none on this board).
NOT_ASSEMBLED = set()

# ATtiny1616-M (VQFN-20) pin numbers. No Bread Modular firmware exists for this module, so
# the pins follow the hardware: knobs on ADC0 pins PA1/PA2/PA6/PA7 (AIN1/2/6/7); I2C on the
# default TWI0 pins PB0 (SCL) / PB1 (SDA); all six LEDs on TCA0 split-mode PWM outputs
# (WO2 PB2, WO3 PA3, WO4 PA4, WO5 PA5 default; WO0 PB3 and WO1 PB4 through PORTMUX, because
# their default pins PB0/PB1 are the I2C bus); buttons on PC0/PC1 (internal pull-ups).
# PB5, PC2 and PC3 are spare.
MCU = {'20': 'POT1', '1': 'POT2', '7': 'POT3', '8': 'POT4',
       '12': 'LED1', '2': 'LED2', '5': 'LED3', '6': 'LED4',
       '11': 'LED_REC', '10': 'LED_RANGE',
       '14': 'SCL', '13': 'SDA', '15': 'REC_BTN', '16': 'RANGE_BTN',
       '19': 'UPDI_PA0', '4': '+5V', '3': 'GND', '21': 'GND',
       '9': None, '17': None, '18': None}

# Output channels: op-amp origin (X0, Y0 + k * DY); TL074 unit pins (+, -, out).
X0, Y0, DY = 337.82, 60.96, 43.18
AMP_PINS = [('3', '2', '1'), ('5', '6', '7'), ('10', '9', '8'), ('12', '13', '14')]
POT_X, POT_Y = (139.7, 175.26, 210.82, 246.38), 127.0
LED_Y0, LED_DY = 175.26, 7.62
LED_NETS = ['LED1', 'LED2', 'LED3', 'LED4', 'LED_REC', 'LED_RANGE']


def part(ref, sym, value, fp, at, rot, pins, unit=1, mirror=False, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, mirror=mirror,
                fields=fields)


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys -> +12V_F / -12V_F; HT7550 -> +5V;
    # +5V -> R1 10R + C6/C7 -> +5VA (DAC supply = DAC reference, and the output-stage offset)
    c.append(part('J5', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (35.56, 55.88), 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header on B between the lower output jacks, pin 1 (-12 V) at the '
                       'bottom; also takes a 16-pin IDC socket (positions 11-16 overhang upward, unused)'))
    c.append(part('D7', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 66.04), 180,
                  {'1': '+12V_F', '2': '+12V'}, Note='+12 V series reverse-polarity protection'))
    c.append(part('D8', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 45.72), 0,
                  {'1': '-12V', '2': '-12V_F'}, Note='-12 V series reverse-polarity protection'))
    c.append(part('C1', 'C', '10u', 'C0805', (76.2, 69.85), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='25V', Note='+12V_F bulk'))
    c.append(part('C2', 'C', '10u', 'C0805', (76.2, 49.53), 180,
                  {'1': 'GND', '2': '-12V_F'}, Voltage='25V', Note='-12V_F bulk'))
    c.append(part('U1', 'HT75xx-1-SOT89', 'HT7550-1', 'SOT89', (106.68, 68.58), 0,
                  {'1': 'GND', '2': '+12V_F', '3': '+5V'},
                  Note='30 V max input, 100 mA. ~17 mA load: ~0.11 W at 11.6 V in'))
    c.append(part('C3', 'C', '1u', 'C0805', (93.98, 69.85), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='LDO input'))
    c.append(part('C4', 'C', '10u', 'C0805', (119.38, 69.85), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C5', 'C', '10u', 'C0805', (129.54, 69.85), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='+5V bulk at the MCU'))
    c.append(part('R1', 'R', '10R', 'R0603', (139.7, 66.04), 90,
                  {'1': '+5V', '2': '+5VA'},
                  Note='+5VA filter: with C6 a 1.6 kHz low-pass that keeps MCU / LED switching noise off the '
                       'DAC reference. <= 3 mA load: <= 30 mV drop'))
    c.append(part('C6', 'C', '10u', 'C0805', (149.86, 69.85), 0,
                  {'1': '+5VA', '2': 'GND'}, Voltage='25V', Note='+5VA bulk (DAC supply = DAC reference)'))
    c.append(part('C7', 'C', '100n', 'C0603', (160.02, 69.85), 0,
                  {'1': '+5VA', '2': 'GND'}, Voltage='50V', Note='U3 decoupling, at its VDD pin'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (25.4, 58.42), 0, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (71.12, 66.04), 0, {'1': '+12V_F'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (71.12, 45.72), 0, {'1': '-12V_F'}))
    c.append(part('#FLG04', 'PWR_FLAG', 'PWR_FLAG', None, (48.26, 45.72), 0, {'1': '-12V'}))
    c.append(part('#FLG05', 'PWR_FLAG', 'PWR_FLAG', None, (48.26, 66.04), 180, {'1': '+12V'}))
    c.append(part('#FLG06', 'PWR_FLAG', 'PWR_FLAG', None, (154.94, 66.04), 0, {'1': '+5VA'}))

    # ---- MCU and programming
    c.append(part('U2', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', (63.5, 129.54), 0, MCU,
                  Note='5 V, 20 MHz. 2 KB RAM: the takes live in the FRAM U4, not in RAM'))
    c.append(part('C8', 'C', '100n', 'C0603', (43.18, 107.95), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U2 decoupling'))
    c.append(part('R2', 'R', '4.7k', 'R0603', (96.52, 111.76), 90,
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular)'))
    c.append(part('J6', 'Conn_01x02', 'UPDI', 'H1x2', (114.3, 111.76), 0,
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power'))

    # ---- Buttons: to GND, MCU internal pull-ups, debounced in firmware
    for ref, net, y, role in (('SW1', 'REC_BTN', 180.34, 'REC: hold + move a knob records that knob; '
                                                        'hold 5 s without moving a knob erases every take'),
                              ('SW2', 'RANGE_BTN', 193.04, 'RANGE: click toggles 0..+5 V / -5..+5 V for all four '
                                                          'outputs (state kept in the FRAM)')):
        c.append(part(ref, 'SW_Push', ref == 'SW1' and 'REC' or 'RANGE', 'SW6', (40.64, y), 0,
                      {'1': net, '2': 'GND'}, MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                      Note=f'{role}. Generic 6 x 6 mm THT tact, 7 mm tall, as modules/8bit SW1; hand-soldered '
                           'on the F side, pressed through the panel by the printed cap'))

    # ---- LEDs: MCU pin -> 10k -> LED -> GND (0.33 mA at 100 % duty; dimmed further by PWM)
    led_role = ['Motion LED 1 (brightness = output 1 position in the selected range)', 'Motion LED 2',
                'Motion LED 3', 'Motion LED 4', 'REC LED (recording / erase countdown)',
                'RANGE LED: off = 0..+5 V, on = -5..+5 V']
    for i, net in enumerate(LED_NETS):
        y = LED_Y0 + i * LED_DY
        c.append(part(f'R{5 + i}', 'R', '10k', 'R0603', (81.28, y), 90,
                      {'1': net, '2': f'{net}_A'},
                      Note='LED current: 0.33 mA at 100 % duty (a red LED at 3 mA dimmed to 1 % was the '
                           'modules/mcc lesson: keep the LEDs dim by the circuit)'))
        c.append(part(f'D{1 + i}', 'LED', 'LED_3mm', 'LED3', (99.06, y), 180,
                      {'2': f'{net}_A', '1': 'GND'}, Note=f'{led_role[i]}. Hand-soldered 3 mm THT'))

    # ---- I2C bus (400 kHz): FRAM 0x50, DAC 0x60
    c.append(part('C9', 'C', '100n', 'C0603', (119.38, 190.5), 0,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U4 decoupling'))
    c.append(part('U4', 'MB85RC256V', 'MB85RC256V', 'SOIC8', (142.24, 190.5), 0,
                  {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'GND', '5': 'SDA', '6': 'SCL', '7': 'GND', '8': '+5V'},
                  Note='32 KB I2C FRAM, address 0x50 (A0-A2 low), WP low = writable. No write delay, 10^12 '
                       'cycles: the four takes are recorded and played straight from it (2 bytes x 50 frames/s '
                       '= ~81 s per knob), so they survive power-off without a save step'))
    c.append(part('R4', 'R', '2.2k', 'R0603', (165.1, 180.34), 0,
                  {'1': '+5V', '2': 'SDA'}, Note='I2C pull-up (400 kHz)'))
    c.append(part('R3', 'R', '2.2k', 'R0603', (175.26, 180.34), 0,
                  {'1': '+5V', '2': 'SCL'}, Note='I2C pull-up (400 kHz)'))
    c.append(part('U3', 'MCP4728', 'MCP4728', 'TSSOP10', (200.66, 190.5), 0,
                  {'1': '+5VA', '2': 'SCL', '3': 'SDA', '4': 'GND', '5': None,
                   '6': 'DAC1', '7': 'DAC2', '8': 'DAC3', '9': 'DAC4', '10': 'GND'},
                  Note='Quad 12-bit I2C DAC, address 0x60. Firmware selects VREF = VDD (+5VA), so every '
                       'output is ratiometric to +5VA like the output-stage offset. LDAC low: an output '
                       'updates when its write is acknowledged. RDY/BSY unused'))

    # ---- Knobs 1-4: plain voltage dividers into ADC pins
    for i, x in enumerate(POT_X, 1):
        c.append(part(f'RV{i}', 'R_Potentiometer', '50k', 'RV09', (x, POT_Y), 0,
                      {'1': 'GND', '2': f'POT{i}', '3': '+5V'}, mirror=True,
                      Note=f'Knob {i}: RV09 9 mm vertical, linear (user stock, as audio-out). CW = +5V. '
                           'Hand-soldered'))
        c.append(part(f'C{9 + i}', 'C', '10n', 'C0603', (x + 10.16, POT_Y + 3.81), 0,
                      {'1': f'POT{i}', '2': 'GND'}, Voltage='50V', Note='ADC hold / noise filter'))

    # ---- Outputs 1-4: DAC -> 10k / 100n (160 Hz) -> TL074, gain 2 around +5VA:
    # Vout = 2 x Vdac - (+5VA), so DAC 0..+5VA -> -5..+5 V; 1k series to the jack
    amp = ('TL074 on +/-12 V: one output amplifier per unit, Vout = 2 x Vdac - (+5VA). '
           'Code 0 = -5 V, 2048 = 0 V, 4095 = +5 V')
    for k in range(4):
        n, y = k + 1, Y0 + k * DY
        plus, minus, out = AMP_PINS[k]
        r0, cn = 11 + 4 * k, 14 + k
        c.append(part(f'R{r0}', 'R', '10k', 'R0603', (X0 - 25.4, y + 2.54), 90,
                      {'1': f'DAC{n}', '2': f'FLT{n}'},
                      Note='Smoothing low-pass with the 100n: 160 Hz, 1 ms. Removes the 1 kHz update '
                           'steps; far above any hand-moved knob'))
        c.append(part(f'C{cn}', 'C', '100n', 'C0603', (X0 - 15.24, y + 6.35), 0,
                      {'1': f'FLT{n}', '2': 'GND'}, Voltage='50V', Note='Smoothing low-pass (160 Hz)'))
        c.append(part('U5', 'TL074', 'TL074', 'SOIC14', (X0, y), 0,
                      {plus: f'FLT{n}', minus: f'FB{n}', out: f'AMP{n}'}, unit=n, mirror=True, Note=amp))
        c.append(part(f'R{r0 + 1}', 'R', '10k', 'R0603', (X0 - 10.16, y - 13.97), 0,
                      {'1': '+5VA', '2': f'FB{n}'},
                      Note='Rg to +5VA: the -5 V offset. Equal to Rf, so 0 V sits at DAC mid-scale '
                           'whatever +5VA is (1 % parts: <= +/-50 mV at 0 V)'))
        c.append(part(f'R{r0 + 2}', 'R', '10k', 'R0603', (X0 + 2.54, y - 10.16), 90,
                      {'1': f'FB{n}', '2': f'AMP{n}'}, Note='Rf: gain 1 + Rf/Rg = 2'))
        c.append(part(f'R{r0 + 3}', 'R', '1k', 'R1206', (X0 + 25.4, y), 90,
                      {'1': f'AMP{n}', '2': f'OUT{n}'}, Power='0.5W',
                      Note='Output series: short / mis-patch current limit; 0.5 W for a permanent '
                           '+/-12 V mis-patch (0.29 W)'))
        c.append(part(f'J{n}', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (X0 + 50.8, y), 180,
                      {'T': f'OUT{n}', 'S': 'GND', 'TN': None},
                      Note=f'CV out {n}: 0..+5 V or -5..+5 V (RANGE), DC coupled, 1k source'))
    c.append(part('U5', 'TL074', 'TL074', 'SOIC14', (254.0, 187.96), 0,
                  {'11': '-12V_F', '4': '+12V_F'}, unit=5, Note=amp))
    c.append(part('C18', 'C', '100n', 'C0603', (264.16, 179.07), 0,
                  {'1': '+12V_F', '2': 'GND'}, Voltage='50V', Note='U5 V+ decoupling'))
    c.append(part('C19', 'C', '100n', 'C0603', (264.16, 196.85), 0,
                  {'1': 'GND', '2': '-12V_F'}, Voltage='50V', Note='U5 V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Codes shared with modules/8bit are the same parts (its live audit 2026-11-14); the new ones
# (10R, 2.2k, MCP4728, MB85RC256V) and the Extended ones were looked up live on 2026-11-15
# (docs/sourcing-candidates.json). All R/C are JLCPCB Basic except the four 0.5 W 1206 output
# resistors (no Basic exists); U2, U3, U4 and U5 are Extended, U1 Preferred Extended.
# The THT jacks, pots, LEDs, switches and headers are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '10R', 'R0603'): dict(LCSC='C22859', MPN='0603WAF100JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C2074262', MPN='ESR18EZPF1001', Manufacturer='ROHM Semicon'),
    ('R', '2.2k', 'R0603'): dict(LCSC='C4190', MPN='0603WAF2201T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7550-1', 'SOT89'): dict(LCSC='C16106', MPN='HT7550-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR',
                                                       Manufacturer='Microchip'),
    ('TL074', 'TL074', 'SOIC14'): dict(LCSC='C12594', MPN='TL074CDR', Manufacturer='Texas Instruments'),
    ('MCP4728', 'MCP4728', 'TSSOP10'): dict(LCSC='C478093', MPN='MCP4728T-E/UN', Manufacturer='Microchip'),
    ('MB85RC256V', 'MB85RC256V', 'SOIC8'): dict(LCSC='C45273903', MPN='MB85RC256VPNF-G-AMERE2',
                                                 Manufacturer='RAMXEED/FUJITSU'),
}


# Reference / value text offsets from the symbol origin (centred), keyed 'REF/unit', reference or
# symbol. Parts not listed: see text_at.
TEXT_AT = {
    'U2': ((10.16, -25.4), (10.16, 25.4)),
    'U1': ((0, -8.89), (0, -6.35)),
    'U3': ((7.62, -8.89), (8.89, 10.16)),
    'U4': ((6.35, -10.16), (8.89, -7.62)),
    'U5/5': ((2.54, -10.16), (2.54, -7.62)),
    # Rg of each output stage: text on the left, clear of the FBn label
    **{f'R{12 + 4 * k}': ((-2.54, -1.27), (-2.54, 1.27), 'right') for k in range(4)},
    'TL074': ((2.54, 6.35), (2.54, 8.89)),
    'J5': ((1.27, -12.7), (1.27, 12.7)),
    'J6': ((0, -3.81), (0, 5.08)),
    '#FLG04': ((-5.08, -5.08), (0, -2.54)),
    'SW_Push': ((0, -5.08), (0, 2.54)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 6.35)),
    'R_Potentiometer': ((-5.08, -1.27), (-5.08, 1.27)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
    '#FLG05': ((0, 5.08), (0, 2.54)),
}


def text_at(p):
    """(reference offset, value offset, justify) from the symbol origin."""
    for key in (f"{p['ref']}/{p['unit']}", p['ref'], p['sym']):
        if key in TEXT_AT:
            t = TEXT_AT[key]
            return t if len(t) == 3 else (*t, None)
    if p['sym'] in ('R', 'C') and p['rot'] in (0, 180):      # vertical: right of the body
        # KiCad mirrors the justification with the symbol rotation
        return (2.54, -1.27), (2.54, 1.27), 'left' if p['rot'] == 0 else 'right'
    return (0, -2.54), (0, 2.54), None                      # horizontal: above / below


# Supply nets are drawn with power symbols (net name = symbol value); every other net
# carries a local label, so all net names are explicit (the routed PCB names them).
RAIL_SYMBOL = {'GND': 'GND', '+5V': '+5V', '+5VA': '+5VA', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Schematic drawing, block by block. Wires are polylines whose points are (x, y) or
# 'REF.PIN' (that pin's end). Power symbols: (net, point, rotation). Labels: (net, point,
# side the text runs). build() splits wires at every connection point, adds the junction
# dots, checks that nothing dangles and compares the exported netlist with CIRCUIT.
WIRES = [
    # Power entry: J5 pin pairs tied left/right, series Schottkys, bulk, HT7550-1, +5VA filter
    ['J5.1', (27.94, 50.8), (27.94, 45.72), (45.72, 45.72), (45.72, 50.8), 'J5.2'],
    [(45.72, 45.72), 'D8.1'], ['D8.2', (83.82, 45.72)],
    ['J5.3', (27.94, 53.34), (27.94, 58.42), 'J5.7'], ['J5.5', (27.94, 55.88)], [(27.94, 58.42), (22.86, 58.42)],
    ['J5.4', (45.72, 53.34), (45.72, 58.42), 'J5.8'], ['J5.6', (45.72, 55.88)], [(45.72, 58.42), (48.26, 58.42)],
    ['J5.9', (27.94, 60.96), (27.94, 66.04), (45.72, 66.04), (45.72, 60.96), 'J5.10'],
    [(45.72, 66.04), 'D7.2'], ['D7.1', 'U1.2'], ['U1.3', 'R1.1'], ['R1.2', (165.1, 66.04)],
    # MCU, UPDI
    ['C8.1', (63.5, 104.14), 'U2.4'], ['U2.19', 'R2.1'], ['R2.2', 'J6.1'],
    ['J6.2', (106.68, 114.3), (106.68, 116.84)],
    ['U2.15', (45.72, 134.62)], ['U2.16', (45.72, 137.16)],
    # Buttons
    ['SW1.1', (33.02, 180.34)], ['SW2.1', (33.02, 193.04)],
    # I2C: FRAM address / WP straps, pull-ups, DAC
    ['U4.1', (129.54, 187.96), (129.54, 198.12)], ['U4.2', (129.54, 190.5)], ['U4.3', (129.54, 193.04)],
    ['U4.5', (154.94, 187.96)], ['U4.6', (154.94, 190.5)], ['U4.7', (154.94, 193.04), (154.94, 198.12)],
    ['U3.2', (175.26, 187.96), 'R3.2'], ['U3.3', (165.1, 190.5), 'R4.2'],
    ['U3.4', (182.88, 193.04), (182.88, 203.2)],
    # U5 supply pins and decoupling
    ['U5.4', (251.46, 175.26), (264.16, 175.26)], ['U5.11', (251.46, 200.66), (264.16, 200.66)],
    ['C18.2', 'C19.1'], [(264.16, 187.96), (269.24, 187.96)],
]
MCU_STUBS = {'20': 114.3, '1': 116.84, '2': 119.38, '5': 121.92, '6': 124.46, '7': 127.0, '8': 129.54,
             '14': 134.62, '13': 137.16, '12': 139.7, '11': 142.24, '10': 144.78}
WIRES += [[f'U2.{pin}', (81.28, y)] for pin, y in MCU_STUBS.items()]
WIRES += [[f'U3.{6 + i}', (218.44, 187.96 + 2.54 * i)] for i in range(4)]
WIRES += [[f'RV{i}.2', (x + 17.78, POT_Y)] for i, x in enumerate(POT_X, 1)]
for i in range(6):
    y = LED_Y0 + i * LED_DY
    WIRES += [[(73.66, y), f'R{5 + i}.1'], [f'R{5 + i}.2', f'D{1 + i}.2']]
for k in range(4):
    y, r0 = Y0 + k * DY, 11 + 4 * k
    plus, minus, out = AMP_PINS[k]
    WIRES += [
        [(X0 - 33.02, y + 2.54), f'R{r0}.1'], [f'R{r0}.2', f'U5.{plus}'],
        [f'U5.{minus}', (X0 - 10.16, y - 2.54), (X0 - 10.16, y - 10.16), f'R{r0 + 2}.1'],
        [f'R{r0 + 2}.2', (X0 + 10.16, y - 10.16), (X0 + 10.16, y)],
        [f'U5.{out}', f'R{r0 + 3}.1'], [f'R{r0 + 3}.2', f'J{k + 1}.T'],
        [f'J{k + 1}.S', (X0 + 43.18, y + 2.54), (X0 + 43.18, y + 5.08)],
    ]

POWER = [
    ('-12V', (53.34, 45.72), 0), ('-12V_F', (83.82, 45.72), 0), ('GND', (22.86, 58.42), 0),
    ('GND', (48.26, 58.42), 0), ('+12V', (53.34, 66.04), 0), ('+12V_F', (86.36, 66.04), 0),
    ('+5V', (124.46, 66.04), 0), ('+5VA', (165.1, 66.04), 0),
    ('GND', 'C2.1', 0), ('GND', 'C1.2', 0), ('GND', 'C3.2', 0), ('GND', 'U1.1', 0),
    ('GND', 'C4.2', 0), ('GND', 'C5.2', 0), ('GND', 'C6.2', 0), ('GND', 'C7.2', 0),
    ('+5V', (53.34, 104.14), 0), ('GND', 'C8.2', 0), ('GND', 'U2.3', 0), ('GND', (106.68, 116.84), 0),
    ('GND', 'SW1.2', 90), ('GND', 'SW2.2', 90),
    ('+5V', 'C9.1', 0), ('GND', 'C9.2', 0), ('+5V', 'U4.8', 0), ('GND', 'U4.4', 0),
    ('GND', (129.54, 198.12), 0), ('GND', (154.94, 198.12), 0),
    ('+5V', 'R4.1', 0), ('+5V', 'R3.1', 0), ('+5VA', 'U3.1', 0), ('GND', 'U3.10', 0),
    ('GND', (182.88, 203.2), 0),
    ('+12V_F', (257.81, 175.26), 0), ('-12V_F', (257.81, 200.66), 180), ('GND', (269.24, 187.96), 0),
]
POWER += [('GND', f'D{1 + i}.1', 90) for i in range(6)]
for i in range(1, 5):
    POWER += [('+5V', f'RV{i}.3', 0), ('GND', f'RV{i}.1', 0), ('GND', f'C{9 + i}.2', 0)]
for k in range(4):
    POWER += [('+5VA', f'R{12 + 4 * k}.1', 0), ('GND', f'C{14 + k}.2', 0),
              ('GND', (X0 + 43.18, Y0 + k * DY + 5.08), 0)]

LABELS = [
    ('UPDI_PA0', (81.28, 111.76), 'R'), ('UPDI', (101.6, 111.76), 'R'),
    ('REC_BTN', (45.72, 134.62), 'L'), ('RANGE_BTN', (45.72, 137.16), 'L'),
    ('REC_BTN', (33.02, 180.34), 'L'), ('RANGE_BTN', (33.02, 193.04), 'L'),
    ('SDA', (154.94, 187.96), 'R'), ('SCL', (154.94, 190.5), 'R'),
    ('SCL', (177.8, 187.96), 'R'), ('SDA', (177.8, 190.5), 'R'),
]
LABELS += [(MCU[pin], (81.28, y), 'R') for pin, y in MCU_STUBS.items()]
LABELS += [(f'DAC{i + 1}', (218.44, 187.96 + 2.54 * i), 'R') for i in range(4)]
LABELS += [(f'POT{i}', (x + 17.78, POT_Y), 'R') for i, x in enumerate(POT_X, 1)]
for i, net in enumerate(LED_NETS):
    LABELS += [(net, (73.66, LED_Y0 + i * LED_DY), 'L'), (f'{net}_A', (86.36, LED_Y0 + i * LED_DY), 'R')]
for k in range(4):
    y, n = Y0 + k * DY, k + 1
    LABELS += [(f'DAC{n}', (X0 - 33.02, y + 2.54), 'L'), (f'FLT{n}', (X0 - 20.32, y + 2.54), 'R'),
               (f'FB{n}', (X0 - 8.89, y - 10.16), 'R'), (f'AMP{n}', (X0 + 11.43, y), 'R'),
               (f'OUT{n}', (X0 + 30.48, y), 'R')]

TEXTS = [
    ((20.32, 17.78), 'BIG MODULAR MOTION - S1 schematic (4-knob motion recorder, 4 CV outs, 6HP). '
                     'Circuit intent: docs/research.md', 2.0),
    ((20.32, 30.48), 'POWER: +12V -> B5819W -> +12V_F (U5 V+, HT7550-1 -> +5V); -12V -> B5819W -> -12V_F (U5 V-).\n'
                     '+5V -> R1 10R / C6 -> +5VA: DAC supply = DAC reference, and the output-stage offset.', 1.4),
    ((20.32, 82.55), 'PWR_FLAG: #FLG01/#FLG04/#FLG05 mark the Eurorack GND/-12V/+12V entry at J5; #FLG02/#FLG03 mark the\n'
                     'protected rails behind D7/D8 and #FLG06 marks +5VA behind R1, which ERC cannot see through.', 1.1),
    ((20.32, 92.71), 'MCU: ATtiny1616 at 5 V, 20 MHz. Knobs PA1/PA2/PA6/PA7 (ADC0). I2C PB0 SCL / PB1 SDA (TWI0, 400 kHz).\n'
                     'LEDs on TCA0 split PWM: PB2 WO2, PA3 WO3, PA4 WO4, PA5 WO5; PB3 WO0 and PB4 WO1 via PORTMUX.\n'
                     'Buttons PC0 / PC1 (internal pull-ups). Spare: PB5, PC2, PC3. UPDI J6: pin 1 UPDI, pin 2 GND.', 1.1),
    ((20.32, 161.29), 'BUTTONS: REC (hold + move a knob = record that knob;\n'
                      'hold 5 s without moving a knob = erase every take), RANGE (click).', 1.1),
    ((60.96, 168.91), 'LEDS: four motion LEDs, REC, RANGE (on = -5..+5 V).\n'
                      '10k: 0.33 mA at full duty, dimmed further by PWM.', 1.1),
    ((114.3, 161.29), 'I2C: MB85RC256V FRAM 0x50 (takes: 2 bytes x 50 frames/s, ~81 s per knob, always saved)\n'
                      'and MCP4728 quad 12-bit DAC 0x60 (VREF = VDD = +5VA, LDAC low). 2.2k pull-ups.', 1.1),
    ((129.54, 104.14), 'KNOBS 1-4: 50k linear dividers +5V..GND into PA1 / PA2 / PA6 / PA7, 10n at each pin.\n'
                       'Idle = plays the take, shifted up / down by the knob; REC held = the knob is recorded.', 1.1),
    ((238.76, 165.1), 'U5 supply: +/-12V_F, 100n each.', 1.1),
    ((289.56, 25.4), 'OUTPUTS 1-4: DAC -> 10k / 100n (160 Hz) -> TL074, gain 2 around +5VA: Vout = 2 x Vdac - (+5VA).\n'
                     'Code 0 = -5 V, 2048 = 0 V, 4095 = +5 V. RANGE is firmware only: 0..+5 V uses codes 2048..4095\n'
                     '(2.4 mV steps), -5..+5 V uses 0..4095. 1k series to the jack, DC coupled.', 1.1),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/motion/schematic/' + key))


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
    if name == 'MCP4728':
        # the unused pin 5 is "RDY/~{BSY}" in the stock library: KiCad escapes the slash in the board's
        # unconnected-(...) net name ({slash}) but not in the netlist, which the shared ref/pin/net parity
        # then reports as a mismatch. One name without a slash keeps both equal.
        def rename(node):
            for item in node:
                if isinstance(item, list):
                    if len(item) > 1 and item[0] == 'name' and item[1] == 'RDY/~{BSY}':
                        item[1] = 'RDY_~{BSY}'
                    rename(item)
        rename(sym)
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
        if key in RENAMED:  # same pinout under another part name: rename the copy and its units
            for item in sym:
                if isinstance(item, list) and item[0] == 'symbol':
                    item[1] = item[1].replace(name, key, 1)
                elif isinstance(item, list) and item[0] == 'property' and item[1] in RENAMED[key]:
                    item[2] = RENAMED[key][item[1]]
            sym[1] = key
            edit = f'renamed from {lib}:{name} (same package and pinout); ' + ', '.join(sorted(RENAMED[key])) + ' set'
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
        '(options "") (descr "MOTION pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - MOTION") (rev "S1") (company "Big Modular")
        (comment 1 "SCHEMATIC S1 - 6HP motion recorder: 4 knobs -> I2C FRAM -> 4 x 12-bit CV out, REC + RANGE")
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
                *([[atom('mirror'), atom('x')]] if p['mirror'] else []),
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
            ox, oy = xform(px, -py if p['mirror'] else py, p['rot'])
            ex, ey = r(x + ox), r(y + oy)
            key = f"{p['ref']}/{n}"
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                continue
            nets.setdefault(net, []).append(key)
            ends[f"{p['ref']}.{n}"] = (ex, ey, net)
    multi = {ref: u for ref, u in units.items() if len(u) > 1}
    assert multi == {'U5': {1, 2, 3, 4, 5}}, multi
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
