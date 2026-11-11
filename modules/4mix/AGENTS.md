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
- Printable channel VOL knobs in the repo-root `mechanical/knobs/` (its own
  `tools/build_knobs.sh`, previews in `renders/`; four widths, one folder each: `wide/` Ø16, `slim/` Ø13, `slimmer/` Ø11.5, `slimmest/` Ø10, all 13.5 mm tall,
  11.5 mm bore for the measured shaft (18 mm above the pot body, about 13 mm above the
  panel), paint-pen pointer pocket; grip 4 for the 6 mm RV09 shaft (R0904N type KQ: 40-tooth knurl on
  the top 7 mm, from the data sheet, not counted): solid knob, round blind bore, 20 teeth in its top
  6 mm that drop into every second knurl groove and wedge tighter toward the roof; round bore Ø6.2
  in every fit, eight tooth depths `t1` .. `t8` per width + a fit gauge per width = its eight knobs
  in one print, numbered by 1 .. 8 notches in the base rim) and a
  knob puller for every width in `puller/` (spring tongs, 0.8 mm hooks under the knob base,
  one leg above and one below the knob). User test prints, 2026-11-11: grips 1 and 2 (slit sleeve
  with spring fingers) loose even in the tightest fit; grip 3 (square tapered bore, friction only)
  held in `fit1` but slipped on the shaft when turned hard, so the user asked for teeth that line
  up with the shaft grooves, as on the Thonk Tall Trimmer Toppers; of the first grip 4 gauge the
  loosest tile `fit8` dropped into the knurl and locked ("workable"), so the tooth ladder keeps
  that bore and varies the tooth depth around it (`t4` = old `fit8`, 0.05 mm steps on the tip
  diameter). The user then printed the tile gauge and a slim `t4` knob: `t4` slim is like the old
  `fit8`, but gauge and knobs did not agree (the bores are identical in the STEP files, so it is
  the print: cause not confirmed), hence the gauge made of real knobs; slim `t2` / `t3` knobs in
  print, result open. Same day: folders per width and the two new widths (wall behind the teeth
  2.10 / 1.44 mm against 2.76 on slim). Slimmer, slimmest and the new gauges are not test-printed.
- JLCPCB export in `jlcpcb/` (bottom Economic PCBA; R20/R30/R33 2512 Extended), not
  supplier-accepted, not built. Re-export after any source change (`jlcpcb/README.md`).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports go in the ignored `research/`. SMD placement and routing are manual, group by
group, straight on the board (root `AGENTS.md`); once that starts, do not rerun
`tools/build_layout.py`. Bread Modular is read-only. No merges, pushes, orders or uploads.
