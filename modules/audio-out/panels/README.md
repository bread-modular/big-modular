# audio-out panels (4HP)

| Directory | Contents |
|---|---|
| `front-pcb/` | Native passive FR4 panel `audio-out-panel.kicad_{pro,pcb}`, 1.6 mm, NPTH only, F.SilkS labels |
| `front-cad/` | FreeCAD printable panel, 2.0 mm thick, plain (no labels): `build_front_panel.py`, `.FCStd`, `.step`, `.stl` |

The two panels are alternatives with the same holes. Regenerate the printed panel headless from
`modules/audio-out`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
```
