"""Generate the 16bit boards from docs/geometry.json and the native schematic netlist.

Run from modules/16bit with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/build_layout.py

Writes hardware/16bit.kicad_pcb (4-layer carrier: placed footprints with schematic nets,
no routing) and panels/front-pcb/16bit-panel.kicad_pcb (passive 6HP panel: outline, NPTH
holes, silkscreen labels). Placement comes from the geometry contract; references,
values, fields, symbol links and pad nets come from the netlist that kicad-cli
exports from hardware/16bit.kicad_sch (what "Update PCB from Schematic" would do).

This generator owns placement and net assignment and writes an UNROUTED carrier.
Routing is a later, separate step (as modules/8bit: explicit copper through the shared
`pcb plan/apply/promote` flow; the accepted routed native PCB then becomes the source
of truth and this script must not be rerun over it).

3D models are vendored into hardware/_kicad_models/<sha256>/<name> and bound via
${KIPRJMOD}, the repository convention that `pcb promote` resolves.
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
LIBNAME = '16BIT'
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


def schematic_netlist():
    """Native netlist of the root schematic: {ref: component} and {net: [(ref, pin)]}."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / '16bit.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / '16bit.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        skip = ('Footprint',)
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') not in skip}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'uuid': c.findtext('tstamps').split()[0], 'fields': fields}
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


