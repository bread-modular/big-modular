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
  sources pinned in `PROVENANCE.json`).
- **S1 placement, 10HP** (2026-11-06; user: USB-C on top, IN 1-6 in two rows of three, OUT 1-8 in three rows,
  ninth spot empty, no schematic changes, 10HP if 8HP is too tight). Fit study in `docs/research.md`
  section 5 (`tools/fit_density.py`): 8HP 64 % SMD density with no room for the SOIC-14s between the jack
  columns, 10HP 45 % (as modules/usb-audio). `tools/build_layout.py` built the carrier
  `hardware/usb-audio-max.kicad_pcb` (49.5 x 110 mm, 4 layers: 14 jacks, J1 power in the ninth spot, J2/J3
  strips, J4 SWD + BOOT/RESET top left on B; every other SMD part parked right of the board), the MCU board
  `hardware/usb-audio-max-mcu.kicad_pcb` (modules/usb-audio's 29 x 29.55 mm outline, centred: USB-C and
  J102/J103 placed, rest parked) and the panel `panels/front-pcb/usb-audio-max-panel.kicad_pcb`.
  Native DRC 0 violations / parity 0 on both boards (432 / 88 unconnected: nothing routed), panel DRC 0;
  courtyards >= 1.06 mm from the edges. Nothing routed, no export, no firmware.
- Open: group-by-group SMD placement and manual routing of both boards (floorplan proposal and buck layout
  rules in `docs/research.md` sections 5 and 7); firmware (96 kHz SPI1 path is untested on the CH32V307).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` (carrier) and
`tools/kicad-project-mcu.json` (MCU board) for doctor/check. Raw reports go in the ignored
`research/`. Placement and routing are manual, group by group, straight on the boards (root
`AGENTS.md`); once that starts, do not rerun `tools/build_layout.py`. No merges, pushes, orders or
uploads.
