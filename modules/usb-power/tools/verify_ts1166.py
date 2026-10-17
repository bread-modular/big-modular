#!/usr/bin/env python3
"""Validate the requested switch's HOLE PATTERN; explicitly report assembly blockers.

Uses native KiCad only for footprint inspection (shared inspect rejects retained
USB model dependencies). Does not install SW1, alter a panel, or claim 3D fit.
User drawing row spacing = 2.50mm; public same-name PDF = 2.15mm, NOT equivalent.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
NAME = 'SW_TS1166VW_RightAngle_THT_P4.50_P7.00_Row2.50mm'
FOOTPRINT = ROOT/'hardware/BigModular.pretty'/(NAME+'.kicad_mod')


def fit_report(g, h=4.3):
    """H follows the push axis; it cannot solve PCB-normal body interference."""
    assert h > 0
    projection = 7.1  # dimensioned seating plane -> housing extremity, +/-0.1
    front_copper_x = g['carrier_X_mm'][1]
    available = g['panel_mm'][0] - front_copper_x
    rear = g['panel_mm'][2]
    target_recess_behind_panel_rear = .45  # design intent, NOT measured part datum
    target_tip = rear + target_recess_behind_panel_rear
    return {
        'H_choice_mm': h,
        'H_choice_status': 'PROVISIONAL short stem for recessed tool-operated reset; not purchase/fit release',
        'H_direction': 'parallel to main PCB / along actuator, NOT normal to PCB',
        'normal_projection_mm': projection,
        'normal_projection_tolerance_mm': .1,
        'current_component_face_X_mm': front_copper_x,
        'available_normal_space_mm': round(available, 5),
        'body_extreme_X_mm': round(front_copper_x + projection, 5),
        'nominal_overhang_mm': round(max(0, projection - available), 5),
        'fits_current_stack': projection + .1 <= available,
        'target_actuator_tip_Z_mm': round(target_tip,5),
        'target_H_reference_Z_mm': round(target_tip + h, 5),
        'H_reference_warning': 'Target only: H-reference to hole-row datum is not sufficiently specified in the supplied drawing. No footprint placement derived from this target.',
        'release_blockers': [
            '7.1mm seating projection exceeds the present 5.1mm lateral allowance',
            'User PCB pattern says row2.50; external TS-1166VW PDF says row2.15',
            'Actual sample must establish H-reference/actuator axis relative to holes and case-tab continuity',
            'Panel opening/board/bracket arrangement must be reworked before substitution; no automatic width change',
        ],
    }


def verify(footprint=FOOTPRINT):
    footprint = Path(footprint)
    fp = pcb.FootprintLoad(str(footprint.parent), footprint.stem)
    assert fp is not None, 'native footprint load failed'
    expected = {'1': (-2.25, 0, 1, 2), '2': (2.25, 0, 1, 2),
                'MP1': (-3.5, -2.5, 1.5, 2.6), 'MP2': (3.5, -2.5, 1.5, 2.6)}
    pads = list(fp.Pads())
    assert len(pads) == 4 and {p.GetNumber() for p in pads} == set(expected)
    record = {}
    for pad in pads:
        actual = tuple(round(pcb.ToMM(v), 5) for v in
                       [pad.GetPosition().x, pad.GetPosition().y,
                        pad.GetDrillSize().x, pad.GetSize().x])
        assert actual == expected[pad.GetNumber()], ('hole pattern mismatch', pad.GetNumber(), actual)
        assert pad.GetAttribute() == pcb.PAD_ATTRIB_PTH, 'all four legs need plated solder holes'
        assert pad.GetShape() == pcb.PAD_SHAPE_CIRCLE
        assert pad.GetDrillSize().x == pad.GetDrillSize().y
        assert pad.GetSize().x == pad.GetSize().y
        assert pad.IsOnLayer(pcb.F_Cu) and pad.IsOnLayer(pcb.B_Cu)
        assert not pad.IsOnLayer(pcb.F_Paste) and not pad.IsOnLayer(pcb.B_Paste)
        assert not pad.GetNetname(), 'library pattern must not tie support legs to circuit ground'
        record[pad.GetNumber()] = {'XY_mm': list(actual[:2]), 'drill_mm': actual[2],
                                  'copper_diameter_mm': actual[3],
                                  'annular_ring_mm': round((actual[3]-actual[2])/2, 3)}
    # Independent analytic solder-land clearance, not a substitute for native DRC.
    minimum_gap = min(math.dist(expected[a][:2], expected[b][:2]) -
                      (expected[a][3]+expected[b][3])/2
                      for i,a in enumerate(expected) for b in list(expected)[i+1:])
    assert minimum_gap > .45
    assert not list(fp.Models()), 'no borrowed 3D model for a different switch'
    assert not any(d.GetLayer() == pcb.Edge_Cuts for d in fp.GraphicalItems())
    g = json.loads((ROOT/'docs/assembly-geometry.json').read_text())
    b = pcb.LoadBoard(str(ROOT/'hardware/usb-power.kicad_pcb'))
    sw = next(f for f in b.GetFootprints() if f.GetReference() == 'SW1')
    return {
        'status': 'RETIRED THT ALTERNATIVE / HOLE PATTERN CHECKED / DOES NOT FIT CURRENT STACK',
        'footprint': footprint.name, 'footprint_sha256': hashlib.sha256(footprint.read_bytes()).hexdigest(),
        'pads': record, 'minimum_land_clearance_mm': round(minimum_gap, 5),
        'signal_numbering': '1/2 are our left/right convention; seller schematic does not assign useful pin numbers',
        'support_numbering': 'MP1/MP2 isolated solder pads; neither is a reset contact or assumed ground',
        'source_row_spacing_mm': 2.5,
        'external_same_name_PDF_row_spacing_mm': 2.15,
        'courtyard_status': 'Provisional reservation only; no qualified body outline or 3D model',
        'fit': fit_report(g),
        'installed_on_active_board': sw.GetFPID().GetLibItemName() == NAME,
        'active_SW1_retained': str(sw.GetFPID().GetLibItemName()),
        'routing_performed': False, 'fabrication_ready': False,
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--footprint', type=Path, default=FOOTPRINT)
    p.add_argument('--output', type=Path, help='NEW JSON file; never overwrite existing evidence')
    args = p.parse_args()
    report = verify(args.footprint)
    text = json.dumps(report, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as f:
            f.write(text)
    print(text, end='')
