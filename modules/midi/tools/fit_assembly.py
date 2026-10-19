"""Nominal panel-over-carrier fit check (FreeCAD, headless). Use tools/fit_assembly.sh.

Inputs (written by the wrapper with kicad-cli, user origin = panel origin):
  research/<version>/fit/board.step   carrier body only
  research/<version>/fit/<REF>.step   one STEP per front-side THT part (J1..J9, D1..D8)
  research/<version>/fit/back.step    all back-side parts
Panels: the printed panel STEP (panels/front-cad) and an FR4 plate built from the
native panel PCB holes at panel_pcb_thickness_mm.

KiCad STEP frame: X = panel X, Y = -panel Y, board Z0..1.6 with F.Cu at Z1.6.
The panel rear face sits stack_Z_mm.panel_rear_seat above F.Cu.
Writes the version's fit-report.json (docs/fit/ for V1, docs/v2/fit/ for V2) and
research/<version>/fit/midi-fit-assembly.step. MIDI_VERSION (v1|v2) comes from the wrapper.
Nominal model geometry only: the jack models are 'Untested' upstream.
"""
import json
import math
import os
import sys
from pathlib import Path

import FreeCAD as App
import Part

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from sexp import nodes, one, parse  # noqa: E402

VERSION = os.environ['MIDI_VERSION']
assert VERSION in ('v1', 'v2'), VERSION
FIT = MODULE / 'research' / VERSION / 'fit'
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
BOARD_T = GEO['main_pcb']['thickness_mm']
SEAT = GEO['stack_Z_mm']['panel_rear_seat']
PW, PH = GEO['panel_mm']


def read(path):
    s = Part.Shape()
    s.read(str(path))
    return s


def fr4_panel():
    """FR4 plate from the native panel PCB NPTH holes, in the KiCad STEP frame."""
    tree = parse((MODULE / 'panels/front-pcb/midi-panel.kicad_pcb').read_text())
    ox, oy = GEO['kicad_origin_mm']
    t = GEO['panel_pcb_thickness_mm']
    plate = Part.makeBox(PW, PH, t, App.Vector(0, -PH, 0))
    cuts = []
    for fp in nodes(tree, 'footprint'):
        at = one(fp, 'at')
        x, y = float(at[1]) - ox, float(at[2]) - oy
        for pad in nodes(fp, 'pad'):
            d = float(one(pad, 'drill')[1])
            cuts.append(Part.makeCylinder(d / 2, t + 2, App.Vector(x, -y, -1)))
    shape = plate.cut(Part.makeCompound(cuts))
    shape.translate(App.Vector(0, 0, BOARD_T + SEAT))
    return shape, t


def printed_panel():
    shape = read(MODULE / 'panels/front-cad/midi-front-panel.step')
    # CAD frame Y = 128.5 - panel Y  ->  STEP frame Y = -panel Y
    shape.translate(App.Vector(0, -PH, BOARD_T + SEAT))
    return shape, GEO['panel_print_thickness_mm']


def through(part, panel_top):
    """Highest Z of the part relative to the panel front face (+ = proud)."""
    return round(part.BoundBox.ZMax - panel_top, 3)


def main():
    board = read(FIT / 'board.step')
    back = read(FIT / 'back.step')
    refs = [j['ref'] for j in GEO['jacks']] + [d['ref'] for d in GEO['leds']]
    parts = {ref: read(FIT / f'{ref}.step') for ref in refs}
    report = {'frame': 'KiCad STEP, user origin = panel origin; Z0 = board bottom',
              'board_bbox_mm': [round(v, 3) for v in (board.BoundBox.XMin, board.BoundBox.XMax,
                                                      -board.BoundBox.YMax, -board.BoundBox.YMin)],
              'panels': {}}
    rail_y0, rail_y1 = GEO['rail_clear_gap_Y_mm']
    report['board_inside_rail_gap'] = (-board.BoundBox.YMax >= rail_y0 and -board.BoundBox.YMin <= rail_y1)
    report['board_inside_panel_width'] = (board.BoundBox.XMin >= 0 and board.BoundBox.XMax <= PW)
    lowest = min(back.BoundBox.ZMin, board.BoundBox.ZMin, *(p.BoundBox.ZMin for p in parts.values()))
    for name, (panel, t) in {'fr4_1.6': fr4_panel(), 'printed_2.0': printed_panel()}.items():
        top = BOARD_T + SEAT + t
        rows = {}
        for ref, part in parts.items():
            clash = part.common(panel).Volume
            rows[ref] = {'interference_mm3': round(clash, 4), 'top_vs_panel_front_mm': through(part, top)}
        report['panels'][name] = {
            'thickness_mm': t,
            'front_face_Z_mm': round(top, 3),
            'depth_behind_panel_rear_mm': round(BOARD_T + SEAT - lowest, 3),
            'parts': rows,
            'max_interference_mm3': max(r['interference_mm3'] for r in rows.values()),
        }
    asm = Part.makeCompound([board, back, *parts.values(), printed_panel()[0]])
    asm.exportStep(str(FIT / 'midi-fit-assembly.step'))
    out = MODULE / ('docs/fit' if VERSION == 'v1' else f'docs/{VERSION}/fit') / 'fit-report.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


main()
