"""Generate the 3D-printable usb-power front panel with FreeCAD (no labels).

Run headless from modules/usb-power:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py

Outline, NPTH holes and the USB aperture are read from the native panel PCB
(../front-pcb/usb-power-panel.kicad_pcb) and asserted against
docs/assembly-geometry.json, so the print cannot drift from the PCB panel.
Thickness stays at the panel contract (1.6 mm): the bracket foot seats on the
panel rear face at Z1.6, and the USB mouth recess / SW1 button depth assume it.
CAD frame: X across, Y = 128.5 - panel Y (origin upper left seen from +Z),
Z0..1.6 with the +Z face as the panel FRONT. Holes are nominal, without print
compensation; ream/drill to size after printing. Nominal geometry only, no
physical-fit or strength qualification.
"""
import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
MODULE = HERE.parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from sexp import nodes, one, parse, walk  # noqa: E402

PCB = HERE.parent / 'front-pcb/usb-power-panel.kicad_pcb'
NAME = 'usb-power-front-panel'


def xy(node):
    return float(node[1]), float(node[2])


def panel_geometry():
    tree = parse(PCB.read_text())
    edges = []
    for kind in ('gr_line', 'gr_arc'):
        for item in nodes(tree, kind):
            if one(item, 'layer')[1] != 'Edge.Cuts':
                continue
            points = [xy(one(item, key)) for key in ('start', 'mid', 'end') if one(item, key)]
            edges.append((kind, points))
    xs = [p[0] for _, pts in edges for p in pts]
    ys = [p[1] for _, pts in edges for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    on_outer = lambda p: math.isclose(p[0], x0) or math.isclose(p[0], x1) or \
        math.isclose(p[1], y0) or math.isclose(p[1], y1)
    inner = [(k, pts) for k, pts in edges if not all(on_outer(p) for p in pts)]
    ix = [p[0] for _, pts in inner for p in pts]
    iy = [p[1] for _, pts in inner for p in pts]
    arcs = [pts for k, pts in inner if k == 'gr_arc']
    assert len(arcs) == 4, 'expected one rounded-rectangle USB aperture'
    # Corner arc radius = chord from start to end over sqrt(2) for a 90-degree arc.
    radius = round(math.dist(arcs[0][0], arcs[0][2]) / math.sqrt(2), 3)
    holes = []
    for fp in nodes(tree, 'footprint'):
        fx, fy = xy(one(fp, 'at'))
        mech = next(p[2] for p in nodes(fp, 'property') if p[1] == 'MechanicalID')
        for pad in nodes(fp, 'pad'):
            assert pad[2] == 'np_thru_hole', 'passive panel must carry only NPTH holes'
            holes.append((mech, round(fx - x0, 3), round(fy - y0, 3), float(one(pad, 'drill')[1])))
    return {
        'size': (round(x1 - x0, 3), round(y1 - y0, 3)),
        'aperture': (round(min(ix) - x0, 3), round(min(iy) - y0, 3),
                     round(max(ix) - min(ix), 3), round(max(iy) - min(iy), 3), radius),
        'holes': sorted(holes),
    }


def check_contract(g):
    c = json.loads((MODULE / 'docs/assembly-geometry.json').read_text())
    assert list(g['size']) == c['panel_mm'][:2], g['size']
    assert all(math.isclose(a, b) for a, b in zip(g['aperture'], c['aperture_XYWHR_mm'])), g['aperture']
    want = sorted(map(tuple, c['rail_holes_mm'] + c['panel_bracket_holes_mm']
                      + [c['reset_XY_diameter_mm']] + [l['panel_XY_diameter_mm'] for l in c['LEDs']]))
    assert sorted(h[1:] for h in g['holes']) == want, g['holes']
    return c['panel_mm'][2]


def build():
    g = panel_geometry()
    thickness = check_contract(g)
    width, height = g['size']
    doc = App.newDocument(NAME.replace('-', '_'))
    plate = doc.addObject('Part::Box', 'Plate')
    plate.Length, plate.Width, plate.Height = width, height, thickness
    cutters = []

    def cylinder(label, x, y, d):
        cyl = doc.addObject('Part::Cylinder', label)
        cyl.Radius, cyl.Height = d / 2, thickness + 2
        cyl.Placement.Base = App.Vector(x, height - y, -1)
        cutters.append(cyl)

    def box(label, x, y, w, h):
        b = doc.addObject('Part::Box', label)
        b.Length, b.Width, b.Height = w, h, thickness + 2
        b.Placement.Base = App.Vector(x, y, -1)
        cutters.append(b)

    for mech, x, y, d in g['holes']:
        cylinder(f'Hole_{mech}', x, y, d)
    ax, ay, aw, ah, r = g['aperture']
    ay = height - ay - ah  # aperture bottom edge in the CAD frame
    box('USB_X', ax, ay + r, aw, ah - 2 * r)
    box('USB_Y', ax + r, ay, aw - 2 * r, ah)
    for i, (cx, cy) in enumerate([(ax + r, ay + r), (ax + aw - r, ay + r),
                                  (ax + r, ay + ah - r), (ax + aw - r, ay + ah - r)], 1):
        cyl = doc.addObject('Part::Cylinder', f'USB_R{i}')
        cyl.Radius, cyl.Height = r, thickness + 2
        cyl.Placement.Base = App.Vector(cx, cy, -1)
        cutters.append(cyl)
    tools = doc.addObject('Part::MultiFuse', 'Cutouts')
    tools.Shapes = cutters
    panel = doc.addObject('Part::Cut', 'FrontPanel')
    panel.Base, panel.Tool = plate, tools
    doc.recompute()
    shape = panel.Shape
    assert shape.isValid() and len(shape.Solids) == 1
    expected = width * height * thickness - thickness * (
        sum(math.pi * (d / 2) ** 2 for *_, d in g['holes']) + aw * ah - (4 - math.pi) * r * r)
    assert math.isclose(shape.Volume, expected, rel_tol=1e-6), (shape.Volume, expected)
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    shape.exportStep(str(HERE / f'{NAME}.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{NAME}.stl'))
    print(json.dumps({'panel_mm': [width, height, thickness], 'aperture_XYWHR_mm': g['aperture'],
                      'holes': g['holes'], 'volume_mm3': round(shape.Volume, 3),
                      'mesh_facets': mesh.CountFacets}, indent=2))


build()
