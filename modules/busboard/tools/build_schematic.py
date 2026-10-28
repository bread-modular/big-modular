"""Generate the busboard schematic (hardware/busboard.kicad_sch) and its pinned library.

Run from modules/busboard:
  python3 -B tools/build_schematic.py

Writes hardware/Busboard.kicad_sym (stock KiCad 10 Conn_02x08_Odd_Even, renamed into the
Busboard library), hardware/sym-lib-table and the flat root schematic, then lets
`kicad-cli sch upgrade --force` re-save it natively. Eight identical 16-pin Eurorack bus
headers J1-J8, every pin in parallel (Doepfer A-100 pinout). Pins of one rail on one side of
a header are wired together; each wired group carries one global label, so the rails
keep their plain names (GND, +12V, ...) for the PCB net classes.
"""
import copy
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
STOCK = Path('/usr/share/kicad/symbols')
PROJECT = 'busboard'
LIB = 'Busboard'
SYM = 'Conn_02x08_Odd_Even'
FOOTPRINT = f'{LIB}:IDC-Header_2x08_P2.54mm_Vertical'
STUB = 2.54
SLOTS = 8

# Doepfer A-100 16-pin bus, pin 1 at the red cable stripe. The rail pairs sit side by side
# (odd pin left, even pin right); groups list the pins of one net on one side.
RAILS = [('-12V', (1,), (2,)), ('GND', (3, 5, 7), (4, 6, 8)), ('+12V', (9,), (10,)),
         ('+5V', (11,), (12,)), ('CV', (13,), (14,)), ('GATE', (15,), (16,))]

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR BUSBOARD - 8 x 16-pin Eurorack bus (passive, all headers in parallel)', 2.0),
    ((20.32, 27.94), 'Doepfer A-100 pinout: 1-2 -12V (red stripe), 3-8 GND, 9-10 +12V, 11-12 +5V, 13-14 CV, 15-16 GATE.\n'
                     'Feed it from any header (usb-power J7 harness or a rack PSU, never both). 10-pin module\n'
                     'cables plug in at the pin 1 end (pins 1-10). CV and GATE are bussed between the headers\n'
                     'only and are not driven on this board.', 1.27),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/{PROJECT}/schematic/' + key))


def r(v):
    return round(v, 2)


def wire(a, b, key):
    return [atom('wire'), [atom('pts'), [atom('xy'), *a], [atom('xy'), *b]],
            [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]], [atom('uuid'), uid('wire/' + key)]]


def build():
    src = STOCK / 'Connector_Generic.kicad_sym'
    stock = parse(src.read_text())
    sym = copy.deepcopy(next(s for s in nodes(stock, 'symbol') if s[1] == SYM))
    assert one(sym, 'extends') is None
    filt = next(p for p in nodes(sym, 'property') if p[1] == 'ki_fp_filters')
    filt[2] = 'IDC*Header*2x08*'
    pins = {one(p, 'number')[1]: (float(one(p, 'at')[1]), float(one(p, 'at')[2])) for p in walk(sym, 'pin')}

    lib = [atom('kicad_symbol_lib'), one(stock, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0'], copy.deepcopy(sym)]
    (HW / f'{LIB}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") '
        '(options "") (descr "busboard pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - Busboard") (rev "S1") (company "Big Modular")
        (comment 1 "SCHEMATIC S1 - passive 8 x 16-pin Eurorack bus - not released")
        (comment 2 "Fits the case bottom plate; see modules/busboard/README.md"))
      (lib_symbols))''')
    emb = copy.deepcopy(sym)
    emb[1] = f'{LIB}:{SYM}'
    one(sch, 'lib_symbols').append(emb)

    items = []
    for i in range(SLOTS):
        ref = f'J{i + 1}'
        x, y = 50.8 + (i % 4) * 76.2, 76.2 + (i // 4) * 63.5
        props = [('Reference', ref, (x + 1.27, y - 12.7), False),
                 ('Value', 'IDC_2x08_Box', (x + 1.27, y + 15.24), False),
                 ('Footprint', FOOTPRINT, (x, y), True), ('Datasheet', '', (x, y), True),
                 ('Description', 'Eurorack 16-pin bus header, shrouded (keyed) IDC box header, '
                                 'through hole, hand-soldered', (x, y), True),
                 ('Note', f'Bus slot {i + 1}; key notch and pin 1 (-12 V, red stripe) as the board silk', (x, y), True)]
        node = [atom('symbol'), [atom('lib_id'), f'{LIB}:{SYM}'], [atom('at'), x, y, 0], [atom('unit'), 1],
                [atom('exclude_from_sim'), atom('no')], [atom('in_bom'), atom('yes')], [atom('on_board'), atom('yes')],
                [atom('in_pos_files'), atom('yes')], [atom('dnp'), atom('no')], [atom('uuid'), uid('sym/' + ref)]]
        for name, value, (px, py), hide in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), 0],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        node += [[atom('pin'), n, [atom('uuid'), uid(f'pin/{ref}/{n}')]] for n in sorted(pins, key=int)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), ref], [atom('unit'), 1]]]])
        items.append(node)
        for net, left, right in RAILS:
            for side, group in (('L', left), ('R', right)):
                ends = []
                for n in group:
                    px, py = pins[str(n)]
                    ex, ey = r(x + px), r(y - py)
                    sx = r(ex - STUB if side == 'L' else ex + STUB)
                    items.append(wire((ex, ey), (sx, ey), f'{ref}/{n}'))
                    ends.append((sx, ey))
                for k, (a, b) in enumerate(zip(ends, ends[1:])):
                    items.append(wire(a, b, f'{ref}/{net}/{side}/{k}'))
                for k, p in enumerate(ends[1:-1]):
                    items.append([atom('junction'), [atom('at'), *p], [atom('diameter'), 0],
                                  [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'junction/{ref}/{side}/{k}')]])
                lx, ly = ends[0]
                ang, just = (180, 'right') if side == 'L' else (0, 'left')
                items.append([atom('global_label'), net, [atom('shape'), atom('passive')], [atom('at'), lx, ly, ang],
                              [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                               [atom('justify'), atom(just)]],
                              [atom('uuid'), uid(f'label/{ref}/{net}/{side}')]])
    for i, ((x, y), s, size) in enumerate(TEXTS):
        items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                      [atom('effects'), [atom('font'), [atom('size'), size, size]], [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'text/{i}')]])
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])
    out = HW / f'{PROJECT}.kicad_sch'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True, stdout=subprocess.DEVNULL)

    pro = HW / f'{PROJECT}.kicad_pro'
    data = json.loads(pro.read_text())
    data['schematic']['top_level_sheets'] = [{'filename': f'{PROJECT}.kicad_sch', 'name': PROJECT, 'uuid': root}]
    data['sheets'] = [[root, 'Root']]
    pro.write_text(json.dumps(data, indent=2) + '\n')
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbol in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': {SYM: {'library': f'Connector_Generic:{SYM}', 'source': str(src),
                           'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                           'edits': "ki_fp_filters -> 'IDC*Header*2x08*'"}}}, indent=2) + '\n')
    print(out)


if __name__ == '__main__':
    build()
