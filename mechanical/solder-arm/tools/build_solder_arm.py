"""Desk-clamp soldering arm for the module PCBs: every part is 3D printed, no metal hardware.

Build: mechanical/solder-arm/tools/build_solder_arm.sh

Chain, desk to board:
  desk clamp (C frame, printed screw + captive nut + snap-on pad)
    J1 yaw    -> swivel bracket
    J2 pitch  -> arm link (one)
    J3 turn   -> head rail with two sliding jaws; the board edges sit in the jaws' V grooves

The head sits on the side of the link and turns about a level axis through the board: J3 tilts
the board and, half a turn on, flips it over. The link is long enough for the head to turn all
the way round beside the swivel bracket (checked at every tooth step).

No board size is built in. The jaws slide on the rail, so the head takes any board edge-to-edge
distance between OPEN_MIN and OPEN_MAX; the build scans every .kicad_pcb in modules/ (carriers,
MCU boards, panels) and asserts that each one has a side in that range.

Every joint is the same: two face-tooth rings (TEETH radial teeth, so TEETH positions per turn),
one flat T-bolt and one knob. The bolt is keyed in one part (flat-sided hole + head pocket), so
the knob is tightened with one hand; half a turn back lets the teeth skip.

Threads are a 45 degree stub profile, cut with THREAD_CLR radial clearance. The joint bolts print
lying on their flat (layers along the bolt, the strong way); the clamp screw and the jaw
thumbscrews only push, and print standing.

Frames. Joint ports: origin on the tooth ring's mid plane, z out of the part, x the ring's zero
direction. A keyed part has a tooth tip at zero, the other part a valley, so angle 0 meshes.
Head frame: X along the rail, +Y from the rail to the board, Z across the board; the roll axis
(J3) is the Y axis. Clamp frame: desk top at z = 0, desk edge at x = 0, +X into the desk.

CAD-checked prototype: no part is printed, no fit is measured.
"""
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
ARM = Path(os.environ.get('ARM_DIR', Path(__file__).resolve().parents[1]))
REPO = ARM.parents[1]
OUT = ARM/'print'
CAD = ARM/'cad'
RESEARCH = ARM/'research'
BED = 256.0           # Bambu Lab P2S
FZ = 1e-4             # fuzzy tolerance: OCC booleans on the helical thread faces fail without it
FUSE = 0.5            # overlap of solids that are fused

# joints
T = 12.0              # plate thickness at every joint
HALF_W = 23.0         # plates and the link are 46 mm wide
TEETH = 36            # 10 degree steps
R_IN, R_OUT = 12.5, 20.5
TOOTH_H = 1.6         # valley to sharp tip at R_OUT; the height grows with the radius
TIP_CUT = 0.8         # tips are flat at this share of the half height, valleys stay sharp
MID = TOOTH_H/2       # ring mid plane above the plate face; two mated plates are 2*MID apart
RING_END = 1.5        # 45 degree cone at both ends of the teeth
JOINT = dict(r=7.0, depth=1.25, pitch=3.5, crest=0.5)
THUMB = dict(r=5.0, depth=1.0, pitch=3.0, crest=0.5)
CLAMP = dict(r=9.0, depth=1.8, pitch=5.0, crest=0.7)
THREAD_CLR = 0.35     # radial, on the internal thread
HOLE_CLR = 0.35       # bolt in a plain hole, radial
FLAT = 4.9            # bolt flats from the axis: the bolt is 9.8 mm thick
FLAT_CLR = 0.2
HEAD_HALF = 11.5      # T head half length
HEAD_CAP = 1.5        # straight part of the head
HEAD_SEAT = 0.45      # head top below the plate face when it sits on its 45 degree shoulders
POCKET_HALF = 11.75
POCKET_CAP = 1.7
TAPER_END = 4.5       # the 45 degree shoulders run on to this half length, as webs beside the shank
KNOB_R, KNOB_H = 19.0, 14.0
BOLT_L = 2*T + 2*MID - HEAD_SEAT + KNOB_H + 1.85   # 41 mm

# arm
LINK_L = 190.0        # joint to joint: the head (swing radius ~123 mm) turns clear of the swivel bracket
LEG = T + KNOB_R + 5 + HALF_W                      # bracket leg: 59 mm
LEG_HOLE = T + KNOB_R + 5                          # hole centre from the outer corner: 36 mm

# clamp
SPINE = 16.0
GAP = 68.0            # between the jaws
BOTTOM_JAW = 32.0
BOTTOM_JAW_L = 50.0
TOP_JAW_L = 74.0
J1_X = 48.0
SCREW_X = 30.0
NUT, NUT_H, NUT_CLR = 30.0, 16.0, 0.25
NUT_ROOF = 6.0        # jaw material above the nut slot
SCREW_THREAD = 95.0
SCREW_KNOB_R, SCREW_KNOB_H = 22.0, 12.0
NECK_R, NECK_H = 5.0, 6.0
BALL_R, BALL_TOP_R = 7.0, 4.5
BALL_UNDER, BALL_CYL, BALL_CONE = 2.0, 1.5, 2.5    # mushroom tip: 45 degree underside, straight, top cone
PAD_R, PAD_T, PAD_H = 20.0, 3.0, 13.5
PAD_BORE, PAD_LIP, PAD_WALL = 7.4, 6.7, 1.8
PAD_LIP_Z = 10.0

