# Big Modular KiCad tooling and sourcing

## Local toolkit, not a dependency on another checkout

The portable toolkit was imported from Bread Modular commit
`3894c03d4afedd2eb782a3e1270403840abc848d` using its fixed-allowlist `bundle`
command with `--include-routing --include-tracemaker`. Bread Modular was read
only. The local tools and skills do not require that original checkout at runtime.

- Canonical tools, native/edit APIs, exporter, catalog client, BOM auditor and
  passive planner: [`../opt/kicad-tools/`](../opt/kicad-tools/README.md).
- Workflow skill: [`kicad-workflow`](../opt/kicad-tools/skills/kicad-workflow/SKILL.md).
- Sourcing skill: [`jlcpcb-assembly`](../opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md).
- Agent discovery: `.agents/skills/kicad-workflow` and
  `.agents/skills/jlcpcb-assembly`, relative links to those same canonical skills.
- Compatibility alias: `opt/kicad-jlcpcb` → `kicad-tools/jlcpcb`.
- Optional routing controller source: `opt/kicad-routing` and
  `opt/kicad-tools/tracemaker`. No vendor runtime, binary or download was imported.
- Import provenance and exact file hashes:
  [`import-manifest.json`](../opt/kicad-tools/import-manifest.json).
- Upstream MIT license: [`../opt/kicad-tools/LICENSE`](../opt/kicad-tools/LICENSE).
  Big Modular's existing root license is unchanged.

No Bread Modular boards, library collections, firmware, Git metadata, credentials
or production artifacts were copied. Upstream historical test/research evidence
belongs to the toolkit; it is not validation of Big Modular hardware. The root
Big Modular README was retained instead of the standalone bundle README.

[`Code.md`](../Code.md) and [`AGENTS.md`](../AGENTS.md) make this the required
common-tool-first workflow for subsequent KiCad and sourcing tasks.

## Start here

Run from this Big Modular workspace root:

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B opt/kicad-tools/kicad_tools.py assembly --help
python3 -B opt/kicad-tools/kicad_tools.py assembly audit --help
```

The project profile explicitly selects `hardware/big_modular.kicad_pcb`, its root
schematic and local libraries. This avoids ambiguous selection between the
carrier and `front_panel.kicad_pcb`. Paths are relative to the profile file, not
the original Bread Modular checkout, and no global configuration is required.

Core tools use Python's standard library. Native checks need an installed KiCad
CLI; PCB edit APIs additionally need a compatible `pcbnew` interpreter. `doctor`
reports actual dependencies; use its output rather than assuming optional
routing runtimes are installed.

## Read-only native inspection

Always choose a **new** report directory outside `hardware/` and its dependencies:

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json \
  --reports research/kicad-private-check-01 --dry-run

python3 -B opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --only erc \
  --reports research/kicad-erc-01

python3 -B opt/kicad-tools/kicad_tools.py netlist inspect \
  research/kicad-erc-01/netlist.xml
```

The real check stages private copies, exports a native XML netlist and retains
raw commands, native findings and source hashes. An ERC-only run is an explicit
partial scope; it does not run board DRC. The checker still compares ref/pin/net
identities: **the carrier's incomplete J1 + UI socket-reservation PCB intentionally does not match the full
88-component schematic, so findings/exit 1 are expected**, even if ERC has no
violations. Never suppress that mismatch or call this a fabrication-ready pass.
A full `check` additionally runs native DRC/refill-in-memory/parity without saving
the source board; it is diagnostic, not permission to synchronize or route it.
The mechanical front panel is not a full schematic-matched circuit project.

Keep Big Modular's existing generation and engineering verification commands in
[`README.md`](../README.md). Do not rerun generators or overwrite existing reports
merely to install or test shared tools.

## Sourcing, audits and alternatives

Read both the [sourcing skill](../opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md)
and [assembly API/policy](../opt/kicad-tools/jlcpcb/ASSEMBLY.md) before use.
Illustrative bounded **read-only** catalog commands (not run by setup):

```sh
python3 -B opt/kicad-tools/kicad_tools.py assembly lookup C25804 \
  --strict-live --max-requests 1 \
  --cache-dir research/jlcpcb-catalog

python3 -B opt/kicad-tools/kicad_tools.py assembly search '10k 0603' \
  --basic-only --limit 12 --strict-live --max-requests 1
```

These example codes/values are not chosen Big Modular parts. Keep exact C-code,
MPN, footprint/land pattern, ratings, circuit conditions, Basic classification,
Economy eligibility, quantity/stock and dated raw evidence independent. Missing
eligibility or rating data remains unknown; offline fixtures never prove live
availability. Passive network suggestions are review candidates, not approvals
or automatic schematic/PCB changes. No authenticated calls, uploads, purchases
or order placement are performed by the sourcing tools.

