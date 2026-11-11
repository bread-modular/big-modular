"""FreeCAD generator for a modular, Moog-style tiered stand for 2 or 3 skiffs (mechanical/case/tools/build_case.py).

Run with FreeCAD's headless interpreter (see mechanical/case/tools/build_stand.sh):
  mechanical/case/tools/build_stand.sh                   # tilts 0 / 40 / 70 deg
  STAND_TILTS=0,35,65 mechanical/case/tools/build_stand.sh

Frame (all dimensions mm), the skiff assembly frame turned on its side:
  X  across the stand, same as the case X (X = 0 is the inner face of the left case side panel)
  Y  depth, front (user) -> back
  Z  up, Z = 0 is the table

Each side frame is a printed cheek in the Y/Z plane with a flat outer face: a 4 mm (T_WEB) web with
12 mm (T) bosses on the inner face where screws go (splice plate seats, stretcher ends), at the feet
and along each row (the guide wall, see below), made of one piece per tier:
  tier 1 = the base beside row 1, tier 2 bolts on behind it, tier 3 on top of that.
Row 1 lies flat (first tilt 0) on a thin ledge (TONGUE_1) at the foot of each tier 1 cheek, so its
weight goes into the stand (it loads the front feet against the rows above) instead of the desk.
Tier 2 carries a stop lug behind it and tier 1 a low one (FRONT_STOP) in front of it, so row 1
stays put with no bolts: it is lifted over the front lugs onto the ledges and out the same way.
  A 2-row stand is tier 1 + 2, a 3-row stand adds tier 3: the pieces do not change.
Every piece is the convex outline of its row (plus the foot for tier 1) minus the rows below it,
clipped RISE above each case's bottom plate underside (the cheeks only guide the case sides, they
do not reach up to the module faces), with lightening windows (RIM rims) wherever the web is not
needed. The pieces butt together and a 6 mm splice plate on the outer face bolts across each joint
with 4 M3x8 screws into M3x10 hex spacers superglued in the cheeks (the case's 5.7 AF x 10.2 blind
socket): along the butt edge where it is long, across it where it is short. Every joint takes the
same plate: the 1-2 plate keeps its pre-ledge place on the 43 mm edge, and an adapter plate (round
holes + slots) joins a tier 1 printed with the grown 1-2 plate to any tier 2.
The cases are held with no screws. Each row has a guide wall on both cheeks: a full-thickness (T)
band beside the case up to RISE, with a ledge (TONGUE thick, row 1 TONGUE_1) under the case bottom
plate along the whole case depth, both fused to a solid web band (no windows above TONGUE + RIM
under the plate). The band is full thickness only in a RAIL wide rail along its bottom (on the ledge) and top, in ribs
across it and over the step (the lip, RAIL tall); the bays between are pocketed from the inner face
down to the web. Row 1
sits on its thin ledges between low lugs on tier 1 in front of it and lugs on tier 2 behind it.
Rows 2+ slide in: the case bottom plate and its outer socket wall stand 3.15 mm past the side
panel outer face (13 mm tall), and a lip on top of each band covers that step, so the case can
only move along its rail, not lift off it (cable pulls). The lip starts at the lower (front) end
of the rail; a short lug there stops the step end; one lug per side, no bar across. A case drops
onto its ledges behind the lip and slides down under it onto the lugs; the row above has to come
out first. The top row's lip runs the whole case depth; a lower row's lip is only as long as its
case can slide up the rail clear of the stand and still lift off there (row 2: the row 3 lugs
and ledge are 41 mm behind its back end), sized in the build from the full stand so a 2-row
stand uses the same pieces. A stretcher on each tier that has room for one (not tier 1: row 1
fills it) ties the left and right cheeks. Each end sits in a U channel (box groove) on the cheek
inner face (3 mm walls, 3 mm proud), open on the side it slides in from, so it cannot turn or shift
once screwed: an M3x8 through a deep counterbore in the full-thickness channel floor (3 mm of cheek
under the head) into the spacer in each stretcher end.
The modules are held by 10 mm M3 male-female hex standoffs: the male end goes through the panel
into the rail spacer and the hex body stands 10 mm proud of the module face on both rail hole
lines. A row is placed so the lower row's back standoffs and the upper row's front standoffs are
SO_GAP apart (fingers / a 5.5 mm nut driver between them) and each is SO_CASE clear of the other
row's case + ledge.
The tier 3 cheeks only join the stand at their lower end (splice plates to tier 2), so their top ends
spring sideways. A top bar across the top ends ties them, pushed straight down the rails onto both
cheek ends with no change to the cheeks: each end is a cap over the cheek end (outer leg on the
outer face, a shoulder in the recess under the ledge against the web, a lip over the cheek top), and
a thin snap finger slides down between the cheek inner face and the case side panel, where a barb on
it clicks into the last guide wall pocket under the end rail. Its beam runs under the bottom plate
level, so row 3 slides in and out past it with the bar on. It comes off straight up (firm pull).
The stand stands on 12 x 12 mm self-adhesive (3M) rubber feet, each stuck on a flat full-thickness
plate (T x PAD) on the cheek underside: one under tier 1's front end and two under tier 2 (behind
row 1, rear foot). No screws or spacers in the feet.
Print set (mechanical/case/print/stand/, see its README.md): tier1/ tier2/ tier3/ hold each tier's two
cheeks, common/ the shared stretcher, splice plates and the 1-2 adapter plate.
"""

import json
import math
import os
import time
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = Path(os.environ.get("CASE_DIR", Path(__file__).resolve().parents[1]))
BED = 256.0

# --- the skiff, as built by build_case.py (42 HP, 60 mm side panels) ---------------
CASE_Y0, CASE_YLEN = -2.0, 132.5       # case front edge, depth
CASE_H = 65.0                          # bottom plate underside -> module fronts
PLATE_X0, PLATE_LEN = -15.15, 249.0    # bottom plate outer X extent
SIDE_T = 12.0

# --- fasteners (same as the case) ------------------------------------------------
M3_CLEAR, M3_CB_D, M3_CB_DEPTH = 3.4, 6.5, 3.2
SOCKET_AF, SOCKET_DEPTH = 5.7, 10.2
HEAD_D, HEAD_K = 5.5, 3.0              # M3 socket head (ISO 4762)

# --- stand -----------------------------------------------------------------------
T = 12.0             # cheek thickness (X) at the screw bosses (splice pads, stretcher ends), the feet and the rails:
                     # the 10.2 mm spacer socket + 1.5 mm floor and the 12 mm foot set it
