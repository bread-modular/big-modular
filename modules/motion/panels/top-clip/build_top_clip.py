"""Generate the 3D-printable MOTION top clip with FreeCAD.

Run headless from modules/motion:
  freecadcmd panels/top-clip/build_top_clip.py

Why: all four jacks sit in the bottom 25 mm of the carrier and the RV09 pots have no
bushing or nut, so nothing held the upper 85 mm of the carrier to the panel. The clip
holds the carrier top edge (Y9.25) to the panel with one M3 screw; the routed carrier is
unchanged, the panel gets one Ø3.2 hole (docs/geometry.json `top_clip`).

Shape: a C channel along the carrier top edge, X5..29, plus a screw boss X22..29:
- SHOULDER rests on the carrier F face inside the 1 mm keep-out strip (Y9.25..10.0);
- NOSE hooks the B face (Y9.25..10.1) behind a 1.8 mm slot for the 1.6 mm board;
- BACK face (Y8.2) stays 0.2 mm off the skiff rail (Y8.0) over the whole depth;
- BOSS reaches the panel rear (Z10) and takes an M3x6 / M3x8 machine screw from the
  front, cutting its own thread in a blind Ø2.6 hole (floor at Z1.4, so even an M3x10
  stops 1.4 mm above the carrier).

Assembly: slide the clip onto the top edge from the right end, fit the panel, tighten the
jack nuts, then the clip screw. Print it standing on its right end (X29 face on the bed):
no overhang, no support; the slot and screw loads run along the layers.

Frame: X across (panel X), CAD Y = 128.5 - panel Y, Z = carrier Z (Z0 = carrier F.Cu,
+Z toward the panel; panel rear Z10), so the STEP drops onto the printed panel STEP moved
to Z10. Outputs (this directory): motion-top-clip.step (assembly frame),
motion-top-clip.stl (print orientation). Nominal geometry: no physical-fit or strength
claim; measure the real jack stack (panel_rear_seat) before printing.
"""
import json
import math
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
MODULE = HERE.parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
CLIP = GEO['top_clip']
H = GEO['panel_mm'][1]
NAME = 'motion-top-clip'
V = App.Vector
EDGE_KEEPOUT = 1.0        # root AGENTS.md: no copper / courtyards within 1 mm of the edge
RAIL_CLEARANCE = 0.2
BOARD_T = GEO['main_pcb']['thickness_mm']
EPS = 1e-9


def box(x0, x1, y0, y1, z0, z1):
    """Box in panel X / panel Y (down) / carrier Z."""
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, H - y1, z0))


def check():
    pcb_x0, pcb_y0, pcb_x1, _ = GEO['main_pcb']['outline_mm']
    rail_y = GEO['rail_clear_gap_Y_mm'][0]
    st = GEO['stack_Z_mm']
    x0, x1 = CLIP['X_mm']
    boss = CLIP['boss']
    assert CLIP['top_Z'] == st['panel_rear_seat'], 'the clip must reach the panel rear'
    assert CLIP['back_Y'] - rail_y >= RAIL_CLEARANCE - EPS, 'clip vs skiff rail'
    assert 0.1 - EPS <= pcb_y0 - CLIP['spine_face_Y'] <= 0.2 + EPS, 'spine vs carrier top edge'
    for key in ('shoulder_inner_Y', 'nose_inner_Y'):
        overlap = CLIP[key] - pcb_y0
        assert 0.6 <= overlap < EDGE_KEEPOUT, f'{key}: must grip inside the 1 mm keep-out strip'
    s0, s1 = CLIP['slot_Z']
    assert s1 == 0.0 and 0.1 <= (s1 - s0) - BOARD_T <= 0.25, 'slot vs board thickness'
    assert CLIP['nose_Z'][1] == s0 and CLIP['nose_Z'][1] - CLIP['nose_Z'][0] >= 1.0 - EPS, 'nose'
    assert pcb_x0 + 0.5 <= x0 < boss['X'][0] < boss['X'][1] == x1 <= pcb_x1 - 0.5, 'clip X span'
    assert boss['Y'][0] == CLIP['back_Y'] and boss['Z_bottom'] >= 0.5, 'boss stands off the F face'
    sx, sy = CLIP['screw_XY']
    r = CLIP['screw_hole_D'] / 2
    walls = (sx - r - boss['X'][0], boss['X'][1] - sx - r, sy - r - boss['Y'][0],
             boss['Y'][1] - sy - r)
    assert min(walls) >= 1.5 - EPS, f'boss walls around the screw hole {walls}'
    assert CLIP['screw_hole_bottom_Z'] - boss['Z_bottom'] >= 0.6 - EPS, 'hole floor'
    # M3x6 .. M3x10 from the front of either panel: enough thread, never on the carrier
    for panel_t in (GEO['panel_pcb_thickness_mm'], GEO['panel_print_thickness_mm']):
        front = st['panel_rear_seat'] + panel_t
        for length in (6, 8, 10):
            tip = front - length
            assert tip >= CLIP['screw_hole_bottom_Z'] + 0.1 - EPS, (panel_t, length, tip)
            assert CLIP['top_Z'] - tip >= 3.5, (panel_t, length, 'thread engagement')
    return walls


