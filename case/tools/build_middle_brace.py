"""One-piece top cap tying all four rails across the existing middle frame.

Six HP of the LEFT case's right end and RIGHT case's left end are reserved.
Three M3 holes per rail use the ACTUAL saved rail's 2 HP phase, not a new grid.
The four screw tabs match the rail width with no overhang, match the source
faceplate thickness, and sit flush with its front surface.
The bridge is a thin cap shaped on the frame's own top: over each proud
collar, down its slope and flat along the frame between the rails, one layer
above it. Between the rails it is a narrow spine, not the full frame width,
flared into the two crossbars. It is NOT a solid block.
Each tab meets the roof through a solid filleted shoulder that wraps the first
screw head, instead of the earlier 1.6 mm return wall that snapped off.
Print screw tabs DOWN on the bed, supports only under the cap: no support
touches the thin tabs or their holes.
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
OUTER_R = 2.0
INNER_R = 8.0        # flare where the spine runs into each crossbar
FRAME_GAP = 0.30     # beside the frame and its lip
ROOF_GAP = 0.20      # cap underside above the frame top, all along its profile
# Spine between the rails. Its 1.6 mm section only has to carry what the 10 mm
# screw arms can feed it: 16 mm is 25.6 mm2, above the two arms' net section at
# their holes (2 x 10.6 mm2). An estimate, not a tested rating.
SPINE_W = 16.0
EDGE_R = 0.6         # round on the spine's long top edges
# Frame top silhouette, as build_middle_frame.frame() draws it. The built cap
# is measured against the SAVED frame, so a changed frame fails the build.
COLLAR_INNER = 3.0   # collar flat past the rail's inner edge
COLLAR_BLEND = 6.0   # slope from the collar down to the module-face plane
SHOULDER = 13.0      # solid shoulder end, measured from the frame's own face
SHOULDER_BASE_R = 1.5  # concave fillet, shoulder to tab top
SHOULDER_TOP_R = 1.0   # round on the shoulder's top edge
SCREW_L = 6.0
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
        # These boundaries reserve actual module slots, including the right lip.
        self.x0 = d.row_x0 + (d.hp-REACH_HP)*base.HP
        self.x1 = j.offset + d.row_x0 + REACH_HP*base.HP
        self.frame_cx = d.L + j.width/2
        self.t = d.panel_t  # exact source-panel thickness, not a new guessed value
        self.z0 = d.top
        self.mount_z = d.top + self.t
        self.roof_z = j.collar_top + ROOF_GAP
        self.z1 = self.roof_z + self.t
        # Screw arms follow the actual rail edges, not the wider frame collars.
        # No added front/back margin and no extension into either module bay.
        self.tab_width = d.rail_w
        self.y0 = d.rail_y[0]
        self.y1 = d.rail_y[1] + self.tab_width
        self.front_inner = d.rail_y[0] + self.tab_width
        self.back_inner = d.rail_y[1]
        # The two shoulders remain outside the middle frame and its 1HP lip.
        # They connect low screw tabs to a 1-panel-thick raised roof, and end
        # the same distance from the frame faces on both sides.
        self.left_wall_x1 = d.L - FRAME_GAP
        self.right_wall_x0 = j.offset + d.fill + FRAME_GAP
        self.shoulder_x0 = d.L - SHOULDER
        self.shoulder_x1 = j.offset + SHOULDER
        # The crossbars cover the frame and its lip from shoulder to shoulder;
        # the spine between them is centred over the frame body; only the
        # right-hand flares reach over its 1HP lip.
        self.cx = (self.left_wall_x1 + self.right_wall_x0)/2
        self.web_x0 = self.cx - SPINE_W/2
        self.web_x1 = self.cx + SPINE_W/2
        self.spine_z1 = d.case_top + ROOF_GAP + self.t
        assert d.L < self.web_x0-INNER_R and self.web_x1+INNER_R < j.offset+d.fill
        assert self.web_x1 < j.offset
        assert SPINE_W*self.t >= 2*(self.tab_width-base.M3_CLEAR)*self.t, 'spine weaker than the arms'
        assert abs(self.mount_z-d.case_top) < 1e-8, 'screw tabs must be flush with module fronts'
        assert self.t >= 1.2, 'source faceplate is too thin for this prototype'
        self.holes = []
        for side, offset, indices in (('left',0,range(d.n_sockets-3,d.n_sockets)),
                                      ('right',j.offset,range(3))):
            for rail_i, y in enumerate(d.hole_y):
                for k in indices:
                    x = offset+d.module_hole_x()[k]
                    assert self.x0+base.M3_CLEAR/2 < x < self.x1-base.M3_CLEAR/2
                    self.holes.append({'case':side, 'rail':'front' if rail_i == 0 else 'back',
                                       'rail_socket_index':k, 'x':x, 'y':y,
                                       'case_local_x':d.module_hole_x()[k]})
        assert len(self.holes) == 12
        # Each shoulder holds the first screw in a walled pocket and its base
        # fillet runs out before the second screw's head.
        for side, edge in (('left',self.shoulder_x0),('right',self.shoulder_x1)):
            xs = sorted((abs(h['x']-edge),h['x']) for h in self.holes if h['case'] == side)
            first = [x for _,x in xs if (x > edge) == (side == 'left')]
            second = [x for _,x in xs if (x > edge) != (side == 'left')]
            self.pocket_rim = min(abs(x-edge) for x in first)-HEAD_RELIEF_D/2-SHOULDER_TOP_R
            assert self.pocket_rim >= 1.0, 'pocket rim too thin at the shoulder top'
            assert min(abs(x-edge) for x in second)-HEAD_RELIEF_D/2 > SHOULDER_BASE_R
        assert SHOULDER_BASE_R+SHOULDER_TOP_R < self.z1-self.mount_z


def frame_top(d, j, grow, x0, length):
    """Everything under the frame's top silhouette grown by `grow`, over X."""
    y0, y1 = d.y0, d.y0+d.ylen
    over, inner, low = middle.COLLAR_OVERHANG, d.rail_w+COLLAR_INNER, d.top-10
    pts = [(y0-over,low), (y1+over,low), (y1+over,j.collar_top), (y1-inner,j.collar_top),
           (y1-inner-COLLAR_BLEND,d.case_top), (y0+inner+COLLAR_BLEND,d.case_top),
           (y0+inner,j.collar_top), (y0-over,j.collar_top)]
    body = middle.yz_prism(pts,0,1)
    body = body.makeFillet(middle.OUTLINE_FILLET,
                           [e for e in middle.x_edges(body) if e.CenterOfMass.z > low+1])
    ends = [f for f in body.Faces if f.BoundBox.XLength < 1e-6 and abs(f.BoundBox.XMin) < 1e-6]
    assert len(ends) == 1
    solid = ends[0].makeOffset2D(grow).extrude(V(length,0,0))
    if solid.Volume < 0:
        solid.reverse()
    solid.translate(V(x0,0,0))
    valid(solid,'frame top profile')
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


