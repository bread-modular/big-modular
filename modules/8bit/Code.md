# 8bit contract (S6 schematic, 6HP, R1 routed carrier)

| | |
|---|---|
| KiCad project | `hardware/8bit.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/8bit-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| LFO panel | `panels/front-pcb/8bit-lfo-panel.kicad_{pro,pcb}` (no J1 MIDI / RV3 holes; J1 and RV3 not fitted, no wire bridge on S6, `docs/mechanics.md`) |
| 4HP LFO panel | `panels/front-pcb/8bit-lfo-4hp-panel.kicad_{pro,pcb}` for the old 4HP S5/R4 carrier (J1 MIDI hole kept, no RV3 hole, RV3 pin 3 -> wiper bridge; `docs/mechanics.md`, 2026-11-23) |
| Button cap | `panels/button-actuator/` (FreeCAD generator, one-piece cap STL/STEP) |
| Generators, profile | `tools/` (`build_schematic.py`, `build_layout.py`, `import_footprints.py`, `kicad-project.json`). Copper lives in the native PCB |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md`; JP1 guide `docs/jumpers.md` |
| Evidence | `docs/fit/` (native ERC/DRC JSON, renders), `docs/8bit-schematic.pdf`, `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` |
| Fabrication export | `jlcpcb/` (shared exporter, bottom-side assembly; `jlcpcb/README.md`): S6/R1 carrier, panel and optional LFO panel, 2026-11-14 |

## Fixed by the brief

- Based on Bread Modular `8bit` (ATtiny1616, DAC audio), as a Eurorack module, **6HP**
  (user, 2026-11-14; was 4HP to S5).
- **Panel order** (user, 2026-11-14): **MIDI in and CV in on one line** at the top; the three
  knobs spread over the middle (zigzag, 20 mm row pitch, the jack-to-knob spacing of
  `modules/mcc`); **MODE (record) button and its LED on one row** above the outputs;
  **OUT (DAC) and GATE out as low as the board allows**; **power header at the side**
  (upright at the right edge, as `modules/12bit`), so the middle is not reserved for it.
- CV goes to an ADC pin with protection; user decisions S4: an op-amp buffer at Eurorack
  input impedance (MCP6002 on +5 V, so PB0 never sees more than the rail; the dual, not the single
  MCP6001, because C7377 is JLCPCB Preferred Extended: no feeder fee, user 2026-11-14) and the full
  bipolar range (±5.5 V -> 0..5 V, with headroom). The MIDI protection can be bypassed,
  **like MIDI V2** (3-pad solder jumper JP1, shipped open: 1-2 = protected/`PORT_INVEN`,
  2-3 = direct/stock firmware).
- **Three 50k pots, all into the MCU** (user stock RV09: no bushing, no nut, as
  `modules/audio-out`): P1 PA1, P2 PA2, **P3 PB5** (user, S6: the passive low-pass on
  pot 3 is removed completely; the DAC drives the output amplifier directly).
- **GATE out** (user, S6): PA7, the Bread Modular `GATE_PIN` every firmware already
  drives, through a TL074 follower and 1k, 0 / +5 V.
- **MODE button = a hand-soldered 6 x 6 mm THT tact switch, 7 mm tall** (user decision S5,
  replacing the BM SMD K2-1808SN), on the carrier F side, with a one-piece printed cap
  (press-fit on the stem, flange captive behind the panel, tip through the Ø4.2 hole).
- Bottom: **audio out** from the DAC, at Eurorack level, protected.

## Design rules kept from the repo

- BM 8bit pin map is kept (firmware ports); new inputs on pins no BM firmware
  touches (PB0 CV, PB5 knob 3). PA7 is the BM gate output and feeds the GATE jack; PB4
  (BM logger TX) stays unconnected (`docs/research.md` E1/E2/E13/E14).
- Jacks: QingPu WQP-PJ301M-12 (BM AudioJacks footprint, edited as `modules/midi`).
  Pots: BM `Potentiometer_RV09`, copper unedited, with the audio-out RV09 proxy model.
  SW1: stock KiCad `SW_PUSH_6mm_H7.3mm` (pins 6.5 x 4.5 mm, matching the user's drawing;
  7.3 mm is the closest stock model height). Everything else is stock KiCad. `hardware/8BIT.pretty/PROVENANCE.json` records every source and hash.
- All JLC-assembled SMD parts on the back (one assembly side); jacks, pots, LED,
  headers and SW1 are hand-soldered. All R/C are JLCPCB Basic except R12/R15 (0.5 W 1206
  for the ±12 V mis-patch, no Basic exists); ATtiny1616, TL074 (TL074CDR C12594, as
  `modules/12bit`), and BAT54SW are Extended, HT7550-1 and MCP6002 (C7377) Preferred Extended
  (live audit 2026-11-14).
- Power header as `modules/12bit`: J4 upright at the right board edge on B, unshrouded,
  pin 1 (-12 V) at the bottom, 16-pin IDC envelope checked (`docs/geometry.json`
  `power_header`). UPDI on a 2-pin 2.54 mm header (J5: UPDI, GND) at the right edge.
