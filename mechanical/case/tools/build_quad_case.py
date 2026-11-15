"""Fused flat panels for a 2 x 2 set of the existing 42 HP / 60 mm skiffs.

Build only this variant: mechanical/case/tools/build_quad_case.sh.
Original case, middle-frame and angle-joiner exports are never overwritten.

Four cases in ONE plane: two side by side, two rows deep. Each panel is one print that holds
both rows, the second one ROW_GAP behind the first:
  fused-side-left / -right   two standard side panels (build_case) end to end
  fused-middle               two shared middle frames (build_middle_frame) end to end
Between the rows each part is solid over its whole section. Outside that joint every half is
the stock part, so rails, bases, covers, screws and the side plate sockets are the stock ones:
8 rails, 4 bases, up to 8 covers.

The joint closes the two rail notches that face it on each side panel: those rails go in along
their length, as in the middle frame's blind sockets, not from the front / back.

The set also goes on the angle joiner (build_angle_joiner) as its upper element: the joiner's
upper rings bolt to the front row's sockets, the rear row stands above it. That scene is
checked here with a double-width lower row; the rear row's sockets stay free.

All coordinates are the original build_case assembly axes of the LEFT front case.
CAD-checked prototype: not printed, fit-tested or load-rated.
"""
import hashlib
import itertools
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
import build_middle_frame as common
import build_angle_joiner as joiner
import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
CASE = base.CASE
OUT = CASE/'print'/'quad-case'
RESEARCH = CASE/'research'/'quad-case'
TOL = 1e-3

ROW_GAP = 3.0        # between the two rows' stock panels, bases and rails (Y)
NOTCH_END_CLR = 0.3  # rail to the joint in the notches the joint closes
BASE_TRAVEL = 20.0   # straight way kept free under each base for putting it on (8 mm needed)
BED_MARGIN = 4.0     # free bed on each side of the diagonal print pose
ROWS = ('front', 'rear')
FUSED = ('fused_left', 'fused_middle', 'fused_right')
# Assumed masses for the tip-back estimate only (kg per case, modules included).
TIP_LOADS = {'every case loaded': (1.5, 1.5), 'lower row empty, upper rows full': (0.7, 2.5)}

box, cyl, moved = base.box, base.cyl, common.moved


def assert_solid(shape, label):
    assert shape.isValid() and len(shape.Solids) == 1, label


def clear(a, b, label):
    """No shared volume. Shapes whose boxes are apart need no boolean."""
    if not a.BoundBox.intersect(b.BoundBox):
        return 0.0
    return common.no_collision(a, b, label)


def pitch(d):
    return d.ylen + ROW_GAP


def rows(d):
    return [(ROWS[0], 0.0), (ROWS[1], pitch(d))]


def fused_side(d, left):
    """Front and rear standard side panel of one end as one part (that case's own X)."""
    y1 = d.y0 + d.ylen
    keep = d.notch_clr + d.lip_clr           # lip fillet to a rail, as on the standard panel
    stock = (d.y0+d.rail_w+keep, y1-d.rail_w-keep)
    webs = [stock, tuple(y+pitch(d) for y in stock), (y1+keep, y1+ROW_GAP-keep)]
    blank = base.side_panel_blank(d, left, d.ylen+pitch(d), webs)
    cuts = base.side_panel_cuts(d, left) + [moved(c, dy=pitch(d)) for c in base.side_panel_cuts(d, left)]
    # The joint closes the front row's rear notch and the rear row's front notch: give each
    # rail end room there, on the left under the lip too.
    x_in = 0.0 if left else d.L
    nd = d.tenon + d.notch_clr
    nx = x_in - nd if left else x_in
    size = (nd, NOTCH_END_CLR+0.5, d.rail_h+d.notch_clr)
    lip = (d.fill+1, NOTCH_END_CLR+0.5, d.notch_clr)
    for y in (y1-0.5, y1+ROW_GAP-NOTCH_END_CLR):
        cuts.append(box((nx, y, d.top-d.rail_h), size))
        if left:
            cuts.append(box((0, y, d.top), lip))
    return base.cut_all(blank, cuts)


