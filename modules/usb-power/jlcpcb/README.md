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
| `source-sha256.json` | PCB/PRO/sheet inputs and export/ZIP SHA-256 |

## Upload map

| Order | Files | Notes |
|---|---|---|
| Carrier PCB | `usb-power-gerbers.zip` | JLC standard 4-layer: JLC04161H-7628, FR4 Tg155, 1.6 mm, 1 oz outer / 0.5 oz inner, HASL (with lead), tented vias |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | front side only; D10/C62/C93 DNP, J7 excluded |
| Passive panel PCB | `usb-power-panel-gerbers.zip` | JLC standard 2-layer FR4 Tg135, 1.6 mm, black mask, no assembly |

## Source identity

- Carrier PCB: `937cba26feb2d0aba6c7add300378e405f82fae2901569460de81e96626c6b1a`;
  project `122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9`;
  root schematic `4c3512d82c8a66903d2e7b917938ddf9b1f514697861766c53a8bb51eba13500`.
- Panel PCB: `5e8b99ea3f9f178ea0030ab29d5c906e31b8a1ed722a0491b78efd74b32f4aab`;
  project `d8211fb9ceb1112ac893d16ada5df17ab439c3295ff61ca9fb112b4154045e52`.
- `source-sha256.json` binds the complete carrier/panel PCB, project and
  hierarchical-sheet inputs plus the assembly and ZIP identities.

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

This is the complete regenerated manufacturing export, not a supplier-accepted
release. The carrier BOM/CPL contain 112 unique fitted refs (44 BOM rows), all
top-side with LCSC codes; D10/C62/C93 are DNP and J7 is excluded. Before upload:
confirm BOM/CPL refs/sides/rotations and run JLCPCB DFM. All order options are
JLC standard (no paid stack, copper, finish or via options; standard tolerances;
tented unfilled vias). Bench thermal/joint/EMI/startup/load qualification
remains outstanding and is not claimed.
