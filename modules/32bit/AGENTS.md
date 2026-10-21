# 32bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S2 schematic** (`hardware/32bit.kicad_sch`, ERC 0, wired blocks + labels): Bread Modular
  32bit-5v (ESP32-S3-WROOM-1U-N16R8, ES8388) on Eurorack 6HP. TS MIDI in (16bit NPN front end,
  JP1), two audio inputs (TL074 followers, no IN R normal, firmware handles mono), two CV inputs with 50k
  attenuators (16bit chain), TL072 ±5 V outputs, 6x6 mm MODE button (IO8), 3 mm red LED (IO18),
  USB-C data + BOOT/RESET, AMS1117-5.0/-3.3 from +12 V. R1 layout swap: CV1 = U7B/U6B,
  CV2 = U7A/U6A. Firmware-visible pin changes are logged in `docs/firmware-pins.md` (none yet).
- **S2 placement** (`hardware/32bit.kicad_pcb`, 4 layers): THT jacks/pots/MODE/LED/J6 placed,
  USB-C + BOOT/RESET as 16bit, OUT L/R at the side edges like IN/CV, U1 zone reserved (Dwgs.User), all other SMD parked right of the
  board. 6HP FR4 panel DRC 0.
- **R1 manual routing in progress** (root `AGENTS.md` divide and conquer, batch scripts and DRC
  reports in `research/r1/`): power entry, output stage, regulators, audio inputs, ES8388 codec and
  the CV section (U6 between the pots above IO9/IO10) are placed and routed; parity 0, no vias in
  SMD pads, no tracks on In1. Still open: ±12 V feeds to U7/U8, codec <-> ESP32 I2S/I2C, ESP32
  support parts, USB, MIDI, LED, button.
- Open: rest of the routing, U8 thermal (radio never used), sourcing check.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Bread Modular is read-only.
No merges, pushes, orders or uploads.
