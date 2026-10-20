"""Import the pinned 16bit footprints into hardware/16BIT.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed.

Run from modules/16bit with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only:
- the Bread Modular AudioJacks library (MIT, Barwise) for the PJ301M-12 jack, with the
  same two edits as modules/8bit (decorative F.SilkS arcs removed, F.CrtYd = model
  envelope + 0.25 mm, 3D model -> ${KIPRJMOD}/16BIT.3dshapes/PJ301M-12.step);
- Bread Modular 16bit footprints, copper unedited (Bread Modular footprints are preferred:
  the user's builds prove them): the RP2350 QFN-60 with thermal vias, the 2016 VREG
  inductor, the 0402 small-pad VREG capacitors, the PSRAM SOIC-8, and (as modules/8bit) the
  RV09 pot (audio-out RV09 proxy model) and the K2-1808SN-A4SW-01 RUN/BOOT switches (courtyard
  added, pad-overlapping silk removed);
- the installed KiCad stock library for everything else, unedited, including (as modules/8bit)
  the MODE tact switch `SW_PUSH_6mm_H7.3mm` and the 3 mm mode LED `LED_D3.0mm`. The USB-C receptacle is
  the stock HRO TYPE-C-31-M-12 (the Bread Modular part): Bread Modular's copy merges the
  VBUS/GND pads under A-numbers, which the stock 14P symbol can't map.

hardware/16BIT.pretty/PROVENANCE.json records source paths and SHA-256 of every input
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
LIBNAME = '16BIT'

STOCK_FOOTPRINTS = [
    ('LED_THT', 'LED_D3.0mm'),
    ('Button_Switch_THT', 'SW_PUSH_6mm_H7.3mm'),
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Package_SO', 'SOIC-8_5.3x5.3mm_P1.27mm'),
    ('Package_SO', 'SOIC-14_3.9x8.7mm_P1.27mm'),
    ('Package_TO_SOT_SMD', 'SOT-223-3_TabPin2'),
    ('Package_TO_SOT_SMD', 'SOT-23'),
    ('Package_TO_SOT_SMD', 'SOT-323_SC-70'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Crystal', 'Crystal_SMD_3225-4Pin_3.2x2.5mm'),
    ('Connector_USB', 'USB_C_Receptacle_HRO_TYPE-C-31-M-12'),
    ('Resistor_SMD', 'R_0402_1005Metric'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_1206_3216Metric'),
    ('Capacitor_SMD', 'C_0402_1005Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Capacitor_SMD', 'C_1206_3216Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
    ('Jumper', 'SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm'),
]

# Bread Modular footprints copied with unedited copper: (library dir relative to the BM repo, name)
BM_FOOTPRINTS = [
    ('modules/16bit/footprints/RP2350_60QFN_minimal.pretty', 'RP2350-QFN-60-1EP_7x7_P0.4mm_EP3.4x3.4mm_ThermalVias'),
    ('modules/16bit/footprints/RP2350_60QFN_minimal.pretty', 'L_pol_2016'),
    ('modules/16bit/footprints/RP2350_60QFN_minimal.pretty', 'C_0402_1005Metric_small_pads'),
    ('modules/16bit/footprints/BreadModular_MISC.pretty', 'SOIC-8 Generic'),
    ('modules/16bit/footprints/BreadModular_Pots.pretty', 'Potentiometer_RV09'),
    ('modules/16bit/footprints/BreadModular_MISC.pretty', 'K2-1808SN-A4SW-01'),
]

# BM footprints without a courtyard: name -> (half-width X, half-height Y) of the added F.CrtYd.
# K2-1808SN-A4SW-01: body 4.2 x 3.25 mm (LCSC C92589), pads reach X +/-2.665, Y +/-1.45.
BM_COURTYARD = {'K2-1808SN-A4SW-01': (2.95, 1.9)}

# BM footprints whose plated thermal vias get the 'heatsink' fabrication property (metadata only):
# KiCad then counts the SMD part as SMD (no footprint_type_mismatch); copper is unchanged.
BM_HEATSINK_VIAS = {'RP2350-QFN-60-1EP_7x7_P0.4mm_EP3.4x3.4mm_ThermalVias'}

# BM footprint -> 3D model (in 16BIT.3dshapes) and its recorded source.
BM_MODEL = {
    'Potentiometer_RV09': ('RV09_proxy.step', REPO / 'modules/8bit/hardware/8BIT.3dshapes/RV09_proxy.step',
                           'modules/8bit/hardware/8BIT.3dshapes/RV09_proxy.step (copy of the audio-out user-sample proxy)'),
    'RP2350-QFN-60-1EP_7x7_P0.4mm_EP3.4x3.4mm_ThermalVias': (
        'RP2350_QFN60.step', None, 'Bread Modular modules/16bit/RP2350_QFN60.step'),
}

# Stock footprints whose F.SilkS outline crosses their own pads (DRC silk_over_copper).
SILK_OFF_PADS = set()

# Footprints whose referenced model KiCad 10 does not ship: an explicitly recorded visual proxy
# (fit is not judged from these models).
MODEL_PROXY = {
    'C_0402_1005Metric_small_pads': '${KICAD10_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0402_1005Metric.step',
    'L_pol_2016': '${KICAD10_3DMODEL_DIR}/Inductor_SMD.3dshapes/L_Cenker_CKCS201610.step',
    'USB_C_Receptacle_HRO_TYPE-C-31-M-12':
        '${KICAD10_3DMODEL_DIR}/Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step',
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


def proxy_model(fp, name):
    """Swap a missing model for its recorded proxy; returns the edit note or None."""
    if name not in MODEL_PROXY:
        return None
    models = fp.Models()
    model = models[0]
    missing = model.m_Filename
    model.m_Filename = MODEL_PROXY[name]
    models[0] = model
    return f'3D model {missing} is not shipped by KiCad 10; visual proxy {MODEL_PROXY[name]}'


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
        edit = proxy_model(fp, name)
        if name in SILK_OFF_PADS:
            # F.SilkS outline items that cross the pads (the LED sits under the panel, no silk visible)
            pads = [p.GetBoundingBox() for p in fp.Pads()]
            gone = [i for i in fp.GraphicalItems() if i.GetLayer() == pcbnew.F_SilkS
                    and any(i.GetBoundingBox().Intersects(b) for b in pads)]
            for item in gone:
                fp.Delete(item)
            edit = f'removed {len(gone)} F.SilkS outline item(s) crossing the pads'
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'KiCad library CC-BY-SA-4.0-with-exception',
                                      'edits': edit or 'none (native load/save only)'}
    for libdir, name in BM_FOOTPRINTS:
        src = bm / libdir / f'{name}.kicad_mod'
        fp = io.FootprintLoad(str(src.parent), name)
        fp.SetFPID(pcbnew.LIB_ID(LIBNAME, name))
        edits = ['copper unedited']
        proxy = proxy_model(fp, name)
        if proxy:
            edits.append(proxy)
        if name in BM_HEATSINK_VIAS:
            vias = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
            assert len(vias) == 9, len(vias)
            for p in vias:
                p.SetProperty(pcbnew.PAD_PROP_HEATSINK)
            edits.append(f'fabrication property "heatsink" on the {len(vias)} plated thermal-via pads (metadata)')
        if name in BM_COURTYARD:
            hx, hy = BM_COURTYARD[name]
            assert not any(i.GetLayer() == pcbnew.F_CrtYd for i in fp.GraphicalItems())
            silk = [i for i in fp.GraphicalItems() if i.GetLayer() == pcbnew.F_SilkS]
            assert len(silk) == 4, len(silk)
            for item in silk:
                fp.Delete(item)
            courtyard(fp, -hx, -hy, hx, hy)
            edits.append(f'added F.CrtYd X +/-{hx}, Y +/-{hy} (upstream has none); removed the 4 F.SilkS '
                         'body lines that overlap its pads')
        if name in BM_MODEL:
            step, model_src, origin = BM_MODEL[name]
            model_src = model_src or bm / 'modules/16bit' / step
            shutil.copyfile(model_src, MODELS / step)
            set_model(fp, step)
            edits.append(f'3D model -> ${{KIPRJMOD}}/{LIBNAME}.3dshapes/{step}')
            record['models'][step] = {'source': origin, 'sha256': sha(MODELS / step)}
        io.FootprintSave(str(LIB), fp)
        record['footprints'][name] = {'source': rel(src), 'source_sha256': sha(src),
                                      'license': 'MIT (c) 2024 Arunoda Susiripala (Bread Modular LICENSE)',
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
        f'(options "") (descr "16bit module pinned footprints; see {LIBNAME}.pretty/PROVENANCE.json")))\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
