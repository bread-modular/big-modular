"""Generate the USB-AUDIO schematics and their pinned symbols.

Run from modules/usb-audio:
  python3 -B tools/build_schematic.py

Two KiCad projects share hardware/ (one symbol library, one footprint library):
- hardware/usb-audio.kicad_sch      carrier (jack/pot board): power, CS4270 codec, analog in/out,
                                    the MCU-board headers, BOOT/RESET, SWD (tools/circuit_carrier.py)
- hardware/usb-audio-mcu.kicad_sch  MCU board: CH32V307RCT6, USB-C, crystal (tools/circuit_mcu.py)

Writes hardware/USBAUDIO.kicad_sym (stock KiCad 10 symbols, derived symbols flattened),
hardware/sym-lib-table and both flat root schematics, then lets `kicad-cli sch upgrade --force`
re-save them natively.

The drawing engine is modules/32bit's (modules/16bit's): each block is wired (drawing(): polylines
whose points are (x, y), 'REF.PIN' or ('REF.PIN', dx, dy)), with power symbols and net labels
naming every net. Pins not reached by a drawn wire get a short stub closed by a power symbol
(rails; neighbouring stubs of one rail are joined into a bar with one symbol) or a net label:
those are the block-to-block connections. Wires are split at every connection point and junction
dots are added; the build asserts nothing dangles and that the exported native netlist equals the
circuit table. Nets named with a leading '_' are short local links drawn without a label
(compared by pins only).

The PCBs never read these tables: tools/build_layout.py takes nets, values and footprints from
the native netlists.
"""
import copy
import hashlib
import importlib
import json
import math
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/sexp.py, tools/circuit_*.py
from sexp import parse, dump, nodes, one, walk, atom

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
STOCK = Path('/usr/share/kicad/symbols')
LIB = 'USBAUDIO'
STUB = 2.54
MERGE_GAP = 15.24   # neighbouring rail stubs closer than this share one bar and one symbol

# Projects built by this script: circuit module -> (project name, title, revision, comment)
PROJECTS = {
    'circuit_carrier': ('usb-audio', 'Big Modular - USB-AUDIO carrier (jack/pot board)', 'S3',
                        'SCHEMATIC S3 - 2 in / 2 out DC-coupled USB audio, CS4270 codec (192 kHz), +/-5 V, 6HP; '
                        'MCU board on 2.54 mm headers J6/J7'),
    'circuit_mcu': ('usb-audio-mcu', 'Big Modular - USB-AUDIO MCU board', 'S1',
                    'SCHEMATIC S1 - CH32V307RCT6 USB 2.0 High-Speed (UAC2), vertical USB-C through the panel; '
                    'soldered to the carrier on 2.54 mm headers J102/J103'),
}

C = None  # the circuit module being built (RAIL_SYMBOL, MIRROR_X, TEXT_*, MULTI_UNIT, circuit, drawing)

FILTER_EDITS = {
    'FerriteBead': 'Inductor_* L_* *Ferrite* C_0805*',
    # pinned library name is USBAUDIO, not Connector*: keep the pin-count part of the stock filter
    'Conn_02x05_Odd_Even': '*_2x??_*', 'Conn_01x10': '*_1x??_*', 'Conn_01x04': '*_1x??_*',
}

