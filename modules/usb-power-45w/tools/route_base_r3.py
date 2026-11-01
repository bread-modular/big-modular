#!/usr/bin/env python3
"""R3 manual divide-and-conquer routing of the R2 BASE board, one reviewed batch at a time.

  python3 -B tools/route_base_r3.py apply <batch>            # backup -> shared plan/apply -> write back -> DRC/audit
  python3 -B tools/route_base_r3.py ops <batch> <out.json>   # emit the shared `pcb plan` ops only
  python3 -B tools/route_base_r3.py render <out.png> [x0 x1 y0 y1] [layers]   # native-frame view
  python3 -B tools/route_base_r3.py audit                    # DRC + parity + geometry audit of the board

No router and no path finding: every track, via and zone in BATCHES is written by hand in NATIVE
board coordinates (mm, KiCad x right, y toward the panel edge Y102.275) and reviewed before it is
applied. The shared `opt/kicad-tools` pcb plan/apply does the edit on a candidate (it refuses
shorts, clearance faults and XML parity changes); tools/route_r2.writeback() then writes the
opens-only draft back to the canonical board with the board's own 3D-model tokens and proves
that every footprint and every earlier copper item is unchanged and only this batch was added.
Raw files go to the ignored research/r3-base/; the board is backed up to /tmp before each batch.
Batches only ADD copper; earlier copper is removed only by explicit `delete` entries (by UUID).

Layer plan (base): F signal + local power pours; In1 solid GND (no tracks); In2 = always-on
V3V3 logic plane over the logic/negative area plus a separate VIN area (U5 out -> XB1), each
one piece; B signal + power pours + D10/U5/Q4 heat spreading.
"""
import collections
import json
import math
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
REPO = MOD.parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import route_r2  # noqa: E402  (shared plan/apply wrapper, writeback proof)

BOARD = route_r2.st.board_file('base')
CFG = MOD / 'tools/kicad-project-base.json'
RES = MOD / 'research/r3-base'
V6 = (0.6, 0.3)
from route_base_r3_batches import BATCHES  # noqa: E402  (hand-written batch data)


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/usb-power-45w/r3-base/{key}'))


_NETS = {}


def net(short):
    if not _NETS:
        import pcbnew
        b = pcbnew.LoadBoard(str(BOARD))
        _NETS['_'] = [str(n) for n in b.GetNetsByName().keys()]
    names = _NETS['_']
    for cand in (short, '/' + short, f'Net-({short})'):
        if cand in names:
            return cand
    hits = [n for n in names if n.startswith(f'Net-({short}')]
    assert len(hits) == 1, (short, hits)
    return hits[0]


_PADU = {}


def pad_uuid(ref, num, at):
    """UUID of the pad `ref`.`num` nearest `at` (for duplicated pad numbers: EP vias, shell lugs)."""
    import pcbnew
    if not _PADU:
        _PADU['b'] = pcbnew.LoadBoard(str(BOARD))
    f = _PADU['b'].FindFootprintByReference(ref)
    best = min((p for p in f.Pads() if p.GetNumber() == num),
               key=lambda p: math.hypot(pcbnew.ToMM(p.GetPosition().x) - at[0], pcbnew.ToMM(p.GetPosition().y) - at[1]))
    return best.m_Uuid.AsString()


