"""Generate the 16bit S1 schematic (hardware/16bit.kicad_sch) and its pinned symbols.

Run from modules/16bit:
  python3 -B tools/build_schematic.py

Writes hardware/16BIT.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
plus Bread Modular's PT8211 symbol), hardware/sym-lib-table and the flat root
schematic, then lets `kicad-cli sch upgrade --force` re-save it natively.

CIRCUIT below is docs/research.md section 3: Bread Modular 16bit (RP2350A, W25Q128
flash, APS6404L PSRAM, PT8211 I2S DAC, USB-C for UF2 flashing) moved to a 6HP
Eurorack module: TS MIDI in with the MIDI V2 / 8bit protected front end (JP1 bypass),
two bipolar CV inputs, each through its own attenuator pot (RV1/RV2, jack normalled to +5V so an
unpatched input is a plain knob) and a TL072 buffer, two plain knobs (RV3/RV4), a red mode LED
on a PWM pin (GPIO13, Bread Modular 1k), a 6 x 6 mm THT mode button and two DC-coupled
+/-5 V outputs (TL074).

Drawing: each block is wired (drawing(): polylines whose points are (x, y), 'REF.PIN'
or ('REF.PIN', dx, dy)), with power symbols and net labels naming every net. Pins not
reached by a drawn wire get a short stub closed by a power symbol (rails; neighbouring
stubs of one rail are joined into a bar with one symbol) or a net label: those are the
block-to-block connections (MCU pins, memories). Wires are split at every connection
point and junction dots are added; the build asserts nothing dangles and that the
exported native netlist equals CIRCUIT. Nets named with a leading '_' are short local
links drawn without a label (compared by pins only).

The PCB never reads this table: tools/build_layout.py takes nets, values and footprints
from the native netlist.
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
BM_SCH = Path.home() / 'data/projects/bread-modular/modules/16bit/16bit.kicad_sch'
PROJECT = '16bit'
LIB = '16BIT'
STUB = 2.54
MERGE_GAP = 15.24   # neighbouring rail stubs closer than this share one bar and one symbol

FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
    # Bread Modular footprints (preferred: the user's builds prove them) carry other names.
    'RP2350A': 'RP2350-QFN-60-1EP_7x7_P0.4mm_EP3.4x3.4mm*',
    'APS6404L-3SQRx-SN': 'SOIC-8*Generic',
}

# lib symbol -> (stock library, stock name); 'BM' = embedded symbol of the Bread Modular 16bit schematic
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'L': ('Device', 'L'),
    'LED': ('Device', 'LED'), 'Crystal_GND24': ('Device', 'Crystal_GND24'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'D_Schottky': ('Device', 'D_Schottky'), '1N4148W': ('Diode', '1N4148W'), 'BAT54SW': ('Diode', 'BAT54SW'),
    'MMBT3904': ('Transistor_BJT', 'MMBT3904'),
    'RP2350A': ('MCU_RaspberryPi', 'RP2350A'),
    'W25Q128JVS': ('Memory_Flash', 'W25Q128JVS'),
    'APS6404L-3SQRx-SN': ('Memory_RAM', 'APS6404L-3SQRx-SN'),
    'PT8211': ('BM', 'Audio:PT8211'),
    'TL074': ('Amplifier_Operational', 'TL074'), 'MCP6002-xSN': ('Amplifier_Operational', 'MCP6002-xSN'),
    'TL072': ('Amplifier_Operational', 'TL072'),
    'AMS1117-3.3': ('Regulator_Linear', 'AMS1117-3.3'), 'AMS1117-5.0': ('Regulator_Linear', 'AMS1117-5.0'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'USB_C_Receptacle_USB2.0_14P': ('Connector', 'USB_C_Receptacle_USB2.0_14P'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'SW_Push': ('Switch', 'SW_Push'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+1V1': ('power', '+1V1'), '+3V3': ('power', '+3V3'), '+5V': ('power', '+5V'),
    '+12V': ('power', '+12V'), '-12V': ('power', '-12V'),
}

FP = {
    'R0402': 'R_0402_1005Metric', 'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0402': 'C_0402_1005Metric', 'C0402S': 'C_0402_1005Metric_small_pads', 'C0603': 'C_0603_1608Metric',
    'C0805': 'C_0805_2012Metric', 'C1206': 'C_1206_3216Metric',
    'SOD123': 'D_SOD-123', 'SOT23': 'SOT-23', 'SOT323': 'SOT-323_SC-70', 'SOT223': 'SOT-223-3_TabPin2',
    'QFN60': 'RP2350-QFN-60-1EP_7x7_P0.4mm_EP3.4x3.4mm_ThermalVias', 'L2016': 'L_pol_2016',
    'XTAL3225': 'Crystal_SMD_3225-4Pin_3.2x2.5mm',
    'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm', 'SOIC8W': 'SOIC-8_5.3x5.3mm_P1.27mm', 'SOIC8BM': 'SOIC-8 Generic',
    'SOIC14': 'SOIC-14_3.9x8.7mm_P1.27mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'SWK2': 'K2-1808SN-A4SW-01', 'SW6': 'SW_PUSH_6mm_H7.3mm', 'LED3': 'LED_D3.0mm',
    'USBC': 'USB_C_Receptacle_HRO_TYPE-C-31-M-12', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
}

# Copper-only parts: no BOM row, no CPL row (solder jumpers are bridged by hand).
NOT_ASSEMBLED = {'JP1'}

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', '+1V1': '+1V1', '+3V3': '+3V3', '+5V': '+5V', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V'}

# Symbols drawn mirrored about X (pots: +3V3 up, wiper right, GND down; J1: sleeve at the bottom).
MIRROR_X = {'RV1', 'RV2', 'RV3', 'RV4', 'J1'}

# RP2350A (QFN-60) pin -> net. Bread Modular 16bit GPIO map kept so its firmware ports:
# GPIO0 PSRAM CS, GPIO1-3 I2S to the PT8211, GPIO5 MIDI RX (UART1), GPIO12 mode button,
# GPIO13 mode LED, GPIO26/27 = BM AIN_1/AIN_2 (CV1/CV2, after the RV1/RV2 attenuators),
# GPIO28/29 = BM's knob channels (RV3/RV4). Dropped (left open): GPIO4 MIDI out,
# GPIO19/20 gate outs. SWD is open as on Bread Modular (UF2 over USB).
MCU = {'1': '+3V3', '11': '+3V3', '20': '+3V3', '30': '+3V3', '38': '+3V3', '45': '+3V3',
       '6': '+1V1', '23': '+1V1', '39': '+1V1', '50': '+1V1',
       '44': '+3V3', '46': 'VREG_AVDD', '47': 'GND', '48': 'VREG_LX', '49': '+3V3',
       '53': '+3V3', '54': '+3V3', '61': 'GND',
       '51': 'USB_DM', '52': 'USB_DP', '21': 'XIN', '22': 'XOUT', '26': 'RUN',
       '55': 'QSPI_SD3', '56': 'QSPI_SCLK', '57': 'QSPI_SD0', '58': 'QSPI_SD2', '59': 'QSPI_SD1',
       '60': 'QSPI_SS', '24': None, '25': None,
       '2': 'PSRAM_CS', '3': 'I2S_BCK', '4': 'I2S_WS', '5': 'I2S_DIN', '7': None, '8': 'MIDI_RX',
       '9': None, '10': None, '12': None, '13': None, '14': None, '15': None,
       '16': 'BUTTON', '17': 'LED', '18': None, '19': None,
       '27': None, '28': None, '29': None, '31': None, '32': None, '33': None, '34': None,
       '35': None, '36': None, '37': None,
       '40': 'CV1_ADC', '41': 'CV2_ADC', '42': 'POT3', '43': 'POT4'}

# Block rows (sheet mm).
CV_Y = (223.52, 256.54)                       # CV1 / CV2 signal rows
POT_Y = (233.68, 259.08)                      # RV3 / RV4 wiper rows
CVX = 40.64                                   # level shift / clamp / MCP6002 sit right of the pot + TL072
OPS_Y = 287.02                                # U6 / U7 supply units and decoupling
LED_Y = 236.22                                # mode LED row
OUT_Y = {'L': 102.87, 'R': 71.12}             # DAC_L / DAC_R rows into U5A / U5B
OUT_PARTS = {'L': dict(unit=1, inp='3', inn='2', out='1', rs='R26', cf='C34', rf='R28', rg='R29', ro='R30', j='J4'),
             'R': dict(unit=2, inp='5', inn='6', out='7', rs='R27', cf='C35', rf='R31', rg='R32', ro='R33', j='J5')}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/L: rot 90 = horizontal, pin 1 left; rot 270 = pin 1
    right; rot 0 = vertical, pin 1 on top; rot 180 = pin 1 at the bottom. Diodes: rot 0 = K left."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottkys; +12V_F -> AMS1117-5.0 -> +5V -> AMS1117-3.3 -> +3V3
    c.append(part('J6', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (40.64, 66.04), 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(two('D3', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 55.88), '-12V', '-12V_F', rot=0,
                 Note='-12 V series reverse-polarity protection'))
    c.append(two('D2', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 76.2), '+12V_F', '+12V', rot=180,
                 Note='+12 V series reverse-polarity protection'))
    c.append(two('C2', 'C', '10u', 'C0805', (78.74, 59.69), 'GND', '-12V_F', rot=180, Voltage='25V',
                 Note='-12V_F bulk'))
    c.append(two('C1', 'C', '10u', 'C0805', (78.74, 80.01), '+12V_F', 'GND', rot=0, Voltage='25V',
                 Note='+12V_F bulk'))
    c.append(part('U8', 'AMS1117-5.0', 'AMS1117-5.0', 'SOT223', (124.46, 76.2), 0,
                  {'1': 'GND', '2': '+5V', '3': '+12V_F'},
                  Note='+5V for U9 (+3V3 chain). ~65 mA: ~0.45 W in the SOT-223 (tab on a 4-layer GND pour)'))
    c.append(two('C3', 'C', '22u', 'C0805', (139.7, 80.01), '+5V', 'GND', rot=0, Voltage='25V', Note='U8 output'))
    c.append(part('U9', 'AMS1117-3.3', 'AMS1117-3.3', 'SOT223', (162.56, 76.2), 0,
                  {'1': 'GND', '2': '+3V3', '3': '+5V'}, Note='+3V3 for the RP2350, memories, DAC, CV buffers'))
    c.append(two('C4', 'C', '22u', 'C0805', (177.8, 80.01), '+3V3', 'GND', rot=0, Voltage='25V', Note='U9 output'))
    c.append(two('C19', 'C', '10u', 'C0805', (187.96, 80.01), '+3V3', 'GND', rot=0, Voltage='25V',
                 Note='+3V3 bulk (Bread Modular C19)'))
    c.append(two('C21', 'C', '100u', 'C1206', (198.12, 80.01), '+3V3', 'GND', rot=0, Voltage='6.3V',
                 Note='+3V3 reservoir (Bread Modular C21)'))
    for ref, net, at, rot in (('#FLG01', 'GND', (30.48, 68.58), 0), ('#FLG02', '+12V_F', (71.12, 76.2), 180),
                              ('#FLG03', '-12V_F', (71.12, 55.88), 180), ('#FLG04', '+12V', (53.34, 76.2), 180),
                              ('#FLG05', '-12V', (53.34, 55.88), 180), ('#FLG06', '+1V1', (312.42, 96.52), 180),
                              ('#FLG07', 'VREG_AVDD', (313.69, 55.88), 0)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))

    # ---- RP2350A core, as Bread Modular 16bit (RP2350 minimal design)
    c.append(part('U1', 'RP2350A', 'RP2350A', 'QFN60', (279.4, 152.4), 0, MCU,
                  Note='Bread Modular 16bit MCU, 12 MHz crystal, internal core regulator'))
    for ref, x in (('C5', 228.6), ('C6', 238.76), ('C7', 248.92), ('C8', 259.08),
                   ('C9', 269.24), ('C10', 279.4), ('C11', 289.56)):
        c.append(two(ref, 'C', '100n', 'C0402', (x, 83.82), '+3V3', 'GND', rot=0, Voltage='16V',
                     Note='U1 IOVDD/ADC_AVDD/QSPI_IOVDD/USB_OTP_VDD decoupling (one per supply pin)'))
    c.append(two('C12', 'C', '4.7u', 'C0402S', (299.72, 83.82), '+3V3', 'GND', rot=0, Voltage='10V',
                 Note='VREG_VIN (Bread Modular C6)'))
    c.append(two('L1', 'L', '3.3u', 'L2016', (304.8, 96.52), 'VREG_LX', '+1V1',
                 Note='Core regulator inductor. Bread Modular L1 / RP2350 reference AOTA-B201610S3R3-101-T is '
                      'out of stock at LCSC; cjiang FTC201610S3R3MBCA meets its L/DCR/Isat/shielding but has no '
                      'polarity mark (orientation random): check the core regulator at bring-up'))
    for ref, x, val, fp, note in (('C13', 320.04, '4.7u', 'C0402S', 'Core regulator output (Bread Modular C7)'),
                                  ('C14', 330.2, '4.7u', 'C0402', 'DVDD (Bread Modular C10)'),
                                  ('C15', 340.36, '100n', 'C0402', 'DVDD decoupling'),
                                  ('C16', 350.52, '100n', 'C0402', 'DVDD decoupling')):
        c.append(two(ref, 'C', val, fp, (x, 83.82), '+1V1', 'GND', rot=0, Voltage='10V', Note=note))
    c.append(two('R4', 'R', '33', 'R0402', (304.8, 55.88), '+3V3', 'VREG_AVDD',
                 Note='VREG_AVDD filter (Bread Modular R5)'))
    c.append(two('C17', 'C', '4.7u', 'C0402', (320.04, 59.69), 'VREG_AVDD', 'GND', rot=0, Voltage='10V',
                 Note='VREG_AVDD filter (Bread Modular C9)'))
    # Crystal: 12 MHz, 1k on XOUT, 15p loads (Bread Modular Y1/R2/C3/C4)
    c.append(part('Y1', 'Crystal_GND24', '12MHz', 'XTAL3225', (215.9, 180.34), 0,
                  {'1': 'XIN', '2': 'GND', '3': '_XTAL_R', '4': 'GND'}, MPN='ABM8-272-T3',
                  Note='12 MHz (Bread Modular Y1)'))
    c.append(two('R5', 'R', '1k', 'R0402', (226.06, 176.53), 'XOUT', '_XTAL_R', rot=0,
                 Note='XOUT series (Bread Modular R2)'))
    c.append(two('C18', 'C', '15p', 'C0402', (208.28, 184.15), 'XIN', 'GND', rot=0, Voltage='50V',
                 Note='Crystal load'))
    c.append(two('C20', 'C', '15p', 'C0402', (223.52, 184.15), '_XTAL_R', 'GND', rot=0, Voltage='50V',
                 Note='Crystal load'))
    # RUN (reset) and BOOT (QSPI_SS low at reset = USB bootloader), Bread Modular SW1/SW3
    c.append(part('SW3', 'SW_Push', 'RUN', 'SWK2', (200.66, 114.3), 0, {'1': '_RUN_R', '2': 'RUN'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='Reset (Bread Modular SW1 RESET), B side next to the USB-C'))
    c.append(two('R6', 'R', '1k', 'R0402', (185.42, 114.3), 'GND', '_RUN_R', Note='Bread Modular R4'))
    c.append(part('SW2', 'SW_Push', 'BOOT', 'SWK2', (200.66, 129.54), 0, {'1': '_BOOT_R', '2': 'GND'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='BOOTSEL (Bread Modular SW3 BOOT): hold while pressing RUN for UF2 mode'))
    c.append(two('R7', 'R', '1k', 'R0402', (185.42, 129.54), '_BOOT_R', 'QSPI_SS', rot=270,
                 Note='Bread Modular R6'))

    # ---- Flash and PSRAM on QSPI (Bread Modular U2/U5)
    c.append(part('U2', 'W25Q128JVS', 'W25Q128JVS', 'SOIC8W', (373.38, 101.6), 0,
                  {'1': 'QSPI_SS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND', '5': 'QSPI_SD0',
                   '6': 'QSPI_SCLK', '7': 'QSPI_SD3', '8': '+3V3'}, Note='16 MB program flash (Bread Modular U2)'))
    c.append(two('C22', 'C', '100n', 'C0402', (393.7, 93.98), '+3V3', 'GND', rot=0, Voltage='16V',
                 Note='U2 decoupling'))
    c.append(part('U3', 'APS6404L-3SQRx-SN', 'APS6404L-3SQR-SN', 'SOIC8BM', (373.38, 152.4), 0,
                  {'1': 'PSRAM_CS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND', '5': 'QSPI_SD0',
                   '6': 'QSPI_SCLK', '7': 'QSPI_SD3', '8': '+3V3'},
                  Note='8 MB QSPI PSRAM (Bread Modular U5 "PSRAM", BM SOIC-8 Generic footprint), CS on GPIO0'))
    c.append(two('C23', 'C', '100n', 'C0402', (393.7, 144.78), '+3V3', 'GND', rot=0, Voltage='16V',
                 Note='U3 decoupling'))
    c.append(two('R8', 'R', '10k', 'R0402', (403.86, 162.56), '+3V3', 'PSRAM_CS', rot=0,
                 Note='PSRAM CS idle pull-up (Bread Modular R14)'))

    # ---- USB-C (UF2 flashing, data only; VBUS is not used: power the module from the rack)
    c.append(part('J7', 'USB_C_Receptacle_USB2.0_14P', 'USB-C', 'USBC', (124.46, 172.72), 0,
                  {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
                   'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
                   'A5': 'CC1', 'B5': 'CC2', 'A6': '_USB_CONN_DP', 'B6': '_USB_CONN_DP',
                   'A7': '_USB_CONN_DM', 'B7': '_USB_CONN_DM', 'SH': '_USB_SHIELD'},
                  MPN='TYPE-C-31-M-12', Manufacturer='HRO',
                  Note='Bread Modular J5. Data only, as Bread Modular: VBUS is not connected to any rail'))
    c.append(two('R9', 'R', '27', 'R0402', (154.94, 180.34), '_USB_CONN_DP', 'USB_DP', Note='Bread Modular R7'))
    c.append(two('R10', 'R', '27', 'R0402', (154.94, 170.18), '_USB_CONN_DM', 'USB_DM', Note='Bread Modular R8'))
    c.append(two('R11', 'R', '5.1k', 'R0402', (180.34, 154.94), 'CC1', 'GND', rot=0, Note='UFP Rd (Bread Modular R3)'))
    c.append(two('R12', 'R', '5.1k', 'R0402', (190.5, 154.94), 'CC2', 'GND', rot=0, Note='UFP Rd (Bread Modular R11)'))
    c.append(two('C24', 'C', '10n', 'C0402', (116.84, 204.47), '_USB_SHIELD', 'GND', rot=0, Voltage='50V',
                 Note='Shield to GND (Bread Modular C20)'))

    # ---- MIDI input (TS): the MIDI V2 / 8bit NPN front end at 3.3 V, JP1 bypass
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (22.86, 152.4), 0,
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(two('R3', 'R', '100k', 'R0603', (43.18, 148.59), 'MIDI_IN', '+3V3', rot=180, Note='Idle pull-up'))
    c.append(two('R1', 'R', '10k', 'R0603', (53.34, 152.4), 'MIDI_IN', '_Q1_B',
                 Note='Base resistor: 0.26 mA from a 3.3 V sender, ~1.1 mA at +/-12 V'))
    c.append(two('D4', '1N4148W', '1N4148W', 'SOD123', (63.5, 158.75), '_Q1_B', 'GND', rot=270,
                 Note='Clamps Q1 B-E for a negative input'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23', (73.66, 152.4), 0, {'1': '_Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting buffer: input high = RX low. Firmware: invert GPIO5 input (gpio_set_inover)'))
    c.append(two('R2', 'R', '22k', 'R0603', (76.2, 138.43), 'RX_Q', '+3V3', rot=180,
                 Note='Q1 collector pull-up to +3V3'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3', (93.98, 142.24), 0,
                  {'1': 'RX_Q', '2': 'MIDI_RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. 1-2 = protected (Q1 drives GPIO5, input '
                       'inverted in firmware). 2-3 = direct/unprotected (stock BM 16bit firmware). Never both'))

    # ---- CV inputs: jack -> RV1/RV2 attenuator (tip normalled to +5V: unpatched = 0..+5 V knob) -> U7 TL072
    # follower on +/-12 V (the pot sees no load) -> 100k / 56k to +3V3 / 120k to GND maps -5.9..+6.0 V onto
    # 0..3.3 V (Zin ~138k), BAT54SW clamp, 1n, MCP6002 rail-to-rail follower on +3V3 -> ADC0/ADC1 (BM AIN_1/AIN_2)
    for i, (y, jack, rv, rin, rup, rdn, d, cf) in enumerate(zip(CV_Y, ('J2', 'J3'), ('RV1', 'RV2'), ('R13', 'R16'),
                                                                ('R14', 'R17'), ('R15', 'R18'), ('D5', 'D6'),
                                                                ('C25', 'C26')), 1):
        c.append(part(jack, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (22.86, y), 0,
                      {'T': f'CV{i}_IN', 'S': 'GND', 'TN': '+5V'},
                      Note=f'CV{i} in, about -5.9..+6.0 V. Tip normalled to +5V: unpatched, RV{i} is a 0..+5 V knob'))
        c.append(part(rv, 'R_Potentiometer', '50k', 'RV09', (45.72, y + 3.81), 0,
                      {'1': 'GND', '2': f'_CV{i}_POT', '3': f'CV{i}_IN'},
                      Note=f'CV{i} attenuator: RV09 9 mm vertical, linear (user stock). CW = full CV (or +5 V '
                           f'unpatched). Hand-soldered'))
        unit = dict(unit=i)
        pins = {'3': f'_CV{i}_POT', '2': f'CV{i}_AMP', '1': f'CV{i}_AMP'} if i == 1 else \
            {'5': f'_CV{i}_POT', '6': f'CV{i}_AMP', '7': f'CV{i}_AMP'}
        c.append(part('U7', 'TL072', 'TL072', 'SOIC8', (60.96, y + 6.35), 0, pins, **unit,
                      Note='Attenuator buffers on +/-12 V: the 138k level shift would otherwise load the 50k wiper'))
        c.append(two(rin, 'R', '100k', 'R0603', (45.72 + CVX, y), f'CV{i}_AMP', f'CV{i}_BUF',
                     Note='Level-shift input. Zin = 100k + 56k||120k = 138k. Clamp current <= 0.09 mA at +/-12 V'))
        c.append(two(rup, 'R', '56k', 'R0603', (53.34 + CVX, y - 3.81), '+3V3', f'CV{i}_BUF', rot=0,
                     Note='Level-shift offset: 0 V CV -> 1.63 V. +3V3 is also the ADC reference'))
        c.append(two(rdn, 'R', '120k', 'R0603', (60.96 + CVX, y + 3.81), f'CV{i}_BUF', 'GND', rot=0,
                     Note='Level-shift: V(CV_BUF) = 0.276 x Vin + 1.628 V'))
        c.append(two(cf, 'C', '1n', 'C0603', (68.58 + CVX, y + 3.81), f'CV{i}_BUF', 'GND', rot=0, Voltage='50V',
                     Note='With the 27.6k Thevenin: 5.8 kHz CV low-pass'))
        c.append(part(d, 'BAT54SW', 'BAT54SW', 'SOT323', (83.82 + CVX, y - 5.08), 0,
                      {'1': 'GND', '2': '+3V3', '3': f'CV{i}_BUF'},
                      Note='Clamp: holds the op-amp input within -0.3..+3.6 V'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', (106.68 + CVX, CV_Y[0] + 2.54), 0,
                  {'3': 'CV1_BUF', '2': 'CV1_ADC', '1': 'CV1_ADC'}, unit=1,
                  Note='CV buffers on +3V3 (Bread Modular U3 MCP6002): ADC pins only ever see 0..3.3 V'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', (106.68 + CVX, CV_Y[1] + 2.54), 0,
                  {'5': 'CV2_BUF', '6': 'CV2_ADC', '7': 'CV2_ADC'}, unit=2))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', (137.16, OPS_Y), 0,
                  {'4': 'GND', '8': '+3V3'}, unit=3))
    c.append(two('C27', 'C', '100n', 'C0603', (144.78, OPS_Y), '+3V3', 'GND', rot=0, Voltage='50V',
                 Note='U6 decoupling'))
    c.append(part('U7', 'TL072', 'TL072', 'SOIC8', (91.44, OPS_Y), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(two('C28', 'C', '100n', 'C0603', (99.06, OPS_Y - 3.81), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U7 V+ decoupling'))
    c.append(two('C29', 'C', '100n', 'C0603', (99.06, OPS_Y + 3.81), 'GND', '-12V_F', rot=0, Voltage='50V',
                 Note='U7 V- decoupling'))

    # ---- Knobs 3/4 (50k linear dividers on +3V3) -> ADC2/ADC3 (Bread Modular's two knob channels)
    for i, (rv, cap, y) in enumerate(zip(('RV3', 'RV4'), ('C30', 'C31'), POT_Y), 3):
        c.append(part(rv, 'R_Potentiometer', '50k', 'RV09', (198.12, y), 0,
                      {'1': 'GND', '2': f'POT{i}', '3': '+3V3'},
                      Note=f'Knob {i}: RV09 9 mm vertical, linear (user stock). CW = +3V3. Hand-soldered'))
        c.append(two(cap, 'C', '10n', 'C0603', (208.28, y + 3.81), f'POT{i}', 'GND', rot=0, Voltage='50V',
                     Note='Wiper noise filter / ADC sample charge'))

    # ---- Mode button (Bread Modular SW2, GPIO12) and red mode LED (Bread Modular D1: GPIO13 -> 1k -> LED)
    c.append(part('SW1', 'SW_Push', 'MODE', 'SW6', (337.82, 210.82), 0, {'1': 'BUTTON', '2': 'GND'},
                  MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Mode button (Bread Modular SW2, GPIO12 internal pull-up), as modules/8bit SW1: generic '
                       '6 x 6 mm THT tact, 7 mm tall, pins 6.5 x 4.5 mm. Hand-soldered on the F side; pressed '
                       'through the panel by the modules/8bit printed cap'))
    c.append(two('R20', 'R', '1k', 'R0603', (345.44, LED_Y), 'LED', '_LED_A',
                 Note='Mode LED current (Bread Modular 1k), ~1.3 mA at 3.3 V'))
    c.append(two('D1', 'LED', 'LED_3mm_red', 'LED3', (360.68, LED_Y), 'GND', '_LED_A', rot=180,
                 Note='Mode LED: 3 mm red (as modules/8bit D1). GPIO13 PWM sets the brightness. Hand-soldered THT'))
    # ---- PT8211 I2S DAC (Bread Modular U4) with BM's 1k/10n output filters
    c.append(part('U4', 'PT8211', 'PT8211', 'SOIC8', (441.96, 101.6), 270,
                  {'1': 'I2S_BCK', '2': 'I2S_WS', '3': 'I2S_DIN', '4': 'GND', '5': '+3V3',
                   '6': 'DAC_L', '7': None, '8': 'DAC_R'}, Note='16-bit stereo I2S DAC (Bread Modular U4)'))
    c.append(two('C33', 'C', '100n', 'C0402', (454.66, 115.57), '+3V3', 'GND', rot=0, Voltage='16V',
                 Note='U4 decoupling'))

    # ---- Outputs: U5A/U5B gain 6.1 with -5.1 x VOFF (1.98 V). The PT8211 full scale is ~0.5 x VDD
    # (2.5 Vpp typ at 5 V), so 1.65 V +/-0.825 V at 3.3 V -> 0 V +/-5.0 V (~10 Vpp Eurorack)
    for ch, y in OUT_Y.items():
        o = OUT_PARTS[ch]
        c.append(two(o['rs'], 'R', '1k', 'R0603', (463.55, y), f'DAC_{ch}', f'DAC_{ch}F',
                     Note='Bread Modular R17/R18'))
        c.append(two(o['cf'], 'C', '10n', 'C0603', (471.17, y + 3.81), f'DAC_{ch}F', 'GND', rot=0, Voltage='50V',
                     Note='Bread Modular C22/C23: 16 kHz low-pass'))
        c.append(part('U5', 'TL074', 'TL074', 'SOIC14', (487.68, y + 2.54), 0,
                      {o['inp']: f'DAC_{ch}F', o['inn']: f'FB_{ch}', o['out']: f'AMP_{ch}'}, unit=o['unit'],
                      Note='Output stage on +/-12 V'))
        c.append(two(o['rf'], 'R', '51k', 'R0603', (487.68, y + 12.7), f'FB_{ch}', f'AMP_{ch}',
                     Note='Rf: gain 1 + 51k/10k = 6.1'))
        c.append(two(o['rg'], 'R', '10k', 'R0603', (477.52, y + 16.51), 'VOFF', f'FB_{ch}', rot=180,
                     Note='Rg to the offset'))
        c.append(two(o['ro'], 'R', '1k', 'R1206', (505.46, y + 2.54), f'AMP_{ch}', f'OUT_{ch}', Power='0.5W',
                     Note='Output series: short / mis-patch limit; 0.5 W for a permanent +/-12 V mis-patch'))
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (528.32, y + 2.54), 180,
                      {'T': f'OUT_{ch}', 'S': 'GND', 'TN': None}, Note=f'Out {ch}, Eurorack level (~10 Vpp)'))
    c.append(part('U5', 'TL074', 'TL074', 'SOIC14', (487.68, 152.4), 0,
                  {'10': 'VREF_DIV', '9': 'VOFF', '8': 'VOFF'}, unit=3))
    c.append(two('R34', 'R', '10k', 'R0603', (469.9, 146.05), '+3V3', 'VREF_DIV', rot=0, Note='Offset divider top'))
    c.append(two('R35', 'R', '15k', 'R0603', (464.82, 153.67), 'VREF_DIV', 'GND', rot=0,
                 Note='Offset divider bottom: 3.3 x 15/25 = 1.98 V = 6.1/5.1 x DAC mid-scale'))
    c.append(two('C36', 'C', '10u', 'C0805', (459.74, 153.67), 'VREF_DIV', 'GND', rot=0, Voltage='25V',
                 Note='Filters +3V3 noise off the offset (2 Hz)'))
    c.append(part('U5', 'TL074', 'TL074', 'SOIC14', (487.68, 175.26), 0,
                  {'12': 'GND', '13': '_U5D_OUT', '14': '_U5D_OUT'}, unit=4))
    c.append(part('U5', 'TL074', 'TL074', 'SOIC14', (525.78, 165.1), 0,
                  {'4': '+12V_F', '11': '-12V_F'}, unit=5))
    c.append(two('C37', 'C', '100n', 'C0603', (533.4, 161.29), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U5 V+ decoupling'))
    c.append(two('C38', 'C', '100n', 'C0603', (533.4, 168.91), 'GND', '-12V_F', rot=0, Voltage='50V',
                 Note='U5 V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # Power entry: J6 pin pairs tied left/right (as modules/8bit), series Schottkys, LDO chain
    W += [['J6.1', (33.02, 60.96), (33.02, 55.88), (50.8, 55.88), (50.8, 60.96), 'J6.2'], [(50.8, 55.88), 'D3.1'],
          ['J6.3', (33.02, 63.5), (33.02, 68.58), 'J6.7'], ['J6.5', (33.02, 66.04)], [(33.02, 68.58), (27.94, 68.58)],
          ['J6.4', (50.8, 63.5), (50.8, 68.58), 'J6.8'], ['J6.6', (50.8, 66.04)], [(50.8, 68.58), (53.34, 68.58)],
          ['J6.9', (33.02, 71.12), (33.02, 76.2), (50.8, 76.2), (50.8, 71.12), 'J6.10'], [(50.8, 76.2), 'D2.2'],
          ['D3.2', (86.36, 55.88)], ['D2.1', 'U8.3'], ['U8.2', 'U9.3'], ['U9.2', (205.74, 76.2)]]
    P += [('-12V', (55.88, 55.88), 0), ('GND', (27.94, 68.58), 0), ('GND', (53.34, 68.58), 90),
          ('+12V', (55.88, 76.2), 0), ('-12V_F', (86.36, 55.88), 0), ('+12V_F', (88.9, 76.2), 0),
          ('+5V', (147.32, 76.2), 0), ('+3V3', (205.74, 76.2), 0)]
    # RP2350 core regulator and VREG_AVDD filter
    W += [['L1.2', (316.23, 96.52)], ['R4.2', (325.12, 55.88)]]
    P += [('+1V1', (316.23, 96.52), 0)]
    L += [('VREG_AVDD', (325.12, 55.88), 'R')]
    # Crystal
    W += [['Y1.1', (203.2, 180.34), (203.2, 167.64), 'U1.21'], ['Y1.3', 'R5.2'],
          ['R5.1', (226.06, 170.18), (241.3, 170.18), (241.3, 177.8), 'U1.22'],
          ['C18.2', (208.28, 190.5), (223.52, 190.5), 'C20.2'], ['Y1.2', (215.9, 190.5)], [(208.28, 190.5), (208.28, 193.04)]]
    P += [('GND', (208.28, 193.04), 0)]
    L += [('XIN', (205.74, 167.64), 'R'), ('XOUT', (228.6, 170.18), 'R')]
    # RUN / BOOT
    W += [['R6.2', 'SW3.1'], ['SW3.2', (243.84, 114.3), (243.84, 129.54), 'U1.26'], ['R7.1', 'SW2.1']]
    L += [('RUN', (215.9, 114.3), 'R')]
    # USB-C data pairs, shield
    W += [['J7.A7', 'R10.1'], ['J7.B7', (144.78, 172.72), (144.78, 170.18)],
          ['J7.A6', (147.32, 175.26), (147.32, 180.34), 'R9.1'], ['J7.B6', (147.32, 177.8)],
          ['R10.2', (167.64, 170.18), (167.64, 137.16), 'U1.51'],
          ['R9.2', (172.72, 180.34), (172.72, 139.7), 'U1.52'], ['J7.SH', 'C24.1']]
    L += [('USB_DM', (190.5, 137.16), 'R'), ('USB_DP', (220.98, 139.7), 'R')]
    # MIDI in
    W += [['J1.T', 'R1.1'], ['J1.S', (30.48, 154.94), (30.48, 157.48)], ['R1.2', 'Q1.1'], ['D4.1', (63.5, 152.4)], ['Q1.3', 'R2.1'], [(76.2, 142.24), 'JP1.1'],
          ['JP1.2', (93.98, 149.86), (99.06, 149.86)],
          ['JP1.3', (101.6, 142.24), (101.6, 124.46), (46.99, 124.46), (46.99, 152.4)]]
    P += [('GND', (30.48, 157.48), 0)]
    L += [('MIDI_IN', (55.88, 124.46), 'R'), ('RX_Q', (80.01, 142.24), 'R'), ('MIDI_RX', (99.06, 149.86), 'R')]
    # CV inputs: jack tip -> RV attenuator top, wiper -> U7 follower -> level shift / clamp -> U6 follower
    for i, y in enumerate(CV_Y, 1):
        jack, rv, rin, d = ('J2', 'RV1', 'R13', 'D5') if i == 1 else ('J3', 'RV2', 'R16', 'D6')
        inp, inn, out = ('U6.3', 'U6.2', 'U6.1') if i == 1 else ('U6.5', 'U6.6', 'U6.7')
        ainp, ainn, aout = ('U7.3', 'U7.2', 'U7.1') if i == 1 else ('U7.5', 'U7.6', 'U7.7')
        W += [[f'{jack}.T', f'{rv}.3'], [f'{jack}.S', (30.48, y - 2.54), (30.48, y - 5.08), (33.02, y - 5.08)],
              [f'{jack}.TN', (30.48, y + 2.54), (30.48, y + 5.08)], [f'{rv}.2', ainp],
              [aout, (71.12, y + 6.35), (71.12, y), f'{rin}.1'],
              [(71.12, y + 6.35), (71.12, y + 12.7), (50.8, y + 12.7), (50.8, y + 8.89), ainn],
              [f'{rin}.2', inp], [f'{d}.2', (132.08, y - 10.16)],
              [out, (157.48, y + 2.54), (157.48, y + 10.16), (137.16, y + 10.16), (137.16, y + 5.08), inn],
              [(157.48, y + 2.54), (162.56, y + 2.54)]]
        P += [('+3V3', (132.08, y - 10.16), 0), ('GND', (33.02, y - 5.08), 90), ('+5V', (30.48, y + 5.08), 180)]
        L += [(f'CV{i}_IN', (35.56, y), 'R'), (f'CV{i}_AMP', (71.12, y), 'R'), (f'CV{i}_BUF', (113.03, y), 'R'),
              (f'CV{i}_ADC', (162.56, y + 2.54), 'R')]
    # Knobs 3/4: wiper -> hold cap -> label
    for i, y in zip((3, 4), POT_Y):
        W += [[f'RV{i}.2', f'C{27 + i}.1'], [f'C{27 + i}.1', (215.9, y)]]
        L += [(f'POT{i}', (215.9, y), 'R')]
    # U7 decoupling: shared GND node to the side, clear of C29
    W += [['C28.2', (104.14, OPS_Y)]]
    P += [('GND', (104.14, OPS_Y), 90)]
    # Mode LED: GPIO13 -> R20 -> D1 -> GND
    W += [['R20.1', (335.28, LED_Y)], ['R20.2', 'D1.2'], ['D1.1', (370.84, LED_Y), (370.84, LED_Y + 5.08)]]
    P += [('GND', (370.84, LED_Y + 5.08), 0)]
    L += [('LED', (335.28, LED_Y), 'L')]
    # DAC and outputs
    W += [['U4.4', (431.8, 105.41), (431.8, 110.49)], ['U4.5', (454.66, 105.41), (454.66, 111.76)], [(454.66, 109.22), (459.74, 109.22)],
          ['U4.6', 'R26.1'], ['U4.8', (454.66, 97.79), (454.66, OUT_Y['R']), 'R27.1']]
    P += [('+3V3', (459.74, 109.22), 270), ('GND', (431.8, 110.49), 0)]
    L += [('DAC_L', (450.85, 102.87), 'R'), ('DAC_R', (454.66, 85.09), 'U')]
    for ch, y in OUT_Y.items():
        o = OUT_PARTS[ch]
        u = lambda n: f'U5.{n}'  # noqa: E731
        W += [[f"{o['rs']}.2", u(o['inp'])],
              [u(o['inn']), (477.52, y + 5.08), (477.52, y + 12.7), f"{o['rf']}.1"],
              [f"{o['rf']}.2", (497.84, y + 12.7), (497.84, y + 2.54)],
              [u(o['out']), f"{o['ro']}.1"], [f"{o['ro']}.2", f"{o['j']}.T"],
              [f"{o['rg']}.1", (477.52, y + 22.86), (472.44, y + 22.86)],
              [f"{o['j']}.S", (520.7, y + 5.08), (520.7, y + 7.62)]]
        P += [('GND', (520.7, y + 7.62), 0)]
        L += [(f'DAC_{ch}F', (467.36, y), 'R'), (f'FB_{ch}', (477.52, y + 8.89), 'R'),
              (f'AMP_{ch}', (497.84, y + 7.62), 'R'), (f'OUT_{ch}', (513.08, y + 2.54), 'R'),
              ('VOFF', (472.44, y + 22.86), 'L')]
    # Offset reference, spare amplifier, op-amp supply
    W += [['U5.10', (459.74, 149.86)], ['U5.9', (477.52, 154.94), (477.52, 160.02), (497.84, 160.02), (497.84, 152.4)],
          ['U5.8', (502.92, 152.4)],
          ['U5.14', (497.84, 175.26), (497.84, 182.88), (477.52, 182.88), (477.52, 177.8), 'U5.13'],
          ['U5.4', 'C37.1'], ['U5.11', 'C38.2'], ['C37.2', (546.1, 165.1)]]
    P += [('+12V_F', (528.32, 157.48), 0), ('-12V_F', (528.32, 172.72), 180), ('GND', (546.1, 165.1), 0)]
    L += [('VREF_DIV', (459.74, 149.86), 'U'), ('VOFF', (502.92, 152.4), 'R')]
    return W, P, L


# JLCPCB parts (LCSC codes checked live for the 2026-10-21 export, research/export-1/catalog).
# Every R/C is JLCPCB Basic except the 27R USB resistors (no Basic 27R 0402). The THT jacks,
# pots, LED, MODE switch and power header are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C4410', MPN='1206W4F1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R0402'): dict(LCSC='C25105', MPN='0402WGF330JTCE', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0402'): dict(LCSC='C11702', MPN='0402WGF1001TCE', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0402'): dict(LCSC='C25744', MPN='0402WGF1002TCE', Manufacturer='UNI-ROYAL'),
    ('R', '27', 'R0402'): dict(LCSC='C25100', MPN='0402WGF270JTCE', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0402'): dict(LCSC='C25905', MPN='0402WGF5101TCE', Manufacturer='UNI-ROYAL'),
    ('R', '120k', 'R0603'): dict(LCSC='C25808', MPN='0603WAF1203T5E', Manufacturer='UNI-ROYAL'),
    ('R', '51k', 'R0603'): dict(LCSC='C23196', MPN='0603WAF5102T5E', Manufacturer='UNI-ROYAL'),
    ('R', '15k', 'R0603'): dict(LCSC='C22809', MPN='0603WAF1502T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('C', '1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung'),
    ('C', '10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '100n', 'C0402'): dict(LCSC='C1525', MPN='CL05B104KO5NNNC', Manufacturer='Samsung'),
    ('C', '4.7u', 'C0402'): dict(LCSC='C23733', MPN='CL05A475MP5NRNC', Manufacturer='Samsung'),
    ('C', '4.7u', 'C0402S'): dict(LCSC='C23733', MPN='CL05A475MP5NRNC', Manufacturer='Samsung'),
    ('C', '15p', 'C0402'): dict(LCSC='C1548', MPN='0402CG150J500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '10n', 'C0402'): dict(LCSC='C15195', MPN='CL05B103KB5NNNC', Manufacturer='Samsung'),
    ('C', '22u', 'C0805'): dict(LCSC='C45783', MPN='CL21A226MAQNNNE', Manufacturer='Samsung'),
    ('C', '100u', 'C1206'): dict(LCSC='C15008', MPN='CL31A107MQHNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
    ('L', '3.3u', 'L2016'): dict(LCSC='C5832345', MPN='FTC201610S3R3MBCA', Manufacturer='cjiang (Changjiang Micro)'),
    ('Crystal_GND24', '12MHz', 'XTAL3225'): dict(LCSC='C20625731', MPN='ABM8-272-T3', Manufacturer='Abracon'),
    ('SW_Push', 'RUN', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('SW_Push', 'BOOT', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('USB_C_Receptacle_USB2.0_14P', 'USB-C', 'USBC'): dict(LCSC='C165948', MPN='TYPE-C-31-M-12',
                                                          Manufacturer='Korean Hroparts Elec'),
    ('RP2350A', 'RP2350A', 'QFN60'): dict(LCSC='C42411118', MPN='RP2350A', Manufacturer='Raspberry Pi'),
    ('W25Q128JVS', 'W25Q128JVS', 'SOIC8W'): dict(LCSC='C97521', MPN='W25Q128JVSIQ', Manufacturer='Winbond'),
    ('APS6404L-3SQRx-SN', 'APS6404L-3SQR-SN', 'SOIC8BM'): dict(LCSC='C5333729', MPN='APS6404L-3SQR-SN',
                                                              Manufacturer='AP Memory'),
    # PT8211 (C92004) is out of stock; Bread Modular 16bit-5v uses this pin-compatible SOP-8 TM8211.
    ('PT8211', 'PT8211', 'SOIC8'): dict(LCSC='C22381766', MPN='TM8211-TA2302', Manufacturer='Titan Micro (TM)'),
    ('TL074', 'TL074', 'SOIC14'): dict(LCSC='C12594', MPN='TL074CDR', Manufacturer='Texas Instruments'),
    ('TL072', 'TL072', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
    ('MCP6002-xSN', 'MCP6002', 'SOIC8'): dict(LCSC='C7377', MPN='MCP6002T-I/SN', Manufacturer='Microchip'),
    ('AMS1117-5.0', 'AMS1117-5.0', 'SOT223'): dict(LCSC='C6187', MPN='AMS1117-5.0', Manufacturer='AMS'),
    ('AMS1117-3.3', 'AMS1117-3.3', 'SOT223'): dict(LCSC='C6186', MPN='AMS1117-3.3', Manufacturer='AMS'),
}

# Block titles (drawn as sheet text).
TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR 16BIT - S1 schematic (Bread Modular 16bit for Eurorack, 6HP, 4 layers). '
                     'Circuit intent: docs/research.md; placement: docs/geometry.json', 2.0),
    ((20.32, 33.02), 'POWER: +12V -> D2 -> +12V_F (U5 V+, U8 AMS1117-5.0 -> +5V -> U9 AMS1117-3.3 -> +3V3); '
                     '-12V -> D3 -> -12V_F (U5 V-)', 1.4),
    ((20.32, 101.6), 'PWR_FLAG: GND/+12V/-12V mark the Eurorack entry at J6; +12V_F/-12V_F are fed only through D2/D3;\n'
                      '+1V1 (core regulator via L1) and VREG_AVDD (via R4) are fed through passive parts.', 1.1),
    ((20.32, 116.84), 'MIDI IN (TS): MIDI V2 / 8bit NPN front end at 3.3 V, no opto', 1.4),
    ((20.32, 180.34), 'JP1 RX SOURCE (back, shipped OPEN, bridge one pair): 1-2 = PROTECTED (Q1 drives GPIO5,\n'
                      'firmware inverts the input); 2-3 = DIRECT (unprotected, stock BM 16bit firmware). Never both.', 1.1),
    ((20.32, 203.2), 'CV IN 1/2: tip normalled to +5V -> RV1/RV2 50k attenuator -> U7 TL072 follower\n'
                     '-> 100k / 56k to +3V3 / 120k to GND, BAT54SW clamp, 1n -> U6 MCP6002 follower -> ADC0/ADC1.\n'
                     'Unpatched: RV = 0..+5 V knob. Patched: RV scales the CV. -5.9..+6.0 V -> 0..3.3 V.', 1.1),
    ((185.42, 220.98), 'KNOBS 3/4: 50k dividers on +3V3 -> ADC2 (GPIO28) / ADC3 (GPIO29),\n'
                       'the Bread Modular knob channels.', 1.1),
    ((322.58, 200.66), 'MODE: SW1 (6 x 6 mm THT tact) on GPIO12, red LED on GPIO13 through 1k (Bread Modular pins).\n'
                       'GPIO13 is PWM6B: the duty cycle sets the LED brightness.', 1.1),
    ((424.18, 33.02), 'DAC + OUTPUTS: PT8211 (I2S GPIO1-3) -> 1k/10n -> U5A/U5B gain 6.1 with -5.1 x VOFF (1.98 V):\n'
                      'full scale 1.65 V +/- 0.825 V -> 0 V +/- 5.0 V, DC coupled, 1k series to J4 (L) / J5 (R).', 1.1),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/16bit/schematic/' + key))


def stock_symbol(lib, name):
    """Stock symbol flattened through every `extends` level (parent body/pins, child properties)."""
    if lib == 'BM':
        tree = parse(BM_SCH.read_text())
        sym = copy.deepcopy({s[1]: s for s in nodes(one(tree, 'lib_symbols'), 'symbol')}[name])
        short = name.split(':')[1]
        sym[1] = short
        for u in nodes(sym, 'symbol'):
            assert u[1].startswith(short)
        return sym, BM_SCH, None
    tree = parse((STOCK / f'{lib}.kicad_sym').read_text())
    syms = {s[1]: s for s in nodes(tree, 'symbol')}
    sym = copy.deepcopy(syms[name])
    chain = []
    while one(sym, 'extends'):
        base = one(sym, 'extends')[1]
        chain.append(base)
        parent = copy.deepcopy(syms[base])
        props = {p[1]: p for p in nodes(sym, 'property')}
        for i, item in enumerate(parent):
            if isinstance(item, list) and item[0] == 'property' and item[1] in props:
                parent[i] = props.pop(item[1])
            elif isinstance(item, list) and item[0] == 'symbol':
                item[1] = item[1].replace(base, name, 1)
        parent[1] = name
        insert = max(i for i, item in enumerate(parent) if isinstance(item, list) and item[0] == 'property') + 1
        parent[insert:insert] = list(props.values())
        sym = parent
    return sym, STOCK / f'{lib}.kicad_sym', ' <- '.join(chain) or None


def pin_table(sym, unit):
    """Pins of one unit (body style 1) plus the pins common to all units."""
    out = {}
    for u in nodes(sym, 'symbol'):
        num, style = u[1].rsplit('_', 2)[-2:]
        if num not in ('0', str(unit)) or style not in ('0', '1'):
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


def power_symbol(i, net, x, y, rot, root):
    sym = RAIL_SYMBOL[net]
    body = (0, -1) if sym == 'GND' else (0, 1)          # library direction pin -> body
    dx, dy = xform(*body, rot)
    just = [atom('justify'), atom('left' if (dx > 0) != (rot == 90) else 'right')] if dx else None
    vx, vy = r(x + dx * 3.81), r(y + dy * 3.81)
    if sym == 'GND':
        vx, vy = r(x + dx * 5.08), r(y + dy * 5.08)
    ref = f'#PWR{i + 1:03d}'
    fa = rot % 180                                      # horizontal text at any rotation
    hide = [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('hide'), atom('yes')]]
    props = [[atom('property'), 'Reference', ref, [atom('at'), x, y, 0], copy.deepcopy(hide)],
             [atom('property'), 'Value', net, [atom('at'), vx, vy, fa],
              [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]] + ([just] if just else [])]]
    for name in ('Footprint', 'Datasheet', 'Description'):
        props.append([atom('property'), name, '', [atom('at'), x, y, 0], copy.deepcopy(hide)])
    return [atom('symbol'), [atom('lib_id'), f'{LIB}:{sym}'], [atom('at'), x, y, rot], [atom('unit'), 1],
            [atom('exclude_from_sim'), atom('no')], [atom('in_bom'), atom('no')], [atom('on_board'), atom('no')],
            [atom('in_pos_files'), atom('no')], [atom('dnp'), atom('no')], [atom('uuid'), uid(f'pwr/{i}')],
            *props, [atom('pin'), '1', [atom('uuid'), uid(f'pwr/{i}/pin')]],
            [atom('instances'), [atom('project'), PROJECT,
             [atom('path'), '/' + root, [atom('reference'), ref], [atom('unit'), 1]]]]]




def is_local(net):
    return net.startswith('_')


def draw(ends, root):
    """Wires, power symbols, labels and junctions: drawing() plus automatic stubs.

    ends: {pin end (x, y): (net, outward (dx, dy), [pin keys])} of every connected pin (stacked
    pins share one end). Pins on a drawn wire are left alone; every other pin gets a stub."""
    wires_in, power_in, labels_in = drawing()

    def at(pt):
        if isinstance(pt, str):
            hit = [e for e, v in ends.items() if pt.replace('.', '/', 1) in v[2]]
            assert hit, f'unknown or unconnected pin {pt}'
            return hit[0]
        if isinstance(pt[0], str):
            x, y = at(pt[0])
            return (r(x + pt[1]), r(y + pt[2]))
        return (r(pt[0]), r(pt[1]))

    segs = []
    for line in wires_in:
        pts = [at(pt) for pt in line]
        for a_, b_ in zip(pts, pts[1:]):
            assert a_ != b_ and (a_[0] == b_[0] or a_[1] == b_[1]), f'wire {line}: {a_} -> {b_} not axis-aligned'
            segs.append((a_, b_))

    def on_seg(pt, a_, b_, inclusive=True):
        if a_[0] == b_[0] == pt[0]:
            lo, hi = sorted((a_[1], b_[1]))
            return lo <= pt[1] <= hi if inclusive else lo < pt[1] < hi
        if a_[1] == b_[1] == pt[1]:
            lo, hi = sorted((a_[0], b_[0]))
            return lo <= pt[0] <= hi if inclusive else lo < pt[0] < hi
        return False

    def crosses(s1, s2):
        (a1, b1), (a2, b2) = s1, s2
        if (a1[0] == b1[0]) == (a2[0] == b2[0]):
            return False
        if a1[0] != b1[0]:
            (a1, b1), (a2, b2) = (a2, b2), (a1, b1)
        x, y = a1[0], a2[1]                     # s1 vertical at x, s2 horizontal at y
        return (min(a1[1], b1[1]) < y < max(a1[1], b1[1])) and (min(a2[0], b2[0]) < x < max(a2[0], b2[0]))

    power = [(net, at(pt), rot) for net, pt, rot in power_in]
    labels = [(net, at(pt), side) for net, pt, side in labels_in]
    drawn = {e for e in ends if any(on_seg(e, *s) for s in segs)}
    drawn |= {pt for _, pt, _ in power} | {pt for _, pt, _ in labels}

    # Automatic stubs for every pin not reached by a drawn wire.
    stubs = {}
    for e, (net, d, keys) in sorted(ends.items()):
        if e in drawn:
            continue
        s = (r(e[0] + d[0] * STUB), r(e[1] + d[1] * STUB))
        stubs[e] = (s, net, d, keys)
        segs.append((e, s))
    # Join neighbouring stubs of one rail that point the same way into a bar with one symbol.
    anchors = set(ends) | {s for s, *_ in stubs.values()} | {p for s_ in segs for p in s_}
    groups = {}
    for e, (s, net, d, keys) in stubs.items():
        if net in RAIL_SYMBOL:
            line = s[1] if d[0] == 0 else s[0]
            groups.setdefault((net, d, line), []).append(s)
    symbol_at = {}
    for (net, d, line), pts in groups.items():
        along = 0 if d[0] == 0 else 1          # vertical stubs -> horizontal bar (along X)
        pts.sort(key=lambda p: p[along])
        bars = [[pts[0]]]
        for p in pts[1:]:
            prev = bars[-1][-1]
            seg = (prev, p)
            blocked = (any(on_seg(a, *seg, inclusive=False) for a in anchors)
                       or any(crosses(seg, s_) for s_ in segs))
            if p[along] - prev[along] <= MERGE_GAP and not blocked:
                bars[-1].append(p)
            else:
                bars.append([p])
        for bar in bars:
            for a_, b_ in zip(bar, bar[1:]):
                segs.append((a_, b_))
            gnd = RAIL_SYMBOL[net] == 'GND'
            if along == 0 or len(bar) == 1:      # horizontal bar or single stub: symbol continues the stub
                symbol_at[bar[0]] = (net, d)
            else:                                # vertical bar: + rails at the top, GND at the bottom
                symbol_at[bar[-1] if gnd else bar[0]] = (net, (0, 1) if gnd else (0, -1))
    for e, (s, net, d, keys) in stubs.items():
        if net in RAIL_SYMBOL:
            if s in symbol_at:
                n_, dd = symbol_at[s]
                if RAIL_SYMBOL[net] == 'GND':
                    rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[dd]
                else:
                    rot = {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[dd]
                power.append((net, s, rot))
        else:
            side = {(1, 0): 'R', (-1, 0): 'L', (0, -1): 'U', (0, 1): 'D'}[d]
            labels.append((net, s, side))

    # Split every segment at every connection point it passes; check nothing dangles.
    pin_pts = set(ends)
    power_pts = {pt for _, pt, _ in power}
    label_pts = {pt for _, pt, _ in labels}
    anchors = pin_pts | power_pts | label_pts | {p for s_ in segs for p in s_}
    split = []
    for a_, b_ in segs:
        cuts = sorted((pt for pt in anchors if on_seg(pt, a_, b_, inclusive=False)),
                      key=lambda pt: abs(pt[0] - a_[0]) + abs(pt[1] - a_[1]))
        chain = [a_] + cuts + [b_]
        split += list(zip(chain, chain[1:]))
    split = sorted(set(tuple(sorted(s_)) for s_ in split))
    degree = {}
    for a_, b_ in split:
        for e in (a_, b_):
            degree[e] = degree.get(e, 0) + 1
    for e, n in degree.items():
        assert n > 1 or e in pin_pts | power_pts | label_pts, f'dangling wire end at {e}'
    for pt in label_pts | power_pts:
        assert pt in degree or pt in pin_pts, f'symbol/label at {pt} touches nothing'
    out = []
    for a_, b_ in split:
        out.append([atom('wire'), [atom('pts'), [atom('xy'), *a_], [atom('xy'), *b_]],
                    [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                    [atom('uuid'), uid(f'wire/{a_}/{b_}')]])
    for pt in sorted(degree):
        n = degree[pt] + (pt in pin_pts) + (pt in power_pts)
        if n >= 3:
            out.append([atom('junction'), [atom('at'), *pt], [atom('diameter'), 0],
                        [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'junction/{pt}')]])
    for i, (net, (x, y), rot) in enumerate(power):
        out.append(power_symbol(i, net, x, y, rot, root))
    for i, (net, (x, y), side) in enumerate(labels):
        lang, just = {'R': (0, 'left'), 'L': (180, 'right'), 'U': (90, 'left'), 'D': (270, 'right')}[side]
        out.append([atom('label'), net, [atom('at'), x, y, lang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                     [atom('justify'), atom(just), atom('bottom')]],
                    [atom('uuid'), uid(f'label/{i}')]])
    return out


def check_netlist(sch, nets, no_connects):
    """The native netlist must equal CIRCUIT exactly: same net names (local '_' nets: same
    pins under KiCad's automatic name), same pins, same no-connects."""
    import xml.etree.ElementTree as ET
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml), str(sch)],
                       check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(xml).getroot()
    got = {n.get('name'): frozenset(f"{d.get('ref')}/{d.get('pin')}" for d in n.findall('node')
                                    if not d.get('ref').startswith('#'))
           for n in root.find('nets')}
    got = {k: v for k, v in got.items() if v}
    nc = {next(iter(v)) for k, v in got.items() if k.startswith('unconnected-') and len(v) == 1}
    assert nc == no_connects, f'no-connect pins differ: {sorted(nc ^ no_connects)}'
    got = {k: v for k, v in got.items() if not k.startswith('unconnected-')}
    want = {n: frozenset(k for k in keys if not k.startswith('#')) for n, keys in nets.items()}
    local = {v for n, v in want.items() if is_local(n)}
    auto = {v for k, v in got.items() if k.startswith('Net-(')}
    assert local == auto, f'local nets differ: {sorted(map(sorted, local ^ auto))}'
    got = {k: v for k, v in got.items() if not k.startswith('Net-(')}
    want = {net_name(n): v for n, v in want.items() if not is_local(n)}
    bad = {k: (sorted(got.get(k, ())), sorted(want.get(k, ()))) for k in set(got) | set(want)
           if got.get(k) != want.get(k)}
    assert not bad, 'netlist differs from CIRCUIT (net: got, want):\n' + '\n'.join(
        f'  {k}: {v}' for k, v in sorted(bad.items()))


