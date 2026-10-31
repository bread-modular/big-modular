#!/usr/bin/env python3
"""Stacked two-PCB FIT STUDY for usb-power-45w (study only, not accepted hardware).

Reads the accepted native carrier (read-only), partitions all 217 schematic refs onto a
BASE board (same outline/plane as the accepted carrier) and a parallel TOP board joined by
soldered 2.54 mm pins, places every part with a greedy nearest-feasible courtyard raster
(a placement helper, NOT a router: no tracks, vias or zones are created), and writes two
unrouted candidate boards plus a placement manifest.

Frame (same as docs/mechanical-preview.md): X across the module (panel 0..20), Y down the
panel, Z depth from the panel front. Native board map for BOTH boards:
native x = Y + 35.75, native y = 104.275 - Z. Both boards' F faces point to +X.

Run from the repository root:
  python3 -B modules/usb-power-45w/tools/stacked-fit-study/stacked_fit.py
  STACK_FIT_VARIANT=base-protection python3 -B ...   # labelled partition variant (see README)
"""
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pcbnew

MOD = Path(__file__).resolve().parents[2]
HW = MOD / 'hardware'
# 'literal': user's split (base = USB/20 V/main protection/LEDs/RESET, top = all the rest).
# 'base-protection': labelled VARIANT, the whole negative-rail protection sheet (U8/Q4/R48/R49
# Kelvin, U16/U17 optos) stays on the base; N12_RAW crosses as DC instead of -12V.
VARIANT = os.environ.get('STACK_FIT_VARIANT', 'literal')
assert VARIANT in ('literal', 'base-protection'), VARIANT
DOC = MOD / 'docs' / 'stacked-fit-study' / ('' if VARIANT == 'literal' else 'variant-base-protection')
sys.path.insert(0, str(MOD / 'tools'))
import mechanics45 as m  # noqa: E402

STOCK = Path('/usr/share/kicad/footprints')
G = 0.05                                  # raster pitch, mm
Y0, Y1, Z0, Z1 = 14.0, 114.5, 2.0, 42.0   # board frame extents
NY, NZ = int(round((Y1 - Y0) / G)), int(round((Z1 - Z0) / G))
CY_MARGIN = 0.01                          # courtyard raster margin (DRC uses the polygon)
EDGE_STROKE = 0.03                        # courtyard line half-width for the edge rule
EDGE = 1.0                                # courtyard/copper to Edge.Cuts
HS = 2.0                                  # SMD pad to hand-soldered THT/SW pad

# ---- stack (X) -------------------------------------------------------------------------
STACK = {
    'panel_X': [0.0, 20.0],
    'base_B': 2.5, 'base_F': 4.1, 'thickness': 1.6,
    'gap': 5.0,                       # SELECTED: set by 5.0 mm M3 F-F hex standoffs
    'top_B': 9.1, 'top_F': 10.7,
}
TOL = {   # worst-case linear contributions (assumed, see report)
    'bracket_web_X': 0.2, 'base_thickness': 0.16, 'standoff_length': 0.15,
    'top_thickness': 0.16, 'solder_standoff': 0.1, 'top_board_bow': 0.3,
}

TOP_SHEETS = {'/+12 V converter and output eFuse/', '/+5 V converter and output eFuse/',
              '/Negative converter - raw rail/', '/Negative rail protection and level shifting/'}
NEG_PROT = '/Negative rail protection and level shifting/'
if VARIANT == 'base-protection':
    TOP_SHEETS = TOP_SHEETS - {NEG_PROT}
TOP_EXTRA = {'C5'}   # post-U5 bulk can moves up with the VIN trunk; U5 local C2 stays base
# Floorplan adjustment 1 (balance): status pull-ups, RUN pull-downs, protected-rail bleeders and
# the NEG_OFF opto LED driver are support logic on nets that already cross (or replace V3V3 and
# NOT_RUN by the two NEG_OFF LED nets). No converter, eFuse-setting or Kelvin-sense part moves.
BASE_EXTRA = {'R35', 'R44', 'R62', 'R37', 'R46', 'R36', 'R45', 'R58', 'R59', 'R60', 'Q5'}

