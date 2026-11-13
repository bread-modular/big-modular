"""Slide-in cover with hook slots and a clip-on patch cable holder for the 42 HP / 60 mm skiff.

Build only this add-on: mechanical/case/tools/build_cable_holder.sh.
Original case, cover, stand and joiner exports are never overwritten.

The panel is the standard 2 mm slide-in cover blank (build_case.cover_plates) with four hook
slots and stiffening ribs on its INNER face only. Its outer face stays one flat plane, 2.2 mm
behind the frame edge like every other cover, so nothing stands out of the case with the holder
off. It is symmetric along X and goes in either groove.

The holder is a separate comb for patch cables, hooked into two neighbouring slots, no screws:
two flat tongues go through the cover at an angle, a heel under the comb lies on the cover's
outer face, and a rigid barb under each tongue sits behind the cover below the slot. A load on
the comb wedges the tongues between the slot's lower outer and upper inner edges. To take it
off, lift the comb tip until the barbs clear the slot, then pull: the comb's back end is cut
square at the slot's lower edge, so nothing above the slot stops that turn.

The slot angle follows from the case tilt: the comb rises RISE degrees above level, so the
plugs slide towards the case, not off the tips. One holder per tilt:
  joiner-60  upper case of the 60 degree angle joiner (build_angle_joiner.py), back cover up
  stand-40   row 2 of the tiered stand (build_stand.py, 40 degrees), back cover up
All holders fit the same panel; only the tongue thickness and heel change.

Profile frame, for a back cover: n = distance out of the cover's outer face, z = assembly Z.
Holder frame: X along the case, s along the comb plate (0 at the slot's lower outer edge A,
positive out of the case), t across it (0 = tongue underside, up to the comb's top face).
The holder prints with its top face on the bed, the panel with its outer face on the bed.

CAD-checked prototype: the fits are not printed or measured.
"""
import hashlib
import heapq
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
import build_middle_frame as common
import build_angle_joiner as joiner
import FreeCAD as App
import Mesh
import MeshPart
import numpy as np
import Part
import shapely
from shapely.geometry import Polygon, box as rect

V = App.Vector
CASE = base.CASE
OUT = CASE/'print'/'cable-holder'
RESEARCH = CASE/'research'/'cable-holder'
TOL = 1e-3

RISE = 8.0            # comb above level, tip up
REF_TILT = 60.0       # the slot height makes this tilt's tongue as thick as the comb
VARIANTS = {'joiner-60': 60.0, 'stand-40': 40.0}

# panel
SLOT_PITCH = 54.0     # four slots; a holder takes two neighbours: left, centre or right
SLOT_Z = 13.0         # slot lower edge (seat edge A), assembly Z
SLOT_CLR_Z = 0.3      # slot height over the tongue
SLOT_CLR_X = 0.3      # each side of the tongue
TONGUE_W = 16.0
RIB_H = 3.0           # inner face only
RIB_W = 3.0
RIB_GAP = 1.2         # slot edge to the ribs beside it
RIB_Z = (6.5, 46.5)   # clear of the bottom plate top and the rail underside
LINTEL_GAP = 2.0      # slot top to the rib above it

# holder
WIDTH = 100.0         # clear of the bottom plate socket walls at both case ends
PLATE_T = 5.0
COMB_LEN = 50.0       # comb tip, along the plate from A
CABLE_SLOT = 5.0      # patch cable slot width
CABLE_PITCH = 10.5
CABLE_SLOTS = 9
SLOT_END = 24.0       # centre of a cable slot's round closed end
TIP_R = 2.0
HEEL_Z = 5.6          # heel bottom, 0.6 mm over the bottom plate edge
TONGUE_PAST = 1.5     # tongue end past the slot's upper inner edge
TONGUE_ROOT = 2.0     # tongue prism overlap into the body
END_CHAMFER = (1.0, 0.6)  # tongue end: underside, top
BARB_CLR = 0.3        # barb root behind the cover's inner face
BARB_OVERLAP = 1.0    # barb tip below the slot's lower inner edge
BARB_BACK = 1.5       # barb root length on the tongue
FUSE = 0.5            # overlap of prisms that are fused
GRID = 1e-6           # 2D booleans snap to this: GEOS mishandles the profile's collinear edges otherwise

# motion search in the profile plane
STEP = 0.1            # mm
STEP_DEG = 1.0
SHRINK = 0.02         # so a seat contact is not a collision
LAYER = 0.2


def bounds(shape):
    b = shape.optimalBoundingBox(False, False)
    return [round(v, 4) for v in (b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax)]


