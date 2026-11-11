"""MULTI-MIX carrier (jack board) S3 circuit table, drawing and sourcing (tools/build_schematic.py).

CIRCUIT is docs/research.md section 3. A digital 4-channel mixer on modules/usb-audio-max's codec,
power and MCU board, in modules/4mix's panel layout widened to 20HP (same jack and pot references;
the MCU board takes the MAIN/OUT spot, OUT and MAIN stack beside it: docs/geometry.json):

- Power: modules/usb-audio-max unchanged (J8 = its J1): Eurorack 10-pin +/-12 V -> B5819W ->
  +12V_F / -12V_F; +12V_F -> R1 || R2 -> discrete regulator (U1A LM358 + Q1 BCP56, U9 REF5050A
  reference) -> +5VA (codec VCC, input drivers); +12V_F -> FB2 + R3 -> U2 TPS562208 FCCM buck -> L1
  -> +3V3 (MCU board, pots, mux, link logic) -> FB1 -> +3V3_C (codec VDD, clock logic) -> R21 ->
  +3V3_OSC (Y1).
- Codec: U3 PCM3168A at 48 kHz only (SCKI 24.576 MHz = 512 fS, single-rate TDM, BCK 256 fS =
  12.288 MHz): DOUT1 = ADC 1-6, DIN1 = DAC 1-8; DOUT2 open, DIN2-4 to GND. I2C 0x44 (ADR0 to GND,
  ADR1 10k to GND). The ADC is the
  TDM clock master (DAC tied as slave) on a stand-alone unit or the chain master; on a clock slave
  (CLK IN connected) the ADC and DAC stay in slave mode (the register reset default, TI SBAS452A
  Table 13) and the clocks come from the link.
- Inputs (x6): CH1-CH4 (J101-J401) and RTN A / RTN B (J3/J4). Jack (TN -> NORM) -> 10u (AC
  coupling, modules/4mix D3) -> 100k -> U5/U6 inverting driver on +5VA (20k || 47p, + input at
  VCOM_REF) -> 470R / 2.2n C0G -> VINn+ (single-ended ADC). Full scale +/-7.07 V (14.1 Vpp): 10 Vpp
  Eurorack audio sits at -3 dBFS. 100k input impedance.
- NORM: every jack normal (TN) sits on one node, R64 1k to GND with R63 100k from NORM_PROBE (MCU
  PA8): an unpatched input reads a ~-50 dBFS pseudo-random probe, so the firmware knows which inputs
  are patched (RTN A/B unpatched = take the return from USB).
- Outputs (x5): DAC1 SEND A (J1), DAC2 SEND B (J2), DAC3 MAIN OUT (J5), DAC4 USB 1 (J9), DAC5 USB 2
  (J10: two outputs the host assigns, e.g. from Ableton). Net DACn = output n; the codec channel behind it
  is CODEC_VOUT (R1 routing, 2026-11-09: the outputs to U7 take the western VOUT3-5 pins, the outputs to U8
  the eastern VOUT1-2 pins, so the two groups leave the codec without crossing and land on U7/U8 in
  their pin order; the firmware maps the TDM slots). VOUT6-8 unused (open).
  U7A-C / U8A-B difference amplifiers on +/-12 V (15k in, 27k || 47p, gain 1.8: 8 Vpp differential -> +/-7.2 V,
  matches the inputs) -> 2 x 2k 1206 (1k, 0.5 W) -> jack, DC-coupled (no VCOMDA excursion).
- Pots (x15, modules/4mix references; RV1 MAIN now below OUT): RV09 50k B as DC dividers +3V3_POT (R62 47R / C48 10u from
  +3V3) to GND, wiper 100n -> U10 74HC4067 (S0-S3 from the MCU) -> R61 1k -> POT_ADC (MCU PC1).
  I15 = GND (ADC zero check). Nothing on the knobs carries audio.
- Clock link (2x5 keyed IDC, docs/research.md section 4): CLK OUT (J6, left edge) / CLK IN (J7,
  right edge), same pinout, daisy chain: straight ribbon from a unit's CLK OUT to the next unit's
  CLK IN (slaves to the left of the master). Clock only: no audio and no control crosses the link;
  each unit keeps its own USB and its own outputs. The master is the unit with CLK IN open. Pinout
  survives a Eurorack power cable: pins 1-2 (-12 V) carry only the 4.7k/10k-protected DET line or
  nothing, pins 9-10 (+12 V) nothing; pins 3-8 (GND) carry GND and the clocks behind 150R.
  1 DET (CLK OUT: 4.7k to GND; CLK IN: 10k -> LINK_N, 100k pull-up, BAT54S clamp: low = linked)
  2 NC; 3, 5, 8 GND; 4 SCKI; 6 BCK; 7 LRCK; 9, 10 NC.
  LINK_N switches the clocks by hardware: U11 74LVC1G97 (2:1 mux) picks Y1 or the link SCKI, U13
  74LVC2G125 drives the link BCK/LRCK onto the codec clock nets (codec in slave mode). U12/U14A
  74LVC2G34 repeat SCKI/BCK/LRCK out of CLK OUT to the next unit (U14B spare).
- MCU board: J12/J13 1x12 2.54 mm strips (= J112/J113 on the MCU board). BOOT/RESET (SW2/SW1) and
  SWD (J15) on the carrier B side. S3 strip map (2026-11-10, user: single-sided MCU board extended to the
  carrier top, strips moved up; the third strip J14 between the MCU and the codec is gone): J12 (west)
  boot/reset, DOUT1, codec reset, POT_ADC, MUX_S0-S3 and LINK_N; J13 (east) SWD, DIN1, I2C, BCK/LRCK and
  NORM_PROBE. Each strip pin faces its codec pin or its carrier part. The I2C pull-ups are on the MCU
  board (R108/R109).
"""

PAPER = 'A1'

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+3V3_C': '+3V3', '+3V3_OSC': '+3V3', '+3V3_POT': '+3V3', '+3V3_POTB': '+3V3',
               '+5VA': '+5VA', '+12V': '+12V', '-12V': '-12V', '+12V_F': '+12V', '-12V_F': '-12V'}

IN_CH = range(1, 7)
OUT_CH = range(1, 6)
# input n -> (jack, tip net, panel role); CH1-CH4 and the jack refs are modules/4mix's
IN_JACK = {1: ('J101', 'IN_CH1', 'CH1 IN'), 2: ('J201', 'IN_CH2', 'CH2 IN'), 3: ('J301', 'IN_CH3', 'CH3 IN'),
           4: ('J401', 'IN_CH4', 'CH4 IN'), 5: ('J3', 'IN_RTNA', 'RETURN A'), 6: ('J4', 'IN_RTNB', 'RETURN B')}
# output n (= DAC n) -> (jack, net, panel role)
OUT_JACK = {1: ('J1', 'SEND_A', 'SEND A'), 2: ('J2', 'SEND_B', 'SEND B'), 3: ('J5', 'MAIN_OUT', 'MAIN OUT'),
            4: ('J9', 'USB_OUT1', 'USB 1'), 5: ('J10', 'USB_OUT2', 'USB 2')}
# Input driver units: channel -> (ref, unit); U6C is the VCOM buffer, U6D spare.
IN_AMP = {1: ('U5', 1), 2: ('U5', 2), 3: ('U5', 3), 4: ('U5', 4), 5: ('U6', 1), 6: ('U6', 2)}
# Output stages: U7A-C (SEND A/B, MAIN; U7D spare), U8 OPA1678 dual by the USB 1/2 jacks (bottom right)
# output n -> codec VOUT channel (TDM DAC slot): SEND A 5, SEND B 3, MAIN 4, USB 1 1, USB 2 2
CODEC_VOUT = {1: 5, 2: 3, 3: 4, 4: 1, 5: 2}
OUT_AMP = {1: ('U7', 1), 2: ('U7', 2), 3: ('U7', 3), 4: ('U8', 1), 5: ('U8', 2)}
# Pots (modules/4mix references) in mux order: (ref, wiper net, role); mux input = index
POTS = [('RV101', 'W_VOL1', 'CH1 VOL'), ('RV102', 'W_SA1', 'CH1 SEND A'), ('RV103', 'W_SB1', 'CH1 SEND B'),
        ('RV201', 'W_VOL2', 'CH2 VOL'), ('RV202', 'W_SA2', 'CH2 SEND A'), ('RV203', 'W_SB2', 'CH2 SEND B'),
        ('RV301', 'W_VOL3', 'CH3 VOL'), ('RV302', 'W_SA3', 'CH3 SEND A'), ('RV303', 'W_SB3', 'CH3 SEND B'),
        ('RV401', 'W_VOL4', 'CH4 VOL'), ('RV402', 'W_SA4', 'CH4 SEND A'), ('RV403', 'W_SB4', 'CH4 SEND B'),
        ('RV2', 'W_LVLA', 'RETURN A level'), ('RV3', 'W_LVLB', 'RETURN B level'), ('RV1', 'W_MAIN', 'MAIN')]
# Top-row pots: own supply filter R65/C50 (+3V3_POTB), the other twelve share R62/C48 (+3V3_POT)
TOP_POTS = ('RV1', 'RV2', 'RV3')
# 74HC4067 data pins I0..I15
MUX_IN = ['9', '8', '7', '6', '5', '4', '3', '2', '23', '22', '21', '20', '19', '18', '17', '16']

# Symbols drawn mirrored about X: input jacks (sleeve down), the output difference amplifiers
# (- input on top for the feedback, + input below with its divider to GND), Q2 and the pots (CW end up).
MIRROR_X = ({IN_JACK[n][0] for n in IN_CH} | {f'{u}/{k}' for u, k in OUT_AMP.values()} | {'Q2'}
            | {ref for ref, _, _ in POTS})

NOT_ASSEMBLED = set()