BASE_OUTLINE = m.carrier_outline(m.geometry())
TOP_REAR_Z = 28.0     # top board stops in front of J2/J3 boxes (Z30.23) and plugs (Z31.63)
TOP_SPLIT_Y = 51.5    # full depth only above J2 (box starts Y53.02)
NOTCH_Z = 20.5        # notches clear brackets, front nuts and the side-nut driver (Z11..19)
TOP_OUTLINE = [(14.0, 2.0), (16.5, 2.0), (16.5, NOTCH_Z), (27.5, NOTCH_Z), (27.5, 2.0),
               (101.0, 2.0), (101.0, NOTCH_Z), (112.0, NOTCH_Z), (112.0, 2.0), (114.5, 2.0),
               (114.5, TOP_REAR_Z), (TOP_SPLIT_Y, TOP_REAR_Z), (TOP_SPLIT_Y, 42.0), (14.0, 42.0)]

# ---- interconnect (added parts, counted separately) ------------------------------------
# XP: 2x8 power, XL: 2x4 logic. Same pin positions on both boards (straight pins).
XP_PIN1 = (55.0, 22.6)       # header courtyard 1.0 mm inside the top rear edge Z28
XP_NETS = ['GND', 'GND', 'VIN', 'VIN', 'VIN', 'VIN', 'GND', 'GND',
           '+12V', '+12V', '+5V', '+5V', 'GND', 'GND', '-12V', '-12V']
XL_PIN1 = (44.0, 12.0)
XL_NAME = 'PinHeader_2x04_P2.54mm_Vertical'
XL_NETS = ['GND', '/MAIN_OK', '/RUN', '/P12_OK', '/P5_OK', '/N12_STATUS',
           '/Negative rail protection and level shifting/NEG_OFF_LED',
           '/Negative rail protection and level shifting/NEG_OFF_K']
if VARIANT == 'base-protection':   # -12V is made on the base; raw DC rail crosses instead
    XP_NETS = ['N12_RAW' if n == '-12V' else n for n in XP_NETS]
    XL_NAME = 'PinHeader_2x03_P2.54mm_Vertical'
    XL_NETS = ['GND', '/MAIN_OK', '/RUN', '/P12_OK', '/P5_OK', 'V3V3']
    # top has room in this variant: the +12/+5 sheets' own status pull-ups, RUN pull-downs and
    # bleeders go back to their sheets (top); only V3V3 (pull-up supply) is added to the pins.
    BASE_EXTRA = BASE_EXTRA - {'R35', 'R44', 'R36', 'R45', 'R37', 'R46'}
STANDOFFS = [(20.5, 37.0), (46.9, 37.0), (96.0, 23.3), (82.0, 6.8)]
STANDOFF_CY_R = 3.6     # hex 5.5 AF (6.35 circ.) / ISO 7380 head 5.7 + margin
STANDOFF_CU_R = 3.6     # all-layer copper keep-out annulus r1.7..3.6 (NPTH pad itself outside)
NUT_DRIVER = [(22.0, 15.0), (106.5, 15.0)]   # base F keep-out for side nut + Ø8 driver
NUT_KEEP_R = 5.0
PIN_BUDGET_A = 1.5      # assumed per-pin design budget (0.64 mm square pin), not a rating

# ---- heights above own board face (max envelopes, assumed from package classes) ---------
HEIGHT = {
    'CP_Elec_6.3x7.7': 8.0, 'L_SLO1040H6R8MTT': 4.2, 'TO-252-2': 2.4, 'D_SMC': 2.62,
    'D_SMB': 2.62, 'D_SMA': 2.62, 'SOIC-14_3.9x8.7mm_P1.27mm': 1.75,
    'SO-4_4.4x3.6mm_P2.54mm': 2.6, 'SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm': 1.75,
    'MSOP-10_3x3mm_P0.5mm': 1.1, 'TI_SO-PowerPAD-8_ThermalVias': 1.7, 'SOT-23': 1.45,
    'SOT-23-5': 1.45, 'SOT-23-6': 1.45, 'SOT-583-8': 0.6, 'SOT-89-3': 1.6,
    'TPS7A16_DGN0008C': 1.1, 'C_0603_1608Metric': 0.95, 'R_0603_1608Metric': 0.55,
    'LED_0603_1608Metric': 0.8, 'C_1206_3216Metric': 1.8, 'R_1206_3216Metric': 0.7,
    'Fuse_1206_3216Metric': 1.4, 'TestPoint_Pad_D1.0mm': 0.05,
    'HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm_Mask2.96x2.96mm_ThermalVias': 1.2,
    'HRO-TYPE-C-31-M-12': 3.36, 'SW_TL3340AF160QG_HandSolder': 3.3,
    'LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm_Edge': 3.9,
    'IDC-Header_2x08_P2.54mm_Vertical': 9.25,
}
HAND_SOLDER = {'J1', 'J2', 'J3', 'D8', 'D16', 'D17', 'D18', 'SW1'}
FIXED_BASE = ['J1', 'D8', 'D16', 'D17', 'D18', 'SW1', 'J2', 'J3']
TOP_BIG_ANCHORS = {   # (Y, Z) targets; nearest feasible courtyard position is taken
    'L1': (30.5, 35.4), 'C34': (40.0, 26.0), 'L2': (38.0, 8.5), 'C35': (50.0, 8.5),
    'L3': (93.0, 9.0), 'C36': (91.0, 19.5), 'C5': (58.0, 17.0), 'Q4': (78.0, 21.0),
}
BIG_NETS = {'GND', 'VIN', 'V3V3', 'N12_RAW', '+12V', '+5V', '-12V', '/RUN', '/MAIN_OK'}


