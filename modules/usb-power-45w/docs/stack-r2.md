# usb-power-45w R2: two stacked boards, one output header (refit + first routing)

> **Status (2026-10-31): canonical boards placed and checked; routing STARTED, not complete.**
> Top: first critical group routed (U4 negative converter power stage), 163 unconnected left.
> Base: placed, **no copper yet**, 318 unconnected. Not a manufacturing release, no fab export,
> no 45 W / 54.5 W rating, no thermal or connector-current qualification.

User direction (2026-10-31): "Refit with one IDC. Then start routing. I like this design." Two
stacked boards behind the original 4HP panel, every part on the F side of each board, one
protected 16-pin output (J2), passive expander/cable later (no powered bus).

## Files

| What | Where |
| --- | --- |
| S7 circuit (authoritative, readable hierarchy) | `hardware/usb-power-45w.kicad_sch` + 7 pages, `docs/usb-power-45w-schematic.pdf`, `docs/bom.csv` |
| Base board (native project) | `hardware/base/usb-power-45w-base.kicad_{pro,sch,pcb,dru}` |
| Top board (native project) | `hardware/top/usb-power-45w-top.kicad_{pro,sch,pcb}` |
| Shared-tool check profiles | `tools/kicad-project-base.json`, `tools/kicad-project-top.json` |
| Partition, header pin maps, stack geometry, assumed heights/tolerances | `tools/stack_r2.py` |
| Per-board schematics generator | `tools/board_schematics.py` |
| Board seed (one time) / reviewed placement moves | `tools/build_stack.py` / `tools/stack_place.py` (+ `docs/stack-r2/placement-moves.json`) |
| Manual routing batches (shared plan/apply) | `tools/route_r2.py` |
| Independent checks | `tools/check_stack.py` -> `docs/stack-r2/validation.json`, `tools/drc_summary.py` |
| Views | `docs/stack-r2/img/` (`face-base.png`, `face-top.png`, `face-top-U4-T1.png`, `assembly-rear.png`) |

The old monolithic carrier `hardware/usb-power-45w.kicad_pcb` (+ `tools/kicad-project.json`) is
**superseded** and kept unchanged as history: it still carries J3, so its DRC parity against the
S7 root now reports J3. The fit study `docs/stacked-fit-study/` stays historical.

## S7 schematic change (J3, one net name, J2 land)

- **J3 removed** from the circuit table, hierarchy, BOM and verifier (216 circuit refs). J2 keeps
  its accepted position, pin 1 = -12 V, red-stripe marking; its Note now says single output,
  one cable/contact pair per rail limits the load; use the later passive expander for more.
