#!/usr/bin/env python3
"""Check that no copper sits in the M3 support exclusion annulus (R2 stack, both boards). Read-only.

  python3 -B tools/check_support_copper.py top|base|<board.kicad_pcb> [--refill] [--json OUT]

Ideal exclusion per support (independent of how the keep-out zones are drawn): the annulus
R_IN = 1.7 .. R_OUT = tools/stack_r2.STANDOFF_CU_R (3.6) mm around the support centre, on EVERY
copper layer. Only the support's own central NPTH aperture (r1.6, no copper) is excluded.
Supports = the Stack_M3_Spacer_* footprints; their centres must equal stack_r2.STANDOFFS.

1. Copper vs ideal annulus. Every copper item on every copper layer: tracks/arcs, vias (pad size on
   that layer), pads (every pad except the support NPTH), zone fills (as stored in the file, i.e.
   what goes to the Gerbers; --refill also checks a fresh native refill held in memory, not saved),
   board and footprint graphics/text on copper. A connected item with radial distance range
   [d_min, d_max] from the centre hits the annulus iff d_min < R_OUT and d_max > R_IN (strict: no
   tolerance). Exact float64 point-segment geometry on the native 1 nm grid for tracks, vias,
   round pads and fill polygons (numeric error < 1e-9 mm). Other pads and graphics use KiCad's
   ERROR_OUTSIDE polygons (at most the board max_error, 0.005 mm, larger than the copper), so they
   can only give false alarms, never miss copper.
2. Keep-out definition (what DRC and the zone filler enforce): every rule area named MH<T|B><k>_*
   is ONE simple contour (no holes, no self-intersection, so it survives a native save/reload),
   on all copper layers, tracks/vias/pads/pours not allowed; their union per support contains the
   ideal annulus (point test on a 0.25 deg x 0.02 mm polar grid incl. both boundary circles, plus
   the exact construction margin reported by min distance of the union edges); the NPTH pad lies
   outside every keep-out.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import stack_r2 as st  # noqa: E402

R_IN = 1.7
R_OUT = st.STANDOFF_CU_R
NPTH_D = 3.2


def nat(y, z):
    return (y + 35.75, 104.275 - z)


def seg_dist(c, a, b):
    """Distance point c to segment ab (mm, float64)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((c[0] - ax) * dx + (c[1] - ay) * dy) / L))
    return math.hypot(ax + t * dx - c[0], ay + t * dy - c[1])


