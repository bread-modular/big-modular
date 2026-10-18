# 3D-printed front panel (no labels)

`usb-power-front-panel.stl` is the print file; `.step` and the editable `.FCStd`
come from `build_front_panel.py` (see `../README.md`). Same outline, holes and
USB aperture as `../front-pcb/usb-power-panel.kicad_pcb`, with no legend:

| Feature | Panel X,Y (origin upper left) | Size mm |
|---|---|---|
| Outline | 0,0 | 9.8 x 128.5 x 1.6 |
| H1/H2 rail holes | 2.42,3 / 2.42,125.5 | Ø3.2 |
| H3/H4 bracket holes | 6.4,22 / 6.4,106.5 | Ø3.2 |
| USB aperture | 3.3,28.1 | 5.0 x 10.8, R0.6 |
| H5 LED (D10) | 6.1,43 | Ø3.6 |
| H6 SW1 retry | 5.8,49.5 | Ø3.2 |

CAD frame: X across, CAD Y = 128.5 - panel Y, Z0..1.6 with +Z as the panel
front; all cuts go through, so either face can go on the bed (front face down
gives the cleanest front).

- Thickness stays 1.6 mm on purpose: the bracket foot seats on the panel rear at
  Z1.6, and the USB mouth recess and SW1 button depth (0.45 mm behind the rear)
  are budgeted for it. A thicker print moves the front face outward and changes
  those depths.
- Holes are nominal with no print compensation; drill/ream Ø3.2/Ø3.6 and check
  the USB aperture against the plug after printing.
- Suggested: PETG/ABS, 100% infill or 4+ perimeters, 0.2 mm layers.
