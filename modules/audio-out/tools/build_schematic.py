"""Generate the S3 audio-out schematic (hardware/audio-out.kicad_sch) and its pinned symbols.

Run from modules/audio-out:
  python3 -B tools/build_schematic.py

Writes hardware/AudioOut.kicad_sym (stock KiCad 10 symbols, derived symbols flattened,
renamed into the AudioOut library), hardware/sym-lib-table and the flat root schematic,
then lets `kicad-cli sch upgrade --force` re-save it natively. CIRCUIT below is the
circuit intent of docs/research.md section 3. Every pin gets a short stub and a
local net label (usb-power / midi style), so connectivity is explicit by name.
The dual opamps are placed as three units each (A, B, power).

The PCB never reads this table: tools/build_layout.py takes nets, values and
footprints from the native netlist that kicad-cli exports from this schematic.
"""
import copy
import hashlib
import json
import math
import re
import subprocess
import uuid
from pathlib import Path

from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
STOCK = Path('/usr/share/kicad/symbols')
PROJECT = 'audio-out'
LIB = 'AudioOut'
STUB = 2.54

# Footprint filters of these stock symbols are qualified with stock library names
# (Connector*:...); the pinned footprints live in the AudioOut library, so the copies
# get the same patterns without the library part.
FILTER_EDITS = {
    'Conn_02x05_Odd_Even': '*_2x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'D_Schottky': ('Device', 'D_Schottky'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'),
    'OPA1678': ('Amplifier_Operational', 'OPA1678'),
    'MC33178': ('Amplifier_Operational', 'MC33178'),
    'AudioJack3': ('Connector_Audio', 'AudioJack3'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
}

FP = {
    'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'SOD123': 'D_SOD-123', 'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm',
    'PJ366ST': 'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical',
    'RV09': 'Potentiometer_RV09',
    'H2x5': 'PinHeader_2x05_P2.54mm_Vertical',
}

# Per-channel references (docs/research.md 3.2-3.4).
CH = {
    'L': dict(jack='J1', rs='R1', cin='C1', rtop='R3', rbot='R5', rline='R7', rlaw='R9', rhp='R11',
              pot='RV1', buf=1, drv=1, sw='T'),
    'R': dict(jack='J2', rs='R2', cin='C2', rtop='R4', rbot='R6', rline='R8', rlaw='R10', rhp='R12',
              pot='RV2', buf=2, drv=2, sw='R'),
}
# Opamp unit pins: unit -> (out, -, +)
UNIT_PINS = {1: ('1', '2', '3'), 2: ('7', '6', '5')}


def part(ref, sym, value, fp, at, rot, pins, unit=1, **fields):
    return dict(ref=ref, sym=sym, value=value, fp=fp, at=at, rot=rot, pins=pins, unit=unit, fields=fields)


