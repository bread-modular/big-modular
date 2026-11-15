"""Import the pinned DRIVE footprints into hardware/DRIVE.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed. pcbnew
gives every saved item a new random UUID; a footprint that is otherwise identical to the
file already in the library keeps that file, so a re-run only changes what really changed.

Run from modules/drive with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only, as modules/vca-mix: the Bread Modular AudioJacks library (MIT,
Barwise) for the jack, the benjiaomodular library that Bread Modular uses for its RV09
pots (CC-BY-SA 4.0) and the installed KiCad stock library for everything else.
Footprints are loaded and saved natively by pcbnew, so the copies are KiCad 10 format.
The only intentional edits:

- PJ301M-12 jack: exactly the MIDI module's edits (3D model -> ${KIPRJMOD}/DRIVE.3dshapes,
  the two decorative F.SilkS arcs over the TN pad removed, F.CrtYd -> model envelope
  + 0.25 mm);
- RV09: none (native load/save only). No 3D model exists upstream.

The STEP file is copied byte-exactly. hardware/DRIVE.pretty/PROVENANCE.json records
source paths and SHA-256 of every input and output.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
LIB = HW / 'DRIVE.pretty'
MODELS = HW / 'DRIVE.3dshapes'
STOCK = Path('/usr/share/kicad/footprints')

STOCK_FOOTPRINTS = [
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Package_SO', 'SOIC-16_3.9x9.9mm_P1.27mm'),
    ('Package_TO_SOT_SMD', 'SOT-23'),
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
    keep.m_Filename = '${KIPRJMOD}/DRIVE.3dshapes/' + step
    models.clear()
    models.push_back(keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bread-modular', default=str(Path.home() / 'data/projects/bread-modular'))
    args = ap.parse_args()
    bm = Path(args.bread_modular) / 'opt'
    jacks = bm / 'AudioJacks'
    LIB.mkdir(exist_ok=True)
    before = {old.name: old.read_text() for old in LIB.glob('*.kicad_mod')}
    for old in LIB.glob('*.kicad_mod'):
        old.unlink()
    MODELS.mkdir(exist_ok=True)
    record = {'footprints': {}, 'models': {}}
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

    def load(src):
        fp = io.FootprintLoad(str(src.parent), src.stem)
        fp.SetFPID(pcbnew.LIB_ID('DRIVE', src.stem))
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
                     f'3D model -> ${{KIPRJMOD}}/DRIVE.3dshapes/{step}'}
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
    no_uuid = lambda text: re.sub(r'\(uuid "[0-9a-f-]+"\)', '', text)  # noqa: E731
    for name in record['footprints']:
        out = LIB / f'{name}.kicad_mod'
        old = before.get(out.name)
        if old is not None and no_uuid(old) == no_uuid(out.read_text()):
            out.write_text(old)
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
