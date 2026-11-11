# LADDER agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S3 schematic** (`hardware/ladder.kicad_sch`): an analog version of the modules/16bit
  polysynth ladder filter. Moog transistor ladder (DMMT3904W pairs, 47n NP0), expo cutoff
  (CUTOFF + envelope x DEPTH, clamped ~31 kHz), vactrol resonance (S2, user 2026-11-09) with the
  16bit (1 + k) makeup (RES knob + RES CV drive the LED), ATtiny1616 envelope (ENV TIME, GATE or
  MIDI), Bread Modular V2CA vactrol VCA with CURVE; FILTER OUT and VCA OUT.
- **S3 (user 2026-11-09): envelope automation recording**: REC button SW1 (PC2) + LED D11 (PC3)
  as modules/acid, recording ENV TIME + DEPTH (shared CvRecorder, firmware not written). DEPTH
  moved into the MCU (RV2 on PA7): DAC = envelope or CV (PA2, sensed on PA3) x DEPTH -> U4A ->
  cutoff; the VCA gets the undepthed envelope as PB0 PWM (R52/C36/R53/C37) or the CV through U3.
- Native ERC `--severity-all` 0; the build asserts the native netlist against `circuit()`
  (135 parts, 82 nets). ngspice check of the core: `tools/sim_ladder.py` (models only).
- **P2 placement** (`hardware/ladder.kicad_pcb`, user 2026-11-09: THT placed, more knob room,
  modules/hats as the example, "don't route yet"): 10HP, 4 layers, knob grid 30 x 27 mm,
  vactrols on B between the knob columns, J11 UPDI at the left edge; P2: J10 upright on B at the
  right edge between DEPTH and CURVE, bottom jacks down to Y110.3, knob rows down 5 mm (Y37/64/91); every SMD part parked on B off the right edge. Shared check: ERC 0, DRC 0, parity 0,
  294 unconnected (unrouted). Panel `panels/front-pcb/` (DRC 0) + FreeCAD print `panels/front-cad/`.
- **R1 routing done** (user 2026-11-09 "start routing" / "continue"; manual divide and conquer,
  batch scripts `research/route/b00..b25_*.py`, replayed from `research/route/p2-base.kicad_pcb` by
  `research/route/build.sh`; checks `chk.py` / `drcsum.py`; `astar.py` is a one-connection path
  finder whose suggestions were checked and tidied by hand, used for REC_SW / LED_REC only).
  b00-b17: planes, power entry, ladder core + bias, expo, input amp, front-ends, cutoff summer,
  followers, diff amp, output amp, U11 + FB summer + VCA amp, VCA LED driver, -12V_F, audio input.
  b18-b25: U1 HT7550 moved into the free B area above U12 (C3 / C4 beside it), C5 / C7; MCU lines
  north (DAC through the RV4 1-2 gap, B lanes Y82.6 / 83.2 / 83.8 above U12 for GATE_N / RX / DAC,
  CV_SENSE / CVIN_DIV left of the RV4 lug, CVIN_DIV on B up the J5 side), +5V riser + top band;
  U2 left side re-fanned for a pin-3 GND via; R40 / R41 left of the RV4 lug; D8 / D10 / R42 in a
  row above U7; R39 west of U12; RES_S / RES_A / RES_X / ENV_T / UPDI cross under U12 on B (the
  "corridor") and come down the left column on F through the RV1 lug gap and pin gaps; R7 by J11;
  +5V for U3 / C7 / RV2.3 returns along the right edge on B (Y80 to the C4 riser); REC_SW /
  LED_REC across the south (R54 under D11). Six dangling corner vias of earlier batches removed.
  Native DRC 0 (no warnings, no dangling vias), unconnected 0, parity 0; shared check ERC 0 / DRC 0
  / unconnected 0 / parity 0 (`research/r1-check/`); no vias in SMD pads, no In1 tracks, In2
  +12V_F one piece, In1 GND one main piece + four small spoke-tied fragments (2.6 / 2.6 / 1.0 / 1.0
  mm², as before R1); SMD >= 2 mm from pot / jack pads (closest D9 2.01 mm), courtyards >= 1 mm
  from the edge.
- **R2 fab review + JLCPCB export** (user 2026-11-10 "check it, improve as needed, make it FAB
  ready"; edits straight on the board by `research/fab-review/fix1.py` / `fix2.py`, so
  `research/route/build.sh` reproduces R1 only). Fixed: R32 moved 3.6 mm east (was 0.68 mm from
  the hand-soldered SW1 GND pad; closest SMD to SW1 now R33 2.28 mm); C35 moved to U9.4 with its
  own GND via (routed pin-to-cap 10.2 -> 2.5 mm), -12V_F bus straight down from D2; GND vias at
  U11.3 / D3.2 pulled 0.35 / 0.30 mm off their pads; B silk `P` / `D` at JP1 and `LADDER R2`;
  JLC04161H-7628 stackup recorded; zone fills saved. Judged and kept for the first prototype (not
  waived): U3 +5V 11.3 mm to C7 (static uA switch); SMD 1.28-1.92 mm from the U12 / J10 / J11
  hand-soldered pins (the 2 mm rule covers pots / jacks: closest D9 - RV2 2.01 mm). 734 tracks /
  141 vias; shared check ERC 0 / DRC 0 (no warnings, no exclusions) / unconnected 0 / parity 0
  (`research/fab-final/`), planes as R1, copper >= 1.2 mm and courtyards >= 1.08 mm from the edge.
  Export in `jlcpcb/` (bottom Economic, 116 parts / 36 rows; 18 THT + JP1 by hand; panel
  Gerbers), not supplier-accepted, not built. Open: Extended passives (47n NP0 1206, 1k 0.5 W
  1206) are a user decision; ATtiny1616 stock 238 at lookup; supplier preview. Read
  `jlcpcb/README.md` before release work.
- No firmware.

## Boundaries

Shared tools stay in `../../opt/`. Raw reports, renders and sim decks go in the ignored
`research/` (P2 check: `research/p2-check/`; R2 fab review: `research/fab-review/`, `research/fab-final/`). Routing follows the root manual divide-and-conquer
rules, straight on `hardware/ladder.kicad_pcb`; `tools/build_layout.py` must not be re-run once
routing starts (it refuses a board with tracks). Accepted fabrication outputs live in `jlcpcb/`; never
hand-edit them. No merges, pushes, orders or uploads.
