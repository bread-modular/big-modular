"""Independent placement record of the S8 single board (read-only, pcbnew).

  python3 -B tools/check_s8_board.py [--board hardware/single/usb-power-45w-single.kicad_pcb] [--out <json>]

DRC does not check these, so this does (root AGENTS.md placement rules + docs/s8-single/mechanical.json):

- every part placed on the board, on F (user: "Use single side"), nothing parked;
- courtyard overlaps between parts;
- courtyard to Edge.Cuts >= 1.0 mm (cutbacks included); the R1-approved panel overhangs J1/SW1/D8 are
  listed, not hidden;
- bracket M3: no courtyard inside the F-side nut + 8 mm driver circles; no THT tail under the B-side
  bracket webs (Y17..27 / Y101.5..111.5, Z1.6..20);
- 2 mm hand-solder clearance: every SMD pad >= 2.0 mm (copper edge to copper edge) from the THT pads of the
  hand-soldered parts J1 (shell lugs), D8, J2 and J3; SW1 (machine-placed SMD, R1 "extra margin") reported;
- J2/J3 pin 1 against the contract; board depth; courtyard fill;
- S8.4 local-loop contract (review M4): pad-centre distance from each listed IC pin to the nearest pad of its
  bypass capacitor / clamp on the same net, against the LOCAL_LOOPS limits (straight line, the review's metric);
- S9.2 routing contract: pre_routing_checklist (net classes, .kicad_dru, rule areas, S9.2b via policy and thermal
  fields, stack-up, test pads, placement) and post_routing_screen (the copper items DRC cannot express; PENDING while
  the board carries no copper beyond the S9.2b thermal fields).
Not a fit, routability or thermal proof; a short straight-line distance is not a routed loop.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
import mechanics_s8  # noqa: E402
import s92_contract  # noqa: E402
import s92_parts  # noqa: E402
from mechanics45 import carrier_xy  # noqa: E402

GEO = mechanics_s8.geometry()
APPROVED_OVERHANG = {'J1', 'SW1', 'D8'}          # R1 steps 1-2 (docs/r1-routing.md): panel-registered parts
HAND_SOLDERED = ('J1', 'D8', 'J2', 'J3')          # THT pads soldered by hand
REPORT_ONLY = ('SW1',)
mm = pcbnew.ToMM
# S8.4 local decoupling / protection-loop contract: (IC, pins, net, qualifying refs or prefix, value, limit mm, why).
# A qualifying part is any listed ref, or any ref with the prefix (and value, if given), with a pad on `net`.
# IC bypass at the supply pin (S8.4). S9.0: the U23 (+5V eFuse) and U3 (+5V converter) rows left with +5V; the U2
# rows follow the TPS552892-Q1 lands (VIN 7, VOUT 11, VCC 18).
LOCAL_LOOPS = [
    ('U20', ('3',), 'VPD', ('C65',), None, 4.5, 'U20 VCC (VPD) bypass'),
    ('U18', ('3',), 'VPD', ('C57',), None, 4.5, 'U18 VCC (VPD) bypass'),
    ('U9', ('8',), 'VPD', ('C46',), None, 4.5, 'LDO input'),
    ('U9', ('1',), 'V3V3', ('C47',), None, 4.5, 'LDO output'),
    ('U5', ('1', '2', '3', '6'), 'MAIN_IN', ('C2',), None, 4.5, 'main eFuse IN'),
    ('U1', ('1', '8'), 'VPD_U1', ('C1',), None, 4.5, 'CH224A VHV (R3 BASE block)'),
    ('U2', ('7',), 'VIN', ('C8',), None, 4.5, '+12V converter HF input cap'),          # S9.0: TPS552892 VIN land
    ('U2', ('11',), 'P12_VOUT', ('C81',), None, 4.5, '+12V converter HF output cap'),  # S9.0: VOUT land (TI 0.1 uF)
    ('U2', ('18',), None, ('C82',), None, 4.5, '+12V converter VCC (LDO) cap'),       # S9.0: net = the VCC pin's own
    ('C82', ('2',), 'GND', ('R113',), None, 3.0, 'sole AGND/PGND link: R113 PGND pad at the C82.2 PGND terminal'),
    ('U4', ('3',), 'VIN', 'C', '100n', 4.5, '-12V converter HF input cap'),
    ('U21', ('1',), 'REF_OV', ('C67',), None, 4.5, 'TLV431 stabilising cap'),
    *[(u, (p,), 'V3V3', 'C', '100n', 6.0, f'{u} logic bypass')
      for u, p in (('U10', '6'), ('U11', '6'), ('U12', '14'), ('U13', '14'), ('U14', '14'), ('U15', '5'))],
]


def local_loops(fps):
    """Measured LOCAL_LOOPS rows; a missing qualifying part counts as a violation."""
    def net(p):
        return p.GetNetname().split('/')[-1]
    rows = []
    for ic, pins, netname, who, value, limit, why in LOCAL_LOOPS:
        src = [p for p in fps[ic].Pads() if p.GetNumber() in pins]
        netname = netname or net(src[0])                    # None: the (local) net of the listed IC pin itself
        assert src and all(net(p) == netname for p in src), (ic, pins, netname)
        best = None
        for ref, fp in fps.items():
            if ref == ic or not (ref in who if isinstance(who, tuple) else
                                 (ref.startswith(who) and ref[len(who):].isdigit()
                                  and (value is None or fp.GetValue() == value))):
                continue
            for q in fp.Pads():
                if q.GetNumber() and net(q) == netname:
                    for p in src:
                        d = math.dist((mm(p.GetPosition().x), mm(p.GetPosition().y)),
                                      (mm(q.GetPosition().x), mm(q.GetPosition().y)))
                        if best is None or d < best[0]:
                            best = (d, f'{ic}.{p.GetNumber()}', f'{ref}.{q.GetNumber()}')
        rows.append({'from': best[1] if best else f'{ic}.{pins[0]}', 'to': best[2] if best else None, 'net': netname,
                     'distance_mm': round(best[0], 2) if best else None, 'limit_mm': limit, 'purpose': why,
                     'ok': best is not None and best[0] <= limit})
    return {'metric': 'pad-centre straight-line distance, same net (the metric of the S8.3 reviews)',
            'rows': rows, 'violations': [r for r in rows if not r['ok']]}


def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def poly_pts(sp):
    return [(mm(sp.Outline(i).CPoint(k).x), mm(sp.Outline(i).CPoint(k).y))
            for i in range(sp.OutlineCount()) for k in range(sp.Outline(i).PointCount())]


def poly_segs(sp):
    out = []
    for i in range(sp.OutlineCount()):
        o = sp.Outline(i)
        pts = [(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())]
        out += list(zip(pts, pts[1:] + pts[:1]))
    return out


def poly_dist(a, b):
    """Minimum distance between two polygon sets (0 if they touch/overlap)."""
    x = pcbnew.SHAPE_POLY_SET(a)
    x.BooleanIntersection(b)
    if x.Area() > 0:
        return 0.0
    sa, sb = poly_segs(a), poly_segs(b)
    return min(min(seg_dist(p, *s) for p in poly_pts(a) for s in sb), min(seg_dist(p, *s) for p in poly_pts(b) for s in sa))


def pad_poly(p):
    sp = pcbnew.SHAPE_POLY_SET()
    p.TransformShapeToPolygon(sp, pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, 0, pcbnew.FromMM(0.005),
                              pcbnew.ERROR_INSIDE)
    return sp


def check(board_path):
    b = pcbnew.LoadBoard(str(board_path))
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, True)
    segs = poly_segs(outline)
    bb = outline.BBox()
    fps = {fp.GetReference(): fp for fp in b.GetFootprints() if fp.GetReference()}
    placed, parked, on_back = {}, [], []
    for ref, fp in fps.items():
        if fp.GetLayer() != pcbnew.F_Cu:
            on_back.append(ref)
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if cy.OutlineCount() == 0:
            continue
        inter = pcbnew.SHAPE_POLY_SET(cy)
        inter.BooleanIntersection(outline)
        if inter.Area() == 0:
            parked.append(ref)
            continue
        outside = (cy.Area() - inter.Area()) / 1e12
        d = min(seg_dist(p, *s) for p in poly_pts(cy) for s in segs)
        placed[ref] = dict(courtyard_to_edge_mm=round(-d if outside > 0.01 else d, 3), overhang_mm2=round(outside, 2),
                           approved_overhang=ref in APPROVED_OVERHANG, polys=cy)
    refs = sorted(placed)
    overlaps = []
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if not placed[a]['polys'].BBox().Intersects(placed[c]['polys'].BBox()):
                continue
            x = pcbnew.SHAPE_POLY_SET(placed[a]['polys'])
            x.BooleanIntersection(placed[c]['polys'])
            if x.Area() > 1e6:      # > 0.001 mm2
                overlaps.append([a, c, round(x.Area() / 1e12, 3)])
    edge_bad = sorted(r for r, v in placed.items() if v['courtyard_to_edge_mm'] < 1.0 and not v['approved_overhang'])
    closest_edge = sorted(((v['courtyard_to_edge_mm'], r) for r, v in placed.items() if not v['approved_overhang']))[:6]
    # Bracket M3: F-side nut + driver circle, B-side web footprint
    br = GEO['brackets']
    r_drv = br['side_nut_driver_diameter_max_mm'] / 2
    driver = {}
    for y, z in GEO['carrier_holes_YZ_mm']:
        cx, cyy = carrier_xy(y, z)
        near = []
        for ref, v in placed.items():
            d = min(math.hypot(px - cx, py - cyy) for px, py in poly_pts(v['polys']))
            inside = v['polys'].Contains(pcbnew.VECTOR2I(pcbnew.FromMM(cx), pcbnew.FromMM(cyy)))
            dseg = min(seg_dist((cx, cyy), *s) for s in poly_segs(v['polys']))
            near.append((round(-1 if inside else dseg - r_drv, 3), ref))
        near.sort()
        driver[f'Y{y:g}'] = {'centre_native': [cx, cyy], 'radius_mm': r_drv, 'closest_courtyards_gap_mm': near[:4],
                             'violations': [r for g, r in near if g < 0]}
    webs = []
    for yc in br['Y_centres_mm']:
        x0, y0 = carrier_xy(yc - 5, br['outer_Z_mm'][1])
        x1, y1 = carrier_xy(yc + 5, br['front_foot_Z_mm'][0])
        webs.append((min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)))
    tails = []
    for ref, fp in fps.items():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                x, y = mm(p.GetPosition().x), mm(p.GetPosition().y)
                for w in webs:
                    if w[0] - 1 <= x <= w[1] + 1 and w[2] - 1 <= y <= w[3] + 1:
                        tails.append(f'{ref}.{p.GetNumber()}')
    # 2 mm hand-solder clearance
    tht = {r: [(p, pad_poly(p)) for p in fps[r].Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
           for r in HAND_SOLDERED + REPORT_ONLY if r in fps}
    if 'SW1' in tht:
        tht['SW1'] = [(p, pad_poly(p)) for p in fps['SW1'].Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    smd = [(ref, p, pad_poly(p)) for ref, fp in fps.items() for p in fp.Pads()
           if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and ref not in HAND_SOLDERED and ref not in REPORT_ONLY]
    hand = {}
    for r, pads in tht.items():
        best = []
        bx = pcbnew.BOX2I()
        for _, sp in pads:
            bx.Merge(sp.BBox())
        bx.Inflate(pcbnew.FromMM(6))
        for ref, p, sp in smd:
            if not bx.Intersects(sp.BBox()):
                continue
            d = min(poly_dist(sp, tp) for _, tp in pads)
            best.append((round(d, 3), f'{ref}.{p.GetNumber()}'))
        best.sort()
        hand[r] = {'closest_smd_pads_mm': best[:5], 'violations_lt_2mm': [x for x in best if x[0] < 2.0],
                   'rule': 'report only (SMD, machine-placed)' if r in REPORT_ONLY else 'must be >= 2.0 mm'}
    headers = {}
    for h in GEO['headers']:
        p1 = [p for p in fps[h['reference']].Pads() if p.GetNumber() == '1'][0].GetPosition()
        want = carrier_xy(*h['pin1_YZ_mm'])
        headers[h['reference']] = dict(pin1_native=[round(mm(p1.x), 3), round(mm(p1.y), 3)], contract=list(want),
                                       rot=fps[h['reference']].GetOrientationDegrees(),
                                       matches=abs(mm(p1.x) - want[0]) < 1e-3 and abs(mm(p1.y) - want[1]) < 1e-3)
    loops = local_loops(fps)
    net=lambda r,p: next(q.GetNetname().split('/')[-1] for q in fps[r].Pads() if q.GetNumber()==p)
    # S9.2 item 2: C82.2 is PGND, R113 the only AGND_U2 <-> PGND part, AGND_U2 exactly the contract members.
    agnd = sorted(f'{r}.{q.GetNumber()}' for r, fp in fps.items() for q in fp.Pads()
                  if q.GetNumber() and q.GetNetname().split('/')[-1] == 'AGND_U2')
    bridges = sorted(r for r, fp in fps.items() if r != 'U2'      # U2 itself has separate AGND (17) and PGND (9) pins
                     and {q.GetNetname().split('/')[-1] for q in fp.Pads() if q.GetNumber()} >= {'AGND_U2', 'GND'})
    ground_ok=(net('U2','17')==net('U2','5')==net('R113','1')=='AGND_U2'
               and net('U2','9')==net('C82','2')==net('R113','2')=='GND' and fps['R113'].GetValue()=='0'
               and agnd == sorted(s92_contract.GROUND['members_AGND_U2']) and bridges == ['R113'])
    contract = contract_screen(fps)
    placement_ok = (not parked and not on_back and not overlaps and not edge_bad and not tails
                    and not any(v['violations'] for v in driver.values())
                    and not any(v['violations_lt_2mm'] for r, v in hand.items() if r not in REPORT_ONLY)
                    and all(h['matches'] for h in headers.values())
                    and round(104.275 - mm(bb.GetTop()), 3) <= GEO['carrier_Z_mm'][1] + 1e-6
                    and not loops['violations'] and ground_ok and contract['pass'])
    pre = pre_routing_checklist(Path(board_path), b, fps, placement_ok)
    post = post_routing_screen(b, fps)

    inset = pcbnew.SHAPE_POLY_SET(outline)
    inset.Deflate(pcbnew.FromMM(1.0), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
    occ = sum(v['polys'].Area() for v in placed.values()) / 1e12
    for v in placed.values():
        del v['polys']
    z_rear = round(104.275 - mm(bb.GetTop()), 3)
    res = {'board': str(Path(board_path).relative_to(MODULE)) if Path(board_path).is_relative_to(MODULE) else str(board_path),
           'ground_split': {'pass': ground_ok, 'analog': 'AGND_U2', 'power': 'GND', 'sole_link': 'R113 PGND pad at C82.2 (PGND)',
                            'AGND_U2_pads': agnd, 'parts_on_both_nets': bridges},
           'routing_contract_screen': contract,
           'pre_routing_checklist': pre, 'post_routing_screen': post,
           'parts_on_board': len(placed), 'parked_parts': sorted(parked), 'parts_on_B': sorted(on_back),
           'tracks': len(list(b.GetTracks())), 'zones': len(copper_zones(b)),
           'routed_items': len(routed_items(b, fps)),
           'rule_areas': len([z for z in b.Zones() if z.GetIsRuleArea()]),
           'courtyard_overlaps': overlaps,
           'edge_rule_findings_not_approved': edge_bad, 'closest_courtyards_to_edge_mm': closest_edge,
           'approved_panel_overhangs': {r: placed[r] for r in sorted(APPROVED_OVERHANG) if r in placed},
           'bracket_driver_circles': driver, 'tht_tails_under_B_bracket_webs': tails,
           'hand_solder_2mm': hand, 'headers_vs_contract': headers, 'local_loops': loops,
           'board_rear_edge_Z_from_panel_front': z_rear,
           'area_mm2': {'outline': round(outline.Area() / 1e12), 'inset_1mm': round(inset.Area() / 1e12),
                        'courtyards_sum': round(occ), 'fill_of_inset': round(occ / (inset.Area() / 1e12), 3)},
           'note': 'Placement record; courtyard fill is a density screen, not a routing proof.'}
    # an unrouted board passes with every post-routing item PENDING; a routed board must pass them all
    res['pass'] = placement_ok and pre['pass'] and post['status'] in ('PENDING', 'PASS')
    return res


def contract_screen(fps):
    """S9.2 routing contract items that can be checked on the unrouted board (tools/s92_contract.py). Copper/via items
    (thermal areas, via counts, sense routing) are reported PENDING, never as passed."""
    def pad(ref, num):
        return next(q for q in fps[ref].Pads() if q.GetNumber() == num)

    def xy(q):
        return mm(q.GetPosition().x), mm(q.GetPosition().y)

    def netof(q):
        return q.GetNetname().split('/')[-1]
    tps = []
    for t in s92_contract.TEST_POINTS:
        q = pad(t['ref'], '1')
        a = pad(*t['near'])
        d = math.dist(xy(q), xy(a))
        size = mm(q.GetSize().x)
        want = 1.5 if t['size'].startswith('1.5') else 1.0
        tps.append({'ref': t['ref'], 'net': netof(q), 'want_net': t['net'], 'pad_mm': round(size, 3),
                    'anchor': f"{t['near'][0]}.{t['near'][1]}", 'distance_mm': round(d, 2), 'limit_mm': t['max'],
                    'ok': netof(q) == t['net'] and d <= t['max'] and abs(size - want) < 1e-6})
    pairs = []
    for t in s92_contract.TEST_POINTS:
        if t.get('pair') and t['ref'] < t['pair']:
            d = math.dist(xy(pad(t['ref'], '1')), xy(pad(t['pair'], '1')))
            pairs.append({'pair': [t['ref'], t['pair']], 'pitch_mm': round(d, 3), 'ok': abs(d - 2.54) < 0.02})
    prox = []
    for (r, n), to, lim, why in s92_contract.PROXIMITY:
        a = pad(r, n)
        best = min((math.dist(xy(a), xy(pad(rr, nn))), f'{rr}.{nn}') for rr, nn in to)
        prox.append({'from': f'{r}.{n}', 'to': best[1], 'distance_mm': round(best[0], 2), 'limit_mm': lim, 'why': why,
                     'ok': best[0] <= lim})
    kel = {num: netof(pad('R109', num)) for num in ('1', '2', '3', '4')}
    kelvin_ok = (kel == {'1': 'P12_VOUT', '2': 'P12_ISP', '3': 'P12_ISN', '4': '+12V'}
                 and netof(pad('U2', '12')) == 'P12_ISP' and netof(pad('U2', '13')) == 'P12_ISN'
                 and netof(pad('U2', '11')) == 'P12_VOUT'
                 and sorted(f'{r}.{q.GetNumber()}' for r, fp in fps.items() for q in fp.Pads()
                            if q.GetNumber() and netof(q) in ('P12_ISP', 'P12_ISN'))
                 == ['R109.2', 'R109.3', 'TP22.1', 'TP23.1', 'U2.12', 'U2.13'])
    ok = all(x['ok'] for x in tps + pairs + prox) and kelvin_ok
    return {'test_points': tps, 'pairs_2p54': pairs, 'proximity': prox,
            'kelvin': {'pad_nets': kel, 'pass': kelvin_ok},
            # S9.2 audit: every copper/via item is a machine check in post_routing_screen (PENDING until routed); the
            # two items DRC now enforces are listed with their rules instead
            'pending_after_routing': sorted(s92_contract.POST_ROUTING),
            'enforced_by_drc': ENFORCED_BY_DRC,
            'pass': ok}


ENFORCED_BY_DRC = {
    'ground.no_second_bridge_copper': ['S92_AGND_U2_to_PGND', 'S92_AGND_U2_island', 'S92_AGND_U2_no_inner_copper',
                                       'native short/clearance check', 'exact ref/pin/net parity (no second 0 ohm)'],
    'thermal.R109.sense_copper': ['S92_SENSE_pair (0.2 mm, no pour, no via)', 'S92_SENSE_F_Cu_only', 'S92_SENSE_to_force'],
}


# ---- S9.2 routing readiness (DeepSeek audit): pre-routing checklist and post-routing machine screen ------------------
def copper_zones(b):
    return [z for z in b.Zones() if not z.GetIsRuleArea()]


def poly_of(points):
    sp = pcbnew.SHAPE_POLY_SET()
    sp.NewOutline()
    for x, y in points:
        sp.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return sp


def inside(a, b):
    """True if polygon set a lies wholly inside b (area outside b below 1e-4 mm2)."""
    x = pcbnew.SHAPE_POLY_SET(a)
    x.BooleanSubtract(b)
    return x.Area() / 1e12 < 1e-4


def overlap(a, b):
    x = pcbnew.SHAPE_POLY_SET(a)
    x.BooleanIntersection(b)
    return x.Area() / 1e12


def layer_poly(p, layer):
    sp = pcbnew.SHAPE_POLY_SET()
    p.TransformShapeToPolygon(sp, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
    return sp


def rule_area_rows(b, fps):
    """Board rule areas against s92_contract.RULE_AREAS: presence, layers, keepout flags, exact polygon, and the fit
    (listed parts wholly inside, no other part's pad on the area's layers intersecting it)."""
    flags = {'tracks': 'GetDoNotAllowTracks', 'vias': 'GetDoNotAllowVias', 'pours': 'GetDoNotAllowZoneFills',
             'pads': 'GetDoNotAllowPads', 'footprints': 'GetDoNotAllowFootprints'}
    got = {z.GetZoneName(): z for z in b.Zones() if z.GetIsRuleArea()}
    rows = []
    for spec in s92_contract.RULE_AREAS:
        z, poly = got.get(spec['name']), poly_of(spec['polygon'])
        row = {'name': spec['name'], 'present': z is not None}
        if z is not None:
            row['layers'] = sorted(b.GetLayerName(l) for l in z.GetLayerSet().Seq())
            row['blocks'] = sorted(k for k, g in flags.items() if getattr(z, g)())
            row['polygon_matches'] = [[round(x, 4), round(y, 4)] for x, y in poly_pts(z.Outline())] == \
                [list(p) for p in spec['polygon']]
            row['net'] = z.GetNetname()
        not_in = [f'{r}.{p.GetNumber()}' for r in spec.get('pads_in', []) for p in fps[r].Pads()
                  if p.GetNumber() and not inside(layer_poly(p, pcbnew.F_Cu), poly)]
        not_in += [r for r in spec.get('courtyard_in', []) if not inside(fps[r].GetCourtyard(pcbnew.F_CrtYd), poly)]
        # S9.2b no-via areas: each named pad's F.Cu copper lies wholly inside (every copper part of a multi-part pad)
        not_in += [rp for rp in spec.get('pad_cover', []) for p in fps[rp.split('.')[0]].Pads()
                   if p.GetNumber() == rp.split('.')[1] and p.IsOnLayer(pcbnew.F_Cu)
                   and not inside(layer_poly(p, pcbnew.F_Cu), poly)]
        allowed = set(spec.get('pads_in', [])) | set(spec.get('courtyard_in', [])) | set(spec.get('touch', []))
        lids = [b.GetLayerID(n) for n in spec['layers']]
        foreign = sorted({r for r, fp in fps.items() if r not in allowed for p in fp.Pads()
                          for lid in lids if p.IsOnLayer(lid) and overlap(layer_poly(p, lid), poly) > 0})
        row.update(not_inside=not_in, foreign_pads=foreign)
        row['ok'] = (z is not None and row['layers'] == sorted(spec['layers']) and row['blocks'] == sorted(spec['blocks'])
                     and row['polygon_matches'] and row['net'] == '' and not not_in and not foreign)
        rows.append(row)
    extra = sorted(n for n in got if n not in {a['name'] for a in s92_contract.RULE_AREAS})
    return rows, extra


def netclass_rows(board_path, b):
    import copy
    from fnmatch import fnmatchcase
    pro = json.loads(Path(board_path).with_suffix('.kicad_pro').read_text())
    want = s92_contract.project_netclasses(copy.deepcopy(pro))['net_settings']
    project_ok = (pro['net_settings']['classes'] == want['classes']
                  and pro['net_settings']['netclass_patterns'] == want['netclass_patterns'])
    nets = {str(n): ni.GetNetClassName() for n, ni in b.GetNetsByName().items()
            if str(n) and not str(n).startswith('unconnected-')}
    hits = {n: [k for k, c in s92_contract.NETCLASSES.items() if any(fnmatchcase(n, p) for p in c['patterns'])]
            for n in nets}
    wrong = sorted(n for n, k in nets.items() if k != (hits[n][0] if hits[n] else 'Default'))
    multi = sorted(n for n, h in hits.items() if len(h) > 1)
    default = sorted(n for n, h in hits.items() if not h)
    count = {k: sum(1 for v in nets.values() if v == k) for k in ['Default', *s92_contract.NETCLASSES]}
    return {'project_matches_contract': project_ok, 'nets': len(nets), 'per_class': count, 'board_class_mismatch': wrong,
            'nets_in_two_classes': multi, 'default_nets': default,
            'ok': project_ok and not wrong and not multi and default == sorted(s92_contract.DEFAULT_NETS)}


def field_at(fps):
    """{ref: (x, y, orientation)} of the thermal-field parts as placed."""
    return {f['ref']: (round(mm(fps[f['ref']].GetPosition().x), 4), round(mm(fps[f['ref']].GetPosition().y), 4),
                       round(fps[f['ref']].GetOrientationDegrees(), 3)) for f in s92_contract.THERMAL_VIA_FIELDS}


def _xy(v):
    return (round(mm(v.x), 4), round(mm(v.y), 4))


def field_copper(b, fps):
    """The S9.2b thermal-field items on the board, matched exactly (geometry, layer, width/size, net) against
    s92_contract.field_items() at the parts' actual positions: ([(spec, board item)], [missing or duplicated specs])."""
    tracks, zones = list(b.GetTracks()), copper_zones(b)
    found, missing = [], []
    for it in s92_contract.field_items(field_at(fps)):
        if it['kind'] == 'via':
            hit = [v for v in tracks if v.GetClass() == 'PCB_VIA' and _xy(v.GetPosition()) == tuple(it['at'])
                   and v.GetNetname() == it['net']]
        elif it['kind'] == 'spoke':
            hit = [x for x in tracks if x.GetClass() == 'PCB_TRACK' and x.GetLayer() == pcbnew.F_Cu
                   and {_xy(x.GetStart()), _xy(x.GetEnd())} == {tuple(it['start']), tuple(it['end'])}
                   and x.GetNetname() == it['net'] and abs(mm(x.GetWidth()) - it['width']) < 1e-6]
        else:
            hit = [z for z in zones if z.GetZoneName() == it['name'] and z.GetNetname() == it['net']
                   and z.GetLayer() == b.GetLayerID(it['layer'])
                   and sorted(poly_pts(z.Outline())) == sorted((round(x, 4), round(y, 4)) for x, y in it['polygon'])]
        if len(hit) == 1:
            found.append((it, hit[0]))
        else:
            missing.append({**{k: it[k] for k in ('kind', 'ref', 'i') if k in it}, 'found': len(hit)})
    return found, missing


