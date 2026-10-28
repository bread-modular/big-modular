"""Generate the blank 2/4/6/8 HP front panels from docs/geometry.json.

Run from modules/blank with KiCad's Python (pcbnew 10):
  python3 -B tools/build_panels.py

Writes panels/front-pcb/blank-<n>hp.kicad_{pcb,pro}: passive panel, Edge.Cuts outline and
the rail NPTH holes only (no copper, no silk). The .kicad_pro is copied from the 8bit panel
project (same design rules).
"""
import json
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
OUT = MODULE / 'panels/front-pcb'
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
OX, OY = GEO['kicad_origin_mm']
PRO_TEMPLATE = REPO / 'modules/8bit/panels/front-pcb/8bit-panel.kicad_pro'


def pt(x, y):
    """Panel-frame mm -> KiCad internal units."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def npth(board, mech_id, x, y, d):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(mech_id)
    fp.SetValue('MECHANICAL_NPTH')
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
    fp.SetField('MechanicalID', mech_id)
    fp.GetField('MechanicalID').SetVisible(False)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE)
    size = pcbnew.VECTOR2I(pcbnew.FromMM(d), pcbnew.FromMM(d))
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, size)
    pad.SetDrillSize(size)
    pad.SetLayerSet(pad.UnplatedHoleMask())
    fp.Add(pad)
    pad.thisown = 0
    yard = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    yard.SetLayer(pcbnew.F_CrtYd)
    yard.SetWidth(pcbnew.FromMM(0.05))
    yard.SetCenter(pcbnew.VECTOR2I(0, 0))
    yard.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(d / 2 + 0.25), 0))
    fp.Add(yard)
    yard.thisown = 0
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pt(x, y))


def build_panel(spec):
    path = OUT / f"{spec['name']}.kicad_pcb"
    board = pcbnew.NewBoard(str(path))
    tb = board.GetTitleBlock()
    tb.SetTitle(f"Big Modular - blank {spec['hp']}HP front panel")
    tb.SetRevision('S1')
    tb.SetCompany('Big Modular')
    tb.SetComment(0, 'Blank passive panel, NPTH rail holes only, no copper')
    tb.SetComment(1, 'Geometry contract: ../../docs/geometry.json')
    w, h = spec['width_mm'], GEO['panel_height_mm']
    edge = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.05))
    edge.SetStart(pt(0, 0))
    edge.SetEnd(pt(w, h))
    board.Add(edge)
    edge.thisown = 0
    n = 0
    for y in GEO['rail_hole_Y_mm']:
        for x in spec['rail_hole_X_mm']:
            n += 1
            npth(board, f'H{n}', x, y, GEO['rail_hole_diameter_mm'])
    # Save, reload and save again so the file equals its native re-serialisation.
    pcbnew.SaveBoard(str(path), board)
    pcbnew.SaveBoard(str(path), pcbnew.LoadBoard(str(path)))
    pro = json.loads(PRO_TEMPLATE.read_text())
    pro['meta']['filename'] = f"{spec['name']}.kicad_pro"
    pro['schematic']['top_level_sheets'][0].update(filename=f"{spec['name']}.kicad_sch", name=spec['name'])
    path.with_suffix('.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n')
    path.with_suffix('.kicad_prl').unlink(missing_ok=True)
    return path


if __name__ == '__main__':
    for spec in GEO['panels']:
        print(build_panel(spec))
