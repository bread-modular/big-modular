#!/usr/bin/env python3
"""R3 BASE routing completion (window 5+): new hand-reviewed batches on top of route_base_r3.py.

  python3 -B tools/route_base_r3_final.py apply <batch>      # shared plan/apply + writeback + audit (route_base_r3)
  python3 -B tools/route_base_r3_final.py path NET LAYERS x0 y0 x1 y1 [width]
        ONE-connection suggestion helper: grid search between two points of ONE net on the given
        layers (e.g. F, B or FB), avoiding other-net copper + clearance, edge 1.0 mm, keep-outs, SMD
        pads/masks (no via in any SMD pad), NPTH/THT holes. It only PRINTS corner coordinates; nothing
        is written. Each suggestion is checked on a render, copied by hand into FINAL below and then
        goes through the shared plan/apply DRC/parity gate like every other batch. No bulk routing,
        no auto-accept.

Batches reuse route_base_r3.emit(): ends ('pad', ref, num) | ('via', key) | ('trk', 'batch/trk/i', (x, y)[, seg]).
Extra end ('tuu', '<track uuid>', (x, y)) branches on an existing track by UUID.
"""
import heapq
import math
import sys
import uuid

import route_base_r3 as R
from route_base_r3_batches import BATCHES

FINAL = {}

_emit0 = R.emit


def emit(batch):
    if batch not in FINAL:
        return _emit0(batch)
    spec = dict(FINAL[batch])
    remap = {}

    def conv(e):
        if e[0] == 'tuu':                    # ('tuu', '<existing track uuid>', (x, y))
            key = 'TUU:' + e[1]
            remap[R.uid(key)] = e[1]
            return ('trk', key, e[2])
        if e[0] == 'vuu':                    # ('vuu', '<existing via uuid>') ends on an existing via
            key = 'VUU:' + e[1]
            remap[R.uid('via/' + key)] = e[1]
            return ('via', key)
        return e
    spec['tracks'] = [(n, L, w, conv(a), wps, conv(b)) for n, L, w, a, wps, b in spec.get('tracks', [])]
    if spec.get('delete_poly'):              # every existing child segment of an earlier polyline key
        import pcbnew
        have = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(str(R.BOARD)).GetTracks()}
        dels = list(spec.get('delete', []))
        for key in spec['delete_poly']:
            par = uuid.UUID(R.uid(key))
            kids = [str(uuid.uuid5(par, str(i))) for i in range(64)]
            found = [k for k in [str(par)] + kids if k in have]
            assert found, ('no segments for', key)
            dels += [('track', k) for k in found]
        spec['delete'] = dels
    BATCHES[batch] = spec
    doc = _emit0(batch)
    for op in doc['operations']:
        for side in ('start', 'end'):
            e = op.get(side)
            if isinstance(e, dict) and e.get('track') in remap:
                e['track'] = remap[e['track']]
            if isinstance(e, dict) and e.get('uuid') in remap:
                e['uuid'] = remap[e['uuid']]
    return doc


R.emit = emit


# ---------------------------------------------------------------------------------------------
# Hand-reviewed batches (native board mm). Corner lists came from the one-connection helper below,
# one connection at a time, each checked on a render and by the shared plan/apply DRC gate.

# A1: middle logic, local: START_CT C49.1 -> under U11 -> U11.4; POR_SER R91.2 -> B x104.65 -> R65.1;
# START_SENSE R69.2 -> between XB1.4/XB1.6 (x94.55, 0.31 mm each side) -> R70.1; BAD_RC U15.2 -> R72.2;
# FAULT_LATCH U12.9 -> south of U12 -> TP11.
FINAL['A1-mid-local'] = {
    'tracks': [
        ('START_CT', 'F.Cu', 0.2, ('pad', 'C49', '1'), [(104.7, 87.025), (104.7, 90.725), (105.45, 91.475)], ('pad', 'U11', '4')),
        ('START_SENSE', 'F.Cu', 0.2, ('pad', 'R69', '2'), [(94.55, 75.925), (94.55, 81.525), (98.1, 85.075)], ('pad', 'R70', '1')),
        ('BAD_RC', 'F.Cu', 0.2, ('pad', 'U15', '2'), [(93.1, 85.925), (93.65, 86.475), (93.65, 89.025), (92.75, 89.925),
                                                      (92.75, 90.675), (91.9, 91.525)], ('pad', 'R72', '2')),
        ('FAULT_LATCH', 'F.Cu', 0.2, ('pad', 'U12', '9'), [(99.55, 93.325), (96.55, 96.325), (96.0, 96.325), (93.9, 94.225)],
         ('pad', 'TP11', '1')),
    ],
}

# A2: POR_SER R91.2 -> via -> B x104.65 -> via (104.65,84.225) -> F x103.1 -> R65.1;
# POR_SENSE R65.2 -> F east of U11 (x106.9) -> under U10 -> U10.5.
FINAL['A2-por'] = {
    'vias': {'a-ps-0': ('POR_SER', (104.65, 76.675)), 'a-ps-1': ('POR_SER', (104.65, 84.225))},
    'tracks': [
        ('POR_SER', 'F.Cu', 0.2, ('pad', 'R91', '2'), [], ('via', 'a-ps-0')),
        ('POR_SER', 'B.Cu', 0.2, ('via', 'a-ps-0'), [], ('via', 'a-ps-1')),
        ('POR_SER', 'F.Cu', 0.2, ('via', 'a-ps-1'), [(103.1, 85.775), (103.1, 87.125)], ('pad', 'R65', '1')),
        ('POR_SENSE', 'F.Cu', 0.2, ('pad', 'R65', '2'), [(105.65, 87.925), (106.9, 89.175), (106.9, 91.775), (106.3, 92.375),
                                                         (105.15, 92.375), (104.8, 92.725), (104.8, 93.425), (105.4, 94.025)], ('pad', 'U10', '5')),
    ],
}

# A3: rip own A2 POR_SENSE track (it sat under the U10 body, the only via slot for RESET_N).
FINAL['A3-rip-porsense'] = {
    'delete_poly': ['A2-por/trk/3'],
}

# A4: RESET_N U10.1 -> via under U10 (104.7,93.425) -> B south of the V1 VIN corner -> x100.2 under U12 ->
# via (99.9,87.6) on the L1 RESET_N under-body track. START_READY U11.1 -> F corridor x102.6 between the U12 and
# U11 pad columns -> y88.895 through the 0.67 mm U12.13/U12.12 gap (0.235 mm each side) -> U12.3.
FINAL['A4-reset-start'] = {
    'vias': {'a-rn-0': ('RESET_N', (104.7, 93.425)), 'a-rn-1': ('RESET_N', (99.9, 87.6))},
    'tracks': [
        ('RESET_N', 'F.Cu', 0.2, ('pad', 'U10', '1'), [(104.35, 93.075)], ('via', 'a-rn-0')),
        ('RESET_N', 'B.Cu', 0.2, ('via', 'a-rn-0'), [(102.95, 93.425), (100.2, 90.675), (100.2, 87.9)], ('via', 'a-rn-1')),
        ('START_READY', 'F.Cu', 0.2, ('pad', 'U11', '1'), [(102.95, 89.55), (102.6, 89.2), (102.6, 88.895), (98.6, 88.895),
                                                           (97.95, 89.53)], ('pad', 'U12', '3')),
    ],
}

# A5: POR_SENSE R66.1 -> via (107.65,90.025) -> B east of R51 (x109.6, clear of the V1 VIN via) -> via (107.0,94.025) -> U10.5.
FINAL['A5-porsense'] = {
    'vias': {'a-pse-0': ('POR_SENSE', (107.65, 90.025)), 'a-pse-1': ('POR_SENSE', (107.0, 94.025))},
    'tracks': [
        ('POR_SENSE', 'F.Cu', 0.2, ('pad', 'R66', '1'), [(107.65, 89.225)], ('via', 'a-pse-0')),
        ('POR_SENSE', 'B.Cu', 0.2, ('via', 'a-pse-0'), [(109.6, 91.975), (109.6, 92.725), (108.3, 94.025)], ('via', 'a-pse-1')),
        ('POR_SENSE', 'F.Cu', 0.2, ('via', 'a-pse-1'), [], ('pad', 'U10', '5')),
    ],
}

# A6: START_SENSE U11.5 -> via east of U11 (107.0,90.575) -> B diagonal (outside the V1 VIN loop) -> via (103.3,84.575) -> F y84.225 under XB1 -> R70.1.
FINAL['A6-startsense'] = {
    'vias': {'a-ss2-0': ('START_SENSE', (107.0, 90.575)), 'a-ss2-1': ('START_SENSE', (103.3, 84.575))},
    'tracks': [
        ('START_SENSE', 'F.Cu', 0.2, ('pad', 'U11', '5'), [(106.0, 90.575)], ('via', 'a-ss2-0')),
        ('START_SENSE', 'B.Cu', 0.2, ('via', 'a-ss2-0'), [(103.3, 86.875)], ('via', 'a-ss2-1')),
        ('START_SENSE', 'F.Cu', 0.2, ('via', 'a-ss2-1'), [(102.95, 84.225), (99.2, 84.225)], ('pad', 'R70', '1')),
    ],
}

