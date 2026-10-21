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
- Schematic nets connected for readability; THT placement only, **no routing**.

## Design rules kept from the repo

- BM 32bit-5v GPIO map (I2S IO11-14/IO21, I2C IO47/48, CV IO9/IO10, button IO8, LED IO18, MIDI RXD0).
  User 2026-10-21: ESP32 pins and op-amp halves may change for routing, but every change that
  touches firmware is logged in `docs/firmware-pins.md` (BM GPIO -> 32bit GPIO, change log,
  behaviour differences). R1 so far: CV1 = U7B/U6B, CV2 = U7A/U6A; no ESP32 pin moved.
  IO35-37 (octal PSRAM) stay open.
- modules/16bit parts for jacks (PJ301M-12), pots (BM RV09 50k), MODE switch, LED, power entry,
  MIDI front end, CV chain. BM footprints preferred (ES8388, RV09, K2, FB1 on C_0805).
- All SMD on B (one assembly side); jacks, pots, LED, header and SW1 hand-soldered.
- PWR_FLAGs only where ERC can't see a source: J6 entry, ±12V_F, +3V3_ESP32 (FB1), +3V3_8388 (R5).
- Routing (later): manual divide and conquer, no autorouters, no vias in SMD pads (root `AGENTS.md`).

## Sources and generators

- `tools/build_schematic.py` + `tools/circuit32.py` own `hardware/32bit.kicad_sch`, `32BIT.kicad_sym`
  and `sym-lib-table` (modules/16bit drawing engine). The build asserts nothing dangles and that
  the native netlist equals the circuit table.
- `tools/build_layout.py` places from `docs/geometry.json`, parks unplaced SMD off the board and
  takes nets/values/fields from the native netlist. Once SMD placement starts by hand on the board,
  the board owns placement: do not rerun it over hand work.
- `tools/import_footprints.py` rebuilds `hardware/32BIT.pretty` / `32BIT.3dshapes` (`PROVENANCE.json`).

## Verification (S2, 2026-10-21)

- Native ERC `--severity-all`: 0. Native DRC `--severity-all --schematic-parity`: 0 violations,
  0 parity, 236 unconnected (unrouted). Panel DRC 0.
- Shared `kicad_tools.py check`: ERC 0, DRC 0 violations, parity 0, 236 unconnected; `order_ready: false`.
- Not done: SMD placement, routing, sourcing check, 3D fit, bench.
