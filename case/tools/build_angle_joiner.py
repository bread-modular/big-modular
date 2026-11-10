"""Fixed-angle bolt-on joiner plates for two existing 42 HP / 60 mm skiffs.

Build only this variant: case/tools/build_angle_joiner.sh.
Original case, stand and side-by-side middle-frame exports are never overwritten.
Lower case is horizontal; upper case is 60 degrees above horizontal. Two mirrored
skeletal cheeks include rear desk feet. Four captured M3x10 female hex spacers
load from INSIDE each replacement side panel; M3x8 screws enter from OUTSIDE.
The 1.8 mm outer shoulder retains the spacers mechanically, not by glue pull-out.

All coordinates are original build_case assembly axes (X along the rails).
This is a CAD-checked prototype, not a tested lifting bracket or rated stand.
"""
import hashlib
import itertools
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
import build_middle_frame as common
import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = base.CASE
TOL = 1e-3
ANGLE = 60.0
GAP_Y = 18.0
GAP_Z = 6.0
PLATE_T = 8.0
SCREW_L = 8.0
GRIP = 2.0
CB_DEPTH = PLATE_T - GRIP
BASE_RELIEF = 3.65  # stock base overhang 3.15 + 0.50 mm
RELIEF_CLR = 0.50
MOUNT_Y = (25.0, 103.5)
MOUNT_Z = (25.0, 45.0)
PAD_R = 12.0
BRIDGE_R = 16.0
LEG_R = 14.0
BRACE_R = 10.0
FOOT = (272.0, 8.0)  # behind the upper case; cheek prints diagonally on the 256 mm bed
FOOT_WIDTH = 16.0  # 2 mm margin each side of the user's 12 mm square pad
FOOT_LENGTH = 20.0
FOOT_HEIGHT = 8.0
FOOT_FILLET = 2.0
RUBBER_PAD_SIZE = 12.0
FRONT_PAD_Y = 7.0
ROUND = 2.0
WINDOW_R = 6.0
SERVICE_D = 8.5


def bounds(shape):
    b = shape.optimalBoundingBox(False, False)
    return [round(v, 6) for v in (b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax)]


def assert_solid(shape, label):
    assert shape.isValid() and len(shape.Solids) == 1, label


def clear(a, b, label):
    return common.no_collision(a, b, label)


class Layout:
    def __init__(self, d):
        a = math.radians(ANGLE)
        self.c, self.s = math.cos(a), math.sin(a)
        # Position upper case's front/top edge behind and above lower back/top.
        self.ty = d.y0 + d.ylen + GAP_Y - (d.y0 * self.c - d.case_top * self.s)
        self.tz = d.case_top + GAP_Z - (d.y0 * self.s + d.case_top * self.c)

    def point(self, y, z, upper=False):
        if not upper:
            return y, z
        return y * self.c - z * self.s + self.ty, y * self.s + z * self.c + self.tz

    def place(self, shape, upper=False):
        s = shape.copy()
        if upper:
            s.rotate(V(0, 0, 0), V(1, 0, 0), ANGLE)
            s.translate(V(0, self.ty, self.tz))
        return s

    def mounts(self, upper=False):
        return [self.point(y, z, upper) for y in MOUNT_Y for z in MOUNT_Z]


def rounded_box(x, length, y0, y1, z0, z1, radius):
    b = base.box((x, y0, z0), (length, y1-y0, z1-z0))
    return b.makeFillet(radius, common.x_edges(b))


def capsule(a, b, radius, x, length):
    dy, dz = b[0]-a[0], b[1]-a[1]
    dist = math.hypot(dy, dz)
    ny, nz = -dz / dist * radius, dy / dist * radius
    rect = common.yz_prism([(a[0]+ny, a[1]+nz), (b[0]+ny, b[1]+nz),
                            (b[0]-ny, b[1]-nz), (a[0]-ny, a[1]-nz)], x, length)
    return rect.fuse([base.cyl(radius, length, (x, *p), (1, 0, 0)) for p in (a, b)]).removeSplitter()


