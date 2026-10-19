"""Generate the V1 S4 MIDI schematic (hardware/v1/midi.kicad_sch) and its pinned symbols.

Run from modules/midi:
  python3 -B tools/v1/build_schematic.py

Writes hardware/v1/MIDI.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the MIDI library), hardware/v1/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. CIRCUIT below is the
circuit intent of docs/research.md section 3. Every pin gets a short stub and a
local net label (usb-power style), so connectivity is explicit by name.

The PCB never reads this table: tools/v1/build_layout.py takes nets, values and
footprints from the native netlist that kicad-cli exports from this schematic.
"""
import copy
import hashlib
import json
import math
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # shared tools/sexp.py
from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[2]
HW = MODULE / 'hardware/v1'
STOCK = Path('/usr/share/kicad/symbols')
PROJECT = 'midi'
STUB = 2.54

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the MIDI library, so the copies
# get the same patterns without the library part. JP1 is a jumper on a 2.54 mm header.
FILTER_EDITS = {
    'Conn_01x02': '*_1x??_*',
    'Conn_02x05_Odd_Even': '*_2x??_*',
    'Jumper_3_Open': 'Jumper* TestPoint*3Pads* TestPoint*Bridge* PinHeader_1x03_P2.54mm_Vertical',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'LED': ('Device', 'LED'),
    'D': ('Device', 'D'), 'D_Schottky': ('Device', 'D_Schottky'),
    'ATtiny1616-M': ('MCU_Microchip_ATtiny', 'ATtiny1616-M'),
    'HT75xx-1-SOT89': ('Regulator_Linear', 'HT75xx-1-SOT89'),
    'AudioJack3': ('Connector_Audio', 'AudioJack3'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Jumper_3_Open': ('Jumper', 'Jumper_3_Open'),
    'Conn_01x02': ('Connector_Generic', 'Conn_01x02'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'SOD123': 'D_SOD-123', 'LED3': 'LED_D3.0mm',
    'QFN20': 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm',
    'SOT89': 'SOT-89-3', 'PJ366ST': 'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'H1x2': 'PinHeader_1x02_P2.54mm_Vertical', 'H1x3': 'PinHeader_1x03_P2.54mm_Vertical', 'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
}

# Pin map (docs/research.md 3.3), identical to Bread Modular so the firmware ports.
OUT_PINS = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 13, 7: 14, 8: 12}   # PA5 PA6 PA7 PB5 PB4 PB1 PB0 PB2
LED_PINS = {1: 15, 2: 16, 3: 17, 4: 18, 5: 20, 6: 1, 7: 2, 8: 5}  # PC0-PC3, PA1-PA4
CH_RES = {1: ('R3', 'R4'), 2: ('R5', 'R6'), 3: ('R7', 'R8'), 4: ('R9', 'R10'),
          5: ('R12', 'R13'), 6: ('R14', 'R15'), 7: ('R16', 'R17'), 8: ('R18', 'R19')}


def part(ref, sym, value, fp, at, rot, pins, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, fields=fields)


def circuit():
    c = []
    # ---- Power: Eurorack +12 V -> reverse diode -> dropper -> HT7550 -> +5V
    c.append(part('J10', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (45.72, 58.42), 0,
                  {'1': None, '2': None, '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V', '10': '+12V'},
                  Note='Unshrouded vertical header, pin 1 (-12 V) at the board bottom; '
                       'also takes a 16-pin IDC socket (positions 11-16 overhang, unused)'))
    c.append(part('D10', 'D_Schottky', 'B5819W', 'SOD123', (91.44, 45.72), 0,
                  {'1': 'VIN_D', '2': '+12V'},
                  Note='Series reverse-polarity protection'))
    c.append(part('R20', 'R', '39', 'R1206', (91.44, 55.88), 90,
                  {'1': 'VIN_D', '2': 'VIN_LDO'}, Power='0.5W',
                  Note='Dropper: shares LDO heat in the ~77 mA worst case (research 3.1); '
                       'anti-surge 0.5 W part, sits on the VIN_LDO heat-sink copper'))
    c.append(part('C5', 'C', '1u', 'C0805', (91.44, 66.04), 90,
                  {'1': 'VIN_LDO', '2': 'GND'}, Voltage='50V'))
    c.append(part('U3', 'HT75xx-1-SOT89', 'HT7550-1', 'SOT89', (124.46, 50.8), 0,
                  {'1': 'GND', '2': 'VIN_LDO', '3': '+5V'},
                  Note='30 V max input, 150 mA. Tab = pin 2 (VIN): heat-sink copper is VIN_LDO'))
    c.append(part('C4', 'C', '10u', 'C0805', (124.46, 66.04), 90,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='LDO output'))
    c.append(part('C3', 'C', '10u', 'C0805', (124.46, 78.74), 90,
                  {'1': '+5V', '2': 'GND'}, Voltage='25V', Note='Local bulk'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (45.72, 78.74), 0, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (101.6, 78.74), 0, {'1': 'VIN_LDO'}))

    # ---- MIDI input: Bread Modular V1 direct input, TRS Type A/B on a 2.54 mm jumper.
    # The opto-isolated input is deferred to V2 (docs/research.md 3.2).
    c.append(part('J1', 'AudioJack3', 'PJ366ST', 'PJ366ST', (27.94, 127.0), 0,
                  {'T': 'TIP', 'R': 'RING', 'S': 'GND'}, Note='TRS MIDI in'))
    c.append(part('JP1', 'Jumper_3_Open', 'TRS_A/B', 'H1x3', (63.5, 127.0), 0,
                  {'1': 'TIP', '2': 'RX', '3': 'RING'},
                  Note='1x3 2.54 mm header + shunt. 1-2 = Type A (Tip = data), '
                       '2-3 = Type B (Ring = data). No shunt = no input. '
                       'Common drives PB3 directly, as Bread Modular V1 (no series R, no pull-up)'))

    # ---- MCU and programming
    u1 = {'4': '+5V', '3': 'GND', '21': 'GND', '19': 'UPDI_PA0', '11': 'RX'}
    for ch in range(1, 9):
        u1[str(OUT_PINS[ch])] = f'CH{ch}_TX'
        u1[str(LED_PINS[ch])] = f'CH{ch}_LED'
    c.append(part('U1', 'ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20', (210.82, 104.14), 0, u1,
                  Note='5 V: 20 MHz as Bread Modular'))
    c.append(part('C1', 'C', '100n', 'C0603', (190.5, 142.24), 90,
                  {'1': '+5V', '2': 'GND'}, Voltage='50V', Note='U1 decoupling'))
    c.append(part('R11', 'R', '4.7k', 'R0603', (190.5, 152.4), 90,
                  {'1': 'UPDI_PA0', '2': 'UPDI'}, Note='UPDI series resistor (Bread Modular)'))
    c.append(part('J11', 'Conn_01x02', 'UPDI', 'H1x2', (190.5, 165.1), 0,
                  {'1': 'UPDI', '2': 'GND'},
                  Note='Pin 1 UPDI, pin 2 GND. Program with the module on Eurorack power'))

    # ---- Outputs: GPIO -> 1k -> TS tip; GPIO -> 1k -> LED -> GND
    for ch in range(1, 9):
        col, row = (ch - 1) // 4, (ch - 1) % 4
        x0, y0 = 256.54 + col * 76.2, 45.72 + row * 33.02
        rout, rled = CH_RES[ch]
        c.append(part(rout, 'R', '1k', 'R0603', (x0, y0), 90,
                      {'1': f'CH{ch}_TX', '2': f'OUT{ch}'}, Note=f'Output {ch} series (Bread Modular)'))
        c.append(part(f'J{ch + 1}', 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (x0 + 43.18, y0 + 2.54), 0,
                      {'T': f'OUT{ch}', 'S': 'GND', 'TN': None}, Note=f'MIDI out {ch} (TS)'))
        c.append(part(rled, 'R', '1k', 'R0603', (x0, y0 + 12.7), 90,
                      {'1': f'CH{ch}_LED', '2': f'LED{ch}_A'}, Note=f'LED {ch} current'))
        c.append(part(f'D{ch}', 'LED', 'LED_3mm_red', 'LED3', (x0 + 30.48, y0 + 12.7), 180,
                      {'2': f'LED{ch}_A', '1': 'GND'}, Note='Hand-soldered 3 mm THT'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Live strict lookups 2026-10-18, recorded in docs/sourcing-candidates.json (jlc_release).
# Passives and D10 are JLCPCB Basic; R20, U1 and U3 are Extended by choice/necessity.
# The THT jacks, LEDs and headers are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '4.7k', 'R0603'): dict(LCSC='C23162', MPN='0603WAF4701T5E', Manufacturer='UNI-ROYAL'),
    ('R', '39', 'R1206'): dict(LCSC='C414944', MPN='HP06W2F390JT5E', Manufacturer='UNI-ROYAL'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('HT75xx-1-SOT89', 'HT7550-1', 'SOT89'): dict(LCSC='C16106', MPN='HT7550-1', Manufacturer='Holtek'),
    ('ATtiny1616-M', 'ATtiny1616-MNR', 'QFN20'): dict(LCSC='C507118', MPN='ATTINY1616-MNR',
                                                       Manufacturer='Microchip'),
}


# Reference / value text offsets from the symbol origin (default: just above/below).
TEXT_AT = {
    'U1': ((10.16, -25.4), (10.16, 25.4)),
    'U3': ((0, -7.62), (8.89, 7.62)),
    'J10': ((1.27, -8.89), (1.27, 8.89)),
    'J1': ((0, -6.35), (0, 6.35)),
    'J11': ((0, -3.81), (0, 5.08)),
    'Jumper_3_Open': ((0, -6.35), (0, -3.81)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 6.35)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR MIDI - S4 schematic (5 V logic, BM V1 direct input). Circuit intent: docs/research.md', 2.0),
    ((20.32, 33.02), 'POWER: Eurorack +12V -> B5819W -> 39R -> HT7550-1 -> +5V.  -12V (J10 pins 1-2) unused.', 1.4),
    ((20.32, 86.36), 'PWR_FLAG: #FLG01 marks the Eurorack GND entry; #FLG02 marks VIN_LDO, which is\n'
                     'fed from +12V only through passives (D10, R20) that ERC cannot see through.', 1.1),
    ((20.32, 101.6), 'MIDI IN: Bread Modular V1 direct input (3.3 V and 5 V senders), no opto', 1.4),
    ((20.32, 152.4), 'JP1 TRS TYPE (2.54 mm header on the back): shunt 1-2 = TYPE A (Tip = data),\n'
                     'shunt 2-3 = TYPE B (Ring = data). The unused conductor is left open.\n'
                     'Sleeve = GND (as Bread Modular V1). Firmware: no PORT_INVEN.\n'
                     'Opto-isolated input (ground-loop break, voltage-sensed) is deferred to V2.', 1.1),
    ((175.26, 71.12), 'MCU: ATtiny1616 at 5 V, 20 MHz; pin map identical to Bread Modular', 1.4),
    ((175.26, 177.8), 'UPDI J11: pin 1 UPDI, pin 2 GND (2.54 mm). Power the module from Eurorack while programming.', 1.1),
    ((256.54, 33.02), 'OUTPUTS 1-8: GPIO -> 1k -> TS tip (sleeve GND); GPIO -> 1k -> LED -> GND', 1.4),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'big-modular/midi/schematic/' + key))


def stock_symbol(lib, name):
    tree = parse((STOCK / f'{lib}.kicad_sym').read_text())
    syms = {s[1]: s for s in nodes(tree, 'symbol')}
    sym = copy.deepcopy(syms[name])
    ext = one(sym, 'extends')
    if ext:  # flatten: parent body/pins, child properties
        parent = copy.deepcopy(syms[ext[1]])
        props = {p[1]: p for p in nodes(sym, 'property')}
        for i, item in enumerate(parent):
            if isinstance(item, list) and item[0] == 'property' and item[1] in props:
                parent[i] = props.pop(item[1])
            elif isinstance(item, list) and item[0] == 'symbol':
                item[1] = item[1].replace(ext[1], name, 1)
        parent[1] = name
        insert = max(i for i, item in enumerate(parent) if isinstance(item, list) and item[0] == 'property') + 1
        parent[insert:insert] = list(props.values())
        sym = parent
    return sym, (STOCK / f'{lib}.kicad_sym'), ext[1] if ext else None


def pin_table(sym):
    out = {}
    for p in walk(sym, 'pin'):
        at = one(p, 'at')
        out[one(p, 'number')[1]] = (float(at[1]), float(at[2]), float(at[3]), p[1])
    return out


def xform(px, py, rot):
    """Library XY (Y up) -> schematic offset (Y down) for a CCW symbol rotation."""
    x, y = px, -py
    a = math.radians(rot)
    return (round(x * math.cos(a) + y * math.sin(a), 4), round(-x * math.sin(a) + y * math.cos(a), 4))


def outward(angle, rot):
    """Unit vector from the pin end away from the body, schematic coordinates."""
    dx, dy = xform(math.cos(math.radians(angle)), math.sin(math.radians(angle)), rot)
    return (-round(dx), -round(dy))


def r(v):
    return round(v, 2)


def build():
    lib_syms, sources = {}, {}
    for key, (lib, name) in SYMBOLS.items():
        sym, src, parent = stock_symbol(lib, name)
        edit = None
        if key in FILTER_EDITS:
            prop = next(pp for pp in nodes(sym, 'property') if pp[1] == 'ki_fp_filters')
            edit = f'ki_fp_filters {prop[2]!r} -> {FILTER_EDITS[key]!r}'
            prop[2] = FILTER_EDITS[key]
        lib_syms[key] = sym
        sources[key] = {'library': f'{lib}:{name}', 'source': str(src).replace(str(Path.home()), '~', 1),
                        'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                        'flattened_from': parent, 'edits': edit}
    # Local pinned symbol library (names unprefixed inside the library file).
    stock_header = parse((STOCK / 'Device.kicad_sym').read_text())
    lib = [atom('kicad_symbol_lib'), one(stock_header, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(lib_syms[k]) for k in sorted(lib_syms)]
    (HW / 'MIDI.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        '(sym_lib_table (version 7) (lib (name "MIDI") (type "KiCad") (uri "${KIPRJMOD}/MIDI.kicad_sym") '
        '(options "") (descr "MIDI module pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - MIDI") (rev "S4") (company "Big Modular")
        (comment 1 "SCHEMATIC S3 - 5 V logic - not released, not for fabrication")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = 'MIDI:' + k
        embedded.append(s)

    items, nets = [], {}
    for p in circuit():
        sym = lib_syms[p['sym']]
        pins = pin_table(sym)
        assert set(p['pins']) == set(pins), (p['ref'], sorted(pins), sorted(p['pins']))
        x, y = p['at']
        is_flag = p['ref'].startswith('#')
        dr, dv = TEXT_AT.get(p['ref'], TEXT_AT.get(p['sym'], ((0, -3.81), (0, 3.81))))
        props = [('Reference', p['ref'], (x + dr[0], y + dr[1]), False),
                 ('Value', p['value'], (x + dv[0], y + dv[1]), is_flag),
                 ('Footprint', f"MIDI:{FP[p['fp']]}" if p['fp'] else '', (x, y), True),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''), (x, y), True),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''), (x, y), True)]
        props += [(k, v, (x, y), True) for k, v in p['fields'].items()]
        fang = 90 if p['rot'] in (90, 270) else 0
        node = [atom('symbol'), [atom('lib_id'), 'MIDI:' + p['sym']], [atom('at'), x, y, p['rot']],
                [atom('unit'), 1], [atom('exclude_from_sim'), atom('no')],
                [atom('in_bom'), atom('no' if is_flag else 'yes')],
                [atom('on_board'), atom('no' if is_flag else 'yes')],
                [atom('in_pos_files'), atom('no' if is_flag else 'yes')], [atom('dnp'), atom('no')],
                [atom('uuid'), uid('sym/' + p['ref'])]]
        for name, value, (px, py), hide in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), fang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{p['ref']}/{n}")]] for n in sorted(pins)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), 1]]]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, py, p['rot'])
            ex, ey = r(x + ox), r(y + oy)
            key = f"{p['ref']}/{n}"
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                continue
            nets.setdefault(net, []).append(key)
            dx, dy = outward(ang, p['rot'])
            sx, sy = r(ex + dx * STUB), r(ey + dy * STUB)
            items.append([atom('wire'), [atom('pts'), [atom('xy'), ex, ey], [atom('xy'), sx, sy]],
                          [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                          [atom('uuid'), uid('wire/' + key)]])
            lang, just = {(1, 0): (0, 'left'), (-1, 0): (180, 'right'),
                          (0, -1): (90, 'left'), (0, 1): (270, 'right')}[(dx, dy)]
            items.append([atom('label'), net, [atom('at'), sx, sy, lang],
                          [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                           [atom('justify'), atom(just), atom('bottom')]],
                          [atom('uuid'), uid('label/' + key)]])
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    for i, ((x, y), s, size) in enumerate(TEXTS):
        items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                      [atom('effects'), [atom('font'), [atom('size'), size, size]], [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'text/{i}')]])
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])
    out = HW / 'midi.kicad_sch'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True,
                   stdout=subprocess.DEVNULL)
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': 'Pinned stock KiCad 10 symbols in hardware/MIDI.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    print(out, f'{len(nets)} nets')


if __name__ == '__main__':
    build()
