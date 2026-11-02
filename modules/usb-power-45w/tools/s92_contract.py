"""S9.2 / P2.2 placement-and-routing contract of the single board (machine-readable half of
docs/s8-single/routing-notes.md). place_s8.sync_candidate copies it into docs/s8-single/placement.json; check_s8_board.py
checks every item that can be checked on the unrouted board (pad nets, test-pad anchors, star/Kelvin geometry, clamp
proximity) and lists the copper/via items that can only be checked after routing as PENDING (never as passed).

The thermal items put a board behind the screens in calcs.json: the U2 Tj screen uses TI's JEDEC 2s2p RthetaJA, the
R109 rating TA-I's 300 mm2 copper condition and the D10 screen an effective RthetaJA target. The published rating is
conditional on these items being met by the routed board and on the post-prototype thermal tests (TH-1..TH-3).
"""

# Acceptance test pads. near = (ref, pad) the pad must sit next to, max = straight-line pad-centre limit (mm) checked on
# the unrouted board; pair = the 2.54 mm partner (probe tip + ground spring or differential pair).
TEST_POINTS = [
    dict(ref='TP1', net='VPD', size='1.0 mm round (S7 pad, DC only)', near=('Q3', '2'), max=5.0,
         measure='VPD at the module: UVLO / OVP / input-range tests (IN-1, IN-2), DC', limit='13.5-16.5 V operating; OVP trip 17.30-19.44 V; UVLO on <= 12.98 V'),
    dict(ref='TP26', net='VIN', size='1.5 mm round', near=('D24', '1'), max=9.0, pair='TP27',
         measure='D24 cathode / U2+U4 input: clamp voltage and energy under injection (CL-1), VIN ripple and ringing (EMI-1)',
         limit='CL-1: <= 30.0 V incl. ringing at 1 A / 20 ms, integral(V*I) <= 0.648 J; EMI-1: <= 1.5 V p-p at 20 MHz BW'),
    dict(ref='TP27', net='GND', size='1.5 mm round', near=('D25', '1'), max=6.0, pair='TP26',
         measure='ground-spring reference for TP26 (via to In1 at the pad)', limit='-'),
    dict(ref='TP20', net='P12_VOUT', size='1.5 mm round', near=('R109', '1'), max=11.0, pair='TP24',
         measure='R109 force node (converter side): force drop V(TP20-TP24) vs sense V(TP22-TP23) (KS-1); D26 clamp (CL-2)',
         limit='KS-1: V(TP20-TP24) >= V(TP22-TP23); CL-2: P12_VOUT <= 24.0 V'),
    dict(ref='TP24', net='+12V', size='1.5 mm round', near=('R109', '4'), max=5.0, pair='TP20',
         measure='+12V output after R109: regulation, ripple, load-step, Bode injection point (LS-1)',
         limit='11.54-12.65 V DC; <= 60 mV p-p ripple; PM > 45 deg, GM > 10 dB'),
    dict(ref='TP22', net='P12_ISP', size='1.5 mm round', near=('R109', '2'), max=10.0, pair='TP23',
         measure='Kelvin sense + (U2 ISP): V(TP22-TP23) at the CC limit (KS-1, CC-1)',
         limit='VSNS 48-52 mV at the limit; I = V/18 mOhm within 2.62-2.95 A'),
    dict(ref='TP23', net='P12_ISN', size='1.5 mm round', near=('R109', '3'), max=5.0, pair='TP22',
         measure='Kelvin sense - (U2 ISN)', limit='see TP22'),
    dict(ref='TP25', net='-12V', size='1.5 mm round', near=('U4', '1'), max=6.0,
         measure='-12V at the converter output: regulation, ripple (ground spring on D4 pin 1)',
         limit='-11.38..-12.62 V DC; <= 60 mV p-p'),
    dict(ref='TP28', net='AGND_U2', size='1.5 mm round', near=('R113', '1'), max=5.0, pair='TP29',
         measure='AGND island vs PGND star: DC offset and switching noise (GS-1); sole-bridge check with R113 lifted (GS-2)',
         limit='GS-1: |V| <= 5 mV DC, <= 50 mV p-p (20 MHz); GS-2: AGND-PGND > 10 ohm with R113 removed'),
    dict(ref='TP29', net='GND', size='1.5 mm round', near=('C82', '2'), max=9.0, pair='TP28',
         measure='PGND reference near the C82.2 star (via to In1 at the pad)', limit='-'),
    dict(ref='TP30', net='N_EN_RETURN', size='1.5 mm round', near=('Q15', '2'), max=5.0,
         measure='U4 enable AND gate mid-node: defined default (EN-1)',
         limit=('MAIN_LED_OK low: <= 0.1 V (R115 100k to PGND, <= 1 uA switch leakage); RUN high: <= 0.1 V (Q14 on); '
                'RUN low with MAIN_LED_OK high: <= 3.37 V (Q15 source follower) and U4 EN off')),
    dict(ref='TP19', net='STARTED', size='1.0 mm round (S8.5 logic pad)', near=('U12', '5'), max=25.0,
         measure='one-shot latch: startup sequence S1-S4 (logic analyser, 1 kHz+)', limit='high at first enable; cleared only by RESET/POR'),
    dict(ref='TP10', net='ARMED', size='1.0 mm round (S8.5 logic pad)', near=('U11', '1'), max=33.0,
         measure='arming delay S1-S4', limit='ARMED 0.31-0.88 s after first enable; <= 0.90 s'),
    dict(ref='TP9', net='RUN', size='1.0 mm round (S7 logic pad)', near=('U13', '3'), max=12.0,
         measure='RUN / U5 SHDN: fault latch tests S3/S4, T2', limit='low within 20 us of OV_N low'),
    dict(ref='TP5', net='MAIN_OK', size='1.0 mm round (S7 logic pad)', near=('R63', '2'), max=12.0,
         measure='U5 PGOOD/FLT: OVP/UVLO response (IN-2), source tests S1/S2', limit='low within 14 us + PGOOD deglitch of an OVP trip'),
    dict(ref='TP6', net='OV_N', size='1.0 mm round (S8 logic pad)', near=('U20', '2'), max=10.0,
         measure='rail overvoltage guard T2', limit='low <= 20 us at >= 0.5 V overdrive'),
]
# Every other existing pad is kept unchanged (S7/S8 diagnostic pads, 1.0 mm round): TP2 VPD_U1, TP3 MAIN_IN, TP4 VIN
# (damper), TP7 MAIN_IMON, TP8 GND, TP11 FAULT_LATCH, TP12 P12_OK, TP14 N12_OK, TP15 V20_OK, TP16 V3V3, TP17 REF_OV.
KEPT_DIAGNOSTIC = {'TP2': 'VPD_U1', 'TP3': 'MAIN_IN', 'TP4': 'VIN', 'TP7': 'MAIN_IMON', 'TP8': 'GND', 'TP11': 'FAULT_LATCH',
                   'TP12': 'P12_OK', 'TP14': 'N12_OK', 'TP15': 'V20_OK', 'TP16': 'V3V3', 'TP17': 'REF_OV'}