def circuit():
    c = []
    # ---- Power: Eurorack +/-12 V -> series Schottky (reverse protection) -> rails
    c.append(part('J5', 'Conn_02x05_Odd_Even', 'Eurorack_2x5', 'H2x5', (35.56, 63.5), 0,
                  {'1': '-12V_IN', '2': '-12V_IN', '3': 'GND', '4': 'GND', '5': 'GND', '6': 'GND',
                   '7': 'GND', '8': 'GND', '9': '+12V_IN', '10': '+12V_IN'},
                  Note='Unshrouded 2x5 pin header, pin 1 (-12 V) at the board bottom; '
                       '10-pin cable, red stripe down (use a 10-to-16 cable on a 16-pin bus)'))
    c.append(part('D1', 'D_Schottky', 'B5819W', 'SOD123', (68.58, 50.8), 180,
                  {'1': '+12V', '2': '+12V_IN'}, Note='Series reverse-polarity protection, +12 V'))
    c.append(part('D2', 'D_Schottky', 'B5819W', 'SOD123', (68.58, 76.2), 180,
                  {'1': '-12V_IN', '2': '-12V'}, Note='Series reverse-polarity protection, -12 V'))
    c.append(part('C3', 'C', '10u', 'C0805', (88.9, 58.42), 90, {'1': '+12V', '2': 'GND'},
                  Voltage='25V', Note='+12 V bulk at the entry'))
    c.append(part('C4', 'C', '10u', 'C0805', (88.9, 71.12), 90, {'1': 'GND', '2': '-12V'},
                  Voltage='25V', Note='-12 V bulk at the entry'))
    c.append(part('#FLG01', 'PWR_FLAG', 'PWR_FLAG', None, (35.56, 86.36), 0, {'1': 'GND'}))
    c.append(part('#FLG02', 'PWR_FLAG', 'PWR_FLAG', None, (101.6, 45.72), 0, {'1': '+12V'}))
    c.append(part('#FLG03', 'PWR_FLAG', 'PWR_FLAG', None, (101.6, 81.28), 0, {'1': '-12V'}))
    # Opamp supply units and local decoupling
    c.append(part('U1', 'OPA1678', 'OPA1678IDR', 'SOIC8', (127.0, 63.5), 0,
                  {'4': '-12V', '8': '+12V'}, unit=3, Note='Input buffers / line drivers'))
    c.append(part('U2', 'MC33178', 'MC33178DR2G', 'SOIC8', (167.64, 63.5), 0,
                  {'4': '-12V', '8': '+12V'}, unit=3, Note='Headphone drivers, 80 mA class'))
    c.append(part('C5', 'C', '100n', 'C0603', (142.24, 58.42), 90, {'1': '+12V', '2': 'GND'},
                  Voltage='50V', Note='U1 V+ decoupling'))
    c.append(part('C6', 'C', '100n', 'C0603', (142.24, 71.12), 90, {'1': 'GND', '2': '-12V'},
                  Voltage='50V', Note='U1 V- decoupling'))
    c.append(part('C7', 'C', '100n', 'C0603', (182.88, 58.42), 90, {'1': '+12V', '2': 'GND'},
                  Voltage='50V', Note='U2 V+ decoupling'))
    c.append(part('C8', 'C', '100n', 'C0603', (182.88, 71.12), 90, {'1': 'GND', '2': '-12V'},
                  Voltage='50V', Note='U2 V- decoupling'))
    c.append(part('C9', 'C', '10u', 'C0805', (205.74, 58.42), 90, {'1': '+12V', '2': 'GND'},
                  Voltage='25V', Note='U2 local bulk (headphone peaks)'))
    c.append(part('C10', 'C', '10u', 'C0805', (205.74, 71.12), 90, {'1': 'GND', '2': '-12V'},
                  Voltage='25V', Note='U2 local bulk (headphone peaks)'))

    # ---- Channels: TS in -> 1k -> 1u -> node T -> 47k/56k divider -> U1 follower.
    #      J2 (R in) switch contact TN is normalled to IN_L: with no R plug, L feeds both sides.
    #      U1 out (BUF) -> 100R -> line out; BUF -> 50k pot (+15k law) -> U2 follower -> 10R -> phones
    for i, (ch, d) in enumerate(CH.items()):
        y = 124.46 + i * 60.96
        c.append(part(d['jack'], 'AudioJack2_SwitchT', 'PJ301M-12', 'PJ301M', (25.4, y), 0,
                      {'T': f'IN_{ch}', 'S': 'GND', 'TN': 'IN_L' if ch == 'R' else None},
                      Note='R input (TS); unpatched, TN normals it to IN_L' if ch == 'R' else 'L input (TS)'))
        c.append(part(d['rs'], 'R', '1k', 'R0603', (50.8, y - 2.54), 90,
                      {'1': f'IN_{ch}', '2': f'INR_{ch}'}, Note='Input series (injection limit)'))
        c.append(part(d['cin'], 'C', '1u', 'C0805', (71.12, y - 2.54), 90,
                      {'1': f'INR_{ch}', '2': f'T_{ch}'}, Voltage='50V', Note='Input DC block (1.5 Hz with 103k)'))
        c.append(part(d['rtop'], 'R', '47k', 'R0603', (91.44, y - 2.54), 90,
                      {'1': f'T_{ch}', '2': f'A_{ch}'}, Note='Line-level divider top'))
        c.append(part(d['rbot'], 'R', '56k', 'R0603', (106.68, y + 10.16), 0,
                      {'1': f'A_{ch}', '2': 'GND'}, Note='Line-level divider bottom: x0.544'))
        out, neg, pos = UNIT_PINS[d['buf']]
        c.append(part('U1', 'OPA1678', 'OPA1678IDR', 'SOIC8', (124.46, y), 0,
                      {pos: f'A_{ch}', neg: f'BUF_{ch}', out: f'BUF_{ch}'}, unit=d['buf'],
                      Note='Input buffers / line drivers'))
        c.append(part(d['rline'], 'R', '100', 'R0603', (152.4, y - 12.7), 90,
                      {'1': f'BUF_{ch}', '2': f'LINE_{ch}'}, Note='Line out build-out'))
        c.append(part(d['pot'], 'R_Potentiometer', '50k', 'RV09', (162.56, y + 12.7), 0,
                      {'3': f'BUF_{ch}', '2': f'VOL_{ch}', '1': 'GND'},
                      Note=f'{ch} headphone volume (Bread Modular RV09; pin 3 = CW end)'))
        c.append(part(d['rlaw'], 'R', '15k', 'R0603', (180.34, y + 22.86), 0,
                      {'1': f'VOL_{ch}', '2': 'GND'}, Note='Taper-shaping load (linear pot -> ~log)'))
        out, neg, pos = UNIT_PINS[d['drv']]
        c.append(part('U2', 'MC33178', 'MC33178DR2G', 'SOIC8', (205.74, y + 10.16), 0,
                      {pos: f'VOL_{ch}', neg: f'HP_{ch}_DRV', out: f'HP_{ch}_DRV'}, unit=d['drv'],
                      Note='Headphone drivers, 80 mA class'))
        c.append(part(d['rhp'], 'R', '10', 'R1206', (233.68, y + 7.62), 90,
                      {'1': f'HP_{ch}_DRV', '2': f'HP_{ch}'}, Power='0.25W',
                      Note='Headphone build-out / short-circuit limit'))
    c.append(part('J3', 'AudioJack3', 'PJ366ST', 'PJ366ST', (264.16, 132.08), 180,
                  {'T': 'LINE_L', 'R': 'LINE_R', 'S': 'GND'}, Note='Stereo line out (TRS, unbalanced)'))
    c.append(part('J4', 'AudioJack3', 'PJ366ST', 'PJ366ST', (264.16, 193.04), 180,
                  {'T': 'HP_L', 'R': 'HP_R', 'S': 'GND'}, Note='Headphone out (TRS)'))
    for p in c:
        p['fields'].update(SOURCING.get((p['sym'], p['value'], p['fp']), {}))
    return c


