# HATS agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md`, `docs/research.md` and
`docs/noise-in-protection.md`. Paths below are module-relative.

## Current state

- **S4 schematic (2026-11-08, user direction):** one STM32G071C8T6 U2 (modules/12bit support:
  C6/C7, FB1 + C24/C25 VREF+, C26 NRST, J11 1x5 SWD) replaces U2/U3 ATtiny1616 (R4/R5/J12 gone).
  DAC1 PA4 white noise, DAC2 PA5 velocity, PA2 gate, PA3 open hat, ADC PA1 NOISE TONE (C27) and
  PA6 CUTOFF (RV3 now a +3V3 divider, C28), PB0 TIM3_CH3 PWM -> R51 330R -> U11 VTL5C LED; U11 LDR
  with R50 51k across it replaces the RV3 rheostat (CUT_R to VMID_H). SW1 REC (PB4), R48/D6 REC LED
  (PB5). ERC 0, native netlist = `circuit()`.
- **R4 (2026-11-09)**: 4-layer carrier re-placed and re-routed by hand for S4 (In1 GND / In2 +3V3, all assembled SMD on B; SW1 REC + D6 REC LED on F at the bottom as modules/16bit). 636 tracks / 120 tented 0.3/0.6 mm vias, no vias in SMD pads, no inner tracks, inner planes one piece. ERC 0, unconnected 0, parity 0. DRC: the 18 U7 stacking items (17 still excluded, one U7 silk/RV4-lug exclusion no longer matches) + the new U11-under-RV1/RV2 stacking (10 `pth_inside_courtyard`, 10 `silk_over_copper`), **not excluded: awaiting user approval**. SMD-to-pot/jack >= 2.05 mm. P5 panel: 13 NPTH (REC button 4.2 mm at X6.3 Y114.45, REC LED X23.7 Y114.45, REC legend). JLCPCB export re-done (95 placements / 33 BOM rows), not supplier-accepted. STM32 firmware in `firmware/` (2026-11-09): BM NOISE + HIHAT ports, PWM cutoff vactrol, shared REC recorder (CUTOFF + NOISE TONE), JP1 p/d builds with `opt/stm32g0-tools`; compiled and host-tested, not run on hardware.
  Batch scripts and DRC reports: `research/s4/route/`. The S3/R3 bullets below are history.

- **S3 schematic:** Bread Modular NOISE + HIHAT, two ATtiny1616 sharing MIDI RX;
  protected NOISE IN normalling; AUDIO and HAT CV outputs with ENV LED.
- No recording controls: SW1, D6 and R48 removed; U2 PC2 and U3 PC2/PC3 are NC.
- R14 = 470k; new R49 = 22k in the jack-sense branch; D7 = BAV199 dual rail clamp.
  All other original circuit values and functional MCU pin assignments retained.
  Firmware clock/reference changes are explicitly outside this task.
- **R3 routed carrier** (2026-11-03): 4 layers, In1 GND / In2 +3V3, all 89 assembled SMD parts on B.
  498 tracks / 94 ordinary tented 0.3/0.6 mm vias, no vias in SMD pads or mask openings,
  no tracks on inner layers; each inner plane is one piece. ERC 0, unconnected 0, parity 0.
  DRC: only the U7-under-RV3 stacking (10 `pth_inside_courtyard` errors, 8 `silk_over_copper`
  warnings), user-approved exclusions via `tools/vactrol_exclusions.py` (2026-11-03; the shared
  gate still counts them). No ignored ERC/DRC rule severities.
- Actual copper setback >=1 mm; closest SMD-to-pot/jack pad gap 2.045 mm.
  RV1-RV4 courtyard-line bounding boxes are 0.815 mm from the edge: the existing
  user-approved pot-column exception, not an exception for copper.
- **P4 panel:** 11 NPTH holes (4 jacks, 4 pots, ENV LED, 2 rail holes). Shafts at Y41/Y75,
  34 mm row pitch. R3: all pots upright (RV3/RV4 no longer rotated); U7 lies on B under the
  CUTOFF pot (LOW/ACID pattern). The lower SMD (U6 VCA/filter, HPF and envelope parts) was
  re-placed into the freed bands and re-routed by hand; see `docs/research.md` (S3/R3).
  ENV LED D5 sits on the AUDIO OUT / HAT CV jack centre line, midway between them (body X15 Y102,
  rot 90, 2026-11-03; before that X15 Y105, X22.25 Y112.2 below J4, X26 Y93 beside it). U10 moved
  below the LED on B (KiCad 115/157.1); R42/R41 stand left of the LED, C22 below U10; U10 pins 2-6
  escape to vias under its body and run on F beside the LED; LED_A runs on F from R47.
  U1/D1/C3/C5 kept from the below-J4 step.
- `firmware/` (S4): one STM32 firmware, BM NOISE + HIHAT ports + CUTOFF vactrol PWM + shared
  CvRecorder (lanes CUTOFF, NOISE TONE), JP1 p/d builds (`MIDI_RX_INVERT`, USART1 RXINV), shared
  `opt/stm32g0-tools`. The vactrol LDR model and the BM delay-unit timing are estimates to re-fit
  on the bench. Compiled + host-tested, not run on hardware. See `firmware/README.md`. (The S3
  ATtiny ports were removed; they are in git history.)
- JLCPCB export in `jlcpcb/`: bottom Economic target, 89 placements / 33 BOM rows,
  re-exported from R3 + the LED move (2026-11-03); shared source manifest equal.
  Not supplier-accepted, not built. Supplier preview and formal component review gates
  remain open; R43/R46 are the existing Extended passive exception.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and explicit single-link routing review artifacts are in ignored
`research/s3-r2/` and `research/pot-flip/` (R3 batch scripts, DRC reports). Native schematic
owns presentation; native PCB owns placement/copper.
Do not regenerate the carrier. `build_layout.py --panel-only` regenerates only the
passive panel; the carrier builder refuses to overwrite a routed board.
No commits, uploads or orders without user authorization.
