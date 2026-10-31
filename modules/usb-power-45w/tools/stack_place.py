#!/usr/bin/env python3
"""Explicit, reviewed placement moves on the canonical R2 boards (no automatic placement).

  python3 -B tools/stack_place.py apply <batch>      # apply MOVES[batch] in place (board backed up to /tmp)
  python3 -B tools/stack_place.py replay             # all batches in order (only after a fresh build_stack.py seed)
  python3 -B tools/stack_place.py show <board> REF...  # footprint origin, courtyard bbox, pad YZ + nets
  python3 -B tools/stack_place.py free <board> REF Y Z [rot] [--ignore REF,...]
      # helper for ONE part: nearest positions where its courtyard clears every other courtyard
      # (bbox; supports as circles), stays 1.0 mm (+stroke) inside the outline and, on the base,
      # keeps SMD pads 2.0 mm from hand-soldered pads. A human picks; nothing is written.

Positions are footprint origins in the stack YZ frame (Y down the panel, Z depth from the panel
front; native x = Y + 35.75, native y = 104.275 - Z). A move never drags copper: a footprint
with tracks attached to its pads is refused. Every batch is recorded with its reasons in
docs/stack-r2/placement-moves.json.
"""
import json
import shutil
import sys
import time
from pathlib import Path

import pcbnew

MOD = Path(__file__).resolve().parents[1]
REC = MOD / 'docs/stack-r2/placement-moves.json'

