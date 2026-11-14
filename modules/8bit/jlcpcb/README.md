# 8bit — manufacturing export (S6/R1, 6HP)

Generated on 2026-11-14 from the S6 schematic and the R1 hand-routed 2-layer 6HP carrier
with the shared `opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. It replaces
the S5/R4 4HP export. The carrier was re-exported the same day after the **U4 MCP6001 ->
MCP6002 swap** (MCP6002T-I/SN C7377, SOIC-8, Preferred Extended: no feeder fee; U4 moved
below the CV cluster with C15 beside its pin 8, local re-route only); the panels are unchanged. Never hand-edit these files: change the sources, then re-export with
the commands below.

## Contents

| Path | Data |
|---|---|
| `8bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `8bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `8bit-lfo-panel-gerbers.zip` | Optional LFO front panel ZIP (for a `firmware/lfo` build: no MIDI jack or P3 hole) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (F / B copper, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/`, `lfo-panel/` | Panel exports: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/`, `panel/` and `lfo-panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `8bit-gerbers.zip` | **2 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz copper, HASL, **tented vias**, no via-in-pad / POFV / resin fill (no vias in SMD pads). Every via is 0.3 / 0.6 mm; tracks >= 0.2 mm, clearance >= 0.2 mm. Leave the other options at JLCPCB's defaults. No `JLCJLCJLCJLC` marker, so pick the order-number option deliberately. The 110 mm length is over JLCPCB's 102 x 102 mm special price (as every 110 mm carrier) |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 38 parts in 24 BOM rows, all on the back |
| Front panel PCB | `8bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly; black mask suits a panel |
| LFO front panel PCB (optional) | `8bit-lfo-panel-gerbers.zip` | Same options. Only for a unit built as the LFO (`../docs/mechanics.md`, `../firmware/README.md`): J1 and RV3 are then not fitted |
| Button cap | `../panels/button-actuator/8bit-button-cap.stl` | 3D print (one part, socket down); not a JLCPCB PCB order |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1, J2, J3, J6 | QingPu WQP-PJ301M-12 TS jack (MIDI, CV, OUT, GATE) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV3 | RV09 50k linear pot (no bushing) | Front-side THT, user stock. No lead sits under the power cable socket: the 16-pin IDC envelope starts 3.0 mm below RV2's pins and ends 1.0 mm above the LED pads (`../docs/geometry.json` `power_header`) |
| D1 | 3 mm red LED | Height is set by the panel (`../docs/mechanics.md`). Its pads are 1.1 mm from D5 on the back: solder it with a fine tip |
| SW1 | 6 x 6 mm THT tact switch, 7 mm tall, 4 pins (user-bought) | Front-side THT. Solder it, then press the cap on before fitting the panel |
| J4 | 2x5 2.54 mm pin header | Eurorack power, back side, upright at the right edge; pin 1 (-12 V) at the bottom, marked `-12V` |
| J5 | 1x2 2.54 mm pin header | UPDI (UPDI, GND), back side, labelled |
| JP1 | 3-pad solder jumper (copper only) | **Shipped open; solder exactly one bridge** (`../docs/jumpers.md`). `P` = protected input, firmware sets `PORT_INVEN` on PB3. `D` = direct, stock Bread Modular firmware |

The exporter excluded exactly these 12 refs (`carrier/export-report.json`): the 11 THT
parts and JP1 as "Excluded from BOM".

## Parts

Codes and fields come from the schematic `SOURCING` table. Live strict lookup at export
(2026-11-14T05:16Z, 5 boards, recorded in `../docs/sourcing-candidates.json`): all 24 codes
and MPNs resolved, every part Economy-eligible.

- **Basic:** every 0603/0805 resistor and capacitor, D2 1N4148W, D4/D5 B5819W, Q1 MMBT3904.
- **Extended:** R12/R15 ROHM ESR18EZPF1001 (C2074262, 1k 0.5 W 1206; stock 99,546),
  U1 ATTINY1616-MNR (C507118; 10,257), U3 TL074CDR (C12594; 178,280), D3 BAT54SWT1G
  (C78260; 168,070).
- **Preferred Extended:** U2 HT7550-1 (C16106; 174,784), U4 MCP6002T-I/SN (C7377; 67,081 at
  2026-11-14T15:36Z, re-audit after the swap).

Four Extended part types carry JLCPCB's Extended fees. Public stock is a dated web
observation, not a reservation.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift (`tools/kicad-project.json` declares the manifest).

- Carrier PCB `2d18b0d530dfc7df589f3870692ce6b6b5dea8a4289b1b8e0743889aaab2a38e`.
- Carrier project `e6c8f00aab1f27e00951e295485cea149fa1a2bec87ea6447c4eacc68dd0bc66`.
- Carrier schematic `d01a32f24e521deee881c5070b00a72b7afe7707868a1d0c0313bf5ff4406066`.
- Panel PCB `fc3e85703d6fce821f798b49f19d1fde2297d712b3a6ae9635830c9d434a9eeb`.
- Panel project `e74649aa9ca6dd3fc3a813425112727c7141c578b934e17e081945270d071dc6`.
- LFO panel PCB `c161d7f45de0a4f2fb67a47211c93fbf7063337b5605373dcf9d92aceb47bc40`.
- LFO panel project `ca498367eec266399cf548d9ffa68c0071ffdc51700b3dc4130184ef6adc4e57`.

## Reproduce

From `modules/8bit`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native-NEW

rm -f jlcpcb/carrier/*.gbr jlcpcb/carrier/*.drl jlcpcb/panel/*.gbr jlcpcb/panel/*.drl \
  jlcpcb/lfo-panel/*.gbr jlcpcb/lfo-panel/*.drl

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 8bit --schematic 8bit.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/8bit-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 8bit-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/8bit-panel-gerbers.zip -d jlcpcb/panel

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 8bit-lfo-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/lfo-panel
unzip -o jlcpcb/lfo-panel/8bit-lfo-panel-gerbers.zip -d jlcpcb/lfo-panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/8bit-gerbers.zip jlcpcb/panel/8bit-panel-gerbers.zip \
  jlcpcb/lfo-panel/8bit-lfo-panel-gerbers.zip jlcpcb/
```

