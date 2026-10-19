"""Import the pinned IMIX footprints into hardware/IMIX.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed.

Run from modules/imix with KiCad's Python (pcbnew 10), after tools/build_pot_model.py:
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only: the Bread Modular AudioJacks library (MIT, Barwise) for the
PJ301M-12 jack, the Bread Modular pot library (benjiaomodular, CC BY-SA 4.0) for the
RV09 pot that Bread Modular uses, and the installed KiCad stock library for the rest.
Footprints are loaded and saved natively by pcbnew (KiCad 10 format). Intentional edits:

- PJ301M-12 jack: the midi module's edits (model -> ${KIPRJMOD}/IMIX.3dshapes, two
  decorative F.SilkS arcs removed, F.CrtYd = model envelope + 0.25 mm), plus the F.SilkS
  body-outline segments (those reaching X +/-4.5) removed: in the two-column jack grid the
  outline lies on the board edge (silk_edge_clearance), and the carrier silk is hidden
  behind the panel anyway.
- RV09 pot: the Value text moves from F.SilkS to F.Fab (the upstream silk value text
  "Potentiometer_RV09" sits inside the body outline), and a nominal 3D proxy
  (${KIPRJMOD}/IMIX.3dshapes/RV09_vertical_proxy.step, tools/build_pot_model.py) is
  attached; the upstream footprint has no model. Pads, courtyard and silk are unchanged.

hardware/IMIX.pretty/PROVENANCE.json records source paths and SHA-256 of every input
and output.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
LIB = HW / 'IMIX.pretty'
MODELS = HW / 'IMIX.3dshapes'
STOCK = Path('/usr/share/kicad/footprints')

STOCK_FOOTPRINTS = [
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_1206_3216Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
]

# name -> (step file, courtyard half-width X, courtyard Y top, courtyard Y bottom); as midi
JACKS = {
    'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical': ('PJ301M-12.step', 4.75, -6.25, 7.80),
}
POT = 'Potentiometer_RV09'
POT_MODEL = 'RV09_vertical_proxy.step'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    """Host-neutral provenance path (~ for the home directory)."""
    return str(path).replace(str(Path.home()), '~', 1)


def mm(v):
    return pcbnew.FromMM(v)


def set_model(fp, filename):
    models = fp.Models()
    keep = pcbnew.FP_3DMODEL()
    keep.m_Filename = filename
    models.clear()
    models.push_back(keep)


def fix_jack(fp, step, hx, ytop, ybot):
    for item in list(fp.GraphicalItems()):
        silk = item.GetLayer() == pcbnew.F_SilkS and item.GetClass() == 'PCB_SHAPE'
        is_ring = silk and item.GetShape() == pcbnew.SHAPE_T_ARC
        is_outline = (silk and item.GetShape() == pcbnew.SHAPE_T_SEGMENT and
                      max(abs(pcbnew.ToMM(item.GetStart().x)), abs(pcbnew.ToMM(item.GetEnd().x))) >= 4.4)
        if item.GetLayer() == pcbnew.F_CrtYd or is_ring or is_outline:
            fp.Delete(item)
    rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    rect.SetLayer(pcbnew.F_CrtYd)
    rect.SetWidth(mm(0.05))
    rect.SetStart(pcbnew.VECTOR2I(mm(-hx), mm(ytop)))
    rect.SetEnd(pcbnew.VECTOR2I(mm(hx), mm(ybot)))
    fp.Add(rect)
    rect.thisown = 0  # the footprint owns it now
    set_model(fp, '${KIPRJMOD}/IMIX.3dshapes/' + step)


def fix_pot(fp):
    fp.Value().SetLayer(pcbnew.F_Fab)
    set_model(fp, '${KIPRJMOD}/IMIX.3dshapes/' + POT_MODEL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bread-modular', default=str(Path.home() / 'data/projects/bread-modular'))
    args = ap.parse_args()
    bm = Path(args.bread_modular)
    jacks = bm / 'opt/AudioJacks'
    pots = bm / 'opt/footprints/BreadModular_Pots.pretty'
    assert (MODELS / POT_MODEL).is_file(), 'run tools/build_pot_model.py first'
    LIB.mkdir(exist_ok=True)
    for old in LIB.glob('*.kicad_mod'):
        old.unlink()
    MODELS.mkdir(exist_ok=True)
    record = {'footprints': {}, 'models': {}}
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    for lib, name in STOCK_FOOTPRINTS:
        src = STOCK / f'{lib}.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID('IMIX', name))
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'KiCad library CC-BY-SA-4.0-with-exception',
                                      'edits': 'none (native load/save only)'}
    for name, (step, hx, ytop, ybot) in JACKS.items():
        src = jacks / 'AudioJacks.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID('IMIX', name))
        fix_jack(fp, step, hx, ytop, ybot)
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {
            'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2021 Barwise',
            'edits': 'removed two decorative F.SilkS arcs crossing the TN/R pad and the F.SilkS '
                     'body-outline segments reaching X +/-4.5 (on the board edge in the jack grid); '
                     f'F.CrtYd -> X +/-{hx}, Y {ytop}..{ybot} (model envelope +0.25); '
                     f'3D model -> ${{KIPRJMOD}}/IMIX.3dshapes/{step}'}
        model_src = jacks / 'AudioJacks.3dshapes' / step
        shutil.copyfile(model_src, MODELS / step)
        record['models'][step] = {'source': rel(model_src), 'sha256': sha(model_src),
                                  'license': 'MIT (c) 2021 Barwise'}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')
    src = pots / f'{POT}.kicad_mod'
    fp = io.FootprintLoad(str(pots), POT)
    fp.SetFPID(pcbnew.LIB_ID('IMIX', POT))
    fix_pot(fp)
    io.FootprintSave(str(LIB), fp)
    record['footprints'][POT] = {
        'source': rel(src), 'source_sha256': sha(src),
        'license': 'CC BY-SA 4.0 (benjiaomodular KiCad libraries, via Bread Modular opt/footprints)',
        'edits': 'Value text F.SilkS -> F.Fab; 3D model -> ${KIPRJMOD}/IMIX.3dshapes/' + POT_MODEL +
                 ' (nominal proxy, tools/build_pot_model.py); pads/courtyard/silk unchanged'}
    record['models'][POT_MODEL] = {'source': 'tools/build_pot_model.py (generated nominal proxy)',
                                   'sha256': sha(MODELS / POT_MODEL), 'license': 'project'}
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
