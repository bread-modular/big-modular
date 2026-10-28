# line-in — manufacturing export (S2/R1)

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
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 30 parts in 11 BOM rows, all on the back |
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

- Carrier PCB `f4d7b89bb3f6a08610d53da92d1ad3c5a975fe6906c49c6df376e9530c045cd8`.
- Carrier project `9f220a34c031f68083e4a78b6324ee8500c0e2569131c8259dd13e3506e8bb11`.
- Carrier schematic `91af959c7dabcf4fd5b6f28f14eb3ea7545c181970517a209e09f18e76c9a043`.
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

## Checks done for this export (2026-10-28)

- **Shared `check`** (run before and after the export):
  `no_findings_in_requested_checks`. That covers:
  - ERC 0 and DRC 0 at all severities, with zones refilled;
  - 0 unconnected and schematic parity 0;
  - the manifest equal (5 sources, all exports byte-identical).
- **Panel DRC:** 0.
- **Carrier drill file:** 47 round PTH hits (31 vias + 16 round pads) plus 16
  routed slots (jack and pot lugs) = 63. That matches 31 vias + 32 THT pads. There
  are no NPTH holes on the carrier.
- **Panel drill file:** 8 NPTH holes: 4 jacks (6.2 mm), 2 pots (7.2 mm), 2 rail
  holes (3.2 mm, X 12.58). No copper holes.
- **Gerber ZIP:** both copper layers with their GND pours, both masks,
  silkscreens and pastes, the edge, and PTH/NPTH drills. F.Paste is empty
  because there are no front SMD parts.
- **Assembly audit** (live, 5 boards, run 2026-10-28T14:40Z on this CPL; raw JSON in
  the ignored `research/jlcpcb-audit.json`):
  - Every C-code and MPN matches the catalog, every part is Economy-eligible and in
    stock (lowest: R7/R8/R12 C2074262, 100,736).
  - All capacitors, D1/D2 (B5819W) and U1-U3 (TL072CDT) and the 0603 resistors are
    **Basic**.
  - **R7, R8, R12 (ROHM ESR18EZPF1001, 1k 1206 0.5 W) are Extended**, the only
    catalog failure ("R/C requires actual Basic"). The only Basic 1206 1k is
    UNI-ROYAL 1206W4F1001T5E (C4410, 0.25 W), below the ~0.36 W a ±12 V
    output patched into OUT L/R/MONO can put in the resistor. Same part and
    trade-off as acid and 8bit. Open user decision; not changed.
  - D1/D2 and U1-U3 report `package/footprint: unknown` (catalog "SOD-123" / "SO-8"
    versus the pinned footprint names); the land patterns match, but this is left
    for your review attestation.
  - Every part is still `fail` on the open review items (land pattern, pin
    mapping, ratings, role; DC-bias / ESR for the caps). These are left open rather
    than filled with boilerplate.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **R7/R8/R12 class:** accept the Extended 0.5 W ESR18 (Extended feeder fee) or
   decide otherwise.
2. **Bottom-side Economic assembly.** Confirm the quote form offers **Bottom**
   for Economic, and whether the 19 mm width needs edge rails.
3. **Placement preview.** Check in JLCPCB's bottom-side preview:
   - U1, U2 (0°) and U3 (90°): the pin 1 dot (SOIC-8).
   - D1: the cathode bar on pad 1, the +12 V rail; the anode on the J10 +12 V pin.
   - D2: the cathode bar on pad 1, the J10 -12 V pin; the anode on the -12 V rail.
   - Every rotation: bottom-side CPL rotations are the usual place for errors.
4. **Live recheck before ordering:** stock, Basic/Extended class, minimum assembly
   quantities and attrition. The stock figures above are a snapshot, not a
   reservation.
5. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
6. **Bench:** real RV09 height against the panel, jack hole fit, line level to
   ~10 Vpp at the outputs, MONO sum.
