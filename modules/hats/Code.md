# HATS contract (S4 schematic, R6 routed carrier, P5 panel)

**S4 (2026-11-08, user direction):** one STM32G071C8T6 (modules/12bit part and support) replaces
both ATtiny1616; CUTOFF becomes an ADC knob that drives a second vactrol (U11 LDR || R50 51k is
the bridged-T rheostat, LED from PB0 PWM via R51); REC button SW1 + LED D6/R48 return for the
shared recorder (lanes CUTOFF and NOISE TONE).

**R4 (2026-11-09):** 4-layer carrier re-placed and re-routed by hand for S4 (In1 GND / In2 +3V3, all assembled SMD on B; SW1 REC + D6 REC LED on F at the bottom as modules/16bit). 636 tracks / 120 tented 0.3/0.6 mm vias, no vias in SMD pads, no inner tracks, inner planes one piece. ERC 0, unconnected 0, parity 0. DRC: the 18 U7 stacking items (17 still excluded, one U7 silk/RV4-lug exclusion no longer matches) + the new U11-under-RV1/RV2 stacking (10 `pth_inside_courtyard`, 10 `silk_over_copper`), **not excluded: awaiting user approval**. SMD-to-pot/jack >= 2.05 mm. P5 panel: 13 NPTH (REC button 4.2 mm at X6.3 Y114.45, REC LED X23.7 Y114.45, REC legend). JLCPCB export re-done (95 placements / 33 BOM rows), not supplier-accepted. STM32 firmware in `firmware/` (2026-11-09): BM NOISE + HIHAT ports, PWM cutoff vactrol, shared REC recorder (CUTOFF + NOISE TONE), JP1 p/d builds with `opt/stm32g0-tools`; compiled and host-tested, not run on hardware.
**R5 (2026-11-09, fab review):** R4 copper unchanged; B silk only: J11 `SWD` + `3V3 DIO CLK GND RST`, vactrol
notes 1.0 mm / 0.15 mm clear of pot pads, `-12V` beside J10 pins 1/2, `HATS R5`; stale U7 exclusion re-keyed
(same items). U11 stacking still unapproved; C6/C26 placement near U2 open (user decision).
**R6 (2026-11-09, fab fixes, user-approved re-route around U2, no THT moved):** U2 support caps at their pins on B (routed length pin-pad centre to cap-pad centre): C6 (VDD 100n) GND 2.1 mm from pin 7 (pad edge gap 0.6 mm), +3V3 4.2 mm along the pin-6 track with a plane via, plus an under-chip GND via on pin 7 (was 100n reached only through the planes, ~7.3 mm away); C25 (VREF+ 100n) 2.3 mm from pin 5 (edge gap 0.6 mm), on to C24 and FB1 (now below C26) by B tracks; C26 (NRST 100n) on the pin-10 escape, 5.6 mm (was by J11, ~22.7 mm); NRST via to the F run to J11 kept. C19 (U8 decoupling) took C6's old spot and copper; C20 (U9 decoupling, plane vias as before) moved below U9 (native X103.5 Y114.2). U1 HT7533 tab: +12V_F patches U1_TAB_B (27.5 mm2 filled) and U1_TAB_F (78.8 mm2) tied by 8 tented free vias beside the tab (not in it); prototype temperature check stays. The 18 U11/RV1/RV2 stacking items are now user-approved exclusions (2026-11-09, `tools/vactrol_exclusions.py ... U11`): DRC 36 = 36 excluded, 0 active. ERC 0, unconnected 0, native schematic parity 0 (the shared literal ref/pin/net comparison still shows only the four pre-existing `{slash}` NC-name escapes, U2 29/32/33/34), 639 tracks / 131 vias, no vias in SMD pads, no inner tracks, In1/In2 one piece, SMD-to-pot/jack 2.05 mm. `HATS R6`. JLCPCB re-exported (BOM unchanged; CPL: only the 6 moved parts C6/C19/C20/C25/C26/FB1). R43/R46 stay Extended: Basic 1k is 0.25 W (1206) / 0.125 W (0805); 0.5 W would need 2 x 2k Basic in parallel per output, a schematic change with no room in the edge columns. Scripts/reports: `research/fab-fix2/`.
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
  planes continuous. No ignored ERC/DRC rule severities. DRC exclusions: only the vactrol stacking
  items, 18 per vactrol (10 `pth_inside_courtyard` + 8 `silk_over_copper`): U7 under RV3/RV4
  (user-approved 2026-11-03) and U11 under RV1/RV2 (user-approved 2026-11-09), written by
  `tools/vactrol_exclusions.py <report> U7|U11` (re-run for the vactrol whose parts moved, with
  the other set already excluded; it keeps the other set; the shared gate still counts them, as
  on LOW / ACID). That script expects exactly the 18 active items of one set: for a single stale
  key (marker moved, same item UUIDs) use `research/fab-fix/rekey_u7.py` instead.
- Back silk legends are functional: keep the J11 SWD pin legend, the vactrol assembly notes
  (>= 1.0 mm / 0.15 mm, off pad openings) and `-12V` at J10 pins 1/2 when moving parts.
- Use the shared exporter for both carrier and panel, refresh the shared source
  manifest, and verify all upload mirrors. Export success is not supplier signoff.