def solid(shape, label):
    s = shape.removeSplitter()
    if not s.isValid():
        s.fix(1e-7, 1e-7, 1e-3)
    assert s.isValid() and len(s.Solids) == 1, f'{label}: invalid or not one solid'
    return s.Solids[0]


def slot_h(d):
    """Slot height without clearance: the REF_TILT tongue is exactly PLATE_T thick."""
    b = math.radians(90 - REF_TILT + RISE)
    return (PLATE_T + d.cover_t*math.cos(b))/math.sin(b)


def slot_x(d):
    return [d.L/2 + (k - 1.5)*SLOT_PITCH for k in range(4)]


class Seat:
    """Holder profile for one case tilt."""

    def __init__(self, d, tilt):
        self.tilt = tilt
        self.beta = 90 - tilt + RISE                     # comb plate to the cover plane
        b = math.radians(self.beta)
        self.sin, self.cos = math.sin(b), math.cos(b)
        t = d.cover_t
        self.ht = slot_h(d)*self.sin - t*self.cos        # tongue: edge A to the upper inner edge
        self.tu = self.ht - PLATE_T                      # comb underside
        self.s_b = (t + self.ht*self.cos)/self.sin       # tongue top on the upper inner edge
        self.s_e = self.s_b + TONGUE_PAST
        self.face = max(self.beta, 45.0)                 # barb hook face to the tongue: <= 45 deg overhang
        g = math.radians(self.face)
        self.s0 = (t + BARB_CLR)/self.sin
        self.barb = (BARB_OVERLAP + self.s0*self.cos)/(self.sin + self.cos/math.tan(g))
        self.barb_tip = -self.s0 + self.barb/math.tan(g)

    def st(self, n, dz):
        return n*self.sin - dz*self.cos, n*self.cos + dz*self.sin

    def nz(self, s, t):
        return s*self.sin + t*self.cos, -s*self.cos + t*self.sin

    def profiles(self):
        """(body, hook) polygons in (s, t): the full-width comb + heel, and a tongue + barb."""
        zh = HEEL_Z - SLOT_Z
        plate = rect(0, self.tu, COMB_LEN, self.ht)
        top = self.tu + FUSE
        heel = Polygon([self.st(0, zh), self.st((top - zh*self.sin)/self.cos, zh), self.st(0, top/self.sin)])
        outside = Polygon([self.st(0, -300), self.st(300, -300), self.st(300, 300), self.st(0, 300)])
        # nothing behind the cover's outer face, and nothing above A behind the plane s = 0: the
        # comb's back end is square, so the holder can turn about A to bring the barbs out
        body = common2(common2(union2([plate, heel]), outside), rect(0, -300, 300, 300))
        lo, hi = END_CHAMFER
        tongue = Polygon([(-self.s_e, lo), (-self.s_e + lo, 0), (TONGUE_ROOT, 0), (TONGUE_ROOT, self.ht),
                          (-self.s_e + hi, self.ht), (-self.s_e, self.ht - hi)])
        back = -self.s0 - BARB_BACK
        assert back > -self.s_e + lo + 0.5, 'barb runs into the tongue end chamfer'
        barb = Polygon([(-self.s0, 0), (self.barb_tip, -self.barb), (back, -self.barb), (back, FUSE), (-self.s0, FUSE)])
        hook = union2([tongue, barb])
        body, hook = outline(body), outline(hook)
        heel_s = max(s for s, _ in heel.exterior.coords)
        assert heel_s < SLOT_END - CABLE_SLOT/2 - 1, 'heel under the cable slots'
        return body, hook


def union2(shapes):
    return shapely.union_all(shapes, grid_size=GRID)


def common2(a, b):
    return shapely.intersection(a, b, grid_size=GRID)


def outline(shape):
    """The one polygon of a 2D boolean result, without the zero-area leftovers of touching edges."""
    parts = [p for p in getattr(shape, 'geoms', [shape]) if p.geom_type == 'Polygon' and p.area > 1e-9]
    assert len(parts) == 1 and not parts[0].interiors, 'profile is not one outline'
    return parts[0].simplify(GRID)


def prism(poly, x0, length):
    return common.yz_prism(list(poly.exterior.coords)[:-1], x0, length)


def cable_x():
    return [(k - (CABLE_SLOTS - 1)/2)*CABLE_PITCH for k in range(CABLE_SLOTS)]


