"""Import the pinned ACID footprints into hardware/ACID.pretty (one-time, reviewable).

Run from modules/acid with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only, as modules/vca-mix: the Bread Modular AudioJacks library (MIT,
Barwise) for the jack, the benjiaomodular library that Bread Modular uses for its RV09
pots (CC-BY-SA 4.0), the Bread Modular MISC library (MIT) for the VTL5C vactrol and the
installed KiCad stock library for everything else. Footprints are loaded and saved
natively by pcbnew, so the copies are KiCad 10 format. The only intentional edits:

- PJ301M-12 jack: exactly the MIDI / VCA-MIX edits (3D model -> ${KIPRJMOD}/ACID.3dshapes,
  the two decorative F.SilkS arcs over the TN pad removed, F.CrtYd -> model envelope
  + 0.25 mm);
- VTL5C: the Bread Modular footprint as is, plus the VCA-MIX F.CrtYd (silk box + 0.25 mm)
  and two build-note silk lines inside the box (SOLDER FIRST / TRIM FLUSH);
- RV09: copper unedited; 3D model -> the user-sample RV09 proxy of modules/8bit
  (ACID.3dshapes/RV09_proxy.step);
- VQFN-20: the recorded 3D-model proxy of modules/8bit (KiCad ships no VQFN-20 3x3 model).

The STEP files are copied byte-exactly. hardware/ACID.pretty/PROVENANCE.json records
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
LIB = HW / 'ACID.pretty'
MODELS = HW / 'ACID.3dshapes'
STOCK = Path('/usr/share/kicad/footprints')

STOCK_FOOTPRINTS = [
    ('Package_DFN_QFN', 'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm'),
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Package_SO', 'TSSOP-10_3x3mm_P0.5mm'),
    ('Package_TO_SOT_SMD', 'SOT-89-3'),
    ('Package_TO_SOT_SMD', 'SOT-23'),
    ('Package_TO_SOT_SMD', 'SOT-323_SC-70'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_1206_3216Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Capacitor_SMD', 'C_1206_3216Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_1x02_P2.54mm_Vertical'),
    ('Jumper', 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm'),
    ('LED_THT', 'LED_D3.0mm'),                   # mode / record LEDs, as modules/8bit
    ('Button_Switch_THT', 'SW_PUSH_6mm_H7.3mm'), # MODE / REC tact switches, as modules/8bit
]

# The stock footprint references a model KiCad does not ship; the only shipped 3x3 mm
# 20-pin P0.4 body (UQFN) is the recorded visual proxy, as modules/8bit.
MODEL_PROXY = {
    'VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm':
        '${KICAD10_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm.step',
}
REPO = MODULE.parents[1]
POT_MODEL = ('RV09_proxy.step', REPO / 'modules/8bit/hardware/8BIT.3dshapes/RV09_proxy.step')

# name -> (step file, courtyard half-width X, courtyard Y top, courtyard Y bottom)
JACKS = {
    'Jack_3.5mm_QingPu_WQP-PJ301M-12_Vertical': ('PJ301M-12.step', 4.75, -6.25, 7.80),
}

POT = 'Potentiometer_RV09'
VACTROL = 'VTL5C'
VACTROL_CRTYD = (5.38, 7.92)  # half-width X, half-height Y: BM silk box outer edge + 0.25
# Build notes inside the body box (as modules/vca-mix, without its LED current line):
# (local Y, text); 0.8 mm font = the project minimum.
VACTROL_NOTES = [(4.4, 'SOLDER FIRST'), (3.1, 'TRIM FLUSH')]
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
    keep.m_Filename = '${KIPRJMOD}/ACID.3dshapes/' + step
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
        fp.SetFPID(pcbnew.LIB_ID('ACID', src.stem))
        return fp

    for lib, name in STOCK_FOOTPRINTS:
        src = STOCK / f'{lib}.pretty' / f'{name}.kicad_mod'
        fp = load(src)
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
        fp = load(src)
        fix_jack(fp, step, hx, ytop, ybot)
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {
            'source': rel(src), 'source_sha256': sha(src), 'license': 'MIT (c) 2021 Barwise',
            'edits': 'removed two decorative F.SilkS arcs crossing the TN pad; '
                     f'F.CrtYd -> X +/-{hx}, Y {ytop}..{ybot} (model envelope +0.25); '
                     f'3D model -> ${{KIPRJMOD}}/ACID.3dshapes/{step}'}
        model_src = jacks / 'AudioJacks.3dshapes' / step
        shutil.copyfile(model_src, MODELS / step)
        record['models'][step] = {'source': rel(model_src), 'sha256': sha(model_src),
                                  'license': 'MIT (c) 2021 Barwise'}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')

    src = bm / 'KiCadLibraries/benjiaomodular.pretty' / f'{POT}.kicad_mod'
    fp = load(src)
    step, model_src = POT_MODEL
    shutil.copyfile(model_src, MODELS / step)
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = '${KIPRJMOD}/ACID.3dshapes/' + step
    fp.Models().clear()
    fp.Models().push_back(model)
    io.FootprintSave(str(LIB), fp)
    record['footprints'][POT] = {'source': rel(src), 'source_sha256': sha(src),
                                 'license': 'CC-BY-SA-4.0 (benjiaomodular KiCad libraries)',
                                 'edits': f'copper unedited; 3D model -> ${{KIPRJMOD}}/ACID.3dshapes/{step} '
                                          '(upstream has none)'}
    record['models'][step] = {'source': 'modules/8bit/hardware/8BIT.3dshapes/RV09_proxy.step (user pot sample '
                                        'proxy from modules/audio-out/tools/make_pot_model.py)',
                              'sha256': sha(model_src), 'license': 'Big Modular (this repository)'}
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
    (HW / 'fp-lib-table').write_text(
        '(fp_lib_table (version 7) (lib (name "ACID") (type "KiCad") (uri "${KIPRJMOD}/ACID.pretty") '
        '(options "") (descr "ACID pinned footprints; see ACID.pretty/PROVENANCE.json")))\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
