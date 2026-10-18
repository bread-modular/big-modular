# usb-power current review (read-only)

## Pre-FAB layout pass (2026-10-18, workspace 098) — supersedes the inventory/SHA below

Current carrier PCB `f4163f66…` (PRO/schematic/panel unchanged). Edits were made only through `pcb plan/apply/promote`: 109 explicit operations (raw ops/plan/candidate in ignored `research/`). Candidate and promoted board: ERC 0; DRC 0 viol / 0 unconnected / 0 parity (refill, all severities+exclusions); exact ref/pin/net parity equal; no pad-net changes; zone outlines, drawings and design settings identical; stored fills equal a fresh refill. `jlcpcb/` regenerated with the shared exporter (manifest 0 mismatched / 0 stale; carrier PTH 246 via holes = 246 vias; BOM unchanged, CPL differs only in the five moved refs).

- 681 tracks (F.Cu 441, In1 65, In2 66, B.Cu 109), 246 vias (138x0.60, 104x0.65, 4x0.50; drill 0.30). The earlier 670 omitted the six B.Cu test-pad leads from db45d6c.
- **U3 input loop:** C7 now at (129.0,99.3) rot 270. C7.1 VPROT goes to U3.3 over about 1.9 mm of F.Cu. C7.2 NRAW goes to the existing NRAW via at (130.5,99.0). A new 1.0 mm In1 return runs from that via straight under the U3 pin column to the U3.1 via. The old VPROT detour (2 vias, In2 stubs) was removed. The loop is no longer the ~8 mm + 2 transitions traced in layout/REPORT.md, but it is still not an all-front-layer bypass and needs bench ringing measurement.
- **Vias out of small SMD pads:** U2.5 OV_SET and U2.6 EF_MODE (staggered 0.50 mm vias at the pin ends; R6 moved 0.25 mm left, its VIN9 stub re-dropped to an existing via), R72.1, R73.2, R74.2, C61.1/.2 (C61 moved 0.5 mm left), R26.2, R25.2, C36.2 (C36 moved 0.4 mm right), R17.1, R91.2, C88.1 (C88 moved 0.8 mm up; two feed vias below the pad), plus R36.1 and R82.2, where the via hole grazed the pad. The only via hole left in a 0603 or IC pin pad is R9.1 (GND; the x=136.75 edge notch and bottom edge leave no legal off-pad position), plus a 0.01 mm corner graze on U5.1.
- Bottom test pads re-checked: they are solid 2 mm B.Cu discs on their nets, with mask openings equal to the copper. The nearest foreign pour (GND at TP PRAW, RTN at TP VPROT) is 0.25–0.35 mm away under mask. No change was needed.
- Not updated: `docs/routed-baseline.json` still records the older 043 checkpoint (721/251); it was already stale before this pass.

Canonical carrier PCB `a7adc70a…` (merged routing cleanup 9442e03; this pass restored only `exclude_from_pos_files` on J7/D10) and all reviewed PCB/PRO/schematic sources are unchanged; current native checks remain 0 (ERC 0; DRC 0/0/0, refill, all severities+exclusions). Diff-read stack: inner Cu 0.0152 (0.5 oz), 7628 prepreg, HAL SnPb. Reviewed at HEAD b5c537f. Hashes: current source identity is [../../jlcpcb/source-sha256.json](../../jlcpcb/source-sha256.json) (tool-written, no drift); `raw/SOURCES.sha256` and `raw/evidence-*.txt` are the earlier receipts, left unchanged.

Independent physical-layout review: [layout/REPORT.md](layout/REPORT.md).

## Native checks
- Carrier common `check` (root+7 sheets, 63 deps): ERC 0; DRC 0 viol / 0 unconnected / 0 parity, refill, all severities+exclusions; source unchanged. `raw/carrier/`
- Panel: common check exits 2 (no SCH). Standalone kicad-cli 10.0.6 `pcb drc --severity-all --refill-zones` with panel PRO: 0/0; parity not run. `raw/panel/`
- 670 tracks (F.Cu 434, In1 64, In2 68, B.Cu 104), 249 vias (138x0.60, 109x0.65, 2x0.50 in U2 pads 5/6; drill 0.30), 90 board nets, 10 zones, 120 footprints, none on back. Merged cleanup (9442e03): `/P5` loop removed (34->22 tracks, 8->6 vias); SW1 case-tie track deleted, so the two MP case pads stay on their separate KiCad unconnected nets.

