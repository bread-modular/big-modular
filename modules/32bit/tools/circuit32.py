"""32bit S1 circuit table, drawing and sourcing (imported by tools/build_schematic.py).

CIRCUIT is docs/research.md section 3: Bread Modular 32bit-5v (ESP32-S3-WROOM-1U-N16R8,
ES8388 stereo codec, USB-C data, BOOT/RESET) moved to a 6HP Eurorack module. Reused from
modules/16bit: the Eurorack power entry, the TS MIDI in NPN front end (JP1 bypass), the CV1/CV2
chain (jack normalled to +5V -> 50k attenuator -> op-amp follower -> level shift -> MCP6002 ->
ADC), the 6 x 6 mm THT mode button, the 3 mm red mode LED and the USB-C / BOOT / RESET parts.
New for Eurorack: two audio inputs (100k / 22k divider -> TL074 follower -> 1u -> 1k -> ES8388
LIN2/RIN2 (R1; BM LIN1/RIN1), no normal; firmware handles mono) and two audio outputs (ES8388 LOUT1/ROUT1 -> BM 1k -> 10u ->
TL072 gain 3.5 -> 1k 0.5 W -> jack).
"""

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+5V': '+5V', '+12V': '+12V', '-12V': '-12V',
               '+12V_F': '+12V', '-12V_F': '-12V', '+3V3_ESP32': '+3V3', '+3V3_8388': '+3V3'}

# Symbols drawn mirrored about X (pots: +3V3 up, wiper right, GND down; J1: sleeve at the bottom).
MIRROR_X = {'RV1', 'RV2', 'J1'}

# ESP32-S3-WROOM-1U pin -> net. Bread Modular 32bit-5v GPIO map kept so its firmware ports:
# IO11/12/13/14/21 = I2S DIN/WS/DOUT/BCLK/MCLK, IO8 mode button, IO18 mode LED, RXD0 (GPIO44) =
# MIDI in (UART0). Moved in R1 (docs/firmware-pins.md): CV1/CV2 = IO1/IO2 (ADC1 CH0/CH1, BM IO9/IO10)
# so U6 sits beside the module's right pin row; I2C SCL/SDA = IO38/IO39 (BM IO47/IO48) so the ES8388
# beside that row reaches them directly (the band above the top row only has room for the I2S lines).
# Dropped (left open): TXD0 (BM TX header), IO9/IO10, IO47/IO48, BM gate outs (BM IO1/IO2).
# IO35/36/37 are the N16R8 octal PSRAM pins and must stay unconnected.
MCU = {'1': 'GND', '40': 'GND', '41': 'GND', '2': '+3V3_ESP32', '3': 'EN', '27': 'BOOT',
       '13': 'USB_DM', '14': 'USB_DP', '36': 'MIDI_RX', '37': None,
       '12': 'BUTTON', '11': 'LED', '39': 'CV1_ADC', '38': 'CV2_ADC',
       '19': 'I2S_DIN', '20': 'I2S_LRCK', '21': 'I2S_DOUT', '22': 'I2S_BCLK', '23': 'I2S_MCLK',
       '31': 'CCLK', '32': 'CDATA',
       '4': None, '5': None, '6': None, '7': None, '8': None, '9': None, '10': None, '15': None,
       '16': None, '24': None, '25': None, '26': None, '28': None, '29': None, '30': None,
       '33': None, '34': None, '35': None, '17': None, '18': None}

# ES8388 (BM Module32 symbol) pin -> net. CE low = I2C address 0x10 (BM). R1 layout: the audio inputs
# use the second input pair LIN2/RIN2 (pins 22/21, the corner beside the VMID caps; BM: LIN1/RIN1),
# so firmware selects input 2 (ADCCONTROL2). LIN1/RIN1, LOUT2/ROUT2 and the NC pins are open.
CODEC = {'1': 'MCLK', '2': '+3V3_8388', '3': '+3V3_8388', '4': 'GND', '5': 'SCLK', '6': 'DSDIN',
         '7': 'LRCK', '8': 'ASDOUT', '9': None, '10': 'VREF', '11': 'CODEC_ROUT', '12': 'CODEC_LOUT',
         '13': 'GND', '14': None, '15': None, '16': '+3V3_8388', '17': '+3V3_8388', '18': 'GND',
         '19': 'ADCVREF', '20': 'VMID', '21': 'CODEC_RIN', '22': 'CODEC_LIN', '23': None, '24': None,
         '25': None, '26': 'GND', '27': 'CDATA', '28': 'CCLK', '29': 'GND'}

# Block rows (sheet mm).
CV_Y = (223.52, 256.54)                       # CV1 / CV2 signal rows (as modules/16bit)
CVX = 40.64                                   # level shift / clamp / MCP6002 right of the pot + op-amp
OPS_Y = 287.02                                # U6 / U7 supply units and decoupling
LED_Y = 236.22                                # mode LED row
ESP = (279.4, 152.4)                          # U1
COD = (391.16, 101.6)                         # U4
IN_Y = {'L': 50.8, 'R': 76.2}                 # audio input rows
IN_PARTS = {'L': dict(j='J8', unit=3, inp='10', inn='9', out='8', rin='R40', rdn='R41', cac='C43', rs='R42',
                      rb='R43', net='CODEC_LIN'),
            'R': dict(j='J9', unit=4, inp='12', inn='13', out='14', rin='R44', rdn='R45', cac='C44', rs='R46',
                      rb='R47', net='CODEC_RIN')}
OUT_Y = {'L': 111.76, 'R': 147.32}             # audio output rows
OUT_PARTS = {'L': dict(unit=1, inp='3', inn='2', out='1', rs='R50', cac='C45', rb='R51', rf='R52', rg='R53',
                       ro='R54', j='J4', src='CODEC_LOUT'),
             'R': dict(unit=2, inp='5', inn='6', out='7', rs='R55', cac='C46', rb='R56', rf='R57', rg='R58',
                       ro='R59', j='J5', src='CODEC_ROUT')}
