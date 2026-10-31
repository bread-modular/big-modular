# 32bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S2 schematic** (`hardware/32bit.kicad_sch`, ERC 0, wired blocks + labels): Bread Modular
  32bit-5v (ESP32-S3-WROOM-1U-N16R8, ES8388) on Eurorack 6HP. TS MIDI in (16bit NPN front end,
  JP1), two audio inputs (TL074 followers, no IN R normal, firmware handles mono), two CV inputs with 50k
  attenuators (16bit chain), TL072 ±5 V outputs, 6x6 mm MODE button (IO8), 3 mm red LED (IO18),
  USB-C data + BOOT/RESET, AMS1117-5.0/-3.3 from +12 V. R1 layout swap: CV1 = U7B/U6B,
  CV2 = U7A/U6A. Firmware-visible pin changes are logged in `docs/firmware-pins.md`.
- **R1 routed carrier** (`hardware/32bit.kicad_pcb`, 4 layers: F signal / In1 GND / In2 +3V3 / B
  signal): every part placed and routed by hand (root `AGENTS.md` divide and conquer; batch scripts and
  DRC reports in `research/r1/`). Native DRC 0 / unconnected 0 / parity 0, no exclusions; no vias in SMD
  pads, no tracks on In1, both planes one piece. USB-C + BOOT/RESET as 16bit; 6HP FR4 panel DRC 0.
  Firmware-visible changes (CV ADC IO1/IO2, I2C IO38/IO39, codec LIN2/RIN2) in `docs/firmware-pins.md`.
- **R2 (2026-10-22)**: 2 mm hand-solder clearance (every SMD pad >= 2.0 mm from jack/pot pads) except
  four user-accepted parts: the user moved R5, C27, R55 and C46 for edge margin and kept them there
  (option A, 2026-10-22): R5 1.33 mm from RV2, C27 1.62 / R55 1.63 / C46 1.75 mm from J5. Everything
  else >= 2.02 mm. SMD parts moved/re-routed by hand, jacks/pots/panel unchanged (`docs/research.md`
  section 7, scripts in `research/r2mm/`). DRC 0 / unconnected 0 / parity 0. B silk MIDI JP1 labels
  (P/D + legend, as modules/16bit).
- JLCPCB export in `jlcpcb/` re-exported from R2 (2026-10-22, not supplier-accepted); manifest equal.
  U1 is Standard-PCBA only: user chose Standard PCBA (2026-10-22).
- **Firmware (2026-10-31)**: `firmware/polysynth` (ESP-IDF v5.5.1), 9-voice MIDI polysynth after
  the BM 16bit polysynth on the BM 32bit-5v drivers with the R1 pins; CV1 = release, CV2 = one-knob
  filter (0 = bypass), MODE = saw + 7 build-time wavetables (saved in NVS, LED brightness shows it).
  `firmware/setup.sh|compile.sh|flash.sh p|d` over the shared `opt/esp32-tools`.
  Builds and host DSP tests pass; not bench-tested. See `firmware/README.md`.
- Open: bench (U8 thermal, codec levels, firmware). Radio never used.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Bread Modular is read-only.
No merges, pushes, orders or uploads.
