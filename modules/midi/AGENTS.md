# midi agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- S3: flat root schematic at 5 V logic (opto removed, deferred to V2)
  (`hardware/midi.kicad_sch`, ERC 0).
- R1: fully routed 2-layer carrier, GND on both layers. The routed native PCB
  owns copper; `tools/route_plan.py` records its explicit geometry for the
  shared plan/apply/promote flow (`Code.md`).
- 4HP FR4 panel and FreeCAD printed panel.
- The shared `check` reports no findings: ERC 0, DRC 0, 0 unconnected,
  schematic parity 0, ref/pin/net parity equal.
- Open checks in `docs/research.md` §4: D2 (R20 rating, U3 temperature in the
  fault case), D5 (LED brightness) and D6 (R21 vs the injection limit) are
  bench/sourcing items.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for
doctor/check. Raw reports and caches go in the ignored `research/`. There is no
`jlcpcb/` export until a separate task authorises fabrication outputs. Bread Modular is read-only. No commits, merges,
pushes, orders or uploads.
