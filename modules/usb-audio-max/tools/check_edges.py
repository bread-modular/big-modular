"""Courtyard-to-edge (1.0 mm) and SMD-to-jack pad (2.0 mm) checks for the placed parts.

Run from modules/usb-audio-max with KiCad's Python: python3 -B tools/check_edges.py
As modules/usb-audio/tools/check_edges.py. Parked parts (outside the board outline) are skipped.
Prints the closest values per board and exits non-zero when a placed part breaks either rule.
"""
import json
import sys
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
OX, OY = GEO['kicad_origin_mm']
JACKS = {j['ref'] for j in GEO['jacks']}


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
    under = [r for r in rows if r[0] < 1.0]
    print(path.name, 'courtyard to edge, closest:', rows[:6], 'under 1 mm:', under)
    hand = [fp for fp in board.GetFootprints() if fp.GetReference() in JACKS]
    smd = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
           and x0 < pcbnew.ToMM(p.GetPosition().x) - OX < x1 and y0 < pcbnew.ToMM(p.GetPosition().y) - OY < y1]
    worst = []
    for pad in smd:
        for fp in hand:
            for hp in fp.Pads():
                d = pcbnew.ToMM(pad.GetEffectiveShape(pcbnew.F_Cu).GetClearance(hp.GetEffectiveShape(pcbnew.F_Cu)))
                worst.append((round(d, 2), pad.GetParentFootprint().GetReference(), fp.GetReference()))
    worst.sort()
    print('  SMD to jack pads, closest:', worst[:4] if hand else 'no jacks on this board')
    return not under and not [w for w in worst if w[0] < 2.0]


ok = check(MODULE / 'hardware/usb-audio-max.kicad_pcb', GEO['main_pcb']['outline_mm'])
ok &= check(MODULE / 'hardware/usb-audio-max-mcu.kicad_pcb', GEO['mcu_pcb']['outline_mm'])
sys.exit(0 if ok else 1)
