# Opus independent PCB review 080 (CORRECTED) — routing-progress-078, NOT RELEASED

Supersedes the first 080 report in full. Hardware read-only; no PCB/schematic/rule/exclusion/test edits, no fab exports.

## Withdrawn (unsupported or wrong)
- "Fresh 0/0" from my first raw `kicad-cli` run: that run (cwd library resolution) returned **238 ERC 'BigModular' library warnings, exit 5**; `set -e` stopped DRC. Not evidence.
- Old B1/B2/B3: used U14 **pad 15** (SW) as the EP and a fictional PGND net. Real U14 = TPS55340RTER WQFN-16, **EP17 = /GND @129.80,84.40**, SW = pins 1/15/16.
- Graph `noTrackPath` loop areas, `audit.json` island results (all `None`), old "U3 input C71 VPROT–NRAW" (C71 is NRAW–GND), old rule values.

## Independently re-run (this round)
- Target `research/review-080-opus/usb-power.kicad_pcb` = 078 SHA `23e57358…0735e`; `.kicad_pro` `122b817b…29de9` **identical before/after**; 075 `DEPENDENCIES.json` `e056507e…`, `CHECKPOINT.json` `f6451672…`, `candidate-profile.json` `0fefa34a…` match (`receipts/hash-*.txt`, `common-check-sha256.txt`).
- Common check: `kicad_tools.py check --config candidate-profile.json --reports <NEW> --only both` (privately staged lib tables). RC 0, `source_unchanged: true`.

## Verdicts
| Area | Verdict | Evidence |
|---|---|---|
| Native ERC/DRC/parity | **PASS** | ERC 0 (8 sheets), DRC 0 viol/0 unconnected/0 parity, refill+all-severity; `ignored_checks` [] both; no `ignore` severities. Ref/pin/net parity equal; netlist 116 comps, 344 nodes, 39 unconnected-* nets. |
| 1,110 fields, fixed J1/J7/SW1/D10/mounts/outline | **NOT re-verified** | Handoff receipt only. |
| U12/U13 EP thermal geometry | **PASS (geometry only)** | Each EP: 9 in-pad 0.30/0.60 GND vias, all **solid** in F local GND (U12 9a875a8a 25.6 mm², U13 3a4e0ea3 23.0 mm²), In1 GND 43e392e3 (single island 2042 mm²) and B GND. External 0.30/0.65 within 3.5 mm: U12 4, U13 6 (2 F-spoke). In1 GND shrank 2295→2042 mm² vs SR2 baseline (new In1 routing), still one island. Thermal performance NOT qualified. |
| U14 boost | **CONDITIONAL — R1/R2** | See below. |
| U3 inverting (GND pin=NRAW) | **PASS, bench items** | C9 NRAW–GND output cap 2.5 mm F to U3.1. HF input cap C7 (VPROT–NRAW) loop 6.4 mm² but via In2/B + In1 0.40 mm (1be680b5/8fc7c006). FB divider R10/R84/R15/R9 local. |
| U5 +5 buck | **PASS** | C18 input loop ≈5 mm² all F, no vias; SW F 0.5→0.85 mm to L4. |
| LDO feeds / NRAW neck | **PASS** | In1 0.75×1.8 mm neck da5bd72f ≈1.2 mΩ (1 oz) → ~0.35 mV @300 mA. U12 IN escapes 0.25–0.30 × ≤1.6 mm. |
| Assembly | **CONDITIONAL — R3** | 30 UUID-new / 22 removed vias touching SMD pads vs SR2 (edge-touch method; cannot confirm "17"). Center-in on SOT-23-6 leads U3.5 NINV_EN, U5.2 FIVE_SW (106.86,95.15). |
| Fabrication | **CONDITIONAL** | Project min annular 0.10, hole 0.30, hole-hole 0.25 (min diff-net gap measured 0.491). Vias 0.30/0.60–0.65 exceed JLC Q&A preferred 0.2/+0.15. 20 vs 18 µm plating, drill tolerance, inner 1 oz need explicit service acceptance. Unfilled in-pad PCBA acceptance UNKNOWN; tenting does not seal EP holes; fabrication.md prototype allowance stands. DeepSeek fill/cap 0.15–0.55 claim not re-verified. |
| L1 mechanics | **BLOCKS RELEASE** | 5.40 vs 5.10 mm unresolved, not waived. |
| Release | **NOT RELEASED / not JLC-ready** | Service + mechanical gates open. |

## U14 measured from actual geometry (`u14geo.txt`, `geo2.txt`, `loops_explicit.txt`)
- All U14 ground pins (5,6,10–14,17) are one /GND net (pinfunctions PGND_11–13, AGND_6, EP_AGND_17): no PGND/AGND split exists in schematic.
- **EP17 has 0 vias — identical in SR2 baseline (not a regression).** EP ties only by 0.24 mm F tracks to pins 6/14; U14 reaches In1 only via 3 GND vias at 130.20,81.60 / 130.90,81.80 / 131.65,81.80 (2.8–3.2 mm).
- **Hot loop** SW→D29 (128.00,80.45→76.45)→F→vias 126.60,75.1–76.7→B 1.8 mm e7387e67→vias 132.50→F→C78.1 (133.53,76.60); C78.2→vias 136.4–137.2,77.9–78.5→B 1.5 mm→vias 130.2–131.65,81.8→U14.13. Explicit polygon ≈**42.9 mm², 30.6 mm**, 4 via-group transitions. C84 (131.00,75.00) sits in the direct F path. SR2 had no PRAW routing, so no baseline comparison.
- FB: R86 senses PRAW at C78.1 via In1 0.25 mm 31bbfd34/fcc10d1c (x≈134.3, y 77.9–84.0) — Kelvin-like, but it slots In1 GND between C78 and U14 return vias (5/41 samples outside fill). Comp/FB returns (R87, C86, C87) via 132.00,90.00, separate from power vias: good.

## Focused corrections for Astra (layout only, no part/value/stack change)
- **R1** Shrink boost diode→Cout→PGND loop: one PRAW 22 µF (C78/C77) on F adjacent D29 cathode with GND pad next to U14 pins 11–13 (relocate C84 as needed); add GND vias beside U14 11–13 and C78.2.
- **R2** Move R86 PRAW sense trace off In1 (In2/F) to restore In1 return.
- **R3** Dogbone the center-in-pad vias on U3.5 and U5.2.
- Optional R4: U14 EP vias (same accepted 0.30/0.60 pattern); otherwise bench thermal.

Bench-only after fixes: SW ringing/EMI, U14/U12/U13 temperature at SR2 loads (+400/−300 mA, +5 @250 mA planning), startup, EP X-ray.

## Promotion
- **Routing promotion: FAIL (hold) pending focused R1–R3.** Native connectivity is clean and no hard electrical blocker was verified, but R1 (U14 hot loop ≈42.9 mm², 4 via-group transitions) is PCB-resolvable now and not fixable on the bench.
- If the user explicitly accepts R1 as a bench risk, promotion as NOT RELEASED prototype is not electrically unsafe.
- Release holds, separate from routing: L1 5.40 vs 5.10 mm; service acceptance (plating, drill tolerance, inner 1 oz, unfilled in-pad PCBA); bench thermal/EMI/startup qualification.
- UNKNOWN (not measured): 1,110-field parity, the handoff's "17 new routing vias in SMD" count, U12/U13/U14 thermal performance.

Receipts: `receipts/`. Private renders: `research/review-080-opus/_render/` (ignored).
