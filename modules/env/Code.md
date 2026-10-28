# ENV contract (S3 schematic, P7 THT placement, R1 routing, JLCPCB export)

| | |
|---|---|
| KiCad project | `hardware/env.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/env-panel.kicad_{pro,pcb}` (FR4, NPTH only, 6HP) |
| Generators, profile | `tools/` (`import_footprints.py`, `build_schematic.py`, `build_layout.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Fabrication outputs | `jlcpcb/` (shared exporter only, never hand-edited; `jlcpcb/README.md`) |

## Fixed by the brief

- The ACID envelope (Bread Modular ENV on an ATtiny1616, ACID pin map and values) as its own
  MIDI module: MIDI IN + MIDI OUT (passive thru, J5 wired in parallel with J1), GATE IN (patched:
  MIDI notes bypassed, the gate drives the envelope; PB1 jack detect), ATTACK + RELEASE, MODE button with HR / AR / ASR LEDs, REC button + LED
  (records the knob positions), ENV OUT 0..5 V protected. 3.3 V internal signals.
- 6HP panel top to bottom (user, 2026-10-28, P7): GATE IN + MIDI IN in one row; ATTACK;
  RELEASE (30 mm pitch); MODE button + HR / AR / ASR LEDs in one row; REC button + REC LED
  (buttons on the left); ENV OUT + ENV LED + MIDI OUT at the bottom. J3 power header vertical on
  B on the right edge between the pots, pin 1 (-12 V) at the bottom (10- or 16-pin cable); J4
  UPDI on B at the left edge.

## Rules

- Same parts and footprints as ACID (`hardware/ENV.pretty/PROVENANCE.json`): RV09 50k linear
  (user stock), PJ301M-12, 3 mm LEDs, 6 x 6 mm tact switches.
- `build_schematic.py` asserts the exported netlist equals `circuit()`; placement by hand
  (`LAYOUT`), every signal net wired by the ACID grid router. PWR_FLAGs only `#FLG01`-`#FLG05`.
- 1 mm board-edge keep-out (`min_copper_edge_clearance` 1.0 mm, courtyards measured) and the
  2 mm hand-solder clearance once SMD parts are placed. Routing follows the root manual
  divide-and-conquer rules; once it starts the native PCB owns placement and copper and
  `build_layout.py` must not be rerun.
