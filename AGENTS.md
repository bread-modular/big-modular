# Agent entry point

This repository is a monorepo of Eurorack modules built with shared KiCad tooling.

## Layout

- `modules/<name>/` — one self-contained hardware project per module. It owns its
  KiCad sources (`hardware/`), `docs/`, module tooling (`tools/`), `tests/` and
  upload-ready `jlcpcb/` outputs.
- `opt/` — shared, module-independent tooling (`opt/kicad-tools/` native KiCad
  checks, PCB/schematic edits, JLCPCB export/assembly; `opt/kicad-routing/` optional
  router facade). It stays at the repository root. Never move it into a module and
  never fork or duplicate it per module.
- `modules/<name>/AGENTS.md` and `modules/<name>/Code.md` — module-specific
  circuit/release contract. Read them before touching that module.

| Module | Description | Release |
| --- | --- | --- |
| `modules/usb-power/` | USB-C PD input → protected 9V, dual TPS54302 bucks, TPS65131 raw ±13.5V, TPS7A4700/TPS7A3301 quiet ±12V, +5V | LDO-R1 source; recovered exports STALE |

Current module: **usb-power** (USB-C PD Eurorack power supply, LDO-R1 release).
Canonical sources are `modules/usb-power/hardware/usb-power.kicad_{pro,sch,pcb}`
plus `usb-power-panel.kicad_{pro,pcb}`. Read `modules/usb-power/Code.md` before any
hardware work.

## Tools

For KiCad read `opt/kicad-tools/skills/kicad-workflow/SKILL.md`; for
sourcing/assembly also read `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`
and the jlcpcb docs. Common-tool-first; inspect actual CLI help. Do not strip
dependencies or weaken rules.

Quick check:

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config modules/usb-power/tools/kicad-project.json
python3 -B -m unittest discover -s modules/usb-power/tests -v
```

## Workspace rules

Work only in this isolated workspace. No advisor/delegation, commits, merges,
pushes, main writes, GUI interaction, orders or vendor uploads. Supervisor reviews
and merges verified work; the assistant does not merge. No access to other
workspaces for recovery; prior workspace028 and Bread Modular are read-only. No
external project changes. No arbitrary raw-rail/current guarantee changes.

## Required workflow

Read canonical `opt/kicad-tools` skills and relevant CLI help; common tools first.
Use `modules/usb-power/tools/kicad-project.json` for the carrier and hierarchical
root. New candidates and raw reports go in the module's `research/`; accepted
fabrication outputs in the module's `jlcpcb/`. Reuse `tools/release_hro.py`/native
KiCad/common staging/CAM pipeline, not a new exporter/router.
Keep generators/BOM/native fields coherent; native schematic presentation owns
placement/wires and accepted native PCB owns routing. Explicit candidate edits only.

Full native ERC/DRC includes warnings/exclusions/opens/parity; independent exact
ref/pin/net/NC/field parity and mechanics are mandatory. No ignored rules, exclusions,
fake power flags or weakened assertions. Update accepted routing baselines only for
independently inspected intentional changes; historical release SHA integrity remains.
Typical manufacturer data plus prototype screening is not guaranteed performance.
Source/sourcing and Basic/Economy gates remain distinct; no stock claims without evidence.

## Fabrication outputs

`modules/usb-power/jlcpcb/` is the sole shipping-set location; `production/` is
retired, not an active archive. The recovered Git export snapshot is STALE for the
migrated project/tool paths. It was not regenerated during recovery.

Read `modules/usb-power/docs/migration-recovery.md` (recovery evidence and remaining
release gates) and `modules/usb-power/jlcpcb/README.md` (shared-tool export/CAM
commands and promotion gates). Any native electrical/PCB repair and new export
belongs to Astra's separate authorized task; never hand-edit generated files or
historical manifests.
