> **Superseded (2026-11-01):** BASE routing is finished (0 opens); see [final record](/modules/usb-power-45w/docs/r3-base/final/README.md). Kept as history.

# R3 BASE manual routing checkpoint

Workspace HEAD f722d0824c673e08bf238586100c8086cd2bb39e (branch okbrain/big-modular/203-3c13e4e0).
Tools: `tools/route_base_r3.py` (apply/audit/render; shared `pcb plan/apply` + `route_r2.writeback`),
hand-written batches in `tools/route_base_r3_batches.py`. Raw reports: ignored `research/r3-base/`.

## Window 2 resume (2026-10-31)

- Board sha256 at resume: c6847a11062ef97ee3dc79028531169f4999963e8a543592f5ac2738153f1a7f
- Audit at resume: DRC violations 0, parity 0, exclusions 0, unconnected 234, tracks 154, vias 69,
  vias in SMD pad/mask 0, In1 tracks 0, zero/dup/dangling 0; planes In1 GND 1 piece, In2 V3V3 1, In2 VIN 1.
- Done in window 1: PL1-PL4 refinements, P1 planes, I1 input power, I2 CC/CH224A, U5b rear escapes.
- N1-neg-core applied: unconnected 219, DRC 0, parity 0, vias 74, tracks 183
  Board sha256 after N1: fc635ad000e79e96… — see below. Helper change: ('trk', key, at, seg) endpoint selects a
  polyline child segment (uuid5(parent, seg), same rule as shared automation child_uuid).

## Next (N2, not applied) — U8 left side + east cluster, findings from window 2
- Under-body via column x116.1 (clear of both pad rows by 0.33 mm): pin1 N_VCC via (116.1,88.3) [+F
  (116.85,88.3)->(116.85,91.2)->C43.1], pin2 N_UV via (116.1,89.15), pin3 N_OV via (116.1,90.0).
  N_GATE via (117.6,89.3) already placed. Pin 5 VEE stays F: U8.5->(113.7,90.3)->(113.7,93.0)->
  (119.175,93.0)->C43.2 (keepout MHB4 centre 117.75,96.975 r3.6: y93.0 F is 3.85 mm away), R53.2 tee
  at (113.7,92.275), R53.2->(112.95,91.52)->(111.0,91.52)->D20.1, C43.2->C44.2->R55.2 F.
- N_VCC: R51.2->F x110.35->y94.7->R50.2; B link from (116.1,88.3) west y88.3 -> via (110.35,92.0).
- N_UV: R52.2->R53.1 F diagonal; R53.1->via (114.25,93.85); B trunk (115.3,89.95..92.8) and
  y93.1 east to via (128.4,93.1) -> U16.4.
- BLOCKER to solve first: N_OV (U8.3 -> R55.1/R54.2) and N_TIMER (U8.6 -> C44.1) cannot land a via
  near R54/R55/C44 (row gaps 0.64-0.85 mm; U16.1 0.89 mm below; Q4 pins/N_SENSE strip above) without
  crossing the N_UV y93.1 trunk. Options: refine the AI-placed R54/R55/C44/R59 row (e.g. shift the row
  0.5 mm east/south) or route N_UV trunk north of U16 on F. Decide before writing N2.
- -12V (N3): F zone over Q4 tab + D14.2, B zone under tab + strip y75.0-76.6 west to J2.1/2, vias
  x127.3 y79.4..83.9, R58.2 -> via (120.35,76.3), C45.2 -> Q4.2; GND vias R58.1 (120.35,77.95),
  C45.1 (122.975,76.75).
fc635ad000e79e96c66c18f58ec806c8ebf9eaa9a9ebd3916efd4bb3c4eb0521  hardware/base/usb-power-45w-base.kicad_pcb
- N3-neg-out applied (-12V Q4 tab F/B spreading + J2 strip): unconnected 212, DRC 0 (all severities),
  parity 0, exclusions 0, vias 83, tracks 195, vias-in-SMD 0, In1 tracks 0, zero/dup/dangling 0; all
  zones one piece (In1 GND 3094.8 mm2, In2 V3V3 2533.3, In2 VIN 429.3). Board sha256 9128d4ddfa8d1754c49c479344f5ea337d5bc9b0bf4c285146a4a4f8b972211d.
  Lesson: a via with no attached same-net track is re-netted by KiCad save/reload from the stale
  In1/In2 fill -> shared "Save/reload item invariants failed"; always tie every new via with a track.
  Images: docs/r3-base/neg-kelvin-n3.png, docs/r3-base/whole-n3.png.
- R1-rails (+12V F pour with 1.8 mm neck; +5V 1.25 mm F track north of J2 + XB1 pour): 202 opens.
- G1/G1b/G2/G3 GND/V3V3 dogbones (G1b replaced a via found 0.17 mm inside C46.2): 132 opens, DRC 0,
  parity 0, vias 147, tracks 272, vias-in-SMD 0, In1 tracks 0, no zero/dup/dangling; all zones one
  piece (In1 GND 3064 mm2, In2 V3V3 2504, In2 VIN 428). sha256 8f199ffc6af2c57b…
  Still open GND/V3V3: U10.2/U11.2 GND, U11.6/U19.5/C57.1/R22.1/R86.1 V3V3 (no clear dogbone spot;
  R22.1/R86.1 sit over the In2 VIN band -> track to a V3V3 via north of y74.05).
