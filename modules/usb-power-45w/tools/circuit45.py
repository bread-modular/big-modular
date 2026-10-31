"""usb-power-45w S6 circuit table and drawing.

Board-protection policy: USB PD 20 V; use a 5 A contract/cable for full load.
U5 TPS16630 (60 V) limits the load path to 4.19 A nominal with PGOOD buck gating.
No adapter-power tracking; a smaller source can trip or cycle under excess load.
D1 SMBJ22A protects the high-voltage input; Q2/Q3 limit current into D9,
which separately shunts the always-on CH224A supply. D10 blocks reverse current toward USB (TPS16630 itself does not).
The three converter power stages and their individual targets are unchanged.
See docs/design.md for tolerance, transient, thermal and total-load constraints.
"""

# Supply nets drawn with power symbols (net name = symbol value); every other net is a local label.
RAIL_SYMBOL = {'GND': 'GND', 'VIN': 'VCC', '+12V': '+12V', '+5V': '+5V', '-12V': '-12V', 'V3V3': 'VCC', 'P12_RAW': 'VCC', 'P5_RAW': 'VCC', 'N12_RAW': 'VCC'}

# Q1 drawn mirrored about X: emitter (to +12V) on top, collector at the bottom.
MIRROR_X = {'Q1', 'Q2', 'Q3'}
MULTI_UNIT = {}
TEXT_LEFT = {'C9', 'C18', 'R15'}
TEXT_POS = {'Q2': ((7.62, -3.81), (7.62, -1.27), 'left'),
            'Q3': ((7.62, -3.81), (7.62, -1.27), 'left'),
            'Q1': ((5.08, -5.08), (5.08, -2.54), 'left'),
            'R8': ((6.35, -1.27), (6.35, 1.27), 'left'), 'R11': ((6.35, -1.27), (6.35, 1.27), 'left'),
            'L1': ((0, 2.54), (0, 5.08)), 'L2': ((0, 2.54), (0, 5.08)),
            'C5': ((2.54, 5.08), (2.54, 7.62), 'left'),
            'SW1': ((0, -11.43), (0, -8.89)), 'D8': ((3.81, -1.27), (3.81, 1.27), 'right')}

# Block anchors (IC centres, sheet mm).
U5_AT = (208.28, 60.96)   # eFuse
U2_AT = (368.3, 71.12)    # +12V buck
U3_AT = (368.3, 198.12)   # +5V buck
U4_AT = (111.76, 218.44)   # -12V inverting buck-boost
J2_AT, J3_AT = (45.72, 335.28), (101.6, 335.28)
EF_Y = 104.14               # eFuse set-up resistor / capacitor row
EXTRA_Y = 332.74          # bulk caps / clamps / LEDs row
SW_AT = (444.5, 332.74)  # front panel RESET button
LED_AT = (505.46, 332.74)  # front panel power LED (R22 above D8)

# JLCPCB parts, live-checked 2026-10-30/31 (assembly.py search/lookup --strict-live; stock is not a reservation).
# Every resistor and ceramic capacitor is Basic. C5/C34/C35/C36 are inherited
# Extended electrolytics: a documented unresolved Basic-policy gate, NOT an approved exception.
UNIROYAL = 'UNI-ROYAL'
R0603 = {'120k': 'C25808', '100k': 'C25803', '68k': 'C23231', '47k': 'C25819', '33k': 'C4216', '20k': 'C4184',
         '13k': 'C22797', '12k': 'C22790', '10k': 'C25804', '9.1k': 'C23260', '7.5k': 'C23234', '6.8k': 'C23212', '5.1k': 'C23186', '3.3k': 'C22978', '22k': 'C31850', '15k': 'C22809', '220k': 'C22961', '470k': 'C23178',
         '2.2k': 'C4190', '1k': 'C21190', '820': 'C23253', '33': 'C23140'}
