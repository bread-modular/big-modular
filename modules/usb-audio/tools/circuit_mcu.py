"""USB-AUDIO MCU board S1 circuit table, drawing and sourcing (imported by tools/build_schematic.py).

CH32V307RCT6 (LQFP-64, RISC-V, USB 2.0 High-Speed with built-in PHY) on a small 4-layer board
that sits on the carrier's F side, between the carrier and the panel, soldered on the carrier's
2.54 mm headers (J102 = carrier J6, J103 = carrier J7). A vertical USB-C (HRO TYPE-C-31-D-15)
on its top side comes out through the panel.

- USB: J101 D+/D- -> U102 USBLC6-2SC6 -> PB7/PB6 (USBHS_DP/DM, also the ROM bootloader port).
  Data only: VBUS powers nothing (the module runs from the rack); R103/R104 divide it to PA9 so
  the firmware only connects (D+ pull-up) while a host is present. CC1/CC2 5.1k (UFP).
- Audio: codec is I2S master. I2S2 (slave RX): PB13 CK, PB12 WS, PB15 SD <- codec SDOUT.
  I2S3 (slave TX, default pins): PB3 CK, PA15 WS, PB5 SD -> R108 33R -> codec SDIN.
  I2C2: PB10 SCL, PB11 SDA (pull-ups on the carrier). PB14 = codec RST.
- Clock: Y101 8 MHz (HSE; USBHS PHY PLL reference as the WCH EVT).
- Boot: BOOT0 10k pull-down (BOOT button on the carrier pulls it to +3V3), BOOT1/PB2 10k pull-down;
  NRST 10k / 100n (RESET button on the carrier). SWDIO/SWCLK go to the carrier's J8.
"""

RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', 'VBUS': 'VBUS'}
MIRROR_X = set()
# J102/J103 are the carrier's J6/J7 pin strips seen from this board (copper only here).
NOT_ASSEMBLED = {'J102', 'J103'}
MCU = (157.48, 160.02)
HDR = (231.14, 121.92)

