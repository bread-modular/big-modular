"""Generate the 3D-printable USB-AUDIO 6HP front panel with FreeCAD.

Run headless from modules/usb-audio:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py

Outline and NPTH holes are read from the native panel PCB
(../front-pcb/usb-audio-panel.kicad_pcb) and asserted against docs/geometry.json, so the
print cannot drift from the PCB panel. Plain panel: no labels (3D printed, the
FR4 panel silk legend is not carried over).
Thickness is panel_print_thickness_mm (2.0 mm, stiffer than the 1.6 mm FR4 panel);
the PJ301M-12 threads still leave ~0.5 mm past a 2.0 mm nut (as modules/midi); the
RV09 pots take no nut.
The USB-C shell stands 0.9 mm proud of this print (1.3 mm on FR4, docs/geometry.json).
CAD frame: X across, Y = 128.5 - panel Y (origin lower left seen from +Z), Z0..t with
the +Z face as the panel FRONT. Holes are nominal, without print compensation; ream
to size after printing. Nominal geometry only, no physical-fit or strength claim.

USB brace v5: the removable C-saddle captures the MCU board itself, not the carrier.
Its front contact reaches 5.6/5.8/6.0 mm behind the panel (interchangeable saddles,
not loose shims); the rear jaw is 7.75 mm behind the panel. Two M3x6 screws, one on each
side of the USB opening, positively retain it and prevent rotation. The nut is loaded into a
top-edge-loading channel before assembly; it is captive when the screw is installed.
Measured hex insert: 5.5 mm across flats x 2.7 mm thick. The channel is 3.1 mm
high with a 6.0 mm AF pocket and flared entrance. Rear tongue reaches 3.0 mm
under the MCU centrally, relieved by 0.35 mm beyond the bare edge bearing strip.
Panel geometry and screw locations are unchanged from v4.
Fit by sliding DOWN over the top edge with the module out of the rack, not sideways
past the header pins. The screw seats plastic on plastic; it must NOT bend the PCB.
The 6.0 mm saddle matches the user's measured gap, not the nominal 5.9 mm CAD gap.
No strength or physical fit is implied by the geometric checks.
"""
import json
import math
import os
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

HERE = Path(__file__).resolve().parent
MODULE = HERE.parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from sexp import nodes, one, parse  # noqa: E402

PCB = HERE.parent / 'front-pcb/usb-audio-panel.kicad_pcb'
NAME = 'usb-audio-front-panel'
PRINT_THICKNESS = 2.0  # as modules/midi panel_print_thickness_mm
BRACE_NAME = 'usb-brace-v5'
PANEL_PRINT_NAME = f'{NAME}-v4-print.stl'  # unchanged panel, compatible with v5
STOP_DEPTHS = (5.6, 5.8, 6.0)
BRACE_X = (2.0, 28.0)
WEB_Y = (8.2, 9.7)         # 0.2 rail margin; 0.3 mm before MCU edge
CONTACT_Y_END = 10.8        # only 0.8 mm of the 1 mm copper-free MCU edge strip
REAR_DEPTH = 7.75           # 6.0 gap + 1.6 board + 0.15 running clearance
TONGUE_X = (6.0, 24.0)
TONGUE_Y_END = 13.0        # 3.0 mm beyond MCU top edge, central span only
TONGUE_RELIEF = 0.35       # avoid rubbing the board/mask beyond the bare edge
LIP_THICK = 1.3             # lip is BETWEEN the two boards, not behind the carrier
SCREW_CENTRES = ((6.8, 11.0), (23.2, 11.0))
SCREW_XY = SCREW_CENTRES[1]
SCREW_CLEARANCE = 3.4
SCREW_LENGTH = 6.0          # under-head length; longer screws can hit the PCB
SCREW_HEAD_DIAMETER = 5.5   # socket-cap head envelope; no washer
SCREW_HEAD_HEIGHT = 3.0
NUT_AF = 5.5                # user-measured hex insert, across flats
NUT_THICK = 2.7             # user-measured height, not the earlier 2.4 assumption
NUT_SOCKET_AF = 6.0         # 0.5 mm total AF fit allowance
NUT_CHANNEL_HEIGHT = 3.1   # 0.4 mm total height allowance
NUT_LOAD_FLARE = 0.25       # per-side entry lead-in
NUT_SEAT_Z = 8.4            # 1.6 mm roof between nut and panel rear
EAR_BOTTOM_Z = 6.8          # clears USB base even at 5.6 mm front-stop contact
EAR_XY = [(17.8, 9.7), (28.0, 9.7), (28.0, 11.5), (25.75, 12.0),
          (25.75, 14.6), (20.0, 14.6), (17.8, 12.0)]