# head
RAIL_L = 240.0
RAIL_CHAMFER = 0.8
HUB_EXTRA = 6.0       # the hub stands this far behind the rail, so a jaw sleeve clears the arm link
SLIDE_CLR = 0.3       # jaw tunnel around the rail, each side
SLEEVE_L = 26.0
SLEEVE_WALL = 4.0     # back wall
FRONT_WALL = 6.0
FLOOR = 8.0           # bed side of the jaw: the thumbscrew thread is in it
ROOF = 3.0            # bridged over the tunnel
JOG = 16.0            # groove face to the sleeve: lets the fingers close in front of the hub
FINGER_T, FINGER_H, FINGER_L = 7.0, 10.0, 76.0
GROOVE_Z = 5.0        # board plane above the jaw's bed face
GROOVE_MOUTH, GROOVE_BOTTOM, GROOVE_D = 3.2, 0.6, 1.3   # 45 degree walls
LIP_CHAMFER = 2.0
THUMB_HEAD_R, THUMB_HEAD_H, THUMB_L = 10.0, 7.0, 11.0
BOARD_T = (0.8, 2.4)  # board thickness the groove takes on both flanks


# ---------- geometry helpers ----------

def frame(o, x, z):
    """Placement with the given origin, x and z axes."""
    x, z = V(x).normalize(), V(z).normalize()
    y = z.cross(x)
    return App.Placement(App.Matrix(x.x, y.x, z.x, o[0], x.y, y.y, z.y, o[1], x.z, y.z, z.z, o[2], 0, 0, 0, 1))


def place(shape, pl):
    return shape.transformed(pl.toMatrix(), True)


def move(shape, x=0, y=0, z=0):
    s = shape.copy()
    s.translate(V(x, y, z))
    return s


def one(shape, label):
    s = shape.removeSplitter()
    if not s.isValid():
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


PLAIN = False         # True: threads become plain cylinders (collision proxies, see Arm)


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
        # one sweep this long meshes badly (190k facets with false overhangs on the 95 mm clamp
        # screw): build it in pieces of at most 8 turns, they continue each other
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


def tooth_ring(kind):
    """Face-tooth ring on a plate face at z = 0, teeth up, from z = -FUSE. Every flank is a plane
    through the ring centre on the mid plane, so two rings touch along the whole flank. kind:
    'tip' (keyed part) or 'valley' at angle 0."""
    k = TOOTH_H/(2*R_OUT)
    r1, r2, zb = R_IN - 2.5, R_OUT + 2.5, -FUSE
    off = 0.5 if kind == 'tip' else 0.0

    def P(r, a, w=None):
        return V(r*math.cos(a), r*math.sin(a), zb if w is None else MID + k*r*w)

    def face(pts):
        return Part.Face(Part.makePolygon(pts + [pts[0]]))

    faces, outer, inner = [], [], []
    for i in range(TEETH):
        step = 2*math.pi/TEETH
        a = [(i - off + f)*step for f in (0, 0.25*(1 + TIP_CUT), 1 - 0.25*(1 + TIP_CUT), 1)]
        w = [-1, TIP_CUT, TIP_CUT, -1]
        for j in range(3):
            faces.append(face([P(r1, a[j], w[j]), P(r2, a[j], w[j]), P(r2, a[j + 1], w[j + 1]), P(r1, a[j + 1], w[j + 1])]))
            faces.append(face([P(r2, a[j]), P(r2, a[j + 1]), P(r2, a[j + 1], w[j + 1]), P(r2, a[j], w[j])]))
            faces.append(face([P(r1, a[j]), P(r1, a[j], w[j]), P(r1, a[j + 1], w[j + 1]), P(r1, a[j + 1])]))
            outer.append(P(r2, a[j]))
            inner.append(P(r1, a[j]))
    faces.append(face(outer).cut(face(inner)).Faces[0])
    shell = Part.makeCompound(faces)
    shell.sewShape()
    assert len(shell.Shells) == 1 and shell.Shells[0].isClosed(), 'tooth shell'
    solid = Part.Solid(shell.Shells[0])
    if solid.Volume < 0:
        solid.reverse()
    assert solid.isValid(), 'tooth polyhedron'
    env = rev([(R_IN - RING_END, zb), (R_IN - RING_END, 0), (R_IN, RING_END), (R_OUT, RING_END),
               (R_OUT + RING_END, 0), (R_OUT + RING_END, zb)])
    return one(solid.common(env), 'tooth ring')


def round_cut(length, up=False):
    """Plain bolt hole along +Z from z = -1. up: teardrop towards +X for a hole printed lying."""
    r = JOINT['r'] + HOLE_CLR
    cut = cyl(r, -1, length + 1)
    if up:
        s = r/math.sqrt(2)
        cut = cut.fuse(prism([(s, -s), (r*math.sqrt(2), 0), (s, s)], -1, length + 1))
    return cut


def keyed_cut(length, up=False):
    """Flat-sided bolt hole with the T head pocket, along +Z from the head-side face z = 0. The
    flats are the planes y = +-(FLAT + FLAT_CLR), the head lies along X. up: gabled towards +X."""
    r, f = JOINT['r'] + HOLE_CLR, FLAT + FLAT_CLR
    hole = cyl(r, -1, length + 1).common(box(-r - 1, r + 1, -f, f, -1, length + 1))
    e = TAPER_END - 0.2
    taper = POCKET_HALF - e
    pocket = prism_xz([(-POCKET_HALF, -1), (POCKET_HALF, -1), (POCKET_HALF, POCKET_CAP), (e, POCKET_CAP + taper),
                       (-e, POCKET_CAP + taper), (-POCKET_HALF, POCKET_CAP)], -f, f)
    cut = hole.fuse(pocket)
    if up:
        xc = math.sqrt(r*r - f*f)
        cut = cut.fuse(prism([(xc - 0.01, -f), (xc + f, 0), (xc - 0.01, f)], -1, length + 1))
        cut = cut.fuse(prism([(POCKET_HALF - 0.01, -f), (POCKET_HALF + f, 0), (POCKET_HALF - 0.01, f)], -1, POCKET_CAP))
    return cut


