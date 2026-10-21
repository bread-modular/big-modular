# LOW contract (S2 schematic, R1 routed carrier)

| | |
|---|---|
| KiCad project | `hardware/low.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/low-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Generators, profile | `tools/` (`import_footprints.py`, `build_schematic.py`, `build_layout.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |

## Fixed by the brief

- Bread Modular MCO + LOW, 6HP, **3.3 V internal signals** (BM values and topology kept).
- MIDI in like 8bit; AUDIO bypass mapped to 0..3.3 V (clipping accepted); CV bypass
  0..5 V -> 0..3.3 V; unpatched they carry the MCO square mix and the MCO velocity DAC.
- Panel: MIDI, DETUNE + MIX, AUDIO + CV, CUTOFF, OUT. No BLAST button.
- Vactrols on B as modules/vca-mix; parts may sit over the vactrol footprints.

## Rules

- BM MCO pin map unchanged, so its firmware runs as is.
- Pots: BM `Potentiometer_RV09`, 50k linear (user stock). Jacks: PJ301M-12 (BM AudioJacks,
  vca-mix edits). VTL5C: BM footprint + vca-mix courtyard. Everything else stock KiCad;
  `hardware/LOW.pretty/PROVENANCE.json` records sources and hashes.
- `build_schematic.py` asserts the exported netlist equals `circuit()`. Signal nets are
  drawn as wires (`LAYOUT` placement, `WIRES` polylines, one name label per net, junctions
  computed; the build fails if a wire touches another net). Supply pins get a stub and a
  power symbol. VEL_CV is the only label-joined signal net (U2 DAC -> U4B NC2). Only PWR_FLAGs `#FLG01`-`#FLG05` (J10 entry and
  the rails behind D1/D2).
- All SMD on B (one assembly side). JP1 is copper only (not in BOM/CPL).
