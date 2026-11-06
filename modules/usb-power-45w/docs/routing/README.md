# R1 routing — 10-pin outputs and manual routing

**ROUTING CLOSED, NOT FABRICATION-READY.** **0 unconnected** (ERC 0 / DRC 0 / warnings 0 / parity 0) after the 2026-11-04 continuation
([continuation-238.md](continuation-238.md): input power path, USB-PD group, U2/U4 cells, logic blocks, test points on B
with silkscreen labels, north monitor matrix re-placed, BAD filter group U15/R72/C51 moved; B210 hand-built ordered corridor lanes closed P12_OK and V20_OK, B211–B213
closed RUN Q10→U13, −12V R99→rail and TIMER_GO; B214 −12V R82→rail by the one approved In2 hop; B215 RUN→Q14 on the approved bottom lane
(B y 101.05, Q14 rotated 180° in place); B216 MAIN_LED_OK→Q15 on a new B row y 98.6 under U13/SW1/C52 (R64 moved 0.5 mm, local via moves).
B217 closed the last open, VPD→R112.1/Q1.2, with the user-approved In2 hop (C80.2 GND via moved; In2 V3V3/VIN one piece each);
B218 moved C54 beside U15.5 (bypass 1.77 mm). B219–B222 cleared the cheap `check_s8_board.py` items with 0 unconnected throughout:
R115 −0.5 mm (R115↔Q14 4.71 mm), TP28/TP29 on F in the AGND island pocket and TP20 beside TP24 (all anchors and both pairs pass),
RA_U2_CELL grown to a superset of S9.2 round the settled cell (TP23 may touch), D27 +0.1 mm (D27.2→R9.1 3.99 mm); placement/
contract records refreshed. `tools/check_s8_board.py` still FAIL: U12.14→C52.1 7.63 mm, D25↔D24 9.04 mm, the TP22/TP23 pair
8.25 mm, R116.1 inside RA_AGND_ISLAND (each needs routed copper ripped or a part moved, user decision) plus the post-routing
copper/thermal items (min_widths 59); see the Open section).
Earlier record: [continuation.md](continuation.md) (356 unconnected).

Open `hardware/usb-power-45w.kicad_pro`.
The previous `docs/design/review-s93.json` is historical evidence for the pre-routing S9.3/P2.3 files,
not a current release certificate. `checkpoint.json` is refreshed to the B223 board (hashes, 0 unconnected, check_s8
result); the narrative evidence is `continuation-238.md`, the native reports in ignored `research/routing/final-b223/native/`
and `research/routing/final-b223/check_s8.json`. The 356-open batch table and text below are historical (earlier session). The raw `research/` reports stayed in the routing workspace (git-ignored) and are not in this tree.

## Connector change

- J2 and J3 are now **Wurth 61201021621 shrouded 10-pin headers**, 1.1 mm drills, using a new pinned local footprint.
- Original pin-1 positions, rotations, red-stripe orientation, references, schematic UUIDs and PCB identities are retained.
- Pins **1/2 = -12V; 3–8 = GND; 9/10 = +12V**. The twelve unused contacts formerly numbered 11–16 were removed.
- Native XML comparison proves **every remaining ref/pin/net is identical** to the incoming S9.3 design: 185 references,
  84 functional nets. No converter, startup, protection or current-rating change was made.
- The 10-pin body is 20.36 mm long versus 27.98 mm for the previous part: **7.62 mm reclaimed per header**.
  The footprint includes the matching generic 2x5 KiCad 3D proxy; it is not a manufacturer-specific fit proof.
- Schematic/library, circuit generator, native BOM, PDF, pin verifier, mechanical envelopes and rear silk agree.
  Six obsolete B.SilkS `NC` labels were removed. The two mated-plug guide rectangles were shortened too.

Manufacturer drawing: https://www.we-online.com/components/products/datasheet/61201021621.pdf

The 3M D89110 **dimensional reference only** is 17.3 x 6.1 mm; the conservative guide uses 17.6 x 6.2 mm.
Cable/plug selection, mated-height tolerance, strain-relief fit and contact heating remain open. This does not authorize
parallel supplies or increase the module rating. Keep the two-header rule for the 2.4 A +12V prototype load.

Plug drawing: https://multimedia.3m.com/mws/media/485893O/3m-tm-idc-ribbon-cable-socket-ts2243.pdf

## Placement changes

Native KiCad coordinates in mm; all six parts remain on F.Cu. No test pad, panel part, inductor, converter or thermal
field moved. The board outline and mounting holes are unchanged.

| Ref | Old x, y, rotation | New x, y, rotation | Reason |
| --- | --- | --- | --- |
| C34 | 102.70, 68.45, 0° | 90.90, 60.80, 90° | Use reclaimed J2 space |
| D2 | 108.65, 68.45, 0° | 94.00, 61.30, 90° | Use reclaimed J2 space; local polarity clamp |
| C59 | 133.60, 68.45, 0° | 124.00, 61.00, 90° | Use reclaimed J3 space |
| D27 | 108.65, 87.10, 0° | 108.60, 68.40, 0° | Bring +12V soft-start injection beside its divider |
| C84 | 106.90, 89.70, 0° | 105.00, 67.50, 0° | Beside D27, in the strip released by C34/D2 |
| R116 | 103.80, 89.70, 0° | 101.90, 67.50, 0° | Same soft-start group |