def side_panel(d, left):
    """Keep every existing rail/base/cover interface; add inward-loading sockets."""
    sgn = 1 if left else -1
    inner = 0 if left else d.L
    outer = -d.T if left else d.L + d.T
    cuts = []
    for y in MOUNT_Y:
        for z in MOUNT_Z:
            # Pocket starts at the INBOARD face, toward the outside; the remaining
            # 1.8 mm outside wall is a shoulder with only a 3.4 mm screw passage.
            cuts.append(base.end_spacer_socket(inner, -sgn, y, z))
            cuts.append(base.cyl(base.M3_CLEAR/2, d.T+2, (outer-sgn, y, z), (sgn, 0, 0)))
    return base.cut_all(base.side_panel(d, left), cuts)


def rail_axes(d, layout):
    z = d.top - d.rail_h/2
    return [layout.point(y, z, upper) for upper in (False, True) for y in d.hole_y]


def rubber_pad_centres(d):
    """All four adhesive faces share Z=0; real pad thickness is unspecified."""
    left_x = -d.T-PLATE_T+FOOT_WIDTH/2
    return {'rear_left': (left_x, FOOT[0]),
            'rear_right': (d.L-left_x, FOOT[0]),
            'front_left': (d.plate_x0+7, FRONT_PAD_Y),
            'front_right': (d.plate_x0+d.plate_len-7, FRONT_PAD_Y)}


def foot_land(x):
    """Integral plinth with rounded top ends and a full flat adhesive face.

    No bottom-edge fillet, holes or lettering reduce the 12 x 12 bonding patch.
    No raised rim assumes a particular rubber-pad thickness/compression.
    Simple cylindrical top blends also avoid tiny compound-fillet mesh slivers.
    """
    foot = base.box((x, FOOT[0]-FOOT_LENGTH/2, 0), (FOOT_WIDTH, FOOT_LENGTH, FOOT_HEIGHT))
    top = [e for e in common.x_edges(foot) if e.CenterOfMass.z > FOOT_HEIGHT-0.01]
    return foot.makeFillet(FOOT_FILLET, top)


def plate(d, layout, left):
    # Build the LEFT cheek at its contact face, then mirror for the right cheek.
    contact = -d.T
    x = contact - PLATE_T
    pad = rounded_box(x, PLATE_T, MOUNT_Y[0]-PAD_R, MOUNT_Y[1]+PAD_R,
                      MOUNT_Z[0]-PAD_R, MOUNT_Z[1]+PAD_R, 10.0)
    a = (MOUNT_Y[1], sum(MOUNT_Z)/2)
    b = layout.point(MOUNT_Y[0], sum(MOUNT_Z)/2, True)
    c = layout.point(MOUNT_Y[1], sum(MOUNT_Z)/2, True)
    shape = pad.fuse([layout.place(pad, True), capsule(a, b, BRIDGE_R, x, PLATE_T),
                      capsule(c, FOOT, LEG_R, x, PLATE_T), capsule(a, FOOT, BRACE_R, x, PLATE_T)]).removeSplitter()
    # The two rail screws near the joint stay accessible. Reinforce their access
    # holes rather than leaving a thin crescent at the edge of a bridge.
    access = (rail_axes(d, layout)[1], rail_axes(d, layout)[2])
    shape = shape.fuse([base.cyl(10, PLATE_T, (x, *p), (1, 0, 0)) for p in access]).removeSplitter()
    shape = shape.cut(base.box((x-1, -100, -100), (PLATE_T+2, 500, 100))).removeSplitter()
    # Round all non-tangent silhouette corners except the flat desk contact.
    edges = [e for e in common.x_edges(shape) if e.CenterOfMass.z > 0.1]
    shape = shape.makeFillet(ROUND, edges)
    assert_solid(shape, 'rounded cheek outline')

    # Enlarged 16 x 20 mm adhesive plinth with R2 top end blends.
    # Keep the outside face at x (the print bed); widening is inward, behind the case.
    shape = shape.fuse(foot_land(x)).removeSplitter()

    cuts = []
    window = rounded_box(x-1, PLATE_T+6, MOUNT_Y[0]+15, MOUNT_Y[1]-15, 24, 46, WINDOW_R)
    cuts += [window, layout.place(window, True)]
    # Bases project 3.15 mm past the panel. Pockets clear their entire envelope,
    # leaving 4.35 mm of plate behind it instead of forcing a case modification.
    for upper in (False, True):
        relief = base.box((contact-BASE_RELIEF, d.y0-RELIEF_CLR, -RELIEF_CLR),
                          (BASE_RELIEF+1, d.ylen+2*RELIEF_CLR,
                           d.P+d.socket_h+2*RELIEF_CLR))
        cuts.append(layout.place(relief, upper))
        for y, z in layout.mounts(upper):
            cuts.append(base.cyl(base.M3_CLEAR/2, PLATE_T+2, (x-1, y, z), (1, 0, 0)))
            cuts.append(base.cyl(base.M3_CB_D/2, CB_DEPTH+1, (x-1, y, z), (1, 0, 0)))
    for y, z in rail_axes(d, layout):
        cuts.append(base.cyl(SERVICE_D/2, PLATE_T+6, (x-1, y, z), (1, 0, 0)))
    shape = base.cut_all(shape, cuts)
    if not left:
        shape = shape.mirror(V(d.L/2, 0, 0), V(1, 0, 0))
    assert_solid(shape, 'finished cheek')
    return shape


