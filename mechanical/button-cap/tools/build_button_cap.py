"""Generate the two-piece 3D-printable push-button cap (plunger + press-on head) with FreeCAD.

Run headless from the repository root (or use tools/build_button_cap.sh):
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd mechanical/button-cap/tools/build_button_cap.py

Every module with a push button uses the modules/8bit stack: a 6 x 6 x 7 mm THT tact switch on
the carrier F side, its stem top 3.0 mm below the panel rear, a Ø4.2 panel hole. The one-piece
modules/8bit cap (panels/button-actuator) only shows a Ø3.6 tip 1.9 mm proud of the panel, which
is small and sharp under the finger. This set keeps that cap's rear half and adds a wide head in
front of the panel:

- PLUNGER: the modules/8bit cap (socket on the switch stem, Ø7 flange captive behind the panel)
  with the Ø3.6 tip lengthened to Z15.0. Printed socket-down, as before.
- HEAD: a Ø8 (`wide`) or Ø6.5 (`slim`) disc, 3.4 mm tall, pressed onto the tip from the front
  after the panel is on. Its Ø4.0 socket has three crush ribs on a Ø3.3 circle that bite the
  Ø3.6 tip; the tip bottoms on the socket roof, which sets the height: 1.0 mm (FR4) / 0.6 mm
  (2.0 mm print) between the head and the panel front, more than the ~0.25 mm switch travel.
  Printed top-face-down, so the finger face is the smooth bed face; no supports.

Assembly: press the plunger onto the soldered switch, fit the panel over the tip, press the head
on. Pull the head off to take the panel off again.

Frame: Z0 = carrier F.Cu, +Z toward the panel (docs/geometry.json of the modules). The stack
comes from modules/8bit/docs/geometry.json and is asserted against every module that has a
button. Nominal geometry: nothing here is test-printed; the crush ribs are there because FDM
holes print undersize, tune RIB_D if the head is loose or will not go on.
Outputs: print/button-plunger.stl, print/button-head-{wide,slim}.stl (print orientation),
cad/button-cap-{wide,slim}.step (plunger + head, assembled frame), cad/dimensions.json.
"""
import json
import math
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parents[1]
GEO8 = json.loads((ROOT / 'modules/8bit/docs/geometry.json').read_text())
V = App.Vector

TRAVEL = 0.25           # switch travel, nominal
# Plunger = modules/8bit cap with a longer tip.
OLD = GEO8['button_actuator']['cap']
SOCKET_D, SOCKET_Z = OLD['socket_D'], OLD['socket_Z']
FLANGE_D, FLANGE_Z = OLD['body_D'], OLD['body_Z']
TIP_D = OLD['tip_D']
TIP_Z = [FLANGE_Z[1], 15.0]
TIP_CHAMFER = 0.3
# Head.
HEADS = {'wide': 8.0, 'slim': 6.5}
HEAD_Z = [12.6, 16.0]
HEAD_SOCKET_D = 4.0     # clear of the tip; the ribs do the gripping
RIB_D = 3.3             # circle the three rib faces lie on (tip Ø3.6: 0.15 mm crush per rib;
                        # was 3.5, the first print (2026-11-18) pulled off too easily)
RIB_W = 0.7
RIB_Z0 = HEAD_Z[0] + 0.4
MOUTH_CHAMFER = 0.3
TOP_CHAMFER = 0.8       # finger face edge (on the bed)
BOTTOM_CHAMFER = 0.3
# Neighbours in front of the panel (radii, nominal).
LED_HOLE_R = 1.6
JACK_NUT_R = 4.62       # 8 mm across-flats hex nut, corner radius (not measured)
KNOB_R = {'wide': 8.0, 'slim': 6.5, 'slimmer': 5.75, 'slimmest': 5.0}   # mechanical/knobs bases


def revolve(profile):
    pts = [V(r, 0, z) for r, z in profile]
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return face.revolve(V(0, 0, 0), V(0, 0, 1), 360)


