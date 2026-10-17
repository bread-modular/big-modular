# Rework verification — FAIL / NOT ACCEPTED

The latest review board is `project/usb-power.kicad_pcb` in this directory. It is a byte-identical, compact forensic copy of the actual `boost-apply-005` common-tool output, **not a completed common-tool candidate**. `NOT_ACCEPTED.json` binds every copied file to its source hash. There is no `completion.json`, no promotion to canonical hardware, and no claim that Phase 1 placement or Phase 2 routing is complete. Independent Phase 3 checks were run to quantify the remaining state; they FAIL.

## Exact authorized stale-copper deletion

Primary requested audit: **`../stale-copper.json`**. No retained copper was relabeled to KiCad's adopted nets.

- Round 1: exactly the previously recorded **42 tracks + 11 vias**, matching the UUID/old-net/native-proposal inventory exactly.
- Continuing into actual common `pcb plan/apply` exposed one additional GND via adopting NRAW when C70 was moved. Round 2 removed only that observed UUID.
- A real routing apply then exposed **42 more tracks + 7 vias** whose only native change was their net name. Round 3 removed exactly those original objects from a new branch of the immutable pre-routing source; new route objects were not among them.
- Reloading that new branch exposed **8 tracks + 2 vias** more. Round 4 removed exactly that newly observed set.
- Total authorized drift deletions: **92 tracks + 21 vias**. All UUIDs, old nets, unadopted native proposals, individual source hashes, per-round source/candidate hashes and count/SHA of untouched objects are recorded. Deletions preserve all other bytes, including footprint transforms, values, pads, UUIDs, drawings, globals and all eight zones/cached fills.
- Latest exact-deletion-only source: `../stale-copper-004/project/usb-power.kicad_pcb`. Its `pcb inspect` and `doctor` both pass. Raw/native item equality is exact, with **zero remaining net-assignment drift**. The later routing review board also has zero raw/native drift.

The first round-3 diagnostic asserted that drift should already have settled, and failed after writing its exclusively new output but before writing the stage receipt. That output was inspected (not replayed), proved byte-identical to exactly the recorded 49 removals, and its missing audit receipt was reconstructed. The fresh ten-object drift was then handled as round 4. No unrecorded or guessed deletion remains.

## Phase 1 checkpoint and actual routing work

L5 remains **(119.8,78.8), 0 degrees, F.Cu**, with its approved land unchanged. All other new-stage placements were retained. The actual reviewed common-tool operations moved only:

- C70: (118.3,88.3) -> (118.3,86.8), clearing one enlarged-L1 courtyard conflict.
- C84: (131.0,74.8) -> (131.0,75.0), correcting its measured 0.475 mm edge clearance against the unchanged 0.5 mm requirement.

Operation chain: `../rework-requests/boost-005.ops.json`, `boost-005.plan.json`, `boost-005.review.json`, `boost-005.apply.receipt.json`. The earlier route revisions are retained as rejected in-memory reviews, not accepted routes. They were refined against native copper-shape collision checks; no search/pathfinding or autorouter was used.

The final common request contains **31 explicit polylines, five ordinary 0.300 mm-drill vias, two footprint moves and 14 selected deletions**. It generated **57 segments + five vias**. The selected routing replacements are **12 old tracks + two vias**, separate from the drift-deletion audit; every UUID, inspected geometry and conflict rationale is in `boost-003.scope-review.json`, with already-drift-deleted IDs omitted from the final request. These are local affected-stage obstructions, not a full-board/net-wide rip-up. All unselected geometry remains preserved by the native item comparison.

Hand-specified partial nets:

- `/VPROT`: boost input-bank/inductor feed and local VIN/EN decoupling connections.
- `/Direct 9V positive boost/PBOOST_SW`: inductor-to-D29 trunk, widened trunk overlay and short QFN pin fanouts.
- `/Direct 9V positive boost/PBOOST_SS`.
- `/Direct 9V positive boost/PBOOST_COMP` and `PBOOST_COMP_RC`.
- `/Direct 9V positive boost/PBOOST_FB`: local divider/sense junction only; output Kelvin source remains unfinished.
- `/Direct 9V positive boost/PBOOST_FREQ` and `PBOOST_FREQ_SER`.
- `/GND`: local boost power/analog returns, with separate ground-plane access vias.

Tool/autorouter-generated paths: **none**. Common tools executed the manually specified geometry; they did not choose paths. Wide 1.0/1.2 mm switch/input trunks and short restricted QFN escapes were used. Native DRC finds **zero geometric violations involving the 62 added routing objects**, but this does not establish a complete loop, thermal/current rating or a qualified power supply.

