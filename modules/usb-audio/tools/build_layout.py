"""Generate the USB-AUDIO boards from docs/geometry.json and the native schematic netlists.

Run from modules/usb-audio with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/build_layout.py

Writes (S1 placement, UNROUTED, not for fabrication):
- hardware/usb-audio.kicad_pcb       carrier, 4 layers: jacks, pots, power header, the two MCU-board
                                     header strips J6/J7, SWD J8 and BOOT/RESET placed; every other
                                     SMD part parked in a grid right of the board (B side)
- hardware/usb-audio-mcu.kicad_pcb   MCU board, 4 layers: USB-C J101 and the header holes J102/J103
                                     placed (same XY as J6/J7), the rest parked; U101 zone reserved
- panels/front-pcb/usb-audio-panel.kicad_pcb  passive 6HP FR4 panel: NPTH holes, USB-C slot, labels

Placement comes from the geometry contract; references, values, fields, symbol links and pad nets
come from the netlists kicad-cli exports from the schematics (what "Update PCB from Schematic"
would do). Once SMD placement starts by hand on a board, that board owns placement: do not rerun
this script over hand work.

3D models are vendored into hardware/_kicad_models/<sha256>/<name> and bound via ${KIPRJMOD}.
"""
import hashlib
import json
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
LIBNAME = 'USBAUDIO'
LIB = HW / f'{LIBNAME}.pretty'
OX, OY = GEO['kicad_origin_mm']
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

JACK_FP = {'QingPu WQP-PJ301M-12': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical'}


def pt(x, y):
    """Panel-frame mm -> KiCad internal units."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def new_board(path, title, comments, rev='S1'):
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


def schematic_netlist(project):
    """Native netlist of a root schematic: {ref: component} and {net: [(ref, pin)]}."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / f'{project}.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        skip = ('Footprint',)
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') not in skip}
        props = {pp.get('name') for pp in c.findall('property')}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'uuid': c.findtext('tstamps').split()[0], 'fields': fields,
                               'not_in_bom': 'exclude_from_bom' in props}
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


def save_canonical(path, board):
    """Save, then reload and save once more: the reload fills native defaults (e.g. property
    font thickness) so the file equals its own native re-serialisation, which the shared
    `pcb plan/apply` worker requires."""
    pcbnew.SaveBoard(str(path), board)
    pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))


