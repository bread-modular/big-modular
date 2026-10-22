# 32bit — ESP32-S3 + ES8388 stereo audio (6HP)

Based on Bread Modular `32bit-5v`: an ESP32-S3-WROOM-1U-N16R8 with an ES8388 stereo codec. It
reads MIDI, two audio inputs and two CV inputs (each with its own attenuator knob), and drives two
audio outputs. Bread Modular's GPIO map is kept, so its ESP-IDF firmware ports (flash over the
USB-C on the back). Pin map, change log and the code changes a port needs (CV scaling, MIDI polarity):
[`docs/firmware-pins.md`](docs/firmware-pins.md).

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS) | modules/16bit NPN front end at 3.3 V -> RXD0; JP1 (back, shipped open): `P` protected (firmware inverts RX), `D` direct (stock BM firmware) |
| **IN L**, **IN R** | 100k / 22k -> TL074 follower -> 1u -> 1k -> ES8388 LIN2/RIN2 (±5 V -> ±0.9 V) (no normal: firmware handles mono) |
| **CV1**, **CV2** + **P1**, **P2** | Jack normalled to +5V -> 50k attenuator -> TL074 follower -> level shift -> MCP6002 -> IO1/IO2 (modules/16bit chain) |
| **OUT L**, **OUT R** | ES8388 LOUT1/ROUT1 -> 1k -> 10u -> TL072 gain 3.55 -> 1k 0.5 W (~±5 V) |
| **MODE** + LED | 6 x 6 mm THT tact on IO8, 3 mm red LED on IO18 (as modules/16bit) |

Power: Eurorack 10-pin, ±12 V through series Schottkys, AMS1117-5.0 -> +5V -> AMS1117-3.3 -> +3V3
(radio never used: see `docs/research.md` D2). USB-C (back, top edge) is data only, with BOOT / RESET below it.

**Status: S2 schematic + R2 routed carrier (manual, 4 layers, 2 mm hand-solder clearance around jacks/pots except 4 user-accepted parts at 1.33-1.75 mm); R2 JLCPCB export in [`jlcpcb/`](jlcpcb/README.md) (U1 Standard PCBA, user choice); not supplier-accepted, not built.** Shared `check`: ERC 0,
DRC 0 violations, 0 unconnected, parity 0. Firmware pin changes vs Bread Modular: `docs/firmware-pins.md`.

| Path | Contents |
|---|---|
| `hardware/` | `32bit.kicad_{pro,sch,pcb}` (29 x 110 mm carrier, 4 layers), pinned symbols/footprints (`32BIT.kicad_sym`, `32BIT.pretty` + `PROVENANCE.json`, `32BIT.3dshapes`), vendored models |
| `panels/front-pcb/32bit-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `docs/research.md` | BM baseline, decisions, circuit, placement, open items |
| `docs/geometry.json` | 6HP panel and placement contract |
| `docs/32bit-schematic.pdf`, `docs/fit/` | Schematic PDF; native ERC/DRC JSON; placement render |
| `jlcpcb/` | JLCPCB Gerbers, BOM, CPL, upload map and sourcing notes |
| `tools/` | Generators (`circuit32.py` holds the circuit table) and the shared-tool profile |

Rebuild (from `modules/32bit`):

```sh
python3 -B tools/import_footprints.py   # library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic + pinned symbols, netlist asserted
# tools/build_layout.py made the S1 placement only: the routed board owns placement now, do not rerun it
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/32bit/tools/kicad-project.json \
   --reports modules/32bit/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
