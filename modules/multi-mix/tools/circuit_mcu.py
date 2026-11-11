"""MULTI-MIX MCU board S4 circuit table, drawing and sourcing (imported by tools/build_schematic.py).

modules/usb-audio-max's MCU board (itself modules/usb-audio's S1/R2: same CH32V307RCT6, USB-C, crystal,
boot and supply parts) with this module's pins. It sits on the carrier's F side, between the carrier
and the panel, soldered on the carrier's two 1x12 2.54 mm strips (J112 = carrier J12, J113 = J13). S3 (2026-11-10):
every part on the top (F) side, the board extended to the carrier top edge around the M3 standoff.
A vertical USB-C (HRO TYPE-C-31-D-15) on its top side comes out through the panel.

- USB: J101 D+/D- -> U102 USBLC6-2SC6 -> PB7/PB6 (USBHS_DP/DM, also the ROM bootloader port): one
  composite device, UAC2 audio (6 in / 8 out at 48 kHz) + USB-MIDI (CC out). Data only: VBUS powers
  nothing; R103/R104 divide it to PC11 (VBUS_DET).
  CC1/CC2 5.1k (UFP).
- Audio: the PCM3168A runs at 48 kHz only (single rate, TDM, 256 BCK per frame, BCK 12.288 MHz),
  so only DOUT1/DIN1 are used. I2S3 slave RX PB3 CK, PA15 WS, PB5 SD <- DOUT1 (ADC 1-6); I2S2 slave TX
  PB13 CK, PB12 WS, PB15 SD -> R110 33R -> DIN1 (DAC 1-8). S3: the I2S3 clock pins (PB3, PA15) are tied
  to the I2S2 ones on this board, so BCK and LRCK take one strip pin each.
  PB14 (SPI2_MISO) sits on the same PB15 node: the CH32V307 datasheet (V3.9 Table 4-29) rates I2S CK at
  8 MHz max, below BCK, while its SPI slave is rated to 72 MHz, so the firmware can run SPI2/SPI3 as
  slaves instead (RX on PB5 = SPI3_MOSI as now; TX on PB14 = SPI2_MISO, PB15 then an input). PB4 is free.
  SPI1 (usb-audio-max's 96 kHz second line pair) is not used: PA4-PA7 stay free. I2C2: PB10 SCL, PB11 SDA,
  pull-ups R108/R109 2.2k here (S2, were R18/R19 on the carrier). PC0 = codec RST.
- Mixer controls: PC1 = ADC_IN11 <- POT_ADC (carrier 74HC4067 COM through 1k); PC2/PC3/PA0/PA1 =
  MUX_S0-S3 (pin order = J112.8-11). PA8 = NORM_PROBE (pseudo-random probe on the jack
  normals: the firmware finds unpatched inputs).
- Clock link (docs/research.md section 4): clock only, no data. PA2 <- LINK_N (S3, was PA9; low = CLK IN connected:
  clock slave; the carrier switches SCKI/BCK/LRCK by hardware, the firmware keeps the codec in slave mode).
- MIDI IN (S4, 2026-11-11, docs/research.md section 11): PA10 = USART1_RX <- MIDI_RX (J113.11, was a third
  GND): the carrier's TS MIDI IN jack behind 10k + BAT54S, not inverted (31250 baud, idle high). The firmware
  forwards it as USB-MIDI. PA9 (USART1_TX) stays free.
  PC6-PC9, PB0, PB1, PA3, PA9, PA11, PA12, PB4 and PC13 are free.
- Clock: Y101 8 MHz (HSE; USBHS PHY PLL reference as the WCH EVT).
- Boot: BOOT0 10k pull-down (BOOT button on the carrier pulls it to +3V3), BOOT1/PB2 10k pull-down;
  NRST 10k / 100n (RESET button on the carrier). SWDIO/SWCLK go to the carrier's J15.
"""

RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', 'VBUS': 'VBUS'}
MIRROR_X = set()
# J112/J113 are the carrier's J12/J13 pin strips seen from this board (copper only here).
NOT_ASSEMBLED = {'J112', 'J113'}
MCU = (157.48, 160.02)
HDR = (231.14, 121.92)

