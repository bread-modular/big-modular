"""USB-AUDIO-MAX carrier (jack board) S2 circuit table, drawing and sourcing (tools/build_schematic.py).

CIRCUIT is docs/research.md section 3. 6 in / 8 out, DC-coupled, no level controls, up to 96 kHz:

- Power: Eurorack 10-pin +/-12 V -> B5819W series Schottkys -> +12V_F / -12V_F (output op-amps);
  +12V_F -> R1 || R2 (2 x 33R 2512 = 16.5R) -> discrete regulator (U1A LM358 + Q1 BCP56) -> +5VA
  (PCM3168A VCC, input op-amps);
  +12V_F -> FB2 + R3 2.2R (input filter) -> V3_IN -> U2 TPS562208 buck -> L1 4.7u -> +3V3 (MCU board,
  I2C pull-ups) -> FB1 -> +3V3_C (PCM3168A VDD, clock buffer) -> R21 10R -> +3V3_OSC (Y1). ~250 mA max
  on +3V3 (user, 2026-11-05: buck, kept away from the audio). Only the digital rail is switched: the
  TPS562208 is the FCCM variant (forced continuous conduction: it never skips pulses, so it switches at
  a fixed ~580 kHz at any load, with no audio-band bursts); FB2 + R3 with C6/C7 keep its input ripple off
  +12V_F (output op-amps, the +5VA regulator, U9); L1 is a molded (shielded) inductor; FB1 and R21/C43
  filter the codec VDD and the clock oscillator. ngspice (docs/research.md D7): ~50 uV rms on +12V_F,
  ~0.1 uV on +5VA, ~0.06 mV on +3V3_C; USB load bursts at 8 kHz put about as much on +12V_F as the
  S1.2 linear +3V3 did (~-142 dBFS at the jacks either way).
- +5VA is the DC reference of every channel: the DAC full scale is 1.6 x VCC and the ADC full scale
  0.2 x VCC, so +5VA sets the gain of all DC/CV paths. U9 REF5050A (0.1 %, 8 ppm/C max) -> R6 10k ->
  V5_SET (C19 1u: 16 Hz filter, 10 ms soft start) -> U1A LM358 + input. U1A drives the Q1 BCP56
  emitter follower through R9 150R; R8 2.2R in the emitter with Q2 MMBT3904 limits the current to
  ~0.3-0.35 A. Feedback R7 10k from +5VA (Kelvin at the codec), PI compensation C37 22n + R16 47k
  (integrator for zero DC error, proportional gain 4.7 for a low output impedance). +5VA = V5_SET +
  the LM358 offset (calibrated out). Replaces the LT3045 (S1 D11) at ~$1.2 instead of ~$8.9; an
  AMS1117 drifts 0.5 % over temperature and 0.3 % per 1000 h (typ), which calibration cannot remove.
- Codec: U3 PCM3168A, I2C control (MODE = DGND), address 0x44 (ADR1 = ADR0 = 0). Y1 24.576 MHz on
  SCKI: 256 fS at 96 kHz (dual rate), 512 fS at 48 kHz (single rate). The ADC is the clock master in
  24-bit I2S-mode TDM (BCK = 128 fS at 96 kHz / 256 fS at 48 kHz = 12.288 MHz both); BCKDA/LRCKDA are
  tied to BCKAD/LRCKAD, so the DAC is a slave on the same clocks. 96 kHz: DOUT1 = ADC1-4,
  DOUT2 = ADC5-6, DIN1 = DAC1-4, DIN2 = DAC5-8; 48 kHz: DOUT1 = ADC1-6, DIN1 = DAC1-8.
  U4 74LVC2G34 buffers BCK/LRCK to the MCU board (codec master outputs: 20 pF max load).
- Inputs (x6): jack (TN to GND: unpatched = 0 V) -> 100k -> U5/U6 inverting driver on +5VA
  (gain -24k/100k = -0.24, + input at VB_IN = VCOM x 100/124 so 0 V in = VCOM) -> 470R / 2.2n C0G
  -> VINn+. ADC single-ended mode (SEAD = 1), full scale 0.2 x VCC Vrms = +/-1.414 V -> +/-5.89 V at
  the jack; HPF bypassed (BYP = 111) for DC; firmware restores the polarity (REVAD) and calibrates
  the offset. VINn- = VCOM_REF (buffered VCOMAD). 100k input; the 5 V driver keeps VIN within
  0..5 V for any +/-12 V patch (inverting input stays at 1.7..2.4 V).
- Outputs (x8): VOUTn+/VOUTn- (differential, centred on VCOMDA, 1.6 x VCC = 8 Vpp full scale) ->
  U7/U8 difference amplifier on +/-12 V (15k in, 22k feedback || 47p, gain 1.467, pole 154 kHz):
  common mode removed, so 0 V out at mid-scale with no coupling capacitor; full scale +/-5.87 V
  (matches the input's +/-5.89 V). Each DAC pin sees >= 15k (datasheet DC-coupled minimum for this
  gain: 14.1k). -> 2 x 2k 1206 in parallel (1k, 0.5 W) -> jack.
- References on +5VA: U6C buffers VCOMAD (10k source, 1 uA max) -> VCOM_BUF -> 100R / 10u -> VCOM_REF
  (VINn-); VCOM_BUF -> 24k / 100k -> U6D -> VB_IN. VB_IN tracks the codec's own mid-rail.
- MCU board link: J2/J3 1x10 2.54 mm pin headers. BOOT/RESET (SW2/SW1) and the SWD header J4 sit on
  the carrier, as modules/usb-audio.
"""

PAPER = 'A1'

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', '+3V3': '+3V3', '+3V3_C': '+3V3', '+3V3_OSC': '+3V3', '+5VA': '+5VA',
               '+12V': '+12V', '-12V': '-12V', '+12V_F': '+12V', '-12V_F': '-12V'}

IN_CH = range(1, 7)
OUT_CH = range(1, 9)
IN_JACK = {n: f'J{10 + n}' for n in IN_CH}
OUT_JACK = {n: f'J{20 + n}' for n in OUT_CH}
# Input driver units: channel -> (ref, unit); U6C/U6D are the references.
IN_AMP = {1: ('U5', 1), 2: ('U5', 2), 3: ('U5', 3), 4: ('U5', 4), 5: ('U6', 1), 6: ('U6', 2)}
OUT_AMP = {n: ('U7' if n <= 4 else 'U8', (n - 1) % 4 + 1) for n in OUT_CH}

# Symbols drawn mirrored about X: input jacks (sleeve down) and the output difference amplifiers
# (- input on top for the feedback, + input below with its divider to GND).
MIRROR_X = {IN_JACK[n] for n in IN_CH} | {f'{u}/{k}' for u, k in OUT_AMP.values()} | {'Q2'}

NOT_ASSEMBLED = set()

