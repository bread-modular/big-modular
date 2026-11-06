# 12bit contract (S2 schematic, P3 placement, R1 routing)

| | |
|---|---|
| KiCad project | `hardware/12bit.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/12bit-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Generators, profile | `tools/` (`build_schematic.py`, `build_layout.py`, `import_footprints.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Fabrication | `jlcpcb/` (R1 export, see `jlcpcb/README.md`) |
| Routing batches | `research/route/` (ignored: `lib.py` helpers, `b1`-`b4` batch scripts, DRC JSON, renders) |
| Evidence | `docs/fit/` (native ERC/DRC JSON, renders), `docs/12bit-schematic.pdf`, `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` |

## Fixed by the brief (user, 2026-11-06)

- modules/8bit on an **STM32G071C8T6** (two 12-bit DAC channels), new module `12bit`, **6HP**.
- **Two audio outputs** (both DAC channels), usable in different ways by the firmware.
- **No low-pass filter**: knob 3 is a plain knob read by the MCU.
- Schematic and THT placement only; **no routing** (superseded 2026-11-06: user asked to route and export).

## Changed by the user (2026-11-06, S2/P2)

- **Gate output removed** (S1 had one); the free TL074 section U4D is a grounded follower.
- Power header moved off the bottom edge to the **right edge** (upright, pin 1 at the bottom).
- OUT 1 / OUT 2 **as low as possible** (Y110.4: courtyards 1.03 mm above the bottom edge).
- Row 3 is **MODE, LED, P3** left to right on one row (P3 and MODE swapped, the LED beside
  the switch instead of below it).
- Pot rows spaced further from the jacks (P1/P2 Y40 -> Y45, row 3 Y60 -> Y69).

## Changed by the user (2026-11-06, P3)

- Row 3 (MODE, LED, P3) moved down: pot row pitch 24 -> 27 mm.
- Pot block **centred between the jack rows** on the panel: jacks Y21 / Y110.4, pots Y52.2 /
  Y79.2 (both 31.2 mm from their jack row). SWD J6 moved Y90 -> Y93 to clear the MODE legs.
- Trade-off: a power cable socket (16- or 10-pin) now overhangs the RV3 solder joints on B
  (socket 2.5 mm above B): trim the RV3 leads/lugs to <= 2 mm.

## R1 routing and export (user, 2026-11-06: "Start routing and export to JLC")

Manual divide-and-conquer routing, written to `hardware/12bit.kicad_pcb` batch by batch
(board backed up to `/tmp/` before each; `research/route/b1_out.py` .. `b4_inputs.py`):

1. **Output stage + power entry** around/below U4 between the OUT jacks: U4 rotated so pins
   1-7 face up (OUT1_AMP left, OUT2_AMP right), gain resistors above, VOFF bus under the
   SOIC body, VOFF divider between R16/R17; D2/D3/C1 in a column left of J5; +12V_F and
   -12V_F reach U4 V+/V- on F; both OUT_AMP nets hop F to R16/R17.
2. **MCU** U3 between the pot rows (rot 180 on B): VDD/VBAT joined inside the pad ring with
   a +3V3 via, VSS inner GND via; VREF+ spine C11/C10/FB1 and C12/C13 right of the MCU.
3. **MCU I/O**: SWDIO/NRST in the lane between the SW1 pads and SWCLK down the far left of J6
   (F); LED inner via -> F -> R7 -> D1; BUTTON on B round the left; POT1 over the top on F
   (C7 under RV1), POT2/POT3 on F (C9 between the RV3 lugs, C8 above RV2); DAC1 on B
   through the D1 / RV3 gap, DAC2 on F (the mirrored LQFP order needs one hop).
4. **Inputs + regulator** between the jack row and P1/P2: MIDI front end left, CV front end
   right, HT7533 (U1, C3, C4) at the right edge fed by a +12V_F F run up the right side.

