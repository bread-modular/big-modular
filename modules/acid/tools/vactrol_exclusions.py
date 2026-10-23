#!/usr/bin/env python3
"""Write the U7/U8 vactrol DRC exclusions (and nothing else) into hardware/acid.kicad_pro.

R1 moved the VTL5C vactrols U8 and U7 (B.Cu) under the ATTACK (RV3) and RELEASE (RV4) pots,
between the pot lugs and pins, as on modules/low (U5 under CUTOFF) and modules/vca-mix (D10).
That stacking gives exactly 22 native findings per the user's approval (2026-10-22: "The
vactrols placements is fine"):

- 8 x `pth_inside_courtyard`: vactrol pads 1-4 of U8 / U7 inside the RV3 / RV4 courtyard;
- 10 x `pth_inside_courtyard`: RV3 / RV4 lugs (2) and pins 1-3 inside the U8 / U7 courtyard;
- 4 x `silk_over_copper`: the U8 / U7 B-silk outline over the RV3 / RV4 lugs.

Only those 22 are excluded; both rules stay active for everything else.

KiCad keys an exclusion on the marker position and the item UUIDs, so re-run this after
moving U7, U8, RV3 or RV4, or after rebuilding the board with tools/build_layout.py:

  kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
      -o research/drc/vactrols.json hardware/acid.kicad_pcb
  python3 -B tools/vactrol_exclusions.py research/drc/vactrols.json

Refuses (writes nothing) unless the report's active findings are exactly the 22 expected ones.
Re-run the DRC afterwards and confirm all 22 show as excluded.
"""
import json
import re
import sys
from pathlib import Path

PRO = Path(__file__).resolve().parent.parent / 'hardware/acid.kicad_pro'
COMMENT = 'U7/U8 vactrol under the RELEASE/ATTACK pot (modules/low U5 stacking), user-approved 2026-10-22'
PAIRS = {'U8': 'RV3', 'U7': 'RV4'}
POT = {v: k for k, v in PAIRS.items()}
PAD = re.compile(r'PTH pad (\S*) ?\[[^]]*\] of (\w+)')


def expected(violation):
    """Return a short key for a vactrol/pot finding, or None for anything else."""
    if len(violation.get('items', [])) != 2:
        return None
    a, b = (item['description'] for item in violation['items'])
    kind = violation.get('type')
    if kind == 'pth_inside_courtyard':
        m = PAD.fullmatch(a)
        owner = re.fullmatch(r'Footprint (\w+)', b)
        if not m or not owner:
            return None
        num, ref, other = m[1] or 'lug', m[2], owner[1]
        if PAIRS.get(ref) == other and num in '1234':
            return f'{kind}:{ref}.{num}@{other}'
        if POT.get(ref) == other and num in ('lug', '1', '2', '3'):
            return f'{kind}:{ref}.{num}@{other}'
        return None
    if kind == 'silk_over_copper':
        s = re.fullmatch(r'Segment of (U[78]) on B\.Silkscreen', a)
        m = PAD.fullmatch(b)
        if s and m and not m[1] and PAIRS[s[1]] == m[2]:
            return f'{kind}:{s[1]}@{m[2]}.lug'
    return None


def want():
    keys = []
    for vac, pot in PAIRS.items():
        keys += [f'pth_inside_courtyard:{vac}.{p}@{pot}' for p in '1234']
        keys += [f'pth_inside_courtyard:{pot}.{p}@{vac}' for p in ('lug', 'lug', '1', '2', '3')]
        keys += [f'silk_over_copper:{vac}@{pot}.lug'] * 2
    return sorted(keys)


def main(report):
    violations = [v for v in json.loads(Path(report).read_text())['violations'] if not v.get('excluded')]
    keys = sorted(filter(None, map(expected, violations)))
    if len(violations) != len(want()) or keys != want():
        sys.exit(f'refusing: expected exactly the {len(want())} U7/U8 findings, got {len(violations)} '
                 f'violations ({len(keys)} matching)')
    exclusions = []
    for v in violations:
        main_item, aux_item = v['items']
        x, y = main_item['pos']['x'], main_item['pos']['y']
        if v['type'] == 'silk_over_copper':
            # The JSON gives the silk segment start; KiCad's marker sits where the horizontal
            # vactrol-outline segment crosses the lug (lug X, segment Y). Checked by re-running DRC.
            x = aux_item['pos']['x']
        x, y = round(x * 1e6), round(y * 1e6)
        exclusions.append([f"{v['type']}|{x}|{y}|{main_item['uuid']}|{aux_item['uuid']}", COMMENT])
    project = json.loads(PRO.read_text())
    project['board']['design_settings']['drc_exclusions'] = sorted(exclusions)
    PRO.write_text(json.dumps(project, indent=2) + '\n')
    print(f'{len(exclusions)} U7/U8 exclusions written to {PRO.name}')


if __name__ == '__main__':
    main(sys.argv[1])
