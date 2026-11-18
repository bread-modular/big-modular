# ENV — manufacturing export (S5/R2, 5 V)

Re-exported on 2026-11-18 after **R20 470k (ENV OUT idle pull-down to -12V_F)** was placed and
routed (S5 schematic, R2 board: R1 copper + R20, two short B links, one via and one F run; see
`docs/research.md` sections 7 and 8), using the unchanged shared
`opt/kicad-tools/jlcpcb/export.py`. P7 placement of every other part and the panel geometry are
unchanged. The S4 conversion (U1 HT7550-1 / +5V, R5-R8 1k) is in `docs/research.md` section 6.
Never hand-edit generated fabrication or assembly files: change the sources, then export.

## Upload files

| Order | Files | Options |
|---|---|---|
| Carrier PCB | **`env-gerbers.zip`** | 2 layers, FR4, 1.6 mm, nominal 29.0 x 110.0 mm, 1 oz, HASL, tented vias; no filled/capped via-in-pad requirement |
| Carrier assembly | **`assembly/bom.csv`, `assembly/positions.csv`** | Bottom-side Economic PCBA target; **37 parts in 19 BOM rows**, all on B. Supplier acceptance is still pending |
| Front panel PCB | **`env-panel-gerbers.zip`** | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly |

The carrier has no `JLCJLCJLCJLC` marker; choose the order-number option deliberately.
All 27 vias are 0.3 mm drill / 0.6 mm copper and clear of SMD copper/mask openings.
The board's stroke-inclusive outline bounding box is 29.05 x 110.05 mm, not its nominal
edge-centre dimensions above.

`carrier/` and `panel/` contain the exporter ZIPs, their unpacked Gerbers/drills, BOM/CPL
and export reports. Top-level ZIPs and `assembly/` CSVs are byte-identical mirrors.
`source-sha256.json` binds the five native sources to the exported ZIPs/BOM/CPL.

### Changed assembly parts

S5 / R2 adds one part and one BOM row; no other CPL line changed:

| Reference | Part | Position (B) |
|---|---|---|
| R20 | **470k, C23178**, UNI-ROYAL 0603WAF4703T5E, 0603 | X120.925 Y121.4, rot 0, left of C8 |

S3 -> S4 (history):

| References | S3 | S4 |
|---|---|---|
| U1 | HT7533-1, C14289 | **HT7550-1, C16106**, Holtek, SOT-89-3; same pin mapping / land pattern |
| R5, R6, R7, R8 | 330R, C23138 | **1k, C21190**, UNI-ROYAL 0603WAF1001T5E, 0603 |

R9/R13 already use the same 1k 0603 part, so their row now includes R5-R8 and the BOM
shrinks from 19 to 18 rows. R13 (ENV level LED) and R10/R11 (output gain) are unchanged.
The complete CPL is byte-identical to S3: no part moved or rotated.

## Hand-soldered after delivery (excluded from BOM and CPL)

| Refs | Part / handling |
|---|---|
| J1, J2, J5, J6 | QingPu WQP-PJ301M-12 TS jacks: MIDI IN, ENV OUT, MIDI OUT, GATE IN; front-side THT, fit to panel before soldering |
| RV1, RV2 | RV09 50k linear ATTACK / RELEASE pots; front-side THT, no nut |
| SW1, SW2 | 6 x 6 mm THT MODE / REC switches |
| D4-D8 | 3 mm red HR / AR / ASR / REC / ENV LEDs; set height to panel holes |
| J3 | 2x5 2.54 mm header, back side, vertical; pin 1 (-12 V) at bottom. **Unkeyed: red stripe to -12V silk.** 10- or 16-pin cable |
| J4 | Optional 1x2 UPDI/GND header; pin 1 square/top = UPDI. Module is now a **5 V target**; use a compatible programmer, module externally powered |
| JP1 | Copper-only 3-pad jumper, shipped open. P = 1-2 protected, PB3 inversion on; D = 2-3 direct, inversion off. Never both. **Use P for 3.3 V senders; D is unprotected 5 V logic only** |

