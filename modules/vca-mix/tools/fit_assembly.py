"""Nominal panel-over-carrier fit check (FreeCAD, headless). Use tools/fit_assembly.sh.

Inputs (written by the wrapper with kicad-cli, user origin = panel origin):
  research/fit/board.step      carrier body only
  research/fit/<REF>.step      one STEP per front-side THT part (J1..J9, J11)
  research/fit/back.step       all back-side parts
Panels: the printed panel STEP (panels/front-cad) and an FR4 plate built from the
native panel PCB holes at panel_pcb_thickness_mm.

KiCad STEP frame: X = panel X, Y = -panel Y, board Z0..1.6 with F.Cu at Z1.6.
The panel rear face sits stack_Z_mm.panel_rear_seat above F.Cu.
Writes docs/fit/fit-report.json and research/fit/vca-mix-fit-assembly.step.
Nominal model geometry only: the jack models are 'Untested' upstream. The pots are
envelopes built from the Song Huei R0904N drawing (geometry.json pot_model); the
vactrols have no model and are listed under not_modelled.
"""
import json
import math
import sys
from pathlib import Path

import FreeCAD as App
import Part

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / 'tools'))
from sexp import nodes, one, parse  # noqa: E402

FIT = MODULE / 'research/fit'
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
    tree = parse((MODULE / 'panels/front-pcb/vca-mix-panel.kicad_pcb').read_text())
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
    shape = read(MODULE / 'panels/front-cad/vca-mix-front-panel.step')
    # CAD frame Y = 128.5 - panel Y  ->  STEP frame Y = -panel Y
    shape.translate(App.Vector(0, -PH, BOARD_T + SEAT))
    return shape, GEO['panel_print_thickness_mm']


def pot_envelope(x, y):
    """R0904N envelope at panel shaft XY: body + collar box, then the plain shaft."""
    m = GEO['pot_model']
    top = m['body_H_mm'] + m['collar_H_mm']
    body = Part.makeBox(m['body_D_mm'], m['body_W_mm'], top,
                        App.Vector(x - m['body_D_mm'] / 2, -y - m['body_W_mm'] / 2, BOARD_T))
    shaft = Part.makeCylinder(m['shaft_dia_mm'] / 2, m['shaft_tip_L_mm'] - top,
                              App.Vector(x, -y, BOARD_T + top))
    return body.fuse(shaft)


def through(part, panel_top):
    """Highest Z of the part relative to the panel front face (+ = proud)."""
    return round(part.BoundBox.ZMax - panel_top, 3)


def main():
    board = read(FIT / 'board.step')
    back = read(FIT / 'back.step')
    refs = [j['ref'] for j in GEO['jacks']]
    parts = {ref: read(FIT / f'{ref}.step') for ref in refs}
    pots = {p['ref']: pot_envelope(*p['shaft_XY']) for p in GEO['pots']}
    knurl = GEO['pot_model']['knurl_len_mm']
    report = {'frame': 'KiCad STEP, user origin = panel origin; Z0 = board bottom',
              'board_bbox_mm': [round(v, 3) for v in (board.BoundBox.XMin, board.BoundBox.XMax,
                                                      -board.BoundBox.YMax, -board.BoundBox.YMin)],
              'panels': {},
              'pot_model': 'Song Huei R0904N envelope from geometry.json pot_model (datasheet nominal, no vendor 3D model)',
              'not_modelled': {'vactrols': [v['ref'] for v in GEO['vactrols']],
                               'note': 'No VTL5C 3D model exists upstream; the vactrols are on B, behind the board (docs/research.md D4).'}}
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
        for ref, part in pots.items():
            proud = through(part, top)
            rows[ref] = {'interference_mm3': round(part.common(panel).Volume, 4), 'top_vs_panel_front_mm': proud,
                         'knurl_bottom_vs_panel_front_mm': round(proud - knurl, 3),
                         'body_top_below_panel_rear_mm': round(SEAT - GEO['pot_model']['body_H_mm']
                                                               - GEO['pot_model']['collar_H_mm'], 3)}
        report['panels'][name] = {
            'thickness_mm': t,
            'front_face_Z_mm': round(top, 3),
            'depth_behind_panel_rear_mm': round(BOARD_T + SEAT - lowest, 3),
            'parts': rows,
            'max_interference_mm3': max(r['interference_mm3'] for r in rows.values()),
        }
    asm = Part.makeCompound([board, back, *parts.values(), *pots.values(), printed_panel()[0]])
    asm.exportStep(str(FIT / 'vca-mix-fit-assembly.step'))
    out = MODULE / 'docs/fit/fit-report.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


main()