MCU_PINS = {
    '7': 'NRST', '60': 'BOOT0', '28': 'BOOT1', '46': 'SWDIO', '49': 'SWCLK', '42': 'VBUS_DET',
    '58': 'USB_DM', '59': 'USB_DP',
    '33': 'I2S_LRCK', '34': 'I2S_SCLK', '36': 'I2S_ADC',          # I2S2 slave RX
    '50': 'I2S_LRCK', '55': 'I2S_SCLK', '57': '_DAC_SRC',          # I2S3 slave TX
    '29': 'I2C_SCL', '30': 'I2C_SDA', '35': 'CODEC_RST',
    '5': '_OSC_IN', '6': '_OSC_OUT',
    '1': '+3V3', '19': '+3V3', '48': '+3V3', '32': '+3V3', '64': '+3V3', '13': '+3V3',
    '18': 'GND', '31': 'GND', '47': 'GND', '63': 'GND', '12': 'GND',
}
UNUSED = ['2', '3', '4', '8', '9', '10', '11', '14', '15', '16', '17', '20', '21', '22', '23', '24', '25', '26',
          '27', '37', '38', '39', '40', '41', '43', '44', '45', '51', '52', '53', '54', '56', '61', '62']


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def circuit():
    c = []
    pins = dict(MCU_PINS)
    pins.update({n: None for n in UNUSED})
    assert len(pins) == 64
    c.append(part('U101', 'CH32V30xRxTx', 'CH32V307RCT6', 'LQFP64', MCU, 0, pins,
                  Note='RISC-V 144 MHz, USB 2.0 HS device with built-in PHY (USB Audio Class 2), 2 x I2S'))
    x, y = MCU
    c.append(part('Y101', 'Crystal', '8MHz', 'XTAL5032', (x + 27.94, y + 12.7), 90,
                  {'1': '_OSC_OUT', '2': '_OSC_IN'}, Note='HSE 8 MHz, CL 20 pF (as the WCH CH32V307 EVT)'))
    c.append(two('C101', 'C', '33p', 'C0402', (x + 35.56, y + 6.35), '_OSC_IN', 'GND', Voltage='50V',
                 Note='Load cap: 2 x (CL 20 pF - ~4 pF stray)'))
    c.append(two('C102', 'C', '33p', 'C0402', (x + 35.56, y + 19.05), '_OSC_OUT', 'GND', Voltage='50V',
                 Note='Load cap'))
    c.append(two('R108', 'R', '33', 'R0402', (111.76, y + 22.86), 'I2S_DAC', '_DAC_SRC',
                 Note='Series termination: PB5 (I2S3_SD) -> codec SDIN'))
    # Supply decoupling: one 100n per VDD/VIO pin, VDDA 100n + 1u, VBAT 100n, 10u bulk
    for i, (val, fp, volt, note) in enumerate((('100n', 'C0402', '16V', 'VDD pin 19'),
                                               ('100n', 'C0402', '16V', 'VIO pin 32'),
                                               ('100n', 'C0402', '16V', 'VDD pin 48'),
                                               ('100n', 'C0402', '16V', 'VIO pin 64'),
                                               ('100n', 'C0402', '16V', 'VDDA pin 13'),
                                               ('1u', 'C0402', '25V', 'VDDA pin 13 bulk'),
                                               ('100n', 'C0402', '16V', 'VBAT pin 1'),
                                               ('10u', 'C0603', '10V', '+3V3 bulk at the header'))):
        c.append(two(f'C{103 + i}', 'C', val, fp, (124.46 + 10.16 * i, 246.38), '+3V3', 'GND', rot=0, Voltage=volt,
                     Note=f'{note} decoupling'))
    c.append(two('R105', 'R', '10k', 'R0402', (96.52, 99.06), '+3V3', 'NRST', rot=0, Note='NRST pull-up'))
    c.append(two('C111', 'C', '100n', 'C0402', (104.14, 99.06), 'NRST', 'GND', rot=0, Voltage='16V',
                 Note='NRST power-on delay (as the WCH EVT)'))
    c.append(two('R106', 'R', '10k', 'R0402', (114.3, 99.06), 'BOOT0', 'GND', rot=0,
                 Note='BOOT0 low = run from flash; carrier SW2 BOOT pulls it high'))
    c.append(two('R107', 'R', '10k', 'R0402', (121.92, 99.06), 'BOOT1', 'GND', rot=0,
                 Note='BOOT1 (PB2) low: BOOT0 high selects the system-memory bootloader'))

    # ---- USB-C (vertical, through the panel) and ESD
    c.append(part('J101', 'USB_C_Receptacle_USB2.0_16P', 'USB-C', 'USBC_V', (40.64, 165.1), 0,
                  {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
                   'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
                   'A5': '_CC1', 'B5': '_CC2', 'A6': '_DP_C', 'B6': '_DP_C', 'A7': '_DM_C', 'B7': '_DM_C',
                   'A8': None, 'B8': None, 'SH': 'GND'},
                  MPN='TYPE-C-31-D-15', Manufacturer='Korean Hroparts Elec',
                  Note='Vertical 16P SMD USB-C, H = 8.8 mm: mouth 1.3 mm proud of the panel front '
                       '(docs/geometry.json stack). Shell legs are GND in the HRO land pattern'))
    c.append(part('U102', 'USBLC6-2SC6', 'USBLC6-2SC6', 'SOT23-6', (81.28, 167.64), 0,
                  {'1': '_DM_C', '6': 'USB_DM', '3': '_DP_C', '4': 'USB_DP', '5': 'VBUS', '2': 'GND'},
                  Note='USB 2.0 HS ESD (flow-through: pins 1/6 and 3/4 are one line each inside)'))
    c.append(two('R101', 'R', '5.1k', 'R0402', (66.04, 154.94), '_CC1', 'GND', Note='UFP Rd'))
    c.append(two('R102', 'R', '5.1k', 'R0402', (78.74, 157.48), '_CC2', 'GND', Note='UFP Rd'))
    c.append(two('R103', 'R', '10k', 'R0402', (99.06, 134.62), 'VBUS', 'VBUS_DET', rot=0,
                 Note='VBUS sense: 5 V -> 3.33 V on PA9 (FT pin)'))
    c.append(two('R104', 'R', '20k', 'R0402', (99.06, 142.24), 'VBUS_DET', 'GND', rot=0, Note='VBUS sense divider'))

    # ---- Carrier headers (copper only on this board)
    hx, hy = HDR
    c.append(part('J102', 'Conn_01x10', 'MCU_L', 'H1x10', HDR, 0,
                  {'1': '+3V3', '2': 'GND', '3': 'SWDIO', '4': 'SWCLK', '5': 'NRST', '6': 'BOOT0',
                   '7': 'I2C_SCL', '8': 'I2C_SDA', '9': 'GND', '10': 'GND'},
                  Note='Carrier J6 strip (bought/soldered with the carrier BOM)'))
    c.append(part('J103', 'Conn_01x10', 'MCU_R', 'H1x10', (hx + 30.48, hy), 0,
                  {'1': '+3V3', '2': 'GND', '3': 'I2S_SCLK', '4': 'GND', '5': 'I2S_LRCK', '6': 'I2S_ADC',
                   '7': 'I2S_DAC', '8': 'CODEC_RST', '9': 'GND', '10': 'GND'},
                  Note='Carrier J7 strip'))
    for ref, net, at, rot in (('#FLG101', '+3V3', (hx - 7.62, hy - 10.16), 0),
                              ('#FLG102', 'GND', (hx - 7.62, hy + 10.16), 180),
                              ('#FLG103', 'VBUS', (58.42, 149.86), 180)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    W, P, L = [], [], []
    x, y = MCU
    # Crystal and load caps
    W += [['U101.5', (x + 22.86, y + 10.16), (x + 22.86, y + 6.35), 'C101.1'], [(x + 27.94, y + 6.35), 'Y101.2'],
          ['U101.6', (x + 22.86, y + 15.24), (x + 22.86, y + 19.05), 'C102.1'], [(x + 27.94, y + 19.05), 'Y101.1'],
          ['U101.57', 'R108.2']]
    # USB-C pairs into the ESD part
    W += [['J101.A7', (58.42, 162.56), (58.42, 165.1), 'J101.B7'], [(58.42, 165.1), (66.04, 165.1), (66.04, 167.64),
                                                                    'U102.1'],
          ['J101.A6', (60.96, 167.64), (60.96, 170.18), 'J101.B6'], [(60.96, 170.18), 'U102.3'],
          ['J101.A5', 'R101.1'], ['J101.B5', 'R102.1'],
          ['R103.2', (104.14, 138.43)], ['J101.A4', (60.96, 149.86), (60.96, 144.78)]]
    P += [('VBUS', (60.96, 144.78), 0)]
    L += [('VBUS_DET', (104.14, 138.43), 'R')]
    # Header supply pins with the PWR_FLAGs
    hx, hy = HDR
    W += [['J102.1', (hx - 10.16, hy - 10.16)], ['J102.9', (hx - 10.16, hy + 10.16)]]
    P += [('+3V3', (hx - 10.16, hy - 10.16), 90), ('GND', (hx - 10.16, hy + 10.16), 270)]
    return W, P, L


# JLCPCB parts, live-checked 2026-10-23 (CH32V307RCT6, TYPE-C-31-D-15, USBLC6-2SC6 Extended; the rest Basic).
SOURCING = {
    ('CH32V30xRxTx', 'CH32V307RCT6', 'LQFP64'): dict(LCSC='C2988083', MPN='CH32V307RCT6', Manufacturer='WCH'),
    ('Crystal', '8MHz', 'XTAL5032'): dict(LCSC='C115962', MPN='X50328MSB2GI', Manufacturer='YXC'),
    ('USB_C_Receptacle_USB2.0_16P', 'USB-C', 'USBC_V'): dict(LCSC='C22464480', MPN='TYPE-C-31-D-15',
                                                             Manufacturer='Korean Hroparts Elec'),
    ('USBLC6-2SC6', 'USBLC6-2SC6', 'SOT23-6'): dict(LCSC='C7519', MPN='USBLC6-2SC6', Manufacturer='STMicroelectronics'),
    ('C', '33p', 'C0402'): dict(LCSC='C1562', MPN='0402CG330J500NT', Manufacturer='FH'),
    ('C', '100n', 'C0402'): dict(LCSC='C1525', MPN='CL05B104KO5NNNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0402'): dict(LCSC='C52923', MPN='CL05A105KA5NQNC', Manufacturer='Samsung'),
    ('C', '10u', 'C0603'): dict(LCSC='C19702', MPN='CL10A106KP8NNNC', Manufacturer='Samsung'),
    ('R', '10k', 'R0402'): dict(LCSC='C25744', MPN='0402WGF1002TCE', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0402'): dict(LCSC='C25765', MPN='0402WGF2002TCE', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0402'): dict(LCSC='C25905', MPN='0402WGF5101TCE', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R0402'): dict(LCSC='C25105', MPN='0402WGF330JTCE', Manufacturer='UNI-ROYAL'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR USB-AUDIO - MCU board, S1. CH32V307RCT6, USB 2.0 High-Speed (UAC2, 192 kHz / 24-bit, '
                     '2 in / 2 out). Circuit intent: docs/research.md', 2.0),
    ((20.32, 129.54), 'USB-C (vertical, through the panel): data only, VBUS sensed on PA9 (no power drawn).\n'
                      'D+/D- -> USBLC6-2SC6 -> PB7/PB6 = USBHS_DP/DM (also the ROM bootloader port).', 1.1),
    ((86.36, 83.82), 'BOOT/RESET buttons and the SWD header are on the carrier (B side).\n'
                     'Hold BOOT, press RESET: ROM bootloader on the USB-C (wchisp / WCHISPTool).', 1.1),
    ((200.66, 83.82), 'CARRIER HEADERS: J102 = carrier J6, J103 = carrier J7 (2.54 mm pin strips,\n'
                      'soldered through both boards; the strips are in the carrier BOM).', 1.1),
    ((119.38, 228.6), 'I2S2 slave RX: PB13 CK, PB12 WS, PB15 SD (codec SDOUT). I2S3 slave TX: PB3 CK, PA15 WS,\n'
                      'PB5 SD (codec SDIN). I2C2: PB10/PB11. PB14 codec RST. The codec is the clock master.', 1.1),
]

TEXT_LEFT = {'R105', 'R103', 'R104'}
TEXT_POS = {'U101': ((0, -60.96), (0, 60.96)), 'U102': ((-7.62, -6.35), (0, 11.43), 'right'),
            'J101': ((0, -27.94), (0, 27.94)), 'J102': ((0, -13.97), (0, 16.51)), 'J103': ((0, -13.97), (0, 16.51)),
            'Y101': ((5.08, -1.27), (5.08, 1.27), 'left')}
MULTI_UNIT = {}
