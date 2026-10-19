# 8bit — ATtiny1616 DAC voice (4HP)

Based on Bread Modular `8bit`. An ATtiny1616 plays audio from its DAC; its firmware
reads MIDI, a CV input and three knobs. Bread Modular's firmware pin map is kept.

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS) | MIDI V2 NPN front end (3.3 V / 5 V senders, ±12 V tolerant). Solder jumper JP1 (back, shipped open): `P` = protected (firmware `PORT_INVEN` on PB3), `D` = direct/unprotected (stock BM firmware) |
| **CV** in | Bipolar: 56k/51k/510k level shift maps **-5.5..+5.5 V to 0..5 V** (input impedance 102k), BAT54SW clamp + 1n, MCP6001 follower on +5 V into PB0 (ADC). ±12 V tolerant; unpatched = 0 V = mid-scale (~509 of 1023) |
| **P1**, **P2** | 50k linear dividers into PA1 / PA2 (BM knobs) |
| **P3** (1M linear) | Passive low-pass on the DAC, as Bread Modular (~160 Hz..15.9 kHz, CW = brighter). No jumpers |
| **MODE** button + LED | Bread Modular's SMD tact switch (K2-1808SN-A4SW-01) on the carrier front, pressed through the panel by a printed two-part actuator (`panels/button-actuator/`); LED on PA5 |
| **OUT** | TL072 on ±12 V: DAC 0..4.34 V -> ±4.8 V, DC coupled, 1k series |

Power: Eurorack 10-pin (16-pin IDC fits), ±12 V through series Schottkys, +5 V from
an HT7550-1. UPDI on a 2-pin header. Pots: the user's RV09 stock (50k and 1M, no
bushing, 16 mm shaft, no nut), as `modules/audio-out`.

**Status: S4 schematic + R3 routed carrier, JLCPCB export in `jlcpcb/`, not
supplier-accepted, not bench-tested.** Shared `check`: ERC 0, DRC 0 at all
severities, 0 unconnected, parity equal, source manifest equal, no exclusions
(`docs/fit/`). Live assembly audit: all parts resolved and Economy-eligible; R12's
fault power is the one hard fail (`jlcpcb/README.md`). No 3D fit or printed panel
yet (`docs/research.md` §6).

| Path | Contents |
|---|---|
| `hardware/` | KiCad project `8bit.kicad_{pro,sch,pcb}` (19 x 110 mm carrier, 2 layers, routed), pinned symbols, footprints and models (`8BIT.pretty`, `8BIT.3dshapes`, `PROVENANCE.json`), vendored 3D models (`_kicad_models/<sha256>/`) |
| `panels/front-pcb/8bit-panel.kicad_{pro,pcb}` | 4HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/button-actuator/` | Printed MODE actuator: plunger + cap STL (print orientation), assembled STEP, FreeCAD generator |
| `docs/jumpers.md` | The JP1 MIDI-input jumper and the firmware pin map |
| `docs/research.md` | BM baseline, decisions, circuit, sourcing, open items |
| `docs/geometry.json`, `docs/mechanics.md` | 4HP fit, stack, button actuator, panel and placement contract |
| `docs/8bit-schematic.pdf`, `docs/fit/` | Schematic PDF; native ERC/DRC JSON and renders |
| `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` | Pinned-symbol provenance; dated live JLCPCB lookups |
| `docs/jlcpcb-audit-requirements.json` | Circuit stress/manual-part policy for the assembly audit (reviews empty) |
| `jlcpcb/` | Gerbers, BOM/CPL, source manifest; upload map and order gates in `jlcpcb/README.md` |
| `tools/` | Generators, `route_plan.py` (all copper) and the shared-tool profile `kicad-project.json` |

Full rebuild (from `modules/8bit`). The routed `hardware/8bit.kicad_pcb` is the copper
source of truth: rerun the layout generator only as this whole sequence.

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic + pinned symbols
python3 -B tools/build_layout.py        # placement + netlist nets + models, UNROUTED; panel
python3 -B tools/route_plan.py > research/route/plan.json        # copper as shared ops v1
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb plan --config modules/8bit/tools/kicad-project.json \
   --ops modules/8bit/research/route/plan.json > modules/8bit/research/route/edit-plan.json)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb apply --plan modules/8bit/research/route/edit-plan.json \
   --ops modules/8bit/research/route/plan.json --output modules/8bit/research/route-cand-NEW)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py pcb promote --candidate modules/8bit/research/route-cand-NEW \
   --plan modules/8bit/research/route/edit-plan.json)
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/button-actuator/build_button_actuator.py
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/8bit/tools/kicad-project.json \
   --reports modules/8bit/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
