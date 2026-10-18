"""Generate the 3D-printable usb-power panel-to-carrier L bracket with FreeCAD.

Run headless from modules/usb-power:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/bracket/build_bracket.py

Same plain L as hardware/mechanics/corner_braces.scad; every dimension comes
from the `brackets` contract in docs/assembly-geometry.json. Print two. Local
frame: X across (foot to X9.2), Y = bracket width (10), Z from the panel rear
face (foot Z0..3, web X0..2.4 up to Z18.4). Front/panel M3 hole along Z at
X6.3; side/carrier M3 hole along X at Z13.4 with a 90-degree countersink on the
outer (X0) face for an M3x8 flat head. No nut traps or inserts; loose M3 nuts.
The STL is laid on the L profile (Y up = 10 mm print height), matching the
SCAD print arrangement. Nominal geometry; measure the web (<= 2.40 mm) and bore
fit after printing. No physical-fit or strength qualification.
"""
import json
import math
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
MODULE = HERE.parents[1]
NAME = 'usb-power-bracket'


def contract():
    b = json.loads((MODULE / 'docs/assembly-geometry.json').read_text())['brackets']
    x0, x1 = b['outer_X_mm']
    z0, z1 = b['outer_Z_mm']
    web = b['side_web_X_mm']
    foot = b['front_foot_Z_mm']
    assert math.isclose(web[1] - web[0], b['web_mm']) and math.isclose(foot[1] - foot[0], b['wall_mm'])
    return {
        'width_x': round(x1 - x0, 3), 'width_y': b['width_Y_mm'], 'depth_z': round(z1 - z0, 3),
        'foot': b['wall_mm'], 'web': b['web_mm'], 'hole': b['hole_mm'],
        'front_x': round(b['front_hole_X_mm'] - x0, 3), 'side_z': round(b['side_hole_Z_mm'] - z0, 3),
        'sink_d': b['side_countersink_diameter_mm'],
        # 90-degree countersink depth = (head diameter - clearance) / 2.
        'sink_depth': round((b['side_countersink_diameter_mm'] - b['hole_mm']) / 2, 3),
        'quantity': b['quantity'],
    }


def build():
    c = contract()
    doc = App.newDocument(NAME.replace('-', '_'))
    foot = doc.addObject('Part::Box', 'Foot')
    foot.Length, foot.Width, foot.Height = c['width_x'], c['width_y'], c['foot']
    web = doc.addObject('Part::Box', 'Web')
    web.Length, web.Width, web.Height = c['web'], c['width_y'], c['depth_z']
    body = doc.addObject('Part::MultiFuse', 'L')
    body.Shapes = [foot, web]

    front = doc.addObject('Part::Cylinder', 'PanelHole')
    front.Radius, front.Height = c['hole'] / 2, c['foot'] + 0.2
    front.Placement.Base = App.Vector(c['front_x'], c['width_y'] / 2, -0.1)
    side = doc.addObject('Part::Cylinder', 'CarrierHole')
    side.Radius, side.Height = c['hole'] / 2, c['web'] + 0.2
    side.Placement = App.Placement(App.Vector(-0.1, c['width_y'] / 2, c['side_z']),
                                   App.Rotation(App.Vector(0, 1, 0), 90))
    sink = doc.addObject('Part::Cone', 'Countersink')
    sink.Radius1, sink.Radius2, sink.Height = c['sink_d'] / 2, c['hole'] / 2, c['sink_depth']
    sink.Placement = App.Placement(App.Vector(0, c['width_y'] / 2, c['side_z']),
                                   App.Rotation(App.Vector(0, 1, 0), 90))
    tools = doc.addObject('Part::MultiFuse', 'Holes')
    tools.Shapes = [front, side, sink]
    bracket = doc.addObject('Part::Cut', 'Bracket')
    bracket.Base, bracket.Tool = body, tools
    # Print orientation: lay the L profile on the bed (local Y becomes height).
    printed = doc.addObject('Part::Feature', 'BracketPrintOrientation')
    doc.recompute()
    shape = bracket.Shape
    assert shape.isValid() and len(shape.Solids) == 1
    assert c['web'] - c['sink_depth'] >= 1.5, 'insufficient material behind countersink'
    flat = shape.copy()
    flat.Placement = App.Placement(App.Vector(0, c['depth_z'], 0), App.Rotation(App.Vector(1, 0, 0), 90))
    printed.Shape = flat
    printed.Visibility = False
    doc.recompute()
    bb = flat.BoundBox
    assert math.isclose(bb.ZMin, 0, abs_tol=1e-9) and math.isclose(bb.ZLength, c['width_y'])
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    shape.exportStep(str(HERE / f'{NAME}.step'))
    mesh = MeshPart.meshFromShape(Shape=flat, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{NAME}.stl'))
    print(json.dumps({'bracket_mm': c, 'volume_mm3': round(shape.Volume, 3),
                      'print_bbox_mm': [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)],
                      'mesh_facets': mesh.CountFacets}, indent=2))


build()
