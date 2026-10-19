# midi — manufacturing export (V1.0, S4/R5)

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change
the sources, then re-export with the commands below.

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
| Carrier PCB | `midi-gerbers.zip` | 2 layers, FR4, 1.6 mm, 19.05 x 110.05 mm, 1 oz, HASL, standard everything else. The board has no `JLCJLCJLCJLC` marker (removed in R5), so pick the order-number option deliberately: "Remove" (check the quote for any fee), or JLCPCB prints the number where it chooses |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 25 parts in 9 BOM rows, all on the back |
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

The exporter excluded exactly these 20 refs, as THT (`carrier/export-report.json`).
The shared native audit lists them as manual too.

Soldering notes:
- **GND pads have no thermal reliefs** (jack sleeves, LED cathodes, J10/J11 GND),
  so use a hot iron.
- **J10 and J11 sit in the U3 heat-sink copper on F.Cu,** which is cleared
  around their pins; their GND pins connect on the B.Cu GND pour. U3, R20, C4, C5
  and D10 (JLC-assembled) sit beside J10 on the B.Cu heat sink.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `e99ec404ce789c56e8e17eaccda157199d27e6832ceb1ecb04f0d729133809e2`.
- Carrier project `d4fe2f305c6613a1c0186c7cef4a40a5ce36714e00cac635064ebd5999d4a5c2`.
- Carrier schematic `245db40d54a29ca96c01690b1b47e70fced984da89ce177e9470e3bbf4751144`.
- Panel PCB `c0e0cd7924a8ec1f52c5319f707667d83c51914fabf856feda238937fcdf3ff6`.
- Panel project `a44750bd6a13746dd643dac6b0c2ab6b0706ecf73fd3ac8787128754f8f6e44c`.

## Reproduce

From `modules/midi`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board midi --schematic midi.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/midi-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board midi-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/midi-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/midi-gerbers.zip jlcpcb/panel/midi-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change, so no stale plots remain
beside a new ZIP. The assembly audit (`docs/research.md` §5) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/midi-symbols.xml hardware/midi.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/midi/hardware --board midi.kicad_pcb --symbols-xml /tmp/midi-symbols.xml \
  --cpl modules/midi/jlcpcb/carrier/positions.csv \
  --requirements modules/midi/docs/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

- **Shared `check`:** `no_findings_in_requested_checks`. That covers:
  - ERC 0 and DRC 0 at all severities, with zones refilled;
  - 0 unconnected and schematic parity 0;
  - ref/pin/net parity equal;
  - the manifest equal.
- **Panel DRC:** 0.
- **Drill files:** 78 round PTH hits plus 27 routed slots (the 3 jack lugs × 9
  jacks) = 105. That matches 47 vias + 58 THT pads. There are no NPTH holes on the
  carrier.
- **Gerber ZIP:** has both copper layers with their pours (GND and the VIN_LDO
  heat sink), both masks, silkscreens and pastes, the edge, and PTH/NPTH drills.
  F.Paste is empty because there are no front SMD parts.
- **3D fit:** 0 mm³ interference against both panels (`docs/fit/fit-report.json`).
- **Assembly audit** (live, 5 boards):
  - Every C-code, MPN, Economy flag and stock level passes.
  - R/C parts are Basic except R20, which is Extended by choice.
  - R20 passes its stress check.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly.**
   - JLCPCB's capabilities page (read 2026-10-19) says Economic is "Single sided
     placement" but doesn't say which side.
   - Confirm that the quote form offers **Bottom** for Economic. If it doesn't,
     Standard PCBA is needed, and its stated 70 x 70 mm minimum board size means
     JLCPCB would also have to panelise this 19 mm board.
   - In the same quote, check whether the 19 mm width needs edge rails (courtyards
     sit ~0.2 mm from the edge) and whether that keeps Economic eligibility.
2. **Placement preview.** Check these parts in JLCPCB's bottom-side preview:
   - U1: the pin 1 dot. It's a 0.4 mm-pitch QFN, exactly at the Economic limit.
   - U3: the three pins point down (toward the board's bottom edge) and the
     tab points up, toward D10 (`docs/mechanics.md`).
   - D10: the cathode bar is on pad 1, the VIN_D net that runs up to R20. The
     anode is pad 2, on the +12 V track from J10.
   - Every rotation: bottom-side CPL rotations are the usual place for errors.
3. **Live recheck before ordering:** stock, Basic/Extended class, minimum assembly
   quantities and attrition. The stock figures in `docs/research.md` §5 are a
   snapshot, not a reservation.
4. **Your review attestations** in the audit (land pattern, pin mapping, ratings,
   capacitor role). These are left open rather than filled with boilerplate.
   Archive the U1/U3/D10 datasheet PDFs with SHA-256 first and cite their pages;
   the HT7550-1 catalog URL no longer serves a PDF (`docs/research.md` §6).
5. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
6. **Bench:**
   - U3 fault test (`docs/research.md` §3.1, D2): 12.6 V, all outputs shorted,
     all LEDs lit, 30 min, thermocouple on U3's tab; +5 V must stay below 5.5 V.
     Needs firmware with a drive-everything test mode (none is in the repo yet);
   - LED brightness (D5);
   - seat two brands of 16-pin IDC socket on J10 (one-sided key bump over U3/C4);
   - the real jack panel height and hole fit.