def fused_middle(d, j, left):
    """Front and rear shared middle frame as one part (frame-local X: 0 .. j.width): one
    silhouette, solid between the rows up to the collar tops, with `left`'s lip on its right."""
    y1 = d.y0 + d.ylen
    body = common.frame_body(d, j, pitch(d), left)
    assert_solid(body, 'fused middle body')
    cuts = common.frame_cuts(d, j) + [moved(c, dy=pitch(d)) for c in common.frame_cuts(d, j)]
    # One channel between the bottom tongues, straight through under the joint.
    cuts.append(box((d.T, y1-1, d.P-1), (j.bottom_slot, ROW_GAP+2, j.bridge_z-d.P+1)))
    return base.cut_all(body, cuts)


def consistent(shape, label):
    """Booleans on this solid add up: a clip box takes exactly what the cut leaves behind."""
    b = shape.BoundBox
    for axis, at in ((0, b.Center.x), (1, b.Center.y+7), (1, b.YMin+b.YLength/4), (2, b.Center.z)):
        lo = [b.XMin-5, b.YMin-5, b.ZMin-5]
        size = [b.XLength+10, b.YLength+10, b.ZLength+10]
        size[axis] = at - lo[axis]
        clip = box(tuple(lo), tuple(size))
        inside, outside = shape.common(clip).Volume, shape.cut(clip).Volume
        assert inside > 1 and outside > 1 and abs(inside+outside-shape.Volume) < TOL, (label, axis, inside, outside)


def cases(d, j):
    return [(row, col, dy, dx) for row, dy in rows(d) for col, dx in (('left', 0.0), ('right', j.offset))]


def assembly(d, j, source, parts):
    asm = {name.replace('-', '_').replace('_side', ''): shape for name, shape in parts.items()}
    assert set(asm) == set(FUSED)
    for row, col, dy, dx in cases(d, j):
        for name in ('bottom_plate', 'rail_front', 'rail_back'):
            asm[f'{row}_{col}_{name}'] = moved(source[name], dx=dx, dy=dy)
    return asm


def same(a, b, label):
    diff = a.cut(b).Volume + b.cut(a).Volume
    assert diff < TOL, (label, 'differs from the stock part', diff)
    return round(diff, 6)


def saved(name, keys=None):
    """Solids of a saved native document in cad/."""
    doc = App.openDocument(str(CASE/'cad'/name))
    out = {o.Name: o.Shape.copy() for o in doc.Objects if hasattr(o, 'Shape') and (keys is None or o.Name in keys)}
    App.closeDocument(doc.Name)
    for key, shape in out.items():
        assert_solid(shape, f'{name}/{key}')
    assert keys is None or set(out) == set(keys), (name, sorted(out))
    return out


def tip_back(d, layout):
    """Horizontal push on the top row that lifts the lower row's front pads (static, rigid),
    next to the same estimate for today's two rows on the same plates."""
    rear = joiner.FOOT[0]
    low_y = base.PANEL_H/2

    def centre(dy):
        return layout.point(base.PANEL_H/2+dy, d.case_top/2, True)[0]

    def height(y):
        return layout.point(y, d.case_top, True)[1]

    mid_y, top_y = centre(0), centre(pitch(d))
    edge = d.y0 + d.ylen
    heights = {'three_rows': {'at_top_row_centre': height(base.PANEL_H/2+pitch(d)),
                              'at_top_edge': height(edge+pitch(d))},
               'two_rows_today': {'at_top_row_centre': height(base.PANEL_H/2), 'at_top_edge': height(edge)}}
    out = {'rear_pad_centre_y_mm': rear, 'lower_row_centre_y_mm': low_y,
           'middle_row_centre_y_mm': round(mid_y, 1), 'top_row_centre_y_mm': round(top_y, 1),
           'top_row_centre_behind_rear_pad_mm': round(top_y-rear, 1),
           'push_height_mm': {k: {n: round(h, 1) for n, h in v.items()} for k, v in heights.items()},
           'assumption': 'rigid, two cases per row, mass at each case centre, no cable pull; '
                         'an estimate to compare the two arrangements, not a rating',
           'push_to_tip_back_N': {}}
    for label, (m_low, m_up) in TIP_LOADS.items():
        two = 2*9.81*(m_low*(rear-low_y) + m_up*(rear-mid_y))
        three = two + 2*9.81*m_up*(rear-top_y)
        assert three > 0, 'the set would fall back on its own'
        out['push_to_tip_back_N'][f'{label} ({m_low} / {m_up} kg per case)'] = {
            'three_rows': {k: round(three/h, 1) for k, h in heights['three_rows'].items()},
            'two_rows_today': {k: round(two/h, 1) for k, h in heights['two_rows_today'].items()}}
    return out