def print_pose(shape, rot=None):
    """Rotate into the print orientation and put the bounding box corner on the origin."""
    s = shape.copy()
    if rot:
        s = s.transformed(App.Placement(V(0, 0, 0), App.Rotation(*rot)).toMatrix(), True)
    b = s.optimalBoundingBox(False, False)     # BoundBox is loose around the helical faces
    s.translate(V(-b.XMin, -b.YMin, -b.ZMin))
    return s


# ---------- parts, each in its use frame ----------

def joint_bolt():
    """Flat T bolt: head top at z = 0, thread along +Z, flats y = +-FLAT, head along X."""
    r, d = JOINT['r'], JOINT['depth']
    rod = thread_rod(JOINT, 0, BOLT_L)
    rod = rod.common(rev([(0, 0), (r + 1, 0), (r + 1, BOLT_L - d - 1.5), (r - d - 0.3, BOLT_L), (0, BOLT_L)]), FZ)
    taper = HEAD_HALF - TAPER_END
    head = prism_xz([(-HEAD_HALF, 0), (HEAD_HALF, 0), (HEAD_HALF, HEAD_CAP), (TAPER_END, HEAD_CAP + taper),
                     (-TAPER_END, HEAD_CAP + taper), (-HEAD_HALF, HEAD_CAP)], -FLAT, FLAT)
    bolt = rod.fuse(head, FZ).common(box(-20, 20, -FLAT, FLAT, -1, BOLT_L + 1), FZ)
    return one(bolt, 'joint bolt')


def threaded_knob(spec, clr, r, h, lobes, scallop):
    return one(tapped(lobed(r, h, lobes, scallop), spec, clr, 0, h), 'knob')


def joint_knob():
    return threaded_knob(JOINT, THREAD_CLR, KNOB_R, KNOB_H, 6, 7.0)


def link():
    """Arm link, flat, teeth on the z = T face, a plain bolt hole at both ends (the bolts are keyed
    in the bracket and in the head; both knobs sit on the z = 0 face). End a at the origin, end b
    at (LINK_L, 0)."""
    body = cyl(HALF_W, 0, T).fuse(move(cyl(HALF_W, 0, T), LINK_L)).fuse(box(0, LINK_L, -HALF_W, HALF_W, 0, T))
    ports = {}
    for name, x in (('a', 0.0), ('b', LINK_L)):
        body = body.fuse(move(tooth_ring('valley'), x, 0, T))
        body = body.cut(move(round_cut(T + 3), x))
        ports[name] = frame((x, 0, T + MID), (1, 0, 0), (0, 0, 1))
    return one(body, 'link'), ports


def bracket():
    """Swivel bracket, an L of two plates. Plate A (x 0..T, along Y) is keyed, plate B (y 0..T,
    along X) takes a knob on its inner face. Teeth on both outer faces. Prints on its side."""
    c = 3.0
    prof = [(c, 0), (LEG - c, 0), (LEG, c), (LEG, T), (T + 4, T), (T, T + 4), (T, LEG), (c, LEG), (0, LEG - c), (0, c)]
    body = prism(prof, -HALF_W, HALF_W)
    ring_a = frame((0, LEG_HOLE, 0), (0, 1, 0), (-1, 0, 0))
    ring_b = frame((LEG_HOLE, 0, 0), (1, 0, 0), (0, -1, 0))
    body = body.fuse(place(tooth_ring('tip'), ring_a)).fuse(place(tooth_ring('valley'), ring_b))
    bolt_a = frame((T, LEG_HOLE, 0), (0, 0, 1), (-1, 0, 0))
    body = body.cut(place(keyed_cut(T + 3, up=True), bolt_a))
    body = body.cut(place(round_cut(T + 3, up=True), frame((LEG_HOLE, T, 0), (0, 0, 1), (0, -1, 0))))
    ports = {'A': frame((-MID, LEG_HOLE, 0), (0, 1, 0), (-1, 0, 0)), 'B': frame((LEG_HOLE, -MID, 0), (1, 0, 0), (0, -1, 0))}
    return one(body, 'bracket'), ports, {'A': bolt_a}


def clamp_body():
    g, bj = GAP, BOTTOM_JAW
    prof = [(-SPINE + 4, T), (TOP_JAW_L - 3, T), (TOP_JAW_L, T - 3), (TOP_JAW_L, 1), (TOP_JAW_L - 1, 0), (6, 0), (0, -6),
            (0, -g + 10), (10, -g), (BOTTOM_JAW_L, -g), (BOTTOM_JAW_L, -g - bj + 3), (BOTTOM_JAW_L - 3, -g - bj),
            (-SPINE + 4, -g - bj), (-SPINE, -g - bj + 4), (-SPINE, T - 4)]
    body = prism_xz(prof, -HALF_W, HALF_W)
    body = body.fuse(move(tooth_ring('tip'), J1_X, 0, T))
    bolt = frame((J1_X, 0, 0), (0, 1, 0), (0, 0, 1))
    body = body.cut(place(keyed_cut(T + 3, up=True), bolt))
    # clamp screw: clearance hole through the bottom jaw, nut slot open on the +Y side
    hole = cyl(CLAMP['r'] + 0.5, -g - bj - 1, -g + 1)
    s = (CLAMP['r'] + 0.5)/math.sqrt(2)
    hole = hole.fuse(prism([(-s, s), (0, (CLAMP['r'] + 0.5)*math.sqrt(2)), (s, s)], -g - bj - 1, -g + 1))
    body = body.cut(move(hole, SCREW_X))
    half = NUT/2 + NUT_CLR
    slot_z = -g - NUT_ROOF - NUT_H - 2*NUT_CLR
    body = body.cut(box(SCREW_X - half, SCREW_X + half, -half, HALF_W + 1, slot_z, -g - NUT_ROOF))
    port = frame((J1_X, 0, T + MID), (1, 0, 0), (0, 0, 1))
    return one(body, 'clamp'), {'top': port}, {'top': bolt}, slot_z


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
    tip = rev([(0, z1 - 1), (NECK_R, z1 - 1), (NECK_R, za), (BALL_R, za + BALL_UNDER), (BALL_R, za + BALL_UNDER + BALL_CYL),
               (BALL_TOP_R, za + BALL_UNDER + BALL_CYL + BALL_CONE), (0, za + BALL_UNDER + BALL_CYL + BALL_CONE)])
    body = lobed(SCREW_KNOB_R, SCREW_KNOB_H, 6, 8.0).fuse(rod, FZ).fuse(tip, FZ)
    return one(body, 'clamp screw'), za + BALL_UNDER + BALL_CYL + BALL_CONE


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


