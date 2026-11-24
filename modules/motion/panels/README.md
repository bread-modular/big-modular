# motion panels (6HP)

| Directory | Contents |
|---|---|
| `front-pcb/` | Native passive FR4 panel `motion-panel.kicad_{pro,pcb}`: 30.0 x 128.5 x 1.6 mm, NPTH only, F.SilkS labels |
| `front-cad/` | FreeCAD printable panel, 2.0 mm thick, plain (no labels): `build_front_panel.py`, `.FCStd`, `.step`, `.stl` |
| `top-clip/` | Printed top clip (C1, 2026-11-24) that holds the carrier top edge to the panel with one M3 screw: `build_top_clip.py` (FreeCAD), `check_top_clip.py` (KiCad Python, against the routed carrier and the FR4 panel), `render_section.py` (`../docs/fit/top-clip-section.png`), `.FCStd`, `.step` (assembly frame), `.stl` (print orientation) |

The two panels are alternatives with the same holes: jacks Ø6.2, pots Ø7.2, LEDs Ø3.2, REC / RANGE buttons Ø4.2 (modules/8bit printed cap, 1.5 mm proud of the print), rail holes Ø3.2 at X12.58, and (P2, 2026-11-24) the top-clip screw hole Ø3.2 at X25.0 / Y12.0. Either one mounts on the
jack bushings with the PJ301M-12 nuts plus the rail screws; the RV09 pots take no nut.

## Top clip (`top-clip/`)

All four jacks sit in the bottom 25 mm and the pots have no bushing or nut, so without it
nothing holds the upper 85 mm of the carrier: the top end flexes away when a knob is
pressed and the shafts wander in their holes. The clip is a C channel along the carrier
top edge (X5..29): its shoulder rests on the F face and its nose hooks the B face, both
inside the 1 mm edge keep-out strip (no copper, no parts), and its back stays 0.2 mm off
the skiff rail. A boss at the right end reaches the panel rear and takes the screw.

- Hardware: one M3x6 or M3x8 button-head machine screw (M3x10 at most; the blind hole
  stops it 1.4 mm above the carrier); it cuts its own thread in the Ø2.6 hole.
- Assembly: slide the clip onto the carrier top edge from the right end, fit the panel,
  tighten the jack nuts, then drive the screw from the front at the hole right of `MOTION`.
- Print: PLA or PETG, standing on its right end (the boss end on the bed), 0.2 mm layers,
  no support (OrcaSlicer 2.4.2 P2S CLI slice 2026-11-24: 120 layers, 0.84 g, ~25 min, no
  support). Not test-printed: the fit relies on the nominal jack stack (panel rear 10.0 mm
  above the carrier F face); measure it on a built board before printing.

Regenerate from `modules/motion`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/top-clip/build_top_clip.py
python3 -B panels/top-clip/check_top_clip.py
python3 -B panels/top-clip/render_section.py
```

Regenerate the printed panel headless from `modules/motion`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
```

The script reads the outline and holes from `front-pcb/motion-panel.kicad_pcb` and asserts them
against `docs/geometry.json`; it checks a single valid solid, the drilled-blank volume and a
closed manifold STL. Print suggestion: PETG/ABS, front face down, 0.2 mm layers. Holes are
nominal: ream after printing. LED domes sit 0.4 mm behind the print front. Not test-printed; no physical-fit claim.
