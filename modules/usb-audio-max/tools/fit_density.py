"""Placement-density fit study: this carrier (10HP as placed, and the 8HP alternative) against the
routed carriers in the repository.

Run from modules/usb-audio-max with KiCad's Python (pcbnew 10):  python3 -B tools/fit_density.py

free area = board inset 1 mm (edge keep-out)
            - jack/pot pads + 2 mm (hand-solder keep-out; pad bounding boxes, rounded corners)
            - other THT pads + 0.5 mm, and the courtyards of THT parts mounted on B
density   = sum of SMD courtyard areas (placed and parked) / free area
Raster at 0.1 mm. It ignores routing, so it only ranks boards against each other; the routed
carriers set the scale (docs/research.md section 5).
"""
import json
from pathlib import Path

import numpy as np
import pcbnew

MODULE = Path(__file__).resolve().parents[1]
MODULES = MODULE.parent
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
RES = 0.1
HAND = ('Jack_', 'Potentiometer')
REFERENCES = ['acid/hardware/acid.kicad_pcb', 'hats/hardware/hats.kicad_pcb',
              'usb-audio/hardware/usb-audio.kicad_pcb', '16bit/hardware/16bit.kicad_pcb',
              '32bit/hardware/32bit.kicad_pcb']


def mm(v):
    return pcbnew.ToMM(v)


def box(b):
    return mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom())


def is_smd(fp):
    name = fp.GetFPID().GetLibItemName().wx_str()
    if name.startswith(HAND):
        return False
    return bool(fp.GetAttributes() & pcbnew.FP_SMD) or 'ThermalVias' in name or all(
        p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in fp.Pads())


def obstacles(board, outline, shift=None):
    """Hand-solder pad boxes, other THT pad boxes and B-side THT courtyards inside the outline.
    shift: {ref: (dx, dy)} moves a footprint's obstacles (what-if plans)."""
    x0, y0, x1, y1 = outline
    hand, other, back = [], [], []
    for fp in board.GetFootprints():
        if is_smd(fp):
            continue
        dx, dy = (shift or {}).get(fp.GetReference(), (0.0, 0.0))
        p = fp.GetPosition()
        if not (x0 <= mm(p.x) + dx <= x1 and y0 <= mm(p.y) + dy <= y1):
            continue
        name = fp.GetFPID().GetLibItemName().wx_str()
        for pad in fp.Pads():
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                l, t, r, b = box(pad.GetBoundingBox())
                (hand if name.startswith(HAND) else other).append((l + dx, t + dy, r + dx, b + dy))
        if fp.IsFlipped():
            poly = fp.GetCourtyard(pcbnew.B_CrtYd)
            if poly.OutlineCount():
                l, t, r, b = box(poly.BBox())
                back.append((l + dx, t + dy, r + dx, b + dy))
    return hand, other, back


def smd_area(board):
    total = 0.0
    for fp in board.GetFootprints():
        if is_smd(fp):
            for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                poly = fp.GetCourtyard(layer)
                if poly.OutlineCount():
                    total += poly.Area() / 1e12
                    break
    return total


def density(name, outline, hand, other, back, smd):
    x0, y0, x1, y1 = outline
    X, Y = np.meshgrid(np.arange(x0 + RES / 2, x1, RES), np.arange(y0 + RES / 2, y1, RES))
    usable = (X >= x0 + 1) & (X <= x1 - 1) & (Y >= y0 + 1) & (Y <= y1 - 1)

    def near(boxes, d):
        m = np.zeros_like(usable)
        for l, t, r, b in boxes:
            dx = np.maximum(np.maximum(l - X, 0), X - r)
            dy = np.maximum(np.maximum(t - Y, 0), Y - b)
            m |= np.hypot(dx, dy) <= d
        return m
    keep = near(hand, 2.0)
    blocked = keep | near(other, 0.5) | near(back, 0.0)
    a = RES * RES
    free = (usable & ~blocked).sum() * a
    area = (x1 - x0) * (y1 - y0)
    row = dict(board=name, size_mm=f'{x1 - x0:.1f} x {y1 - y0:.1f}', smd_courtyard_mm2=round(smd),
               hand_keepout_mm2=round((usable & keep).sum() * a), free_mm2=round(free),
               smd_of_board_pct=round(100 * smd / area), density_pct=round(100 * smd / free))
    print(row)
    return row


def outline_of(board):
    return box(board.GetBoardEdgesBoundingBox())


def main():
    rows = []
    for rel in REFERENCES:
        board = pcbnew.LoadBoard(str(MODULES / rel))
        o = outline_of(board)
        rows.append(density(rel.split('/')[0], o, *obstacles(board, o), smd_area(board)))
    board = pcbnew.LoadBoard(str(MODULE / 'hardware/usb-audio-max.kicad_pcb'))
    smd = smd_area(board)
    o = outline_of(board)
    rows.append(density('usb-audio-max 10HP (as placed)', o, *obstacles(board, o), smd))
    # 8HP what-if: modules/acid's 39.3 mm carrier and jack columns (X7.5 / 20.15 / 32.8), the strips
    # at the MCU board edges (X3.4 / 36.9), J1 under the third column, J4/SW1/SW2 unchanged.
    ox, oy = GEO['kicad_origin_mm']
    cols = dict(zip(GEO['jack_columns_X_mm'], (7.5, 20.15, 32.8)))
    shift = {j['ref']: (cols[j['XY'][0]] - j['XY'][0], 0.0) for j in GEO['jacks']}
    shift.update({'J2': (3.4 - 13.65, 0.0), 'J3': (36.9 - 36.85, 0.0), 'J1': (34.0 - 45.0, 0.0)})
    o8 = (ox + 0.5, o[1], ox + 39.8, o[3])
    rows.append(density('usb-audio-max 8HP (what-if)', o8, *obstacles(board, (o8[0], o8[1], o[2], o8[3]), shift), smd))
    out = MODULE / 'research/fit/density.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + '\n')


main()
