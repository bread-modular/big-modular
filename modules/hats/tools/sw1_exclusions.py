#!/usr/bin/env python3
"""Write the SW1/U7 DRC exclusions (and nothing else) into hardware/hats.kicad_pro.

The REC button SW1 sits inside the HIHAT vactrol U7's outline on the user's direction
(2026-10-23: "You can put the button inside the vactrol. I am going to solder it from the
other side."). That stacking gives exactly 4 native `pth_inside_courtyard` errors: SW1's
four pins inside U7's courtyard. The user approved them (2026-10-24: "Ignore those DRC is
the PCB"). Only those 4 are excluded; the rule stays at `error` for everything else.

KiCad keys an exclusion on the marker position and the pad/footprint UUIDs, so re-run this
after moving SW1 or U7:

  kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
      -o research/drc/sw1.json hardware/hats.kicad_pcb
  python3 -B tools/sw1_exclusions.py research/drc/sw1.json

Refuses (writes nothing) unless the report's active findings are exactly the 4 expected ones.
"""
import json
import re
import sys
from pathlib import Path

PRO = Path(__file__).resolve().parent.parent / 'hardware/hats.kicad_pro'
COMMENT = 'SW1 REC button inside the U7 vactrol outline (soldered from the other side), user-approved 2026-10-24'


def expected(violation):
    """Return a short key for an SW1/U7 finding, or None for anything else."""
    if violation.get('type') != 'pth_inside_courtyard' or len(violation.get('items', [])) != 2:
        return None
    pad, owner = (item['description'] for item in violation['items'])
    m = re.fullmatch(r'PTH pad ([12]) \[(/REC_SW|GND)\] of SW1', pad)
    if m and owner == 'Footprint U7':
        return 'pin' + m[1]
    return None


def main(report):
    violations = [v for v in json.loads(Path(report).read_text())['violations'] if not v.get('excluded')]
    keys = sorted(filter(None, map(expected, violations)))
    if len(violations) != 4 or keys != ['pin1', 'pin1', 'pin2', 'pin2']:
        sys.exit(f'refusing: expected exactly the 4 SW1/U7 findings, got {len(violations)} violations')
    exclusions = []
    for v in violations:
        main_item, aux_item = v['items']
        x, y = (round(main_item['pos'][axis] * 1e6) for axis in ('x', 'y'))
        exclusions.append([f"{v['type']}|{x}|{y}|{main_item['uuid']}|{aux_item['uuid']}", COMMENT])
    project = json.loads(PRO.read_text())
    project['board']['design_settings']['drc_exclusions'] = sorted(exclusions)
    PRO.write_text(json.dumps(project, indent=2) + '\n')
    print(f'{len(exclusions)} SW1/U7 exclusions written to {PRO.name}')


if __name__ == '__main__':
    main(sys.argv[1])
