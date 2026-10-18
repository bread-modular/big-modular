#!/usr/bin/env python3
"""Generate the routed 2-layer PCB from design.py + the generated schematic.

    python3 -B opt/updi-programmer/tools/build_schematic.py
    python3 -B opt/updi-programmer/tools/build_pcb.py

Needs KiCad 10 pcbnew Python. Placement and every track/via below are
explicit (hand-planned, no autorouter); GND is a pour on both layers.
Footprint paths/fields come from the schematic so DRC schematic parity holds.
"""
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design as D  # noqa: E402
from build_schematic import FPLIB, HW, uid  # noqa: E402

import pcbnew  # noqa: E402

PCB = HW / (D.PROJECT + '.kicad_pcb')
PRO = HW / (D.PROJECT + '.kicad_pro')

# Board outline (mm), all four corners rounded. USB-C near the top-left
# corner (shell 1.5 mm below the top edge so it clears the corner radius), UPDI
# header on the right. The receptacle mouth overhangs the left edge by 1.2 mm
# (same as modules/usb-power: front shell slot copper 0.6 mm inside the edge)
# so any plug overmold clears the FR4.
X0, Y0, W, H, RADIUS = 100.0, 100.0, 42.0, 18.0, 1.0
USB_OVERHANG = 1.2

# ref: (x, y, rotation degrees)
PLACE = {
    'J2': (X0 - USB_OVERHANG, 106.9, 270),  # mouth = footprint origin
    'R3': (111.0, 105.2, 270),
    'R4': (110.5, 110.3, 270),
    'C2': (105.5, 115.6, 0),
    'U1': (115.5, 109.0, 0),
    'C1': (117.975, 112.96, 270),
    'C3': (119.4, 105.2, 90),
    'C4': (115.0, 104.3, 0),
    'R1': (122.5, 110.2, 0),
    'R2': (122.5, 108.365, 0),
    'R7': (121.5, 105.6, 180),
    'D2': (124.6, 105.6, 0),
    'D1': (124.0, 101.4, 0),
    'R6': (120.8, 101.4, 180),
    'U2': (129.0, 107.5, 270),
    'C5': (129.1, 104.6, 0),
    'R5': (132.8, 105.0, 0),
    'R8': (133.625, 103.0, 90),
    'J1': (136.5, 115.16, 180),  # pin 1 (UPDI) bottom, pin 5 (SELF) at y 105.0
}

SIG, PWR, THIN = 0.2, 0.4, 0.3
F, B = 'F.Cu', 'B.Cu'

