"""Readable S8 single-board hierarchy (wired power-flow overview + six pages).

Same method as tools/hierarchy6.py (S7): consumes the exact, native-verified flat S8 sheet,
moves whole wired islands onto their page, adds the explicitly listed readability links and
real hierarchical pins for every net that crosses pages, then checks native flat/hierarchy
parity (components, fields, pin memberships). Page 05 of S7 (negative protection) is gone; the
S7 pages 06/07 become 05/06. No component field or connection is changed here. S8 final: the rail
LEDs are gone, page 06 keeps the MAIN LED only. S8.1: the guard reference (U21, R100, C67, TP17) and
the MON_OVN clamp D22 join the page-06 monitor group. S8.3: the +5V disconnect and split banks replace the crowbar on page 06.
U18/U20 now run from always-on VPD with 3.3 V logic pull-ups. S8.4: U23 FLT gets its own R108/TP21 on page 06 (off P5_OK);
TIMER_GO = RUN AND MAIN_OK on page 05. S8.5 wires the one-shot arming latch on page 05 (U14 gate 2 -> START_N -> U12 A
preset; STARTED -> U13 pin 10; U11 output = ARMED -> U13 pin 4; TP19 = STARTED); page 06 is unchanged apart from notes.
S9.0: +5V removed, so the +5V converter page is gone and the pages renumber (01 input, 02 +12V, 03 -12V, 04 fault/reset,
05 outputs/status); the U23 cell, the +5V monitor/guard channels and the J2/J3 +5V pins leave page 05.
"""
import copy
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from circuit_s8 import BUCKBOOST_ADDED
from sexp import parse, dump, nodes, one, walk

PAGES = {
    1: ('01_usb_input', 'USB PD, main eFuse and VIN damper', (420, 297)),
    2: ('02_positive_12v', '+12 V buck-boost converter', (420, 297)),
    3: ('03_negative_converter', '-12 V inverting converter', (420, 297)),
    4: ('04_fault_reset', 'Always-on control - fault latch, overvoltage preset and RESET', (550, 420)),
    5: ('05_outputs_status', 'Two output headers - monitors, overvoltage guard and MAIN LED', (550, 390)),
}


# Page notes clear of the inter-sheet interface text (height - 71.12) and of the S8 parts.
NOTE_AT = {1: (20.32, 180.34), 2: (20.32, 190.5), 3: (20.32, 180.34), 4: (381.0, 320.04), 5: (20.32, 30.48)}


def layout(parts):
    """Page and translation per reference (S7 offsets kept for every retained group)."""
    plan = {}

    def put(refs, page, dx, dy):
        for ref in refs:
            assert ref in parts and ref not in plan, ref
            plan[ref] = (page, dx, dy)
    rr = lambda prefix, a, b: [prefix + str(i) for i in range(a, b + 1)]
    put(['U2', 'L1', 'R8', 'R9', *rr('C', 6, 14), '#FLG04', *BUCKBOOST_ADDED, 'R113', '#FLG10', 'D26'], 2, -276.86, 0)
    put(['U4', 'L3', 'Q1', 'Q14', 'Q15', 'R112', *rr('R', 13, 18), *rr('C', 24, 33), '#FLG03'], 3, 0, -147.32)
    put(['D2'], 2, -25.4, -203.2)
    put(['D4'], 3, -50.8, -241.3)
    put(['J2', 'J3', 'C34', 'C36', 'C59', 'C61'], 5, 0, -86.36)
    put(['SW1'], 4, -38.1, -254)
    put(['U9', 'U10', 'U11', 'U12', 'U13', 'U14', 'U15', *rr('R', 63, 72), 'R91', *rr('C', 46, 55),
         'TP9', 'TP10', 'TP11', 'TP12', 'TP14', 'TP15', 'TP16', 'TP6', 'TP19'], 4, 0, -393.7)
    put(['U18', 'U20', 'D15', *rr('R', 73, 76), *rr('R', 80, 85), 'R35', 'R62', 'R93', 'R94', 'R97', 'R98', 'R99',
         'C56', 'C57', 'C63', 'C65', 'C66', 'U21', 'R100', 'C67', 'TP17', 'D22'], 5, -599.44, -508)
    put(['D8', 'R22', 'Q6', 'Q10'], 5, -599.44, -508)
    put([ref for ref in parts if ref not in plan], 1, 0, 0)
    return plan


