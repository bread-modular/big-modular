# Bounded model-resource verification

Shared tooling only; no hardware edits/exports, source normalization, router run,
runtime download, dependency install or commit. Existing licensing is unchanged;
third-party model bytes are never bundled with the toolkit. Synthetic solid STEP
assets are generated locally by the installed native CLI inside temporary tests.

## Reproduce from repository or a core toolkit copy

```sh
python3 -B opt/kicad-tools/kicad_tools.py pcb inspect --help
python3 -B -m unittest discover -s opt/kicad-tools/tests -p test_models.py -v
KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v
KICAD_AUTOMATION_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/automation/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/schematic/tests -v
# Consumer-specific, read-only admission; PROFILE is an explicit project config:
python3 -B opt/kicad-tools/kicad_tools.py doctor --config "$PROFILE"
python3 -B opt/kicad-tools/kicad_tools.py pcb inspect --config "$PROFILE"
```

Verified with matching CLI/pcbnew 10.0.6 on Linux. Native startup PROPERTY_ENUM
assertions and SWIG deprecation diagnostics remain visible; not suppressed.

## Results and coverage

- Resource unit cases: **7/7 pass**. Multiple/repeated/same-basename models in PCB and library;
  STEP/STP/WRL; spaces, config-relative roots, KIPRJMOD, full hashes/byte bounds,
  unused-file exclusion, source preservation, output confinement, stale resources,
  absent/ambient variables, missing files, broken/in-root/escaping symlinks,
  unsupported formats/URIs, traversal, secondary references, embedded/images/fonts.
- Automation suite: **30/30 pass** (native opt-in). CLI inspect → plan → accepted
  text apply with external model/local footprint/symbol/repeated-sheet dependencies;
  all original item identities and exact model offset/scale/rotation arrays retained.
  Model-byte mutation invalidates the plan before output creation. A model-bearing
  template addition accepts; move/rotate retains model transforms and correctly
  produces an opens-only draft, not acceptance.
- Native relocation deletes the original source, model/library/sheet trees and
  config. Relocated inspect, XML/ERC/all-severity DRC/schematic parity pass. Native
  GLB export with **no board body** succeeds with nonempty model meshes and no
  exporter diagnostics, proving staged STEP/STP/WRL loading without source access.
- Exact empty `(embedded_files)` is dependency-free and native-readable, but native
  save drops it. Regression requires apply to **fail**, source unchanged and no
  completion marker; no preservation/canonicalization exemption was introduced.
- Shared suite: **62 run, 60 pass, 1 failure + 1 error**. Both outstanding
  checks require the already-missing root `docs/kicad-routing-research.md`: the
  optional routing bundle allowlist and an existing GUIDE link-validation test. Do not fix by relaxing the allowlist or inventing
  a file: routing packaging is outside this focused change.
- Flat-schematic default regression: **27 run, 15 pass, 12 opt-in skips**, no failures.
  No module/electrical tests were run or edited. Optional Gerbonara/Shapely dependency
  issues remain out of scope; nothing was installed or disabled.

## Consumer admission result — BLOCKED, not claimed PASS

The selected consumer's complete read-only `Plan` inventory succeeds with explicit
preinstalled model-root binding: **48 native/resource files, 2,739,748 bytes,
7 sheets, 14 distinct STEP files (1,201,863 bytes)** plus the profile hash. Every
referenced model (including those in explicit local `.pretty` dependencies) is
present and hash-covered. No model-tree scan, copying or real-board staging/edit
was performed. Source hashes reverified unchanged; PCB SHA-256:
`7c4e5fbc923ed376fee01d578f52644c276e3cb8a862d67e01b8ec7acaedfae9`.

`pcb inspect` stops at the existing **duplicate serialized board UUID** guard:
**24 duplicated IDs / 24 extra occurrences**. For example, UUID
`2747f57f-aa1b-5427-a105-3abd19e2ddd2` belongs to both `R4.Value` and
`R4.Manufacturer`; `bf90a805-96dc-5610-b74f-00d5590c8afc` similarly duplicates
`C11.Value` / `C11.Manufacturer`. The shared diagnostic now gives the board path,
duplicate count and bounded sample. No ignored project severities were found in
the bounded read-only settings scan. Later native lossless-save/electrical gates
are **not proven** for this consumer. Hardware UUID repairs need separate explicit
authorization; this task neither edits them nor relaxes their admission policy.

## Scope limits

Only self-contained STEP Part 21 / VRML2 references in native PCB/footprint models
are supported, not arbitrary resource formats, external STEP assemblies, WRL
URLs/scripts, symlink models, nonempty embedded files, images/fonts or project
resource-path settings. Existing symlink native-table policy is unchanged. This
is not a general geometry/hostile-file sandbox or a 3D export feature expansion.

Native STEP export cannot contain WRL mesh assets; the synthetic relocation probe
therefore uses native GLB (with all model kinds), not an ignored STEP-export error.
Router/TraceMaker supported subsets and all rule/lock/native check gates remain
unchanged. Re-plan after tool/config/resource/path changes; no source, snapshot,
output, hash or completeness guard is waived to gain admission.
