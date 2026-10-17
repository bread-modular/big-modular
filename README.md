# Big Modular

A collection of Eurorack modules built with shared KiCad tooling.

## Modules

| Module | Description | Release |
| --- | --- | --- |
| [`usb-power`](modules/usb-power/) | USB-C PD input → protected 9V, dual TPS54302 bucks, TPS65131 raw ±13.5V, TPS7A4700/TPS7A3301 quiet ±12V, +5V | LDO-R1 source; recovered exports STALE |

Each module is self-contained under `modules/<name>/`:

```text
modules/usb-power/
  hardware/     KiCad project (usb-power.kicad_{pro,sch,pcb}, panel, local libs)
  docs/         design, fabrication and evidence notes
  tools/        module generators/checkers
  tests/        module regression tests
  jlcpcb/       recovered Gerber/BOM/CPL snapshot (STALE until re-export)
```

## Common tooling

`opt/` holds shared, module-independent tooling and must not be copied into modules:

- `opt/kicad-tools/` — native KiCad checks, PCB/schematic edits, JLCPCB export/assembly
- `opt/kicad-routing/` — optional router facade

Read `opt/kicad-tools/skills/kicad-workflow/SKILL.md` and
`opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md` before KiCad or sourcing work.

## Quick check

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config modules/usb-power/tools/kicad-project.json
python3 -B -m unittest discover -s modules/usb-power/tests -v
```

Recovery evidence and remaining release gates: [`modules/usb-power/docs/migration-recovery.md`](modules/usb-power/docs/migration-recovery.md).