def pad_uuid(ref, number, index):
    """Deterministic pad UUID: (reference, pad number, library pad order)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/16bit/pcb/pad/{ref}/{number}/{index}'))


def place(board, ref, name, x, y, rot, comp, back=False, anchor='centre', model_z=None):
    lib, fpname = comp['footprint'].split(':')
    assert (lib, fpname) == (LIBNAME, name), f'{ref}: schematic footprint {comp["footprint"]} != geometry {name}'
    fp = IO.FootprintLoad(str(LIB), name)
    fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
    fp.SetReference(ref)
    fp.SetValue(comp['value'])
    fp.SetPath(pcbnew.KIID_PATH('/' + comp['uuid']))
    fp.SetSheetname('/')
    fp.SetSheetfile('16bit.kicad_sch')
    for key, val in comp['fields'].items():
        fp.SetField(key, val)
        fp.GetField(key).SetVisible(False)
    # Stable pad UUIDs (library pad UUIDs are not kept): a later route plan names duplicated
    # pad numbers (switch pads, USB shield) by UUID, as the shared `pcb apply` requires.
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


def build_carrier():
    path = HW / '16bit.kicad_pcb'
    comps, nets = schematic_netlist()
    board = new_board(path, 'Big Modular - 16bit carrier', [
        'S3: placement only, UNROUTED - not released, not for fabrication',
        'Front (F) faces the panel; THT jacks/pots/LED/SW1 hand-soldered; SMD on B; 4 layers',
        'Geometry contract: docs/geometry.json; nets: hardware/16bit.kicad_sch',
    ])
    board.SetCopperLayerCount(GEO['main_pcb']['copper_layers'])
    # R1 leaves 123 vias in SMD pads (+ U1's EP thermal vias): the fab must resin-fill and
    # copper-cap them (IPC-4761 type VII, "POFV"); vias stay tented. docs/research.md section 7.2.
    ds = board.GetDesignSettings()
    ds.m_FillVias = True
    ds.m_CapVias = True
    x0, y0, x1, y1 = GEO['main_pcb']['outline_mm']
    rect(board, pcbnew.Edge_Cuts, x0, y0, x1, y1)
    # Fit references (non-fabricated): panel outline and rail keep-out bands.
    pw, ph = GEO['panel_mm']
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ph)
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ry0)
    rect(board, pcbnew.Dwgs_User, 0, ry1, pw, ph)
    text(board, pcbnew.Dwgs_User, '6HP PANEL 30.0 x 128.5', pw / 2, -2.0, 1.0)
    text(board, pcbnew.Dwgs_User, 'RAIL', pw / 2, ry0 / 2 + 1.0, 1.0)
    text(board, pcbnew.Dwgs_User, 'RAIL', pw / 2, (ry1 + ph) / 2 + 1.0, 1.0)
    for j in GEO['jacks']:
        place(board, j['ref'], JACK_FP[j['part']], *j['XY'], GEO['jack_rotation_deg'], comps[j['ref']],
              anchor='origin')
    sx_off, sy_off = GEO['pot_shaft_offset_mm']
    for p in GEO['pots']:  # footprint origin = shaft - offset (rotation 0)
        sx, sy = p['shaft_XY']
        place(board, p['ref'], GEO['pot_footprint'], sx - sx_off, sy - sy_off, 0, comps[p['ref']], anchor='origin')
    sw = GEO['button']
    assert sw['side'] == 'F'
    place(board, sw['ref'], sw['footprint'], *sw['XY'], sw.get('rot', 0), comps[sw['ref']])
    stack = GEO['stack_Z_mm']
    lz = stack['led_body_bottom'] - stack['led_model_body_bottom']
    for d in GEO['leds']:
        place(board, d['ref'], d['footprint'], *d['XY'], d.get('rot', 0), comps[d['ref']], model_z=lz)
    for p in GEO['back_side_parts']:
        place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], back=True,
              anchor='origin' if p['ref'] == 'J7' else 'centre')
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
    # Every numbered pad gets a net, except the USB-C SBU pads (A8/B8: not in the USB 2.0 symbol).
    for fp in fps.values():
        for pad in fp.Pads():
            spare = fp.GetReference() == 'J7' and pad.GetNumber() in ('A8', 'B8')
            assert pad.GetNumber() == '' or pad.GetNetname() or spare, \
                f'{fp.GetReference()} pad {pad.GetNumber()} has no net'
    # USB-C opening (footprint +Y, away from the A/B signal pads) toward the top board edge,
    # front face 0.35 mm inside it (front silk stays on the board): plug from above, behind the panel.
    j7 = next(p for p in GEO['back_side_parts'] if p['ref'] == 'J7')
    _, jy = pad_xy(fps['J7'], 'A1')
    assert jy > j7['XY'][1] + 3.0, 'J7 opening does not face the top edge'
    assert 0 < j7['XY'][1] - 3.65 - GEO['main_pcb']['outline_mm'][1] <= 0.5, 'J7 front not at the top edge'
    # Pot shafts on their columns (pin 1 left of pin 3 in the front view, pins 7.5 mm below).
    for p in GEO['pots']:
        sx, sy = p['shaft_XY']
        x1_, y1_ = pad_xy(fps[p['ref']], '1')
        x3_, _ = pad_xy(fps[p['ref']], '3')
        assert abs(x1_ - (sx - 2.5)) < 0.01 and abs(x3_ - (sx + 2.5)) < 0.01, p['ref']
        assert abs(y1_ - (sy + 7.5)) < 0.01, p['ref']
    # Back-silkscreen aids. J6 is vertical with pin 1 (-12 V) at the bottom so a 16-pin
    # IDC socket overhangs up over the board (geometry.json power_header).
    ph = GEO['power_header']
    pin1 = next(pad for pad in fps['J6'].Pads() if pad.GetNumber() == '1').GetPosition()
    assert abs(pcbnew.ToMM(pin1.x) - OX - ph['pin1_XY_mm'][0]) < 0.01, 'J6 pin 1 column'
    assert abs(pcbnew.ToMM(pin1.y) - OY - ph['pin1_XY_mm'][1]) < 0.01, 'J6 pin 1 is not at the bottom row'
    text(board, pcbnew.B_SilkS, '-12V', ph['column_X_mm'][1] + 3.8, ph['pin1_XY_mm'][1] - 1.1, 0.8, mirrored=True)
    sx, sy = ph['idc16_socket_envelope_mm']['X'], ph['idc16_socket_envelope_mm']['Y']
    rect(board, pcbnew.Dwgs_User, sx[0], sy[0], sx[1], sy[1])
    text(board, pcbnew.Dwgs_User, 'IDC16', (sx[0] + sx[1]) / 2, sy[0] + 1.0, 0.8)
    # JP1 MIDI RX source (shipped open): P = protected (bridge 1-2), D = direct (bridge 2-3).
    jp1 = {n: pad_xy(fps['JP1'], n) for n in '123'}
    assert jp1['1'][1] < jp1['2'][1] < jp1['3'][1] or jp1['1'][1] > jp1['2'][1] > jp1['3'][1], 'JP1 not vertical'
    text(board, pcbnew.B_SilkS, 'P', 1.3, jp1['1'][1], 0.8, mirrored=True)
    text(board, pcbnew.B_SilkS, 'D', 1.3, jp1['3'][1], 0.8, mirrored=True)
    save_canonical(path, board)
    return path


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
    path = MODULE / 'panels/front-pcb/16bit-panel.kicad_pcb'
    board = new_board(path, 'Big Modular - 16bit 6HP front panel', [
        'S1 FIT STUDY: passive panel, NPTH only, no copper',
        'Geometry contract: ../../docs/geometry.json',
    ])
    pw, ph = GEO['panel_mm']
    rect(board, pcbnew.Edge_Cuts, 0, 0, pw, ph)
    holes = GEO['panel_hole_diameters_mm']
    spots = [(x, y, d) for x, y, d in GEO['rail_holes_mm']]
    spots += [(*j['XY'], holes['jack']) for j in GEO['jacks']]
    spots += [(*p['shaft_XY'], holes['pot']) for p in GEO['pots']]
    spots += [(*GEO['button']['XY'], holes['button'])]
    spots += [(*d['XY'], holes['led']) for d in GEO['leds']]
    for n, (x, y, d) in enumerate(spots, 1):
        npth(board, f'H{n}', x, y, d)
    for lab in GEO['panel_labels']:
        text(board, pcbnew.F_SilkS, lab['text'], *lab['XY'], lab['size'])
    save_canonical(path, board)
    return path


if __name__ == '__main__':
    print(build_carrier())
    print(build_panel())
