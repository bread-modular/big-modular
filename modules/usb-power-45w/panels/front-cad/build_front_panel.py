"""Generate the 3D-printable usb-power-45w 4HP front panel with FreeCAD (no labels).

Run headless from modules/usb-power-45w:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py

Outline, NPTH holes and the USB aperture are read from the native panel PCB
(../front-pcb/usb-power-45w-panel.kicad_pcb) and asserted against
docs/mechanical-geometry.json, so the print cannot drift from the PCB panel.
Thickness stays at the panel contract (1.6 mm), as modules/usb-power: the bracket
foot seats on the panel rear face at Z1.6 (tools/bracket45.py), and the USB mouth
and SW1 RESET depth assume it.
CAD frame: X across, Y = 128.5 - panel Y (origin lower left seen from +Z),
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
from sexp import nodes, one, parse  # noqa: E402

PCB = HERE.parent / 'front-pcb/usb-power-45w-panel.kicad_pcb'
NAME = 'usb-power-45w-front-panel'
PANEL_LEDS = ('D8',)  # S8: MAIN is the only panel LED; D16-D18 stay in the contract history


def xy(node):
    return float(node[1]), float(node[2])


def panel_geometry():
    tree = parse(PCB.read_text())
    rects = [r for r in nodes(tree, 'gr_rect') if one(r, 'layer')[1] == 'Edge.Cuts']
    assert len(rects) == 1, 'expected one Edge.Cuts rectangle as the outline'
    (ax0, ay0), (ax1, ay1) = xy(one(rects[0], 'start')), xy(one(rects[0], 'end'))
    x0, y0, x1, y1 = min(ax0, ax1), min(ay0, ay1), max(ax0, ax1), max(ay0, ay1)
    inner = []
    for kind in ('gr_line', 'gr_arc'):
        for item in nodes(tree, kind):
            if one(item, 'layer')[1] != 'Edge.Cuts':
                continue
            points = [xy(one(item, key)) for key in ('start', 'mid', 'end') if one(item, key)]
            inner.append((kind, points))
    ix = [p[0] for _, pts in inner for p in pts]
    iy = [p[1] for _, pts in inner for p in pts]
    arcs = [pts for k, pts in inner if k == 'gr_arc']
    assert len(arcs) == 4 and len(inner) == 8, 'expected one rounded-rectangle USB aperture'
    # Corner arc radius = chord from start to end over sqrt(2) for a 90-degree arc.
    radius = round(math.dist(arcs[0][0], arcs[0][2]) / math.sqrt(2), 3)
    holes = []
    for fp in nodes(tree, 'footprint'):
        fx, fy = xy(one(fp, 'at'))
        mech = next(p[2] for p in nodes(fp, 'property') if p[1] == 'MechanicalID')
        for pad in nodes(fp, 'pad'):
            assert pad[2] == 'np_thru_hole' and pad[3] == 'circle', 'passive panel: round NPTH only'
            assert xy(one(pad, 'at')) == (0, 0), 'panel pads sit on the footprint origin'
            holes.append((mech, round(fx - x0, 3), round(fy - y0, 3), float(one(pad, 'drill')[1])))
    return {
        'size': (round(x1 - x0, 3), round(y1 - y0, 3)),
        'aperture': (round(min(ix) - x0, 3), round(min(iy) - y0, 3),
                     round(max(ix) - min(ix), 3), round(max(iy) - min(iy), 3), radius),
        'holes': sorted(holes),
    }


def check_contract(g):
    c = json.loads((MODULE / 'docs/mechanical-geometry.json').read_text())
    assert list(g['size']) == c['panel_mm'][:2], g['size']
    assert all(math.isclose(a, b) for a, b in zip(g['aperture'], c['aperture_XYWHR_mm'])), g['aperture']
    leds = [l['panel_XY_diameter_mm'] for l in c['LEDs'] if l['reference'] in PANEL_LEDS]
    want = sorted(map(tuple, c['rail_holes_mm'] + c['panel_bracket_holes_mm']
                      + [c['reset_XY_diameter_mm']] + leds))
    assert sorted(h[1:] for h in g['holes']) == want, (g['holes'], want)
    return c['panel_mm'][2]


def build():
    g = panel_geometry()
    thickness = check_contract(g)
    width, height = g['size']
    doc = App.newDocument(NAME.replace('-', '_'))
    plate = Part.makeBox(width, height, thickness)
    cutters = [Part.makeCylinder(d / 2, thickness + 2, App.Vector(x, height - y, -1))
               for _, x, y, d in g['holes']]
    ax, ay, aw, ah, r = g['aperture']
    ay = height - ay - ah  # aperture bottom edge in the CAD frame
    cutters += [Part.makeBox(aw, ah - 2 * r, thickness + 2, App.Vector(ax, ay + r, -1)),
                Part.makeBox(aw - 2 * r, ah, thickness + 2, App.Vector(ax + r, ay, -1))]
    cutters += [Part.makeCylinder(r, thickness + 2, App.Vector(cx, cy, -1))
                for cx in (ax + r, ax + aw - r) for cy in (ay + r, ay + ah - r)]
    shape = plate.cut(Part.makeCompound(cutters)).removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    expected = width * height * thickness - thickness * (
        sum(math.pi * (d / 2) ** 2 for *_, d in g['holes']) + aw * ah - (4 - math.pi) * r * r)
    assert math.isclose(shape.Volume, expected, rel_tol=1e-6), (shape.Volume, expected)
    obj = doc.addObject('Part::Feature', 'FrontPanel')
    obj.Shape = shape
    doc.recompute()
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    shape.exportStep(str(HERE / f'{NAME}.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{NAME}.stl'))
    print(json.dumps({'panel_mm': [width, height, thickness], 'aperture_XYWHR_mm': g['aperture'],
                      'holes': g['holes'], 'volume_mm3': round(shape.Volume, 3),
                      'mesh_facets': mesh.CountFacets}, indent=2))


build()
