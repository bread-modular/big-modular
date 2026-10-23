"""Import the pinned 4MIX footprints into hardware/4MIX.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed.

Run from modules/4mix with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only:
- the Bread Modular AudioJacks library (MIT, Barwise) for the PJ301M-12 jack, with the
  modules/32bit edits (decorative F.SilkS arcs removed, F.CrtYd = model envelope + 0.25 mm,
  3D model -> ${KIPRJMOD}/4MIX.3dshapes/PJ301M-12.step);
- the Bread Modular RV09 pot (the one 4mix uses), copper unedited, with the modules/32bit
  RV09 proxy model (copy of the audio-out user-sample proxy) attached;
- the installed KiCad stock library for everything else, unedited.

hardware/4MIX.pretty/PROVENANCE.json records source paths and SHA-256 of every input
and output.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pcbnew

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
STOCK = Path('/usr/share/kicad/footprints')
LIBNAME = '4MIX'

STOCK_FOOTPRINTS = [
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_2512_6332Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x03_P2.54mm_Vertical'),
]

# Bread Modular footprints copied with unedited copper: (library dir relative to the BM repo, name)
BM_FOOTPRINTS = [
    ('opt/footprints/BreadModular_Pots.pretty', 'Potentiometer_RV09'),
]

# BM footprint -> 3D model (in 4MIX.3dshapes) and its recorded source.
BM_MODEL = {
    'Potentiometer_RV09': ('RV09_proxy.step', REPO / 'modules/32bit/hardware/32BIT.3dshapes/RV09_proxy.step',
                           'modules/32bit/hardware/32BIT.3dshapes/RV09_proxy.step (copy of the audio-out user-sample proxy)'),
}

# name -> (step file, courtyard half-width X, courtyard Y top, courtyard Y bottom)
JACKS = {
    'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical': ('PJ301M-12.step', 4.75, -6.25, 7.80),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    """Host-neutral provenance path (~ for the home directory)."""
    return str(path).replace(str(Path.home()), '~', 1)


def mm(v):
    return pcbnew.FromMM(v)


def courtyard(fp, x0, y0, x1, y1):
    rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    rect.SetLayer(pcbnew.F_CrtYd)
    rect.SetWidth(mm(0.05))
    rect.SetStart(pcbnew.VECTOR2I(mm(x0), mm(y0)))
    rect.SetEnd(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    fp.Add(rect)
    rect.thisown = 0  # the footprint owns it now


def set_model(fp, step):
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = f'${{KIPRJMOD}}/{LIBNAME}.3dshapes/' + step
    fp.Models().clear()
    fp.Models().push_back(model)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bread-modular', default=str(Path.home() / 'data/projects/bread-modular'))
    args = ap.parse_args()
    bm = Path(args.bread_modular)
    hw = MODULE / 'hardware'
    LIB, MODELS = hw / f'{LIBNAME}.pretty', hw / f'{LIBNAME}.3dshapes'
    jacks = bm / 'opt/AudioJacks'
    LIB.mkdir(exist_ok=True)
    for old in LIB.glob('*.kicad_mod'):
        old.unlink()
    MODELS.mkdir(exist_ok=True)
    record = {'footprints': {}, 'models': {}}
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    for lib, name in STOCK_FOOTPRINTS:
        src = STOCK / f'{lib}.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'KiCad library CC-BY-SA-4.0-with-exception',
                                      'edits': 'none (native load/save only)'}
    for libdir, name in BM_FOOTPRINTS:
        src = bm / libdir / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
        edits = ['copper unedited']
        if name in BM_MODEL:
            step, model_src, origin = BM_MODEL[name]
            shutil.copyfile(model_src, MODELS / step)
            set_model(fp, step)
            edits.append(f'3D model -> ${{KIPRJMOD}}/{LIBNAME}.3dshapes/{step}')
            record['models'][step] = {'source': origin, 'sha256': sha(MODELS / step)}
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'CC BY-SA 4.0 (benjiaomodular KiCad libraries, via Bread Modular opt/footprints)',
                                      'edits': '; '.join(edits)}
    for name, (step, hx, ytop, ybot) in JACKS.items():
        src = jacks / 'AudioJacks.pretty' / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
        for item in list(fp.GraphicalItems()):
            is_ring = (item.GetLayer() == pcbnew.F_SilkS and item.GetClass() == 'PCB_SHAPE'
                       and item.GetShape() == pcbnew.SHAPE_T_ARC)
            if item.GetLayer() == pcbnew.F_CrtYd or is_ring:
                fp.Delete(item)
        courtyard(fp, -hx, ytop, hx, ybot)
        set_model(fp, step)
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {
            'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2021 Barwise',
            'edits': 'removed two decorative F.SilkS arcs crossing the TN/R pad; '
                     f'F.CrtYd -> X +/-{hx}, Y {ytop}..{ybot} (model envelope +0.25); '
                     f'3D model -> ${{KIPRJMOD}}/{LIBNAME}.3dshapes/{step}'}
        model_src = jacks / 'AudioJacks.3dshapes' / step
        shutil.copyfile(model_src, MODELS / step)
        record['models'][step] = {'source': rel(model_src), 'sha256': sha(model_src),
                                  'license': 'MIT (c) 2021 Barwise'}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    (hw / 'fp-lib-table').write_text(
        f'(fp_lib_table (version 7) (lib (name "{LIBNAME}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIBNAME}.pretty") '
        f'(options "") (descr "4MIX module pinned footprints; see {LIBNAME}.pretty/PROVENANCE.json")))\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
