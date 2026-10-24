"""Courtyard-to-edge (1.0 mm) and SMD-to-pot/jack pad (2.0 mm) checks for the placed parts.

Run from modules/usb-audio with KiCad's Python: python3 -B tools/check_edges.py
Parked parts (outside the board outline) are skipped. Prints the closest values per board.
"""
import json
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
OX, OY = GEO['kicad_origin_mm']


def check(path, box):
    board = pcbnew.LoadBoard(str(path))
    x0, y0, x1, y1 = box
    rows = []
    for fp in board.GetFootprints():
        bb = None
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            poly = fp.GetCourtyard(layer)
            if poly.OutlineCount():
                bb = poly.BBox()
        if bb is None:
            continue
        l, r = pcbnew.ToMM(bb.GetLeft()) - OX - 0.025, pcbnew.ToMM(bb.GetRight()) - OX + 0.025
        t, b = pcbnew.ToMM(bb.GetTop()) - OY - 0.025, pcbnew.ToMM(bb.GetBottom()) - OY + 0.025
        if l > x1 or r < x0 or t > y1 or b < y0:
            continue  # parked
        rows.append((round(min(l - x0, x1 - r, t - y0, y1 - b), 3), fp.GetReference()))
    rows.sort()
    print(path.name, 'courtyard to edge, closest:', rows[:6], 'under 1 mm:', [r for r in rows if r[0] < 1.0])
    hand = [fp for fp in board.GetFootprints() if fp.GetReference()[:2] in ('J2', 'J3', 'J4', 'J5', 'RV')]
    smd = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
           and x0 < pcbnew.ToMM(p.GetPosition().x) - OX < x1]
    worst = []
    for pad in smd:
        for fp in hand:
            for hp in fp.Pads():
                d = pcbnew.ToMM(pad.GetEffectiveShape(pcbnew.F_Cu).GetClearance(hp.GetEffectiveShape(pcbnew.F_Cu)))
                worst.append((round(d, 2), pad.GetParentFootprint().GetReference(), fp.GetReference()))
    worst.sort()
    print('  SMD to pot/jack pads, closest:', worst[:4])


check(MODULE / 'hardware/usb-audio.kicad_pcb', GEO['main_pcb']['outline_mm'])
check(MODULE / 'hardware/usb-audio-mcu.kicad_pcb', GEO['mcu_pcb']['outline_mm'])
