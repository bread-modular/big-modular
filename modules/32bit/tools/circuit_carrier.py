"""32bit carrier (jack board) S4 circuit table, drawing and sourcing (tools/build_schematic.py).

S4 (user, 2026-11-23): the modules/usb-audio S5 carrier with the ESP32-S3 MCU board (32bit-mcu) on its
J6/J7 strips, for a master processor in front of PA systems (docs/research.md section 9). Changes from
usb-audio S5: the four volume pots leave the audio path (IN: 100k to GND sets the input impedance,
jack -> 1k -> follower; OUT: difference amplifier -> 1k -> jack, no follower U7); RV1 / RV2 are two
50k control pots read by the ESP32 ADC, plus a MODE button and LED, all firmware-defined; RESET / BOOT
pull EN / GPIO0 low (ESP32-S3); no SWD header; R1 22R for the ESP32-S3 load. Kept: every reference
designator of the kept usb-audio parts, so the routed usb-audio copper carries over.

6HP, 2 in / 2 out, DC-coupled, +/-5 V (CV too), 48 kHz (up to 192 kHz):

- Power: Eurorack 10-pin +/-12 V -> B5819W series Schottkys -> +12V_F / -12V_F (op-amps);
  +12V_F -> U1 AMS1117-5.0 -> +5VA (CS4272 VA, U6, the R49 reference divider); +12V_F -> R1 22R 1 W -> U2 AMS1117-3.3 -> +3V3
  (MCU board, pots, I2C pull-ups); +3V3 -> FB1 -> +3V3_C (CS4272 VD/VL, oscillator).
  +3V3 budget (S4): ESP32-S3R8 at 240 MHz, radio off, 66..108 mA (datasheet v2.2 table 5-9, dual core, peripheral
  clocks off..on) + flash / in-package PSRAM (the datasheet says higher with PSRAM; ~20 mA allowed) + codec VD/VL +
  oscillator (~20 mA) + LED, pots, pull-ups (~5 mA): ~130 mA typical, 180 mA design maximum (the S3 module drew
  an estimated ~110 mA with the ES8388). R1 22R: 0.37 W at 130 mA, 0.71 W at 180 mA (1 W part); U2 then sees
  >= 6.9 V at 180 mA from an 11.4 V rail (dropout 1.3 V maximum) and drops ~0.7 W at 130 mA.
- Codec (S4, 2026-11-21): U3 CS4272 (the CS4270 is discontinued), differential in and out, I2C
  control-port mode, address 0x10 (AD0 = GND), master. External MCLK (XTI = GND, XTO open): Y1
  24.576 MHz = 512 / 256 / 128 x 48 / 96 / 192 kHz (Ratio1:0 = 10, table 9). It drives SCLK (64 Fs)
  and LRCK to the ESP32-S3 I2S port (slave, full duplex). RST held low by R17 until the MCU releases it.
  The codec leaves reset as a clock slave (SCLK / LRCK are inputs until the M/S bit is written), so
  R14 / R16 10k hold I2S_SCLK / I2S_LRCK low and R48 47k holds I2S_DAC low: no floating clock line
  while the MCU's I2S slaves wait (the first board's random bit offsets). TP1 = MCLK scope pad; the
  other clock / data lines are probed on the J7 joints (B silk).
- Inputs: jack (TN to GND: unpatched = 0 V; R50/R51 100k to GND = input impedance and bias path for an
  AC-coupled source) -> R20/R21 1k -> U4A/U4B follower (+/-12 V) -> U6 inverting stage on +5VA (gain -5.1k/20k, + input at
  VB_IN = VCOM_BUF x 2/2.51 so 0 V in = VCOM_BUF) = AIN-; U6 unity inverter about VCOM_BUF = AIN+; each
  leg 100R, 2.2n C0G across the pair. Differential full scale 1.13 x VA = 5.65 Vpp -> +/-5.54 V at
  the jack. The 5 V stages cannot push AIN outside 0..5 V on a +/-12 V mis-patch. The ADC HPF is
  frozen for DC (register 06h).
- Outputs: AOUT+/- -> U5A/U5B difference amplifier (6.8k / 15k, 100p: gain 2.2, 106 kHz) on
  +/-12 V: the common mode (VCOM) cancels, so no VREF_OUT and no power-up step; DAC full scale
  0.96 x VA = 4.8 Vpp differential -> +/-5.29 V. AOUT sees 6.8k (minimum 3k). -> 2 x 2k 1206 in
  parallel (1k, 0.5 W) -> jack (S4: no volume pot and follower; the NE5532 drives the 1k + cable).
- Reference on +5VA (S5, 2026-11-22: no buffer op-amp): R49 2.7k from +5VA over R40 + R41 (2.51k) makes
  VCOM_BUF = 0.482 x VA = 2.41 V (the codec's own VCOM is about 0.48 x VA and moves with the same rail),
  C38 10u + C39 100n to GND (12 Hz). VCOM_BUF only sets the common mode of the differential ADC drive
  and feeds op-amp + inputs (no signal current): AIN+ - AIN- = 2 x 0.255 x Vin whatever it is, as long
  as VB_IN = VCOM_BUF x 2/2.51, which R40 / R41 hold (no capacitor on VB_IN). The codec's VCOM pin
  only has its own filter capacitors now (25k source, 1 uA max: nothing may load it).
- U4 / U5 are NE5532 (JLCPCB Basic, as modules/multi-mix U8): bipolar inputs, 200 nA typical / 800 nA
  maximum bias current, 4 mV maximum offset; with the 1k in front of each follower the bias adds 0.2 mV
  typical (an unpatched input sits on TN = GND). Datasheet values.
- Controls (firmware-defined): RV1 / RV2 50k from POT_TOP (+3V3 -> R52 2.2k, C42 1u: 3.03 V, inside the
  ESP32-S3 ADC 12 dB range) to GND, wiper -> POT1 / POT2 (their 100n sampling caps sit at the ESP32 pins on the
  MCU board);
  SW3 MODE to GND (ESP32 pull-up); LED -> R53 1k -> D3 3 mm red (~1.5 mA).
- I2C pull-ups: on the MCU board (R106 / R107 2.2k), not on the carrier (usb-audio R18 / R19 removed).
- MCU board link: J6/J7 1x10 2.54 mm pin headers (the MCU board solders on top of them, F side).
  RESET (SW1, EN low) and BOOT (SW2, GPIO0 low) sit on the carrier B side; the ESP32-S3 also enters
  download mode over its USB, so they are for recovery.
"""

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+3V3_C': '+3V3', '+5VA': '+5VA', '+12V': '+12V',
               '-12V': '-12V', '+12V_F': '+12V', '-12V_F': '-12V'}