def nat(y, z):
    return pcbnew.VECTOR2I(pcbnew.FromMM(float(y) + 35.75), pcbnew.FromMM(104.275 - float(z)))


def to_yz(v):
    return pcbnew.ToMM(v.x) - 35.75, 104.275 - pcbnew.ToMM(v.y)


def side_of(fp):
    ref = fp.GetReference()
    if ref in BASE_EXTRA:
        return 'B'
    return 'T' if fp.GetSheetname() in TOP_SHEETS or ref in TOP_EXTRA else 'B'


# ---- raster helpers --------------------------------------------------------------------
def inside_mask(poly):
    ys = Y0 + (np.arange(NY) + 0.5) * G
    zs = Z0 + (np.arange(NZ) + 0.5) * G
    Yc, Zc = np.meshgrid(ys, zs, indexing='ij')
    ins = np.zeros_like(Yc, bool)
    for (ya, za), (yb, zb) in zip(poly, poly[1:] + poly[:1]):
        cond = (za > Zc) != (zb > Zc)
        with np.errstate(divide='ignore', invalid='ignore'):
            yint = ya + (Zc - za) * (yb - ya) / (zb - za)
        ins ^= cond & (Yc < yint)
    return ins


def window_any(mask, a0, a1, b0, b1):
    """any(mask[i+a0:i+a1+1, j+b0:j+b1+1]) for every (i, j); outside raster counts True."""
    pad = max(abs(a0), abs(a1), abs(b0), abs(b1)) + 2
    mp = np.pad(mask.astype(np.int32), pad, constant_values=1)
    s = np.zeros((mp.shape[0] + 1, mp.shape[1] + 1), np.int64)
    s[1:, 1:] = mp.cumsum(0).cumsum(1)
    i = np.arange(NY)[:, None] + pad
    j = np.arange(NZ)[None, :] + pad
    tot = (s[i + a1 + 1, j + b1 + 1] - s[i + a0, j + b1 + 1]
           - s[i + a1 + 1, j + b0] + s[i + a0, j + b0])
    return tot > 0


def cell_span(lo, hi, origin):
    return int(math.floor((lo - origin) / G)), int(math.floor((hi - origin) / G - 1e-9))


def mark_rect(mask, ylo, yhi, zlo, zhi):
    a0, a1 = cell_span(ylo, yhi, Y0)
    b0, b1 = cell_span(zlo, zhi, Z0)
    mask[max(a0, 0):max(min(a1 + 1, NY), 0), max(b0, 0):max(min(b1 + 1, NZ), 0)] = True


def fp_rects(fp):
    """Courtyard bbox and SMD-pad bbox in YZ relative to the footprint position."""
    py, pz = to_yz(fp.GetPosition())
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    def yzbox(b, grow=0.0):
        xa, xb = pcbnew.ToMM(b.GetLeft()), pcbnew.ToMM(b.GetRight())
        ya, yb = pcbnew.ToMM(b.GetTop()), pcbnew.ToMM(b.GetBottom())
        return [xa - 35.75 - py - grow, xb - 35.75 - py + grow,
                104.275 - yb - pz - grow, 104.275 - ya - pz + grow]
    court = yzbox(bb, CY_MARGIN)
    smd = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    padbox = None
    if smd:
        pb = smd[0].GetBoundingBox()
        for p in smd[1:]:
            pb.Merge(p.GetBoundingBox())
        padbox = yzbox(pb, 0.0)
    return court, padbox


IO = pcbnew.PCB_IO_KICAD_SEXPR()
_POOL = {}   # preloaded before any Board.Remove(): SWIG returns untyped objects afterwards


