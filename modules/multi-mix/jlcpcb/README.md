# multi-mix — manufacturing export (carrier S5/R3, MCU board S4/R3, 20HP panel P4)

Exported on 2026-11-11 after the MIDI IN jack change (`docs/research.md` section 11), with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction ("make it fab ready").
Never hand-edit these files: change the sources, then re-export with the commands below.

> **Prototype order set, not order-approved.** Open gates before you order: (1) two courtyard items on
> panel-fixed parts need your OK (MCU board J101 USB-C 0.53 mm from the MS3 notch edge, carrier MS3
> 0.98 mm from the top edge; `docs/research.md` section 10); (2) the 10 Extended R/C placements below
> need your OK (or Basic substitutes); (3) C1562 (C101/C102) failed today's exact lookup — confirm it in
> the JLCPCB part preview; (4) the shared assembly audit's per-part rating/role reviews are unrecorded
> (`unknown`, as on every module here), so the audit exits 1; (5) JLCPCB's own part/placement preview
> (rotation, pin 1, bottom side) and the quote options below are manual. No firmware exists and nothing
> is bench-tested: the U3 stencil, the Q1 temperature and the I2S clock rate (CH32V307 rated 8 MHz,
> `docs/research.md` 6a F1) are prototype risks, not proven by these files.

The module has two KiCad projects in one `hardware/` directory, so it keeps one manifest per
board set (`main/`, `mcu/`), declared as `source_manifest` in `tools/kicad-project.json` and
`tools/kicad-project-mcu.json` (as modules/usb-audio-max).

## Contents

