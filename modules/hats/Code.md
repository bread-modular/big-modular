# HATS contract (S4 schematic, R4 routed carrier, P5 panel)

**S4 (2026-11-08, user direction):** one STM32G071C8T6 (modules/12bit part and support) replaces
both ATtiny1616; CUTOFF becomes an ADC knob that drives a second vactrol (U11 LDR || R50 51k is
the bridged-T rheostat, LED from PB0 PWM via R51); REC button SW1 + LED D6/R48 return for the
shared recorder (lanes CUTOFF and NOISE TONE).

**R4 (2026-11-09):** 4-layer carrier re-placed and re-routed by hand for S4 (In1 GND / In2 +3V3, all assembled SMD on B; SW1 REC + D6 REC LED on F at the bottom as modules/16bit). 636 tracks / 120 tented 0.3/0.6 mm vias, no vias in SMD pads, no inner tracks, inner planes one piece. ERC 0, unconnected 0, parity 0. DRC: the 18 U7 stacking items (17 still excluded, one U7 silk/RV4-lug exclusion no longer matches) + the new U11-under-RV1/RV2 stacking (10 `pth_inside_courtyard`, 10 `silk_over_copper`), **not excluded: awaiting user approval**. SMD-to-pot/jack >= 2.05 mm. P5 panel: 13 NPTH (REC button 4.2 mm at X6.3 Y114.45, REC LED X23.7 Y114.45, REC legend). JLCPCB export re-done (95 placements / 33 BOM rows), not supplier-accepted. STM32 firmware in `firmware/` (2026-11-09): BM NOISE + HIHAT ports, PWM cutoff vactrol, shared REC recorder (CUTOFF + NOISE TONE), JP1 p/d builds with `opt/stm32g0-tools`; compiled and host-tested, not run on hardware.
Tables below that still say S3/R3/P4 are history unless they name S4.

| | |
|---|---|
| KiCad project | `hardware/hats.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/hats-panel.kicad_{pro,pcb}` (FR4, 13 NPTH holes, 6HP; P5) |
| Circuit intent / source profile | `tools/build_schematic.py`, `tools/kicad-project.json` |
| Placement contract | `docs/geometry.json`; native PCB owns routed SMD placement |
| Circuit / protection rationale | `docs/research.md`, `docs/noise-in-protection.md` |

## Fixed by the brief

- Bread Modular NOISE (blue output) -> HIHAT; 6HP; 3.3 V internal signals.
- S4: one STM32G071C8T6 U2 (pin map in `tools/build_schematic.py` `MCU_PINS`), SWD on J11. S3: two ATtiny1616.
- Panel: MIDI + NOISE IN; NOISE TONE + BLUE TONE; CUTOFF + DECAY; ENV LED midway between AUDIO and HAT CV on their centre line (X15 Y102);
  AUDIO + HAT CV. J10 horizontal on B along the bottom.
- S4: **recording is back**: SW1 REC (PB4), D6/R48 REC LED (PB5); CUTOFF and NOISE TONE are MCU-read. S3 had none.
- Pot shaft rows Y41 / Y75 (34 mm pitch); all four pots upright (pins below the bodies).
  U7 lies on B under the CUTOFF pot RV3 (modules/low / modules/acid pattern), centre X9.5 Y79.4.
- NOISE IN sense: R14 470k, R49 22k series, D7 BAV199 low-leakage dual rail clamp.
- Leave firmware clock/DAC reference settings unchanged (user scope decision).

## Rules

- Pots: BM `Potentiometer_RV09`, stock 50k / 1M linear. Jacks PJ301M-12; vactrol VTL5C.
  Footprint provenance: `hardware/HATS.pretty/PROVENANCE.json`.
- Native netlist must equal `build_schematic.circuit()` including NCs and metadata.
  Only VMID_H is label-joined; power flags remain #FLG01-#FLG05.
- 1 mm copper-edge keep-out, including filled polygons, with native rule 1.0 mm.
  Only the existing RV1-RV4 courtyard exception remains: measured line-box margin
  0.815 mm (historical cached-yard documentation quoted 0.77 mm), user accepted.
- Every SMD pad >=2 mm from hand-soldered jack/pot pads and lugs.
- Manual divide-and-conquer routing; no autorouters or in-pad vias. Keep both inner
  planes continuous. No ignored ERC/DRC rule severities. DRC exclusions: only the 18 U7-under-RV3
  stacking items (10 `pth_inside_courtyard` + 8 `silk_over_copper`), user-approved 2026-11-03,
  written by `tools/vactrol_exclusions.py` (re-run after moving U7, RV3 or RV4; the shared gate
  still counts them, as on LOW / ACID).
- Use the shared exporter for both carrier and panel, refresh the shared source
  manifest, and verify all upload mirrors. Export success is not supplier signoff.
