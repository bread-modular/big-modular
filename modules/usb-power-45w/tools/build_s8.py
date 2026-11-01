"""Generate the S8 single-board schematic (hardware/single/usb-power-45w-single.kicad_{pro,sch} + 6 pages).

  python3 -B tools/build_s8.py [--output-root <candidate-module-root>]

Circuit table: tools/circuit_s8.py (derived from the untouched S7 table). Same drawing engine as
the S7 system schematic (tools/build_schematic.py flat_sheet + tools/hierarchy_s8.py), so the flat
intermediate is checked pin-for-pin against the table (check_netlist) and the hierarchy against the
flat sheet (exact component/field/pin-membership parity). S8 UUIDs use their own namespace.

Writes only under hardware/single/ (project, root, pages, the project's pinned symbol library and
library tables) and docs/s8-single/ (wiring/parity records). Symbols: the S7 pinned symbols that S8
uses (no new symbol). Footprints: the shared hardware/USBPOWER45.pretty (no new footprint).
"""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
import types
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_schematic as bs  # noqa: E402
import circuit_s8  # noqa: E402
import hierarchy_s8  # noqa: E402
from sexp import parse, dump, one, atom  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
STEM = circuit_s8.PROJECT
POWER_SYMBOLS = {'GND', 'VCC', '+12V', '+5V', '-12V'}


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/usb-power-45w/s8-single/schematic/' + key))


def single_dir(root=MODULE):
    return Path(root) / 'hardware' / 'single'


def root_file(root=MODULE):
    return single_dir(root) / f'{STEM}.kicad_sch'


def lib_symbols(parts):
    """The S7 pinned symbols (tools/build_schematic.py SYMBOLS) that S8 uses, flattened the same way."""
    used = {p['sym'] for p in parts} | POWER_SYMBOLS
    out = {k: v for k, v in bs.lib_symbols().items() if k in used}
    assert used <= set(out), sorted(used - set(out))
    return out


def build(output_root=None):
    root = Path(output_root).resolve() if output_root else MODULE
    hw = single_dir(root)
    docs = root / 'docs' / 's8-single'
    hw.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    bs.uid = uid                                   # S8 namespace for every generated UUID
    parts = circuit_s8.circuit()
    syms = lib_symbols(parts)
    lib = [atom('kicad_symbol_lib'), one(parse((bs.STOCK / 'Device.kicad_sym').read_text()), 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(syms[k]) for k in sorted(syms)]
    (hw / f'{bs.LIB}.kicad_sym').write_text(dump(lib) + '\n')
    (hw / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{bs.LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{bs.LIB}.kicad_sym") '
        '(options "") (descr "usb-power-45w S8 pinned symbols; see tools/build_s8.py")))\n')
    (hw / 'fp-lib-table').write_text(
        f'(fp_lib_table (version 7) (lib (name "{bs.LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/../{bs.LIB}.pretty") '
        '(options "") (descr "usb-power-45w pinned footprints, shared with the S7 projects")))\n')

    # Project file first: kicad-cli loads it when re-saving the sheets, so every run sees the same project.
    out = root_file(root)
    pro = hw / f'{STEM}.kicad_pro'
    meta = json.loads((root / 'hardware' / 'usb-power-45w-system.kicad_pro').read_text())
    meta['meta']['filename'] = pro.name
    meta['schematic']['top_level_sheets'] = [{'filename': out.name, 'name': out.stem, 'uuid': uid('root')}]
    meta['sheets'] = []
    pro.write_text(json.dumps(meta, indent=2) + '\n')

    sch, nets, _ = bs.flat_sheet(
        parts, syms, project=STEM, key='root', title='Big Modular - usb-power-45w S8 single board',
        comments=('S8 final: single board, no per-rail eFuses, ceramic bulk, two output headers, OV guard, MAIN LED only',
                  'Design notes and pre-calculations: docs/s8-single-board.md'),
        source=circuit_s8.drawing(), texts=circuit_s8.TEXTS)
    one(one(sch, 'title_block'), 'rev')[1] = 'S8 final'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True, stdout=subprocess.DEVNULL)
    nc = {f"{p['ref']}/{n}" for p in parts for n, net in p['pins'].items() if net is None}
    bs.check_netlist(out, nets, nc)
    api = types.SimpleNamespace(circuit=circuit_s8.circuit, pin_table=bs.pin_table, xform=bs.xform,
                                outward=bs.outward, uid=uid, PROJECT=STEM)
    crossing = hierarchy_s8.split(out, docs, api)

    refs = sorted(p['ref'] for p in parts if not p['ref'].startswith('#'))
    record = {'revision': 'S8 final', 'project': f'hardware/single/{pro.name}', 'components': len(refs),
              'nets': len(nets), 'no_connect_pins': len(nc), 'removed_from_S7': sorted(circuit_s8.S8_REMOVED),
              'inter_sheet_nets': {n: sorted(p) for n, p in sorted(crossing.items())},
              'symbols': sorted(syms),
              'library_sha256': hashlib.sha256((hw / f'{bs.LIB}.kicad_sym').read_bytes()).hexdigest()}
    (docs / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    print(out, f'{len(nets)} nets, {len(refs)} parts')
    return record


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-root', type=Path, help='Explicit candidate module root; default is this module')
    build(ap.parse_args().output_root)
