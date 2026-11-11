# multi-mix agent entry point

Read the root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`. Paths here
are relative to the module.

## Current state

- **S3 schematics** (2026-11-10, `docs/research.md` sections 5 and 9), ERC 0 both: carrier
  `hardware/multi-mix.kicad_sch`, 232 parts (modules/usb-audio-max power and PCM3168A at 48 kHz; 4 channel +
  2 return inputs, AC-coupled; SEND A / SEND B / MAIN outputs on U7 and host-assigned USB 1 / USB 2 outputs
  (DAC4/DAC5, J9/J10) on U8 OPA1678; 15 RV09 pots on a 74HC4067, RV1-RV3 on their own R65/C50 +3V3_POTB filter;
  NORM patch-detect probe; CLK OUT (J6) / CLK IN (J7) 2x5 IDC daisy-chain clock link, clock only; MCU strips
  J12/J13, 2 x 1x12) and MCU board `hardware/multi-mix-mcu.kicad_sch`, 27 parts (usb-audio-max MCU board with
  the mux, probe and LINK_N pins, I2C pull-ups and the DIN1 series resistor; strips J112/J113). Jack and pot
  references are modules/4mix's.
- **R1 routing, both boards** (2026-11-10, manual divide and conquer, batches in `research/route/`): carrier
  and MCU board native DRC 0 / unconnected 0 / parity 0, no exclusions, no vias in SMD pads (codec thermal vias
  only), no In1 tracks, courtyards >= 1.00 mm from the edge, SMD >= 2 mm from pot/jack pads. Carrier: all 200
  SMD parts on B, In1 GND, In2 +3V3 with a +5VA island (codec, input drivers, finger to the regulator) and two
  +3V3_C islands. MCU board: single-sided (every part on F, user), outline extended to the carrier top with a
  notch for MS3 and the IN4-jack notch, USB-C unchanged (X84.1 Y21), 3225 crystal. J15 SWD and SW1/SW2 moved on
  the carrier B side (`docs/geometry.json`). Through-hole positions are P3's and fixed (user).
- **R2 fab-review fixes** (2026-11-11, `docs/research.md` section 10, batches in the ignored `research/fab-fix/`):
  carrier schematic S4 (C21/C27 1 uF 0402 C52923; nets `REF_NR`, `CODEC_ADR1` labelled), codec supply caps at
  their pins and VREF 10 uF caps under pins 59/60, MCU USB per modules/usb-audio (`tools/check_usb.py` passes,
  In2 GND island, stackup recorded), SCKI 52 mm, Q1 B tab pour + thermal vias, no right-angle corners,
  1.0 mm service silk + J15 legend. Both boards ERC 0 / DRC 0 / unconnected 0 / parity 0; shared `check`
  ref/pin/net equal on both (standoffs: blank reference + `MechanicalID`, as usb-audio-max).
- **Datasheet review** (`docs/research.md` 6a): CH32V307 I2S rated 8 MHz < 12.288 MHz BCK -> SPI-slave fallback
  pins tied on the MCU board (PB14 on PB15, PA15/PB3 on PB12/PB13); PCM3168A slave BCK duty margin 5.7 ns
  (4-unit limit), no SCKI phase rule, ADC/DAC reset to slave, SEAD resets to differential.
- Open: J101 courtyard 0.53 mm to the MS3 notch, MS3 courtyard 0.98 mm to the edge (user decision); next panel re-check, JLCPCB export, firmware,
  bench. Do not rerun `tools/build_layout.py` (it
  would park the SMD parts again).

## Boundaries

Shared tools stay in `../../opt/`. `tools/kicad-project.json` / `kicad-project-mcu.json` are the shared-tool
profiles of the two boards (shared `check` runs since P1).
Raw reports go in the ignored `research/`. Placement and routing are manual, group by
group, straight on the boards (root `AGENTS.md`); the through-hole parts stay where they are. No merges, pushes, orders or uploads.
