# mcc — manufacturing export (V1: S4/R4)

Generated on 2026-10-20 from the current S4/R4 sources (V1: R4 is a 0.5 W 1206,
back silk `MCC V1`) with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter, on user direction. Never hand-edit
these files: change the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `mcc-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `mcc-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `mcc-gerbers.zip` | 2 layers, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz, HASL, standard everything else. The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately: "Remove" (check the quote for any fee), or JLCPCB prints the number where it chooses |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 50 parts in 23 BOM rows, all on the back |
| Front panel PCB | `mcc-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly; black mask suits a panel |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1, J2 | QingPu WQP-PJ301M-12 jack (MIDI IN, MIDI OUT; TS) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| J11-J14 | QingPu WQP-PJ301M-12 jack (CV 1-4) | Front-side THT, panel-nut fixed |
| RV1-RV4 | RV09 50k linear (knobs 1-4) | Front-side THT, snap-in, no nut. Seat flat before soldering |
| SW1 | 6x6x7 mm THT tact switch (BANK) | Front-side THT |
| D4-D6 | 3 mm LED (bank A/B/C) | Front-side THT; set the height to the panel before soldering |
| J3 | 2x5 2.54 mm pin header | Eurorack power, back side; pin 1 (-12 V) next to the B silk `-12V` |
| J4 | 1x2 2.54 mm pin header | UPDI, back side; B silk `UPDI` (pin 1) and `GND` (pin 2) |
| JP1, JP2 | Solder jumpers (no part) | **Shipped open: bridge one side of each or MIDI does nothing.** `P` = protected (normal), `D` = direct (debug bypass) |

The exporter excluded exactly these refs (16 as THT, JP1/JP2 as excluded from BOM),
see `carrier/export-report.json`.

Soldering notes:
- Both GND pours connect to pads with thermal reliefs.
- **J3 has no key.** Plug the cable with the red stripe (-12 V) at the `-12V`
  silk.
- Program U1 through J4 with the module on Eurorack power (the UPDI programmer
  does not power the board).

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `68fa5b80d353423f6c3291b70dc06557a05c9e6712f1e769729a04d91fb602b5`.
- Carrier project `2a8604afe522f17e912630e01a05c314e0123be3ff37672a3f5f65f9ceb9031d`.
- Carrier schematic `3071429902812b74a6de5574a5ab26794f905b695be2f35be41cfc75f15703eb`.
- Panel PCB `ff255ba28c202edead43e7418eac53112d2715e334c515b6129c25ed599dbfc3`.
- Panel project `a8725155bfbaef36716bc4bc383541eef6aef42bfe2f956d0f0662d3ffa023cb`.

## Reproduce

From `modules/mcc`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board mcc --schematic mcc.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/mcc-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board mcc-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/mcc-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/mcc-gerbers.zip jlcpcb/panel/mcc-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change, so no stale plots remain
beside a new ZIP. The catalog audit (no requirements file yet) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/mcc-symbols.xml hardware/mcc.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/mcc/hardware --board mcc.kicad_pcb --symbols-xml /tmp/mcc-symbols.xml \
  --cpl modules/mcc/jlcpcb/carrier/positions.csv \
  --export-report modules/mcc/jlcpcb/carrier/export-report.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- **Shared `check`** (after the export): ERC 0, DRC 0, 0 unconnected, schematic
  parity 0, no exclusions, manifest equal (5 sources, all exports
  byte-identical). `order_ready` stays `false` (supplier gates below).
- **Carrier drill file:** 75 round PTH hits plus 26 routed slots = 101, matching
  41 vias + 60 THT pads. No NPTH holes.
- **Panel drill file:** 16 NPTH holes (6 jacks 6.2 mm, 4 pots 7.2 mm, button
  4.2 mm, 3 LEDs and 2 rail holes 3.2 mm). No copper holes.
- **Gerber ZIP:** both copper layers with their GND pours, both masks,
  silkscreens and pastes, the edge, and PTH/NPTH drills. F.Paste is empty
  because there are no front SMD parts.
- **BOM/CPL:** 50 parts, 23 rows, every row with LCSC, MPN and manufacturer;
  every CPL row is `bottom`.
- **Catalog audit** (live, 5 boards, 2026-10-20 15:42 UTC): every C-code
  resolves to its MPN and package. Basic: all R/C except R4, 1N4148W, B5819W,
  MMBT3904, CJ431. Extended: ATtiny1616-MNR C507118 (5,207 in stock),
  MCP6002T-I/SN C7377 (50,199), BAT54SWT1G C78260 (48,605), HT7550-1 C16106
  (205,472), and R4 ROHM ESR18EZPF1001 C2074262 (1k 1 % 500 mW 1206, 101,148; no
  Basic 0.5 W 1206 exists, same part as modules/8bit R12). The audit also flags R4
  with "R/C requires actual Basic", which is this deliberate choice. There is no
  `docs/jlcpcb-audit-requirements.json` yet, so the per-part requirement/review
  rows stay `unknown` and the audit fails on them and on the 18 excluded refs;
  that is expected, not a catalog failure.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly.** Confirm the quote form offers **Bottom**
   for Economic, with the five Extended parts (Extended parts add a loading fee each).
2. **Placement preview.** Check in JLCPCB's bottom-side preview:
   - U1 (VQFN-20) and U4/U5 (SOIC-8): the pin 1 dot;
   - D1/D3 (SOD-123): the cathode bands; D2, D11-D14 (SOT-323) and Q1/U3 (SOT-23) orientation;
   - every rotation: bottom-side CPL rotations are the usual place for errors.
3. **Live recheck before ordering:** stock, Basic/Extended class, minimum
   assembly quantities and attrition. The figures above are a snapshot.
4. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
5. **Bench:** MIDI in/out with the jumpers on `P`, CV range (±5 V), knob reads,
   and the real pot, jack, LED and button panel fit.
