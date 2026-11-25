"""Under-desk patch cable holder: every part is 3D printed, no metal hardware.

Build: mechanical/desk-cable-holder/tools/build_desk_cable_holder.sh

A C-shaped hanger sits under the desk top, behind the desk edge: its top flange lies against the
desk's underside, its back wall drops from there and carries the comb, which points to the front.
One C clamp (printed screw + captive square nut + snap-on pad, the mechanical/solder-arm clamp
hardware with the same thread) presses the flange up against the desk. Nothing joins the hanger to
the clamp: the pad sits in a pocket in the flange, and the flange's front edge faces the clamp's
spine. Only the clamp is in front of and on top of the desk.

Cables hang by a plug: the cable goes through a slot from the front, the plug sits in one of the
slot's conical seats, so it cannot slide out of the open end. The plugs stand in the room between
the comb and the flange.

Frame: desk top at z = 0, desk edge at x = 0, +X into the desk, Y along the edge. The hanger is
built with the desk's underside at z = 0.

CAD-checked prototype: no part is printed, no fit is measured.
"""
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
HOLDER = Path(os.environ.get('HOLDER_DIR', Path(__file__).resolve().parents[1]))
OUT = HOLDER/'print'
CAD = HOLDER/'cad'
RESEARCH = HOLDER/'research'
BED = 256.0           # Bambu Lab P2S
FZ = 1e-4             # fuzzy tolerance: OCC booleans on the helical thread faces fail without it
FUSE = 0.5            # overlap of solids that are fused

# hanger (its own frame: desk underside at z = 0)
WIDTH = 240.0
FLANGE_T = 6.0        # against the desk's underside
POCKET = 2.0          # pad pocket in the flange
POCKET_CLR = 0.5      # radial, around the pad
PLUG_ROOM = 58.0      # flange to the comb: a 45 mm plug + lifting it out of its seat
COMB_T = 6.0          # at the tooth tips
ROOT_T = 10.0         # at the back wall: the teeth print standing, layers across them
FRONT = 3.0           # tooth tips behind the desk edge
WALL_X, WALL_T = 57.0, 5.0            # back wall
GUSSET = 5.0          # 45 degree corners inside the C
STRIP = 24.0          # flange depth on the wings, wall included
TONGUE_HALF = 32.0    # the flange reaches the desk edge here, for the clamp pad
TONGUE_X = 0.5        # tongue front edge: faces the clamp spine
WINDOW_Y = (34.0, 106.0)              # opening in the back wall of each wing
WINDOW_MARGIN = 4.0   # from the gussets
SLOT_W = 5.0          # cables up to about 4.5 mm
SLOT_PITCH = 11.5
SLOT_FIRST = 30.0     # first slot centre from the middle
SLOTS_PER_WING = 8
SEAT_X = (14.5, 25.0, 35.5, 46.0)     # plug seats, from the desk edge inwards
SEAT_D = 9.5          # cone mouth on the top face, 45 degrees down to the slot
MOUTH = 6.0           # the slot widens over this length at the tooth tips: found by feel
MOUTH_W = 10.0
NOTCH_HALF = 21.0     # clamp + 1 mm each side
NOTCH_X = 48.0        # notch back edge: the bottom jaw ends at 46
PLUG_L = 50.0         # plug envelope above its seat in the checks
# clamp
CLAMP_HALF_W = 20.0
SPINE = 16.0
JAW_T = 14.0          # top jaw, on the desk top
JAW_L = 45.0
RELIEF_R = 2.0        # round relief in the inside top corner: the desk corner is free, no notch
GAP = 68.0            # desk top to the bottom jaw
BOTTOM_JAW = 32.0
BOTTOM_JAW_L = 46.0
SCREW_X = 26.0
CLAMP = dict(r=9.0, depth=1.8, pitch=5.0, crest=0.7)   # as mechanical/solder-arm
THREAD_CLR = 0.35     # radial, on the internal thread; the nut adds 0.05
NUT, NUT_H, NUT_CLR = 30.0, 16.0, 0.25
NUT_ROOF = 6.0        # jaw material above the nut slot
SCREW_THREAD = 75.0
SCREW_KNOB_R, SCREW_KNOB_H = 22.0, 12.0
NECK_R, NECK_H = 5.0, 6.0
BALL_R, BALL_TOP_R = 7.0, 4.5
BALL_UNDER, BALL_CYL, BALL_CONE = 2.0, 1.5, 2.5    # mushroom tip: 45 degree underside, straight, top cone
PAD_R, PAD_T, PAD_H = 20.0, 3.0, 13.5
PAD_BORE, PAD_LIP, PAD_WALL = 7.4, 6.7, 1.8
PAD_LIP_Z = 10.0

DESKS = (8.0, 18.0, 28.0, 40.0, 50.0)   # desk thicknesses that are assembled and checked
SHOWN = 28.0                            # the one in the renders and the reference assembly
CABLE_D = 5.0                           # thickest cable assumed in the clearance check
CABLES = (100, 150, 200, 300, 450, 600) # cable lengths drawn in the renders, mm
SLOT_CABLES = (600, 600, 450, 450, 300, 300, 200, 200, 150, 150, 150, 100, 100, 100, 200, 300)   # per slot, left to right
FOLDED = 600                            # hung folded in the renders: both plugs in the slot


