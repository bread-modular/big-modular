# ACID: MIDI oscillator + envelope + vactrol SVF (10HP)

Bread Modular **MCO** + **ENV** (one ATtiny1616) and **SVF** (two-vactrol state-variable
filter, LP / HP / BP outs) on one Eurorack module, at Bread Modular's 3.3 V signal level. Each
output is one TL072 stage with a gain solder jumper on the back: x3 (shipped, the LOW level),
x3.9, or x11.1 (the user's BM DRIVE at 75 %).

| Panel (top to bottom) | Circuit |
|---|---|
| **MIDI** in, **AUDIO** in, **CV** in (top row) | MIDI: 8bit / LOW NPN front end, JP1 protected/direct jumper. Bypasses: AUDIO 10 Vpp -> 0..3.3 V (clips), unpatched = MCO; CV 0..5 V -> 0..3.3 V, unpatched = envelope |
| **DETUNE**, **MIX** | BM MCO knobs |
| **ATTACK**, **RELEASE** | BM ENV time knobs (attack = hold in HR mode), 4 mm lower than DETUNE / MIX |
| **HR / AR / ASR** LEDs, **MODE** button | Envelope model select (BM ENV algorithms) |
| **REC** button + LED (LED right of the button) | Records the envelope knob positions |
| **FREQ** | BM SVF cutoff/CV amount |
| **RES**, **CURVE** | BM SVF resonance (500k), freq curve (on the DETUNE/ATTACK and MIX/RELEASE columns) |
| **LP**, **HP**, **BP**, **ENV OUT** (bottom row) | Gain jumper JP2 / JP3 / JP4 on the back: open x3.0 (shipped), `M` x3.9, `H` x11.1; ~10 Vpp ceiling (TL072 clip), 500R. ENV OUT: envelope 0..3.3 V -> 0..5 V (protected) |

**Status: S3 schematic (gain jumpers; every net wired, ERC 0) + P4/R3 10HP re-layout (2026-11-06),
manual divide-and-conquer routing, 4-layer (every net routed; DRC 0 + 22 user-approved
vactrol-under-pot exclusions, 0 unconnected, parity 0); 10HP panel. JLCPCB export in
[`jlcpcb/`](jlcpcb/README.md): S3/R3 10HP set (2026-11-06), not supplier-accepted.
Not built.**

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic (placement by hand, wires by its router)
python3 -B tools/build_layout.py --panel-only   # regenerate the passive panel only; the routed carrier is the native source
kicad-cli pcb drc --format json --units mm --severity-all --schematic-parity \
   -o research/drc/vactrols.json hardware/acid.kicad_pcb
python3 -B tools/vactrol_exclusions.py research/drc/vactrols.json   # after every build_layout run
python3 -B tools/sim_level.py           # output-level model (research.md 3.4)
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/acid/tools/kicad-project.json \
   --reports modules/acid/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
