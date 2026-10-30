"""usb-power-45w S2 circuit table, drawing and sourcing (imported by tools/build_schematic.py).

USB-C PD 20 V input (CH224A, 120k CFG1) -> 5 A fuse + SMBJ20A TVS -> VPD -> U5 TPS259470A eFuse -> VIN (20 V)
-> three direct switchers, no LDOs, all in forced PWM (fixed frequency at every load) (docs/design.md):
  U2 TPS62933F sync buck                        VIN -> +12V   (6.8 uH, 1.2 MHz)
  U3 TPS62933F sync buck                        VIN -> +5V    (3.3 uH, ~2.0 MHz)
  U4 LMR38020F sync inverting buck-boost (IC ground = -12V)   VIN -> -12V  (15 uH, ~790 kHz)
VBUS sees only ~2 uF at attach (C1 + C2): every bulk cap sits behind U5, which ramps VIN at ~2 V/ms (C3 1 nF)
and opens only inside its 17.6 V UVLO / 25.3 V OVLO window, so a 5/9/12/15 V contract keeps everything off.
U5 AUXOFF holds EN_P (U2/U3) low until the VIN ramp is done; U4 EN is fed from +12V through the Q1 PNP:
-12V starts after +12V and stops with it.
Outputs: two parallel 16-pin Eurorack box headers (Doepfer pinout), bulk caps, rail clamps and rail LEDs.
Front panel as modules/usb-power: SW1 TL3340 RESET on the U5 EN/UVLO pin, D8 red 3 mm +5V power LED.
"""

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', 'VIN': 'VCC', '+12V': '+12V', '+5V': '+5V', '-12V': '-12V'}

# Q1 drawn mirrored about X: emitter (to +12V) on top, collector at the bottom.
MIRROR_X = {'Q1'}
MULTI_UNIT = {}
TEXT_LEFT = {'C9', 'C18', 'R15'}
TEXT_POS = {'Q1': ((5.08, -5.08), (5.08, -2.54), 'left'),
            'R8': ((6.35, -1.27), (6.35, 1.27), 'left'), 'R11': ((6.35, -1.27), (6.35, 1.27), 'left'),
            'L1': ((0, 2.54), (0, 5.08)), 'L2': ((0, 2.54), (0, 5.08)),
            'C5': ((2.54, 5.08), (2.54, 7.62), 'left'),
            'SW1': ((0, -11.43), (0, -8.89)), 'D8': ((3.81, -1.27), (3.81, 1.27), 'right')}

# Block anchors (IC centres, sheet mm).
U5_AT = (165.1, 53.34)   # eFuse
U2_AT = (248.92, 63.5)    # +12V buck
U3_AT = (279.4, 142.24)   # +5V buck
U4_AT = (101.6, 142.24)   # -12V inverting buck-boost
J2_AT, J3_AT = (45.72, 223.52), (101.6, 223.52)
EF_Y = 88.9               # eFuse set-up resistor / capacitor row
EXTRA_Y = 220.98          # bulk caps / clamps / LEDs row
SW_AT = (325.12, 220.98)  # front panel RESET button
LED_AT = (363.22, 220.98)  # front panel power LED (R22 above D8)

# JLCPCB parts, live-checked 2026-10-30/31 (assembly.py search/lookup --strict-live; stock is not a reservation).
# Every R and C below is a JLCPCB Basic part.
UNIROYAL = 'UNI-ROYAL'
R0603 = {'120k': 'C25808', '100k': 'C25803', '68k': 'C23231', '47k': 'C25819', '33k': 'C4216', '20k': 'C4184',
         '13k': 'C22797', '12k': 'C22790', '10k': 'C25804', '9.1k': 'C23260', '5.1k': 'C23186', '3.3k': 'C22978',
         '2.2k': 'C4190', '1k': 'C21190', '820': 'C23253'}
R_MPN = {'120k': '0603WAF1203T5E', '100k': '0603WAF1003T5E', '68k': '0603WAF6802T5E', '47k': '0603WAF4702T5E',
         '33k': '0603WAF3302T5E', '20k': '0603WAF2002T5E', '13k': '0603WAF1302T5E', '12k': '0603WAF1202T5E',
         '10k': '0603WAF1002T5E', '9.1k': '0603WAF9101T5E', '5.1k': '0603WAF5101T5E', '3.3k': '0603WAF3301T5E',
         '2.2k': '0603WAF2201T5E', '1k': '0603WAF1001T5E', '820': '0603WAF8200T5E'}