def lib_text(sym, name):
    p = next(pp for pp in nodes(sym, 'property') if pp[1] == name)
    at = one(p, 'at')
    return float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0


# Reference / value text: two-pin parts on the free side ('left' overrides), a few parts placed by hand
# (offsets from the symbol origin, horizontal text; keys 'REF' or 'REF/unit', optional justify).
TEXT_LEFT = {'R3', 'D4', 'C18', 'C36', 'C24', 'R15', 'R18'}
TEXT_POS = {'U4': ((0, -8.89), (0, 8.89)), 'D1': ((0, -5.08), (0, -2.54)),
            'U8': ((0, -6.35), (0, -3.81)), 'U9': ((0, -6.35), (0, -3.81)),
            'U5/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U6/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U7/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'Y1': ((0, -6.35), (0, -3.81)),
            'JP1': ((0, -6.35), (0, -3.81)), 'D5': ((0, -6.35), (0, -3.81)), 'D6': ((0, -6.35), (0, -3.81)),
            'R20': ((0, -5.08), (0, -2.54))}


def text_at(p, sym):
    """[(field, (x, y), angle, justify)] for Reference and Value. KiCad stores field angles so that
    angle == symbol rotation (mod 180) reads horizontally."""
    x, y = p['at']
    flat = p['rot'] % 180
    key = next((k for k in (f"{p['ref']}/{p['unit']}", p['ref']) if k in TEXT_POS), None)
    if key:
        (rx, ry), (vx, vy), *just = TEXT_POS[key]
        just = just[0] if just else None
        return [('Reference', (x + rx, y + ry), flat, just), ('Value', (x + vx, y + vy), flat, just)]
    two_pin = p['sym'] in ('R', 'C', 'L', 'D_Schottky', '1N4148W')
    vertical = (p['rot'] in (0, 180)) == (p['sym'] in ('R', 'C', 'L'))
    if two_pin and not vertical:                       # horizontal: above / below, centred
        return [('Reference', (x, y - 2.54), flat, None), ('Value', (x, y + 2.54), flat, None)]
    if two_pin:
        dx, just = (-2.54, 'right') if p['ref'] in TEXT_LEFT else (2.54, 'left')
        if p['rot'] == 180:                            # KiCad mirrors the justification at 180 degrees
            just = {'left': 'right', 'right': 'left'}[just]
        return [('Reference', (x + dx, y - 1.27), flat, just), ('Value', (x + dx, y + 1.27), flat, just)]
    if p['sym'] == 'R_Potentiometer':
        return [('Reference', (x - 2.54, y - 1.27), 0, 'right'), ('Value', (x - 2.54, y + 1.27), 0, 'right')]
    out = []
    for name in ('Reference', 'Value'):
        lx, ly, la = lib_text(sym, name)
        ox, oy = xform(lx, ly, p['rot'])
        out.append((name, (x + ox, y + oy), int((la + p['rot']) % 180), None))
    return out


