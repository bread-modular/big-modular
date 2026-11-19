# 12bit contract (S3 schematic, P3 placement, R3 2-layer routing)

| | |
|---|---|
| KiCad project | `hardware/12bit.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/12bit-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Generators, profile | `tools/` (`build_schematic.py`, `build_layout.py`, `import_footprints.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Fabrication | `jlcpcb/` (**S3 / R3 export, 2026-11-19**: 48 parts / 25 rows, bottom Economic; see `jlcpcb/README.md`. The S2 / R2 export of the first board is in git history) |
| Routing batches | `research/route/` (R1, ignored: `b1`-`b4`), `research/route2l/` (R2, ignored: `lib.py` one-connection finder + checks, `b1_top.py`, `b2_islands.py`, `drc.sh`, DRC JSON), `research/route-s3/` (R3, ignored: `lib.py` edits + checks, `b1_sync.py` .. `b4_sense.py`, `verify.py`, `check.sh`) |
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

R1 layers: F signal + GND pour, In1 solid GND, In2 solid +3V3, B parts + signal + GND pour (superseded by R2).
Net class Power (0.4 mm) for GND, +3V3, ±12V, ±12V_F; signals 0.25 mm (0.2 mm MCU fan-out);
vias 0.3/0.6 mm. Zones thermal-relief, 0.25 mm clearance, 1 mm copper-edge rule.

## R2: 2 layers (user, 2026-11-07: "Start a 2 layer board")

Cost: the 4-layer price drove the 12bit board cost (every 110 mm carrier misses JLCPCB's 102 mm
special price). R1 had no tracks on In1/In2, so its F/B copper and placement stay; the In1 GND
and In2 +3V3 zones were deleted and the stack-up set to F / B. Board backed up to `/tmp/` before
each batch; `research/route2l/` (one-connection finder, every path checked before writing):

1. **+3V3 top + right**: U1 out via -> F to R5, D5, R1, R3 vias (0.4 mm); F to the C6 via, then
   B down the right of C8 to RV2.3; F column RV2.3 - FB1 via - C13 via - RV3.3 (x 124.55..125.1,
   between +12V_F and the RV3 lug).
2. **+3V3 islands**: MCU VDD via -> F -> new via (119.45, 113.1) -> B -> RV2.3; RV1.3 -> F
   past the RV1 lug -> R3 via; J6.1 -> B -> via -> F (Y137.92) -> via -> B -> RV3.3; R14 (VOFF
   divider) -> F -> via -> B up the left past J6 -> J6.1. Four new vias, all clear of SMD pads.

Layers: F signal + GND pour, B parts + signal + GND pour, tied by the R1 GND vias (26). 271
tracks (F 83, B 188), 63 vias (0.3/0.6 mm). Pours: B one piece; F one piece plus a 25 mm²
strip between the +12V_F run and the +3V3 column (Y113.6..135.8), tied to B by four GND vias
(not an island). Net classes, widths and zone settings as R1.

## S3 / R3: +3V0 reference rail (user, 2026-11-19: "Add the hardware fix too")

The first board buzzed at the outputs whenever the MCU load changed at an audio rate (the knob ADC
scan, `firmware/README.md` humtest): the DAC reference was the MCU's own +3V3 rail through a ferrite.
S3 gives the analog side its own rail. Not built, not measured: the numbers are datasheet values.

- **U5 LM4040B30FTA** (3.000 V +/-0.2 % shunt, SOT-23, C460604, Extended; pin 1 cathode, 2 anode, 3 open,
  read from the Diodes datasheet figure) fed from +12V_F by **R18 2.2k** (4.0 mA) makes **+3V0**.
  It supplies VREF+ (through FB1, C10 / C11 as before), the three knobs, the VOFF divider R14, the CV
  level shift R5 with its buffer U2 / C6 / D5 and the MIDI pull-ups R1 / R3: <= 1.6 mA.
  +12V_F ripple reaches it divided by R18 / Zr = 2200 / 0.4 R (about -75 dB).
