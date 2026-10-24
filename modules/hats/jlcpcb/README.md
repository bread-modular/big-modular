# HATS manufacturing export — S3 / R2 / P4

Generated from the current S3 schematic, R2 routed carrier and P4 panel using the unchanged
shared `opt/kicad-tools/jlcpcb/export.py`. Recording hardware is removed, pot row pitch is
34 mm, NOISE IN detection has R49/D7 protection, and all copper has >=1 mm edge setback.
**Complete matched export, not supplier-accepted or bench-validated.**

## Files to upload

| Order | Files | Configuration |
|---|---|---|
| Carrier PCB | `hats-gerbers.zip` | 4 layers, FR4, 1.6 mm, 29 x 110 mm; F/In1 GND/In2 +3V3/B; ordinary tented vias, no POFV |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | Bottom-side Economic target; **89 placements / 33 BOM rows** |
| Front panel | `hats-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30 x 128.5 mm, no assembly; 11 NPTH holes |

`carrier/` and `panel/` contain the exporter outputs, loose Gerbers/drills and export reports.
The upload ZIPs and assembly CSVs are byte-identical mirrors. `source-sha256.json` covers
all five native source files and the four carrier/panel export payloads. All hashes match;
the earlier stale project hash has been replaced by a genuinely regenerated package.

Select supplier stack-up/finish/color/order quantity deliberately. The previous target was
standard stack-up, 1 oz outer copper and HASL. The board has no order-number marker; select
that supplier option explicitly. No supplier quote or order settings were submitted.

## Manual assembly (excluded from both CSVs)

| Refs | Part / instruction |
|---|---|
| J1-J4 | PJ301M-12 TS jacks, F side; align to panel before soldering |
| RV1, RV3, RV4 | RV09 50k linear pots, F side; RV3/RV4 rotated 180 degrees, solder pins above shafts |
| RV2 | RV09 1M linear pot, F side |
| D5 | 3 mm ENV LED only, F side; cathode to square pad, dome flush with panel |
| U7 | VTL5C-type vactrol, B side; no switch underneath |
| J10 | Unshrouded 2x5 power header on B, horizontal at bottom; red stripe / pin 1 to -12V |
| J11, J12 | Optional 1x2 UPDI headers on B; square pin UPDI, other pin GND |
| JP1 | Copper-only jumper, shipped open. Bridge 1-2 for protected/inverted RX or 2-3 for direct/unprotected 3.3 V RX; never both |

Exactly 13 THT refs plus JP1 are excluded. SW1, D6 and R48 are **absent**, not DNP or manual
assembly options. The panel has no REC button/LED apertures or legend.

## Verification

- Shared native check: **ERC 0, DRC 0, unconnected 0, schematic parity 0**; includes warnings
  and exclusions. Exact ref/pin/net and metadata parity pass; no ignored ERC/DRC severities or
  DRC exclusions remain. Source files are unchanged by checks/export.
- Panel native DRC: 0 violations / 0 opens; all 11 holes align to the carrier/geometry contract.
- Four saved copper layers and all four exported copper Gerbers: **1.0005 mm** pour setback.
  Copper-edge rule = 1.0 mm. Other pad/track/via copper is >=1.09 mm from the outline.
- Existing user-approved RV1-RV4 courtyard exception remains: 0.815 mm measured line-box
  margin (historical cached-yard documentation quoted 0.77 mm). No copper exception.
- 536 tracks / 99 through vias (0.3 mm drill, 0.6 mm copper); no in-pad/mask-opening vias,
  no inner-layer tracks, one continuous filled piece per inner plane, no disconnected outer
  GND pours. No zero-length/duplicate tracks or off-centre via endpoints remain.
- SMD-to-pot/jack pad clearance >= **2.0465 mm**. Pot rows Y41/Y75, 34 mm pitch; U7 centre Y88.
- BOM/CPL refs and quantities match; all selected parts are bottom-side with LCSC/MPN fields.
  CPL transforms match native footprints. ZIP CRCs, loose members, upload mirrors and hashes pass.
- Native schematic, all copper plots, bottom paste/assembly and panel drawing were inspected.
  This is not an authenticated supplier placement preview or a full Gerber CAM/DFM signoff.

Raw evidence: `../research/s3-r2/` (ignored), including `final-native/`, `panel-drc.json`,
`geometry-audit.json`, `independent-verification.json`, `package-verification.json`,
`assembly-audit.json` and catalog snapshots.

## Sourcing and remaining assembly gates

A new strict-live audit covered all **33 C-codes**, using **5 boards as a screening quantity**
only, not as an order. All codes resolved to the intended MPNs and showed Economy eligibility
and enough public stock for that screening quantity at retrieval. Exact UTC timestamps,
source URLs and raw-response hashes are retained in `assembly-audit.json` / `catalog/`.

- New R14 C23178 (470k) and R49 C31850 (22k) are Basic; D7 C40919 (BAV199,215) is Extended.
- Existing Extended nonpassives remain SS8050, SS8550, MCP6002, ATtiny1616 and TS5A23157.
  Preferred Extended is not Basic.
- **R43/R46, ROHM ESR18EZPF1001 C2074262 (1k, 1206, 0.5 W), remain Extended.** The package is
  not all-Basic passives; the strict passive sourcing/signoff exception remains unresolved.
- The formal audit is **not passed/order-ready**: per-reference human land-pattern/pin-mapping/
  rating attestations and complete application requirements are still missing. No blanket
  approval records were fabricated. Public stock is not reserved and excludes unverified
  attrition/minimum/reel requirements.

Before ordering, verify exact bottom-side component matches, pin 1/polarity/rotations,
carrier/panel DFM and drill/outline previews, service options, stock and attrition at the
chosen quantity. Bench validation remains for power/thermal, MIDI jumper/inversion,
NOISE IN contact transients/normalling, physical fit and actual audio/CV levels.
Firmware clock/reference settings were deliberately left untouched at the user's request.

## Reproduce from the repository root

Do not hand-edit generated CSV/Gerber files. Update native sources, refill/save, verify,
then use the shared exporter for **both** boards:

```sh
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/hats/tools/kicad-project.json --reports modules/hats/research/new-check

python3 -B opt/kicad-tools/jlcpcb/export.py modules/hats/hardware \
  --board hats --schematic hats.kicad_sch --side bottom --require-part-numbers \
  --manifest modules/hats/jlcpcb/source-sha256.json --overwrite -o modules/hats/jlcpcb/carrier

python3 -B opt/kicad-tools/jlcpcb/export.py modules/hats/panels/front-pcb \
  --board hats-panel --pcb-only --manifest modules/hats/jlcpcb/source-sha256.json \
  --overwrite -o modules/hats/jlcpcb/panel

unzip -o modules/hats/jlcpcb/carrier/hats-gerbers.zip -d modules/hats/jlcpcb/carrier
unzip -o modules/hats/jlcpcb/panel/hats-panel-gerbers.zip -d modules/hats/jlcpcb/panel
cp modules/hats/jlcpcb/carrier/bom.csv modules/hats/jlcpcb/carrier/positions.csv modules/hats/jlcpcb/assembly/
cp modules/hats/jlcpcb/carrier/hats-gerbers.zip modules/hats/jlcpcb/panel/hats-panel-gerbers.zip modules/hats/jlcpcb/
```

Prune stale board-prefixed loose Gerber/drill files if the layer/member set changes. Recheck
all manifest entries and mirrors after export. To update just the panel from geometry:
`/usr/bin/python3 -B modules/hats/tools/build_layout.py --panel-only`.
Never run the carrier builder over a routed design.
