#!/usr/bin/env python3
"""Readable face views of the R2 stacked boards (placement + copper), from the native boards.

  python3 -B tools/render_stack.py <out-dir> [base|top ...] [--zoom Y0 Y1 Z0 Z1] [--layers F.Cu,B.Cu]

View = the board's F face seen from +X (Y right, Z = depth down, panel at the top), the same frame
as docs/stacked-fit-study. Courtyards are outlined, pads filled by net role, tracks drawn per
layer (F red, B blue, In2 orange), vias as rings. The other board's outline is drawn grey.
Not a CAD render: bodies are courtyard outlines. PIL only (no matplotlib on this host).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import pcbnew  # noqa: E402
import stack_r2 as st  # noqa: E402

PCOL = {'GND': (122, 122, 122), 'VIN': (214, 39, 40), 'VPD': (255, 127, 14), 'EF_IN': (255, 160, 80),
        'N12_RAW': (148, 103, 189), '-12V': (106, 61, 154), '+12V': (44, 160, 44), '+5V': (23, 190, 207),
        'P12_RAW': (152, 223, 138), 'P5_RAW': (158, 218, 229), 'V3V3': (188, 189, 34)}
LCOL = {'F.Cu': (208, 48, 42), 'B.Cu': (42, 95, 208), 'In2.Cu': (224, 138, 0), 'In1.Cu': (85, 85, 85)}
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def yz(v):
    return pcbnew.ToMM(v.x) - 35.75, 104.275 - pcbnew.ToMM(v.y)


def poly_yz(sp):
    return [[yz(sp.Outline(i).CPoint(k)) for k in range(sp.Outline(i).PointCount())] for i in range(sp.OutlineCount())]


def render(board, out, zoom=None, layers=('F.Cu', 'B.Cu'), title=''):
    b = pcbnew.LoadBoard(str(MOD / 'hardware' / board / f'usb-power-45w-{board}.kicad_pcb'))
    pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])   # view only, not saved
    y0, y1, z0, z1 = zoom or (12.0, 116.0, 0.0, 44.0)
    S = 2400 / (y1 - y0)
    W, H = int((y1 - y0) * S), int((z1 - z0) * S) + 40
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    fs = max(9, int(S * (0.55 if zoom else 0.9)))
    font = ImageFont.truetype(FONT, fs)
    P = lambda y, z: ((y - y0) * S, (z - z0) * S)  # noqa: E731
    for z in b.Zones():
        ln = b.GetLayerName(z.GetFirstLayer())
        if z.GetIsRuleArea() or ln not in layers:
            continue
        c = LCOL.get(ln, (128, 128, 128))
        for q in poly_yz(z.GetFilledPolysList(z.GetFirstLayer())):
            dr.polygon([P(*v) for v in q], fill=c + (28,))
    if board == 'base':
        q = st.TOP_OUTLINE + st.TOP_OUTLINE[:1]
        dr.line([P(*v) for v in q], fill=(150, 150, 150), width=2)
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            dr.line([P(*yz(d.GetStart())), P(*yz(d.GetEnd()))], fill='black', width=3)
    labels = []
    for f in b.GetFootprints():
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        for q in poly_yz(cy) if cy.OutlineCount() else []:
            dr.line([P(*v) for v in q + q[:1]], fill=(60, 60, 60), width=1)
        for p in f.Pads():
            c = PCOL.get(p.GetNetname(), (200, 160, 80))
            for q in poly_yz(p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)):
                dr.polygon([P(*v) for v in q], fill=c + (230,), outline=(0, 0, 0))
        if f.GetReference():
            labels.append((yz(f.GetPosition()), f.GetReference()))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            continue
        ln = b.GetLayerName(t.GetLayer())
        if ln in layers:
            w = max(1, int(pcbnew.ToMM(t.GetWidth()) * S))
            a, c = P(*yz(t.GetStart())), P(*yz(t.GetEnd()))
            dr.line([a, c], fill=LCOL[ln] + (170,), width=w)
            for e in (a, c):
                dr.ellipse([e[0] - w / 2, e[1] - w / 2, e[0] + w / 2, e[1] + w / 2], fill=LCOL[ln] + (170,))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            (cx, cz), r = P(*yz(t.GetPosition())), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 * S
            dr.ellipse([cx - r, cz - r, cx + r, cz + r], fill='white', outline='black', width=2)
    for (y, z), r in labels:
        if y0 <= y <= y1 and z0 <= z <= z1:
            x, yy = P(y, z)
            bb = dr.textbbox((x, yy), r, font=font, anchor='mm')
            dr.rectangle(bb, fill=(255, 255, 255, 170))
            dr.text((x, yy), r, fill='black', font=font, anchor='mm')
    dr.text((10, H - 34), title or f'{board.upper()} F face from +X (Y right, Z depth down, panel at top). Pads by net '
            '(VIN red, GND grey, N12_RAW purple, +12 green, +5 cyan); tracks F red / B blue / In2 orange; '
            'grey dashed = top outline', fill='black', font=ImageFont.truetype(FONT, 18))
    img.save(out)



def assembly(out):
    """Stack view from the rear (looking along +Z): X across the module (panel 0..20) horizontal,
    Y down the panel vertical. Boards as slabs, every part as its Y span x assumed height."""
    import mechanics45 as m
    S = st.STACK
    sc = 14.0
    W, H = int(24 * sc) + 340, int(118 * sc) + 80
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    f = ImageFont.truetype(FONT, 13)
    P = lambda x, y: (40 + (x + 1) * sc, 30 + (y - 10) * sc)  # noqa: E731
    dr.rectangle([P(0, 10), P(20, 128)], outline=(150, 150, 150), width=1)
    dr.line([P(20, 10), P(20, 128)], fill=(200, 0, 0), width=2)
    dr.text(P(20.3, 11), 'X20 = 4HP width', fill=(200, 0, 0), font=f)
    for name, xb, xf, col in (('base', S['base_B'], S['base_F'], (60, 120, 60)), ('top', S['top_B'], S['top_F'], (60, 60, 160))):
        b = pcbnew.LoadBoard(str(MOD / 'hardware' / name / f'usb-power-45w-{name}.kicad_pcb'))
        ys = [yz(d.GetStart())[0] for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
        dr.rectangle([P(xb, min(ys)), P(xf, max(ys))], fill=col + (200,))
        for fp in b.GetFootprints():
            h = st.HEIGHT.get(fp.GetFPID().GetLibItemName().wx_str(), 0)
            if h <= 0:
                continue
            bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            y0, y1 = sorted((yz(pcbnew.VECTOR2I(bb.GetLeft(), 0))[0], yz(pcbnew.VECTOR2I(bb.GetRight(), 0))[0]))
            dr.rectangle([P(xf, y0), P(xf + h, y1)], fill=col + (60,), outline=col + (160,))
    env = m.envelopes(m.geometry())
    for k in ('J2_plug',):
        x, y, _ = env[k][1]
        dr.rectangle([P(x[0], y[0]), P(x[1], y[1])], outline=(200, 120, 0), width=2)
    for y, _z in st.STANDOFFS:
        dr.rectangle([P(S['base_B'] - st.BOLT['head_k'], y - 2.85), P(S['base_B'], y + 2.85)], fill=(90, 90, 90))
        dr.line([P(S['base_B'], y), P(S['base_B'] + st.BOLT['length'], y)], fill=(40, 40, 40), width=3)
        dr.rectangle([P(S['top_F'], y - 2.75), P(S['top_F'] + st.BOLT['nut_m'], y + 2.75)], fill=(120, 120, 120))
    lines = ['R2 stack seen from the rear (along +Z)', 'green: base (B X2.5, F X4.1)', 'blue: top (B X9.1, F X10.7)',
             'boxes: parts, assumed max height', 'orange: J2 mated plug envelope', 'grey: M3 through bolt,',
             '  head under base B, nut on top F', 'cans 8.0 assumed -> X18.7',
             'not CAD; heights are assumptions', 'projection over all Z: overlaps', '  here are at different depths']
    for i, t in enumerate(lines):
        dr.text((W - 320, 40 + 20 * i), t, fill='black', font=f)
    img.save(out)


PAGE = {1: ('USB-PD input + main protection', (214, 39, 40)), 2: ('+12 V converter U2 + eFuse U6', (44, 160, 44)),
        3: ('+5 V converter U3 + eFuse U7', (23, 160, 190)), 4: ('-12 V raw converter U4', (148, 103, 189)),
        5: ('negative protection U8/Q4 (Kelvin)', (106, 61, 154)), 6: ('fault latch / RESET (always-on)', (227, 119, 194)),
        7: ('outputs J2, monitors, panel LEDs', (255, 127, 14)), 0: ('board-to-board headers / supports', (90, 90, 90))}
KEY = ('U', 'J', 'Q', 'L', 'F', 'SW', 'X')


def face(board, page, W):
    """One board's F face, courtyards tinted by S7 schematic page (functional block), key refs only."""
    b = pcbnew.LoadBoard(str(MOD / 'hardware' / board / f'usb-power-45w-{board}.kicad_pcb'))
    pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])
    y0, y1, z0, z1 = 12.0, 116.0, -1.0, 44.0
    S = W / (y1 - y0)
    img = Image.new('RGB', (W, int((z1 - z0) * S)), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    P = lambda y, z: ((y - y0) * S, (z - z0) * S)  # noqa: E731
    for z in b.Zones():
        ln = b.GetLayerName(z.GetFirstLayer())
        if z.GetIsRuleArea() or ln not in ('F.Cu', 'B.Cu'):
            continue
        for q in poly_yz(z.GetFilledPolysList(z.GetFirstLayer())):
            dr.polygon([P(*v) for v in q], fill=LCOL[ln] + (30,))
    if board == 'base':
        q = st.TOP_OUTLINE + st.TOP_OUTLINE[:1]
        dr.line([P(*v) for v in q], fill=(120, 120, 220), width=3)
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            dr.line([P(*yz(d.GetStart())), P(*yz(d.GetEnd()))], fill='black', width=3)
    font = ImageFont.truetype(FONT, int(S * 1.25))
    labels = []
    for f in b.GetFootprints():
        r = f.GetReference()
        pg = page.get(r, 0)
        col = PAGE[pg][1]
        cy = f.GetCourtyard(pcbnew.F_CrtYd)
        for q in poly_yz(cy) if cy.OutlineCount() else []:
            dr.polygon([P(*v) for v in q], fill=col + (95,), outline=col + (255,))
        for p_ in f.Pads():
            for q in poly_yz(p_.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)):
                dr.polygon([P(*v) for v in q], fill=(200, 170, 90, 200))
        if r and (r.startswith(KEY) or r in ('D10', 'D1', 'C5', 'C34', 'C35', 'C36', 'R48', 'R49')):
            labels.append((yz(f.GetPosition()), r))
    for t in b.GetTracks():
        ln = b.GetLayerName(t.GetLayer())
        if t.GetClass() == 'PCB_VIA':
            (cx, cz), rr = P(*yz(t.GetPosition())), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 * S
            dr.ellipse([cx - rr, cz - rr, cx + rr, cz + rr], fill='white', outline='black')
        elif ln in LCOL:
            dr.line([P(*yz(t.GetStart())), P(*yz(t.GetEnd()))], fill=LCOL[ln] + (220,),
                    width=max(1, int(pcbnew.ToMM(t.GetWidth()) * S)))
    for y, z in st.STANDOFFS:
        cx, cz = P(y, z)
        rr = 1.6 * S
        dr.ellipse([cx - rr, cz - rr, cx + rr, cz + rr], outline='black', width=3)
    for (y, z), r in labels:
        x_, z_ = P(y, z)
        bb = dr.textbbox((x_, z_), r, font=font, anchor='mm')
        dr.rectangle(bb, fill=(255, 255, 255, 200))
        dr.text((x_, z_), r, fill='black', font=font, anchor='mm')
    return img, P, S