def routed_items(b, fps):
    """Tracks, vias and copper zones that are not the generated thermal fields: the routing work."""
    ids = {x.m_Uuid.AsString() for _, x in field_copper(b, fps)[0]}
    return [x for x in list(b.GetTracks()) + copper_zones(b) if x.m_Uuid.AsString() not in ids]


def via_policy_rows(board_path, b, fps):
    """S9.2b via-in-pad PROHIBITED and standard JLCPCB vias only (s92_contract.VIA_SPEC / VIA_IN_PAD): no footprint has a
    plated hole inside one of its pads; U4/U5/U9 use the hole-free copies; the board setup tents and does not fill vias;
    every via is a 0.3/0.6 mm through via without per-via overrides, >= 0.1 mm from every pad's copper and outside every
    pad's solder-mask opening."""
    from sexp import parse, nodes, one
    spec = s92_contract.VIA_SPEC
    holes_in_pads = {}
    for ref, fp in sorted(fps.items()):
        pads = list(fp.Pads())
        holes = [p for p in pads if p.GetDrillSize().x > 0]
        hit = [h for h in holes for q in pads if q is not h and q.IsOnLayer(pcbnew.F_Cu) and q.HitTest(h.GetPosition())]
        if hit:
            holes_in_pads[ref] = sorted({h.GetNumber() for h in hit})
    names = {f['ref']: fps[f['ref']].GetFPIDAsString() for f in s92_contract.THERMAL_VIA_FIELDS}
    want_names = {f['ref']: 'USBPOWER45:' + s92_parts.NO_VIA_IN_PAD[f['key']][1] for f in s92_contract.THERMAL_VIA_FIELDS}
    tree = parse(Path(board_path).read_text())
    setup = one(tree, 'setup')

    def side(key, s):
        node = one(setup, key)
        return None if node is None or one(node, s) is None else one(node, s)[1] == 'yes'

    def flag(key):
        node = one(setup, key)
        return None if node is None else node[1] == 'yes'
    board_setup = {'tenting_front': side('tenting', 'front'), 'tenting_back': side('tenting', 'back'),
                   'covering_front': side('covering', 'front'), 'covering_back': side('covering', 'back'),
                   'plugging_front': side('plugging', 'front'), 'plugging_back': side('plugging', 'back'),
                   'capping': flag('capping'), 'filling': flag('filling')}
    setup_ok = (board_setup['tenting_front'] is True and board_setup['tenting_back'] is True
                and all(v is False for k, v in board_setup.items() if not k.startswith('tenting')))
    bad_vias, overrides = [], []
    for node in nodes(tree, 'via'):
        size, drill = float(one(node, 'size')[1]), float(one(node, 'drill')[1])
        layers = list(one(node, 'layers')[1:])
        at = [float(x) for x in one(node, 'at')[1:3]]
        extra = sorted(c[0] for c in node if isinstance(c, list) and c[0] not in ('at', 'size', 'drill', 'layers', 'net',
                                                                                  'uuid'))
        if (abs(size - spec['diameter_mm']) > 1e-6 or abs(drill - spec['drill_mm']) > 1e-6 or layers != ['F.Cu', 'B.Cu']
                or any(not isinstance(c, list) for c in node[1:])):       # 'blind' / 'micro' type atoms
            bad_vias.append({'at': at, 'size': size, 'drill': drill, 'layers': layers})
        if extra:
            overrides.append({'at': at, 'nodes': extra})
    vias = [v for v in b.GetTracks() if v.GetClass() == 'PCB_VIA']
    pads = [(r, p) for r, fp in fps.items() for p in fp.Pads()]
    near_pad, in_mask = [], []
    for v in vias:
        ring = pcbnew.SHAPE_POLY_SET()
        v.TransformShapeToPolygon(ring, pcbnew.F_Cu, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_OUTSIDE)
        box = ring.BBox()
        box.Inflate(pcbnew.FromMM(0.2))
        for r, p in pads:
            if not p.GetBoundingBox().Intersects(box):
                continue
            for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(lid) and poly_dist(ring, layer_poly(p, lid)) < s92_contract.VIA_SPEC['via_to_pad_min_mm'] - 1e-6:
                    near_pad.append([_xy(v.GetPosition()), f'{r}.{p.GetNumber()}'])
            for lid in (pcbnew.F_Mask, pcbnew.B_Mask):
                if p.IsOnLayer(lid):
                    opening = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(opening, lid, max(0, p.GetSolderMaskExpansion(lid)), pcbnew.FromMM(0.005),
                                              pcbnew.ERROR_OUTSIDE)
                    if overlap(ring, opening) > 0:
                        in_mask.append([_xy(v.GetPosition()), f'{r}.{p.GetNumber() or "mask"}'])
    ok = (not holes_in_pads and names == want_names and setup_ok and not bad_vias and not overrides and not near_pad
          and not in_mask)
    return {'decision': s92_contract.VIA_IN_PAD['decision'], 'footprint_holes_in_pads': holes_in_pads,
            'thermal_pad_footprints': names, 'board_setup': board_setup, 'board_setup_ok': setup_ok,
            'vias': len(vias), 'non_standard_vias': bad_vias, 'via_overrides': overrides,
            'vias_closer_than_0p1mm_to_a_pad': near_pad, 'vias_in_a_mask_opening': in_mask, 'ok': ok}


