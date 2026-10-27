# vca-mix — manufacturing export (S4/P4/R1)

Generated on 2026-10-20 from the current R1 sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit
these files: change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `vca-mix-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `vca-mix-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `vca-mix-gerbers.zip` | 2 layers, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz, HASL, standard everything else. The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately: "Remove" (check the quote for any fee), or JLCPCB prints the number where it chooses |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 82 parts in 13 BOM rows, all on the back |
| Front panel PCB | `vca-mix-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly; black mask suits a panel |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J9, J11 | QingPu WQP-PJ301M-12 TS jack (IN/CV/OUT x 3, MIX) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV3 | Song Huei R0904N 50k linear tall trimmer (VOL1-3) | Front-side THT, snap-in, no nut. Seat flat before soldering |
| U104, U204, U304 | VTL5C-type vactrol (Bread Modular footprint) | Back-side THT behind its pot. **Fit it before its pot** (B silk `SOLDER FIRST`, `TRIM FLUSH`): its leads sit under the pot body (D10) |
| J10 | 2x5 2.54 mm pin header | Eurorack power, back side; pin 1 (-12 V) next to the B silk `-12V` |

The exporter excluded exactly these 17 refs, as THT (`carrier/export-report.json`).

Soldering notes:
- Both GND pours connect to GND pads **solid** (D12, no thermal relief), so the
  jack sleeves, pot pin 1 and the J10 GND pins need a hotter iron.
- Each pot's left bracket tab (no net) lands under the vactrol body; once the
  vactrol is in, that tab may be hard to reach. It is mechanical only.
- **J10 has no key.** Plug the cable with the red stripe (-12 V) at the `-12V`
  silk.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `ce6988072882559cbbac5108f4447019db4ff28b7b68ad9aac9cdc9700597509`.
- Carrier project `cd8ac5fcfe2f606b9ed0794aa53dc5de7db0516c540cc34ddc14a904eb36c780`.
- Carrier schematic `b9288a508a262cef9beb223b59c811b66cc1af1d7fba18c255943d9ce8262cac`.
- Panel PCB `d625398bec31045501ebb3c6826d7874f126f42466971db3cb8a37914b7cc5f0`.
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

Delete the unpacked Gerbers first if layers change, so no stale plots remain
beside a new ZIP. The catalog audit (no requirements file yet) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/vca-mix-symbols.xml hardware/vca-mix.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/vca-mix/hardware --board vca-mix.kicad_pcb --symbols-xml /tmp/vca-mix-symbols.xml \
  --cpl modules/vca-mix/jlcpcb/carrier/positions.csv \
  --export-report modules/vca-mix/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- **Shared `check`** (after the export): ERC 0, 0 unconnected, schematic parity
  0, manifest equal (5 sources, all exports byte-identical). DRC = the **9
  `pth_inside_courtyard` D10 exclusions**, nothing else, so `order_ready` is
  `false` (D14, accepted by the user; the 9 are verified by hand).
- **Panel DRC:** 0 / 0.
- **GND pours:** the saved fill equals a fresh refill.
- **Carrier drill file:** 71 round PTH hits (40 vias + 31 round pads: 10 J10,
  12 vactrol, 9 pot pins) plus 36 routed slots (30 jack lugs, 6 pot bracket
  tabs) = 107, matching 40 vias + 67 THT pads. No NPTH holes.
- **Panel drill file:** 15 NPTH holes: 10 jacks (6.2 mm), 3 pots (7.2 mm), 2
  rail holes (3.2 mm). No copper holes.
- **Gerber ZIP:** both copper layers with their GND pours, both masks,
  silkscreens and pastes, the edge, and PTH/NPTH drills. F.Paste is empty
  because there are no front SMD parts.
- **BOM/CPL:** 82 parts, 13 rows, every row with LCSC, MPN and manufacturer;
  every CPL row is `bottom`.
- **3D fit:** 0 mm³ interference for jacks and pots against both panels
  (`docs/fit/fit-report.json`; vactrols not modelled, D4).
- **Catalog audit** (live, 5 boards, 2026-10-20 03:39 UTC): every C-code
  resolves to its MPN and package and is Economy-eligible. All parts are Basic
  except R105/R205/R305/R404 (C54315, 1 W 2512, Extended, 72,292 in stock; the
  audit flags Extended R/C, accepted as D7). Lowest Basic stock: B5819W C8598,
  484,751. There is no `docs/jlcpcb-audit-requirements.json` yet, so the
  per-part requirement/review rows stay `unknown` and the audit fails on them
  and on the 17 THT refs; that is expected, not a catalog failure.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly.** Confirm the quote form offers **Bottom**
   for Economic, with the Extended 2512 part.
2. **Placement preview.** Check in JLCPCB's bottom-side preview:
   - all 10 TL072s (SOIC-8): the pin 1 dot;
   - D101-D301 (1N4148W) and D501/D502 (B5819W): the cathode bands;
   - every rotation: bottom-side CPL rotations are the usual place for errors.
3. **Live recheck before ordering:** stock, Basic/Extended class, minimum
   assembly quantities and attrition. The figures above are a snapshot.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench** (D4/D8): vactrol fit and LED current, the TL072 driver headroom at
   +12 V CV, the real pot and jack panel fit.
