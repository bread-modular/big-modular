"""Generate the 32bit S4 MCU board and panel from docs/geometry.json and the native netlists.

Forked from modules/usb-audio. Run from modules/32bit with KiCad's Python (pcbnew 10), after
tools/build_schematic.py, naming the boards to (re)build: a board placed and routed by hand must not be
rebuilt.
  python3 -B tools/build_layout.py mcu panel

Writes:
- hardware/32bit-mcu.kicad_pcb   MCU board, 4 layers: USB-C J101 and the header holes J102/J103 placed
                                 (same XY as the carrier J6/J7), the rest parked right of the board (F side)
- panels/front-pcb/32bit-panel.kicad_pcb  passive 6HP FR4 panel: NPTH holes, USB-C slot, labels

The carrier is not built here: it is the routed modules/usb-audio S5 / R5 carrier, converted once by
tools/carrier_from_usb_audio.py and then edited by hand. References, values, fields, symbol links and pad
nets come from the netlists kicad-cli exports from the schematics (what "Update PCB from Schematic" would
do). 3D models are vendored into hardware/_kicad_models/<sha256>/<name> and bound via ${KIPRJMOD}.
"""
import hashlib
import json
import math
import os
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
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
LIBNAME = '32BIT'
LIB = HW / f'{LIBNAME}.pretty'
OX, OY = GEO['kicad_origin_mm']
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

FP_CACHE = {}  # name -> library footprint, loaded before a board (the IO plugin breaks after LoadBoard)
JACK_FP = {'QingPu WQP-PJ301M-12': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical'}


def pt(x, y):
    """Panel-frame mm -> KiCad internal units."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def new_board(path, title, comments, rev='S1', reuse=False):
    """reuse: keep the existing board file's setup (stackup, design settings) and empty it."""
    if reuse:
        # Empty the file as text (setup, stackup and layers stay), then load it.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from sexp import parse, dump
        tree = parse(Path(path).read_text())
        drop = {'footprint', 'segment', 'arc', 'via', 'zone', 'gr_line', 'gr_rect', 'gr_text', 'gr_circle', 'gr_poly',
                'gr_arc', 'net', 'group', 'dimension', 'title_block', 'generated'}
        tree = [n for n in tree if not (isinstance(n, list) and str(n[0]) in drop)]
        Path(path).write_text(dump(tree) + '\n')
        board = pcbnew.LoadBoard(str(path))
    else:
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


def dedup_uuids(path):
    """Footprints copied from FP_CACHE keep the library item UUIDs: give every repeated UUID after
    its first occurrence a deterministic new one (uuid5 of the old one and its occurrence)."""
    import re
    text = Path(path).read_text()
    seen = {}

    def sub(m):
        u = m.group(1)
        seen[u] = seen.get(u, 0) + 1
        if seen[u] == 1:
            return m.group(0)
        return '(uuid "%s")' % uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/32bit/dedup/{u}/{seen[u]}')
    Path(path).write_text(re.sub(r'\(uuid "([0-9a-f-]+)"\)', sub, text))


def save_canonical(path, board):
    """Save, then reload and save once more: the reload fills native defaults (e.g. property
    font thickness) so the file equals its own native re-serialisation, which the shared
    `pcb plan/apply` worker requires."""
    pcbnew.SaveBoard(str(path), board)
    dedup_uuids(path)
    pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))


