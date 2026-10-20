#!/usr/bin/env python3
"""Emit the explicit routing plan (shared `pcb plan/apply` ops v1) for the 16bit R1 carrier (routed, final).

The copper is frozen in tools/route_r1.json (KiCad-frame mm): polylines that start and end on
pad centres, vias or an exact point on an earlier track (tee), plus the vias. Nothing is routed
here; this only turns that data into ops. Layer plan:
  F.Cu / B.Cu  signals 0.2 mm, rails 0.4 mm (+12V, -12V, +12V_F, -12V_F, +5V, +3V3, +1V1)
  In1.Cu       solid GND plane, no tracks
  In2.Cu       +3V3 plane; a few signals cross it
  vias         through, as frozen (0.5/0.3 mm, the board default)

A plan holds at most 256 operations, so the ops are split into stages of whole nets (zones
first), applied in order, each on the previous stage's candidate:

  python3 -B tools/route_plan.py research/route/ops      (writes ops-1.json, ops-2.json, ...)
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEO = json.loads((HERE.parent / 'docs/geometry.json').read_text())
ROUTE = json.loads((HERE / 'route_r1.json').read_text())
OX, OY = GEO['kicad_origin_mm']
STAGE = 256
PLANES = (('In1.Cu', 'GND'), ('In2.Cu', '+3V3'))

ops = []
segments = []                       # (uuid, a, b, net, layer) of every emitted straight piece, for tees


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/16bit/route-r1/' + key))


def child(parent, i):                # same derivation as the shared apply worker
    return parent if i == 0 else str(uuid.uuid5(uuid.UUID(parent), str(i)))


def on_segment(pt, a, b):
    nm = [round(v * 1e6) for v in (*pt, *a, *b)]
    (x, y), (ax, ay), (bx, by) = nm[0:2], nm[2:4], nm[4:6]
    return ((bx - ax) * (y - ay) == (by - ay) * (x - ax)
            and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by))


X0, Y0, X1, Y1 = GEO['main_pcb']['outline_mm']
for layer, net in PLANES:
    ops.append({'op': 'add_zone', 'uuid': uid(f'zone/{net}/{layer}'), 'net': net, 'layer': layer,
                'polygon': [[round(OX + x, 4), round(OY + y, 4)] for x, y in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1))],
                'clearance_mm': 0.25, 'min_thickness_mm': 0.2, 'pad_connection': 'thermal'})

by_net = {}                         # net -> its vias then its polylines; a stage holds whole nets
for i, v in enumerate(ROUTE['vias']):
    by_net.setdefault(v['net'], []).append({'op': 'add_via', 'uuid': uid(f'via/{i}'), 'net': v['net'], 'at': v['at'],
                                            'diameter_mm': v['diameter_mm'], 'drill_mm': v['drill_mm']})


def end(e, net, layer):
    if 'pad' in e:
        return {'pad': {'ref': e['pad'][0], 'number': e['pad'][1]}}, None
    if 'pad_uuid' in e:              # pad number used more than once in its footprint (U1 pad 61)
        return {'uuid': e['pad_uuid']}, None
    if 'via' in e:
        return {'uuid': uid(f"via/{e['via']}")}, ROUTE['vias'][e['via']]['at']
    # A tee at a polyline vertex lies on two pieces; either one is exact.
    hits = [s for s in segments if s[3:] == (net, layer) and on_segment(e['tee'], s[1], s[2])]
    assert hits, ('tee needs an earlier track', e, net, layer)
    return {'track': hits[0][0], 'at': e['tee']}, e['tee']


for i, t in enumerate(ROUTE['tracks']):
    key = uid(f'trk/{i}')
    start, a = end(t['start'], t['net'], t['layer'])
    stop, b = end(t['end'], t['net'], t['layer'])
    by_net.setdefault(t['net'], []).append({'op': 'add_polyline', 'uuid': key, 'net': t['net'], 'layer': t['layer'],
                                              'start': start, 'waypoints': t['waypoints'], 'end': stop,
                                              'width_mm': t['width_mm']})
    # Pad centres are only known to the worker, so pieces touching a pad are not tee targets.
    pts = ([a] if a else []) + t['waypoints'] + ([b] if b else [])
    first = 0 if a else 1
    for j in range(len(pts) - 1):
        segments.append((child(key, j + first), pts[j], pts[j + 1], t['net'], t['layer']))

if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    # Whole nets per stage: a via whose tracks come in a later stage would be a dangling-via
    # finding in between, which the shared apply rejects. Zones go first.
    stages = [list(ops)]
    for net in sorted(by_net):
        group = by_net[net]
        assert len(group) <= STAGE, ('net needs more than one stage', net, len(group))
        if len(stages[-1]) + len(group) > STAGE:
            stages.append([])
        stages[-1].extend(group)
    for n, chunk in enumerate(stages, 1):
        (out / f'ops-{n}.json').write_text(json.dumps({'schema_version': 1, 'operations': chunk}, indent=1) + '\n')
    print(f'{sum(map(len, stages))} operations in {len(stages)} stages -> {out}')
