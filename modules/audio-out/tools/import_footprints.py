"""Import the pinned audio-out footprints into hardware/AudioOut.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed.

Run from modules/audio-out with KiCad's Python (pcbnew 10), after tools/make_pot_model.py:
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only: the Bread Modular AudioJacks library (MIT, Barwise) for the
two jacks, the Bread Modular pot footprint (opt/footprints/BreadModular_Pots.pretty,
MIT) for the RV09 volume pots, and the installed KiCad stock library for everything
else. Footprints are loaded and saved natively by pcbnew, so the copies are KiCad 10
format. The intentional edits are:

- jacks (same as modules/midi): 3D model -> ${KIPRJMOD}/AudioOut.3dshapes/<jack>.step;
  the two decorative F.SilkS arcs (R2.895) removed (they cross the TN/R pad);
  F.CrtYd -> the STEP model envelope + 0.25 mm;
- pot: the Value text moves from F.SilkS to F.Fab (it overlaps the pads) and the
  footprint gets the generated RV09 proxy model ${KIPRJMOD}/AudioOut.3dshapes/RV09_proxy.step
  (the Bread Modular footprint has none; see tools/make_pot_model.py).

The jack STEP files are copied byte-exactly. hardware/AudioOut.pretty/PROVENANCE.json
records source paths and SHA-256 of every input and output.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
HW = MODULE / 'hardware'
LIB = HW / 'AudioOut.pretty'
MODELS = HW / 'AudioOut.3dshapes'
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

# name -> (step file, courtyard half-width X, courtyard Y top, courtyard Y bottom)
JACKS = {
    'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical': ('PJ301M-12.step', 4.75, -6.25, 7.80),
    'Jack_3.5mm_QingPu_WQP-PJ366ST_Vertical': ('PJ366ST.step', 5.25, -6.25, 7.80),
}

POT = 'Potentiometer_RV09'
POT_MODEL = 'RV09_proxy.step'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    """Host-neutral provenance path (~ for the home directory)."""
    return str(path).replace(str(Path.home()), '~', 1)


def mm(v):
    return pcbnew.FromMM(v)


def set_model(fp, step):
    models = fp.Models()
    keep = pcbnew.FP_3DMODEL()
    keep.m_Filename = '${KIPRJMOD}/AudioOut.3dshapes/' + step
    models.clear()
    models.push_back(keep)


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
    set_model(fp, step)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bread-modular', default=str(Path.home() / 'data/projects/bread-modular'))
    args = ap.parse_args()
    bm = Path(args.bread_modular)
    jacks = bm / 'opt/AudioJacks'
    pots = bm / 'opt/footprints/BreadModular_Pots.pretty'
    assert (MODELS / POT_MODEL).is_file(), 'run tools/make_pot_model.py first'
    LIB.mkdir(exist_ok=True)
    for old in LIB.glob('*.kicad_mod'):
        old.unlink()
    record = {'footprints': {}, 'models': {}}
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    for lib, name in STOCK_FOOTPRINTS:
        src = STOCK / f'{lib}.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID('AudioOut', name))
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'KiCad library CC-BY-SA-4.0-with-exception',
                                      'edits': 'none (native load/save only)'}
    for name, (step, hx, ytop, ybot) in JACKS.items():
        src = jacks / 'AudioJacks.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID('AudioOut', name))
        fix_jack(fp, step, hx, ytop, ybot)
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {
            'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2021 Barwise',
            'edits': 'removed two decorative F.SilkS arcs crossing the TN/R pad; '
                     f'F.CrtYd -> X +/-{hx}, Y {ytop}..{ybot} (model envelope +0.25); '
                     f'3D model -> ${{KIPRJMOD}}/AudioOut.3dshapes/{step}'}
        model_src = jacks / 'AudioJacks.3dshapes' / step
        shutil.copyfile(model_src, MODELS / step)
        record['models'][step] = {'source': rel(model_src), 'sha256': sha(model_src),
                                  'license': 'MIT (c) 2021 Barwise'}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')
    src = pots / f'{POT}.kicad_mod'
    fp = io.FootprintLoad(str(pots), POT)
    fp.SetFPID(pcbnew.LIB_ID('AudioOut', POT))
    fp.Value().SetLayer(pcbnew.F_Fab)
    set_model(fp, POT_MODEL)
    io.FootprintSave(str(LIB), fp)
    record['footprints'][POT] = {
        'source': rel(src), 'source_sha256': sha(src),
        'license': 'MIT (c) 2024 Arunoda Susiripala (Bread Modular)',
        'edits': f'Value text F.SilkS -> F.Fab; 3D model (none upstream) -> '
                 f'${{KIPRJMOD}}/AudioOut.3dshapes/{POT_MODEL} (generated nominal proxy)'}
    record['models'][POT_MODEL] = {'source': 'tools/make_pot_model.py (generated)',
                                   'sha256': sha(MODELS / POT_MODEL),
                                   'license': 'generated in this repository'}
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    (HW / 'fp-lib-table').write_text(
        '(fp_lib_table (version 7) (lib (name "AudioOut") (type "KiCad") (uri "${KIPRJMOD}/AudioOut.pretty") '
        '(options "") (descr "audio-out module pinned footprints; see AudioOut.pretty/PROVENANCE.json")))\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
