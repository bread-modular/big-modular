"""S9.2 pinned land patterns: the R109 4-terminal Kelvin split land and the 1.5 mm acceptance test pad.

R109 (S9.2 item 3): a TRUE 4-terminal Kelvin land for a 2-terminal 1206 metal-alloy shunt. Each terminal land of the
TA-I RLM12 recommended pattern (2 <= R < 50 mOhm: pad length b 1.7 mm, pad width a 1.8 mm, inner gap L 1.6 mm; TA-I
TRLM-XX0S001A section 6, https://www.tai.com.tw/files/uploads/Prod_spec/RLM.pdf) is split across its width into a
FORCE pad (full 1.7 mm length, 1.1 mm wide, -y side) and a separate SENSE pad (0.5 mm wide, +y side) with a 0.2 mm gap
(= board netclass clearance). The sense pad starts at the land's INNER edge (|x| 0.8 mm, the side of the resistive
element) and runs 1.3 mm outward, so it always sits under the RLM12 electrode (C 0.5 +/- 0.3 mm from a 3.2 +/- 0.2 mm
body end) and its solder fillet, also at the minimum body width (1.4 mm): the sense potential is taken at the electrode
next to the element, not through the force copper or the force solder joint (ADI Analog Dialogue 46-2, split-pad
Kelvin footprint for 2-pad shunts). Pads 1/4 = force, 2/3 = sense, matching the KiCad Device:R_Shunt symbol (1 and 4
current, 2 sense on the pin-1 side, 3 sense on the pin-4 side). Copper-pad solder-mask expansion 0.025 mm: the
force/sense mask web is 0.15 mm. Paste 1:1. No vias.

S9.2b (owner decision 2026-11-02: NO via-in-pad anywhere on the single board): the pinned S7 land patterns of U4
(LMR38020 DDA), U5 (TPS16630 PWP) and U9 (TPS7A16 DGN) drill 8 / 15 / 4 plated holes into their exposed pads. The single
board gets hole-free copies (NO_VIA_IN_PAD): each is the pinned file with every plated hole and the B.Cu-only copy of
the exposed pad removed, and nothing else changed (lands, solder-mask window, paste apertures, courtyard, 3D model). The
S7 files stay byte-identical for the routed S7 boards. The thermal vias become standard board vias beside the pad
(tools/s92_contract.py THERMAL_VIA_FIELDS, written by tools/place_s8.py --apply-thermal-vias).
"""
import shutil
from pathlib import Path

from sexp import parse, dump, nodes, one

PRETTY = Path(__file__).resolve().parents[1] / 'hardware' / 'USBPOWER45.pretty'
# footprint key (circuit table): (pinned S7 land pattern with plated holes in the exposed pad, hole-free S9.2b copy)
NO_VIA_IN_PAD = {
    'PPAD8': ('TI_SO-PowerPAD-8_ThermalVias', 'TI_SO-PowerPAD-8_NoViaInPad'),
    'PWP20': ('HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm_Mask2.96x2.96mm_ThermalVias',
              'HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm_Mask2.96x2.96mm_NoViaInPad'),
    'DGN8': ('TPS7A16_DGN0008C', 'TPS7A16_DGN0008C_NoViaInPad'),
}
FP_S92 = {'KELVIN1206': 'R_Shunt_1206_KelvinSplit_RLM12', 'TP15': 'TestPoint_Pad_D1.5mm',
          **{key: new for key, (_, new) in NO_VIA_IN_PAD.items()}}
