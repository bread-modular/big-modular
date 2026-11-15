# ladder contract (S5 schematic, P4 placement, R1 routing)

| | |
|---|---|
| KiCad project | `hardware/ladder.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/ladder-panel.kicad_{pro,pcb}` (FR4, 6HP); `panels/front-cad/` (printable) |
| Circuit intent / source profile | `tools/build_schematic.py`, `tools/kicad-project.json` |
| Placement contract | `docs/geometry.json`; native PCB owns SMD placement and copper once routing starts |
| Circuit rationale, numbers, ngspice check | `docs/research.md`, `tools/sim_ladder.py` |
| Routing record | `docs/research.md` section 8; batch scripts in the ignored `research/route/` |
| Fabrication outputs | `jlcpcb/` (S5 / R1 export 2026-11-15; shared exporter only) |

## Fixed by the brief (user 2026-11-15)

- **Pure analog, no MIDI**: no MCU, no firmware, no VCA. Classic transistor ladder.
- Inputs on top: **IN**, **CV**, **RES CV**; **OUT** at the bottom.
- Knobs: **CUTOFF** and **RES** are the main knobs with room around them; **DEPTH** attenuates
  the CV. RES CV has no control.
- **CV LED** after DEPTH: dimmer than the modules/mcc LEDs, by the circuit (no firmware), and
  it follows the whole CV / DEPTH range. LEDs in the U4A buffer loop, 21 uA per volt at `CV_S`
  as shipped.
- **Solder jumpers set the LED brightness, and a second LED shows negative CV** (S5): JP1..JP3
  (open as shipped) add loads R6 / R7 / R8; D11 positive, D12 negative, anti-parallel.
- **6HP.** Schematic + THT placement + panel done; **routed** (R1, user 2026-11-15: "Go this
  looks good. Do the routing too.").
- RES CV by an **LM13700 OTA** (S5; user 2026-11-15: "I don't mind using an OTA if that's a
  common standard design which works out of the gate", read as the resonance element). It
  replaces the vactrol of S2..S4 (user 2026-11-09: "doesn't need to be accurate").

## Rules

- `tools/build_schematic.py` owns `hardware/ladder.kicad_sch`, `LADDER.kicad_sym` and
  `sym-lib-table`: modules/acid's generator (pinned stock KiCad 10 symbols, 1.27 mm grid wire
  router, native netlist assertion) with this module's circuit, placement, sourcing and notes.
  `LB0..LB4` are the only label-joined signal nets. `kicad-cli sch upgrade --force` writes the
  file natively.
- Symbol edits (`docs/schematic-symbols.json`): footprint filter of `Conn_02x05_Odd_Even`
  (as acid), and **DMMT3904W** = stock `MMDT3904` renamed with the DMMT3904W pin
  numbers (1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2; Diodes DS30311 p. 1).
- `tools/import_footprints.py` (acid's, plus SOT-363) wrote `LADDER.pretty`, `LADDER.3dshapes`
  and `fp-lib-table`; `PROVENANCE.json` records sources and hashes. S5 added SOIC-16 and the
  2-pad solder jumper (the existing files were kept byte-identical, only the two new entries
  were added to `PROVENANCE.json`). The library still holds S3 footprints no longer used.
- `tools/build_layout.py` (modules/hats's builder) writes the carrier and the panel from
  `docs/geometry.json` and the native netlist; it refuses to overwrite a carrier with tracks.
  `--panel-only` regenerates only the panel. **The carrier is routed: the native PCB is the
  source of truth for SMD placement, copper and B silk; do not re-run the carrier build.**
- Pots: BM `Potentiometer_RV09`, stock 50k linear. Jacks PJ301M-12. Two CV LEDs, 3 mm THT
  (D11 red; D12 a second colour, user's choice). No vactrol. JP1..JP3 are copper only (no BOM /
  CPL row) and go on B.
- 1 mm board-edge keep-out (copper-edge rule 1.0 mm; every courtyard >= 1.0 mm, closest RV2
  1.015 mm incl. line width). Every SMD pad >= 2 mm from hand-soldered jack / pot pads (closest
  2.015 mm).
- Routing: manual divide and conquer (root AGENTS.md), no autorouters, no vias in SMD pads.
  No ignored ERC/DRC rule severities, no exclusions.
- **4 layers**: F signal (north-south runs; only THT parts there), In1 solid GND, In2 +12V_F
  plane, B signal with every SMD part. No tracks on In1 / In2. -12V_F and +5V are tracks
  (0.4 / 0.3 mm).
- PWR_FLAGs: GND, +12V, -12V (header side), +12V_F, -12V_F.

## Verification (S5 / P4 / R1, 2026-11-15)

- `python3 -B tools/build_schematic.py`: router completes every wired net; native netlist
  equals `circuit()` (108 parts, 62 nets).
- `kicad-cli sch erc --severity-all`: 0 violations.
- P4 (before routing): `python3 -B tools/build_layout.py`; shared check ERC 0, DRC 0, parity 0,
  230 unconnected. Panel DRC 0, 11 holes.
- **R1**: shared `kicad_tools.py check --config modules/ladder/tools/kicad-project.json`
  (`research/r1-check/`): ERC 0, DRC 0 violations, **0 unconnected**, parity 0, no exclusions;
  DRC on the saved plane fills (no refill) 0 too.
  Independent pad-net compare against the native netlist: 301 pins, 108 refs, 71 nets, 0
  differences. `research/route/audit.py`: 521 tracks / 81 vias, none on In1 / In2, no
  zero-length or duplicate segments, no via in or at an SMD pad (closest 0.16 mm, same net),
  In2 one piece, In1 one piece plus 7 spoke-tied fragments between the GND pads of J10 and the
  jacks.
- `python3 -B tools/sim_ladder.py`: cutoff ~55 Hz .. 17.1 kHz, passband within 2 % with
  resonance, self-oscillation from I_ABC ~0.17 mA (knob ~60 %), 6 .. 6.7 Vpp at OUT; bias
  converter 0.31 mA at knob full or +5 V RES CV; CV LEDs 21 uA per volt at `CV_S` with the
  jumpers open, both polarities, 8 jumper steps to 188 uA per volt (models, not measurements).
- Live LCSC lookups 2026-11-15 for the S5 parts (LM13700MX/NOPB C174050 Extended, MMBT5401
  C8326 Basic, 22k C31850 Basic).
- **Fab review (2026-11-15)**, `docs/research.md` section 9: B silk texts 1.0 mm / 0.15 mm,
  JLC04161H-7628 stackup recorded, no copper change (still R1); shared check ERC 0 / DRC 0 /
  unconnected 0 / parity 0 (`research/fab/check-post/`), saved fills equal a fresh refill,
  DMMT3904W pin-out re-read from DS30311; trial export 95 placements / 30 rows (bottom).
- Routed, fab-reviewed and exported (`jlcpcb/`, 2026-11-15: 95 placements / 30 rows, bottom,
  manifest equal); not supplier-accepted, not built, not bench-tested.