# Symbols drawn mirrored about X (pots: pin 3 up, wiper right, pin 1 down; input jacks: sleeve down).
MIRROR_X = {'RV1', 'RV2', 'J2', 'J3'}

# Header strips J6/J7 are bought and soldered by hand with the MCU board (no LCSC field); listed in
# the carrier BOM. The MCU board's J102/J103 are the same strips seen from the other board.
NOT_ASSEMBLED = {'TP1'}   # bare test pad

PWR = (40.64, 66.04)          # J1 (as modules/32bit J6)
COD = (279.4, 165.1)          # U3 CS4270
IN_Y = (241.3, 274.32)        # input channel rows
OUT_Y = (254.0, 294.64)       # output channel rows
IN_X0 = 22.86                 # input jack column
OUT_X0 = 335.28               # output R30 column
REF_Y = 330.2                 # reference divider row
HDR = (482.6, 76.2)           # J6; J7 at +30.48

IN_PARTS = [dict(j='J2', rpd='R50', rs='R20', fu='U4', fun=1, rin='R22', rf='R24', cf='C20', dun=1, iun=2,
                 ri='R44', rif='R46', rn='R26', rp='R28', c='C22', ch='1', adc='ADC_A'),
            dict(j='J3', rpd='R51', rs='R21', fu='U4', fun=2, rin='R23', rf='R25', cf='C21', dun=3, iun=4,
                 ri='R45', rif='R47', rn='R27', rp='R29', c='C23', ch='2', adc='ADC_B')]
OUT_PARTS = [dict(rn='R30', rp='R32', rf='R34', rg='R42', cf='C34', cg='C36', u='U5', un=1,
                  ro='R36', rpar='R38', j='J4', ch='1', dac='DAC_A'),
             dict(rn='R31', rp='R33', rf='R35', rg='R43', cf='C35', cg='C37', u='U5', un=2,
                  ro='R37', rpar='R39', j='J5', ch='2', dac='DAC_B')]
CTL = (373.38, 340.36)        # controls block: pots, MODE, LED
# Op-amp unit pins: unit -> (+, -, out)
OPA4 = {1: ('3', '2', '1'), 2: ('5', '6', '7'), 3: ('10', '9', '8'), 4: ('12', '13', '14')}
OPA2 = {1: ('3', '2', '1'), 2: ('5', '6', '7')}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/FB: rot 90 = horizontal, pin 1 left; rot 0 = vertical,
    pin 1 on top. Diodes: rot 0 = K left."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


# Dual op-amp on U4 / U5 (stock dual symbol, SOIC-8), all on +/-12 V. NE5532 since S5 (user, 2026-11-22): a
# JLCPCB Basic part (C7426, no feeder fee), as modules/multi-mix U8. Before: OPA1678IDR C192421 (pre-order only at
# JLCPCB on 2026-11-22), then OPA1656IDR C1849431 (Extended, about $1.1 each). Same SOIC-8 pinout. Unity-gain
# stable, 5 nV/rtHz, supply +/-5 .. +/-15 V, inputs and output stay about 2 .. 3 V inside the rails (+/-5.5 V
# signals on +/-11.7 V are well inside); bipolar inputs: 200 nA typical / 800 nA maximum bias current, anti-parallel
# diodes between the inputs (the followers have 1k / the pot in series). It cannot run on +5VA, so the VCOM
# buffer U8 is gone (reference divider R49).
DUAL = 'NE5532'


def opamp(ref, unit, at, plus, minus, out, quad=True, **fields):
    p, m, o = (OPA4 if quad else OPA2)[unit]
    return part(ref, 'OPA1679' if quad else DUAL, 'OPA1679' if quad else DUAL,
                'SOIC14' if quad else 'SOIC8', at, 0, {p: plus, m: minus, o: out}, unit=unit, **fields)


