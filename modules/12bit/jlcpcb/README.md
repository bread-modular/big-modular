# 12bit — manufacturing export (S3/R3)

Generated on 2026-11-19 from the S3 schematic (+3V0 reference rail, `../Code.md`) and the R3 2-layer
hand-routed carrier with the shared `opt/kicad-tools/jlcpcb/export.py` exporter, on user direction
("Do the JLCPCB export"). It replaces the S2 / R2 export of the first board (2026-11-07, in git
history). Never hand-edit these files: change the sources, then re-export with the commands below.

S3 / R3 is not built and not measured: the reference rail is aimed at the output buzz of the first
board, and only a built board can confirm it.

## Contents

| Path | Data |
|---|---|
| `12bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `12bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (F / B copper, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `12bit-gerbers.zip` | **2 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz copper, HASL, **tented vias**, no via-in-pad / POFV / resin fill (no vias in SMD pads). Every via is 0.3 / 0.6 mm (65). Leave the other options at JLCPCB's defaults. The 110 mm length is over JLCPCB's 102 x 102 mm special price (as every 110 mm carrier); 2 layers since R2 to cut the cost |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 48 parts in 25 BOM rows, all on the back |
| Front panel PCB | `12bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly. Same panel as the first board (source unchanged, only the plot date differs): no need to reorder it for a panel you already have |

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

## Changes against the S2 / R2 export

- New: **U5 LM4040B30FTA** (C460604, SOT-23) and **R18 2.2k** (C4190).
- Re-valued: R5 56k -> 51k, R6 120k -> 100k, R10 / R12 24k -> 27k, R15 24k -> 22k.
- Moved: U1, C3, C4 (now right of the MCU). No other placement changed (CPL diff checked).
- Copper: 291 tracks, 65 vias (R2: 271 / 63). Panel: unchanged.

## Parts

Codes and fields come from the schematic `SOURCING` table. All 25 codes were looked up live at the
export (shared `assembly.py audit --strict-live`, 2026-11-19 01:03 UTC, `research/jlc-audit-s3/`;
`docs/sourcing-candidates.json`): every code is Economic-eligible and its MPN matches the BOM.

- **Basic**: all resistors and capacitors except R16 / R17, the diodes D2-D4, Q1, U1, FB1.
- **Extended (6 part types)**: STM32G071C8T6 C529341, TL074CDR C12594, MCP6001T C29429,
  BAT54SW C78260, LM4040B30FTA C460604 (new), ROHM ESR18 1k 1206 0.5 W C2074262 (R16 / R17, as
  modules/8bit). None is Preferred Extended.
- **Stock to watch**: STM32G071C8T6 listed **965** (4,969 on 2026-11-06). LM4040B30FTA 13,618,
  MCP6001T 31,686, ESR18 99,305.
- FB1 ferrite C1002 still fails the shared exact lookup (truncated keyword search), as before; a
  strict-live search lists it as Basic, Economic, 1,382,208 in stock. Check it in the JLCPCB BOM match.

Public stock is not a reservation. The audit's circuit-requirement reviews (ratings, land patterns)
have no requirements file and stay unknown, as for the S2 export.

Not an order approval: check part matches, pin 1 / polarity and rotations of every
bottom-side part (U3 LQFP-48, U4, U1, **U5**, Q1, D2-D5) in JLCPCB's preview, and the carrier and
panel DFM previews. U5 is new: pad 1 = cathode (+3V0), pad 2 = anode (GND), pad 3 open.

## Checks at the export (2026-11-19)

- Shared `check` before and after: ERC 0, DRC 0 (warnings included), unconnected 0, parity 0, no
  exclusions; source manifest **equal** after the export (`research/check-s3-export-after/`).
- Saved zone fills equal a fresh refill (B one piece, F one piece + the stitched strip).
- BOM refs = CPL refs = the 48 SMD footprints on B; CPL coordinates equal the board; the 12 excluded
  refs are the 11 THT parts + JP1.
- Drill file: 95 round hits (65 vias + 30 round THT holes) + 18 slots (jack and pot lugs) = the board.
- Every bottom SMD pad has its region in B.Cu, B.Mask and B.Paste (161 paste regions = 161 pads);
  every via is flashed on F.Cu and B.Cu. No Gerber viewer was run: look at the JLCPCB preview.
- Top-level ZIPs and `assembly/` CSVs are byte-identical to `carrier/` and `panel/`.
- Printed panel `panels/front-cad/`: script re-run, asserts pass, STL byte-identical (holes unchanged).

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
