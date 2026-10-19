# audio-out — manufacturing export (S3/R3)

Generated from the current accepted sources with the shared
`opt/kicad-tools/jlcpcb/export.py` exporter. Never hand-edit these files: change
the sources, then re-export with the commands below.

## Contents

| Path | Data |
|---|---|
| `audio-out-gerbers.zip` | Carrier Gerber/drill ZIP (upload this) |
| `audio-out-panel-gerbers.zip` | FR4 front panel Gerber/drill ZIP (upload this) |
| `assembly/bom.csv`, `assembly/positions.csv` | Carrier BOM and CPL (upload these) |
| `carrier/` | Carrier export: ZIP unpacked (2 copper layers, masks, silk, paste, edge, PTH/NPTH drills), BOM, CPL, export report |
| `panel/` | Panel export: ZIP unpacked, empty BOM/CPL, export report |
| `source-sha256.json` | PCB/project/schematic inputs and export SHA-256 |

The top-level ZIPs and `assembly/` CSVs are byte-identical copies of the files in
`carrier/` and `panel/`.

## Upload map

| Order | Files | Options |
|---|---|---|
| Carrier PCB | `audio-out-gerbers.zip` | 2 layers, FR4, 1.6 mm, 19.0 x 110.0 mm, 1 oz, HASL, standard everything else. The board has no `JLCJLCJLCJLC` marker, so pick the order-number option deliberately: "Remove" (check the quote for any fee), or JLCPCB prints the number where it chooses |
| Carrier assembly | `assembly/bom.csv`, `assembly/positions.csv` | **Economic PCBA, assembly side: Bottom.** 26 parts in 12 BOM rows, all on the back |
| Front panel PCB | `audio-out-panel-gerbers.zip` | 2 layers, FR4, 1.6 mm, 20.0 x 128.5 mm (4HP), no assembly; black mask suits a panel |

### Hand-soldered after delivery (not in the BOM/CPL)

| Refs | Part | Why it's manual |
|---|---|---|
| J1, J2 | QingPu WQP-PJ301M-12 TS jack (IN L, IN R) | Front-side THT, panel-nut fixed; fit to the panel before soldering |
| J3, J4 | QingPu WQP-PJ366ST TRS jack (LINE, PHONES) | Same as above (Bread Modular part) |
| RV1, RV2 | RV09 vertical 50k pot (VOL L, VOL R) | Front-side THT; no nut, so the pots hang on their pins. Seat them flat before soldering |
| J5 | 2x5 2.54 mm pin header, unshrouded | Eurorack power, back side; pin 1 (-12 V) at the bottom, silk `-12V`; 10-pin cable |

The exporter excluded exactly these 7 refs, as THT (`carrier/export-report.json`).
The shared native audit lists them as manual too.

Soldering notes:
- **GND pads have no thermal reliefs** (both pours connect solid to jack
  sleeves, pot pin 1 and J5 GND), so use a hot iron.
- **J5 has no key.** Plug the cable with the red stripe (-12 V) at the bottom,
  next to the `-12V` silk. On a 16-pin bus use a 10-to-16 cable; a 16-pin plug
  would sit over the PHONES jack's pins (`docs/mechanics.md`).

## Source identity

Taken from `source-sha256.json`; the shared `check` re-hashes them and fails on
drift.

- Carrier PCB `dff25364351ea354da193f12c628f2446fd015ef290e49a80c6cd250bc481186`.
- Carrier project `3b1412c553e3847a26ff6911666a6d0abe15d51aa3ab741ec6182649cc448648`.
- Carrier schematic `aaf04615a5f6b2d455a4ab37434182d8a380d8b269ff094f2f162a00d056792c`.
- Panel PCB `9b4087a569cd4c55a5e2df693f4d49a838a2bf8e7b968eaa96502e323e313d77`.
- Panel project `da9975bd3660b7d635dc3bf74b158b944bde39f34e186a3e333d9c034e854085`.

## Reproduce

From `modules/audio-out`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/native

python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board audio-out --schematic audio-out.kicad_sch --side bottom --require-part-numbers \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/carrier
unzip -o jlcpcb/carrier/audio-out-gerbers.zip -d jlcpcb/carrier

