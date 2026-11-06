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
  `opt/attiny1616-tools/` holds the shared ATtiny1616 compile/flash scripts and
  shared sketch libraries in `lib/` (e.g. `lib/CvRecorder/`), symlinked into
  each sketch folder.
- `opt/esp32-tools/` — shared ESP32-S3 ESP-IDF setup/compile/flash scripts (reuse an
  installed `~/esp/esp-idf`), wrapped by `modules/32bit/firmware/`.
- `opt/rp2350-tools/` — shared RP2350 Pico SDK setup/compile/flash scripts (reuse an
  installed `~/.breadmodular` Pico SDK 2.1.1 / ARM GCC 14.2 / picotool), wrapped by
  `modules/16bit/firmware/`.
- `modules/<name>/AGENTS.md` and `modules/<name>/Code.md` — module-specific
  circuit/release contract. Read them before touching that module.

| Module | Description | Release |
| --- | --- | --- |
| `modules/usb-power/` | USB-C PD 9 V input, TPS26600 protection, TPS55340 boost, TPS54302 inverting buck-boost, TPS7A4700/TPS7A3301 ±12 V, +5 V | SR2 schematic + 084 PCB source accepted; not released |
| `modules/usb-power-45w/` | USB-C PD 15 V / 3 A (CH224A, R1 56k) -> TPS16630 main eFuse (precision UVLO, OVP coordinated with D24 SMBJ20A) -> TPS552892-Q1 +12 V buck-boost and LMR38020 -12 V inverting converter (own-input enable, sequenced after +12 V); ±12 V only, two 10-pin outputs J2/J3; always-on STARTED one-shot, fault latch and RESET; MAIN LED only; one 4-layer carrier, all parts on F, 4HP panel | **S9.3-10P / R1** schematic + **manually routed** board (`hardware/usb-power-45w.kicad_pro`): two 10-pin IDC outputs J2/J3 (Wurth 61201021621); FB-injection soft starts on both converters start it from a strict 3.00 A source in one attempt (netlist plant peak 2.955 A, 0 U5 drop-outs); 185 refs / 84 nets, ERC 0, DRC 0 / 0 warnings / parity 0 / **0 unconnected**; In1 one-piece GND, two approved In2 hops, test points on B; routing contract in native DRC (8 net classes, 22 `S92_*` rules, 15 rule areas), no via-in-pad. Prototype targets +12 V 2.4 A / -12 V 0.8 A, <=33 W. Open: `tools/check_s8_board.py` copper/thermal screen FAIL (U12.14-C52.1, D25-D24, TP22/TP23 pair, R116.1 in RA_AGND_ISLAND, min widths, U2/R109/D10 thermal copper, D1 GND vias), width/pour-neck enforcement. Record `docs/routing/checkpoint.json` + `docs/routing/README.md`; review `docs/design.md`. No fab export. |
| `modules/midi/` | 4HP TRS MIDI in (TRS A/B jumper header, no opto) -> ATtiny1616 -> 8 x TS modular MIDI outs + LEDs, +12 V -> 5 V LDO (Bread Modular `midi` based). Two versions: `hardware/v1/` (BM V1 direct input, unprotected) and `hardware/v2/` (±12 V mis-patch protected NPN input with a JP2 debug bypass, clamped outputs, +5V shunt) | V1.0 (S4/R5) and V2.0 (S3/R3) routed carriers + shared 4HP panels; JLCPCB exports in `modules/midi/jlcpcb/v1/` and `jlcpcb/v2/`, not supplier-accepted |
| `modules/audio-out/` | 4HP ±12 V pure-analog stereo out: 2 x TS in (IN R normalled to IN L; OPA1678 buffers) -> TRS consumer line out + TRS headphone out (MC33178, RV09 50k volume per ear) (Bread Modular `base` based) | S3 schematic (IN R normalled to IN L, no MONO jumper, unshrouded 10-pin power header, 10-pin cable) + R4 routed carrier (thermal-relief GND pours) (IN L, IN R, LINE, VOL L, VOL R, PHONES); 4HP panels; JLCPCB export in `modules/audio-out/jlcpcb/`, not supplier-accepted, not built |
| `modules/vca-mix/` | VCA-MIX, 6HP: 3 x vactrol VCA (Bread Modular V2CA, no CURVE; Bread Modular LOW/SVF vactrol driver; IN/CV/OUT per channel, CV unpatched = open) + per-channel volume after the VCA (OUT post-volume) + MIX out (Bread Modular imix style), buffered inputs/CV, 1 W output resistors, ±12 V, 10 x TL072 | S4 schematic + P4 placement + 6HP panels; R1 routed carrier, final (TraceMaker + cleanup, 0 unconnected; the 9 vactrol/pot stacking findings are user-approved DRC exclusions, D10; copied into `hardware/` past the shared gate, which still counts them, D14, user-verified manually; vactrol build notes on silk); JLCPCB export in `modules/vca-mix/jlcpcb/`, not supplier-accepted, not built |
| `modules/16bit/` | 16bit, 6HP: RP2350A + W25Q128 flash + APS6404L PSRAM, PT8211 I2S DAC -> TL074 ±5 V outs, MIDI in (NPN, JP1), 2 x CV in with attenuators, 2 knobs, MODE button + LED, USB-C data, 4-layer (Bread Modular `16bit` based) | S3 schematic; R2 manual divide-and-conquer routing done (DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, plain tented, no POFV; B silk BOOT/RESET/JP1 labels); 6HP panel; JLCPCB export in `modules/16bit/jlcpcb/` (bottom Economic, TM8211 for PT8211, cjiang L1, user-stocked Adafruit 4677 PSRAM), not supplier-accepted, not built; BM 16bit 1.6.0 firmware (six apps) in `modules/16bit/firmware/` (JP1 p/d builds, `opt/rp2350-tools`), compiled, not bench-tested |
| `modules/low/` | LOW, 6HP: Bread Modular MCO (ATtiny1616 dual square, DETUNE/MIX) + LOW (two-vactrol LPG, CUTOFF) at 3.3 V; 8bit MIDI in; AUDIO and CV bypass inputs (10 Vpp / 0..5 V mapped to 0..3.3 V) normalled via a TS5A23157 to the MCO square mix and velocity DAC; TL072 ±12 V out | S3 schematic (ERC 0, signal nets wired, LCSC fields; R17/R18 47k/100k for Basic) + R3 manual divide-and-conquer routing, 2-layer, SMD >= 2 mm from pot/jack pads (closest U6 2.20 mm), 1 mm edge keep-out (copper-edge rule 1.0 mm; RV1/RV2 courtyards 0.82 mm, user-accepted) (KiCad DRC 0 / unconnected 0 / parity 0; the 3 U5-under-CUTOFF stacking items are user-approved DRC exclusions, still counted by the shared gate; no vias in SMD pads); JLCPCB export in `modules/low/jlcpcb/` (bottom Economic, all R/C Basic), not supplier-accepted, not built; BM MCO firmware in `modules/low/firmware/` (JP1 p/d builds), compiled, not bench-tested |
| `modules/acid/` | ACID, 8HP: Bread Modular MCO + ENV on one ATtiny1616 (3 envelope models + LEDs, REC button), BM SVF (two vactrols on B, RES 500k), all at 3.3 V; 8bit MIDI in; AUDIO and CV bypass inputs (10 Vpp / 0..5 V mapped to 0..3.3 V) normalled via a TS5A23157 to the MCO mix and the DAC envelope; no DRIVE: LP / HP / BP outs, each one TL072 stage with a 3-pad gain jumper (open x3.0 shipped, 2-3 x3.9, 1-2 x11.1; ~10 Vpp ceiling) + protected 0..5 V envelope CV out | S3 schematic (gain jumpers JP2-JP4, Rg 4.7k + 10k + 5.1k; ERC 0, every signal net wired; 0.5 W 1206 1k = ROHM ESR18) + R2 = R1 manual divide-and-conquer routing + gain-jumper clusters (LP/HP on the left edge strip, BP under RES/CURVE), 4-layer (vactrols under ATTACK/RELEASE, 22 stacking items user-approved DRC exclusions, still counted by the shared gate; KiCad DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, In1/In2 planes one piece; B silk UPDI + MIDI JP1 + gain-jumper labels); 8HP panel; JLCPCB export in `modules/acid/jlcpcb/` (S3/R2 carrier, bottom Economic, 98 parts), not supplier-accepted, not built; BM MCO + ENV merged firmware with the shared REC recorder in `modules/acid/firmware/` (JP1 p/d builds), compiled, not bench-tested |
| `modules/32bit/` | 32bit, 6HP: ESP32-S3-WROOM-1U-N16R8 + ES8388 codec, MIDI in (NPN, JP1), 2 x audio in (TL074, no normal), 2 x CV in with attenuators, TL072 ±5 V outs, MODE button + LED, USB-C data + BOOT/RESET, 4-layer (Bread Modular `32bit-5v` based) | S2 schematic (ERC 0; R1 layout pin changes logged in `docs/firmware-pins.md`) + R2 manual divide-and-conquer routing (R1 + 2 mm hand-solder clearance, closest 2.02 mm except user-accepted R5/C27/R55/C46 at 1.33-1.75 mm; DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, In1/In2 planes one piece; B silk MIDI JP1 labels); 6HP panel; R2 JLCPCB export in `modules/32bit/jlcpcb/` (U1 ESP32 module Standard PCBA, user choice), not supplier-accepted, not built; polysynth firmware in `modules/32bit/firmware/` (CV1 release, CV2 filter; JP1 p/d builds) + BM fxrack firmware (delay/reverb, PSRAM), compiled, not bench-tested |
| `modules/4mix/` | 4MIX, 18HP: Bread Modular 4mix (no overdrive) on ±12 V: audio only, every input AC-coupled; 4 channels (IN jack on top, SEND A, SEND B, VOL), 2 post-fader sends + 2 returns, top line SEND A, SEND B, RTN A, RTN B, MAIN, OUT (sends top left, return levels below their jacks); big-knob space on each channel VOL; 2x3 EXP IN (top left) / EXP OUT (top right) headers and power (bottom right) on the back; 2 x 10 mm M3 F-F hex standoffs MS1/MS2 hold the carrier bottom to the panel, 9 x TL072 | S2 hierarchical schematic (channel sheet x 4, ERC 0) + P6 placement (user hand placement, tidied; M3x10 standoffs MS1/MS2, mechanical footprints) + R1 manual divide-and-conquer routing, 4-layer (In1 GND, In2 +12V), all SMD on B (DRC 0 / unconnected 0 / parity 0, no vias in SMD pads, SMD >= 2 mm from pot/jack pads, closest 2.27 mm); 18HP panel fit study; JLCPCB export in `modules/4mix/jlcpcb/` (bottom Economic, all R/C Basic except the 1 W 2512 output resistors), not supplier-accepted, not built |
| `modules/hats/` | HATS, 6HP: Bread Modular NOISE (blue noise, NOISE TONE / BLUE TONE) -> HIHAT (CUTOFF, DECAY, vactrol VCA), two ATtiny1616 (BM pin maps) on one MIDI RX; NOISE IN normalled via a TS5A23157 to the internal blue noise; no recording controls; TL072 AUDIO out x3 + HAT CV out 0..5 V with ENV LED, ±12 V | S3 schematic (ERC 0, nets wired, VMID_H label-joined) + R3 manual divide-and-conquer routing, 4-layer (In1 GND, In2 +3V3), all SMD on B; all four pots upright, vactrol U7 on B under CUTOFF (LOW/ACID pattern; 10 `pth_inside_courtyard` + 8 `silk_over_copper` stacking items are user-approved DRC exclusions, still counted by the shared gate; ENV LED midway between AUDIO and HAT CV on their centre line); unconnected 0 / parity 0, no vias in SMD pads, SMD >= 2 mm from pot/jack pads (closest 2.045 mm), RV1-RV4 courtyards 0.815 mm (user-accepted); 6HP panel; JLCPCB export in `modules/hats/jlcpcb/` (R3, bottom Economic, 89 parts), not supplier-accepted, not built; BM NOISE + HIHAT firmwares in `modules/hats/firmware/` (JP1 p/d builds), compiled, not bench-tested |
| `modules/usb-audio/` | USB-AUDIO, 6HP: 2 in / 2 out USB audio interface, CH32V307RCT6 (USB 2.0 HS, UAC2) on a separate MCU board soldered on 2.54 mm strips over the carrier F side (vertical HRO USB-C 1.3 mm proud of the panel), CS4270 codec (I2S master, 24.576 MHz, 192 kHz), DC-coupled ±5 V in/out (CV too) with a 0..1 volume pot per jack (IN: jack, pot; OUT: pot, jack), OPA1678/OPA1679, BOOT/RESET + SWD on the carrier back, both boards 4-layer | Carrier S2 schematic (follower quad split into U4/U7 duals) + R2 codec-centred manual re-route (In2 +3V3 with a +5VA island under the codec; DAC paths 2-8 mm); MCU board S1 + R1 (1x10 strips, pin 10 GND); both ERC 0 / DRC 0 / unconnected 0 / parity 0, copper-edge 1.0 mm, no vias in SMD pads, planes one piece; 6HP panel with USB-C slot; JLCPCB export in `modules/usb-audio/jlcpcb/` (`main/` carrier bottom Economic + panel, `mcu/` top Economic; C20-C23 C0G and R1 2512 still Extended R/C, user decision open), not supplier-accepted, no firmware |
| `modules/usb-audio-max/` | USB-AUDIO-MAX, 10HP: 6 in / 8 out USB audio interface, CH32V307RCT6 (USB 2.0 HS, UAC2) on a separate MCU board (modules/usb-audio MCU board + SPI1 for the second TDM line pair), TI PCM3168A codec (TDM clock master, SCKI 24.576 MHz, up to 96 kHz), DC-coupled +/-5.9 V in/out, no level controls; inputs 100k -> OPA1679 inverting driver on +5VA (single-ended ADC), outputs OPA1679 difference amplifiers on +/-12 V -> 1k; +5VA linear and precise (2 x 33R + discrete LM358/BCP56 regulator referenced to a REF5050, MMBT3904 current limit: +5VA is the DC reference of every channel), +3V3 from a TPS562208 FCCM buck (~580 kHz at every load, never in the audio band) behind a ferrite + 2.2R input filter, molded inductor; only the digital rail switches | **S2 schematics, final** (carrier + MCU board, ERC 0, netlists asserted, every LCSC code live-checked 2026-11-05: 49 codes, all Economic-eligible, PCM3168APAPR C529289 Extended, 1517) + footprint library; ngspice (models, not measured): +5VA loop PM >= 78 deg / GM >= 26 dB, buck ripple ~50 uV on +12V_F / 0.1 uV on +5VA, USB load bursts -142 dBFS at the jacks (as with the S1.2 LDO); **S1 placement, 10HP** (user: 10HP if 8HP is too tight; fit study 8HP 64 % vs 10HP 45 % SMD density, `docs/research.md` section 5): USB-C on top, IN 1-6 two rows of three, OUT 1-8 three rows (ninth spot empty, J1 power behind it), carrier 49.5 x 110 mm + modules/usb-audio-size MCU board centred, 10HP FR4 panel; THT/headers/BOOT/RESET placed, SMD parked (DRC 0 / parity 0, nothing routed); 48 kHz all I2S, 96 kHz adds SPI1 (runtime switch); no routing, export or firmware; 96 kHz SPI1 path untested |
| `modules/busboard/` | Busboard: passive 8 x 16-pin shrouded IDC Eurorack bus (Doepfer pinout, CV/GATE bussed only) for the case floor, 205 x 32 mm 2-layer, 4 x M3 holes beside the end headers (196 x 21 mm, bolted from under the bottom plate's solid frame; plate ribs under the board) | S1 schematic + R3 board (straight bus tracks, GND pours; ERC 0 / DRC 0 / unconnected 0 / parity 0); JLCPCB Gerbers in `modules/busboard/jlcpcb/` (no assembly), not supplier-accepted, not built |
| `modules/blank/` | Blank panels 2HP / 4HP / 6HP / 8HP: outline + Ø3.2 rail holes only (2HP X2.42, others X12.58, 8HP also X32.9), no labels | FR4 panels (native DRC 0) + FreeCAD 2.0 mm prints; JLCPCB exports in `modules/blank/jlcpcb/`, not supplier-accepted |

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