def hex_prism(x, y, z, length, direction, af=5.5):
    r = af / math.sqrt(3)
    # Flats along Y, exactly as base.end_spacer_socket.
    pts = [V(x, y+r*math.cos(math.radians(30+60*i)), z+r*math.sin(math.radians(30+60*i)))
           for i in range(6)]
    return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(direction*length, 0, 0))


def fasteners(d, layout, left, upper):
    sgn = 1 if left else -1
    outer = -d.T if left else d.L + d.T
    shoulder = d.T - base.SPACER_SOCKET_DEPTH
    result = {}
    for i, (y, z) in enumerate(layout.mounts(upper)):
        seat = outer - sgn*GRIP
        shaft = base.cyl(1.5, SCREW_L, (seat, y, z), (sgn, 0, 0))
        head = base.cyl(2.75, 3.0, (seat-sgn*3, y, z), (sgn, 0, 0))
        spacer = hex_prism(outer+sgn*shoulder, y, z, base.SPACER_L, sgn)
        spacer = spacer.cut(base.cyl(base.M3_CLEAR/2, base.SPACER_L+2,
                                    (outer+sgn*(shoulder-1), y, z), (sgn, 0, 0)))
        # Upper sockets rotate with the case around their X axes.
        if upper:
            spacer.rotate(V(0, y, z), V(1, 0, 0), ANGLE)
        result[f'screw_{i}'] = shaft.fuse(head).removeSplitter()
        result[f'spacer_{i}'] = spacer
    return result


def assembly(d, layout, source, parts):
    asm = {'joiner_left': parts['joiner-left'], 'joiner_right': parts['joiner-right']}
    for upper, label in ((False, 'lower'), (True, 'upper')):
        for name in ('bottom_plate', 'rail_front', 'rail_back'):
            asm[f'{label}_{name}'] = layout.place(source[name], upper)
        for side in ('left', 'right'):
            asm[f'{label}_side_panel_{side}'] = layout.place(parts[f'side-panel-{side}'], upper)
    return asm


