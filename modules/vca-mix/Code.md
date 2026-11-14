# vca-mix contract (S6 schematic, P6 8HP placement, R3 manual routing)

## Fixed by the brief

- Module name **VCA-MIX** (directory `vca-mix`, KiCad library nickname `VCA_MIX`).
- **8HP** (user direction 2026-11-14; 6HP until S5), **three channels**. Each channel has a vactrol VCA (Bread Modular V2CA)
  with three TS jacks, **QingPu WQP-PJ301M-12**: IN (audio), CV, OUT.
- **S6 (user direction 2026-11-14): a RANGE knob per channel**, the Bread Modular V2CA
  CURVE pot: RV(n+3) 50k as a rheostat (pin 1 = CCW end on RNGn, wiper and pin 3 on GND)
  with Rn14 10k across it, in series with the Rn09 330 R sense resistor. At 0 the sense is
  330 R (the punchy response), at max 330 R + 8.33k.
- The CV drives the vactrol LED through a **Bread Modular LOW/SVF vactrol driver**
  (LED inside the op amp loop, I_LED = CV x 0.331 / R_sense from 0 V, no dead zone).
- **S5 (user direction 2026-11-13): the CV runs on the modules/acid 3.3 V pipeline**;
  the audio stays on ±12 V. CV range 0..5 V: 51k / 100k divider (5 V -> 3.31 V), BAT54SW
  clamp to GND / +3V3, MCP6002 follower, 1M / 1M, MCP6002 driver, sense leg to GND,
  HT7533-1 +3V3 from +12 V.
- A volume pot per channel (Bread Modular pot: **Song Huei R0904N 50k** tall trimmer, `Potentiometer_RV09` footprint) sits **after the VCA**:
  OUT follows it (buffered wiper) and the three post-volume channels feed **MIX**.
- With no CV plugged in, the VCA is fully open, so the module is a 3-channel mixer.
- Audio inputs and CVs are buffered; OUT and MIX are driven through 1k 1 W 2512
  resistors (as modules/imix and modules/8bit).
- The hand-soldered parts follow the MIDI module: jacks and pots THT on F, the
  power header THT on B. The vactrols use the **unchanged Bread Modular VTL5C
  footprint** (wider Chinese vactrols) and mount on B as on Bread Modular. Every
  SMD part is on B for JLCPCB assembly.
- **P6 (user direction 2026-11-14): the VOL knobs stand alone in the right column**, so no
  patched cable hangs over a knob that is turned all the time. Per channel (31 mm cell): IN
  and CV jacks on the row, **OUT jack under CV**, **RANGE knob under IN** (rarely turned),
  VOL knob in the right column between the two jack rows. **MIX jack under the last RANGE
  knob** (left column, bottom). The vactrol is on B in the right column, hanging under its
  VOL pot (LDR lead pair under the pot body, body over the pot pins). Power header on B
  along the bottom edge, right of the MIX jack.
- 4-layer carrier: F signal / In1 GND / In2 +12V / B signal. Root `AGENTS.md` rules apply:
  manual routing, no vias in SMD pads, 1 mm edge keep-out, 2 mm hand-solder clearance.

## S6 / P6 / R3 state

- `tools/build_schematic.py` owns `hardware/vca-mix.kicad_sch`, `VCA_MIX.kicad_sym` and
  `sym-lib-table`. It uses stock KiCad 10 symbols, flattened and pinned
  (`docs/schematic-symbols.json`). The only symbol edits are two footprint-filter
  patterns (`Conn_02x05_Odd_Even`; `VTL5C` also names the Bread Modular footprint).
  Ten dual op amps are placed unit by unit (A, B, power unit C): per channel Un01
  (TL072: input buffer, VCA), Un02 (MCP6002: vactrol driver, CV follower), Un03
  (TL072: follower, spare); U401 (TL072) the mix. Pots: RV1-RV3 VOL, RV4-RV6 RANGE.
  `wiring()` draws every net as wires between computed pin ends (as modules/imix), and the
  build fails unless the native netlist equals `circuit()`. `kicad-cli sch upgrade --force`
  writes the file natively. Its `SOURCING` table adds `LCSC`/`MPN`/`Manufacturer` to every
  assembled part; THT parts carry none.
- The `.kicad_pro` root-sheet UUID must equal the schematic's (`uid('root')`); the
  shared `pcb plan` rejects a mismatch.
- `docs/geometry.json` owns the panel, the THT placement and the stack.
  `tools/build_layout.py` writes the **P6 base** (THT placed, every SMD part parked off the
  board, no copper) and the 8HP panel. It takes references, values, fields, symbol links
  and pad nets **only** from the native netlist, and vendors 3D models into
  `hardware/_kicad_models/<sha256>/`.
- **The native PCB owns the SMD placement and all copper** (R2, 2026-11-14, placed and
  routed by hand straight on the board; R1 was the P5 board and is gone; **R3** = R2 + the
  fab-review edits of the same day, below). `build_layout.py`
  refuses to overwrite a routed carrier; use `--panel-only` to regenerate the panel. Its
  board text `VCA-MIX P6` is renamed `VCA-MIX S6/R3` on the routed board; `-12V` is where
  the generator puts it. A schematic change goes onto the board as an explicit edit (footprint / net
  update + local re-route), not by regenerating.
- **R3 fab-review edits** (2026-11-14, `research/fab/fab_r3.py`, every coordinate by hand,
  DRC + parity after each stage): Cn05 (MCP6002 +3V3 100n) moved to Un02 pin 8 (routed
  2.2 mm, was 10.9 mm; its GND pad shares a via with Dn01 pin 1); B silk legend 1.0 mm high /
  0.15 mm stroke (vactrol notes from the library, board texts); JLC04161H-7628 stackup
  recorded in the board, zone fills saved; title block revision `S6/R3`.
