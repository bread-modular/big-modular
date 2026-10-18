# usb-power panels and brackets

| Directory | Contents |
|---|---|
| `front-pcb/` | Canonical native passive front panel PCB `usb-power-panel.kicad_{pro,pcb}` (2HP, 9.8 x 128.5 x 1.6 mm). JLCPCB export lives in `../jlcpcb/passive-panel/`. |
| `front-cad/` | FreeCAD 3D-print front panel, no labels: `build_front_panel.py`, `.FCStd`, `.step`, `.stl`. |
| `bracket/` | FreeCAD 3D-print panel-to-carrier L bracket (print two): `build_bracket.py`, `.FCStd`, `.step`, `.stl`. |

The PCB panel and the printed panel are alternatives; both mount with the same
two printed brackets. Regenerate the CAD headless from `modules/usb-power`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/bracket/build_bracket.py
```

The front panel reads its outline, NPTH holes and USB aperture from
`front-pcb/usb-power-panel.kicad_pcb` and asserts them against
`docs/assembly-geometry.json`; the bracket reads the `brackets` contract from the
same file (and matches `hardware/mechanics/corner_braces.scad`). Each script
checks a single valid solid, its analytic volume (panel) or countersink
material (bracket), and a closed manifold STL. Never hand-edit the exports; edit
the source/contract and rerun. Nominal geometry only; no physical-fit, ABS/PLA
or strength qualification is claimed.