T_WEB = 4.0          # cheek thickness everywhere else (rim, ribs, pocket floors): the bosses stand proud on the inner face
BOSS_MARGIN = 2.0    # splice pad reaches this far past the splice plate outline
# stretcher seat: a U channel (box groove) on the cheek inner face, STRETCH + 2 x STR_CLR wide, its
# walls RIM_W thick and RIM_H proud of the inner face, open on one side (the first of up / back /
# front with a clear path) so the stretcher slides into it between the built cheeks; the screw
# then pulls it onto the boss floor and the channel walls stop it turning or moving
STR_CLR = 0.25       # stretcher -> channel wall (each side)
RIM_W = 3.0          # channel wall thickness
RIM_H = 3.0          # channel walls stand this far proud of the cheek inner face
GAP_X = 1.0          # bottom plate edge -> cheek inner face (clears the rail screw heads)
TONGUE = 6.0         # ledge under the case bottom plate (Z in case frame), rows 2+
TONGUE_1 = 3.0       # row 1 ledge: at the foot of the tier 1 cheek, just thick enough to carry the case
TONGUE_IN = 8.0      # ledge reaches this far inboard past the side panel centre line
WEB = 18.0           # solid web band under each ledge (and the stretcher / lug margins)
BELOW = TONGUE + WEB  # cheek below the case bottom plate
RIM = 12.0           # rim / rib width round the lightening windows
WIN_MIN = 400.0      # smallest lightening window (mm2)
# the guide wall along each row is full thickness (T) only in rails: one along the ledge, one along
# its top or the lip, ribs across between them every RIB_PITCH; the bays between are pocketed from the inner face down to the T_WEB web (open side up: no bridges)
RAIL = 6.0           # full-thickness rail width (case frame Z) along the bottom and top of the wall
RIB = 5.0            # rib width across the wall
RIB_PITCH = 40.0     # rib spacing (at most)
POCKET_MIN = 10.0    # narrowest pocket worth cutting
RISE = 40.0          # cheek top over each case's bottom plate underside: guide wall beside the case, no higher
FOOT_H = 14.0        # rear foot height
# feet: a flat T x PAD plate on the cheek underside for a FOOT x FOOT self-adhesive (3M) rubber
# foot. Tier 1 has one at its front end, tier 2 one just behind row 1 and one at the rear foot.
FOOT = 12.0          # square 3M rubber foot
PAD = 16.0           # plate length (Y), 2 mm past the foot each end; its width is the cheek thickness T (= FOOT)
PAD_Z = 8.0          # full-thickness block over the plate (stiff under the foot)
PAD_END = 3.0        # plate edge to the cheek end
STOP = (10.0, 6.0, 30.0)  # stop lug at the lower end of each row (row 1: behind it): Y length, inboard of the case side panel outer face, Z height (case frame)
STOP_CLR = 0.5       # stop lug to the case end face in the model
FRONT_STOP = (8.0, 10.0)  # row 1 front lug on tier 1: Y length, top (case frame Z); the case lifts over it to go in / out
# tier 3 top bar (case frame of row 3; the tier 3 cheeks are not changed for it): the cheeks only join
# the stand at their lower end, so their top ends spring sideways. The bar is pushed down the rails
# onto the cheek top ends (case Y = CASE_Y0 + CASE_YLEN). Each end is a cap over the cheek end: the
# plate on the end face (down), the outer leg on the flat outer face (out), the shoulder in the
# recess under the ledge against the T_WEB web (in, and up the case Z under the ledge) and a lip over
# the cheek top (RISE, down the case Z). A snap finger hangs from that lip between the cheek inner
# face and the case side panel (over the lip); a barb on it rides over the end rail and clicks into
# the last guide wall pocket (up). The beam joins the two caps under the bottom plate level
# (BAR_BEAM_Z), so the cases slide along their rails past it.
BAR_W = 10.0         # bar thickness over the cheek top ends (case Y)
BAR_DOWN = 12.0      # outer leg, shoulder and top lip reach down the cheek from its top end (case Y)
BAR_LEG = 3.5        # outer leg thickness (X), outside the cheek outer face
BAR_CLR = 0.25       # bar to cheek, each side (X: outer leg, shoulder; Z: shoulder under the ledge)
BAR_TOP = 4.0        # bar top over the cheek top (RISE)
BAR_LIP_CLR = 0.3    # top lip over the cheek top (Z)
BAR_SH = 8.0         # shoulder reach inboard of the cheek inner face, under the ledge
BAR_BEAM_Z = -0.5    # beam top (case Z): under the bottom plate, the cases slide over it
BAR_SLIT = 0.8       # slit between the snap finger and the cap plate
FINGER_T = 2.0       # snap finger thickness (X); it bends along the case Z from its root in the top lip
FINGER_CLR = 0.3     # finger to the cheek inner face
FINGER_DOWN = 9.5    # finger reach down the cheek inner face from its top end: the end rail (RAIL) and the barb
BARB = 0.9           # barb past the finger face: BARB - FINGER_CLR overlap with the end rail
BARB_Z = (23.0, 30.5)    # barb span (case Z), inside the pocket's straight end wall (its corners are rounded)
BARB_IN, BARB_OUT = 30.0, 45.0   # lead-in (lower) / retention (upper) face angle from the case Y axis
BARB_LAND = 0.4      # flat barb tip (case Y)
BAR_UP = 0.35        # lift before the barb catches the end rail
# lip over the case's side step (rows 2+): the bottom plate and its outer socket wall stand
# PLATE_STEP past the side panel outer face up to STEP_Z; the lip covers that step so a case
# cannot lift off its rail, only slide along it
PLATE_STEP = -SIDE_T - PLATE_X0        # 3.15: plate edge past the side panel outer face
STEP_Z = 13.0                          # top of the step (5 mm plate + 8 mm socket wall)
LIP_CLR = 0.5        # step top -> lip underside (Z, case frame)
LIP_X_CLR = 0.75     # lip edge -> side panel outer face (X)
LIP_GAP = 1.0        # loading: case front end this far behind the lip end before it drops in
LIP_MIN = 20.0       # shortest lip worth having
STOP_UP = 6.0        # rows 2+ stop lug length (Y); its top is the step top (STEP_Z)
REAR_FOOT = 20.0     # rear foot reaches this far behind row 2
ROW_CLR = 6.0        # free space between neighbouring rows (case + ledge)
STANDOFF_H = 10.0    # M3 male-female hex standoff body above the module face (module fixing)
STANDOFF_AF = 5.5
SO_GAP = 15.0        # back standoffs of a row <-> front standoffs of the row above
SO_CASE = 12.0       # standoffs of a row <-> case + ledge of its neighbour
HOLE_Y = (3.0, 128.5 - 3.0)            # module rail hole lines (case Y)
CASE_X_IN = 218.7                      # case inner width (side panel to side panel)
SPLICE_T, SPLICE_W, SPLICE_L = 6.0, 34.0, 74.0
SPLICE_CB = M3_CB_DEPTH  # splice plate holes counterbored like the case bottom plate: M3x8 well into the spacer
SPLICE_MIN_EDGE = 36.0   # shorter butt edges get the splice plate across the joint instead of along it
SPLICE_X_L = 60.0        # cross splice: length across the joint (holes at +-9 and +-(L/2 - 8))
# 1-2 adapter plate: a tier 1 printed while the 1-2 plate grew with the 43 mm edge (TONGUE_1 longer)
# has its upper pair of spacers TONGUE_1 higher; the adapter has a round hole for each lower spacer and
# a TONGUE_1 slot for each upper one, so it joins any tier 1 to any tier 2 (left and right, one part)
SPLICE_ADAPTER = TONGUE_1
STRETCH = 20.0       # square stretcher section
STR_HW = STRETCH / 2 + STR_CLR          # channel half width
STR_BOX = STR_HW + RIM_W                # channel outer half width (= the full-thickness boss under it)
SCREW_L = 8.0        # the only M3 screw length used (M3x8 socket head): splices and stretcher ends
STRETCH_GRIP = 3.0   # cheek left under the stretcher screw head (the counterbore takes the rest of T)
STRETCH_CB = T - STRETCH_GRIP                      # 9: stretcher screw counterbore depth
STRETCH_ENGAGE = SCREW_L - STRETCH_GRIP - (SOCKET_DEPTH - 10.0)   # 4.8: thread into the spacer
SPLICE_ENGAGE = SCREW_L - (SPLICE_T - SPLICE_CB) - (SOCKET_DEPTH - 10.0)  # 5.0: thread into the spacer
ENGAGE_MIN = 4.0     # the case's rule: ~4 mm of thread in the spacer
SOCKET_WALL = 1.5    # printed wall round / under each spacer socket (checked)

X_IN = PLATE_X0 - GAP_X                 # left cheek inner face
X_IN_R = PLATE_X0 + PLATE_LEN + GAP_X    # right cheek inner face
BOLT_X = (-SIDE_T / 2, 218.7 + SIDE_T / 2)


# ---------------- 2D helpers (profile plane: u = Y, v = Z) ------------------------
def rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def add(p, q, k=1.0):
    return (p[0] + k * q[0], p[1] + k * q[1])


