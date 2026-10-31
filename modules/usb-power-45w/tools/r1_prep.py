"""R1 step 0 (explicit, one-off): library repairs synced to the board + J2/J3 -12V marking.

- U8 LM5067 VSSOP-10: TI DGS0010A land pattern example (4221984/A): 10 x 1.45 x 0.30, pitch 0.5,
  row span 4.4, R0.05 (was 1.5 x 0.35 at span 4.2 -> 0.15 mm pad gap).
- U4 LMR38020 PowerPAD thermal vias: pad_prop_heatsink, as the HTSSOP ThermalVias footprints.
- J2/J3: old usb-power J7 marking style. Horizontal "1 / -12V / RED" outside the box body (front
  side, visible with the plug mated; ribbon leaves to the rear) replaces the rotated "-12V" text
  that sat under the box body; B silk per-pin labels N12 GND GND GND P12 P5 NC NC as old J7.
Pad numbers, nets, positions of every other pad and the header placement are unchanged.
"""
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcb45 as P  # noqa: E402

LABELS = ['N12', 'GND', 'GND', 'GND', 'P12', 'P5', 'NC', 'NC']


def run():
    print('backup', P.backup('r1-prep'))
    b = P.load()
    f = P.fps(b)
    for p in f['U8'].Pads():
        loc = f['U8'].GetPosition()
        rel = p.GetFPRelativePosition()
        x = 2.2 if rel.x > 0 else -2.2
        p.SetFPRelativePosition(pcbnew.VECTOR2I(P.mm(x), rel.y))
        p.SetSize(pcbnew.PADSTACK.ALL_LAYERS, P.V(1.45, 0.30))
        p.SetRoundRectRadiusRatio(pcbnew.PADSTACK.ALL_LAYERS, 0.05 / 0.30)
    for p in f['U4'].Pads():
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            p.SetProperty(pcbnew.PAD_PROP_HEATSINK)
    for d in list(b.GetDrawings()):
        if isinstance(d, pcbnew.PCB_TEXT) and d.GetText() == '-12V' and d.GetLayer() == pcbnew.F_SilkS:
            b.Remove(d)
    for ref in ('J2', 'J3'):
        p1 = P.pad(b, ref, 1).GetPosition()
        p2 = P.pad(b, ref, 2).GetPosition()
        x1, y1, y2 = (pcbnew.ToMM(v) for v in (p1.x, p1.y, p2.y))
        P.text(b, pcbnew.F_SilkS, '1 / -12V / RED', x1 + 5.25, y2 + 4.3, justify=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
        for i, lab in enumerate(LABELS):
            P.text(b, pcbnew.B_SilkS, lab, x1 - 2.54 * i, y2 + 2.16, mirror=True)
    P.save(b)


if __name__ == '__main__':
    run()