# ---------- geometry helpers (as mechanical/solder-arm/tools/build_solder_arm.py) ----------

def move(shape, x=0, y=0, z=0):
    s = shape.copy()
    s.translate(V(x, y, z))
    return s


def place(shape, pl):
    return shape.transformed(pl.toMatrix(), True)


def one(shape, label):
    s = shape.removeSplitter()
    # removeSplitter once returned a "valid" tapped nut with 13 % less volume: keep the input then
    if not s.isValid() or abs(s.Volume - shape.Volume) > 1e-4*shape.Volume:
        s = shape
    assert s.isValid() and len(s.Solids) == 1, f'{label}: invalid or {len(s.Solids)} solids'
    return s.Solids[0]


def prism(points, z0, z1):
    """Polygon in the XY plane, extruded from z0 to z1."""
    wire = Part.makePolygon([V(x, y, z0) for x, y in points] + [V(points[0][0], points[0][1], z0)])
    return Part.Face(wire).extrude(V(0, 0, z1 - z0))


def prism_xz(points, y0, y1):
    """Polygon of (x, z) points, extruded along Y."""
    wire = Part.makePolygon([V(x, y0, z) for x, z in points] + [V(points[0][0], y0, points[0][1])])
    return Part.Face(wire).extrude(V(0, y1 - y0, 0))


def rev(points):
    """Polygon of (r, z) points, revolved around Z."""
    wire = Part.makePolygon([V(r, 0, z) for r, z in points] + [V(points[0][0], 0, points[0][1])])
    return Part.Face(wire).revolve(V(0, 0, 0), V(0, 0, 1), 360)


def cyl(r, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(0, 0, z0))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


PLAIN = False         # True: threads become plain cylinders (collision proxies)


def thread_rod(spec, z0, z1, clr=0.0):
    """Threaded rod from z0 to z1, right-handed, 45 degree flanks. The ridge centre is at angle 0
    (the +X side) at every z that is a multiple of the pitch, so two threads built here line up
    when one is shifted by dz and turned by 360*dz/pitch."""
    rM, d, p, c = spec['r'] + clr, spec['depth'], spec['pitch'], spec['crest']
    rm = rM - d
    if PLAIN:
        return cyl(rm if clr else rM, z0, z1)
    turns = (z1 - z0)/p
    if turns > 12:
        # one long sweep meshes badly: build it in pieces of at most 8 turns, they continue each other
        n = math.ceil(turns/8)
        cuts = [z0 + (z1 - z0)*i/n for i in range(n + 1)]
        rod = thread_rod(spec, cuts[0], cuts[1], clr)
        for a, b in zip(cuts[1:], cuts[2:]):
            rod = rod.fuse(thread_rod(spec, a, b, clr), FZ)
        assert rod.isValid() and len(rod.Solids) == 1, 'thread pieces'
        return rod.Solids[0]
    start = (math.floor(z0/p) - 1)*p
    height = (math.ceil(z1/p) + 1)*p - start
    helix = Part.makeHelix(p, height, rm)
    helix.translate(V(0, 0, start))
    hw, e = c/2 + d, 0.3
    pts = [V(rm - e, 0, start - hw - e), V(rm, 0, start - hw), V(rM, 0, start - c/2),
           V(rM, 0, start + c/2), V(rm, 0, start + hw), V(rm - e, 0, start + hw + e)]
    ridge = Part.Wire(helix).makePipeShell([Part.makePolygon(pts + [pts[0]])], True, True)
    rod = cyl(rm, start - hw - 1, start + height + hw + 1).fuse(ridge, FZ)
    rod = rod.common(cyl(rM + 1, z0, z1), FZ)
    assert rod.isValid() and len(rod.Solids) == 1, 'thread boolean'
    ridge_area = d*(c + d)
    centroid = rm + d*(3*c + 2*d)/(3*(2*c + 2*d))
    expected = math.pi*rm*rm*(z1 - z0) + ridge_area*2*math.pi*centroid*(z1 - z0)/p
    assert abs(rod.Volume - expected)/expected < 0.002, ('thread volume', rod.Volume, expected)
    return rod.Solids[0]


def tapped(body, spec, clr, z0, z1, x=0.0, y=0.0, ends=(True, True)):
    """Cut an internal thread along Z through body from z0 to z1, with a lead-in cone at the chosen
    ends. One cutter, one cut: cutting the cones after the thread left an invalid solid."""
    rM, d = spec['r'] + clr, spec['depth']
    cutter = thread_rod(spec, z0 - 1, z1 + 1, clr)
    lead = rM + 0.4
    for z, s, on in ((z0, 1, ends[0]), (z1, -1, ends[1])):
        if on and not PLAIN:
            # 31 degrees: a 45 degree cone lies in the thread flanks and breaks the boolean
            deep = z - s + s*(d + 1.5)/0.6
            cone = rev([(0, z - s), (lead + 0.6, z - s), (rM - d - 0.5, deep), (0, deep)])
            cutter = cutter.fuse(cone, FZ)
    assert cutter.isValid() and len(cutter.Solids) == 1, 'thread cutter'
    out = body.cut(move(cutter, x, y), FZ)
    assert out.isValid() and len(out.Solids) == 1, 'tapped hole'
    removed = body.Volume - out.Volume
    rod = math.pi*(rM - d)**2*(z1 - z0)
    assert rod - 1e-6 <= removed < math.pi*(lead + 1)**2*(z1 - z0), ('tapped volume', removed, rod)
    return out


