"""Carrier and shared print/CAD helpers. Its upper end tabs slide into the two desk clips.
Hanger frame: top of the tabs Z=0; +X into the desk, Y along its edge.
"""
import math
import os
from pathlib import Path
import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
HOLDER = Path(os.environ.get('HOLDER_DIR', Path(__file__).resolve().parents[1]))
OUT = HOLDER/'print'
CAD = HOLDER/'cad'
BED = 256.0           # Bambu Lab P2S
FZ = 1e-4             # fuzzy tolerance: OCC booleans on the helical thread faces fail without it
WIDTH = 240.0
FLANGE_T = 6.0        # slides into the clip shelves
PLUG_ROOM = 58.0      # flange to the comb: a 45 mm plug + lifting it out of its seat
COMB_T = 6.0          # at the tooth tips
ROOT_T = 10.0         # at the back wall: the teeth print standing, layers across them
FRONT = 3.0           # tooth tips behind the desk edge
WALL_X, WALL_T = 57.0, 5.0            # back wall
GUSSET = 5.0          # 45 degree corners inside the C
STRIP = 24.0          # flange depth on the wings, wall included
SLOT_W = 5.0          # cables up to about 4.5 mm
SLOTS = 16
OUTER_SLOT = 110.5    # keep the end grooves clear of the clips
SEAT_X = (14.5, 25.0, 35.5, 46.0)     # plug seats, from the desk edge inwards
SEAT_D = 9.5          # cone mouth on the top face, 45 degrees down to the slot
MOUTH = 6.0           # the slot widens over this length at the tooth tips: found by feel
MOUTH_W = 10.0
PLUG_L = 50.0         # plug envelope above its seat in the checks
CABLE_D = 5.0                           # thickest cable assumed in the clearance check
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
    pitch = 2 * OUTER_SLOT / (SLOTS - 1)
    return [-OUTER_SLOT + i * pitch for i in range(SLOTS)]


def hanger():
    """Clip tab top at z = 0, desk edge at x = 0. A C that is open to the front: flange, back wall, comb."""
    w, g = WIDTH/2, GUSSET
    tip = COMB_TOP - COMB_T
    # the comb's underside runs from the tooth tips to the foot of the wall: thicker at the root
    prof = [(BACK - STRIP, 0), (BACK, 0), (BACK, BOTTOM), (WALL_X, BOTTOM), (FRONT, tip), (FRONT, COMB_TOP),
            (WALL_X - g, COMB_TOP), (WALL_X, COMB_TOP + g), (WALL_X, -FLANGE_T - g), (WALL_X - g, -FLANGE_T),
            (BACK - STRIP, -FLANGE_T)]
    body = prism_xz(prof, -w, w)
    # Only the two end tabs need the full C section; a low return stiffens
    # the comb between them. Sloping shoulders widen the roots of the posts.
    cut_yz = [(-98, 1), (98, 1), (98, -16), (85, COMB_TOP + 12),
              (-85, COMB_TOP + 12), (-98, -16)]
    loop = [V(FRONT-1, y, z) for y,z in cut_yz + cut_yz[:1]]
    body = body.cut(Part.Face(Part.makePolygon(loop)).extrude(V(BACK-FRONT+2, 0, 0)))
    low, high = BOTTOM - 1, COMB_TOP + 1
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
    return one(body, 'hanger')


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
