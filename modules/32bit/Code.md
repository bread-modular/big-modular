# 32bit contract (S2 schematic, S2 THT placement)

| | |
|---|---|
| KiCad project | `hardware/32bit.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/32bit-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Generators, profile | `tools/` (`build_schematic.py`, `circuit32.py`, `build_layout.py`, `import_footprints.py`, `sexp.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Evidence | `docs/fit/` (native ERC/DRC JSON, render), `docs/32bit-schematic.pdf`, `docs/schematic-symbols.json` |

## Fixed by the brief (user, 2026-10-21)

- Bread Modular `32bit-5v` (ESP32-S3-WROOM-1U-N16R8 + ES8388) as a Eurorack module, **6HP**, 4-layer carrier.
- Top: **MIDI in**, **two audio inputs**, **two CV inputs**. Bottom: **two outputs**. **Two pots**
  (CV1/CV2 attenuators, unpatched = knob, as BM). **Mode button** and **LED**.
- USB-C and BOOT/RESET as modules/16bit (B side, top edge).
- S2 (user, 2026-10-21): the radio is never used; IN R is **not** normalled (firmware handles mono);
  OUT L/OUT R sit at the side edges (X5.5/X24.5) like the top jacks.
- Schematic nets connected for readability. R1 (user 2026-10-21): all parts placed and routed by hand
  (manual divide and conquer, root `AGENTS.md`); batch scripts and DRC reports in `research/r1/`.

## Design rules kept from the repo

- BM 32bit-5v GPIO map (I2S IO11-14/IO21, button IO8, LED IO18, MIDI RXD0) except the R1 moves below.
  User 2026-10-21: ESP32 pins and op-amp halves may change for routing, but every change that
  touches firmware is logged in `docs/firmware-pins.md` (BM GPIO -> 32bit GPIO, change log,
  behaviour differences). R1: CV1 = U7B/U6B, CV2 = U7A/U6A; CV1/CV2 ADC IO9/IO10 -> IO1/IO2;
  I2C IO47/IO48 -> IO38/IO39; codec inputs LIN1/RIN1 -> LIN2/RIN2.
  IO35-37 (octal PSRAM) stay open.
- modules/16bit parts for jacks (PJ301M-12), pots (BM RV09 50k), MODE switch, LED, power entry,
  MIDI front end, CV chain. BM footprints preferred (ES8388, RV09, K2, FB1 on C_0805).
- All SMD on B (one assembly side); jacks, pots, LED, header and SW1 hand-soldered.
- PWR_FLAGs only where ERC can't see a source: J6 entry, ±12V_F, +3V3_ESP32 (FB1), +3V3_8388 (R5).
- Routing: manual divide and conquer, no autorouters, no vias in SMD pads (root `AGENTS.md`). F carries
  the long runs and every crossing of the pot row (RV1/RV2 tab gaps, not between pot pins); In1 solid GND,
  no tracks; In2 +3V3 plane, one short +3V3_8388 hop joining the codec's two supply islands (plane stays
  one piece). U8 has +5V tab patches on F and B tied by four thermal vias beside the tab.

## Sources and generators

- `tools/build_schematic.py` + `tools/circuit32.py` own `hardware/32bit.kicad_sch`, `32BIT.kicad_sym`
  and `sym-lib-table` (modules/16bit drawing engine). The build asserts nothing dangles and that
  the native netlist equals the circuit table.
- `tools/build_layout.py` places from `docs/geometry.json`, parks unplaced SMD off the board and
  takes nets/values/fields from the native netlist. Once SMD placement starts by hand on the board,
  the board owns placement: do not rerun it over hand work.
- `tools/import_footprints.py` rebuilds `hardware/32BIT.pretty` / `32BIT.3dshapes` (`PROVENANCE.json`).

## Verification (R1 routed, 2026-10-21)

- Native ERC `--severity-all`: 0. Native DRC `--severity-all --schematic-parity --refill-zones`:
  0 violations, 0 unconnected, 0 parity, no exclusions. Panel DRC 0.
- Shared `kicad_tools.py check`: ERC 0, DRC 0 violations, 0 unconnected, parity 0; `order_ready: false`.
- Manual: no vias in/touching SMD pads, no tracks on In1, In1 GND and In2 +3V3 planes one piece each,
  no zero-length/duplicate segments (off-grid ends only on 1.27 mm pad axes).
- JLCPCB export: `jlcpcb/` re-exported from R2 (2026-10-22; bottom side, 90 parts / 38 rows, BOM
  unchanged from R1, live catalog audit from R1). U1 (C3013946) is Standard-PCBA only, not Economic:
  user chose Standard PCBA (2026-10-22). Shared `check` manifest equal.
- Not done: 3D fit, supplier acceptance, bench.

## Verification (R2 hand-solder clearance, 2026-10-22)

- Every SMD pad >= 2.0 mm (copper to copper) from every jack and pot pad, lugs included (R1: 35 parts
  under 2 mm), except four user-accepted parts (option A, 2026-10-22: the user moved them inward for
  edge margin and kept them): R5 1.33 mm from RV2, C27 1.62 / R55 1.63 / C46 1.75 mm from J5. Next
  closest: U6, R15, R18 2.02 mm; C6, C25, C26 2.03 mm; R54 2.06 mm. Moves and free-space map:
  `docs/research.md` section 7.
- Native ERC 0; native DRC `--severity-all --schematic-parity --refill-zones`: 0 violations,
  0 unconnected, 0 parity, no exclusions. Shared `check`: ERC 0, DRC 0 / 0 / 0.
- Manual: no vias in/touching SMD pads, no tracks on In1, In1 GND and In2 +3V3 one piece each, no
  dangling ends, zero-length or duplicate segments; new off-grid points only on pad axes.
- Courtyards under 0.5 mm from the edge (copper >= 0.5 mm): R4 0.49 mm, plus R1's J7, SW2/SW3, U1 and
  the jacks. After the user's moves C6 is 0.53 mm, C27/R55 0.82 mm, R5 > 1 mm.
- B silk MIDI JP1 labels as modules/16bit: P (pad 1 RX_Q, protected), D (pad 3 MIDI_IN, direct),
  legend P=PROT / MIDI JP1 / D=DIRECT beside it. DRC 0 / 0 / 0 after adding them.