def _preload():
    for lib, name, n in (('Connector_PinHeader_2.54mm', 'PinHeader_2x08_P2.54mm_Vertical', 2),
                         ('Connector_PinHeader_2.54mm', XL_NAME, 2),
                         ('MountingHole', 'MountingHole_3.2mm_M3', 2 * len(STANDOFFS))):
        for _ in range(n):
            fp = IO.FootprintLoad(str(STOCK / f'{lib}.pretty'), name)
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            _POOL.setdefault((lib, name), []).append(fp)


def load_stock(lib, name):
    return _POOL[(lib, name)].pop()


def place_header(board, ref, name, pin1, nets):
    fp = load_stock('Connector_PinHeader_2.54mm', name)
    board.Add(fp)
    fp.SetReference(ref)
    fp.SetValue(f'{name} (study interconnect)')
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(nat(*pin1))
        p = {q.GetNumber(): to_yz(q.GetPosition()) for q in fp.Pads()}
        d2 = (p['2'][0] - p['1'][0], p['2'][1] - p['1'][1])
        d3 = (p['3'][0] - p['1'][0], p['3'][1] - p['1'][1])
        if abs(d2[0]) < 1e-3 and abs(d2[1] - 2.54) < 1e-3 and abs(d3[0] - 2.54) < 1e-3:
            break
    else:
        raise SystemExit(f'{ref}: no orientation gives pin2 +Z / pin3 +Y')
    fp.SetPosition(nat(*pin1))
    for q in fp.Pads():
        net = board.FindNet(nets[int(q.GetNumber()) - 1])
        assert net is not None, nets[int(q.GetNumber()) - 1]
        q.SetNet(net)
    return fp


def place_standoffs(board, prefix):
    out = []
    for k, (y, z) in enumerate(STANDOFFS, 1):
        fp = load_stock('MountingHole', 'MountingHole_3.2mm_M3')
        board.Add(fp)
        fp.SetReference(f'{prefix}{k}')
        fp.SetValue('M3 x 5.0 F-F hex standoff (study)')
        fp.SetPosition(nat(y, z))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        zone = pcbnew.ZONE(board)   # copper keep-out ring for a metal standoff/screw head
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowPads(True)
        zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowFootprints(False)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask())
        zone.SetZoneName(f'{prefix}{k}_copper_keepout_r{STANDOFF_CU_R}')
        o = zone.Outline()
        o.NewOutline()
        for a in range(32):
            t = 2 * math.pi * a / 32
            o.Append(nat(y + STANDOFF_CU_R * math.cos(t), z + STANDOFF_CU_R * math.sin(t)))
        o.NewHole()
        for a in range(32):
            t = -2 * math.pi * a / 32
            o.Append(nat(y + 1.7 * math.cos(t), z + 1.7 * math.sin(t)))
        board.Add(zone)
        out.append(fp)
    return out


def set_outline(board, poly):
    for d in list(board.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            board.Remove(d)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.05))
        s.SetStart(nat(*a))
        s.SetEnd(nat(*b))
        board.Add(s)


# ---- placement -------------------------------------------------------------------------
class Placer:
    def __init__(self, board, outline):
        self.board = board
        ins = inside_mask(outline)
        k = int(math.ceil((EDGE + EDGE_STROKE) / G))
        self.occ = window_any(~ins, -k, k, -k, k)   # cells closer than EDGE to the outline
        self.hs = np.zeros_like(self.occ)
        self.log = []

    def block_fp(self, fp):
        (a, b, c, d), _ = fp_rects(fp)
        py, pz = to_yz(fp.GetPosition())
        mark_rect(self.occ, py + a, py + b, pz + c, pz + d)
        if fp.GetReference() in HAND_SOLDER or fp.GetReference().startswith('X'):
            for p in fp.Pads():
                if fp.GetReference() == 'J1' and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    continue
                bb = p.GetBoundingBox()
                ya, yb = pcbnew.ToMM(bb.GetLeft()) - 35.75, pcbnew.ToMM(bb.GetRight()) - 35.75
                za, zb = 104.275 - pcbnew.ToMM(bb.GetBottom()), 104.275 - pcbnew.ToMM(bb.GetTop())
                mark_rect(self.hs, ya - HS - G, yb + HS + G, za - HS - G, zb + HS + G)

    def block_circle(self, y, z, r):
        mark_rect(self.occ, y - r, y + r, z - r, z + r)

    def place(self, fp, target, region=None, rots=(0, 90)):
        best = None
        pos0, rot0 = fp.GetPosition(), fp.GetOrientationDegrees()
        ys = Y0 + 0.05 + np.arange(NY) * G           # candidate position = cell + offset
        zs = Z0 + 0.025 + np.arange(NZ) * G          # native y on the 0.05 grid
        for rot in rots:
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(nat(50, 20))
            (a, b, c, d), pad = fp_rects(fp)
            a0, a1 = cell_span(0.05 + a, 0.05 + b, 0.0)
            b0, b1 = cell_span(0.025 + c, 0.025 + d, 0.0)
            bad = window_any(self.occ, a0, a1, b0, b1)
            if pad is not None:
                p0, p1 = cell_span(0.05 + pad[0], 0.05 + pad[1], 0.0)
                q0, q1 = cell_span(0.025 + pad[2], 0.025 + pad[3], 0.0)
                bad |= window_any(self.hs, p0, p1, q0, q1)
            ok = ~bad
            if region is not None:
                ok &= region
            if not ok.any():
                continue
            cyo, czo = (a + b) / 2, (c + d) / 2
            dist = (ys[:, None] + cyo - target[0]) ** 2 + (zs[None, :] + czo - target[1]) ** 2
            dist = np.where(ok, dist, np.inf)
            i, j = np.unravel_index(np.argmin(dist), dist.shape)
            if best is None or dist[i, j] < best[0]:
                best = (dist[i, j], rot, i, j, (a0, a1, b0, b1))
        if best is None:          # leave the part parked where it was (counted as unplaced)
            fp.SetOrientationDegrees(rot0)
            fp.SetPosition(pos0)
            return False
        _, rot, i, j, (a0, a1, b0, b1) = best
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(nat(round(ys[i], 3), round(zs[j], 3)))
        self.occ[max(i + a0, 0):i + a1 + 1, max(j + b0, 0):j + b1 + 1] = True
        return True


