# 32bit — manufacturing export (S4: carrier S4 / R1, MCU board S1 / R1)

Exported on 2026-11-23 for **S4**: the modules/usb-audio S5 carrier (CS4272, NE5532, AMS1117 +5VA,
2 in / 2 out, two firmware control pots + MODE + LED, two M3x10 standoffs) and a separate ESP32-S3 MCU
board (ESP32-S3R8 + W25Q128JVSIQ + 40 MHz crystal, panel USB-C) soldered on two 1x10 strips
(`../docs/research.md` section 9). It replaces the S3 / R3 export (2026-11-15, single board, in git
history). Shared `opt/kicad-tools/jlcpcb/export.py` exporter. Two separate orders, no panelization (user,
2026-11-23: the boards share no part code, so a panel saves no feeder fees). Never hand-edit these
files: change the sources, then re-export with the commands below.

The module has two KiCad projects in one `hardware/` directory, so it keeps one manifest per board set
(`main/`, `mcu/`), declared as `source_manifest` in `tools/kicad-project.json` and
`tools/kicad-project-mcu.json`.

## Contents

| Path | Data |
|---|---|
| `main/32bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `main/32bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `main/assembly/bom.csv`, `main/assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `main/carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3 with the +5VA island, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `main/panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `main/source-sha256.json` | Carrier + panel sources and export SHA-256 |
| `mcu/32bit-mcu-gerbers.zip` | MCU board Gerber/drill ZIP (upload this) |
| `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | MCU board BOM and CPL (upload these) |
| `mcu/board/` | MCU board export: ZIP unpacked, BOM, CPL, export report |
| `mcu/source-sha256.json` | MCU board sources and export SHA-256 |