Layers: F signal + GND pour, In1 solid GND, In2 solid +3V3, B parts + signal + GND pour.
Net class Power (0.4 mm) for GND, +3V3, ±12V, ±12V_F; signals 0.25 mm (0.2 mm MCU fan-out);
vias 0.3/0.6 mm. Zones thermal-relief, 0.25 mm clearance, 1 mm copper-edge rule.

## Design rules kept from the repo

- 8bit / 16bit circuits: MIDI V2 NPN front end with JP1 (copper-only solder jumper, not in
  BOM/CPL), bipolar CV level shift + MCP6001 follower, RV09 50k knobs (user stock), 8bit MODE
  switch `SW_PUSH_6mm_H7.3mm` + 3 mm LED, 0.5 W 1206 output resistors, B5819W supply diodes.
- Footprints: BM AudioJacks PJ301M-12 and BM `Potentiometer_RV09` (hats edits), stock KiCad
  for the rest; `hardware/12BIT.pretty/PROVENANCE.json` records sources and hashes.
- MCU symbol: stock `STM32G081CBTx` copied as `STM32G071C8Tx` (same STM32G0x1 LQFP-48
  pinout; edits recorded in `docs/schematic-symbols.json`).
- All JLC-assembled SMD on B; THT parts hand-soldered. LCSC/MPN/Manufacturer on every
  assembled part (`SOURCING` in `tools/build_schematic.py`), live-checked 2026-11-06.
- PWR_FLAGs only at the J5 entry (GND, ±12V) and behind D2/D3 (±12V_F).
- Root rules: 1 mm board-edge keep-out (copper rule 1.0 mm in the `.kicad_pro`; THT
  courtyards measured >= 1.02 mm), 2 mm SMD-to-pot/jack hand-solder clearance once SMD is
  placed, no vias in SMD pads, manual divide-and-conquer routing, no autorouters.

## Sources and generators

- `tools/build_schematic.py` owns `hardware/12bit.kicad_sch`, `12BIT.kicad_sym` and
  `sym-lib-table`. Parts are placed by hand (`LAYOUT`); signal nets are drawn as wires by the
  small schematic grid router copied from modules/hats; rails use power symbols. The build
  fails unless the exported native netlist equals `circuit()` and nothing is label-joined.
- `tools/build_layout.py` places from `docs/geometry.json`, takes references, values, fields
  and pad nets only from the native netlist, vendors 3D models into
  `hardware/_kicad_models/<sha256>/`, writes the **unrouted** carrier and the panel. It
  refuses to overwrite a carrier that has tracks (`--panel-only` rebuilds the panel).
- `tools/import_footprints.py` rebuilds `hardware/12BIT.pretty` and `12BIT.3dshapes`.

## Verification (S2/R1, 2026-11-06)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- `kicad_tools.py check --config tools/kicad-project.json`: ERC 0; DRC **0 violations (warnings
  included), 0 unconnected, parity 0**, no exclusions (`docs/fit/carrier-drc.json`,
  `research/check-r1/`).
- Measured after every batch (`research/route/lib.py`): no vias in SMD pads; no tracks on In1/In2;
  no zero-length/duplicate segments; each pour one piece (F, B, In1 GND, In2 +3V3); closest SMD
  pad to a pot/jack pad 2.025 mm (C7.1-RV1.2), then FB1-RV2 2.09, D3-J4 2.09; every courtyard
  >= 1.015 mm from the edge (RV1-RV3; earlier P3 figure 1.02 measured the same way rounded).
- Panel DRC 0 / 0 (`docs/fit/panel-drc.json`).
- MCU pin table checked against ST DS12232 Table 12 (LQFP48 column): 4 VBAT, 5 VREF+, 6 VDD/VDDA,
  7 VSS/VSSA, 10 PF2-NRST, 11/12 PA0/PA1, 15/16 PA4/PA5 (TT_a, DAC), 17/18 PA6/PA7, 35 PA13,
  36 PA14-BOOT0, 43/44 PB4/PB5, 46 PB7 (**FT_fa**, 5 V tolerant, USART1_RX) — matches the symbol.
- JLC export in `jlcpcb/` (not supplier-accepted).
- Not done: firmware, 3D fit, bench.