# Pre-routing proximity screens (pad-centre straight line, same net unless stated): (from, to-candidates, limit mm, why).
PROXIMITY = [
    (('D24', '1'), [('C8', '1'), ('C6', '1'), ('C7', '1'), ('C77', '1'), ('C78', '1')], 10.0, 'D24 cathode at the U2 VIN bank'),
    (('D25', '2'), [('D24', '1')], 6.0, 'D25 VIN clamp beside D24'),
    (('D26', '1'), [('C80', '1'), ('C79', '1'), ('C14', '1')], 10.0, 'D26 cathode on the P12_VOUT bank pour'),
    (('C82', '2'), [('R113', '2')], 3.0, 'R113 PGND pad on the C82.2 PGND terminal (sole star)'),
    (('R115', '1'), [('Q14', '3'), ('Q15', '2')], 5.0, 'R115 at the AND-gate mid-node'),
    (('R109', '2'), [('U2', '12')], 12.0, 'ISP sense run R109 pad 2 -> U2 pin 12'),
    (('R109', '3'), [('U2', '13')], 13.0, 'ISN sense run R109 pad 3 -> U2 pin 13'),
]

GROUND = {
    'analog_net': 'AGND_U2', 'power_net': 'GND', 'sole_link': 'R113', 'star': 'C82.2 (PGND terminal of the VCC capacitor)',
    'members_AGND_U2': ['U2.5', 'U2.17', 'R9.2', 'R110.2', 'C83.2', 'R113.1', 'TP28.1'],
    'pgnd_at_star': ['C82.2', 'R113.2'], 'maximum_link_to_C82_pad_mm': 3.0,
    'rule': ('C82.2 is PGND. R113 pin 2 (PGND) lands on the C82.2 pad copper with 3-4 PGND vias to In1 at C82.2 (TI SLVSGT7 '
             '8.4.1 items 6/7). AGND_U2 is an F.Cu trace island (U2.17/.5, R9.2, R110.2, C83.2, TP28) fed ONLY from R113 pin 1. '
             'No AGND pour on In1/In2/B.Cu, no via from AGND_U2 to any GND layer, no second 0 ohm, no net tie. In1 stays solid '
             'PGND under the island. The checker fails any AGND_U2 copper touching GND other than through R113.'),
}

KELVIN = {
    'part': 'R109 TA-I RLM12FTCMR018 18 mOhm 1 % 75 ppm 1 W on R_Shunt_1206_KelvinSplit_RLM12',
    'pads': {'1': 'force P12_VOUT (converter bank)', '2': 'sense P12_ISP -> U2 ISP pin 12 only',
             '3': 'sense P12_ISN -> U2 ISN pin 13 only', '4': 'force +12V (rail)'},
    'rule': ('Sense traces leave pads 2/3 on their +y edge within 0.6 mm of the inner (element) end, run as a 0.2 mm '
             'coupled pair (<= 0.3 mm gap) on F.Cu to U2 pins 12/13, never touch force copper, P12_VOUT or +12V pours, and '
             'carry no current. Force current enters/leaves only through pads 1/4. Sense pads stay free of pour (keep-out 0.3 mm).'),
    'residual_error': '0.2 % sense-point residual allowed in the CC-limit band (calcs plus12_buckboost)',
}

