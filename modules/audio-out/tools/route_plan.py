#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the audio-out carrier.

All geometry is written out here in panel-frame millimetres (KiCad = +100/+50); nothing
is autorouted. Layer plan (docs/research.md section 3.6), panel order IN L, IN R, LINE, VOL L, VOL R,
PHONES (docs/geometry.json):
  F.Cu  edge lanes: +12V left (X1.4), -12V right (X18.6) with one spur per opamp group;
        IN_L from J1 T to the J2 TN normal; BUF_L down the middle (X12.0) to the R7 via
        and RV1 pin 3; BUF_R down the middle (X9.6) to the R8 via, then the left side
        (X2.7) to RV2 pin 3; GND pour.
  B.Cu  every SMD-local connection (input chains, opamp pins, decoupling, line-out
        build-outs), HP_L right edge (X18.6) and HP_R left (X2.4) down to PHONES; GND pour.
Vias 0.6/0.3 mm. Tracks 0.25 mm signal, 0.4 mm rails and headphone outputs, 0.5 mm at the
power header. GND pours on both layers with thermal-relief pad connections.

  python3 -B tools/route_plan.py > research/route/plan.json   (then shared pcb plan/apply/promote)
"""
import json
import sys
import uuid

SIG, PWR, HDR, VIA = 0.25, 0.4, 0.5, (0.6, 0.3)
B, F = 'B.Cu', 'F.Cu'
OX, OY = 100.0, 50.0
XL, XR = 1.4, 18.6          # F.Cu rail lanes (+12V left, -12V right); 0.5 mm edge rule
HL, HR = 2.4, 18.6          # B.Cu headphone lanes (HP_R left, HP_L right)

ops = []


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/audio-out/route/' + key))


def a(x, y):
    """Panel frame -> KiCad board coordinates."""
    return [round(OX + x, 4), round(OY + y, 4)]


def via(name, net, x, y):
    ops.append({'op': 'add_via', 'uuid': uid('via/' + name), 'net': '/' + net, 'at': a(x, y),
                'diameter_mm': VIA[0], 'drill_mm': VIA[1]})
    return name


def end(e):
    if isinstance(e, tuple):
        return {'pad': {'ref': e[0], 'number': e[1]}}
    return {'uuid': uid('via/' + e)}


def track(name, net, layer, s, pts, e, w=SIG):
    ops.append({'op': 'add_polyline', 'uuid': uid('trk/' + name), 'net': '/' + net, 'layer': layer,
                'start': end(s), 'waypoints': [a(x, y) for x, y in pts], 'end': end(e), 'width_mm': w})


# ---- power entry: J5 -> D1/D2 (series Schottky) -> bulk -> F.Cu edge lanes ----------------
track('p12tie', '+12V_IN', B, ('J5', '9'), [], ('J5', '10'), HDR)
track('p12in', '+12V_IN', B, ('J5', '9'), [], ('D1', '2'), HDR)
track('p12c3', '+12V', B, ('D1', '1'), [], ('C3', '1'), PWR)
via('p12', '+12V', XL, 106.85)
track('p12v', '+12V', B, ('D1', '1'), [], 'p12', PWR)
track('m12tie', '-12V_IN', B, ('J5', '1'), [], ('J5', '2'), HDR)
track('m12in', '-12V_IN', B, ('J5', '2'), [(13.0, 116.65)], ('D2', '1'), HDR)
track('m12c4', '-12V', B, ('D2', '2'), [], ('C4', '2'), PWR)
via('m12', '-12V', XR, 113.35)
track('m12v', '-12V', B, ('D2', '2'), [], 'm12', PWR)

# +12V lane (F.Cu, left edge) -> U2 group (via on the lane, B.Cu to C9/C7) -> U1 (via left of U1)
via('p12u2', '+12V', XL, 71.6)
via('p12u1', '+12V', 4.6, 24.6)
track('p12f1', '+12V', F, 'p12', [], 'p12u2', PWR)
track('p12f2', '+12V', F, 'p12u2', [(XL, 24.6)], 'p12u1', PWR)
track('p12c9', '+12V', B, 'p12u2', [(5.05, 71.6)], ('C9', '1'), PWR)
track('p12c7', '+12V', B, 'p12u2', [(4.7, 71.6)], ('C7', '1'), PWR)
track('p12u2b', '+12V', B, ('C7', '1'), [(6.2, 73.595)], ('U2', '8'), SIG)
track('p12u1a', '+12V', B, 'p12u1', [], ('U1', '8'), PWR)
track('p12u1b', '+12V', B, ('U1', '8'), [], ('C5', '1'), SIG)

# -12V lane (F.Cu, right edge) -> U2 (via below C8) -> C10 (via above it) -> U1 (via right of C6)
via('m12u2', '-12V', 14.6, 79.0)
via('m12c10', '-12V', 16.6, 68.3)
via('m12u1', '-12V', 14.0, 30.4)
track('m12f1', '-12V', F, 'm12', [(XR, 79.0)], 'm12u2', PWR)
track('m12f2', '-12V', F, 'm12u2', [(XR, 79.0), (XR, 68.3)], 'm12c10', PWR)
track('m12f3', '-12V', F, 'm12c10', [(XR, 68.3), (XR, 30.4)], 'm12u1', PWR)
track('m12u2a', '-12V', B, 'm12u2', [], ('C8', '2'), PWR)
track('m12u2b', '-12V', B, ('C8', '2'), [], ('U2', '4'), SIG)
track('m12c10b', '-12V', B, 'm12c10', [(16.05, 69.0)], ('C10', '2'), PWR)
track('m12u1a', '-12V', B, 'm12u1', [], ('C6', '2'), PWR)
track('m12u1b', '-12V', B, ('C6', '2'), [], ('U1', '4'), SIG)

# ---- L input chain (row Y15.4): J1 T -> R1 -> C1 -> T_L -> R3 -> A_L (R5 to GND) -> U1 +A --
track('inl', 'IN_L', B, ('J1', 'T'), [(15.825, 17.0)], ('R1', '1'))
track('inrl', 'INR_L', B, ('R1', '2'), [], ('C1', '1'))
track('tl', 'T_L', B, ('C1', '2'), [], ('R3', '1'))
track('al', 'A_L', B, ('R3', '2'), [], ('R5', '1'))
track('alu1', 'A_L', B, ('R3', '2'), [(8.6, 16.8), (8.6, 21.9), (14.4, 21.9), (14.4, 26.885)], ('U1', '3'))
# IN R normal: J1 T -> J2 TN (F.Cu, left of the BUF_R via)
track('inln', 'IN_L', F, ('J1', 'T'), [(12.6, 21.8), (8.6, 21.8), (8.6, 31.4)], ('J2', 'TN'))

# ---- R input chain (row Y36.3): J2 T -> R2 -> C2 -> T_R -> R4 -> A_R (R6 to GND) -> U1 +B --
track('inr', 'IN_R', B, ('J2', 'T'), [(15.825, 35.0)], ('R2', '1'))
track('inrr', 'INR_R', B, ('R2', '2'), [], ('C2', '1'))
track('tr', 'T_R', B, ('C2', '2'), [], ('R4', '1'))
track('ar', 'A_R', B, ('R4', '2'), [], ('R6', '1'))
track('aru1', 'A_R', B, ('R4', '2'), [(8.6, 34.9), (8.6, 29.0)], ('U1', '5'))

# ---- U1 followers and BUF fan-out ---------------------------------------------------------
track('bufl12', 'BUF_L', B, ('U1', '1'), [], ('U1', '2'))
track('bufr76', 'BUF_R', B, ('U1', '7'), [], ('U1', '6'))
via('bufl', 'BUF_L', 13.0, 22.9)
via('bufr', 'BUF_R', 9.6, 29.8)
track('bufls', 'BUF_L', B, ('U1', '1'), [], 'bufl')
track('bufrs', 'BUF_R', B, ('U1', '6'), [(9.6, 27.3)], 'bufr')
# line-out build-outs: F.Cu down the middle to a via above each resistor
via('bufl2', 'BUF_L', 14.92, 40.6)
via('bufr2', 'BUF_R', 6.62, 40.6)
track('bufld', 'BUF_L', F, 'bufl', [(12.0, 23.9), (12.0, 40.6)], 'bufl2')
track('bufrd', 'BUF_R', F, 'bufr', [(9.6, 40.6)], 'bufr2')
track('bufl7', 'BUF_L', B, 'bufl2', [], ('R7', '1'))
track('bufr8', 'BUF_R', B, 'bufr2', [], ('R8', '1'))
track('linel', 'LINE_L', B, ('R7', '2'), [], ('J3', 'T'))
track('liner', 'LINE_R', B, ('R8', '2'), [], ('J3', 'R'))
# pot CW ends (F.Cu): BUF_L straight down X12.0 to RV1 pin 3; BUF_R through the LINE gap,
# then the left side (X2.7, inside the +12V lane) and under the RV2 tabs to RV2 pin 3
track('bufl1', 'BUF_L', F, 'bufl2', [(12.0, 40.6), (12.0, 68.5)], ('RV1', '3'))
track('bufr1', 'BUF_R', F, 'bufr2', [(9.6, 40.6), (9.6, 50.0), (2.7, 56.9), (2.7, 85.5), (12.5, 85.5)],
      ('RV2', '3'))

# ---- volume wipers -> taper loads -> U2 followers -> build-out -> PHONES ------------------
track('voll1', 'VOL_L', B, ('RV1', '2'), [], ('R9', '1'))
track('voll2', 'VOL_L', B, ('R9', '1'), [(10.6, 76.135)], ('U2', '3'))
track('volr1', 'VOL_R', B, ('RV2', '2'), [], ('R10', '1'))
track('volr2', 'VOL_R', B, ('R10', '1'), [(10.0, 78.6), (8.8, 77.405)], ('U2', '5'))
track('hpld12', 'HP_L_DRV', B, ('U2', '1'), [], ('U2', '2'))
track('hprd76', 'HP_R_DRV', B, ('U2', '7'), [], ('U2', '6'))
track('hpld', 'HP_L_DRV', B, ('U2', '1'), [(14.2, 73.595), (15.0, 72.737)], ('R11', '1'), PWR)
track('hprd', 'HP_R_DRV', B, ('U2', '6'), [(5.0, 76.135)], ('R12', '1'), PWR)
track('hpl', 'HP_L', B, ('R11', '2'), [(HR, 77.2), (HR, 94.0)], ('J4', 'T'), PWR)
track('hpr', 'HP_R', B, ('R12', '2'), [(HL, 91.0)], ('J4', 'R'), PWR)

# ---- GND stitching: ties the two pours in open areas (both layers clear there) ------------
for n, (x, y) in enumerate([(3.0, 12.0), (17.0, 12.0), (17.0, 26.0), (3.0, 28.5), (3.5, 40.0), (17.0, 40.0),
                            (10.8, 44.0), (6.0, 52.0), (16.0, 55.0), (7.0, 59.5), (5.0, 86.8), (16.5, 86.5),
                            (10.0, 93.0), (13.0, 101.0), (7.0, 101.0), (17.0, 107.5), (3.0, 117.5)]):
    via(f'gnd{n}', 'GND', x, y)


def zone(name, net, layer, poly):
    ops.append({'op': 'add_zone', 'uuid': uid('zone/' + name), 'net': '/' + net, 'layer': layer,
                'polygon': [a(x, y) for x, y in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.2,
                'pad_connection': 'thermal'})


# ---- GND pours on both layers (whole board), thermal reliefs: hand-soldered GND pins and no
#      0603 tombstoning on the reflowed back ------------------------------------------------
X0, X1, Y0, Y1 = 0.475, 19.525, 9.225, 119.275       # board outline
zone('gnd/' + B, 'GND', B, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])
zone('gnd/' + F, 'GND', F, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])

if __name__ == '__main__':
    json.dump({'schema_version': 1, 'operations': ops}, sys.stdout, indent=1)
    sys.stdout.write('\n')