- The S4 route data and copy step (`tools/route_r1.json`, `route_plan.py`,
  `promote_r1.py`) are removed: they built the old 6HP 2-layer board.
- **DRC exclusions: exactly the 15 D10 items, user-approved 2026-11-14.** The vactrol /
  VOL-pot stacking gives per channel 5 `pth_inside_courtyard` (the three pot pins inside the
  vactrol courtyard, the two LDR leads inside the pot courtyard; no silk finding).
  `tools/d10_exclusions.py` writes them into `hardware/vca-mix.kicad_pro` as per-item
  exclusions: it refuses unless the active findings are exactly those 15 pad / footprint
  pairs, refuses if any other exclusion is present, and restores the project if a marker is
  not matched. Re-run it after moving a vactrol or its pot, or after a layout rebuild (new
  UUIDs). No rule severity change, no other exclusion. The shared `check` counts excluded
  findings too (D14).
- PWR_FLAGs: `#FLG01` (GND at the Eurorack entry), `#FLG02`/`#FLG03` (+12V/-12V,
  fed only through D501/D502). No other flags (+3V3 is driven by U501's output pin).
- Local footprint edits: the jack edits are the same as MIDI's. The VTL5C keeps
  Bread Modular's pads and silk box; a courtyard (silk box + 0.25 mm) is added so DRC sees
  the body, three build-note silk lines (`SOLDER FIRST`, `TRIM FLUSH`, `LED 5mA`; D4;
  1.0 mm high, 0.15 mm stroke) sit across the body in its pad-free block between the VOL
  pot pins and the LED leads (R3; they ran along the body at 0.8 mm before), and BM's `+` /
  `-` marks are moved inside the box, beside the LED leads. All recorded in `hardware/VCA_MIX.pretty/PROVENANCE.json`.
  `tools/import_footprints.py` keeps a library file whose content is unchanged apart from
  pcbnew's fresh UUIDs, so a re-run only touches what changed.
- The FreeCAD panel is generated from the native panel PCB and asserts against
  `geometry.json`. Never hand-edit the `.step`/`.stl`/`.FCStd` files.
- `jlcpcb/` is the S6 / P6 / R3 export (2026-11-14, shared exporter; bottom Economic, 88
  parts / 17 BOM rows, the 20 THT refs by hand, 8HP panel Gerbers). The manifest covers the
  carrier PCB / project / schematic and the panel PCB / project: any change to one of them
  needs a re-export (`jlcpcb/README.md`), or the shared `check` fails on the manifest.
- Circuit intent, decisions and open checks are in `docs/research.md`.

## Verification (S6 / P6 / R3, 2026-11-14)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`). The schematic is
  unchanged from S6 (netlist assertion passed at its build).
- Native DRC `--severity-all --all-track-errors --schematic-parity` on `hardware/`
  (`docs/fit/carrier-drc.json`): **0 unconnected, parity 0**, 15 items = the D10
  stacking set, all excluded, 0 active findings. Panel DRC: 0 / 0 (`docs/fit/panel-drc.json`).
- Shared `kicad_tools.py check` after the export (`research/fab/check-post/`): ERC 0,
  0 unconnected, parity 0, DRC 15 (the same, counted although excluded), export manifest
  equal (5 sources, exports byte-identical), `order_ready` false (D14).
- Measured on the board (`research/p6/route/rt.py checks`, `research/fab/review.py`): no via in or touching an SMD
  pad (closest 0.29 mm); 0 tracks on In1 / In2; In2 +12V one piece; In1 GND one piece plus
  five spoke-tied slivers (2.6 mm² x 2 between the J10 GND pins, 1.0 mm² x 3 at the IN
  jacks); SMD pads >= 2.015 mm from every pot / jack pad (U401.4 to the OUT3 sleeve pad);
  courtyards >= 1.025 mm from the edge; copper-edge rule 1.0 mm. 467 track segments,
  82 vias; saved zone fills equal a fresh refill. The placement / routing script is
  `research/p6/route/build.py` (ignored; every coordinate hand-written, replayed batch by
  batch with DRC after each; it reproduces R2, the R3 edits are `research/fab/fab_r3.py`).
- Fab review (2026-11-14, `research/fab/review-final.txt`; `docs/research.md` section 4.2):
  routed pin-to-cap lengths, hand-solder distances, via / pad / edge distances, drill
  table, silk sizes, fills. Judged and kept for the first prototype, not waived: +12V caps
  of Un03 (9.0 mm) and U401 (8.1 mm) and the U501 input cap (7.1 mm), all through the In2
  plane; SMD pads 1.09 - 1.9 mm from the J10 and vactrol lead pads (outside the pot / jack
  rule).
- `tools/fit_assembly.sh` (nominal, P6): 0 mm³ interference for all jacks and the six
  pots against both panels, board inside the rail gap and the panel width. Vactrols are
  not modelled (D4; build notes on the footprint silk).
- LCSC codes: all 17 live-checked 2026-11-14 13:07 UTC with the shared audit
  (`research/fab/audit.json`): MPN and package match, all Economy-eligible; 14 Basic,
  C54315 and C78260 Extended, C7377 Preferred Extended (user-accepted, D7 / D16). The audit
  is not order-ready (no requirements file; `jlcpcb/README.md`).
- Not done: JLCPCB placement preview / DFM, any build. No bench, physical-fit or order
  claim; the vactrol-under-pot assembly order has not been tried on a real board.
