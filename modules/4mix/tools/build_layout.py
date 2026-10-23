"""Generate the 4MIX boards from docs/geometry.json and the native schematic netlist.

Run from modules/4mix with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/build_layout.py

Writes hardware/4mix.kicad_pcb (4-layer 18HP carrier: F signal / In1 GND plane / In2 +12V plane /
B signal + SMD; P6 THT placement with schematic nets, no routing; every SMD part parked in a grid right of the board) and
panels/front-pcb/4mix-panel.kicad_pcb (passive 18HP panel: outline, NPTH holes, silkscreen
labels). Placement comes from the geometry contract; references, values, fields, symbol
links (hierarchical sheet paths) and pad nets come from the netlist that kicad-cli exports
from hardware/4mix.kicad_sch (what "Update PCB from Schematic" would do).

This generator owns placement and net assignment and writes an UNROUTED carrier. SMD
placement and routing are later, separate steps done by hand on the board (root AGENTS.md:
manual divide and conquer); once that starts, the native PCB is the source of truth and
this script must not be rerun over it.

3D models are vendored into hardware/_kicad_models/<sha256>/<name> and bound via
${KIPRJMOD}, the repository convention that `pcb promote` resolves.
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
LIBNAME = '4MIX'
LIB = HW / f'{LIBNAME}.pretty'
OX, OY = GEO['kicad_origin_mm']
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

JACK_FP = {'QingPu WQP-PJ301M-12': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical'}


def pt(x, y):
    """Panel-frame mm -> KiCad internal units."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def new_board(path, title, comments, rev='S2'):
    board = pcbnew.NewBoard(str(path))
    tb = board.GetTitleBlock()
    tb.SetTitle(title)
    tb.SetRevision(rev)
    tb.SetCompany('Big Modular')
    for i, text in enumerate(comments):
        tb.SetComment(i, text)
    return board


def rect(board, layer, x0, y0, x1, y1, width=0.05):
    shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    shape.SetLayer(layer)
    shape.SetWidth(pcbnew.FromMM(width))
    shape.SetStart(pt(x0, y0))
    shape.SetEnd(pt(x1, y1))
    board.Add(shape)
    shape.thisown = 0


def circle(board, layer, x, y, d, width=0.1):
    shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
    shape.SetLayer(layer)
    shape.SetWidth(pcbnew.FromMM(width))
    shape.SetCenter(pt(x, y))
    shape.SetEnd(pt(x + d / 2, y))
    board.Add(shape)
    shape.thisown = 0


def text(board, layer, s, x, y, size, mirrored=False, thickness=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(thickness or max(0.15, size * 0.15)))
    t.SetMirrored(mirrored)
    t.SetPosition(pt(x, y))
    board.Add(t)
    t.thisown = 0


