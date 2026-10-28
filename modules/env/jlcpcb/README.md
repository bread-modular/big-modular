# ENV — manufacturing export (S3/R1)

Generated on 2026-10-28 from the S3 schematic and the R1 hand-routed 2-layer board (plus the
B silk UPDI / JP1 labels, `docs/research.md` 5) with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit these files:
change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `env-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `env-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (F/B copper, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `env-gerbers.zip` | 2 layers, FR4, 1.6 mm, 29.05 x 110.05 mm, 1 oz, HASL, tented vias (all 26 are 0.3/0.6 mm, none in SMD pads; no copper or courtyard within 1 mm of the edge). The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 36 parts in 19 BOM rows, all on the back |
| Front panel PCB | `env-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1, J2, J5, J6 | QingPu WQP-PJ301M-12 TS jack (J6 GATE IN, J1 MIDI IN, J2 ENV OUT, J5 MIDI OUT) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1, RV2 | RV09 50k linear pot (ATTACK, RELEASE) | Front-side THT, no nut |
| SW1, SW2 | 6 x 6 mm THT tact switch (MODE, REC) | Front-side THT |
| D4-D8 | 3 mm red LED (HR / AR / ASR, REC, ENV) | Front-side THT; set the height to the panel holes |
| J3 | 2x5 2.54 mm pin header | Eurorack power, back side, vertical on the right edge; pin 1 (-12 V) at the bottom, at the `-12V` silk. **No key**: red stripe to `-12V`. 10- or 16-pin cable |
| J4 | 1x2 2.54 mm pin header (`UPDI` / `GND` silk) | Optional, for programming; pin 1 (square, top) UPDI, pin 2 GND |
| JP1 | 3-pad solder jumper (`JP1 D=DIRECT P=PROT` silk, `D` / `P` under the pads) | Copper only, **shipped open**: bridge P (1-2, protected, PORT_INVEN on) or D (2-3, direct, 3.3 V senders only), never both |

The exporter excluded exactly these 15 THT refs plus JP1 (`carrier/export-report.json`).

## Parts (live catalog, 2026-10-28 17:12 UTC, 5 boards)

Every C-code resolves to its MPN and package and is Economy-eligible
(`research/export-1/audit.json`, ignored).

- **Resistors and capacitors: all JLCPCB Basic**, except R12, the 1206 1k 0.5 W ENV OUT
  resistor: ROHM ESR18EZPF1001 C2074262, Extended (no Basic 0.5 W 1206 1k exists; as ACID).
- **Basic semis/ICs:** B5819W C8598, 1N4148W C81598, MMBT3904 C20526, HT7533-1 C14289,
  TL072CDT C6961.
- **Extended (one setup fee each):** ESR18EZPF1001 C2074262 (100,736),
  **ATTINY1616-MNR C507118 (1,902 in stock: the lowest; recheck before ordering)**.

The audit exits non-zero, as for ACID, LOW and vca-mix: there is no
`docs/jlcpcb-audit-requirements.json`, so the per-part requirement/review rows stay
`unknown`, and the 15 THT refs and JP1 have no catalog code. That is expected, not a catalog
failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `dc25c581983aa1c500294b832293f20d7598f5fa37186c8093d22287dac25a51`.
- Carrier project `e94c57bf60d418eeb3101fdff8468f466f9fcdbff976f230a3a9376088a0a18c`.
- Carrier schematic `03183a9730254a8e0042f91cf188b8e37167c15642c115252709ee6f5104bee5`.
- Panel PCB `b4fe51e87cda4470639b13283c55074fc8afb5f667741ba2e21b7f9c18e0ad52`.
- Panel project `6d22f07fec3e78d77b7bd951908fa575494a745a4fc166cf66ae9bb95dc45946`.

## Reproduce

From `modules/env`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board env --schematic env.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/env-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board env-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/env-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/env-gerbers.zip jlcpcb/panel/env-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change. The catalog audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/env-symbols.xml hardware/env.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/env/hardware --board env.kicad_pcb --symbols-xml /tmp/env-symbols.xml \
  --cpl modules/env/jlcpcb/carrier/positions.csv \
  --export-report modules/env/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export

- **Shared `check`** (after export): ERC 0, DRC 0, 0 unconnected, schematic parity 0, no
  exclusions, manifest equal (5 sources, all exports byte-identical). `order_ready` stays
  `false`: the supplier gates below are manual.
- **Zones:** a refill on a scratch copy gives byte-identical filled polygons (13), so the
  exported pours are current.
- **Silk:** native DRC with all severities (silk over copper, overlap, edge at warning): 0
  findings with the new labels.
- **Carrier drill file:** 62 round PTH hits (26 vias + 36 round pads) plus 16 slots = 78,
  matching 26 vias + 52 THT pads. No NPTH holes.
- **Panel:** DRC 0 / 0. 15 NPTH holes: 4 jacks (6.2 mm), 2 pots (7.2 mm), 2 buttons (4.2 mm),
  5 LEDs + 2 rail holes (3.2 mm).
- **BOM/CPL:** 36 parts, 19 rows, every row with LCSC, MPN and manufacturer; every CPL row is
  `bottom`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly** with the two Extended parts above.
2. **Placement preview** in JLCPCB's bottom-side view: pin 1 of U2 (QFN-20) and U3 (SOIC-8);
   U1 tab; D1-D3, D9 cathode bands; Q1/Q2 orientation; every rotation.
3. **Live recheck before ordering:** stock (ATtiny1616 especially), class, attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench:** GATE IN threshold and jack detect, MIDI JP1 paths, MIDI OUT thru, DAC / ENV OUT
   range, ENV LED. Firmware (MIDI / GATE IN gate with the PB1 bypass, three envelope models,
   REC) is not written.