def thermal_field_rows(b, fps):
    """The board's S9.2b thermal fields against s92_contract.THERMAL_VIA_FIELDS at the parts' actual positions: every via,
    spoke and landing pour present exactly once, each spoke ending inside the exposed-pad copper."""
    found, missing = field_copper(b, fps)
    rows = {}
    for f in s92_contract.THERMAL_VIA_FIELDS:
        num = s92_contract.exposed_pad(f['key'])['pad']
        ep = max((p for p in fps[f['ref']].Pads() if p.GetNumber() == num and p.IsOnLayer(pcbnew.F_Cu)
                  and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD), key=lambda p: p.GetSize().x * p.GetSize().y)
        mine = [(it, x) for it, x in found if it['ref'] == f['ref']]
        vias = [x for it, x in mine if it['kind'] == 'via']
        spokes = [x for it, x in mine if it['kind'] == 'spoke']
        landing = [x for it, x in mine if it['kind'] == 'landing']
        into_pad = sum(1 for it, x in mine if it['kind'] == 'spoke'
                       and ep.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(it['end'][0]), pcbnew.FromMM(it['end'][1]))))
        n = 2 * f['per_end']
        rows[f['ref']] = {'pad': f"{f['ref']}.{num}", 'net': f['net'], 'vias': len(vias), 'spokes': len(spokes),
                          'spokes_into_pad': into_pad, 'landing_pour': landing[0].GetZoneName() if landing else None,
                          'landing_mm2': round(landing[0].Outline().Area() / 1e12, 1) if landing else 0.0,
                          'landing_filled': bool(landing) and landing[0].IsFilled(),
                          'ok': len(vias) == n and len(spokes) == n and into_pad == n and len(landing) == 1}
    return {'fields': rows, 'missing': missing, 'vias_total': sum(r['vias'] for r in rows.values()),
            'ok': not missing and all(r['ok'] for r in rows.values())}


