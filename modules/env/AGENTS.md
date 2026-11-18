# ENV agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S5 schematic** (`hardware/env.kicad_sch`, 2026-11-18, ERC 0, every signal net wired; S5 = S4 + R20 470k
  from ENV_OUT to -12V_F, research.md 7; on the board since R2): the ACID
  envelope block on its own 6HP module. 8bit / ACID MIDI input (+ J5 MIDI OUT, passive thru) and
  J6 GATE IN (NPN buffer -> PB2, TN jack detect -> PB1: patched = MIDI notes bypassed) -> one ATtiny1616 at 5 V (HT7550-1, as our 8bit)
  (Bread Modular ENV pin map as ACID) -> PA6 DAC INT43V, firmware codes 0..194 (~0..3.3 V) -> TL072 x1.51 -> protected
  0..5 V ENV OUT + envelope-level LED. ATTACK / RELEASE knobs, MODE button + HR / AR / ASR LEDs,
  REC button + LED. R5-R8 are 1k; the separate ENV LED resistor R13 stays 1k. R20 with R12 holds a silent
  ENV OUT at about -25 mV (the TL072 offset left +2.8 mV, which leaked through modules/vca-mix; user bodge
  on the first board: resistor from the J2 tip to -12 V, confirmed working).
- **P7 placement** (`docs/geometry.json`, 6HP): GATE IN + MIDI IN at the top, ENV OUT + ENV
  LED + MIDI OUT at the bottom (jack columns X7 / X23), pots in the centre column at a 30 mm
  pitch, MODE button in the mode LED row and REC button + LED below (buttons on the left); J3
  power vertical on the right edge between the pots (pin 1 at the bottom) + J4 UPDI on the left
  edge between the pots, both on B.
- **R2 routing** (`hardware/env.kicad_pcb`, research.md 4 and 8; 2026-11-18: R2 = R1 copper + R20 on B
  left of C8 (X120.925 Y121.4), -12V_F link to the U3.4 / C8.2 feed, ENV_OUT dogbone to a via at
  X120.1 Y123.2 and an F run down to the ENV OUT track at Y131.5; 222 tracks / 27 vias; R20.1 2.24 mm from
  RV2.3; silk `ENV R2`): manual divide-and-conquer, 2 layers,
  GND pours on F and B, all SMD on B (U2 between the pots, U3 output stage below J3, input groups
  between the top jacks). ERC 0; KiCad DRC 0 / unconnected 0 / parity 0; no vias in SMD pads;
  copper >= 1.0 mm and courtyards >= 1.02 mm from the edge; SMD >= 2.10 mm from pot / jack pads; tracks >= 1.03 mm from pot / jack / J3 pads and none
  between pot pins (research.md 4.1).
  The native PCB now owns placement and copper: do not rerun `tools/build_layout.py`.
- B silk labels: `JP1 D=DIRECT P=PROT` (+ `D` / `P` under the pads) and `UPDI` / `GND` at J4
  (research.md 5).
- 6HP panel `panels/front-pcb/env-panel.kicad_pcb`, DRC 0. Printed panel `panels/front-cad/` (2.0 mm, plain), not test-printed.
- **JLCPCB export** in `jlcpcb/` (`jlcpcb/README.md`): S5/R2, 2026-11-18, shared `check` manifest equal; carrier bottom Economic, 37 parts / 19 rows,
  all R/C Basic except R12 (ESR18 0.5 W, Extended) + ATtiny1616 Extended + U1 HT7550-1 Preferred Extended; panel Gerbers. The
  manifest is checked by the shared `check`: re-export after any source edit. Not
  supplier-accepted, not built.
- S4 supply/LED conversion is documented in research.md 6; the panel is unchanged since R1.
  Use JP1 protected mode for 3.3 V MIDI senders; direct mode is now 5 V logic only.
- ACID is unchanged: its envelope still lives there too (research.md 1).

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check. Raw reports
go in the ignored `research/`. Firmware in `firmware/` (`firmware/README.md`: ACID envelope without the MCO, MIDI / GATE IN gate
with the PB1 bypass, three models (the selected MODE LED stays lit), REC; USART receive-only because PB2 is GATE IN; JP1 p/d builds), compiled, not
bench-tested. Board
saves from scripts must go through a scratch copy: pcbnew rewrites the `.kicad_pro` on save
(research.md 4).
