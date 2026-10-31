#!/usr/bin/env python3
"""FINAL bounded manual placement pass on the base-protection VARIANT (study only).

Runs after `STACK_FIT_VARIANT=base-protection stacked_fit.py` (greedy helper output) and applies
an explicit, reviewed list of (Y, Z, rotation) moves to the two candidate boards in place. No
greedy repacking: every moved ref is listed in MOVES with its reason. Packages, nets, outlines,
standoffs and the user-fixed base parts (J1/SW1/LEDs/J2/J3) are not touched.

  STACK_FIT_VARIANT=base-protection python3 -B .../manual_pass.py            # apply MOVES
  STACK_FIT_VARIANT=base-protection python3 -B .../manual_pass.py --free top C27 81.6 21 [rot]
      # helper: list the nearest raster-feasible positions for ONE part (courtyard, 1 mm edge,
      # 2 mm hand-solder, standoff/nut-driver keep-outs), for a human to choose from
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('STACK_FIT_VARIANT', 'base-protection')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import pcbnew  # noqa: E402
import stacked_fit as sf  # noqa: E402

assert sf.VARIANT == 'base-protection', 'manual pass applies to the base-protection variant only'

# ref: (Y, Z, rot, reason). Positions are footprint origins in the study YZ frame.
MOVES = {
    'top': {
        # U4 group: turn U4 so SW (pin 8) faces the L3 SW pad, FB (pin 5) faces away to the
        # R14/R15 divider, VIN/N12_RAW (pins 3/1) face +Z where the input caps now sit.
        'U4': (82.25, 16.025, 270, 'SW toward L3 SW pad, FB toward R14/R15 away from L3, VIN side to +Z'),
        'C28': (83.5, 11.275, 180, 'BOOT cap across BOOT/SW pins, clear of the MHT4 keep-out'),
        'C27': (82.4, 20.725, 0, 'U4 HF input cap VIN-N12_RAW right at pins 3/1'),
        'C25': (82.7, 22.875, 0, 'U4 input cap VIN-N12_RAW stacked under C27'),
        'C26': (82.85, 25.475, 0, 'U4 input cap VIN-N12_RAW stacked under C25'),
        'C31': (102.0, 25.325, 0, 'N12_RAW output ceramic displaced by the U4 input caps'),
        'D4': (108.8, 24.225, 0, 'N12_RAW clamp displaced by the U4 input caps'),
        'R13': (78.6, 17.975, 90, 'RT/SYNC to N12_RAW at U4 pin 4'),
        # U3 FB network: R11/R12 leave the far side of L2 (next to its SW pad) for the slot right
        # of C15, on the FB-pin side of U3; C15 (10u, 2.96 mm) and C17 (100n) stay at U3 VIN.
        'C16': (68.9, 11.975, 90, 'second U3 10u input cap -> VIN trunk between C5 and U4 (frees FB slot)'),
        'R12': (49.3, 8.325, 0, 'U3 FB lower resistor (FB-GND), FB side of U3, >= 7 mm from L2'),
        'R11': (49.3, 5.975, 0, 'U3 FB upper resistor (P5_RAW-FB), stacked with R12'),
    },
    'base': {
        'Q10': (32.0, 23.025, 0, 'RUN-gated LED_RETURN FET: moved next to Q6-Q8 (LED_RETURN) and '
                'U5/U13/U14 (RUN); frees its old spot for D15'),
        'D15': (97.1, 14.975, 90, 'MON_N12 clamp: next to R82/R81 (MON_N12 divider) and U18'),
    },
}


def load(name):
    return pcbnew.LoadBoard(str(sf.DOC / 'boards' / name / f'usb-power-45w-{name}.kicad_pcb'))


def placer_for(board, name, skip=()):
    pl = sf.Placer(board, sf.BASE_OUTLINE if name == 'base' else sf.TOP_OUTLINE)
    poly = sf.BASE_OUTLINE if name == 'base' else sf.TOP_OUTLINE
    from check_fit import poly_contains
    for f in board.GetFootprints():
        r = f.GetReference()
        if r in skip:
            continue
        y, z = sf.to_yz(f.GetPosition())
        if r.startswith('MH') or (not r and name == 'base') or poly_contains(poly, y, z) \
                or r in ('J1', 'SW1', 'D8', 'D16', 'D17', 'D18'):
            if r.startswith('MH'):
                continue
            pl.block_fp(f)
    for y, z in sf.STANDOFFS:
        pl.block_circle(y, z, sf.STANDOFF_CY_R)
    if name == 'base':
        for y, z in sf.NUT_DRIVER:
            pl.block_circle(y, z, sf.NUT_KEEP_R)
    return pl


def free(name, ref, ty, tz, rots):
    b = load(name)
    fp = next(f for f in b.GetFootprints() if f.GetReference() == ref)
    pl = placer_for(b, name, skip={ref} | set(filter(None, os.environ.get('SKIP', '').split(','))))
    ys = sf.Y0 + 0.05 + np.arange(sf.NY) * sf.G
    zs = sf.Z0 + 0.025 + np.arange(sf.NZ) * sf.G
    out = []
    for rot in rots:
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(sf.nat(50, 20))
        (a, b_, c, d), pad = sf.fp_rects(fp)
        a0, a1 = sf.cell_span(0.05 + a, 0.05 + b_, 0.0)
        b0, b1 = sf.cell_span(0.025 + c, 0.025 + d, 0.0)
        bad = sf.window_any(pl.occ, a0, a1, b0, b1)
        if pad is not None:
            p0, p1 = sf.cell_span(0.05 + pad[0], 0.05 + pad[1], 0.0)
            q0, q1 = sf.cell_span(0.025 + pad[2], 0.025 + pad[3], 0.0)
            bad |= sf.window_any(pl.hs, p0, p1, q0, q1)
        dist = (ys[:, None] - ty) ** 2 + (zs[None, :] - tz) ** 2
        dist = np.where(~bad, dist, np.inf)
        for k in np.argsort(dist, axis=None)[:4000:400]:
            i, j = np.unravel_index(k, dist.shape)
            if np.isfinite(dist[i, j]):
                out.append((round(float(np.sqrt(dist[i, j])), 2), rot, round(float(ys[i]), 3), round(float(zs[j]), 3)))
    for o in sorted(out)[:12]:
        print(o)


def apply():
    log = {}
    for name, moves in MOVES.items():
        if not moves:
            continue
        b = load(name)
        fps = {f.GetReference(): f for f in b.GetFootprints()}
        for ref, (y, z, rot, why) in moves.items():
            assert ref in fps, f'{ref} not on {name}'
            assert ref not in sf.FIXED_BASE and not ref.startswith(('X', 'MH')), ref
            f = fps[ref]
            before = [*map(lambda v: round(v, 3), sf.to_yz(f.GetPosition())), f.GetOrientationDegrees()]
            f.SetOrientationDegrees(rot)
            f.SetPosition(sf.nat(y, z))
            log[ref] = {'board': name, 'from_YZ_rot': before, 'to_YZ_rot': [y, z, rot], 'reason': why}
        pcbnew.SaveBoard(str(sf.DOC / 'boards' / name / f'usb-power-45w-{name}.kicad_pcb'), b)
    man_p = sf.DOC / 'placement-manifest.json'
    man = json.loads(man_p.read_text())
    man['manual_pass'] = {'moves': log, 'note': 'final bounded manual pass; positions chosen by hand, '
                          'feasibility re-checked by check_fit.py (DRC + independent geometry)'}
    man_p.write_text(json.dumps(man, indent=1))
    print(json.dumps(log, indent=0))


if __name__ == '__main__':
    if len(sys.argv) >= 6 and sys.argv[1] == '--free':
        free(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]),
             [int(sys.argv[6])] if len(sys.argv) > 6 else [0, 90, 180, 270])
    else:
        apply()
