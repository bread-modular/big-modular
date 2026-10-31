"""M1 mechanical-preview contract for usb-power-45w (4HP, unrouted). mm, stdlib only.

Assembly frame (copied from modules/usb-power/tools/stack_geometry.py): origin at the
panel's upper-left FRONT corner seen from the front; X across (right), Y down, Z into the
case (panel front Z0, rear Z1.6). The carrier stands perpendicular to the panel with its
B.Cu face at X2.5 and F.Cu at X4.1, exactly as the old 2HP module; the 4HP panel only
widens the free space on the F side (X4.1..20.0 instead of X4.1..9.8).

Native carrier frame (same map as the old carrier): native x = Y + 35.75,
native y = 104.275 - Z. Native panel frame: native = panel XY + (50, 30).

Run from the repository root:
  python3 -B modules/usb-power-45w/tools/mechanics45.py            # write docs JSON + checks
This is a nominal envelope contract. It is not a physical-fit, strength or tolerance
qualification; manufacturer values are cited where used, proxies are labelled.
"""
import json
import math
from copy import deepcopy
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
OLD = MODULE.parent / 'usb-power'

LED_Y = {'D8': 43.0, 'D16': 49.5, 'D17': 56.0, 'D18': 62.5}
LED_LABEL = {'D8': 'MAIN', 'D16': '+12V', 'D17': '+5V', 'D18': '-12V'}
RESET_Y = 69.0

