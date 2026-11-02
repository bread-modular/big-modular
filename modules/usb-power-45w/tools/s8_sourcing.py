"""S8 sourcing snapshot through the shared read-only JLCPCB lookup (opt/kicad-tools/jlcpcb/assembly.py).

  python3 -B tools/s8_sourcing.py --out docs/s8-single/sourcing.json [--cache-dir research/s8/sourcing]
  python3 -B tools/s8_sourcing.py --out docs/s8-single/sourcing.json --from-snapshot docs/s8-single/sourcing.json

Looks up every LCSC code of the S8 table (and of the S7 parts S8 removes, for the delta) with
--strict-live, one request per code, and records classification, Economic eligibility, stock and
the quantity-1 unit price with the tool's own evidence (URL, UTC time, response hash). A dated
public-catalog observation, not a reservation, quote or order acceptance. --from-snapshot reuses the
recorded rows (same codes, same dated evidence, no network) and only recomputes quantities and totals
for the current table; it refuses if the table uses a code the snapshot does not have.

S8.4: --selected writes a live exact-code evidence file for selected/changed parts (with the full price
ladder and the references that use each code) plus the Basic-only passive-policy decision (review M8);
--extra-snapshot merges such a file's rows into a --from-snapshot run, so new codes need no full re-audit.

  python3 -B tools/s8_sourcing.py --selected C705793 C861121 ... --out docs/s8-single/s84-sourcing.json \
      --cache-dir research/s84/catalog-current
  python3 -B tools/s8_sourcing.py --out docs/s8-single/sourcing.json --from-snapshot docs/s8-single/sourcing.json \
      --extra-snapshot docs/s8-single/s84-sourcing.json
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import circuit45  # noqa: E402
import circuit_s8  # noqa: E402

REPO = HERE.parents[2]
TOOL = REPO / 'opt/kicad-tools/jlcpcb/assembly.py'


def lookup(code, cache):
    cmd = [sys.executable, '-B', str(TOOL), 'lookup', code, '--strict-live', '--max-requests', '1', '--timeout', '20']
    if cache:
        cmd += ['--cache-dir', str(cache)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {'code': code, 'error': (r.stderr or r.stdout)[-400:]}
    p = d.get('part') or {}
    prices = p.get('prices') or [{}]
    return {'code': code, 'mpn': p.get('mpn'), 'manufacturer': p.get('manufacturer'), 'package': p.get('package'),
            'classification': p.get('classification'), 'economy_eligible': p.get('economy_eligible'),
            'stock': p.get('stock'), 'unit_price_q1_usd': prices[0].get('unit_price'),
            'price_ladder_usd': [[q.get('start'), q.get('end'), q.get('unit_price')] for q in prices if q],
            'evidence': p.get('evidence'), 'failures': d.get('failures')}


# S8.4 (review M8): Basic-only passive policy decision for the 0.1 % thin-film dividers. Numbers: calcs.json
# basic_only_counterfactual (what the threshold screens become with 1 % Basic parts).
PRECISION_POLICY = {
    'decision': 'ACCEPT Extended for the 0.1 % / 25 ppm thin-film dividers only (documented exception); every other '
                'passive stays Basic. Not an order approval.',
    'refs': ['R93', 'R94', 'R98', 'R99'],
    'why': 'They set protection thresholds: the U20 overvoltage guard bands (+12V R93/R94, -12V R98/R99). With 1 % + 1 % '
           'TCR Basic parts the -12V guard minimum falls below the stacked converter peak (calcs.json '
           'basic_only_counterfactual). The searched JLC catalog has no Basic 0.1 % 0603 resistor (S8.4 keyword '
           'snapshots; every hit Extended). S9.0: the +5V precision parts (R95/R96, R101/R102, R11/R12) left with +5V.',
    'cost': 'Extended per-unique-part fees apply to the precision codes (not included in the q1 parts totals); all '
            'selected codes were observed Economic-eligible.',
    'not_done': 'No Basic substitute was qualified; replacing them with 1 % parts would need a new threshold design.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cache-dir', type=Path)
    ap.add_argument('--from-snapshot', type=Path, help='reuse the rows of an earlier output (offline)')
    ap.add_argument('--extra-snapshot', type=Path, action='append', default=[],
                    help='with --from-snapshot: also reuse the rows of a selected-part evidence file')
    ap.add_argument('--selected', nargs='+', help='S8.4: live exact-code rows for these codes only (evidence file)')
    a = ap.parse_args()
    if a.selected:
        return selected(a)
    snap = json.loads(a.from_snapshot.read_text()) if a.from_snapshot else None
    s8 = [p for p in circuit_s8.circuit() if not p['ref'].startswith('#')]
    s7 = [p for p in circuit45.circuit() if not p['ref'].startswith('#')]
    use8 = Counter(p['fields']['LCSC'] for p in s8 if p['fields'].get('LCSC'))
    use7 = Counter(p['fields']['LCSC'] for p in s7 if p['fields'].get('LCSC'))
    codes = sorted(set(use8) | set(use7))
    rows = {}
    if snap:
        for extra in a.extra_snapshot:
            for code, row in json.loads(extra.read_text())['codes'].items():
                snap['codes'].setdefault(code, row)
        missing = sorted(set(codes) - set(snap['codes']))
        if missing:
            raise SystemExit(f'snapshot has no row for {missing}: run a live lookup')
    for code in codes:
        if snap:
            rows[code] = {k: v for k, v in snap['codes'][code].items() if not k.startswith('qty_')}
        else:
            rows[code] = lookup(code, a.cache_dir)
        rows[code].update(qty_S8=use8.get(code, 0), qty_S7=use7.get(code, 0))
        print(code, rows[code].get('classification'), rows[code].get('stock'), rows[code].get('unit_price_q1_usd'),
              file=sys.stderr)

    def total(which):
        known = [r for r in rows.values() if r.get(f'qty_{which}') and r.get('unit_price_q1_usd') is not None]
        return round(sum(r['unit_price_q1_usd'] * r[f'qty_{which}'] for r in known), 2)

    def ext(which):
        return sorted(c for c, r in rows.items() if r.get(f'qty_{which}') and r.get('classification') != 'Basic')
    manual = {'S8': sorted(p['ref'] for p in s8 if not p['fields'].get('LCSC') and not p['ref'].startswith('TP')),
              'S7': sorted(p['ref'] for p in s7 if not p['fields'].get('LCSC') and not p['ref'].startswith('TP'))}
    note = ('Public JLCPCB catalog lookups via the shared tool, --strict-live, one request per code. Stock '
            'and price are dated observations, not reservations, quotes or order acceptance. Quantity-1 '
            'unit prices only: no setup/Extended fees, attrition, manual parts, PCB or shipping.')
    if snap:
        note += (' Rows reused offline from the earlier snapshot (see each evidence.retrieved_at_utc); quantities '
                 'and totals recomputed for the current S8 table. This is not a full live re-audit.')
    if a.extra_snapshot:
        note += (' S8.4: rows of new codes come from the live selected-part evidence ' +
                 ', '.join(str(x.name) for x in a.extra_snapshot) + '.')
    out = {'note': note,
           'codes': rows,
           'summary': {'S8_codes': len(use8), 'S7_codes': len(use7),
                       'S8_placements': sum(use8.values()), 'S7_placements': sum(use7.values()),
                       'S8_parts_usd_q1': total('S8'), 'S7_parts_usd_q1': total('S7'),
                       'S8_non_basic_codes': ext('S8'), 'S7_non_basic_codes': ext('S7'),
                       'manual_parts_no_LCSC': manual,
                       'failures': sorted(c for c, r in rows.items() if r.get('error') or r.get('failures'))},
           'basic_only_policy': PRECISION_POLICY}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out['summary'], indent=1))


def selected(a):
    """S8.4: live exact-code evidence for the selected/changed parts (no totals)."""
    s8 = [p for p in circuit_s8.circuit() if not p['ref'].startswith('#')]
    refs = {}
    for p in s8:
        if p['fields'].get('LCSC'):
            refs.setdefault(p['fields']['LCSC'], []).append(p['ref'])
    rows = {}
    for code in a.selected:
        rows[code] = lookup(code, a.cache_dir)
        rows[code]['refs_S8'] = sorted(refs.get(code, []), key=lambda r: (r[0], int(r[1:])))
        print(code, rows[code].get('classification'), rows[code].get('stock'), rows[code].get('unit_price_q1_usd'),
              file=sys.stderr)
    out = {'note': 'S8.4 live exact-code rows (shared --strict-live lookup, one request per code) for the parts the S8.4 '
                   'review fixes add or change (R11/R12 0.1 %, R83 200k, R108) and re-checks of U23, D21, D23, U18/U20 '
                   'and the existing 0.1 % codes, with full price ladders. Raw snapshots: research/s84/catalog-current. '
                   'Dated public-catalog observations, not reservations, quotes or order acceptance.',
           'codes': rows, 'basic_only_policy': PRECISION_POLICY,
           'failures': sorted(c for c, r in rows.items() if r.get('error') or r.get('failures'))}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({c: [r.get('classification'), r.get('stock'), r.get('unit_price_q1_usd'), r.get('refs_S8')]
                      for c, r in rows.items()}, indent=1))
    return out


if __name__ == '__main__':
    main()
