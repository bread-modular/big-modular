"""Render the usb-power-45w M1 mechanical-preview drawings (system Python + pcbnew 10).

Run from the repository root after tools/build_assembly.py (needs its STL meshes):
  python3 -B modules/usb-power-45w/tools/render_preview.py

Every drawn feature is taken from the native boards (pcbnew: outline, holes, aperture,
pads, courtyards, panel text) or from docs/mechanical-geometry.json (bracket, fasteners,
proposal envelopes) in the common assembly frame; nothing is free-hand. Writes into
docs/mechanical-preview/: front/side/top SVG+PNG, isometric PNG (OpenSCAD, xvfb) and the
combined printable usb-power-45w-mechanical-preview.pdf. Nominal; not a fit approval.
"""
import json
import math
import subprocess
import sys
from html import escape
from pathlib import Path

import pcbnew
from PIL import Image, ImageDraw, ImageFont

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from mechanics45 import carrier_outline, fastener_solids  # noqa: E402

G = json.loads((MODULE / 'docs/mechanical-geometry.json').read_text())
VER = json.loads((MODULE / 'docs/mechanical-preview/verification.json').read_text())['report']
CHK = json.loads((MODULE / 'docs/mechanical-preview/contract-check.json').read_text())['report']
OUT = MODULE / 'docs/mechanical-preview'
STL = MODULE / 'research/mech-preview/stl'
ENV = G['envelopes_XYZ_mm']
mm = pcbnew.ToMM
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
COL = {'panel': '#e9d7a8', 'carrier': '#5f9e6e', 'bracket': '#e58b3a', 'part': '#555b66', 'led': '#d23c3c',
       'plug': '#f2b84b', 'ribbon': '#9aa7b8', 'conflict': '#d10000', 'tool': '#3aa6c9', 'limit': '#b0006a',
       'env': '#8f96a3', 'can': '#4a6fa5', 'ink': '#1d2f45'}
STAMP = 'M1 MECHANICAL PREVIEW - UNROUTED - NOT A RELEASE - nominal mm'