# lib symbol -> (stock library, stock name)
SYMBOLS = {
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'FerriteBead': ('Device', 'FerriteBead'),
    'R_Potentiometer': ('Device', 'R_Potentiometer'), 'D_Schottky': ('Device', 'D_Schottky'),
    'Crystal': ('Device', 'Crystal'),
    'CS4270': ('Audio', 'CS4270'),
    'CH32V30xRxTx': ('MCU_WCH_RiscV', 'CH32V30xRxTx'),
    'OPA1679': ('Amplifier_Operational', 'OPA1679'), 'OPA1678': ('Amplifier_Operational', 'OPA1678'),
    'AMS1117-3.3': ('Regulator_Linear', 'AMS1117-3.3'), 'AMS1117-5.0': ('Regulator_Linear', 'AMS1117-5.0'),
    'ASE-xxxMHz': ('Oscillator', 'ASE-xxxMHz'),
    'USBLC6-2SC6': ('Power_Protection', 'USBLC6-2SC6'),
    'AudioJack2_SwitchT': ('Connector_Audio', 'AudioJack2_SwitchT'),
    'USB_C_Receptacle_USB2.0_16P': ('Connector', 'USB_C_Receptacle_USB2.0_16P'),
    'Conn_02x05_Odd_Even': ('Connector_Generic', 'Conn_02x05_Odd_Even'),
    'Conn_01x10': ('Connector_Generic', 'Conn_01x10'), 'Conn_01x04': ('Connector_Generic', 'Conn_01x04'),
    'SW_Push': ('Switch', 'SW_Push'),
    'PWR_FLAG': ('power', 'PWR_FLAG'),
    'GND': ('power', 'GND'), '+3V3': ('power', '+3V3'), '+5VA': ('power', '+5VA'),
    '+12V': ('power', '+12V'), '-12V': ('power', '-12V'), 'VBUS': ('power', 'VBUS'),
}

FP = {
    'R0402': 'R_0402_1005Metric', 'R0603': 'R_0603_1608Metric', 'R1206': 'R_1206_3216Metric',
    'R2512': 'R_2512_6332Metric',
    'C0402': 'C_0402_1005Metric', 'C0603': 'C_0603_1608Metric', 'C0805': 'C_0805_2012Metric',
    'C1206': 'C_1206_3216Metric',
    'SOD123': 'D_SOD-123', 'SOT223': 'SOT-223-3_TabPin2', 'SOT23-6': 'SOT-23-6',
    'SOIC8': 'SOIC-8_3.9x4.9mm_P1.27mm', 'SOIC14': 'SOIC-14_3.9x8.7mm_P1.27mm',
    'TSSOP24': 'TSSOP-24_4.4x7.8mm_P0.65mm', 'LQFP64': 'LQFP-64_10x10mm_P0.5mm',
    'OSC3225': 'Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm', 'XTAL5032': 'Crystal_SMD_5032-2Pin_5.0x3.2mm',
    'PJ301M': 'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical', 'RV09': 'Potentiometer_RV09',
    'SWK2': 'K2-1808SN-A4SW-01', 'USBC_V': 'USB_C_Receptacle_HRO_TYPE-C-31-D-15_Vertical',
    'H2x5': 'PinHeader_2x05_P2.54mm_Vertical', 'H1x10': 'PinHeader_1x10_P2.54mm_Vertical',
    'H1x4': 'PinHeader_1x04_P2.54mm_Vertical',
}


def uid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'big-modular/usb-audio/{C.PROJECT}/schematic/' + key))


def stock_symbol(lib, name):
    """Stock symbol flattened through every `extends` level (parent body/pins, child properties)."""
    tree = parse((STOCK / f'{lib}.kicad_sym').read_text())
    syms = {s[1]: s for s in nodes(tree, 'symbol')}
    sym = copy.deepcopy(syms[name])
    chain = []
    while one(sym, 'extends'):
        base = one(sym, 'extends')[1]
        chain.append(base)
        parent = copy.deepcopy(syms[base])
        props = {p[1]: p for p in nodes(sym, 'property')}
        for i, item in enumerate(parent):
            if isinstance(item, list) and item[0] == 'property' and item[1] in props:
                parent[i] = props.pop(item[1])
            elif isinstance(item, list) and item[0] == 'symbol':
                item[1] = item[1].replace(base, name, 1)
        parent[1] = name
        insert = max(i for i, item in enumerate(parent) if isinstance(item, list) and item[0] == 'property') + 1
        parent[insert:insert] = list(props.values())
        sym = parent
    return sym, STOCK / f'{lib}.kicad_sym', ' <- '.join(chain) or None


def pin_table(sym, unit):
    """Pins of one unit (body style 1) plus the pins common to all units."""
    out = {}
    for u in nodes(sym, 'symbol'):
        num, style = u[1].rsplit('_', 2)[-2:]
        if num not in ('0', str(unit)) or style not in ('0', '1'):
            continue
        for p in walk(u, 'pin'):
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