MCU_PINS = {
    '7': 'NRST', '60': 'BOOT0', '28': 'BOOT1', '46': 'SWDIO', '49': 'SWCLK', '52': 'VBUS_DET',  # PC11 (R1, was PA8)
    '58': 'USB_DM', '59': 'USB_DP',
    '33': 'I2S_LRCK', '34': 'I2S_SCLK', '36': 'I2S_DAC1_SRC',     # I2S2 slave TX (DIN1), S2 (was RX)
    '35': 'I2S_DAC1_SRC',                                          # PB14 = SPI2_MISO (SPI-slave TX fallback)
    '50': 'I2S_LRCK', '55': 'I2S_SCLK', '57': 'I2S_ADC1',          # I2S3 slave RX (DOUT1); clocks tied to I2S2's (S3)
    '29': 'I2C_SCL', '30': 'I2C_SDA', '8': 'CODEC_RST',             # PC0 (S2, was PA2)
    '9': 'POT_ADC',                                                # PC1 = ADC_IN11 (S2, was PC0)
    '10': 'MUX_S0', '11': 'MUX_S1', '14': 'MUX_S2', '15': 'MUX_S3',  # PC2, PC3, PA0, PA1 (S2, were PA12-PA9)
    '41': 'NORM_PROBE', '16': 'LINK_N',                            # PA8 TIM1_CH1, PA2 (S3, was PA9)
    '43': 'MIDI_RX',                                               # PA10 = USART1_RX (S4), 5 V tolerant
    '5': '_OSC_IN', '6': '_OSC_OUT',
    '1': '+3V3', '19': '+3V3', '48': '+3V3', '32': '+3V3', '64': '+3V3', '13': '+3V3',
    '18': 'GND', '31': 'GND', '47': 'GND', '63': 'GND', '12': 'GND',
}
UNUSED = ['2', '3', '4', '17', '20', '21', '22', '23', '24', '25', '26', '27',
          '37', '38', '39', '40', '42', '44', '45', '51', '53', '54', '56', '61', '62']


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
    c.append(part('Y101', 'Crystal_GND24', '8MHz', 'XTAL3225', (x + 27.94, y + 12.7), 90,
                  {'1': '_OSC_OUT', '3': '_OSC_IN', '2': 'GND', '4': 'GND'},
                  Note='HSE 8 MHz, CL 20 pF (as the WCH CH32V307 EVT); 3225 (R1 layout, was 5032)'))
    c.append(two('C101', 'C', '33p', 'C0402', (x + 35.56, y + 6.35), '_OSC_IN', 'GND', Voltage='50V',
                 Note='Load cap: 2 x (CL 20 pF - ~4 pF stray)'))
    c.append(two('C102', 'C', '33p', 'C0402', (x + 35.56, y + 19.05), '_OSC_OUT', 'GND', Voltage='50V',
                 Note='Load cap'))
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
    c.append(two('R108', 'R', '2.2k', 'R0402', (132.08, 99.06), '+3V3', 'I2C_SCL', rot=0,
                 Note='I2C pull-up (400 kHz; S2: moved here from the carrier, was R18)'))
    c.append(two('R109', 'R', '2.2k', 'R0402', (139.7, 99.06), '+3V3', 'I2C_SDA', rot=0,
                 Note='I2C pull-up (S2: moved here from the carrier, was R19)'))
    c.append(two('R110', 'R', '33', 'R0402', (149.86, 99.06), 'I2S_DAC1_SRC', 'I2S_DAC1', rot=0,
                 Note='Series termination PB15/PB14 -> codec DIN1, at the source (S2: was R65 on the carrier)'))

    # ---- USB-C (vertical, through the panel) and ESD
    c.append(part('J101', 'USB_C_Receptacle_USB2.0_16P', 'USB-C', 'USBC_V', (40.64, 165.1), 0,
                  {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
                   'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
                   'A5': '_CC1', 'B5': '_CC2', 'A6': '_DP_C', 'B6': '_DP_C', 'A7': '_DM_C', 'B7': '_DM_C',
                   'A8': None, 'B8': None, 'SH': 'GND'},
                  MPN='TYPE-C-31-D-15', Manufacturer='Korean Hroparts Elec',
                  Note='Vertical 16P SMD USB-C, H = 8.8 mm: mouth 1.3 mm proud of the panel front '
                       '(docs/geometry.json stack). Shell legs are GND in the HRO land pattern'))
    c.append(part('U102', 'USBLC6-2SC6', 'USBLC6-2SC6', 'SOT23-6', (81.28, 175.26), 0,
                  {'1': '_DM_C', '6': 'USB_DM', '3': '_DP_C', '4': 'USB_DP', '5': 'VBUS', '2': 'GND'},
                  Note='USB 2.0 HS ESD (flow-through: pins 1/6 and 3/4 are one line each inside)'))
    c.append(two('R101', 'R', '5.1k', 'R0402', (66.04, 154.94), '_CC1', 'GND', Note='UFP Rd'))
    c.append(two('R102', 'R', '5.1k', 'R0402', (86.36, 157.48), '_CC2', 'GND', Note='UFP Rd'))
    c.append(two('R103', 'R', '10k', 'R0402', (99.06, 134.62), 'VBUS', 'VBUS_DET', rot=0,
                 Note='VBUS sense: 5 V -> 3.33 V on PC11'))
    c.append(two('R104', 'R', '20k', 'R0402', (99.06, 142.24), 'VBUS_DET', 'GND', rot=0, Note='VBUS sense divider'))

    # ---- Carrier headers (copper only on this board)
    hx, hy = HDR
    c.append(part('J112', 'Conn_01x12', 'MCU_L', 'H1x12', HDR, 0,
                  {'1': 'BOOT0', '2': 'NRST', '3': '+3V3', '4': 'GND', '5': 'I2S_ADC1', '6': 'CODEC_RST',
                   '7': 'POT_ADC', '8': 'MUX_S0', '9': 'MUX_S1', '10': 'MUX_S2', '11': 'MUX_S3', '12': 'LINK_N'},
                  Note='Carrier J12 strip (bought/soldered with the carrier BOM): boot/reset, DOUT1, codec reset, '
                       'the pot mux and the clock-link detect, towards the carrier west side'))
    c.append(part('J113', 'Conn_01x12', 'MCU_R', 'H1x12', (hx + 30.48, hy), 0,
                  {'1': 'SWCLK', '2': 'SWDIO', '3': '+3V3', '4': 'GND', '5': 'I2S_DAC1', '6': 'I2C_SCL',
                   '7': 'I2C_SDA', '8': 'GND', '9': 'I2S_SCLK', '10': 'I2S_LRCK', '11': 'MIDI_RX', '12': 'NORM_PROBE'},
                  Note='Carrier J13 strip, east of the codec: SWD, DIN1, I2C, BCK/LRCK, MIDI RX, jack-normal probe'))
    for ref, net, at, rot in (('#FLG101', '+3V3', (hx - 7.62, hy - 7.62), 0),
                              ('#FLG102', 'GND', (hx + 15.24, hy + 5.08), 180),
                              ('#FLG103', 'VBUS', (58.42, 149.86), 180)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    W, P, L = [], [], []
    x, y = MCU
    # Crystal and load caps
    W += [['U101.5', (x + 22.86, y + 10.16), (x + 22.86, y + 6.35), 'C101.1'], [(x + 27.94, y + 6.35), 'Y101.3'],
          ['U101.6', (x + 22.86, y + 15.24), (x + 22.86, y + 19.05), 'C102.1'], [(x + 27.94, y + 19.05), 'Y101.1']]
    # USB-C pairs into the ESD part
    W += [['J101.A7', (58.42, 162.56), (58.42, 165.1), 'J101.B7'], [(58.42, 165.1), (66.04, 165.1), (66.04, 175.26),
                                                                    'U102.1'],
          ['J101.A6', (60.96, 167.64), (60.96, 170.18), 'J101.B6'], [(60.96, 170.18), (63.5, 170.18), (63.5, 177.8), 'U102.3'],
          ['J101.A5', 'R101.1'], ['J101.B5', 'R102.1'],
          ['R103.2', (104.14, 138.43)], ['J101.A4', (60.96, 149.86), (60.96, 144.78)]]
    P += [('VBUS', (60.96, 144.78), 0)]
    L += [('VBUS_DET', (104.14, 138.43), 'R')]
    # Header supply pins with the PWR_FLAGs
    hx, hy = HDR
    W += [['J112.3', (hx - 10.16, hy - 7.62)], ['J113.8', (hx + 12.7, hy + 5.08)]]
    P += [('+3V3', (hx - 10.16, hy - 7.62), 90), ('GND', (hx + 12.7, hy + 5.08), 270)]
    return W, P, L


# JLCPCB parts as modules/usb-audio-max (live-checked 2026-11-05); CH32V307RCT6 re-checked for this module
# 2026-11-09 (docs/research.md section 6).
SOURCING = {
    ('CH32V30xRxTx', 'CH32V307RCT6', 'LQFP64'): dict(LCSC='C2988083', MPN='CH32V307RCT6', Manufacturer='WCH'),
    ('Crystal_GND24', '8MHz', 'XTAL3225'): dict(LCSC='C2682774', MPN='X32258MSB4SI', Manufacturer='YXC'),
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
    ('R', '2.2k', 'R0402'): dict(LCSC='C25879', MPN='0402WGF2201TCE', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R0402'): dict(LCSC='C25105', MPN='0402WGF330JTCE', Manufacturer='UNI-ROYAL'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR MULTI-MIX - MCU board, S4. CH32V307RCT6, USB 2.0 High-Speed (UAC2 48 kHz / 24-bit, '
                     '6 in / 8 out, + USB-MIDI). Circuit intent: docs/research.md', 2.0),
    ((20.32, 129.54), 'USB-C (vertical, through the panel): data only, VBUS sensed on PC11 (no power drawn).\n'
                      'D+/D- -> USBLC6-2SC6 -> PB7/PB6 = USBHS_DP/DM (also the ROM bootloader port).', 1.1),
    ((86.36, 83.82), 'BOOT/RESET buttons and the SWD header are on the carrier (B side).\n'
                     'Hold BOOT, press RESET: ROM bootloader on the USB-C (wchisp / WCHISPTool).', 1.1),
    ((200.66, 83.82), 'CARRIER STRIPS: J112 = carrier J12, J113 = J13 (2 x 1x12 2.54 mm pin strips,\n'
                      'soldered through both boards; the strips are in the carrier BOM).', 1.1),
    ((119.38, 228.6), 'PCM3168A TDM at 48 kHz (codec = clock master, or slave on the clock link; BCK 12.288 MHz).\n'
                      'I2S3 slave RX: PB3 CK, PA15 WS, PB5 SD <- DOUT1 (ADC 1-6). I2S2 slave TX: PB13 CK, PB12 WS, PB15 SD -> R110 33R -> DIN1 (DAC 1-8).\n'
                      'PB3/PB13 share BCK and PA15/PB12 share LRCK (tied on this board).\n'
                      'I2S is rated 8 MHz max (DS V3.9): SPI-slave fallback RX PB5 (SPI3_MOSI), TX PB14 (SPI2_MISO, tied to PB15).\n'
                      'I2C2: PB10/PB11 (codec 0x44, pull-ups R108/R109). PC0 codec RST. Pots: PC1 = ADC_IN11 (74HC4067 COM), PC2/PC3/PA0/PA1 = S0-S3.\n'
                      'Clock link: PA2 LINK_N (low = CLK IN connected = clock slave, clocks switched on the carrier).\n'
                      'PA8 NORM_PROBE (jack-normal probe). PA10 = USART1_RX <- MIDI_RX (carrier MIDI IN jack, 31250 baud, not inverted) -> USB-MIDI.', 1.1),
]

TEXT_LEFT = {'R105', 'R103', 'R104'}
TEXT_POS = {'U101': ((15.24, -58.42), (0, 60.96)), 'U102': ((7.62, -6.35), (7.62, -3.81), 'left'),
            'J101': ((0, -27.94), (0, 27.94)), 'J112': ((0, -16.51), (0, 19.05)), 'J113': ((0, -16.51), (0, 19.05)),
            'Y101': ((5.08, -1.27), (5.08, 1.27), 'left'), 'R101': ((0, -5.08), (0, -2.54))}
MULTI_UNIT = {}
