"""Generate the routed busboard PCB (hardware/busboard.kicad_pcb) from the native netlist.

Run from modules/busboard with KiCad's Python (pcbnew 10), after tools/build_schematic.py:
  python3 -B tools/build_layout.py

2-layer, 205 x 32 mm. J1-J8 (shrouded 2x08 IDC box headers) in one row at a 22.5 mm pitch,
long axis across the board, all with pin 1 (-12 V) at the top edge, 1.5 mm from the courtyards
to the top and bottom edges. Each bus pin row runs
straight across the board as a track from pad centre to pad centre: -12V, GND, +12V and +5V
1.5 mm on F.Cu and B.Cu, CV and GATE 0.5 mm on B.Cu. GND pours on both layers. Four NPTH M3
holes (board-only footprints), two at each end within the header height, over the bottom plate's
solid frame: M3 bolts from under the plate into nuts on the board.

Hand-drawn straight segments, no router. Rerunning this script rebuilds the whole board.
"""
import hashlib
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
LIB = HW / 'Busboard.pretty'
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
OX, OY = 100.0, 100.0           # board top-left corner in KiCad coordinates

W, H = 205.0, 32.0              # board outline
PITCH = 22.5                    # header to header
PIN1 = (22.5, 7.1)              # J1 pin 1 (courtyard 5.6 above it); J8 pin 1 at x = 180.0
ROW = 2.54
# 196 x 21 mm hole pitch: over the case bottom plate's solid frame at each side panel
# (case/tools/build_case.py BUS_*), beyond the centre pocket
HOLES = [(x, y) for x in (4.5, 200.5) for y in (5.5, 26.5)]   # beside J1 / J8, not above them
# bus row (0 = pins 1/2) -> net, width, layers
ROWS = {0: ('-12V', 1.5, 'FB'), 1: ('GND', 1.5, 'FB'), 2: ('GND', 1.5, 'FB'), 3: ('GND', 1.5, 'FB'),
        4: ('+12V', 1.5, 'FB'), 5: ('+5V', 1.5, 'FB'), 6: ('CV', 0.5, 'B'), 7: ('GATE', 0.5, 'B')}
ZONE_CLEARANCE = 0.5            # pour to other nets: no slivers between the 1.5 mm rails
SLOTS = 8


def pt(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def schematic_netlist():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'busboard.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / 'busboard.kicad_sch')], check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find('components'):
        fields = {f.get('name'): f.text or '' for f in c.find('fields') if f.get('name') != 'Footprint'}
        comps[c.get('ref')] = {'value': c.findtext('value'), 'footprint': c.findtext('footprint'),
                               'uuid': c.findtext('tstamps').split()[0], 'fields': fields}
    nets = {(d.get('ref'), d.get('pin')): n.get('name') for n in root.find('nets') for d in n.findall('node')}
    return comps, nets


def vendor_model(token):
    """Copy a stock model into hardware/_kicad_models/<sha256>/ and bind it via ${KIPRJMOD}."""
    src = Path(token.replace('${KICAD10_3DMODEL_DIR}', '/usr/share/kicad/3dmodels'))
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    dest = HW / '_kicad_models' / digest / src.name
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return '${KIPRJMOD}/_kicad_models/%s/%s' % (digest, src.name)


def footprint(board, name):
    fp = IO.FootprintLoad(str(LIB), name)
    fp.SetFPID(pcbnew.LIB_ID('Busboard', name))
    board.Add(fp)
    fp.thisown = 0
    models = fp.Models()
    for i in range(len(models)):
        model = models[i]
        model.m_Filename = vendor_model(model.m_Filename)
        models[i] = model
    return fp


def text(board, layer, s, x, y, size, just=pcbnew.GR_TEXT_H_ALIGN_CENTER, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(max(0.15, size * 0.15)))
    t.SetHorizJustify(just)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    t.SetPosition(pt(x, y))
    board.Add(t)
    t.thisown = 0


def track(board, net, layer, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(*a))
    t.SetEnd(pt(*b))
    t.SetWidth(pcbnew.FromMM(width))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)
    t.thisown = 0


