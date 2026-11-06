# 12bit — STM32G071 two-channel DAC voice (6HP)

modules/8bit moved from the ATtiny1616 to an **STM32G071C8T6**: its two 12-bit DAC channels
drive two outputs and the passive low-pass is gone (knob 3 is a plain knob). 6HP. (The S1
gate output was removed in S2.)

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS) / **CV** in | 8bit MIDI V2 NPN front end, JP1 on the back (shipped open): `P` = protected (USART1 RX inverted in firmware), `D` = direct. CV: -5.9..+6.0 V -> 0..3.3 V (Zin 138k), BAT54SW clamp, MCP6001 follower into PA0; unpatched = 0 V |
| **P1**, **P2** / **MODE**, LED, **P3** | 50k linear RV09 dividers into PA1 / PA6 / PA7. MODE: 8bit 6 x 6 x 7 mm THT switch (PB4) with the 8bit printed cap; 3 mm LED beside it on the same row (PB5, PWM) |
| **OUT 1**, **OUT 2** | DAC1_OUT1 / DAC1_OUT2 -> 1k/4.7n step smoothing (34 kHz) -> TL074 x3.4 around a 2.33 V offset -> ±4.9 V, DC coupled (audio, CV or LFO), 1k 0.5 W |

Power: Eurorack 10-pin (16-pin IDC fits) on B, upright at the right edge above OUT 2, ±12 V through series
Schottkys, +3V3 from an HT7533-1. SWD on a 1x5 header on B (1 3V3 sense, 2 SWDIO, 3 SWCLK,
4 GND, 5 NRST).

**Status: S2 schematic (ERC 0) + P3 placement + R1 hand routing (DRC 0, unconnected 0,
parity 0) + JLCPCB export in `jlcpcb/` (not supplier-accepted).** No firmware. See `docs/research.md` for decisions and open items.

| Path | Contents |
|---|---|
| `hardware/` | KiCad project `12bit.kicad_{pro,sch,pcb}` (29 x 110 mm carrier, 4 layers, routed R1), pinned symbols/footprints/models |
| `panels/front-pcb/12bit-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `docs/research.md` | Brief, decisions, circuit, placement, open items |
| `docs/geometry.json` | Placement contract (panel frame) |
| `docs/12bit-schematic.pdf`, `docs/fit/` | Schematic PDF; native ERC/DRC JSON and renders |
| `docs/schematic-symbols.json`, `docs/sourcing-candidates.json` | Pinned-symbol provenance; dated live JLCPCB lookups |
| `tools/` | Generators and the shared-tool profile `kicad-project.json` |

Rebuild (from `modules/12bit`; the carrier is now routed, so `build_layout.py` refuses it; use `--panel-only` for the panel):

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic + pinned symbols, netlist asserted
python3 -B tools/build_layout.py        # THT placement + parked SMD + nets, UNROUTED; panel
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/12bit/tools/kicad-project.json \
   --reports modules/12bit/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