def plunger():
    rs, rf, rt, c = SOCKET_D / 2, FLANGE_D / 2, TIP_D / 2, TIP_CHAMFER
    return revolve([(rs, SOCKET_Z[0]), (rf, FLANGE_Z[0]), (rf, FLANGE_Z[1]), (rt, TIP_Z[0]),
                    (rt, TIP_Z[1] - c), (rt - c, TIP_Z[1]), (0, TIP_Z[1]), (0, SOCKET_Z[1]),
                    (rs, SOCKET_Z[1])])


def head(d):
    r, rs = d / 2, HEAD_SOCKET_D / 2
    z0, z1 = HEAD_Z
    roof = TIP_Z[1]
    body = revolve([(rs + MOUTH_CHAMFER, z0), (r - BOTTOM_CHAMFER, z0), (r, z0 + BOTTOM_CHAMFER),
                    (r, z1 - TOP_CHAMFER), (r - TOP_CHAMFER, z1), (0, z1), (0, roof), (rs, roof),
                    (rs, z0 + MOUTH_CHAMFER)])
    for i in range(3):
        rib = Part.makeBox(rs + 0.2 - RIB_D / 2, RIB_W, roof - RIB_Z0, V(RIB_D / 2, -RIB_W / 2, RIB_Z0))
        rib.rotate(V(0, 0, 0), V(0, 0, 1), 120 * i)
        body = body.fuse(rib)
    return body.removeSplitter()


def check_stack():
    st = GEO8['stack_Z_mm']
    rear = st['panel_rear_seat']
    fronts = {'FR4': rear + GEO8['panel_pcb_thickness_mm'], 'print': rear + GEO8['panel_print_thickness_mm']}
    hole = GEO8['panel_hole_diameters_mm']['button']
    assert SOCKET_Z[1] == st['switch_stem_top'] and FLANGE_Z[1] < rear, 'plunger = modules/8bit cap'
    assert TIP_D <= hole - 0.5, 'tip clearance in the panel hole'
    assert FLANGE_D >= hole + 2.0, 'the flange must be captive behind the panel'
    gaps = {k: round(HEAD_Z[0] - z, 2) for k, z in fronts.items()}
    assert min(gaps.values()) >= TRAVEL + 0.3, gaps
    grip = round(TIP_Z[1] - RIB_Z0, 2)
    assert grip >= 1.8, 'rib grip length on the tip'
    assert HEAD_Z[1] - TIP_Z[1] >= 1.0, 'head roof (finger face) thickness'
    assert HEAD_SOCKET_D - TIP_D >= 0.3 and 0.05 <= TIP_D - RIB_D <= 0.4, 'socket clears the tip, ribs crush'
    assert min(HEADS.values()) / 2 - HEAD_SOCKET_D / 2 >= 1.2, 'head socket wall'
    assert min(HEADS.values()) >= hole + 2.0, 'the head must cover the panel hole'
    return fronts, gaps, grip


def check_modules():
    """Every module with a button: same stack, and what the head comes close to on its panel."""
    rows = []
    for f in sorted((ROOT / 'modules').glob('*/docs/geometry.json')):
        g = json.loads(f.read_text())
        buttons = g.get('buttons') or ([g['button']] if 'button' in g else [])
        if not buttons:
            continue
        name = f.parts[-3]
        assert g['panel_hole_diameters_mm']['button'] == 4.2, name
        st = g.get('stack_Z_mm', {})
        assert st.get('panel_rear_seat', 10.0) == 10.0 and st.get('switch_stem_top', 7.0) == 7.0, name
        assert st.get('switch_body_top', 3.1) + TRAVEL + 0.5 <= FLANGE_Z[0], name
        assert g['panel_pcb_thickness_mm'] == 1.6, name
        width = g['panel_mm'][0]
        near = [('LED', LED_HOLE_R, p['XY']) for p in g.get('leds', [])]
        near += [('jack nut', JACK_NUT_R, p['XY']) for p in g.get('jacks', [])]
        pots = [p.get('shaft_XY') or p.get('XY') for p in g.get('pots', [])]
        for b in buttons:
            x, y = b['XY']
            dist = lambda p: math.hypot(p[0] - x, p[1] - y)
            row = {'module': name, 'ref': b['ref'], 'edge': round(min(x, width - x), 2)}
            for kind, r, p in near:
                row[kind] = round(min(row.get(kind, 99), dist(p) - r), 2)
            if pots:
                row['pot shaft'] = round(min(dist(p) for p in pots), 2)
            others = [dist(o['XY']) for o in buttons if o is not b]
            if others:
                row['button'] = round(min(others), 2)
            rows.append(row)
    assert len(rows) >= 11, 'modules with buttons'
    return rows