# A7: FAULT_LATCH U12.9 -> via under U12 (99.95,93.875) -> B y94.675 under U10/R51 -> x110.05 -> via (108.05,86.375) -> TP6.
FINAL['A7-faultlatch'] = {
    'vias': {'a-fl1-0': ('FAULT_LATCH', (99.95, 93.875)), 'a-fl1-1': ('FAULT_LATCH', (108.05, 86.375))},
    'tracks': [
        ('FAULT_LATCH', 'F.Cu', 0.2, ('pad', 'U12', '9'), [(100.7, 93.875)], ('via', 'a-fl1-0')),
        ('FAULT_LATCH', 'B.Cu', 0.2, ('via', 'a-fl1-0'), [(100.75, 94.675), (108.25, 94.675), (110.05, 92.875), (110.05, 88.375)], ('via', 'a-fl1-1')),
        ('FAULT_LATCH', 'F.Cu', 0.2, ('via', 'a-fl1-1'), [], ('pad', 'TP6', '1')),
    ],
}

# A8: GND U11.2 + U10.2 -> F x102.6 between the U12 and U11/U10 pad columns (0.25/0.35 mm) -> GND via
# (102.6,96.5) above SW1. BAD_RC R72.2 -> via -> B y92.325/95.125 -> via (110.65,93.075) -> F x110.2 -> C51.1.
FINAL['A8-gnd-badrc'] = {
    'vias': {'a-g1': ('GND', (102.6, 96.5)), 'a-rc2-0': ('BAD_RC', (92.65, 92.325)), 'a-rc2-1': ('BAD_RC', (110.65, 93.075))},
    'tracks': [
        ('GND', 'F.Cu', 0.25, ('pad', 'U11', '2'), [(102.6, 90.5)], ('via', 'a-g1')),
        ('GND', 'F.Cu', 0.25, ('pad', 'U10', '2'), [], ('trk', 'A8-gnd-badrc/trk/0', (102.6, 94.05), 1)),
        ('BAD_RC', 'F.Cu', 0.2, ('pad', 'R72', '2'), [], ('via', 'a-rc2-0')),
        ('BAD_RC', 'B.Cu', 0.2, ('via', 'a-rc2-0'), [(97.45, 92.325), (100.25, 95.125), (108.6, 95.125)], ('via', 'a-rc2-1')),
        ('BAD_RC', 'F.Cu', 0.2, ('via', 'a-rc2-1'), [(110.2, 92.625), (110.2, 90.025)], ('pad', 'C51', '1')),
    ],
}

# W1: U13.14 V3V3 dogbone via moved from (69.85,64.0) (it blocked the only F lane north of U13) to under the
# U13 body (69.84,67.3). MAIN_LED_OK U13.11 -> north F lane y63.45 (1.075 mm to the edge) -> U14.1 -> west of U14
# (x61.4) -> diagonal outside the MHB1 keep-out (3.75 mm from its centre) -> Q6.1.
FINAL['W1-u13-north'] = {
    'delete': [('via', 'via/g1-u13-14')],
    'delete_poly': ['G1-dog-west/trk/0'],
    'vias': {'w-u13-14': ('V3V3', (69.84, 67.3))},
    'tracks': [
        ('V3V3', 'F.Cu', 0.3, ('pad', 'U13', '14'), [], ('via', 'w-u13-14')),
        ('MAIN_LED_OK', 'F.Cu', 0.2, ('pad', 'U13', '11'), [(73.65, 63.95), (73.15, 63.45), (63.3, 63.45), (62.775, 63.975)], ('pad', 'U14', '1')),
        ('MAIN_LED_OK', 'F.Cu', 0.2, ('pad', 'U14', '1'), [(62.3, 65.175), (61.4, 66.075), (61.4, 67.725), (57.15, 71.975)], ('pad', 'Q6', '1')),
    ],
}

# W2: U13/U14 local. RUN chain U14.13-U14.12, U14.10-U14.9, U13.9 -> under-body lane y68.6 -> U13.3 -> lane y69.22
# -> U14.10, U14.12 -> x69.15 (around NC pin 11) -> lane. V20_OK U13.13/U13.10 -> vias north of the pads (y64.2,
# 0.35 mm below the MAIN_LED_OK lane) -> B y64.2. MAIN_OK U13.12 -> via under the body -> B x72.38 -> MAIN_OK B lane y74.2.
FINAL['W2-u13-local'] = {
    'vias': {'w-v20-13': ('V20_OK', (71.11, 64.2)), 'w-v20-10': ('V20_OK', (74.92, 64.2)), 'w-mok': ('MAIN_OK', (72.38, 67.4))},
    'tracks': [
        ('RUN', 'F.Cu', 0.2, ('pad', 'U14', '13'), [], ('pad', 'U14', '12')),
        ('RUN', 'F.Cu', 0.2, ('pad', 'U14', '10'), [], ('pad', 'U14', '9')),
        ('RUN', 'F.Cu', 0.2, ('pad', 'U13', '9'), [(76.19, 67.9), (75.5, 68.6), (73.0, 68.6), (72.38, 69.22)], ('pad', 'U13', '3')),
        ('RUN', 'F.Cu', 0.2, ('trk', 'W2-u13-local/trk/2', (72.38, 69.22), 4), [(69.15, 69.22), (68.75, 69.62)], ('pad', 'U14', '10')),
        ('RUN', 'F.Cu', 0.2, ('pad', 'U14', '12'), [(68.9, 67.725), (69.15, 67.975)], ('trk', 'W2-u13-local/trk/3', (69.15, 69.22), 0)),
        ('V20_OK', 'F.Cu', 0.2, ('pad', 'U13', '13'), [], ('via', 'w-v20-13')),
        ('V20_OK', 'F.Cu', 0.2, ('pad', 'U13', '10'), [], ('via', 'w-v20-10')),
        ('V20_OK', 'B.Cu', 0.2, ('via', 'w-v20-13'), [], ('via', 'w-v20-10')),
        ('MAIN_OK', 'F.Cu', 0.2, ('pad', 'U13', '12'), [], ('via', 'w-mok')),
        ('MAIN_OK', 'B.Cu', 0.2, ('via', 'w-mok'), [], ('tuu', '24cbe904-d322-5401-b69c-2c3c61962c8e', (72.38, 74.2))),
    ],
}

# W3: TIMER_GO U13.8 -> F north lane y63.775 over the MHB2 keep-out -> between C54/R83 -> x92.8 west of J2.15 -> R69.1.
FINAL['W3-timer'] = {
    'tracks': [
        ('TIMER_GO', 'F.Cu', 0.2, ('pad', 'U13', '8'), [(79.4, 63.775), (84.0, 63.775), (86.6, 66.375), (87.55, 66.375), (92.8, 71.625)], ('pad', 'R69', '1')),
    ],
}

# W4: ARMED U13.4 -> under-body lane y69.275 -> via (78.3,69.275) -> B y71.875 south of MHB2 -> via (95.55,74.975) -> TP10.
FINAL['W4-armed'] = {
    'vias': {'w-ar-0': ('ARMED', (78.3, 69.275)), 'w-ar-1': ('ARMED', (95.55, 74.975))},
    'tracks': [
        ('ARMED', 'F.Cu', 0.2, ('pad', 'U13', '4'), [(73.65, 70.175), (74.55, 69.275)], ('via', 'w-ar-0')),
        ('ARMED', 'B.Cu', 0.2, ('via', 'w-ar-0'), [(80.9, 71.875), (92.45, 71.875)], ('via', 'w-ar-1')),
        ('ARMED', 'F.Cu', 0.2, ('via', 'w-ar-1'), [], ('pad', 'TP10', '1')),
    ],
}

# W5: FAULT_CLK U13.6 -> via (78.4,73.075) south-east of U13 -> B diagonal under D9/C1 -> x89.5 between the XB1.1/XB1.2
# column and U1 -> via under the U12 body (98.7,89.725) -> U12.11.
FINAL['W5-faultclk'] = {
    'vias': {'w-fc-0': ('FAULT_CLK', (78.4, 73.075)), 'w-fc-1': ('FAULT_CLK', (98.7, 89.725))},
    'tracks': [
        ('FAULT_CLK', 'F.Cu', 0.2, ('pad', 'U13', '6'), [(76.2, 71.125), (77.0, 71.925), (77.4, 72.075)], ('via', 'w-fc-0')),
        ('FAULT_CLK', 'B.Cu', 0.2, ('via', 'w-fc-0'), [(83.2, 77.875), (86.0, 77.875), (89.5, 81.375), (89.5, 82.125), (97.1, 89.725)], ('via', 'w-fc-1')),
        ('FAULT_CLK', 'F.Cu', 0.2, ('via', 'w-fc-1'), [(99.75, 90.775)], ('pad', 'U12', '11')),
    ],
}