| Path | Data |
|---|---|
| `main/multi-mix-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `main/multi-mix-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `main/assembly/bom.csv`, `main/assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `main/carrier/` | Carrier export: ZIP unpacked (4 copper layers: F / In1 GND / In2 +3V3 + +5VA + 2 x +3V3_C / B, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `main/panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `main/source-sha256.json` | Carrier + panel sources and export SHA-256 |
| `mcu/multi-mix-mcu-gerbers.zip` | MCU board Gerber/drill ZIP (upload this) |
| `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | MCU board BOM and CPL (upload these) |
| `mcu/board/` | MCU board export: ZIP unpacked, BOM, CPL, export report |
| `mcu/source-sha256.json` | MCU board sources and export SHA-256 |

The ZIPs beside each `assembly/` and the `assembly/` CSVs are byte-identical copies of the files
in `main/carrier/`, `main/panel/` and `mcu/board/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `main/multi-mix-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 100.0 x 110.0 mm, 1 oz outer, HASL, stackup JLC04161H-7628. Tented vias, no via-in-pad / POFV (no routing vias in SMD pads). Vias 0.6/0.3 mm (294) + ten 0.5/0.2 mm (DAC pin fan-out at the codec). **Min hole 0.2 mm**: those ten and the 36 PCM3168A PowerPAD thermal holes (footprint-owned, inside U3's exposed pad) — check the 0.2 mm drill option/price in the quote. Jack legs are 1.6 x 0.6 mm plated slots (36), pot lugs 1.1 x 2.3 mm slots (30). 3 x 3.2 mm NPTH (standoffs). No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `main/assembly/bom.csv`, `main/assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 203 parts in 46 BOM rows, all on the back |
| MCU board PCB | `mcu/multi-mix-mcu-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 35.45 mm (notched outline), same base options as the carrier; **explicit JLC04161H-7628 stack and USB targets below**. Min hole 0.3 mm (59 vias 0.6/0.3). The USB-C shell legs are plated slots |
| MCU board assembly | `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | **Economic PCBA, assembly side: Top.** 25 parts in 13 BOM rows, all on the front, J101 USB-C included |
| Front panel PCB | `main/multi-mix-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 101.3 x 128.5 mm (20HP), no copper, no assembly. 34 round NPTH (15 x 7.2 pots, 12 x 6.2 jacks incl. the new MIDI IN hole H35, 7 x 3.2) + the 9.5 x 3.7 mm USB-C slot |

### USB fabrication constraints (MCU board)

Do not substitute an arbitrary four-layer stack. The MCU PCB records the JLC04161H-7628 stack and keeps
modules/usb-audio's USB geometry (0.30 mm coupled / 0.20 mm gap on F over In1 GND, 0.40 mm single-ended
fan-outs, B crossovers over the stitched In2 GND island). `tools/check_usb.py` passes on the exported
board (pair mismatch 0.27 / 0.02 mm; IPC-2141 estimate 88.6 ohm differential / 45.7 ohm single). Request
**90 ohm differential / 45 ohm single-ended** targets and fabricator confirmation. Nominal analytic
figures, not a supplier measurement or a USB compliance test.

### PCM3168A (U3) PowerPAD land and Q1 heat

Same footprint and rules as modules/usb-audio-max (its `jlcpcb/README.md`): mask opened to 7.4 x 7.4 mm,
25 paste dots between the 36 thermal holes; Q1 BCP56 has F (188 mm2) and B (68 mm2) `/V5_IN` pours tied
by 11 thermal vias beside the tab. Paste coverage and Q1 temperature are bench items.

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J5, J101, J201, J301, J401, J9, J10, **J11** | QingPu WQP-PJ301M-12 TS jack (12; J11 = MIDI IN) | Carrier F-side THT, panel-nut fixed; fit to the panel before soldering. Trim the J11 tip lead to <= 2 mm (CLK IN ribbon socket beside it) and the J10 TN/S leads to <= 1.5 mm (power socket) |
| 15 x RV | RV09 50k B pot | Carrier F-side THT, panel-fixed |
| J8 | 2x5 2.54 mm pin header | Eurorack power, carrier back (silk `-12V`) |
| J7 | 2x5 2.54 mm pin header, **unshrouded** (S5) | CLK IN, carrier back, right edge. Not keyed: ribbon red wire on pin 1 (silk `CLK IN - NOT POWER`) |
| J6 | 2x5 2.54 mm keyed IDC box header | CLK OUT, carrier back, left edge |
| J12, J13 (carrier) + J112, J113 (MCU board) | 1x12 2.54 mm male strips | One strip per side joins the two boards; buy one pair, not two. Solder the MCU board on with the panel fitted so the USB-C lines up with its slot |
| J15 | 1x4 2.54 mm pin header (SWD) | Optional, carrier back; only for a WCH-LinkE |
| MS1-MS3 | M3 x 10 mm F-F hex standoffs + 6 x M3 screws | Mechanical, carrier to panel |

The exporter excluded exactly these electrical refs: the 33 carrier THT refs as non-SMD
(`main/carrier/export-report.json`) and J112/J113 as "Excluded from BOM"
(`mcu/board/export-report.json`).

## Parts (strict-live audit, 2026-11-11 02:20 UTC, 5 boards)

`assembly.py audit --strict-live` on both BOM/CPL sets; raw reports and snapshots in
`research/midi/audit/` (ignored). 57 codes: **34 Basic, 22 Extended, 1 unresolved by exact lookup**;
every resolved code reported Economic-eligible (`componentProductType` 0). The audit exits 1 by design
(no requirements file; per-part rating/role reviews are human gates, as on every module).

- **New with the MIDI IN jack:** R85 100k C25803 and R86 10k C25804 (Basic), D4 BAT54S C47546 (Extended,
  already on the board as D3; 279,134 in stock). No new code.
- **Extended semis / others (one setup fee each):** PCM3168APAPR C529289 (**1508** in stock),
  CH32V307RCT6 C2988083 (1862), TYPE-C-31-D-15 C22464480 (**450**, the tightest), OPA1678IDR C192421
  (**847**), OPA1679IDR C2878631 (2742), 74HC4067PW C179326, 74LVC1G97DW-7 C460532 (4153),
  SN74LVC2G125DCTR C206035 (4694), SN74LVC2G34 C14461, BAT54S C47546, BCP56-16 C92221, TPS562208 C91301,
  REF5050AIDR C27804, 24.576 MHz oscillator C5203547, 8 MHz crystal C2682774, MWSA0402S inductor C408337,
  GZ2012D121TF ferrite C5671, K2-1808SN switches C92589, USBLC6-2SC6 C7519.
- **R/C that are not Basic (10 placements, as modules/usb-audio-max, user decision open):**
  C211-C216 2.2n C0G 0603 C33353 (Extended, 2844; no Basic C0G at 2.2n in 0603), R1/R2 33R 2512 1 W
  C53728 (Extended), R3/R8 2.2R 1206 C144499 (Extended).
- **C101/C102 33p C0G 0402 C1562** (MCU board): exact lookup came back ambiguous today (as on
  modules/usb-audio and usb-audio-max, where an earlier lookup recorded it Basic and Economic-eligible).
- **Q2 C20526**: catalog MPN text `MMBT3904(RANGE:100-300)` vs native `MMBT3904` (same C-code, hFE
  bin qualifier).

Stock is a public web count at the recorded lookup time, not a reservation. The JLCPCB part and
placement preview (rotation/pin 1, especially the bottom-side SOIC/SOT parts, D4 and U3) is a manual
order gate.

## Source identity

Taken from the manifests; the shared `check` re-hashes them and fails on drift (equal on 2026-11-11,
`research/midi/final-carrier`, `research/midi/final-mcu`).

- Carrier PCB `597fdfeb0abf45761ea1f366b7f013fb73281069db73c74bba759f6541a83f69`.
- Carrier project `903c3d129b5a8f9a47deda99a8f9a41a5ff34f18354ddc63ae27415bc33467e1`.
- Carrier schematic `c2daa88d55d8c97207057f5ff9b32fddf9ac6b21bf5f8edcc66e1ee6d088e23c`.
- MCU PCB `d407a6b9969528fc794cb0a215634d37a8480d32f5b752a6eaaf9418348a1c14`.
- MCU project `17b65b01655365de590162d86507d6f15a3184fe5ea9ef486420e190bbb96057`.
- MCU schematic `751af264da7fb73b279428f216ba2bff4968cba403355c29b9f719788cae5c23`.
- Panel PCB `1a5c47dc6eaa243b98177544e120d7381ad03e46d300778ddb7ab2b95f6ae97b`.
- Panel project `8520b46f31c39f02279f9b10ed2c98d7fb545e90468302ada3b8ddc26291883e`.

## Reproduce

Refill and save both boards first (the exporter plots the saved fills). Then, from
`modules/multi-mix`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project-mcu.json --reports research/native-mcu
(cd ../.. && python3 -B modules/multi-mix/tools/check_usb.py)

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board multi-mix --schematic multi-mix.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/carrier
unzip -o jlcpcb/main/carrier/multi-mix-gerbers.zip -d jlcpcb/main/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board multi-mix-panel --pcb-only \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/panel
unzip -o jlcpcb/main/panel/multi-mix-panel-gerbers.zip -d jlcpcb/main/panel

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board multi-mix-mcu --schematic multi-mix-mcu.kicad_sch --side top --require-part-numbers \
  --manifest jlcpcb/mcu/source-sha256.json --overwrite -o jlcpcb/mcu/board
unzip -o jlcpcb/mcu/board/multi-mix-mcu-gerbers.zip -d jlcpcb/mcu/board

cp jlcpcb/main/carrier/bom.csv jlcpcb/main/carrier/positions.csv jlcpcb/main/assembly/
cp jlcpcb/main/carrier/multi-mix-gerbers.zip jlcpcb/main/panel/multi-mix-panel-gerbers.zip jlcpcb/main/
cp jlcpcb/mcu/board/bom.csv jlcpcb/mcu/board/positions.csv jlcpcb/mcu/assembly/
cp jlcpcb/mcu/board/multi-mix-mcu-gerbers.zip jlcpcb/mcu/
```

Catalog audit, from the repository root:

```sh
python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/multi-mix/jlcpcb/main/carrier/bom.csv \
  --cpl modules/multi-mix/jlcpcb/main/carrier/positions.csv \
  --export-report modules/multi-mix/jlcpcb/main/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64
python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/multi-mix/jlcpcb/mcu/board/bom.csv \
  --cpl modules/multi-mix/jlcpcb/mcu/board/positions.csv \
  --export-report modules/multi-mix/jlcpcb/mcu/board/export-report.json \
  --boards 5 --side top --strict-live --max-requests 64
```