def stackup_rows(board_path, b):
    import re
    text = Path(board_path).read_text()
    setup = text[text.index('(setup'):text.index('(pcbplotparams')]
    cu = {m[0]: round(float(m[1]) * 1000, 1) for m in
          re.findall(r'\(layer "([A-Za-z0-9.]+Cu)"\s*\(type "copper"\)\s*\(thickness ([\d.]+)\)', setup)}
    diel = [float(x) for x in re.findall(r'\(layer "dielectric \d+"\s*\(type "(?:prepreg|core)"\)\s*\(thickness ([\d.]+)\)',
                                         setup)]
    got = {'layers': b.GetCopperLayerCount(), 'thickness_mm': round(mm(b.GetDesignSettings().GetBoardThickness()), 3),
           'copper_um': cu, 'dielectric_mm': diel}
    want = {k: s92_contract.STACKUP[k] for k in got}
    return {**got, 'contract': s92_contract.STACKUP['jlc'], 'ok': got == want}


def test_pad_rows(fps):
    bad = []
    for r, fp in sorted(fps.items()):
        if not r.startswith('TP'):
            continue
        pads = list(fp.Pads())
        p = pads[0]
        if not (len(pads) == 1 and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.IsOnLayer(pcbnew.F_Cu)
                and p.IsOnLayer(pcbnew.F_Mask) and not p.IsOnLayer(pcbnew.F_Paste)):
            bad.append(r)
    return {'pads': sum(1 for r in fps if r.startswith('TP')), 'not_bare_exposed_copper': bad, 'ok': not bad}


