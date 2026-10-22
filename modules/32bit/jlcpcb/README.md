# 32bit — manufacturing export (S2/R2)

Generated on 2026-10-22 from the S2 schematic and the R2 hand-routed board (2 mm hand-solder
clearance pass, user edge-margin moves, B silk MIDI JP1 labels; not yet committed) with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. It replaces the R1 export. Never hand-edit
these files: change the sources, then re-export with the commands below.

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
| Carrier PCB | `32bit-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL (or ENIG), stackup JLC04161H-7628 (the board's stackup: 0.21 mm 7628 prepreg). **Via covering: tented**, no via-in-pad fill / POFV (no vias in SMD pads). **Min via hole: 0.2 mm** (footprint thermal vias: 12 in U1's GND pad at 0.2/0.6 mm, 9 in U4's EP at 0.2/0.5 mm; every routed via, 106 of them, is 0.3/0.6 mm). This is the same drill set as Bread Modular 32bit-5v, whose shipped `32bit-5v-PTH.drl` has the same 21 x 0.2 mm thermal-via hits (same ESP32 and ES8388 footprints) and 0.3 mm routed vias, and which JLCPCB has fabricated: keep it, pick the 0.2 mm "min via hole size" option. No `JLCJLCJLCJLC` marker: choose the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Assembly side: Bottom.** 90 parts in 38 BOM rows, all on the back. **PCBA service: Standard** (U1, below) |
| Front panel PCB | `32bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### U1 is Standard-PCBA only: Standard PCBA chosen

The ESP32-S3-WROOM-1U-N16R8 (C3013946, Extended, 25,291 in stock) is **not Economic-PCBA
eligible** (live catalog, 2026-10-22 08:12 UTC: `componentProductType` 2, "Standard only"). It is
the only JLCPCB listing for that MPN. Every other part is Economy-eligible. **User decision
(2026-10-22): Standard PCBA for the whole carrier**, files as they are (U1 assembled by JLCPCB).

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J5, J8, J9 | QingPu WQP-PJ301M-12 TS jack (MIDI, CV1, CV2, OUT L, OUT R, IN L, IN R) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1, RV2 | RV09 50k linear pot | Front-side THT, no nut |
| SW1 | 6 x 6 mm THT tact switch (MODE) | Front-side THT |
| D1 | 3 mm red LED (MODE) | Front-side THT; set its height to the panel hole |
| J6 | 2x5 2.54 mm pin header | Eurorack power, back side |
| JP1 | 3-pad solder jumper (MIDI RX source) | Copper only, **shipped open**: bridge P (protected, firmware inverts RX) or D (direct), never both |

The exporter excluded exactly these 12 THT refs plus JP1 (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-22 08:11 UTC, 5 boards; R1 audit, BOM unchanged in R2)

Every C-code resolves to its MPN and package (`research/export-1/audit.txt`, ignored).

- **Resistors and capacitors: all JLCPCB Basic and Economy-eligible**, no exceptions.
- **Basic semis/ICs:** B5819W (C8598), 1N4148W (C81598), MMBT3904 (C20526), TL072CDT (C6961),
  AMS1117-5.0 (C6187), AMS1117-3.3 (C6186).
- **Extended (one setup fee each), Economy-eligible:** ES8388 C365736 (43,301), TL074CDR C12594
  (117,141), MCP6002T C7377 (preferred Extended, 61,765), BAT54SWT1G C78260 (32,794),
  GZ2012D121TF ferrite C5671 (42,446), TYPE-C-31-M-12 C165948 (333,192), K2-1808SN-A4SW-01
  C92589 (10,375).
- **Extended, Standard PCBA only:** ESP32-S3-WROOM-1U-N16R8 C3013946 (25,291), see above.

Stock is a public web count at that time, not a reservation.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `2b56e3551c071bbe482590116e8ce5d201769e01ba36a7be5d46dfea3a3cdf11`.
- Carrier project `ba49573f1309ebb3ec65eb62ae903295a5a3efc6a6a57185a895abab7cfe03ad`.
- Carrier schematic `db630e9ff2f68f8567e658e9e4f2509087f7b2dea860fcf4b79c4ca978c7b775`.
- Panel PCB `bd9ab573a13d5bb2c5cdb118d0280583f45c3309063bd47b1a28f82c82a49191`.
- Panel project `72a3c93bad51d8f3a4c9a36470036ccc7511879dc53289f3a1d303f67b535dc3`.

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

## Checks done for this export

- **Shared `check`** (after the R2 export): ERC 0, DRC 0 (all severities), 0 unconnected,
  parity 0, 0 exclusions; manifest equal (5 sources, exports byte-identical).
  `order_ready: false`, as always for this tool. Reports in `research/export-r2/` (ignored).
- **Carrier drill file:** 149 round PTH hits (106 routed vias, 21 footprint thermal vias,
  22 round THT pads) plus the routed slots; 2 NPTH holes (USB-C pegs).
- **Panel drill file:** 13 NPTH holes, no copper holes.
- **Gerber ZIP:** all 4 copper layers with their pours, both masks, silkscreens and pastes,
  the edge, PTH/NPTH drills. F.Paste is empty: no front SMD parts.
- **BOM/CPL:** 90 parts, 38 rows, every row with LCSC, MPN and manufacturer; every CPL row
  is `bottom` and matches its footprint's position on the R2 board (90 / 90). The BOM is
  byte-identical to R1; 43 CPL rows moved with the R2 parts.
- **Panel:** re-exported from the unchanged panel source; Gerbers equal to R1 apart from dates.
- **Catalog audit (R1, same BOM):** fails on the U1 Economy item above, on the 12 THT refs (no code, hand
  soldered), and on per-part requirement/review rows that stay `unknown` without
  `docs/jlcpcb-audit-requirements.json`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

- Order the carrier with Standard PCBA (U1, above).
- Recheck stock, classification and PCBA service eligibility live; check attrition and minimums.
- In JLCPCB's preview, check every part match, centroid, rotation, pin 1 and polarity
  (U1 antenna connector, U4 QFN pin 1, D2-D6, U5-U9, J7).
- Bench: U8 temperature, codec input/output levels, MIDI with JP1 in both positions.