def emit(batch):
    spec = BATCHES[batch]
    ops = []
    for ref, at, rot in spec.get('moves', []):       # reviewed placement refinements (recorded reasons)
        if at is not None:
            ops.append({'op': 'move_footprint', 'target': {'ref': ref}, 'at': list(at)})
        if rot is not None:
            ops.append({'op': 'rotate_footprint', 'target': {'ref': ref}, 'rotation_deg': rot})
    for k in spec.get('delete', []):
        kind, key = k
        ops.append({'op': 'delete_item', 'uuid': key if '-' in key and len(key) == 36 else uid(key), 'expected_kind': kind})
    for i, z in enumerate(spec.get('zones', [])):
        layer, n, poly, conn = z[:4]
        ops.append({'op': 'add_zone', 'uuid': uid(f'{batch}/zone/{i}'), 'net': net(n), 'layer': layer,
                    'polygon': [list(p) for p in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.25,
                    'pad_connection': conn})
    for k, (n, at, *size) in spec.get('vias', {}).items():
        d, dr = size[0] if size else V6
        ops.append({'op': 'add_via', 'uuid': uid(f'via/{k}'), 'net': net(n), 'at': list(at),
                    'diameter_mm': d, 'drill_mm': dr})

    def end(e):
        if e[0] == 'pad':
            return {'pad': {'ref': e[1], 'number': e[2]}}
        if e[0] == 'padu':                      # ('padu', ref, num, (x, y))
            return {'uuid': pad_uuid(e[1], e[2], e[3])}
        if e[0] == 'trk':                       # ('trk', 'batch/trk/i', (x, y)[, seg]) branch on a track segment
            t = uid(e[1]) if len(e) < 4 or not e[3] else str(uuid.uuid5(uuid.UUID(uid(e[1])), str(e[3])))
            return {'track': t, 'at': list(e[2])}
        return {'uuid': uid(f'via/{e[1]}')}
    for i, (n, layer, w, a, wps, b) in enumerate(spec.get('tracks', [])):
        ops.append({'op': 'add_polyline', 'uuid': uid(f'{batch}/trk/{i}'), 'net': net(n), 'layer': layer,
                    'width_mm': w, 'start': end(a), 'waypoints': [list(p) for p in wps], 'end': end(b)})
    return {'schema_version': 1, 'operations': ops}


def apply(batch):
    route_r2.st.refuse_replay(f'route_base_r3.py apply {batch}')
    stamp = time.strftime('%H%M%S')
    work = RES / 'route' / f'{batch}-{stamp}'
    work.mkdir(parents=True)
    shutil.copy(BOARD, f'/tmp/usb-power-45w-base-r3-{batch}-{stamp}.kicad_pcb')
    (work / 'ops.json').write_text(json.dumps(emit(batch), indent=1))
    rc, out, err = route_r2.tools('pcb', 'plan', '--config', str(CFG), '--ops', str(work / 'ops.json'), '--allow-draft-opens')
    (work / 'plan.stdout').write_text(out + err)
    try:
        plan_doc = json.loads(out[out.find('{'):out.rfind('}') + 1])
    except ValueError:
        plan_doc = {}
    if plan_doc.get('kind') != 'pcb_edit_plan':
        print('PLAN FAILED rc', rc, out[-2500:], err[-1500:])
        return 1
    planpath = work / 'plan.json'
    planpath.write_text(json.dumps(plan_doc, indent=1))
    cand = Path('/tmp/usbpower45-r3-base') / work.name / 'cand'
    cand.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = route_r2.tools('pcb', 'apply', '--plan', str(planpath), '--ops', str(work / 'ops.json'), '--output', str(cand))
    (work / 'apply.stdout').write_text(out + err)
    if not (cand / 'result.json').exists():
        print('APPLY FAILED rc', rc, (out + err)[-3000:])
        return 1
    shutil.copy(cand / 'result.json', work / 'result.json')
    res = json.loads((cand / 'result.json').read_text())
    print('candidate', res.get('status'), 'parity', res.get('checks', {}).get('parity', {}).get('equal'))
    if res.get('status') not in ('draft', 'accepted'):
        print('errors:', json.dumps(res.get('errors'))[:1500])
        seen = set()

        def walk(o):
            if isinstance(o, dict):
                if o.get('category') and o.get('category') != 'unconnected_items' and 'identity' in o:
                    k = json.dumps(o['identity'], sort_keys=True)
                    if k not in seen:
                        seen.add(k)
                        print('  ', o['category'], o.get('severity'), o['identity']['description'][:70],
                              [(i['description'][:60], i['pos']) for i in o['identity']['items']])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(res)
        return 1
    rc = writeback(cand, work, {m[0] for m in BATCHES[batch].get('moves', [])},
                   {uid(k) if not (len(k) == 36 and k.count('-') == 4) else k for _, k in BATCHES[batch].get('delete', [])})
    if rc:
        return rc
    return audit(work)


def writeback(cand, work, moved, deleted):
    """route_r2.writeback with two explicit allowances: footprints named in the batch's 'moves' may
    change position/rotation only (pads, nets and fields identical), and copper named in 'delete' may
    disappear. Everything else: every footprint identical, every earlier copper item kept."""
    import re
    import pcbnew
    cpcb = next(cand.glob('inputs/**/' + BOARD.name))
    ctext, stext = cpcb.read_text(), BOARD.read_text()
    pat = re.compile(r'\(model "([^"]*)"')
    cm, sm = pat.findall(ctext), pat.findall(stext)
    assert len(cm) == len(sm) and all(Path(a).name == Path(b).name for a, b in zip(cm, sm)), 'model token map'
    it = iter(sm)
    out = pat.sub(lambda m_: '(model "%s"' % next(it), ctext)
    tmp = work / 'writeback.kicad_pcb'
    tmp.write_text(out)
    old, new = pcbnew.LoadBoard(str(BOARD)), pcbnew.LoadBoard(str(tmp))

    def fps(b, pos=True):
        return {f.m_Uuid.AsString(): (f.GetReference(),) + ((f.GetPosition().x, f.GetPosition().y, f.GetOrientationDegrees())
                                                             if pos else ()) +
                (tuple((p.GetNumber(), p.GetNetname()) for p in f.Pads()),
                 tuple(sorted((x.GetName(), x.GetText()) for x in f.GetFields())))
                for f in b.GetFootprints()}
    fo, fn = fps(old), fps(new)
    assert set(fo) == set(fn), 'footprint set changed'
    for k in fo:
        if fo[k][0] in moved:
            assert fps(old, False)[k] == fps(new, False)[k], ('moved footprint changed beyond placement', fo[k][0])
        else:
            assert fo[k] == fn[k], ('footprint changed', fo[k][0])

    def copper(b):
        out_ = {}
        for t in b.GetTracks():
            out_[t.m_Uuid.AsString()] = (t.GetClass(), t.GetNetname(), t.GetStart().x, t.GetStart().y,
                                         t.GetEnd().x, t.GetEnd().y,
                                         t.GetWidth(pcbnew.F_Cu) if t.GetClass() == 'PCB_VIA' else t.GetWidth(), t.GetLayer())
        for z in b.Zones():
            out_[z.m_Uuid.AsString()] = ('ZONE', z.GetNetname(), z.GetFirstLayer(), z.GetIsRuleArea(),
                                         tuple((z.Outline().CVertex(i).x, z.Outline().CVertex(i).y)
                                               for i in range(z.Outline().TotalVertices())))
        return out_
    co, cn = copper(old), copper(new)
    for k, v in co.items():
        if k in deleted:
            assert k not in cn, ('delete not applied', k)
        else:
            assert cn.get(k) == v, ('earlier copper changed', k)
    added = sorted(set(cn) - set(co))
    shutil.copy(tmp, BOARD)
    print('written back:', len(added), 'items added;', len(set(co) & deleted), 'deleted;', len(moved), 'moved;',
          len(cn), 'copper items total')
    (work / 'writeback.json').write_text(json.dumps({'added': len(added), 'deleted': sorted(set(co) & deleted),
                                                     'moved': sorted(moved), 'total': len(cn)}))
    return 0


def drc(out):
    rep = Path(out) / 'drc.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--schematic-parity', '--format', 'json',
                    '-o', str(rep), str(BOARD)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return json.loads(rep.read_text())


def audit(work=None):
    work = Path(work or RES / 'audit' / time.strftime('%H%M%S'))
    work.mkdir(parents=True, exist_ok=True)
    d = drc(work)
    kinds = collections.Counter(f"{v['severity']}:{v['type']}" for v in d['violations'])
    print('DRC', dict(kinds), 'unconnected', len(d['unconnected_items']), 'parity', len(d['schematic_parity']),
          'excluded', sum(1 for v in d['violations'] if v.get('excluded')))
    for v in d['violations'][:25]:
        print('  ', v['type'], v['description'][:70], [(i['description'][:50], i['pos']) for i in v['items']])
    geo = geometry()
    print('GEO', json.dumps({k: v for k, v in geo.items() if k != 'planes'}))
    print('PLANES', json.dumps(geo['planes']))
    unc = collections.Counter()
    for u in d['unconnected_items']:
        unc[u['items'][0]['description'].split('[')[-1].split(']')[0] if '[' in u['items'][0]['description'] else '?'] += 1
    print('OPEN by net', dict(unc.most_common()))
    (work / 'audit.json').write_text(json.dumps({'drc': dict(kinds), 'unconnected': len(d['unconnected_items']),
                                                  'parity': len(d['schematic_parity']), 'geo': geo}, indent=1))
    return 0


def geometry():
    """Vias vs SMD pad copper AND mask opening, tracks on In1, dangling/zero-length/duplicate tracks,
    off-grid ends, plane pieces from filled polygons."""
    import pcbnew
    b = pcbnew.LoadBoard(str(BOARD))
    M = pcbnew.ToMM
    smd = [(f.GetReference(), p) for f in b.GetFootprints() for p in f.Pads()
           if p.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN) and p.IsOnCopperLayer()]
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    trks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK']
    vip = []
    for v in vias:
        r = v.GetWidth(pcbnew.F_Cu) // 2
        for ref, p in smd:
            mask = max(p.GetSolderMaskExpansion(pcbnew.F_Mask), 0) if p.IsOnLayer(pcbnew.F_Mask) else 0
            if p.HitTest(v.GetPosition(), r + mask):
                vip.append((ref, p.GetNumber(), round(M(v.GetPosition().x), 3), round(M(v.GetPosition().y), 3)))
    in1 = sum(1 for t in trks if t.GetLayer() == pcbnew.In1_Cu)
    zero = [t.m_Uuid.AsString() for t in trks if t.GetStart() == t.GetEnd()]
    seen, dup = set(), []
    for t in trks:
        k = (t.GetLayer(), t.GetNetCode(), *sorted([(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)]))
        if k in seen:
            dup.append(t.m_Uuid.AsString())
        seen.add(k)
    # dangling: a track end touching nothing of its net (pad, via, other track end/body, zone fill)
    filler = pcbnew.ZONE_FILLER(b)
    zs = [z for z in b.Zones() if not z.GetIsRuleArea()]
    filler.Fill(zs)
    dangling = []
    for t in trks:
        for e in (t.GetStart(), t.GetEnd()):
            ok = False
            for f in b.GetFootprints():
                for p in f.Pads():
                    if p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(t.GetLayer()) and p.HitTest(e, 0):
                        ok = True
                        break
                if ok:
                    break
            if not ok:
                for o in b.GetTracks():
                    if o is t or o.GetNetCode() != t.GetNetCode():
                        continue
                    if o.GetClass() == 'PCB_VIA' and o.HitTest(e, 0):
                        ok = True
                    elif o.GetClass() == 'PCB_TRACK' and o.GetLayer() == t.GetLayer() and o.HitTest(e, 0):
                        ok = True
                    if ok:
                        break
            if not ok:
                for z in zs:
                    if z.GetNetCode() == t.GetNetCode() and z.IsOnLayer(t.GetLayer()) and \
                            z.GetFilledPolysList(t.GetLayer()).Contains(e):
                        ok = True
                        break
            if not ok:
                dangling.append((t.GetNetname(), b.GetLayerName(t.GetLayer()), round(M(e.x), 3), round(M(e.y), 3)))
    offgrid = 0
    for t in list(trks) + list(vias):
        for e in ((t.GetStart(), t.GetEnd()) if t.GetClass() == 'PCB_TRACK' else (t.GetPosition(),)):
            for c in (M(e.x), M(e.y)):
                if abs(round(c / 0.05) * 0.05 - c) > 0.0005:
                    offgrid += 1
    planes = {}
    for z in zs:
        lay = z.GetFirstLayer()
        fp = z.GetFilledPolysList(lay)
        areas = sorted((round(abs(fp.Outline(i).Area()) / 1e12, 2) for i in range(fp.OutlineCount())), reverse=True)
        key = f'{b.GetLayerName(lay)}:{z.GetNetname()}'
        planes.setdefault(key, []).append({'pieces': len(areas), 'areas_mm2': areas[:5]})
    return {'vias': len(vias), 'tracks': len(trks), 'vias_in_smd_pad_or_mask': vip, 'tracks_on_In1': in1,
            'zero_length': zero, 'duplicates': dup, 'dangling_ends': dangling, 'off_grid_ends': offgrid,
            'planes': planes}


