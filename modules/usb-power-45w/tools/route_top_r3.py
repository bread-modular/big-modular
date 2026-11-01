#!/usr/bin/env python3
"""R3: finish the manual routing of the TOP board, one reviewed batch at a time.

  python3 -B tools/route_top_r3.py ops <batch> <out.json>   # emit the shared `pcb plan` ops
  python3 -B tools/route_top_r3.py apply <batch>            # route_r2 plan -> apply -> verified write-back
  python3 -B tools/route_top_r3.py audit [reports-dir]      # DRC/parity + geometry audit of the canonical top
  python3 -B tools/route_top_r3.py view <png> [x0 x1 y0 y1] [layers]   # native-frame inspection render

No router: every track, via and zone below is written by hand. Coordinates here are NATIVE board
mm (x right, y down, as in pcbnew) - route_r2 batches use the stack YZ frame, so each batch is
emitted here in native mm with the route_r2 UUID scheme and handed to the unchanged route_r2
apply/writeback (shared opt/kicad-tools pcb plan/apply; /tmp backup; raw files in research/r2/route/).
Via keys are prefixed with the batch id so every via UUID stays unique across batches.
Layers: F signal + local power pours, In1 solid GND (no tracks), In2 VIN plane, B signal + heat.
"""
import json
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import route_r2 as r2  # noqa: E402

PCB = r2.st.board_file('top')
VP = (0.6, 0.3)     # power via (in groups)
VS = (0.5, 0.3)     # signal via

B = {}              # batch -> spec in native mm


def uid(key):
    return r2.uid('top', key)


