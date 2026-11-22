# usb-audio — manufacturing export (carrier S5 / P2 / R5, MCU board S1/R2)

Carrier re-exported on 2026-11-22 (03:31 UTC) for the **S5 / P2 / R5** carrier: S4 / R4 of the same
day (CS4272 codec, power header at the left edge, everything 8 mm lower, two M3x10 standoffs above the
MCU board; `../Code.md`) with NE5532 on U4 / U5 / U7 and the reference divider R49 / C38 / C39 in
place of the VCOM buffer U8 and C33. The panel set is the S4 export of the same day (panel sources
unchanged). Shared `opt/kicad-tools/jlcpcb/export.py` exporter. The MCU board is unchanged: its set was
re-exported the same day from the same sources (only the Gerber dates and the project-file hash in the
manifest differ; BOM and CPL are byte-identical). Never hand-edit these files: change the sources,
then re-export with the commands below.

The module has two KiCad projects in one `hardware/` directory, so it keeps one manifest per
board set (`main/`, `mcu/`), declared as `source_manifest` in `tools/kicad-project.json` and
`tools/kicad-project-mcu.json`. A shared manifest would merge the two `bom.csv` rows into one.

## Contents

| Path | Data |
|---|---|
| `main/usb-audio-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `main/usb-audio-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `main/assembly/bom.csv`, `main/assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `main/carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3 with the +5VA island, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `main/panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `main/source-sha256.json` | Carrier + panel sources and export SHA-256 |
| `mcu/usb-audio-mcu-gerbers.zip` | MCU board Gerber/drill ZIP (upload this) |
| `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | MCU board BOM and CPL (upload these) |
| `mcu/board/` | MCU board export: ZIP unpacked, BOM, CPL, export report |
| `mcu/source-sha256.json` | MCU board sources and export SHA-256 |

The ZIPs beside each `assembly/` and the `assembly/` CSVs are byte-identical copies of the files
in `main/carrier/`, `main/panel/` and `mcu/board/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `main/usb-audio-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL, stackup JLC04161H-7628. Tented vias, no via-in-pad / POFV (no vias in SMD pads). Min hole 0.3 mm (114 vias 0.3/0.6 mm), 2 NPTH 3.2 mm (standoffs). No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `main/assembly/bom.csv`, `main/assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 88 parts in 32 BOM rows, all on the back |
| MCU board PCB | `mcu/usb-audio-mcu-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 29.55 mm, same base options as the carrier; **explicit JLC04161H-7628 stack and USB impedance targets below**. Min hole 0.3 mm (49 vias: 48 at 0.6 mm diameter, U102 VBUS at 0.5 mm). The USB-C shell legs are plated slots (0.5 / 0.95 mm tools) |
| MCU board assembly | `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | **Economic PCBA, assembly side: Top.** 23 parts in 12 BOM rows, all on the front, J101 USB-C included |
| Front panel PCB | `main/usb-audio-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### USB fabrication constraints

Do not substitute an arbitrary four-layer stack. The MCU native PCB records the
JLC04161H-7628 stack (0.2104 mm outer prepreg, Er 4.4). The coupled USB section is
0.30 mm width / 0.20 mm gap, with 0.40 mm single-ended fanouts. Request **90 ohm
differential / 45 ohm single-ended** USB targets and fabricator confirmation. The
recorded 88.62 / 45.67 ohm values are nominal analytic estimates, not supplier
measurement or acceptance. In1 is GND; In2 retains +3V3 except a stitched USB GND
island beneath every B-side USB segment. See [repair details](../docs/usb-output-fix.md).

### Hand-soldered or fitted after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J2-J5 | QingPu WQP-PJ301M-12 TS jack (IN 1, IN 2, OUT 1, OUT 2) | Carrier F-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV4 | RV09 50k linear pot | Carrier F-side THT, no nut |
| J1 | 2x5 2.54 mm pin header | Eurorack power, carrier back, upright at the left edge; pin 1 / 2 (-12 V) at the bottom |
| J6, J7 (carrier) + J102, J103 (MCU board) | 1x10 2.54 mm male strips, 2.5 mm plastic | One strip per side joins the two boards (pin 10 GND). Solder the MCU board on with the panel and the standoffs fitted so the USB-C lines up with its slot |
| J8 | 1x4 2.54 mm pin header (SWD) | Optional, carrier back; only for a WCH-LinkE |
| MS1, MS2 | M3 x 10 mm F-F hex standoff + 2 x M3x6 screw each | Between the carrier and the panel above the MCU board (USB plug forces); not M3x8 |
| TP1 | Bare pad (MCLK) | Scope point, nothing fitted |