MASK_MARGIN = 0.025
RLM12_LAND = dict(pad_length_b=1.7, pad_width_a=1.8, inner_gap_L=1.6)       # TA-I RLM12, 2 <= R < 50 mOhm
RLM12_BODY = dict(L=(3.0, 3.2, 3.4), W=(1.4, 1.6, 1.8), C=(0.2, 0.5, 0.8), t=(0.4, 0.6, 0.8))   # mm (min, nom, max)
SPLIT_GAP = 0.20                       # force/sense copper gap = netclass clearance
SENSE_WIDTH, SENSE_LENGTH = 0.50, 1.30
# (pad, role, centre x, centre y, width, height) in the footprint frame (KiCad, y down); x < 0 is the pin-1 terminal.
_x_in = RLM12_LAND['inner_gap_L'] / 2                       # 0.8
_x_out = _x_in + RLM12_LAND['pad_length_b']                  # 2.5
_y_lo, _y_hi = -RLM12_LAND['pad_width_a'] / 2, RLM12_LAND['pad_width_a'] / 2     # -0.9, +0.9
_force_h = RLM12_LAND['pad_width_a'] - SENSE_WIDTH - SPLIT_GAP                   # 1.1
KELVIN_PADS = [
    ('1', 'force', -(_x_in + _x_out) / 2, _y_lo + _force_h / 2, RLM12_LAND['pad_length_b'], _force_h),
    ('2', 'sense', -(_x_in + SENSE_LENGTH / 2), _y_hi - SENSE_WIDTH / 2, SENSE_LENGTH, SENSE_WIDTH),
    ('3', 'sense', _x_in + SENSE_LENGTH / 2, _y_hi - SENSE_WIDTH / 2, SENSE_LENGTH, SENSE_WIDTH),
    ('4', 'force', (_x_in + _x_out) / 2, _y_lo + _force_h / 2, RLM12_LAND['pad_length_b'], _force_h),
]
COURTYARD = (_x_out + 0.25, _y_hi + 0.25)                    # half sizes: 2.75 x 1.15


def kelvin_footprint():
    cx, cy = COURTYARD
    text = f'''(footprint "{FP_S92['KELVIN1206']}" (version 20241229) (generator pcbnew) (layer "F.Cu")
      (descr "4-terminal Kelvin split land for a 2-terminal 1206 metal-alloy shunt (TA-I RLM12 2..50 mOhm land a 1.8 b 1.7 L 1.6): force pads 1/4, sense pads 2/3 from the inner land edge; S9.2 R109")
      (tags "shunt Kelvin 4-terminal split pad R109") (attr smd)
      (property "Reference" "REF**" (at 0 -1.75) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
      (property "Value" "0.018" (at 0 1.75) (layer "F.Fab") (effects (font (size 0.7 0.7) (thickness 0.1))))
      (fp_rect (start -1.6 -0.8) (end 1.6 0.8) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
      (fp_line (start -0.6 0.8) (end 0.6 0.8) (stroke (width 0.1) (type default)) (layer "F.Fab"))
      (fp_rect (start {-cx:g} {-cy:g}) (end {cx:g} {cy:g}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
    '''
    for n, _, x, y, w, h in KELVIN_PADS:
        text += (f'(pad "{n}" smd roundrect (at {x:g} {y:g}) (size {w:g} {h:g}) (layers "F.Cu" "F.Paste" "F.Mask") '
                 f'(solder_mask_margin {MASK_MARGIN}) (roundrect_rratio {min(.05 / w, .05 / h):.8f}))\n')
    return text + ')\n'


STOCK_TP = Path('/usr/share/kicad/footprints/TestPoint.pretty') / (FP_S92['TP15'] + '.kicad_mod')


def pad_layers(pad):
    return list(one(pad, 'layers')[1:])


def is_plated_hole(pad):
    return pad[2] in ('thru_hole', 'np_thru_hole')


def no_via_footprint(key, pretty=PRETTY):
    """Hole-free single-board copy of a pinned S7 exposed-pad land pattern (NO_VIA_IN_PAD[key]) as library text: the
    plated holes and the B.Cu-only exposed-pad copy are dropped, the name/value/description say so, all else is kept.
    One top-level item per line (the pinned TPS7A16 file is a single line)."""
    src, name = NO_VIA_IN_PAD[key]
    tree = parse((Path(pretty) / f'{src}.kicad_mod').read_text())
    drop = [c for c in nodes(tree, 'pad') if is_plated_hole(c) or pad_layers(c) == ['B.Cu']]
    assert drop and all(c[1] for c in drop), (key, 'expected numbered exposed-pad holes and a B.Cu pad copy')
    tree[:] = [c for c in tree if not any(c is d for d in drop)]
    tree[1] = name
    one(tree, 'descr')[1] += (f'; S9.2b single-board copy of {src}: no plated hole in any pad (owner decision, no via-in-pad), '
                              'no B.Cu pad copy; thermal vias are standard 0.3/0.6 mm board vias beside the pad')
    one(tree, 'tags')[1] += ' NoViaInPad'
    next(p for p in nodes(tree, 'property') if p[1] == 'Value')[2] = name
    head = [c for c in tree if not isinstance(c, list)]
    return '(' + ' '.join(dump(c) for c in head) + ''.join('\n\t' + dump(c) for c in tree if isinstance(c, list)) + '\n)\n'