def brace(d, j, p):
    height = p.z1-p.z0
    outline = silhouette(p)

    # Panel-thick tabs + solid shoulders + panel-thick cap. Each tab and its
    # shoulder is one stepped X/Z profile: concave fillet at the tab, round on top.
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
    skin = [arm(p.x0,p.shoulder_x0,p.left_wall_x1),
            arm(p.x1,p.shoulder_x1,p.right_wall_x0),
            base.box((p.left_wall_x1-1,p.y0,p.z0),
                     (p.right_wall_x0-p.left_wall_x1+2,p.y1-p.y0,height))]
    # The cap takes the frame's own top profile: its top face is that profile
    # one gap plus one panel thickness up, its underside one gap up.
    top = frame_top(d,j,ROOF_GAP+p.t,p.x0-1,p.x1-p.x0+2)
    room = frame_top(d,j,ROOF_GAP,p.left_wall_x1,p.right_wall_x0-p.left_wall_x1)
    shape = skin[0].multiFuse(skin[1:]).common(outline).common(top).cut(room).removeSplitter()
    valid(shape,'cap before rounding')
    # Round the long top edges of the spine between the rails. Its sides are
    # bare skin edges, so tell the top edge from the underside one.
    def cap_top_edge(e):
        b = e.BoundBox
        if not (b.XLength < 1e-6 and min(abs(b.XMin-p.web_x0),abs(b.XMin-p.web_x1)) < 1e-6
                and b.YLength > 1e-3
                and p.front_inner+INNER_R-1e-6 < b.YMin and b.YMax < p.back_inner-INNER_R+1e-6):
            return False
        m = e.valueAt((e.FirstParameter+e.LastParameter)/2)
        inward = 0.05 if abs(b.XMin-p.web_x0) < 1e-6 else -0.05
        return not shape.isInside(V(m.x+inward,m.y,m.z+0.05),1e-6,True)
    square = shape.common(base.box((p.x0-1,p.y0-1,p.z0),(p.x1-p.x0+2,p.y1-p.y0+2,p.t)))
    shape = shape.makeFillet(EDGE_R,[e for e in shape.Edges if cap_top_edge(e)])
    # The round runs on along the tangent edges; keep the screw tabs square and
    # full panel thickness, so it fades out on the tab tops at the shoulders.
    shape = shape.fuse(square).removeSplitter()
    valid(shape,'cap')
    cuts = []
    for hole in p.holes:
        x,y = hole['x'],hole['y']
        cuts.append(base.cyl(base.M3_CLEAR/2,height+2,(x,y,p.z0-1)))
        # The first screw on each side sits inside the shoulder: pocket only
        # the elevated material so the head/tool is clear and its mounting tab
        # remains exactly panel-thick. This is NOT a countersink in the thin tab.
        # The right-hand pocket is open towards the roof, beside the 1HP lip.
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
    frame_distance = s.distToShape(asm['middle_frame'])[0]
    assert abs(frame_distance-min(FRAME_GAP,ROOF_GAP)) < 1e-5, frame_distance
    checks['closest_frame_clearance_mm'] = round(frame_distance,6)
    # A clearance gauge around the whole raised collar cannot overlap the brace.
    for y in d.hole_y:
        gauge = base.box((d.L-FRAME_GAP+1e-4,y-2,j.collar_top),
                         (j.width+d.fill+2*FRAME_GAP-2e-4,4,ROOF_GAP-1e-4))
        middle.no_collision(s,gauge,'collar roof clearance gauge')
    # The cap follows the SAVED frame's top: walk its underside from one rail
    # to the other, over collar, round, slope and flat, along the spine's
    # centre line and both edges, and both crossbars across the frame's own
    # width. Every point is one gap off the frame.
    lines = [(x,p.y0+1,p.y1-1) for x in (p.web_x0+0.5,p.cx,p.web_x1-0.5)]
    for x in (d.L+1.0,p.frame_cx,j.offset-1.0):  # the 1HP lip has no collar
        lines += [(x,p.y0+1,p.front_inner-1),(x,p.back_inner+1,p.y1-1)]
    profile = []
    for x,ya,yb in lines:
        for k in range(int((yb-ya)/0.5+1e-6)+1):
            y = ya+0.5*k
            column = s.common(base.box((x-0.005,y-0.005,p.z0-1),(0.01,0.01,p.z1-p.z0+2)))
            assert column.Volume > 0, ('cap missing over the frame',x,y)
            under = bbox(column)[4]
            gap = Part.Vertex(V(x,y,under)).distToShape(asm['middle_frame'])[0]
            assert abs(gap-ROOF_GAP) < 2e-3, ('cap does not follow the frame',x,y,gap)
            profile.append((y,under))
    lows = [z for _,z in profile]
    assert abs(min(lows)-(d.case_top+ROOF_GAP)) < 1e-6 and abs(max(lows)-p.roof_z) < 1e-6
    checks['cap_underside_follows_saved_frame_top'] = {
        'points_checked':len(profile),'gap_mm':ROOF_GAP,
        'underside_above_module_faces_mm':[round(min(lows)-d.case_top,3),round(max(lows)-d.case_top,3)]}
    # Horizontal rail-bearing area, using the ACTUAL perforated rail top faces.
    bottom = [f for f in s.Faces if abs(f.BoundBox.ZMin-d.top)<1e-6 and abs(f.BoundBox.ZMax-d.top)<1e-6]
    contacts = {}
    for side in ('left','right'):
        for rail in ('front','back'):
            name = f'{side}_rail_{rail}'
            top_faces = [f for f in asm[name].Faces if abs(f.BoundBox.ZMin-d.top)<1e-6 and abs(f.BoundBox.ZMax-d.top)<1e-6]
            area = sum(a.common(b).Area for a in bottom for b in top_faces)
            assert area > 170, (name,'insufficient rail contact',area)
            contacts[name] = round(area,4)
            xs = sorted(h['x'] for h in p.holes if h['case']==side and h['rail']==rail)
            assert len(xs) == 3 and all(abs(b-a-2*base.HP)<1e-6 for a,b in zip(xs,xs[1:]))
    checks['four_coplanar_rail_contact_areas_mm2'] = contacts
    # Measure each screw arm, from its tip to the cap's corner fillet, against
    # the saved rail's XY envelope. Hex socket openings are intentionally excluded
    # from this footprint check; the actual solid rail contact is checked above.
    footprints = {}
    for side, x0, x1 in (('left',p.x0,p.web_x0-INNER_R),
                        ('right',p.web_x1+INNER_R,p.x1)):
        for rail in ('front','back'):
            name = f'{side}_rail_{rail}'
            rb = bbox(asm[name])
            y0,y1 = (p.y0-1,base.PANEL_H/2) if rail=='front' else (base.PANEL_H/2,p.y1+1)
            wing = s.common(base.box((x0,y0,p.z0-1), (x1-x0,y1-y0,p.z1-p.z0+2)))
            valid(wing,name+' screw arm')
            wb = bbox(wing)
            rail_envelope = base.box((rb[0],rb[2],p.z0-1),
                                     (rb[1]-rb[0],rb[3]-rb[2],p.z1-p.z0+2))
            overhang = wing.cut(rail_envelope).Volume
            assert overhang < TOL, (name,'screw arm overhangs rail',overhang)
            assert abs(wb[2]-rb[2]) < 1e-6 and abs(wb[3]-rb[3]) < 1e-6, (name,wb,rb)
            assert abs(wb[3]-wb[2]-d.rail_w) < 1e-6, name+' screw arm width'
            footprints[name] = {'rail_y_bounds_mm':rb[2:4], 'screw_arm_y_bounds_mm':wb[2:4],
                                'rail_width_mm':round(rb[3]-rb[2],6),
                                'screw_arm_width_mm':round(wb[3]-wb[2],6),
                                'outside_rail_footprint_mm3':round(overhang,9)}
    checks['screw_arms_within_saved_rail_footprints'] = footprints
    checks['hole_count'] = len(p.holes)
    checks['holes_per_rail'] = 3
    checks['hole_pitch_mm'] = 2*base.HP
    # Read actual screw-head bearing solids: every mounting zone must be exactly
    # the source faceplate thickness and have its upper face at the module plane.
    tab_checks = []
    for h in p.holes:
        region = base.cyl(HEAD_D/2,p.z1-p.z0+2,(h['x'],h['y'],p.z0-1))
        bearing = s.common(region)
        bb = bbox(bearing)
        assert abs(bb[4]-d.top) < 1e-6 and abs(bb[5]-d.case_top) < 1e-6, ('tab not flush',h,bb)
        assert abs(bb[5]-bb[4]-d.panel_t) < 1e-6, ('tab thickness mismatch',h,bb)
        bearing_area = bearing.Volume/p.t
        assert bearing_area > 12, ('insufficient screw-head bearing area',h,bearing_area)
        tab_checks.append({'case':h['case'],'rail':h['rail'],'x_mm':round(h['x'],3),
                           'thickness_mm':round(bb[5]-bb[4],6),
                           'top_above_module_face_mm':round(bb[5]-d.case_top,6),
                           'head_bearing_area_mm2':round(bearing_area,4)})
    checks['faceplate_flush_screw_tabs'] = tab_checks
    for y,top in ((d.hole_y[0],p.z1),(base.PANEL_H/2,p.spine_z1),(d.hole_y[1],p.z1)):
        roof = s.common(base.box((p.cx-2,y-1,p.z0-1),(4,2,p.z1-p.z0+2)))
        assert abs(roof.Volume-4*2*p.t) < TOL, 'cap is not panel-thick'
        assert abs(bbox(roof)[5]-bbox(roof)[4]-p.t) < 1e-6 and abs(bbox(roof)[5]-top) < 1e-6
    checks['bridge_roof_thickness_mm'] = p.t
    # The spine between the flares: its real width and section, and nothing
    # else between the two crossbars.
    spine = s.common(base.box((p.x0-1,base.PANEL_H/2-0.5,p.z0-1),(p.x1-p.x0+2,1,p.z1-p.z0+2)))
    sb = bbox(spine)
    assert abs(sb[0]-p.web_x0) < 1e-6 and abs(sb[1]-p.web_x1) < 1e-6, sb
    assert abs(sb[4]-(d.case_top+ROOF_GAP)) < 1e-6 and abs(sb[5]-p.spine_z1) < 1e-6, sb
    arms_net = 2*(p.tab_width-base.M3_CLEAR)*p.t
    assert SPINE_W*p.t-0.5 < spine.Volume <= SPINE_W*p.t+1e-6 and spine.Volume > arms_net
    between = s.common(base.box((p.x0-1,p.front_inner+INNER_R,p.z0-1),
                                (p.x1-p.x0+2,p.back_inner-p.front_inner-2*INNER_R,p.z1-p.z0+2)))
    bb = bbox(between)
    assert abs(bb[0]-p.web_x0) < 1e-6 and abs(bb[1]-p.web_x1) < 1e-6, bb
    checks['spine'] = {'width_mm':round(sb[1]-sb[0],6),'section_mm2':round(spine.Volume,3),
                       'two_screw_arms_net_section_at_holes_mm2':round(arms_net,3),
                       'flare_radius_mm':INNER_R,
                       'length_between_crossbars_mm':round(p.back_inner-p.front_inner,3)}
    # Shoulders: the plastic joining each tab to the raised roof, cut just above
    # the tab top. The return walls they replace were 16 mm2 on the left and
    # two small pillars beside the screw-head scallop on the right.
    shoulders = {}
    side_wall = (d.rail_w-HEAD_RELIEF_D)/2
    for side, x0, x1 in (('left',p.shoulder_x0,p.left_wall_x1),
                        ('right',p.right_wall_x0,p.shoulder_x1)):
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
    # Full circular gauges through all mounting holes, plus actual insert fit.
    for i,h in enumerate(p.holes,1):
        x,y = h['x'],h['y']
        gauge = base.cyl(base.M3_CLEAR/2-1e-4,p.z1-p.z0+2,(x,y,p.z0-1))
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
    checks['nominal_thread_engagement_mm'] = round(engagement,3)
    checks['screw_tip_clearance_to_spacer_bottom_mm'] = round(base.SPACER_L-engagement,3)
    checks['fastener_envelopes_and_top_tool_access'] = 'PASS; threads are not modelled'
    # Open-bottom steps cannot undercut on a vertical installation path. Also
    # sample the lowering path against the saved frame, rails and all bases.
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
    panels = 0
    for side,offset in (('left',0),('right',j.offset)):
        for name,info in d.panels.items():
            for slot in range(0,d.hp,2):
                x = d.row_x0+slot*base.HP
                if x+info['width'] > d.L+1e-6:
                    continue
                # Reserve an entire 6HP slot group even though the H leaves the
                # interior open. No claim of installing a module beside the cap.
                if side=='left' and x+info['width'] > p.x0+1e-6:
                    continue
                if side=='right' and x < d.row_x0+REACH_HP*base.HP-1e-6:
                    continue
                panel = base.box((offset+x,0,d.top),(info['width'],info['height'],info['thickness']))
                middle.no_collision(panel,s,'remaining module envelope/'+name)
                for tag,part in fasteners.items():
                    if tag.startswith('screw_'):
                        middle.no_collision(panel,part,'module/screw '+tag)
                panels += 1
    assert panels > 0
    checks['remaining_slot_module_panel_envelopes_checked'] = panels
    checks['remaining_hp_each_case'] = d.hp-REACH_HP
    # Include the exposed inner edge of the right screw tabs at the lip relief,
    # not only the two outside slot boundaries.
    ligaments = [min(h['x']-(p.x0 if h['case']=='left' else p.right_wall_x0),
                     (p.left_wall_x1 if h['case']=='left' else p.x1)-h['x'])-base.M3_CLEAR/2
                 for h in p.holes]
    checks['minimum_hole_edge_ligament_mm'] = round(min(ligaments),3)
    # Measure actual layer sections rather than claiming what needs support.
    # Tabs and shoulders stand on the bed; the only material that starts over
    # air is the cap's underside, in the channel the frame fills.
    posed = print_pose(s)
    origin = bbox(s)
    channel = base.box((p.left_wall_x1-origin[0]-1e-4,-1,-1),
                       (p.right_wall_x0-p.left_wall_x1+2e-4,250,50))
    layers = int(math.ceil((p.z1-p.z0)/LAYER-1e-6))
    def layer(i):
        # Unit-thick prism of one layer section: sturdier than paper-thin cuts.
        z = (i+0.5)*LAYER
        prism = Part.makeFace(posed.slice(V(0,0,1),z),'Part::FaceMakerBullseye').extrude(V(0,0,1))
        prism.translate(V(0,0,-z))
        return prism
    sections = [layer(i) for i in range(layers)]
    supported, stray = 0.0, 0.0
    for a,b in zip(sections,sections[1:]):
        over = b.cut(a)
        if not over.Solids:
            continue
        supported += over.Volume
        stray += over.cut(channel).Volume
    assert stray < 0.01, ('material outside the cap channel starts over air',stray)
    # Both crossbars, the flares and the spine, as far as they lie in the
    # channel, less the two right-hand screw pockets that open into it.
    footprint = silhouette(p).common(base.box((p.left_wall_x1,p.y0-1,p.z0),
                                              (p.right_wall_x0-p.left_wall_x1,p.y1-p.y0+2,1))).Volume
    assert footprint-10 < supported < footprint+0.5, (supported,footprint)
    # Tabs and shoulders all start on the bed itself.
    bed = sections[0].Volume
    assert bed > 1000, ('bed contact',bed)
    tab_slab = posed.common(base.box((-1,-1,0),(250,250,p.t)))
    assert abs(tab_slab.Volume-bed*p.t) < TOL, 'screw tabs must rise straight from the bed'
    checks['print_bed_contact_mm2'] = round(bed,1)
    checks['print_supports_required'] = True
    checks['print_support_footprint_mm2'] = round(supported,1)
    checks['print_support_height_mm'] = [round(d.case_top+ROOF_GAP-p.z0,3),round(p.roof_z-p.z0,3)]
    checks['print_material_starting_over_air_outside_cap_channel_mm2'] = round(stray,4)
    checks['print_orientation'] = 'screw tabs down on the bed; supports under the cap only'
    return checks


