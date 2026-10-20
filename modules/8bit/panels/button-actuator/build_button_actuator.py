"""Generate the 3D-printable one-piece MODE button cap with FreeCAD.

Run headless from modules/8bit:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/button-actuator/build_button_actuator.py

SW1 is a generic 6 x 6 mm THT tact switch, 7 mm tall (body to Z3.5, Ø3.5 round stem to
Z7.0), on the carrier F side; the panel rear is 3.0 mm above the stem top. The cap is one
part, printable without supports, no glue:

- SOCKET (Z4.5..7.0): a blind hole that press-fits over the switch stem; the stem top
  bottoms in it, which sets the height.
- FLANGE (Z4.5..9.7): Ø7, wider than the panel hole, so the cap cannot leave through the
  front. It stays 1.0 mm above the switch body and 0.3 mm below the panel rear.
- TIP (Z9.7..13.0): Ø3.6 through the Ø4.2 panel hole, 1.4 mm (FR4) / 1.0 mm (print)
  proud of the panel front, more than the ~0.25 mm switch travel.

Assembly: press the cap onto the soldered switch, then fit the panel over the tip.
Print it socket-down (flange on the bed, tip up); the socket roof is a short bridge.

All sizes come from docs/geometry.json (`button_actuator`) and are asserted against the
switch, the panel stack and the neighbouring parts. Frame: the carrier frame of
docs/geometry.json, Z0 = carrier F.Cu, +Z toward the panel. Nominal geometry: no
physical-fit claim; FDM holes print undersize, so measure the stem and tune socket_D
for the press fit (ream the panel hole if the tip binds).
Outputs (this directory): 8bit-button-cap.stl (print orientation) and
8bit-button-actuator.step (the cap in the carrier frame at SW1).
"""
import json
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
MODULE = HERE.parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
TRAVEL = 0.25      # switch travel, nominal
V = App.Vector


def cyl(d, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, V(0, 0, z0))


def check(cap):
    st = GEO['stack_Z_mm']
    rear = st['panel_rear_seat']
    fronts = {'FR4': rear + GEO['panel_pcb_thickness_mm'], 'print': rear + GEO['panel_print_thickness_mm']}
    hole = GEO['panel_hole_diameters_mm']['button']
    assert cap['socket_Z'][1] == st['switch_stem_top'], 'the stem top must bottom in the socket'
    assert cap['socket_Z'][0] == cap['body_Z'][0], 'the socket opens on the flange underside'
    assert cap['socket_Z'][1] - cap['socket_Z'][0] >= 2.0, 'press-fit grip length'
    assert 0.0 <= cap['socket_D'] - st['switch_stem_D'] <= 0.2, 'socket vs stem (press fit, FDM undersize)'
    assert cap['body_Z'][0] - st['switch_body_top'] >= TRAVEL + 0.5, 'flange vs switch body'
    assert cap['body_Z'][1] - cap['socket_Z'][1] >= 1.5, 'socket roof thickness'
    assert 0.2 <= rear - cap['body_Z'][1] <= 0.5, 'flange play behind the panel'
    assert cap['body_D'] >= hole + 2.0, 'the flange must be captive behind the panel'
    assert cap['body_D'] - cap['socket_D'] >= 2.4, 'socket wall'
    assert cap['tip_D'] <= hole - 0.5, 'tip clearance in the panel hole'
    assert cap['tip_Z'][0] == cap['body_Z'][1]
    gaps = {k: round(cap['tip_Z'][1] - z, 2) for k, z in fronts.items()}
    assert min(gaps.values()) >= TRAVEL + 0.5, gaps
    # Neighbours (panel frame): flange vs the LED body and the RV3 / J3 bodies.
    x, y = GEO['button']['XY']
    r = cap['body_D'] / 2
    led = GEO['leds'][0]
    assert led['X'] - 1.9 - (x + r) >= 1.0, 'cap vs LED flange'
    rv3 = next(p for p in GEO['pots'] if p['ref'] == 'RV3')
    assert (y - r) - (rv3['shaft_Y'] + 6.5) >= 1.0, 'cap vs RV3 body'
    j3 = next(j for j in GEO['jacks'] if j['ref'] == 'J3')
    assert (j3['Y'] - 4.5) - (y + r) >= 1.0, 'cap vs J3 body'
    assert x - r >= 1.0, 'cap inside the panel edge'
    return gaps


def build():
    cp = GEO['button_actuator']['cap']
    gaps = check(cp)
    cap = cyl(cp['body_D'], *cp['body_Z']).fuse(cyl(cp['tip_D'], *cp['tip_Z']))
    cap = cap.cut(cyl(cp['socket_D'], cp['socket_Z'][0] - 0.1, cp['socket_Z'][1])).removeSplitter()
    assert cap.isValid() and len(cap.Solids) == 1
    x, y = GEO['button']['XY']
    ox, oy = GEO['kicad_origin_mm']
    # Assembly in the KiCad 3D frame (X right, Y up = -sheet Y) at the SW1 position.
    asm = cap.copy()
    asm.Placement = App.Placement(V(ox + x, -(oy + y), 0), App.Rotation())
    asm.exportStep(str(HERE / '8bit-button-actuator.step'))
    # Print orientation = assembled orientation (socket down), starting at Z0.
    s = cap.copy()
    s.translate(V(0, 0, -s.BoundBox.ZMin))
    mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.1)
    mesh.write(str(HERE / '8bit-button-cap.stl'))
    print('cap volume mm3', round(cap.Volume, 2), 'height', round(s.BoundBox.ZLength, 2))
    print('tip-to-panel-front', gaps)


build()