# E1: east locals. REF_GOOD U18.6 -> U18.9 under the body; R74.1 -> C56.1. NEG_OFF_LED R60.2 -> R59.2 (F), R59.2 -> B hop
# -> U16.1. V3V3 C57.1 -> R88.1 (its V3V3 via).
FINAL['E1-east-local'] = {
    'vias': {'e-no1-0': ('NEG_OFF_LED', (125.0, 91.525)), 'e-no1-1': ('NEG_OFF_LED', (123.4, 93.125))},
    'tracks': [
        ('REF_GOOD', 'F.Cu', 0.2, ('pad', 'U18', '6'), [], ('pad', 'U18', '9')),
        ('REF_GOOD', 'F.Cu', 0.2, ('pad', 'R74', '1'), [(146.15, 76.175), (144.5, 76.175)], ('pad', 'C56', '1')),
        ('NEG_OFF_LED', 'F.Cu', 0.2, ('pad', 'R60', '2'), [(130.8, 92.875), (128.6, 92.875), (126.4, 90.675)], ('pad', 'R59', '2')),
        ('NEG_OFF_LED', 'F.Cu', 0.2, ('pad', 'R59', '2'), [], ('via', 'e-no1-0')),
        ('NEG_OFF_LED', 'B.Cu', 0.2, ('via', 'e-no1-0'), [], ('via', 'e-no1-1')),
        ('NEG_OFF_LED', 'F.Cu', 0.2, ('via', 'e-no1-1'), [(122.7, 93.825)], ('pad', 'U16', '1')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'C57', '1'), [(131.3, 99.375), (129.45, 99.375)], ('pad', 'R88', '1')),
    ],
}

# E2: REF_GOOD C56.1 -> B hop -> via under U18 (between pins 10/9, same net) -> U18.10. P12_OK U18.1 -> XB2.4 and
# P5_OK U18.2 -> XB2.5 on F (parallel 45-degree runs 1.2 mm apart).
FINAL['E2-east-xb2'] = {
    'vias': {'e-rg2-0': ('REF_GOOD', (144.5, 77.675)), 'e-rg2-1': ('REF_GOOD', (140.4, 81.125))},
    'tracks': [
        ('REF_GOOD', 'F.Cu', 0.2, ('pad', 'C56', '1'), [], ('via', 'e-rg2-0')),
        ('REF_GOOD', 'B.Cu', 0.2, ('via', 'e-rg2-0'), [(143.85, 77.675)], ('via', 'e-rg2-1')),
        ('REF_GOOD', 'F.Cu', 0.2, ('via', 'e-rg2-1'), [(141.0, 80.525)], ('pad', 'U18', '10')),
        ('P12_OK', 'F.Cu', 0.2, ('pad', 'U18', '1'), [(136.5, 75.425), (134.75, 73.675), (134.75, 71.075)], ('pad', 'XB2', '4')),
        ('P5_OK', 'F.Cu', 0.2, ('pad', 'U18', '2'), [(136.1, 76.725), (131.8, 72.425)], ('pad', 'XB2', '5')),
    ],
}

# E3: N12_STATUS U18.14 -> via -> B east of U18 -> via -> U19.2. MON_20 R84.1 -> via -> B x133.4 + diagonal -> via under
# U18 (140.15,79.175) -> U18.11.
FINAL['E3-east-status'] = {
    'vias': {'e-ns-0': ('N12_STATUS', (142.45, 74.625)), 'e-ns-1': ('N12_STATUS', (145.15, 79.875)),
             'e-m20-0': ('MON_20', (133.4, 92.875)), 'e-m20-1': ('MON_20', (140.15, 79.175))},
    'tracks': [
        ('N12_STATUS', 'F.Cu', 0.2, ('pad', 'U18', '14'), [], ('via', 'e-ns-0')),
        ('N12_STATUS', 'B.Cu', 0.2, ('via', 'e-ns-0'), [(145.15, 77.325)], ('via', 'e-ns-1')),
        ('N12_STATUS', 'F.Cu', 0.2, ('via', 'e-ns-1'), [(144.75, 80.275)], ('pad', 'U19', '2')),
        ('MON_20', 'F.Cu', 0.2, ('pad', 'R84', '1'), [(133.4, 93.075)], ('via', 'e-m20-0')),
        ('MON_20', 'B.Cu', 0.2, ('via', 'e-m20-0'), [(133.4, 85.925)], ('via', 'e-m20-1')),
        ('MON_20', 'F.Cu', 0.2, ('via', 'e-m20-1'), [(140.25, 79.275)], ('pad', 'U18', '11')),
    ],
}

# E4: V3V3 U19.5 -> dogbone via (144.2,79.775) into the In2 V3V3 plane. N12_OK Q9.1 -> via -> long B diagonal (free B
# under the east block) -> via (146.05,79.775) -> U19.4.
FINAL['E4-east-n12ok'] = {
    'vias': {'e-v2-0': ('V3V3', (144.2, 79.775)), 'e-n12-0': ('N12_OK', (131.2, 96.175)), 'e-n12-1': ('N12_OK', (146.05, 79.775))},
    'tracks': [
        ('V3V3', 'F.Cu', 0.25, ('pad', 'U19', '5'), [(144.2, 79.125)], ('via', 'e-v2-0')),
        ('N12_OK', 'F.Cu', 0.2, ('pad', 'Q9', '1'), [], ('via', 'e-n12-0')),
        ('N12_OK', 'B.Cu', 0.2, ('via', 'e-n12-0'), [(146.05, 81.325)], ('via', 'e-n12-1')),
        ('N12_OK', 'F.Cu', 0.2, ('via', 'e-n12-1'), [(145.7, 79.425)], ('pad', 'U19', '4')),
    ],
}

# E5: RUN R64.1 -> F y71.325 under the MHB3 keep-out -> XB2.3; XB2.3 -> B x129.75/x130.0 (east of the Q4 B spread) -> via -> TP9.
FINAL['E5-east-run'] = {
    'vias': {'e-r2-0': ('RUN', (130.0, 97.375))},
    'tracks': [
        ('RUN', 'F.Cu', 0.2, ('pad', 'R64', '1'), [(118.3, 71.325), (129.55, 71.325)], ('pad', 'XB2', '3')),
        ('RUN', 'B.Cu', 0.2, ('pad', 'XB2', '3'), [(129.75, 71.125), (129.75, 75.725), (130.0, 75.975)], ('via', 'e-r2-0')),
        ('RUN', 'F.Cu', 0.2, ('via', 'e-r2-0'), [], ('pad', 'TP9', '1')),
    ],
}

# E6: V20_OK U18.13 -> via -> B between the XB2 pin columns (x132.2) -> under MHB3 (y71.325) -> via -> R85.2.
# +5V monitor tap R77.1 -> via -> B diagonal east of U18 -> via (132.55,63.725) -> F north lane y63.725 over MHB3 -> the
# 1.25 mm +5V F track corner (113.45,65.8).
FINAL['E6-east-v20-5v'] = {
    'vias': {'e-v20-0': ('V20_OK', (139.75, 76.725)), 'e-v20-1': ('V20_OK', (118.95, 67.175)),
             'e-5-0': ('+5V', (148.2, 80.925)), 'e-5-1': ('+5V', (132.55, 63.725))},
    'tracks': [
        ('V20_OK', 'F.Cu', 0.2, ('pad', 'U18', '13'), [], ('via', 'e-v20-0')),
        ('V20_OK', 'B.Cu', 0.2, ('via', 'e-v20-0'), [(134.1, 71.075), (133.0, 71.075), (132.2, 70.275), (132.2, 69.325), (131.5, 68.625),
                                                     (129.0, 68.625), (126.3, 71.325), (123.1, 71.325)], ('via', 'e-v20-1')),
        ('V20_OK', 'F.Cu', 0.2, ('via', 'e-v20-1'), [], ('pad', 'R85', '2')),
        ('+5V', 'F.Cu', 0.25, ('pad', 'R77', '1'), [(147.0, 83.475), (148.2, 82.275)], ('via', 'e-5-0')),
        ('+5V', 'B.Cu', 0.25, ('via', 'e-5-0'), [(145.65, 78.375), (145.65, 77.025), (143.1, 74.475), (143.1, 74.275), (143.0, 74.175)], ('via', 'e-5-1')),
        ('+5V', 'F.Cu', 0.25, ('via', 'e-5-1'), [(115.525, 63.725)], ('tuu', 'ca9b31f1-b3ef-58b7-af95-11d505a9f7d8', (113.45, 65.8))),
    ],
}