def lobed(r, h, lobes, scallop_r, chamfer=1.0):
    """Knob body: chamfered disc with finger scallops."""
    body = rev([(0, 0), (r - chamfer, 0), (r, chamfer), (r, h - chamfer), (r - chamfer, h), (0, h)])
    for i in range(lobes):
        a = 2*math.pi*i/lobes
        cut = cyl(scallop_r, -1, h + 1)
        cut.translate(V((r + scallop_r*0.55)*math.cos(a), (r + scallop_r*0.55)*math.sin(a), 0))
        body = body.cut(cut)
    return body


def print_pose(shape, rot=None):
    """Rotate into the print orientation (rotations in turn) and put the bounding box corner on the origin."""
    s = shape.copy()
    for r in rot or ():
        s = s.transformed(App.Placement(V(0, 0, 0), App.Rotation(*r)).toMatrix(), True)
    b = s.optimalBoundingBox(False, False)     # BoundBox is loose around the helical faces
    s.translate(V(-b.XMin, -b.YMin, -b.ZMin))
    return s


# ---------- parts (clamp body in the desk frame, the others in their own) ----------

COMB_TOP = -(FLANGE_T + PLUG_ROOM)      # hanger frame
BACK = WALL_X + WALL_T
BOTTOM = COMB_TOP - ROOT_T


def slot_centres():
    ys = [SLOT_FIRST + SLOT_PITCH*k for k in range(SLOTS_PER_WING)]
    return [-y for y in reversed(ys)] + ys


def hanger():
    """Desk underside at z = 0, desk edge at x = 0. A C that is open to the front: flange, back wall, comb."""
    w, g = WIDTH/2, GUSSET
    tip = COMB_TOP - COMB_T
    # the comb's underside runs from the tooth tips to the foot of the wall: thicker at the root
    prof = [(BACK - STRIP, 0), (BACK, 0), (BACK, BOTTOM), (WALL_X, BOTTOM), (FRONT, tip), (FRONT, COMB_TOP),
            (WALL_X - g, COMB_TOP), (WALL_X, COMB_TOP + g), (WALL_X, -FLANGE_T - g), (WALL_X - g, -FLANGE_T),
            (BACK - STRIP, -FLANGE_T)]
    body = prism_xz(prof, -w, w)
    body = body.fuse(box(TONGUE_X, BACK - STRIP + FUSE, -TONGUE_HALF, TONGUE_HALF, -FLANGE_T, 0))
    # pad pocket: round, with a 45 degree roof towards the front (the hanger prints standing on its wall)
    r = PAD_R + POCKET_CLR
    q = r/math.sqrt(2)
    pocket = cyl(r, -FLANGE_T - 1, -FLANGE_T + POCKET)
    pocket = pocket.fuse(prism([(-q, -q), (-r*math.sqrt(2), 0), (-q, q)], -FLANGE_T - 1, -FLANGE_T + POCKET))
    body = body.cut(move(pocket, SCREW_X))
    # the clamp's bottom jaw and screw pass the comb here
    low, high = BOTTOM - 1, COMB_TOP + 1
    body = body.cut(box(FRONT - 1, NOTCH_X, -NOTCH_HALF, NOTCH_HALF, low, high))
    h, m = SLOT_W/2, MOUTH_W/2
    end = SEAT_X[-1]                       # slot end = centre of the last seat
    slope = (m - h)/MOUTH
    # the cone ends 0.2 mm inside the slot: a rim on the slot wall breaks the boolean
    depth = SEAT_D/2 - (h - 0.2)
    seat = rev([(0, COMB_TOP - depth), (h - 0.2, COMB_TOP - depth), (SEAT_D/2 + 1, high), (0, high)])
    for y in slot_centres():
        cut = box(FRONT - 1, end, y - h, y + h, low, high)
        cut = cut.fuse(move(cyl(h, low, high), end, y))
        nose = FRONT - 0.5
        cut = cut.fuse(prism([(nose, y - m - 0.5*slope), (FRONT + MOUTH, y - h), (FRONT + MOUTH, y + h),
                              (nose, y + m + 0.5*slope)], low, high))
        body = body.cut(cut)
        for x in SEAT_X:
            body = body.cut(move(seat, x, y))
    # openings in the back wall: less plastic, it lies on the bed
    z0, z1, c = COMB_TOP + g + WINDOW_MARGIN, -FLANGE_T - g - WINDOW_MARGIN, 6.0
    for side in (-1, 1):
        y0, y1 = sorted((side*WINDOW_Y[0], side*WINDOW_Y[1]))
        window = [(y0 + c, z0), (y1 - c, z0), (y1, z0 + c), (y1, z1 - c), (y1 - c, z1), (y0 + c, z1), (y0, z1 - c), (y0, z0 + c)]
        wire = Part.makePolygon([V(WALL_X - 1, y, z) for y, z in window + window[:1]])
        body = body.cut(Part.Face(wire).extrude(V(WALL_T + 2, 0, 0)))
    return one(body, 'hanger')