python3 -B ../../opt/kicad-tools/jlcpcb/export.py panels/front-pcb \
  --board audio-out-panel --pcb-only \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb/panel
unzip -o jlcpcb/panel/audio-out-panel-gerbers.zip -d jlcpcb/panel

cp jlcpcb/carrier/bom.csv jlcpcb/carrier/positions.csv jlcpcb/assembly/
cp jlcpcb/carrier/audio-out-gerbers.zip jlcpcb/panel/audio-out-panel-gerbers.zip jlcpcb/
```

Delete the unpacked Gerbers first if layers change, so no stale plots remain
beside a new ZIP. The assembly audit (`docs/research.md` §5) is:

```sh
kicad-cli sch export netlist --format kicadxml -o /tmp/audio-out-symbols.xml hardware/audio-out.kicad_sch
(cd ../.. && python3 -B opt/kicad-tools/jlcpcb/assembly.py audit \
  --project-dir modules/audio-out/hardware --board audio-out.kicad_pcb --symbols-xml /tmp/audio-out-symbols.xml \
  --cpl modules/audio-out/jlcpcb/carrier/positions.csv \
  --requirements modules/audio-out/docs/jlcpcb-audit-requirements.json \
  --boards 5 --side bottom --strict-live)
```

## Checks done for this export

- **Shared `check`** (run before and after the export):
  `no_findings_in_requested_checks`. That covers:
  - ERC 0 and DRC 0 at all severities, with zones refilled;
  - 0 unconnected and schematic parity 0;
  - ref/pin/net parity equal;
  - the manifest equal (5 sources, all exports byte-identical).
- **Panel DRC:** 0.
- **Carrier drill files:** 44 round PTH hits (28 vias + 16 round pads) plus 16
  routed slots (the jack lugs) = 60. That matches 28 vias + 32 THT pads. There
  are no NPTH holes on the carrier.
- **Panel drill file:** 8 NPTH holes: 4 jacks (6.2 mm), 2 pots (7.2 mm), 2 rail
  slots (3.2 mm). No copper holes.
- **Gerber ZIP:** has both copper layers with their GND pours, both masks,
  silkscreens and pastes, the edge, and PTH/NPTH drills. F.Paste is empty
  because there are no front SMD parts.
- **3D fit:** 0 mm³ interference against both panels (`docs/fit/fit-report.json`).
- **Assembly audit** (live, 5 boards, run 2026-10-19 on this CPL):
  - No catalog failures: every C-code, MPN, Economy flag and stock level passes.
  - All R/C/diodes are Basic; U1 (OPA1678, 14,019 in stock) and U2 (MC33178,
    36,998 in stock) are Extended.
  - Every part is still `fail` only on the open review items below.

## Status and order gates (not done here)

This is a complete export, not a supplier-accepted release. Before ordering:

1. **Bottom-side Economic assembly.** Confirm the quote form offers **Bottom**
   for Economic (as for midi). In the same quote, check whether the 19 mm width
   needs edge rails and whether that keeps Economic eligibility.
2. **Placement preview.** Check in JLCPCB's bottom-side preview:
   - U1 and U2: the pin 1 dot (SOIC-8, both at 180°).
   - D1: the cathode bar is on pad 1, the +12 V rail; the anode is on the
     J5 +12 V pin.
   - D2: the cathode bar is on pad 1, the J5 -12 V pin; the anode is on the
     -12 V rail.
   - Every rotation: bottom-side CPL rotations are the usual place for errors.
3. **Live recheck before ordering:** stock, Basic/Extended class, minimum assembly
   quantities and attrition. The stock figures above are a snapshot, not a
   reservation.
4. **Your review attestations** in the audit (land pattern, pin mapping, ratings,
   capacitor role). These are left open rather than filled with boilerplate.
5. **JLCPCB DFM / Gerber viewer check** of both ZIPs.
6. **Bench:**
   - measure the real RV09 pot height (shaft tip to PCB) before ordering the
     panel; the model uses a nominal 6.8 mm body (`docs/mechanics.md`);
   - IN R normalling (only IN L patched -> both channels), line level and
     headphone level into 32 Ω;
   - the real jack panel height and hole fit.