# S1: D18 anode: R88.2 -> via (129.45,100.925) -> B south band y100.975/y100.725 under the MHB4 keep-out -> diagonal -> B
# y97.925 under SW1 (B free; pegs 1.6 mm away) -> D18.2.
FINAL['S1-d18a'] = {
    'vias': {'s-d18a-0': ('Net-(D18-A)', (129.45, 100.925))},
    'tracks': [
        ('Net-(D18-A)', 'F.Cu', 0.2, ('pad', 'R88', '2'), [(129.55, 100.925)], ('via', 's-d18a-0')),
        ('Net-(D18-A)', 'B.Cu', 0.2, ('via', 's-d18a-0'), [(129.4, 100.975), (123.2, 100.975), (122.4, 100.175), (120.5, 100.175),
                                                          (119.95, 100.725), (113.05, 100.725), (110.25, 97.925)], ('pad', 'D18', '2')),
    ],
}

# U1 (Astra U8 escape, tested on the 101-open WIP, re-validated here): swap the AI-placed C43/R90 sites so N_VCC/N12_RAW
# sit under U8 pins 1/5. N_VCC U8.1 -> F x116.7 under the U8 body -> C43.1; N12_RAW quiet return U8.5 -> C43.2 (0.25 mm).
FINAL['U1-u8-c43'] = {
    'moves': [('C43', (115.3, 91.95), 180), ('R90', (118.4, 91.95), 0)],
    'tracks': [
        ('N_VCC', 'F.Cu', 0.2, ('pad', 'U8', '1'), [(116.7, 88.3), (116.7, 91.0)], ('pad', 'C43', '1')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'U8', '5'), [(114.525, 90.525)], ('pad', 'C43', '2')),
    ],
}

# U2: re-lay own U1 N_VCC under-body run at x116.95 (frees the two under-body vias). N_UV U8.2 -> via (116.3,88.95) -> B ->
# via (113.9,93.2) between R53/C43 -> R53.1 -> R52.2. N_OV U8.3 -> SE stub -> via (116.0,89.95) -> B y90.6 under R90/C44/R55 ->
# via between R55/R54 (123.35,91.5) -> R54.2, R55.1 (Astra legs; the exact Astra via pair failed 0.166 mm against the N_OV stub).
# N12_RAW quiet return C43.2 -> R53.2 -> D20.1 (Astra), D20.1 -> west of R56 -> D19.1 (helper; the D19/R56/R49 raw-reference group).
FINAL['U2-u8-uv-ov-raw'] = {
    'delete_poly': ['U1-u8-c43/trk/0'],
    'vias': {'u-uv-0': ('N_UV', (116.3, 88.95)), 'u-uv-1': ('N_UV', (113.9, 93.2)),
             'u-ov-0': ('N_OV', (116.0, 89.95)), 'u-ov-1': ('N_OV', (123.35, 91.5))},
    'tracks': [
        ('N_VCC', 'F.Cu', 0.2, ('pad', 'U8', '1'), [(116.95, 88.3), (116.95, 91.0)], ('pad', 'C43', '1')),
        ('N_UV', 'F.Cu', 0.2, ('pad', 'U8', '2'), [(115.9, 88.8)], ('via', 'u-uv-0')),
        ('N_UV', 'B.Cu', 0.2, ('via', 'u-uv-0'), [(115.35, 88.95), (113.9, 90.4)], ('via', 'u-uv-1')),
        ('N_UV', 'F.Cu', 0.2, ('via', 'u-uv-1'), [], ('pad', 'R53', '1')),
        ('N_UV', 'F.Cu', 0.2, ('pad', 'R53', '1'), [(112.1, 93.05), (111.35, 93.05)], ('pad', 'R52', '2')),
        ('N_OV', 'F.Cu', 0.2, ('pad', 'U8', '3'), [(115.65, 89.3), (116.0, 89.65)], ('via', 'u-ov-0')),
        ('N_OV', 'B.Cu', 0.2, ('via', 'u-ov-0'), [(117.15, 89.95), (117.8, 90.6), (123.35, 90.6)], ('via', 'u-ov-1')),
        ('N_OV', 'F.Cu', 0.2, ('via', 'u-ov-1'), [], ('pad', 'R54', '2')),
        ('N_OV', 'F.Cu', 0.2, ('via', 'u-ov-1'), [], ('pad', 'R55', '1')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'C43', '2'), [(113.6, 91.95)], ('pad', 'R53', '2')),
        ('N12_RAW', 'F.Cu', 0.2, ('pad', 'R53', '2'), [(112.95, 91.55), (112.0, 91.55)], ('pad', 'D20', '1')),
        ('N12_RAW', 'F.Cu', 0.2, ('pad', 'D20', '1'), [(111.0, 90.175), (110.4, 89.575), (110.4, 87.475), (110.05, 87.125), (110.05, 86.275),
                                                       (110.4, 85.925), (112.15, 85.925)], ('pad', 'D19', '1')),
    ],
}

# U3: own E1 NEG_OFF_LED B hop moved onto F (R59.2 -> x125.1 east of R54 -> y93.93 -> U16.1) to free B for the R90 -12V feed:
# R90.1 -> via (117.6,92.95) -> B y92.65 under R90/C44/R55/R54 -> x124.0 north -> existing -12V via (127.3,84.8) (Astra lane, moved
# 0.1 mm off the R54 GND via). N12_RAW C44.2 -> R55.2; N_OUT_PIN D20.2 -> D20.3.
FINAL['U3-u8-m12-neg'] = {
    'delete_poly': ['E1-east-local/trk/3', 'E1-east-local/trk/4', 'E1-east-local/trk/5'],
    'delete': [('via', 'via/e-no1-0'), ('via', 'via/e-no1-1')],
    'vias': {'u-m12-0': ('-12V', (117.6, 92.95))},
    'tracks': [
        ('NEG_OFF_LED', 'F.Cu', 0.2, ('pad', 'R59', '2'), [(125.0, 91.525), (125.0, 92.95), (125.2, 93.15), (125.2, 93.93)], ('pad', 'U16', '1')),
        ('-12V', 'F.Cu', 0.3, ('pad', 'R90', '1'), [], ('via', 'u-m12-0')),
        ('-12V', 'B.Cu', 0.3, ('via', 'u-m12-0'), [(117.9, 92.65), (124.0, 92.65), (124.0, 85.6), (124.8, 84.8)],
         ('vuu', '2de01af0-3302-5c3b-95d8-11094ad7d96e')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'C44', '2'), [], ('pad', 'R55', '2')),
        ('N_OUT_PIN', 'F.Cu', 0.2, ('pad', 'D20', '2'), [], ('pad', 'D20', '3')),
    ],
}

# U4: N_VCC C43.1 -> F south-west outside the MHB4 keep-out, past the N_UV via -> R50.2.
FINAL['U4-nvcc-r50'] = {
    'tracks': [
        ('N_VCC', 'F.Cu', 0.2, ('pad', 'C43', '1'), [(116.075, 93.0), (114.6, 94.475)], ('pad', 'R50', '2')),
    ],
}

# U5: re-lay own U2/U3 lanes so N_UV can run east under the R90..R54 row: N_OV B straight y89.95 -> via (123.35,89.75) in the
# R55/R54 pad gap -> F x123.35 -> R54.2, R55.1; -12V R90.1 -> via north of R90 (117.6,90.95) -> B y90.95 -> x124.1 -> existing
# -12V via (127.3,84.8); N_UV via (113.9,93.2) -> B y92.6 (0.3 mm off the R54 GND via) -> via (127.35,93.45) -> U16.4.
FINAL['U5-u8-lanes-uv'] = {
    'delete_poly': ['U2-u8-uv-ov-raw/trk/6', 'U2-u8-uv-ov-raw/trk/7', 'U2-u8-uv-ov-raw/trk/8', 'U3-u8-m12-neg/trk/1', 'U3-u8-m12-neg/trk/2'],
    'delete': [('via', 'via/u-ov-1'), ('via', 'via/u-m12-0')],
    'vias': {'u-ov-2': ('N_OV', (123.35, 89.75)), 'u-m12-1': ('-12V', (117.6, 90.95)), 'u-uv-2': ('N_UV', (127.35, 93.45))},
    'tracks': [
        ('N_OV', 'B.Cu', 0.2, ('via', 'u-ov-0'), [(123.05, 89.95)], ('via', 'u-ov-2')),
        ('N_OV', 'F.Cu', 0.2, ('via', 'u-ov-2'), [], ('pad', 'R54', '2')),
        ('N_OV', 'F.Cu', 0.2, ('via', 'u-ov-2'), [(123.35, 91.5)], ('pad', 'R55', '1')),
        ('-12V', 'F.Cu', 0.3, ('pad', 'R90', '1'), [], ('via', 'u-m12-1')),
        ('-12V', 'B.Cu', 0.3, ('via', 'u-m12-1'), [(123.8, 90.95), (124.1, 90.65), (124.1, 85.6), (124.9, 84.8)],
         ('vuu', '2de01af0-3302-5c3b-95d8-11094ad7d96e')),
        ('N_UV', 'B.Cu', 0.2, ('via', 'u-uv-1'), [(114.5, 92.6), (125.7, 92.6), (126.5, 93.4)], ('via', 'u-uv-2')),
        ('N_UV', 'F.Cu', 0.2, ('via', 'u-uv-2'), [], ('pad', 'U16', '4')),
    ],
}

