#!/usr/bin/env python3
"""Generate the local symbol/footprint library and the schematic.

    python3 -B opt/updi-programmer/tools/build_schematic.py --refresh-library
    python3 -B opt/updi-programmer/tools/build_schematic.py

--refresh-library re-copies the symbols/footprints listed in design.py from
the KiCad 10 installation (and modules/usb-power for the HRO USB-C part) into
hardware/UPDIProgrammer.{kicad_sym,pretty}. Without it only the committed
local library is read, so the schematic is reproducible offline.
"""
import argparse
import copy
import math
import os
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design as D  # noqa: E402
from sexp import Sym, dump, nodes, one, parse  # noqa: E402

HERE = Path(__file__).resolve().parent
HW = HERE.parent / 'hardware'
REPO = HERE.parents[2]
SYMLIB = HW / (D.LIB + '.kicad_sym')
FPLIB = HW / (D.LIB + '.pretty')
SCH = HW / (D.PROJECT + '.kicad_sch')
NS = uuid.UUID('5b1c7d1e-6a43-4c55-9d1e-3c1b8f6a0b10')
STUB = 2.54


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(map(str, parts))))


def expand(path):
    env = {'KICAD10_SYMBOL_DIR': os.environ.get('KICAD10_SYMBOL_DIR', '/usr/share/kicad/symbols'),
           'KICAD10_FOOTPRINT_DIR': os.environ.get('KICAD10_FOOTPRINT_DIR', '/usr/share/kicad/footprints'),
           'REPO': str(REPO)}
    for k, v in env.items():
        path = path.replace('${%s}' % k, v)
    return Path(path)


# ---------------------------------------------------------------------------
# Library refresh
# ---------------------------------------------------------------------------
def _find_symbol(tree, name):
    for s in nodes(tree, 'symbol'):
        if s[1] == name:
            return s
    raise KeyError(name)


def _flatten(tree, name, local):
    """Return a standalone copy of `name` renamed to `local` (resolves extends)."""
    sym = copy.deepcopy(_find_symbol(tree, name))
    ext = one(sym, 'extends')
    if ext:
        parent = _flatten(tree, ext[1], local)
        child_props = {p[1]: p for p in nodes(sym, 'property')}
        out = [x for x in parent if not (isinstance(x, list) and x[0] == 'property')]
        props = [child_props.get(p[1], p) for p in nodes(parent, 'property')]
        props += [p for k, p in child_props.items() if k not in {x[1] for x in props}]
        first_sub = next(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == 'symbol')
        sym = out[:first_sub] + props + out[first_sub:]
    old = sym[1]
    sym[1] = local
    for sub in nodes(sym, 'symbol'):
        sub[1] = local + sub[1][len(old):] if sub[1].startswith(old) else sub[1]
    return sym


def refresh_library():
    trees = {}
    syms = []
    for local, src, name in D.SYMBOL_SOURCES:
        path = expand(src)
        if path not in trees:
            trees[path] = parse(path.read_text())
        s = _flatten(trees[path], name, local)
        for p in nodes(s, 'property'):
            if p[1] == 'Footprint' and p[2]:
                p[2] = D.LIB + ':' + p[2].split(':', 1)[-1]
        syms.append(s)
    lib = [Sym('kicad_symbol_lib'), [Sym('version'), Sym('20241209')],
           [Sym('generator'), 'updi_programmer_build'], [Sym('generator_version'), '10.0']] + syms
    SYMLIB.write_text(dump(lib) + '\n')
    if FPLIB.exists():
        shutil.rmtree(FPLIB)
    FPLIB.mkdir()
    for lib_dir, name in D.FOOTPRINT_SOURCES:
        d = expand(lib_dir)
        if not d.is_absolute() or not d.exists():
            d = expand('${KICAD10_FOOTPRINT_DIR}') / lib_dir
        body = (d / (name + '.kicad_mod')).read_text()
        if name in D.MODEL_OVERRIDES:
            old, new = D.MODEL_OVERRIDES[name]
            assert old in body, (name, old)
            body = body.replace(old, new)
        (FPLIB / (name + '.kicad_mod')).write_text(body)
    print('library refreshed:', SYMLIB.name, len(syms), 'symbols;', FPLIB.name,
          len(D.FOOTPRINT_SOURCES), 'footprints')


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def r4(v):
    return round(v + 0.0, 4) + 0.0


def rot(dx, dy, deg):
    """Rotate a screen-space (y down) vector by a symbol rotation `deg`."""
    a = math.radians(deg)
    c, s = round(math.cos(a)), round(math.sin(a))
    return dx * c + dy * s, -dx * s + dy * c


def load_symbols():
    lib = parse(SYMLIB.read_text())
    return {s[1]: s for s in nodes(lib, 'symbol')}