def rail():
    c, h = RAIL_CHAMFER, T/2
    sec = [(-T + c, -h), (-c, -h), (0, -h + c), (0, h - c), (-c, h), (-T + c, h), (-T, h - c), (-T, -h + c)]   # (y, z)
    wire = Part.makePolygon([V(-RAIL_L/2, y, z) for y, z in sec] + [V(-RAIL_L/2, sec[0][0], sec[0][1])])
    body = Part.Face(wire).extrude(V(RAIL_L, 0, 0))
    to_y = frame((0, 0, 0), (1, 0, 0), (0, -1, 0))        # local z -> head -Y
    back = T + HUB_EXTRA
    body = body.fuse(place(cyl(HALF_W, 0, back), to_y))
    body = body.fuse(place(tooth_ring('tip'), frame((0, -back, 0), (1, 0, 0), (0, -1, 0))))
    # the standard bolt: its pocket starts HUB_EXTRA inside the front face
    bolt = frame((0, -HUB_EXTRA, 0), (1, 0, 0), (0, -1, 0))
    f = FLAT + FLAT_CLR
    body = body.cut(place(keyed_cut(T + 3), bolt)).cut(box(-POCKET_HALF, POCKET_HALF, -HUB_EXTRA - 0.5, 1, -f, f))
    port = frame((0, -back - MID, 0), (1, 0, 0), (0, -1, 0))
    return one(body, 'rail'), {'hub': port}, {'hub': bolt}


def jaw(side):
    """Sliding jaw in its print frame: bed at z = 0, groove face at x = 0, sleeve at +x (side = 1)
    or mirrored (side = -1). The rail axis is at y = -T/2, z = FLOOR + SLIDE_CLR + T/2."""
    tunnel = T + 2*SLIDE_CLR
    height = FLOOR + tunnel + ROOF
    y_front = SLIDE_CLR + FRONT_WALL
    y_back = -T - SLIDE_CLR - SLEEVE_WALL
    x1 = JOG + SLEEVE_L
    body = box(JOG, x1, y_back, y_front, 0, height).fuse(box(0, x1, SLIDE_CLR, y_front, 0, height))
    tip = y_front + FINGER_L
    finger = prism([(0, y_front - FUSE), (FINGER_T + 10, y_front - FUSE), (FINGER_T + 10, y_front), (FINGER_T, y_front + 10),
                    (FINGER_T, tip - 3), (FINGER_T - 3, tip), (0, tip)], 0, FINGER_H)
    body = body.fuse(finger)
    body = body.cut(box(JOG - 1, x1 + 1, -T - SLIDE_CLR, SLIDE_CLR, FLOOR, FLOOR + tunnel))
    m, b = GROOVE_MOUTH/2, GROOVE_BOTTOM/2
    out = m + (m - b)/GROOVE_D
    body = body.cut(prism_xz([(-1, GROOVE_Z - out), (0, GROOVE_Z - m), (GROOVE_D, GROOVE_Z - b),
                              (GROOVE_D, GROOVE_Z + b), (0, GROOVE_Z + m), (-1, GROOVE_Z + out)], 0, tip + 1))
    c = LIP_CHAMFER
    body = body.cut(prism_xz([(-1, -1), (c, -1), (c, 0), (0, c), (-1, c)], 0, tip + 1))
    body = body.cut(prism_xz([(-1, FINGER_H + 1), (c, FINGER_H + 1), (c, FINGER_H), (0, FINGER_H - c), (-1, FINGER_H - c)], y_front, tip + 1))
    sx = JOG + SLEEVE_L/2
    if side < 0:
        body = body.mirror(V(0, 0, 0), V(1, 0, 0))
        sx = -sx
    body = tapped(body, THUMB, THREAD_CLR, 0, FLOOR, sx, -T/2, ends=(True, False))
    return one(body, 'jaw'), V(sx, -T/2, 0), height


def thumbscrew():
    """Head at z = 0, thread up; the flat tip presses on the rail."""
    r, d = THUMB['r'], THUMB['depth']
    z1 = THUMB_HEAD_H + THUMB_L
    rod = thread_rod(THUMB, THUMB_HEAD_H - 1, z1)
    rod = rod.common(rev([(0, 0), (r + 1, 0), (r + 1, z1 - d - 0.3), (r - d - 0.3, z1), (0, z1)]), FZ)
    return one(lobed(THUMB_HEAD_R, THUMB_HEAD_H, 8, 3.0, 0.8).fuse(rod, FZ), 'thumbscrew')


# ---------- checks ----------

