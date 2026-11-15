# LADDER: pure-analog 6HP transistor ladder filter

A classic Moog 4-pole transistor ladder low-pass, analog from jack to jack: no MIDI, no MCU, no
firmware. OTA (LM13700) resonance with the modules/16bit `PolyFilter` makeup (the dry level
holds as resonance goes up), an attenuated CV input for the cutoff and two dim LEDs that show
it.

| Control / jack | Function |
|---|---|
| **IN** | Audio in, 10 Vpp |
| **RES CV** | Adds to RES, +5 V = the knob's full range, negative subtracts; no attenuator; audio rate works |
| **CV** | Cutoff modulation, DC coupled: positive opens the filter, negative closes it |
| **DEPTH** | Attenuates the CV: 0 .. +8.3 octaves for a 5 V CV |
| CV LEDs `-` / `+` | Show the CV after DEPTH, one per polarity, dim and linear from 0 V |
| **CUTOFF** | ~55 Hz .. ~17 kHz, exponential, CW = open (main knob) |
| **RES** | 0 .. self-oscillation from about 60 % of the travel; dry level kept (main knob) |
| **OUT** | Filter output, 10 Vpp for 10 Vpp in |

LED brightness: three solder jumpers on the back beside the CUTOFF pot (silk `LED`, `1` `2` `3`
= JP1..JP3), open as shipped (dimmest).

| JP1 | JP2 | JP3 | LED current at +/-5 V CV, DEPTH full |
|---|---|---|---|
| open | open | open | 0.06 mA |
| closed | open | open | 0.12 mA |
| open | closed | open | 0.19 mA |
| closed | closed | open | 0.25 mA |
| open | open | closed | 0.34 mA |
| closed | open | closed | 0.40 mA |
| open | closed | closed | 0.47 mA |
| closed | closed | closed | 0.53 mA |

**Status: S5 schematic (ERC 0, netlist asserted) + P4 placement + R1 manual routing: 6HP,
4 layers (In1 GND, In2 +12V_F), 95 SMD parts and the 3 solder jumpers on the back (ERC 0 /
DRC 0 / unconnected 0 / parity 0). Panel PCB + printable panel. Fab-reviewed 2026-11-15 (B silk 1.0 mm, stackup
recorded, no copper change). JLCPCB export in `jlcpcb/` (2026-11-15), not supplier-accepted, not built.** The earlier
10HP S3 / R2 version (ATtiny1616 envelope, REC, vactrol VCA) is in git history.

Panel, top to bottom: IN, RES CV; CV, DEPTH (the two CV LEDs below it); CUTOFF; RES; OUT.

```sh
python3 -B tools/build_schematic.py   # schematic (placement by hand, wires by its router)
python3 -B tools/build_layout.py --panel-only   # panel only: the carrier is routed (the build refuses it)
python3 -B tools/sim_ladder.py        # ngspice check of ladder / expo / OTA resonance / CV LED loop
kicad-cli sch erc --severity-all --format json -o research/erc.json hardware/ladder.kicad_sch
```

Schematic PDF: [`docs/ladder-schematic.pdf`](docs/ladder-schematic.pdf). Design notes:
[`docs/research.md`](docs/research.md).