CAPS = {  # (value, footprint) -> fields
    ('100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO', Voltage='50V'),
    ('1u', 'C0603'): dict(LCSC='C15849', MPN='CL10A105KB8NNNC', Manufacturer='Samsung', Voltage='50V'),
    ('22n', 'C0603'): dict(LCSC='C21122', MPN='CL10B223KB8NNNC', Manufacturer='Samsung', Voltage='50V'),
    ('10n', 'C0603'): dict(LCSC='C57112', MPN='0603B103K500NT', Manufacturer='FH', Voltage='50V'),
    ('1n', 'C0603'): dict(LCSC='C1588', MPN='CL10B102KB8NNNC', Manufacturer='Samsung', Voltage='50V'),
    ('10u', 'C1206'): dict(LCSC='C13585', MPN='CL31A106KBHNNNE', Manufacturer='Samsung', Voltage='50V'),
    ('22u', 'C1206'): dict(LCSC='C12891', MPN='CL31A226KAHNNNE', Manufacturer='Samsung', Voltage='25V'),
    ('47u', 'CP63'): dict(LCSC='C165527', MPN='MVK50V47M6.3*8 6.3TP', Manufacturer='SamYoung', Voltage='50V'),
    ('100u', 'CP63'): dict(LCSC='C350012', MPN='MVK 35V100 M 6.3*8', Manufacturer='SamYoung', Voltage='35V'),
}
SLO = {  # Sunltech SLO1040H molded 10.8 x 10 mm inductors (one land pattern)
    '15u': ('C182184', 'SLO1040H150MTT', 'Isat 7 A, Irms 4.5 A'),
    '6.8u': ('C207852', 'SLO1040H6R8MTT', 'Isat 10 A, Irms 7 A, DCR 22 mOhm'),
    '3.3u': ('C207850', 'SLO1040H3R3MTT', 'Isat 16 A, Irms 10 A'),
}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def two(ref, sym, value, fp, at, a, b, rot=0, **fields):
    """Two-pin part: pin 1 = a, pin 2 = b. R/C/L/F: rot 0 = vertical, pin 1 on top; rot 90 = horizontal,
    pin 1 left. Diodes/LEDs: rot 270 = K on top, rot 90 = A on top."""
    return part(ref, sym, value, fp, at, rot, {'1': a, '2': b}, **fields)


def res(ref, value, at, a, b, rot=0, **kw):
    return two(ref, 'R', value, 'R0603', at, a, b, rot, LCSC=R0603[value], MPN=R_MPN[value], Manufacturer=UNIROYAL,
               Tolerance='1%', **kw)


def cap(ref, value, fp, at, a, b, rot=0, **kw):
    sym = 'C_Polarized' if fp == 'CP63' else 'C'
    return two(ref, sym, value, fp, at, a, b, rot, **CAPS[(value, fp)], **kw)


def inductor(ref, value, at, a, b, rot=0, note=''):
    code, mpn, rating = SLO[value]
    return two(ref, 'L', value, 'SLO1040', at, a, b, rot, LCSC=code, MPN=mpn, Manufacturer='Sunltech',
               Note=f'Molded 10.8 x 10 mm, {rating}. {note}'.strip())


