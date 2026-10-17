# Routing checkpoint 076 — UNFINISHED / NOT FOR FABRICATION

Resume this PCB with 075's frozen dependencies. Do not use canonical hardware.
Candidate SHA-256: `2482301aa94d465a2fd8657f95d511d8167a2dde9c58943f032694273220c340`.

## Verified copper checkpoint
- Native DRC **88 errors / 18 warnings → 23 errors / 15 warnings**; **65 fewer opens**. All remaining errors are opens. Zero short, clearance, hole-clearance, mask, courtyard, edge or schematic-parity errors; no ignores/exclusions.
- Native ERC **0/0**; independent exact **116 refs / 344 pins / 39 NC / 1,110 fields** PASS. All 120 footprint objects, including four mounts, serialize identically to 075. No component moved in the retained candidate; all components remain front.
- Added **230 tracks + 56 ordinary 0.30/0.65 mm through vias**; explicitly removed seven UUIDs with reasons/before geometry in `routing-ops.json`. New via holes intersect none of the five native schematic-identified EP pads.
- Explicitly hand-routed named nets: `/Direct 9V negative IBB/{NRAW,NINV_SW,NINV_BOOT,NINV_FB,NINV_EN}`, `/Direct 9V positive boost/{PRAW,PBOOST_SW}`, `/VPROT`, `/GND`. Names in the ops are fully expanded, not inferred from numeric codes.
- Work includes both LDO local input banks; PRAW diode/output banks and LDO distribution; U3 SW/BOOT, VIN and NRAW local bulk return, partial FB/EN; U14 parallel SW fingers, output hot-loop return, output-bank Kelvin PRAW sense and partial input distribution. Existing COMP/FB/FREQ/SS circuitry is preserved. U3 local ground is NRAW, U2 EP17 is RTN, both LDO EP21s are system GND.
- Main current copper is **0.8–1.8 mm**, typically 1.2–1.5 mm, with two/three parallel barrels at principal power transitions. Short fine-pitch escapes are 0.3–0.6 mm; signal/BOOT/Kelvin fingers 0.24–0.4 mm. Parallel SW-pin fingers enter the existing wide SW trunk. This is geometry/conductance intent, **not an ampacity, loop-stability, thermal or operating qualification**; shared-feed and narrow-neck review remains required.
- Native refill is saved in the candidate; refill/save changed no semantic item geometry/settings. Original zone definitions, rules, dependencies, mechanical/UI/outline, L1=C357250 and L4/L5=C207852 remain unchanged. Canonical PCB was not promoted.

## Thermal steering: still FAIL, not an improvement claim
All **16** 075 external thermal vias remain byte-semantically unchanged. Fixed dangling U12 pin11 stub `4391ad97…` to actual corner via `40203dcf…`; recentered `1f09e0e4…` and `3babd0dc…` (actual U13 via center is **58.4,81.1**, not 58.35,81.1).

Only U12 southwest spoke `b85654d1…` could widen to **0.50 mm**. The seven other straight-diagonal 0.50 mm trials gave native **0.1207 mm** clearance against adjacent numbered pads (<0.20 required), so they retain original **0.30 mm** geometry. No rule/pad/NC edits were made.

Saved native F.GND EP-containing filled subpolygons now measure **U12 25.5923 mm² / U13 23.0394 mm²**, and still contain only **four of eight** thermal-via centers each. These areas are smaller than the supervisor's 075 figures (26.8/25.1); routing has **not** solved thermal non-regression. No ~100 mm² connected spreader, all-eight front connection, improved neck equivalence or qualified temperature claim. The two requested marginal via/pad pairs were not relocated; their original geometry remains. Next placement/copper pass must integrate stronger thermal exits/spreaders with rail routing; do not accept the ordinary-process thermal change merely because electrical DRC passes.

## Next physical bottlenecks
23 exact opens are in `after-drc.json`: NRAW long distribution through C71 to the U13 bank; U3 EN/EN_LO and remote R15 divider/C93 feedback placement; U14 C88 VIN feed and C84 return; remaining C91/92 input-bank/common supply and system-ground joins; C73; remaining +5 V converter routing. Do not claim an operable board. Main converter current loops and quiet return segregation still require final engineering review.

075's **41 older exposed-pad hole intersections**, L1 **5.40 vs 5.10 mm** mounted-height decision, explicit INNER 1 oz requirement and tighter drill/plating contract mismatches remain blockers. No via fill/cap process authorized. No fabrication export before final Opus review.

## Restore, without another dependency archive
From repo root, use a NEW output path:
```sh
python3 -B modules/usb-power/docs/routing-progress-075/materialize_resume.py \
  --output modules/usb-power/research/routing-next-076
cp modules/usb-power/docs/routing-progress-076/usb-power.kicad_pcb \
  modules/usb-power/research/routing-next-076/usb-power.kicad_pcb
sha256sum modules/usb-power/research/routing-next-076/usb-power.kicad_pcb
```
The helper initially restores 075; **replace only its PCB with this exact 076 candidate**, then verify the SHA above. RESTORE.json describes the original 075 materialization, not the replaced PCB.

Immutable closure: `../routing-progress-075/DEPENDENCIES.json` SHA `e056507eb0d7808f102186036c46688c69e8f2090e4831c2ea94ae9522b7bf6e`; `CHECKPOINT.json` SHA `f64516722696030e1a8366876a8835df461580fd33e3e04fa95c08d9f2a65ae0`. All restored dependency hashes were rechecked unchanged.

Common inspect/plan/apply ran first. Apply returned rejected with 87 opens/18 inherited warnings even under draft policy. The explicitly authorized narrow native exception then used unchanged common/native APIs, exact UUID preservation and full checks, never weakened gates. This compact docs location is the supervisor-authorized checkpoint exception. Selected docs are staged, not committed. No GUI, delegation, exports or orders.
