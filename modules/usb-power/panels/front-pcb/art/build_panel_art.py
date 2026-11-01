#!/usr/bin/env python3
"""Generate copper-art candidates for the usb-power 2HP front panel PCB.

Reads the canonical panel (outline and holes untouched), removes every front
caption (BIG/MOD title, USB 9V, +5V POWER, RETRY), moves the V1 mark to
B.Silkscreen and draws unconnected F.Cu
artwork with matching F.Mask openings, so the art shows as bare (HASL silver or
ENIG gold) copper on the black mask. Candidates go to the module's ignored
research/panel-art/. The accepted design (F, "charged") is written to the
canonical panel with --apply; re-running is idempotent because earlier
footprint-free F.Cu/F.Mask art is stripped first.

    python3 -B panels/front-pcb/art/build_panel_art.py [--finish "HAL lead-free"]
    python3 -B panels/front-pcb/art/build_panel_art.py --only f-charged --apply
"""
import argparse
import math
import os
import pathlib
import re
import subprocess
import sys

import random

import pcbnew

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "usb-power-panel.kicad_pcb"
OUT = HERE.parents[2] / "research" / "panel-art"

CX = 54.9                      # panel centre line (board X 50.0 .. 59.8)
X0, X1 = 51.0, 58.8            # art keeps >= 1 mm from the panel edges
ZONES = {                      # free Y bands between holes, screw heads and labels
    "top": (37.0, 47.6),       # rail screw head (r 3.05) .. bracket head (r 3.55)
    "main": (83.0, 132.2),     # under the RETRY button hole .. lower bracket head
    "foot": (141.0, 151.6),    # lower bracket head .. lower rail screw head
}
LINE = 0.50                    # exposed copper line width
MASK = 0.05                    # mask opening grows this much per side


class Art:
    def __init__(self, board):
        self.b = board

    def _add(self, shape_t, layer, width, fill, setup):
        s = pcbnew.PCB_SHAPE(self.b, shape_t)
        s.SetLayer(layer)
        s.SetWidth(pcbnew.FromMM(width))
        s.SetFilled(fill)
        setup(s)
        self.b.Add(s)

    def seg(self, a, b, w=LINE):
        for layer, ww in ((pcbnew.F_Cu, w), (pcbnew.F_Mask, w + 2 * MASK)):
            self._add(pcbnew.SHAPE_T_SEGMENT, layer, ww, False, lambda s: (
                s.SetStart(pcbnew.VECTOR2I_MM(*a)), s.SetEnd(pcbnew.VECTOR2I_MM(*b))))

    def poly(self, pts, w=LINE):
        for a, b in zip(pts, pts[1:]):
            self.seg(a, b, w)

    def dot(self, c, d):
        for layer, dd in ((pcbnew.F_Cu, d), (pcbnew.F_Mask, d + 2 * MASK)):
            self._add(pcbnew.SHAPE_T_CIRCLE, layer, 0, True, lambda s: (
                s.SetCenter(pcbnew.VECTOR2I_MM(*c)),
                s.SetEnd(pcbnew.VECTOR2I_MM(c[0] + dd / 2, c[1]))))

    def ring(self, c, d, w=LINE):
        for layer, ww in ((pcbnew.F_Cu, w), (pcbnew.F_Mask, w + 2 * MASK)):
            self._add(pcbnew.SHAPE_T_CIRCLE, layer, ww, False, lambda s: (
                s.SetCenter(pcbnew.VECTOR2I_MM(*c)),
                s.SetEnd(pcbnew.VECTOR2I_MM(c[0] + d / 2, c[1]))))

    def fill(self, pts):
        """Solid polygon; a 0.2 mm stroke rounds the tips (no copper slivers)."""
        for layer, ww in ((pcbnew.F_Cu, 0.2), (pcbnew.F_Mask, 0.2 + 2 * MASK)):
            ps = pcbnew.SHAPE_POLY_SET()
            ps.NewOutline()
            for x, y in pts:
                ps.Append(pcbnew.FromMM(r2(x)), pcbnew.FromMM(r2(y)))
            self._add(pcbnew.SHAPE_T_POLY, layer, ww, True, lambda s: s.SetPolyShape(ps))

    def taper(self, pts, w0, w1):
        """Polyline whose width runs from w0 to w1 (round joints)."""
        n = len(pts) - 1
        for k, (a, b) in enumerate(zip(pts, pts[1:])):
            self.seg(a, b, round(w0 + (w1 - w0) * k / max(n - 1, 1), 2))


