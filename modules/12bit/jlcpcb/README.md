# 12bit — manufacturing export (S2/R1)

Generated on 2026-11-06 from the S2 schematic and the R1 hand-routed carrier with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit these files:
change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `12bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `12bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (F / In1 GND / In2 +3V3 / B copper, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `12bit-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL (or ENIG). **Via covering: tented**, no via-in-pad / POFV (no vias in SMD pads). Every via is 0.3 / 0.6 mm |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 46 parts in 24 BOM rows, all on the back |
| Front panel PCB | `12bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J4 | QingPu WQP-PJ301M-12 TS jack (MIDI, CV, OUT 1, OUT 2) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV3 | RV09 50k linear pot | Front-side THT, no nut. Trim RV3's leads/lugs to <= 2 mm on the back (the power cable socket sits over them) |
| SW1 | 6 x 6 mm THT tact switch (MODE) | Front-side THT |
| D1 | 3 mm red LED (MODE) | Front-side THT; set its height to the panel hole |
| J5 | 2x5 2.54 mm pin header | Eurorack power, back side, upright at the right edge, pin 1 (-12 V) at the bottom |
| J6 | 1x5 2.54 mm pin header | SWD (3V3 sense, DIO, CLK, GND, RST), back side |
| JP1 | 3-pad solder jumper (MIDI RX source) | Copper only, **shipped open**: bridge 1-2 (protected, firmware sets USART1 RXINV) or 2-3 (direct), never both |

The exporter excluded exactly these 11 THT refs plus JP1 (`carrier/export-report.json`).

## Parts

Codes and fields come from the schematic `SOURCING` table (live-checked 2026-11-06, see
`docs/sourcing-candidates.json`). Rechecked live at export (2026-11-06): STM32G071C8T6
C529341 Extended, 4,969 in stock; TL074CDR C12594 Extended, 102,818. The FB1 ferrite C1002
still fails the shared exact lookup (truncated keyword search), as before; check it in the
JLCPCB BOM match. All resistors and capacitors are JLCPCB Basic except R16/R17 (ROHM ESR18
1k 1206 0.5 W, C2074262, Extended, as modules/8bit). Other Extended: STM32G071C8T6, TL074CDR,
MCP6001T, BAT54SW. Public stock is not a reservation.

Not an order approval: check part matches, pin 1 / polarity and rotations of every
bottom-side part (U3 LQFP-48, U4, U1, Q1, D2-D5) in JLCPCB's preview, and the carrier and
panel DFM previews.

## Reproduce from the repository root

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/12bit/tools/kicad-project.json --reports modules/12bit/research/new-check

python3 -B opt/kicad-tools/jlcpcb/export.py modules/12bit/hardware \
  --board 12bit --schematic 12bit.kicad_sch --side bottom --require-part-numbers \
  --manifest modules/12bit/jlcpcb/source-sha256.json --overwrite -o modules/12bit/jlcpcb/carrier

python3 -B opt/kicad-tools/jlcpcb/export.py modules/12bit/panels/front-pcb \
  --board 12bit-panel --pcb-only --manifest modules/12bit/jlcpcb/source-sha256.json \
  --overwrite -o modules/12bit/jlcpcb/panel

unzip -o modules/12bit/jlcpcb/carrier/12bit-gerbers.zip -d modules/12bit/jlcpcb/carrier
unzip -o modules/12bit/jlcpcb/panel/12bit-panel-gerbers.zip -d modules/12bit/jlcpcb/panel
cp modules/12bit/jlcpcb/carrier/bom.csv modules/12bit/jlcpcb/carrier/positions.csv modules/12bit/jlcpcb/assembly/
cp modules/12bit/jlcpcb/carrier/12bit-gerbers.zip modules/12bit/jlcpcb/panel/12bit-panel-gerbers.zip modules/12bit/jlcpcb/
```

Never run `tools/build_layout.py` over the routed carrier (it refuses); `--panel-only`
rebuilds the panel.
