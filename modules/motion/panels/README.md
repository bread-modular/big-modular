# motion panels (6HP)

| Directory | Contents |
|---|---|
| `front-pcb/` | Native passive FR4 panel `motion-panel.kicad_{pro,pcb}`: 30.0 x 128.5 x 1.6 mm, NPTH only, F.SilkS labels |
| `front-cad/` | FreeCAD printable panel, 2.0 mm thick, plain (no labels): `build_front_panel.py`, `.FCStd`, `.step`, `.stl` |

The two panels are alternatives with the same holes: jacks Ø6.2, pots Ø7.2, LEDs Ø3.2, REC / RANGE buttons Ø4.2 (modules/8bit printed cap, 1.5 mm proud of the print), rail holes Ø3.2 at X12.58. Either one mounts on the
jack bushings with the PJ301M-12 nuts plus the rail screws; the RV09 pots take no nut.

Regenerate the printed panel headless from `modules/motion`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
```

The script reads the outline and holes from `front-pcb/motion-panel.kicad_pcb` and asserts them
against `docs/geometry.json`; it checks a single valid solid, the drilled-blank volume and a
closed manifold STL. Print suggestion: PETG/ABS, front face down, 0.2 mm layers. Holes are
nominal: ream after printing. LED domes sit 0.4 mm behind the print front. Not test-printed; no physical-fit claim.