def pins_of(sym):
    out = []
    for sub in nodes(sym, 'symbol'):
        for p in nodes(sub, 'pin'):
            at = one(p, 'at')
            out.append(dict(number=one(p, 'number')[1], name=one(p, 'name')[1],
                            x=float(at[1]), y=float(at[2]), angle=float(at[3]),
                            hidden=bool(one(p, 'hide')) and one(p, 'hide')[1] != 'no',
                            type=p[1]))
    return out


def pin_screen(part_at, pin):
    """Absolute pin point and outward unit direction (screen coordinates)."""
    x, y, r = part_at
    px, py = rot(pin['x'], -pin['y'], r)
    a = math.radians(pin['angle'])
    bx, by = rot(round(math.cos(a)), -round(math.sin(a)), r)
    return (r4(x + px), r4(y + py)), (-bx, -by)


def body_dir(sym):
    """Screen direction a power/flag symbol body extends at rotation 0."""
    p = pins_of(sym)[0]
    a = math.radians(p['angle'])
    return round(math.cos(a)), -round(math.sin(a))


def rotation_for(sym, want):
    for r in (0, 90, 180, 270):
        if rot(*body_dir(sym), r) == want:
            return r
    raise ValueError(want)


# ---------------------------------------------------------------------------
# Schematic writer
# ---------------------------------------------------------------------------
FONT = [Sym('font'), [Sym('size'), 1.27, 1.27]]


def effects(justify=None, hide=False):
    e = [Sym('effects'), copy.deepcopy(FONT)]
    if justify:
        e.append([Sym('justify')] + [Sym(j) for j in justify.split()])
    if hide:
        e.append([Sym('hide'), Sym('yes')])
    return e


def prop(name, value, at, hide=False, justify=None, angle=0):
    # Field angles are stored in the parent symbol frame; callers pass the
    # symbol rotation so the text reads horizontally on the sheet.
    return [Sym('property'), name, value, [Sym('at'), at[0], at[1], angle], effects(justify, hide)]


def place(ref, lib_id, at, props, pin_numbers, root, in_bom=True):
    node = [Sym('symbol'), [Sym('lib_id'), D.LIB + ':' + lib_id], [Sym('at'), at[0], at[1], at[2]],
            [Sym('unit'), 1], [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes' if in_bom else 'no')],
            [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('no')], [Sym('uuid'), uid('sym', ref)]]
    node += props
    for n in sorted(set(pin_numbers), key=lambda v: (len(v), v)):
        node.append([Sym('pin'), n, [Sym('uuid'), uid('pin', ref, n)]])
    node.append([Sym('instances'), [Sym('project'), D.PROJECT,
                 [Sym('path'), '/' + root, [Sym('reference'), ref], [Sym('unit'), 1]]]])
    return node


def wire(a, b, key):
    return [Sym('wire'), [Sym('pts'), [Sym('xy'), a[0], a[1]], [Sym('xy'), b[0], b[1]]],
            [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('default')]], [Sym('uuid'), uid('wire', key)]]


def label(name, at, d, key):
    justify = {(-1, 0): 'right bottom', (1, 0): 'left bottom', (0, -1): 'left bottom', (0, 1): 'right bottom'}[d]
    angle = 90 if d[0] == 0 else 0
    return [Sym('label'), name, [Sym('at'), at[0], at[1], angle], effects(justify), [Sym('uuid'), uid('label', key)]]


def text(s, at, key):
    return [Sym('text'), s, [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), at[0], at[1], 0],
            effects('left bottom'), [Sym('uuid'), uid('text', key)]]


