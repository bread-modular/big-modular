#!/usr/bin/env python3
"""Face view of the S8 single board (same frame and drawing style as tools/render_stack.py).

  python3 -B tools/render_s8.py <out.png> [--board <kicad_pcb>] [--title <text>]

F face from +X: Y right, Z (depth) down, panel at the top (the native KiCad view upside down).
Courtyards outlined (red where two overlap), pads coloured by net, references labelled; the bracket
nut/driver circles, the 1 mm edge band and the 2 mm hand-solder rings around the THT pads of J1, D8,
J2 and J3 are drawn so the placement rules can be read off the picture. PIL only; not a CAD render.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pcbnew  # noqa: E402
import render_stack as rs  # noqa: E402

BOARD = HERE.parent / 'hardware/single/usb-power-45w-single.kicad_pcb'
FONT = rs.FONT
PCOL = dict(rs.PCOL, **{'-12V': (106, 61, 154), '+12V': (44, 160, 44)})
HAND = ('J1', 'D8', 'J2', 'J3')
DRIVERS = [(22.0, 15.0), (106.5, 15.0)]       # bracket M3 Y/Z: F-side nut + 8 mm driver circle


def yz(v):
    return pcbnew.ToMM(v.x) - 35.75, 104.275 - pcbnew.ToMM(v.y)


def polys(sp):
    return [[yz(sp.Outline(i).CPoint(k)) for k in range(sp.Outline(i).PointCount())] for i in range(sp.OutlineCount())]


def render(board_path, out, title='', zoom=None):
    b = pcbnew.LoadBoard(str(board_path))
    y0, y1, z0, z1 = zoom or (12.0, 116.0, -1.0, 52.0)
    S = 2600 / (y1 - y0)
    W, H = int((y1 - y0) * S), int((z1 - z0) * S) + 46
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    fs = max(9, int(S * (0.55 if zoom else 0.78)))
    font = ImageFont.truetype(FONT, fs)
    P = lambda y, z: ((y - y0) * S, (z - z0) * S)  # noqa: E731
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, True)
    inset = pcbnew.SHAPE_POLY_SET(outline)
    inset.Deflate(pcbnew.FromMM(1.0), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
    for q in polys(outline):
        dr.polygon([P(*v) for v in q], fill=(236, 244, 236))
    for q in polys(inset):
        dr.line([P(*v) for v in q + q[:1]], fill=(150, 190, 150), width=1)
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            dr.line([P(*yz(d.GetStart())), P(*yz(d.GetEnd()))], fill='black', width=3)
    for y, z in DRIVERS:
        (cx, cz), r = P(y, z), 4.0 * S
        dr.ellipse([cx - r, cz - r, cx + r, cz + r], outline=(58, 166, 201), width=3)
        r = 1.6 * S
        dr.ellipse([cx - r, cz - r, cx + r, cz + r], fill='white', outline='black', width=2)
    fps = [f for f in b.GetFootprints() if f.GetReference()]
    cys = {f.GetReference(): f.GetCourtyard(pcbnew.F_CrtYd) for f in fps}
    bad = set()
    refs = sorted(cys)
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if cys[a].OutlineCount() and cys[c].OutlineCount() and cys[a].BBox().Intersects(cys[c].BBox()):
                x = pcbnew.SHAPE_POLY_SET(cys[a])
                x.BooleanIntersection(cys[c])
                if x.Area() > 1e6:
                    bad |= {a, c}
    for f in fps:
        if f.GetReference() in HAND:
            for p in f.Pads():
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    (cx, cz) = P(*yz(p.GetPosition()))
                    r = (pcbnew.ToMM(max(p.GetSize(pcbnew.F_Cu).x, p.GetSize(pcbnew.F_Cu).y)) / 2 + 2.0) * S
                    dr.ellipse([cx - r, cz - r, cx + r, cz + r], fill=(255, 196, 0, 40))
    labels = []
    for f in fps:
        r = f.GetReference()
        for q in polys(cys[r]) if cys[r].OutlineCount() else []:
            dr.line([P(*v) for v in q + q[:1]], fill=(210, 0, 0) if r in bad else (60, 60, 60), width=3 if r in bad else 1)
        for p in f.Pads():
            c = PCOL.get(p.GetNetname(), (200, 160, 80))
            for q in polys(p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)):
                dr.polygon([P(*v) for v in q], fill=c + (230,), outline=(0, 0, 0))
        labels.append((yz(f.GetPosition()), r))
    for (y, z), r in labels:
        if y0 <= y <= y1 and z0 <= z <= z1:
            x, yy = P(y, z)
            bb = dr.textbbox((x, yy), r, font=font, anchor='mm')
            dr.rectangle(bb, fill=(255, 255, 255, 170))
            dr.text((x, yy), r, fill='black', font=font, anchor='mm')
    dr.text((10, H - 40), title or 'S8 single board, F face from +X (Y right, Z depth down, panel at top)',
            fill='black', font=ImageFont.truetype(FONT, 19))
    dr.text((10, H - 18), 'Pads by net: VIN red, GND grey, +12V green, -12V purple, VPD orange, V3V3 olive. '
            'Blue circles: bracket nut + 8 mm driver keep-out. Yellow: 2 mm hand-solder rings (J1, D8, J2, J3). '
            'Thin green: 1 mm edge band. Red courtyard = overlap.', fill=(60, 60, 60), font=ImageFont.truetype(FONT, 14))
    img.save(out)
    return sorted(bad)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('out', type=Path)
    ap.add_argument('--board', type=Path, default=BOARD)
    ap.add_argument('--title', default='')
    a = ap.parse_args()
    print(render(a.board, a.out, a.title), a.out)
