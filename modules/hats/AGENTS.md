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
- **R2 routed carrier:** 4 layers, In1 GND / In2 +3V3, all 89 assembled SMD parts on B.
  536 tracks / 99 ordinary tented 0.3/0.6 mm vias, no vias in SMD pads or mask openings,
  no tracks on inner layers; each inner plane is one piece. Fresh ERC/DRC/opens/parity 0.
  No DRC exclusions or ignored ERC/DRC rule severities remain.
- Actual copper setback >=1 mm; closest SMD-to-pot/jack pad gap 2.0465 mm.
  RV1-RV4 courtyard-line bounding boxes are 0.815 mm from the edge: the existing
  user-approved pot-column exception, not an exception for copper.
- **P4 panel:** 11 NPTH holes (4 jacks, 4 pots, ENV LED, 2 rail holes). Shafts at Y41/Y75,
  34 mm row pitch. RV3/RV4 rotate 180 degrees so their solder pins are above the bodies.
  U7 moved from Y84.7 to Y88 to clear the lower pots; nearby SMD/local traces adjusted.
  ENV LED D5 + R47 moved beside the HAT CV jack (LED body X26 Y93, 2026-10-24); the long
  F.Cu CVO_AMP run to the old LED spot is gone.
- JLCPCB export in `jlcpcb/`: bottom Economic target, 89 placements / 33 BOM rows.
  Not supplier-accepted, not built. Supplier preview and formal component review gates
  remain open; R43/R46 are the existing Extended passive exception.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and explicit single-link routing review artifacts are in ignored
`research/s3-r2/`. Native schematic owns presentation; native PCB owns placement/copper.
Do not regenerate the carrier. `build_layout.py --panel-only` regenerates only the
passive panel; the carrier builder refuses to overwrite a routed board.
No commits, uploads or orders without user authorization.
