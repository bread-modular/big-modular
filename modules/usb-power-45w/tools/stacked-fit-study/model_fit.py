#!/usr/bin/env python3
"""Extract a box model of the two candidate boards (study only).

Writes docs/stacked-fit-study/model.json: per footprint YZ courtyard/body/pad boxes,
board, side, sheet group, assumed max height and absolute X range. Consumed by
check_fit.py and render_fit.py (plain JSON, no pcbnew needed there).
"""
import json
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[1]
sys.path.insert(0, str(HERE))
from stacked_fit import DOC, HEIGHT, STACK, to_yz  # noqa: E402


def yzbox(bb):
    return [round(pcbnew.ToMM(bb.GetLeft()) - 35.75, 4), round(pcbnew.ToMM(bb.GetRight()) - 35.75, 4),
            round(104.275 - pcbnew.ToMM(bb.GetBottom()), 4), round(104.275 - pcbnew.ToMM(bb.GetTop()), 4)]


def signature(f):
    """Copied-field and pad-geometry signature (footprint-local, so placement-independent)."""
    fields = {x.GetName(): x.GetText() for x in f.GetFields() if x.GetName() != 'Reference'}
    pads = []
    for p in f.Pads():
        rp = p.GetFPRelativePosition()
        sz = p.GetSize(pcbnew.F_Cu)
        pads.append([p.GetNumber(), int(p.GetAttribute()), int(p.GetShape(pcbnew.F_Cu)),
                     round(pcbnew.ToMM(rp.x), 4), round(pcbnew.ToMM(rp.y), 4),
                     round(pcbnew.ToMM(sz.x), 4), round(pcbnew.ToMM(sz.y), 4),
                     round(pcbnew.ToMM(p.GetDrillSizeX()), 4), round(pcbnew.ToMM(p.GetDrillSizeY()), 4),
                     p.GetLayerSet().FmtHex()])
    return {'fpid': f'{f.GetFPID().GetLibNickname()}:{f.GetFPID().GetLibItemName()}',
            'attributes': int(f.GetAttributes()), 'fields': fields, 'pads': sorted(pads),
            'dnp': bool(f.IsDNP()), 'exclude_from_bom': bool(f.IsExcludedFromBOM()),
            'exclude_from_pos': bool(f.IsExcludedFromPosFiles())}


def main():
    man = json.loads((DOC / 'placement-manifest.json').read_text())
    sheets = man['sheets']
    out = {'stack': STACK, 'parts': []}
    for name in ('base', 'top'):
        b = pcbnew.LoadBoard(str(DOC / 'boards' / name / f'usb-power-45w-{name}.kicad_pcb'))
        face = STACK['base_F'] if name == 'base' else STACK['top_F']
        for f in b.GetFootprints():
            ref = f.GetReference()
            fpn = str(f.GetFPID().GetLibItemName())
            cy = f.GetCourtyard(pcbnew.F_CrtYd)
            court = yzbox(cy.BBox()) if cy.OutlineCount() else yzbox(f.GetBoundingBox(False, False))
            pads = []
            for p in f.Pads():
                pads.append({'num': p.GetNumber(), 'net': p.GetNetname(),
                             'smd': p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD,
                             'npth': p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH,
                             'box': yzbox(p.GetBoundingBox()),
                             'drill': round(pcbnew.ToMM(p.GetDrillSizeX()), 3)})
            if ref.startswith('X'):
                h = 2.5 if name == 'base' else 0.0      # header plastic sits on the base F face
                grp = 'interconnect'
            elif ref.startswith('MH'):
                h, grp = 0.0, 'standoff'
            elif not ref:
                h, grp = 0.0, 'carrier hole'
            else:
                h = HEIGHT[fpn]
                grp = sheets[ref].strip('/').split(' - ')[0]
            # body box: courtyard shrunk by its 0.25 class margin (visual/collision proxy)
            body = [court[0] + 0.25, court[1] - 0.25, court[2] + 0.25, court[3] - 0.25]
            out['parts'].append({'ref': ref, 'board': name, 'fp': fpn, 'group': grp,
                                 'pos': [round(v, 4) for v in to_yz(f.GetPosition())],
                                 'rot': f.GetOrientationDegrees(), 'court': court, 'body': body,
                                 'height': h, 'X': [face, round(face + h, 3)], 'pads': pads,
                                 'value': f.GetValue(), 'sig': signature(f)})
        edges = []
        for d in b.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts:
                edges.append([to_yz(d.GetStart()), to_yz(d.GetEnd())])
        out[f'{name}_edges'] = edges
    acc = pcbnew.LoadBoard(str(MOD / 'hardware' / 'usb-power-45w.kicad_pcb'))   # read-only
    out['accepted_fixed'] = {f.GetReference(): [*map(lambda v: round(v, 4), to_yz(f.GetPosition())),
                                                f.GetOrientationDegrees()]
                             for f in acc.GetFootprints()
                             if f.GetReference() in ('J1', 'J2', 'J3', 'SW1', 'D8', 'D16', 'D17', 'D18')}
    out['accepted_sig'] = {f.GetReference(): signature(f) for f in acc.GetFootprints() if f.GetReference()}
    (DOC / 'model.json').write_text(json.dumps(out))
    print(len(out['parts']))


if __name__ == '__main__':
    main()