def pads_centre(fp):
    boxes = [pad.GetBoundingBox() for pad in fp.Pads()]
    x0 = min(b.GetLeft() for b in boxes)
    x1 = max(b.GetRight() for b in boxes)
    y0 = min(b.GetTop() for b in boxes)
    y1 = max(b.GetBottom() for b in boxes)
    return pcbnew.VECTOR2I((x0 + x1) // 2, (y0 + y1) // 2)


def schematic_netlist():
    """Native netlist of the root schematic: {ref: component} and {net: [(ref, pin)]}."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / '4mix.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / '4mix.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        skip = ('Footprint',)
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') not in skip}
        sp = c.find('sheetpath')
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'path': sp.get('tstamps') + c.findtext('tstamps').split()[0],
                               'sheetname': sp.get('names'),
                               'sheetfile': props.get('Sheetfile', '4mix.kicad_sch'), 'fields': fields}
    nets = {n.get('name'): [(d.get('ref'), d.get('pin')) for d in n.findall('node')]
            for n in root.find('nets')}
    return comps, nets


MODEL_VARS = {'KICAD10_3DMODEL_DIR': '/usr/share/kicad/3dmodels', 'KIPRJMOD': str(HW)}


def vendor_model(token):
    """Copy a footprint's model into hardware/_kicad_models/<sha256>/ and return its ${KIPRJMOD} token."""
    path = token
    for var, val in MODEL_VARS.items():
        path = path.replace('${%s}' % var, os.environ.get(var, val))
    src = Path(path)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    dest = HW / '_kicad_models' / digest / src.name
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return '${KIPRJMOD}/_kicad_models/%s/%s' % (digest, src.name)


# JLCPCB JLC04161H-7628 4-layer 1.6 mm stackup (same block as modules/32bit). pcbnew's Python
# API does not expose BOARD_STACKUP, so it goes in as text before the canonical reload.
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


def save_canonical(path, board, stackup=None):
    """Save, then reload and save once more: the reload fills native defaults (e.g. property
    font thickness) so the file equals its own native re-serialisation, which the shared
    `pcb plan/apply` worker requires."""
    pcbnew.SaveBoard(str(path), board)
    if stackup:
        text_ = path.read_text()
        assert '(stackup' not in text_ and text_.count('\t(setup\n') == 1
        path.write_text(text_.replace('\t(setup\n', '\t(setup\n' + stackup, 1))
    loaded = pcbnew.LoadBoard(str(path))
    if stackup:  # the reload drops zone fills: refill with connectivity built
        loaded.BuildConnectivity()
        pcbnew.ZONE_FILLER(loaded).Fill(loaded.Zones())
    pcbnew.SaveBoard(str(path), loaded)


def pad_uuid(ref, number, index):
    """Deterministic pad UUID: (reference, pad number, library pad order)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/4mix/pcb/pad/{ref}/{number}/{index}'))


def place(board, ref, name, x, y, rot, comp, back=False, anchor='centre'):
    lib, fpname = comp['footprint'].split(':')
    assert (lib, fpname) == (LIBNAME, name), f'{ref}: schematic footprint {comp["footprint"]} != geometry {name}'
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
    for i, pad in enumerate(fp.Pads()):
        pad.SetUuid(pcbnew.KIID(pad_uuid(ref, pad.GetNumber(), i)))
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))
    fp.SetOrientationDegrees(rot)
    if back:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if anchor == 'centre':
        c = pads_centre(fp)
        target = pt(x, y)
        fp.Move(pcbnew.VECTOR2I(target.x - c.x, target.y - c.y))
    # References live on Fab: the carrier silkscreen is hidden behind the panel.
    fp.Reference().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
    models = fp.Models()
    for i in range(len(models)):  # element proxies are copies: write them back
        model = models[i]
        model.m_Filename = vendor_model(model.m_Filename)
        models[i] = model
    return fp


def pad_xy(fp, num):
    pads = [p for p in fp.Pads() if p.GetNumber() == num]
    p = pads[0].GetPosition()
    return pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY


def courtyard_box(fp):
    """Courtyard bounding box (panel frame, line width included) on the footprint's own side."""
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    boxes = [g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == layer]
    return (min(pcbnew.ToMM(b.GetLeft()) for b in boxes) - OX, min(pcbnew.ToMM(b.GetTop()) for b in boxes) - OY,
            max(pcbnew.ToMM(b.GetRight()) for b in boxes) - OX, max(pcbnew.ToMM(b.GetBottom()) for b in boxes) - OY)


def standoff(board, ref, x, y):
    """Board-only M3 hex standoff footprint (geometry.json mount_standoffs): origin = standoff axis,
    NPTH, F courtyard = hex circumcircle (stands on F between carrier and panel), B courtyard = bolt
    head, F.Fab hex, 3D model = mechanical/standoff-m3x10.step. The panel hole is coaxial."""
    ms = GEO['mount_standoffs']
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference('')  # mechanical: no reference (shared parity convention, as usb-power H1-H4)
    fp.SetValue(f'Standoff M3x{ms["length_mm"]:g} F-F')
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetField('MechanicalID', ref)
    fp.GetField('MechanicalID').SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE)
    size = pcbnew.VECTOR2I(pcbnew.FromMM(ms['carrier_hole_d_mm']), pcbnew.FromMM(ms['carrier_hole_d_mm']))
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, size)
    pad.SetDrillSize(size)
    pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad)
    pad.thisown = 0
    mm = pcbnew.FromMM

    def add(g, layer, width):
        g.SetLayer(layer)
        g.SetWidth(mm(width))
        fp.Add(g)
        g.thisown = 0

    for layer, r in ((pcbnew.F_CrtYd, ms['F_courtyard_R_mm']), (pcbnew.B_CrtYd, ms['carrier_B_keepout_R_mm'])):
        g = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        g.SetCenter(pcbnew.VECTOR2I(0, 0))
        g.SetEnd(pcbnew.VECTOR2I(mm(r), 0))
        add(g, layer, 0.05)
    rc = ms['hex_af_mm'] / math.sqrt(3)  # circumradius, flats facing +/-X
    corners = [(rc * math.cos(math.radians(30 + 60 * k)), rc * math.sin(math.radians(30 + 60 * k))) for k in range(7)]
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        g = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        g.SetStart(pcbnew.VECTOR2I(mm(ax), mm(ay)))
        g.SetEnd(pcbnew.VECTOR2I(mm(bx), mm(by)))
        add(g, pcbnew.F_Fab, 0.1)
    label = pcbnew.PCB_TEXT(fp)
    label.SetText(ref)
    label.SetLayer(pcbnew.F_Fab)
    label.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    label.SetTextThickness(mm(0.12))
    label.SetPosition(pcbnew.VECTOR2I(0, mm(-ms['F_courtyard_R_mm'] - 0.8)))
    fp.Add(label)
    label.thisown = 0
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = vendor_model(str(MODULE / 'mechanical/standoff-m3x10.step'))
    fp.Models().push_back(model)
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))
    return fp


