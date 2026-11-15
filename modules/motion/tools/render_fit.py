"""Render the P1 placement: carrier with its THT parts, alone and behind the 6HP panel (nominal).

Run from modules/motion with KiCad's Python (pcbnew 10):  python3 -B tools/render_fit.py
Writes research/fit/ (ignored: the panel STEP and the assembly board copies) and docs/fit/*.png.

The assembly is a research copy of the carrier without the parked SMD parts, plus a fit
footprint whose 3D model is the panel STEP (rear at Z = panel_rear_seat 10 mm), all in the
panel frame. Nominal model geometry only: the RV09 is an envelope proxy, the LEDs stand at the
height of geometry.json stack_Z_mm, and the printed button caps are not modelled.
"""
import json
import os
import subprocess
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
OX, OY = GEO['kicad_origin_mm']
FIT = MODULE / 'research/fit'
DOCS = MODULE / 'docs/fit'
VARS = ['-D', 'KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels']


def run(*args):
    subprocess.run(['kicad-cli', *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fit_footprint(board, ref, step, z):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    # through-hole type: the kicad-cli render preset hides the models of unspecified / not-in-POS footprints
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE)
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = str(step)
    model.m_Offset = pcbnew.VECTOR3D(0, 0, z)
    fp.Models().push_back(model)
    board.Add(fp)
    fp.thisown = 0
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(OX), pcbnew.FromMM(OY)))


def main():
    FIT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    hw = MODULE / 'hardware'
    carrier = hw / 'motion.kicad_pcb'
    panel = MODULE / 'panels/front-pcb/motion-panel.kicad_pcb'
    run('pcb', 'export', 'step', *VARS, '--force', '--user-origin', f'{OX}x{OY}mm', '--board-only',
        '--include-silkscreen', '-o', str(FIT / 'panel.step'), str(panel))
    board = pcbnew.LoadBoard(str(carrier))
    x0, y0, x1, y1 = GEO['main_pcb']['outline_mm']
    for fp in list(board.GetFootprints()):
        p = fp.GetPosition()
        if not (x0 <= pcbnew.ToMM(p.x) - OX <= x1 and y0 <= pcbnew.ToMM(p.y) - OY <= y1):
            board.Delete(fp)  # parked SMD part
            continue
        models = fp.Models()  # the copy lives in research/fit: bind ${KIPRJMOD} models absolutely
        for i in range(len(models)):
            m = models[i]
            m.m_Filename = m.m_Filename.replace('${KIPRJMOD}', str(hw))
            models[i] = m
    for d in list(board.GetDrawings()):  # fit references (panel outline, rail bands, IDC envelope)
        if d.GetLayer() == pcbnew.Dwgs_User:
            board.Delete(d)
    asm = FIT / 'motion-assembly.kicad_pcb'
    pcbnew.SaveBoard(str(asm), board)
    fit_footprint(board, 'FIT_PANEL', FIT / 'panel.step', GEO['stack_Z_mm']['panel_rear_seat'])
    asm_panel = FIT / 'motion-assembly-panel.kicad_pcb'
    pcbnew.SaveBoard(str(asm_panel), board)
    for dst in (asm, asm_panel):
        dst.with_suffix('.kicad_pro').write_text((hw / 'motion.kicad_pro').read_text())
    shots = [
        (asm_panel, 'assembly-panel-front.png', ['--zoom', '0.75']),
        (asm_panel, 'assembly-panel-iso.png', ['--rotate', '-55,0,-30', '--perspective', '--zoom', '0.65']),
        (asm_panel, 'assembly-panel-side.png', ['--side', 'right', '--zoom', '0.75']),
        (asm, 'carrier-front.png', ['--zoom', '0.75']),
        (asm, 'carrier-iso.png', ['--rotate', '-55,0,-30', '--perspective', '--zoom', '0.65']),
        (asm, 'carrier-back.png', ['--side', 'bottom', '--zoom', '0.9']),
        (panel, 'panel-front.png', ['--zoom', '0.75']),
    ]
    for pcb, name, extra in shots:
        run('pcb', 'render', *VARS, '--quality', 'high', '--background', 'opaque', '-w', '1400', '-h', '1800',
            *extra, '-o', str(DOCS / name), str(pcb))
        print(DOCS / name)
    overview()


def overview():
    """docs/fit/overview.png: panel front, 3D view with the panel, carrier 3D view, side by side."""
    import numpy as np
    from PIL import Image

    def crop(name, pad):
        im = Image.open(DOCS / name).convert('RGB')
        a = np.asarray(im).astype(int)
        bg = a[2, 2]
        ys, xs = np.where(np.abs(a - bg).sum(axis=2) > 30)
        return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                        min(im.width, xs.max() + pad), min(im.height, ys.max() + pad)))
    h = 1300
    ims = [crop(n, 30) for n in ('assembly-panel-front.png', 'assembly-panel-iso.png', 'carrier-iso.png')]
    ims = [im.resize((int(im.width * h / im.height), h)) for im in ims]
    out = Image.new('RGB', (sum(i.width for i in ims) + 40 * (len(ims) + 1), h + 80), (245, 245, 245))
    x = 40
    for im in ims:
        out.paste(im, (x, 40))
        x += im.width + 40
    out.save(DOCS / 'overview.png')
    print(DOCS / 'overview.png')


main()
os._exit(0)  # pcbnew can crash on interpreter teardown after footprints were deleted
