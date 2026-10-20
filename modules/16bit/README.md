# 16bit — RP2350 I2S voice (6HP)

Based on Bread Modular `16bit`: an RP2350A plays audio through a PT8211 16-bit stereo
DAC and reads MIDI, two CV inputs (each with its own attenuator knob) and two more knobs. Bread Modular's GPIO map is kept, so
its firmware ports (UF2 over the USB-C on the back).

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS) | MIDI V2 / 8bit NPN front end at 3.3 V; solder jumper JP1 (back, shipped open): `P` protected (firmware inverts GPIO5), `D` direct (stock BM firmware) |
| **CV1**, **CV2** + **P1**, **P2** | Jack tip normalled to +5V -> P1/P2 50k attenuator -> TL072 follower -> -5.9..+6.0 V to 0..3.3 V (100k / 56k / 120k), BAT54SW clamp, MCP6002 follower -> GPIO26/27 (ADC0/1). Unpatched: P1/P2 are 0..+5 V knobs; patched: they scale the CV |
| **P3**, **P4** | 50k linear RV09 (user stock) dividers on +3V3 -> GPIO28/29 (ADC2/3), BM's knob channels |
| **MODE** + LED | 6 x 6 x 7 mm THT tact switch (as 8bit, GPIO12) with the 8bit printed cap; 3 mm red LED on GPIO13 through 1k (BM), PWM brightness |
| **OUT L**, **OUT R** | TL074 on ±12 V: gain 6.1 around 1.65 V; PT8211 full scale (~1.65 Vpp at 3.3 V) -> ±5.0 V, DC coupled, 1k 0.5 W series |

Power: Eurorack 10-pin (16-pin IDC fits), ±12 V through series Schottkys, AMS1117-5.0 ->
+5V -> AMS1117-3.3 -> +3V3. USB-C (back, top edge, plug from above) is data only (as BM): flash with the module powered.

**Status: S3 schematic + S5 placement + R1 routing (rev1 reviewed), not released.** Shared `check`: ERC 0,
DRC 0 violations, 0 unconnected, parity 0 (`docs/fit/routed-render.png`, `docs/research.md` §6-§7). No sourcing lookups yet (`docs/research.md` §5).

> **Fabrication requirement: via-in-pad fill.** 123 vias sit in SMD pads (53 GND, 27 +3V3,
> 43 signal/rail) plus U1's 9 exposed-pad thermal vias. Order **"via in pad: resin filled + copper
> capped (POFV), all vias"** (JLCPCB: "Via Covering: Epoxy Filled & Capped"). A plain tented
> 4-layer order risks solder wicking and tombstoned 0402s. Fallback if POFV isn't available:
> hand-apply paste and reflow with tented vias, and expect more joints to touch up. See `Code.md`.

| Path | Contents |
|---|---|
| `hardware/` | `16bit.kicad_{pro,sch,pcb}` (29 x 110 mm carrier, 4 layers, placed and routed), pinned symbols/footprints (`16BIT.kicad_sym`, `16BIT.pretty` + `PROVENANCE.json`, `16BIT.3dshapes`), vendored models (`_kicad_models/`) |
| `panels/front-pcb/16bit-panel.kicad_{pro,pcb}` | 6HP FR4 front panel: NPTH only, silkscreen labels |
| `docs/research.md` | BM baseline, decisions, circuit, placement, open items |
| `docs/geometry.json` | 6HP panel and placement contract |
| `docs/16bit-schematic.pdf`, `docs/fit/` | Schematic PDF; native ERC/DRC JSON; placement render |
| `tools/` | Generators and the shared-tool profile `kicad-project.json` |

Rebuild (from `modules/16bit`):

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic + pinned symbols, netlist asserted
python3 -B tools/build_layout.py        # placement + netlist nets + models, UNROUTED; panel
python3 -B tools/route_plan.py research/route/ops   # frozen R1 copper -> shared ops, 3 stages
# then `kicad_tools.py pcb plan/apply` each stage on the previous candidate (stages 1-2 with
# `--allow-draft-opens`), `pcb promote` the last
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/16bit/tools/kicad-project.json \
   --reports modules/16bit/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
