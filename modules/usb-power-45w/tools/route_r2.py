#!/usr/bin/env python3
"""Manual divide-and-conquer routing of the R2 stacked boards, one reviewed batch at a time.

  python3 -B tools/route_r2.py ops <board> <batch> <out.json>     # emit shared `pcb plan` ops
  python3 -B tools/route_r2.py apply <board> <batch>               # plan -> apply -> promote

No router: every track, via and zone below is written by hand (stack YZ frame: Y down the
panel, Z depth; native x = Y + 35.75, native y = 104.275 - Z). `apply` uses the shared
`opt/kicad-tools` pcb plan/apply/promote on the canonical board (backed up to /tmp first,
raw plan/candidate files in research/r2/route/). Batches only ADD copper; routed copper is
never wiped. Layer plan per board: F signal + local power pours, In1 solid GND (no tracks),
In2 power plane (top: VIN; base: decided per batch), B signal + heat spreading.
"""
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
REPO = MOD.parents[1]
sys.path.insert(0, str(MOD / 'tools'))
import stack_r2 as st  # noqa: E402

V6 = (0.6, 0.3)      # default via (netclass), power vias are used in groups

ROUTE = {'top': {}, 'base': {}}

# ---------------------------------------------------------------------------------------------
# TOP T1: U4 (LMR38020F inverting) power stage. Planes first (In1 GND, In2 VIN), then the hot
# loops: VIN-N12_RAW input caps C27/C25/C26 at pins 3/1, BOOT C28 at pins 7/8, SW pin 8 -> L3,
# N12_RAW pour joining pin 1, C36, D4 and the output column; GND pour joining the column GND
# pads, C24 and the L3 GND pad; EN_N escape (pin 2 sits between VIN and N12_RAW) on B; RT.
# B.Cu N12_RAW pour under U4/C36/column: IC-ground spreading for the EP thermal vias
# (U4 EP9 = N12_RAW, NEVER GND).
ROUTE['top']['T1-U4-power-stage'] = {
    'zones': [
        ('In1.Cu', 'GND', st.TOP_OUTLINE, 'thermal'),
        ('In2.Cu', 'VIN', st.TOP_OUTLINE, 'thermal'),
        ('F.Cu', 'VIN', [(79.4, 20.6), (82.2, 20.6), (82.2, 27.5), (79.4, 27.5)], 'solid'),
        ('F.Cu', 'N12_RAW', [(83.6, 19.0), (92.4, 19.0), (92.4, 17.3), (94.4, 17.3), (94.4, 29.4),
                             (83.6, 29.4)], 'solid'),
        ('F.Cu', 'GND', [(86.9, 11.6), (95.4, 11.6), (95.4, 6.3), (100.0, 6.3), (100.0, 21.0), (99.4, 21.0),
                         (99.4, 29.4), (95.4, 29.4), (95.4, 17.0), (92.2, 17.0), (92.2, 18.7), (86.9, 18.7)],
         'solid'),
        ('B.Cu', 'N12_RAW', [(79.0, 13.0), (92.4, 13.0), (92.4, 15.4), (94.4, 15.4), (94.4, 29.4), (79.0, 29.4)],
         'solid'),
    ],
    'vias': {
        'vin1': ('VIN', (79.95, 22.5)), 'vin2': ('VIN', (79.95, 24.0)), 'vin3': ('VIN', (79.95, 25.5)),
        'vin4': ('VIN', (93.525, 14.2)),
        'g1': ('GND', (99.6, 8.0)), 'g2': ('GND', (99.6, 10.0)), 'g3': ('GND', (98.2, 13.2)),
        'g4': ('GND', (98.2, 17.0)), 'g5': ('GND', (98.2, 19.6)), 'g6': ('GND', (98.2, 22.1)),
        'g7': ('GND', (98.2, 24.6)), 'g8': ('GND', (98.2, 27.1)), 'g9': ('GND', (87.6, 14.9)),
        'g10': ('GND', (89.9, 14.9)), 'g11': ('GND', (91.0, 28.2)),
        'n1': ('N12_RAW', (86.0, 20.6)), 'n2': ('N12_RAW', (86.0, 24.6)), 'n3': ('N12_RAW', (91.5, 20.6)),
        'n4': ('N12_RAW', (91.5, 23.2)), 'n5': ('N12_RAW', (79.45, 17.4)),
        'en1': ('EN_N', (82.885, 20.95), (0.5, 0.3)), 'en2': ('EN_N', (77.1, 16.55), (0.5, 0.3)),
    },
    'tracks': [
        # (net, layer, width, start, waypoints, end); ends: ('pad', ref, num) | ('via', key)
        ('VIN', 'F.Cu', 0.6, ('pad', 'U4', '3'), [], ('pad', 'C27', '1')),
        ('N12_RAW', 'F.Cu', 0.6, ('pad', 'U4', '1'), [(84.155, 21.9)], ('pad', 'C27', '2')),
        ('U4-SW', 'F.Cu', 0.6, ('pad', 'U4', '8'), [], ('pad', 'C28', '1')),
        ('U4-SW', 'F.Cu', 1.2, ('pad', 'C28', '1'), [(85.6, 11.4)], ('pad', 'L3', '1')),
        ('U4-BOOT', 'F.Cu', 0.4, ('pad', 'U4', '7'), [], ('pad', 'C28', '2')),
        ('VIN', 'F.Cu', 0.6, ('pad', 'C24', '1'), [], ('via', 'vin4')),
        ('GND', 'F.Cu', 0.6, ('pad', 'D4', '1'), [], ('via', 'g11')),
        ('EN_N', 'F.Cu', 0.3, ('pad', 'U4', '2'), [], ('via', 'en1')),
        ('EN_N', 'B.Cu', 0.3, ('via', 'en1'), [(77.1, 20.95)], ('via', 'en2')),
        ('EN_N', 'F.Cu', 0.3, ('via', 'en2'), [], ('pad', 'R18', '1')),
        ('RT_U4', 'F.Cu', 0.25, ('pad', 'U4', '4'), [], ('pad', 'R13', '2')),
        ('N12_RAW', 'F.Cu', 0.3, ('pad', 'R13', '1'), [(79.45, 18.125)], ('via', 'n5')),
    ],
}