def clamp_body():
    top, low = JAW_T, -GAP - BOTTOM_JAW
    # the desk's corner stands in a round relief, the jaw lies flat on the desk top. The relief is part
    # of the profile: cut as a cylinder, the solid's volume came out 0.25 % wrong
    o = 0.3*RELIEF_R
    a0 = -math.asin(o/RELIEF_R)
    relief = [(-o + RELIEF_R*math.cos(a), o + RELIEF_R*math.sin(a))
              for a in (a0 + (1.5*math.pi - 2*a0)*i/16 for i in range(17))]
    assert abs(relief[0][1]) < 1e-9 and abs(relief[-1][0]) < 1e-9, relief
    prof = [(-SPINE + 4, top), (JAW_L - 3, top), (JAW_L, top - 3), (JAW_L, 1), (JAW_L - 1, 0),
            *relief, (0, -GAP + 10), (10, -GAP), (BOTTOM_JAW_L, -GAP),
            (BOTTOM_JAW_L, low + 3), (BOTTOM_JAW_L - 3, low), (-SPINE + 4, low), (-SPINE, low + 4), (-SPINE, top - 4)]
    body = prism_xz(prof, -CLAMP_HALF_W, CLAMP_HALF_W)
    # clamp screw: clearance hole through the bottom jaw (teardrop, it prints lying), nut slot open on the +Y side
    r = CLAMP['r'] + 0.5
    hole = cyl(r, low - 1, -GAP + 1)
    s = r/math.sqrt(2)
    hole = hole.fuse(prism([(-s, s), (0, r*math.sqrt(2)), (s, s)], low - 1, -GAP + 1))
    body = body.cut(move(hole, SCREW_X))
    half = NUT/2 + NUT_CLR
    slot_z = -GAP - NUT_ROOF - NUT_H - 2*NUT_CLR
    body = body.cut(box(SCREW_X - half, SCREW_X + half, -half, CLAMP_HALF_W + 1, slot_z, -GAP - NUT_ROOF))
    return one(body, 'clamp body'), slot_z


def clamp_nut():
    body = box(-NUT/2, NUT/2, -NUT/2, NUT/2, 0, NUT_H)
    return one(tapped(body, CLAMP, THREAD_CLR + 0.05, 0, NUT_H), 'clamp nut')


def clamp_screw():
    """Knob at z = 0, thread up, mushroom tip for the pad."""
    r, d = CLAMP['r'], CLAMP['depth']
    z0 = SCREW_KNOB_H
    z1 = z0 + SCREW_THREAD
    rod = thread_rod(CLAMP, z0 - 1, z1)
    rod = rod.common(rev([(0, z0 - 1), (r + 1, z0 - 1), (r + 1, z1 - d - 0.5), (r - d - 0.3, z1), (0, z1)]), FZ)
    za = z1 + NECK_H
    top = za + BALL_UNDER + BALL_CYL + BALL_CONE
    tip = rev([(0, z1 - 1), (NECK_R, z1 - 1), (NECK_R, za), (BALL_R, za + BALL_UNDER), (BALL_R, za + BALL_UNDER + BALL_CYL),
               (BALL_TOP_R, top), (0, top)])
    body = lobed(SCREW_KNOB_R, SCREW_KNOB_H, 6, 8.0).fuse(rod, FZ).fuse(tip, FZ)
    return one(body, 'clamp screw'), top


def clamp_pad():
    """Pad in its print pose: disc on the bed, slit collar up. The collar snaps over the mushroom."""
    ro = PAD_BORE + PAD_WALL
    body = rev([(0, 0), (PAD_R - 0.6, 0), (PAD_R, 0.6), (PAD_R, PAD_T), (ro, PAD_T), (ro, PAD_H - 0.6), (ro - 0.6, PAD_H),
                (PAD_LIP + 0.5, PAD_H), (PAD_LIP, PAD_H - 0.5), (PAD_LIP, PAD_LIP_Z + PAD_BORE - PAD_LIP), (PAD_BORE, PAD_LIP_Z),
                (PAD_BORE, PAD_T), (0, PAD_T)])
    for i in range(3):
        slit = box(-ro - 1, ro + 1, -0.6, 0.6, PAD_T + 1.0, PAD_H + 1)
        slit.rotate(V(0, 0, 0), V(0, 0, 1), 60*i)
        body = body.cut(slit)
    return one(body, 'clamp pad')


