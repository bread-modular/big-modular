"""Narrow two-screw base: the full-height frame at half the width along the desk edge.
FreeCADCmd narrow_base.py -> print/two-screw-base/narrow-56/ and cad/two-screw-base/narrow-56/.
The 112 mm wide base is never overwritten. Same C section, top jaw reach, J1 pivot, thread and
desk range (5-52 mm); only the width (112 -> 56 mm) and the screw spacing (80 -> 32 mm) change.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_two_screw_base as b

DIR = 'narrow-56'
HALF = 28.0     # 56 mm along the edge, half the wide base
OFF = 16.0      # screws 32 mm apart: 4.1 mm of lip outside each tapped bore, 8.4 mm between the knobs
FAN = 14.0      # corner cut; keeps 6.3 mm of top jaw beside the J1 tooth ring
WALLS = 5


def main():
    stock = b.frame_blank()               # wide defaults, for the section comparison below
    b.HALF, b.OFF, b.FAN, b.NOTCH = HALF, OFF, FAN, 0
    out = b.OUT/DIR
    out.mkdir(exist_ok=True, parents=True)
    original = b.original_clamp()
    body = b.wide_base(original)
    screw = b.screwfit.screw(b.HEIGHT)

    # Geometry guards: the end of the lower lip outside each bore, the knob gap, and the
    # top jaw left around the J1 ring (4 mm in front of it, as on the wide base).
    bore = b.screwfit.R['r'] + b.screwfit.CLR
    lip_end = HALF - OFF - bore
    knob_gap = 2*OFF - 2*b.screwfit.KR
    rim = b.arm.R_OUT + b.arm.RING_END
    reach = b.arm.TOP_JAW_L
    ring_margin = min(reach - b.arm.J1_X - rim, HALF - rim,
                      (reach + HALF - FAN - b.arm.J1_X)/math.sqrt(2) - rim)
    assert lip_end >= 4 and knob_gap >= 8 and ring_margin >= 4, (lip_end, knob_gap, ring_margin)
    # Same C section as the wide base: the narrow frame is the wide one cut to +/-28 mm,
    # apart from the corner cut and the lower-lip notch it no longer has.
    mid = b.arm.box(-20, 20, -HALF+FAN+1, HALF-FAN-1, b.BOTTOM-2, b.arm.T+2)
    lip = b.arm.box(8, 31, -20, 20, b.BOTTOM-2, b.TOP+2)   # the wide base's notch region
    narrow_mid = b.frame_blank().cut(lip).common(mid)
    wide_mid = stock.cut(lip).common(mid)
    delta = abs(narrow_mid.cut(wide_mid).Volume) + abs(wide_mid.cut(narrow_mid).Volume)
    assert delta < 1e-5, ('C section differs from the wide base', delta)

    print('Narrow base built; checking desk contact, travel and fit', flush=True)
    supplied = b.check_hardware(body, screw, b.HEIGHT, (5, 8, 18, 25.5, 36.25, 52))
    cable = b.check_hardware(body, b.stock_screw(), b.screwfit.TIP, (8, 25.5, 52))
    upper, parts, at25 = b.check_upper(body, original, screw)
    b.CAD = b.CAD/DIR
    b.PREVIEW = b.ARM/'research'/'two-screw-base'/DIR/'render'
    b.save_assembly(parts, body, at25)
    b.arm.OUT = b.plates.PRINT = b.plates.OUT = out
    posed = {'base': b.arm.print_pose(body, (b.X, 90)), 'hand-screw': b.arm.print_pose(screw)}
    details = {n: b.arm.export_part(s, n) | b.arm.overhangs(s) for n, s in posed.items()}
    plate = b.plates.build_plate('print-this', [['base', 'hand-screw', 'hand-screw']],
                                 {n: b.plates.part_mesh(n) for n in posed})
    record = dict(status='CAD_PASS', physical_load_test=False, base_width_mm=2*HALF,
                  screw_spacing_mm=2*OFF, screw_from_edge_mm=b.AX, desk_range_mm=[5, 52],
                  screw_height_mm=b.HEIGHT, lip_outside_bore_mm=round(lip_end, 2),
                  knob_gap_mm=round(knob_gap, 2), top_jaw_around_j1_ring_mm=round(ring_margin, 2),
                  c_section_difference_mm3=round(delta, 8), volume_cm3=round(body.Volume/1000, 3),
                  supplied_screw_fit=supplied, cable_screw_fit=cable, interface=upper,
                  parts=details, plate=plate)
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print('NARROW_BASE_PASS', flush=True)


if __name__ == '__main__' or any(Path(a).resolve() == Path(__file__).resolve() for a in sys.argv[1:]):
    main()
