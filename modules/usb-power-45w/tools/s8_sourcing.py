"""S8 sourcing snapshot through the shared read-only JLCPCB lookup (opt/kicad-tools/jlcpcb/assembly.py).

  python3 -B tools/s8_sourcing.py --out docs/s8-single/sourcing.json [--cache-dir research/s8/sourcing]
  python3 -B tools/s8_sourcing.py --out docs/s8-single/sourcing.json --from-snapshot docs/s8-single/sourcing.json

Looks up every LCSC code of the S8 table (and of the S7 parts S8 removes, for the delta) with
--strict-live, one request per code, and records classification, Economic eligibility, stock and
the quantity-1 unit price with the tool's own evidence (URL, UTC time, response hash). A dated
public-catalog observation, not a reservation, quote or order acceptance. --from-snapshot reuses the
recorded rows (same codes, same dated evidence, no network) and only recomputes quantities and totals
for the current table; it refuses if the table uses a code the snapshot does not have.
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
            'evidence': p.get('evidence'), 'failures': d.get('failures')}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cache-dir', type=Path)
    ap.add_argument('--from-snapshot', type=Path, help='reuse the rows of an earlier output (offline)')
    a = ap.parse_args()
    snap = json.loads(a.from_snapshot.read_text()) if a.from_snapshot else None
    s8 = [p for p in circuit_s8.circuit() if not p['ref'].startswith('#')]
    s7 = [p for p in circuit45.circuit() if not p['ref'].startswith('#')]
    use8 = Counter(p['fields']['LCSC'] for p in s8 if p['fields'].get('LCSC'))
    use7 = Counter(p['fields']['LCSC'] for p in s7 if p['fields'].get('LCSC'))
    codes = sorted(set(use8) | set(use7))
    rows = {}
    if snap:
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
                 'and totals recomputed for the S8 final table (rail LEDs removed, no new code).')
    out = {'note': note,
           'codes': rows,
           'summary': {'S8_codes': len(use8), 'S7_codes': len(use7),
                       'S8_placements': sum(use8.values()), 'S7_placements': sum(use7.values()),
                       'S8_parts_usd_q1': total('S8'), 'S7_parts_usd_q1': total('S7'),
                       'S8_non_basic_codes': ext('S8'), 'S7_non_basic_codes': ext('S7'),
                       'manual_parts_no_LCSC': manual,
                       'failures': sorted(c for c, r in rows.items() if r.get('error') or r.get('failures'))}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out['summary'], indent=1))


if __name__ == '__main__':
    main()
