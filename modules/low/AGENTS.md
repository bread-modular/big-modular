# LOW agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths
are module-relative.

## Current state

- **S2 schematic** (`hardware/low.kicad_sch`, ERC 0, signal nets wired): Bread Modular MCO + LOW on
  3.3 V, 8bit MIDI input, AUDIO/CV bypass inputs normalled through U4 TS5A23157 to the
  MCO square mix / velocity DAC, TL072 ±12 V output.
- **R1 routed carrier** (`hardware/low.kicad_pcb`, 2026-10-21): manual divide-and-conquer routing
  (root AGENTS.md), all SMD on B, 2 layers with GND pours on F.Cu and B.Cu, Power net class 0.4 mm.
  Native DRC + parity: 3 U5-under-RV3 stacking findings (vca-mix D10 pattern, no exclusion),
  0 unconnected, parity 0; no vias in SMD pads. Per-batch scripts and the one-connection path
  finder are in the ignored `research/route/`. The native PCB now owns placement and copper.
- 6HP panel `panels/front-pcb/low-panel.kicad_pcb`, DRC 0.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports go in the ignored `research/`. Routing follows the root manual
divide-and-conquer rules; once routing starts, the native PCB owns placement and copper
and `build_layout.py` must not be rerun over it.
