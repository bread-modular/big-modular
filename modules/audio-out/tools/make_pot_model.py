"""Generate the RV09 volume-pot proxy model (hardware/AudioOut.3dshapes/RV09_proxy.step).

Run headless from modules/audio-out:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd tools/make_pot_model.py

The Bread Modular RV09 footprint has no 3D model and there is no pot drawing, so this
is an envelope for the panel fit check and renders, not a manufacturer model. It
follows the user's sample (2026-10-19 photo, "B1M"): a 9 mm vertical RV09 ("tall
trimmer" style) with a short plain collar and a knurled shaft, NO threaded bushing
and no nut; the shaft (the rotating part) is 16 mm tall above the body (user
measurement). Footprint frame (KiCad footprint origin, Y down in KiCad = -Y here,
Z0 = PCB F.Cu surface):
- body: the footprint F.Fab rectangle X -4.877..4.623, Y -5.358..5.992, height
  BODY_H (nominal, not yet measured);
- collar: COLLAR_D on the footprint's shaft circle centre (-0.127, -0.508), COLLAR_L tall;
- shaft: SHAFT_D, SHAFT_L above the body top (collar included).
"""
from pathlib import Path

import FreeCAD as App
import Part

MODULE = Path(__file__).resolve().parents[1]
OUT = MODULE / 'hardware/AudioOut.3dshapes/RV09_proxy.step'

BODY_X = (-4.877, 4.623)
BODY_Y = (-5.358, 5.992)     # KiCad footprint frame (Y down)
SHAFT_XY = (-0.127, -0.508)
BODY_H = 6.8
COLLAR_D, COLLAR_L = 7.0, 1.0
SHAFT_D, SHAFT_L = 6.0, 16.0


def build():
    # KiCad 3D frame: X right, Y up (= -footprint Y), Z up from the board top.
    body = Part.makeBox(BODY_X[1] - BODY_X[0], BODY_Y[1] - BODY_Y[0], BODY_H,
                        App.Vector(BODY_X[0], -BODY_Y[1], 0))
    sx, sy = SHAFT_XY[0], -SHAFT_XY[1]
    bush = Part.makeCylinder(COLLAR_D / 2, COLLAR_L, App.Vector(sx, sy, BODY_H))
    shaft = Part.makeCylinder(SHAFT_D / 2, SHAFT_L - COLLAR_L, App.Vector(sx, sy, BODY_H + COLLAR_L))
    shape = body.fuse([bush, shaft]).removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shape.exportStep(str(OUT))
    print(OUT, round(shape.Volume, 3))


build()
