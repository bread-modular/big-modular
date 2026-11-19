# 12bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S3 schematic** (`hardware/12bit.kicad_sch`, ERC 0, wired nets + power symbols, netlist
  asserted against `circuit()`): modules/8bit moved to an **STM32G071C8T6** (ATtiny1616 low
  on stock) on 6HP. 8bit MIDI in (JP1, shipped open) and bipolar CV in, three 50k knobs on the
  ADC (knob 3 is no longer the passive low-pass), 8bit MODE switch + LED,
  **two DC-coupled ±5 V outputs** from the two 12-bit DAC channels (TL074), SWD header,
  HT7533-1 +3V3. S2 removed the S1 gate output (U4D is a grounded spare).
  **S3 (2026-11-19, after the output buzz of the first board): +3V0 reference rail**, an LM4040
  3.0 V shunt (U5, R18 from +12V_F) for VREF+, the knobs, VOFF, the CV shift + buffer and the
  MIDI pull-ups; +3V3 only feeds the MCU and J6.1. R5 / R6 / R10 / R12 / R15 re-valued so the
  firmware and levels stay as S2. See `Code.md`.
- **P3 placement + R3 routing** (`hardware/12bit.kicad_pcb`, **2 layers** F / B, GND pours on
  both, 1 mm copper-edge rule): THT rows MIDI/CV Y21, P1/P2 Y52.2, MODE + LED + P3 Y79.2, OUT 1/2
  Y110.4; all 49 SMD on B. R3 = R2 + four hand batches (`research/route-s3/`): U1 / C3 / C4 moved
  beside the MCU, U5 / R18 in their place, the old +3V3 tree is +3V0, J6.1 on a thin +3V3 line.
  Shared check: ERC 0, DRC 0 (warnings incl.), **unconnected 0**, parity 0; no vias in SMD
  pads; SMD >= 2.025 mm from pot/jack pads; courtyards >= 1.015 mm from the edge. 6HP FR4 panel DRC 0.
- **JLCPCB export** in `jlcpcb/`: **S3 / R3, 2026-11-19** (2 layers, bottom Economic, 48 parts / 25 rows,
  shared `check` manifest equal; 6 Extended part types, STM32G071C8T6 listed stock 965). Not
  supplier-accepted, no JLCPCB preview, not built, not measured. The S2 / R2 export of the first board
  (46 parts / 24 rows) is in git history.
- Firmware in `firmware/` (`clapsnare`, `osc3`, `humtest`); first board built. Open items: `docs/research.md` §5.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Routing follows the root manual
divide-and-conquer rules; now that it is routed the native PCB owns placement and copper and
`tools/build_layout.py` must not be rerun over it (it refuses a board with tracks).
No merges, pushes, orders or uploads.
