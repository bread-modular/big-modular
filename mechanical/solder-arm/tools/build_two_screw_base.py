"""Drop-in two-screw desk base. The released J1 is transplanted, not redrawn.
Build headless with FreeCADCmd. Writes only two-screw-base subfolders.
Desk top Z=0; +X points into the desk and Y runs along its front edge.
"""
import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

TOOLS = Path(__file__).resolve().parent
ARM = TOOLS.parent
CABLE = ARM.parent / 'desk-cable-holder'
sys.path.insert(0, str(TOOLS))
import build_solder_arm as arm
import build_plates as plates
sys.path.insert(0, str(CABLE / 'tools'))
import end_clip_hardware as screwfit

OUT = ARM / 'print' / 'two-screw-base'
CAD = ARM / 'cad' / 'two-screw-base'
PREVIEW = ARM / 'research' / 'two-screw-base' / 'render'
HALF = 56.0                      # along the edge (original body: +/-23)
AX, OFF = 13.0, 40.0             # short lower jaw; one screw under each top wing
FAN = 36.0                       # 45 degree corner cut where the top jaw fans into the pivot
NOTCH = 19.0                     # relieved lower-lip centre between the screws (0 = none)
BOTTOM, TOP = -67., -54.         # 13 mm integral tapped land
PITCH = screwfit.R['pitch']
HEIGHT = screwfit.TIP + PITCH    # one extra turn to retain the arm's 5 mm minimum
X, Z = arm.V(1, 0, 0), arm.V(0, 0, 1)


def original_clamp():
    # J1 of the arm (top plate, tooth ring, keyed pocket), as on the original clamp
    return arm.pivot()[0]


def window(radius):
    return arm.move(arm.cyl(radius, -1, arm.T + 3), arm.J1_X)


def frame_blank():
    """Untapped frame, also used by the comparative frame-load model."""
    # End-on C section. Upper corner relief accepts a square edge. The 4 mm
    # internal lower radius recedes BEHIND the edge of even a 52 mm desktop.
    prof = [(-10, arm.T), (arm.TOP_JAW_L-3, arm.T), (arm.TOP_JAW_L, arm.T-3),
            (arm.TOP_JAW_L, 1), (arm.TOP_JAW_L-1, 0), (2, 0), (.8, .65),
            (-.65, .65), (-1.2, .1), (-1.2, -1.2), (0, -2.4), (0, -46.6),
            (-1.6, -48.2), (-1.6, TOP+4)]
    prof += [(2.4-4*math.cos(i*math.pi/16), TOP+4-4*math.sin(i*math.pi/16))
             for i in range(1, 9)]
    prof += [(24.5, TOP), (27, TOP-2.5), (27, BOTTOM+2.5), (24.5, BOTTOM),
             (1, BOTTOM), (-10, BOTTOM+2.5), (-13, BOTTOM+5.5), (-13, arm.T-3)]
    body = arm.prism_xz(prof, -HALF, HALF)
    # Fan the top into the central pivot; relieve the unused centre of the lower
    # lip, NOT the cross-edge spine. Both transitions grow <=1 mm per mm of Y
    # when printed on the -Y end. No suspended crossbar to bridge.
    reach = arm.TOP_JAW_L
    outline = [(-14, -HALF), (reach-FAN, -HALF), (reach, -HALF+FAN),
               (reach, HALF-FAN), (reach-FAN, HALF), (-14, HALF)]
    body = body.common(arm.prism(outline, BOTTOM-1, arm.T+1))
    if not NOTCH:
        return body
    notch = arm.prism([(27, -NOTCH), (30, -NOTCH), (30, NOTCH), (27, NOTCH), (27-NOTCH, 0)], BOTTOM-1, TOP+1)
    return body.cut(notch)


def wide_base(original, frame=None):
    body = frame_blank() if frame is None else frame
    # The annular overlap makes a single fused solid. Everything inside it,
    # including the head pocket, key flats, axial stack and tooth phase, comes
    # directly from the already released clamp in its assembly frame.
    rim = arm.R_OUT + arm.RING_END
    body = arm.one(body.cut(window(rim+.2)).fuse(original.common(window(rim+.6))), 'pivot graft')
    for y in (-OFF, OFF):
        body = screwfit.tap(body, AX, y, BOTTOM, TOP, roof_side=1)
    return body


