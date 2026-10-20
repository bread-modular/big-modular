# 8bit contract (S5 schematic, R4 routed carrier)

| | |
|---|---|
| KiCad project | `hardware/8bit.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/8bit-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Button cap | `panels/button-actuator/` (FreeCAD generator, one-piece cap STL/STEP) |
| Generators, copper, profile | `tools/` (`build_schematic.py`, `build_layout.py`, `import_footprints.py`, `route_plan.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md`; JP1 guide `docs/jumpers.md` |
| Evidence | `docs/fit/` (native ERC/DRC JSON, renders), `docs/8bit-schematic.pdf`, `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` |
| Fabrication export | `jlcpcb/` (shared exporter, bottom-side assembly; `jlcpcb/README.md`) |

## Fixed by the brief

- Based on Bread Modular `8bit` (ATtiny1616, DAC audio), as a Eurorack module, **4HP**.
- Top: **MIDI in** and **CV in**. CV goes to an ADC pin with protection; user decisions
  S4: an op-amp buffer at Eurorack input impedance (MCP6001 on +5 V, so PB0 never sees
  more than the rail) and the full bipolar range (±5.5 V -> 0..5 V, with headroom).
  The MIDI protection can be bypassed, **like MIDI V2** (3-pad solder jumper JP1,
  shipped open: 1-2 = protected/`PORT_INVEN`, 2-3 = direct/stock firmware).
- Three pots, **50k (P1/P2) and 1M (P3) only** (user stock RV09: no bushing, no nut,
  as `modules/audio-out`). **Pot 3 = passive low-pass filter only** (DAC -> R7 -> RV3
  rheostat -> C13, as Bread Modular; user decision S3: no ADC option, no jumpers).
- **MODE button = a hand-soldered 6 x 6 mm THT tact switch, 7 mm tall** (user decision S5,
  replacing the BM SMD K2-1808SN), on the carrier F side, with a one-piece printed cap
  (press-fit on the stem, flange captive behind the panel, tip through the Ø4.2 hole).
- Bottom: **audio out** from the DAC, at Eurorack level, protected.

## Design rules kept from the repo

- BM 8bit pin map is kept (firmware ports); new inputs on pins no BM firmware
  touches (PB0 CV). PA7 and PB4 stay unconnected (`docs/research.md` E1/E2).
- Jacks: QingPu WQP-PJ301M-12 (BM AudioJacks footprint, edited as `modules/midi`).
  Pots: BM `Potentiometer_RV09`, copper unedited, with the audio-out RV09 proxy model.
  SW1: stock KiCad `SW_PUSH_6mm_H7.3mm` (pins 6.5 x 4.5 mm, matching the user's drawing;
  7.3 mm is the closest stock model height). Everything else is stock KiCad. `hardware/8BIT.pretty/PROVENANCE.json` records every source and hash.
- All JLC-assembled SMD parts on the back (one assembly side); jacks, pots, LED,
  headers and SW1 are hand-soldered. All R/C and the TL072 are JLCPCB Basic
  except R12 (0.5 W 1206 for the ±12 V mis-patch, no Basic exists); ATtiny1616, HT7550-1,
  BAT54SW and MCP6001 are Extended.
- Power header and IDC-16 envelope identical to `modules/midi` (J4 vertical, pin 1
  -12 V at the bottom, unshrouded). UPDI on a 2-pin 2.54 mm header (J5: UPDI, GND).
- PWR_FLAGs: `#FLG01` GND, `#FLG04` -12V, `#FLG05` +12V at the J4 entry; `#FLG02` +12V_F,
  `#FLG03` -12V_F behind D4/D5. No others.
- Solder jumpers are copper only (stock `Open` footprints, not in BOM/CPL), so every
  net stays separate in copper; nothing needs an exclusion.

## Sources and generators

- `tools/build_schematic.py` owns `hardware/8bit.kicad_sch`, `8BIT.kicad_sym` and
  `sym-lib-table` (stock KiCad 10 symbols, flattened and pinned; the only edits are
  two footprint-filter patterns). Parts are joined by drawn wires, junctions and power
  symbols (labels only for long runs); the build asserts nothing dangles and that the
  exported netlist equals `CIRCUIT`. `kicad-cli sch upgrade --force` writes it natively. Multi-unit symbols (TL072) are
  placed per unit. `SOURCING` adds `LCSC`/`MPN`/`Manufacturer` to every assembled part.
- `tools/build_layout.py` places from `docs/geometry.json` and takes references,
  values, fields, symbol links and pad nets **only** from the native netlist. It
  vendors 3D models into `hardware/_kicad_models/<sha256>/`, writes the **unrouted**
  carrier and the panel. pcbnew assigns new item UUIDs on every run (as `modules/midi`),
  so a rerun changes the files without changing placement, nets or fields.
- `tools/import_footprints.py` rebuilds `hardware/8BIT.pretty` and `8BIT.3dshapes`.
- `tools/sexp.py` is a copy of `modules/midi/tools/sexp.py` (module-local helper).
- Pad UUIDs are deterministic (`pad_uuid` in `build_layout.py`): `route_plan.py` names
  SW1's duplicated pad 1 (BUTTON pair) by UUID, as the shared `pcb apply` requires.
- **The routed native PCB (R4) owns copper.** `tools/route_plan.py` holds every track,
  via and both GND pours (thermal reliefs) as shared `pcb plan` ops v1, applied by
  plan -> apply (new candidate under `research/`) -> promote. Don't rerun
  `build_layout.py` over the routed board except as the full README rebuild. Route
  changes are explicit edits to `route_plan.py`; nothing is autorouted.
- `panels/button-actuator/build_button_actuator.py` owns the cap STL/STEP and asserts
  its stack against `geometry.json`. Never hand-edit the outputs.

## Verification (S5/R4, 2026-10-20)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier **0
  violations, 0 unconnected, 0 parity** (`docs/fit/carrier-drc.json`); panel 0/0
  (`docs/fit/panel-drc.json`).
- Shared `pcb apply` accepted the R4 candidate (ERC/DRC empty, parity equal, source
  unchanged); `pcb promote` re-bound every model token (0 external).
- `kicad_tools.py check --config tools/kicad-project.json`:
  `no_findings_in_requested_checks`, no exclusions, no ignored rules; source
  manifest `jlcpcb/source-sha256.json` present and equal.
- Live strict JLCPCB lookups of every LCSC code: `docs/sourcing-candidates.json`
  (2026-10-19; SW1 is user-bought, no lookup).
- Export (2026-10-20, S5/R4): 37 parts / 24 BOM rows, bottom side; BOM unchanged from
  2026-10-19, CPL moves R10/R11/C14. Live strict audit (2026-10-19, not rerun): all
  codes resolved and Economy-eligible; R12 (0.5 W) passes its 0.28 W fault power and
  fails only the R/C Basic policy (intentional Extended); human reviews empty, so
  `order_ready: false`.
- Not done: 3D fit, printed panel, cap test print, bench.
