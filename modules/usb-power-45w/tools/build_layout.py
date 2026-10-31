"""Generate the usb-power-45w M1 mechanical-preview boards (UNROUTED) with KiCad's pcbnew 10.

Run from the repository root, after tools/mechanics45.py:
  python3 -B modules/usb-power-45w/tools/build_layout.py [--panel-only]

Writes
- hardware/usb-power-45w.kicad_pcb: perpendicular 4-layer carrier. Outline, M3 holes and
  bracket cutbacks copied from modules/usb-power (rear edge moved to Z42). References,
  values, fields, hierarchical symbol links and pad nets come from the native root
  schematic netlist (what "Update PCB from Schematic" does), so every schematic footprint
  is present with exact pads/nets. PLACED: the panel-interface parts J1, SW1, D8, D16-D18,
  the output headers J2/J3, and the four retained cans C5/C34/C35/C36 at PROVISIONAL
  height-context positions. Every other SMD part is PARKED OFF-BOARD (not placed).
  No tracks, vias or zones.
- panels/front-pcb/usb-power-45w-panel.kicad_pcb: passive 4HP panel (outline, USB aperture,
  NPTH holes, silkscreen labels).

Geometry comes from docs/mechanical-geometry.json. The board is built and saved in a
private temporary project copy; only the .kicad_pcb is copied back, so the schematic
project file is never rewritten. Refuses to overwrite a carrier that already has copper.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
sys.path.insert(0, str(MODULE / 'tools'))
from mechanics45 import carrier_outline, carrier_xy, panel_xy  # noqa: E402

GEO = json.loads((MODULE / 'docs/mechanical-geometry.json').read_text())
LIBNAME = 'USBPOWER45'
LIB = HW / f'{LIBNAME}.pretty'
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
CARRIER = HW / 'usb-power-45w.kicad_pcb'
PANEL_DIR = MODULE / 'panels/front-pcb'
PANEL = PANEL_DIR / 'usb-power-45w-panel.kicad_pcb'
OLD_PANEL_PRO = MODULE.parent / 'usb-power/panels/front-pcb/usb-power-panel.kicad_pro'

# JLC04161H-7628 4-layer 1.6 mm stack, same block as modules/4mix and modules/usb-power.
STACKUP_4L = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4 Tg155 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4 Tg155") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4 Tg155 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
\t\t\t(copper_finish "HAL SnPb")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def V(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def CV(y, z):
    return V(*carrier_xy(y, z))


def PV(x, y):
    return V(*panel_xy(x, y))


def schematic_netlist():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / 'usb-power-45w.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
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
    nets = {net_name(n.get('name')): [(d.get('ref'), d.get('pin')) for d in n.findall('node')]
            for n in root.find('nets')}
    return comps, nets


def net_name(name):
    """The XML netlist un-escapes names; KiCad stores a '/' inside an auto-generated pin-name net
    (e.g. Net-(U4-RT/SYNC)) as {slash}, which native DRC parity compares against."""
    for prefix in ('Net-(', 'unconnected-('):
        if name.startswith(prefix):
            return prefix + name[len(prefix):].replace('/', '{slash}')
    return name


def new_board(title, comments, rev):
    board = pcbnew.BOARD()
    tb = board.GetTitleBlock()
    tb.SetTitle(title)
    tb.SetRevision(rev)
    tb.SetCompany('Big Modular')
    for i, t in enumerate(comments):
        tb.SetComment(i, t)
    return board


def shape(board, layer, kind, width=0.05, **pts):
    s = pcbnew.PCB_SHAPE(board, kind)
    s.SetLayer(layer)
    s.SetWidth(pcbnew.FromMM(width))
    if kind == pcbnew.SHAPE_T_ARC:
        s.SetArcGeometry(pts['start'], pts['mid'], pts['end'])
    elif kind == pcbnew.SHAPE_T_CIRCLE:
        s.SetCenter(pts['center'])
        s.SetEnd(pts['end'])
    else:
        s.SetStart(pts['start'])
        s.SetEnd(pts['end'])
    board.Add(s)
    s.thisown = 0
    return s


def line(board, layer, a, b, width=0.05):
    return shape(board, layer, pcbnew.SHAPE_T_SEGMENT, width, start=a, end=b)


def rect(board, layer, a, b, width=0.05):
    return shape(board, layer, pcbnew.SHAPE_T_RECT, width, start=a, end=b)


def text(board, layer, s, at, size, thickness=None, rot=0, justify=None, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(V(size, size))
    t.SetTextThickness(pcbnew.FromMM(thickness or max(0.12, size * 0.15)))
    t.SetPosition(at)
    t.SetTextAngleDegrees(rot)
    if justify is not None:
        t.SetHorizJustify(justify)
    t.SetMirrored(mirror)
    board.Add(t)
    t.thisown = 0


def pad_uuid(ref, number, index):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/usb-power-45w/pcb/pad/{ref}/{number}/{index}'))


def pads_centre(fp):
    boxes = [p.GetBoundingBox() for p in fp.Pads()]
    return pcbnew.VECTOR2I((min(b.GetLeft() for b in boxes) + max(b.GetRight() for b in boxes)) // 2,
                           (min(b.GetTop() for b in boxes) + max(b.GetBottom() for b in boxes)) // 2)


def place(board, ref, comp, at, rot=0, anchor='origin'):
    lib, name = comp['footprint'].split(':')
    assert lib == LIBNAME, comp['footprint']
    fp = IO.FootprintLoad(str(LIB), name)
    fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
    fp.SetReference(ref)
    fp.SetValue(comp['value'])
    fp.SetPath(pcbnew.KIID_PATH(comp['path']))
    fp.SetSheetname(comp['sheetname'])
    fp.SetSheetfile(comp['sheetfile'])
    for key, val in comp['fields'].items():
        fp.SetField(key, val)
        fp.GetField(key).SetVisible(False)
    attrs = fp.GetAttributes()
    if comp['no_bom']:
        attrs |= pcbnew.FP_EXCLUDE_FROM_BOM
    if comp['no_pos']:
        attrs |= pcbnew.FP_EXCLUDE_FROM_POS_FILES
    if comp['dnp']:
        attrs |= pcbnew.FP_DNP
    fp.SetAttributes(attrs)
    for i, pad in enumerate(fp.Pads()):
        pad.SetUuid(pcbnew.KIID(pad_uuid(ref, pad.GetNumber(), i)))
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(at)
    fp.SetOrientationDegrees(rot)
    if anchor == 'centre':
        c = pads_centre(fp)
        fp.Move(pcbnew.VECTOR2I(at.x - c.x, at.y - c.y))
    fp.Reference().SetLayer(pcbnew.F_Fab)
    return fp


def courtyard(fp):
    boxes = [g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_CrtYd]
    return (min(b.GetLeft() for b in boxes), min(b.GetTop() for b in boxes),
            max(b.GetRight() for b in boxes), max(b.GetBottom() for b in boxes))


def npth(board, ref, mech_id, at, d, value='MECHANICAL_NPTH'):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
    fp.SetField('MechanicalID', mech_id)
    fp.GetField('MechanicalID').SetVisible(False)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE)
    size = V(d, d)
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, size)
    pad.SetDrillSize(size)
    pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad)
    pad.thisown = 0
    yard = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    yard.SetLayer(pcbnew.F_CrtYd)
    yard.SetWidth(pcbnew.FromMM(0.05))
    yard.SetCenter(V(0, 0))
    yard.SetEnd(V(d / 2 + 0.25, 0))
    fp.Add(yard)
    yard.thisown = 0
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(at)
    return fp


def save_canonical(board, dest, pro_src, stackup=None):
    """Save in a private temp project (pro copy), insert the stack, reload + re-save, copy back."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        path = tmp / dest.name
        shutil.copyfile(pro_src, path.with_suffix('.kicad_pro'))
        pcbnew.SaveBoard(str(path), board)
        if stackup:
            t = path.read_text()
            assert '(stackup' not in t and t.count('\t(setup\n') == 1
            path.write_text(t.replace('\t(setup\n', '\t(setup\n' + stackup, 1))
        pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))
        pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)


