# midi — TRS MIDI to 8 x TS modular MIDI (4HP)

Based on Bread Modular `midi`. TRS MIDI in goes to an ATtiny1616 (Bread Modular
V1-style direct input, TRS Type A/B on a jumper header; no opto until V2),
which sends MIDI channel *n* to TS output *n* (tip = logic-level MIDI, sleeve =
GND). There is one hand-soldered 3 mm LED per output, and power comes from
Eurorack +12 V through a 5 V LDO (5 V logic, as Bread Modular).

**Status: V1.0 (R3) fabrication export, not supplier-accepted.**
- The schematic is drawn (native ERC 0).
- The 2-layer carrier is fully routed. The regulator sits beside the power header
  on heat-sink copper on both layers
  (DRC 0 at all severities, 0 unconnected, parity equal, shared `check` with no
  findings).
- The 4HP panels (FR4 + printed) are checked for fit.
- All 27 SMD parts on the back are JLCPCB-sourced (Basic for every R/C except
  R20).
- Gerbers, BOM and CPL are in [`jlcpcb/`](jlcpcb/README.md).
- Nothing is bench-tested.

| Path | Contents |
|---|---|
| `hardware/midi.kicad_{pro,pcb}` | Carrier: 19 x 110 mm, routed on 2 layers (R3), GND poured both sides, U3 heat sink beside J10 |
| `hardware/midi.kicad_sch` | Flat root schematic (S3); PDF in `docs/midi-schematic.pdf` |
| `hardware/_kicad_models/` | Vendored 3D models (`<sha256>/<name>`), bound via `${KIPRJMOD}` |
| `hardware/MIDI.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/MIDI.pretty`, `MIDI.3dshapes` | Pinned footprints and jack models (`PROVENANCE.json`) |
| `panels/front-pcb/midi-panel.kicad_{pro,pcb}` | 4HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | BM baseline, circuit, decisions, sourcing |
| `docs/sourcing-candidates.json`, `docs/jlcpcb-audit-requirements.json` | Dated JLCPCB part records; assembly-audit circuit requirements |
| `jlcpcb/` | Fabrication export: Gerber ZIPs, BOM, CPL, source manifest ([README](jlcpcb/README.md)) |
| `docs/mechanics.md`, `docs/geometry.json` | 4HP fit, stack and placement contract |
| `docs/fit/` | Native DRC/ERC JSON, nominal 3D fit report, renders |
| `tools/` | Footprint import, schematic and layout generators, routing plan, fit check, `kicad-project.json` |

Rebuild (from `modules/midi`; the routed PCB is the source of truth, so only run
the layout steps as this whole sequence, then the checks in `Code.md`):

```sh
python3 -B tools/import_footprints.py          # one-time library import (pcbnew)
python3 -B tools/build_schematic.py            # schematic + pinned symbols
python3 -B tools/build_layout.py               # placement + netlist nets + vendored models, UNROUTED
git checkout panels/front-pcb/midi-panel.kicad_pcb  # unless the panel really changed: the generator re-UUIDs it
python3 -B tools/route_plan.py > research/route/plan.json   # R3 copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/midi/tools/kicad-project.json \
   --ops modules/midi/research/route/plan.json > modules/midi/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/midi/research/route/edit-plan.json \
   --ops modules/midi/research/route/plan.json --output modules/midi/research/route-cand-NEW)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/midi/research/route-cand-NEW \
   --plan modules/midi/research/route/edit-plan.json)
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
tools/fit_assembly.sh                          # nominal panel/carrier 3D fit
```

After any source change, re-export with the commands in [`jlcpcb/README.md`](jlcpcb/README.md).

Read [`Code.md`](Code.md) before changing hardware.
