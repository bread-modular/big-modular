# 16bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and `docs/research.md`.
Module paths are module-relative.

## Current state

- **S3 schematic** (`hardware/16bit.kicad_sch`, ERC 0, wired blocks + power symbols):
  Bread Modular 16bit (RP2350A, W25Q128, APS6404L PSRAM, PT8211) on Eurorack 6HP. TS MIDI in
  with the 8bit/MIDI V2 NPN front end and JP1 (shipped open), two bipolar CV
  inputs, each normalled to +5V through its own 50k attenuator (RV1/RV2 -> TL072 -> level shift ->
  MCP6002 on +3V3 -> ADC0/1), two 50k knobs RV3/RV4 (-> ADC2/3), no mux,
  6x6 mm THT mode button (8bit SW1, GPIO12), 3 mm red mode LED (GPIO13 PWM, 1k),
  TL074 ±5 V outputs (gain 6.1), AMS1117-5.0/-3.3 from +12 V, USB-C data only.
- **S5 placement + R2 manual routing (2026-10-21)** (`hardware/16bit.kicad_pcb`, 4 layers):
  R1 TraceMaker copper (123 in-pad vias, POFV) was stripped and the board placed and routed by
  hand, group by group. **No vias in SMD pads** (dogbone to a via clear of the pad), so it is a
  plain tented 4-layer board, no POFV. Shared check ERC 0 / DRC 0 / unconnected 0 / parity 0;
  In2 +3V3 one piece, In1 GND one main piece + two spoke-tied 2.6 mm² pieces at J6. B silk
  labels BOOT / RESET and the JP1 MIDI legend (`Code.md`). The board owns placement and copper:
  do not rerun `tools/build_layout.py` over it. 6HP FR4 panel DRC 0.
- **JLCPCB export (2026-10-21)** in `jlcpcb/` (`jlcpcb/README.md`): LCSC/MPN fields from
  `SOURCING` in `tools/build_schematic.py`, copied onto the routed board's footprints (fields
  only). Bottom-side Economic, 86 parts / 43 rows; R/C all Basic except R9/R10 27 Ω. U4 =
  TM8211-TA2302 (BM 16bit-5v), L1 = cjiang FTC201610S3R3MBCA (unmarked: check the core
  regulator at bring-up), U3 = Adafruit 4677 C17430771 (user-stocked ESP-PSRAM64H, same
  APS6404L pinout). Not supplier-accepted.
- **Firmware (2026-11-02)** in `firmware/` (`firmware/README.md`): BM 16bit 1.6.0, six apps,
  JP1 `p`/`d` builds over the shared `opt/rp2350-tools`; compiled, not bench-tested.
  Polysynth (2026-11-06): P1 selects one of 16 wavetables or Noise (Kimura Taro CC0 tables
  via the open-vital-resources Vital conversion + generated Classic / PWM; classic synths, FM,
  complex; no filter-sweep tables; fully down = Classic, P2 morphs square -> saw -> tri -> sine;
  set-waveform removed; top = Noise, P2 brown -> pink -> white -> blue -> digital -> crackle,
  made per voice), P2 moves the position; tables from `16bit/tools/build_wavetables.py`.
  Wavetables play at exact pitch (BM whole-hertz notes beat in chords); output auto level
  (polyphony gain + limiter, as the 32bit polysynth) replaces BM's fixed sum / 4.
  Filter (2026-11-06): Vital-style TPT ladder (`polysynth/poly_filter.h`) replaces BM
  FilterFX: exact cutoff, passband held at 0 dB at every resonance (BM lost 3-7 dB at the
  power-on resonance from open down to ~430 Hz), exponential cutoff / env depth, full
  resonance range; MCC Banks B / C fold onto Bank A.
  Sampler (2026-11-08): P1 = group A kick drive (techno soft clip, before P3), P2 = resonance
  of the group A P4 highpass as a DJ filter (2026-11-08, Pioneer DJM style: 24 dB/oct,
  +14 / +20 / +30 dB at the cutoff at 1/4 / 1/2 / full, no peak up to 500 Hz (no mud), fading
  in steeply to full at 1.2 kHz and up; P4 20 Hz..20 kHz on a two-part exponential curve that
  reaches 1.2 kHz (full resonance) at the 25 % mark (rev 6), squelching, peak guard); group B unfiltered again; P1 / P2
  fully down = the earlier output bit for bit (`sampler/sampler_dsp.h`, `tools/sim_sampler.cpp`).
- Open: firmware app mapping of P1/P2, 3D fit, bench (`docs/research.md` §5, §7.6).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Bread Modular is read-only.
No merges, pushes, orders or uploads.
