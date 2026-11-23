# usb-audio-max — manufacturing export (carrier S3/R2 with the clock link, MCU board S2/R1, 12HP panel)

`main/` (carrier + panel) re-exported on 2026-11-20 for the S3 / R2 carrier: the modules/multi-mix clock
link (CLK OUT J6 / CLK IN J7, 21 more SMD parts), carrier and panel widened from 10HP to 12HP. `mcu/` is
the 2026-11-08 export, unchanged (same MCU board, same files). **Panel set re-exported on 2026-11-23: USB-C
slot 9.5 -> 11.0 x 5.2 mm (`../panels/README.md`); carrier set untouched.** Shared `opt/kicad-tools/jlcpcb/export.py`
exporter. Never hand-edit these files: change the sources, then re-export with the commands below.
The fab-review fixes of 2026-11-08 (F1 MCU fills saved, F2 Q1 collector copper, F3 PCM3168A land) are
unchanged in S3 / R2.

> **Prototype order set, not order-approved.** Open gates before you order: (0) the S3 clock link is
> new copper that no built board has run, and firmware 1.1.0 does not start a linked (slave) unit yet
> (`../firmware/README.md`); (1) the 10 Extended R/C placements below need your OK (or Basic
> substitutes); (2) C1562 (C101/C102, MCU board) failed the 2026-11-08 exact lookup — confirm it in the
> JLCPCB part preview; (3) the shared assembly audit's per-part rating/role
> reviews are unrecorded (`unknown`, as on every module here), so the audit exits 1; (4) JLCPCB's own
> part/placement preview (rotation, pin 1, bottom side) and the quote options below are manual. The
> U3 stencil and the Q1 temperature are prototype risks for the bench, not proven by these files.

The module has two KiCad projects in one `hardware/` directory, so it keeps one manifest per
board set (`main/`, `mcu/`), declared as `source_manifest` in `tools/kicad-project.json` and
`tools/kicad-project-mcu.json` (as modules/usb-audio).

## Contents