The ZIPs beside each `assembly/` and the `assembly/` CSVs are byte-identical copies of the files in
`main/carrier/`, `main/panel/` and `mcu/board/` (checked with `cmp`).

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `main/32bit-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL, stackup JLC04161H-7628. Tented vias, no via-in-pad / POFV (no vias in SMD pads). Min hole 0.3 mm (117 vias 0.3/0.6 mm), 2 NPTH 3.2 mm (standoffs). No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `main/assembly/bom.csv`, `main/assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 88 parts in 33 BOM rows, all on the back |
| MCU board PCB | `mcu/32bit-mcu-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 29.55 mm, same base options; the board records the JLC04161H-7628 stack. Min via hole 0.3 mm (41 vias: 39 at 0.6 mm, two at 0.5 mm under the U102 body); the U101 exposed-pad thermal vias are 0.2 mm holes; the USB-C shell legs are plated slots |
| MCU board assembly | `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | **Economic PCBA, assembly side: Top.** 25 parts in 14 BOM rows, all on the front, J101 USB-C included |
| Front panel PCB | `main/32bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### Hand-soldered or fitted after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J2-J5 | QingPu WQP-PJ301M-12 TS jack (IN L, IN R, OUT L, OUT R) | Carrier F-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1, RV2 | RV09 50k linear pot | Carrier F-side THT, no nut; control pots read by the ESP32 |
| SW3, D3 | MODE tact switch, 3 mm LED | Carrier F-side THT behind the panel |
| J1 | 2x5 2.54 mm pin header | Eurorack power, carrier back, upright at the side edge; pin 1 / 2 (-12 V) at the bottom |
| J6, J7 (carrier) + J102, J103 (MCU board) | 1x10 2.54 mm male strips, 2.5 mm plastic | Join the two boards. Solder the MCU board on with the panel and the standoffs fitted so the USB-C lines up with its slot. **J6 differs from modules/usb-audio: the MCU boards are not interchangeable** (B silk "J6: 32BIT ONLY") |
| MS1, MS2 | M3 x 10 mm F-F hex standoff + 2 x M3x6 screw each | Between the carrier and the panel above the MCU board (USB plug forces) |
| TP1 | Bare pad (MCLK) | Scope point, nothing fitted |

The exporter excluded exactly the 11 carrier THT refs (D3, J1-J7, RV1, RV2, SW3) as non-SMD and TP1 as
"Excluded from BOM" (`main/carrier/export-report.json`; the standoffs are mechanical footprints without a
reference), and J102 / J103 as "Excluded from BOM" (`mcu/board/export-report.json`).

## Parts (live catalog check, 2026-11-23, 5 boards each)

Every code of both BOMs was looked up live on the JLCPCB catalog endpoint of
`opt/kicad-tools/jlcpcb/catalog.py`; snapshot in `research/export-s4/free-stock/` (ignored,
`free-stock-2026-11-23.json` + raw responses). For every code the free stock (`canPresaleNumber`) is above
the need (placements x 5 + attrition) and `minPurchaseNum` is 1: **no pre-order part** (root `AGENTS.md`).
All are Economic-eligible (`componentProductType` 0). The `assembly.py audit` tables (not strict-live) are
in `research/export-s4/audit/`.

- **Carrier, Extended (7 part types, 8 rows):** CS4272-CZZR C2151111 (listed 1,153, free 1,147), OPA1679IDR
  C2878631 (free 2,411), 24.576 MHz oscillator C5203547 (free 9,369), K2-1808SN-A4SW-01 C92589 (free 12,670;
  RESET and BOOT are two rows), GZ2012D121TF ferrite C5671 (free 111,800), C22/C23 2.2n C0G C107043 (free
  256,161), **R1 22R 2512 1 W C118189** (free 50,145; 22R instead of usb-audio's 33R for the ESP32-S3
  +3V3 budget, section 9.1).
- **Carrier, Basic (25 rows):** every other R/C, B5819W C8598, AMS1117-5.0 C6187 (free 78,964), AMS1117-3.3
  C6186, NE5532DR C7426 (free 222,147).
- **MCU board, Extended (4 part types):** ESP32-S3R8 C2913194 (listed 19,870, free 18,934), TYPE-C-31-D-15
  C22464480 (**listed 421, free 414**), 40 MHz crystal C5210647 (free 5,525), USBLC6-2SC6 C7519 (free
  34,197). Basic: W25Q128JVSIQ C97521 (free 65,665) and every 0402 R/C.

The two boards share no LCSC code, so an Extended part type is loaded once per order either way (11
types). Stock is a public web count at the lookup time, not a reservation: check again right before
ordering (the USB-C and the CS4272 are the low ones).

## Source identity

Taken from the manifests; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `fd3f21daff750cfc1a3068cc6c89a120646e8cc77d63e383f1a99268470e67df`.
- Carrier project `c1b52ac8635a3d187ea1e1b1af6883099efcdfd15bb386f330088047bf58d91d`.
- Carrier schematic `6f17eea5b6436eb0a7749e03902da47cbfb437dd19a834576da0a9a8ac0471ab`.
- MCU PCB `277a77d54f1d7a108d38878efc5ad800db1ed3e96179a10e314e91cc3efce78d`.
- MCU project `9dfc412aa0ab710ef5b0f7899dd71049ce045d1abcc7ce70526600df46eb804b`.
- MCU schematic `672c098fced40a25ff3e7be9f6fb4c7c20b1a6f69304d7b46dfd9f2977753162`.
- Panel PCB `2a49f615078d521b29aee934b81e9efa7cc9d4b0ee5c875c6eb9e416cb1734ba`.
- Panel project `72a3c93bad51d8f3a4c9a36470036ccc7511879dc53289f3a1d303f67b535dc3`.

## Reproduce

LCSC/MPN/Manufacturer come from `SOURCING` in `tools/circuit_carrier.py` and `tools/circuit_mcu.py`.
After a change, rebuild the schematic and copy the fields onto the routed board's footprints (fields only,
never `tools/build_layout.py`, which would discard the routing). Then, from `modules/32bit`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project-mcu.json --reports research/native-mcu

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 32bit --schematic 32bit.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/carrier
unzip -o jlcpcb/main/carrier/32bit-gerbers.zip -d jlcpcb/main/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 32bit-panel --pcb-only \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/panel
unzip -o jlcpcb/main/panel/32bit-panel-gerbers.zip -d jlcpcb/main/panel

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 32bit-mcu --schematic 32bit-mcu.kicad_sch --side top --require-part-numbers \
  --manifest jlcpcb/mcu/source-sha256.json --overwrite -o jlcpcb/mcu/board
unzip -o jlcpcb/mcu/board/32bit-mcu-gerbers.zip -d jlcpcb/mcu/board

cp jlcpcb/main/carrier/bom.csv jlcpcb/main/carrier/positions.csv jlcpcb/main/assembly/
cp jlcpcb/main/carrier/32bit-gerbers.zip jlcpcb/main/panel/32bit-panel-gerbers.zip jlcpcb/main/
cp jlcpcb/mcu/board/bom.csv jlcpcb/mcu/board/positions.csv jlcpcb/mcu/assembly/
cp jlcpcb/mcu/board/32bit-mcu-gerbers.zip jlcpcb/mcu/
```