def on_stand(d, j, asm):
    """The set as the upper element of the angle joiner, over a double-width lower row."""
    layout = joiner.Layout(d)
    lower = saved('double-case-assembly.FCStd')
    plates = saved('angle-joiner-parts.FCStd', ('joiner_left', 'joiner_right'))
    plates['joiner_right'] = moved(plates['joiner_right'], dx=j.offset)
    scene = {**{f'lower_{name}': shape for name, shape in lower.items()},
             **{f'upper_{name}': layout.place(shape, True) for name, shape in asm.items()}, **plates}
    upper = {name: shape for name, shape in scene.items() if name.startswith('upper_')}
    for (an, a), (bn, b) in itertools.combinations(scene.items(), 2):
        clear(a, b, f'on the stand: {an}/{bn}')
    checks = {'parts_no_interference': len(scene),
              'lower_row': 'cad/double-case-assembly.FCStd (two cases on the stock middle frame)',
              'plates': 'cad/angle-joiner-parts.FCStd, the right one moved to the double width'}
    low = min(shape.BoundBox.ZMin for shape in upper.values())
    assert low > 5, 'the set touches the desk'
    checks['set_lowest_point_above_desk_mm'] = round(low, 1)

    # The 16 plate screws and their captured spacers: the stock stack, into the lower row's
    # standard panels and the set's front row.
    hardware = {}
    for left, side, dx in ((True, 'left', 0.0), (False, 'right', j.offset)):
        plate = scene['joiner_'+side]
        for is_upper, panel in ((False, scene[f'lower_{side}_side_panel_{side}']), (True, upper['upper_fused_'+side])):
            for name, shape in joiner.fasteners(d, layout, left, is_upper).items():
                shape = moved(shape, dx=dx)
                clear(shape, plate, f'{name}/plate {side}')
                clear(shape, panel, f'{name}/panel {side}')
                hardware[f'{"upper" if is_upper else "lower"}_{side}_{name}'] = shape
        # The plate goes on from outside, after the rows are built.
        sg = 1 if left else -1
        for distance in (0.2, 1, 3, 6, 12, 25):
            sliding = moved(plate, dx=-sg*distance)
            for name, part in scene.items():
                if not name.startswith('joiner'):
                    clear(sliding, part, f'plate {side} outside approach/{name}')
        # Every outer rail screw of the set stays reachable with the plates on.
        xo = -d.T if left else j.offset+d.L+d.T
        z = d.top - d.rail_h/2
        for dy in (0.0, pitch(d)):
            for y in d.hole_y:
                py, pz = layout.point(y+dy, z, True)
                clear(cyl(2.75, 3, (xo-sg*3, py, pz), (sg, 0, 0)), plate, 'rail screw head')
                clear(cyl(2.5, 45, (xo-sg*45, py, pz), (sg, 0, 0)), plate, 'rail screw driver')
    shoulder = d.T - base.SPACER_SOCKET_DEPTH
    checks['plate_hardware'] = {'M3x8_screws': 16, 'M3x10_hex_spacers': 16,
                                'thread_engagement_mm': round(joiner.SCREW_L-joiner.GRIP-shoulder, 3),
                                'hardware_solids_clear': True,
                                'plate_outside_approach_samples_clear_mm': [0.2, 1, 3, 6, 12, 25],
                                'set_outer_rail_screws_reachable': 8,
                                'rear_row_sockets': '8, left empty'}
    whole = Part.makeCompound(list(scene.values()))
    checks['bounds_xyz_mm'] = common.size(whole)
    checks['tip_back'] = tip_back(d, layout)
    return checks, scene, hardware


