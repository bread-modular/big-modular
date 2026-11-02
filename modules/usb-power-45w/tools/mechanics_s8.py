"""S8 single-board mechanical contract (P1 trial placement, unrouted). mm, stdlib only.

  python3 -B tools/mechanics_s8.py            # write docs/s8-single/mechanical.json (+ checks)

The M1 contract (tools/mechanics45.py: frame, panel, carrier plane X2.5..4.1, Y14..114.5, bracket
holes/cutbacks, brackets, fasteners, J1/SW1/LED registration, IDC plug envelope) with the S8
changes the user asked for on 2026-11-01:

- "you can go up to 50mm depth for panel": the board grows from Z42 to **Z50 from the panel
  front** (48.4 mm behind its rear face). Every board part stays inside Z50; only the ribbon
  leaves past the rear edge toward the bus header.
- "Remove each rail LEDs too": one panel LED (D8 MAIN, Y43). SW1 RESET keeps Y69.
- J2 / J3 move with the rear edge: pin 1 at Z44 (was Z36), same Y76 / Y107, same rotation.
- No electrolytic cans (S8 is all-ceramic). "Use single side": every part on F.

Frame (unchanged): origin at the panel's upper-left FRONT corner, X across, Y down, Z into the
case. Native carrier map: native x = Y + 35.75, native y = 104.275 - Z.
Nominal envelopes, not a physical-fit, strength or tolerance qualification.
S8.4 (review M9): main() also writes an explicit `risks` list derived from the checks (IDC strain-relief
overshoot past the 4HP panel edge, the 1.1 mm IDC envelope margin, case depth, nominal proxies).
"""
import json
import math
from copy import deepcopy
from pathlib import Path

import mechanics45 as m45

MODULE = Path(__file__).resolve().parents[1]
OUT = MODULE / 'docs/s8-single/mechanical.json'
DEPTH_Z = 50.0           # board rear edge, from the panel FRONT (user: "up to 50mm depth")
HEADER_PIN1_Z = 44.0     # J2/J3 pin 1 row moves 8 mm with the rear edge (M1: Z36 at a Z42 edge)
CASE = {'source': 'modules/busboard/README.md + tools/mechanics45.py depth basis (60 mm case)',
        'plate_top_behind_panel_rear_mm': 58.4, 'bus_header_top_above_plate_mm': 15.7}


def geometry():
    g = m45.geometry()
    g['revision'] = 'S9.1 single board P2.1: one carrier, every part on F, trial placement, UNROUTED'
    g['status'] = 'Trial placement for review. No tracks, vias or zones. Not a release.'
    g['carrier_Z_mm'] = [2.0, DEPTH_Z]
    g['depth_target'] = {
        'limit_from_panel_front_mm': DEPTH_Z,
        'limit_behind_panel_rear_mm': round(DEPTH_Z - g['panel_mm'][2], 3),
        'basis': 'user 2026-11-01: "you can go up to 50mm depth for panel". Read strictly: the board and every '
                 'part end at Z50 from the panel FRONT (= 48.4 behind its rear face), which satisfies both readings',
        'case_note': 'In the 60 mm case (bus plate top 58.4 behind the panel rear, bus header tops 15.7 above it) '
                     'the bus headers end 42.7 behind the panel rear: a 48.4 deep board must sit beside a bus '
                     'header, not over it. The case/cable route is a user check, not modelled here.'}
    g['LEDs'] = [l for l in g['LEDs'] if l['reference'] == 'D8']
    g['LED']['note'] = ('S8: one panel LED (D8 MAIN). No LED MPN selected (manual part, user stock 3 mm red). '
                        'Form leads in a jig with the panel.')
    g['headers'] = [{'reference': 'J2', 'pin1_YZ_mm': [76.0, HEADER_PIN1_Z], 'rotation_deg': 270},
                    {'reference': 'J3', 'pin1_YZ_mm': [107.0, HEADER_PIN1_Z], 'rotation_deg': 270}]
    g['header']['note'] = 'J2/J3 = Wurth 61201621621 (selected in the S8 table), hand-soldered THT.'
    g['mating_plug']['ribbon_shown_to_Z_mm'] = DEPTH_Z + 8.0
    g['cans'] = {'status': 'none: S8 is all-ceramic', 'parts': []}
    g['single_side'] = 'every part on F (user 2026-11-01: "Use single side for now"); B face: copper only'
    g['inductor_body'] = {'parts': ['L1', 'L3'], 'body_LWH_max_mm': [10.3, 10.3, 4.0],     # S9.0: L2 (+5V) removed
                          'basis': 'SLO1040 class 10 x 10 x 4.0 mm (footprint L_SLO1040H6R8MTT has no 3D model; '
                                   'renders use a 10 x 10 x 4 proxy)'}
    return g