def r2(v):
    return round(v / 0.05) * 0.05


# ---- variant A: ripple settling into clean DC --------------------------------
def waves(art):
    """Three vertical lines start as a sine ripple and calm to straight DC."""
    y0, y1 = ZONES["main"]
    xs = (CX - 2.6, CX, CX + 2.6)
    for i, x in enumerate(xs):
        pts = []
        n = 240
        for k in range(n + 1):
            t = k / n
            y = y0 + t * (y1 - y0)
            amp = 1.0 * (1 - t) ** 1.6
            pts.append((x + amp * math.sin(2 * math.pi * (y - y0) / 7.0 + i * 2.1), y))
        art.poly(pts)
        art.dot((x, y1), 1.2)
    # top: one full sine cycle across the panel (the AC in); foot: flat DC bars
    t0, t1 = ZONES["top"]
    for j, yc in enumerate((t0 + 2.8, t0 + 7.6)):
        pts = [(X0 + 0.3 + k * (X1 - X0 - 0.6) / 120,
                yc + 1.6 * math.sin(2 * math.pi * k / 120 + j * math.pi)) for k in range(121)]
        art.poly(pts)
    f0, f1 = ZONES["foot"]
    ground(art, f0 + 3.0)


# ---- variant B: circuit traces ----------------------------------------------
def traces(art):
    """Four PCB-style traces with 45-degree jogs ending in round pads."""
    y0, y1 = ZONES["main"]
    lanes = (51.9, 53.9, 55.9, 57.9)
    plan = [  # (start lane, jog at y, to lane, end y)
        (0, 98.0, 1, 112.0), (1, 92.0, 0, 128.0),
        (2, 104.0, 3, 131.0), (3, 88.0, 2, 120.0)]
    for a, jog, b, end in plan:
        xa, xb = lanes[a], lanes[b]
        dy = abs(xb - xa)
        art.poly([(xa, y0), (xa, jog), (xb, jog + dy), (xb, end)])
        art.ring((xb, end + 0.0), 1.3, 0.4)
        art.dot((xa, y0), 0.9)
    t0, t1 = ZONES["top"]
    for k, x in enumerate((52.4, CX, 57.4)):
        art.ring((x, (t0 + t1) / 2 + (-2.2, 0, 2.2)[k]), 1.6, 0.4)
    art.poly([(52.4, (t0 + t1) / 2 - 2.2 + 0.8), (52.4, t1 - 0.5)])
    art.poly([(57.4, (t0 + t1) / 2 + 2.2 - 0.8), (57.4, t0 + 0.5)])
    art.poly([(CX, (t0 + t1) / 2 + 0.8), (CX, t1 - 0.5)])
    f0, f1 = ZONES["foot"]
    for x in (52.4, CX, 57.4):
        art.dot((x, (f0 + f1) / 2), 0.9)


# ---- variant C: halftone dot fade -------------------------------------------
def halftone(art):
    """Hex dot grid that grows from fine dust at the top to solid at the bottom."""
    y0, y1 = ZONES["main"]
    pitch = 1.3
    rows = int((y1 - y0) / (pitch * 0.866))
    for r in range(rows + 1):
        y = y0 + r * pitch * 0.866
        t = (y - y0) / (y1 - y0)
        d = 0.30 + 0.85 * t ** 1.3
        off = (pitch / 2) if r % 2 else 0.0
        x = X0 + 0.4 + off
        while x <= X1 - 0.4 + 1e-6:
            art.dot((r2(x), r2(y)), round(d, 2))
            x += pitch
    t0, t1 = ZONES["top"]
    for k in range(4):
        art.dot((CX, t0 + 1.2 + k * 2.6), 0.4 + 0.25 * k)
    f0, f1 = ZONES["foot"]
    art.ring((CX, (f0 + f1) / 2), 6.0, 0.5)
    art.dot((CX, (f0 + f1) / 2), 2.6)