def holder(g):
    """Holder in its own frame (X, s, t)."""
    body, hook = g.profiles()
    s = prism(body, -WIDTH/2, WIDTH)
    s = s.fuse([prism(hook, x - TONGUE_W/2, TONGUE_W) for x in (-SLOT_PITCH/2, SLOT_PITCH/2)])
    s = solid(s, 'holder body')
    cuts = []
    for x in cable_x():
        cuts += [base.box((x - CABLE_SLOT/2, SLOT_END, g.tu - 1), (CABLE_SLOT, COMB_LEN - SLOT_END + 1, PLATE_T + 2)),
                 base.cyl(CABLE_SLOT/2, PLATE_T + 2, (x, SLOT_END, g.tu - 1))]
    s = base.cut_all(s, cuts)
    tips = [e for e in s.Edges if len(e.Vertexes) == 2 and e.BoundBox.XLength < 1e-6
            and e.BoundBox.YLength < 1e-6 and abs(e.BoundBox.YMin - COMB_LEN) < 1e-6]
    assert len(tips) == 2*(CABLE_SLOTS + 1), len(tips)
    return solid(s.makeFillet(TIP_R, tips), 'holder')


def on_back_cover(d, g, shape, x):
    """Holder frame -> case frame, seated on the back cover with its centre at X = x."""
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(1, 0, 0), g.beta - 90)        # (s, t) -> (n, z)
    s.translate(V(x, d.groove_y[1] + (d.groove_w + d.cover_t)/2, SLOT_Z))
    return s


def print_pose(shape):
    """Top face (t = ht) on the bed."""
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    b = s.BoundBox
    s.translate(V(-b.XMin, -b.YMin, -b.ZMin))
    return s


def rib_boxes(d):
    """Inner-face ribs as (x0, x1, z0, z1) in assembly coordinates."""
    half = TONGUE_W/2 + SLOT_CLR_X + RIB_GAP
    xs = slot_x(d)
    ribs = [(x + sgn*half - (RIB_W if sgn < 0 else 0), x + sgn*half + (RIB_W if sgn > 0 else 0), *RIB_Z)
            for x in xs for sgn in (-1, 1)]
    x0, x1 = xs[0] - half - RIB_W, xs[-1] + half + RIB_W
    lintel = SLOT_Z + slot_h(d) + SLOT_CLR_Z + LINTEL_GAP
    return ribs + [(x0, x1, lintel, lintel + RIB_W), (x0, x1, RIB_Z[1] - RIB_W, RIB_Z[1])]


def panel(d):
    """Cover in print pose: outer face on the bed, ribs up."""
    c = d.cover_blank_size()
    w, t, h = c['plate']
    nx, nz = c['bottom_corner_notches_x_z']
    blank = base.box((0, 0, 0), (w, h, t)).cut(Part.makeCompound(
        [base.box((-1, -1, -1), (nx + 1, nz + 1, t + 2)), base.box((w - nx, -1, -1), (nx + 1, nz + 1, t + 2))]))
    ref = base.cover_blank(d, 1)
    placed = base.cover_in_assembly(d, blank, 1)
    assert placed.cut(ref).Volume + ref.cut(placed).Volume < TOL, 'cover blank differs from build_case'
    ear, z0 = d.groove_d - d.cover_clr, d.cover_z0
    sw = TONGUE_W + 2*SLOT_CLR_X
    ribs = [base.box((a + ear, c0 - z0, t - FUSE), (b - a, c1 - c0, RIB_H + FUSE)) for a, b, c0, c1 in rib_boxes(d)]
    slots = [base.box((x + ear - sw/2, SLOT_Z - z0, -1), (sw, slot_h(d) + SLOT_CLR_Z, t + RIB_H + 2)) for x in slot_x(d)]
    assert all(r.common(s).Volume < TOL for r in ribs for s in slots), 'rib across a slot'
    return solid(blank.fuse(ribs).cut(Part.makeCompound(slots)), 'panel'), blank


def panel_in_assembly(d, s, i):
    """The back groove takes the print pose as build_case does; the front one takes the same
    part turned round (the panel is symmetric along X, so that is a mirror in Y)."""
    a = base.cover_in_assembly(d, s, i)
    if i == 0:
        a = a.mirror(V(0, d.groove_y[0] + d.groove_w/2, 0), V(0, 1, 0))
    return a


