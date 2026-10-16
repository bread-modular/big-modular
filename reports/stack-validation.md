# A4.2 — restored SMT reset, retained 2HP and plain L brackets

**Placement-only draft. No routing, electrical reset integration or fabrication approval.**

## Delivered change

- SW1 is again **E-Switch TL3340AF160QG**, LCSC **C2886925**, using the exact
  earlier `SW_TL3340AF160QG_HandSolder` library footprint, unchanged byte-for-byte.
- Actual SW1 placement: F.Cu, unrotated, assembly locator-row centre Y91/Z4.1.
  Three signal lands, two solder anchors and two Ø0.9 NPTH locator holes.
  Pins1+3 share RESET_A_PENDING; pin2 is RESET_B_PENDING; anchors have no net.
- Reset access opening remains Ø3.2/Y91 and moves X7.2 → **X6.4** to match the
  1.7 mm actuator axis above the main-board F.Cu plane X4.7.
- Nominal body top X8.0 leaves **1.8 mm lateral space** inside the 9.8 mm panel.
  Nominal actuator tip remains Z2.05, **0.45 mm behind the panel rear**.
  These are drawing-based dimensions, not sample/tolerance qualification.
- **2HP panel, 30 mm PCB depth, USB, LED/resistor, output landing/pigtail and
  all M3 mounting geometry retained.** The two plain L brackets, their SCAD,
  dimension drawing and fasteners are unchanged. No middle PCB is reintroduced.
- The TS-1166VW and MJTP1117 library footprints are retained as retired
  alternatives, not active parts. The TS-1166VW 4.3H recommendation is historical;
  order the exact selected SMT MPN instead of choosing a generic stem height.
- Buying guide, assembly drawing, placement inventory and acceptance matrix
  now describe the restored SMT selection. LED and resistor remain through-hole.

[Assembly](../docs/assembly.pdf) · [mechanics](../docs/mechanics.md) ·
[buying guide](../docs/parts-buying-guide.md) · [unchanged plain L dimensions](../docs/m3-brackets.pdf).

## Executed checks

| Check | Result / boundary |
|---|---|
| New switch tests | **6/6 passed**, including rejection of wrong pin3 net, plated locator holes, old panel axis, undersized land and signal-connected case anchor |
| Full suite | **42/44 passed**; the same two pre-existing schematic-byte baseline failures remain, detailed below |
| Native geometry | Two outlines, ten mechanical NPTHs, five SMT switch lands, two locator NPTHs, sixteen output pins, panel alignment and both bracket/tool envelopes checked |
| Regeneration | New-output-only builder reproduces both delivered PCBs byte-for-byte; source files unchanged; existing destination rejected |
| Drawing regeneration | Assembly SVG and geometry match the contract; plain L SVG is byte-identical to the previous revision |
| Scoped preservation | Every main footprint except SW1 and every panel footprint except H6 preserved as exact native ASTs, including UUIDs and nets |
| Input preservation | Current schematics, project files, symbols, BOM, pin audit, libraries, SCAD and original preservation baselines unchanged by this task |
| Native main PCB DRC | **4 existing J1 hole-clearance errors**, **17 unconnected items**; no new geometric violation from SW1 |
| Native panel DRC | **0 violations / 0 unconnected items**; no paired electrical schematic for this mechanical panel |
| Common-tool private check | Source unchanged, order_ready=false; retains **68 ERC warnings**, 4 DRC violations, 17 opens and **115 schematic-parity findings** |
| Circuit regression | Existing verifier passes 260 connected pins, 65 independent spot checks, 20 wired/hierarchy paths + named continuation, 57 local paths and 28 gate cases |
| Visual review | Native main/panel plots and updated assembly drawing inspected; this was 2D evidence, not a fabricated/assembled 3D fit trial |

SW1 adds a third electrical pad compared with the previous two-contact THT
footprint; pin3 is the internally common contact. The unconnected count is not
hidden or waived. No routes are added to clear it. D10/R32/SW1/J7 are still
PCB-only placements and full schematic/PCB parity is intentionally incomplete.

Evidence:

- `smt-reset/geometry-check.json`: current nominal interface/bracket result.
- `smt-reset/preservation.json`: start-of-task hashes and unchanged footprint ASTs.
- `smt-reset/full-tests.txt` / `switch-tests.txt`: exact test logs.
- `stack-a4-2-native/`: raw native ERC, DRC, netlist/parity and private source hashes.
- `carrier-drc.json` / `panel-drc.json`: separate per-board native checks.
- `smt-reset/catalog-check.json`: bounded live exact-code/MPN lookup; not an order.

The common `pcb inspect` still rejects J1's retained 3D-model dependencies. The
existing narrow native candidate generator was used, with the shared private
check retained. No import/tool change, rule weakening or source-baseline reset.

## Two pre-existing test failures, preserved honestly

1. `test_deterministic_candidate_mode_preserves_all_sources`: old schematic
   generator bytes differ from the currently saved KiCad schematic files.
2. `test_original_circuit_and_usb_are_unchanged`: old historical schematic hash
   differs from the current input-protection sheet. It fails before its USB
   comparison; independent native J1 AST preservation still passes.

The same failures were recorded in `ts1166/full-tests.txt` before this task.
Current schematic/project files were snapshotted and preserved, not reverted;
those historical checks were not relaxed. Neither failure is a new switch-fit
failure, but the full suite is **not green**.

## Soldering, fit and release limits

- Five exposed SMT lands are intended for a fine-tip iron, flux and tweezers.
  A physical soldering trial and actual component-to-pad registration remain
  required. No process time/temperature qualification is claimed.
- Manufacturer no-trace region is a **Dwgs.User drawing reservation**, not an
  enforced copper rule area. Respect it during any later authorized routing.
- Exact selected-part drawing was visually reviewed for pads, pegs, internal
  pin1+3 common contact and axis dimensions; no borrowed 3D switch model.
  [source](https://configured-product-images.s3.amazonaws.com/2D/specs/TL3340AF160QG.pdf)
- LCSC public page and one strict-live common-tool lookup identify C2886925 as
  TL3340AF160QG. No stock quantity, shipping, PCBA service eligibility or purchase
  guarantee is made. DigiKey link retained; page extraction unavailable. No
  exact authenticated AliExpress seller verified.
  [source](https://www.lcsc.com/product-detail/C2886925.html)
- Bracket front-nut clearance is still only **0.125 mm nominal**. Actual ABS
  shrinkage, nut/tool/screw seating and mechanical strength need testing.
- Existing USB clearance errors, PD authorization/protection, converter
  placement/routing/thermal design, full cable envelope and working reset/LED
  integration remain unresolved. No powering or fabrication approval.

No routing, part order, fabrication upload or commit. No Bread Modular changes.