D27.2 to R9.1 is now **3.73 mm straight-line** rather than 15.34 mm; this is not a claim that the sensitive FB route is
finished. U2 sense escape and the U4 soft-start pocket still need a deliberate placement/routing pass.

Placement checks: no courtyard overlaps; no new edge or bracket violations; minimum non-panel courtyard-to-edge
1.279 mm. Minimum SMD-to-hand-solder-pad clearance remains 2.010 mm (D8–Q6); J2 is 3.364 mm and J3 is 4.289 mm.
The inherited, explicitly approved J1/SW1/D8 panel overhangs are unchanged. All 27 test pads are preserved.

## Manual routing batches

| Batch | Added | Native ERC | DRC violations / parity | Unconnected |
| --- | --- | --- | --- | --- |
| Incoming S9.3 | Existing thermal fields only | 0 | 0 / 0 | 411 |
| 10-pin conversion and six-part placement | No routing yet | 0 | 0 / 0 | 411 |
| 03 | In1 GND plane | 0 | 0 / 0 | 394 |
| 04 | B.Cu output buses and paired rail contacts | 0 | 0 / 0 | 388 |
| 05 | C34/C36/C59, D2 and six adjacent GND vias | 0 | 0 / 0 | 380 |
| 10 | USB CC1/CC2, 0.25 mm F/B routes | 0 | 0 / 0 | 378 |
| 11 | U5 ground, DVDT and OV controls | 0 | 0 / 0 | 370 |
| 12 | U5 UV and trim chain | 0 | 0 / 0 | 366 |
| 13 | U5 ILIM/IMON controls and TP7 | 0 | 0 / 0 | 360 |
| 14 | MAIN_OK to R63, RUN to Q10, Q10 GND | 0 | 0 / 0 | **356** |

- In1 GND is **one filled island**, about 4208 mm²; no tracks on In1.
- +12V header bus and local power links: **1.5 mm**. -12V header bus and C36 branch: **0.8 mm**.
- Layer changes in the rail buses use the actual THT header contacts, not a single small power via.
- D2 has three GND vias; C34/C59/C36 each have one. Every added via is 0.3 mm drill / 0.6 mm copper,
  tented and clear of pads/mask openings. All original thermal fields remain intact.
- Initial batches added **25 segments, six vias and one plane**. The continuation adds **86 segments and 16 vias**.
  Current board total: **137 segments, 48 vias, four copper zones**, 15 unchanged rule areas. No zero-length or duplicate segments.
- Header buses and these local parts are connected **to each other**, not yet to the converters.
  **356 connections remain unrouted.** No autorouter, exclusions, reduced clearance or rule waiver was used.

The full post-routing thermal/copper gate correctly reports **FAIL**, not PASS. In particular, the existing J2 THT
antipads intrude into the contract's 15 mm U2 no-slot area (largest hole 2.201 mm), even though the plane is one piece.
Resolve that with the U2-cell placement before routing the converter; do not waive the plane rule. Other outstanding
items include Kelvin routing, U2/D10/R109/U4 thermal copper and the D1/D24/D25/D26 clamp connections. Per-class width/
pour-neck enforcement from the S9.3 review is also still open; the first output tracks were explicitly sized above.

Remaining work is converter/USB-input/logic routing, critical placement, full current-path/thermal/pour-neck validation,
and the existing hardware acceptance tests. Soft-start compensation/damping proposals require a separate circuit
decision; they were not silently added here. Old assembly renders remain historical; these are the current native views:

![Current placement and F.Cu](face-front.png)

![Initial output routing, F red and B blue](outputs-FB.png)

## Verification and continuation

**Validation:** the initial 81-test checkpoint is retained in `research/routing/07-all-tests.log`. The continuation adds three regression tests; the current full-suite result is in `checkpoint.json` and `research/routing/16-all-tests.log`. Native full ERC is clean; DRC has only the **356** documented routing opens. The separate finished-routing thermal/copper gate still fails, as it must for this draft.

Shared checks and raw logs are in ignored `research/routing/`. Each batch was backed up under `/tmp/usb234-*` before
writing the workspace board. Completed placement was independently screened and rendered before routing.
The common PCB plan/apply produced an opens-only draft; its promote command refuses drafts. The six reviewed transforms
were therefore applied with native pcbnew, as required by the repository's direct-board manual routing policy. No tool
guard was changed, no relocated model bindings were copied back, and native checks were rerun afterward.

The standard shared check still reports connectivity findings for this draft; that is expected and not suppressed:

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/usb-power-45w/tools/kicad-project.json \
  --reports modules/usb-power-45w/research/<new-check-dir>
python3 -B modules/usb-power-45w/tools/check_s8_board.py
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
```

The placement regression checks the placement/pre-routing invariants and explicitly requires the incomplete final
copper gate to remain FAIL. Dedicated R1 tests check exact 10-pin geometry/polarity, layer-aware header/local-part
connectivity, preserved thermal-via policy, minimum routed rail widths and the one-piece GND plane. The continuation also checks CC/main-protection connectivity and removal of a CC segment as a negative control. The old negative
controls for unused header pins are replaced by **extra-contact insertion must fail** controls, not removed coverage.

No fabrication export, order, commit, merge or push was made.
