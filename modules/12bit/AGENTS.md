# 12bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S2 schematic** (`hardware/12bit.kicad_sch`, ERC 0, wired nets + power symbols, netlist
  asserted against `circuit()`): modules/8bit moved to an **STM32G071C8T6** (ATtiny1616 low
  on stock) on 6HP. 8bit MIDI in (JP1, shipped open) and bipolar CV in at 3.3 V, three 50k
  knobs on the ADC (knob 3 is no longer the passive low-pass), 8bit MODE switch + LED,
  **two DC-coupled ±5 V outputs** from the two 12-bit DAC channels (TL074), SWD header,
  HT7533-1 +3V3. S2 removed the S1 gate output (U4D is a grounded spare) and renumbered
  J3/J4 = OUT 1/2, J5 = power, J6 = SWD, R16/R17 = output resistors.
- **P3 placement + R2 routing** (`hardware/12bit.kicad_pcb`, **2 layers** F / B, GND pours on
  both, 1 mm copper-edge rule): THT rows MIDI/CV Y21, P1/P2 Y52.2, MODE + LED + P3 Y79.2, OUT 1/2
  Y110.4; all 46 SMD on B. R1 (4-layer, four hand batches) kept its F/B copper; R2 (user,
  2026-11-07, cost) removed the In1 GND / In2 +3V3 planes and routed +3V3 as tracks in two
  batches (`research/route2l/`, see `Code.md`).
  Shared check: ERC 0, DRC 0 (warnings incl.), **unconnected 0**, parity 0; no vias in SMD
  pads; SMD >= 2.025 mm from pot/jack pads; courtyards >= 1.015 mm from the edge. 6HP FR4 panel DRC 0.
- **JLCPCB export** in `jlcpcb/` (R2, 2 layers, bottom Economic, 46 parts / 24 rows), not supplier-accepted.
- No firmware. Open items: `docs/research.md` §5.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Routing follows the root manual
divide-and-conquer rules; now that it is routed the native PCB owns placement and copper and
`tools/build_layout.py` must not be rerun over it (it refuses a board with tracks).
No merges, pushes, orders or uploads.