def print_pose(shape):
    # As installed: rail seats on the bed, raised roof up.
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
            for prop,value in (('ReachPerCaseHP',REACH_HP),('RailPadThickness',p.t),('RailPadWidth',p.tab_width),
                               ('BridgeSkinThickness',p.t),('ShoulderBaseFillet',SHOULDER_BASE_R),
                               ('ShoulderTopRound',SHOULDER_TOP_R),('RoofClearance',ROOF_GAP),
                               ('SpineWidth',SPINE_W),('SpineFlareRadius',INNER_R),('CapEdgeRound',EDGE_R),
                               ('HoleDiameter',base.M3_CLEAR),('HolePitch',2*base.HP),
                               ('FrameClearance',FRAME_GAP),('ScrewLength',SCREW_L)):
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
    s=brace(d,j,p)
    fasteners,engagement=hardware(d,p)
    checks=verify(d,j,p,s,asm,fasteners,engagement)
    for folder in (OUT,RESEARCH,CASE/'cad'):
        folder.mkdir(parents=True,exist_ok=True)
    native_document('MiddleTopBrace',CASE/'cad'/'middle-brace.FCStd',{'top_brace':s},p)
    full={**asm,'top_brace':s,**fasteners}
    native_document('BracedDoubleCase',CASE/'cad'/'middle-braced-assembly.FCStd',full,p)
    prints={'middle-brace-6hp':export_part(s,OUT/'middle-brace-6hp')}
    coupon=s.common(base.box((p.x0-1,p.y0-1,p.z0-1),
                             (p.x1-p.x0+2,p.front_inner-p.y0+1,p.z1-p.z0+2))).removeSplitter()
    valid(coupon,'front fitting coupon')
    prints['front-fit-coupon']=export_part(coupon,OUT/'front-fit-coupon')
    Part.makeCompound(list(full.values())).exportStep(str(OUT/'assembly-preview.step'))
    reopened=Part.Shape()
    reopened.read(str(OUT/'assembly-preview.step'))
    assert reopened.isValid() and len(reopened.Solids)==len(full)
    # Solid by solid. The brace's flares cross the cap's curved profile, and
    # those edges round-trip as splines: about 2e-3 mm3 off in 8 cm3. Its own
    # print STEP is still compared shape against shape in export_part.
    for (name,part),solid in zip(full.items(),reopened.Solids):
        limit = 5*TOL if name == 'top_brace' else TOL
        assert abs(solid.Volume-part.Volume) < limit, (name,solid.Volume-part.Volume)
    for name,part in full.items():
        MeshPart.meshFromShape(Shape=part,LinearDeflection=0.02,AngularDeflection=0.12).write(str(RESEARCH/f'asm-{name}.stl'))
    MeshPart.meshFromShape(Shape=s,LinearDeflection=0.01,AngularDeflection=0.10).write(str(RESEARCH/'brace.stl'))
    # Show remaining module area without inventing electronics or knob geometry.
    for side,offset,x0,width in (('left',0,d.row_x0,(d.hp-REACH_HP)*base.HP-0.5),
                                ('right',j.offset,d.row_x0+REACH_HP*base.HP,(d.hp-REACH_HP)*base.HP-0.5)):
        panel=base.box((offset+x0,0,d.top),(width,base.PANEL_H,d.panel_t))
        MeshPart.meshFromShape(Shape=panel,LinearDeflection=0.02,AngularDeflection=0.12).write(str(RESEARCH/f'display-{side}.stl'))
    dimensions={'reach_hp_per_case':REACH_HP,'nominal_reach_mm':REACH_HP*base.HP,
                'rail_pad_thickness_mm':p.t,'source_faceplate_thickness_mm':d.panel_t,
                'rail_pad_width_mm':p.tab_width,'source_rail_width_mm':d.rail_w,
                'bridge_skin_thickness_mm':p.t,'screw_tabs_above_module_faces_mm':round(p.mount_z-d.case_top,3),'spine_width_mm':round(p.web_x1-p.web_x0,3),'crossbar_span_over_frame_mm':round(p.right_wall_x0-p.left_wall_x1,3),'cap_edge_round_mm':EDGE_R,'outline_radius_mm':OUTER_R,
                'inside_corner_radius_mm':INNER_R,'frame_clearance_mm':FRAME_GAP,
                'cap_clearance_over_frame_top_mm':ROOF_GAP,
                'spine_above_module_faces_mm':round(p.spine_z1-d.case_top,3),
                'shoulder_end_from_frame_face_mm':SHOULDER,
                'shoulder_base_fillet_mm':SHOULDER_BASE_R,'shoulder_top_round_mm':SHOULDER_TOP_R,
                'minimum_cap_thickness_over_collars_mm':p.t,
                'raised_bridge_above_module_faces_mm':round(p.z1-d.case_top,3),
                'head_clearance_pocket_diameter_mm':HEAD_RELIEF_D,'hole_diameter_mm':base.M3_CLEAR,'hole_pitch_mm':2*base.HP,
                'screw_length_mm':SCREW_L,'bounds_assembly_xyz_mm':bbox(s),
                'remaining_hp_each_case':d.hp-REACH_HP}
    (RESEARCH/'camera.json').write_text(json.dumps({'cx':p.cx,'cy':base.PANEL_H/2,'cz':(p.z0+p.z1)/2,
                                                       'front_y':d.hole_y[0],'left_x':p.x0,'right_x':p.x1},indent=2)+'\n')
    exports=[CASE/'cad'/'middle-brace.FCStd',CASE/'cad'/'middle-braced-assembly.FCStd']
    exports+=sorted(f for f in OUT.iterdir() if f.suffix in ('.step','.stl','.3mf'))
    source_paths=[CASE/'cad'/name for name in ('assembly.FCStd','middle-frame.FCStd','double-case-assembly.FCStd')]
    panel_sources=sorted(base.MODULES.glob('*/panels/front-pcb/*.kicad_pcb'))
    report={'status':'PASS','dimensions':dimensions,'source_geometry_differences_mm3':diffs,
            'source_sha256':{str(f.relative_to(CASE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source_paths},
            'faceplate_source_sha256':{str(f.relative_to(CASE.parent)):hashlib.sha256(f.read_bytes()).hexdigest()
                                      for f in panel_sources},
            'checks':checks,'holes_assembly_coordinates_mm':p.holes,'print':prints,
            'hardware':'12 M3x6 socket-head screws, no washers; 12 installed M3x10 female hex spacers in rail top sockets',
            'prototype_status':'Geometry and mesh checked only; print fit, stiffness and load capacity untested',
            'export_sha256':{str(f.relative_to(CASE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in exports}}
    text=json.dumps(report,indent=2)+'\n'
    (OUT/'verification.json').write_text(text)
    (RESEARCH/'build-report.json').write_text(text)
    print('MIDDLE_BRACE_BUILD_PASS',flush=True)


if __name__=='__main__' or any(Path(a).resolve()==Path(__file__).resolve() for a in sys.argv[1:]):
    main()
