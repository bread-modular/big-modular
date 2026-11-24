# MOTION — manufacturing export (S1/R1, 6HP)

Generated on 2026-11-15 from the S1 schematic and the R1 hand-routed 2-layer carrier with
the shared `opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit
these files: change the sources, then re-export with the commands below. Not
supplier-accepted, not built; there is no firmware yet.

## Contents

| Path | Data |
|---|---|
| `motion-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `motion-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (F / B copper, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `motion-gerbers.zip` | **2 layers**, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz copper, HASL, **tented vias**, no via-in-pad / POFV / resin fill. Every via is 0.3 / 0.6 mm; tracks >= 0.2 mm, clearance >= 0.2 mm. Leave the other options at JLCPCB's defaults. No `JLCJLCJLCJLC` marker, so pick the order-number option deliberately. The 110 mm length is over JLCPCB's 102 x 102 mm special price (as every 110 mm carrier) |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 52 parts in 15 BOM rows, all on the back |
| Front panel PCB | `motion-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly; black mask suits a panel. **P2** (re-exported 2026-11-24): 19 NPTH incl. the Ø3.2 top-clip screw hole at X25 / Y12; smallest tool 3.2 mm, no PTH |

One via sits in the ATtiny1616 exposed ground pad (U2, centre). It is that pad's ground
via, the one exception to the no-via-in-SMD-pad rule, and needs no POFV: it is 0.3 mm,
open on the pad side and tented on the front.

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J4 | QingPu WQP-PJ301M-12 TS jack (OUT 1-4) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1-RV4 | RV09 50k linear pot (no bushing) | Front-side THT, user stock |
| D1-D4, D5, D6 | 3 mm LED (motion 1-4, REC, RANGE) | Height is set by the panel. D6's pads are 1.04 mm from R10 on the back: use a fine tip |
| SW1, SW2 | 6 x 6 mm THT tact switch, 7 mm tall, 4 pins | Front-side THT. Solder, then press the printed cap on before fitting the panel |
| J5 | 2x5 2.54 mm pin header | Eurorack power, back side between OUT 3 and OUT 4; pin 1 (-12 V) at the bottom, marked `-12V`. **Solder it before the jacks** |
| J6 | 1x2 2.54 mm pin header | UPDI (UPDI, GND), back side, labelled |

The exporter excluded exactly these 18 refs (`carrier/export-report.json`).

## Parts

Codes and fields come from the schematic. Live strict lookup of every BOM code at export
(2026-11-15T14:49Z, 5 boards, recorded in `../docs/sourcing-candidates.json`
`bom_live_lookup`): all 15 codes and MPNs resolved, every part Economy-eligible.

- **Basic (9 rows):** every 0603 / 0805 resistor and capacitor except the 1k outputs,
  D7 / D8 B5819W.
- **Extended (5 rows):** R14 / R18 / R22 / R26 ROHM ESR18EZPF1001 (C2074262, 1k 0.5 W
  1206; stock 99,501), U2 ATTINY1616-MNR (C507118; 10,045), U3 MCP4728T-E/UN (C478093;
  15,946), U4 MB85RC256V (C45273903; 16,911), U5 TL074CDR (C12594; 177,450).
- **Preferred Extended:** U1 HT7550-1 (C16106; 175,510).

Five Extended part types carry JLCPCB's Extended fees. Public stock is a dated web
observation, not a reservation.

**Not done:** the shared `assembly.py audit` reports failures for this module because no
`docs/jlcpcb-audit-requirements.json` (per-part circuit requirements, manual-part policy,
review attestations) has been written. Only the catalog facts above come from it.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on drift
(`tools/kicad-project.json` declares the manifest).

## Reproduce

From `modules/motion`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native-NEW

rm -f jlcpcb/carrier/*.gbr jlcpcb/carrier/*.drl jlcpcb/panel/*.gbr jlcpcb/panel/*.drl

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board motion --schematic motion.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/motion-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board motion-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/motion-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/motion-gerbers.zip jlcpcb/panel/motion-panel-gerbers.zip jlcpcb/
```

The exporter merges into an existing manifest and keeps rows it did not write, so delete
`jlcpcb/source-sha256.json` first when a source path changes. Never run
`tools/build_layout.py` over the routed carrier (it refuses); `build_layout.py panels`
rebuilds only the panel.

## Checks done for this export (2026-11-15, S1/R1)

- **Shared `check`:** `no_findings_in_requested_checks`, manifest present and equal
  (5 sources): ERC 0, DRC 0 at all severities with zones refilled, 0 unconnected,
  schematic parity 0, ref/pin/net parity equal; no exclusions, no ignored rules.
- **Saved fills:** native DRC without a refill is also 0 / 0 / 0 for the carrier.
- **Independent ground check** (`research/r1/gndnet.py`, pours + pads + vias): one GND
  net. The pours are in pieces (F 22, B 20), because the long knob / LED / output runs
  cross both layers; 37 stitching vias tie every piece.
- **Measured:** 402 tracks / 89 vias, all 0.3 / 0.6 mm, none in an SMD pad except the U2
  exposed-pad ground via. Tracks 0.2 (MCU fan-out, I2C) / 0.25 signal / 0.3-0.4 power.
  Track and via copper >= 1.1 mm and courtyards >= 1.015 mm from the edge. SMD pads
  >= 2.025 mm from pot and jack pads (C6 to RV2); LED / switch / header pads >= 1.04 mm.
  Decoupling 0.6-1.2 mm from its supply pin (C8 at U2, C9 at U4, C7 at U3, C18 / C19 at
  U5, C3 / C4 at U1).
- **Not checked here:** JLCPCB's own DFM / part-placement preview, a Gerber viewer pass,
  the requirements audit, bench behaviour. The route is from a one-connection-at-a-time
  path helper, each batch DRC-checked and inspected in a render; it has not been
  reviewed by a second person.
