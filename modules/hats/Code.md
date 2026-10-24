# HATS contract (S2 schematic, R1 routed carrier)

| | |
|---|---|
| KiCad project | `hardware/hats.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/hats-panel.kicad_{pro,pcb}` (FR4, NPTH only, 6HP) |
| Generators, profile | `tools/` (`import_footprints.py`, `build_schematic.py`, `build_layout.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |

## Fixed by the brief

- Bread Modular NOISE (blue output) -> HIHAT, 6HP, 3.3 V internal signals, BM values and topology.
- Panel: MIDI + NOISE IN; NOISE TONE + BLUE TONE; ENV LED; CUTOFF + DECAY; REC LED + REC button;
  AUDIO OUT + HAT CV OUT. J10 horizontal along the bottom edge (B).
- Two ATtiny1616: U2 runs BM NOISE, U3 runs BM HIHAT (pin maps unchanged), both on one RX net.
- REC (S2): SW1 on PC2 of U2 and U3 (internal pull-ups), REC LED D6 on U3 PC3 only.

## Rules

- Pots: BM `Potentiometer_RV09`, user stock 50k / 1M linear. Jacks PJ301M-12, VTL5C, LED as
  modules/low / modules/acid. `hardware/HATS.pretty/PROVENANCE.json` records sources.
- `build_schematic.py` asserts the exported netlist equals `circuit()`; only `VMID_H` is
  label-joined; PWR_FLAGs only `#FLG01`-`#FLG05`.
- 1 mm board-edge keep-out (`min_copper_edge_clearance` 1.0 mm); RV1-RV4 courtyards 0.77 mm
  (same pot columns as modules/low, user-accepted 2026-10-24).
- 2 mm hand-solder clearance and manual divide-and-conquer routing; the native PCB owns copper.
- DRC exclusions: only the 4 SW1-in-U7 `pth_inside_courtyard` items (`tools/sw1_exclusions.py`;
  re-run it after moving SW1 or U7).