# JLCPCB parts for every assembled (SMD, back-side) part, keyed (symbol, value, footprint).
# Live strict lookups 2026-10-19, recorded in docs/sourcing-candidates.json.
# Passives and D1/D2 are JLCPCB Basic; U1 and U2 are Extended by choice (audio opamps).
# The THT jacks, pots and headers are hand-soldered and carry no LCSC field.
SOURCING = {
    ('R', '1k', 'R0603'): dict(LCSC='C21190', MPN='0603WAF1001T5E', Manufacturer='UNI-ROYAL'),
    ('R', '47k', 'R0603'): dict(LCSC='C25819', MPN='0603WAF4702T5E', Manufacturer='UNI-ROYAL'),
    ('R', '56k', 'R0603'): dict(LCSC='C23206', MPN='0603WAF5602T5E', Manufacturer='UNI-ROYAL'),
    ('R', '15k', 'R0603'): dict(LCSC='C22809', MPN='0603WAF1502T5E', Manufacturer='UNI-ROYAL'),
    ('R', '100', 'R0603'): dict(LCSC='C22775', MPN='0603WAF1000T5E', Manufacturer='UNI-ROYAL'),
    ('R', '10', 'R1206'): dict(LCSC='C17903', MPN='1206W4F100JT5E', Manufacturer='UNI-ROYAL'),
    ('C', '100n', 'C0603'): dict(LCSC='C14663', MPN='CC0603KRX7R9BB104', Manufacturer='YAGEO'),
    ('C', '1u', 'C0805'): dict(LCSC='C28323', MPN='CL21B105KBFNNNE', Manufacturer='Samsung'),
    ('C', '10u', 'C0805'): dict(LCSC='C15850', MPN='CL21A106KAYNNNE', Manufacturer='Samsung'),
    ('D_Schottky', 'B5819W', 'SOD123'): dict(LCSC='C8598', MPN='B5819W SL', Manufacturer='CJ (Jiangsu Changjing)'),
    ('OPA1678', 'OPA1678IDR', 'SOIC8'): dict(LCSC='C192421', MPN='OPA1678IDR', Manufacturer='Texas Instruments'),
    ('MC33178', 'MC33178DR2G', 'SOIC8'): dict(LCSC='C39113', MPN='MC33178DR2G', Manufacturer='onsemi'),
}