GEOMETRY = {
    'revision': 'M1 mechanical preview: 4HP panel + perpendicular carrier, UNROUTED',
    'status': 'Preview for user approval before placement/routing. No copper tracks, vias or zones.',
    'hp': 4,
    'panel_mm': [20.0, 128.5, 1.6],
    'panel_source': 'modules/blank/docs/geometry.json blank-4hp: 20.0 x 128.5, rail hole X12.58, Y3/Y125.5, dia 3.2',
    'rail_holes_mm': [[12.58, 3.0, 3.2], [12.58, 125.5, 3.2]],
    'rail_head_diameter_mm': 6.0,
    'rail_profile_YZ_mm': {'note': 'case/tools/build_case.py: rail 10.0 wide centred on the hole line, '
                                   '13.5 deep behind the panel rear; clear gap >= 112.5',
                           'top_Y': [-2.0, 8.0], 'bottom_Y': [120.5, 130.5], 'depth_behind_rear': 13.5},
    'panel_bracket_holes_mm': [[6.4, 22.0, 3.2], [6.4, 106.5, 3.2]],
    'native_panel_origin_mm': [50.0, 30.0],
    'native_carrier_map': 'native x = Y + 35.75; native y = 104.275 - Z (old usb-power carrier map)',
    'carrier_X_mm': [2.5, 4.1],
    'carrier_Y_mm': [14.0, 114.5],
    'carrier_Z_mm': [2.0, 42.0],
    'carrier_thickness_mm': 1.6,
    'carrier_layers': 4,
    'carrier_holes_YZ_mm': [[22.0, 15.0], [106.5, 15.0]],
    'carrier_hole_mm': 3.2,
    'carrier_bracket_reliefs_YZ_mm': [[16.5, 27.5, 10.0], [101.0, 112.0, 10.0]],
    'depth_target': {'limit_behind_panel_rear_mm': 42.0,
                     'basis': 'user target <= 42 mm; case/busboard: plate top to panel rear 58.4, '
                              'bus header tops 15.7 -> 42.7 mm free behind the panel rear',
                     'strict_reading': 'also checked against Z <= 42.0 from the panel FRONT'},
    'aperture_XYWHR_mm': [3.3, 28.1, 5.0, 10.8, 0.6],
    'mouth_axis_XYZ_mm': [5.73, 33.5, 0.8],
    'USB': {'reference': 'J1', 'mpn': 'TYPE-C-31-M-12', 'manufacturer': 'HRO', 'LCSC': 'C165948',
            'mount': 'SMD signal pads + 4 THT shell lugs (mixed)',
            'body_width_depth_height_mm': [8.94, 7.35, 3.26],
            'native_origin_xy_mm': [69.25, 103.475], 'orientation_deg': 0,
            'model_status': 'No verified 3D model: dimensioned envelope only (copied from usb-power).'},
    'LEDs': [{'reference': ref, 'label': LED_LABEL[ref], 'panel_XY_diameter_mm': [6.1, y, 3.6],
              'pad1_YZ_mm': [round(y - 1.27, 3), 6.37]} for ref, y in LED_Y.items()],
    'LED': {'type': 'THT 3 mm round LED, leads formed 90 degrees (old D10 footprint/style, hand-soldered)',
            'footprint': 'USBPOWER45:LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge',
            'pitch_mm': 2.54, 'pad_diameter_mm': 1.8, 'axis_above_PCB_mm': 2.0,
            'nominal_tip_Z_mm': -0.2, 'max_body_diameter_mm': 3.25, 'max_flange_diameter_mm': 3.8,
            'panel_pitch_mm': 6.5,
            'note': 'No LED MPN selected (BOM has none). Generic 5.3 mm lamp envelope as old D10; '
                    'form leads in a jig with the panel.'},
    'reset_XY_diameter_mm': [5.8, RESET_Y, 3.2],
    'switch': {'reference': 'SW1', 'mpn': 'TL3340AF160QG', 'manufacturer': 'E-Switch', 'LCSC': 'C2886925',
               'mount': 'SMT side-actuated (NOT through-hole); hand-solder toe pads; 2 NPTH pegs',
               'peg_row_YZ_mm': [RESET_Y, 4.1], 'actuator_axis_height_mm': 1.7, 'body_height_mm': 3.3,
               'body_width_Y_mm': 4.5, 'body_Z_mm': [2.9, 5.45], 'actuator_tip_Z_mm': 2.05,
               'actuator_diameter_mm': 2.0,
               'model_status': 'No verified 3D model: dimensioned envelope only (copied from usb-power).'},
    'headers': [
        {'reference': 'J2', 'pin1_YZ_mm': [76.0, 36.0], 'rotation_deg': 270},
        {'reference': 'J3', 'pin1_YZ_mm': [107.0, 36.0], 'rotation_deg': 270}],
    'header': {
        'footprint': 'USBPOWER45:IDC-Header_2x08_P2.54mm_Vertical (THT, hand-soldered, unchanged pads)',
        'orientation': 'long axis along Y; pins 1/2 (-12V) at the high-Y end (module bottom), '
                       'odd row at the higher Z; ribbon must leave toward +Z (case floor/bus)',
        'reference_body': 'Wurth 61201621621 WR-BHD box header: L 27.98, W 8.85, H 9.1 (+/-0.15) above PCB',
        'reference_url': 'https://www.we-online.com/components/products/datasheet/61201621621.pdf',
        'body_LWH_max_mm': [28.18, 9.0, 9.25],
        'kicad_courtyard_local_mm': [-4.68, -5.6, 6.22, 23.38],
        'note': 'BOM J2/J3 carry no MPN; the Wurth part is the dimension reference, not a selection.'},
    'mating_plug': {
        'status': 'PROPOSAL ENVELOPE - cable/plug is not specified in the BOM; fit is NOT proven',
        'reference': '3M D891 / 89116 16-way IDC socket drawing 78-5100-2243-3: body 24.9 x 6.1; '
                     'assembled height 14.5 without, 16.3 with standard strain relief (text-extracted '
                     'drawing values; dimension assignment to be confirmed)',
        'reference_url': 'https://multimedia.3m.com/mws/media/485893O/3m-tm-idc-ribbon-cable-socket-ts2243.pdf',
        'required_mated_height_above_FCu_max_mm': 14.8,
        'proposal_body_LW_mm': [25.2, 6.2],
        'proposal_X_mm': [7.1, 18.9],
        'ribbon_X_mm': [15.9, 18.9], 'ribbon_width_Y_mm': 20.8, 'ribbon_exit': '+Z',
        'ribbon_shown_to_Z_mm': 50.0,
        'strain_relief_worst_height_mm': 16.3,
        'requirement': '16-pin keyed IDC socket + 1.27 mm ribbon, mated height <= 14.8 mm above carrier F.Cu '
                       '(X <= 18.9), ribbon leaving toward +Z. A clip-type strain relief reaching 16.3 mm '
                       '(X 20.4) overhangs the 4HP panel edge X20.0 and is not allowed unless measured lower.'},
    'cans': {
        'status': 'PROVISIONAL height-context positions only, NOT a placement. Retained per capacitor study.',
        'body': 'SamYoung MVK 6.3 x 7.7 (8.0 max incl. base) SMD aluminium can, footprint CP_Elec_6.3x7.7',
        'height_max_mm': 8.0, 'base_square_mm': 6.6,
        'parts': [{'reference': r, 'YZ_mm': yz, 'rotation_deg': 0}
                  for r, yz in [('C5', [45.0, 22.0]), ('C34', [56.0, 22.0]),
                                ('C35', [67.0, 22.0]), ('C36', [78.0, 22.0])]]},
    'brackets': None,  # copied verbatim from the old contract in geometry()
    'solder_tail_max_below_B_Cu_mm': 1.8,
    'hand_solder_clearance_mm': 2.0,
    'edge_keepout_mm': 1.0,
    'smd_parking': {'origin_native_mm': [160.0, 60.0], 'pitch_mm': [6.0, 5.0], 'columns': 16,
                    'note': 'Unplaced SMD parked OFF-BOARD to the +native-x side (beyond Y114.5): NOT placed'},
}


