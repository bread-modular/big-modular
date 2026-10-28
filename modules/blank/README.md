# blank — 2HP / 4HP / 6HP / 8HP blank panels

Plain Eurorack blank panels (no labels, no copper): outline plus the rail holes.
Geometry contract: `docs/geometry.json`.

| Panel | Size (mm) | Rail holes X (Y 3.0 / 125.5), Ø3.2 |
|---|---|---|
| 2HP | 9.8 x 128.5 | 2.42 |
| 4HP | 20.0 x 128.5 | 12.58 |
| 6HP | 30.0 x 128.5 | 12.58 |
| 8HP | 40.3 x 128.5 | 12.58, 32.9 |

The rail holes sit 1HP off the Doepfer 7.5 mm phase, the same as every module
(2.42 mm on 2HP, see `case/tools/build_case.py`), so they land on the case's 2HP
spacer grid. The case build checks every panel against that grid.

| Path | Contents |
|---|---|
| `panels/front-pcb/blank-<n>hp.kicad_{pcb,pro}` | Native passive FR4 panels, 1.6 mm, NPTH only |
| `panels/front-cad/blank-<n>hp-front-panel.{FCStd,step,stl}` | FreeCAD printable panels, 2.0 mm |
| `jlcpcb/blank-<n>hp-gerbers.zip` | Gerber/drill ZIP to upload (2 layers, FR4, 1.6 mm, no assembly; black mask suits a panel) |
| `jlcpcb/blank-<n>hp/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |

## Regenerate

From `modules/blank`:

```sh
python3 -B tools/build_panels.py
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panels.py
for n in 2 4 6 8; do
  kicad-cli pcb drc --severity-all --format json -o research/drc-${n}hp.json panels/front-pcb/blank-${n}hp.kicad_pcb
  python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb --board blank-${n}hp --pcb-only \
    --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/blank-${n}hp
  unzip -o jlcpcb/blank-${n}hp/blank-${n}hp-gerbers.zip -d jlcpcb/blank-${n}hp
  cp jlcpcb/blank-${n}hp/blank-${n}hp-gerbers.zip jlcpcb/
done
```

The printable panels read the outline and holes from the KiCad panels and assert
them against `docs/geometry.json`. Print suggestion: PETG/ABS, front face down,
0.2 mm layers; holes are nominal, ream after printing. Nominal geometry only, no
physical-fit claim. Not supplier-accepted.
