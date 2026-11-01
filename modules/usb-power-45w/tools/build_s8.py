"""Generate the S8 single-board schematic (hardware/single/usb-power-45w-single.kicad_{pro,sch} + 6 pages).

  python3 -B tools/build_s8.py [--output-root <candidate-module-root>]

Circuit table: tools/circuit_s8.py (derived from the untouched S7 table). Same drawing engine as
the S7 system schematic (tools/build_schematic.py flat_sheet + tools/hierarchy_s8.py), so the flat
intermediate is checked pin-for-pin against the table (check_netlist) and the hierarchy against the
flat sheet (exact component/field/pin-membership parity). S8 UUIDs use their own namespace.

Writes only under hardware/single/ (project, root, pages, the project's pinned symbol library and
library tables) and docs/s8-single/ (wiring/parity records). Symbols: the S7 pinned symbols that S8
uses plus one S8.1 symbol, TLV431_DBZ (tlv431_dbz() below: the stock TL431DBZ drawing with the TI
TLV431 DBZ pin numbers; tools/verify_s8.py checks them against TI's table), and the S8.2 crowbar symbols:
TLVH432_DBZ (the stock TL431DBZ drawing, whose numbers already are the TLVH432 DBZ pinout) and the stock
Device:Q_SCR_KAG, Transistor_FET:AO3401A and Transistor_BJT:MMBT3904. Footprints: the shared
hardware/USBPOWER45.pretty (no new footprint; the crowbar SCR uses the pinned TO-252-2).
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
POWER_SYMBOLS = {'GND', 'VCC', '+12V', '+5V', '-12V'}
S8_STOCK = {'Q_SCR_KAG': ('Device', 'Q_SCR_KAG'), 'AO3401A': ('Transistor_FET', 'AO3401A'),
            'MMBT3904': ('Transistor_BJT', 'MMBT3904')}      # S8.2 crowbar (stock, flattened as the S7 symbols)


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


def tlvh432_dbz():
    """U22 symbol: KiCad stock Reference_Voltage:TL431DBZ unchanged. Its numbers (K 1, REF 2, A 3) are the TI TLVH432
    DBZ pinout (SLVS555N Pin Functions: CATHODE 1, REF 2, ANODE 3); only value, datasheet and description change."""
    sym, _, _ = bs.stock_symbol('Reference_Voltage', 'TL431DBZ')
    pins = {one(p, 'name')[1]: one(p, 'number')[1] for p in walk(sym, 'pin')}
    assert pins == circuit_s8.TLVH432_DBZ_PINS, ('TL431DBZ pin numbers changed', pins)
    props = {pp[1]: pp for pp in nodes(sym, 'property')}
    props['Value'][2] = 'TLVH432_DBZ'
    props['Datasheet'][2] = 'https://www.ti.com/lit/ds/symlink/tlvh431.pdf'
    props['Description'][2] = 'Shunt regulator 1.24 V, 18 V cathode, SOT-23 TI TLVH432 DBZ pinout (CATHODE 1, REF 2, ANODE 3)'
    return rename(sym, 'TLVH432_DBZ')


def rename(sym, key):
    sym[1] = key
    for u in nodes(sym, 'symbol'):
        u[1] = key + '_' + '_'.join(u[1].rsplit('_', 2)[-2:])
    return sym


def lib_symbols(parts):
    """The S7 pinned symbols (tools/build_schematic.py SYMBOLS) that S8 uses, flattened the same way, plus
    the S8.1 TLV431_DBZ symbol and the S8.2 crowbar symbols."""
    used = {p['sym'] for p in parts} | POWER_SYMBOLS
    out = {k: v for k, v in bs.lib_symbols().items() if k in used}
    if 'TLV431_DBZ' in used:
        out['TLV431_DBZ'] = tlv431_dbz()
    if 'TLVH432_DBZ' in used:
        out['TLVH432_DBZ'] = tlvh432_dbz()
    for key, (lib, name) in S8_STOCK.items():
        if key in used:
            out[key] = rename(bs.stock_symbol(lib, name)[0], key)
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
    bs.NOT_ASSEMBLED = set(bs.NOT_ASSEMBLED) | {p['ref'] for p in parts if p['ref'].startswith('TP')}   # TP17
    bs.TEXT_POS = {**bs.TEXT_POS, **circuit_s8.TEXT_POS_S8}
    bs.MIRROR_X = set(bs.MIRROR_X) | circuit_s8.MIRROR_S8                                    # Q12 source up
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
        comments=('S8.2: single board, no per-rail eFuses, ceramic bulk, two output headers, OV guard, MAIN LED only',
                  'S8.1 review fixes (guard reference U21, LM2901B, 0.1 % dividers, clamp D22) + S8.2 +5V crowbar Q11 - '
                  'docs/s8-single-board.md'),
        source=circuit_s8.drawing(), texts=circuit_s8.TEXTS)
    one(one(sch, 'title_block'), 'rev')[1] = 'S8.2'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True, stdout=subprocess.DEVNULL)
    nc = {f"{p['ref']}/{n}" for p in parts for n, net in p['pins'].items() if net is None}
    bs.check_netlist(out, nets, nc)
    api = types.SimpleNamespace(circuit=circuit_s8.circuit, pin_table=bs.pin_table, xform=bs.xform,
                                outward=bs.outward, uid=uid, PROJECT=STEM)
    crossing = hierarchy_s8.split(out, docs, api)

    refs = sorted(p['ref'] for p in parts if not p['ref'].startswith('#'))
    record = {'revision': 'S8.2', 'project': f'hardware/single/{pro.name}', 'components': len(refs),
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