def obstacles(d):
    """Profile-plane obstacles (n, z) on a slot's centre line and beside the slots."""
    y_out = d.groove_y[1] + (d.groove_w + d.cover_t)/2
    frame = d.y0 + d.ylen - y_out                        # frame edge over the cover's outer face
    t = d.cover_t
    zt = SLOT_Z + slot_h(d) + SLOT_CLR_Z
    case = [rect(-90, 0, frame, d.P), rect(frame - d.rail_w, d.top - d.rail_h, frame, d.top)]
    ribs = [rect(-t - RIB_H, z0, -t, z1) for x0, x1, z0, z1 in rib_boxes(d) if x1 - x0 > 2*RIB_W]
    slotted = union2(case + ribs + [rect(-t, d.cover_z0, 0, SLOT_Z), rect(-t, zt, 0, d.cover_z1)])
    plain = union2(case + [rect(-t - RIB_H, d.cover_z0, 0, d.cover_z1)])
    return slotted, plain, frame


class Motion:
    """Rigid moves of the holder profile in the cover's profile plane: turn about X, shift in n
    and z. A pose is free when the tongue section misses the slotted cover and the comb + heel
    section misses the plain cover. Poses on a STEP / STEP_DEG grid, seated pose = (0, 0, 0)."""

    def __init__(self, d, g):
        self.g = g
        body, hook = g.profiles()
        self.section = np.array(outline(union2([body, hook])).buffer(-SHRINK).exterior.coords)
        self.body = np.array(body.buffer(-SHRINK).exterior.coords)
        self.slotted, self.plain, self.frame = obstacles(d)
        shapely.prepare(self.slotted)
        shapely.prepare(self.plain)
        self.cache = {}

    def pose(self, pts, k):
        a = math.radians(self.g.beta + k[0]*STEP_DEG)
        s, c = math.sin(a), math.cos(a)
        return np.column_stack((k[1]*STEP + pts[:, 0]*s + pts[:, 1]*c, SLOT_Z + k[2]*STEP - pts[:, 0]*c + pts[:, 1]*s))

    def look(self, k):
        """(free, lowest n of the pose)"""
        if k not in self.cache:
            sec = self.pose(self.section, k)
            free = not (self.slotted.intersects(Polygon(sec)) or self.plain.intersects(Polygon(self.pose(self.body, k))))
            self.cache[k] = (free, float(sec[:, 0].min()))
        return self.cache[k]

    def escape(self, lift):
        """Best-first search from the seat to a pose wholly outside the frame, turning the comb
        tip at most `lift` steps up. Returns the path, or None if the holder is held."""
        start = (0, 0, 0)
        assert self.look(start)[0], 'seated pose collides'
        parent, heap = {start: None}, [(-self.look(start)[1], start)]
        while heap:
            _, k = heapq.heappop(heap)
            if self.look(k)[1] > self.frame + 1.0:
                path = []
                while k is not None:
                    path.append(k)
                    k = parent[k]
                return path[::-1]
            for axis in range(3):
                for step in (-1, 1):
                    q = list(k)
                    q[axis] += step
                    q = tuple(q)
                    if q in parent or not -3 <= q[0] <= lift or abs(q[1]) > 600 or abs(q[2]) > 200:
                        continue
                    parent[q] = k
                    free, low = self.look(q)
                    if free:
                        heapq.heappush(heap, (-low, q))
        return None

    def report(self, d):
        seat_low = self.look((0, 0, 0))[1]
        release = next(n for n in range(0, 91) if self.escape(n) is not None)
        assert release >= 10, 'holder comes off without a clear lift of the comb tip'
        path = self.escape(release + 10)                 # a comfortable move, not the tightest one
        low = min(self.look(k)[1] for k in path)
        return {'held_without_lifting_the_tip': True,
                'tip_lift_to_release_deg': release*STEP_DEG,
                'insertion_path_poses': len(path),
                'insertion_path_max_tip_lift_deg': max(k[0] for k in path)*STEP_DEG,
                'seated_reach_behind_inner_face_mm': round(-seat_low - d.cover_t - SHRINK, 2),
                'insertion_reach_behind_inner_face_mm': round(-low - d.cover_t - SHRINK, 2),
                'grid_mm_deg': [STEP, STEP_DEG]}


def overhangs(posed):
    """Downward faces of the print pose, from the mesh: bed contact and anything past 45 deg."""
    mesh = MeshPart.meshFromShape(Shape=posed, LinearDeflection=0.01, AngularDeflection=0.1)
    bed = steep = 0.0
    worst = 0.0
    for f in mesh.Facets:
        nz = f.Normal.z
        if nz > -1e-6:
            continue
        zmin = min(p[2] for p in f.Points)
        zmax = max(p[2] for p in f.Points)
        if zmax < 1e-6:
            bed += f.Area
            continue
        angle = math.degrees(math.asin(min(1.0, -nz)))   # 0 = vertical wall, 90 = flat ceiling
        worst = max(worst, angle)
        if angle > 45.0 + 1e-3:
            steep += f.Area
        assert zmin > -1e-6
    assert steep < 1e-6, f'overhang past 45 deg: {steep:.3f} mm2'
    return {'bed_contact_mm2': round(bed, 1), 'worst_overhang_from_vertical_deg': round(worst, 2),
            'area_past_45_deg_mm2': 0, 'supports_required': False}


