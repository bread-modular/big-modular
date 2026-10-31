"""Hand-written R3 BASE routing batches for tools/route_base_r3.py (native board coordinates, mm).

Each batch: 'zones' [(layer, net, polygon, pad_connection)], 'vias' {key: (net, (x, y)[, (dia, drill)])},
'tracks' [(net, layer, width, start, waypoints, end)] with ends ('pad', ref, num) | ('padu', ref, num, (x, y))
| ('via', key) | ('trk', 'batch/trk/i', (x, y)), optional 'delete' [(kind, key-or-uuid)].
Every coordinate below was chosen by hand for that one connection and reviewed on a render + DRC.
"""
OUTLINE = [(49.75, 62.275), (150.25, 62.275), (150.25, 102.275), (147.75, 102.275), (147.75, 94.275),
           (136.75, 94.275), (136.75, 102.275), (63.25, 102.275), (63.25, 94.275), (52.25, 94.275),
           (52.25, 102.275), (49.75, 102.275)]

BATCHES = {}

# PL1: placement refinements of AI-placed, unrouted SMD around U5 (TPS16630 main eFuse), so its
# control pins escape without crossing each other or the EF_IN / VIN power paths:
#  - C2 (EF_IN 1u bypass) <-> C3 (EF_DVDT 22n) swap positions (same 0603 footprint, same courtyard):
#    C2 now sits beside the EF_IN pins 1-3 with its GND pad next to the exposed pad; C3 beside DVDT pin 10.
#  - R5 rotated 90 -> 270 in place: R5.1 (EF_ILM) faces its via, R5.2 lines up with R29.1.
#  - R26 rotated 0 -> 180 in place: R26.1 (EF_IMON) directly above U5 pin 14, MAIN_OK escapes between.
# Same positions/courtyards otherwise; checked by tools/check_stack.py geometry after the batch.
BATCHES['PL1-u5-refine'] = {
    'moves': [('C2', (55.65, 80.3), 90), ('C3', (64.45, 83.05), 90), ('R5', None, 270), ('R26', None, 180)],
}

# P1: planes. In1 = solid GND over the whole board (no tracks on In1, ever). In2 is split
# deliberately into two one-piece areas: a VIN band (U5 OUT pins -> XB1 VIN pins 3-6, ~4.7 A
# screen; 9.7 mm wide, so the 0.5 oz inner copper is ~20 A/mm2, below a 1 oz outer 2.5 mm track) and
# the always-on V3V3 logic plane around it (U-shape, 40 V3V3 pads on every logic block). 0.6 mm
# between the two outlines. Solid pad connection: header/connector pins carry rail current.
VIN_BAND = [(49.75, 72.35), (62.25, 72.35), (62.25, 74.65), (97.15, 74.65), (97.15, 84.35), (49.75, 84.35)]
V3V3_U = [(49.75, 62.275), (150.25, 62.275), (150.25, 102.275), (147.75, 102.275), (147.75, 94.275),
          (136.75, 94.275), (136.75, 102.275), (63.25, 102.275), (63.25, 94.275), (52.25, 94.275),
          (52.25, 102.275), (49.75, 102.275), (49.75, 84.95), (97.75, 84.95), (97.75, 74.05), (62.85, 74.05),
          (62.85, 71.75), (49.75, 71.75)]
BATCHES['P1-planes'] = {
    'zones': [('In1.Cu', 'GND', OUTLINE, 'solid'), ('In2.Cu', 'V3V3', V3V3_U, 'solid'),
              ('In2.Cu', 'VIN', VIN_BAND, 'solid')],
}

# PL2: R4 and R28 (VPD -> R28 -> R4 -> EF_OV, the U5 OVP divider top) rotated 180 in place, so the
# series link R28.2 - R4.1 is one short hop and EF_OV (R4.2) / VPD (R28.1) face their sources.
BATCHES['PL2-ovp-refine'] = {'moves': [('R4', None, 180), ('R28', None, 180)]}

# I1: USB input power path and the U5 front-row control escapes.
#  VBUS: J1.A4 -> F 0.55 mm -> F1.1 directly; J1.A9 (other side of the CC pins) -> 2 vias -> B VBUS
#  pour under F1/J1 -> 2 vias at the A4 track (the 4.7 A splits over both cable VBUS pins).
#  (CC1/CC2: own batch I2, through the F1 pad gap and the B corridor between the D10 heat pours.)
#  VPD (F1.2 -> D10 anode, D1 TVS, R2, R23): F pour + B pour under D10.2 with 10 vias.
#  EF_IN (D10 cathode -> U5 IN pins 1-3,6 + C2): F pour on D10.1, F pour on the U5 IN pins/C2, B pour
#  linking them (wide), 8 + 11 vias. D10 dissipates ~3.5 W (screen): each terminal spreads on its OWN
#  net on F and B (never GND). Non-GND copper kept >= 3.5 mm from the bracket hole (57.75, 89.275)
#  on F (steel nut) and the B EF_IN pour notched around it.
#  U5: pins 9/12, C2.2, C3.2, R24.2 GND straight into the exposed pad (13 thermal vias to In1/B).
#  EF_UV: U5.7 -> F down the free corridor east of the nut -> R3.1 -> B (south of D10) -> R2.2.
#  EF_OV: U5.8 -> F east under C3 -> R24.1 -> R4.2.  DVDT: U5.10 -> C3.1.
_EFIN_VIA_U5 = [(55.6, 83.0), (55.6, 83.85), (55.6, 84.75), (56.5, 84.75), (57.4, 84.75), (58.3, 84.75),
                (59.2, 84.75), (60.1, 84.75)]
_EFIN_VIA_D10 = [(64.05, 86.7), (64.05, 87.6), (64.05, 88.5), (64.05, 89.4), (65.0, 85.85), (65.9, 85.85),
                 (66.8, 85.85), (65.0, 90.25), (65.9, 90.25), (66.8, 90.25), (67.65, 87.0), (67.65, 88.0),
                 (67.65, 89.0)]
_VPD_VIA_D10 = [(70.85, 87.0), (70.85, 88.0), (70.85, 89.0), (71.9, 90.25), (72.8, 90.25), (73.7, 90.25),
                (72.6, 85.6), (73.5, 85.6), (74.45, 87.6), (76.1, 83.95)]