def inside(pt, ring):
    """Even-odd point in polygon (ring = list of (x, y))."""
    x, y = pt
    n = len(ring)
    hit = False
    for i in range(n):
        (x1, y1), (x2, y2) = ring[i], ring[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def ring_range(c, outline, holes):
    """[d_min, d_max] of the region outline - holes from c (d_min = 0 if c lies in the copper)."""
    edges = [r for r in [outline] + holes]
    dmin = min(seg_dist(c, r[i], r[(i + 1) % len(r)]) for r in edges for i in range(len(r)))
    if inside(c, outline) and not any(inside(c, h) for h in holes):
        dmin = 0.0
    dmax = max(math.hypot(x - c[0], y - c[1]) for x, y in outline)
    return dmin, dmax


def rings(poly_set, mm):
    out = []
    for i in range(poly_set.OutlineCount()):
        def pts(ch):
            return [(mm(ch.CPoint(k).x), mm(ch.CPoint(k).y)) for k in range(ch.PointCount())]
        out.append((pts(poly_set.Outline(i)), [pts(poly_set.Hole(i, h)) for h in range(poly_set.HoleCount(i))]))
    return out


def simple(ring):
    """True if no two non-adjacent edges of the closed ring touch or cross."""
    n = len(ring)

    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-15 else (1 if v > 0 else -1)

    def on(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    def cross(a, b, c, d):
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        if o1 != o2 and o3 != o4:
            return True
        return (o1 == 0 and on(a, c, b)) or (o2 == 0 and on(a, d, b)) or \
               (o3 == 0 and on(c, a, d)) or (o4 == 0 and on(c, b, d))
    if len(set(ring)) != n:
        return False
    for i in range(n):
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            if cross(ring[i], ring[(i + 1) % n], ring[j], ring[(j + 1) % n]):
                return False
    return True


def points_in(ring, P):
    """Vectorised even-odd test of points P (N x 2) in ring."""
    x, y = P[:, 0], P[:, 1]
    hit = np.zeros(len(P), bool)
    r = np.asarray(ring)
    for (x1, y1), (x2, y2) in zip(r, np.roll(r, -1, axis=0)):
        if y1 == y2:
            continue
        m = (y1 > y) != (y2 > y)
        xs = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        hit ^= m & (x < xs)
    return hit


def check(path, refill=False):
    import pcbnew
    mm = pcbnew.ToMM
    b = pcbnew.LoadBoard(str(path))
    cu_layers = list(b.GetEnabledLayers().CuStack())
    lname = b.GetLayerName
    side = 'T' if 'top' in Path(path).name else 'B'
    sup = [f for f in b.GetFootprints() if f.GetFPID().GetLibItemName().wx_str().startswith('Stack_M3_Spacer')]
    res = {'board': str(path), 'R_IN': R_IN, 'R_OUT': R_OUT, 'layers': [lname(l) for l in cu_layers],
           'max_error_mm': mm(b.GetDesignSettings().m_MaxError), 'supports': [], 'problems': []}
    want = sorted(nat(*p) for p in st.STANDOFFS)
    got = sorted((round(mm(f.GetPosition().x), 6), round(mm(f.GetPosition().y), 6)) for f in sup)
    if len(got) != len(want) or any(math.dist(a, c) > 1e-6 for a, c in zip(want, got)):
        res['problems'].append(f'support centres {got} != stack_r2.STANDOFFS {want}')
    npth = set()
    for f in sup:
        pads = list(f.Pads())
        ok = (len(pads) == 1 and pads[0].GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
              and abs(mm(pads[0].GetDrillSize().x) - NPTH_D) < 1e-6 and abs(mm(pads[0].GetSize().x) - NPTH_D) < 1e-6
              and pads[0].GetPosition() == f.GetPosition()
              and pads[0].GetParentFootprint().m_Uuid.AsString() == f.m_Uuid.AsString())
        if not ok:
            res['problems'].append(f'support at {mm(f.GetPosition().x)},{mm(f.GetPosition().y)}: NPTH pad not as built')
        # stable pad UUIDs, not Python id(): SWIG wrappers are rebuilt/recycled per Pads() iteration
        npth.update(p.m_Uuid.AsString() for p in pads)
    if len(npth) != len(sup):
        res['problems'].append(f'{len(npth)} distinct support NPTH pad UUIDs for {len(sup)} supports')

    # copper items: (label, layer, kind, data)
    items = []
    for t in b.GetTracks():
        lay_set = [l for l in cu_layers if t.IsOnLayer(l)]
        if t.GetClass() == 'PCB_VIA':
            for l in lay_set:
                items.append((f'via {t.GetNetname()}', l, 'disc',
                              ((mm(t.GetPosition().x), mm(t.GetPosition().y)), mm(t.GetWidth(l)) / 2)))
        elif t.GetClass() == 'PCB_TRACK':
            items.append((f'track {t.GetNetname()}', t.GetLayer(), 'stadium',
                          ((mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y)),
                           mm(t.GetWidth()) / 2)))
        else:   # arc
            ps = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(ps, t.GetLayer(), 0, b.GetDesignSettings().m_MaxError, pcbnew.ERROR_OUTSIDE)
            items.append((f'arc {t.GetNetname()}', t.GetLayer(), 'poly', rings(ps, mm)))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.m_Uuid.AsString() in npth:
                continue
            for l in cu_layers:
                if not p.IsOnLayer(l) or not p.FlashLayer(l):
                    continue
                lab = f'pad {f.GetReference()}.{p.GetNumber()} {p.GetNetname()}'
                if p.GetShape(l) == pcbnew.PAD_SHAPE_CIRCLE and not p.GetOffset(l).x and not p.GetOffset(l).y:
                    items.append((lab, l, 'disc', ((mm(p.GetPosition().x), mm(p.GetPosition().y)), mm(p.GetSize(l).x) / 2)))
                else:
                    items.append((lab, l, 'poly', rings(p.GetEffectivePolygon(l, pcbnew.ERROR_OUTSIDE), mm)))
        for g in f.GraphicalItems():
            for l in cu_layers:
                if g.IsOnLayer(l):
                    ps = pcbnew.SHAPE_POLY_SET()
                    g.TransformShapeToPolygon(ps, l, 0, b.GetDesignSettings().m_MaxError, pcbnew.ERROR_OUTSIDE)
                    items.append((f'fp graphic {f.GetReference()}', l, 'poly', rings(ps, mm)))
    for g in b.GetDrawings():
        for l in cu_layers:
            if g.IsOnLayer(l):
                ps = pcbnew.SHAPE_POLY_SET()
                g.TransformShapeToPolygon(ps, l, 0, b.GetDesignSettings().m_MaxError, pcbnew.ERROR_OUTSIDE)
                items.append((f'board graphic {g.GetClass()}', l, 'poly', rings(ps, mm)))
    fills = {}

    def take_fills(tag):
        for z in b.Zones():
            if z.GetIsRuleArea():
                continue
            for l in cu_layers:
                if z.IsOnLayer(l):
                    fills.setdefault(tag, []).append((f'{tag} fill {z.GetNetname()}', l, 'poly',
                                                      rings(z.GetFilledPolysList(l), mm)))
    take_fills('stored')
    if refill:
        pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])
        take_fills('refilled')

    def rng(c, kind, data):
        if kind == 'disc':
            d = math.hypot(data[0][0] - c[0], data[0][1] - c[1])
            yield d - data[1], d + data[1]
        elif kind == 'stadium':
            a, e, r = data
            yield seg_dist(c, a, e) - r, max(math.dist(a, c), math.dist(e, c)) + r
        else:
            for outline, holes in data:
                yield ring_range(c, outline, holes)

    keep = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().startswith('MH')]
    groups = [('items', items)] + [(k, v) for k, v in fills.items()]
    for f in sorted(sup, key=lambda f: (f.GetPosition().x, f.GetPosition().y)):
        c = (mm(f.GetPosition().x), mm(f.GetPosition().y))
        rec = {'centre': c, 'hits': [], 'nearest': {}}
        for gname, its in groups:
            for lab, l, kind, data in its:
                for dmin, dmax in rng(c, kind, data):
                    if dmax <= R_IN - 1.0 or dmin > R_OUT + 1.0:
                        continue
                    key = f'{gname}:{lname(l)}'
                    if key not in rec['nearest'] or dmin < rec['nearest'][key][0]:
                        rec['nearest'][key] = (round(dmin, 6), lab)
                    if dmin < R_OUT and dmax > R_IN:
                        rec['hits'].append({'group': gname, 'layer': lname(l), 'item': lab,
                                            'd_min': round(dmin, 6), 'intrusion_mm': round(R_OUT - dmin, 6)})
        # keep-out definition
        mine = []
        for z in keep:
            ps = z.Outline()
            ring = [(mm(ps.CVertex(i).x), mm(ps.CVertex(i).y)) for i in range(ps.TotalVertices())]
            if ring and min(math.hypot(x - c[0], y - c[1]) for x, y in ring) < R_OUT + 1.0:
                mine.append((z, ps, ring))
        kz = {'zones': [z.GetZoneName() for z, _, _ in mine]}
        for z, ps, ring in mine:
            bad = []
            if ps.OutlineCount() != 1 or ps.HoleCount(0) != 0:
                bad.append(f'{ps.OutlineCount()} outlines / {ps.HoleCount(0) if ps.OutlineCount() else 0} holes')
            if not simple(ring):
                bad.append('not a simple contour')
            if any(not z.IsOnLayer(l) for l in cu_layers):
                bad.append('not on every copper layer')
            if not (z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowPads()
                    and z.GetDoNotAllowZoneFills()):
                bad.append('keep-out flags')
            if inside(c, ring) or min(seg_dist(c, ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))) < NPTH_D / 2:
                bad.append('covers the NPTH aperture')
            if bad:
                res['problems'].append(f'{z.GetZoneName()}: ' + ', '.join(bad))
        th = np.radians(np.arange(0, 360, 0.25))
        rr = np.concatenate([[R_IN], np.arange(R_IN + 0.02, R_OUT, 0.02), [R_OUT]])
        T, R = np.meshgrid(th, rr)
        P = np.column_stack([c[0] + (R * np.cos(T)).ravel(), c[1] + (R * np.sin(T)).ravel()])
        cov = np.zeros(len(P), bool)
        for _, _, ring in mine:
            cov |= points_in(ring, P)
        kz['grid_points'] = int(len(P))
        kz['grid_points_uncovered'] = int((~cov).sum())
        if (~cov).any():
            q = P[~cov][0]
            res['problems'].append(f'support {c}: keep-out union leaves {int((~cov).sum())} annulus grid points '
                                   f'uncovered, e.g. ({q[0]:.4f}, {q[1]:.4f})')
        rec['keepout'] = kz
        if rec['hits']:
            res['problems'].append(f'support {c}: {len(rec["hits"])} copper item(s) inside r{R_IN}..{R_OUT}')
        res['supports'].append(rec)
    return res


if __name__ == '__main__':
    args = sys.argv[1:]
    refill = '--refill' in args
    out = None
    if '--json' in args:
        out = Path(args[args.index('--json') + 1])
        args = [a for a in args if a not in ('--json', str(out))]
    args = [a for a in args if a != '--refill']
    board = args[0]
    if board in ('top', 'base'):
        board = MOD / 'hardware' / board / f'usb-power-45w-{board}.kicad_pcb'
    r = check(board, refill)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r, indent=1) + '\n')
    for s in r['supports']:
        near = min(((d, k, lab) for k, (d, lab) in s['nearest'].items()), default=None)
        print(f"support {s['centre']}: hits {len(s['hits'])}, keep-out {s['keepout']['zones']}, "
              f"uncovered {s['keepout']['grid_points_uncovered']}/{s['keepout']['grid_points']}, nearest {near}")
        for h in s['hits'][:8]:
            print('   HIT', h)
    print('problems:', len(r['problems']))
    for p in r['problems']:
        print('  ', p)
    sys.exit(1 if r['problems'] else 0)