def verify(g):
    """Nominal checks of the contract itself (panel, width, depth, rails, M3 paths vs the bare board).
    Part-level placement checks live in tools/check_s8_board.py."""
    rep, problems = {}, []
    pw, ph, pt = g['panel_mm']
    env = m45.envelopes(g)
    holes = ([('rail', *h) for h in g['rail_holes_mm']] + [('bracket', *h) for h in g['panel_bracket_holes_mm']]
             + [(l['reference'], *l['panel_XY_diameter_mm']) for l in g['LEDs']] + [('SW1', *g['reset_XY_diameter_mm'])])
    ax, ay, aw, ah, ar = g['aperture_XYWHR_mm']
    lig = {n + f'@Y{y:g}': round(min(x - d / 2, pw - x - d / 2, y - d / 2, ph - y - d / 2), 3) for n, x, y, d in holes}
    lig['USB_aperture'] = round(min(ax, pw - ax - aw), 3)
    ui = sorted([(y - d / 2, y + d / 2, n) for n, x, y, d in holes if n not in ('rail', 'bracket')] + [(ay, ay + ah, 'USB')])
    for (a0, a1, an), (b0, b1, bn) in zip(ui, ui[1:]):
        lig[f'{an}_to_{bn}_web'] = round(b0 - a1, 3)
    rep['panel_ligaments_mm'] = lig
    if min(lig.values()) < 0.6:
        problems.append(f'panel ligament < 0.6 mm: {lig}')
    width = {k: round(pw - v[1][0][1], 3) for k, v in env.items()}
    width['inductor_body'] = round(pw - (g['carrier_X_mm'][1] + g['inductor_body']['body_LWH_max_mm'][2]), 3)
    sr = g['carrier_X_mm'][1] + g['mating_plug']['strain_relief_worst_height_mm']
    width['IDC_strain_relief_worst_case'] = round(pw - sr, 3)
    rep['margin_to_panel_right_edge_X20_mm'] = width
    if {k for k, v in width.items() if v < 0} - {'IDC_strain_relief_worst_case'}:
        problems.append('solid envelope beyond the 4HP panel edge')
    z1 = g['carrier_Z_mm'][1]
    solids = {k: v for k, v in env.items() if not k.endswith('_ribbon')}
    solid_z = max(v[1][2][1] for v in solids.values())
    lim = g['depth_target']['limit_from_panel_front_mm']
    bus_top = CASE['plate_top_behind_panel_rear_mm'] - CASE['bus_header_top_above_plate_mm'] + pt
    rep['depth_mm'] = {'board_rear_from_panel_front': z1, 'board_rear_behind_panel_rear': round(z1 - pt, 3),
                       'deepest_solid_from_panel_front': round(max(solid_z, z1), 3),
                       'limit_from_panel_front': lim, 'margin': round(lim - max(solid_z, z1), 3),
                       'plug_envelope_rear_Z': round(max(v[1][2][1] for k, v in env.items() if k.endswith('_plug')), 3),
                       'ribbon': 'leaves the plug toward +Z and continues past Z50 to the bus header (not module depth)',
                       'bus_header_tops_Z_in_60mm_case': round(bus_top, 3),
                       'board_below_bus_header_tops_mm': round(z1 - bus_top, 3)}
    if max(solid_z, z1) > lim + 1e-9:
        problems.append('a solid passes the 50 mm depth limit')
    rp = g['rail_profile_YZ_mm']
    rep['rail_clearance_mm'] = {'carrier_top_to_rail': round(g['carrier_Y_mm'][0] - rp['top_Y'][1], 3),
                                'carrier_bottom_to_rail': round(rp['bottom_Y'][0] - g['carrier_Y_mm'][1], 3)}
    if min(rep['rail_clearance_mm'].values()) < 1:
        problems.append('rail clearance < 1 mm')
    keys = sorted(solids)
    coll = [[a, b] for i, a in enumerate(keys) for b in keys[i + 1:]
            if a.split('_')[0] != b.split('_')[0] and m45.overlap(solids[a][1], solids[b][1])]
    rep['envelope_collisions'] = coll
    if coll:
        problems.append(f'envelope collisions: {coll}')
    b = g['brackets']
    board = list(m45.prisms(m45.carrier_outline(g), g['carrier_X_mm']))
    m3 = []
    for y in b['Y_centres_mm']:
        f = m45.fastener_solids(g, y)
        bad = [f'{n} x PCB' for n in ('foot', 'web') for s in board if m45.overlap(f[n], s)]
        bad += [f'{t} x PCB' for t, tool in f['tools'].items() for s in board if m45.overlap(tool, s)]
        bad += [f'{t} x {k}' for t, tool in f['tools'].items() for k, s in solids.items() if m45.overlap(tool, s[1])]
        m3.append({'Y_mm': y, 'blocked': sorted(set(bad))})
        if bad:
            problems.append(f'M3 access blocked at Y{y}: {sorted(set(bad))}')
    rep['m3_bare_board'] = m3
    rep['m3_parts'] = 'F-side nut + 8 mm driver circles (Y22/Y106.5, Z15, r4.0) are checked against every placed ' \
                      'courtyard and 3D body by tools/check_s8_board.py'
    return rep, problems