def pad_uuid(project, ref, number, index):
    """Deterministic pad UUID: (project, reference, pad number, library pad order)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/32bit/{project}/pcb/pad/{ref}/{number}/{index}'))


def place(board, ref, name, x, y, rot, comp, back=False, anchor='centre', model_z=None, project='32bit'):
    lib, fpname = comp['footprint'].split(':')
    assert (lib, fpname) == (LIBNAME, name), f'{ref}: schematic footprint {comp["footprint"]} != geometry {name}'
    fp = pcbnew.FOOTPRINT(FP_CACHE[name]) if name in FP_CACHE else pcbnew.FootprintLoad(str(LIB), name)
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




def standoff(board, ref, x, y):
    """Board-only M3 hex standoff footprint (geometry.json mount_standoffs, as modules/4mix): origin =
    standoff axis, NPTH, F courtyard = hex circumcircle (stands on F between carrier and panel),
    B courtyard = bolt head keep-out, F.Fab hex, 3D model = modules/4mix standoff-m3x10.step."""
    ms = GEO['mount_standoffs']
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference('')  # mechanical: no reference (shared parity convention)
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
    model.m_Filename = vendor_model(str(MODULE.parent / '4mix/mechanical/standoff-m3x10.step'))
    fp.Models().push_back(model)
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))
    return fp


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
    back = project == '32bit'
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


def build_mcu():
    global OX, OY
    OX, OY = GEO.get('mcu_kicad_origin_mm', GEO['kicad_origin_mm'])   # P2: the unchanged file sits 8 mm lower
    path = HW / '32bit-mcu.kicad_pcb'
    comps, nets = schematic_netlist('32bit-mcu')
    # reuse=True keeps the setup of the file in place: the first build copies it from the usb-audio MCU board
    # (JLC04161H-7628 stackup, USB_HS rules, saved fills setting)
    board = new_board(path, 'Big Modular - 32BIT MCU board (ESP32-S3)', [
        'S1: USB-C and header holes placed, other SMD parked, UNROUTED - not for fabrication',
        'All SMD on F (faces the panel); sits on the carrier J6/J7 strips; 4 layers',
        'Geometry contract: docs/geometry.json (same frame as the carrier)',
    ], reuse=True)
    setup(board, GEO['mcu_pcb']['copper_layers'])
    outline(board, GEO['mcu_pcb']['outline_mm'])
    fit_refs(board)
    for p in GEO['mcu_parts']:
        if 'pin1_XY' in p:
            header(board, p['ref'], p, comps[p['ref']], '32bit-mcu')
        else:
            place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], project='32bit-mcu')
    placed = {fp.GetReference() for fp in board.GetFootprints()}
    park(board, comps, placed, '32bit-mcu')
    assign_nets(board, comps, nets, spare={('J101', 'A8'), ('J101', 'B8')})
    save_canonical(path, board)
    dedup_uuids(path)
    return path


def build_panel():
    path = MODULE / 'panels/front-pcb/32bit-panel.kicad_pcb'
    board = new_board(path, 'Big Modular - 32BIT 6HP front panel', [
        'S4 / P1: passive panel, NPTH only (holes, USB-C slot, 2 standoff bolt holes), no copper',
        'Geometry contract: ../../docs/geometry.json',
    ])
    pw, ph = GEO['panel_mm']
    rect(board, pcbnew.Edge_Cuts, 0, 0, pw, ph)
    holes = GEO['panel_hole_diameters_mm']
    spots = [(x, y, d) for x, y, d in GEO['rail_holes_mm']]
    spots += [(*j['XY'], holes['jack']) for j in GEO['jacks']]
    spots += [(*p['shaft_XY'], holes['pot']) for p in GEO['pots']]
    spots += [(*d['XY'], holes['led']) for d in GEO['leds']]
    spots.append((*GEO['button']['XY'], holes['button']))
    ms = GEO['mount_standoffs']  # coaxial with the carrier MS1/MS2 holes (10 mm standoff = carrier F to panel rear)
    assert ms['length_mm'] == GEO['stack_Z_mm']['panel_rear_seat']
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    for x, y in ms['XY_mm']:  # bolt head inside the rail gap
        assert ry0 < y - ms['panel_bolt_head_R_mm'] and y + ms['panel_bolt_head_R_mm'] < ry1, ('bolt in rail band', x, y)
        spots.append((x, y, ms['panel_hole_d_mm']))
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
    builders = {'mcu': build_mcu, 'panel': build_panel}
    if not sys.argv[1:] or set(sys.argv[1:]) - set(builders):
        sys.exit('usage: build_layout.py [mcu] [panel]  (never a board that is placed / routed by hand)')
    for name in sys.argv[1:]:
        print(builders[name]())
