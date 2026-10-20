"""Generate the 3D-printable VCA-MIX 6HP front panel with FreeCAD.

Run headless from modules/vca-mix:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py

Outline, NPTH holes and label texts are read from the native panel PCB
(../front-pcb/vca-mix-panel.kicad_pcb) and asserted against docs/geometry.json, so the
print cannot drift from the PCB panel. Labels are engraved 0.4 mm into the front.
Thickness is panel_print_thickness_mm (2.0 mm, stiffer than the 1.6 mm FR4 panel);
the PJ301M-12 threads still leave ~0.5 mm past a 2.0 mm nut (docs/research.md 4); the
RV09 pot stack is an open check (D3).
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

PCB = HERE.parent / 'front-pcb/vca-mix-panel.kicad_pcb'
NAME = 'vca-mix-front-panel'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
ENGRAVE = 0.4


def xy(node):
    return float(node[1]), float(node[2])


def panel_geometry():
    tree = parse(PCB.read_text())
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
    labels = []
    for t in nodes(tree, 'gr_text'):
        if one(t, 'layer')[1] != 'F.SilkS':
            continue
        tx, ty = xy(one(t, 'at'))
        size = float(one(one(one(t, 'effects'), 'font'), 'size')[1])
        labels.append((t[1], round(tx - x0, 3), round(ty - y0, 3), size))
    return {'size': (round(x1 - x0, 3), round(y1 - y0, 3)), 'holes': holes, 'labels': labels}


def check_contract(g):
    c = json.loads((MODULE / 'docs/geometry.json').read_text())
    assert list(g['size']) == c['panel_mm'], g['size']
    d = c['panel_hole_diameters_mm']
    want = [tuple(h) for h in c['rail_holes_mm']]
    want += [(*j['XY'], d['jack']) for j in c['jacks']]
    want += [(*pot['shaft_XY'], d['pot']) for pot in c['pots']]
    got = [h[1:] for h in g['holes']]
    assert sorted(got) == sorted(want), (sorted(got), sorted(want))
    want_labels = sorted((lab['text'], *lab['XY'], lab['size']) for lab in c['panel_labels'])
    assert sorted(g['labels']) == want_labels, g['labels']
    return c['panel_print_thickness_mm']


def label_solid(s, x, y, size, height, top):
    """Engraving tool for one centred label: KiCad text size ~ cap height."""
    wires = Part.makeWireString(s, FONT, size, 0)
    # Build each glyph face with its holes (letters such as A, D, O).
    glyphs = []
    for char in wires:
        if not char:
            continue
        ordered = sorted(char, key=lambda w: Part.Face(w).Area, reverse=True)
        face = Part.Face(ordered[0])
        for inner in ordered[1:]:
            if face.BoundBox.isInside(inner.BoundBox):
                face = face.cut(Part.Face(inner))
            else:
                face = face.fuse(Part.Face(inner))
        glyphs.append(face)
    body = glyphs[0]
    for gface in glyphs[1:]:
        body = body.fuse(gface)
    bb = body.BoundBox
    body.translate(App.Vector(x - (bb.XMin + bb.XMax) / 2, height - y - (bb.YMin + bb.YMax) / 2,
                              top - ENGRAVE))
    return body.extrude(App.Vector(0, 0, ENGRAVE + 1.0))


def build():
    g = panel_geometry()
    thickness = check_contract(g)
    width, height = g['size']
    doc = App.newDocument(NAME.replace('-', '_'))
    plate = Part.makeBox(width, height, thickness)
    holes = [Part.makeCylinder(d / 2, thickness + 2, App.Vector(x, height - y, -1))
             for _, x, y, d in g['holes']]
    blank = plate.cut(Part.makeCompound(holes))
    hole_volume = thickness * sum(math.pi * (d / 2) ** 2 for *_, d in g['holes'])
    assert math.isclose(blank.Volume, width * height * thickness - hole_volume, rel_tol=1e-6)
    tools = [label_solid(s, x, y, size, height, thickness) for s, x, y, size in g['labels']]
    shape = blank.cut(Part.makeCompound(tools)).removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    engraved = blank.Volume - shape.Volume
    assert engraved > 0, 'labels did not engrave'
    obj = doc.addObject('Part::Feature', 'FrontPanel')
    obj.Shape = shape
    doc.recompute()
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    shape.exportStep(str(HERE / f'{NAME}.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{NAME}.stl'))
    print(json.dumps({'panel_mm': [width, height, thickness], 'holes': g['holes'],
                      'labels': g['labels'], 'engraved_mm3': round(engraved, 3),
                      'volume_mm3': round(shape.Volume, 3), 'mesh_facets': mesh.CountFacets},
                     indent=2))


build()
