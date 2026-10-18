"""Circuit intent for the Big Modular UPDI programmer.

Electrically this is the Bread Modular UPDIProgrammer 0.3.0 (USB-C -> CH340N
-> ATtiny1616 running jtag2updi) with the Bread Modular breadboard headers
(GND1, NC1, OUTPUT1 and the 330R ground resistor R9) replaced by one 1x05
2.54 mm header:

    J1.1    UPDI      UPDI output to the module being programmed (U2 PB0)
    J1.2-4  GND
    J1.5    MCU_UPDI  UPDI input of this board's own ATtiny1616 (via R5), silk SELF

The serial TX/RX header pins of the original are dropped; R1/R2 still feed
the ATtiny1616 USART from the CH340N.
"""

LIB = 'UPDIProgrammer'
PROJECT = 'updi-programmer'
TITLE = 'Big Modular UPDI programmer'
REV = '1.4.0'

# Symbol library sources: (local name, source library file, source symbol).
# Stock symbols come from the KiCad 10 installation; the HRO USB-C symbol is
# the pin-audited 12-land variant from modules/usb-power (paired GND/VBUS
# contacts share one land, matching the HRO footprint).
SYMBOL_SOURCES = [
    ('R', '${KICAD10_SYMBOL_DIR}/Device.kicad_sym', 'R'),
    ('C', '${KICAD10_SYMBOL_DIR}/Device.kicad_sym', 'C'),
    ('LED', '${KICAD10_SYMBOL_DIR}/Device.kicad_sym', 'LED'),
    ('CH340N', '${KICAD10_SYMBOL_DIR}/Interface_USB.kicad_sym', 'CH340N'),
    ('ATtiny1616-M', '${KICAD10_SYMBOL_DIR}/MCU_Microchip_ATtiny.kicad_sym', 'ATtiny1616-M'),
    ('Conn_01x05_Pin', '${KICAD10_SYMBOL_DIR}/Connector.kicad_sym', 'Conn_01x05_Pin'),
    ('GND', '${KICAD10_SYMBOL_DIR}/power.kicad_sym', 'GND'),
    ('+5V', '${KICAD10_SYMBOL_DIR}/power.kicad_sym', '+5V'),
    ('PWR_FLAG', '${KICAD10_SYMBOL_DIR}/power.kicad_sym', 'PWR_FLAG'),
    ('HRO_TYPE_C_31_M_12', '${REPO}/modules/usb-power/hardware/BigModular.kicad_sym', 'HRO_TYPE_C_31_M_12'),
]

FOOTPRINT_SOURCES = [
    ('Resistor_SMD.pretty', 'R_0603_1608Metric'),
    ('Resistor_SMD.pretty', 'R_0402_1005Metric'),
    ('Capacitor_SMD.pretty', 'C_0402_1005Metric'),
    ('Capacitor_SMD.pretty', 'C_0805_2012Metric'),
    ('Capacitor_SMD.pretty', 'C_1206_3216Metric'),
    ('LED_SMD.pretty', 'LED_0603_1608Metric'),
    ('Package_SO.pretty', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Package_DFN_QFN.pretty', 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm'),
    ('Connector_PinHeader_2.54mm.pretty', 'PinHeader_1x05_P2.54mm_Vertical'),
    ('${REPO}/modules/usb-power/hardware/BigModular.pretty', 'HRO-TYPE-C-31-M-12'),
]

# KiCad 10 ships no STEP for the stock VQFN-20 3x3 footprint; the local copy
# points at the closest shipped body (same 3x3 mm, 0.4 mm pitch, 20 pins).
# Visual/3D only: copper, mask and paste are the unchanged stock land.
MODEL_OVERRIDES = {
    'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm': (
        'Package_DFN_QFN.3dshapes/VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm.step',
        'Package_DFN_QFN.3dshapes/UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm.step'),
}

NC = None