def pre_routing_checklist(board_path, b, fps, placement_ok):
    """S9.2 audit item 3: what must hold before routing starts (s92_contract.PRE_ROUTING), each machine-checked."""
    areas, extra = rule_area_rows(b, fps)
    dru = Path(board_path).with_suffix('.kicad_dru')
    want = s92_contract.dru_text((MODULE / s92_contract.R1_RULES).read_text())
    rows = {
        'netclasses': netclass_rows(board_path, b),
        'drc_rules': {'file': dru.name, 'rules': [r[0] for r in s92_contract.drc_rules()],
                      'ok': dru.exists() and dru.read_text() == want},
        'rule_areas': {'areas': areas, 'unexpected': extra, 'ok': all(a['ok'] for a in areas) and not extra},
        'via_in_pad': via_policy_rows(board_path, b, fps),
        'thermal_vias': thermal_field_rows(b, fps),
        'stackup': stackup_rows(board_path, b),
        'test_pads': test_pad_rows(fps),
        'placement': {'ok': placement_ok},
    }
    assert list(rows) == [i for i, _ in s92_contract.PRE_ROUTING]
    return {'items': rows, 'failed': [k for k, v in rows.items() if not v['ok']], 'pass': all(v['ok'] for v in rows.values())}


# Post-routing measurements. Fills are read as saved (run DRC with --refill-zones --save-board first); an unfilled copper
# zone fails the screen rather than being measured as empty.
def islands(b, net, layer):
    """Filled copper of `net` on `layer` (all its zones merged) split into connected pieces."""
    lid = b.GetLayerID(layer)
    acc = pcbnew.SHAPE_POLY_SET()
    for z in copper_zones(b):
        if z.GetNetname() == net and z.IsOnLayer(lid):
            acc.BooleanAdd(z.GetFilledPolysList(lid))
    out = []
    for i in range(acc.OutlineCount()):
        sp = pcbnew.SHAPE_POLY_SET()
        sp.AddOutline(acc.Outline(i))
        for h in range(acc.HoleCount(i)):
            sp.AddHole(acc.Hole(i, h))
        out.append(sp)
    return out


