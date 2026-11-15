# DRIVE agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S1 schematic** (`hardware/drive.kicad_sch`, 2026-11-15): mono OTA overdrive + wavefolder.
  Inverting input buffer -> linearized LM13700 VCA (DRIVE, exponential converter Q1 / Q2) ->
  AC coupling -> five LM13700 tanh cells summed as currents (B = soft clipper; C / D and E / F
  = fold pairs at ±198 mV and ±405 mV, all four at FOLD x I_0) -> TONE low-pass -> dry / wet
  MIX -> output inverter -> 1k 2512. 4 x TL072, 3 x LM13700, 3 x SS8550. DRIVE CV and FOLD CV
  add to their knobs; no MIX CV (user).
- Native ERC `--severity-all` 0; the build asserts the native netlist against `circuit()`
  (92 parts, 50 nets). `tools/sim_drive.py` generates its ngspice deck from `circuit()` (models,
  not measurements); results in `docs/research.md` section 4, plots in `docs/sim/`.
- **P2 placement** (user 2026-11-15: "move the power socket to the side and use that space to
  move down the pots"): 6HP, columns X8 / X22; DRIVE CV + FOLD CV jacks Y21, DRIVE + FOLD Y45,
  TONE + MIX Y80, IN + OUT Y110.3. J10 upright at the right edge on B (X23.8 / X26.34,
  Y91.2..101.36, pins 1/2 = -12 V at the bottom). Pot courtyards 1.02 mm from the edge.
  `docs/geometry.json` is the contract. P1 (hats grid, J10 along the bottom) is history.
- **R1 routing** (2026-11-15, manual divide and conquer, user: "this is all good, do it"):
  4 layers, F signal / In1 GND / In2 +12V / B signal, -12V as 0.4-0.5 mm tracks; all 83 SMD
  parts on B. Top strip between the CV jacks: fold threshold dividers; top band: U4, Q1 / Q2
  (side by side), Q3; middle band: U5 / U6 / U7 and U1; bottom band: U2, U3, D1 / D2, R40.
  393 tracks / 79 vias. Shared check ERC 0, DRC 0 (no exclusions), unconnected 0, parity 0,
  manifest equal (`research/r1-final-check/`). No vias in SMD pads, no inner tracks, SMD pads
  >= 2.025 mm from pot / jack pads, copper >= 1.1 mm and courtyards >= 1.02 mm from the edge.
- **R2 = 2 layers** (2026-11-15, user: "would it be possible to do a 2 layer routing", then
  "do it"; as modules/12bit R2). The R1 F / B signal copper is untouched. In1 GND / In2 +12V
  planes removed; GND is one zone poured on F and B. +12V is a 0.4-0.5 mm trunk, mostly on F:
  D1 via -> U3 -> (B hop under the -12V branch at Y91) -> U1 -> U5 -> C24 -> U7 / U6 / RV1 /
  RV2, and up X18.1 / X17.6 to U4 and R12 / R16 (187 mm on F, 44 mm on B, 7 new vias). 16 GND
  stitching vias tie the F pour pieces between the supply trunks to the B pour. 455 tracks /
  102 vias. Shared check ERC 0, DRC 0 (no exclusions), unconnected 0, parity 0, manifest equal
  (`research/r2-final-check/`). House rules as R1 (same closest distances). B pour: main piece
  + two pad / via-tied pieces; F pour: main piece + 12 via-stitched pieces; spoke-tied
  fragments between the J10 / jack GND pads on both. Batches `research/route/b10`..`b17`,
  helpers `pieces.py` / `voids.py`. R1 board backup: `/tmp/drive-r1-final.kicad_pcb` (not kept).
- **Fab review** (2026-11-15, redone for R2): no stackup record (plain 2-layer 1.6 mm), title
  block and B silk S1/R2, `-12V` silk at J10. Judged, not changed: LM13700 100n caps 3.6-6.1 mm
  from their supply pins; ground is less quiet than the R1 plane (bench item).
- **JLCPCB export** in `jlcpcb/` (R2, 2 layers; 83 placements / 29 rows, bottom Economic,
  assembly CSVs identical to R1; panel Gerbers).
  Read `jlcpcb/README.md`. Not supplier-accepted, not built.
- **Open, user decisions:** LM13700 (C174050) and the 1 W 2512 1k (C54315) are Extended parts;
  JLCPCB preview; bench test. No printed panel (`panels/front-cad/`).

## Boundaries

Shared tools stay in `../../opt/`. Raw reports, renders, sim decks and catalog snapshots go in
the ignored `research/`. Routing follows the root manual divide-and-conquer rules, straight on
`hardware/drive.kicad_pcb`; the carrier is routed, so `tools/build_layout.py` must only run
with `--panel-only` (it refuses a board with tracks). No merges, pushes, orders or uploads.
