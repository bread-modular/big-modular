# Agent entry point

This repository is a monorepo of Eurorack modules built with shared KiCad
tooling.

## Layout

- `modules/<name>/` — one self-contained hardware project per module. It owns
  its KiCad sources (`hardware/`), `docs/`, module tooling (`tools/`) and
  upload-ready `jlcpcb/` outputs.
- `opt/` — shared, module-independent tooling (`opt/kicad-tools/` native KiCad
  checks, PCB/schematic edits, JLCPCB export/assembly; `opt/kicad-routing/`
  optional router facade). It stays at the repository root. Never move it into a
  module and never fork or duplicate it per module.
- `opt/updi-programmer/` — USB-C UPDI programmer (jtag2updi on ATtiny1616) for
  the modules' UPDI chips: generated KiCad project, firmware and README.
  `opt/attiny1616-tools/` holds the shared ATtiny1616 compile/flash scripts.
- `modules/<name>/AGENTS.md` and `modules/<name>/Code.md` — module-specific
  circuit/release contract. Read them before touching that module.

| Module | Description | Release |
| --- | --- | --- |
| `modules/usb-power/` | USB-C PD 9 V input, TPS26600 protection, TPS55340 boost, TPS54302 inverting buck-boost, TPS7A4700/TPS7A3301 ±12 V, +5 V | SR2 schematic + 084 PCB source accepted; not released |
| `modules/midi/` | 4HP TRS MIDI in (TRS A/B jumper header, no opto) -> ATtiny1616 -> 8 x TS modular MIDI outs + LEDs, +12 V -> 5 V LDO (Bread Modular `midi` based). Two versions: `hardware/v1/` (BM V1 direct input, unprotected) and `hardware/v2/` (±12 V mis-patch protected NPN input with a JP2 debug bypass, clamped outputs, +5V shunt) | V1.0 (S4/R5) and V2.0 (S3/R3) routed carriers + shared 4HP panels; JLCPCB exports in `modules/midi/jlcpcb/v1/` and `jlcpcb/v2/`, not supplier-accepted |
| `modules/audio-out/` | 4HP ±12 V pure-analog stereo out: 2 x TS in (IN R normalled to IN L; OPA1678 buffers) -> TRS consumer line out + TRS headphone out (MC33178, RV09 50k volume per ear) (Bread Modular `base` based) | S3 schematic (IN R normalled to IN L, no MONO jumper, unshrouded 10-pin power header, 10-pin cable) + R3 routed carrier (IN L, IN R, LINE, VOL L, VOL R, PHONES); 4HP panels; JLCPCB export in `modules/audio-out/jlcpcb/`, not supplier-accepted, not built |

Canonical sources are `modules/usb-power/hardware/usb-power.kicad_{pro,sch,pcb}`
plus `modules/usb-power/panels/front-pcb/usb-power-panel.kicad_{pro,pcb}`. Read `modules/usb-power/Code.md` before
any hardware work. The MIDI module's sources are
`modules/midi/hardware/v1/midi.kicad_{pro,sch,pcb}` (V1) and
`modules/midi/hardware/v2/midi.kicad_{pro,sch,pcb}` (V2), plus the shared
`modules/midi/panels/front-pcb/midi-panel.kicad_{pro,pcb}`; their shared-tool
profiles are `modules/midi/tools/v1|v2/kicad-project.json`. Read
`modules/midi/Code.md` first.

## Tools

For KiCad read `opt/kicad-tools/skills/kicad-workflow/SKILL.md`; for
sourcing/assembly also read `opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`
and the jlcpcb docs. Common-tool-first; inspect actual CLI help. Do not strip
dependencies or weaken rules.

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config modules/usb-power/tools/kicad-project.json
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power/tools/kicad-project.json --reports <new-dir>
```

## Workspace rules

Work only in this isolated workspace. No advisor/delegation, commits, merges,
pushes, main writes, GUI interaction, orders or vendor uploads. Supervisor
reviews and merges verified work; the assistant does not merge. No access to
other workspaces for recovery; Bread Modular is read-only. No external project
changes. No arbitrary raw-rail/current guarantee changes.

## Required workflow

Read canonical `opt/kicad-tools` skills and relevant CLI help; common tools
first. Use `modules/usb-power/tools/kicad-project.json` for the carrier and
hierarchical root. New candidates and raw reports go in the module's ignored
`research/`; accepted fabrication outputs in the module's `jlcpcb/`. Reuse
shared native checks/export; do not add a new exporter or router.

Keep generators/BOM/native fields coherent; native schematic presentation owns
placement/wires and accepted native PCB owns routing. Explicit candidate edits
only.

Full native ERC/DRC includes warnings/exclusions/opens/parity; independent exact
ref/pin/net/NC/field parity and mechanics are required. No ignored rules,
exclusions, fake power flags or weakened assertions. Update accepted routing
baselines only for independently inspected intentional changes. Manufacturer
data plus prototype screening is not guaranteed performance. Source/sourcing
and Basic/Economy gates remain distinct; no stock claims without evidence.

## Fabrication outputs

`modules/usb-power/jlcpcb/` is the sole shipping-set location; `production/` is
retired, not an active archive. Read `modules/usb-power/jlcpcb/README.md`
(shared-tool export/CAM commands and promotion gates) before release work. Any
native electrical/PCB repair and new export belongs to a separate authorized
task; never hand-edit generated files.