# batch -> board -> ref: (Y, Z, rot, reason)
MOVES = {
    'R2-refit-1-U4': {'top': {
        'C24': (95.0, 15.62, 0, 'U4 VIN-GND 10u: GND pad beside the L3 GND pad, VIN pad on the In2 VIN plane'),
        'C29': (95.0, 18.1, 0, 'N12_RAW-GND output cap column between U4 N12_RAW and the L3 GND pad'),
        'C30': (95.0, 20.6, 0, 'output cap column (was split around the study standoff MHT3)'),
        'C32': (95.0, 23.1, 0, 'output cap column'),
        'C31': (95.0, 25.6, 0, 'output cap column (was 20-25 mm from U4)'),
        'C33': (95.0, 28.1, 0, 'output cap column'),
        'D4': (89.0, 26.4, 180, 'N12_RAW clamp next to C36/U4 N12_RAW (was at Y108.8)'),
    }},
    'R2-refit-2-base-header': {'base': {
        'U17': (100.0, 33.0, 0, 'N_PGD level-shift opto out from under the 2x10 XB1 into the freed J3 area'),
        'R61': (96.5, 37.0, 0, 'U17 LED-side resistor, at U17 pin 1'),
        'R62': (103.0, 37.0, 0, 'N12_STATUS pull-up, at U17 pin 4'),
        'TEXT:1 / -12V / RED': (75.6, 29.16, 'left', 'J2 -12V marking now starts at pin 1 (Y76) and reads '
                                'toward the freed J3 side instead of over C48/U17; same Z, size and layer'),
    }},
    'R2-refit-3-converters': {'top': {
        # U4: whole cluster 0.97 mm deeper so BOOT C28 clears the support #4 tool courtyard
        'U4': (82.25, 17.0, 270, 'U4 0.97 deeper (support #4 tool courtyard); SW pin 8 to L3, FB pin 5 away'),
        'C28': (83.5, 12.35, 180, 'BOOT cap across U4 pins 7/8 (BOOT/SW)'),
        'C27': (82.4, 21.7, 0, 'U4 100n VIN-N12_RAW right at pins 3/1'),
        'C25': (82.7, 23.85, 0, 'U4 10u VIN-N12_RAW under C27'),
        'R13': (78.6, 18.95, 90, 'RT/SYNC at U4 pin 4'),
        # U2 (+12 V): SW/BST pins toward L1 (below), FB pin away from L1, VIN/GND caps at pins 3/4
        'U2': (31.0, 26.0, 180, 'pins 4/5 (GND/SW) face L1; FB pin 8 at the far corner'),
        'L1': (30.3, 34.4, 90, 'SW pad 3.4 mm straight below U2 pin 5'),
        'C10': (28.4, 26.5, 90, 'BOOT cap beside U2 pins 6/5'),
        'C8': (33.6, 26.5, 90, 'U2 100n VIN-GND beside pins 3/4'),
        'C7': (36.0, 25.7, 90, 'U2 10u VIN-GND next to C8'),
        'C6': (38.5, 25.7, 90, 'U2 second 10u VIN-GND'),
        'R9': (27.9, 24.6, 180, 'FB lower resistor at U2 pin 8, away from SW/L1'),
        'R8': (27.9, 22.9, 180, 'FB upper resistor (P12_RAW sense), stacked on R9'),
        'C9': (31.0, 23.3, 0, 'SS cap above U2 (pin 7 track between the pad rows)'),
        'C11': (38.1, 39.6, 0, 'P12_RAW 22u column at the L1 output pad'),
        'C12': (38.1, 37.2, 0, 'P12_RAW 22u column'),
        'C13': (38.1, 34.8, 0, 'P12_RAW 22u column'),
        'C14': (38.1, 32.4, 0, 'P12_RAW 22u column'),
        'C34': (46.0, 26.5, 90, 'P12_RAW bulk can between the U2 input caps and support #2'),
        # U3 (+5 V): rows along Y, SW/BST to L2 and the BOOT cap above, VIN/GND caps below, FB right
        'L2': (36.2, 9.4, 90, 'SW pad at the top, beside U3 pin 5 and BOOT C19'),
        'U3': (44.5, 7.0, 270, 'SW pin 5 toward L2, FB pin 8 at the far end'),
        'C19': (43.5, 4.4, 180, 'BOOT cap above U3 pins 6/5'),
        'C17': (43.5, 9.6, 180, 'U3 100n VIN-GND below pins 3/4'),
        'C15': (44.0, 12.0, 180, 'U3 10u VIN-GND'),
        'C16': (44.0, 14.4, 180, 'U3 second 10u back at U3 (was VIN trunk in the study)'),
        'R12': (47.5, 5.4, 0, 'FB lower resistor at U3 pin 8'),
        'R11': (47.5, 3.8, 0, 'FB upper resistor (P5_RAW sense)'),
        'C18': (47.5, 7.0, 0, 'SS cap, pin 7 track between the pad rows'),
        'R10': (47.6, 10.4, 90, 'RT resistor at U3 pin 1'),
    }},
    'R2-refit-4-repack': {   # one part at a time: target by function, nearest feasible spot from `free`
        'top': {
            'C5': (104.5, 25.2, 0, 'VIN bulk can to the free rear area (In2 VIN plane); frees the middle for U7'),
            'XT2': (66.0, 15.0, 90, 'logic header beside U7 (base XB2 follows)'),
            'C35': (55.0, 6.9, 0, 'P5_RAW bulk can turned flat above U7'),
            'U7': (53.6, 16.6, 90, '+5 eFuse between U3 output and the XT1 +5V pins'),
            'C20': (61.0, 6.0, 90, 'P5_RAW 22u beside C35'),
            'C21': (63.45, 6.0, 90, 'P5_RAW 22u'),
            'C23': (70.15, 6.0, 90, 'P5_RAW 22u'),
            'C22': (70.15, 10.75, 90, 'P5_RAW 22u'),
            'R42': (58.5, 11.8, 0, 'U7 OV divider'),
            'R41': (58.7, 13.6, 0, 'U7 OV divider'),
            'C40': (58.7, 15.2, 0, 'U7 dV/dt'),
            'R43': (58.7, 16.8, 0, 'U7 ILIM'),
            'D13': (63.8, 11.35, 0, '+5V output clamp at U7'),
            'C42': (42.95, 17.5, 0, 'P5_RAW 100n at the L2 output pad'),
            'C41': (51.0, 22.6, 90, '+5V 1u at U7 OUT pins 18-20'),
            'R9': (27.6, 24.1, 180, 'U2 FB lower at pin 8'),
            'R8': (27.6, 22.5, 180, 'U2 FB upper'),
            'U6': (45.5, 24.5, 90, '+12 eFuse between C34-old pocket and U7, shorter +12V run to XT1 pins 9-12'),
            'C38': (42.4, 29.6, 0, '+12V 1u at U6 OUT pins 18-20'),
            'R30': (43.0, 19.3, 0, 'U6 UV divider top at pin 7'),
            'R31': (46.2, 19.3, 0, 'U6 UV divider bottom'),
            'R32': (47.9, 16.1, 0, 'U6 OV divider top'),
            'R33': (48.45, 14.5, 0, 'U6 OV divider bottom'),
            'R38': (39.85, 18.2, 0, 'U6 OV series'),
            'R34': (48.6, 29.6, 0, 'U6 ILIM at pin 11'),
            'R36': (42.4, 31.2, 0, '+12V bleeder'),
            'C39': (40.05, 29.6, 90, 'P12_RAW 100n at the output column'),
            'D2': (19.6, 30.57, 0, 'P12_RAW clamp under C34'),
            'R19': (25.4, 26.45, 90, 'P12_RAW LED resistor'),
            'D5': (24.05, 30.3, 90, 'P12_RAW LED'),
            'R35': (45.5, 31.2, 0, 'P12_OK pull-up at pins 15/16'),
            'C34': (19.8, 25.15, 0, 'P12_RAW bulk can flat in the left pocket'),
            'C37': (48.45, 17.7, 0, 'U6 dV/dt at pin 10'),
            'R37': (45.5, 29.6, 0, 'U6 RUN pull-down at pin 13'),
            'D12': (62.05, 17.2, 90, '+12V clamp on the +12V run above XT1 pins 9-12'),
            'R14': (77.1, 11.05, 90, 'U4 FB lower, out of the support #4 tool courtyard'),
            'D7': (72.15, 11.05, 90, 'N12_RAW LED out of the support #4 tool courtyard'),
            'C26': (78.2, 15.0, 90, 'third U4 VIN-N12_RAW 10u left of U4 (XT1 blocks the spot under C25)'),
            'D3': (32.4, 18.3, 0, 'P5_RAW clamp right under the L2 output pad'),
            'R39': (49.95, 11.5, 0, 'U7 UV divider top'),
            'R40': (53.05, 11.3, 0, 'U7 UV divider bottom'),
            'D6': (39.9, 19.8, 0, 'P5_RAW LED under the L2 output pad'),
            'R20': (40.35, 21.4, 0, 'P5_RAW LED resistor next to D6'),
        },
        'base': {
            'U14': (29.5, 35.28, 0, '0.65 mm toward -Y with U13 (support #2 moved to Y46.2 for the top tool courtyard)'),
            'U13': (37.9, 36.08, 90, '0.65 mm toward -Y: clears the moved support #2'),
        },
    },
    'R2-refit-5-logic-header': {   # XL pair: the only spot free on both boards; U17 group re-seated
        'base': {
            'XB2': (95.25, 36.25, 0, 'logic header pair in the freed J3 volume, turned so U17 fits beside it'),
            'R61': (101.9, 30.7, 0, 'U17 LED-side resistor'),
            'R62': (105.0, 30.7, 0, 'N12_STATUS pull-up at U17'),
            'U17': (102.25, 36.0, 90, 'N_PGD opto beside XB2 (displaced by the logic header)'),
        },
        'top': {
            'XT2': (95.25, 36.25, 0, 'logic header pair (same pins as XB2)'),
        },
    },
    'R2-refit-6-hand-solder': {   # top header posts are soldered from top F: 2 mm to SMD copper
        'base': {
            'XB1': (55.0, 23.2, 90, 'power header pair 0.6 deeper (top outline now Z28.7, 1.53 mm from the J2 box)'),
            'XB2': (95.25, 36.95, 0, 'logic header pair 0.7 deeper: 2 mm from the C33 pads on the top'),
        },
        'top': {
            'XT1': (55.0, 23.2, 90, 'same pins as XB1: posts 2 mm from the U7 / D12 pads'),
            'XT2': (95.25, 36.95, 0, 'same pins as XB2'),
        },
    },
    'R2-refit-7-fixups': {
        'base': {
            'TP12': (53.0, 28.62, 0, 'test pad row between XB1 and J2, probe-reachable outside the top outline'),
            'TP13': (55.2, 28.62, 0, 'test pad row'),
            'TP10': (60.5, 28.62, 0, 'test pad row'),
            'TP15': (62.7, 28.62, 0, 'test pad row'),
            'TP14': (64.9, 28.62, 0, 'test pad row'),
        },
        'top': {
            'C25': (82.8, 23.85, 0, 'VIN pad 2 mm from the XT1 posts'),
            'D12': (62.05, 17.1, 90, 'pads 2 mm from the XT1 posts'),
        },
    },
    'R2-refit-8-U4-input': {'top': {
        'C26': (83.0, 26.3, 0, 'third U4 VIN-N12_RAW 10u stacked under C25 (top edge now Z28.7), '
                'out of the FB corner; VIN pad 2.1 mm from the XT1 posts'),
    }},
    'R2-refit-9-U4-EN': {'top': {
        'C27': (82.39, 21.9, 0, 'pad 1 under U4 pin 3; 0.2 mm lower so the EN_N escape via fits between '
                'the pin row and C27 (EN pin 2 sits between VIN and N12_RAW)'),
    }},
}


