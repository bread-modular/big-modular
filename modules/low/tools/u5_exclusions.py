#!/usr/bin/env python3
"""Write the U5/RV3 DRC exclusions (and nothing else) into hardware/low.kicad_pro.

U5 (VTL5C vactrol) sits on B.Cu under the CUTOFF pot RV3, as on modules/vca-mix (D10) and
Bread Modular SVF. That stacking gives exactly 3 native `pth_inside_courtyard` errors: U5's
LED leads (pads 1, 2) inside RV3's courtyard and RV3's left bracket pad inside U5's
courtyard. The user accepted them (2026-10-21) and asked for them to be excluded
(2026-10-22). Only those 3 are excluded; the rule stays at `error` for everything else.

KiCad keys an exclusion on the marker position and the pad/footprint UUIDs, so re-run this
after moving U5 or RV3:

  kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
      -o research/drc/u5.json hardware/low.kicad_pcb
  python3 -B tools/u5_exclusions.py research/drc/u5.json

Refuses (writes nothing) unless the report holds exactly the 3 expected findings.
"""
import json
import re
import sys
from pathlib import Path

PRO = Path(__file__).resolve().parent.parent / 'hardware/low.kicad_pro'
COMMENT = 'U5 vactrol under CUTOFF pot RV3 (vca-mix D10 stacking), user-approved 2026-10-22'


def expected(violation):
    """Return a short key for a U5/RV3 finding, or None for anything else."""
    if violation.get('type') != 'pth_inside_courtyard' or len(violation.get('items', [])) != 2:
        return None
    pad, owner = (item['description'] for item in violation['items'])
    m = re.fullmatch(r'PTH pad ([12]) \[/VAC_(NEG|POS)\] of U5', pad)
    if m and owner == 'Footprint RV3':
        return 'led' + m[1]
    if pad == 'PTH pad [<no net>] of RV3' and owner == 'Footprint U5':
        return 'bracket'
    return None


def main(report):
    violations = json.loads(Path(report).read_text())['violations']
    keys = sorted(filter(None, map(expected, violations)))
    if len(violations) != 3 or keys != ['bracket', 'led1', 'led2']:
        sys.exit(f'refusing: expected exactly the 3 U5/RV3 findings, got {len(violations)} violations')
    exclusions = []
    for v in violations:
        main_item, aux_item = v['items']
        x, y = (round(main_item['pos'][axis] * 1e6) for axis in ('x', 'y'))
        exclusions.append([f"{v['type']}|{x}|{y}|{main_item['uuid']}|{aux_item['uuid']}", COMMENT])
    project = json.loads(PRO.read_text())
    project['board']['design_settings']['drc_exclusions'] = sorted(exclusions)
    PRO.write_text(json.dumps(project, indent=2) + '\n')
    print(f'{len(exclusions)} U5/RV3 exclusions written to {PRO.name}')


if __name__ == '__main__':
    main(sys.argv[1])