def pad_uuid(project, ref, number, index):
    """Deterministic pad UUID: (project, reference, pad number, library pad order)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/usb-audio/{project}/pcb/pad/{ref}/{number}/{index}'))


def place(board, ref, name, x, y, rot, comp, back=False, anchor='centre', model_z=None, project='usb-audio'):
    lib, fpname = comp['footprint'].split(':')
    assert (lib, fpname) == (LIBNAME, name), f'{ref}: schematic footprint {comp["footprint"]} != geometry {name}'
    fp = IO.FootprintLoad(str(LIB), name)
    fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
    fp.SetReference(ref)
    fp.SetValue(comp['value'])
    fp.SetPath(pcbnew.KIID_PATH('/' + comp['uuid']))
    fp.SetSheetname('/')
    fp.SetSheetfile(f'{project}.kicad_sch')
    if comp.get('not_in_bom'):
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    for key, val in comp['fields'].items():
        fp.SetField(key, val)
        fp.GetField(key).SetVisible(False)
    # Stable pad UUIDs (library pad UUIDs are not kept): a later route plan names duplicated
    # pad numbers (switch pads, USB shield) by UUID, as the shared `pcb apply` requires.
    for i, pad in enumerate(fp.Pads()):
        pad.SetUuid(pcbnew.KIID(pad_uuid(project, ref, pad.GetNumber(), i)))
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
    # References live on Fab: the carrier silkscreen is hidden behind the panel and
    # the dense bands leave no clean room for designators.
    fp.Reference().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
    models = fp.Models()
    for i in range(len(models)):  # element proxies are copies: write them back
        model = models[i]
        model.m_Filename = vendor_model(model.m_Filename)
        if model_z is not None:
            model.m_Offset = pcbnew.VECTOR3D(0, 0, model_z)
        models[i] = model
    return fp


def pad_xy(fp, num):
    pads = [p for p in fp.Pads() if p.GetNumber() == num]
    p = pads[0].GetPosition()
    return pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY


def npth(board, mech_id, x, y, d, slot=None):
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
    w, h = slot or (d, d)
    pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_OVAL if slot else pcbnew.PAD_SHAPE_CIRCLE)
    size = pcbnew.VECTOR2I(pcbnew.FromMM(w), pcbnew.FromMM(h))
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, size)
    if slot:
        pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_OBLONG)
    pad.SetDrillSize(size)
    pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad)
    pad.thisown = 0
    if slot:
        yard = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
        yard.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(-w / 2 - 0.25), pcbnew.FromMM(-h / 2 - 0.25)))
        yard.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(w / 2 + 0.25), pcbnew.FromMM(h / 2 + 0.25)))
    else:
        yard = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        yard.SetCenter(pcbnew.VECTOR2I(0, 0))
        yard.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(d / 2 + 0.25), 0))
    yard.SetLayer(pcbnew.F_CrtYd)
    yard.SetWidth(pcbnew.FromMM(0.05))
    fp.Add(yard)
    yard.thisown = 0
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))




def outline(board, box):
    x0, y0, x1, y1 = box
    rect(board, pcbnew.Edge_Cuts, x0, y0, x1, y1)


def setup(board, layers):
    board.SetCopperLayerCount(layers)
    ds = board.GetDesignSettings()
    ds.m_FillVias = False
    ds.m_CapVias = False


def fit_refs(board):
    """Non-fabricated fit references on Dwgs.User: panel outline and rail keep-out bands."""
    pw, ph = GEO['panel_mm']
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ph)
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ry0)
    rect(board, pcbnew.Dwgs_User, 0, ry1, pw, ph)
    text(board, pcbnew.Dwgs_User, '6HP PANEL 30.0 x 128.5', pw / 2, -2.0, 1.0)


def park(board, comps, placed, project, origin=None):
    """Every part not placed yet (SMD, B side on the carrier / F side on the MCU board) in columns
    right of the board, sorted by prefix and number, for group-by-group placement."""
    p = GEO['parking']
    ox, oy = origin or p['origin_XY']
    gap, y_max = p['gap_mm'], p['column_height_mm']
    key = lambda r: (r.rstrip('0123456789'), int(r[len(r.rstrip('0123456789')):]))  # noqa: E731
    rest = sorted((r for r in comps if r not in placed), key=key)
    cx, cy, col_w = ox, oy, 0.0
    back = project == 'usb-audio'
    for ref in rest:
        name = comps[ref]['footprint'].split(':')[1]
        fp = place(board, ref, name, cx, cy, 0, comps[ref], back=back, project=project)
        bb = fp.GetBoundingBox(False)
        w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
        if cy + h > oy + y_max:
            cx, cy = cx + col_w + gap, oy
            col_w = 0.0
        top = pcbnew.ToMM(bb.GetTop()) - OY
        left = pcbnew.ToMM(bb.GetLeft()) - OX
        fp.Move(pcbnew.VECTOR2I(pcbnew.FromMM(cx - left), pcbnew.FromMM(cy - top)))
        cy += h + gap
        col_w = max(col_w, w)
    text(board, pcbnew.Dwgs_User, 'PARKED SMD (place group by group)', ox + 12.0, oy - 4.0, 1.0)


def assign_nets(board, comps, nets, spare=()):
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
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
            ok = pad.GetNumber() == '' or pad.GetNetname() or (fp.GetReference(), pad.GetNumber()) in spare
            assert ok, f'{fp.GetReference()} pad {pad.GetNumber()} has no net'
    return fps


def header(board, ref, spec, comp, project):
    """1x10 strip: pin 1 at pin1_XY, pins running down (+Y)."""
    x, y = spec['pin1_XY']
    fp = place(board, ref, spec['footprint'], x, y, 0, comp, anchor='origin', project=project)
    px, py = pad_xy(fp, '1')
    assert abs(px - x) < 0.01 and abs(py - y) < 0.01, ref
    return fp


def build_carrier():
    path = HW / 'usb-audio.kicad_pcb'
    comps, nets = schematic_netlist('usb-audio')
    board = new_board(path, 'Big Modular - USB-AUDIO carrier (jack/pot board)', [
        'S1: THT placement only (SMD parked off-board), UNROUTED - not released, not for fabrication',
        'Front (F) faces the panel; jacks/pots/headers hand-soldered; SMD on B; 4 layers',
        'MCU board (usb-audio-mcu) sits on J6/J7 over the top band; geometry: docs/geometry.json',
    ])
    setup(board, GEO['main_pcb']['copper_layers'])
    outline(board, GEO['main_pcb']['outline_mm'])
    fit_refs(board)
    for j in GEO['jacks']:
        place(board, j['ref'], JACK_FP[j['part']], *j['XY'], GEO['jack_rotation_deg'], comps[j['ref']],
              anchor='origin')
    sx_off, sy_off = GEO['pot_shaft_offset_mm']
    for p in GEO['pots']:
        sx, sy = p['shaft_XY']
        place(board, p['ref'], GEO['pot_footprint'], sx - sx_off, sy - sy_off, 0, comps[p['ref']], anchor='origin')
    for h in GEO['carrier_headers']:
        header(board, h['ref'], h, comps[h['ref']], 'usb-audio')
    for p in GEO['back_side_parts']:
        anchor = 'origin' if p['ref'] == 'J8' else 'centre'
        place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], back=True, anchor=anchor)
    m = GEO['mcu_pcb']['outline_mm']
    rect(board, pcbnew.Dwgs_User, *m)
    text(board, pcbnew.Dwgs_User, 'MCU BOARD (F side, Z 2.5-4.1)', 15.0, 36.0, 0.8)
    placed = {fp.GetReference() for fp in board.GetFootprints()}
    park(board, comps, placed, 'usb-audio')
    fps = assign_nets(board, comps, nets)
    for p in GEO['pots']:
        sx, sy = p['shaft_XY']
        x1_, y1_ = pad_xy(fps[p['ref']], '1')
        x3_, _ = pad_xy(fps[p['ref']], '3')
        assert abs(x1_ - (sx - 2.5)) < 0.01 and abs(x3_ - (sx + 2.5)) < 0.01, p['ref']
        assert abs(y1_ - (sy + 7.5)) < 0.01, p['ref']
    ph = GEO['power_header']
    pin1 = next(pad for pad in fps['J1'].Pads() if pad.GetNumber() == '1').GetPosition()
    assert abs(pcbnew.ToMM(pin1.x) - OX - ph['pin1_XY_mm'][0]) < 0.01, 'J1 pin 1 column'
    assert abs(pcbnew.ToMM(pin1.y) - OY - ph['pin1_XY_mm'][1]) < 0.01, 'J1 pin 1 is not at the bottom row'
    text(board, pcbnew.B_SilkS, '-12V', ph['column_X_mm'][1] + 3.8, ph['pin1_XY_mm'][1] - 1.1, 0.8, mirrored=True)
    sx, sy = ph['idc16_socket_envelope_mm']['X'], ph['idc16_socket_envelope_mm']['Y']
    rect(board, pcbnew.Dwgs_User, sx[0], sy[0], sx[1], sy[1])
    text(board, pcbnew.Dwgs_User, 'IDC16', (sx[0] + sx[1]) / 2, sy[0] + 1.0, 0.8)
    for ref, label in (('SW1', 'RESET'), ('SW2', 'BOOT')):
        x, y = next(p['XY'] for p in GEO['back_side_parts'] if p['ref'] == ref)
        text(board, pcbnew.B_SilkS, label, x, y + (-2.6 if ref == 'SW1' else 2.6), 0.8, mirrored=True)
    x, y = next(p['XY'] for p in GEO['back_side_parts'] if p['ref'] == 'J8')
    text(board, pcbnew.B_SilkS, 'SWD', x, y - 2.4, 0.8, mirrored=True)
    save_canonical(path, board)
    return path


def build_mcu():
    path = HW / 'usb-audio-mcu.kicad_pcb'
    comps, nets = schematic_netlist('usb-audio-mcu')
    board = new_board(path, 'Big Modular - USB-AUDIO MCU board', [
        'S1: USB-C and header holes placed, other SMD parked, UNROUTED - not for fabrication',
        'All SMD on F (faces the panel); sits on the carrier J6/J7 strips; 4 layers',
        'Geometry contract: docs/geometry.json (same frame as the carrier)',
    ])
    setup(board, GEO['mcu_pcb']['copper_layers'])
    outline(board, GEO['mcu_pcb']['outline_mm'])
    fit_refs(board)
    for p in GEO['mcu_parts']:
        if 'pin1_XY' in p:
            header(board, p['ref'], p, comps[p['ref']], 'usb-audio-mcu')
        else:
            place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], project='usb-audio-mcu')
    for z in GEO['reserved_zones_mcu']:
        rect(board, pcbnew.Dwgs_User, z['X'][0], z['Y'][0], z['X'][1], z['Y'][1])
        text(board, pcbnew.Dwgs_User, 'U101 LQFP-64', sum(z['X']) / 2, sum(z['Y']) / 2, 1.0)
    placed = {fp.GetReference() for fp in board.GetFootprints()}
    park(board, comps, placed, 'usb-audio-mcu')
    assign_nets(board, comps, nets, spare={('J101', 'A8'), ('J101', 'B8')})
    save_canonical(path, board)
    return path


def build_panel():
    path = MODULE / 'panels/front-pcb/usb-audio-panel.kicad_pcb'
    board = new_board(path, 'Big Modular - USB-AUDIO 6HP front panel', [
        'S1 FIT STUDY: passive panel, NPTH only (holes + USB-C slot), no copper',
        'Geometry contract: ../../docs/geometry.json',
    ])
    pw, ph = GEO['panel_mm']
    rect(board, pcbnew.Edge_Cuts, 0, 0, pw, ph)
    holes = GEO['panel_hole_diameters_mm']
    spots = [(x, y, d) for x, y, d in GEO['rail_holes_mm']]
    spots += [(*j['XY'], holes['jack']) for j in GEO['jacks']]
    spots += [(*p['shaft_XY'], holes['pot']) for p in GEO['pots']]
    n = 0
    for n, (x, y, d) in enumerate(spots, 1):
        npth(board, f'H{n}', x, y, d)
    slot = GEO['usb_slot']
    npth(board, f'H{n + 1}', *slot['XY'], min(slot['size_mm']), slot=slot['size_mm'])
    for lab in GEO['panel_labels']:
        text(board, pcbnew.F_SilkS, lab['text'], *lab['XY'], lab['size'])
    save_canonical(path, board)
    return path


if __name__ == '__main__':
    print(build_carrier())
    print(build_mcu())
    print(build_panel())
