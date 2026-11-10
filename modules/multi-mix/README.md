# multi-mix — digital 4-channel mixer with USB audio and MIDI (20HP)

modules/4mix's panel (4 channels with IN, SEND A, SEND B, VOL; RETURN A/B with levels; SEND A/B outs; OUT
jack over the MAIN knob, plus two host-assigned USB 1 / USB 2 outputs), widened to 20HP for the MCU board and its USB-C, rebuilt as a digital mixer: a PCM3168A codec and a CH32V307 MCU (both from modules/usb-audio-max)
do the mixing. Every knob is a DC divider read through a 74HC4067 mux and sent as MIDI CC (VOL as CC7). Over
USB the computer gets the 4 inputs and 2 returns (24-bit / 48 kHz) and can feed the returns. Units daisy-chain
through keyed 2x5 CLK OUT -> CLK IN ribbons that share the codec clocks only, so stems recorded from several units
over their own USB ports stay sample-locked; each unit keeps its own MAIN OUT and sends (up to 4 units until
bench-tested).

**Status: S3 schematics (ERC 0, netlists asserted) + R1 manual routing of both boards at 20HP (carrier and MCU board DRC 0 / unconnected 0 / parity 0; single-sided MCU board on two 1x12 strips, three standoffs, panel). Datasheet review done (`docs/research.md` 6a). No fab review, no JLCPCB export, not built, no firmware.**

| Path | Contents |
|---|---|
| `hardware/multi-mix.kicad_sch` | Carrier: power, codec, inputs, outputs, knobs + mux, clock link, MCU strips (PDF: `docs/multi-mix-schematic.pdf`) |
| `hardware/multi-mix-mcu.kicad_sch` | MCU board: CH32V307RCT6, USB-C, strips J112/J113 (PDF: `docs/multi-mix-mcu-schematic.pdf`) |
| `hardware/multi-mix.kicad_pcb`, `hardware/multi-mix-mcu.kicad_pcb` | R1 boards, 4 layers, placed and routed by hand (carrier: all SMD on B; MCU board: every part on F) |
| `panels/front-pcb/multi-mix-panel.kicad_pcb` | 20HP passive FR4 panel (NPTH holes, USB-C slot, labels) |
| `docs/geometry.json` | Placement contract (panel frame) |
| `docs/research.md` | Brief, architecture, decisions, clock-link pinout, MCU pins and strip maps, sourcing, datasheet review, placement, S2/S3 changes and R1 routing, open items |
| `tools/` | Schematic generator + circuit tables, footprint import, project files, shared-tool profiles |

Rebuild (from `modules/multi-mix`):

```sh
python3 -B tools/import_footprints.py
python3 -B tools/build_schematic.py
python3 -B tools/build_project.py
# tools/build_layout.py wrote the P3 boards: do NOT run it, the boards are placed and routed by hand
kicad-cli sch erc --severity-all --format json -o docs/erc/multi-mix-erc.json hardware/multi-mix.kicad_sch
kicad-cli sch erc --severity-all --format json -o docs/erc/multi-mix-mcu-erc.json hardware/multi-mix-mcu.kicad_sch
```
