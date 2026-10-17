# Agent entry point

This repository is a monorepo of Eurorack modules. Read `Code.md` first.

## Layout

- `modules/<name>/` — one self-contained hardware project per module
  (`hardware/`, `docs/`, `tools/`, `tests/`, `jlcpcb/`).
- `opt/` — shared, module-independent tooling. Never move it into a module and
  never fork it per module.
- `modules/usb-power/AGENTS.md` and `modules/usb-power/Code.md` — module-specific
  circuit/release contract. Read them before touching that module.

Current module: **usb-power** (USB-C PD Eurorack power supply, LDO-R1 release).
Canonical sources are `modules/usb-power/hardware/usb-power.kicad_{pro,sch,pcb}`
plus `usb-power-panel.kicad_{pro,pcb}`.

## Tools

For KiCad read `opt/kicad-tools/skills/kicad-workflow/SKILL.md`; for
sourcing/assembly also read `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`
and the jlcpcb docs. Common-tool-first; inspect actual CLI help. Do not strip
dependencies or weaken rules.

## Workspace rules

No advisor/delegation, commit, merge, push, main writes, GUI, orders or vendor
uploads. Supervisor reviews/merges the workspace; the assistant does not merge.
No access to other workspaces for recovery. No arbitrary raw-rail/current guarantee
changes. Read `modules/usb-power/docs/migration-recovery.md`; recovered `jlcpcb/`
exports are STALE for migrated inputs. No active `production/` archive.
