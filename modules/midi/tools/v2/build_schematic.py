"""Generate the V2 S3 MIDI schematic (hardware/v2/midi.kicad_sch) and its pinned symbols.

Run from modules/midi:
  python3 -B tools/v2/build_schematic.py

Writes hardware/v2/MIDI.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the MIDI library), hardware/v2/sym-lib-table, the root schematic and the
output channel sheet hardware/v2/out.kicad_sch, then lets `kicad-cli sch upgrade --force`
re-save them natively. The channel sheet (0805 series 1 k, BAT54SW clamp, TS jack, Bread
Modular `gate_out` LED driver) is instanced eight times as CH1-CH8. circuit() and channel() are the
V1 circuit (docs/research.md section 3) plus the V2 mis-patch protection of
docs/research.md section 7: the Q1 NPN input front end, the JP2 input bypass (shipped
open), BAT54SW output clamps behind 0805 1 k resistors and the U2 CJ431 +5V clamp.
Every pin gets a short stub and a local (or, for the sheet ports, hierarchical) net label
(usb-power style), so connectivity is explicit by name.

The PCB never reads this table: tools/v2/build_layout.py takes nets, values and
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # shared tools/sexp.py
from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[2]
HW = MODULE / 'hardware/v2'
STOCK = Path('/usr/share/kicad/symbols')
PROJECT = 'midi'
STUB = 2.54

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the MIDI library, so the copies
# get the same patterns without the library part. JP1 is a jumper on a 2.54 mm header.
FILTER_EDITS = {
    'Conn_01x02': '*_1x??_*',
    'Conn_02x05_Odd_Even': '*_2x??_*',
    'Jumper_3_Open': 'Jumper* TestPoint*3Pads* TestPoint*Bridge* PinHeader_1x03_P2.54mm_Vertical',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LED': ('Device', 'LED'),
    'D': ('Device', 'D'), 'D_Schottky': ('Device', 'D_Schottky'),
    'ATtiny1616-M': ('MCU_Microchip_ATtiny', 'ATtiny1616-M'),
    'HT75xx-1-SOT89': ('Regulator_Linear', 'HT75xx-1-SOT89'),
    'AudioJack3': ('Connector_Audio', 'AudioJack3'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Jumper_3_Open': ('Jumper', 'Jumper_3_Open'),
    'Conn_01x02': ('Connector_Generic', 'Conn_01x02'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'MMBT3904': ('Transistor_BJT', 'MMBT3904'),
    '1N4148W': ('Diode', '1N4148W'),
    'BAT54SW': ('Diode', 'BAT54SW'),
    # CJ431 SOT-23 pinout is 1 REF, 2 K, 3 A: that is TL432DBZ, not TL431DBZ.
    'TL432DBZ': ('Reference_Voltage', 'TL432DBZ'),
    'SolderJumper_3_Open': ('Jumper', 'SolderJumper_3_Open'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R0805': 'R_0805_2012Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'SOD123': 'D_SOD-123', 'LED3': 'LED_D3.0mm',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm',
    'SOT89': 'SOT-89-3', 'PJ366ST': 'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H1x3': 'PinHeader_1x03_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
    'SOT23': 'SOT-23', 'SOT323': 'SOT-323_SC-70', 'SJ3': 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm',
}

# Copper-only parts: no BOM row, no CPL row (JP2 is bridged by hand).
NOT_ASSEMBLED = {'JP2'}

# Pin map (docs/research.md 3.3), identical to Bread Modular so the firmware ports.
OUT_PINS = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 13, 7: 14, 8: 12}   # PA5 PA6 PA7 PB5 PB4 PB1 PB0 PB2
LED_PINS = {1: 15, 2: 16, 3: 17, 4: 18, 5: 20, 6: 1, 7: 2, 8: 5}  # PC0-PC3, PA1-PA4
CH_RES = {1: ('R3', 'R4'), 2: ('R5', 'R6'), 3: ('R7', 'R8'), 4: ('R9', 'R10'),
          5: ('R12', 'R13'), 6: ('R14', 'R15'), 7: ('R16', 'R17'), 8: ('R18', 'R19')}
# Channel sheet CHn: TX -> RTX -> J tip, CL clamp on TX; LED -> RB 10k -> Q base;
# +5V -> D -> RLED -> Q collector.
SHEET = 'out.kicad_sch'
PORTS = {'TX': 'input', 'LED': 'input', '+5V': 'passive', 'GND': 'passive'}


def channel_refs(ch):
    rout, rled = CH_RES[ch]
    return {'RTX': rout, 'CL': f'D{ch + 10}', 'J': f'J{ch + 1}', 'RB': f'R{ch + 30}', 'Q': f'Q{ch + 10}',
            'RLED': rled, 'D': f'D{ch}'}




def part(ref, sym, value, fp, at, rot, pins, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, fields=fields)


def circuit():
    c = []
    # ---- Power: Eurorack +12 V -> reverse diode -> dropper -> HT7550 -> +5V
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (45.72, 58.42), 0,
                  {'1': None, '2': None, '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(part('D10', 'D_Schottky', 'B5819W', 'SOD123', (91.44, 45.72), 0,
                  {'1': 'VIN_D', '2': '+12V'},
                  Note='Series reverse-polarity protection'))
    c.append(part('R20', 'R', '39', 'R1206', (91.44, 55.88), 90,
                  {'1': 'VIN_D', '2': 'VIN_LDO'}, Power='0.5W',
                  Note='Dropper: shares LDO heat in the ~77 mA worst case (research 3.1); '
                       'anti-surge 0.5 W part, sits on the VIN_LDO heat-sink copper'))
    c.append(part('C5', 'C', '1u', 'C0805', (91.44, 66.04), 90,
                  {'1': 'VIN_LDO', '2': 'GND'}, Voltage='50V'))
    c.append(part('U3', 'HT75xx-1-SOT89', 'HT7550-1', 'SOT89', (124.46, 50.8), 0,
                  {'1': 'GND', '2': 'VIN_LDO', '3': '+5V'},
                  Note='30 V max input, 150 mA. Tab = pin 2 (VIN): heat-sink copper is VIN_LDO'))
    c.append(part('C4', 'C', '10u', 'C0805', (124.46, 66.04), 90,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C3', 'C', '10u', 'C0805', (124.46, 78.74), 90,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='Local bulk'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (45.72, 78.74), 0, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (101.6, 78.74), 0, {'1': 'VIN_LDO'}))

    # ---- +5V clamp (docs/research.md 7.4): the LDO cannot sink the output-clamp current.
    c.append(part('U2', 'TL432DBZ', 'CJ431', 'SOT23', (149.86, 55.88), 0,
                  {'1': 'CLAMP_REF', '2': '+5V', '3': 'GND'},
                  Note='+5V shunt clamp, 2.495 V x (1 + R23/R24) = 5.49 V nominal. '
                       'CJ431 SOT-23: 1 REF, 2 K, 3 A (TL432DBZ pinout)'))
    c.append(part('R23', 'R', '12k', 'R0603', (172.72, 45.72), 90,
                  {'1': '+5V', '2': 'CLAMP_REF'}, Note='Clamp divider top'))
    c.append(part('R24', 'R', '10k', 'R0603', (172.72, 58.42), 90,
                  {'1': 'CLAMP_REF', '2': 'GND'}, Note='Clamp divider bottom'))

    # ---- MIDI input: NPN front end (docs/research.md 7.2), TRS Type A/B on a 2.54 mm jumper.
    # No optocoupler in V2 (docs/research.md 3.5).
    c.append(part('J1', 'AudioJack3', 'PJ366ST', 'PJ366ST', (27.94, 127.0), 0,
                  {'T': 'TIP', 'R': 'RING', 'S': 'GND'}, Note='TRS MIDI in'))
    c.append(part('JP1', 'Jumper_3_Open', 'TRS_A/B', 'H1x3', (63.5, 127.0), 0,
                  {'1': 'TIP', '2': 'MIDI_IN', '3': 'RING'},
                  Note='1x3 2.54 mm header + shunt. 1-2 = Type A (Tip = data), '
                       '2-3 = Type B (Ring = data). No shunt = idle (R22 pulls MIDI_IN high)'))
    c.append(part('R22', 'R', '100k', 'R0603', (93.98, 116.84), 0,
                  {'1': 'MIDI_IN', '2': '+5V'},
                  Note='Idle pull-up: no cable / no shunt turns Q1 on = UART idle'))
    c.append(part('R1', 'R', '10k', 'R0603', (93.98, 132.08), 90,
                  {'1': 'MIDI_IN', '2': 'Q1_B'},
                  Note='Base resistor: ~1.1 mA at +/-12 V; 0.26 mA from a 3.3 V sender'))
    c.append(part('D9', '1N4148W', '1N4148W', 'SOD123', (109.22, 147.32), 90,
                  {'1': 'Q1_B', '2': 'GND'},
                  Note='Clamps Q1 B-E to -0.7 V for a negative input (VEBO 6 V)'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23', (121.92, 132.08), 0,
                  {'1': 'Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting input buffer: input high = RX low. Firmware: PORT_INVEN on PB3'))
    c.append(part('R2', 'R', '22k', 'R0603', (137.16, 116.84), 0,
                  {'1': 'RX_Q', '2': '+5V'},
                  Note='Q1 collector pull-up (RX idles low = inverted idle). '
                       'On RX_Q, so the JP2 bypass leaves PB3 loaded only by MIDI_IN, as V1'))
    c.append(part('JP2', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3', (160.02, 134.62), 0,
                  {'1': 'RX_Q', '2': 'RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open (all three pads apart). '
                       'Solder 1-2 = protected: Q1 drives PB3, PORT_INVEN on. '
                       'Solder 2-3 = direct/unprotected debug path (MIDI_IN to PB3 as V1), '
                       'PORT_INVEN off. Exactly one bridge, never both'))

    # ---- MCU and programming
    u1 = {'4': '+5V', '3': 'GND', '21': 'GND', '19': 'UPDI_PA0', '11': 'RX'}
    for ch in range(1, 9):
        u1[str(OUT_PINS[ch])] = f'CH{ch}_TX'
        u1[str(LED_PINS[ch])] = f'CH{ch}_LED'
    c.append(part('U1', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', (210.82, 104.14), 0, u1,
                  Note='5 V: 20 MHz as Bread Modular'))
    c.append(part('C1', 'C', '100n', 'C0603', (190.5, 142.24), 90,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U1 decoupling'))
    c.append(part('R11', 'R', '4.7k', 'R0603', (190.5, 152.4), 90,
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular)'))
    c.append(part('J11', 'Conn_01x02', 'UPDI', 'H1x2', (190.5, 165.1), 0,
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power'))

    # ---- Outputs: one channel sheet per output (channel() below)
    for ch in range(1, 9):
        col, row = (ch - 1) // 4, (ch - 1) % 4
        c.append(dict(sheet=f'CH{ch}', at=(256.54 + col * 76.2, 45.72 + row * 33.02),
                      pins={'TX': f'CH{ch}_TX', 'LED': f'CH{ch}_LED', '+5V': '+5V', 'GND': 'GND'}))
    for p in c:
        if 'sym' in p:
            p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def channel():
    """Output channel sheet: ports TX, LED, +5V, GND; refs are keys of channel_refs().
    GPIO -> 1k (0805) -> TS tip, BAT54SW clamp to +5V/GND on the GPIO side (docs/research.md
    7.3). LED driver as Bread Modular gate_out: the GPIO switches Q through 10k and the LED
    current comes from +5V, not from the GPIO pin."""
    c = [part('RTX', 'R', '1k', 'R0805', (50.8, 50.8), 90,
              {'1': 'TX', '2': 'OUT'}, Power='0.125W',
              Note='Output series (Bread Modular 1k); limits mis-patch current into the clamp'),
         part('CL', 'BAT54SW', 'BAT54SW', 'SOT323', (71.12, 43.18), 0,
              {'1': 'GND', '2': '+5V', '3': 'TX'},
              Note='Output clamp: keeps the GPIO within -0.4..+5.4 V when OUT is mis-patched'),
         part('J', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (93.98, 53.34), 0,
              {'T': 'OUT', 'S': 'GND', 'TN': None}, Note='MIDI out (TS)'),
         part('RB', 'R', '10k', 'R0603', (50.8, 99.06), 90,
              {'1': 'LED', '2': 'Q_B'}, Note='Base resistor (Bread Modular gate_out)'),
         part('Q', 'MMBT3904', 'MMBT3904', 'SOT23', (76.2, 99.06), 0,
              {'1': 'Q_B', '2': 'GND', '3': 'Q_C'},
              Note='LED switch: the LED current comes from +5V, not from the GPIO (Bread Modular SS8050)'),
         part('D', 'LED', 'LED_3mm_red', 'LED3', (101.6, 76.2), 90,
              {'2': '+5V', '1': 'LED_K'}, Note='Hand-soldered 3 mm THT'),
         part('RLED', 'R', '1k', 'R0603', (127.0, 88.9), 90,
              {'1': 'LED_K', '2': 'Q_C'}, Note='LED current, ~3 mA from +5V')]
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Live strict lookups 2026-10-18, recorded in docs/sourcing-candidates.json (jlc_release).
# Passives and D10 are JLCPCB Basic; R20, U1 and U3 are Extended by choice/necessity.
# V2 additions (Q1, D9, D11-D18, U2, R1, R2, R22-R24, 0805 1 k): docs/research.md 7.8.
# LED drivers (both versions): Q11-Q18 MMBT3904 and R31-R38 10k reuse the Q1/R1 parts.
# The THT jacks, LEDs and headers are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0805'): dict(LCSC='C17513', MPN='0805W8F1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '12k', 'R0603'): dict(LCSC='C22790', MPN='0603WAF1202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '39', 'R1206'): dict(LCSC='C414944', MPN='HP06W2F390JT5E', Manufacturer='UNI-ROYAL'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7550-1', 'SOT89'): dict(LCSC='C16106', MPN='HT7550-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR',
                                                       Manufacturer='Microchip'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
    ('TL432DBZ', 'CJ431', 'SOT23'): dict(LCSC='C3113', MPN='CJ431', Manufacturer='CJ (Jiangsu Changjing)'),
}


# Reference / value text offsets from the symbol origin (default: just above/below).
TEXT_AT = {
    'U1': ((10.16, -25.4), (10.16, 25.4)),
    'U3': ((0, -7.62), (8.89, 7.62)),
    'J10': ((1.27, -8.89), (1.27, 8.89)),
    'J1': ((0, -6.35), (0, 6.35)),
    'J11': ((0, -3.81), (0, 5.08)),
    'Jumper_3_Open': ((0, -6.35), (0, -3.81)),
    'SolderJumper_3_Open': ((0, -6.35), (0, -3.81)),
    'MMBT3904': ((10.16, -1.27), (10.16, 1.27)),
    'TL432DBZ': ((-6.35, -2.54), (6.35, 3.81)),
    'BAT54SW': ((0, -3.81), (7.62, 3.81)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 6.35)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR MIDI V2 - S3 schematic (5 V logic, mis-patch protected in/out). '
                     'Circuit intent: docs/research.md 7', 2.0),
    ((20.32, 33.02), 'POWER: Eurorack +12V -> B5819W -> 39R -> HT7550-1 -> +5V.  -12V (J10 pins 1-2) unused.', 1.4),
    ((20.32, 86.36), 'PWR_FLAG: #FLG01 marks the Eurorack GND entry; #FLG02 marks VIN_LDO, which is\n'
                     'fed from +12V only through passives (D10, R20) that ERC cannot see through.', 1.1),
    ((20.32, 101.6), 'MIDI IN: NPN front end (3.3 V and 5 V senders, +/-12 V tolerant), no opto', 1.4),
    ((20.32, 152.4), 'JP1 TRS TYPE (2.54 mm header on the back): shunt 1-2 = TYPE A (Tip = data),\n'
                     'shunt 2-3 = TYPE B (Ring = data). The unused conductor is left open.\n'
                     'Sleeve = GND (as Bread Modular V1). Q1 inverts: firmware sets PORT_INVEN on PB3.\n'
                     'No optocoupler in V2 (ground-loop isolation stays a later item).', 1.1),
    ((20.32, 170.18), 'JP2 RX SOURCE (solder jumper on the back, shipped OPEN: bridge one pair by hand):\n'
                      'Solder 1-2 = PROTECTED (Q1 drives PB3; firmware PORT_INVEN on PB3).\n'
                      'Solder 2-3 = DIRECT debug path (MIDI_IN to PB3 as V1, unprotected;\n'
                      'PORT_INVEN off). Exactly one bridge: never both, and open = PB3 floats.', 1.1),
    ((142.24, 33.02), 'U2 +5V CLAMP: sinks output-clamp current above ~5.5 V (the LDO cannot sink).', 1.1),
    ((175.26, 71.12), 'MCU: ATtiny1616 at 5 V, 20 MHz; pin map identical to Bread Modular', 1.4),
    ((175.26, 177.8), 'UPDI J11: pin 1 UPDI, pin 2 GND (2.54 mm). Power the module from Eurorack while programming.', 1.1),
    ((256.54, 25.4), 'OUTPUTS 1-8: sheets CH1-CH8 (out.kicad_sch): GPIO -> 1k -> TS tip (sleeve GND), BAT54SW\n'
                     'clamp on the GPIO side; LED: GPIO -> 10k -> NPN, +5V -> LED -> 1k -> collector (Bread Modular gate_out)', 1.4),
]

CH_TEXTS = [
    ((25.4, 25.4), 'OUTPUT CHANNEL (instanced as CH1-CH8). TX = U1 output pin, LED = U1 LED pin.', 1.6),
    ((25.4, 33.02), 'MIDI out: TX -> 1k (0805) -> TS tip, sleeve GND; BAT54SW clamps TX to +5V/GND (research 7.3).', 1.27),
    ((25.4, 116.84), 'LED driver as Bread Modular gate_out (SS8050 there): the GPIO only drives the base\n'
                     'through 10k (~0.4 mA); the ~3 mA LED current comes from +5V through the LED and 1k.', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/midi/schematic/' + key))


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


def pin_table(sym):
    out = {}
    for p in walk(sym, 'pin'):
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
    (HW / 'MIDI.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        '(sym_lib_table (version 7) (lib (name "MIDI") (type "KiCad") (uri "${KIPRJMOD}/MIDI.kicad_sym") '
        '(options "") (descr "MIDI V2 pinned stock symbols; see tools/v2/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - MIDI V2") (rev "V2-S4") (company "Big Modular")
        (comment 1 "V2 SCHEMATIC S4 - 5 V logic, mis-patch protected input and outputs, JP2 input bypass (open), LED transistor drivers")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/v2/geometry.json"))
      (lib_symbols))''')
    sub = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(uid('out/file'))}) (paper "A4")
      (title_block (title "Big Modular - MIDI V2 output channel") (rev "V2-S4") (company "Big Modular")
        (comment 1 "Instanced as CH1-CH8 in midi.kicad_sch")
        (comment 2 "Circuit intent: docs/research.md 3.4, 7.3"))
      (lib_symbols))''')
    for doc in (sch, sub):
        embedded = one(doc, 'lib_symbols')
        for k in sorted(lib_syms):
            s = copy.deepcopy(lib_syms[k])
            s[1] = 'MIDI:' + k
            embedded.append(s)

    def symbol(p, key, instances, items, nets):
        """Symbol p with one stub + label per pin; instances = [(path, ref)]."""
        sym = lib_syms[p['sym']]
        pins = pin_table(sym)
        assert set(p['pins']) == set(pins), (p['ref'], sorted(pins), sorted(p['pins']))
        x, y = p['at']
        ref = instances[0][1]
        is_flag = ref.startswith('#')
        assembled = not is_flag and ref not in NOT_ASSEMBLED
        dr, dv = TEXT_AT.get(ref, TEXT_AT.get(p['sym'], ((0, -3.81), (0, 3.81))))
        props = [('Reference', ref, (x + dr[0], y + dr[1]), False),
                 ('Value', p['value'], (x + dv[0], y + dv[1]), is_flag),
                 ('Footprint', f"MIDI:{FP[p['fp']]}" if p['fp'] else '', (x, y), True),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''), (x, y), True),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''), (x, y), True)]
        props += [(k, v, (x, y), True) for k, v in p['fields'].items()]
        fang = 90 if p['rot'] in (90, 270) else 0
        node = [atom('symbol'), [atom('lib_id'), 'MIDI:' + p['sym']], [atom('at'), x, y, p['rot']],
                [atom('unit'), 1], [atom('exclude_from_sim'), atom('no')],
                [atom('in_bom'), atom('yes' if assembled else 'no')],
                [atom('on_board'), atom('no' if is_flag else 'yes')],
                [atom('in_pos_files'), atom('yes' if assembled else 'no')], [atom('dnp'), atom('no')],
                [atom('uuid'), uid('sym/' + key)]]
        for name, value, (px, py), hide in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), fang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{key}/{n}")]] for n in sorted(pins)]
        node.append([atom('instances'), [atom('project'), PROJECT] + [
            [atom('path'), path, [atom('reference'), rf], [atom('unit'), 1]] for path, rf in instances]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, py, p['rot'])
            stub(items, nets, f'{key}/{n}', r(x + ox), r(y + oy), outward(ang, p['rot']), net)

    def stub(items, nets, key, ex, ey, d, net, hier=False):
        if net is None:
            items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
            return
        nets.setdefault(net, []).append(key)
        dx, dy = d
        sx, sy = r(ex + dx * STUB), r(ey + dy * STUB)
        items.append([atom('wire'), [atom('pts'), [atom('xy'), ex, ey], [atom('xy'), sx, sy]],
                      [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                      [atom('uuid'), uid('wire/' + key)]])
        lang, just = {(1, 0): (0, 'left'), (-1, 0): (180, 'right'),
                      (0, -1): (90, 'left'), (0, 1): (270, 'right')}[(dx, dy)]
        effects = [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                   [atom('justify'), atom(just), atom('bottom')]]
        if hier:
            effects[-1] = [atom('justify'), atom(just)]
            items.append([atom('hierarchical_label'), net, [atom('shape'), atom(PORTS[net])],
                          [atom('at'), sx, sy, lang], effects, [atom('uuid'), uid('hlabel/' + key)]])
        else:
            items.append([atom('label'), net, [atom('at'), sx, sy, lang], effects,
                          [atom('uuid'), uid('label/' + key)]])

    def texts(items, entries, prefix):
        for i, ((x, y), s, size) in enumerate(entries):
            items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                          [atom('effects'), [atom('font'), [atom('size'), size, size]], [atom('justify'), atom('left')]],
                          [atom('uuid'), uid(f'{prefix}{i}')]])

    items, nets, sheets = [], {}, []
    for p in circuit():
        if 'sheet' in p:
            sheets.append(p)
            continue
        symbol(p, p['ref'], [('/' + root, p['ref'])], items, nets)
    paths = {}
    for page, p in enumerate(sheets, start=2):
        x, y = p['at']
        sid = uid('sheet/' + p['sheet'])
        paths[p['sheet']] = f'/{root}/{sid}'
        w, h = 25.4, 15.24
        node = [atom('sheet'), [atom('at'), x, y], [atom('size'), w, h],
                [atom('exclude_from_sim'), atom('no')], [atom('in_bom'), atom('yes')],
                [atom('on_board'), atom('yes')], [atom('dnp'), atom('no')],
                [atom('stroke'), [atom('width'), 0.1524], [atom('type'), atom('solid')]],
                [atom('fill'), [atom('color'), 0, 0, 0, 0.0]], [atom('uuid'), sid],
                [atom('property'), 'Sheetname', p['sheet'], [atom('at'), x, r(y - 0.7), 0],
                 [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('justify'), atom('left'), atom('bottom')]]],
                [atom('property'), 'Sheetfile', SHEET, [atom('at'), x, r(y + h + 0.6), 0],
                 [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('justify'), atom('left'), atom('top')]]]]
        for k, (port, net) in enumerate(p['pins'].items()):
            py = r(y + 2.54 * (k + 1))
            node.append([atom('pin'), port, atom(PORTS[port]), [atom('at'), x, py, 180],
                         [atom('uuid'), uid(f"sheetpin/{p['sheet']}/{port}")],
                         [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('justify'), atom('left')]]])
            stub(items, nets, f"{p['sheet']}/{port}", x, py, (-1, 0), net)
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('page'), str(page)]]]])
        items.append(node)
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    texts(items, TEXTS, 'text/')
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])

    sub_items, sub_nets = [], {}
    for p in channel():
        key = 'out/' + p['ref']
        instances = [(paths[f'CH{ch}'], channel_refs(ch)[p['ref']]) for ch in range(1, 9)]
        sym = lib_syms[p['sym']]
        pins = pin_table(sym)
        hier = {n: net for n, net in p['pins'].items() if net in PORTS}
        symbol(dict(p, pins={n: (None if n in hier else net) for n, net in p['pins'].items()}),
               key, instances, sub_items, sub_nets)
        # Ports: replace the placeholder no-connects of port pins with hierarchical labels.
        x, y = p['at']
        for n, net in hier.items():
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, py, p['rot'])
            nc = uid(f'nc/{key}/{n}')
            sub_items[:] = [it for it in sub_items if not (it[0] == 'no_connect' and one(it, 'uuid')[1] == nc)]
            stub(sub_items, sub_nets, f'{key}/{n}', r(x + ox), r(y + oy), outward(ang, p['rot']), net, hier=True)
    single = {n: k for n, k in sub_nets.items() if len(k) < 2 and n not in PORTS}
    assert not single, f'single-pin channel nets: {single}'
    texts(sub_items, CH_TEXTS, 'out/text/')
    sub += sub_items
    sub.append([atom('embedded_fonts'), atom('no')])
    (HW / SHEET).write_text(dump(sub) + '\n')
    out = HW / 'midi.kicad_sch'
    out.write_text(dump(sch) + '\n')
    for f in (out, HW / SHEET):
        subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(f)], check=True,
                       stdout=subprocess.DEVNULL)
    (MODULE / 'docs/v2/schematic-symbols.json').write_text(json.dumps(
        {'note': 'Pinned stock KiCad 10 symbols in hardware/v2/MIDI.kicad_sym (generated by tools/v2/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    print(out, f'{len(nets)} root nets', HW / SHEET, f'{len(sub_nets)} channel nets')


if __name__ == '__main__':
    build()
