"""Seed the S8 single board (P0, UNROUTED) from the S8 schematic with KiCad's pcbnew 10.

  python3 -B tools/build_s8_board.py [--output-root <candidate-module-root>]

Writes hardware/single/usb-power-45w-single.kicad_pcb (+ .kicad_dru): the single-carrier outline from
tools/mechanics_s8.py (Y14..114.5 x Z2..50, both bracket cutbacks, M3 holes), the panel parts J1,
SW1 and D8 at their panel-registered positions and the TWO output headers J2 (pin 1 Y76) and J3
(pin 1 Y107) at the rear edge (pin 1 Z44), with their IDC plug envelopes drawn on User.Drawings.
Every other part is PARKED OFF-BOARD; tools/place_s8.py places them (P1). No tracks, vias or zones.
References, values, fields, symbol links and pad nets come from the native S8 netlist, as
"Update PCB from Schematic" does. The two J1/SW1 front-edge copper allowances are the R1 rules,
copied unchanged (same pad windows). Refuses to overwrite a board that has copper, zones or parts
placed beyond the seed (an S8-candidate P0 seed with D16-D18 at the panel still counts as a seed).
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_layout as bl  # noqa: E402  (shared M1 placement/graphics helpers; its own writers stay refused)
import build_s8  # noqa: E402
import mechanics_s8  # noqa: E402
from build_layout import CV, V, line, place, rect, shape, text  # noqa: E402
from mechanics45 import envelopes  # noqa: E402
from stack_r2 import R1_ARCHIVE  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
FIXED = ['J1', 'SW1', 'D8', 'J2', 'J3']
SEED_FIXED = set(FIXED) | {'D16', 'D17', 'D18'}     # the S8-candidate P0 seed also had the rail LEDs placed


def geometry():
    g = mechanics_s8.geometry()
    g['envelopes_XYZ_mm'] = {k: {'kind': v[0], 'XYZ': v[1]} for k, v in envelopes(g).items()}
    return g


GEO = geometry()


def netlist(root_sch):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(root_sch)], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') != 'Footprint'}
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        sp = c.find('sheetpath')
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'path': sp.get('tstamps') + c.findtext('tstamps').split()[0],
                               'sheetname': sp.get('names'), 'sheetfile': props.get('Sheetfile', ''),
                               'fields': fields, 'no_bom': 'exclude_from_bom' in props,
                               'no_pos': 'exclude_from_pos_files' in props, 'dnp': 'dnp' in props}
    nets = {bl.net_name(n.get('name')): [(d.get('ref'), d.get('pin')) for d in n.findall('node')]
            for n in root.find('nets')}
    return comps, nets


def seed_board(root=MODULE):
    """The P0 seed as an in-memory pcbnew BOARD (also the starting point of tools/place_s8.py)."""
    comps, nets = netlist(build_s8.root_file(root))
    G = GEO
    board = bl.new_board('Big Modular - usb-power-45w S8 single board', [
        'S8 final schematic. UNROUTED: no tracks/vias/zones. Not a release.',
        'Single carrier Y14..114.5 x Z2..50 (50 mm deep), every part on F',
        'J1 SW1 D8 at the panel; J2 + J3 (two IDC outputs) at the rear edge',
        'Nets: hardware/single/usb-power-45w-single.kicad_sch; geometry: docs/s8-single/mechanical.json'], 'S8-P0')
    board.SetCopperLayerCount(G['carrier_layers'])
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(G['carrier_thickness_mm']))
    pts = bl.carrier_outline(G)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        line(board, pcbnew.Edge_Cuts, CV(*a), CV(*b))
    for y, z in G['carrier_holes_YZ_mm']:
        bl.npth(board, '', f'M3_Y{y:g}', CV(y, z), G['carrier_hole_mm'], 'M3 bracket hole')
    placed = {}
    j1 = G['USB']
    placed['J1'] = place(board, 'J1', comps['J1'], V(*j1['native_origin_xy_mm']), j1['orientation_deg'])
    for led in G['LEDs']:
        placed[led['reference']] = place(board, led['reference'], comps[led['reference']], CV(*led['pad1_YZ_mm']))
    placed['SW1'] = place(board, 'SW1', comps['SW1'], CV(*G['switch']['peg_row_YZ_mm']))
    for h in G['headers']:
        placed[h['reference']] = place(board, h['reference'], comps[h['reference']], CV(*h['pin1_YZ_mm']),
                                       h['rotation_deg'])
    assert sorted(placed) == sorted(FIXED), sorted(placed)
    key = lambda r: (''.join(ch for ch in r if ch.isalpha()), int(''.join(ch for ch in r if ch.isdigit())))
    px, py = G['smd_parking']['origin_native_mm']
    x, y, row_h, xmax = px, py, 0.0, px + 95
    for ref in sorted(set(comps) - set(placed), key=key):
        fp = place(board, ref, comps[ref], V(0, 0))
        l, t, r, b = (pcbnew.ToMM(v) for v in bl.courtyard(fp))
        w, h = r - l, b - t
        if x + w > xmax:
            x, y, row_h = px, y + row_h + 0.6, 0.0
        fp.Move(V(x - l, y - t))
        x += w + 0.6
        row_h = max(row_h, h)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints() if fp.GetReference()}
    assert set(fps) == set(comps), set(fps) ^ set(comps)
    for name, members in nets.items():
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        net.thisown = 0
        for ref, pin in members:
            pads = [p for p in fps[ref].Pads() if p.GetNumber() == pin]
            assert pads, f'{ref} has no pad {pin}'
            for p in pads:
                p.SetNet(net)
    for fp in fps.values():
        for p in fp.Pads():
            assert p.GetNumber() == '' or p.GetNetname(), f'{fp.GetReference()} pad {p.GetNumber()} has no net'
    D, C = pcbnew.Dwgs_User, pcbnew.Cmts_User
    b = G['brackets']
    for yc in b['Y_centres_mm']:
        rect(board, D, CV(yc - 5, b['front_foot_Z_mm'][1]), CV(yc + 5, b['outer_Z_mm'][1]), 0.1)
        text(board, D, 'BRACKET WEB on B face', CV(yc, 21.2), 0.8)
        r = b['side_nut_driver_diameter_max_mm'] / 2
        shape(board, D, pcbnew.SHAPE_T_CIRCLE, 0.1, center=CV(yc, b['side_hole_Z_mm']),
              end=CV(yc + r, b['side_hole_Z_mm']))
        text(board, C, 'M3 nut + 8 mm driver keep-out', CV(yc, b['side_hole_Z_mm'] + 4.9), 0.8)
    for h in G['headers']:
        e = G['envelopes_XYZ_mm'][h['reference'] + '_plug']['XYZ']
        rect(board, D, CV(e[1][0], e[2][0]), CV(e[1][1], e[2][1]), 0.1)      # mated IDC plug envelope (PROPOSAL)
        hp = {p.GetNumber(): p.GetPosition() for p in placed[h['reference']].Pads()}
        x1, y1, y2 = pcbnew.ToMM(hp['1'].x), pcbnew.ToMM(hp['1'].y), pcbnew.ToMM(hp['2'].y)
        # pin-1 / red-stripe marking on the rear side of the box (the header strip parts sit in front of it)
        text(board, pcbnew.F_SilkS, '1 / -12V / RED', V(x1 - 0.9, y1 - 4.8), 0.8, justify=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
        for i, lab in enumerate(['N12', 'GND', 'GND', 'GND', 'P12', 'NC', 'NC', 'NC']):
            text(board, pcbnew.B_SilkS, lab, V(x1 - 2.54 * i, y2 + 2.16), 0.8, mirror=True)
    y0, y1 = G['carrier_Y_mm']
    z = G['depth_target']['limit_from_panel_front_mm']
    text(board, C, f'Rear edge Z{z:g}: {z:g} mm from the panel front (user depth limit)', CV((y0 + y1) / 2, z + 0.9), 0.8)
    text(board, C, 'PARKED OFF-BOARD: NOT PLACED', V(px + 40, py - 3), 1.2)
    return board


def seed_refusal(dest):
    """Reason the seed must not overwrite `dest`, or None."""
    if not dest.exists():
        return None
    old = pcbnew.LoadBoard(str(dest))
    outline = pcbnew.SHAPE_POLY_SET()
    old.GetBoardPolygonOutlines(outline, True)
    moved = sorted(fp.GetReference() for fp in old.GetFootprints()
                   if fp.GetReference() and fp.GetReference() not in SEED_FIXED and outline.Contains(fp.GetPosition()))
    if list(old.GetTracks()) or list(old.Zones()) or moved:
        return (f'{dest}: has copper/zones or placed parts ({", ".join(moved[:8])}); the native board owns '
                'placement and routing now, the seed is never rewritten.')
    return None


def save(board, dest):
    hw = dest.parent
    bl.save_canonical(board, dest, hw / f'{build_s8.STEM}.kicad_pro', bl.STACKUP_4L)
    shutil.copyfile(R1_ARCHIVE.with_suffix('.kicad_dru'), dest.with_suffix('.kicad_dru'))
    return dest


def build(output_root=None):
    root = Path(output_root).resolve() if output_root else MODULE
    dest = build_s8.single_dir(root) / f'{build_s8.STEM}.kicad_pcb'
    why = seed_refusal(dest)
    if why:
        raise SystemExit(why)
    return save(seed_board(root), dest)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-root', type=Path)
    print(build(ap.parse_args().output_root))