The exporter merges into an existing manifest and keeps rows it did not write, so
delete `jlcpcb/source-sha256.json` first when a source path changes. Never run
`tools/build_layout.py` over the routed carrier (it refuses); `build_layout.py panels`
rebuilds only the panels. The assembly audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/8bit-symbols.xml hardware/8bit.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/8bit/hardware --board 8bit.kicad_pcb --symbols-xml /tmp/8bit-symbols.xml \
  --cpl modules/8bit/jlcpcb/carrier/positions.csv \
  --export-report modules/8bit/jlcpcb/carrier/export-report.json \
  --requirements modules/8bit/docs/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export (2026-11-14, S6/R1)

- **Shared `check`:** `no_findings_in_requested_checks`, with the manifest present and
  equal (7 sources). That covers ERC 0 and DRC 0 at all severities with zones refilled,
  0 unconnected, schematic parity 0 and ref/pin/net parity equal; no exclusions, no
  ignored rules.
- **Saved fills:** native DRC without a refill is also 0 / 0 / 0 for the carrier and both
  panels, so the Gerbers carry the checked pours (F GND one piece; B GND one piece plus
  two GND-pad-tied fragments under U1).
- **Fab review of the board** (no change needed): supply and ground pins of U1-U4, D2-D5
  and Q1 checked against the datasheet pinouts; J4 pins 1/2 = -12 V at the bottom with the
  `-12V` silk; D1 cathode to GND; decoupling 1.7-2.0 mm from the U3 / U1 supply pins (U4 SOIC-8 after the swap: C15
  2.25 mm from pin 8, its GND via 0.25 mm from the U4.5 pad),
  C4 / C3 2.5 mm from U2. 32 vias, all 0.3 / 0.6 mm, tented, none in an SMD pad (closest
  0.20 mm). Tracks 0.2 (U1 fan-out) / 0.25 signal / 0.4 power. Copper >= 1.0 mm and
  courtyards >= 1.015 mm from the edge. Every SMD pad >= 2.245 mm from the pot and jack
  pads; SW1 pads 3.15 mm from the nearest SMD pad. The LED D1 pads are 1.10 mm from D5
  (judged fine for a 3 mm LED lead; outside the pot/jack rule). B silk text 0.8 mm / 0.15 mm.