GUIDE_X = (13.0, 17.0)
GUIDE_Y = (11.0, 12.0)
GUIDE_BOTTOM_Z = 8.8
REPORT_DIR = MODULE / 'research/usb-brace-v5'


def xy(node):
    return float(node[1]), float(node[2])


def panel_geometry():
    tree = parse(PCB.read_text())
    pts = []
    for kind in ('gr_line', 'gr_rect'):
        for item in nodes(tree, kind):
            if one(item, 'layer')[1] == 'Edge.Cuts':
                pts += [xy(one(item, 'start')), xy(one(item, 'end'))]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    holes = []
    for fp in nodes(tree, 'footprint'):
        at = one(fp, 'at')
        fx, fy = xy(at)
        fangle = float(at[3]) if len(at) > 3 else 0.0
        mech = next(p[2] for p in nodes(fp, 'property') if p[1] == 'MechanicalID')
        for pad in nodes(fp, 'pad'):
            assert pad[2] == 'np_thru_hole', 'passive panel must carry only NPTH holes'
            pat = one(pad, 'at')
            px, py = xy(pat)
            assert px == 0 and py == 0, 'panel pads sit on the footprint origin'
            angle = (fangle + (float(pat[3]) if len(pat) > 3 else 0.0)) % 180
            drill = one(pad, 'drill')
            if pad[3] == 'circle':
                w = h = float(drill[1])
            else:
                assert pad[3] == 'oval' and drill[1] == 'oval', pad
                w, h = float(drill[2]), float(drill[3])
            holes.append((mech, round(fx - x0, 3), round(fy - y0, 3), w, h, angle))
    return {'size': (round(x1 - x0, 3), round(y1 - y0, 3)), 'holes': holes}


_CONTRACT = {}


def geometry_contract():
    if not _CONTRACT:
        _CONTRACT.update(json.loads((MODULE / 'docs/geometry.json').read_text()))
    return _CONTRACT


def check_contract(g):
    c = geometry_contract()
    assert list(g['size']) == c['panel_mm'], g['size']
    d = c['panel_hole_diameters_mm']
    want = [tuple(h) for h in c['rail_holes_mm']]
    want += [(*j['XY'], d['jack']) for j in c['jacks']]
    want += [(*p['shaft_XY'], d['pot']) for p in c['pots']]
    got = [(x, y, w) for _, x, y, w, h, _ in g['holes'] if w == h]
    assert sorted(got) == sorted(want), (sorted(got), sorted(want))
    slot = c['usb_slot']
    slots = [(x, y, w, h, a) for _, x, y, w, h, a in g['holes'] if w != h]
    assert slots == [(*slot['XY'], *slot['size_mm'], 0.0)], slots
    return c.get('panel_print_thickness_mm', PRINT_THICKNESS)


def hole_solid(x, y, w, h, angle, thickness):
    """Through cutter: a cylinder, or a stadium slot (oval NPTH) along its long axis."""
    if w == h:
        return Part.makeCylinder(w / 2, thickness + 2, App.Vector(x, y, -1))
    r, length = min(w, h) / 2, max(w, h) - min(w, h)
    slot = Part.makeBox(length, 2 * r, thickness + 2, App.Vector(-length / 2, -r, -1))
    for end in (-length / 2, length / 2):
        slot = slot.fuse(Part.makeCylinder(r, thickness + 2, App.Vector(end, 0, -1)))
    # KiCad angles turn counter-clockwise on screen (Y down); the CAD Y axis is flipped.
    rot = (angle + (90 if h > w else 0)) % 180
    slot.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), -rot)
    slot.translate(App.Vector(x, y, 0))
    return slot.removeSplitter()


def hole_area(w, h):
    r = min(w, h) / 2
    return math.pi * r ** 2 + 2 * r * (max(w, h) - min(w, h))


