# ENV agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S3 schematic** (`hardware/env.kicad_sch`, ERC 0, every signal net wired): the ACID
  envelope block on its own 6HP module. 8bit / ACID MIDI input (+ J5 MIDI OUT, passive thru) and
  J6 GATE IN (NPN buffer -> PB2, TN jack detect -> PB1: patched = MIDI notes bypassed) -> one ATtiny1616 at 3.3 V
  (Bread Modular ENV pin map as ACID) -> PA6 DAC envelope 0..3.3 V -> TL072 x1.51 -> protected
  0..5 V ENV OUT + envelope-level LED. ATTACK / RELEASE knobs, MODE button + HR / AR / ASR LEDs,
  REC button + LED.
- **P7 placement** (`docs/geometry.json`, 6HP): GATE IN + MIDI IN at the top, ENV OUT + ENV
  LED + MIDI OUT at the bottom (jack columns X7 / X23), pots in the centre column at a 30 mm
  pitch, MODE button in the mode LED row and REC button + LED below (buttons on the left); J3
  power vertical on the right edge between the pots (pin 1 at the bottom) + J4 UPDI on the left
  edge between the pots, both on B.
- **R1 routing** (`hardware/env.kicad_pcb`, research.md 4): manual divide-and-conquer, 2 layers,
  GND pours on F and B, all SMD on B (U2 between the pots, U3 output stage below J3, input groups
  between the top jacks). ERC 0; KiCad DRC 0 / unconnected 0 / parity 0; no vias in SMD pads;
  copper >= 1.0 mm and courtyards >= 1.02 mm from the edge; SMD >= 2.10 mm from pot / jack pads; tracks >= 1.03 mm from pot / jack / J3 pads and none
  between pot pins (research.md 4.1).
  The native PCB now owns placement and copper: do not rerun `tools/build_layout.py`.
- B silk labels: `JP1 D=DIRECT P=PROT` (+ `D` / `P` under the pads) and `UPDI` / `GND` at J4
  (research.md 5).
- 6HP panel `panels/front-pcb/env-panel.kicad_pcb`, DRC 0. No printed (FreeCAD) panel yet.
- **JLCPCB export** in `jlcpcb/` (`jlcpcb/README.md`): carrier bottom Economic, 36 parts / 19 rows,
  all R/C Basic except R12 (ESR18 0.5 W, Extended) + ATtiny1616 Extended; panel Gerbers. The
  manifest is checked by the shared `check`: re-export after any source edit. Not
  supplier-accepted, not built.
- ACID is unchanged: its envelope still lives there too (research.md 1).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check. Raw reports
go in the ignored `research/`. Firmware (MIDI / GATE IN gate with the PB1 bypass, three envelope models, REC) is not written. Board
saves from scripts must go through a scratch copy: pcbnew rewrites the `.kicad_pro` on save
(research.md 4).