R_MPN = {'120k': '0603WAF1203T5E', '100k': '0603WAF1003T5E', '68k': '0603WAF6802T5E', '47k': '0603WAF4702T5E',
         '33k': '0603WAF3302T5E', '20k': '0603WAF2002T5E', '13k': '0603WAF1302T5E', '12k': '0603WAF1202T5E',
         '10k': '0603WAF1002T5E', '9.1k': '0603WAF9101T5E', '7.5k': '0603WAF7501T5E', '6.8k': '0603WAF6801T5E', '5.1k': '0603WAF5101T5E', '3.3k': '0603WAF3301T5E', '22k': '0603WAF2202T5E', '15k': '0603WAF1502T5E', '220k': '0603WAF2203T5E', '470k': '0603WAF4703T5E',
         '2.2k': '0603WAF2201T5E', '1k': '0603WAF1001T5E', '820': '0603WAF8200T5E', '33': '0603WAF330JT5E'}
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
    c.append(two('F1', 'Fuse', '5A 63V', 'F1206', (63.5, 45.72), 'VBUS', 'VPD', rot=90,
                 LCSC='C553937', MPN='S1206-SD-5.0A', Manufacturer='SART(Nanjing Sart Tech)',
                 Note='63 V DC, 50 A interrupt rating. Backup fuse, NOT the USB current budget'))
    c.append(part('U1', 'CH224A', 'CH224A', 'SSOP10', (101.6, 66.04), 0,
                  {'1': 'VPD_U1', '8': 'VPD_U1', '7': 'CC1', '6': 'CC2', '4': '_PD_D', '5': '_PD_D', '11': 'GND',
                   '2': None, '3': None, '9': '_CFG1', '10': None},
                  LCSC='C42459160', MPN='CH224A', Manufacturer='WCH',
                  Note='Fixed 20 V request, independently current-limited/zener-protected supply. Requires a qualified '
                       '20 V / 5 A contract and 5 A cable for full load. No current-contract tracking; PG is not a current guarantee'))
    c.append(res('R1', '120k', (121.92, 64.77), '_CFG1', 'GND', Note='CFG1: 120k = 20 V request'))
    c.append(res('R23', '33', (55.88, 114.3), 'VPD', 'PD_SENSE',
                 Note='Q3 senses the current through this resistor; ~0.6/33 = 18 mA typical. Not a precision limiter'))
    c.append(part('Q2', 'BCX53_NXP', 'BCX53-16,115', 'SOT89', (53.34, 129.54), 0,
                  {'1': 'PD_SENSE', '2': 'VPD_U1', '3': 'PD_BASE'},
                  LCSC='C47787', MPN='BCX53-16,115', Manufacturer='Nexperia',
                  Note='80 V PNP series pass for U1 only; E=1 C/tab=2 B=3. At least 1 cm2 collector copper '
                       'per datasheet thermal example; validate U1 short and overvoltage at 50 C ambient'))
    c.append(part('Q3', 'MMBT3906', 'MMBT3906', 'SOT23', (83.82, 114.3), 0,
                  {'1': 'PD_SENSE', '2': 'VPD', '3': 'PD_BASE'},
                  LCSC='C53444', MPN='MMBT3906LT1G', Manufacturer='onsemi',
                  Note='Limits Q2 drive when drop across R23 approaches VBE; keeps D9 current near tens of mA '
                       'rather than leaving a bare resistor/zener to overheat during sustained overvoltage'))
    c.append(two('R27', 'R', '10k', 'R1206', (86.36, 137.16), 'PD_BASE', 'GND',
                 LCSC='C17902', MPN='1206W4F1002T5E', Manufacturer=UNIROYAL, Tolerance='1%',
                 Note='250 mW base pull-down; ~2 mA at 20 V, <=0.13 W at the 35.5 V rated input clamp'))
    c.append(cap('C1', '1u', 'C0603', (106.68, 137.16), 'VPD_U1', 'GND', Note='At U1 VHV/VBUS; after Q2'))
    c.append(two('D9', 'D_Zener', 'SMAZ24-13-F', 'SMA', (129.54, 137.16), 'VPD_U1', 'GND', rot=270,
                 LCSC='C155317', MPN='SMAZ24-13-F', Manufacturer='Diodes Incorporated',
                 Note='24 V +/-5% zener, rated at 25 mA; 1 W at <=50 C on the specified PCB. Q2/Q3 limit '
                      'current. Validate <30 V at U1 and limiter stability/temperature; not an ideal clamp'))
    c.append(two('D11', 'D_Schottky', 'SS34', 'SMA', (30.48, 139.7), 'VPD', 'VPD_U1', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD',
                 Note='Auxiliary reverse clamp: anode VPD_U1, cathode VPD. Discharges the 1 uF U1 cap on '
                      'input collapse without reverse-BE stress on Q2/Q3. Does not bypass the main D10 blocker'))
    c.append(two('D1', 'D_Zener', 'SMBJ22A', 'SMB', (139.7, 49.53), 'VPD', 'GND', rot=270,
                 LCSC='C10214', MPN='SMBJ22A', Manufacturer='RUILON',
                 Note='22 V stand-off, 35.5 V rated clamp at 16.9 A (10/1000 us), below U5 60 V operating max. '
                      'Does NOT alone protect U1. TVS layout overshoot and pulse derating require bench checks'))
    c.append(two('D10', 'D_Schottky', 'SS1060', 'SMC', (175.26, 45.72), 'EF_IN', 'VPD', rot=180,
                 LCSC='C2917888', MPN='SS1060', Manufacturer='ZHIDE',
                 Note='60 V / 10 A SMC reverse blocker: anode VPD, cathode EF_IN. Screen with 0.75 V at 5 A '
                      'and Tj <=125 C (conservative supplier-document envelope). Up to 3.53 W at limit; '
                      'large copper, target effective RthetaJA <=20 C/W at 50 C ambient. Bench verify'))
    c.append(cap('C2', '1u', 'C0603', (154.94, 66.04), 'EF_IN', 'GND',
                 Note='U5 IN/P_IN local cap. With C1, approximately 2 uF at attach; bulk is behind U5'))

    # ---- U5: board-side protection, not a 45 W adapter limiter; no MCU/NVM.
    c.append(part('U5', 'TPS16630PWP', 'TPS16630PWPR', 'PWP20', U5_AT, 0,
                  {'1': 'EF_IN', '2': 'EF_IN', '3': 'EF_IN', '4': None, '5': None, '6': 'EF_IN',
                   '7': 'EF_UV', '8': 'EF_OV', '9': 'GND', '10': 'EF_DVDT', '11': 'EF_ILM',
                   '12': 'GND', '13': 'EF_SHDN', '14': 'EF_IMON', '15': 'EF_FLT', '16': 'EN_P',
                   '17': None, '18': 'VIN', '19': 'VIN', '20': 'VIN', '21': 'GND'},
                  LCSC='C1849461', MPN='TPS16630PWPR', Manufacturer='Texas Instruments',
                  Note='60 V eFuse, 31 mOhm typ; 4.19 A nominal limit, auto-retry, adjustable UV/OV. '
                       'PGOOD gates U2/U3 with 8-13 ms deglitch. Reverse blocking supplied separately by D10'))
    c.append(res('R2', '100k', (154.94, EF_Y), 'VPD', 'EF_UV', Note='UVLO top: qualified-source voltage sensed before D10'))
    c.append(res('R3', '7.5k', (154.94, EF_Y + 15.24), 'EF_UV', 'GND',
                 Note='UVLO on 17.20 V / off 16.08 V nominal; tolerance/leakage corners in docs'))
    c.append(res('R28', '10k', (177.8, EF_Y - 12.7), 'VPD', '_OV_TOP',
                 Note='In series with R4: 130k OVP top; enough falling-threshold margin to recover at 21 V'))
    c.append(res('R4', '120k', (177.8, EF_Y), '_OV_TOP', 'EF_OV', Note='OVP top with R28; independent of UVLO and RESET'))
    c.append(res('R24', '6.8k', (177.8, EF_Y + 15.24), 'EF_OV', 'GND',
                 Note='OVP off 24.14 V nominal; worst-case trip below 26 V, falling threshold above 21 V'))
    c.append(cap('C3', '22n', 'C0603', (200.66, EF_Y), 'EF_DVDT', 'GND',
                 Note='dVdt: 2 uA x 25 / 22 nF = 2.27 V/ms; ~9 ms ramp, followed by PGOOD delay'))
    # C4 (old ITIMER) removed: TPS16630 has internal overload/auto-retry timing.
    c.append(res('R5', '3.3k', (223.52, EF_Y), 'EF_ILM', '_ILIM_SERIES',
                 Note='Series R5 + R29 = 4.3k: 4.186 A nominal. +/-10% IC and R tolerance/TCR screen '
                      'gives 3.693-4.698 A; +25 mA auxiliary <4.75 A board-side guard. Not a rail OCP'))
    c.append(res('R29', '1k', (223.52, EF_Y + 15.24), '_ILIM_SERIES', 'GND',
                 Note='Series with R5. Both parts Basic; single 4.3k C23159 was Preferred Extended. '
                      'Do not bypass: R5 alone can exceed the 5 A connector path'))
    c.append(res('R6', '100k', (246.38, EF_Y), 'VIN', 'EN_P',
                 Note='Safe EN divider + U5 PGOOD open drain. Fault turnoff has 8-13 ms deglitch; not instant'))
    c.append(res('R7', '10k', (246.38, EF_Y + 15.24), 'EN_P', 'GND', Note='EN_P = VIN/11 while PGOOD is released'))
    c.append(res('R25', '100k', (269.24, EF_Y), 'VPD', 'EF_FLT',
                 Note='FLT pull-up for test point only (raw input voltage logic, NOT MCU-safe). Not tied to EN: avoids fault chatter'))
    c.append(res('R26', '20k', (292.1, EF_Y), 'EF_IMON', 'GND',
                 Note='IMON = 0.558 V/A typical. Do not bypass with a capacitor; TP7 uses system GND'))
    c.append(cap('C5', '47u', 'CP63', (243.84, 49.53), 'VIN', 'GND', Note='Bulk behind U5; input damping'))

    for i, (net, x) in enumerate([('VPD', 50.8), ('VPD_U1', 76.2), ('EF_IN', 116.84), ('VIN', 149.86),
                                  ('EN_P', 182.88), ('EF_FLT', 215.9), ('EF_IMON', 248.92), ('GND', 281.94)], 1):
        c.append(part(f'TP{i}', 'TestPoint', net, 'TP', (x, 153.67), 0, {'1': net},
                      Note='Bare test pad, no fitted part / no assembly placement'))

    # ---- +12V and +5V: unchanged power stages; EN_P from U5 PGOOD
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
    c.append(two('D2', 'D_Schottky', 'SS34', 'SMA', (193.04, ey), '+12V', 'GND', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD', Note='Clamp: +12V never below GND'))
    c.append(res('R19', '10k', (210.82, ey), '+12V', '_LED_P12', Note='+12V LED, ~1 mA'))
    c.append(two('D5', 'LED', 'RED', 'LED0603', (210.82, ey + 7.62), 'GND', '_LED_P12', rot=90,
                 LCSC='C2286', MPN='KT-0603R', Manufacturer='Hubei KENTO', Note='+12V on'))
    c.append(cap('C35', '100u', 'CP63', (238.76, ey), '+5V', 'GND', Note='+5V bulk at the headers'))
    c.append(two('D3', 'D_Schottky', 'SS34', 'SMA', (256.54, ey), '+5V', 'GND', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD', Note='Clamp: +5V never below GND'))
    c.append(res('R20', '1k', (274.32, ey), '+5V', '_LED_P5', Note='+5V LED, ~3 mA'))
    c.append(two('D6', 'LED', 'RED', 'LED0603', (274.32, ey + 7.62), 'GND', '_LED_P5', rot=90,
                 LCSC='C2286', MPN='KT-0603R', Manufacturer='Hubei KENTO', Note='+5V on'))
    c.append(cap('C36', '100u', 'CP63', (302.26, ey), 'GND', '-12V', Note='-12V bulk at the headers'))
    c.append(two('D4', 'D_Schottky', 'SS34', 'SMA', (320.04, ey), 'GND', '-12V', rot=270,
                 LCSC='C8678', MPN='SS34', Manufacturer='MDD', Note='Clamp: -12V never above GND'))
    c.append(two('D7', 'LED', 'RED', 'LED0603', (337.82, ey), '_LED_N12', 'GND', rot=90,
                 LCSC='C2286', MPN='KT-0603R', Manufacturer='Hubei KENTO', Note='-12V on'))
    c.append(res('R21', '10k', (337.82, ey + 7.62), '_LED_N12', '-12V', Note='-12V LED, ~1 mA'))

    # ---- Front panel, as modules/usb-power: SMT RESET button on the eFuse EN/UVLO and a 3 mm +5V power LED
    sx, sy = SW_AT
    c.append(part('SW1', 'TL3340AF160QG', 'TL3340AF160QG', 'TL3340', SW_AT, 0,
                  {'1': 'EF_SHDN', '3': 'EF_SHDN', '2': 'GND', 'MP': None},
                  LCSC='C2886925', MPN='TL3340AF160QG', Manufacturer='E-Switch',
                  Note='RESET: press grounds U5 SHDN (internally pulled up to 2.7 V), release restarts in '
                       'the valid input window. Input off is not a guaranteed module discharge/reset pulse. '
                       'PGOOD follows shutdown after its deglitch. Case MP floating'))
    lx, ly = LED_AT
    c.append(res('R22', '1k', (lx, ly), '+5V', '_LED_PANEL', Note='Panel LED, ~3 mA (as usb-power R32)'))
    c.append(two('D8', 'LED', 'RED 3mm', 'LED3EDGE', (lx, ly + 7.62), 'GND', '_LED_PANEL', rot=90,
                 Note='Front panel +5V POWER LED, as usb-power D10: red 3 mm THT, leads formed 90 degrees, '
                      'hand-soldered (not JLC-assembled). +5V presence only'))

    # VIN is driven by the U5 OUT pin (power output): no flag there. VPD gets one (fuse and connector are passive).
    for ref, net, at in (('#FLG01', 'GND', (30.48, 110.49)), ('#FLG02', 'VPD', (99.06, 45.72)),
                         ('#FLG03', '-12V', (182.88, 231.14)), ('#FLG04', '+12V', (429.26, 71.12)),
                         ('#FLG05', '+5V', (429.26, 198.12)),
                         ('#FLG06', 'VPD_U1', (119.38, 133.35)), ('#FLG07', 'EF_IN', (182.88, 45.72))):
        c.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, at, 0, {'1': net}))
    from protection6 import extend
    return extend(c, part, two, res, cap)


def drawing():
    """WIRES, POWER (net, point, rotation) and LABELS (net, point, side) of the wired blocks."""
    W, P, L = [], [], []
    # Input power path and the separately protected always-on CH224A branch.
    W += [['J1.A4', 'F1.1'], ['F1.2', 'D10.2'], ['D10.1', 'U5.1'],
          ['U5.6', (195.58, 45.72)], ['U5.18', 'U5.20'], ['U5.18', (259.08, 45.72)],
          ['U1.1', (83.82, 50.8), (83.82, 55.88), 'U1.8'],
          ['J1.A5', (76.2, 50.8), (76.2, 60.96), 'U1.7'],
          ['J1.B5', (73.66, 53.34), (73.66, 66.04), 'U1.6'],
          ['U1.4', (81.28, 71.12), (81.28, 76.2), 'U1.5'], ['U1.9', 'R1.1'],
          ['C1.1', 'D9.1'], ['Q3.3', 'R27.1'], ['R23.2', 'Q2.1'],
          ['Q3.1', (71.12, 114.3), (71.12, 121.92), (55.88, 121.92)],
          ['R2.2', 'R3.1'], ['R5.2', 'R29.1'], ['R28.2', 'R4.1'], ['R4.2', 'R24.1']]
    P += [('VIN', (259.08, 45.72), 270)]
    L += [('VBUS', (55.88, 45.72), 'R'), ('CC1', (58.42, 50.8), 'R'), ('CC2', (58.42, 53.34), 'R'),
          ('VPD', (129.54, 45.72), 'U'), ('EF_IN', (182.88, 45.72), 'U'),
          ('VPD_U1', (83.82, 50.8), 'U'),  ('VPD_U1', 'C1.1', 'U'), ('PD_SENSE', (71.12, 121.92), 'R'), ('PD_BASE', 'R27.1', 'R'),
          ('EF_UV', 'R3.1', 'L'), ('EF_OV', 'R24.1', 'L')]

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

    remap = {'+12V': 'P12_RAW', '+5V': 'P5_RAW', '-12V': 'N12_RAW'}
    P = [(remap.get(n,n),pt,rot) for n,pt,rot in P]
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
    # Front panel RESET: both common contacts joined to dedicated SHDN
    x, y = SW_AT
    W += [['SW1.1', (x - 20.32, y - 5.08), (x - 20.32, y), 'SW1.3']]
    L += [('RESET_BTN_N', (x - 20.32, y - 5.08), 'L')]
    from protection6 import extra_drawing
    added = extra_drawing()
    pin_nets = {p['ref']+'.'+pin: net for p in circuit() for pin,net in p['pins'].items()}
    for line in added:
        net = pin_nets[line[0]]
        if net in RAIL_SYMBOL:
            P.append((net, line[0], 90))
        elif not net.startswith('_'):
            L.append((net, line[0], 'L'))
    W += added
    return W, P, L


TEXTS = [
    ((25.4, 25.4), 'S6 INPUT: USB PD 20 V; 5 A contract/cable for full load. Board eFuse limit 4.19 A; no adapter-power tracking.', 1.8),
    ((25.4, 30.48), 'U5 TPS16630: 60 V input; UVLO 17.2 V / OVP 24.14 V nominal; ~9 ms ramp + PGOOD delay; auto-retry.', 1.5),
    ((25.4, 99.06), 'U1 ONLY: Q2/Q3 + R23 current limiter (~18 mA typ) feeds a 24 V shunt. Verify U1 <30 V.', 1.5),
    ((149.86, 139.7), 'UVLO / OVP / ramp / current / enable / diagnostic networks', 1.5),
    ((25.4, 172.72), 'TP5 = MAIN_OK; TP6 = FAULT_LATCH; TP7 = 0.558 V/A typical; TP8 = system GND. D10 blocks USB backfeed.', 1.5),
    ((320.04, 35.56), '+12V: TPS62933F, forced PWM, 1.2 MHz, 6.8 uH', 1.8),
    ((320.04, 40.64), 'Unchanged divider: 0.8 x (1 + 47k/3.3k) = 12.19 V nominal', 1.5),
    ((320.04, 162.56), '+5V: TPS62933F, forced PWM, ~2.0 MHz, 3.3 uH', 1.8),
    ((320.04, 167.64), 'Unchanged divider: 0.8 x (1 + 68k/13k) = 4.98 V nominal', 1.5),
    ((25.4, 184.15), '-12V: LMR38020F inverting buck-boost, forced PWM, ~790 kHz, 15 uH. IC ground = -12V.', 1.8),
    ((25.4, 189.23), 'Unchanged power stage. Q1 enables from +12V, not a precision all-rail supervisor. Validate loop stability.', 1.5),
    ((25.4, 309.88), 'OUTPUTS: parallel 16-pin Eurorack headers (pin 1 = -12V). Not for paralleling independent supplies.', 1.8),
    ((175.26, 316.23), 'RAW bulk caps, polarity clamps and local SMD LEDs', 1.5),
    ((414.02, 309.88), 'PANEL: SW1 common latched RESET; D8 moved to status block', 1.5),
    ((414.02, 314.96), 'No guaranteed discharge time / complete module reset', 1.5),
    ((25.4, 378.46), 'TARGETS: +12V 2.5 A / +5V 2.5 A / -12V 1.0 A = 54.5 W total; simultaneous operation needs bench qualification.', 1.8),
    ((25.4, 383.54), 'Board limit: 4.3k = 3.3k + 1k; new aux budget 50 mA, screen <=4.748 A. Full-load estimate ~66 W input, not a rating.', 1.5),
    ((25.4, 388.62), 'D10 upgraded to 10 A SMC; thermal copper required. Smaller sources may trip/cycle. Test thermal / PD / surge / startup.', 1.5),
]

from protection6 import TEXTS6
TEXTS += TEXTS6

for _ref in ('Q4','Q5','Q6','Q7','Q8','Q9','Q10'):
    TEXT_POS[_ref] = ((5.08,-2.54),(5.08,0),'left')

for _ref in ('D8','D16','D17','D18'):
    TEXT_POS[_ref] = ((5.08,-1.27),(5.08,1.27),'left')