def clearances(rows, d):
    """Free gap in front of the panel between a Ø d head and its neighbours, per button."""
    r = d / 2
    out = []
    for row in rows:
        c = {'module': row['module'], 'ref': row['ref'], 'panel edge': round(row['edge'] - r, 2)}
        for k in ('LED', 'jack nut'):
            if k in row:
                c[k] = round(row[k] - r, 2)
        if 'pot shaft' in row:
            for kn, kr in KNOB_R.items():
                c[f'{kn} knob'] = round(row['pot shaft'] - kr - r, 2)
        if 'button' in row:
            c['next head'] = round(row['button'] - d, 2)
        assert c['panel edge'] >= 0.5, c
        assert c.get('LED', 9) >= 0.5 and c.get('jack nut', 9) >= 1.0 and c.get('next head', 9) >= 2.0, c
        assert c.get('slimmest knob', 9) >= 1.0, c
        out.append(c)
    return out


def write_stl(shape, name, flip=False):
    s = shape.copy()
    if flip:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    s.translate(V(0, 0, -s.BoundBox.ZMin))
    mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds(), name
    assert abs(mesh.Volume - shape.Volume) / shape.Volume < 0.01, name
    mesh.write(str(OUT / 'print' / name))
    return round(s.BoundBox.ZLength, 2)


def build():
    fronts, gaps, grip = check_stack()
    rows = check_modules()
    for d in ('print', 'cad'):
        (OUT / d).mkdir(exist_ok=True)
    pl = plunger()
    assert pl.isValid() and len(pl.Solids) == 1
    report = {
        'frame': 'Z0 = carrier F.Cu, +Z toward the panel; mm',
        'panel_front_Z': fronts,
        'plunger': {'socket_D': SOCKET_D, 'socket_Z': SOCKET_Z, 'flange_D': FLANGE_D, 'flange_Z': FLANGE_Z,
                    'tip_D': TIP_D, 'tip_Z': TIP_Z, 'print_height': write_stl(pl, 'button-plunger.stl'),
                    'volume_mm3': round(pl.Volume, 1)},
        'head': {'Z': HEAD_Z, 'socket_D': HEAD_SOCKET_D, 'rib_circle_D': RIB_D, 'rib_grip': grip,
                 'gap_to_panel_front': gaps,
                 'top_above_panel_front': {k: round(HEAD_Z[1] - z, 2) for k, z in fronts.items()}},
        'heads': {},
    }
    for name, d in HEADS.items():
        hd = head(d)
        assert hd.isValid() and len(hd.Solids) == 1, name
        assert hd.common(pl).Volume < 0.6, 'only the rib crush may overlap the tip'
        h = write_stl(hd, f'button-head-{name}.stl', flip=True)
        Part.makeCompound([pl, hd]).exportStep(str(OUT / 'cad' / f'button-cap-{name}.step'))
        report['heads'][name] = {'D': d, 'print_height': h, 'volume_mm3': round(hd.Volume, 1),
                                 'clearances': clearances(rows, d)}
    (OUT / 'cad' / 'dimensions.json').write_text(json.dumps(report, indent=1) + '\n')
    for name, hd in report['heads'].items():
        worst = {}
        for c in hd['clearances']:
            for k, v in c.items():
                if k not in ('module', 'ref') and v < worst.get(k, (99,))[0]:
                    worst[k] = (v, f"{c['module']} {c['ref']}")
        print(name, 'D', hd['D'], 'smallest gaps', worst)
    print('head gap to panel front', gaps, 'rib grip', grip)
    print('BUTTON_CAP_BUILD_PASS')


build()
