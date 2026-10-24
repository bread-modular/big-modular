"""Read-only USB routing regression checks (in addition to native ERC/DRC).

Run from the repository root: python3 -B modules/usb-audio/tools/check_usb.py
Optional --board selects a different native PCB (and its adjacent .kicad_pro).
Checks each USB-C orientation, not misleading total lengths of branched nets.
No routing, field solver, supplier signoff, eye test or USB certification occurs.
"""
import argparse
from collections import defaultdict
import heapq
import json
import math
from pathlib import Path
import sys

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE.parents[1] / 'opt/kicad-tools'))
import native

CONNECTOR = {'P': 'Net-(J101-D+-PadA6)', 'M': 'Net-(J101-D--PadA7)'}
MCU = {'P': '/USB_DP', 'M': '/USB_DM'}

def xy(v):
    return v.x, v.y

def shortest(board, net, start, end):
    """Endpoint graph; require native DRC separately for actual copper connectivity.

    Tracks in this hand-routed subset terminate at every junction. Through-via
    edges use nominal board thickness; package-internal delay is not included.
    """
    graph = defaultdict(list)
    for t in board.GetTracks():
        if t.GetNetname() != net:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            a = (*xy(t.GetPosition()), pcbnew.F_Cu)
            b = (*xy(t.GetPosition()), pcbnew.B_Cu)
            length = pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness())
            is_via = 1
        else:
            a, b = (*xy(t.GetStart()), t.GetLayer()), (*xy(t.GetEnd()), t.GetLayer())
            length, is_via = pcbnew.ToMM(t.GetLength()), 0
        graph[a].append((b, length, is_via))
        graph[b].append((a, length, is_via))
    source = (*xy(start.GetPosition()), start.GetLayer())
    target = (*xy(end.GetPosition()), end.GetLayer())
    queue, visited = [(0., 0, source)], set()
    while queue:
        length, vias, node = heapq.heappop(queue)
        if node == target:
            return {'length_with_vias_mm': length, 'signal_vias': vias,
                    'planar_mm': length - vias * pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness())}
        if node in visited:
            continue
        visited.add(node)
        for other, distance, via in graph[node]:
            if other not in visited:
                heapq.heappush(queue, (length + distance, vias + via, other))
    raise ValueError(f'No endpoint path for {net}: {start.GetNumber()} -> {end.GetNumber()}')


