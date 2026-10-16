# Big Modular instructions

Read AGENTS.md and README.md. Work only in this task's isolated Big Modular root;
Bread Modular is read-only and outside scope. No commits, merges, pushes, purchases,
vendor uploads or manufacturing exports without explicit authorization.

## Current authorization

V1 electrical simplification supersedes prototype power-inhibit instructions.
Independent TPS26600 9 V-required UV/OV protection, CH224A fixed9V, TPS54302 x2,
TPS65131 +/-12V, J7 physical output and one red D10 final-P5 LED remain.
SW1 is eFuse shutdown/retry, not a debug input. No AUX/MCU/sensing/J8/J2/JP1.
No artificial qualification inhibit. Engineering limits are in docs/engineering.md.

Do not change PCB placement, sync or copper in this stage. USB/button/LED relocation
to the top is deferred to the next mechanical owner. Both board files are preserved.
Do not reuse retired D11/D12 refs (tools/interface_contract.py).

## Required tooling

Read canonical opt/kicad-tools/skills/kicad-workflow/SKILL.md before KiCad work;
for sourcing also read skills/jlcpcb-assembly/SKILL.md, jlcpcb/ASSEMBLY.md and
jlcpcb/README.md there. Read actual CLI help; use the common toolkit first.
Use tools/kicad-project.json to select the carrier and hierarchical root explicitly.
New candidates/reports go to ignored research/, never implicit source overwrites.
No advisors or other models unless requested. No routing without authorization.

Source-of-truth: tools/electrical_design.py, build_project.py, render_schematic.py.
Keep useful mechanical builders/verifiers and their regression inputs: they describe
preserved, unsynchronized PCB reservations, not current electrical parity.
Build/check instructions: docs/build.md. Native ERC/parity findings must be retained;
no rule exclusions, fake power flags or weakened tests to obtain a pass. Passing ERC
is not layout, thermal, safety or manufacturing qualification.

Sourcing evidence requires exact C-code/MPN/rating/pad mapping and bounded strict-live
lookups. Basic and Economy eligibility are independent for assembled R/C; no silent
policy relaxation. Pinned catalog facts are dated evidence, not allocation/current
stock promises. No shared-suite KICAD_JLCPCB_INTEGRATION opt-in on real boards.