def build_schematic():
    syms = load_symbols()
    root = uid('root')
    items, used, pwr = [], set(), [0]
    fp_lib = {fp for _, fp in D.FOOTPRINT_SOURCES}
    netmap = {}

    def power(net, at, d, key):
        pwr[0] += 1
        sym = syms[net]
        r = rotation_for(sym, d)
        ref = '#PWR%02d' % pwr[0]
        used.add(net)
        txt = (at[0] + 2.54 * d[0], at[1] + 3.81 * d[1]) if d[0] == 0 else (at[0] + 5.08 * d[0], at[1])
        props = [prop('Reference', ref, at, hide=True),
                 prop('Value', net, (r4(txt[0]), r4(txt[1])), angle=r % 180),
                 prop('Footprint', '', at, hide=True), prop('Datasheet', '', at, hide=True),
                 prop('Description', 'Power symbol', at, hide=True)]
        items.append(place(ref, net, (at[0], at[1], r), props, ['1'], root, in_bom=False))

    for ref, part in D.PARTS.items():
        sym = syms[part['sym']]
        used.add(part['sym'])
        x, y, r = part['at']
        pins = pins_of(sym)
        numbers = {p['number'] for p in pins}
        assert numbers == set(part['pins']), (ref, numbers ^ set(part['pins']))
        by_point = {}
        for p in pins:
            pt, d = pin_screen(part['at'], p)
            by_point.setdefault(pt, []).append((p, d))
            netmap[(ref, p['number'])] = part['pins'][p['number']]
        joins = {n: g[0] for g in part.get('join', []) for n in g[1:]}
        stub_end = {}
        for pt, group in by_point.items():
            nets = {part['pins'][p['number']] for p, _ in group}
            assert len(nets) == 1, (ref, pt, nets)
            net = nets.pop()
            d = group[0][1]
            key = '%s.%s' % (ref, group[0][0]['number'])
            if net is None:
                items.append([Sym('no_connect'), [Sym('at'), pt[0], pt[1]], [Sym('uuid'), uid('nc', key)]])
                continue
            end = (r4(pt[0] + STUB * d[0]), r4(pt[1] + STUB * d[1]))
            items.append(wire(pt, end, key))
            stub_end[group[0][0]['number']] = end
            if group[0][0]['number'] in joins:
                continue
            if net in ('GND', '+5V'):
                power(net, end, d, key)
            else:
                items.append(label(net, end, d, key))
        for n, first in joins.items():
            assert part['pins'][n] == part['pins'][first]
            items.append(wire(stub_end[n], stub_end[first], '%s.join.%s' % (ref, n)))
        # fields
        is_flag = ref.startswith('#')
        if r in (90, 270):
            ref_at, val_at = (x, r4(y - 2.54)), (x, r4(y + 2.54))
            ref_j = val_j = None
        elif part['sym'] in ('R', 'C'):
            ref_at, val_at, ref_j, val_j = (r4(x + 2.54), r4(y - 1.27)), (r4(x + 2.54), r4(y + 1.27)), 'left', 'left'
        elif part['sym'] == 'LED':
            ref_at, val_at, ref_j, val_j = (x, r4(y - 3.81)), (x, r4(y + 3.81)), None, None
        else:
            lp = {p[1]: one(p, 'at') for p in nodes(sym, 'property')}
            ref_at = (r4(x + float(lp['Reference'][1])), r4(y - float(lp['Reference'][2])))
            val_at = (r4(x + float(lp['Value'][1])), r4(y - float(lp['Value'][2])))
            ref_j = val_j = None
        if part.get('value_at'):
            val_at, val_j = (r4(x + part['value_at'][0]), r4(y + part['value_at'][1])), None
        datasheet = next((p[2] for p in nodes(sym, 'property') if p[1] == 'Datasheet'), '')
        descr = next((p[2] for p in nodes(sym, 'property') if p[1] == 'Description'), '')
        fa = r % 180
        props = [prop('Reference', ref, ref_at, hide=is_flag, justify=ref_j, angle=fa),
                 prop('Value', part['value'], val_at, justify=val_j, angle=fa),
                 prop('Footprint', (D.LIB + ':' + part['fp']) if part.get('fp') else '', (x, y), hide=True),
                 prop('Datasheet', datasheet, (x, y), hide=True),
                 prop('Description', descr, (x, y), hide=True)]
        if part.get('fp'):
            assert part['fp'] in fp_lib, part['fp']
        for field in ('mpn', 'manufacturer', 'lcsc', 'comment'):
            if part.get(field):
                name = {'mpn': 'MPN', 'manufacturer': 'Manufacturer', 'lcsc': 'LCSC', 'comment': 'Comment'}[field]
                props.append(prop(name, part[field], (x, y), hide=True))
        items.append(place(ref, part['sym'], part['at'], props, numbers, root, in_bom=not is_flag))

    for i, (at, s) in enumerate(D.NOTES):
        items.append(text(s, at, i))

    lib_symbols = [Sym('lib_symbols')]
    for name in sorted(used):
        s = copy.deepcopy(syms[name])
        s[1] = D.LIB + ':' + name
        lib_symbols.append(s)
    tree = [Sym('kicad_sch'), [Sym('version'), Sym('20250114')], [Sym('generator'), 'eeschema'],
            [Sym('generator_version'), '10.0'], [Sym('uuid'), root], [Sym('paper'), 'A4'],
            [Sym('title_block'), [Sym('title'), D.TITLE], [Sym('rev'), D.REV], [Sym('company'), 'Big Modular'],
             [Sym('comment'), 1, 'Circuit derived from Bread Modular UPDIProgrammer 0.3.0 (jtag2updi on ATtiny1616)'],
             [Sym('comment'), 2, 'Generated by opt/updi-programmer/tools/build_schematic.py']],
            lib_symbols] + items + [
        [Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]],
        [Sym('embedded_fonts'), Sym('no')]]
    SCH.write_text(dump(tree) + '\n')
    print('wrote', SCH.relative_to(REPO), len(D.PARTS), 'parts', pwr[0], 'power symbols')
    return netmap


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--refresh-library', action='store_true')
    a = ap.parse_args()
    HW.mkdir(exist_ok=True)
    if a.refresh_library or not SYMLIB.exists():
        refresh_library()
    build_schematic()


if __name__ == '__main__':
    main()