# Reference / value text offsets from the symbol origin (default: just above/below).
TEXT_AT = {
    'J5': ((1.27, -8.89), (1.27, 8.89)),
    'AudioJack2_SwitchT': ((0, -6.35), (0, 6.35)),
    'AudioJack3': ((0, -6.35), (0, 6.35)),
    'OPA1678': ((0, -6.35), (0, 6.35)),
    'MC33178': ((0, -6.35), (0, 6.35)),
    'R_Potentiometer': ((-5.08, -2.54), (-5.08, 2.54)),
    'PWR_FLAG': ((0, -5.08), (0, -2.54)),
}

TEXTS = [
    ((20.32, 20.32), 'BIG MODULAR AUDIO OUT - S3 schematic (+/-12 V, pure analog). Circuit intent: docs/research.md', 2.0),
    ((20.32, 33.02), 'POWER: Eurorack +/-12V -> B5819W series diodes -> +12V / -12V rails. +5 V not used.', 1.4),
    ((20.32, 93.98), 'PWR_FLAG: #FLG01 marks the Eurorack GND entry; #FLG02/#FLG03 mark the rails, which are\n'
                     'fed from the header only through the series diodes D1/D2 that ERC cannot see through.', 1.1),
    ((20.32, 106.68), 'CHANNELS (L top, R bottom): TS in -> 1k -> 1u -> T node -> 47k/56k (x0.544) -> OPA1678 follower = BUF\n'
                      'BUF -> 100R -> LINE out.  BUF -> 50k pot (15k taper load) -> MC33178 follower -> 10R -> PHONES.\n'
                      'Line level: 10 Vpp (+/-5 V Eurorack full scale) -> 1.92 Vrms, under the 2 Vrms consumer full scale.', 1.1),
    ((20.32, 223.52), 'NORMALLING: J2 (IN R) switch contact TN is wired to IN_L. With no plug in IN R,\n'
                      'the L input feeds the R channel too (mono L on both sides). A plug in IN R opens\n'
                      'the switch: stereo. No jumper.', 1.1),
    ((243.84, 106.68), 'OUTPUTS (TRS): line out T = L, R = R, S = GND; phones T = L, R = R, S = GND', 1.4),
]


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/{PROJECT}/schematic/' + key))


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


def pin_table(sym, unit):
    """Pins of one unit (plus the unit-0 pins shared by all units)."""
    out = {}
    for sub in nodes(sym, 'symbol'):
        m = re.fullmatch(re.escape(sym[1]) + r'_(\d+)_(\d+)', sub[1])
        if not m or int(m.group(1)) not in (0, unit):
            continue
        for p in walk(sub, 'pin'):
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