def big_knob_centres():
    shafts = {q['ref']: q['shaft_XY'] for q in GEO['pots']}
    return [shafts[r] for r in GEO['big_knob']['refs']]


def build_carrier():
    path = HW / '4mix.kicad_pcb'
    comps, nets = schematic_netlist()
    board = new_board(path, 'Big Modular - 4MIX carrier', [
        'S2/P6: 4-layer, THT placement + 2 M3x10 standoffs only (SMD parked off-board), UNROUTED - not released, not for fabrication',
        'Front (F) faces the panel; THT jacks/pots hand-soldered; SMD on B; J6 EXP IN (top left), J7 EXP OUT (top right), J8 power (bottom right) on B',
        'Geometry contract: docs/geometry.json; nets: hardware/4mix.kicad_sch (+ channel.kicad_sch x 4)',
    ])
    board.SetCopperLayerCount(GEO['main_pcb']['copper_layers'])
    ds = board.GetDesignSettings()
    ds.m_FillVias = False
    ds.m_CapVias = False
    x0, y0, x1, y1 = GEO['main_pcb']['outline_mm']
    rect(board, pcbnew.Edge_Cuts, x0, y0, x1, y1)
    # Fit references (non-fabricated): panel outline, rail keep-out bands, big-knob circle.
    pw, ph = GEO['panel_mm']
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ph)
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ry0)
    rect(board, pcbnew.Dwgs_User, 0, ry1, pw, ph)
    text(board, pcbnew.Dwgs_User, f'{GEO["hp"]}HP PANEL {pw} x {ph}', pw / 2, -2.0, 1.0)
    text(board, pcbnew.Dwgs_User, 'RAIL', pw / 2, ry0 / 2 + 1.0, 1.0)
    text(board, pcbnew.Dwgs_User, 'RAIL', pw / 2, (ry1 + ph) / 2 + 1.0, 1.0)
    bk = GEO['big_knob']
    for xy in big_knob_centres():
        circle(board, pcbnew.Dwgs_User, *xy, bk['reserve_D_mm'])
    text(board, pcbnew.Dwgs_User, f'VOL KNOBS <= {bk["reserve_D_mm"]:g} mm', GEO['panel_mm'][0] / 2,
         big_knob_centres()[0][1] + bk['reserve_D_mm'] / 2 + 1.0, 1.0)
    for j in GEO['jacks']:
        place(board, j['ref'], JACK_FP[j['part']], *j['XY'], GEO['jack_rotation_deg'], comps[j['ref']],
              anchor='origin')
    sx_off, sy_off = GEO['pot_shaft_offset_mm']
    for p in GEO['pots']:  # footprint origin = shaft - offset (rotation 0)
        sx, sy = p['shaft_XY']
        place(board, p['ref'], GEO['pot_footprint'], sx - sx_off, sy - sy_off, 0, comps[p['ref']], anchor='origin')
    for p in GEO['back_side_parts']:
        place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], back=True)
    ms = GEO['mount_standoffs']
    standoffs = [standoff(board, r, *xy) for r, xy in zip(ms['refs'], ms['XY_mm'])]
    # Parking grid: every part not placed yet (SMD, B side), sorted by prefix and number, packed in
    # columns right of the board (each part's own size + gap). Placed group by group later.
    placed = {fp.GetReference() for fp in board.GetFootprints()}
    placed.discard('')  # standoffs: mechanical, no reference
    park = GEO['parking']
    ox, oy = park['origin_XY']
    gap, y_max = park['gap_mm'], park['column_height_mm']
    key = lambda r: (r.rstrip('0123456789'), int(r[len(r.rstrip('0123456789')):]))  # noqa: E731
    rest = sorted((r for r in comps if r not in placed), key=key)
    cx, cy, col_w = ox, oy, 0.0
    for ref in rest:
        name = comps[ref]['footprint'].split(':')[1]
        fp = place(board, ref, name, cx, cy, 0, comps[ref], back=True)
        bb = fp.GetBoundingBox(False)
        w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
        if cy + h > oy + y_max:                      # column full: start the next one
            cx, cy = cx + col_w + gap, oy
            col_w = 0.0
        top = pcbnew.ToMM(bb.GetTop()) - OY
        left = pcbnew.ToMM(bb.GetLeft()) - OX
        fp.Move(pcbnew.VECTOR2I(pcbnew.FromMM(cx - left), pcbnew.FromMM(cy - top)))
        cy += h + gap
        col_w = max(col_w, w)
    text(board, pcbnew.Dwgs_User, 'PARKED SMD (place group by group)', ox + 20.0, oy - 4.0, 1.0)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints() if fp.GetReference()}
    assert set(fps) == set(comps), f'geometry/schematic refs differ: {set(fps) ^ set(comps)}'
    for name, members in nets.items():
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        net.thisown = 0
        for ref, pin in members:
            pads = [pad for pad in fps[ref].Pads() if pad.GetNumber() == pin]
            assert pads, f'{ref} has no pad {pin}'
            for pad in pads:
                pad.SetNet(net)
    for fp in fps.values():
        for pad in fp.Pads():
            assert pad.GetNumber() == '' or pad.GetNetname(), f'{fp.GetReference()} pad {pad.GetNumber()} has no net'
    # Pot shafts where the contract says (pin 1 left of pin 3 in the front view, pins 7.5 mm below).
    for p in GEO['pots']:
        sx, sy = p['shaft_XY']
        x1_, y1_ = pad_xy(fps[p['ref']], '1')
        x3_, _ = pad_xy(fps[p['ref']], '3')
        assert abs(x1_ - (sx - 2.5)) < 0.01 and abs(x3_ - (sx + 2.5)) < 0.01, p['ref']
        assert abs(y1_ - (sy + 7.5)) < 0.01, p['ref']
    # 1 mm edge keep-out for every placed courtyard (DRC does not check courtyards against the edge).
    placed = [fps[j['ref']] for j in GEO['jacks']] + [fps[p['ref']] for p in GEO['pots']] + \
             [fps[p['ref']] for p in GEO['back_side_parts']] + standoffs
    for fp in placed:
        a, b, c, d = courtyard_box(fp)
        margin = min(a - x0, b - y0, x1 - c, y1 - d)
        assert margin >= 1.0 - 1e-6, (fp.GetReference(), 'courtyard within 1 mm of the edge', round(margin, 3))
    # Back-silkscreen aids. J8 is vertical with pin 1 (-12 V) at the bottom so a 16-pin
    # IDC socket overhangs up over the board (geometry.json power_header).
    ph_ = GEO['power_header']
    px, py = pad_xy(fps['J8'], '1')
    assert abs(px - ph_['pin1_XY_mm'][0]) < 0.01 and abs(py - ph_['pin1_XY_mm'][1]) < 0.01, ('J8 pin 1', px, py)
    for t in GEO['back_silk']:
        text(board, pcbnew.B_SilkS, t['text'], *t['XY'], t['size'], mirrored=True)
    sx, sy = ph_['idc16_socket_envelope_mm']['X'], ph_['idc16_socket_envelope_mm']['Y']
    rect(board, pcbnew.Dwgs_User, sx[0], sy[0], sx[1], sy[1])
    text(board, pcbnew.Dwgs_User, 'IDC16', (sx[0] + sx[1]) / 2, sy[0] + 1.0, 0.8)
    plane_zones(board)
    save_canonical(path, board, STACKUP_4L)
    return path


