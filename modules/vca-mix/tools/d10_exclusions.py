#!/usr/bin/env python3
"""Write the D10 DRC exclusions (and nothing else) into hardware/vca-mix.kicad_pro.

D10 (user-approved 2026-10-20): each vactrol sits on B.Cu behind its channel pot, as on
Bread Modular SVF. That stacking gives exactly 9 native `pth_inside_courtyard` errors:
per row the vactrol's two LED leads (pads 1, 2 of U<n>04) inside RV<n>'s courtyard and
RV<n>'s left bracket pad inside U<n>04's courtyard. Only those 9 are excluded; the rule
stays at `error` for everything else.

KiCad keys an exclusion on the marker position and the pad/footprint UUIDs, which a layout
rebuild regenerates, so re-run this after every tools/build_layout.py run:

  kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
      -o research/drc/d10.json hardware/vca-mix.kicad_pcb
  python3 -B tools/d10_exclusions.py research/drc/d10.json

Refuses (writes nothing) unless the report holds exactly the 9 expected pairs.
"""
import json
import re
import sys
from pathlib import Path

PRO = Path(__file__).resolve().parent.parent / 'hardware/vca-mix.kicad_pro'
COMMENT = 'D10: vactrol behind pot (Bread Modular SVF stacking), user-approved 2026-10-20'


def expected_pair(violation):
    """Return (row, kind) for a D10 finding, or None for anything else."""
    if violation.get('type') != 'pth_inside_courtyard' or len(violation.get('items', [])) != 2:
        return None
    pad, owner = (item['description'] for item in violation['items'])
    m = re.fullmatch(r'PTH pad ([12]) \[/LED[AK]([123])\] of U([123])04', pad)
    if m and m[2] == m[3] and owner == f'Footprint RV{m[3]}':
        return int(m[3]), 'led' + m[1]
    m = re.fullmatch(r'PTH pad \[<no net>\] of RV([123])', pad)
    if m and owner == f'Footprint U{m[1]}04':
        return int(m[1]), 'bracket'
    return None


def main(report):
    drc = json.loads(Path(report).read_text())
    violations = drc['violations']
    keys = sorted(filter(None, map(expected_pair, violations)))
    wanted = sorted((row, kind) for row in (1, 2, 3) for kind in ('led1', 'led2', 'bracket'))
    if len(violations) != 9 or keys != wanted:
        sys.exit(f'refusing: expected exactly the 9 D10 findings, got {len(violations)} violations')
    exclusions = []
    for v in violations:
        main_item, aux_item = v['items']
        x, y = (round(main_item['pos'][axis] * 1e6) for axis in ('x', 'y'))
        exclusions.append([f"{v['type']}|{x}|{y}|{main_item['uuid']}|{aux_item['uuid']}", COMMENT])
    project = json.loads(PRO.read_text())
    project['board']['design_settings']['drc_exclusions'] = sorted(exclusions)
    PRO.write_text(json.dumps(project, indent=2) + '\n')
    print(f'{len(exclusions)} D10 exclusions written to {PRO.name}')


if __name__ == '__main__':
    main(sys.argv[1])