def write(pretty):
    """Write/refresh the S9.2 footprints into the module library: the Kelvin land, the stock 1.5 mm test pad (copied
    unchanged) and the three hole-free S9.2b exposed-pad copies (their S7 sources are read, never written)."""
    pretty = Path(pretty)
    (pretty / (FP_S92['KELVIN1206'] + '.kicad_mod')).write_text(kelvin_footprint())
    dst = pretty / (FP_S92['TP15'] + '.kicad_mod')
    if not dst.exists() or dst.read_bytes() != STOCK_TP.read_bytes():
        shutil.copyfile(STOCK_TP, dst)
    for key, (_, name) in NO_VIA_IN_PAD.items():
        (pretty / f'{name}.kicad_mod').write_text(no_via_footprint(key, pretty))
    return pretty


def exposed_pad(key, pretty=PRETTY, copy=True):
    """Exposed-pad geometry of one NO_VIA_IN_PAD land pattern in its own frame (mm): the largest F.Cu copper rectangle
    of the exposed-pad number, the solder-mask window over it and the plated holes (pinned S7 source if copy=False)."""
    src, name = NO_VIA_IN_PAD[key]
    tree = parse((Path(pretty) / f'{name if copy else src}.kicad_mod').read_text())
    pads = nodes(tree, 'pad')
    holes = [p for p in pads if is_plated_hole(p)]
    num = max((p for p in pads if 'F.Cu' in pad_layers(p) and p[1]),
              key=lambda p: float(one(p, 'size')[1]) * float(one(p, 'size')[2]))[1]

    def rect(p):
        (x, y), (w, h) = map(float, one(p, 'at')[1:3]), map(float, one(p, 'size')[1:3])
        return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    copper = max((rect(p) for p in pads if p[1] == num and 'F.Cu' in pad_layers(p) and not is_plated_hole(p)),
                 key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    window = max((rect(p) for p in pads if p[1] in ('', num) and 'F.Mask' in pad_layers(p) and not is_plated_hole(p)
                  and rect(p)[0] >= copper[0] - 1e-9 and rect(p)[2] <= copper[2] + 1e-9),
                 key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    return {'pad': num, 'copper': copper, 'window': window,
            'holes': [(float(one(p, 'at')[1]), float(one(p, 'at')[2]), float(one(p, 'drill')[1])) for p in holes]}


def kelvin_geometry():
    """Pad edges and the electrode-overlap screen over the RLM12 dimension tolerances (used by the tests)."""
    out = {}
    for n, role, x, y, w, h in KELVIN_PADS:
        out[n] = dict(role=role, x=(round(x - w / 2, 4), round(x + w / 2, 4)), y=(round(y - h / 2, 4), round(y + h / 2, 4)))
    sense = out['3']
    worst_body_end = RLM12_BODY['L'][0] / 2                      # shortest body: electrode ends nearest the centre
    electrode_inner = worst_body_end - RLM12_BODY['C'][0]        # shortest electrode
    overlap_x = min(sense['x'][1], worst_body_end) - max(sense['x'][0], electrode_inner)
    overlap_y = min(sense['y'][1], RLM12_BODY['W'][0] / 2) - sense['y'][0]
    gaps = []
    for a in KELVIN_PADS:
        for b in KELVIN_PADS:
            if a[0] < b[0]:
                dx = abs(a[2] - b[2]) - (a[4] + b[4]) / 2
                dy = abs(a[3] - b[3]) - (a[5] + b[5]) / 2
                gaps.append(max(dx, dy) if (dx <= 0 or dy <= 0) else (dx * dx + dy * dy) ** .5)
    return dict(pads=out, min_copper_gap_mm=round(min(gaps), 4),
                sense_electrode_overlap_worst_mm=[round(overlap_x, 3), round(overlap_y, 3)],
                mask_web_mm=round(SPLIT_GAP - 2 * MASK_MARGIN, 3))
