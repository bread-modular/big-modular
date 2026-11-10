"""One-piece top brace tying all four rails across the existing middle frame.

It goes on AFTER the modules: its whole underside is one flat plane on the
module faces, which is also the level of the frame's top and 1HP lip. The four
screw tabs lie on the module panels, match the rail width with no overhang and
are one source-panel thickness; their screws pass through the panel holes.
Three M3 holes per rail use the ACTUAL saved rail's 2 HP phase, not a new grid.
Only the frame's four proud socket collars rise above that plane: each crossbar
bridges its collar between two solid shoulders, with filleted pocket corners
and room around the collar. The spine between the rails lies flat on the frame
and climbs to each crossbar over a 45 degree web.
Each tab meets its crossbar through a solid filleted shoulder that wraps the
first screw head, instead of the earlier 1.6 mm return wall that snapped off.
Print it as it sits, flat on the bed: no supports, only bridges.
Only the new top-brace print set/native documents are written. Not load-rated.
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
import build_middle_frame as middle
import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = base.CASE
OUT = CASE/'print'/'side panels'/'middle-frame'/'top-brace'
RESEARCH = CASE/'research'/'middle-brace'
TOL = 1e-3
REACH_HP = 6
OUTER_R = 3.0
INNER_R = 8.0        # flare where the spine runs into each crossbar
END_MARGIN = 5.0     # tab end past its last hole centre: half the rail width
# Room around each proud collar. The pocket roof is a bridge, so it gets space
# to sag; the side gap leaves the collar's square corner clear of POCKET_R.
SIDE_GAP = 1.2
ROOF_GAP = 0.6
POCKET_R = 2.0       # concave fillet, shoulder wall to pocket roof
# The roof past the rail starts this much higher than the crossbar's own, so
# the crossbar bridge is already there for it to bridge from.
BRIDGE_STEP = 0.4
WEB_GAP = 1.0        # web foot past the nominal end of the frame's slope
WEB_R = 2.0          # rounds where the 45 degree web meets roof and spine
# Spine between the rails. Its 1.6 mm section only has to carry what the 10 mm
# screw arms can feed it: 16 mm is 25.6 mm2, above the two arms' net section at
# their holes (2 x 10.6 mm2). An estimate, not a tested rating.
SPINE_W = 16.0
EDGE_R = 0.6         # round on the spine's long top edges
# Frame top silhouette, as build_middle_frame.frame() draws it. The built brace
# is measured against the SAVED frame, so a changed frame fails the build.
COLLAR_INNER = 3.0   # collar flat past the rail's inner edge
COLLAR_BLEND = 6.0   # slope from the collar down to the module-face plane
SHOULDER = 13.0      # solid shoulder end, measured from the frame's own face
SHOULDER_BASE_R = 1.5  # concave fillet, shoulder to tab top
SHOULDER_TOP_R = 1.0   # round on the shoulder's top edge
SCREW_L = 8.0        # through the tab and a module panel
HEAD_D = 5.5
HEAD_H = 3.0
SPACER_AF = 5.5
HEAD_RELIEF_D = 6.4
LAYER = 0.2          # print-section sampling pitch


def bbox(shape):
    b = shape.optimalBoundingBox(False, False)
    return [round(v, 6) for v in (b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax)]


def valid(shape, name):
    assert shape.isValid() and len(shape.Solids) == 1, name


def difference(a, b):
    return a.cut(b).Volume + b.cut(a).Volume


class Layout:
    def __init__(self, d, j):
        self.t = d.panel_t  # exact source-panel thickness, not a new guessed value
        # One flat underside on the module faces; the frame top and its lip are
        # on that plane too. Only the collars stand above it.
        self.z0 = d.case_top
        self.mount_z = self.z0 + self.t
        self.roof_a = j.collar_top + ROOF_GAP
        self.roof_b = self.roof_a + BRIDGE_STEP
        self.z1 = self.roof_b + self.t
        self.frame_cx = d.L + j.width/2
        # Screw arms follow the actual rail edges, not the wider frame collars.
        # No added front/back margin and no extension past the rail strip.
        self.tab_width = d.rail_w
        self.y0 = d.rail_y[0]
        self.y1 = d.rail_y[1] + self.tab_width
        self.front_inner = d.rail_y[0] + self.tab_width
        self.back_inner = d.rail_y[1]
        assert abs(self.y0-d.y0) < 1e-8 and abs(self.y1-d.y0-d.ylen) < 1e-8
        assert self.t >= 1.2, 'source faceplate is too thin for this prototype'
        self.holes = []
        for side, offset, indices in (('left',0,range(d.n_sockets-REACH_HP//2,d.n_sockets)),
                                      ('right',j.offset,range(REACH_HP//2))):
            for rail_i, y in enumerate(d.hole_y):
                for k in indices:
                    self.holes.append({'case':side, 'rail':'front' if rail_i == 0 else 'back',
                                       'rail_socket_index':k, 'x':offset+d.module_hole_x()[k], 'y':y,
                                       'case_local_x':d.module_hole_x()[k]})
        assert len(self.holes) == 12
        # The tabs lie on the panels, so they need not stop at a slot boundary:
        # every end hole gets the same plastic around it as beside it.
        assert abs(END_MARGIN-self.tab_width/2) < 1e-8
        self.x0 = min(h['x'] for h in self.holes) - END_MARGIN
        self.x1 = max(h['x'] for h in self.holes) + END_MARGIN
        assert self.x1-self.x0 < 2*(REACH_HP+1)*base.HP + j.width + d.fill
        # The shoulders stand on the module faces either side of the collar;
        # the right-hand ones start on the frame's 1HP lip, which has no collar.
        self.left_wall_x1 = d.L - SIDE_GAP
        self.lip_x0 = j.offset + SIDE_GAP
        self.shoulder_x0 = d.L - SHOULDER
        self.shoulder_x1 = j.offset + SHOULDER
        assert self.lip_x0+1.0 < j.offset+d.fill
        # The collar's square top corner stays clear of the pocket fillet.
        self.pocket_corner = POCKET_R - math.hypot(POCKET_R-SIDE_GAP,POCKET_R-ROOF_GAP)
        assert self.pocket_corner >= 0.3, 'pocket fillet too close to the collar corner'
        # The spine is centred over the frame and its lip; so are its flares.
        self.cx = (d.L + j.offset + d.fill)/2
        self.web_x0 = self.cx - SPINE_W/2
        self.web_x1 = self.cx + SPINE_W/2
        assert d.L < self.web_x0-INNER_R and self.web_x1+INNER_R < j.offset+d.fill
        assert self.web_x1 < j.offset
        assert SPINE_W*self.t >= 2*(self.tab_width-base.M3_CLEAR)*self.t, 'spine weaker than the arms'
        # 45 degree web from the spine up to the roof: its foot lands just past
        # the frame's slope, its top where it reaches the roof height.
        rise = self.roof_b - self.z0
        reach = d.rail_w + COLLAR_INNER + COLLAR_BLEND + WEB_GAP
        self.web_foot = (self.y0+reach, self.y1-reach)
        self.web_top = (self.web_foot[0]-rise, self.web_foot[1]+rise)
        self.web_shift = self.t*(math.sqrt(2)-1)  # top face one thickness off the underside
        assert self.web_top[0]-WEB_R*math.tan(math.pi/8) > self.front_inner+1.0
        assert (WEB_R+self.t+WEB_R)*math.tan(math.pi/8) < (self.z1-self.mount_z)*math.sqrt(2)
        self.bridge_b = self.web_top[0]-WEB_R*math.tan(math.pi/8)-self.front_inner
        # Each shoulder holds the first screw in a walled pocket and its base
        # fillet runs out before the second screw's head.
        for side, edge, wall in (('left',self.shoulder_x0,self.left_wall_x1),
                                 ('right',self.shoulder_x1,self.lip_x0)):
            xs = sorted((abs(h['x']-edge),h['x']) for h in self.holes if h['case'] == side)
            first = [x for _,x in xs if (x > edge) == (side == 'left')]
            second = [x for _,x in xs if (x > edge) != (side == 'left')]
            self.pocket_rim = min(abs(x-edge) for x in first)-HEAD_RELIEF_D/2-SHOULDER_TOP_R
            assert self.pocket_rim >= 1.0, 'pocket rim too thin at the shoulder top'
            assert min(abs(x-edge) for x in second)-HEAD_RELIEF_D/2 > SHOULDER_BASE_R
            self.pocket_wall = min(abs(x-wall) for x in first)-HEAD_RELIEF_D/2
            assert self.pocket_wall >= 2.0, 'screw pocket too close to the collar pocket'
        assert SHOULDER_BASE_R+SHOULDER_TOP_R < self.z1-self.mount_z


def yz_solid(points, x0, length, rounds=()):
    """Y/Z outline extruded along X, with the named corners rounded."""
    solid = middle.yz_prism(points,x0,length)
    if solid.Volume < 0:
        solid.reverse()
    for (y,z), radius in rounds:
        edges = [e for e in middle.x_edges(solid)
                 if abs(e.CenterOfMass.y-y) < 1e-6 and abs(e.CenterOfMass.z-z) < 1e-6]
        assert len(edges) == 1, (y,z)
        solid = solid.makeFillet(radius,edges)
    valid(solid,'Y/Z profile')
    return solid


def silhouette(p):
    # The rounded H in plan, independent of the shell's height.
    height = p.z1-p.z0
    outline = base.box((p.x0,p.y0,p.z0), (p.x1-p.x0,p.front_inner-p.y0,height))
    outline = outline.fuse(base.box((p.x0,p.back_inner,p.z0),
                                   (p.x1-p.x0,p.y1-p.back_inner,height)))
    outline = outline.fuse(base.box((p.web_x0,p.y0,p.z0),
                                   (p.web_x1-p.web_x0,p.y1-p.y0,height))).removeSplitter()
    def vertical(e):
        b = e.BoundBox
        return b.XLength < 1e-6 and b.YLength < 1e-6 and b.ZLength > height-0.01
    def inner(e):
        c = e.CenterOfMass
        return min(abs(c.x-p.web_x0),abs(c.x-p.web_x1)) < 1e-6 and min(abs(c.y-p.front_inner),abs(c.y-p.back_inner)) < 1e-6
    outline = outline.makeFillet(INNER_R, [e for e in outline.Edges if vertical(e) and inner(e)])
    outside = [e for e in outline.Edges if vertical(e) and
               min(abs(e.CenterOfMass.x-p.x0),abs(e.CenterOfMass.x-p.x1)) < 1e-6]
    assert len(outside) == 8
    return outline.makeFillet(OUTER_R, outside)


def rows(p, z, height):
    """The two rail strips, front and back."""
    front = base.box((p.x0-1,p.y0,z), (p.x1-p.x0+2,p.front_inner-p.y0,height))
    return front.fuse(base.box((p.x0-1,p.back_inner,z), (p.x1-p.x0+2,p.y1-p.back_inner,height)))


def brace(d, j, p):
    height = p.z1-p.z0
    outline = silhouette(p)

    # Crossbars: panel-thick tabs, solid shoulders and the roof over the collar.
    # Each tab and its shoulder is one stepped X/Z profile: concave fillet at
    # the tab, round on top.
    def arm(tab_x, step_x, inner_x):
        pts = [V(tab_x,p.y0,p.z0), V(inner_x,p.y0,p.z0), V(inner_x,p.y0,p.z1),
               V(step_x,p.y0,p.z1), V(step_x,p.y0,p.mount_z), V(tab_x,p.y0,p.mount_z)]
        solid = Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,p.y1-p.y0,0))
        if solid.Volume < 0:
            solid.reverse()
        def along_y(e, z):
            b = e.BoundBox
            return (b.XLength < 1e-6 and b.ZLength < 1e-6 and b.YLength > 1
                    and abs(b.XMin-step_x) < 1e-6 and abs(b.ZMin-z) < 1e-6)
        for z, radius in ((p.mount_z,SHOULDER_BASE_R),(p.z1,SHOULDER_TOP_R)):
            edges = [e for e in solid.Edges if along_y(e,z)]
            assert len(edges) == 1
            solid = solid.makeFillet(radius,edges)
        valid(solid,'screw arm profile')
        return solid
    bars = [arm(p.x0,p.shoulder_x0,p.left_wall_x1+1),
            arm(p.x1,p.shoulder_x1,p.lip_x0-1),
            base.box((p.left_wall_x1,p.y0,p.z0), (p.lip_x0-p.left_wall_x1,p.y1-p.y0,height))]
    # The collar pocket is open to the bed and at both ends; its two upper
    # corners are filleted, so the roof springs from the shoulders as an arch.
    pocket = base.box((p.left_wall_x1,p.y0-1,p.z0-5), (p.lip_x0-p.left_wall_x1,p.y1-p.y0+2,p.roof_a-p.z0+5))
    crown = [e for e in pocket.Edges if e.BoundBox.YLength > 1 and e.BoundBox.XLength < 1e-6
             and abs(e.BoundBox.ZMin-p.roof_a) < 1e-6]
    assert len(crown) == 2
    pocket = pocket.makeFillet(POCKET_R,crown)
    crossbars = bars[0].multiFuse(bars[1:]).cut(pocket).common(rows(p,p.z0,height))

    # Spine: flat on the frame between the rails, up a 45 degree web at each
    # end to a roof over the rest of the collar and its slope. `under` is the
    # room below it, `over` everything below its top face.
    ya, yb, low = p.y0-1, p.y1+1, p.z0-5
    (foot_f,foot_b), (top_f,top_b), a = p.web_foot, p.web_top, p.web_shift
    under = yz_solid([(ya,low),(yb,low),(yb,p.roof_b),(top_b,p.roof_b),(foot_b,p.z0),
                      (foot_f,p.z0),(top_f,p.roof_b),(ya,p.roof_b)], p.x0-1, p.x1-p.x0+2,
                     [((y,p.roof_b),WEB_R) for y in (top_f,top_b)])
    over = yz_solid([(ya,low),(yb,low),(yb,p.z1),(top_b-a,p.z1),(foot_b-a,p.mount_z),
                     (foot_f+a,p.mount_z),(top_f+a,p.z1),(ya,p.z1)], p.x0-1, p.x1-p.x0+2,
                    [((y,p.z1),WEB_R+p.t) for y in (top_f+a,top_b-a)]
                    + [((y,p.mount_z),WEB_R) for y in (foot_f+a,foot_b-a)])
    spine = over.cut(under).common(base.box((p.x0-1,p.front_inner,p.z0),
                                            (p.x1-p.x0+2,p.back_inner-p.front_inner,height)))
    shape = crossbars.fuse(spine).common(outline).removeSplitter()
    valid(shape,'brace before rounding')

    # Round the spine's long top edges. The fillet runs on along the tangent
    # top edges of the flares, crossbars and shoulders; the tab slab is put
    # back square, so every screw tab stays exactly panel-thick.
    def spine_top_edge(e):
        b = e.BoundBox
        if not (b.XLength < 1e-6 and b.YLength > 1e-3
                and min(abs(b.XMin-p.web_x0),abs(b.XMin-p.web_x1)) < 1e-6
                and p.front_inner+INNER_R-1e-6 < b.YMin and b.YMax < p.back_inner-INNER_R+1e-6):
            return False
        m = e.valueAt((e.FirstParameter+e.LastParameter)/2)
        inward = 0.05 if abs(b.XMin-p.web_x0) < 1e-6 else -0.05
        return not shape.isInside(V(m.x+inward,m.y,m.z+0.05),1e-6,True)
    edges = [e for e in shape.Edges if spine_top_edge(e)]
    assert len(edges) >= 10 and len(edges) % 2 == 0, len(edges)
    square = shape.common(rows(p,p.z0,p.t))
    rounded = shape.makeFillet(EDGE_R,edges).fuse(square).removeSplitter()
    valid(rounded,'brace')
    assert 0 < shape.Volume-rounded.Volume < 60
    return rounded


def finish(p, shape):
    height = p.z1-p.z0
    cuts = []
    for hole in p.holes:
        x,y = hole['x'],hole['y']
        cuts.append(base.cyl(base.M3_CLEAR/2,height+2,(x,y,p.z0-1)))
        # The first screw on each side sits inside the shoulder: pocket only
        # the elevated material so the head/tool is clear and its mounting tab
        # remains exactly panel-thick. This is NOT a countersink in the thin tab.
        cuts.append(base.cyl(HEAD_RELIEF_D/2,height+2,(x,y,p.mount_z)))
    return base.cut_all(shape,cuts)


def sources(d, j):
    source, differences = middle.source_parts(d)
    document = App.openDocument(str(CASE/'cad'/'middle-frame.FCStd'))
    frame = document.getObject('middle_frame').Shape.copy()
    App.closeDocument(document.Name)
    valid(frame,'saved middle frame')
    differences['middle_frame'] = difference(frame,middle.frame(d,j))
    assert differences['middle_frame'] < TOL, 'saved middle frame differs; inspect before building'
    asm = middle.assembly(d,j,frame,source)
    document = App.openDocument(str(CASE/'cad'/'double-case-assembly.FCStd'))
    saved_names = {o.Name for o in document.Objects if hasattr(o,'Shape')}
    assert saved_names == set(asm), 'existing joined assembly contains unexpected parts'
    for name, expected in asm.items():
        differences['assembly/'+name] = difference(document.getObject(name).Shape,expected)
        assert differences['assembly/'+name] < TOL, name+' changed in saved assembly'
    App.closeDocument(document.Name)
    return asm,differences


def hardware(d,p):
    fasteners = {}
    spacer_top = d.top-(base.SPACER_SOCKET_DEPTH-base.SPACER_L)
    for i,h in enumerate(p.holes,1):
        x,y = h['x'],h['y']
        shaft = base.cyl(1.5,SCREW_L,(x,y,p.mount_z-SCREW_L))
        head = base.cyl(HEAD_D/2,HEAD_H,(x,y,p.mount_z))
        fasteners[f'screw_{i:02d}'] = shaft.fuse(head).removeSplitter()
        r = SPACER_AF/math.sqrt(3)
        points = [V(x+r*math.cos(math.radians(60*k)),y+r*math.sin(math.radians(60*k)),
                    spacer_top-base.SPACER_L) for k in range(7)]
        spacer = Part.Face(Part.makePolygon(points)).extrude(V(0,0,base.SPACER_L))
        # Envelope only: bore has thread clearance, not a claimed thread model.
        fasteners[f'spacer_{i:02d}'] = spacer.cut(base.cyl(base.M3_CLEAR/2,base.SPACER_L+2,
                                                        (x,y,spacer_top-base.SPACER_L-1))).removeSplitter()
    return fasteners,spacer_top-(p.mount_z-SCREW_L)


def verify(d,j,p,s,asm,fasteners,engagement):
    valid(s,'brace')
    checks = {'native_valid_single_solid':True}
    collisions = {}
    for name,part in asm.items():
        collisions[name] = middle.no_collision(s,part,'brace/'+name)
    checks['brace_interference_mm3'] = collisions
    height = p.z1-p.z0
    # One flat underside: every downward face on the bed lies in the
    # module-face plane, and nothing reaches below it.
    sb = bbox(s)
    assert abs(sb[4]-d.case_top) < 1e-6 and abs(sb[5]-p.z1) < 1e-6, sb
    bottom = [f for f in s.Faces if abs(f.BoundBox.ZMin-p.z0) < 1e-6 and abs(f.BoundBox.ZMax-p.z0) < 1e-6]
    assert len(bottom) == 5, ('four rail seats and the spine expected',len(bottom))
    flat = sum(f.Area for f in bottom)
    checks['flat_underside'] = {'plane_above_rail_top_mm':round(p.z0-d.top,6),
                                'plane_above_module_faces_mm':round(p.z0-d.case_top,6),
                                'faces':len(bottom),'area_mm2':round(flat,1)}
    # It rests on the SAVED frame's flat top and lip, and keeps clear of the
    # only thing above that plane: the four socket collars and their slopes.
    frame = asm['middle_frame']
    assert s.distToShape(frame)[0] < 1e-6, 'brace does not rest on the frame'
    tops = [f for f in frame.Faces if abs(f.BoundBox.ZMin-d.case_top) < 1e-6 and abs(f.BoundBox.ZMax-d.case_top) < 1e-6]
    seat = sum(a.common(b).Area for a in bottom for b in tops)
    assert seat > 1400, ('too little bearing on the frame',seat)
    checks['bearing_area_on_frame_top_and_lip_mm2'] = round(seat,1)
    proud = frame.common(base.box((d.L-10,p.y0-20,d.case_top+0.01),(j.width+d.fill+20,p.y1-p.y0+40,20)))
    assert len(proud.Solids) == 2 and abs(bbox(proud)[5]-j.collar_top) < 1e-6
    gap = s.distToShape(proud)[0]
    assert 0.35 <= gap <= ROOF_GAP+1e-6, gap
    checks['collar_pockets'] = {'closest_clearance_to_collar_mm':round(gap,3),
                                'clearance_above_collar_top_mm':ROOF_GAP,
                                'clearance_beside_collar_mm':SIDE_GAP,
                                'corner_fillet_mm':POCKET_R,
                                'span_between_shoulders_mm':round(p.lip_x0-p.left_wall_x1,3),
                                'web_foot_past_collar_slope_mm':WEB_GAP}
    # Measure each screw arm, from its tip to the spine's corner flare, against
    # the saved rail's XY envelope. Hex socket openings are intentionally
    # excluded from this footprint check.
    footprints = {}
    for side, x0, x1 in (('left',p.x0,p.web_x0-INNER_R),
                        ('right',p.web_x1+INNER_R,p.x1)):
        for rail in ('front','back'):
            name = f'{side}_rail_{rail}'
            rb = bbox(asm[name])
            y0,y1 = (p.y0-1,base.PANEL_H/2) if rail=='front' else (base.PANEL_H/2,p.y1+1)
            wing = s.common(base.box((x0,y0,p.z0-1), (x1-x0,y1-y0,height+2)))
            valid(wing,name+' screw arm')
            wb = bbox(wing)
            rail_envelope = base.box((rb[0],rb[2],p.z0-1),
                                     (rb[1]-rb[0],rb[3]-rb[2],height+2))
            overhang = wing.cut(rail_envelope).Volume
            assert overhang < TOL, (name,'screw arm overhangs rail',overhang)
            assert abs(wb[2]-rb[2]) < 1e-6 and abs(wb[3]-rb[3]) < 1e-6, (name,wb,rb)
            assert abs(wb[3]-wb[2]-d.rail_w) < 1e-6, name+' screw arm width'
            xs = sorted(h['x'] for h in p.holes if h['case']==side and h['rail']==rail)
            assert len(xs) == 3 and all(abs(b-a-2*base.HP)<1e-6 for a,b in zip(xs,xs[1:]))
            footprints[name] = {'rail_y_bounds_mm':rb[2:4], 'screw_arm_y_bounds_mm':wb[2:4],
                                'rail_width_mm':round(rb[3]-rb[2],6),
                                'screw_arm_width_mm':round(wb[3]-wb[2],6),
                                'outside_rail_footprint_mm3':round(overhang,9)}
    checks['screw_arms_within_saved_rail_footprints'] = footprints
    checks['hole_count'] = len(p.holes)
    checks['holes_per_rail'] = 3
    checks['hole_pitch_mm'] = 2*base.HP
    # Read actual screw-head bearing solids: every mounting zone must be exactly
    # the source faceplate thickness, lying on the module-face plane.
    tab_checks = []
    for h in p.holes:
        region = base.cyl(HEAD_D/2,height+2,(h['x'],h['y'],p.z0-1))
        bearing = s.common(region)
        bb = bbox(bearing)
        assert abs(bb[4]-d.case_top) < 1e-6 and abs(bb[5]-p.mount_z) < 1e-6, ('tab not on the faces',h,bb)
        assert abs(bb[5]-bb[4]-d.panel_t) < 1e-6, ('tab thickness mismatch',h,bb)
        bearing_area = bearing.Volume/p.t
        assert bearing_area > 12, ('insufficient screw-head bearing area',h,bearing_area)
        # Same plastic all round every hole, the end ones included.
        ring = base.cyl(base.M3_CLEAR/2+END_MARGIN-base.M3_CLEAR/2-1e-3,p.t,(h['x'],h['y'],p.z0))
        ring = ring.cut(base.cyl(base.M3_CLEAR/2,p.t+2,(h['x'],h['y'],p.z0-1)))
        assert abs(s.common(ring).Volume-ring.Volume) < TOL, ('thin ligament',h)
        tab_checks.append({'case':h['case'],'rail':h['rail'],'x_mm':round(h['x'],3),
                           'thickness_mm':round(bb[5]-bb[4],6),
                           'underside_above_module_face_mm':round(bb[4]-d.case_top,6),
                           'head_bearing_area_mm2':round(bearing_area,4)})
    checks['panel_thick_screw_tabs_on_module_faces'] = tab_checks
    checks['minimum_hole_edge_ligament_mm'] = round(END_MARGIN-base.M3_CLEAR/2,3)
    # Skin thickness, read from the solid: collar roof, stepped roof, spine.
    skins = {}
    for name,(x,y),low,top in (('roof_over_collar',(p.frame_cx,d.hole_y[0]),p.roof_a,p.z1),
                               ('roof_over_collar_back',(p.frame_cx,d.hole_y[1]),p.roof_a,p.z1),
                               ('stepped_roof',(p.cx,p.front_inner+2.5),p.roof_b,p.z1),
                               ('stepped_roof_back',(p.cx,p.back_inner-2.5),p.roof_b,p.z1),
                               ('spine',(p.cx,base.PANEL_H/2),p.z0,p.mount_z)):
        column = s.common(base.box((x-2,y-1,p.z0-1),(4,2,height+2)))
        cb = bbox(column)
        assert abs(cb[4]-low) < 1e-6 and abs(cb[5]-top) < 1e-6, (name,cb)
        assert abs(column.Volume-4*2*(top-low)) < TOL, name+' is not solid'
        assert top-low >= p.t-1e-9
        skins[name] = round(top-low,6)
    checks['skin_thickness_mm'] = skins
    # The spine between the flares: its real width and section, and nothing
    # else between the two crossbars.
    spine = s.common(base.box((p.x0-1,base.PANEL_H/2-0.5,p.z0-1),(p.x1-p.x0+2,1,height+2)))
    sb = bbox(spine)
    assert abs(sb[0]-p.web_x0) < 1e-6 and abs(sb[1]-p.web_x1) < 1e-6, sb
    assert abs(sb[4]-p.z0) < 1e-6 and abs(sb[5]-p.mount_z) < 1e-6, sb
    arms_net = 2*(p.tab_width-base.M3_CLEAR)*p.t
    assert SPINE_W*p.t-0.5 < spine.Volume <= SPINE_W*p.t+1e-6 and spine.Volume > arms_net
    between = s.common(base.box((p.x0-1,p.front_inner+INNER_R,p.z0-1),
                                (p.x1-p.x0+2,p.back_inner-p.front_inner-2*INNER_R,height+2)))
    bb = bbox(between)
    assert abs(bb[0]-p.web_x0) < 1e-6 and abs(bb[1]-p.web_x1) < 1e-6, bb
    checks['spine'] = {'width_mm':round(sb[1]-sb[0],6),'section_mm2':round(spine.Volume,3),
                       'two_screw_arms_net_section_at_holes_mm2':round(arms_net,3),
                       'flare_radius_mm':INNER_R,'top_edge_round_mm':EDGE_R,
                       'flat_on_frame_between_y_mm':[round(v,3) for v in p.web_foot],
                       'web_angle_deg':45,
                       'length_between_crossbars_mm':round(p.back_inner-p.front_inner,3)}
    # Shoulders: the plastic joining each tab to the raised roof, cut just above
    # the tab top.
    shoulders = {}
    side_wall = (d.rail_w-HEAD_RELIEF_D)/2
    for side, x0, x1 in (('left',p.shoulder_x0,p.left_wall_x1),
                        ('right',p.lip_x0,p.shoulder_x1)):
        first = (max if side == 'left' else min)(h['x'] for h in p.holes if h['case'] == side)
        for rail, ry in zip(('front','back'),d.rail_y):
            cut = s.common(base.box((x0,ry,p.mount_z+0.05),(x1-x0,d.rail_w,0.001)))
            area = cut.Volume/0.001
            assert area > 45, (side,rail,'weak shoulder',area)
            # Solid pocket walls on both rail edges, the full shoulder height.
            for y in (ry+side_wall/2,ry+d.rail_w-side_wall/2):
                for z in (p.mount_z+0.2,p.z1-0.2):
                    assert s.isInside(V(first,y,z),1e-6,True), (side,rail,'pocket wall missing')
            shoulders[f'{side}_{rail}'] = round(area,3)
    checks['shoulder_section_above_tab_mm2'] = shoulders
    checks['screw_pocket_side_wall_mm'] = round(side_wall,3)
    checks['screw_pocket_rim_at_shoulder_top_mm'] = round(p.pocket_rim,3)
    checks['screw_pocket_to_collar_pocket_wall_mm'] = round(p.pocket_wall,3)
    # Full circular gauges through all mounting holes, plus actual insert fit.
    for i,h in enumerate(p.holes,1):
        x,y = h['x'],h['y']
        gauge = base.cyl(base.M3_CLEAR/2-1e-4,height+2,(x,y,p.z0-1))
        middle.no_collision(s,gauge,'through-hole gauge')
        nominal = h['case_local_x']
        assert abs(x-(nominal+(j.offset if h['case']=='right' else 0))) < 1e-6
        assert abs(nominal-d.module_hole_x()[h['rail_socket_index']]) < 1e-6
        for tag in (f'screw_{i:02d}',f'spacer_{i:02d}'):
            valid(fasteners[tag],tag)
            middle.no_collision(fasteners[tag],s,tag+'/brace')
            for name,part in asm.items():
                middle.no_collision(fasteners[tag],part,tag+'/'+name)
        middle.no_collision(fasteners[f'screw_{i:02d}'],fasteners[f'spacer_{i:02d}'],'screw/spacer envelopes')
        # Screwdriver above the head is clear of every structural part.
        access = base.cyl(3.0,20,(x,y,p.mount_z+HEAD_H))
        for name,part in {**asm,'brace':s}.items():
            middle.no_collision(access,part,'tool access/'+name)
    assert 3.5 <= engagement <= base.SPACER_L-2, engagement
    assert HEAD_H <= p.z1-p.mount_z, 'screw heads stand above the brace'
    checks['nominal_thread_engagement_mm'] = round(engagement,3)
    checks['screw_tip_clearance_to_spacer_bottom_mm'] = round(base.SPACER_L-engagement,3)
    checks['screw_head_below_brace_top_mm'] = round(p.z1-p.mount_z-HEAD_H,3)
    checks['fastener_envelopes_and_top_tool_access'] = 'PASS; threads are not modelled'
    # Nothing undercuts on a vertical installation path: sample the lowering
    # path against the saved frame, rails and all bases.
    for lift in (0.1,0.5,2,4,8,20):
        raised = middle.moved(s,dz=lift)
        for name,part in asm.items():
            middle.no_collision(raised,part,'lowering path/'+name)
    checks['vertical_installation_lift_samples_mm'] = [0,0.1,0.5,2,4,8,20]
    covers = 0
    for offset in (0,j.offset):
        for rail in (0,1):
            middle.no_collision(s,middle.moved(base.cover_blank(d,rail),dx=offset),'stock cover')
            covers += 1
    checks['stock_covers_clear'] = covers
    # The brace goes on top of the installed modules: every real panel, at
    # every slot it can take, lies under the flat underside. No HP is reserved.
    panels = 0
    for side,offset in (('left',0),('right',j.offset)):
        for name,info in d.panels.items():
            for slot in range(0,d.hp,2):
                x = d.row_x0+slot*base.HP
                if x+info['width'] > d.L+1e-6:
                    continue
                if offset+x > p.x1 or offset+x+info['width'] < p.x0:
                    continue
                panel = base.box((offset+x,0,d.top),(info['width'],info['height'],info['thickness']))
                assert abs(d.top+info['thickness']-p.z0) < 1e-6, name+' face is off the underside plane'
                middle.no_collision(panel,s,'module under the brace/'+name)
                panels += 1
    assert panels > 0
    checks['module_panel_envelopes_under_brace_checked'] = panels
    checks['reserved_hp_each_case'] = 0
    # A brace screw can only go where the panel under it has a rail hole. For
    # the module that sits against the frame, list the brace holes its own
    # holes land on: every source panel gives at least one per rail.
    def on_brace(side, xs):
        return sorted({round(h['x'],3) for h in p.holes for x in xs
                       if h['case'] == side and abs(h['x']-x) < 0.05})
    aligned = {}
    for name,info in d.panels.items():
        width_hp = round(info['width']/base.HP)
        left = on_brace('left',[d.row_x0+(d.hp-width_hp)*base.HP+x for x in info['holes_x']])
        right = on_brace('right',[j.offset+d.row_x0+x for x in info['holes_x']])
        assert left and right, (name,'no brace hole over this panel')
        aligned[name] = {'width_hp':width_hp,'last_module_of_left_case_x_mm':left,
                         'first_module_of_right_case_x_mm':right}
    checks['brace_holes_over_the_module_next_to_the_frame'] = aligned
    checks['all_twelve_holes_usable_with'] = 'three 2HP panels next to the frame on each case'
    two_hp = [info for info in d.panels.values() if round(info['width']/base.HP) == 2]
    assert two_hp
    for info in two_hp:
        assert len(info['holes_x']) == 1
        xs = [d.row_x0+(d.hp-2*k)*base.HP+info['hole_x'] for k in (1,2,3)]
        assert len(on_brace('left',xs)) == 3
        xs = [j.offset+d.row_x0+2*k*base.HP+info['hole_x'] for k in (0,1,2)]
        assert len(on_brace('right',xs)) == 3
    # Measure actual layer sections rather than claiming what needs support.
    # Printed as installed, flat underside on the bed. Material that starts
    # over air may only be: the collar-pocket fillets and roof, bridged
    # between the two shoulders; and the 45 degree web with the stepped roof,
    # bridged from the already printed crossbar roof to the web.
    posed = print_pose(s)
    origin = bbox(s)
    def to_bed(shape):
        return middle.moved(shape,dx=-origin[0],dy=-origin[2],dz=-origin[4])
    layers = int(round(height/LAYER))
    assert abs(layers*LAYER-height) < 1e-9
    def layer(i):
        # Unit-thick prism of one layer section: sturdier than paper-thin cuts.
        z = (i+0.5)*LAYER
        prism = Part.makeFace(posed.slice(V(0,0,1),z),'Part::FaceMakerBullseye').extrude(V(0,0,1))
        prism.translate(V(0,0,-z))
        return prism
    sections = [layer(i) for i in range(layers)]
    strips = to_bed(rows(p,p.z0-1,height+2))
    pocket = to_bed(base.box((p.left_wall_x1-1e-4,p.y0-1,p.z0-1),
                             (p.lip_x0-p.left_wall_x1+2e-4,p.y1-p.y0+2,height+2))).common(strips)
    webs = [to_bed(base.box((p.x0-1,ya,p.z0-1),(p.x1-p.x0+2,yb-ya,height+2)))
            for ya,yb in ((p.front_inner,p.web_foot[0]+1e-4),(p.web_foot[1]-1e-4,p.back_inner))]
    web_zone = webs[0].fuse(webs[1])
    stray, pocket_area, web_area = 0.0, 0.0, 0.0
    pocket_span, web_reach = {}, {}
    for i,(a,b) in enumerate(zip(sections,sections[1:]),1):
        over = b.cut(a)
        if not over.Solids:
            continue
        in_pocket, in_web = over.common(pocket), over.common(web_zone)
        pocket_area += in_pocket.Volume
        web_area += in_web.Volume
        stray += over.Volume-in_pocket.Volume-in_web.Volume
        if in_pocket.Volume > 1e-6:
            # widest unsupported step in X of this layer, front crossbar
            pocket_span[i] = max(bbox(solid)[1]-bbox(solid)[0] for solid in in_pocket.Solids)
        front = over.common(webs[0])
        if front.Volume > 1e-6:
            web_reach[i] = bbox(front)[3]-bbox(front)[2]
    assert stray < 0.01, ('material outside the pockets and webs starts over air',stray)
    # Layer indices: first layer wholly above each roof.
    roof_a_layer = int(round((p.roof_a-p.z0)/LAYER))
    roof_b_layer = int(round((p.roof_b-p.z0)/LAYER))
    assert abs(roof_a_layer*LAYER-(p.roof_a-p.z0)) < 1e-9 and abs(roof_b_layer*LAYER-(p.roof_b-p.z0)) < 1e-9
    assert max(pocket_span) == roof_a_layer and max(web_reach) == roof_b_layer
    bridge_a, bridge_b = pocket_span[roof_a_layer], web_reach[roof_b_layer]
    assert bridge_a < p.lip_x0-p.left_wall_x1 and bridge_b < 7.0, (bridge_a,bridge_b)
    # Both ends of each bridge already stand on plastic one layer below.
    below_a, below_b = (roof_a_layer-0.5)*LAYER, (roof_b_layer-0.5)*LAYER
    for y in d.hole_y:
        for x in (p.left_wall_x1-0.5,p.lip_x0+0.5):
            assert posed.isInside(V(x-origin[0],y-origin[2],below_a),1e-6,True), 'pocket bridge has no shoulder under its end'
    for ya,yb in ((p.front_inner-0.5,p.front_inner+bridge_b+0.3),(p.back_inner+0.5,p.back_inner-bridge_b-0.3)):
        for x in (p.cx-SPINE_W/2+1,p.cx,p.cx+SPINE_W/2-1):
            assert posed.isInside(V(x-origin[0],ya-origin[2],below_b),1e-6,True), 'stepped roof has no crossbar roof under its edge'
            assert posed.isInside(V(x-origin[0],yb-origin[2],below_b),1e-6,True), 'stepped roof has no web under its edge'
    # Below its top fillet the web advances one layer height per layer: 45 deg.
    fillet_h = WEB_R*(1-math.cos(math.pi/4))
    straight = [v for i,v in web_reach.items() if (i+1)*LAYER < p.roof_b-p.z0-fillet_h-1e-9]
    assert straight and max(straight) < LAYER+0.02, max(straight)
    # First section is cut at half a layer: the two webs have advanced that far.
    bed = sections[0].Volume
    assert abs(bed-flat-SPINE_W*LAYER) < 0.5, (bed,flat)
    # Outside the collar pockets the rail strips rise straight from the bed.
    seats = strips.cut(pocket)
    tab_slab = posed.common(seats.common(to_bed(rows(p,p.z0,p.t))))
    assert abs(tab_slab.Volume-sections[0].common(seats).Volume*p.t) < 10*TOL, 'screw tabs must rise straight from the bed'
    checks['print'] = {'orientation':'as installed: flat underside on the bed',
                       'supports_required':False,
                       'layer_height_assumed_mm':LAYER,
                       'bed_contact_mm2':round(flat,1),
                       'material_starting_over_air_elsewhere_mm2':round(stray,4),
                       'collar_pocket_bridge':{'count':2,'span_mm':round(bridge_a,2),'width_mm':p.tab_width,
                                               'height_above_bed_mm':round(p.roof_a-p.z0,3),
                                               'anchored_on':'both shoulders'},
                       'stepped_roof_bridge':{'count':2,'span_mm':round(bridge_b,2),
                                              'height_above_bed_mm':round(p.roof_b-p.z0,3),
                                              'anchored_on':'crossbar roof (two layers earlier) and web'},
                       'web_overhang_deg_from_vertical':45,
                       'web_advance_per_layer_mm':round(max(straight),3),
                       'overhang_area_in_pockets_mm2':round(pocket_area,1),
                       'overhang_area_in_webs_mm2':round(web_area,1),
                       'status':'geometry only; not printed'}
    return checks


def print_pose(shape):
    # As installed: flat underside on the bed, raised roof up.
    s = shape.copy()
    b=bbox(s)
    s.translate(V(-b[0],-b[2],-b[4]))
    return s


def export_part(s,path):
    posed=print_pose(s)
    valid(posed,path.name)
    dims=middle.size(posed)
    assert all(x < base.BED-4 for x in dims)
    info=base.export(posed,path)
    for ext in ('.stl','.3mf'):
        m=Mesh.Mesh(str(path.with_suffix(ext)))
        assert m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections(),ext
        assert abs(m.Volume-posed.Volume)/posed.Volume < 0.002
        b=m.BoundBox
        assert max(abs(b.XMin),abs(b.YMin),abs(b.ZMin)) < 1e-5
    saved=Part.Shape()
    saved.read(str(path.with_suffix('.step')))
    valid(saved,'STEP readback')
    assert difference(saved,posed) < TOL
    return {'print_bounds_mm':dims,'native_volume_cm3':round(posed.Volume/1000,3),
            'STEP_STL_3MF_readback':'PASS',**info}


def native_document(name,path,shapes,p):
    doc=App.newDocument(name)
    for key,shape in shapes.items():
        obj=doc.addObject('Part::Feature',key)
        obj.Label=key.replace('_',' ').title()
        obj.Shape=shape
        if key=='top_brace':
            for prop,value in (('ReachPerCaseHP',REACH_HP),('ScrewTabThickness',p.t),('ScrewTabWidth',p.tab_width),
                               ('SkinThickness',p.t),('ShoulderBaseFillet',SHOULDER_BASE_R),
                               ('ShoulderTopRound',SHOULDER_TOP_R),('CollarRoofClearance',ROOF_GAP),
                               ('CollarSideClearance',SIDE_GAP),('CollarPocketFillet',POCKET_R),
                               ('BridgeStep',BRIDGE_STEP),('WebFillet',WEB_R),
                               ('SpineWidth',SPINE_W),('SpineFlareRadius',INNER_R),('SpineEdgeRound',EDGE_R),
                               ('HoleDiameter',base.M3_CLEAR),('HolePitch',2*base.HP),
                               ('ScrewLength',SCREW_L)):
                obj.addProperty('App::PropertyFloat',prop,'Build dimensions')
                setattr(obj,prop,value)
                obj.setEditorMode(prop,1)
            obj.addProperty('App::PropertyString','Regenerate','Build dimensions')
            obj.Regenerate='case/tools/build_middle_brace.sh (not a live PartDesign tree)'
    doc.recompute()
    temporary=path.with_name('.'+path.name)
    doc.saveAs(str(temporary))
    App.closeDocument(doc.Name)
    doc=App.openDocument(str(temporary))
    for key,shape in shapes.items():
        actual=doc.getObject(key).Shape
        valid(actual,'native '+key)
        assert difference(actual,shape) < TOL,key
    App.closeDocument(doc.Name)
    temporary.replace(path)


def main():
    d=base.Dims(42,60,0.5,base.module_panels())
    j=middle.Join(d)
    p=Layout(d,j)
    asm,diffs=sources(d,j)
    s=finish(p,brace(d,j,p))
    fasteners,engagement=hardware(d,p)
    checks=verify(d,j,p,s,asm,fasteners,engagement)
    for folder in (OUT,RESEARCH,CASE/'cad'):
        folder.mkdir(parents=True,exist_ok=True)
    native_document('MiddleTopBrace',CASE/'cad'/'middle-brace.FCStd',{'top_brace':s},p)
    full={**asm,'top_brace':s,**fasteners}
    native_document('BracedDoubleCase',CASE/'cad'/'middle-braced-assembly.FCStd',full,p)
    prints={'middle-brace-6hp':export_part(s,OUT/'middle-brace-6hp')}
    # Short test print of everything that bridges: the front crossbar with its
    # collar pocket, the stepped roof, the web and a stub of the spine.
    coupon=s.common(base.box((p.x0-1,p.y0-1,p.z0-1),
                             (p.x1-p.x0+2,p.web_foot[0]+6-p.y0+1,p.z1-p.z0+2))).removeSplitter()
    valid(coupon,'front fitting coupon')
    prints['front-fit-coupon']=export_part(coupon,OUT/'front-fit-coupon')
    Part.makeCompound(list(full.values())).exportStep(str(OUT/'assembly-preview.step'))
    reopened=Part.Shape()
    reopened.read(str(OUT/'assembly-preview.step'))
    assert reopened.isValid() and len(reopened.Solids)==len(full)
    # Solid by solid. The brace's flares cross the web's curved profile, and
    # those edges round-trip as splines: a few 1e-3 mm3 off in 7 cm3. Its own
    # print STEP is still compared shape against shape in export_part.
    for (name,part),solid in zip(full.items(),reopened.Solids):
        limit = 5*TOL if name == 'top_brace' else TOL
        assert abs(solid.Volume-part.Volume) < limit, (name,solid.Volume-part.Volume)
    for name,part in full.items():
        MeshPart.meshFromShape(Shape=part,LinearDeflection=0.02,AngularDeflection=0.12).write(str(RESEARCH/f'asm-{name}.stl'))
    MeshPart.meshFromShape(Shape=s,LinearDeflection=0.01,AngularDeflection=0.10).write(str(RESEARCH/'brace.stl'))
    # Stand-in for the installed modules the brace lies on: one plain sheet per
    # case over the whole module row, without inventing electronics or knobs.
    for side,offset in (('left',0),('right',j.offset)):
        panel=base.box((offset+d.row_x0,0,d.top),(d.hp*base.HP,base.PANEL_H,d.panel_t))
        MeshPart.meshFromShape(Shape=panel,LinearDeflection=0.02,AngularDeflection=0.12).write(str(RESEARCH/f'display-{side}.stl'))
    dimensions={'reach_hp_per_case':REACH_HP,'nominal_reach_mm':REACH_HP*base.HP,
                'underside':'one flat plane on the module faces = frame top and lip',
                'underside_above_module_faces_mm':round(p.z0-d.case_top,3),
                'screw_tab_thickness_mm':p.t,'source_faceplate_thickness_mm':d.panel_t,
                'screw_tab_width_mm':p.tab_width,'source_rail_width_mm':d.rail_w,
                'screw_tabs_top_above_module_faces_mm':round(p.mount_z-d.case_top,3),
                'tab_end_past_last_hole_centre_mm':END_MARGIN,
                'skin_thickness_mm':p.t,'spine_width_mm':round(p.web_x1-p.web_x0,3),
                'spine_edge_round_mm':EDGE_R,'outline_radius_mm':OUTER_R,'inside_corner_radius_mm':INNER_R,
                'collar_pocket_span_mm':round(p.lip_x0-p.left_wall_x1,3),
                'collar_pocket_fillet_mm':POCKET_R,
                'clearance_beside_collar_mm':SIDE_GAP,'clearance_above_collar_mm':ROOF_GAP,
                'bridge_step_mm':BRIDGE_STEP,'web_fillet_mm':WEB_R,
                'web_foot_past_collar_slope_mm':WEB_GAP,
                'shoulder_end_from_frame_face_mm':SHOULDER,
                'shoulder_base_fillet_mm':SHOULDER_BASE_R,'shoulder_top_round_mm':SHOULDER_TOP_R,
                'height_above_module_faces_mm':round(p.z1-d.case_top,3),
                'head_clearance_pocket_diameter_mm':HEAD_RELIEF_D,'hole_diameter_mm':base.M3_CLEAR,'hole_pitch_mm':2*base.HP,
                'screw_length_mm':SCREW_L,'bounds_assembly_xyz_mm':bbox(s),
                'reserved_hp_each_case':0}
    (RESEARCH/'camera.json').write_text(json.dumps({'cx':p.cx,'cy':base.PANEL_H/2,'cz':(p.z0+p.z1)/2,
                                                       'front_y':d.hole_y[0],'left_x':p.x0,'right_x':p.x1,
                                                       'frame_x':p.frame_cx,'web_y':p.web_foot[0]},indent=2)+'\n')
    exports=[CASE/'cad'/'middle-brace.FCStd',CASE/'cad'/'middle-braced-assembly.FCStd']
    exports+=sorted(f for f in OUT.iterdir() if f.suffix in ('.step','.stl','.3mf'))
    source_paths=[CASE/'cad'/name for name in ('assembly.FCStd','middle-frame.FCStd','double-case-assembly.FCStd')]
    panel_sources=sorted(base.MODULES.glob('*/panels/front-pcb/*.kicad_pcb'))
    report={'status':'PASS','dimensions':dimensions,'source_geometry_differences_mm3':diffs,
            'source_sha256':{str(f.relative_to(CASE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source_paths},
            'faceplate_source_sha256':{str(f.relative_to(CASE.parent)):hashlib.sha256(f.read_bytes()).hexdigest()
                                      for f in panel_sources},
            'checks':checks,'holes_assembly_coordinates_mm':p.holes,'print':prints,
            'hardware':'up to 12 M3x8 socket-head screws, no washers, through the module panels\' own rail holes '
                       'into the installed M3x10 female hex spacers in the rail top sockets',
            'prototype_status':'Geometry and mesh checked only; print without supports, fit, stiffness and load capacity untested',
            'export_sha256':{str(f.relative_to(CASE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in exports}}
    text=json.dumps(report,indent=2)+'\n'
    (OUT/'verification.json').write_text(text)
    (RESEARCH/'build-report.json').write_text(text)
    print('MIDDLE_BRACE_BUILD_PASS',flush=True)


if __name__=='__main__' or any(Path(a).resolve()==Path(__file__).resolve() for a in sys.argv[1:]):
    main()