class Sheet:
    def __init__(self, title, sub, w=420, h=297):
        self.w, self.h = w, h
        self.a = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">',
                  '<style>text{font-family:DejaVu Sans,sans-serif;fill:#1d2f45}</style>',
                  f'<rect x="0" y="0" width="{w}" height="{h}" fill="white"/>',
                  f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" fill="none" stroke="#1d2f45" stroke-width=".35"/>']
        self.text(10, 13, title, 5.2, bold=True)
        self.text(10, 20, sub, 2.9)
        self.text(w - 10, h - 7, STAMP, 2.6, anchor='end', fill='#b0006a')

    def text(self, x, y, t, size=2.6, anchor='start', fill=None, bold=False, rot=0):
        tr = f' transform="rotate({rot} {x} {y})"' if rot else ''
        self.a.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" text-anchor="{anchor}"'
                      + (f' fill="{fill}"' if fill else '') + (' font-weight="bold"' if bold else '') + f'{tr}>{escape(t)}</text>')

    def rect(self, x0, y0, x1, y1, fill='none', stroke=COL['ink'], sw=0.25, dash=None, op=1.0, rx=0):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        self.a.append(f'<rect x="{x0:.3f}" y="{y0:.3f}" width="{x1 - x0:.3f}" height="{y1 - y0:.3f}" rx="{rx:.3f}" fill="{fill}" '
                      f'fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')

    def circle(self, x, y, r, fill='white', stroke=COL['ink'], sw=0.25, dash=None, op=1.0):
        self.a.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r:.3f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" '
                      f'stroke-width="{sw}"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')

    def line(self, x0, y0, x1, y1, stroke=COL['ink'], sw=0.25, dash=None):
        self.a.append(f'<path d="M{x0:.3f},{y0:.3f} L{x1:.3f},{y1:.3f}" stroke="{stroke}" stroke-width="{sw}" fill="none"'
                      + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')

    def poly(self, pts, fill='none', stroke=COL['ink'], sw=0.25, op=1.0):
        self.a.append('<polygon points="' + ' '.join(f'{x:.3f},{y:.3f}' for x, y in pts)
                      + f'" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"/>')

    def dim(self, x0, y0, x1, y1, label, off=0, size=2.3, color=COL['ink']):
        """Linear dimension between two points (horizontal or vertical), offset perpendicular."""
        if abs(y1 - y0) < 1e-9:  # horizontal
            yy = y0 + off
            self.line(x0, y0, x0, yy, color, 0.15)
            self.line(x1, y1, x1, yy, color, 0.15)
            self.arrow(x0, yy, x1, yy, color)
            self.text((x0 + x1) / 2, yy - 0.8, label, size, 'middle', color)
        else:
            xx = x0 + off
            self.line(x0, y0, xx, y0, color, 0.15)
            self.line(x1, y1, xx, y1, color, 0.15)
            self.arrow(xx, y0, xx, y1, color)
            self.text(xx - 0.8, (y0 + y1) / 2, label, size, 'middle', color, rot=-90)

    def arrow(self, x0, y0, x1, y1, color=COL['ink']):
        self.line(x0, y0, x1, y1, color, 0.18)
        for (ax, ay), (bx, by) in [((x0, y0), (x1, y1)), ((x1, y1), (x0, y0))]:
            ang = math.atan2(by - ay, bx - ax)
            for s in (-1, 1):
                self.line(ax, ay, ax + 1.4 * math.cos(ang + s * 0.35), ay + 1.4 * math.sin(ang + s * 0.35), color, 0.18)

    def callout(self, x, y, tx, ty, label, size=2.3, color=COL['ink']):
        self.line(x, y, tx, ty, color, 0.15)
        self.circle(x, y, 0.35, color, color, 0.1)
        self.text(tx + (0.8 if tx >= x else -0.8), ty + 0.8, label, size, 'start' if tx >= x else 'end', color)

    def legend(self, x, y, items, size=2.4):
        for i, (c, label, kind) in enumerate(items):
            yy = y + i * 4.4
            if kind == 'dash':
                self.rect(x, yy - 2.4, x + 6, yy + 0.4, 'none', c, 0.4, '1.2 0.8')
            else:
                self.rect(x, yy - 2.4, x + 6, yy + 0.4, c, c, 0.2, op=0.75)
            self.text(x + 8, yy, label, size)

    def axes(self, x, y, h, v, hl, vl):
        self.arrow(x, y, x + 12 * h, y, COL['limit'])
        self.arrow(x, y, x, y + 12 * v, COL['limit'])
        self.text(x + 12 * h + (1 if h > 0 else -1), y + 1, hl, 2.6, 'start' if h > 0 else 'end', COL['limit'], True)
        self.text(x + 1, y + 12 * v + (3 if v > 0 else -1.5), vl, 2.6, 'start', COL['limit'], True)

    def save(self, name):
        self.a.append('</svg>')
        svg = OUT / f'{name}.svg'
        svg.write_text('\n'.join(self.a) + '\n')
        subprocess.run(['rsvg-convert', '-f', 'pdf', '-o', str(OUT / f'{name}.pdf'), str(svg)], check=True)
        subprocess.run(['rsvg-convert', '-f', 'png', '-d', '150', '-p', '150', '-b', 'white', '-o', str(OUT / f'{name}.png'), str(svg)],
                       check=True)
        return OUT / f'{name}.pdf'


def native():
    car = pcbnew.LoadBoard(str(MODULE / 'hardware/usb-power-45w.kicad_pcb'))
    pan = pcbnew.LoadBoard(str(MODULE / 'panels/front-pcb/usb-power-45w-panel.kicad_pcb'))
    ox, oy = G['native_panel_origin_mm']
    texts = [(t.GetText(), mm(t.GetPosition().x) - ox, mm(t.GetPosition().y) - oy, mm(t.GetTextHeight()))
             for t in pan.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS]
    holes = [(mm(fp.GetPosition().x) - ox, mm(fp.GetPosition().y) - oy, mm(next(iter(fp.Pads())).GetDrillSizeX()),
              fp.GetValue()) for fp in pan.GetFootprints()]
    placed = VER['inventory']['placed_on_board']
    parts = {}
    for fp in car.GetFootprints():
        r = fp.GetReference()
        if r not in placed:
            continue
        yz = lambda v: (mm(v.x) - 35.75, 104.275 - mm(v.y))
        boxes = [g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_CrtYd]
        cy = [yz(pcbnew.VECTOR2I(b.GetLeft(), b.GetTop())) for b in boxes] + [yz(pcbnew.VECTOR2I(b.GetRight(), b.GetBottom())) for b in boxes]
        pads = []
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            (y0, z0), (y1, z1) = yz(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), yz(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            pads.append((y0, z0, y1, z1, p.GetAttribute()))
        parts[r] = {'crt': (min(c[0] for c in cy), min(c[1] for c in cy), max(c[0] for c in cy), max(c[1] for c in cy)),
                    'pads': pads}
    return texts, holes, parts


def front_sheet(texts, holes):
    s = Sheet('usb-power-45w - FRONT PANEL VIEW (4HP)',
              'Seen from the front; X across, Y down; origin = panel upper-left front corner. Solid = panel features; '
              'dashed = parts behind the panel (projected).')
    k, ox, oy = 1.8, 60, 40
    P = lambda x, y: (ox + x * k, oy + y * k)
    pw, ph, _ = G['panel_mm']
    s.rect(*P(0, 0), *P(pw, ph), COL['panel'], sw=0.4)
    # Behind-panel projections (dashed).
    y0, y1 = G['carrier_Y_mm']
    s.rect(*P(2.5, y0), *P(4.1, y1), COL['carrier'], COL['carrier'], 0.3, '1.2 0.8', 0.5)
    for yc in G['brackets']['Y_centres_mm']:
        s.rect(*P(0.1, yc - 5), *P(9.3, yc + 5), COL['bracket'], COL['bracket'], 0.3, '1.2 0.8', 0.35)
    for h in G['headers']:
        r = h['reference']
        e = ENV[r + '_plug']['XYZ']
        s.rect(*P(e[0][0], e[1][0]), *P(e[0][1], e[1][1]), COL['plug'], COL['plug'], 0.3, '1.2 0.8', 0.35)
        e = ENV[r]['XYZ']
        s.rect(*P(e[0][0], e[1][0]), *P(e[0][1], e[1][1]), 'none', COL['part'], 0.3, '1.2 0.8')
    for c in G['cans']['parts']:
        e = ENV[c['reference']]['XYZ']
        s.rect(*P(e[0][0], e[1][0]), *P(e[0][1], e[1][1]), 'none', COL['can'], 0.3, '1.2 0.8')
    # Panel features from the native panel PCB.
    x, y, w, h, r = G['aperture_XYWHR_mm']
    s.rect(*P(x, y), *P(x + w, y + h), 'white', rx=r * k, sw=0.35)
    for hx, hy, d, role in holes:
        s.circle(*P(hx, hy), d / 2 * k, 'white', sw=0.35)
        if 'bracket' in role or 'rail' in role:
            s.circle(*P(hx, hy), 3.0 * k, 'none', COL['part'], 0.2, '0.8 0.6')
    for l in G['LEDs']:
        hx, hy, d = l['panel_XY_diameter_mm']
        s.circle(*P(hx, hy), G['LED']['max_body_diameter_mm'] / 2 * k, COL['led'], COL['led'], 0.2, op=0.8)
    sx, sy, sd = G['reset_XY_diameter_mm']
    s.circle(*P(sx, sy), G['switch']['actuator_diameter_mm'] / 2 * k, COL['part'], op=0.6)
    s.rect(*P(4.1, 33.5 - 4.47), *P(7.36, 33.5 + 4.47), COL['part'], COL['part'], 0.2, op=0.55)
    for t, tx, ty, th in texts:
        s.text(*P(tx, ty + th * 0.35), t, th * k * 0.95, 'middle', '#ffffff' if False else '#20262e', True)
    # Dimensions.
    s.dim(*P(0, ph), *P(pw, ph), f'{pw:.1f} (4HP)', 8)
    s.dim(*P(pw, 0), *P(pw, ph), f'{ph:.1f}', 22)
    s.dim(*P(0, 0), *P(12.58, 0), '12.58 rail', -5)
    s.dim(*P(0, 0), *P(6.4, 0), '6.4 bracket', -11)
    rows = [(3.0, 'rail hole Y3.0  d3.2 (blank 4HP)'), (22.0, 'M3 bracket hole X6.4 Y22  d3.2'),
            (28.1, 'USB-C aperture X3.3..8.3  Y28.1..38.9  R0.6'), (33.5, 'J1 shell axis X5.73 Y33.5 (SMD+THT lugs)')]
    rows += [(l['panel_XY_diameter_mm'][1], f'{l["reference"]} {l["label"]} THT LED X6.1 Y{l["panel_XY_diameter_mm"][1]:g} hole d3.6')
             for l in G['LEDs']]
    rows += [(sy, f'SW1 RESET (SMT TL3340) X5.8 Y{sy:g} hole d3.2'), (76.0, 'J2 pin1 (-12V) Y76  [behind, dashed]'),
             (106.5, 'M3 bracket hole X6.4 Y106.5  d3.2'), (107.0, 'J3 pin1 (-12V) Y107 [behind]'), (125.5, 'rail hole Y125.5 d3.2')]
    lx = ox + pw * k + 34
    used = []
    for yy, label in rows:
        ty = oy + yy * k
        while any(abs(ty - u) < 4.2 for u in used):
            ty += 4.2
        used.append(ty)
        s.line(ox + pw * k, oy + yy * k, lx - 2, ty, COL['ink'], 0.12)
        s.text(lx, ty + 0.9, label, 2.5)
    s.axes(20, 40, 1, 1, '+X', '+Y (down)')
    s.legend(250, 60, [(COL['panel'], 'Native 4HP panel PCB 20.0 x 128.5 x 1.6 (passive, NPTH only)', 'fill'),
                       (COL['carrier'], 'Carrier edge behind panel: B.Cu X2.5 / F.Cu X4.1 (copied)', 'dash'),
                       (COL['bracket'], 'Two plain M3 L brackets (foot X0.1..9.3)', 'dash'),
                       (COL['led'], 'THT 3 mm LEDs D8 MAIN, D16 +12V, D17 +5V, D18 -12V', 'fill'),
                       (COL['part'], 'J1 USB-C body / SW1 actuator (no verified model: envelope)', 'fill'),
                       (COL['plug'], 'PROPOSAL envelope: mated IDC plugs on J2/J3 (behind)', 'dash'),
                       (COL['can'], 'PROVISIONAL cans C5/C34/C35/C36 (height context)', 'dash')])
    reg = VER['panel_registration']
    lig = CHK['panel_ligaments_mm']
    notes = ['Checks (nominal):',
             f'- Panel = blank 4HP precedent: {CHK["panel_matches_blank_4hp"]}; rail holes != bracket holes',
             f'- LED/SW1 axes on hole centres: dY = dX = 0.000; LED body radial clearance {reg["D8"]["radial_clearance_body_mm"]} mm',
             f'- SW1 actuator radial clearance {reg["SW1"]["radial_clearance_actuator_mm"]} mm; USB shell-to-aperture '
             f'{reg["J1"]["aperture_minus_shell_each_side_Y_mm"]} (Y) / {reg["J1"]["aperture_minus_shell_each_side_X_mm"]} (X) mm/side',
             f'- Min panel web between openings {min(v for k_, v in lig.items() if "web" in k_):.1f} mm; '
             f'USB aperture to bracket head {lig["USB_aperture_to_top_bracket_head"]} mm',
             '- Rail screw heads d6 (dotted) clear the cluster; bracket screw heads d6 dotted',
             '- Panel native DRC: 0 violations (research/mech-preview/panel-drc.json)',
             'Copied unchanged from usb-power: aperture, LED X6.1 / hole d3.6, SW1 X5.8 / hole d3.2,',
             'USB axis X5.73 Y33.5, bracket holes. Changed: 4HP width, rail X12.58, 4 LEDs, RESET Y69.']
    for i, t in enumerate(notes):
        s.text(250, 100 + i * 4.3, t, 2.45, bold=(i == 0))
    return s.save('front-view')


def side_sheet(parts):
    s = Sheet('usb-power-45w - SIDE VIEW OF THE CARRIER F FACE (YZ, seen from +X)',
              'Z (into case) to the right, Y down. Placed parts: courtyards (thin) + pads (filled). '
              'Bracket web is on the hidden B face (dashed). 205 other SMD parts are PARKED OFF-BOARD (not placed).')
    k, ox, oy = 1.85, 40, 30
    P = lambda z, y: (ox + z * k, oy + y * k)
    pw, ph, pt = G['panel_mm']
    s.rect(*P(0, 0), *P(pt, ph), COL['panel'], sw=0.3)
    rp = G['rail_profile_YZ_mm']
    for yr in (rp['top_Y'], rp['bottom_Y']):
        s.rect(*P(pt, max(yr[0], 0)), *P(pt + rp['depth_behind_rear'], min(yr[1], ph)), '#cccccc', '#999999', 0.2, op=0.5)
    s.poly([P(z, y) for y, z in carrier_outline(G)], COL['carrier'], COL['carrier'], 0.35, 0.35)
    b = G['brackets']
    for yc in b['Y_centres_mm']:
        s.rect(*P(b['front_foot_Z_mm'][0], yc - 5), *P(b['front_foot_Z_mm'][1], yc + 5), COL['bracket'], COL['bracket'], 0.3, op=0.6)
        s.rect(*P(b['front_foot_Z_mm'][1], yc - 5), *P(b['outer_Z_mm'][1], yc + 5), COL['bracket'], COL['bracket'], 0.3, '1.2 0.8', 0.25)
        s.circle(*P(b['side_hole_Z_mm'], yc), 1.6 * k, 'white', sw=0.3)
        s.circle(*P(b['side_hole_Z_mm'], yc), 4.0 * k, 'none', COL['tool'], 0.3, '1 0.7')
        nr = b['nut_AF_max_mm'] / math.sqrt(3)
        s.poly([P(b['side_hole_Z_mm'] + nr * math.cos(math.radians(60 * i)), yc + nr * math.sin(math.radians(60 * i)))
                for i in range(6)], 'none', COL['part'], 0.25)
    for r, d in parts.items():
        y0, z0, y1, z1 = d['crt']
        col = COL['led'] if r.startswith('D') else COL['can'] if r.startswith('C') else COL['part']
        s.rect(*P(z0, y0), *P(z1, y1), 'none', col, 0.2)
        for py0, pz0, py1, pz1, att in d['pads']:
            s.rect(*P(pz0, py0), *P(pz1, py1), '#c8a02a' if att == pcbnew.PAD_ATTRIB_PTH else '#d8b86a', '#7a5d10', 0.08)
        lab = {'J1': 'J1 USB-C', 'SW1': 'SW1'}.get(r, r)
        s.text(*P(z1 + 0.4, (y0 + y1) / 2 + 0.6), lab, 2.2)
    for h in G['headers']:
        r = h['reference']
        e = ENV[r + '_plug']['XYZ']
        s.rect(*P(e[2][0], e[1][0]), *P(e[2][1], e[1][1]), COL['plug'], COL['plug'], 0.3, '1.2 0.8', 0.3)
        e = ENV[r + '_ribbon']['XYZ']
        s.rect(*P(e[2][0], e[1][0]), *P(e[2][1], e[1][1]), COL['ribbon'], COL['ribbon'], 0.3, '1.2 0.8', 0.35)
        y1_, z1_ = h['pin1_YZ_mm']
        s.callout(*P(z1_, y1_), *P(52, y1_ + 3), f'{r} pin 1 = -12V (Y{y1_:g} Z{z1_:g}), odd row high Z')
    zl = G['depth_target']['limit_behind_panel_rear_mm'] + pt
    s.line(*P(zl, -2), *P(zl, ph + 2), COL['limit'], 0.4, '2 1')
    s.text(*P(zl + 0.5, -3), f'Z{zl:g} = 42 behind panel REAR (alt. datum)', 2.4, 'start', COL['limit'], True)
    y0, y1 = G['carrier_Y_mm']
    z0, z1 = G['carrier_Z_mm']
    s.dim(*P(pt, ph), *P(z1, ph), f'bare carrier: Z{z1:g} from FRONT = {z1 - pt:.1f} behind REAR', 9)
    s.dim(*P(0, ph), *P(pt, ph), '1.6', 4)
    s.dim(*P(z0, 0), *P(z0, y0), f'Y{y0:g}', -6)
    s.dim(*P(z1, y0), *P(z1, y1), f'carrier Y{y0:g}..{y1:g} = {y1 - y0:.1f}', 6)
    s.dim(*P(z0, 16.5), *P(10, 16.5), 'cutback to Z10', -4, 2.1)
    s.dim(*P(z0, 101), *P(10, 101), 'cutback to Z10', -4, 2.1)
    s.callout(*P(15, 22), *P(28, 6), 'M3 hole Y22 Z15 (d3.2); nut + 8 mm driver keep-out (cyan)')
    s.callout(*P(15, 106.5), *P(28, 122), 'M3 hole Y106.5 Z15; bracket web Z4.6..20 on B face')
    s.callout(*P(22, 45), *P(52, 32), 'C5/C34/C35/C36 PROVISIONAL SMT cans: generic 7.7 model, 8.0 max envelope')
    s.callout(*P(5.5, 52.75), *P(52, 20), 'Front cluster: USB -> D8 -> D16 -> D17 -> D18 -> RESET')
    s.axes(14, 40, 1, 1, '+Z', '+Y')
    edge = VER['edge_rule_conflicts']
    ab = VER['area_budget_mm2']
    notes = ['Checks / findings (not waived):',
             f'- Courtyard to edge < 1 mm: {", ".join(f"{k_} {v:g}" for k_, v in edge["courtyard_lt_1mm"].items())}',
             f'- Pad copper to edge < 1 mm: {", ".join(f"{k_} {v:g}" for k_, v in edge["copper_lt_1mm"].items())} (DRC errors)',
             '  -> edge-mounted panel parts copied from usb-power; USER DECISION needed',
             f'- J2/J3 courtyard to edge {VER["courtyard_to_edge_mm"]["J2"]}/{VER["courtyard_to_edge_mm"]["J3"]} mm; '
             f'cans >= {min(VER["courtyard_to_edge_mm"][c["reference"]] for c in G["cans"]["parts"])} mm',
             f'- Hand-solder 2 mm: closest D18-SW1 {VER["hand_solder_2mm"]["D18"]["gap_mm"]} mm, D8-J1 {VER["hand_solder_2mm"]["D8"]["gap_mm"]} mm',
             f'- Area estimate (NON-BLOCKING): courtyard bbox sum {ab["smd_courtyard_sum_incl_cans"]:.0f} mm2 vs ~{ab["usable_for_smd_single_sided"]:.0f} mm2 F (x{ab["courtyard_utilisation"]:.2f})',
             '  heuristic: boxes not unioned, cans double-counted; no fit/fail proof',
             '  B-side placement = later option only, not authorized',
             '- M3: foot/web/nuts/driver paths clear of PCB and parts (nominal)']
    for i, t in enumerate(notes):
        s.text(250, 205 + i * 4.2, t, 2.4, bold=(i == 0), fill=COL['conflict'] if 'USER' in t else None)
    s.legend(250, 160, [(COL['carrier'], 'Carrier (native outline, 4-layer, unrouted)', 'fill'),
                        (COL['bracket'], 'Bracket foot (solid) / web on B face (dashed)', 'fill'),
                        (COL['plug'], 'PROPOSAL mated IDC plug envelope', 'dash'),
                        (COL['ribbon'], 'PROPOSAL ribbon leaving +Z toward the bus', 'dash'),
                        (COL['tool'], 'F-side M3 nut driver keep-out (d8)', 'dash'),
                        ('#cccccc', 'Case rail section (context)', 'fill')])
    return s.save('side-view')


def top_sheet():
    s = Sheet('usb-power-45w - TOP VIEW / XZ STACK (seen from above, Y projected)',
              'X across to the right, Z into the case downward. Heights of every placed part, brackets, M3 hardware and '
              'proposal envelopes against the 4HP width (X20.0) and the depth target.')
    k, ox, oy = 3.8, 112, 44
    P = lambda x, z: (ox + x * k, oy + z * k)
    pw, ph, pt = G['panel_mm']
    s.rect(*P(0, 0), *P(pw, pt), COL['panel'], sw=0.3)
    z0, z1 = G['carrier_Z_mm']
    s.rect(*P(2.5, z0), *P(4.1, z1), COL['carrier'], COL['carrier'], 0.3, op=0.7)
    b = G['brackets']
    s.poly([P(0.1, 1.6), P(9.3, 1.6), P(9.3, 4.6), P(2.5, 4.6), P(2.5, 20), P(0.1, 20)], COL['bracket'], COL['bracket'], 0.3, 0.6)
    f = fastener_solids(G, 22)
    for key, col in [('front_nut', COL['part']), ('side_nut', COL['part'])]:
        e = f[key]
        s.rect(*P(e[0][0], e[2][0]), *P(e[0][1], e[2][1]), col, col, 0.2, op=0.5)
    s.rect(*P(6.4 - 3, -2.4), *P(6.4 + 3, 0), COL['part'], COL['part'], 0.2, op=0.5)
    s.rect(*P(6.4 - 1.5, 0), *P(6.4 + 1.5, 8), 'none', COL['part'], 0.2)
    s.rect(*P(0.1, 13.5), *P(8.1, 16.5), 'none', COL['part'], 0.2)
    t = f['tools']['side_nut_driver']
    s.rect(*P(6.6, t[2][0]), *P(pw, t[2][1]), COL['tool'], COL['tool'], 0.25, '1 0.7', 0.2)
    for r, col in [('J1', COL['part']), ('SW1', COL['part']), ('D8', COL['led']), ('J2', COL['part']),
                   ('J2_plug', COL['plug']), ('J2_ribbon', COL['ribbon']), ('C5', COL['can'])]:
        e = ENV[r]['XYZ']
        dash = '1.2 0.8' if r.endswith(('plug', 'ribbon')) else None
        s.rect(*P(e[0][0], e[2][0]), *P(e[0][1], e[2][1]), col, col, 0.25, dash, 0.45)
    mp = G['mating_plug']
    e = ENV['J2_plug']['XYZ']
    s.rect(*P(mp['proposal_X_mm'][1], e[2][0]), *P(4.1 + mp['strain_relief_worst_height_mm'], e[2][1]), COL['conflict'], COL['conflict'], 0.3, op=0.5)
    s.line(*P(pw, -4), *P(pw, 52), COL['limit'], 0.45, '2 1')
    s.text(*P(pw + 0.3, -4.5), '4HP panel edge X20.0', 2.4, 'start', COL['limit'], True)
    s.line(*P(0.7, 22), *P(0.7, 44), '#7a5d10', 0.3, '1 0.6')
    zl = G['depth_target']['limit_behind_panel_rear_mm'] + pt
    s.line(*P(-3, zl), *P(pw + 3, zl), COL['limit'], 0.45, '2 1')
    s.text(*P(pw + 3.3, zl + 0.6), f'Z{zl:g}: 42 behind panel REAR (alt. datum)', 2.4, 'start', COL['limit'], True)
    s.line(*P(-3, 42), *P(pw + 3, 42), COL['limit'], 0.25, '0.6 0.6')
    s.text(*P(pw + 3.3, 42 + 0.6), 'Z42.0 from panel FRONT (= board rear)', 2.2, 'start', COL['limit'])
    # Dimensions.
    s.dim(*P(0, 52), *P(pw, 52), '20.0', 4)
    s.dim(*P(2.5, 49), *P(4.1, 49), '1.6', 2)
    s.dim(*P(4.1, 49), *P(pw, 49), 'F-side allowance 15.9 (old 2HP: 5.7)', -3)
    s.dim(*P(4.1, ENV['J2']['XYZ'][2][0]), *P(ENV['J2']['XYZ'][0][1], ENV['J2']['XYZ'][2][0]), 'header 9.25 max', -2, 2.1)
    s.dim(*P(4.1, 30.6), *P(18.9, 30.6), 'mated plug <= 14.8 (requirement)', -1.2, 2.1)
    s.dim(*P(pw, 0), *P(pw, z1), f'carrier rear Z{z1:g}', 16)
    s.callout(*P(19.6, 34.7), *P(26, 26), 'clip strain relief worst case X20.4: 0.4 OVER 4HP (red)', 2.3, COL['conflict'])
    s.callout(*P(17.4, 45), *P(26, 47.5), 'ribbon leaves +Z toward the bus (continues)')
    s.callout(*P(0.7, 39), *P(26, 41.5), 'THT tails <= 1.8 below B.Cu (X >= 0.7)')
    s.callout(*P(8.1, 22), *P(26, 18), 'cans: generic 7.7 model / 8.0 max envelope (PROVISIONAL)')
    s.callout(*P(6.0, 5), *P(26, 9), 'J1 / LEDs / SW1 front cluster (Y-projected)')
    s.callout(*P(12, 15), *P(26, 13.5), 'side M3 nut + 8 mm driver path X6.6..30 (cyan)')
    s.callout(*P(5, 3), *P(26, 4.5), 'bracket L: foot Z1.6..4.6, web X0.1..2.5')
    s.axes(20, 60, 1, 1, '+X', '+Z (into case)')
    w = CHK['margin_to_panel_right_edge_X20_mm']
    d = CHK['depth_mm']
    notes = ['Width / depth summary (nominal):',
             f'- Margin to X20.0: header {w["J2"]}, plug {w["J2_plug"]}, ribbon {w["J2_ribbon"]}, cans {w["C5"]}, LEDs {w["D8"]} mm',
             f'- Strain-relief clip worst case: {w["IDC_strain_relief_worst_case"]} mm (CONFLICT unless measured lower)',
             f'- Bare carrier: {d["bare_carrier_behind_panel_rear"]} mm behind panel rear (Z{d["bare_carrier_rear_from_panel_front"]:g})',
             f'- Solids: Z{d["assembled_solid_max_from_panel_front"]:g} from front = {d["assembled_solid_max_behind_panel_rear"]} behind rear',
             f'- CABLED (PROPOSAL envelope): Z{d["cabled_envelope_from_panel_front"]:g} from front = {d["cabled_envelope_behind_panel_rear"]} behind rear -> NOT <= 42',
             '- Front: LED tips 0.2 mm proud; M3 pan heads 2.4 mm proud of the panel front']
    for i, t in enumerate(notes):
        s.text(265, 222 + i * 4.3, t, 2.45, bold=(i == 0), fill=COL['conflict'] if ('CONFLICT' in t or 'NOT <=' in t) else None)
    s.legend(265, 190, [(COL['carrier'], 'Carrier B.Cu X2.5 / F.Cu X4.1', 'fill'),
                        (COL['bracket'], 'Plain L bracket (copied)', 'fill'),
                        (COL['part'], 'Placed parts / M3 nuts / heads', 'fill'),
                        (COL['plug'], 'PROPOSAL IDC plug', 'dash'),
                        (COL['ribbon'], 'PROPOSAL ribbon', 'dash'),
                        (COL['conflict'], 'Strain-relief worst-case conflict', 'fill')])
    return s.save('top-view')


SCAD_COLORS = [('rails', [0.75, 0.75, 0.75, 0.35]), ('panel', [0.91, 0.84, 0.66, 1]), ('carrier', [0.30, 0.58, 0.36, 1]),
               ('brackets', [0.90, 0.55, 0.23, 1]), ('screws', [0.75, 0.77, 0.80, 1]), ('nuts', [0.62, 0.64, 0.68, 1]),
               ('headers', [0.15, 0.15, 0.17, 1]), ('leds', [0.85, 0.15, 0.15, 1]), ('cans', [0.32, 0.45, 0.68, 1]),
               ('ui_envelopes', [0.55, 0.58, 0.63, 1]), ('plugs', [0.95, 0.72, 0.29, 0.55]),
               ('ribbons', [0.62, 0.66, 0.74, 0.55]), ('strain_relief_conflict', [0.85, 0.0, 0.0, 0.6]),
               ('tools', [0.23, 0.65, 0.79, 0.25])]


def iso(name, eye, center, size=(1800, 1300), skip=()):
    """OpenSCAD render of the assembly STLs. The scene is mapped to OpenSCAD's Z-up world by a
    proper rotation (scad x = X, scad y = Z, scad z = -Y), so the panel front faces -y and up
    is the module top; camera eye/centre are given in that scad world."""
    lines = ['$fn=48;', 'multmatrix([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]) {']
    for n, c in SCAD_COLORS:
        if n not in skip:
            lines.append(f'  color({c}) import("{STL / (n + ".stl")}");')
    # Axis triad in the ASSEMBLY frame, placed above-left of the panel.
    for rot, lab, col, tip in [('[0,90,0]', 'X', [0.8, 0, 0.3], [16, 0, 0]), ('[-90,0,0]', 'Y', [0.1, 0.5, 0.1], [0, 16, 0]),
                               ('[0,0,0]', 'Z', [0.1, 0.2, 0.8], [0, 0, 16])]:
        lines.append(f'  color({col}) translate([-14,-14,0]) rotate({rot}) {{cylinder(h=12,r=0.6); '
                     'translate([0,0,12]) cylinder(h=3.5,r1=1.4,r2=0);}')
        lines.append(f'  color({col}) translate([{-14 + tip[0]},{-14 + tip[1]},{tip[2]}]) rotate([90,0,0]) '
                     f'linear_extrude(0.5) text("{lab}", size=5, halign="center", valign="center");')
    lines.append('}')
    scad = MODULE / 'research/mech-preview' / f'{name}.scad'
    scad.write_text('\n'.join(lines) + '\n')
    png = MODULE / 'research/mech-preview' / f'{name}-raw.png'
    cam = ','.join(str(v) for v in eye + center)
    subprocess.run(['xvfb-run', '-a', 'openscad', '-o', str(png), f'--imgsize={size[0]},{size[1]}', f'--camera={cam}',
                    '--projection=o', '--viewall', '--colorscheme=Tomorrow', str(scad)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png


def compose(raw, out, title, captions, legend):
    img = Image.open(raw).convert('RGB')
    W, H = img.size
    pad_top, pad_right = 150, 640
    canvas = Image.new('RGB', (W + pad_right, H + pad_top), 'white')
    canvas.paste(img, (0, pad_top))
    d = ImageDraw.Draw(canvas)
    f1, f2, f3 = ImageFont.truetype(FONTB, 40), ImageFont.truetype(FONT, 25), ImageFont.truetype(FONT, 23)
    d.text((30, 22), title, fill=COL['ink'], font=f1)
    for i, c in enumerate(captions):
        d.text((30, 78 + i * 32), c, fill=COL['ink'], font=f2)
    x = W + 20
    y = pad_top + 10
    d.text((x, y), 'Legend (common assembly frame)', fill=COL['ink'], font=ImageFont.truetype(FONTB, 26))
    y += 46
    for color, label in legend:
        d.rectangle([x, y, x + 34, y + 24], fill=tuple(int(255 * v) for v in color[:3]), outline=(40, 40, 40))
        lines = label.split('\n')
        for j, t in enumerate(lines):
            d.text((x + 46, y - 1 + j * 26), t, fill=COL['ink'], font=f3)
        y += 26 * len(lines) + 16
    d.text((30, H + pad_top - 40), STAMP, fill=(176, 0, 106), font=f2)
    canvas.save(out)
    return out


LEGEND = [([0.91, 0.84, 0.66], 'Native 4HP panel PCB (kicad-cli STEP)'),
          ([0.30, 0.58, 0.36], 'Native carrier PCB, 100.5 x 40 x 1.6\n(unrouted; parked SMD not shown)'),
          ([0.90, 0.55, 0.23], 'Two plain M3 L brackets (copied)'),
          ([0.75, 0.77, 0.80], 'M3x8 screws / M3 nuts (proxies)'),
          ([0.15, 0.15, 0.17], 'J2/J3 2x8 box headers (THT, KiCad model)'),
          ([0.85, 0.15, 0.15], 'D8/D16/D17/D18 3 mm LEDs (THT)'),
          ([0.32, 0.45, 0.68], 'C5/C34/C35/C36 cans (SMT)\nPROVISIONAL height context'),
          ([0.55, 0.58, 0.63], 'J1 USB-C / SW1 reset (SMT):\ndrawing envelopes, no model'),
          ([0.95, 0.72, 0.29], 'PROPOSAL: mated IDC plug envelope'),
          ([0.62, 0.66, 0.74], 'PROPOSAL: ribbon leaving +Z to bus'),
          ([0.85, 0.0, 0.0], 'CONFLICT: clip strain relief\nworst case X20.4 > 20.0'),
          ([0.23, 0.65, 0.79], 'Tool paths: M3 nut driver / pliers'),
          ([0.75, 0.75, 0.75], 'Case rail section (context)')]


def main():
    texts, holes, parts = native()
    pages = [front_sheet(texts, holes), side_sheet(parts), top_sheet()]
    raw = iso('iso-front', [230, -120, 90], [10, 22, -64], size=(1700, 1500))
    compose(raw, OUT / 'iso-front.png', 'usb-power-45w M1 - 3D assembly, front-right (F side)',
            ['Actual common-frame geometry: native panel + carrier STEP, brackets, M3 hardware, envelopes.',
             'X across 4HP (20.0), Y down, Z into the case. Carrier perpendicular at B.Cu X2.5 / F.Cu X4.1.',
             'Unrouted. Only J1, SW1, 4 LEDs, J2/J3 and 4 provisional cans are on the board.'], LEGEND)
    raw = iso('iso-rear', [-230, 110, 90], [10, 22, -64], size=(1700, 1500))
    compose(raw, OUT / 'iso-rear.png', 'usb-power-45w M1 - 3D assembly, rear-left (B side, brackets)',
            ['Both L brackets on the carrier B face; M3 side screws from -X (flush heads), nuts on F.Cu.',
             'Panel M3 screws from the front, nuts on the bracket foot. Ribbon envelopes leave toward +Z.',
             'Rails shown translucent for context only.'], LEGEND)
    # Isometric sheet into the PDF.
    iso_svg = OUT / 'iso-sheet.svg'
    iso_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="420mm" height="297mm" '
                       'viewBox="0 0 420 297"><rect width="420" height="297" fill="white"/>'
                       f'<image x="5" y="5" width="410" height="140" preserveAspectRatio="xMidYMid meet" xlink:href="iso-front.png"/>'
                       f'<image x="5" y="150" width="410" height="140" preserveAspectRatio="xMidYMid meet" xlink:href="iso-rear.png"/></svg>\n')
    subprocess.run(['rsvg-convert', '-f', 'pdf', '-o', str(OUT / 'iso-sheet.pdf'), str(iso_svg)], check=True, cwd=OUT)
    pages.append(OUT / 'iso-sheet.pdf')
    subprocess.run(['pdfunite'] + [str(p) for p in pages] + [str(OUT / 'usb-power-45w-mechanical-preview.pdf')], check=True)
    for p in pages:
        p.unlink()
    iso_svg.unlink()
    print('\n'.join(str(p) for p in sorted(OUT.iterdir())))


if __name__ == '__main__':
    main()
