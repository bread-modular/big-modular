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
| `modules/audio-out/` | 4HP ±12 V pure-analog stereo out: 2 x TS in (IN R normalled to IN L; OPA1678 buffers) -> TRS consumer line out + TRS headphone out (MC33178, RV09 50k volume per ear) (Bread Modular `base` based) | S3 schematic (IN R normalled to IN L, no MONO jumper, unshrouded 10-pin power header, 10-pin cable) + R4 routed carrier (thermal-relief GND pours) (IN L, IN R, LINE, VOL L, VOL R, PHONES); 4HP panels; JLCPCB export in `modules/audio-out/jlcpcb/`, not supplier-accepted, not built |
| `modules/vca-mix/` | VCA-MIX, 6HP: 3 x vactrol VCA (Bread Modular V2CA, no CURVE; Bread Modular LOW/SVF vactrol driver; IN/CV/OUT per channel, CV unpatched = open) + per-channel volume after the VCA (OUT post-volume) + MIX out (Bread Modular imix style), buffered inputs/CV, 1 W output resistors, ±12 V, 10 x TL072 | S4 schematic + P4 placement + 6HP panels; R1 routed carrier, final (TraceMaker + cleanup, 0 unconnected; the 9 vactrol/pot stacking findings are user-approved DRC exclusions, D10; copied into `hardware/` past the shared gate, which still counts them, D14, user-verified manually; vactrol build notes on silk); JLCPCB export in `modules/vca-mix/jlcpcb/`, not supplier-accepted, not built |
| `modules/16bit/` | 16bit, 6HP: RP2350A + W25Q128 flash + APS6404L PSRAM, PT8211 I2S DAC -> TL074 ±5 V outs, MIDI in (NPN, JP1), 2 x CV in with attenuators, 2 knobs, MODE button + LED, USB-C data, 4-layer (Bread Modular `16bit` based) | S3 schematic + S5 placement + R1 routed carrier (TraceMaker + hand finish, rev1 reviewed); **needs via-in-pad fill (POFV) at the fab**; 6HP panel; no sourcing or export yet |

Canonical sources are `modules/usb-power/hardware/usb-power.kicad_{pro,sch,pcb}`
plus `modules/usb-power/panels/front-pcb/usb-power-panel.kicad_{pro,pcb}`. Read `modules/usb-power/Code.md` before
any hardware work. The MIDI module's sources are
`modules/midi/hardware/v1/midi.kicad_{pro,sch,pcb}` (V1) and
`modules/midi/hardware/v2/midi.kicad_{pro,sch,pcb}` (V2), plus the shared
`modules/midi/panels/front-pcb/midi-panel.kicad_{pro,pcb}`; their shared-tool
profiles are `modules/midi/tools/v1|v2/kicad-project.json`. Read
`modules/midi/Code.md` first. The VCA-MIX module's sources are
`modules/vca-mix/hardware/vca-mix.kicad_{pro,sch,pcb}` plus
`modules/vca-mix/panels/front-pcb/vca-mix-panel.kicad_{pro,pcb}`; read
`modules/vca-mix/Code.md` first.

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

## Routing with autorouters

Autorouters may route a carrier (user direction, 2026-10-20). Run **both Freerouting
and TraceMaker** on the same frozen placement, rules and GND pours, compare the
results, pick the best and improve it; don't settle for whichever finishes first.

- **Freerouting**: the repo-pinned runtime via `opt/kicad-routing/` (`route doctor`,
  `prepare-runtime` needs an explicit download opt-in). If its supported subset
  refuses the board, the same pinned JAR may be driven through native DSN export /
  SES import. Pass flags that turn its analytics off.
- **TraceMaker**: the shared controller and recipe in `opt/kicad-tools/tracemaker/`
  and `opt/kicad-tools/HYBRID_ROUTING.md`, or a hash-verified upstream release run on
  a research copy (`--no-kb --no-gpu`; `--soft-zones` with the pours present worked
  best on modules/vca-mix).
- Runtimes, builds and driver scripts stay outside the repository or in the module's
  ignored `research/`. Don't add router tooling.
- Give routers only **tighter** rules than the native ones (track widths, Power net
  class, clearance margin, edge inset). Never lower a native rule or accept
  below-rule neck-downs.
- **Compare** with full native DRC + parity: unrouted, DRC findings beyond the
  baseline, via count, track length, below-rule segments, GND-pour continuity and the
  critical analog/power paths (inspect renders).
- **Improve** the pick with explicit, recorded cleanup edits, e.g. removing redundant
  rail legs or freeing crowded pads.
- **Freeze and promote**: freeze the copper as module data and emit it with
  `tools/route_plan.py` as shared `pcb plan/apply/promote` ops (as modules/vca-mix).
  Raw router output never goes into `hardware/`. Router success is not acceptance: the
  shared gates still apply in full.