def verify(d, layout, source, parts, asm):
    checks = {}
    for name, shape in {**parts, **asm}.items():
        assert_solid(shape, name)
    checked = 0
    for (an, a), (bn, b) in itertools.combinations(asm.items(), 2):
        clear(a, b, an+'/'+bn)
        checked += 1
    checks['assembly_pairs_no_interference'] = checked

    # Reuse original full-case checks: rail notches, grooves, bottom sockets etc.
    single = {name.replace('_', '-'): shape for name, shape in source.items()}
    single['side-panel-left'] = parts['side-panel-left']
    single['side-panel-right'] = parts['side-panel-right']
    checks['original_case_interfaces'] = base.checks(d, single)
    for side in ('left', 'right'):
        old, new = source['side_panel_'+side], parts['side-panel-'+side]
        assert new.cut(old).Volume < TOL, 'side panels must not grow into module bay'
        # The bottom mounting band and rail/lip band remain byte-independent exact solids.
        for lo, hi in ((d.P, 17), (50, d.case_top+1)):
            band = base.box((-d.T-1, d.y0-1, lo), (d.L+2*d.T+2, d.ylen+2, hi-lo))
            assert old.common(band).cut(new).Volume < TOL, (side, 'changed original interface')

    # Whole case envelopes, full module row and a 10 mm above-face allowance.
    envelope = base.box((d.plate_x0, d.y0, 0), (d.plate_len, d.ylen, d.case_top))
    lo_env, hi_env = envelope, layout.place(envelope, True)
    clear(lo_env, hi_env, 'case envelopes')
    checks['case_envelope_min_distance_mm'] = round(lo_env.distToShape(hi_env)[0], 3)
    module_rows, above = [], []
    for upper in (False, True):
        panel = base.box((d.row_x0, 0, d.top), (d.hp*base.HP, base.PANEL_H, d.panel_t))
        controls = base.box((d.row_x0, 0, d.case_top), (d.hp*base.HP, base.PANEL_H, 10))
        module_rows.append(layout.place(panel, upper))
        above.append(layout.place(controls, upper))
        for i in (0, 1):
            cover = layout.place(base.cover_blank(d, i), upper)
            for name, part in asm.items():
                clear(cover, part, f'cover{upper}/{i}/{name}')
        for name, part in asm.items():
            clear(module_rows[-1], part, f'module envelope/{upper}/{name}')
            clear(above[-1], part, f'10mm above face/{upper}/{name}')
    clear(above[0], above[1], '10mm above-face envelopes')
    checks['above_face_10mm_envelopes_min_distance_mm'] = round(above[0].distToShape(above[1])[0], 3)
    checks['stock_covers_and_full_module_rows_clear'] = True

    # Original rail screws and straight driver access are not covered by cheeks.
    for left in (True, False):
        sg = 1 if left else -1
        xo = -d.T if left else d.L+d.T
        cheek = parts['joiner-left' if left else 'joiner-right']
        for y, z in rail_axes(d, layout):
            head = base.cyl(2.75, 3, (xo-sg*3, y, z), (sg, 0, 0))
            tool = base.cyl(2.5, 45, (xo-sg*45, y, z), (sg, 0, 0))
            clear(head, cheek, 'original rail screw head')
            clear(tool, cheek, 'rail screw driver access')
        # Cases are assembled first; then cheek approaches along X from outside.
        for distance in (0.2, 1, 3, 6, 12, 25):
            sliding = common.moved(cheek, dx=-sg*distance)
            for name, part in asm.items():
                if not name.startswith('joiner'):
                    clear(sliding, part, 'plate outside approach/'+name)
    checks['existing_rail_head_and_driver_access'] = True
    checks['plate_outside_approach_samples_clear_mm'] = [0.2, 1, 3, 6, 12, 25]

    # Independent full spacer envelopes, shoulder rings, thread stacks and head seats.
    shoulder = d.T-base.SPACER_SOCKET_DEPTH
    engagement = SCREW_L-GRIP-shoulder
    assert shoulder >= 1.5 and 4 <= engagement <= base.SPACER_L-0.5
    assert PLATE_T-BASE_RELIEF >= 4.0
    hardware = {}
    min_surround = 1.5
    for left in (True, False):
        side = 'left' if left else 'right'
        sg = 1 if left else -1
        xo = -d.T if left else d.L+d.T
        xi = 0 if left else d.L
        panel = parts['side-panel-'+side]
        for y in MOUNT_Y:
            for z in MOUNT_Z:
                # Same-AF pocket gauge + extra wall envelope at mid-depth.
                gauge = hex_prism(xo+sg*(shoulder+0.001), y, z,
                                  base.SPACER_SOCKET_DEPTH-0.002, sg, base.SPACER_SOCKET_AF-0.002)
                clear(gauge, panel, 'full hex socket gauge')
                # Whole ring of load-bearing material, excluding screw passage.
                ring = base.cyl(2.65, shoulder-0.002, (xo+sg*0.001, y, z), (sg, 0, 0))
                ring = ring.cut(base.cyl(base.M3_CLEAR/2+0.001, d.T+2, (xo-sg, y, z), (sg, 0, 0)))
                assert ring.cut(panel).Volume < TOL, 'missing capture shoulder'
                # Offset hex witness: >=1.5 mm side material all around the pocket.
                outer_hex = hex_prism(xo+sg*(shoulder+0.1), y, z,
                                      base.SPACER_SOCKET_DEPTH-0.2, sg,
                                      base.SPACER_SOCKET_AF+2*min_surround)
                pocket = hex_prism(xo+sg*(shoulder+0.05), y, z,
                                   base.SPACER_SOCKET_DEPTH-0.1, sg, base.SPACER_SOCKET_AF+0.002)
                wall_ring = outer_hex.cut(pocket)
                assert wall_ring.cut(panel).Volume < TOL, 'socket side walls'
                # Existing rails are near Y edges, not in the spacer entry path.
                insertion = hex_prism(xi, y, z, 16, sg, 5.5)
                for key in ('rail_front', 'rail_back', 'bottom_plate'):
                    clear(insertion, source[key], 'spacer inside insertion')
        for upper in (False, True):
            h = fasteners(d, layout, left, upper)
            for name, shape in h.items():
                for partname in ('joiner_'+side, ('upper' if upper else 'lower')+'_side_panel_'+side):
                    clear(shape, asm[partname], name+'/'+partname)
                hardware[f'{"upper" if upper else "lower"}_{side}_{name}'] = shape
    checks['mount_hardware'] = {'M3x8_screws':16, 'M3x10_hex_spacers':16,
                               'thread_engagement_mm':round(engagement, 3),
                               'outer_capture_shoulder_mm':round(shoulder, 3),
                               'socket_side_wall_verified_mm':min_surround,
                               'plate_under_head_mm':GRIP,
                               'plate_behind_base_relief_mm':PLATE_T-BASE_RELIEF,
                               'inside_spacer_loading':True, 'hardware_solids_clear':True}

    # All four full adhesive patches are solid, clear of screw counterbores and
    # coplanar. Rear patches also retain >=1 mm full-square placement tolerance.
    pads = rubber_pad_centres(d)
    pad_checks = {}
    for name, (cx, cy) in pads.items():
        side = name.rsplit('_', 1)[1]
        rear = name.startswith('rear')
        support = parts['joiner-'+side] if rear else source['bottom_plate']
        thickness = 3.0 if rear else 1.0
        for margin in ((0, 1.0) if rear else (0,)):
            edge = RUBBER_PAD_SIZE+2*margin
            gauge = base.box((cx-edge/2, cy-edge/2, 0.001), (edge, edge, thickness))
            assert gauge.cut(support).Volume < TOL, (name, 'unsupported adhesive patch', margin)
        # Witness directly below the whole pad: no lip, screw or neighbouring
        # structural part can obstruct placing the pad against the Z=0 face.
        below = base.box((cx-RUBBER_PAD_SIZE/2, cy-RUBBER_PAD_SIZE/2, -2),
                         (RUBBER_PAD_SIZE, RUBBER_PAD_SIZE, 2))
        for partname, shape in asm.items():
            clear(below, shape, name+' pad placement/'+partname)
        pad_checks[name] = {'centre_xyz_mm':[round(cx,3),round(cy,3),0.0],
                            'full_square_bonding_area_mm2':RUBBER_PAD_SIZE**2,
                            'verified_solid_depth_mm':thickness,
                            'placement_margin_verified_mm':1.0 if rear else 0.0}
    checks['rubber_pad_lands'] = {'pad_size_mm':[RUBBER_PAD_SIZE,RUBBER_PAD_SIZE],
                                 'quantity':4, 'rear_plinth_size_mm':[FOOT_WIDTH,FOOT_LENGTH,FOOT_HEIGHT],
                                 'rear_top_end_fillet_mm':FOOT_FILLET,
                                 'rear_nominal_pad_edge_margin_xy_mm':[(FOOT_WIDTH-RUBBER_PAD_SIZE)/2,
                                                                      (FOOT_LENGTH-RUBBER_PAD_SIZE)/2],
                                 'recess_depth_mm':0, 'coplanar_bonding_z_mm':0,
                                 'pad_thickness':'user-supplied; use the same thickness at all four positions',
                                 'positions':pad_checks}
    # Conservative static screening assumes point loads anywhere in the central
    # 80% of either case footprint; use pad centres, not the wider pad edges.
    com_samples = []
    for upper in (False, True):
        for y in (d.y0+0.1*d.ylen, d.y0+0.9*d.ylen):
            for z in (6.5, d.case_top):
                com_samples.append(layout.point(y, z, upper)[0])
    # Every convex combination of these screened mass positions stays within
    # the front/rear pad-centre interval. No claim about cable pulls or strength.
    support_margin = min(min(com_samples)-FRONT_PAD_Y, FOOT[0]-max(com_samples))
    assert support_margin >= 4, ('insufficient static support margin', support_margin)
    checks['support_geometry'] = {'front_rubber_pad_centre_y_mm':FRONT_PAD_Y,
                                  'rear_rubber_pad_centre_y_mm':FOOT[0],
                                  'central_80pct_case_pointload_y_range_mm':[round(min(com_samples),3),round(max(com_samples),3)],
                                  'min_pointload_margin_to_pad_centres_mm':round(support_margin,3),
                                  'assumption':'points in central 80% Y and Z=6.5..65, no cable force; not a rating'}
    checks['native_single_solids'] = True
    return checks, hardware