PWR = (40.64, 66.04)          # J1 (as modules/usb-audio)
COD_A = (198.12, 254.0)       # U3 unit 1 (analog)
COD_D = (431.8, 101.6)        # U3 unit 2 (interface, control, supplies)
IN_X0, IN_Y = 22.86, [190.5 + 27.94 * k for k in range(6)]
OUT_X0, OUT_Y = 299.72, [172.72 + 38.1 * k for k in range(8)]
REF_Y = (393.7, 431.8)        # VCOM buffer / VB_IN buffer rows
HDR = (622.3, 101.6)          # J2; J3 at +30.48
PU_Y = 525.78                 # op-amp supply units row
BUCK = (170.18, 127.0)        # U2 VIN/EN side x + 10.16, V3_IN rail y

# OPA1679 unit pins: unit -> (+, -, out)
OPA4 = {1: ('3', '2', '1'), 2: ('5', '6', '7'), 3: ('10', '9', '8'), 4: ('12', '13', '14')}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=90, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/L/FB: rot 90 = horizontal, pin 1 left; rot 0 = vertical,
    pin 1 on top. Diodes: rot 0 = K left."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def opamp(ref, unit, at, plus, minus, out, **fields):
    p, m, o = OPA4[unit]
    return part(ref, 'OPA1679', 'OPA1679', 'SOIC14', at, 0, {p: plus, m: minus, o: out}, unit=unit, **fields)