def overhangs(posed):
    """Downward faces of a print pose, from its mesh. Angles from a vertical wall: 90 = ceiling.
    The 45 degree cones and thread flanks mesh to facets of up to 48 degrees, so the limit is 50."""
    mesh = MeshPart.meshFromShape(Shape=posed, LinearDeflection=0.02, AngularDeflection=0.15)
    bed = steep = flat = 0.0
    worst = 0.0
    steep_top = 0.0
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
            steep_top = max(steep_top, max(p[2] for p in f.Points))
            worst = max(worst, angle)
    return {'bed_contact_mm2': round(bed, 1), 'bridged_ceiling_mm2': round(flat, 1),
            'area_past_50_deg_mm2': round(steep, 1), 'worst_of_it_deg': round(worst, 1),
            'highest_of_it_above_bed_mm': round(steep_top, 2)}


def export_part(shape, name):
    b = shape.optimalBoundingBox(False, False)
    dims = [round(v, 2) for v in (b.XLength, b.YLength, b.ZLength)]
    assert max(dims) <= BED - 4, (name, 'bed', dims)
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


def board_sizes():
    """Outline size of every KiCad board in modules/: Edge.Cuts bounding box and thickness."""
    found = {}
    for path in sorted(REPO.glob('modules/*/hardware/**/*.kicad_pcb')) + sorted(REPO.glob('modules/*/panels/front-pcb/*.kicad_pcb')):
        text = path.read_text()
        xs, ys = [], []
        for m in re.finditer(r'\n\t\((gr_\w+)\b', text):
            i, depth = m.start() + 2, 0
            for j in range(i, len(text)):
                depth += (text[j] == '(') - (text[j] == ')')
                if depth == 0:
                    break
            item = text[i:j + 1]
            if '(layer "Edge.Cuts")' not in item:
                continue
            pts = [(float(a), float(b)) for a, b in re.findall(r'\((?:start|end|mid|xy)\s+(-?[\d.]+)\s+(-?[\d.]+)\)', item)]
            centre = re.search(r'\(center\s+(-?[\d.]+)\s+(-?[\d.]+)\)', item)
            if m.group(1) == 'gr_circle' and centre:
                cx, cy = float(centre.group(1)), float(centre.group(2))
                r = math.dist((cx, cy), pts[0])
                pts = [(cx - r, cy - r), (cx + r, cy + r)]
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        if not xs:
            continue
        thick = re.search(r'\(thickness\s+([\d.]+)\)', text)
        found[str(path.relative_to(REPO))] = (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2),
                                              float(thick.group(1)) if thick else 1.6)
    return found


def groove_seat(t):
    """How far a board of thickness t goes into the V groove."""
    return (GROOVE_MOUTH - t)*GROOVE_D/(GROOVE_MOUTH - GROOVE_BOTTOM)


# ---------- assembly ----------

FLIP = App.Placement(V(0, 0, 0), App.Rotation(V(1, 0, 0), 180))


def mate(world_port, angle, local_port):
    """Placement of a part whose local_port meshes with world_port, turned by angle degrees."""
    return world_port.multiply(FLIP).multiply(App.Placement(V(0, 0, 0), App.Rotation(V(0, 0, 1), angle))).multiply(local_port.inverse())


def hardware(pl, bolt_frame, other_t=T):
    """Bolt and knob placements for a joint whose keyed part sits at pl."""
    seat = App.Placement(V(0, 0, HEAD_SEAT), App.Rotation())
    bolt_pl = pl.multiply(bolt_frame).multiply(seat)
    zk = T + 2*MID + other_t - HEAD_SEAT
    turn = App.Placement(V(0, 0, zk), App.Rotation(V(0, 0, 1), 360*zk/JOINT['pitch']))
    return bolt_pl, bolt_pl.multiply(turn)