def region_mask(rects):
    r = np.zeros((NY, NZ), bool)
    for ya, yb, za, zb in rects:
        mark_rect(r, ya, yb, za, zb)
    return r


def neighbours(fps):
    nets = {}
    for f in fps:
        for p in f.Pads():
            n = p.GetNetname()
            if n and n not in BIG_NETS and not n.startswith('unconnected'):
                nets.setdefault(n, set()).add(f.GetReference())
    nb = {f.GetReference(): set() for f in fps}
    for rs in nets.values():
        if len(rs) <= 12:
            for r in rs:
                nb[r] |= rs - {r}
    return nb


def pads_on(fp, net):
    return any(p.GetNetname() == net for p in fp.Pads())


def run_group(pl, fps, seeds, anchor, region, priority=(), log=None, hot_ic=False):
    """Greedy: priority refs first, then BFS from seeds; target = placed-neighbour centroid."""
    byref = {f.GetReference(): f for f in fps}
    nb = neighbours(list(byref.values()) + [s for s in seeds if s.GetReference() not in byref])
    placed = {s.GetReference(): to_yz(s.GetPosition()) for s in seeds}
    order = [r for r in priority if r in byref]
    frontier = list(placed) + order
    seen = set(order) | set(placed)
    while frontier:
        r = frontier.pop(0)
        for q in sorted(nb.get(r, ())):
            if q in byref and q not in seen:
                seen.add(q)
                order.append(q)
                frontier.append(q)
    order += sorted(r for r in byref if r not in seen)
    spilled, failed = [], []
    for r in order:
        f = byref[r]
        pts = [placed[q] for q in nb.get(r, ()) if q in placed]
        tgt = tuple(np.mean(pts, axis=0)) if pts else anchor
        if hot_ic and r in priority and r != priority[0] and priority[0] in placed:
            tgt = placed[priority[0]]          # hot-loop caps hug the converter IC
        if not pl.place(f, tgt, region):
            if pl.place(f, tgt, None):
                spilled.append(r)
            else:
                failed.append(r)
                continue
        placed[r] = to_yz(f.GetPosition())
    if log is not None:
        log.append({'group_order': order, 'spilled_outside_region': spilled, 'unplaced': failed})
    return failed


def converter_priority(fps, ic, in_ret):
    """IC, input caps (VIN to its return), BOOT cap, inductor on SW."""
    by = {f.GetReference(): f for f in fps}
    icf = by[ic]
    sw = next(p.GetNetname() for p in icf.Pads() if 'SW' in p.GetNetname())
    bst = [p.GetNetname() for p in icf.Pads() if 'BST' in p.GetNetname() or 'BOOT' in p.GetNetname()]
    caps = sorted([r for r, f in by.items() if r.startswith('C') and pads_on(f, 'VIN') and pads_on(f, in_ret)],
                  key=lambda r: (by[r].GetFPIDAsString().find('0603') < 0, r))
    boot = [r for r, f in by.items() if r.startswith('C') and bst and pads_on(f, bst[0])]
    ind = [r for r, f in by.items() if r.startswith('L') and pads_on(f, sw)]
    return [ic] + caps + boot + ind