def section(W):
    """Composite stack section seen along -Y: Z depth horizontal (panel left), X across the module
    vertical (base at the bottom). Each element is drawn at its own representative Z (header,
    LED, bolt, can, J2), so this is a projection for reading the stack, not one cut."""
    import mechanics45 as m
    S_ = st.STACK
    sc = (W - 60) / 54.0
    H = int(23 * sc) + 250
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    f = ImageFont.truetype(FONT, 20)
    fn = ImageFont.truetype(FONT, 24)
    P = lambda x, z: (30 + (z + 1.5) * sc, 10 + (21.5 - x) * sc)  # noqa: E731

    def R(x0, x1, z0, z1, **k):
        (a_, b_), (c_, d_) = P(x0, z0), P(x1, z1)
        dr.rectangle([min(a_, c_), min(b_, d_), max(a_, c_), max(b_, d_)], **k)

    def tag(n, x, z):
        cx, cy = P(x, z)
        dr.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill='white', outline='black', width=2)
        dr.text((cx, cy), str(n), fill='black', font=fn, anchor='mm')
    R(0, 20, -1.2, 0, fill=(160, 160, 160))
    for x in (0, 20):
        dr.line([P(x, -1.2), P(x, 52)], fill=(200, 0, 0), width=2)
    dr.text(P(20.9, 30), 'X20 / X0 = 4HP width limits (red)', fill=(200, 0, 0), font=f)
    R(S_['base_B'], S_['base_F'], 2, 42, fill=(60, 120, 60, 230))
    R(S_['top_B'], S_['top_F'], 2, 28.7, fill=(60, 60, 160, 230))
    R(S_['top_B'], S_['top_F'], 28.7, 42, outline=(60, 60, 160), width=1)
    env = m.envelopes(m.geometry())
    (jx, _, jz) = env['J2'][1]
    R(jx[0], jx[1], jz[0], jz[1], fill=(255, 127, 14, 120), outline=(200, 90, 0), width=2)
    for k in ('J2_plug', 'J2_ribbon'):
        (x, _, z) = env[k][1]
        R(x[0], x[1], z[0], z[1], outline=(200, 90, 0), width=2)
    hz = 6.0
    pl, tail, post = st.PIN['plastic'], st.PIN['tail'], st.PIN['post']
    R(S_['base_F'], S_['base_F'] + pl, hz - 1.27, hz + 3.81, fill=(30, 30, 30))
    for dz in (0, 2.54):
        dr.line([P(S_['base_F'] - tail, hz + dz), P(S_['base_F'] + pl + post, hz + dz)], fill=(200, 160, 40),
                width=max(2, int(0.64 * sc)))
    R(S_['base_F'], S_['base_F'] + 3.9, 11.0, 14.0, fill=(60, 120, 60, 70), outline=(60, 120, 60), width=2)
    bz, B = 19.0, st.BOLT
    R(S_['base_B'] - B['head_k'], S_['base_B'], bz - B['head_d'] / 2, bz + B['head_d'] / 2, fill=(90, 90, 90))
    R(S_['base_F'], S_['top_B'], bz - 3.0, bz + 3.0, fill=(175, 175, 175), outline=(90, 90, 90))
    R(S_['top_F'], S_['top_F'] + B['nut_m'], bz - B['nut_AF'] / 2, bz + B['nut_AF'] / 2, fill=(120, 120, 120))
    dr.line([P(S_['base_B'] - B['head_k'], bz), P(S_['base_B'] + B['length'], bz)], fill='black', width=6)
    R(S_['top_F'], S_['top_F'] + 8.0, 22.7, 27.7, fill=(60, 60, 160, 70), outline=(60, 60, 160), width=2)
    dr.text(P(S_['base_F'] - 0.3, 2.6), 'base', fill='white', font=f, anchor='lt')
    dr.text(P(S_['top_F'] - 0.3, 2.6), 'top', fill='white', font=f, anchor='lt')
    for n, x, z in ((1, 14.5, 7.3), (2, 9.0, 12.5), (3, 15.0, 19.0), (4, 16.0, 25.2), (5, 11.5, 31.5), (6, 17.4, 46.0)):
        tag(n, x, z)
    notes = [
        f'Stack X: base B/F {S_["base_B"]}/{S_["base_F"]}, gap {S_["gap"]}, top B/F {S_["top_B"]}/{S_["top_F"]}; every part on its '
        'board F face; Z = depth from the panel front; top board cut back to Z28.7 over J2 only (Y51.5..82.7).',
        f'1  Samtec TSW-110-07-G-D (2x10) / TSW-103-07-G-D (2x3): tail {tail} / plastic {pl} / post {post}; tail '
        f'{tail - S_["thickness"]:.2f} below base B, post {S_["base_F"] + pl + post - S_["top_F"]:.2f} above top F; soldered both boards.',
        '2  tallest base part under the top board: panel LED flange 3.9 -> 1.10 nominal / 0.44 worst to top B.',
        '3  M3 x 12 ISO 7380 head (k 1.65, X0.85) | plain 5.0 spacer | DIN 934 nut on top F; thread past nut 1.4 nom / 0.63 worst; 5 supports.',
        '4  can 8.0 assumed (MVK 6.3x8 class) -> X18.7: 1.30 nominal / 0.28 worst to the 4HP limit.',
        '5  J2 Wurth WR-BHD 61201621621, drill 1.1 (Wurth pattern), 9.25 envelope;  6  mated plug + ribbon reach Z50 '
        '(42 mm NOT claimed with the cable fitted).',
        'Composite (each element at its own Z, not one cut). Heights/tolerances are assumptions: can/LED/header maxima,',
        'bolt/spacer/nut, pin current and thermal stay prototype gates.']
    y0 = int(23 * sc) + 20
    for i, t in enumerate(notes):
        dr.text((20, y0 + i * 32), t, fill='black', font=f)
    return img