def print_pose(shape, left=True):
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(0, 1, 0), -90 if left else 90)
    b = bounds(s)
    angle = 0
    if max(b[1]-b[0], b[3]-b[2]) > base.BED-4:
        # The rear-foot cheek is longer than the bed, but its actual silhouette
        # (not its bounding rectangle) fits diagonally. Check native trimmed arcs.
        candidates = []
        for deg in range(0, 180):
            p = s.copy()
            p.rotate(V(0, 0, 0), V(0, 0, 1), deg)
            pb = bounds(p)
            candidates.append((max(pb[1]-pb[0], pb[3]-pb[2]), deg))
        _, angle = min(candidates)
        s.rotate(V(0, 0, 0), V(0, 0, 1), angle)
        b = bounds(s)
    s.translate(V(-b[0], -b[2], -b[4]))
    return s, angle


def export_part(shape, path, left):
    posed, angle = print_pose(shape, left)
    b = bounds(posed)
    dims = [round(b[i+1]-b[i],3) for i in (0,2,4)]
    assert max(dims) <= base.BED-4, (path.name, 'bed', dims)
    result = base.export(posed, path)
    for ext in ('.stl', '.3mf'):
        m = Mesh.Mesh(str(path.with_suffix(ext)))
        assert m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections(), path.name+ext
        assert abs(m.Volume-posed.Volume)/posed.Volume < 0.002, path.name+ext+' volume'
        b = m.BoundBox
        # Rotated circular outlines need not have a tessellation vertex at each
        # analytic XY extremum: allow the exporter's 0.005 mm chordal tolerance
        # plus <=0.001 mm 3MF decimal rounding. The planar bed face MUST be Z=0.
        assert -1e-5 <= b.XMin < 0.006 and -1e-5 <= b.YMin < 0.006, 'mesh XY exceeds tessellation tolerance'
        assert abs(b.ZMin) < 1e-5, 'mesh does not touch the print bed'
    saved = Part.Shape()
    saved.read(str(path.with_suffix('.step')))
    assert_solid(saved, path.name+' STEP readback')
    assert saved.cut(posed).Volume+posed.cut(saved).Volume < TOL
    return {'print_bounds_mm':dims, 'in_plane_print_rotation_deg':angle,
            'solid_volume_cm3':round(posed.Volume/1000,3),
            'STEP_STL_3MF_readback':'PASS', **result}