- **Exporter:** 38 components in 24 BOM rows, bottom side, no missing part numbers.
  Each ZIP member is byte-identical to its unpacked copy.
- **Drill files:** carrier PTH = 59 round hits (32 vias 0.3; 2 x 0.9 LED; 21 x 1.0 = 12
  header + 9 pot pins; 4 x 1.1 SW1) plus 18 routed slots (12 jack lugs 0.6, 6 pot lugs
  1.1), matching the board. No NPTH on the carrier. The panel has 11 NPTH holes, the LFO
  panel 9, and neither has PTH.
- **Outlines:** carrier 29.0 x 110.0 mm, both panels 30.0 x 128.5 mm (Edge.Cuts Gerbers).
  Panel holes match the carrier's jack, pot, switch and LED positions.
- **Live assembly audit** (`--strict-live`, 2026-11-14T05:16Z, 5 boards, S6/R1):
  - Every C-code and MPN resolved and every part is Economy-eligible, with stock far
    above the 5-board demand (lowest: U1 ATtiny1616, 10,257). Classes are in "Parts".
  - Re-run after the MCP6002 swap (2026-11-14T15:36Z, same command): U4 C7377 resolves as
    Preferred Extended (67,081); the failure set is unchanged (R12 / R15 Basic policy,
    exporter warning, open human reviews); U1 stock then 10,187.
  - All resistor stress checks pass, including the R12 / R15 mis-patch cases (0.28 W /
    0.29 W on a 0.5 W rating). Their one hard fail is the shared R/C Basic policy (gate 1).
  - Still `unknown` by design: the human land-pattern/pin-mapping/ratings/role reviews in
    `docs/jlcpcb-audit-requirements.json` (empty, never auto-filled), capacitor
    DC-bias/ESR/ESL data, and the package match for the non-passives. The audit also
    keeps the exporter's "review in JLCPCB's preview" warning open. So it reports
    `order_ready: false`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Nothing is built or
bench-tested.

1. **R12 / R15 Extended class (hard audit fail, intentional).** They are ROHM
   ESR18EZPF1001 (C2074262), 0.5 W 1206, so a permanent ±12 V source on OUT or GATE
   (16.8 V / 0.28 W, 17.0 V / 0.29 W) is within rating. The shared audit requires Basic
   for R/C, and no Basic 0.5 W 1k 1206 exists, so this stays a known fail (as MIDI V2's
   R20 and `modules/12bit`). Accept the Extended fee knowingly.
2. **Your reviews:** land pattern, pin mapping and ratings for each assembled part (and
   role for the capacitors), recorded in the requirements file.
3. **JLCPCB placement preview** of every back-side part: U1 pin 1 and the exposed pad,
   U3 / U4 (SOIC-8) pin 1 (mirrored on the back), U2, D3 and Q1 (SOT-89 / SOT-323 / SOT-23
   orientation), and D2 / D4 / D5 cathode bars. The CPL carries the exporter's raw KiCad
   rotations, as every module here.
4. **Live recheck** of stock, attrition and minimums just before ordering, plus JLCPCB's
   DFM check in their Gerber viewer.
5. **Not yet done:** 3D-printed panel and button-cap test print, measuring a real RV09 pot
   against the 3D model, firmware use of P3 (PB5), and bench testing (output and gate
   level, CV range and zero, MIDI on both JP1 settings).