def verify(d, j, parts, asm):
    checks = {}
    for name, shape in asm.items():
        assert_solid(shape, name)
    fused = {name: asm[name] for name in FUSED}
    for name, shape in fused.items():
        consistent(shape, name)
    for (an, a), (bn, b) in itertools.combinations(asm.items(), 2):
        clear(a, b, an+'/'+bn)
    checks['assembly_pairs_no_interference'] = len(asm)*(len(asm)-1)//2
    y1 = d.y0 + d.ylen

    # Outside the joint each half IS the stock part: every rail, base, cover, module and side
    # plate interface checked by build_case / build_middle_frame is unchanged. The halves are
    # compared up to the stock parts' own facing edges.
    half = {'front': box((-50, -50, -50), (700, 50+y1, 200)),
            'rear': box((-50, y1+ROW_GAP, -50), (700, 200, 200))}
    frame = moved(common.frame(d, j), dx=d.L)
    stock = {}
    for row, dy in rows(d):
        for left, name, dx in ((True, 'fused_left', 0.0), (False, 'fused_right', j.offset)):
            stock[f'{name}/{row}'] = same(fused[name].common(half[row]),
                                          moved(base.side_panel(d, left), dx=dx, dy=dy), f'{name}/{row}')
        stock[f'fused_middle/{row}'] = same(fused['fused_middle'].common(half[row]),
                                            moved(frame, dy=dy).common(half[row]), f'fused_middle/{row}')
    checks['stock_geometry_outside_the_joint_diff_mm3'] = stock
    # The joint itself: solid from face to face under the rail notches on the side panels,
    # and right through the middle part.
    for left, name, dx in ((True, 'fused_left', 0.0), (False, 'fused_right', j.offset)):
        x0 = dx + (-d.T if left else d.L)
        core = box((x0, y1-10, d.P), (d.T, ROW_GAP+20, d.top-d.rail_h-d.P-3))
        grooves = Part.makeCompound([box((x0-1, gy+dy-0.01, d.P-1), (d.T+2, d.groove_w+0.02, d.depth))
                                     for gy in d.groove_y for _, dy in rows(d)])
        assert core.cut(grooves).cut(fused[name]).Volume < TOL, name+': joint is not solid'
    core = moved(box((0, y1, d.P), (j.width, ROW_GAP, j.collar_top-d.P)), dx=d.L)
    opened = core.cut(fused['fused_middle']).Volume
    checks['joint'] = {'row_gap_mm': ROW_GAP, 'side_panel_section_mm': [d.T, round(d.top-d.rail_h-d.P, 2)],
                       'side_panel_wall_between_closed_notches_mm': round(ROW_GAP-2*NOTCH_END_CLR, 2),
                       'middle_wall_between_rail_sockets_mm': round(ROW_GAP-2*common.RAIL_CLEARANCE, 2),
                       'middle_joint_solid_fraction': round(1-opened/core.Volume, 3)}

    rail_z = d.top - d.rail_h
    span = d.cover_blank_size()['plate'][0]
    sock = d.T + d.socket_clr
    above = {}
    for row, col, dy, dx in cases(d, j):
        label = f'{row}_{col}'

        def place(shape):
            return moved(shape, dx=dx, dy=dy)

        # Rails go in along X: each end's whole travel and a 0.15 mm fit gauge at its seat.
        for ry in d.rail_y:
            for x_end, sgn in ((-d.tenon, 1), (d.L+d.tenon, -1)):
                x0 = x_end if sgn > 0 else x_end-d.tenon-30
                travel = place(box((x0, ry, rail_z), (d.tenon+30, d.rail_w, d.rail_h)))
                gx = x_end if sgn > 0 else x_end-d.tenon
                gauge = place(box((gx+1e-4, ry-0.15, rail_z+1e-4),
                                  (d.tenon-2e-4, d.rail_w+0.3, d.rail_h+0.15)))
                for name, part in fused.items():
                    clear(travel, part, f'{label} rail travel/{name}')
                    clear(gauge, part, f'{label} rail gauge/{name}')
        # Stock covers: seated, and their whole way in from the open bottom.
        for i in (0, 1):
            cover = place(base.cover_blank(d, i))
            for name, part in asm.items():
                clear(cover, part, f'{label} cover {i}/{name}')
            gy = d.groove_y[i] + (d.groove_w-d.cover_t)/2
            travel = place(box((-(d.groove_d-d.cover_clr), gy, -d.depth),
                               (span, d.cover_t, d.cover_z1+d.depth)))
            for name, part in fused.items():
                clear(travel, part, f'{label} cover {i} travel/{name}')
        # Base: everything under its floor and its four socket walls, as it comes on from below.
        x0 = d.plate_x0
        travel = [box((x0, d.y0, -BASE_TRAVEL), (d.plate_len, d.ylen, BASE_TRAVEL+d.P))]
        for sx in (x0, x0+d.plate_len-(2*d.wall+sock)):
            travel += [box((wx, d.y0, -BASE_TRAVEL), (d.wall, d.ylen, BASE_TRAVEL+d.P+d.socket_h))
                       for wx in (sx, sx+d.wall+sock)]
        for name, part in fused.items():
            for t in travel:
                clear(place(t), part, f'{label} base travel/{name}')
        # Module row and a plain 10 mm envelope above its face.
        panel = place(box((d.row_x0, 0, d.top), (d.hp*base.HP, base.PANEL_H, d.panel_t)))
        above[label] = place(box((d.row_x0, 0, d.case_top), (d.hp*base.HP, base.PANEL_H, 10)))
        for name, part in asm.items():
            clear(panel, part, f'{label} module row/{name}')
            clear(above[label], part, f'{label} 10 mm above the face/{name}')
    checks['module_faces_gap_between_rows_mm'] = round(
        above['front_left'].distToShape(above['rear_left'])[0], 3)
    checks['rails_enter_along_x_with_0.15mm_gauge'] = 'PASS, 16 rail ends'
    checks['stock_covers_seated_and_bottom_entry_clear'] = 'PASS, 8 covers'
    checks['bases_come_on_from_below'] = f'PASS, 4 bases, {BASE_TRAVEL:g} mm straight travel'
    checks['bases_gap_between_rows_mm'] = round(
        asm['front_left_bottom_plate'].distToShape(asm['rear_left_bottom_plate'])[0], 3)
    checks['module_rows_and_10mm_above_face_clear'] = 'PASS, 4 rows'

    # The eight outer rail screws: head and straight driver from outside, nothing in the way.
    for sg, xo in ((1, -d.T), (-1, j.offset+d.L+d.T)):
        for _, dy in rows(d):
            for y in d.hole_y:
                z = d.top - d.rail_h/2
                head = cyl(2.75, 3, (xo-sg*3, y+dy, z), (sg, 0, 0))
                tool = cyl(2.5, 45, (xo-sg*45, y+dy, z), (sg, 0, 0))
                for name, part in fused.items():
                    clear(head, part, 'rail screw head/'+name)
                    clear(tool, part, 'rail screw driver/'+name)
    checks['outer_rail_screws'] = {'count': 8, 'head_and_driver_access': 'PASS', 'middle_rail_screws': 0}

    # Side plate sockets: both halves of both side panels carry the standard four, with the
    # stock spacer pocket, capture shoulder and side walls.
    shoulder = d.T - base.SPACER_SOCKET_DEPTH
    for sg, xo, name in ((1, -d.T, 'fused_left'), (-1, j.offset+d.L+d.T, 'fused_right')):
        for _, dy in rows(d):
            for y in joiner.MOUNT_Y:
                for z in joiner.MOUNT_Z:
                    gauge = joiner.hex_prism(xo+sg*(shoulder+0.001), y+dy, z, base.SPACER_SOCKET_DEPTH-0.002,
                                             sg, base.SPACER_SOCKET_AF-0.002)
                    clear(gauge, fused[name], 'side plate spacer pocket')
                    ring = cyl(2.65, shoulder-0.002, (xo+sg*0.001, y+dy, z), (sg, 0, 0))
                    ring = ring.cut(cyl(base.M3_CLEAR/2+0.001, d.T+2, (xo-sg, y+dy, z), (sg, 0, 0)))
                    assert ring.cut(fused[name]).Volume < TOL, 'missing capture shoulder'
                    loading = joiner.hex_prism(xo+sg*d.T, y+dy, z, 16, sg, 5.5)
                    for other, part in asm.items():
                        clear(loading, part, f'spacer loading from inside/{other}')
    checks['side_plate_sockets'] = {'count': 16, 'pattern_y_z_mm': [list(joiner.MOUNT_Y), list(joiner.MOUNT_Z)],
                                    'rear_row_offset_y_mm': pitch(d),
                                    'outer_capture_shoulder_mm': round(shoulder, 3),
                                    'pocket_gauge_and_inside_loading': 'PASS'}

    # The existing 6 HP top brace of the middle frame: reported, not required.
    brace = saved('middle-brace.FCStd', ('top_brace',))['top_brace']
    fits = {}
    for row, dy in rows(d):
        hit = sum(moved(brace, dy=dy).common(part).Volume for part in asm.values())
        fits[row] = 'fits' if hit < TOL else f'collides, {hit:.1f} mm3'
    checks['existing_middle_top_brace'] = fits
    checks['native_single_solids'] = True
    return checks