def build_clip():
    x0, x1 = CLIP['X_mm']
    yb, top = CLIP['back_Y'], CLIP['top_Z']
    n0, n1 = CLIP['nose_Z']
    boss = CLIP['boss']
    parts = [
        box(x0, x1, yb, CLIP['shoulder_inner_Y'], 0.0, top),        # wall + shoulder
        box(x0, x1, yb, CLIP['spine_face_Y'], n0, 0.0),             # spine beside the edge
        box(x0, x1, yb, CLIP['nose_inner_Y'], n0, n1),              # nose under the B face
        box(*boss['X'], *boss['Y'], boss['Z_bottom'], top),         # screw boss
    ]
    solid = parts[0].fuse(parts[1:]).removeSplitter()
    sx, sy = CLIP['screw_XY']
    z_hole = CLIP['screw_hole_bottom_Z']
    hole = Part.makeCylinder(CLIP['screw_hole_D'] / 2, top + 1 - z_hole, V(sx, H - sy, z_hole))
    return solid.cut(hole).removeSplitter()


def expected_volume():
    x0, x1 = CLIP['X_mm']
    length = x1 - x0
    yb = CLIP['back_Y']
    n0, n1 = CLIP['nose_Z']
    boss = CLIP['boss']
    wall = length * (CLIP['shoulder_inner_Y'] - yb) * CLIP['top_Z']
    spine = length * (CLIP['spine_face_Y'] - yb) * (0.0 - n1)
    nose = length * (CLIP['nose_inner_Y'] - yb) * (n1 - n0)
    boss_v = ((boss['X'][1] - boss['X'][0]) * (boss['Y'][1] - CLIP['shoulder_inner_Y'])
              * (CLIP['top_Z'] - boss['Z_bottom']))
    hole = math.pi * (CLIP['screw_hole_D'] / 2) ** 2 * (CLIP['top_Z'] - CLIP['screw_hole_bottom_Z'])
    return wall + spine + nose + boss_v - hole


def interference(clip):
    """Volumes shared with the carrier, the rail and the panel: all must be zero."""
    px0, py0, px1, py1 = GEO['main_pcb']['outline_mm']
    rear = GEO['stack_Z_mm']['panel_rear_seat']
    rail_y = GEO['rail_clear_gap_Y_mm'][0]
    rail_h = 13.5     # mechanical/case rail section 10 x 13.5 mm
    bodies = {
        'carrier': box(px0, px1, py0, py1, -BOARD_T, 0.0),
        'rail': box(-5, 35, -2.0, rail_y, rear - rail_h, rear),
        'panel': box(0, GEO['panel_mm'][0], 0, H, rear, rear + GEO['panel_print_thickness_mm']),
    }
    return {k: round(clip.common(b).Volume, 6) for k, b in bodies.items()}


def build():
    walls = check()
    clip = build_clip()
    assert clip.isValid() and len(clip.Solids) == 1
    want = expected_volume()
    assert math.isclose(clip.Volume, want, rel_tol=1e-4), (clip.Volume, want)
    hits = interference(clip)
    assert all(v == 0 for v in hits.values()), hits
    doc = App.newDocument(NAME.replace('-', '_'))
    obj = doc.addObject('Part::Feature', 'TopClip')
    obj.Shape = clip
    doc.recompute()
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    clip.exportStep(str(HERE / f'{NAME}.step'))
    # print orientation: right end (X29 face) on the bed
    printed = clip.copy()
    printed.rotate(V(0, 0, 0), V(0, 1, 0), 90)
    bb = printed.BoundBox
    printed.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    bed = [f for f in printed.Faces if f.BoundBox.ZMax < 1e-6]
    mesh = MeshPart.meshFromShape(Shape=printed, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(HERE / f'{NAME}.stl'))
    pb = printed.BoundBox
    print(json.dumps({
        'volume_mm3': round(clip.Volume, 3),
        'interference_mm3': hits,
        'boss_walls_mm': [round(w, 2) for w in walls],
        'print_bbox_mm': [round(pb.XLength, 2), round(pb.YLength, 2), round(pb.ZLength, 2)],
        'bed_area_mm2': round(sum(f.Area for f in bed), 2),
        'mesh_facets': mesh.CountFacets,
    }, indent=2))


build()