- **U1 HT7533-1 +3V3 now only feeds the MCU** (U3 pins 4 / 6, C12, C13, C4) and the J6.1 sense pin.
  DS12232: VREF+ must be 2 V .. VDDA; +3V0 is 3.006 V at most, +3V3 3.2 V at least (HT7533-1 -3 %).
  At power-up +3V0 follows +3V3 (R18 x 1.2 uF = 2.6 ms); R18 limits a fault current into VREF+ to ~5 mA.
- Values for the 3.0 V reference, so the firmware and the levels stay as S2: **R10 / R12 27k** (x3.7),
  **R15 22k** (VOFF 2.0625 V, zero error -19 mV) -> buffered DAC 0.2 .. 2.8 V = -4.83 .. +4.79 V;
  **R5 51k, R6 100k** -> CV -5.9 .. +6.0 V, 0 V = code 2028 (S2 2021), 344.7 codes / V (S2 342.9).
- PB7 (MIDI) idles at 3.0 V (VIH 0.7 x VDD = 2.4 V at most). PA0 never exceeds VREF+ (U2 runs on +3V0).
- PWR_FLAG #FLG06 on +3V0 at the reference (as +12V_F / -12V_F behind their diodes).
- The DAC output buffers still run on VDD/VDDA (DS12232 PSRR typ -80 dB, worst -28 dB). `humtest` step 7
  (buffers off) on the first board, user 2026-11-19: hum still there, a bit duller, so the buffers' supply is not
  the path; it rides on the +3V3 the reference and VOFF hang on, which S3 moves to +3V0. Heard, not measured;
  S3 itself is not built.

R3 is R2 with these local edits, by hand in four batches (board backed up to `/tmp/` before each):

1. `b1_sync.py`: netlist sync (values, fields, pad nets), U5 / R18 added, U1 / C3 / C4 moved; the old
   +3V3 tree (52 tracks / vias) renamed +3V0; its MCU branch, the C13 tap, the old U1 stubs and the J6.1
   taps removed (19 tracks, 3 vias).
2. `b2_island.py`: **U1 (126.0, 122.4), C3, C4 on B right of the MCU**, between the P2 pins and the P3 lug;
   +12V_F tap = a via on the F trunk's diagonal (122.75, 122.95) (on the straight run it was 0.175 mm
   from the POT2 track); U1 out -> C13 -> C4 and -> C12 -> U3 on B; two new GND vias.
3. `b3_reference.py`: **U5 and R18 where U1 was**: old +12V_F via -> R18 -> U5 cathode -> the tree's top via.
4. `b4_sense.py`: the tree passes J6.1 by on B; **J6.1 = +3V3** on its own 0.25 mm sense line: C12 link -> B
   between the CV_ADC via and C3 -> via (119.6, 126.2) -> F between the RV3 lug and the POT3 track, above
   the F link -> via (107.8, 136.95) -> B -> J6.1. (At x 107.45 that via cut the F pour in two.)

291 tracks (F 85, B 206), 65 vias (0.3 / 0.6 mm), 49 SMD on B. Pours: B one piece, F one piece plus the
R2 25 mm2 stitched strip.

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
- PWR_FLAGs only at the J5 entry (GND, ±12V), behind D2/D3 (±12V_F) and at the U5 reference (+3V0, S3).
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

## Verification (S3/R3, 2026-11-19; R2 figures 2026-11-07, R1 2026-11-06)

- **S3 / R3 (2026-11-19)**: schematic build netlist assert passes (60 components, 37 named nets); native ERC
  `--severity-all` 0; shared `check` ERC 0, DRC **0 violations (warnings included), 0 unconnected, parity 0**,
  no exclusions (`docs/fit/`, `research/check-s3/b4b`; source manifest equal since the S3 / R3 export,
  `research/check-s3-export-after/`). `research/route-s3/verify.py`: ref / pin / net / value / field / symbol-link parity against the
  native netlist, no findings; no vias in or within 0.05 mm of an SMD pad; closest SMD pad to a pot / jack
  pad still C7.1 - RV1.2 2.027 mm (new parts: C3 3.47 mm, U1 3.78 mm to the RV3 lug); courtyards >= 1.02 mm
  from the edge (C4 1.025 mm with its line); no zero-length / duplicate segments; only F / B copper.
- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- `kicad_tools.py check --config tools/kicad-project.json`: ERC 0; DRC **0 violations (warnings
  included), 0 unconnected, parity 0**, no exclusions (`docs/fit/carrier-drc.json`,
  `research/check-r1/`; R2 `research/check-r2b/`, manifest equal).
- Measured after every batch (`research/route/lib.py`): no vias in SMD pads; no zero-length/duplicate
  segments; R1 pours one piece each (F, B, In1, In2); R2 B pour one piece, F one + a stitched strip; closest SMD
  pad to a pot/jack pad 2.025 mm (C7.1-RV1.2), then FB1-RV2 2.09, D3-J4 2.09; every courtyard
  >= 1.015 mm from the edge (RV1-RV3; earlier P3 figure 1.02 measured the same way rounded).
- Panel DRC 0 / 0 (`docs/fit/panel-drc.json`).
- MCU pin table checked against ST DS12232 Table 12 (LQFP48 column): 4 VBAT, 5 VREF+, 6 VDD/VDDA,
  7 VSS/VSSA, 10 PF2-NRST, 11/12 PA0/PA1, 15/16 PA4/PA5 (TT_a, DAC), 17/18 PA6/PA7, 35 PA13,
  36 PA14-BOOT0, 43/44 PB4/PB5, 46 PB7 (**FT_fa**, 5 V tolerant, USART1_RX) — matches the symbol.
- **S3 / R3 JLC export in `jlcpcb/` (2026-11-19, user: "Do the JLCPCB export")**: shared exporter, 2 layers, bottom
  Economic, 48 parts / 25 rows (S2 / R2: 46 / 24; + U5, R18), panel Gerbers unchanged apart from the plot date; shared
  `check` manifest equal; BOM = CPL = the 48 SMD on B, drills and pad regions checked against the board
  (`jlcpcb/README.md`). All 25 codes live-checked (`research/jlc-audit-s3/`): Economic-eligible, 6 Extended part
  types (LM4040 new); **STM32G071C8T6 listed stock 965** (4,969 on 2026-11-06). Printed panel script re-run, STL
  identical. Not supplier-accepted, no JLCPCB preview, not built, not measured.
- Firmware (`firmware/README.md`, 2026-11-18): `clapsnare` synthesized clap + snare drum voice (MIDI, CV in on TONE, JP1 p/d builds;
  `p` flashed on the first board, host-tested, hits checked over SWD, not heard and not tested with a MIDI source)
  and `osc3` three-oscillator mixer (user-confirmed working). First board: JP1 = P (PB7 idles low).
  First-board finding (2026-11-18, `humtest` bench firmware, heard by the user): a software ADC scan in 1 kHz bursts
  is a buzz at the outputs. Firmware rule: start the knob ADC from the sample timer (TIM6 TRGO, one scan per sample,
  DMA), no ADC bursts at an audio rate. Done in clapsnare (user: almost gone, a faint rest), osc3 still to do.
  2026-11-19: clapsnare scans only while the drum sounds or a take is recorded (a note-on starts the scan, reads the
  knobs in 0.33 ms, then fires), so the ADC is idle between hits; user: "pretty good now". The MODE LED no longer
  flashes on a note (recorder only; flashed). `humtest` step 7 (DAC buffers off) flashed by the user 2026-11-19: hum still
  there, a bit duller = reference path, the one S3 fixes. A 20 ms start-up wait for the S3 reference is compiled,
  not flashed by the assistant.
- Not done: 3D fit, bench.