PRAW/output Kelvin feed, the negative IBB routing, restored NRAW distribution, remaining affected power/return/feedback connections, and seven remaining L1 courtyard conflicts are NOT closed. There are still 129 retained legacy-net copper objects on nine obsolete net names. No generic signal-style full-board routing or guessed net reassignment was substituted for this work.

## Remaining common apply failure — not hidden or waived

The initial lossless-load gate is cleared. The latest actual command was:

```sh
python3 -B opt/kicad-tools/kicad_tools.py pcb apply \
  --plan modules/usb-power/research/sr2-pcb-rework-072/rework-requests/boost-005.plan.json \
  --output modules/usb-power/research/sr2-pcb-rework-072/boost-apply-005
```

It exits **2**, status **failed**:

> Native worker failed: Save/reload net table changed

Independent inspection establishes the exact difference: removing the last selected copper on `/Direct bipolar rails/BI_REF`, `/Direct bipolar rails/COMP_N` and `/Direct bipolar rails/INV_SW` causes those three now-empty legacy net names to disappear, and KiCad renumbers 97 remaining internal numeric net codes. No added net name and no pad-net membership change occurs. All native top-level items after reload match the reviewed operation result exactly after checking the common tool's recorded, byte-identical model-resource path rebindings. The audit is `../boost-apply-005/independent-reload-audit.json`.

This is not another copper net-assignment drift to delete: no remaining track/via changes net name. Deleting arbitrary surviving copper cannot repair the failed net-table invariant. The common gate was not weakened, its failure was not reclassified as acceptance, and its output was not handed off as a completed candidate. Independent read-only verification of its forensic output is not a replacement completion marker. No schematic-side ambiguity was found, and no circuit change is proposed.

## Independent Phase 3 results

Fresh full common native checks include ERC, exact native XML, all DRC severities, same-stem schematic parity, all-track errors and in-memory zone refill. No ignored checks or exclusions were added. Support sources remain immutable.

- **ERC: 0 errors / 0 warnings.**
- **Exact schematic pad/field/NC parity: PASS**, 116 electrical references, 344 distinct ref/pins, 39 explicit NCs and 1,110 schematic-owned field values. Pin roles, flags and symbol paths match. Extra board-owned fields are enumerated, not silently dropped.
- **DRC: FAIL, 290 errors / 35 warnings**, including **80 opens**.
- Errors: 82 shorts, 80 solder-mask bridges, 32 hole-clearance findings, nine clearance findings, seven courtyard overlaps, 80 unconnected findings.
- Warnings: 23 dangling tracks, one dangling via, six silk-over-copper, four text-height and one silk overlap.
- The four newly introduced reference fields remain 0.65 mm against the unchanged 0.8 mm requirement. No field-resize operation exists in the required common operation schema; hiding them or weakening text-height checks was not used as a workaround.

Before/after context:

- Original stale board: 0 errors / 143 parity warnings (not a valid synchronized board).
- This turn's input, footprint-format-002: **416 errors / 50 warnings**.
- After first 53 drift deletions: 421 errors / 39 warnings.
- Latest forensic routing review: **290 errors / 35 warnings**.

Exact finding identities versus this turn's input: **272 retained, 194 removed, 53 added**. Versus the original stale board: all 143 original parity findings removed; all 325 present findings are new identities. No totals-only or warning-baseline waiver is claimed. Full deltas are in `drc-delta.json`.

Fixed J1/J7/SW1/D10 mechanical fingerprints and poses, all four mounting holes, all 12 outline segments, front-only electrical footprints and all eight zone definitions/caches remain preserved. Model resources are byte-hashed with transforms checked; only bounded staging path tokens differ. Panel and original libraries are unchanged. **The 5.1 mm assembled L1 height envelope remains unqualified:** the frozen part note allows 5.0 mm body maximum, leaving only 0.1 mm before solder; no part substitution, land change, stack adjustment or envelope waiver was made.

**36 focused regression tests pass**, including exact per-round deletion proofs, fresh-drift evidence, zero final native item drift, immutable originals, fixed placement, and assertions that the failed apply is NOT represented as accepted. Passing tests are not DRC approval.

## Files and status

Only files under `modules/usb-power/research/sr2-pcb-rework-072/` were added/updated: narrow helper/tests, exact-deletion candidates and audits, explicit manual operation requests/reviews, common-tool forensic attempts, and this read-only verification snapshot/reports. The canonical carrier, panel, schematics, approved lands, rules, shared toolkit and historical release records remain unchanged.

No commits, fabrication/CPL/assembly exports, autorouter, rule weakening or exclusions. **Overall rework remains incomplete and NOT ACCEPTED.** No production, bench, thermal or startup qualification is claimed.
