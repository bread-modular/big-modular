# SR2 routing checkpoint — UNFINISHED / NOT FOR FABRICATION

This is **preservation only**, for review/merge and continuation in a fresh Astra chat.
No routing, KiCad checks, electrical/thermal investigation, schematic edits, rule/test
edits, canonical promotion, commit or fabrication export was performed while packaging.
All results below are copied from existing evidence, not newly verified engineering.
The user has authorized fresh-chat continuation, including **LDO thermal vias and
JLCPCB compatibility**; neither is implemented or qualified by this checkpoint.

## Resume this board, not the stale canonical hardware

- Preserved board: `usb-power.kicad_pcb` beside this handoff; exactly one PCB is packaged.
- Original candidate: `modules/usb-power/research/sr2-pcb-rework-072/phase3-review-001/project/usb-power.kicad_pcb`.
- SHA-256: `41b64b62a841ce69ab29f291d10b50ff81d3e4d0d79d38117aa7444aec40afce`.
- It is the existing most advanced routing review board: a byte-identical copy of
  `boost-apply-005` output. Common apply **failed**, so this is NOT an accepted
  completion, fabrication handoff or promotion. `evidence/NOT_ACCEPTED.json` retains
  the original source-copy proof. No `completion.json` is present or implied.
- Original carrier/panel and approved libraries remain untouched. Do not redo sync
  or replay already-applied requests. `PROVENANCE.json` maps every copied artifact
  to its original path/hash. Paths inside old receipts are historical, not portable
  instructions. The only large JSON delta was whitespace-compacted without losing data.

## Latest ACTUAL state (existing Phase 3 records)

- Native DRC: **290 errors / 35 warnings**, including **80 opens, 82 shorts,
  80 solder-mask bridges, 32 hole-clearance errors, 9 clearance errors and
  7 courtyard overlaps**. Warnings: 23 dangling tracks, 1 dangling via,
  6 silk-over-copper, 4 text-height, 1 silk overlap.
- ERC: **0 errors / 0 warnings**. Exact ref/pin/net/NC/field parity previously PASS:
  **116 refs, 344 pins, 39 explicit NCs, 1,110 schematic-owned fields**.
- Original stale board's 0 errors / 143 parity warnings were NOT a valid synchronized
  baseline. Prior turn input was 416 errors / 50 warnings. Latest delta against that
  input: 272 retained, 194 removed, 53 added finding identities. A lower warning
  total does not waive newly introduced warnings.
- Existing receipt: 36 focused tests passed; no tests were rerun for packaging.
- Detailed current evidence: `evidence/latest/{drc.json,erc.json,netlist.xml,summary.json,
  exact-parity-and-mechanics.json,drc-delta.json,final-status.json}`.

## What actually changed and routed

Sync already added 32 missing refs (including L5/U14), removed 23 obsolete refs and
replaced L1/L4 with the approved lands. Duplicate-property UUID repair and every
footprint/copper removal are recorded in `evidence/{metadata-sync,uuid-repair,
footprint-sync,footprint-format-repair,stale-copper}.json`. The corrected footprint
sync removed 37 tracks/3 vias; an earlier overbroad trial was superseded and its
38 excess deletions restored. No superseded PCB is packaged.

Authorized observed native-net-drift deletions total **92 tracks + 21 vias** over
four audited rounds (initially 42 + 11). These are distinct from subsequent routing
replacement of **12 obstructing tracks + 2 vias**.

The actual final request created **57 segments and five ordinary 0.300 mm-drill vias**
from 31 hand-specified polylines/five via operations. It moved C70 from (118.3,88.3)
to (118.3,86.8), and C84 from (131.0,74.8) to (131.0,75.0). **L5 remains accepted at
(119.8,78.8), 0 degrees, F.Cu**. Only partial routes exist on:

- `/VPROT`: boost input-bank/inductor feed and local VIN/EN decoupling.
- `/Direct 9V positive boost/PBOOST_SW`: inductor/rectifier trunk and QFN fanout.
- That sheet's `PBOOST_SS`, `PBOOST_COMP`, `PBOOST_COMP_RC`, `PBOOST_FB`,
  `PBOOST_FREQ`, `PBOOST_FREQ_SER`: local control/sense connections.
- `/GND`: local boost returns and plane-access vias.

**Autorouter-selected routes: none.** Common tools executed explicit coordinates;
they did not choose paths. These five vias are NOT completed LDO thermal-via work.
See `evidence/latest/routing-audit.json` for exact created/deleted IDs and nets.
PRAW/output Kelvin feed, negative IBB, NRAW distribution and other affected
power/feedback/return connections remain unfinished; 129 legacy-net copper objects
on nine obsolete nets remained in the prior audit. Fixed UI/mounting/outline and
zone preservation is documented in the existing parity/mechanics receipt.

## Known unresolved limits — do not silently bypass