# V1: U8 east-column escape (own copper reworked, R57/R90 rotated in place, AI-placed). The B gate run under the U8 body
# boxed pins 7-10 in; now: pin 8 -> F straight east into Q4.1; R57 rotated 180 so its gate pad is east: gate R57.1 -> via
# (119.4,79.15) -> B x119.9 (the old R57 N_SENSE lane) -> north of the PGD via -> existing gate via (123,88.6) -> Q4.1.
# R57.2 N_SENSE -> via (117.8,79.15) -> B x117.6 (old gate lane, shortened) -> via on the R89.1 Kelvin track (117.775,85.95)
# -> F -> R89.1 pad (100k tap, pickup at the R48.1 pad unchanged). N_SENSE_PIN: pin 7 -> F west under the body x117.95 -> the D19-R89.2 F run
# (shortened to R89.2). PGD pin 10 -> via NE of the pins (120.25,87.75) -> B corridor x119.3/x118.6 -> via (118.6,77.2) -> F (one-connection
# helper) diagonal NE, y71.775 under XB2, between the XB2 pin columns (x132.3), y68.625 -> U17.2.
# OUT pin 9 -> 0.5/0.3 via in the 1 mm U8/Q4.1 gap -> B y88.2 under the pins -> via -> D20.3, branch -> via -> R90 (rotated
# 180, OUT pad west). -12V R90.1 (east) -> via (119.2,91.0) -> B y90.8 -> the x124.1 -12V lane. N_OV B lane moved south of
# the -12V lane (y91.75) -> via (123.35,91.5) on its F R55/R54 junction.
FINAL['V1-u8-escape'] = {
    'moves': [('R57', (118.6, 80.25), 180), ('R90', (118.4, 91.95), 180)],
    'delete': [('track', '16023f3a-ed7a-5048-af81-bd3b28f6536a'), ('via', '25874993-3740-5b18-8a73-8778624adbb9'),
               ('track', 'f7cd495a-878e-5098-bdb2-52f98f5c0536'), ('track', 'd3e053d8-9df4-5f9a-9ba1-04f53618dd2d'),
               ('track', '8f80ffdc-3342-5c27-aaea-f0dc32da6f7f'), ('track', 'b2dcb9e0-14dd-5330-a122-bf30e9d35c4a'),
               ('track', '951251a0-3ebd-509c-84a2-8aac923cc7fa'), ('via', 'b0d5d994-94e0-5679-9ab3-d5b731d5e76e'),
               ('track', '23a1a201-d924-59eb-b975-02ed8f527de4'), ('via', '47721f33-6623-5aa5-9bd6-abf5443b01b4'),
               ('track', 'e0ce6abd-0212-5a01-b6c2-75e64a252e64'), ('track', '038e3793-d61e-5962-8e6b-f72fcfedb824'),
               ('track', '4a1bb3b1-285b-50d4-bfcf-a8c890115319'), ('via', '2d49a510-2e14-5cf2-8ee8-fe741c3387ac'),
               ('track', '64869824-99f1-5b6e-9e95-066009e6841e'), ('track', '461b5df9-f994-506c-95a2-e570d4b5eb5b'),
               ('track', '3462a244-cb48-58c1-b7e8-81a28ed41631'),
               ('track', 'aa2b09b1-d329-510f-b9c7-9191b095174e'), ('via', '13873869-c81c-5f8e-aa15-a9e7c1dfc519'),
               ('track', '2b2ca52e-8d2a-5b68-a1e5-d777ef534458'), ('track', 'eddf2419-dc8f-51ff-95a4-afe1c8308905'),
               ('track', 'f2d16ed5-dbe9-50d1-bcc3-77eeb29d9ca5'), ('track', 'f4cac44b-d8cf-52a8-bc69-ca9bd78bded7'),
               ('via', '6e956b60-765f-5061-a9d3-2a48a3895380')],
    'vias': {'v1-ns-r57': ('N_SENSE', (117.8, 79.15)), 'v1-ns-pick': ('N_SENSE', (116.8, 86.3)),
             'v1-g-r57': ('N_GATE', (119.4, 79.15)), 'v1-pgd-0': ('N_PGD', (120.25, 87.75)), 'v1-pgd-1': ('N_PGD', (118.6, 77.2)),
             'v1-out-0': ('N_OUT_PIN', (120.375, 88.55), (0.5, 0.3)), 'v1-out-r90': ('N_OUT_PIN', (117.6, 90.95)),
             'v1-out-d20': ('N_OUT_PIN', (112.85, 88.75)), 'v1-m12': ('-12V', (119.2, 91.0)), 'v1-ov': ('N_OV', (123.35, 91.5))},
    'tracks': [
        ('N_SENSE', 'F.Cu', 0.25, ('pad', 'R57', '2'), [], ('via', 'v1-ns-r57')),
        ('N_SENSE', 'B.Cu', 0.25, ('via', 'v1-ns-r57'), [(117.6, 79.35), (117.6, 85.5)], ('via', 'v1-ns-pick')),
        ('N_SENSE', 'F.Cu', 0.25, ('via', 'v1-ns-pick'), [], ('pad', 'R89', '1')),
        ('N_GATE', 'F.Cu', 0.25, ('pad', 'R57', '1'), [], ('via', 'v1-g-r57')),
        ('N_GATE', 'B.Cu', 0.25, ('via', 'v1-g-r57'), [(119.9, 79.65), (119.9, 86.55), (120.4, 87.05), (121.0, 87.05)],
         ('vuu', '0a683347-84ee-5bc6-841e-4d43f0a0264d')),
        ('N_GATE', 'F.Cu', 0.25, ('pad', 'U8', '8'), [(120.95, 89.3)], ('pad', 'Q4', '1')),
        ('N_SENSE_PIN', 'F.Cu', 0.2, ('tuu', '5f41933f-bef6-5858-8cda-22a19931ffc5', (114.5, 87.5)), [],
         ('tuu', '15b7e70d-6799-537e-98b5-dd294c692c9d', (119.425, 87.5))),
        ('N_SENSE_PIN', 'F.Cu', 0.2, ('pad', 'U8', '7'), [(117.95, 89.8)], ('trk', 'V1-u8-escape/trk/6', (117.95, 87.5))),
        ('N_PGD', 'F.Cu', 0.2, ('pad', 'U8', '10'), [(119.75, 88.3)], ('via', 'v1-pgd-0')),
        ('N_PGD', 'B.Cu', 0.2, ('via', 'v1-pgd-0'), [(119.3, 87.75), (119.3, 80.6), (118.6, 79.9)], ('via', 'v1-pgd-1')),
        ('N_PGD', 'F.Cu', 0.2, ('via', 'v1-pgd-1'), [(118.6, 77.025), (123.85, 71.775), (129.85, 71.775), (130.55, 71.075), (131.5, 71.075),
                                                     (132.3, 70.275), (132.3, 69.325), (133.0, 68.625), (136.45, 68.625)], ('pad', 'U17', '2')),
        ('N_OUT_PIN', 'F.Cu', 0.2, ('pad', 'U8', '9'), [(120.1, 88.8)], ('via', 'v1-out-0')),
        ('N_OUT_PIN', 'B.Cu', 0.2, ('via', 'v1-out-0'), [(118.7, 88.55), (118.35, 88.2), (113.3, 88.2)], ('via', 'v1-out-d20')),
        ('N_OUT_PIN', 'B.Cu', 0.2, ('trk', 'V1-u8-escape/trk/12', (117.9, 88.2), 2), [(117.9, 90.65)], ('via', 'v1-out-r90')),
        ('N_OUT_PIN', 'F.Cu', 0.2, ('via', 'v1-out-r90'), [], ('pad', 'R90', '2')),
        ('N_OUT_PIN', 'F.Cu', 0.2, ('via', 'v1-out-d20'), [], ('pad', 'D20', '3')),
        ('-12V', 'F.Cu', 0.3, ('pad', 'R90', '1'), [], ('via', 'v1-m12')),
        ('-12V', 'B.Cu', 0.3, ('via', 'v1-m12'), [(119.4, 90.8), (123.95, 90.8)], ('tuu', 'f28cd4b2-ac74-50a0-b8a8-36dd5137e093', (124.1, 90.65))),
        ('N_OV', 'B.Cu', 0.2, ('vuu', '00f3479a-4eea-533c-8a9f-46d424afcc99'), [(116.0, 91.2), (116.55, 91.75), (123.1, 91.75)], ('via', 'v1-ov')),
    ],
}


