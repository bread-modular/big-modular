> **Superseded (2026-11-01):** BASE routing is finished (0 opens); see [final record](/modules/usb-power-45w/docs/r3-base/final/README.md). Kept as history.

# BASE R3 routing handoff (fresh-context completion)

Status: **unfinished WIP, not release, not merge approval.** BASE only; TOP in this branch is the
old 163-open copy and is NOT this worker's (TOP finished on main 562cb165 / 4eb072f5).

## Saved state (verified at handoff, 2026-10-31)
- Workspace base HEAD f722d082; WIP commit message "Preserve base routing WIP for fresh-context completion; unfinished, not release".
- Board `hardware/base/usb-power-45w-base.kicad_pcb` sha256 7e8b980d1cb9d981c226427ed9c60f0bd61a6381dddb4920cab3e566b34c1aa0.
- Native check: `kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --format json`
  (refill NOT saved) -> violations 0 (all severities), exclusions 0, parity 0, **101 unconnected**.
  Raw: docs/r3-base/drc-handoff.json; list: docs/r3-base/open-handoff.txt.
- Copper: 342 segments, 168 vias (incl. footprint-free), vias in SMD pad/mask 0, In1 tracks 0, zones
  one piece at last audit (In1 GND, In2 V3V3 + In2 VIN island). Re-audit after first new batch.

## Saved batches (see checkpoint.md for per-batch hashes/details)
P1 USB/CC/shield, PD (CH224A), main power F1/D1/D10/U5 -> VIN -> XB1; N-core (-12V pour -> R49/R48 ->
1.5 mm strip -> Q4 source; Kelvin U8 sense tracks taken at the resistor pads); protected -12V (Q4 tab F
+ 7 vias + B spread, 1.6 mm B strip to J2.1/2, R58/C45, R82->D14); R1 rails (+12V F pour 1.8 mm neck,
+5V 1.25 mm F track north of J2 + XB1 pour); G1-G3 GND/V3V3 dogbones; L1/M1/L2 local logic; V1-vin
(XB1.5 -> R51/R50); support keep-out repair; S1 SW1 MP link.

## Support keep-out patch: DONE
4 files imported as EXACT blobs of main 4eb072f5 (git blob ids equal at handoff):
build_stack.py 62713fc8, check_support_copper.py d6f2de0c, fix_support_keepouts.py 24129fc0,
test_support_keepout.py c617716e. fix_support_keepouts.py base ran once (5 seamed annuli -> 20
sectors), check_support_copper.py base --refill -> 0 problems, nearest copper r3.601. Do NOT re-run;
re-run check_support_copper.py base --refill before final. Never run build_stack seed.

## SW1 MP: DONE (user-approved inward off-centre termination, no rule change)
F.Cu 0.2 mm (103.4,101.125)->(106.1,101.125), uuid daf88504-a5f8-501a-af6e-8a0a3e105267; ends 0.15 mm
inside MP pads; outer edge Y101.225 -> 1.05 mm to Edge.Cuts; native DRC confirms case net closed.

## Part positions (R90/D20/C43 move is AUTHORIZED but NOT yet applied)
- R90: HEAD at (115.3 91.95), now at (115.3 91.95)
- D20: HEAD at (111.95 89.5 90), now at (111.95 89.5 90)
- C43: HEAD at (118.4 91.95), now at (118.4 91.95)
- U8: HEAD at (116.95 89.3), now at (116.95 89.3)
- Q4: HEAD at (123.75 83.45 90), now at (123.75 83.45 90)

## U8 obstacle (exact) and planned-not-applied fix
U8 LM5067 escapes N_VCC, N_UV, N_OV, N_OUT_PIN, N_PGD plus -12V to R90.1 cross each other: only one
0.2 mm track fits between U8 pins 6-10 and Q4.1 (taken by N_SENSE_PIN); under-body via columns x116.1
(pins 1-3) and x117.6 (GATE, y89.3) leave no slot for OUT/PGD; B lanes for UV (south-west + east trunk),
OV (east y90.0), VCC (west y88.3), -12V->R90.1 and OUT->D20 cross.
Plan (authorized, no human question needed): move R90/D20 (OUT clamp + bias) beside Q4/D14 on the -12V
side; move C43 beside U8 pins 1/5; then route OUT east on B, then VCC/UV/OV/PGD one at a time, then
the N12_RAW cluster (7 opens) and -12V->R90.1. Keep values/nets/pads/F side/edge 1 mm/courtyards/
Kelvin rules; record exact moves. No draft for this was saved to the board.

## Remaining (101) by net
/RUN 9, N12_RAW 7, V3V3 5, P12_OK/P5_OK/V20_OK/LED_RETURN 4 each, VPD/N12_OK/N_VCC/N_UV/N_OUT_PIN/
REF_GOOD 3 each, 2 each: BAD_RC GND MAIN_OK RESET_N N_OV MAIN_LED_OK FAULT_LATCH NEG_OFF_LED ARMED
MON_20 START_SENSE; 1 each: D8/D16/D17/D18 A/K nets, POR_SENSE POR_SER -12V +12V(R75.1) +5V(R77.1)
VIN N_PGD BAD_FILTERED ANY_BAD NOT_RUN N12_STATUS START_READY NOT_FAULT FAULT_CLK TIMER_GO START_CT.
Order: U8 group -> long status lanes on the B band NORTH of J2 (y63.5-67, x86-121, drop x119-121, east
y71.4-73.6 under MHB3 to XB2/U18; the y72-77 J2-XB1 gap is blocked by the B -12V strip + F +5V track)
-> LED links D8/D16/D17/D18 (y97.9) -> VPD to U9/R83 -> leftovers (TP4, U10.2/U11.2 GND,
U11.6/U19.5/C57.1/R22.1/R86.1 V3V3; R22.1/R86.1 over In2 VIN -> V3V3 via north of y74.05).

## Authorizations already given (no re-asking)
Normal refinement of AI-placed unrouted SMD and localized rip-up of this worker's own copper, with
recorded reason + mechanical checks. Fixed: panel, outline, support holes, J1, SW1, LEDs, J2, header
posts. No autorouter/bulk routing, no vias in SMD pads, no In1 tracks, no waivers/exclusions/rule edits.
Lesson: tie every new via with a same-net track before save (else KiCad re-nets it from stale fills).
