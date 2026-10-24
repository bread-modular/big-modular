# USB-AUDIO agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **Schematics** (ERC 0 both): carrier S2 `hardware/usb-audio.kicad_sch` (±12 V power, CS4270 codec
  as I2S master at 192 kHz, 2 DC-coupled ±5 V input chains and 2 output chains with 0..1 volume pots,
  U4 / U7 OPA1678 pot-wiper followers (S2 split of the S1 quad), U5 OPA1678 gain, U6 OPA1679 drivers,
  BOOT/RESET, SWD, MCU-board headers J6/J7) and MCU board S1
  `hardware/usb-audio-mcu.kicad_sch` (CH32V307RCT6 USB HS, vertical HRO USB-C, 8 MHz HSE, J102/J103).
- **Carrier R2 (manual, divide and conquer, 2026-10-24)**: codec-centred re-placement and re-route
  (`research/route/r2.py` stages 0-11, from the R1 board `research/route/r1-final.kicad_pcb` = commit
  11ca3af). 6HP, 4 layers, 29 x 110 mm: F signal, In1 GND, In2 +3V3 plane with a +5VA island under the
  codec / U5 / U6 area, B signal + all SMD. The codec's analog row faces down with U5 (DAC gain) under
  its DAC end and U6 (ADC drivers + references) under its ADC end; U4 by RV1/RV2, U7 by RV3/RV4. DAC_A/B
  7.8 / 2.3 mm (R1 51 / 57), VREF_OUT 20 mm (R1 75), IN1 38 mm (R1 63); the long runs left are U5
  outputs (low-Z) to the OUT pots and DC references. One 3.1 mm -12V_F hop on In2 (U5 V-, walled in by
  the I2C pair on F); both In2 zones stay one piece. Jacks, pots, J6/J7, power corner unchanged.
- **MCU board R1** (4 layers, 29 x 29.55 mm) with J102/J103 1x10, fully routed (`research/route/mcu.py`).
- Native DRC: 0 violations / 0 unconnected / parity 0 on both boards (copper-edge rule 1.0 mm), no vias
  in SMD pads, no In1 tracks, planes one piece; shared `check` gate clean on both. Courtyards >= 1 mm
  from the edge, closest SMD pad to a pot/jack pad 2.03 mm (U6 to RV1). Panel DRC 0.
- **JLCPCB export** (2026-10-24) in `jlcpcb/main/` (carrier, bottom Economic, + panel) and
  `jlcpcb/mcu/` (top Economic), one manifest each (declared in both profiles). C20-C23 (C0G 0603)
  and R1 (2512) are Extended R/C: user decision open. See `jlcpcb/README.md`.
  Not supplier-accepted, no firmware.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` (carrier) and
`tools/kicad-project-mcu.json` (MCU board) for doctor/check. Raw reports go in the ignored
`research/`. SMD placement and routing are manual, group by group, straight on the boards (root
`AGENTS.md`); once that starts, do not rerun `tools/build_layout.py`. No merges, pushes, orders or uploads.