def yz(v):
    return round(pcbnew.ToMM(v.x) - 35.75, 3), round(104.275 - pcbnew.ToMM(v.y), 3)


def nat(y, z):
    return pcbnew.VECTOR2I(pcbnew.FromMM(y + 35.75), pcbnew.FromMM(104.275 - z))


def path(board):
    return MOD / 'hardware' / board / f'usb-power-45w-{board}.kicad_pcb'


def show(board, refs):
    b = pcbnew.LoadBoard(str(path(board)))
    for r in refs:
        f = b.FindFootprintByReference(r)
        bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
        lo, hi = yz(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), yz(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))
        pads = ' '.join(f"{p.GetNumber()}@{yz(p.GetPosition())}:{p.GetNetname().split('/')[-1][:12]}"
                        for p in f.Pads())
        print(r, yz(f.GetPosition()), f.GetOrientationDegrees(), 'cy', lo, hi, pads[:400])


def apply(batch):
    rec = json.loads(REC.read_text()) if REC.exists() else {}
    for board, moves in MOVES[batch].items():
        src = path(board)
        shutil.copy(src, f'/tmp/{src.stem}-{time.strftime("%H%M%S")}.kicad_pcb')
        b = pcbnew.LoadBoard(str(src))
        padset = {}
        for t in b.GetTracks():
            for f in b.GetFootprints():
                pass
        tracks = list(b.GetTracks())
        for ref, (y, z, rot, why) in moves.items():
            if ref.startswith('TEXT:'):
                t = next(d for d in b.GetDrawings() if d.GetClass() == 'PCB_TEXT' and d.GetText() == ref[5:])
                t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if rot == 'left' else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
                t.SetPosition(nat(y, z))
                continue
            f = b.FindFootprintByReference(ref)
            for p in f.Pads():
                for t in tracks:
                    if t.GetNetCode() == p.GetNetCode() and p.HitTest(t.GetStart()) or \
                            t.GetNetCode() == p.GetNetCode() and p.HitTest(t.GetEnd()):
                        raise SystemExit(f'{ref}: copper attached to pad {p.GetNumber()}, not moving it')
            f.SetOrientationDegrees(rot)
            f.SetPosition(nat(y, z))
        pcbnew.SaveBoard(str(src), b)
        rec.setdefault(batch, {})[board] = {r: {'YZ': [y, z], 'rot': rot, 'reason': why}
                                            for r, (y, z, rot, why) in moves.items()}
    REC.parent.mkdir(parents=True, exist_ok=True)
    REC.write_text(json.dumps(rec, indent=1) + '\n')