THERMAL = {
    'U2': {
        'model': 'TI SLVSGT7 6.4 RthetaJA 43.4 C/W (JEDEC 2s2p); EVM 27.5 C/W (4-layer 2/1/1/2 oz 91 x 66 mm)',
        'requirements': {
            'In1': 'solid PGND plane (0.5 oz), no slot or cut within 15 mm of the U2 centre (via antipads only)',
            'PGND_vias': '>= 10 vias 0.3/0.6 mm at the two ends of the U2 PGND land (5 per end), centres <= 1.5 mm outside '
                         'the package outline, to In1 and to the B.Cu GND pour; never in a pad',
            'VIN_area': 'F.Cu VIN pour >= 120 mm2 joining U2 pin 7, C8, C6, C7, C77, C78 and D24 K; >= 6 vias to an In2 VIN '
                        'area >= 300 mm2',
            'VOUT_area': 'F.Cu P12_VOUT pour >= 150 mm2 joining U2 pin 11, C81, C11-C14, C79, C80, R109 pad 1, D26 K and '
                         'TP20; >= 6 vias to a B.Cu P12_VOUT area >= 200 mm2',
            'B_Cu_GND': 'B.Cu GND pour >= 600 mm2 under the U2 / L1 / bank region, stitched to In1 with >= 20 vias'},
        'acceptance': 'TH-1'},
    'R109': {
        'model': 'TA-I RLM12: 1 W at 70 C with 300 mm2 of pad + trace copper; derates to 0 at 155 C',
        'requirements': {'force_copper': 'P12_VOUT (pad 1) and +12V (pad 4) F.Cu copper >= 150 mm2 each within 10 mm '
                                         '(>= 300 mm2 together), each with >= 3 vias to a same-net B.Cu or In2 area',
                         'sense_copper': 'pads 2/3: 0.2 mm traces only (no pour)'},
        'acceptance': 'TH-1 (R109 body), KS-1, CC-1'},
    'D10': {
        'model': 'SS1060 at 0.75 V x 3 A = 2.25 W; needs effective RthetaJA <= 33 C/W for Tj <= 125 C at 50 C ambient',
        'requirements': {'copper': 'VPD (anode) and MAIN_IN (cathode) F.Cu pours >= 400 mm2 each, each with >= 8 vias to a '
                                   'same-net B.Cu area >= 300 mm2'},
        'acceptance': 'TH-2'},
    'U4': {
        'model': 'LMR38020 DDA exposed pad = -12V (IC ground), not GND',
        'requirements': {'copper': 'footprint thermal vias to a -12V area >= 300 mm2 on In2 or B.Cu; no GND on the EP'},
        'acceptance': 'TH-3'},
    'U5': {
        'model': 'TPS16630 PWP exposed pad = GND; <= 0.48 W at 3 A (53 mOhm max)',
        'requirements': {'copper': 'footprint thermal vias to In1 GND'},
        'acceptance': 'TH-2 (with D10)'},
}

NETCLASS_WIDTHS_MM = {   # minimum routed widths on 1 oz outer copper (IPC-2152 screen, <= 10 C rise), pours preferred
    'VBUS / VPD / MAIN_IN / VIN (3 A, U5 limit 4.7 A)': 2.5,
    'P12_VOUT / +12V (2.95 A CC limit)': 1.5,
    '-12V (LMR38020 limit ~1.5 A)': 0.8,
    'switch nodes SW1/SW2 (U2), SW (U4)': 'short pours, no thin tracks',
    'P12_ISP / P12_ISN (Kelvin sense pair)': 0.2,
    'AGND_U2 island, FB/COMP, EN_N, N_EN_*': 0.25,
    'logic / status': 0.2,
}


def contract():
    return {'revision': 'S9.2 / P2.2', 'status': ('routing contract for the unrouted P2.2 board; pre-routing items checked '
                                                  'by tools/check_s8_board.py, copper/via items PENDING until routed'),
            'test_points': TEST_POINTS, 'kept_diagnostic_pads': KEPT_DIAGNOSTIC, 'proximity': [
                {'from': f'{a}.{b}', 'to_any': [f'{r}.{p}' for r, p in to], 'limit_mm': lim, 'why': why}
                for (a, b), to, lim, why in PROXIMITY],
            'ground': GROUND, 'kelvin': KELVIN, 'thermal': THERMAL, 'min_widths_mm': NETCLASS_WIDTHS_MM,
            'doc': 'docs/s8-single/routing-notes.md'}