NOTES = {
 1: 'S9.1: 15 V / 3 A PD, R1 56k. U5 UVLO: R2 100k 0.1% / (R3 10k 0.1% + R114 510R 1%).\n'
    'Worst start <13.0 V; range 13.5-16.5 V at module incl. <=0.75 V cable drop. OVP unchanged.\n'
    'D24 SMBJ16A VIN pulse clamp (600 W 10/1000 us, 26 V rated clamp); not a continuous shunt.\n'
    'D25: low-current negative clamp, slew-limited room-temperature test only. See calcs residuals.',
 2: 'S9.1: TPS552892-Q1, 966 kHz, L1 6.8u; R109 18mR 1W (2.62-2.94 A). Rating +12V 2.4 A, total <=33 W.\n'
    'AGND_U2: U2.5/.17, R9, R110, C83, C82. ONLY join to PGND (GND) through R113 at C82 ground terminal.\n'
    'COMP R111 6.8k / C83 100n (zero 234 Hz). Rack <=0.44 mF with bounded cable impedance; see full loop sweep.\n'
    'R109 is a slow OUTPUT current limit, not a switch limit. Thermal / Bode measurements remain release gates.',
 3: 'S9.1: U4 enable is powered from own VPD upstream of D10, NEVER from +12V or pumped VIN.\n'
    'Q14 RUN and Q15 MAIN_LED_OK form an AND sink for Q1 base; R112 returns base to emitter when either is off.\n'
    'EN_N relative to -12V = (VPD - VCEsat - V(-12V))/6 only when qualified; otherwise R18 holds it at 0 V.\n'
    'Unpowered or latched-off live +/-12V bus cannot self-enable U4. No reverse-power blocking is claimed.\n'
    'LMR38020F power stage unchanged. Powered parallel supplies and unrestricted hotplug remain prohibited.',
 4: 'S9.1 retains S8.5 STARTED one-shot: START_N = NAND(MAIN_LED_OK,RUN); TIMER_GO = RUN AND STARTED.\n'
    'U11 -> ARMED after 0.31-0.88 s. RESET clears STARTED/FAULT; U20 OV_N presets FAULT even before ARMED.\n'
    'A full V3V3/POR reset DOES re-arm: qualification rejects repetitive hard-reset sources; no masking by retries.\n'
    'ANY_BAD = NAND(MAIN_LED_OK,P12_OK,N12_OK,V3V3). R83 100k validity floor unchanged.',
 5: 'S9.1: +/-12V only, J2/J3 pins 11-16 NC. MAIN LED only. U18/U20 on VPD, own REF_OV unchanged.\n'
    'Guard +12V 14.48-15.27 V, -12V magnitude 13.27-14.02 V. Guard disconnects INPUT, not an external bus.\n'
    'No rail crowbar or eFuse. Uninjected rails decay with load; injected rail remains at the external voltage.\n'
    'See docs/s8-single-board.md for separate latch, clamp, discharge and survival acceptance criteria.'}
REV = 'S9.1'
PAGE_COMMENT = 'S9.1 review fixes; P2.1 UNROUTED; docs/s8-single-board.md'
ROOT_TITLE = ('USB POWER S9.1 / SINGLE BOARD, +/-12V ONLY, 15 V PD INPUT',
              'Own-input enable; VIN pulse clamp; split U2 grounds; STARTED one-shot; no output crowbar.')
DESCRIPTIONS = {1:'15 V PD / TPS16630 / VIN clamp', 2:'TPS552892-Q1 buck-boost / split AGND',
                3:'LMR38020F / own-input enable', 4:'Always-on logic / STARTED + FAULT / RESET',
                5:'Parallel +/-12V headers / monitors / MAIN LED'}
