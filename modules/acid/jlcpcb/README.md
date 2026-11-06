# ACID — manufacturing export (S3/R3, 10HP)

Carrier and panel re-generated on 2026-11-06 from the S3 schematic (LP / HP / BP gain jumpers,
`docs/research.md` 3.6), the P4/R3 10HP board (re-layout, hand re-routing and the via cleanup,
5.3) and the 10HP panel, with the shared `opt/kicad-tools/jlcpcb/export.py` exporter, on user
direction. It replaces the 8HP S3/R2 set. Re-exported the same day after U2 changed from
ATTINY1616-MNR C507118 (3 in stock) to **ATTINY1616-MF C5227638** (fields only). Never hand-edit these files:
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
| Carrier PCB | `acid-gerbers.zip` | 4 layers, FR4, 1.6 mm, 49.5 x 110.0 mm, JLC standard stack-up, 1 oz outer, HASL, tented vias (all 140 are 0.3/0.6 mm, none in SMD pads; no copper or courtyard within 1 mm of the edge). The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 98 parts in 27 BOM rows, all on the back |
| Front panel PCB | `acid-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 50.5 x 128.5 mm (10HP), no assembly |

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
| JP2 / JP3 / JP4 | 3-pad solder jumpers `LP` / `HP` / `BP` (legend `GAIN: OPEN=x3` / `M=x3.9 H=x11` under the HP / LP jumpers) | Copper only, **shipped open = x3.0** at the jack. Bridge `M` (2-3) for x3.9 or `H` (1-2) for x11.1 (the S2 gain, ~10 Vpp ceiling) |

The exporter excluded exactly these 24 THT refs plus JP1-JP4 (`carrier/export-report.json`).

## Parts (live catalog, 2026-11-06 06:35 UTC, 5 boards)

The BOM matches the S3/R2 one (same 27 rows) except the U2 row. Live audit
`research/export-r3-mf/audit.json` (ignored): every C-code resolves to its MPN, no part is
short of stock; stock figures below are from that run.

- **U2 = ATTINY1616-MF C5227638** (240 in stock, $2.58 @1), replacing ATTINY1616-MNR C507118
  (3 in stock < 5 boards). Same die, pinout and VQFN-20 3x3 package, so footprint, copper and
  firmware are unchanged; only the temperature grade (-40..125 C) and the tray packing differ.
  JLCPCB lists no attributes for this code (`missing:attributes` in the audit).
  **Clock caveat:** the firmware runs 20 MHz at 3.3 V. The datasheet guarantees 10 MHz at that
  voltage for the -MNR grade and less for the 125 C grade (16 MHz max, 8 MHz at 2.7 V), so both
  parts run above spec; Bread Modular builds prove the -MNR, the -MF is not bench-tested.

- **Resistors and capacitors: all JLCPCB Basic**, except the 1206 1k 0.5 W output/CV-out
  resistors (R43, R44, R48, R49, R53, R54, R57): ROHM ESR18EZPF1001 C2074262, Extended
  (no Basic 0.5 W 1206 1k exists).
- **Basic semis/ICs:** B5819W C8598, 1N4148W C81598, MMBT3904 C20526, HT7533-1 C14289,
  TL072CDT C6961.
- **Extended (one setup fee each):** ESR18EZPF1001 C2074262 (99,734), ATTINY1616-MF C5227638
  (240), MCP6002T-I/SN C7377 (84,328), BAT54SWT1G C78260 (45,452), TS5A23157DGSR C11133 (5,138).

The audit exits non-zero, as for LOW, vca-mix and 16bit: there is no
`docs/jlcpcb-audit-requirements.json`, so the per-part requirement/review rows stay
`unknown`, and the 24 THT refs and JP1 have no catalog code. That is expected, not a catalog
failure.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `67dc3b9e431e342d7606577cbe240791d18c921abe8c2b75e0ee730a2472d778`.
- Carrier project `9b192541b9b93e5a057acfd05218fb45a785de7ef7759c42e34f688fbd82771f`.
- Carrier schematic `2a28354bcbe9840404276d1c4fa10f17276c2d8c7a25e826a0f9dcb65753e0a3`.
- Panel PCB `4758b32d24a5a035ce823f28e206793feba212951e1f0daea6fec98fa95b7217`.
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

S3/R3 export, 2026-11-06 (carrier and panel):

- **Shared `check`** (after export): ERC 0, 0 unconnected, schematic parity 0, ref/pin/net
  parity equal, manifest equal (5 sources, all exports byte-identical). DRC = the **22
  vactrol-under-pot items** (U7/U8 under RV3/RV4, user-approved). They are native exclusions in
  `acid.kicad_pro` (`tools/vactrol_exclusions.py`), so KiCad's own DRC (all severities, silk
  included) reports 0 active; the shared gate still counts excluded items, so `order_ready`
  stays `false` (as LOW, vca-mix D14).
- **Zones:** a refill on a scratch copy gives identical filled polygons on all 4 zones, so the
  exported pours are current.
- **Board rules** (`research/r3/checks.py`): no via in or touching an SMD pad, no tracks on
  In1 / In2, In1 and In2 one piece each, courtyards >= 1.0 mm from the edge, closest SMD pad to a
  pot / jack pad 2.07 mm (C15-RV5).
- **Carrier drill file:** 197 round PTH hits (140 vias + 57 round pads) plus 35 slots, matching
  140 vias + 92 THT pads. No NPTH holes.
- **Panel:** DRC 0 / 0. 24 NPTH holes: 7 jacks (6.2 mm), 7 pots (7.2 mm), 2 buttons (4.2 mm),
  4 LEDs + 4 rail holes (3.2 mm).
- **BOM/CPL:** 98 parts, 27 rows, every row with LCSC, MPN and manufacturer; every CPL row is
  `bottom`; the 24 THT refs and JP1-JP4 excluded.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly** with the Extended parts above.
2. **Placement preview** in JLCPCB's bottom-side view: pin 1 of U2 (QFN-20), U4 (MSOP-10),
   U3/U5/U6/U9/U10/U11 (SOIC-8); U1 tab; D1-D3 cathode bands; D8/Q1 orientation; every rotation.
3. **Live recheck before ordering:** ATtiny1616 stock (3 on 2026-11-06, 5 needed), the other
   Extended parts, class, attrition.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench:** vactrol fit under ATTACK/RELEASE, DAC/envelope range, vactrol range, output
   level, MIDI JP1 paths. Firmware (MCO + ENV merge, REC) is compiled, not bench-tested.
