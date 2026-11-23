"""32bit MCU board S1 circuit table, drawing and sourcing (imported by tools/build_schematic.py).

S4 of modules/32bit (user, 2026-11-23): the ESP32-S3 of 32bit S3 (docs/research.md section 8) on a small
4-layer board with the modules/usb-audio MCU board outline, header strips and vertical USB-C. It sits on
the carrier's F side, between the carrier and the panel, soldered on the carrier's 2.54 mm headers
(J102 = carrier J6, J103 = carrier J7). All SMD on F (faces the panel).

- U101 ESP32-S3R8 (QFN-56, 8 MB octal PSRAM in the package on GPIO33-37 / SPICS1) + U103 W25Q128JVSIQ
  16 MB quad flash on VDD_SPI (the chip's 3.3 V output) = the N16R8 memory map of 32bit S2 / S3.
- Y101 40 MHz crystal, 10 pF load, C110 / C111 12p (as 32bit S3; no 0R: it was a radio-harmonic option).
- Supply: +3V3 from the carrier (J102.1 / J103.1); VDD3P3, VDDA, VDD3P3_RTC, VDD3P3_CPU straight on +3V3
  with their Espressif decoupling (no ferrite: it filters the RF supply, the radio is never used).
  ESP32-S3R8 at 240 MHz, radio off: 66..108 mA (datasheet v2.2 table 5-9) + flash / PSRAM.
- EN: R103 10k + C109 1u (Espressif); RESET on the carrier pulls it low. GPIO0: R104 10k pull-up; BOOT
  on the carrier pulls it low. Strapping GPIO3 / GPIO45 / GPIO46 open (defaults: SPI boot, VDD_SPI 3.3 V).
- USB: J101 D+/D- -> U102 USBLC6-2SC6 -> GPIO20 / GPIO19 (USB Serial/JTAG + OTG: console, Web Serial,
  firmware download). Data only: VBUS powers nothing (U102 reference only). CC1/CC2 5.1k (UFP).
- Audio: the carrier's CS4272 is the I2S clock master; the ESP32-S3 I2S0 is a full-duplex slave through
  the GPIO matrix: GPIO18 SCLK (BCK), GPIO17 LRCK (WS), GPIO16 <- codec SDOUT (DIN), GPIO13 -> R105 33R ->
  codec SDIN (DOUT), GPIO12 codec RST (GPIO14 / GPIO15 open beside VDD3P3_RTC for its via). I2C GPIO9 SDA / GPIO8 SCL, R106 / R107 2.2k pull-ups here.
- Controls (carrier): GPIO7 / GPIO6 = POT1 / POT2 (ADC1 CH6 / CH5, 12 dB, C112 / C113 100n beside the pins),
  GPIO38 MODE (internal pull-up), GPIO39 LED (LEDC). Pins chosen for the layout (U101 turned so the flash
  pins face the flash, GPIO38 / 39 on the side facing J102 (the rest of that side open around VDD3P3_CPU's via), GPIO14..18 and USB face J103 / U102, GPIO6..9 fan out to the
  pull-up / ADC-cap column on the free bottom right while EN / GPIO0 take the bottom-left lane); the map is in
  docs/firmware-pins.md.
- No radio: LNA_IN open, no antenna; firmware must not start Wi-Fi / BT.
"""

RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', 'VBUS': 'VBUS'}
MIRROR_X = set()
# J102/J103 are the carrier's J6/J7 pin strips seen from this board (copper only here).
NOT_ASSEMBLED = {'J102', 'J103'}
MCU = (157.48, 160.02)
HDR = (269.24, 121.92)

MCU_PINS = {
    '57': 'GND', '2': '+3V3', '3': '+3V3', '55': '+3V3', '56': '+3V3', '20': '+3V3', '46': '+3V3',
    '29': 'VDD_SPI', '4': 'EN', '5': 'BOOT',
    '12': 'POT1', '11': 'POT2',                                                 # GPIO7 / GPIO6, ADC1 CH6 / CH5
    '43': 'MODE', '44': 'LED',                                                  # GPIO38 / 39
    '14': 'I2C_SDA', '13': 'I2C_SCL',                                           # GPIO9 / GPIO8
    '24': 'I2S_SCLK', '23': 'I2S_LRCK', '22': 'I2S_ADC',                       # GPIO18 / 17 / 16
    '18': 'I2S_DOUT', '17': 'CODEC_RST',                                        # GPIO13 / GPIO12
    '25': 'USB_DM', '26': 'USB_DP',
    '30': 'SPIHD', '31': 'SPIWP', '32': 'SPICS0', '33': 'SPICLK', '34': 'SPIQ', '35': 'SPID',
    '53': 'XTAL_N', '54': 'XTAL_P',
}
UNUSED = ['1', '6', '7', '8', '9', '10', '15', '16', '19', '21', '27', '28', '36', '37', '38', '39',
          '40', '41', '42', '45', '47', '48', '49', '50', '51', '52']

