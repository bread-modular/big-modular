# usb-audio — manufacturing export (carrier S3/R3, MCU board S1/R2)

Updated on 2026-10-24 for the authorized USB / R36-R37 repair: carrier S3/R3 and MCU
S1/R2, retaining the unchanged 6HP panel export, with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit these files:
change the sources, then re-export with the commands below.

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
| Carrier PCB | `main/usb-audio-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz outer, HASL, stackup JLC04161H-7628. Tented vias, no via-in-pad / POFV (no vias in SMD pads). Min hole 0.3 mm (87 routed vias 0.3/0.6 mm). No `JLCJLCJLCJLC` marker: pick the order-number option deliberately |
| Carrier assembly | `main/assembly/bom.csv`, `main/assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 74 parts in 29 BOM rows, all on the back |
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

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J2-J5 | QingPu WQP-PJ301M-12 TS jack (IN 1, IN 2, OUT 1, OUT 2) | Carrier F-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV4 | RV09 50k linear pot | Carrier F-side THT, no nut |
| J1 | 2x5 2.54 mm pin header | Eurorack power, carrier back |
| J6, J7 (carrier) + J102, J103 (MCU board) | 1x10 2.54 mm male strips, 2.5 mm plastic | One strip per side joins the two boards (pin 10 GND). Solder the MCU board on with the panel fitted so the USB-C lines up with its slot |
| J8 | 1x4 2.54 mm pin header (SWD) | Optional, carrier back; only for a WCH-LinkE |

The exporter excluded exactly these refs: the 12 carrier THT refs as non-SMD
(`main/carrier/export-report.json`) and J102/J103 as "Excluded from BOM"
(`mcu/board/export-report.json`).

## Parts (historical full catalog audit, 2026-10-24 15:44 UTC, 5 boards each)

The original full-set evidence below is retained, not represented as a new full audit.
Read from `assembly.py audit --strict-live`; raw reports in `research/export-r2/` (ignored). Every
C-code resolved to its MPN and package and is Economic-eligible (`componentProductType` 0).

- **Basic:** every other R/C, AMS1117-5.0 C6187, AMS1117-3.3 C6186, B5819W C8598, 8 MHz crystal
  C115962.
- **Extended semis (one setup fee each):** CS4270-CZZR C1323229 (1,389, Cirrus: discontinued),
  OPA1678IDR C192421 (10,534), OPA1679IDR C2878631 (1,019), 24.576 MHz oscillator C5203547
  (4,030), K2-1808SN-A4SW-01 C92589 (10,347), GZ2012D121TF ferrite C5671 (41,416),
  CH32V307RCT6 C2988083 (576), TYPE-C-31-D-15 C22464480 (471), USBLC6-2SC6 C7519 (42,358).
- **R/C that are not Basic (unchanged; user deferred these findings for now):**
  - C20/C21 2.2n C0G 0603 C33353 (Extended, 5,791) and C22/C23 1n C0G 0603 C163508 (Extended,
    445,056): the ADC/DAC filter caps. JLCPCB has no Basic C0G at 2.2n or 1n in 0603; the Basic
    0603 parts are X7R, which is not used in an audio filter path.
  - R1 33R 2512 1 W C53728 (Extended, 69,271): the +3V3 regulator drop resistor. No Basic 33R
    above 0805 (125 mW).
- C101/C102 33p C0G 0402 C1562: the exact lookup came back ambiguous; the catalog search lists it
  as Basic, Economic-eligible, 1,586,765 in stock.

**Scoped new-part lookup:** R36/R37 changed from 1k to 2k; new R38/R39 are also 2k,
all C17944 / 1206W4F2001T5E / 1206 / 0.25 W / 1%. The shared exact-code live lookup
confirmed **Basic + Economic eligible**. The pairs preserve 1k effective resistance
and provide 0.5 W nominal total rating per output. Schematic, PCB and regenerated
BOM/CPL agree; no CSV-only substitution. Raw evidence: `research/usb-fix/C17944-live.json`.

Stock is a public web count at the recorded lookup time, not a reservation. The
unchanged full-BOM review/assembly acceptance gates have not been cleared here.

## Source identity

Taken from the manifests; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `cb6e5914ed0b7469306e509f67f0f5c22af2417153b82ad040021bcda9f6e2ed`.
- Carrier project `095104386085c81b91d7e1a976b0d5593ef90aa2836cffa86d18e02661adace0`.
- Carrier schematic `4efe0e5ba31a7bf9f9bd1b43320f10fb4bb580f385f3b7988ac21d7caaeaf712`.
- MCU PCB `57fb7b79e46997ecd9e7e4dcdf776cd3aed611b3a8c92895fcc015990066581b`.
- MCU project `f44b54905d91b705c30585a41b4d6e7ee1d2b8077a96b3c0d53c274076169620`.
- MCU schematic `43e70f7855c31936ca631a70b1bd3d0c74125455bdd0d3efadcd9271dfb442f2`.
- Panel PCB `8f438113d7c205553e69991f26a00d4808e77872ad9b9a4215ff3aebd4fb874e`.
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

## Checks done for this export

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `main/panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- `tools/check_usb.py`: both orientations pass (0.41421 / 0.22464 mm mismatch), two
  signal vias per polarity, ground-reference coverage and explicit geometry/stackup checked.
- No existing footprints moved; no vias in SMD pads; courtyards >=1 mm;
  SMD-to-hand-solder pad minimum remains 2.03 mm. In1 and every In2 zone remain one piece.

- **Shared `check`, both boards, after the export:** ERC 0, DRC 0 (all severities), 0
  unconnected, parity 0, 0 exclusions; manifests equal (carrier + panel 5 sources, MCU 3
  sources), exports byte-identical. `order_ready: false`, as always for this tool.
- **Carrier drill file:** 87 vias (0.3 mm) and 46 round THT holes (1.0 mm), plus 20 routed slots
  (0.6 / 1.1 mm); no NPTH holes.
- **MCU drill file:** 49 vias (0.3 mm), 20 header holes (1.0 mm), 4 USB-C shell slots; no NPTH.
- **Panel drill file:** NPTH only: 2 x 3.2 mm mounting holes, 4 x 6.2 mm jacks, 4 x 7.2 mm pots and
  the 9.5 x 3.7 mm USB-C slot; no copper holes.
- **Gerber ZIPs:** 4 copper layers with their pours on both boards, both masks, silks, pastes,
  edge, PTH/NPTH drills. Carrier F.Paste and MCU B.Paste are empty (single-sided assembly).
- **BOM/CPL:** carrier 74 parts / 29 rows, all `bottom`; MCU 23 parts / 12 rows, all `top`;
  every row has LCSC, MPN and manufacturer.
- **Catalog audit:** fails on the 5 non-Basic R/C above and on the per-part requirement/review
  rows that stay `unknown` without `docs/jlcpcb-audit-requirements.json`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

- The 5 Extended R/C (C20-C23, R1) and other prior review findings remain as-is per
  the user for now; this deferral is not a passing supplier/thermal/firmware gate.
- Recheck current stock, classification and
  Economic eligibility live; check attrition and minimums. Buy CS4270 spares (discontinued).
- In JLCPCB's preview, check every part match, centroid, rotation, pin 1 and polarity (U101
  LQFP pin 1, U3 TSSOP, U4-U7, U102, Y1, D1/D2, J101 shell legs in their slots).
- Check the self-drawn J101 footprint against the HRO drawing (merged peg/leg slots).
- Bench: 192 kHz I2S slave timing, codec levels, output power-up transient, firmware (none yet).
