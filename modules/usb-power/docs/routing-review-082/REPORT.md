# Independent Opus delta review 082 — PCB 081 (NOT RELEASED)

Checked PCB `4e4f19a16956be529fd3b08f75de34ff992bf712747fe9da94c303b5080a77db`; PRO `122b817b…529de9` (frozen, identical before/after); candidate-profile `0fefa34a…1506`; 075 DEPENDENCIES/CHECKPOINT hashes match. Restored with the 075 materializer into NEW ignored `research/review-082-actual`, replaced ONLY the PCB; 53 non-PCB closure files byte-identical. Read-only: pcbnew `LoadBoard` only, no SaveBoard, no hardware edits. Scope: the five 081 corrections only; corrected U14 map (SW 1/15/16, PGND 11–13, EP17 /GND @129.8,84.4).

## Native (COMMON check, staged local libraries)

`kicad_tools.py check --config <new>/candidate-profile.json --only both`: ERC 0 (incl. exclusions); DRC refill/all-track/parity 0 violations / 0 unconnected / 0 parity; `source_unchanged: true`; ref/pin/net parity equal. Shared `netlist inspect`: **116 refs / 344 pins / 39 singleton NC nets / 1,110 non-system fields** (89 nets). Count-level identity reproduced; field-UUID identity carried from 081 `exact-parity.json`, not re-audited. Placement delta vs 078: only D29, R88, C84, C78, R90; mounts identical; all footprints front.

## Correction verdicts

1. **Hot loop — PASS (source).** D29.2 SW (129.4,78) / D29.1 PRAW (133.4,78): boost polarity correct. C78.1 PRAW (133.575,81.1), C78.2 GND (130.625,81.1). Actual F.Cu vertices U14.15→(129.55,82.2)→(129.2,81.85)→(129.2,79.2)→D29.2; D29.1→C78.1 1.2 mm; C78.2→(130.55,82.0)→U14.13 0.5 mm (+0.8 mm to U14.12). Independent shoelace over those vertices: **15.42875 mm² / 18.1196 mm** (7.95 mm are component/chip closures), **0 vias**. <10 mm² not met (aspiration only). Non-blocking note: all SW current leaves through one 0.24 × ~0.5 mm neck at U14.15 (U14.16 by 0.24 mm bridge, U14.1 by ~3.5 mm 0.24 loop); width = lead width, ~1 mΩ; optional future widening. Ringing/thermal: UNKNOWN pending bench.
2. **R86 sense — PASS.** 0.8 mm F landing C78.1→via (133.575,82.2), shared with B.Cu 1.5/1.0 distribution; In2 0.25 mm to (134.3,83.2), then F to R86.1. Shared landing+barrel drop estimated ≲ few mV/A (<0.05 % of rail): acceptable Kelvin-like, not four-wire. 41/41 In1 samples and quiet-UUID preservation not resampled here (081 claim; native clean).
3. **Dogbones — PASS.** U3.5 via (131.95,96.64) NINV_EN 0.30/0.60, no pad hit; hole-edge 0.398 / annulus 0.248 mm to U3.5 and U3.2 (NINV_SW, DRC clean) — 081's 0.351 not reproduced (actual larger). U5.2 via (105.95,95.15) FIVE_SW 0.30/0.60, hole 0.100 mm from own pad/mask aperture (tented by board setting; marginal, disclosed). Nets unchanged.
4. **EP vias — PASS.** Four /GND 0.30/0.60 at x129.4/130.2, y84.0/84.8, each fully (64 samples) in In1 island `43e392e3` 2,045.478 mm². U12.21/U13.21 EP via-in-pad counts 9/9 unchanged vs 078 (external 8 not recounted). Ordinary unfilled/uncapped prototype contract; no fill/cap/PCBA claim.
5. **Holes — PASS.** EF_MODE (79.25,87.475)/OV_SET (79.85,86.825) 0.490569→**0.584590 mm**; board different-net minimum **0.553302 mm** (/GND 125.7,85.2 – /VPROT 126.55,85.275), above old minimum; DRC clean.

## Hard defect HD-1 (new, undisclosed; DRC has no via-in-pad rule)

C78.2 `/GND` pad (130.625,81.1; 1.15×1.8; F.Cu/Mask/Paste) now contains pre-existing 078 GND via `8e4785b7` at **(130.9,81.8)**, 0.30/0.65 F→B (hole y81.65–81.95 vs pad edge 82.0) because C78 moved onto it. Open unfilled hole in a pasted 1210 Cout pad: solder wicking/void/tilt risk — the same class correction 3 removed, and contrary to 081's “only U14 EP intersections” disclosure. **Feasible fix:** move via to (131.65,81.8) (existing F 0.8/0.6 GND junction; hole outside all pads; nearest foreign copper 0.478 mm In2 VPROT); keep F 0.6 to pad, remove redundant B.Cu 1.5 mm stub; refill + full COMMON check + via-in-pad audit (hole-to-hole for new spot not computed — DRC must confirm). Not in the selected hot loop; area unchanged.

## Verdict

**Canonical source promotion: FAIL** (HD-1 only). All five corrections verified. After HD-1 fix and clean rerun, no other source blocker found in this delta scope. Unchanged release holds: L1 5.40 vs 5.10 mm user decision; JLC inner-1-oz/plating/drill-tolerance/unfilled-in-pad PCBA acceptance; void/thermal/EMI/startup/load/EP-joint bench qualification. NOT RELEASED.

Receipts: `receipts/` (native summary/ERC/DRC, geometry JSON, read-only scripts, review-receipt.json).