PWR = (40.64, 66.04)          # J8 (modules/usb-audio-max J1)
COD_A = (198.12, 254.0)       # U3 unit 1 (analog)
COD_D = (431.8, 101.6)        # U3 unit 2 (interface, control, supplies)
IN_X0, IN_Y = 22.86, [190.5 + 27.94 * k for k in range(6)]
OUT_X0, OUT_Y = 299.72, [172.72 + 38.1 * k for k in range(5)]
U7D_AT = (OUT_X0, 363.22)           # spare U7D follower, below the output stages
NORM_Y = 360.68
REF_Y = (393.7, 431.8)        # VCOM buffer / spare U6D rows
HDR = (622.3, 101.6)          # J12; J13 at +30.48
PU_Y = 525.78                 # op-amp / logic supply units row
BUCK = (170.18, 127.0)        # U2 VIN/EN side x + 10.16, V3_IN rail y
LX, LY = 480.06, 241.3        # J7 CLK IN; J6 CLK OUT at LY + 50.8
DX = LX + 101.6               # link drivers / receivers column
MX, MY = 401.32, 495.3        # U10 mux
POT_X, POT_Y = [462.28 + 55.88 * c for c in range(5)], [452.12, 497.84, 543.56]

# OPA1679 unit pins: unit -> (+, -, out)
OPA4 = {1: ('3', '2', '1'), 2: ('5', '6', '7'), 3: ('10', '9', '8'), 4: ('12', '13', '14')}
# OPA1678 (dual) unit pins
OPA2 = {1: ('3', '2', '1'), 2: ('5', '6', '7')}
DUAL = {'U8'}


def amp_pins(ref, unit):
    return (OPA2 if ref in DUAL else OPA4)[unit]

POTNOTE = ('RV09 50k B (linear), user stock (no bushing/nut), on the Bread Modular RV09 footprint, hand-soldered. '
           'DC divider only (no audio): pin 3 (CW) = +3V3_POT, pin 1 (CCW) = GND, wiper -> 74HC4067')


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/L/FB: rot 90 = horizontal, pin 1 left; rot 0 = vertical,
    pin 1 on top. Diodes: rot 0 = K left."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def opamp(ref, unit, at, plus, minus, out, **fields):
    p, m, o = amp_pins(ref, unit)
    if ref in DUAL:
        return part(ref, 'OPA1678', 'OPA1678', 'SOIC8', at, 0, {p: plus, m: minus, o: out}, unit=unit, **fields)
    return part(ref, 'OPA1679', 'OPA1679', 'SOIC14', at, 0, {p: plus, m: minus, o: out}, unit=unit, **fields)


def clamp(ref, at, net):
    """BAT54S at rot 180: COM on top (on the signal wire), K left (+3V3), A right (GND)."""
    return part(ref, 'BAT54S', 'BAT54S', 'SOT23', at, 180, {'1': 'GND', '2': '+3V3', '3': net},
                Note='Clamp to +3V3/GND behind the 10k series resistor: a Eurorack power cable plugged into the '
                     'CLK header puts -12 V on pin 1 (1.5 mA into the clamp)')


