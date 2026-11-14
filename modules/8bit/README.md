# 8bit — ATtiny1616 DAC voice (6HP)

Based on Bread Modular `8bit`. An ATtiny1616 plays audio from its DAC; its firmware
reads MIDI, a CV input and three knobs. Bread Modular's firmware pin map is kept.

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS), top left | MIDI V2 NPN front end (3.3 V / 5 V senders, ±12 V tolerant). Solder jumper JP1 (back, shipped open): `P` = protected (firmware `PORT_INVEN` on PB3), `D` = direct/unprotected (stock BM firmware) |
| **CV** in, top right | Bipolar: 56k/51k/510k level shift maps **-5.5..+5.5 V to 0..5 V** (input impedance 102k), BAT54SW clamp + 1n, MCP6002 follower on +5 V into PB0 (ADC). ±12 V tolerant; unpatched = 0 V = mid-scale (~509 of 1023) |
| **P1**, **P2**, **P3** (zigzag left / right / left) | 50k linear dividers into PA1 / PA2 / PB5, 10n at each pin. P3 is a plain MCU knob (S6: the Bread Modular passive low-pass is gone) |
| **MODE** button + LED (one row) | Hand-soldered 6 x 6 mm THT tact switch, 7 mm tall, on the carrier front, pressed through the panel by a one-piece printed cap (`panels/button-actuator/`); LED on PA5 |
| **OUT**, bottom left | TL074 on ±12 V: DAC 0..4.34 V -> ±4.8 V, DC coupled, no filter, 1k series |
| **GATE**, bottom right | PA7 (Bread Modular `GATE_PIN`) -> TL074 follower -> 1k: 0 / +5 V, held low by 100k while the MCU is in reset |

Power: Eurorack 10-pin header upright at the right board edge (16-pin IDC fits), ±12 V
through series Schottkys, +5 V from an HT7550-1. UPDI on a 2-pin header. Pots: the
user's RV09 stock (50k, no bushing, 16 mm shaft, no nut), as `modules/audio-out`.

**Status: S6 schematic + R1 manually routed 6HP carrier, not built, not bench-tested.**
Shared `check`: ERC 0, DRC 0 at all severities, 0 unconnected, parity equal, no
exclusions (`docs/fit/`). JLCPCB export of the S6/R1 carrier and panels in `jlcpcb/`
(2026-11-14, not supplier-accepted; order gates in `jlcpcb/README.md`). Printed panel regenerated
(`panels/front-cad/`), not test-printed (`docs/research.md` §6).

| Path | Contents |
|---|---|
| `hardware/` | KiCad project `8bit.kicad_{pro,sch,pcb}` (29 x 110 mm carrier, 2 layers, routed by hand), pinned symbols, footprints and models (`8BIT.pretty`, `8BIT.3dshapes`, `PROVENANCE.json`), vendored 3D models (`_kicad_models/<sha256>/`) |
| `panels/front-pcb/8bit-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-pcb/8bit-lfo-panel.kicad_{pro,pcb}` | LFO variant of the panel: no MIDI jack or RV3 (P3) hole, RATE/WAVE/REC labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `panels/button-actuator/` | Printed MODE cap: STL (print orientation), STEP at SW1, FreeCAD generator |
| `docs/jumpers.md` | The JP1 MIDI-input jumper and the firmware pin map |
| `docs/research.md` | BM baseline, decisions, circuit, sourcing, open items |
| `docs/geometry.json`, `docs/mechanics.md` | 6HP fit, stack, button cap, panel and placement contract |
| `docs/8bit-schematic.pdf`, `docs/fit/` | Schematic PDF; native ERC/DRC JSON and renders |
| `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` | Pinned-symbol provenance; dated live JLCPCB lookups |
| `docs/jlcpcb-audit-requirements.json` | Circuit stress/manual-part policy for the assembly audit (reviews empty) |
| `jlcpcb/` | S6/R1 manufacturing export: carrier Gerbers + bottom-side BOM/CPL (38 parts), 6HP panel and optional LFO panel Gerbers, source manifest (`jlcpcb/README.md`) |
| `firmware/` | BM `drums`, `supersaw` (MIDI only), `crash` and `lfo` (no MIDI, CV in modulates the rate, MODE = output range -5..+5 V / 0..+5 V) firmwares, the MIDI ones built per JP1 setting (`firmware/README.md`) |
| `tools/` | Generators and the shared-tool profile `kicad-project.json` (the native PCB owns the copper) |

Generators (from `modules/8bit`). The routed `hardware/8bit.kicad_pcb` owns SMD placement
and copper: `build_layout.py` without `panels` refuses to overwrite it.

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic + pinned symbols
python3 -B tools/build_layout.py panels # FR4 panels only; the routed carrier is left alone
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/button-actuator/build_button_actuator.py
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
PANEL=lfo ~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/8bit/tools/kicad-project.json \
   --reports modules/8bit/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