def circuit():
    c = []
    # ---- Power entry (as modules/32bit): Eurorack +/-12 V -> series Schottkys
    c.append(part('J1', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', PWR, 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(two('D1', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 55.88), '-12V', '-12V_F', rot=0,
                 Note='-12 V series reverse-polarity protection'))
    c.append(two('D2', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 76.2), '+12V_F', '+12V', rot=180,
                 Note='+12 V series reverse-polarity protection'))
    c.append(two('C2', 'C', '10u', 'C0805', (78.74, 59.69), 'GND', '-12V_F', rot=180, Voltage='25V',
                 Note='-12V_F bulk'))
    c.append(two('C1', 'C', '10u', 'C0805', (78.74, 80.01), '+12V_F', 'GND', rot=0, Voltage='25V',
                 Note='+12V_F bulk'))
    c.append(part('U1', 'AMS1117-5.0', 'AMS1117-5.0', 'SOT223', (124.46, 76.2), 0,
                  {'1': 'GND', '2': '+5VA', '3': '+12V_F'},
                  Note='+5VA: CS4272 VA (37 mA) + U6 (~10 mA) + reference divider (1 mA). ~50 mA x 7 V = 0.35 W'))
    c.append(two('C3', 'C', '22u', 'C0805', (139.7, 80.01), '+5VA', 'GND', rot=0, Voltage='25V', Note='U1 output'))
    c.append(two('C4', 'C', '100n', 'C0603', (147.32, 80.01), '+5VA', 'GND', rot=0, Voltage='50V',
                 Note='U1 output HF'))
    c.append(two('R1', 'R', '22', 'R2512', (101.6, 101.6), '+12V_F', '_V3_IN', Power='1W',
                 Note='Pre-drop for U2 (S4, ESP32-S3 load): 130 mA -> 2.9 V / 0.37 W here, U2 sees ~8.8 V (0.71 W); '
                      '180 mA design maximum -> 0.71 W here, U2 input >= 6.9 V from an 11.4 V rail (4.6 V minimum)'))
    c.append(two('C5', 'C', '10u', 'C0805', (111.76, 105.41), '_V3_IN', 'GND', rot=0, Voltage='25V',
                 Note='U2 input'))
    c.append(part('U2', 'AMS1117-3.3', 'AMS1117-3.3', 'SOT223', (124.46, 101.6), 0,
                  {'1': 'GND', '2': '+3V3', '3': '_V3_IN'},
                  Note='+3V3: MCU board (ESP32-S3R8 + flash, ~110 mA typical at 240 MHz, radio off), codec VD/VL, '
                       'oscillator, pots: ~130 mA typical, 180 mA design maximum'))
    c.append(two('C6', 'C', '22u', 'C0805', (139.7, 105.41), '+3V3', 'GND', rot=0, Voltage='25V', Note='U2 output'))
    c.append(two('C7', 'C', '10u', 'C0805', (147.32, 105.41), '+3V3', 'GND', rot=0, Voltage='25V',
                 Note='+3V3 bulk'))
    c.append(two('FB1', 'FerriteBead', 'GZ2012D121TF', 'C0805', (175.26, 101.6), '+3V3', '+3V3_C',
                 Note='Codec digital supply filter (as modules/32bit FB1, C_0805 land)'))
    for ref, net, at, rot in (('#FLG01', 'GND', (30.48, 68.58), 0), ('#FLG02', '+12V_F', (71.12, 76.2), 180),
                              ('#FLG03', '-12V_F', (71.12, 55.88), 180), ('#FLG04', '+12V', (53.34, 76.2), 180),
                              ('#FLG05', '-12V', (53.34, 55.88), 180), ('#FLG06', '_V3_IN', (116.84, 101.6), 0),
                              ('#FLG07', '+3V3_C', (185.42, 101.6), 0)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))

    # ---- CS4272 codec (I2C control port), oscillator, clock/data series resistors, pull-downs
    x, y = COD
    c.append(part('U3', 'CS4272', 'CS4272', 'TSSOP28', COD, 0,
                  {'1': None, '2': 'GND', '3': '_MCLK_C', '4': 'CODEC_LRCK', '5': 'CODEC_SCLK', '6': 'CODEC_SDOUT',
                   '7': 'I2S_DAC', '8': 'GND', '9': '+3V3_C', '10': '+3V3_C', '11': 'I2C_SCL', '12': 'I2C_SDA',
                   '13': 'GND', '14': 'CODEC_RST', '15': 'VCOM', '16': 'ADC_AN', '17': 'ADC_AP', '18': 'ADC_BP',
                   '19': 'ADC_BN', '20': '+5VA', '21': 'GND', '22': '_FILTP', '23': None, '24': 'DAC_AN',
                   '25': 'DAC_AP', '26': 'DAC_BP', '27': 'DAC_BN', '28': None},
                  Note='24-bit 192 kHz stereo codec, differential in/out, 114 dB. I2C 0x10 (AD0 = GND). Master, '
                       'external MCLK (XTI = GND); the ESP32-S3 I2S port is its slave. As modules/usb-audio S5'))
    c.append(part('Y1', 'ASE-xxxMHz', '24.576MHz', 'OSC3225', (210.82, 157.48), 0,
                  {'1': '+3V3_C', '2': 'GND', '3': '_OSC', '4': '+3V3_C'},
                  Note='24.576 MHz 3.3 V CMOS oscillator (YXC OT2EL, 3225): MCLK = 512 / 256 / 128 x 48 / 96 / 192 kHz'))
    c.append(two('R10', 'R', '33', 'R0603', (226.06, 157.48), '_OSC', '_MCLK_C',
                 Note='Series termination: MCLK from Y1'))
    c.append(two('R13', 'R', '33', 'R0603', (238.76, 165.1), 'I2S_ADC', 'CODEC_SDOUT',
                 Note='Series termination: SDOUT (ADC data) to the MCU'))
    c.append(two('R15', 'R', '47k', 'R0603', (248.92, 171.45), 'CODEC_SDOUT', 'GND', rot=0,
                 Note='SDOUT (M/S) 47k pull-down: if the MCU never configures the codec, stand-alone mode '
                      'starts as slave (does not drive SCLK/LRCK)'))
    for ref, row, a, b, note in (('R12', 180.34, 'I2S_LRCK', 'CODEC_LRCK', 'LRCK out (codec master)'),
                                 ('R11', 187.96, 'I2S_SCLK', 'CODEC_SCLK', 'SCLK out (codec master)')):
        c.append(two(ref, 'R', '33', 'R0603', (195.58, row), a, b, Note=f'Series termination: {note}'))
    for ref, xx, val, net, note in (
            ('R16', 180.34, '10k', 'I2S_LRCK', 'LRCK'), ('R14', 190.5, '10k', 'I2S_SCLK', 'SCLK'),
            ('R48', 200.66, '47k', 'I2S_DAC', 'SDIN (DAC data)')):
        c.append(two(ref, 'R', val, 'R0603', (xx, 215.9), net, 'GND', rot=0,
                     Note=f'{note} pull-down: the line never floats while the codec pins are inputs (reset, '
                          'slave default before the M/S bit) or the MCU port is off'))
    c.append(two('R17', 'R', '10k', 'R0603', (238.76, 190.5), 'CODEC_RST', 'GND', rot=0,
                 Note='Holds the codec in reset until the ESP32-S3 releases it'))
    c.append(two('C16', 'C', '100n', 'C0603', (312.42, 151.13), '_FILTP', 'GND', rot=0, Voltage='50V',
                 Note='FILT+ HF, closest to pin 22'))
    c.append(two('C15', 'C', '47u', 'C0805', (320.04, 151.13), '_FILTP', 'GND', rot=0, Voltage='6.3V',
                 Note='FILT+ reservoir (datasheet 47 uF)'))
    # decoupling row (y 205.74)
    for ref, xx, val, fp, net, volt, note in (
            ('C10', 231.14, '1u', 'C0603', '+5VA', '50V', 'VA bulk'),
            ('C11', 241.3, '100n', 'C0603', '+5VA', '50V', 'VA HF, closest to pin 20'),
            ('C12', 256.54, '1u', 'C0603', '+3V3_C', '50V', 'VD / VL bulk'),
            ('C13', 266.7, '100n', 'C0603', '+3V3_C', '50V', 'VD HF, closest to pin 9'),
            ('C14', 276.86, '100n', 'C0603', '+3V3_C', '50V', 'VL'),
            ('C19', 287.02, '100n', 'C0603', '+3V3_C', '50V', 'Y1 supply')):
        c.append(two(ref, 'C', val, fp, (xx, 205.74), net, 'GND', rot=0, Voltage=volt, Note=note))
    c.append(two('C17', 'C', '1u', 'C0603', (304.8, 205.74), 'VCOM', 'GND', rot=0, Voltage='50V',
                 Note='VCOM filter (datasheet 1 uF, not more)'))
    c.append(two('C18', 'C', '100n', 'C0603', (314.96, 205.74), 'VCOM', 'GND', rot=0, Voltage='50V',
                 Note='VCOM HF, closest to pin 15'))
    # I2C pull-ups (usb-audio R18 / R19) are on the MCU board since S4 (R106 / R107): their place under J6 is the
    # channel the pot, MODE and LED lines take down the left edge.
    c.append(part('TP1', 'TestPoint', 'MCLK', 'TP15', (246.38, 147.32), 0, {'1': '_MCLK_C'},
                  Note='Scope pad, B side: 24.576 MHz at the codec pin. SCLK / LRCK / ADC / DAC / RST / GND are '
                       'probed on the J7 solder joints (B silk labels)'))

    # ---- Inputs
    for o, y in zip(IN_PARTS, IN_Y):
        x0 = IN_X0
        n = o['ch']
        xd, xi = x0 + 81.28, x0 + 116.84
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0, y), 0,
                      {'T': f'IN{n}', 'S': 'GND', 'TN': 'GND'},
                      Note=f'IN {n}: +/-5 V audio or CV, DC-coupled. TN to GND: unpatched = 0 V'))
        c.append(two(o['rpd'], 'R', '100k', 'R0603', (x0 + 17.78, y + 3.81), f'IN{n}', 'GND', rot=0,
                     Note=f'IN {n} input impedance 100k and DC path for an AC-coupled source (S4: no volume pot)'))
        c.append(two(o['rs'], 'R', '1k', 'R0603', (x0 + 27.94, y + 3.81), f'IN{n}', f'_IN{n}_P',
                     Note='Follower input protection (limits the current in the NE5532 input diodes on a mis-patch)'))
        c.append(opamp(o['fu'], o['fun'], (x0 + 45.72, y + 6.35), f'_IN{n}_P', f'_IN{n}_BUF', f'_IN{n}_BUF',
                       quad=False, Note='+/-12 V input followers (100k input impedance with R50/R51)'))
        c.append(two(o['rin'], 'R', '20k', 'R0603', (x0 + 63.5, y + 6.35), f'_IN{n}_BUF', f'_IN{n}_SUM',
                     Note='Driver Rin: gain -5.1k/20k = -0.255 per leg (+/-5.54 V -> 5.65 Vpp differential)'))
        c.append(opamp('U6', o['dun'], (xd, y + 3.81), 'VB_IN', f'_IN{n}_SUM', f'_IN{n}_N',
                       Note='+5VA single supply: inverting ADC driver (AIN-) and unity inverter (AIN+) per '
                            'channel. Rail-to-rail out: AIN never leaves 0..5 V'))
        c.append(two(o['rf'], 'R', '5.1k', 'R0603', (xd, y + 11.43), f'_IN{n}_SUM', f'_IN{n}_N', Note='Driver Rf'))
        c.append(two(o['cf'], 'C', '100p', 'C0603', (xd, y + 19.05), f'_IN{n}_SUM', f'_IN{n}_N', rot=90,
                     Voltage='50V', Dielectric='C0G', Note='Driver low-pass 312 kHz (anti-alias, stability)'))
        c.append(two(o['ri'], 'R', '2k', 'R0603', (x0 + 101.6, y + 22.86), f'_IN{n}_N', f'_IN{n}_INV',
                     Note='Unity inverter about VCOM_BUF: AIN+ = 2 x VCOM_BUF - AIN-'))
        c.append(opamp('U6', o['iun'], (xi, y + 20.32), 'VCOM_BUF', f'_IN{n}_INV', f'_IN{n}_PP',
                       Note='Unity inverter: the second leg of the differential ADC drive'))
        c.append(two(o['rif'], 'R', '2k', 'R0603', (xi, y + 27.94), f'_IN{n}_INV', f'_IN{n}_PP',
                     Note='Unity inverter Rf'))
        c.append(two(o['rn'], 'R', '100', 'R0603', (x0 + 99.06, y + 3.81), f'_IN{n}_N', o['adc'] + 'N',
                     Note='ADC input network (datasheet figure 12: 91R per leg)'))
        c.append(two(o['rp'], 'R', '100', 'R0603', (xi + 17.78, y + 20.32), f'_IN{n}_PP', o['adc'] + 'P',
                     Note='ADC input network (datasheet figure 12: 91R per leg)'))
        c.append(two(o['c'], 'C', '2.2n', 'C0603', (xi + 24.13, y + 12.7), o['adc'] + 'N', o['adc'] + 'P', rot=0,
                     Voltage='50V', Dielectric='C0G',
                     Note='Across AIN+/AIN- (datasheet 2.7 nF C0G): charge reservoir / anti-alias 362 kHz'))

    # ---- Outputs
    for o, y in zip(OUT_PARTS, OUT_Y):
        x0 = OUT_X0
        n = o['ch']
        xo = x0 + 22.86
        c.append(two(o['rp'], 'R', '6.8k', 'R0603', (x0, y), o['dac'] + 'P', f'_OUT{n}_REF',
                     Note='Difference amplifier, + leg (AOUT+): gain 15k/6.8k = 2.2'))
        c.append(two(o['rg'], 'R', '15k', 'R0603', (x0 + 7.62, y - 6.35), 'GND', f'_OUT{n}_REF', rot=0,
                     Note='Difference amplifier, + leg to GND: VCOM cancels, 0 V out at mid-scale'))
        c.append(two(o['cg'], 'C', '100p', 'C0603', (x0 + 12.7, y - 6.35), 'GND', f'_OUT{n}_REF', rot=0,
                     Voltage='50V', Dielectric='C0G', Note='Matches the feedback capacitor (106 kHz)'))
        c.append(two(o['rn'], 'R', '6.8k', 'R0603', (x0 - 10.16, y + 5.08), o['dac'] + 'N', f'_OUT{n}_FB',
                     Note='Difference amplifier, - leg (AOUT-). AOUT load 6.8k (CS4272 minimum 3k)'))
        c.append(opamp(o['u'], o['un'], (xo, y + 2.54), f'_OUT{n}_REF', f'_OUT{n}_FB', f'_OUT{n}_AMP',
                       quad=False, Note='+/-12 V difference amplifiers: differential DAC -> +/-5.29 V around 0 V'))
        c.append(two(o['rf'], 'R', '15k', 'R0603', (xo, y + 12.7), f'_OUT{n}_FB', f'_OUT{n}_AMP',
                     Note='Rf: 4.8 Vpp differential DAC full scale x 2.2 = +/-5.29 V'))
        c.append(two(o['cf'], 'C', '100p', 'C0603', (xo, y + 20.32), f'_OUT{n}_FB', f'_OUT{n}_AMP', rot=90,
                     Voltage='50V', Dielectric='C0G', Note='DAC output low-pass: 106 kHz with 15k'))
        # Preserve 1k output impedance using two Basic 2k/0.25 W parts per channel.
        # Each sees the full fault voltage: 18.1 V / 1.98k -> 0.166 W maximum per part
        # (output <=5.5 V, external patch <=12.6 V, 1% tolerance). No unlimited-rail guarantee.
        for ref, yy in ((o['ro'], y + 8.89), (o['rpar'], y + 1.27)):
            c.append(two(ref, 'R', '2k', 'R1206', (x0 + 78.74, yy), f'_OUT{n}_AMP', f'OUT{n}',
                         Power='0.25W', Tolerance='1%',
                         Note=f'Parallel with {o["rpar"] if ref == o["ro"] else o["ro"]}: 1k / 0.5W effective. '
                              'Opposing 5.5V output / 12.6V patch: <=0.166W each incl 1% R. '
                              'Resistor sizing to 85C; U5 and simultaneous-fault thermal qualification still required.'))
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0 + 96.52, y + 8.89), 180,
                      {'T': f'OUT{n}', 'S': 'GND', 'TN': None}, Note=f'OUT {n}: +/-5 V, DC-coupled'))

    # ---- Reference on +5VA: resistor divider (S5: no buffer op-amp)
    c.append(two('R49', 'R', '2.7k', 'R0603', (40.64, REF_Y), '+5VA', 'VCOM_BUF',
                 Note='Reference divider top: 2.7k over R40 + R41 (2.51k) = 0.482 x VA = 2.41 V, as the codec VCOM '
                      '(about 0.48 x VA). It only sets the common mode of the differential ADC drive'))
    c.append(two('C38', 'C', '10u', 'C0805', (46.99, REF_Y + 3.81), 'VCOM_BUF', 'GND', rot=0, Voltage='25V',
                 Note='Reference filter: 12 Hz with 2.7k || 2.51k'))
    c.append(two('C39', 'C', '100n', 'C0603', (55.88, REF_Y + 3.81), 'VCOM_BUF', 'GND', rot=0, Voltage='50V',
                 Note='Reference filter HF'))
    c.append(two('R40', 'R', '510', 'R0603', (68.58, REF_Y), 'VCOM_BUF', 'VB_IN',
                 Note='VB_IN = VCOM_BUF x 2/2.51: 0 V in -> VCOM_BUF at the driver output. No capacitor here: '
                      'reference noise then stays common to AIN+ and AIN-'))
    c.append(two('R41', 'R', '2k', 'R0603', (78.74, REF_Y + 3.81), 'VB_IN', 'GND', rot=0, Note='VB_IN divider'))

    # ---- Op-amp supplies and decoupling
    c.append(part('U4', DUAL, DUAL, 'SOIC8', (116.84, 340.36), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(part('U5', DUAL, DUAL, 'SOIC8', (162.56, 340.36), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(part('U6', 'OPA1679', 'OPA1679', 'SOIC14', (208.28, 340.36), 0, {'4': '+5VA', '11': 'GND'}, unit=5))
    for ref, xx, a, b, note in (('C26', 129.54, '+12V_F', 'GND', 'U4 V+'), ('C27', 142.24, 'GND', '-12V_F', 'U4 V-'),
                                ('C28', 175.26, '+12V_F', 'GND', 'U5 V+'), ('C29', 187.96, 'GND', '-12V_F', 'U5 V-'),
                                ('C30', 220.98, '+5VA', 'GND', 'U6 V+')):
        c.append(two(ref, 'C', '100n', 'C0603', (xx, 340.36), a, b, rot=0, Voltage='50V', Note=f'{note} decoupling'))

    # ---- Controls (firmware-defined): two pots on the ESP32 ADC, MODE button, MODE LED
    kx, ky = CTL
    c.append(two('R52', 'R', '2.2k', 'R0603', (kx, ky - 7.62), '+3V3', 'POT_TOP',
                 Note='Pot top: 3.3 V x 25k / 27.2k = 3.03 V full scale (ESP32-S3 ADC 12 dB range ~3.1 V); with C42 '
                      'a 72 Hz filter against the MCU supply noise'))
    c.append(two('C42', 'C', '1u', 'C0603', (kx + 7.62, ky - 3.81), 'POT_TOP', 'GND', rot=0, Voltage='50V',
                 Note='Pot top filter'))
    for ref, xx, net in (('RV1', kx + 20.32, 'POT1'), ('RV2', kx + 43.18, 'POT2')):
        c.append(part(ref, 'R_Potentiometer', '50k', 'RV09', (xx, ky), 0,
                      {'3': 'POT_TOP', '2': net, '1': 'GND'},
                      Note=f'{net}: firmware control, read by the ESP32-S3 ADC1 (RV09 9 mm, linear, user stock). '
                           'Not in the audio path. Hand-soldered'))
    c.append(part('SW3', 'SW_Push', 'MODE', 'SW6', (kx + 66.04, ky), 90, {'1': 'MODE', '2': 'GND'},
                  Note='MODE button (firmware-defined, ESP32 internal pull-up): generic 6 x 6 mm THT tact switch, '
                       '7 mm tall (as modules/16bit SW1); the modules/8bit printed cap fits. Hand-soldered'))
    c.append(two('R53', 'R', '1k', 'R0603', (kx + 78.74, ky - 2.54), 'LED', '_LED_A',
                 Note='MODE LED current: (3.3 V - 1.8 V) / 1k = 1.5 mA'))
    c.append(two('D3', 'LED', 'LED_3mm_red', 'LED3', (kx + 91.44, ky - 2.54), 'GND', '_LED_A', rot=180,
                 Note='MODE LED: 3 mm red THT (as modules/16bit D1), firmware-defined (LEDC PWM). Hand-soldered'))

    # ---- MCU board headers, RESET/BOOT
    hx, hy = HDR
    c.append(part('J6', 'Conn_01x10', 'MCU_L', 'H1x10', HDR, 0,
                  {'1': '+3V3', '2': 'GND', '3': 'EN', '4': 'BOOT', '5': 'MODE', '6': 'LED',
                   '7': 'I2C_SDA', '8': 'I2C_SCL', '9': 'POT1', '10': 'POT2'},
                  MPN='2.54 mm 1x10 male pin header (2.5 mm plastic)',
                  Note='MCU board left strip: soldered here (plastic on the F side) and through J102 on the 32bit-mcu '
                       'board. Pinout differs from the usb-audio CH32V307 board: the two MCU boards do not swap. '
                       'Hand-soldered'))
    c.append(part('J7', 'Conn_01x10', 'MCU_R', 'H1x10', (hx + 30.48, hy), 0,
                  {'1': '+3V3', '2': 'GND', '3': 'I2S_SCLK', '4': 'GND', '5': 'I2S_LRCK', '6': 'I2S_ADC',
                   '7': 'I2S_DAC', '8': 'CODEC_RST', '9': 'GND', '10': 'GND'},
                  MPN='2.54 mm 1x10 male pin header (2.5 mm plastic)',
                  Note='MCU board right strip (I2S: GND between the clocks). Hand-soldered'))
    c.append(part('SW1', 'SW_Push', 'RESET', 'SWK2', (482.6, 116.84), 0, {'1': 'EN', '2': 'GND'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='ESP32-S3 reset: pulls EN low (B side, reachable with the module out of the rack)'))
    c.append(part('SW2', 'SW_Push', 'BOOT', 'SWK2', (482.6, 129.54), 0, {'1': 'BOOT', '2': 'GND'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='Hold BOOT (GPIO0 low), press RESET: ESP32-S3 ROM download mode on the USB-C (recovery)'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # Power entry (as modules/32bit)
    W += [['J1.1', (33.02, 60.96), (33.02, 55.88), (50.8, 55.88), (50.8, 60.96), 'J1.2'], [(50.8, 55.88), 'D1.1'],
          ['J1.3', (33.02, 63.5), (33.02, 68.58), 'J1.7'], ['J1.5', (33.02, 66.04)], [(33.02, 68.58), (27.94, 68.58)],
          ['J1.4', (50.8, 63.5), (50.8, 68.58), 'J1.8'], ['J1.6', (50.8, 66.04)], [(50.8, 68.58), (53.34, 68.58)],
          ['J1.9', (33.02, 71.12), (33.02, 76.2), (50.8, 76.2), (50.8, 71.12), 'J1.10'], [(50.8, 76.2), 'D2.2'],
          ['D1.2', (86.36, 55.88)], ['D2.1', 'U1.3'], ['U1.2', (154.94, 76.2)],
          ['R1.2', 'U2.3'], ['U2.2', (154.94, 101.6)], ['FB1.2', (190.5, 101.6)]]
    P += [('-12V', (55.88, 55.88), 0), ('GND', (27.94, 68.58), 0), ('GND', (53.34, 68.58), 90),
          ('+12V', (55.88, 76.2), 0), ('-12V_F', (86.36, 55.88), 0), ('+12V_F', (88.9, 76.2), 0),
          ('+5VA', (154.94, 76.2), 0), ('+3V3', (154.94, 101.6), 0), ('+3V3_C', (190.5, 101.6), 0)]
    # Codec
    x, y = COD
    W += [['Y1.3', 'R10.1'], ['R10.2', 'U3.3'], ['R13.2', 'U3.6'], [(248.92, 165.1), 'R15.1'],
          ['U3.22', 'C16.1', 'C15.1'],
          ['U3.20', (x + 2.54, y - 27.94), (x + 7.62, y - 27.94)],
          ['U3.10', (x - 2.54, y - 27.94)], ['U3.9', (x, y - 27.94), (x - 7.62, y - 27.94)]]
    P += [('+5VA', (x + 7.62, y - 27.94), 0), ('+3V3_C', (x - 7.62, y - 27.94), 0)]
    W += [[(246.38, 157.48), 'TP1.1']]
    L += [('CODEC_SDOUT', (254.0, 165.1), 'U')]
    W += [['C17.1', 'C18.1'], ['C17.1', ('C17.1', 0, -2.54)]]
    L += [('VCOM', ('C17.1', 0, -2.54), 'U')]
    # Inputs
    for o, y in zip(IN_PARTS, IN_Y):
        x0 = IN_X0
        n = o['ch']
        fp, fm, fo = OPA2[o['fun']]
        dp, dm, do = OPA4[o['dun']]
        ip, im, io = OPA4[o['iun']]
        fu = o['fu']
        xo, xd, xi = x0 + 45.72, x0 + 81.28, x0 + 116.84
        W += [[f"{o['j']}.T", (x0 + 20.32, y), (x0 + 20.32, y + 3.81), f"{o['rs']}.1"], [f"{o['rs']}.2", f'{fu}.{fp}'],
              [f'{fu}.{fo}', f"{o['rin']}.1"],
              [(xo + 10.16, y + 6.35), (xo + 10.16, y + 11.43), (xo - 10.16, y + 11.43), (xo - 10.16, y + 8.89),
               f'{fu}.{fm}'],
              [f"{o['rin']}.2", f'U6.{dm}'],
              [(xd - 10.16, y + 6.35), (xd - 10.16, y + 11.43), f"{o['rf']}.1"],
              [(xd - 10.16, y + 11.43), (xd - 10.16, y + 19.05), f"{o['cf']}.1"],
              [f"{o['rf']}.2", (xd + 10.16, y + 11.43), (xd + 10.16, y + 3.81)],
              [f"{o['cf']}.2", (xd + 10.16, y + 19.05)],
              [(xd + 10.16, y + 11.43), (xd + 10.16, y + 22.86), f"{o['ri']}.1"],
              [f'U6.{do}', f"{o['rn']}.1"], [f"{o['rn']}.2", (xi + 27.94, y + 3.81)],
              [f"{o['ri']}.2", f'U6.{im}'],
              [(xi - 10.16, y + 22.86), (xi - 10.16, y + 27.94), f"{o['rif']}.1"],
              [f"{o['rif']}.2", (xi + 10.16, y + 27.94), (xi + 10.16, y + 20.32)],
              [f'U6.{io}', f"{o['rp']}.1"], [f"{o['rp']}.2", (xi + 27.94, y + 20.32)],
              [(xi + 24.13, y + 3.81), f"{o['c']}.1"], [f"{o['c']}.2", (xi + 24.13, y + 20.32)],
              [f"{o['j']}.TN", (x0 + 7.62, y - 2.54), (x0 + 7.62, y - 5.08)],
              [f"{o['j']}.S", (x0 + 7.62, y + 2.54), (x0 + 7.62, y + 5.08)]]
        P += [('GND', (x0 + 7.62, y - 5.08), 180), ('GND', (x0 + 7.62, y + 5.08), 0)]
        L += [(f'IN{n}', (x0 + 10.16, y), 'R'), (o['adc'] + 'N', (xi + 27.94, y + 3.81), 'R'),
              (o['adc'] + 'P', (xi + 27.94, y + 20.32), 'R')]
    # Outputs
    for o, y in zip(OUT_PARTS, OUT_Y):
        x0 = OUT_X0
        n = o['ch']
        up, um, uo = OPA2[o['un']]
        u = o['u']
        xo = x0 + 22.86
        W += [[f"{o['rp']}.2", f'{u}.{up}'], [(x0 + 7.62, y), f"{o['rg']}.2"], [(x0 + 12.7, y), f"{o['cg']}.2"],
              [f"{o['rn']}.2", f'{u}.{um}'],
              [(xo - 10.16, y + 5.08), (xo - 10.16, y + 12.7), f"{o['rf']}.1"],
              [(xo - 10.16, y + 12.7), (xo - 10.16, y + 20.32), f"{o['cf']}.1"],
              [f"{o['rf']}.2", (xo + 10.16, y + 12.7), (xo + 10.16, y + 2.54)],
              [f"{o['cf']}.2", (xo + 10.16, y + 20.32), (xo + 10.16, y + 12.7)],
              [f'{u}.{uo}', (x0 + 66.04, y + 2.54), (x0 + 66.04, y + 8.89), f"{o['ro']}.1"],
              [f"{o['ro']}.2", f"{o['j']}.T"],
              [(x0 + 73.66, y + 8.89), (x0 + 73.66, y + 1.27), f"{o['rpar']}.1"],
              [f"{o['rpar']}.2", (x0 + 85.09, y + 1.27), (x0 + 85.09, y + 8.89)],
              [f"{o['j']}.S", (x0 + 88.9, y + 11.43), (x0 + 88.9, y + 13.97)]]
        P += [('GND', (x0 + 88.9, y + 13.97), 0)]
        L += [(f'OUT{n}', (x0 + 85.09, y + 8.89), 'R')]
    # Controls: LED chain
    W += [['R53.2', 'D3.2']]
    # Reference
    y0 = REF_Y
    W += [['R49.2', 'R40.1'], ['R40.2', (91.44, y0)]]
    L += [('VB_IN', (91.44, y0), 'R'), ('VCOM_BUF', (62.23, y0), 'U')]
    return W, P, L


# JLCPCB parts. Basic R/C (incl. the 100p C0G), B5819W, AMS1117, NE5532; OPA1679, CS4272, YXC oscillator,
# the 2.2n C0G and the 2512 R are Extended. Free stock / pre-order checked live at each export (jlcpcb/README.md).
# Jacks, pots, the MODE switch and LED, the power header and the J6/J7 strips are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '33', 'R0603'): dict(LCSC='C23140', MPN='0603WAF330JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2.2k', 'R0603'): dict(LCSC='C4190', MPN='0603WAF2201T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0603'): dict(LCSC='C4184', MPN='0603WAF2002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0603'): dict(LCSC='C23186', MPN='0603WAF5101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '220', 'R0603'): dict(LCSC='C22962', MPN='0603WAF2200T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '510', 'R0603'): dict(LCSC='C23193', MPN='0603WAF5100T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2k', 'R0603'): dict(LCSC='C22975', MPN='0603WAF2001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2.7k', 'R0603'): dict(LCSC='C13167', MPN='0603WAF2701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '6.8k', 'R0603'): dict(LCSC='C23212', MPN='0603WAF6801T5E', Manufacturer='UNI-ROYAL'),
    ('R', '15k', 'R0603'): dict(LCSC='C22809', MPN='0603WAF1502T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2k', 'R1206'): dict(LCSC='C17944', MPN='1206W4F2001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22', 'R2512'): dict(LCSC='C118189', MPN='25121WF220JT4E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0603'): dict(LCSC='C15849', MPN='CL10A105KB8NNNC', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '22u', 'C0805'): dict(LCSC='C45783', MPN='CL21A226MAQNNNE', Manufacturer='Samsung'),
    ('C', '47u', 'C0805'): dict(LCSC='C16780', MPN='CL21A476MQYNNNE', Manufacturer='Samsung'),
    ('C', '2.2n', 'C0603'): dict(LCSC='C107043', MPN='CC0603JRNPO9BN222', Manufacturer='YAGEO'),
    ('C', '100p', 'C0603'): dict(LCSC='C14858', MPN='CL10C101JB8NNNC', Manufacturer='Samsung'),
    ('FerriteBead', 'GZ2012D121TF', 'C0805'): dict(LCSC='C5671', MPN='GZ2012D121TF', Manufacturer='Sunlord'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('AMS1117-5.0', 'AMS1117-5.0', 'SOT223'): dict(LCSC='C6187', MPN='AMS1117-5.0', Manufacturer='AMS'),
    ('AMS1117-3.3', 'AMS1117-3.3', 'SOT223'): dict(LCSC='C6186', MPN='AMS1117-3.3', Manufacturer='AMS'),
    ('CS4272', 'CS4272', 'TSSOP28'): dict(LCSC='C2151111', MPN='CS4272-CZZR', Manufacturer='Cirrus Logic'),
    ('OPA1679', 'OPA1679', 'SOIC14'): dict(LCSC='C2878631', MPN='OPA1679IDR', Manufacturer='Texas Instruments'),
    (DUAL, DUAL, 'SOIC8'): dict(LCSC='C7426', MPN='NE5532DR', Manufacturer='Texas Instruments'),
    ('ASE-xxxMHz', '24.576MHz', 'OSC3225'): dict(LCSC='C5203547', MPN='OT2EL4C4JI-111OLP-24.576M',
                                                 Manufacturer='YXC'),
    ('SW_Push', 'RESET', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('SW_Push', 'BOOT', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR 32BIT - carrier (jack board), S4: modules/usb-audio S5 audio path + ESP32-S3 MCU board. '
                     '2 in / 2 out, DC-coupled +/-5 V, CS4272. Circuit intent: docs/research.md; placement: docs/geometry.json',
     2.0),
    ((20.32, 33.02), 'POWER: +12V -> D2 -> +12V_F (op-amps; U1 AMS1117-5.0 -> +5VA; R1 22R -> U2 AMS1117-3.3 -> +3V3 '
                     '-> FB1 -> +3V3_C); -12V -> D1 -> -12V_F', 1.4),
    ((20.32, 121.92), 'PWR_FLAG: GND/+12V/-12V at J1; +12V_F/-12V_F behind D2/D1; V3_IN behind R1; +3V3_C behind FB1.',
     1.1),
    ((203.2, 106.68), 'CS4272 CODEC: I2C control port, address 0x10, 100 kHz. Master, external MCLK 24.576 MHz (XTI = GND):\n'
                      '512 / 256 / 128 x Fs = 48 / 96 / 192 kHz (Ratio1:0 = 10); SCLK = 64 x Fs to the ESP32-S3 I2S slave.\n'
                      'Firmware: RST high, write 03h to 07h (CPEN + PDN) within 10 ms, set the registers, clear PDN.\n'
                      'SCLK / LRCK are codec inputs until the M/S bit is set: R14 / R16 hold them low (no floating clocks).\n'
                      'TP1: MCLK scope pad on the back; SCLK, LRCK, ADC, DAC, RST, GND: J7 solder joints (B silk).', 1.1),
    ((154.94, 172.72), 'I2S series termination (at the codec)\nand pull-downs', 1.1),
    ((20.32, 223.52), 'INPUTS: jack (TN = GND, R50/R51 100k to GND) -> 1k -> U4A/B NE5532 follower (+/-12 V)\n'
                      '-> U6 inverting driver on +5VA (-0.255, + at VB_IN) = AIN-; U6 unity inverter about VCOM_BUF = AIN+;\n'
                      '100R per leg, 2.2n C0G across the pair. +/-5.54 V = 5.65 Vpp differential ADC full scale.', 1.1),
    ((322.58, 223.52), 'OUTPUTS: AOUT+/- -> U5A/B difference amplifier (6.8k / 15k, 100p: x2.2, 106 kHz)\n'
                       '-> 2k || 2k (1k / 0.5W) -> jack. 4.8 Vpp differential DAC full scale -> +/-5.29 V.\n'
                       'The codec common mode (VCOM) cancels: 0 V out at mid-scale and while the codec is in reset.', 1.1),
    ((20.32, 309.88), 'REFERENCE (+5VA): R49 over R40 + R41 = 0.482 x VA = 2.41 V -> VCOM_BUF (unity inverters, C38 / C39) and\n'
                      'VB_IN = VCOM_BUF x 2/2.51 (input drivers, no capacitor). It only sets the ADC common mode;\n'
                      'the codec VCOM pin is not loaded. No buffer op-amp (S5).', 1.1),
    ((449.58, 50.8), 'MCU BOARD LINK: J6/J7 1x10 2.54 mm male headers (plastic on the carrier F side);\n'
                     'the ESP32-S3 MCU board (32bit-mcu) solders on top. RESET (EN) / BOOT (GPIO0) on the carrier B side:\n'
                     'hold BOOT, press RESET = ESP32-S3 ROM download mode on the USB-C (recovery only).', 1.1),
    ((360.68, 320.04), 'CONTROLS (firmware-defined): RV1 / RV2 50k on the ESP32-S3 ADC1 (0..3.03 V), SW3 MODE to GND,\n'
                       'MODE LED D3 through R53 1k. Not in the audio path.', 1.1),
]

TEXT_LEFT = {'R15', 'R17', 'R41', 'R42', 'R43'}
TEXT_POS = {'U1': ((0, -6.35), (0, -3.81)), 'U2': ((0, -6.35), (0, -3.81)),
            'U4/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U5/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U6/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U3': ((0, -26.67), (10.16, 26.67)), 'Y1': ((0, -10.16), (0, 10.16)),
            'SW1': ((0, -3.81), (0, 3.81)), 'SW2': ((0, -3.81), (0, 3.81)),
            'J6': ((0, -13.97), (0, 16.51)), 'J7': ((0, -13.97), (0, 16.51)), 'SW3': ((0, -3.81), (0, 3.81))}

MULTI_UNIT = {'U4': {1, 2, 3}, 'U5': {1, 2, 3}, 'U6': {1, 2, 3, 4, 5}}