def free(board, ref, y, z, rot=None, ignore=(), raw=False, span=10):
    import numpy as np
    sys.path.insert(0, str(MOD / 'tools'))
    import stack_r2 as st
    b = pcbnew.LoadBoard(str(path(board)))
    f = b.FindFootprintByReference(ref)
    if rot is not None:
        f.SetOrientationDegrees(rot)
    f.SetPosition(nat(y, z))
    def box(fp, grow=0.0):
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)   # carrier holes: no courtyard
        (a, c), (bq, d) = yz(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), yz(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))
        return np.array([a - grow, bq + grow, c - grow, d + grow])
    me = box(f, 0.03) - np.array([y, y, z, z])
    hs = []
    hand = {'J1', 'J2', 'SW1', 'D8', 'D16', 'D17', 'D18'}
    smd = [p for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    padbox = None
    if smd:
        bb = smd[0].GetBoundingBox()
        for p in smd[1:]:
            bb.Merge(p.GetBoundingBox())
        (a, c), (bq, d) = yz(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), yz(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))
        padbox = np.array([a, bq, c, d]) - np.array([y, y, z, z])
    rects, circles = [], []
    for o in b.GetFootprints():
        r = o.GetReference()
        if o is f or r == ref or r in ignore:
            continue
        if o.GetFPID().GetLibItemName().wx_str().startswith('Stack_M3'):   # supports (no reference)
            circles.append((*yz(o.GetPosition()), st.STANDOFF_CY_R[board] + 0.03))
        else:
            rects.append(box(o))
        # hand-soldered THT on the SMD face: base J1 lugs/J2/SW1/LEDs; top XT1/XT2 posts (soldered from
        # top F). Base XB1/XB2 tails are soldered from base B (no parts there): not a source here.
        if (board == 'base' and r in hand) or (board == 'top' and r.startswith('XT')):
            for p in o.Pads():
                if r == 'J1' and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    continue
                bb = p.GetBoundingBox()
                (a, c), (bq, d) = yz(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetBottom())), yz(pcbnew.VECTOR2I(bb.GetRight(), bb.GetTop()))
                hs.append([a - 2.0, bq + 2.0, c - 2.0, d + 2.0])
    if board == 'base':          # side-nut + 8 mm driver keep-out on base F (tools/stack_r2.py)
        circles += [(cy, cz, st.NUT_KEEP_R + 0.03) for cy, cz in st.NUT_DRIVER]
    poly = st.TOP_OUTLINE if board == 'top' else None
    if poly is None:
        import mechanics45 as m
        poly = m.carrier_outline(m.geometry())
    g = np.arange(-span, span + 0.0001, 0.05)
    Y, Z = np.meshgrid(y + g, z + g, indexing='ij')
    Y, Z = Y.ravel(), Z.ravel()
    lo_y, hi_y, lo_z, hi_z = Y + me[0], Y + me[1], Z + me[2], Z + me[3]
    ok = np.ones_like(Y, bool)
    for rr in rects:
        ok &= ~((lo_y < rr[1]) & (rr[0] < hi_y) & (lo_z < rr[3]) & (rr[2] < hi_z))
    for cy, cz, cr in circles:
        dy = np.maximum(np.maximum(lo_y - cy, cy - hi_y), 0)
        dz = np.maximum(np.maximum(lo_z - cz, cz - hi_z), 0)
        ok &= np.hypot(dy, dz) >= cr
    if padbox is not None:
        for rr in hs:
            ok &= ~((Y + padbox[0] < rr[1]) & (rr[0] < Y + padbox[1]) & (Z + padbox[2] < rr[3]) & (rr[2] < Z + padbox[3]))
    def inside(py, pz):
        ins = np.zeros_like(py, bool)
        for (ya, za), (yb, zb) in zip(poly, poly[1:] + poly[:1]):
            cond = (za > pz) != (zb > pz)
            with np.errstate(divide='ignore', invalid='ignore'):
                yi = ya + (pz - za) * (yb - ya) / (zb - za)
            ins ^= cond & (py < yi)
        return ins
    for py in (lo_y, hi_y):
        for pz in (lo_z, hi_z):
            ok &= inside(py, pz)
    for (ya, za), (yb, zb) in zip(poly, poly[1:] + poly[:1]):   # axis-parallel outline segments
        sy0, sy1, sz0, sz1 = min(ya, yb), max(ya, yb), min(za, zb), max(za, zb)
        dy = np.maximum(np.maximum(lo_y - sy1, sy0 - hi_y), 0)
        dz = np.maximum(np.maximum(lo_z - sz1, sz0 - hi_z), 0)
        ok &= np.hypot(dy, dz) >= 1.0
    d = np.hypot(Y - y, Z - z)
    if raw:
        return Y, Z, ok, d
    idx = np.argsort(np.where(ok, d, np.inf))[:10]
    out = []
    for i in idx:
        if ok[i]:
            out.append((round(float(Y[i]), 2), round(float(Z[i]), 2), f.GetOrientationDegrees(), round(float(d[i]), 2)))
            print(f'{ref} rot {f.GetOrientationDegrees():.0f}: Y {Y[i]:.2f} Z {Z[i]:.2f}  (moved {d[i]:.2f})')
    return out


