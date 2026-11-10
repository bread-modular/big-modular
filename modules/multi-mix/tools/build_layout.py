"""Generate the MULTI-MIX boards from docs/geometry.json and the native schematic netlists.

Run from modules/multi-mix with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/build_layout.py

modules/usb-audio-max/tools/build_layout.py (carrier + MCU board + panel) with modules/4mix's pots,
big-knob reserve and M3 standoffs. Writes (S1/P3 placement, UNROUTED, not for fabrication):
- hardware/multi-mix.kicad_pcb      carrier, 4 layers, 20HP: the 11 jacks, 15 pots, power header J8,
                                    CLK OUT/IN box headers J6/J7, the MCU-board strips J12-J14, SWD
                                    J15, RESET/BOOT SW1/SW2 and three M3x10 standoffs placed; every
                                    other SMD part parked in a grid right of the board (B side)
- hardware/multi-mix-mcu.kicad_pcb  MCU board (notched outline), 4 layers: USB-C J101 and the strip
                                    holes J112-J114 placed (same XY as J12-J14), the rest parked;
                                    U101 zone reserved
- panels/front-pcb/multi-mix-panel.kicad_pcb  passive 20HP FR4 panel: NPTH holes, USB-C slot, labels

Placement comes from the geometry contract; references, values, fields, symbol links and pad nets
come from the netlists kicad-cli exports from the schematics (what "Update PCB from Schematic"
would do). Once SMD placement starts by hand on a board, that board owns placement: do not rerun
this script over hand work.

3D models are vendored into hardware/_kicad_models/<sha256>/<name> and bound via ${KIPRJMOD}.
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
LIBNAME = 'MULTIMIX'
LIB = HW / f'{LIBNAME}.pretty'
CARRIER, MCU = 'multi-mix', 'multi-mix-mcu'
OX, OY = GEO['kicad_origin_mm']
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
STANDOFF_STEP = MODULE.parents[0] / '4mix/mechanical/standoff-m3x10.step'

JACK_FP = {'QingPu WQP-PJ301M-12': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical'}
HAND_SOLDER_MM = 2.0   # root AGENTS.md: SMD pads >= 2 mm from every pot/jack pad
EDGE_MM = 1.0          # root AGENTS.md: courtyards >= 1 mm from Edge.Cuts


def pt(x, y):
    """Panel-frame mm -> KiCad internal units."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def new_board(path, title, comments, rev='S1/P3'):
    board = pcbnew.NewBoard(str(path))
    tb = board.GetTitleBlock()
    tb.SetTitle(title)
    tb.SetRevision(rev)
    tb.SetCompany('Big Modular')
    for i, text_ in enumerate(comments):
        tb.SetComment(i, text_)
    return board


def rect(board, layer, x0, y0, x1, y1, width=0.05):
    shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    shape.SetLayer(layer)
    shape.SetWidth(pcbnew.FromMM(width))
    shape.SetStart(pt(x0, y0))
    shape.SetEnd(pt(x1, y1))
    board.Add(shape)
    shape.thisown = 0


def polygon(board, layer, pts, width=0.05):
    """Closed outline of straight segments (panel frame)."""
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(layer)
        seg.SetWidth(pcbnew.FromMM(width))
        seg.SetStart(pt(ax, ay))
        seg.SetEnd(pt(bx, by))
        board.Add(seg)
        seg.thisown = 0


MCU_RECTS = [tuple(r) for r in GEO['mcu_pcb']['outline_rects_mm']]  # disjoint rectangles = the notched outline
MCU_POLY = [tuple(q) for q in GEO['mcu_pcb']['outline_polygon_mm']]


def mcu_gap(box):
    """Clearance from a box to the MCU board outline (negative = overlap)."""
    return min(box_gap(box, r) for r in MCU_RECTS)


def inside_mcu(box):
    """True if the box lies inside the notched MCU board outline (area of its overlap with the rectangles)."""
    area = (box[2] - box[0]) * (box[3] - box[1])
    cover = sum(max(0.0, min(box[2], r[2]) - max(box[0], r[0])) * max(0.0, min(box[3], r[3]) - max(box[1], r[1]))
                for r in MCU_RECTS)
    return cover >= area - 1e-6


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
    return t


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
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') != 'Footprint'}
        props = {pp.get('name') for pp in c.findall('property')}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'uuid': c.findtext('tstamps').split()[0], 'fields': fields,
                               'not_in_bom': 'exclude_from_bom' in props}
    nets = {net_name(n.get('name')): [(d.get('ref'), d.get('pin')) for d in n.findall('node')]
            for n in root.find('nets')}
    return comps, nets