- Record the comparison and the choice in the module's `docs/research.md`.

### Learnings (modules/16bit, 4-layer RP2350 QFN-60 at 0.4 mm pitch)

- **Run routers detached and never wait inside a turn.** Agent turns have a 1-hour
  watchdog, and processes started from a tool shell die when the turn ends. Start
  every run with `systemd-run --user --unit <name> ...` and a router time limit
  (`--time`), end the turn, and collect results in the next turn with
  `systemctl --user is-active <name>`.
- **TraceMaker is the primary router for fine-pitch MCU boards.** Freerouting (40
  passes) stalled with its unrouted count swinging between 77 and 148; TraceMaker
  routed 226/234 on its first run. Still run Freerouting for the comparison.
- **Protect the planes in the router flags**: `--no-tracks-on In1.Cu` keeps the
  GND plane solid (without it TraceMaker routed on In1 and split the plane),
  `--layer-cost In2.Cu=3..6` keeps signals mostly off the power plane, and
  `--no-neck-nets <power nets>` stops thin power neck-downs. It does not widen rails
  into 0.2 mm QFN pads: on 16bit +1V1, VREG_AVDD and VREG_LX came out 0.2 mm end to
  end, so report widths per net, not per class (rev1 review).
- **Run a portfolio**, not one run: results are time-limited and not reproducible, so
  launch 3 variants (`--seed`, `--first-nets` for the boxed-in nets such as crystal,
  QSPI, `+1V1`, `--via-cost-mm`, `--global`) and pick by the comparison metrics.
- **Finish the last opens by hand, not with more router rounds.** Pick the best run
  (fewest opens, DRC 0, whole planes) and stop there: a box rip-up around the MCU plus
  a re-route made it worse (11-13 opens vs 4). `tracemaker escape`/`stuck_report` names
  the pins with no 0.2 mm channel; for those, rip only the few nets next to the pin
  (whole nets, never a box), add an explicit escape stub + via (check clearances by
  hand), and route from that via. `tracemaker session` routes the easy rest; give it
  hints `{"version": 1, "layers": {"no_tracks": ["In1.Cu"], "cost": {"In2.Cu": 4}}}`,
  otherwise it puts tracks on the GND plane. A small research-only grid router (exact
  point-in-polygon obstacles, no PIL rasterising) works for long hops; adjacent pins
  whose nets must cross (crystal XIN/XOUT next to DVDD) need a hand-planned escape
  per pin (one inward, one outward). Re-run full native DRC after every edit,
  including snapping/cleanup passes.
- **Watch the +3V3 plane**: In2 signal hops can fence off a plane island; check the
  fill islands and move the fencing signal to F/B. Count plane pieces from the filled
  polygons and report spoke-tied fragments separately (16bit's In1 GND has two 2.6 mm²
  pieces between the J6 GND pins; "one piece" was an overclaim).
- **Count vias in pads before you pick a run** (rev1 review): TraceMaker centres vias in
  SMD pads. 16bit R1 ended with 132 (123 board vias, mostly in 0402 pads, plus the U1 EP
  array), so it needs POFV fill at the fab. Moving them out afterwards is a re-route. Make
  in-pad vias a comparison metric, and decide POFV vs dogbones before routing.
- **Clean before freezing**: drop zero-length/duplicate/dangling segments, centre
  track ends on vias, collapse sub-0.1 mm via stubs; router stubs that wander inside a
  pad are trimmed at the pad centre (pads are convex). Also look for what that pass
  missed on 16bit R1: a second copy of a track 0.065 mm beside the first, spurs and
  hairpins under 20°, and tees that run back along their parent before joining it.
- **GPU builds don't help**: the upstream Linux release is CPU-only. A CUDA build
  (CUDA 12.4 + GCC 13, PTX JIT on sm_120) works, but routing time is dominated by
  CPU path searches, so it was no faster or better.
- **Shared `pcb plan` caps a plan at 256 ops**: a full board needs `route_plan.py` to
  split the copper into stages of whole nets. A stale root-sheet UUID in the
  `.kicad_pro` makes the shared planner refuse the project. Intermediate stages need
  `pcb plan --allow-draft-opens` (opens remain until the last stage; plan the last
  without it). Use absolute paths in stage driver scripts: a relative `..` path broke
  once its parent candidate dir was deleted, and a stale board was re-promoted.

## Fabrication outputs

`modules/usb-power/jlcpcb/` is the sole shipping-set location; `production/` is
retired, not an active archive. Read `modules/usb-power/jlcpcb/README.md`
(shared-tool export/CAM commands and promotion gates) before release work. Any
native electrical/PCB repair and new export belongs to a separate authorized
task; never hand-edit generated files.