class Frame:
    """Panel frame (X, Y down) + stack Z -> CAD frame (Y up, Z0 = panel back)."""

    def __init__(self, height, seat):
        self.height, self.seat = height, seat

    def box(self, xs, ys, zs):
        (x0, x1), (y0, y1), (z0, z1) = xs, ys, zs
        return Part.makeBox(x1 - x0, y1 - y0, z1 - z0,
                            App.Vector(x0, self.height - y1, z0 - self.seat))

    def xz_prism(self, pts, ys):
        """Polygon in (X, stack Z) extruded over the panel Y range ys."""
        y0, y1 = ys
        wire = Part.makePolygon([App.Vector(x, self.height - y1, z - self.seat)
                                 for x, z in pts + pts[:1]])
        return Part.Face(wire).extrude(App.Vector(0, y1 - y0, 0))


def solid(shape):
    shape = shape.removeSplitter()
    assert shape.isValid() and len(shape.Solids) == 1, shape.Solids
    return shape


def xy_prism(f, pts, zs):
    z0, z1 = zs
    wire = Part.makePolygon([App.Vector(x, f.height-y, z0-f.seat)
                             for x, y in pts + pts[:1]])
    return Part.Face(wire).extrude(App.Vector(0, 0, z1-z0))


def hex_prism(f, af, zs, centre=SCREW_XY):
    x, y = centre
    radius = af / math.sqrt(3)
    return xy_prism(f, [(x+radius*math.cos(i*math.pi/3),
                         y+radius*math.sin(i*math.pi/3)) for i in range(6)], zs)


def screw_cylinder(f, diameter, zs, centre=SCREW_XY):
    return Part.makeCylinder(diameter/2, zs[1]-zs[0],
                             App.Vector(centre[0], f.height-centre[1], zs[0]-f.seat))


def brace_ledge(f):
    # Shallow centre locating rib only. The two bolts provide positive retention;
    # there is no flexible snap, sliding keeper or intentional PCB compression.
    return solid(f.box(GUIDE_X, GUIDE_Y, (GUIDE_BOTTOM_Z, f.seat)))


def nut_loading_cutter(f, centre):
    """Open from the top edge of the loose bracket, NOT through its board jaw.

    The hex terminal prevents rotation; the full corner-width throat allows a
    measured hex to slide in along +panel-Y before fitting the bracket. The roof
    is still 1.6 mm thick. No fragile press fit and no inaccessible rear cavity.
    """
    x, y = centre
    half_width = NUT_SOCKET_AF / math.sqrt(3)
    z = (NUT_SEAT_Z-NUT_CHANNEL_HEIGHT, NUT_SEAT_Z)
    channel = f.box((x-half_width, x+half_width), (WEB_Y[0]-1, y), z)
    mouth = xy_prism(f, [(x-half_width-NUT_LOAD_FLARE, WEB_Y[0]-1),
                        (x+half_width+NUT_LOAD_FLARE, WEB_Y[0]-1),
                        (x+half_width+NUT_LOAD_FLARE, WEB_Y[0]),
                        (x+half_width, WEB_Y[0]+.6),
                        (x-half_width, WEB_Y[0]+.6),
                        (x-half_width-NUT_LOAD_FLARE, WEB_Y[0])], z)
    return hex_prism(f, NUT_SOCKET_AF, z, centre).fuse([channel, mouth])


def brace_clip(f, depth):
    lip_top = f.seat - REAR_DEPTH
    front_contact = f.seat - depth
    clip = f.box(BRACE_X, WEB_Y, (lip_top-LIP_THICK, f.seat)).fuse([
        f.box(BRACE_X, (WEB_Y[1], CONTACT_Y_END), (front_contact, f.seat)),
        f.box(BRACE_X, (WEB_Y[1], CONTACT_Y_END), (lip_top-LIP_THICK, lip_top)),
        f.box(TONGUE_X, (WEB_Y[1], TONGUE_Y_END),
              (lip_top-LIP_THICK, lip_top-TONGUE_RELIEF)),
        xy_prism(f, EAR_XY, (EAR_BOTTOM_Z, f.seat)),
        xy_prism(f, [(30-x, y) for x, y in EAR_XY], (EAR_BOTTOM_Z, f.seat))])
    for centre in SCREW_CENTRES:
        clip = clip.cut(nut_loading_cutter(f, centre))
        clip = clip.cut(screw_cylinder(f, SCREW_CLEARANCE, (EAR_BOTTOM_Z-1, f.seat+1), centre))
    return solid(clip)