def build():
    lib_syms, sources = {}, {}
    for key, (lib, name) in SYMBOLS.items():
        sym, src, parent = stock_symbol(lib, name)
        edit = None
        if key in FILTER_EDITS:
            prop = next(pp for pp in nodes(sym, 'property') if pp[1] == 'ki_fp_filters')
            edit = f'ki_fp_filters {prop[2]!r} -> {FILTER_EDITS[key]!r}'
            prop[2] = FILTER_EDITS[key]
        if lib == 'BM':
            edit = 'embedded symbol of the Bread Modular 16bit schematic (KiCad 10 stock has no PT8211); renamed'
        sym[1] = key
        for u in nodes(sym, 'symbol'):
            u[1] = key + '_' + '_'.join(u[1].rsplit('_', 2)[-2:])
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
        '(options "") (descr "16bit pinned symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A2")
      (title_block (title "Big Modular - 16bit") (rev "S1") (company "Big Modular")
        (comment 1 "SCHEMATIC S1 - Bread Modular 16bit (RP2350) for Eurorack 6HP: MIDI in, 2 CV in, 4 pots, red mode LED, 2 outs")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIB}:' + k
        embedded.append(s)

    items, nets, ends = [], {}, {}
    units = {}
    parts = circuit()
    for p in parts:
        sym = lib_syms[p['sym']]
        pins = pin_table(sym, p['unit'])
        assert set(p['pins']) == set(pins), (p['ref'], p['unit'], sorted(set(pins) ^ set(p['pins'])))
        units.setdefault(p['ref'], set()).add(p['unit'])
        x, y = p['at']
        is_flag = p['ref'].startswith('#')
        assembled = not is_flag and p['ref'] not in NOT_ASSEMBLED
        (rn, rxy, ra, rj), (vn, vxy, va, vj) = text_at(p, sym)
        props = [('Reference', p['ref'], rxy, is_flag, ra, rj), ('Value', p['value'], vxy, is_flag, va, vj),
                 ('Footprint', f"{LIB}:{FP[p['fp']]}" if p['fp'] else '', (x, y), True, 0, None),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''),
                  (x, y), True, 0, None),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''),
                  (x, y), True, 0, None)]
        props += [(k, v, (x, y), True, 0, None) for k, v in p['fields'].items()]
        ukey = p['ref'] if p['unit'] == 1 else f"{p['ref']}/{p['unit']}"
        mirror = p['ref'] in MIRROR_X
        node = [atom('symbol'), [atom('lib_id'), f'{LIB}:' + p['sym']], [atom('at'), x, y, p['rot']],
                *([[atom('mirror'), atom('x')]] if mirror else []),
                [atom('unit'), p['unit']], [atom('exclude_from_sim'), atom('no')],
                [atom('in_bom'), atom('yes' if assembled else 'no')],
                [atom('on_board'), atom('no' if is_flag else 'yes')],
                [atom('in_pos_files'), atom('yes' if assembled else 'no')], [atom('dnp'), atom('no')],
                [atom('uuid'), uid('sym/' + ukey)]]
        for name, value, (px, py), hide, ang, just in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), ang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if just:
                prop[-1].append([atom('justify'), atom(just)])
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        all_pins = set().union(*(pin_table(sym, u) for u in range(1, 10)))
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{ukey}/{n}")]] for n in sorted(all_pins)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), p['unit']]]]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, -py if mirror else py, p['rot'])
            ex, ey = r(x + ox), r(y + oy)
            key = f"{p['ref']}/{n}"
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                assert (ex, ey) not in ends, key
                continue
            nets.setdefault(net, []).append(key)
            d = outward(-ang if mirror else ang, p['rot'])
            if (ex, ey) in ends:  # stacked pins or two parts meeting pin to pin (same net only)
                assert ends[(ex, ey)][0] == net, (key, ends[(ex, ey)])
                ends[(ex, ey)][2].append(key)
            else:
                ends[(ex, ey)] = (net, d, [key])
    multi = {ref: u for ref, u in units.items() if len(u) > 1}
    assert multi == {'U5': {1, 2, 3, 4, 5}, 'U6': {1, 2, 3}, 'U7': {1, 2, 3}}, multi
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    items += draw(ends, root)
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
    check_netlist(out, nets, {f"{p['ref']}/{n}" for p in parts for n, net in p['pins'].items() if net is None})
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned symbols in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources}, indent=2) + '\n')
    print(out, f'{len(nets)} nets, {len({p["ref"] for p in parts if not p["ref"].startswith("#")})} parts')


if __name__ == '__main__':
    build()
