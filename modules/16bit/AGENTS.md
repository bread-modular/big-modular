# 16bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S3 schematic** (`hardware/16bit.kicad_sch`, ERC 0, wired blocks + power symbols):
  Bread Modular 16bit (RP2350A, W25Q128, APS6404L PSRAM, PT8211) on Eurorack 6HP. TS MIDI in
  with the 8bit/MIDI V2 NPN front end and JP1 (shipped open), two bipolar CV
  inputs, each normalled to +5V through its own 50k attenuator (RV1/RV2 -> TL072 -> level shift ->
  MCP6002 on +3V3 -> ADC0/1), two 50k knobs RV3/RV4 (-> ADC2/3), no mux,
  6x6 mm THT mode button (8bit SW1, GPIO12), 3 mm red mode LED (GPIO13 PWM, 1k),
  TL074 ±5 V outputs (gain 6.1), AMS1117-5.0/-3.3 from +12 V, USB-C data only.
- **S5 placement + R1 routing** (`hardware/16bit.kicad_pcb`, 4 layers, ROUTED from
  `tools/route_r1.json` via `tools/route_plan.py`): shared check DRC 0 / unconnected 0 / parity 0,
  In2 +3V3 one piece, In1 GND one main piece + two spoke-tied 2.6 mm² pieces at J6. Reviewed in
  rev1 (`docs/research.md` §7): 9 in-pad vias moved off U1/D5/D6, router jogs tidied; **the board
  requires via-in-pad fill (POFV) at the fab** for the remaining 123 in-pad vias + U1 EP array
  (`Code.md`). Next schematic rev: add an input cap at U8 (§7.3 F2). CV jacks + RV1/RV2 grouped, RV3/RV4 22 mm lower, MCU between the rows; OUT jacks at Y99; MODE button + LED in the bottom corners near the edge; regulators between RV3/RV4 and the OUT jacks;
  USB-C on B at the top edge, opening up. 6HP FR4 panel DRC 0.
- Open: sourcing, firmware notes, 3D fit, bench (`docs/research.md` §5, §7.6).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Bread Modular is read-only.
No merges, pushes, orders or uploads.
