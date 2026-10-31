"""Generate the usb-power-45w panel-to-carrier L bracket with FreeCAD (print two).

Run headless from the repository root:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd modules/usb-power-45w/panels/bracket/build_bracket.py

Same plain L as modules/usb-power/panels/bracket (dimensions unchanged; shape in
tools/bracket45.py). Writes .FCStd (editable), .step (assembly orientation) and .stl
(laid on the L profile, 10 mm print height). Nominal geometry; measure the web
(<= 2.40 mm) and bore fit after printing. No physical-fit or strength qualification.
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
from bracket45 import bracket_shape, contract  # noqa: E402

NAME = 'usb-power-45w-bracket'
c = contract()
shape = bracket_shape(Part, App, c)
doc = App.newDocument(NAME.replace('-', '_'))
obj = doc.addObject('Part::Feature', 'Bracket')
obj.Shape = shape
flat = shape.copy()
flat.Placement = App.Placement(App.Vector(0, c['depth_z'], 0), App.Rotation(App.Vector(1, 0, 0), 90))
printed = doc.addObject('Part::Feature', 'BracketPrintOrientation')
printed.Shape = flat
doc.recompute()
bb = flat.BoundBox
assert math.isclose(bb.ZMin, 0, abs_tol=1e-9) and math.isclose(bb.ZLength, c['width_y'])
doc.saveAs(str(HERE / f'{NAME}.FCStd'))
shape.exportStep(str(HERE / f'{NAME}.step'))
mesh = MeshPart.meshFromShape(Shape=flat, LinearDeflection=0.01, AngularDeflection=0.1)
assert mesh.isSolid() and not mesh.hasNonManifolds()
mesh.write(str(HERE / f'{NAME}.stl'))
print(json.dumps({'bracket_mm': c, 'volume_mm3': round(shape.Volume, 3),
                  'print_bbox_mm': [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)]}, indent=1))
