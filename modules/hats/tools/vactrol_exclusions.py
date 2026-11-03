#!/usr/bin/env python3
"""Write the U7/RV3/RV4 vactrol DRC exclusions (and nothing else) into hardware/hats.kicad_pro.

R3 put the VTL5C vactrol U7 (B.Cu) under the CUTOFF pot RV3, between the pot lugs and pins,
as on modules/low (U5) and modules/acid (U7/U8). Its LED leads reach under DECAY (RV4). That
stacking gives exactly 18 native findings, user-approved 2026-11-03 ("Those errors are fine"):

- 4 x `pth_inside_courtyard`: U7 pads 3/4 inside RV3, pads 1/2 inside RV4;
- 6 x `pth_inside_courtyard`: RV3 lugs (2) and pins 1-3, RV4 left lug inside U7;
- 3 x `silk_over_copper`: the RV3 F-silk outline over U7 pads 3/4;
- 5 x `silk_over_copper`: the U7 B-silk outline over the RV3 lugs (3) and the RV4 left lug (2).

Only those 18 are excluded; both rules stay active for everything else.

KiCad keys an exclusion on the marker position and the item UUIDs. The JSON report gives item
positions, not the marker, so each finding gets a few candidate marker positions; candidates
are tried with native DRC runs until all 18 are excluded. Refuses (restores the project) if
the active findings are not exactly the expected 18 or a finding stays unmatched. Re-run after
moving U7, RV3 or RV4:

  python3 -B tools/vactrol_exclusions.py research/drc/vactrol.json
"""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HW = Path(__file__).resolve().parent.parent / 'hardware'
PRO, PCB = HW / 'hats.kicad_pro', HW / 'hats.kicad_pcb'
COMMENT = 'U7 vactrol under CUTOFF pot RV3 (modules/low U5 stacking), user-approved 2026-11-03'
PAD = re.compile(r'PTH pad (\S*) ?\[[^]]*\] of (\w+)')
WANT = Counter({
    'pth:U7.1@RV4': 1, 'pth:U7.2@RV4': 1, 'pth:U7.3@RV3': 1, 'pth:U7.4@RV3': 1,
    'pth:RV3.lug@U7': 2, 'pth:RV3.1@U7': 1, 'pth:RV3.2@U7': 1, 'pth:RV3.3@U7': 1, 'pth:RV4.lug@U7': 1,
    'silk:RV3@U7.3': 1, 'silk:RV3@U7.4': 2, 'silk:U7@RV3.lug': 3, 'silk:U7@RV4.lug': 2,
})


def key(v):
    if len(v.get('items', [])) != 2:
        return None
    a, b = (i['description'] for i in v['items'])
    m = PAD.fullmatch(b if v['type'] == 'silk_over_copper' else a)
    if not m:
        return None
    pad = f'{m[2]}.{m[1] or "lug"}'
    if v['type'] == 'pth_inside_courtyard' and (o := re.fullmatch(r'Footprint (\w+)', b)):
        return f'pth:{pad}@{o[1]}'
    if v['type'] == 'silk_over_copper' and (s := re.fullmatch(r'Segment of (\w+) on [FB]\.Silkscreen', a)):
        return f'silk:{s[1]}@{pad}'
    return None


def candidates(v):
    a, b = v['items']
    ax, ay, bx, by = a['pos']['x'], a['pos']['y'], b['pos']['x'], b['pos']['y']
    # Marker = first item, or where a silk segment meets the pad (centre line / stadium end).
    pts = [(ax, ay), (bx, ay), (ax, by), (ax, by + 0.26), (ax, by - 0.26)]
    return [f"{v['type']}|{round(x * 1e6)}|{round(y * 1e6)}|{a['uuid']}|{b['uuid']}" for x, y in pts]


def drc(project, exclusions):
    project['board']['design_settings']['drc_exclusions'] = sorted([e, COMMENT] for e in exclusions)
    PRO.write_text(json.dumps(project, indent=2) + '\n')
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'drc.json'
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--units', 'mm', '--severity-all',
                        '-o', str(out), str(PCB)], check=True, capture_output=True)
        return json.loads(out.read_text())['violations']


def main(report):
    original = PRO.read_text()
    found = [v for v in json.loads(Path(report).read_text())['violations'] if not v.get('excluded')]
    if Counter(map(key, found)) != WANT:
        sys.exit(f'refusing: expected exactly the {sum(WANT.values())} U7/RV3/RV4 findings, got {len(found)}')
    project = json.loads(original)
    done, todo = [], [candidates(v) for v in found]
    for k in range(len(todo[0])):
        trial = done + [c[k] for c in todo]
        vs = drc(project, trial)
        hit = {f"{v['type']}|{v['items'][0]['uuid']}|{v['items'][1]['uuid']}" for v in vs if v.get('excluded')}
        ids = lambda e: '|'.join(e.split('|')[i] for i in (0, 3, 4))
        done += [c[k] for c in todo if ids(c[k]) in hit]
        todo = [c for c in todo if ids(c[k]) not in hit]
        if not todo:
            break
    vs = drc(project, done)
    if todo or len(done) != len(found) or any(not v.get('excluded') for v in vs):
        PRO.write_text(original)
        sys.exit(f'refusing: {len(todo)} findings without a matching marker position; project restored')
    print(f'{len(done)} U7/RV3/RV4 exclusions written to {PRO.name}; DRC: {len(vs)} findings, all excluded')


if __name__ == '__main__':
    main(sys.argv[1])