class Arm:
    """All parts. plain = True builds them without threads: OCC booleans between two solids with
    helical faces (a nut in its slot, a knob on a plate) came back empty or failed here, so the
    pose collision checks run on these proxies. Thread pairs are checked by their gap instead."""

    def __init__(self, plain=False):
        global PLAIN
        t0 = time.time()
        PLAIN = plain
        try:
            self.build()
        finally:
            PLAIN = False
        self.build_s = round(time.time() - t0, 1)

    def build(self):
        self.bolt = joint_bolt()
        self.knob = joint_knob()
        self.link, self.ln_ports = link()
        self.bracket, self.br_ports, self.br_bolts = bracket()
        self.clamp, self.cl_ports, self.cl_bolts, self.slot_z = clamp_body()
        self.nut = clamp_nut()
        self.screw, self.screw_len = clamp_screw()
        self.pad = clamp_pad()
        self.rail, self.rl_ports, self.rl_bolts = rail()
        self.jaw_r, self.thumb_r, self.jaw_h = jaw(1)
        self.jaw_l, self.thumb_l, _ = jaw(-1)
        self.thumb = thumbscrew()
        self.rail_z = FLOOR + SLIDE_CLR + T/2          # rail axis above the jaw's bed face
        self.open_min = 2*(HALF_W + SLIDE_CLR - JOG)
        self.open_max = 2*(RAIL_L/2 - JOG - SLEEVE_L)

    def prints(self):
        """Print poses: name -> (shape, copies, orientation note)."""
        side = (V(1, 0, 0), 90)
        return {
            'clamp-body': (print_pose(self.clamp, side), 1, 'on its side, nut slot open upwards'),
            'clamp-screw': (print_pose(self.screw), 1, 'standing on its knob'),
            'clamp-nut': (print_pose(self.nut), 1, 'flat'),
            'clamp-pad': (print_pose(self.pad), 1, 'disc on the bed, collar up'),
            'swivel-bracket': (print_pose(self.bracket), 1, 'on its side (the L on the bed)'),
            'arm-link': (print_pose(self.link), 1, 'flat, teeth up'),
            'head-rail': (print_pose(self.rail, (V(1, 0, 0), -90)), 1, 'front face on the bed, teeth up'),
            'jaw-left': (print_pose(self.jaw_l), 1, 'thick floor on the bed'),
            'jaw-right': (print_pose(self.jaw_r), 1, 'thick floor on the bed'),
            'joint-bolt': (print_pose(self.bolt, side), 3, 'lying on a flat'),
            'joint-knob': (print_pose(self.knob), 3, 'flat'),
            'jaw-thumbscrew': (print_pose(self.thumb), 2, 'standing on its head'),
        }

    def assemble(self, q, board, desk=25.0):
        """World placements. q = joint angles J1..J3 in degrees (multiples of 360/TEETH);
        board = (grip distance, other side, thickness)."""
        assert all(abs(a/(360/TEETH) - round(a/(360/TEETH))) < 1e-9 for a in q), 'angle off the tooth grid'
        parts = {}
        I = App.Placement()

        def add(name, shape, pl):
            parts[name] = place(shape, pl)

        def joint(n, shape, pl, bolt_frame):
            b, k = hardware(pl, bolt_frame)
            add(f'bolt-{n}', self.bolt, b)
            add(f'knob-{n}', self.knob, k)

        add('clamp-body', self.clamp, I)
        joint(1, self.clamp, I, self.cl_bolts['top'])
        turret = mate(self.cl_ports['top'], q[0], self.br_ports['B'])
        add('turret', self.bracket, turret)
        joint(2, self.bracket, turret, self.br_bolts['A'])
        arm = mate(turret.multiply(self.br_ports['A']), q[1], self.ln_ports['a'])
        add('link', self.link, arm)
        head = mate(arm.multiply(self.ln_ports['b']), q[2], self.rl_ports['hub'])
        add('head-rail', self.rail, head)
        joint(3, self.rail, head, self.rl_bolts['hub'])

        # jaws: print frame -> head frame
        grip, other, thick = board
        g = grip/2 - groove_seat(thick)
        assert self.open_min/2 - 1e-9 <= g <= self.open_max/2 + 1e-9, ('jaw range', 2*g)
        zt = FLOOR - 1.5                                  # thumbscrew tip on the rail's chamfered face
        z0 = FLOOR + SLIDE_CLR - (THUMB_HEAD_H + THUMB_L)
        for name, shape, sx, s in (('jaw-right', self.jaw_r, self.thumb_r, 1), ('jaw-left', self.jaw_l, self.thumb_l, -1)):
            pl = head.multiply(App.Placement(V(s*g, 0, -self.rail_z), App.Rotation()))
            add(name, shape, pl)
            add('thumbscrew-' + name[4:], self.thumb,
                pl.multiply(App.Placement(V(sx.x, sx.y, z0), App.Rotation(V(0, 0, 1), 360*z0/THUMB['pitch']))))
        y0 = SLIDE_CLR + 2.0
        pcb = box(-grip/2, grip/2, y0, y0 + other, GROOVE_Z - thick/2, GROOVE_Z + thick/2)
        add('board', pcb, head.multiply(App.Placement(V(0, 0, -self.rail_z), App.Rotation())))

        # clamp screw, nut and pad for this desk
        add('clamp-nut', self.nut, App.Placement(V(SCREW_X, 0, self.slot_z), App.Rotation()))
        zs = -desk - PAD_T - self.screw_len
        dz = zs - self.slot_z
        add('clamp-screw', self.screw, App.Placement(V(SCREW_X, 0, zs), App.Rotation(V(0, 0, 1), -360*dz/CLAMP['pitch'])))
        add('clamp-pad', self.pad, App.Placement(V(SCREW_X, 0, -desk), App.Rotation(V(1, 0, 0), 180)))
        add('desk', box(6, 330, -260, 260, -desk, 0), I)
        self.head = head
        # board: its normal against the desk normal (0 = level, thumbscrews down; 180 = flipped)
        self.board_deg = math.degrees(math.acos(max(-1.0, min(1.0, head.Rotation.multVec(V(0, 0, 1)).z))))
        self.link_deg = math.degrees(math.asin(max(-1.0, min(1.0, arm.Rotation.multVec(V(1, 0, 0)).z))))
        return parts


MATED = [('bolt-1', 'clamp-body'), ('bolt-1', 'turret'), ('bolt-1', 'knob-1'), ('knob-1', 'turret'), ('clamp-body', 'turret'),
         ('bolt-2', 'turret'), ('bolt-2', 'link'), ('bolt-2', 'knob-2'), ('knob-2', 'link'), ('turret', 'link'),
         ('bolt-3', 'head-rail'), ('bolt-3', 'link'), ('bolt-3', 'knob-3'), ('knob-3', 'link'), ('link', 'head-rail'),
         ('jaw-right', 'head-rail'), ('jaw-left', 'head-rail'), ('thumbscrew-right', 'jaw-right'), ('thumbscrew-left', 'jaw-left'),
         ('thumbscrew-right', 'head-rail'), ('thumbscrew-left', 'head-rail'), ('board', 'jaw-right'), ('board', 'jaw-left'),
         ('clamp-nut', 'clamp-body'), ('clamp-screw', 'clamp-nut'), ('clamp-screw', 'clamp-body'), ('clamp-screw', 'clamp-pad'),
         ('clamp-pad', 'desk'), ('clamp-body', 'desk'), ('bolt-1', 'desk')]
THREADED = [('bolt-1', 'knob-1'), ('bolt-2', 'knob-2'), ('bolt-3', 'knob-3'),
            ('clamp-screw', 'clamp-nut'), ('thumbscrew-right', 'jaw-right'), ('thumbscrew-left', 'jaw-left')]
