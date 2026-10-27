# 8bit — manufacturing export (S5/R4)

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change
the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `8bit-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `8bit-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `8bit-gerbers.zip` | 2 layers, FR4, 1.6 mm, 19.0 x 110.0 mm, 1 oz, HASL, standard everything else. No `JLCJLCJLCJLC` marker, so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 37 parts in 24 BOM rows, all on the back |
| Front panel PCB | `8bit-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 20.0 x 128.5 mm (4HP), no assembly; black mask suits a panel |
| Button cap | `../panels/button-actuator/8bit-button-cap.stl` | 3D print (one part, socket down); not a JLCPCB PCB order |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J3 | QingPu WQP-PJ301M-12 TS jack | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| RV1, RV2 / RV3 | RV09 pot, 50k / 1M (no bushing) | Front-side THT, user stock |
| D1 | 3 mm red LED | Height is set by the panel (`docs/mechanics.md`) |
| SW1 | 6 x 6 mm THT tact switch, 7 mm tall, 4 pins (user-bought) | Front-side THT. Solder it, then press the cap on before fitting the panel |
| J4 | 2x5 2.54 mm pin header | Eurorack power, back side; pin 1 (-12 V) marked `-12V` |
| J5 | 1x2 2.54 mm pin header | UPDI, back side |
| JP1 | 3-pad solder jumper (copper only) | **Shipped open; solder exactly one bridge** (`docs/jumpers.md`). `P` = protected input, firmware sets `PORT_INVEN` on PB3. `D` = direct, stock Bread Modular firmware |

The exporter excluded these 11 refs (`carrier/export-report.json`): the 10 THT
parts (including SW1) and JP1 as "Excluded from BOM".

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift (`tools/kicad-project.json` declares the manifest).

- Carrier PCB `c8f6993b8ef236e1c781ab7e2af8957816d3f5c7ed0471fd7007fd391eecb92b`.
- Carrier project `b4337e9349fdb9270bee7f9cfc48e3ac45cecf26ea330f6865b30e4eb8c867ae`.
- Carrier schematic `35d01fae7afce0db8058bebd11fa1eef0154198896dce0b386b83a7e24bb984f`.
- Panel PCB `f011721f73e7da6a7895a1b6e3885d3e43a4c55f6c3d3c17b92d19362073179c`.
- Panel project `e74649aa9ca6dd3fc3a813425112727c7141c578b934e17e081945270d071dc6`.

## Reproduce

From `modules/8bit`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native-NEW

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board 8bit --schematic 8bit.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/8bit-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board 8bit-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/8bit-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/8bit-gerbers.zip jlcpcb/panel/8bit-panel-gerbers.zip jlcpcb/
```

The exporter merges into an existing manifest and keeps rows it did not write, so
delete `jlcpcb/source-sha256.json` first when a source path changes. Delete the
unpacked Gerbers first if layers change. The assembly audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/8bit-symbols.xml hardware/8bit.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/8bit/hardware --board 8bit.kicad_pcb --symbols-xml /tmp/8bit-symbols.xml \
  --cpl modules/8bit/jlcpcb/carrier/positions.csv \
  --requirements modules/8bit/docs/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live --max-requests 64)
```

## Checks done for this export (2026-10-20, S5/R4)

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- **Shared `check`:** `no_findings_in_requested_checks`, with the manifest
  present and equal. That covers ERC 0 and DRC 0 at all severities with zones
  refilled, 0 unconnected, schematic parity 0 and ref/pin/net parity equal.
- **Exporter:** 37 components in 24 BOM rows, bottom side, no missing part
  numbers.
- **Drill files:** 67 round PTH hits (40 vias + 27 round THT pads) plus 15 routed
  slots (jack and pot lugs), matching the board. No NPTH holes on the carrier.
  The panel has 10 NPTH holes and no PTH.
- **Outlines:** carrier 19.0 x 110.0 mm, panel 20.0 x 128.5 mm (Edge.Cuts Gerbers).
- **Live assembly audit** (`--strict-live`, 2026-10-20T02:38:52Z, 5 boards, S5/R4):
  - Every C-code and MPN resolved and every part is Economy-eligible, with stock
    far above the 5-board demand (lowest: U1 ATtiny1616, 7,581).
  - Basic: all R/C except R12, D2, D4, D5, Q1, U3 (TL072CDT). Extended: R12
    (ESR18EZPF1001), U1 (ATtiny1616), D3 (BAT54SW), U4 (MCP6001); Preferred Extended: U2 (HT7550-1). These carry
    JLCPCB's Extended fees.
  - All resistor stress checks pass, including R12's 0.28 W fault case on its
    0.5 W rating. R12's one hard fail is the shared R/C Basic policy (gate 1).
  - Still `unknown` by design: the human land-pattern/pin-mapping/ratings/role
    reviews in `docs/jlcpcb-audit-requirements.json` (empty, never auto-filled),
    capacitor DC-bias/ESR/ESL data, and the package match for the non-passives.
    So the audit reports `order_ready: false`.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release.

1. **R12 Extended class (hard audit fail, intentional).** R12 is ROHM
   ESR18EZPF1001 (C2074262), a 0.5 W 1206, so a permanent -12 V source on OUT
   (16.8 V / 0.28 W) is within rating. The shared audit requires Basic for R/C,
   and no Basic 0.5 W 1k 1206 exists, so this stays a known fail (as MIDI V2's
   R20). Accept the Extended fee knowingly.
2. **Your reviews:** land pattern, pin mapping and ratings for each assembled
   part (and role for the capacitors), recorded in the requirements file.
3. **JLCPCB placement preview** of every back-side part: U1 pin 1 and the
   exposed pad, U3/U4 pin 1 (mirrored on the back), D3 and Q1 (SOT-323/SOT-23
   orientation), and D2/D4/D5 cathode bars.
4. **Live recheck** of stock, attrition and minimums just before ordering, plus
   JLCPCB's DFM check in their Gerber viewer.
5. **Not yet done:** 3D fit against the panel, a button-cap test print, measuring
   a real RV09 pot against the 3D model, and bench testing (output level, CV range
   and zero, MIDI on both JP1 settings).
