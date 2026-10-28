# line-in — manufacturing export (S3/R2)

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change
the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `line-in-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `line-in-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `line-in-gerbers.zip` | 2 layers, FR4, 1.6 mm, 19.0 x 110.0 mm, 1 oz, HASL, standard everything else. The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately: "Remove" (check the quote for any fee), or JLCPCB prints the number where it chooses |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 36 parts in 13 BOM rows, all on the back |
| Front panel PCB | `line-in-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 20.0 x 128.5 mm (4HP), no assembly; black mask suits a panel |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1 | QingPu WQP-PJ366ST TRS jack (IN: tip L, ring R) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| J2, J3, J4 | QingPu WQP-PJ301M-12 TS jack (OUT L, OUT R, MONO) | Same as above |
| RV1, RV2 | RV09 vertical 50k pot (LEVEL L, LEVEL R) | Front-side THT; no nut, so the pots hang on their pins. Seat them flat before soldering |
| J10 | 2x5 2.54 mm pin header, unshrouded, horizontal along the bottom edge | Eurorack power, back side; pin 1 (-12 V) marked by the back silk `-12V`; 10-pin cable only |

The exporter excluded exactly these 7 refs, as THT (`carrier/export-report.json`).
The shared native audit lists them as manual too
(`docs/jlcpcb-audit-requirements.json`).

**J10 has no key.** Plug the cable with the red stripe (-12 V) next to the `-12V`
silk. A 16-pin plug does not fit the 4HP width; use a 10-to-16 cable on a 16-pin bus.

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `701a3622482cad18dfa23476d50285287b1e1e9b1e95afd3699a4d95609f2393`.
- Carrier project `9f220a34c031f68083e4a78b6324ee8500c0e2569131c8259dd13e3506e8bb11`.
- Carrier schematic `8a8b3e1bb5fb586039720fdd33fe70f88051c1a458112b6ce8d00a70e4ef5a32`.
- Panel PCB `3177a65783898872f1e9ef40b08d03ff0147b26ce7b3645f717cbbf6f87061e2`.
- Panel project `1065016ea74056ee5e1ea5843ab82ee5f65016d8633078b9daaea47756d0d4ef`.

## Reproduce

From `modules/line-in`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board line-in --schematic line-in.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/line-in-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board line-in-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/line-in-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/line-in-gerbers.zip jlcpcb/panel/line-in-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change, so no stale plots remain
beside a new ZIP. The assembly audit is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/line-in-symbols.xml hardware/line-in.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/line-in/hardware --board line-in.kicad_pcb --symbols-xml /tmp/line-in-symbols.xml \
  --cpl modules/line-in/jlcpcb/carrier/positions.csv \
  --requirements modules/line-in/docs/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live)
```

## S3/R2 checks and changes

- Added input protection: R13/R14 10k and D3-D6 low-leakage BAV199 ground clamps.
  All existing placements and the output resistors remain unchanged. See
  `../docs/input-protection.md` for the powered-transient envelope and limits.
- Shared full check: ERC 0, DRC 0, unconnected 0, native parity 0, independent
  ref/pin/net parity equal, no exclusions. The profile explicitly verifies the
  source manifest; all five source hashes and all exports match.
- Panel DRC 0; panel source and shipping files are unchanged.
- Hand-solder gap >=2.081mm; courtyard-to-edge >=1.075mm. All 44 vias are outside
  SMD pad copper/mask openings. No panel axes moved.
- Carrier drill file: 60 round PTH hits (44 vias + 16 round THT pads) plus 16
  plated slots. Carrier NPTH is empty. The panel still has eight NPTH holes.
- Both copper layers, masks, silks, pastes, edge and drills are in the ZIP.
  BOM/CPL reference sets are equal: 36 Bottom components, 13 rows, seven manual
  THT refs excluded consistently. CSV/ZIP/loose-file mirrors are byte-identical.
- Final native plots were inspected. This is not an independent Gerber CAM or
  authenticated placement-preview approval.

## Sourcing and accepted review findings

The user accepted the previous assembly-review and physical-fit concerns and
instructed that the output resistors be left alone if shared with other modules.
**R7/R8/R12 are exactly ESR18EZPF1001 / C2074262**, as ACID, HATS, 8bit and MCC,
and remain unchanged. Their Extended classification and the earlier continuous
opposite-rail fault uncertainty are accepted as-is, not proved harmless.

A fresh strict-live audit of all 36 SMD references observed all 13 exact C-codes
and MPNs, Economy eligibility, and stock above the five-board placement demand.
This is a snapshot, not a reservation or an attrition/minimum-order approval.

- **R13/R14:** UNI-ROYAL 0603WAF1002T5E, C25804, 10k/1%/100mW/75V, Basic.
  The auditor's conservative voltage/current/power checks pass.
- **D3-D6:** Nexperia BAV199,215, C40919, SOT-23, Extended and Economy-eligible.
  This is **one additional unique Extended diode type**. Do not substitute
  ordinary BAV99/BAT54 parts: the low leakage is intentional.
- All R/C except the accepted ESR18 output resistors were observed Basic; existing
  D1/D2 and U1-U3 were also Basic.
- Human review attestations and capacitor impedance/bias evidence remain open.
  The unchanged shared Basic-only passive gate still flags ESR18. The audit
  therefore returns failure; no rule or review was falsified to make it green.

Evidence: ignored `research/input-protection/assembly-audit.json`, catalog
snapshots, `release-final/`, `geometry-review.json`, `preservation.json` and
`package-final.json`.

## User-controlled order / prototype checks

The accepted review concerns are not reopened as design-change requests, but no
supplier acceptance or physical test has been performed. Before approving an
order, verify Bottom-side service options, final Gerber DFM and the actual vendor
placement preview, including U1-U3 pin 1, D1/D2 cathode bars and D3-D6 SOT-23
orientation. Recheck stock/attrition/minimum quantities and the new Extended
diode type.

Bench qualification is still outstanding: low-level audio THD/noise, clipping
recovery, input step faults over temperature, and actual panel fit. **Powered-off
input immunity is not established**; the external ground clamp does not provide
a zero-volt clamp or a qualified power-off disconnect. No IEC ESD/surge claim.