# V2: N_VCC R51.2 feed (user-authorised In2 power-only hop: R51.2 is boxed on F by BAD_RC x110.2/N12_RAW/D20 and on B by
# POR_SENSE/FAULT_LATCH/VIN). N_VCC corner (114.6,94.475) -> via -> In2 0.3 mm slot in the V3V3 plane between the BAD_RC and
# GND vias, north between the V3V3 and VIN vias -> via (107.5,91.5) west of R51 -> F -> R51.2. V3V3 plane stays one piece.
FINAL['V2-nvcc-r51'] = {
    'vias': {'v2-nv-0': ('N_VCC', (114.6, 94.475)), 'v2-nv-1': ('N_VCC', (107.5, 91.5))},
    'tracks': [
        ('N_VCC', 'In2.Cu', 0.3, ('via', 'v2-nv-0'), [(114.2, 94.075), (108.6, 94.075), (108.2, 93.675), (108.2, 92.2)], ('via', 'v2-nv-1')),
        ('N_VCC', 'F.Cu', 0.3, ('via', 'v2-nv-1'), [], ('pad', 'R51', '2')),
    ],
}


# V3: C44 and R55 (AI-placed) rotated 180 in place so their N12_RAW pads face south, away from the B -12V/N_OV lanes that box
# the old pads in. N_TIMER U8.6 -> C44.1 (now north); N_OV via (123.35,91.5) -> R55.1 (now north) and R54.2; N12_RAW C44.2 -> R55.2
# (both south) -> via (121.2,93.25) for the B join to U16.3 and the west N12_RAW group (next batches).
FINAL['V3-c44-r55'] = {
    'moves': [('C44', (120.95, 91.5), 270), ('R55', (122.55, 91.5), 270)],
    'delete': [('track', '320653b9-7ab3-5e6d-8ec1-fed8eb22bc3d'), ('track', '1ed30ee3-9116-5ce7-9a88-4299916ed754'),
               ('track', '3d7bbba3-3f64-5101-88e6-86c49df23d37'), ('track', 'c6e45904-0c22-5b82-af66-f57573d4a69b'),
               ('track', '62208e6c-74be-54b0-b3c0-9a9ee3fae46e'), ('track', 'b0ce78a8-6e7a-55d2-b098-e7dcff142f30'),
               ('track', '4b3d23df-b69b-5b1e-b02f-2d191865f902')],
    'tracks': [
        ('N_TIMER', 'F.Cu', 0.2, ('pad', 'U8', '6'), [(120.05, 90.3)], ('pad', 'C44', '1')),
        ('N_OV', 'F.Cu', 0.2, ('vuu', '6e193ab6-aefd-597b-a550-46d9ee1fbb80'), [], ('pad', 'R55', '1')),
        ('N_OV', 'F.Cu', 0.2, ('vuu', '6e193ab6-aefd-597b-a550-46d9ee1fbb80'), [], ('pad', 'R54', '2')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'C44', '2'), [], ('pad', 'R55', '2')),
    ],
}


# V4: N12_RAW quiet-reference joins (one-connection helper, each checked): C44.2 -> F south under the U16 body (y95.725,
# between U16.1/U16.2 rows) -> U16.3; C44.2 -> F y92.825 under R90 -> via (116.75,93.05) -> B hop under the N_VCC run ->
# via (114.9,93.1) -> C43.2. Room for the hop vias: own N_UV B lane lifted from y92.6 to y92.4 (MHB4 keep-out below).
FINAL['V4-n12raw-join'] = {
    'delete': [('track', '5c2206c5-35fd-52d7-ae2a-5a9a1e289b04'), ('track', 'eb15e6d6-f64d-5dd6-b380-63a298357710'),
               ('track', '605d1aa3-4b56-5a0c-8541-3f1b34be98ee'), ('track', '4ebdf3f7-7053-523d-ab78-77d0a666130a')],
    'vias': {'v4-nr-0': ('N12_RAW', (116.75, 93.05)), 'v4-nr-1': ('N12_RAW', (114.9, 93.1))},
    'tracks': [
        ('N_UV', 'B.Cu', 0.2, ('vuu', '94abd9f5-8c89-5c54-a382-3ce3ef6bc3a1'), [(114.7, 92.4), (125.5, 92.4), (126.55, 93.45)],
         ('vuu', '0e1f65e6-13df-594a-9739-aed1a062b543')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'C44', '2'), [(120.95, 94.075), (122.6, 95.725), (128.25, 95.725)], ('pad', 'U16', '3')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'C44', '2'), [(120.4, 92.825), (117.1, 92.825)], ('via', 'v4-nr-0')),
        ('N12_RAW', 'B.Cu', 0.25, ('via', 'v4-nr-0'), [(116.6, 93.2), (115.0, 93.2)], ('via', 'v4-nr-1')),
        ('N12_RAW', 'F.Cu', 0.25, ('via', 'v4-nr-1'), [(114.9, 92.45)], ('pad', 'C43', '2')),
    ],
}


# L1: LED drivers next to their LEDs (user-authorised move of the unfixed AI-placed Q6/Q7/Q8 and R22/R86/R87): the west
# drivers needed six long cathode/anode runs across the USB-PD power block. Free F block x76-87.4, y88-95 (VPD F pour ends at
# x75.8 there). Row A y93.32: Q6 over D8.1, R22 over D8.2, Q7 over D16.1, R86 over D16.2 (straight drops; SMD pads end at
# y<=95.0, >=2.0 mm from the LED pads). Row B y89.5: Q8 (rot 180, drain west) and R87 for D17 (B lanes next batch).
# V3V3 resistor ends -> In2 V3V3 (via) / the U9.1 V3V3 via. The old MAIN_LED_OK leg to Q6 and the R87 V3V3 island via go.
FINAL['L1-led-drivers'] = {
    'moves': [('Q6', (77.48, 93.32), 270), ('Q7', (83.98, 93.32), 270), ('R22', (80.02, 93.4), 270), ('R86', (86.52, 93.4), 270),
              ('Q8', (83.7, 89.5), 180), ('R87', (86.6, 89.5), 90)],
    'delete_poly': ['W1-u13-north/trk/2'],
    'delete': [('track', '7d4c65af-962c-585b-9e07-9d2be8429b63'), ('via', 'a2111f0a-e93e-510b-9310-ad5b0d6eb33f')],
    'vias': {'l1-v3-r22': ('V3V3', (80.02, 91.6))},
    'tracks': [
        ('Net-(D8-K)', 'F.Cu', 0.25, ('pad', 'Q6', '3'), [], ('pad', 'D8', '1')),
        ('Net-(D8-A)', 'F.Cu', 0.25, ('pad', 'R22', '2'), [], ('pad', 'D8', '2')),
        ('Net-(D16-K)', 'F.Cu', 0.25, ('pad', 'Q7', '3'), [], ('pad', 'D16', '1')),
        ('Net-(D16-A)', 'F.Cu', 0.25, ('pad', 'R86', '2'), [], ('pad', 'D16', '2')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'R86', '1'), [], ('vuu', 'c64795df-c88c-5657-b7b1-b2f42f117a39')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'R87', '1'), [], ('pad', 'R86', '1')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'R22', '1'), [], ('via', 'l1-v3-r22')),
    ],
}


# L2: D17 cathode/anode on B (helper, one connection each): Q8.3 -> via (84.1,91.525) -> B 45-degree -> D17.1; R87.2 -> via
# (87.35,89.425) -> B -> D17.2 (parallel, 1.8 mm apart). U11.6 V3V3: own POR_SENSE R65.2 -> R66.1 F link moved to B (via east
# of R65.2 -> B -> the existing POR_SENSE via (107.65,90.025)) so U11.6 gets a dogbone via (106.35,88.75) into the In2 V3V3 plane.
FINAL['L2-d17-u11'] = {
    'delete': [('track', '94d18762-948f-5d10-9f65-413fac62151a'), ('track', 'aed48de3-626c-5d37-afa3-01c9c4d0041a'),
               ('track', 'cbbcbbcc-1564-5ddd-adbd-4b29587af22a')],
    'vias': {'l2-k': ('Net-(D17-K)', (84.1, 91.525)), 'l2-a': ('Net-(D17-A)', (87.35, 89.425)),
             'l2-ps': ('POR_SENSE', (106.55, 87.9)), 'l2-v3': ('V3V3', (106.35, 88.75))},
    'tracks': [
        ('Net-(D17-K)', 'F.Cu', 0.2, ('pad', 'Q8', '3'), [(82.75, 90.175)], ('via', 'l2-k')),
        ('Net-(D17-K)', 'B.Cu', 0.2, ('via', 'l2-k'), [], ('pad', 'D17', '1')),
        ('Net-(D17-A)', 'F.Cu', 0.2, ('pad', 'R87', '2'), [], ('via', 'l2-a')),
        ('Net-(D17-A)', 'B.Cu', 0.2, ('via', 'l2-a'), [(87.35, 92.175), (93.0, 97.825)], ('pad', 'D17', '2')),
        ('POR_SENSE', 'F.Cu', 0.2, ('pad', 'R65', '2'), [], ('via', 'l2-ps')),
        ('POR_SENSE', 'B.Cu', 0.2, ('via', 'l2-ps'), [(107.65, 89.0)], ('vuu', '1161de62-1c20-5bfd-aee1-2f97960dd94e')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'U11', '6'), [], ('via', 'l2-v3')),
    ],
}