def net_name(name):
    """The XML netlist un-escapes names; KiCad stores a '/' inside an auto-generated pin-name net
    as {slash}, which native DRC parity compares against (as modules/usb-audio-max)."""
    for prefix in ('Net-(', 'unconnected-('):
        if name.startswith(prefix):
            return prefix + name[len(prefix):].replace('/', '{slash}')
    return name


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
    """Save, then reload and save once more so the file equals its own native re-serialisation."""
    pcbnew.SaveBoard(str(path), board)
    pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))


def pad_uuid(project, ref, number, index):
    """Deterministic pad UUID: (project, reference, pad number, library pad order)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/multi-mix/{project}/pcb/pad/{ref}/{number}/{index}'))


def place(board, ref, name, x, y, rot, comp, back=False, anchor='centre', project=CARRIER):
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


def box_gap(a, b):
    """Clearance between two boxes (x0, y0, x1, y1); negative = overlap."""
    dx = max(b[0] - a[2], a[0] - b[2])
    dy = max(b[1] - a[3], a[1] - b[3])
    return max(dx, dy) if dx < 0 or dy < 0 else math.hypot(dx, dy)


def standoff(board, ref, x, y):
    """Board-only M3 hex standoff footprint (as modules/4mix): origin = standoff axis, NPTH, F courtyard =
    hex circumcircle, B courtyard = bolt head, F.Fab hex, 3D model standoff-m3x10.step. Panel hole coaxial."""
    ms = GEO['mount_standoffs']
    mm = pcbnew.FromMM
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
    size = pcbnew.VECTOR2I(mm(ms['carrier_hole_d_mm']), mm(ms['carrier_hole_d_mm']))
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, size)
    pad.SetDrillSize(size)
    pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad)
    pad.thisown = 0

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
    model.m_Filename = vendor_model(str(STANDOFF_STEP))
    fp.Models().push_back(model)
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))
    return fp


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
    text(board, pcbnew.Dwgs_User, f'{GEO["hp"]}HP PANEL {pw:.1f} x {ph:.1f}', pw / 2, -2.0, 1.0)


def park(board, comps, placed, project, origin=None):
    """Every part not placed yet (SMD, B side on the carrier / F side on the MCU board) in columns
    right of the board, sorted by prefix and number, for group-by-group placement."""
    p = GEO['parking']
    ox, oy = origin or p['origin_XY']
    gap, y_max = p['gap_mm'], p['column_height_mm']
    key = lambda r: (r.rstrip('0123456789'), int(r[len(r.rstrip('0123456789')):]))  # noqa: E731
    rest = sorted((r for r in comps if r not in placed), key=key)
    cx, cy, col_w = ox, oy, 0.0
    back = project == CARRIER
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


def assign_nets(board, comps, nets):
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
            ok = pad.GetNumber() == '' or pad.GetNetname() or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
            assert ok, f'{fp.GetReference()} pad {pad.GetNumber()} has no net'
    return fps


def header(board, ref, spec, comp, project):
    """1x10 strip: pin 1 at pin1_XY, pins running down (+Y)."""
    x, y = spec['pin1_XY']
    fp = place(board, ref, spec['footprint'], x, y, 0, comp, anchor='origin', project=project)
    px, py = pad_xy(fp, '1')
    assert abs(px - x) < 0.01 and abs(py - y) < 0.01, ref
    return fp


def big_knob_centres():
    shafts = {q['ref']: q['shaft_XY'] for q in GEO['pots']}
    return [shafts[r] for r in GEO['big_knob']['refs']]


def pad_gap(a, b):
    """Copper edge-to-edge distance between two pads (mm), from their shapes on any shared layer."""
    sa = a.GetEffectivePolygon(pcbnew.F_Cu if a.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
    sb = b.GetEffectivePolygon(pcbnew.F_Cu if b.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
    best = None
    for i in range(sa.OutlineCount()):
        for j in range(sb.OutlineCount()):
            ca, cb = sa.Outline(i), sb.Outline(j)
            d = min(ca.SquaredDistance(cb.CPoint(k)) for k in range(cb.PointCount()))
            d = pcbnew.ToMM(math.sqrt(min(d, min(cb.SquaredDistance(ca.CPoint(k)) for k in range(ca.PointCount())))))
            best = d if best is None else min(best, d)
    return best


def build_carrier():
    path = HW / f'{CARRIER}.kicad_pcb'
    comps, nets = schematic_netlist(CARRIER)
    board = new_board(path, 'Big Modular - MULTI-MIX carrier', [
        'S1/P3: THT placement + 3 M3x10 standoffs only (SMD parked off-board), UNROUTED - not released, not for fabrication',
        f'{GEO["hp"]}HP. Front (F) faces the panel; jacks/pots/headers hand-soldered; SMD on B; 4 layers',
        'MCU board (multi-mix-mcu) sits on J12/J13/J14 in the top-right corner; geometry: docs/geometry.json',
    ])
    setup(board, GEO['main_pcb']['copper_layers'])
    x0, y0, x1, y1 = GEO['main_pcb']['outline_mm']
    rect(board, pcbnew.Edge_Cuts, x0, y0, x1, y1)
    fit_refs(board)
    bk = GEO['big_knob']
    for xy in big_knob_centres():
        circle(board, pcbnew.Dwgs_User, *xy, bk['reserve_D_mm'])
    for j in GEO['jacks']:
        place(board, j['ref'], JACK_FP[j['part']], *j['XY'], GEO['jack_rotation_deg'], comps[j['ref']],
              anchor='origin')
    sx_off, sy_off = GEO['pot_shaft_offset_mm']
    for p in GEO['pots']:  # footprint origin = shaft - offset (rotation 0)
        sx, sy = p['shaft_XY']
        place(board, p['ref'], GEO['pot_footprint'], sx - sx_off, sy - sy_off, 0, comps[p['ref']], anchor='origin')
    for h in GEO['carrier_headers']:
        header(board, h['ref'], h, comps[h['ref']], CARRIER)
    for p in GEO['back_side_parts']:
        place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], back=True,
              anchor=p.get('anchor', 'centre'))
    ms = GEO['mount_standoffs']
    standoffs = [standoff(board, r, *xy) for r, xy in zip(ms['refs'], ms['XY_mm'])]
    m = MCU_RECTS[0]
    polygon(board, pcbnew.Dwgs_User, MCU_POLY)
    text(board, pcbnew.Dwgs_User, 'MCU BOARD (F side, Z 2.5-4.1)', (m[0] + m[2]) / 2, m[3] - 1.2, 0.8)
    us = GEO['usb_slot']
    rect(board, pcbnew.Dwgs_User, us['XY'][0] - us['size_mm'][0] / 2, us['XY'][1] - us['size_mm'][1] / 2,
         us['XY'][0] + us['size_mm'][0] / 2, us['XY'][1] + us['size_mm'][1] / 2)
    placed = {fp.GetReference() for fp in board.GetFootprints()} - {''}
    park(board, comps, placed, CARRIER)
    fps = assign_nets(board, comps, nets)
    report = {}
    # Jacks and pots where the contract says.
    for j in GEO['jacks']:
        x, y = j['XY']
        tx, ty = pad_xy(fps[j['ref']], 'T')
        _, sy = pad_xy(fps[j['ref']], 'S')
        assert abs(tx - x) < 0.01 and abs(ty - (y - 4.92)) < 0.01 and abs(sy - (y + 6.48)) < 0.01, j['ref']
    for p in GEO['pots']:
        sx, sy = p['shaft_XY']
        x1_, y1_ = pad_xy(fps[p['ref']], '1')
        x3_, _ = pad_xy(fps[p['ref']], '3')
        assert abs(x1_ - (sx - 2.5)) < 0.01 and abs(x3_ - (sx + 2.5)) < 0.01 and abs(y1_ - (sy + 7.5)) < 0.01, p['ref']
    # 1 mm edge keep-out for every placed courtyard (DRC does not check courtyards against the edge).
    fixed = [fps[j['ref']] for j in GEO['jacks']] + [fps[p['ref']] for p in GEO['pots']]
    placed_fps = fixed + [fps[h['ref']] for h in GEO['carrier_headers']] + \
        [fps[p['ref']] for p in GEO['back_side_parts']] + standoffs
    edge = {}
    for fp in placed_fps:
        a, b, c, d = courtyard_box(fp)
        margin = min(a - x0, b - y0, x1 - c, y1 - d)
        edge[fp.GetReference() or fp.GetFieldText('MechanicalID')] = round(margin, 3)
        assert margin >= EDGE_MM - 1e-6, (fp.GetReference(), 'courtyard within 1 mm of the edge', round(margin, 3))
    report['closest_courtyard_to_edge'] = sorted(edge.items(), key=lambda kv: kv[1])[:4]
    # The MCU board stands on F between the carrier and the panel: no jack/pot body or standoff under it.
    mcu_gap_ = {}
    for fp in fixed + standoffs:
        g = mcu_gap(courtyard_box(fp))
        mcu_gap_[fp.GetReference() or fp.GetFieldText('MechanicalID')] = round(g, 3)
        assert g > 0, ('F courtyard under the MCU board', fp.GetReference(), round(g, 3))
    report['closest_F_courtyard_to_mcu_board'] = sorted(mcu_gap_.items(), key=lambda kv: kv[1])[:4]
    # J15 tails come through to F: outside the MCU board and the jack bodies.
    for pad in fps['J15'].Pads():
        bb = pad.GetBoundingBox()
        box = tuple(v - o for v, o in zip((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                                           pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())), (OX, OY, OX, OY)))
        assert mcu_gap(box) > 0.5, 'J15 tail under the MCU board'
    # B-side box headers (J6/J7/J8): no other part's through-hole pad (pot lugs, jack pins) under their bodies.
    box_gap_min = {}
    for ref in ('J6', 'J7', 'J8'):
        yard = courtyard_box(fps[ref])
        for fp in placed_fps:
            if fp.GetReference() == ref:
                continue
            for pad in fp.Pads():
                if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                    continue
                bb = pad.GetBoundingBox()
                box = tuple(v - o for v, o in zip((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                                                   pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())), (OX, OY, OX, OY)))
                g = box_gap(box, yard)
                assert g > 0.05, ('THT pad under a B box header', ref, fp.GetReference(), round(g, 3))
                box_gap_min[ref] = min(box_gap_min.get(ref, (9e9,)), (round(g, 3), fp.GetReference()))
    report['closest_THT_pad_to_B_header_courtyard'] = box_gap_min
    # 2 mm hand-solder clearance: placed SMD pads (SW1/SW2) to every jack/pot pad.
    smd = [pad for r in ('SW1', 'SW2') for pad in fps[r].Pads()]
    worst = min((pad_gap(a, b), a.GetParentFootprint().GetReference(), b.GetParentFootprint().GetReference())
                for a in smd for f in fixed for b in f.Pads())
    assert worst[0] >= HAND_SOLDER_MM, ('hand-solder clearance', worst)
    report['closest_smd_to_pot_jack_pad'] = (round(worst[0], 2), worst[1], worst[2])
    # Power header pin 1 at the bottom row.
    ph_ = GEO['power_header']
    px, py = pad_xy(fps['J8'], '1')
    assert abs(px - ph_['pin1_XY_mm'][0]) < 0.01 and abs(py - ph_['pin1_XY_mm'][1]) < 0.01, ('J8 pin 1', px, py)
    sx, sy = ph_['idc16_socket_envelope_mm']['X'], ph_['idc16_socket_envelope_mm']['Y']
    rect(board, pcbnew.Dwgs_User, sx[0], sy[0], sx[1], sy[1])
    text(board, pcbnew.Dwgs_User, 'IDC16', (sx[0] + sx[1]) / 2, sy[0] + 1.0, 0.8)
    # CLK headers level, pin 1 at the top.
    (ax, ay), (bx, by) = pad_xy(fps['J6'], '1'), pad_xy(fps['J7'], '1')
    assert abs(ay - by) < 0.01 and ay < pad_xy(fps['J6'], '9')[1], 'J6/J7 pin 1 rows'
    for t in GEO['back_silk']:
        text(board, pcbnew.B_SilkS, t['text'], *t['XY'], t['size'], mirrored=True)
    for ref, label, dy in (('SW1', 'RESET', -2.6), ('SW2', 'BOOT', 2.6)):
        x, y = next(p['XY'] for p in GEO['back_side_parts'] if p['ref'] == ref)
        text(board, pcbnew.B_SilkS, label, x, y + dy, 0.8, mirrored=True)
    x, y = next(p['XY'] for p in GEO['back_side_parts'] if p['ref'] == 'J15')
    text(board, pcbnew.B_SilkS, 'SWD', x, y + 3 * 2.54 + 2.6, 0.8, mirrored=True)  # below: MS3 is above
    save_canonical(path, board)
    return path, report


def build_mcu():
    path = HW / f'{MCU}.kicad_pcb'
    comps, nets = schematic_netlist(MCU)
    board = new_board(path, 'Big Modular - MULTI-MIX MCU board', [
        'S1/P3: USB-C and strip holes placed, other SMD parked, UNROUTED - not for fabrication',
        'All SMD on F (faces the panel); sits on the carrier J12/J13/J14 strips; 4 layers',
        'Geometry contract: docs/geometry.json (same frame as the carrier)',
    ])
    setup(board, GEO['mcu_pcb']['copper_layers'])
    polygon(board, pcbnew.Edge_Cuts, MCU_POLY)
    fit_refs(board)
    parts = []
    for p in GEO['mcu_parts']:
        if 'pin1_XY' in p:
            parts.append(header(board, p['ref'], p, comps[p['ref']], MCU))
        else:
            parts.append(place(board, p['ref'], p['footprint'], *p['XY'], p['rot'], comps[p['ref']], project=MCU))
    zones = []
    for z in GEO['reserved_zones_mcu']:
        rect(board, pcbnew.Dwgs_User, z['X'][0], z['Y'][0], z['X'][1], z['Y'][1])
        text(board, pcbnew.Dwgs_User, 'U101 LQFP-64', sum(z['X']) / 2, sum(z['Y']) / 2, 1.0)
        zones.append((z['X'][0], z['Y'][0], z['X'][1], z['Y'][1]))
    placed = {fp.GetReference() for fp in board.GetFootprints()}
    park(board, comps, placed, MCU, origin=(max(r[2] for r in MCU_RECTS) + 8.0, 10.0))
    assign_nets(board, comps, nets)
    report = {}
    boxes = {fp.GetReference(): courtyard_box(fp) for fp in parts}
    refs = sorted(boxes)
    for i, a in enumerate(refs):  # placed parts: no courtyard overlap, inside the outline, clear of U101
        for b in refs[i + 1:]:
            assert box_gap(boxes[a], boxes[b]) > 0, ('MCU courtyards overlap', a, b)
        for z in zones:
            assert box_gap(boxes[a], z) > 0.5, ('MCU part in the U101 zone', a)
        assert inside_mcu(boxes[a]), ('outside the MCU board outline', a)
    report['J114_to_J113_courtyard_gap'] = round(box_gap(boxes['J114'], boxes['J113']), 3)
    report['J101_to_J114_courtyard_gap'] = round(box_gap(boxes['J101'], boxes['J114']), 3)
    save_canonical(path, board)
    return path, report


def build_panel():
    path = MODULE / 'panels/front-pcb/multi-mix-panel.kicad_pcb'
    path.parent.mkdir(parents=True, exist_ok=True)
    board = new_board(path, f'Big Modular - MULTI-MIX {GEO["hp"]}HP front panel', [
        'S1/P3 FIT STUDY: passive panel, NPTH only (holes + USB-C slot), no copper',
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
    ms = GEO['mount_standoffs']  # coaxial with the carrier MS holes (10 mm standoff = carrier F to panel rear)
    assert ms['length_mm'] == GEO['stack_Z_mm']['panel_rear_seat']
    assert ms['panel_hole_refs'][0] == f'H{n + 1}'
    ry0, ry1 = GEO['rail_clear_gap_Y_mm']
    for ref, (x, y) in zip(ms['panel_hole_refs'], ms['XY_mm']):
        assert ry0 < y - ms['panel_bolt_head_R_mm'] and y + ms['panel_bolt_head_R_mm'] < ry1, ('bolt in rail band', ref)
        npth(board, ref, x, y, ms['panel_hole_d_mm'])
    slot = GEO['usb_slot']
    npth(board, f'H{n + 1 + len(ms["refs"])}', *slot['XY'], min(slot['size_mm']), slot=slot['size_mm'])
    for lab in GEO['panel_labels']:
        t = text(board, pcbnew.F_SilkS, lab['text'], *lab['XY'], lab['size'])
        bb = t.GetBoundingBox()
        assert pcbnew.ToMM(bb.GetLeft()) - OX >= 1.0 and pcbnew.ToMM(bb.GetRight()) - OX <= pw - 1.0, lab
    bk = GEO['big_knob']
    rk = bk['reserve_D_mm'] / 2
    centres = big_knob_centres()
    for xy in centres:
        circle(board, pcbnew.Dwgs_User, *xy, bk['reserve_D_mm'])
    # Front clearances: label boxes vs knobs/nuts/bolt heads/USB slot, big knobs vs everything (as modules/4mix).
    boxes = [(t.GetText(), t.GetBoundingBox()) for t in board.GetDrawings()
             if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS]
    rounds = [(j['ref'], j['XY'], bk['jack_nut_R_mm']) for j in GEO['jacks']]
    rounds += [(q['ref'], q['shaft_XY'], bk['small_knob_R_mm']) for q in GEO['pots'] if q['ref'] not in bk['refs']]
    rounds += [(r, xy, ms['panel_bolt_head_R_mm']) for r, xy in zip(ms['refs'], ms['XY_mm'])]
    rounds += [(r, xy[:2], 3.0) for r, xy in zip(('rail1', 'rail2', 'rail3', 'rail4'), GEO['rail_holes_mm'])]

    def box_to_point(bb, cx, cy):
        nx = min(max(OX + cx, pcbnew.ToMM(bb.GetLeft())), pcbnew.ToMM(bb.GetRight())) - OX
        ny = min(max(OY + cy, pcbnew.ToMM(bb.GetTop())), pcbnew.ToMM(bb.GetBottom())) - OY
        return math.hypot(nx - cx, ny - cy)

    worst_label = None
    for s, bb in boxes:
        for ref, (x, y), rr in rounds + [(r, xy, rk) for r, xy in zip(bk['refs'], centres)]:
            g = box_to_point(bb, x, y) - rr
            assert g > 0.3, ('panel label over a knob/nut/bolt', s, ref, round(g, 2))
            worst_label = min(worst_label or (9e9,), (round(g, 2), s, ref))
        sx_, sy_ = slot['XY']
        sw, sh = slot['size_mm']
        box = (pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY,
               pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY)
        assert box_gap(box, (sx_ - sw / 2, sy_ - sh / 2, sx_ + sw / 2, sy_ + sh / 2)) > 0.5, ('label on the USB slot', s)
    for n_, (cx, cy) in enumerate(centres):
        for ref, (x, y), rr in rounds:
            assert math.hypot(x - cx, y - cy) - rr - rk > 0, ('big knob overlaps', bk['refs'][n_], ref)
        for ox, oy in centres[n_ + 1:]:
            assert math.hypot(ox - cx, oy - cy) > 2 * rk + 1.0, ('big knobs overlap', bk['refs'][n_])
    knobs = [(q['ref'], q['shaft_XY']) for q in GEO['pots'] if q['ref'] not in bk['refs']]
    near = min((math.hypot(a[1][0] - b[1][0], a[1][1] - b[1][1]) - 2 * bk['small_knob_R_mm'], a[0], b[0])
               for i, a in enumerate(knobs) for b in knobs[i + 1:])
    assert near[0] > 2.0, ('small knobs too close', near)
    save_canonical(path, board)
    return path, {'closest_label_gap': worst_label, 'closest_small_knob_gap': (round(near[0], 2), near[1], near[2])}


if __name__ == '__main__':
    for fn in (build_carrier, build_mcu, build_panel):
        p, rep = fn()
        print(p)
        for k, v in rep.items():
            print('  ', k, v)