U5_PWR = (525.78, 193.04)                     # U5 TL072 supply unit
I2S = [('R23', 'I2S_MCLK', 'MCLK', 'IO21 -> MCLK'), ('R24', 'I2S_BCLK', 'SCLK', 'IO14 -> SCLK (BCLK)'),
       ('R25', 'I2S_LRCK', 'LRCK', 'IO12 -> LRCK (WS)'), ('R26', 'I2S_DOUT', 'DSDIN', 'IO13 -> DSDIN'),
       ('R27', 'ASDOUT', 'I2S_DIN', 'ASDOUT -> IO11')]


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/L/FB: rot 90 = horizontal, pin 1 left; rot 270 = pin 1
    right; rot 0 = vertical, pin 1 on top; rot 180 = pin 1 at the bottom. Diodes: rot 0 = K left."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def circuit():
    c = []
    # ---- Power (as modules/16bit): Eurorack +/-12 V -> series Schottkys; +12V_F -> AMS1117-5.0 -> +5V
    # -> AMS1117-3.3 -> +3V3
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
                  Note='+5V for U9 (+3V3 chain) and the CV normals. ~110 mA (ESP32-S3, radio never used): ~0.75 W in '
                       'the SOT-223, tab patch + thermal vias on the 4-layer board'))
    c.append(two('C3', 'C', '22u', 'C0805', (139.7, 80.01), '+5V', 'GND', rot=0, Voltage='25V', Note='U8 output'))
    c.append(part('U9', 'AMS1117-3.3', 'AMS1117-3.3', 'SOT223', (162.56, 76.2), 0,
                  {'1': 'GND', '2': '+3V3', '3': '+5V'}, Note='+3V3 for the ESP32-S3, codec, CV buffers, MIDI'))
    c.append(two('C4', 'C', '22u', 'C0805', (177.8, 80.01), '+3V3', 'GND', rot=0, Voltage='25V',
                 Note='U9 output (Bread Modular C41 22u)'))
    c.append(two('C19', 'C', '10u', 'C0805', (187.96, 80.01), '+3V3', 'GND', rot=0, Voltage='25V',
                 Note='+3V3 bulk (Bread Modular C8)'))
    for ref, net, at, rot in (('#FLG01', 'GND', (30.48, 68.58), 0), ('#FLG02', '+12V_F', (71.12, 76.2), 180),
                              ('#FLG03', '-12V_F', (71.12, 55.88), 180), ('#FLG04', '+12V', (53.34, 76.2), 180),
                              ('#FLG05', '-12V', (53.34, 55.88), 180),
                              ('#FLG06', '+3V3_ESP32', (284.48, 106.68), 0),
                              ('#FLG07', '+3V3_8388', (350.52, 147.32), 0)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))

    # ---- ESP32-S3-WROOM-1U-N16R8 (Bread Modular U1) with its ferrite-fed supply, EN reset RC, BOOT
    x, y = ESP
    c.append(part('U1', 'ESP32-S3-WROOM-1', 'ESP32-S3-WROOM-1U-N16R8', 'WROOM1U', ESP, 0, MCU,
                  Note='Bread Modular 32bit-5v U1: 16 MB flash, 8 MB octal PSRAM (IO35-37 reserved), U.FL antenna '
                       'connector unused (radio off: no antenna path through the panel)'))
    c.append(two('FB1', 'FerriteBead', 'GZ2012D121TF', 'C0805', (x - 11.43, y - 45.72), '+3V3', '+3V3_ESP32',
                 Note='Bread Modular FB1 (120R at 100 MHz), BM footprint C_0805'))
    c.append(two('C5', 'C', '100n', 'C0402', (x + 10.16, y - 41.91), '+3V3_ESP32', 'GND', rot=0, Voltage='16V',
                 Note='U1 decoupling (Bread Modular C1)'))
    c.append(two('C6', 'C', '10u', 'C0603', (x + 20.32, y - 41.91), '+3V3_ESP32', 'GND', rot=0, Voltage='10V',
                 Note='U1 bulk (Bread Modular C2)'))
    c.append(two('R4', 'R', '10k', 'R0402', (243.84, 125.73), '+3V3', 'EN', rot=0, Note='EN pull-up (Bread Modular R3)'))
    c.append(two('C7', 'C', '1u', 'C0402', (233.68, 133.35), 'EN', 'GND', rot=0, Voltage='25V',
                 Note='EN power-on delay (Bread Modular C3)'))
    c.append(two('C8', 'C', '100n', 'C0402', (223.52, 133.35), 'EN', 'GND', rot=0, Voltage='16V',
                 Note='EN filter (Bread Modular C4)'))
    c.append(part('SW3', 'SW_Push', 'RESET', 'SWK2', (213.36, 134.62), 90, {'1': 'GND', '2': 'EN'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='Reset: pulls EN low (Bread Modular SW2), B side next to the USB-C'))
    c.append(part('SW2', 'SW_Push', 'BOOT', 'SWK2', (254.0, 139.7), 90, {'1': 'GND', '2': 'BOOT'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='BOOT: IO0 low at reset = USB download mode (Bread Modular SW1). Hold BOOT, press RESET'))

    # ---- USB-C (data only, as Bread Modular: VBUS is not used, power the module from the rack).
    # The ESP32-S3 USB PHY is wired straight to the receptacle, as Bread Modular 32bit-5v (no series R).
    c.append(part('J7', 'USB_C_Receptacle_USB2.0_14P', 'USB-C', 'USBC', (124.46, 172.72), 0,
                  {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
                   'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
                   'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP',
                   'A7': 'USB_DM', 'B7': 'USB_DM', 'SH': '_USB_SHIELD'},
                  MPN='TYPE-C-31-M-12', Manufacturer='HRO',
                  Note='Bread Modular J5. Data only, as Bread Modular: VBUS is not connected to any rail'))
    c.append(two('R11', 'R', '5.1k', 'R0402', (180.34, 154.94), 'CC1', 'GND', rot=0, Note='UFP Rd (Bread Modular R4)'))
    c.append(two('R12', 'R', '5.1k', 'R0402', (190.5, 154.94), 'CC2', 'GND', rot=0, Note='UFP Rd (Bread Modular R11)'))
    c.append(two('C24', 'C', '10n', 'C0402', (116.84, 204.47), '_USB_SHIELD', 'GND', rot=0, Voltage='50V',
                 Note='Shield to GND (Bread Modular C20)'))

    # ---- MIDI input (TS): the modules/16bit NPN front end at 3.3 V, JP1 bypass, to RXD0 (GPIO44)
    c.append(part('J1', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (22.86, 152.4), 0,
                  {'T': 'MIDI_IN', 'S': 'GND', 'TN': None}, Note='MIDI in (TS: tip = logic-level MIDI)'))
    c.append(two('R3', 'R', '100k', 'R0603', (43.18, 148.59), 'MIDI_IN', '+3V3', rot=180, Note='Idle pull-up'))
    c.append(two('R1', 'R', '10k', 'R0603', (53.34, 152.4), 'MIDI_IN', '_Q1_B',
                 Note='Base resistor: 0.26 mA from a 3.3 V sender, ~1.1 mA at +/-12 V'))
    c.append(two('D4', '1N4148W', '1N4148W', 'SOD123', (63.5, 158.75), '_Q1_B', 'GND', rot=270,
                 Note='Clamps Q1 B-E for a negative input'))
    c.append(part('Q1', 'MMBT3904', 'MMBT3904', 'SOT23', (73.66, 152.4), 0, {'1': '_Q1_B', '2': 'GND', '3': 'RX_Q'},
                  Note='Inverting buffer: input high = RX low. Firmware: invert the UART0 RX line '
                       '(uart_set_line_inverse(UART_NUM_0, UART_SIGNAL_RXD_INV))'))
    c.append(two('R2', 'R', '22k', 'R0603', (76.2, 138.43), 'RX_Q', '+3V3', rot=180,
                 Note='Q1 collector pull-up to +3V3'))
    c.append(part('JP1', 'SolderJumper_3_Open', 'RX_PROT/DIRECT', 'SJ3', (93.98, 142.24), 0,
                  {'1': 'RX_Q', '2': 'MIDI_RX', '3': 'MIDI_IN'},
                  Note='Solder jumper, copper only, shipped open. 1-2 = protected (Q1 drives RXD0, line '
                       'inverted in firmware). 2-3 = direct/unprotected (stock BM 32bit firmware). Never both'))

    # ---- CV inputs (as modules/16bit): jack -> RV1/RV2 attenuator (tip normalled to +5V: unpatched =
    # 0..+5 V knob) -> U7B/U7A follower (CV1/CV2) on +/-12 V -> 100k / 56k to +3V3 / 120k to GND, BAT54SW clamp, 1n
    # -> U6 MCP6002 follower on +3V3 -> IO1/IO2 (BM BUFF_CV1/BUFF_CV2 on IO9/IO10; moved in R1)
    for i, (y, jack, rv, rin, rup, rdn, d, cf) in enumerate(zip(CV_Y, ('J2', 'J3'), ('RV1', 'RV2'), ('R13', 'R16'),
                                                                ('R14', 'R17'), ('R15', 'R18'), ('D5', 'D6'),
                                                                ('C25', 'C26')), 1):
        c.append(part(jack, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (22.86, y), 0,
                      {'T': f'CV{i}_IN', 'S': 'GND', 'TN': '+5V'},
                      Note=f'CV{i} in, about -5.9..+6.0 V. Tip normalled to +5V: unpatched, RV{i} is a 0..+5 V knob'))
        c.append(part(rv, 'R_Potentiometer', '50k', 'RV09', (45.72, y + 3.81), 0,
                      {'1': 'GND', '2': f'_CV{i}_POT', '3': f'CV{i}_IN'},
                      Note=f'CV{i} attenuator / knob (Bread Modular RV{i}): RV09 9 mm vertical, linear (user stock). '
                           f'CW = full CV (or +5 V unpatched). Hand-soldered'))
        # R1 pin swap (layout): CV1 on U7B / U6B, CV2 on U7A / U6A, so each CV chain stays on its own
        # side of U7 and U6 on the board. Same chips, same circuit.
        pins = {'5': f'_CV{i}_POT', '6': f'CV{i}_AMP', '7': f'CV{i}_AMP'} if i == 1 else \
            {'3': f'_CV{i}_POT', '2': f'CV{i}_AMP', '1': f'CV{i}_AMP'}
        c.append(part('U7', 'TL074', 'TL074', 'SOIC14', (60.96, y + 6.35), 0, pins, unit=3 - i,
                      Note='Input buffers on +/-12 V: B = CV1, A = CV2 attenuator followers, C/D = audio input followers'))
        c.append(two(rin, 'R', '100k', 'R0603', (45.72 + CVX, y), f'CV{i}_AMP', f'CV{i}_BUF',
                     Note='Level-shift input. Zin = 100k + 56k||120k = 138k. Clamp current <= 0.09 mA at +/-12 V'))
        c.append(two(rup, 'R', '56k', 'R0603', (53.34 + CVX, y - 3.81), '+3V3', f'CV{i}_BUF', rot=0,
                     Note='Level-shift offset: 0 V CV -> 1.63 V'))
        c.append(two(rdn, 'R', '120k', 'R0603', (60.96 + CVX, y + 3.81), f'CV{i}_BUF', 'GND', rot=0,
                     Note='Level-shift: V(CV_BUF) = 0.276 x Vin + 1.628 V'))
        c.append(two(cf, 'C', '1n', 'C0603', (68.58 + CVX, y + 3.81), f'CV{i}_BUF', 'GND', rot=0, Voltage='50V',
                     Note='With the 27.6k Thevenin: 5.8 kHz CV low-pass'))
        c.append(part(d, 'BAT54SW', 'BAT54SW', 'SOT323', (83.82 + CVX, y - 5.08), 0,
                      {'1': 'GND', '2': '+3V3', '3': f'CV{i}_BUF'},
                      Note='Clamp: holds the op-amp input within -0.3..+3.6 V'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', (106.68 + CVX, CV_Y[0] + 2.54), 0,
                  {'5': 'CV1_BUF', '6': 'CV1_ADC', '7': 'CV1_ADC'}, unit=2,
                  Note='CV buffers on +3V3 (Bread Modular U3 MCP6002): ADC pins only ever see 0..3.3 V'))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', (106.68 + CVX, CV_Y[1] + 2.54), 0,
                  {'3': 'CV2_BUF', '2': 'CV2_ADC', '1': 'CV2_ADC'}, unit=1))
    c.append(part('U6', 'MCP6002-xSN', 'MCP6002', 'SOIC8', (137.16, OPS_Y), 0,
                  {'4': 'GND', '8': '+3V3'}, unit=3))
    c.append(two('C27', 'C', '100n', 'C0603', (144.78, OPS_Y), '+3V3', 'GND', rot=0, Voltage='50V',
                 Note='U6 decoupling'))
    c.append(part('U7', 'TL074', 'TL074', 'SOIC14', (91.44, OPS_Y), 0, {'4': '+12V_F', '11': '-12V_F'}, unit=5))
    c.append(two('C28', 'C', '100n', 'C0603', (99.06, OPS_Y - 3.81), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U7 V+ decoupling'))
    c.append(two('C29', 'C', '100n', 'C0603', (99.06, OPS_Y + 3.81), 'GND', '-12V_F', rot=0, Voltage='50V',
                 Note='U7 V- decoupling'))

    # ---- Mode button (Bread Modular SW4, IO8) and red mode LED (Bread Modular D1: IO18 -> LED -> 1k)
    c.append(part('SW1', 'SW_Push', 'MODE', 'SW6', (337.82, 210.82), 0, {'1': 'BUTTON', '2': 'GND'},
                  MPN='6x6x7 mm THT tact switch, 4 pins (generic)',
                  Note='Mode button (Bread Modular SW4, IO8 internal pull-up), as modules/16bit SW1: generic '
                       '6 x 6 mm THT tact, 7 mm tall. Hand-soldered on the F side; pressed through the panel by the '
                       'modules/8bit printed cap'))
    c.append(two('R20', 'R', '1k', 'R0603', (345.44, LED_Y), 'LED', '_LED_A',
                 Note='Mode LED current (Bread Modular R9 1k), ~1.3 mA at 3.3 V'))
    c.append(two('D1', 'LED', 'LED_3mm_red', 'LED3', (360.68, LED_Y), 'GND', '_LED_A', rot=180,
                 Note='Mode LED: 3 mm red (as modules/16bit D1). IO18 LEDC PWM sets the brightness. Hand-soldered THT'))

    # ---- ES8388 codec (Bread Modular U4) on its own filtered +3V3_8388 rail
    c.append(part('U4', 'ES8388', 'ES8388', 'QFN28', COD, 0, CODEC,
                  Note='Bread Modular 32bit-5v U4 stereo codec, BM QFN-28 thermal-via footprint, I2C address 0x10'))
    c.append(two('R5', 'R', '10', 'R0603', (342.9, 147.32), '+3V3', '+3V3_8388',
                 Note='Codec supply filter (Bread Modular R15)'))
    for ref, x, val, fp, volt, note in (('C30', 360.68, '100u', 'C1206', '6.3V', 'Codec reservoir (Bread Modular C7)'),
                                        ('C31', 370.84, '10u', 'C0402', '10V', 'Bread Modular C5'),
                                        ('C32', 381.0, '10u', 'C0402', '10V', 'Bread Modular C37'),
                                        ('C33', 391.16, '10u', 'C0402', '10V', 'Bread Modular C38'),
                                        ('C34', 401.32, '100n', 'C0402', '16V', 'DVDD decoupling (Bread Modular C21)'),
                                        ('C35', 411.48, '100n', 'C0402', '16V', 'PVDD decoupling (Bread Modular C22)'),
                                        ('C36', 421.64, '100n', 'C0402', '16V', 'AVDD decoupling (Bread Modular C26)'),
                                        ('C37', 431.8, '100n', 'C0402', '16V', 'HPVDD decoupling (Bread Modular C39)')):
        c.append(two(ref, 'C', val, fp, (x, 160.02), '+3V3_8388', 'GND', rot=0, Voltage=volt, Note=note))
    for ref, x, net, val, note in (('C38', 360.68, 'ADCVREF', '10u', 'ADCVREF (Bread Modular C35)'),
                                   ('C39', 370.84, 'ADCVREF', '100n', 'ADCVREF (Bread Modular C36)'),
                                   ('C40', 391.16, 'VMID', '10u', 'VMID (Bread Modular C33)'),
                                   ('C41', 401.32, 'VMID', '100n', 'VMID (Bread Modular C34)'),
                                   ('C42', 421.64, 'VREF', '10u', 'VREF (Bread Modular C27)')):
        c.append(two(ref, 'C', val, 'C0402', (x, 190.5), net, 'GND', rot=0,
                     Voltage='10V' if val == '10u' else '16V', Note=note))
    for ref, x, net in (('R21', 441.96, 'CDATA'), ('R22', 452.12, 'CCLK')):
        c.append(two(ref, 'R', '4.7k', 'R0402', (x, 190.5), '+3V3', net, rot=0,
                     Note=f'I2C {net} pull-up to +3V3 (Bread Modular {"R24" if net == "CDATA" else "R25"}: '
                          '+3V3_8388; R1 layout uses the +3V3 plane, same level through the 10R)'))
    for i, (ref, a, b, note) in enumerate(I2S):
        c.append(two(ref, 'R', '33', 'R0402', (342.9, 93.98 + 7.62 * i), a, b,
                     Note=f'I2S series, Bread Modular: {note}'))

    # ---- Audio inputs: J8 IN L / J9 IN R (not normalled; firmware handles mono) -> 100k / 22k (x0.18: +/-5 V -> +/-0.9 V,
    # clip at about +/-7.5 V) -> U7C/U7D follower on +/-12 V -> 1u -> 1k -> ES8388 LIN2/RIN2 (R1), 100k bias to VMID
    for ch, y in IN_Y.items():
        o = IN_PARTS[ch]
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (444.5, y), 0,
                      {'T': f'IN_{ch}', 'S': 'GND', 'TN': None},
                      Note=f'Audio in {ch}, Eurorack level (+/-5 V). No normal: firmware handles mono'))
        c.append(two(o['rin'], 'R', '100k', 'R0603', (459.74, y), f'IN_{ch}', f'_IN{ch}_DIV',
                     Note='Input divider top: Zin ~122k'))
        c.append(two(o['rdn'], 'R', '22k', 'R0603', (467.36, y + 3.81), f'_IN{ch}_DIV', 'GND', rot=0,
                     Note='Input divider bottom: x0.18 (+/-5 V -> +/-0.9 V at the codec)'))
        pins = {o['inp']: f'_IN{ch}_DIV', o['inn']: f'_IN{ch}_BUF', o['out']: f'_IN{ch}_BUF'}
        c.append(part('U7', 'TL074', 'TL074', 'SOIC14', (485.14, y + 2.54), 0, pins, unit=o['unit']))
        c.append(two(o['cac'], 'C', '1u', 'C0402', (502.92, y + 2.54), f'_IN{ch}_BUF', f'_IN{ch}_AC', Voltage='25V',
                     Note='AC coupling into the VMID-biased codec input (1.3 Hz with 122k)'))
        c.append(two(o['rs'], 'R', '1k', 'R0603', (514.35, y + 2.54), f'_IN{ch}_AC', o['net'],
                     Note='Limits the codec pin clamp current on a +/-12 V mis-patch'))
        c.append(two(o['rb'], 'R', '100k', 'R0402', (523.24, y + 6.35), o['net'], 'VMID', rot=0,
                     Note='Input bias to VMID (Bread Modular R19/R16); 0402 to fit beside the codec (R1)'))

    # ---- Audio outputs: ES8388 LOUT1/ROUT1 -> BM 1k -> 10u -> U5A/U5B gain 1 + 56k/22k = 3.55 on +/-12 V
    # -> 1k 0.5 W -> J4 OUT L / J5 OUT R. About 1 Vrms codec full scale -> +/-5 V
    for ch, y in OUT_Y.items():
        o = OUT_PARTS[ch]
        c.append(two(o['rs'], 'R', '1k', 'R0603', (449.58, y), o['src'], f'_OUT{ch}_SRC',
                     Note='Bread Modular R17/R13 codec output series'))
        c.append(two(o['cac'], 'C', '10u', 'C0805', (461.01, y), f'_OUT{ch}_SRC', f'_OUT{ch}_AC', Voltage='25V',
                     Note='AC coupling: removes the 1.65 V VMID bias (0.16 Hz with 100k)'))
        c.append(two(o['rb'], 'R', '100k', 'R0603', (467.36, y + 3.81), f'_OUT{ch}_AC', 'GND', rot=0,
                     Note='Output stage bias to 0 V'))
        c.append(part('U5', 'TL072', 'TL072', 'SOIC8', (485.14, y + 2.54), 0,
                      {o['inp']: f'_OUT{ch}_AC', o['inn']: f'_OUT{ch}_FB', o['out']: f'_OUT{ch}_AMP'}, unit=o['unit'],
                      Note='Output stage on +/-12 V'))
        c.append(two(o['rf'], 'R', '56k', 'R0603', (485.14, y + 12.7), f'_OUT{ch}_FB', f'_OUT{ch}_AMP',
                     Note='Rf: gain 1 + 56k/22k = 3.55'))
        c.append(two(o['rg'], 'R', '22k', 'R0603', (474.98, y + 16.51), f'_OUT{ch}_FB', 'GND', rot=0,
                     Note='Rg to GND'))
        c.append(two(o['ro'], 'R', '1k', 'R1206', (505.46, y + 2.54), f'_OUT{ch}_AMP', f'OUT_{ch}', Power='0.5W',
                     Note='Output series: short / mis-patch limit; 0.5 W for a permanent +/-12 V mis-patch'))
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (528.32, y + 2.54), 180,
                      {'T': f'OUT_{ch}', 'S': 'GND', 'TN': None}, Note=f'Out {ch}, Eurorack level (~10 Vpp)'))
    bx, by = U5_PWR
    c.append(part('U5', 'TL072', 'TL072', 'SOIC8', U5_PWR, 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(two('C47', 'C', '100n', 'C0603', (bx + 7.62, by - 3.81), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U5 V+ decoupling'))
    c.append(two('C48', 'C', '100n', 'C0603', (bx + 7.62, by + 3.81), 'GND', '-12V_F', rot=0, Voltage='50V',
                 Note='U5 V- decoupling'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # Power entry (as modules/16bit)
    W += [['J6.1', (33.02, 60.96), (33.02, 55.88), (50.8, 55.88), (50.8, 60.96), 'J6.2'], [(50.8, 55.88), 'D3.1'],
          ['J6.3', (33.02, 63.5), (33.02, 68.58), 'J6.7'], ['J6.5', (33.02, 66.04)], [(33.02, 68.58), (27.94, 68.58)],
          ['J6.4', (50.8, 63.5), (50.8, 68.58), 'J6.8'], ['J6.6', (50.8, 66.04)], [(50.8, 68.58), (53.34, 68.58)],
          ['J6.9', (33.02, 71.12), (33.02, 76.2), (50.8, 76.2), (50.8, 71.12), 'J6.10'], [(50.8, 76.2), 'D2.2'],
          ['D3.2', (86.36, 55.88)], ['D2.1', 'U8.3'], ['U8.2', 'U9.3'], ['U9.2', (195.58, 76.2)]]
    P += [('-12V', (55.88, 55.88), 0), ('GND', (27.94, 68.58), 0), ('GND', (53.34, 68.58), 90),
          ('+12V', (55.88, 76.2), 0), ('-12V_F', (86.36, 55.88), 0), ('+12V_F', (88.9, 76.2), 0),
          ('+5V', (147.32, 76.2), 0), ('+3V3', (195.58, 76.2), 0)]
    # ESP32 supply: FB1 -> +3V3_ESP32 with C5/C6
    x, y = ESP
    W += [['FB1.2', (x, y - 45.72), 'U1.2'], [(x, y - 45.72), (x + 25.4, y - 45.72)]]
    P += [('+3V3_ESP32', (x + 25.4, y - 45.72), 0)]
    # EN reset RC and RESET / BOOT buttons
    W += [['U1.3', 'SW3.2'], ['U1.27', 'SW2.2']]
    L += [('EN', (256.54, 129.54), 'R'), ('BOOT', (256.54, 134.62), 'R')]
    # USB-C data pairs (straight to the ESP32-S3 PHY), shield
    W += [['J7.A7', (157.48, 170.18)], ['J7.B7', (144.78, 172.72), (144.78, 170.18)],
          ['J7.A6', (147.32, 175.26), (147.32, 180.34), (157.48, 180.34)], ['J7.B6', (147.32, 177.8)],
          ['J7.SH', 'C24.1']]
    L += [('USB_DM', (157.48, 170.18), 'R'), ('USB_DP', (157.48, 180.34), 'R')]
    # MIDI in (as modules/16bit)
    W += [['J1.T', 'R1.1'], ['J1.S', (30.48, 154.94), (30.48, 157.48)], ['R1.2', 'Q1.1'], ['D4.1', (63.5, 152.4)],
          ['Q1.3', 'R2.1'], [(76.2, 142.24), 'JP1.1'],
          ['JP1.2', (93.98, 149.86), (99.06, 149.86)],
          ['JP1.3', (101.6, 142.24), (101.6, 124.46), (46.99, 124.46), (46.99, 152.4)]]
    P += [('GND', (30.48, 157.48), 0)]
    L += [('MIDI_IN', (55.88, 124.46), 'R'), ('RX_Q', (80.01, 142.24), 'R'), ('MIDI_RX', (99.06, 149.86), 'R')]
    # CV inputs (as modules/16bit)
    for i, y in enumerate(CV_Y, 1):
        jack, rv, rin, d = ('J2', 'RV1', 'R13', 'D5') if i == 1 else ('J3', 'RV2', 'R16', 'D6')
        inp, inn, out = ('U6.5', 'U6.6', 'U6.7') if i == 1 else ('U6.3', 'U6.2', 'U6.1')
        ainp, ainn, aout = ('U7.5', 'U7.6', 'U7.7') if i == 1 else ('U7.3', 'U7.2', 'U7.1')
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
    W += [['C28.2', (104.14, OPS_Y)]]
    P += [('GND', (104.14, OPS_Y), 90)]
    # Mode LED: IO18 -> R20 -> D1 -> GND
    W += [['R20.1', (335.28, LED_Y)], ['R20.2', 'D1.2'], ['D1.1', (370.84, LED_Y), (370.84, LED_Y + 5.08)]]
    P += [('GND', (370.84, LED_Y + 5.08), 0)]
    L += [('LED', (335.28, LED_Y), 'L')]
    # Codec supply pins drawn to one +3V3_8388 symbol per side; reference / bias caps in pairs
    cx, cy = COD
    W += [['U4.2', (cx - 20.32, cy - 13.97)], ['U4.3', (cx - 20.32, cy - 10.16)],
          [(cx - 20.32, cy - 13.97), (cx - 20.32, cy - 10.16)], [(cx - 20.32, cy - 13.97), (cx - 25.4, cy - 13.97)],
          ['U4.16', (cx + 20.32, cy - 13.97)], ['U4.17', (cx + 20.32, cy - 10.16)],
          [(cx + 20.32, cy - 13.97), (cx + 20.32, cy - 10.16)], [(cx + 20.32, cy - 13.97), (cx + 25.4, cy - 13.97)]]
    P += [('+3V3_8388', (cx - 25.4, cy - 13.97), 90), ('+3V3_8388', (cx + 25.4, cy - 13.97), 270)]
    W += [['R5.2', (353.06, 147.32)]]
    P += [('+3V3_8388', (353.06, 147.32), 0)]
    for a, b, net in (('C38', 'C39', 'ADCVREF'), ('C40', 'C41', 'VMID')):
        W += [[f'{a}.1', f'{b}.1'], [f'{a}.1', (f'{a}.1', 0, -2.54)]]
        L += [(net, (f'{a}.1', 0, -2.54), 'U')]
    # Audio inputs
    for ch, y in IN_Y.items():
        o = IN_PARTS[ch]
        u = lambda n: f'U7.{n}'  # noqa: E731
        W += [[f"{o['j']}.T", f"{o['rin']}.1"], [f"{o['rin']}.2", u(o['inp'])],
              [u(o['out']), f"{o['cac']}.1"],
              [(495.3, y + 2.54), (495.3, y + 10.16), (474.98, y + 10.16), (474.98, y + 5.08), u(o['inn'])],
              [f"{o['cac']}.2", f"{o['rs']}.1"], [f"{o['rs']}.2", (530.86, y + 2.54)],
              [f"{o['j']}.S", (452.12, y - 2.54), (452.12, y - 5.08), (454.66, y - 5.08)]]
        P += [('GND', (454.66, y - 5.08), 90)]
        L += [(f'IN_{ch}', (450.85, y), 'R'), (o['net'], (530.86, y + 2.54), 'R')]
    # Audio outputs
    for ch, y in OUT_Y.items():
        o = OUT_PARTS[ch]
        u = lambda n: f'U5.{n}'  # noqa: E731
        W += [[f"{o['rs']}.2", f"{o['cac']}.1"], [f"{o['cac']}.2", u(o['inp'])],
              [u(o['inn']), (474.98, y + 5.08), (474.98, y + 12.7), f"{o['rf']}.1"],
              [f"{o['rf']}.2", (495.3, y + 12.7), (495.3, y + 2.54)],
              [u(o['out']), f"{o['ro']}.1"], [f"{o['ro']}.2", f"{o['j']}.T"],
              [f"{o['j']}.S", (520.7, y + 5.08), (520.7, y + 7.62)]]
        P += [('GND', (520.7, y + 7.62), 0)]
        L += [(f'OUT_{ch}', (513.08, y + 2.54), 'R')]
    bx, by = U5_PWR
    W += [['U5.8', 'C47.1'], ['U5.4', 'C48.2'], ['C47.2', (bx + 20.32, by)]]
    P += [('+12V_F', (bx + 2.54, by - 7.62), 0), ('-12V_F', (bx + 2.54, by + 7.62), 180), ('GND', (bx + 20.32, by), 0)]
    return W, P, L


# JLCPCB parts. Codes reused from modules/16bit (live-checked 2026-10-21) and from the Bread Modular
# 32bit-5v BOM (ESP32-S3, ES8388, ferrite, 10R, 4.7k, 10u/1u 0402); NOT live-checked for 32bit yet.
# THT jacks, pots, LED, MODE switch and the power header are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C4410', MPN='1206W4F1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10', 'R0603'): dict(LCSC='C22859', MPN='0603WAF100JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R0402'): dict(LCSC='C25105', MPN='0402WGF330JTCE', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0402'): dict(LCSC='C25900', MPN='0402WGF4701TCE', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0402'): dict(LCSC='C25744', MPN='0402WGF1002TCE', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0402'): dict(LCSC='C25905', MPN='0402WGF5101TCE', Manufacturer='UNI-ROYAL'),
    ('R', '120k', 'R0603'): dict(LCSC='C25808', MPN='0603WAF1203T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0402'): dict(LCSC='C25741', MPN='0402WGF1003TCE', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('C', '1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0603'): dict(LCSC='C19702', MPN='CL10A106KP8NNNC', Manufacturer='Samsung'),
    ('C', '10u', 'C0402'): dict(LCSC='C15525', MPN='CL05A106MQ5NUNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0402'): dict(LCSC='C52923', MPN='CL05A105KA5NQNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0402'): dict(LCSC='C1525', MPN='CL05B104KO5NNNC', Manufacturer='Samsung'),
    ('C', '10n', 'C0402'): dict(LCSC='C15195', MPN='CL05B103KB5NNNC', Manufacturer='Samsung'),
    ('C', '22u', 'C0805'): dict(LCSC='C45783', MPN='CL21A226MAQNNNE', Manufacturer='Samsung'),
    ('C', '100u', 'C1206'): dict(LCSC='C15008', MPN='CL31A107MQHNNNE', Manufacturer='Samsung'),
    ('FerriteBead', 'GZ2012D121TF', 'C0805'): dict(LCSC='C5671', MPN='GZ2012D121TF', Manufacturer='Sunlord'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904(RANGE:100-300)',
                                            Manufacturer='CJ (Jiangsu Changjing)'),
    ('1N4148W', '1N4148W', 'SOD123'): dict(LCSC='C81598', MPN='1N4148W', Manufacturer='ST(Semtech)'),
    ('BAT54SW', 'BAT54SW', 'SOT323'): dict(LCSC='C78260', MPN='BAT54SWT1G', Manufacturer='onsemi'),
    ('SW_Push', 'RESET', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('SW_Push', 'BOOT', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('USB_C_Receptacle_USB2.0_14P', 'USB-C', 'USBC'): dict(LCSC='C165948', MPN='TYPE-C-31-M-12',
                                                          Manufacturer='Korean Hroparts Elec'),
    ('ESP32-S3-WROOM-1', 'ESP32-S3-WROOM-1U-N16R8', 'WROOM1U'): dict(LCSC='C3013946', MPN='ESP32-S3-WROOM-1U-N16R8',
                                                                    Manufacturer='Espressif Systems'),
    ('ES8388', 'ES8388', 'QFN28'): dict(LCSC='C365736', MPN='ES8388', Manufacturer='Everest Semiconductor'),
    ('TL074', 'TL074', 'SOIC14'): dict(LCSC='C12594', MPN='TL074CDR', Manufacturer='Texas Instruments'),
    ('TL072', 'TL072', 'SOIC8'): dict(LCSC='C6961', MPN='TL072CDT', Manufacturer='STMicroelectronics'),
    ('MCP6002-xSN', 'MCP6002', 'SOIC8'): dict(LCSC='C7377', MPN='MCP6002T-I/SN', Manufacturer='Microchip'),
    ('AMS1117-5.0', 'AMS1117-5.0', 'SOT223'): dict(LCSC='C6187', MPN='AMS1117-5.0', Manufacturer='AMS'),
    ('AMS1117-3.3', 'AMS1117-3.3', 'SOT223'): dict(LCSC='C6186', MPN='AMS1117-3.3', Manufacturer='AMS'),
}

# Block titles (drawn as sheet text).
TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR 32BIT - S1 schematic (Bread Modular 32bit-5v for Eurorack, 6HP, 4 layers). '
                     'Circuit intent: docs/research.md; placement: docs/geometry.json', 2.0),
    ((20.32, 33.02), 'POWER: +12V -> D2 -> +12V_F (op-amp V+, U8 AMS1117-5.0 -> +5V -> U9 AMS1117-3.3 -> +3V3); '
                     '-12V -> D3 -> -12V_F (op-amp V-)', 1.4),
    ((20.32, 101.6), 'PWR_FLAG: GND/+12V/-12V mark the Eurorack entry at J6; +12V_F/-12V_F are fed only through D2/D3;\n'
                      '+3V3_ESP32 (via FB1) and +3V3_8388 (via R5) are fed through passive parts.', 1.1),
    ((20.32, 116.84), 'MIDI IN (TS): modules/16bit NPN front end at 3.3 V, no opto -> RXD0 (GPIO44, UART0)', 1.4),
    ((20.32, 180.34), 'JP1 RX SOURCE (back, shipped OPEN, bridge one pair): 1-2 = PROTECTED (Q1 drives RXD0,\n'
                      'firmware inverts the UART RX line); 2-3 = DIRECT (unprotected, stock BM firmware). Never both.', 1.1),
    ((20.32, 203.2), 'CV IN 1/2: tip normalled to +5V -> RV1/RV2 50k attenuator -> U7B/U7A TL074 follower\n'
                     '-> 100k / 56k to +3V3 / 120k to GND, BAT54SW clamp, 1n -> U6B/U6A MCP6002 follower -> IO1/IO2.\n'
                     'Unpatched: RV = 0..+5 V knob. Patched: RV scales the CV. -5.9..+6.0 V -> 0..3.3 V.', 1.1),
    ((116.84, 139.7), 'USB-C (data only, as Bread Modular): VBUS not connected,\n'
                      'D+/D- straight to the ESP32-S3 USB PHY (flash over USB).', 1.1),
    ((205.74, 93.98), 'ESP32-S3-WROOM-1U-N16R8 (Bread Modular 32bit-5v GPIO map).\n'
                      'RESET = EN low; BOOT = IO0 low at reset (download mode). IO35-37 = octal PSRAM, keep open.', 1.1),
    ((322.58, 248.92), 'MODE: SW1 (6 x 6 mm THT tact) on IO8, red LED on IO18 through 1k (Bread Modular pins).\n'
                       'IO18 LEDC PWM sets the LED brightness.', 1.1),
    ((330.2, 71.12), 'ES8388 CODEC (Bread Modular U4): I2S IO11-14/IO21 through 33R,\n'
                    'I2C IO38 (CCLK) / IO39 (CDATA), CE = GND (0x10). Inputs on LIN2/RIN2. +3V3 -> R5 10R -> +3V3_8388.', 1.1),
    ((436.88, 33.02), 'AUDIO IN L/R: 100k / 22k (x0.18) -> U7C/U7D follower -> 1u -> 1k -> LIN2/RIN2 (100k to VMID).\n'
                      '+/-5 V -> +/-0.9 V; codec PGA sets the gain. No IN R normal: firmware handles mono.', 1.1),
    ((436.88, 101.6), 'AUDIO OUT L/R: LOUT1/ROUT1 -> 1k -> 10u -> U5A/U5B gain 3.55 (56k/22k) -> 1k 0.5 W -> J4/J5.\n'
                      '~1 Vrms codec full scale -> +/-5 V; the codec output volume trims the level.', 1.1),
]

# Reference / value text: two-pin parts on the free side ('left' overrides), a few parts placed by hand
# (offsets from the symbol origin, horizontal text; keys 'REF' or 'REF/unit', optional justify).
TEXT_LEFT = {'R3', 'D4', 'C24', 'R15', 'R18', 'C8'}
TEXT_POS = {'D1': ((0, -5.08), (0, -2.54)),
            'U8': ((0, -6.35), (0, -3.81)), 'U9': ((0, -6.35), (0, -3.81)),
            'U5/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U6/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U7/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'JP1': ((0, -6.35), (0, -3.81)), 'D5': ((0, -6.35), (0, -3.81)), 'D6': ((0, -6.35), (0, -3.81)),
            'R20': ((0, -5.08), (0, -2.54)), 'SW2': ((-6.35, -1.27), (-6.35, 1.27)),
            'SW3': ((-6.35, -1.27), (-6.35, 1.27)), 'FB1': ((0, -3.81), (0, 3.81)),
            'U1': ((-10.16, -29.21), (5.08, -30.48), 'left'), 'U4': ((0, -21.59), (0, 39.37)),
            'C43': ((0, -6.35), (0, -3.81)), 'C44': ((0, -6.35), (0, -3.81)),
            'C45': ((0, -6.35), (0, -3.81)), 'C46': ((0, -6.35), (0, -3.81)),
            'J4': ((0, -11.43), (0, -8.89)), 'J5': ((0, -11.43), (0, -8.89))}

MULTI_UNIT = {'U5': {1, 2, 3}, 'U6': {1, 2, 3}, 'U7': {1, 2, 3, 4, 5}}
