# 32bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S3 schematic** (2026-11-15, `hardware/32bit.kicad_sch`, ERC 0, netlist asserted, 116 parts / 118 nets):
  the ESP32-S3-WROOM-1U-N16R8 module (JLCPCB Standard PCBA only) is replaced by its contents, all
  Economic: **U1 ESP32-S3R8** (QFN-56, 8 MB octal PSRAM inside, C2913194), **U2 W25Q128JVSIQ** 16 MB
  flash on VDD_SPI (C97521, Basic; R7 0R on the clock, C17), **Y1 40 MHz** 3225 crystal (C5210647; R6 0R,
  C9 / C10 12p), supply decoupling C5 / C12 / C13 (+3V3_ESP32 behind FB1, C6), C14 / C15 (+3V3), C16
  (VDD_SPI), R8 BOOT pull-up. Same GPIOs and memory map as S2, same firmware. LNA_IN open: the radio is
  never used. Everything else is S2: Bread Modular 32bit-5v on Eurorack 6HP, TS MIDI in (16bit NPN front
  end, JP1), two audio inputs (TL074 followers, no IN R normal), two CV inputs with 50k attenuators,
  TL072 +/-5 V outputs, MODE button (GPIO8) + LED (GPIO18), USB-C data + BOOT/RESET, AMS1117-5.0/-3.3.
  Firmware-visible pin changes since Bread Modular are in `docs/firmware-pins.md` (none in S3).
- **R3 routed carrier** (2026-11-15, `hardware/32bit.kicad_pcb`, 4 layers: F signal / In1 GND / In2 +3V3 /
  B signal): the MCU area re-placed and re-routed by hand (root `AGENTS.md` divide and conquer; batch
  scripts and DRC reports in `research/s3/`), the rest is R2 copper. U1 at X109.3 Y134.6 on B, flash above
  it, crystal and VDDA caps on its right, VDD3P3 caps below, FB1 + C6 left of them. I2S data/clocks and USB
  wrap around the flash on F to via staircases beside the left pin column; MCLK stays on B; EN, BOOT and
  the CV ADC lines enter from the south. Native DRC 0 / unconnected 0 / parity 0, no exclusions; 760
  tracks / 130 vias, none in or touching SMD pads; In1 GND and In2 +3V3 one piece each (saved fills), no
  new inner-layer tracks. 2 mm hand-solder clearance kept: new parts FB1 2.005 mm, C6 2.006 mm from J4;
  the four user-accepted R2 parts (R5 1.33, C27 1.62, R55 1.63, C46 1.75 mm) are unchanged.
- JLCPCB export in `jlcpcb/` re-exported from S3 / R3 (2026-11-15, carrier only; 103 parts / 43 rows,
  bottom, **Economic PCBA**; not supplier-accepted); shared `check` manifest equal.
- **Firmware (2026-10-31)**: `firmware/polysynth` (ESP-IDF v5.5.1), 9-voice MIDI polysynth after
  the BM 16bit polysynth on the BM 32bit-5v drivers with the R1 pins; CV1 = release, CV2 = one-knob
  filter (0 = bypass), MODE = saw + 7 build-time wavetables (saved in NVS, LED brightness shows it).
  `firmware/setup.sh|compile.sh|flash.sh p|d` over the shared `opt/esp32-tools`.
  Builds and host DSP tests pass; not bench-tested. See `firmware/README.md`.
- **fxrack firmware (2026-11-04)**: `firmware/fxrack`, the BM 32bit-5v fxrack app (L: delay CV1 time /
  CV2 feedback -> hall reverb on MIDI CC 20 decay 0.3..20 s / CC 21 mix (2026-11-06: diffuser + 8-line modulated FDN replaces BM's
  classic comb reverb; host render/analysis in `firmware/fxrack/tools`, outputs in `research/fxrack-reverb/`); R: short comb on CC 22/23; no pipe delay; MODE press = 4-bar CV1/CV2 + CC 20..23 motion
  recorder on MIDI clock, as 8bit/16bit) on the
  32bit drivers; PSRAM on for the delay buffers; BM all-pass buffer overrun fixed. `./compile.sh p|d fxrack`; `./flash.sh [p|d] [fxrack|polysynth] [port]` asks for the firmware (Enter = polysynth) when none is given, as the 16bit `flash.sh`.
  Builds (p, d) and host tests (ASan) pass; not bench-tested. See `firmware/README.md` section fxrack.
- **master firmware (2026-11-22)**: `firmware/master`, end-of-chain processor for a live set in place of
  the user's DAW chain: IN L kick (sub cut, look-ahead limiter), IN R mix (low cut, 3-band dynamics keyed
  by the kick's bands), parallel compressor fed from both, then glue compressor (2 / 4 / 10, stepped
  attack / release, auto release, range, dry / wet, soft clip) -> low / high cut -> look-ahead limiter ->
  mono on both outputs. 75 settings in one table (`main/include/ms_params.h`), set from
  `firmware/master/web/index.html` over the USB-C port (Web Serial, text protocol `ms_proto.h`; demo mode
  without the module) and saved in NVS on request. The page is a mixer of four channel strips (KICK, MIX,
  PARALLEL, MASTER: trim knob, effect slots, parallel send, fader + meters); a click on a slot shows its
  settings in the panel under the mixer (2026-11-22, user). Ranges and names come from `desc`, the page's
  `STRIPS` table places them; `web/run.sh` serves it on port 3000 and stops whatever listens there first. New in the
  drivers: 24-bit codec words, 16-frame I2S blocks, 240 MHz. No MIDI / JP1: `./compile.sh master`,
  `./flash.sh master [port]`. Latency about 4.8 ms as shipped (buffers 1.1..1.45 ms + ~1 ms assumed for
  the codec + 1.0 / 1.5 ms look-aheads), not measured. Builds (328 KB), host tests pass (585 checks),
  page checked in headless Chromium (`firmware/master/tests/web_check.mjs`, not part of `make`), QEMU count 1120 / 1360 instructions per sample (factory / all on);
  **not bench-tested, not heard**. `tools/ms_render` runs the chain over WAV files. See
  `firmware/README.md` section master.
- Open: JLCPCB preview (U1 QFN pin 1, U2, Y1 rotation), bench (first power-up of the bare-chip circuit:
  40 MHz start-up, flash boot, PSRAM; U8 thermal, codec levels, firmware). master on the module: 24-bit
  codec words + 16-frame blocks, CPU load and U8 heat at 240 MHz, measured latency, port open / close
  resets. The back USB-C is blocked by the case rail: the printed 8HP riser
  `mechanical/case/print/accessories/usb-riser/` lifts the module 18 mm so a plug passes over the back rail
  (2026-11-22, CAD + slicer checked against a stand-in of this module, not printed; the module sits 7.5 mm
  from the riser's left edge, the plug overmold ends 0.15 mm from the carrier's top edge in the model). Radio never used; firmware must
  not start Wi-Fi / BT.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Bread Modular is read-only.
No merges, pushes, orders or uploads.
