# LOW: MIDI oscillator + low-pass gate (6HP)

Bread Modular **MCO** (ATtiny1616 dual square oscillator) and **LOW** (two-pole vactrol
low-pass gate) on one Eurorack module, at Bread Modular's 3.3 V signal level.

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS) | 8bit NPN front end, JP1 protected/direct jumper |
| **DETUNE**, **MIX** | BM MCO knobs: tone 2 detune 0..12 semitones, tone 2 level |
| **AUDIO** in | Bypasses the MCO into the LPG: AC coupled, 10 Vpp -> 0..3.3 V, hotter clips. Unpatched: MCO square mix |
| **CV** in | Bypasses the LPG CV: 0..5 V -> 0..3.3 V. Unpatched: MCO velocity (BM DAC) |
| **CUTOFF** | BM LOW vactrol LED current |
| **OUT** | TL072, 0..3.3 V -> ±5 V |

**Status: S3 schematic (wired nets, LCSC fields) + R3 routed carrier (manual, SMD >= 2 mm from pot/jack pads, 1 mm edge keep-out; KiCad DRC 0 with the 3 known U5/RV3 stacking items excluded, 0 unconnected, parity 0); JLCPCB export in [`jlcpcb/`](jlcpcb/README.md), not supplier-accepted, not built.**

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic + pinned symbols
python3 -B tools/build_layout.py        # P2 only: THT placement + parked SMD, UNROUTED. Do NOT rerun over the routed board
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/low/tools/kicad-project.json \
   --reports modules/low/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
