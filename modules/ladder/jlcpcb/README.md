# LADDER manufacturing export — S3 / R2 / 10HP panel

Exported 2026-11-10 from the S3 schematic, the R2 carrier and the 10HP panel, using the unchanged
shared `opt/kicad-tools/jlcpcb/export.py` (commands at the end). **Complete matched export, not
supplier-accepted, not built; no firmware yet.**

**R2 = fab-review fixes on the R1 routing (2026-11-10, local re-routes, no THT part moved):**

- R32 (10k, DIF_N / LAD_AF) moved 3.6 mm east along its row: its pads were 0.68 mm / 1.01 mm from
  the hand-soldered SW1 GND pad; closest SMD pad to SW1 is now R33 at 2.28 mm.
- C35 (U9 -12V_F 100n) moved from the D2 corner to U9 pin 4 with its own GND via: routed
  pin-to-cap length 10.2 mm (to C2) -> 2.5 mm. The -12V_F bus runs straight down from D2.
- GND vias at U11.3 and D3.2 pulled back from their own pads (0.05 mm / 0.09 mm -> 0.35 mm /
  0.30 mm), so no via sits in a mask opening.
- B silk: `P` / `D` at JP1 (pad 1 = protected RX, pad 3 = direct MIDI), board text `LADDER R2`.
- JLC04161H-7628 stackup recorded in the board; In1 / In2 zone fills saved (R1 was saved unfilled).