def zone(board, net, layer):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetLocalClearance(pcbnew.FromMM(ZONE_CLEARANCE))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.5))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.8))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
        ol.Append(pt(x, y))
    z.SetZoneName(f'GND_{board.GetLayerName(layer)}')
    board.Add(z)
    z.thisown = 0


def build():
    comps, pinnet = schematic_netlist()
    path = HW / 'busboard.kicad_pcb'
    board = pcbnew.NewBoard(str(path))
    tb = board.GetTitleBlock()
    tb.SetTitle('Big Modular - Busboard')
    tb.SetRevision('R3')
    tb.SetCompany('Big Modular')
    tb.SetComment(0, 'S1/R3: passive 8 x 16-pin Eurorack bus, 2-layer 205 x 32 mm - not released')
    board.SetCopperLayerCount(2)
    board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))

    rect = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    rect.SetLayer(pcbnew.Edge_Cuts)
    rect.SetWidth(pcbnew.FromMM(0.05))
    rect.SetStart(pt(0, 0))
    rect.SetEnd(pt(W, H))
    board.Add(rect)
    rect.thisown = 0

    netinfo = {}
    for name in sorted(set(pinnet.values())):
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        netinfo[name] = n

    for i in range(SLOTS):
        ref = f'J{i + 1}'
        comp = comps[ref]
        lib, name = comp['footprint'].split(':')
        assert lib == 'Busboard'
        fp = footprint(board, name)
        fp.SetReference(ref)
        fp.SetValue(comp['value'])
        fp.SetPath(pcbnew.KIID_PATH('/' + comp['uuid']))
        fp.SetSheetname('/')
        fp.SetSheetfile('busboard.kicad_sch')
        for key, val in comp['fields'].items():
            if key.startswith('__') or key in ('Reference', 'Value'):
                continue
            fp.SetField(key, val)
            fp.GetField(key).SetVisible(False)
        fp.SetPosition(pt(PIN1[0] + i * PITCH, PIN1[1]))
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Value().SetVisible(False)
        for pad in fp.Pads():
            pad.SetNet(netinfo[pinnet[(ref, pad.GetNumber())]])

    for k, (x, y) in enumerate(HOLES):
        fp = footprint(board, 'MountingHole_3.2mm_M3')
        fp.SetReference('')             # mechanical: no schematic symbol (repository convention)
        fp.SetValue('MountingHole_M3')
        fp.SetField('MechanicalID', f'H{k + 1}')
        fp.GetField('MechanicalID').SetVisible(False)
        fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.SetPosition(pt(x, y))

    layers = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
    for row, (net, width, sides) in ROWS.items():
        y = round(PIN1[1] + row * ROW, 2)
        xs = [round(PIN1[0] + i * PITCH + c, 2) for i in range(SLOTS) for c in (0, ROW)]
        for side in sides:
            for a, b in zip(xs, xs[1:]):
                track(board, netinfo[net], layers[side], (a, y), (b, y), width)
        # rail names in the J1-J2 finger gap
        text(board, pcbnew.F_SilkS, net, PIN1[0] + 7.0, y, 0.8, pcbnew.GR_TEXT_H_ALIGN_LEFT)

    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(board, netinfo['GND'], layer)
    # no room above/below the headers: legends run vertically in the finger gaps
    gap = lambda i: PIN1[0] + ROW / 2 + (i + 0.5) * PITCH   # centre between J(i+1) and J(i+2)
    text(board, pcbnew.F_SilkS, 'BIG MODULAR BUSBOARD R3', gap(3), H / 2, 1.2, angle=90)
    text(board, pcbnew.F_SilkS, 'RED STRIPE = -12V (TOP)', gap(5), H / 2, 1.0, angle=90)
    text(board, pcbnew.B_SilkS, 'BIG MODULAR BUSBOARD R3', gap(3), H / 2, 1.2, angle=90)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)
    pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))
    print(path)


if __name__ == '__main__':
    build()
