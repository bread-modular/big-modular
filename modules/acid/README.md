# ACID: MIDI oscillator + envelope + vactrol SVF (8HP)

Bread Modular **MCO** + **ENV** (one ATtiny1616) and **SVF** (two-vactrol state-variable
filter, LP / HP / BP outs) on one Eurorack module, at Bread Modular's 3.3 V signal level. Each
output gets the gain of the user's BM DRIVE at 75 % in one TL072 stage.

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in (TS) | 8bit / LOW NPN front end, JP1 protected/direct jumper |
| **DETUNE**, **MIX** | BM MCO knobs |
| **ATTACK**, **RELEASE** | BM ENV time knobs (attack = hold in HR mode) |
| **HR / AR / ASR** LEDs, **MODE** button | Envelope model select (BM ENV algorithms) |
| **REC** LED + button | Records the envelope knob positions (firmware later) |
| **ENV OUT** | Envelope 0..3.3 V -> 0..5 V (protected) |
| **AUDIO** in, **FREQ**, **CV** in | Bypasses: AUDIO 10 Vpp -> 0..3.3 V (clips), unpatched = MCO; CV 0..5 V -> 0..3.3 V, unpatched = envelope. FREQ = BM SVF cutoff/CV amount |
| **RES**, **CURVE** | BM SVF resonance (500k), freq curve |
| **LP**, **HP**, **BP** out | x11.1, ~10 Vpp ceiling (TL072 clip), 500R |

**Status: S2 schematic (every net wired, ERC 0) + R1 manual routing, 4-layer (every net
routed; DRC 0 + 22 user-approved vactrol-under-pot exclusions, 0 unconnected, parity 0);
8HP panel. JLCPCB export in [`jlcpcb/`](jlcpcb/README.md) (bottom Economic), not supplier-accepted, not built.**

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic (placement by hand, wires by its router)
python3 -B tools/build_layout.py        # P3: THT placement from geometry.json + parked SMD. Do NOT rerun once routing starts
kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
   -o research/drc/vactrols.json hardware/acid.kicad_pcb
python3 -B tools/vactrol_exclusions.py research/drc/vactrols.json   # after every build_layout run
python3 -B tools/sim_level.py           # output-level model (research.md 3.4)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/acid/tools/kicad-project.json \
   --reports modules/acid/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