BATCHES['I1-input-power'] = {
    'zones': [
        ('B.Cu', 'VBUS', [(65.5, 93.1), (73.1, 93.1), (73.1, 94.75), (65.5, 94.75)], 'solid'),
        ('F.Cu', 'VPD', [(70.25, 93.75), (70.25, 86.0), (70.9, 84.15), (77.35, 84.15), (77.35, 87.0), (75.8, 87.0),
                         (75.8, 91.2), (75.1, 91.2), (75.1, 93.75)], 'solid'),
        ('B.Cu', 'VPD', [(70.6, 83.6), (77.6, 83.6), (77.6, 87.7), (75.75, 87.7), (75.75, 92.0), (70.6, 92.0)], 'solid'),
        ('F.Cu', 'EF_IN', [(63.2, 85.4), (68.0, 85.4), (68.0, 91.4), (63.2, 91.4)], 'solid'),
        ('F.Cu', 'EF_IN', [(54.95, 80.65), (56.55, 80.65), (56.55, 82.2), (60.65, 82.2), (60.65, 85.35),
                           (54.95, 85.35)], 'solid'),
        ('B.Cu', 'EF_IN', [(54.95, 82.6), (68.0, 82.6), (68.0, 91.95), (60.75, 91.95), (60.75, 86.35),
                           (54.95, 86.35)], 'solid'),
    ],
    'vias': {
        **{f'b3-efin-u5-{i}': ('EF_IN', p) for i, p in enumerate(_EFIN_VIA_U5)},
        **{f'b3-efin-d10-{i}': ('EF_IN', p) for i, p in enumerate(_EFIN_VIA_D10)},
        **{f'b3-vpd-d10-{i}': ('VPD', p) for i, p in enumerate(_VPD_VIA_D10)},
        'b3-vbus-1': ('VBUS', (71.9, 94.35)), 'b3-vbus-2': ('VBUS', (72.65, 93.95)),
        'b3-vbus-3': ('VBUS', (66.8, 94.3)), 'b3-vbus-4': ('VBUS', (65.95, 93.55)),
        'b3-uv-1': ('EF_UV', (63.25, 92.35)), 'b3-uv-2': ('EF_UV', (76.3, 88.7)),
        'b3-gnd-r3': ('GND', (66.2, 91.15)),
        'b3-gnd-d1-1': ('GND', (79.6, 87.3)), 'b3-gnd-d1-2': ('GND', (80.6, 87.3)), 'b3-gnd-d1-3': ('GND', (81.95, 85.55)),
    },
    'tracks': [
        ('VBUS', 'F.Cu', 0.55, ('pad', 'J1', 'A4'), [], ('via', 'b3-vbus-3')),
        ('VBUS', 'F.Cu', 0.55, ('via', 'b3-vbus-3'), [], ('pad', 'F1', '1')),
        ('VBUS', 'F.Cu', 0.5, ('via', 'b3-vbus-4'), [], ('via', 'b3-vbus-3')),
        ('VBUS', 'F.Cu', 0.5, ('pad', 'J1', 'A9'), [(71.7, 94.85)], ('via', 'b3-vbus-1')),
        ('VBUS', 'F.Cu', 0.5, ('via', 'b3-vbus-1'), [], ('via', 'b3-vbus-2')),
        ('GND', 'F.Cu', 0.5, ('pad', 'D1', '2'), [(79.6, 86.5)], ('via', 'b3-gnd-d1-1')),
        ('GND', 'F.Cu', 0.5, ('pad', 'D1', '2'), [(80.6, 86.5)], ('via', 'b3-gnd-d1-2')),
        ('GND', 'F.Cu', 0.5, ('pad', 'D1', '2'), [(81.2, 85.55)], ('via', 'b3-gnd-d1-3')),
        ('GND', 'F.Cu', 0.4, ('pad', 'J1', 'A1'), [], ('padu', 'J1', 'S1', (64.93, 96.695))),
        ('GND', 'F.Cu', 0.4, ('pad', 'J1', 'A12'), [], ('padu', 'J1', 'S1', (73.57, 96.695))),
        ('GND', 'F.Cu', 0.4, ('pad', 'R3', '2'), [], ('via', 'b3-gnd-r3')),
        ('GND', 'F.Cu', 0.4, ('pad', 'U5', '9'), [(62.325, 81.8)], ('padu', 'U5', '21', (60.05, 80.3))),
        ('GND', 'F.Cu', 0.4, ('pad', 'U5', '12'), [(62.325, 78.8)], ('padu', 'U5', '21', (60.05, 80.3))),
        ('GND', 'F.Cu', 0.4, ('pad', 'C2', '2'), [(57.0, 79.525)], ('padu', 'U5', '21', (60.05, 80.3))),
        ('GND', 'F.Cu', 0.3, ('pad', 'C3', '2'), [(63.9, 81.95), (63.1, 81.95)], ('padu', 'U5', '21', (60.05, 80.3))),
        ('GND', 'F.Cu', 0.3, ('pad', 'R24', '2'), [(63.1, 79.075)], ('padu', 'U5', '21', (60.05, 80.3))),
        ('EF_DVDT', 'F.Cu', 0.25, ('pad', 'U5', '10'), [(62.975, 83.6)], ('pad', 'C3', '1')),
        ('EF_UV', 'F.Cu', 0.2, ('pad', 'U5', '7'), [(61.025, 85.25), (62.6, 86.85), (62.6, 91.7)], ('via', 'b3-uv-1')),
        ('EF_UV', 'F.Cu', 0.25, ('via', 'b3-uv-1'), [], ('pad', 'R3', '1')),
        ('EF_UV', 'B.Cu', 0.25, ('via', 'b3-uv-1'), [(63.45, 92.55), (76.3, 92.55)], ('via', 'b3-uv-2')),
        ('EF_UV', 'F.Cu', 0.25, ('via', 'b3-uv-2'), [], ('pad', 'R2', '2')),
        ('EF_OV', 'F.Cu', 0.2, ('pad', 'U5', '8'), [(61.675, 84.6), (65.45, 84.6), (65.45, 80.725)], ('pad', 'R24', '1')),
        ('EF_OV', 'F.Cu', 0.2, ('pad', 'R4', '2'), [(66.575, 78.0), (65.45, 78.0), (65.45, 80.0)], ('pad', 'R24', '1')),
    ],
}