# ---- shared lightning-bolt outline -----------------------------------------
BOLT = [(0.40, 0.00), (0.92, 0.00), (0.60, 0.38), (0.88, 0.38),
        (0.12, 1.00), (0.36, 0.55), (0.08, 0.55)]


def bolt(cx, cy, w, h):
    return [(cx + (u - 0.5) * w, cy + (v - 0.5) * h) for u, v in BOLT]


def inside(p, poly):
    x, y = p
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def edge_dist(p, poly):
    best = 1e9
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ax, ay = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (ax * ax + ay * ay)))
        best = min(best, math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay))
    return best


def ground(art, y):
    for k, w in enumerate((7.0, 5.0, 3.0)):
        art.seg((CX - w / 2, y + k * 2.2), (CX + w / 2, y + k * 2.2))


# ---- variant D: bolt emblem with speed streaks ------------------------------
def flash(art):
    """Bolt bursting out of a ring at the top, speed streaks trailing below."""
    t0, t1 = ZONES["top"]
    cy = (t0 + t1) / 2
    art.ring((CX, cy), 7.2, 0.5)
    art.fill(bolt(CX, cy, 4.6, 9.4))
    y0, y1 = ZONES["main"]
    for x, length, w in ((51.7, 20.0, 0.5), (53.3, 34.0, 0.7), (54.9, 48.0, 1.0),
                         (56.5, 30.0, 0.7), (58.1, 14.0, 0.5)):
        art.fill([(x - w / 2, y0), (x + w / 2, y0), (x + 0.1, y0 + length),
                  (x - 0.1, y0 + length)])
    f0, f1 = ZONES["foot"]
    art.fill(bolt(CX, (f0 + f1) / 2, 3.6, 7.4))


# ---- variant E: branching lightning strike to ground ------------------------
def strike(art):
    """A jagged stroke with forks runs the length of the panel into a ground."""
    rnd = random.Random(7)

    def channel(x, y, y_end, drift, steps):
        pts = [(x, y)]
        dy = (y_end - y) / steps
        for _ in range(steps):
            x += drift + 0.3 * (CX - x) + rnd.uniform(-1.3, 1.3)
            x = min(X1 - 0.6, max(X0 + 0.6, x))
            y += dy
            pts.append((r2(x), r2(y)))
        return pts

    t0, t1 = ZONES["top"]
    art.fill(bolt(CX, (t0 + t1) / 2, 5.2, 9.6))
    y0, y1 = ZONES["main"]
    main = channel(CX, y0, y1, 0.0, 22)
    art.taper(main, 1.0, 0.45)
    for k, drift, steps in ((4, -0.45, 6), (9, 0.5, 7), (15, -0.4, 5)):
        art.taper(channel(*main[k], main[k][1] + steps * 2.0, drift, steps), 0.45, 0.2)
    f0, f1 = ZONES["foot"]
    ground(art, f0 + 3.0)


# ---- variant F: halftone with a bolt knocked out ----------------------------
def charged(art):
    """Even dot field with a bolt left as black negative space."""
    y0, y1 = ZONES["main"]
    shape = bolt(CX, (y0 + y1) / 2, 6.6, 34.0)
    pitch = 1.25
    rows = int((y1 - y0) / (pitch * 0.866))
    for r in range(rows + 1):
        y = y0 + r * pitch * 0.866
        x = X0 + 0.4 + ((pitch / 2) if r % 2 else 0.0)
        while x <= X1 - 0.4 + 1e-6:
            p = (r2(x), r2(y))
            if not inside(p, shape) and edge_dist(p, shape) > 0.55:
                art.dot(p, 0.75)
            x += pitch
    for (z0, z1), grow in ((ZONES["top"], 1), (ZONES["foot"], -1)):
        rows = int((z1 - z0 - 0.8) / (pitch * 0.866))
        for r in range(rows + 1):
            y = z0 + 0.4 + r * pitch * 0.866
            t = r / rows if grow > 0 else 1 - r / rows
            x = X0 + 0.4 + ((pitch / 2) if r % 2 else 0.0)
            while x <= X1 - 0.4 + 1e-6:
                art.dot((r2(x), r2(y)), round(0.25 + 0.5 * t, 2))
                x += pitch


