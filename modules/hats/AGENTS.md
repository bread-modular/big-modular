# HATS agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S2 schematic** (`hardware/hats.kicad_sch`, ERC 0, every signal net wired except the
  label-joined `VMID_H`): Bread Modular NOISE (blue noise only) + HIHAT, two ATtiny1616 (Bread
  Modular pin maps), 3.3 V signals; 8bit MIDI input feeding both MCUs; NOISE IN normalled through
  U5 TS5A23157 to the internal blue noise; TL072 AUDIO out x3 and HAT CV out 0..5 V with the ENV
  LED. S2 adds the REC button SW1 on PC2 of both MCUs (internal pull-ups) and the REC LED D6 on U3
  PC3 (as modules/acid); recording needs new firmware on both chips.
- **R1 routed carrier** (`hardware/hats.kicad_pcb`): P2 placement with the REC LED + button as one
  row and SW1 inside the U7 vactrol outline (user, soldered from the other side); manual
  divide-and-conquer routing, 4-layer (F.Cu / In1 GND / In2 +3V3 / B.Cu), all SMD on B. KiCad DRC 0
  (the 4 SW1-in-U7 `pth_inside_courtyard` items are user-approved exclusions,
  `tools/sw1_exclusions.py`; the shared gate still counts them) / 0 unconnected / parity 0; no vias
  in SMD pads; SMD >= 2 mm from pot/jack pads (closest R36-RV4 2.02 mm); RV1-RV4 courtyards
  0.77 mm from the edge (user-accepted).
- 6HP panel `panels/front-pcb/hats-panel.kicad_pcb`.
- **JLCPCB export** in `jlcpcb/` (2026-10-24, bottom Economic, 88 parts / 31 rows), not
  supplier-accepted, not built. See `jlcpcb/README.md`.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check. Raw reports go
in the ignored `research/`. Routing has started: the native PCB owns placement and copper; do not rerun
`build_layout.py` over it.