CONVERTERS = (('/+12 V converter and output eFuse/', 'U2', 'GND', 'L1', 'U6'),
              ('/+5 V converter and output eFuse/', 'U3', 'GND', 'L2', 'U7'),
              ('/Negative converter - raw rail/', 'U4', 'N12_RAW', 'L3', None))
TOP_REGIONS = {'U2': [(14, TOP_SPLIT_Y, NOTCH_Z, 42)], 'U3': [(27.5, 74, 2, NOTCH_Z + 2)],
               'U4': [(74, 114.5, 2, TOP_REAR_Z)]}
# Kelvin/MOSFET core first, then optos/clamps, then the rest of the sheet.
NEG_CORE = ['Q4', 'R48', 'R49', 'R89', 'U8', 'D19', 'R57', 'D20', 'R90', 'D14', 'C45',
            'C43', 'C44', 'R53', 'R52', 'R55', 'R54', 'R56', 'U16', 'U17']


def place_top_essentials_first(pl, fps, grp, hdrs, log):
    """VARIANT: inductors/cans, then every converter IC + input caps + BOOT and the output
    eFuse ICs (all three converters) BEFORE any filler, then each group's remaining parts."""
    failed, big = [], []
    anchors = {r: t for r, t in TOP_BIG_ANCHORS.items() if r in fps}
    for r, tgt in anchors.items():
        if pl.place(fps[r], tgt, None):
            big.append(fps[r])
        else:
            failed.append(r)
    log.append({'big_first': list(anchors), 'unplaced': list(failed)})
    done = {f.GetReference() for f in big} | set(failed)
    seeds = list(hdrs) + big
    ess = {}
    for sheet, ic, ret, ind, efuse in CONVERTERS:
        pri = [r for r in converter_priority(grp(sheet), ic, ret) if r not in done]
        if efuse:
            pri.append(efuse)
        ess[sheet] = pri
        sub = [fps[r] for r in pri]
        failed += run_group(pl, sub, seeds, TOP_BIG_ANCHORS[ind], region_mask(TOP_REGIONS[ic]),
                            pri, log, hot_ic=True)
        seeds += [f for f in sub if f.GetReference() not in failed]
        done |= set(pri)
    for sheet, ic, ret, ind, efuse in CONVERTERS:
        rest = [f for f in grp(sheet) if f.GetReference() not in done]
        failed += run_group(pl, rest, seeds, TOP_BIG_ANCHORS[ind], region_mask(TOP_REGIONS[ic]), (), log)
        seeds += [f for f in rest if f.GetReference() not in failed]
    log.append({'essentials': ess})
    return failed


def ics(fl):
    return sorted(f.GetReference() for f in fl if f.GetReference()[0] in 'UQ')   # ICs and transistors first


def place_base_protection_first(pl, fps, grp, hdrs, log):
    """VARIANT: the negative-protection core is reserved next to the N12_RAW pins and J2/J3
    BEFORE the base support logic and monitors fill in."""
    fixed = [f for r, f in fps.items() if r in FIXED_BASE]
    failed = []
    neg = grp(NEG_PROT)
    core = [f for f in neg if f.GetReference() in NEG_CORE]
    failed += run_group(pl, core, fixed + list(hdrs), (88.0, 20.0), region_mask([(74, 114.5, 2, 30)]),
                        NEG_CORE, log)
    seeds = fixed + list(hdrs) + [f for f in core if f.GetReference() not in failed]
    rest = [f for f in neg if f.GetReference() not in NEG_CORE]
    failed += run_group(pl, rest, seeds, (88.0, 20.0), region_mask([(66, 114.5, 2, 30)]), (), log)
    seeds += rest
    usb = [f for f in grp('/USB PD and main eFuse/') if f.GetReference() not in FIXED_BASE]
    failed += run_group(pl, usb, seeds, (40.0, 20.0), region_mask([(14, 60, 2, 42)]),
                        ['F1', 'D10', 'U5', 'C2', 'D1'] + ics(usb), log)
    ctl = [f for f in grp('/Always-on control - all-rail fault latch and RESET/') if f.GetReference() not in FIXED_BASE]
    outs = [f for f in grp('/Protected outputs - voltage monitors and panel LEDs/') if f.GetReference() not in FIXED_BASE]
    # every logic/monitor IC is reserved before any resistor/cap filler of either group
    failed += run_group(pl, ctl, seeds + usb, (65.0, 18.0), region_mask([(46, 90, 2, 29)]), ics(ctl + outs), log)
    failed += run_group(pl, outs, seeds + usb + ctl, (60.0, 15.0), None, ics(outs), log)
    negrefs = {f.GetReference() for f in neg}
    moved = [f for r, f in fps.items() if r in BASE_EXTRA and r not in negrefs]
    failed += run_group(pl, moved, seeds + usb + ctl + outs, (52.0, 18.0), None, (), log)
    return failed