def on_segment(pt, a, b):
    (x, y), (x0, y0), (x1, y1) = pt, a, b
    return (min(x0, x1) - 1e-6 <= x <= max(x0, x1) + 1e-6 and min(y0, y1) - 1e-6 <= y <= max(y0, y1) + 1e-6
            and abs((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) < 1e-6)


def check_isolation(segs):
    """Connectivity is by label only: no pin end or stub end may touch another pin's stub."""
    bad = [(k1, k2) for n1, k1, a1, b1 in segs for n2, k2, a2, b2 in segs
           if k1 != k2 and (on_segment(a1, a2, b2) or on_segment(b1, a2, b2))]
    assert not bad, f'stubs touch: {bad}'


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
    (HW / f'{LIB}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") '
        '(options "") (descr "audio-out module pinned stock symbols; see tools/build_schematic.py")))\n')

    root = uid('root')
    q = json.dumps
    sch = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A3")
      (title_block (title "Big Modular - Audio Out") (rev "S3") (company "Big Modular")
        (comment 1 "SCHEMATIC S3 - +/-12 V analog - not released, not for fabrication")
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))''')
    embedded = one(sch, 'lib_symbols')
    for k in sorted(lib_syms):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIB}:' + k
        embedded.append(s)

    items, nets, segs = [], {}, []
    for p in circuit():
        sym = lib_syms[p['sym']]
        pins = pin_table(sym, p['unit'])
        assert set(p['pins']) == set(pins), (p['ref'], p['unit'], sorted(pins), sorted(p['pins']))
        x, y = p['at']
        key0 = p['ref'] if p['unit'] == 1 else f"{p['ref']}.{p['unit']}"
        is_flag = p['ref'].startswith('#')
        dr, dv = TEXT_AT.get(p['ref'], TEXT_AT.get(p['sym'], ((0, -3.81), (0, 3.81))))
        props = [('Reference', p['ref'], (x + dr[0], y + dr[1]), False),
                 ('Value', p['value'], (x + dv[0], y + dv[1]), is_flag),
                 ('Footprint', f"{LIB}:{FP[p['fp']]}" if p['fp'] else '', (x, y), True),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''), (x, y), True),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''), (x, y), True)]
        props += [(k, v, (x, y), True) for k, v in p['fields'].items()]
        fang = 90 if p['rot'] in (90, 270) else 0
        node = [atom('symbol'), [atom('lib_id'), f'{LIB}:' + p['sym']], [atom('at'), x, y, p['rot']],
                [atom('unit'), p['unit']], [atom('exclude_from_sim'), atom('no')],
                [atom('in_bom'), atom('no' if is_flag else 'yes')],
                [atom('on_board'), atom('no' if is_flag else 'yes')],
                [atom('in_pos_files'), atom('no' if is_flag else 'yes')], [atom('dnp'), atom('no')],
                [atom('uuid'), uid('sym/' + key0)]]
        for name, value, (px, py), hide in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), fang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{p['ref']}/{n}")]] for n in sorted(pins)]
        node.append([atom('instances'), [atom('project'), PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), p['unit']]]]])
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
            segs.append((net, key, (ex, ey), (sx, sy)))
            items.append([atom('wire'), [atom('pts'), [atom('xy'), ex, ey], [atom('xy'), sx, sy]],
                          [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                          [atom('uuid'), uid('wire/' + key)]])
            lang, just = {(1, 0): (0, 'left'), (-1, 0): (180, 'right'),
                          (0, -1): (90, 'left'), (0, 1): (270, 'right')}[(dx, dy)]
            items.append([atom('label'), net, [atom('at'), sx, sy, lang],
                          [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                           [atom('justify'), atom(just), atom('bottom')]],
                          [atom('uuid'), uid('label/' + key)]])
    check_isolation(segs)
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    for i, ((x, y), s, size) in enumerate(TEXTS):
        items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                      [atom('effects'), [atom('font'), [atom('size'), size, size]], [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'text/{i}')]])
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])
    out = HW / f'{PROJECT}.kicad_sch'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True,
                   stdout=subprocess.DEVNULL)
    # The project file names the root sheet by UUID.
    pro = HW / f'{PROJECT}.kicad_pro'
    data = json.loads(pro.read_text())
    data['schematic']['top_level_sheets'][0]['uuid'] = root
    pro.write_text(json.dumps(data, indent=2) + '\n')
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned stock KiCad 10 symbols in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources},
        indent=2) + '\n')
    print(out, f'{len(nets)} nets')


if __name__ == '__main__':
    build()
