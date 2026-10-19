"""Generate the 3D-printable two-part MODE button actuator with FreeCAD.

Run headless from modules/8bit:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/button-actuator/build_button_actuator.py

SW1 is the Bread Modular 8bit SMD tact switch (K2-1808SN-A4SW-01, 2.5 mm tall) on the
carrier F side, 7.5 mm below the panel rear. The actuator bridges that gap in two parts,
each printable without supports, glued together through the panel hole:

- PLUNGER (behind the panel): a foot that rests on the switch button and a Ø7 body,
  wider than the panel hole, so it cannot leave through the front. A blind socket opens
  on its top. Print it socket-down (the foot points up).
- CAP (in front of the panel): a Ø8 finger cap with a Ø3.6 stem underneath. Push the
  stem through the panel hole from the front and glue it into the plunger socket (CA
  glue), the stem bottomed in the socket. Print it cap-down (the stem points up).

Glued, the actuator is captive in the panel: the plunger body stops 0.3 mm behind the
panel rear, the cap stands 1.4 mm (FR4) / 1.0 mm (print) proud of the panel front, more
than the ~0.25 mm switch travel, so pressing the cap reaches the switch before the panel.

All sizes come from docs/geometry.json (`button_actuator`) and are asserted against the
panel stack and the neighbouring parts. Frame: the carrier frame of docs/geometry.json,
Z0 = carrier F.Cu, +Z toward the panel. Nominal geometry: no physical-fit claim; FDM
holes print undersize, so ream the socket / panel hole if the stem binds.
Outputs (this directory): 8bit-button-plunger.stl, 8bit-button-cap.stl (print
orientation) and 8bit-button-actuator.step (both parts assembled in the carrier frame).
"""
import json
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
MODULE = HERE.parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
CHAMFER = 0.4      # cap top edge
TRAVEL = 0.25      # switch travel, nominal
V = App.Vector


def cyl(d, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, V(0, 0, z0))


def check(a):
    st = GEO['stack_Z_mm']
    pl, cap = a['plunger'], a['cap']
    rear = st['panel_rear_seat']
    fronts = {'FR4': rear + GEO['panel_pcb_thickness_mm'], 'print': rear + GEO['panel_print_thickness_mm']}
    hole = GEO['panel_hole_diameters_mm']['button']
    assert pl['foot_Z'][0] == st['switch_top'], 'the foot must rest on the switch button'
    assert pl['foot_D'] <= 2.4, 'the foot must stay on the 4.2 x 3.25 mm switch top'
    assert pl['foot_Z'][1] == pl['body_Z'][0]
    assert 0.2 <= rear - pl['body_Z'][1] <= 0.5, 'plunger play behind the panel'
    assert pl['body_D'] >= hole + 2.0 and cap['cap_D'] >= hole + 2.0, 'both ends must be captive'
    assert cap['stem_D'] <= hole - 0.5 and cap['stem_D'] <= pl['socket_D'] - 0.2, 'stem clearances'
    assert pl['socket_Z'][1] == pl['body_Z'][1] and pl['socket_Z'][0] - pl['body_Z'][0] >= 1.5
    assert cap['stem_Z'][0] == pl['socket_Z'][0], 'the stem bottoms in the socket (sets the glued length)'
    assert cap['stem_Z'][1] == cap['cap_Z'][0]
    gaps = {k: round(cap['cap_Z'][0] - z, 2) for k, z in fronts.items()}
    assert min(gaps.values()) >= TRAVEL + 0.5, gaps
    # Neighbours (panel frame): plunger body vs the LED body and the RV3 / J3 bodies.
    x, y = GEO['button']['XY']
    r = pl['body_D'] / 2
    led = GEO['leds'][0]
    assert led['X'] - 1.9 - (x + r) >= 1.0, 'plunger vs LED flange'
    rv3 = next(p for p in GEO['pots'] if p['ref'] == 'RV3')
    assert (y - r) - (rv3['shaft_Y'] + 6.5) >= 1.0, 'plunger vs RV3 body'
    j3 = next(j for j in GEO['jacks'] if j['ref'] == 'J3')
    assert (j3['Y'] - 4.5) - (y + r) >= 1.0, 'plunger vs J3 body'
    assert x - r >= 1.0, 'plunger body inside the panel edge'
    return gaps


def build():
    a = GEO['button_actuator']
    gaps = check(a)
    pl, cp = a['plunger'], a['cap']
    plunger = cyl(pl['foot_D'], *pl['foot_Z']).fuse(cyl(pl['body_D'], *pl['body_Z']))
    plunger = plunger.cut(cyl(pl['socket_D'], pl['socket_Z'][0], pl['socket_Z'][1] + 0.1)).removeSplitter()
    cap = cyl(cp['cap_D'], *cp['cap_Z'])
    top = [e for e in cap.Edges if abs(e.BoundBox.ZMin - cp['cap_Z'][1]) < 1e-6 and e.BoundBox.ZMax - e.BoundBox.ZMin < 1e-6]
    cap = cap.makeChamfer(CHAMFER, top)
    cap = cap.fuse(cyl(cp['stem_D'], *cp['stem_Z'])).removeSplitter()
    for s in (plunger, cap):
        assert s.isValid() and len(s.Solids) == 1
    assert plunger.common(cap).Volume < 1e-6, 'parts overlap'
    x, y = GEO['button']['XY']
    ox, oy = GEO['kicad_origin_mm']
    # Assembly in the KiCad 3D frame (X right, Y up = -sheet Y) at the SW1 position.
    place = App.Placement(V(ox + x, -(oy + y), 0), App.Rotation())
    asm = Part.makeCompound([plunger.copy(), cap.copy()])
    asm.Placement = place
    asm.exportStep(str(HERE / '8bit-button-actuator.step'))
    # Print orientations: plunger socket-down, cap top-down; both start at Z0.
    flip = App.Rotation(V(1, 0, 0), 180)
    for name, shape in (('plunger', plunger), ('cap', cap)):
        s = shape.copy()
        s.Placement = App.Placement(V(0, 0, 0), flip)
        s.translate(V(0, 0, -s.BoundBox.ZMin))
        mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.1)
        mesh.write(str(HERE / f'8bit-button-{name}.stl'))
        print(name, 'volume mm3', round(shape.Volume, 2), 'height', round(s.BoundBox.ZLength, 2))
    print('cap-to-panel gap', gaps)


build()