def save_native(path, objects, d):
    doc = App.newDocument(path.stem.replace('-', '_'))
    for name, shape in objects.items():
        obj = doc.addObject('Part::Feature', name.replace('-', '_'))
        obj.Shape = shape
        obj.Label = name.replace('_', ' ').replace('-', ' ').title()
        for prop, value in (('RowGap', ROW_GAP), ('RowPitch', pitch(d)), ('NotchEndClearance', NOTCH_END_CLR)):
            obj.addProperty('App::PropertyFloat', prop, 'Build metadata')
            setattr(obj, prop, value)
            obj.setEditorMode(prop, 1)
        obj.addProperty('App::PropertyString', 'Regenerate', 'Build metadata')
        obj.Regenerate = 'mechanical/case/tools/build_quad_case.sh; dimensions in build_quad_case.py'
    doc.recompute()
    tmp = path.with_name('.'+path.name)
    doc.saveAs(str(tmp))
    App.closeDocument(doc.Name)
    check = App.openDocument(str(tmp))
    for name, expected in objects.items():
        got = check.getObject(name.replace('-', '_')).Shape
        assert got.isValid() and len(got.Solids) == 1, name+' FCStd reload'
        assert got.cut(expected).Volume + expected.cut(got).Volume < TOL
    App.closeDocument(check.Name)
    tmp.replace(path)


