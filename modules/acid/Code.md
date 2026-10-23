# ACID contract (S2 schematic, R1 routing, JLCPCB export)

| | |
|---|---|
| KiCad project | `hardware/acid.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/acid-panel.kicad_{pro,pcb}` (FR4, NPTH only, 8HP) |
| Generators, profile | `tools/` (`import_footprints.py`, `build_schematic.py`, `build_layout.py`, `sim_level.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Fabrication outputs | `jlcpcb/` (shared exporter, bottom Economic; never hand-edit, re-export after any board edit; `jlcpcb/README.md`) |

## Fixed by the brief

- Bread Modular MCO + ENV + SVF, 8HP, **3.3 V internal signals** (BM values and topology kept;
  deviations listed in research.md 3.5). No DRIVE circuit.
- MIDI in like 8bit; AUDIO bypass mapped to 0..3.3 V (clipping accepted); CV bypass 0..5 V ->
  0..3.3 V (as modules/low); unpatched they carry the MCO square mix and the DAC envelope.
- Envelope CV out 0..3.3 V -> 0..5 V, protected. LP / HP / BP outs, each one TL072 stage: the
  DRIVE-at-75 % gain (x11.1) with a ~10 Vpp ceiling (research.md 3.4).
- Panel (user P2 layout, P3 edge fixes + alignment): MIDI, DETUNE + MIX, ATTACK + RELEASE with the HR/AR/ASR LED column,
  REC LED + button, MODE button, ENV OUT, AUDIO + FREQ + CV, RES + CURVE, LP + HP + BP OUT.
- Vactrols on B, hand-soldered (modules/low / vca-mix). R1: under ATTACK / RELEASE between the lug
  and pin rows (research.md 5); the stacking findings are user-approved.
- 4 layers (R1): F signal + GND pour, In1 solid GND (no tracks), In2 +3V3 plane, B signal + GND pour;
  SMD on B only.

## Rules

- One ATtiny1616 keeps the BM MCO pin map and the BM ENV knob/button/LED pins (research.md 3).
- Pots: BM `Potentiometer_RV09`, user stock 50k / 500k / 1M linear. Jacks: PJ301M-12 (modules/low
  footprint). LEDs 3 mm and 6 x 6 mm tact switches as modules/8bit. VTL5C: BM footprint +
  modules/low courtyard. `hardware/ACID.pretty/PROVENANCE.json` records sources and hashes.
- `build_schematic.py` asserts the exported netlist equals `circuit()`. Symbols are placed by
  hand (`LAYOUT`); every signal net is drawn as wires by its grid router (never touching another
  net's pin, stub, body or wire end), one name label per net; only `ENV_CV` is label-joined.
  The build fails if a net cannot be routed. PWR_FLAGs only `#FLG01`-`#FLG05`.
- 1 mm board-edge keep-out (`min_copper_edge_clearance` 1.0 mm in `acid.kicad_pro`, courtyards
  >= 1 mm, measured). 2 mm hand-solder clearance applies when SMD parts are placed.
- DRC exclusions: exactly the 22 user-approved U7/U8 under RV4/RV3 stacking items (R1), written
  only by `tools/vactrol_exclusions.py`, which refuses any other finding. `build_layout.py` rewrites `acid.kicad_pro` and drops them:
  re-run the DRC + `vactrol_exclusions.py` after every rebuild. Routing follows the root manual divide-and-conquer rules; once it starts the
  native PCB owns placement and copper and `build_layout.py` must not be rerun.
