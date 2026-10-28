# ENV: MIDI envelope (6HP)

The ACID envelope on its own module: Bread Modular **ENV** on one ATtiny1616 at 5 V (the same HT7550-1 supply as our 8bit),
triggered by MIDI notes, with three envelope models, knob recording and a protected 0..5 V
output.

| Panel (top to bottom) | Circuit |
|---|---|
| **GATE IN**, **MIDI IN** (top row) | GATE: NPN buffer (~1.9 V threshold, ±12 V safe) + jack detect: a patched GATE IN bypasses MIDI notes. MIDI: 8bit / ACID NPN front end, JP1 protected/direct jumper |
| **ATTACK**, **RELEASE** | BM ENV time knobs, 50k dividers (attack = hold in HR mode), 30 mm apart |
| **MODE** button + **HR / AR / ASR** LEDs (one row) | Envelope model select (BM ENV algorithms) |
| **REC** button + LED | Records the knob positions (firmware later) |
| **ENV OUT**, **ENV** LED, **MIDI OUT** (bottom row) | Scaled DAC ~0..3.3 V (INT43V, codes 0..194) -> TL072 x1.51 -> 0..5 V, 1k 0.5 W series; the LED shows the envelope level (driven by the output amp). MIDI OUT is a passive thru wired to MIDI IN (daisy chain) |

**Status: S4 schematic (ERC 0, every net wired) + P7 THT placement + R1 manual routing (2 layers,
DRC 0, unconnected 0, parity 0; B silk JP1 / UPDI labels); 6HP panel. JLCPCB export in
[`jlcpcb/`](jlcpcb/README.md) (bottom Economic, 36 parts), not supplier-accepted, not built. No
firmware.** R5-R8 (HR/AR/ASR/REC indicators) are now 1k; R13 (ENV LED) was already 1k.

**Firmware contract:** 4.34 V DAC setting at a 5 V supply, scale the envelope to DAC codes
0..194; use VDD for the knob ADC reference. Use JP1 **P/protected** for 3.3 V MIDI senders
(direct mode is 5 V logic only) and a 5 V-compatible UPDI programmer.

```sh
python3 -B tools/import_footprints.py   # one-time library import (pcbnew)
python3 -B tools/build_schematic.py     # schematic (placement by hand, wires by its router)
python3 -B tools/build_layout.py        # P7: THT placement + parked SMD. Do NOT rerun: R1 is routed
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/env/tools/kicad-project.json \
   --reports modules/env/research/check-NEW)
```

Read [`Code.md`](Code.md) before changing hardware.
