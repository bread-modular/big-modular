# midi — TRS MIDI to 8 x TS modular MIDI (4HP)

Based on Bread Modular `midi`. TRS MIDI in goes to an ATtiny1616 (Bread Modular
V1-style direct input, TRS Type A/B on a jumper header; no opto until V2),
which sends MIDI channel *n* to TS output *n* (tip = logic-level MIDI, sleeve =
GND). There is one hand-soldered 3 mm LED per output, and power comes from
Eurorack +12 V through a 5 V LDO (5 V logic, as Bread Modular).

**Status: S3 schematic + R1 routed carrier, not released.** The schematic is drawn
(native ERC 0), the 2-layer carrier is fully routed (DRC 0 at all severities,
0 unconnected, parity equal, shared `check` with no findings) and the 4HP panels
(FR4 + printed) are checked for fit. No sourcing gate, fabrication export or bench
test yet.

| Path | Contents |
|---|---|
| `hardware/midi.kicad_{pro,pcb}` | Carrier: 19 x 110 mm, routed on 2 layers (R1), GND poured both sides |
| `hardware/midi.kicad_sch` | Flat root schematic (S3); PDF in `docs/midi-schematic.pdf` |
| `hardware/_kicad_models/` | Vendored 3D models (`<sha256>/<name>`), bound via `${KIPRJMOD}` |
| `hardware/MIDI.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/MIDI.pretty`, `MIDI.3dshapes` | Pinned footprints and jack models (`PROVENANCE.json`) |
| `panels/front-pcb/midi-panel.kicad_{pro,pcb}` | 4HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | BM baseline, circuit, decisions, sourcing observations |
| `docs/mechanics.md`, `docs/geometry.json` | 4HP fit, stack and placement contract |
| `docs/fit/` | Native DRC/ERC JSON, nominal 3D fit report, renders |
| `tools/` | Footprint import, schematic and layout generators, routing plan, fit check, `kicad-project.json` |

Rebuild (from `modules/midi`; the routed PCB is the source of truth, so only run
the layout steps as this whole sequence, then the checks in `Code.md`):

```sh
python3 -B tools/import_footprints.py          # one-time library import (pcbnew)
python3 -B tools/build_schematic.py            # schematic + pinned symbols
python3 -B tools/build_layout.py               # placement + netlist nets + vendored models, UNROUTED
python3 -B tools/route_plan.py > research/route/plan.json   # R1 copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/midi/tools/kicad-project.json \
   --ops modules/midi/research/route/plan.json > modules/midi/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/midi/research/route/edit-plan.json \
   --ops modules/midi/research/route/plan.json --output modules/midi/research/route-cand-NEW)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/midi/research/route-cand-NEW \
   --plan modules/midi/research/route/edit-plan.json)
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
tools/fit_assembly.sh                          # nominal panel/carrier 3D fit
```

Read [`Code.md`](Code.md) before changing hardware.