- Routing lanes decided: E-W status signals use a B band NORTH of J2 (y63.5-67, x86-121), drop at
  x119-121 (west of it the R85/R64/C55 GND/V3V3 vias sit at x117.0) and run east at y71.4-73.6 under
  MHB3 to XB2/U18. The y72-77 band between J2 and XB1 is blocked for crossing (B -12V J2 strip
  x110.75-113 + F +5V track x112.8-114.1).
- L1 (SW1/U10/U11/U12 local, START_READY, RESET_N under U12), M1 (U18/U19/U17 monitor block),
  L2 (POR_SENSE, NEG_OFF_K, N_TIMER, -12V R82): **104 opens**, DRC violations 0 (all severities),
  parity 0, exclusions 0, vias 147, tracks 334, vias in SMD pad/mask 0, In1 tracks 0, no
  zero/dup/dangling; every zone one piece. sha256 03467e0d82075f39f1583b268bc48492952f3319ac467f33a8c27b706c4f0e45.
  Full open list: docs/r3-base/open-w2.txt (raw DRC docs/r3-base/drc-w2.json).
  Images: docs/r3-base/whole-w2.png, neg-kelvin-w2.png, input-heat-w2.png.

## Open technical items (need a decision, not routing effort)
- SW1 MP case pads (net unconnected-(SW1-CASE-PadMP)), X102.60/X106.90 Y101.325: any track must start
  at the pad centre, 0.95 mm from the Y102.275 edge, so copper-edge 1.0 mm fails for the track (the
  .dru 0.55 mm window covers only the pads). Options: user-approved extra .dru window for that net's
  track, or accept the ratsnest. Not changed (no rule edits without approval).
- U8 escape (N_VCC/N_UV/N_OV/N_OUT_PIN/N_PGD + R90.1 -12V): over-constrained as placed. Concrete
  findings: only one 0.2 mm track fits between U8 pins 6-10 and Q4.1 (used by N_SENSE_PIN); under-body
  via columns x116.1 (pins 1-3) and x117.6 (GATE 89.3) leave no slot for OUT/PGD; B lanes for UV
  (south-west + east trunk), OV (east y90.0), VCC (west y88.3), -12V to R90.1 and OUT to D20 cross.
  Recommended: refine the AI-placed R90/D20 (OUT clamp + bias) next to Q4/D14 on the -12V side and
  move C43 to the U8 pin1/pin5 side, then route OUT east on B; or ask the user.
- V1-vin (XB1.5 -> B x102.6 -> R51.1/R50.1; uses the B column between the U12 and U11 vias):
  **102 opens**, DRC 0, parity 0, exclusions 0, vias 148, tracks 341, vias in SMD 0, In1 tracks 0.
  sha256 133cfeb5d1d6a16bf9e1dce3ac44aac4a987c7cad3f2439c04230707332a6add. open-w2.txt/drc-w2.json refreshed. Window 2 ends here (handoff).
  Next order: U8 escape decision (see above) -> N12_RAW/VEE cluster + -12V to R90.1 -> long status
  lanes via the north B band (P12_OK, P5_OK, N12_OK, V20_OK, RUN, MAIN_OK, ARMED, TIMER_GO, MON_20,
  NOT_RUN, MAIN_LED_OK, BAD_FILTERED, ANY_BAD, NOT_FAULT, FAULT_CLK, FAULT_LATCH) -> LED cathode/anode
  links to D8/D16/D17/D18 (panel row, y97.9) -> VPD feed to U9/R83 -> leftovers (TP4, U10.2/U11.2 GND,
  U11.6/U19.5/C57.1/R22.1/R86.1 V3V3, +12V R75.1, +5V R77.1).

## Window 3 (2026-10-31)
- Resume sha256 133cfeb5d1d6… (= V1-vin), audit unchanged (102 opens, DRC 0, parity 0).
- Support keep-out repair: imported EXACT copies of tools/{build_stack.py,check_support_copper.py,
  fix_support_keepouts.py,test_support_keepout.py} from main 4eb072f5 (`git show 4eb072f5:<path>`),
  ran `tools/fix_support_keepouts.py base` once (backup /tmp/usb-power-45w-base-pre-support-keepout-133cfeb5d1d6.kicad_pcb):
  5 seamed MHB1-5 annuli -> 20 overlapping sectors; footprints/tracks/copper zones unchanged.
  check_support_copper.py base --refill: before 10 problems (In1/In2 fills entering r1.85 at all 5
  supports, 5242-5244 uncovered grid points each) -> after 0 problems, nearest copper r3.601.
  sha256 after cadc63542dc31d5e2702195e8a534ff5004615cfb3b95e565b20cfc4751ced54; audit: DRC 0, parity 0, 102 opens.

## Window 4 (2026-10-31)
- Resume sha256 cadc6354… (support keep-out repair already in; 4 imported files = exact 4eb072f5 blobs,
  re-verified by sha256 of `git show 4eb072f5:<path>`), audit 102 opens, DRC 0, parity 0.
- S1-sw1-mp (user-approved inward off-centre termination, no rule change): shared `pcb plan` endpoints
  are only pad centre / via / track branch, so this ONE connection is an explicit native edit: F.Cu
  0.2 mm segment (103.4,101.125)->(106.1,101.125), uuid daf88504-a5f8-501a-af6e-8a0a3e105267, net
  unconnected-(SW1-CASE-PadMP). Both ends 0.15 mm inside the MP pads (X101.65-103.55 / 105.95-107.85,
  Y100.975-101.675); outer track edge Y101.225 -> 1.05 mm to Edge.Cuts Y102.275; 0.40 mm to the SW1
  NPTH pegs (bottom Y100.625). Audit: 101 opens, DRC 0, parity 0, no dangling.
