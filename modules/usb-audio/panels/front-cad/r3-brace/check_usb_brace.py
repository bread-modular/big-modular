"""FreeCAD mechanical validation + section data for the v5 printed USB saddle.

Run system Python inspect_brace_pcb.py to generate research/usb-brace-v5/pcb-mechanics.json,
then run this script with FreeCADCmd. Uses read-only native PCB positions, actual local
STEP models (USB is an envelope proxy), SMD courtyard/height envelopes, solder/pin
allowances and an explicit nominal-vs-measured stack. Not a strength test or ERC/DRC.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import FreeCAD as App
import Part
import Mesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ['USB_BRACE_IMPORT_ONLY'] = '1'
import build_front_panel as cad

OUT = cad.REPORT_DIR
(OUT/'clearances.json').unlink(missing_ok=True)
snapshot = json.loads((OUT/'pcb-mechanics.json').read_text())
assert hashlib.sha256(Path(snapshot['board']).read_bytes()).hexdigest() == snapshot['board_sha256']
assert hashlib.sha256(Path(snapshot['carrier_board']).read_bytes()).hexdigest() == snapshot['carrier_sha256']
assert snapshot['top_surface_copper_min_y'] > cad.CONTACT_Y_END
c = cad.geometry_contract()
f = cad.Frame(c['panel_mm'][1], c['stack_Z_mm']['panel_rear_seat'])
panel = Part.read(str(HERE/f'{cad.NAME}.step'))
clips = [(depth, Part.read(str(HERE/f'{cad.BRACE_NAME}-stop{depth:.1f}.step')))
         for depth in cad.STOP_DEPTHS]
hardware = cad.hardware_shapes(f, cad.PRINT_THICKNESS)


def overlapping_bounds(a, b):
    aa, bb = a.BoundBox, b.BoundBox
    return (aa.XMax > bb.XMin and bb.XMax > aa.XMin and
            aa.YMax > bb.YMin and bb.YMax > aa.YMin and
            aa.ZMax > bb.ZMin and bb.ZMax > aa.ZMin)


def no_overlap(a, b, label):
    if overlapping_bounds(a, b):
        vol = a.common(b).Volume
        assert vol < 1e-6, (label, 'intersection mm3', vol)


def environments(gap):
    top = f.seat-gap
    out, visual = {}, {}
    main, mcu = c['main_pcb']['outline_mm'], c['mcu_pcb']['outline_mm']
    out['carrier'] = f.box((main[0], main[2]), (main[1], main[3]), (-1.6, 0))
    out['MCU_board'] = f.box((mcu[0], mcu[2]), (mcu[1], mcu[3]), (top-1.6, top))
    # Blanket 0.25 mm underside allowance over the routed area: the deeper tongue
    # is recessed, and must NOT become an unverified bearing on solder mask/vias.
    out['MCU_underside_surface_allowance'] = f.box(
        (mcu[0], mcu[2]), (mcu[1]+1.0, mcu[3]), (top-1.85, top-1.6))
    for header in snapshot['carrier_header_envelopes']:
        x0, y0, x1, y1 = header['bbox']
        out[header['ref']+'_carrier_header_plastic'] = f.box(
            (x0, x1), (y0, y1), (0, c['stack_Z_mm']['header_plastic']))
    for fp in snapshot['footprints']:
        # Include actual native PTH locations; USB shield solder was missing in v4.
        for i, pad in enumerate(fp['pads']):
            if pad['thru']:
                x0, y0, x1, y1 = pad['bbox']
                out[f"{fp['ref']}_underside_solder{i}"] = f.box(
                    (x0-.25, x1+.25), (y0-.25, y1+.25), (top-3.1, top-1.6))
        ref, (x, y) = fp['ref'], fp['xy']
        if ref in ('J102', 'J103'):
            # These are bare copper holes on MCU, not another plastic pin-header body.
            for i, pad in enumerate(fp['pads']):
                x0, y0, x1, y1 = pad['bbox']
                out[f'{ref}_solder{i}'] = f.box((x0-.15, x1+.15), (y0-.15, y1+.15), (top, top+.8))
                px, py = (x0+x1)/2, (y0+y1)/2
                out[f'{ref}_pin{i}'] = f.box((px-.32, px+.32), (py-.32, py+.32), (-.5, 10.0))
            continue
        assert len(fp['models']) == 1, ref
        model = fp['models'][0]
        assert model['scale'] == [1., 1., 1.] and model['rotation'] == [0., 0., 0.], ref
        body = Part.read(model['path'])
        body.translate(App.Vector(*model['offset']))
        body.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), fp['angle'])
        body.translate(App.Vector(x, f.height-y, top-f.seat))
        visual[ref] = body
        if ref == 'J101':
            # Actual proxy solids, plus independent rectangular body and shell margins.
            out['USB_model'] = body
            out['USB_base_margin'] = f.box((8.85, 21.15), (13.35, 18.65), (top, top+2.25))
            shell = cad.hole_solid(15, f.height-16, 9.24, 3.46, 0, 8.95-2.1-2)
            shell.translate(App.Vector(0, 0, top+2.1-f.seat+1))
            out['USB_shell_margin'] = shell
        else:
            x0, y0, x1, y1 = fp['courtyard']
            body_height = body.BoundBox.ZMax-(top-f.seat)
            out[ref+'_courtyard_height'] = f.box((x0, x1), (y0, y1), (top, top+body_height+.2))
    visual['carrier'] = out['carrier']
    visual['MCU_board'] = out['MCU_board']
    return out, visual


result = {'status': 'pass', 'pcb_sha256': snapshot['board_sha256'],
          'surface_copper_to_contact_y_mm': round(snapshot['top_surface_copper_min_y']-cad.CONTACT_Y_END, 3),
          'variants': {}, 'limits': ['No physical test or structural analysis',
          'Underside solder allowance 1.5 mm high / 0.25 mm XY; mask-via allowance 0.25 mm',
          'USB STEP is a proxy; cable boot is an assumed 12x6 mm test envelope',
          'Case rail geometry is the project keepout only; 0.2 mm margin must be physically checked',
          'No ERC/DRC acceptance: shared inspector refused existing ignored rule severities; PCB unchanged']}
sections = {}
for depth, clip in clips:
    gap = max(depth, 5.9)
    obstacles, visual = environments(gap)
    moving = Part.makeCompound([clip, hardware[0]])  # nuts loaded before fitting; screws added last
    for key, body in obstacles.items():
        no_overlap(moving, body, (depth, key))
        no_overlap(panel, body, (depth, 'panel', key))
        no_overlap(hardware[1], body, (depth, 'screws', key))
    # Dense sampled insertion sweep from ABOVE, with no rail installed. No sideways insertion.
    for i in range(81):
        dy = -20 + i*.25
        shifted = moving.copy()
        shifted.translate(App.Vector(0, -dy, 0))  # +panel-Y is -CAD-Y
        no_overlap(shifted, panel, (depth, 'assembly sweep', dy, 'panel'))
        for key, body in obstacles.items():
            no_overlap(shifted, body, (depth, 'assembly sweep', dy, key))
    # Check the whole allowed axial play, including both bearing stops. A smaller
    # front-stop depth must not let the USB body hit a nut ear before the stop.
    last_gap = cad.REAR_DEPTH-c['mcu_pcb']['thickness_mm']
    for i in range(13):
        travel_gap = depth+(last_gap-depth)*i/12
        travel_obstacles, _ = environments(travel_gap)
        for key, body in travel_obstacles.items():
            no_overlap(moving, body, (depth, 'board travel', travel_gap, key))
            no_overlap(panel, body, (depth, 'panel board travel', travel_gap, key))
            no_overlap(hardware[1], body, (depth, 'screw board travel', travel_gap, key))
    distances = sorted((round(moving.distToShape(body)[0], 4), key) for key, body in obstacles.items()
                       if key not in ('carrier', 'MCU_board'))
    result['variants'][f'{depth:.1f}'] = {'board_gap_mm': gap, 'sweep_samples': 81, 'axial_board_travel_samples': 13,
         'min_component_envelope_clearances_mm': distances[:8],
         'nut_to_MCU_mm': round(hardware[0].distToShape(obstacles['MCU_board'])[0], 3),
         'screw_to_MCU_mm': round(hardware[1].distToShape(obstacles['MCU_board'])[0], 3),
         'tongue_to_underside_allowance_mm': round(clip.distToShape(obstacles['MCU_underside_surface_allowance'])[0], 3)}
    # Save native section wire geometry and a cropped assembly for a reproducible review render.
    if depth == 6.0:
        entities = {'panel': panel, 'saddle': clip, 'nuts': hardware[0], 'screws': hardware[1], **visual}
        crop = f.box((0, 30), (0, 26), (-2, 18))
        for name, body in entities.items():
            part = body.common(crop)
            if not part.isNull() and part.Volume > 1e-8:
                vertices, faces = part.tessellate(.05)
                sections.setdefault('mesh', {})[name] = {
                    'vertices': [[v.x, f.height-v.y, v.z+f.seat] for v in vertices],
                    'faces': faces}
            for x in (15.0, 23.2):
                wires = body.slice(App.Vector(1, 0, 0), x)
                sections.setdefault(f'x{x}', {})[name] = [
                    [[f.height-p.y, p.z+f.seat] for p in w.discretize(Distance=.04)] for w in wires]
        doc = App.newDocument('USB_Brace_V5_Measured_6mm_Assembly')
        for name, body in entities.items():
            obj = doc.addObject('Part::Feature', name)
            obj.Shape = body
        doc.recompute()
        doc.saveAs(str(OUT/'assembly-measured-6mm.FCStd'))

# Reject the incompatible 6.0 mm stop on the nominal 5.9 mm model instead of blessing a press fit.
nominal, _ = environments(5.9)
assert dict(clips)[6.0].common(nominal['MCU_board']).Volume > 0
result['nominal_6mm_stop_is_intentionally_rejected'] = True
# All source PCBs remain untouched. Also test nut anti-rotation in each pocket.
for centre in cad.SCREW_CENTRES:
    nut = cad.hex_prism(f, cad.NUT_AF, (cad.NUT_SEAT_Z-cad.NUT_THICK, cad.NUT_SEAT_Z), centre)
    for degrees in (-15, 15):
        turned = nut.copy()
        turned.rotate(App.Vector(centre[0], f.height-centre[1], 0), App.Vector(0, 0, 1), degrees)
        assert turned.common(dict(clips)[6.0]).Volume > .01, ('nut socket fails anti-rotation', centre)
result['nut_socket_anti_rotation_15deg'] = 'pass'
# A fitted nut is not proof it can be installed. Sweep loading from the open top
# edge in the plane of the panel, including the fit allowance, before PCB assembly.
result['nut_loading'] = {}
for centre in cad.SCREW_CENTRES:
    for depth, clip in clips:
        for label, af, h in [('measured', cad.NUT_AF, cad.NUT_THICK),
                             ('clearance_gauge', cad.NUT_SOCKET_AF, cad.NUT_CHANNEL_HEIGHT)]:
            top_z = cad.NUT_SEAT_Z-(cad.NUT_CHANNEL_HEIGHT-h)/2
            gauge = cad.hex_prism(f, af, (top_z-h, top_z), centre)
            for i in range(41):
                shift = -10+i*.25
                moving = gauge.copy()
                moving.translate(App.Vector(0, -shift, 0))
                no_overlap(moving, clip, ('nut loading', centre, depth, label, shift))
    result['nut_loading'][str(centre)] = {'samples_per_gauge_per_variant': 41,
        'measured_AF_mm': cad.NUT_AF, 'measured_height_mm': cad.NUT_THICK,
        'gauge_AF_mm': cad.NUT_SOCKET_AF, 'channel_height_mm': cad.NUT_CHANNEL_HEIGHT}
# Regression: v4's stated rear insertion path was obstructed by its own front jaw,
# even for the old thinner nut. Preserve evidence instead of blaming only tolerances.
v4path = OUT/'v4-before/usb-brace-v4-stop6.0.step'
if v4path.exists():
    v4clip = Part.read(str(v4path))
    old_nut = cad.hex_prism(f, 5.5, (6.0, 8.4), cad.SCREW_CENTRES[0])
    volumes = []
    for i in range(41):
        moved = old_nut.copy()
        moved.translate(App.Vector(0, 0, -10+i*.25))
        volumes.append(moved.common(v4clip).Volume)
    assert max(volumes) > .1
    result['v4_rear_loading_obstruction_mm3'] = round(max(volumes), 3)
# Read the actual exported STL files, not just their source BRep shapes.
result['stl_roundtrip'] = {}
meshes = [(HERE/cad.PANEL_PRINT_NAME, panel)]
meshes += [(HERE/f'{cad.BRACE_NAME}-stop{d:.1f}.stl', sh) for d, sh in clips]
coupon = panel.common(f.box((0, 30), (0, 30), (0, 12)))
meshes.append((HERE/f'{cad.BRACE_NAME}-panel-top-test.stl', coupon))
for path, shape in meshes:
    mesh = Mesh.Mesh(str(path))
    assert mesh.isSolid() and not mesh.hasNonManifolds(), path.name
    assert abs(mesh.Volume-shape.Volume)/shape.Volume < .001, path.name
    bb = mesh.BoundBox
    assert abs(bb.ZMin) < 1e-5
    result['stl_roundtrip'][path.name] = {
        'closed': True, 'size_mm': [round(v, 3) for v in (bb.XLength, bb.YLength, bb.ZLength)],
        'volume_mm3': round(mesh.Volume, 3)}
# A longer screw is not an allowed substitute: its tip enters the nominal PCB.
for centre in cad.SCREW_CENTRES:
    too_long = cad.screw_cylinder(f, 3, (4, 12), centre)
    assert too_long.common(nominal['MCU_board']).Volume > 0
result['M3x8_rejected_on_nominal_stack'] = True
(OUT/'clearances.json').write_text(json.dumps(result, indent=2)+'\n')
(OUT/'render-data.json').write_text(json.dumps(sections))
print(json.dumps(result, indent=2))
