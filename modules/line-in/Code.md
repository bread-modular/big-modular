# line-in contract (S2 schematic, P3 placement, R1 routing)

## Fixed by the brief

- Stereo line input module for Eurorack, from Bread Modular `line_in`, improved for
  ±12 V (user, 2026-10-28). This round: schematic with wired nets, THT placement and
  panels only; routing comes later (manual divide and conquer, root `AGENTS.md`).
- Input: one stereo TRS jack, **QingPu WQP-PJ366ST** (tip L, ring R, sleeve GND), as BM.
- LEVEL L / LEVEL R: **RV09 50k linear** (user stock, BM value) on the Bread Modular
  `Potentiometer_RV09` footprint; pin 3 = jack, pin 1 = GND, wiper = level.
- Outputs: OUT L, OUT R, MONO on **QingPu WQP-PJ301M-12** (TN unconnected).
- Power: unshrouded 2x5 header J10, 10-pin cable, B5819W per rail, as audio-out;
  **horizontal along the bottom edge** (user, 2026-10-28; as hats), pin 1 (-12 V) left.
- 4HP, one centred column (audio-out rail holes, board outline, jack rotation).
  **IN on top, then the pots, outputs as low as possible** (user, 2026-10-28): IN Y19.0,
  LEVEL L Y36.5, LEVEL R Y58.0 (21.5 mm pitch), OUT L Y78.5, OUT R Y92.5, MONO Y106.5
  (14 mm pitch).
- Gain **~x20** like Doepfer A-119 (user, 2026-10-28; LEVEL sets the level): 5.1k into
  100k || 20p = -19.6, ~80 kHz roll-off.
- OUT L / OUT R keep Bread Modular's inverting gain stage (user, 2026-10-28: no
  re-inversion stage); L stays L and R stays R.

## S2/P3 state

- `tools/build_schematic.py` owns `hardware/line-in.kicad_sch`, `LineIn.kicad_sym` and
  `sym-lib-table` (modules/imix generator: stock KiCad 10 symbols flattened and
  pinned, wires + junctions, one label per signal net, stock power symbols). The
  build fails unless the native netlist equals `circuit()`. `SOURCING` adds
  `LCSC`/`MPN`/`Manufacturer` to every SMD part (reused codes; re-audit before export).
- PWR_FLAGs: `#FLG01` GND, `#FLG02` +12V, `#FLG03` -12V (rails fed only through D1/D2).
- `tools/import_footprints.py` builds `hardware/LineIn.pretty` with audio-out's edits.
- `docs/geometry.json` owns placement and the panel; `tools/build_layout.py` places
  the THT parts, parks every SMD part on B off the right edge, and takes refs,
  values, fields and pad nets only from the native netlist.
- `min_copper_edge_clearance` = 1.0 mm in the `.kicad_pro`.

## Verification (S2/P3)

- Native ERC `--severity-all`: 0.
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier 0 violations,
  parity 0, 80 unconnected (unrouted); panel 0/0/0.
- Shared `doctor` passes; shared `check`: ERC 0, DRC 0, parity 0, 80 unconnected.
- THT courtyards to Edge.Cuts >= 1.50 mm (J10), 1.67 mm (jacks); IDC10 envelope clear of
  THT pads (asserted by the layout build).
- (P3 state; R1 and the export below supersede this.)

## R1 routing (manual divide and conquer, 2026-10-28)

- Native board owns the copper. Batches were scripted with pcbnew in the ignored
  `research/route/route_r1.py` (applied to the P3 board, then written to
  `hardware/line-in.kicad_pcb` after each batch with full DRC + parity).
- Layers: 2-layer, all SMD on B. F.Cu: -12V lane X1.85, +12V lane X18.15 (0.4 mm), IN_L
  (J1 T -> RV1.3), IN_R (X16.9 -> RV2.3; B under IN_L at the top), GAIN_L X11.25 (RV2
  pin 2/3 gap, J2 gap), GAIN_R X12.6 -> X10.2 (J2/J3 gaps) to R8, LVL_L/LVL_R wiper
  feeds. GND pours on F and B (thermal, 0.3 mm), islands removed. Signals 0.25 mm,
  rails 0.4 mm, header 0.5 mm, vias 0.6/0.3.
- Groups (SMD pads >= 2 mm from every pot/jack pad):
  - power entry between OUT R and MONO: D2/C2 left, C1/D1 right, J10 pairs tied,
    -12V_IN / +12V_IN up the B edges; R12 (MONO) and R8 (OUT_R) beside them.
  - U3 mono sum between OUT L and OUT R (rot 90): R10 + C8 left, R7/R9/R11/C13/C7 right;
    SUM joins pin 2 under the body.
  - U2 (LEVEL R -> OUT L) and U1 (between the pots, same layout 21.2 mm up): C(V-),
    C(in), R(1M) left; R(5.1k), C(20p), R(100k) right; C(V+) under the body; BUF over
    pin 5; GAIN_L leaves through a via under U1's body.
- Verification R1: native DRC `--severity-all --schematic-parity --refill-zones` 0 / 0
  unconnected / 0 parity; shared `check` no findings; no vias in SMD pads; closest
  SMD-to-pot/jack pad 2.17 mm (R4-RV2.3); courtyards to edge >= 1.08 mm (D1/D2); no tracks
  on In layers (2-layer). Pours: one main piece per side; F has 4 spoke-tied slivers
  between J10 pins, B one 50 mm2 piece under J10 tied by its GND pins.
- Decoupling: C3/C5 sit under their op-amp; C7 is ~6 mm from U3 pin 8 (fed by the
  +12V F lane), C4/C6/C8 within ~3 mm.

## Export (2026-10-28)

- Shared `export.py` (carrier `--side bottom --require-part-numbers`, panel
  `--pcb-only`) into `jlcpcb/`, one `source-sha256.json`; shared `check` passes with
  the manifest equal. Live strict audit (5 boards): all Basic + Economy except
  R7/R8/R12 ROHM ESR18 (Extended; Basic 1206 1k is 0.25 W, below the ~0.36 W
  output mis-patch fault). Review attestations left open. See `jlcpcb/README.md`.