def export_part(shape, path):
    b = bounds(shape)
    dims = [round(b[i + 1] - b[i], 3) for i in (0, 2, 4)]
    assert max(dims) <= base.BED - 4, (path.name, 'bed', dims)
    assert abs(b[0]) < 1e-6 and abs(b[2]) < 1e-6 and abs(b[4]) < 1e-6, (path.name, 'origin', b)
    result = base.export(shape, path)
    for ext in ('.stl', '.3mf'):
        m = Mesh.Mesh(str(path.with_suffix(ext)))
        assert m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections(), path.name + ext
        assert abs(m.Volume - shape.Volume)/shape.Volume < 0.002, path.name + ext + ' volume'
        assert abs(m.BoundBox.ZMin) < 1e-5, 'mesh does not touch the print bed'
    saved = Part.Shape()
    saved.read(str(path.with_suffix('.step')))
    assert saved.isValid() and len(saved.Solids) == 1, path.name + ' STEP readback'
    assert saved.cut(shape).Volume + shape.cut(saved).Volume < TOL
    return {'print_bounds_mm': dims, 'solid_volume_cm3': round(shape.Volume/1000, 2),
            'STEP_STL_3MF_readback': 'PASS', **result}


def save_native(path, objects):
    doc = App.newDocument(path.stem.replace('-', '_'))
    for name, shape in objects.items():
        obj = doc.addObject('Part::Feature', name.replace('-', '_'))
        obj.Shape = shape
        obj.Label = name.replace('_', ' ').replace('-', ' ').title()
        for prop, value in (('SlotPitch', SLOT_PITCH), ('SlotLowerEdgeZ', SLOT_Z), ('TongueWidth', TONGUE_W),
                            ('CombRiseDegrees', RISE), ('CableSlotWidth', CABLE_SLOT)):
            obj.addProperty('App::PropertyFloat', prop, 'Build metadata')
            setattr(obj, prop, value)
            obj.setEditorMode(prop, 1)
        obj.addProperty('App::PropertyString', 'Regenerate', 'Build metadata')
        obj.Regenerate = 'mechanical/case/tools/build_cable_holder.sh; dimensions in build_cable_holder.py'
    doc.recompute()
    tmp = path.with_name('.' + path.name)
    doc.saveAs(str(tmp))
    App.closeDocument(doc.Name)
    check = App.openDocument(str(tmp))
    for name, expected in objects.items():
        got = check.getObject(name.replace('-', '_')).Shape
        assert got.isValid() and len(got.Solids) == 1, name + ' FCStd reload'
        assert got.cut(expected).Volume + expected.cut(got).Volume < TOL
    App.closeDocument(check.Name)
    tmp.replace(path)


def saved_solids(name):
    """Solids of a saved assembly, in its own frame, and the objects' placements. Compounds are
    split (`name.k`): OCC booleans against a compound of solids can come back empty."""
    doc = App.openDocument(str(CASE/'cad'/name))
    shapes, places = {}, {}
    for o in doc.Objects:
        solids = o.Shape.copy().Solids
        shapes.update({o.Name if len(solids) == 1 else f'{o.Name}.{k}': s for k, s in enumerate(solids)})
        places[o.Name] = o.Placement
    App.closeDocument(doc.Name)
    return shapes, places


def clear_of(shape, others, label):
    """No shared volume with any saved solid; returns the closest one."""
    box_ = shape.BoundBox
    near = (None, 1e9)
    for name, other in others.items():
        b = other.BoundBox
        if not box_.intersect(b):
            continue
        common.no_collision(shape, other, f'{label} / {name}')
        gap = shape.distToShape(other)[0]
        if gap < near[1]:
            near = (name, gap)
    return {'collisions': 0, 'closest': near[0], 'closest_gap_mm': None if near[0] is None else round(near[1], 3)}


