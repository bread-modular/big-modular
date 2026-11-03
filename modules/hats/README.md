# HATS

6HP Eurorack hi-hat: Bread Modular NOISE (blue noise, NOISE TONE / BLUE TONE) feeding the
Bread Modular HIHAT (CUTOFF, vactrol VCA, closed-hat DECAY), driven by shared MIDI.
NOISE IN replaces the internal noise through protected jack-contact detection.
Outputs: AUDIO (nominal ~10 Vpp) and HAT CV (intended 0..5 V) with ENV LED.

**S3 schematic / R3 routed four-layer carrier / P4 panel.** Recording functionality,
button, LED and associated circuitry have been removed. Pot row spacing is **34 mm**
(previously 24 mm); all pots upright, with the vactrol on the back under CUTOFF (as on
LOW). Copper setback is **1 mm**; all assembled SMD is on the back.

JLCPCB files: `jlcpcb/` (re-exported from R3, 2026-11-03). See `jlcpcb/README.md`, `docs/research.md` and
`docs/noise-in-protection.md`. Exported, not supplier-accepted or bench-validated.
Firmware clock/reference settings were left unchanged at the user's request.
