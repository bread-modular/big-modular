"""Native per-board schematics for the R2 stacked boards, derived from the S7 circuit table.

  python3 -B tools/board_schematics.py [--output-root <candidate-module-root>]

Writes hardware/usb-power-45w.kicad_sch (BASE, the main project) and
hardware/usb-power-45w-top.kicad_sch (TOP) (one wired flat sheet each, same drawing engine and coordinates as the verified S7 flat
intermediate). Each sheet holds exactly the board's share of the S7 circuit table
(tools/stack_r2.py) plus its two board-to-board headers. Drawn wires that led to the other
board are dropped; the pins they served are re-joined by their net's power symbol or label.
Every native netlist is checked against the board's table, and the aggregate proof
(both boards joined pin-for-pin through the headers == the S7 root netlist) is
tools/check_stack.py's job. The S7 hierarchy (hardware/usb-power-45w-system.kicad_sch) stays the
readable, authoritative circuit.

Header-fed supply nets: a board whose supply only arrives through the header pins gets ONE
PWR_FLAG per such net (refs #FLGB../#FLGT..), placed at the header pin. That is KiCad's way of
marking an external source (here: the other board); flags are added only where native ERC
reports an undriven power input on that board, and each one is listed in HEADER_FED.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_schematic as bs  # noqa: E402
import circuit45  # noqa: E402
from circuit45 import part  # noqa: E402
from sexp import dump  # noqa: E402
import stack_r2 as st  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
# Supply nets that reach the board only through its header (net -> header pin). The flag is the
# KiCad marker for "driven from outside this sheet"; see the module docstring.
HEADER_FED = {'top': {'GND': 'XT1.1', 'VIN': 'XT1.3', 'V3V3': 'XT2.6'},
              'base': {'+12V': 'XB1.9', '+5V': 'XB1.15', 'N12_RAW': 'XB1.19'}}


def board_drawing(refs):
    """S7 drawing() restricted to one board: a polyline / symbol / label that names a pin of the
    other board is dropped (its pins are re-labelled by the engine)."""
    wires, power, labels = circuit45.drawing()

    def ok(pt):
        if isinstance(pt, str):
            return pt.split('.')[0] in refs
        if isinstance(pt[0], str):
            return pt[0].split('.')[0] in refs
        return True
    return ([w for w in wires if all(ok(p) for p in w)],
            [x for x in power if ok(x[1])], [x for x in labels if ok(x[1])])


def build(output_root=None):
    root = Path(output_root).resolve() if output_root else MODULE
    hw = root / 'hardware'
    parts = circuit45.circuit()
    side = st.board_of(parts)
    lib = bs.lib_symbols()
    report = {}
    for board in ('base', 'top'):
        hw.mkdir(parents=True, exist_ok=True)
        project = st.STEM[board]   # = the board project's name (native save relabels instances to it)
        pro = st.board_file(board, '.kicad_pro', root)
        if not pro.exists():     # board project: rules copied from the system project, sheet record below
            shutil.copy(hw / f'{st.SYSTEM_STEM}.kicad_pro', pro)
        # Library tables: the module's hardware/sym-lib-table and fp-lib-table (shared by all projects).
        sub = [p for p in parts if side[p['ref']] == board]
        sub += st.header_parts(board, part)
        hdr = {h[0]: h for h in st.HEADERS[board]}
        for i, (net, pin) in enumerate(sorted(HEADER_FED[board].items())):
            ref = f'#FLG{board[0].upper()}{i + 1:02d}'
            x, y = sub[[p['ref'] for p in sub].index(next(iter(hdr)))]['at']
            sub.append(part(ref, 'PWR_FLAG', 'PWR_FLAG', None, (x - 30.48, y - 20.32 + 10.16 * i), 0, {'1': net}))
        refs = {p['ref'] for p in sub}
        title = f'usb-power-45w {board.upper()} board (R2 stack) - derived from S7'
        comments = (f'{board.upper()} share of the S7 circuit + board-to-board headers; tools/board_schematics.py',
                    f'Authoritative readable circuit: {st.SYSTEM_STEM}.kicad_sch (S7 hierarchy)',
                    'Header pins: tools/stack_r2.py; aggregate proof: tools/check_stack.py')
        sch, nets, _ = bs.flat_sheet(sub, lib, project=project, key=f'R2/{board}/root', title=title,
                                     comments=comments, source=board_drawing(refs), texts=[])
        out = st.board_file(board, '.kicad_sch', root)
        out.write_text(dump(sch) + '\n')
        subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True, stdout=subprocess.DEVNULL)
        meta = json.loads(pro.read_text())   # copied root project: point its sheet record at this root
        meta['schematic']['top_level_sheets'] = [{'filename': out.name, 'name': out.stem,
                                                  'uuid': bs.uid(f'R2/{board}/root')}]
        pro.write_text(json.dumps(meta, indent=2) + '\n')
        nc = {f"{p['ref']}/{n}" for p in sub for n, net in p['pins'].items() if net is None}
        bs.check_netlist(out, nets, nc)
        report[board] = {'refs': len([r for r in refs if not r.startswith('#')]),
                         'flags': sorted(r for r in refs if r.startswith('#FLG')), 'nets': len(nets)}
        print(out, report[board])
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-root', type=Path)
    print(json.dumps(build(ap.parse_args().output_root)))
