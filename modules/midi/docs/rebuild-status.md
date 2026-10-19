# MIDI two-version tree: rebuild status

Why this file exists: workspace 107 held the complete V1 + V2 project. It was merged
into `main` (6bb9ae7) from a stash that left out untracked files, and then the
worktree was deleted. The new directories (`hardware/v2/`, `tools/v1|v2/`,
`jlcpcb/v1|v2/`) were never added to git, so they were lost. This file records what
survived, what was regenerated and how it was verified, and every deviation from
the contract in `Code.md`.

## Current state (after step 5)

| | V1 (S4/R5) | V2 (S3/R3) |
|---|---|---|
| Sources | `hardware/v1/` = the pre-loss accepted files, moved (no byte changed) | `hardware/v2/` regenerated; netlist, fields, placement and all 279 copper items equal the recovered evidence |
| Generators | `tools/v1/` reproduce the schematic byte-identically and the board semantically (0 differences) | `tools/v2/` rebuilt; they reproduce the recovered evidence (0 differences) |
| Export | `jlcpcb/v1/` re-exported (BOM/CPL byte-identical, Gerbers differ only in dates) | `jlcpcb/v2/` re-exported (41 parts, 18 BOM rows) |
| ERC / DRC / parity | 0 / 0-0-0 / equal | 0 / 0-0-0 / equal |
| Shared `check` | no findings, manifest equal | no findings, manifest equal |
| 3D fit | 0 mm³ both panels | 0 mm³ both panels (report identical to V1's) |
| Not rerun | renders, live audit (BOM/CPL unchanged) | renders, live audit (gate in `jlcpcb/v2/README.md`) |

Nothing is missing from the `Code.md` layout. The deviations at the end are the
only places where a detail had to be chosen rather than reproduced.

## Step log

| Step | State |
|---|---|
| 1 Inventory + gap analysis | done (this file, `docs/v2/recovered/`) |
| 2 Layout (`hardware/v1`, `tools/v1`, `jlcpcb/v1`, shared-tool patch) | done: see below |
| 3 V1 restore + verification | done: see below |
| 4 V2 rebuild + verification | done: see below |
| 5 Docs pass | done: `Code.md`, `README.md`, `AGENTS.md`, `docs/research.md` §7.6, `jlcpcb/v1/README.md` (v1 paths), `jlcpcb/v2/README.md` (rewritten) |

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

## What `main` had before the rebuild (6bb9ae7)

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

## Gap per version (before the rebuild; all closed in steps 2-4)

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

## Step 2 result

- Applied `107-uncommitted-tracked.patch` unchanged (12 files). Shared tests:
  `tests/test_project` 13 OK, `jlcpcb/tests/test_export` 38 OK (4 skipped).
- `git mv` of the flat project into `hardware/v1/`; `fp-lib-table`/`sym-lib-table`
  are `${KIPRJMOD}`-relative, so they resolve again with no edit. The 11 + 3
  `_kicad_models` dirs were merged into `hardware/v1/_kicad_models/` (13; the
  duplicate PJ301M-12 was byte-identical).
- Flat generators -> `tools/v1/` (paths now `hardware/v1`, `tools/v1`; `sexp` is
  imported from `tools/`). Text the generators embed in outputs (board comment
  `nets: hardware/midi.kicad_sch`, sym-lib-table descr, schematic-symbols note) is
  left as it was so that step 3 can test byte reproduction.
- `tools/v1/kicad-project.json` points at `hardware/v1` and declares
  `source_manifest: ../../jlcpcb/v1/source-sha256.json`.
- Flat `jlcpcb/*` -> `jlcpcb/v1/` (moved, not regenerated).
- Verification: `kicad-cli` ERC 0; DRC (`--severity-all --schematic-parity
  --refill-zones`) 0/0/0; `doctor` exit 0. The sha256 values of
  `hardware/v1/midi.kicad_{pcb,pro,sch}` and the panel equal the old manifest's
  values, so the move changed no source byte. `check` exits 1 **only** because
  `jlcpcb/v1/source-sha256.json` still keys the old flat paths (generated file,
  not hand-edited; re-exported in step 3).

## Step 3 result (V1)

Reproduction test, in a scratch copy of the module (so no committed source was
rewritten): `tools/v1/build_schematic.py` -> `tools/v1/build_layout.py` ->
`tools/v1/route_plan.py` (71 polylines, 47 vias, 4 zones) -> shared `pcb plan` ->
`pcb apply` (accepted: ERC/DRC findings empty, parity equal) -> `pcb promote`
(0 external model tokens).

- `midi.kicad_sch`, `MIDI.kicad_sym`, `sym-lib-table`, `midi.kicad_pro`,
  `docs/schematic-symbols.json`: **byte-identical** to the committed files (after the
  generator's symbols note was updated to the `v1` paths the committed doc already
  had).
- `midi.kicad_pcb`: **semantically identical**. A pcbnew comparison of every
  footprint (FPID, position, rotation, side, value, symbol path, attributes, all
  fields, pad numbers/nets/positions, 3D model tokens, graphics), all 149 tracks,
  47 vias, 4 zones (layer, net, every outline vertex, settings), drawings, texts,
  title block and net list found 0 differences. It is not byte-identical: pcbnew
  gives new footprints random UUIDs, which also changes the footprint order in the
  file. So the committed (accepted, previously verified) board is kept as is.
- `_kicad_models/`: same 13 content-hash directories.
- The panel generator (`build_layout.py` also writes the panel) uses random UUIDs
  too; the shared panel is not regenerated.
- `tools/v1/route_plan.py` (flat `tools/route_plan.py` from 6ea27cb) is the S4/R5
  copper. The only R5 change was deleting the B silk marker; the flat
  `build_layout.py` already writes no marker.

Re-export (`jlcpcb/v1/`, shared `export.py`, README commands with `hardware/v1`
and `--manifest jlcpcb/v1/source-sha256.json`): the stale generated manifest and
unpacked plots were deleted first, then regenerated. `bom.csv` and `positions.csv`
are byte-identical to before; Gerber/drill files differ only in the creation
date; export reports differ only in absolute paths. The manifest now keys
`hardware/v1/*` and `jlcpcb/v1/*`.

Verification:
- native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`)
- native DRC `--severity-all --schematic-parity --refill-zones`: carrier 0/0/0,
  panel 0/0 (`docs/fit/carrier-drc.json`, `docs/fit/panel-drc.json`; only the
  date changed)
- `kicad_tools.py check --config tools/v1/kicad-project.json`:
  `no_findings_in_requested_checks`, exit 0, ref/pin/net parity `equal: true`,
  manifest equal (5 sources), `source_unchanged: true`
- `tools/fit_assembly.sh v1`: 0 mm³ against the FR4 and printed panels, board
  inside rail gap and panel width; `docs/fit/fit-report.json` byte-unchanged
- Renders (`docs/fit/*.png`) were not regenerated (no render command is recorded,
  and the board bytes are unchanged, so the images are still current).
- The live assembly audit was not rerun: BOM/CPL are byte-identical to the export
  it audited.

Helpers used for these comparisons (ignored, not deliverables):
`research/rebuild/boardsig.py`, `research/rebuild/extract.py`.

## Step 4 result (V2)

Rebuilt from `docs/v2/geometry.json`, `docs/v2/schematic-symbols.json`,
`docs/research.md` §7, `docs/v2/midi-schematic.pdf` (presentation) and the recovered
evidence in `docs/v2/recovered/`. Every comparison below is against that evidence.

- `tools/v2/build_schematic.py` (V1 generator + the V2 circuit): the native netlist
  equals the recovered S3 netlist: 62 refs, 56 nets, 173 pins, every field value and
  field order, every symbol UUID (same uuid5 scheme as V1), JP2 excluded from the BOM.
  The schematic plotted to PDF is word-for-word identical to the surviving
  `docs/v2/midi-schematic.pdf` (750 words, same bounding boxes to 0.01 mm), so that
  PDF is kept as it is. ERC 0. `docs/v2/schematic-symbols.json` regenerates
  byte-identically.
- `tools/import_footprints.py --version v2` -> `hardware/v2/MIDI.pretty` (V1 set + stock
  SOT-23, SOT-323_SC-70, R_0805, SolderJumper-3 Open). `midi.kicad_pro` and
  `fp-lib-table` copied from V1.
- `tools/v2/build_layout.py` (V1 generator, V2 geometry, asserts that V2 geometry
  equals V1 except `revision`/`back_side_parts`, no panel output, B silk
  `MIDI V2.0` + JP2 `P`/`D`): all 62 footprints (position, rotation, side, value,
  symbol path) and all 177 pads (position, net) equal the recovered board.
- `tools/v2/route_plan.py`: the recovered items carry uuid5 names under
  `big-modular/midi-v2/route/` (found from the zone UUIDs), so the original plan
  names were recovered: 91 V1 items unchanged, the TX vias/tracks that follow the
  0805 pads, R10/LED4, RX to JP2, LED8, the seven right-edge GND vias removed, and
  the V2 items (`cl*`, `clg*`, `clp*`, `p5cl*`, `rail*`, `railin`, `railr2`,
  `railu2`, `spine`, `u2p`, `r23p`, `r2p`, `r22p`, `midin*`, `midina/b`, `q1b`,
  `q1e`, `d9a`, `d9k`, `rxq`, `rxr2`, `uref`, `uref2`, `u2g`, `r24g`, `gnd*` vias).
  The plan predicts all 279 recovered items (218 tracks, 57 vias, 4 zones) with
  equal UUID, layer, net, endpoints and width: 0 differences.
- Shared `pcb plan` -> `pcb apply` (`research/v2/route-cand1`: accepted, ERC/DRC
  findings empty, parity equal, source unchanged) -> `pcb promote` (0 external
  model tokens). The promoted `hardware/v2/midi.kicad_pcb` has the 279 items with
  the recovered UUIDs and geometry (pcbnew read-back, 0 differences).
- Export `jlcpcb/v2/` (shared `export.py`, bottom side, `--require-part-numbers`):
  41 components in 18 BOM rows, JP2 excluded from the BOM, equal to the recovered
  V2 export report.

Verification:
- native ERC `--severity-all`: 0 (`docs/v2/fit/schematic-erc.json`)
- native DRC `--severity-all --schematic-parity --refill-zones`: 0/0/0
  (`docs/v2/fit/carrier-drc.json`); both reports differ from the surviving ones
  only in the date
- `kicad_tools.py check --config tools/v2/kicad-project.json`:
  `no_findings_in_requested_checks`, exit 0, ref/pin/net parity `equal: true`,
  `jlcpcb/v2/source-sha256.json` equal (5 sources); `doctor` exit 0
- `tools/fit_assembly.sh v2`: 0 mm³ against both panels, board inside rail gap and
  panel width; `docs/v2/fit/fit-report.json` byte-unchanged and identical to V1's

Helpers (ignored): `research/rebuild/{netcmp,placecmp,plancmp,coppercmp,v1inv2}.py`.

## Deviations

Each one is a detail the surviving sources do not fix. The choice and its basis are
recorded here.

1. **Not byte-identical files.** pcbnew gives new footprints and library items random
   UUIDs, so `hardware/v2/midi.kicad_pcb` and `hardware/v2/MIDI.pretty/*.kicad_mod`
   cannot equal 107's bytes (which are lost anyway). Placement, pads, nets and
   copper equal the recovered board (above); the footprints come from the same stock
   sources (`PROVENANCE.json` source hashes).
2. **V2 schematic title text.** The surviving PDF shows `... Circuit intent:
   docs/research.md 7` with no `§` glyph (the `7` starts where `§7` would). It is
   reproduced as shown, so the plot is word-identical. `§7` was probably intended.
3. **V2 board title block** (title, rev, comments) is not in any surviving source
   (§7.6 says R3 changed it). Chosen: title `Big Modular - MIDI V2 carrier`, rev
   `V2-S3`, comments in the V1 style. Not electrical.
4. **JP2 `P`/`D` silk size** is not in the inspection (position only). 1.0 mm,
   like `A`/`B`, matching their height in the surviving `docs/v2/fit/carrier-back.png`.
5. **Zone outlines.** The inspection only has each zone's first vertex. The V2 plan
   uses V1's polygons (same names, same anchors; `Code.md`: V2 keeps the V1 heat
   sink). DRC with refilled zones is 0.
6. **`hardware/v2/midi.kicad_pro`** is a copy of V1's (107's V2 project file is lost).
7. **`jlcpcb/v2/` layout** mirrors `jlcpcb/v1/` (carrier, panel, assembly, top-level
   ZIPs); 107's `jlcpcb/v2/README.md` is lost and is rewritten in step 5.
8. **Not rerun:** the renders (`docs/v2/fit/*.png`, from 107; no render command
   is recorded) and the live assembly audit (network; parts and fields equal
   the S3 netlist it audited).