The export excludes exactly 15 THT references plus JP1; see `carrier/export-report.json`.

## Catalog observations and unresolved assembly gates

**R20 (S5):** C23178 looked up on 2026-11-18 on the public LCSC and JLCPCB endpoints:
0603WAF4703T5E, UNI-ROYAL, 0603, **Basic**, listed stock 390,900 (LCSC) / 1,016,562 (JLCPCB).
Not reserved inventory. The other 18 codes were **not** re-checked for S5; their audit below is
from 2026-10-28 and covers 36 references.

The final strict-live audit checked all 36 assembled references / 18 unique codes for
**one board of placement demand** (not an order quantity), with public responses at
**2026-10-28T18:42:56Z..18:43:38Z**. Raw records and request hashes are in ignored
`research/5v-conversion/catalog-audit.json` and `catalog/`.

- All 18 exact codes resolved to their intended MPN/package and exposed
  **Economic eligibility**. Public stock exceeded this one-board demand at retrieval;
  this is not reserved inventory or authenticated service acceptance.
- R/C are observed **Basic except R12**, the retained ROHM ESR18EZPF1001 C2074262
  1206 1k 0.5 W output resistor, which is **Extended**. Its Basic-policy exception is
  still unresolved; the audit does not waive it.
- **U1 HT7550-1 C16106 is Preferred Extended, not Basic.** It is the same part used in
  our 8bit. Check the current portal's fees and options before ordering.
- U2 ATTINY1616-MNR C507118 is **Extended**; the other selected semiconductors are Basic
  in this observation. Recheck stock, classification, attrition/minimums and service
  options immediately before an order.

**The formal audit exits nonzero:** R12 fails the R/C Basic rule, per-part electrical /
land-pattern review requirements are not fully recorded, and supplier preview warnings
remain open. No placeholder attestations or rule waivers were added. The export is
complete, but **`order_ready` remains false**.

## Source identity

The shared check verifies these hashes against `source-sha256.json`:

- Carrier PCB: `52f17ccbf3eed8ac9d8f442d443a8e9ce4311f3786809310df5fede27cb3ea6b`
- Carrier project: `e6d7ff817ec3c7e4d4445ad57061dafb8d49e9cdf08a747443d04f12220dd735`
- Carrier schematic: `eb3fa31c7f3f6d209deac558c743ad29b7f79e2e7d762b6ab682ea261060289b`
- Panel PCB: `b4fe51e87cda4470639b13283c55074fc8afb5f667741ba2e21b7f9c18e0ad52`
- Panel project: `6d22f07fec3e78d77b7bd951908fa575494a745a4fc166cf66ae9bb95dc45946`

## Reproduce

From the repository root, after saving/refilling and checking authorized source edits:

```sh
python3 -B opt/kicad-tools/jlcpcb/export.py modules/env/hardware \
  --board env --schematic env.kicad_sch --side bottom --require-part-numbers \
  --manifest modules/env/jlcpcb/source-sha256.json --overwrite \
  -o modules/env/jlcpcb/carrier
unzip -o modules/env/jlcpcb/carrier/env-gerbers.zip -d modules/env/jlcpcb/carrier

python3 -B opt/kicad-tools/jlcpcb/export.py modules/env/panels/front-pcb \
  --board env-panel --pcb-only \
  --manifest modules/env/jlcpcb/source-sha256.json --overwrite \
  -o modules/env/jlcpcb/panel
unzip -o modules/env/jlcpcb/panel/env-panel-gerbers.zip -d modules/env/jlcpcb/panel

cp modules/env/jlcpcb/carrier/bom.csv modules/env/jlcpcb/carrier/positions.csv \
  modules/env/jlcpcb/assembly/
cp modules/env/jlcpcb/carrier/env-gerbers.zip modules/env/jlcpcb/panel/env-panel-gerbers.zip \
  modules/env/jlcpcb/

python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/env/tools/kicad-project.json --reports modules/env/research/check-NEW
```