- Root rules hold: 1 mm board-edge keep-out (`min_copper_edge_clearance` 1.0, courtyards
  measured), SMD pads >= 2 mm from pot/jack pads, no vias in SMD pads.
- PWR_FLAGs: `#FLG01` GND, `#FLG04` -12V, `#FLG05` +12V at the J4 entry; `#FLG02` +12V_F,
  `#FLG03` -12V_F behind D4/D5. No others.
- Solder jumpers are copper only (stock `Open` footprints, not in BOM/CPL), so every
  net stays separate in copper; nothing needs an exclusion.

## Sources and generators

- `tools/build_schematic.py` owns `hardware/8bit.kicad_sch`, `8BIT.kicad_sym` and
  `sym-lib-table` (stock KiCad 10 symbols, flattened and pinned; the only edits are
  two footprint-filter patterns). Parts are joined by drawn wires, junctions and power
  symbols (labels only for long runs); the build asserts nothing dangles and that the
  exported netlist equals `CIRCUIT`. `kicad-cli sch upgrade --force` writes it natively. Multi-unit symbols (TL074) are
  placed per unit. `SOURCING` adds `LCSC`/`MPN`/`Manufacturer` to every assembled part.
- `tools/build_layout.py` places the THT parts from `docs/geometry.json`, parks every
  SMD part off the right board edge and takes references, values, fields, symbol links
  and pad nets **only** from the native netlist. It vendors 3D models into
  `hardware/_kicad_models/<sha256>/`, writes the **unrouted** carrier and both panels,
  and **refuses to overwrite a carrier that has tracks** (`build_layout.py panels`
  rebuilds only the panels). pcbnew assigns new item UUIDs on every run (as `modules/midi`),
  so a rerun changes the files without changing placement, nets or fields.
- `tools/import_footprints.py` rebuilds `hardware/8BIT.pretty` and `8BIT.3dshapes`.
- `tools/sexp.py` is a copy of `modules/midi/tools/sexp.py` (module-local helper).
- **The routed native PCB (R1) owns SMD placement, copper, pours and the B-silk notes.**
  It was routed by hand, divide and conquer (root `AGENTS.md`): power entry, output
  stage, MCU, MIDI, CV + UPDI, cross-board links, silk; full native DRC + parity after
  every batch. Nothing is autorouted. Changes are explicit manual edits to the board
  (back it up to `/tmp/` first, DRC reports in `research/`). The S5 4HP
  `tools/route_plan.py` is removed: it described a board that no longer exists.
- `panels/button-actuator/build_button_actuator.py` owns the cap STL/STEP and asserts
  its stack against `geometry.json`. Never hand-edit the outputs.

## Verification (S6/R1, 2026-11-14)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`); the schematic build
  asserts the exported netlist equals `CIRCUIT`.
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier **0
  violations, 0 unconnected, 0 parity**, no exclusions (`docs/fit/carrier-drc.json`);
  panel 0/0 (`docs/fit/panel-drc.json`); LFO panel 0/0 (`docs/fit/lfo-panel-drc.json`); 4HP LFO panel 0/0 (`docs/fit/lfo-4hp-panel-drc.json`).
- `kicad_tools.py check --config tools/kicad-project.json`: ERC 0, DRC 0 / 0 / 0, no
  exclusions, no ignored rules; status `no_findings_in_requested_checks`, source manifest
  (`jlcpcb/source-sha256.json`, 7 sources) present and equal after the S6/R1 export.
- Fab review + export (2026-11-14): no board change needed; native DRC on the saved fills
  (no refill) 0 / 0 / 0 for the carrier and both panels; carrier 38 parts / 24 BOM rows,
  drill and outline counts and the live assembly audit in `jlcpcb/README.md`. Audit
  `order_ready: false` by design (R12/R15 Extended R/C policy fail, empty human reviews).
- Measured on the routed board: 50 footprints placed, 258 tracks, 32 vias (0.6 / 0.3);
  no via in an SMD pad (closest via to SMD pad 0.20 mm, U3.12); every SMD pad >= 2 mm
  from pot/jack pads (closest C7.2 - J3 tip 2.245 mm); courtyards >= 1.015 mm from the
  edge (RV1); U4 (SOIC-8, MCP6002 swap 2026-11-14) 2.44 mm from the RV1 lug, its GND via 0.25 mm
  from the U4.5 pad; F GND pour one piece; B GND pour one piece plus two fragments tied by GND
  pads/tracks under U1 (2.6 mm² under the exposed pad, 0.4 mm² at C1); no zero-length,
  duplicate or dangling segments.
- Printed panel and MODE cap generators rerun for 6HP (their geometry assertions pass).
- Not done: human part reviews, JLCPCB placement preview and live recheck (order gates in
  `jlcpcb/README.md`), printed panel, cap test print, bench.
