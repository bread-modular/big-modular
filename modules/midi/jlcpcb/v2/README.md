# midi — manufacturing export (V2.0, S3/R3)

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change
the sources, then re-export with the commands below.

V2 is V1 plus mis-patch protection (`docs/research.md` §7). The panels are shared
with V1 and unchanged, so `midi-panel-gerbers.zip` matches `jlcpcb/v1/` apart from
the plot dates.

## Contents

| Path | Data |
|---|---|
| `midi-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `midi-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `midi-gerbers.zip` | 2 layers, FR4, 1.6 mm, 19.05 x 110.05 mm, 1 oz, HASL, standard everything else. No `JLCJLCJLCJLC` marker (as V1), so pick the order-number option deliberately |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 41 parts in 18 BOM rows, all on the back |
| Front panel PCB | `midi-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 20.05 x 128.55 mm (4HP), no assembly; black mask suits a panel |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J2-J9 | QingPu WQP-PJ301M-12 TS jack | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| J1 | QingPu WQP-PJ366ST TRS jack | Same as above (Bread Modular part) |
| D1-D8 | 3 mm red LED | Height is set by the panel (flush with the panel front; `docs/mechanics.md`) |
| J10 | 2x5 2.54 mm pin header, unshrouded | Eurorack power, back side; pin 1 (-12 V) at the bottom, silk `-12V` |
| J11 | 1x2 2.54 mm pin header | UPDI, back side |
| JP1 | 1x3 2.54 mm pin header + 1 shunt | TRS Type A/B, back side; shunt on `A` (1-2) for most gear |
| JP2 | 3-pad solder jumper (copper only) | **Shipped open; solder exactly one bridge.** `P` (1-2) = protected input, firmware sets `PORT_INVEN` on PB3. `D` (2-3) = V1-style direct path for debugging, firmware without `PORT_INVEN`. With no bridge, PB3 floats |

The exporter excluded these 21 refs (`carrier/export-report.json`): the 20 THT
parts, and JP2 as "Excluded from BOM".

Soldering notes (as V1):
- **GND pads have no thermal reliefs** (jack sleeves, LED cathodes, J10/J11 GND),
  so use a hot iron.
- **J10 and J11 sit in the U3 heat-sink copper on F.Cu,** which is cleared around
  their pins; their GND pins connect on the B.Cu GND pour.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `27ccaa1cd2b5702bdd8b1d6cab1d3d57e6ea9d15d0f04922671c636c022fd659`.
- Carrier project `d4fe2f305c6613a1c0186c7cef4a40a5ce36714e00cac635064ebd5999d4a5c2`.
- Carrier schematic `93e7eadb477a8649cbcdb2dc380337d70a9e271f24452db68410355044df40ae`.
- Panel PCB `c0e0cd7924a8ec1f52c5319f707667d83c51914fabf856feda238937fcdf3ff6`.
- Panel project `a44750bd6a13746dd643dac6b0c2ab6b0706ecf73fd3ac8787128754f8f6e44c`.

## Reproduce

From `modules/midi`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/v2/kicad-project.json --reports research/v2/native-NEW

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware/v2 \
  --board midi --schematic midi.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/v2/source-sha256.json --overwrite -o jlcpcb/v2/carrier
unzip -o jlcpcb/v2/carrier/midi-gerbers.zip -d jlcpcb/v2/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board midi-panel --pcb-only \
  --manifest jlcpcb/v2/source-sha256.json --overwrite -o jlcpcb/v2/panel
unzip -o jlcpcb/v2/panel/midi-panel-gerbers.zip -d jlcpcb/v2/panel

cp jlcpcb/v2/carrier/bom.csv jlcpcb/v2/carrier/positions.csv jlcpcb/v2/assembly/
cp jlcpcb/v2/carrier/midi-gerbers.zip jlcpcb/v2/panel/midi-panel-gerbers.zip jlcpcb/v2/
```

The exporter merges into an existing manifest and keeps rows it did not write, so
delete `jlcpcb/v2/source-sha256.json` first when a source path changes. Delete the
unpacked Gerbers first if layers change. The assembly audit (`docs/research.md`
§5, §7.6) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/midi-v2-symbols.xml hardware/v2/midi.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/midi/hardware/v2 --board midi.kicad_pcb --symbols-xml /tmp/midi-v2-symbols.xml \
  --cpl modules/midi/jlcpcb/v2/carrier/positions.csv \
  --requirements modules/midi/docs/v2/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

This export was regenerated on 2026-10-19 by the rebuild in
`docs/rebuild-status.md` (the original V2 tree was lost). The rebuilt sources
equal the recovered V2 S3/R3 evidence: netlist, fields, placement, and all 218
tracks, 57 vias and 4 zones.

- **Shared `check`:** `no_findings_in_requested_checks`. That covers:
  - ERC 0 and DRC 0 at all severities, with zones refilled;
  - 0 unconnected and schematic parity 0;
  - ref/pin/net parity equal;
  - the manifest equal.
- **Exporter:** 41 components in 18 BOM rows, bottom side, no missing part
  numbers. This equals the recovered pre-loss V2 export report.
- **Drill files:** 88 round PTH hits plus 27 routed slots (the 3 jack lugs × 9
  jacks) = 115. That matches 57 vias + 58 THT pads. There are no NPTH holes on the
  carrier.
- **3D fit:** 0 mm³ interference against both panels
  (`docs/v2/fit/fit-report.json`, identical to V1's).
- **Assembly audit:** last run live before the loss (2026-10-19 ~05:10 UTC for
  S3/R3, `docs/research.md` §7.6). Every C-code, MPN, Economy flag and stock level
  passed, and every resistor passed its stress check (including the 0805s). The
  only hard fail was R20's intentional Extended class. It was **not rerun** on this
  regenerated export. The parts and fields are the same, but run it again before
  ordering (gate 2 below).

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. The V1 order gates
in `jlcpcb/v1/README.md` (bottom-side Economic assembly, placement preview, live
recheck, your review attestations, DFM check, bench) all apply. In addition:

1. **Placement preview of the V2 parts:** Q1 and U2 (SOT-23), D11-D18 (SOT-323,
   COM to the GPIO side), D9 (cathode bar to Q1_B), and the 0805 output
   resistors.
2. **Live audit** with the command above (`--strict-live`), because the last run
   was before the regeneration.
3. **Bench** (`docs/research.md` §7.7): a ±12 V mis-patch soak on MIDI IN and on
   every output, U2 stability while clamping, and 3.3 V/5 V senders with V2
   firmware (`PORT_INVEN`) and JP2 1-2. Also try the JP2 2-3 direct path once.
