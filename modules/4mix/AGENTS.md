# 4mix agent entry point

Read the root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Paths here are relative to the module.

## Current state

- S2 schematic (ERC 0; every input AC-coupled), hierarchical: root `hardware/4mix.kicad_sch` (power, MAIN/SEND
  summers, returns, output, expansion) + `hardware/channel.kicad_sch` used four times
  (CH1..CH4, parts numbered n01..). Bread Modular `4mix` on ±12 V without the overdrive.
- P6 placement (user hand placement, tidied; + 2 x 10 mm M3 F-F hex standoffs MS1/MS2 at the bottom, mechanical footprints): 18HP, THT only (9 jacks, 15 RV09 pots; top line
  SEND A, SEND B, RTN A, RTN B, MAIN, OUT, LVL A/B below their return jacks; big-knob space on each channel VOL; J6 EXP IN top left, J7 EXP OUT top right, J8 power bottom right, on B). 4-layer (F signal / In1 GND / In2 +12V / B signal).
- R1 manual divide-and-conquer routing, complete: every SMD part on B, KiCad DRC 0 / unconnected 0 /
  parity 0, no vias in SMD pads, SMD >= 2 mm from pot/jack pads (closest 2.27 mm), courtyards >= 1 mm
  from the edge, In1/In2 planes one piece each. Batch scripts in the ignored `research/route/`.
- 18HP FR4 panel (`panels/front-pcb/`), fit study only. No FreeCAD panel.
- JLCPCB export in `jlcpcb/` (bottom Economic PCBA; R20/R30/R33 2512 Extended), not
  supplier-accepted, not built. Re-export after any source change (`jlcpcb/README.md`).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports go in the ignored `research/`. SMD placement and routing are manual, group by
group, straight on the board (root `AGENTS.md`); once that starts, do not rerun
`tools/build_layout.py`. Bread Modular is read-only. No merges, pushes, orders or uploads.