The exporter excluded exactly the 12 carrier THT refs as non-SMD and TP1 as "Excluded from BOM"
(`main/carrier/export-report.json`; the standoffs are mechanical footprints without a reference), and
J102/J103 as "Excluded from BOM" (`mcu/board/export-report.json`).

## Parts (live catalog audit, carrier 2026-11-22 03:31 UTC, MCU board 01:47 UTC, 5 boards each)

`assembly.py audit --strict-live` on both BOMs; raw snapshots and the tables in
`research/export-s5/` (carrier, S5) and `research/export-s4/` (MCU board) (ignored;
`free-stock-2026-11-22.json`). For every code the free stock
(`canPresaleNumber`) is far above the need and `minPurchaseNum` is 1: **no pre-order part**
(root `AGENTS.md`). All are Economic-eligible (`componentProductType` 0).

- **U4 / U5 / U7 are NE5532DR C7426** (Basic; listed 237,183, free 223,326, about $0.10): user
  choice for S5, as modules/multi-mix U8. Before, on the S4 export: OPA1656IDR C1849431 (Extended,
  about $1.1), which had replaced the pre-order-only OPA1678IDR C192421 (free -955, minimum
  purchase 13). Bipolar inputs: offsets in `../docs/research.md` section 9. Datasheet values.
- **New in S5:** R49 2.7k 0603 C13167 (Basic, free 765,286), C38 10u 0805 C15850 and C39 100n 0603
  C14663 (both already in the BOM). U8 and C33 are gone.
- **Carrier, Basic (24 rows):** every R/C except the two below, B5819W C8598, AMS1117-5.0 C6187
  (free 80,319), AMS1117-3.3 C6186, NE5532DR C7426.
- **Carrier, Extended (7 part types, 8 rows):** CS4272-CZZR C2151111 (listed 1,163, free 1,156),
  OPA1679IDR C2878631 (2,450 free), 24.576 MHz oscillator C5203547 (9,375 free), K2-1808SN-A4SW-01
  C92589 (12,693 free; SW1 and SW2 are two rows), GZ2012D121TF ferrite C5671 (111,932 free),
  C22/C23 2.2n C0G 0603 C107043 (304,271 free; C33353 is pre-order only), R1 33R 2512 1 W C53728
  (19,637 free). The 100p C0G (C14858) of the S4 filters is Basic, so the S3 1n C0G is gone.
- **MCU board (unchanged BOM):** CH32V307RCT6 C2988083 (listed 1,611, free 1,472), TYPE-C-31-D-15
  C22464480 (free 414), USBLC6-2SC6 C7519 (free 37,364) Extended; the other 9 rows Basic.

Stock is a public web count at the recorded lookup time, not a reservation: check again right
before ordering. The audit still reports its per-part requirement / review rows as `unknown`
(no `docs/jlcpcb-audit-requirements.json`) and the exporter warning for human reconciliation.

## Source identity

Taken from the manifests; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `6968c2ca1919e9dd17c3c611c31ba4374131cf1b1c1db580d4dcc9d33789e99b`.
- Carrier project `8e2a8b591aa88ecdd785bc4833e52a2276eb241fa942ce7a15af5f9123b74ebf`.
- Carrier schematic `2ef2465a99539fbf5955702f20a2310bc4bab9afe4ff2d6520064500be2871dd`.
- MCU PCB `57fb7b79e46997ecd9e7e4dcdf776cd3aed611b3a8c92895fcc015990066581b` (unchanged).
- MCU project `461c2ade8cd98aa29194a3737d39c01bf8db58812024cf96e9721967928167fd` (the file as
  committed; the 2026-10-24 manifest carried an older hash).
- MCU schematic `43e70f7855c31936ca631a70b1bd3d0c74125455bdd0d3efadcd9271dfb442f2` (unchanged).
- Panel PCB `ee53d49b038c0f63b992448de711562f8187d9a64841c3e5a4d4a3420e560978`.
- Panel project `9742319ffc9e26c7d1e061c14dd3f10fe0a9ccb5b08de1d4e744babafa57fb64`.

## Reproduce

LCSC/MPN/Manufacturer come from `SOURCING` in `tools/circuit_carrier.py` and
`tools/circuit_mcu.py`. After a change, rebuild the schematic and copy the fields onto the routed
board's footprints (fields only, never `tools/build_layout.py`, which would discard the routing).
Then, from `modules/usb-audio`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project-mcu.json --reports research/native-mcu

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-audio --schematic usb-audio.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/carrier
unzip -o jlcpcb/main/carrier/usb-audio-gerbers.zip -d jlcpcb/main/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board usb-audio-panel --pcb-only \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/panel
unzip -o jlcpcb/main/panel/usb-audio-panel-gerbers.zip -d jlcpcb/main/panel

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-audio-mcu --schematic usb-audio-mcu.kicad_sch --side top --require-part-numbers \
  --manifest jlcpcb/mcu/source-sha256.json --overwrite -o jlcpcb/mcu/board
