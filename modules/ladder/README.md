# LADDER: analog 16bit ladder filter + envelope + vactrol VCA

An analog take on the modules/16bit polysynth ladder filter: a classic Moog 4-pole
transistor ladder with the 16bit's controls and its resonance makeup (the dry level holds as
resonance goes up), an ATtiny1616 envelope driven by GATE or MIDI, a full CV bypass, and a
Bread Modular V2CA-style vactrol VCA on the filter output.

| Control / jack | Function |
|---|---|
| **CUTOFF** | ~55 Hz .. ~17 kHz, exponential, CW = open |
| **RESONANCE** | vactrol-controlled, 0 .. self-oscillation near the top (point depends on the vactrol); dry level kept (16bit (1 + k) makeup) |
| **ENV TIME** | attack = release, 5 ms .. 2 s (firmware) |
| **DEPTH** | 0 .. +8 octaves of envelope (or CV) on top of CUTOFF (read by the MCU, recordable) |
| **REC** + LED | records ENV TIME + DEPTH for 4 bars on MIDI clock, then loops (as ACID; firmware to write) |
| **CURVE** | VCA response: CCW punchy, CW soft (V2CA CURVE) |
| **MIDI**, **GATE** | start / release the envelope (MIDI: TS, JP1 protected / direct) |
| **CV** | 0..5 V, replaces the envelope (cutoff via the MCU x DEPTH; the VCA directly) |
| **AUDIO IN** | 10 Vpp |
| **RES CV** | adds to RESONANCE (slow, through the vactrol), +5 V ~ the knob's full range |
| **FILTER OUT**, **VCA OUT** | direct ladder out; through the vactrol VCA |

**Status: S3 schematic (vactrol resonance, REC; ERC 0, netlist asserted) + R2 routed carrier: 10HP,
4 layers, all SMD on the back (manual routing + 2026-11-10 fab-review fixes; DRC 0 / unconnected 0 /
parity 0). Panel PCB + printable panel. JLCPCB export in [`jlcpcb/`](jlcpcb/README.md), not
supplier-accepted, not built. No firmware.**

Panel, top to bottom: MIDI, GATE, CV, RES CV; CUTOFF, RES; ENV TIME, DEPTH; REC button + LED,
CURVE; AUDIO IN, FILTER OUT, VCA OUT.

```sh
python3 -B tools/build_schematic.py   # schematic (placement by hand, wires by its router)
python3 -B tools/build_layout.py      # carrier P2 placement + panel (refuses a routed carrier: do not run)
python3 -B tools/sim_ladder.py        # ngspice check of ladder / expo / resonance
kicad-cli sch erc --severity-all --format json -o research/erc.json hardware/ladder.kicad_sch
```

Schematic PDF: [`docs/ladder-schematic.pdf`](docs/ladder-schematic.pdf). Design notes:
[`docs/research.md`](docs/research.md).
