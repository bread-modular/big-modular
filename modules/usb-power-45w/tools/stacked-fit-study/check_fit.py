#!/usr/bin/env python3
"""Independent checks for the stacked two-PCB fit study (study only).

Inputs: docs/stacked-fit-study/{model.json, placement-manifest.json, boards/*}, the accepted
hierarchy root (read-only, fresh ERC + XML netlist into a scratch dir) and the accepted board.
Output: docs/stacked-fit-study/validation.json (+ raw native reports in the scratch dir).

  python3 -B modules/usb-power-45w/tools/stacked-fit-study/check_fit.py --scratch <dir>
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[1]
DOC = MOD / 'docs' / 'stacked-fit-study' / ('' if os.environ.get('STACK_FIT_VARIANT', 'literal') == 'literal'
                                          else 'variant-base-protection')
HW = MOD / 'hardware'
sys.path.insert(0, str(MOD / 'tools'))
import mechanics45 as m  # noqa: E402

HS = 2.0
EDGE = 1.0
STROKE = 0.025


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout[-2000:], r.stderr[-2000:]


def poly_contains(poly, y, z):
    ins = False
    for (ya, za), (yb, zb) in zip(poly, poly[1:] + poly[:1]):
        if (za > z) != (zb > z) and y < ya + (z - za) * (yb - ya) / (zb - za):
            ins = not ins
    return ins


def seg_rect_dist(a, b, r):
    """Min distance from an axis-parallel segment to an axis-aligned rect [y0,y1,z0,z1]."""
    (ya, za), (yb, zb) = a, b
    y0, y1 = sorted((ya, yb))
    z0, z1 = sorted((za, zb))
    dy = max(r[0] - y1, y0 - r[1], 0.0)
    dz = max(r[2] - z1, z0 - r[3], 0.0)
    return math.hypot(dy, dz)


def rect_inside(poly, r):
    return all(poly_contains(poly, y, z) for y in r[:2] for z in r[2:])


def rect_gap(a, b):
    dy = max(a[0] - b[1], b[0] - a[1], 0.0)
    dz = max(a[2] - b[3], b[2] - a[3], 0.0)
    return math.hypot(dy, dz)


def overlap3(a, b):
    return all(a[i][0] < b[i][1] and b[i][0] < a[i][1] for i in range(3))


def outline_poly(edges):
    pts = [tuple(e[0]) for e in edges]
    # edges were written in order by stacked_fit.set_outline (top) / carrier generator (base)
    return pts


def ordered_poly(edges):
    segs = [(tuple(map(lambda v: round(v, 4), e[0])), tuple(map(lambda v: round(v, 4), e[1]))) for e in edges]
    poly = [segs[0][0], segs[0][1]]
    rest = segs[1:]
    while rest:
        for k, (a, b) in enumerate(rest):
            if a == poly[-1]:
                poly.append(b)
                rest.pop(k)
                break
            if b == poly[-1]:
                poly.append(a)
                rest.pop(k)
                break
        else:
            raise SystemExit('open outline')
    return poly[:-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scratch', required=True)
    args = ap.parse_args()
    sc = Path(args.scratch)
    sc.mkdir(parents=True, exist_ok=True)
    model = json.loads((DOC / 'model.json').read_text())
    man = json.loads((DOC / 'placement-manifest.json').read_text())
    st = model['stack']
    rep = {'inputs_sha256_16': {}, 'problems': []}
    for p in [HW / 'usb-power-45w.kicad_sch', HW / 'usb-power-45w.kicad_pcb', HW / 'usb-power-45w.kicad_pro',
              HW / 'usb-power-45w.kicad_dru'] + sorted((DOC / 'boards').glob('*/*.kicad_pcb')):
        rep['inputs_sha256_16'][str(p.relative_to(MOD))] = sha(p)

    # ---- native ERC (accepted root, unchanged) + XML netlist -----------------------------
    erc = sc / 'erc.json'
    rc, _, err = run(['kicad-cli', 'sch', 'erc', '--severity-all', '--format', 'json', '-o', str(erc),
                      str(HW / 'usb-power-45w.kicad_sch')])
    ev = json.loads(erc.read_text())
    nerc = sum(len(s.get('violations', [])) for s in ev.get('sheets', []))
    rep['erc'] = {'violations': nerc, 'rc': rc}
    if nerc:
        rep['problems'].append(f'ERC {nerc}')
    net_xml = sc / 'netlist.xml'
    run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(net_xml),
         str(HW / 'usb-power-45w.kicad_sch')])
    root = ET.parse(net_xml).getroot()
    sch = {}
    for c in root.iter('comp'):
        fields = {f.get('name'): (f.text or '') for f in c.iter('field')}
        sch[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'), 'fields': fields}
    sch_pins = {}
    for n in root.iter('net'):
        name = n.get('name')
        for nd in n.iter('node'):
            sch_pins[(nd.get('ref'), nd.get('pin'))] = name

    # ---- native DRC per candidate board ---------------------------------------------------
    rep['drc'] = {}
    for name in ('base', 'top'):
        pcb = DOC / 'boards' / name / f'usb-power-45w-{name}.kicad_pcb'
        out = sc / f'drc-{name}.json'
        rc, _, err = run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', str(out), str(pcb)])
        d = json.loads(out.read_text())
        kinds = {}
        for v in d.get('violations', []):
            kinds.setdefault(f"{v['severity']}:{v['type']}", []).append(
                ' | '.join(i.get('description', '') for i in v.get('items', []))[:160])
        rep['drc'][name] = {
            'rc': rc, 'violations': len(d.get('violations', [])),
            'unconnected_items': len(d.get('unconnected_items', [])),
            'schematic_parity': 'not run (candidate basename has no schematic); see manifest parity',
            'by_type': {k: len(v) for k, v in kinds.items()},
            'examples': {k: v[:6] for k, v in kinds.items()}}

    # ---- partition / field / pin parity ---------------------------------------------------
    parts = model['parts']
    study = [p for p in parts if p['ref'] and not p['ref'].startswith(('X', 'MH'))]
    refs = [p['ref'] for p in study]
    dup = sorted({r for r in refs if refs.count(r) > 1})
    pads = {}
    for p in study:
        for q in p['pads']:
            if q['num']:
                pads.setdefault((p['ref'], q['num']), set()).add(q['net'])
    pad_bad = []
    for (r, n), nets in pads.items():
        sn = sch_pins.get((r, n))
        bn = next(iter(nets))
        if len(nets) != 1:
            pad_bad.append((r, n, sorted(nets), sn))
        elif sn is None:
            if not bn.startswith('unconnected-') and bn:
                pad_bad.append((r, n, bn, 'not in netlist'))
        elif sn.replace('/', '{slash}') != bn and sn != bn:
            pad_bad.append((r, n, bn, sn))
    missing_pins = sorted(k for k in sch_pins if k[0] in sch and k not in pads)
    val_bad = [p['ref'] for p in study if sch.get(p['ref'], {}).get('value') != p['value']]
    fp_bad = [p['ref'] for p in study if sch.get(p['ref'], {}).get('footprint', '').split(':')[-1] != p['fp']]
    rep['parity'] = {
        'schematic_refs': len(sch), 'refs_assigned_present': len(refs), 'duplicates': dup,
        'missing_refs': sorted(set(sch) - set(refs)), 'extra_refs': sorted(set(refs) - set(sch)),
        'per_board': {b: sum(1 for p in study if p['board'] == b) for b in ('base', 'top')},
        'pad_net_mismatches': pad_bad[:20], 'n_pad_net_mismatches': len(pad_bad),
        'netlist_pins_without_pad': missing_pins[:20],
        'value_mismatches': val_bad, 'footprint_mismatches': fp_bad,
        'added_parts_counted_separately': sorted(p['ref'] or '(carrier hole)' for p in parts
                                                 if not p['ref'] or p['ref'].startswith(('X', 'MH'))),
        'note': 'refs_assigned_present counts board membership, NOT placement; see geometry.*.unplaced_refs. '
                'Net-(U4-RT/SYNC) {slash} escape normalised.'}
    # copied fields + footprint-local pad geometry vs the ACCEPTED board, and BOM fields vs the netlist
    acc = model['accepted_sig']
    sig_bad, fld_bad = [], []
    for p in study:
        a, c = acc.get(p['ref']), p['sig']
        if a is None:
            sig_bad.append((p['ref'], 'not on accepted board'))
            continue
        for k in ('fpid', 'attributes', 'fields', 'pads', 'dnp', 'exclude_from_bom', 'exclude_from_pos'):
            if a[k] != c[k]:
                sig_bad.append((p['ref'], k))
        for k, v in sch.get(p['ref'], {}).get('fields', {}).items():
            if k in ('Footprint', 'Datasheet', 'Description'):
                continue
            if k in c['fields'] and c['fields'][k] != v:
                fld_bad.append((p['ref'], k, c['fields'][k], v))
    nc_pins = sorted(k for k, n in sch_pins.items() if n.startswith('unconnected-'))
    nc_bad = [k for k in nc_pins if next(iter(pads.get(k, {''}))) != sch_pins[k]]
    field_names = sorted({k for p in study for k in p['sig']['fields']})
    rep['parity'].update({
        'accepted_board_signature_mismatches': sig_bad,
        'checked_signature': 'FPID, footprint attributes, DNP/BOM/POS flags, every footprint field '
                             '(Value, Datasheet, Description, LCSC, MPN, Manufacturer, Note, ...) and every '
                             'pad: number, type, shape, footprint-local position, size, drill, layer set',
        'field_names_checked': field_names,
        'netlist_field_mismatches': fld_bad,
        'nc_pins_in_netlist': len(nc_pins), 'nc_pin_mismatches': nc_bad,
        'refs_with_LCSC': sum(1 for p in study if p['sig']['fields'].get('LCSC')),
        'refs_with_MPN': sum(1 for p in study if p['sig']['fields'].get('MPN'))})
    if dup or rep['parity']['missing_refs'] or rep['parity']['extra_refs'] or pad_bad or val_bad or fp_bad \
            or missing_pins or sig_bad or fld_bad or nc_bad:
        rep['problems'].append('partition parity')

    # ---- interconnect logical join --------------------------------------------------------
    nets_on = {'base': set(), 'top': set()}
    for p in study:
        for q in p['pads']:
            if q['net'] and not q['net'].startswith('unconnected-'):
                nets_on[p['board']].add(q['net'])
    crossing = sorted(nets_on['base'] & nets_on['top'])
    conn = {}
    for p in parts:
        if p['ref'].startswith('X'):
            for q in p['pads']:
                conn.setdefault(p['ref'][2], {}).setdefault(p['board'], {})[q['num']] = (q['net'], q['box'])
    join_bad, carried = [], set()
    for k, sides in conn.items():
        for num, (net, box) in sides['base'].items():
            tnet, tbox = sides['top'][num]
            if net != tnet or max(abs(a - b) for a, b in zip(box, tbox)) > 1e-3:
                join_bad.append((k, num, net, tnet))
            carried.add(net)
    pins_per_net = {}
    for k, sides in conn.items():
        for num, (net, _) in sides['base'].items():
            pins_per_net[net] = pins_per_net.get(net, 0) + 1
    budget = man['pin_budget_A']
    currents = {'VIN': 4.748, '+12V': 2.971, '+5V': 2.971, '-12V': 1.143, 'N12_RAW': 1.143, 'GND': 6.0}
    currents = {n: i for n, i in currents.items() if n in crossing}
    rep['interconnect'] = {
        'crossing_nets': crossing, 'carried_nets': sorted(carried),
        'crossing_not_carried': sorted(set(crossing) - carried),
        'carried_not_needed': sorted(carried - set(crossing)),
        'pin_alignment_or_net_mismatch': join_bad, 'pins_per_net': pins_per_net,
        'current_screen_A': {n: {'I_screen': i, 'pins': pins_per_net.get(n, 0),
                                 'A_per_pin': round(i / max(pins_per_net.get(n, 1), 1), 3),
                                 'within_assumed_budget': i / max(pins_per_net.get(n, 1), 1) <= budget}
                             for n, i in currents.items()},
        'note': f'{budget} A/pin is an ASSUMED conservative design budget for 0.64 mm square pins in a '
                'stacked, poorly ventilated gap, not a vendor rating; GND worst case assumes no '
                'cancellation of input return and load returns.'}
    if rep['interconnect']['crossing_not_carried'] or join_bad:
        rep['problems'].append('interconnect join')

    # ---- geometry: outline, edge, HS, courtyard overlaps ----------------------------------
    polys = {b: ordered_poly(model[f'{b}_edges']) for b in ('base', 'top')}
    allowed_overhang = {'J1', 'SW1', 'D8', 'D16', 'D17', 'D18'}
    geo = {}
    for b in ('base', 'top'):
        poly = polys[b]
        segs = list(zip(poly, poly[1:] + poly[:1]))
        bp = [p for p in parts if p['board'] == b and p['ref']]
        unplaced, edge_viol, edge_min = [], [], {}
        for p in bp:
            c = p['court']
            cg = [c[0] - STROKE, c[1] + STROKE, c[2] - STROKE, c[3] + STROKE]
            if not rect_inside(poly, c) and p['ref'] not in allowed_overhang:
                unplaced.append(p['ref'])
                continue
            dmin = min(seg_rect_dist(a, bb, cg) for a, bb in segs) if rect_inside(poly, cg) else 0.0
            edge_min[p['ref']] = round(dmin, 3)
            if dmin < EDGE - 1e-6 and p['ref'] not in allowed_overhang:
                edge_viol.append((p['ref'], round(dmin, 3)))
        placed = [p for p in bp if p['ref'] not in unplaced]
        over = []
        for i, a in enumerate(placed):
            for bb in placed[i + 1:]:
                ca, cb = a['court'], bb['court']
                if ca[0] < cb[1] and cb[0] < ca[1] and ca[2] < cb[3] and cb[2] < ca[3]:
                    if not (a['ref'].startswith('MH') or bb['ref'].startswith('MH')):
                        over.append((a['ref'], bb['ref']))
        # hand-solder: SMD pads vs THT/hand-soldered pads (bbox distance <= true distance)
        hs_src = [(p['ref'], q['box']) for p in placed for q in p['pads']
                  if (p['ref'] in ('J2', 'J3', 'D8', 'D16', 'D17', 'D18', 'SW1') or p['ref'].startswith('X')
                      or (p['ref'] == 'J1' and not q['smd'])) and not q['npth']]
        hs_min, hs_viol = {}, []
        for p in placed:
            if p['ref'] in ('SW1', 'J1') or p['ref'].startswith(('X', 'MH')):
                continue
            for q in p['pads']:
                if not q['smd']:
                    continue
                for r, bx in hs_src:
                    dd = rect_gap(q['box'], bx)
                    key = f'{p["ref"]}-{r}'
                    if dd < hs_min.get(key, 99):
                        hs_min[key] = round(dd, 3)
                    if dd < HS - 1e-6:
                        hs_viol.append((p['ref'], q['num'], r, round(dd, 3)))
        closest = sorted(hs_min.items(), key=lambda kv: kv[1])[:6]
        geo[b] = {'refs_on_board': len(bp), 'placed_inside_outline': len(placed),
                  'unplaced_refs': sorted(unplaced),
                  'courtyard_edge_violations_lt_1mm': edge_viol,
                  'closest_courtyard_edge_mm': sorted(edge_min.items(), key=lambda kv: kv[1])[:6],
                  'courtyard_overlaps_bbox': over, 'hand_solder_violations_lt_2mm': hs_viol[:20],
                  'closest_hand_solder_mm': closest,
                  'approved_overhangs_kept_at_same_geometry': sorted(allowed_overhang) if b == 'base' else []}
        if edge_viol or over or hs_viol:
            rep['problems'].append(f'{b} geometry')
        if unplaced:
            rep['problems'].append(f'{b} unplaced {len(unplaced)}')
    rep['geometry'] = geo

    # fixed base interface parts unchanged vs accepted board positions
    accpos = {r: tuple(v) for r, v in model['accepted_fixed'].items()}
    fixed = {}
    for p in parts:
        if p['board'] == 'base' and p['ref'] in ('J1', 'J2', 'J3', 'SW1', 'D8', 'D16', 'D17', 'D18'):
            a = accpos.get(p['ref'])
            fixed[p['ref']] = {'pos_YZ': p['pos'], 'rot': p['rot'],
                               'same_as_accepted': a is not None and abs(a[0] - p['pos'][0]) < 1e-3
                               and abs(a[1] - p['pos'][1]) < 1e-3 and abs(a[2] - p['rot']) < 1e-3}
    rep['fixed_interfaces'] = fixed
    if not all(v['same_as_accepted'] for v in fixed.values()):
        rep['problems'].append('fixed interface moved')

    # ---- 3D / width / tolerance -----------------------------------------------------------
    tol = man['tolerances_assumed']
    tol_lin = sum(tol.values())
    topp = [p for p in parts if p['board'] == 'top' and p['ref'] and p['ref'] not in geo['top']['unplaced_refs']]
    tall = max(topp, key=lambda p: p['X'][1])
    margin_nom = 20.0 - tall['X'][1]
    width = {'tallest_top_part': tall['ref'], 'top_X_max_nominal': tall['X'][1],
             'margin_to_X20_nominal': round(margin_nom, 3),
             'margin_worst_case_linear': round(margin_nom - tol_lin, 3),
             'tolerances_assumed': tol,
             'status': 'CONDITIONAL MODEL SCREEN, not a tolerance proof',
             'note': 'Can 8.0 is an assumed envelope: BOM can 6.3x8 class, 7.7 generic model, so 8.0 '
                     'is not a manufacturer max incl. base plate/solder. Tolerances are assumed '
                     'linear-sum values without vendor data; no statistical claim. Neighbour panel '
                     'normally starts at X20.32 (not counted).'}
    if width['margin_worst_case_linear'] <= 0:
        rep['problems'].append('width')
    # base parts under the top board
    tpoly = polys['top']
    under = []
    for p in parts:
        if p['board'] != 'base' or not p['ref'] or p['height'] <= 0:
            continue
        b = p['body']
        corners_in = any(poly_contains(tpoly, y, z) for y in b[:2] for z in b[2:]) or \
            poly_contains(tpoly, (b[0] + b[1]) / 2, (b[2] + b[3]) / 2)
        if corners_in or (p['ref'] in ('J2', 'J3')):
            clr = st['top_B'] - p['X'][1]
            under.append((p['ref'], p['fp'][:22], p['X'][1], round(clr, 3)))
    under.sort(key=lambda t: t[3])
    hdr_overlap = [u for u in under if u[0] in ('J2', 'J3')]
    # proper check: does the top outline overlap J2/J3/plug YZ envelopes at all?
    env = m.envelopes(m.geometry())
    hdr = {}
    for k in ('J2', 'J3', 'J2_plug', 'J3_plug', 'J2_ribbon', 'J3_ribbon'):
        x, y, z = env[k][1]
        r = [y[0], y[1], z[0], z[1]]
        segs = list(zip(tpoly, tpoly[1:] + tpoly[:1]))
        inside = any(poly_contains(tpoly, yy, zz) for yy in r[:2] for zz in r[2:])
        hdr[k] = {'YZ_clearance_from_top_outline_mm': 0.0 if inside else round(min(seg_rect_dist(a, b, r) for a, b in segs), 3),
                  'X': x}
    under = [u for u in under if u[0] not in ('J2', 'J3')]
    tol_under = tol['base_thickness'] + tol['standoff_length'] + tol['solder_standoff'] + tol['top_board_bow']
    rep['stack'] = {
        'X_stack': st, 'width': width,
        'base_parts_under_top_board_lowest_clearance': under[:8],
        'base_under_top_min_clearance_nominal': under[0][3] if under else None,
        'base_under_top_min_clearance_worst_linear': round(under[0][3] - tol_under, 3) if under else None,
        'top_outline_vs_J2J3_plug_ribbon': hdr,
    }
    if under and under[0][3] - tol_under <= 0:
        rep['problems'].append('base part hits top board')
    if any(v['YZ_clearance_from_top_outline_mm'] <= 0 for v in hdr.values()):
        rep['problems'].append('top board intrudes on headers/plugs')
    # brackets, nuts, tool paths vs top board slab and top parts
    g = m.geometry()
    mech = []
    slab_boxes = []
    # approximate top slab by rectangles of its outline (axis-parallel decomposition by Y bands)
    ys = sorted({v[0] for v in tpoly})
    for y0, y1 in zip(ys, ys[1:]):
        mid = (y0 + y1) / 2
        zs = sorted(a[1] for a, b in zip(tpoly, tpoly[1:] + tpoly[:1])
                    if a[1] == b[1] and min(a[0], b[0]) < mid < max(a[0], b[0]))
        for z0, z1 in zip(zs[::2], zs[1::2]):
            slab_boxes.append(([st['top_B'], st['top_F']], [y0, y1], [z0, z1]))
    solids = [('top_slab', s) for s in slab_boxes]
    for p in topp:
        b = p['body']
        solids.append((p['ref'], (p['X'], b[:2], b[2:])))
    for yc in g['brackets']['Y_centres_mm']:
        fs = m.fastener_solids(g, yc)
        items = {k: fs[k] for k in ('foot', 'web', 'front_nut', 'side_nut')}
        items.update({k: v for k, v in fs['tools'].items()})
        side_tip = g['brackets']['outer_X_mm'][0] + max(g['brackets']['side_head_recess_mm']) + g['brackets']['side_length_mm']
        items['side_screw'] = [[g['brackets']['outer_X_mm'][0], side_tip], [yc - 1.5, yc + 1.5],
                               [g['brackets']['side_hole_Z_mm'] - 1.5, g['brackets']['side_hole_Z_mm'] + 1.5]]
        for k, box in items.items():
            for nm, s in solids:
                if overlap3(box, s):
                    mech.append((f'{k}@Y{yc}', nm))
    # panel and rails vs top board/parts
    panel = [[0, 20], [0, 128.5], [0, 1.6]]
    for nm, s in solids:
        if overlap3(panel, s):
            mech.append(('panel', nm))
    rep['stack']['mechanical_collisions_top_vs_brackets_nuts_tools_panel'] = mech
    if mech:
        rep['problems'].append('mechanical collision')
    # standoffs: through-height and screw heads
    rep['stack']['standoffs'] = {
        'positions_YZ': man['standoffs_YZ'], 'type': 'M3 x 5.0 F-F hex, 5.5 AF (6.35 circ.), nylon PA66 '
        'preferred; metal allowed only with the r4.0 all-layer copper keep-out kept',
        'screws': 'ISO 7380 M3x4 button head both sides: k 1.65 <= 1.8 base-underside limit; '
                  '2.4 mm engagement each side, 0.2 mm apart inside the 5.0 standoff',
        'base_underside_head_X': round(st['base_B'] - 1.65, 3), 'top_head_X': round(st['top_F'] + 1.65, 3)}
    # two opposing M3x4 screws in a 5.0 F-F standoff: nominal and worst-case tip gap (assumed tolerances)
    scr_l, scr_tol, so_tol, brd_tol = 4.0, 0.24, tol['standoff_length'], tol['base_thickness']
    eng_nom = scr_l - st['thickness']
    tip_nom = st['gap'] - 2 * eng_nom
    tip_min = (st['gap'] - so_tol) - 2 * ((scr_l + scr_tol) - (st['thickness'] - brd_tol))
    rep['stack']['standoff_screw_tips'] = {
        'engaged_each_side_nom_mm': round(eng_nom, 2), 'tip_gap_nom_mm': round(tip_nom, 2),
        'tip_gap_worst_mm': round(tip_min, 2),
        'assumed': f'screw length +/-{scr_tol} (ISO 7380 l=4 js15 class, assumed), standoff '
                   f'+/-{so_tol}, board -{brd_tol}; thread assumed through and unobstructed',
        'verdict': 'OK' if tip_min > 0 else 'HARDWARE SELECTION GATE (unqualified): fastener length, '
                   'thread engagement and screw-tip clearance are not qualified; the assumed M3x4 pair '
                   'can meet at worst case. No replacement screw/standoff is approved here; a through '
                   'bolt + plain 5 mm spacer + nut is a possible later option, not modelled or validated'}
    if tip_min <= 0:
        rep['problems'].append('standoff screw tips (hardware selection gate)')
    rep['stack']['interconnect_pins'] = {
        'selected_envelope': 'standard 2.54 mm male header, 0.64 mm square pin, 2.5 mm plastic seated on '
                             'base F, 3.0 mm tail / 6.0 mm post (11.5 mm overall)',
        'base_tail_below_B_mm': round(3.0 - st['thickness'], 2),
        'post_above_top_F_mm': round(6.0 - (st['gap'] - 2.5) - st['thickness'], 2),
        'air_gap_above_plastic_mm': round(st['gap'] - 2.5, 2),
        'note': 'Pin length tolerance and exact MPN not verified here; any header whose tail stays <= 1.8 '
                'below base B and whose post clears top F by >= 0.5 fits this envelope.'}

    # ---- converter packing metrics ----------------------------------------------------------
    byref = {p['ref']: p for p in parts if p['ref']}
    conv = {}
    for ic, ret, l in (('U2', 'GND', 'L1'), ('U3', 'GND', 'L2'), ('U4', 'N12_RAW', 'L3')):
        icp = byref[ic]
        vin_pads = [q['box'] for q in icp['pads'] if q['net'] == 'VIN']
        caps = []
        for p in parts:
            if p['board'] == 'top' and p['ref'].startswith('C'):
                nets = {q['net'] for q in p['pads']}
                if 'VIN' in nets and ret in nets:
                    cv = [q['box'] for q in p['pads'] if q['net'] == 'VIN']
                    caps.append((p['ref'], round(min(rect_gap(a, b) for a in cv for b in vin_pads), 2)))
        caps.sort(key=lambda t: t[1])
        fbnet = next((q['net'] for q in icp['pads'] if 'FB' in q['net']), None)
        fb = [p for p in parts if p['board'] == 'top' and any(q['net'] == fbnet for q in p['pads']) and p['ref'] != ic]
        lc = byref[l]['court']
        swnet = next(q['net'] for q in icp['pads'] if q['net'].endswith('-SW)'))
        swcu = [q['box'] for pp in parts if pp['board'] == icp['board'] for q in pp['pads'] if q['net'] == swnet]
        fbsw = [(p['ref'], round(min(rect_gap(q['box'], b) for q in p['pads'] if q['net'] == fbnet for b in swcu), 2))
                for p in fb]
        bnet = next((q['net'] for q in icp['pads'] if 'BOOT' in q['net'] or 'BST' in q['net']), None)
        bpin = [q['box'] for q in icp['pads'] if q['net'] == bnet]
        bcap = [(p['ref'], round(min(rect_gap(q['box'], b) for q in p['pads'] if q['net'] == bnet for b in bpin), 2))
                for p in parts if p['ref'] != ic and any(q['net'] == bnet for q in p['pads'])]
        conv[ic] = {'FB_net_pad_gap_to_SW_net_copper_mm': fbsw, 'BOOT_cap_pad_gap_mm': bcap,
                    'input_caps_VIN_pad_gap_mm': caps,
                    'nearest_input_cap_mm': caps[0][1] if caps else None,
                    'within_2_3mm': [c for c in caps if c[1] <= 3.0],
                    'FB_parts_gap_to_inductor_courtyard_mm': [(p['ref'], round(rect_gap(p['court'], lc), 2))
                                                              for p in fb],
                    'board': icp['board']}
    rep['converters'] = conv
    def hot(n):
        b = n.split('/')[-1]
        if b == 'N12_RAW':     # reported separately: DC rail transfer, not a hot-loop/sense split
            return False
        return any(k in b for k in ('SW', 'BST', 'BOOT', 'FB', '_RAW', 'SENSE')) or b.startswith('N_') \
            or b.startswith('Net-(U2') or b.startswith('Net-(U3') or b.startswith('Net-(U4')
    split = [n for n in rep['interconnect']['crossing_nets'] if hot(n)]
    rep['hot_loop_or_kelvin_nets_crossing'] = split
    rep['raw_dc_rail_crossing'] = [n for n in rep['interconnect']['crossing_nets'] if n == 'N12_RAW']
    # negative protection core: all on one board and compact around U8 (Kelvin locality screen)
    core = ['Q4', 'R48', 'R49', 'R89', 'U8', 'D19', 'D20', 'R57', 'U16', 'U17']
    u8 = byref['U8']['court']
    rep['negative_protection_block'] = {
        'boards': sorted({byref[r]['board'] for r in core}),
        'courtyard_gap_to_U8_mm': {r: round(rect_gap(byref[r]['court'], u8), 2) for r in core if r != 'U8'},
        'R48_R49_courtyard_gap_mm': round(rect_gap(byref['R48']['court'], byref['R49']['court']), 2),
        'note': 'Courtyard bbox gaps only; Kelvin routing (R48/R49 sense to U8 SENSE via R89) not proven.'}
    if len(rep['negative_protection_block']['boards']) > 1:
        rep['problems'].append('negative protection block split')
    if split:
        rep['problems'].append('hot loop split')

    # ---- thermal plan facts -------------------------------------------------------------------
    # Exact known thermal terminals (datasheet/footprint), checked against the board pad nets below.
    # No heuristic pad-number guess: U2/U3 have no exposed pad, D10 has no dedicated EP.
    THERMAL = {
        'D10': ('no dedicated EP; both terminals carry the heat', [('1', 'EF_IN'), ('2', 'VPD')]),
        'U5': ('exposed pad', [('21', 'GND')]),
        'U6': ('exposed pad', [('21', 'GND')]),
        'U7': ('exposed pad', [('21', 'GND')]),
        'U4': ('exposed pad (negative converter: NOT GND)', [('9', 'N12_RAW')]),
        'Q4': ('drain / tab', [('2', '-12V')]),
        'U2': ('no exposed pad', []),
        'U3': ('no exposed pad', []),
    }
    th = {}
    for r, (kind, terms) in THERMAL.items():
        p = byref.get(r)
        if not p:
            continue
        so = [math.hypot((p['court'][0] + p['court'][1]) / 2 - y, (p['court'][2] + p['court'][3]) / 2 - z)
              for y, z in man['standoffs_YZ']]
        board_nets = {(q['num'], q['net'].rsplit('/', 1)[-1]) for q in p['pads']}  # hier. names
        th[r] = {'board': p['board'], 'pos_YZ': p['pos'], 'thermal_terminal': kind,
                 'thermal_pad_net': [f'pad {n} = {net}' for n, net in terms],
                 'thermal_pad_net_matches_board': all(t in board_nets for t in terms),
                 'nearest_standoff_centre_mm': round(min(so), 2),
                 'faces_inner_gap': p['board'] == 'base'}
        if not th[r]['thermal_pad_net_matches_board']:
            rep['problems'].append(f'thermal pad net mismatch {r}')
    rep['thermal_facts'] = th
    # ---- compact pass/fail gates ------------------------------------------------------------
    unpl = geo['base']['unplaced_refs'] + geo['top']['unplaced_refs']
    nb = rep['negative_protection_block']
    def pf(ok):
        return 'PASS' if ok else 'FAIL'
    rep['gates'] = {
        'all_217_placed_inside_outlines': pf(not unpl) + (f' ({len(unpl)} unplaced: {unpl})' if unpl else ''),
        'ERC_0': pf(nerc == 0),
        'DRC_errors_0': pf(all(v['by_type'].get(k, 0) == 0 for v in rep['drc'].values()
                               for k in v['by_type'] if k.startswith('error'))),
        'parity_refs_pads_nets_NC_fields_padgeometry': pf('partition parity' not in rep['problems']),
        'interconnect_join': pf('interconnect join' not in rep['problems']),
        'edge_1mm_and_handsolder_2mm_and_no_overlap': pf(not any(f'{b} geometry' in rep['problems'] for b in geo)),
        'fixed_interfaces_unchanged': pf('fixed interface moved' not in rep['problems']),
        'no_hot_loop_or_kelvin_net_crossing': pf(not split),
        'U2_U3_U4_input_cap_le_3mm': pf(all((v['nearest_input_cap_mm'] or 99) <= 3.0 for v in conv.values())),
        'FB_net_ge_1mm_from_SW_copper_and_FB_parts_ge_1mm_off_inductor_courtyard': pf(all(
            min(g for _, g in v['FB_net_pad_gap_to_SW_net_copper_mm']) >= 1.0 and
            min(g for _, g in v['FB_parts_gap_to_inductor_courtyard_mm']) >= 1.0 for v in conv.values())),
        'neg_protection_block_one_board': pf(len(nb['boards']) == 1),
        'width_margin_positive_under_assumed_tolerances (model screen)': pf(width['margin_worst_case_linear'] > 0),
        'standoff_screw_tips': rep['stack']['standoff_screw_tips']['verdict'],
        'mechanical_collisions_0': pf(not mech),
    }
    (DOC / 'validation.json').write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep['gates'], indent=0))
    print(json.dumps({'problems': rep['problems'], 'drc': {k: (v['violations'], v['unconnected_items'], v['by_type'])
                                                           for k, v in rep['drc'].items()},
                      'erc': rep['erc'], 'width': width, 'parity_missing': rep['parity']['missing_refs'],
                      'n_pad_bad': len(pad_bad), 'under': under[:4], 'hdr': hdr, 'mech': mech[:10],
                      'geo': {b: (v['unplaced_refs'], v['courtyard_edge_violations_lt_1mm'][:5],
                                  v['courtyard_overlaps_bbox'][:5], v['hand_solder_violations_lt_2mm'][:5],
                                  v['closest_hand_solder_mm'][:3]) for b, v in geo.items()},
                      'conv': {k: (v['nearest_input_cap_mm'], v['within_2_3mm']) for k, v in conv.items()},
                      'cross': rep['interconnect']['crossing_nets'],
                      'notcarried': rep['interconnect']['crossing_not_carried'],
                      'extra': rep['interconnect']['carried_not_needed']}, indent=0))


if __name__ == '__main__':
    main()
