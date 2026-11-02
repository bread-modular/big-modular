"""S8 single board: 3D assembly, collision screen and review images (system Python + FreeCAD + OpenSCAD).

  python3 -B tools/s8_mechanical.py [--freecad ~/Applications/FreeCAD_1.1.3.AppImage]

1. footprint courtyard centres from the native board (pcbnew) -> research/s8f/assembly/footprints.json
2. FreeCAD (tools/build_s8_assembly.py): native board + S8 panel STEP, brackets, M3 proxies, J1/SW1/L1-L3
   proxies, IDC plug/ribbon and tool envelopes; interference screen; STEP/FCStd/STL
3. OpenSCAD renders (front-right F side, rear-left B side with brackets) composed with a legend
4. KiCad raytraced board views (kicad-cli pcb render) from a render-only copy whose L1-L3 get a 10 x 10 mm
   KiCad proxy model (L_TechFuse_SL1040; the pinned SLO1040 footprint has none); the native board is untouched
5. placement drawing PDF of the native board (F.Fab references + pad sketches, courtyards, outline, notes)
Outputs: docs/s8-single/assembly/ (zipped STEP, report, images, PDF). Nominal geometry; not a fit approval.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pcbnew
from PIL import Image, ImageDraw, ImageFont

MODULE = Path(__file__).resolve().parents[1]
DESIGN = Path(os.environ.get('S8_DESIGN_ROOT', str(MODULE)))
BOARD = DESIGN / 'hardware/single/usb-power-45w-single.kicad_pcb'
WORK = Path(os.environ.get('S8_ASM_WORK', str(MODULE / 'research/s90/assembly')))
OUT = DESIGN / 'docs/s8-single/assembly'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
COLORS = [('panel', [0.91, 0.84, 0.66, 1]), ('carrier', [0.30, 0.58, 0.36, 1]), ('brackets', [0.90, 0.55, 0.23, 1]),
          ('screws', [0.75, 0.77, 0.80, 1]), ('nuts', [0.75, 0.77, 0.80, 1]), ('headers', [0.15, 0.15, 0.17, 1]),
          ('led', [0.85, 0.15, 0.15, 1]), ('ics', [0.22, 0.22, 0.25, 1]), ('passives', [0.72, 0.60, 0.42, 1]),
          ('inductors', [0.35, 0.36, 0.40, 1]), ('ui_envelopes', [0.55, 0.58, 0.63, 1]), ('plugs', [0.95, 0.72, 0.29, 0.75]),
          ('ribbons', [0.62, 0.66, 0.74, 0.55]), ('tools', [0.23, 0.65, 0.79, 0.25]), ('rails', [0.75, 0.75, 0.75, 0.35])]
LEGEND = [([0.91, 0.84, 0.66], 'S8 4HP panel (USB-C, MAIN LED, RESET)'),
          ([0.30, 0.58, 0.36], 'S8 board 100.5 x 48 x 1.6, every part on F'),
          ([0.22, 0.22, 0.25], 'ICs / diodes / transistors (KiCad models)'),
          ([0.72, 0.60, 0.42], 'R / C (KiCad models)'),
          ([0.35, 0.36, 0.40], 'L1 / L3 proxy 10.3 x 10.3 x 4.0 (no model)'),
          ([0.15, 0.15, 0.17], 'J2 / J3 16-pin box headers (THT)'),
          ([0.85, 0.15, 0.15], 'D8 MAIN LED (THT)'),
          ([0.55, 0.58, 0.63], 'J1 / SW1 body envelopes (no model)'),
          ([0.90, 0.55, 0.23], 'Two plain M3 L brackets'),
          ([0.75, 0.77, 0.80], 'M3 screws / nuts (proxies)'),
          ([0.95, 0.72, 0.29], 'PROPOSAL: mated IDC plug envelope'),
          ([0.62, 0.66, 0.74], 'PROPOSAL: ribbon leaving +Z to the bus'),
          ([0.23, 0.65, 0.79], 'Tool paths: M3 nut driver / pliers'),
          ([0.75, 0.75, 0.75], 'Case rail section (context)')]
STAMP = 'S9.0 SINGLE BOARD P2.0 - TRIAL PLACEMENT, UNROUTED - NOT A RELEASE - nominal mm'


def footprints():
    b = pcbnew.LoadBoard(str(BOARD))
    out = {}
    for fp in b.GetFootprints():
        r = fp.GetReference()
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if not r or cy.OutlineCount() == 0:
            continue
        c = cy.BBox().Centre()
        out[r] = {'centre_YZ': [round(pcbnew.ToMM(c.x) - 35.75, 4), round(104.275 - pcbnew.ToMM(c.y), 4)]}
    return out


def scad_render(name, eye, center, size=(1800, 1300), skip=()):
    lines = ['$fn=48;', 'multmatrix([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]) {']
    for n, c in COLORS:
        if n not in skip and (WORK / 'stl' / f'{n}.stl').exists():
            lines.append(f'  color({c}) import("{WORK / "stl" / (n + ".stl")}");')
    lines.append('}')
    scad = WORK / f'{name}.scad'
    scad.write_text('\n'.join(lines) + '\n')
    png = WORK / f'{name}-raw.png'
    cam = ','.join(str(v) for v in eye + center)
    subprocess.run(['xvfb-run', '-a', 'openscad', '-o', str(png), f'--imgsize={size[0]},{size[1]}', f'--camera={cam}',
                    '--projection=o', '--viewall', '--colorscheme=Tomorrow', str(scad)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png


def compose(raw, out, title, captions, legend=LEGEND):
    img = Image.open(raw).convert('RGB')
    W, H = img.size
    pad_top, pad_right = 150, 660 if legend else 0
    canvas = Image.new('RGB', (W + pad_right, H + pad_top), 'white')
    canvas.paste(img, (0, pad_top))
    d = ImageDraw.Draw(canvas)
    f1, f2, f3 = ImageFont.truetype(FONTB, 38), ImageFont.truetype(FONT, 24), ImageFont.truetype(FONT, 22)
    d.text((30, 20), title, fill=(29, 47, 69), font=f1)
    for i, c in enumerate(captions):
        d.text((30, 74 + i * 30), c, fill=(29, 47, 69), font=f2)
    if legend:
        x, y = W + 20, pad_top + 10
        d.text((x, y), 'Legend', fill=(29, 47, 69), font=ImageFont.truetype(FONTB, 26))
        y += 44
        for color, label in legend:
            d.rectangle([x, y, x + 34, y + 24], fill=tuple(int(255 * v) for v in color[:3]), outline=(40, 40, 40))
            d.text((x + 46, y - 1), label, fill=(29, 47, 69), font=f3)
            y += 40
    d.text((30, H + pad_top - 40), STAMP, fill=(176, 0, 106), font=f2)
    canvas.save(out)
    return out


def kicad_renders():
    """Raytraced board views from a render-only copy (inductor proxy model); the native board is not touched."""
    tmp = WORK / 'render-copy'
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(BOARD.parent, tmp, ignore=shutil.ignore_patterns('*.kicad_prl', '*-backups'))
    shutil.copytree(MODULE / 'hardware/USBPOWER45.pretty', tmp.parent / 'USBPOWER45.pretty', dirs_exist_ok=True)
    pcb = tmp / BOARD.name
    b = pcbnew.LoadBoard(str(pcb))
    for fp in b.GetFootprints():
        if fp.GetFPIDAsString().endswith('L_SLO1040H6R8MTT') and len(fp.Models()) == 0:
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = '${KICAD10_3DMODEL_DIR}/Inductor_SMD.3dshapes/L_TechFuse_SL1040.step'
            fp.Models().append(m)
    pcbnew.SaveBoard(str(pcb), b)
    shots = {'board-top': ['--side', 'top', '-w', '2400', '-h', '1250', '--zoom', '1.7'],
             'board-iso': ['--side', 'top', '--rotate', '-40,0,-25', '--perspective', '-w', '2400', '-h', '1500', '--zoom', '1.3']}
    out = {}
    for name, args in shots.items():
        png = OUT / f'{name}.jpg'
        subprocess.run(['kicad-cli', 'pcb', 'render', '-o', str(png), '--quality', 'high', '--background', 'opaque',
                        '-D', 'KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels'] + args + [str(pcb)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out[name] = png
    return out


def placement_pdf():
    """Fab drawing of the native board (references, pad sketches, courtyards, outline, keep-out notes)."""
    pdf = OUT / 'usb-power-45w-single-placement.pdf'
    subprocess.run(['kicad-cli', 'pcb', 'export', 'pdf', '--mode-single', '-o', str(pdf),
                    '-l', 'F.Fab,F.Courtyard,F.Silkscreen,Edge.Cuts,User.Drawings,User.Comments', '--sp', '--ev',
                    '--ibt', '--scale', '0', str(BOARD)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pdf


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--freecad', type=Path, default=Path.home() / 'Applications/FreeCAD_1.1.3.AppImage')
    ap.add_argument('--skip-freecad', action='store_true', help='reuse the last FreeCAD output in research/')
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (WORK / 'footprints.json').write_text(json.dumps(footprints(), indent=1) + '\n')
    if not a.skip_freecad:
        env = dict(os.environ, S8_ASM_WORK=str(WORK))
        r = subprocess.run([str(a.freecad), 'freecadcmd', str(MODULE / 'tools/build_s8_assembly.py')], env=env,
                           capture_output=True, text=True)
        (WORK / 'freecad.log').write_text(r.stdout + '\n' + r.stderr)
        if r.returncode != 0 or not (WORK / 'report.json').exists():
            raise SystemExit(f'FreeCAD failed, see {WORK / "freecad.log"}')
    rep = json.loads((WORK / 'report.json').read_text())
    with zipfile.ZipFile(OUT / 'usb-power-45w-single-assembly.step.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(WORK / 'assembly.step', 'usb-power-45w-single-assembly.step')     # 10 MB STEP -> ~1.7 MB
    (OUT / 'assembly-report.json').write_text(json.dumps(rep, indent=1) + '\n')
    raw = scad_render('iso-front', [230, -120, 90], [10, 25, -64], size=(1700, 1400))
    compose(raw, OUT / 'iso-front.png', 'usb-power-45w S8 single board - 3D assembly, front-right (F side)',
            ['Native S9.0 / P2.0 board + S9 panel, brackets, M3, inductor/J1/SW1 body proxies and envelopes.',
             'X across 4HP (20.0), Y down, Z into the case (50 mm deep board). Every part on F; unrouted.',
             f'Collision screen: {len(rep["solid_interference_mm3"])} part-to-part / part-to-hardware overlaps.'])
    raw = scad_render('iso-rear', [-230, 110, 90], [10, 25, -64], size=(1700, 1400))
    compose(raw, OUT / 'iso-rear.png', 'usb-power-45w S8 single board - 3D assembly, rear-left (B side, brackets)',
            ['Both L brackets on the board B face; M3 side screws from -X (flush heads), nuts on F.',
             'Panel M3 screws from the front, nuts on the bracket foot. Ribbons leave the plugs toward +Z.',
             'B face carries no parts (single-sided assembly); THT tails trimmed <= 1.8 mm.'])
    kicad = kicad_renders()
    placement_pdf()
    print(json.dumps({'report': {k: rep[k] for k in ('solid_interference_mm3', 'extents', 'proxies')},
                      'images': sorted(str(p.relative_to(DESIGN)) for p in OUT.glob('*.[pj][np]g'))}, indent=1))
    return rep, kicad


if __name__ == '__main__':
    main()
