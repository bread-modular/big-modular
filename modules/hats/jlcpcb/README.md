# HATS manufacturing export — S4 / R6 / P5

Re-exported 2026-11-09 from the S4 schematic (one STM32G071C8T6, PWM cutoff vactrol U11, REC
button + LED), the R6 carrier and the P5 panel, using the unchanged shared
`opt/kicad-tools/jlcpcb/export.py` (commands at the end). **Complete matched export, not
supplier-accepted or bench-validated; the STM32 firmware in `../firmware/` is compiled, not run on hardware.**

**R6 = fab fixes on R5 (2026-11-09, user-approved local re-route, no THT part moved).** U2 support
caps at their pins (routed pin-to-pad length): C6 (VDD) GND 2.1 mm from pin 7, +3V3 4.2 mm on the
pin-6 track, under-chip GND via on pin 7; C25 (VREF+) 2.3 mm from pin 5; C26 (NRST) 5.6 mm on the
pin-10 escape (was ~22.7 mm by J11). C19 took C6's old spot; C20 moved below U9; FB1 below C26. U1 HT7533 tab gets
+12V_F copper on B (27.5 mm2) and F (78.8 mm2) tied by 8 tented vias beside the tab. The 18
U11/RV1/RV2 stacking items are now user-approved exclusions like U7's. Board text `HATS R6`.
BOM unchanged; CPL changes only C6, C19, C20, C25, C26, FB1 (non-polar). Outline, NPTH and
F mask/paste/silk Gerbers are unchanged; copper, B mask/paste/silk and PTH drill changed.
Panel export untouched.

R5 (same day) = R4 copper + B silk: J11 legend `SWD` + `3V3 DIO CLK GND RST` (pin 1 = square
pad = 3V3/VTref), U7/U11 `SOLDER FIRST` / `TRIM FLUSH` at 1.0 mm / 0.15 mm, `-12V` beside J10.

| Order | Files | Configuration |
|---|---|---|
| Carrier PCB | `hats-gerbers.zip` | 4 layers, FR4, 1.6 mm, 29 x 110 mm; F/In1 GND/In2 +3V3/B; ordinary tented vias, no POFV |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | Bottom-side Economic target; **95 placements / 33 BOM rows** |
| Front panel | `hats-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30 x 128.5 mm, no assembly; **13 NPTH holes** (REC button 4.2 mm, REC LED 3.2 mm added) |

BOM changes from R3: U2/U3 ATtiny1616 -> one U2 STM32G071C8T6 (C529341, Extended); new FB1
600R ferrite (C1002), C24 1u, C25/C26 100n, C7 4.7u (+3V3 bulk), C27/C28 10n wiper caps, R48 1k
(REC LED), R50 51k (across the U11 LDR), R51 330R (U11 LED); R4/R5 4.7k removed.

Manual assembly (excluded from both CSVs; exporter list = these 15 THT refs + JP1):

| Refs | Part / instruction |
|---|---|
| J1-J4 | PJ301M-12 TS jacks, F side |
| RV1, RV3, RV4 / RV2 | RV09 50k / 1M linear pots, F side, upright |
| D5 / D6 | 3 mm ENV LED / 3 mm REC LED, F side, dome flush with the panel; cathode = square pad 1 |
| SW1 | 6 x 6 x 7 mm THT tact (REC), F side, bottom left; 8bit/16bit printed cap |
| U7 | VTL5C vactrol, B side, under RV3: solder first, trim flush, then fit RV3 |
| U11 | VTL5C vactrol (cutoff), B side, under RV1/RV2: solder first, trim flush, then fit RV1/RV2 |
| J10 | Unshrouded 2x5 power header on B; red stripe / pin 1 to -12V (silk `-12V` beside pins 1/2) |
| J11 | Optional 1x5 SWD header on B: +3V3, SWDIO, SWCLK, GND, NRST (pin 1 square; silk `SWD`, `3V3 DIO CLK GND RST`) |
| JP1 | Copper-only MIDI jumper, shipped open (1-2 protected/inverted RX, 2-3 direct RX) |

Verification (R6, 2026-11-09): shared check ERC 0, DRC unconnected 0, native schematic parity 0
(the literal ref/pin/net comparison differs only in the four pre-existing `{slash}` NC-name
escapes, U2 29/32/33/34), source manifest equal, exports byte-identical, upload mirrors identical. DRC lists 36 items, all vactrol
stacking and all excluded (user-approved): 18 U7/RV3/RV4 (2026-11-03) and 18 U11/RV1/RV2
(2026-11-09; 10 `pth_inside_courtyard`, 8 `silk_over_copper`); the shared gate still counts them.
639 tracks / 131 vias, no vias in SMD pads, no inner tracks, In1 GND and In2 +3V3 one piece each,
closest SMD-to-pot/jack pad 2.05 mm, RV1-RV4 courtyards unchanged (existing pot-column
exception). Raw reports: `../research/fab-fix2/` (ignored). Open before ordering: supplier
preview/placement review; R43/R46 Extended (Basic 1k is 0.25 W 1206 C4410 / 0.125 W 0805; 0.5 W
needs two Basic 2k C17944 in parallel per output, a schematic change with no room in the edge
columns, so kept); U1 tab temperature on the prototype (~0.33 W estimated). Sourcing: the
STM32G071C8T6 and the ferrite were live-checked for modules/12bit on 2026-11-06; not re-checked
here, no stock claim.

The S3/R3 notes below are history.

---

## History: S3 / R3 / P4 export

Re-exported 2026-11-03 from the S3 schematic, the R3 routed carrier (all pots upright, vactrol
U7 under CUTOFF, ENV LED between AUDIO OUT and HAT CV) and the P4 panel (LED hole X15 Y102, on the jack centre line) using the unchanged
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
| RV1, RV3, RV4 | RV09 50k linear pots, F side; all upright, solder pins below the shafts |
| RV2 | RV09 1M linear pot, F side |
| D5 | 3 mm ENV LED only, F side, midway between J3 and J4 on their centre line; cathode to square (lower) pad, dome flush with panel |
| U7 | VTL5C-type vactrol, B side, under RV3: solder U7 first, trim its leads flush, then fit RV3 |
| J10 | Unshrouded 2x5 power header on B, horizontal at bottom; red stripe / pin 1 to -12V |
| J11, J12 | Optional 1x2 UPDI headers on B; square pin UPDI, other pin GND |
| JP1 | Copper-only jumper, shipped open. Bridge 1-2 for protected/inverted RX or 2-3 for direct/unprotected 3.3 V RX; never both |

Exactly 13 THT refs plus JP1 are excluded. SW1, D6 and R48 are **absent**, not DNP or manual
assembly options. The panel has no REC button/LED apertures or legend.

## Verification

R3 re-export (2026-11-03): shared check ERC 0, DRC unconnected 0, schematic parity 0, exact
ref/pin/net parity equal, source manifest equal. DRC lists only the 18 user-approved U7/RV3/RV4
stacking items (10 `pth_inside_courtyard`, 8 `silk_over_copper`), all excluded via
`tools/vactrol_exclusions.py` and still counted by the shared gate. 498 tracks / 94 vias, no
vias in SMD pads, no inner tracks, inner planes one piece, closest SMD-to-pot/jack pad 2.045 mm.
BOM unchanged (33 rows); CPL updated. Panel DRC 0. The R2 notes below are historical.

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

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