def net_name(net):
    """Exported name: power-symbol nets keep their value, labelled nets are sheet-local."""
    return net if net in C.RAIL_SYMBOL else '/' + net


def power_symbol(i, net, x, y, rot, root):
    sym = C.RAIL_SYMBOL[net]
    body = (0, -1) if sym == 'GND' else (0, 1)          # library direction pin -> body
    dx, dy = xform(*body, rot)
    just = [atom('justify'), atom('left' if (dx > 0) != (rot == 90) else 'right')] if dx else None
    vx, vy = r(x + dx * 3.81), r(y + dy * 3.81)
    if sym == 'GND':
        vx, vy = r(x + dx * 5.08), r(y + dy * 5.08)
    ref = f'#PWR{i + 1:03d}'
    fa = rot % 180                                      # horizontal text at any rotation
    hide = [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]], [atom('hide'), atom('yes')]]
    props = [[atom('property'), 'Reference', ref, [atom('at'), x, y, 0], copy.deepcopy(hide)],
             [atom('property'), 'Value', net, [atom('at'), vx, vy, fa],
              [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]] + ([just] if just else [])]]
    for name in ('Footprint', 'Datasheet', 'Description'):
        props.append([atom('property'), name, '', [atom('at'), x, y, 0], copy.deepcopy(hide)])
    return [atom('symbol'), [atom('lib_id'), f'{LIB}:{sym}'], [atom('at'), x, y, rot], [atom('unit'), 1],
            [atom('exclude_from_sim'), atom('no')], [atom('in_bom'), atom('no')], [atom('on_board'), atom('no')],
            [atom('in_pos_files'), atom('no')], [atom('dnp'), atom('no')], [atom('uuid'), uid(f'pwr/{i}')],
            *props, [atom('pin'), '1', [atom('uuid'), uid(f'pwr/{i}/pin')]],
            [atom('instances'), [atom('project'), C.PROJECT,
             [atom('path'), '/' + root, [atom('reference'), ref], [atom('unit'), 1]]]]]




def is_local(net):
    return net.startswith('_')


