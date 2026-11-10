# ladder contract (S3 schematic, P2 placement)

| | |
|---|---|
| KiCad project | `hardware/ladder.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/ladder-panel.kicad_{pro,pcb}` (FR4, 10HP); `panels/front-cad/` (printable) |
| Circuit intent / source profile | `tools/build_schematic.py`, `tools/kicad-project.json` |
| Placement contract | `docs/geometry.json`; native PCB owns SMD placement and copper once routing starts |
| Circuit rationale, numbers, ngspice check | `docs/research.md`, `tools/sim_ladder.py` |

## Fixed by the brief

- Analog version of the modules/16bit `PolyFilter`: classic transistor ladder; knobs
  **CUTOFF**, **RESONANCE**, **ENV TIME**, **DEPTH**, **CURVE**.
- Envelope from the **ATtiny1616 DAC**, started by **GATE** or **MIDI**; ENV TIME and DEPTH
  act on it. A **CV** jack fully bypasses it.
- External **AUDIO IN**; **FILTER OUT** (direct) and **VCA OUT** (vactrol VCA on the same
  envelope / CV, with CURVE).
- **RES CV** modulates the resonance, no depth control; by a **vactrol** (user 2026-11-09:
  "doesn't need to be accurate"), not the S1 LM13700.
- **Envelope automation recording** (user 2026-11-09, S3): REC button + LED as modules/acid,
  recording ENV TIME + DEPTH (shared `opt/attiny1616-tools/lib/CvRecorder`). DEPTH is therefore
  an MCU knob (PA7): DAC = envelope (or the PA2 CV when PA3 sees a cable) x DEPTH; the VCA gets
  the undepthed envelope from the PB0 PWM (two RC poles) or the CV directly through U3.
- **Panel** (user 2026-11-09: maximum panel space, more room for the knobs, modules/hats as the
  example): 10HP, knob grid 30 x 27 mm (CUTOFF + RES; ENV TIME + DEPTH; REC + CURVE), top jacks
  MIDI / GATE / CV / RES CV, bottom AUDIO IN / FILTER OUT / VCA OUT. **Not routed** ("don't
  route yet").

## Rules

- `tools/build_schematic.py` owns `hardware/ladder.kicad_sch`, `LADDER.kicad_sym` and
  `sym-lib-table`: modules/acid's generator (pinned stock KiCad 10 symbols, 1.27 mm grid wire
  router, native netlist assertion) with this module's circuit, placement, sourcing and notes.
  `LB0..LB4`, `ENV_BUF` and `VCA_ENV` are the only label-joined signal nets.
  `kicad-cli sch upgrade --force` writes the file natively.
- Symbol edits (`docs/schematic-symbols.json`): footprint filters of `Conn_01x02`,
  `Conn_02x05_Odd_Even`, `VTL5C` (as acid), and **DMMT3904W** = stock `MMDT3904` renamed with
  the DMMT3904W pin numbers (1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2; Diodes DS30311 p. 1).
- `tools/import_footprints.py` (acid's, plus SOT-363) wrote `LADDER.pretty`, `LADDER.3dshapes`
  and `fp-lib-table`; `PROVENANCE.json` records sources and hashes.
- `tools/build_layout.py` (modules/hats's builder) writes the carrier and the panel from
  `docs/geometry.json` and the native netlist; it refuses to overwrite a carrier with tracks.
  `--panel-only` regenerates only the panel. Once SMD groups move onto the board, the native
  PCB is the source of truth.
- Pots: BM `Potentiometer_RV09`, stock 50k linear. Jacks PJ301M-12. Vactrols VTL5C on B in the
  middle column, clear of every pot pad (no stacking exclusions). REC button / LED as acid.
- 1 mm board-edge keep-out (copper-edge rule 1.0 mm; every placed courtyard >= 1.2 mm).
  Every SMD pad >= 2 mm from hand-soldered jack / pot pads once placed.
- Routing: manual divide and conquer (root AGENTS.md), no autorouters, no vias in SMD pads.
  No ignored ERC/DRC rule severities, no exclusions.
- PWR_FLAGs: GND, +12V, -12V (header side), +12V_F, -12V_F.

## Verification (S3 / P2, 2026-11-09)

- `python3 -B tools/build_schematic.py`: router completes every wired net; native netlist
  equals `circuit()` (135 parts, 82 nets).
- `kicad-cli sch erc --severity-all`: 0 violations.
- `python3 -B tools/build_layout.py`; shared
  `kicad_tools.py check --config modules/ladder/tools/kicad-project.json`: ERC 0, DRC 0
  violations, parity 0, 294 unconnected (unrouted). Panel DRC 0.
- `python3 -B tools/sim_ladder.py` (S2 core, unchanged): cutoff ~54 Hz .. 17.1 kHz, flat
  passband with resonance, self-oscillation from R_LDR ~2.5k (models, not measurements).
