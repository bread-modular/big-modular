## Electrical prototype checkpoint (current)

The authorized electrical update supersedes the earlier unchanged-circuit checkpoint below.
See `docs/electrical-prototype.md`: new 7-child hierarchy, direct rails, always-on MCU diagnostics.
PCB mechanics/routing remain unchanged; no full schematic-PCB sync. Main power-up is blocked.

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
  root schematic; there are two active PCBs, so do not rely on automatic selection.
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

Both active boards are intentionally unrouted. A4.2 uses a front panel and one
perpendicular main PCB carrying J1, D10/D11/D12/SW1 and J7 wire landing reservations.
The middle PCB and J3-J6 were retired; previous files are in docs/archive.
J2 remains the off-board 16-pin keyed power OUTPUT on a flying lead. D10/D11/D12/SW1/J7
are NOT added to the unchanged circuit schematic/root BOM at the LED3 checkpoint.
R32 axial reservation is retired; Basic SMD LED resistors await the electrical brief.
D10/D11/D12 are reserved exclusively for +12/-12/+5 red manual LEDs by
`tools/interface_contract.py`; never allocate them to general diodes. Never parallel another
active PSU. Do not synchronize from the full schematic or generate manufacturing
outputs as part of tooling setup. Preserve native J1 geometry and circuit intent.

`check` always retains native schematic-to-PCB parity findings, including in an
ERC-only run. The incomplete carrier is expected to fail full parity. Report
that as the known design state, not a toolkit installation failure or a clean
hardware check. The mechanical panel has no matching circuit schematic; do not pair it with
the carrier schematic to manufacture a pass.

Keep the existing `tools/build_project.py`, `tools/render_schematic.py`,
`tools/build_mechanics.py` and `tools/verify_project.py`: they encode Big Modular's
specific inventory/geometry regressions and are not replaced by generic tools.
A4.2 uses `tools/build_stack.py --output NEW` and `tools/build_mechanics.py --output
NEW`; `tools/verify_stack.py` checks both boards, interface pins and brackets.
The legacy full builder is disabled. Read docs/mechanics.md and the buying guide:
two plain 3mm-wall M3 L brackets, restored TL3340AF160QG SMT switch with
hand-solder lands, and power output on cable-mounted IDC.
The retired TS-1166VW-type alternative has a separate custom footprint and
`docs/ts1166-switch.md` / `tools/verify_ts1166.py`. It is NOT installed: 7.1mm
normal projection exceeds the current 5.1mm allowance; uploaded row2.50 conflicts
with a public row2.15 variant. The user chose the earlier SMT part instead;
do not reinstall either THT alternative or widen the panel automatically.
Actual print/hardware fit, hand soldering and output harness remain unqualified.
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