def old_contract():
    return json.loads((OLD / 'docs/assembly-geometry.json').read_text())


def geometry():
    g = deepcopy(GEOMETRY)
    g['brackets'] = deepcopy(old_contract()['brackets'])
    return g


def carrier_xy(y, z):
    return (round(y + 35.75, 5), round(104.275 - z, 5))


def panel_xy(x, y):
    return (round(x + 50.0, 5), round(y + 30.0, 5))


def carrier_outline(g=None):
    g = g or geometry()
    y0, y1 = g['carrier_Y_mm']
    z0, z1 = g['carrier_Z_mm']
    (a0, a1, az), (b0, b1, bz) = g['carrier_bracket_reliefs_YZ_mm']
    return [(y0, z0), (a0, z0), (a0, az), (a1, az), (a1, z0), (b0, z0), (b0, bz), (b1, bz), (b1, z0),
            (y1, z0), (y1, z1), (y0, z1)]


def header_frame(h):
    """Centre of the 2x8 pin field (Y, Z) for the rotated header (local +x -> -Z, +y -> -Y)."""
    y1, z1 = h['pin1_YZ_mm']
    return y1 - 8.89, z1 - 1.27


def envelopes(g):
    """Conservative XYZ solid envelopes. Keys: name -> (kind, [[x0,x1],[y0,y1],[z0,z1]])."""
    j = g['mouth_axis_XYZ_mm'][1]
    s = g['reset_XY_diameter_mm'][1]
    fcu = g['carrier_X_mm'][1]
    env = {'J1': ('manufacturer drawing envelope (no model)', [[fcu, 7.46], [j - 4.82, j + 4.82], [0.8, 9.22]]),
           'SW1': ('manufacturer drawing envelope (no model)', [[fcu, 7.4], [s - 3.1, s + 3.1], [2.05, 6.9]])}
    for led in g['LEDs']:
        y = led['panel_XY_diameter_mm'][1]
        env[led['reference']] = ('generic 3 mm LED envelope', [[fcu, 8.0], [y - 2.17, y + 2.17], [-0.2, 7.27]])
    L, W, H = g['header']['body_LWH_max_mm']
    mp = g['mating_plug']
    for h in g['headers']:
        yc, zc = header_frame(h)
        r = h['reference']
        env[r] = ('Wurth 61201621621 body max', [[fcu, fcu + H], [yc - L / 2, yc + L / 2], [zc - W / 2, zc + W / 2]])
        pl, pw = mp['proposal_body_LW_mm']
        env[r + '_plug'] = ('PROPOSAL mated IDC socket envelope', [mp['proposal_X_mm'], [yc - pl / 2, yc + pl / 2],
                                                                   [zc - pw / 2, zc + pw / 2]])
        env[r + '_ribbon'] = ('PROPOSAL ribbon envelope (continues to bus)',
                              [mp['ribbon_X_mm'], [yc - mp['ribbon_width_Y_mm'] / 2, yc + mp['ribbon_width_Y_mm'] / 2],
                               [zc + pw / 2, mp['ribbon_shown_to_Z_mm']]])
    c = g['cans']
    for p in c['parts']:
        y, z = p['YZ_mm']
        hb = c['base_square_mm'] / 2
        env[p['reference']] = ('PROVISIONAL can position, MVK max body',
                               [[fcu, fcu + c['height_max_mm']], [y - hb, y + hb], [z - hb, z + hb]])
    return env


