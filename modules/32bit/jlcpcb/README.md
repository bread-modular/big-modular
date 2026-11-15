# 32bit — manufacturing export (S3/R3)

Generated on 2026-11-15 from the S3 schematic (ESP32-S3R8 + W25Q128JVSIQ + 40 MHz crystal instead of the
ESP32-S3-WROOM-1U module) and the R3 hand-routed board with the shared `opt/kicad-tools/jlcpcb/export.py`
exporter. It replaces the S2/R2 export (2026-10-22). Only the carrier was re-exported; the panel export is
unchanged. Never hand-edit these files: change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `32bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `32bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `32bit-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL (or ENIG), stackup JLC04161H-7628 (the board's stackup: 0.21 mm 7628 prepreg). **Via covering: tented**, no via-in-pad fill / POFV (no vias in SMD pads). **Min via hole: 0.2 mm** (footprint thermal vias only: 9 in U1's exposed pad and 9 in U4's, 0.2 mm drill; every routed via, 130 of them, is 0.3/0.6 mm). No `JLCJLCJLCJLC` marker: choose the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Assembly side: Bottom.** 103 parts in 43 BOM rows, all on the back. **PCBA service: Economic** (no Standard-only part since S3; confirm in the quote) |
| Front panel PCB | `32bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### S3: no Standard-only part

Until S2 the ESP32-S3-WROOM-1U-N16R8 (C3013946) forced Standard PCBA for the whole carrier: no Espressif
module is Economic-eligible (live catalog 2026-11-15). S3 uses the module's contents instead:

| Ref | Part | LCSC | Notes (live catalog 2026-11-15, a web count, not a reservation) |
|---|---|---|---|
| U1 | ESP32-S3R8, QFN-56 7 x 7 mm, 0.4 mm pitch, exposed pad | C2913194 | Extended, Economic-eligible; listed stock 21,376 (the same number as the WROOM-1U listing: recheck) |
| U2 | W25Q128JVSIQ, SOIC-8 208 mil | C97521 | Basic, 82,492 |
| Y1 | 40 MHz 3225 crystal, 10 pF, X322540MMB4SI | C5210647 | Extended; recheck stock and eligibility in the quote |
| C9, C10 | 12p C0G 0402 | C1547 | |
| R6 / R7 | 0R 0402 / 0R 0603 | C17168 / C21189 | |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J5, J8, J9 | QingPu WQP-PJ301M-12 TS jack (MIDI, CV1, CV2, OUT L, OUT R, IN L, IN R) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1, RV2 | RV09 50k linear pot | Front-side THT, no nut |
| SW1 | 6 x 6 mm THT tact switch (MODE) | Front-side THT |
| D1 | 3 mm red LED (MODE) | Front-side THT; set its height to the panel hole |
| J6 | 2x5 2.54 mm pin header | Eurorack power, back side |
| JP1 | 3-pad solder jumper (MIDI RX source) | Copper only, **shipped open**: bridge P (protected, firmware inverts RX) or D (direct), never both |

None of these 13 refs is in the BOM/CPL (`carrier/export-report.json` lists the excluded refs).

## Parts

The S2 parts keep their 2026-10-22 audit (all resistors and capacitors Basic; B5819W, 1N4148W, MMBT3904,
TL072CDT, AMS1117-5.0 / -3.3 Basic; ES8388 C365736, TL074CDR C12594, MCP6002T C7377, BAT54SWT1G C78260,
GZ2012D121TF C5671, TYPE-C-31-M-12 C165948, K2-1808SN-A4SW-01 C92589 Extended and Economic-eligible).
The S3 parts are in the table above. The full `assembly.py audit` was **not** rerun for S3: run it (command
below) and recheck stock before ordering.

## Source identity

In `source-sha256.json` (rewritten by the 2026-11-15 export); the shared `check` re-hashes the five
sources and fails on drift. Checked after the export: manifest equal.

## Reproduce

LCSC/MPN/Manufacturer come from `SOURCING` in `tools/circuit32.py`. After a change, rebuild the
schematic and copy the fields onto the routed board's footprints (fields only, not
`tools/build_layout.py`, which would discard the hand routing). Then, from `modules/32bit`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 32bit --schematic 32bit.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/32bit-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 32bit-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/32bit-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/32bit-gerbers.zip jlcpcb/panel/32bit-panel-gerbers.zip jlcpcb/
```

Catalog audit (no requirements file yet):

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/32bit-symbols.xml hardware/32bit.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/32bit/hardware --board 32bit.kicad_pcb --symbols-xml /tmp/32bit-symbols.xml \
  --cpl modules/32bit/jlcpcb/carrier/positions.csv \
  --export-report modules/32bit/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export (2026-11-15)

- **Shared `check`** (after the export): ERC 0, DRC 0 (all severities), 0 unconnected, parity 0,
  0 exclusions; manifest equal (5 sources, exports byte-identical). `order_ready: false`, as always for
  this tool. Reports in `research/s3/check-export/` (ignored).
- Zones refilled and saved before the export; DRC on the saved fills: 0 / 0 / 0.
- **BOM/CPL:** 103 parts, 43 rows, every row with LCSC, MPN and manufacturer; the hand-fitted refs above are left out.
- **Panel:** not re-exported (source unchanged since the 2026-10-27 rail-hole move).
- Not done: Gerber / drill review by eye, the live catalog audit for the whole BOM, JLCPCB preview.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

- Order the carrier with Economic PCBA; if the quote forces Standard, find the part that does it first.
- Recheck stock, classification and PCBA service eligibility live; check attrition and minimums.
- In JLCPCB's preview, check every part match, centroid, rotation, pin 1 and polarity
  (U1 QFN-56 pin 1, U2 pin 1, Y1, U4 QFN pin 1, D2-D6, U5-U9, J7).
- Bench: first power-up of the bare-chip circuit (40 MHz start-up, flash boot, PSRAM, USB download with
  BOOT / RESET), U8 temperature, codec input/output levels, MIDI with JP1 in both positions.
