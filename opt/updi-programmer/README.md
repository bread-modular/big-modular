# UPDI programmer

USB-C UPDI programmer for the ATtiny (UPDI) chips on Big Modular modules.
It is the Bread Modular `opt/UPDIProgrammer` 0.3.0 circuit (USB-C → CH340N →
ATtiny1616 running [jtag2updi](https://github.com/ElTangas/jtag2updi)) with the
Bread Modular breadboard headers replaced by a single 5-pin 2.54 mm header.
It shows up as a normal `jtag2updi` programmer for avrdude.

## Header J1 (1x05, 2.54 mm)

| Pin | Silk | Net | Use |
| --- | --- | --- | --- |
| 1 (square pad) | UPDI | `UPDI` (ATtiny1616 PB0) | UPDI **out** → the module's UPDI pin |
| 2 | GND | `GND` | → the module's GND |
| 3 | GND | `GND` | spare ground |
| 4 | GND | `GND` | spare ground (e.g. for self-flashing) |
| 5 | SELF | `MCU_UPDI` (4.7k → ATtiny1616 UPDI, 100k pull-down) | UPDI **in**, flashes this board's own ATtiny1616 |

J1 is a plain 1x05 male header, hand-soldered after assembly (it is in the
native BOM but excluded from the JLCPCB CPL).

**Programming a module:** plug in USB-C, wire J1.1 UPDI → module UPDI and
J1.2 GND → module GND, then use the module's flash script (avrdude
`-c jtag2updi`, e.g. `opt/attiny1616-tools/flash.sh`).

**Flashing this board's firmware:** see [`firmware/readme.txt`](firmware/readme.txt).
JLCPCB-assembled boards arrive with a blank ATtiny1616. A second UPDI
programmer drives J1.5 SELF + J1.4 GND while this board is powered from its
own USB-C; then run `firmware/setup.sh` once and
`firmware/flash.sh <port of the second programmer>`.

Notes:

- UPDI (J1.1) is driven at the board's 5 V USB logic level (as on the Bread Modular
  board). Only connect it to a target whose UPDI pin tolerates 5 V.
- GND on J1 is tied directly to USB ground. The Bread Modular board put a 330 Ω
  resistor in series with its ground header because that header could be
  plugged onto a 3.3 V rail; this board uses flying leads, so it is not needed.
- The CH340N serial TX/RX are no longer brought out; they still connect to the
  ATtiny1616 USART through R1/R2 (1k).

## Layout

```
firmware/   jtag2updi_t1616.hex (byte-identical to Bread Modular), readme.txt,
            setup.sh / flash.sh -> ../../attiny1616-tools/updi-programmer-*.sh
hardware/   updi-programmer.kicad_{pro,sch,pcb}
            UPDIProgrammer.kicad_sym / UPDIProgrammer.pretty (project-local library)
tools/      design.py           circuit intent (parts, pins, nets, fields)
            build_schematic.py  local library refresh + schematic generator
            build_pcb.py        placement, explicit routes, GND pours, design rules
            kicad-project.json  profile for opt/kicad-tools
            jlcpcb-requirements.json  circuit stresses for the assembly audit
jlcpcb/     fabrication export (see jlcpcb/README.md)
```

Shared module-side scripts (arduino-cli + megaTinyCore compile/flash, avrdude
setup) live in [`../attiny1616-tools/`](../attiny1616-tools/).

## Board

- 42 × 18 mm, 2 layers, 1 mm radius on all four corners; all parts on the
  top side.
- USB-C sits near the top-left corner (shell 1.5 mm below the top edge, clear
  of the corner radius) with its mouth 1.2 mm past the left edge
  (front shell slot copper 0.6 mm inside it, as in `modules/usb-power`), so
  bulky plug overmolds clear the PCB.
- Placement and every track/via are explicit in `tools/build_pcb.py` (no
  autorouter). GND is poured on both layers with stitching vias.
- Rules (in the `.kicad_pro`): 0.15 mm clearance, 0.15 mm min track (0.2 mm
  signal, 0.4 mm +5V), 0.6/0.3 mm vias, 0.5 mm copper-to-edge.
- USB-C: HRO TYPE-C-31-M-12 (LCSC C165948), the same 12-land footprint and
  pin-audited symbol as `modules/usb-power`. A5/B5 CC 5.1k pull-downs, 5 V sink only.
- The stock KiCad VQFN-20 3×3 footprint references a STEP model that KiCad 10
  does not ship. The local copy points at the shipped UQFN-20 3×3 0.4 mm body
  instead (`MODEL_OVERRIDES` in `design.py`). This only affects the 3D view;
  the copper land is unchanged.

## Regenerate and check

```sh
python3 -B opt/updi-programmer/tools/build_schematic.py   # --refresh-library to re-copy parts
python3 -B opt/updi-programmer/tools/build_pcb.py         # needs KiCad 10 pcbnew Python
python3 -B opt/kicad-tools/kicad_tools.py doctor --config opt/updi-programmer/tools/kicad-project.json
python3 -B opt/kicad-tools/kicad_tools.py check  --config opt/updi-programmer/tools/kicad-project.json \
  --reports opt/updi-programmer/research/<new-dir>
```

`build_pcb.py` takes pad nets and fields from kicad-cli's exported netlist and
asserts that they match `design.py`. pcbnew assigns fresh UUIDs to tracks on
every run, so regenerating produces a new file even when nothing changed.

Status: native ERC 0, DRC 0 (warnings included), 0 unconnected, 0 schematic
parity issues. Fabrication export in [`jlcpcb/`](jlcpcb/README.md). The circuit
matches the Bread Modular board, which works; this layout has not been built
or tested.
