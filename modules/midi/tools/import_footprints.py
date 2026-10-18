"""Import the pinned MIDI footprints into hardware/MIDI.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed.

Run from modules/midi with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only: the Bread Modular AudioJacks library (MIT, Barwise) for the
two jacks and the installed KiCad stock library for everything else. Footprints are
loaded and saved natively by pcbnew, so the copies are KiCad 10 format. The only
intentional edits are on the two jacks:

- 3D model path -> ${KIPRJMOD}/MIDI.3dshapes/<jack>.step (plain model, no nut);
- the two decorative F.SilkS arcs (R2.895) are removed: they cross the TN/R pad
  and only produce silk-over-copper findings;
- F.CrtYd -> the STEP model envelope + 0.25 mm. The upstream courtyard (X +/-5.0,
  Y -7.25..7.58) is sized around the reference text, not the body; the model body
  is X +/-4.5 (PJ301M-12) / +/-5.0 (PJ366ST), Y -6.0..4.5 with the S pad to 7.53.

The STEP files are copied byte-exactly. hardware/MIDI.pretty/PROVENANCE.json records
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
LIB = HW / 'MIDI.pretty'
MODELS = HW / 'MIDI.3dshapes'
STOCK = Path('/usr/share/kicad/footprints')

STOCK_FOOTPRINTS = [
    ('LED_THT', 'LED_D3.0mm'),
    ('Package_DFN_QFN', 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm'),
    ('Package_TO_SOT_SMD', 'SOT-89-3'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_1206_3216Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_1x02_P2.54mm_Vertical'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical'),
]

# name -> (step file, courtyard half-width X, courtyard Y top, courtyard Y bottom)
JACKS = {
    'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical': ('PJ301M-12.step', 4.75, -6.25, 7.80),
    'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical': ('PJ366ST.step', 5.25, -6.25, 7.80),
}


# The stock footprint references a model KiCad does not ship; use the only shipped
# 3x3 mm 20-pin P0.4 body (UQFN, thinner than VQFN) as an explicitly recorded visual
# proxy. The <0.4 mm height difference is irrelevant to the panel fit.
MODEL_PROXY = {
    'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm':
        '${KICAD10_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm.step',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    """Host-neutral provenance path (~ for the home directory)."""
    return str(path).replace(str(Path.home()), '~', 1)


def mm(v):
    return pcbnew.FromMM(v)


def fix_jack(fp, step, hx, ytop, ybot):
    for item in list(fp.GraphicalItems()):
        is_ring = (item.GetLayer() == pcbnew.F_SilkS and item.GetClass() == 'PCB_SHAPE'
                   and item.GetShape() == pcbnew.SHAPE_T_ARC)
        if item.GetLayer() == pcbnew.F_CrtYd or is_ring:
            fp.Delete(item)
    rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    rect.SetLayer(pcbnew.F_CrtYd)
    rect.SetWidth(mm(0.05))
    rect.SetStart(pcbnew.VECTOR2I(mm(-hx), mm(ytop)))
    rect.SetEnd(pcbnew.VECTOR2I(mm(hx), mm(ybot)))
    fp.Add(rect)
    rect.thisown = 0  # the footprint owns it now
    models = fp.Models()
    keep = pcbnew.FP_3DMODEL()
    keep.m_Filename = '${KIPRJMOD}/MIDI.3dshapes/' + step
    models.clear()
    models.push_back(keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bread-modular', default=str(Path.home() / 'data/projects/bread-modular'))
    args = ap.parse_args()
    jacks = Path(args.bread_modular) / 'opt/AudioJacks'
    LIB.mkdir(exist_ok=True)
    for old in LIB.glob('*.kicad_mod'):
        old.unlink()
    MODELS.mkdir(exist_ok=True)
    record = {'footprints': {}, 'models': {}}
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    for lib, name in STOCK_FOOTPRINTS:
        src = STOCK / f'{lib}.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID('MIDI', name))
        edits = 'none (native load/save only)'
        if name in MODEL_PROXY:
            models = fp.Models()
            model = models[0]
            missing = model.m_Filename
            model.m_Filename = MODEL_PROXY[name]
            models[0] = model
            edits = f'3D model {missing} is not shipped by KiCad; visual proxy {MODEL_PROXY[name]}'
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'KiCad library CC-BY-SA-4.0-with-exception',
                                      'edits': edits}
    for name, (step, hx, ytop, ybot) in JACKS.items():
        src = jacks / 'AudioJacks.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID('MIDI', name))
        fix_jack(fp, step, hx, ytop, ybot)
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {
            'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2021 Barwise',
            'edits': 'removed two decorative F.SilkS arcs crossing the TN/R pad; '
                     f'F.CrtYd -> X +/-{hx}, Y {ytop}..{ybot} (model envelope +0.25); '
                     f'3D model -> ${{KIPRJMOD}}/MIDI.3dshapes/{step}'}
        model_src = jacks / 'AudioJacks.3dshapes' / step
        shutil.copyfile(model_src, MODELS / step)
        record['models'][step] = {'source': rel(model_src), 'sha256': sha(model_src),
                                  'license': 'MIT (c) 2021 Barwise'}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