def overlap(a, b):
    return all(min(x[1], y[1]) - max(x[0], y[0]) > 1e-7 for x, y in zip(a, b))


def prisms(outline, x_range):
    ys = sorted({v[0] for v in outline})
    for lo, hi in zip(ys, ys[1:]):
        mid = (lo + hi) / 2
        zs = sorted(a[1] for a, b in zip(outline, outline[1:] + outline[:1])
                    if a[1] == b[1] and min(a[0], b[0]) < mid < max(a[0], b[0]))
        for z0, z1 in zip(zs[::2], zs[1::2]):
            yield [x_range, [lo, hi], [z0, z1]]


def fastener_solids(g, y):
    """Bracket, screw/nut and tool-path boxes at bracket centre Y (old m3_fit.py geometry)."""
    b = g['brackets']
    fx = b['front_hole_X_mm']
    foot_back = b['front_foot_Z_mm'][1]
    nr = b['nut_AF_max_mm'] / math.sqrt(3)
    rr = b['side_nut_driver_diameter_max_mm'] / 2
    bx = g['carrier_X_mm']
    sz = b['side_hole_Z_mm']
    return {
        'foot': [b['outer_X_mm'], [y - 5, y + 5], b['front_foot_Z_mm']],
        'web': [b['side_web_X_mm'], [y - 5, y + 5], [foot_back, b['outer_Z_mm'][1]]],
        'front_nut': [[fx - nr, fx + nr], [y - nr, y + nr], [foot_back, foot_back + b['nut_thickness_max_mm']]],
        'side_nut': [[bx[1], bx[1] + b['nut_thickness_max_mm']], [y - nr, y + nr], [sz - nr, sz + nr]],
        'tools': {
            'front_nut_entry': [[fx - nr, 30], [y - nr, y + nr], [foot_back, foot_back + b['nut_thickness_max_mm']]],
            'front_nut_pliers': [b['front_tool_X_mm'], [y - b['front_tool_Y_width_mm'] / 2, y + b['front_tool_Y_width_mm'] / 2],
                                 b['front_tool_Z_mm']],
            'side_nut_driver': [[bx[1], 30], [y - rr, y + rr], [sz - rr, sz + rr]],
            'front_screwdriver': [[fx - 1.5, fx + 1.5], [y - 1.5, y + 1.5], [-25, 0]],
            'side_screwdriver': [[-25, 0.1], [y - 1.5, y + 1.5], [sz - 1.5, sz + 1.5]]}}