def cable_drop(g, place, world, x_centre):
    """A 4 mm cable hanging straight down from three cable slots' closed ends: free length to the
    first thing below (table = world Z 0) and clearance to everything over the first 60 mm."""
    free, gap = [], []
    for x in (cable_x()[0], 0.0, cable_x()[-1]):
        top = place(Part.Vertex(V(x, SLOT_END, g.tu))).Vertexes[0].Point
        rope = Part.makeCylinder(2.0, top.z, V(top.x, top.y, 0), V(0, 0, 1))
        first = Part.makeCylinder(2.0, 60.0, V(top.x, top.y, top.z - 60.0), V(0, 0, 1))
        floor, near = 0.0, 1e9
        for other in world.values():
            if not rope.BoundBox.intersect(other.BoundBox):
                near = min(near, first.distToShape(other)[0]) if first.BoundBox.ZMin < other.BoundBox.ZMax + 10 else near
                continue
            hit = rope.common(other)
            if hit.Volume > TOL:
                floor = max(floor, hit.BoundBox.ZMax)
            near = min(near, first.distToShape(other)[0])
        free.append(round(top.z - floor, 1))
        gap.append(round(near, 2))
    assert min(gap) >= 5.0, f'cable too close to the case under the comb: {gap}'
    return {'holder_centre_x_mm': round(x_centre, 2), 'free_hang_mm': min(free),
            'clearance_over_first_60_mm': min(gap)}


def in_scene(d, g, hold, pan, world, place, label):
    """Panel + holders (left and right, then centre) on a tilted case's back cover."""
    out = {}
    p = place(panel_in_assembly(d, pan, 1))
    out['panel'] = clear_of(p, world, f'{label} panel')
    placed = {'panel': p}
    xs = slot_x(d)
    drops = []
    for name, x in (('holder_left', (xs[0] + xs[1])/2), ('holder_right', (xs[2] + xs[3])/2),
                    ('holder_centre', (xs[1] + xs[2])/2)):
        put = lambda s, x=x: place(on_back_cover(d, g, s, x))
        h = put(hold)
        out[name] = clear_of(h, world, f'{label} {name}')
        common.no_collision(h, p, f'{label} {name} / panel')
        assert h.distToShape(p)[0] < 1e-6, f'{label} {name} is not seated on the panel'
        placed[name] = h
        drops.append(cable_drop(g, put, {**world, 'panel': p}, x))
        tip = put(Part.makeLine(V(0, 0, g.ht), V(0, COMB_LEN, g.ht))).Vertexes
        rise = math.degrees(math.asin((tip[1].Point.z - tip[0].Point.z)/COMB_LEN))
        assert abs(rise - RISE) < 1e-6, f'{label}: comb rise {rise}'
    common.no_collision(placed['holder_left'], placed['holder_right'], f'{label} two holders')
    out['two_holders_gap_mm'] = round(placed['holder_left'].distToShape(placed['holder_right'])[0], 3)
    out['comb_rise_above_level_deg'] = RISE
    out['cables'] = drops
    return out, placed