# (net, width, layer, [points])
TRACKS = [
    # USB D+ : A6/B6 drop to B.Cu behind the pads, back up next to U1.1
    ('D+', SIG, F, [(106.495, 106.65), (104.99, 106.65)]),
    ('D+', SIG, F, [(106.495, 107.65), (104.99, 107.65)]),
    ('D+', SIG, B, [(104.99, 107.65), (104.99, 107.1)]),
    ('D+', SIG, B, [(104.99, 106.65), (104.99, 107.1), (111.3, 107.1)]),
    ('D+', SIG, F, [(111.3, 107.1), (113.025, 107.095)]),
    # USB D- : B7/A7 joined on F.Cu, then down to U1.2
    ('D-', SIG, F, [(106.495, 106.15), (108.14, 106.15), (108.14, 107.15)]),
    ('D-', SIG, F, [(106.495, 107.15), (108.14, 107.15), (109.355, 108.365), (113.025, 108.365)]),
    # CC pull-downs
    ('CC1', SIG, F, [(106.495, 105.65), (110.0, 105.65), (111.0, 104.65), (111.0, 104.375)]),
    ('CC2', SIG, F, [(106.495, 108.65), (108.4, 108.65), (109.225, 109.475), (110.5, 109.475)]),
    # +5V top rail: VBUS A4 -> C4 -> D1 -> U2 VCC / C5
    ('+5V', PWR, F, [(106.495, 104.45), (108.3, 104.45), (109.75, 103.0), (128.6, 103.0)]),
    ('+5V', THIN, F, [(128.6, 103.0), (128.6, 105.5)]),
    ('+5V', SIG, F, [(128.6, 105.5), (128.6, 106.05)]),
    ('+5V', THIN, F, [(113.525, 103.0), (113.525, 104.3)]),
    ('+5V', THIN, F, [(124.787, 103.0), (124.787, 101.4)]),
    # +5V bottom rail: VBUS A9 drops to B.Cu (clear of CC2), up again at C1 -> U1 VCC
    ('+5V', PWR, F, [(106.495, 109.35), (107.75, 109.35)]),
    ('+5V', PWR, B, [(107.75, 109.35), (108.8, 110.4), (108.8, 111.45), (109.8, 112.45), (118.9, 112.45)]),
    ('+5V', PWR, F, [(117.975, 112.45), (118.9, 112.45)]),
    ('+5V', THIN, F, [(117.975, 110.905), (117.975, 112.45)]),
    # top and bottom rails joined on B.Cu beside U1
    ('+5V', PWR, B, [(118.9, 103.0), (118.9, 112.45)]),
    # CH340N
    ('V3', SIG, F, [(117.975, 107.095), (119.4, 107.095), (119.4, 105.71)]),
    ('RXD', SIG, F, [(117.975, 108.365), (121.675, 108.365)]),
    ('TXD', SIG, F, [(117.975, 109.635), (121.1, 109.635), (121.675, 110.2)]),
    ('SERIAL_RX', SIG, F, [(123.325, 108.365), (124.3, 108.365)]),
    ('SERIAL_RX', SIG, B, [(124.3, 108.365), (126.0, 110.9), (128.6, 110.9)]),
    ('SERIAL_RX', SIG, F, [(128.6, 110.9), (128.6, 108.95)]),
    ('SERIAL_TX', SIG, F, [(123.325, 110.2), (127.6, 110.2), (128.2, 109.6), (128.2, 108.95)]),
    # ATtiny1616
    ('GND', SIG, F, [(129.0, 106.05), (129.0, 107.5)]),
    ('LED', SIG, F, [(125.387, 105.6), (125.9, 105.6), (126.7, 106.4), (126.7, 107.5), (127.55, 107.5)]),
    ('D2_K', SIG, F, [(122.325, 105.6), (123.813, 105.6)]),
    ('D1_K', SIG, F, [(123.213, 101.4), (121.625, 101.4)]),
    ('RESET', SIG, F, [(130.45, 107.1), (131.0, 107.1), (131.975, 106.125), (131.975, 105.0)]),
    ('MCU_UPDI', SIG, F, [(133.625, 105.0), (136.5, 105.0)]),
    ('MCU_UPDI', SIG, F, [(133.625, 103.51), (133.625, 105.0)]),
    ('UPDI', 0.25, F, [(129.4, 108.95), (129.4, 110.0), (134.56, 115.16), (136.5, 115.16)]),
    # USB shell ring + shield capacitor
    ('SHIELD', THIN, F, [(101.4, 102.58), (105.58, 102.58)]),
    ('SHIELD', THIN, F, [(101.4, 111.22), (105.58, 111.22)]),
    ('SHIELD', THIN, F, [(101.4, 102.58), (101.4, 111.22)]),
    ('SHIELD', THIN, F, [(101.4, 111.22), (101.4, 114.25), (102.75, 115.6), (104.55, 115.6)]),
    # GND stubs to stitching vias
    ('GND', THIN, F, [(106.495, 103.675), (107.6, 103.675), (108.1, 103.175)]),
    ('GND', THIN, F, [(106.495, 110.125), (107.5, 110.125), (107.9, 110.75)]),
    ('GND', THIN, F, [(113.025, 109.635), (111.5, 109.635)]),
    ('GND', THIN, F, [(110.5, 111.125), (111.45, 111.1)]),
    ('GND', THIN, F, [(111.0, 106.025), (112.0, 105.8)]),
    ('GND', THIN, F, [(116.475, 104.3), (117.6, 104.3)]),
    ('GND', THIN, F, [(119.4, 104.69), (117.6, 104.3)]),
    ('GND', THIN, F, [(120.675, 105.6), (120.675, 104.4)]),
    ('GND', THIN, F, [(129.61, 104.6), (130.5, 104.6)]),
    ('GND', THIN, F, [(119.975, 101.4), (118.9, 101.4)]),
    ('GND', THIN, F, [(133.625, 102.49), (134.6, 102.49)]),
    ('GND', THIN, F, [(106.45, 115.6), (107.5, 115.6)]),
    ('GND', THIN, F, [(117.975, 113.47), (117.975, 114.5)]),
]