## Engineering
- U14: SW1/15/16, VIN2+EN3=VPROT, PGND11-13, EP17=GND (4 vias). Loop SW->D29 A(129.40,78.00)->K(133.40,78.00)->C78(133.57,81.10)->C78 GND(130.62,81.10)->0.5 mm->PGND13(130.55,83.00): compact.
- U3: GND1=NRAW, VIN3=VPROT, SW2->L1->GND. C7 100n ~3 mm; C89-C92 2.2u/50V VPROT-NRAW 8-19 mm.
- U12/U13 EP21=GND, 9 vias each. RTN separate net with own F/In2/B zones. In1 GND plane 2045 mm2.

## Findings
1. LOW optional: all U14 SW current exits one 0.24x0.8 mm stub (129.55,83.00->82.20)+0.45 mm; no SW zone. Widen if clearance allows, else bench SW ring/temp. Peak current not established.
2. LOW verify: C7.2->U3.1 return path not fully traced (UNKNOWN).
3. CAUTION 0.5 oz inner: NRAW U3->U13 mostly In1 1.0-1.5 mm, neck 0.75x1.8 mm at (77.8-79.6,90.5); N12 In2 1.0x13.8 mm to J7. Drop vs U13 headroom UNKNOWN; bench at max load. Thermal spreading reduced.
4. MEDIUM export: `jlcpcb/` has only README, BOM/CPL x2, export-report, B_Cu/B_Mask/B_Paste/B_Silk (tracked, not ignored). Missing front/inner/edge Gerbers, drills, ZIPs, passive-panel/, source-sha256.json. export-report cites 69a1 (stale). BOM/CPL 112 refs paired, top, LCSC complete, D10/C62/C93/J7 absent. Fix: rerun shared exporter, then DFM.
5. Mechanics consistent: native panel = SCAD = stack_geometry = mechanics.md: USB X3.3 Y28.1 W5.0 H10.8 R0.6 (datum native 50.0,30.0). Panel Y = carrier X-35.75: J1 33.5, SW1 49.5 match. L1 (mechanics.md): 9.80-0.10-(0.10+2.40+1.76)=5.44 >= 5.25+0.15=5.40. Inputs documented, not re-verified; measure web.

No PCB correction required.

## Stale docs
fabrication.md 207 vias, X3.90; mechanics.md L4 (=L5), L2/L3, 585/207/8; engineering/README/AGENTS/Code TPS65131, L2/L3, inner-1oz hold; jlcpcb/README 69a1.

## Constraints
Native SR2 governs. U14 TPS55340 boost: L5 6.8u, D29, C77-C80 22u PRAW. U3 TPS54302 inverting, IC GND=NRAW, L1 22u to GND, C7+C89-C92 VPROT-NRAW, 22u NRAW-GND bank. U12/U13 LDOs, EP=GND. JLC04161H-7628, 1/0.5 oz, HASL, tented 0.30 vias, all parts front, DNP D10/C62/C93, J7 excluded. Panel 2L Tg135 9.8x128.5; web 2.40 +0/-0.1.

## Export finding resolution
Finding 4 is resolved: the shared exporter was rerun on the unchanged sources and produced the complete carrier and panel sets (all copper/mask/legend/paste/edge layers, PTH/NPTH drills), both Gerber ZIPs, and the assembly BOM/CPL. Input and file identities are recorded in [../../jlcpcb/source-sha256.json](../../jlcpcb/source-sha256.json). The set was regenerated again from the merged board (carrier PTH 249 via holes = 249 vias, 112 refs / 44 BOM rows, manifest tool-written with 0 mismatched sources and 0 stale exports). No supplier acceptance, DFM completion or bench performance is claimed.

## Physical-layout cross-reference
Findings 2 (C7.2→U3.1 return) and 3 (inner-rail drop) were UNKNOWN in this pass. The independent layout review traced C7.2→U3.1 as approximately 8.0 mm of planar copper plus two layer transitions and screened the actual NRAW/VPROT/N12 rail segments: [layout/REPORT.md](layout/REPORT.md). Raw receipts above are unchanged.