def save_native(path, objects):
    doc = App.newDocument(path.stem.replace('-', '_'))
    for name, shape in objects.items():
        obj = doc.addObject('Part::Feature', name.replace('-', '_'))
        obj.Shape = shape
        obj.Label = name.replace('_', ' ').replace('-', ' ').title()
        for prop, value in (('UpperAngleDegrees', ANGLE), ('HexSocketAF', base.SPACER_SOCKET_AF),
                            ('HexSocketDepth', base.SPACER_SOCKET_DEPTH), ('MountScrewLength', SCREW_L),
                            ('RubberPadSize', RUBBER_PAD_SIZE), ('RearFootWidth', FOOT_WIDTH),
                            ('RearFootLength', FOOT_LENGTH)):
            obj.addProperty('App::PropertyFloat', prop, 'Build metadata')
            setattr(obj, prop, value)
            obj.setEditorMode(prop, 1)
        obj.addProperty('App::PropertyString', 'Regenerate', 'Build metadata')
        obj.Regenerate = 'case/tools/build_angle_joiner.sh; dimensions in build_angle_joiner.py'
    doc.recompute()
    tmp = path.with_name('.'+path.name)
    doc.saveAs(str(tmp))
    App.closeDocument(doc.Name)
    check = App.openDocument(str(tmp))
    for name, expected in objects.items():
        got = check.getObject(name.replace('-', '_')).Shape
        assert_solid(got, name+' FCStd reload')
        assert got.cut(expected).Volume+expected.cut(got).Volume < TOL
    App.closeDocument(check.Name)
    tmp.replace(path)