def free_pair(refs, y, z, rot, span=25):
    """Board-to-board header pair: positions feasible on BOTH boards (same pin 1, same rotation)."""
    import numpy as np
    Y, Z, ok1, d = free('base', refs[0], y, z, rot, raw=True, span=span)
    _, _, ok2, _ = free('top', refs[1], y, z, rot, raw=True, span=span)
    ok = ok1 & ok2
    idx = np.argsort(np.where(ok, d, np.inf))[:10]
    for i in idx:
        if ok[i]:
            print(f'{refs[0]}/{refs[1]} rot {rot}: pin 1 Y {Y[i]:.2f} Z {Z[i]:.2f} (moved {d[i]:.2f})')


if __name__ == '__main__':
    if sys.argv[1] == 'replay':
        for k in [k for k in MOVES if not k.startswith('_')]:
            apply(k)
    elif sys.argv[1] == 'pair':
        free_pair(sys.argv[2].split(','), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]))
    elif sys.argv[1] == 'free':
        a = sys.argv[2:]
        ign = ()
        if '--ignore' in a:
            k = a.index('--ignore')
            ign = tuple(a[k + 1].split(','))
            a = a[:k] + a[k + 2:]
        free(a[0], a[1], float(a[2]), float(a[3]), float(a[4]) if len(a) > 4 else None, ign)
    elif sys.argv[1] == 'show':
        show(sys.argv[2], sys.argv[3:])
    else:
        apply(sys.argv[2])