VIAS = [
    ('D+', (104.99, 106.65)), ('D+', (104.99, 107.65)), ('D+', (111.3, 107.1)),
    ('SERIAL_RX', (124.3, 108.365)), ('SERIAL_RX', (128.6, 110.9)),
    ('GND', (129.0, 107.5)),  # ATtiny1616 exposed pad
    ('GND', (108.1, 103.175)), ('GND', (107.9, 110.75)), ('GND', (111.45, 111.1)), ('GND', (112.0, 105.8)),
    ('GND', (117.6, 104.3)), ('GND', (120.675, 104.4)), ('GND', (130.5, 104.6)), ('GND', (118.9, 101.4)),
    ('GND', (134.6, 102.49)), ('GND', (107.5, 115.6)), ('GND', (117.975, 114.5)), ('GND', (111.5, 109.635)),
    ('+5V', (118.9, 103.0)), ('+5V', (118.9, 112.45)), ('+5V', (107.75, 109.35)),
    # stitching
    ('GND', (113.0, 116.5)), ('GND', (122.0, 116.5)), ('GND', (131.0, 116.5)), ('GND', (140.5, 101.5)),
    ('GND', (140.5, 116.5)), ('GND', (131.0, 101.5)), ('GND', (103.5, 116.5)),
]

SILK = [
    # (text, x, y, size, justify)
    # J1 pin labels, pin 1 (square pad) at the bottom
    ('UPDI', 138.4, 115.16, 0.8, 'left'),
    ('GND', 138.4, 112.62, 0.8, 'left'),
    ('GND', 138.4, 110.08, 0.8, 'left'),
    ('GND', 138.4, 107.54, 0.8, 'left'),
    ('SELF', 138.4, 105.0, 0.8, 'left'),
    ('PWR', 126.0, 101.4, 0.8, 'left'),
    ('ACT', 124.6, 104.05, 0.8, 'center'),
    ('BIG MODULAR UPDI v' + D.REV, 121.0, 115.5, 1.0, 'center'),
]

VIA_D, VIA_DRILL = 0.6, 0.3


def mm(x, y):
    return pcbnew.VECTOR2I_MM(x, y)


def layer(board, name):
    return board.GetLayerID(name)


def project_settings():
    """Design rules written to the .kicad_pro (JLCPCB 2-layer friendly)."""
    severities = {k: 'error' for k in (
        'annular_width', 'clearance', 'copper_edge_clearance', 'courtyards_overlap', 'drill_out_of_range',
        'hole_clearance', 'invalid_outline', 'item_on_disabled_layer', 'items_not_allowed', 'malformed_courtyard',
        'npth_inside_courtyard', 'pth_inside_courtyard', 'shorting_items', 'solder_mask_bridge', 'starved_thermal',
        'text_on_edge_cuts', 'through_hole_pad_without_hole', 'track_width', 'tracks_crossing', 'unconnected_items',
        'unresolved_variable', 'zones_intersect', 'footprint')}
    severities.update({k: 'warning' for k in (
        'connection_width', 'copper_sliver', 'duplicate_footprints', 'extra_footprint', 'footprint_symbol_mismatch',
        'footprint_symbol_field_mismatch', 'footprint_type_mismatch', 'hole_to_hole', 'holes_co_located',
        'isolated_copper', 'lib_footprint_issues', 'lib_footprint_mismatch', 'missing_courtyard', 'missing_footprint',
        'net_conflict', 'silk_edge_clearance', 'silk_over_copper', 'silk_overlap', 'text_height', 'text_thickness',
        'track_dangling', 'via_dangling', 'padstack', 'mirrored_text_on_front_layer', 'nonmirrored_text_on_back_layer',
        'track_not_centered_on_via')})
    return {
        'board': {
            'design_settings': {
                'defaults': {'copper_line_width': 0.2, 'copper_text_size_h': 1.5, 'copper_text_size_v': 1.5,
                             'copper_text_thickness': 0.3, 'silk_line_width': 0.12, 'silk_text_size_h': 0.8,
                             'silk_text_size_v': 0.8, 'silk_text_thickness': 0.15, 'board_outline_line_width': 0.1},
                'rule_severities': severities,
                'rules': {'min_clearance': 0.15, 'min_connection': 0.0, 'min_copper_edge_clearance': 0.5,
                          'min_hole_clearance': 0.25, 'min_hole_to_hole': 0.25, 'min_microvia_diameter': 0.2,
                          'min_microvia_drill': 0.1, 'min_resolved_spokes': 2, 'min_silk_clearance': 0.0,
                          'min_text_height': 0.8, 'min_text_thickness': 0.08, 'min_through_hole_diameter': 0.3,
                          'min_track_width': 0.15, 'min_via_annular_width': 0.1, 'min_via_diameter': 0.5,
                          'solder_mask_to_copper_clearance': 0.0, 'use_height_for_length_calcs': True},
                'track_widths': [0.0, SIG, 0.25, THIN, PWR],
                'via_dimensions': [{'diameter': 0.0, 'drill': 0.0}, {'diameter': VIA_D, 'drill': VIA_DRILL}],
                'drc_exclusions': [],
            },
        },
        'net_settings': {
            'classes': [{'name': 'Default', 'clearance': 0.15, 'track_width': SIG, 'via_diameter': VIA_D,
                         'via_drill': VIA_DRILL, 'microvia_diameter': 0.3, 'microvia_drill': 0.1,
                         'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25, 'diff_pair_width': 0.2,
                         'bus_width': 12, 'wire_width': 6, 'line_style': 0, 'priority': 2147483647,
                         'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)'}],
            'meta': {'version': 4},
            'net_colors': None, 'netclass_assignments': None, 'netclass_patterns': [],
        },
    }