unzip -o jlcpcb/mcu/board/usb-audio-mcu-gerbers.zip -d jlcpcb/mcu/board

cp jlcpcb/main/carrier/bom.csv jlcpcb/main/carrier/positions.csv jlcpcb/main/assembly/
cp jlcpcb/main/carrier/usb-audio-gerbers.zip jlcpcb/main/panel/usb-audio-panel-gerbers.zip jlcpcb/main/
cp jlcpcb/mcu/board/bom.csv jlcpcb/mcu/board/positions.csv jlcpcb/mcu/assembly/
cp jlcpcb/mcu/board/usb-audio-mcu-gerbers.zip jlcpcb/mcu/
```

Catalog audit (no requirements file yet), from the repository root:

```sh
python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/usb-audio/jlcpcb/main/carrier/bom.csv \
  --cpl modules/usb-audio/jlcpcb/main/carrier/positions.csv \
  --export-report modules/usb-audio/jlcpcb/main/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64
python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/usb-audio/jlcpcb/mcu/board/bom.csv \
  --cpl modules/usb-audio/jlcpcb/mcu/board/positions.csv \
  --export-report modules/usb-audio/jlcpcb/mcu/board/export-report.json \
  --boards 5 --side top --strict-live --max-requests 64
```

## Checks done for this export (2026-11-22)

- **Shared `check`, both boards, after the export:** ERC 0, DRC 0 (all severities, warnings
  included), 0 unconnected, parity 0, 0 exclusions; manifests equal (carrier + panel 5 sources, MCU 3
  sources), exports byte-identical. `order_ready: false`, as always for this tool.
- **Carrier copper:** 818 tracks / 114 vias, none in or touching an SMD pad, no tracks on In1 / In2;
  In2 +3V3 one piece, In2 +5VA island one piece, In1 GND one piece + two 1 mm2 slivers between the
  IN jacks' TN and S pads (both GND, tied by the pads' spokes). Fills saved.
- **Clearances:** courtyards >= 1.01 mm from the edge (J8), SMD pads >= 2.01 mm from pot / jack pads
  (SW2 to RV3; R19 to J2 2.03 mm) (`tools/check_edges.py`). Under the 16-pin IDC socket envelope
  only D1 / D2 (SOD-123) and the pin row of U2 (SOT-223) reach in, all lower than its 2.5 mm.
- **Carrier drill files:** PTH 114 vias (0.3 mm) and 46 round THT holes (1.0 mm) plus the routed
  jack / pot slots (0.6 / 1.1 mm); NPTH 2 x 3.2 mm (MS1 / MS2).
- **Panel drill file:** NPTH only: 2 x 3.2 mm rail holes, 2 x 3.2 mm standoff holes, 4 x 6.2 mm jacks,
  4 x 7.2 mm pots and the 9.5 x 5.2 mm USB-C slot; panel DRC 0.
- **BOM/CPL:** carrier 88 parts / 32 rows, all `bottom`; MCU 23 parts / 12 rows, all `top`;
  every row has LCSC, MPN and manufacturer.
- **Printed panel:** `../panels/front-cad/` regenerated from the panel PCB at the S4 export (13 holes
  + slot, asserted against `docs/geometry.json`); the panel did not change in S5, so it was not
  rebuilt.
- `tools/check_usb.py` (MCU board) was not rerun: that board is unchanged.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release, and the S5 carrier is not built.
Before ordering:

- **Firmware:** the CS4272 needs a new driver (register map, I2C address 0x10, MCLK ratio bits);
  firmware 1.1.0 does not run on this carrier.
- Recheck free stock and minimum purchase live (CS4272: about 1,150 free).
- In JLCPCB's preview, check every part match, centroid, rotation, pin 1 and polarity (U3 TSSOP-28
  pin 1, U4 / U5 / U7, U6, Y1, D1/D2, SW1/SW2; MCU board: U101 LQFP pin 1, U102, J101 shell legs).
- R1 (2512) and C22/C23 (C0G) stay Extended; other earlier review findings were deferred by the
  user and are not cleared here.
- Bench: the I2S start that failed on the first boards (the pull-downs and the short SCLK path
  are aimed at it; the root cause was never confirmed with a scope), VCOM_BUF (2.41 V from the
  R49 divider), offsets of the NE5532 followers against the pot position, levels, 192 kHz, thermal
  of U2 / R1.
