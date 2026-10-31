"""Independent M1 mechanical-preview checks on the NATIVE boards (read-only, pcbnew 10).

Run from the repository root after tools/build_layout.py:
  python3 -B modules/usb-power-45w/tools/check_mechanics.py --out modules/usb-power-45w/docs/mechanical-preview/verification.json

Checks: exact ref / pad / net parity and field parity against a fresh native netlist,
library pad-map identity, zero copper, placed-vs-parked inventory, courtyard and copper
distances to Edge.Cuts, placed courtyard overlaps, 2 mm hand-solder clearance, panel-to-
carrier registration (USB/LED/RESET axes, bracket holes), panel outline/holes and an area
budget. Findings are reported, never waived. Not a substitute for native ERC/DRC.
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from mechanics45 import carrier_outline  # noqa: E402

GEO = json.loads((MODULE / 'docs/mechanical-geometry.json').read_text())
HW = MODULE / 'hardware'
PANEL = MODULE / 'panels/front-pcb/usb-power-45w-panel.kicad_pcb'
mm = pcbnew.ToMM
HAND_THT = ['J2', 'J3'] + [l['reference'] for l in GEO['LEDs']]
EDGE_MOUNT = ['J1', 'SW1'] + [l['reference'] for l in GEO['LEDs']]


def yz(v):
    return mm(v.x) - 35.75, 104.275 - mm(v.y)


def netlist():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / 'usb-power-45w.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
        return ET.parse(out).getroot()


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx * dx + dy * dy < 1e-18:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def poly_edges(points):
    return list(zip(points, points[1:] + points[:1]))


def inside(p, poly):
    x, y = p
    c = False
    for (x0, y0), (x1, y1) in poly_edges(poly):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def box_edge_distance(box, outline):
    """Signed: min distance from a box's corners/edges to the outline; negative if outside/crossing."""
    l, t, r, b = box
    corners = [(l, t), (r, t), (r, b), (l, b)]
    pts = corners + [((l + r) / 2, t), ((l + r) / 2, b), (l, (t + b) / 2), (r, (t + b) / 2)]
    d = min(seg_dist(p, a, c) for p in pts for a, c in poly_edges(outline))
    # outline vertices inside the box also reduce clearance (re-entrant cutbacks)
    for v in outline:
        if l <= v[0] <= r and t <= v[1] <= b:
            return -0.0
    if not all(inside(p, outline) for p in corners):
        return -d
    # nearest edge distance from the box boundary: sample densely
    best = d
    for i in range(41):
        f = i / 40
        for p in [(l + f * (r - l), t), (l + f * (r - l), b), (l, t + f * (b - t)), (r, t + f * (b - t))]:
            best = min(best, min(seg_dist(p, a, c) for a, c in poly_edges(outline)))
    return best


def courtyard_box(fp):
    boxes = [g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_CrtYd]
    return (min(mm(b.GetLeft()) for b in boxes), min(mm(b.GetTop()) for b in boxes),
            max(mm(b.GetRight()) for b in boxes), max(mm(b.GetBottom()) for b in boxes))


