# LADDER agent entry point

Read root `AGENTS.md`, then `Code.md`, `README.md` and `docs/research.md`. Module paths are
module-relative.

## Current state

- **S5 schematic** (`hardware/ladder.kicad_sch`, user 2026-11-15: "MIDI less and pure analog",
  6HP, no VCA): Moog transistor ladder (DMMT3904W pairs, 47n NP0), expo cutoff (CUTOFF + CV x
  DEPTH, clamped ~31 kHz), **LM13700 OTA resonance** with the 16bit (1 + k) makeup (RES knob +
  RES CV set the OTA bias current). IN, CV, RES CV in; one OUT. No MCU, MIDI, GATE, envelope,
  REC or VCA (all S3), no vactrol (S5).
- **CV x DEPTH**: J3 -> R9 39k -> DEPTH pot RV2 -> U4A -> `CV_S` -> R14 47k into the cutoff
  summer: 5 V CV at full DEPTH = +8.3 octaves, bipolar (negative closes). R9 keeps a +/-12 V
  mis-patch inside the TL072 common-mode range.
- **CV LEDs D11 (positive) / D12 (negative, S5)**, anti-parallel in the U4A feedback loop:
  I_LED = |V(CV_S)| x (1 / R14 + closed steps), linear from 0 V. **Solder jumpers JP1..JP3**
  (S5, open as shipped) add R6 47k / R7 22k / R8 10k: 0.06 mA at 5 V CV / DEPTH full with all
  open (MCC: 3 mA, dimmed in firmware to 1 %), 8 steps up to 0.53 mA.
- **Resonance (S5)**, user: "I don't mind using an OTA if that's a common standard design which
  works out of the gate", read as the resonance element: U9B summer -> C20 -> R39 10k / R42 1k
  -> U8A (LM13700 half, no linearizing diodes) -> C22 -> feedback base. k = 25 x I_ABC [mA],
  self-oscillation at ~0.17 mA. U7B + Q9 (MMBT5401): I_ABC = 6.16 x (knob / 100k + RES CV /
  100k); knob full or +5 V CV = 0.31 mA, capped ~1.2 mA by R50. The RES knob is on +5V.
- Five TL072 (U4, U5, U6, U7, U9) + one LM13700 (U8). Refs keep their S3 numbers.
- Native ERC `--severity-all` 0; the build asserts the native netlist against `circuit()`
  (108 parts, 62 nets). ngspice: `tools/sim_ladder.py` (core + OTA resonance + bias converter
  + CV / LED loop, models only).
- **P4 placement** (`hardware/ladder.kicad_pcb`, 2026-11-15): 6HP, carrier 29 x 110 mm. IN + RES CV (Y17.5); CV jack + DEPTH (Y35.0), the two CV LEDs under
  DEPTH (Y46.5: D12 X19.3, D11 X24.8, `-` / `+` on the panel); CUTOFF (Y64) and RES (Y90) alone
  on the centre line as the main knobs (26 mm apart, knobs up to ~22 mm); OUT (Y110.4). J10
  upright on B at the right edge beside OUT. THT positions unchanged by the routing.
  Panel `panels/front-pcb/` (DRC 0, 11 holes) + FreeCAD print `panels/front-cad/`.
- **R1 routing** (2026-11-15, user: "Go this looks good. Do the routing too."): manual divide
  and conquer, **4 layers** (F signal, In1 GND, In2 +12V_F plane, B signal), all 95 SMD parts +
  JP1..JP3 on B, F carries the long north-south runs, three B bridges in the empty pot / jack
  zones (RES_CV under DEPTH, -12V_F above RES, AIN_BUF below RES). 521 tracks / 81 vias.
  Shared check (`research/r1-check/`): ERC 0, DRC 0, **unconnected 0**, parity 0, no
  exclusions; independent pad-net compare 0 differences; no vias in SMD pads, no tracks on
  In1 / In2, In2 one piece, In1 one piece + 7 spoke-tied fragments between GND pads; SMD >=
  2 mm from pot / jack pads (closest 2.015 mm), courtyards >= 1.0 mm from the edge (RV2
  1.015 mm). B silk `LADDER R1`, `LED` `1` `2` `3` at JP1..JP3. Record: `docs/research.md`
  section 8; stage scripts in the ignored `research/route/` (`lib.py`, `s00`..`s08`, each
  stage re-runs from the previous snapshot in `snap/`).
- **Fab review (2026-11-15)**, `docs/research.md` section 9: B silk texts 1.0 mm high,
  JLC04161H-7628 stackup recorded, no copper or placement change (still R1); checks 0 after the
  edits (`research/fab/check-post/`); scripts in the ignored `research/fab/` (`review.py`,
  `fab_r1.py`). Judged and kept: U8 bypass caps 5.9 mm routed, U1 input cap through the In2
  plane. Live stock 2026-11-15: DMMT3904W C155305 684 (6 per board). Plain Extended: DMMT3904W,
  47n NP0, ESR18 1k, LM13700; HT7550-1 is Preferred Extended.
- **Not done**: JLCPCB export (`jlcpcb/` holds none; the stale S3 / R2 set was
  removed), bench test. Bench check item: LTAIL runs beside AIN_BUF for 12 mm (estimate only).
- The S3 / R2 10HP design (ATtiny1616 envelope, REC, VCA; routed and exported, never built) is
  in git history: commit `b32225b` and before. S4 (vactrol resonance, one LED) was never
  committed; its sources are copied in the ignored `research/s4-backup/`.
- No firmware: there is no MCU.

## Boundaries

Shared tools stay in `../../opt/`. Raw reports, renders and sim decks go in the ignored
`research/` (P4 check: `research/p4-check/`; renders: `research/render/s5/`, script
`research/s5/render.py`; R1 renders: `research/render/r1/`). Routing follows the root manual
divide-and-conquer rules, straight on `hardware/ladder.kicad_pcb`; `tools/build_layout.py` must
not be re-run for the carrier (it refuses a board with tracks; `--panel-only` is fine). Accepted fabrication outputs live in `jlcpcb/`; never hand-edit
them. No merges, pushes, orders or uploads.