def screw_at(screw, height, y, desk):
    dz = -desk-height
    turn = App.Rotation(Z, 360*dz/PITCH)
    return arm.place(screw, App.Placement(arm.V(AX, y, dz), turn))


def desk(t):
    return arm.box(0, 340, -260, 260, -t, 0)


def clear(a, b, label):
    if a.BoundBox.intersect(b.BoundBox):
        v = abs(a.common(b).Volume)
        assert v < 1e-4, (label, v)


def check_hardware(base, screw, height, samples):
    report = {}
    for t in samples:
        table = desk(t)
        clear(base, table, ('desk in mouth', t))
        gaps = []
        for y in (-OFF, OFF):
            placed = screw_at(screw, height, y, t)
            clear(placed, base, ('screw in thread', t, y))
            clear(placed, table, ('screw at desk underside', t, y))
            gap = arm.gap(placed.Shells[0], base.Shells[0])
            assert .2 < gap < .4, ('mating flanks', t, y, gap)
            gaps.append(gap)
            # Actual tip and the top land straight above it both bear on the desk.
            area = arm.move(placed, z=.01).common(table).Volume/.01
            assert abs(area-math.pi*screwfit.FACE**2) < .3, ('tip bearing', area)
            land = arm.move(arm.cyl(screwfit.FACE, 0, .1), AX, y)
            assert land.cut(base).Volume < 1e-5, 'top contact does not cover screw face'
            # One turn back clears the desktop during entry; while sliding on,
            # the desk occupies a subset of the final half-space checked here.
            loose = screw_at(screw, height, y, t+PITCH)
            clear(loose, base, 'one turn backed off')
            assert abs(arm.gap(loose, table)-PITCH) < .01
        knob_gap = BOTTOM - (-t-height+screwfit.KH)
        # Exclude both the screw tip runout and the tapped mouth's conical lead.
        lead = (screwfit.R['depth']+.4)/.6
        full = min(TOP, -t-screwfit.TIP_RUNOUT) - max(BOTTOM+lead, -t-height+screwfit.KH)
        assert knob_gap >= 2 and full >= 2*PITCH, (t, knob_gap, full)
        report[f'{t:g}'] = dict(flank_gaps_mm=gaps, knob_clearance_mm=round(knob_gap, 2),
                                 full_profile_overlap_mm=round(full, 2), contact_each_mm2=round(area, 1))
    return report


def stock_screw():
    # Independent compatibility check with the cable holder screw people have
    # already printed, using its RELEASED file (centred about its six-lobed knob).
    s = Part.read(str(CABLE / 'print' / 'end-clips' / 'parts' / 'hand-screw.step'))
    b = s.optimalBoundingBox(False, False)
    assert s.isValid() and abs(b.ZLength-screwfit.TIP) < .001
    return arm.move(s, -b.Center.x, -b.Center.y, -b.ZMin)


def check_upper(base, original, screw):
    joint = window(arm.R_OUT+arm.RING_END+.75)
    old, new = original.common(joint), base.common(joint)
    delta = abs(old.cut(new).Volume) + abs(new.cut(old).Volume)
    assert delta < 1e-5, ('J1 against released part', delta)
    model = arm.Arm(plain=True, base=False)  # conservative, full-size shank on the T-bolt; this base checked here
    poses = {}
    at25 = [screw_at(screw, HEIGHT, y, 25) for y in (-OFF, OFF)]
    for name, args in arm.POSES.items():
        parts = model.assemble(*args)
        parts = {n: p for n, p in parts.items() if n not in ('desk-base', 'screw-left', 'screw-right', 'desk')}
        for n, p in parts.items():
            clear(p, base, (name, n, 'new base'))
            for s in at25:
                clear(p, s, (name, n, 'new screw'))
        poses[name] = 'clear'
        if name == 'work':
            work = parts
    bolt = work['bolt-1']
    for dz in (-85, -55, -30, -8, 0):
        clear(arm.move(bolt, z=dz), base, 'insert the original T-bolt before clamping')
    # Negative controls: the yaw teeth must lock between detents and the flats
    # must actually hold the bolt, not just be roomy enough for it to pass.
    turned = work['turret'].copy()
    turned.rotate(arm.V(arm.J1_X, 0, 0), Z, 180/arm.TEETH)
    assert turned.common(base).Volume > 20, 'yaw teeth not indexing'
    turned = bolt.copy()
    turned.rotate(arm.V(arm.J1_X, 0, 0), Z, 15)
    assert turned.common(base).Volume > 5, 'T-bolt not keyed'
    return dict(joint_symmetric_difference_mm3=round(delta, 7), yaw_teeth=arm.TEETH,
                bolt_head_above_desk_mm=round(bolt.optimalBoundingBox(False, False).ZMin, 2),
                original_upper_poses=poses), work, at25