def circuit():
    c = []
    # ---- Power entry (modules/usb-audio-max): Eurorack +/-12 V -> series Schottkys
    c.append(part('J8', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', PWR, 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header (modules/4mix J8 position, bottom right on B), pin 1 (-12 V) '
                       'at the board bottom; also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(two('D1', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 55.88), '-12V', '-12V_F', rot=0,
                 Note='-12 V series reverse-polarity protection'))
    c.append(two('D2', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 76.2), '+12V_F', '+12V', rot=180,
                 Note='+12 V series reverse-polarity protection (~0.4 A: 0.2 W)'))
    c.append(two('C2', 'C', '10u', 'C0805', (78.74, 59.69), 'GND', '-12V_F', rot=180, Voltage='25V',
                 Note='-12V_F bulk'))
    c.append(two('C1', 'C', '10u', 'C0805', (78.74, 80.01), '+12V_F', 'GND', rot=0, Voltage='25V',
                 Note='+12V_F bulk'))
    # +5VA: pre-drop pair + discrete regulator (LM358 + BCP56 emitter follower) referenced to a REF5050
    for ref, yy in (('R1', 76.2), ('R2', 68.58)):
        c.append(two(ref, 'R', '33', 'R2512', (99.06, yy), '+12V_F', 'V5_IN', Power='1W',
                     Note='R1 || R2 = 16.5R pre-drop for Q1 (modules/usb-audio-max D7/D11). +5VA load here ~170 mA '
                          '(codec VCC + 2 x OPA1679): ~2.8 V, 0.24 W each'))
    c.append(two('C3', 'C', '10u', 'C0805', (109.22, 80.01), 'V5_IN', 'GND', rot=0, Voltage='25V',
                 Note='Q1 collector'))
    c.append(part('Q1', 'BCP56', 'BCP56-16', 'SOT223', (124.46, 78.74), 90,
                  {'1': '_Q1_B', '2': 'V5_IN', '3': '_Q1_E', '4': 'V5_IN'},
                  Note='+5VA pass transistor (emitter follower in the U1A loop). ~0.6 W at 12.6 V / 170 mA: '
                       '>= 1 cm2 collector (tab) copper'))
    c.append(two('R8', 'R', '2.2', 'R1206', (139.7, 76.2), '_Q1_E', '+5VA', Tolerance='1%',
                 Note='Current sense: Q2 limits +5VA at ~0.3-0.35 A. Inside the U1A loop, so it adds no DC error'))
    c.append(part('Q2', 'MMBT3904', 'MMBT3904', 'SOT23', (134.62, 86.36), 90,
                  {'1': '_Q1_E', '2': '+5VA', '3': '_Q1_B'},
                  Note='Current limit: steals Q1 base drive through R9 when R8 drops ~0.65 V. Not thermal: '
                       'keep it away from Q1'))
    c.append(two('R9', 'R', '150', 'R0603', (116.84, 101.6), '_REG_OUT', '_Q1_B',
                 Note='Base resistor: lets Q2 override U1A'))
    c.append(part('U1', 'LM358', 'LM358', 'SOIC8', (101.6, 101.6), 0, {'3': 'V5_SET', '2': '_REG_FB', '1': '_REG_OUT'},
                  Note='+5VA error amplifier on +12V_F (modules/usb-audio-max D11: PI compensation R16/C37 with R7, '
                       'ngspice PM >= 78 deg)'))
    c.append(part('U1', 'LM358', 'LM358', 'SOIC8', (162.56, 104.14), 0, {'5': 'GND', '6': '_U1B', '7': '_U1B'},
                  unit=2, Note='Unused half: follower at GND'))
    c.append(part('U1', 'LM358', 'LM358', 'SOIC8', (180.34, 99.06), 0, {'8': '+12V_F', '4': 'GND'}, unit=3))
    c.append(two('C38', 'C', '100n', 'C0603', (193.04, 99.06), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U1 V+'))
    c.append(two('R7', 'R', '10k', 'R0603', (81.28, 104.14), '+5VA', '_REG_FB',
                 Note='Feedback from +5VA, Kelvin-sensed at the codec VCC pins; equals R6 (bias currents cancel)'))
    c.append(two('R16', 'R', '47k', 'R0603', (104.14, 111.76), '_REG_CC', '_REG_OUT',
                 Note='PI zero (154 Hz with C37)'))
    c.append(two('C37', 'C', '22n', 'C0603', (93.98, 111.76), '_REG_FB', '_REG_CC', Voltage='50V',
                 Note='Integrator with R7: zero DC error'))
    c.append(two('C16', 'C', '1u', 'C0603', (187.96, 67.31), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U9 input'))
    c.append(part('U9', 'REF5050AD', 'REF5050A', 'SOIC8', (205.74, 71.12), 0,
                  {'1': None, '2': '+12V_F', '3': None, '4': 'GND', '5': 'REF_NR', '6': '_REF_OUT', '7': None,
                   '8': None},
                  Note='+5VA reference (as modules/usb-audio-max: +5VA sets the codec gain; kept so the two '
                       'modules share one power design)'))
    c.append(two('C17', 'C', '1u', 'C0603', (218.44, 82.55), 'REF_NR', 'GND', rot=0, Voltage='50V',
                 Note='U9 TRIM/NR noise reduction'))
    c.append(two('C18', 'C', '10u', 'C0805', (226.06, 72.39), '_REF_OUT', 'GND', rot=0, Voltage='25V',
                 Note='U9 output (datasheet 1-50 uF, ESR <= 1.5R)'))
    c.append(two('R6', 'R', '10k', 'R0603', (236.22, 68.58), '_REF_OUT', 'V5_SET',
                 Note='Reference filter with C19 (16 Hz, 10 ms soft start); equals R7'))
    c.append(two('C19', 'C', '1u', 'C0603', (245.11, 72.39), 'V5_SET', 'GND', rot=0, Voltage='50V',
                 Note='Reference filter; ground side Kelvin to the codec AGND'))
    # +3V3: input filter + TPS562208 FCCM buck (only the digital rail is switched)
    xu, yr = BUCK
    ys = yr - 5.08                                   # SW / +3V3 line
    c.append(two('FB2', 'FerriteBead', 'GZ2012D121TF', 'C0805', (101.6, yr), '+12V_F', '_BK_F',
                 Note='Buck input filter (with R3, C6-C8): keeps the switching harmonics off +12V_F and the bus'))
    c.append(two('R3', 'R', '2.2', 'R1206', (113.03, yr), '_BK_F', 'V3_IN', Tolerance='1%',
                 Note='Buck input filter: with C6/C7 a ~5 kHz RC, no LC resonance'))
    for ref, xx in (('C6', 121.92), ('C7', 132.08)):
        c.append(two(ref, 'C', '10u', 'C1206', (xx, yr + 3.81), 'V3_IN', 'GND', rot=0, Voltage='50V',
                     Note='U2 input (1206 50 V). Hot loop C6/C8 - U2 VIN/GND as small as possible'))
    c.append(two('C8', 'C', '100n', 'C0603', (142.24, yr + 3.81), 'V3_IN', 'GND', rot=0, Voltage='50V',
                 Note='U2 VIN HF bypass, right at pins 3/1'))
    c.append(two('R4', 'R', '100k', 'R0603', (xu - 15.24, yr + 5.08), 'V3_IN', '_BK_EN',
                 Note='EN pull-up'))
    c.append(part('U2', 'TPS562208', 'TPS562208', 'SOT23-6', (xu, yr + 2.54), 0,
                  {'1': 'GND', '2': '_BK_SW', '3': 'V3_IN', '4': '_BK_FB', '5': '_BK_EN', '6': '_BK_BST'},
                  Note='+3V3 buck, FCCM variant (TPS562201 is the pulse-skipping one: do not substitute): ~580 kHz '
                       'at every load. Load: MCU board ~100 mA + PCM3168A VDD 130 mA + logic/pots ~10 mA'))
    c.append(two('C4', 'C', '100n', 'C0603', (xu + 17.78, ys + 3.81), '_BK_SW', '_BK_BST', rot=0, Voltage='50V',
                 Note='Bootstrap (VBST to SW)'))
    c.append(two('L1', 'L', '4.7u', 'MWSA0402S', (xu + 31.75, ys), '_BK_SW', '+3V3',
                 Note='Molded (fully shielded) inductor'))
    c.append(two('R20', 'R', '10k', 'R0603', (xu + 22.86, yr + 8.89), '_BK_FB', 'GND', rot=0,
                 Note='Feedback bottom: +3V3 = 0.768 V x (1 + 33k/10k) = 3.30 V'))
    c.append(two('R5', 'R', '33k', 'R0603', (xu + 34.29, yr + 5.08), '_BK_FB', '+3V3',
                 Note='Feedback top (TI table: 33.2k / 10k for 3.3 V)'))
    for ref, dx in (('C9', 43.18), ('C10', 53.34)):
        c.append(two(ref, 'C', '22u', 'C0805', (xu + dx, ys + 3.81), '+3V3', 'GND', rot=0, Voltage='25V',
                     Note='U2 output (2 x 22u)'))
    c.append(two('C5', 'C', '100n', 'C0603', (xu + 63.5, ys + 3.81), '+3V3', 'GND', rot=0, Voltage='50V',
                 Note='U2 output HF'))
    c.append(two('FB1', 'FerriteBead', 'GZ2012D121TF', 'C0805', (xu + 81.28, ys), '+3V3', '+3V3_C',
                 Note='Codec digital / clock-logic supply filter'))
    c.append(two('R21', 'R', '10', 'R0603', (xu + 99.06, ys), '+3V3_C', '+3V3_OSC',
                 Note='Clock oscillator supply filter with C43 / C29 (1.6 kHz). Place at Y1'))
    c.append(two('C43', 'C', '10u', 'C0805', (xu + 106.68, ys + 3.81), '+3V3_OSC', 'GND', rot=0, Voltage='25V',
                 Note='Y1 supply filter, at Y1'))
    for ref, net, at, rot in (('#FLG01', 'GND', (30.48, 68.58), 0), ('#FLG02', '+12V_F', (71.12, 76.2), 180),
                              ('#FLG03', '-12V_F', (71.12, 55.88), 180), ('#FLG04', '+12V', (53.34, 76.2), 180),
                              ('#FLG05', '-12V', (53.34, 55.88), 180), ('#FLG06', 'V5_IN', (114.3, 76.2), 0),
                              ('#FLG07', '+3V3_C', (xu + 91.44, ys), 0), ('#FLG08', 'V3_IN', (118.11, yr), 0),
                              ('#FLG09', '+5VA', (152.4, 76.2), 0), ('#FLG10', '+3V3', (xu + 40.64, ys), 0),
                              ('#FLG11', '+3V3_OSC', (xu + 104.14, ys), 0),
                              ('#FLG12', '+3V3_POT', (MX + 7.62, MY + 38.1), 180),
                              ('#FLG13', '+3V3_POTB', (MX + 7.62, MY + 55.88), 180)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))

    # ---- PCM3168A codec: unit 1 analog, unit 2 interface/control/supplies
    a = {'52': 'ADC_IN1', '54': 'ADC_IN2', '56': 'ADC_IN3', '58': 'ADC_IN4', '62': 'ADC_IN5', '64': 'ADC_IN6',
         '51': 'VCOM_REF', '53': 'VCOM_REF', '55': 'VCOM_REF', '57': 'VCOM_REF', '61': 'VCOM_REF', '63': 'VCOM_REF',
         '1': 'VCOMAD', '59': 'VREFAD1', '60': 'VREFAD2', '15': 'VCOMDA'}
    vout_out = {ch: n for n, ch in CODEC_VOUT.items()}
    for i, (p_, m_) in enumerate((('31', '32'), ('29', '30'), ('27', '28'), ('25', '26'), ('23', '24'),
                                  ('21', '22'), ('19', '20'), ('17', '18'))):
        n = vout_out.get(i + 1)
        a[p_], a[m_] = (f'DAC{n}P', f'DAC{n}N') if n else (None, None)
    c.append(part('U3', 'PCM3168A', 'PCM3168A', 'TQFP64EP', COD_A, 0, a, unit=1,
                  Note='24-bit 6-in / 8-out codec at 48 kHz (single-rate TDM). I2C 0x44. SE inputs; VOUT1-5 used '
                       '(VOUT5 SEND A, VOUT3 SEND B, VOUT4 MAIN, VOUT1 USB 1, VOUT2 USB 2), VOUT6-8 open. PowerPAD to GND with thermal vias (~1.2 W)'))
    c.append(part('U3', 'PCM3168A', 'PCM3168A', 'TQFP64EP', COD_D, 0,
                  {'7': 'BCK_C', '36': 'BCK_C', '6': 'LRCK_C', '35': 'LRCK_C',
                   '8': '_DOUT1_C', '9': None, '10': None,
                   '37': 'I2S_DAC1', '38': 'GND', '39': 'GND', '40': 'GND',
                   '41': '_SCKI', '48': 'GND', '45': 'GND', '44': 'CODEC_ADR1',
                   '43': 'I2C_SDA', '42': 'I2C_SCL', '4': 'CODEC_RST', '5': None, '13': None,
                   '49': '+5VA', '3': '+5VA', '14': '+5VA', '34': '+5VA', '46': '+3V3_C', '12': '+3V3_C',
                   '50': 'GND', '2': 'GND', '16': 'GND', '33': 'GND', '47': 'GND', '11': 'GND', '65': 'GND'},
                  unit=2))
    xd, yd = COD_D
    c.append(part('Y1', 'ASE-xxxMHz', '24.576MHz', 'OSC3225', (xd + 22.86, yd - 43.18), 0,
                  {'1': '+3V3_OSC', '2': 'GND', '3': '_OSC', '4': '+3V3_OSC'},
                  Note='24.576 MHz 3.3 V CMOS oscillator (YXC OT2EL, 3225): SCKI = 512 fS at 48 kHz. Runs on '
                       'every unit; U11 passes it on unless CLK IN is connected'))
    c.append(two('R10', 'R', '33', 'R0603', (xd + 38.1, yd - 43.18), '_OSC', 'SCKI_LOC',
                 Note='Series termination: Y1 -> U11 In0'))
    c.append(two('R60', 'R', '33', 'R0603', (xd + 27.94, yd - 20.32), '_SCKI', 'SCKI_SEL',
                 Note='Series termination: U11 (selected SCKI) -> codec SCKI'))
    c.append(part('U4', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (xd - 45.72, yd - 20.32), 180,
                  {'3': 'BCK_C', '4': 'BCK_B'}, unit=2,
                  Note='BCK/LRCK buffer to the MCU board and the CLK OUT repeaters (U12): the codec clock pins '
                       'see two short loads (U4, U13 output) only. Channels follow the layout: unit B (3/4) BCK, '
                       'unit A (1/6) LRCK'))
    c.append(part('U4', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (xd - 45.72, yd - 5.08), 180,
                  {'1': 'LRCK_C', '6': 'LRCK_B'}, unit=1))
    for ref, row, a_, b_, note in (('R11', yd - 20.32, 'I2S_SCLK', 'BCK_B', 'BCK to the MCU (I2S2/I2S3 CK)'),
                                   ('R12', yd - 5.08, 'I2S_LRCK', 'LRCK_B', 'LRCK to the MCU (WS)')):
        c.append(two(ref, 'R', '33', 'R0603', (xd - 66.04, row), a_, b_, Note=f'Series termination: {note}'))
    c.append(two('R13', 'R', '33', 'R0603', (xd - 27.94, yd + 10.16), 'I2S_ADC1', '_DOUT1_C',
                 Note='Series termination: DOUT1 (ADC 1-6 at 48 kHz) to PB5 (I2S3 SD / SPI3 MOSI)'))
    c.append(two('R15', 'R', '10k', 'R0603', (xd + 35.56, yd - 12.7), 'CODEC_ADR1', 'GND',
                 Note='ADR1 strap (I2C address bit 1 = 0) through a resistor: the pin is the MDO output in '
                      'SPI mode and has no internal pull-down'))
    c.append(two('R17', 'R', '10k', 'R0603', (xd + 25.4, yd + 11.43), 'CODEC_RST', 'GND', rot=0,
                 Note='Holds the codec in reset until the MCU (PC0) releases it with SCKI running'))
    for i, (ref, val, fp, net, volt, note) in enumerate((
            ('C20', '1u', 'C0603', '+5VA', '50V', 'VCCAD1 pin 49'), ('C21', '1u', 'C0402', '+5VA', '25V', 'VCCAD2 pin 3'),
            ('C22', '1u', 'C0603', '+5VA', '50V', 'VCCDA1 pin 14'), ('C23', '1u', 'C0603', '+5VA', '50V', 'VCCDA2 pin 34'),
            ('C24', '10u', 'C0805', '+5VA', '25V', 'VCC (ADC side) bulk'),
            ('C25', '10u', 'C0805', '+5VA', '25V', 'VCC (DAC side) bulk'),
            ('C26', '1u', 'C0603', '+3V3_C', '50V', 'VDD1 pin 46'), ('C27', '1u', 'C0402', '+3V3_C', '25V', 'VDD2 pin 12'),
            ('C28', '10u', 'C0805', '+3V3_C', '25V', 'VDD bulk'),
            ('C29', '100n', 'C0603', '+3V3_OSC', '50V', 'Y1 supply'), ('C30', '100n', 'C0603', '+3V3_C', '50V', 'U4 supply'))):
        c.append(two(ref, 'C', val, fp, (370.84 + 10.16 * i, 160.02), net, 'GND', rot=0, Voltage=volt,
                     Note=f'{note} decoupling'))
    for i, (ref, val, fp, net, volt, note) in enumerate((
            ('C11', '10u', 'C0805', 'VCOMAD', '25V', 'VCOMAD (pin 1)'), ('C12', '10u', 'C0805', 'VCOMDA', '25V', 'VCOMDA (pin 15)'),
            ('C13', '10u', 'C0805', 'VREFAD1', '25V', 'VREFAD1 (pin 59)'), ('C14', '100n', 'C0603', 'VREFAD1', '50V', 'VREFAD1 HF'),
            ('C15', '10u', 'C0805', 'VREFAD2', '25V', 'VREFAD2 (pin 60)'))):
        c.append(two(ref, 'C', val, fp, (165.1 + 10.16 * i, 300.99), net, 'GND', rot=0, Voltage=volt,
                     Note=f'{note} decoupling, at the pin'))

    # ---- Inputs: CH1-CH4, RTN A, RTN B (AC-coupled, as modules/4mix D3)
    for n, y in zip(IN_CH, IN_Y):
        x0 = IN_X0
        u, k = IN_AMP[n]
        jack, tip, role = IN_JACK[n]
        c.append(part(jack, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0, y), 0,
                      {'T': tip, 'S': 'GND', 'TN': 'NORM'},
                      Note=f'{role}: audio, AC-coupled, 100k, up to +/-7.07 V before ADC clipping. TN on NORM: '
                           'unpatched = 0 V plus the NORM_PROBE patch-detect probe'))
        c.append(two(f'C{220 + n}', 'C', '10u', 'C0805', (x0 + 17.78, y), tip, f'_IN{n}_AC', Voltage='25V',
                     Note='AC coupling (modules/4mix D3: 10u into 100k, -3 dB at 0.16 Hz); X5R, the DC across it '
                          'is VCOM (~2.5 V) plus any DC on the patch'))
        c.append(two(f'R{200 + n}', 'R', '100k', 'R0603', (x0 + 30.48, y), f'_IN{n}_AC', f'_IN{n}_SUM',
                     Note='Rin: 100k input impedance; gain -20k/100k = -0.2'))
        c.append(opamp(u, k, (x0 + 50.8, y - 2.54), 'VCOM_REF', f'_IN{n}_SUM', f'_IN{n}_DRV',
                       Note='+5VA single-supply ADC drivers (U5A-D CH1-4, U6A/B RTN A/B), VCOM buffer (U6C), '
                            'spare (U6D). Rail-to-rail out: VIN never leaves 0..5 V'))
        c.append(two(f'R{210 + n}', 'R', '20k', 'R0603', (x0 + 50.8, y + 5.08), f'_IN{n}_SUM', f'_IN{n}_DRV',
                     Note='Rf: +/-7.07 V at the jack = +/-1.414 V (1 Vrms SE full scale at VCC 5 V)'))
        c.append(two(f'C{200 + n}', 'C', '47p', 'C0603', (x0 + 50.8, y + 12.7), f'_IN{n}_SUM', f'_IN{n}_DRV',
                     Voltage='50V', Dielectric='C0G', Note='Rf || 47p: 169 kHz pole'))
        c.append(two(f'R{220 + n}', 'R', '470', 'R0603', (x0 + 68.58, y - 2.54), f'_IN{n}_DRV', f'ADC_IN{n}',
                     Note='ADC input network (datasheet 12.1.3: 47R/0.1u .. 470R/1n, ~160 kHz)'))
        c.append(two(f'C{210 + n}', 'C', '2.2n', 'C0603', (x0 + 76.2, y + 1.27), f'ADC_IN{n}', 'GND', rot=0,
                     Voltage='50V', Dielectric='C0G', Note='ADC charge reservoir / anti-alias (154 kHz), C0G'))
    c.append(two('R63', 'R', '100k', 'R0603', (40.64, NORM_Y), 'NORM_PROBE', 'NORM',
                 Note='Patch-detect probe: MCU PA8 pseudo-random bits, 3.3 V x 1k/101k = 33 mV on NORM; an unpatched '
                      'input reads it at ~-50 dBFS, a patched one never (its TN is open)'))
    c.append(two('R64', 'R', '1k', 'R0603', (55.88, NORM_Y + 3.81), 'NORM', 'GND', rot=0,
                 Note='NORM to GND: unpatched inputs sit at 0 V through 1k (as modules/4mix TN to GND)'))

    # ---- Outputs: DAC1 SEND A, DAC2 SEND B, DAC3 MAIN, DAC4 USB 1, DAC5 USB 2
    for n, y in zip(OUT_CH, OUT_Y):
        xo = OUT_X0
        u, k = OUT_AMP[n]
        jack, net, role = OUT_JACK[n]
        c.append(two(f'R{300 + n}', 'R', '15k', 'R0603', (xo - 17.78, y - 2.54), f'DAC{n}N', f'_OUT{n}_M',
                     Tolerance='1%', Note='Difference amplifier Rin (VOUT-)'))
        c.append(two(f'R{310 + n}', 'R', '15k', 'R0603', (xo - 35.56, y + 2.54), f'DAC{n}P', f'_OUT{n}_P',
                     Tolerance='1%', Note='Difference amplifier Rin (VOUT+)'))
        c.append(opamp(u, k, (xo, y), f'_OUT{n}_P', f'_OUT{n}_M', f'_OUT{n}_AMP',
                       Note='+/-12 V difference amplifiers (U7A SEND A, U7B SEND B, U7C MAIN, U7D spare; '
                            'U8A USB 1, U8B USB 2)'))
        c.append(two(f'R{320 + n}', 'R', '27k', 'R0603', (xo, y - 10.16), f'_OUT{n}_M', f'_OUT{n}_AMP',
                     Tolerance='1%', Note='Rf: gain 27k/15k = 1.8, 8 Vpp differential -> +/-7.2 V (inputs +/-7.07 V)'))
        c.append(two(f'C{300 + n}', 'C', '47p', 'C0603', (xo, y - 17.78), f'_OUT{n}_M', f'_OUT{n}_AMP',
                     Voltage='50V', Dielectric='C0G', Note='Rf || 47p: 125 kHz pole'))
        c.append(two(f'R{330 + n}', 'R', '27k', 'R0603', (xo - 15.24, y + 6.35), f'_OUT{n}_P', 'GND', rot=0,
                     Tolerance='1%', Note='Rg to GND: the VCOMDA common mode cancels'))
        c.append(two(f'C{310 + n}', 'C', '47p', 'C0603', (xo - 25.4, y + 6.35), f'_OUT{n}_P', 'GND', rot=0,
                     Voltage='50V', Dielectric='C0G', Note='Matches Cf on the + leg'))
        for ref, yy in ((f'R{340 + n}', y), (f'R{350 + n}', y + 7.62)):
            other = f'R{350 + n}' if ref == f'R{340 + n}' else f'R{340 + n}'
            c.append(two(ref, 'R', '2k', 'R1206', (xo + 17.78, yy), f'_OUT{n}_AMP', net,
                         Power='0.25W', Tolerance='1%',
                         Note=f'Parallel with {other}: 1k / 0.5W effective (modules/usb-audio-max). '
                              'Opposing 7.2V output / 12.6V patch: <=0.24W each'))
        c.append(part(jack, 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (xo + 33.02, y), 180,
                      {'T': net, 'S': 'GND', 'TN': None}, Note=f'{role}: audio, DC-coupled, 1k'))
    c.append(part('U7', 'OPA1679', 'OPA1679', 'SOIC14', U7D_AT, 0, {'12': 'GND', '13': '_U7D', '14': '_U7D'},
                  unit=4, Note='Spare section: follower at GND'))

    # ---- VCOM reference on +5VA (U6C) and the spare U6D
    y0, y1 = REF_Y
    c.append(opamp('U6', 3, (76.2, y0), 'VCOMAD', '_VCOM_BUF', '_VCOM_BUF',
                   Note='VCOMAD buffer (10k source, 1 uA max)'))
    c.append(two('R50', 'R', '100', 'R0603', (93.98, y0), '_VCOM_BUF', 'VCOM_REF',
                 Note='Isolates U6C from the 10 uF on VCOM_REF'))
    c.append(two('C40', 'C', '10u', 'C0805', (104.14, y0 + 3.81), 'VCOM_REF', 'GND', rot=0, Voltage='25V',
                 Note='VCOM_REF: VIN1-6 - (single-ended termination) and the driver + inputs (AC-coupled inputs '
                      'idle at VCOM)'))
    c.append(two('C41', 'C', '100n', 'C0603', (114.3, y0 + 3.81), 'VCOM_REF', 'GND', rot=0, Voltage='50V',
                 Note='VCOM_REF HF, at the codec'))
    c.append(opamp('U6', 4, (81.28, y1), 'VCOM_REF', '_U6D', '_U6D', Note='Spare section: follower at VCOM_REF'))

    # ---- Pots: 15 x RV09 DC dividers -> U10 74HC4067 -> POT_ADC
    for i, (ref, wiper, role) in enumerate(POTS):
        px, py = POT_X[i % 5], POT_Y[i // 5]
        rail = '+3V3_POTB' if ref in TOP_POTS else '+3V3_POT'
        c.append(part(ref, 'R_Potentiometer', '50k B', 'RV09', (px, py), 0, {'3': rail, '1': 'GND', '2': wiper},
                      Note=f'{role} (panel position: docs/geometry.json; mux input I{i}). ' + POTNOTE))
        c.append(two(f'C{701 + i}', 'C', '100n', 'C0603', (px + 10.16, py + 3.81), wiper, 'GND', rot=0, Voltage='50V',
                     Note='Wiper filter: low source impedance for the mux/ADC sampling, ~1 ms with the pot'))
    mux = {'1': '_POT_COM', '10': 'MUX_S0', '11': 'MUX_S1', '14': 'MUX_S2', '13': 'MUX_S3', '15': 'GND',
           '24': '+3V3', '12': 'GND'}
    mux.update({MUX_IN[i]: w for i, (_, w, _) in enumerate(POTS)})
    mux[MUX_IN[15]] = 'GND'
    c.append(part('U10', '74HC4067', '74HC4067PW', 'TSSOP24', (MX, MY), 0, mux,
                  Note='16:1 analog mux on +3V3: I0-I14 = the 15 pot wipers (table in docs/research.md), I15 = GND '
                       '(ADC zero check). /E tied low; S0-S3 from the MCU (PC2, PC3, PA0, PA1)'))
    c.append(two('R61', 'R', '1k', 'R0603', (MX - 22.86, MY - 12.7), 'POT_ADC', '_POT_COM',
                 Note='Mux COM -> MCU PC1 (ADC_IN11); with the 100n wiper caps the sample charge comes from the caps'))
    c.append(two('R62', 'R', '47', 'R0603', (MX - 15.24, MY + 38.1), '+3V3', '+3V3_POT',
                 Note='Pot supply filter with C48 (340 Hz); 15 x 50k = 1 mA, 47 mV drop (ratiometric: the firmware '
                      'calibrates both ends)'))
    c.append(two('C48', 'C', '10u', 'C0805', (MX, MY + 41.91), '+3V3_POT', 'GND', rot=0, Voltage='25V',
                 Note='+3V3_POT filter'))
    c.append(two('R65', 'R', '47', 'R0603', (MX - 15.24, MY + 55.88), '+3V3', '+3V3_POTB',
                 Note='Pot supply filter of the top-row pots RV1-RV3 with C50 (340 Hz), placed under them: the '
                      'top row sits north of the codec\'s analog lines, a second local filter saves a rail '
                      'link across them (3 x 50k = 0.2 mA, 9 mV drop; the firmware calibrates both ends)'))
    c.append(two('C50', 'C', '10u', 'C0805', (MX, MY + 59.69), '+3V3_POTB', 'GND', rot=0, Voltage='25V',
                 Note='+3V3_POTB filter'))
    c.append(two('C49', 'C', '100n', 'C0603', (MX + 45.72, MY - 25.4), '+3V3', 'GND', rot=0, Voltage='50V',
                 Note='U10 supply decoupling'))

    # ---- Clock link: J7 CLK IN (from the upstream unit), J6 CLK OUT (to the next unit). Clock only.
    hdr_note = ('Keyed (shrouded) 2x5 IDC box header on B, silk "CLK - NOT POWER". Daisy chain: straight 10-way '
                'ribbon from a unit\'s CLK OUT to the next unit\'s CLK IN. Power-cable safe pinout '
                '(docs/research.md D10)')
    c.append(part('J7', 'Conn_02x05_Odd_Even', 'CLK_IN', 'IDC2x5', (LX, LY), 0,
                  {'1': '_CLKI_DET', '2': None, '3': 'GND', '4': 'CLKI_SCKI', '5': 'GND', '6': 'CLKI_BCK',
                   '7': 'CLKI_LRCK', '8': 'GND', '9': None, '10': None},
                  Note='CLK IN (right edge, B side): from the upstream unit; connected = this unit '
                       'is a clock slave. ' + hdr_note))
    c.append(part('J6', 'Conn_02x05_Odd_Even', 'CLK_OUT', 'IDC2x5', (LX, LY + 50.8), 0,
                  {'1': '_CLKO_DET', '2': None, '3': 'GND', '4': 'CLKO_SCKI', '5': 'GND', '6': 'CLKO_BCK',
                   '7': 'CLKO_LRCK', '8': 'GND', '9': None, '10': None},
                  Note='CLK OUT (left edge, B side): the clocks this unit runs on, repeated to the '
                       'next unit in the chain. ' + hdr_note))
    # link detect / clock-slave select
    c.append(two('R82', 'R', '4.7k', 'R0603', (LX - 15.24, LY + 45.72), 'GND', '_CLKO_DET',
                 Note='Presents GND (4.7k) to the next unit\'s DET: that unit becomes a clock slave. '
                      '-12 V from a power cable: 2.6 mA, 31 mW'))
    c.append(two('R83', 'R', '10k', 'R0603', (LX - 15.24, LY - 5.08), 'LINK_N', '_CLKI_DET',
                 Note='DET input protection (power cable on CLK IN: -12 V -> 1.5 mA into D3)'))
    c.append(two('R84', 'R', '100k', 'R0603', (LX - 22.86, LY - 8.89), '+3V3', 'LINK_N', rot=0,
                 Note='LINK_N pull-up: CLK IN open = high = clock master; linked = 3.3 V x 14.7k/114.7k = 0.42 V'))
    c.append(clamp('D3', (LX - 35.56, LY), 'LINK_N'))
    # pull-downs on the CLK IN clock inputs (open on the master)
    for i, (ref, net) in enumerate((('R76', 'CLKI_SCKI'), ('R77', 'CLKI_BCK'), ('R78', 'CLKI_LRCK'))):
        c.append(two(ref, 'R', '100k', 'R0603', (LX + 30.48 + 10.16 * i, LY + 25.4), net, 'GND', rot=0,
                     Note='Keeps the unused link clock input low on the master'))
    # clock receivers (slave): LINK_N low enables U13 and makes U11 pass the link SCKI
    c.append(part('U13', '74LVC2G125', 'SN74LVC2G125', 'SSOP8', (DX, LY - 35.56), 0,
                  {'1': 'LINK_N', '2': 'CLKI_BCK', '6': '_BCK_RX'}, unit=1,
                  Note='Link BCK/LRCK onto the codec clock nets, only when linked (/OE = LINK_N). The firmware must '
                       'keep the codec ADC in slave mode while LINK_N is low (else R74/R75 limit the fight to 16 mA)'))
    c.append(part('U13', '74LVC2G125', 'SN74LVC2G125', 'SSOP8', (DX, LY - 5.08), 0,
                  {'7': 'LINK_N', '5': 'CLKI_LRCK', '3': '_LRCK_RX'}, unit=2))
    c.append(two('R74', 'R', '100', 'R0603', (DX + 22.86, LY - 35.56), '_BCK_RX', 'BCK_C',
                 Note='Series termination / contention limit: link BCK -> codec BCKAD/BCKDA'))
    c.append(two('R75', 'R', '100', 'R0603', (DX + 22.86, LY - 5.08), '_LRCK_RX', 'LRCK_C',
                 Note='Series termination / contention limit: link LRCK -> codec LRCKAD/LRCKDA'))
    c.append(part('U11', '74LVC1G97', '74LVC1G97', 'SC70-6', (DX, LY + 121.92), 0,
                  {'3': 'SCKI_LOC', '1': 'CLKI_SCKI', '6': 'LINK_N', '4': 'SCKI_SEL', '5': '+3V3_C', '2': 'GND'},
                  Note='2:1 mux (In2 = select: H -> Y = In0 = local Y1, L -> Y = In1 = link SCKI; Diodes DS35127 '
                       'function table). Schmitt inputs. LINK_N switches it: change only with the codec in reset'))
    c.append(two('C44', 'C', '100n', 'C0603', (DX + 30.48, LY + 125.73), '+3V3_C', 'GND', rot=0, Voltage='50V',
                 Note='U11 supply decoupling'))
    # repeaters: every line leaving the board is buffered, behind 150R
    for ref, unit, (pin_in, pin_out), y, src, rser, dst, note in (
            ('U14', 1, ('1', '6'), LY + 30.48, 'SCKI_SEL', 'R72', 'CLKO_SCKI', 'SCKI out of CLK OUT'),
            ('U12', 1, ('1', '6'), LY + 45.72, 'BCK_B', 'R70', 'CLKO_BCK', 'BCK out of CLK OUT'),
            ('U12', 2, ('3', '4'), LY + 60.96, 'LRCK_B', 'R71', 'CLKO_LRCK', 'LRCK out of CLK OUT')):
        c.append(part(ref, '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (DX, y), 0,
                      {pin_in: src, pin_out: f'_{dst}_D'}, unit=unit,
                      Note='Clock repeaters (U12 BCK/LRCK, U14A SCKI): a power cable on the header shorts only a '
                           'buffer output through 150R (22 mA, within the 50 mA rating)'))
        c.append(two(rser, 'R', '150', 'R0603', (DX + 22.86, y), f'_{dst}_D', dst,
                     Note=f'Series termination ~ ribbon impedance, short-circuit limit: {note}'))
    c.append(part('U14', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (DX, LY + 81.28), 0, {'3': 'GND', '4': None}, unit=2,
                  Note='Spare buffer (was the bus-data driver): input to GND, output open'))

    # ---- Op-amp / logic supply units and decoupling
    c.append(part('U5', 'OPA1679', 'OPA1679', 'SOIC14', (40.64, PU_Y), 0, {'4': '+5VA', '11': 'GND'}, unit=5))
    c.append(part('U6', 'OPA1679', 'OPA1679', 'SOIC14', (76.2, PU_Y), 0, {'4': '+5VA', '11': 'GND'}, unit=5))
    c.append(part('U7', 'OPA1679', 'OPA1679', 'SOIC14', (111.76, PU_Y), 0, {'4': '+12V_F', '11': '-12V_F'}, unit=5))
    c.append(part('U8', 'OPA1678', 'OPA1678', 'SOIC8', (302.26, PU_Y), 0, {'8': '+12V_F', '4': '-12V_F'}, unit=3))
    c.append(part('U4', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (162.56, PU_Y), 0, {'5': '+3V3_C', '2': 'GND'}, unit=3))
    c.append(part('U12', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (187.96, PU_Y), 0, {'5': '+3V3_C', '2': 'GND'}, unit=3))
    c.append(part('U13', '74LVC2G125', 'SN74LVC2G125', 'SSOP8', (226.06, PU_Y), 0, {'8': '+3V3_C', '4': 'GND'}, unit=3))
    c.append(part('U14', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (264.16, PU_Y), 0, {'5': '+3V3_C', '2': 'GND'}, unit=3))
    for ref, xx, a_, b_, note in (('C31', 53.34, '+5VA', 'GND', 'U5 V+'), ('C32', 88.9, '+5VA', 'GND', 'U6 V+'),
                                  ('C33', 124.46, '+12V_F', 'GND', 'U7 V+'), ('C34', 137.16, 'GND', '-12V_F', 'U7 V-'),
                                  ('C35', 314.96, '+12V_F', 'GND', 'U8 V+'), ('C36', 327.66, 'GND', '-12V_F', 'U8 V-'),
                                  ('C45', 200.66, '+3V3_C', 'GND', 'U12 supply'),
                                  ('C46', 238.76, '+3V3_C', 'GND', 'U13 supply'),
                                  ('C47', 276.86, '+3V3_C', 'GND', 'U14 supply')):
        c.append(two(ref, 'C', '100n', 'C0603', (xx, PU_Y), a_, b_, rot=0, Voltage='50V', Note=f'{note} decoupling'))

    # ---- MCU board strips, I2C pull-ups, BOOT/RESET, SWD
    hx, hy = HDR
    strip = 'MCU board strip: soldered here (plastic on the F side) and through the MCU board. Hand-soldered'
    c.append(part('J12', 'Conn_01x12', 'MCU_L', 'H1x12', HDR, 0,
                  {'1': 'BOOT0', '2': 'NRST', '3': '+3V3', '4': 'GND', '5': 'I2S_ADC1', '6': 'CODEC_RST',
                   '7': 'POT_ADC', '8': 'MUX_S0', '9': 'MUX_S1', '10': 'MUX_S2', '11': 'MUX_S3', '12': 'LINK_N'},
                  MPN='2.54 mm 1x12 male pin header (2.5 mm plastic)',
                  Note=f'J112 on the MCU board (boot/reset, DOUT1, codec reset, pot mux, clock-link detect). {strip}'))
    c.append(part('J13', 'Conn_01x12', 'MCU_R', 'H1x12', (hx + 30.48, hy), 0,
                  {'1': 'SWCLK', '2': 'SWDIO', '3': '+3V3', '4': 'GND', '5': 'I2S_DAC1', '6': 'I2C_SCL',
                   '7': 'I2C_SDA', '8': 'GND', '9': 'I2S_SCLK', '10': 'I2S_LRCK', '11': 'GND', '12': 'NORM_PROBE'},
                  MPN='2.54 mm 1x12 male pin header (2.5 mm plastic)',
                  Note=f'J113 on the MCU board, east of the codec (SWD, DIN1, I2C, BCK/LRCK, probe). {strip}'))
    # I2C pull-ups: R108/R109 on the MCU board (S2, were R18/R19 here).
    c.append(part('SW1', 'SW_Push', 'RESET', 'SWK2', (hx, hy + 55.88), 0, {'1': 'NRST', '2': 'GND'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='CH32V307 reset (B side, reachable with the module out of the rack)'))
    c.append(part('SW2', 'SW_Push', 'BOOT', 'SWK2', (hx, hy + 68.58), 0, {'1': 'BOOT0', '2': '+3V3'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='Hold BOOT, press RESET: ROM bootloader on the USB-C (PB6/PB7), flash with wchisp/WCHISPTool'))
    # DIN1 series termination: R110 33R on the MCU board, at the source (S2, was R65 here).
    c.append(part('J15', 'Conn_01x04', 'SWD', 'H1x4', (hx + 45.72, hy + 63.5), 0,
                  {'1': '+3V3', '2': 'SWDIO', '3': 'SWCLK', '4': 'GND'},
                  Note='WCH-LinkE debug (SWDIO/SWCLK). Optional, hand-soldered, B side'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # Power entry (modules/usb-audio-max, J1 -> J8)
    W += [['J8.1', (33.02, 60.96), (33.02, 55.88), (50.8, 55.88), (50.8, 60.96), 'J8.2'], [(50.8, 55.88), 'D1.1'],
          ['J8.3', (33.02, 63.5), (33.02, 68.58), 'J8.7'], ['J8.5', (33.02, 66.04)], [(33.02, 68.58), (27.94, 68.58)],
          ['J8.4', (50.8, 63.5), (50.8, 68.58), 'J8.8'], ['J8.6', (50.8, 66.04)], [(50.8, 68.58), (53.34, 68.58)],
          ['J8.9', (33.02, 71.12), (33.02, 76.2), (50.8, 76.2), (50.8, 71.12), 'J8.10'], [(50.8, 76.2), 'D2.2'],
          ['D1.2', (86.36, 55.88)]]
    P += [('-12V', (55.88, 55.88), 0), ('GND', (27.94, 68.58), 0), ('GND', (53.34, 68.58), 90),
          ('+12V', (55.88, 76.2), 0), ('-12V_F', (86.36, 55.88), 0), ('+12V_F', (88.9, 76.2), 0)]
    W += [['D2.1', 'R1.1'], [(92.71, 76.2), (92.71, 68.58), 'R2.1'], ['R2.2', (105.41, 68.58), (105.41, 76.2)],
          ['R1.2', 'Q1.2'], ['Q1.4', 'Q1.2'], ['Q1.3', 'R8.1'], ['Q2.1', (134.62, 76.2)],
          ['R8.2', (175.26, 76.2)], ['Q2.2', (146.05, 88.9), (146.05, 76.2)],
          ['Q2.3', (124.46, 88.9)], ['Q1.1', (124.46, 101.6)], ['R9.2', (124.46, 101.6)],
          ['U1.1', 'R9.1'], [(110.49, 101.6), (110.49, 111.76), 'R16.2'], ['R16.1', 'C37.2'],
          ['U1.2', (88.9, 104.14), (88.9, 111.76), 'C37.1'], [(88.9, 104.14), 'R7.2'],
          ['U1.3', (88.9, 99.06)],
          ['U1.6', (152.4, 106.68), (152.4, 111.76), (172.72, 111.76), (172.72, 104.14), 'U1.7']]
    P += [('+5VA', (175.26, 76.2), 0)]
    W += [['U9.6', 'R6.1'], ['U9.5', (218.44, 73.66), 'C17.1'], ['R6.2', (260.35, 68.58)]]
    L += [('REF_NR', 'C17.1', 'L')]  # named (fab review): no escaped '/' in the auto net name
    L += [('V5_SET', (260.35, 68.58), 'R'), ('V5_SET', (88.9, 99.06), 'L'), ('V5_IN', (116.84, 76.2), 'U')]
    xu, yr = BUCK
    ys = yr - 5.08
    W += [[(95.25, yr - 2.54), (95.25, yr), 'FB2.1'], ['FB2.2', 'R3.1'], ['R3.2', 'U2.3'],
          ['R4.1', (xu - 19.05, yr)], ['R4.2', 'U2.5'],
          ['U2.2', (xu + 12.7, yr), (xu + 12.7, ys), 'C4.1', 'L1.1'], ['U2.6', 'C4.2'],
          ['U2.4', 'R20.1', 'R5.1'], ['R5.2', (xu + 38.1, ys)],
          ['L1.2', 'FB1.1'], [(xu + 68.58, ys), (xu + 68.58, ys - 2.54)],
          ['FB1.2', 'R21.1'], [(xu + 88.9, ys), (xu + 88.9, ys - 2.54)],
          ['R21.2', 'C43.1', (xu + 110.49, ys), (xu + 110.49, ys - 2.54)]]
    P += [('+12V_F', (95.25, yr - 2.54), 0), ('+3V3', (xu + 68.58, ys - 2.54), 0),
          ('+3V3_C', (xu + 88.9, ys - 2.54), 0), ('+3V3_OSC', (xu + 110.49, ys - 2.54), 0)]
    L += [('V3_IN', (124.46, yr), 'U')]

    # Codec unit 1 (analog): VIN- bus to VCOM_REF
    xa, ya = COD_A
    lx = xa - 17.78
    vin_m = [ya - 5.08 + 2.54 * i for i in range(6)]
    for yy in vin_m:
        W += [[(lx, yy), (lx - 5.08, yy)]]
    W += [[(lx - 5.08, vin_m[0]), (lx - 5.08, vin_m[-1]), (lx - 10.16, vin_m[-1])]]
    L += [('VCOM_REF', (lx - 10.16, vin_m[-1]), 'L')]
    # Codec unit 2 (interface)
    xd, yd = COD_D
    W += [['U3.7', 'U4.3'], ['U3.36', (xd - 22.86, yd - 17.78), (xd - 22.86, yd - 20.32)],
          ['U3.6', 'U4.1'], ['U3.35', (xd - 22.86, yd - 2.54), (xd - 22.86, yd - 5.08)],
          ['U4.4', 'R11.2'], ['U4.6', 'R12.2'], ['R11.1', (xd - 73.66, yd - 20.32)],
          ['R12.1', (xd - 73.66, yd - 5.08)],
          ['U3.8', 'R13.2'], ['R13.1', (xd - 40.64, yd + 10.16)],
          ['U3.41', 'R60.1'], ['Y1.3', 'R10.1'],
          ['U3.44', 'R15.1'], ['R15.2', (xd + 41.91, yd - 12.7), (xd + 41.91, yd - 10.16)],
          ['U3.4', (xd + 30.48, yd + 7.62)]]
    L += [('I2S_SCLK', (xd - 73.66, yd - 20.32), 'L'), ('I2S_LRCK', (xd - 73.66, yd - 5.08), 'L'),
          ('BCK_C', (xd - 27.94, yd - 20.32), 'U'), ('LRCK_C', (xd - 27.94, yd - 5.08), 'U'),
          ('BCK_B', (xd - 60.96, yd - 20.32), 'U'), ('LRCK_B', (xd - 60.96, yd - 5.08), 'U'),
          ('I2S_ADC1', (xd - 40.64, yd + 10.16), 'L'), ('CODEC_RST', (xd + 30.48, yd + 7.62), 'R'),
          ('CODEC_ADR1', 'R15.1', 'L')]  # named (fab review): no escaped '/' in the auto net name
    P += [('GND', (xd + 41.91, yd - 10.16), 0)]

    # Inputs
    for n, y in zip(IN_CH, IN_Y):
        x0 = IN_X0
        u, k = IN_AMP[n]
        up, um, uo = OPA4[k]
        j, tip = IN_JACK[n][:2]
        cin, rin, rf, cf, rs = f'C{220 + n}', f'R{200 + n}', f'R{210 + n}', f'C{200 + n}', f'R{220 + n}'
        xm, xr = x0 + 40.64, x0 + 60.96           # - input column, feedback return column
        W += [[f'{j}.T', f'{cin}.1'], [f'{cin}.2', f'{rin}.1'], [f'{rin}.2', f'{u}.{um}'],
              [(xm, y), (xm, y + 5.08), f'{rf}.1'], [f'{rf}.2', (xr, y + 5.08), (xr, y - 2.54)],
              [(xm, y + 5.08), (xm, y + 12.7), f'{cf}.1'], [f'{cf}.2', (xr, y + 12.7), (xr, y + 5.08)],
              [f'{u}.{uo}', f'{rs}.1'], [f'{rs}.2', (x0 + 83.82, y - 2.54)],
              [f'{j}.TN', (x0 + 7.62, y - 2.54), (x0 + 7.62, y - 5.08)],
              [f'{j}.S', (x0 + 7.62, y + 2.54), (x0 + 7.62, y + 5.08)]]
        P += [('GND', (x0 + 7.62, y + 5.08), 0)]
        L += [(tip, (x0 + 10.16, y), 'U'), ('NORM', (x0 + 7.62, y - 5.08), 'U'),
              (f'ADC_IN{n}', (x0 + 83.82, y - 2.54), 'R')]
    W += [['R63.2', (66.04, NORM_Y)]]
    L += [('NORM', (66.04, NORM_Y), 'R')]

    # Outputs
    for n, y in zip(OUT_CH, OUT_Y):
        xo = OUT_X0
        u, k = OUT_AMP[n]
        up, um, uo = amp_pins(u, k)
        rm, rp, rf, cf = f'R{300 + n}', f'R{310 + n}', f'R{320 + n}', f'C{300 + n}'
        ro, ro2, j = f'R{340 + n}', f'R{350 + n}', OUT_JACK[n][0]
        W += [[(xo - 43.18, y - 2.54), f'{rm}.1'], [f'{rm}.2', f'{u}.{um}'],
              [(xo - 43.18, y + 2.54), f'{rp}.1'], [f'{rp}.2', f'{u}.{up}'],
              [(xo - 10.16, y - 2.54), (xo - 10.16, y - 10.16), f'{rf}.1'],
              [f'{rf}.2', (xo + 10.16, y - 10.16), (xo + 10.16, y)],
              [(xo - 10.16, y - 10.16), (xo - 10.16, y - 17.78), f'{cf}.1'],
              [f'{cf}.2', (xo + 10.16, y - 17.78), (xo + 10.16, y - 10.16)],
              [f'{u}.{uo}', f'{ro}.1'], [(xo + 12.7, y), (xo + 12.7, y + 7.62), f'{ro2}.1'],
              [f'{ro2}.2', (xo + 24.13, y + 7.62), (xo + 24.13, y)], [f'{ro}.2', f'{j}.T'],
              [f'{j}.S', (xo + 26.67, y + 2.54), (xo + 26.67, y + 12.7)]]
        P += [('GND', (xo + 26.67, y + 12.7), 0)]
        L += [(f'DAC{n}N', (xo - 43.18, y - 2.54), 'L'), (f'DAC{n}P', (xo - 43.18, y + 2.54), 'L'),
              (OUT_JACK[n][1], (xo + 25.4, y), 'U')]
    xo, yo = U7D_AT
    W += [['U7.14', (xo + 10.16, yo), (xo + 10.16, yo + 7.62), (xo - 10.16, yo + 7.62),
           (xo - 10.16, yo + 2.54), 'U7.13']]

    # VCOM reference and spare U6D
    y0, y1 = REF_Y
    W += [['U6.8', 'R50.1'], [(86.36, y0), (86.36, y0 + 7.62), (66.04, y0 + 7.62), (66.04, y0 + 2.54), 'U6.9'],
          ['R50.2', (121.92, y0)],
          ['U6.14', (91.44, y1), (91.44, y1 + 7.62), (71.12, y1 + 7.62), (71.12, y1 + 2.54), 'U6.13']]
    L += [('VCOM_REF', (121.92, y0), 'R')]

    # Pots: wiper -> filter cap -> label
    for i, (ref, wiper, _) in enumerate(POTS):
        px, py = POT_X[i % 5], POT_Y[i // 5]
        W += [[f'{ref}.2', (px + 17.78, py)]]
        L += [(wiper, (px + 17.78, py), 'R')]
    # Mux COM, pot supply filter
    W += [['U10.1', 'R61.2'], ['R62.2', 'C48.1', (MX + 15.24, MY + 38.1), (MX + 15.24, MY + 35.56)]]
    P += [('+3V3_POT', (MX + 15.24, MY + 35.56), 0)]
    W += [['R65.2', 'C50.1', (MX + 15.24, MY + 55.88), (MX + 15.24, MY + 53.34)]]
    P += [('+3V3_POTB', (MX + 15.24, MY + 53.34), 0)]

    # Clock link
    for hy_ in (LY, LY + 50.8):
        j = 'J7' if hy_ == LY else 'J6'
        W += [[f'{j}.3', (LX - 10.16, hy_ - 2.54)], [f'{j}.5', (LX - 7.62, hy_), (LX - 7.62, hy_ - 2.54)]]
        P += [('GND', (LX - 10.16, hy_ - 2.54), 270)]
    W += [['J7.1', 'R83.2'], ['R83.1', (LX - 38.1, LY - 5.08)], ['J6.1', 'R82.2']]
    L += [('LINK_N', (LX - 38.1, LY - 5.08), 'L')]
    W += [['U13.6', 'R74.1'], ['U13.3', 'R75.1']]
    for ref, pin_out, rser, y in (('U14', '6', 'R72', LY + 30.48), ('U12', '6', 'R70', LY + 45.72),
                                  ('U12', '4', 'R71', LY + 60.96)):
        W += [[f'{ref}.{pin_out}', f'{rser}.1']]

    # MCU strips: supply pins with their rails drawn by the stubs
    return W, P, L


# JLCPCB parts: modules/usb-audio-max's (live-checked 2026-11-05) plus this module's new codes (live
# lookups 2026-11-09, docs/research.md section 6). Jacks, pots, headers and strips are hand-soldered.
SOURCING = {
    ('R', '33', 'R0603'): dict(LCSC='C23140', MPN='0603WAF330JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '47', 'R0603'): dict(LCSC='C23182', MPN='0603WAF470JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '150', 'R0603'): dict(LCSC='C22808', MPN='0603WAF1500T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '470', 'R0603'): dict(LCSC='C23179', MPN='0603WAF4700T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '15k', 'R0603'): dict(LCSC='C22809', MPN='0603WAF1502T5E', Manufacturer='UNI-ROYAL'),
    ('R', '20k', 'R0603'): dict(LCSC='C4184', MPN='0603WAF2002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '27k', 'R0603'): dict(LCSC='C22967', MPN='0603WAF2702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '33k', 'R0603'): dict(LCSC='C4216', MPN='0603WAF3302T5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100k', 'R0603'): dict(LCSC='C25803', MPN='0603WAF1003T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10', 'R0603'): dict(LCSC='C22859', MPN='0603WAF100JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '2.2', 'R1206'): dict(LCSC='C144499', MPN='AC1206FR-072R2L', Manufacturer='YAGEO'),
    ('R', '2k', 'R1206'): dict(LCSC='C17944', MPN='1206W4F2001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '33', 'R2512'): dict(LCSC='C53728', MPN='25121WF330JT4E', Manufacturer='UNI-ROYAL'),
    ('C', '47p', 'C0603'): dict(LCSC='C1671', MPN='CL10C470JB8NNNC', Manufacturer='Samsung'),
    ('C', '2.2n', 'C0603'): dict(LCSC='C33353', MPN='CL10C222JB8NNNC', Manufacturer='Samsung'),
    ('C', '22n', 'C0603'): dict(LCSC='C21122', MPN='CL10B223KB8NNNC', Manufacturer='Samsung'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0603'): dict(LCSC='C15849', MPN='CL10A105KB8NNNC', Manufacturer='Samsung'),
    ('C', '1u', 'C0402'): dict(LCSC='C52923', MPN='CL05A105KA5NQNC', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C1206'): dict(LCSC='C13585', MPN='CL31A106KBHNNNE', Manufacturer='Samsung'),
    ('C', '22u', 'C0805'): dict(LCSC='C45783', MPN='CL21A226MAQNNNE', Manufacturer='Samsung'),
    ('FerriteBead', 'GZ2012D121TF', 'C0805'): dict(LCSC='C5671', MPN='GZ2012D121TF', Manufacturer='Sunlord'),
    ('L', '4.7u', 'MWSA0402S'): dict(LCSC='C408337', MPN='MWSA0402S-4R7MT', Manufacturer='Sunlord'),
    ('TPS562208', 'TPS562208', 'SOT23-6'): dict(LCSC='C91301', MPN='TPS562208DDCR', Manufacturer='Texas Instruments'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('LM358', 'LM358', 'SOIC8'): dict(LCSC='C7950', MPN='LM358DR2G', Manufacturer='onsemi'),
    ('BCP56', 'BCP56-16', 'SOT223'): dict(LCSC='C92221', MPN='BCP56-16,115', Manufacturer='Nexperia'),
    ('MMBT3904', 'MMBT3904', 'SOT23'): dict(LCSC='C20526', MPN='MMBT3904', Manufacturer='CJ (Jiangsu Changjing)'),
    ('REF5050AD', 'REF5050A', 'SOIC8'): dict(LCSC='C27804', MPN='REF5050AIDR', Manufacturer='Texas Instruments'),
    ('PCM3168A', 'PCM3168A', 'TQFP64EP'): dict(LCSC='C529289', MPN='PCM3168APAPR', Manufacturer='Texas Instruments'),
    ('74LVC2G34', 'SN74LVC2G34', 'SC70-6'): dict(LCSC='C14461', MPN='SN74LVC2G34DCKR', Manufacturer='Texas Instruments'),
    ('74LVC2G125', 'SN74LVC2G125', 'SSOP8'): dict(LCSC='C206035', MPN='SN74LVC2G125DCTR',
                                                  Manufacturer='Texas Instruments'),
    ('74LVC1G97', '74LVC1G97', 'SC70-6'): dict(LCSC='C460532', MPN='74LVC1G97DW-7', Manufacturer='Diodes Incorporated'),
    ('74HC4067', '74HC4067PW', 'TSSOP24'): dict(LCSC='C179326', MPN='74HC4067PW,118', Manufacturer='Nexperia'),
    ('BAT54S', 'BAT54S', 'SOT23'): dict(LCSC='C47546', MPN='BAT54S,215', Manufacturer='Nexperia'),
    ('OPA1679', 'OPA1679', 'SOIC14'): dict(LCSC='C2878631', MPN='OPA1679IDR', Manufacturer='Texas Instruments'),
    ('OPA1678', 'OPA1678', 'SOIC8'): dict(LCSC='C192421', MPN='OPA1678IDR', Manufacturer='Texas Instruments'),
    ('ASE-xxxMHz', '24.576MHz', 'OSC3225'): dict(LCSC='C5203547', MPN='OT2EL4C4JI-111OLP-24.576M',
                                                 Manufacturer='YXC'),
    ('SW_Push', 'RESET', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('SW_Push', 'BOOT', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR MULTI-MIX - carrier (jack board), S3. Digital 4-channel mixer: 4 IN + 2 RETURN, SEND A / SEND B / '
                     'MAIN OUT, 15 knobs read by the MCU (MIDI CC), USB audio + MIDI, PCM3168A at 48 kHz, clock link. '
                     'Circuit intent: docs/research.md', 2.0),
    ((20.32, 33.02), 'POWER (as modules/usb-audio-max): +12V -> D2 -> +12V_F (output op-amps; R1||R2 16.5R -> Q1 BCP56 (U1A LM358 loop, '
                     'ref U9 REF5050) -> +5VA; FB2 + R3 -> U2 TPS562208 FCCM buck -> L1 -> +3V3 -> FB1 -> +3V3_C -> R21 -> '
                     '+3V3_OSC); -12V -> D1 -> -12V_F. +12 V ~0.32 A max, -12 V ~10 mA.', 1.4),
    ((185.42, 45.72), 'DC REFERENCE (kept from modules/usb-audio-max): +5VA sets the codec gain (DAC 1.6 x VCC, ADC 0.2 x VCC):\n'
                      'U9 REF5050A -> R6 10k / C19 1u -> V5_SET -> U1A LM358 -> R9 -> Q1 BCP56 -> R8 -> +5VA;\n'
                      'R7 10k senses +5VA at the codec; C37 22n + R16 47k = PI compensation. Q2 limits at ~0.3-0.35 A.', 1.1),
    ((20.32, 116.84), '+3V3 BUCK, kept out of the audio:\n'
                      '- only the digital rail is switched; +5VA stays linear\n'
                      '- U2 is the FCCM TPS562208: fixed ~580 kHz at every load\n'
                      '  (TPS562201 pulse-skips into the audio band: do not substitute)\n'
                      '- FB2 + R3 2.2R + C6/C7 keep its switching current off +12V_F\n'
                      '- L1 molded; FB1 filters the codec VDD / clock logic, R21/C43 Y1', 1.1),
    ((20.32, 154.94), 'PWR_FLAG: GND/+12V/-12V at J8; +12V_F/-12V_F behind D2/D1; V5_IN behind R1||R2; V3_IN behind FB2 + R3; +3V3 behind L1; '
                      '+5VA at R8; +3V3_C behind FB1; +3V3_OSC behind R21; +3V3_POT behind R62.', 1.1),
    ((330.2, 39.37), 'PCM3168A at 48 kHz: I2C 0x44 (MODE = DGND, ADR0 = GND, ADR1 10k to GND). SCKI 24.576 MHz = 512 fS, single-rate 24-bit\n'
                    'I2S-mode TDM, BCK 256 fS = 12.288 MHz: DOUT1 = ADC1-6, DIN1 = DAC1-8 (DOUT2 open, DIN2-4 GND).\n'
                    'DAC slots: VOUT5 SEND A, VOUT3 SEND B, VOUT4 MAIN, VOUT1 USB 1, VOUT2 USB 2 (net DACn = output n).\n'
                    'Stand-alone / chain master: ADC = clock master, DAC slave on the tied BCK/LRCK. Clock slave (LINK_N low):\n'
                    'ADC + DAC slaves, U11 feeds the link SCKI, U13 the link BCK/LRCK. Firmware: SEAD = 1, REVAD = 1.', 1.1),
    ((20.32, 167.64), 'INPUTS (x6: CH1-4, RTN A/B): jack (TN = NORM) -> 10u -> 100k -> inverting driver on +5VA (-0.2, + at VCOM_REF)\n'
                      '-> 470R / 2.2n C0G -> VINn+ (single-ended). +/-7.07 V = 1 Vrms ADC full scale. 100k, AC-coupled (modules/4mix D3).', 1.1),
    ((20.32, 350.52), 'NORM: all six jack normals on one node; NORM_PROBE (PA8) pseudo-random bits via 100k/1k = 33 mV: the firmware\n'
                      'correlates it in each ADC channel to tell patched from unpatched (RTN A/B unpatched -> returns from USB).', 1.1),
    ((246.38, 142.24), 'OUTPUTS (x5): DAC1 SEND A (J1, VOUT5), DAC2 SEND B (J2, VOUT3), DAC3 MAIN OUT (J5, VOUT4) on U7A-C; DAC4 USB 1\n'
                       '(J9, VOUT1), DAC5 USB 2 (J10, VOUT2) on U8 (host-assigned outs, bottom right); VOUT6-8 open. Difference amplifier on +/-12 V (15k / 27k || 47p,\n'
                       'gain 1.8) -> 2k || 2k (1k / 0.5 W) -> jack. Full scale +/-7.2 V.', 1.1),
    ((20.32, 375.92), 'VCOM (+5VA): U6C buffers VCOMAD -> 100R / 10u -> VCOM_REF (VIN1-6 - and the driver + inputs). U6D, U7D spare.', 1.1),
    ((360.68, 424.18), 'KNOBS: 15 x RV09 50k B (modules/4mix references) as DC dividers on +3V3_POT; nothing on them carries audio.\n'
                       'Wiper 100n -> U10 74HC4067 (I0-I14, I15 = GND) -> R61 1k -> POT_ADC (MCU PC1 = ADC_IN11); S0-S3 = PC2, PC3, PA0, PA1.\n'
                       'The firmware scans them, smooths with hysteresis and sends MIDI CC (VOL as CC7 per channel).', 1.1),
    ((459.74, 185.42), 'CLOCK LINK (keyed 2x5 IDC daisy chain, straight ribbon CLK OUT -> next unit CLK IN; master = the unit with CLK IN open):\n'
                       '1 DET | 2 NC | 3 GND | 4 SCKI | 5 GND | 6 BCK | 7 LRCK | 8 GND | 9 NC | 10 NC  (Eurorack power cable safe)\n'
                       'Clock only (sample-locked USB multitrack): each unit keeps its own USB and outputs. Up to 4 units until bench-tested.\n'
                       'LINK_N low (CLK IN connected) = clock slave: U11 takes SCKI and U13 BCK/LRCK from the link, by hardware;\n'
                       'U14A/U12 repeat them out of CLK OUT to the next unit.', 1.1),
    ((579.12, 50.8), 'MCU BOARD LINK: J12/J13 1x12 2.54 mm male strips (plastic on the carrier F side);\n'
                     'the MCU board (multi-mix-mcu, J112/J113) solders on top. BOOT/RESET and SWD on the carrier (B side):\n'
                     'hold BOOT, press RESET = CH32V307 ROM bootloader on the USB-C. I2C pull-ups are on the MCU board.', 1.1),
]

TEXT_LEFT = {'C3', 'C17', 'C19', 'R20', 'R84'}
TEXT_POS = {'U1': ((3.81, -6.35), (3.81, -3.81), 'left'), 'U1/2': ((3.81, -6.35), (3.81, -3.81), 'left'),
            'U1/3': ((1.27, -1.27), (1.27, 1.27), 'left'),
            'Q1': ((-7.62, 12.7), (-7.62, 15.24)), 'Q2': ((2.54, 6.35), (2.54, 8.89), 'left'),
            'U2': ((-7.62, -8.89), (-7.62, -6.35), 'left'), 'R4': ((0, -2.54), (0, 2.54)),
            'FB1': ((0, -3.81), (0, 3.81)), 'FB2': ((0, -3.81), (0, 3.81)), 'U9': ((2.54, -8.89), (2.54, -6.35), 'left'),
            'U5/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U6/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U7/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U8/3': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U4/3': ((-6.35, -1.27), (-6.35, 1.27), 'right'), 'U12/3': ((-6.35, -1.27), (-6.35, 1.27), 'right'),
            'U13/3': ((-6.35, -1.27), (-6.35, 1.27), 'right'), 'U14/3': ((-6.35, -1.27), (-6.35, 1.27), 'right'),
            'U4': ((-1.27, -10.16), (-1.27, -7.62)), 'U4/2': ((-1.27, 8.89), (-1.27, 11.43)),
            'U3': ((-12.7, -27.94), (12.7, -27.94)), 'U3/2': ((-22.86, -30.48), (-22.86, -27.94)),
            'Y1': ((-10.16, -6.35), (-10.16, -3.81), 'right'),
            'SW1': ((0, -3.81), (0, 3.81)), 'SW2': ((0, -3.81), (0, 3.81)),
            'J12': ((0, -16.51), (0, 19.05)), 'J13': ((0, -16.51), (0, 19.05)),
            'J15': ((0, -6.35), (0, 8.89)), 'J6': ((1.27, -8.89), (1.27, 8.89)), 'J7': ((1.27, -8.89), (1.27, 8.89)),
            'U10': ((5.08, -30.48), (5.08, -27.94), 'left'), 'U11': ((5.08, -13.97), (5.08, 13.97), 'left'),
            'U13': ((3.81, -11.43), (3.81, 6.35), 'left'), 'U13/2': ((3.81, -11.43), (3.81, 6.35), 'left'),
            'U12': ((-1.27, -6.35), (-1.27, 6.35)), 'U12/2': ((-1.27, -6.35), (-1.27, 6.35)),
            'U14': ((-1.27, -6.35), (-1.27, 6.35)), 'U14/2': ((-1.27, -6.35), (-1.27, 6.35)),
            'R82': ((0, -5.08), (0, -2.54)), 'R83': ((0, -5.08), (0, -2.54)),
            'D3': ((0, 3.81), (0, 6.35)),
            'U7/4': ((0, 7.62), (0, 10.16)), 'U6/4': ((3.81, -6.35), (3.81, -3.81), 'left')}
# Op-amp unit texts: input drivers / references above-right of the triangle, output stages below it.
TEXT_POS.update({f'{u}/{k}' if k > 1 else u: ((3.81, -6.35), (3.81, -3.81), 'left')
                 for u, k in list(IN_AMP.values()) + [('U6', 3)]})
TEXT_POS.update({f'{u}/{k}' if k > 1 else u: ((0, 7.62), (0, 10.16)) for u, k in OUT_AMP.values()})
TEXT_POS.update({ref: ((-2.54, -6.35), (-2.54, 6.35), 'right') for ref, _, _ in POTS})

MULTI_UNIT = {'U1': {1, 2, 3}, 'U3': {1, 2}, 'U4': {1, 2, 3}, 'U5': {1, 2, 3, 4, 5}, 'U6': {1, 2, 3, 4, 5},
              'U7': {1, 2, 3, 4, 5}, 'U8': {1, 2, 3}, 'U12': {1, 2, 3}, 'U13': {1, 2, 3}, 'U14': {1, 2, 3}}