**Do not feed root `BOM.csv` directly to `assembly audit --bom`:** that command
expects the exporter's grouped assembly BOM schema. Big Modular's CSV is a
per-reference design inventory. Also, auditing this partial PCB alone would
miss the unplaced circuit parts. Once design work is explicitly authorized,
reconcile the full native schematic inventory and approved manual/DNP exclusions,
then obtain a matched exporter BOM/CPL/report or complete native PCB/XML inputs,
reference-specific requirements and actual board quantity before an assembly
audit. Missing CPL, incomplete placement and unknown requirements are blockers,
not reasons to exclude most of the circuit. Do not run the Bread Modular
`modules/` production wrapper in this project.

## Tooling-only verification

No network, real manufacturing exports or runtime installation is needed:

```sh
unset KICAD_JLCPCB_INTEGRATION PYTHONPATH
python3 -B -m unittest discover -s tests -v
python3 -B -m unittest discover -s opt/kicad-tools/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/jlcpcb/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/automation/tests -p test_unit.py -v
python3 -B -m unittest discover -s opt/kicad-tools/schematic/tests -v
python3 -B -m unittest discover -s opt/kicad-routing/tests -v
python3 -B -m unittest discover -s opt/kicad-tools/tracemaker -p test_trial.py -v

# Optional native tests use synthetic temporary designs only.
KICAD_TOOLS_INTEGRATION=1 python3 -B -m unittest discover -s opt/kicad-tools/tests -v
```

Keep `KICAD_JLCPCB_INTEGRATION` unset for shared-suite discovery: that legacy
opt-in includes real repository-board exports. Native/router/engine tests not
explicitly enabled remain skips, not passes. See the imported
[verification guide](../opt/kicad-tools/VERIFICATION.md) for each exact native
opt-in and its limitations; do not mistake its historical results for new runs.

Current setup evidence is kept under ignored
`research/kicad-toolkit-verification/`; the tracked local integration guards check
payload hashes, relative skill links, explicit selection, no-write dry-run
behavior and canonical/compatibility CLI entry points. Tool tests validate the
installation, not this power circuit's electrical safety or order readiness.

### Results actually run for this import

| Suite | Passed | Skipped | Failures/errors |
| --- | ---: | ---: | ---: |
| Big Modular setup guards | 6 | 0 | 0 |
| Toolkit core, default | 53 | 2 native opt-in | 0 |
| Assembly/sourcing/exporter | 97 | 6 native opt-in | 0 |
| PCB automation unit | 13 | 0 | 0 |
| Schematic, default | 15 | 12 native opt-in | 0 |
| Routing unit | 76 | 0 | 0 |
| TraceMaker controller unit | 27 | 0 | 0 |
| Toolkit core, synthetic native/relocation | 55 | 0 | 0 |

Doctor resolved the explicit project and installed CLI/`pcbnew`; dry-run created
no output. Native XML export/inspection succeeded. A real private **ERC-only**
run returned findings/exit 1 with no operational errors and unchanged source
hashes during that run. It retained the expected incomplete PCB parity and
**68 footprint-link warnings**: the isolated HOME/config has no standard global
footprint-library table. Those configuration warnings were not suppressed or
misrepresented as circuit findings/cleanliness; the original tracked ERC report
remains untouched. Board DRC was not run against Big Modular during setup.

The `pcbnew` dependency probe also retained its upstream `PROPERTY_ENUM`
assertion diagnostics while returning successfully. No live supplier lookup,
stock/eligibility validation, real-board export, router execution or runtime
installation was performed. Native exporter checks used synthetic temporary
fixtures only.

Big Modular schematics, boards, BOM, existing reports, libraries and engineering
scripts remained byte-identical. Two `.kicad_pro` metadata files changed
concurrently while a KiCad GUI process had this workspace open; those unrelated
metadata changes were preserved rather than reverted or folded into the toolkit
import. Bread Modular's source hashes, Git HEAD and pre-existing status were
verified unchanged.

## A4.2 mechanical-placement boundary

Two active PCBs: `big_modular` and mechanical `front_panel`. The middle board is
retired in `docs/archive/a3-stack-superseded.zip`. No UI mating headers remain.
Use `build_stack.py --output NEW` and `build_mechanics.py --output NEW` for candidates.
The native helper is narrowly required because common `pcb inspect` rejects the
retained USB 3D dependency and cannot author these part/NPTH reservations. Shared
`check` still runs private ERC/DRC/parity; current evidence: `reports/stack-a4-2-native`.
Do not equate geometry tests with a routed or power-qualified circuit. The output
J2 is cable-mounted; J7 is a new PCB-only landing, not a header population choice.