HEAD = ('head-rail', 'jaw-left', 'jaw-right', 'thumbscrew-left', 'thumbscrew-right', 'board')
FIXED = ('desk', 'clamp-body', 'turret', 'bolt-1', 'knob-1', 'bolt-2', 'knob-2')


def interference(parts):
    """Common volume of every pair of thread-free parts. Mated pairs touch; nothing may overlap.
    A thread pair is skipped: its proxies overlap by the thread depth."""
    names = sorted(parts)
    worst, pairs = 0.0, 0
    hits = []
    mated = {frozenset(p) for p in MATED}
    threaded = {frozenset(p) for p in THREADED}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = parts[a], parts[b]
            if frozenset((a, b)) in threaded or not A.BoundBox.intersect(B.BoundBox):
                continue
            pairs += 1
            vol = A.common(B).Volume
            limit = 0.5 if frozenset((a, b)) in mated else 1e-6
            worst = max(worst, vol)
            if vol > limit:
                hits.append((a, b, round(vol, 3)))
    assert not hits, ('interference', hits)
    return {'pairs_with_overlapping_boxes': pairs, 'collisions': 0, 'largest_touch_volume_mm3': round(worst, 4)}


def gap(a, b):
    return round(a.distToShape(b)[0], 3)


POSES = {
    # J1 yaw (0 = link along the desk edge), J2 link (0 = straight up), J3 head (0 = rail along the link);
    # board gripped across this side
    'work': ((300, 60, 330), (110.0, 29.0, 1.6)),      # arm swung 60 degrees over the desk, link 30 degrees up, board level; 6HP carrier held by its ends
    'flipped': ((300, 60, 150), (110.0, 29.0, 1.6)),   # the same, J3 half a turn on
    'low': ((300, 80, 350), (110.0, 29.0, 1.6)),       # link 10 degrees up, board level
    'mirrored': ((120, 300, 210), (110.0, 29.0, 1.6)), # as work with J1 half a turn on and the link leaning the other way: the link is on the board's other side
    'tilted': ((300, 50, 290), (91.3, 110.0, 1.6)),    # link 40 degrees up, board tilted 30 degrees, 18HP carrier
    'easel': ((0, 30, 0), (29.0, 110.0, 1.6)),         # link along the desk edge, board tilted 60 degrees, 6HP carrier held by its long edges
}
SWEEP = 'work'        # J3 is turned through every tooth step in this pose


def head_sweep(proxy):
    """Turn the head through all TEETH steps of J3 in the SWEEP pose: smallest gap from the head
    (rail, jaws, thumbscrews, board) to the desk, clamp, bracket and their hardware, and from
    the jaws and the board to the arm link they turn beside."""
    q, board = POSES[SWEEP]
    fixed_gap = link_gap = 1e9
    for i in range(TEETH):
        parts = proxy.assemble((q[0], q[1], i*360/TEETH), board)
        head = Part.makeCompound([parts[n] for n in HEAD])
        fixed_gap = min(fixed_gap, head.distToShape(Part.makeCompound([parts[n] for n in FIXED]))[0])
        link_gap = min(link_gap, Part.makeCompound([parts[n] for n in HEAD[1:]]).distToShape(parts['link'])[0])
    assert fixed_gap > 5.0 and link_gap > 2.0, ('head sweep', fixed_gap, link_gap)
    return {'pose': SWEEP, 'steps': TEETH, 'smallest_gap_to_desk_clamp_bracket_mm': round(fixed_gap, 2),
            'smallest_gap_jaws_to_link_mm': round(link_gap, 2)}


