# drive contract (S1 schematic, P2 placement, R2 routing)

| | |
|---|---|
| KiCad project | `hardware/drive.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/drive-panel.kicad_{pro,pcb}` (FR4, 6HP) |
| Circuit intent / source profile | `tools/build_schematic.py`, `tools/kicad-project.json` |
| Placement contract | `docs/geometry.json`; the native PCB owns SMD placement and copper once routing starts |
| Circuit rationale, numbers, ngspice check | `docs/research.md`, `tools/sim_drive.py`, `docs/sim/` |
| Sourcing evidence | `docs/sourcing-candidates.json` (live lookups 2026-11-15) |

## Fixed by the brief

- A **really nice overdrive with a MIX knob** and **CV controls** (user, 2026-11-15), the
  "drive + wavefolder" approach, **built on OTAs** ("to test things out"), **simulated first**.
- **Mono, single, 6HP. No CV on MIX.** CV on DRIVE and FOLD, adding to the knobs (no attenuators).
- S1 / P1 was schematic + THT placement only. Then (user, 2026-11-15): **power socket to the
  side, pots moved down into that space** (P2), **route it, fab-review it, export it** (R1).

## Rules

- `tools/build_schematic.py` owns `hardware/drive.kicad_sch`, `DRIVE.kicad_sym` and
  `sym-lib-table`: modules/vca-mix's generator (pinned stock KiCad 10 symbols, explicit wires,
  native netlist assertion). Every net is wired; DRY, X, Y and IABC_A also join two blocks by a
  label. `kicad-cli sch upgrade --force` writes the file natively.
- Symbol edits (`docs/schematic-symbols.json`): the footprint filter of `Conn_02x05_Odd_Even`,
  and **LM13700 pins 5 / 12 typed passive**: they are current outputs and five of them are summed
  on `YS`. This is a pin-type correction, not an ERC waiver; no rule severity is changed.
- `tools/sim_drive.py` builds its deck from `circuit()`: change a value in the schematic
  generator and the simulation follows. Re-run it after any circuit change.
- `tools/import_footprints.py` (vca-mix's, plus SOIC-16 and SOT-23, no vactrol) wrote
  `DRIVE.pretty`, `DRIVE.3dshapes` and `fp-lib-table`; `PROVENANCE.json` records sources and hashes.
- `tools/build_layout.py` (modules/vca-mix's builder) writes the carrier and the panel from
  `docs/geometry.json` and the native netlist; it refuses to overwrite a carrier with tracks.
  `--panel-only` regenerates only the panel.
- Pots: BM `Potentiometer_RV09`, stock 50k linear. Jacks PJ301M-12.
- Q1 / Q2 (DRIVE expo pair) go side by side on the board, same orientation.
- PNP = SS8550 (C8542, Basic); MMBT3906 is Extended at JLCPCB.
- 1 mm board-edge keep-out (copper-edge rule 1.0 mm). Every SMD pad >= 2 mm from hand-soldered
  jack / pot pads once placed.
- Routing: manual divide and conquer (root AGENTS.md), no autorouters, no vias in SMD pads.
  No ignored ERC/DRC rule severities, no exclusions.
- Layers (R2, user 2026-11-15): **2 layers**, F / B, one GND zone poured on both; +12V and -12V
  run as 0.4-0.5 mm tracks. Every F pour piece cut off by a trunk needs a stitching via into the
  B pour (`research/route/pieces.py`, `voids.py`). R1 was F / In1 GND / In2 +12V / B. J10 stays upright at the right edge on B (root AGENTS.md, side power header).
- PWR_FLAGs: GND, +12V, -12V.

## Verification (S1, 2026-11-15)

- `python3 -B tools/build_schematic.py`: native netlist equals `circuit()` (92 parts, 50 nets).
- `kicad-cli sch erc --severity-all`: 0 violations.
- `python3 -B tools/sim_drive.py`: wet gain -0.6 .. +31.3 dB over the DRIVE knob, 6.5 dB / V
  at DRIVE CV, limit +35 dB; fold 0 .. 1.0 over the FOLD knob, 0.2 / V, limit 1.06; transfer
  with two folds per side; OUT in phase with IN for dry and wet; TONE 615 Hz .. 16.8 kHz;
  converter steps without overshoot (models, not measurements).
- Not built.

## Verification (P2 / R1, 2026-11-15)

- Shared `kicad_tools.py check --config modules/drive/tools/kicad-project.json`: ERC 0, DRC 0
  violations (no exclusions), unconnected 0, parity 0, source manifest equal. Panel DRC 0.
- 393 tracks / 79 vias (0.6 / 0.3 mm, tented). No vias in SMD pads (closest via to a pad
  0.15 mm, same net), no tracks on In1 / In2, no zero-length / off-angle / off-centre segments.
- In2 +12V one piece. In1 GND one piece plus five spoke-tied fragments (2 x 2.63 mm2 between
  the J10 GND pins, 3 x 1.0 mm2 between the S / TN pads of J1-J3).
- SMD pads to pot / jack pads >= 2.025 mm (R27 / R28 at RV1). Copper to the edge >= 1.1 mm,
  courtyards >= 1.02 mm (RV1-RV4). J10 pad edges 1.95 mm from the RV4 pins, 1.87 mm from the
  J4 tip pad (THT to THT).
- Export: 83 placements / 29 BOM rows, all on B; upload mirrors byte-identical.

## Verification (R2, 2 layers, 2026-11-15)

- Shared `kicad_tools.py check`: ERC 0, DRC 0 violations (no exclusions), unconnected 0,
  parity 0, source manifest equal (`research/r2-final-check/`). Panel unchanged.
- 455 tracks / 102 vias: R1's 393 / 79 untouched + 62 +12V segments, 7 +12V vias, 16 GND
  stitching vias. No vias in SMD pads (closest 0.15 mm, same net), no zero-length / off-angle
  segments, track ends centred.
- GND: B pour 1759 mm2 main piece + two pad / via-tied pieces (20.8, 7.2 mm2); F pour 1713 mm2
  main piece + 12 pieces of 5.9-83.7 mm2 between the trunks, each with 1-7 vias into the B
  pour; 7 spoke-tied fragments per layer between the J10 / jack GND pads.
- +12V path D1 -> R12 / R16 about 115 mm of 0.4-0.5 mm track: about 0.13 ohm, 3 mV at 22 mA
  (calculated).
- Distances as R1: SMD pads >= 2.025 mm from pot / jack pads, copper >= 1.1 mm and courtyards
  >= 1.02 mm from the edge.
- Export: 2 copper layers, 83 placements / 29 BOM rows; BOM and positions byte-identical to R1;
  mask and paste Gerbers unchanged, 23 more via drills.
