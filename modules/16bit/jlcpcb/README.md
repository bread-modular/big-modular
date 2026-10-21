# 16bit — manufacturing export (S3/R2)

Generated on 2026-10-21 from the current S3 schematic and R2 hand-routed board with the
shared `opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit
these files: change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `16bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `16bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `16bit-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL (or ENIG), stackup JLC04161H-7628 (the board's stackup: 0.21 mm 7628 prepreg). **Via covering: tented**, no via-in-pad fill / POFV (no vias in SMD pads). **Min via hole: 0.25 mm** (U1's 9 footprint thermal vias, 0.25/0.6 mm; every routed via is 0.3/0.6 mm): pick the matching "min via hole size" option and check the quote. No `JLCJLCJLCJLC` marker: choose the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 86 parts in 43 BOM rows, all on the back |
| Front panel PCB | `16bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J5 | QingPu WQP-PJ301M-12 TS jack (MIDI, CV1, CV2, OUT L, OUT R) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV4 | RV09 50k linear pot | Front-side THT, no nut |
| SW1 | 6 x 6 mm THT tact switch (MODE) | Front-side THT |
| D1 | 3 mm red LED (MODE) | Front-side THT; set its height to the panel hole |
| J6 | 2x5 2.54 mm pin header | Eurorack power, back side |
| JP1 | 3-pad solder jumper (MIDI RX source) | Copper only, **shipped open**: bridge P (protected) or D (direct), never both |

The exporter excluded exactly the 12 THT refs plus JP1 (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-21 07:50 UTC, 5 boards)

Every C-code resolves to its MPN and package and is Economy-eligible (`research/export-1/`).

- **Resistors and capacitors: all JLCPCB Basic**, except **R9/R10 27 Ω 0402 (C25100,
  Extended, 75,329 in stock)**: LCSC has no Basic 27 Ω 0402, and 27 Ω is the RP2350 USB value.
  R30/R33 (1k 1206) moved from ROHM C2074262 (Extended) to UNI-ROYAL C4410 (Basic).
  C11702 (1k 0402, R5-R7) is Basic, Economy, 20.2 M in stock by live search; the shared exact
  lookup rejects it (its keyword search is truncated), so the audit lists it as unresolved.
- **Basic semis/ICs:** B5819W, 1N4148W, MMBT3904, W25Q128JVSIQ (C97521), TL072CDT,
  AMS1117-5.0/-3.3.
- **Extended (one setup fee each):** RP2350A C42411118 (5,951), APS6404L C5333729 (3,867),
  TM8211-TA2302 C22381766 (9,039), TL074CDR C12594, MCP6002T C7377 (preferred), ABM8-272-T3
  C20625731 (4,849), FTC201610S3R3MBCA C5832345 (1,411), TYPE-C-31-M-12 C165948,
  K2-1808SN-A4SW-01 C92589, BAT54SWT1G C78260, 27 Ω C25100.

Substitutions against Bread Modular 16bit, both on the same footprint with no copper change:

- **U4: TM8211-TA2302** in place of the PT8211 (C92004, stock 1). Bread Modular 16bit-5v uses
  it; same SOP-8 pinout. The schematic value stays `PT8211`.
- **L1: cjiang FTC201610S3R3MBCA** in place of the Abracon AOTA-B201610S3R3-101-T
  (C42411119, stock 3). It meets the RP2350 datasheet's numbers (3.3 µH ±20 %, DCR 170 mΩ max
  ≤ 250, Isat 2.0 A min ≥ 1.5, molded metal-powder, shielded) and fits `L_pol_2016` (2.0 x
  1.6 mm body, 2.0 mm pitch). **It has no polarity mark**, so its orientation on the reel
  is random and the silk dot can't be honoured. Check the core regulator (+1V1 ripple,
  load steps) at bring-up.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `d41f06236f673cf207ffececf37276732b4bd5ec2bc7526da5049dda2a144866`.
- Carrier project `c900706434bc85d82a08bdb539912c25897c19516f1e8bdc43f2ca29872212a0`.
- Carrier schematic `9935e4e437e30fb739d220f68360961cf3b1cbaf1a6d057371a65b86f555e251`.
- Panel PCB `f7c154c2fa2eaa191081287fe374488e83d9e63d06462710d1cc3388fad315c9`.
- Panel project `da9d97ae5b440cca0097db590d1f6c90e41f6a2c02534180f7577e4164a57822`.

## Reproduce

LCSC/MPN/Manufacturer come from `SOURCING` in `tools/build_schematic.py`. After a change,
rebuild the schematic and copy the fields onto the routed board's footprints (fields only,
not `tools/build_layout.py`, which would discard the hand routing). Then, from `modules/16bit`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 16bit --schematic 16bit.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/16bit-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 16bit-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/16bit-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/16bit-gerbers.zip jlcpcb/panel/16bit-panel-gerbers.zip jlcpcb/
```

Catalog audit (no requirements file yet):

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/16bit-symbols.xml hardware/16bit.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/16bit/hardware --board 16bit.kicad_pcb --symbols-xml /tmp/16bit-symbols.xml \
  --cpl modules/16bit/jlcpcb/carrier/positions.csv \
  --export-report modules/16bit/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export

- **Shared `check`** (after the export): ERC 0, DRC 0 (all severities), 0 unconnected,
  parity 0, 0 exclusions; manifest equal (5 sources, exports byte-identical).
  `order_ready: false`, as always for this tool.
- **Panel DRC:** 0 / 0.
- **Field sync:** only LCSC/MPN/Manufacturer/Note properties changed on the board; track and
  via count unchanged (830), copper untouched.
- **Carrier drill file:** 182 round PTH hits (145 vias + 9 U1 thermal vias + 28 round THT
  pads) plus 27 routed slots = 145 vias + 64 thru-hole pads (the 9 thermal vias included). 2 NPTH holes (USB-C pegs).
- **Panel drill file:** 13 NPTH holes, no copper holes.
- **Gerber ZIP:** all 4 copper layers with their pours, both masks, silkscreens and pastes,
  the edge, PTH/NPTH drills. F.Paste is empty: no front SMD parts.
- **BOM/CPL:** 86 parts, 43 rows, every row with LCSC, MPN and manufacturer; every CPL row
  is `bottom`.
- **Catalog audit:** fails only on the expected items: the 12 THT refs (no code, hand
  soldered), R9/R10 Extended, the C11702 lookup quirk, and per-part requirement/review rows
  that stay `unknown` without `docs/jlcpcb-audit-requirements.json`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly.** Confirm the quote offers **Bottom** for Economic on a
   4-layer board, with the QFN-60 (0.4 mm pitch) and the USB-C.
2. **Placement preview.** Check in JLCPCB's bottom-side preview:
   - U1 RP2350A (QFN-60) pin 1 and the U2-U7 SOIC pin-1 dots;
   - D2-D4 cathode bands, D5/D6 and Q1 (SOT) orientation;
   - J7 USB-C and SW2/SW3 sitting on their pads;
   - every rotation: bottom-side CPL rotations are the usual place for errors.
3. **Live recheck before ordering:** stock (L1 1,411 and APS6404L 3,867 are the thinnest),
   Basic/Extended class, minimum quantities and attrition. The figures above are a snapshot.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs, and the min-via-hole option above.
5. **Bench:** core regulator with the unmarked L1, U8 temperature (F9), MIDI JP1 both ways,
   real jack/pot panel fit.
