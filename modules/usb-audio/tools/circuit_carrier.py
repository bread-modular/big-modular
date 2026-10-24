"""USB-AUDIO carrier (jack/pot board) S1 circuit table, drawing and sourcing (tools/build_schematic.py).

CIRCUIT is docs/research.md section 3. 6HP, 2 in / 2 out, DC-coupled, +/-5 V (CV too), 192 kHz:

- Power: Eurorack 10-pin +/-12 V -> B5819W series Schottkys -> +12V_F / -12V_F (op-amps);
  +12V_F -> U1 AMS1117-5.0 -> +5VA (CS4270 VA, U6); +12V_F -> R1 33R 1 W -> U2 AMS1117-3.3 -> +3V3
  (MCU board, oscillator, I2C pull-ups); +3V3 -> FB1 -> +3V3_C (CS4270 VD/VLC).
- Codec: U3 CS4270 in I2C control-port mode, address 0x48 (AD2..AD0 = 0), master in quad speed
  (MCLK/LRCK 128: Y1 24.576 MHz -> 192 kHz; 96/48 kHz via the MCLK divider). It drives SCLK/LRCK
  to both CH32V307 I2S ports (slaves). RST held low by R17 until the MCU releases it.
- Inputs: jack (TN to GND: unpatched = 0 V) -> RV1/RV2 50k volume (0..1) -> R20/R21 1k -> U4A/U4B
  follower (+/-12 V, by the IN pots) -> U6A/U6B inverting driver on +5VA (gain -5.1k/20k, + input at VB_IN =
  VQ x 20/25.1 so 0 V in = VQ) -> 220R / 2.2n C0G -> AINA/AINB. +/-5.49 V = ADC full scale
  (0.56 x VA = 2.8 Vpp); the 5 V driver cannot push AIN outside 0..5 V on a +/-12 V mis-patch.
  The CS4270 ADC_INV bits restore the polarity; its HPF is frozen for DC (register 04h bits 7/6).
- Outputs: AOUTA/AOUTB -> 470R / 1n C0G -> U5A/U5B non-inverting gain 3.2 (22k/10k) with Rg to
  VREF_OUT = VQ x 32/22, so VQ out = 0 V; DAC full scale 0.65 x VA = 3.25 Vpp -> +/-5.2 V. AOUT
  sees only an op-amp input (CS4270 AOUT DC load max 10 uA). -> RV3/RV4 50k volume -> U7A/U7B
  follower (by the OUT pots) -> 1k 1206 -> jack. U4 and U7 are separate duals (R2, 2026-10-24) so
  each follower sits at its pot wiper; the gain stages U5 sit at the codec AOUT pins.
- References on +5VA: U6C buffers VQ (25k source, max 1 uA) for the VB_IN divider; U6D makes
  VREF_OUT from VQ. Both track the codec's own mid-rail.
- MCU board link: J6/J7 1x10 2.54 mm pin headers (the MCU board solders on top of them, F side).
  BOOT/RESET (SW2/SW1) and the SWD header J8 sit on the carrier so the MCU board needs none.
"""

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+3V3_C': '+3V3', '+5VA': '+5VA', '+12V': '+12V',
               '-12V': '-12V', '+12V_F': '+12V', '-12V_F': '-12V'}

# Symbols drawn mirrored about X (pots: pin 3 up, wiper right, pin 1 down; input jacks: sleeve down).
MIRROR_X = {'RV1', 'RV2', 'RV3', 'RV4', 'J2', 'J3'}

# Header strips J6/J7 are bought and soldered by hand with the MCU board (no LCSC field); listed in
# the carrier BOM. The MCU board's J102/J103 are the same strips seen from the other board.
NOT_ASSEMBLED = set()

PWR = (40.64, 66.04)          # J1 (as modules/32bit J6)
COD = (279.4, 165.1)          # U3 CS4270
IN_Y = (241.3, 274.32)        # input channel rows
OUT_Y = (241.3, 274.32)       # output channel rows
IN_X0 = 22.86                 # input jack column
OUT_X0 = 335.28               # output R30 column
REF_Y = (330.2, 360.68)       # VQ buffer / VREF_OUT amp rows
HDR = (482.6, 76.2)           # J6; J7 at +30.48

IN_PARTS = [dict(j='J2', rv='RV1', rs='R20', fu='U4', fun=1, rin='R22', rf='R24', du='U6', dun=1,
                 ro='R26', c='C20', ch='1', adc='ADC_A'),
            dict(j='J3', rv='RV2', rs='R21', fu='U4', fun=2, rin='R23', rf='R25', du='U6', dun=2,
                 ro='R27', c='C21', ch='2', adc='ADC_B')]
