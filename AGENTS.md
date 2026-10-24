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
| `modules/16bit/` | 16bit, 6HP: RP2350A + W25Q128 flash + APS6404L PSRAM, PT8211 I2S DAC -> TL074 ±5 V outs, MIDI in (NPN, JP1), 2 x CV in with attenuators, 2 knobs, MODE button + LED, USB-C data, 4-layer (Bread Modular `16bit` based) | S3 schematic; R2 manual divide-and-conquer routing done (DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, plain tented, no POFV; B silk BOOT/RESET/JP1 labels); 6HP panel; JLCPCB export in `modules/16bit/jlcpcb/` (bottom Economic, TM8211 for PT8211, cjiang L1, user-stocked Adafruit 4677 PSRAM), not supplier-accepted, not built |
| `modules/low/` | LOW, 6HP: Bread Modular MCO (ATtiny1616 dual square, DETUNE/MIX) + LOW (two-vactrol LPG, CUTOFF) at 3.3 V; 8bit MIDI in; AUDIO and CV bypass inputs (10 Vpp / 0..5 V mapped to 0..3.3 V) normalled via a TS5A23157 to the MCO square mix and velocity DAC; TL072 ±12 V out | S3 schematic (ERC 0, signal nets wired, LCSC fields; R17/R18 47k/100k for Basic) + R3 manual divide-and-conquer routing, 2-layer, SMD >= 2 mm from pot/jack pads (closest U6 2.20 mm), 1 mm edge keep-out (copper-edge rule 1.0 mm; RV1/RV2 courtyards 0.82 mm, user-accepted) (KiCad DRC 0 / unconnected 0 / parity 0; the 3 U5-under-CUTOFF stacking items are user-approved DRC exclusions, still counted by the shared gate; no vias in SMD pads); JLCPCB export in `modules/low/jlcpcb/` (bottom Economic, all R/C Basic), not supplier-accepted, not built |
| `modules/acid/` | ACID, 8HP: Bread Modular MCO + ENV on one ATtiny1616 (3 envelope models + LEDs, REC button), BM SVF (two vactrols on B, RES 500k), all at 3.3 V; 8bit MIDI in; AUDIO and CV bypass inputs (10 Vpp / 0..5 V mapped to 0..3.3 V) normalled via a TS5A23157 to the MCO mix and the DAC envelope; no DRIVE: LP / HP / BP outs, each one TL072 stage (x11.1, ~10 Vpp ceiling) + protected 0..5 V envelope CV out | S2 schematic (ERC 0, every signal net wired; 0.5 W 1206 1k = ROHM ESR18) + R1 manual divide-and-conquer routing done, 4-layer (vactrols under ATTACK/RELEASE, 22 stacking items user-approved DRC exclusions, still counted by the shared gate; KiCad DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, In1/In2 planes one piece; B silk UPDI + MIDI JP1 labels); 8HP panel; JLCPCB export in `modules/acid/jlcpcb/` (bottom Economic, 92 parts), not supplier-accepted, not built |
| `modules/32bit/` | 32bit, 6HP: ESP32-S3-WROOM-1U-N16R8 + ES8388 codec, MIDI in (NPN, JP1), 2 x audio in (TL074, no normal), 2 x CV in with attenuators, TL072 ±5 V outs, MODE button + LED, USB-C data + BOOT/RESET, 4-layer (Bread Modular `32bit-5v` based) | S2 schematic (ERC 0; R1 layout pin changes logged in `docs/firmware-pins.md`) + R2 manual divide-and-conquer routing (R1 + 2 mm hand-solder clearance, closest 2.02 mm except user-accepted R5/C27/R55/C46 at 1.33-1.75 mm; DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, In1/In2 planes one piece; B silk MIDI JP1 labels); 6HP panel; R2 JLCPCB export in `modules/32bit/jlcpcb/` (U1 ESP32 module Standard PCBA, user choice), not supplier-accepted, not built |
| `modules/4mix/` | 4MIX, 18HP: Bread Modular 4mix (no overdrive) on ±12 V: audio only, every input AC-coupled; 4 channels (IN jack on top, SEND A, SEND B, VOL), 2 post-fader sends + 2 returns, top line SEND A, SEND B, RTN A, RTN B, MAIN, OUT (sends top left, return levels below their jacks); big-knob space on each channel VOL; 2x3 EXP IN (top left) / EXP OUT (top right) headers and power (bottom right) on the back; 2 x 10 mm M3 F-F hex standoffs MS1/MS2 hold the carrier bottom to the panel, 9 x TL072 | S2 hierarchical schematic (channel sheet x 4, ERC 0) + P6 placement (user hand placement, tidied; M3x10 standoffs MS1/MS2, mechanical footprints) + R1 manual divide-and-conquer routing, 4-layer (In1 GND, In2 +12V), all SMD on B (DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, SMD >= 2 mm from pot/jack pads, closest 2.27 mm); 18HP panel fit study; JLCPCB export in `modules/4mix/jlcpcb/` (bottom Economic, all R/C Basic except the 1 W 2512 output resistors), not supplier-accepted, not built |
| `modules/hats/` | HATS, 6HP: Bread Modular NOISE (blue noise, NOISE TONE / BLUE TONE) -> HIHAT (CUTOFF, DECAY, vactrol VCA), two ATtiny1616 (BM pin maps) on one MIDI RX; NOISE IN normalled via a TS5A23157 to the internal blue noise; REC button to both MCUs (PC2) + REC LED (HIHAT PC3); TL072 AUDIO out x3 + HAT CV out 0..5 V with ENV LED, ±12 V | S2 schematic (ERC 0, nets wired, VMID_H label-joined) + R1 manual divide-and-conquer routing, 4-layer (In1 GND, In2 +3V3), all SMD on B (KiCad DRC 0 / unconnected 0 / parity 0; SW1 REC button inside the U7 vactrol outline: 4 user-approved DRC exclusions, still counted by the shared gate; no vias in SMD pads; SMD >= 2 mm from pot/jack pads, closest 2.02 mm; RV1-RV4 courtyards 0.77 mm, user-accepted); 6HP panel; JLCPCB export in `modules/hats/jlcpcb/` (bottom Economic, 88 parts), not supplier-accepted, not built |

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

