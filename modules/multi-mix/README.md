# multi-mix — digital 4-channel mixer with USB audio and MIDI (20HP)

modules/4mix's panel (4 channels with IN, SEND A, SEND B, VOL; RETURN A/B with levels; SEND A/B outs; OUT
jack over the MAIN knob, plus two host-assigned USB 1 / USB 2 outputs), widened to 20HP for the MCU board and its USB-C, rebuilt as a digital mixer: a PCM3168A codec and a CH32V307 MCU (both from modules/usb-audio-max)
do the mixing. Every knob is a DC divider read through a 74HC4067 mux and sent as MIDI CC (VOL as CC7). A TS MIDI IN jack
above the USB outs takes the rack's internal MIDI (controller modules) and passes it to the DAW as USB-MIDI. Over
USB the computer gets the 4 inputs and 2 returns (24-bit / 48 kHz) and can feed the returns. Units daisy-chain
through 2x5 CLK OUT -> CLK IN ribbons that share the codec clocks only, so stems recorded from several units
over their own USB ports stay sample-locked; each unit keeps its own MAIN OUT and sends (up to 4 units until
bench-tested).

**Status: carrier S5 / MCU S4 schematics (ERC 0, netlists asserted) + manual routing of both boards at 20HP (carrier R4, MCU board R3: DRC 0 / unconnected 0 / parity 0; single-sided MCU board on two 1x12 strips, three standoffs, panel P6). Datasheet review done (`docs/research.md` 6a); fab-review fixes applied (section 10); TS MIDI IN jack J11 above USB 1 -> PA10 USART1_RX, CLK IN J7 an unshrouded 2x5 header moved up (section 11, 2026-11-11). R4 / P5 (section 12, 2026-11-19): carrier B.Cu GND pour for the codec heat and the USB-C slot 1.5 mm longer downwards, both from the first modules/usb-audio-max board. JLCPCB export in `jlcpcb/` (carrier bottom Economic 203 parts / 46 rows, MCU board top Economic 25 / 13, panel), not supplier-accepted. C211-C216 = C107043 (C33353 was pre-order only, section 12b). J101 / MS3 courtyards user-accepted for the prototype. Open: 10 Extended R/C placements (user decision). Not built, no firmware.**

| Path | Contents |
|---|---|
| `hardware/multi-mix.kicad_sch` | Carrier: power, codec, inputs, outputs, knobs + mux, clock link, MIDI IN, MCU strips (PDF: `docs/multi-mix-schematic.pdf`) |
| `hardware/multi-mix-mcu.kicad_sch` | MCU board: CH32V307RCT6, USB-C, strips J112/J113 (PDF: `docs/multi-mix-mcu-schematic.pdf`) |
| `hardware/multi-mix.kicad_pcb`, `hardware/multi-mix-mcu.kicad_pcb` | Carrier R4 / MCU board R3, 4 layers, placed and routed by hand (carrier: all SMD on B; MCU board: every part on F) |
| `panels/front-pcb/multi-mix-panel.kicad_pcb` | 20HP passive FR4 panel P6 (NPTH holes, 11.0 x 5.2 mm USB-C slot, labels) |
| `jlcpcb/` | JLCPCB export: `main/` carrier + panel, `mcu/` MCU board (`jlcpcb/README.md`: upload map, hand-soldered parts, audit, order gates) |
| `docs/geometry.json` | Placement contract (panel frame) |
| `docs/research.md` | Brief, architecture, decisions, clock-link pinout, MCU pins and strip maps, sourcing, datasheet review, placement, S2/S3 changes and R1 routing, fab-review fixes (S4/R2), MIDI IN (S5/R3), usb-audio-max carry-over (R4/P5), open items |
| `tools/` | Schematic generator + circuit tables, footprint import, project files, shared-tool profiles, `check_usb.py` (MCU USB routing check) |

Rebuild (from `modules/multi-mix`):

```sh
python3 -B tools/import_footprints.py
python3 -B tools/build_schematic.py
python3 -B tools/build_project.py
# tools/build_layout.py wrote the P3 boards: do NOT run it, the boards are placed and routed by hand
kicad-cli sch erc --severity-all --format json -o docs/erc/multi-mix-erc.json hardware/multi-mix.kicad_sch
kicad-cli sch erc --severity-all --format json -o docs/erc/multi-mix-mcu-erc.json hardware/multi-mix-mcu.kicad_sch
```