def write_project():
    base = json.loads(Path('/usr/share/kicad/template/kicad.kicad_pro').read_text()) if not PRO.exists() \
        else json.loads(PRO.read_text())
    base['meta']['filename'] = PRO.name
    s = project_settings()
    base.setdefault('board', {}).setdefault('design_settings', {}).update(s['board']['design_settings'])
    base['net_settings'] = s['net_settings']
    base.setdefault('erc', {})
    base['erc'].setdefault('rule_severities', {})
    base.setdefault('schematic', {}).setdefault('legacy_lib_dir', '')
    PRO.write_text(json.dumps(base, indent=2, sort_keys=True) + '\n')


def outline(board):
    """Rectangle with all four corners rounded."""
    x1, y1, x2, y2, r = X0, Y0, X0 + W, Y0 + H, RADIUS
    edge = layer(board, 'Edge.Cuts')
    lines = [((x1 + r, y1), (x2 - r, y1)), ((x2, y1 + r), (x2, y2 - r)),
             ((x2 - r, y2), (x1 + r, y2)), ((x1, y2 - r), (x1, y1 + r))]
    for a, b in lines:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a)), s.SetEnd(mm(*b)), s.SetLayer(edge), s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)
    k = 1 - 0.70710678
    arcs = [((x2 - r, y1), (x2 - r * k, y1 + r * k), (x2, y1 + r)),
            ((x2, y2 - r), (x2 - r * k, y2 - r * k), (x2 - r, y2)),
            ((x1 + r, y2), (x1 + r * k, y2 - r * k), (x1, y2 - r)),
            ((x1, y1 + r), (x1 + r * k, y1 + r * k), (x1 + r, y1))]
    for a, m_, b in arcs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(mm(*a), mm(*m_), mm(*b)), s.SetLayer(edge), s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)


def zone(board, name, net):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer(board, name))
    z.SetNet(net)
    z.SetZoneName('GND_' + name.split('.')[0])
    o = z.Outline()
    o.NewOutline()
    for x, y in ((X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)):
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    z.SetLocalClearance(pcbnew.FromMM(0.25))
    z.SetMinThickness(pcbnew.FromMM(0.2))
    z.SetThermalReliefGap(pcbnew.FromMM(0.3))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(0)
    board.Add(z)
    return z


