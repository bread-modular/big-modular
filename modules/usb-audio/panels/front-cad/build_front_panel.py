"""Generate the 3D-printable USB-AUDIO 6HP front panel with FreeCAD.

Run headless from modules/usb-audio:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py

Outline and NPTH holes are read from the native panel PCB
(../front-pcb/usb-audio-panel.kicad_pcb) and asserted against docs/geometry.json, so the
print cannot drift from the PCB panel. Plain panel: no labels (3D printed, the
FR4 panel silk legend is not carried over).
Thickness is panel_print_thickness_mm (2.0 mm, stiffer than the 1.6 mm FR4 panel);
the PJ301M-12 threads still leave ~0.5 mm past a 2.0 mm nut (as modules/midi); the
RV09 pots take no nut.
The USB-C shell stands 0.9 mm proud of this print (1.3 mm on FR4, docs/geometry.json).
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

PCB = HERE.parent / 'front-pcb/usb-audio-panel.kicad_pcb'
NAME = 'usb-audio-front-panel'
PRINT_THICKNESS = 2.0  # as modules/midi panel_print_thickness_mm


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
        at = one(fp, 'at')
        fx, fy = xy(at)
        fangle = float(at[3]) if len(at) > 3 else 0.0
        mech = next(p[2] for p in nodes(fp, 'property') if p[1] == 'MechanicalID')
        for pad in nodes(fp, 'pad'):
            assert pad[2] == 'np_thru_hole', 'passive panel must carry only NPTH holes'
            pat = one(pad, 'at')
            px, py = xy(pat)
            assert px == 0 and py == 0, 'panel pads sit on the footprint origin'
            angle = (fangle + (float(pat[3]) if len(pat) > 3 else 0.0)) % 180
            drill = one(pad, 'drill')
            if pad[3] == 'circle':
                w = h = float(drill[1])
            else:
                assert pad[3] == 'oval' and drill[1] == 'oval', pad
                w, h = float(drill[2]), float(drill[3])
            holes.append((mech, round(fx - x0, 3), round(fy - y0, 3), w, h, angle))
    return {'size': (round(x1 - x0, 3), round(y1 - y0, 3)), 'holes': holes}


def check_contract(g):
    c = json.loads((MODULE / 'docs/geometry.json').read_text())
    assert list(g['size']) == c['panel_mm'], g['size']
    d = c['panel_hole_diameters_mm']
    want = [tuple(h) for h in c['rail_holes_mm']]
    want += [(*j['XY'], d['jack']) for j in c['jacks']]
    want += [(*p['shaft_XY'], d['pot']) for p in c['pots']]
    got = [(x, y, w) for _, x, y, w, h, _ in g['holes'] if w == h]
    assert sorted(got) == sorted(want), (sorted(got), sorted(want))
    slot = c['usb_slot']
    slots = [(x, y, w, h, a) for _, x, y, w, h, a in g['holes'] if w != h]
    assert slots == [(*slot['XY'], *slot['size_mm'], 0.0)], slots
    return c.get('panel_print_thickness_mm', PRINT_THICKNESS)


def hole_solid(x, y, w, h, angle, thickness):
    """Through cutter: a cylinder, or a stadium slot (oval NPTH) along its long axis."""
    if w == h:
        return Part.makeCylinder(w / 2, thickness + 2, App.Vector(x, y, -1))
    r, length = min(w, h) / 2, max(w, h) - min(w, h)
    slot = Part.makeBox(length, 2 * r, thickness + 2, App.Vector(-length / 2, -r, -1))
    for end in (-length / 2, length / 2):
        slot = slot.fuse(Part.makeCylinder(r, thickness + 2, App.Vector(end, 0, -1)))
    # KiCad angles turn counter-clockwise on screen (Y down); the CAD Y axis is flipped.
    rot = (angle + (90 if h > w else 0)) % 180
    slot.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), -rot)
    slot.translate(App.Vector(x, y, 0))
    return slot.removeSplitter()


def hole_area(w, h):
    r = min(w, h) / 2
    return math.pi * r ** 2 + 2 * r * (max(w, h) - min(w, h))


def build():
    g = panel_geometry()
    thickness = check_contract(g)
    width, height = g['size']
    doc = App.newDocument(NAME.replace('-', '_'))
    plate = Part.makeBox(width, height, thickness)
    holes = [hole_solid(x, height - y, w, h, a, thickness) for _, x, y, w, h, a in g['holes']]
    blank = plate.cut(Part.makeCompound(holes))
    hole_volume = thickness * sum(hole_area(w, h) for _, _, _, w, h, _ in g['holes'])
    assert math.isclose(blank.Volume, width * height * thickness - hole_volume, rel_tol=1e-6)
    shape = blank.removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    obj = doc.addObject('Part::Feature', 'FrontPanel')
    obj.Shape = shape
    doc.recompute()
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    shape.exportStep(str(HERE / f'{NAME}.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{NAME}.stl'))
    print(json.dumps({'panel_mm': [width, height, thickness], 'holes': g['holes'],
                      'volume_mm3': round(shape.Volume, 3), 'mesh_facets': mesh.CountFacets},
                     indent=2))


build()
