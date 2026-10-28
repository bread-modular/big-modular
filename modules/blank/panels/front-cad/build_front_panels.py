"""Generate the 3D-printable blank 2/4/6/8 HP front panels with FreeCAD.

Run headless from modules/blank:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panels.py

Outline and NPTH rail holes are read from each native panel PCB
(../front-pcb/blank-<n>hp.kicad_pcb) and asserted against docs/geometry.json, so the
prints cannot drift from the PCB panels. Thickness is panel_print_thickness_mm (2.0 mm).
CAD frame: X across, Y = 128.5 - panel Y (origin lower left seen from +Z), Z0..t with
the +Z face as the panel FRONT. Holes are nominal, without print compensation; ream
to size after printing. Nominal geometry only, no physical-fit or strength claim.
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

GEO = json.loads((MODULE / 'docs/geometry.json').read_text())


def xy(node):
    return float(node[1]), float(node[2])


def panel_geometry(pcb):
    tree = parse(pcb.read_text())
    pts = []
    for kind in ('gr_line', 'gr_rect'):
        for item in nodes(tree, kind):
            if one(item, 'layer')[1] == 'Edge.Cuts':
                pts += [xy(one(item, 'start')), xy(one(item, 'end'))]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    holes = []
    for fp in nodes(tree, 'footprint'):
        fx, fy = xy(one(fp, 'at'))
        mech = next(p[2] for p in nodes(fp, 'property') if p[1] == 'MechanicalID')
        for pad in nodes(fp, 'pad'):
            assert pad[2] == 'np_thru_hole', 'passive panel must carry only NPTH holes'
            holes.append((mech, round(fx - x0, 3), round(fy - y0, 3), float(one(pad, 'drill')[1])))
    return {'size': (round(x1 - x0, 3), round(y1 - y0, 3)), 'holes': holes}


def check_contract(spec, g):
    assert list(g['size']) == [spec['width_mm'], GEO['panel_height_mm']], g['size']
    d = GEO['rail_hole_diameter_mm']
    want = [(x, y, d) for x in spec['rail_hole_X_mm'] for y in GEO['rail_hole_Y_mm']]
    got = [h[1:] for h in g['holes']]
    assert sorted(got) == sorted(want), (sorted(got), sorted(want))


def build(spec):
    name = f"{spec['name']}-front-panel"
    g = panel_geometry(HERE.parent / f"front-pcb/{spec['name']}.kicad_pcb")
    check_contract(spec, g)
    thickness = GEO['panel_print_thickness_mm']
    width, height = g['size']
    doc = App.newDocument(name.replace('-', '_'))
    plate = Part.makeBox(width, height, thickness)
    holes = [Part.makeCylinder(d / 2, thickness + 2, App.Vector(x, height - y, -1))
             for _, x, y, d in g['holes']]
    blank = plate.cut(Part.makeCompound(holes))
    hole_volume = thickness * sum(math.pi * (d / 2) ** 2 for *_, d in g['holes'])
    assert math.isclose(blank.Volume, width * height * thickness - hole_volume, rel_tol=1e-6)
    shape = blank.removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    obj = doc.addObject('Part::Feature', 'FrontPanel')
    obj.Shape = shape
    doc.recompute()
    doc.saveAs(str(HERE / f'{name}.FCStd'))
    shape.exportStep(str(HERE / f'{name}.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{name}.stl'))
    App.closeDocument(doc.Name)
    return {'name': name, 'panel_mm': [width, height, thickness], 'holes': g['holes'],
            'volume_mm3': round(shape.Volume, 3), 'mesh_facets': mesh.CountFacets}


print(json.dumps([build(spec) for spec in GEO['panels']], indent=2))