def plane_zones(board):
    """Solid inner planes over the whole outline (pulled back by the 1 mm copper-edge rule)."""
    rules = GEO['main_pcb']['plane_rules']
    x0, y0, x1, y1 = GEO['main_pcb']['outline_mm']
    for lname, nname in GEO['main_pcb']['planes'].items():
        layer = board.GetLayerID(lname)
        board.SetLayerType(layer, pcbnew.LT_POWER)
        board.SetLayerName(layer, nname if nname == 'GND' else 'PWR')
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(board.FindNet(nname))
        zone.SetZoneName(f'{lname} {nname} plane')
        zone.SetLocalClearance(pcbnew.FromMM(rules['clearance_mm']))
        zone.SetMinThickness(pcbnew.FromMM(rules['min_width_mm']))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(pcbnew.FromMM(rules['thermal_gap_mm']))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(rules['thermal_spoke_mm']))
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            v = pt(x, y)
            outline.Append(v.x, v.y)
        board.Add(zone)


def npth(board, mech_id, x, y, d):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(mech_id)
    fp.SetValue('MECHANICAL_NPTH')
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
    fp.SetField('MechanicalID', mech_id)
    fp.GetField('MechanicalID').SetVisible(False)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE)
    size = pcbnew.VECTOR2I(pcbnew.FromMM(d), pcbnew.FromMM(d))
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, size)
    pad.SetDrillSize(size)
    pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad)
    pad.thisown = 0
    yard = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    yard.SetLayer(pcbnew.F_CrtYd)
    yard.SetWidth(pcbnew.FromMM(0.05))
    yard.SetCenter(pcbnew.VECTOR2I(0, 0))
    yard.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(d / 2 + 0.25), 0))
    fp.Add(yard)
    yard.thisown = 0
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))


