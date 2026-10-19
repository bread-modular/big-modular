# MIDI two-version tree: rebuild status

Why this file exists: workspace 107 held the complete V1 + V2 project. It was merged
into `main` (6bb9ae7) from a stash that left out untracked files, and then the
worktree was deleted. The new directories (`hardware/v2/`, `tools/v1|v2/`,
`jlcpcb/v1|v2/`) were never added to git, so they were lost. This file records what
survived, what has to be regenerated, and every deviation from the contract in
`Code.md`. It is updated after each rebuild step.

## Step log

| Step | State |
|---|---|
| 1 Inventory + gap analysis | done (this file, `docs/v2/recovered/`) |
| 2 Layout (`hardware/v1`, `tools/v1`, `jlcpcb/v1`, shared-tool patch) | pending |
| 3 V1 restore + verification | pending |
| 4 V2 rebuild + verification | pending |
| 5 Docs pass | pending |

## Recovered evidence (outside the repo, read-only)

| Source | Content | Use |
|---|---|---|
| `~/recovery-107/107-uncommitted-tracked.patch` | 12-file patch: `opt/kicad-tools` `source_manifest` profile key + `manifest_root` (check and exporter), tests and docs; `tools/fit_assembly.{py,sh}` take `v1\|v2`; `tools/import_footprints.py --version` + `V2_FOOTPRINTS`; `panels/README.md` | applies cleanly to `main` (`git apply --check`); applied in step 2 |
| `~/recovery-107/bl2u65eu9.txt` | V2 (S3) native netlist + full field dump (62 parts, 56 nets, 173 pins, symbol UUIDs), the final V2 DRC JSON (0/0/0), V2 export report (41 assembled parts, 18 BOM rows, `side: bottom`) | extracted to `docs/v2/recovered/netlist.json` |
| `~/recovery-107/b22045jd2.txt` | shared `pcb apply` acceptance report of `research/v2-bypass/route-cand1` (V2 **R2** routing, plan sha256 `42c3b169…`): status accepted, checks ERC/DRC empty, parity equal. Its `inspection` holds every footprint (ref, XY, rotation, side, symbol path), every pad net, all 218 tracks and 57 vias (XY, width, layer, net), the 4 zone anchors and all silk texts | extracted to `docs/v2/recovered/board-inspection.json` (footprints, pads, tracks, vias, zones, silk text) |
| `~/recovery-107/bmeg7o4y2.txt` | a copy of the shared `jlcpcb-assembly` SKILL.md | no rebuild content |
| `~/recovery-107/107-autostash-files.txt` | the 138 tracked paths of the stash (no untracked paths) | confirms that `hardware/v2`, `tools/v1\|v2` and `jlcpcb/v1\|v2` were never tracked |
| branches `recover/107-autostash` (6729a04), `recover/107-commit` (9cfaed0) | the stash deletes the flat `hardware/midi.*`, `jlcpcb/*` (moved into untracked `v1/` dirs); 9cfaed0 = `main`'s MIDI commit | not merged, not deleted |

Notes on the evidence:

- The route report is the V2 **R2** board (JP2 note: "1-2 (default copper bridge)").
  The netlist dump is **S3/R3** (JP2 footprint
  `MIDI:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm`, `exclude_from_bom`). By
  `Code.md` and `docs/research.md` §7.5, R3 only swaps JP2 to the stock Open
  footprint (same pads, no copper bridge) and updates its note; tracks and vias
  are R2's. So V2 R3 copper = the recovered R2 tracks/vias + the Open JP2.
- Zone outlines are not in the inspection (anchor point only). They have to come
  from the V1 generator logic (complement polygons 0.3 mm off the VIN_LDO heat
  sink); V2 keeps the V1 heat sink, and the recovered anchors match V1's corners.

## What `main` has (6bb9ae7)

