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
- **P6 panel + R3 manual routing (2026-11-15, user direction 2026-11-14)**: OUT jacks at the very
  bottom (Y110.4, X7.5 / X22.5), MODE (record) button above OUT L (X7.5, Y98.0), MODE LED on the
  same row 13.5 mm to its right (X21.0; user 2026-11-15: apart as in R2, where it was 20 mm; X21.0
  is the limit beside the J6 header pads, 1.05 mm),
  power header J6 upright at the right board edge (pins Y91.7..101.86, -12 V at the bottom), MIDI
  jack 0.95 mm up (Y16.55) and CV jacks 1.3 mm up (Y30.7: as far as the MIDI jack courtyard and
  the top edge allow), RV3/RV4 2.5 mm down (Y80.0, pot rows 31.5 mm apart). R2 copper kept above
  the output amp (board cut at Y75.75 and stretched 2.5 mm, nine crossing tracks jogged); the
  band below it was re-placed and re-routed by hand: regulators U8/U9 stacked between the OUT
  jacks, D2 / C1 / C2 + R20 in the centre, R33 between D2 and the LED, R27 / C35 above the LED, D3 + VREF
  divider right of OUT R, C3 / C21 / C19 / C4 left of OUT L, +5V / LED / BUTTON on F down the
  right edge and across between the OUT R pads. Shared check ERC 0 / DRC 0 / unconnected 0 /
  parity 0, no exclusions; 147 vias, none in an SMD pad; In2 one piece, In1 as R2 (the two
  2.6 mm² pieces sit between the J6 GND pins). Every re-placed SMD pad is >= 2.03 mm from pot /
  jack pads and every new courtyard >= 1.0 mm from the edge; the R2 parts kept in place are as
  close as before (closest C31 0.225 mm to the RV4 pins; J2 / J3 courtyards 0.2 mm from the
  edge). U8's caps are farther than in R2 (C1 ~11 mm, C3 ~8.5 mm of track): check +5V at
  bring-up. 6HP FR4 panel regenerated (`tools/build_layout.py panels`), DRC 0, holes checked
  against the carrier; printed panel rebuilt. Replay scripts in the ignored `research/p6/`
  (`s04_led.py` = the LED move). Solder D1 before J6: its legs come out beside the header body.
- **S5 placement + R2 manual routing (2026-10-21)** (`hardware/16bit.kicad_pcb`, 4 layers):
  R1 TraceMaker copper (123 in-pad vias, POFV) was stripped and the board placed and routed by
  hand, group by group. **No vias in SMD pads** (dogbone to a via clear of the pad), so it is a
  plain tented 4-layer board, no POFV. Shared check ERC 0 / DRC 0 / unconnected 0 / parity 0;
  In2 +3V3 one piece, In1 GND one main piece + two spoke-tied 2.6 mm² pieces at J6. B silk
  labels BOOT / RESET and the JP1 MIDI legend (`Code.md`). The board owns placement and copper:
  do not rerun `tools/build_layout.py` over it. 6HP FR4 panel DRC 0.
- **JLCPCB export (2026-11-15, P6 / R3)** in `jlcpcb/` (`jlcpcb/README.md`): re-exported from the
  P6 board and panel with the shared exporter; shared `check` manifest equal. LCSC/MPN fields from
  `SOURCING` in `tools/build_schematic.py` (board fields in sync, BOM byte-identical to the R2
  export). Bottom-side Economic, 86 parts / 43 rows; R/C all Basic except R9/R10 27 Ω. Live audit
  2026-11-15: classes unchanged, **L1 stock down to 53**, Y1 449. U4 =
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
  Sampler (2026-11-08): P1 = group A kick drive (techno soft clip, before P3; level held at the dry kick's, a low FDN rumble tail rising with the knob), P2 = resonance
  of the group A P4 highpass as a DJ filter (2026-11-08, Pioneer DJM style: 24 dB/oct,
  +11.5 / +17.5 / +26 dB at the cutoff at 1/4 / 1/2 / full, no peak up to 500 Hz (no mud), fading
  in steeply to full at 1.2 kHz and up; P4 20 Hz..20 kHz on a two-part exponential curve that
  reaches 1.2 kHz (full resonance) at the 25 % mark (rev 6), squelching, peak guard); group B unfiltered again; P1 / P2
  fully down = the earlier output bit for bit (`sampler/sampler_dsp.h`, `tools/sim_sampler.cpp`).
- Open: firmware app mapping of P1/P2, 3D fit, bench (`docs/research.md` §5, §7.6).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. Bread Modular is read-only.
No merges, pushes, orders or uploads.