Catalog audit, from the repository root (as modules/usb-audio, with `--boards 5 --strict-live
--max-requests 64`, `--side bottom` for `main/carrier/` and `--side top` for `mcu/board/`).

## Checks done for this export (2026-11-23)

- **Shared `check`, both boards, after the export:** ERC 0, DRC 0 (all severities), 0 unconnected,
  parity 0, 0 exclusions; manifests equal (carrier + panel 5 sources, MCU 3 sources), exports
  byte-identical. `order_ready: false`, as always for this tool.
- **Copper** (`../docs/research.md` section 9.1): carrier 753 tracks / 117 vias, MCU board 239 / 41; no via
  in an SMD pad, no inner-layer tracks, planes one piece (carrier In1 + the two pad-tied slivers usb-audio
  has). Courtyards >= 1.02 mm (carrier) / 1.06 mm (MCU board) from the edge, SMD >= 2.03 mm from pot / jack
  pads.
- **BOM/CPL:** carrier 88 parts / 33 rows, all `bottom`; MCU 25 parts / 14 rows, all `top`; every row has
  LCSC, MPN and manufacturer.
- **Panel drill file:** NPTH only: rail and standoff holes 3.2 mm, LED 3.2 mm, MODE 4.2 mm, 4 x 6.2 mm jacks,
  2 x 7.2 mm pots, the 5.2 mm wide USB-C slot. Printed panel `../panels/front-cad/` was regenerated from
  this panel PCB in the S4 layout task (asserted against `docs/geometry.json`); the panel did not change
  since.
- **USB (`tools/check_usb.py`, MCU board, `research/export-s4/check_usb.json`):** the script is the
  modules/usb-audio high-speed check (pins re-mapped to the ESP32-S3, pad-tolerant path search). It
  reports the HS criteria as failed: D+ / D- layer transitions differ on the connector leg, path mismatch
  1.1 mm (A side) / 3.5 mm (B side) against its 0.5 mm bound, and about 10 mm of B-side USB track runs
  over the In2 +3V3 plane with no GND island. **Judged fine for this board, not waived:** the ESP32-S3 USB
  is full speed (12 Mbit/s); 3.5 mm is about 20 ps against FS edges of 4..20 ns, and +3V3 is an AC
  reference through its decoupling. A future revision can tidy it; nothing was re-routed.

## Status and order gates (not done here)

Complete export, not a supplier-accepted release; S4 is not built. Before ordering:

- **Firmware:** `master` needs a CS4272 driver (I2C 0x10, ESP32-S3 as I2S slave to the codec's 24.576 MHz
  clock), shared with modules/usb-audio; no CS4272 board has been built yet.
- Recheck free stock and minimum purchase live (USB-C 414 free, CS4272 1,147 free).
- In JLCPCB's preview, check every part match, centroid, rotation, pin 1 and polarity (carrier: U3
  TSSOP-28 pin 1, U4 / U5 / U7, U6, Y1, D1 / D2, SW1 / SW2; MCU board: U101 QFN-56 pin 1 and exposed pad,
  U102, U103, Y101, J101 shell legs).
- Bench: +3V3 current and U2 / R1 heat (22R 1 W, 0.37 W at 130 mA), 40 MHz start-up, flash boot and PSRAM,
  USB enumeration, the I2S start, noise floor against the usb-audio board.