def tps62933f(c, u, at, out, refs, lval, rfb, rt, fsw):
    """TPS62933F sync buck, forced PWM (datasheet SLUSEA4D): VIN 2 x 10u + 100n, SS 22n (~3 ms), BST 100n,
    L, FB divider (VREF 0.8 V), 4 x 22u out. RT to GND = 1.2 MHz, or an RT resistor (equation 2)."""
    x, y = at
    cin1, cin2, chf, css, cbst, lref, rtop, rbot, couts, rrt = refs
    sw, bst, fb, ss = f'_SW_{u}', f'_BST_{u}', f'_FB_{u}', f'_SS_{u}'
    rt_net = 'GND' if rt is None else f'_RT_{u}'
    c.append(part(u, 'TPS62933F', 'TPS62933FDRLR', 'SOT583', at, 0,
                  {'1': rt_net, '2': 'EN_P', '3': 'VIN', '4': 'GND', '5': sw, '6': bst, '7': ss, '8': fb},
                  LCSC='C5219272', MPN='TPS62933FDRLR', Manufacturer='Texas Instruments',
                  Note=f'{out} sync buck, 3.8-30 V in, 3 A, forced PWM (FCCM, no light-load skipping), {fsw}'))
    for ref, dx, v, fp in ((cin1, -38.1, '10u', 'C1206'), (cin2, -30.48, '10u', 'C1206'),
                           (chf, -22.86, '100n', 'C0603')):
        c.append(cap(ref, v, fp, (x + dx, y - 11.43), 'VIN', 'GND', Note=f'{u} input, at VIN/GND pins'))
    c.append(cap(css, '22n', 'C0603', (x - 17.78, y + 6.35), ss, 'GND', Note=f'{u} soft start ~3 ms (>= 6.8n)'))
    if rt is not None:
        c.append(res(rrt, rt, (x - 12.7, y + 8.89), rt_net, 'GND', Note=f'{u} RT: {fsw} (fSW = 17293 x RT^-0.942)'))
    c.append(cap(cbst, '100n', 'C0603', (x + 12.7, y - 3.81), bst, sw, Note=f'{u} bootstrap'))
    c.append(inductor(lref, lval, (x + 20.32, y), sw, out, rot=90))
    rt_val, rb_val = rfb
    c.append(res(rbot, rb_val, (x + 12.7, y + 11.43), fb, 'GND', Note=f'FB bottom: {out}'))
    c.append(res(rtop, rt_val, (x + 20.32, y + 7.62), fb, out, rot=90, Note=f'FB top: {out}'))
    for i, ref in enumerate(couts):
        c.append(cap(ref, '22u', 'C1206', (x + 33.02 + 7.62 * i, y + 3.81), out, 'GND', Note=f'{out} output'))


