# HATS agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md`, `docs/research.md` and
`docs/noise-in-protection.md`. Paths below are module-relative.

## Current state

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
- `firmware/`: BM NOISE (U2, J11) and HIHAT (U3, J12) ports, JP1 p/d builds
  (`MIDI_RX_INVERT`, both MCUs on one RX); otherwise BM unchanged (clock/DAC reference
  kept). Compiled, not bench-tested. See `firmware/README.md`.
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
