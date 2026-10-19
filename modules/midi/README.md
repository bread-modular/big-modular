# midi — TRS MIDI to 8 x TS modular MIDI (4HP)

Based on Bread Modular `midi`. TRS MIDI in goes to an ATtiny1616 (TRS Type A/B on a
jumper header, no opto), which sends MIDI channel *n* to TS output *n* (tip =
logic-level MIDI, sleeve = GND). There is one hand-soldered 3 mm LED per output, switched by
an NPN transistor from +5V as in Bread Modular's `gate_out`, and
power comes from Eurorack +12 V through a 5 V LDO (5 V logic, as Bread Modular).

There are two hardware versions. Both use the same panels and mechanics:

| | **V1** (`hardware/v1/`) | **V2** (`hardware/v2/`) |
|---|---|---|
| MIDI IN | Bread Modular V1 direct input: JP1 drives PB3, no series R or pull-up | NPN front end: 3.3 V and 5 V senders, survives ±12 V. Inverting: firmware sets `PORT_INVEN` on PB3. JP2 solder jumper (shipped open; solder 1-2 = protected, 2-3 = V1 direct path for debugging) |
| MIDI OUT | GPIO → 0603 1 k → tip | GPIO → 0805 1 k → tip, BAT54SW clamp to +5V/GND on the GPIO side |
| +5V | HT7550-1 | HT7550-1 plus CJ431 shunt clamp (5.49 V), so clamp current can't pump the rail |
| Mis-patched ±12 V CV/gate cable | Known risk | Survives indefinitely (design; bench test open) |
| Back silk | `MIDI V1.0` | `MIDI V2.0` |
| LEDs | +5V → LED → 1 k → MMBT3904 (GPIO → 10 k base), one channel sheet per output | same |
| SMD parts (JLC-assembled) | 41 in 11 BOM rows | 57 in 18 BOM rows |
| Fabrication export | [`jlcpcb/v1/`](jlcpcb/v1/README.md) | [`jlcpcb/v2/`](jlcpcb/v2/README.md) |

**Status: V1.0 (S5/R6) and V2.0 (S4/R4) fabrication exports, not supplier-accepted.**
- Both schematics are drawn (native ERC 0).
- Both 2-layer carriers are fully routed: DRC 0 at all severities, 0 unconnected,
  parity equal, shared `check` with no findings. The regulator sits beside the power
  header on heat-sink copper on both layers.
- The 4HP panels (FR4 + printed) are checked for fit with both carriers.
- Every SMD part on the back is JLCPCB-sourced. Every R/C is Basic except R20, as
  the brief requires.
- Nothing is bench-tested.

| Path | Contents |
|---|---|
| `hardware/v1/`, `hardware/v2/` | KiCad projects: `midi.kicad_{pro,sch,pcb}` (19 x 110 mm carrier, 2 layers, GND poured both sides, U3 heat sink beside J10), pinned symbols (`MIDI.kicad_sym`, `sym-lib-table`), footprints and jack models (`MIDI.pretty`, `MIDI.3dshapes`, `PROVENANCE.json`), vendored 3D models (`_kicad_models/<sha256>/`) |
| `panels/front-pcb/midi-panel.kicad_{pro,pcb}` | 4HP FR4 front panel: NPTH only, silkscreen labels (shared by V1 and V2) |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | BM baseline, circuit, decisions, sourcing (V1 §1-6, V2 §7) |
| `docs/geometry.json`, `docs/mechanics.md` | 4HP fit, stack, panel and V1 placement contract |
| `docs/v2/geometry.json` | V2 placement (mechanics asserted equal to V1's) |
| `docs/v2/recovered/` | Evidence the V2 rebuild was checked against (netlist + field dump, routed-board inspection) |
| `docs/rebuild-status.md` | How the two-version tree was rebuilt and verified after the 2026-10-19 loss; deviations |
| `docs/midi-schematic.pdf`, `docs/v2/midi-schematic.pdf` | Schematic PDFs |
| `docs/fit/`, `docs/v2/fit/` | Native DRC/ERC JSON, nominal 3D fit report, renders |
| `docs/sourcing-candidates.json`, `docs/jlcpcb-audit-requirements.json`, `docs/v2/jlcpcb-audit-requirements.json` | Dated JLCPCB part records; assembly-audit circuit requirements |
| `jlcpcb/v1/`, `jlcpcb/v2/` | Fabrication exports: Gerber ZIPs, BOM, CPL, source manifest |
| `tools/v1/`, `tools/v2/` | Schematic and layout generators, routing plan, shared-tool profile (`kicad-project.json`) |
| `tools/` | Shared: footprint import and fit check (take `v1`/`v2`), S-expression helper |

Rebuild one version (from `modules/midi`, with `V=v1` or `V=v2`). The routed PCB is
the source of truth, so only run the layout steps as this whole sequence, then the
checks in `Code.md`:

```sh
python3 -B tools/import_footprints.py --version $V    # one-time library import (pcbnew)
python3 -B tools/$V/build_schematic.py         # schematic + pinned symbols
python3 -B tools/$V/build_layout.py            # placement + netlist nets + vendored models, UNROUTED
git checkout panels/front-pcb/midi-panel.kicad_pcb  # V1 only, unless the panel really changed: the generator re-UUIDs it
mkdir -p research/$V/route
python3 -B tools/$V/route_plan.py > research/$V/route/plan.json   # copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/midi/tools/$V/kicad-project.json \
   --ops modules/midi/research/$V/route/plan.json > modules/midi/research/$V/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/midi/research/$V/route/edit-plan.json \
   --ops modules/midi/research/$V/route/plan.json --output modules/midi/research/$V/route-cand-NEW)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/midi/research/$V/route-cand-NEW \
   --plan modules/midi/research/$V/route/edit-plan.json)
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py   # only if the panel changed
tools/fit_assembly.sh $V                       # nominal panel/carrier 3D fit
```

After any source change, re-export that version with the commands in its
`jlcpcb/<v>/README.md`.

Read [`Code.md`](Code.md) before changing hardware.
