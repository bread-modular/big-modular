"""S8 P1 trial placement: every part on F, group by group, NO copper (user direction, 2026-11-01).
S8.1 / P1.1 (review fixes, same day): the guard reference U21 + C67 sits above U20 between the shifted OV
dividers and the MON_OVN clamp D22; R100 takes the free slot of the R98/R99 column, TP17 the rear row; D15
moved to the free spot left of its old place to make room.
S8.3 / P1.3: U23 TPS259470A and split +5V banks replace the S8.2 crowbar. The U11 timer stays
in its S8.2 position. U12 shifts 0.8 mm; R91 and TP11/TP16 move to make room for the bank.
All fixed mechanical parts stay put. This is a FIT draft: shorten U23 bypass/clamp loops before routing.
Use sync_candidate(source_board, output_root) for a separate native-preserving synchronization;
--write is the older seed-based placement entry point, not a native edit-preservation tool.

  python3 -B tools/place_s8.py [--write] [--png <file>] [--force]

"Use single side for now. [...] Don't route for now. But try to see the fit and etc. make them to the
PCB, brackets and etc. So I can get a review from someone else."

Starts from the P0 seed (tools/build_s8_board.py: Z50 outline, J1/SW1/D8 at the panel, J2/J3 at the
rear edge, everything else parked) and moves every other part to the native position below. Native
frame: x = Y + 35.75, y = 104.275 - Z (panel/front edge at the bottom of the KiCad view, rear edge
with J2/J3 at the top, module top Y14 on the left). Positions are footprint origins (x, y, rotation).

Floor plan (one functional group per region, see docs/s8-single-board.md):
  rear-left    monitors + overvoltage guard (U18, U20, references, dividers) and the bad-status filter
  front-left   USB-C PD input, fuse, TVS, D10, U5 main eFuse, VIN damper, always-on LDO, MAIN LED driver
  rear strip   header caps / clamps right at the J2 and J3 rail pins
  middle-right +12V cell (U2/L1) and +5V cell (U3/L2) in front of J2, -12V cell (U4/L3) in front of J3
  front-right  latch / reset / timer logic around SW1, +5V series disconnect and split capacitor bank

--write refuses a board with copper/zones and a board whose placement was edited outside this table
(it must equal the seed or the last placement this tool wrote, docs/s8-single/placement.json).
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_s8  # noqa: E402
import build_s8_board as seed  # noqa: E402

MODULE = Path(__file__).resolve().parents[1]
BOARD = build_s8.single_dir() / f'{build_s8.STEM}.kicad_pcb'
RECORD = MODULE / 'docs/s8-single/placement.json'


def shifted(table, dx, dy):
    return {r: (round(x + dx, 3), round(y + dy, 3), a) for r, (x, y, a) in table.items()}


# ---- Converter cell template: the routed R3 TOP +12V group (U2/L1, hardware/usb-power-45w-top.kicad_pcb),
# reused for both TPS62933F rails. L vertical with its SW pad toward the IC, the output column beside L,
# input caps C(in) under the column, BOOT/SS/FB on the far side of the IC from the SW copper.
TOP_12V = {'L1': (66.05, 69.875, 90), 'U2': (66.75, 78.275, 180), 'C6': (74.25, 78.575, 90),
           'C7': (71.75, 78.575, 90), 'C8': (69.35, 77.775, 90), 'C9': (66.75, 80.975, 0),
           'C10': (64.15, 77.775, 90), 'R8': (63.35, 81.775, 180), 'R9': (63.35, 80.175, 180),
           'C11': (73.85, 64.675, 0), 'C12': (73.85, 67.075, 0), 'C13': (73.85, 69.475, 0), 'C14': (73.85, 71.875, 0)}
AS_5V = {'L1': 'L2', 'U2': 'U3', 'C6': 'C15', 'C7': 'C16', 'C8': 'C17', 'C9': 'C18', 'C10': 'C19', 'R8': 'R11',
         'R9': 'R12', 'C11': 'C20', 'C12': 'C21', 'C13': 'C22', 'C14': 'C23'}
CELL_DY = 6.97                     # column top courtyard (TOP y 63.48) -> y 70.45, below the header strip
P12 = shifted(TOP_12V, 27.84, CELL_DY)                                  # x 88.5 .. 104.04
P5 = {AS_5V[r]: v for r, v in shifted(TOP_12V, 27.84 + 15.6, CELL_DY).items()}   # x 104.1 .. 119.64

GROUPS = [
    ('+12V converter (U2/L1)',
     'R3 TOP +12V group moved as one block (dx 27.84, dy 6.97): output column C11-C14 right under the J2 '
     '+12V pins (x 101.6), SW pad of L1 above the U2 SW pin, C8 at VIN/GND, FB divider away from SW',
     P12),
    ('+5V converter (U3/L2)',
     'Same block as +12V (same IC, same layout) one cell to the right; R10 (RT) at U3 pin 1',
     {**P5, 'R10': (112.79, 87.85, 270)}),
    ('Header strip (J2/J3 rail pins)',
     'Header ceramics, the +12/+5 polarity clamps and the +5V TVS in one row 3.9 mm in front of the J2/J3 pins '
     'they serve (where a backfeed or transient from the rack enters)',
     {'D3': (92.0, 68.45, 0), 'C35': (97.95, 68.45, 0), 'C34': (102.7, 68.45, 0), 'D2': (108.65, 68.45, 0),
      'C36': (114.6, 68.45, 180),
      'D23': (122.9, 68.45, 0), 'C60': (128.85, 68.45, 0), 'C59': (133.6, 68.45, 0)}),
    ('-12V converter (U4/L3)',
     'Compact inverting cell in front of J3: C27/C25/C26 (VIN to the IC ground -12V) at pins 3/1, BOOT C28 '
     'between U4 and L3, SW pin 2.5 mm from L3, output row (C29-C32 + C61) behind L3 at the J3 -12V pins, '
     '-12V pour area behind U4 (D4, C33), FB/RT/EN network on the side away from SW',
     {'U4': (130.8, 79.2, 0), 'C28': (135.4, 77.9, 270), 'L3': (142.65, 79.1, 0),
      'C27': (125.9, 78.55, 90), 'C25': (123.5, 78.55, 90), 'C26': (121.1, 78.55, 90), 'C24': (130.2, 86.6, 0),
      'R13': (127.6, 83.6, 90), 'R14': (131.55, 83.6, 270), 'R15': (133.2, 83.6, 270),
      'Q1': (122.6, 84.4, 0), 'R17': (125.35, 84.4, 90), 'R18': (125.35, 87.5, 90), 'R16': (121.5, 81.7, 0),
      'D4': (130.0, 74.4, 0), 'C33': (122.3, 72.1, 0),
      'C29': (137.2, 70.0, 270), 'C30': (139.6, 70.0, 270), 'C61': (142.0, 70.0, 90), 'C31': (144.4, 70.0, 270),
      'C32': (146.8, 70.0, 270)}),
    ('USB-C PD input, fuse, TVS, D10, U5 main eFuse (BASE R3 block)',
     'Routed R3 BASE input group kept at the same native coordinates: F1 right behind J1, D10/D1 behind it, '
     'CH224A with Q2/Q3/D9/D11 beside it, U5 and its UV/OV/ILIM/IMON/dVdT parts on the left',
     {'F1': (69.25, 92.7, 0), 'D10': (69.25, 88.05, 0), 'D1': (78.0, 85.55, 0), 'Q2': (76.2, 80.65, 0),
      'Q3': (80.35, 81.2, 90), 'U1': (84.95, 83.35, 270), 'D11': (76.85, 76.25, 0), 'D9': (84.05, 74.55, 0),
      'R27': (70.95, 76.9, 0), 'R23': (71.5, 80.5, 90), 'R2': (75.05, 89.45, 90), 'R3': (65.35, 92.3, 0),
      'C1': (83.45, 77.95, 90), 'C3': (64.45, 83.05, 90), 'R24': (64.45, 79.9, 90), 'U5': (60.05, 80.3, 90),
      'C2': (55.65, 80.3, 90), 'R5': (55.65, 77.15, 270), 'R29': (54.05, 77.15, 90), 'R26': (60.05, 75.5, 180),
      'R4': (67.0, 76.65, 180), 'R28': (78.6, 73.2, 180), 'R1': (88.55, 85.85, 90),
      'TP1': (81.55, 78.1, 90), 'TP2': (85.35, 78.45, 0), 'TP8': (68.2, 74.1, 90)}),
    ('MAIN LED driver (BASE R3)', 'Q6/R22 behind D8, Q10 (RUN-gated return) as on BASE',
     {'Q6': (77.48, 93.32, 270), 'R22': (80.02, 93.4, 270), 'Q10': (67.75, 81.25, 0)}),
    ('Always-on LDO U9', 'VPD in from the rear (D1/U1 side), V3V3 out toward the front strip; C46 VPD, C47/C48 V3V3',
     {'U9': (85.0, 92.2, 90), 'C46': (85.0, 88.1, 0), 'C47': (85.1, 97.3, 0)}),
    ('VIN damper (R92 + C5 + C62)', 'On the VIN bus at the rear-left corner (In2 VIN plane), TP4 = VIN',
     {'C5': (52.3, 58.5, 90), 'C62': (54.8, 58.5, 90), 'R92': (57.3, 58.5, 90), 'TP4': (59.7, 56.6, 0)}),
    ('Monitors + overvoltage guard (U18, U20)',
     'Two LM2901B side by side in the rear-left; every divider/pull-up in a 0603 column next to the pin it serves '
     '(left of U18: +12/+5 dividers and outputs; between them: VPD/-12V dividers and the REF divider; right of '
     'U20: OV_N pull-up, REF_OV bias R100, -12V OV divider); in front of U20 the OV dividers (shifted left, S8.1), the '
     'TLV431 U21 with C67 above U20 pins 5/7/10 and the MON_OVN clamp D22 above C66/R99; D15 left of the dividers; '
     'status test pads (TP17 = REF_OV) in the rear row',
     {'U18': (68.95, 63.0, 0), 'U20': (81.3, 63.0, 0),
      'R35': (63.6, 59.95, 90), 'C57': (63.6, 63.0, 90), 'R76': (63.6, 66.05, 90),
      'R44': (61.95, 59.95, 90), 'R79': (61.95, 63.0, 90), 'R75': (61.95, 66.05, 90),
      'R62': (73.55, 59.95, 90), 'R84': (73.55, 63.0, 90), 'R81': (73.55, 66.05, 90),
      'R85': (75.15, 59.95, 90), 'R83': (75.15, 63.0, 90), 'R82': (75.15, 66.05, 90),
      'R73': (76.75, 59.95, 90), 'R74': (76.75, 63.0, 90), 'C56': (76.75, 66.05, 90),
      'R97': (85.9, 59.95, 90), 'C65': (85.9, 63.0, 90), 'C66': (85.9, 66.05, 270),
      'R100': (87.5, 59.95, 270), 'R98': (87.5, 63.0, 270), 'R99': (87.5, 66.05, 270),
      'R78': (63.2, 68.45, 0), 'R77': (66.4, 68.45, 0), 'R80': (69.6, 68.45, 0), 'D15': (71.3, 73.15, 0),
      'C63': (75.4, 68.45, 0), 'C64': (78.6, 68.45, 0), 'R94': (75.4, 70.05, 0), 'R96': (78.6, 70.05, 0),
      'R93': (75.4, 71.65, 0), 'R95': (78.6, 71.65, 0),
      'U21': (82.2, 69.4, 0), 'C67': (82.2, 71.95, 0), 'D22': (86.45, 69.4, 180),
      'TP12': (63.5, 56.6, 0), 'TP13': (66.0, 56.6, 0), 'TP14': (71.5, 56.6, 0), 'TP15': (74.0, 56.6, 0),
      'TP17': (80.0, 56.6, 0), 'TP6': (85.0, 56.6, 0)}),
    ('Bad-status filter (U14 NAND, R72/C51, U15 Schmitt)',
     'Next to the monitors whose outputs it combines: U14 inputs face U18, ANY_BAD -> R72/C51 -> U15',
     {'U14': (56.5, 66.4, 180), 'U15': (55.9, 73.5, 0), 'R72': (59.3, 72.75, 90), 'C51': (60.9, 72.75, 90),
      'C54': (51.9, 72.9, 90), 'C55': (51.9, 69.4, 90), 'TP7': (64.75, 74.8, 90), 'TP3': (62.8, 86.5, 0)}),
    ('Latch / reset / timer logic (U10-U13)',
     'Front strip around SW1: U10 (POR + RESET) right behind SW1, U13 AND gates and U12 latch either side, U11 '
     'start timer on the right (P1.2: moved right, above the crowbar SCR: R71/C52/C50 in one row under C24, '
     'C49/R70/R69 beside its CT/SENSE pins); pull-ups/dividers at their pins; RUN/ARMED/FAULT/V3V3 test pads at the front',
     {'U13': (94.2, 94.4, 90), 'U12': (112.6, 94.4, 90), 'U10': (104.75, 92.3, 0), 'U11': (128.4, 92.35, 0),
      'C53': (88.8, 94.4, 90), 'C52': (130.85, 88.65, 0), 'C48': (101.4, 93.7, 90),
      'R68': (103.75, 94.85, 0), 'R67': (99.75, 90.6, 90), 'R91': (99.8, 96.8, 90), 'R65': (101.4, 90.6, 90),
      'R66': (99.75, 93.7, 90), 'R71': (127.75, 88.65, 0), 'R70': (132.95, 92.6, 90), 'R69': (134.55, 92.6, 90),
      'C49': (131.35, 92.6, 90), 'C50': (133.95, 88.65, 0), 'R63': (95.5, 89.85, 0), 'R64': (92.0, 99.6, 0),
      'TP9': (94.6, 99.8, 0), 'TP10': (96.9, 99.8, 0), 'TP5': (99.1, 99.8, 0), 'TP11': (65.0, 71.4, 0),
      'TP16': (67.3, 71.4, 0)}),
    ('+5V series disconnect (S8.3)',
     'U23 replaces the crowbar trigger. C73/C74 downstream; C69-C72/C75/C76 extend the upstream bank. '
     'D21 on P5_RAW in the cleared SCR area; D23 at the headers. Fit placement only: tighten D21/D23/local '
     'bypass loops around U23 before routing; distributed bulk ceramics are not an ideal lumped bank.',
     {'U23': (120.1, 91.15, 0),
      'R101': (119.7, 87.73, 270), 'R102': (121.3, 87.73, 90), 'R107': (122.9, 87.73, 270),
      'R103': (123.4, 91.15, 90), 'R104': (125.0, 91.15, 90), 'C68': (123.8, 94.1, 0),
      'C73': (119.8, 95.5, 0), 'C74': (120.1, 98.0, 0),
      'C69': (124.8, 96.8, 0), 'C70': (124.8, 99.3, 0),
      'C71': (129.55, 96.8, 0), 'C72': (129.55, 99.3, 0),
      'D21': (133.8, 97.7, 90), 'TP18': (119.8, 100.23, 0),
      'C75': (110.7, 99.8, 0), 'C76': (115.4, 99.8, 0)}),
]


def fixed_groups():
    return GROUPS


def table():
    out = {}
    for name, why, parts in fixed_groups():
        for r, v in parts.items():
            assert r not in out, (r, name)
            out[r] = v
    return out


def board(root=MODULE):
    b = seed.seed_board(root)
    tb = b.GetTitleBlock()
    tb.SetRevision('S8.3-P1.3')
    for i, t in enumerate(['S8.3 schematic (+5V series disconnect, U20 supply fix). P1.3 TRIAL PLACEMENT, UNROUTED: no tracks/vias/zones. Not a release.',
                           'Single carrier Y14..114.5 x Z2..50 (50 mm deep), every part on F (single-sided)',
                           'Placement: tools/place_s8.py groups; checks: tools/check_s8_board.py, docs/s8-single/board-p1.json',
                           'Nets: hardware/single/usb-power-45w-single.kicad_sch; geometry: docs/s8-single/mechanical.json']):
        tb.SetComment(i, t)
    for d in list(b.GetDrawings()):
        if d.GetClass() == 'PCB_TEXT' and d.GetText().startswith('PARKED OFF-BOARD'):
            b.Remove(d)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints() if fp.GetReference()}
    missing = sorted(set(fps) - set(table()) - set(seed.FIXED))
    if missing:
        print('NOT PLACED:', ', '.join(missing), file=sys.stderr)
    for r, (x, y, a) in table().items():
        assert r in fps, r
        assert r not in seed.FIXED, f'{r} is a seed/panel part'
        fp = fps[r]
        fp.SetOrientationDegrees(a)
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    return b


def snapshot(b):
    return {fp.GetReference(): [round(pcbnew.ToMM(fp.GetPosition().x), 4), round(pcbnew.ToMM(fp.GetPosition().y), 4),
                                round(fp.GetOrientationDegrees(), 3), fp.GetLayerName()]
            for fp in b.GetFootprints() if fp.GetReference()}


def write(force=False):
    dest = BOARD
    if dest.exists() and not force:
        old = pcbnew.LoadBoard(str(dest))
        if list(old.GetTracks()) or list(old.Zones()):
            raise SystemExit(f'{dest}: has copper/zones; placement is owned by the native board now.')
        cur = snapshot(old)
        prev = json.loads(RECORD.read_text())['parts'] if RECORD.exists() else None
        if prev is None:
            why = seed.seed_refusal(dest)
            if why:
                raise SystemExit(why)
        elif cur != prev:
            diff = sorted(r for r in set(cur) | set(prev) if cur.get(r) != prev.get(r))
            raise SystemExit(f'{dest}: placement differs from the last tool output ({", ".join(diff[:10])}); '
                             'edited in KiCad? Not overwritten (use --force only to discard those edits).')
    b = board()
    seed.save(b, dest)
    rec = {'note': 'Last placement written by tools/place_s8.py (guard against overwriting KiCad edits).',
           'parts': snapshot(pcbnew.LoadBoard(str(dest)))}
    RECORD.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    return dest


def sync_candidate(source_board, output_root):
    """S8-only native XML synchronization to a distinct candidate; retained identity/model preservation.

    Shared flat primitives cannot add an IC or synchronize PCB nets. Reuse the
    existing module native netlist reader and S-expression parser; pcbnew owns
    transforms/save/reload. Text metadata editing avoids this host's broken
    KiCad-10 Python GetField() wrapper (returns an untyped SWIG pointer).
    """
    import copy
    from sexp import parse, dump, nodes, one, atom, walk
    src, root = Path(source_board).resolve(), Path(output_root).resolve()
    dest = root / 'hardware/single' / BOARD.name
    assert dest.resolve() != src, 'candidate must not overwrite source'
    old = pcbnew.LoadBoard(str(src))
    assert not list(old.GetTracks()) and not list(old.Zones()), 'refuse routed/zone-bearing board'
    before = snapshot(old)
    assert before == json.loads(RECORD.read_text())['parts'], 'native placement changed since recorded baseline'
    comps, nets = seed.netlist(build_s8.root_file(root))
    membership = {rp: name for name, members in nets.items() for rp in members}
    tree = parse(src.read_text())
    def ref(f):
        return next((p[2] for p in nodes(f, 'property') if p[1] == 'Reference'), '')
    fps = {ref(f): f for f in nodes(tree, 'footprint') if ref(f)}
    original_ids = {r: one(f, 'uuid')[1] for r, f in fps.items()}
    original_models = {r: copy.deepcopy(nodes(f, 'model')) for r, f in fps.items()}
    for r in set(fps) - set(comps):
        tree.remove(fps.pop(r))
    for r, comp in comps.items():
        if r not in fps:
            f = parse((MODULE / 'hardware/USBPOWER45.pretty' / (comp['footprint'].split(':')[1] + '.kicad_mod')).read_text())
            f[1] = comp['footprint']
            f[:] = [v for v in f if not isinstance(v, list) or v[0] not in ('version', 'generator', 'uuid')]
            f.append([atom('uuid'), build_s8.uid('pcb/footprint/' + r)])
            f.append([atom('at'), 0, 0, 0])
            for i, node in enumerate(walk(f, 'uuid')):
                node[1] = build_s8.uid(f'pcb/{r}/item/{i}')
            tree.append(f); fps[r] = f
        f = fps[r]
        assert f[1] == comp['footprint'], (r, 'footprint replacement needs review')
        fields = {p[1]: p for p in nodes(f, 'property')}
        for key, val in {'Reference': r, 'Value': comp['value'], **comp['fields']}.items():
            if key in fields:
                fields[key][2] = val
            else:
                f.append(parse(f'(property {json.dumps(key)} {json.dumps(val)} (at 0 0 0) (layer "F.Fab") '
                               '(hide yes) (effects (font (size 1 1) (thickness 0.15))))'))
        for key in ('path', 'sheetname', 'sheetfile'):
            node = one(f, key)
            if node is None: f.append([atom(key), comp[key]])
            else: node[1] = comp[key]
        attrs = one(f, 'attr')
        for key, flag in [('no_bom', 'exclude_from_bom'), ('no_pos', 'exclude_from_pos_files'), ('dnp', 'dnp')]:
            if comp[key] and atom(flag) not in attrs:
                attrs.append(atom(flag))
        for i, pad in enumerate(nodes(f, 'pad')):
            if not pad[1]: continue
            net = membership[(r, str(pad[1]))]
            n = one(pad, 'net')
            if n is None: pad.append([atom('net'), net])
            else: n[1:] = [net]
            if one(pad, 'uuid') is None: pad.append([atom('uuid'), build_s8.uid(f'pcb/{r}/pad/{i}')])
        if r in original_ids:
            assert one(f, 'uuid')[1] == original_ids[r]
            assert nodes(f, 'model') == original_models[r]
    one(one(tree, 'title_block'), 'rev')[1] = 'S8.3-P1.3'
    one(one(tree, 'title_block'), 'comment')[2] = 'S8.3 +5V series disconnect; VPD comparators. P1.3 DRAFT placement, UNROUTED.'
    one(tree, 'title_block').append([atom('comment'), 5, 'S8.3: +5V series eFuse; crowbar removed; UNROUTED'])
    draft = dest.with_suffix('.sync.kicad_pcb')
    draft.write_text(dump(tree) + '\n')
    # A differently named temporary PCB otherwise loads DEFAULT design settings.
    # Bind the exact candidate project and restore it byte-for-byte after SaveBoard.
    project = dest.with_suffix('.kicad_pro')
    project_bytes = project.read_bytes()
    draft_project = draft.with_suffix('.kicad_pro')
    draft_project.write_bytes(project_bytes)
    b = pcbnew.LoadBoard(str(draft))
    for f in b.GetFootprints():
        r = f.GetReference()
        if r and r not in original_ids:
            f.Reference().SetLayer(pcbnew.F_Fab)  # same presentation as all existing S8 references
        if r in table():
            x, y, angle = table()[r]
            f.SetOrientationDegrees(angle)
            f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    # Existing native stackup/rules are already present; the seed writer would add them twice.
    pcbnew.SaveBoard(str(dest), b)
    project.write_bytes(project_bytes)
    draft.unlink()
    draft_project.unlink()
    after = snapshot(pcbnew.LoadBoard(str(dest)))
    reloaded = parse(dest.read_text())
    for f in nodes(reloaded, 'footprint'):
        r = ref(f)
        if r in original_ids:
            assert one(f, 'uuid')[1] == original_ids[r]
            assert nodes(f, 'model') == original_models[r]
    rec = {'note': 'S8.3 native synchronization; retained UUIDs/models, outline and fixed parts preserved.',
           'parts': after,
           'moved_retained_refs': sorted(r for r in set(before) & set(after) if before[r] != after[r]),
           'added_refs': sorted(set(after) - set(before)), 'removed_refs': sorted(set(before) - set(after))}
    (root / 'docs/s8-single/placement.json').write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    return dest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--png', type=Path)
    a = ap.parse_args()
    if a.write:
        print(write(a.force))
    if a.png:
        import render_s8
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'b.kicad_pcb'
            pcbnew.SaveBoard(str(p), board())
            print('overlaps:', render_s8.render(p, a.png, 'S8 P1 trial placement (work in progress)'))
        print(a.png)