ROOT_RAIL_LINKS = (((2, '+12V'), (5, '+12V'), 304.8), ((3, '-12V'), (5, '-12V'), 330.2))
ROOT_FAULT_POLICY = ('ONE-SHOT FAULT POLICY\nSTARTED retains the first start within each power epoch.\n'
                     'Faults cannot restart it; full power reset CAN. Repeated source resets FAIL qualification.\n'
                     'OV_N presets FAULT asynchronously. Crowbar vs eFuse deferred/open.')
ROOT_OUTPUTS = ('+12V 2.4 A / -12V 0.8 A, <=33 W together (prototype, not measured).\n'
                '13.5-16.5 V at module; 15 V / 3 A PD. Rack +12V <=0.44 mF, impedance bounds in calcs.\n'
                'No reverse-current blocking; no powered parallel supply or unrestricted hotplug qualification.')


def split(root_path, docs_dir, api):
    """root_path: S8 root schematic (flat intermediate on entry); api: build_s8 module namespace."""
    hw = Path(root_path).parent
    docs_dir = Path(docs_dir)
    out = Path(root_path)
    flat = parse(out.read_text()); rootid = one(flat, 'uuid')[1]
    partlist = api.circuit(); parts = {p['ref']: p for p in partlist}; plan = layout(parts)
    flatxml = docs_dir / 'flat-parity.xml'
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(flatxml), str(out)],
                   check=True, stdout=subprocess.DEVNULL)
    expected = ET.parse(flatxml).getroot()
    libs = {s[1]: s for s in nodes(one(flat, 'lib_symbols'), 'symbol')}
    symbols = nodes(flat, 'symbol')
    refs = {next(p[2] for p in nodes(s, 'property') if p[1] == 'Reference'): s for s in symbols}
    parent = {}

    def find(p):
        parent.setdefault(p, p)
        if parent[p] != p:
            parent[p] = find(parent[p])
        return parent[p]

    def union(a, b):
        parent[find(a)] = find(b)
    xy = lambda n: tuple(map(float, one(n, 'at')[1:3]))
    for w in nodes(flat, 'wire'):
        a, b = [tuple(map(float, p[1:])) for p in one(w, 'pts')[1:]]
        union(a, b)
    pins = {}; directions = {}; owners = defaultdict(set); islandnets = defaultdict(set)
    for ref, s in refs.items():
        tab = api.pin_table(libs[one(s, 'lib_id')[1]], int(one(s, 'unit')[1]))
        x, y = xy(s); rot = float(one(s, 'at')[3]); mir = one(s, 'mirror') is not None
        for num, (px, py, ang, typ) in tab.items():
            dx, dy = api.xform(px, -py if mir else py, rot); pt = (round(x + dx, 2), round(y + dy, 2))
            pins[(ref, num)] = pt
            if ref in plan:
                owners[find(pt)].add(plan[ref])
                islandnets[find(pt)].add(parts[ref]['pins'][num] or ('NC:' + ref + '.' + num))
                directions[ref + '.' + num] = api.outward(-ang if mir else ang, rot)

    def island(pt):
        opts = owners[find(pt)]
        assert len(opts) == 1, ('island not a single planned placement transform', pt, opts)
        return next(iter(opts))
    sheetids = {i: api.uid('S8/sheet/' + name) for i, (name, _, _) in PAGES.items()}
    trees = {}
    for i, (name, title, size) in PAGES.items():
        trees[i] = parse(f'''(kicad_sch (version 20260306) (generator "eeschema") (generator_version "10.0")
          (uuid "{api.uid('S8/file/' + name)}") (paper "User" {size[0]} {size[1]})
          (title_block (title {json.dumps(title)}) (rev "{REV}") (company "Big Modular")
          (comment 1 {json.dumps(PAGE_COMMENT)}))
          (lib_symbols) (embedded_fonts no))''')
        one(trees[i], 'lib_symbols').extend(copy.deepcopy(nodes(one(flat, 'lib_symbols'), 'symbol')))

    def move(node, dx, dy):
        for loc in [one(node, 'at'), *[one(p, 'at') for p in nodes(node, 'property')]]:
            if loc:
                loc[1] = round(float(loc[1]) + dx, 2); loc[2] = round(float(loc[2]) + dy, 2)
        if node[0] == 'wire':
            for p in one(node, 'pts')[1:]:
                p[1] = round(float(p[1]) + dx, 2); p[2] = round(float(p[2]) + dy, 2)
    for n in flat:
        if not isinstance(n, list):
            continue
        kind = n[0]
        if kind == 'symbol':
            ref = next(p[2] for p in nodes(n, 'property') if p[1] == 'Reference')
            pg, dx, dy = plan[ref] if ref in plan else island(xy(n))
        elif kind == 'wire':
            pg, dx, dy = island(tuple(map(float, one(n, 'pts')[1][1:])))
        elif kind in ('label', 'junction', 'no_connect'):
            pg, dx, dy = island(xy(n))
        else:
            continue
        nn = copy.deepcopy(n); move(nn, dx, dy)
        if kind == 'symbol':
            for path in walk(one(nn, 'instances'), 'path'):
                path[1] = '/' + rootid + '/' + sheetids[pg]
        trees[pg].append(nn)
    ends = {}
    for (ref, pin), pt in pins.items():
        if ref in plan:
            pg, dx, dy = plan[ref]; ends[ref + '.' + pin] = (round(pt[0] + dx, 2), round(pt[1] + dy, 2))
    pin_nets = {p['ref'] + '.' + n: v or ('NC:' + p['ref'] + '.' + n) for p in partlist for n, v in p['pins'].items()}
    obstacles = defaultdict(list); pinpoints = defaultdict(dict)
    for key, pt in ends.items():
        pinpoints[plan[key.split('.')[0]][0]][pt] = pin_nets[key]
    for w in nodes(flat, 'wire'):
        a, b = [tuple(map(float, p[1:])) for p in one(w, 'pts')[1:]]; pg, dx, dy = island(a)
        ns = islandnets[find(a)]; assert len(ns) == 1
        obstacles[pg].append(((round(a[0] + dx, 2), round(a[1] + dy, 2)), (round(b[0] + dx, 2), round(b[1] + dy, 2)),
                              next(iter(ns))))
    routes = []
    count = 0

    def text(t, s, x, y, size=1.25):
        nonlocal count
        count += 1
        t.append(parse(f'(text {json.dumps(s)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left top)) '
                       f'(uuid "{api.uid("S8/text/" + str(count))}"))'))

    def line(t, *points):
        nonlocal count
        pts = [ends[p] if isinstance(p, str) else p for p in points]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            assert a[0] == b[0] or a[1] == b[1], ('nonorthogonal', points, a, b)
            count += 1
            t.append(parse(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) '
                           f'(uuid "{api.uid("S8/wire/" + str(count))}"))'))

    def link(pg, a, b, lane=None):
        """Explicit schematic-only lane for one listed connection (see hierarchy6.link)."""
        aa, bb = ends[a], ends[b]; net = pin_nets[a]; assert net == pin_nets[b], (a, b, net, pin_nets[b])

        def on(p, x, y):
            return (min(x[0], y[0]) <= p[0] <= max(x[0], y[0]) and min(x[1], y[1]) <= p[1] <= max(x[1], y[1])
                    and (x[0] == y[0] == p[0] or x[1] == y[1] == p[1]))

        def clear(path):
            for x, y in zip(path, path[1:]):
                if x == y:
                    continue
                for pt, n in pinpoints[pg].items():
                    if n != net and on(pt, x, y):
                        return False
                for c, d, n in obstacles[pg]:
                    if n == net:
                        continue
                    if any(on(pt, c, d) for pt in (x, y)) or any(on(pt, x, y) for pt in (c, d)):
                        return False
            return True
        da, db = directions[a], directions[b]
        candidates = []
        if aa[0] == bb[0] or aa[1] == bb[1]:
            candidates.append([aa, bb])
        for escape in (5.08, 3.81, 2.54, 6.35, 7.62, 8.89, 10.16, 11.43, 12.7, 15.24):
            sa = (round(aa[0] + da[0] * escape, 2), round(aa[1] + da[1] * escape, 2))
            sb = (round(bb[0] + db[0] * escape, 2), round(bb[1] + db[1] * escape, 2))
            for axis in ('x', 'y'):
                dim = 0 if axis == 'x' else 1; size = PAGES[pg][2][dim]
                target = lane[1] if lane and lane[0] == axis else (sa[dim] + sb[dim]) / 2
                values = sorted([round(15.24 + k * 1.27, 3) for k in range(int((size - 30.48) / 1.27))],
                                key=lambda v: abs(v - target))
                if lane and lane[0] == axis:
                    values = [lane[1]] + values
                for v in values:
                    path = ([aa, sa, (v, sa[1]), (v, sb[1]), sb, bb] if axis == 'x'
                            else [aa, sa, (sa[0], v), (sb[0], v), sb, bb])
                    if clear(path):
                        candidates.append(path); break
        candidates = [p for p in candidates if clear(p)]
        assert candidates, ('No safe schematic lane', pg, a, b)

        def score(path):
            manual = lane and any(abs(pt[0 if lane[0] == 'x' else 1] - lane[1]) < .001 for pt in path[1:-1])
            return (0 if manual else 1, sum(abs(x[0] - y[0]) + abs(x[1] - y[1]) for x, y in zip(path, path[1:])))
        path = min(candidates, key=score)
        line(trees[pg], *path)
        obstacles[pg].extend((x, y, net) for x, y in zip(path, path[1:]) if x != y)
        routes.append({'page': pg, 'from': a, 'to': b, 'net': net, 'path': path})

    # Logic chain (S7 page 06 -> S9 page 04): stored-state feedback and clocks are wired.
    link(4, 'U10.1', 'U12.1', ('y', 152.4)); link(4, 'U12.1', 'U12.13', ('x', 27.94))
    link(4, 'U12.8', 'U13.2', ('y', 271.78))
    link(4, 'U13.6', 'U12.11', ('y', 281.94))
    link(4, 'U14.6', 'R72.1', ('x', 396.24))
    link(4, 'R72.2', 'C51.1'); link(4, 'C51.1', 'U15.2', ('x', 485.14))
    link(4, 'U15.4', 'U13.5', ('y', 297.18))
    # S8.5 one-shot arming: ARMED is the U11 output (level), STARTED the U12 A latch, START_N its preset.
    link(4, 'U11.1', 'U13.4', ('y', 162.56))
    link(4, 'U14.8', 'U12.4', ('y', 246.38))
    link(4, 'U12.5', 'U13.10', ('y', 187.96))
    # Monitors and the MAIN LED gate (S7 page 07 -> S9 page 05). Rail LEDs removed (S8 final); S9.0: no +5V monitor.
    for pin, ref in [('7', 'R76'), ('8', 'R82'), ('11', 'R84')]:
        link(5, 'U18.' + pin, ref + '.1', ('x', 20.32 + int(pin) * 5.08))
    link(5, 'Q6.2', 'Q10.3', ('y', 205.74))
    for a, b, lane in [('U9.1', 'C47.1', None), ('R66.1', 'U10.5', ('x', 139.7)), ('U10.3', 'SW1.1', ('y', 45.72)),
                       ('R70.1', 'U11.5', ('x', 259.08)), ('U11.4', 'C49.1', ('x', 335.28))]:
        link(4, a, b, lane)
    link(5, 'D15.3', 'R82.1', ('y', 185.42))
    (docs_dir / 'schematic-wiring.json').write_text(json.dumps(routes, indent=2) + '\n')

    # Inter-sheet nets from the circuit table; each gets a real hierarchical pin. GND alone is global.
    netpages = defaultdict(set)
    for p in partlist:
        for n in p['pins'].values():
            if n is not None:
                netpages[n].add(plan[p['ref']][0])
    crossing = {n: pgs for n, pgs in netpages.items() if len(pgs) > 1 and n != 'GND'}
    for pg, t in trees.items():
        text(t, PAGES[pg][1].upper(), 20.32, 12.7, 2)
        names = sorted(n for n, pgs in crossing.items() if pg in pgs)
        width, height = PAGES[pg][2]
        for i, n in enumerate(names):
            cols = 4 if width < 500 else 5
            x = 25.4 + (i % cols) * 88.9; y = round(round((height - 50.8) / 1.27) * 1.27 + (i // cols) * 10.16, 2)
            line(t, (x, y), (x + 15.24, y))
            count += 1
            t.append(parse(f'(hierarchical_label {json.dumps(n)} (shape bidirectional) (at {x} {y} 180) '
                           f'(effects (font (size 1.1 1.1)) (justify right)) (uuid "{api.uid("S8/port/" + str(pg) + n)}"))'))
            t.append(parse(f'(label {json.dumps(n)} (at {x + 15.24} {y} 0) (effects (font (size 1.1 1.1)) '
                           f'(justify left bottom)) (uuid "{api.uid("S8/port-label/" + str(pg) + n)}"))'))
        text(t, 'INTER-SHEET INTERFACE (see wired power-flow overview)', 20.32, height - 71.12, 1.2)
    for pg, msg in NOTES.items():
        text(trees[pg], msg, *NOTE_AT[pg], 1.15)

    # Overview: main power paths wired, control interfaces named at each block.
    root = copy.deepcopy(flat)
    root[:] = [n for n in root if not isinstance(n, list) or n[0] in
               ['version', 'generator', 'generator_version', 'uuid', 'paper', 'title_block', 'lib_symbols', 'embedded_fonts']]
    one(root, 'paper')[1:] = ['User', 560, 530]; one(root, 'lib_symbols')[1:] = []
    one(one(root, 'title_block'), 'title')[1] = 'USB power S9 single board - wired power flow overview'
    for t, (x, y, size) in zip(ROOT_TITLE, ((20.32, 15.24, 2.4), (20.32, 25.4, 1.2))):
        text(root, t, x, y, size)
    boxes = {1: (40.64, 60.96, 81.28, 111.76), 2: (177.8, 50.8, 101.6, 81.28),
             3: (177.8, 284.48, 101.6, 71.12), 4: (40.64, 406.4, 259.08, 96.52), 5: (370.84, 60.96, 106.68, 254.0)}
    outputs = {1: ['VPD', 'VIN', 'MAIN_OK'], 2: ['+12V'], 3: ['-12V'],
               4: ['RUN', 'V3V3', 'MAIN_LED_OK', 'FAULT_LATCH'], 5: ['P12_OK', 'N12_OK', 'V20_OK', 'OV_N']}
    descriptions = DESCRIPTIONS
    rootpins = {}
    for pg, (x, y, w, h) in boxes.items():
        names = sorted(n for n, pgs in crossing.items() if pg in pgs)
        right = [n for n in outputs[pg] if n in names]; left = [n for n in names if n not in right]
        sh = parse(f'''(sheet (at {x} {y}) (size {w} {h}) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0))
          (uuid "{sheetids[pg]}") (property "Sheetname" {json.dumps(PAGES[pg][1])} (at {x} {y - 2.54} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
          (property "Sheetfile" {json.dumps(PAGES[pg][0] + '.kicad_sch')} (at {x} {y + h + 2.54} 0) (effects (font (size 1.1 1.1)) (justify left top)))
          (instances (project "{api.PROJECT}" (path "/{rootid}" (page "{pg + 1}")))))''')
        for side, ns in [('L', left), ('R', right)]:
            for k, n in enumerate(ns):
                px = x if side == 'L' else x + w; py = round(y + 10.16 + k * 7.62, 2); ang = 180 if side == 'L' else 0
                rootpins[(pg, n)] = (px, py)
                sh.append(parse(f'(pin {json.dumps(n)} bidirectional (at {px} {py} {ang}) (effects (font (size 1.1 1.1)) '
                                f'(justify {"left" if side == "L" else "right"})) (uuid "{api.uid("S8/sheetpin/" + str(pg) + n)}"))'))
        root.append(sh)
        text(root, descriptions[pg], x + 10.16, y + h - 20.32, 1.4)

    def rootlink(a, b, lane):
        aa, bb = rootpins[a], rootpins[b]; line(root, aa, (lane, aa[1]), (lane, bb[1]), bb)
    for pg in [2, 3]:
        rootlink((1, 'VIN'), (pg, 'VIN'), 137.16)
    for a, b, lane in ROOT_RAIL_LINKS:
        rootlink(a, b, lane)
    for key, pt in rootpins.items():
        n = key[1]; side = 'R' if n in outputs[key[0]] else 'L'; dx = 7.62 if side == 'R' else -7.62
        target = (round(pt[0] + dx, 2), pt[1]); line(root, pt, target)
        count += 1
        root.append(parse(f'(label {json.dumps(n)} (at {target[0]} {target[1]} {0 if side == "R" else 180}) '
                          f'(effects (font (size 1 1)) (justify {"left" if side == "R" else "right"} bottom)) '
                          f'(uuid "{api.uid("S8/rootlabel/" + str(count))}"))'))
    text(root, ROOT_FAULT_POLICY, 370.84, 340.36, 1.4)
    text(root, ROOT_OUTPUTS, 370.84, 386.08, 1.2)
    trees[0] = root
    # Split added wires at endpoints and pin ends, then add junctions (as hierarchy6).
    for pg, t in trees.items():
        allpins = ({pt for key, pt in ends.items() if plan[key.split('.')[0]][0] == pg} if pg
                   else set(rootpins.values()))
        anchors = allpins | {xy(n) for typ in ['label', 'hierarchical_label', 'junction'] for n in nodes(t, typ)}
        wires = [tuple(tuple(map(float, p[1:])) for p in one(w, 'pts')[1:]) for w in nodes(t, 'wire')]
        anchors |= {p for seg in wires for p in seg}
        t[:] = [n for n in t if not (isinstance(n, list) and n[0] in ('wire', 'junction'))]
        segments = set()
        for a, b in wires:
            pts = [p for p in anchors if min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
                   and (a[0] == b[0] == p[0] or a[1] == b[1] == p[1])]
            pts.sort(key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
            segments.update(tuple(sorted([aa, bb])) for aa, bb in zip(pts, pts[1:]) if aa != bb)
        degree = defaultdict(int)
        for a, b in sorted(segments):
            line(t, a, b); degree[a] += 1; degree[b] += 1
        for pt, d in degree.items():
            if d >= 3 or (d >= 2 and pt in allpins):
                count += 1
                t.append(parse(f'(junction (at {pt[0]} {pt[1]}) (diameter 0) (color 0 0 0 0) '
                               f'(uuid "{api.uid("S8/junction/" + str(count))}"))'))
        if pg:
            t.append(parse(f'(sheet_instances (path "/{rootid}/{sheetids[pg]}" (page "{pg + 1}")))'))
        else:
            t.append(parse('(sheet_instances (path "/" (page "1")))'))
        dest = out if pg == 0 else hw / (PAGES[pg][0] + '.kicad_sch')
        dest.write_text(dump(t) + '\n')
    subprocess.run(['kicad-cli', 'sch', 'upgrade', '--force', str(out)], check=True, stdout=subprocess.DEVNULL)
    xml = docs_dir / 'hierarchy-parity.xml'
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml), str(out)],
                   check=True, stdout=subprocess.DEVNULL)
    actual = ET.parse(xml).getroot()

    def identity(root):
        comps = {c.get('ref'): (c.findtext('value'), c.findtext('footprint'),
                                tuple(sorted((f.get('name'), f.text) for f in c.findall('fields/field'))))
                 for c in root.findall('components/comp')}
        nets = {frozenset((p.get('ref'), p.get('pin')) for p in n.findall('node')) for n in root.findall('nets/net')}
        return comps, nets
    want, got = identity(expected), identity(actual)
    assert want[0] == got[0], 'Hierarchy changed component values/fields/footprints'
    assert want[1] == got[1], ('Hierarchy changed nets; inspect native XML', len(want[1] ^ got[1]))
    (docs_dir / 'hierarchy-parity.json').write_text(json.dumps(
        {'equal_pin_sets': True, 'components': len(got[0]), 'sheets': len(PAGES) + 1,
         'note': 'Net paths intentionally change; exact component/pin memberships and native fields preserved.'},
        indent=2) + '\n')
    flatxml.unlink(); xml.unlink()
    print('Native S8 hierarchy:', len(PAGES) + 1, 'pages;', len(got[0]), 'parts; exact flat/hierarchy parity')
    return crossing
