#!/usr/bin/env python3
"""Independent checks for the R2 stacked boards (canonical hardware/base + hardware/top).

  python3 -B tools/check_stack.py --scratch research/r2/check-<n>

Writes docs/stack-r2/validation.json; raw native ERC/DRC/netlists stay in --scratch.
1. Native ERC (all severities) of the S7 root and both board schematics.
2. Native DRC (all severities, schematic parity, no exclusions) of both boards.
3. Aggregate interconnect equivalence: base + top native netlists joined pin-for-pin through
   XB1=XT1 / XB2=XT2 (header pins then removed) == the S7 root netlist, exact pin-set partition
   incl. no-connect pins; every S7 ref on exactly one board with identical value/footprint/fields.
4. Header manifest: pin nets on both boards == tools/stack_r2.py, same pin positions; crossing
   nets == carried nets; per-pin current screen.
5. Geometry: 1 mm courtyard (+stroke) / copper edge, 2 mm hand-solder, via-in-SMD-pad, In1 tracks,
   plane pieces, fixed base interfaces vs the accepted monolithic board.
6. Stack mechanics: heights vs gap/panel width with assumed tolerances, J2 box/plug/ribbon vs the
   top outline, brackets/nuts/tools vs top slab and parts, through-bolt and header-pin lengths.
7. Converter locality metrics and thermal-terminal nets.
Not a manufacturing release, not a 45 W rating; assumptions are listed in the output.
"""
import argparse
import collections
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
HW = MOD / 'hardware'
sys.path.insert(0, str(MOD / 'tools'))
import pcbnew  # noqa: E402
import stack_r2 as st  # noqa: E402
import mechanics45 as m  # noqa: E402

STROKE = 0.025
ALLOWED_OVERHANG = {'J1', 'SW1', 'D8', 'D16', 'D17', 'D18'}   # user-authorised, same fixed positions
ROOT_HS = {'J1', 'J2', 'XT1', 'XT2'}   # root rule: hand-soldered connector THT pads/lugs on the SMD face
EXTRA_HS = {'SW1', 'D8', 'D16', 'D17', 'D18'}   # hand-soldered, not jacks: same 2 mm kept as extra margin
B_FACE_JOINT = {'XB1', 'XB2'}   # base header tails are soldered from base B (no parts on B): F-side distance informational


def yz(v):
    return pcbnew.ToMM(v.x) - 35.75, 104.275 - pcbnew.ToMM(v.y)


def bbox_yz(bb):
    (a, c), (b, d) = yz(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), yz(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))
    return [a, b, c, d]


def gap(r, s):
    return math.hypot(max(r[0] - s[1], s[0] - r[1], 0.0), max(r[2] - s[3], s[2] - r[3], 0.0))


def seg_rect(a, b, r):
    """Distance from segment a-b to rect r (0 if they touch)."""
    def inside(p):
        return r[0] <= p[0] <= r[1] and r[2] <= p[1] <= r[3]
    if inside(a) or inside(b):
        return 0.0
    def pt_seg(p, q1, q2):
        dx, dy = q2[0] - q1[0], q2[1] - q1[1]
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((p[0] - q1[0]) * dx + (p[1] - q1[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - q1[0] - t * dx, p[1] - q1[1] - t * dy)
    corners = [(r[0], r[2]), (r[1], r[2]), (r[1], r[3]), (r[0], r[3])]
    d = min(pt_seg(c, a, b) for c in corners)
    edges = list(zip(corners, corners[1:] + corners[:1]))
    d = min(d, *(pt_seg(p, e1, e2) for p in (a, b) for e1, e2 in edges))
    def cross(p1, p2, p3, p4):
        def o(p, q, s):
            return (q[0] - p[0]) * (s[1] - p[1]) - (q[1] - p[1]) * (s[0] - p[0])
        return o(p1, p2, p3) * o(p1, p2, p4) < 0 and o(p3, p4, p1) * o(p3, p4, p2) < 0
    if any(cross(a, b, e1, e2) for e1, e2 in edges):
        return 0.0
    return d


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode


def xml_netlist(sch, out):
    run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out), str(sch)])
    root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        comps[c.get('ref')] = (c.findtext('value'), c.findtext('footprint'),
                               tuple(sorted((f.get('name'), f.text or '') for f in c.find('fields'))))
    nets = {}
    for n in root.find('nets'):
        nets[n.get('name')] = frozenset((d.get('ref'), d.get('pin')) for d in n.findall('node'))
    return comps, nets