def clip_print_pose(clip):
    """Broad outside web down; short 6.5 mm print, jaws upright, nut sockets accessible."""
    s = clip.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    bb = s.BoundBox
    s.translate(App.Vector(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


def panel_print_pose(panel):
    s = panel.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(App.Vector(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


def hardware_shapes(f, thickness):
    nuts, screws = [], []
    for centre in SCREW_CENTRES:
        nut = hex_prism(f, NUT_AF, (NUT_SEAT_Z-NUT_THICK, NUT_SEAT_Z), centre)
        nut = nut.cut(screw_cylinder(f, 3.0, (0, 20), centre))
        screw = screw_cylinder(f, 3.0, (f.seat+thickness-SCREW_LENGTH, f.seat+thickness), centre)
        screw = screw.fuse(screw_cylinder(f, SCREW_HEAD_DIAMETER,
                        (f.seat+thickness, f.seat+thickness+SCREW_HEAD_HEIGHT), centre))
        nuts.append(solid(nut))
        screws.append(solid(screw))
    return Part.makeCompound(nuts), Part.makeCompound(screws)


def check_brace(f, panel, clips, hardware):
    c = geometry_contract()
    z = c['stack_Z_mm']
    main, mcu = c['main_pcb']['outline_mm'], c['mcu_pcb']['outline_mm']
    carrier = f.box((main[0], main[2]), (main[1], main[3]), (-c['main_pcb']['thickness_mm'], 0))
    rail_y = c['rail_clear_gap_Y_mm'][0]
    t = c['mcu_pcb']['thickness_mm']
    assert WEB_Y[0] > rail_y and WEB_Y[1] < mcu[1] < CONTACT_Y_END < mcu[1]+1.0
    assert f.seat-REAR_DEPTH-LIP_THICK > 0   # completely above the carrier
    screw_tip = f.seat+PRINT_THICKNESS-SCREW_LENGTH
    engagement = NUT_SEAT_Z-max(screw_tip, NUT_SEAT_Z-NUT_THICK)
    assert engagement >= 2.4-1e-8 and screw_tip >= NUT_SEAT_Z-NUT_THICK
    assert NUT_CHANNEL_HEIGHT > NUT_THICK and NUT_SOCKET_AF > NUT_AF
    assert TONGUE_Y_END > CONTACT_Y_END and TONGUE_RELIEF > 0
    assert TONGUE_RELIEF < LIP_THICK
    report = {}
    for depth, body in clips:
        # Verify each saddle at its intended board position; never waive an interference.
        # Separately record what does NOT fit the nominal drawing.
        fitted_gap = max(depth, f.seat-z['mcu_board_top'])
        board = f.box((mcu[0], mcu[2]), (mcu[1], mcu[3]),
                      (f.seat-fitted_gap-t, f.seat-fitted_gap))
        assert f.height-body.BoundBox.YMax >= rail_y-1e-8
        for name, other in [('panel', panel), ('carrier', carrier), ('mcu', board),
                            ('nut', hardware[0]), ('screw', hardware[1])]:
            assert body.common(other).Volume < 1e-6, (depth, name, 'collision')
        assert body.isValid() and len(body.Solids) == 1
        for other in hardware:
            assert other.common(board).Volume < 1e-6
            assert other.common(panel).Volume < 1e-6
        report[f'stop{depth:.1f}'] = {
            'volume_mm3': round(body.Volume, 3), 'front_stop_depth_mm': depth,
            'rear_depth_mm': REAR_DEPTH,
            'central_tongue_reach_past_board_edge_mm': TONGUE_Y_END-mcu[1],
            'central_tongue_relief_mm': TONGUE_RELIEF, 'jaw_opening_mm': round(REAR_DEPTH-depth, 3),
            'total_board_play_mm': round(REAR_DEPTH-depth-t, 3),
            'validation_board_gap_mm': fitted_gap,
            'nominal_stack_front_interference_mm': round(max(0, depth-(f.seat-z['mcu_board_top'])), 3),
            'carrier_clearance_mm': round(body.distToShape(carrier)[0], 3),
            'rail_envelope_margin_mm': round(f.height-body.BoundBox.YMax-rail_y, 3),
        }
    # Small, explicit cable boot TEST envelope, not a universal USB cable guarantee.
    boot = f.box((9, 21), (13, 19), (f.seat+PRINT_THICKNESS, f.seat+PRINT_THICKNESS+15))
    assert hardware[1].common(boot).Volume < 1e-6
    report['hardware'] = {'screw': '2 x M3x6 socket cap, head <=5.5 mm diameter; NO washer',
                          'nut': '2 x user-measured M3 hex inserts, 5.5 mm AF x 2.7 mm',
                          'nut_pocket_AF_mm': NUT_SOCKET_AF,
                          'nut_channel_height_mm': NUT_CHANNEL_HEIGHT,
                          'nut_load_direction': 'from top edge of loose bracket, parallel to panel',
                          'modeled_thread_overlap_mm': round(engagement, 3),
                          'screw_tip_depth_from_panel_back_mm': SCREW_LENGTH-PRINT_THICKNESS,
                          'test_cable_boot_mm': [12, 6],
                          'test_boot_to_head_clearance_mm': round(hardware[1].distToShape(boot)[0], 3)}
    return report


def write_mesh(shape, path):
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01, AngularDeflection=0.1)
    assert mesh.isSolid() and not mesh.hasNonManifolds()
    mesh.write(str(path))
    return mesh.CountFacets


def export_step(shape, path):
    shape.exportStep(str(path))
    # OCC writes trailing spaces; normalize formatting without changing geometry.
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


def build():
    g = panel_geometry()
    thickness = check_contract(g)
    width, height = g['size']
    f = Frame(height, geometry_contract()['stack_Z_mm']['panel_rear_seat'])
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR/'build.json').unlink(missing_ok=True)
    doc = App.newDocument(NAME.replace('-', '_'))
    plate = Part.makeBox(width, height, thickness)
    holes = [hole_solid(x, height-y, w, h, a, thickness) for _, x, y, w, h, a in g['holes']]
    blank = plate.cut(Part.makeCompound(holes))
    hole_volume = thickness*sum(hole_area(w, h) for _, _, _, w, h, _ in g['holes'])
    assert math.isclose(blank.Volume, width*height*thickness-hole_volume, rel_tol=1e-6)
    ledge = brace_ledge(f)
    assert ledge.common(Part.makeCompound(holes)).Volume < 1e-6
    extra_hole = Part.makeCompound([screw_cylinder(f, SCREW_CLEARANCE,
                        (f.seat-1, f.seat+thickness+1), centre) for centre in SCREW_CENTRES])
    assert extra_hole.common(Part.makeCompound(holes)).Volume < 1e-6
    shape = solid(blank.fuse(ledge).cut(extra_hole))
    assert math.isclose(shape.Volume, blank.Volume+ledge.Volume-2*math.pi*(SCREW_CLEARANCE/2)**2*thickness,
                        rel_tol=1e-6)
    clips = [(depth, brace_clip(f, depth)) for depth in STOP_DEPTHS]
    hardware = hardware_shapes(f, thickness)
    report = check_brace(f, shape, clips, hardware)
    # Default visual assembly is explicitly the measured 6.0 mm build, not the 5.9 drawing.
    for name, body in [('FrontPanel', shape), ('SaddleStop60Measured', dict(clips)[6.0]),
                       ('M3NutEnvelope', hardware[0]), ('M3x6ScrewEnvelope', hardware[1])]:
        obj = doc.addObject('Part::Feature', name)
        obj.Shape = body
    doc.recompute()
    doc.saveAs(str(HERE / f'{NAME}.FCStd'))
    export_step(shape, HERE / f'{NAME}.step')
    facets = write_mesh(shape, HERE / f'{NAME}.stl')
    write_mesh(panel_print_pose(shape), HERE / PANEL_PRINT_NAME)
    for depth, clip in clips:
        stl = f'{BRACE_NAME}-stop{depth:.1f}.stl'
        report[f'stop{depth:.1f}'].update(stl=stl, mesh_facets=write_mesh(clip_print_pose(clip), HERE / stl))
        export_step(clip, HERE / f'{BRACE_NAME}-stop{depth:.1f}.step')
    coupon = solid(shape.common(f.box((0, width), (0, 30), (0, f.seat+thickness))))
    write_mesh(panel_print_pose(coupon), HERE / f'{BRACE_NAME}-panel-top-test.stl')
    result = {'revision': 'v5-accessible-nuts-deeper-tongue', 'panel_mm': [width, height, thickness],
              'original_pcb_holes': g['holes'], 'printed_only_m3_holes': [[*xy, SCREW_CLEARANCE] for xy in SCREW_CENTRES],
              'volume_mm3': round(shape.Volume, 3), 'mesh_facets': facets, 'usb_brace': report,
              'status': 'CAD checks only; physical fit, cable boot and strength untested'}
    (REPORT_DIR / 'build.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return f, shape, clips, hardware


# FreeCADCmd loads scripts as modules, not necessarily as __main__.
if os.environ.get('USB_BRACE_IMPORT_ONLY') != '1':
    build()