## Routing: manual, divide and conquer (no autorouters)

User direction, 2026-10-21. It replaces the 2026-10-20 autorouter direction: the
16bit R1 TraceMaker copper needed 123 in-pad vias (POFV) and was stripped and
re-routed this way instead.

- **No autorouters.** Do not run Freerouting, TraceMaker (`route`, `tracemaker run`,
  `tracemaker session`) or any other full-board/bulk router, and do not hand them the
  board as a fallback. A small path-finding helper for **one connection at a time** is
  fine, as long as you check and accept each path yourself.
- **No vias in SMD pads.** Fan out with a short dogbone track to a via clear of the pad
  copper and its mask opening. The only exception is a footprint's own exposed-pad
  thermal vias (e.g. RP2350 EP). Check every via against every SMD pad after each batch;
  never propose POFV as the fix.
- **Work straight on the board** (`modules/<name>/hardware/*.kicad_pcb`), not on a
  research copy, and **update the board after every batch** so the user can reload it
  in KiCad and follow along. Back up the board to `/tmp/` before each round; DRC reports
  go in the module's ignored `research/`.

### Divide and conquer

1. **Clear the board first if asked:** strip tracks/vias, keep footprints and zone
   outlines, then park the SMD parts in a grid off the board edge so they can be
   placed group by group.
2. **Set up the layers before routing.** 4-layer: F.Cu signal / In1 solid GND /
   In2 main power plane (+3V3) / B.Cu signal, plus a Power net class. No tracks on In1.
   In2 only for short power hops when F/B are blocked, and check that the plane stays
   one piece afterwards.
3. **Place and route one functional group at a time**, near its connector: e.g. power
   entry + regulators by the power header, output amps between the output jacks, USB
   at its port, MIDI input at its jack, CV buffers by their pots, then the MCU with its
   memories, DAC and decoupling. Keep the space reserved for the MCU empty until it's
   that group's turn.
4. **Route a few traces per batch** (one net or a handful of local links), write them
   to the board, then run full native DRC + parity. Fix every new finding before the
   next batch. Report what the batch added and what is still open.
5. **Leave cross-board links until both ends are placed** (MCU pins, rails that cross
   the middle), and say so in the report instead of forcing a long detour.
6. **Stop and ask** when a choice needs the user: moving a fixed jack/pot or a part the
   user placed, ripping up earlier groups, or a schematic change such as a pin swap.
   Respect parts and copper the user routed by hand; only move them with a reason
   you report.
7. **Commit only when the user asks**, at the end of a group.

### 1 mm board-edge keep-out (must)

User direction, 2026-10-22. Applies to every carrier board, routed or not.

- **Nothing within 1 mm of the board edge**: no tracks, vias, pads, zone copper, and no
  component courtyards (SMD and THT) closer than 1.0 mm to `Edge.Cuts`.
- Set the board's **copper-to-edge clearance to 1.0 mm**
  (`min_copper_edge_clearance` in the `.kicad_pro`) so native DRC enforces it for copper
  and the pours pull back; refill zones and save after changing it.
- DRC does not check courtyards against the edge: measure them (courtyard bounding box
  incl. line width) after every placement batch and report any under 1 mm.
- If a fixed part (panel-located pot/jack) can't meet it, stop and ask; don't move it
  silently.

### 2 mm hand-solder clearance around pots and jacks

User direction, 2026-10-22 (was 3 mm on LOW R2, relaxed). Applies to every carrier board.

- **Every SMD pad >= 2.0 mm from every hand-soldered pot and jack pad**, mounting lugs
  included, measured copper edge to copper edge, so the iron has room.
- DRC does not check it: measure it after every placement batch and report the closest
  pads. The 1 mm edge keep-out wins where both can't hold; report the conflict.

### Routing rules learned on modules/16bit

- **Short critical paths first**: regulator input caps within 2-3 mm, decoupling cap
  at its pin with its own GND via, memories right beside the MCU so QSPI runs with no
  vias, USB D+/D- side by side on one layer with vias only at the port and the MCU.
- **Use F.Cu when only through-hole parts sit there**: it's the free layer for long
  runs and rail feeds. Hop with a via pair placed clear of the pads.
- **Heat**: a linear regulator dropping ~0.5 W gets a tab patch on F and B tied by
  thermal vias beside (not in) the tab.
- **Check after every edit, cleanup passes included**: native DRC + parity, vias in SMD
  pads, tracks on In1, plane pieces counted from the filled polygons (report small
  spoke-tied fragments separately), and inspect a render of the area.
- **Clean as you go**: no zero-length/duplicate/dangling segments, track ends centred
  on vias and pads, coordinates on a round 0.05/0.1 mm grid.
- **Shared `pcb plan` caps a plan at 256 ops** if you freeze copper as plan ops: split
  into stages of whole nets; intermediate stages need `--allow-draft-opens`.

## Fabrication outputs

`modules/usb-power/jlcpcb/` is the sole shipping-set location; `production/` is
retired, not an active archive. Read `modules/usb-power/jlcpcb/README.md`
(shared-tool export/CAM commands and promotion gates) before release work. Any
native electrical/PCB repair and new export belongs to a separate authorized
task; never hand-edit generated files.
