# HATS contract (S3 schematic, R2 routed carrier, P4 panel)

| | |
|---|---|
| KiCad project | `hardware/hats.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/hats-panel.kicad_{pro,pcb}` (FR4, 11 NPTH holes, 6HP) |
| Circuit intent / source profile | `tools/build_schematic.py`, `tools/kicad-project.json` |
| Placement contract | `docs/geometry.json`; native PCB owns routed SMD placement |
| Circuit / protection rationale | `docs/research.md`, `docs/noise-in-protection.md` |

## Fixed by the brief

- Bread Modular NOISE (blue output) -> HIHAT; 6HP; 3.3 V internal signals.
- Two ATtiny1616 (U2 NOISE / U3 HIHAT), original functional pin maps, one RX net.
- Panel: MIDI + NOISE IN; NOISE TONE + BLUE TONE; ENV LED; CUTOFF + DECAY;
  AUDIO + HAT CV. J10 horizontal on B along the bottom.
- **No recording functionality.** No SW1, D6 or R48; former recording GPIOs are NC.
- Pot shaft rows Y41 / Y75 (34 mm pitch); lower pots rotated 180 degrees. U7 centre Y88.
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
  planes continuous. No ignored ERC/DRC rule severities or DRC exclusions.
- Use the shared exporter for both carrier and panel, refresh the shared source
  manifest, and verify all upload mirrors. Export success is not supplier signoff.