# PL3: CH224A branch refinement (all unrouted AI placements). As placed, PD_SENSE (Q2.E/Q3.B/R23),
# PD_BASE (Q2.B/Q3.C/R27) and VPD_U1 (Q2.C tab/D11/D9/C1/U1) were mutually enclosed and the CC lines
# could only reach U1 from the far side. R23 (33R VPD->PD_SENSE) moves from the D10 side (75.0, 92.3)
# into the free spot west of Q2 (71.5, 80.5) so its VPD pin sits on the VPD pour edge and its
# PD_SENSE pin faces Q2.E; U1 is turned 180 deg in place so CC1/CC2 face the USB side.
BATCHES['PL3-ch224-refine'] = {'moves': [('R23', (71.5, 80.5), 90), ('U1', None, 270)]}

# I2: CC lines and the CH224A low-current branch (F, short B hops only).
#  CC1/CC2: J1 -> F through the F1 pad gap -> vias in the D10 body gap -> B corridor between the
#  D10 heat pours -> B rows south of Q2/Q3 -> B rows south of D1's GND vias -> vias at U1 CC pins.
#  VPD: pour -> R23.1 -> row south of Q2/Q3 -> Q3.E -> TP1; R23.1 -> west column -> R28.1 -> D11.K.
#  PD_SENSE: R23.2 -> Q2.E -> over the Q2 tab -> Q3.B. PD_BASE: R27 -> D11 body gap -> Q3.C, and
#  Q2.B -> B hop -> R27. VPD_U1: Q2 tab -> B hop -> D11.A -> D9 -> C1 -> TP2 -> U1.1 (+ B to U1.8).
BATCHES['I2-cc-ch224'] = {
    'vias': {
        'b3-cc1': ('CC1', (68.9, 91.4)), 'b3-cc2': ('CC2', (69.6, 90.6)),
        'b3-cc1-u1': ('CC1', (83.95, 87.5)), 'b3-cc2-u1': ('CC2', (82.95, 87.5)),
        'b3-pdb-1': ('PD_BASE', (72.9, 82.3)), 'b3-pdb-2': ('PD_BASE', (76.85, 74.95)),
        'b3-vu1-tab': ('VPD_U1', (77.5, 82.2)), 'b3-vu1-d11': ('VPD_U1', (78.85, 74.75)),
        'b3-vu1-u1a': ('VPD_U1', (84.95, 87.5)), 'b3-vu1-u1b': ('VPD_U1', (86.3, 79.15)),
        'b3-gnd-r27': ('GND', (79.6, 71.65)), 'b3-gnd-d9c1': ('GND', (84.35, 76.35)),
        'b3-gnd-u1': ('GND', (87.45, 83.35)),
    },
    'tracks': [
        ('CC1', 'F.Cu', 0.2, ('pad', 'J1', 'A5'), [(68.0, 94.55), (68.9, 93.65)], ('via', 'b3-cc1')),
        ('CC2', 'F.Cu', 0.2, ('pad', 'J1', 'B5'), [(71.0, 94.55), (69.6, 94.55)], ('via', 'b3-cc2')),
        ('CC1', 'B.Cu', 0.2, ('via', 'b3-cc1'), [(70.2, 91.4), (70.2, 83.35), (78.3, 83.35), (78.3, 88.7), (83.95, 88.7)],
         ('via', 'b3-cc1-u1')),
        ('CC2', 'B.Cu', 0.2, ('via', 'b3-cc2'), [(69.6, 82.9), (78.75, 82.9), (78.75, 88.2), (82.95, 88.2)],
         ('via', 'b3-cc2-u1')),
        ('CC1', 'F.Cu', 0.2, ('via', 'b3-cc1-u1'), [], ('pad', 'U1', '7')),
        ('CC2', 'F.Cu', 0.2, ('via', 'b3-cc2-u1'), [], ('pad', 'U1', '6')),
        ('VPD', 'F.Cu', 0.25, ('via', 'b3-vpd-d10-6'), [(72.6, 83.25), (81.3, 83.25)], ('pad', 'Q3', '2')),
        ('VPD', 'F.Cu', 0.3, ('pad', 'R23', '1'), [(71.5, 84.5)], ('via', 'b3-vpd-d10-6')),
        ('VPD', 'F.Cu', 0.25, ('pad', 'Q3', '2'), [(81.5, 81.1)], ('pad', 'TP1', '1')),
        ('VPD', 'F.Cu', 0.25, ('pad', 'R23', '1'), [(70.2, 81.0), (70.2, 77.7), (72.525, 77.7)], ('pad', 'R28', '1')),
        ('VPD', 'F.Cu', 0.25, ('pad', 'R28', '1'), [], ('pad', 'D11', '1')),
        ('PD_SENSE', 'F.Cu', 0.25, ('pad', 'R23', '2'), [(72.5, 79.15)], ('pad', 'Q2', '1')),
        ('PD_SENSE', 'F.Cu', 0.2, ('pad', 'Q2', '1'), [(78.66, 79.15), (78.66, 81.1)], ('pad', 'Q3', '1')),
        ('PD_BASE', 'F.Cu', 0.25, ('pad', 'R27', '1'), [(76.85, 74.3)], ('via', 'b3-pdb-2')),
        ('PD_BASE', 'F.Cu', 0.2, ('via', 'b3-pdb-2'), [(76.85, 77.6), (80.45, 77.6), (80.45, 79.0)], ('pad', 'Q3', '3')),
        ('PD_BASE', 'F.Cu', 0.25, ('pad', 'Q2', '3'), [], ('via', 'b3-pdb-1')),
        ('PD_BASE', 'B.Cu', 0.25, ('via', 'b3-pdb-1'), [(72.9, 75.6), (76.2, 75.6)], ('via', 'b3-pdb-2')),
        ('VPD_U1', 'F.Cu', 0.4, ('pad', 'Q2', '2'), [(77.5, 81.0)], ('via', 'b3-vu1-tab')),
        ('VPD_U1', 'B.Cu', 0.3, ('via', 'b3-vu1-tab'), [(78.85, 80.5)], ('via', 'b3-vu1-d11')),
        ('VPD_U1', 'F.Cu', 0.3, ('via', 'b3-vu1-d11'), [], ('pad', 'D11', '2')),
        ('VPD_U1', 'F.Cu', 0.3, ('pad', 'D11', '2'), [(80.45, 75.6)], ('pad', 'D9', '1')),
        ('VPD_U1', 'F.Cu', 0.3, ('pad', 'D9', '1'), [(82.6, 75.45), (82.6, 78.4)], ('pad', 'C1', '1')),
        ('VPD_U1', 'F.Cu', 0.3, ('pad', 'C1', '1'), [], ('pad', 'TP2', '1')),
        ('VPD_U1', 'F.Cu', 0.3, ('pad', 'TP2', '1'), [], ('via', 'b3-vu1-u1b')),
        ('VPD_U1', 'F.Cu', 0.3, ('via', 'b3-vu1-u1b'), [], ('pad', 'U1', '1')),
        ('VPD_U1', 'B.Cu', 0.3, ('via', 'b3-vu1-u1a'), [(85.4, 87.05), (85.4, 80.0)], ('via', 'b3-vu1-u1b')),
        ('VPD_U1', 'F.Cu', 0.3, ('pad', 'U1', '8'), [], ('via', 'b3-vu1-u1a')),
        ('Net-(U1-DM)', 'F.Cu', 0.25, ('pad', 'U1', '5'), [], ('pad', 'U1', '4')),
        ('Net-(U1-CFG1)', 'F.Cu', 0.2, ('pad', 'U1', '9'), [(86.4, 87.4), (88.0, 87.4)], ('pad', 'R1', '1')),
        ('GND', 'F.Cu', 0.4, ('pad', 'U1', '11'), [], ('via', 'b3-gnd-u1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R1', '2'), [], ('via', 'b3-gnd-u1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R27', '2'), [], ('via', 'b3-gnd-r27')),
        ('GND', 'F.Cu', 0.4, ('pad', 'D9', '2'), [], ('via', 'b3-gnd-d9c1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C1', '2'), [], ('via', 'b3-gnd-d9c1')),
    ],
}