OUT_PARTS = [dict(rs='R30', c='C22', u='U5', un=1, rg='R32', rf='R34', rv='RV3', fu='U7', fun=1, ro='R36',
                  j='J4', ch='1', dac='DAC_A'),
             dict(rs='R31', c='C23', u='U5', un=2, rg='R33', rf='R35', rv='RV4', fu='U7', fun=2, ro='R37',
                  j='J5', ch='2', dac='DAC_B')]
# Op-amp unit pins: unit -> (+, -, out)
OPA4 = {1: ('3', '2', '1'), 2: ('5', '6', '7'), 3: ('10', '9', '8'), 4: ('12', '13', '14')}
OPA2 = {1: ('3', '2', '1'), 2: ('5', '6', '7')}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/FB: rot 90 = horizontal, pin 1 left; rot 0 = vertical,
    pin 1 on top. Diodes: rot 0 = K left."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def opamp(ref, unit, at, plus, minus, out, quad=True, **fields):
    p, m, o = (OPA4 if quad else OPA2)[unit]
    return part(ref, 'OPA1679' if quad else 'OPA1678', 'OPA1679' if quad else 'OPA1678',
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
                  Note='+5VA: CS4270 VA (37 mA) + U6 (~10 mA). ~50 mA x 7 V = 0.35 W'))
    c.append(two('C3', 'C', '22u', 'C0805', (139.7, 80.01), '+5VA', 'GND', rot=0, Voltage='25V', Note='U1 output'))
    c.append(two('C4', 'C', '100n', 'C0603', (147.32, 80.01), '+5VA', 'GND', rot=0, Voltage='50V',
                 Note='U1 output HF'))
    c.append(two('R1', 'R', '33', 'R2512', (101.6, 101.6), '+12V_F', '_V3_IN', Power='1W',
                 Note='Pre-drop for U2: 100 mA -> 3.3 V / 0.33 W here, U2 sees ~8.7 V (0.54 W); '
                      '150 mA -> U2 input 7.0 V, still above its 4.6 V minimum'))
    c.append(two('C5', 'C', '10u', 'C0805', (111.76, 105.41), '_V3_IN', 'GND', rot=0, Voltage='25V',
                 Note='U2 input'))
    c.append(part('U2', 'AMS1117-3.3', 'AMS1117-3.3', 'SOT223', (124.46, 101.6), 0,
                  {'1': 'GND', '2': '+3V3', '3': '_V3_IN'},
                  Note='+3V3: MCU board (CH32V307 + USB HS PHY, ~60-100 mA), oscillator, CS4270 VD/VLC'))
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

    # ---- CS4270 codec (I2C control port), oscillator, clock/data series resistors
    x, y = COD
    c.append(part('U3', 'CS4270', 'CS4270', 'TSSOP24', COD, 0,
                  {'1': 'I2S_DAC', '2': '_LRCK_C', '3': '_MCLK_C', '4': '_SCLK_C', '5': '+3V3_C', '6': 'GND',
                   '7': '_SDOUT_C', '8': '+3V3_C', '9': 'I2C_SDA', '10': 'I2C_SCL', '11': 'CODEC_AD0', '12': 'GND',
                   '13': 'GND', '14': 'CODEC_RST', '15': 'ADC_A', '16': 'ADC_B', '17': 'VQ', '18': '_FILTP',
                   '19': '+5VA', '20': 'GND', '21': None, '22': 'DAC_A', '23': 'DAC_B', '24': None},
                  Note='24-bit 192 kHz stereo codec. I2C 0x48. Master, quad speed, MCLK/LRCK 128. '
                       'Cirrus lists it as discontinued; JLC/LCSC stock checked 2026-10-23'))
    c.append(part('Y1', 'ASE-xxxMHz', '24.576MHz', 'OSC3225', (210.82, 152.4), 0,
                  {'1': '+3V3_C', '2': 'GND', '3': '_OSC', '4': '+3V3_C'},
                  Note='24.576 MHz 3.3 V CMOS oscillator (YXC OT2EL, 3225): MCLK = 128 x 192 kHz'))
    for ref, row, a, b, note in (('R12', 149.86, 'I2S_LRCK', '_LRCK_C', 'LRCK out (codec master)'),
                                 ('R10', 152.4, '_OSC', '_MCLK_C', 'MCLK from Y1'),
                                 ('R11', 154.94, 'I2S_SCLK', '_SCLK_C', 'SCLK out (codec master)')):
        c.append(two(ref, 'R', '33', 'R0603', (226.06 if ref == 'R10' else 256.54, row), a, b,
                     Note=f'Series termination: {note}'))
    c.append(two('R13', 'R', '33', 'R0603', (304.8, 147.32), '_SDOUT_C', 'I2S_ADC',
                 Note='Series termination: SDOUT (ADC data) to the MCU'))
    c.append(two('R15', 'R', '47k', 'R0603', (297.18, 143.51), '_SDOUT_C', 'GND', rot=180,
                 Note='SDOUT (M/S) 47k pull-down: if the MCU never configures the codec, stand-alone mode '
                      'starts as slave (does not drive SCLK/LRCK)'))
    c.append(two('R16', 'R', '47k', 'R0603', (254.0, 172.72), 'GND', 'CODEC_AD0',
                 Note='AD0 strap through a resistor (datasheet 6.1): I2C address 1001000 = 0x48'))
    c.append(two('R17', 'R', '10k', 'R0603', (248.92, 184.15), 'CODEC_RST', 'GND', rot=0,
                 Note='Holds the codec in reset until the MCU (PB14) releases it with clocks running'))
    c.append(two('C15', 'C', '47u', 'C0805', (302.26, 181.61), '_FILTP', 'GND', rot=0, Voltage='6.3V',
                 Note='FILT+ reservoir (datasheet 47 uF)'))
    c.append(two('C16', 'C', '100n', 'C0603', (309.88, 181.61), '_FILTP', 'GND', rot=0, Voltage='50V',
                 Note='FILT+ HF, closest to pin 18'))
    # decoupling row (y 205.74)
    for ref, xx, val, fp, net, volt, note in (
            ('C10', 231.14, '1u', 'C0603', '+5VA', '50V', 'VA bulk'),
            ('C11', 241.3, '100n', 'C0603', '+5VA', '50V', 'VA HF, closest to pin 19'),
            ('C12', 256.54, '1u', 'C0603', '+3V3_C', '50V', 'VD bulk'),
            ('C13', 266.7, '100n', 'C0603', '+3V3_C', '50V', 'VD HF, closest to pin 5'),
            ('C14', 276.86, '100n', 'C0603', '+3V3_C', '50V', 'VLC'),
            ('C19', 287.02, '100n', 'C0603', '+3V3_C', '50V', 'Y1 supply')):
        c.append(two(ref, 'C', val, fp, (xx, 205.74), net, 'GND', rot=0, Voltage=volt, Note=note))
    c.append(two('C17', 'C', '10u', 'C0805', (304.8, 205.74), 'VQ', 'GND', rot=0, Voltage='25V',
                 Note='VQ filter (datasheet 10 uF)'))
    c.append(two('C18', 'C', '100n', 'C0603', (314.96, 205.74), 'VQ', 'GND', rot=0, Voltage='50V',
                 Note='VQ HF, closest to pin 17'))
    c.append(two('R18', 'R', '2.2k', 'R0603', (226.06, 177.8), '+3V3', 'I2C_SCL', rot=0,
                 Note='I2C pull-up (datasheet 2k), shared with the MCU board'))
    c.append(two('R19', 'R', '2.2k', 'R0603', (218.44, 177.8), '+3V3', 'I2C_SDA', rot=0, Note='I2C pull-up'))

    # ---- Inputs
    for o, y in zip(IN_PARTS, IN_Y):
        x0 = IN_X0
        n = o['ch']
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0, y), 0,
                      {'T': f'IN{n}', 'S': 'GND', 'TN': 'GND'},
                      Note=f'IN {n}: +/-5 V audio or CV, DC-coupled. TN to GND: unpatched = 0 V'))
        c.append(part(o['rv'], 'R_Potentiometer', '50k', 'RV09', (x0 + 17.78, y + 3.81), 0,
                      {'3': f'IN{n}', '2': f'_IN{n}_POT', '1': 'GND'},
                      Note=f'IN {n} volume 0..1 (RV09 9 mm, linear, user stock). Hand-soldered'))
        c.append(two(o['rs'], 'R', '1k', 'R0603', (x0 + 27.94, y + 3.81), f'_IN{n}_POT', f'_IN{n}_P',
                     Note='Follower input protection (no effect on the pot: FET-input op-amp)'))
        c.append(opamp(o['fu'], o['fun'], (x0 + 45.72, y + 6.35), f'_IN{n}_P', f'_IN{n}_BUF', f'_IN{n}_BUF',
                       quad=False, Note='+/-12 V input pot-wiper followers, placed by RV1/RV2'))
        c.append(two(o['rin'], 'R', '20k', 'R0603', (x0 + 63.5, y + 6.35), f'_IN{n}_BUF', f'_IN{n}_SUM',
                     Note='Driver Rin: gain -5.1k/20k = -0.255 (+/-5.49 V -> 2.8 Vpp ADC full scale)'))
        c.append(opamp(o['du'], o['dun'], (x0 + 81.28, y + 3.81), 'VB_IN', f'_IN{n}_SUM', f'_IN{n}_DRV',
                       Note='+5VA single supply: ADC drivers (A/B), VQ buffer (C), VREF_OUT (D). '
                            'Rail-to-rail out: AIN never leaves 0..5 V'))
        c.append(two(o['rf'], 'R', '5.1k', 'R0603', (x0 + 81.28, y + 11.43), f'_IN{n}_SUM', f'_IN{n}_DRV',
                     Note='Driver Rf'))
        c.append(two(o['ro'], 'R', '220', 'R0603', (x0 + 99.06, y + 3.81), f'_IN{n}_DRV', o['adc'],
                     Note='ADC input network: source impedance < 1k (datasheet 5.5.1)'))
        c.append(two(o['c'], 'C', '2.2n', 'C0603', (x0 + 106.68, y + 7.62), o['adc'], 'GND', rot=0, Voltage='50V',
                     Dielectric='C0G', Note='ADC charge reservoir / anti-alias (329 kHz), C0G for linearity'))

    # ---- Outputs
    for o, y in zip(OUT_PARTS, OUT_Y):
        x0 = OUT_X0
        n = o['ch']
        c.append(two(o['rs'], 'R', '470', 'R0603', (x0, y), o['dac'], f'_OUT{n}_FLT',
                     Note='DAC output filter R (datasheet 470R)'))
        c.append(two(o['c'], 'C', '1n', 'C0603', (x0 + 7.62, y + 3.81), f'_OUT{n}_FLT', 'GND', rot=0, Voltage='50V',
                     Dielectric='C0G', Note='DAC output filter C: 339 kHz with 470R (192 kHz first)'))
        c.append(opamp(o['u'], o['un'], (x0 + 22.86, y + 2.54), f'_OUT{n}_FLT', f'_OUT{n}_FB', f'_OUT{n}_AMP',
                       quad=False, Note='+/-12 V output gain stages. High-Z on AOUT (CS4270: 10 uA max DC load)'))
        c.append(two(o['rf'], 'R', '22k', 'R0603', (x0 + 22.86, y + 12.7), f'_OUT{n}_FB', f'_OUT{n}_AMP',
                     Note='Rf: gain 1 + 22k/10k = 3.2 (3.25 Vpp DAC full scale -> +/-5.2 V)'))
        c.append(two(o['rg'], 'R', '10k', 'R0603', (x0 + 7.62, y + 17.78), 'VREF_OUT', f'_OUT{n}_FB',
                     Note='Rg to VREF_OUT (= VQ x 32/22): VQ at AOUT -> 0 V out'))
        c.append(part(o['rv'], 'R_Potentiometer', '50k', 'RV09', (x0 + 43.18, y + 6.35), 0,
                      {'3': f'_OUT{n}_AMP', '2': f'_OUT{n}_POT', '1': 'GND'},
                      Note=f'OUT {n} volume 0..1 (RV09 9 mm, linear, user stock). Hand-soldered'))
        c.append(opamp(o['fu'], o['fun'], (x0 + 60.96, y + 8.89), f'_OUT{n}_POT', f'_OUT{n}_BUF', f'_OUT{n}_BUF',
                       quad=False, Note='+/-12 V output pot-wiper followers, placed by RV3/RV4'))
        c.append(two(o['ro'], 'R', '1k', 'R1206', (x0 + 78.74, y + 8.89), f'_OUT{n}_BUF', f'OUT{n}', Power='0.25W',
                     Note='Output series: short / mis-patch limit (1206: 0.14 W on a permanent +/-12 V mis-patch)'))
        c.append(part(o['j'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0 + 96.52, y + 8.89), 180,
                      {'T': f'OUT{n}', 'S': 'GND', 'TN': None}, Note=f'OUT {n}: +/-5 V, DC-coupled'))

    # ---- References on +5VA (U6C, U6D)
    c.append(opamp('U6', 3, (50.8, REF_Y[0]), 'VQ', '_VQ_BUF', '_VQ_BUF',
                   Note='VQ buffer (VQ: 25k source, 1 uA max)'))
    c.append(two('R40', 'R', '5.1k', 'R0603', (68.58, REF_Y[0]), '_VQ_BUF', 'VB_IN', Note='VB_IN = VQ x 20/25.1'))
    c.append(two('R41', 'R', '20k', 'R0603', (78.74, REF_Y[0] + 3.81), 'VB_IN', 'GND', rot=0, Note='VB_IN divider'))
    c.append(two('C24', 'C', '100n', 'C0603', (86.36, REF_Y[0] + 3.81), 'VB_IN', 'GND', rot=0, Voltage='50V',
                 Note='VB_IN filter'))
    c.append(opamp('U6', 4, (50.8, REF_Y[1]), 'VQ', '_VREF_FB', 'VREF_OUT', Note='VREF_OUT = VQ x (1 + 10k/22k)'))
    c.append(two('R43', 'R', '10k', 'R0603', (50.8, REF_Y[1] + 7.62), '_VREF_FB', 'VREF_OUT',
                 Note='Same ratio as the output stages (Rg/Rf): tracks them'))
    c.append(two('R42', 'R', '22k', 'R0603', (40.64, REF_Y[1] + 13.97), '_VREF_FB', 'GND', rot=0))

    # ---- Op-amp supplies and decoupling
    c.append(part('U4', 'OPA1678', 'OPA1678', 'SOIC8', (116.84, 340.36), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(part('U5', 'OPA1678', 'OPA1678', 'SOIC8', (162.56, 340.36), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(part('U6', 'OPA1679', 'OPA1679', 'SOIC14', (208.28, 340.36), 0, {'4': '+5VA', '11': 'GND'}, unit=5))
    c.append(part('U7', 'OPA1678', 'OPA1678', 'SOIC8', (254.0, 340.36), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    for ref, xx, a, b, note in (('C26', 129.54, '+12V_F', 'GND', 'U4 V+'), ('C27', 142.24, 'GND', '-12V_F', 'U4 V-'),
                                ('C28', 175.26, '+12V_F', 'GND', 'U5 V+'), ('C29', 187.96, 'GND', '-12V_F', 'U5 V-'),
                                ('C30', 220.98, '+5VA', 'GND', 'U6 V+'),
                                ('C31', 266.7, '+12V_F', 'GND', 'U7 V+'), ('C32', 279.4, 'GND', '-12V_F', 'U7 V-')):
        c.append(two(ref, 'C', '100n', 'C0603', (xx, 340.36), a, b, rot=0, Voltage='50V', Note=f'{note} decoupling'))

    # ---- MCU board headers, BOOT/RESET, SWD
    hx, hy = HDR
    c.append(part('J6', 'Conn_01x10', 'MCU_L', 'H1x10', HDR, 0,
                  {'1': '+3V3', '2': 'GND', '3': 'SWDIO', '4': 'SWCLK', '5': 'NRST', '6': 'BOOT0',
                   '7': 'I2C_SCL', '8': 'I2C_SDA', '9': 'GND', '10': 'GND'},
                  MPN='2.54 mm 1x10 male pin header (2.5 mm plastic)',
                  Note='MCU board left strip: soldered here (plastic on the F side) and through J102 on the MCU '
                       'board. Hand-soldered'))
    c.append(part('J7', 'Conn_01x10', 'MCU_R', 'H1x10', (hx + 30.48, hy), 0,
                  {'1': '+3V3', '2': 'GND', '3': 'I2S_SCLK', '4': 'GND', '5': 'I2S_LRCK', '6': 'I2S_ADC',
                   '7': 'I2S_DAC', '8': 'CODEC_RST', '9': 'GND', '10': 'GND'},
                  MPN='2.54 mm 1x10 male pin header (2.5 mm plastic)',
                  Note='MCU board right strip (I2S: GND between the clocks). Hand-soldered'))
    c.append(part('SW1', 'SW_Push', 'RESET', 'SWK2', (482.6, 116.84), 0, {'1': 'NRST', '2': 'GND'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='CH32V307 reset (B side, reachable with the module out of the rack)'))
    c.append(part('SW2', 'SW_Push', 'BOOT', 'SWK2', (482.6, 129.54), 0, {'1': 'BOOT0', '2': '+3V3'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='Hold BOOT, press RESET: ROM bootloader on the USB-C (PB6/PB7), flash with wchisp/WCHISPTool'))
    c.append(part('J8', 'Conn_01x04', 'SWD', 'H1x4', (528.32, 124.46), 0,
                  {'1': '+3V3', '2': 'SWDIO', '3': 'SWCLK', '4': 'GND'},
                  Note='WCH-LinkE debug (SWDIO/SWCLK). Optional, hand-soldered, B side'))
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
    W += [['U3.1', (261.62, 147.32), (261.62, 144.78), (248.92, 144.78)],
          ['Y1.3', 'R10.1'], ['R12.2', 'U3.2'], ['R10.2', 'U3.3'], ['R11.2', 'U3.4'],
          ['U3.7', 'R13.1'], ['R16.2', 'U3.11'],
          ['U3.12', (256.54, 175.26)], ['U3.13', (256.54, 177.8)], [(256.54, 175.26), (256.54, 177.8)],
          [(256.54, 176.53), (254.0, 176.53)],
          ['U3.14', (243.84, 180.34)],
          ['U3.18', 'C16.1'],
          ['U3.19', (x, y - 30.48)], ['U3.5', (x - 2.54, y - 27.94), (x - 7.62, y - 27.94)],
          ['U3.8', (x + 2.54, y - 27.94), (x + 7.62, y - 27.94)]]
    P += [('GND', (254.0, 176.53), 270), ('+5VA', (x, y - 30.48), 0), ('+3V3_C', (x - 7.62, y - 27.94), 0),
          ('+3V3_C', (x + 7.62, y - 27.94), 0)]
    L += [('CODEC_RST', (243.84, 180.34), 'L'), ('I2S_DAC', (248.92, 144.78), 'L'), ('CODEC_AD0', (259.08, 172.72), 'U')]
    W += [['C17.1', 'C18.1'], ['C17.1', ('C17.1', 0, -2.54)]]
    L += [('VQ', ('C17.1', 0, -2.54), 'U')]
    # Inputs
    for o, y in zip(IN_PARTS, IN_Y):
        x0 = IN_X0
        n = o['ch']
        fp, fm, fo = OPA2[o['fun']]
        dp, dm, do = OPA4[o['dun']]
        fu, du = o['fu'], o['du']
        xo, xd = x0 + 45.72, x0 + 81.28
        W += [[f"{o['j']}.T", f"{o['rv']}.3"], [f"{o['rv']}.2", f"{o['rs']}.1"], [f"{o['rs']}.2", f'{fu}.{fp}'],
              [f'{fu}.{fo}', f"{o['rin']}.1"],
              [(xo + 10.16, y + 6.35), (xo + 10.16, y + 11.43), (xo - 10.16, y + 11.43), (xo - 10.16, y + 8.89),
               f'{fu}.{fm}'],
              [f"{o['rin']}.2", f'{du}.{dm}'],
              [(xd - 10.16, y + 6.35), (xd - 10.16, y + 11.43), f"{o['rf']}.1"],
              [f"{o['rf']}.2", (xd + 10.16, y + 11.43), (xd + 10.16, y + 3.81)],
              [f'{du}.{do}', f"{o['ro']}.1"], [f"{o['ro']}.2", (x0 + 111.76, y + 3.81)],
              [f"{o['j']}.TN", (x0 + 7.62, y - 2.54), (x0 + 7.62, y - 5.08)],
              [f"{o['j']}.S", (x0 + 7.62, y + 2.54), (x0 + 7.62, y + 5.08)]]
        P += [('GND', (x0 + 7.62, y - 5.08), 180), ('GND', (x0 + 7.62, y + 5.08), 0)]
        L += [(f'IN{n}', (x0 + 10.16, y), 'R'), (o['adc'], (x0 + 111.76, y + 3.81), 'R')]
    # Outputs
    for o, y in zip(OUT_PARTS, OUT_Y):
        x0 = OUT_X0
        n = o['ch']
        up, um, uo = OPA2[o['un']]
        fp, fm, fo = OPA2[o['fun']]
        u, fu = o['u'], o['fu']
        xo, xf = x0 + 22.86, x0 + 60.96
        W += [[f"{o['rs']}.2", f'{u}.{up}'],
              [f'{u}.{um}', (xo - 10.16, y + 5.08), (xo - 10.16, y + 17.78), f"{o['rg']}.2"],
              [(xo - 10.16, y + 12.7), f"{o['rf']}.1"],
              [f"{o['rf']}.2", (xo + 10.16, y + 12.7), (xo + 10.16, y + 2.54)],
              [f'{u}.{uo}', f"{o['rv']}.3"], [f"{o['rv']}.2", f'{fu}.{fp}'],
              [f'{fu}.{fo}', f"{o['ro']}.1"],
              [(xf + 10.16, y + 8.89), (xf + 10.16, y + 13.97), (xf - 10.16, y + 13.97), (xf - 10.16, y + 11.43),
               f'{fu}.{fm}'],
              [f"{o['ro']}.2", f"{o['j']}.T"],
              [f"{o['j']}.S", (x0 + 88.9, y + 11.43), (x0 + 88.9, y + 13.97)]]
        P += [('GND', (x0 + 88.9, y + 13.97), 0)]
        L += [(f'OUT{n}', (x0 + 85.09, y + 8.89), 'R')]
    # References
    y0, y1 = REF_Y
    W += [['U6.8', 'R40.1'], [(58.42 + 2.54, y0), (60.96, y0 + 5.08), (40.64, y0 + 5.08), (40.64, y0 + 2.54), 'U6.9'],
          ['R40.2', (91.44, y0)],
          ['U6.14', (71.12, y1)], ['U6.13', (40.64, y1 + 2.54), (40.64, y1 + 7.62), 'R43.1'],
          [(40.64, y1 + 7.62), 'R42.1'], ['R43.2', (60.96, y1 + 7.62), (60.96, y1)]]
    L += [('VB_IN', (91.44, y0), 'R'), ('VREF_OUT', (71.12, y1), 'R')]
    return W, P, L


# JLCPCB parts. Basic R/C, B5819W, AMS1117 from the 2026-10-23 live lookups (and modules/32bit);
# OPA1679/OPA1678, CS4270, YXC oscillator, C0G caps, 2512 R are Extended (live-checked 2026-10-23).
# Jacks, pots, the power header and the J6/J7/J8 strips are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '33', 'R0603'): dict(LCSC='C23140', MPN='0603WAF330JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2.2k', 'R0603'): dict(LCSC='C4190', MPN='0603WAF2201T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0603'): dict(LCSC='C4184', MPN='0603WAF2002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '5.1k', 'R0603'): dict(LCSC='C23186', MPN='0603WAF5101T5E', Manufacturer='UNI-ROYAL'),
    ('R', '220', 'R0603'): dict(LCSC='C22962', MPN='0603WAF2200T5E', Manufacturer='UNI-ROYAL'),
    ('R', '470', 'R0603'): dict(LCSC='C23179', MPN='0603WAF4700T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R1206'): dict(LCSC='C4410', MPN='1206W4F1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R2512'): dict(LCSC='C53728', MPN='25121WF330JT4E', Manufacturer='UNI-ROYAL'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0603'): dict(LCSC='C15849', MPN='CL10A105KB8NNNC', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '22u', 'C0805'): dict(LCSC='C45783', MPN='CL21A226MAQNNNE', Manufacturer='Samsung'),
    ('C', '47u', 'C0805'): dict(LCSC='C16780', MPN='CL21A476MQYNNNE', Manufacturer='Samsung'),
    ('C', '2.2n', 'C0603'): dict(LCSC='C33353', MPN='CL10C222JB8NNNC', Manufacturer='Samsung'),
    ('C', '1n', 'C0603'): dict(LCSC='C163508', MPN='CL10C102JB8NNNC', Manufacturer='Samsung'),
    ('FerriteBead', 'GZ2012D121TF', 'C0805'): dict(LCSC='C5671', MPN='GZ2012D121TF', Manufacturer='Sunlord'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('AMS1117-5.0', 'AMS1117-5.0', 'SOT223'): dict(LCSC='C6187', MPN='AMS1117-5.0', Manufacturer='AMS'),
    ('AMS1117-3.3', 'AMS1117-3.3', 'SOT223'): dict(LCSC='C6186', MPN='AMS1117-3.3', Manufacturer='AMS'),
    ('CS4270', 'CS4270', 'TSSOP24'): dict(LCSC='C1323229', MPN='CS4270-CZZR', Manufacturer='Cirrus Logic'),
    ('OPA1679', 'OPA1679', 'SOIC14'): dict(LCSC='C2878631', MPN='OPA1679IDR', Manufacturer='Texas Instruments'),
    ('OPA1678', 'OPA1678', 'SOIC8'): dict(LCSC='C192421', MPN='OPA1678IDR', Manufacturer='Texas Instruments'),
    ('ASE-xxxMHz', '24.576MHz', 'OSC3225'): dict(LCSC='C5203547', MPN='OT2EL4C4JI-111OLP-24.576M',
                                                 Manufacturer='YXC'),
    ('SW_Push', 'RESET', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('SW_Push', 'BOOT', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR USB-AUDIO - carrier (jack/pot board), S1. 2 in / 2 out, DC-coupled +/-5 V, '
                     'CS4270 24-bit 192 kHz. Circuit intent: docs/research.md; placement: docs/geometry.json', 2.0),
    ((20.32, 33.02), 'POWER: +12V -> D2 -> +12V_F (op-amps; U1 AMS1117-5.0 -> +5VA; R1 33R -> U2 AMS1117-3.3 -> +3V3 '
                     '-> FB1 -> +3V3_C); -12V -> D1 -> -12V_F', 1.4),
    ((20.32, 121.92), 'PWR_FLAG: GND/+12V/-12V at J1; +12V_F/-12V_F behind D2/D1; V3_IN behind R1; +3V3_C behind FB1.',
     1.1),
    ((203.2, 116.84), 'CS4270 CODEC: I2C control port, address 0x48. Master, quad speed: MCLK 24.576 MHz / 128 = 192 kHz;\n'
                      'SCLK = 64 x Fs to both CH32V307 I2S slaves (I2S2 RX, I2S3 TX). HPF freeze (reg 04h b7/b6) for DC.\n'
                      'Firmware: RST high after clocks, write PDN within 1045 LRCK periods, then FM = quad master.', 1.1),
    ((20.32, 223.52), 'INPUTS: jack (TN = GND) -> 50k volume (0..1) -> 1k -> U4A/B follower (+/-12 V, at the pots)\n'
                      '-> U6A/B inverting driver on +5VA (-0.255, + at VB_IN) -> 220R / 2.2n C0G -> AINA/AINB.\n'
                      '+/-5.49 V = 2.8 Vpp ADC full scale. ADC_INV restores the polarity.', 1.1),
    ((322.58, 223.52), 'OUTPUTS: AOUTA/B -> 470R / 1n C0G -> U5A/B gain 3.2 (Rg 10k to VREF_OUT, Rf 22k)\n'
                       '-> 50k volume (0..1) -> U7A/B follower -> 1k -> jack. 3.25 Vpp DAC full scale -> +/-5.2 V.\n'
                       'Power-up: AOUT starts at 0 V (Popguard) so the outputs sit near -8 V for ~0.4 s.', 1.1),
    ((20.32, 309.88), 'REFERENCES (+5VA): U6C buffers VQ (VA/2) -> VB_IN = VQ x 20/25.1 (input drivers);\n'
                      'U6D: VREF_OUT = VQ x 32/22 (output stages). Both track the codec mid-rail.', 1.1),
    ((449.58, 50.8), 'MCU BOARD LINK: J6/J7 1x10 2.54 mm male headers (plastic on the carrier F side);\n'
                     'the MCU board (usb-audio-mcu) solders on top. BOOT/RESET and SWD on the carrier (B side):\n'
                     'hold BOOT, press RESET = CH32V307 ROM bootloader on the USB-C.', 1.1),
]

TEXT_LEFT = {'R15', 'R17', 'R41', 'R42'}
TEXT_POS = {'U1': ((0, -6.35), (0, -3.81)), 'U2': ((0, -6.35), (0, -3.81)),
            'U4/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U7/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U5/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U6/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U3': ((0, -26.67), (10.16, 26.67)), 'Y1': ((0, -10.16), (0, 10.16)),
            'R11': ((-2.54, 2.54), (2.54, 2.54), 'right'),
            'R12': ((-2.54, -2.54), (2.54, -2.54), 'right'),
            'SW1': ((0, -3.81), (0, 3.81)), 'SW2': ((0, -3.81), (0, 3.81)),
            'J6': ((0, -13.97), (0, 16.51)), 'J7': ((0, -13.97), (0, 16.51)), 'J8': ((0, -6.35), (0, 6.35))}

MULTI_UNIT = {'U4': {1, 2, 3}, 'U5': {1, 2, 3}, 'U6': {1, 2, 3, 4, 5}, 'U7': {1, 2, 3}}