def circuit():
    c = []
    # ---- Power entry (as modules/usb-audio): Eurorack +/-12 V -> series Schottkys
    c.append(part('J1', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', PWR, 0,
                  {'1': '-12V', '2': '-12V', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(two('D1', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 55.88), '-12V', '-12V_F', rot=0,
                 Note='-12 V series reverse-polarity protection'))
    c.append(two('D2', 'D_Schottky', 'B5819W', 'SOD123', (63.5, 76.2), '+12V_F', '+12V', rot=180,
                 Note='+12 V series reverse-polarity protection (~0.5 A: 0.23 W)'))
    c.append(two('C2', 'C', '10u', 'C0805', (78.74, 59.69), 'GND', '-12V_F', rot=180, Voltage='25V',
                 Note='-12V_F bulk'))
    c.append(two('C1', 'C', '10u', 'C0805', (78.74, 80.01), '+12V_F', 'GND', rot=0, Voltage='25V',
                 Note='+12V_F bulk'))
    # +5VA: pre-drop pair + discrete regulator (LM358 + BCP56 emitter follower) referenced to a REF5050
    for ref, yy in (('R1', 76.2), ('R2', 68.58)):
        c.append(two(ref, 'R', '33', 'R2512', (99.06, yy), '+12V_F', 'V5_IN', Power='1W',
                     Note='R1 || R2 = 16.5R pre-drop for Q1: 230 mA max -> 3.8 V, 0.44 W each; V5_IN >= 7.1 V at '
                          '11.4 V / 230 mA (Q1 needs >= 5.9 V). +5VA short at the Q2 limit (~0.35 A): ~1.0 W each'))
    c.append(two('C3', 'C', '10u', 'C0805', (109.22, 80.01), 'V5_IN', 'GND', rot=0, Voltage='25V',
                 Note='Q1 collector'))
    c.append(part('Q1', 'BCP56', 'BCP56-16', 'SOT223', (124.46, 78.74), 90,
                  {'1': '_Q1_B', '2': 'V5_IN', '3': '_Q1_E', '4': 'V5_IN'},
                  Note='+5VA pass transistor (emitter follower in the U1A loop). hFE 100-250 at 150 mA. '
                       '<= 0.70 W at 12.6 V (worst load 195 mA): >= 1 cm2 collector (tab) copper, 6 cm2 '
                       'for 1.35 W. A sustained +5VA short (~1.8-2 W at the Q2 limit) overheats it'))
    c.append(two('R8', 'R', '2.2', 'R1206', (139.7, 76.2), '_Q1_E', '+5VA', Tolerance='1%',
                 Note='Current sense: Q2 limits +5VA at ~0.3-0.35 A (Vbe 0.65-0.77 V; ngspice short: 0.35 A); '
                      '0.12 W at 230 mA. Inside the U1A loop (sensed after it), so it adds no DC error'))
    c.append(part('Q2', 'MMBT3904', 'MMBT3904', 'SOT23', (134.62, 86.36), 90,
                  {'1': '_Q1_E', '2': '+5VA', '3': '_Q1_B'},
                  Note='Current limit: steals Q1 base drive through R9 when R8 drops ~0.65 V. Not thermal: '
                       'keep it away from Q1'))
    c.append(two('R9', 'R', '150', 'R0603', (116.84, 101.6), '_REG_OUT', '_Q1_B',
                 Note='Base resistor: lets Q2 override U1A (at the limit Q2 sinks the LM358 output current, '
                      '~40 mA); 1.5 mA x 150R headroom at hFE 160'))
    c.append(part('U1', 'LM358', 'LM358', 'SOIC8', (101.6, 101.6), 0, {'3': 'V5_SET', '2': '_REG_FB', '1': '_REG_OUT'},
                  Note='+5VA error amplifier on +12V_F: +5VA = V5_SET + Vos (<= 7 mV, 7 uV/C typ: calibrated '
                       'out with the channel offsets). PI compensation R16/C37 with R7 (loop check: '
                       'docs/research.md D11)'))
    c.append(part('U1', 'LM358', 'LM358', 'SOIC8', (162.56, 104.14), 0, {'5': 'GND', '6': '_U1B', '7': '_U1B'},
                  unit=2, Note='Unused half: follower at GND'))
    c.append(part('U1', 'LM358', 'LM358', 'SOIC8', (180.34, 99.06), 0, {'8': '+12V_F', '4': 'GND'}, unit=3))
    c.append(two('C38', 'C', '100n', 'C0603', (193.04, 99.06), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U1 V+'))
    c.append(two('R7', 'R', '10k', 'R0603', (81.28, 104.14), '+5VA', '_REG_FB',
                 Note='Feedback from +5VA, Kelvin-sensed at the codec VCC pins; equals R6 so the LM358 bias '
                      'currents cancel (50 nA offset x 10k = 0.5 mV max)'))
    c.append(two('R16', 'R', '47k', 'R0603', (104.14, 111.76), '_REG_CC', '_REG_OUT',
                 Note='PI zero (154 Hz with C37): proportional gain 4.7 lowers the +5VA output impedance'))
    c.append(two('C37', 'C', '22n', 'C0603', (93.98, 111.76), '_REG_FB', '_REG_CC', Voltage='50V',
                 Note='Integrator with R7 (723 Hz unity): zero DC error. ngspice (vendor BCP56/LM358 models): '
                      'PM >= 78 deg, GM >= 26 dB over 8-250 mA, 8-100 uF, hFE 70-250, LM358 GBW 0.5-2x; '
                      'Zout <= 0.76 ohm'))
    c.append(two('C16', 'C', '1u', 'C0603', (187.96, 67.31), '+12V_F', 'GND', rot=0, Voltage='50V',
                 Note='U9 input'))
    c.append(part('U9', 'REF5050AD', 'REF5050A', 'SOIC8', (205.74, 71.12), 0,
                  {'1': None, '2': '+12V_F', '3': None, '4': 'GND', '5': '_REF_NR', '6': '_REF_OUT', '7': None,
                   '8': None},
                  Note='+5VA DC reference: 5.000 V +/-0.1 %, 8 ppm/C max (standard grade); load = U1A input only'))
    c.append(two('C17', 'C', '1u', 'C0603', (218.44, 82.55), '_REF_NR', 'GND', rot=0, Voltage='50V',
                 Note='U9 TRIM/NR noise reduction'))
    c.append(two('C18', 'C', '10u', 'C0805', (226.06, 72.39), '_REF_OUT', 'GND', rot=0, Voltage='25V',
                 Note='U9 output (datasheet 1-50 uF, ESR <= 1.5R)'))
    c.append(two('R6', 'R', '10k', 'R0603', (236.22, 68.58), '_REF_OUT', 'V5_SET',
                 Note='Reference filter with C19 (16 Hz, 10 ms soft start); equals R7 for bias-current balance'))
    c.append(two('C19', 'C', '1u', 'C0603', (245.11, 72.39), 'V5_SET', 'GND', rot=0, Voltage='50V',
                 Note='Reference filter (leakage x 10k: 10 nA = 0.1 mV); ground side Kelvin to the codec AGND'))
    # +3V3: input filter + TPS562208 FCCM buck (only the digital rail is switched; docs/research.md D7)
    xu, yr = BUCK
    ys = yr - 5.08                                   # SW / +3V3 line
    c.append(two('FB2', 'FerriteBead', 'GZ2012D121TF', 'C0805', (101.6, yr), '+12V_F', '_BK_F',
                 Note='Buck input filter (with R3, C6-C8): keeps the switching harmonics off +12V_F and the bus'))
    c.append(two('R3', 'R', '2.2', 'R1206', (113.03, yr), '_BK_F', 'V3_IN', Tolerance='1%',
                 Note='Buck input filter: with C6/C7 a ~5 kHz RC, no LC resonance; 2.2R << the buck input '
                      'impedance (~130R), so the D-CAP2 loop stays stable. ~90 mA -> 0.2 V, 20 mW'))
    for ref, xx in (('C6', 121.92), ('C7', 132.08)):
        c.append(two(ref, 'C', '10u', 'C1206', (xx, yr + 3.81), 'V3_IN', 'GND', rot=0, Voltage='50V',
                     Note='U2 input (1206 50 V: ~6.5 uF left at 12 V). Hot loop C6/C8 - U2 VIN/GND as small as possible'))
    c.append(two('C8', 'C', '100n', 'C0603', (142.24, yr + 3.81), 'V3_IN', 'GND', rot=0, Voltage='50V',
                 Note='U2 VIN HF bypass, right at pins 3/1'))
    c.append(two('R4', 'R', '100k', 'R0603', (xu - 15.24, yr + 5.08), 'V3_IN', '_BK_EN',
                 Note='EN pull-up (EN to GND 0.6-2.4M inside: EN >= 0.86 x VIN, within its 17 V rating)'))
    c.append(part('U2', 'TPS562208', 'TPS562208', 'SOT23-6', (xu, yr + 2.54), 0,
                  {'1': 'GND', '2': '_BK_SW', '3': 'V3_IN', '4': '_BK_FB', '5': '_BK_EN', '6': '_BK_BST'},
                  Note='+3V3 buck, FCCM variant (TPS562201 is the pulse-skipping one: do not substitute): ~580 kHz '
                       'at every load, D-CAP2, 1 ms soft start. Load: MCU board ~100 mA + PCM3168A VDD 130 mA + '
                       'Y1/U4 -> ~250 mA (~1 W in, ~90 mA from +12 V)'))
    c.append(two('C4', 'C', '100n', 'C0603', (xu + 17.78, ys + 3.81), '_BK_SW', '_BK_BST', rot=0, Voltage='50V',
                 Note='Bootstrap (VBST to SW)'))
    c.append(two('L1', 'L', '4.7u', 'MWSA0402S', (xu + 31.75, ys), '_BK_SW', '+3V3',
                 Note='Molded (fully shielded) inductor: small stray field near the audio. Isat 2.4 A min, '
                      '105 mOhm max; ripple ~1 A p-p (FCCM: the current goes negative at light load)'))
    c.append(two('R20', 'R', '10k', 'R0603', (xu + 22.86, yr + 8.89), '_BK_FB', 'GND', rot=0,
                 Note='Feedback bottom: +3V3 = 0.768 V x (1 + 33k/10k) = 3.30 V (3.22-3.39 V with VFB +/-2.5 %)'))
    c.append(two('R5', 'R', '33k', 'R0603', (xu + 34.29, yr + 5.08), '_BK_FB', '+3V3',
                 Note='Feedback top (TI table: 33.2k / 10k for 3.3 V)'))
    for ref, dx in (('C9', 43.18), ('C10', 53.34)):
        c.append(two(ref, 'C', '22u', 'C0805', (xu + dx, ys + 3.81), '+3V3', 'GND', rot=0, Voltage='25V',
                     Note='U2 output (2 x 22u: ~26 uF at 3.3 V, inside TI\'s 20-68 uF)'))
    c.append(two('C5', 'C', '100n', 'C0603', (xu + 63.5, ys + 3.81), '+3V3', 'GND', rot=0, Voltage='50V',
                 Note='U2 output HF'))
    c.append(two('FB1', 'FerriteBead', 'GZ2012D121TF', 'C0805', (xu + 81.28, ys), '+3V3', '+3V3_C',
                 Note='Codec digital supply filter (with C26-C28: switching ripple ~0.06 mV at VDD)'))
    c.append(two('R21', 'R', '10', 'R0603', (xu + 99.06, ys), '+3V3_C', '+3V3_OSC',
                 Note='Clock oscillator supply filter with C43 / C29 (1.6 kHz): keeps supply ripple off the '
                      'SCKI edges (jitter). Place at Y1'))
    c.append(two('C43', 'C', '10u', 'C0805', (xu + 106.68, ys + 3.81), '+3V3_OSC', 'GND', rot=0, Voltage='25V',
                 Note='Y1 supply filter, at Y1'))
    for ref, net, at, rot in (('#FLG01', 'GND', (30.48, 68.58), 0), ('#FLG02', '+12V_F', (71.12, 76.2), 180),
                              ('#FLG03', '-12V_F', (71.12, 55.88), 180), ('#FLG04', '+12V', (53.34, 76.2), 180),
                              ('#FLG05', '-12V', (53.34, 55.88), 180), ('#FLG06', 'V5_IN', (114.3, 76.2), 0),
                              ('#FLG07', '+3V3_C', (xu + 91.44, ys), 0), ('#FLG08', 'V3_IN', (118.11, yr), 0),
                              ('#FLG09', '+5VA', (152.4, 76.2), 0), ('#FLG10', '+3V3', (xu + 40.64, ys), 0),
                              ('#FLG11', '+3V3_OSC', (xu + 104.14, ys), 0)):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, rot, {'1': net}))

    # ---- PCM3168A codec: unit 1 analog, unit 2 interface/control/supplies
    a = {'52': 'ADC_IN1', '54': 'ADC_IN2', '56': 'ADC_IN3', '58': 'ADC_IN4', '62': 'ADC_IN5', '64': 'ADC_IN6',
         '51': 'VCOM_REF', '53': 'VCOM_REF', '55': 'VCOM_REF', '57': 'VCOM_REF', '61': 'VCOM_REF', '63': 'VCOM_REF',
         '1': 'VCOMAD', '59': 'VREFAD1', '60': 'VREFAD2', '15': 'VCOMDA'}
    for i, (p_, m_) in enumerate((('31', '32'), ('29', '30'), ('27', '28'), ('25', '26'), ('23', '24'),
                                  ('21', '22'), ('19', '20'), ('17', '18'))):
        a[p_], a[m_] = f'DAC{i + 1}P', f'DAC{i + 1}N'
    c.append(part('U3', 'PCM3168A', 'PCM3168A', 'TQFP64EP', COD_A, 0, a, unit=1,
                  Note='24-bit 6-in / 8-out codec (ADC to 96 kHz, DAC to 192 kHz). I2C 0x44. ADC master, '
                       'I2S-mode TDM; SE inputs, HPF bypassed. PowerPAD to GND with thermal vias (~1.2 W)'))
    c.append(part('U3', 'PCM3168A', 'PCM3168A', 'TQFP64EP', COD_D, 0,
                  {'7': '_BCK_C', '36': '_BCK_C', '6': '_LRCK_C', '35': '_LRCK_C',
                   '8': '_DOUT1_C', '9': '_DOUT2_C', '10': None,
                   '37': 'I2S_DAC1', '38': 'I2S_DAC2', '39': 'GND', '40': 'GND',
                   '41': '_SCKI', '48': 'GND', '45': 'GND', '44': '_ADR1',
                   '43': 'I2C_SDA', '42': 'I2C_SCL', '4': 'CODEC_RST', '5': None, '13': None,
                   '49': '+5VA', '3': '+5VA', '14': '+5VA', '34': '+5VA', '46': '+3V3_C', '12': '+3V3_C',
                   '50': 'GND', '2': 'GND', '16': 'GND', '33': 'GND', '47': 'GND', '11': 'GND', '65': 'GND'},
                  unit=2))
    xd, yd = COD_D
    c.append(part('Y1', 'ASE-xxxMHz', '24.576MHz', 'OSC3225', (xd + 22.86, yd - 43.18), 0,
                  {'1': '+3V3_OSC', '2': 'GND', '3': '_OSC', '4': '+3V3_OSC'},
                  Note='24.576 MHz 3.3 V CMOS oscillator (YXC OT2EL, 3225): SCKI = 256 fS at 96 kHz, '
                       '512 fS at 48 kHz (48 kHz family only, as modules/usb-audio). Own filtered supply '
                       '+3V3_OSC (R21/C43/C29)'))
    c.append(two('R10', 'R', '33', 'R0603', (xd + 27.94, yd - 20.32), '_SCKI', '_OSC',
                 Note='Series termination: SCKI'))
    c.append(part('U4', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (xd - 45.72, yd - 20.32), 180,
                  {'1': '_BCK_C', '6': '_BCK_B'}, unit=1,
                  Note='BCK/LRCK buffer to the MCU board: the codec master outputs see two short loads only'))
    c.append(part('U4', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (xd - 45.72, yd - 5.08), 180,
                  {'3': '_LRCK_C', '4': '_LRCK_B'}, unit=2))
    for ref, row, a_, b_, note in (('R11', yd - 20.32, 'I2S_SCLK', '_BCK_B', 'BCK to the MCU (I2S2/I2S3/SPI1 SCK)'),
                                   ('R12', yd - 5.08, 'I2S_LRCK', '_LRCK_B', 'LRCK to the MCU (WS/NSS)')):
        c.append(two(ref, 'R', '33', 'R0603', (xd - 66.04, row), a_, b_, Note=f'Series termination: {note}'))
    c.append(two('R13', 'R', '33', 'R0603', (xd - 27.94, yd + 10.16), 'I2S_ADC1', '_DOUT1_C',
                 Note='Series termination: DOUT1 (ADC 1-4 at 96 kHz, 1-6 at 48 kHz) to PB15'))
    c.append(two('R14', 'R', '33', 'R0603', (xd - 33.02, yd + 15.24), 'I2S_ADC2', '_DOUT2_C',
                 Note='Series termination: DOUT2 (ADC 5-6 at 96 kHz) to PA7'))
    c.append(two('R15', 'R', '10k', 'R0603', (xd + 35.56, yd - 12.7), '_ADR1', 'GND',
                 Note='ADR1 strap (I2C address bit 1 = 0) through a resistor: the pin is the MDO output in '
                      'SPI mode and has no internal pull-down'))
    c.append(two('R17', 'R', '10k', 'R0603', (xd + 25.4, yd + 11.43), 'CODEC_RST', 'GND', rot=0,
                 Note='Holds the codec in reset until the MCU (PB14) releases it with SCKI running'))
    # supply decoupling row (datasheet: 1 uF at each supply pin + 10 uF per supply line)
    for i, (ref, val, fp, net, volt, note) in enumerate((
            ('C20', '1u', 'C0603', '+5VA', '50V', 'VCCAD1 pin 49'), ('C21', '1u', 'C0603', '+5VA', '50V', 'VCCAD2 pin 3'),
            ('C22', '1u', 'C0603', '+5VA', '50V', 'VCCDA1 pin 14'), ('C23', '1u', 'C0603', '+5VA', '50V', 'VCCDA2 pin 34'),
            ('C24', '10u', 'C0805', '+5VA', '25V', 'VCC (ADC side) bulk'),
            ('C25', '10u', 'C0805', '+5VA', '25V', 'VCC (DAC side) bulk'),
            ('C26', '1u', 'C0603', '+3V3_C', '50V', 'VDD1 pin 46'), ('C27', '1u', 'C0603', '+3V3_C', '50V', 'VDD2 pin 12'),
            ('C28', '10u', 'C0805', '+3V3_C', '25V', 'VDD bulk'),
            ('C29', '100n', 'C0603', '+3V3_OSC', '50V', 'Y1 supply'), ('C30', '100n', 'C0603', '+3V3_C', '50V', 'U4 supply'))):
        c.append(two(ref, 'C', val, fp, (370.84 + 10.16 * i, 160.02), net, 'GND', rot=0, Voltage=volt,
                     Note=f'{note} decoupling'))
    # codec references (datasheet 12.1.4/12.1.5: 10 uF at VCOMAD, VCOMDA, VREFAD1/2)
    for i, (ref, val, fp, net, volt, note) in enumerate((
            ('C11', '10u', 'C0805', 'VCOMAD', '25V', 'VCOMAD (pin 1)'), ('C12', '10u', 'C0805', 'VCOMDA', '25V', 'VCOMDA (pin 15)'),
            ('C13', '10u', 'C0805', 'VREFAD1', '25V', 'VREFAD1 (pin 59)'), ('C14', '100n', 'C0603', 'VREFAD1', '50V', 'VREFAD1 HF'),
            ('C15', '10u', 'C0805', 'VREFAD2', '25V', 'VREFAD2 (pin 60)'))):
        c.append(two(ref, 'C', val, fp, (165.1 + 10.16 * i, 300.99), net, 'GND', rot=0, Voltage=volt,
                     Note=f'{note} decoupling, at the pin'))

    # ---- Inputs
    for n, y in zip(IN_CH, IN_Y):
        x0 = IN_X0
        u, k = IN_AMP[n]
        c.append(part(IN_JACK[n], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0, y), 0,
                      {'T': f'IN{n}', 'S': 'GND', 'TN': 'GND'},
                      Note=f'IN {n}: +/-5 V audio or CV, DC-coupled, 100k. TN to GND: unpatched = 0 V'))
        c.append(two(f'R{200 + n}', 'R', '100k', 'R0603', (x0 + 17.78, y), f'IN{n}', f'_IN{n}_SUM',
                     Note='Rin: 100k input impedance; gain -24k/100k = -0.24'))
        c.append(opamp(u, k, (x0 + 38.1, y - 2.54), 'VB_IN', f'_IN{n}_SUM', f'_IN{n}_DRV',
                       Note='+5VA single supply ADC drivers (U5A-D, U6A/B), VCOM buffer (U6C), VB_IN buffer (U6D). '
                            'Rail-to-rail out: VIN never leaves 0..5 V'))
        c.append(two(f'R{210 + n}', 'R', '24k', 'R0603', (x0 + 38.1, y + 5.08), f'_IN{n}_SUM', f'_IN{n}_DRV',
                     Note='Rf: +/-5.89 V at the jack = +/-1.414 V (1 Vrms SE full scale at VCC 5 V)'))
        c.append(two(f'C{200 + n}', 'C', '47p', 'C0603', (x0 + 38.1, y + 12.7), f'_IN{n}_SUM', f'_IN{n}_DRV',
                     Voltage='50V', Dielectric='C0G', Note='Rf || 47p: 141 kHz pole'))
        c.append(two(f'R{220 + n}', 'R', '470', 'R0603', (x0 + 55.88, y - 2.54), f'_IN{n}_DRV', f'ADC_IN{n}',
                     Note='ADC input network (datasheet 12.1.3: 47R/0.1u .. 470R/1n, ~160 kHz)'))
        c.append(two(f'C{210 + n}', 'C', '2.2n', 'C0603', (x0 + 63.5, y + 1.27), f'ADC_IN{n}', 'GND', rot=0,
                     Voltage='50V', Dielectric='C0G', Note='ADC charge reservoir / anti-alias (154 kHz), C0G'))

    # ---- Outputs
    for n, y in zip(OUT_CH, OUT_Y):
        xo = OUT_X0
        u, k = OUT_AMP[n]
        c.append(two(f'R{300 + n}', 'R', '15k', 'R0603', (xo - 17.78, y - 2.54), f'DAC{n}N', f'_OUT{n}_M',
                     Tolerance='1%', Note='Difference amplifier R1 (VOUT-): >= 14.1k DAC load at gain 1.467'))
        c.append(two(f'R{310 + n}', 'R', '15k', 'R0603', (xo - 35.56, y + 2.54), f'DAC{n}P', f'_OUT{n}_P',
                     Tolerance='1%', Note='Difference amplifier R1 (VOUT+)'))
        c.append(opamp(u, k, (xo, y), f'_OUT{n}_P', f'_OUT{n}_M', f'_OUT{n}_AMP',
                       Note='+/-12 V difference amplifiers (U7A-D OUT 1-4, U8A-D OUT 5-8)'))
        c.append(two(f'R{320 + n}', 'R', '22k', 'R0603', (xo, y - 10.16), f'_OUT{n}_M', f'_OUT{n}_AMP',
                     Tolerance='1%', Note='Rf: gain 22k/15k = 1.467, 8 Vpp differential -> +/-5.87 V'))
        c.append(two(f'C{300 + n}', 'C', '47p', 'C0603', (xo, y - 17.78), f'_OUT{n}_M', f'_OUT{n}_AMP',
                     Voltage='50V', Dielectric='C0G', Note='Rf || 47p: 154 kHz pole'))
        c.append(two(f'R{330 + n}', 'R', '22k', 'R0603', (xo - 15.24, y + 6.35), f'_OUT{n}_P', 'GND', rot=0,
                     Tolerance='1%', Note='Rg to GND: the VCOMDA common mode cancels (resistor match sets the '
                                          'residual offset, calibrated in firmware)'))
        c.append(two(f'C{310 + n}', 'C', '47p', 'C0603', (xo - 25.4, y + 6.35), f'_OUT{n}_P', 'GND', rot=0,
                     Voltage='50V', Dielectric='C0G', Note='Matches Cf on the + leg'))
        for ref, yy in ((f'R{340 + n}', y), (f'R{350 + n}', y + 7.62)):
            other = f'R{350 + n}' if ref == f'R{340 + n}' else f'R{340 + n}'
            c.append(two(ref, 'R', '2k', 'R1206', (xo + 17.78, yy), f'_OUT{n}_AMP', f'OUT{n}',
                         Power='0.25W', Tolerance='1%',
                         Note=f'Parallel with {other}: 1k / 0.5W effective (as modules/usb-audio R36/R38). '
                              'Opposing 5.9V output / 12.6V patch: <=0.17W each'))
        c.append(part(OUT_JACK[n], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (xo + 33.02, y), 180,
                      {'T': f'OUT{n}', 'S': 'GND', 'TN': None}, Note=f'OUT {n}: +/-5 V, DC-coupled, 1k'))

    # ---- References on +5VA (U6C, U6D)
    y0, y1 = REF_Y
    c.append(opamp('U6', 3, (76.2, y0), 'VCOMAD', 'VCOM_BUF', 'VCOM_BUF',
                   Note='VCOMAD buffer (10k source, 1 uA max)'))
    c.append(two('R50', 'R', '100', 'R0603', (93.98, y0), 'VCOM_BUF', 'VCOM_REF',
                 Note='Isolates U6C from the 10 uF on VCOM_REF'))
    c.append(two('C40', 'C', '10u', 'C0805', (104.14, y0 + 3.81), 'VCOM_REF', 'GND', rot=0, Voltage='25V',
                 Note='VCOM_REF (VIN1-6 -, single-ended termination)'))
    c.append(two('C41', 'C', '100n', 'C0603', (114.3, y0 + 3.81), 'VCOM_REF', 'GND', rot=0, Voltage='50V',
                 Note='VCOM_REF HF, at the codec'))
    c.append(two('R51', 'R', '24k', 'R0603', (45.72, y1 - 2.54), 'VCOM_BUF', '_VB_DIV',
                 Note='VB_IN = VCOM x 100/124: same ratio as the input Rf/Rin, so 0 V in = VCOM at VIN+'))
    c.append(two('R52', 'R', '100k', 'R0603', (53.34, y1 + 1.27), '_VB_DIV', 'GND', rot=0, Note='VB divider'))
    c.append(two('C42', 'C', '10u', 'C0805', (63.5, y1 + 1.27), '_VB_DIV', 'GND', rot=0, Voltage='25V',
                 Note='VB filter (0.8 Hz)'))
    c.append(opamp('U6', 4, (81.28, y1), '_VB_DIV', 'VB_IN', 'VB_IN', Note='VB_IN buffer for the six drivers'))

    # ---- Op-amp / buffer supplies and decoupling
    c.append(part('U5', 'OPA1679', 'OPA1679', 'SOIC14', (40.64, PU_Y), 0, {'4': '+5VA', '11': 'GND'}, unit=5))
    c.append(part('U6', 'OPA1679', 'OPA1679', 'SOIC14', (76.2, PU_Y), 0, {'4': '+5VA', '11': 'GND'}, unit=5))
    c.append(part('U7', 'OPA1679', 'OPA1679', 'SOIC14', (111.76, PU_Y), 0, {'4': '+12V_F', '11': '-12V_F'}, unit=5))
    c.append(part('U8', 'OPA1679', 'OPA1679', 'SOIC14', (162.56, PU_Y), 0, {'4': '+12V_F', '11': '-12V_F'}, unit=5))
    c.append(part('U4', '74LVC2G34', 'SN74LVC2G34', 'SC70-6', (228.6, PU_Y), 0, {'5': '+3V3_C', '2': 'GND'}, unit=3))
    for ref, xx, a_, b_, note in (('C31', 53.34, '+5VA', 'GND', 'U5 V+'), ('C32', 88.9, '+5VA', 'GND', 'U6 V+'),
                                  ('C33', 124.46, '+12V_F', 'GND', 'U7 V+'), ('C34', 137.16, 'GND', '-12V_F', 'U7 V-'),
                                  ('C35', 175.26, '+12V_F', 'GND', 'U8 V+'), ('C36', 187.96, 'GND', '-12V_F', 'U8 V-')):
        c.append(two(ref, 'C', '100n', 'C0603', (xx, PU_Y), a_, b_, rot=0, Voltage='50V', Note=f'{note} decoupling'))

    # ---- MCU board headers, I2C pull-ups, BOOT/RESET, SWD
    hx, hy = HDR
    c.append(part('J2', 'Conn_01x10', 'MCU_L', 'H1x10', HDR, 0,
                  {'1': '+3V3', '2': 'GND', '3': 'SWDIO', '4': 'SWCLK', '5': 'NRST', '6': 'BOOT0',
                   '7': 'I2C_SCL', '8': 'I2C_SDA', '9': 'CODEC_RST', '10': 'GND'},
                  MPN='2.54 mm 1x10 male pin header (2.5 mm plastic)',
                  Note='MCU board left strip: soldered here (plastic on the F side) and through J102 on the MCU '
                       'board. Hand-soldered'))
    c.append(part('J3', 'Conn_01x10', 'MCU_R', 'H1x10', (hx + 30.48, hy), 0,
                  {'1': '+3V3', '2': 'GND', '3': 'I2S_SCLK', '4': 'GND', '5': 'I2S_LRCK', '6': 'I2S_ADC1',
                   '7': 'I2S_DAC1', '8': 'I2S_ADC2', '9': 'I2S_DAC2', '10': 'GND'},
                  MPN='2.54 mm 1x10 male pin header (2.5 mm plastic)',
                  Note='MCU board right strip (TDM: GND between the clocks). Hand-soldered'))
    c.append(two('R18', 'R', '2.2k', 'R0603', (hx - 25.4, hy + 39.37), '+3V3', 'I2C_SCL', rot=0,
                 Note='I2C pull-up, shared with the MCU board (400 kHz)'))
    c.append(two('R19', 'R', '2.2k', 'R0603', (hx - 17.78, hy + 39.37), '+3V3', 'I2C_SDA', rot=0, Note='I2C pull-up'))
    c.append(part('SW1', 'SW_Push', 'RESET', 'SWK2', (hx, hy + 55.88), 0, {'1': 'NRST', '2': 'GND'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='CH32V307 reset (B side, reachable with the module out of the rack)'))
    c.append(part('SW2', 'SW_Push', 'BOOT', 'SWK2', (hx, hy + 68.58), 0, {'1': 'BOOT0', '2': '+3V3'},
                  MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec',
                  Note='Hold BOOT, press RESET: ROM bootloader on the USB-C (PB6/PB7), flash with wchisp/WCHISPTool'))
    c.append(part('J4', 'Conn_01x04', 'SWD', 'H1x4', (hx + 45.72, hy + 63.5), 0,
                  {'1': '+3V3', '2': 'SWDIO', '3': 'SWCLK', '4': 'GND'},
                  Note='WCH-LinkE debug (SWDIO/SWCLK). Optional, hand-soldered, B side'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # Power entry (as modules/usb-audio)
    W += [['J1.1', (33.02, 60.96), (33.02, 55.88), (50.8, 55.88), (50.8, 60.96), 'J1.2'], [(50.8, 55.88), 'D1.1'],
          ['J1.3', (33.02, 63.5), (33.02, 68.58), 'J1.7'], ['J1.5', (33.02, 66.04)], [(33.02, 68.58), (27.94, 68.58)],
          ['J1.4', (50.8, 63.5), (50.8, 68.58), 'J1.8'], ['J1.6', (50.8, 66.04)], [(50.8, 68.58), (53.34, 68.58)],
          ['J1.9', (33.02, 71.12), (33.02, 76.2), (50.8, 76.2), (50.8, 71.12), 'J1.10'], [(50.8, 76.2), 'D2.2'],
          ['D1.2', (86.36, 55.88)]]
    P += [('-12V', (55.88, 55.88), 0), ('GND', (27.94, 68.58), 0), ('GND', (53.34, 68.58), 90),
          ('+12V', (55.88, 76.2), 0), ('-12V_F', (86.36, 55.88), 0), ('+12V_F', (88.9, 76.2), 0)]
    # +5VA: D2 -> R1 || R2 -> V5_IN -> Q1 (C left, E right) -> R8 -> +5VA; Q2 across R8 pulls the Q1 base;
    # U1A (+ = V5_SET, - = R7 from +5VA, PI network R16/C37 to its output) drives the base through R9
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
    L += [('V5_SET', (260.35, 68.58), 'R'), ('V5_SET', (88.9, 99.06), 'L'), ('V5_IN', (116.84, 76.2), 'U')]
    # +3V3: +12V_F -> FB2 -> R3 -> V3_IN (C6-C8, R4 to EN) -> U2 TPS562208 -> SW (C4 to VBST) -> L1 -> +3V3
    # (C9/C10/C5, R5/R20 to VFB) -> FB1 -> +3V3_C -> R21 -> +3V3_OSC (C43)
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
    W += [['U3.7', 'U4.1'], ['U3.36', (xd - 22.86, yd - 17.78), (xd - 22.86, yd - 20.32)],
          ['U3.6', 'U4.3'], ['U3.35', (xd - 22.86, yd - 2.54), (xd - 22.86, yd - 5.08)],
          ['U4.6', 'R11.2'], ['U4.4', 'R12.2'], ['R11.1', (xd - 73.66, yd - 20.32)],
          ['R12.1', (xd - 73.66, yd - 5.08)],
          ['U3.8', 'R13.2'], ['R13.1', (xd - 40.64, yd + 10.16)],
          ['U3.9', 'R14.2'], ['R14.1', (xd - 43.18, yd + 15.24)],
          ['U3.41', 'R10.1'], ['R10.2', (xd + 34.29, yd - 20.32), (xd + 34.29, yd - 43.18), 'Y1.3'],
          ['U3.44', 'R15.1'], ['R15.2', (xd + 41.91, yd - 12.7), (xd + 41.91, yd - 10.16)],
          ['U3.4', (xd + 30.48, yd + 7.62)]]
    L += [('I2S_SCLK', (xd - 73.66, yd - 20.32), 'L'), ('I2S_LRCK', (xd - 73.66, yd - 5.08), 'L'),
          ('I2S_ADC1', (xd - 40.64, yd + 10.16), 'L'), ('I2S_ADC2', (xd - 43.18, yd + 15.24), 'L'),
          ('CODEC_RST', (xd + 30.48, yd + 7.62), 'R')]
    P += [('GND', (xd + 41.91, yd - 10.16), 0)]

    # Inputs
    for n, y in zip(IN_CH, IN_Y):
        x0 = IN_X0
        u, k = IN_AMP[n]
        up, um, uo = OPA4[k]
        j, rin, rf, cf, rs = IN_JACK[n], f'R{200 + n}', f'R{210 + n}', f'C{200 + n}', f'R{220 + n}'
        xm, xr = x0 + 30.48, x0 + 48.26           # - input column, feedback return column
        W += [[f'{j}.T', f'{rin}.1'], [f'{rin}.2', f'{u}.{um}'],
              [(xm, y), (xm, y + 5.08), f'{rf}.1'], [f'{rf}.2', (xr, y + 5.08), (xr, y - 2.54)],
              [(xm, y + 5.08), (xm, y + 12.7), f'{cf}.1'], [f'{cf}.2', (xr, y + 12.7), (xr, y + 5.08)],
              [f'{u}.{uo}', f'{rs}.1'], [f'{rs}.2', (x0 + 71.12, y - 2.54)],
              [f'{j}.TN', (x0 + 7.62, y - 2.54), (x0 + 7.62, y - 5.08)],
              [f'{j}.S', (x0 + 7.62, y + 2.54), (x0 + 7.62, y + 5.08)]]
        P += [('GND', (x0 + 7.62, y - 5.08), 180), ('GND', (x0 + 7.62, y + 5.08), 0)]
        L += [(f'IN{n}', (x0 + 11.43, y), 'U'), (f'ADC_IN{n}', (x0 + 71.12, y - 2.54), 'R')]

    # Outputs
    for n, y in zip(OUT_CH, OUT_Y):
        xo = OUT_X0
        u, k = OUT_AMP[n]
        up, um, uo = OPA4[k]
        rm, rp, rf, cf = f'R{300 + n}', f'R{310 + n}', f'R{320 + n}', f'C{300 + n}'
        ro, ro2, j = f'R{340 + n}', f'R{350 + n}', OUT_JACK[n]
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
              (f'OUT{n}', (xo + 25.4, y), 'U')]

    # References
    y0, y1 = REF_Y
    W += [['U6.8', 'R50.1'], [(86.36, y0), (86.36, y0 + 7.62), (66.04, y0 + 7.62), (66.04, y0 + 2.54), 'U6.9'],
          ['R50.2', (121.92, y0)],
          ['R51.2', 'U6.12'], ['R51.1', (35.56, y1 - 2.54)],
          ['U6.14', (99.06, y1)], [(91.44, y1), (91.44, y1 + 7.62), (71.12, y1 + 7.62), (71.12, y1 + 2.54), 'U6.13']]
    L += [('VCOM_BUF', (76.2, y0 + 7.62), 'D'), ('VCOM_REF', (121.92, y0), 'R'), ('VCOM_BUF', (35.56, y1 - 2.54), 'L'),
          ('VB_IN', (99.06, y1), 'R')]
    return W, P, L


# JLCPCB parts (live lookups 2026-11-05, docs/research.md section 6; usb-audio parts re-used where the
# value matches). Jacks, the power header and the J2/J3/J4 strips are hand-soldered: no LCSC field.
SOURCING = {
    ('R', '33', 'R0603'): dict(LCSC='C23140', MPN='0603WAF330JT5E', Manufacturer='UNI-ROYAL'),
    ('R', '150', 'R0603'): dict(LCSC='C22808', MPN='0603WAF1500T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '470', 'R0603'): dict(LCSC='C23179', MPN='0603WAF4700T5E', Manufacturer='UNI-ROYAL'),
    ('R', '2.2k', 'R0603'): dict(LCSC='C4190', MPN='0603WAF2201T5E', Manufacturer='UNI-ROYAL'),
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10k', 'R0603'): dict(LCSC='C25804', MPN='0603WAF1002T5E', Manufacturer='UNI-ROYAL'),
    ('R', '15k', 'R0603'): dict(LCSC='C22809', MPN='0603WAF1502T5E', Manufacturer='UNI-ROYAL'),
    ('R', '22k', 'R0603'): dict(LCSC='C31850', MPN='0603WAF2202T5E', Manufacturer='UNI-ROYAL'),
    ('R', '24k', 'R0603'): dict(LCSC='C23352', MPN='0603WAF2402T5E', Manufacturer='UNI-ROYAL'),
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
    ('OPA1679', 'OPA1679', 'SOIC14'): dict(LCSC='C2878631', MPN='OPA1679IDR', Manufacturer='Texas Instruments'),
    ('ASE-xxxMHz', '24.576MHz', 'OSC3225'): dict(LCSC='C5203547', MPN='OT2EL4C4JI-111OLP-24.576M',
                                                 Manufacturer='YXC'),
    ('SW_Push', 'RESET', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
    ('SW_Push', 'BOOT', 'SWK2'): dict(LCSC='C92589', MPN='K2-1808SN-A4SW-01', Manufacturer='Korean Hroparts Elec'),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR USB-AUDIO-MAX - carrier (jack board), S2. 6 in / 8 out, DC-coupled +/-5.9 V, '
                     'no level controls, PCM3168A 24-bit, up to 96 kHz. Circuit intent: docs/research.md', 2.0),
    ((20.32, 33.02), 'POWER: +12V -> D2 -> +12V_F (output op-amps; R1||R2 16.5R -> Q1 BCP56 (U1A LM358 loop, ref U9 REF5050) -> +5VA; '
                     'FB2 + R3 -> U2 TPS562208 FCCM buck -> L1 -> +3V3 -> FB1 -> +3V3_C -> R21 -> +3V3_OSC); -12V -> D1 -> -12V_F. '
                     '+12 V ~0.34 A max, -12 V ~20 mA.', 1.4),
    ((185.42, 45.72), 'DC REFERENCE: +5VA sets the gain of every channel (DAC 1.6 x VCC, ADC 0.2 x VCC), so it is a precision rail:\n'
                      'U9 REF5050A (0.1 %, 8 ppm/C) -> R6 10k / C19 1u -> V5_SET -> U1A LM358 -> R9 -> Q1 BCP56 -> R8 -> +5VA;\n'
                      'R7 10k senses +5VA at the codec; C37 22n + R16 47k = PI compensation. Q2 limits at ~0.3-0.35 A (R8 2.2R).\n'
                      'Calibration removes the fixed offset and gain errors; this keeps them from drifting.', 1.1),
    ((20.32, 116.84), '+3V3 BUCK, kept out of the audio (D7):\n'
                      '- only the digital rail is switched; +5VA (codec VCC, input op-amps)\n'
                      '  stays linear from +12V_F\n'
                      '- U2 is the FCCM TPS562208: fixed ~580 kHz at every load, it never\n'
                      '  pulse-skips into the audio band (TPS562201 would: do not substitute)\n'
                      '- FB2 + R3 2.2R + C6/C7 keep its switching current off +12V_F\n'
                      '  (output op-amps, +5VA regulator, U9) and off the Eurorack bus\n'
                      '- L1 molded (shielded); FB1 filters the codec VDD, R21/C43 the clock\n'
                      '- layout: C6/C8-U2 loop tight, small SW node, buck in the power corner\n'
                      '  away from the inputs and the codec analog pins, solid GND under it', 1.1),
    ((20.32, 154.94), 'PWR_FLAG: GND/+12V/-12V at J1; +12V_F/-12V_F behind D2/D1; V5_IN behind R1||R2; V3_IN behind FB2 + R3; +3V3 behind L1 (buck); '
                      '+5VA at R8 (discrete regulator); +3V3_C behind FB1; +3V3_OSC behind R21.',
     1.1),
    ((330.2, 38.1), 'PCM3168A INTERFACE: I2C 0x44 (MODE = DGND, ADR1/ADR0 = 0). ADC = clock master, 24-bit I2S-mode TDM;\n'
                    'DAC = slave on the same BCK/LRCK (pins tied). SCKI 24.576 MHz: 96 kHz = 256 fS (dual rate, BCK 128 fS),\n'
                    '48 kHz = 512 fS (single rate, BCK 256 fS): BCK = 12.288 MHz in both. 96 kHz: DOUT1 ADC1-4, DOUT2 ADC5-6,\n'
                    'DIN1 DAC1-4, DIN2 DAC5-8. 48 kHz: DOUT1 ADC1-6, DIN1 DAC1-8. Firmware: SEAD = 1 (single-ended),\n'
                    'BYP = 111 (HPF off, DC), REVAD = 1 (inverting drivers), offsets calibrated per channel.', 1.1),
    ((20.32, 167.64), 'INPUTS (x6): jack (TN = GND) -> 100k -> inverting driver on +5VA (-0.24, + at VB_IN) -> 470R / 2.2n C0G\n'
                      '-> VINn+ (single-ended mode; VINn- = VCOM_REF). +/-5.89 V = 1 Vrms ADC full scale. 100k input impedance.', 1.1),
    ((246.38, 142.24), 'OUTPUTS (x8): VOUTn+/- (8 Vpp differential around VCOMDA) -> difference amplifier on +/-12 V\n'
                       '(15k / 22k || 47p, gain 1.467) -> 2k || 2k (1k / 0.5 W) -> jack. Full scale +/-5.87 V, DC-coupled:\n'
                       'the common mode (VCOMDA) cancels, so the outputs stay near 0 V while the DAC powers up or mutes.', 1.1),
    ((20.32, 375.92), 'REFERENCES (+5VA): U6C buffers VCOMAD -> VCOM_BUF -> 100R / 10u -> VCOM_REF (VIN1-6 -);\n'
                      'VCOM_BUF x 100/124 -> U6D -> VB_IN (input drivers). Both track the codec mid-rail.', 1.1),
    ((579.12, 50.8), 'MCU BOARD LINK: J2/J3 1x10 2.54 mm male headers (plastic on the carrier F side);\n'
                     'the MCU board (usb-audio-max-mcu) solders on top. BOOT/RESET and SWD on the carrier (B side):\n'
                     'hold BOOT, press RESET = CH32V307 ROM bootloader on the USB-C.', 1.1),
]

TEXT_LEFT = {'C3', 'C17', 'C19', 'R20'}
TEXT_POS = {'U1': ((3.81, -6.35), (3.81, -3.81), 'left'), 'U1/2': ((3.81, -6.35), (3.81, -3.81), 'left'),
            'U1/3': ((1.27, -1.27), (1.27, 1.27), 'left'),
            'Q1': ((-7.62, 12.7), (-7.62, 15.24)), 'Q2': ((2.54, 6.35), (2.54, 8.89), 'left'),
            'U2': ((-7.62, -8.89), (-7.62, -6.35), 'left'), 'R4': ((0, -2.54), (0, 2.54)),
            'FB1': ((0, -3.81), (0, 3.81)), 'FB2': ((0, -3.81), (0, 3.81)), 'U9': ((2.54, -8.89), (2.54, -6.35), 'left'),
            'U5/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U6/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U7/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'), 'U8/5': ((-5.08, -1.27), (-5.08, 1.27), 'right'),
            'U4/3': ((-6.35, -1.27), (-6.35, 1.27), 'right'),
            'U4': ((-1.27, -10.16), (-1.27, -7.62)), 'U4/2': ((-1.27, 8.89), (-1.27, 11.43)),
            'U3': ((-12.7, -27.94), (12.7, -27.94)), 'U3/2': ((-22.86, -30.48), (-22.86, -27.94)),
            'Y1': ((-10.16, -6.35), (-10.16, -3.81), 'right'),
            'SW1': ((0, -3.81), (0, 3.81)), 'SW2': ((0, -3.81), (0, 3.81)),
            'J2': ((0, -13.97), (0, 16.51)), 'J3': ((0, -13.97), (0, 16.51)), 'J4': ((0, -6.35), (0, 8.89))}
# Op-amp unit texts: input drivers / references above-right of the triangle, output stages below it.
TEXT_POS.update({f'{u}/{k}' if k > 1 else u: ((3.81, -6.35), (3.81, -3.81), 'left')
                 for u, k in list(IN_AMP.values()) + [('U6', 3), ('U6', 4)]})
TEXT_POS.update({f'{u}/{k}' if k > 1 else u: ((0, 7.62), (0, 10.16)) for u, k in OUT_AMP.values()})

MULTI_UNIT = {'U1': {1, 2, 3}, 'U3': {1, 2}, 'U4': {1, 2, 3}, 'U5': {1, 2, 3, 4, 5}, 'U6': {1, 2, 3, 4, 5}, 'U7': {1, 2, 3, 4, 5},
              'U8': {1, 2, 3, 4, 5}}