- U4 RT/SYNC net named `RT_U4` (was the auto name `Net-(U4-RT/SYNC)`, whose `/` is escaped
  differently by native DRC parity and the shared tool's XML parity). Same pins.
- No semiconductor/capacitor/package substitution, no current-limit or rail change.
- Checks: root ERC 0 (all severities), exact flat/hierarchy parity, `verify_design.py` passes
  (`S7_schematic_checks_not_bench_qualification`), unit tests pass (the pre-S7 history fixture
  restores J3 and the old RT net name).

## Partition and interconnect

Rule (`stack_r2.board_of`): schematic pages 02/03/04 + C5 = **top (86 refs)**; everything else =
**base (130 refs)**. Base: USB/CH224A, F1, D1, D10, U5 + C2, always-on U9 latch/RESET, monitors,
panel LEDs, SW1, J1, J2 and the **whole negative protection block** (U8/Q4/R48/R49/R89 Kelvin,
U16/U17). Top: U2/U3/U4 with input caps, BOOT, L, FB, RT, the four cans (C5 VIN bulk at the
converter side, C34/C35/C36 raw bulk), U6/U7.

Soldered 2.54 mm male headers, same pin positions on both boards (added refs XB1/XB2 base,
XT1/XT2 top):

| Header | Pins | Screen A / pin (assumed 1.5 A/pin budget, not a rating) |
| --- | --- | --- |
| XP 2x10 | 1-2 GND, 3-6 VIN, 7-8 GND, 9-12 +12V, 13-14 GND, 15-18 +5V, 19-20 N12_RAW | VIN 4.748/4 = 1.19; +12/+5 2.971/4 = 0.74; N12_RAW 1.143/2 = 0.57 |
| XL 2x3 | 1 GND, 2 MAIN_OK, 3 RUN, 4 P12_OK, 5 P5_OK, 6 V3V3 | GND 7 pins, 6 A no-cancellation screen = 0.86 |

The power header grew from the study's 2x8 to 2x10 so +12V/+5V get 4 pins each. No SW, BOOT,
FB, sense or Kelvin net crosses. GND return: the input return (top converters -> USB on base)
and the +12/+5 load returns (J2 on base -> top converters) both use the 7 GND pins and In1
planes of both boards; no cancellation is assumed.

**Per-board native schematics** are one wired flat sheet each, derived from the S7 table with the
same drawing engine; each native netlist equals the board's table share. Supplies that reach a
board only through the header carry one PWR_FLAG each (top: GND, VIN, V3V3; base: +12V, +5V,
N12_RAW), the KiCad marker for an external source (the other board), listed in
`board_schematics.HEADER_FED`. **Aggregate proof** (`check_stack.py`): base + top native netlists
joined XB1.n=XT1.n / XB2.n=XT2.n, header pins removed, equal the S7 root netlist as exact
(ref, pin) partitions, 145 nets incl. no-connects, 216 refs each on exactly one board with
identical value/footprint/fields.

## Placement refit (electrical, before copper)

Seed: the study's final variant boards. Every later change is an explicit move with its reason
(`stack_place.py`, batches 1-9); batch 4/5 positions were chosen one part at a time with the
`free` helper (nearest feasible spot to a functional target) and frozen in the source. No
automatic placement, no package change.

- **Top outline** grown into the freed J3 volume: full depth again from Y82.7 (J2 box end + 1.5)
  and the rear edge over J2 at Z28.7 (1.53 mm in front of the J2 box, plug 2.93, ribbon 5.19).
- **U2 (+12)**: turned so pins 4/5 (GND/SW) face L1, L1 vertical with its SW pad 3.4 mm below
  pin 5; BOOT C10 beside pins 5/6 (1.05 mm); input C8 1.05 mm, C7 3.29 mm; FB R8/R9 at pin 8 on
  the far side (FB pads 2.25 mm from any SW copper).
- **U3 (+5)**: rows along Y; SW pin toward the L2 SW pad and BOOT C19 above pins 5/6 (1.05 mm);
  C17 1.05 mm, C15 3.07 mm, **C16 back at U3** (5.45 mm; it was VIN-trunk in the study); FB
  R11/R12 at pin 8 on the far side (2.38 mm from SW copper).
- **U4 (-)**: C27 0.95 mm / C25 2.47 mm / C26 4.92 mm stacked under pins 3/1, BOOT C28 at pins 7/8
  (0.70 mm); **D4 clamp and C29-C33 output column next to U4/C36** (the study had D4/C31 20-25 mm
  away); support #3 moved out of the middle of that group.
- U6/U7 and their setting parts re-seated beside their converters; C34 (P12_RAW can) with D2/D5
  in the left pocket; C5 in the free rear area on the In2 VIN plane; logic header pair moved to
  the freed J3 volume (only spot free on both boards); U17/R61/R62 re-seated beside it.
- Base: J3 + its markings removed; J2 `1 / -12V / RED` text now starts at pin 1 and reads toward
  the freed side (the 11 study silk warnings are gone); U13/U14 0.65 mm toward -Y for support #2;
  test-pad row between XB1 and J2 (probe-reachable beside the top outline).

## Check results (this checkpoint)

| Gate | Base | Top |
| --- | --- | --- |
| Native ERC, all severities | 0 | 0 (root S7: 0) |
| Native DRC, all severities, schematic parity, no exclusions added | 0 violations, 0 warnings, parity 0 | 0 violations, 0 warnings, parity 0 |
| Shared `kicad_tools.py check` (profiles above) | ERC 0, DRC 0 + 318 unconnected | ERC 0, DRC 0 + 163 unconnected |
| Courtyard/copper 1 mm edge | approved J1/SW1/D8/D16-D18 overhangs only (same positions; base keeps the J1/SW1 DRU windows) | min 1.00 (R11), supports 1.004 |
| 2 mm hand-solder (SMD copper to connector THT pads/lugs) | root rule J1/J2: pass; SW1/LEDs (extra margin): pass | XT1/XT2 posts (soldered from top F): min 2.00 (D12) |
| Vias in SMD pads / tracks on In1 | 0 / 0 | 0 / 0 (22 vias) |
| Planes | not poured yet | In1 GND 1 piece; In2 VIN 1 piece + one 2.6 mm2 spoke-tied fragment between the four XT1 VIN posts |
| Thermal terminal nets | Q4 tab = -12V, U5 EP = GND | U4 EP9 = N12_RAW, U6/U7 EP = GND |

Base XB1/XB2 tails are soldered from base **B** (no parts on that face), so F-side SMD distance to
them is reported, not gated (closest R49 1.22 mm, the N12_RAW shunt next to the N12_RAW pins).

## Mechanics (nominal + documented assumptions, not a guarantee)

X across the module (panel 0..20): base B/F 2.5/4.1, gap 5.0, top B/F 9.1/10.7.

- Width: tallest top part = 8.0 mm assumed can (SamYoung MVK 6.3x8 class) -> X18.7, 1.30 nominal,
  **0.28** after the assumed linear tolerances (bracket web 0.2, boards 0.16 each, spacer 0.1,
  solder 0.1, top bow 0.3). Real can max incl. base plate, LED flange and header heights are
  prototype hardware gates (supervisor-relayed evidence pending).
- Base parts under the top board: LED flange envelope 3.9 -> 1.10 nominal, 0.44 worst.
- **Supports: one M3 through bolt each** (5 positions: Y/Z 20.5/36.7, 46.2/36.7, 89.0/36.7,
  82.0/7.3, 109.2/36.7): ISO 7380 M3x12 head under base B (k 1.65 -> X0.85), plain 5.0 mm spacer
  (OD <= 6), DIN 934 nut on top F. Grip + nut 10.6, thread exposure 1.4 nominal / 0.63 worst. No
  opposing screw tips. Tools: hex key from the open base-B side (module out of the rack); nut held
  by a thin-wall 5.5 AF socket (OD <= 8.5, top tool courtyard r4.25) or flat pliers. All-layer
  copper keep-out r1.7..3.6 on both boards. Pins are not supports.
- Header pins: plastic 2.5 on base F, 2.5 air, tail <= 1.8 below base B, post >= 0.5 above top F;
  long-pin part is provisional (see *Current hardware checkpoint*).
- Brackets, nuts, driver paths, panel vs top slab/parts: 0 collisions (model). J2 box/plug/ribbon
  vs top outline: 1.50 / 2.93 / 5.19 mm.
- Bare boards end at Z42; with the J2 plug + ribbon the envelope reaches about Z50. **42 mm is not
  claimed with the cable fitted.**

## Routing (manual, shared `pcb plan/apply`)

Rules: no autorouter, one reviewed batch at a time, F signal + local pours, In1 solid GND (no
tracks), In2 power (top: VIN), B signal + heat spreading, no vias in SMD pads. Each batch's ops
are planned and applied by the shared tool on a new candidate (shorts, clearance and XML parity
refused there); intermediate candidates still have opens, so the shared `promote` (accepted
candidates only) cannot run: the opens-only draft is written back with the board's own 3D-model
tokens and verified (all footprints identical, earlier copper kept, only the batch added), then
native DRC/parity and `check_stack.py` run again. Backups go to `/tmp/`, raw files to
`research/r2/route/`.

**T1 (done): U4 power stage** - In1 GND + In2 VIN planes; F VIN pour joining U4 pin 3 and
C27/C25/C26 with 3 vias to In2; F N12_RAW pour joining pin 1, C27/C25/C26, C36, D4 and the output
column; F GND pour joining the column, C24 and the L3 GND pad, 11 GND vias; SW pin 8 -> C28 ->
L3 (1.2 mm); BOOT pin 7 -> C28; EN_N escapes from between VIN and N12_RAW through a 0.5 mm via
and B to R18; RT -> R13; B N12_RAW pour under U4/C36/column spreading the EP thermal vias (never
GND). Widths: SW 1.2 mm, pin links 0.6 mm (pad-limited), pours elsewhere; current derating and
temperature are not qualified.

**Open (next batches):** top U4 FB/EN divider/Q1 and its N12_RAW/GND returns; U2 and U3 power
stages, U6/U7 eFuses, P12_RAW/P5_RAW output pours, +12V/+5V runs to XT1, C5; base: In1 GND +
In2 plan, USB/CH224A, F1/D1/D10/U5 input path (D10/U5 heat on base B), VIN to XB1, negative
protection Kelvin (R48/R49 -> R89 -> U8) and Q4 tab, J2 rails, latch/monitor/LED logic, XL.

## Current hardware checkpoint (selected vs provisional; no fabrication claim)

- **J2 selected:** Wurth WR-BHD 61201621621 (MPN/Manufacturer in the circuit table, native
  fields and source BOM); land `IDC-Header_2x08_P2.54mm_Vertical_Wurth_61201621621`, 1.1 mm drill
  per the Wurth recommendation, same position / pin 1 = -12 V / red-stripe marking.
  `tools/build_stack.py` re-seats it from that pinned land (pad centres asserted unchanged).
- **Board-to-board headers provisional:** Samtec TSW-110-07 (XB1/XT1, 2x10) and TSW-103-07
  (XB2/XT2, 2x3) style long posts. Dimension datums (tail/plastic/post) are from the footprint
  note, not fully qualified against the Samtec drawing; per-pin current with every pin soldered
  through both boards is **not rated** (1.5 A/pin is an assumed budget, not manufacturer proof).
- **Physical strips: 2 in total** (one 2x10, one 2x3), each soldered through both boards. XB* are
  the base lands; XT* are the same strips' second ends / top lands, not 4 physical strips.
- **BOM:** the source BOM lists the 216 circuit parts only; it excludes the new mechanical/
  interface parts (2 header strips, 5 M3 bolts/spacers/nuts). An assembly BOM is a future gate;
  no fabrication export now.
- **Opens at this checkpoint: 481** (base 318, top 163); DRC 0 / parity 0 per board, routing not
  complete.

## Hardware gates kept open (not blocking prototype routing)

Long-pin header part qualification and per-pin current, can/LED/header real maxima, bolt/spacer/nut selection,
thermal (D10 ~3.5 W screen and U5 on the base face the 5 mm gap; stacking does not guarantee a
temperature gain), startup/overload/reset/noise bench tests, Extended electrolytics and LM5067
sourcing (unchanged from S6).

## Rebuild / check

```sh
python3 -B modules/usb-power-45w/tools/build_schematic.py         # S7 root (+ hierarchy)
python3 -B modules/usb-power-45w/tools/board_schematics.py        # per-board schematics
python3 -B modules/usb-power-45w/tools/check_stack.py --scratch modules/usb-power-45w/research/r2/check
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project-top.json --reports <new-dir>
python3 -B modules/usb-power-45w/tools/render_stack.py modules/usb-power-45w/docs/stack-r2/img base top assembly
```

`build_stack.py` + `stack_place.py replay` reproduce the placement only while a board has no
copper (the seed refuses to overwrite routed boards). Routed copper is never regenerated.