def draw(ends, root):
    """Wires, power symbols, labels and junctions: drawing() plus automatic stubs.

    ends: {pin end (x, y): (net, outward (dx, dy), [pin keys])} of every connected pin (stacked
    pins share one end). Pins on a drawn wire are left alone; every other pin gets a stub."""
    wires_in, power_in, labels_in = C.drawing()

    def at(pt):
        if isinstance(pt, str):
            hit = [e for e, v in ends.items() if pt.replace('.', '/', 1) in v[2]]
            assert hit, f'unknown or unconnected pin {pt}'
            return hit[0]
        if isinstance(pt[0], str):
            x, y = at(pt[0])
            return (r(x + pt[1]), r(y + pt[2]))
        return (r(pt[0]), r(pt[1]))

    segs = []
    for line in wires_in:
        pts = [at(pt) for pt in line]
        for a_, b_ in zip(pts, pts[1:]):
            assert a_ != b_ and (a_[0] == b_[0] or a_[1] == b_[1]), f'wire {line}: {a_} -> {b_} not axis-aligned'
            segs.append((a_, b_))

    def on_seg(pt, a_, b_, inclusive=True):
        if a_[0] == b_[0] == pt[0]:
            lo, hi = sorted((a_[1], b_[1]))
            return lo <= pt[1] <= hi if inclusive else lo < pt[1] < hi
        if a_[1] == b_[1] == pt[1]:
            lo, hi = sorted((a_[0], b_[0]))
            return lo <= pt[0] <= hi if inclusive else lo < pt[0] < hi
        return False

    def crosses(s1, s2):
        (a1, b1), (a2, b2) = s1, s2
        if (a1[0] == b1[0]) == (a2[0] == b2[0]):
            return False
        if a1[0] != b1[0]:
            (a1, b1), (a2, b2) = (a2, b2), (a1, b1)
        x, y = a1[0], a2[1]                     # s1 vertical at x, s2 horizontal at y
        return (min(a1[1], b1[1]) < y < max(a1[1], b1[1])) and (min(a2[0], b2[0]) < x < max(a2[0], b2[0]))

    power = [(net, at(pt), rot) for net, pt, rot in power_in]
    labels = [(net, at(pt), side) for net, pt, side in labels_in]
    drawn = {e for e in ends if any(on_seg(e, *s) for s in segs)}
    drawn |= {pt for _, pt, _ in power} | {pt for _, pt, _ in labels}

    # Automatic stubs for every pin not reached by a drawn wire.
    stubs = {}
    for e, (net, d, keys) in sorted(ends.items()):
        if e in drawn:
            continue
        s = (r(e[0] + d[0] * STUB), r(e[1] + d[1] * STUB))
        stubs[e] = (s, net, d, keys)
        segs.append((e, s))
    # Join neighbouring stubs of one rail that point the same way into a bar with one symbol.
    anchors = set(ends) | {s for s, *_ in stubs.values()} | {p for s_ in segs for p in s_}
    groups = {}
    for e, (s, net, d, keys) in stubs.items():
        if net in C.RAIL_SYMBOL:
            line = s[1] if d[0] == 0 else s[0]
            groups.setdefault((net, d, line), []).append(s)
    symbol_at = {}
    for (net, d, line), pts in groups.items():
        along = 0 if d[0] == 0 else 1          # vertical stubs -> horizontal bar (along X)
        pts.sort(key=lambda p: p[along])
        bars = [[pts[0]]]
        for p in pts[1:]:
            prev = bars[-1][-1]
            seg = (prev, p)
            blocked = (any(on_seg(a, *seg, inclusive=False) for a in anchors)
                       or any(crosses(seg, s_) for s_ in segs))
            if p[along] - prev[along] <= MERGE_GAP and not blocked:
                bars[-1].append(p)
            else:
                bars.append([p])
        for bar in bars:
            for a_, b_ in zip(bar, bar[1:]):
                segs.append((a_, b_))
            gnd = C.RAIL_SYMBOL[net] == 'GND'
            if along == 0 or len(bar) == 1:      # horizontal bar or single stub: symbol continues the stub
                symbol_at[bar[0]] = (net, d)
            else:                                # vertical bar: + rails at the top, GND at the bottom
                symbol_at[bar[-1] if gnd else bar[0]] = (net, (0, 1) if gnd else (0, -1))
    for e, (s, net, d, keys) in stubs.items():
        if net in C.RAIL_SYMBOL:
            if s in symbol_at:
                n_, dd = symbol_at[s]
                if C.RAIL_SYMBOL[net] == 'GND':
                    rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[dd]
                else:
                    rot = {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[dd]
                power.append((net, s, rot))
        else:
            side = {(1, 0): 'R', (-1, 0): 'L', (0, -1): 'U', (0, 1): 'D'}[d]
            labels.append((net, s, side))

    # Split every segment at every connection point it passes; check nothing dangles.
    pin_pts = set(ends)
    power_pts = {pt for _, pt, _ in power}
    label_pts = {pt for _, pt, _ in labels}
    anchors = pin_pts | power_pts | label_pts | {p for s_ in segs for p in s_}
    split = []
    for a_, b_ in segs:
        cuts = sorted((pt for pt in anchors if on_seg(pt, a_, b_, inclusive=False)),
                      key=lambda pt: abs(pt[0] - a_[0]) + abs(pt[1] - a_[1]))
        chain = [a_] + cuts + [b_]
        split += list(zip(chain, chain[1:]))
    split = sorted(set(tuple(sorted(s_)) for s_ in split))
    degree = {}
    for a_, b_ in split:
        for e in (a_, b_):
            degree[e] = degree.get(e, 0) + 1
    for e, n in degree.items():
        assert n > 1 or e in pin_pts | power_pts | label_pts, f'dangling wire end at {e}'
    for pt in label_pts | power_pts:
        assert pt in degree or pt in pin_pts, f'symbol/label at {pt} touches nothing'
    out = []
    for a_, b_ in split:
        out.append([atom('wire'), [atom('pts'), [atom('xy'), *a_], [atom('xy'), *b_]],
                    [atom('stroke'), [atom('width'), 0], [atom('type'), atom('default')]],
                    [atom('uuid'), uid(f'wire/{a_}/{b_}')]])
    for pt in sorted(degree):
        n = degree[pt] + (pt in pin_pts) + (pt in power_pts)
        if n >= 3:
            out.append([atom('junction'), [atom('at'), *pt], [atom('diameter'), 0],
                        [atom('color'), 0, 0, 0, 0], [atom('uuid'), uid(f'junction/{pt}')]])
    for i, (net, (x, y), rot) in enumerate(power):
        out.append(power_symbol(i, net, x, y, rot, root))
    for i, (net, (x, y), side) in enumerate(labels):
        lang, just = {'R': (0, 'left'), 'L': (180, 'right'), 'U': (90, 'left'), 'D': (270, 'right')}[side]
        out.append([atom('label'), net, [atom('at'), x, y, lang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]],
                     [atom('justify'), atom(just), atom('bottom')]],
                    [atom('uuid'), uid(f'label/{i}')]])
    return out