def pad_poly(pad):
    poly = pad.GetEffectivePolygon(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
    pts = []
    for oi in range(poly.OutlineCount()):
        o = poly.Outline(oi)
        pts += [(mm(o.CPoint(i).x), mm(o.CPoint(i).y)) for i in range(o.PointCount())]
    return pts


def poly_gap(a, b):
    if not a or not b:
        return math.inf
    return min(min(seg_dist(p, *e) for e in poly_edges(b) for p in a),
               min(seg_dist(p, *e) for e in poly_edges(a) for p in b))


def check_carrier(rep, problems):
    board = pcbnew.LoadBoard(str(HW / 'usb-power-45w.kicad_pcb'))
    root = netlist()
    rep['copper'] = {'tracks_and_vias': len(board.GetTracks()), 'zones': len(list(board.Zones())),
                     'copper_layers': board.GetCopperLayerCount()}
    if len(board.GetTracks()) or len(list(board.Zones())):
        problems.append('carrier has copper/zones')
    unesc = lambda s: s.replace('{slash}', '/')
    want = {}
    for n in root.find('nets'):
        for d in n.findall('node'):
            want[(d.get('ref'), d.get('pin'))] = n.get('name')
    got, extra_pads = {}, []
    fps = {fp.GetReference(): fp for fp in board.GetFootprints() if fp.GetReference()}
    for ref, fp in fps.items():
        for p in fp.Pads():
            if p.GetNumber() == '':
                if p.GetNetname():
                    extra_pads.append((ref, 'unnumbered'))
                continue
            k = (ref, p.GetNumber())
            nm = unesc(p.GetNetname())
            if k in got and got[k] != nm:
                extra_pads.append(k)
            got[k] = nm
    comps = {c.get('ref'): c for c in root.find('components')}
    field_bad = []
    for ref, c in comps.items():
        fp = fps.get(ref)
        if fp is None:
            continue
        if fp.GetValue() != c.findtext('value') or fp.GetFPIDAsString() != c.findtext('footprint'):
            field_bad.append((ref, 'value/footprint'))
        for f in c.find('fields'):
            name = f.get('name')
            if name == 'Footprint':
                continue
            if not fp.HasField(name) or fp.GetFieldText(name) != (f.text or ''):
                field_bad.append((ref, name))
        path = c.find('sheetpath').get('tstamps') + c.findtext('tstamps').split()[0]
        if fp.GetPath().AsString() != path:
            field_bad.append((ref, 'symbol path'))
    rep['parity'] = {'schematic_refs': len(comps), 'pcb_refs': len(fps),
                     'missing_refs': sorted(set(comps) - set(fps)), 'extra_refs': sorted(set(fps) - set(comps)),
                     'pad_net_mismatches': sorted([list(k) for k in want if got.get(k) != want[k]]),
                     'pcb_pads_not_in_netlist': sorted([list(k) for k in got if k not in want]),
                     'conflicting_duplicate_pads': extra_pads, 'field_mismatches': field_bad,
                     'net_escape_note': "Net-(U4-RT/SYNC) is stored natively as Net-(U4-RT{slash}SYNC); "
                                        "compared unescaped here, native DRC parity requires the escaped form"}
    if any(rep['parity'][k] for k in ['missing_refs', 'extra_refs', 'pad_net_mismatches', 'pcb_pads_not_in_netlist',
                                      'conflicting_duplicate_pads', 'field_mismatches']):
        problems.append('carrier parity mismatch')
    # Library pad maps unchanged (number, type, local position, size, drill).
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    lib_bad = []
    cache = {}
    for ref, fp in fps.items():
        name = fp.GetFPID().GetLibItemName().wx_str()
        if name not in cache:
            lfp = io.FootprintLoad(str(HW / 'USBPOWER45.pretty'), name)
            cache[name] = sorted((p.GetNumber(), p.GetAttribute(), round(mm(p.GetFPRelativePosition().x), 4),
                                  round(mm(p.GetFPRelativePosition().y), 4), round(mm(p.GetSizeX()), 4),
                                  round(mm(p.GetSizeY()), 4), round(mm(p.GetDrillSizeX()), 4)) for p in lfp.Pads())
        mine = sorted((p.GetNumber(), p.GetAttribute(), round(mm(p.GetFPRelativePosition().x), 4),
                       round(mm(p.GetFPRelativePosition().y), 4), round(mm(p.GetSizeX()), 4),
                       round(mm(p.GetSizeY()), 4), round(mm(p.GetDrillSizeX()), 4)) for p in fp.Pads())
        if mine != cache[name]:
            lib_bad.append(ref)
    rep['library_pad_maps_identical'] = not lib_bad
    if lib_bad:
        problems.append(f'pad maps differ from library: {lib_bad}')
    # Outline vs contract.
    outline_native = [(y + 35.75, 104.275 - z) for y, z in carrier_outline(GEO)]
    edges = sorted(tuple(sorted([(round(mm(d.GetStart().x), 3), round(mm(d.GetStart().y), 3)),
                                 (round(mm(d.GetEnd().x), 3), round(mm(d.GetEnd().y), 3))]))
                   for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts)
    want_edges = sorted(tuple(sorted([(round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))]))
                        for a, b in poly_edges(outline_native))
    rep['outline_matches_contract'] = edges == want_edges
    if edges != want_edges:
        problems.append('carrier outline differs from contract')
    holes = sorted((round(yz(fp.GetPosition())[0], 3), round(yz(fp.GetPosition())[1], 3),
                    round(mm(next(iter(fp.Pads())).GetDrillSizeX()), 3))
                   for fp in board.GetFootprints() if not fp.GetReference())
    rep['carrier_m3_holes_YZd'] = holes
    if holes != sorted((y, z, GEO['carrier_hole_mm']) for y, z in GEO['carrier_holes_YZ_mm']):
        problems.append('carrier M3 holes differ from contract')
    # Placed vs parked.
    bb = (min(p[0] for p in outline_native), min(p[1] for p in outline_native),
          max(p[0] for p in outline_native), max(p[1] for p in outline_native))
    placed, parked, straddle = [], [], []
    for ref, fp in fps.items():
        l, t, r, b = courtyard_box(fp)
        if r < bb[0] or l > bb[2] or b < bb[1] or t > bb[3]:
            parked.append(ref)
        else:
            placed.append(ref)
    rep['inventory'] = {'placed_on_board': sorted(placed), 'parked_off_board_count': len(parked),
                        'parked_off_board_min_gap_to_board_mm': round(min(courtyard_box(fps[r])[0] for r in parked) - bb[2], 3),
                        'note': 'Parked parts are NOT placed. C5/C34/C35/C36 positions are PROVISIONAL height context.'}
    # Courtyard and copper distance to Edge.Cuts for placed parts.
    edge_rep, cu_rep = {}, {}
    for ref in sorted(placed):
        fp = fps[ref]
        edge_rep[ref] = round(box_edge_distance(courtyard_box(fp), outline_native), 3)
        dmin = math.inf
        for p in fp.Pads():
            if not (p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu)):
                continue
            pts = pad_poly(p)
            d = min(seg_dist(q, *e) for q in pts for e in poly_edges(outline_native))
            if not all(inside(q, outline_native) for q in pts):
                d = -d
            dmin = min(dmin, d)
        cu_rep[ref] = round(dmin, 3)
    lim = GEO['edge_keepout_mm']
    rep['courtyard_to_edge_mm'] = edge_rep
    rep['pad_copper_to_edge_mm'] = cu_rep
    rep['edge_rule_conflicts'] = {
        'courtyard_lt_1mm': {r: v for r, v in edge_rep.items() if v < lim - 1e-6},
        'copper_lt_1mm': {r: v for r, v in cu_rep.items() if v < lim - 1e-6},
        'note': 'J1/SW1/D8/D16-D18 are edge-mounted panel interfaces copied from usb-power; their bodies '
                'intentionally overhang the front edge into the panel. NOT waived: needs a user decision.'}
    nonedge = {r: v for r, v in edge_rep.items() if v < lim - 1e-6 and r not in EDGE_MOUNT}
    nonedge.update({r: v for r, v in cu_rep.items() if v < lim - 1e-6 and r not in EDGE_MOUNT})
    if nonedge:
        problems.append(f'non-edge-mount part within 1 mm of the edge: {nonedge}')
    if rep['edge_rule_conflicts']['courtyard_lt_1mm'] or rep['edge_rule_conflicts']['copper_lt_1mm']:
        problems.append('1 mm edge rule conflict for edge-mounted panel parts (legacy concept): user decision')
    # Placed courtyard overlaps.
    ov = []
    pl = sorted(placed)
    for i, a in enumerate(pl):
        for b2 in pl[i + 1:]:
            A, B = courtyard_box(fps[a]), courtyard_box(fps[b2])
            if min(A[2], B[2]) > max(A[0], B[0]) and min(A[3], B[3]) > max(A[1], B[1]):
                ov.append([a, b2])
    rep['placed_courtyard_bbox_overlaps'] = ov
    if ov:
        problems.append(f'placed courtyard overlaps: {ov}')
    # 2 mm hand-solder clearance: placed SMD pads vs hand-soldered THT pads.
    hs = {}
    for t in HAND_THT:
        tht = [pad_poly(p) for p in fps[t].Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
        best = (math.inf, None)
        for r in placed:
            if r == t:
                continue
            for p in fps[r].Pads():
                if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or not p.IsOnLayer(pcbnew.F_Cu):
                    continue
                g = min(poly_gap(pad_poly(p), q) for q in tht)
                if g < best[0]:
                    best = (g, f'{r}.{p.GetNumber()}')
        hs[t] = {'closest_smd_pad': best[1], 'gap_mm': None if best[1] is None else round(best[0], 3)}
    rep['hand_solder_2mm'] = hs
    bad = {k: v for k, v in hs.items() if v['gap_mm'] is not None and v['gap_mm'] < GEO['hand_solder_clearance_mm']}
    if bad:
        problems.append(f'hand-solder clearance < 2 mm: {bad}')
    # Panel registration of carrier-mounted interfaces.
    reg = {}
    fcu = GEO['carrier_X_mm'][1]
    for l in GEO['LEDs']:
        pads = {p.GetNumber(): yz(p.GetPosition()) for p in fps[l['reference']].Pads()}
        axis_y = (pads['1'][0] + pads['2'][0]) / 2
        hx, hy, d = l['panel_XY_diameter_mm']
        reg[l['reference']] = {'axis_Y_minus_hole_Y': round(axis_y - hy, 4),
                               'axis_X_minus_hole_X': round(fcu + GEO['LED']['axis_above_PCB_mm'] - hx, 4),
                               'radial_clearance_body_mm': round((d - GEO['LED']['max_body_diameter_mm']) / 2, 3)}
    pegs = [yz(p.GetPosition()) for p in fps['SW1'].Pads() if p.GetNumber() == '']
    sx, sy, sd = GEO['reset_XY_diameter_mm']
    reg['SW1'] = {'peg_mid_Y_minus_hole_Y': round((pegs[0][0] + pegs[1][0]) / 2 - sy, 4),
                  'peg_Z': round(pegs[0][1], 3),
                  'actuator_axis_X_minus_hole_X': round(fcu + GEO['switch']['actuator_axis_height_mm'] - sx, 4),
                  'radial_clearance_actuator_mm': round((sd - GEO['switch']['actuator_diameter_mm']) / 2, 3)}
    lugs = [yz(p.GetPosition()) for p in fps['J1'].Pads() if p.GetNumber() == 'S1']
    ax, ay, aw, ah, ar = GEO['aperture_XYWHR_mm']
    jy = (min(v[0] for v in lugs) + max(v[0] for v in lugs)) / 2
    w, d_, h = GEO['USB']['body_width_depth_height_mm']
    reg['J1'] = {'body_centre_Y_minus_aperture_centre_Y': round(jy - (ay + ah / 2), 4),
                 'body_axis_X_minus_aperture_centre_X': round(fcu + h / 2 - (ax + aw / 2), 4),
                 'aperture_minus_shell_each_side_Y_mm': round((ah - w) / 2, 3),
                 'aperture_minus_shell_each_side_X_mm': round((aw - h) / 2, 3),
                 'note': 'copied unchanged: the old aperture is intentionally asymmetric about the X5.73 shell axis '
                         '(usb-power docs/usb-fit.json conservative shell X3.68..7.93, min corner margin 0.233); '
                         'that acceptance budget is inherited, not re-qualified here'}
    reg['brackets'] = {'carrier_hole_Y_equals_panel_hole_Y': [h[0] for h in GEO['carrier_holes_YZ_mm']]
                       == [h[1] for h in GEO['panel_bracket_holes_mm']],
                       'carrier_side_hole_Z_equals_bracket_side_hole_Z': all(h[1] == GEO['brackets']['side_hole_Z_mm']
                                                                            for h in GEO['carrier_holes_YZ_mm'])}
    rep['panel_registration'] = reg
    worst = max(abs(v) for k, r in reg.items() if k != 'brackets' for kk, v in r.items()
                if isinstance(v, float) and ('minus' in kk) and 'aperture_minus' not in kk
                and kk != 'body_axis_X_minus_aperture_centre_X')
    if worst > 1e-3 or not all(reg['brackets'].values()):
        problems.append('panel/carrier registration mismatch')
    # Area budget: usable board area (outline minus 1 mm keep-out) vs component courtyards.
    y0, y1 = GEO['carrier_Y_mm']
    z0, z1 = GEO['carrier_Z_mm']
    gross = (y1 - y0) * (z1 - z0) - sum((b - a) * (c - z0) for a, b, c in GEO['carrier_bracket_reliefs_YZ_mm'])
    inner = (y1 - y0 - 2) * (z1 - z0 - 2) - sum((b - a + 2) * (c - z0) for a, b, c in GEO['carrier_bracket_reliefs_YZ_mm'])
    def area(r):
        l, t, rr, b = courtyard_box(fps[r])
        return (rr - l) * (b - t)
    reserved = {
        'placed_courtyards_on_board': round(sum(area(r) for r in placed if r not in EDGE_MOUNT), 1),
        'front_cluster_strip_Y28..72_Z2..9.3': round((72.1 - 28.0) * (9.3 - 2.0), 1),
        'M3_nut_driver_keepouts_2x(8x9)': 2 * 8 * 9.0}
    smd = sum(area(r) for r in parked)
    free = inner - sum(reserved.values()) + reserved['placed_courtyards_on_board'] * 0  # cans are SMD: counted below
    cans = [c['reference'] for c in GEO['cans']['parts']]
    smd_total = smd + sum(area(r) for r in cans)
    usable = inner - reserved['front_cluster_strip_Y28..72_Z2..9.3'] - reserved['M3_nut_driver_keepouts_2x(8x9)'] \
        - sum(area(r) for r in ('J2', 'J3'))
    # B face (X0.5..2.5 envelope, <= 2.0 mm parts) as a planning alternative: minus bracket-web contact
    # (10 x 10 mm each, plus 1 mm), THT pad rows of J1/LEDs/J2/J3 (+1 mm) and the 1 mm keep-out.
    tht_b = 0.0
    for r in EDGE_MOUNT + ['J2', 'J3']:
        pts = [q for p in fps[r].Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for q in pad_poly(p)]
        if pts:
            tht_b += (max(q[0] for q in pts) - min(q[0] for q in pts) + 2) * (max(q[1] for q in pts) - min(q[1] for q in pts) + 2)
    web_b = 2 * 11.0 * (20.0 + 1 - 10.0)
    b_usable = inner - web_b - tht_b
    rep['area_budget_mm2'] = {
        'B_side_alternative_usable_low_profile': round(b_usable, 1),
        'B_side_excluded': {'bracket_web_contact': web_b, 'tht_pad_rows': round(tht_b, 1)},
        'utilisation_if_F_plus_B_low_profile': None,
        'gross_outline': round(gross, 1), 'inside_1mm_keepout': round(inner, 1),
        'reserved': reserved, 'J2_J3_courtyards': round(sum(area(r) for r in ('J2', 'J3')), 1),
        'usable_for_smd_single_sided': round(usable, 1),
        'smd_courtyard_sum_incl_cans': round(smd_total, 1),
        'courtyard_utilisation': round(smd_total / usable, 3),
        'courtyard_utilisation_F_plus_B': round(smd_total / (usable + b_usable), 3),
        'note': 'Courtyard bbox sum, single-sided F placement as the old module; a planning indicator, '
                'not a placement result.'}
    rep['area_budget_mm2'].pop('utilisation_if_F_plus_B_low_profile')
    tall = ('L_SLO1040', 'D_SMA', 'D_SMB', 'D_SMC', 'TO-252', 'SO-4_', 'CP_Elec')
    f_only = [r for r in parked + cans if any(k in fps[r].GetFPIDAsString() for k in tall)]
    fa = sum(area(r) for r in f_only)
    rep['area_budget_mm2']['F_only_parts_over_2mm'] = {
        'refs': sorted(f_only), 'courtyard_sum': round(fa, 1), 'share_of_F_usable': round(fa / usable, 3),
        'low_profile_remainder': round(smd_total - fa, 1),
        'basis': 'heights > 2.0 mm (SLO1040 4.0, SMA/SMB/SMC 2.3-2.6, TO-252 2.4, LTV-354T ~2.2, cans 8.0) stay on F'}
    # Non-blocking planning note (not a problem): bbox sum, no union, cans double-counted.
    rep['area_budget_mm2']['status'] = 'NON-BLOCKING PLANNING ESTIMATE'
    rep['area_budget_mm2']['limitations'] = (
        'Courtyard bounding boxes are summed, not unioned; cans are counted in the required sum and also '
        'fall in reserved strips; reserved strips/keep-outs are coarse rectangles. Neither proves fit nor '
        'failure and does not mandate a redesign. B-side placement is a later option only; double-sided '
        'assembly is not authorized.')
    del free
    return board


def check_panel(rep, problems):
    b = pcbnew.LoadBoard(str(PANEL))
    ox, oy = GEO['native_panel_origin_mm']
    edges = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    xs = [mm(v.x) for d in edges for v in (d.GetStart(), d.GetEnd())]
    ys = [mm(v.y) for d in edges for v in (d.GetStart(), d.GetEnd())]
    size = (round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3))
    holes = sorted((round(mm(fp.GetPosition().x) - ox, 3), round(mm(fp.GetPosition().y) - oy, 3),
                    round(mm(next(iter(fp.Pads())).GetDrillSizeX()), 3)) for fp in b.GetFootprints())
    want = sorted(tuple(h) for h in GEO['rail_holes_mm'] + GEO['panel_bracket_holes_mm']
                  + [l['panel_XY_diameter_mm'] for l in GEO['LEDs']] + [GEO['reset_XY_diameter_mm']])
    arcs = [d for d in edges if d.GetShape() == pcbnew.SHAPE_T_ARC]
    ax = [mm(v.x) - ox for d in edges if d.GetShape() != pcbnew.SHAPE_T_RECT for v in (d.GetStart(), d.GetEnd())]
    ay = [mm(v.y) - oy for d in edges if d.GetShape() != pcbnew.SHAPE_T_RECT for v in (d.GetStart(), d.GetEnd())]
    ap = (round(min(ax), 3), round(min(ay), 3), round(max(ax) - min(ax), 3), round(max(ay) - min(ay), 3),
          round(mm(arcs[0].GetRadius()), 3) if arcs else None)
    pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
    rep['panel'] = {'size_mm': size, 'thickness_mm': mm(b.GetDesignSettings().GetBoardThickness()),
                    'holes_XYd': holes, 'holes_match_contract': holes == want,
                    'aperture_XYWHR': ap, 'aperture_matches_contract': list(ap) == GEO['aperture_XYWHR_mm'],
                    'all_pads_npth': all(p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH for p in pads),
                    'copper_items': len(b.GetTracks()) + len(list(b.Zones())),
                    'silk_labels': sorted(t.GetText() for t in b.GetDrawings()
                                          if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS)}
    if size != tuple(GEO['panel_mm'][:2]) or holes != want or list(ap) != GEO['aperture_XYWHR_mm']:
        problems.append('panel geometry differs from contract')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rep, problems = {}, []
    check_carrier(rep, problems)
    check_panel(rep, problems)
    Path(args.out).write_text(json.dumps({'report': rep, 'problems': problems}, indent=1) + '\n')
    print(json.dumps({'report': rep, 'problems': problems}, indent=1))


if __name__ == '__main__':
    main()
