# USB-AUDIO agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S1 schematics** (ERC 0 both): carrier `hardware/usb-audio.kicad_sch` (±12 V power, CS4270 codec
  as I2S master at 192 kHz, 2 DC-coupled ±5 V input chains and 2 output chains with 0..1 volume pots,
  OPA1679/OPA1678, BOOT/RESET, SWD, MCU-board headers J6/J7) and MCU board
  `hardware/usb-audio-mcu.kicad_sch` (CH32V307RCT6 USB HS, vertical HRO USB-C, 8 MHz HSE, J102/J103).
- **R1 routing (manual, divide and conquer)**: 6HP; carrier (4 layers, 29 x 110 mm: F signal, In1 GND,
  In2 +3V3, B signal + all SMD) with jacks/pots in four rows (IN: jack, pot; OUT: pot, jack), J1 power,
  J8 SWD, SW1/SW2 on B, 1x10 strips J6/J7 (pin 10 GND); MCU board (4 layers, 29 x 27 mm) with J102/J103
  1x10. Both fully routed. Batch scripts in `research/route/` (`carrier.py` stages 1-6, `mcu.py`).
- Native DRC: 0 violations / 0 unconnected / parity 0 on both boards (copper-edge rule 1.0 mm), no vias
  in SMD pads, no In1/In2 tracks, planes one piece; shared `check` gate clean on both. Panel DRC 0.
  Not supplier-accepted, no firmware.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` (carrier) and
`tools/kicad-project-mcu.json` (MCU board) for doctor/check. Raw reports go in the ignored
`research/`. SMD placement and routing are manual, group by group, straight on the boards (root
`AGENTS.md`); once that starts, do not rerun `tools/build_layout.py`. No merges, pushes, orders or uploads.