def hull(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def sat_gap(a, b):
    """Separation distance lower bound of two convex polygons (> 0: apart)."""
    best = -1e9
    for poly in (a, b):
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            n = (q[1] - p[1], p[0] - q[0])
            L = math.hypot(*n)
            n = (n[0] / L, n[1] / L)
            pa = [x * n[0] + y * n[1] for x, y in a]
            pb = [x * n[0] + y * n[1] for x, y in b]
            best = max(best, min(pb) - max(pa), min(pa) - max(pb))
    return best


def face2d(pts):
    return Part.Face(Part.makePolygon([V(x, y, 0) for x, y in pts] + [V(pts[0][0], pts[0][1], 0)]))


# profile plane (x=u=Y, y=v=Z, z=w) -> stand (X=w, Y=u, Z=v)
TO_STAND = App.Matrix(0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1)


def to_stand(shape, x0):
    s = shape.copy()
    s.transformShape(TO_STAND)
    s.translate(V(x0, 0, 0))
    return s


class Row:
    """One skiff, tilted by `a` about X; F = front-top edge (module face front) in (Y, Z)."""

    def __init__(self, a_deg, F):
        self.deg = a_deg
        self.a = math.radians(a_deg)
        self.F = F

    def pt(self, y, z):
        """case frame (Y, Z) -> profile plane"""
        return add(self.F, rot((y - CASE_Y0, z - CASE_H), self.a))

    def quad(self, y0, y1, z0, z1):
        """Case frame rectangle Y y0..y1, Z z0..z1 in the profile plane."""
        return [self.pt(y0, z0), self.pt(y1, z0), self.pt(y1, z1), self.pt(y0, z1)]

    def rect(self, below=0.0):
        return self.quad(CASE_Y0, CASE_Y0 + CASE_YLEN, -below, CASE_H)

    def standoff(self, i):
        """Outline of the standoff row on hole line i (0 front, 1 back) over the module face."""
        y0, y1 = HOLE_Y[i] - STANDOFF_AF / 2, HOLE_Y[i] + STANDOFF_AF / 2
        z0, z1 = CASE_H, CASE_H + STANDOFF_H
        return [self.pt(y0, z0), self.pt(y1, z0), self.pt(y1, z1), self.pt(y0, z1)]

    @property
    def B(self):
        return self.pt(CASE_Y0 + CASE_YLEN, CASE_H)

    @property
    def n(self):
        return rot((0, 1), self.a)

    def placement(self):
        m = App.Matrix()
        m.rotateX(self.a)
        p = App.Placement(m)
        o = self.pt(0, 0)
        return App.Placement(V(0, o[0], o[1]), p.Rotation)


def layout(tilts):
    rows = []
    for k, a in enumerate(tilts):
        if k == 0:
            # row 1 sits on its TONGUE_1 ledges at the foot of the tier 1 cheeks
            r = Row(a, (0.0, 0.0))
            lo = min(p[1] for p in r.rect(TONGUE_1))
            fy = min(p[0] for p in r.rect(TONGUE_1))
            r = Row(a, (-fy, -lo))
        else:
            prev = rows[-1]
            # slide the row back/up along the bisector of the two face directions until the
            # case + ledge outlines are ROW_CLR apart and the standoffs have hand room
            u = rot((1, 0), (prev.a + math.radians(a)) / 2)
            s = 0.0
            while True:
                r = Row(a, add(prev.B, u, s))
                if min(so_gaps(prev, r)) >= 0:
                    break
                s += 0.25
        rows.append(r)
    return rows


def tongue(k):
    """Ledge thickness under row k's bottom plate."""
    return TONGUE_1 if k == 0 else TONGUE


def so_gaps(lo, hi):
    """Margins (>= 0: ok) of the row clearances between a row and the row above it."""
    return (sat_gap(lo.rect(TONGUE), hi.rect(TONGUE)) - ROW_CLR,
            sat_gap(lo.standoff(1), hi.standoff(0)) - SO_GAP,
            sat_gap(lo.standoff(1), hi.rect(TONGUE)) - SO_CASE,
            sat_gap(hi.standoff(0), lo.rect(TONGUE)) - SO_CASE)


def clip_faces(rows):
    """Everything above the chain of RISE lines (RISE over each case's bottom plate underside): the
    cheeks only reach that far up the case sides."""
    chain = []
    for r in rows:
        chain += [r.pt(CASE_Y0, RISE), r.pt(CASE_Y0 + CASE_YLEN, RISE)]
    top = chain[-1]
    return face2d([add(chain[0], (-600, 0))] + chain + [add(top, rows[-1].n, 600), (chain[0][0] - 600, top[1] + 600)])


def union2d(faces):
    """Union of planar faces as faces with the internal edges gone (a 2D fuse keeps them)."""
    sol = faces[0].extrude(V(0, 0, 1))
    if len(faces) > 1:
        sol = sol.multiFuse([f.extrude(V(0, 0, 1)) for f in faces[1:]])
    sol = sol.removeSplitter()
    return Part.makeCompound([f for f in sol.Faces if abs(f.CenterOfMass.z) < 1e-6])


def biggest(face):
    fs = sorted(face.Faces, key=lambda f: -f.Area)
    return fs[0]


def rounded(f, r, min_area):
    """Faces of f with the corners rounded to r (anything thinner than 2 r goes), each >= min_area."""
    out = []
    for g in f.Faces:
        if g.Area < min_area:
            continue
        try:   # a thin face can vanish under the -r offset: skip it
            g = g.makeOffset2D(-r, 0).makeOffset2D(r, 0)
        except Exception:
            continue
        out += [h for h in g.Faces if h.Area >= min_area]
    return out


def windows(piece, keep):
    """Lightening windows RIM inside the piece outline, clear of the `keep` faces."""
    try:
        w = piece.makeOffset2D(-RIM, 0)
    except Exception:   # a piece narrower than two rims has none
        return []
    for k in keep:
        w = w.cut(k)
    return rounded(w, 5.0, WIN_MIN)


def hex_prism(c, depth, x0, sgn):
    """Hex socket for an M3 hex spacer, from the cheek outer face into it (axis X)."""
    r = SOCKET_AF / math.sqrt(3)
    pts = [V(0, c[0] + r * math.cos(math.radians(60 * i)), c[1] + r * math.sin(math.radians(60 * i))) for i in range(6)]
    w = Part.makePolygon(pts + [pts[0]])
    p = Part.Face(w).extrude(V(sgn * (depth + 0.01), 0, 0))
    p.translate(V(x0 - sgn * 0.01, 0, 0))
    return p


def cyl(r, h, base, axis):
    return Part.makeCylinder(r, h, V(*base), V(*axis))


def svg_profile(path, faces, rows, extra=(), pockets=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["#c9a46a", "#7a9cc6", "#9bc67a", "#c67a9b"]
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-40 -420 460 460" width="900">']
    for i, f in enumerate(faces):
        for w in f.Wires:
            pts = " ".join(f"{v.x:.1f},{-v.y:.1f}" for v in w.discretize(Deflection=0.5))
            out.append(f'<polygon points="{pts}" fill="{cols[i % 4]}" fill-opacity="0.6" stroke="black" stroke-width="0.5"/>')
    for f in pockets:
        for w in f.Wires:
            pts = " ".join(f"{v.x:.1f},{-v.y:.1f}" for v in w.discretize(Deflection=0.5))
            out.append(f'<polygon points="{pts}" fill="#555" fill-opacity="0.5" stroke="black" stroke-width="0.3"/>')
    for r in rows:
        pts = " ".join(f"{x:.1f},{-y:.1f}" for x, y in r.rect())
        out.append(f'<polygon points="{pts}" fill="none" stroke="red" stroke-width="0.8"/>')
    for x, y in extra:
        out.append(f'<circle cx="{x:.1f}" cy="{-y:.1f}" r="3" fill="black"/>')
    out.append('<line x1="-40" y1="0" x2="420" y2="0" stroke="gray"/></svg>')
    path.write_text("\n".join(out))


def main():
    tilts = [float(t) for t in os.environ.get("STAND_TILTS", "0,40,70").split(",")]
    tiers = int(os.environ.get("STAND_TIERS", len(tilts)))
    t0 = time.time()
    rows = layout(tilts)

    # tier 1 stands on the desk beside row 1 and carries it on its ledges; tier 2 has a rear foot under
    # row 2 (it carries the rows above, so the stand cannot tip back); tier 3 sits on tier 2 only
    r1 = rows[0].rect(TONGUE_1)
    y_front, y_mid = min(p[0] for p in r1), max(p[0] for p in r1)
    foot = [(y_front, 0), (y_mid, 0), (y_mid, FOOT_H), (y_front, FOOT_H)]
    y_back = max(p[0] for p in rows[1].rect(BELOW)) + REAR_FOOT
    rear = [(y_back - 60, 0), (y_back, 0), (y_back, FOOT_H), (y_back - 60, FOOT_H)]

    # the stop lugs (profile plane), each on the piece that carries its row: row 1 stops on tier 2
    # behind it and on a low lug on tier 1 in front of it, rows 2+ on their own tier at the lower
    # (front) end of the rail
    # rows 2+: a short lug at the lower end of the lip channel stops the plate + socket wall end
    # only (inboard to the lip edge, up to the step top), so the row below slides as far up its
    # rail as it can under it on its way in
    def stop2d(k):
        if k == 0:
            ys = max(p[0] for p in r1) + STOP_CLR
            return [(ys, 0), (ys + STOP[0], 0), (ys + STOP[0], STOP[2]), (ys, STOP[2])]
        y1 = CASE_Y0 - STOP_CLR
        return rows[k].quad(y1 - STOP_UP, y1, -BELOW, STEP_Z)
    stops = {1 if k == 0 else k: [] for k in range(len(rows))}
    for k in range(len(rows)):
        stops[1 if k == 0 else k].append((k, stop2d(k)))
    # row 1 front lug: on tier 1 in front of the case, as far inboard as the back lugs; the case
    # front end is lifted over it. front_root ties it to the cheek front end (the guide wall up to
    # the cheek inner face, the ledge under the plate) across the STOP_CLR gap
    yf = CASE_Y0 - STOP_CLR
    stops[0] = [(0, rows[0].quad(yf - FRONT_STOP[0], yf, -TONGUE_1, FRONT_STOP[1]))]
    front_root = rows[0].quad(yf - FRONT_STOP[0], CASE_Y0 + 1, -TONGUE_1, FRONT_STOP[1])

    clip = clip_faces(rows)
    desk = face2d([(-600, 0), (900, 0), (900, -600), (-600, -600)])
    outlines = []
    for k in range(len(rows)):
        if k == 0:
            pts = foot + r1
        else:
            pts = rows[k - 1].rect(TONGUE_1 if k == 1 else BELOW) + rows[k].rect(BELOW) + (rear if k == 1 else [])
        o = face2d(hull(pts)).cut(clip)
        extra = [face2d(front_root)] if k == 0 else []
        outlines.append(union2d(o.Faces + extra + [face2d(st) for _, st in stops.get(k, [])]).cut(desk))
    solid2d = []
    for k in range(len(rows)):
        p = outlines[k]
        for q in outlines[:k]:
            p = p.cut(q)
        solid2d.append(biggest(p))
    for k, sts in stops.items():
        for _, st in sts:
            f = face2d(st).cut(desk)
            assert abs(f.common(solid2d[k]).Area - f.Area) < 1e-3, \
                f"stop lug of piece {k} is cut by another piece: {f.Area:.1f} {f.common(solid2d[k]).Area:.1f} {[round(f.common(o).Area, 1) for o in solid2d]} {st}"
    pieces2d = solid2d
    svg_profile(CASE / "research" / "stand" / "profile.svg", solid2d, rows)

    # joints: longest shared edge between neighbouring pieces -> splice plate. A long edge takes the
    # plate along it (2 + 2 holes beside the edge); a short one (tier 1 is only RISE tall) across it
    # (2 + 2 holes in a line across the edge). The plate is given in its own frame (a along the edge,
    # b across it) so the print set holds one part per plate size.
    joints = []
    for k in range(1, len(rows)):
        sec = pieces2d[k].section(pieces2d[k - 1])
        e = max(sec.Edges, key=lambda e: e.Length)
        a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
        if a.y > b.y:
            a, b = b, a
        d = ((b.x - a.x) / e.Length, (b.y - a.y) / e.Length)
        # the 1-2 edge grew TONGUE_1 at its top with the row 1 ledge; its plate keeps the size and
        # holes it had before (TONGUE_1 / 2 below the edge middle), so every joint takes the one
        # splice plate and tier 2 printed before the ledge still fits (SPLICE_ADAPTER: a tier 1
        # printed with the plate grown to the 43 mm edge)
        seat = e.Length - (TONGUE_1 if k == 1 else 0)
        mid = add(((a.x + b.x) / 2, (a.y + b.y) / 2), d, -(e.Length - seat) / 2)
        joints.append({"tiers": (k, k + 1), "edge": (mid, d, (-d[1], d[0])), "edge_mm": round(e.Length, 1),
                       "seat_mm": round(seat, 1)})
    long_edges = [j["seat_mm"] for j in joints if j["edge_mm"] >= SPLICE_MIN_EDGE]
    L = min([SPLICE_L] + [m - 8 for m in long_edges])
    W = min([SPLICE_W] + [j["edge_mm"] - 2 for j in joints if j["edge_mm"] < SPLICE_MIN_EDGE])
    for j in joints:
        mid, d, nrm = j.pop("edge")
        if j["edge_mm"] >= SPLICE_MIN_EDGE:
            half = (L / 2, SPLICE_W / 2)
            local = [(s * (L / 2 - 9), t * (WEB / 2 - 0.5)) for s in (-1, 1) for t in (-1, 1)]
        else:
            half = (W / 2, SPLICE_X_L / 2)
            local = [(0, t * u) for t in (-1, 1) for u in (9, SPLICE_X_L / 2 - 8)]
        to2d = lambda ab: add(add(mid, d, ab[0]), nrm, ab[1])
        corners = [to2d((s * half[0], t * half[1])) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        j.update(holes=[to2d(h) for h in local], plate=corners, half=half, local=local, frame=(mid, d, nrm))

    # the 1-2 adapter plate (plate frame of the 1-2 joint, a along the edge, up): round holes on the
    # lower pair, SPLICE_ADAPTER slots from the upper pair up, the plate SPLICE_ADAPTER longer at the top
    j12 = joints[0]
    assert j12["edge_mm"] >= SPLICE_MIN_EDGE, "1-2 adapter: the 1-2 joint takes a plate along its edge"
    ha, hb = j12["half"]
    a_lo, a_hi = -(ha - 9), ha - 9
    adapter = {"span": (-ha, ha + SPLICE_ADAPTER), "hb": hb,
               "holes": [(a_lo, b) for b in (-(WEB / 2 - 0.5), WEB / 2 - 0.5)],
               "slots": [((a_hi, b), (a_hi + SPLICE_ADAPTER, b)) for b in (-(WEB / 2 - 0.5), WEB / 2 - 0.5)]}
    assert sorted(adapter["holes"] + [sl[0] for sl in adapter["slots"]]) == sorted(j12["local"]), \
        "1-2 adapter: round holes + slot ends != the splice plate holes"
    # it stays on the outer face of the pieces and under the pre-ledge 40 mm edge top (tier 2 printed then)
    mid12, d12, nrm12 = j12["frame"]
    f_ad = face2d([add(add(mid12, d12, a), nrm12, b) for a, b in
                   ((adapter["span"][0], -hb), (adapter["span"][1], -hb), (adapter["span"][1], hb), (adapter["span"][0], hb))])
    both = pieces2d[0].fuse(pieces2d[1])
    assert abs(f_ad.common(both).Area - f_ad.Area) < 1e-3, "1-2 adapter off the tier 1 + 2 outer faces"
    top_gap = j12["seat_mm"] / 2 - adapter["span"][1]
    assert top_gap >= 1.0 - 1e-6, f"1-2 adapter top {top_gap:.2f} mm under the pre-ledge edge top"
    adapter["top_gap_mm"] = round(top_gap, 2)

    # feet: plate centres (profile Y) on the desk edge of tiers 1 and 2
    def pad2d(y):
        return [(y - PAD / 2, 0), (y + PAD / 2, 0), (y + PAD / 2, PAD_Z), (y - PAD / 2, PAD_Z)]

    assert T >= FOOT, f"cheek {T} mm narrower than the {FOOT} mm foot"
    feet = {0: [y_front + PAD_END + PAD / 2], 1: [y_mid + PAD_END + PAD / 2, y_back - PAD_END - PAD / 2]}
    for k, ys in feet.items():
        for y in ys:
            f = face2d(pad2d(y))
            assert abs(f.common(solid2d[k]).Area - f.Area) < 1e-3, f"tier {k + 1}: foot pad at Y {y:.1f} off the piece"

    # the case guide rails (row frame Y along the case, Z -ledge .. RISE)
    def rail2d(k):
        return face2d(rows[k].quad(CASE_Y0, CASE_Y0 + CASE_YLEN, -tongue(k), RISE))

    # stretchers: one per tier, as far back as the piece allows, its channel clear of every case outline
    def sq2d(c, h):
        return [(c[0] - h, c[1] - h), (c[0] + h, c[1] - h), (c[0] + h, c[1] + h), (c[0] - h, c[1] + h)]
    stretchers = []
    for k, p in enumerate(solid2d):
        bb = p.BoundBox
        try:
            pin = p.makeOffset2D(-WEB / 2, 0)
        except Exception:
            stretchers.append(None)
            continue
        best = None
        y = bb.XMin
        while y < bb.XMax:
            z = bb.YMin
            while z < bb.YMax:
                sq = sq2d((y, z), STR_BOX)
                fsq = face2d(sq)
                if abs(fsq.common(pin).Area - fsq.Area) < 1e-3 and all(sat_gap(sq, r.rect(TONGUE)) > 2 for r in rows) \
                        and all(not any(abs(h[0] - y) < 20 and abs(h[1] - z) < 20 for h in j["holes"]) for j in joints):
                    score = y + (0.3 * z if k == 0 else 0.6 * z)
                    if best is None or score > best[0]:
                        best = (score, (y, z))
                z += 4
            y += 4
        # tier 3 is a thin cheek: its row ties the two sides
        stretchers.append(best[1] if best else None)

    # the side each stretcher channel opens to: the first of up / back / front (profile plane) along
    # which the stretcher slides out between the cheeks clear of everything standing proud of their
    # inner faces (ledges, lips, stop lugs: the rail quads, rows 2+ from the ledge up; the row 1
    # lugs) and of the desk. Checked again in 3D against the built stand (checks.stretchers).
    obst = [rows[k].quad(CASE_Y0 - STOP_UP - 1, CASE_Y0 + CASE_YLEN, -TONGUE, RISE) for k in range(1, len(rows))]
    obst += [st for k, sts in stops.items() for _, st in sts]
    obst.append([(-600, -600), (900, -600), (900, 0), (-600, 0)])
    str_open = []
    for k, c in enumerate(stretchers):
        if not c:
            str_open.append(None)
            continue
        sq = sq2d(c, STRETCH / 2)
        for d in ((0, 1), (1, 0), (-1, 0)):
            sweep = hull(sq + [add(p, d, 400) for p in sq])
            if all(sat_gap(sweep, o) > 0.5 for o in obst):
                str_open.append(d)
                break
        else:
            raise AssertionError(f"tier {k + 1}: no free side to slide the stretcher in")

    def channel2d(k):
        """The U channel round stretcher k's end (profile plane), open towards str_open[k]."""
        c, d = stretchers[k], str_open[k]
        slot = sq2d(c, STR_HW)
        slot = hull(slot + [add(p, d, STR_BOX + 2) for p in slot])
        return face2d(sq2d(c, STR_BOX)).cut(face2d(slot))

    # lightening windows, keeping solid: the web under each rail down to TONGUE + RIM (the ledge and the
    # guide band sit on solid web along their whole length), the stop lugs, the splice seats and a
    # boss round each stretcher end
    pieces2d = []
    for k, p in enumerate(solid2d):
        keep = [face2d(rows[k].quad(CASE_Y0 - STOP[0] - 20, CASE_Y0 + CASE_YLEN + RIM, -(TONGUE + RIM), CASE_H + 50))]
        keep += [face2d(st).makeOffset2D(WEB / 2, 2) for _, st in stops.get(k, [])]
        keep += [face2d(j["plate"]).makeOffset2D(BOSS_MARGIN + 2, 2) for j in joints if k + 1 in j["tiers"]]
        keep += [face2d(pad2d(y)).makeOffset2D(WEB / 2, 2) for y in feet.get(k, [])]
        if stretchers[k]:
            keep.append(face2d(sq2d(stretchers[k], STR_BOX)).makeOffset2D(WEB / 2, 2))
        for w in windows(p, keep):
            p = p.cut(w)
        pieces2d.append(biggest(p))

    # what the guide wall pockets stay clear of: the splice seats, feet, stretcher boss, stop lugs
    def solid_keep(k):
        out = [face2d(j["plate"]).makeOffset2D(BOSS_MARGIN + 2, 2) for j in joints if k + 1 in j["tiers"]]
        out += [face2d(pad2d(y)).makeOffset2D(RAIL / 2, 2) for y in feet.get(k, [])]
        out += [face2d(st).makeOffset2D(RAIL / 2, 2) for _, st in stops.get(k, [])]
        if stretchers[k]:
            out.append(face2d(sq2d(stretchers[k], STR_BOX)).makeOffset2D(RAIL / 2, 2))
        return out

    def pockets(k, lip_len):
        """Bays of row k's guide wall pocketed down to the web (profile plane faces): between the
        bottom rail (on the ledge) and the top rail, between ribs, above the lip where
        there is one (it is RAIL tall over the step), clear of the solid_keep parts."""
        y_end = CASE_Y0 + CASE_YLEN - RAIL
        z_lip = STEP_Z + LIP_CLR + RAIL
        zones = [(CASE_Y0 + RAIL, min(CASE_Y0 + lip_len, y_end), z_lip)] if lip_len > 0 else []
        if lip_len < CASE_YLEN:
            zones.append((CASE_Y0 + (lip_len + RIB if lip_len > 0 else RAIL), y_end, RAIL))
        z1 = RISE - RAIL
        out = []
        for y0, y1, z0 in zones:
            if y1 - y0 < POCKET_MIN or z1 - z0 < POCKET_MIN:
                continue
            n = math.ceil((y1 - y0 + RIB) / RIB_PITCH)
            b = (y1 - y0 - (n - 1) * RIB) / n
            for i in range(n):
                ya = y0 + i * (b + RIB)
                f = face2d(rows[k].quad(ya, ya + b, z0, z1)).common(pieces2d[k])
                for q in solid_keep(k):
                    f = f.cut(q)
                out += rounded(f, POCKET_MIN / 2 - 0.5, POCKET_MIN ** 2)
        return out

    def bosses(k, lip_len=0.0):
        """2D full-thickness pads of piece k: the splice plate seat at each joint, the floor of the
        stretcher channel, the case guide wall (rails and ribs round the pockets), the feet."""
        out = []
        for j in joints:
            if k + 1 in j["tiers"]:
                f = face2d(j["plate"]).makeOffset2D(-2, 0).makeOffset2D(2 + BOSS_MARGIN, 2)
                out += f.common(pieces2d[k]).Faces
        if stretchers[k]:
            out += face2d(sq2d(stretchers[k], STR_BOX)).common(pieces2d[k]).Faces
        wall = rail2d(k).common(pieces2d[k])
        for f in pockets(k, lip_len):
            wall = wall.cut(f)
        out += wall.Faces
        for y in feet.get(k, []):
            out += face2d(pad2d(y)).common(pieces2d[k]).Faces
        return [f for f in out if f.Area > 1]

    if os.environ.get("STAND_2D"):
        # quick look at the profiles: windows, and the wall pockets with no lips
        svg_profile(CASE / "research" / "stand" / "profile-cut.svg", pieces2d, rows,
                    pockets=[f for k in range(len(rows)) for f in pockets(k, 0.0)])
        return

    def lip_x(left):
        """Lip edge (and rows 2+ stop lug inner face): LIP_X_CLR off the side panel outer face."""
        return -SIDE_T - LIP_X_CLR if left else CASE_X_IN + SIDE_T + LIP_X_CLR

    def cheek(k, left, lip_len):
        sgn = 1 if left else -1      # outward is -X on the left
        x_in = X_IN if left else X_IN_R
        x_out = x_in - sgn * T
        # thin web flush with the flat outer face (the splice plates sit on it); full-thickness bosses
        # where screws / spacers go and along the case guide rail, standing proud on the inner face
        # with the ledge and the stop lugs, so the piece still prints outer face down with no supports
        x_web = x_out + sgn * T_WEB
        s = to_stand(pieces2d[k].extrude(V(0, 0, T_WEB)), min(x_out, x_web))
        x_b = x_web - sgn * 1.0      # bosses start 1 mm inside the web (no coplanar faces to fuse)

        def solid(f, x1):
            """2D profile f (clipped to the piece) standing from the web up to X = x1."""
            f = f.common(pieces2d[k])
            assert f.Area > 1
            return to_stand(f.extrude(V(0, 0, abs(x1 - x_b))), min(x1, x_b))
        bs = [solid(b, x_in) for b in bosses(k, lip_len)]
        # ledge under the bottom plate along the whole case depth, inboard past the side panel centre
        # (row 1: the thin TONGUE_1 ledge at the foot of the cheek)
        tx1 = BOLT_X[0] + TONGUE_IN if left else BOLT_X[1] - TONGUE_IN
        bs.append(solid(face2d(rows[k].quad(CASE_Y0, CASE_Y0 + CASE_YLEN, -tongue(k), 0)), tx1))
        if k > 0:
            # lip over the plate step from the lower (front) end of the rail, lip_len along it, RAIL
            # tall (the guide wall above it is pocketed like the rest)
            if lip_len > 0:
                z = STEP_Z + LIP_CLR
                bs.append(solid(face2d(rows[k].quad(CASE_Y0, CASE_Y0 + lip_len, z, z + RAIL)), lip_x(left)))
        # stop lugs: row 1 against the outer part of the case side panel end (plate, socket wall,
        # side panel); rows 2+ against the plate step end only, flush with the lip
        if stretchers[k]:
            # stretcher channel walls, proud of the inner face
            bs.append(solid(channel2d(k), x_in + sgn * RIM_H))
        sx = (-SIDE_T + STOP[1]) if left else (CASE_X_IN + SIDE_T - STOP[1])
        bs += [solid(face2d(st).cut(desk), sx if r == 0 else lip_x(left)) for r, st in stops.get(k, [])]
        if k == 0:
            # row 1 front lug root: full thickness to the cheek inner face, and to the lug under the plate
            bs.append(solid(face2d(front_root), x_in))
            y0 = front_root[0][0]
            bs.append(solid(face2d(rows[0].quad(y0, CASE_Y0 + 1, -TONGUE_1, 0)), sx))
        s = s.multiFuse(bs).removeSplitter()
        cuts = []
        socks = []
        for j in joints:
            if k + 1 in j["tiers"]:
                for h in j["holes"]:
                    # sockets only under this piece's half of the splice
                    if face2d([add(h, (-1, -1)), add(h, (1, -1)), add(h, (1, 1)), add(h, (-1, 1))]).common(pieces2d[k]).Area > 1:
                        cuts.append(hex_prism(h, SOCKET_DEPTH, x_out, sgn))
                        socks.append((f"splice-{j['tiers'][0]}{j['tiers'][1]}", h, x_out, sgn))
                        cuts.append(cyl(1.2, T + 2, (x_out - sgn, h[0], h[1]), (sgn, 0, 0)))  # glue vent
        if stretchers[k]:
            y, z = stretchers[k]
            cuts.append(cyl(M3_CLEAR / 2, T + 2, (x_out - sgn, y, z), (sgn, 0, 0)))
            cuts.append(cyl(M3_CB_D / 2, STRETCH_CB + 1, (x_out - sgn, y, z), (sgn, 0, 0)))  # M3x8 reaches the spacer
        precut[f"tier{k + 1}-{'left' if left else 'right'}"] = (s, socks)
        for c in cuts:
            s = s.cut(c)
        return s.removeSplitter()

    def splice(j, left):
        sgn = 1 if left else -1
        x_out = (X_IN - T) if left else (X_IN_R + T)
        f = face2d(j["plate"])
        f = f.makeOffset2D(-4, 0).makeOffset2D(4, 2)
        s = to_stand(f.extrude(V(0, 0, SPLICE_T)), x_out - SPLICE_T if left else x_out)
        for h in j["holes"]:
            s = s.cut(cyl(M3_CLEAR / 2, SPLICE_T + 2, (x_out - sgn * (SPLICE_T + 1), h[0], h[1]), (sgn, 0, 0)))
            s = s.cut(cyl(M3_CB_D / 2, SPLICE_CB + 1, (x_out - sgn * (SPLICE_T + 1), h[0], h[1]), (sgn, 0, 0)))
        return s

    def stretcher(k):
        y, z = stretchers[k]
        L = X_IN_R - X_IN
        s = Part.makeBox(L, STRETCH, STRETCH, V(X_IN, y - STRETCH / 2, z - STRETCH / 2))
        precut[f"stretcher-{k + 1}"] = (s, [("stretcher", (y, z), xe, sg) for xe, sg in ((X_IN, 1), (X_IN_R, -1))])
        for xe, sg in ((X_IN, 1), (X_IN_R, -1)):
            s = s.cut(hex_prism((y, z), SOCKET_DEPTH, xe, sg))
        return s

    # every tier of the full stand is built (a 2-row stand uses the same tier 1 + 2 pieces as the
    # 3-row one), with no lips first: they are sized below from the free loading paths
    lip_len = {k: 0.0 for k in range(1, len(rows))}
    asm = {}
    precut = {}   # part -> (solid before the screw cuts, its spacer sockets), for the fastener check
    for k in range(len(rows)):
        for left in (True, False):
            asm[f"tier{k + 1}-{'left' if left else 'right'}"] = cheek(k, left, lip_len.get(k, 0))
        if stretchers[k]:
            asm[f"stretcher-{k + 1}"] = stretcher(k)
    for j in joints:
        for left in (True, False):
            asm[f"splice-{j['tiers'][0]}{j['tiers'][1]}-{'left' if left else 'right'}"] = splice(j, left)

    # the skiffs, from the case build, with the screw heads the stand has to clear: an M3 socket head
    # (ISO 4762, 5.5 x 3) in each bottom plate counterbore and on each rail screw outside the side panels
    case_parts = Part.read(str(CASE / "print" / "assembly-preview.step"))
    assert len(case_parts.Solids) == 5, "case: bottom plate, 2 side panels, 2 rails"
    heads = []
    for f in case_parts.Faces:
        c, b = f.Surface, f.BoundBox
        if not isinstance(c, Part.Cylinder):
            continue
        if abs(c.Radius - M3_CB_D / 2) < 1e-3 and abs(c.Axis.z) > 0.99:
            heads.append(cyl(HEAD_D / 2, HEAD_K, (b.Center.x, b.Center.y, b.ZMax - HEAD_K), (0, 0, 1)))
        elif abs(c.Radius - M3_CLEAR / 2) < 1e-3 and abs(c.Axis.x) > 0.99 and b.XMin < -SIDE_T + 1e-3:
            heads.append(cyl(HEAD_D / 2, HEAD_K, (-SIDE_T, b.Center.y, b.Center.z), (-1, 0, 0)))
        elif abs(c.Radius - M3_CLEAR / 2) < 1e-3 and abs(c.Axis.x) > 0.99 and b.XMax > CASE_X_IN + SIDE_T - 1e-3:
            heads.append(cyl(HEAD_D / 2, HEAD_K, (CASE_X_IN + SIDE_T, b.Center.y, b.Center.z), (1, 0, 0)))
    uniq = {}
    for h in heads:
        uniq.setdefault(tuple(round(v, 1) for v in h.BoundBox.Center), h)
    heads = list(uniq.values())
    assert len(heads) == 12, f"case screw heads: {len(heads)} (8 bottom plate + 4 rail)"
    case_parts = Part.makeCompound(case_parts.Solids + heads)
    case_at = []
    for k in range(len(rows)):
        c = case_parts.copy()
        c.Placement = rows[k].placement().multiply(c.Placement)
        case_at.append(c)

    # loading rows 2+: the case drops onto its ledges behind the lip (along its face normal), then
    # slides down the rail under the lip onto the stop lugs (lift the row above out first). The lip
    # can only be as long as the case slides up its rail clear of the stand and still lifts off
    # there (the row above's lugs lean over row 2's back end), less LIP_GAP; the top row's lip runs
    # the full depth.
    def hit_vol(shape, near):
        return max([0.0] + [shape.common(o).Volume for o in near])

    def nearby(shape, d, dist):
        bb = shape.BoundBox
        bb2 = shape.translated(d * dist).BoundBox
        bb.add(bb2)
        bb.enlarge(1)
        return [o for o in asm.values() if o.BoundBox.intersect(bb)]

    def free_slide(shape, d, dist, step=2.0):
        """Free travel of shape along unit d (up to dist): 0.05 mm resolution."""
        near = nearby(shape, d, dist)
        t = 0.0
        while t < dist:
            t1 = min(dist, t + step)
            if hit_vol(shape.translated(d * t1), near) > 1e-3:
                lo, hi = t, t1
                while hi - lo > 0.05:
                    m = (lo + hi) / 2
                    lo, hi = (lo, m) if hit_vol(shape.translated(d * m), near) > 1e-3 else (m, hi)
                return lo
            t = t1
        return None

    # lifted off: clear of its own guide walls (RISE + 2 up the face normal), then out to the front
    # (-Y). Sized from the top row down, so a lower row sees the lips of the rows above it.
    def lifts_out(c, nrm):
        return free_slide(c, nrm, RISE + 2) is None and \
            free_slide(c.translated(nrm * (RISE + 2)), V(0, -1, 0), 250) is None

    slide_free = {}
    for k in reversed(range(1, len(rows))):
        up = rows[k].placement().Rotation.multVec(V(0, 1, 0))
        nrm = V(0, rows[k].n[0], rows[k].n[1])
        s = free_slide(case_at[k], up, CASE_YLEN + LIP_GAP + 2)
        slide_free[k] = s
        if s is not None:
            lifts = lambda t: lifts_out(case_at[k].translated(up * t), nrm)
            lo, hi = int(LIP_MIN + LIP_GAP), math.floor(s - 1.0)
            assert lifts(lo), f"row {k + 1}: no loading position for a {LIP_MIN} mm lip"
            while lo < hi:
                m = (lo + hi + 1) // 2
                lo, hi = (m, hi) if lifts(m) else (lo, m - 1)
            lip_len[k] = lo - LIP_GAP
        else:
            lip_len[k] = CASE_YLEN
        for left in (True, False):
            asm[f"tier{k + 1}-{'left' if left else 'right'}"] = cheek(k, left, lip_len[k])

    def top_bar(barbs=True):
        """Top bar over the top tier's cheek ends (row case frame): the left half as boxes (cap plate, outer
        leg, top lip, shoulder, beam, snap finger + barb), mirrored to the right end."""
        def box(x0, x1, y0, y1, z0, z1):
            return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
        cx = CASE_X_IN / 2
        y_top, z_bot = CASE_Y0 + CASE_YLEN, -BELOW
        yb, y_low, z_top = y_top + BAR_W, y_top - BAR_DOWN, RISE + BAR_TOP
        xo = X_IN - T
        xl = xo - BAR_CLR - BAR_LEG
        xf = X_IN + FINGER_CLR
        z_f = STEP_Z + LIP_CLR + RAIL + FINGER_CLR   # finger bottom: over the lip
        half = [box(xl, xf - BAR_SLIT, y_top, yb, z_bot, z_top),                                   # cap plate
                box(xl, xo - BAR_CLR, y_low, yb, z_bot, z_top),                                     # outer leg
                box(xl, xf + FINGER_T, y_low, yb, RISE + BAR_LIP_CLR, z_top),                       # top lip
                box(xo + T_WEB + BAR_CLR, X_IN + BAR_SH, y_low, yb, z_bot, -TONGUE - BAR_CLR),      # shoulder
                box(xf - BAR_SLIT - 0.01, cx + 1, y_top, yb, z_bot, BAR_BEAM_Z),                   # beam
                box(xf, xf + FINGER_T, y_top - FINGER_DOWN, yb, z_f, RISE + BAR_LIP_CLR + 0.01)]  # finger
        if barbs:
            b = face2d(barb_pts(xf)).extrude(V(0, 0, BARB_Z[1] - BARB_Z[0]))
            half.append(b.translated(V(0, 0, BARB_Z[0])))
        h = half[0].multiFuse(half[1:]).removeSplitter()
        return h.fuse(h.mirror(V(cx, 0, 0), V(1, 0, 0))).removeSplitter()

    def barb_pts(xf):
        """Barb on the finger (X, case Y): retention face up, BAR_UP under the end rail's pocket edge."""
        y_end = CASE_Y0 + CASE_YLEN - RAIL
        y1 = y_end - BAR_UP + FINGER_CLR / math.tan(math.radians(BARB_OUT))
        y2 = y1 - BARB / math.tan(math.radians(BARB_OUT))
        y3 = y2 - BARB_LAND
        y4 = y3 - BARB / math.tan(math.radians(BARB_IN))
        return [(xf + 0.01, y1), (xf - BARB, y2), (xf - BARB, y3), (xf + 0.01, y4)]

    # the bar goes in after the lips are sized, so the cheeks do not change for it
    kb = len(rows) - 1
    bar_name = f"topbar-{kb + 1}"
    bar_case = top_bar()
    bar_nb = top_bar(barbs=False)
    for b in (bar_case, bar_nb):
        assert b.isValid() and len(b.Solids) == 1
    asm[bar_name] = bar_case.copy()
    asm[bar_name].Placement = rows[kb].placement().multiply(asm[bar_name].Placement)
    built = {f"tier{k + 1}-" for k in range(tiers)} | {f"stretcher-{k + 1}" for k in range(tiers)} | \
        {f"splice-{j['tiers'][0]}{j['tiers'][1]}-" for j in joints if j["tiers"][1] <= tiers} | \
        ({bar_name} if kb < tiers else set())
    full_stand = dict(asm)
    asm = {n: s for n, s in asm.items() if any(n.startswith(b) for b in built)}
    cases = {f"case-{k + 1}": case_at[k] for k in range(tiers)}

    # the module standoffs (hex bodies over the face), every 4 HP along both hole lines
    rs = STANDOFF_AF / math.sqrt(3)
    hexf = Part.Face(Part.makePolygon([V(rs * math.cos(math.radians(60 * i)), rs * math.sin(math.radians(60 * i)), 0)
                                       for i in range(7)]))
    xs = [12.58 + 20.32 * i for i in range(11) if 12.58 + 20.32 * i < CASE_X_IN - 6]
    so = [hexf.extrude(V(0, 0, STANDOFF_H)).translated(V(x, y, CASE_H)) for x in xs for y in HOLE_Y]
    for k in range(tiers):
        c = Part.makeCompound(so)
        c.Placement = rows[k].placement().multiply(c.Placement)
        cases[f"standoffs-{k + 1}"] = c

    # checks: nothing in the stand collides with a case, nothing in the stand with itself
    report = {"tilts_deg": tilts[:tiers], "tiers": tiers, "build_s": None, "checks": {}}
    clash = {}
    for cn, c in cases.items():
        for n, s in asm.items():
            v = s.common(c).Volume
            if v > 1e-2:
                clash[f"{n}/{cn}"] = round(v, 2)
    names = list(asm)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = asm[a].common(asm[b]).Volume
            if v > 1e-2:
                clash[f"{a}/{b}"] = round(v, 2)
    report["checks"]["clashes_mm3"] = clash
    report["checks"]["row_clearance_mm"] = [round(sat_gap(rows[k].rect(TONGUE), rows[k + 1].rect(TONGUE)), 1)
                                           for k in range(tiers - 1)]
    # lower row back standoffs <-> upper row front standoffs, and standoffs <-> the other case
    report["checks"]["standoff_to_standoff_mm"] = [
        round(sat_gap(rows[k].standoff(1), rows[k + 1].standoff(0)), 1) for k in range(tiers - 1)]
    report["checks"]["standoff_to_case_mm"] = [
        round(min(sat_gap(rows[k].standoff(1), rows[k + 1].rect(TONGUE)),
                  sat_gap(rows[k + 1].standoff(0), rows[k].rect(TONGUE))), 1) for k in range(tiers - 1)]
    for k in range(tiers - 1):
        for n in (f"case-{k + 1}", f"case-{k + 2}"):
            v = cases[f"standoffs-{k + 2 if n.endswith(str(k + 1)) else k + 1}"].common(cases[n]).Volume
            if v > 1e-2:
                clash[f"standoffs/{n}"] = round(v, 2)
    # rough tipping check: every case 1.5 kg at its outline centre, the stand ~ 0
    com_y = sum(sum(p[0] for p in r.rect()) / 4 for r in rows[:tiers]) / tiers
    report["checks"]["centre_of_mass_y_mm"] = round(com_y, 1)
    # on the rubber feet: the front and rear pad centres
    report["checks"]["foot_y_mm"] = [round(feet[0][0], 1), round(feet[1][-1], 1)]
    report["checks"]["com_inside_foot"] = feet[0][0] + 30 < com_y < feet[1][-1] - 30
    bb = Part.makeCompound(list(asm.values()) + list(cases.values())).BoundBox
    report["overall_mm"] = {"width": round(bb.XLength, 1), "depth": round(bb.YLength, 1), "height": round(bb.ZLength, 1)}
    report["rows"] = [{"tilt_deg": r.deg, "face_front_edge_yz": [round(v, 1) for v in r.F],
                       "face_back_edge_yz": [round(v, 1) for v in r.B]} for r in rows[:tiers]]
    report["joints"] = [{"tiers": j["tiers"], "butt_edge_mm": j["edge_mm"], "plate_seat_mm": j["seat_mm"],
                         "splice": "along" if j["edge_mm"] >= SPLICE_MIN_EDGE else "across",
                         "holes": [[round(v, 2) for v in h] for h in j["holes"]]}
                        for j in joints if j["tiers"][1] <= tiers]
    report["splice_adapter_12"] = {
        "plate_mm": [round(adapter["span"][1] - adapter["span"][0], 1), round(2 * adapter["hb"], 1)],
        "round_holes_along_mm": sorted({round(h[0] - adapter["span"][0], 2) for h in adapter["holes"]}),
        "slots_along_mm": sorted({tuple(round(c[0] - adapter["span"][0], 2) for c in sl) for sl in adapter["slots"]}),
        "top_under_pre_ledge_edge_mm": adapter["top_gap_mm"]}
    # screwless rows, loading path (checked against the full stand, the other cases out):
    #   row 1 lifts off its ledges (also with the rows above in), and lifted over its front lugs it
    #   slides out to the front
    #   rows 2+ are held under the lips (lifting moves only LIP_CLR); they slide up the rail until
    #   the case front end is LIP_GAP past the lip end, then lift straight off (face normal)
    stand = list(full_stand.values())
    load = {}
    for k in range(tiers):
        c = cases[f"case-{k + 1}"]
        nrm = V(0, rows[k].n[0], rows[k].n[1])
        if k == 0:
            over = FRONT_STOP[1] + 1.0
            others = [o for n, o in cases.items() if n not in ("case-1", "standoffs-1")]
            moves = [nrm * t for t in range(1, int(over) + 1)] + \
                [nrm * over + V(0, -t, 0) for t in range(2, int(CASE_YLEN) + 4, 4)]
            hit = max(hit_vol(c.translated(mv), stand) for mv in moves)
            hit_in = max(hit_vol(c.translated(nrm * t), stand + others) for t in range(1, int(over) + 1))
            load["case-1"] = {"path": f"lifts {over:g} mm over the front lugs, slides out to the front",
                              "clash_mm3": round(hit, 2), "lift_clash_rows_above_in_mm3": round(hit_in, 2)}
            continue
        up = rows[k].placement().Rotation.multVec(V(0, 1, 0))
        # the top row slides on past the top bar (it stays on): front end LIP_GAP past the bar's back face
        s = lip_len[k] + LIP_GAP + (BAR_W if k == kb else 0.0)
        held = free_slide(c, nrm, 5.0, step=0.25)
        slid = c.translated(up * s)
        lift = lifts_out(slid, nrm)
        load[f"case-{k + 1}"] = {
            "lip_mm": round(lip_len[k], 1), "lip_full_depth": lip_len[k] >= CASE_YLEN,
            "free_slide_up_rail_mm": None if slide_free[k] is None else round(slide_free[k], 1),
            "held_lift_mm": None if held is None else round(held, 2),
            "slide_to_load_mm": round(s, 1), "past_top_bar": k == kb,
            "slide_clear": free_slide(c, up, s, step=1.0) is None,
            "lift_clear_after_slide": lift}
    report["checks"]["loading"] = load

    # top bar: free play on the cheek ends (X: outer legs / shoulders, case Y: the end faces down and
    # the barbs up, case Z: shoulder under the ledge / top lip on the cheek top), the lift off the ends
    # clear of everything but the barbs with all the cases in, and room for the finger to flex
    if bar_name in asm:
        bar = asm[bar_name]
        rot_b = rows[kb].placement().Rotation
        cheeks_b = [asm[f"tier{kb + 1}-left"], asm[f"tier{kb + 1}-right"]]
        rest = [o for n, o in full_stand.items() if n != bar_name] + list(cases.values())

        def bar_travel(d, lim=3.0):
            hit = lambda t: hit_vol(bar.translated(d * t), cheeks_b) > 1e-3
            if not hit(lim):
                return None
            lo, hi = 0.0, lim
            while hi - lo > 0.02:
                lo, hi = (lo, (lo + hi) / 2) if hit((lo + hi) / 2) else ((lo + hi) / 2, hi)
            return round(lo, 2)
        nb = bar_nb.copy()
        nb.Placement = rows[kb].placement().multiply(nb.Placement)
        up = rot_b.multVec(V(0, 1, 0))
        bb = nb.BoundBox
        bb.add(nb.translated(up * (BAR_DOWN + 5)).BoundBox)
        near = [o for o in rest if o.BoundBox.intersect(bb)]
        z_barb = (BARB_Z[0] + BARB_Z[1]) / 2
        finger_l = RISE + BAR_LIP_CLR - z_barb
        flex = BARB - FINGER_CLR
        room = -SIDE_T - (X_IN + FINGER_CLR + FINGER_T)
        b = bar.BoundBox
        report["checks"]["top_bar"] = {
            "tier": kb + 1, "length_mm": round(bar_case.BoundBox.XLength, 1),
            "beam_mm": [BAR_W, round(BAR_BEAM_Z + BELOW, 1)], "beam_top_under_plate_mm": -BAR_BEAM_Z,
            "play_mm": {n: bar_travel(rot_b.multVec(V(*d))) for n, d in
                        (("out_left", (-1, 0, 0)), ("out_right", (1, 0, 0)), ("down_rail", (0, -1, 0)),
                         ("up_to_barb", (0, 1, 0)), ("case_z_up", (0, 0, 1)), ("case_z_down", (0, 0, -1)))},
            "lift_off_clear_cases_in": all(hit_vol(nb.translated(up * (0.5 * t)), near) < 1e-3
                                           for t in range(0, int(2 * (BAR_DOWN + 5)) + 1)),
            "snap": {"barb_overlap_mm": round(flex, 2), "lead_in_deg": BARB_IN, "retention_deg": BARB_OUT,
                     "finger_mm": [FINGER_T, round(FINGER_DOWN + BAR_W, 1), round(finger_l, 1)],
                     "finger_strain_pct": round(100 * 1.5 * FINGER_T * flex / finger_l ** 2, 2),
                     "finger_to_side_panel_mm": {"nominal": round(room, 2), "flexed": round(room - flex, 2),
                                                 "flexed_case_against_lip": round(room - flex - LIP_X_CLR, 2)}}}
        tb = report["checks"]["top_bar"]
        assert tb["lift_off_clear_cases_in"], tb
        assert all(v is not None and v <= 0.6 for n, v in tb["play_mm"].items() if n != "down_rail"), tb
        assert tb["play_mm"]["down_rail"] is not None and tb["play_mm"]["down_rail"] < 0.05, tb
        assert tb["snap"]["finger_to_side_panel_mm"]["flexed_case_against_lip"] >= 0.3, tb
        assert load[f"case-{kb + 1}"]["slide_clear"] and load[f"case-{kb + 1}"]["lift_clear_after_slide"], load

    # stretchers: each slides into its channels along the open side, clear of the whole stand (the
    # cases out), and the channel walls stop it STR_CLR away in the other in-plane directions
    frame = [s for n, s in full_stand.items() if not n.startswith("stretcher")]
    st_rep = {}
    for k in range(tiers):
        if not stretchers[k]:
            continue
        s = asm[f"stretcher-{k + 1}"]
        d = str_open[k]
        side = {(0, 1): "up", (1, 0): "back", (-1, 0): "front"}[d]
        out_d = V(0, d[0], d[1])
        bb = s.BoundBox
        bb.add(s.translated(out_d * 300).BoundBox)
        near = [o for o in frame if o.BoundBox.intersect(bb)]
        moves = [out_d * t for t in range(1, 301, 2)]

        def stop_at(v, lim=3.0):
            hit = lambda t: hit_vol(s.translated(v * t), near) > 1e-3
            if not hit(lim):
                return None
            lo, hi = 0.0, lim
            while hi - lo > 0.02:
                lo, hi = (lo, (lo + hi) / 2) if hit((lo + hi) / 2) else ((lo + hi) / 2, hi)
            return round(lo, 2)
        st_rep[f"stretcher-{k + 1}"] = {
            "centre_yz_mm": [round(v, 1) for v in stretchers[k]], "channel_open": side, "channel_mm": [round(2 * STR_HW, 2), RIM_H, RIM_W],
            "slide_in_clash_mm3": round(max(hit_vol(s.translated(mv), near) for mv in moves), 2),
            "held_mm": {n: stop_at(V(0, *v)) for n, v in
                        (("down", (-d[0], -d[1])), ("side_a", (d[1], -d[0])), ("side_b", (-d[1], d[0])))}}
        assert st_rep[f"stretcher-{k + 1}"]["slide_in_clash_mm3"] < 1e-2, st_rep
        assert all(v is not None and v < STR_CLR + 0.1 for v in st_rep[f"stretcher-{k + 1}"]["held_mm"].values()), st_rep
    report["checks"]["stretchers"] = st_rep

    # case fit, row by row (the case as built, screw heads included): free travel from its modelled
    # seat across the stand (X), along the rails onto the stop lugs and off the ledges, and the area
    # each ledge carries under the bottom plate
    def travel(shape, d, lim=8.0):
        bb = shape.BoundBox
        bb.enlarge(lim + 1)
        near = [o for o in stand if o.BoundBox.intersect(bb)]
        hit = lambda t: any(shape.translated(d * t).common(o).Volume > 1e-3 for o in near)
        if not hit(lim):
            return None
        lo, hi = 0.0, lim
        while hi - lo > 0.05:
            lo, hi = (lo, (lo + hi) / 2) if hit((lo + hi) / 2) else ((lo + hi) / 2, hi)
        return round(lo, 2)
    fit = {}
    for k in range(tiers):
        rot_k = rows[k].placement().Rotation
        c = cases[f"case-{k + 1}"]
        plate = c.Solids[0]
        down = rot_k.multVec(V(0, 0, -1))
        f = {"seat": "ledges", "ledge_mm": tongue(k),
             "play_left_right_mm": [travel(c, V(-1, 0, 0)), travel(c, V(1, 0, 0))],
             "to_stop_lugs_mm": travel(c, rot_k.multVec(V(0, 1 if k == 0 else -1, 0)))}
        for side in ("left", "right"):
            a = plate.translated(down * 0.1).common(asm[f"tier{k + 1}-{side}"]).Volume / 0.1
            f[f"ledge_{side}_contact"] = {"area_cm2": round(a / 100, 1), "width_mm": round(a / CASE_YLEN, 1)}
        if k == 0:
            f["to_front_lugs_mm"] = travel(c, V(0, -1, 0))
        if k:
            f["lip_over_step_mm"] = round(PLATE_STEP - LIP_X_CLR, 2)
            f["lip_section_mm"] = [round(GAP_X + PLATE_STEP - LIP_X_CLR, 2), RAIL]
        fit[f"case-{k + 1}"] = f
    report["checks"]["case_fit"] = fit

    # fasteners: every screw is an M3x8 socket head into an M3x10 hex spacer glued in a blind
    # socket (as in the case). Each socket must sit in solid print with SOCKET_WALL round it and
    # under it, and the screw must reach ENGAGE_MIN into the spacer without passing its end.
    def wall_prism(c, x0, sgn):
        r = (SOCKET_AF + 2 * SOCKET_WALL) / math.sqrt(3)
        pts = [V(0, c[0] + r * math.cos(math.radians(60 * i)), c[1] + r * math.sin(math.radians(60 * i))) for i in range(6)]
        p = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(sgn * (SOCKET_DEPTH + SOCKET_WALL), 0, 0))
        return p.translated(V(x0 + sgn * 0.02, 0, 0))
    fast = {}
    for n, (pre, socks) in precut.items():
        if n not in asm:
            continue
        for kind, c, x0, sgn in socks:
            w = wall_prism(c, x0, sgn)
            fast.setdefault(n, {"sockets": 0, "walled": 0})
            fast[n]["sockets"] += 1
            fast[n]["walled"] += abs(pre.common(w).Volume - w.Volume) < 0.05
    stacks = {"splice": {"under_head_mm": SPLICE_T - SPLICE_CB, "into_spacer_mm": round(SPLICE_ENGAGE, 2)},
              "stretcher": {"under_head_mm": STRETCH_GRIP, "into_spacer_mm": round(STRETCH_ENGAGE, 2)}}
    # the stretcher screw grips the full cheek boss: measure it at each stretcher end
    for k in range(tiers):
        if not stretchers[k]:
            continue
        y, z = stretchers[k]
        for side, x_in, sgn in (("left", X_IN, 1), ("right", X_IN_R, -1)):
            pre = precut[f"tier{k + 1}-{side}"][0]
            ray = pre.common(Part.makeLine(V(x_in - sgn * 40, y, z), V(x_in + sgn * 5, y, z)))
            th = sum(e.Length for e in ray.Edges)
            assert abs(th - T) < 0.05, f"tier{k + 1}-{side}: stretcher boss {th:.2f} mm, not {T}"
    for n, f in fast.items():
        assert f["walled"] == f["sockets"], f"{n}: spacer socket without {SOCKET_WALL} mm walls: {f}"
    for n, st in stacks.items():
        assert ENGAGE_MIN <= st["into_spacer_mm"] <= 10.0 - 0.5, f"{n}: M3x{SCREW_L:g} {st}"
    report["checks"]["fasteners"] = {"screw": f"M3x{SCREW_L:g} socket head only", "stacks": stacks,
                                     "spacer_sockets": fast}
    report["feet"] = {f"tier{k + 1}": [round(y, 1) for y in ys] for k, ys in feet.items() if k < tiers}
    report["checks"]["foot_pad_mm"] = [T, PAD]
    report["checks"]["foot_mm"] = [FOOT, FOOT]

    out = CASE / "print" / "stand"
    rnd = CASE / "research" / "stand"
    out.mkdir(parents=True, exist_ok=True)
    rnd.mkdir(parents=True, exist_ok=True)
    for f in list(rnd.glob("asm-*.stl")):
        f.unlink()
    report["print"] = {}
    # print set: one folder per tier (its two cheeks) plus common/ for the parts every joint and
    # stretcher share; flat cheeks with the outer face on the bed, ledges and lugs up
    for f in list(out.glob("*.stl")) + list(out.glob("*.3mf")) + list(out.glob("*/*.stl")) + list(out.glob("*/*.3mf")):
        if f.parent == out or f.parent.name == "common" or f.parent.name in {f"tier{k + 1}" for k in range(tiers)}:
            f.unlink()
    prints = {}
    for n, s in asm.items():
        assert s.isValid() and len(s.Solids) == 1, f"{n}: not one valid solid"
        if n.startswith("tier"):
            p = s.copy()
            p.rotate(V(0, 0, 0), V(0, 1, 0), -90 if n.endswith("left") else 90)   # outer face (-X on the left) down
            prints[f"{n.split('-')[0]}/{n}"] = (p, s.Volume)
    # the top bar prints back face down (legs and finger up), diagonal: longer than the bed
    if bar_name in asm:
        p = bar_case.copy()
        p.rotate(V(0, 0, 0), V(1, 0, 0), -90)
        p.rotate(V(0, 0, 0), V(0, 0, 1), 45)
        prints[f"tier{kb + 1}/top-bar"] = (p, bar_case.Volume)
    # splice plates are symmetric (left = right mirror): one common part per plate size, along
    # (long butt edges) or across (short ones)
    for j in joints:
        if j["tiers"][1] > tiers:
            continue
        kind = "along" if j["edge_mm"] >= SPLICE_MIN_EDGE else "across"
        ha, hb = j["half"]
        p = face2d([(-ha, -hb), (ha, -hb), (ha, hb), (-ha, hb)]).makeOffset2D(-4, 0).makeOffset2D(4, 2)
        p = p.extrude(V(0, 0, SPLICE_T))
        for a, b in j["local"]:
            p = p.cut(cyl(M3_CLEAR / 2, SPLICE_T + 2, (a, b, -1), (0, 0, 1)))
            p = p.cut(cyl(M3_CB_D / 2, SPLICE_CB + 1, (a, b, SPLICE_T - SPLICE_CB), (0, 0, 1)))
        n = f"common/splice-plate-{kind}"
        for side in ("left", "right"):
            v = asm[f"splice-{j['tiers'][0]}{j['tiers'][1]}-{side}"].Volume
            assert abs(v - p.Volume) < 0.5, f"{n} print {p.Volume} != assembly {v}"
        if n in prints:
            assert abs(prints[n][1] - p.Volume) < 0.5, f"{n}: two sizes"
        prints[n] = (p, p.Volume)
    # the 1-2 adapter plate (same section and counterbores, counterbores up)
    a0, a1 = adapter["span"]
    hb = adapter["hb"]
    p = face2d([(a0, -hb), (a1, -hb), (a1, hb), (a0, hb)]).makeOffset2D(-4, 0).makeOffset2D(4, 2).extrude(V(0, 0, SPLICE_T))

    def slot(r, h, z, c0, c1):
        s = cyl(r, h, (c0[0], c0[1], z), (0, 0, 1))
        if c1 == c0:
            return s
        return s.fuse(cyl(r, h, (c1[0], c1[1], z), (0, 0, 1))).fuse(Part.makeBox(c1[0] - c0[0], 2 * r, h, V(c0[0], c0[1] - r, z)))
    for c0, c1 in [(h, h) for h in adapter["holes"]] + adapter["slots"]:
        p = p.cut(slot(M3_CLEAR / 2, SPLICE_T + 2, -1, c0, c1))
        p = p.cut(slot(M3_CB_D / 2, SPLICE_CB + 1, SPLICE_T - SPLICE_CB, c0, c1))
    prints["common/splice-plate-adapter"] = (p, p.Volume)
    strs = [s for n, s in asm.items() if n.startswith("stretcher")]
    if strs:
        assert len({round(s.Volume, 1) for s in strs}) == 1 and len({round(s.BoundBox.XLength, 2) for s in strs}) == 1
        prints["common/stretcher"] = (strs[0].copy(), strs[0].Volume)
    for n, (p, vol) in prints.items():
        b = p.BoundBox
        p.translate(V(-b.XMin, -b.YMin, -b.ZMin))
        b = p.BoundBox
        (out / n).parent.mkdir(exist_ok=True)
        mesh = MeshPart.meshFromShape(Shape=p, LinearDeflection=0.02, AngularDeflection=0.2)
        mesh.write(str(out / f"{n}.stl"))
        mesh.write(str(out / f"{n}.3mf"))
        dims = sorted([b.XLength, b.YLength, b.ZLength], reverse=True)
        report["print"][n] = {"bbox_mm": [round(v, 1) for v in (b.XLength, b.YLength, b.ZLength)],
                              "fits_p2s_bed": dims[0] <= BED - 4 and dims[1] <= BED - 4,
                              "volume_cm3": round(vol / 1000, 1)}
    for n, s in asm.items():
        # assembly-pose meshes for the render
        MeshPart.meshFromShape(Shape=s, LinearDeflection=0.05, AngularDeflection=0.3).write(str(rnd / f"asm-{n}.stl"))
    def mesh_case(n, c, d, half=None):
        """case meshes, the screw heads apart (they render in their own colour), cut by half"""
        sol = c.Solids
        parts = {n: sol} if n.startswith("standoffs") else {n: sol[:5], f"screws-{n[5:]}": sol[5:]}
        for m, p in parts.items():
            p = Part.makeCompound([q.common(half) for q in p] if half else p)
            if p.Volume > 1e-3:
                MeshPart.meshFromShape(Shape=p, LinearDeflection=0.1, AngularDeflection=0.3).write(str(d / f"asm-{m}.stl"))
    for n, c in cases.items():
        mesh_case(n, c, rnd)
    # fit views: the stand and the cases cut open, meshes + camera per view in research/stand/fit/
    #   row<k>: across row k on its front bolt line (case Y 25), looking up the rails at the left
    #           ledge, guide band and bottom plate screw head
    #   stop<k>: along the left side of the case at the lower end of row k: row 1 at case X -9
    #           (through its stop lugs), rows 2+ at X -14 (through the plate step, lip and lug)
    #   load<k>: rows 2+ that have a short lip, at X -14: the case at its loading position (slid up
    #           the rail, its front end LIP_GAP past the lip end), the row above out
    views = {}
    for k in range(tiers):
        pl = rows[k].placement()
        yc = 25.0
        half = Part.makeBox(2000, 1000, 2000, V(-1000, yc, -1000))
        half.Placement = pl.multiply(half.Placement)
        views[f"row{k + 1}"] = (half, pl.multVec(V(-8, yc, 8)), pl.Rotation.multVec(V(0, 1, 0)), 75, cases)
        xc = -9.0 if k == 0 else -14.0
        half = Part.makeBox(1000, 2000, 2000, V(xc, -1000, -1000))
        ye = CASE_YLEN + CASE_Y0 if k == 0 else CASE_Y0
        views[f"stop{k + 1}"] = (half, pl.multVec(V(xc, ye, 12)), V(1, 0, 0), 90, cases)
        if k == 0:
            views["front1"] = (half, pl.multVec(V(xc, CASE_Y0, 12)), V(1, 0, 0), 90, cases)
        if k and lip_len[k] < CASE_YLEN:
            s_load = lip_len[k] + LIP_GAP
            moved = {n: (c.translated(pl.Rotation.multVec(V(0, s_load, 0))) if n == f"case-{k + 1}" else c)
                     for n, c in cases.items() if n not in (f"case-{k + 2}", f"standoffs-{k + 2}")}
            views[f"load{k + 1}"] = (half, pl.multVec(V(xc, CASE_Y0 + CASE_YLEN / 2 + s_load / 2, 20)), V(1, 0, 0), 230, moved)
    #   bar<k>: the top bar on the left cheek end, cut along the case Z through the barb (finger and
    #           barb in the last pocket under the end rail); bar<k>x: across it through the barb
    #           (outer leg, shoulder under the ledge, top lip, finger over the case side panel)
    if bar_name in asm:
        pl = rows[kb].placement()
        zc = (BARB_Z[0] + BARB_Z[1]) / 2
        y_end = CASE_Y0 + CASE_YLEN - RAIL
        half = Part.makeBox(2000, 2000, 1000, V(-1000, -1000, zc - 1000))
        half.Placement = pl.multiply(half.Placement)
        views[f"bar{kb + 1}"] = (half, pl.multVec(V(X_IN, y_end + 2, zc)), pl.Rotation.multVec(V(0, 0, -1)), 36, cases)
        yc = y_end - 1.2
        half = Part.makeBox(2000, 1000, 2000, V(-1000, yc - 1000, -1000))
        half.Placement = pl.multiply(half.Placement)
        views[f"bar{kb + 1}x"] = (half, pl.multVec(V(X_IN - 2, yc, 10)), pl.Rotation.multVec(V(0, -1, 0)), 85, cases)
    #   stretcher<k>: the left end of the stretcher in its channel, from inboard / above / behind,
    #           the stand right of the channel walls cut away, no cases
    for k in range(tiers):
        if stretchers[k]:
            y, z = stretchers[k]
            half = Part.makeBox(1000, 2000, 2000, V(X_IN + RIM_H + 30 - 1000, -1000, -1000))
            look = V(-1, -0.7, -0.8)
            look.normalize()
            views[f"stretcher{k + 1}"] = (half, V(X_IN + RIM_H, y, z), look, 90, {})
    fitd = rnd / "fit"
    for f in fitd.glob("*/*"):
        f.unlink()
    for v, (half, tgt, look, scale, view_cases) in views.items():
        d = fitd / v
        d.mkdir(parents=True, exist_ok=True)
        box = Part.makeBox(scale * 3, scale * 3, scale * 3, tgt - V(1, 1, 1) * scale * 1.5).BoundBox
        for n, s in asm.items():
            if s.BoundBox.intersect(box):
                cut = s.common(half)
                if cut.Volume > 1e-3:
                    MeshPart.meshFromShape(Shape=cut, LinearDeflection=0.05, AngularDeflection=0.3).write(str(d / f"asm-{n}.stl"))
        for n, c in view_cases.items():
            if c.BoundBox.intersect(box):
                mesh_case(n, c, d, half)
        (d / "camera.json").write_text(json.dumps({"target_mm": [round(x, 2) for x in tgt],
                                                   "look_dir": [round(x, 4) for x in look], "ortho_mm": scale}))
    doc = App.newDocument("SkiffStand")
    for n, s in list(asm.items()) + list(cases.items()):
        doc.addObject("Part::Feature", n.replace("-", "_")).Shape = s
    (CASE / "cad").mkdir(exist_ok=True)
    doc.saveAs(str(CASE / "cad" / f"stand-{tiers}.FCStd"))
    report["build_s"] = round(time.time() - t0, 1)
    n_str = sum(1 for s in stretchers[:tiers] if s)
    report["hardware"] = {
        "cases": "none: row 1 is lifted over its front lugs onto its ledges; rows 2+ drop onto their ledges behind the lips and slide down under them onto the stop lugs",
        "top_bar": "none: pushed down onto the tier 3 cheek top ends until both fingers click; pull it straight up to take it off",
        "splice_plates": f"{8 * (tiers - 1)}x M3x{SCREW_L:g} + {8 * (tiers - 1)}x M3x10 hex spacer (glued in the cheeks): "
                         f"{SPLICE_CB:g} mm counterbore, {SPLICE_T - SPLICE_CB:g} mm plate under the head, {SPLICE_ENGAGE:.1f} mm into the spacer",
        "feet": f"{2 * sum(len(ys) for k, ys in feet.items() if k < tiers)}x {FOOT:g} x {FOOT:g} mm self-adhesive (3M) rubber foot, "
                f"stuck on a flat {T:g} x {PAD:g} mm plate under the cheek (no screws)",
        "stretchers": f"{2 * n_str}x M3x{SCREW_L:g} + {2 * n_str}x M3x10 hex spacer (glued in the stretcher ends), each end slid into a "
                      f"{2 * STR_HW:g} mm U channel ({RIM_H:g} mm walls) on the cheek: "
                      f"{STRETCH_CB:g} mm counterbore, {STRETCH_GRIP:g} mm cheek under the head, {STRETCH_ENGAGE:.1f} mm into the spacer",
    }
    (rnd / f"stand-{tiers}-report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


main()
