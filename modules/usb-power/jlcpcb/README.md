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
| Passive panel PCB | `usb-power-panel-gerbers.zip` | JLC standard 2-layer FR4 Tg135, 1.6 mm, black mask, white silk, **lead-free HASL** (silver copper art), no assembly |

## Source identity

- Carrier PCB: `9af7362164024cbf7633330342c507518941e1b95ca605212c8e2e1d4dfce567`;
  project `122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9`;
  root schematic `4c3512d82c8a66903d2e7b917938ddf9b1f514697861766c53a8bb51eba13500`.
- Panel PCB: `48f6d6feac89bb8789dfbc2b95df994216fac81900c4a47fcde5023a7bba8c54`;
  project `d8211fb9ceb1112ac893d16ada5df17ab439c3295ff61ca9fb112b4154045e52`.
- `source-sha256.json` binds the complete carrier/panel PCB, project and
  hierarchical-sheet inputs plus the assembly and ZIP identities.

## Panel artwork

The panel front has no captions; its art is design F ("charged"): a dot field
with a lightning bolt left as black negative space, plus fading dot bands at
the top and foot. It is unconnected F.Cu with matching F.Mask openings, so it
shows as bare lead-free HASL (silver) on the black mask; `V1` is on B.Silkscreen.
Regenerate it with
`python3 -B panels/front-pcb/art/build_panel_art.py --only f-charged --apply`
(idempotent), then run panel DRC and the panel export below.

## Reproduce

From `modules/usb-power`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-power --schematic usb-power.kicad_sch \
  --include-through-hole --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/usb-power-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board usb-power-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/passive-panel
unzip -o jlcpcb/passive-panel/usb-power-panel-gerbers.zip -d jlcpcb/passive-panel
```

The exporter publishes the ZIP, BOM/CPL and report; the per-layer Gerbers and
drills in `carrier/` and `passive-panel/` are that ZIP unpacked, so never leave
stale plots beside a new ZIP. Copy `carrier/bom.csv` and `carrier/positions.csv`
to `assembly/` and both ZIPs to this directory afterwards.

## Status

This is the complete regenerated manufacturing export, not a supplier-accepted
release. The carrier BOM/CPL contain 112 unique fitted refs (44 BOM rows), all
top-side with LCSC codes; D10/C62/C93 are DNP and J7 is excluded. Before upload:
confirm BOM/CPL refs/sides/rotations and run JLCPCB DFM. All order options are
JLC standard (no paid stack, copper, finish or via options, except the panel's
lead-free HASL finish; standard tolerances;
tented unfilled vias). Bench thermal/joint/EMI/startup/load qualification
remains outstanding and is not claimed.
