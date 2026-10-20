# vca-mix agent entry point

Read the root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Paths here are relative to the module.

## Current state

- S4 schematic (`hardware/vca-mix.kicad_sch`, ERC 0): 3 x Bread Modular V2CA vactrol
  VCA (no CURVE) driven by a Bread Modular LOW/SVF vactrol driver, buffered audio
  and CV inputs, post-VCA volume with OUT after the pot, imix-style mixer, 1k 1 W
  2512 on OUT1-3 and MIX, ±12 V, 10 x TL072 (three per channel + one for the mix).
  Every assembled part carries `LCSC`, `MPN` and `Manufacturer` fields from
  `SOURCING` in `tools/build_schematic.py`.
- P4 placement: one row per channel (IN/CV/OUT jacks, VOL knob right below), vactrols
  on B behind their own pots (Bread Modular SVF style, unchanged BM VTL5C footprint).
- R1 routing: TraceMaker route + cleanup frozen in `tools/route_r1.json`, emitted by
  `tools/route_plan.py` as shared ops. The shared apply gives 0 unconnected / parity
  equal but is `rejected` on the 9 excluded D10 findings, so on user direction
  (2026-10-20) `tools/promote_r1.py` copied it into `hardware/vca-mix.kicad_pcb`:
  the board is **routed (R1 final)**; the user verifies the D10 exceptions by hand.
- 6HP FR4 panel and FreeCAD printed panel.
- Pots: Song Huei R0904N on the unchanged Bread Modular RV09 footprint
  (user-confirmed in BM builds; use BM footprints when in doubt).
- Vactrol build notes (D4) are B.SilkS text inside the VTL5C body box (`SOLDER FIRST`,
  `TRIM FLUSH`, `LED 18.5mA`), added by `tools/import_footprints.py`.
- D14 (shared gate counts the excluded D10 items) is accepted by the user for this
  module: `pcb promote` and `order_ready` stay blocked; `tools/promote_r1.py` is the copy step. D10 is decided: 9 per-item
  DRC exclusions via `tools/d10_exclusions.py` only.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. There is no `jlcpcb/` export
yet: that needs D14 resolved and a separate release task using the shared
exporter.
Bread Modular is read-only. No merges, pushes, orders or uploads.