def build_panel():
    path = MODULE / 'panels/front-pcb/4mix-panel.kicad_pcb'
    board = new_board(path, 'Big Modular - 4MIX 18HP front panel', [
        'S2 FIT STUDY: passive panel, NPTH only, no copper',
        'Geometry contract: ../../docs/geometry.json',
    ])
    pw, ph = GEO['panel_mm']
    rect(board, pcbnew.Edge_Cuts, 0, 0, pw, ph)
    holes = GEO['panel_hole_diameters_mm']
    spots = [(x, y, d) for x, y, d in GEO['rail_holes_mm']]
    spots += [(*j['XY'], holes['jack']) for j in GEO['jacks']]
    spots += [(*p['shaft_XY'], holes['pot']) for p in GEO['pots']]
    ms = GEO['mount_standoffs']
    bolts = ms['XY_mm']  # coaxial with the carrier holes (10 mm standoff = carrier F to panel rear)
    assert ms['length_mm'] == GEO['stack_Z_mm']['panel_rear_seat']
    spots += [(x, y, ms['panel_hole_d_mm']) for x, y in bolts]
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    for x, y in bolts:  # bolt head inside the rail gap
        assert ry0 < y - ms['panel_bolt_head_R_mm'] and y + ms['panel_bolt_head_R_mm'] < ry1, ('standoff bolt in rail band', x, y)
    for n, (x, y, d) in enumerate(spots, 1):
        npth(board, f'H{n}', x, y, d)
    for lab in GEO['panel_labels']:
        text(board, pcbnew.F_SilkS, lab['text'], *lab['XY'], lab['size'])
    bk = GEO['big_knob']
    rk = bk['reserve_D_mm'] / 2
    centres = big_knob_centres()
    for xy in centres:
        circle(board, pcbnew.Dwgs_User, *xy, bk['reserve_D_mm'])
    # Nothing on the panel inside a big-knob circle: no label box, no jack nut, no small knob, no
    # standoff bolt head, no other big knob.
    boxes = [(t.GetText(), t.GetBoundingBox()) for t in board.GetDrawings()
             if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS]
    others = [(j['ref'], j['XY'], bk['jack_nut_R_mm']) for j in GEO['jacks']]
    others += [(q['ref'], q['shaft_XY'], bk['small_knob_R_mm']) for q in GEO['pots'] if q['ref'] not in bk['refs']]
    others += [(r, xy, ms['panel_bolt_head_R_mm']) for r, xy in zip(ms['refs'], bolts)]
    for n, (cx, cy) in enumerate(centres):
        for s, bb in boxes:  # closest point of the label box to the knob centre
            nx = min(max(OX + cx, pcbnew.ToMM(bb.GetLeft())), pcbnew.ToMM(bb.GetRight())) - OX
            ny = min(max(OY + cy, pcbnew.ToMM(bb.GetTop())), pcbnew.ToMM(bb.GetBottom())) - OY
            assert math.hypot(nx - cx, ny - cy) > rk + 0.5, ('label under a big knob', s, bk['refs'][n])
        for ref, (x, y), rr in others:
            clear = math.hypot(x - cx, y - cy) - rr - rk
            assert clear > 0, ('big knob overlaps', bk['refs'][n], ref, round(clear, 2))
        for ox, oy in centres[n + 1:]:
            assert math.hypot(ox - cx, oy - cy) > 2 * rk + 1.0, ('big knobs overlap', bk['refs'][n])
    save_canonical(path, board)
    return path


if __name__ == '__main__':
    print(build_carrier())
    print(build_panel())
