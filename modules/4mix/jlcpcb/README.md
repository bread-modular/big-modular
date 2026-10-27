# 4mix — manufacturing export (S2/R1)

Generated on 2026-10-23 from the S2 schematic and the R1 hand-routed 4-layer board (not yet
committed) with the shared `opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never
hand-edit these files: change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `4mix-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `4mix-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +12V, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic (root + channel sheet) inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `4mix-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 90.0 x 110.0 mm, 1 oz outer, HASL (or ENIG), stackup JLC04161H-7628 (the board's stackup). Via covering: **tented**, no via-in-pad fill / POFV (no vias in SMD pads). All 101 vias 0.3/0.6 mm. No copper or courtyard within 1 mm of the edge. No `JLCJLCJLCJLC` marker: choose the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 120 parts in 13 BOM rows, all on the back |
| Front panel PCB | `4mix-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 91.3 x 128.5 mm (18HP), no assembly |

### Hand-soldered / fitted after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J5, J101, J201, J301, J401 | QingPu WQP-PJ301M-12 TS jack (SEND A/B, RTN A/B, OUT, IN 1-4) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV3, RVn01-RVn03 (n = 1..4) | RV09 50k linear pot (RV1 MAIN, RV2/RV3 LVL A/B; per channel RVn01 VOL, RVn02 SEND A, RVn03 SEND B) | Front-side THT, no nut |
| J6, J7 | 2x3 2.54 mm pin header (EXP IN, EXP OUT) | Back side, optional: only for chaining another 4mix |
| J8 | 2x5 2.54 mm pin header | Eurorack power, back side, bottom right; pin 1 (-12 V) at the `-12V` silk |
| MS1, MS2 | 10 mm M3 F-F hex standoff + 4 x M3x6 screws | Mechanical (no reference, not in the BOM); hold the carrier bottom to the panel |

The exporter excluded exactly the 27 THT refs (12 jacks/headers + 15 pots) (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-23 04:17 UTC, 5 boards)

Every C-code resolves to its MPN and package and is Economy-eligible
(`research/export-1/audit.json`, ignored).

- **Resistors and capacitors: all JLCPCB Basic except R20/R30/R33** (1k 1 W 2512, C54315
  25121WF1001T4E, **Extended**, 70,361 in stock): the same output resistor and code as vca-mix
  (accepted there as D7) and imix. One Extended setup fee. A keyword search for a Basic 1k 2512
  returned nothing.
- **Basic semis/ICs:** TL072CDT C6961 (179,877, 45 needed for 5 boards), B5819W C8598 (606,684).
- **New to the audit vs earlier modules:** 1M C22935, 1k C21190, 100p C14858, 1u C15849, 10k
  C25804; all Basic, all in stock in the millions.

The audit exits non-zero, as for vca-mix and LOW: there is no
`docs/jlcpcb-audit-requirements.json`, so the per-part requirement/review rows stay `unknown`,
the 27 THT refs have no catalog code, and C54315 is flagged as an Extended R. That is expected,
not a catalog failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `0c39d0e53ebbac17159240afa74f3e02eeefd3353f3c384139fdbeadab5c03aa`.
- Carrier project `06544182379c79dfa9a97a8eef6b5a58cbf5472158bdd6383fe6116a1978f207`.
- Root schematic `3ef6c794494223b974a6acd6a51a0c7ee9c08ed0d6ab4f336335234c49a22bcf`.
- Channel sheet `d2d89da1e67ca651bdc126cc2d2cc6e64d24f71586fcb12e92e4394e1d8fa5a5`.
- Panel PCB `8b005d76c20b94c89dee478d71c40cc5ff47ec1c56ddce4888b5ea24d67d8262`.
- Panel project `41f15a7cc0ee32b5042e793ff1d63385da896688adfed7198523acf4ad81a1c1`.

## Reproduce

From `modules/4mix`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 4mix --schematic 4mix.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/4mix-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 4mix-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/4mix-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/4mix-gerbers.zip jlcpcb/panel/4mix-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change. The catalog audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/4mix-symbols.xml hardware/4mix.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/4mix/hardware --board 4mix.kicad_pcb --symbols-xml /tmp/4mix-symbols.xml \
  --cpl modules/4mix/jlcpcb/carrier/positions.csv \
  --export-report modules/4mix/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

Panel re-exported on 2026-10-27 for the rail-hole move: the left rail holes H1/H3 went 1HP (5.08 mm) right, X 7.5 to X 12.58, so both pairs (with X 83.7) sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- **Shared `check`** (before and after the export): ERC 0, DRC 0 violations / 0 unconnected /
  0 schematic parity, nothing excluded; ref/pin/net parity equal (MS1/MS2 reported as mechanical);
  manifest equal (6 sources, all exports byte-identical).
- **Zone fills current:** refilling a copy with the project rules gives identical In1 GND / In2
  +12V fill polygons.
- **Panel DRC:** 0 / 0.
- **Carrier drill file:** PTH 101 vias (0.3 mm) + 67 round pads (1.0 mm) + 57 slots (27 jack
  1.6 x 0.6, 30 pot lug 1.1 x 2.3) = every via and THT pad on the board. NPTH: 2 x 3.2 mm
  (standoffs MS1/MS2).
- **Panel drill file:** 30 NPTH holes: 9 jacks (6.2 mm), 15 pots (7.2 mm), 4 rail + 2 standoff
  holes (3.2 mm). No copper holes.
- **Gerber ZIP:** all four copper layers (F, In1 GND plane, In2 +12V plane, B), both masks,
  silkscreens and pastes, the edge, PTH/NPTH drills. F.Paste is empty (no front SMD parts).
  Per-layer renders inspected (`research/export-1/layers/`, ignored): both planes solid.
- **BOM/CPL:** 120 parts, 13 rows, every row with LCSC, MPN and manufacturer; every CPL row is
  `bottom`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly** on a 4-layer board, with the Extended 2512 part. Confirm the
   quote form offers it.
2. **Placement preview** in JLCPCB's bottom-side view: pin 1 of all 9 TL072s (SOIC-8), D1/D2
   (B5819W) cathode bands, every rotation.
3. **Live recheck before ordering:** stock, class, attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Mechanical/bench:** panel fit (jacks, pots, standoffs, big VOL knobs), standoff thread depth
   for M3x6, levels, send leakage/crosstalk.