def build_carrier():
    if CARRIER.exists():
        old = pcbnew.LoadBoard(str(CARRIER))
        if list(old.GetTracks()) or list(old.Zones()):
            raise RuntimeError('Refusing to overwrite a carrier with copper/zones; edit it explicitly.')
    comps, nets = schematic_netlist()
    board = new_board('Big Modular - usb-power-45w carrier (M1 mechanical preview)', [
        'M1 PREVIEW, UNROUTED: no tracks/vias/zones. Not a placement or release.',
        'Placed: J1 SW1 D8 D16 D17 D18 J2 J3; C5 C34 C35 C36 PROVISIONAL height context only',
        'All other SMD PARKED OFF-BOARD (native x >= 160): NOT placed',
        'Geometry: docs/mechanical-geometry.json; nets: hardware/usb-power-45w.kicad_sch'], 'M1')
    board.SetCopperLayerCount(GEO['carrier_layers'])
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(GEO['carrier_thickness_mm']))
    pts = carrier_outline(GEO)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        line(board, pcbnew.Edge_Cuts, CV(*a), CV(*b))
    for y, z in GEO['carrier_holes_YZ_mm']:
        npth(board, '', f'M3_Y{y:g}', CV(y, z), GEO['carrier_hole_mm'], 'M3 bracket hole')
    placed = {}
    j1 = GEO['USB']
    placed['J1'] = place(board, 'J1', comps['J1'], V(*j1['native_origin_xy_mm']), j1['orientation_deg'])
    for led in GEO['LEDs']:
        placed[led['reference']] = place(board, led['reference'], comps[led['reference']], CV(*led['pad1_YZ_mm']))
    placed['SW1'] = place(board, 'SW1', comps['SW1'], CV(*GEO['switch']['peg_row_YZ_mm']))
    for h in GEO['headers']:
        placed[h['reference']] = place(board, h['reference'], comps[h['reference']], CV(*h['pin1_YZ_mm']),
                                       h['rotation_deg'])
    for c in GEO['cans']['parts']:
        placed[c['reference']] = place(board, c['reference'], comps[c['reference']], CV(*c['YZ_mm']),
                                       c['rotation_deg'], anchor='centre')
    # Park every other part off-board on F (shelf packing by courtyard, 0.6 mm gaps).
    key = lambda r: (''.join(ch for ch in r if ch.isalpha()), int(''.join(ch for ch in r if ch.isdigit())))
    px, py = GEO['smd_parking']['origin_native_mm']
    x, y, row_h, xmax = px, py, 0.0, px + 95
    for ref in sorted(set(comps) - set(placed), key=key):
        fp = place(board, ref, comps[ref], V(0, 0))
        l, t, r, b = (pcbnew.ToMM(v) for v in courtyard(fp))
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
    # Non-fabricated planning graphics (User.Drawings / User.Comments).
    D, C = pcbnew.Dwgs_User, pcbnew.Cmts_User
    b = GEO['brackets']
    for yc in b['Y_centres_mm']:
        rect(board, D, CV(yc - 5, b['front_foot_Z_mm'][1]), CV(yc + 5, b['outer_Z_mm'][1]), 0.1)
        text(board, D, 'BRACKET WEB on B face', CV(yc, 21.2), 0.8)
        r = b['side_nut_driver_diameter_max_mm'] / 2
        shape(board, D, pcbnew.SHAPE_T_CIRCLE, 0.1, center=CV(yc, b['side_hole_Z_mm']),
              end=CV(yc + r, b['side_hole_Z_mm']))
        text(board, C, 'F-side M3 nut + 8 mm driver keep-out', CV(yc + 10, b['side_hole_Z_mm'] + 5.6), 0.8)
    for h in GEO['headers']:
        e = GEO['envelopes_XYZ_mm'][h['reference'] + '_plug']['XYZ']
        rect(board, D, CV(e[1][0], e[2][0]), CV(e[1][1], e[2][1]), 0.1)
        text(board, D, f'{h["reference"]} IDC plug PROPOSAL envelope; ribbon exits +Z (rear)', CV(sum(e[1]) / 2, 42.8), 0.8)
        # Old usb-power J7 marking: horizontal "1 / -12V / RED" outside the box body (front side,
        # visible with the plug mated) and B silk per-pin labels (R1 step 0, tools/r1_prep.py).
        hp = {p.GetNumber(): p.GetPosition() for p in placed[h['reference']].Pads()}
        x1, y2 = pcbnew.ToMM(hp['1'].x), pcbnew.ToMM(hp['2'].y)
        text(board, pcbnew.F_SilkS, '1 / -12V / RED', V(x1 + 5.25, y2 + 4.3), 0.8,
             justify=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
        for i, lab in enumerate(['N12', 'GND', 'GND', 'GND', 'P12', 'P5', 'NC', 'NC']):
            text(board, pcbnew.B_SilkS, lab, V(x1 - 2.54 * i, y2 + 2.16), 0.8, mirror=True)
    z = GEO['depth_target']['limit_behind_panel_rear_mm'] + GEO['panel_mm'][2]
    y0, y1 = GEO['carrier_Y_mm']
    line(board, C, CV(y0, z), CV(y1, z), 0.1)
    text(board, C, f'42 mm behind panel rear (Z{z:g}) target', CV((y0 + y1) / 2, z + 0.9), 0.8)
    line(board, C, CV(y0, GEO['panel_mm'][2]), CV(y1, GEO['panel_mm'][2]), 0.1)
    text(board, C, 'panel REAR face Z1.6 (carrier front edge Z2)', CV(70, 0.6), 0.8)
    for c in GEO['cans']['parts']:
        text(board, D, 'PROVISIONAL', CV(c['YZ_mm'][0], c['YZ_mm'][1] - 4.6), 0.8)
    text(board, C, 'PARKED OFF-BOARD SMD: NOT PLACED (M1 mechanical preview)', V(px + 40, py - 3), 1.2)
    text(board, C, 'M1 PREVIEW - UNROUTED - SMD PARKED - NOT FOR FABRICATION', CV(64, 39.5), 1.2)
    save_canonical(board, CARRIER, HW / 'usb-power-45w.kicad_pro', STACKUP_4L)
    return CARRIER


def build_panel():
    board = new_board('Big Modular - usb-power-45w 4HP front panel (M1 preview)', [
        'Passive panel, NPTH only, no copper. 4HP 20.0 x 128.5 x 1.6',
        'Rail holes from modules/blank 4HP; bracket holes/USB aperture copied from usb-power',
        'Geometry: ../../docs/mechanical-geometry.json'], 'M1')
    pw, ph, _ = GEO['panel_mm']
    E = pcbnew.Edge_Cuts
    rect(board, E, PV(0, 0), PV(pw, ph))
    x, y, w, h, r = GEO['aperture_XYWHR_mm']
    line(board, E, PV(x + r, y), PV(x + w - r, y))
    line(board, E, PV(x + w, y + r), PV(x + w, y + h - r))
    line(board, E, PV(x + w - r, y + h), PV(x + r, y + h))
    line(board, E, PV(x, y + h - r), PV(x, y + r))
    k = r * (1 - 2 ** -0.5)
    for (sx, sy), (mx, my), (ex, ey) in [
            ((x, y + r), (x + k, y + k), (x + r, y)),
            ((x + w - r, y), (x + w - k, y + k), (x + w, y + r)),
            ((x + w, y + h - r), (x + w - k, y + h - k), (x + w - r, y + h)),
            ((x + r, y + h), (x + k, y + h - k), (x, y + h - r))]:
        shape(board, E, pcbnew.SHAPE_T_ARC, 0.05, start=PV(sx, sy), mid=PV(mx, my), end=PV(ex, ey))
    holes = ([('rail', *hh) for hh in GEO['rail_holes_mm']] + [('bracket', *hh) for hh in GEO['panel_bracket_holes_mm']]
             + [(l['reference'], *l['panel_XY_diameter_mm']) for l in GEO['LEDs']]
             + [('SW1', *GEO['reset_XY_diameter_mm'])])
    for i, (role, hx, hy, d) in enumerate(holes, 1):
        npth(board, f'H{i}', f'H{i}', PV(hx, hy), d, f'NPTH {role}')
    S = pcbnew.F_SilkS
    lx = 13.6
    text(board, S, 'USB', PV(10.0, 10.6), 1.6)
    text(board, S, 'POWER', PV(10.0, 13.4), 1.6)
    text(board, S, 'USB-C', PV(lx, 32.4), 1.2)
    text(board, S, 'PD 20V', PV(lx, 34.8), 1.2)
    for l in GEO['LEDs']:
        text(board, S, l['label'], PV(lx, l['panel_XY_diameter_mm'][1]), 1.2)
    text(board, S, 'RESET', PV(lx, GEO['reset_XY_diameter_mm'][1]), 1.2)
    text(board, S, 'BIG MOD', PV(10.0, 116.0), 1.0)
    D = pcbnew.Dwgs_User
    for i, note in enumerate([
            '4HP 20.0 x 128.5 x 1.6; rail holes X12.58 Y3/125.5 (blank 4HP precedent)',
            'M3 bracket holes X6.4 Y22/106.5; USB aperture/LED X6.1/SW1 X5.8 copied from usb-power',
            'LEDs D8 MAIN, D16 +12V, D17 +5V, D18 -12V (THT, hand-soldered); SW1 TL3340 SMT side reset',
            'M1 preview: not supplier-accepted, not a release']):
        text(board, D, note, PV(pw + 40, 6 + 3 * i), 0.9)
    save_canonical(board, PANEL, OLD_PANEL_PRO)
    pro = json.loads(OLD_PANEL_PRO.read_text())
    pro['meta']['filename'] = PANEL.with_suffix('.kicad_pro').name
    PANEL.with_suffix('.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n')
    return PANEL


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--panel-only', action='store_true')
    args = ap.parse_args()
    if not args.panel_only:
        print(build_carrier())
    print(build_panel())