def coupons(d):
    panel = base.box((-d.T, -10, -10), (d.T, 20, 20))
    panel = base.cut_all(panel, [base.end_spacer_socket(0, -1, 0, 0),
                                base.cyl(base.M3_CLEAR/2, d.T+2, (-d.T-1,0,0), (1,0,0))])
    plate = base.box((-d.T-PLATE_T, -10, -10), (PLATE_T, 20, 20))
    plate = base.cut_all(plate, [base.cyl(base.M3_CLEAR/2, PLATE_T+2, (-d.T-PLATE_T-1,0,0), (1,0,0)),
                                base.cyl(base.M3_CB_D/2, CB_DEPTH+1, (-d.T-PLATE_T-1,0,0), (1,0,0))])
    return {'fit-socket':panel, 'fit-plate':plate}


def main():
    d = base.Dims(42, 60, 0.5, base.module_panels())
    layout = Layout(d)
    source, differences = common.source_parts(d)
    parts = {'side-panel-left':side_panel(d, True), 'side-panel-right':side_panel(d, False),
             'joiner-left':plate(d, layout, True), 'joiner-right':plate(d, layout, False)}
    asm = assembly(d, layout, source, parts)
    checks, hardware = verify(d, layout, source, parts, asm)
    out = CASE/'print'/'side panels'/'angle-joiner'
    research = CASE/'research'/'angle-joiner'
    for folder in (out, research, CASE/'cad'):
        folder.mkdir(parents=True, exist_ok=True)
    save_native(CASE/'cad'/'angle-joiner-parts.FCStd', parts)
    save_native(CASE/'cad'/'angle-joiner-assembly.FCStd', {**asm, **hardware})
    report = {'status':'PASS', 'source':'cad/assembly.FCStd', 'source_difference_mm3':differences,
              'geometry':{'lower_angle_deg':0, 'upper_angle_deg':ANGLE, 'panel_included_angle_deg':180-ANGLE,
                          'upper_front_edge_gap_y_z_mm':[GAP_Y,GAP_Z],
                          'upper_origin_y_z_mm':[layout.ty,layout.tz], 'plate_thickness_mm':PLATE_T,
                          'mount_pattern_y_z_mm':[list(MOUNT_Y),list(MOUNT_Z)],
                          'mount_pattern_pitch_mm':[MOUNT_Y[1]-MOUNT_Y[0],MOUNT_Z[1]-MOUNT_Z[0]],
                          'outside_fillet_mm':ROUND, 'window_fillet_mm':WINDOW_R,
                          'case_width_hp':d.hp, 'case_side_panel_depth_mm':d.depth,
                          'socket_AF_mm':base.SPACER_SOCKET_AF, 'socket_depth_mm':base.SPACER_SOCKET_DEPTH},
              'checks':checks, 'print':{}, 'prototype':'not printed, load-tested or rated; do not carry by plates'}
    for name, shape in {**parts, **coupons(d)}.items():
        report['print'][name] = export_part(shape, out/name, not name.endswith('right'))
    Part.makeCompound(list(asm.values())).exportStep(str(out/'assembly-preview.step'))
    # Readback of the multi-solid neutral assembly, not intended for printing.
    readback = Part.Shape()
    readback.read(str(out/'assembly-preview.step'))
    assert readback.isValid() and len(readback.Solids) == len(asm)
    expected = Part.makeCompound(list(asm.values()))
    assert abs(readback.Volume-expected.Volume) < TOL
    for name, shape in {**asm, **hardware}.items():
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.025, AngularDeflection=0.15)
        mesh.write(str(research/f'asm-{name}.stl'))
    for name, shape in parts.items():
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.025, AngularDeflection=0.15).write(str(research/f'part-{name}.stl'))
    # Underside area guides for previews ONLY, not an assumed rubber thickness
    # or extra printable parts. Real pad dimensions beyond 12 x 12 are unknown.
    for name, (cx, cy) in rubber_pad_centres(d).items():
        marker = base.box((cx-RUBBER_PAD_SIZE/2, cy-RUBBER_PAD_SIZE/2, -0.15),
                          (RUBBER_PAD_SIZE, RUBBER_PAD_SIZE, 0.15))
        MeshPart.meshFromShape(Shape=marker, LinearDeflection=0.025, AngularDeflection=0.15).write(str(research/f'pad-area-{name}.stl'))
    (research/'rubber-pad-locations.json').write_text(json.dumps(checks['rubber_pad_lands'], indent=2)+'\n')
    # Full-face display sheets only; no inference about actual knob/PCB dimensions.
    for upper, label in ((False,'lower'), (True,'upper')):
        display = base.box((d.row_x0, 0, d.top), (d.hp*base.HP,base.PANEL_H,d.panel_t))
        display = layout.place(display, upper)
        MeshPart.meshFromShape(Shape=display, LinearDeflection=0.025, AngularDeflection=0.15).write(str(research/f'display-{label}.stl'))
    report['assembly_bounds_xyz_mm'] = common.size(expected)
    files = list(out.glob('*.step')) + list(out.glob('*.stl')) + list(out.glob('*.3mf'))
    files += [CASE/'cad'/'angle-joiner-parts.FCStd',CASE/'cad'/'angle-joiner-assembly.FCStd']
    report['export_sha256'] = {str(p.relative_to(CASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    data = json.dumps(report, indent=2)+'\n'
    (out/'verification.json').write_text(data)
    (research/'build-report.json').write_text(data)
    print('ANGLE_JOINER_BUILD_PASS', flush=True)


# FreeCADCmd imports scripts by stem, unlike CPython's __main__.
if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
