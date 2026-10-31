"""Small pcbnew helpers for explicit, reviewed edits of the usb-power-45w carrier (R1 work).

Edits go straight to hardware/usb-power-45w.kicad_pcb (root AGENTS.md routing policy) after a
/tmp backup. The project file is never rewritten (SaveBoard aSkipSettings). Nothing here places
or routes automatically: every op names its ref, pad, net, layer and coordinates.
"""
import shutil
import time
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
BOARD = MODULE / 'hardware/usb-power-45w.kicad_pcb'


def mm(v):
    return pcbnew.FromMM(v)


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def load(path=BOARD):
    return pcbnew.LoadBoard(str(path))


def backup(tag):
    dest = Path('/tmp') / f'usbp45-{tag}-{time.strftime("%H%M%S")}.kicad_pcb'
    shutil.copyfile(BOARD, dest)
    return dest


def save(board, path=BOARD):
    assert pcbnew.SaveBoard(str(path), board, True)


def fps(board):
    return {fp.GetReference(): fp for fp in board.GetFootprints() if fp.GetReference()}


def pad(board, ref, number, index=0):
    pads = [p for p in fps(board)[ref].Pads() if p.GetNumber() == str(number)]
    return pads[index]


def text(board, layer, s, x, y, size=0.8, rot=0, justify=None, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(V(size, size))
    t.SetTextThickness(mm(max(0.12, size * 0.15)))
    t.SetPosition(V(x, y))
    t.SetTextAngleDegrees(rot)
    if justify is not None:
        t.SetHorizJustify(justify)
    t.SetMirrored(mirror)
    board.Add(t)
    return t


def track(board, net, layer, pts, width):
    """One explicit polyline (list of (x, y) mm) on one copper layer."""
    n = board.FindNet(net)
    assert n is not None and n.GetNetCode() > 0, net
    out = []
    for a, b in zip(pts, pts[1:]):
        s = pcbnew.PCB_TRACK(board)
        s.SetStart(V(*a))
        s.SetEnd(V(*b))
        s.SetWidth(mm(width))
        s.SetLayer(layer)
        s.SetNet(n)
        board.Add(s)
        out.append(s)
    return out


def via(board, net, x, y, size=0.6, drill=0.3):
    n = board.FindNet(net)
    assert n is not None and n.GetNetCode() > 0, net
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y))
    v.SetWidth(mm(size))
    v.SetDrill(mm(drill))
    v.SetNet(n)
    board.Add(v)
    return v
