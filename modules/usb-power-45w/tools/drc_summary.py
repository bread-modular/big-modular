"""Native DRC (all severities, schematic parity) summary for the R2 stacked boards.

  python3 -B tools/drc_summary.py <reports-dir> [base|top ...]
Raw kicad-cli JSON stays in <reports-dir> (use the ignored research/ area)."""
import collections
import json
import subprocess
import sys
from pathlib import Path

HW = Path(__file__).resolve().parents[1] / 'hardware'


def drc(board, out):
    rep = Path(out) / f'drc-{board}.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--schematic-parity', '--format', 'json',
                    '-o', str(rep), str(HW / board / f'usb-power-45w-{board}.kicad_pcb')],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.loads(rep.read_text())
    kinds = collections.Counter(f"{v['severity']}:{v['type']}" for v in d['violations'])
    return {'violations': dict(kinds), 'unconnected': len(d['unconnected_items']),
            'parity': len(d['schematic_parity']),
            'excluded': sum(1 for v in d['violations'] if v.get('excluded')),
            'details': [(v['type'], [i['description'][:60] for i in v['items']]) for v in d['violations']
                        + d['schematic_parity']]}


if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for b in sys.argv[2:] or ['base', 'top']:
        r = drc(b, out)
        print(b, r['violations'], 'unconnected', r['unconnected'], 'parity', r['parity'], 'excluded', r['excluded'])
        for t, items in r['details']:
            print('   ', t, items)
