#!/usr/bin/env python3
"""Render study views from docs/stacked-fit-study/model.json (PIL only, box proxies).

face-base.png / face-top.png : board F faces seen from +X (Y right, Z down), courtyards by group
front.png  : X-Y section looking from the panel (+Z), all solids projected
side.png   : X-Z view looking along +Y (stack, gap, cans, headers, plugs, brackets)
iso.png    : painter's-algorithm isometric of all solids
"""
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[1]
DOC = MOD / 'docs' / 'stacked-fit-study' / ('' if os.environ.get('STACK_FIT_VARIANT', 'literal') == 'literal'
                                          else 'variant-base-protection')
sys.path.insert(0, str(MOD / 'tools'))
import mechanics45 as m  # noqa: E402
sys.path.insert(0, str(HERE))
from check_fit import ordered_poly, poly_contains  # noqa: E402

COL = {'USB PD and main eFuse': (231, 76, 60), 'Always-on control': (155, 89, 182),
       'Protected outputs': (52, 152, 219), '+12 V converter and output eFuse': (230, 126, 34),
       '+5 V converter and output eFuse': (241, 196, 15), 'Negative converter': (26, 188, 156),
       'Negative rail protection and level shifting': (46, 204, 113), 'interconnect': (60, 60, 60),
       'standoff': (127, 140, 141), 'carrier hole': (127, 140, 141)}
try:
    FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
    SMALL = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10)
except OSError:
    FONT = SMALL = ImageFont.load_default()


def solids(model):
    """Every solid as (name, kind, [x0,x1],[y0,y1],[z0,z1], rgb)."""
    st = model['stack']
    g = m.geometry()
    out = []
    polys = {n: ordered_poly(model[f'{n}_edges']) for n in ('base', 'top')}
    allowed = {'J1', 'SW1', 'D8', 'D16', 'D17', 'D18'}
    for p in model['parts']:
        if p['height'] <= 0 or p['group'] in ('standoff', 'carrier hole'):
            continue
        b = p['body']
        if p['ref'] not in allowed and not poly_contains(polys[p['board']], (b[0] + b[1]) / 2, (b[2] + b[3]) / 2):
            continue   # unplaced (parked off-board): listed in the report, not drawn
        out.append((p['ref'], 'part', p['X'], b[:2], b[2:], COL.get(p['group'], (100, 100, 100))))
    env = m.envelopes(g)
    for k in ('J2_plug', 'J3_plug', 'J2_ribbon', 'J3_ribbon'):
        x, y, z = env[k][1]
        out.append((k, 'proxy', x, y, z, (180, 180, 220)))
    for yc in g['brackets']['Y_centres_mm']:
        fs = m.fastener_solids(g, yc)
        for k in ('foot', 'web', 'front_nut', 'side_nut'):
            x, y, z = fs[k]
            out.append((f'{k}@{yc}', 'mech', x, y, z, (120, 120, 120)))
    for (y, z) in json.loads((DOC / 'placement-manifest.json').read_text())['standoffs_YZ']:
        out.append((f'standoff@{y},{z}', 'mech', [st['base_F'], st['top_B']], [y - 2.75, y + 2.75],
                    [z - 2.75, z + 2.75], (90, 90, 90)))
    out.append(('panel', 'panel', [0, 20], [0, 128.5], [0, 1.6], (200, 200, 170)))
    return out


def board_polys(model):
    res = {}
    for name in ('base', 'top'):
        res[name] = model[f'{name}_edges']
    return res


