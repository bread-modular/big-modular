# imix — manufacturing export (S3/R3, 6HP)

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change
the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `imix-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `imix-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `imix-gerbers.zip` | 2 layers, FR4, 1.6 mm, 29.0 x 110.0 mm, 1 oz, HASL, standard everything else. The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately: "Remove" (check the quote for any fee), or JLCPCB prints the number where it chooses |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 36 parts in 8 BOM rows, all on the back; all Basic except R18 (C54315, Extended: expect the Extended-part fee) |
| Front panel PCB | `imix-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 30.0 x 128.5 mm (6HP), no assembly; black mask suits a panel |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1-J4 | QingPu WQP-PJ301M-12 TS jack (IN 1-4) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| J5 | QingPu WQP-PJ301M-12 TS jack (MIX) | Same as above |
| RV1-RV4 | Thonk Tall Trimmer B50K (Song Huei R0904N, 25 mm shaft) | Not a JLCPCB part; front-side THT snap-in; fit to the panel before soldering |
| J10 | 2x5 2.54 mm pin header, unshrouded | Eurorack power, back side; pin 1 (-12 V) at the bottom, silk `-12V` |

The exporter excluded exactly these 10 refs, as THT (`carrier/export-report.json`);
the audit requirements list the same 10 as manual.

Soldering notes:
- **GND pads have no thermal reliefs** (jack sleeves, input-jack TN lugs, pot pin 1, J10 GND), so use a
  hot iron.
- Fit order: snap the pots and push the jacks into the board, put the panel on, nut
  the five jacks, then solder, so the shafts and bushings line up with the panel
  holes.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `4915aeb6b15b33167156240cfd300496ac529eba97153b70664cd3140c965f37` (R3, R18 1 W 2512).
- Carrier project `6b4cfec5c1272aace4c13a072669b0aaa79d76b38955a9fae91e453d621b5ba4`.
- Carrier schematic `429354893e38863ea2794794cf13491e17b8e9c6ff7fd2fbb364029b3f1e48c7` (S3, R18 C54315).
- Panel PCB `6d701f890885edde86a63548b755741adc3cc375954287992c864fdcccb7ec33`.
- Panel project `e7156bbbb5883643c9fab0d81e72337c84d60000f11303adfe4c4a63853bb2f1`.

## Reproduce

From `modules/imix`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board imix --schematic imix.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/imix-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board imix-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/imix-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/imix-gerbers.zip jlcpcb/panel/imix-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change, so no stale plots remain
beside a new ZIP. The assembly audit (`docs/research.md` §5) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/imix-symbols.xml hardware/imix.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/imix/hardware --board imix.kicad_pcb --symbols-xml /tmp/imix-symbols.xml \
  --cpl modules/imix/jlcpcb/carrier/positions.csv \
  --requirements modules/imix/docs/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

Panel re-exported on 2026-10-27 for the rail-hole move: rail holes H1/H2 went 1HP (5.08 mm) right, X 7.5 to X 12.58, as modules/midi, so they sit on the 2HP case hole grid (Y 3.0 / 125.5 kept; `docs/geometry.json`). Only `panel/`, the panel Gerber ZIP and the manifest changed; the carrier export is untouched. The panel NPTH drill now has the rail holes at X 12.58; panel DRC: no findings, 0 unconnected.

- **Shared `check`:** `no_findings_in_requested_checks`. That covers:
  - ERC 0 and DRC 0 at all severities, with zones refilled;
  - 0 unconnected and schematic parity 0;
  - ref/pin/net parity equal;
  - the manifest equal (5 sources, exports byte-identical).
- **Panel DRC:** 0.
- **Drill files:**
  - Carrier: 86 round PTH hits plus 23 routed slots (15 jack lugs and 8 pot
    bracket tabs) = 109. That matches 64 vias + 45 THT pads. There are no NPTH holes.
  - Panel: 11 NPTH holes (2 rail, 5 jack, 4 pot) and no PTH.
- **Gerber ZIP:** has both copper layers with their GND pours, both masks,
  silkscreens and pastes, the edge, and PTH/NPTH drills. F.Paste is empty because
  there are no front SMD parts.
- **3D fit:** 0 mm³ interference against both panels; the pot shafts stand 13.4 mm
  (FR4) / 13.0 mm (printed) proud (`docs/fit/fit-report.json`).
- **Assembly audit** (live, 5 boards, 2026-10-19T17:00:35Z):
  - Every C-code, MPN, Economy flag, stock level and
    voltage/power/dielectric requirement passes.
  - One intentional hard failure: R18 (UNI-ROYAL 25121WF1001T4E, 1 W 2512) is
    Extended and fails the shared "R/C requires actual Basic" rule. No Basic 1 W
    1k was found; the rule is not weakened (`docs/research.md` §5). R18's power
    check is sized for a -12 V source on MIX against +10.5 V (0.51 W, 51 %).
  - It also reports gates it treats as unknown:
    - the human review attestations;
    - the capacitor ESR/ESL/DC-bias limits;
    - the package review for D1, D2 and U1-U3.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Pot footprint (M1).** Seat a real Thonk Tall Trimmer in a 1:1 print of the
   copper (or a bare board). The Bread Modular RV09 tab spacing and pin offset
   differ slightly from Thonk's drawing (`docs/research.md` §4).
2. **Bottom-side Economic assembly.** Confirm that the quote form offers
   **Bottom** for Economic PCBA on this board. If it doesn't, Standard PCBA is
   needed; check its minimum-size/panelisation terms in the same quote.
3. **Placement preview.** Check these in JLCPCB's bottom-side preview:
   - U1, U2 and U3 pin 1;
   - D1/D2 polarity: the cathode bar is on pad 1. D1's cathode is on the +12 V
     side, by C1. D2's cathode is on the -12V_IN side, toward J10;
   - every rotation: bottom-side CPL rotations are the usual place for errors.
4. **Live recheck before ordering:** stock, Basic/Extended class, minimum assembly
   quantities and attrition. The audit's stock figures are a snapshot, not a
   reservation.
5. **Your review attestations** in the audit (land pattern, pin mapping, ratings,
   capacitor role). These are left open rather than filled with boilerplate.
6. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
7. **Bench** (`docs/research.md` §4 E1/E2): gain law, unity at full CW, clipping,
   crosstalk, noise, output offset; seat a 16-pin IDC socket on J10.
