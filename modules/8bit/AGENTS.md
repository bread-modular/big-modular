# 8bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- **S5 schematic** (`hardware/8bit.kicad_sch`, ERC 0, fully wired with power symbols): Bread Modular 8bit on Eurorack.
  TS MIDI in with the MIDI V2 NPN front end and JP1 bypass (shipped open), protected
  bipolar CV in (±5.5 V -> 0..5 V, 102k, MCP6001 follower on +5V) to PB0, 50k knobs on PA1/PA2, 1M knob 3 as the passive LPF only (as BM), 6x6x7 mm THT mode switch (S5, user-bought) + LED, TL072 ±4.8 V output,
  ±12 V Schottky protection, HT7550-1 +5V.
- **R4 routed carrier** (`hardware/8bit.kicad_pcb`, copper from `tools/route_plan.py`
  via shared plan/apply/promote): shared `check` no findings (DRC 0, 0 unconnected,
  parity equal). 4HP FR4 panel DRC 0. One-piece printed button cap in `panels/button-actuator/`.
- `jlcpcb/` export (bottom-side assembly, 37 parts) with source manifest; live audit
  passes except R12's intentional Extended class (0.5 W ROHM ESR18EZPF1001, as MIDI V2's R20)
  and the empty human reviews. Not supplier-accepted.
  Re-exported for S5/R4 (2026-10-20); live audit not rerun (BOM unchanged). Re-export after any source change (`jlcpcb/README.md`). No 3D fit or printed panel yet.
- `firmware/`: BM `drums`, `supersaw` (MIDI only, CV1 pitch mode removed) and `crash`,
  built per JP1 setting (`p`/`d`) with the shared `opt/attiny1616-tools`. Compiled, not bench-tested.
- `opt/kicad-tools/automation` was synced to `main` (thermal-relief zones); 5 files are
  byte-identical to `main`.
- Open: part reviews/placement preview, cap press-fit/test print, pot measurement, bench
  (`docs/research.md` §6).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. The routed native PCB owns
copper: changes are explicit edits to `tools/route_plan.py` through `pcb plan/apply/
promote`; rerun `build_layout.py` only as the full README rebuild. Bread Modular is read-only. No merges, pushes, orders or uploads.