def erc(sch, out):
    run(['kicad-cli', 'sch', 'erc', '--severity-all', '--format', 'json', '-o', str(out), str(sch)])
    d = json.loads(Path(out).read_text())
    return sum(len(s.get('violations', [])) for s in d.get('sheets', []))


def board(name):
    return pcbnew.LoadBoard(str(HW / name / f'usb-power-45w-{name}.kicad_pcb'))


def outline_segments(b):
    segs = []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            assert d.GetShape() == pcbnew.SHAPE_T_SEGMENT, 'outline must be straight segments'
            segs.append((yz(d.GetStart()), yz(d.GetEnd())))
    return segs


def poly_contains(segs, p):
    ins = False
    for (ya, za), (yb, zb) in segs:
        if (za > p[1]) != (zb > p[1]) and p[0] < ya + (p[1] - za) * (yb - ya) / (zb - za):
            ins = not ins
    return ins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scratch', required=True)
    sc = Path(ap.parse_args().scratch)
    sc.mkdir(parents=True, exist_ok=True)
    rep = {'problems': [], 'not_claimed': [
        'manufacturing release / fabrication export', '45 W or simultaneous 54.5 W rating',
        'thermal performance or junction temperatures', 'connector/pin current rating (vendor data)',
        'can/LED/header/bolt heights beyond the assumed envelopes listed in stack_assumptions']}
    sch = {'root': HW / 'usb-power-45w.kicad_sch', 'base': HW / 'base/usb-power-45w-base.kicad_sch',
           'top': HW / 'top/usb-power-45w-top.kicad_sch'}
    rep['erc'] = {k: erc(v, sc / f'erc-{k}.json') for k, v in sch.items()}
    if any(rep['erc'].values()):
        rep['problems'].append('ERC')
    import drc_summary
    rep['drc'] = {}
    for b in ('base', 'top'):
        r = drc_summary.drc(b, sc)
        r.pop('details')
        rep['drc'][b] = r
        if r['violations'] or r['parity'] or r['excluded']:
            rep['problems'].append(f'DRC {b}')
    # ---- 3. aggregate interconnect equivalence -----------------------------------------------
    net = {k: xml_netlist(v, sc / f'netlist-{k}.xml') for k, v in sch.items()}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for b in ('base', 'top'):
        for nodes in net[b][1].values():
            nodes = sorted(nodes)
            for n in nodes[1:]:
                parent[find((b, *n))] = find((b, *nodes[0]))
            find((b, *nodes[0]))
    hdr_pins = {}
    for bref, tref in st.PAIRS.items():
        nets_b = {p: n for n, s in net['base'][1].items() for r, p in s if r == bref}
        nets_t = {p: n for n, s in net['top'][1].items() for r, p in s if r == tref}
        hdr_pins[bref] = (nets_b, nets_t)
        for p in nets_b:
            parent[find(('base', bref, p))] = find(('top', tref, p))
    groups = collections.defaultdict(set)
    for x in list(parent):
        if x[1] in st.PAIRS or x[1] in st.PAIRS.values():
            continue
        groups[find(x)].add((x[1], x[2]))
    joined = {frozenset(g) for g in groups.values() if g}
    rootsets = {s for s in net['root'][1].values()}
    refs_b = set(net['base'][0]) - set(st.PAIRS)
    refs_t = set(net['top'][0]) - set(st.PAIRS.values())
    comp_bad = [r for r in net['root'][0] if (net['base'][0].get(r) or net['top'][0].get(r)) != net['root'][0][r]]
    rep['interconnect_equivalence'] = {
        'root_refs': len(net['root'][0]), 'base_refs': len(refs_b), 'top_refs': len(refs_t),
        'refs_on_both_boards': sorted(refs_b & refs_t),
        'refs_missing': sorted(set(net['root'][0]) - refs_b - refs_t),
        'refs_extra': sorted((refs_b | refs_t) - set(net['root'][0])),
        'value_footprint_field_mismatch': comp_bad,
        'root_nets_incl_NC': len(rootsets), 'joined_nets_incl_NC': len(joined),
        'nets_only_in_root': len(rootsets - joined), 'nets_only_in_join': len(joined - rootsets),
        'equal': rootsets == joined and not comp_bad and not (refs_b & refs_t)
        and set(net['root'][0]) == refs_b | refs_t,
        'method': 'union of the two native board netlists, XB1.n=XT1.n and XB2.n=XT2.n, header pins '
                  'removed, compared as exact (ref, pin) partitions incl. single-pin no-connect nets'}
    if not rep['interconnect_equivalence']['equal']:
        rep['problems'].append('interconnect equivalence')
    # ---- 4. header manifest / currents --------------------------------------------------------
    man_bad = []
    for (bref, (nb, nt)), want in zip(hdr_pins.items(), (st.XP_NETS, st.XL_NETS)):
        for i, w in enumerate(want, 1):
            for side, got in (('base', nb.get(str(i))), ('top', nt.get(str(i)))):
                if got is None or got.lstrip('/') != w:
                    man_bad.append((bref, i, side, got, w))
    bb, tb = board('base'), board('top')
    pos_bad = []
    for bref, tref in st.PAIRS.items():
        fb, ft = bb.FindFootprintByReference(bref), tb.FindFootprintByReference(tref)
        for p in fb.Pads():
            q = ft.FindPadByNumber(p.GetNumber())
            if max(abs(a - c) for a, c in zip(yz(p.GetPosition()), yz(q.GetPosition()))) > 1e-4 \
                    or p.GetNetname() != q.GetNetname():
                pos_bad.append((bref, p.GetNumber(), p.GetNetname(), q.GetNetname()))
    cross = set()
    names = {b: {n.lstrip('/') for n, s in net[b][1].items() if not n.startswith('unconnected-')
                 and any(r not in st.PAIRS and r not in st.PAIRS.values() and not r.startswith('#') for r, _ in s)}
             for b in ('base', 'top')}
    cross = names['base'] & names['top']
    carried = set(st.XP_NETS) | set(st.XL_NETS)
    cnt = collections.Counter(st.XP_NETS + st.XL_NETS)
    rep['header_manifest'] = {
        'XP_power_2x10': st.XP_NETS, 'XL_logic_2x3': st.XL_NETS, 'pin_net_mismatches': man_bad,
        'pin_position_or_net_mismatch_base_vs_top': pos_bad,
        'crossing_nets': sorted(cross), 'crossing_not_carried': sorted(cross - carried),
        'carried_not_crossing': sorted(carried - cross),
        'no_SW_BOOT_FB_SENSE_Kelvin_crossing': not [n for n in cross if any(k in n for k in ('SW', 'BST', 'BOOT', 'FB', 'SENSE', 'N_OUT'))],
        'current_screen': {n: {'I_screen_A': i, 'pins': cnt[n], 'A_per_pin': round(i / cnt[n], 3),
                               'within_assumed_budget': i / cnt[n] <= st.PIN_BUDGET_A}
                           for n, i in st.SCREEN_A.items()},
        'note': f'{st.PIN_BUDGET_A} A/pin is an ASSUMED design budget for soldered 0.64 mm square pins in a '
                'poorly ventilated gap, not a vendor rating. GND: 7 pins carry the input return (down) and '
                'the +12/+5 load return (up) in opposite directions; no cancellation is assumed (6 A screen).'}
    if man_bad or pos_bad or cross - carried or carried - cross:
        rep['problems'].append('header manifest')
    # ---- 5. geometry -----------------------------------------------------------------------
    geo = {}
    acc = pcbnew.LoadBoard(str(HW / 'usb-power-45w.kicad_pcb'))
    for name, b in (('base', bb), ('top', tb)):
        segs = outline_segments(b)
        edge, edge_bad, hs, hs_bad = {}, [], {}, []
        src = []
        for f in b.GetFootprints():
            r = f.GetReference()
            if r in ROOT_HS | EXTRA_HS | B_FACE_JOINT:
                for p in f.Pads():
                    if (r == 'J1' and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD) or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                        continue
                    src.append((r, bbox_yz(p.GetBoundingBox())))
        for f in b.GetFootprints():
            sup = f.GetFPID().GetLibItemName().wx_str().startswith('Stack_M3')
            r = f.GetReference() or ('support@Y%.1f' % yz(f.GetPosition())[0] if sup else '(carrier hole)')
            cy = f.GetCourtyard(pcbnew.F_CrtYd)
            if cy.OutlineCount():
                c = bbox_yz(cy.BBox())
                if sup:     # circle: bbox corners overstate, use centre distance
                    cyy, czz = yz(f.GetPosition())
                    rr = (c[1] - c[0]) / 2          # bbox already includes the half line width
                    d = min(seg_rect(a, e, [cyy, cyy, czz, czz]) for a, e in segs) - rr
                else:
                    cg = [c[0] - STROKE, c[1] + STROKE, c[2] - STROKE, c[3] + STROKE]
                    inside = all(poly_contains(segs, (y, z)) for y in cg[:2] for z in cg[2:])
                    d = min(seg_rect(a, e, cg) for a, e in segs) if inside else 0.0
                edge[r] = round(d, 3)
                if d < 1.0 - 1e-6 and r not in ALLOWED_OVERHANG:
                    edge_bad.append((r, round(d, 3)))
            if r in ROOT_HS | EXTRA_HS | B_FACE_JOINT or sup or r == '(carrier hole)':
                continue
            for p in f.Pads():
                if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue
                pb = bbox_yz(p.GetBoundingBox())
                for sr, sb in src:
                    g = gap(pb, sb)
                    key = (r, sr)
                    if g < hs.get(key, 99):
                        hs[key] = round(g, 3)
                    if g < 2.0 - 1e-6 and sr not in B_FACE_JOINT:
                        hs_bad.append((r, p.GetNumber(), sr, round(g, 3), 'root' if sr in ROOT_HS else 'extra'))
        vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
        vip = []
        for v in vias:
            for f in b.GetFootprints():
                for p in f.Pads():
                    if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                        continue
                    rad = v.GetWidth(pcbnew.F_Cu) // 2 + pcbnew.FromMM(0.05)
                    if p.HitTest(v.GetPosition(), rad):
                        vip.append((f.GetReference(), p.GetNumber(), [round(x, 3) for x in yz(v.GetPosition())]))
        in1 = sum(1 for t in b.GetTracks() if t.GetClass() != 'PCB_VIA' and t.GetLayer() == pcbnew.In1_Cu)
        filler = pcbnew.ZONE_FILLER(b)
        zs = [z for z in b.Zones() if not z.GetIsRuleArea()]
        filler.Fill(zs)
        planes = {}
        for z in zs:
            for lay in z.GetLayerSet().CuStack():
                fp = z.GetFilledPolysList(lay)
                areas = sorted((round(abs(fp.Outline(i).Area()) / 1e12, 1) for i in range(fp.OutlineCount())), reverse=True)
                planes[f'{b.GetLayerName(lay)}:{z.GetNetname()}'] = {'pieces': len(areas), 'areas_mm2': areas[:6]}
        geo[name] = {
            'courtyard_edge_lt_1mm': edge_bad, 'closest_courtyard_edge_mm': sorted(edge.items(), key=lambda kv: kv[1])[:6],
            'approved_overhangs': sorted(ALLOWED_OVERHANG) if name == 'base' else [],
            'hand_solder_lt_2mm': hs_bad[:20], 'closest_hand_solder_mm': sorted(hs.items(), key=lambda kv: kv[1])[:6],
            'vias': len(vias), 'vias_in_smd_pads': vip, 'tracks_on_In1': in1,
            'tracks': sum(1 for t in b.GetTracks() if t.GetClass() != 'PCB_VIA'),
            'planes': planes}
        if edge_bad or hs_bad or vip or in1:
            rep['problems'].append(f'{name} geometry')
    fixed = {}
    for r in ('J1', 'J2', 'SW1', 'D8', 'D16', 'D17', 'D18'):
        a, c = acc.FindFootprintByReference(r), bb.FindFootprintByReference(r)
        fixed[r] = (a.GetPosition() == c.GetPosition() and a.GetOrientationDegrees() == c.GetOrientationDegrees())
    rep['fixed_interfaces_same_as_accepted'] = fixed
    rep['J3_absent'] = bb.FindFootprintByReference('J3') is None and tb.FindFootprintByReference('J3') is None
    if not all(fixed.values()) or not rep['J3_absent']:
        rep['problems'].append('fixed interfaces')
    rep['geometry'] = geo
    # ---- 6. stack mechanics -------------------------------------------------------------------
    S = st.STACK
    tsegs = outline_segments(tb)

    def parts(b, face):
        out = []
        for f in b.GetFootprints():
            r = f.GetReference()
            if not r:
                continue
            h = st.HEIGHT[f.GetFPID().GetLibItemName().wx_str()]
            c = bbox_yz(f.GetCourtyard(pcbnew.F_CrtYd).BBox())
            out.append((r, h, [face, face + h], c))
        return out
    topp, basep = parts(tb, S['top_F']), parts(bb, S['base_F'])
    tall = max(topp, key=lambda p: p[2][1])
    tol = sum(st.TOL.values())
    under = []
    for r, h, x, c in basep:
        if r in ('J2',) or h <= 0:
            continue
        pts = [(y, z) for y in c[:2] for z in c[2:]] + [((c[0] + c[1]) / 2, (c[2] + c[3]) / 2)]
        if any(poly_contains(tsegs, p) for p in pts) or min(seg_rect(a, e, c) for a, e in tsegs) == 0:
            under.append((r, h, round(S['top_B'] - x[1], 3)))
    under.sort(key=lambda u: u[2])
    tol_under = st.TOL['base_thickness'] + st.TOL['spacer_length'] + st.TOL['solder_standoff'] + st.TOL['top_board_bow']
    env = m.envelopes(m.geometry())
    hdr = {}
    for k in ('J2', 'J2_plug', 'J2_ribbon'):
        x, y, z = env[k][1]
        r = [y[0], y[1], z[0], z[1]]
        ins = any(poly_contains(tsegs, (a, c)) for a in r[:2] for c in r[2:])
        hdr[k] = 0.0 if ins else round(min(seg_rect(a, e, r) for a, e in tsegs), 3)
    g = m.geometry()
    slab = []
    ys = sorted({p[0] for s in tsegs for p in s})
    for y0, y1 in zip(ys, ys[1:]):
        mid = (y0 + y1) / 2
        zz = sorted(a[1] for a, e in tsegs if a[1] == e[1] and min(a[0], e[0]) < mid < max(a[0], e[0]))
        for z0, z1 in zip(zz[::2], zz[1::2]):
            slab.append(('top_slab', ([S['top_B'], S['top_F']], [y0, y1], [z0, z1])))
    solids = slab + [(r, (x, c[:2], c[2:])) for r, h, x, c in topp if h > 0]
    def ov(a, b):
        return all(a[i][0] < b[i][1] and b[i][0] < a[i][1] for i in range(3))
    mech = []
    for yc in g['brackets']['Y_centres_mm']:
        fs = m.fastener_solids(g, yc)
        items = {k: fs[k] for k in ('foot', 'web', 'front_nut', 'side_nut')}
        items.update(fs['tools'])
        for k, box in items.items():
            for nm, s in solids:
                if ov(box, s):
                    mech.append((f'{k}@Y{yc}', nm))
    for nm, s in solids:
        if ov([[0, 20], [0, 128.5], [0, 1.6]], s):
            mech.append(('panel', nm))
    B = st.BOLT
    stack_len = S['thickness'] + S['gap'] + S['thickness'] + B['nut_m']
    rep['stack'] = {
        'X_stack': S, 'tolerances_assumed': st.TOL, 'linear_tolerance_sum': round(tol, 2),
        'tallest_top_part': tall[0], 'top_X_max_nominal': tall[2][1],
        'width_margin_to_X20_nominal': round(20 - tall[2][1], 3),
        'width_margin_worst_linear': round(20 - tall[2][1] - tol, 3),
        'base_parts_under_top_lowest_clearance': under[:6],
        'under_top_min_nominal': under[0][2] if under else None,
        'under_top_min_worst_linear': round(under[0][2] - tol_under, 3) if under else None,
        'top_outline_to_J2_box_plug_ribbon_mm': hdr,
        'collisions_brackets_nuts_tools_panel_vs_top': mech,
        'through_bolt': {
            'hardware_class': 'ISO 7380 M3 x 12 button head under base B, plain 5.0 mm spacer (OD <= 6), DIN 934 M3 nut on top F',
            'head_X_min': round(S['base_B'] - B['head_k'], 2),
            'grip_plus_nut_mm': round(stack_len, 2),
            'thread_exposure_nominal_mm': round(B['length'] - stack_len, 2),
            'thread_exposure_worst_mm': round(B['length'] - B['length_tol'] - stack_len - st.TOL['spacer_length'] - 2 * 0.16, 2),
            'tip_X_nominal': round(S['base_B'] + B['length'], 2),
            'tools': 'hex key on the head from the open base-B side (module out of the rack); nut held by a '
                     'thin-wall 5.5 AF socket, OD <= 8.5 (top tool courtyard r4.25) or flat pliers',
            'opposing_screw_collision': 'not possible: one through bolt per support',
            'supports_YZ': st.STANDOFFS},
        'header_pins': {'part': 'Samtec TSW-110-07-G-D / TSW-103-07-G-D (catalogue F-226 lead style -07)',
                        'plastic_on_base_F': st.PIN['plastic'], 'air_gap_above_plastic': round(S['gap'] - st.PIN['plastic'], 2),
                        'tail_below_base_B': round(st.PIN['tail'] - S['thickness'], 2),
                        'tail_below_base_B_max': st.PIN['tail_below_base_B_max'],
                        'post_end_X': round(S['base_F'] + st.PIN['plastic'] + st.PIN['post'], 2),
                        'post_above_top_F': round(S['base_F'] + st.PIN['plastic'] + st.PIN['post'] - S['top_F'], 2),
                        'post_above_top_F_min': st.PIN['post_above_top_F_min'],
                        'note': 'nominal catalogue lengths; soldered all-pins-loaded current is a prototype gate; '
                                'pins are not supports'},
        'cabled_envelope': 'bare boards end at Z42; the mated J2 plug + ribbon envelope reaches Z50 '
                           '(proposal envelope) - 42 mm is NOT claimed with the cable fitted'}
    if rep['stack']['width_margin_worst_linear'] <= 0 or (under and under[0][2] - tol_under <= 0) \
            or any(v <= 0 for v in hdr.values()) or mech\
            or rep['stack']['header_pins']['tail_below_base_B'] > st.PIN['tail_below_base_B_max']\
            or rep['stack']['header_pins']['post_above_top_F'] < st.PIN['post_above_top_F_min'] or rep['stack']['through_bolt']['thread_exposure_worst_mm'] < 0:
        rep['problems'].append('stack mechanics')
    # ---- 7. converters / thermal --------------------------------------------------------------
    def pads(b, ref):
        return b.FindFootprintByReference(ref).Pads()
    conv = {}
    for ic, ret, sw_l in (('U2', 'GND', 'L1'), ('U3', 'GND', 'L2'), ('U4', 'N12_RAW', 'L3')):
        icp = {p.GetNumber(): p for p in pads(tb, ic)}
        vin = [bbox_yz(p.GetBoundingBox()) for p in icp.values() if p.GetNetname() == 'VIN']
        swn = next(p.GetNetname() for p in icp.values() if 'SW' in p.GetNetname())
        fbn = next(p.GetNetname() for p in icp.values() if 'FB' in p.GetNetname())
        btn = next(p.GetNetname() for p in icp.values() if 'BST' in p.GetNetname() or 'BOOT' in p.GetNetname())
        caps, fbsw, boot = [], [], []
        swcu = [bbox_yz(p.GetBoundingBox()) for f in tb.GetFootprints() for p in f.Pads() if p.GetNetname() == swn]
        for f in tb.GetFootprints():
            r = f.GetReference()
            ns = {p.GetNetname() for p in f.Pads()}
            if r.startswith('C') and 'VIN' in ns and ret in ns:
                caps.append((r, round(min(gap(bbox_yz(p.GetBoundingBox()), v) for p in f.Pads() if p.GetNetname() == 'VIN' for v in vin), 2)))
            if r != ic and fbn in ns:
                fbsw.append((r, round(min(gap(bbox_yz(p.GetBoundingBox()), s) for p in f.Pads() if p.GetNetname() == fbn for s in swcu), 2)))
            if r != ic and btn in ns:
                bp = [bbox_yz(p.GetBoundingBox()) for p in icp.values() if p.GetNetname() == btn]
                boot.append((r, round(min(gap(bbox_yz(p.GetBoundingBox()), q) for p in f.Pads() if p.GetNetname() == btn for q in bp), 2)))
        caps.sort(key=lambda t: t[1])
        conv[ic] = {'input_caps_VIN_pad_gap_mm': caps, 'BOOT_cap_gap_mm': boot, 'FB_pad_gap_to_SW_copper_mm': fbsw}
    rep['converters'] = conv
    therm = {}
    for b, r, pad, want in (('top', 'U4', '9', 'N12_RAW'), ('base', 'Q4', '2', '-12V'), ('base', 'U5', '21', 'GND'),
                            ('top', 'U6', '21', 'GND'), ('top', 'U7', '21', 'GND')):
        f = (tb if b == 'top' else bb).FindFootprintByReference(r)
        got = {p.GetNetname() for p in f.Pads() if p.GetNumber() == pad}
        therm[f'{r}.{pad}'] = {'board': b, 'net': sorted(got), 'expected': want, 'ok': got == {want}}
        if got != {want}:
            rep['problems'].append(f'thermal net {r}')
    rep['thermal_terminals'] = therm
    out = MOD / 'docs/stack-r2/validation.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1) + '\n')
    print(json.dumps({'problems': rep['problems'], 'erc': rep['erc'],
                      'drc': {k: (v['violations'], v['unconnected'], v['parity']) for k, v in rep['drc'].items()},
                      'equal': rep['interconnect_equivalence']['equal'],
                      'stack': {k: rep['stack'][k] for k in ('width_margin_worst_linear', 'under_top_min_nominal',
                                                             'under_top_min_worst_linear', 'top_outline_to_J2_box_plug_ribbon_mm',
                                                             'collisions_brackets_nuts_tools_panel_vs_top')}}, indent=0))


if __name__ == '__main__':
    main()
