"""Generate the audio-out boards from docs/geometry.json and the native schematic netlist.

Run from modules/audio-out with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/build_layout.py

Writes hardware/audio-out.kicad_pcb (carrier: placed footprints with schematic nets, no
routing) and panels/front-pcb/audio-out-panel.kicad_pcb (passive 4HP panel: outline,
NPTH holes, silkscreen labels). Placement comes from the geometry contract; references,
values, fields, symbol links and pad nets come from the netlist that kicad-cli
exports from hardware/audio-out.kicad_sch (what "Update PCB from Schematic" would do).

This generator owns placement and net assignment and writes an UNROUTED carrier.
Copper comes from tools/route_plan.py through the shared `pcb plan/apply/promote`
transaction (README "Rebuild"); the accepted routed native PCB is the source of
truth (root AGENTS.md). Rerunning this script discards routing, so only do it as
the first step of that full rebuild.

3D models are vendored into hardware/_kicad_models/<sha256>/<name> and bound via
${KIPRJMOD}, the repository convention (as usb-power and midi) that `pcb promote` resolves.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
LIB = MODULE / 'hardware/AudioOut.pretty'
OX, OY = GEO['kicad_origin_mm']
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

JACK_FP = {
    'QingPu WQP-PJ366ST': 'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical',
    'QingPu WQP-PJ301M-12': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
}
POT_FP = 'Potentiometer_RV09'
POT_ORIGIN_FROM_SHAFT = (0.127, 0.508)


def pt(x, y):
    """Panel-frame mm -> KiCad internal units."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def new_board(path, title, comments, rev='F0'):
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
        out = Path(tmp) / 'audio-out.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(MODULE / 'hardware/audio-out.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        skip = ('Footprint',)
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') not in skip}
        # Multi-unit symbols list one tstamp per unit; the footprint links to the first.
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'uuid': c.findtext('tstamps').split()[0], 'fields': fields}
    nets = {n.get('name'): [(d.get('ref'), d.get('pin')) for d in n.findall('node')]
            for n in root.find('nets')}
    return comps, nets


MODEL_VARS = {'KICAD10_3DMODEL_DIR': '/usr/share/kicad/3dmodels', 'KIPRJMOD': str(MODULE / 'hardware')}


def vendor_model(token):
    """Copy a footprint's model into hardware/_kicad_models/<sha256>/ and return its ${KIPRJMOD} token."""
    path = token
    for var, val in MODEL_VARS.items():
        path = path.replace('${%s}' % var, os.environ.get(var, val))
    src = Path(path)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    dest = MODULE / 'hardware/_kicad_models' / digest / src.name
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


def place(board, ref, name, x, y, rot, comp, back=False, anchor='centre'):
    lib, fpname = comp['footprint'].split(':')
    assert (lib, fpname) == ('AudioOut', name), f'{ref}: schematic footprint {comp["footprint"]} != geometry {name}'
    fp = IO.FootprintLoad(str(LIB), name)
    fp.SetFPID(pcbnew.LIB_ID('AudioOut', name))
    fp.SetReference(ref)
    fp.SetValue(comp['value'])
    fp.SetPath(pcbnew.KIID_PATH('/' + comp['uuid']))
    fp.SetSheetname('/')
    fp.SetSheetfile('audio-out.kicad_sch')
    for key, val in comp['fields'].items():
        fp.SetField(key, val)
        fp.GetField(key).SetVisible(False)
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
    # the narrow 4HP bands leave no clean room for designators.
    fp.Reference().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
    models = fp.Models()
    for i in range(len(models)):  # element proxies are copies: write them back
        model = models[i]
        model.m_Filename = vendor_model(model.m_Filename)
        models[i] = model
    return fp


