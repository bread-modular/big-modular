# 32bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S4 (2026-11-23; docs/research.md sections 9.1, 9.2)**: the board pair below replaces S3 in
  `hardware/`: **carrier S4 / R2** `hardware/32bit.kicad_{sch,pcb}` (modules/usb-audio S5 carrier with its routed
  copper: CS4272 clock master, NE5532 stages, AMS1117-5.0 +5VA; volume pots out of the audio path; RV1 / RV2
  control pots, MODE button + LED; R1 22R for the ESP32-S3 +3V3 budget; MS1 / MS2 M3x10 standoffs as usb-audio
  P2) and the **ESP32-S3 MCU board S1 / R2** `hardware/32bit-mcu.kicad_{sch,pcb}` (ESP32-S3R8 + W25Q128 + 40 MHz,
  USB-C on the panel, soldered on J6 / J7). Both hand-routed (`research/s4/`), ERC 0 / DRC 0 / unconnected 0 /
  parity 0, no exclusions, no vias in SMD pads; shared `check` clean, manifests equal.
  S4 GPIO map in `docs/firmware-pins.md`. **S4 JLCPCB export in `jlcpcb/` (2026-11-23, `jlcpcb/README.md`)**:
  two orders, no panel (`main/` carrier 88 parts / 33 rows bottom Economic + FR4 panel, `mcu/` 25 / 14 top
  Economic), every code live-checked, no pre-order part; not supplier-accepted.
  **Fab review 2026-11-23 (uncommitted, research.md 9.2, `jlcpcb/README.md`):** two fixes, `main/` re-exported
  (BOM / CPL unchanged). **Carrier R2**: U2 AMS1117-3.3 drops 0.71..0.79 W with the ESP32-S3
  load and sat on a bare tab pad; seven +3V3 vias beside the tab into In2 + a 35 mm2 B patch and 45 mm2 on F
  (`research/fab-review/t01.py`; 753 tracks / 124 vias, DRC 0 / unconnected 0 / parity 0). **Panel P2**: USB-C
  slot 9.5 -> 11.0 x 5.2 mm (the 9.5 slot's round ends cut 0.034 mm into the shell's upper corners); FR4 +
  printed panel regenerated. **MCU board R2 (user: no extra PCB cost)**: the nine thermal vias in the U101
  exposed pad drilled 0.3 mm instead of KiCad's 0.2 mm (0.5 mm pads and positions kept; library footprint,
  `tools/import_footprints.py` and the project's 0.3 mm minimum-hole rule updated, `research/fab-review/t02.py`),
  so no hole on either board is under 0.3 mm; ERC 0 / DRC 0 / unconnected 0 / parity 0, `mcu/` re-exported
  (BOM / CPL unchanged). `docs/fit/` (assembly renders, ERC / DRC JSON), the schematic PDFs, `Code.md` and
  `README.md` now describe S4. Open: CS4272 driver in `master`, JLCPCB preview, bench (U2 heat first). **Everything from here down describes S3 (ES8388) and is history once S4 is accepted.**
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
- S3 / R3 JLCPCB export (2026-11-15, carrier only; 103 parts / 43 rows, bottom, **Economic PCBA**; not
  supplier-accepted): replaced by the S4 set, in git history.
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
- **master firmware (2026-11-22, 0.3.0 2026-11-23)**: `firmware/master`, end-of-chain processor for a live
  set in place of the user's DAW chain: IN L kick (filter, look-ahead limiter), IN R mix (filter, 3-band
  dynamics keyed by the kick's bands), parallel compressor fed from both, then glue compressor (circuit
  model of the analog VCA bus compressor since 0.2.0: feedback detector, RC timing with the G series
  two-capacitor release A, gain cell colour) -> filter -> look-ahead limiter -> mono on both outputs.
  **0.3.0 (user, 2026-11-23)**: the sub cut / low cut / main cuts are one filter device per strip (low cut +
  high cut, each on / off, 10 Hz..20 kHz, resonance 0.5..6, 12 / 24 / 48 dB/oct; 0.2.x names `k_hp_*`,
  `m_hp_*`, `eq_*` still load, also over `set`); the effects of each strip run in any order (`k_order`,
  `m_order`, `o_order`, all six master orders; the multiband key stays at the kick limiter's input);
  both limiters have auto release (two-stage program-dependent: fast 30 ms to a slow stage with 100 ms
  attack / 1 s release; Ableton does not publish theirs). 95 settings in one table
  (`main/include/ms_params.h`), set from `firmware/master/web/index.html` over the USB-C port (Web Serial,
  text protocol `ms_proto.h`; demo mode without the module) and saved in NVS on request. **Page (0.3.0)**:
  mixer of four strips on top, the selected effect in a fixed 400 px panel under it (graph + Ableton-style
  knobs: filter response with draggable L / H points, limiter / compressor reduction history, static
  curves with the working point, glue reduction needle, multiband bands with draggable splits and live
  reduction), connection and settings buttons in a side panel on the right, slots dragged up / down to
  reorder, grey surfaces + one amber accent. Ranges and names come from `desc`, the page's `STRIPS` table
  places them; `web/run.sh` serves it on port 3000 and stops whatever listens there first. New in the
  drivers: 24-bit codec words, 16-frame I2S blocks, 240 MHz. No MIDI / JP1: `./compile.sh master`,
  `./flash.sh master [port]`. Latency about 4.8 ms as shipped (buffers 1.1..1.45 ms + ~1 ms assumed for
  the codec + 1.0 / 1.5 ms look-aheads), not measured. Builds (0.3.0, 332 KB), host tests pass (778
  checks), page checked in headless Chromium (`firmware/master/tests/web_check.mjs`, not part of `make`),
  QEMU count 1165 / 1735 instructions per sample (factory / all on); the demo loop run through the chain
  in QEMU (`firmware/master/tools/cpu-bench/audio.sh`) equals the host render within 8 steps of 24 bits;
  0.2.0 was heard on the built board (noise at high volume, see the bench notes), **0.3.0 not flashed,
  not heard**. `tools/ms_render` runs the chain over WAV files. See `firmware/README.md` section master.
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