TMF_FILES = {
    '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
    ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
    ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
    '</Types>\n',
    '_rels/.rels': '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
    '</Relationships>\n'}


def write_3mf(mesh, path):
    """Geometry-only 3MF of the STL's mesh at full float precision.

    FreeCAD's writer keeps six significant digits: 1 um on these 250 mm parts, which folds the
    thinnest facets of the lip's 0.5 mm round over each other once the part is turned on the bed.
    """
    points, tris = mesh.Topology
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
             ' <metadata name="Application">big-modular mechanical/case/tools/build_quad_case.py</metadata>',
             ' <resources>', '  <object id="1" type="model">', '   <mesh>', '    <vertices>']
    model += [f'     <vertex x="{p.x:.9g}" y="{p.y:.9g}" z="{p.z:.9g}"/>' for p in points]
    model += ['    </vertices>', '    <triangles>']
    model += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
    model += ['    </triangles>', '   </mesh>', '  </object>', ' </resources>',
              ' <build>', '  <item objectid="1"/>', ' </build>', '</model>']
    with zipfile.ZipFile(path, 'w') as archive:
        for name, text in {**TMF_FILES, '3D/3dmodel.model': '\n'.join(model)+'\n'}.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))   # fixed date: same bytes on a rebuild
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text)


def export_part(shape, path, left):
    """Print pose (outer / left-bay face down, diagonal if it has to be), then STEP, STL and 3MF
    with readback."""
    posed, angle = joiner.print_pose(shape, left)
    b = joiner.bounds(posed)
    dims = [round(b[i+1]-b[i], 3) for i in (0, 2, 4)]
    assert max(dims[:2]) <= base.BED - 2*BED_MARGIN, (path.name, 'bed', dims)
    posed.exportStep(str(path.with_suffix('.step')))
    mesh = MeshPart.meshFromShape(Shape=posed, LinearDeflection=0.005, AngularDeflection=0.1)
    mesh.write(str(path.with_suffix('.stl')))
    write_3mf(Mesh.Mesh(str(path.with_suffix('.stl'))), path.with_suffix('.3mf'))
    for ext in ('.stl', '.3mf'):
        m = Mesh.Mesh(str(path.with_suffix(ext)))
        assert m.isSolid() and not m.hasNonManifolds() and not m.hasSelfIntersections(), path.name+ext
        assert abs(m.Volume-posed.Volume)/posed.Volume < 0.002, path.name+ext+' volume'
        mb = m.BoundBox
        # Turned arcs need no tessellation vertex at their XY extreme; the bed face must be Z = 0.
        assert -1e-5 <= mb.XMin < 0.006 and -1e-5 <= mb.YMin < 0.006, 'mesh XY exceeds tessellation tolerance'
        assert abs(mb.ZMin) < 1e-5, 'mesh does not touch the print bed'
    saved = Part.Shape()
    saved.read(str(path.with_suffix('.step')))
    assert_solid(saved, path.name+' STEP readback')
    assert saved.cut(posed).Volume + posed.cut(saved).Volume < TOL
    return {'print_bounds_mm': dims, 'in_plane_print_rotation_deg': angle,
            'free_bed_per_side_mm': round((base.BED-max(dims[:2]))/2, 2),
            'solid_volume_cm3': round(posed.Volume/1000, 3), 'stl_facets': mesh.CountFacets,
            'STEP_STL_3MF_readback': 'PASS'}


