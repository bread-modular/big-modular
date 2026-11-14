# vca-mix — manufacturing export (S6 / P6 / R3, 8HP)

Exported 2026-11-14 from the S6 schematic, the P6 / R3 carrier (8HP, 4 layers, RANGE pots)
and the 8HP FR4 panel with the unchanged shared `opt/kicad-tools/jlcpcb/export.py`, on user
direction. It replaces the S4 / R1 6HP export of 2026-10-20. **Complete matched export, not
supplier-accepted, not built.** Never hand-edit these files: change the sources, then
re-export with the commands below.

**R3 = fab-review fixes on the R2 routing (2026-11-14; local edits, no THT part moved):**

- C105 / C205 / C305 (MCP6002 +3V3 100n) moved from 10.9 mm down the +3V3 trunk to pin 8 of
  U102 / U202 / U302: routed pin-to-cap 2.2 mm. The cap's GND pad shares one via with the
  BAT54SW GND pin beside it.
- B silk legend at the JLCPCB minimum (1.0 mm high, 0.15 mm stroke): the vactrol notes
  (`SOLDER FIRST`, `TRIM FLUSH`, `LED 5mA`; were 0.8 mm) are now three horizontal lines in
  the pad-free block between the pot pins and the LED leads; board texts `VCA-MIX S6/R3` and
  `-12V`.
- JLC04161H-7628 stackup recorded in the board; In1 / In2 zone fills saved (equal to a fresh
  refill).
- The 15 vactrol-under-VOL-pot DRC items are **user-approved (2026-11-14)** and written as
  per-item exclusions by `tools/d10_exclusions.py` (D10). Nothing else is excluded and the
  rule stays at `error`.

## Contents

