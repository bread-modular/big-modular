# DRIVE manufacturing export — S1 / R2 / P2

Exported 2026-11-15 from the S1 schematic, the R2 2-layer routed carrier and the P2 panel with the
unchanged shared `opt/kicad-tools/jlcpcb/export.py` (commands at the end). **Complete matched
export, not supplier-accepted, not built, not bench-validated.**

| Order | Files | Configuration |
|---|---|---|
| Carrier PCB | `drive-gerbers.zip` | **2 layers**, FR4, 1.6 mm, 29 x 110 mm; GND pours on F and B; ordinary tented vias, no POFV |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | Bottom-side Economic target; **83 placements / 29 BOM rows** |
| Front panel | `drive-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30 x 128.5 mm, no assembly; 10 NPTH holes |

`carrier/` and `panel/` hold the exporter outputs, loose Gerbers / drills and export reports.
The upload ZIPs and assembly CSVs are byte-identical mirrors. `source-sha256.json` covers the
five native source files and the four export payloads.

## Manual assembly (excluded from both CSVs)

| Refs | Part / instruction |
|---|---|
| J10 | Unshrouded 2x5 power header on B, upright at the right edge. **Solder it first** (its joints are on F between the MIX pot and the OUT jack). Red stripe / pin 1 to -12V at the bottom (silk `-12V`) |
| J1-J4 | PJ301M-12 TS jacks, F side; align to the panel before soldering |
| RV1-RV4 | RV09 50k linear pots, F side. Trim the RV4 leads to <= 2 mm: a 16-pin power cable overhangs them |

## Verification

- Shared check (`../research/r2-final-check/`): ERC 0, DRC 0 violations (no exclusions),
  unconnected 0, schematic parity 0, source manifest equal, exports byte-identical.
- Panel native DRC 0; every panel hole on its carrier part.
- 455 tracks / 102 vias, no vias in SMD pads. GND pours: B one main piece + two pad / via-tied
  pieces, F one main piece + 12 via-stitched pieces; spoke-tied fragments between GND pads.
  BOM and positions are byte-identical to the R1 export. SMD pads >= 2.025 mm from pot / jack pads,
  copper >= 1.1 mm and courtyards >= 1.02 mm from the edge.
- Fab review: `../docs/research.md` section 6 (R2 table).
- Not an authenticated supplier placement preview or a full Gerber CAM / DFM signoff.

## Sourcing (public catalog, 2026-11-15, 5 boards as a screening quantity)

Strict-live audit of the 29 C-codes (run for R1, same BOM; `../research/r1-audit/`, ignored): 28 resolved to the
intended MPN, Economic-eligible, with stock far above the screening quantity. C1653 (22p, C4)
does not resolve by exact code in the tool (short-code ambiguity); the earlier MPN search found
it as Basic (`../docs/sourcing-candidates.json`).

- **Extended:** LM13700MX/NOPB C174050 (10,529 in stock) and the 1 W 2512 1k C54315 (60,289).
  User decision open.
- **Preferred Extended (no feeder fee):** 240k C4197. Everything else is Basic.
- The formal audit is not passed / order-ready: per-part land-pattern, pin-mapping and rating
  attestations are not recorded. Stock is an observation, not a reservation.

Before ordering: check part matches, pin 1 / polarity / rotations in the JLCPCB preview, DFM,
stock and attrition at the order quantity.

## Reproduce from the repository root

Do not hand-edit generated CSV / Gerber files.

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/drive/tools/kicad-project.json --reports modules/drive/research/new-check

python3 -B opt/kicad-tools/jlcpcb/export.py modules/drive/hardware \
  --board drive --schematic drive.kicad_sch --side bottom --require-part-numbers \
  --manifest modules/drive/jlcpcb/source-sha256.json --overwrite -o modules/drive/jlcpcb/carrier

python3 -B opt/kicad-tools/jlcpcb/export.py modules/drive/panels/front-pcb \
  --board drive-panel --pcb-only --manifest modules/drive/jlcpcb/source-sha256.json \
  --overwrite -o modules/drive/jlcpcb/panel

unzip -o modules/drive/jlcpcb/carrier/drive-gerbers.zip -d modules/drive/jlcpcb/carrier
unzip -o modules/drive/jlcpcb/panel/drive-panel-gerbers.zip -d modules/drive/jlcpcb/panel
cp modules/drive/jlcpcb/carrier/bom.csv modules/drive/jlcpcb/carrier/positions.csv modules/drive/jlcpcb/assembly/
cp modules/drive/jlcpcb/carrier/drive-gerbers.zip modules/drive/jlcpcb/panel/drive-panel-gerbers.zip modules/drive/jlcpcb/
```

Never run `tools/build_layout.py` without `--panel-only`: the carrier is routed.
