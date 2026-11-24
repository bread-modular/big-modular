"""Check the top clip against the routed carrier and the FR4 panel (KiCad Python).

Run from modules/motion:  python3 -B panels/top-clip/check_top_clip.py

Carrier: no F courtyard under the clip where it stands over the F face (shoulder strip
and boss), no B courtyard under the nose, no copper (tracks, vias, pads, zone fills) where
the shoulder and the nose touch the board. Panel: the screw hole is there, and the screw
head clears every other hole, the silk legend, the panel edge and the Ø16 knob skirts.
Prints a JSON report; exits non-zero on a failure.
"""
import json
import math
import sys
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[2]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
CLIP = GEO['top_clip']
OX, OY = GEO['kicad_origin_mm']      # carrier and panel boards share this origin
KNOB_D = 16.0      # widest printed knob (mechanical/knobs wide/)
EPS = 1e-6


def mm(v):
    return pcbnew.ToMM(v)


def rect_poly(x0, y0, x1, y1):
    p = pcbnew.SHAPE_POLY_SET()
    p.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        p.Append(pcbnew.FromMM(x + OX), pcbnew.FromMM(y + OY))
    return p


def overlap_area(a, b):
    c = pcbnew.SHAPE_POLY_SET(a)
    c.BooleanIntersection(b)
    return sum(c.Outline(i).Area() for i in range(c.OutlineCount())) / 1e12


def rect_gap(poly, r):
    """Gap (mm) between a polygon's bounding box and a rectangle (x0, y0, x1, y1), panel frame."""
    bb = poly.BBox()
    x0, y0 = mm(bb.GetX()) - OX, mm(bb.GetY()) - OY
    x1, y1 = mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY
    dx = max(r[0] - x1, x0 - r[2], 0.0)
    dy = max(r[1] - y1, y0 - r[3], 0.0)
    return math.hypot(dx, dy) if dx and dy else max(dx, dy)


def check_carrier(fails):
    board = pcbnew.LoadBoard(str(MODULE / 'hardware/motion.kicad_pcb'))
    edge = GEO['main_pcb']['outline_mm'][1]
    x0, x1 = CLIP['X_mm']
    boss = CLIP['boss']
    f_zones = {'shoulder': (x0, edge, x1, CLIP['shoulder_inner_Y']),
               'boss': (boss['X'][0], edge, boss['X'][1], boss['Y'][1])}
    b_zones = {'nose': (x0, edge, x1, CLIP['nose_inner_Y'])}
    gaps = {}
    for fp in board.GetFootprints():
        for layer, zones in ((pcbnew.F_CrtYd, f_zones), (pcbnew.B_CrtYd, b_zones)):
            yard = fp.GetCourtyard(layer)
            if not yard.OutlineCount():
                continue
            for name, r in zones.items():
                key = f'{name}:{fp.GetReference()}'
                if overlap_area(yard, rect_poly(*r)) > EPS:
                    fails.append(f'courtyard {key} under the clip')
                gaps[key] = round(rect_gap(yard, r), 3)
    closest = dict(sorted(gaps.items(), key=lambda kv: kv[1])[:4])
    copper = {}
    contact = {pcbnew.F_Cu: rect_poly(x0, edge, x1, CLIP['shoulder_inner_Y']),
               pcbnew.B_Cu: rect_poly(x0, edge, x1, CLIP['nose_inner_Y'])}
    for layer, zone_rect in contact.items():
        hits = []
        for item in list(board.GetTracks()) + [p for fp in board.GetFootprints() for p in fp.Pads()]:
            if not item.IsOnLayer(layer):
                continue
            poly = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
            if overlap_area(poly, zone_rect) > EPS:
                hits.append(item.GetClass())
        for zone in board.Zones():
            if zone.IsOnLayer(layer) and zone.HasFilledPolysForLayer(layer):
                if overlap_area(zone.GetFilledPolysList(layer), zone_rect) > EPS:
                    hits.append(f'zone {zone.GetNetname()}')
        copper[board.GetLayerName(layer)] = hits
        if hits:
            fails.append(f'copper under the clip contact on {board.GetLayerName(layer)}: {hits}')
    return {'closest_courtyards_mm': closest, 'copper_in_contact_strips': copper}


def check_panel(fails):
    board = pcbnew.LoadBoard(str(MODULE / 'panels/front-pcb/motion-panel.kicad_pcb'))
    sx, sy = CLIP['screw_XY']
    head_r = CLIP['screw_head_D'] / 2
    hole_d = GEO['panel_hole_diameters_mm']['clip_screw']
    found, hole_gaps = False, {}
    for fp in board.GetFootprints():
        x, y = mm(fp.GetPosition().x) - OX, mm(fp.GetPosition().y) - OY
        d = mm(next(iter(fp.Pads())).GetDrillSize().x)
        dist = math.hypot(x - sx, y - sy)
        if dist < EPS:
            found = abs(d - hole_d) < EPS
            continue
        hole_gaps[fp.GetReference()] = round(dist - head_r - d / 2, 3)
    if not found:
        fails.append('no Ø3.2 clip screw hole in the FR4 panel')
    if min(hole_gaps.values()) < 1.0:
        fails.append(f'screw head too close to a panel hole: {hole_gaps}')
    text_gaps = {}
    for item in board.GetDrawings():
        if item.GetClass() != 'PCB_TEXT':
            continue
        bb = item.GetBoundingBox()
        r = (mm(bb.GetX()) - OX, mm(bb.GetY()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY)
        dx = max(r[0] - sx, sx - r[2], 0.0)
        dy = max(r[1] - sy, sy - r[3], 0.0)
        text_gaps[item.GetText()] = round(math.hypot(dx, dy) - head_r, 3)
    if min(text_gaps.values()) < 0.3:
        fails.append(f'screw head on the silk legend: {text_gaps}')
    width = GEO['panel_mm'][0]
    edge_gap = min(sx, width - sx, sy) - head_r
    rail_gap = min(math.hypot(sx - x, sy - y) - head_r - d / 2 for x, y, d in GEO['rail_holes_mm'])
    knob_gap = min(math.hypot(sx - p['shaft_XY'][0], sy - p['shaft_XY'][1]) - head_r - KNOB_D / 2
                   for p in GEO['pots'])
    if edge_gap < 1.0 or knob_gap < 1.0:
        fails.append(f'screw head: edge {edge_gap:.2f} mm, knob skirt {knob_gap:.2f} mm')
    return {'screw_hole_found': found,
            'head_to_nearest_hole_mm': min(hole_gaps.items(), key=lambda kv: kv[1]),
            'head_to_nearest_text_mm': min(text_gaps.items(), key=lambda kv: kv[1]),
            'head_to_panel_edge_mm': round(edge_gap, 3),
            'head_to_rail_hole_mm': round(rail_gap, 3),
            'head_to_knob_skirt_mm': round(knob_gap, 3)}


def main():
    fails = []
    report = {'carrier': check_carrier(fails), 'panel': check_panel(fails), 'fails': fails}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(1 if fails else 0)


main()