def nat(p):
    return [round(p[0] + 35.75, 4), round(104.275 - p[1], 4)]


def uid(board, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/usb-power-45w/r2/{board}/{key}'))


def board_net(board, short):
    """Short net name -> exact board net name (auto 'Net-(U4-SW)' style names included)."""
    import pcbnew
    b = pcbnew.LoadBoard(str(st.board_file(board)))
    names = [str(n) for n in b.GetNetsByName().keys()]
    for cand in (short, '/' + short, f'Net-({short})'):
        if cand in names:
            return cand
    hits = [n for n in names if n.startswith(f'Net-({short}')]
    assert len(hits) == 1, (short, hits)
    return hits[0]


def emit(board, batch):
    spec = ROUTE[board][batch]
    ops, nets = [], {}

    def n(s):
        if s not in nets:
            nets[s] = board_net(board, s)
        return nets[s]
    for i, (layer, net, poly, conn) in enumerate(spec.get('zones', [])):
        ops.append({'op': 'add_zone', 'uuid': uid(board, f'{batch}/zone/{i}'), 'net': n(net), 'layer': layer,
                    'polygon': [nat(p) for p in poly], 'clearance_mm': 0.25, 'min_thickness_mm': 0.25,
                    'pad_connection': conn})
    vias = spec.get('vias', {})
    for k, (net, at, *size) in vias.items():
        d, dr = size[0] if size else V6
        ops.append({'op': 'add_via', 'uuid': uid(board, f'via/{k}'), 'net': n(net), 'at': nat(at),
                    'diameter_mm': d, 'drill_mm': dr})

    def end(e):
        if e[0] == 'pad':
            return {'pad': {'ref': e[1], 'number': e[2]}}
        return {'uuid': uid(board, f'via/{e[1]}')}
    for i, (net, layer, w, a, wps, b) in enumerate(spec.get('tracks', [])):
        ops.append({'op': 'add_polyline', 'uuid': uid(board, f'{batch}/trk/{i}'), 'net': n(net), 'layer': layer,
                    'width_mm': w, 'start': end(a), 'waypoints': [nat(p) for p in wps], 'end': end(b)})
    return {'schema_version': 1, 'operations': ops}


def tools(*args):
    r = subprocess.run([sys.executable, '-B', str(REPO / 'opt/kicad-tools/kicad_tools.py'), *args],
                       capture_output=True, text=True, cwd=REPO)
    return r.returncode, r.stdout, r.stderr


def apply(board, batch):
    st.refuse_replay(f'route_r2.py apply {board} {batch}')
    work = MOD / 'research/r2/route' / f'{board}-{batch}-{time.strftime("%H%M%S")}'
    work.mkdir(parents=True)
    src = st.board_file(board)
    shutil.copy(src, f'/tmp/{src.stem}-{time.strftime("%H%M%S")}.kicad_pcb')
    (work / 'ops.json').write_text(json.dumps(emit(board, batch), indent=1))
    cfg = MOD / 'tools' / f'kicad-project-{board}.json'
    rc, out, err = tools('pcb', 'plan', '--config', str(cfg), '--ops', str(work / 'ops.json'), '--allow-draft-opens')
    (work / 'plan.stderr').write_text(err)
    try:
        plan_doc = json.loads(out[out.find('{'):out.rfind('}') + 1])
    except ValueError:
        plan_doc = {}
    print('plan rc', rc, plan_doc.get('status'), plan_doc.get('error', ''))
    if plan_doc.get('kind') != 'pcb_edit_plan':
        print(out[-1500:], err[-800:])
        return 1
    planpath = str(work / 'plan.json')
    Path(planpath).write_text(json.dumps(plan_doc, indent=1))
    cand = Path('/tmp/usbpower45-r2-route') / work.name / 'cand'     # must be outside every input dir
    cand.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = tools('pcb', 'apply', '--plan', planpath, '--ops', str(work / 'ops.json'), '--output', str(cand))
    (work / 'apply.stdout').write_text(out + err)
    print('apply rc', rc, (out + err)[-1500:])
    if not (cand / 'result.json').exists():
        return 1
    shutil.copy(cand / 'result.json', work / 'result.json')
    res = json.loads((cand / 'result.json').read_text())
    print('candidate status', res.get('status'), 'parity equal', res.get('checks', {}).get('parity', {}).get('equal'))
    if res.get('status') == 'accepted':
        rc, out, err = tools('pcb', 'promote', '--candidate', str(cand), '--plan', planpath)
        (work / 'promote.stdout').write_text(out + err)
        print('promote rc', rc, (out + err)[-600:])
        return rc
    if res.get('status') != 'draft':
        return 1
    # Intermediate batches still have opens, so the shared `promote` (accepted candidates only) cannot
    # run. The opens-only draft (shorts/clearance/parity already refused by the shared apply) is
    # written back with the source's own 3D-model tokens, then verified: every footprint identical,
    # every earlier copper item kept, only this batch's items added.
    return writeback(board, cand, src, work)


def writeback(board, cand, src, work):
    import re
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
        return {f.m_Uuid.AsString(): (f.GetReference(), f.GetPosition().x, f.GetPosition().y, f.GetOrientationDegrees(),
                                      tuple((p.GetNumber(), p.GetNetname()) for p in f.Pads()),
                                      tuple(sorted((x.GetName(), x.GetText()) for x in f.GetFields())))
                for f in b.GetFootprints()}

    def copper(b):
        out_ = {}
        for t in b.GetTracks():
            out_[t.m_Uuid.AsString()] = (t.GetClass(), t.GetNetname(), t.GetStart().x, t.GetStart().y,
                                         t.GetEnd().x, t.GetEnd().y, t.GetWidth(pcbnew.F_Cu) if t.GetClass() == 'PCB_VIA' else t.GetWidth(), t.GetLayer())
        for z in b.Zones():
            out_[z.m_Uuid.AsString()] = ('ZONE', z.GetNetname(), z.GetFirstLayer(), z.GetIsRuleArea())
        return out_
    assert fps(old) == fps(new), 'footprints changed'
    co, cn = copper(old), copper(new)
    assert all(cn.get(k) == v for k, v in co.items()), 'earlier copper changed'
    added = sorted(set(cn) - set(co))
    shutil.copy(tmp, src)
    print('written back:', len(added), 'items added;', len(cn), 'copper items total')
    (work / 'writeback.json').write_text(json.dumps({'added': len(added), 'total': len(cn)}))
    return 0


if __name__ == '__main__':
    if sys.argv[1] == 'ops':
        Path(sys.argv[4]).write_text(json.dumps(emit(sys.argv[2], sys.argv[3]), indent=1))
    else:
        sys.exit(apply(sys.argv[2], sys.argv[3]))