| Path | Data |
|---|---|
| `vca-mix-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `vca-mix-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (4 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `vca-mix-gerbers.zip` | **4 layers**, FR4, 1.6 mm, 39.3 x 110.0 mm; F signal / In1 GND / In2 +12V / B signal; stackup JLC04161H-7628 (1 oz outer, 0.5 oz inner), HASL, ordinary tented vias (0.6 / 0.3 mm), no via-in-pad / POFV; tracks 0.25 mm and 0.4 mm, clearance 0.2 mm. The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 88 parts in 17 BOM rows, all on the back |
| Front panel PCB | `vca-mix-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 40.3 x 128.5 mm (8HP), no assembly; black mask suits a panel |

No quote or order was submitted.

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J9, J11 | QingPu WQP-PJ301M-12 TS jack (IN / CV / OUT x 3, MIX) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV3 | Song Huei R0904N 50k linear tall trimmer (VOL 1-3) | Front-side THT, snap-in, no nut. **Fit after the vactrol under it** |
| RV4-RV6 | Song Huei R0904N 50k linear tall trimmer (RANGE 1-3) | Front-side THT, snap-in, no nut. Nothing under them |
| U104, U204, U304 | VTL5C-type vactrol (Bread Modular footprint) | Back-side THT under its VOL pot. **Fit it before that pot** (B silk `SOLDER FIRST`, `TRIM FLUSH`, `LED 5mA`; `+` / `-` at the LED leads) |
| J10 | 2x5 2.54 mm pin header | Eurorack power, back side, along the bottom edge; pins 1 / 2 (-12 V) at the B silk `-12V` |

The exporter excluded exactly these 20 refs, as THT (`carrier/export-report.json`).

Soldering notes:
- **Vactrol first, then its VOL pot.** The vactrol's LDR lead pair (pads 3 / 4) comes out on
  F under the pot body: solder it on F and trim it flush before the pot goes in. The LED
  pair (1 / 2) is clear of the pot.
- **The VOL pot's three pins come out on B under the vactrol body** (the 15 excluded DRC
  items are this stacking). Leave the vactrol a few mm off the board so the iron reaches
  them from the side, or solder them from F, where their pads lie just beyond the pot body
  outline. The two bracket lugs are clear on B. Not tried on a real board.
- Both planes connect to pads through thermal spokes; no special iron needed.
- Hand-soldered pins with SMD pads closer than 2 mm (outside the pot / jack rule): J10 has
  four (closest R402 at 1.29 mm from pin 7, C502 at 1.30 mm from pin 1), the vactrol leads
  25 (closest C403 at 1.09 mm from U304 pin 2, Rn10 at 1.18 mm from pin 4). Use a fine tip.
- **J10 has no key.** Plug the cable with the red stripe (-12 V) at the `-12V` silk.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift.

- Carrier PCB `e217cd7b1c0e4cd5a70f22d3902deafbc025ae1c4dc07878f2bdcd359a374ec3`.
- Carrier project `f35550e12486b50f3f380faa43dd7d3de5c51b2d575c855a76a401a3af56cc8d`.
- Carrier schematic `969a716e5bdea6d1c99af1f277295e905e20ea041abd89d350cf68d39d1e8e0f`.
- Panel PCB `4d1059dc6aac97737bb53fb65569f8ccb501275ba110a91c916110adef47d508`.
- Panel project `2cd86d43edad4b1d86d82b000a0a98e3fd2915bce9128e00555f6ee850019447`.

## Reproduce

From `modules/vca-mix`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board vca-mix --schematic vca-mix.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/vca-mix-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board vca-mix-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/vca-mix-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/vca-mix-gerbers.zip jlcpcb/panel/vca-mix-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change, so no stale plots remain beside a new
ZIP. After moving a vactrol or its pot, or a layout rebuild (new UUIDs), re-run
`tools/d10_exclusions.py` (usage in the file) before the export: it refuses unless the
active findings are exactly the approved 15. Never run `tools/build_layout.py` over the
routed carrier. The catalog audit (no requirements file yet) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/vca-mix-symbols.xml hardware/vca-mix.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/vca-mix/hardware --board vca-mix.kicad_pcb --symbols-xml /tmp/vca-mix-symbols.xml \
  --cpl modules/vca-mix/jlcpcb/carrier/positions.csv \
  --export-report modules/vca-mix/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export (2026-11-14)

- **Shared `check`** (after the export): ERC 0, 0 unconnected, schematic parity 0, manifest
  equal (5 sources, all exports byte-identical). DRC lists **15 items, all of them the
  excluded `pth_inside_courtyard` D10 stacking items** (5 per channel: the vactrol's two LDR
  leads inside the pot courtyard, the pot's three pins inside the vactrol courtyard); KiCad's
  own DRC has 0 active findings. The shared gate counts excluded items, so it still reports
  `order_ready: false` (D14).
- **Panel DRC:** 0 / 0.
- **Copper:** 467 track segments (B 382, F 85) / 82 vias; no tracks on In1 / In2; no via in
  or touching an SMD pad (closest via copper to pad copper 0.29 mm). In2 +12V one piece; In1
  GND one piece plus five spoke-tied slivers (2.6 mm² x 2 between the J10 GND pins, 1.0 mm²
  x 3 between each IN jack's TN / S pads). Saved fills equal a fresh refill.
- **Keep-outs:** copper >= 1.0 mm from the edge by rule (tracks 1.43 mm, vias 1.5 mm, pads
  1.33 mm); courtyards >= 1.025 mm; SMD pads >= 2.015 mm from every pot / jack pad (closest
  U401.4 to the OUT3 sleeve).
- **Decoupling, routed pin-to-cap:** every TL072 -12V pin 1.7 - 2.1 mm; +12V 2.9 mm (Un01),
  9.0 mm (Un03) and 8.1 mm (U401), the last two through the In2 plane; MCP6002 2.2 mm; U501
  HT7533-1 output cap 2.3 mm, input cap 7.1 mm. The 7 - 9 mm ones are kept for the first
  prototype (all fed from the solid +12V plane), not waived: check the outputs and the
  +3V3 rail for oscillation on the bench.
- **Carrier drill file:** 82 via hits (0.3 mm) + 40 round pads (1.0 mm: 10 J10, 18 pot pins,
  12 vactrol leads) + 42 routed slots (30 jack lugs, 12 pot bracket tabs) = 164, matching 82
  vias + 82 THT pads. No NPTH holes.
- **Panel drill file:** 20 NPTH holes: 10 jacks (6.2 mm), 6 pots (7.2 mm), 4 rail holes
  (3.2 mm); jack holes on the carrier jack centres, pot holes on the shaft axes. No copper
  holes.
- **Gerber ZIP:** 13 files: four copper layers (In1 / In2 with their planes), both masks
  (vias tented, no via openings), silkscreens and pastes, the edge, PTH/NPTH drills. B.Paste
  has the 240 SMD pads; F.Paste is empty because there are no front SMD parts.
- **BOM/CPL:** 88 parts, 17 rows, every row with LCSC, MPN and manufacturer; the 88 CPL rows
  are the board's 88 SMD footprints, all `bottom`.
- **3D fit:** 0 mm³ interference for jacks and pots against both panels
  (`../docs/fit/fit-report.json`; vactrols not modelled, D4).
- **Catalog audit** (live, 5 boards, 2026-11-14 13:07 UTC): all 17 C-codes resolve to their
  MPN and package and are Economy-eligible. 14 rows are Basic. Not Basic, all user-accepted:

  | Part | Code | Class | Public stock at lookup |
  |---|---|---|---|
  | R105, R205, R305, R404 1k 1 W 2512 | C54315 | Extended (D7) | 60,375 |
  | U102, U202, U302 MCP6002T-I/SN | C7377 | Preferred Extended (D16) | 67,081 |
  | D101, D201, D301 BAT54SWT1G | C78260 | Extended (D16) | 168,051 |

  Lowest Basic stock: TL072CDT C6961, 120,398. Stock is a snapshot, not a reservation. The
  audit itself is not order-ready: there is no `docs/jlcpcb-audit-requirements.json`, so
  the per-part requirement / review rows stay `unknown`; it also flags the Extended 2512
  resistor, the 20 THT refs (no code) and the exporter's standing preview warning. That is
  expected, not a catalog failure.

Raw reports, the review script and its output: `../research/fab/` (ignored).

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly.** Confirm the quote form offers **Bottom** for
   Economic with the two Extended parts and the Preferred Extended MCP6002.
2. **Placement preview.** Check in JLCPCB's bottom-side preview:
   - the 7 TL072s and 3 MCP6002s (SOIC-8): the pin 1 dot;
   - D101-D301 (BAT54SW, SOT-323) and U501 (HT7533-1, SOT-89): orientation;
   - D501 / D502 (B5819W): the cathode bands;
   - every rotation: bottom-side CPL rotations are the usual place for errors.
3. **Live recheck before ordering:** stock, Basic / Extended class, minimum assembly
   quantities and attrition. The figures above are a snapshot.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs, with the 4-layer stackup chosen.
5. **Bench** (D4 / D15 / D17): vactrol fit under the VOL pot and the pot-pin soldering,
   LED current and the driver ceiling near the top of the CV range, the Rn14 value for the
   RANGE knob, the real pot and jack panel fit.
