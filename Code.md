# Big Modular project instructions

This is Bread Modular's take on a set of Eurorack modules. Read `README.md` for
current circuit, mechanical and fabrication blockers before hardware work.

## Workspace and source boundaries

- Make edits only in this task's isolated Big Modular Git workspace.
- Bread Modular at `/home/azero/data/projects/bread-modular` is a read-only
  reference: never edit, regenerate, initialize submodules, install tools,
  switch branches or commit there. The older `projectsh` path is not present on
  this host; the actual source path was verified during toolkit import.
- Do not commit, merge, push, order parts or upload designs without explicit user
  authorization. Importing tooling is not permission to modify the circuit.

## Required KiCad and part-sourcing workflow

Use the imported common tools first; do not recreate exporters, catalog clients,
parsers or routers when the existing toolkit supports the requested operation.

- Before any KiCad task, read
  `opt/kicad-tools/skills/kicad-workflow/SKILL.md` and the relevant command's
  actual `--help`/API documentation.
- Before sourcing, substitutions, BOM audits or assembly preparation, also read
  `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`,
  `opt/kicad-tools/jlcpcb/ASSEMBLY.md` and the exporter README.
- The two skills are discoverable at `.agents/skills/` through relative links.
  Their single authoritative copies live under `opt/kicad-tools/skills/`.
- Start with `python3 -B opt/kicad-tools/kicad_tools.py doctor --config
  tools/kicad-project.json`. This profile explicitly selects the carrier and
  root schematic; there are two PCBs, so do not rely on automatic selection.
- Use `opt/kicad-tools/kicad_tools.py` for private checks, native netlist work,
  candidate PCB/schematic edits, export and assembly sourcing. Legacy
  `opt/kicad-jlcpcb` resolves to the same canonical JLCPCB utilities.
- Outputs and candidates must be explicitly new and separate from source files.
  Use `research/` or a new external temporary path for reports/catalog snapshots.
  Preserve all native findings and source hashes; do not weaken rules or hide
  unknowns to obtain a clean result.
- Supplier stock and service eligibility require bounded `--strict-live`
  evidence. Offline fixtures/caches are replay evidence, never current stock.
  Follow the sourcing skill's independent Basic/Economy gates for assembled R/C
  parts, exact code/MPN/footprint/rating checks and explicit manual exclusions.
  All substitutions require electrical and physical review; no CSV-only edits.
- The upstream skills contain historical Bread Modular module/branch examples.
  Apply their common-tool and safety workflow here, but do not run module-specific
  production wrappers, release jobs or commit instructions in Big Modular.

## Preserve Big Modular's current hardware state

Both boards are intentionally unrouted. The carrier contains only electrical
connector J1; the front panel is mechanical. **Do not synchronize either board
from the full schematic, place components, route, regenerate manufacturing
outputs or install a routing runtime as part of tooling setup.** Existing J1
geometry, project libraries, `BOM.csv` and hardware deliverables are not migrated
from Bread Modular.

`check` always retains native schematic-to-PCB parity findings, including in an
ERC-only run. The incomplete carrier is expected to fail full parity. Report
that as the known design state, not a toolkit installation failure or a clean
hardware check. The panel has no matching circuit schematic; do not pair it with
the carrier schematic to manufacture a pass.

Keep the existing `tools/build_project.py`, `tools/render_schematic.py`,
`tools/build_mechanics.py` and `tools/verify_project.py`: they encode Big Modular's
specific inventory/geometry regressions and are not replaced by generic tools.
Regeneration is a separate, explicitly scoped design task.

Optional Freerouting and TraceMaker controllers are copied for future authorized
use, but their runtimes are not installed. Availability of their source code is
not permission to route this power design. Passing tool tests, ERC or DRC never
establishes electrical safety, fabrication approval or order readiness.

## Setup verification

See `docs/kicad-tooling.md` for commands, import provenance and limitations.
Run `python3 -B -m unittest discover -s tests -v` for local integration guards.
Keep `KICAD_JLCPCB_INTEGRATION` unset during shared-suite discovery; its legacy
opt-in can export real repository boards. Use only the documented synthetic
native opt-ins for tooling verification.
