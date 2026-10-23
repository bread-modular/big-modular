# ACID — manufacturing export (S2/R1)

Generated on 2026-10-23 from the S2 schematic and the R1 hand-routed 4-layer board (plus the
B silk UPDI / MIDI JP1 labels, `docs/research.md` 5.1) with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit these files:
change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `acid-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `acid-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers incl. In1 GND / In2 +3V3, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `acid-gerbers.zip` | 4 layers, FR4, 1.6 mm, 39.35 x 110.05 mm, JLC standard stack-up, 1 oz outer, HASL, tented vias (all 168 are 0.3/0.6 mm, none in SMD pads; no copper or courtyard within 1 mm of the edge). The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 92 parts in 27 BOM rows, all on the back |
| Front panel PCB | `acid-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 40.3 x 128.5 mm (8HP), no assembly |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J7 | QingPu WQP-PJ301M-12 TS jack (J1 MIDI, J2 AUDIO, J3 CV, J5 ENV OUT, J4 LP, J6 HP, J7 BP) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV7 | RV09 linear pot: RV1 DETUNE, RV2 MIX, RV3 ATTACK, RV4 RELEASE, RV7 CURVE 50k; RV5 RES 500k; RV6 FREQ 1M | Front-side THT, no nut |
| SW1, SW2 | 6 x 6 mm THT tact switch (MODE, REC) | Front-side THT |
| D4-D7 | 3 mm red LED (HR / AR / ASR, REC) | Front-side THT; set the height to the panel holes |
| U7, U8 | VTL5C-type vactrol (Bread Modular footprint) | Back-side THT. **Fit both before ATTACK/RELEASE (RV3/RV4)**: their leads sit under the pot bodies (the 22 excluded DRC items) |
| J10 | 2x5 2.54 mm pin header | Eurorack power, back side; pin 1 (-12 V) at the `-12V` silk. **No key**: red stripe to `-12V` |
| J11 | 1x2 2.54 mm pin header (`GND UPDI` silk) | Optional, for programming; pin 1 (square) UPDI, pin 2 GND |
| JP1 | 3-pad solder jumper (`JP1 D=DIRECT P=PROT` silk, `D` / `P` at the pads) | Copper only, **shipped open**: bridge P (1-2, protected, PORT_INVEN on) or D (2-3, direct, 3.3 V senders only), never both |

The exporter excluded exactly these 24 THT refs plus JP1 (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-23 04:21 UTC, 5 boards)

Every C-code resolves to its MPN and package and is Economy-eligible
(`research/export-1/audit.json`, ignored).

- **Resistors and capacitors: all JLCPCB Basic**, except the 1206 1k 0.5 W output/CV-out
  resistors (R43, R44, R48, R49, R53, R54, R57): ROHM ESR18EZPF1001 C2074262, Extended
  (no Basic 0.5 W 1206 1k exists).
- **Basic semis/ICs:** B5819W C8598, 1N4148W C81598, MMBT3904 C20526, HT7533-1 C14289,
  TL072CDT C6961.
- **Extended (one setup fee each):** ESR18EZPF1001 C2074262 (101,055), ATTINY1616-MNR C507118
  (5,053), MCP6002T-I/SN C7377 (preferred, 73,388), BAT54SWT1G C78260 (32,344),
  **TS5A23157DGSR C11133 (462 in stock: the lowest; recheck before ordering)**.

The audit exits non-zero, as for LOW, vca-mix and 16bit: there is no
`docs/jlcpcb-audit-requirements.json`, so the per-part requirement/review rows stay
`unknown`, and the 24 THT refs and JP1 have no catalog code. That is expected, not a catalog
failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `5e4936209eaec51eb97aabb4da7d49c098d39b8d879c9cc364e165cc39e96f6e`.
- Carrier project `2b16ebe4e117a70e29f7aaa705259fc66d700a8de8574ae69aab4d548a704068`.
- Carrier schematic `776bf1537405e5ed5ab01e169faae8ede8ccfaa5d55dad4685bed0bae50bccd7`.
- Panel PCB `29b85ef02ae41eb63d50d176fa6d51ae0097b8baabda3c3c1f2084a29ba8f70d`.
- Panel project `f305bcc9525db9aaaf0c2e09ff9b4a45e533191f56bed62385825f31da0950cd`.

## Reproduce

From `modules/acid`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board acid --schematic acid.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/acid-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board acid-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/acid-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/acid-gerbers.zip jlcpcb/panel/acid-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change. The catalog audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/acid-symbols.xml hardware/acid.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/acid/hardware --board acid.kicad_pcb --symbols-xml /tmp/acid-symbols.xml \
  --cpl modules/acid/jlcpcb/carrier/positions.csv \
  --export-report modules/acid/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export

- **Shared `check`** (after export): ERC 0, 0 unconnected, schematic parity 0, manifest equal
  (5 sources, all exports byte-identical). DRC = the **22 vactrol-under-pot items** (U7/U8 under
  RV3/RV4, user-approved). They are native exclusions in `acid.kicad_pro`
  (`tools/vactrol_exclusions.py`), so KiCad's own DRC reports 0 active; the shared gate still
  counts excluded items, so `order_ready` stays `false` (as LOW, vca-mix D14).
- **Zones:** a refill on a scratch copy gives byte-identical filled polygons (44), so the
  exported pours are current.
- **Silk:** DRC silk checks (silk over copper/mask, overlap, edge, text height) at warning
  severity: 0 findings with the new labels.
- **Carrier drill file:** 225 round PTH hits (168 vias + 57 round pads) plus 35 slots = 260,
  matching 168 vias + 92 THT pads. No NPTH holes.
- **Panel:** DRC 0 / 0. 24 NPTH holes: 7 jacks (6.2 mm), 7 pots (7.2 mm), 2 buttons (4.2 mm), 4 LEDs + 4 rail holes (3.2 mm).
- **BOM/CPL:** 92 parts, 27 rows, every row with LCSC, MPN and manufacturer; every CPL row is
  `bottom`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly** with the Extended parts above.
2. **Placement preview** in JLCPCB's bottom-side view: pin 1 of U2 (QFN-20), U4 (MSOP-10),
   U3/U5/U6/U9/U10/U11 (SOIC-8); U1 tab; D1-D3 cathode bands; D8/Q1 orientation; every rotation.
3. **Live recheck before ordering:** stock (TS5A23157 and ATtiny1616 especially), class,
   attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench:** vactrol fit under ATTACK/RELEASE, DAC/envelope range, vactrol range, output
   level, MIDI JP1 paths. Firmware (MCO + ENV merge, REC) is not written.
