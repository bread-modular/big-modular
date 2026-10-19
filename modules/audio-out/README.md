# audio-out — stereo line + headphone output (4HP)

A pure-analog Eurorack output module based on the Bread Modular `base`
headphone/line output, redone for ±12 V. Two TS inputs (L, R) feed:
- a stereo TRS **line out** at consumer line level (10 Vpp in -> 1.92 Vrms);
- a TRS **headphone out** with one volume pot per ear (Bread Modular RV09 50k).

IN R is normalled to IN L by the IN R jack's switch contact: with only IN L
patched, L goes to both sides of both outputs; patching IN R gives normal stereo.
There is no MONO jumper.

Panel, top to bottom: IN L, IN R, LINE, VOL L, VOL R, PHONES.

Signal chain per channel: 1k -> 1 uF -> 47k/56k divider -> **OPA1678** follower
-> 100R line out, and -> 50k pot (15k taper load) -> **MC33178** follower -> 10R
phones.

**Status: S3 schematic + R4 routed carrier, exported to `jlcpcb/` (not supplier-accepted), not built.**
- The schematic is drawn (native ERC 0).
- The 2-layer carrier is fully routed with GND poured on both sides (thermal reliefs): DRC 0 at all
  severities, 0 unconnected, parity equal, and the shared `check` has no
  findings.
- The 4HP panels (FR4 + printed) are checked for fit against nominal models.
- All 26 SMD parts on the back are JLCPCB-sourced: Basic for every R/C/diode, and
  OPA1678/MC33178 Extended.
- JLCPCB export in `jlcpcb/`; upload map and order gates in `jlcpcb/README.md`.
  Nothing is ordered or bench-tested.

| Path | Contents |
|---|---|
| `hardware/audio-out.kicad_{pro,sch,pcb}` | Carrier (19 x 110 mm, routed R4) and flat schematic (S3); PDF in `docs/audio-out-schematic.pdf` |
| `hardware/AudioOut.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/AudioOut.pretty`, `AudioOut.3dshapes` | Pinned footprints, jack models, RV09 model from the user's sample (`PROVENANCE.json`) |
| `hardware/_kicad_models/` | Vendored 3D models (`<sha256>/<name>`) |
| `panels/front-pcb/audio-out-panel.kicad_{pro,pcb}` | 4HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel generated from the panel PCB |
| `docs/research.md` | BM baseline, circuit, decisions, open items, sourcing |
| `docs/mechanics.md`, `docs/geometry.json` | 4HP fit, stack and placement contract |
| `jlcpcb/` | JLCPCB Gerber ZIPs (carrier, panel), BOM/CPL, source hashes; `jlcpcb/README.md` has the upload map |
| `docs/sourcing-candidates.json`, `docs/jlcpcb-audit-requirements.json` | Dated JLCPCB records; audit circuit requirements |
| `docs/fit/` | Native ERC/DRC JSON, nominal 3D fit report |
| `tools/` | Generators, routing plan, fit check, `kicad-project.json` |

Rebuild (from `modules/audio-out`). The routed PCB is the source of truth, so only
run the layout steps as this whole sequence, then the checks in `Code.md`:

```sh
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd tools/make_pot_model.py   # RV09 model from the user's sample
python3 -B tools/import_footprints.py          # one-time library import (pcbnew)
python3 -B tools/build_schematic.py            # schematic + pinned symbols
python3 -B tools/build_layout.py               # placement + netlist nets + vendored models + panel, UNROUTED
mkdir -p research/route
python3 -B tools/route_plan.py > research/route/plan.json   # R3 copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/audio-out/tools/kicad-project.json \
   --ops modules/audio-out/research/route/plan.json > modules/audio-out/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/audio-out/research/route/edit-plan.json \
   --ops modules/audio-out/research/route/plan.json --output modules/audio-out/research/route-cand-NEW)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/audio-out/research/route-cand-NEW \
   --plan modules/audio-out/research/route/edit-plan.json)
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
tools/fit_assembly.sh                          # nominal panel/carrier 3D fit
```

Read [`Code.md`](Code.md) before changing hardware.