def inspect(path):
    board = pcbnew.LoadBoard(str(path))
    pads = {(f.GetReference(), p.GetNumber()): p for f in board.GetFootprints() for p in f.Pads()}
    errors, orientations = [], {}
    for orient, pp, pm in [('A', 'A6', 'A7'), ('B', 'B6', 'B7')]:
        paths = {}
        for polarity, pin, esd_in, esd_out, mcu_pin in [('P', pp, '3', '4', '59'), ('M', pm, '1', '6', '58')]:
            a = shortest(board, CONNECTOR[polarity], pads['J101', pin], pads['U102', esd_in])
            b = shortest(board, MCU[polarity], pads['U102', esd_out], pads['U101', mcu_pin])
            paths[polarity] = {'connector_to_esd': a, 'esd_to_mcu': b,
                              'total_mm': a['length_with_vias_mm'] + b['length_with_vias_mm']}
            if a['signal_vias'] != 2 or b['signal_vias'] != 0:
                errors.append(f'{orient}/{polarity}: expected 2 connector transitions, 0 MCU transitions')
        skew = abs(paths['P']['total_mm'] - paths['M']['total_mm'])
        if skew > .5:
            errors.append(f'{orient}: path mismatch {skew:.4f} mm exceeds reviewed 0.5 mm bound')
        orientations[orient] = dict(paths, mismatch_mm=skew)
    project = json.loads(path.with_suffix('.kicad_pro').read_text())
    nc = project['net_settings']
    expected_class = {'track_width': .4, 'diff_pair_width': .3, 'diff_pair_gap': .2, 'clearance': .2}
    usb_class = next((c for c in nc['classes'] if c['name'] == 'USB_HS'), {})
    if any(usb_class.get(k) != v for k, v in expected_class.items()):
        errors.append('USB_HS class geometry missing or changed')
    assigned = {r['pattern'] for r in nc['netclass_patterns'] if r['netclass'] == 'USB_HS'}
    if not ((set(CONNECTOR.values()) | set(MCU.values())) <= assigned):
        errors.append('USB_HS must cover both sides of U102')
    ast = native.kicad.parse_sexpr(path.read_text())
    setup = native.kicad.child(ast, 'setup')
    stack = native.kicad.child(setup, 'stackup') or []
    layers = {n[1]: n for n in stack[1:] if isinstance(n, list) and n[0] == 'layer'}
    for name, thickness in [('F.Cu', .035), ('In1.Cu', .0152), ('In2.Cu', .0152), ('B.Cu', .035),
                            ('dielectric 1', .2104), ('dielectric 2', 1.065), ('dielectric 3', .2104)]:
        value = native.kicad.child(layers.get(name, []), 'thickness')
        if not value or abs(float(value[1]) - thickness) > .000001:
            errors.append(f'Stackup {name}: expected {thickness} mm')
    for name, er in [('dielectric 1', 4.4), ('dielectric 2', 4.6), ('dielectric 3', 4.4)]:
        value = native.kicad.child(layers.get(name, []), 'epsilon_r')
        if not value or float(value[1]) != er:
            errors.append(f'Stackup {name}: expected Er={er}')
    zones = list(board.Zones())
    ground = {layer: [z.GetFilledPolysList(layer) for z in zones if z.GetNetname() == 'GND' and z.IsOnLayer(layer)]
              for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu)}
    if not any(z.GetZoneName() == 'USB_HS_GND_REFERENCE' and z.GetNetname() == 'GND' for z in zones):
        errors.append('Missing In2 USB ground reference island')
    usb_nets = set(CONNECTOR.values()) | set(MCU.values())
    usb_vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() in usb_nets]
    sample_count = 0
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() not in usb_nets:
            continue
        if t.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
            errors.append('USB signal track on an inner plane')
            continue
        if pcbnew.ToMM(t.GetWidth()) not in (.3, .4):
            errors.append(f'Unreviewed USB width: {pcbnew.ToMM(t.GetWidth())}')
        layer = pcbnew.In1_Cu if t.GetLayer() == pcbnew.F_Cu else pcbnew.In2_Cu
        ax, ay = xy(t.GetStart()); bx, by = xy(t.GetEnd())
        length = math.hypot(bx-ax, by-ay)
        steps = max(1, math.ceil(length/50000))  # 0.05 mm longitudinal sampling
        for i in range(steps+1):
            x, y = ax+(bx-ax)*i/steps, ay+(by-ay)*i/steps
            # Expected signal-via antipads are not plane splits. Omit only a
            # bounded 0.7mm transition neighborhood; check all other trace edges.
            if any(math.hypot(x-v.GetPosition().x, y-v.GetPosition().y) <= 700000 for v in usb_vias):
                continue
            for off in (-t.GetWidth()/2, 0, t.GetWidth()/2):
                p = pcbnew.VECTOR2I(round(x-(by-ay)*off/length), round(y+(bx-ax)*off/length))
                sample_count += 1
                if not any(poly.Contains(p) for poly in ground[layer]):
                    errors.append(f'No ground under {t.GetNetname()} {pcbnew.ToMM(p.x):.3f},{pcbnew.ToMM(p.y):.3f}')
                    break
    h, er, copper = .2104, 4.4, .035
    def z0(w):
        return 87/math.sqrt(er+1.41)*math.log(5.98*h/(.8*w+copper))
    return {'pass': not errors, 'errors': sorted(set(errors)), 'orientations': orientations,
            'reference_samples': sample_count,
            'impedance_estimate_ohms': {'single_0p40mm': z0(.4),
                'differential_0p30mm_gap_0p20mm': 2*z0(.3)*(1-.48*math.exp(-.96*.2/h))},
            'limits': 'IPC-2141-style nominal uncoated estimates, not a field solution. Pad escapes, connector branches, vias, solder mask and package internals require supplier/bench validation. No USB certification claim.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board', type=Path, default=MODULE/'hardware/usb-audio-mcu.kicad_pcb')
    args = ap.parse_args()
    report = inspect(args.board)
    print(json.dumps(report, indent=2))
    return 0 if report['pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