def circuit():
    c = []
    # ---- USB-C PD input: CH224A requests 20 V (CFG1 120k, WCH CH224 datasheet V2.0 table 5-1)
    c.append(part('J1', 'HRO_TYPE_C_31_M_12', 'TYPE-C-31-M-12', 'USBC', (38.1, 60.96), 0,
                  {'A1': 'GND', 'A12': 'GND', 'A4': 'VBUS', 'A9': 'VBUS', 'A5': 'CC1', 'B5': 'CC2',
                   'A6': None, 'A7': None, 'B6': None, 'B7': None, 'A8': None, 'B8': None, 'S1': 'GND'},
                  LCSC='C165948', MPN='TYPE-C-31-M-12', Manufacturer='Korean Hroparts Elec',
                  Note='As usb-power J1 (5 A / 20 V contacts). Power only: data and SBU open, shell to GND'))
    c.append(two('F1', 'Fuse', '5A', 'F1206', (63.5, 45.72), 'VBUS', 'VPD', rot=90,
                 LCSC='C57525', MPN='0466005.NRHF', Manufacturer='Littelfuse',
                 Note='5 A fast 1206 fuse (32 V class): back-up only, U5 limits at ~4 A first'))
    c.append(part('U1', 'CH224A', 'CH224A', 'SSOP10', (101.6, 66.04), 0,
                  {'1': 'VPD', '8': 'VPD', '7': 'CC1', '6': 'CC2', '4': '_PD_D', '5': '_PD_D', '11': 'GND',
                   '2': None, '3': None, '9': '_CFG1', '10': None},
                  LCSC='C42459160', MPN='CH224A', Manufacturer='WCH',
                  Note='USB PD sink, fixed 20 V request (CFG1 120k). Powered from VPD, ahead of the eFuse: '
                       'DP/DM tied locally, CFG2/CFG3/PG open'))
    c.append(res('R1', '120k', (121.92, 64.77), '_CFG1', 'GND', Note='CH224A CFG1 to GND: 120k = 20 V request'))
    c.append(cap('C1', '1u', 'C0603', (78.74, 49.53), 'VPD', 'GND', Note='CH224A VHV decoupling'))
    c.append(two('D1', 'D_Zener', 'SMBJ20A', 'SMB', (121.92, 49.53), 'VPD', 'GND', rot=270,
                 LCSC='C10213', MPN='SMBJ20A', Manufacturer='RUILON',
                 Note='Unidirectional TVS, 20 V stand-off / 22.2 V min breakdown (21 V PD max), clamps hot-plug '
                      'ringing for U5 (28 V abs max)'))
    c.append(cap('C2', '1u', 'C0603', (134.62, 49.53), 'VPD', 'GND',
                 Note='U5 IN cap. C1 + C2 = all the capacitance VBUS sees at attach (USB-C sink limit 10 uF)'))

    # ---- U5 TPS259470A eFuse: UVLO/OVLO window, dVdt inrush ramp, 4 A active current limit, auto-retry
    c.append(part('U5', 'TPS259470ARPW', 'TPS259470ARPWR', 'RPW10', U5_AT, 0,
                  {'5': 'VPD', '1': 'EF_UV', '2': 'EF_OV', '7': 'EF_DVDT', '10': 'EF_TMR', '6': 'VIN',
                   '3': 'EN_P', '4': None, '9': 'EF_ILM', '8': 'GND'},
                  LCSC='C3662799', MPN='TPS259470ARPWR', Manufacturer='Texas Instruments',
                  Note='eFuse (SLVSFC9C): 2.7-23 V, 28 mOhm, OVLO, active current limit, auto-retry. '
                       'AUXOFF (open drain) releases EN_P once VIN has ramped. FLT open'))
    ex = 139.7
    c.append(res('R2', '100k', (ex, EF_Y), 'VPD', 'EF_UV',
                  Note='UVLO/OVLO divider: on >= 1.2 x 107.3/7.3 = 17.6 V, off < 16.0 V'))
    c.append(res('R3', '2.2k', (ex + 7.62, EF_Y), 'EF_UV', 'EF_OV', Note='UVLO/OVLO divider, see R2'))
    c.append(res('R4', '5.1k', (ex + 15.24, EF_Y), 'EF_OV', 'GND',
                 Note='UVLO/OVLO divider: OVLO cuts VIN above 1.2 x 107.3/5.1 = 25.3 V'))
    c.append(cap('C3', '1n', 'C0603', (ex + 22.86, EF_Y), 'EF_DVDT', 'GND',
                 Note='dVdt: 2000 / 1000 pF = 2 V/ms, VIN 0 -> 20 V in ~10 ms, ~0.15 A inrush into ~75 uF'))
    c.append(cap('C4', '10n', 'C0603', (ex + 30.48, EF_Y), 'EF_TMR', 'GND',
                 Note='ITIMER: overcurrent blanking 1.51 V x 10 nF / 1.8 uA = 8 ms'))
    c.append(res('R5', '820', (ex + 38.1, EF_Y), 'EF_ILM', 'GND', Note='ILM: limit 3334 / 820 = 4.1 A (+/-10 %)'))
    c.append(res('R6', '100k', (ex + 45.72, EF_Y), 'VIN', 'EN_P',
                 Note='EN_P = VIN / 11 = 1.8 V at 20 V (TPS62933 EN max 5.5 V, AUXOFF max 6.5 V)'))
    c.append(res('R7', '10k', (ex + 53.34, EF_Y), 'EN_P', 'GND', Note='EN_P divider bottom, see R6'))
    c.append(cap('C5', '47u', 'CP63', (190.5, 49.53), 'VIN', 'GND',
                 Note='Aluminium bulk on VIN, behind the eFuse: damps the converter input ceramics'))

    # ---- +12V and +5V: TPS62933F in forced PWM; EN_P from the eFuse AUXOFF
    tps62933f(c, 'U2', U2_AT, '+12V', ('C6', 'C7', 'C8', 'C9', 'C10', 'L1', 'R8', 'R9',
                                       ('C11', 'C12', 'C13', 'C14'), None),
              '6.8u', ('47k', '3.3k'), None, '1.2 MHz (RT to GND)')
    tps62933f(c, 'U3', U3_AT, '+5V', ('C15', 'C16', 'C17', 'C18', 'C19', 'L2', 'R11', 'R12',
                                      ('C20', 'C21', 'C22', 'C23'), 'R10'),
              '3.3u', ('68k', '13k'), '10k', '~2.0 MHz (RT 10k)')

    # ---- -12V: LMR38020FDDAR synchronous inverting buck-boost. IC GND (pins 1/9) = -12V; L3 from SW to system
    # GND. FB = 1.0 V above -12V: |Vout| = 1.0 x (1 + 100k / 9.1k) = 11.99 V.
    x, y = U4_AT
    c.append(part('U4', 'LMR38020FDDA', 'LMR38020FDDAR', 'PPAD8', U4_AT, 0,
                  {'3': 'VIN', '2': 'EN_N', '4': '_RT_U4', '7': '_BOOT_U4', '8': '_SW_U4', '6': None, '5': 'FB_N',
                   '1': '-12V', '9': '-12V'},
                  LCSC='C5149193', MPN='LMR38020FDDAR', Manufacturer='Texas Instruments',
                  Note='Synchronous inverting buck-boost, forced PWM: device sees VIN + 12 V = 32 V (80 V part). '
                       'Pins 1 and pad are the -12V node, not GND. PG open'))
    yr = y - 15.24
    c.append(cap('C24', '10u', 'C1206', (x - 58.42, yr + 3.81), 'VIN', 'GND', Note='U4 input, VIN to system GND'))
    for ref, dx, v, fp in (('C25', -50.8, '10u', 'C1206'), ('C26', -43.18, '10u', 'C1206'),
                           ('C27', -35.56, '100n', 'C0603')):
        c.append(cap(ref, v, fp, (x + dx, yr + 3.81), 'VIN', '-12V',
                     Note='U4 input across VIN and the IC ground (-12V): sees 32 V, 50 V part'))
    c.append(res('R13', '33k', (x - 16.51, y + 5.08), '-12V', '_RT_U4', rot=90,
                 Note='RT: ~790 kHz (TI table 8-1: 34.8k = 750 kHz, 25.5k = 1 MHz)'))
    c.append(cap('C28', '100n', 'C0603', (x + 15.24, y - 8.89), '_SW_U4', '_BOOT_U4', Note='U4 bootstrap'))
    c.append(inductor('L3', '15u', (x + 35.56, y + 3.81), '_SW_U4', 'GND',
                      note='Peak 2.0 A at 1 A out (HS limit 2.6 A min)'))
    for i, ref in enumerate(('C29', 'C30', 'C31', 'C32', 'C33')):
        c.append(cap(ref, '22u', 'C1206', (x + 50.8 + 7.62 * i, y + 16.51), '-12V', 'GND', Note='-12V output'))
    c.append(res('R15', '9.1k', (x + 30.48, y + 24.13), 'FB_N', '-12V', Note='FB bottom, to the IC ground (-12V)'))
    c.append(res('R14', '100k', (x + 38.1, y + 20.32), 'FB_N', 'GND', rot=90, Note='FB top, to system GND'))
    # EN_N: +12V -> Q1 (on while +12V > ~0.7 V) -> R17 100k -> EN_N -> R18 20k -> -12V. EN = (V(+12V) - V(-12V))
    # / 6: starts at +12V ~ 8 V, runs at ~4 V (abs max VIN + 0.3 V), off as soon as +12V is gone.
    c.append(part('Q1', 'MMBT3906', 'MMBT3906', 'SOT23', (x - 29.21, y + 22.86), 0,
                  {'1': '_QB', '2': '+12V', '3': '_QC'},
                  LCSC='C53444', MPN='MMBT3906LT1G', Manufacturer='onsemi',
                  Note='-12V enable from +12V: -12V follows +12V up and down'))
    c.append(res('R16', '100k', (x - 38.1, y + 22.86), 'GND', '_QB', rot=90, Note='Q1 base: ~0.11 mA'))
    c.append(res('R17', '100k', (x - 20.32, y + 27.94), '_QC', 'EN_N', rot=90, Note='EN_N divider top'))
    c.append(res('R18', '20k', (x - 12.7, y + 31.75), 'EN_N', '-12V', Note='EN_N divider bottom (to IC ground)'))

    # ---- Outputs: 2 x 16-pin box header in parallel (Doepfer: 1-2 -12V, 3-8 GND, 9-10 +12V, 11-12 +5V)
    for ref, at in (('J2', J2_AT), ('J3', J3_AT)):
        pins = {'1': '-12V', '2': '-12V', '9': '+12V', '10': '+12V', '11': '+5V', '12': '+5V'}
        pins.update({str(n): 'GND' for n in range(3, 9)})
        pins.update({str(n): None for n in range(13, 17)})
        c.append(part(ref, 'Conn_02x08_Odd_Even', 'IDC 2x8 box header', 'IDC16', at, 0, pins,
                      Note='Hand-soldered shrouded 16-pin box header, pin 1 = -12V (red stripe). J2 and J3 are in '
                           'parallel: use both cables above ~1.5 A per rail. CV/GATE (13-16) open'))
    ey = EXTRA_Y
    c.append(cap('C34', '100u', 'CP63', (175.26, ey), '+12V', 'GND', Note='+12V bulk at the headers'))
    c.append(two('D2', 'D_Schottky', 'SS34', 'SMA', (182.88, ey), '+12V', 'GND', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD', Note='Clamp: +12V never below GND'))
    c.append(res('R19', '10k', (190.5, ey), '+12V', '_LED_P12', Note='+12V LED, ~1 mA'))
    c.append(two('D5', 'LED', 'RED', 'LED0603', (190.5, ey + 7.62), 'GND', '_LED_P12', rot=90,
                 LCSC='C2286', MPN='KT-0603R', Manufacturer='Hubei KENTO', Note='+12V on'))
    c.append(cap('C35', '100u', 'CP63', (203.2, ey), '+5V', 'GND', Note='+5V bulk at the headers'))
    c.append(two('D3', 'D_Schottky', 'SS34', 'SMA', (210.82, ey), '+5V', 'GND', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD', Note='Clamp: +5V never below GND'))
    c.append(res('R20', '1k', (218.44, ey), '+5V', '_LED_P5', Note='+5V LED, ~3 mA'))
    c.append(two('D6', 'LED', 'RED', 'LED0603', (218.44, ey + 7.62), 'GND', '_LED_P5', rot=90,
                 LCSC='C2286', MPN='KT-0603R', Manufacturer='Hubei KENTO', Note='+5V on'))
    c.append(cap('C36', '100u', 'CP63', (231.14, ey), 'GND', '-12V', Note='-12V bulk at the headers'))
    c.append(two('D4', 'D_Schottky', 'SS34', 'SMA', (238.76, ey), 'GND', '-12V', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD', Note='Clamp: -12V never above GND'))
    c.append(two('D7', 'LED', 'RED', 'LED0603', (246.38, ey), '_LED_N12', 'GND', rot=90,
                 LCSC='C2286', MPN='KT-0603R', Manufacturer='Hubei KENTO', Note='-12V on'))
    c.append(res('R21', '10k', (246.38, ey + 7.62), '_LED_N12', '-12V', Note='-12V LED, ~1 mA'))

    # ---- Front panel, as modules/usb-power: SMT RESET button on the eFuse EN/UVLO and a 3 mm +5V power LED
    sx, sy = SW_AT
    c.append(part('SW1', 'TL3340AF160QG', 'TL3340AF160QG', 'TL3340', SW_AT, 0,
                  {'1': 'EF_UV', '3': 'EF_UV', '2': 'GND', 'MP': None},
                  LCSC='C2886925', MPN='TL3340AF160QG', Manufacturer='E-Switch',
                  Note='RESET, as usb-power SW1 (P021301 Rev B: contacts 1+3 common, 2 = NO). Press pulls U5 '
                       'EN/UVLO to GND: U5 shuts down, VIN, EN_P and every rail turn off. Release: U5 restarts '
                       '(fault cleared, soft ramp, rails in order) if VPD is in the 17.6-25.3 V window. '
                       'R2 limits the pressed current to 0.2 mA. Case MP floating'))
    lx, ly = LED_AT
    c.append(res('R22', '1k', (lx, ly), '+5V', '_LED_PANEL', Note='Panel LED, ~3 mA (as usb-power R32)'))
    c.append(two('D8', 'LED', 'RED 3mm', 'LED3EDGE', (lx, ly + 7.62), 'GND', '_LED_PANEL', rot=90,
                 Note='Front panel +5V POWER LED, as usb-power D10: red 3 mm THT, leads formed 90 degrees, '
                      'hand-soldered (not JLC-assembled). +5V presence only'))

    # VIN is driven by the U5 OUT pin (power output): no flag there. VPD gets one (fuse and connector are passive).
    for ref, net, at in (('#FLG01', 'GND', (53.34, 93.98)), ('#FLG02', 'VPD', (99.06, 45.72)),
                         ('#FLG03', '-12V', (172.72, 154.94)), ('#FLG04', '+12V', (309.88, 63.5)),
                         ('#FLG05', '+5V', (340.36, 142.24))):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, 0, {'1': net}))
    return c


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # USB-C -> F1 -> VPD rail -> U5 eFuse -> VIN; CH224A on VPD
    W += [['J1.A4', 'F1.1'], ['F1.2', 'U5.5'], [(83.82, 45.72), (83.82, 55.88), 'U1.8'],
          ['U1.1', (83.82, 50.8)], ['J1.A5', (76.2, 50.8), (76.2, 60.96), 'U1.7'],
          ['J1.B5', (73.66, 53.34), (73.66, 66.04), 'U1.6'], ['U1.4', (81.28, 71.12), (81.28, 76.2), 'U1.5'],
          ['U1.9', 'R1.1'], ['U5.6', (193.04, 45.72)]]
    P += [('VIN', (193.04, 45.72), 270)]
    L += [('VBUS', (55.88, 45.72), 'R'), ('CC1', (58.42, 50.8), 'R'), ('CC2', (58.42, 53.34), 'R'),
          ('VPD', (142.24, 45.72), 'U')]

    def buck(u, at, out, rt):
        x, y = at
        w = [[(x - 45.72, y - 15.24), (x - 12.7, y - 15.24), (x - 12.7, y - 7.62), f'{u}.3'],
             [f'{u}.7', (x - 17.78, y + 2.54)],
             [f'{u}.6', (x + 12.7, y - 7.62)], [f'{u}.5', (x + 16.51, y)],
             [f'{u}.8', (x + 16.51, y + 7.62)], [(x + 24.13, y + 7.62), (x + 24.13, y)],
             [(x + 24.13, y), (x + 63.5, y)]]
        if rt:
            w += [[f'{u}.1', (x - 12.7, y + 5.08)]]
        p = [('VIN', (x - 45.72, y - 15.24), 90), (out, (x + 63.5, y), 270)]
        if not rt:   # RT to GND (1.2 MHz): drawn down to a GND symbol clear of the SS cap
            w += [[f'{u}.1', (x - 12.7, y + 5.08), (x - 12.7, y + 12.7)]]
            p += [('GND', (x - 12.7, y + 12.7), 0)]
        return w, p

    for u, at, out, rt in (('U2', U2_AT, '+12V', False), ('U3', U3_AT, '+5V', True)):
        w, p = buck(u, at, out, rt)
        W += w
        P += p

    # -12V inverter
    x, y = U4_AT
    yr = y - 15.24
    W += [[(x - 63.5, yr), (x - 17.78, yr), (x - 17.78, y - 5.08), 'U4.3'],
          ['U4.7', 'C28.2'], ['C28.1', (x + 20.32, y - 12.7), (x + 20.32, y)], ['U4.8', 'L3.1'],
          [(x + 45.72, y + 12.7), (x + 86.36, y + 12.7)],
          ['R15.1', 'R14.1'],
          ['Q1.3', 'R17.1'], ['R17.2', 'R18.1']]
    P += [('VIN', (x - 63.5, yr), 90), ('-12V', (x + 45.72, y + 12.7), 90), ('-12V', (x + 86.36, y + 12.7), 270)]
    L += [('FB_N', 'R15.1', 'L'), ('EN_N', 'R18.1', 'R')]

    # Output headers: every pin wired out to its rail symbol, GND pins joined per side
    for j, (hx, hy) in (('J2', J2_AT), ('J3', J3_AT)):
        lx, rx = hx - 5.08 - 5.08, hx + 7.62 + 5.08
        W += [[f'{j}.1', (lx, hy - 7.62)], [f'{j}.2', (rx, hy - 7.62)],
              [f'{j}.3', (lx + 2.54, hy - 5.08), (lx + 2.54, hy), f'{j}.7'], [f'{j}.5', (lx + 2.54, hy - 2.54)],
              [(lx + 2.54, hy - 5.08), (lx, hy - 5.08)],
              [f'{j}.4', (rx - 2.54, hy - 5.08), (rx - 2.54, hy), f'{j}.8'], [f'{j}.6', (rx - 2.54, hy - 2.54)],
              [(rx - 2.54, hy - 5.08), (rx, hy - 5.08)],
              [f'{j}.9', (lx, hy + 2.54)], [f'{j}.10', (rx, hy + 2.54)],
              [f'{j}.11', (lx, hy + 5.08)], [f'{j}.12', (rx, hy + 5.08)]]
        P += [('-12V', (lx, hy - 7.62), 90), ('-12V', (rx, hy - 7.62), 270),
              ('GND', (lx, hy - 5.08), 270), ('GND', (rx, hy - 5.08), 90),
              ('+12V', (lx, hy + 2.54), 90), ('+12V', (rx, hy + 2.54), 270),
              ('+5V', (lx, hy + 5.08), 90), ('+5V', (rx, hy + 5.08), 270)]
    # Front panel RESET: both common contacts joined to EF_UV
    x, y = SW_AT
    W += [['SW1.1', (x - 20.32, y - 5.08), (x - 20.32, y), 'SW1.3']]
    L += [('EF_UV', (x - 20.32, y - 5.08), 'L')]
    return W, P, L


TEXTS = [
    ((25.4, 26.67), 'USB-C PD 20 V INPUT: CH224A (CFG1 120k = 20 V), 5 A fuse, SMBJ20A TVS. VBUS sees only C1 + C2 '
                    '(2 uF) at attach. Use a 20 V PD charger rated 45 W or more; 60 W for the full budget', 1.8),
    ((25.4, 30.48), 'U5 TPS259470A eFuse: on 17.6-25.3 V only (R2/R3/R4), VIN ramps at 2 V/ms (C3), limit 4.1 A '
                    '(R5), auto-retry. AUXOFF holds EN_P low until VIN has ramped, then U2/U3 start', 1.5),
    ((200.66, 35.56), '+12V: U2 TPS62933F, forced PWM, 1.2 MHz, 6.8 uH. VOUT = 0.8 V x (1 + 47k / 3.3k) = 12.19 V',
     1.8),
    ((223.52, 118.11), '+5V: U3 TPS62933F, forced PWM, ~2.0 MHz (RT 10k), 3.3 uH. VOUT = 0.8 V x (1 + 68k / 13k) '
                       '= 4.98 V', 1.8),
    ((22.86, 107.95), '-12V: U4 LMR38020F inverting buck-boost, forced PWM, ~790 kHz (RT 33k), 15 uH. IC ground pins '
                      '= -12V. |VOUT| = 1.0 V x (1 + 100k / 9.1k) = 11.99 V', 1.8),
    ((22.86, 111.76), 'Q1: -12V is enabled from +12V (starts at +12V ~ 8 V, stops when +12V goes): the -12V rail '
                      'never runs alone. Internal compensation', 1.5),
    ((22.86, 200.66), 'OUTPUT: 2 x 16-pin Eurorack box header in parallel (Doepfer pinout, pin 1 = -12V)', 1.8),
    ((175.26, 200.66), 'Bulk caps, rail clamps (SS34) and rail LEDs at the headers', 1.5),
    ((289.56, 200.66), 'FRONT PANEL (as usb-power): SW1 RESET pulls U5 EN/UVLO low: all rails off,', 1.5),
    ((289.56, 204.47), 'release = restart. D8 red 3 mm +5V power LED (hand-soldered)', 1.5),
    ((22.86, 254.0), 'Budget (docs/design.md): +12V 2.5 A, +5V 2.5 A, -12V 1.0 A per rail; '
                     'all rails together <= ~39 W out on a 45 W charger (~52 W on 60 W)', 1.8),
]
