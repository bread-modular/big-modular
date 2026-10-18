# updi-programmer — manufacturing export

Generated from `hardware/updi-programmer.kicad_{pcb,sch}` with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files;
regenerate them.

## Contents

| Path | Data |
|---|---|
| `board/updi-programmer-gerbers.zip` | 2-layer Gerbers + PTH/NPTH drills (upload this) |
| `board/*.gbr`, `board/*.drl` | the same ZIP unpacked, for viewing |
| `board/bom.csv` | JLCPCB BOM, 12 rows, every row has an LCSC code |
| `board/positions.csv` | JLCPCB CPL, 18 parts, all top side |
| `board/export-report.json` | exporter report (layers, exclusions, warnings) |
| `source-sha256.json` | PCB/PRO/SCH inputs and ZIP/BOM/CPL SHA-256 |

## Upload map

| Order | Files | Notes |
|---|---|---|
| PCB | `board/updi-programmer-gerbers.zip` | JLC standard 2-layer FR4, 1.6 mm, 42 × 18 mm, any colour, HASL, tented vias; the USB-C shell overhangs the left edge by 1.2 mm (normal for edge connectors) |
| Assembly | `board/bom.csv`, `board/positions.csv` | Economic PCBA, top side only |

J1 (1x05 2.54 mm male header) is **not** JLC assembled: it is the user's own
header, hand-soldered after delivery. The PCB footprint is excluded from
position files, so J1 is absent from both `bom.csv` and `positions.csv`
(`export-report.json` records the reason).

The assembled ATtiny1616 is blank. Flash `firmware/jtag2updi_t1616.hex`
through J1.5 SELF / J1.4 GND with a second UPDI programmer
(see `../firmware/readme.txt`).

## Parts

| Refs | LCSC | MPN | JLC class |
|---|---|---|---|
| C1, C3, C5 | C1525 | CL05B104KO5NNNC 100nF 16V X7R 0402 | Basic |
| C2 | C1710 | CL21B103KBANNNC 10nF 50V X7R 0805 | Basic |
| C4 | C12891 | CL31A226KAHNNNE 22uF 25V X5R 1206 | Basic |
| D1 | C2286 | KT-0603R red (power) | Basic |
| D2 | C2290 | KT-0603W white (UPDI activity) | Basic |
| R1, R2, R6, R7 | C21190 | 0603WAF1001T5E 1k | Basic |
| R3, R4 | C23186 | 0603WAF5101T5E 5.1k | Basic |
| R5 | C23162 | 0603WAF4701T5E 4.7k | Basic |
| R8 | C25741 | 0402WGF1003TCE 100k | Basic |
| J2 | C165948 | HRO TYPE-C-31-M-12 | Extended |
| U1 | C2977777 | WCH CH340N | Extended |
| U2 | C507118 | Microchip ATTINY1616-MNR | Extended |

The three Extended parts (USB-C, CH340N, ATtiny1616) have no Basic equivalent
and carry JLC's Extended feeder fee.

## Reproduce

From `opt/updi-programmer`:

```sh
python3 -B tools/build_schematic.py
python3 -B tools/build_pcb.py
python3 -B ../kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../kicad-tools/jlcpcb/export.py hardware \
  --board updi-programmer --schematic updi-programmer.kicad_sch \
  --include-through-hole --side top --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/board
unzip -o jlcpcb/board/updi-programmer-gerbers.zip -d jlcpcb/board

kicad-cli sch export netlist --format kicadxml -o research/symbols.xml \
  hardware/updi-programmer.kicad_sch
python3 -B ../kicad-tools/jlcpcb/assembly.py audit \
  --project-dir hardware --board updi-programmer --symbols-xml research/symbols.xml \
  --cpl jlcpcb/board/positions.csv --export-report jlcpcb/board/export-report.json \
  --requirements tools/jlcpcb-requirements.json --boards 10 --side top --strict-live
```

`--include-through-hole` is needed because the HRO USB-C footprint is typed
through-hole (SMD contacts plus plated shell pegs). `build_pcb.py` regenerates
track UUIDs, so rebuilding the PCB always requires a fresh export; the shared
`check` fails when the sources drift from `source-sha256.json`.

## Status

Native ERC 0, DRC 0 (warnings included), 0 unconnected, 0 schematic parity,
source manifest equal. This is a complete export, not a supplier-accepted
release.

Live strict audit at 2026-10-18T16:44:16Z for 10 boards: every code and MPN
matched, all parts were Economy-eligible and in stock (lowest was U2 at 5,626 pcs).
Open items in that audit:

- **Human reviews not attested:** land pattern, pin mapping and ratings for
  every part, plus role for capacitors. Capacitor ESR/ESL and DC-bias data are
  unknown. Supplier package strings for D1/D2/J2/U1/U2 need a footprint review.
- **Standard exporter warning:** check parts, centroids, rotations, pin 1 and
  LED polarity (KiCad pad 1 = cathode) in JLCPCB's placement preview.

Before ordering, recheck stock and attrition at the actual quantity and do
JLCPCB DFM.
