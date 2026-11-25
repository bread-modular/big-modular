"""End-to-end dock for two standard skiffs. X across the case; v up the case;
 n out from a cover's outer face. In local CAD, (x, v, n) = FreeCAD (X, Y, Z).
 The original grooves capture each cover; the exposed dovetails do the docking.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_case as base
from build_middle_frame import moved, source_parts
from build_cable_holder import export_part, overhangs
import FreeCAD as App
import MeshPart
import Part

V = App.Vector
OUT = base.CASE / 'print/covers/case-dock'
RESEARCH = base.CASE / 'research/case-dock'
CAD = base.CASE / 'cad'
RAIL_INSET = 24.0                  # inward from each side panel's inside face
RAIL_W = 28.0                      # outer receiver width / pin grip length
GAP = 8.0                          # between case shells, at the seam
RECEIVER_TOP = 44.0
TRAVEL = 35.0                      # lift guest vertical to clear both rails
PIN_V, PIN_N, PIN_D = 28.0, 6.45, 3.4
STOP_V, TAIL_V = 10.4, 10.7        # 0.3 mm free above stop on a level desk
LEAD = 1.2                         # tapered first 1.2 mm at the nose of the tail
TOL = 1e-3

# Sections in (x relative to rail centre, n from the receiver's cover).
# Cavity is open at n=9.4. Both print profiles overhang by at most 45 degrees.
CAVITY = [(-9.05, 3.0), (9.05, 3.0), (4.3, 8.0), (4.3, 10.0),
          (-4.3, 10.0), (-4.3, 8.0)]
TAIL = [(-8.17, 3.4), (8.17, 3.4), (3.8, 8.0), (3.8, 9.7),
        (11, 12.5), (-11, 12.5), (-3.8, 9.7), (-3.8, 8.0)]


def face_wire(points):
    return Part.makePolygon(points + [points[0]])


def section(profile, xc, v, separation=None):
    return face_wire([V(xc + x, v, n if separation is None else separation - n)
                      for x, n in profile])


def extrude(profile, xc, v0, v1, separation=None):
    return Part.Face(section(profile, xc, v0, separation)).extrude(V(0, v1-v0, 0))


def pin_hole(xc, n):
    """Teardrop with a Ø3.4 mm round shank zone and a printable roof with margin below 45°."""
    r = PIN_D / 2
    slope = math.radians(43)
    a, b = r * math.cos(slope), r * math.sin(slope)
    x = xc - RAIL_W / 2 - 1
    left, bottom, right, top = (V(x, PIN_V+dv, n+dn)
                               for dv, dn in ((-a, b), (0, -r), (a, b), (0, r / math.sin(slope))))
    return Part.Face(Part.Wire([Part.Arc(left, bottom, right).toShape(),
                               Part.makeLine(right, top), Part.makeLine(top, left)])).extrude(V(RAIL_W+2, 0, 0))


def solid(shape, label):
    assert shape.isValid() and len(shape.Solids) == 1, label
    return shape


def blank(d, front_y):
    s = moved(base.cover_blank(d, 0), dy=-front_y)
    s.rotate(V(), V(1, 0, 0), -90)
    return s


def receiver_at(x):
    body = base.box((x - RAIL_W/2, 7.5, -0.1), (RAIL_W, RECEIVER_TOP - 7.5, 9.5))
    return body.cut(extrude(CAVITY, x, STOP_V, RECEIVER_TOP + 1)).cut(pin_hole(x, PIN_N)).removeSplitter()


def tail_at(x, separation):
    nose = [(a - math.copysign(1, a), n) for a, n in TAIL]
    ramp = Part.makeLoft([section(nose, x, TAIL_V, separation),
                         section(TAIL, x, TAIL_V + LEAD, separation)], True, True)
    body = extrude(TAIL, x, TAIL_V + LEAD, 43, separation).fuse(ramp)
    return body.cut(pin_hole(x, separation - PIN_N)).removeSplitter()


def at_cover(shape, y, rear):
    s = shape.mirror(V(), V(0, 0, 1)) if rear else shape.copy()
    s.rotate(V(), V(1, 0, 0), 90)
    s.translate(V(0, y, 0))
    return s


def posed(shape):
    b = shape.optimalBoundingBox(False, False)
    return moved(shape, -b.XMin, -b.YMin, -b.ZMin)


def collision(s, obstacles):
    return max((s.common(o).Volume for o in obstacles), default=0)


def clear(s, obstacles, label):
    v = collision(s, obstacles)
    assert v < TOL, (label, v)
    return round(v, 6)


def save_native(stem, named):
    doc = App.newDocument(stem.replace('-', '_'))
    for name, shape in named.items():
        obj = doc.addObject('Part::Feature', name)
        obj.Label = name.replace('_', ' ').title()
        obj.Shape = shape
    doc.recompute()
    dst = CAD / (stem + '.FCStd')
    tmp = dst.with_name('.' + dst.name)
    doc.saveAs(str(tmp))
    App.closeDocument(doc.Name)
    check = App.openDocument(str(tmp))
    for name, s in named.items():
        t = solid(check.getObject(name).Shape, name + ' readback')
        assert t.cut(s).Volume + s.cut(t).Volume < TOL, name
    App.closeDocument(check.Name)
    tmp.replace(dst)


def render_meshes(named, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for name, s in named.items():
        MeshPart.meshFromShape(Shape=s, LinearDeflection=0.04,
                               AngularDeflection=0.15).write(str(dst / (name + '.stl')))


def main():
    d = base.Dims(42, 60, 0.5, base.module_panels())
    case, source_difference = source_parts(d)
    inset = d.groove_edge + (d.groove_w - d.cover_t) / 2
    front_y, rear_y = d.y0 + inset, d.y0 + d.ylen - inset
    separation = GAP + 2*inset
    offset = d.ylen + GAP
    assert abs(front_y + offset - rear_y - separation) < 1e-6
    centres = (RAIL_INSET, d.L - RAIL_INSET)
    old_blank = blank(d, front_y)
    beam = base.box((4.5, 14, -0.1), (d.L - 9, 24, 1.9))
    receiver = solid(old_blank.fuse([beam, *map(receiver_at, centres)]).removeSplitter(), 'receiver')
    slider = solid(old_blank.fuse([beam, *(tail_at(x, separation) for x in centres)]).removeSplitter(), 'slider')
    a, b = at_cover(receiver, rear_y, True), at_cover(slider, front_y + offset, False)
    frame = {k: s for k, s in case.items() if k != 'bottom_plate'}
    other = {k: moved(s, dy=offset) for k, s in case.items()}
    front_cover = base.cover_blank(d, 0)
    back_cover = moved(base.cover_blank(d, 1), dy=offset)

    # Install each cover once from below: occupied rectangle (full width) for the original
    # plate, and a separate conservative envelope for all exterior features. The original
    # corner reliefs are needed only once the stock bottom is reinstalled.
    ow = old_blank.BoundBox
    install = {}
    for label, shape, y, rear in (('receiver', receiver, rear_y, True),
                                  ('slider', slider, front_y, False)):
        high = shape.BoundBox
        plate_sweep = base.box((ow.XMin, -d.depth, -d.cover_t),
                               (ow.XLength, d.depth + ow.YMax, d.cover_t))
        addon_sweep = base.box((4.5, -d.depth, 0), (d.L - 9, d.depth + RECEIVER_TOP, high.ZMax))
        for s in (plate_sweep, addon_sweep):
            clear(at_cover(s, y, rear), frame.values(), label + ' continuous installation sweep')
        assembled = at_cover(shape, y, rear)
        clear(assembled, case.values(), label + ' with original bottom plate fitted')
        # At z=34 the ends overlap both side panels by 2.7 mm. Push/pull shows capture.
        for sign in (-1, 1):
            assert all(collision(moved(assembled, dy=sign*0.5), [case[k]]) > TOL
                       for k in ('side_panel_left', 'side_panel_right')), label + ' groove retention'
        install[label] = {'continuous_bottom_install': 'PASS', 'stock_bottom_refit': 'PASS',
                          'both_side_grooves_capture_cover': 'PASS'}

    # Exact conservative docking sweep: bury the taper and pin hole in the full tail
    # section and sweep this along v, so there is no undetected intermediate collision.
    for x in centres:
        sweep = extrude(TAIL, x, TAIL_V, 43 + TRAVEL, separation)
        clear(at_cover(sweep, front_y+offset, False), [a, *case.values()], 'continuous docking sweep')
    # Other guest solids travel parallel to Y=constant planes, never crossing receiver.
    assert a.BoundBox.YMax < min(o.BoundBox.YMin for o in other.values())
    assert b.BoundBox.YMin > max(o.BoundBox.YMax for o in case.values())
    assert a.BoundBox.YMax < b.BoundBox.YMax and a.BoundBox.YMax < front_y + offset - 1.8
    assert rear_y + 1.8 < b.BoundBox.YMin  # receiver beam vs the tail at all heights
    assert TRAVEL + TAIL_V > RECEIVER_TOP
    clear(b, [a, *case.values(), *other.values()], 'seated slider')
    clear(a, [*case.values(), *other.values()], 'seated receiver')
    clear(moved(b, dz=TRAVEL, dy=20), [a, *case.values()], 'released slider')
    # Keep the second cover's remote face and its 1.8 mm beam clear throughout.
    assert b.BoundBox.YMax >= front_y + offset + d.cover_t - 1e-6
    lateral_checks = {key: round(collision(moved(b, *shift), [a]), 4)
                      for key, shift in {'left': (-1, 0, 0), 'right': (1, 0, 0),
                                         'pull_apart': (0, 1, 0), 'push_together': (0, -1, 0),
                                         'lower_through_stop': (0, 0, -1)}.items()}
    assert min(lateral_checks.values()) > TOL, lateral_checks

    # One optional M3x35 bolt, accessible along X from either side at the seam;
    # the 6.4 mm cylindrical envelope also gives room for a socket head and hex nut.
    x = centres[0]
    y = rear_y + PIN_N
    pin = Part.makeCylinder(1.5, 35, V(x-RAIL_W/2, y, PIN_V), V(1, 0, 0))
    tool_envelope = Part.makeCylinder(3.2, d.L+2*d.T+20, V(-d.T-10, y, PIN_V), V(1, 0, 0))
    clear(pin, [a, b, *case.values(), *other.values()], 'locking bolt fit')
    clear(tool_envelope, [*case.values(), *other.values()], 'bolt access in the gap')
    assert collision(moved(b, dz=1), [pin]) > TOL, 'locking bolt cannot stop lifting'

    for directory in (OUT, RESEARCH, CAD):
        directory.mkdir(parents=True, exist_ok=True)
    # Coupon pair: identical dovetails and bolt holes on short sections of the actual covers.
    crop = base.box((x-18, 6, -2.2), (36, 39, 13.2))
    parts = {'dock-receiver-cover': posed(receiver), 'dock-slider-cover': posed(slider),
             'fit-receiver': posed(solid(receiver.common(crop).removeSplitter(), 'receiver coupon')),
             'fit-slider': posed(solid(slider.common(crop).removeSplitter(), 'slider coupon'))}
    files = {n: {**overhangs(s), **export_part(s, OUT/n)} for n, s in parts.items()}
    save_native('case-dock-parts', {n.replace('-', '_'): s for n, s in parts.items()})

    named = {**{f'Host_{k}': s for k, s in case.items()},
             **{f'Guest_{k}': s for k, s in other.items()},
             'Host_free_cover': front_cover, 'Guest_free_cover': back_cover,
             'Dock_receiver': a, 'Dock_slider': b}
    Part.makeCompound(list(named.values())).exportStep(str(OUT/'assembly-preview.step'))
    save_native('case-dock-assembly', named)
    render_meshes(named, RESEARCH/'seated')
    render_meshes({k: moved(s, dz=TRAVEL) if k.startswith('Guest_') or k == 'Dock_slider' else s
                   for k, s in named.items()}, RESEARCH/'loading')
    render_meshes({'Dock_receiver': receiver, 'Dock_slider': moved(slider, dy=55)}, RESEARCH/'detail')
    report = {'source_difference_mm3': source_difference, 'cover_installation': install,
              'case_shell_gap_mm': GAP, 'minimum_vertical_docking_travel_mm': round(RECEIVER_TOP-TAIL_V, 2),
              'checked_vertical_travel_mm': TRAVEL, 'continuous_sweep': 'PASS',
              'seat_clearance_to_stop_mm': round(TAIL_V-STOP_V, 3),
              'dovetail_flank_clearance_x_mm': 0.5, 'dovetail_floor_clearance_mm': 0.4,
              'interference_at_1_mm_displacement_from_seat_mm3': lateral_checks,
              'optional_M3x35_bolt': 'PASS: fits seated, blocks lift; both case shells clear the tool envelope',
              'print': files, 'physical_fit_and_load': 'not tested'}
    (RESEARCH/'verification.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