# PL4: TP7 (EF_IMON test pad) moves 0.7 mm toward the U14 gap, so MAIN_OK can drop to its via between
# the R26 pads and R26.2 gets its own GND via.
BATCHES['PL4-tp7'] = {'moves': [('TP7', (60.3, 72.9), None)]}

# U5b: U5 OUT/rear-row escapes. VIN: F pour on pins 18-20 + 4 x 0.8/0.4 vias into the In2 VIN band.
# EF_ILM: pin 11 -> via -> B row north of the U5 rear pins -> via -> R5.1; R5.2 -> R29.1, R29.2 GND.
# EF_IMON: pin 14 -> R26.1 -> TP7. MAIN_OK pins 15+16 -> between the R26 pads -> via (B in a later
# batch) -> B row -> TP5, R63.2. RUN pin 13 -> via -> B -> Q10 gate (rest of RUN later). TP3 (EF_IN) -> via -> B EF_IN pour.
BATCHES['U5b-rear'] = {
    'zones': [('F.Cu', 'VIN', [(56.7, 73.95), (58.75, 73.95), (58.75, 77.3), (56.7, 77.3)], 'solid')],
    'vias': {
        'b3-vin-u5-1': ('VIN', (57.1, 74.65)), 'b3-vin-u5-2': ('VIN', (57.95, 74.65)),
        'b3-vin-u5-3': ('VIN', (57.1, 75.5)), 'b3-vin-u5-4': ('VIN', (57.95, 75.5)),
        'b3-mok-tp5': ('MAIN_OK', (74.65, 74.45)), 'b3-mok-r63': ('MAIN_OK', (84.475, 73.0)),
        'b3-ilm-1': ('EF_ILM', (63.6, 76.3)), 'b3-ilm-2': ('EF_ILM', (55.65, 75.25)),
        'b3-gnd-r29': ('GND', (52.7, 76.6)), 'b3-gnd-r26': ('GND', (59.2, 74.3)),
        'b3-mok-u5': ('MAIN_OK', (60.05, 74.2)), 'b3-run-u5': ('RUN', (61.9, 74.9)),
        'b3-run-q10': ('RUN', (66.8, 79.2)), 'b3-gnd-q10': ('GND', (66.8, 83.15)),
        'b3-efin-tp3': ('EF_IN', (64.75, 77.55)),
    },
    'tracks': [
        ('EF_ILM', 'F.Cu', 0.25, ('pad', 'U5', '11'), [(62.975, 76.5)], ('via', 'b3-ilm-1')),
        ('EF_ILM', 'B.Cu', 0.2, ('via', 'b3-ilm-1'), [(63.6, 77.6), (56.3, 77.6)], ('via', 'b3-ilm-2')),
        ('EF_ILM', 'F.Cu', 0.25, ('via', 'b3-ilm-2'), [], ('pad', 'R5', '1')),
        ('Net-(R29-Pad1)', 'F.Cu', 0.25, ('pad', 'R5', '2'), [], ('pad', 'R29', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R29', '2'), [], ('via', 'b3-gnd-r29')),
        ('EF_IMON', 'F.Cu', 0.25, ('pad', 'U5', '14'), [], ('pad', 'R26', '1')),
        ('EF_IMON', 'F.Cu', 0.2, ('pad', 'R26', '1'), [(60.875, 74.6), (60.5, 73.4)], ('pad', 'TP7', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R26', '2'), [], ('via', 'b3-gnd-r26')),
        ('MAIN_OK', 'F.Cu', 0.25, ('pad', 'U5', '16'), [], ('pad', 'U5', '15')),
        ('MAIN_OK', 'F.Cu', 0.2, ('pad', 'U5', '15'), [(60.375, 76.4), (60.05, 76.1)], ('via', 'b3-mok-u5')),
        ('RUN', 'F.Cu', 0.2, ('pad', 'U5', '13'), [(61.675, 76.4), (61.9, 75.3)], ('via', 'b3-run-u5')),
        ('RUN', 'B.Cu', 0.2, ('via', 'b3-run-u5'), [(64.2, 74.9), (66.8, 77.5)], ('via', 'b3-run-q10')),
        ('RUN', 'F.Cu', 0.25, ('via', 'b3-run-q10'), [], ('pad', 'Q10', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'Q10', '2'), [], ('via', 'b3-gnd-q10')),
        ('EF_IN', 'F.Cu', 0.25, ('pad', 'TP3', '1'), [], ('via', 'b3-efin-tp3')),
        ('EF_IN', 'B.Cu', 0.3, ('via', 'b3-efin-tp3'), [(64.75, 85.0)], ('via', 'b3-efin-d10-4')),
        ('MAIN_OK', 'B.Cu', 0.2, ('via', 'b3-mok-u5'), [(74.4, 74.2)], ('via', 'b3-mok-tp5')),
        ('MAIN_OK', 'B.Cu', 0.2, ('via', 'b3-mok-tp5'), [(74.9, 74.2), (76.2, 74.2), (78.0, 72.4), (83.9, 72.4)],
         ('via', 'b3-mok-r63')),
        ('MAIN_OK', 'F.Cu', 0.2, ('via', 'b3-mok-tp5'), [], ('pad', 'TP5', '1')),
        ('MAIN_OK', 'F.Cu', 0.2, ('via', 'b3-mok-r63'), [], ('pad', 'R63', '2')),
    ],
}

# N1: negative-rail protection core (U8 LM5067, Q4, R48||R49 50 mOhm shunt, R89 Kelvin, D19/D20 clamps).
#  Power path N12_RAW (XB1.19/20) -> F pour -> R49.2/R48.2; N_SENSE R49.1/R48.1 -> F pour -> strip
#  between the Q4 tab and its gate pin (1.5 mm, 1.14 A) -> Q4.3 source. The Q4 gate goes to B (via
#  under the U8 body, clear of every pad) so the source strip does not cross it.
#  Kelvin: U8.5 VEE pickup = own 0.25 mm track from the R49.2 pad's south edge (no load current south
#  of the pad) to D19.1/R56.2 (and later the U8.5 low-current cluster); SENSE pickup = R89.1 own
#  track to the R48.1 pad between the two shunt pads. R57 (gate-source) R57.2 -> B -> via in the strip.
#  N_SENSE_PIN: D19.3/D19.2 -> row y87.5 -> east of U8 -> U8.7, R89.2 tees in. N_PWR: R56.1 -> U8.4.
BATCHES['N1-neg-core'] = {
    'zones': [
        ('F.Cu', 'N12_RAW', [(112.6, 77.5), (115.0, 77.5), (115.0, 81.1), (120.1, 81.1), (120.1, 82.75),
                             (112.6, 82.75)], 'solid'),
        ('F.Cu', 'N_SENSE', [(115.55, 84.15), (120.6, 84.15), (120.6, 85.65), (126.8, 85.65), (126.8, 89.75),
                             (125.25, 89.75), (125.25, 87.15), (120.1, 87.15), (120.1, 85.9), (115.55, 85.9)], 'solid'),
    ],
    'vias': {
        'n1-ng-r57': ('N_GATE', (117.8, 79.15)), 'n1-ns-r57': ('N_SENSE', (119.4, 79.15)),
        'n1-ns-strip': ('N_SENSE', (121.0, 86.4)), 'n1-ng-u8': ('N_GATE', (117.6, 89.3)),
        'n1-ng-q4': ('N_GATE', (123.0, 88.6)),
    },
    'tracks': [
        ('N_GATE', 'F.Cu', 0.25, ('pad', 'R57', '1'), [], ('via', 'n1-ng-r57')),
        ('N_SENSE', 'F.Cu', 0.25, ('pad', 'R57', '2'), [], ('via', 'n1-ns-r57')),
        ('N_SENSE', 'B.Cu', 0.25, ('via', 'n1-ns-r57'), [(119.9, 79.65), (119.9, 86.4)], ('via', 'n1-ns-strip')),
        ('N_GATE', 'B.Cu', 0.25, ('via', 'n1-ng-r57'), [(117.6, 79.35)], ('via', 'n1-ng-u8')),
        ('N_GATE', 'B.Cu', 0.25, ('via', 'n1-ng-u8'), [(118.3, 88.6)], ('via', 'n1-ng-q4')),
        ('N_GATE', 'F.Cu', 0.2, ('pad', 'U8', '8'), [], ('via', 'n1-ng-u8')),
        ('N_GATE', 'F.Cu', 0.3, ('pad', 'Q4', '1'), [], ('via', 'n1-ng-q4')),
        ('N_SENSE', 'F.Cu', 0.25, ('pad', 'R89', '1'), [(117.775, 85.75), (118.3, 85.2)], ('pad', 'R48', '1')),
        ('N_SENSE_PIN', 'F.Cu', 0.2, ('pad', 'D19', '2'), [(114.5, 87.5), (120.25, 87.5), (120.25, 89.8)], ('pad', 'U8', '7')),
        ('N_SENSE_PIN', 'F.Cu', 0.2, ('pad', 'R89', '2'), [], ('trk', 'N1-neg-core/trk/8', (119.425, 87.5), 1)),
        ('N_SENSE_PIN', 'F.Cu', 0.2, ('pad', 'D19', '3'), [(114.5, 85.45)], ('pad', 'D19', '2')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'R49', '2'), [(116.55, 83.35), (112.6, 83.35)], ('pad', 'D19', '1')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'R56', '2'), [], ('trk', 'N1-neg-core/trk/11', (112.6, 85.075), 2)),
        ('N_PWR', 'F.Cu', 0.2, ('pad', 'R56', '1'), [(110.95, 87.45), (113.55, 87.45), (113.55, 89.8)], ('pad', 'U8', '4')),
    ],
}

# N3: delivered -12V. F pour on the Q4 drain tab (+ D14.2 TVS pad), 7 x 0.6/0.3 vias in a column
# east of the tab (clear of the tab pad/mask) to a B pour under the tab (heat spreading on the
# correct net) that runs as a 1.6 mm strip at y75.0-76.6 west to J2.1/J2.2 (THT, B side). 1.14 A.
# R58.2 drops to the strip; C45.2 ties to the tab. C45.1 -> R58.1 -> GND via to In1.
_N12V_VIAS = [(127.3, 79.4), (127.3, 80.3), (127.3, 81.2), (127.3, 82.1), (127.3, 83.0), (127.3, 83.9), (127.3, 84.8)]
BATCHES['N3-neg-out'] = {
    'zones': [
        ('F.Cu', '-12V', [(120.6, 78.6), (127.95, 78.6), (127.95, 84.65), (130.35, 84.65), (130.35, 87.7),
                          (128.05, 87.7), (128.05, 85.35), (120.6, 85.35)], 'solid'),
        ('B.Cu', '-12V', [(110.75, 67.25), (113.0, 67.25), (113.0, 75.0), (127.95, 75.0), (127.95, 85.35),
                          (120.6, 85.35), (120.6, 76.6), (110.75, 76.6)], 'solid'),
    ],
    'vias': {
        **{f'n3-m12-tab-{i}': ('-12V', p) for i, p in enumerate(_N12V_VIAS)},
        'n3-m12-r58': ('-12V', (120.35, 76.3)),
        'n3-gnd-r58': ('GND', (120.35, 77.95)),
    },
    'tracks': [
        ('-12V', 'F.Cu', 0.4, ('pad', 'R58', '2'), [], ('via', 'n3-m12-r58')),
        ('-12V', 'F.Cu', 0.4, ('pad', 'C45', '2'), [(124.525, 79.4)], ('pad', 'Q4', '2')),
        ('GND', 'F.Cu', 0.4, ('pad', 'R58', '1'), [], ('via', 'n3-gnd-r58')),
        ('GND', 'F.Cu', 0.4, ('pad', 'C45', '1'), [], ('pad', 'R58', '1')),   # C47 sits right above C45
        # Tie the via column with F copper (an unattached via is re-netted by KiCad's save/reload
        # from the stale In1/In2 fill, which the shared save/reload invariant rightly rejects).
        ('-12V', 'F.Cu', 0.6, ('via', 'n3-m12-tab-0'), [p for p in _N12V_VIAS[1:-1]], ('via', 'n3-m12-tab-6')),
        ('-12V', 'F.Cu', 0.6, ('pad', 'Q4', '2'), [], ('via', 'n3-m12-tab-3')),
    ],
}

# R1: protected +12V / +5V from the top board (XB1) to the J2 output header (2.647 A nominal each).
#  +12V: F pour J2.9/10 -> 1.8 mm neck between TP14 and R91 (y72.2-77.35, leaves the B band free for
#  the E-W status lanes) -> XB1.9-12. J2.7/8 GND (x103.28) and J2.11/12 +5V (x99.9) bound it.
#  +5V: cannot cross +12V on F, so 1.25 mm F track J2.11 -> north of J2 (y65.8, 1 mm edge keep-out
#  kept) -> east of J2.1/2 (x113.45) -> y76.7 -> XB1.18, plus an F pour over XB1.15-18.
BATCHES['R1-rails'] = {
    'zones': [
        ('F.Cu', '+12V', [(100.15, 67.25), (103.0, 67.25), (103.0, 72.2), (103.2, 72.2), (103.2, 77.35),
                          (104.85, 77.35), (104.85, 82.1), (99.55, 82.1), (99.55, 77.35), (101.4, 77.35),
                          (101.4, 72.2), (100.15, 72.2)], 'solid'),
        ('F.Cu', '+5V', [(107.2, 77.3), (112.3, 77.3), (112.3, 82.1), (107.2, 82.1)], 'solid'),
    ],
    'tracks': [
        ('+5V', 'F.Cu', 1.25, ('pad', 'J2', '11'), [(99.05, 65.8), (113.45, 65.8), (113.45, 76.7), (111.07, 76.7)],
         ('pad', 'XB1', '18')),
        ('+5V', 'F.Cu', 1.25, ('pad', 'J2', '12'), [], ('pad', 'J2', '11')),
    ],
}


def _dog(batch, items, w=0.3):
    """GND/V3V3 dogbones: each (key, net, (x, y), [pad ends]) -> one via + a short track per pad.
    Spots were proposed per pad, clearance-checked (/tmp inspection aid) and chosen by hand: away
    from the U8 escape area, the north B status band and the J2/XB1 rail necks."""
    vias, tracks = {}, []
    for key, n, at, ends in items:
        vias[f'{batch}-{key}'] = (n, at)
        for e in ends:
            tracks.append((n, 'F.Cu', w, e, [], ('via', f'{batch}-{key}')))
    return {'vias': vias, 'tracks': tracks}


# G1: west/middle GND (In1) and V3V3 (In2) dogbones, x < 102.
BATCHES['G1-dog-west'] = _dog('g1', [
    ('u13-14', 'V3V3', (69.85, 64.0), [('pad', 'U13', '14')]),
    ('u13-7', 'GND', (78.5, 70.65), [('pad', 'U13', '7')]),
    ('u14-14', 'V3V3', (67.7, 64.15), [('pad', 'U14', '14')]),
    ('u14-7', 'GND', (61.05, 71.75), [('pad', 'U14', '7')]),
    ('r87', 'V3V3', (70.0, 72.85), [('pad', 'R87', '1')]),
    ('tp8', 'GND', (69.95, 76.0), [('pad', 'TP8', '1')]),
    ('r63', 'V3V3', (82.85, 73.15), [('pad', 'R63', '1')]),
    ('c54-1', 'V3V3', (86.3, 70.3), [('pad', 'C54', '1'), ('pad', 'C53', '1')]),
    ('c53-2', 'GND', (87.5, 73.1), [('pad', 'C53', '2')]),
    ('c54-2', 'GND', (88.7, 68.7), [('pad', 'C54', '2')]),
    ('u15-3', 'GND', (91.75, 87.9), [('pad', 'U15', '3'), ('pad', 'C46', '2')]),
    ('u15-5', 'V3V3', (93.65, 85.3), [('pad', 'U15', '5'), ('pad', 'R67', '1')]),
    ('u9-1', 'V3V3', (87.3, 93.1), [('pad', 'U9', '1')]),
    ('r71', 'V3V3', (93.0, 91.45), [('pad', 'R71', '1')]),
    ('u12-2', 'V3V3', (98.05, 88.25), [('pad', 'U12', '2')]),
    ('u12-4', 'V3V3', (98.05, 90.8), [('pad', 'U12', '4')]),
    ('u12-12', 'V3V3', (99.55, 89.55), [('pad', 'U12', '12')]),
    ('u12-10', 'V3V3', (99.55, 92.05), [('pad', 'U12', '10')]),
    ('u12-14', 'V3V3', (101.3, 85.95), [('pad', 'U12', '14')]),
    ('u12-7', 'GND', (96.3, 95.65), [('pad', 'U12', '7')]),
    ('r70', 'GND', (101.1, 85.1), [('pad', 'R70', '2')]),
])
BATCHES['G1-dog-west']['tracks'].append(('GND', 'F.Cu', 0.3, ('pad', 'U9', '4'), [(90.225, 91.9)], ('padu', 'U9', '9', (89.8, 91.45))))
# G1b: the shared U15.3/C46.2 GND via of G1 sat 0.17 mm inside the C46.2 pad (audit: via in SMD
# pad) -> removed and replaced 0.25 mm further NW, clear of both pads' copper.
BATCHES['G1b-fix-u15'] = {
    'delete': [('track', 'G1-dog-west/trk/11'), ('track', 'G1-dog-west/trk/12'), ('via', 'via/g1-u15-3')],
    **_dog('g1b', [('u15-3', 'GND', (91.45, 87.65), [('pad', 'U15', '3'), ('pad', 'C46', '2')])]),
}

# G2: middle GND/V3V3 dogbones (x 102-128). R85/R64/C55 drop to the WEST so the x119-121 N-S B
# corridor (north status band -> under MHB3) stays free; C48 drops south, R91 north of the +12V neck.
BATCHES['G2-dog-mid'] = _dog('g2', [
    ('c47-1', 'V3V3', (123.1, 74.15), [('pad', 'C47', '1')]),
    ('c47-2', 'GND', (126.1, 74.15), [('pad', 'C47', '2')]),
    ('c48-1', 'V3V3', (107.1, 76.95), [('pad', 'C48', '1')]),
    ('c48-2', 'GND', (108.6, 76.95), [('pad', 'C48', '2')]),
    ('c49-2', 'GND', (106.55, 84.9), [('pad', 'C49', '2')]),
    ('c50-1', 'V3V3', (112.0, 100.65), [('pad', 'C50', '1')]),
    ('c50-2', 'GND', (112.0, 96.7), [('pad', 'C50', '2')]),
    ('r68-1', 'V3V3', (110.4, 100.7), [('pad', 'R68', '1')]),
    ('c51-2', 'GND', (109.3, 86.4), [('pad', 'C51', '2'), ('pad', 'R66', '2')]),
    ('c52-1', 'V3V3', (122.15, 100.9), [('pad', 'C52', '1')]),
    ('c52-2', 'GND', (123.4, 98.1), [('pad', 'C52', '2')]),
    ('q5-2', 'GND', (123.4, 100.05), [('pad', 'Q5', '2')]),
    ('c55-1', 'V3V3', (117.0, 74.4), [('pad', 'C55', '1')]),
    ('c55-2', 'GND', (117.0, 72.8), [('pad', 'C55', '2')]),
    ('r64-2', 'GND', (117.0, 69.6), [('pad', 'R64', '2')]),
    ('r85-1', 'V3V3', (117.0, 68.1), [('pad', 'R85', '1')]),
    ('r52-1', 'GND', (111.6, 94.9), [('pad', 'R52', '1')]),
    ('r54-1', 'GND', (124.45, 93.3), [('pad', 'R54', '1')]),
    ('r59-1', 'V3V3', (127.05, 92.3), [('pad', 'R59', '1')]),
    ('r91-1', 'V3V3', (103.9, 74.5), [('pad', 'R91', '1')]),
    ('sw1-2', 'GND', (104.75, 96.6), [('pad', 'SW1', '2')]),
    ('tp16', 'V3V3', (129.35, 76.3), [('pad', 'TP16', '1')]),
    ('u10-6', 'V3V3', (107.3, 93.1), [('pad', 'U10', '6')]),
])
# (U11.6 V3V3: no clear via spot, R65/R66 within 0.1 mm of every candidate; joined in the U10/U11 batch.)

# G3: east GND/V3V3 dogbones (x > 128): U17/U18/U19 monitor block, D14/D15, R84/C58, R88, C57.
BATCHES['G3-dog-east'] = _dog('g3', [
    ('c56-2', 'GND', (143.75, 74.15), [('pad', 'C56', '2')]),
    ('c57-2', 'GND', (134.45, 99.8), [('pad', 'C57', '2')]),
    ('c58-1', 'V3V3', (134.35, 94.9), [('pad', 'C58', '1')]),
    ('r84-2', 'GND', (132.75, 90.9), [('pad', 'R84', '2'), ('pad', 'C58', '2')]),
    ('d14-1', 'GND', (129.2, 92.2), [('pad', 'D14', '1')]),
    ('d15-1', 'GND', (130.85, 90.25), [('pad', 'D15', '1')]),
    ('d15-2', 'V3V3', (134.85, 90.25), [('pad', 'D15', '2')]),
    ('r60-1', 'V3V3', (131.15, 95.3), [('pad', 'R60', '1')]),
    ('r61-1', 'GND', (135.65, 73.6), [('pad', 'R61', '1')]),
    ('r62-1', 'V3V3', (139.9, 74.8), [('pad', 'R62', '1')]),
    ('r73-1', 'V3V3', (146.55, 78.1), [('pad', 'R73', '1')]),
    ('r74-2', 'GND', (146.95, 74.15), [('pad', 'R74', '2')]),
    ('r76-2', 'GND', (137.7, 85.45), [('pad', 'R76', '2')]),
    ('r79-2', 'GND', (147.35, 79.05), [('pad', 'R79', '2')]),
    ('r80-1', 'V3V3', (137.65, 91.8), [('pad', 'R80', '1')]),
    ('r88-1', 'V3V3', (127.4, 100.3), [('pad', 'R88', '1')]),
    ('u17-3', 'GND', (139.25, 66.9), [('pad', 'U17', '3')]),
    ('u18-12', 'GND', (139.9, 78.0), [('pad', 'U18', '12')]),
    ('u18-3', 'V3V3', (138.4, 78.0), [('pad', 'U18', '3')]),
    ('u19-3', 'GND', (146.75, 81.0), [('pad', 'U19', '3')]),
])

# L1: local logic links around SW1/U10/U11/U12/U9 (F only, threads between SOIC pins where needed).
#  RESET_BTN_N: SW1.1 -> U10.3; SW1.3 -> up x105.98 -> y95.9 -> tee (around the SW1.2 GND via);
#  SW1.3 column -> y97.2 (clear of R50 by 0.3) -> R68.2. RESET_N: U10.1 -> U11.3; R67.2 -> U12.1 ->
#  y87.6 under the U12 body (between the U12.14 pad and the U12.2 V3V3 via) -> U12.13.
#  START_READY U12.3 -> R71.2. VPD U9.5 -> C46.1 (U9.8 joins with the VPD feed: R1/CFG1 copper above it).
#  R28.2 -> R4.1 (OVP divider series link).
BATCHES['L1-logic-local'] = {
    'tracks': [
        ('Net-(R28-Pad2)', 'F.Cu', 0.25, ('pad', 'R28', '2'), [], ('pad', 'R4', '1')),
        ('RESET_BTN_N', 'F.Cu', 0.25, ('pad', 'SW1', '1'), [(103.525, 95.9)], ('pad', 'U10', '3')),
        ('RESET_BTN_N', 'F.Cu', 0.25, ('pad', 'SW1', '3'), [(105.975, 95.9)], ('trk', 'L1-logic-local/trk/1', (103.525, 95.9), 0)),
        ('RESET_BTN_N', 'F.Cu', 0.25, ('trk', 'L1-logic-local/trk/2', (105.975, 97.2), 0), [(110.4, 97.2)], ('pad', 'R68', '2')),
        ('RESET_N', 'F.Cu', 0.25, ('pad', 'U10', '1'), [], ('pad', 'U11', '3')),
        ('START_READY', 'F.Cu', 0.25, ('pad', 'U12', '3'), [], ('pad', 'R71', '2')),
        ('RESET_N', 'F.Cu', 0.25, ('pad', 'R67', '2'), [], ('pad', 'U12', '1')),
        ('RESET_N', 'F.Cu', 0.2, ('pad', 'U12', '1'), [(97.7, 86.99), (98.3, 87.6), (100.5, 87.6)], ('pad', 'U12', '13')),
        ('VPD', 'F.Cu', 0.25, ('pad', 'U9', '5'), [(90.95, 89.45)], ('pad', 'C46', '1')),
    ],
}

# M1: always-on monitor block (U18 comparator, U19, U17 PGD opto, sense dividers), F only.
#  REF_GOOD 10-9 direct, 4-6 west of the left pins (x135.4); MON_P5 under the U18 body, out between
#  pins 11/10, down x143.0, between U19.1 and R78.1 (y81.99) -> R78.2 tee -> R79.1; MON_P5_SER below
#  R78 (y84.25, 0.23 from R77.1). N12_STATUS U18.14 -> R62.2 -> x140.5 (outside the MHB5 keep-out)
#  -> y63.7 -> U17.4. N_PGD_LED U17.1 -> y72.7 -> R61.2. MON_N12 R82.1 -> y86.75 -> D15.3 / R81.2 ->
#  y86.3 -> U18.8. MON_N_SER R81.1 -> R80.2. MON_P12 R75.2 -> x134.625 -> U18.7 -> R76.1.
BATCHES['M1-monitor'] = {
    'tracks': [
        ('REF_GOOD', 'F.Cu', 0.25, ('pad', 'U18', '10'), [], ('pad', 'U18', '9')),
        ('REF_GOOD', 'F.Cu', 0.2, ('pad', 'U18', '4'), [(135.4, 79.25), (135.4, 81.79)], ('pad', 'U18', '6')),
        ('MON_P5', 'F.Cu', 0.2, ('pad', 'U18', '5'), [(138.0, 80.52), (138.65, 79.9), (143.0, 79.9), (143.0, 81.99),
                                                       (147.35, 81.99)], ('pad', 'R79', '1')),
        ('MON_P5', 'F.Cu', 0.2, ('pad', 'R78', '2'), [], ('trk', 'M1-monitor/trk/2', (145.325, 81.99), 4)),
        ('MON_P5_SER', 'F.Cu', 0.2, ('pad', 'R78', '1'), [(143.675, 84.25), (148.425, 84.25)], ('pad', 'R77', '2')),
        ('N12_STATUS', 'F.Cu', 0.25, ('pad', 'U18', '14'), [], ('pad', 'R62', '2')),
        ('N12_STATUS', 'F.Cu', 0.2, ('pad', 'R62', '2'), [(141.575, 72.6), (140.5, 71.5), (140.5, 63.7), (136.73, 63.7)],
         ('pad', 'U17', '4')),
        ('N_PGD_LED', 'F.Cu', 0.2, ('pad', 'U17', '1'), [(136.73, 72.7), (138.475, 72.7)], ('pad', 'R61', '2')),
        ('MON_N12', 'F.Cu', 0.2, ('pad', 'R82', '1'), [(131.775, 86.75), (132.85, 86.75)], ('pad', 'D15', '3')),
        ('MON_N12', 'F.Cu', 0.2, ('trk', 'M1-monitor/trk/8', (132.85, 86.75), 2), [], ('pad', 'R81', '2')),
        ('MON_N12', 'F.Cu', 0.2, ('pad', 'R81', '2'), [(137.2, 86.3), (140.5, 86.3), (141.625, 85.2)], ('pad', 'U18', '8')),
        ('MON_N_SER', 'F.Cu', 0.2, ('pad', 'R81', '1'), [], ('pad', 'R80', '2')),
        ('MON_P12', 'F.Cu', 0.2, ('pad', 'R75', '2'), [(134.625, 83.06)], ('pad', 'U18', '7')),
        ('MON_P12', 'F.Cu', 0.2, ('trk', 'M1-monitor/trk/12', (134.625, 83.06), 0), [], ('pad', 'R76', '1')),
        ('REF_GOOD', 'F.Cu', 0.2, ('pad', 'C56', '1'), [], ('pad', 'R73', '2')),
    ],
}

# L2: short local links. POR_SENSE R65.2 -> R66.1; NEG_OFF_K U16.2 -> y96.47 -> Q5.3 (4.98 mm from
# the MHB4 centre); N_TIMER U8.6 -> x120.05 between C43.2/C44.2 -> C44.1; -12V R82.2 -> north of
# R82 (y84.4) -> D14.2 (the -12V F pour).
BATCHES['L2-local'] = {
    'tracks': [
        ('POR_SENSE', 'F.Cu', 0.2, ('pad', 'R65', '2'), [(106.6, 88.9)], ('pad', 'R66', '1')),
        ('NEG_OFF_K', 'F.Cu', 0.25, ('pad', 'U16', '2'), [(126.8, 96.47)], ('pad', 'Q5', '3')),
        ('N_TIMER', 'F.Cu', 0.2, ('pad', 'U8', '6'), [(120.05, 90.3), (120.05, 92.275)], ('pad', 'C44', '1')),
        ('-12V', 'F.Cu', 0.25, ('pad', 'R82', '2'), [(133.425, 84.4), (129.2, 84.4)], ('pad', 'D14', '2')),
    ],
}

# V1: VIN tap for the U8 shunt-supply feed (R51||R50, mA): XB1.5 (B) ->
# y83.5 -> the free B column x102.6 (between the U12 and U11 vias) -> y92.35 -> via between R51.2 and
# R51.1 -> R51.1 -> R50.1 (F).
BATCHES['V1-vin'] = {
    'vias': {'v1-r51': ('VIN', (108.95, 92.45))},
    'tracks': [
        ('VIN', 'B.Cu', 0.3, ('pad', 'XB1', '5'), [(95.83, 83.5), (102.6, 83.5), (102.6, 92.35), (108.85, 92.35)],
         ('via', 'v1-r51')),
        ('VIN', 'F.Cu', 0.3, ('via', 'v1-r51'), [], ('pad', 'R51', '1')),
        ('VIN', 'F.Cu', 0.3, ('pad', 'R51', '1'), [], ('pad', 'R50', '1')),
    ],
}