# ref: symbol, value, footprint, pin -> net, extra fields, schematic (x, y, rot)
PARTS = {
    # --- USB-C --------------------------------------------------------------
    'J2': dict(sym='HRO_TYPE_C_31_M_12', value='TYPE-C-31-M-12', fp='HRO-TYPE-C-31-M-12',
               mpn='TYPE-C-31-M-12', manufacturer='Korean Hroparts Elec', lcsc='C165948',
               pins={'A1': 'GND', 'A12': 'GND', 'A4': '+5V', 'A9': '+5V', 'A5': 'CC1', 'B5': 'CC2',
                     'A6': 'D+', 'B6': 'D+', 'A7': 'D-', 'B7': 'D-', 'A8': NC, 'B8': NC, 'S1': 'SHIELD'},
               at=(45.72, 76.2, 0)),
    'R3': dict(sym='R', value='5.1k', fp='R_0603_1608Metric', lcsc='C23186', mpn='0603WAF5101T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'CC1', '2': 'GND'}, at=(81.28, 55.88, 0)),
    'R4': dict(sym='R', value='5.1k', fp='R_0603_1608Metric', lcsc='C23186', mpn='0603WAF5101T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'CC2', '2': 'GND'}, at=(93.98, 55.88, 0)),
    'C2': dict(sym='C', value='10nF', fp='C_0805_2012Metric', lcsc='C1710', mpn='CL21B103KBANNNC', manufacturer='Samsung Electro-Mechanics',
               pins={'1': 'SHIELD', '2': 'GND'}, at=(81.28, 81.28, 0)),
    '#FLG01': dict(sym='PWR_FLAG', value='PWR_FLAG', pins={'1': '+5V'}, at=(93.98, 78.74, 0)),
    '#FLG02': dict(sym='PWR_FLAG', value='PWR_FLAG', pins={'1': 'GND'}, at=(104.14, 78.74, 0)),
    # --- USB to serial ------------------------------------------------------
    'U1': dict(sym='CH340N', value='CH340N', fp='SOIC-8_3.9x4.9mm_P1.27mm', mpn='CH340N', manufacturer='WCH(Jiangsu Qin Heng)', lcsc='C2977777',
               pins={'1': 'D+', '2': 'D-', '3': 'GND', '4': NC, '5': '+5V', '6': 'TXD', '7': 'RXD', '8': 'V3'},
               at=(50.8, 152.4, 0)),
    'C1': dict(sym='C', value='100nF', fp='C_0402_1005Metric', lcsc='C1525', mpn='CL05B104KO5NNNC', manufacturer='Samsung Electro-Mechanics',
               pins={'1': '+5V', '2': 'GND'}, at=(25.4, 132.08, 0)),
    'C3': dict(sym='C', value='100nF', fp='C_0402_1005Metric', lcsc='C1525', mpn='CL05B104KO5NNNC', manufacturer='Samsung Electro-Mechanics',
               pins={'1': 'V3', '2': 'GND'}, at=(35.56, 132.08, 0)),
    'R1': dict(sym='R', value='1k', fp='R_0603_1608Metric', lcsc='C21190', mpn='0603WAF1001T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'TXD', '2': 'SERIAL_TX'}, at=(81.28, 137.16, 90)),
    'R2': dict(sym='R', value='1k', fp='R_0603_1608Metric', lcsc='C21190', mpn='0603WAF1001T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'RXD', '2': 'SERIAL_RX'}, at=(81.28, 157.48, 90)),
    # --- MCU (jtag2updi) ----------------------------------------------------
    'U2': dict(sym='ATtiny1616-M', value='ATtiny1616-M', fp='VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm',
               mpn='ATTINY1616-MNR', manufacturer='Microchip Tech', lcsc='C507118',
               pins={'3': 'GND', '21': 'GND', '4': '+5V', '19': 'RESET', '8': 'LED', '14': 'UPDI',
                     '12': 'SERIAL_RX', '11': 'SERIAL_TX',
                     '1': NC, '2': NC, '5': NC, '6': NC, '7': NC, '9': NC, '10': NC, '13': NC,
                     '15': NC, '16': NC, '17': NC, '18': NC, '20': NC},
               value_at=(-12.7, 27.94), at=(160.02, 88.9, 0)),
    'C4': dict(sym='C', value='22uF', fp='C_1206_3216Metric', lcsc='C12891', mpn='CL31A226KAHNNNE', manufacturer='Samsung Electro-Mechanics',
               pins={'1': '+5V', '2': 'GND'}, at=(129.54, 50.8, 0)),
    'C5': dict(sym='C', value='100nF', fp='C_0402_1005Metric', lcsc='C1525', mpn='CL05B104KO5NNNC', manufacturer='Samsung Electro-Mechanics',
               pins={'1': '+5V', '2': 'GND'}, at=(139.7, 50.8, 0)),
    'R5': dict(sym='R', value='4.7k', fp='R_0603_1608Metric', lcsc='C23162', mpn='0603WAF4701T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'RESET', '2': 'MCU_UPDI'}, at=(198.12, 63.5, 90)),
    # --- UPDI header --------------------------------------------------------
    # Hand-soldered 1x05 male header (user stock): kept in the BOM, excluded
    # from JLCPCB assembly by the PCB footprint's exclude-from-position flag.
    'J1': dict(sym='Conn_01x05_Pin', value='UPDI', fp='PinHeader_1x05_P2.54mm_Vertical',
               comment='hand-solder, not JLC assembled',
               pins={'1': 'UPDI', '2': 'GND', '3': 'GND', '4': 'GND', '5': 'MCU_UPDI'}, join=[['2', '3', '4']],
               at=(246.38, 88.9, 0)),
    'R8': dict(sym='R', value='100k', fp='R_0402_1005Metric', lcsc='C25741', mpn='0402WGF1003TCE', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'MCU_UPDI', '2': 'GND'}, at=(236.22, 116.84, 0)),
    # --- Indicators ---------------------------------------------------------
    'D1': dict(sym='LED', value='LED', fp='LED_0603_1608Metric', comment='USB power, red', lcsc='C2286', mpn='KT-0603R', manufacturer='Hubei KENTO Elec',
               pins={'1': 'D1_K', '2': '+5V'}, at=(152.4, 142.24, 180)),
    'R6': dict(sym='R', value='1k', fp='R_0603_1608Metric', lcsc='C21190', mpn='0603WAF1001T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'D1_K', '2': 'GND'}, at=(177.8, 142.24, 90)),
    'D2': dict(sym='LED', value='LED', fp='LED_0603_1608Metric', comment='UPDI activity, white', lcsc='C2290', mpn='KT-0603W', manufacturer='Hubei KENTO Elec',
               pins={'1': 'D2_K', '2': 'LED'}, at=(152.4, 160.02, 180)),
    'R7': dict(sym='R', value='1k', fp='R_0603_1608Metric', lcsc='C21190', mpn='0603WAF1001T5E', manufacturer='UNI-ROYAL(Uniroyal Elec)',
               pins={'1': 'D2_K', '2': 'GND'}, at=(177.8, 160.02, 90)),
}

# Board-level notes rendered on the schematic.
NOTES = [
    ((20.32, 35.56), '## USB-C (sink: 5.1k CC pull-downs, 5 V only)'),
    ((20.32, 116.84), '## USB to serial'),
    ((119.38, 35.56), '## MCU: ATtiny1616 running jtag2updi (firmware/jtag2updi_t1616.hex)'),
    ((119.38, 134.62), '## Indicators'),
    ((210.82, 35.56), '## UPDI header (2.54 mm)'),
    ((210.82, 40.64), 'J1.1   UPDI  UPDI out -> module UPDI'),
    ((210.82, 44.45), 'J1.2-4 GND   -> module GND'),
    ((210.82, 48.26), 'J1.5   SELF  program this board\'s own ATtiny1616 (MCU_UPDI)'),
    ((210.82, 52.07), 'Normal use: wire J1.1 + J1.2 to the module.'),
    ((210.82, 55.88), 'Self-flash: drive J1.5 + J1.4 from a second programmer.'),
]