# P1: TP4 VIN -> dogbone via (71.6,75.75) into the In2 VIN plane. +12V monitor feed (divider only, mA-level) R75.1 -> via -> B
# y73.425 -> via -> F diagonal parallel to the PGD run (1.24 mm) -> via (116.7,77.175) -> B y77.175/75.975 west of the -12V B band
# -> XB1.12 (one-connection helper).
FINAL['P1-vin-p12'] = {
    'vias': {'p1-vin': ('VIN', (71.6, 75.75)), 'p1-12-0': ('+12V', (127.45, 73.425)), 'p1-12-1': ('+12V', (120.45, 73.425)),
             'p1-12-2': ('+12V', (116.7, 77.175))},
    'tracks': [
        ('VIN', 'F.Cu', 0.3, ('pad', 'TP4', '1'), [], ('via', 'p1-vin')),
        ('+12V', 'F.Cu', 0.2, ('pad', 'R75', '1'), [(130.55, 76.525)], ('via', 'p1-12-0')),
        ('+12V', 'B.Cu', 0.2, ('via', 'p1-12-0'), [], ('via', 'p1-12-1')),
        ('+12V', 'F.Cu', 0.2, ('via', 'p1-12-1'), [], ('via', 'p1-12-2')),
        ('+12V', 'B.Cu', 0.2, ('via', 'p1-12-2'), [(109.8, 77.175), (108.6, 75.975), (104.35, 75.975), (103.45, 76.875)], ('pad', 'XB1', '12')),
    ],
}


# M1 (one-connection helper, each reviewed): ARMED U12.5 -> via under the U12 body -> B -> F hop over the B lane at y~87.5 ->
# B x94.6 north beside XB1 -> via -> F -> the W4 ARMED via at TP10. VPD U9.8 -> F loop north of U9 pins 7/6 -> U9.5 VPD stub.
FINAL['M1-armed-vpd'] = {
    'vias': {'m1-ar-0': ('ARMED', (97.65, 91.575)), 'm1-ar-1': ('ARMED', (94.75, 88.675)), 'm1-ar-2': ('ARMED', (94.75, 86.325)),
             'm1-ar-3': ('ARMED', (95.55, 76.325))},
    'tracks': [
        ('ARMED', 'F.Cu', 0.2, ('pad', 'U12', '5'), [(96.85, 91.575)], ('via', 'm1-ar-0')),
        ('ARMED', 'B.Cu', 0.2, ('via', 'm1-ar-0'), [], ('via', 'm1-ar-1')),
        ('ARMED', 'F.Cu', 0.2, ('via', 'm1-ar-1'), [], ('via', 'm1-ar-2')),
        ('ARMED', 'B.Cu', 0.2, ('via', 'm1-ar-2'), [(94.6, 86.175), (94.6, 77.275)], ('via', 'm1-ar-3')),
        ('ARMED', 'F.Cu', 0.2, ('via', 'm1-ar-3'), [], ('via', 'w-ar-1')),
        ('VPD', 'F.Cu', 0.25, ('pad', 'U9', '8'), [(88.25, 88.625), (88.25, 87.925), (88.6, 87.575), (89.85, 87.575), (90.2, 87.925)],
         ('pad', 'U9', '5')),
    ],
}


# M2: U9 VPD group (U9.5/U9.8/C46) -> main VPD (Q3.2/TP1 run): U9.8 -> via -> B west past the LED driver row B -> F hop ->
# B x81.4 -> via (81.2,83.325) -> F -> the Q3.2/TP1 VPD run (one-connection helper; LDO input, mA-level, 0.25 mm).
FINAL['M2-vpd-u9'] = {
    'vias': {'m2-0': ('VPD', (87.55, 88.175)), 'm2-1': ('VPD', (81.4, 89.375)), 'm2-2': ('VPD', (81.4, 87.475)), 'm2-3': ('VPD', (81.2, 83.325))},
    'tracks': [
        ('VPD', 'F.Cu', 0.25, ('pad', 'U9', '8'), [(87.8, 88.175)], ('via', 'm2-0')),
        ('VPD', 'B.Cu', 0.25, ('via', 'm2-0'), [(86.35, 89.375)], ('via', 'm2-1')),
        ('VPD', 'F.Cu', 0.25, ('via', 'm2-1'), [], ('via', 'm2-2')),
        ('VPD', 'B.Cu', 0.25, ('via', 'm2-2'), [(81.4, 85.975), (81.2, 85.775)], ('via', 'm2-3')),
        ('VPD', 'F.Cu', 0.25, ('via', 'm2-3'), [(81.5, 83.025)], ('tuu', 'ea91b733-3cb4-5bea-a8df-37f2076f0232', (81.5, 81.1))),
    ],
}


# M3: RESET_N U13.1 -> via -> B under U13 -> F hop south of the MHB2 keep-out -> B diagonal past D9 -> via (89.3,80.225) -> F
# west of XB1 -> R67.2 (RESET_N, joins U12.1) (one-connection helper).
FINAL['M3-reset'] = {
    'vias': {'m3-0': ('RESET_N', (75.55, 72.025)), 'm3-1': ('RESET_N', (78.7, 71.525)), 'm3-2': ('RESET_N', (80.95, 73.075)),
             'm3-3': ('RESET_N', (89.3, 80.225))},
    'tracks': [
        ('RESET_N', 'F.Cu', 0.2, ('pad', 'U13', '1'), [(69.85, 71.125), (70.75, 72.025)], ('via', 'm3-0')),
        ('RESET_N', 'B.Cu', 0.2, ('via', 'm3-0'), [(76.05, 71.525)], ('via', 'm3-1')),
        ('RESET_N', 'F.Cu', 0.2, ('via', 'm3-1'), [(79.3, 70.925), (79.85, 70.925), (80.95, 72.025)], ('via', 'm3-2')),
        ('RESET_N', 'B.Cu', 0.2, ('via', 'm3-2'), [(83.5, 75.625), (84.7, 75.625)], ('via', 'm3-3')),
        ('RESET_N', 'F.Cu', 0.2, ('via', 'm3-3'), [(89.3, 81.825), (91.7, 84.225), (95.4, 84.225)], ('pad', 'R67', '2')),
    ],
}


# ---------------------------------------------------------------------------------------------
# one-connection suggestion helper (prints only)
RES = 0.05
X0, Y0, X1, Y1 = 49.75, 62.275, 150.25, 102.275
CLR = 0.2
MARGIN = 0.03
PATH_BUDGET = 3_000_000


def _grid():
    nx, ny = int(round((X1 - X0) / RES)) + 1, int(round((Y1 - Y0) / RES)) + 1
    return nx, ny


def _rast(polys, nx, ny):
    from PIL import Image, ImageDraw
    import numpy as np
    img = Image.new('1', (nx, ny), 0)
    d = ImageDraw.Draw(img)
    for poly in polys:
        if len(poly) >= 3:
            d.polygon([((x - X0) / RES, (y - Y0) / RES) for x, y in poly], fill=1, outline=1)
    return np.array(img, dtype=bool)


def _sps_polys(sps):
    import pcbnew
    M = pcbnew.ToMM
    out = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i)
        out.append([(M(o.CPoint(k).x), M(o.CPoint(k).y)) for k in range(o.PointCount())])
    return out