def risks(g, rep):
    """S8.4 (review M9): open mechanical risks, numbers taken from the checks so they cannot drift."""
    width = rep['margin_to_panel_right_edge_X20_mm']
    plug = min(width[f'{h["reference"]}_{k}'] for h in g['headers'] for k in ('plug', 'ribbon'))
    sr = width['IDC_strain_relief_worst_case']
    return [
        {'id': 'IDC_strain_relief_overshoot', 'severity': 'open (not approved)',
         'value_mm': sr, 'measure': 'margin to the 4HP panel edge X20 (negative = beyond the panel)',
         'detail': f'A clip-type strain relief at the drawing worst case ({g["mating_plug"]["strain_relief_worst_height_mm"]}'
                   f' mm mated height) reaches X{20 - sr:g}: {abs(sr):g} mm past the 4HP edge, into the neighbouring '
                   'module. Use a socket without the tall strain relief (or measure a lower one) on J2/J3.'},
        {'id': 'IDC_envelope_margin', 'severity': 'open (tight)', 'value_mm': plug,
         'measure': 'mated IDC plug/ribbon envelope margin to the 4HP panel edge X20',
         'detail': f'The PROPOSAL mated envelope (14.8 mm max above F.Cu) leaves only {plug:g} mm. The cable/plug is '
                   'not in the BOM and the drawing dimensions were text-extracted; freeze the socket/ribbon part and '
                   'check the tolerance stack with the neighbouring module in the case.'},
        {'id': 'case_depth', 'severity': 'open (user check)',
         'value_mm': rep['depth_mm']['board_below_bus_header_tops_mm'],
         'measure': 'board rear edge below the bus header tops in the 60 mm case',
         'detail': 'The 48.4 mm deep board cannot sit directly over a busboard header in the 60 mm case.'},
        {'id': 'nominal_proxies', 'severity': 'open',
         'detail': 'J1, SW1, L1 and L3 are proxies, not manufacturer models; '
                   'the 3D screen is nominal, not an assembly approval.'}]


def main():
    g = geometry()
    g['envelopes_XYZ_mm'] = {k: {'kind': v[0], 'XYZ': v[1]} for k, v in m45.envelopes(g).items()}
    rep, problems = verify(g)
    g['checks'] = {'report': rep, 'problems': problems}
    g['risks'] = risks(g, rep)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(g, indent=1) + '\n')
    print(json.dumps({'report': rep, 'problems': problems}, indent=1))
    return g


if __name__ == '__main__':
    main()
