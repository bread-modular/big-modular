#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the VCA-MIX R1 carrier.

The copper is frozen in tools/route_r1.json (KiCad-frame mm): TraceMaker's full-board route
of the P4 placement plus one hand cleanup, chained into polylines that start and end on pad
centres, vias or (three +12V tees) an exact point on an earlier track. Nothing is routed here;
this only turns that data into ops. Layer plan as routed:
  signals  0.25 mm, mostly B.Cu inside each channel row; F.Cu for crossings.
  rails    0.4 mm: +12V/-12V from J10 -> D501/D502 down the right side and the board centre,
           one tap per TL072 pin 8/4 with its 100n beside it.
  GND      poured on both layers (IMIX settings: solid pad connection, 0.25 mm clearance,
           0.2 mm minimum width); vias 0.6/0.3 mm.

  python3 -B tools/route_plan.py > research/route/plan.json   (then shared pcb plan/apply/promote)
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEO = json.loads((HERE.parent / 'docs/geometry.json').read_text())
ROUTE = json.loads((HERE / 'route_r1.json').read_text())
OX, OY = GEO['kicad_origin_mm']

ops = []
segments = []                       # (uuid, a, b) of every emitted straight piece, for tees


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/vca-mix/route-r1/' + key))


def child(parent, i):                # same derivation as the shared apply worker
    return parent if i == 0 else str(uuid.uuid5(uuid.UUID(parent), str(i)))


def on_segment(pt, a, b):
    nm = [round(v * 1e6) for v in (*pt, *a, *b)]
    (x, y), (ax, ay), (bx, by) = nm[0:2], nm[2:4], nm[4:6]
    return ((bx - ax) * (y - ay) == (by - ay) * (x - ax)
            and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by))


for i, v in enumerate(ROUTE['vias']):
    ops.append({'op': 'add_via', 'uuid': uid(f'via/{i}'), 'net': v['net'], 'at': v['at'],
                'diameter_mm': v['diameter_mm'], 'drill_mm': v['drill_mm']})


def end(e, net, layer):
    if 'pad' in e:
        return {'pad': {'ref': e['pad'][0], 'number': e['pad'][1]}}, None
    if 'via' in e:
        return {'uuid': uid(f"via/{e['via']}")}, ROUTE['vias'][e['via']]['at']
    hits = [s for s in segments if s[3:] == (net, layer) and on_segment(e['tee'], s[1], s[2])]
    assert len(hits) == 1, ('tee needs exactly one earlier track', e, net, layer)
    return {'track': hits[0][0], 'at': e['tee']}, e['tee']


for i, t in enumerate(ROUTE['tracks']):
    key = uid(f'trk/{i}')
    start, a = end(t['start'], t['net'], t['layer'])
    stop, b = end(t['end'], t['net'], t['layer'])
    ops.append({'op': 'add_polyline', 'uuid': key, 'net': t['net'], 'layer': t['layer'],
                'start': start, 'waypoints': t['waypoints'], 'end': stop, 'width_mm': t['width_mm']})
    # Pad centres are only known to the worker, so pieces touching a pad are not tee targets.
    pts = ([a] if a else []) + t['waypoints'] + ([b] if b else [])
    first = 0 if a else 1
    for j in range(len(pts) - 1):
        segments.append((child(key, j + first), pts[j], pts[j + 1], t['net'], t['layer']))

X0, Y0, X1, Y1 = GEO['main_pcb']['outline_mm']
for layer in ('B.Cu', 'F.Cu'):
    ops.append({'op': 'add_zone', 'uuid': uid('zone/gnd/' + layer), 'net': 'GND', 'layer': layer,
                'polygon': [[round(OX + x, 4), round(OY + y, 4)] for x, y in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1))],
                'clearance_mm': 0.25, 'min_thickness_mm': 0.2})

if __name__ == '__main__':
    json.dump({'schema_version': 1, 'operations': ops}, sys.stdout, indent=1)
    sys.stdout.write('\n')
