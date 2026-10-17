# Big Modular instructions

Read `AGENTS.md` and `README.md`. Work only in this isolated workspace. No advisor,
delegation, commits, merges, pushes, main writes, orders/uploads or GUI interaction.
Supervisor reviews and merges verified work. Prior workspace028 and Bread Modular
are read-only. No external project changes.

## Repository layout

This is a multi-module repository. Each module lives under `modules/<name>/` and
owns its KiCad sources, docs, module tooling, tests and upload-ready `jlcpcb/` outputs. `opt/` is shared common tooling and stays at the
repository root — do not duplicate it inside modules.

Module-specific circuit/release contracts are in `modules/<name>/Code.md` and
`modules/<name>/AGENTS.md`. For the current module (`usb-power`) read
`modules/usb-power/Code.md` before any hardware work.

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

FAB files belong in `modules/<name>/jlcpcb/` and are generated only through the
common KiCad/JLCPCB tools. For the current board layout the working invocation is:

```sh
python3 opt/kicad-tools/jlcpcb/export.py modules/usb-power/hardware \
  --board usb-power.kicad_pcb --include-through-hole --require-part-numbers \
  -o modules/usb-power/jlcpcb/usb-power --overwrite
python3 opt/kicad-tools/jlcpcb/export.py modules/usb-power/hardware \
  --board usb-power-panel.kicad_pcb --pcb-only \
  -o modules/usb-power/jlcpcb/usb-power-panel --overwrite
```

See `modules/usb-power/jlcpcb/README.md` for the mirror/verification steps.
`jlcpcb/` is the upload set; do not hand-edit generated files.
