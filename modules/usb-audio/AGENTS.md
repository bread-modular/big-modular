# USB-AUDIO agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **Latest scoped repair: carrier S3/R3, MCU S1/R2** (2026-10-24), superseding the
  S2/R2 and MCU R1 baselines below. R36/R38 and R37/R39 are Basic 2k/0.25 W 1206
  pairs in parallel (1k/0.5 W per output). USB active paths have two signal vias
  per polarity, In2 GND beneath B-side USB, an explicit JLC04161H-7628 stackup and
  USB_HS geometry on both sides of U102. See `docs/usb-output-fix.md` and run
  `tools/check_usb.py` as well as native checks. No existing footprints moved.
  Other review findings are deferred by the user, not proven resolved. Current
  exports: carrier 74 bottom placements / MCU 23 top placements; no supplier acceptance.

- **USB brace v5** (printed bracket only, no PCB change): same **two-hole v4 panel**
  and M3x6 screw positions. User hex nut measured 5.5 mm AF x 2.7 mm high. New top-edge
  loading channels (6.0 mm AF terminal / 3.1 mm height / flared mouth) replace v4's
  obstructed rear-loading route; load nuts before fitting the bracket. Positively
  captive only after screws installed. Rear tongue extends **3 mm** into the gap,
  X6–24 / end Y13, relieved 0.35 mm beyond the unchanged 0.8 mm bare-edge bearing strip.
  No increase in PCB separation. Retains 5.6/5.8/6.0 mm front-stop options, rear jaw
  7.75 mm from panel back. Use `usb-brace-v5-stop*.stl`; **no panel reprint needed**
  if already using `usb-audio-front-panel-v4-print.stl` (STL hash unchanged).
  Checks include measured nuts and allowance gauges through 41 loading positions,
  81 bracket insertion positions, 13 board-travel positions, header plastic and
  underside solder/surface envelopes. Native mechanical checks pass, not physical
  fit/strength. 6.0 mm does NOT fit nominal 5.9 mm gap; start with 5.6 as fit test.
  Only 0.2 mm rail margin; actual solder protrusions and cable boot need checking.
  See `panels/README.md`. No longer screws: M3x8 can hit the PCB. No print started.

### Prior placement/routing baselines

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
  Not supplier-accepted.
- **Firmware 1.1.0** (2026-11-11) in `firmware/` (read `firmware/README.md`): TinyUSB UAC2 2 in / 2 out,
  48 / 96 / 192 kHz, CDC console, DFU bootloader. Loopback-tested on Linux on the first board
  (OUT 1/2 -> IN 1/2); macOS / Windows not tested here.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` (carrier) and
`tools/kicad-project-mcu.json` (MCU board) for doctor/check. Raw reports go in the ignored
`research/`. SMD placement and routing are manual, group by group, straight on the boards (root
`AGENTS.md`); once that starts, do not rerun `tools/build_layout.py`. No merges, pushes, orders or uploads.
