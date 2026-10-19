"""Generate the nominal tall-trimmer pot 3D proxy (FreeCAD, headless).

Run from modules/imix:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd tools/build_pot_model.py

Writes hardware/IMIX.3dshapes/RV09_vertical_proxy.step in the footprint frame of
Potentiometer_RV09 (STEP X = footprint X, STEP Y = -footprint Y, Z0 = PCB F side).
The Bread Modular footprint has no model, so this is a dimensioned proxy for the
panel fit check only, not a vendor model. Dimensions are from the Thonk drawing of
the Song Huei R0904N "Tall Trimmer" (R0904N_Thonk.pdf, L-25 KQ shaft):

- body: the footprint F.Fab rectangle (9.5 x 11.35 mm), BODY_H = 6.8 mm tall;
- collar: COLLAR_L = 1.0 mm on the shaft axis (the midpoint of the two bracket
  pads, footprint (-0.127, -0.508)); its 7.0 mm diameter is an assumption;
- shaft: 6.0 mm insulated, up to SHAFT_TOP = 25.0 mm (6.8 + 1 + 17.2). No bushing
  and no nut: the snap-in bracket holds the pot (docs/research.md section 4).
"""
from pathlib import Path

import FreeCAD as App
import Part

MODULE = Path(__file__).resolve().parents[1]
OUT = MODULE / 'hardware/IMIX.3dshapes/RV09_vertical_proxy.step'
BODY = (-4.877, -5.358, 4.623, 5.992)      # footprint F.Fab rectangle x0, y0, x1, y1
SHAFT_XY = (-0.127, -0.508)                # footprint frame
BODY_H, COLLAR_L, SHAFT_TOP = 6.8, 1.0, 25.0


def build():
    x0, y0, x1, y1 = BODY
    body = Part.makeBox(x1 - x0, y1 - y0, BODY_H, App.Vector(x0, -y1, 0))
    sx, sy = SHAFT_XY[0], -SHAFT_XY[1]
    collar = Part.makeCylinder(3.5, COLLAR_L, App.Vector(sx, sy, BODY_H))
    shaft = Part.makeCylinder(3.0, SHAFT_TOP - BODY_H, App.Vector(sx, sy, BODY_H))
    shape = body.fuse(collar).fuse(shaft).removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shape.exportStep(str(OUT))
    print(OUT, round(shape.Volume, 3))


build()
