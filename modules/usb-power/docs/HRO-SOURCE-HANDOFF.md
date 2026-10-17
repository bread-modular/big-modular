> Historical024 source handoff retained for provenance.025 completed its remaining
> scope; current release is production/hro-r1 and current integration instructions
> are docs/hro-integration.md. Do not follow the old deferred/candidate-only status.

# HRO source handoff — continue fabrication from these canonical files

Workspace: `/home/azero/.okbrain/workspaces/big-modular/024`; branch `okbrain/big-modular/024-8cdb205a`; base `7bf93dc`.
Uncommitted, unstaged. No commit/merge/main writes/GUI interaction/advisors/uploads/orders.
Latest steering: finish source checks, hand off now; fabrication ZIP/CAM packaging deferred.

## Verified checkpoint

- Canonical `hardware/usb-power.kicad_pcb`: `a8cd9e8dbb8451fd426e5dc5feed8090044b879353ade9b36bcf02a0aaa8e4e6`.
- Canonical `hardware/usb-power-panel.kicad_pcb`: `d6c75c7b9994f7e6fe9d1e6688407e5e3b4f87e4d8c4d073cfd85ff2aa28974b`.
- **71/71 tests pass**, fail-fast full suite. Final log: `research/hro-release-024/final-tests-source-preserving.log`.
- Fresh carrier ERC: **0 errors /0 warnings /0 exclusions /0 ignored checks**.
- Fresh carrier DRC: **0 errors /0 warnings /0 exclusions /0 ignored checks /0 opens /0 native parity findings**; independent ref/pin/net parity equal.
- Passive panel DRC: **0 errors /0 warnings /0 exclusions /0 ignored checks /0 opens**. No schematic/ERC applies to this passive panel.
- Same zero native results for the saved-main presentation overlay described below.
- 64 electrical +4 mechanical carrier footprints;421 segments/133 vias/4 zones. One continuous In1 GND; isolated RTN and every net's connected-pad membership pass. Geometry/M3/HRO fit pass.
- 197 non-USB electrical pin identities preserved. Exactly8 USB segments +1 CC2 via changed from supplied routed source; other545 copper items and non-USB pad/model/pose geometry preserved. No GCT relief code/import.
- All-severity checks exposed5 four-way schematic junctions: changed to paired Ts with identical connectivity, not excluded. Only nonfabrication J7/hole courtyards and exact library filters added outside J1.
- Schematic/source/library/BOM determinism, NEW routed-copy preservation, NEW panel builder safety and mechanical drawing regeneration passed. Assembly/USB-fit SVGs visually inspected. SCAD is a labelled envelope only; no OpenSCAD executable was available.

Evidence under `research/hro-release-024`:
`final-native-check/summary.json`, `final-native-check/erc.json`, `final-native-check/drc.json`,
`final-native-check/netlist.xml`, `final-panel-drc.json`, `final-geometry.json`,
`final-verification.json`, `final-overlay-check/summary.json`,
`source-preservation-verification.json`, `external-preservation-final.json`,
`final-source-manifest.json`, `changed-files.txt`.
Failed/intermediate checks are retained; do not confuse `final-carrier-check/` (an earlier failed pass) with successful **`final-native-check/`**.

## Main overlaps and non-destructive integration

Main is still dirty. Overlap paths are the six `.kicad_sch` files and `hardware/usb-power.kicad_pro`.
Main's `hardware/.history` is dirty but is NOT a task delta and must stay untouched.
All98 captured main files, all73 predecessor023 files and four Bread reference files
still hash-match the initial snapshot. User presentation changes were NOT imported
as this workspace's task delta.

The NEW, native-verified presentation-preserving merge aid is
`research/hro-release-024/main-presentation-overlay-v2/`.
It combines canonical HRO board/libs with the captured user's sheet presentation and
project metadata. `presentation-overlay.json` records exact input hashes; its boards
are the canonical board bytes. It patches only J1 identity/shared-pin mapping,
three exact footprint filters, stage text and five paired-T presentation repairs.
Non-J1 instances and all other wire/layout bytes are retained. No main write occurred.

User-controlled strategy: save/close KiCad yourself before integration; compare live
main hashes against the overlay input manifest. If equal, preserve your presentation
using this overlay for the seven overlapping files, while integrating the remaining
scoped workspace delta normally. If changed, snapshot the newly saved main closure
outside main and run `tools/hro_merge_overlay.py --input-hardware SAVED_COPY --output NEW`
from this workspace, then rerun native checks on the NEW overlay. Never replace dirty
sheets/project with this workspace's older presentation wholesale. Do not copy `.history`,
locks or personal GUI settings. Finally rerun full tests/native checks on the user-merged
canonical tree. No automatic stash, checkout, reset, commit or merge is needed/performed.

## Focused continuation (not completed here)

Audit actual via-in-pad intersections and reconcile the intended all133 Type-VII
fill/cap process with final drill/fab notes; do not assert every via individually
requires filling. Finalize truthful carrier four-layer stack/material/finished1.6mm/
copper/drill/process notes and separate passive panel requirements. Current stack
was preserved, not supplier-approved. Export from these exact canonical source hashes,
inspect actual Gerbers/drills/closed outlines/plated slots/NPTHs/masks/paste/silk/all
four copper layers, generate clearly named separate ZIPs, preview and hash-manifest
the final output. No manufacturing export or assembly CSV was generated here.
Use common tooling; bare-PCB-only output support is a separate continuation concern.
Do not imply assembly/sourcing/bench/physical cable or ABS bracket qualification.
See `docs/usb-hro-review.md` for exact land deviations, missing model and aperture fit limits.

## Exact changed-file inventory

```text
AGENTS.md
BOM.csv
Code.md
README.md
docs/HRO-SOURCE-HANDOFF.md
docs/assembly-geometry.json
docs/assembly.pdf
docs/assembly.svg
docs/build.md
docs/engineering.md
docs/mechanical-baseline.json
docs/mechanical-preservation.json
docs/mechanics.md
docs/pin-net-audit.json
docs/routed-baseline.json
docs/schematic.pdf
docs/usb-fit.pdf
docs/usb-fit.svg
docs/usb-hro-review.md
hardware/01_input_protection.kicad_sch
hardware/02_hardgate.kicad_sch
hardware/03_bucks.kicad_sch
hardware/04_bipolar.kicad_sch
hardware/07_output_rails.kicad_sch
hardware/BigModular.kicad_sym
hardware/BigModular.pretty/HRO-TYPE-C-31-M-12.kicad_mod
hardware/BigModular.pretty/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.kicad_mod
hardware/BigModular.pretty/WireLanding_2x08_P2.54mm.kicad_mod
hardware/usb-power.kicad_pcb
hardware/usb-power.kicad_pro
hardware/usb-power.kicad_sch
hardware/usb-power-panel.kicad_pcb
hardware/usb-power-panel.kicad_pro
hardware/mechanics/assembly-envelope.scad
tests/test_hro_source.py
tests/test_m3_access.py
tests/test_stack_geometry.py
tools/build_mechanics.py
tools/build_stack.py
tools/electrical_design.py
tools/hro_connector.py
tools/hro_fit.py
tools/hro_merge_overlay.py
tools/render_schematic.py
tools/routed_checks.py
tools/stack_geometry.py
tools/verify_project.py
tools/verify_stack.py
```
