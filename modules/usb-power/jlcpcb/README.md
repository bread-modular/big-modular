# usb-power — manufacturing export

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. There is no module-local release
orchestrator, CAM venv, or pinned CAM dependency set.

## Contents

| Path | Data |
|---|---|
| `carrier/` | 4-layer Gerbers + PTH/NPTH drills, BOM, CPL, export report |
| `passive-panel/` | 2-layer panel Gerbers + drills, empty BOM/CPL, export report |
| `assembly/` | carrier BOM and CPL |
| `usb-power-gerbers.zip` | carrier Gerber/drill ZIP |
| `usb-power-panel-gerbers.zip` | panel Gerber/drill ZIP |
| `source-sha256.json` | source and ZIP SHA-256 |

## Upload map

| Order | Files | Notes |
|---|---|---|
| Carrier PCB | `usb-power-gerbers.zip` | 4 layers, 1.6 mm, 1 oz inner copper |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | front side only; D10/C62/C93 DNP, J7 excluded |
| Passive panel PCB | `usb-power-panel-gerbers.zip` | 2 layers, 1.6 mm, no assembly |

## Source identity

- Carrier: `69a1e329e919ca0f8ddaaec38e30de119fa0d0639823c0017e1675554ff52adc`
  (accepted 084 routing source; unchanged)
- Panel: `174607b27726d41fe67a2c25c6ab2ef53fb5d194b0697f97c215f0e744eb7e66`
  (USB aperture, D10 and SW1 moved -0.60 mm in X; bracket PCB web 2.40 mm)

## Reproduce

From `modules/usb-power`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-power --schematic usb-power.kicad_sch \
  --include-through-hole --require-part-numbers \
  -o research/fresh-carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-power-panel --pcb-only \
  -o research/fresh-panel
```

## Status

This is a fresh manufacturing export, not a supplier-accepted release.
Before upload: run native ERC/DRC/parity, check BOM/CPL refs/sides/rotations,
and obtain JLCPCB DFM/process acceptance (inner 1 oz, plating/drill tolerance,
unfilled vias). Bench thermal/joint/EMI/startup/load qualification remains
outstanding.