def area(sp):
    return round(sp.Area() / 1e12, 2)


class Copper:
    """Routed copper of one board, indexed by net."""

    def __init__(self, b, fps):
        self.b, self.fps = b, fps
        self.tracks = [t for t in b.GetTracks() if t.GetClass() in ('PCB_TRACK', 'PCB_ARC')]
        self.vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']

    def pad(self, ref, num):
        return next(p for p in self.fps[ref].Pads() if p.GetNumber() == num)

    def pad_net(self, ref, num):
        return self.pad(ref, num).GetNetname()

    def island_of(self, ref, num, layer='F.Cu'):
        """The filled island of the pad's net on `layer` that touches the pad, or None."""
        p = self.pad(ref, num)
        sp = layer_poly(p, self.b.GetLayerID(layer))
        sp.Inflate(pcbnew.FromMM(0.01), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
        return next((i for i in islands(self.b, p.GetNetname(), layer) if overlap(sp, i) > 0), None)

    def holds(self, island, pads, layer='F.Cu'):
        """Pads (ref.num) of `pads` that the island does NOT touch."""
        miss = []
        for rp in pads:
            r, n = rp.split('.')
            sp = layer_poly(self.pad(r, n), self.b.GetLayerID(layer))
            sp.Inflate(pcbnew.FromMM(0.01), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
            if island is None or overlap(sp, island) <= 0:
                miss.append(rp)
        return miss

    def vias_in(self, island, net):
        return [v for v in self.vias if v.GetNetname() == net and island is not None and island.Contains(v.GetPosition())]

    def landing(self, vias, net, layers):
        """Largest same-net island on any of `layers` that holds at least one of the vias: (layer, area, vias held)."""
        best = (None, 0.0, 0)
        for layer in layers:
            for i in islands(self.b, net, layer):
                held = sum(1 for v in vias if i.Contains(v.GetPosition()))
                if held and area(i) > best[1]:
                    best = (layer, area(i), held)
        return best

    def vias_near(self, ref, num, net, limit):
        sp = layer_poly(self.pad(ref, num), pcbnew.F_Cu)
        segs = poly_segs(sp)
        out = []
        for v in self.vias:
            if v.GetNetname() != net:
                continue
            c = (mm(v.GetPosition().x), mm(v.GetPosition().y))
            if sp.Contains(v.GetPosition()) or min(seg_dist(c, *s) for s in segs) <= limit:
                out.append(v)
        return out

    def chains(self, net):
        """Connected track chains of a net: [{'tracks': [...], 'pads': {ref.num}}] (vias join chains on any layer)."""
        items = [t for t in self.tracks if t.GetNetname() == net]
        vias = [v for v in self.vias if v.GetNetname() == net]
        parent = list(range(len(items) + len(vias)))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        def join(i, j):
            parent[find(i)] = find(j)
        ends = [(t.GetStart(), t.GetEnd(), t.GetLayer()) for t in items]
        for i, (a, c, la) in enumerate(ends):
            for j in range(i + 1, len(ends)):
                a2, c2, lb = ends[j]
                if la == lb and {(p.x, p.y) for p in (a, c)} & {(p.x, p.y) for p in (a2, c2)}:
                    join(i, j)
            for k, v in enumerate(vias):
                if any(v.HitTest(p) for p in (a, c)):
                    join(i, len(items) + k)
        pads = [(f'{r}.{p.GetNumber()}', p) for r, fp in self.fps.items() for p in fp.Pads()
                if p.GetNetname() == net and p.GetNumber()]
        groups = {}
        for i, t in enumerate(items):
            g = groups.setdefault(find(i), {'tracks': [], 'pads': set()})
            g['tracks'].append(t)
            for rp, p in pads:
                if p.IsOnLayer(t.GetLayer()) and (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())):
                    g['pads'].add(rp)
        return list(groups.values())


def _tvs(cu, ref, bank, gnd_vias, alt_bcu=False):
    """TVS proximity: the cathode pad on the same F.Cu pour island as the protected bank pads (D26 alternatively >= 2
    vias from its own island into the B.Cu island that the bank's vias land in) and >= gnd_vias GND vias at the anode."""
    net, isl = cu.pad_net(ref, '1'), cu.island_of(ref, '1')
    miss = cu.holds(isl, bank)
    row = {'cathode_island_mm2': area(isl) if isl else 0.0, 'bank_pads_not_on_it': miss}
    joined = not miss
    if miss and alt_bcu and isl is not None:
        theirs = cu.vias_in(cu.island_of(*bank[0].split('.')), net)
        own = cu.vias_in(isl, net)
        shared = [i for i in islands(cu.b, net, 'B.Cu') if any(i.Contains(v.GetPosition()) for v in theirs)]
        row['vias_into_bank_B_Cu_island'] = max((sum(1 for v in own if i.Contains(v.GetPosition())) for i in shared),
                                                default=0)
        joined = row['vias_into_bank_B_Cu_island'] >= 2
    anode = cu.vias_near(ref, '2', 'GND', 1.5)
    row.update(anode_gnd_vias=len(anode), ok=joined and len(anode) >= gnd_vias)
    return row


def post_routing_screen(b, fps):
    """s92_contract.POST_ROUTING measured on the routed board; every item PENDING while the board carries no copper
    beyond the S9.2b thermal fields (fixed pre-routing copper, checked by pre_routing_checklist.thermal_vias)."""
    zones = copper_zones(b)
    found, _ = field_copper(b, fps)
    if not routed_items(b, fps):
        return {'status': 'PENDING', 'reason': 'unrouted: no track, via or copper zone beyond the S9.2b thermal fields',
                'items': {k: {'status': 'PENDING', 'requirement': v} for k, v in s92_contract.POST_ROUTING.items()}}
    unfilled = sorted(z.GetZoneName() or z.GetNetname() for z in zones if not z.IsFilled())
    cu = Copper(b, fps)
    field_vias = {f['ref']: [x for it, x in found if it['ref'] == f['ref'] and it['kind'] == 'via']
                  for f in s92_contract.THERMAL_VIA_FIELDS}
    spokes = {x.m_Uuid.AsString() for it, x in found if it['kind'] == 'spoke'}
    P12 = s92_contract.P12
    r = {}
    r['tvs.D24'] = _tvs(cu, 'D24', ['C8.1', 'C6.1', 'C7.1', 'C77.1', 'C78.1'], 3)
    r['tvs.D26'] = _tvs(cu, 'D26', ['C14.1', 'C79.1', 'C80.1'], 3, alt_bcu=True)
    r['tvs.D1'] = _tvs(cu, 'D1', ['D10.2'], 3)
    d25 = cu.vias_near('D25', '1', 'GND', 1.5)
    r['tvs.D25'] = {'gnd_vias': len(d25), 'ok': len(d25) >= 1}
    agnd = P12 + 'AGND_U2'
    bruns = [c for c in cu.chains(agnd) if all(t.GetLayer() == pcbnew.B_Cu for t in c['tracks'])]
    r['ground.agnd_link'] = {'b_cu_runs': len(bruns), 'vias': sum(1 for v in cu.vias if v.GetNetname() == agnd),
                             'ok': len(bruns) <= 1}
    r['kelvin.sense_routing'] = kelvin_routing(cu)
    in1 = islands(b, 'GND', 'In1.Cu')
    other_in1 = sorted({z.GetNetname() for z in zones if z.IsOnLayer(pcbnew.In1_Cu) and z.GetNetname() != 'GND'})
    u2 = fps['U2'].GetPosition()
    holes = []
    for i in in1:
        for h in range(i.HoleCount(0)):
            hb = i.Hole(0, h).BBox()
            c = hb.Centre()
            if math.hypot(mm(c.x - u2.x), mm(c.y - u2.y)) <= 15.0:
                holes.append(max(mm(hb.GetWidth()), mm(hb.GetHeight())))
    r['thermal.U2.In1'] = {'pieces': len(in1), 'other_nets_on_In1': other_in1, 'largest_hole_within_15mm_mm':
                           round(max(holes), 3) if holes else 0.0, 'ok': len(in1) == 1 and not other_in1
                           and all(h <= 1.6 for h in holes)}
    box = pcbnew.BOX2I()
    for p in fps['U2'].Pads():
        box.Merge(p.GetBoundingBox())
    box.Inflate(pcbnew.FromMM(4.0))
    pads_all = [(p, layer_poly(p, pcbnew.F_Cu)) for fp in fps.values() for p in fp.Pads() if p.IsOnLayer(pcbnew.F_Cu)]
    def clear_of_pads(v):
        ring = pcbnew.SHAPE_POLY_SET()
        v.TransformShapeToPolygon(ring, pcbnew.F_Cu, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
        return all(overlap(ring, sp) <= 0 for p, sp in pads_all if p.GetBoundingBox().Intersects(ring.BBox()))
    pg = [v for v in cu.vias if v.GetNetname() == 'GND' and box.Contains(v.GetPosition())
          and round(mm(v.GetDrillValue()), 3) == 0.3 and mm(v.GetWidth(pcbnew.F_Cu)) >= 0.6 - 1e-6 and clear_of_pads(v)]
    r['thermal.U2.PGND_vias'] = {'count': len(pg), 'ok': len(pg) >= 10}
    vin = cu.island_of('U2', '7')
    vin_v = cu.vias_in(vin, 'VIN')
    l2 = cu.landing(vin_v, 'VIN', ['In2.Cu'])
    r['thermal.U2.VIN_area'] = {'F_Cu_mm2': area(vin) if vin else 0.0,
                                'misses': cu.holds(vin, ['C8.1', 'C6.1', 'C7.1', 'C77.1', 'C78.1', 'D24.1']),
                                'vias': len(vin_v), 'In2_mm2': l2[1],
                                'ok': bool(vin) and area(vin) >= 120 and not cu.holds(vin, ['C8.1', 'C6.1', 'C7.1', 'C77.1',
                                                                                         'C78.1', 'D24.1'])
                                and len(vin_v) >= 6 and l2[1] >= 300}
    vo = cu.island_of('U2', '11')
    vo_pads = ['C81.1', 'C11.1', 'C12.1', 'C13.1', 'C14.1', 'C79.1', 'C80.1', 'R109.1']
    vo_v = cu.vias_in(vo, P12 + 'P12_VOUT')
    lb = cu.landing(vo_v, P12 + 'P12_VOUT', ['B.Cu'])
    r['thermal.U2.VOUT_area'] = {'F_Cu_mm2': area(vo) if vo else 0.0, 'misses': cu.holds(vo, vo_pads), 'vias': len(vo_v),
                                 'B_Cu_mm2': lb[1], 'ok': bool(vo) and area(vo) >= 150 and not cu.holds(vo, vo_pads)
                                 and len(vo_v) >= 6 and lb[1] >= 200}
    bg = next((i for i in islands(b, 'GND', 'B.Cu') if i.Contains(u2)), None)
    bg_v = cu.vias_in(bg, 'GND')
    r['thermal.U2.B_Cu_GND'] = {'mm2': area(bg) if bg else 0.0, 'vias': len(bg_v),
                                'ok': bool(bg) and area(bg) >= 600 and len(bg_v) >= 20}
    force = {}
    for num, net in (('1', P12 + 'P12_VOUT'), ('4', '+12V')):
        c = cu.pad('R109', num).GetPosition()
        circ = pcbnew.SHAPE_POLY_SET()
        circ.NewOutline()
        for k in range(72):
            circ.Append(int(c.x + pcbnew.FromMM(10) * math.cos(k * math.pi / 36)),
                        int(c.y + pcbnew.FromMM(10) * math.sin(k * math.pi / 36)))
        copper = pcbnew.SHAPE_POLY_SET()
        for i in islands(b, net, 'F.Cu'):
            copper.BooleanAdd(i)
        for t in cu.tracks:
            if t.GetNetname() == net and t.GetLayer() == pcbnew.F_Cu:
                t.TransformShapeToPolygon(copper, pcbnew.F_Cu, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
        copper.Simplify()
        near = [v for v in cu.vias if v.GetNetname() == net and circ.Contains(v.GetPosition())]
        landed = sum(1 for v in near if any(i.Contains(v.GetPosition()) for layer in ('B.Cu', 'In2.Cu')
                                            for i in islands(b, net, layer)))
        force[f'pad{num}'] = {'F_Cu_within_10mm_mm2': round(overlap(copper, circ), 1), 'vias_landed': landed}
    r['thermal.R109.force_copper'] = {**force, 'ok': all(v['F_Cu_within_10mm_mm2'] >= 150 and v['vias_landed'] >= 3
                                                          for v in force.values())}
    d10 = {}
    for p in fps['D10'].Pads():
        net, isl = p.GetNetname(), cu.island_of('D10', p.GetNumber())
        vv = cu.vias_in(isl, net)
        lbd = cu.landing(vv, net, ['B.Cu'])
        d10[net.split('/')[-1]] = {'F_Cu_mm2': area(isl) if isl else 0.0, 'vias': len(vv), 'B_Cu_mm2': lbd[1]}
    r['thermal.D10.copper'] = {**d10, 'ok': all(v['F_Cu_mm2'] >= 400 and v['vias'] >= 8 and v['B_Cu_mm2'] >= 300
                                                for v in d10.values())}
    u4v = field_vias['U4']
    u4a = max([area(i) for layer in ('In2.Cu', 'B.Cu') for i in islands(b, '-12V', layer)
               if u4v and all(i.Contains(v.GetPosition()) for v in u4v)] or [0.0])
    r['thermal.U4.copper'] = {'field_vias': len(u4v), 'minus12_area_mm2': u4a, 'ok': len(u4v) == 10 and u4a >= 300}
    for ref in ('U5', 'U9'):
        vs = field_vias[ref]
        landed = sum(1 for v in vs if any(i.Contains(v.GetPosition()) for i in in1))
        r[f'thermal.{ref}.copper'] = {'field_vias': len(vs), 'in_In1_GND': landed, 'ok': landed == len(vs) and bool(vs)}
    r['min_widths'] = min_widths(cu, skip=spokes)
    items = {k: {'status': 'PASS' if v.pop('ok') else 'FAIL', 'requirement': s92_contract.POST_ROUTING[k], **v}
             for k, v in r.items()}
    assert set(items) == set(s92_contract.POST_ROUTING)
    failed = sorted(k for k, v in items.items() if v['status'] == 'FAIL')
    return {'status': 'FAIL' if failed or unfilled else 'PASS', 'unfilled_zones': unfilled, 'failed': failed,
            'items': items}


def kelvin_routing(cu):
    """Sense attach at the R109 pads and pair coupling, measured on the main path R109.2/3 -> U2.12/13."""
    P12 = s92_contract.P12
    out, paths = {}, {}
    for net, rpad, upad in ((P12 + 'P12_ISP', ('R109', '2'), ('U2', '12')), (P12 + 'P12_ISN', ('R109', '3'), ('U2', '13'))):
        pad = cu.pad(*rpad)
        bb = pad.GetBoundingBox()
        inner = bb.GetRight() if rpad[1] == '2' else bb.GetLeft()
        bad = []
        segs = [t for t in cu.tracks if t.GetNetname() == net and t.GetLayer() == pcbnew.F_Cu]
        for t in segs:
            for a, c in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                if pad.HitTest(a) and not pad.HitTest(c):
                    if c.y <= bb.GetBottom():
                        bad.append('leaves the pad sideways or north')
                        continue
                    f = (bb.GetBottom() - a.y) / (c.y - a.y) if c.y != a.y else 0
                    x = a.x + f * (c.x - a.x)
                    if abs(mm(x - inner)) > 0.6:
                        bad.append(f'crosses the +y edge {abs(mm(x - inner)):.2f} mm from the inner end')
        paths[net] = main_path(cu, segs, cu.pad(*rpad), cu.pad(*upad))
        out[net.split('/')[-1]] = {'attach_problems': bad, 'main_path_found': paths[net] is not None}
    esc = poly_of(next(a for a in s92_contract.RULE_AREAS if a['name'] == 'RA_U2_SENSE_ESCAPE')['polygon'])
    pads = [layer_poly(cu.pad('R109', n), pcbnew.F_Cu) for n in ('2', '3')]
    for net, other in ((P12 + 'P12_ISP', P12 + 'P12_ISN'), (P12 + 'P12_ISN', P12 + 'P12_ISP')):
        unc = 0.0
        if paths[net] and paths[other]:
            osegs = [((mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y))) for t in paths[other]]
            for t in paths[net]:
                a, c = (mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y))
                n = max(1, int(math.dist(a, c) / 0.1))
                for k in range(n):
                    s = (a[0] + (c[0] - a[0]) * (k + 0.5) / n, a[1] + (c[1] - a[1]) * (k + 0.5) / n)
                    pt = pcbnew.VECTOR2I(pcbnew.FromMM(s[0]), pcbnew.FromMM(s[1]))
                    if esc.Contains(pt) or any(min(seg_dist(s, *g) for g in poly_segs(p)) <= 1.0 or p.Contains(pt)
                                               for p in pads):
                        continue
                    if min(seg_dist(s, *g) for g in osegs) > 0.5 + 1e-6:     # 0.2 mm width + 0.3 mm gap
                        unc += math.dist(a, c) / n
        out[net.split('/')[-1]]['uncoupled_mm'] = round(unc, 2)
    ok = all(not v['attach_problems'] and v['main_path_found'] and v.get('uncoupled_mm', 99) <= 1.0 for v in out.values())
    return {**out, 'ok': ok}


def main_path(cu, segs, start_pad, end_pad):
    """Track segments of the shortest chain from start_pad to end_pad (BFS over shared endpoints), or None."""
    key = lambda p: (p.x, p.y)
    adj = {}
    for t in segs:
        a, c = key(t.GetStart()), key(t.GetEnd())
        adj.setdefault(a, []).append((c, t))
        adj.setdefault(c, []).append((a, t))
    starts = [n for n in adj if start_pad.HitTest(pcbnew.VECTOR2I(*n))]
    goal = {n for n in adj if end_pad.HitTest(pcbnew.VECTOR2I(*n))}
    prev, todo = {n: None for n in starts}, list(starts)
    while todo:
        n = todo.pop(0)
        if n in goal:
            path = []
            while prev[n] is not None:
                n, t = prev[n]
                path.append(t)
            return path
        for m, t in adj.get(n, []):
            if m not in prev:
                prev[m] = (n, t)
                todo.append(m)
    return None


def min_widths(cu, skip=()):
    """Current-path widths (s92_contract.CURRENT_MIN_MM): a chain that reaches a current-carrying pad (or no pad: a link
    between pours) needs the class minimum; a chain reaching only tap pads needs its taps' minimum. Neck-downs of
    <= 1.0 mm that end inside a pad are allowed. skip = UUIDs of the S9.2b thermal spokes (heat paths, no load current)."""
    classes = {n: c for n, c in s92_contract.CURRENT_MIN_MM.items()}
    nets = {}
    for n, ni in cu.b.GetNetsByName().items():
        if ni.GetNetClassName() in classes:
            nets[str(n)] = classes[ni.GetNetClassName()]
    bad = []
    for net, need in sorted(nets.items()):
        for ch in cu.chains(net):
            taps = [s92_contract.tap_min(rp.split('.')[0]) for rp in ch['pads']]
            req = need if (not taps or any(t is None for t in taps)) else max(taps)
            for t in ch['tracks']:
                w = mm(t.GetWidth())
                if w + 1e-6 >= req or t.m_Uuid.AsString() in skip:
                    continue
                neck = (mm(t.GetLength()) <= 1.0 and any(p.HitTest(x) for fp in cu.fps.values() for p in fp.Pads()
                                                          if p.GetNetname() == net for x in (t.GetStart(), t.GetEnd())))
                if not neck:
                    bad.append({'net': net, 'width_mm': round(w, 3), 'required_mm': req,
                                'at': [round(mm(t.GetStart().x), 2), round(mm(t.GetStart().y), 2)]})
    return {'violations': bad[:20], 'count': len(bad), 'ok': not bad}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--board', type=Path, default=MODULE / 'hardware/single/usb-power-45w-single.kicad_pcb')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    res = check(a.board.resolve())
    txt = json.dumps(res, indent=1) + '\n'
    if a.out:
        a.out.write_text(txt)
    print(txt)
