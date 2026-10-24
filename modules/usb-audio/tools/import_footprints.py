"""Import the pinned USB-AUDIO footprints into hardware/USBAUDIO.pretty (one-time, reviewable).

The library is rebuilt from scratch: footprints no longer listed are removed. Both projects
(carrier usb-audio and usb-audio-mcu) use it.

Run from modules/usb-audio with KiCad's Python (pcbnew 10):
  python3 -B tools/import_footprints.py [--bread-modular ~/data/projects/bread-modular]

Sources are read-only:
- the Bread Modular AudioJacks library (MIT, Barwise) for the PJ301M-12 jack, with the same two
  edits as modules/8bit and modules/32bit;
- Bread Modular footprints, copper unedited (preferred: the user's builds prove them): the RV09
  pot (audio-out RV09 proxy model) and the K2-1808SN-A4SW-01 BOOT/RESET switches (courtyard
  added, pad-overlapping silk removed), as modules/32bit;
- the installed KiCad stock library for everything else, unedited;
- one footprint drawn here from the manufacturer drawing: the HRO TYPE-C-31-D-15 vertical USB-C
  (recommended PCB layout, docs/research.md section 5), with the proxy model from
  tools/make_usbc_model.py.

hardware/USBAUDIO.pretty/PROVENANCE.json records source paths and SHA-256 of every input
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
LIBNAME = 'USBAUDIO'

STOCK_FOOTPRINTS = [
    ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm'),
    ('Package_SO', 'SOIC-14_3.9x8.7mm_P1.27mm'),
    ('Package_SO', 'TSSOP-24_4.4x7.8mm_P0.65mm'),
    ('Package_QFP', 'LQFP-64_10x10mm_P0.5mm'),
    ('Package_TO_SOT_SMD', 'SOT-223-3_TabPin2'),
    ('Package_TO_SOT_SMD', 'SOT-23-6'),
    ('Diode_SMD', 'D_SOD-123'),
    ('Oscillator', 'Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm'),
    ('Crystal', 'Crystal_SMD_5032-2Pin_5.0x3.2mm'),
    ('Resistor_SMD', 'R_0402_1005Metric'),
    ('Resistor_SMD', 'R_0603_1608Metric'),
    ('Resistor_SMD', 'R_1206_3216Metric'),
    ('Resistor_SMD', 'R_2512_6332Metric'),
    ('Capacitor_SMD', 'C_0402_1005Metric'),
    ('Capacitor_SMD', 'C_0603_1608Metric'),
    ('Capacitor_SMD', 'C_0805_2012Metric'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_2x05_P2.54mm_Vertical'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_1x10_P2.54mm_Vertical'),
    ('Connector_PinHeader_2.54mm', 'PinHeader_1x04_P2.54mm_Vertical'),
]

# Bread Modular footprints copied with unedited copper: (library dir relative to the BM repo, name)
BM_FOOTPRINTS = [
    ('modules/16bit/footprints/BreadModular_Pots.pretty', 'Potentiometer_RV09'),
    ('modules/16bit/footprints/BreadModular_MISC.pretty', 'K2-1808SN-A4SW-01'),
]

# BM footprints without a courtyard: name -> (half-width X, half-height Y) of the added F.CrtYd.
# K2-1808SN-A4SW-01: body 4.2 x 3.25 mm (LCSC C92589), pads reach X +/-2.665, Y +/-1.45.
BM_COURTYARD = {'K2-1808SN-A4SW-01': (2.95, 1.9)}

# Footprints whose plated thermal vias get the 'heatsink' fabrication property (metadata only):
# KiCad then counts the SMD part as SMD (no footprint_type_mismatch); copper is unchanged.
HEATSINK_VIAS = {}

# BM footprint -> 3D model (in USBAUDIO.3dshapes) and its recorded source.
BM_MODEL = {
    'Potentiometer_RV09': ('RV09_proxy.step', REPO / 'modules/8bit/hardware/8BIT.3dshapes/RV09_proxy.step',
                           'modules/8bit/hardware/8BIT.3dshapes/RV09_proxy.step (copy of the audio-out user-sample proxy, as modules/32bit)'),
}

# Stock footprints whose F.SilkS outline crosses their own pads (DRC silk_over_copper).
SILK_OFF_PADS = set()

# Footprints whose referenced model KiCad 10 does not ship: an explicitly recorded visual proxy
# (fit is not judged from these models).
MODEL_PROXY = {
    # KiCad 10 ships no ASE 3225 oscillator model; the same 3.2 x 2.5 mm 4-pad body as a visual proxy.
    'Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm':
        '${KICAD10_3DMODEL_DIR}/Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step',
}
MODEL_NONE = set()

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


def heatsink(fp, name):
    vias = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    assert len(vias) == HEATSINK_VIAS[name], (name, len(vias))
    for p in vias:
        p.SetProperty(pcbnew.PAD_PROP_HEATSINK)
    return f'fabrication property "heatsink" on the {len(vias)} plated thermal-via pads (metadata)'


# HRO TYPE-C-31-D-15 recommended PCB layout (drawing 2023-10-27; frame: pad columns along Y, A row at -X).
USBC = 'USB_C_Receptacle_HRO_TYPE-C-31-D-15_Vertical'
USBC_STEP = 'USB_C_HRO_TYPE-C-31-D-15_proxy.step'
USBC_A = ['A12', 'A9', 'A8', 'A7', 'A6', 'A5', 'A4', 'A1']     # top to bottom at X -1.365
USBC_B = ['B1', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B12']     # top to bottom at X +1.365


def add_pad(fp, number, kind, shape, xy, size, drill=None, layers=None):
    pad = pcbnew.PAD(fp)
    pad.SetNumber(number)
    pad.SetAttribute(kind)
    pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, shape)
    pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.VECTOR2I(mm(size[0]), mm(size[1])))
    if drill:
        pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_OBLONG if drill[0] != drill[1] else pcbnew.PAD_DRILL_SHAPE_CIRCLE)
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(drill[0]), mm(drill[1])))
    pad.SetLayerSet(layers)
    pad.SetPosition(pcbnew.VECTOR2I(mm(xy[0]), mm(xy[1])))
    fp.Add(pad)
    pad.thisown = 0
    return pad


def line(fp, layer, a, b, width):
    seg = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
    seg.SetLayer(layer)
    seg.SetWidth(mm(width))
    seg.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
    seg.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    fp.Add(seg)
    seg.thisown = 0


def hro_usbc():
    """Signal pads 1.59 x 0.50 at 1.00 pitch, columns 1.14 apart (outer 4.32); shell legs in plated
    slots (drawing 0.45 x 1.20, here a 0.50 x 1.20 slot: the JLCPCB minimum plated slot width) at
    X +/-1.43, Y +/-4.225, overlapping the corner GND pads as drawn; the two plastic pegs (0.90
    holes at (-1.50, +5.41) and (+1.50, -5.41)) share one longer plated slot with their neighbour
    leg. Body 5.00 x 12.00. Shell pads carry the 'mechanical' fabrication property."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID(LIBNAME, USBC))
    fp.SetLibDescription('HRO TYPE-C-31-D-15 USB 2.0 Type-C receptacle, vertical, 16P SMD, H = 8.8 mm '
                         '(D-15A/B/C/D: 9.3/10/10.5/12.4 mm, same land); HRO drawing 2023-10-27')
    fp.SetKeywords('USB C Type-C receptacle vertical HRO TYPE-C-31-D-15')
    fp.SetAttributes(pcbnew.FP_SMD)
    smd = pcbnew.LSET()
    for layer in (pcbnew.F_Cu, pcbnew.F_Paste, pcbnew.F_Mask):
        smd.AddLayer(layer)
    for col, x in ((USBC_A, -1.365), (USBC_B, 1.365)):
        for i, num in enumerate(col):
            add_pad(fp, num, pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_SHAPE_ROUNDRECT, (x, -3.5 + i), (1.59, 0.50), layers=smd)
    # Legs without a peg beside them: plain plated slots.
    for xy in ((-1.43, -4.225), (1.43, 4.225)):
        pad = add_pad(fp, 'SH', pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_SHAPE_OVAL, xy, (0.80, 1.50), (0.50, 1.20),
                      pcbnew.PAD.PTHMask())
        pad.SetProperty(pcbnew.PAD_PROP_MECHANICAL)
    # Leg + peg pairs: the drawing puts the 0.90 peg hole 0.14 mm past the leg slot end, closer than any
    # fab hole-to-hole rule, so each pair is one plated slot 0.95 x 2.24 mm (leg slot end -3.62 to peg
    # hole end -5.86), centred between the leg (X 1.43) and peg (X 1.50) columns.
    for xy in ((1.465, -4.74), (-1.465, 4.74)):
        pad = add_pad(fp, 'SH', pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_SHAPE_OVAL, xy, (1.25, 2.54), (0.95, 2.24),
                      pcbnew.PAD.PTHMask())
        pad.SetProperty(pcbnew.PAD_PROP_MECHANICAL)
    for a, b in (((-2.5, -6.0), (2.5, -6.0)), ((2.5, -6.0), (2.5, 6.0)), ((2.5, 6.0), (-2.5, 6.0)),
                 ((-2.5, 6.0), (-2.5, -6.0))):
        line(fp, pcbnew.F_Fab, a, b, 0.1)
    for a, b in (((-2.61, -6.11), (-2.61, 6.11)), ((2.61, -6.11), (2.61, 6.11))):
        line(fp, pcbnew.F_SilkS, a, b, 0.12)
    courtyard(fp, -2.75, -6.25, 2.75, 6.25)
    fp.Reference().SetPosition(pcbnew.VECTOR2I(0, mm(-7.2)))
    fp.Reference().SetLayer(pcbnew.F_SilkS)
    fp.Value().SetPosition(pcbnew.VECTOR2I(0, mm(7.2)))
    fp.Value().SetLayer(pcbnew.F_Fab)
    set_model(fp, USBC_STEP)
    return fp


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
        if name in MODEL_NONE:
            missing = [m.m_Filename for m in fp.Models()]
            fp.Models().clear()
            edit = f'3D model {missing} is not shipped by KiCad 10; removed (no proxy)'
        if name in HEATSINK_VIAS:
            edit = '; '.join(filter(None, [edit, heatsink(fp, name)]))
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
        if name in HEATSINK_VIAS:
            edits.append(heatsink(fp, name))
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
            model_src = model_src or bm / step
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
    io.FootprintSave(str(LIB), hro_usbc())
    record['footprints'][USBC] = {'source': 'drawn by tools/import_footprints.py from the HRO TYPE-C-31-D-15 '
                                            'drawing (recommended PCB layout)', 'source_sha256': None,
                                  'license': 'module-local', 'edits': 'plated slot width 0.45 -> 0.50 (JLCPCB minimum); peg holes merged with the adjacent leg slots (0.95 x 2.24 plated)'}
    record['models'][USBC_STEP] = {'source': 'tools/make_usbc_model.py (envelope proxy)', 'sha256': sha(MODELS / USBC_STEP)}
    shutil.copyfile(jacks / 'LICENSE', MODELS / 'LICENSE-AudioJacks-MIT.txt')
    for name in record['footprints']:
        record['footprints'][name]['output_sha256'] = sha(LIB / f'{name}.kicad_mod')
    (LIB / 'PROVENANCE.json').write_text(json.dumps(record, indent=2) + '\n')
    (hw / 'fp-lib-table').write_text(
        f'(fp_lib_table (version 7) (lib (name "{LIBNAME}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIBNAME}.pretty") '
        f'(options "") (descr "USB-AUDIO pinned footprints (both projects); see {LIBNAME}.pretty/PROVENANCE.json")))\n')
    print(json.dumps({k: sorted(v) for k, v in record.items()}, indent=2))


if __name__ == '__main__':
    main()
