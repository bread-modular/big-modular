# vca-mix — 3 x vactrol VCA + 3-channel mixer (6HP)

Each channel is a Bread Modular V2CA vactrol VCA (no CURVE knob) with IN, CV and
OUT jacks. The CV drives the vactrol through a Bread Modular LOW/SVF vactrol
driver, so the response follows the CV from 0 V with no dead zone. A volume pot
after each VCA sets the channel level: OUT follows it, and the three channels sum
into a MIX output (the Bread Modular imix mixer). With no CV plugged in, the VCA is
fully open, so VCA-MIX also works as a plain 3-channel mixer. Power is Eurorack
±12 V (10 x TL072). Inputs and CVs are buffered; OUT and MIX drive through 1 W
1k resistors.

**Status: S4 schematic + P4 placement + R1 routing (final), not released.**
- Schematic drawn with wired nets (native ERC 0).
- 6HP panels (FR4 + printed) generated.
- Carrier placed with schematic nets (parity equal). One row per channel, the knob
  below its jacks; vactrols on B behind their own pots (Bread Modular SVF style).
- R1 routing (TraceMaker, picked over Freerouting; `docs/research.md` 4.1) is complete
  in a shared-tool candidate: 0 unconnected, parity equal. The 9 `pth_inside_courtyard`
  findings from the vactrol/pot stacking are user-approved per-item DRC exclusions (D10).
  It is in `hardware/` (user direction 2026-10-20): the shared apply output was copied
  with `tools/promote_r1.py` because `pcb promote` refuses it while the shared gate
  counts excluded findings (D14). The user accepts that and verifies the 9 by hand.
- Vactrol build notes are silk inside each vactrol outline on the back: `SOLDER FIRST`,
  `TRIM FLUSH`, `LED 18.5mA` (fit the vactrol before its pot, D4/D10).
- Nominal 3D fit of jacks and pots against both panels checked.
- All SMD parts are JLCPCB-sourced: Basic except the four 1 W 2512 resistors.
- Nothing is bench-tested.

| Path | Contents |
|---|---|
| `hardware/vca-mix.kicad_sch` | Flat root schematic (S4); PDF in `docs/vca-mix-schematic.pdf` |
| `hardware/vca-mix.kicad_{pro,pcb}` | Carrier: 29 x 110 mm, 2 layers, R1 routed (P4 placement, 472 tracks, 40 vias, GND pours both layers) |
| `hardware/VCA_MIX.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/VCA_MIX.pretty`, `VCA_MIX.3dshapes` | Pinned footprints and jack model (`PROVENANCE.json`) |
| `hardware/_kicad_models/` | Vendored 3D models (`<sha256>/<name>`), bound via `${KIPRJMOD}` |
| `panels/front-pcb/vca-mix-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | BM baseline, circuit, power budget, mechanics, decisions, sourcing |
| `docs/geometry.json` | Placement, panel and stack contract |
| `docs/sourcing-candidates.json` | Dated JLCPCB part records |
| `docs/fit/` | Native ERC/DRC JSON, nominal 3D fit report, renders |
| `tools/` | Footprint import, schematic and layout generators, R1 route data + plan emitter + D14 copy step (`route_r1.json`, `route_plan.py`, `promote_r1.py`), fit check, `kicad-project.json` |

## Front panel

```
        VCA-MIX
  IN1   CV1   OUT1        one row per channel:
  VOL1  (o)               knob directly below its jacks
  IN2   CV2   OUT2
  VOL2  (o)
  IN3   CV3   OUT3
  VOL3  (o)
        MIX
```

Rebuild (from `modules/vca-mix`). `build_layout.py` writes the R1 base without
copper; R1 is then applied with the shared tools. Don't rerun `build_layout.py` over a
promoted routed board except to rebuild R1 from scratch this way:

```sh
python3 -B tools/import_footprints.py          # one-time library import (pcbnew)
python3 -B tools/build_schematic.py            # schematic + pinned symbols
python3 -B tools/build_layout.py               # R1 base: placement + netlist nets + vendored models, no copper
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
tools/fit_assembly.sh                          # nominal panel/carrier 3D fit
python3 -B tools/route_plan.py > research/route/plan.json   # R1 copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/vca-mix/tools/kicad-project.json \
   --ops modules/vca-mix/research/route/plan.json > modules/vca-mix/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/vca-mix/research/route/edit-plan.json \
   --ops modules/vca-mix/research/route/plan.json --output modules/vca-mix/research/route-cand-NEW)
# after any build_layout.py run, re-key the D10 exclusions (pad/footprint UUIDs change):
kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
   -o research/drc/d10.json hardware/vca-mix.kicad_pcb
python3 -B tools/d10_exclusions.py research/drc/d10.json
# (re-run d10_exclusions.py and re-plan before apply when the base changed)
# while D14 is open, `pcb promote` refuses the candidate; copy it with the same model rebinding:
python3 -I -B tools/promote_r1.py \
   research/route-cand-NEW/inputs$(pwd)/hardware/vca-mix.kicad_pcb hardware/vca-mix.kicad_pcb
# once D14 is resolved, use the shared promote instead:
# (cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/vca-mix/research/route-cand-NEW \
#    --plan modules/vca-mix/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/vca-mix/tools/kicad-project.json \
   --reports modules/vca-mix/research/check-NEW)
```

A rebuild is reproducible except for UUIDs that KiCad assigns itself (schematic
pin/wire items after `sch upgrade`, PCB items from pcbnew). Same nets, placement and
fields; review diffs by content, not by bytes.

Read [`Code.md`](Code.md) before changing hardware.