def build(only):
    src = pcbnew.LoadBoard(str(HW / 'usb-power-45w.kicad_pcb'))
    parts = [f for f in src.GetFootprints() if f.GetReference()]
    partition = {f.GetReference(): side_of(f) for f in parts}
    sheets = {f.GetReference(): f.GetSheetname() for f in parts}
    out = {'partition': partition, 'sheets': sheets, 'log': {}}
    boards = {}
    for side, name in (('B', 'base'), ('T', 'top')):
        if name != only:
            continue
        b = pcbnew.LoadBoard(str(HW / 'usb-power-45w.kicad_pcb'))
        pre = 'XB' if side == 'B' else 'XT'
        xp = place_header(b, pre + '1', 'PinHeader_2x08_P2.54mm_Vertical', XP_PIN1, XP_NETS)
        xl = place_header(b, pre + '2', XL_NAME, XL_PIN1, XL_NETS)
        so = place_standoffs(b, 'MHB' if side == 'B' else 'MHT')
        pl = Placer(b, BASE_OUTLINE if side == 'B' else TOP_OUTLINE)
        for f in b.GetFootprints():
            if side == 'B' and (f.GetReference() in FIXED_BASE or not f.GetReference()):
                pl.block_fp(f)
        fps = {f.GetReference(): f for f in b.GetFootprints()
               if f.GetReference() in partition and partition[f.GetReference()] == side}
        for f in (xp, xl):
            pl.block_fp(f)
        for y, z in STANDOFFS:
            pl.block_circle(y, z, STANDOFF_CY_R)
        if side == 'B':
            for y, z in NUT_DRIVER:
                pl.block_circle(y, z, NUT_KEEP_R)
        log = []
        failed = []
        def grp(sheet_key, extra=()):
            return [f for r, f in fps.items() if sheets[r] == sheet_key or r in extra]
        if side == 'T' and VARIANT == 'base-protection':
            failed += place_top_essentials_first(pl, fps, grp, [xp, xl], log)
        elif side == 'B' and VARIANT == 'base-protection':
            failed += place_base_protection_first(pl, fps, grp, [xp, xl], log)
        elif side == 'T':
            # Floorplan adjustment 1 (the single allowed one): big parts first at explicit
            # anchors (inductors, cans, Q4), then each IC next to its inductor, then the rest.
            big = []
            for r, tgt in TOP_BIG_ANCHORS.items():
                if pl.place(fps[r], tgt, None):
                    big.append(fps[r])
                else:
                    failed.append(r)
            log.append({'big_first': list(TOP_BIG_ANCHORS), 'unplaced': list(failed)})
            bigrefs = {f.GetReference() for f in big} | set(failed)
            seeds = [xp, xl] + big
            def g2(k):
                return [f for f in grp(k) if f.GetReference() not in bigrefs]
            p12, p5 = g2('/+12 V converter and output eFuse/'), g2('/+5 V converter and output eFuse/')
            n12, npr = g2('/Negative converter - raw rail/'), g2('/Negative rail protection and level shifting/')
            failed += run_group(pl, p12, seeds, TOP_BIG_ANCHORS['L1'],
                                region_mask([(14, TOP_SPLIT_Y, NOTCH_Z, 42)]),
                                converter_priority(grp('/+12 V converter and output eFuse/'), 'U2', 'GND'), log, hot_ic=True)
            failed += run_group(pl, p5, seeds, TOP_BIG_ANCHORS['L2'], region_mask([(27.5, 66, 2, NOTCH_Z + 2)]),
                                converter_priority(grp('/+5 V converter and output eFuse/'), 'U3', 'GND'), log, hot_ic=True)
            failed += run_group(pl, n12, seeds, TOP_BIG_ANCHORS['L3'], region_mask([(74, 114.5, 2, TOP_REAR_Z)]),
                                converter_priority(grp('/Negative converter - raw rail/'), 'U4', 'N12_RAW'), log, hot_ic=True)
            failed += run_group(pl, npr, seeds, TOP_BIG_ANCHORS['Q4'], region_mask([(51.5, 101, 2, TOP_REAR_Z)]),
                                ['R48', 'R49', 'U8'], log)
        else:
            fixed = [f for r, f in fps.items() if r in FIXED_BASE]
            usb = grp('/USB PD and main eFuse/')
            usb = [f for f in usb if f.GetReference() not in FIXED_BASE]
            ctl = [f for f in grp('/Always-on control - all-rail fault latch and RESET/')
                   if f.GetReference() not in FIXED_BASE]
            outs = [f for f in grp('/Protected outputs - voltage monitors and panel LEDs/')
                    if f.GetReference() not in FIXED_BASE]
            failed += run_group(pl, usb, fixed + [xp], (40.0, 20.0), region_mask([(14, 60, 2, 42)]),
                                ['F1', 'D10', 'U5', 'C2', 'D1'], log)
            failed += run_group(pl, ctl, fixed + [xl], (75.0, 18.0), region_mask([(52, 101, 2, 29)]), (), log)
            failed += run_group(pl, outs, fixed + [xl, xp], (60.0, 15.0), None, (), log)
            moved = [f for r, f in fps.items() if r in BASE_EXTRA]
            failed += run_group(pl, moved, fixed + [xl, xp] + outs, (52.0, 18.0), None, (), log)
        # Removal last: after Board.Remove() this SWIG build returns untyped objects.
        doomed = [f for f in b.GetFootprints()
                  if (f.GetReference() in partition and partition[f.GetReference()] != side)
                  or (not f.GetReference() and side == 'T')]
        if side == 'T':
            set_outline(b, TOP_OUTLINE)
        for f in doomed:
            b.Remove(f)
        out['log'][name] = log
        out[f'{name}_unplaced'] = failed
        boards[name] = b
    return boards, out


