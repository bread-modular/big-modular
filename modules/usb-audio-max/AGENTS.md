# USB-AUDIO-MAX agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S2 schematics, final** (2026-11-05), ERC 0 both: carrier `hardware/usb-audio-max.kicad_sch` (±12 V power,
  2 x 33R + discrete LM358/BCP56 regulator (REF5050 reference, MMBT3904 current limit) -> +5VA (precision DC
  reference for every channel), FB2 + 2.2R input filter -> TPS562208 FCCM buck (~580 kHz at every load, molded
  inductor) -> +3V3 (user: buck again in S2; ngspice in `docs/research.md` 2a), PCM3168A as TDM clock master with
  SCKI 24.576 MHz, 6 DC-coupled inputs (100k -> OPA1679 inverting driver on +5VA, single-ended ADC),
  8 DC-coupled outputs (OPA1679 difference amplifiers on ±12 V, 2 x 2k), VCOM/VB references, BOOT/RESET,
  SWD, MCU-board headers J2/J3) and MCU board `hardware/usb-audio-max-mcu.kicad_sch` (modules/usb-audio
  MCU S1 + SPI1 on PA4-PA7 for the second TDM line pair; J102/J103; circuit unchanged since S1). Every LCSC
  code re-checked live (49, all Economic-eligible).
- Footprint library built (`tools/import_footprints.py`; pcbnew gives new UUIDs on every run, geometry and
  sources pinned in `PROVENANCE.json`); no PCBs, panel, export or firmware.
- Panel 8HP (user decision, 2026-11-05). Open: jack layout, placement/routing (buck layout rules in
  `docs/research.md` section 7), firmware (96 kHz SPI1 path is untested on the CH32V307).

## Boundaries

Shared tools stay in `../../opt/`. Raw reports go in the ignored `research/`. Placement and routing
are manual, group by group, straight on the boards (root `AGENTS.md`). No merges, pushes, orders or
uploads.