| Path | State |
|---|---|
| `hardware/midi.kicad_{pro,sch,pcb}`, `fp-lib-table`, `sym-lib-table` (flat) | V1 S4/R5 project: 45 footprints, no R2/R21, JP1 present, no JP2, B silk `MIDI V1.0`, no `JLCJLCJLCJLC` marker, 149 segments, 47 vias. Belongs in `hardware/v1/` |
| `hardware/fp-lib-table`, `sym-lib-table` | `${KIPRJMOD}/MIDI.pretty`, `${KIPRJMOD}/MIDI.kicad_sym`: **broken**, the merge moved both into `hardware/v1/` |
| `hardware/_kicad_models/` (11 dirs) + `hardware/v1/_kicad_models/` (3 dirs, one duplicate) | the union is the 13 models the V1 board references; to be merged into `hardware/v1/_kicad_models/` |
| `hardware/v1/MIDI.pretty`, `MIDI.kicad_sym`, `MIDI.3dshapes` | V1 library, present (13 footprints + PROVENANCE.json) |
| `tools/*.py`, `tools/kicad-project.json` (flat) | V1 S4 generators (last changed in 6ea27cb, which also produced the S4/R4 board): `build_schematic.py`, `build_layout.py` (writes `MIDI V1.0`), `route_plan.py`, plus the shared `sexp.py`, `import_footprints.py`, `fit_assembly.*` (pre-patch, single version) |
| `jlcpcb/{carrier,panel,assembly}`, `jlcpcb/*.zip`, `jlcpcb/source-sha256.json`, `jlcpcb/README.md` | V1 export (flat). Belongs in `jlcpcb/v1/` |
| `docs/` (V1) | `geometry.json`, `fit/`, `midi-schematic.pdf`, `schematic-symbols.json`, `jlcpcb-audit-requirements.json`, `research.md` (incl. §7), `mechanics.md`, `sourcing-candidates.json`: present |
| `docs/v2/` | `geometry.json` (differs from V1 only in `revision` and `back_side_parts`), `schematic-symbols.json`, `midi-schematic.pdf`, `jlcpcb-audit-requirements.json`, `fit/{carrier-front,carrier-back}.png`, `fit/{carrier-drc,schematic-erc,fit-report}.json`: present |
| `panels/` | shared panels: present, unchanged |
| `opt/kicad-tools` | lacks the `source_manifest` support from the patch |

## Gap per version

### V1 (S4/R5)

| Required by `Code.md` | Status |
|---|---|
| `hardware/v1/midi.kicad_{pro,sch,pcb}`, lib tables, `_kicad_models/` | move from flat `hardware/` (step 2) |
| `tools/v1/{build_schematic,build_layout,route_plan}.py`, `tools/v1/kicad-project.json` (with `source_manifest`) | move from flat `tools/`, repath to `hardware/v1` (steps 2-3); `route_plan.py` must reproduce the R5 copper (check in step 3) |
| `jlcpcb/v1/{carrier,panel,assembly}`, zips, `source-sha256.json`, `README.md` | move from flat `jlcpcb/`, then re-export with the shared exporter (step 3) |
| `docs/fit/` | present; refresh in step 3 |

### V2 (S3/R3)

| Required by `Code.md` | Status |
|---|---|
| `hardware/v2/MIDI.pretty` (+ stock SOT-23, SOT-323_SC-70, R_0805, SolderJumper-3 Open), `MIDI.kicad_sym`, `_kicad_models/` | **lost**; regenerate with `tools/import_footprints.py --version v2` and the V2 schematic generator |
| `hardware/v2/midi.kicad_{pro,sch,pcb}` | **lost**; regenerate |
| `tools/v2/build_schematic.py` | **lost**; rebuild from `tools/v1/build_schematic.py` + `docs/v2/schematic-symbols.json` + `docs/research.md` §7 + `docs/v2/recovered/netlist.json` (fields, values, footprints, nets must match exactly) |
| `tools/v2/build_layout.py` | **lost**; rebuild from `tools/v1/build_layout.py` + `docs/v2/geometry.json` (placement must match the recovered footprint XY/rotation) |
| `tools/v2/route_plan.py` | **lost**; rebuild so its tracks/vias equal the recovered 218 tracks + 57 vias |
| `tools/v2/kicad-project.json` | **lost**; recreate |
| `jlcpcb/v2/` | **lost**; re-export with the shared exporter |
| `docs/v2/fit/` | present (pre-loss); refresh after the rebuild |

## Deviations

None yet.