def check_netlist(sch, nets, no_connects):
    """The native netlist must equal CIRCUIT exactly: same net names (local '_' nets: same
    pins under KiCad's automatic name), same pins, same no-connects."""
    import xml.etree.ElementTree as ET
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / 'n.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml), str(sch)],
                       check=True, stdout=subprocess.DEVNULL)
        root = ET.parse(xml).getroot()
    got = {n.get('name'): frozenset(f"{d.get('ref')}/{d.get('pin')}" for d in n.findall('node')
                                    if not d.get('ref').startswith('#'))
           for n in root.find('nets')}
    got = {k: v for k, v in got.items() if v}
    nc = {next(iter(v)) for k, v in got.items() if k.startswith('unconnected-') and len(v) == 1}
    assert nc == no_connects, f'no-connect pins differ: {sorted(nc ^ no_connects)}'
    got = {k: v for k, v in got.items() if not k.startswith('unconnected-')}
    want = {n: frozenset(k for k in keys if not k.startswith('#')) for n, keys in nets.items()}
    local = {v for n, v in want.items() if is_local(n)}
    auto = {v for k, v in got.items() if k.startswith('Net-(')}
    assert local == auto, f'local nets differ: {sorted(map(sorted, local ^ auto))}'
    got = {k: v for k, v in got.items() if not k.startswith('Net-(')}
    want = {net_name(n): v for n, v in want.items() if not is_local(n)}
    bad = {k: (sorted(got.get(k, ())), sorted(want.get(k, ()))) for k in set(got) | set(want)
           if got.get(k) != want.get(k)}
    assert not bad, 'netlist differs from CIRCUIT (net: got, want):\n' + '\n'.join(
        f'  {k}: {v}' for k, v in sorted(bad.items()))


def lib_text(sym, name):
    p = next(pp for pp in nodes(sym, 'property') if pp[1] == name)
    at = one(p, 'at')
    return float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0


def text_at(p, sym):
    """[(field, (x, y), angle, justify)] for Reference and Value. KiCad stores field angles so that
    angle == symbol rotation (mod 180) reads horizontally."""
    x, y = p['at']
    flat = p['rot'] % 180
    key = next((k for k in (f"{p['ref']}/{p['unit']}", p['ref']) if k in C.TEXT_POS), None)
    if key:
        (rx, ry), (vx, vy), *just = C.TEXT_POS[key]
        just = just[0] if just else None
        return [('Reference', (x + rx, y + ry), flat, just), ('Value', (x + vx, y + vy), flat, just)]
    two_pin = p['sym'] in ('R', 'C', 'L', 'FerriteBead', 'D_Schottky', '1N4148W')
    vertical = (p['rot'] in (0, 180)) == (p['sym'] in ('R', 'C', 'L', 'FerriteBead'))
    if two_pin and not vertical:                       # horizontal: above / below, centred
        return [('Reference', (x, y - 2.54), flat, None), ('Value', (x, y + 2.54), flat, None)]
    if two_pin:
        dx, just = (-2.54, 'right') if p['ref'] in C.TEXT_LEFT else (2.54, 'left')
        if p['rot'] == 180:                            # KiCad mirrors the justification at 180 degrees
            just = {'left': 'right', 'right': 'left'}[just]
        return [('Reference', (x + dx, y - 1.27), flat, just), ('Value', (x + dx, y + 1.27), flat, just)]
    if p['sym'] == 'R_Potentiometer':
        return [('Reference', (x - 2.54, y - 1.27), 0, 'right'), ('Value', (x - 2.54, y + 1.27), 0, 'right')]
    out = []
    for name in ('Reference', 'Value'):
        lx, ly, la = lib_text(sym, name)
        ox, oy = xform(lx, ly, p['rot'])
        out.append((name, (x + ox, y + oy), int((la + p['rot']) % 180), None))
    return out


