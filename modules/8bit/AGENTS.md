# 8bit agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- **S4 schematic** (`hardware/8bit.kicad_sch`, ERC 0, fully wired with power symbols): Bread Modular 8bit on Eurorack.
  TS MIDI in with the MIDI V2 NPN front end and JP1 bypass (shipped open), protected
  bipolar CV in (±5.5 V -> 0..5 V, 102k, MCP6001 follower on +5V) to PB0, 50k knobs on PA1/PA2, 1M knob 3 as the passive LPF only (as BM), BM SMD mode switch + LED, TL072 ±4.8 V output,
  ±12 V Schottky protection, HT7550-1 +5V.
- **R3 routed carrier** (`hardware/8bit.kicad_pcb`, copper from `tools/route_plan.py`
  via shared plan/apply/promote): shared `check` no findings (DRC 0, 0 unconnected,
  parity equal). 4HP FR4 panel DRC 0. Printed button actuator in `panels/button-actuator/`.
- `jlcpcb/` export (bottom-side assembly, 37 parts) with source manifest; live audit
  passes except R12's fault power and the empty human reviews. Not supplier-accepted.
  Re-export after any source change (`jlcpcb/README.md`). No 3D fit or printed panel yet.
- `opt/kicad-tools/automation` was synced to `main` (thermal-relief zones); 5 files are
  byte-identical to `main`.
- Open: R12 rating, part reviews/placement preview, actuator test print, pot measurement, bench
  (`docs/research.md` §6).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. The routed native PCB owns
copper: changes are explicit edits to `tools/route_plan.py` through `pcb plan/apply/
promote`; rerun `build_layout.py` only as the full README rebuild. Bread Modular is read-only. No merges, pushes, orders or uploads.