def stl(shape, path):
    MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.025, AngularDeflection=0.15).write(str(path))


def main():
    d = base.Dims(42, 60, 0.5, base.module_panels())
    j = common.Join(d)
    source, differences = common.source_parts(d)
    # The saved middle frame is the same solid this generator fuses.
    differences['middle_frame'] = same(saved('middle-frame.FCStd', ('middle_frame',))['middle_frame'],
                                       common.frame(d, j), 'cad/middle-frame.FCStd')

    left = fused_side(d, True)
    parts = {'fused-side-left': left,
             'fused-middle': moved(fused_middle(d, j, left), dx=d.L),
             'fused-side-right': moved(fused_side(d, False), dx=j.offset)}
    asm = assembly(d, j, source, parts)
    checks = verify(d, j, parts, asm)
    checks['on_the_angle_joiner'], scene, hardware = on_stand(d, j, asm)
    for folder in (OUT, RESEARCH, CASE/'cad'):
        folder.mkdir(parents=True, exist_ok=True)
    for old in list(RESEARCH.glob('*.stl')):
        old.unlink()
    natives = {'quad-case-parts.FCStd': parts, 'quad-case-assembly.FCStd': asm,
               'quad-case-on-stand.FCStd': {**scene, **hardware}}
    for name, objects in natives.items():
        save_native(CASE/'cad'/name, objects, d)

    whole = Part.makeCompound(list(asm.values()))
    report = {'status': 'PASS',
              'source': ['cad/assembly.FCStd', 'cad/middle-frame.FCStd', 'cad/double-case-assembly.FCStd',
                         'cad/angle-joiner-parts.FCStd', 'cad/middle-brace.FCStd'],
              'source_difference_mm3': differences,
              'geometry': {'rows': 2, 'cases_per_row': 2, 'rows_in_one_plane': True,
                           'row_gap_mm': ROW_GAP, 'row_pitch_mm': pitch(d),
                           'side_panel_thickness_mm': d.T, 'middle_frame_width_mm': round(j.width, 3),
                           'closed_notch_rail_end_clearance_mm': NOTCH_END_CLR,
                           'case_width_hp': d.hp, 'case_side_panel_depth_mm': d.depth},
              'checks': checks, 'print': {},
              'assembly_bounds_xyz_mm': common.size(whole),
              'hardware': {'outer_rail_screws': '8 existing M3x10, through the two fused side panels',
                           'middle_rail_screws': 0,
                           'base_screws': '16 existing M3x6, four per base',
                           'base_spacers': '16 M3x10 female hex spacers glued into the bottom sockets',
                           'on_the_angle_joiner': '8 M3x8 socket head + 8 M3x10 hex spacers loaded from inside '
                                                  'the front row (the plates\' upper rings), as on a single case'},
              'prototype': 'not printed, fit-tested or load-rated'}
    for name, shape in parts.items():
        report['print'][name] = export_part(shape, OUT/name, not name.endswith('right'))
    whole.exportStep(str(OUT/'assembly-preview.step'))
    readback = Part.Shape()
    readback.read(str(OUT/'assembly-preview.step'))
    assert readback.isValid() and len(readback.Solids) == len(asm)
    assert abs(readback.Volume-whole.Volume) < TOL

    # Preview meshes only: not print files.
    for name, shape in asm.items():
        stl(shape, RESEARCH/f'asm-{name}.stl')
    for name, shape in {**scene, **hardware}.items():
        stl(shape, RESEARCH/f'stand-{name}.stl')
    for name, shape in parts.items():
        stl(shape, RESEARCH/f'part-{name}.stl')
    layout = joiner.Layout(d)
    for row, col, dy, dx in cases(d, j):
        sheet = box((dx+d.row_x0, dy, d.top), (d.hp*base.HP, base.PANEL_H, d.panel_t))
        stl(sheet, RESEARCH/f'display-{row}-{col}.stl')
        stl(layout.place(sheet, True), RESEARCH/f'stand-display-upper-{row}-{col}.stl')
    for col, dx in (('left', 0.0), ('right', j.offset)):
        stl(box((dx+d.row_x0, 0, d.top), (d.hp*base.HP, base.PANEL_H, d.panel_t)),
            RESEARCH/f'stand-display-lower-{col}.stl')
    b = whole.BoundBox
    sb = Part.makeCompound(list(scene.values())).BoundBox
    (RESEARCH/'camera.json').write_text(json.dumps(
        {'centre': [round(v, 3) for v in (b.Center.x, b.Center.y, b.Center.z)],
         'size': common.size(whole), 'middle_x': round(d.L+j.width/2, 3),
         'joint_y': round(d.y0+d.ylen+ROW_GAP/2, 3), 'right_x': round(j.offset+d.L+d.T/2, 3),
         'stand_centre': [round(v, 3) for v in (sb.Center.x, sb.Center.y, sb.Center.z)],
         'stand_size': [round(v, 3) for v in (sb.XLength, sb.YLength, sb.ZLength)]}, indent=2)+'\n')

    files = sorted(p for p in OUT.iterdir() if p.suffix in ('.step', '.stl', '.3mf'))
    files += [CASE/'cad'/name for name in natives]
    report['export_sha256'] = {str(p.relative_to(CASE)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in files}
    data = json.dumps(report, indent=2)+'\n'
    (OUT/'verification.json').write_text(data)
    (RESEARCH/'build-report.json').write_text(data)
    print('QUAD_CASE_BUILD_PASS', flush=True)


# FreeCADCmd imports scripts by stem, unlike CPython's __main__.
if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
