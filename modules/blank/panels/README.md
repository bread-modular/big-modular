# blank panels (2HP / 4HP / 6HP / 8HP)

| Directory | Contents |
|---|---|
| `front-pcb/` | Native passive FR4 panels `blank-<n>hp.kicad_{pro,pcb}`, 1.6 mm, rail holes only, no labels |
| `front-cad/` | FreeCAD printable panels, 2.0 mm thick: `build_front_panels.py` + `blank-<n>hp-front-panel.{FCStd,step,stl}` |

Regenerate the printed panels headless from `modules/blank`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panels.py
```