def build_carrier():
    path = MODULE / 'hardware/audio-out.kicad_pcb'
    comps, nets = schematic_netlist()
    board = new_board(path, 'Big Modular - Audio Out carrier', [
        'S3/R3: +/-12 V pure-analog stereo out, routed natively - not released, not for fabrication',
        'Front (F) faces the panel; THT jacks/pots hand-soldered; SMD on B',
        'Geometry contract: docs/geometry.json; nets: hardware/audio-out.kicad_sch',
    ], rev='R2')
    x0, y0, x1, y1 = GEO['main_pcb']['outline_mm']
    rect(board, pcbnew.Edge_Cuts, x0, y0, x1, y1)
    # Fit references (non-fabricated): panel outline and rail keep-out bands.
    pw, ph = GEO['panel_mm']
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ph)
    rect(board, pcbnew.Dwgs_User, 0, 0, pw, ry0)
    rect(board, pcbnew.Dwgs_User, 0, ry1, pw, ph)
    text(board, pcbnew.Dwgs_User, '4HP PANEL 20.0 x 128.5', pw / 2, -2.0, 1.0)
    text(board, pcbnew.Dwgs_User, 'RAIL', pw / 2, ry0 / 2 + 1.0, 1.0)
    text(board, pcbnew.Dwgs_User, 'RAIL', pw / 2, (ry1 + ph) / 2 + 1.0, 1.0)
    cx = GEO['column_X_mm']
    for j in GEO['jacks']:
        place(board, j['ref'], JACK_FP[j['part']], cx, j['Y'],
              GEO['jack_rotation_deg'], comps[j['ref']], anchor='origin')
    ox, oy = POT_ORIGIN_FROM_SHAFT
    for p in GEO['pots']:
        fp = place(board, p['ref'], POT_FP, cx + ox, p['shaft_Y'] + oy, 0, comps[p['ref']], anchor='origin')
        fp.Value().SetLayer(pcbnew.F_Fab)
    for p in GEO['back_side_parts']:
        place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], back=True)
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
            assert pad.GetNumber() == '' or pad.GetNetname(), f'{fp.GetReference()} pad {pad.GetNumber()} has no net'
    # J5 is an unshrouded 2x5 pin header, vertical with pin 1 (-12 V) at the bottom. The
    # 10-pin IDC socket envelope must stay on the board, off the J4 leads and clear of the
    # parts beside it (geometry.json power_header).
    ph = GEO['power_header']
    pin1 = next(pad for pad in fps['J5'].Pads() if pad.GetNumber() == '1').GetPosition()
    assert abs(pcbnew.ToMM(pin1.y) - OY - ph['pin1_XY_mm'][1]) < 0.01, 'J5 pin 1 is not at the bottom row'
    assert abs(pcbnew.ToMM(pin1.x) - OX - ph['pin1_XY_mm'][0]) < 0.01, 'J5 pin 1 is not in the left column'
    (bx0, bx1), (by0, by1) = ph['idc10_socket_envelope_mm']['X'], ph['idc10_socket_envelope_mm']['Y']
    rows = sorted(pcbnew.ToMM(pad.GetPosition().y) - OY for pad in fps['J5'].Pads())
    assert abs(rows[0] - 3.81 - by0) < 0.01 and abs(rows[-1] + 3.81 - by1) < 0.01, 'J5 socket envelope != pin rows'
    assert by1 <= GEO['main_pcb']['outline_mm'][3], 'J5 socket overhangs the board bottom'
    for fp in fps.values():  # the socket sits on the pin spacer: keep it off THT leads and other parts
        if fp.GetReference() == 'J5':
            continue
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            if pcbnew.ToMM(bb.GetRight()) - OX > bx0 and pcbnew.ToMM(bb.GetLeft()) - OX < bx1:
                assert pcbnew.ToMM(bb.GetBottom()) - OY + 0.5 <= by0 or pcbnew.ToMM(bb.GetTop()) - OY >= by1, \
                    f'{fp.GetReference()} pad {pad.GetNumber()} under the J5 socket'
    for s in GEO['back_silk']:
        text(board, pcbnew.B_SilkS, s['text'], *s['XY'], s['size'], mirrored=True)
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
    path = MODULE / 'panels/front-pcb/audio-out-panel.kicad_pcb'
    board = new_board(path, 'Big Modular - Audio Out 4HP front panel', [
        'F0 FIT STUDY: passive panel, NPTH only, no copper',
        'Geometry contract: ../../docs/geometry.json',
    ])
    pw, ph = GEO['panel_mm']
    rect(board, pcbnew.Edge_Cuts, 0, 0, pw, ph)
    n = 0
    for x, y, d in GEO['rail_holes_mm']:
        n += 1
        npth(board, f'H{n}', x, y, d)
    holes = GEO['panel_hole_diameters_mm']
    for p in GEO['pots']:
        n += 1
        npth(board, f'H{n}', GEO['column_X_mm'], p['shaft_Y'], holes['pot'])
    for j in GEO['jacks']:
        n += 1
        npth(board, f'H{n}', GEO['column_X_mm'], j['Y'], holes['jack'])
    for lab in GEO['panel_labels']:
        text(board, pcbnew.F_SilkS, lab['text'], *lab['XY'], lab['size'])
    save_canonical(path, board)
    return path


if __name__ == '__main__':
    print(build_carrier())
    print(build_panel())