- Actual common `pcb apply` failed with **"Save/reload net table changed"**:
  three empty legacy names (`BI_REF`, `COMP_N`, `INV_SW`, under `/Direct bipolar rails/`)
  disappeared and 97 numeric net codes renumbered. Independent item comparison found
  no unintended item/pad-net changes after documented resource-path rebinding.
  This is not permission to weaken the invariant or call the failed apply accepted.
  Evidence: `evidence/{apply-failure,independent-reload-audit}.json`.
- Last records show zero raw/native copper-net assignment drift and inspect/doctor
  pass, not full DRC acceptance. Future fresh drift remains subject to the prior
  exact UUID logging/deletion authorization, not net-wide rip-up.
- Common schema cannot delete/replace footprints or resize reference fields;
  audited native exceptions were separately authorized. Four 0.65 mm references
  still violate the 0.8 mm text requirement. Do not hide them or weaken rules.
- Last TraceMaker doctor reported routing not ready (runtime not installed/reviewed).
  Do not assume the optional hybrid path is available. Never full-board autoroute.
- Existing L1 mechanical decision remains recorded, not resolved by packaging:
  5.10 mm envelope versus 5.40 mm under the recorded allowance calculation.
  See `evidence/l1-mechanical-design-decision.json`; no stack/land/part change is
  silently authorized by this checkpoint. LDO thermal and JLC compatibility work
  is newly authorized for continuation, not already complete.

## Compact dependencies and portable restoration

All small local project dependencies are copied **byte-for-byte**: same-stem project
settings, frozen root/seven child schematics, symbol/footprint tables and local
libraries. Copied schematics are immutable reference snapshots, not design edits.
Candidate-specific relative model tokens in footprints/board are retained unchanged.
Shared `opt/` tools and module tools remain repository dependencies, never duplicated.

**14 cached STEP resources are intentionally not staged.** `DEPENDENCIES.json` gives
all model tokens' project-relative destinations, sizes, SHA-256 values and providers
under `/usr/share/kicad/3dmodels`. All 14 matching providers were present at packaging.
`materialize_resume.py` copies the preserved project into an exclusively NEW research
folder and restores those exact resources; it does not load/save KiCad, alter tokens,
rerun sync, route or check. A missing/hash-different provider fails closed; use
`--model-root` for an equivalent installed library elsewhere. Do not remove model
references to make closure checks pass. No user-state `.kicad_prl`, binary, model
cache, duplicate PCB, image, huge stdout dump or fabrication output is staged.

## Exact continuation entry points (FUTURE CHAT ONLY; not run while packaging)

Run from repository root after reviewing AGENTS and the shared KiCad workflow and
hybrid-routing docs; inspect actual tool help before new engineering operations.

```sh
C=modules/usb-power/research/sr2-routing-checkpoint
R=modules/usb-power/research/sr2-routing-resume-001
python3 -B "$C/materialize_resume.py" --output "$R"
python3 -B opt/kicad-tools/kicad_tools.py pcb inspect --config "$R/candidate-profile.json"
python3 -B opt/kicad-tools/kicad_tools.py doctor --config "$R/candidate-profile.json"
```

`rework-requests/boost-005.ops.json` is the exact last applied request;
`boost-005.plan.json` is its original hash-bound plan; `boost-005.review.json` and
`boost-003.scope-review.json` explain the local changes. **Do not replay them:** their
geometry already exists here and their preconditions refer to omitted older input.
The unchanged `boost_routes.py` is only the original first-draft intent helper, not
the final revised route coordinates. Read the final operations as the source of truth.
The unchanged `check_manual_routes.py` remains runnable at this directory depth and
uses the repository's native worker; it is a collision screen, not a router or DRC.

After writing a NEW, explicitly reviewed `next.ops.json` for still-needed changes:

```sh
python3 -B "$C/rework-requests/check_manual_routes.py" \
  --board "$R/usb-power.kicad_pcb" --ops "$R/next.ops.json" \
  --output "$R/next.collisions.json"
python3 -B opt/kicad-tools/kicad_tools.py pcb plan \
  --config "$R/candidate-profile.json" --ops "$R/next.ops.json" \
  --allow-draft-opens > "$R/next.plan.json"
# Inspect the plan and its exit status before applying; never accept failed output.
python3 -B opt/kicad-tools/kicad_tools.py pcb apply \
  --plan "$R/next.plan.json" \
  --output modules/usb-power/research/sr2-routing-apply-next
```

Native verification of a chosen continuation candidate uses the existing common
`check --config <candidate-profile> --reports <NEW-report-directory>` command;
independent exact field/NC/mechanical comparison remains mandatory. No packaged
old sync/test driver is needed to resume: they require deliberately omitted older
projects. No rule weakening, exclusions, schematic changes, commits or fabrication
exports. Finish the remaining routing/clearances and authorized thermal/JLC work
in the fresh chat, not in this preservation task.
