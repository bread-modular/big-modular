# MOTION contract (S1 schematic, P1 placement, R1 routing)

| | |
|---|---|
| KiCad project | `hardware/motion.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/motion-panel.kicad_{pro,pcb}` (FR4, NPTH only; P2 adds the top-clip M3 hole) |
| Top clip | `panels/top-clip/` (printed, holds the carrier top edge to the panel; `docs/geometry.json` `top_clip`) |
| Generators, profile | `tools/` (`build_schematic.py`, `build_layout.py`, `import_footprints.py`, `render_fit.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Evidence | `docs/fit/` (native ERC/DRC JSON, renders), `docs/motion-schematic.pdf`, `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` |

## Fixed by the brief (user, 2026-11-15)

- 6HP. Four knobs, four CV outputs. One REC button: hold it and move a knob to record
  that knob. An LED shows the motion.
- One range selector for the module: off = 0..+5 V, on = -5..+5 V.
- A recorded take is moved up and down with its knob.
- ATtiny1616 + MCP4728 + MB85RC256V FRAM; takes are recorded straight into the FRAM
  (always saved). Hold REC 5 s without moving a knob = erase every take.

## Decisions made in S1 (see `docs/research.md` section 2; D1 is not user-confirmed)

- RANGE = a second tact button + LED (on = -5..+5 V); the range is firmware only, the
  output stage is always -5..+5 V.
- Motion LEDs on MCU PWM pins; all LEDs through 10k.
- DAC reference = +5VA = output offset (ratiometric); 160 Hz low-pass per output.
- Knob zigzag with the motion LED beside each knob; power header on B between the
  lower jacks.

## Design rules kept from the repo

- Jacks: QingPu WQP-PJ301M-12 (BM AudioJacks footprint, edited as `modules/midi`). Pots:
  BM `Potentiometer_RV09`, copper unedited, user stock 50k (no bushing, no nut). Switches:
  stock KiCad `SW_PUSH_6mm_H7.3mm`, as `modules/8bit`. Everything else is stock KiCad.
  `hardware/MOTION.pretty/PROVENANCE.json` records every source and hash.
- All JLC-assembled SMD parts go on the back; jacks, pots, LEDs, switches and headers
  are hand-soldered.
- Root rules: 1 mm board-edge keep-out (`min_copper_edge_clearance` 1.0, courtyards
  measured), SMD pads >= 2 mm from pot/jack pads, no vias in SMD pads, manual
  divide-and-conquer routing.
- PWR_FLAGs: `#FLG01` GND, `#FLG04` -12V, `#FLG05` +12V at the J5 entry; `#FLG02` +12V_F,
  `#FLG03` -12V_F behind D7/D8; `#FLG06` +5VA behind R1. No others.

## Sources and generators

- `tools/build_schematic.py` owns `hardware/motion.kicad_sch`, `MOTION.kicad_sym` and
  `sym-lib-table` (stock KiCad 10 symbols, flattened and pinned; the MB85RC256V symbol is
  the stock FM24C64B renamed, same pinout). Parts are joined by drawn wires and power
  symbols, with labels at the MCU and for the I2C bus; the build asserts nothing dangles
  and that the exported netlist equals `CIRCUIT`.
- `tools/build_layout.py` places the THT parts from `docs/geometry.json`, parks every SMD
  part off the right board edge and takes references, values, fields and pad nets only
  from the native netlist. It **refuses to overwrite a carrier that has tracks**
  (`build_layout.py panels` rebuilds only the panel).
- `tools/import_footprints.py` rebuilds `hardware/MOTION.pretty` and `MOTION.3dshapes`.
  A rerun gives every footprint new UUIDs: once the board is routed, restore the
  existing files and add only new entries.
- `tools/render_fit.py` writes the `docs/fit/` renders from a research copy (THT parts
  only, panel STEP at Z 10 mm). pcbnew rewrites the `.kicad_pro` on save: the render
  works on copies only.

## Routing contract (R1, 2026-11-15)

- 2 layers. B carries every SMD part and the local links; F (THT parts only) carries the
  long runs: four output trunks and the ±12 V feeds from the TL074 down between the RV4
  lugs to the jack rows, and the knob / LED / button links out of the MCU hop vias.
- GND pours on F and B, clearance 0.25 mm; **solid on SMD pads, thermal reliefs on THT
  pads** (hand-soldered). The pours are in pieces; `research/r1/b10_gnd.py` adds one
  stitching via wherever an F piece and a B piece overlap, `b11` ties the last four pads.
- MCU I2C reaches the FRAM pins from the left, under the SOIC body, so U4.7 / U4.8 / C9
  get +5 V and GND through two vias under the body.
- One ground via in the U2 exposed pad (the allowed exception); every other via is clear
  of every SMD pad.
- Batches and helpers are in the ignored `research/r1/` (`b01`..`b12`, `router.py`:
  one connection per call; `gndnet.py`, `pour.py`: ground checks). The board is the source.

## Verification (S1 / P1 / R1, 2026-11-15)

- Native ERC `--severity-all`: 0; the schematic build asserts the exported netlist equals
  `CIRCUIT` (49 named nets, 70 parts).
- Shared `check`: `no_findings_in_requested_checks`, manifest equal (5 sources): DRC 0
  violations / 0 unconnected / 0 parity with refill and with the saved fills, ref/pin/net
  parity equal, no exclusions (`docs/fit/carrier-drc.json`). Panel DRC 0 / 0.
- Measured: SMD pads >= 2.025 mm from pot / jack pads; courtyards >= 1.015 mm, track and
  via copper >= 1.1 mm from the edge; one GND net (`gndnet.py`).
- Not done: JLCPCB preview, requirements audit, bench, second review of the route.

## Firmware (2026-11-24)

`firmware/` (`firmware/README.md`): ATtiny1616 sketch on the S1 pin map, built with the shared
`opt/attiny1616-tools`. `motion/MotionRecorder.h` is the modules/16bit cpx4 free-motion recorder
behaviour on a frame store (the FRAM), plus the 5 s erase; `test.sh` runs it on the host. Compiled
(8810 B flash, 331 B RAM) and host-tested, not flashed, not bench-tested.
