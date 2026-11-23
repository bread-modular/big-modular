# 32bit ES1 — manufacturing export (carrier ES1 / R4, panel = S3 panel)

Exported on 2026-11-23 for the **ES1** variant (`../../docs/research.md` section 10): the S3 / R3 board
(ES8388, MIDI in, two audio in, two CV in, two pots, MODE, back USB-C) with its own codec supply (U10 LP5907
from +5V) and its own codec clock (Y2 11.2896 MHz, ES8388 = I2S master). It is ordered **next to** the S4
CS4272 set in `../main/` + `../mcu/` to compare the two; it replaces nothing. Shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change the sources, then re-export
with the commands below.

## Contents

| Path | Data |
|---|---|
| `32bit-es-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `32bit-es-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | Carrier + panel sources and export SHA-256 (`tools/es/kicad-project.json` `source_manifest`) |

The top-level ZIPs and the `assembly/` CSVs are copies of the files in `carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `32bit-es-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL (or ENIG), stackup JLC04161H-7628. **Via covering: tented**, no via-in-pad fill / POFV (no vias in SMD pads). **Smallest hole 0.3 mm** (PTH drill file tools T1/T2 0.300: the nine thermal vias each under U1 and U4 and every routed via; nothing smaller). No `JLCJLCJLCJLC` marker: choose the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Assembly side: Bottom.** 108 parts in 45 BOM rows, all on the back. **PCBA service: Economic** (every code `componentProductType` 0, live 2026-11-23; confirm in the quote) |
| Front panel PCB | `32bit-es-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly. Same holes as the S3 panel (back USB-C: no panel slot) |

Printed panel: `../../panels/es/front-cad/` (2.0 mm, regenerated from this panel PCB, not test-printed).

### Hand-soldered after delivery (not in the BOM/CPL)

As S3: J1-J5, J8, J9 (PJ301M-12 jacks), RV1, RV2 (RV09 50k), SW1 (MODE), D1 (3 mm LED), J6 (2x5 power
header), JP1 (3-pad MIDI jumper, copper only, shipped open: bridge P or D, never both).

## Parts (live catalog 2026-11-23, 5 boards + 10 attrition each)

Every BOM code was looked up: listed stock, free stock (`canPresaleNumber`) above the need and
`minPurchaseNum` 1 for all 45 rows, so **no pre-order part**. The two ES1 parts:

| Ref | Part | LCSC | Class | Stock (free) |
|---|---|---|---|---|
| U10 | TI LP5907MFX-3.3/NOPB, SOT-23-5 | C80670 | Extended | 7,064 (3,827) |
| Y2 | YXC OT322511.2896MJBA4SL, 11.2896 MHz CMOS, 3.2 x 2.5 mm | C2831381 | Extended | 783 (753) |

Both are plain Extended (no Preferred Extended LP5907 or 11.2896 MHz 3225 part was found), so ES1 has two
more feeder fees than S3. The rest is the S3 BOM (C49 / C50 1u and C51 100n are existing Basic rows). Y2's
pin-out (1 tri-state, 2 GND, 3 OUT, 4 VDD) was read from the YXC YSO110TR datasheet; it matches KiCad's
Abracon ASE land used for it. Stock is a web count, not a reservation: recheck right before ordering.

## Checks done for this export (2026-11-23)

- **Shared `check` after the export** (`tools/es/kicad-project.json`): ERC 0, DRC 0 (all severities),
  0 unconnected, parity 0, 0 exclusions; manifest equal. `order_ready: false`, as always for this tool.
- **Copper** (`../../docs/research.md` section 10.2): 779 tracks / 136 vias, no via in an SMD pad, no In1
  tracks, In1 / In2 one piece each; new SMD >= 2.15 mm from pot / jack pads; zone fills saved.
- **BOM/CPL:** 108 parts / 45 rows, all `bottom`; every row has LCSC, MPN and manufacturer.
- **Firmware:** build with `BOARD=es1` (`../../firmware/README.md`, "Board: S3 or ES1"); an S3 build does
  not run this board's codec correctly.

Not done: JLCPCB preview (check U10 and Y2 pin 1 and rotation: the exporter applies no rotation offsets),
a whole-BOM `assembly.py audit`.

## Reproduce

From `modules/32bit`:

```sh
python3 -B tools/es/build_schematic.py
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/es/kicad-project.json --reports research/es/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware/es \
  --board 32bit-es --schematic 32bit-es.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/es/source-sha256.json --overwrite -o jlcpcb/es/carrier
unzip -o jlcpcb/es/carrier/32bit-es-gerbers.zip -d jlcpcb/es/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/es/front-pcb \
  --board 32bit-es-panel --pcb-only \
  --manifest jlcpcb/es/source-sha256.json --overwrite -o jlcpcb/es/panel
unzip -o jlcpcb/es/panel/32bit-es-panel-gerbers.zip -d jlcpcb/es/panel

cp jlcpcb/es/carrier/bom.csv jlcpcb/es/carrier/positions.csv jlcpcb/es/assembly/
cp jlcpcb/es/carrier/32bit-es-gerbers.zip jlcpcb/es/panel/32bit-es-panel-gerbers.zip jlcpcb/es/
```
