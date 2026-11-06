"""Shared pcbnew 10 board helpers for tools/build_s8_board.py and tools/build_s8_panel.py.

Coordinate frames (V carrier, CV carrier Y/Z, PV panel), board creation, drawing primitives,
footprint placement from hardware/USBPOWER45.pretty, NPTH holes and save_canonical() (saves in a
private temporary project copy so the project file is never rewritten). Geometry comes from
docs/mechanical-geometry.json.
"""
import json
import shutil
import sys
import tempfile
import uuid
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
