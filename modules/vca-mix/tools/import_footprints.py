"""Import the pinned VCA-MIX footprints into hardware/VCA_MIX.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed.

Run from modules/vca-mix with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only: the Bread Modular AudioJacks library (MIT, Barwise) for the
jack, the benjiaomodular library that Bread Modular uses for its RV09 pots (CC-BY-SA
4.0), the Bread Modular MISC library (MIT) for the VTL5C vactrol and the installed
KiCad stock library for everything else. Footprints are loaded and saved natively by
pcbnew, so the copies are KiCad 10 format. The only intentional edits:

- PJ301M-12 jack: exactly the MIDI module's edits (3D model -> ${KIPRJMOD}/VCA_MIX.3dshapes,
  the two decorative F.SilkS arcs over the TN pad removed, F.CrtYd -> model envelope
  + 0.25 mm);
- VTL5C: the Bread Modular footprint as is (pads and its 10.16 x 15.24 mm silk box,
  sized for the wider Chinese vactrols). It has no courtyard, so F.CrtYd = the silk
  box outer edge + 0.25 mm (10.76 x 15.84 mm) is added for DRC body checks, plus three
  build-note silk lines inside the box (SOLDER FIRST / TRIM FLUSH / LED 18.5mA);
- RV09: none (native load/save only). No 3D model exists upstream.

The STEP file is copied byte-exactly. hardware/VCA_MIX.pretty/PROVENANCE.json records
source paths and SHA-256 of every input and output.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
LIB = HW / 'VCA_MIX.pretty'
MODELS = HW / 'VCA_MIX.3dshapes'
STOCK = Path('/usr/share/kicad/footprints')

STOCK_FOOTPRINTS = [
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_2512_6332Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
]

# name -> (step file, courtyard half-width X, courtyard Y top, courtyard Y bottom)
JACKS = {
    'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical': ('PJ301M-12.step', 4.75, -6.25, 7.80),
}

POT = 'Potentiometer_RV09'
VACTROL = 'VTL5C'
VACTROL_CRTYD = (5.38, 7.92)  # half-width X, half-height Y: BM silk box outer edge + 0.25
# Build notes (user direction 2026-10-20, D4/D10): silk inside the body box, across its short
# axis, in the strip between the pad 3/4 end and the pot bracket pad that lands mid-body
# (board X 103.6..108.8 at rot 90). (local Y, text); 0.8 mm font = the project minimum.
VACTROL_NOTES = [(4.4, 'SOLDER FIRST'), (3.1, 'TRIM FLUSH'), (1.8, 'LED 18.5mA')]
VACTROL_NOTE_SIZE = 0.8


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    """Host-neutral provenance path (~ for the home directory)."""
    return str(path).replace(str(Path.home()), '~', 1)


def mm(v):
    return pcbnew.FromMM(v)


def add_rect(fp, layer, hx, y0, y1, width):
    rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    rect.SetLayer(layer)
    rect.SetWidth(mm(width))
    rect.SetStart(pcbnew.VECTOR2I(mm(-hx), mm(y0)))
    rect.SetEnd(pcbnew.VECTOR2I(mm(hx), mm(y1)))
    fp.Add(rect)
    rect.thisown = 0  # the footprint owns it now


def fix_jack(fp, step, hx, ytop, ybot):
    for item in list(fp.GraphicalItems()):
        is_ring = (item.GetLayer() == pcbnew.F_SilkS and item.GetClass() == 'PCB_SHAPE'
                   and item.GetShape() == pcbnew.SHAPE_T_ARC)
        if item.GetLayer() == pcbnew.F_CrtYd or is_ring:
            fp.Delete(item)
    add_rect(fp, pcbnew.F_CrtYd, hx, ytop, ybot, 0.05)
    models = fp.Models()
    keep = pcbnew.FP_3DMODEL()
    keep.m_Filename = '${KIPRJMOD}/VCA_MIX.3dshapes/' + step
    models.clear()
    models.push_back(keep)


def fix_vactrol(fp):
    hx, hy = VACTROL_CRTYD
    assert not [i for i in fp.GraphicalItems() if i.GetLayer() == pcbnew.F_CrtYd], 'upstream VTL5C gained a courtyard'
    add_rect(fp, pcbnew.F_CrtYd, hx, -hy, hy, 0.05)
    for y, note in VACTROL_NOTES:
        text = pcbnew.PCB_TEXT(fp)
        text.SetText(note)
        text.SetLayer(pcbnew.F_SilkS)
        text.SetPosition(pcbnew.VECTOR2I(0, mm(y)))
        text.SetTextSize(pcbnew.VECTOR2I(mm(VACTROL_NOTE_SIZE), mm(VACTROL_NOTE_SIZE)))
        text.SetTextThickness(mm(0.12))
        text.SetKeepUpright(True)
        fp.Add(text)
        text.thisown = 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bread-modular', default=str(Path.home() / 'data/projects/bread-modular'))
    args = ap.parse_args()
    bm = Path(args.bread_modular) / 'opt'
    jacks = bm / 'AudioJacks'
    LIB.mkdir(exist_ok=True)
    for old in LIB.glob('*.kicad_mod'):
        old.unlink()
    MODELS.mkdir(exist_ok=True)
    record = {'footprints': {}, 'models': {}}
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

    def load(src):
        fp = io.FootprintLoad(str(src.parent), src.stem)
        fp.SetFPID(pcbnew.LIB_ID('VCA_MIX', src.stem))
        return fp

    for lib, name in STOCK_FOOTPRINTS:
        src = STOCK / f'{lib}.pretty' / f'{name}.kicad_mod'
        io.FootprintSave(str(LIB), load(src))
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'KiCad library CC-BY-SA-4.0-with-exception',
                                      'edits': 'none (native load/save only)'}
    for name, (step, hx, ytop, ybot) in JACKS.items():
        src = jacks / 'AudioJacks.pretty' / f'{name}.kicad_mod'
        fp = load(src)
        fix_jack(fp, step, hx, ytop, ybot)
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {
            'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2021 Barwise',
            'edits': 'removed two decorative F.SilkS arcs crossing the TN pad; '
                     f'F.CrtYd -> X +/-{hx}, Y {ytop}..{ybot} (model envelope +0.25); '
                     f'3D model -> ${{KIPRJMOD}}/VCA_MIX.3dshapes/{step}'}
        model_src = jacks / 'AudioJacks.3dshapes' / step
        shutil.copyfile(model_src, MODELS / step)
        record['models'][step] = {'source': rel(model_src), 'sha256': sha(model_src),
                                  'license': 'MIT (c) 2021 Barwise'}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')

    src = bm / 'KiCadLibraries/benjiaomodular.pretty' / f'{POT}.kicad_mod'
    io.FootprintSave(str(LIB), load(src))
    record['footprints'][POT] = {'source': rel(src), 'source_sha256': sha(src),
                                 'license': 'CC-BY-SA-4.0 (benjiaomodular KiCad libraries)',
                                 'edits': 'none (native load/save only); no 3D model upstream'}
    src = bm / 'BreadModular_MISC.pretty' / f'{VACTROL}.kicad_mod'
    fp = load(src)
    fix_vactrol(fp)
    io.FootprintSave(str(LIB), fp)
    hx, hy = VACTROL_CRTYD
    record['footprints'][VACTROL] = {
        'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2024 Arunoda Susiripala (Bread Modular)',
        'edits': f'added F.CrtYd X +/-{hx}, Y +/-{hy} (silk box + 0.25) and F.SilkS build notes '
                 f'{[n for _, n in VACTROL_NOTES]} inside the box; pads, original silk and text '
                 'unchanged; no 3D model upstream'}
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
