#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the imix R3 carrier.

All geometry is written out here in panel-frame millimetres (docs/geometry.json) and
shifted by kicad_origin_mm; nothing is autorouted. Layer plan (docs/research.md 3.4):
  buffers  one TL072 cluster per channel pair, B.Cu, centred (16, row + 13) below rows 1
           and 3. Left section (pins 5-8) = upper channel, right section (pins 1-4) =
           lower channel; feedback R || C beside each pin column, input R below it.
  inputs   F.Cu: upper channel from its jack tip down X10.5 to a via left of the
           cluster, then B down X9.0 to its input R; lower channel from its jack tip
           across Y(row + 17.2) to a via under its input R.
  pots     upper channel: 100R -> via -> F.Cu across Y(row + 9.1) to pot pin 3;
           lower channel: 100R -> B.Cu down X23.7 between the pot brackets to pin 3.
  SUM      wiper -> 100k under each pot (B) -> via -> F.Cu to the right-edge bus X28.3
           -> down to Y91.5 -> via -> U3 summer (B, below RV4).
  rails    J10 -> D1/D2 -> C1/C2 (B, right of the header). +12V: F.Cu Y103.05 to U3 and
           on to the left edge, B.Cu up X3.2; -12V: B.Cu along the bottom edge Y118.4 and
           up X1.6, F.Cu X26 to U3. Each cluster takes F.Cu taps (+12V row + 11,
           -12V row + 14.2) to vias under the SOIC body.
  GND      poured on both layers, local vias at every SMD GND pad, stitched.
Vias 0.6/0.3 mm. Tracks 0.25 mm signal, 0.4 mm rails.

  python3 -B tools/route_plan.py > research/route/plan.json   (then shared pcb plan/apply/promote)
