"""Generate the HRO TYPE-C-31-D-15 vertical USB-C proxy model (hardware/USBAUDIO.3dshapes/).

Run headless from modules/usb-audio:
  ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd tools/make_usbc_model.py

Envelope from the HRO drawing (TYPE-C-31-D-15, 2023-10-27, docs/research.md section 5): plastic
base 12.00 x 5.00 mm, 2.10 mm tall; metal shell 8.94 x 3.16 mm (stadium) to H = 8.8 mm above the
PCB; mouth 8.34 x 2.56 mm, 6.2 mm deep (USB-C receptacle reference depth). Footprint frame: the
pad columns run along Y, so the shell's long axis is Y. Not a manufacturer model.
"""
from pathlib import Path

import FreeCAD as App
import Part

MODULE = Path(__file__).resolve().parents[1]
H = 8.8


def stadium(length, width, height, z0=0.0):
    """Stadium (obround) prism, long axis Y, centred on the origin."""
    r = width / 2
    box = Part.makeBox(width, length - width, height, App.Vector(-r, -(length - width) / 2, z0))
    c1 = Part.makeCylinder(r, height, App.Vector(0, (length - width) / 2, z0))
    c2 = Part.makeCylinder(r, height, App.Vector(0, -(length - width) / 2, z0))
    return box.fuse([c1, c2]).removeSplitter()


def build():
    base = Part.makeBox(5.0, 12.0, 2.1, App.Vector(-2.5, -6.0, 0))
    shell = stadium(8.94, 3.16, H - 2.1, 2.1).cut(stadium(8.34, 2.56, 6.2, H - 6.2))
    tongue = Part.makeBox(0.7, 6.69, 4.45, App.Vector(-0.35, -3.345, H - 6.2))
    shape = base.fuse([shell, tongue]).removeSplitter()
    out = MODULE / 'hardware/USBAUDIO.3dshapes/USB_C_HRO_TYPE-C-31-D-15_proxy.step'
    out.parent.mkdir(parents=True, exist_ok=True)
    shape.exportStep(str(out))
    print(out, round(shape.BoundBox.ZMax, 3))


build()
