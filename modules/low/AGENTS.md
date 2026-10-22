# LOW agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths
are module-relative.

## Current state

- **S3 schematic** (`hardware/low.kicad_sch`, ERC 0, signal nets wired; S3 = S2 + LCSC fields, R17/R18 47k/100k): Bread Modular MCO + LOW on
  3.3 V, 8bit MIDI input, AUDIO/CV bypass inputs normalled through U4 TS5A23157 to the
  MCO square mix / velocity DAC, TL072 ±12 V output.
- **R3 routed carrier** (`hardware/low.kicad_pcb`, 2026-10-22): manual divide-and-conquer routing
  (root AGENTS.md); every SMD pad >= 2 mm from the pot/jack pads (root rule, hand soldering;
  closest U6 2.20, C9 2.43, D4 2.83 mm) and the root **1 mm board-edge keep-out** (R3, research.md 5.3: copper-edge rule
  1.0 mm, courtyards >= 1 mm except the panel-fixed RV1/RV2 at 0.82 mm, user-accepted), all SMD on B, 2 layers with
  GND pours on F.Cu and B.Cu, Power net class 0.4 mm.
  KiCad DRC: 0 violations, 0 unconnected, parity 0; the 3 U5-under-RV3 stacking findings are
  user-approved exclusions written by `tools/u5_exclusions.py` (vca-mix D10 pattern; the shared
  gate still counts them, so `order_ready` stays false). No vias in SMD pads. Per-batch scripts and the one-connection path
  finder are in the ignored `research/route/`. The native PCB now owns placement and copper.
- 6HP panel `panels/front-pcb/low-panel.kicad_pcb`, DRC 0.
- **JLCPCB export** in `jlcpcb/` (2026-10-22 re-export of R3, bottom Economic, all R/C Basic): see
  `jlcpcb/README.md`. Not supplier-accepted, not built.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports go in the ignored `research/`. Routing follows the root manual
divide-and-conquer rules; once routing starts, the native PCB owns placement and copper
and `build_layout.py` must not be rerun over it.