def face(model, name, path, scale=9):
    """Floorplan of one board; legend and captions in a band BELOW the drawing (never over parts)."""
    man = json.loads((DOC / 'placement-manifest.json').read_text())
    moved = {r for r, v in man.get('manual_pass', {}).get('moves', {}).items() if v['board'] == name}
    W, Hd = int(110 * scale), int(46 * scale)
    H = Hd + 110
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    ox, oz = 10.0, 0.0
    P = lambda y, z: ((y - ox) * scale, (z - oz) * scale)
    other = 'top' if name == 'base' else 'base'
    for a, b in model[f'{other}_edges']:
        d.line([P(*a), P(*b)], fill=(190, 190, 190), width=1)
    for a, b in model[f'{name}_edges']:
        d.line([P(*a), P(*b)], fill='black', width=2)
    for p in model['parts']:
        if p['board'] != name:
            continue
        c = p['court']
        col = COL.get(p['group'], (100, 100, 100))
        light = tuple(int(v * 0.35 + 255 * 0.65) for v in col)
        d.rectangle([P(c[0], c[2]), P(c[1], c[3])], outline=col, fill=light)
        for q in p['pads']:
            bb = q['box']
            d.rectangle([P(bb[0], bb[2]), P(bb[1], bb[3])], fill=(184, 115, 51) if not q['npth'] else (40, 40, 40))
        if p['ref'] in moved:
            d.rectangle([P(c[0], c[2]), P(c[1], c[3])], outline=(200, 0, 0), width=3)
        cx, cz = (c[0] + c[1]) / 2, (c[2] + c[3]) / 2
        if p['ref']:
            d.text(P(cx, cz), p['ref'], fill='black', font=SMALL, anchor='mm')
    if name == 'top':   # base-only obstacles projected (grey) for reference
        for p in model['parts']:
            if p['board'] == 'base' and p['ref'] in ('J2', 'J3'):
                c = p['court']
                d.rectangle([P(c[0], c[2]), P(c[1], c[3])], outline=(150, 150, 150), width=2)
                d.text(P((c[0] + c[1]) / 2, (c[2] + c[3]) / 2), p['ref'] + ' (base, below)', fill=(120, 120, 120),
                       font=FONT, anchor='mm')
    d.line([(0, Hd), (W, Hd)], fill=(220, 220, 220))
    d.text((8, Hd + 6), f'{name.upper()} board F face from +X (Y right, Z = depth down, panel at top). '
           'Grey outline = other board.', fill='black', font=FONT)
    d.text((8, Hd + 24), 'Copper = pads; courtyards tinted by sheet; RED frame = moved in the final manual pass.',
           fill='black', font=FONT)
    x, y = 8, Hd + 48
    for k, v in COL.items():
        if k == 'carrier hole':
            continue
        w = int(d.textlength(k, font=SMALL)) + 30
        if x + w > W - 8:
            x, y = 8, y + 18
        d.rectangle([x, y, x + 12, y + 12], fill=v)
        d.text((x + 16, y), k, fill='black', font=SMALL)
        x += w
    im.save(path)


def ortho(model, path, axes, title, scale=9, rng=None):
    """axes: ('Y','X') etc.: horizontal, vertical. Depth sort by remaining axis."""
    idx = {'X': 2, 'Y': 3, 'Z': 4}
    sol = solids(model)
    h, v = axes
    (h0, h1), (v0, v1) = rng
    W, H = int((h1 - h0) * scale) + 20, int((v1 - v0) * scale) + 60
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    if v == 'X':
        P = lambda a, b: (10 + (a - h0) * scale, 10 + (v1 - b) * scale)
    else:
        P = lambda a, b: (10 + (a - h0) * scale, 10 + (b - v0) * scale)
    # boards as solids
    st = model['stack']
    boards = []
    for name, xr in (('base', [st['base_B'], st['base_F']]), ('top', [st['top_B'], st['top_F']])):
        ys = [pt[0] for e in model[f'{name}_edges'] for pt in e]
        zs = [pt[1] for e in model[f'{name}_edges'] for pt in e]
        boards.append((name, 'board', xr, [min(ys), max(ys)], [min(zs), max(zs)], (34, 120, 60)))
    allsol = [x for x in sol if x[1] in ('panel', 'mech')] + boards + \
        sorted([x for x in sol if x[1] == 'part'], key=lambda x: -(x[idx[{'X': 'Y', 'Y': 'Z', 'Z': 'Y'}[h if h != 'X' else v]]][0])) + \
        [x for x in sol if x[1] == 'proxy']
    for s in allsol:
        a = s[idx[h]]
        b = s[idx[v]]
        col = s[5]
        fill = tuple(int(c * 0.5 + 255 * 0.5) for c in col) if s[1] != 'board' else col
        (x0, y0), (x1, y1) = P(a[0], b[0]), P(a[1], b[1])
        box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        if s[1] == 'proxy':
            d.rectangle(box, outline=col, width=2)
        else:
            d.rectangle(box, outline=col, fill=fill)
    for xline, lab in ((20.0, 'X20 panel edge'), (st['top_F'] + 8.0, 'can top X18.7'),
                       (st['top_B'], 'top B X9.1'), (st['base_F'], 'base F X4.1')):
        if 'X' in axes:
            if h == 'X':
                d.line([P(xline, v0), P(xline, v1)], fill=(200, 0, 0), width=1)
                d.text(P(xline, v0), lab, fill=(200, 0, 0), font=SMALL)
            else:
                d.line([P(h0, xline), P(h1, xline)], fill=(200, 0, 0), width=1)
                d.text(P(h0, xline), lab, fill=(200, 0, 0), font=SMALL)
    d.text((10, H - 40), title, fill='black', font=FONT)
    im.save(path)