| Path | Data |
|---|---|
| `main/usb-audio-max-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `main/usb-audio-max-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `main/assembly/bom.csv`, `main/assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `main/carrier/` | Carrier export: ZIP unpacked (4 copper layers: F / In1 GND / In2 +12V_F + +5VA + 2 x +3V3_C / B; the U4 +3V3_C island now reaches the CLK IN receiver, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `main/panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `main/source-sha256.json` | Carrier + panel sources and export SHA-256 |
| `mcu/usb-audio-max-mcu-gerbers.zip` | MCU board Gerber/drill ZIP (upload this) |
| `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | MCU board BOM and CPL (upload these) |
| `mcu/board/` | MCU board export: ZIP unpacked, BOM, CPL, export report |
| `mcu/source-sha256.json` | MCU board sources and export SHA-256 |

The ZIPs beside each `assembly/` and the `assembly/` CSVs are byte-identical copies of the files
in `main/carrier/`, `main/panel/` and `mcu/board/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `main/usb-audio-max-gerbers.zip` | **4 layers**, FR4, 1.6 mm, **59.6 x 110.0 mm**, 1 oz outer, HASL, stackup JLC04161H-7628. Tented vias, no via-in-pad / POFV (no routing vias in SMD pads). Vias 0.6/0.3 mm (252) + one 0.5/0.3. **Min hole 0.2 mm**: the 36 PCM3168A PowerPAD thermal holes (footprint-owned, inside U3's exposed pad, tented on the far side) — check the 0.2 mm drill option/price in the quote. Jack legs are 1.6 x 0.6 mm plated slots. No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `main/assembly/bom.csv`, `main/assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 200 parts in 42 BOM rows, all on the back |
| MCU board PCB | `mcu/usb-audio-max-mcu-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 29.55 mm, same base options as the carrier; **explicit JLC04161H-7628 stack and USB impedance targets below**. Min hole 0.3 mm (59 vias: 58 at 0.6 mm, one 0.5 mm). The USB-C shell legs are plated slots (0.5 / 0.95 mm tools) |
| MCU board assembly | `mcu/assembly/bom.csv`, `mcu/assembly/positions.csv` | **Economic PCBA, assembly side: Top.** 24 parts in 12 BOM rows, all on the front, J101 USB-C included |
| Front panel PCB | `main/usb-audio-max-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, **60.6 x 128.5 mm (12HP)**, no assembly; one routed NPTH slot 11.0 x 5.2 mm (USB-C). The printable panel is `../panels/front-cad/` |

### USB fabrication constraints (MCU board)

Do not substitute an arbitrary four-layer stack. The MCU native PCB now records the
JLC04161H-7628 stack (0.2104 mm outer prepreg, Er 4.4), copied from modules/usb-audio's MCU board,
whose USB geometry this board keeps: coupled USB section 0.30 mm width on F.Cu over the In1 GND plane,
0.40 mm single-ended fanouts; the D+/D- crossovers to the USB-C B row run on B.Cu over a stitched
In2 GND island: sampled every 0.05 mm along both edges and the centre line, 441 samples over the
island, 186 inside the crossover vias' own anti-pads (<= 0.6 mm from a via centre), 0 over a gap
(`research/fab-fix/usb-ref.json`); 3 GND stitching vias within 2.5 mm. Request **90 ohm differential / 45 ohm
single-ended** USB targets and fabricator confirmation. These are nominal analytic figures, not a
supplier measurement or a USB compliance test.

### PCM3168A (U3) PowerPAD land

Footprint `PCM3168A_HTQFP-64-1EP_10x10mm_P0.5mm_EP8x8mm_Mask7.4x7.4mm_ThermalVias` (fab review F3):
8 x 8 mm copper, solder mask opened to 7.4 x 7.4 mm over the 7.25 x 7.00 mm PowerPAD (TI SBAS452A
12.1.11; was 5 x 5 mm), 25 round 1.15 mm paste apertures between the 36 thermal holes (26.0 mm2 =
51 % of the PowerPAD, >= 0.09 mm from every hole's annulus), holes tied solid to the In1 GND plane
(TI SLMA002). Paste coverage is not a measured joint: ask for / do an X-ray or a sacrificial cross
check of the first boards if available, and watch U3 temperature at bring-up.
Checked in the exported Gerbers (`research/fab-fix/gerber-check.json`), not only the native board:
B_Mask one 7.4 x 7.4 mm flash at U3, B_Paste 25 x 1.15 mm round flashes, 36 x 0.2 mm PTH hits inside
the pad, no F_Mask opening over the pad (the holes are tented on the far side).

### Q1 (BCP56-16) collector copper

Fab review F2: `/V5_IN` pours on B (around the tab, 33.3 mm2 filled) and F (under J27 / Q1, 131.4 mm2
filled), solid connections, 10 x 0.6/0.3 vias beside (not in) the tab: 164.7 mm2 tab-connected copper
against the >= 100 mm2 the design asks for (Gerbers: pour regions on F_Cu and B_Cu, 10 x 0.3 mm holes
within 3.5 mm of the tab). Estimate, not a measurement: Nexperia rates the SOT-223 at 125 K/W with
1 cm2 collector copper on a single-sided board, so at the 0.70 W worst case (12.6 V, 195 mA) expect
a junction rise of roughly <= 90 K (Tj ~130 C at a 40 C case interior, Tj max 150 C); the 4-layer
board's In1 plane should lower that. Bench: measure the Q1 case temperature at 12.6 V and full +5VA
load; a sustained +5VA short is still not thermally protected (D11).

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J11-J16, J21-J28 | QingPu WQP-PJ301M-12 TS jack (IN 1-6, OUT 1-8) | Carrier F-side THT, panel-nut fixed; fit to the panel before soldering |
| J1 | 2x5 2.54 mm pin header | Eurorack power, carrier back |
| J6, J7 | 2x5 2.54 mm pin headers, unshrouded | CLK OUT (left edge) / CLK IN (right edge), carrier back, pin 1 at the top (square pad, silk triangle + "1" beside it). 10-way IDC ribbon between units, red wire on pin 1. Leave them off if the clock link is not used: the unit is then always the clock master |
| J2, J3 (carrier) + J102, J103 (MCU board) | 1x10 2.54 mm male strips | One strip per side joins the two boards; buy one pair, not two. Solder the MCU board on with the panel fitted so the USB-C lines up with its slot |
| J4 | 1x4 2.54 mm pin header (SWD) | Optional, carrier back; only for a WCH-LinkE |
| MS1, MS2 | M3 x 10 mm F-F hex standoffs + 4 x M3 screws | Mechanical, carrier top corners to panel holes H20/H21 (USB-C push support) |

The exporter excluded exactly these electrical refs: the 20 carrier THT refs as non-SMD
(`main/carrier/export-report.json`) and J102/J103 as "Excluded from BOM"
(`mcu/board/export-report.json`).

## Parts

### Carrier (strict-live audit, 2026-11-20 00:59 UTC, 5 boards)

`assembly.py audit --strict-live` on `main/carrier/`; raw report and snapshots in `research/clk/audit/`
(ignored). 41 codes: **25 Basic, 16 Extended**, every code Economic-eligible (`componentProductType` 0).
The audit exits 1 by design (no requirements file; per-part rating/role reviews are human gates, as on
every module). Free stock (`canPresaleNumber`) and minimum order read from the same answers: every code
has free stock above the 5-board need and a minimum order of 1 (no pre-order part).

Re-checked 2026-11-20 after the root `AGENTS.md` pre-order rule landed, carrier and `mcu/` BOMs, 5
boards + attrition (`research/preorder/check_preorder.py`, ignored): 54 rows, 0 failures; the tightest
are J101 TYPE-C-31-D-15 (414 free), PCM3168APAPR (1,483), CH32V307RCT6 (1,465) and OPA1679IDR (2,465).
The modules/multi-mix NE5532DR swap (its U8 OPA1678IDR dual) has no counterpart here: this board has
no OPA1678. U5 / U6 (+5VA single supply) need the rail-to-rail OPA1679; U7 / U8 (+/-12 V outputs)
could only go Basic as four NE5532DR duals in place of the two quads (no Basic quad audio op-amp at
JLCPCB), a re-place and re-route of the output stage for about $1.5 per board, and the OPA1679
Extended fee stays for U5 / U6. Not done; user decision.

- **New in S3 (clock link, the modules/multi-mix codes):** SN74LVC2G125DCTR C206035 (Extended, 2,040
  free), 74LVC1G97DW-7 C460532 (Extended, 4,090), BAT54S C47546 (Extended, 429,439), 4.7k C23162 (Basic);
  two more SN74LVC2G34 C14461 (now 3 per board) and 33R / 100R / 150R / 10k / 100k / 100n from rows
  that were already there. Three more Extended setup fees.
- **Extended semis / others (one setup fee each):** PCM3168APAPR C529289 (**1,483** free, the tightest),
  OPA1679IDR C2878631 (2,465), BCP56-16 C92221, TPS562208 C91301, REF5050AIDR C27804, SN74LVC2G34 C14461,
  24.576 MHz oscillator C5203547, MWSA0402S inductor C408337, GZ2012D121TF ferrite C5671, K2-1808SN
  switches C92589, and the three link parts above.
- **R/C that are not Basic (10 placements, user decision open):**
  - C211-C216 2.2n C0G 0603: **changed on 2026-11-20 from C33353 to YAGEO CC0603JRNPO9BN222 C107043**
    (Extended, 308,955 free, minimum order 1; same 2.2n / NP0 / 5 % / 50 V / 0603). C33353 listed 639 in
    stock but is pre-order only now (free stock -1705, minimum order 301). No Basic C0G at 2.2n in 0603.
  - R1/R2 33R 2512 1 W C53728 (Extended): the +5VA input drop resistors (power rating).
  - R3/R8 2.2R 1206 C144499 (Extended): the buck input filter resistor and the Q1 current-sense
    resistor.
- **Q2 C20526**: catalog MPN text `MMBT3904(RANGE:100-300)` vs native `MMBT3904` (same C-code, hFE
  bin qualifier).

### MCU board (strict-live audit, 2026-11-08 03:42 UTC, not repeated)

Unchanged board and BOM: CH32V307RCT6 C2988083 (1875 then), TYPE-C-31-D-15 C22464480 (**452** then),
USBLC6-2SC6 C7519, all Extended; **C101/C102 33p C0G 0402 C1562**: the exact lookup came back ambiguous
that day (as on modules/usb-audio); the fab review's lookup earlier on 2026-11-08 recorded it Basic,
Economic-eligible, 1,308,517 in stock. Re-check these before ordering.

Stock is a public web count at the recorded lookup time, not a reservation. The JLCPCB part and
placement preview (rotation/pin 1, especially the bottom-side SOIC/SOT parts, U3 and the new SC-70 /
SM8 link parts U11-U14) is a manual order gate.

## Source identity

Taken from the manifests; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `a4c3f10e0d828b154d7e1af648e37c5587153fea89cc2c3b8ea4b58bc9fcf128`.
- Carrier project `039ab4888ad0436b37edbd5b15cbc0795c00942068be1f9fa2e6b9ed8d0be175`.
- Carrier schematic `eb25e7086fa1fa6b5af7925d90c0835580514554afae7f6fb2b1bd977740e374`.
- MCU PCB `39ae92f71854281a70d053b2086155c5a0e12fdfd4d78d21b53fb239a9b95503`.
- MCU project `4ef0e47ef1a29ea21a5cf080105c3aeec870b59cbe2f3328fda52dfd571db9be`.
- MCU schematic `709e97d1852fd5b5e4364237aac0331792039be90fd46f37d0b2980506e2f365`.
- Panel PCB `5c33e370404c07d052f7380ab3d8292f085b861c2d16ad0aaa9ef711c7935688` (2026-11-23, 11.0 mm USB-C slot).
- Panel project `5a6fd1595e5d801277a5d1d3dc2d0cbda4f82c685530cccda285ff7337d3e8ba`.

## Reproduce

Refill and save both boards first (the exporter plots the saved fills). Then, from
`modules/usb-audio-max`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project-mcu.json --reports research/native-mcu

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-audio-max --schematic usb-audio-max.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/carrier
unzip -o jlcpcb/main/carrier/usb-audio-max-gerbers.zip -d jlcpcb/main/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board usb-audio-max-panel --pcb-only \
  --manifest jlcpcb/main/source-sha256.json --overwrite -o jlcpcb/main/panel
unzip -o jlcpcb/main/panel/usb-audio-max-panel-gerbers.zip -d jlcpcb/main/panel

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-audio-max-mcu --schematic usb-audio-max-mcu.kicad_sch --side top --require-part-numbers \
  --manifest jlcpcb/mcu/source-sha256.json --overwrite -o jlcpcb/mcu/board
unzip -o jlcpcb/mcu/board/usb-audio-max-mcu-gerbers.zip -d jlcpcb/mcu/board

cp jlcpcb/main/carrier/bom.csv jlcpcb/main/carrier/positions.csv jlcpcb/main/assembly/
cp jlcpcb/main/carrier/usb-audio-max-gerbers.zip jlcpcb/main/panel/usb-audio-max-panel-gerbers.zip jlcpcb/main/
cp jlcpcb/mcu/board/bom.csv jlcpcb/mcu/board/positions.csv jlcpcb/mcu/assembly/
cp jlcpcb/mcu/board/usb-audio-max-mcu-gerbers.zip jlcpcb/mcu/
```

Catalog audit, from the repository root:

```sh
python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/usb-audio-max/jlcpcb/main/carrier/bom.csv \
  --cpl modules/usb-audio-max/jlcpcb/main/carrier/positions.csv \
  --export-report modules/usb-audio-max/jlcpcb/main/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64
python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --bom modules/usb-audio-max/jlcpcb/mcu/board/bom.csv \
  --cpl modules/usb-audio-max/jlcpcb/mcu/board/positions.csv \
  --export-report modules/usb-audio-max/jlcpcb/mcu/board/export-report.json \
  --boards 5 --side top --strict-live --max-requests 64
```