class Holder:
    """All parts. plain = True builds them without threads: OCC booleans between two solids with
    helical faces fail, so the collision checks run on these proxies and the thread pair is
    checked by its gap instead."""

    def __init__(self, plain=False):
        global PLAIN
        t0 = time.time()
        PLAIN = plain
        try:
            self.hanger = hanger()
            self.clamp, self.slot_z = clamp_body()
            self.nut = clamp_nut()
            self.screw, self.screw_len = clamp_screw()
            self.pad = clamp_pad()
        finally:
            PLAIN = False
        self.build_s = round(time.time() - t0, 1)
        # desk range: the knob stops under the bottom jaw (thin desk), the pad collar on it (thick desk)
        self.tip = self.screw_len - SCREW_KNOB_H - SCREW_THREAD     # thread end to the mushroom top
        self.under_pad = FLANGE_T - POCKET                          # flange between the desk and the pad
        self.desk_min = GAP + BOTTOM_JAW - SCREW_THREAD - self.tip - PAD_T - self.under_pad
        self.desk_max = GAP - PAD_H - self.under_pad

    def prints(self):
        """Print poses: name -> (shape, copies, orientation note)."""
        return {
            'hanger': (print_pose(self.hanger, [(V(0, 1, 0), 90), (V(0, 0, 1), 90)]), 1, 'back wall on the bed, teeth pointing up'),
            'clamp-body': (print_pose(self.clamp, [(V(1, 0, 0), 90)]), 1, 'on its side, nut slot open upwards'),
            'clamp-screw': (print_pose(self.screw), 1, 'standing on its knob'),
            'clamp-nut': (print_pose(self.nut), 1, 'flat'),
            'clamp-pad': (print_pose(self.pad), 1, 'disc on the bed, collar up'),
        }

    def assemble(self, desk):
        """World placements on a desk of the given thickness, clamp tightened."""
        assert self.desk_min <= desk <= self.desk_max, desk
        nut_z = self.slot_z + NUT_CLR
        pad_z = -desk - self.under_pad
        screw_z = pad_z - PAD_T - self.screw_len
        turn = App.Rotation(V(0, 0, 1), 360*(screw_z - nut_z)/CLAMP['pitch'])
        return {
            'desk': box(0, 260, -200, 200, -desk, 0),
            'hanger': move(self.hanger, 0, 0, -desk),
            'clamp-body': self.clamp,
            'clamp-nut': move(self.nut, SCREW_X, 0, nut_z),
            'clamp-screw': place(self.screw, App.Placement(V(SCREW_X, 0, screw_z), turn)),
            'clamp-pad': place(self.pad, App.Placement(V(SCREW_X, 0, pad_z), App.Rotation(V(1, 0, 0), 180))),
        }


# ---------- checks ----------

def overhangs(posed):
    """Downward faces of a print pose, from its mesh. Angles from a vertical wall: 90 = ceiling.
    The 45 degree cones and thread flanks mesh to facets of up to 48 degrees, so the limit is 50."""
    mesh = MeshPart.meshFromShape(Shape=posed, LinearDeflection=0.02, AngularDeflection=0.15)
    bed = steep = flat = worst = 0.0
    for f in mesh.Facets:
        nz = f.Normal.z
        if nz > -1e-6:
            continue
        if max(p[2] for p in f.Points) < 1e-4:
            bed += f.Area
            continue
        angle = math.degrees(math.asin(min(1.0, -nz)))
        if angle > 89.0:
            flat += f.Area
        elif angle > 50.0:
            steep += f.Area
            worst = max(worst, angle)
    return {'bed_contact_mm2': round(bed, 1), 'bridged_ceiling_mm2': round(flat, 1),
            'area_past_50_deg_mm2': round(steep, 1), 'worst_of_it_deg': round(worst, 1)}


def export_part(shape, name):
    b = shape.optimalBoundingBox(False, False)
    dims = [round(v, 2) for v in (b.XLength, b.YLength, b.ZLength)]
    assert max(dims) <= BED - 12, (name, 'bed', dims)
    assert abs(b.XMin) < 1e-4 and abs(b.YMin) < 1e-4 and abs(b.ZMin) < 1e-4, (name, 'origin')
    path = OUT/name
    shape.exportStep(str(path.with_suffix('.step')))
    # the mesher sometimes leaves a flaw on a long helical face at one setting: take the first clean one
    for lin, ang in ((0.02, 0.1), (0.02, 0.15), (0.03, 0.15), (0.05, 0.2)):
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang)
        if (mesh.isSolid() and not mesh.hasNonManifolds() and not mesh.hasSelfIntersections()
                and abs(mesh.Volume - shape.Volume)/shape.Volume < 0.003):
            break
    else:
        raise AssertionError(name + ': no clean mesh')
    mesh.write(str(path.with_suffix('.stl')))
    mesh.write(str(path.with_suffix('.3mf')))
    for ext in ('.stl', '.3mf'):
        m = Mesh.Mesh(str(path.with_suffix(ext)))
        assert m.isSolid() and not m.hasNonManifolds(), name + ext
        assert abs(m.Volume - shape.Volume)/shape.Volume < 0.003, name + ext + ' volume'
    saved = Part.Shape()
    saved.read(str(path.with_suffix('.step')))
    assert saved.isValid() and len(saved.Solids) == 1, name + ' STEP readback'
    assert abs(saved.Volume - shape.Volume)/shape.Volume < 1e-4, name + ' STEP volume'
    return {'print_bounds_mm': dims, 'volume_cm3': round(shape.Volume/1000, 2), 'stl_facets': mesh.CountFacets,
            'mesh_deflection_mm_rad': [lin, ang]}