def text(board, s, x, y, size, justify):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(mm(size, size))
    t.SetTextThickness(pcbnew.FromMM(0.15 if size < 1 else 0.18))
    t.SetHorizJustify({'left': pcbnew.GR_TEXT_H_ALIGN_LEFT, 'center': pcbnew.GR_TEXT_H_ALIGN_CENTER,
                       'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT}[justify])
    t.SetPosition(mm(x, y))
    board.Add(t)


def native_netlist():
    """ref -> {pin: net} and ref -> {field: value} from kicad-cli's netlist."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'net.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out),
                        str(HW / (D.PROJECT + '.kicad_sch'))], check=True, capture_output=True)
        root = ET.parse(out).getroot()
    pins, fields = {}, {}
    for c in root.find('components'):
        fields[c.get('ref')] = {f.get('name'): f.text or '' for f in c.find('fields')}
    for n in root.find('nets'):
        for node in n:
            pins.setdefault(node.get('ref'), {})[node.get('pin')] = n.get('name')
    return pins, fields


def build():
    write_project()
    sch_pins, sch_fields = native_netlist()
    board = pcbnew.NewBoard(str(PCB))
    board.SetCopperLayerCount(2)
    tb = board.GetTitleBlock()
    tb.SetTitle(D.TITLE), tb.SetRevision(D.REV), tb.SetCompany('Big Modular')
    tb.SetComment(0, 'Circuit derived from Bread Modular UPDIProgrammer 0.3.0')
    tb.SetComment(1, 'Generated by opt/updi-programmer/tools/build_pcb.py')
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)

    nets = {}
    for ref, pins in sorted(sch_pins.items()):
        for pin, n in sorted(pins.items()):
            if n not in nets:
                ni = pcbnew.NETINFO_ITEM(board, n)
                board.Add(ni)
                nets[n] = ni
            # design.py names map to the native local-label names (/NAME)
            intent = D.PARTS[ref]['pins'][pin]
            assert intent is None or n in (intent, '/' + intent), (ref, pin, intent, n)
    for n in list(nets):
        if n.startswith('/'):
            nets[n[1:]] = nets[n]

    sch_text = (HW / (D.PROJECT + '.kicad_sch')).read_text()
    for ref, part in D.PARTS.items():
        if ref.startswith('#'):
            continue
        fp = pcbnew.FootprintLoad(str(FPLIB), part['fp'])
        assert fp, part['fp']
        fp.SetFPID(pcbnew.LIB_ID(D.LIB, part['fp']))
        fp.SetReference(ref)
        fp.SetValue(part['value'])
        sym_uuid = uid('sym', ref)
        assert sym_uuid in sch_text, ref
        fp.SetPath(pcbnew.KIID_PATH('/' + sym_uuid))
        fp.SetSheetname('/')
        fp.SetSheetfile(D.PROJECT + '.kicad_sch')
        for name, value in sch_fields[ref].items():
            if name in ('Reference', 'Value', 'Footprint'):
                continue
            f = fp.GetField(name)
            if f is None:
                f = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), name)
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
                fp.Add(f)
            f.SetText(value)
        x, y, r = PLACE[ref]
        fp.SetPosition(mm(x, y))
        fp.SetOrientationDegrees(r)
        fp.Reference().SetVisible(False)
        # J1 is the user's own hand-soldered header: in the BOM, not in the
        # JLCPCB CPL (the shared exporter drops refs excluded from pos files).
        fp.SetExcludedFromPosFiles(ref == 'J1')
        for pad in fp.Pads():
            n = pad.GetNumber()
            if not n:
                continue
            pad.SetNet(nets[sch_pins[ref][n]])
        board.Add(fp)

    for net, width, lname, pts in TRACKS:
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(mm(*a)), t.SetEnd(mm(*b))
            t.SetWidth(pcbnew.FromMM(width))
            t.SetLayer(layer(board, lname))
            t.SetNet(nets[net])
            board.Add(t)
    for net, (x, y) in VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetPosition(mm(x, y))
        v.SetWidth(pcbnew.FromMM(VIA_D))
        v.SetDrill(pcbnew.FromMM(VIA_DRILL))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[net])
        board.Add(v)

    outline(board)
    for s in SILK:
        text(board, *s)
    zones = [zone(board, 'F.Cu', nets['GND']), zone(board, 'B.Cu', nets['GND'])]
    pcbnew.ZONE_FILLER(board).Fill(zones)
    pcbnew.SaveBoard(str(PCB), board)
    write_project()  # SaveBoard may rewrite the project; keep the reviewed rules
    # The in-script fill above runs before the .kicad_pro rules are loaded, so it
    # ignores edge/hole clearance. Refill natively with the project rules and save.
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '-o', str(Path(tmp) / 'drc.rpt'),
                        str(PCB)], check=True, capture_output=True)
    write_project()
    print('wrote', PCB.name, len(board.GetFootprints()), 'footprints', len(board.GetTracks()), 'tracks/vias')


if __name__ == '__main__':
    build()