"""
import json
import sys
import uuid
from pathlib import Path

GEO = json.loads((Path(__file__).resolve().parents[1] / 'docs/geometry.json').read_text())
OX, OY = GEO['kicad_origin_mm']
SIG, PWR, VIA = 0.25, 0.4, (0.6, 0.3)
B, F = 'B.Cu', 'F.Cu'
ROWY = {p['channel']: p['XY'][1] for p in GEO['pots']}            # pot shaft / jack row Y
JACKY = {j['role']: j['XY'][1] for j in GEO['jacks']}
TIP = -4.92                                                       # jack T pad above the shaft
PIN_ROW = 7.5                                                     # RV pins 1-3 below the shaft
EDGE_SUM, RAIL_P, RAIL_M = 28.3, 3.2, 1.6

ops = []


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/imix/route-r3/' + key))


def p(x, y):
    return [round(OX + x, 4), round(OY + y, 4)]


def via(name, net, x, y):
    ops.append({'op': 'add_via', 'uuid': uid('via/' + name), 'net': net, 'at': p(x, y),
                'diameter_mm': VIA[0], 'drill_mm': VIA[1]})
    return name


def end(e):
    if isinstance(e, tuple):
        return {'pad': {'ref': e[0], 'number': e[1]}}
    return {'uuid': uid('via/' + e)}


def track(name, net, layer, a, pts, b, w=SIG):
    ops.append({'op': 'add_polyline', 'uuid': uid('trk/' + name), 'net': net, 'layer': layer,
                'start': end(a), 'waypoints': [p(x, y) for x, y in pts], 'end': end(b), 'width_mm': w})


# ---- input-buffer clusters ---------------------------------------------------------------
CLUSTERS = (('U1', 1, 2, 'C3', 'C4'), ('U2', 3, 4, 'C5', 'C6'))
for u, top, bot, cp, cm in CLUSTERS:
    y = ROWY[top]
    cx, cy = 16.0, y + 13.0
    # upper channel (section B, left column: 8 V+, 7 OUT, 6 -, 5 +)
    n = top
    rin, rfb, cfb, r100 = f'R{n}', f'R{n + 4}', f'C{n + 8}', f'R{n + 8}'
    track(f'buf{n}a', f'/BUF{n}', B, (u, '7'), [], (rfb, '2'))
    track(f'buf{n}b', f'/BUF{n}', B, (rfb, '2'), [], (cfb, '2'))
    track(f'buf{n}c', f'/BUF{n}', B, (rfb, '2'), [], (r100, '1'))
    track(f'inv{n}a', f'/INV{n}', B, (u, '6'), [], (rfb, '1'))
    track(f'inv{n}b', f'/INV{n}', B, (rfb, '1'), [], (cfb, '1'))
    track(f'inv{n}c', f'/INV{n}', B, (rin, '2'), [], (rfb, '1'))
    via(f'pot{n}', f'/POT{n}', 9.875, y + 9.1)
    track(f'pot{n}a', f'/POT{n}', B, (r100, '2'), [], f'pot{n}')
    track(f'pot{n}b', f'/POT{n}', F, f'pot{n}', [(23.5, y + 9.1)], (f'RV{n}', '3'))
    via(f'in{n}', f'/IN{n}', 9.0, y + 8.8)
    track(f'in{n}a', f'/IN{n}', F, (f'J{n}', 'T'), [(10.5, y + TIP), (10.5, y + 8.0)], f'in{n}')
    track(f'in{n}b', f'/IN{n}', B, f'in{n}', [(9.0, cy + 2.9)], (rin, '1'))
    # lower channel (section A, right column: 1 OUT, 2 -, 3 +, 4 V-)
    n = bot
    rin, rfb, cfb, r100 = f'R{n}', f'R{n + 4}', f'C{n + 8}', f'R{n + 8}'
    track(f'buf{n}a', f'/BUF{n}', B, (u, '1'), [], (rfb, '2'))
    track(f'buf{n}b', f'/BUF{n}', B, (rfb, '2'), [], (cfb, '2'))
    track(f'buf{n}c', f'/BUF{n}', B, (cfb, '2'), [], (r100, '1'))
    track(f'inv{n}a', f'/INV{n}', B, (u, '2'), [], (rfb, '1'))
    track(f'inv{n}b', f'/INV{n}', B, (rfb, '1'), [], (cfb, '1'))
    track(f'inv{n}c', f'/INV{n}', B, (rin, '2'), [], (rfb, '1'))
    track(f'pot{n}', f'/POT{n}', B, (r100, '2'), [(23.7, ROWY[n] + PIN_ROW - 1.5)], (f'RV{n}', '3'))
    via(f'in{n}', f'/IN{n}', cx + 6.125, y + 17.2)
    track(f'in{n}a', f'/IN{n}', F, (f'J{n}', 'T'), [(8.2, y + 17.2)], f'in{n}')
    track(f'in{n}b', f'/IN{n}', B, f'in{n}', [], (rin, '1'))
    # supplies and (+) inputs
    via(f'gnd{u}', 'GND', cx, cy - 0.3)
    track(f'gnd{u}a', 'GND', B, (u, '3'), [], f'gnd{u}')
    track(f'gnd{u}b', 'GND', B, (u, '5'), [(cx - 1.0, cy + 1.905)], f'gnd{u}')
    via(f'p12{u}', '+12V', cx - 0.9, y + 11.0)
    track(f'p12{u}a', '+12V', B, f'p12{u}', [], (u, '8'), PWR)
    track(f'p12{u}b', '+12V', B, (u, '8'), [], (cp, '1'), PWR)
    via(f'm12{u}', '-12V', cx + 0.9, y + 14.2)
    track(f'm12{u}a', '-12V', B, f'm12{u}', [], (u, '4'), PWR)
    track(f'm12{u}b', '-12V', B, (u, '4'), [], (cm, '2'), PWR)
    via(f'g{cp}', 'GND', cx - 2.475, cy - 6.1)
    track(f'g{cp}', 'GND', B, (cp, '2'), [], f'g{cp}')
    via(f'g{cm}', 'GND', cx + 2.475, cy + 6.1)
    track(f'g{cm}', 'GND', B, (cm, '1'), [], f'g{cm}')
    # rail taps from the left-edge rails
    via(f'pl{u}', '+12V', RAIL_P, y + 11.0)
    track(f'p12{u}f', '+12V', F, f'pl{u}', [], f'p12{u}', PWR)
    via(f'ml{u}', '-12V', RAIL_M, y + 14.2)
    track(f'm12{u}f', '-12V', F, f'ml{u}', [], f'm12{u}', PWR)

# ---- wipers -> 100k -> SUM bus (right edge, F.Cu) -> U3 ----------------------------------
for n, y in ROWY.items():
    track(f'wiper{n}', f'/WIPER{n}', B, (f'RV{n}', '2'), [], (f'R{n + 12}', '1'))
    via(f'sum{n}', '/SUM', 21.0, y + 2.5)
    track(f'sum{n}a', '/SUM', B, (f'R{n + 12}', '2'), [], f'sum{n}')
via('sumu', '/SUM', 16.6, 91.5)
for n, y in ROWY.items():  # bus: each row's via -> X28.3 -> next row's via (row 4: -> U3)
    if n < 4:
        track(f'bus{n}', '/SUM', F, f'sum{n}', [(EDGE_SUM, y + 2.5), (EDGE_SUM, ROWY[n + 1] + 2.5)], f'sum{n + 1}')
    else:
        track(f'bus{n}', '/SUM', F, f'sum{n}', [(EDGE_SUM, y + 2.5), (EDGE_SUM, 91.5)], 'sumu')
track('sumu1', '/SUM', B, 'sumu', [], ('C13', '1'))
track('sumu2', '/SUM', B, ('C13', '1'), [], ('R17', '1'))
track('sumu3', '/SUM', B, ('R17', '1'), [], ('U3', '2'))

# ---- summer output, spare, output (B.Cu) ---------------------------------------------------
track('mix1', '/MIX', B, ('C13', '2'), [], ('R17', '2'))
track('mix2', '/MIX', B, ('R17', '2'), [], ('U3', '1'))
track('mix3', '/MIX', B, ('R17', '2'), [(10.0, 93.5)], ('R18', '1'))
track('out', '/OUT', B, ('R18', '2'), [], ('J5', 'T'))
track('spare', '/SPARE', B, ('U3', '6'), [], ('U3', '7'))

# ---- power: J10 -> D1/D2 -> rails ------------------------------------------------------------
track('p12in', '/+12V_IN', B, ('J10', '9'), [], ('J10', '10'), PWR)
track('p12d', '/+12V_IN', B, ('J10', '10'), [], ('D1', '2'), PWR)
track('p12c', '+12V', B, ('D1', '1'), [], ('C1', '1'), PWR)
via('p12a', '+12V', 24.6, 104.35)
via('p12b', '+12V', 13.4, 102.2)
via('p12l', '+12V', RAIL_P, 103.05)
track('p12v', '+12V', B, ('C1', '1'), [], 'p12a', PWR)
track('p12f', '+12V', F, 'p12a', [(23.3, 103.05), (13.4, 103.05)], 'p12b', PWR)
track('p12g', '+12V', F, 'p12b', [(12.55, 103.05)], 'p12l', PWR)
track('p12u', '+12V', B, 'p12b', [], ('C7', '1'), PWR)
track('p12p', '+12V', B, ('C7', '1'), [], ('U3', '8'), PWR)
track('p12e', '+12V', B, 'p12l', [], 'plU2', PWR)
track('p12e2', '+12V', B, 'plU2', [], 'plU1', PWR)
track('m12in', '/-12V_IN', B, ('J10', '1'), [], ('J10', '2'), PWR)
track('m12d', '/-12V_IN', B, ('J10', '2'), [], ('D2', '1'), PWR)
track('m12c', '-12V', B, ('D2', '2'), [], ('C2', '2'), PWR)
via('m12a', '-12V', 26.0, 114.55)
via('m12b', '-12V', 17.5, 96.6)
track('m12v', '-12V', B, ('C2', '2'), [], 'm12a', PWR)
track('m12f', '-12V', F, 'm12a', [(26.0, 96.6)], 'm12b', PWR)
track('m12u', '-12V', B, 'm12b', [], ('C8', '2'), PWR)
track('m12p', '-12V', B, ('C8', '2'), [], ('U3', '4'), PWR)
track('m12e', '-12V', B, 'm12a', [(26.0, 118.4), (RAIL_M, 118.4)], 'mlU2', PWR)
track('m12e2', '-12V', B, 'mlU2', [], 'mlU1', PWR)

# ---- GND: local returns to vias, stitching -------------------------------------------------
for name, pad, xy in [('u3p3', ('U3', '3'), (14.9, 93.3)), ('u3p5', ('U3', '5'), (16.9, 100.9)),
                      ('c7', ('C7', '2'), (12.095, 104.7)), ('c8', ('C8', '1'), (20.1, 95.0)),
                      ('c1', ('C1', '2'), (27.6, 101.2)), ('c2', ('C2', '1'), (27.6, 111.3))]:
    via('g' + name, 'GND', *xy)
    track('g' + name, 'GND', B, pad, [], 'g' + name)
STITCH = []
for n, y in ROWY.items():
    STITCH += [(12.8, y - 3.0), (12.8, y + 5.0), (26.2, y + 5.0), (4.6, y), (6.5, y + 12.5)]
STITCH += [(12.0, 110.0), (4.6, 114.0), (13.5, 117.0), (28.5, 109.5), (22.0, 100.0), (27.0, 93.5),
           (4.6, 11.5), (27.0, 11.5)]
for i, (x, y) in enumerate(STITCH):
    via(f'stitch{i}', 'GND', x, y)


def zone(name, net, layer, poly):
    ops.append({'op': 'add_zone', 'uuid': uid('zone/' + name), 'net': net, 'layer': layer,
                'polygon': [p(x, y) for x, y in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.2})


X0, Y0, X1, Y1 = GEO['main_pcb']['outline_mm']
for layer in (B, F):
    zone('gnd/' + layer, 'GND', layer, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])

if __name__ == '__main__':
    json.dump({'schema_version': 1, 'operations': ops}, sys.stdout, indent=1)
    sys.stdout.write('\n')