def main():
    for p in (OUT, CAD, RESEARCH):
        p.mkdir(parents=True, exist_ok=True)
    # print/plates/ belongs to build_plates.py, which runs after this build
    for old in [*OUT.glob('*'), *OUT.glob('plates/*'), *CAD.glob('*'), *(RESEARCH/'render').glob('*.stl')]:
        if old.is_file():
            old.unlink()
    arm = Arm()
    proxy = Arm(plain=True)
    report = {'status': 'FAIL', 'build_s': arm.build_s}

    # threads: one clearance everywhere, checked as the smallest gap of each pair in mesh
    turn = lambda dz, pitch: App.Placement(V(0, 0, dz), App.Rotation(V(0, 0, 1), 360*dz/pitch))
    report['threads'] = {
        'profile': '45 degree flanks, flat crest and root',
        'joint': {**JOINT, 'gap_mm': gap(arm.bolt, place(arm.knob, turn(20.0, JOINT['pitch'])))},
        'clamp': {**CLAMP, 'gap_mm': gap(arm.screw, place(arm.nut, turn(40.0, CLAMP['pitch'])))},
        'thumbscrew': {**THUMB, 'gap_mm': gap(place(arm.thumb, App.Placement(arm.thumb_r, App.Rotation()).multiply(turn(-9.0, THUMB['pitch']))), arm.jaw_r)},
    }
    for k in ('joint', 'clamp', 'thumbscrew'):
        assert 0.2 <= report['threads'][k]['gap_mm'] <= 0.4, (k, report['threads'][k])

    # teeth: flanks touch at angle 0, tips do not reach the valleys, half a step collides
    tip, valley = tooth_ring('tip'), tooth_ring('valley')
    up = App.Placement(V(0, 0, 2*MID), App.Rotation(V(1, 0, 0), 180))
    meshed = place(valley, up)
    half = place(valley, up.multiply(App.Placement(V(0, 0, 0), App.Rotation(V(0, 0, 1), 180/TEETH))))
    k = TOOTH_H/(2*R_OUT)
    report['teeth'] = {'count': TEETH, 'step_deg': 360/TEETH,
                       'flank_to_plate_deg': round(math.degrees(math.atan(k*(1 + TIP_CUT)/(0.5*math.pi*(1 + TIP_CUT)/TEETH))), 1),
                       'meshed_overlap_mm3': round(tip.common(meshed).Volume, 4),
                       'half_step_overlap_mm3': round(tip.common(half).Volume, 1),
                       'lift_to_skip_mm': round(TOOTH_H*(1 + TIP_CUT)/2, 2),
                       'knob_turns_to_skip': round(TOOTH_H*(1 + TIP_CUT)/2/JOINT['pitch'], 2)}
    assert report['teeth']['meshed_overlap_mm3'] < 0.01 and report['teeth']['half_step_overlap_mm3'] > 20

    # boards in the repo
    seat = groove_seat(1.6)
    lo, hi = arm.open_min + 2*seat, arm.open_max + 2*seat
    boards = {}
    for path, (w, h, t) in board_sizes().items():
        assert BOARD_T[0] <= t <= BOARD_T[1], (path, t)
        fits = [s for s in (w, h) if arm.open_min + 2*groove_seat(t) <= s <= arm.open_max + 2*groove_seat(t)]
        assert fits, (path, w, h)
        boards[path] = {'size_mm': [w, h], 'thickness_mm': t, 'grip_across_mm': fits}
    report['boards'] = {'grip_range_for_1.6_mm_boards_mm': [round(lo, 2), round(hi, 2)],
                        'groove_bite_mm': {'1.6': round(seat, 2), '2.0': round(groove_seat(2.0), 2)},
                        'board_thickness_range_mm': list(BOARD_T), 'scanned': len(boards), 'all_fit': True, 'boards': boards}

    # assembly poses
    report['poses'] = {}
    for name, (q, board) in POSES.items():
        parts = arm.assemble(q, board)
        plain = proxy.assemble(q, board)
        info = interference(plain)
        c = parts['board'].BoundBox.Center
        info.update({'angles_deg': list(q), 'board_mm': list(board), 'link_above_level_deg': round(arm.link_deg, 1),
                     'board_tilt_deg': round(arm.board_deg, 1), 'board_centre_mm': [round(c.x, 1), round(c.y, 1), round(c.z, 1)],
                     'board_to_jaw_mm': [gap(parts['board'], parts['jaw-left']), gap(parts['board'], parts['jaw-right'])]})
        report['poses'][name] = info
        folder = RESEARCH/'render'
        folder.mkdir(exist_ok=True)
        for part, shape in parts.items():
            mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.03, AngularDeflection=0.2)
            mesh.write(str(folder/f'{name}-{part}.stl'))
        if name == 'work':
            # reference assembly, threads left out to keep the files small
            doc = App.newDocument('SolderArm')
            for part, shape in plain.items():
                if part != 'desk':
                    doc.addObject('Part::Feature', part.replace('-', '_')).Shape = shape
            doc.recompute()
            doc.saveAs(str(CAD/'solder-arm-assembly.FCStd'))
            App.closeDocument(doc.Name)
            Part.makeCompound([s for n, s in plain.items() if n != 'desk']).exportStep(str(OUT/'assembly-preview.step'))

    report['head_sweep'] = head_sweep(proxy)

    # print files
    report['print'] = {}
    total = 0.0
    doc = App.newDocument('SolderArmParts')
    for name, (shape, copies, how) in arm.prints().items():
        info = export_part(shape, name)
        info.update({'copies': copies, 'orientation': how, **overhangs(shape)})
        report['print'][name] = info
        total += copies*shape.Volume
        doc.addObject('Part::Feature', name.replace('-', '_')).Shape = shape
        folder = RESEARCH/'render'
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.03, AngularDeflection=0.2).write(str(folder/f'print-{name}.stl'))
    doc.recompute()
    doc.saveAs(str(CAD/'solder-arm-parts.FCStd'))
    App.closeDocument(doc.Name)
    report['solid_volume_cm3'] = round(total/1000, 1)

    # supports: only the declared exceptions
    for name, info in report['print'].items():
        if name.startswith('jaw-') and name != 'jaw-thumbscrew':
            assert info['area_past_50_deg_mm2'] == 0 and info['bridged_ceiling_mm2'] < (T + 2*SLIDE_CLR)*SLEEVE_L + 1, (name, info)
        elif name == 'joint-bolt':
            assert info['bridged_ceiling_mm2'] == 0 and info['highest_of_it_above_bed_mm'] < 2.0, (name, info)
        else:
            assert info['area_past_50_deg_mm2'] == 0 and info['bridged_ceiling_mm2'] == 0, (name, info)

    report['dimensions'] = {
        'joint_plate_mm': T, 'link_joint_to_joint_mm': LINK_L, 'joints': 3,
        'link_pivot_above_desk_mm': T + 2*MID + LEG_HOLE,
        'jaw_opening_mm': [round(arm.open_min, 2), round(arm.open_max, 2)], 'finger_length_mm': FINGER_L,
        'rail_mm': [RAIL_L, T, T], 'joint_bolt_length_mm': BOLT_L,
        'desk_thickness_mm': [5, GAP - PAD_T - (arm.screw_len - SCREW_KNOB_H - SCREW_THREAD) - 0.5],
        'clamp_reach_onto_desk_mm': TOP_JAW_L, 'thread_clearance_radial_mm': THREAD_CLR}
    report['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['export_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.st*'))}
    report['status'] = 'PASS'
    text = json.dumps(report, indent=2) + '\n'
    (OUT/'verification.json').write_text(text)
    (RESEARCH/'build-report.json').write_text(text)
    print('SOLDER_ARM_BUILD_PASS')


# FreeCADCmd imports scripts by stem, unlike CPython's __main__.
if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
