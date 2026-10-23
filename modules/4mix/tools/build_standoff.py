"""FreeCAD generator for the 4MIX carrier standoff 3D model (docs/geometry.json mount_standoffs).

Run with FreeCAD's headless interpreter (see tools/build_standoff.sh):
  modules/4mix/tools/build_standoff.sh

The carrier has no jacks along its bottom half, so two 10 mm M3 female-female hex standoffs
(user stock) hold it to the panel there: one M3 from the carrier B side, one from the panel
front. This is only the carrier footprint's 3D model (nothing is printed).

Frame (KiCad footprint model frame): origin = standoff axis on the carrier F surface, Z toward
the panel, hex flats facing +/-X. Writes mechanical/standoff-m3x10.step.
"""

import math
import os
from pathlib import Path

import FreeCAD as App
import Part

V = App.Vector
MODULE = Path(os.environ.get('MODULE_DIR', Path(__file__).resolve().parents[1]))
import json  # noqa: E402
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
S = GEO['mount_standoffs']
OUT = MODULE / 'mechanical'
TAP_D = 2.5  # M3 tap drill, through


def main():
    rc = S['hex_af_mm'] / math.sqrt(3)
    pts = [V(rc * math.cos(math.radians(30 + 60 * k)), rc * math.sin(math.radians(30 + 60 * k)), 0) for k in range(7)]
    body = Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, S['length_mm']))
    body = body.cut(Part.makeCylinder(TAP_D / 2, S['length_mm'] + 2, V(0, 0, -1))).removeSplitter()
    assert body.isValid() and len(body.Solids) == 1
    OUT.mkdir(exist_ok=True)
    body.exportStep(str(OUT / 'standoff-m3x10.step'))
    bb = body.BoundBox
    print('standoff bbox', [round(v, 3) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)])


main()