# W25Q128JVSIQ pin -> net (quad I/O; QE is set from the factory on the IQ part).
FLASH = {'1': 'SPICS0', '2': 'SPIQ', '3': 'SPIWP', '4': 'GND', '5': 'SPID', '6': 'SPICLK',
         '7': 'SPIHD', '8': 'VDD_SPI'}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def circuit():
    c = []
    pins = dict(MCU_PINS)
    pins.update({n: None for n in UNUSED})
    assert len(pins) == 57
    c.append(part('U101', 'ESP32-S3', 'ESP32-S3R8', 'QFN56', MCU, 0, pins,
                  Note='ESP32-S3 with 8 MB octal PSRAM in the package (GPIO33-37, SPICS1 reserved); with U103 = the '
                       'N16R8 memory map of 32bit S2 / S3. JLCPCB Economic. Radio never used: LNA_IN open, firmware '
                       'must not start Wi-Fi / BT'))
    x, y = MCU
    # Supply decoupling (Espressif ESP32-S3 hardware design guidelines, as 32bit S3)
    for i, (ref, val, fp, net, volt, note) in enumerate((
            ('C101', '10u', 'C0603', '+3V3', '10V', '+3V3 bulk (the supply arrives over the header pins)'),
            ('C102', '100n', 'C0402', '+3V3', '16V', 'VDD3P3 (pins 2, 3)'),
            ('C103', '1u', 'C0402', '+3V3', '25V', 'VDDA (pins 55, 56), Espressif reference 1u'),
            ('C104', '10n', 'C0402', '+3V3', '50V', 'VDDA (pins 55, 56), Espressif reference 10n'),
            ('C105', '100n', 'C0402', '+3V3', '16V', 'VDD3P3_RTC (pin 20)'),
            ('C106', '100n', 'C0402', '+3V3', '16V', 'VDD3P3_CPU (pin 46)'),
            ('C107', '1u', 'C0402', 'VDD_SPI', '25V', 'VDD_SPI (pin 29) output, Espressif reference 1u'),
            ('C108', '100n', 'C0402', 'VDD_SPI', '16V', 'U103 VCC (pin 8)'),
            ('C112', '100n', 'C0402', 'POT1', '16V', 'POT1 ADC input (Espressif: 100n at the ADC pin)'),
            ('C113', '100n', 'C0402', 'POT2', '16V', 'POT2 ADC input'))):
        c.append(two(ref, 'C', val, fp, (101.6 + 10.16 * i, 246.38), net, 'GND', rot=0, Voltage=volt,
                     Note=note if net.startswith('POT') else f'{note} decoupling'))
    c.append(two('R103', 'R', '10k', 'R0402', (96.52, 99.06), '+3V3', 'EN', rot=0, Note='EN pull-up (Espressif)'))
    c.append(two('C109', 'C', '1u', 'C0402', (104.14, 99.06), 'EN', 'GND', rot=0, Voltage='25V',
                 Note='EN power-on delay: 10k x 1u, the chip starts after +3V3 is up (Espressif)'))
    c.append(two('R104', 'R', '10k', 'R0402', (114.3, 99.06), '+3V3', 'BOOT', rot=0,
                 Note='GPIO0 pull-up: boot from flash; carrier SW2 BOOT pulls it low (download mode)'))
    c.append(two('R106', 'R', '2.2k', 'R0402', (124.46, 99.06), '+3V3', 'I2C_SCL', rot=0,
                 Note='I2C pull-up (100 kHz bus to the codec; on the carrier until usb-audio S5)'))
    c.append(two('R107', 'R', '2.2k', 'R0402', (132.08, 99.06), '+3V3', 'I2C_SDA', rot=0, Note='I2C pull-up'))
    c.append(two('R105', 'R', '33', 'R0402', (241.3, 226.06), 'I2S_DOUT', 'I2S_DAC',
                 Note='Series termination: GPIO13 (I2S DOUT) -> codec SDIN'))
    # 16 MB quad SPI flash on VDD_SPI
    c.append(part('U103', 'W25Q128JVS', 'W25Q128JVS', 'SOIC8W', (213.36, 175.26), 0, FLASH,
                  Note='16 MB quad SPI flash (W25Q128JVSIQ: QE set), SOIC-8 208 mil, on VDD_SPI (3.3 V)'))
    # 40 MHz crystal: 10 pF load, 12p each side (6 pF + about 4 pF of pins and copper)
    c.append(part('Y101', 'Crystal_GND24', '40MHz', 'XTAL3225', (101.6, 177.8), 0,
                  {'1': 'XTAL_P', '2': 'GND', '3': 'XTAL_N', '4': 'GND'}, MPN='X322540MMB4SI',
                  Note='40 MHz, 10 pF load, +/-10 ppm, ESR <= 40R, 3.2 x 2.5 mm (the ESP32-S3 crystal)'))
    c.append(two('C110', 'C', '12p', 'C0402', (91.44, 185.42), 'XTAL_P', 'GND', rot=0, Voltage='50V',
                 Note='Crystal load, C0G'))
    c.append(two('C111', 'C', '12p', 'C0402', (111.76, 185.42), 'XTAL_N', 'GND', rot=0, Voltage='50V',
                 Note='Crystal load, C0G'))

    # ---- USB-C (vertical, through the panel) and ESD
    c.append(part('J101', 'USB_C_Receptacle_USB2.0_16P', 'USB-C', 'USBC_V', (40.64, 165.1), 0,
                  {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
                   'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
                   'A5': '_CC1', 'B5': '_CC2', 'A6': '_DP_C', 'B6': '_DP_C', 'A7': '_DM_C', 'B7': '_DM_C',
                   'A8': None, 'B8': None, 'SH': 'GND'},
                  MPN='TYPE-C-31-D-15', Manufacturer='Korean Hroparts Elec',
                  Note='Vertical 16P SMD USB-C, H = 8.8 mm: mouth 1.3 mm proud of the panel front '
                       '(docs/geometry.json stack), as modules/usb-audio. Shell legs are GND in the HRO land pattern'))
    c.append(part('U102', 'USBLC6-2SC6', 'USBLC6-2SC6', 'SOT23-6', (81.28, 167.64), 0,
                  {'1': '_DM_C', '6': 'USB_DM', '3': '_DP_C', '4': 'USB_DP', '5': 'VBUS', '2': 'GND'},
                  Note='USB ESD (flow-through: pins 1/6 and 3/4 are one line each inside)'))
    c.append(two('R101', 'R', '5.1k', 'R0402', (66.04, 154.94), '_CC1', 'GND', Note='UFP Rd'))
    c.append(two('R102', 'R', '5.1k', 'R0402', (78.74, 157.48), '_CC2', 'GND', Note='UFP Rd'))

    # ---- Carrier headers (copper only on this board)
    hx, hy = HDR
    c.append(part('J102', 'Conn_01x10', 'MCU_L', 'H1x10', HDR, 0,
                  {'1': '+3V3', '2': 'GND', '3': 'EN', '4': 'BOOT', '5': 'MODE', '6': 'LED',
                   '7': 'I2C_SDA', '8': 'I2C_SCL', '9': 'POT1', '10': 'POT2'},
                  Note='Carrier J6 strip (bought/soldered with the carrier BOM)'))
    c.append(part('J103', 'Conn_01x10', 'MCU_R', 'H1x10', (hx + 30.48, hy), 0,
                  {'1': '+3V3', '2': 'GND', '3': 'I2S_SCLK', '4': 'GND', '5': 'I2S_LRCK', '6': 'I2S_ADC',
                   '7': 'I2S_DAC', '8': 'CODEC_RST', '9': 'GND', '10': 'GND'},
                  Note='Carrier J7 strip (same pinout as modules/usb-audio)'))
    for ref, net, at, rot in (('#FLG101', '+3V3', (hx - 7.62, hy - 10.16), 0),
                              ('#FLG102', 'GND', (hx - 12.7, hy - 5.08), 90),
                              ('#FLG103', 'VBUS', (58.42, 149.86), 180),
                              ('#FLG104', 'VDD_SPI', (190.5, 236.22), 0)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    W, P, L = [], [], []
    # USB-C pairs into the ESD part
    W += [['J101.A7', (58.42, 162.56), (58.42, 165.1), 'J101.B7'], [(58.42, 165.1), (66.04, 165.1), (66.04, 167.64),
                                                                    'U102.1'],
          ['J101.A6', (60.96, 167.64), (60.96, 170.18), 'J101.B6'], [(60.96, 170.18), 'U102.3'],
          ['J101.A5', 'R101.1'], ['J101.B5', 'R102.1'],
          ['J101.A4', (60.96, 149.86), (60.96, 144.78)]]
    P += [('VBUS', (60.96, 144.78), 0)]
    # Header supply pins with the PWR_FLAGs
    hx, hy = HDR
    W += [['J102.1', (hx - 10.16, hy - 10.16)], ['J102.2', (hx - 12.7, hy - 7.62), (hx - 12.7, hy - 2.54)]]
    P += [('+3V3', (hx - 10.16, hy - 10.16), 90), ('GND', (hx - 12.7, hy - 2.54), 0)]
    return W, P, L


# JLCPCB parts: ESP32-S3R8, W25Q128JVSIQ, 40 MHz crystal, 12p as modules/32bit S3 (live-checked 2026-11-15);
# USB-C, USBLC6-2SC6 and the 0402 R/C as modules/usb-audio. Free stock / pre-order checked at the export.
SOURCING = {
    ('ESP32-S3', 'ESP32-S3R8', 'QFN56'): dict(LCSC='C2913194', MPN='ESP32-S3R8', Manufacturer='Espressif Systems'),
    ('W25Q128JVS', 'W25Q128JVS', 'SOIC8W'): dict(LCSC='C97521', MPN='W25Q128JVSIQ', Manufacturer='Winbond'),
    ('Crystal_GND24', '40MHz', 'XTAL3225'): dict(LCSC='C5210647', MPN='X322540MMB4SI',
                                                Manufacturer='YXC Crystal Oscillators'),
    ('USB_C_Receptacle_USB2.0_16P', 'USB-C', 'USBC_V'): dict(LCSC='C22464480', MPN='TYPE-C-31-D-15',
                                                             Manufacturer='Korean Hroparts Elec'),
    ('USBLC6-2SC6', 'USBLC6-2SC6', 'SOT23-6'): dict(LCSC='C7519', MPN='USBLC6-2SC6', Manufacturer='STMicroelectronics'),
    ('C', '12p', 'C0402'): dict(LCSC='C1547', MPN='0402CG120J500NT', Manufacturer='FH (Guangdong Fenghua)'),
    ('C', '10n', 'C0402'): dict(LCSC='C15195', MPN='CL05B103KB5NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0402'): dict(LCSC='C1525', MPN='CL05B104KO5NNNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0402'): dict(LCSC='C52923', MPN='CL05A105KA5NQNC', Manufacturer='Samsung'),
    ('C', '10u', 'C0603'): dict(LCSC='C19702', MPN='CL10A106KP8NNNC', Manufacturer='Samsung'),
    ('R', '10k', 'R0402'): dict(LCSC='C25744', MPN='0402WGF1002TCE', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0402'): dict(LCSC='C25905', MPN='0402WGF5101TCE', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R0402'): dict(LCSC='C25105', MPN='0402WGF330JTCE', Manufacturer='UNI-ROYAL'),
    ('R', '2.2k', 'R0402'): dict(LCSC='C25879', MPN='0402WGF2201TCE', Manufacturer='UNI-ROYAL'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR 32BIT - MCU board, S1 (32bit S4). ESP32-S3R8 + W25Q128JVSIQ, 40 MHz, native USB on the '
                     'front-panel USB-C. Circuit intent: docs/research.md section 9', 2.0),
    ((20.32, 129.54), 'USB-C (vertical, through the panel): data only (no power drawn).\n'
                      'D+/D- -> USBLC6-2SC6 -> GPIO20 / GPIO19 (USB Serial/JTAG: console, Web Serial, download).', 1.1),
    ((86.36, 83.82), 'RESET (EN) and BOOT (GPIO0) buttons are on the carrier (B side). Hold BOOT, press RESET:\n'
                     'ROM download mode on the USB-C. Strapping GPIO3 / GPIO45 / GPIO46 open (defaults).', 1.1),
    ((238.76, 83.82), 'CARRIER HEADERS: J102 = carrier J6, J103 = carrier J7 (2.54 mm pin strips,\n'
                      'soldered through both boards; the strips are in the carrier BOM). J6 pinout is 32bit-only.', 1.1),
    ((119.38, 210.82), 'I2S0 slave (codec = clock master): GPIO18 SCLK, GPIO17 LRCK, GPIO16 DIN (codec SDOUT),\n'
                       'GPIO13 DOUT -> R105 -> codec SDIN, GPIO12 codec RST. I2C GPIO9 SDA / GPIO8 SCL. POT1 / POT2 GPIO7 /\n'
                       'GPIO6 (ADC1), MODE GPIO38, LED GPIO39. Radio never used: LNA_IN open.', 1.1),
]

TEXT_LEFT = {'R103', 'R104', 'R106', 'R107'}
TEXT_POS = {'U101': ((0, -45.72), (0, 45.72)), 'U102': ((-7.62, -6.35), (0, 11.43), 'right'),
            'U103': ((0, -10.16), (0, 10.16)),
            'J101': ((0, -27.94), (0, 27.94)), 'J102': ((0, -13.97), (0, 16.51)), 'J103': ((0, -13.97), (0, 16.51)),
            'Y101': ((0, -6.35), (0, 6.35))}
MULTI_UNIT = {}