def main():
    d = base.Dims(42, 60, 0.5, base.module_panels())
    source, differences = common.source_parts(d)
    for folder in (OUT, RESEARCH, CASE/'cad'):
        folder.mkdir(parents=True, exist_ok=True)
    pan, blank = panel(d)
    seats = {name: Seat(d, tilt) for name, tilt in VARIANTS.items()}
    holders = {name: holder(g) for name, g in seats.items()}
    xs = slot_x(d)
    checks = {}

    # panel: a cover blank plus inner ribs, flat outer face, symmetric, clear in both grooves
    c = d.cover_blank_size()
    w, t, h = c['plate']
    b = bounds(pan)
    assert b == [0, w, 0, h, 0, t + RIB_H], b
    flat = pan.common(base.box((-1, -1, -1), (w + 2, h + 2, t + 1)))
    assert flat.cut(blank).Volume < TOL, 'panel outside the cover blank'
    mirrored = pan.mirror(V(w/2, 0, 0), V(1, 0, 0))
    assert pan.cut(mirrored).Volume + mirrored.cut(pan).Volume < TOL, 'panel is not symmetric along X'
    y_out = d.groove_y[1] + (d.groove_w + d.cover_t)/2
    grooves = {}
    for i, name in enumerate(('front', 'back')):
        a = panel_in_assembly(d, pan, i)
        for part, shape in source.items():
            common.no_collision(a, shape, f'panel in the {name} groove / {part}')
        ab = bounds(a)
        behind = (ab[2] - d.y0) if i == 0 else (d.y0 + d.ylen - ab[3])
        grooves[name] = {'collisions': 0, 'outer_face_behind_frame_edge_mm': round(behind, 3),
                         'reach_behind_inner_face_mm': round(ab[3] - ab[2] - t, 3)}
        assert abs(behind - (d.y0 + d.ylen - y_out)) < 1e-6
        # it slides in from the open bottom like any cover: side panels and rails only
        for k in range(1, 23):
            low = common.moved(a, dz=-2.5*k)
            for part in ('side_panel_left', 'side_panel_right', 'rail_front', 'rail_back'):
                common.no_collision(low, source[part], f'panel sliding into the {name} groove / {part}')
    lintel = SLOT_Z + slot_h(d) + SLOT_CLR_Z
    checks['panel'] = {'grooves': grooves, 'slides_in_from_the_bottom': 'PASS', 'symmetric_along_x': True,
                       'outer_face': 'one flat plane, slots only',
                       'rib_top_below_rail_underside_mm': round(d.top - d.rail_h - RIB_Z[1], 2),
                       'rib_bottom_above_plate_top_mm': round(RIB_Z[0] - d.P, 2),
                       'slot_top_to_lintel_rib_mm': LINTEL_GAP,
                       'slot_top_z_mm': round(lintel, 3)}

    # holders: seated on a level case's back cover at the three positions
    centres = {'left': (xs[0] + xs[1])/2, 'centre': (xs[1] + xs[2])/2, 'right': (xs[2] + xs[3])/2}
    back = panel_in_assembly(d, pan, 1)
    case_asm = {}
    for name, g in seats.items():
        hold = holders[name]
        seat = {}
        for pos, x in centres.items():
            s = on_back_cover(d, g, hold, x)
            common.no_collision(s, back, f'{name} {pos} / panel')
            for part, shape in source.items():
                common.no_collision(s, shape, f'{name} {pos} / {part}')
            sb = bounds(s)
            assert sb[0] > 0 and sb[1] < d.L, f'{name} {pos} does not fit between the side panels'
            seat[pos] = {'collisions': 0, 'to_side_panels_mm': [round(sb[0], 2), round(d.L - sb[1], 2)],
                         'reach_behind_inner_face_mm': round(y_out - d.cover_t - sb[2], 2),
                         'bottom_above_plate_top_mm': round(HEEL_Z - d.P, 2)}
            if name == 'joiner-60' and pos != 'centre':
                case_asm[f'holder_{pos}'] = s
        motion = Motion(d, g).report(d)
        checks[name] = {'case_tilt_deg': g.tilt, 'comb_to_cover_deg': g.beta,
                        'tongue_thickness_mm': round(g.ht, 3), 'comb_thickness_mm': PLATE_T,
                        'tongue_in_slot_clearance_mm': {'x_each_side': SLOT_CLR_X, 'z': SLOT_CLR_Z},
                        'barb': {'height_mm': round(g.barb, 2), 'hook_face_to_tongue_deg': g.face,
                                 'below_slot_edge_mm': BARB_OVERLAP, 'behind_inner_face_mm': BARB_CLR},
                        'seated': seat, 'profile_motion': motion,
                        'print': overhangs(print_pose(hold))}
    checks['panel']['print'] = overhangs(pan)

    # angle joiner: upper case at 60 deg, its back cover is the one facing up
    layout = joiner.Layout(d)
    world, _ = saved_solids('angle-joiner-assembly.FCStd')
    ref = layout.place(source['rail_back'], True)
    assert ref.cut(world['upper_rail_back']).Volume + world['upper_rail_back'].cut(ref).Volume < TOL
    assert joiner.ANGLE == VARIANTS['joiner-60']
    checks['joiner-60']['on_angle_joiner'], on_joiner = in_scene(
        d, seats['joiner-60'], holders['joiner-60'], pan, world, lambda s: layout.place(s, True), 'angle joiner')
    rear = max(s.BoundBox.YMax for n, s in world.items() if n.startswith('joiner'))
    checks['joiner-60']['on_angle_joiner']['comb_tip_past_rear_feet_mm'] = round(
        on_joiner['holder_left'].BoundBox.YMax - rear, 1)

    # tiered stand: row 2 at 40 deg
    stand, places = saved_solids('stand-2.FCStd')
    row = places['case_2']
    assert abs(row.Rotation.Angle - math.radians(VARIANTS['stand-40'])) < 1e-9 and abs(row.Rotation.Axis.x - 1) < 1e-9

    def on_row(s):
        r = s.copy()
        r.Placement = row.multiply(r.Placement)
        return r

    ref = on_row(source['rail_back'])
    # the stand's case is the STEP preview plus screw heads: same rail to 0.1 %
    same = max(ref.common(s).Volume for n, s in stand.items() if n.startswith('case_2.'))
    assert same > 0.999*ref.Volume, 'stand row 2 is not the case at this placement'
    checks['stand-40']['on_stand_row_2'], on_stand = in_scene(
        d, seats['stand-40'], holders['stand-40'], pan, stand, on_row, 'stand')

    # outputs
    posed = {'cable-holder-panel': pan, **{f'cable-holder-{n}': print_pose(s) for n, s in holders.items()}}
    exports = {name: export_part(shape, OUT/name) for name, shape in posed.items()}
    save_native(CASE/'cad'/'cable-holder-parts.FCStd', posed)
    save_native(CASE/'cad'/'cable-holder-assembly.FCStd', {**source, 'cable_holder_panel': back, **case_asm})

    # preview meshes (ignored research folder)
    def stl(shape, name):
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2).write(str(RESEARCH/name))

    for old in RESEARCH.glob('*.stl'):
        old.unlink()
    for name, shape in {**world, **on_joiner}.items():
        stl(shape, f'joiner-{name}.stl')
    for name, shape in {**stand, **on_stand}.items():
        stl(shape, f'stand-{name}.stl')
    tongue_x = xs[0]
    for name, shape in {**{n: s for n, s in world.items() if n in ('upper_bottom_plate', 'upper_rail_back')},
                        'panel': on_joiner['panel'], 'holder_left': on_joiner['holder_left']}.items():
        stl(shape.common(base.box((tongue_x, -500, -500), (60, 1500, 1500))), f'section-{name}.stl')
    a = layout.place(Part.Vertex(V(d.L/2, y_out, SLOT_Z)), True).Vertexes[0].Point
    sa = on_row(Part.Vertex(V(d.L/2, y_out, SLOT_Z))).Vertexes[0].Point
    (RESEARCH/'camera.json').write_text(json.dumps({
        'seat': [a.x, a.y, a.z], 'stand_seat': [sa.x, sa.y, sa.z], 'tongue_x': tongue_x,
        'left_x': centres['left'], 'panel': [w, h]}, indent=1) + '\n')

    tools = ['tools/build_cable_holder.py', 'tools/build_cable_holder.sh', 'tools/build_case.py',
             'tools/build_middle_frame.py', 'tools/build_angle_joiner.py']
    sources = ['cad/assembly.FCStd', 'cad/angle-joiner-assembly.FCStd', 'cad/stand-2.FCStd']
    sha = lambda rel: hashlib.sha256((CASE/rel).read_bytes()).hexdigest()
    report = {
        'status': 'PASS',
        'prototype': 'CAD-checked only: not printed, fits not measured',
        'source': 'cad/assembly.FCStd', 'source_difference_mm3': differences,
        'dimensions': {
            'panel_mm': [w, h, t], 'panel_with_ribs_mm': [w, h, t + RIB_H],
            'slots': {'count': 4, 'pitch_mm': SLOT_PITCH, 'centres_x_mm': [round(x, 3) for x in xs],
                      'width_mm': TONGUE_W + 2*SLOT_CLR_X, 'height_mm': round(slot_h(d) + SLOT_CLR_Z, 3),
                      'lower_edge_z_mm': SLOT_Z},
            'ribs_mm': {'height': RIB_H, 'width': RIB_W},
            'holder': {'width_mm': WIDTH, 'comb_tip_from_slot_edge_mm': COMB_LEN,
                       'cable_slots': CABLE_SLOTS, 'cable_slot_width_mm': CABLE_SLOT,
                       'cable_slot_pitch_mm': CABLE_PITCH, 'cable_slot_length_mm': COMB_LEN - SLOT_END + CABLE_SLOT/2,
                       'tongues': 2, 'tongue_width_mm': TONGUE_W, 'tongue_pitch_mm': SLOT_PITCH,
                       'positions_centre_x_mm': {k: round(v, 3) for k, v in centres.items()}}},
        'checks': checks, 'print': exports,
        'source_sha256': {rel: sha(rel) for rel in tools + sources},
        'export_sha256': {f'print/cable-holder/{name}{ext}': sha(f'print/cable-holder/{name}{ext}')
                          for name in posed for ext in ('.step', '.stl', '.3mf')},
        'limits': ['not printed or fit-tested', 'profile motion search is a 2D grid search, not a tolerance study',
                   'no load test; cables only']}
    data = json.dumps(report, indent=2) + '\n'
    (OUT/'verification.json').write_text(data)
    (RESEARCH/'build-report.json').write_text(data)
    print('CABLE_HOLDER_BUILD_PASS', flush=True)


# FreeCADCmd imports scripts by stem, unlike CPython's __main__.
if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