def save_assembly(work, base, screws):
    CAD.mkdir(exist_ok=True, parents=True)
    PREVIEW.mkdir(exist_ok=True, parents=True)
    doc = App.newDocument('TwoScrewSolderArm')
    shapes = dict(work, wide_base=base, left_screw=screws[0], right_screw=screws[1])
    for name, s in shapes.items():
        doc.addObject('Part::Feature', name.replace('-', '_')).Shape = s
        mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=.05, AngularDeflection=.22)
        mesh.write(str(PREVIEW / (name+'.stl')))
    doc.recompute()
    doc.saveAs(str(CAD / 'assembly.FCStd'))
    App.closeDocument(doc.Name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = original_clamp()
    base = wide_base(original)
    screw = screwfit.screw(HEIGHT)
    print('Solids built; checking desk contact, travel and fit', flush=True)
    fit = check_hardware(base, screw, HEIGHT, (5, 8, 18, 25.5, 36.25, 52))
    cable_fit = check_hardware(base, stock_screw(), screwfit.TIP, (8, 25.5, 52))
    for y in (-OFF, OFF):
        # Displacing without turning must catch the thread, not slide through.
        # OCC's common of two crossing helices can have inverted shells. Test
        # material points on the -X flank instead of trusting a signed volume.
        aligned = screw_at(screw, HEIGHT, y, 25)
        pushed = arm.move(aligned, z=.8)
        crest = PITCH*math.ceil((BOTTOM+4)/PITCH) + PITCH/2
        probes = [arm.V(AX-r, y, crest+dz) for r in (6.9, 7.1, 7.3) for dz in (1, 1.2, 1.4)]
        assert any(base.isInside(p, 1e-4, False) and pushed.isInside(p, 1e-4, False)
                   and not aligned.isInside(p, 1e-4, True) for p in probes), ('no load flank', y)
    upper, work, at25 = check_upper(base, original, screw)
    print('Interface and arm poses checked; exporting meshes and plate', flush=True)
    shapes = {'wide-base': arm.print_pose(base, (X, 90)), 'hand-screw': arm.print_pose(screw)}
    arm.OUT = plates.PRINT = plates.OUT = OUT  # do not run either legacy full-build main
    parts = {n: arm.export_part(s, n) | arm.overhangs(s) for n, s in shapes.items()}
    plate = plates.build_plate('print-this', [['wide-base', 'hand-screw', 'hand-screw']],
                               {n: plates.part_mesh(n) for n in shapes})
    save_assembly(work, base, at25)
    report = dict(status='CAD_PASS', physical_load_test=False, base_width_mm=2*HALF,
                  screw_spacing_mm=2*OFF, screw_from_edge_mm=AX, desk_range_mm=[5, 52],
                  screw_height_mm=HEIGHT, supplied_screw_fit=fit, cable_screw_fit=cable_fit,
                  interface=upper, parts=parts, plate=plate)
    (OUT / 'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print('TWO_SCREW_BASE_PASS', flush=True)


if __name__ == '__main__' or any(Path(s).resolve() == Path(__file__).resolve() for s in sys.argv[1:]):
    main()
