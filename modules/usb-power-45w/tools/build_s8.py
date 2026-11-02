"""Generate the S8 single-board schematic (hardware/single/usb-power-45w-single.kicad_{pro,sch} + 6 pages).

  python3 -B tools/build_s8.py [--output-root <candidate-module-root>]

Circuit table: tools/circuit_s8.py (derived from the untouched S7 table). Same drawing engine as
the S7 system schematic (tools/build_schematic.py flat_sheet + tools/hierarchy_s8.py), so the flat
intermediate is checked pin-for-pin against the table (check_netlist) and the hierarchy against the
flat sheet (exact component/field/pin-membership parity). S8 UUIDs use their own namespace.

Writes a separate review candidate with --output-root. S8.3 replaced the S8.2 crowbar
with the pinned TPS259470 symbol/land pattern in tools/s83_parts.py; S8.4 applies the review
fixes listed in tools/circuit_s8.py; S8.5 wires the one-shot arming latch (circuit_s8.py docstring,
item B). S9.0 removes the +5V subsystem (the S8.3 TPS259470 symbol/land pattern, tools/s83_parts.py, is gone with
U23) and the +5V power symbol. Shared S7 symbols, footprints and native projects are not rewritten.
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
from sexp import parse, dump, nodes, one, atom, walk  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
STEM = circuit_s8.PROJECT
POWER_SYMBOLS = {'GND', 'VCC', '+12V', '-12V'}     # S9.0: no +5V symbol
REV = 'S9.2'
from s90_parts import FP_S90, symbol as buckboost_symbol  # noqa: E402
import s92_contract  # noqa: E402
import s92_parts  # noqa: E402
FP_S8 = {**bs.FP, **FP_S90, **s92_parts.FP_S92}
# S9.2 routing contract (docs/s8-single/routing-notes.md 3.2): netclasses by net-name pattern, owned by
# tools/s92_contract.py NETCLASSES (also written by tools/place_s8.py --apply-rules), so a schematic rebuild writes the
# same classes. Every class keeps the 0.2 mm board clearance; patterns match the full hierarchical net names.
NETCLASSES = {name: (c['width'], c['patterns']) for name, c in s92_contract.NETCLASSES.items()}


def routing_netclasses(meta):
    """Write the S9.2 netclasses into a project dict (tools/s92_contract.py project_netclasses)."""
    return s92_contract.project_netclasses(meta)


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/usb-power-45w/s8-single/schematic/' + key))


def single_dir(root=MODULE):
    return Path(root) / 'hardware' / 'single'


def root_file(root=MODULE):
    return single_dir(root) / f'{STEM}.kicad_sch'


def tlv431_dbz():
    """U21 symbol: KiCad stock Reference_Voltage:TL431DBZ (K 1, REF 2, A 3 = the TL431 DBZ order) with the pins
    renumbered by name to the TI TLV431 DBZ package, SLVS139Z Table 4-1 (REF 1, CATHODE 2, ANODE 3)."""
    sym, _, _ = bs.stock_symbol('Reference_Voltage', 'TL431DBZ')
    pins = list(walk(sym, 'pin'))
    assert sorted(one(p, 'name')[1] for p in pins) == sorted(circuit_s8.TLV431_DBZ_PINS), 'TL431DBZ pin names changed'
    for p in pins:
        one(p, 'number')[1] = circuit_s8.TLV431_DBZ_PINS[one(p, 'name')[1]]
    props = {pp[1]: pp for pp in nodes(sym, 'property')}
    props['Value'][2] = 'TLV431_DBZ'
    props['Datasheet'][2] = 'https://www.ti.com/lit/ds/symlink/tlv431.pdf'
    props['Description'][2] = 'Shunt regulator 1.24 V, SOT-23 TI DBZ pinout (REF 1, CATHODE 2, ANODE 3)'
    sym[1] = 'TLV431_DBZ'
    for u in nodes(sym, 'symbol'):
        u[1] = 'TLV431_DBZ_' + '_'.join(u[1].rsplit('_', 2)[-2:])
    return sym


def lib_symbols(parts):
    """The S7 pinned symbols (tools/build_schematic.py SYMBOLS) that S8 uses, flattened the same way, plus
    the S8.1 TLV431_DBZ symbol and the S9.0 TPS552892_RYQ symbol (tools/s90_parts.py)."""
    used = {p['sym'] for p in parts} | POWER_SYMBOLS
    out = {k: v for k, v in bs.lib_symbols().items() if k in used}
    if 'TLV431_DBZ' in used:
        out['TLV431_DBZ'] = tlv431_dbz()
    if 'TPS552892_RYQ' in used:
        out['TPS552892_RYQ'] = buckboost_symbol()
    if 'R_Shunt' in used:                          # S9.2 R109: KiCad stock Device:R_Shunt (1/4 force, 2/3 sense)
        sym, _, _ = bs.stock_symbol('Device', 'R_Shunt')
        sym[1] = 'R_Shunt'
        for u in nodes(sym, 'symbol'):
            u[1] = 'R_Shunt_' + '_'.join(u[1].rsplit('_', 2)[-2:])
        out['R_Shunt'] = sym
    assert used <= set(out), sorted(used - set(out))
    return out


def build(output_root=None):
    root = Path(output_root).resolve() if output_root else MODULE
    hw = single_dir(root)
    docs = root / 'docs' / 's8-single'
    hw.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    bs.FP = dict(FP_S8)
    bs.uid = uid                                   # S8 namespace for every generated UUID
    parts = circuit_s8.circuit()
    bs.NOT_ASSEMBLED = set(bs.NOT_ASSEMBLED) | {p['ref'] for p in parts if p['ref'].startswith('TP')}   # TP17
    bs.TEXT_POS = {**bs.TEXT_POS, **circuit_s8.TEXT_POS_S8}
    bs.MIRROR_X = set(bs.MIRROR_X) | circuit_s8.MIRROR_S8
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
    meta = json.loads((pro if pro.exists() else root / 'hardware' / 'usb-power-45w-system.kicad_pro').read_text())
    meta['meta']['filename'] = pro.name
    meta['schematic']['top_level_sheets'] = [{'filename': out.name, 'name': out.stem, 'uuid': uid('root')}]
    meta['sheets'] = []
    pro.write_text(json.dumps(routing_netclasses(meta), indent=2) + '\n')
    if (root / 'hardware' / 'USBPOWER45.pretty').is_dir():
        s92_parts.write(root / 'hardware' / 'USBPOWER45.pretty')      # S9.2 pinned footprints (Kelvin land, 1.5 mm pad)

    sch, nets, _ = bs.flat_sheet(
        parts, syms, project=STEM, key='root', title='Big Modular - usb-power-45w S8 single board',
        comments=('S9.2 single board: +/-12V only, 15 V PD; MAIN LED only; routing-ready, not routed',
                  'One-shot arming latch (STARTED); U18/U20 on VPD; see docs/s8-single-board.md'),
        source=circuit_s8.drawing(), texts=circuit_s8.TEXTS)
    one(one(sch, 'title_block'), 'rev')[1] = REV
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True, stdout=subprocess.DEVNULL)
    nc = {f"{p['ref']}/{n}" for p in parts for n, net in p['pins'].items() if net is None}
    bs.check_netlist(out, nets, nc)
    api = types.SimpleNamespace(circuit=circuit_s8.circuit, pin_table=bs.pin_table, xform=bs.xform,
                                outward=bs.outward, uid=uid, PROJECT=STEM)
    crossing = hierarchy_s8.split(out, docs, api)

    refs = sorted(p['ref'] for p in parts if not p['ref'].startswith('#'))
    record = {'revision': REV, 'project': f'hardware/single/{pro.name}', 'components': len(refs),
              'nets': len(nets), 'no_connect_pins': len(nc),
              'removed_from_S7': sorted(set(circuit_s8.S8_REMOVED) | set(circuit_s8.S9_REMOVED)),
              'removed_in_S9_plus5': sorted(set(circuit_s8.S9_REMOVED) | set(circuit_s8.S8_PLUS5_DROPPED)),
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