def floorplan(out):
    import circuit45
    from hierarchy6 import layout
    parts = circuit45.circuit()
    plan = layout({p['ref']: p for p in parts})
    page = {r: v[0] for r, v in plan.items()}
    W = 1800
    base, _, _ = face('base', page, W)
    top, _, _ = face('top', page, W)
    sec = section(W)
    tf = ImageFont.truetype(FONT, 30)
    sf = ImageFont.truetype(FONT, 22)
    lh = 34
    leg_h = 2 * lh + 10
    H = 60 + base.height + 50 + top.height + 50 + leg_h + sec.height + 50
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    dr.text((20, 14), 'usb-power-45w R2: two stacked boards behind the 4HP panel, one protected 16-pin output (J2)',
            fill='black', font=tf)
    y = 60
    dr.text((20, y), 'BASE board, F face (130 parts; blue line = top-board outline above it; circles = M3 supports)',
            fill='black', font=sf)
    img.paste(base, (0, y + 30)); y += 30 + base.height + 20
    dr.text((20, y), 'TOP board, F face (86 parts; red/blue = routed F/B copper so far, U4 stage)', fill='black', font=sf)
    img.paste(top, (0, y + 30)); y += 30 + top.height + 20
    for i, k in enumerate([1, 2, 3, 4, 5, 6, 7, 0]):
        name, col = PAGE[k]
        cx, cy = 20 + (i % 4) * 445, y + (i // 4) * lh
        dr.rectangle([cx, cy + 4, cx + 26, cy + 26], fill=col + (140,), outline=col)
        dr.text((cx + 34, cy + 2), name, fill='black', font=sf)
    y += leg_h
    dr.text((20, y), 'STACK SECTION (seen along -Y: Z depth left to right, X across the module bottom to top)', fill='black', font=sf)
    img.paste(sec, (0, y + 30))
    img.save(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('boards', nargs='*', default=['base', 'top'])
    ap.add_argument('--zoom', nargs=4, type=float)
    ap.add_argument('--tag', default='')
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for bd in a.boards:
        if bd == 'assembly':
            assembly(Path(a.out) / 'assembly-rear.png')
        elif bd == 'floorplan':
            floorplan(Path(a.out) / 'floorplan-single-idc.png')
        else:
            render(bd, Path(a.out) / f'face-{bd}{a.tag}.png', a.zoom)