def emit(batch):
    """Shared `pcb plan` ops for one batch, native mm, same UUID scheme as route_r2 (via keys are
    '<batch>/<key>', so earlier vias stay addressable). Optional reviewed placement refinements
    ('moves': [(ref, (x, y) | None, rotation | None)]) come first. Track ends: ('pad', ref, num),
    ('padu', pad-uuid) for repeated pad numbers, ('via', key) | ('via', '<batch>/<key>'),
    ('trk', '<batch>', polyline index, segment index, (x, y)) = branch on an earlier straight segment."""
    s = B[batch]
    ops, nets = [], {}

    def n(x):
        if x not in nets:
            nets[x] = r2.board_net('top', x)
        return nets[x]

    def at(q):
        return [round(q[0], 4), round(q[1], 4)]
    for key in s.get('delete_vias', []):          # reviewed removal of own earlier vias ('<batch>/<key>')
        ops.append({'op': 'delete_item', 'uuid': uid(f'via/{key}'), 'expected_kind': 'via'})
    for b, i, nseg in s.get('deletes', []):     # reviewed rip-up of own earlier polylines (all segments)
        op = uid(f'{b}/trk/{i}')
        for seg in range(nseg):
            ops.append({'op': 'delete_item', 'uuid': op if seg == 0 else str(r2.uuid.uuid5(r2.uuid.UUID(op), str(seg))),
                        'expected_kind': 'track'})
    for ref, pos, rot in s.get('moves', []):
        if pos is not None:
            ops.append({'op': 'move_footprint', 'target': {'ref': ref}, 'at': at(pos)})
        if rot is not None:
            ops.append({'op': 'rotate_footprint', 'target': {'ref': ref}, 'rotation_deg': rot})
    for i, (layer, net, poly, conn) in enumerate(s.get('zones', [])):
        ops.append({'op': 'add_zone', 'uuid': uid(f'{batch}/zone/{i}'), 'net': n(net), 'layer': layer,
                    'polygon': [at(q) for q in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.25,
                    'pad_connection': conn})
    for k, (net, xy, *size) in s.get('vias', {}).items():
        d, dr = size[0] if size else VP
        ops.append({'op': 'add_via', 'uuid': uid(f'via/{batch}/{k}'), 'net': n(net), 'at': at(xy),
                    'diameter_mm': d, 'drill_mm': dr})

    def end(e):
        if e[0] == 'pad':
            return {'pad': {'ref': e[1], 'number': e[2]}}
        if e[0] == 'padu':
            return {'uuid': e[1]}
        if e[0] == 'via':
            return {'uuid': uid('via/' + (e[1] if '/' in e[1] else f'{batch}/{e[1]}'))}
        if e[0] == 'via0':      # route_r2 T1 via keys (no batch prefix)
            return {'uuid': uid(f'via/{e[1]}')}
        _, b, i, seg, q = e
        op = uid(f'{b}/trk/{i}')
        return {'track': op if seg == 0 else str(r2.uuid.uuid5(r2.uuid.UUID(op), str(seg))), 'at': at(q)}
    for i, (net, layer, w, a, wps, b) in enumerate(s.get('tracks', [])):
        ops.append({'op': 'add_polyline', 'uuid': uid(f'{batch}/trk/{i}'), 'net': n(net), 'layer': layer,
                    'width_mm': w, 'start': end(a), 'waypoints': [at(q) for q in wps], 'end': end(b)})
    return {'schema_version': 1, 'operations': ops}


def apply(batch):
    """route_r2.apply with this module's emit; footprints listed in the batch 'moves' may change
    (position/rotation only - pads, nets and fields are asserted by the shared worker)."""
    r2.st.refuse_replay(f'route_top_r3.py apply {batch}')
    r2.emit = lambda board, b: emit(b)
    moved = {m[0] for m in B[batch].get('moves', [])}
    deleted = {o['uuid'] for o in emit(batch)['operations'] if o['op'] == 'delete_item'}
    if moved or deleted:
        orig = r2.writeback

        def wb(board, cand, src, work):
            import pcbnew
            old = pcbnew.LoadBoard(str(src))
            keep = {f.m_Uuid.AsString(): (f.GetPosition().x, f.GetPosition().y, f.GetOrientationDegrees())
                    for f in old.GetFootprints()}
            rc = _writeback_moves(board, cand, src, work, moved, orig, deleted)
            new = pcbnew.LoadBoard(str(src))
            ch = sorted(f.GetReference() for f in new.GetFootprints()
                        if keep[f.m_Uuid.AsString()] != (f.GetPosition().x, f.GetPosition().y, f.GetOrientationDegrees()))
            print('moved footprints:', ch) if moved else None
            assert set(ch) <= moved, ch
            return rc
        r2.writeback = wb
    rc = r2.apply('top', batch)
    work = sorted((MOD / 'research/r2/route').glob(f'top-{batch}-*'))[-1]
    res = json.loads((work / 'result.json').read_text()) if (work / 'result.json').exists() else {}
    if rc and res.get('status') == 'accepted' and not (work / 'writeback.json').exists():
        # Accepted (zero opens) but the shared `promote` refuses the board's ${KICAD10_3DMODEL_DIR} model
        # tokens (it only re-resolves staged _kicad_models copies): use the same verified write-back.
        print('promote refused model bindings; verified write-back of the accepted candidate instead')
        cand = Path('/tmp/usbpower45-r2-route') / work.name / 'cand'
        rc = r2.writeback('top', cand, PCB, work)
    return rc


def _writeback_moves(board, cand, src, work, moved, orig, deleted=frozenset()):
    """Same as route_r2.writeback, but the footprint identity check excludes the reviewed moves and
    exactly the reviewed deleted track UUIDs may disappear."""
    import re
    import shutil
    import pcbnew
    cpcb = next(cand.glob('inputs/**/' + src.name))
    ctext, stext = cpcb.read_text(), src.read_text()
    pat = re.compile(r'\(model "([^"]*)"')
    cm, sm = pat.findall(ctext), pat.findall(stext)
    assert len(cm) == len(sm) and all(Path(a).name == Path(b).name for a, b in zip(cm, sm)), 'model token map'
    it = iter(sm)
    out = pat.sub(lambda m_: '(model "%s"' % next(it), ctext)
    tmp = work / 'writeback.kicad_pcb'
    tmp.write_text(out)
    old, new = pcbnew.LoadBoard(str(src)), pcbnew.LoadBoard(str(tmp))

    def fps(b):
        return {f.m_Uuid.AsString(): (f.GetReference(),
                                      None if f.GetReference() in moved else (f.GetPosition().x, f.GetPosition().y,
                                                                              f.GetOrientationDegrees()),
                                      tuple((p.GetNumber(), p.GetNetname()) for p in f.Pads()),
                                      tuple(sorted((x.GetName(), x.GetText()) for x in f.GetFields())))
                for f in b.GetFootprints()}

    def copper(b):
        o = {}
        for t in b.GetTracks():
            o[t.m_Uuid.AsString()] = (t.GetClass(), t.GetNetname(), t.GetStart().x, t.GetStart().y, t.GetEnd().x,
                                      t.GetEnd().y, t.GetWidth(pcbnew.F_Cu) if t.GetClass() == 'PCB_VIA' else t.GetWidth(),
                                      t.GetLayer())
        for z in b.Zones():
            o[z.m_Uuid.AsString()] = ('ZONE', z.GetNetname(), z.GetFirstLayer(), z.GetIsRuleArea())
        return o
    assert fps(old) == fps(new), 'footprints changed beyond the reviewed moves'
    co, cn = copper(old), copper(new)
    assert set(co) - set(cn) == set(deleted), ('deleted set', set(co) - set(cn), deleted)
    assert all(cn.get(k) == v for k, v in co.items() if k not in deleted), 'earlier copper changed'
    added = sorted(set(cn) - set(co))
    shutil.copy(tmp, src)
    print('written back:', len(added), 'items added;', len(deleted), 'deleted;', len(cn), 'copper items total')
    (work / 'writeback.json').write_text(json.dumps({'added': len(added), 'deleted': sorted(deleted), 'total': len(cn),
                                                     'moved': sorted(moved)}))
    return 0


# =============================================================================================
# Batches (native mm). Ends: ('pad', ref, num) | ('via', key) (own batch) | ('via', 'T2/key')
# =============================================================================================
# ---------------------------------------------------------------------------------------------
# T2: U2 (+12 V TPS62933F) local stage. SOT-583 pins 1-4 (GND/MAIN_OK/VIN/GND) on the right,
# 5-8 (SW/BST/SS/FB) on the left. VIN pin 3 and GND pin 4 run straight to the 100 nF C8 (input
# loop ~2 mm), F VIN pour joins C8/C7/C6 (5 vias to the In2 VIN plane), F GND pour joins C8/C7/C6 and
# the C11-C14 output-cap returns (vias to In1). SW: small F pour pin 5 - L1.1 - C10.2 (BOOT cap);
# BST pin 6 -> C10.1. MAIN_OK (pin 2, between VIN and GND) escapes east then south to a via.
# RT pin 1 (= GND) -> C9.2 -> GND via. SS pin 7 down the channel between the pin columns to C9.1;
# FB pin 8 west to R9/R8 (FB pads ~2 mm from the SW copper).
B['T2-U2-stage'] = {
    'zones': [
        ('F.Cu', 'U2-SW', [(63.9, 75.8), (66.75, 75.8), (66.75, 77.5), (63.9, 77.5)], 'solid'),
        ('F.Cu', 'VIN', [(68.55, 78.0), (76.3, 78.0), (76.3, 80.85), (68.55, 80.85)], 'solid'),
        ('F.Cu', 'GND', [(68.35, 76.05), (74.15, 76.05), (74.15, 63.4), (77.0, 63.4), (77.0, 72.3),
                         (76.3, 72.3), (76.3, 77.7), (68.35, 77.7)], 'solid'),
    ],
    'vias': {
        'mo1': ('MAIN_OK', (68.15, 80.05), VS),
        'vin1': ('VIN', (70.3, 79.55)), 'vin2': ('VIN', (70.3, 80.45)), 'vin3': ('VIN', (73.0, 79.55)),
        'vin4': ('VIN', (73.0, 80.45)), 'vin5': ('VIN', (75.8, 79.6)),
        'g1': ('GND', (70.3, 77.1)), 'g2': ('GND', (73.0, 77.1)), 'g3': ('GND', (76.6, 65.9)),
        'g4': ('GND', (76.6, 68.3)), 'g5': ('GND', (76.6, 70.7)), 'g6': ('GND', (67.6, 82.1)),
        'g7': ('GND', (62.5, 79.1)),
    },
    'tracks': [
        ('VIN', 'F.Cu', 0.3, ('pad', 'U2', '3'), [(68.65, 78.025)], ('pad', 'C8', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'U2', '4'), [(68.65, 77.525)], ('pad', 'C8', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'U2', '1'), [(67.49, 80.3)], ('pad', 'C9', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C9', '2'), [], ('via', 'g6')),
        ('MAIN_OK', 'F.Cu', 0.2, ('pad', 'U2', '2'), [(68.15, 78.525)], ('via', 'mo1')),
        ('U2-SW', 'F.Cu', 0.3, ('pad', 'U2', '5'), [(66.01, 75.6)], ('pad', 'L1', '1')),
        ('U2-BST', 'F.Cu', 0.25, ('pad', 'U2', '6'), [(65.0, 78.025)], ('pad', 'C10', '1')),
        ('U2-SS', 'F.Cu', 0.2, ('pad', 'U2', '7'), [(66.75, 78.525), (66.75, 80.3)], ('pad', 'C9', '1')),
        ('U2-FB', 'F.Cu', 0.2, ('pad', 'U2', '8'), [(65.2, 79.025)], ('pad', 'R9', '1')),
        ('U2-FB', 'F.Cu', 0.2, ('pad', 'R9', '1'), [], ('pad', 'R8', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R9', '2'), [], ('via', 'g7')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T3: P12_RAW west network. F pour on L1.2 + C11-C14.1 (output node), B P12_RAW pour under the
# whole west part (3 vias from the F pour, C39.1, C34.1, R19/R8). D2 (clamp) and C34 (can) on a
# 0.8/1.2 mm F run from L1.2, D5/R19 power LED, local GND vias (C34.2, D2.2/D5.1).
B['T3-P12RAW-west'] = {
    'zones': [
        ('F.Cu', 'P12_RAW', [(63.9, 63.4), (73.5, 63.4), (73.5, 72.95), (68.3, 72.95), (68.3, 71.5), (63.9, 71.5)],
         'solid'),
        ('B.Cu', 'P12_RAW', [(50.9, 63.4), (76.3, 63.4), (76.3, 84.3), (63.9, 84.3), (63.9, 82.7), (50.9, 82.7)],
         'solid'),
    ],
    'vias': {
        'p1': ('P12_RAW', (73.3, 65.875)), 'p2': ('P12_RAW', (73.3, 68.275)), 'p3': ('P12_RAW', (73.3, 70.675)),
        'pc39': ('P12_RAW', (75.8, 76.55)), 'pa': ('P12_RAW', (61.6, 80.7)),
        'pc34a': ('P12_RAW', (52.0, 80.6)), 'pc34b': ('P12_RAW', (53.5, 80.6)),
        'gc34a': ('GND', (57.2, 80.6)), 'gc34b': ('GND', (58.8, 80.6)), 'gd5': ('GND', (59.0, 75.9)),
    },
    'tracks': [
        ('P12_RAW', 'F.Cu', 0.8, ('pad', 'L1', '2'), [(63.6, 67.3), (61.0, 71.95), (54.0, 71.95)], ('pad', 'D2', '1')),
        ('P12_RAW', 'F.Cu', 1.2, ('pad', 'D2', '1'), [], ('pad', 'C34', '1')),
        ('P12_RAW', 'F.Cu', 0.6, ('pad', 'C34', '1'), [], ('via', 'pc34a')),
        ('P12_RAW', 'F.Cu', 0.6, ('pad', 'C34', '1'), [], ('via', 'pc34b')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C34', '2'), [], ('via', 'gc34a')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C34', '2'), [], ('via', 'gc34b')),
        ('GND', 'F.Cu', 0.3, ('pad', 'D2', '2'), [(58.9, 74.763)], ('pad', 'D5', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'D5', '1'), [], ('via', 'gd5')),
        ('D5-A', 'F.Cu', 0.25, ('pad', 'R19', '2'), [(61.0, 76.0), (61.0, 73.188)], ('pad', 'D5', '2')),
        ('P12_RAW', 'F.Cu', 0.3, ('pad', 'R19', '1'), [(61.6, 79.4)], ('via', 'pa')),
        ('P12_RAW', 'F.Cu', 0.3, ('via', 'pa'), [(61.6, 81.775)], ('pad', 'R8', '2')),
        ('P12_RAW', 'F.Cu', 0.4, ('pad', 'C39', '1'), [], ('via', 'pc39')),
        ('P12_RAW', 'F.Cu', 0.6, ('pad', 'C11', '1'), [], ('via', 'p1')),
        ('P12_RAW', 'F.Cu', 0.6, ('pad', 'C12', '1'), [], ('via', 'p2')),
        ('P12_RAW', 'F.Cu', 0.6, ('pad', 'C13', '1'), [], ('via', 'p3')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T4: U3 (+5 V TPS62933F) local stage + P5_RAW B pour. Pins 1-4 (RT/MAIN_OK/VIN/GND) face north,
# 5-8 (SW/BST/SS/FB) south. VIN pin 3 / GND pin 4 straight to the 100 nF C17; F VIN pour C17/C15/C16
# with 3 In2 vias; F GND pour on their returns with 2 In1 vias. SW F pour pin 5 - C19.2 - L2.1 under
# the inductor body; BST pin 6 -> C19.1; SS between the pin rows to C18; FB pin 8 -> R12/R11 (away
# from SW); RT -> R10. MAIN_OK: U3 via mo2 -> B (south, bottom edge y100.75, up x64.75) -> U2 via mo1.
# B P5_RAW pour (x73.9-107.4, y87.5-100.1) fed by 3 vias at L2.2; D3 clamp on a 0.8 mm F run to L2.2.
B['T4-U3-stage'] = {
    'zones': [
        ('F.Cu', 'U3-SW', [(73.4, 97.75), (79.62, 97.75), (79.62, 98.35), (79.25, 98.7), (79.25, 100.5),
                           (77.75, 100.5), (77.75, 99.1), (73.4, 99.1)], 'solid'),
        ('F.Cu', 'VIN', [(79.4, 93.55), (80.55, 93.55), (80.55, 88.7), (82.5, 88.7), (82.5, 95.25), (79.4, 95.25)],
         'solid'),
        ('F.Cu', 'GND', [(76.95, 88.7), (79.05, 88.7), (79.05, 95.45), (76.95, 95.45)], 'solid'),
        ('B.Cu', 'P5_RAW', [(73.9, 87.5), (107.4, 87.5), (107.4, 100.1), (73.9, 100.1)], 'solid'),
    ],
    'vias': {
        'mo2': ('MAIN_OK', (80.75, 95.6), VS),
        'v1': ('VIN', (82.15, 90.0)), 'v2': ('VIN', (82.15, 92.3)), 'v3': ('VIN', (81.3, 94.3)),
        'gv1': ('GND', (77.35, 91.1)), 'gv2': ('GND', (78.45, 93.7)), 'gr10': ('GND', (83.35, 92.0)),
        'gc18': ('GND', (85.1, 97.6)), 'gd3': ('GND', (70.2, 87.6)),
        'l1': ('P5_RAW', (74.3, 89.3)), 'l2': ('P5_RAW', (74.3, 90.6)), 'l3': ('P5_RAW', (74.3, 91.9)),
        'pr11': ('P5_RAW', (85.1, 99.7)), 'pc42': ('P5_RAW', (77.9, 88.0)),
    },
    'tracks': [
        ('VIN', 'F.Cu', 0.3, ('pad', 'U3', '3'), [(80.0, 94.9)], ('pad', 'C17', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'U3', '4'), [(79.5, 95.6)], ('pad', 'C17', '2')),
        ('MAIN_OK', 'F.Cu', 0.2, ('pad', 'U3', '2'), [(80.5, 96.0)], ('via', 'mo2')),
        ('MAIN_OK', 'B.Cu', 0.2, ('via', 'mo2'), [(80.75, 100.75), (64.75, 100.75), (64.75, 81.0), (68.15, 81.0)],
         ('via', 'T2-U2-stage/mo1')),
        ('U3-RT', 'F.Cu', 0.2, ('pad', 'U3', '1'), [(81.6, 96.535), (82.5, 95.6)], ('pad', 'R10', '1')),
        ('U3-SS', 'F.Cu', 0.2, ('pad', 'U3', '7'), [(80.5, 97.275)], ('pad', 'C18', '1')),
        ('U3-FB', 'F.Cu', 0.2, ('pad', 'U3', '8'), [(81.0, 98.875)], ('pad', 'R12', '1')),
        ('U3-FB', 'F.Cu', 0.2, ('pad', 'R12', '1'), [], ('pad', 'R11', '1')),
        ('U3-BST', 'F.Cu', 0.25, ('pad', 'U3', '6'), [], ('pad', 'C19', '1')),
        ('VIN', 'F.Cu', 0.6, ('via', 'v1'), [], ('pad', 'C16', '1')),
        ('VIN', 'F.Cu', 0.6, ('via', 'v2'), [], ('pad', 'C15', '1')),
        ('VIN', 'F.Cu', 0.6, ('via', 'v3'), [], ('pad', 'C17', '1')),
        ('GND', 'F.Cu', 0.6, ('via', 'gv1'), [], ('pad', 'C16', '2')),
        ('GND', 'F.Cu', 0.6, ('via', 'gv2'), [], ('pad', 'C15', '2')),
        ('GND', 'F.Cu', 0.3, ('via', 'gr10'), [], ('pad', 'R10', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C18', '2'), [], ('pad', 'R12', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C18', '2'), [], ('via', 'gc18')),
        ('GND', 'F.Cu', 0.6, ('pad', 'D3', '2'), [], ('via', 'gd3')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'L2', '2'), [], ('via', 'l1')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'L2', '2'), [], ('via', 'l2')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'L2', '2'), [], ('via', 'l3')),
        ('P5_RAW', 'F.Cu', 0.3, ('pad', 'R11', '2'), [], ('via', 'pr11')),
        ('P5_RAW', 'F.Cu', 0.4, ('pad', 'C42', '1'), [], ('via', 'pc42')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'D3', '1'), [(66.15, 88.3), (69.6, 89.3)], ('pad', 'L2', '2')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T5a: U6 (TPS16630 +12 V eFuse) input side and setting parts. Reviewed placement refinements (unrouted
# AI-placed SMD, recorded in docs/r3-top): R20 (P5_RAW->D6-A LED resistor) moved from between C6 and the
# U6 input pins to (72.6, 83.0) - its D6-A pad blocked the P12_RAW feed neck to U6 pins 1-3; D6, R37 and
# C37 turned 180 deg in place (D6-A faces R20; R37 RUN pad faces U6 pin 13 so P12_OK can leave between
# its pads; C37 DVDT pad faces U6 pin 10 so P12_OV passes between its pads). P12_RAW: F pour on pins
# 1-3 fed from the B P12_RAW pour by 4 vias, pin 6 joined under the NC pins 4/5. UV/OV dividers, DVDT,
# pin 9 GND -> EP, local GND vias.
B['T5a-U6-input'] = {
    'moves': [('R20', (72.6, 83.0), 0.0), ('D6', None, 180.0), ('R37', None, 180.0), ('C37', None, 180.0)],
    'zones': [
        ('F.Cu', 'P12_RAW', [(73.95, 81.15), (79.85, 81.15), (79.85, 83.62), (73.95, 83.62)], 'solid'),
    ],
    'vias': {
        'pf1': ('P12_RAW', (74.6, 82.0)), 'pf2': ('P12_RAW', (75.6, 82.0)), 'pf3': ('P12_RAW', (74.6, 83.0)),
        'pf4': ('P12_RAW', (75.6, 83.0)), 'pr38': ('P12_RAW', (73.7, 85.3)),
        'gd6': ('GND', (77.25, 83.65)), 'gc42': ('GND', (79.5, 87.95)), 'g31': ('GND', (82.3, 86.6)),
        'g33': ('GND', (84.4, 90.95)),
    },
    'tracks': [
        ('P12_RAW', 'F.Cu', 0.6, ('via', 'pf1'), [], ('via', 'pf2')),
        ('P12_RAW', 'F.Cu', 0.6, ('via', 'pf2'), [], ('pad', 'U6', '1')),
        ('P12_RAW', 'F.Cu', 0.6, ('via', 'pf3'), [], ('via', 'pf4')),
        ('P12_RAW', 'F.Cu', 0.6, ('via', 'pf4'), [], ('pad', 'U6', '1')),
        ('P12_RAW', 'F.Cu', 0.4, ('pad', 'U6', '1'), [], ('pad', 'U6', '3')),
        ('P12_RAW', 'F.Cu', 0.4, ('pad', 'U6', '6'), [(81.575, 83.95), (79.625, 83.95)], ('pad', 'U6', '3')),
        ('P12_RAW', 'F.Cu', 0.25, ('pad', 'R30', '1'), [(78.325, 83.9)], ('pad', 'U6', '1')),
        ('P12_RAW', 'F.Cu', 0.3, ('pad', 'R38', '1'), [], ('via', 'pr38')),
        ('P12_RAW', 'B.Cu', 0.4, ('via', 'pr38'), [], ('via', 'pf3')),
        ('D6-A', 'F.Cu', 0.25, ('pad', 'R20', '2'), [], ('pad', 'D6', '2')),
        ('P5_RAW', 'F.Cu', 0.3, ('pad', 'R20', '1'), [(66.15, 83.0)], ('pad', 'D3', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'D6', '1'), [], ('via', 'gd6')),
        ('P12_UV', 'F.Cu', 0.2, ('pad', 'U6', '7'), [(82.225, 84.3)], ('pad', 'R31', '1')),
        ('P12_UV', 'F.Cu', 0.2, ('pad', 'R31', '1'), [], ('pad', 'R30', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R31', '2'), [(82.5, 86.3)], ('via', 'g31')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C37', '2'), [], ('via', 'g31')),
        ('P12_OV', 'F.Cu', 0.2, ('pad', 'U6', '8'), [(82.875, 83.9), (83.6, 84.3), (83.6, 85.4), (84.2, 85.9),
                                                       (84.2, 87.4)], ('pad', 'R32', '2')),
        ('P12_OV', 'F.Cu', 0.2, ('pad', 'R32', '2'), [], ('pad', 'R33', '1')),
        ('P12_DVDT', 'F.Cu', 0.2, ('pad', 'U6', '10'), [(84.175, 84.0), (84.975, 84.8)], ('pad', 'C37', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'U6', '9'), [(83.525, 80.9)], ('padu', 'cedde933-62e6-5e8d-ae32-341542e3347d')),
        ('P12_OV_SER', 'F.Cu', 0.2, ('pad', 'R38', '2'), [(76.9, 85.875), (80.4, 85.875), (80.4, 87.6), (82.0, 87.6)],
         ('pad', 'R32', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C42', '2'), [], ('via', 'gc42')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R33', '2'), [], ('via', 'g33')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T5b: +12V from U6 (pins 18-20, NW corner) to XT1 pins 9-12. F +12V pour on pins 18-20 with C38/R36,
# 3 vias to a B +12V pour: west leg beside the U6 B thermal pad -> under the U6 input pins -> band
# y84.0-85.8 under XT1/U7 north row -> 4 vias up to an F pour on XT1 pins 9/11 (+ links to 10/12).
# D12 (+12V clamp) on an F run to its own via into the band. C38/R36/R37 grounds join to one via.
B['T5b-U6-12V'] = {
    'zones': [
        ('F.Cu', '+12V', [(76.55, 75.45), (79.85, 75.45), (79.85, 77.75), (76.55, 77.75)], 'solid'),
        ('B.Cu', '+12V', [(76.6, 75.4), (78.1, 75.4), (78.1, 81.65), (84.6, 81.65), (84.6, 84.0), (104.5, 84.0),
                          (104.5, 85.8), (76.6, 85.8)], 'solid'),
        ('F.Cu', '+12V', [(99.6, 80.4), (104.5, 80.4), (104.5, 85.7), (99.6, 85.7)], 'solid'),
    ],
    'vias': {
        't1': ('+12V', (77.15, 75.85)), 't2': ('+12V', (77.15, 76.75)), 't3': ('+12V', (77.15, 77.65)),
        'ta': ('+12V', (100.4, 84.65)), 'tb': ('+12V', (101.4, 84.65)), 'tc': ('+12V', (102.4, 84.65)),
        'td': ('+12V', (103.4, 84.65)), 'td12': ('+12V', (96.3, 85.0)),
        'g36': ('GND', (79.0, 71.9)),
    },
    'tracks': [
        ('+12V', 'F.Cu', 0.5, ('pad', 'C38', '1'), [], ('via', 't1')),
        ('+12V', 'F.Cu', 0.5, ('via', 't1'), [], ('via', 't2')),
        ('+12V', 'F.Cu', 0.5, ('via', 't2'), [], ('via', 't3')),
        ('+12V', 'F.Cu', 0.5, ('via', 't2'), [], ('pad', 'U6', '20')),
        ('+12V', 'F.Cu', 0.3, ('pad', 'R36', '1'), [], ('pad', 'C38', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R36', '2'), [], ('pad', 'C38', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C38', '2'), [], ('pad', 'R37', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R36', '2'), [], ('via', 'g36')),
        ('+12V', 'F.Cu', 0.8, ('pad', 'XT1', '9'), [], ('pad', 'XT1', '10')),
        ('+12V', 'F.Cu', 0.8, ('pad', 'XT1', '11'), [], ('pad', 'XT1', '12')),
        ('+12V', 'F.Cu', 0.8, ('pad', 'XT1', '9'), [], ('via', 'ta')),
        ('+12V', 'F.Cu', 0.8, ('via', 'ta'), [], ('via', 'tb')),
        ('+12V', 'F.Cu', 0.8, ('via', 'tb'), [], ('via', 'tc')),
        ('+12V', 'F.Cu', 0.8, ('via', 'tc'), [], ('via', 'td')),
        ('+12V', 'F.Cu', 0.8, ('pad', 'XT1', '11'), [], ('via', 'td')),
        ('+12V', 'F.Cu', 0.6, ('pad', 'D12', '1'), [(96.3, 88.4)], ('via', 'td12')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T6m: reviewed placement refinements for the logic pull-ups/bleeders (unrouted AI-placed 0603s):
# R35 (V3V3->P12_OK) and R44 (V3V3->P5_OK) go next to XT2 (x137.7, >= 2 mm from the XT2 posts), so
# V3V3 stays local to the header instead of two long runs across the board; R46 (second RUN
# pull-down, was isolated at the bottom edge) takes R35's old spot beside R37 (turned so its RUN pad
# faces the RUN run); R45 (+5V bleeder, was at the bottom edge) sits on the +5V band beside XT1 13-16.
# Local links: P12_OK pin 4 -> R35, V3V3 pin 6 -> R44 -> R35, P5_OK pin 5 -> R44, R46/R37 grounds.
B['T6m-pullups'] = {
    'moves': [('R35', (137.7, 69.865), 180.0), ('R44', (137.7, 72.405), 0.0), ('R46', (81.25, 73.075), 180.0),
              ('R45', (107.4, 85.2), 0.0)],
    'tracks': [
        ('P12_OK', 'F.Cu', 0.25, ('pad', 'XT2', '4'), [], ('pad', 'R35', '2')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'XT2', '6'), [], ('pad', 'R44', '1')),
        ('V3V3', 'F.Cu', 0.25, ('pad', 'R44', '1'), [], ('pad', 'R35', '1')),
        ('P5_OK', 'F.Cu', 0.25, ('pad', 'XT2', '5'), [(131.0, 73.6), (138.525, 73.6)], ('pad', 'R44', '2')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R46', '2'), [], ('pad', 'R37', '2')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T6: U7 (TPS16630 +5 V eFuse). +5V: F bar on pins 18-20 + C41.1, 3 vias into a B +5V band
# (y82.2-83.75 under XT1, above the +12V band) that turns up beside XT1 13/14 to pins 15-18; D13 clamp
# and R45 bleeder via their own vias. P5_RAW: pins 1-3 bar + pin 6 under NC 4/5, 2 vias at the SW corner
# into the B P5_RAW pour; R39/R41 tops; output caps C35/C20-C23 one via each. R41 turned 180 deg in
# place (its P5_RAW pad was boxed in by U7 pin 10, C40 and R42; now it faces a free via spot).
# UV/OV/DVDT/ILIM/GND pin escapes and local GND vias.
B['T6-U7'] = {
    'moves': [('R41', None, 180.0)],
    'zones': [
        ('B.Cu', '+5V', [(85.0, 82.2), (107.6, 82.2), (107.6, 77.6), (112.2, 77.6), (112.2, 83.75), (85.0, 83.75)],
         'solid'),
    ],
    'vias': {
        'p5a': ('+5V', (85.6, 83.0)), 'p5b': ('+5V', (86.75, 83.48)), 'p5c': ('+5V', (87.85, 82.7)),
        't5d': ('+5V', (99.3, 83.0)), 't5r45': ('+5V', (106.6, 83.6)),
        'pr1': ('P5_RAW', (85.8, 91.0)), 'pr2': ('P5_RAW', (85.8, 91.9)), 'pr41': ('P5_RAW', (96.2, 90.7)),
        'pc35': ('P5_RAW', (88.05, 99.0)), 'pc20': ('P5_RAW', (96.75, 98.6)), 'pc21': ('P5_RAW', (99.2, 98.6)),
        'pc23': ('P5_RAW', (105.9, 98.6)), 'pc22': ('P5_RAW', (105.9, 93.5)),
        'gc41': ('GND', (85.6, 80.9)), 'gr40': ('GND', (89.6, 94.1)), 'gr42': ('GND', (95.1, 93.75)),
        'gr43': ('GND', (95.25, 86.35)), 'gd12': ('GND', (97.8, 87.175)), 'gd13': ('GND', (101.55, 94.5)),
        'gc35': ('GND', (93.45, 99.0)), 'gc20': ('GND', (96.75, 95.5)), 'gc21': ('GND', (99.2, 95.5)),
        'gc23': ('GND', (104.5, 96.8)), 'gc22': ('GND', (104.5, 92.05)), 'gr45': ('GND', (108.3, 86.5)),
    },
    'tracks': [
        ('+5V', 'F.Cu', 0.4, ('pad', 'U7', '20'), [], ('pad', 'U7', '18')),
        ('+5V', 'F.Cu', 0.5, ('pad', 'U7', '20'), [], ('via', 'p5a')),
        ('+5V', 'F.Cu', 0.4, ('pad', 'U7', '19'), [], ('via', 'p5b')),
        ('+5V', 'F.Cu', 0.4, ('pad', 'U7', '18'), [(87.725, 83.6)], ('via', 'p5c')),
        ('+5V', 'F.Cu', 0.5, ('pad', 'C41', '1'), [], ('via', 'p5b')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C41', '2'), [], ('via', 'gc41')),
        ('+5V', 'F.Cu', 0.6, ('pad', 'D13', '1'), [(99.3, 91.5)], ('via', 't5d')),
        ('+5V', 'F.Cu', 0.4, ('pad', 'R45', '1'), [], ('via', 't5r45')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R45', '2'), [], ('via', 'gr45')),
        ('P5_RAW', 'F.Cu', 0.4, ('pad', 'U7', '1'), [], ('pad', 'U7', '3')),
        ('P5_RAW', 'F.Cu', 0.25, ('pad', 'U7', '6'), [(89.675, 91.68), (87.725, 91.68)], ('pad', 'U7', '3')),
        ('P5_RAW', 'F.Cu', 0.5, ('pad', 'U7', '1'), [], ('via', 'pr1')),
        ('P5_RAW', 'F.Cu', 0.5, ('pad', 'U7', '1'), [], ('via', 'pr2')),
        ('P5_RAW', 'F.Cu', 0.3, ('pad', 'R39', '1'), [], ('via', 'pr2')),
        ('P5_RAW', 'F.Cu', 0.3, ('pad', 'R41', '1'), [], ('via', 'pr41')),
        ('P5_UV', 'F.Cu', 0.2, ('pad', 'U7', '7'), [(90.325, 92.15), (88.6, 92.15)], ('pad', 'R40', '1')),
        ('P5_UV', 'F.Cu', 0.2, ('pad', 'R40', '1'), [], ('pad', 'R39', '2')),
        ('P5_OV', 'F.Cu', 0.2, ('pad', 'U7', '8'), [(90.975, 91.75), (92.9, 91.75)], ('pad', 'R41', '2')),
        ('P5_OV', 'F.Cu', 0.2, ('pad', 'R41', '2'), [], ('pad', 'R42', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'U7', '9'), [(91.625, 88.9)], ('padu', '3ad997a5-3d57-5cd4-88cd-b072d3b04d7b')),
        ('P5_DVDT', 'F.Cu', 0.2, ('pad', 'U7', '10'), [(92.85, 89.7)], ('pad', 'C40', '1')),
        ('P5_ILIM', 'F.Cu', 0.2, ('pad', 'U7', '11'), [(92.95, 84.812), (92.95, 86.9)], ('pad', 'R43', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R40', '2'), [], ('via', 'gr40')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R42', '2'), [], ('via', 'gr42')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R43', '2'), [], ('via', 'gr43')),
        ('GND', 'F.Cu', 0.3, ('pad', 'C40', '2'), [], ('pad', 'R43', '2')),
        ('GND', 'F.Cu', 0.6, ('pad', 'D12', '2'), [], ('via', 'gd12')),
        ('GND', 'F.Cu', 0.6, ('pad', 'D13', '2'), [], ('via', 'gd13')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C35', '2'), [], ('via', 'gc35')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C20', '2'), [], ('via', 'gc20')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C21', '2'), [], ('via', 'gc21')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C23', '2'), [], ('via', 'gc23')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C22', '2'), [], ('via', 'gc22')),
        ('P5_RAW', 'F.Cu', 0.6, ('pad', 'C35', '1'), [], ('via', 'pc35')),
        ('P5_RAW', 'F.Cu', 0.6, ('pad', 'C20', '1'), [], ('via', 'pc20')),
        ('P5_RAW', 'F.Cu', 0.6, ('pad', 'C21', '1'), [], ('via', 'pc21')),
        ('P5_RAW', 'F.Cu', 0.6, ('pad', 'C23', '1'), [], ('via', 'pc23')),
        ('P5_RAW', 'F.Cu', 0.6, ('pad', 'C22', '1'), [], ('via', 'pc22')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T7: logic links to XT2 and C5. RUN on F: XT2.3 -> south of the M3 support -> down x119.7 -> above
# XT1 (y76.7) -> round the J2-cutout corner (x86.0) -> R46/R37 -> U6.13, branch down between the XT1
# columns 1/3 (x92.02) to U7.13. P12_OK: U6.15/16 between the R37 pads to a via, B above XT1 (y76.75)
# -> XT2.4 between its pin rows. P5_OK: XT2.5 -> B y77.2 -> via west of XT1 pin 2 -> F down to
# U7.15/16. MAIN_OK: branch off the U2-U3 B run at the bottom edge -> B y100.75 -> up x134.65/134.9
# beside XT2 -> XT2.2. U6 ILIM -> R34, R34 GND via. C5 VIN/GND vias to In2/In1.
B['T7-logic'] = {
    'vias': {
        'po1': ('P12_OK', (81.25, 72.0), VS), 'pk1': ('P5_OK', (89.3, 77.55), VS),
        'g34': ('GND', (85.175, 73.45)),
        'c5v1': ('VIN', (136.8, 80.6)), 'c5v2': ('VIN', (138.3, 80.6)),
        'c5g1': ('GND', (142.2, 80.6)), 'c5g2': ('GND', (143.7, 80.6)),
    },
    'tracks': [
        ('RUN', 'F.Cu', 0.2, ('pad', 'XT2', '3'), [(129.4, 69.865), (129.4, 74.2), (120.0, 74.2), (119.7, 74.5),
                                                   (119.7, 76.7), (86.0, 76.7), (86.0, 72.6), (82.8, 72.6)],
         ('pad', 'R46', '1')),
        ('RUN', 'F.Cu', 0.2, ('trk', 'T7-logic', 0, 5, (92.02, 76.7)), [(92.02, 83.4), (90.975, 83.4)],
         ('pad', 'U7', '13')),
        ('RUN', 'F.Cu', 0.2, ('pad', 'R37', '1'), [], ('pad', 'R46', '1')),
        ('RUN', 'F.Cu', 0.2, ('pad', 'U6', '13'), [(82.875, 75.5)], ('pad', 'R37', '1')),
        ('P12_OK', 'F.Cu', 0.25, ('pad', 'U6', '16'), [], ('pad', 'U6', '15')),
        ('P12_OK', 'F.Cu', 0.2, ('pad', 'U6', '15'), [(81.575, 75.95), (81.25, 75.6)], ('via', 'po1')),
        ('P12_OK', 'B.Cu', 0.2, ('via', 'po1'), [(86.05, 72.0), (86.05, 76.75), (120.4, 76.75), (120.4, 73.9),
                                                 (129.8, 73.9), (129.8, 71.135), (132.6, 71.135)],
         ('pad', 'XT2', '4')),
        ('P5_OK', 'B.Cu', 0.2, ('pad', 'XT2', '5'), [(131.0, 74.4), (120.85, 74.4), (120.85, 77.2), (89.3, 77.2)],
         ('via', 'pk1')),
        ('P5_OK', 'F.Cu', 0.2, ('via', 'pk1'), [(89.25, 83.5)], ('pad', 'U7', '16')),
        ('P5_OK', 'F.Cu', 0.25, ('pad', 'U7', '16'), [], ('pad', 'U7', '15')),
        ('MAIN_OK', 'B.Cu', 0.2, ('trk', 'T4-U3-stage', 3, 0, (80.75, 100.75)),
         [(134.65, 100.75), (134.65, 77.0), (134.9, 76.75), (134.9, 67.325)], ('pad', 'XT2', '2')),
        ('P12_ILIM', 'F.Cu', 0.2, ('pad', 'U6', '11'), [(84.175, 75.9)], ('pad', 'R34', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R34', '2'), [], ('via', 'g34')),
        ('VIN', 'F.Cu', 0.6, ('pad', 'C5', '1'), [], ('via', 'c5v1')),
        ('VIN', 'F.Cu', 0.6, ('pad', 'C5', '1'), [], ('via', 'c5v2')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C5', '2'), [], ('via', 'c5g1')),
        ('GND', 'F.Cu', 0.6, ('pad', 'C5', '2'), [], ('via', 'c5g2')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T8: U4 remainder + Q1 sequencing + MAIN_OK re-route. Rip-up (own copper, reviewed): the T4 MAIN_OK
# B run along the bottom edge and its T7 branch to XT2 - they enclosed the south-east, so the Q1
# emitter's P12_RAW sense could not reach Q1 from the west without crossing. New MAIN_OK: U2 via ->
# B north of the P5_RAW pour (y86.9) -> U3 via; and U2 via -> B down x64.4 -> bottom y101.15 ->
# up x134.65/134.9 -> XT2.2. P12_RAW sense: R8.2 -> F -> via -> B down x65.4 -> y100.7 -> via -> Q1.2.
# FB_N divider (R15 to N12_RAW = U4 IC ground via n5, R14 to GND) kept away from SW; EN_N R17 -> R18;
# Q1-C via B; Q1-B round Q1.3; D7 LED; R21/R18/R13 N12_RAW link; XT1 19/20 -> B N12_RAW pour.
B['T8-U4-Q1'] = {
    'deletes': [('T4-U3-stage', 3, 5), ('T7-logic', 10, 5)],
    'vias': {
        'ps0': ('P12_RAW', (65.4, 83.3), VS), 'ps1': ('P12_RAW', (108.35, 97.5), VS),
        'qc1': ('Q1-C', (110.1, 91.4), VS), 'qc2': ('Q1-C', (111.9, 95.6), VS), 'n6': ('N12_RAW', (110.2, 92.4), VS),
        'g14': ('GND', (112.85, 91.5)), 'gd7': ('GND', (107.9, 91.3)), 'g16': ('GND', (109.725, 100.15)),
    },
    'tracks': [
        ('MAIN_OK', 'B.Cu', 0.2, ('via', 'T2-U2-stage/mo1'), [(68.9, 80.8), (68.9, 86.9), (80.4, 86.9), (80.4, 95.2)],
         ('via', 'T4-U3-stage/mo2')),
        ('MAIN_OK', 'B.Cu', 0.2, ('via', 'T2-U2-stage/mo1'), [(68.15, 81.0), (64.4, 81.0), (64.4, 101.15),
                                                            (134.65, 101.15), (134.65, 77.0), (134.9, 76.75),
                                                            (134.9, 67.325)], ('pad', 'XT2', '2')),
        ('P12_RAW', 'F.Cu', 0.2, ('pad', 'R8', '2'), [(62.525, 82.55), (65.4, 82.55)], ('via', 'ps0')),
        ('P12_RAW', 'B.Cu', 0.2, ('via', 'ps0'), [(65.4, 100.7), (108.35, 100.7)], ('via', 'ps1')),
        ('P12_RAW', 'F.Cu', 0.2, ('via', 'ps1'), [], ('pad', 'Q1', '2')),
        ('Q1-B', 'F.Cu', 0.2, ('pad', 'Q1', '1'), [(110.6, 95.0), (112.9, 95.0), (112.9, 98.6)], ('pad', 'R16', '2')),
        ('Q1-C', 'F.Cu', 0.2, ('pad', 'Q1', '3'), [], ('via', 'qc2')),
        ('Q1-C', 'B.Cu', 0.2, ('via', 'qc2'), [(109.5, 95.0), (109.5, 92.0)], ('via', 'qc1')),
        ('Q1-C', 'F.Cu', 0.2, ('via', 'qc1'), [], ('pad', 'R17', '1')),
        ('EN_N', 'F.Cu', 0.2, ('pad', 'R17', '2'), [], ('pad', 'R18', '1')),
        ('FB_N', 'F.Cu', 0.2, ('pad', 'U4', '5'), [(116.095, 91.2), (113.9, 93.4)], ('pad', 'R14', '1')),
        ('FB_N', 'F.Cu', 0.2, ('pad', 'R14', '1'), [], ('pad', 'R15', '1')),
        ('N12_RAW', 'F.Cu', 0.3, ('pad', 'R21', '2'), [], ('pad', 'R18', '2')),
        ('N12_RAW', 'F.Cu', 0.3, ('pad', 'R18', '2'), [], ('pad', 'R13', '1')),
        ('N12_RAW', 'F.Cu', 0.25, ('pad', 'R15', '2'), [], ('via', 'n6')),
        ('N12_RAW', 'B.Cu', 0.25, ('via', 'n6'), [(111.0, 93.2), (114.6, 93.2), (115.2, 92.6)], ('via0', 'n5')),
        ('N12_RAW', 'B.Cu', 0.6, ('pad', 'XT1', '20'), [], ('pad', 'XT1', '19')),
        ('N12_RAW', 'B.Cu', 0.4, ('pad', 'XT1', '19'), [(116.6, 81.025)], ('via0', 'n2')),
        ('D7-K', 'F.Cu', 0.2, ('pad', 'R21', '1'), [(109.3, 88.6), (109.3, 93.4)], ('pad', 'D7', '1')),
        ('GND', 'F.Cu', 0.3, ('pad', 'D7', '2'), [], ('via', 'gd7')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R14', '2'), [], ('via', 'g14')),
        ('GND', 'F.Cu', 0.3, ('pad', 'R16', '1'), [], ('via', 'g16')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T9: current/heat polish (no new connectivity). The In1 GND / In2 VIN planes meet the XT1 posts with
# thermal spokes; solid F + B patches on the VIN posts (3-6) and on each GND post pair (1/2, 7/8,
# 13/14), each with a via at the cluster centre, give the header current a solid path into the planes
# (the VIN centre via also ties the spoke-isolated In2 fragment between the VIN posts). U6 thermal pad:
# B GND pour north/east of its B pad (heat spreading on the outer layer). Third P5_RAW via at the U7
# inputs; second 0.4 mm B run from XT1 pin 20 into the B N12_RAW pour.
_PATCH = {'VIN': [(92.55, 77.75), (97.05, 77.75), (97.05, 81.9), (92.55, 81.9)],
          'G12': [(89.65, 77.75), (91.8, 77.75), (91.8, 81.9), (89.65, 81.9)],
          'G78': [(97.45, 77.75), (99.35, 77.75), (99.35, 81.9), (97.45, 81.9)],
          'G1314': [(104.75, 77.75), (107.25, 77.75), (107.25, 81.9), (104.75, 81.9)]}
B['T9-polish'] = {
    'zones': [(lay, 'VIN' if k == 'VIN' else 'GND', poly, 'solid') for k, poly in _PATCH.items()
              for lay in ('F.Cu', 'B.Cu')] + [
        ('B.Cu', 'GND', [(78.4, 72.5), (85.7, 72.5), (85.7, 81.35), (78.4, 81.35)], 'solid'),
    ],
    'vias': {
        'vx': ('VIN', (94.56, 79.805)), 'g12': ('GND', (90.75, 79.805)), 'g78': ('GND', (98.37, 79.805)),
        'g1314': ('GND', (105.99, 79.805)), 'pr3': ('P5_RAW', (85.05, 91.55)),
    },
    'tracks': [
        ('VIN', 'F.Cu', 0.8, ('via', 'vx'), [], ('pad', 'XT1', '3')),
        ('GND', 'F.Cu', 0.8, ('via', 'g12'), [], ('pad', 'XT1', '1')),
        ('GND', 'F.Cu', 0.8, ('via', 'g78'), [], ('pad', 'XT1', '7')),
        ('GND', 'F.Cu', 0.8, ('via', 'g1314'), [], ('pad', 'XT1', '13')),
        ('P5_RAW', 'F.Cu', 0.4, ('via', 'pr3'), [], ('via', 'T6-U7/pr2')),
        ('N12_RAW', 'B.Cu', 0.4, ('pad', 'XT1', '20'), [(114.9, 79.525), (116.6, 79.525)], ('via0', 'n2')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T10: via-to-pad margin fix. check_stack's via-in-SMD-pad gate (via radius + 0.05 mm) flagged
# same-net vias that sat only 0.05 mm off pad copper (between the C6/C7 and C15/C16 pads and beside
# L2.2); vin3/vin4 had 0.054-0.073 mm. Reviewed rip-up of those vias (+ their stubs) and re-placement
# >= 0.17 mm clear of every SMD pad; same nets, same plane connections.
B['T10-via-margin'] = {
    'delete_vias': ['T2-U2-stage/g2', 'T2-U2-stage/vin3', 'T2-U2-stage/vin4', 'T4-U3-stage/v1', 'T4-U3-stage/v2',
                    'T4-U3-stage/l1', 'T4-U3-stage/l2', 'T4-U3-stage/l3'],
    'deletes': [('T4-U3-stage', 9, 1), ('T4-U3-stage', 10, 1), ('T4-U3-stage', 19, 1), ('T4-U3-stage', 20, 1),
                ('T4-U3-stage', 21, 1)],
    'vias': {
        'g2': ('GND', (73.0, 75.85)), 'vin3': ('VIN', (72.95, 81.1)),
        'v1': ('VIN', (82.3, 90.0)), 'v2': ('VIN', (82.3, 92.3)),
        'l1': ('P5_RAW', (74.5, 89.3)), 'l2': ('P5_RAW', (74.5, 90.6)), 'l3': ('P5_RAW', (74.5, 91.9)),
    },
    'tracks': [
        ('GND', 'F.Cu', 0.6, ('via', 'g2'), [], ('pad', 'C6', '2')),
        ('VIN', 'F.Cu', 0.6, ('via', 'vin3'), [], ('pad', 'C7', '1')),
        ('VIN', 'F.Cu', 0.6, ('via', 'v1'), [], ('pad', 'C16', '1')),
        ('VIN', 'F.Cu', 0.6, ('via', 'v2'), [], ('pad', 'C15', '1')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'L2', '2'), [], ('via', 'l1')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'L2', '2'), [], ('via', 'l2')),
        ('P5_RAW', 'F.Cu', 0.8, ('pad', 'L2', '2'), [], ('via', 'l3')),
    ],
}

# ---------------------------------------------------------------------------------------------
# T11: correction of T10 (an index slip ripped up the R11.2 -> pr11 stub instead of the L2.2 -> old-l1
# stub). Remove the orphaned L2.2 stub (it ended where the old l1 via was) and restore R11.2 -> pr11.
B['T11-fix'] = {
    'deletes': [('T4-U3-stage', 18, 1)],
    'tracks': [
        ('P5_RAW', 'F.Cu', 0.3, ('pad', 'R11', '2'), [], ('via', 'T4-U3-stage/pr11')),
    ],
}



# ---------------------------------------------------------------------------------------------
def audit(rep_dir):
    import collections
    import pcbnew
    import drc_summary
    rep_dir = Path(rep_dir)
    rep_dir.mkdir(parents=True, exist_ok=True)
    d = drc_summary.drc('top', rep_dir)
    raw = json.loads((rep_dir / 'drc-top.json').read_text())
    b = pcbnew.LoadBoard(str(PCB))
    out = {'drc_violations': d['violations'], 'unconnected': d['unconnected'], 'parity': d['parity'],
           'excluded': d['excluded'], 'details': d['details']}
    cnt = collections.Counter()
    for u in raw['unconnected_items']:
        desc = u['items'][0]['description']
        cnt[desc[desc.find('[') + 1:desc.find(']')]] += 1
    out['open_by_net'] = dict(cnt.most_common())
    # vias vs SMD pad copper and mask opening (pad + mask margin + via radius)
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    bad = []
    for v in vias:
        vr = v.GetWidth(pcbnew.F_Cu) / 2
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue
                for lay in (pcbnew.F_Cu, pcbnew.F_Mask):
                    if not p.IsOnLayer(lay):
                        continue
                    poly = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE)
                    exp = p.GetSolderMaskExpansion(pcbnew.F_Mask) if lay == pcbnew.F_Mask else 0
                    dist = poly.Distance(v.GetPosition()) if not poly.Contains(v.GetPosition()) else 0
                    if dist < vr + exp + pcbnew.FromMM(0.1):     # >= 0.1 mm clear (check_stack uses 0.05)
                        bad.append((f.GetReference(), p.GetNumber(), 'mask' if exp else 'copper',
                                    round(pcbnew.ToMM(v.GetPosition().x), 3), round(pcbnew.ToMM(v.GetPosition().y), 3)))
    out['vias'] = len(vias)
    out['vias_in_smd_pad_or_mask'] = sorted(set(bad))
    trk = [t for t in b.GetTracks() if t.GetClass() != 'PCB_VIA']
    out['tracks'] = len(trk)
    out['tracks_on_In1'] = sum(1 for t in trk if t.GetLayer() == pcbnew.In1_Cu)
    out['tracks_on_In2'] = sum(1 for t in trk if t.GetLayer() == pcbnew.In2_Cu)
    out['zero_length'] = [t.m_Uuid.AsString() for t in trk if t.GetStart() == t.GetEnd()]
    seen, dup = set(), []
    for t in trk:
        k = (t.GetNetname(), t.GetLayer(), *sorted([(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)]))
        if k in seen:
            dup.append(t.m_Uuid.AsString())
        seen.add(k)
    out['duplicate_segments'] = dup
    # dangling ends: a track end must touch another same-net track end/body, a via or a pad on that layer
    def touches(pt, lay, net, me):
        for o in trk:
            if o is me or o.GetNetname() != net or o.GetLayer() != lay:
                continue
            if o.HitTest(pt, 1000):
                return True
        for v in vias:
            if v.GetNetname() == net and (v.GetPosition() - pt).EuclideanNorm() <= v.GetWidth(pcbnew.F_Cu) / 2:
                return True
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname() == net and p.IsOnLayer(lay) and p.HitTest(pt):
                    return True
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.GetNetname() == net and z.IsOnLayer(lay) and z.HitTestFilledArea(lay, pt):
                return True
        return False
    filler = pcbnew.ZONE_FILLER(b)
    zs = [z for z in b.Zones() if not z.GetIsRuleArea()]
    filler.Fill(zs)
    out['dangling_track_ends'] = [(t.GetNetname(), b.GetLayerName(t.GetLayer()), round(pcbnew.ToMM(pt.x), 3),
                                   round(pcbnew.ToMM(pt.y), 3)) for t in trk for pt in (t.GetStart(), t.GetEnd())
                                  if not touches(pt, t.GetLayer(), t.GetNetname(), t)]
    lonely = []
    for v in vias:
        hit = any(t.GetNetname() == v.GetNetname() and (t.GetStart() == v.GetPosition() or t.GetEnd() == v.GetPosition())
                  for t in trk)
        if not hit:
            hit = sum(1 for z in zs if z.GetNetname() == v.GetNetname()
                      and any(z.IsOnLayer(l) and z.HitTestFilledArea(l, v.GetPosition()) for l in z.GetLayerSet().CuStack())) >= 2
        if not hit:
            lonely.append((v.GetNetname(), round(pcbnew.ToMM(v.GetPosition().x), 3), round(pcbnew.ToMM(v.GetPosition().y), 3)))
    out['vias_not_joining_two_layers'] = lonely
    planes = {}
    for z in zs:
        for lay in z.GetLayerSet().CuStack():
            fp = z.GetFilledPolysList(lay)
            areas = sorted((round(abs(fp.Outline(i).Area()) / 1e12, 2) for i in range(fp.OutlineCount())), reverse=True)
            planes.setdefault(f'{b.GetLayerName(lay)}:{z.GetNetname()}', []).append(areas)
    out['zone_fill_pieces'] = planes
    therm = {}
    for r, pad, want in (('U4', '9', 'N12_RAW'), ('U6', '21', 'GND'), ('U7', '21', 'GND')):
        f = b.FindFootprintByReference(r)
        therm[f'{r}.{pad}'] = sorted({p.GetNetname() for p in f.Pads() if p.GetNumber() == pad}) == [want]
    out['thermal_terminal_nets_ok'] = therm
    (rep_dir / 'audit.json').write_text(json.dumps(out, indent=1))
    return out


# ---------------------------------------------------------------------------------------------
PCOL = {'GND': (122, 122, 122), 'VIN': (214, 39, 40), 'N12_RAW': (148, 103, 189), '+12V': (44, 160, 44),
        '+5V': (23, 190, 207), 'P12_RAW': (130, 200, 110), 'P5_RAW': (130, 190, 220), 'V3V3': (188, 189, 34)}
LCOL = {'F.Cu': (208, 48, 42), 'B.Cu': (42, 95, 208), 'In2.Cu': (224, 138, 0), 'In1.Cu': (60, 60, 60)}


def view(png, box=None, layers=('F.Cu', 'B.Cu', 'In2.Cu'), title=None, grid=True, labels_pads=True):
    import pcbnew
    from PIL import Image, ImageDraw, ImageFont
    font_p = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    b = pcbnew.LoadBoard(str(PCB))
    pcbnew.ZONE_FILLER(b).Fill([z for z in b.Zones() if not z.GetIsRuleArea()])
    x0, x1, y0, y1 = box or (49.0, 151.0, 61.5, 103.0)
    S = min(2600 / (x1 - x0), 1800 / (y1 - y0))
    W, H = int((x1 - x0) * S), int((y1 - y0) * S) + 30
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img, 'RGBA')
    P = lambda x, y: ((x - x0) * S, (y - y0) * S)  # noqa: E731
    mm = pcbnew.ToMM

    def polys(sp):
        return [[(mm(sp.Outline(i).CPoint(k).x), mm(sp.Outline(i).CPoint(k).y))
                 for k in range(sp.Outline(i).PointCount())] for i in range(sp.OutlineCount())]
    if grid:
        f = ImageFont.truetype(font_p, max(9, int(S * 0.35)))
        for gx in range(int(x0), int(x1) + 1):
            c = (215, 215, 215) if gx % 5 else (170, 170, 170)
            dr.line([P(gx, y0), P(gx, y1)], fill=c, width=1)
            if gx % 5 == 0:
                dr.text((P(gx, y0)[0] + 2, 2), str(gx), fill=(90, 90, 90), font=f)
        for gy in range(int(y0), int(y1) + 1):
            c = (215, 215, 215) if gy % 5 else (170, 170, 170)
            dr.line([P(x0, gy), P(x1, gy)], fill=c, width=1)
            if gy % 5 == 0:
                dr.text((2, P(x0, gy)[1] + 2), str(gy), fill=(90, 90, 90), font=f)
    order = [l for l in ('In1.Cu', 'In2.Cu', 'B.Cu', 'F.Cu') if l in layers]
    for ln in order:
        lid = b.GetLayerID(ln)
        for z in b.Zones():
            if z.GetIsRuleArea():
                continue
            if z.IsOnLayer(lid):
                c = LCOL[ln]
                for q in polys(z.GetFilledPolysList(lid)):
                    dr.polygon([P(*v) for v in q], fill=c + (45 if ln.startswith('In') else 60,), outline=c + (140,))
    for z in b.Zones():
        if z.GetIsRuleArea():
            for q in polys(z.Outline()):
                dr.line([P(*v) for v in q + q[:1]], fill=(0, 0, 0, 120), width=1)
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            dr.line([P(mm(d.GetStart().x), mm(d.GetStart().y)), P(mm(d.GetEnd().x), mm(d.GetEnd().y))], fill='black', width=3)
    fpad = ImageFont.truetype(font_p, max(8, int(S * 0.28)))
    fref = ImageFont.truetype(font_p, max(9, int(S * 0.5)))
    labels = []
    for fp in b.GetFootprints():
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        for q in polys(cy) if cy.OutlineCount() else []:
            dr.line([P(*v) for v in q + q[:1]], fill=(150, 150, 150), width=1)
        for p in fp.Pads():
            c = PCOL.get(p.GetNetname(), (205, 165, 85))
            for q in polys(p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)):
                dr.polygon([P(*v) for v in q], fill=c + (200,), outline=(0, 0, 0))
            if labels_pads and p.GetAttribute() != pcbnew.PAD_ATTRIB_PTH or (p.GetNumber() and fp.GetReference().startswith('X')):
                if p.GetSize().x > 300000 and p.GetSize().x < 5000000 and p.GetNumber():
                    x, y = P(mm(p.GetPosition().x), mm(p.GetPosition().y))
                    dr.text((x, y), p.GetNumber(), fill=(0, 0, 0), font=fpad, anchor='mm')
        if fp.GetReference():
            labels.append(((mm(fp.GetPosition().x), mm(fp.GetPosition().y)), fp.GetReference()))
    for ln in order:
        lid = b.GetLayerID(ln)
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA' or t.GetLayer() != lid:
                continue
            w = max(1, int(mm(t.GetWidth()) * S))
            a, c = P(mm(t.GetStart().x), mm(t.GetStart().y)), P(mm(t.GetEnd().x), mm(t.GetEnd().y))
            dr.line([a, c], fill=LCOL[ln] + (190,), width=w)
            for e in (a, c):
                dr.ellipse([e[0] - w / 2, e[1] - w / 2, e[0] + w / 2, e[1] + w / 2], fill=LCOL[ln] + (190,))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            (cx, cz), r = P(mm(t.GetPosition().x), mm(t.GetPosition().y)), mm(t.GetWidth(pcbnew.F_Cu)) / 2 * S
            dr.ellipse([cx - r, cz - r, cx + r, cz + r], fill=PCOL.get(t.GetNetname(), (255, 255, 255)), outline='black', width=2)
            rr = mm(t.GetDrillValue()) / 2 * S
            dr.ellipse([cx - rr, cz - rr, cx + rr, cz + rr], fill='white')
    for (x, y), r in labels:
        if x0 <= x <= x1 and y0 <= y <= y1:
            px, py = P(x, y)
            bb = dr.textbbox((px, py), r, font=fref, anchor='mm')
            dr.rectangle(bb, fill=(255, 255, 255, 150))
            dr.text((px, py), r, fill=(0, 0, 0), font=fref, anchor='mm')
    dr.text((8, H - 24), title or ('TOP board, native frame (pcbnew x right / y down, mm grid). Layers %s: F red, '
                                   'B blue, In2 orange; pads by net (VIN red, GND grey, N12_RAW purple, +12V green, +5V cyan)'
                                   % '/'.join(layers)), fill='black', font=ImageFont.truetype(font_p, 16))
    img.save(png)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'ops':
        Path(sys.argv[3]).write_text(json.dumps(emit(sys.argv[2]), indent=1))
    elif cmd == 'apply':
        sys.exit(apply(sys.argv[2]))
    elif cmd == 'audit':
        o = audit(sys.argv[2] if len(sys.argv) > 2 else MOD / 'research/r3-top/audit')
        o.pop('details') if not o['details'] else None
        print(json.dumps(o, indent=1)[:6000])
    elif cmd == 'view':
        box = tuple(float(v) for v in sys.argv[3:7]) if len(sys.argv) >= 7 else None
        lay = tuple(sys.argv[7].split(',')) if len(sys.argv) >= 8 else ('F.Cu', 'B.Cu', 'In2.Cu')
        view(sys.argv[2], box, lay)