def save_board(name, b):
    d = DOC / 'boards' / name
    d.mkdir(parents=True, exist_ok=True)
    stem = f'usb-power-45w-{name}'
    shutil.copy(HW / 'usb-power-45w.kicad_pro', d / f'{stem}.kicad_pro')
    if name == 'base':   # same J1/SW1 windows at the same positions; top has neither part
        shutil.copy(HW / 'usb-power-45w.kicad_dru', d / f'{stem}.kicad_dru')
    rel = os.path.relpath(HW, d)
    (d / 'fp-lib-table').write_text(
        '(fp_lib_table (version 7) (lib (name "USBPOWER45") (type "KiCad") '
        f'(uri "${{KIPRJMOD}}/{rel}/USBPOWER45.pretty") (options "") '
        '(descr "accepted module library, referenced read-only")))\n')
    pcbnew.SaveBoard(str(d / f'{stem}.kicad_pcb'), b)


if __name__ == '__main__':
    import subprocess
    if len(sys.argv) == 3 and sys.argv[1] == '--side':
        # One board per process: this SWIG build returns untyped proxies after Board.Remove().
        _preload()
        bs, o = build(sys.argv[2])
        save_board(sys.argv[2], bs[sys.argv[2]])
        Path(f'/tmp/stacked_fit_{sys.argv[2]}.json').write_text(json.dumps(o))
        os._exit(0)
    merged = {'log': {}}
    for name in ('base', 'top'):
        subprocess.run([sys.executable, '-B', __file__, '--side', name], check=True,
                       stderr=subprocess.DEVNULL)
        o = json.loads(Path(f'/tmp/stacked_fit_{name}.json').read_text())
        merged['partition'], merged['sheets'] = o['partition'], o['sheets']
        merged['log'].update(o['log'])
        merged[f'{name}_unplaced'] = o[f'{name}_unplaced']
    man = {'variant': VARIANT, 'XL_footprint': XL_NAME, 'stack': STACK, 'tolerances_assumed': TOL, 'top_outline_YZ': TOP_OUTLINE,
           'base_outline_YZ': BASE_OUTLINE, 'XP_pin1_YZ': XP_PIN1, 'XP_nets': XP_NETS,
           'XL_pin1_YZ': XL_PIN1, 'XL_nets': XL_NETS, 'standoffs_YZ': STANDOFFS,
           'standoff_courtyard_r': STANDOFF_CY_R, 'standoff_copper_keepout_r': STANDOFF_CU_R,
           'nut_driver_keepout': {'YZ': NUT_DRIVER, 'r': NUT_KEEP_R},
           'pin_budget_A': PIN_BUDGET_A, **merged}
    (DOC / 'placement-manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in merged.items() if k.endswith('unplaced')}),
          json.dumps({n: [g.get('spilled_outside_region') for g in merged['log'][n]] for n in merged['log']}))