def verify(g):
    """Nominal mechanical checks. Returns (report, problems). Problems are listed, never waived."""
    rep, problems = {}, []
    pw, ph, pt = g['panel_mm']
    blank = json.loads((MODULE.parents[1] / 'modules/blank/docs/geometry.json').read_text())
    b4 = next(p for p in blank['panels'] if p['hp'] == 4)
    rep['panel_matches_blank_4hp'] = (pw == b4['width_mm'] and ph == blank['panel_height_mm']
                                      and [h[0] for h in g['rail_holes_mm']] == b4['rail_hole_X_mm'] * 2
                                      and [h[1] for h in g['rail_holes_mm']] == blank['rail_hole_Y_mm'])
    if not rep['panel_matches_blank_4hp']:
        problems.append('panel/rail holes differ from blank 4HP precedent')
    rails = {(h[0], h[1]) for h in g['rail_holes_mm']}
    brk = {(h[0], h[1]) for h in g['panel_bracket_holes_mm']}
    rep['rail_vs_bracket_holes_distinct'] = not (rails & brk)
    # old contract invariants: carrier plane, bracket, holes and reliefs copied unchanged
    old = old_contract()
    copied = {k: old[k] == g[k] for k in ['carrier_X_mm', 'carrier_holes_YZ_mm', 'carrier_bracket_reliefs_YZ_mm',
                                          'panel_bracket_holes_mm', 'brackets', 'aperture_XYWHR_mm',
                                          'mouth_axis_XYZ_mm']}
    copied['carrier_Y_mm'] = old['carrier_Y_mm'] == g['carrier_Y_mm']
    rep['copied_from_old_usb_power'] = copied
    if not all(copied.values()):
        problems.append(f'copied geometry drift: {copied}')
    rep['changed_from_old_usb_power'] = {
        'panel_width': [old['panel_mm'][0], pw], 'rail_hole_X': [old['rail_holes_mm'][0][0], g['rail_holes_mm'][0][0]],
        'carrier_rear_Z': [37.0, g['carrier_Z_mm'][1]],
        'panel_LEDs': 'one D10 at Y43 -> four D8/D16/D17/D18 at Y43/49.5/56/62.5 (6.5 pitch, same X6.1/hole 3.6)',
        'reset_Y': [old['reset_XY_diameter_mm'][1], g['reset_XY_diameter_mm'][1]],
        'output_header': 'single J7 2x8 -> J2 + J3 2x8 at the rear edge'}
    # Panel holes/aperture: inside the panel, clear of rail heads and of each other.
    head = g['rail_head_diameter_mm'] / 2
    holes = ([('rail', *h) for h in g['rail_holes_mm']] + [('bracket', *h) for h in g['panel_bracket_holes_mm']]
             + [(l['reference'], *l['panel_XY_diameter_mm']) for l in g['LEDs']]
             + [('SW1', *g['reset_XY_diameter_mm'])])
    ax, ay, aw, ah, ar = g['aperture_XYWHR_mm']
    web = {}
    for n, x, y, d in holes:
        web[n + f'@Y{y:g}_edge_ligament'] = round(min(x - d / 2, pw - x - d / 2, y - d / 2, ph - y - d / 2), 3)
    web['USB_aperture_edge_ligament'] = round(min(ax, pw - ax - aw), 3)
    ui = sorted([(y - d / 2, y + d / 2, n) for n, x, y, d in holes if n not in ('rail', 'bracket')]
                + [(ay, ay + ah, 'USB')])
    for (a0, a1, an), (b0, b1, bn) in zip(ui, ui[1:]):
        web[f'{an}_to_{bn}_panel_web'] = round(b0 - a1, 3)
    web['USB_aperture_to_top_bracket_head'] = round(ay - (22 + head), 3)
    web['rail_head_to_bracket_head_Y_gap'] = round(22 - head - (3 + head), 3)
    rep['panel_ligaments_mm'] = web
    if min(web.values()) < 0.6:
        problems.append(f'panel ligament < 0.6 mm: {web}')
    # Envelope solder-access gaps along Y in the front cluster (old rule >= 0.8 mm).
    env = envelopes(g)
    front = sorted(['J1', 'SW1'] + [l['reference'] for l in g['LEDs']], key=lambda r: env[r][1][1][0])
    gaps = {f'{a}_to_{b}': round(env[b][1][1][0] - env[a][1][1][1], 3) for a, b in zip(front, front[1:])}
    rep['front_cluster_access_gaps_mm'] = gaps
    if min(gaps.values()) < 0.8:
        problems.append(f'front cluster access gap < 0.8: {gaps}')
    # Width: every module solid within the 4HP envelope; B-side tails inside X >= 0.
    width = {k: round(pw - v[1][0][1], 3) for k, v in env.items() if not k.endswith('_ribbon')}
    width.update({k: round(pw - v[1][0][1], 3) for k, v in env.items() if k.endswith('_ribbon')})
    sr = g['carrier_X_mm'][1] + g['mating_plug']['strain_relief_worst_height_mm']
    width['IDC_strain_relief_worst_case'] = round(pw - sr, 3)
    rep['margin_to_panel_right_edge_X20_mm'] = width
    rep['B_side_tail_min_X_mm'] = round(g['carrier_X_mm'][0] - g['solder_tail_max_below_B_Cu_mm'], 3)
    over = {k: v for k, v in width.items() if v < 0}
    rep['width_conflicts'] = over
    if set(over) - {'IDC_strain_relief_worst_case'}:
        problems.append(f'solid envelope beyond the 4HP panel edge: {over}')
    # Depth.
    z1 = g['carrier_Z_mm'][1]
    solid_z = max(v[1][2][1] for k, v in env.items() if not k.endswith('_ribbon'))
    lim = g['depth_target']['limit_behind_panel_rear_mm']
    rep['depth_mm'] = {
        'bare_carrier_rear_from_panel_front': z1, 'bare_carrier_behind_panel_rear': round(z1 - pt, 3),
        'assembled_solid_max_from_panel_front': round(max(solid_z, z1), 3),
        'assembled_solid_max_behind_panel_rear': round(max(solid_z, z1) - pt, 3),
        'limit_behind_panel_rear': lim, 'margin_behind_rear_reading': round(lim - (max(solid_z, z1) - pt), 3),
        'margin_strict_from_front_reading': round(42.0 - max(solid_z, z1), 3),
        'cabled_envelope_from_panel_front': round(max(v[1][2][1] for k, v in env.items() if k.endswith('_ribbon')), 3),
        'cabled_envelope_behind_panel_rear': round(max(v[1][2][1] for k, v in env.items() if k.endswith('_ribbon')) - pt, 3),
        'cabled_depth_within_42': False,
        'datum_note': 'Both datums shown; none shifted. Bare board/solids Z42.0 from the panel front = 40.4 behind '
                      'the rear. The PROVISIONAL cable envelope reaches Z50 from the front = 48.4 behind the rear, '
                      'so the cabled depth is NOT <= 42 in this draft (cable route still open).',
        'ribbon': f'leaves the plug at Z <= {max(v[1][2][1] for k, v in env.items() if k.endswith("_plug")):.2f} '
                  'toward +Z (the case floor); it necessarily continues past the module envelope to the bus '
                  'header - shown to Z50, not counted as module depth',
        'front_protrusion': 'LED tips Z-0.2 (0.2 mm proud of the panel front, as old D10); screw heads in front'}
    if max(solid_z, z1) - pt > lim:
        problems.append('assembled depth exceeds target')
    # Rail clearance.
    rp = g['rail_profile_YZ_mm']
    rep['rail_clearance_mm'] = {'carrier_top_to_rail': round(g['carrier_Y_mm'][0] - rp['top_Y'][1], 3),
                                'carrier_bottom_to_rail': round(rp['bottom_Y'][0] - g['carrier_Y_mm'][1], 3),
                                'bracket_top_to_rail': round(22 - 5 - rp['top_Y'][1], 3),
                                'bracket_bottom_to_rail': round(rp['bottom_Y'][0] - 111.5, 3)}
    if min(rep['rail_clearance_mm'].values()) < 1:
        problems.append('rail clearance < 1 mm')
    # Envelope-to-envelope collisions (solids only).
    solids = {k: v[1] for k, v in env.items()}
    coll = []
    keys = sorted(solids)
    for i, a in enumerate(keys):
        for bkey in keys[i + 1:]:
            same = a.split('_')[0] == bkey.split('_')[0]
            if not same and overlap(solids[a], solids[bkey]):
                coll.append([a, bkey])
    rep['envelope_collisions'] = coll
    if coll:
        problems.append(f'envelope collisions: {coll}')
    # M3 fastening and tool paths (ported from usb-power/tools/m3_fit.py, 4HP width).
    b = g['brackets']
    outline = carrier_outline(g)
    board = list(prisms(outline, g['carrier_X_mm']))
    nr = b['nut_AF_max_mm'] / math.sqrt(3)
    fx = b['front_hole_X_mm']
    front_exit = b['front_length_mm'] - b['front_foot_Z_mm'][1] - b['nut_thickness_max_mm']
    side_tip = [b['outer_X_mm'][0] + r + b['side_length_mm'] for r in b['side_head_recess_mm']]
    side_exit = side_tip[0] - g['carrier_X_mm'][1] - b['nut_thickness_max_mm']
    m3 = []
    for y in b['Y_centres_mm']:
        f = fastener_solids(g, y)
        bad = []
        for name in ('foot', 'web'):
            bad += [f'{name} x PCB' for s in board if overlap(f[name], s)]
            bad += [f'{name} x {k}' for k, s in solids.items() if overlap(f[name], s)]
        for tname, tool in f['tools'].items():
            bad += [f'{tname} x PCB' for s in board if overlap(tool, s)]
            bad += [f'{tname} x {k}' for k, s in solids.items() if overlap(tool, s)]
            bad += [f'{tname} x {k}' for k in ('foot', 'web') if overlap(tool, f[k])]
        bad += [f'side_nut x {k}' for k, s in solids.items() if overlap(f['side_nut'], s)]
        m3.append({'Y_mm': y, 'blocked': sorted(set(bad)),
                   'front_bolt_exposure_mm': round(front_exit, 3), 'side_bolt_exposure_min_mm': round(side_exit, 3),
                   'front_nut_upright_clearance_mm': round(fx - nr - b['side_web_X_mm'][1], 3),
                   'front_nut_right_X_mm': round(fx + nr, 3), 'front_head_right_X_mm': fx + b['front_head_diameter_max_mm'] / 2,
                   'side_tip_X_mm': [round(v, 3) for v in side_tip]})
        if bad:
            problems.append(f'M3 access blocked at Y{y}: {sorted(set(bad))}')
    rep['m3_fastening'] = {'brackets': m3, 'service': b['access'],
                           'limitation': 'Nominal envelopes; actual tools, ABS shrinkage and screw seating need trial.'}
    return rep, problems


def main():
    g = geometry()
    g['envelopes_XYZ_mm'] = {k: {'kind': v[0], 'XYZ': v[1]} for k, v in envelopes(g).items()}
    rep, problems = verify(g)
    out = MODULE / 'docs/mechanical-geometry.json'
    out.write_text(json.dumps(g, indent=1) + '\n')
    chk = MODULE / 'docs/mechanical-preview/contract-check.json'
    chk.parent.mkdir(exist_ok=True)
    chk.write_text(json.dumps({'report': rep, 'problems': problems}, indent=1) + '\n')
    print(json.dumps({'report': rep, 'problems': problems}, indent=1))


if __name__ == '__main__':
    main()