def iso(model, path, scale=7.0):
    sol = solids(model)
    st = model['stack']
    # board slabs as prisms from edges' bbox pieces (approximate outline by edge polygon)
    polys = {n: ordered_poly(model[f'{n}_edges']) for n in ('base', 'top')}
    ang = math.radians(30)
    def proj(x, y, z):   # view from +X, -Y, -Z-ish
        u = (z * math.cos(ang) - x * math.cos(ang)) * scale
        w = (y + (z + x) * math.sin(ang) * 0.6) * scale
        return u, w
    faces = []
    def box(x, y, z, col, name):
        X, Y, Z = x, y, z
        pts = lambda a: [proj(*p) for p in a]
        # visible faces: +X (top), -Z (front), -Y (top edge)
        faces.append((X[1] + 0 * Z[0], pts([(X[1], Y[0], Z[0]), (X[1], Y[1], Z[0]), (X[1], Y[1], Z[1]), (X[1], Y[0], Z[1])]), col))
        faces.append((X[0], pts([(X[0], Y[0], Z[0]), (X[1], Y[0], Z[0]), (X[1], Y[1], Z[0]), (X[0], Y[1], Z[0])]),
                      tuple(int(c * 0.8) for c in col)))
        faces.append((X[0], pts([(X[0], Y[0], Z[0]), (X[1], Y[0], Z[0]), (X[1], Y[0], Z[1]), (X[0], Y[0], Z[1])]),
                      tuple(int(c * 0.65) for c in col)))
    for name, xr in (('base', [st['base_B'], st['base_F']]), ('top', [st['top_B'], st['top_F']])):
        poly = polys[name]
        top3 = [proj(xr[1], y, z) for y, z in poly]
        faces.append((xr[1] - 0.01, top3, (34, 120, 60) if name == 'base' else (40, 140, 90)))
    for s in sol:
        if s[0] == 'panel':
            box([0, 20], [0, 128.5], [0, 1.6], (220, 220, 190), 'panel')
            continue
        box(s[2], s[3], s[4], s[5], s[0])
    # painter: lower X first (we look from +X), then larger Z first
    faces.sort(key=lambda f: f[0])
    us = [p[0] for f in faces for p in f[1]]
    ws = [p[1] for f in faces for p in f[1]]
    W, H = max(int(max(us) - min(us)) + 40, 560), int(max(ws) - min(ws)) + 110
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    mu, mw = min(us) - 20, min(ws) - 20
    for _, pts, col in faces:
        d.polygon([(u - mu, w - mw) for u, w in pts], fill=col, outline=(30, 30, 30))
    for k, line in enumerate(('Isometric box proxy from +X (component side), Y down the panel.',
                              'Panel left (beige); base board (dark green) with J2/J3 + plug/ribbon',
                              'proxies (lilac); top board (light green) with cans; standoffs/brackets grey.',
                              'Courtyard-derived boxes at assumed max heights, not CAD.')):
        d.text((10, H - 84 + 18 * k), line, fill='black', font=FONT)
    im.save(path)


def main():
    model = json.loads((DOC / 'model.json').read_text())
    img = DOC / 'img'
    img.mkdir(exist_ok=True)
    face(model, 'base', img / 'face-base.png')
    face(model, 'top', img / 'face-top.png')
    ortho(model, img / 'front.png', ('X', 'Y'), 'FRONT (looking +Z from panel): X across 0..20 (right = X20 '
          'panel edge), Y down. All solids behind the panel projected; boards green.', 12, ((-1, 22), (10, 130)))
    ortho(model, img / 'side.png', ('Z', 'X'), 'SIDE/TOP (looking +Y): Z depth right (panel Z0..1.6), X up/down '
          '(base X2.5..4.1, top X9.1..10.7, red X20). J2/J3 + plug + ribbon proxies at the rear.', 14, ((-2, 52), (-1, 22)))
    iso(model, img / 'iso.png')
    print('ok')


if __name__ == '__main__':
    main()
