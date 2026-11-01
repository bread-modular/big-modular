"""FreeCAD generator for a modular, Moog-style tiered stand for 2 or 3 skiffs (case/tools/build_case.py).

Run with FreeCAD's headless interpreter (see case/tools/build_stand.sh):
  case/tools/build_stand.sh                   # tilts 0 / 40 / 70 deg
  STAND_TILTS=0,35,65 case/tools/build_stand.sh

Frame (all dimensions mm), the skiff assembly frame turned on its side:
  X  across the stand, same as the case X (X = 0 is the inner face of the left case side panel)
  Y  depth, front (user) -> back
  Z  up, Z = 0 is the table

Each side frame is a printed cheek in the Y/Z plane with a flat outer face: a 6 mm (T_WEB) web with
12 mm (T) bosses on the inner face only where screws go (splice plate seats, stretcher ends), made of
one piece per tier:
  tier 1 = the base beside row 1, tier 2 bolts on behind it, tier 3 on top of that.
Row 1 is not lifted: the skiff stands on the desk on its own bottom plate, as it does without the
stand (first tilt 0). The tier 1 cheeks stand on the desk either side of it and tier 2 carries a
stop lug behind it, so row 1 slides in from the front with no bolts and lifts out the same way.
  A 2-row stand is tier 1 + 2, a 3-row stand adds tier 3: the pieces do not change.
Every piece is the convex outline of its row (plus the foot for tier 1) minus the rows below it,
clipped flush with the module faces, with lightening windows. The pieces butt together and a
6 mm splice plate on the outer face bolts across each joint with 4 M3 screws into M3 hex
spacers superglued in the cheeks (the case's 5.7 AF x 10.2 blind socket).
Rows 2 and 3 sit on a tongue on the cheek's inner face, under its bottom plate: the case's own four
plate-to-side-panel bolts get longer (M3x12) and go through the tongue too, so the cases need no
change. A stretcher on each tier that has room for one (not tier 1: row 1 fills it) ties the left and right cheeks, M3 into spacers in its ends.
The modules are held by 10 mm M3 male-female hex standoffs: the male end goes through the panel
into the rail spacer and the hex body stands 10 mm proud of the module face on both rail hole
lines. A row is placed so the lower row's back standoffs and the upper row's front standoffs are
SO_GAP apart (fingers / a 5.5 mm nut driver between them) and each is SO_CASE clear of the other
row's case + tongue.
Print set (case/print/stand/, see its README.md): tier1/ tier2/ tier3/ hold each tier's two
cheeks, common/ the shared stretcher and splice plate.
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
BOLT_Y = (25.0, 128.5 - 25.0)          # plate-to-side-panel bolts, at the side panel centre

# --- fasteners (same as the case) ------------------------------------------------
M3_CLEAR, M3_CB_D, M3_CB_DEPTH = 3.4, 6.5, 3.2
SOCKET_AF, SOCKET_DEPTH = 5.7, 10.2

# --- stand -----------------------------------------------------------------------
T = 12.0             # cheek thickness (X) at the screw bosses (splice pads, stretcher ends)
T_WEB = 6.0          # cheek thickness everywhere else (rim, ribs): the bosses stand proud on the outer face
BOSS_MARGIN = 2.0    # splice pad reaches this far past the splice plate outline
BOSS_R = 10.0        # round boss behind each stretcher end
GAP_X = 1.0          # bottom plate edge -> cheek inner face (clears the rail screw heads)
TONGUE = 6.0         # tongue under the case bottom plate (Z in case frame)
TONGUE_IN = 8.0      # tongue reaches this far inboard past the bolt line
WEB = 18.0           # rim / rib width around the windows
BELOW = TONGUE + WEB  # cheek below the case bottom plate
FOOT_H = 14.0        # rear foot height
STOP = (10.0, 6.0, 30.0)  # row 1 stop lug behind the case: Y length, inboard of the case side panel outer face, Z height
REAR_FOOT = 20.0     # rear foot reaches this far behind row 2
ROW_CLR = 6.0        # free space between neighbouring rows (case + tongue)
STANDOFF_H = 10.0    # M3 male-female hex standoff body above the module face (module fixing)
STANDOFF_AF = 5.5
SO_GAP = 15.0        # back standoffs of a row <-> front standoffs of the row above
SO_CASE = 12.0       # standoffs of a row <-> case + tongue of its neighbour
HOLE_Y = (3.0, 128.5 - 3.0)            # module rail hole lines (case Y)
CASE_X_IN = 218.7                      # case inner width (side panel to side panel)
SPLICE_T, SPLICE_W, SPLICE_L = 6.0, 34.0, 74.0
STRETCH = 20.0       # square stretcher section

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

    def rect(self, below=0.0):
        y0, y1 = CASE_Y0, CASE_Y0 + CASE_YLEN
        return [self.pt(y0, -below), self.pt(y1, -below), self.pt(y1, CASE_H), self.pt(y0, CASE_H)]

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
            # row 1 stands on the desk on its own bottom plate (no tongue, no foot under it)
            r = Row(a, (0.0, 0.0))
            lo = min(p[1] for p in r.rect())
            fy = min(p[0] for p in r.rect())
            r = Row(a, (-fy, -lo))
        else:
            prev = rows[-1]
            # slide the row back/up along the bisector of the two face directions until the
            # case + tongue outlines are ROW_CLR apart and the standoffs have hand room
            u = rot((1, 0), (prev.a + math.radians(a)) / 2)
            s = 0.0
            while True:
                r = Row(a, add(prev.B, u, s))
                if min(so_gaps(prev, r)) >= 0:
                    break
                s += 0.25
        rows.append(r)
    return rows


def so_gaps(lo, hi):
    """Margins (>= 0: ok) of the row clearances between a row and the row above it."""
    return (sat_gap(lo.rect(TONGUE), hi.rect(TONGUE)) - ROW_CLR,
            sat_gap(lo.standoff(1), hi.standoff(0)) - SO_GAP,
            sat_gap(lo.standoff(1), hi.rect(TONGUE)) - SO_CASE,
            sat_gap(hi.standoff(0), lo.rect(TONGUE)) - SO_CASE)


def clip_faces(rows):
    """Everything in front of / above the chain of module faces: the cheeks end flush with them."""
    chain = []
    for r in rows:
        chain += [r.F, r.B]
    top = chain[-1]
    return face2d([add(chain[0], (-600, 0))] + chain + [add(top, rows[-1].n, 600), (chain[0][0] - 600, top[1] + 600)])


def biggest(face):
    fs = sorted(face.Faces, key=lambda f: -f.Area)
    return fs[0]


def windows(piece, row):
    inner = piece.makeOffset2D(-WEB, 0)
    band = face2d([row.pt(CASE_Y0 - 50, -BELOW - WEB / 2), row.pt(CASE_Y0 + CASE_YLEN + 50, -BELOW - WEB / 2),
                   row.pt(CASE_Y0 + CASE_YLEN + 50, -BELOW + WEB / 2), row.pt(CASE_Y0 - 50, -BELOW + WEB / 2)])
    w = inner.cut(band)
    out = []
    for f in w.Faces:
        if f.Area < 900:
            continue
        try:   # a long thin window can vanish under the -6 offset: skip it
            g = f.makeOffset2D(-6, 0).makeOffset2D(6, 2) if f.Area > 1500 else None
        except ValueError:
            g = None
        if g is not None and g.Faces:
            out += g.Faces
    return out


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


def svg_profile(path, faces, rows, extra=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["#c9a46a", "#7a9cc6", "#9bc67a", "#c67a9b"]
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-40 -420 460 460" width="900">']
    for i, f in enumerate(faces):
        for w in f.Wires:
            pts = " ".join(f"{v.x:.1f},{-v.y:.1f}" for v in w.discretize(Deflection=0.5))
            out.append(f'<polygon points="{pts}" fill="{cols[i % 4]}" fill-opacity="0.6" stroke="black" stroke-width="0.5"/>')
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

    # tier 1 stands on the desk beside row 1; tier 2 has a rear foot under row 2 (it carries the
    # rows above, so the stand cannot tip back); tier 3 sits on tier 2 only
    r1 = rows[0].rect()
    y_front, y_mid = min(p[0] for p in r1), max(p[0] for p in r1)
    foot = [(y_front, 0), (y_mid, 0), (y_mid, FOOT_H), (y_front, FOOT_H)]
    y_back = max(p[0] for p in rows[1].rect(BELOW)) + REAR_FOOT
    rear = [(y_back - 60, 0), (y_back, 0), (y_back, FOOT_H), (y_back - 60, FOOT_H)]

    clip = clip_faces(rows)
    desk = face2d([(-600, 0), (900, 0), (900, -600), (-600, -600)])
    outlines = []
    for k in range(len(rows)):
        if k == 0:
            pts = foot + r1
        else:
            pts = rows[k - 1].rect(0 if k == 1 else BELOW) + rows[k].rect(BELOW) + (rear if k == 1 else [])
        outlines.append(face2d(hull(pts)).cut(clip).cut(desk))
    solid2d = []
    for k in range(len(rows)):
        p = outlines[k]
        for q in outlines[:k]:
            p = p.cut(q)
        solid2d.append(biggest(p))
    pieces2d = solid2d
    svg_profile(CASE / "research" / "stand" / "profile.svg", solid2d, rows)

    # joints: longest shared edge between neighbouring pieces -> splice plate
    joints = []
    for k in range(1, len(rows)):
        sec = pieces2d[k].section(pieces2d[k - 1])
        e = max(sec.Edges, key=lambda e: e.Length)
        a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
        mid = ((a.x + b.x) / 2, (a.y + b.y) / 2)
        d = ((b.x - a.x) / e.Length, (b.y - a.y) / e.Length)
        nrm = (-d[1], d[0])
        joints.append({"tiers": (k, k + 1), "edge": (mid, d, nrm), "edge_mm": round(e.Length, 1)})
    # one splice plate for every joint: as long as the shortest butt edge allows
    L = min([SPLICE_L] + [j["edge_mm"] - 8 for j in joints])
    for j in joints:
        mid, d, nrm = j.pop("edge")
        holes = [add(add(mid, d, s * (L / 2 - 9)), nrm, t * (WEB / 2 - 0.5)) for s in (-1, 1) for t in (-1, 1)]
        corners = [add(add(mid, d, s * L / 2), nrm, t * SPLICE_W / 2) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        j.update(holes=holes, plate=corners, splice_l=L)

    # stretchers: one per tier, as far back as the piece allows, clear of every case outline
    stretchers = []
    for k, p in enumerate(solid2d):
        bb = p.BoundBox
        pin = p.makeOffset2D(-WEB / 2, 0)
        best = None
        y = bb.XMin
        while y < bb.XMax:
            z = bb.YMin
            while z < bb.YMax:
                sq = [(y - STRETCH / 2 - 3, z - STRETCH / 2 - 3), (y + STRETCH / 2 + 3, z - STRETCH / 2 - 3),
                      (y + STRETCH / 2 + 3, z + STRETCH / 2 + 3), (y - STRETCH / 2 - 3, z + STRETCH / 2 + 3)]
                fsq = face2d(sq)
                if abs(fsq.common(pin).Area - fsq.Area) < 1e-3 and all(sat_gap(sq, r.rect(TONGUE)) > 3 for r in rows) \
                        and all(not any(abs(h[0] - y) < 20 and abs(h[1] - z) < 20 for h in j["holes"]) for j in joints):
                    score = y + (0.3 * z if k == 0 else 0.6 * z)
                    if best is None or score > best[0]:
                        best = (score, (y, z))
                z += 4
            y += 4
        # tier 3 is a thin cheek: its row ties the two sides
        stretchers.append(best[1] if best else None)

    # lightening windows, keeping a boss round each stretcher end
    pieces2d = []
    for k, p in enumerate(solid2d):
        for w in windows(p, rows[k]):
            if stretchers[k]:
                y, z = stretchers[k]
                b = STRETCH / 2 + WEB / 2
                w = w.cut(face2d([(y - b, z - b), (y + b, z - b), (y + b, z + b), (y - b, z + b)]))
            for f in w.Faces:
                if f.Area > 900:
                    p = p.cut(f)
        pieces2d.append(biggest(p))

    def bosses(k):
        """2D boss pads of piece k: the splice plate seat at each joint, a disc at the stretcher end."""
        out = []
        for j in joints:
            if k + 1 in j["tiers"]:
                f = face2d(j["plate"]).makeOffset2D(-4, 0).makeOffset2D(4 + BOSS_MARGIN, 2)
                out += f.common(pieces2d[k]).Faces
        if stretchers[k]:
            y, z = stretchers[k]
            out += Part.Face(Part.Wire(Part.makeCircle(BOSS_R, V(y, z, 0)))).common(pieces2d[k]).Faces
        return [f for f in out if f.Area > 1]

    def cheek(k, left):
        sgn = 1 if left else -1      # outward is -X on the left
        x_in = X_IN if left else X_IN_R
        x_out = x_in - sgn * T
        # thin web flush with the flat outer face (the splice plates sit on it); full-thickness bosses
        # only where screws / spacers go, standing proud on the inner face with the tongue, so the
        # piece still prints outer face down with no supports
        x_web = x_out + sgn * T_WEB
        s = to_stand(pieces2d[k].extrude(V(0, 0, T_WEB)), min(x_out, x_web))
        x_b = x_web - sgn * 1.0      # bosses start 1 mm inside the web (no coplanar faces to fuse)
        bs = [to_stand(b.extrude(V(0, 0, abs(x_in - x_b))), min(x_in, x_b)) for b in bosses(k)]
        if bs:
            s = s.multiFuse(bs).removeSplitter()
        r = rows[k]
        # tongue under the bottom plate, along the whole case depth, from the web
        tx1 = BOLT_X[0] + TONGUE_IN if left else BOLT_X[1] - TONGUE_IN
        tongue = Part.makeBox(abs(tx1 - x_web), CASE_YLEN, TONGUE, V(min(x_web, tx1), CASE_Y0, -TONGUE))
        bx = BOLT_X[0] if left else BOLT_X[1]
        for by in BOLT_Y:
            tongue = tongue.cut(cyl(M3_CLEAR / 2, TONGUE + 2, (bx, by, -TONGUE - 1), (0, 0, 1)))
            tongue = tongue.cut(cyl(M3_CB_D / 2, M3_CB_DEPTH + 1, (bx, by, -TONGUE - 1), (0, 0, 1)))
        tongue.Placement = r.placement().multiply(tongue.Placement)
        if k > 0:      # row 1 stands on the desk: no tongue under it
            s = s.fuse(tongue)
        if k == 1:
            # stop lug behind row 1, against the back end of its side panel
            ys = max(p[0] for p in rows[0].rect()) + 0.5
            sx = (-SIDE_T + STOP[1]) if left else (CASE_X_IN + SIDE_T - STOP[1])
            s = s.fuse(Part.makeBox(abs(sx - x_web), STOP[0], STOP[2], V(min(x_web, sx), ys, 0)))
        cuts = []
        for j in joints:
            if k + 1 in j["tiers"]:
                for h in j["holes"]:
                    # sockets only under this piece's half of the splice
                    if face2d([add(h, (-1, -1)), add(h, (1, -1)), add(h, (1, 1)), add(h, (-1, 1))]).common(pieces2d[k]).Area > 1:
                        cuts.append(hex_prism(h, SOCKET_DEPTH, x_out, sgn))
                        cuts.append(cyl(1.2, T + 2, (x_out - sgn, h[0], h[1]), (sgn, 0, 0)))  # glue vent
        if stretchers[k]:
            y, z = stretchers[k]
            cuts.append(cyl(M3_CLEAR / 2, T + 2, (x_out - sgn, y, z), (sgn, 0, 0)))
            cuts.append(cyl(M3_CB_D / 2, M3_CB_DEPTH + 1, (x_out - sgn, y, z), (sgn, 0, 0)))
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
        return s

    def stretcher(k):
        y, z = stretchers[k]
        L = X_IN_R - X_IN
        s = Part.makeBox(L, STRETCH, STRETCH, V(X_IN, y - STRETCH / 2, z - STRETCH / 2))
        for xe, sg in ((X_IN, 1), (X_IN_R, -1)):
            s = s.cut(hex_prism((y, z), SOCKET_DEPTH, xe, sg))
        return s

    asm = {}
    for k in range(tiers):
        for left in (True, False):
            asm[f"tier{k + 1}-{'left' if left else 'right'}"] = cheek(k, left)
        if stretchers[k]:
            asm[f"stretcher-{k + 1}"] = stretcher(k)
    for j in joints:
        if j["tiers"][1] <= tiers:
            for left in (True, False):
                asm[f"splice-{j['tiers'][0]}{j['tiers'][1]}-{'left' if left else 'right'}"] = splice(j, left)

    # the skiffs, from the case build
    case_parts = Part.read(str(CASE / "print" / "assembly-preview.step"))
    cases = {}
    for k in range(tiers):
        c = case_parts.copy()
        c.Placement = rows[k].placement().multiply(c.Placement)
        cases[f"case-{k + 1}"] = c

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
    report["checks"]["foot_y_mm"] = [round(y_front, 1), round(y_back, 1)]
    report["checks"]["com_inside_foot"] = y_front + 30 < com_y < y_back - 30
    bb = Part.makeCompound(list(asm.values()) + list(cases.values())).BoundBox
    report["overall_mm"] = {"width": round(bb.XLength, 1), "depth": round(bb.YLength, 1), "height": round(bb.ZLength, 1)}
    report["rows"] = [{"tilt_deg": r.deg, "face_front_edge_yz": [round(v, 1) for v in r.F],
                       "face_back_edge_yz": [round(v, 1) for v in r.B]} for r in rows[:tiers]]
    report["joints"] = [{"tiers": j["tiers"], "butt_edge_mm": j["edge_mm"]} for j in joints if j["tiers"][1] <= tiers]

    out = CASE / "print" / "stand"
    rnd = CASE / "research" / "stand"
    out.mkdir(parents=True, exist_ok=True)
    rnd.mkdir(parents=True, exist_ok=True)
    for f in list(rnd.glob("asm-*.stl")):
        f.unlink()
    report["print"] = {}
    # print set: one folder per tier (its two cheeks) plus common/ for the parts every joint and
    # stretcher share; flat cheeks with the outer face on the bed, tongue up
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
    # every splice plate is the same symmetric plate (left = right mirror), so one common part
    lens = {j["splice_l"] for j in joints if j["tiers"][1] <= tiers}
    if lens:
        assert len(lens) == 1, f"splice plates differ: {lens}"
        L = lens.pop()
        f = face2d([(-L / 2, -SPLICE_W / 2), (L / 2, -SPLICE_W / 2), (L / 2, SPLICE_W / 2), (-L / 2, SPLICE_W / 2)])
        p = f.makeOffset2D(-4, 0).makeOffset2D(4, 2).extrude(V(0, 0, SPLICE_T))
        for sx in (-1, 1):
            for sy in (-1, 1):
                p = p.cut(cyl(M3_CLEAR / 2, SPLICE_T + 2, (sx * (L / 2 - 9), sy * (WEB / 2 - 0.5), -1), (0, 0, 1)))
        vols = {round(s.Volume, 1) for n, s in asm.items() if n.startswith("splice")}
        assert vols == {round(p.Volume, 1)}, f"splice print {p.Volume} != assembly {vols}"
        prints["common/splice-plate"] = (p, p.Volume)
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
    for n, c in cases.items():
        MeshPart.meshFromShape(Shape=c, LinearDeflection=0.1, AngularDeflection=0.3).write(str(rnd / f"asm-{n}.stl"))
    doc = App.newDocument("SkiffStand")
    for n, s in list(asm.items()) + list(cases.items()):
        doc.addObject("Part::Feature", n.replace("-", "_")).Shape = s
    (CASE / "cad").mkdir(exist_ok=True)
    doc.saveAs(str(CASE / "cad" / f"stand-{tiers}.FCStd"))
    report["build_s"] = round(time.time() - t0, 1)
    n_str = sum(1 for s in stretchers[:tiers] if s)
    report["hardware"] = {
        "case_to_tongue": f"{4 * (tiers - 1)}x M3x12 (rows 2+; row 1 stands loose on the desk) socket head, replacing the case's M3x6 plate bolts "
                          "(same hex spacers in the side panels)",
        "splice_plates": f"{8 * (tiers - 1)}x M3x10 + {8 * (tiers - 1)}x M3x10 hex spacer (glued in the cheeks)",
        "stretchers": f"{2 * n_str}x M3x14 + {2 * n_str}x M3x10 hex spacer (glued in the stretcher ends)",
    }
    (rnd / f"stand-{tiers}-report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


main()