def gap(a, b):
    return round(a.distToShape(b)[0], 3)


TOUCHING = [('hanger', 'desk'), ('hanger', 'clamp-pad'), ('clamp-pad', 'clamp-screw'),
            ('clamp-nut', 'clamp-body'), ('clamp-body', 'desk')]


def interference(parts):
    """Common volume of every pair of thread-free parts. Mated pairs touch; nothing may overlap.
    The thread pair is skipped: its proxies overlap by the thread depth."""
    names = sorted(parts)
    touching = {frozenset(p) for p in TOUCHING}
    worst, pairs, hits = 0.0, 0, []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if {a, b} == {'clamp-screw', 'clamp-nut'} or not parts[a].BoundBox.intersect(parts[b].BoundBox):
                continue
            pairs += 1
            vol = parts[a].common(parts[b]).Volume
            worst = max(worst, vol)
            if vol > (0.05 if frozenset((a, b)) in touching else 1e-6):
                hits.append((a, b, round(vol, 3)))
    assert not hits, ('interference', hits)
    return {'pairs_with_overlapping_boxes': pairs, 'collisions': 0, 'largest_touch_volume_mm3': round(worst, 4)}


def seats(desk):
    """Seat centres on the comb's top face, world frame."""
    return [V(x, y, COMB_TOP - desk) for y in slot_centres() for x in SEAT_X]


def hanging(parts, desk):
    """From every seat: a straight CABLE_D cable hanging down (smallest gap to the clamp and its
    hardware) and a plug standing PLUG_L high (its axis to the hanger's wall and flange)."""
    fixed = Part.makeCompound([parts[n] for n in ('clamp-body', 'clamp-nut', 'clamp-screw', 'clamp-pad')])
    # the hanger above the comb: flange, wall and gussets
    above = parts['hanger'].common(box(-10, 100, -WIDTH, WIDTH, COMB_TOP - desk + 0.5, 1 - desk))
    cable_gap = plug_gap = 1e9
    for seat in seats(desk):
        cable = move(cyl(CABLE_D/2, -700, 0), seat.x, seat.y, seat.z)
        cable_gap = min(cable_gap, cable.distToShape(fixed)[0])
        axis = Part.makeLine(seat + V(0, 0, 0.6), seat + V(0, 0, PLUG_L))
        plug_gap = min(plug_gap, axis.distToShape(above)[0])
    return round(cable_gap, 2), round(plug_gap, 2)


def cable_props(desk):
    """Cables for the renders only: one plug in a seat, the cable straight down, the other plug at
    its end. The FOLDED length hangs as a loop with both plugs in neighbouring seats."""
    barrel, tip, wire = 3.5, 1.75, 1.75
    seat_z = COMB_TOP - desk - (SEAT_D/2 - barrel)       # where a 7 mm barrel rests in the cone
    plug = cyl(barrel, seat_z, seat_z + 26).fuse(cyl(tip, seat_z + 25, seat_z + 40))
    props = {}
    for i, (y, length) in enumerate(zip(slot_centres(), SLOT_CABLES)):
        if length == FOLDED:
            for k in (0, 2):
                xa, xb = SEAT_X[k], SEAT_X[k + 1]
                r = (xb - xa)/2
                drop = (length - math.pi*r)/2
                loop = Part.makeTorus(r, wire, V(0, 0, seat_z - drop), V(0, 1, 0)).common(
                    box(-r - wire - 1, r + wire + 1, -wire - 1, wire + 1, seat_z - drop - r - wire - 1, seat_z - drop))
                side = cyl(wire, seat_z - drop, seat_z + 1)
                shape = Part.makeCompound([move(plug, xa), move(plug, xb), move(side, xa), move(side, xb), move(loop, xa + r)])
                props[f'cable-{length}-{i}-{k}'] = move(shape, 0, y)
            continue
        for k in range(4 if length <= 300 else 3):
            cable = cyl(wire, seat_z - length, seat_z + 1)
            far = cyl(barrel, seat_z - length - 26, seat_z - length).fuse(cyl(tip, seat_z - length - 40, seat_z - length - 25))
            props[f'cable-{length}-{i}-{k}'] = move(Part.makeCompound([plug, cable, far]), SEAT_X[k], y)
    return props


def write_mesh(shape, path):
    MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.03, AngularDeflection=0.2).write(str(path))