| Order | Files | Configuration |
|---|---|---|
| Carrier PCB | `ladder-gerbers.zip` | 4 layers, FR4, 1.6 mm, 49.5 x 110 mm; F / In1 GND / In2 +12V_F / B; ordinary tented vias, no POFV |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | Bottom-side Economic target; **116 placements / 36 BOM rows** |
| Front panel | `ladder-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 50.5 x 128.5 mm, no assembly; **18 NPTH holes** (7 jacks 6.2, 5 pots 7.2, REC button 4.2, REC LED 3.2, 4 rail 3.2 mm) |

`carrier/` and `panel/` contain the exporter outputs, loose Gerbers/drills and export reports.
The upload ZIPs and assembly CSVs are byte-identical mirrors. `source-sha256.json` covers the five
native source files and the four export payloads.

Select supplier stack-up/finish/colour/quantity deliberately (target: JLC04161H-7628, 1 oz outer
copper, HASL). The board has no order-number marker; select that supplier option explicitly. No
quote or order was submitted.

## Manual assembly (excluded from both CSVs: 18 THT refs + JP1)

| Refs | Part / instruction |
|---|---|
| J1-J7 | PJ301M-12 TS jacks, F side; align to the panel before soldering |
| RV1-RV5 | RV09 50k linear pots, F side, upright |
| D11 | 3 mm REC LED, F side, dome flush with the panel; cathode = square pad 1 (GND) |
| SW1 | 6 x 6 x 7.3 mm THT tact (REC), F side |
| U10 / U12 | VTL5C vactrols (VCA / resonance), B side between the knob columns: solder first, trim flush (silk `SOLDER FIRST`, `TRIM FLUSH`; `+` / `-` at the LED pins 2 / 1) |
| J10 | Unshrouded 2x5 power header on B, upright at the right edge; red stripe / pin 1 to -12V (silk `-12V`) |
| J11 | Optional 1x2 UPDI header on B: square pin 1 UPDI, pin 2 GND (silk `UPDI`, `GND`) |
| JP1 | Copper-only MIDI jumper, shipped open: bridge the middle pad to `P` (protected / inverted RX through Q1) or to `D` (direct RX), never both |

## Verification (R2, 2026-11-10)

- Shared check: **ERC 0, DRC 0 (no warnings, no exclusions), unconnected 0, schematic parity 0**;
  source manifest equal, exports byte-identical. Panel native DRC 0; all 18 panel holes match the
  carrier jack / pot-shaft / LED / button centres.
- 734 tracks / 141 through vias (0.3 mm drill, 0.6 mm copper); no vias in SMD pads or within
  0.15 mm of one, no inner-layer tracks, In2 +12V_F one piece, In1 GND one main piece + four small
  spoke-tied fragments between THT pins (2.6 / 2.6 / 1.0 / 1.0 mm2, as on R1).
- Copper >= 1.2 mm from the outline (pours 1.0005 mm), courtyards >= 1.08 mm.
- SMD pads >= 2.01 mm from every pot / jack pad (closest D9 - RV2). Other hand-soldered pads
  (outside the pot / jack rule, same net or enough room for the iron, kept): R29 - U12.4 1.28 mm
  (same net), R28 - J11.1 1.58 mm, D2 - J10.1 1.75 mm (same net), D1 - J10 1.88 mm, R31 - J11.2 1.92 mm.
- Decoupling, routed pin-to-cap: every TL072 supply pin 1.7 - 2.9 mm, U2 2.7 mm; U1
  input cap C3 2.3 mm from the tab copper, output cap C4 2.5 mm. U3
  (TS5A23157, static uA load) +5V 11.3 mm to C7 and 7.4 mm to its GND via: kept for the prototype.
- U1 HT7550 drops 7 V at ~15 mA (~0.1 W): no tab copper needed.

Raw reports and review scripts: `../research/fab-baseline/`, `../research/fab-review/`,
`../research/fab-final/` (ignored).

## Sourcing (live lookup 2026-11-10, 5 boards as a screening quantity, not an order)

All 36 C-codes resolved to the intended MPNs and packages, all Economic-eligible. 29 rows are
Basic. Not Basic:

| Part | Code | Class | Public stock at lookup |
|---|---|---|---|
| C10-C13 47n NP0 1206 (ladder caps) | C20617849 | Extended | 1,895 |
| R47, R51 1k 0.5 W 1206 (ROHM ESR18) | C2074262 | Extended | 99,546 |
| Q3-Q8 DMMT3904W | C155305 | Extended | 4,034 |
| D5 BAT54SW | C78260 | Extended | 41,513 |
| U2 ATtiny1616-MF | C5227638 | Extended | **238** |
| U3 TS5A23157DGSR (MSOP-10) | C11133 | Extended | 4,934 |
| U1 HT7550-1 | C16106 | Preferred Extended | 181,206 |

The two Extended passives (47n NP0, 1k 0.5 W) are a user decision, as on modules/hats and
modules/acid; not waived. Public stock is not reserved. The formal audit is not order-ready: the
per-reference land-pattern / pin-mapping / rating attestations are not filled in.

Open before ordering: supplier preview (bottom-side rotations, pin 1 of U2 / U3 / Q3-Q8, diode
polarity), the Extended-passive decision, ATtiny1616 stock at order time. Bench: vactrol
resonance / VCA fit, cutoff scaling, MIDI jumper, firmware (not written).

## Reproduce from the repository root

Do not hand-edit generated CSV/Gerber files. Update native sources, refill/save, verify, then use
the shared exporter for both boards:

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/ladder/tools/kicad-project.json --reports modules/ladder/research/new-check

python3 -B opt/kicad-tools/jlcpcb/export.py modules/ladder/hardware \
  --board ladder --schematic ladder.kicad_sch --side bottom --require-part-numbers \
  --manifest modules/ladder/jlcpcb/source-sha256.json --overwrite -o modules/ladder/jlcpcb/carrier

python3 -B opt/kicad-tools/jlcpcb/export.py modules/ladder/panels/front-pcb \
  --board ladder-panel --pcb-only --manifest modules/ladder/jlcpcb/source-sha256.json \
  --overwrite -o modules/ladder/jlcpcb/panel

unzip -o modules/ladder/jlcpcb/carrier/ladder-gerbers.zip -d modules/ladder/jlcpcb/carrier
unzip -o modules/ladder/jlcpcb/panel/ladder-panel-gerbers.zip -d modules/ladder/jlcpcb/panel
cp modules/ladder/jlcpcb/carrier/bom.csv modules/ladder/jlcpcb/carrier/positions.csv modules/ladder/jlcpcb/assembly/
cp modules/ladder/jlcpcb/carrier/ladder-gerbers.zip modules/ladder/jlcpcb/panel/ladder-panel-gerbers.zip modules/ladder/jlcpcb/
```

Never run `tools/build_layout.py` over the routed carrier.