# ---------------------------------------------------------------------------------------------
PCOL = {'GND': (130, 130, 130), 'VIN': (214, 39, 40), 'VPD': (255, 127, 14), 'EF_IN': (240, 170, 60),
        'VBUS': (200, 90, 0), 'N12_RAW': (148, 103, 189), '-12V': (90, 40, 140), '+12V': (44, 160, 44),
        '+5V': (23, 190, 207), 'V3V3': (188, 189, 34), 'N_SENSE': (230, 90, 200)}
LCOL = {'F.Cu': (208, 48, 42), 'B.Cu': (42, 95, 208), 'In2.Cu': (224, 138, 0), 'In1.Cu': (85, 85, 85)}
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def render(out, zoom=None, layers=('F.Cu', 'B.Cu', 'In2.Cu'), title=''):
    import pcbnew
    from PIL import Image, ImageDraw, ImageFont
    b = pcbnew.LoadBoard(str(BOARD))
    pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])   # view only, not saved
    M = pcbnew.ToMM
    x0, x1, y0, y1 = zoom or (48.5, 151.5, 61.0, 103.5)
    S = min(2600 / (x1 - x0), 1800 / (y1 - y0))
    W, H = int((x1 - x0) * S), int((y1 - y0) * S) + 30
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    fs = max(8, int(S * 0.45))
    font, small = ImageFont.truetype(FONT, fs), ImageFont.truetype(FONT, max(7, int(S * 0.22)))
    P = lambda x, y: ((x - x0) * S, (y - y0) * S)  # noqa: E731

    def polys(sp):
        return [[P(M(sp.Outline(i).CPoint(k).x), M(sp.Outline(i).CPoint(k).y)) for k in range(sp.Outline(i).PointCount())]
                for i in range(sp.OutlineCount())]
    g = 1 if (x1 - x0) < 40 else 5
    for gx in range(int(x0), int(x1) + 1):
        if gx % g == 0:
            dr.line([P(gx, y0), P(gx, y1)], fill=(235, 235, 235) if gx % 5 else (205, 205, 205), width=1)
            if gx % 5 == 0:
                dr.text(P(gx + 0.1, y0 + 0.1), str(gx), fill=(150, 150, 150), font=small)
    for gy in range(int(y0), int(y1) + 1):
        if gy % g == 0:
            dr.line([P(x0, gy), P(x1, gy)], fill=(235, 235, 235) if gy % 5 else (205, 205, 205), width=1)
            if gy % 5 == 0:
                dr.text(P(x0 + 0.1, gy + 0.1), str(gy), fill=(150, 150, 150), font=small)
    for z in b.Zones():
        if z.GetIsRuleArea():
            for q in polys(z.Outline()):
                dr.polygon(q, outline=(255, 0, 255))
            continue
        ln = b.GetLayerName(z.GetFirstLayer())
        if ln not in layers:
            continue
        for q in polys(z.GetFilledPolysList(z.GetFirstLayer())):
            dr.polygon(q, fill=LCOL.get(ln, (128, 128, 128)) + (45,), outline=LCOL.get(ln, (128, 128, 128)) + (120,))
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            dr.line([P(M(d.GetStart().x), M(d.GetStart().y)), P(M(d.GetEnd().x), M(d.GetEnd().y))], fill='black', width=3)
    labels = []
    for f in b.GetFootprints():
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        for q in polys(cy) if cy.OutlineCount() else []:
            dr.line(q + q[:1], fill=(90, 90, 90), width=1)
        for p in f.Pads():
            if not p.IsOnCopperLayer():
                continue
            nn = p.GetNetname().lstrip('/')
            c = PCOL.get(nn, (205, 165, 90))
            for q in polys(p.GetEffectivePolygon(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, pcbnew.ERROR_INSIDE)):
                dr.polygon(q, fill=c + (215,), outline=(0, 0, 0))
            if p.GetDrillSizeX():
                cx, cy_ = P(M(p.GetPosition().x), M(p.GetPosition().y))
                r = M(p.GetDrillSizeX()) / 2 * S
                dr.ellipse([cx - r, cy_ - r, cx + r, cy_ + r], outline=(0, 0, 0))
            if zoom and p.GetNumber() and nn and not nn.startswith('unconnected'):
                cx, cy_ = P(M(p.GetPosition().x), M(p.GetPosition().y))
                t = f'{p.GetNumber()}:{nn[:9]}'
                dr.text((cx, cy_), t, fill=(0, 0, 0), font=small, anchor='mm')
        if f.GetReference():
            labels.append(((M(f.GetPosition().x), M(f.GetPosition().y)), f.GetReference()))
    order = {'In2.Cu': 0, 'B.Cu': 1, 'F.Cu': 2}
    for t in sorted([t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK'], key=lambda t: order.get(b.GetLayerName(t.GetLayer()), 0)):
        ln = b.GetLayerName(t.GetLayer())
        if ln in layers:
            w = max(1, int(M(t.GetWidth()) * S))
            a, c = P(M(t.GetStart().x), M(t.GetStart().y)), P(M(t.GetEnd().x), M(t.GetEnd().y))
            dr.line([a, c], fill=LCOL[ln] + (150,), width=w)
            for e in (a, c):
                dr.ellipse([e[0] - w / 2, e[1] - w / 2, e[0] + w / 2, e[1] + w / 2], fill=LCOL[ln] + (150,))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            (cx, cy_), r = P(M(t.GetPosition().x), M(t.GetPosition().y)), M(t.GetWidth(pcbnew.F_Cu)) / 2 * S
            dr.ellipse([cx - r, cy_ - r, cx + r, cy_ + r], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    for (x, y), r in labels:
        if x0 <= x <= x1 and y0 <= y <= y1:
            px, py = P(x, y - (0.0 if not zoom else 0.0))
            bb = dr.textbbox((px, py), r, font=font, anchor='mm')
            dr.rectangle(bb, fill=(255, 255, 255, 150))
            dr.text((px, py), r, fill=(0, 0, 160), font=font, anchor='mm')
    dr.text((8, H - 26), title or f'BASE native view x{x0}-{x1} y{y0}-{y1} (panel edge at bottom); F red, B blue, '
            f'In2 orange; layers {",".join(layers)}', fill='black', font=ImageFont.truetype(FONT, 16))
    img.save(out)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'ops':
        Path(sys.argv[3]).write_text(json.dumps(emit(sys.argv[2]), indent=1))
    elif cmd == 'apply':
        sys.exit(apply(sys.argv[2]))
    elif cmd == 'audit':
        sys.exit(audit())
    elif cmd == 'render':
        z = tuple(float(v) for v in sys.argv[3:7]) if len(sys.argv) >= 7 else None
        lay = tuple(sys.argv[7].split(',')) if len(sys.argv) >= 8 else ('F.Cu', 'B.Cu', 'In2.Cu')
        render(sys.argv[2], z, lay)
