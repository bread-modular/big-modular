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
  bypass capacitor / clamp on the same net, against the LOCAL_LOOPS limits (straight line, the review's metric).
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
           'parts_on_board': len(placed), 'parked_parts': sorted(parked), 'parts_on_B': sorted(on_back),
           'tracks': len(list(b.GetTracks())), 'zones': len(list(b.Zones())),
           'courtyard_overlaps': overlaps,
           'edge_rule_findings_not_approved': edge_bad, 'closest_courtyards_to_edge_mm': closest_edge,
           'approved_panel_overhangs': {r: placed[r] for r in sorted(APPROVED_OVERHANG) if r in placed},
           'bracket_driver_circles': driver, 'tht_tails_under_B_bracket_webs': tails,
           'hand_solder_2mm': hand, 'headers_vs_contract': headers, 'local_loops': loops,
           'board_rear_edge_Z_from_panel_front': z_rear,
           'area_mm2': {'outline': round(outline.Area() / 1e12), 'inset_1mm': round(inset.Area() / 1e12),
                        'courtyards_sum': round(occ), 'fill_of_inset': round(occ / (inset.Area() / 1e12), 3)},
           'note': 'Placement record; courtyard fill is a density screen, not a routing proof.'}
    res['pass'] = (not parked and not on_back and not overlaps and not edge_bad and not tails
                   and not any(v['violations'] for v in driver.values())
                   and not any(v['violations_lt_2mm'] for r, v in hand.items() if r not in REPORT_ONLY)
                   and all(h['matches'] for h in headers.values()) and z_rear <= GEO['carrier_Z_mm'][1] + 1e-6
                   and not loops['violations'] and ground_ok and contract['pass'])
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
    pending = sorted(f'thermal.{k}.{x}' for k, v in s92_contract.THERMAL.items() for x in v['requirements'])
    ok = all(x['ok'] for x in tps + pairs + prox) and kelvin_ok
    return {'test_points': tps, 'pairs_2p54': pairs, 'proximity': prox,
            'kelvin': {'pad_nets': kel, 'pass': kelvin_ok},
            'pending_after_routing': pending + ['kelvin.sense_routing', 'ground.no_second_bridge_copper', 'min_widths'],
            'pass': ok}


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
