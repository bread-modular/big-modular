# LADDER manufacturing export — S5 / R1 / panel

Exported 2026-11-15 from the S5 schematic, the fab-reviewed R1 carrier (6HP, pure analog,
4 layers) and the 6HP panel, using the unchanged shared `opt/kicad-tools/jlcpcb/export.py`
(commands at the end). **Complete matched export, not supplier-accepted, not built, not
bench-tested.** The S3 / R2 / 10HP export that lived here before is in git history (commit
`b32225b` and before); it does not match these sources.

| Order | Files | Configuration |
|---|---|---|
| Carrier PCB | `ladder-gerbers.zip` | 4 layers, FR4, 1.6 mm, 29 x 110 mm; F / In1 GND / In2 +12V_F / B; stackup JLC04161H-7628; ordinary tented vias, no POFV |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | Bottom-side Economic target; **95 placements / 30 BOM rows**, every row with an LCSC code |
| Front panel | `ladder-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30 x 128.5 mm, no assembly; **11 NPTH holes** |

`carrier/` and `panel/` hold the exporter outputs, loose Gerbers / drills and export reports.
The upload ZIPs and assembly CSVs are byte-identical mirrors. `source-sha256.json` covers the
five native source files and the four carrier / panel export payloads.

## Manual assembly (excluded from both CSVs)

Exporter exclusion list = these 10 THT refs + JP1..JP3.

| Refs | Part / instruction |
|---|---|
| J4, J5 / J3 / J6 | PJ301M-12 TS jacks, F side: IN, RES CV / CV / OUT |
| RV2, RV3, RV4 | RV09 50k linear pots, F side: DEPTH, CUTOFF, RES |
| D11 / D12 | 3 mm CV LEDs, F side under DEPTH, dome flush with the panel: D11 red (`+`), D12 second colour (`-`); cathode = square pad |
| J10 | Unshrouded 2x5 power header on B, upright at the right edge; red stripe / pin 1 to -12V (silk `-12V`) |
| JP1..JP3 | Copper-only LED brightness jumpers, shipped open (B silk `LED` `1` `2` `3`); bridge to step the CV LED current up (`../README.md` table) |

## Verification (2026-11-15)

- Shared check before and after the export (`../research/export-check/`,
  `../research/export-check-post/`, ignored): ERC 0, DRC 0, unconnected 0, schematic parity 0,
  no exclusions, no ignored severities; source manifest **equal** (5 sources, exports
  byte-identical); sources unchanged by check / export.
- Panel native DRC (`--severity-all`): 0 violations, 0 unconnected.
- BOM refs = CPL refs (95), all on `bottom`; quantities sum to 95. Carrier ZIP: 4 copper
  layers, both masks / pastes / silks, Edge.Cuts, PTH + NPTH drills (13 members). Panel NPTH:
  2 rail holes 3.2 mm, 2 LED holes 3.2 mm, 4 jack holes 6.2 mm, 3 pot holes 7.2 mm.
- Board facts from the fab review (`../docs/research.md` section 9), unchanged since: 521
  tracks / 81 vias, no vias in SMD pads, no tracks on In1 / In2, SMD >= 2 mm from pot / jack
  pads (closest 2.015 mm), copper and courtyards >= 1.0 mm from the edge.

This is not an authenticated JLCPCB placement preview or a full Gerber CAM / DFM signoff.

## Sourcing

From the fab review's live lookup (2026-11-15 13:31 UTC, `../docs/research.md` section 9; not
re-checked here, stock is a dated observation, not reserved): all codes Economic-eligible.
Plain Extended: DMMT3904W C155305 (684 in stock, 6 per board), 47n NP0 C20617849,
LM13700MX/NOPB C174050, ESR18 1k C2074262 (R47). Preferred Extended: HT7550-1 C16106. TL072CDT
C6961 and MMBT5401 C8326 Basic.

Before ordering: JLCPCB preview of every bottom-side part (pin 1 / polarity / rotation, SOT-363
DMMT3904W and SOIC-16 LM13700 especially), drill / outline preview, stackup and finish selected
deliberately (no order-number marker on the board), stock at the chosen quantity. Bench: power,
self-oscillation point, CV LED brightness, LTAIL beside AIN_BUF (12 mm, estimate only).

## Reproduce from the repository root

Never hand-edit generated files. Update native sources, refill / save, verify, then:

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

Prune stale board-prefixed loose files if the layer set changes; recheck the manifest and
mirrors after export. Panel only from geometry: `python3 -B modules/ladder/tools/build_layout.py
--panel-only`. Never run the carrier builder over the routed board.