def symbol_library():
    lib_syms, sources = {}, {}
    for key, (lib, name) in SYMBOLS.items():
        sym, src, parent = stock_symbol(lib, name)
        edit = None
        if key in FILTER_EDITS:
            prop = next(pp for pp in nodes(sym, 'property') if pp[1] == 'ki_fp_filters')
            edit = f'ki_fp_filters {prop[2]!r} -> {FILTER_EDITS[key]!r}'
            prop[2] = FILTER_EDITS[key]
        sym[1] = key
        for u in nodes(sym, 'symbol'):
            u[1] = key + '_' + '_'.join(u[1].rsplit('_', 2)[-2:])
        lib_syms[key] = sym
        sources[key] = {'library': f'{lib}:{name}', 'source': str(src).replace(str(Path.home()), '~', 1),
                        'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                        'flattened_from': parent, 'edits': edit}
    stock_header = parse((STOCK / 'Device.kicad_sym').read_text())
    lib = [atom('kicad_symbol_lib'), one(stock_header, 'version'),
           [atom('generator'), 'kicad_symbol_editor'], [atom('generator_version'), '10.0']]
    lib += [copy.deepcopy(lib_syms[k]) for k in sorted(lib_syms)]
    (HW / f'{LIB}.kicad_sym').write_text(dump(lib) + '\n')
    (HW / 'sym-lib-table').write_text(
        f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") '
        '(options "") (descr "USB-AUDIO pinned symbols (both projects); see tools/build_schematic.py")))\n')
    (MODULE / 'docs/schematic-symbols.json').write_text(json.dumps(
        {'note': f'Pinned symbols in hardware/{LIB}.kicad_sym (generated by tools/build_schematic.py)',
         'symbols': sources}, indent=2) + '\n')
    return lib_syms


def build(module, lib_syms):
    global C
    C = importlib.import_module(module)
    project, title, rev, comment = PROJECTS[module]
    C.PROJECT = project
    root = uid('root')
    q = json.dumps
    sch = parse(f"""(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
      (uuid {q(root)}) (paper "A2")
      (title_block (title {q(title)}) (rev {q(rev)}) (company "Big Modular")
        (comment 1 {q(comment)})
        (comment 2 "Circuit intent: docs/research.md; placement: docs/geometry.json"))
      (lib_symbols))""")
    parts = C.circuit()
    used = {p['sym'] for p in parts} | {C.RAIL_SYMBOL[n] for n in C.RAIL_SYMBOL}
    embedded = one(sch, 'lib_symbols')
    for k in sorted(used):
        s = copy.deepcopy(lib_syms[k])
        s[1] = f'{LIB}:' + k
        embedded.append(s)

    items, nets, ends = [], {}, {}
    units = {}
    for p in parts:
        sym = lib_syms[p['sym']]
        pins = pin_table(sym, p['unit'])
        assert set(p['pins']) == set(pins), (p['ref'], p['unit'], sorted(set(pins) ^ set(p['pins'])))
        units.setdefault(p['ref'], set()).add(p['unit'])
        x, y = p['at']
        is_flag = p['ref'].startswith('#')
        assembled = not is_flag and p['ref'] not in C.NOT_ASSEMBLED
        (rn, rxy, ra, rj), (vn, vxy, va, vj) = text_at(p, sym)
        props = [('Reference', p['ref'], rxy, is_flag, ra, rj), ('Value', p['value'], vxy, is_flag, va, vj),
                 ('Footprint', f"{LIB}:{FP[p['fp']]}" if p['fp'] else '', (x, y), True, 0, None),
                 ('Datasheet', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Datasheet'), ''),
                  (x, y), True, 0, None),
                 ('Description', next((pp[2] for pp in nodes(sym, 'property') if pp[1] == 'Description'), ''),
                  (x, y), True, 0, None)]
        props += [(k, v, (x, y), True, 0, None) for k, v in p['fields'].items()]
        ukey = p['ref'] if p['unit'] == 1 else f"{p['ref']}/{p['unit']}"
        mirror = p['ref'] in C.MIRROR_X
        node = [atom('symbol'), [atom('lib_id'), f'{LIB}:' + p['sym']], [atom('at'), x, y, p['rot']],
                *([[atom('mirror'), atom('x')]] if mirror else []),
                [atom('unit'), p['unit']], [atom('exclude_from_sim'), atom('no')],
                [atom('in_bom'), atom('yes' if assembled else 'no')],
                [atom('on_board'), atom('no' if is_flag else 'yes')],
                [atom('in_pos_files'), atom('yes' if assembled else 'no')], [atom('dnp'), atom('no')],
                [atom('uuid'), uid('sym/' + ukey)]]
        for name, value, (px, py), hide, ang, just in props:
            prop = [atom('property'), name, value, [atom('at'), r(px), r(py), ang],
                    [atom('effects'), [atom('font'), [atom('size'), 1.27, 1.27]]]]
            if just:
                prop[-1].append([atom('justify'), atom(just)])
            if hide:
                prop[-1].append([atom('hide'), atom('yes')])
            node.append(prop)
        all_pins = set().union(*(pin_table(sym, u) for u in range(1, 10)))
        node += [[atom('pin'), n, [atom('uuid'), uid(f"pin/{ukey}/{n}")]] for n in sorted(all_pins)]
        node.append([atom('instances'), [atom('project'), C.PROJECT,
                     [atom('path'), '/' + root, [atom('reference'), p['ref']], [atom('unit'), p['unit']]]]])
        items.append(node)
        for n, net in sorted(p['pins'].items()):
            px, py, ang, _ = pins[n]
            ox, oy = xform(px, -py if mirror else py, p['rot'])
            ex, ey = r(x + ox), r(y + oy)
            key = f"{p['ref']}/{n}"
            if net is None:
                items.append([atom('no_connect'), [atom('at'), ex, ey], [atom('uuid'), uid('nc/' + key)]])
                assert (ex, ey) not in ends, key
                continue
            nets.setdefault(net, []).append(key)
            d = outward(-ang if mirror else ang, p['rot'])
            if (ex, ey) in ends:  # stacked pins or two parts meeting pin to pin (same net only)
                assert ends[(ex, ey)][0] == net, (key, ends[(ex, ey)])
                ends[(ex, ey)][2].append(key)
            else:
                ends[(ex, ey)] = (net, d, [key])
    multi = {ref: u for ref, u in units.items() if len(u) > 1}
    assert multi == C.MULTI_UNIT, multi
    single = {n: k for n, k in nets.items() if len(k) < 2}
    assert not single, f'single-pin nets: {single}'
    items += draw(ends, root)
    for i, ((x, y), s, size) in enumerate(C.TEXTS):
        items.append([atom('text'), s, [atom('exclude_from_sim'), atom('no')], [atom('at'), x, y, 0],
                      [atom('effects'), [atom('font'), [atom('size'), size, size]], [atom('justify'), atom('left')]],
                      [atom('uuid'), uid(f'text/{i}')]])
    sch += items
    sch.append([atom('sheet_instances'), [atom('path'), '/', [atom('page'), '1']]])
    sch.append([atom('embedded_fonts'), atom('no')])
    out = HW / f'{project}.kicad_sch'
    out.write_text(dump(sch) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True,
                   stdout=subprocess.DEVNULL)
    check_netlist(out, nets, {f"{p['ref']}/{n}" for p in parts for n, net in p['pins'].items() if net is None})
    print(out, f'{len(nets)} nets, {len({p["ref"] for p in parts if not p["ref"].startswith("#")})} parts')


if __name__ == '__main__':
    syms = symbol_library()
    for name in (sys.argv[1:] or PROJECTS):
        build(name, syms)