# ---- variant G: Jacob's ladder ----------------------------------------------
def ladder(art):
    """Two spreading electrodes with jagged arcs climbing between them."""
    rnd = random.Random(3)
    y0, y1 = ZONES["main"]
    lx = lambda y: 52.7 - 1.3 * (y1 - 0.5 - y) / (y1 - y0 - 1.0)
    rx = lambda y: 57.1 + 1.3 * (y1 - 0.5 - y) / (y1 - y0 - 1.0)
    art.seg((lx(y1 - 0.5), y1 - 0.5), (lx(y0 + 0.5), y0 + 0.5), 0.7)
    art.seg((rx(y1 - 0.5), y1 - 0.5), (rx(y0 + 0.5), y0 + 0.5), 0.7)
    for y in (88.0, 95.0, 102.0, 109.0, 116.0, 123.0):
        a, b = lx(y), rx(y)
        n = 7
        pts = [(a, y)] + [(r2(a + (b - a) * k / n), r2(y + rnd.uniform(-0.9, 0.9)))
                          for k in range(1, n)] + [(b, y)]
        art.poly(pts, 0.35)
    t0, t1 = ZONES["top"]
    art.fill(bolt(CX, (t0 + t1) / 2, 5.2, 9.6))
    f0, f1 = ZONES["foot"]
    ground(art, f0 + 3.0)


VARIANTS = {"a-waves": waves, "b-traces": traces, "c-halftone": halftone,
            "d-flash": flash, "e-strike": strike, "f-charged": charged,
            "g-ladder": ladder}
CAPTIONS = ("BIG", "MOD", "USB 9V", "+5V POWER", "RETRY")


def build(name, fn, finish, apply=False):
    b = pcbnew.LoadBoard(str(SRC))
    for d in list(b.GetDrawings()):
        if d.GetClass() == "PCB_SHAPE" and d.GetLayer() in (pcbnew.F_Cu, pcbnew.F_Mask):
            b.Remove(d)  # earlier art
        elif d.GetClass() == "PCB_TEXT" and d.GetText() in CAPTIONS:
            b.Remove(d)
        elif d.GetClass() == "PCB_TEXT" and d.GetText() == "V1":
            d.SetLayer(pcbnew.B_SilkS)
            d.SetMirrored(True)
    fn(Art(b))
    OUT.mkdir(parents=True, exist_ok=True)
    dst = SRC if apply else OUT / f"usb-power-panel-{name}.kicad_pcb"
    b.Save(str(dst))
    txt = dst.read_text()
    dst.write_text(re.sub(r'\(copper_finish "[^"]*"\)', f'(copper_finish "{finish}")', txt))
    if not apply:
        pro = (SRC.with_suffix(".kicad_pro")).read_text()
        dst.with_suffix(".kicad_pro").write_text(pro)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--finish", default="HAL lead-free")
    ap.add_argument("--only", choices=sorted(VARIANTS))
    ap.add_argument("--apply", action="store_true",
                    help="write --only's design to the canonical panel")
    a = ap.parse_args()
    if a.apply and not a.only:
        ap.error("--apply needs --only")
    if a.only:
        print(build(a.only, VARIANTS[a.only], a.finish, a.apply), flush=True)
        os._exit(0)  # skip pcbnew's teardown, which can segfault after Save

    # pcbnew cannot reliably load a second board per process: one run each
    for name in VARIANTS:
        subprocess.run([sys.executable, "-B", __file__, "--only", name,
                        "--finish", a.finish], check=True)


if __name__ == "__main__":
    main()