Use fresh report directories. If layer selection changes, remove only stale unpacked
Gerber/drill members not present in the fresh ZIP. Panel-only shared `check` currently
requires a schematic; use full native `kicad-cli pcb drc` on a private copy with its
project rules instead (do not invent a panel schematic or weaken the common gate).

## Verification for S5 / R2 (2026-11-18)

Evidence: `research/r2-b1/`, `research/check-r2/` (ignored).

- Shared `check`: **ERC 0 / DRC 0 / unconnected 0 / schematic parity 0** (all severities, no
  exclusions), all five source hashes and the recorded exports equal the manifest.
- BOM / CPL against the S4 export: exactly one added line each (R20); 37 references, 19 rows.
- 222 tracks / 27 vias, none in or at an SMD pad (new via 1.03 mm from R20.1). R20.1 is 2.24 mm
  from RV2.3; closest SMD to pot / jack copper is still D3-J1.TN 2.10 mm; courtyards >= 1.02 mm
  from the edge. GND pours: same pieces as R1 on both layers.
- Both ZIPs pass the CRC test. Panel sources are unchanged; its Gerbers differ only in
  creation metadata. Printed panel `panels/front-cad/` regenerated (same STL).
- Not done for S5: the deterministic Gerber-command comparison, the whole-BOM live audit and any
  supplier preview. `order_ready` stays false.

## Verification for S4 (history, before R20)

Evidence: `research/5v-conversion/` (ignored).

- Full carrier native **ERC 0 / DRC 0 / unconnected 0 / schematic parity 0**;
  warnings/exclusions included, no ignored checks. Independent 147-pin circuit contract,
  eight NC pins, all native fields and generator values/nets agree.
- Before/after native connectivity differs only by the intentional +3V3 -> +5V rename
  on 11 supply pins; purchased values change only for U1 and R5-R8.
- Schematic render reviewed; native schematic save/reload retains the netlist. PCB
  geometry, model paths, source libraries except the +5V symbol, and project rules are
  preserved. Only the Power net-class pattern is renamed in the project.
- Fresh native saved refill is semantically identical (13 filled polygons); no vias in
  SMD pads or their mask openings. Copper-edge DRC uses 1.0 mm; closest measured
  courtyard bounding-box edge is 1.045 mm, closest SMD-to-pot/jack copper is 2.101 mm.
- Panel full native DRC: zero findings, no ignored checks. All panel/control centres
  still align; panel sources are byte-identical to S3.
- Both ZIPs pass CRC, have 11 expected members each, and match loose files exactly.
  All copper/mask/paste/silk/outline/drill fabrication commands equal the S3 baseline;
  only revision and creation-time metadata differ. This is a deterministic comparison,
  **not a supplier CAM-viewer signoff**.
- Carrier: 62 round PTH hits plus 16 routed slots, no NPTH. Panel: 15 NPTH holes, no PTH.
- BOM/CPL: 36 matching unique references, 18 correctly grouped rows, complete part
  numbers, bottom-only; positions/rotations match the native PCB and the prior CPL.
- Final shared check: all five source hashes and recorded exports match the manifest;
  all ZIP/CSV mirrors match. No design uploads, orders, commits or changes outside ENV.

## Remaining release gates

- Resolve the R12 Basic-parts exception and incomplete formal per-part review evidence.
- Supplier CAM/DFM review of both ZIPs and bottom-side placement preview: U2 QFN pin 1,
  U3 pin 1, U1 tab, diode cathodes, Q1/Q2 and every placement/rotation.
- Physical assembly/fit and prototype testing, including LDO startup/temperature,
  gate threshold/detect, MIDI/direct/thru behavior, LED current and DAC/output range.
- ENV firmware is in `firmware/` (runs on the first S4 board with the R20 bodge). It uses the
  4.34 V reference at 5 V, DAC codes **0..194**, and VDD for the knob ADC conversions. The
  ~0..5 V output is nominal, not a precision/clamped 5 V guarantee.
