# HATS — manufacturing export (S2/R1)

Generated on 2026-10-24 from the S2 schematic and the R1 manual divide-and-conquer routed
board (4-layer, SW1/U7 DRC exclusions), using the shared `opt/kicad-tools/jlcpcb/export.py`
exporter, on user direction. Never hand-edit these files: change the sources, then re-export
with the commands below.

## Contents

| Path | Data |
|---|---|
| `hats-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `hats-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `hats-gerbers.zip` | 4 layers, FR4, 1.6 mm, 29.0 x 110.0 mm, JLC standard stack-up, 1 oz outer, HASL, tented vias (all 97 are 0.3/0.6 mm, none in SMD pads; no copper or courtyard within 1 mm of the edge except the RV1-RV4 courtyards, 0.77 mm, user-accepted). The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 88 parts in 31 BOM rows, all on the back |
| Front panel PCB | `hats-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J4 | QingPu WQP-PJ301M-12 TS jack (MIDI, NOISE IN, AUDIO, HAT CV) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1, RV3, RV4 | RV09 50k linear pot (NOISE TONE, CUTOFF, DECAY) | Front-side THT, no nut |
| RV2 | RV09 1M linear pot (BLUE TONE) | Front-side THT, no nut |
| D5, D6 | 3 mm red LED (ENV, REC) | Front-side THT; flat/cathode to the square pad |
| SW1 | 6 mm tactile button (REC) | Front-side THT, **inside the U7 vactrol outline** (the 4 excluded DRC items). Solder SW1 from the back **before** U7 |
| U7 | VTL5C-type vactrol (Bread Modular footprint) | Back-side THT over SW1's pins; trim SW1's leads flush first |
| J10 | 2x5 2.54 mm pin header | Eurorack power, back side, horizontal along the bottom edge; pin 1 (-12 V) at the `-12V` silk. **No key**: red stripe to `-12V` |
| J11, J12 | 1x2 2.54 mm pin header (`UPDI N` / `UPDI H` silk) | Optional, for programming the NOISE (U2) / HIHAT (U3) chip; pin 1 (square) UPDI, pin 2 GND |
| JP1 | 3-pad solder jumper (MIDI RX path) | Copper only, **shipped open**: bridge 1-2 (protected, needs inverted RX in firmware) or 2-3 (direct, stock firmware), never both |

The exporter excluded exactly these 15 THT refs plus JP1 (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-24 05:34 UTC, 5 boards)

Every C-code resolves to its MPN and package and is Economy-eligible
(`research/export/audit.json`, ignored).

- **Resistors and capacitors: all JLCPCB Basic** except the 2 x 1 kΩ 1206 0.5 W output
  resistors (ROHM ESR18EZPF1001 C2074262, Extended, the same part as ACID).
- **Basic semis/ICs:** B5819W C8598, 1N4148W C81598, MMBT3904 C20526, HT7533-1 C14289
  (141,810), TL072CDT C6961.
- **Extended (one setup fee each):** SS8050 C431710 (preferred, 1,335,938), SS8550 C364314
  (105,567), ESR18EZPF1001 C2074262 (101,016), MCP6002T-I/SN C7377 (preferred, 72,582),
  **ATTINY1616-MNR C507118 (4,626; 2 per board)**, **TS5A23157DGSR C11133 (422 in stock: the
  lowest; recheck before ordering)**.

The audit exits non-zero, as for low/acid: there is no `docs/jlcpcb-audit-requirements.json`,
so the per-part requirement/review rows stay `unknown`, and the 15 THT refs and JP1 have no
catalog code. That is expected, not a catalog failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `4350be78d73a19a3d2ff35469d955ce864dcb223bdb9defa4a900c0fe75c14a7`.
- Carrier project `4e1d1a704d1b48590add008ae991018219ee643c3899b32bc33a0f7c5b8d388f`.
- Carrier schematic `cff2c7c0873aca2d200dad3df90d79bd262b931c2868fae12406c3f66aef8f89`.
- Panel PCB `512bfb9e5e4ab3fd8de43ca5e85a7e84c34e6e8d7f1c4e7a34ca2bf51e5f9e36`.
- Panel project `1532ee8aea234b7885b42a7099ed9d474e1b50d3268b2cad903bf7292cccb1ea`.

## Reproduce

From `modules/hats`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board hats --schematic hats.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/hats-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board hats-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/hats-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/hats-gerbers.zip jlcpcb/panel/hats-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change. The catalog audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/hats-symbols.xml hardware/hats.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/hats/hardware --board hats.kicad_pcb --symbols-xml /tmp/hats-symbols.xml \
  --cpl modules/hats/jlcpcb/carrier/positions.csv \
  --export-report modules/hats/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export

- **Shared `check`:** ERC 0, 0 unconnected, schematic parity 0, manifest equal (5 sources, all
  exports byte-identical). DRC = the **4 `pth_inside_courtyard` items of SW1's pins inside U7's
  courtyard** (button inside the vactrol, user-approved 2026-10-24). They are native exclusions
  in `hats.kicad_pro` (`tools/sw1_exclusions.py`), so KiCad's own DRC reports 0; the shared gate
  still counts excluded items, so `order_ready` stays `false` (as low/acid).
- **Zones:** a refill of a copy changed no filled polygon, so the exported fills are current.
- **R1 routing:** 4 layers (F.Cu / In1 GND / In2 +3V3 / B.Cu), no tracks on In1/In2, In1 and
  In2 one piece each, no vias in SMD pads. Every SMD pad >= 2 mm from the pot/jack pads
  (closest R36 to RV4, 2.02 mm). Copper-to-edge rule 1.0 mm.
- **Panel DRC:** 0 / 0. Panel drill file: 13 NPTH holes (4 jacks, 4 pots, 2 LEDs, 1 button,
  2 rail holes).
- **BOM/CPL:** 88 parts, 31 rows, every row with LCSC, MPN and manufacturer; BOM and CPL
  reference sets equal; every CPL row is `bottom`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly** with the Extended parts above.
2. **Placement preview** in JLCPCB's bottom-side view: pin 1 of U2/U3 (QFN-20), the
   TS5A23157 (MSOP-10), the SOIC-8 op-amps; HT7533 tab; diode cathode bands; SOT-23
   orientation; every rotation.
3. **Live recheck before ordering:** stock (TS5A23157 and ATtiny1616 especially), class,
   attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Firmware:** the REC button/LED need new code on both chips (not written yet).
6. **Bench:** SW1/U7 fit, MIDI JP1 paths, NOISE IN normalling, output levels.
