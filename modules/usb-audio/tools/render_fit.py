"""Render the S1 placement: carrier, MCU board, panel and the stacked assembly (nominal).

Run from modules/usb-audio with KiCad's Python (pcbnew 10):  python3 -B tools/render_fit.py
Writes research/fit/ (ignored: STEP exports, the assembly board copy) and docs/fit/*.png.

The assembly is a research copy of the carrier with the parked SMD removed and two fit footprints
whose 3D models are the MCU board STEP (placed parts only, bottom at Z = header plastic 2.5 mm)
and the panel STEP (rear at Z = panel_rear_seat 10 mm), all in the panel frame. Nominal model
geometry only: the USB-C and the RV09 are envelope proxies.
"""
import json
import subprocess
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
GEO = json.loads((MODULE / 'docs/geometry.json').read_text())
OX, OY = GEO['kicad_origin_mm']
FIT = MODULE / 'research/fit'
DOCS = MODULE / 'docs/fit'
CLI = ['kicad-cli']
VARS = ['-D', 'KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels']


def run(*args):
    subprocess.run([*CLI, *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def placed_refs(path, box):
    board = pcbnew.LoadBoard(str(path))
    x0, y0, x1, y1 = box
    out = []
    for fp in board.GetFootprints():
        p = fp.GetPosition()
        if x0 <= pcbnew.ToMM(p.x) - OX <= x1 and y0 <= pcbnew.ToMM(p.y) - OY <= y1:
            out.append(fp.GetReference())
    return out


def fit_footprint(board, ref, step, z):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
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
    carrier, mcu = hw / 'usb-audio.kicad_pcb', hw / 'usb-audio-mcu.kicad_pcb'
    panel = MODULE / 'panels/front-pcb/usb-audio-panel.kicad_pcb'
    origin = f'{OX}x{OY}mm'
    mcu_refs = placed_refs(mcu, GEO['mcu_pcb']['outline_mm'])  # J102/J103 = carrier J6/J7 strips (drawn there)
    run('pcb', 'export', 'step', *VARS, '--force', '--user-origin', origin, '--include-silkscreen',
        '--include-soldermask', '--component-filter', ','.join(r for r in mcu_refs if r not in ('J102', 'J103')), '-o', str(FIT / 'mcu.step'), str(mcu))
    run('pcb', 'export', 'step', *VARS, '--force', '--user-origin', origin, '--board-only', '--include-silkscreen',
        '-o', str(FIT / 'panel.step'), str(panel))
    board = pcbnew.LoadBoard(str(carrier))
    keep = set(placed_refs(carrier, GEO['main_pcb']['outline_mm']))
    for fp in list(board.GetFootprints()):
        if fp.GetReference() not in keep:
            board.Delete(fp)
            continue
        models = fp.Models()  # the copy lives in research/fit: bind ${KIPRJMOD} models absolutely
        for i in range(len(models)):
            m = models[i]
            m.m_Filename = m.m_Filename.replace('${KIPRJMOD}', str(hw))
            models[i] = m
    stack = GEO['stack_Z_mm']
    fit_footprint(board, 'FIT_MCU', FIT / 'mcu.step', stack['mcu_board_bottom'])
    asm = FIT / 'usb-audio-assembly.kicad_pcb'
    pcbnew.SaveBoard(str(asm), board)
    fit_footprint(board, 'FIT_PANEL', FIT / 'panel.step', stack['panel_rear_seat'])
    asm_panel = FIT / 'usb-audio-assembly-panel.kicad_pcb'
    pcbnew.SaveBoard(str(asm_panel), board)
    for src in (hw / 'usb-audio.kicad_pro',):
        for dst in (asm, asm_panel):
            dst.with_suffix('.kicad_pro').write_text(src.read_text())
    shots = [
        (asm, 'assembly-iso-front.png', ['--rotate', '-35,0,25', '--perspective', '--zoom', '0.95']),
        (asm, 'assembly-side.png', ['--side', 'right', '--zoom', '1.0']),
        (asm_panel, 'assembly-panel-iso.png', ['--rotate', '-35,0,25', '--perspective', '--zoom', '0.95']),
        (asm_panel, 'assembly-panel-front.png', ['--zoom', '0.85']),
        (mcu, 'mcu-board-top.png', ['--zoom', '1.0']),
        (carrier, 'carrier-back.png', ['--side', 'bottom', '--zoom', '1.0']),
    ]
    for pcb, name, extra in shots:
        run('pcb', 'render', *VARS, '--quality', 'high', '--background', 'opaque', '-w', '1600', '-h', '1200',
            *extra, '-o', str(DOCS / name), str(pcb))
        print(DOCS / name)
    overview()


def overview():
    """docs/fit/overview.png: panel front, assembly, MCU board top, side by side (tight crops)."""
    import numpy as np
    from PIL import Image

    def crop(name, pad):
        im = Image.open(DOCS / name).convert('RGB')
        a = np.asarray(im).astype(int)
        m = (a[..., 1] > a[..., 0] + 15) & (a[..., 1] > a[..., 2] + 5)   # green board / panel pixels
        ys, xs = np.where(m)
        return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                        min(im.width, xs.max() + pad), min(im.height, ys.max() + pad)))
    h = 1100
    ims = [crop('assembly-panel-front.png', 30), crop('assembly-iso-front.png', 60), crop('mcu-board-top.png', 30)]
    ims = [im.resize((int(im.width * h / im.height), h)) for im in ims]
    out = Image.new('RGB', (sum(i.width for i in ims) + 40 * (len(ims) + 1), h + 80), (245, 245, 245))
    x = 40
    for im in ims:
        out.paste(im, (x, 40))
        x += im.width + 40
    out.save(DOCS / 'overview.png')
    print(DOCS / 'overview.png')


main()