def obstacles(netname, width):
    import numpy as np
    import pcbnew
    b = pcbnew.LoadBoard(str(R.BOARD))
    zs = [z for z in b.Zones() if not z.GetIsRuleArea()]
    pcbnew.ZONE_FILLER(b).Fill(zs)
    nx, ny = _grid()
    MM = pcbnew.FromMM
    hw = width / 2
    vr = R.V6[0] / 2  # use the explicitly selected candidate via diameter
    lay = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
    tpol = {'F': [], 'B': []}
    vpol = []           # via centre forbidden (any layer copper of other nets, inflated by via r)
    for f in b.GetFootprints():
        for p in f.Pads():
            same = p.GetNetname() == netname
            for L, lid in lay.items():
                if not p.IsOnLayer(lid):
                    continue
                if not same:
                    s = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(s, lid, MM(CLR + hw + MARGIN), MM(0.005), pcbnew.ERROR_OUTSIDE)
                    tpol[L] += _sps_polys(s)
                s = pcbnew.SHAPE_POLY_SET()
                smd = p.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN)
                mask = max(p.GetSolderMaskExpansion(pcbnew.F_Mask), 0) if smd else 0
                if smd or not same:
                    p.TransformShapeToPolygon(s, lid, MM((CLR if not same else 0.1) + mask + vr + MARGIN), MM(0.005),
                                              pcbnew.ERROR_OUTSIDE)
                    vpol += _sps_polys(s)
            if p.GetDrillSizeX():
                r = pcbnew.ToMM(max(p.GetDrillSizeX(), p.GetDrillSizeY())) / 2
                c = (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))
                circ = [(c[0] + (r + 0.25 + vr + 0.2) * math.cos(a / 16 * math.pi), c[1] + (r + 0.25 + vr + 0.2) * math.sin(a / 16 * math.pi)) for a in range(32)]
                vpol.append(circ)
                if not p.IsOnCopperLayer() or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    circ2 = [(c[0] + (r + 0.25 + hw + MARGIN) * math.cos(a / 16 * math.pi), c[1] + (r + 0.25 + hw + MARGIN) * math.sin(a / 16 * math.pi)) for a in range(32)]
                    tpol['F'].append(circ2)
                    tpol['B'].append(circ2)
    for t in b.GetTracks():
        same = t.GetNetname() == netname
        for L, lid in lay.items():
            if not t.IsOnLayer(lid):
                continue
            if not same:
                s = pcbnew.SHAPE_POLY_SET()
                t.TransformShapeToPolygon(s, lid, MM(CLR + hw + MARGIN), MM(0.005), pcbnew.ERROR_OUTSIDE)
                tpol[L] += _sps_polys(s)
        if not same:
            s = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(s, pcbnew.F_Cu if t.GetClass() == 'PCB_VIA' else t.GetLayer(),
                                      MM(CLR + vr + MARGIN), MM(0.005), pcbnew.ERROR_OUTSIDE)
            vpol += _sps_polys(s)
        if t.GetClass() == 'PCB_VIA':
            c = (pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y))
            rr = 0.15 + 0.25 + 0.15 + 0.05
            vpol.append([(c[0] + rr * math.cos(a / 16 * math.pi), c[1] + rr * math.sin(a / 16 * math.pi)) for a in range(32)])
    for z in zs:
        if z.GetNetname() == netname:
            continue
        for L, lid in lay.items():
            if z.IsOnLayer(lid):
                s = z.GetFilledPolysList(lid).CloneDropTriangulation()
                s.Inflate(MM(CLR + hw + MARGIN), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005))
                tpol[L] += _sps_polys(s)
                s = z.GetFilledPolysList(lid).CloneDropTriangulation()
                s.Inflate(MM(CLR + vr + MARGIN), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005))
                vpol += _sps_polys(s)
    keep = []
    for z in b.Zones():
        if z.GetIsRuleArea():
            s = z.Outline().CloneDropTriangulation()
            s.Inflate(MM(hw + MARGIN), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005))
            keep += _sps_polys(s)
    edge = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(edge, False)
    e_t, e_v = edge.CloneDropTriangulation(), edge.CloneDropTriangulation()
    e_t.Inflate(-MM(1.0 + hw + MARGIN), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.005))
    e_v.Inflate(-MM(1.0 + vr + MARGIN), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.005))
    inside_t, inside_v = _rast(_sps_polys(e_t), nx, ny), _rast(_sps_polys(e_v), nx, ny)
    kp = _rast(keep, nx, ny)
    blk = {L: _rast(tpol[L], nx, ny) | kp | ~inside_t for L in lay}
    vblk = _rast(vpol, nx, ny) | kp | ~inside_v | blk['F'] | blk['B']
    return blk, vblk


def path(netname, layers, a, bpt, width=0.2, viacost=40):
    import numpy as np
    blk, vblk = obstacles(netname, width)
    ny, nx = blk['F'].shape
    Ls = list(layers)
    cell = lambda p: (int(round((p[0] - X0) / RES)), int(round((p[1] - Y0) / RES)))  # noqa: E731
    sa, sb = cell(a), cell(bpt)
    for L in Ls:                         # endpoints sit on their own pads: clear a small disc
        for (cx, cy) in (sa, sb):
            blk[L][max(cy - 6, 0):cy + 7, max(cx - 6, 0):cx + 7] &= False
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    start = [(0.0, (sa[0], sa[1], li, -1)) for li in range(len(Ls)) if a[2] is None or Ls[li] == a[2]]
    goal_layers = {li for li in range(len(Ls)) if len(bpt) < 3 or bpt[2] is None or Ls[li] == bpt[2]}
    h = lambda x, y: math.hypot(x - sb[0], y - sb[1])  # noqa: E731
    best = {}
    prev = {}
    pq = [(h(sa[0], sa[1]), g, s) for g, s in start]
    for _, g, s in pq:
        best[s] = g
    heapq.heapify(pq)
    goal = None
    n = 0
    while pq:
        f, g, s = heapq.heappop(pq)
        if best.get(s, 1e18) < g:
            continue
        x, y, li, d = s
        if (x, y) == sb and li in goal_layers:
            goal = s
            break
        n += 1
        if n > PATH_BUDGET:
            break
        for di, (dx, dy) in enumerate(dirs):
            X, Y = x + dx, y + dy
            if not (0 <= X < nx and 0 <= Y < ny) or blk[Ls[li]][Y, X]:
                continue
            c = g + (1.4142 if dx and dy else 1.0) + (2.0 if d not in (-1, di) else 0)
            t = (X, Y, li, di)
            if c < best.get(t, 1e18):
                best[t] = c
                prev[t] = s
                heapq.heappush(pq, (c + h(X, Y), c, t))
        if len(Ls) > 1 and not vblk[y, x]:
            for lj in range(len(Ls)):
                if lj != li:
                    t = (x, y, lj, -1)
                    c = g + viacost
                    if c < best.get(t, 1e18):
                        best[t] = c
                        prev[t] = s
                        heapq.heappush(pq, (c + h(x, y), c, t))
    if goal is None:
        print('NO PATH', netname, layers, a, bpt, 'expanded', n, 'budget_exhausted', n > PATH_BUDGET)
        return None
    seq = []
    s = goal
    while s in prev:
        seq.append(s)
        s = prev[s]
    seq.append(s)
    seq.reverse()
    pts = [(round(X0 + x * RES, 3), round(Y0 + y * RES, 3), Ls[li]) for x, y, li, _ in seq]
    # compress to corners per layer run
    runs = []
    for p in pts:
        if runs and runs[-1][0] == p[2]:
            runs[-1][1].append(p[:2])
        else:
            if runs:
                runs.append((p[2], [runs[-1][1][-1]]))   # via point
                runs[-1][1].pop()
                runs[-1][1].append(runs[-2][1][-1])
            else:
                runs.append((p[2], []))
            runs[-1][1].append(p[:2])
    out = []
    for L, ps in runs:
        cs = [ps[0]]
        for i in range(1, len(ps) - 1):
            d1 = (round((ps[i][0] - ps[i - 1][0]) / RES), round((ps[i][1] - ps[i - 1][1]) / RES))
            d2 = (round((ps[i + 1][0] - ps[i][0]) / RES), round((ps[i + 1][1] - ps[i][1]) / RES))
            if d1 != d2:
                cs.append(ps[i])
        if len(ps) > 1:
            cs.append(ps[-1])
        out.append((L, [(round(x, 3), round(y, 3)) for x, y in cs]))
    out = [(L, [p for i, p in enumerate(cs) if i == 0 or p != cs[i - 1]]) for L, cs in out]
    return out


def endpoint(spec):
    """'U12.9' -> pad centre + its layer; 'x,y,L' -> point."""
    import pcbnew
    if ',' in spec:
        x, y, L = spec.split(',')
        return (float(x), float(y), None if L == '*' else L), ('pt', (float(x), float(y)))
    ref, num = spec.split('.')
    b = pcbnew.LoadBoard(str(R.BOARD))
    p = next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
    L = None if p.GetDrillSizeX() else ('F' if p.IsOnLayer(pcbnew.F_Cu) else 'B')
    return (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), L), ('pad', ref, num)


def suggest(tag, net, layers, s0, s1, w=0.2, vc=40):
    a, ea = endpoint(s0)
    b, eb = endpoint(s1)
    out = path(net, layers, a, b, w, vc)
    if not out:
        return
    vias, trks = {}, []
    short = net.lstrip('/')
    for i, (L, cs) in enumerate(out):
        st = ea if i == 0 else ('via', f'{tag}-{i - 1}')
        en = eb if i == len(out) - 1 else ('via', f'{tag}-{i}')
        if i < len(out) - 1:
            vias[f'{tag}-{i}'] = (short, cs[-1])
        wps = cs[1:-1] if st[0] != 'pt' else cs[1:-1]
        trks.append((short, L + '.Cu', w, st, wps, en))
    print('VIAS', repr(vias))
    for t in trks:
        print('TRK ', repr(t) + ',')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'apply':
        sys.exit(R.apply(sys.argv[2]))
    elif cmd == 'ops':
        import json
        from pathlib import Path
        Path(sys.argv[3]).write_text(json.dumps(emit(sys.argv[2]), indent=1))
    elif cmd == 'path':
        tag, net, layers, s0, s1 = sys.argv[2:7]
        w = float(sys.argv[7]) if len(sys.argv) > 7 else 0.2
        vc = float(sys.argv[8]) if len(sys.argv) > 8 else 40
        suggest(tag, net, layers, s0, s1, w, vc)