def main():
    for p in (OUT, CAD, RESEARCH/'render'):
        p.mkdir(parents=True, exist_ok=True)
    # print/plates/ belongs to build_plates.py, which runs after this build
    for old in [*OUT.glob('*'), *CAD.glob('*'), *(RESEARCH/'render').glob('*.stl')]:
        if old.is_file():
            old.unlink()
    holder = Holder()
    proxy = Holder(plain=True)
    report = {'status': 'FAIL', 'build_s': holder.build_s}

    # geometry facts the design rests on
    ys = slot_centres()
    teeth = [round(b - a - SLOT_W, 2) for a, b in zip(ys, ys[1:]) if b - a < 2*SLOT_PITCH]
    end_tooth = WIDTH/2 - ys[-1] - SLOT_W/2
    notch_tooth = ys[len(ys)//2] - SLOT_W/2 - NOTCH_HALF
    assert min(teeth + [end_tooth, notch_tooth]) >= 6.0, (teeth, end_tooth, notch_tooth)
    assert SLOT_PITCH - SEAT_D >= 1.9 and SEAT_X[1] - SEAT_X[0] - SEAT_D >= 0.9
    assert SLOT_PITCH - MOUTH_W >= 1.5, 'tooth tips'
    assert SEAT_X[0] - SEAT_D/2 - FRONT - MOUTH >= 0.7, 'first seat behind the slot mouth'
    assert WALL_X - GUSSET - SEAT_X[-1] - SEAT_D/2 - 1 >= 0.2, 'last seat cone clear of the wall gusset'
    assert NOTCH_HALF - CLAMP_HALF_W >= 1.0 and NOTCH_X - BOTTOM_JAW_L >= 2.0 and WALL_X - NOTCH_X >= 8.0
    assert TONGUE_HALF - PAD_R - POCKET_CLR >= 10.0 and BACK - SCREW_X - PAD_R - POCKET_CLR >= 10.0
    assert BACK - STRIP > SEAT_X[-2] and PLUG_ROOM >= PLUG_L + 5
    report['comb'] = {
        'slots': len(ys), 'slot_width_mm': SLOT_W, 'slot_pitch_mm': SLOT_PITCH, 'slot_mouth_mm': [MOUTH_W, MOUTH],
        'seats_per_slot': len(SEAT_X), 'seats': len(ys)*len(SEAT_X), 'seat_cone_mm': SEAT_D,
        'seat_pitch_along_slot_mm': SEAT_X[1] - SEAT_X[0], 'seat_behind_desk_edge_mm': list(SEAT_X),
        'tooth_width_mm': {'between_slots': min(teeth), 'ends': round(end_tooth, 2), 'beside_clamp': round(notch_tooth, 2)},
        'tooth_thickness_mm': {'tip': COMB_T, 'root': round(COMB_T + (ROOT_T - COMB_T)*(SEAT_X[-1] - FRONT)/(WALL_X - FRONT), 2)},
        'notch_mm': [2*NOTCH_HALF, NOTCH_X - FRONT]}
    report['hanger'] = {
        'width_mm': WIDTH, 'depth_behind_desk_edge_mm': BACK, 'height_below_desk_underside_mm': -BOTTOM,
        'comb_top_below_desk_underside_mm': -COMB_TOP, 'plug_room_mm': PLUG_ROOM, 'tooth_tips_behind_desk_edge_mm': FRONT,
        'flange_mm': {'thickness': FLANGE_T, 'wings_depth': STRIP, 'tongue_width': 2*TONGUE_HALF, 'tongue_front_behind_desk_edge': TONGUE_X,
                      'pad_pocket_depth': POCKET, 'pad_pocket_dia': 2*(PAD_R + POCKET_CLR)},
        'wall_mm': WALL_T, 'wall_openings_mm': [WINDOW_Y[1] - WINDOW_Y[0], PLUG_ROOM - 2*(GUSSET + WINDOW_MARGIN)]}

    # thread pair: the smallest gap in mesh, as in the solder arm
    turn = App.Placement(V(0, 0, 40.0), App.Rotation(V(0, 0, 1), 360*40.0/CLAMP['pitch']))
    report['thread'] = {**CLAMP, 'profile': '45 degree flanks, flat crest and root',
                        'radial_clearance_mm': THREAD_CLR + 0.05, 'gap_mm': gap(holder.screw, place(holder.nut, turn))}
    assert 0.2 <= report['thread']['gap_mm'] <= 0.4, report['thread']
    # the screw goes in from below: its tip and thread pass the jaw hole, the tip passes the nut
    assert BALL_R < CLAMP['r'] + THREAD_CLR + 0.05 - CLAMP['depth'] and CLAMP['r'] < CLAMP['r'] + 0.5

    # assembled on desks of several thicknesses
    assert holder.desk_min <= DESKS[0] and DESKS[-1] <= holder.desk_max, (holder.desk_min, holder.desk_max)
    report['desks'] = {}
    for desk in DESKS:
        plain = proxy.assemble(desk)
        info = interference(plain)
        nut_z = holder.slot_z + NUT_CLR
        thread = (plain['clamp-screw'].BoundBox.ZMin + SCREW_KNOB_H, plain['clamp-screw'].BoundBox.ZMin + SCREW_KNOB_H + SCREW_THREAD)
        assert thread[0] <= nut_z and thread[1] >= nut_z + NUT_H, ('thread not through the nut', desk, thread)
        cable_gap, plug_gap = hanging(plain, desk)
        assert cable_gap >= 5.0 and plug_gap >= 5.5, (desk, cable_gap, plug_gap)
        # nothing of the hanger is in front of the desk edge or above its underside
        b = plain['hanger'].BoundBox
        assert b.XMin >= TONGUE_X - 1e-6 and b.ZMax <= -desk + 1e-6, (desk, b)
        info.update({
            'knob_below_bottom_jaw_mm': round(-GAP - BOTTOM_JAW - plain['clamp-screw'].BoundBox.ZMin - SCREW_KNOB_H, 2),
            'pad_collar_above_bottom_jaw_mm': round(plain['clamp-pad'].BoundBox.ZMin + GAP, 2),
            'comb_underside_below_desk_top_mm': round(-b.ZMin, 1),
            'lowest_point_below_desk_top_mm': round(-plain['clamp-screw'].BoundBox.ZMin, 1),
            'real_thread_gap_mm': gap(*[holder.assemble(desk)[n] for n in ('clamp-screw', 'clamp-nut')]),
            f'cable_{CABLE_D:g}mm_to_clamp_mm': cable_gap, 'plug_axis_to_wall_and_flange_mm': plug_gap})
        assert info['knob_below_bottom_jaw_mm'] >= -1e-6 and info['pad_collar_above_bottom_jaw_mm'] >= -1e-6, info
        assert 0.2 <= info['real_thread_gap_mm'] <= 0.4, info
        report['desks'][f'{desk:g}'] = info
    # the hanger cannot leave: the pad stands in its pocket, the tongue's front edge faces the clamp spine
    shown = proxy.assemble(SHOWN)
    held = {}
    # into the desk the pad meets the pocket's 45 degree roof: 0.5 mm of clearance is 0.71 mm of travel
    for way, (dx, dy) in {'out_0.8mm': (-0.8, 0), 'in_1.2mm': (1.2, 0), 'sideways_0.8mm': (0, 0.8)}.items():
        moved = move(shown['hanger'], dx, dy)
        held[way] = (moved.common(shown['clamp-pad']).Volume, moved.common(shown['clamp-body']).Volume)
    assert min(v[0] for v in held.values()) > 5 and held['out_0.8mm'][1] > 5, held
    report['hanger_held'] = {f'moved_{way}_overlaps_pad_and_clamp_mm3': [round(v, 2) for v in vols] for way, vols in held.items()}
    report['hanger_held']['pad_in_pocket_mm'] = POCKET
    spine = shown['clamp-body'].BoundBox
    report['outside_the_desk'] = {'part': 'clamp-body', 'in_front_of_desk_edge_mm': round(-spine.XMin, 1), 'above_desk_top_mm': round(spine.ZMax, 1),
                                  'width_mm': round(spine.YLength, 1), 'on_desk_top_mm': JAW_L}

    # render meshes and the reference assembly (threads left out of the saved assembly)
    real = holder.assemble(SHOWN)
    folder = RESEARCH/'render'
    for part, shape in real.items():
        write_mesh(shape, folder/f'use-{part}.stl')
    for part, shape in cable_props(SHOWN).items():
        write_mesh(shape, folder/f'use-{part}.stl')
    doc = App.newDocument('DeskCableHolder')
    for part, shape in shown.items():
        if part != 'desk':
            doc.addObject('Part::Feature', part.replace('-', '_')).Shape = shape
    doc.recompute()
    doc.saveAs(str(CAD/'desk-cable-holder-assembly.FCStd'))
    App.closeDocument(doc.Name)
    Part.makeCompound([s for n, s in shown.items() if n != 'desk']).exportStep(str(OUT/'assembly-preview.step'))

    # print files
    report['print'] = {}
    total = 0.0
    doc = App.newDocument('DeskCableHolderParts')
    for name, (shape, copies, how) in holder.prints().items():
        info = export_part(shape, name)
        info.update({'copies': copies, 'orientation': how, **overhangs(shape)})
        # no supports: nothing past 50 degrees, no bridged ceiling
        assert info['area_past_50_deg_mm2'] == 0 and info['bridged_ceiling_mm2'] == 0, (name, info)
        report['print'][name] = info
        total += copies*shape.Volume
        doc.addObject('Part::Feature', name.replace('-', '_')).Shape = shape
        write_mesh(shape, folder/f'print-{name}.stl')
    doc.recompute()
    doc.saveAs(str(CAD/'desk-cable-holder-parts.FCStd'))
    App.closeDocument(doc.Name)
    report['solid_volume_cm3'] = round(total/1000, 1)

    report['dimensions'] = {
        'desk_thickness_mm': [round(holder.desk_min, 1), round(holder.desk_max, 1)], 'desk_thicknesses_checked_mm': list(DESKS),
        'clamp_reach_onto_desk_mm': JAW_L, 'clamp_reach_under_desk_mm': BOTTOM_JAW_L, 'clamp_width_mm': 2*CLAMP_HALF_W,
        'clamp_above_desk_top_mm': JAW_T, 'bottom_jaw_below_desk_top_mm': GAP + BOTTOM_JAW,
        'screw_thread_mm': SCREW_THREAD, 'thread_clearance_radial_mm': THREAD_CLR, 'cable_lengths_drawn_mm': list(CABLES),
        'shown_desk_mm': SHOWN, 'seat_below_desk_top_shown_mm': round(SHOWN - COMB_TOP, 1)}
    report['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['export_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.st*'))}
    report['status'] = 'PASS'
    text = json.dumps(report, indent=2) + '\n'
    (OUT/'verification.json').write_text(text)
    (RESEARCH/'build-report.json').write_text(text)
    print('DESK_CABLE_HOLDER_BUILD_PASS')


# FreeCADCmd imports scripts by stem, unlike CPython's __main__.
if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
