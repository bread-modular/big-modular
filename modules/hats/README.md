# HATS

6HP Eurorack hi-hat: Bread Modular NOISE (blue noise, NOISE TONE / BLUE TONE) feeding the
Bread Modular HIHAT (CUTOFF, vactrol VCA, closed-hat DECAY), driven by shared MIDI.
NOISE IN replaces the internal noise through protected jack-contact detection.
Outputs: AUDIO (nominal ~10 Vpp) and HAT CV (intended 0..5 V) with ENV LED.

**S4 schematic (2026-11-08):** one STM32G071C8T6 runs both Bread Modular firmwares; CUTOFF is
read by the ADC and played on a second vactrol by PWM, so CUTOFF and NOISE TONE can be recorded
(REC button + LED at the bottom). **R4** carrier routed by hand for S4 (4 layers, all SMD on the
back, ERC 0 / unconnected 0 / parity 0), **P5** panel with the REC button and LED holes, JLCPCB
re-exported. The new vactrol U11 under NOISE TONE / BLUE TONE adds stacking DRC items that still
need your approval. The STM32 firmware is in `firmware/` (compiled and host-tested, not run on hardware yet).
**R5** (2026-11-09) = R4 copper with fab-review silk fixes: SWD pin legend on J11, larger vactrol
assembly notes clear of the pot pads, `-12V` beside the power header, `HATS R5` board text.
**R6** (2026-11-09) = fab fixes: the MCU's supply, reference and reset caps (C6, C25, C26) moved to
their pins with a local re-route, heat-spreading copper on both sides of the 3.3 V regulator tab
(U1), the U11 vactrol stacking findings approved and excluded like U7's, `HATS R6` board text.

**S3 schematic / R3 routed four-layer carrier / P4 panel.** Recording functionality,
button, LED and associated circuitry have been removed. Pot row spacing is **34 mm**
(previously 24 mm); all pots upright, with the vactrol on the back under CUTOFF (as on
LOW). Copper setback is **1 mm**; all assembled SMD is on the back.

JLCPCB files: `jlcpcb/` (re-exported from S4/R6/P5, 2026-11-09). See `jlcpcb/README.md`, `docs/research.md` and
`docs/noise-in-protection.md`. Exported, not supplier-accepted or bench-validated.
Firmware clock/reference settings were left unchanged at the user's request.
