# LOW — manufacturing export (S3/R3)

Generated on 2026-10-21 from the S3 schematic (S2 + LCSC/MPN/Manufacturer fields, R17/R18
47k/100k) and the R2 hand-routed board with the user's C9/U6 moves; the carrier was re-exported
on 2026-10-22 from R3 (1 mm board-edge keep-out, U5/RV3 DRC exclusions, `docs/research.md` 5.3;
panel unchanged), using the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit these files:
change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `low-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `low-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `low-gerbers.zip` | 2 layers, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz, HASL, tented vias (all 0.3/0.6 mm, none in SMD pads; no copper or courtyard within 1 mm of the edge except the RV1/RV2 courtyards, 0.82 mm). The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 58 parts in 26 BOM rows, all on the back |
| Front panel PCB | `low-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J4 | QingPu WQP-PJ301M-12 TS jack (MIDI, AUDIO, CV, OUT) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV3 | RV09 50k linear pot (DETUNE, MIX, CUTOFF) | Front-side THT, no nut |
| U5, U7 | VTL5C-type vactrol (Bread Modular footprint) | Back-side THT. **Fit U5 before CUTOFF (RV3)**: its leads sit under the pot body (the 3 excluded DRC items) |
| J10 | 2x5 2.54 mm pin header | Eurorack power, back side, vertical at the bottom; pin 1 (-12 V) at the `-12V` silk. **No key**: red stripe to `-12V` |
| J11 | 1x2 2.54 mm pin header (`UPDI` silk) | Optional, for programming; pin 1 (square) UPDI, pin 2 GND |
| JP1 | 3-pad solder jumper (`PROT RX DIR` silk) | Copper only, **shipped open**: bridge 1-2 (protected) or 2-3 (direct), never both |

The exporter excluded exactly the 11 THT refs plus JP1 (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-21 12:52 UTC, 5 boards)

Every C-code resolves to its MPN and package and is Economy-eligible
(`research/export-1/audit.json`, ignored).

- **Resistors and capacitors: all JLCPCB Basic.** 1M C22935, 200k C25811, 33k C4216 and
  47k C25819 are new to the repo; the rest are the codes used by vca-mix/16bit.
- **R17/R18 changed from 51k/110k to 47k/100k**: 110k 0603 has no Basic part (only Preferred
  Extended C25805). 100k || R24 1M = 90.9k, so 5.0 V in still gives 3.30 V at the LPG; input
  impedance 147k, clamp current 0.26 mA at -12 V, jack-detect unplugged level 0.42 V.
- **Basic semis/ICs:** B5819W C8598, 1N4148W C81598, MMBT3904 C20526, HT7533-1 C14289
  (115,680), TL072CDT C6961.
- **Extended (one setup fee each):** ATTINY1616-MNR C507118 (5,159), MCP6002T-I/SN C7377
  (preferred, 49,366), BAT54SWT1G C78260 (32,838), **TS5A23157DGSR C11133 (518 in stock: the
  lowest; recheck before ordering)**.

The audit exits non-zero, as for vca-mix and 16bit: there is no
`docs/jlcpcb-audit-requirements.json`, so the per-part requirement/review rows stay
`unknown`, and the 11 THT refs and JP1 have no catalog code. That is expected, not a catalog
failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `4c6164de3fe4a4a08f2969cd181c59d5a96184f4cd8f0494a068ff628d86668d`.
- Carrier project `dc765a35f7ed9e3740062da90224665f8036652e058907e47d776e9bd0a8a827`.
- Carrier schematic `4cc827516e4b8de62f52750d17837487db5f271716ce57c83b59ca6876ea040d`.
- Panel PCB `c7cd173b359867675152d2ba582aab87a6b30e521c5736066f567c488679b29b`.
- Panel project `a84349687ec42c51876c9bda27a01b3788d09101e8d0697de8d2435ce09328ba`.

## Reproduce

From `modules/low`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board low --schematic low.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/low-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board low-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/low-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/low-gerbers.zip jlcpcb/panel/low-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change. The catalog audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/low-symbols.xml hardware/low.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/low/hardware --board low.kicad_pcb --symbols-xml /tmp/low-symbols.xml \
  --cpl modules/low/jlcpcb/carrier/positions.csv \
  --export-report modules/low/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- **Shared `check`** (after the 2026-10-22 export): ERC 0, 0 unconnected, schematic parity 0,
  ref/pin/net parity equal, manifest equal (5 sources, all exports byte-identical). DRC = the
  **3 `pth_inside_courtyard` items of U5 under RV3** (vactrol/pot stacking, user-approved). They
  are native exclusions in `low.kicad_pro` (`tools/u5_exclusions.py`), so KiCad's own DRC reports
  0; the shared gate still counts excluded items, so `order_ready` stays `false` (as vca-mix D14).
- **R3 edge keep-out:** copper-to-edge rule 1.0 mm (pours refilled), every track/via/pad >= 1.0 mm
  from the edge, every courtyard >= 1.0 mm except RV1/RV2 (0.82 mm, panel-fixed, user-accepted). CPL changes vs
  2026-10-21: C5, C12, C16, D4, U9 positions; BOM unchanged. Every SMD pad >= 2 mm from the pot/jack pads (closest U6 2.20 mm).
- **2 mm re-export (2026-10-22):** D4 0.125 mm in (X127.25, in line with R11/R17; courtyard 1.0 -> 1.125 mm
  from the edge, pad 2.83 mm from J3) and the user's hand-rerouted DETUNE F.Cu run, pours refilled. CPL: D4 only;
  BOM unchanged. KiCad DRC 0 (3 excluded) / 0 unconnected / parity 0; no vias in SMD pads.
- **Before export:** the user's U6 move had left U6 pin 7 (LPG_AMP) unconnected; a 0.25 mm
  B.Cu link from pin 7 to the pin 6 track fixed it. The LCSC/MPN/Manufacturer fields, R17/R18
  values and their Notes were written to the PCB footprints; placement and copper are
  otherwise unchanged. No vias in SMD pads.
- **Panel DRC:** 0 / 0.
- **Carrier drill file:** 80 round PTH hits (51 vias + 29 round pads) plus 18 slots = 98,
  matching 51 vias + 47 THT pads. No NPTH holes.
- **Panel drill file:** 9 NPTH holes: 4 jacks (6.2 mm), 3 pots (7.2 mm), 2 rail holes (3.2 mm).
- **BOM/CPL:** 58 parts, 26 rows, every row with LCSC, MPN and manufacturer; every CPL row is
  `bottom`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly** with the Extended parts above.
2. **Placement preview** in JLCPCB's bottom-side view: pin 1 of U2 (QFN-20), U4 (MSOP-10),
   U3/U6/U8/U9 (SOIC-8); U1 tab; D1-D3 cathode bands; D4/Q1 orientation; every rotation.
3. **Live recheck before ordering:** stock (TS5A23157 especially), class, attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench:** vactrol fit under CUTOFF, jack-detect threshold (1M pull-ups, research.md),
   MIDI JP1 paths, output level.
