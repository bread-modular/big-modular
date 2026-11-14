#!/usr/bin/env python3
"""Write the D10 DRC exclusions (and nothing else) into hardware/vca-mix.kicad_pro.

D10: each VTL5C vactrol U<n>04 sits on B.Cu under its channel's VOL pot RV<n> on F.Cu, as on
modules/low (U5), modules/acid (U7/U8) and modules/hats (U7/U11). On the P6 8HP board that
stacking gives exactly 15 native `pth_inside_courtyard` errors, 5 per channel, user-approved
2026-11-14 ("Those DRC issues are fine"):

- 2 x the vactrol's LDR leads, pads 3 and 4 of U<n>04, inside RV<n>'s courtyard;
- 3 x the pot pins 1, 2 and 3 of RV<n> inside U<n>04's courtyard.

Only those 15 are excluded; the rule stays at `error` for everything else. (The S4 6HP board
had a different set of 9, approved 2026-10-20; that board is gone.)

KiCad keys an exclusion on the marker position and the item UUIDs. The JSON report gives item
positions, not the marker, so each finding gets a few candidate marker positions; candidates
are tried with native DRC runs until all 15 are excluded. Refuses (restores the project) if
the active findings are not exactly the expected 15 or a finding stays unmatched. Re-run after
moving a vactrol or its pot, or after a layout rebuild (new UUIDs):

  kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
      -o research/drc/d10.json hardware/vca-mix.kicad_pcb
  python3 -B tools/d10_exclusions.py research/drc/d10.json
"""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HW = Path(__file__).resolve().parent.parent / 'hardware'
PRO, PCB = HW / 'vca-mix.kicad_pro', HW / 'vca-mix.kicad_pcb'
COMMENT = 'D10: vactrol under its VOL pot (modules/low U5 stacking), user-approved 2026-11-14'
PAD = re.compile(r'PTH pad (\S+) \[[^]]*\] of (\w+)')
WANT = Counter({f'pth:{pad}@{owner}': 1 for n in (1, 2, 3) for pad, owner in (
    (f'U{n}04.3', f'RV{n}'), (f'U{n}04.4', f'RV{n}'),
    (f'RV{n}.1', f'U{n}04'), (f'RV{n}.2', f'U{n}04'), (f'RV{n}.3', f'U{n}04'))})


def key(v):
    if v.get('type') != 'pth_inside_courtyard' or len(v.get('items', [])) != 2:
        return None
    a, b = (i['description'] for i in v['items'])
    m, o = PAD.fullmatch(a), re.fullmatch(r'Footprint (\w+)', b)
    return f'pth:{m[2]}.{m[1]}@{o[1]}' if m and o else None


def candidates(v):
    a, b = v['items']
    ax, ay, bx, by = a['pos']['x'], a['pos']['y'], b['pos']['x'], b['pos']['y']
    # Marker = the pad (first item); the other points are fallbacks.
    pts = [(ax, ay), (bx, by), (bx, ay), (ax, by)]
    return [f"{v['type']}|{round(x * 1e6)}|{round(y * 1e6)}|{a['uuid']}|{b['uuid']}" for x, y in pts]


def drc(project, exclusions, kept):
    project['board']['design_settings']['drc_exclusions'] = sorted(kept + [[e, COMMENT] for e in exclusions])
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
        sys.exit(f'refusing: expected exactly the {sum(WANT.values())} D10 findings, got {len(found)}')
    try:
        project = json.loads(original)
        kept = [e for e in project['board']['design_settings'].get('drc_exclusions', []) if e[1] != COMMENT]
        if kept:
            sys.exit(f'refusing: {len(kept)} exclusions that are not D10 in {PRO.name}')
        ids = lambda e: '|'.join(e.split('|')[i] for i in (0, 3, 4))
        done, todo = [], [candidates(v) for v in found]
        for k in range(len(todo[0])):
            vs = drc(project, done + [c[k] for c in todo], kept)
            hit = {f"{v['type']}|{v['items'][0]['uuid']}|{v['items'][1]['uuid']}" for v in vs if v.get('excluded')}
            done += [c[k] for c in todo if ids(c[k]) in hit]
            todo = [c for c in todo if ids(c[k]) not in hit]
            if not todo:
                break
        vs = drc(project, done, kept)
        if todo or len(done) != len(found) or len(vs) != len(found) or any(not v.get('excluded') for v in vs):
            PRO.write_text(original)
            sys.exit(f'refusing: {len(todo)} findings without a matching marker position; project restored')
    except BaseException:
        PRO.write_text(original)  # any trial failure (DRC run, report parse, interrupt): restore
        raise
    print(f'{len(done)} D10 exclusions written to {PRO.name}; DRC: {len(vs)} findings, all excluded')


if __name__ == '__main__':
    main(sys.argv[1])
