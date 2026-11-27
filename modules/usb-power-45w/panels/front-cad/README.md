# 3D-printed front panel (no labels)

`usb-power-45w-front-panel.stl` is the print file; `.step` and the editable `.FCStd`
come from `build_front_panel.py`. Same outline, holes and USB aperture as
`../front-pcb/usb-power-45w-panel.kicad_pcb`, with no legend. It is an alternative to
the FR4 panel and mounts with the same two printed brackets (`../bracket/`).

| Feature | Panel X,Y (origin upper left) | Size mm |
|---|---|---|
| Outline | 0,0 | 20.0 x 128.5 x 1.6 (4HP) |
| H1/H2 rail holes | 12.58,3 / 12.58,125.5 | Ø3.2 |
| H3/H4 bracket holes | 6.4,22 / 6.4,106.5 | Ø3.2 |
| USB aperture | 3.3,28.1 | 5.0 x 10.8, R0.6 |
| H5 MAIN LED (D8) | 6.1,43 | Ø3.6 |
| H6 SW1 RESET | 5.8,69 | Ø3.2 |

Regenerate headless from `modules/usb-power-45w`:

```sh
freecadcmd panels/front-cad/build_front_panel.py
```

The script reads the outline, NPTH holes and USB aperture from the FR4 panel PCB and
asserts them against `docs/mechanical-geometry.json`; it checks a single valid solid,
its analytic volume and a closed manifold STL. Never hand-edit the exports.

CAD frame: X across, CAD Y = 128.5 - panel Y, Z0..1.6 with +Z as the panel front; all
cuts go through, so either face can go on the bed (front face down gives the cleanest
front).

- Thickness stays 1.6 mm on purpose (as `modules/usb-power`): the bracket foot seats
  on the panel rear at Z1.6, and the USB mouth and SW1 RESET depth are budgeted for
  it. A thicker print moves the front face outward and changes those depths.
- Holes are nominal with no print compensation; drill/ream Ø3.2/Ø3.6 and check the
  USB aperture against the plug after printing.
- Suggested: PETG/ABS, 100% infill or 4+ perimeters, 0.2 mm layers.
- Not test-printed; nominal geometry only, no physical-fit or strength claim.
