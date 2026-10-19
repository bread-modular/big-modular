# imix — 4-channel buffered CV/audio mixer (6HP)

Four inputs, each with a level knob beside its jack, mixed to one MIX output at
the bottom. DC-coupled, so it mixes Eurorack CV or audio. Full clockwise = unity
gain for that channel. As on Bread Modular's `imix`, every input has an inverting
op-amp buffer in front of its pot (fixed 100k input impedance, the pot driven from
the buffer), with 20 pF feedback caps and 100 nF decoupling at every op-amp. It
uses Thonk Tall Trimmer pots (B50K on Bread Modular's RV09 footprint), PJ301M-12
jacks (as midi, TN grounds an unpatched input), three TL072s on ±12 V (two for the
buffers, one summer), and a 1k (1 W 2512) series output.

**Status: S3 schematic + R3 routed carrier + 6HP panels + JLCPCB export
(`jlcpcb/`, not supplier-accepted). Nothing bench-tested.**
- Schematic: native ERC 0.
- Carrier: 29 x 110 mm, 2 layers, fully routed. DRC 0 at all severities, 0
  unconnected, parity equal. The shared `check` reports no findings, and the
  export manifest is equal.
- All 36 SMD parts are on the back and JLCPCB Basic, except R18 (1 W 2512,
  Extended, sized for a -12 V source patched into MIX), checked by a live strict
  audit (`docs/sourcing-candidates.json`, `jlcpcb/README.md`).
- Panels (FR4 + printed): 0 mm³ nominal interference; pot shafts about 13 mm
  proud. Open check M1 in `docs/research.md`: seat a real pot on the footprint.

| Path | Contents |
|---|---|
| `hardware/imix.kicad_{pro,pcb}` | Carrier: 4 rows of jack + pot, MIX jack at the bottom; SMD on B; GND poured both sides |
| `hardware/imix.kicad_sch` | Flat root schematic (S3); PDF in `docs/imix-schematic.pdf` |
| `hardware/_kicad_models/` | Vendored 3D models (`<sha256>/<name>`), bound via `${KIPRJMOD}` |
| `hardware/IMIX.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/IMIX.pretty`, `IMIX.3dshapes` | Pinned footprints, jack model, pot proxy (`PROVENANCE.json`) |
| `panels/front-pcb/imix-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | Brief, Bread Modular baseline, circuit, routing, open checks, sourcing |
| `docs/geometry.json` | Placement, panel, labels and stack contract |
| `docs/jlcpcb-audit-requirements.json` | Per-part ratings and manual-assembly reasons for the assembly audit |
| `jlcpcb/` | Shared-exporter Gerbers, BOM/CPL, manifest; upload map and order gates in `jlcpcb/README.md` |
| `docs/fit/` | Native ERC/DRC JSON, nominal 3D fit report, renders |
| `tools/` | Generators (pot proxy, footprints, schematic, layout), routing plan, fit check, `kicad-project.json` |

Panel (top to bottom): `IMIX`, `IN` / `LEVEL` column labels, four rows of input
jack + channel number + level knob, then the `MIX` jack.

Rebuild (from `modules/imix`; the routed PCB is the source of truth, so only run
the layout steps as this whole sequence, then the checks in `Code.md`):

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd tools/build_pot_model.py   # Tall Trimmer 3D proxy
python3 -B tools/import_footprints.py          # one-time library import (pcbnew)
python3 -B tools/build_schematic.py            # schematic + pinned symbols
python3 -B tools/build_layout.py               # placement + netlist nets + vendored models, UNROUTED
python3 -B tools/route_plan.py > research/route/plan.json   # R3 copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/imix/tools/kicad-project.json \
   --ops modules/imix/research/route/plan.json > modules/imix/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/imix/research/route/edit-plan.json \
   --ops modules/imix/research/route/plan.json --output modules/imix/research/route-cand-NEW)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/imix/research/route-cand-NEW \
   --plan modules/imix/research/route/edit-plan.json)
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
tools/fit_assembly.sh                          # nominal panel/carrier 3D fit
```

Then re-export with the commands in `jlcpcb/README.md`.

Read [`Code.md`](Code.md) before changing hardware.
