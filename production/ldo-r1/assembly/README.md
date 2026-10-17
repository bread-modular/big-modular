# LDO-R1 JLC assembly BOM / CPL (current prototype)

Generated from the frozen 037 source with the **existing common exporter**
(`opt/kicad-tools/jlcpcb/export.py`), KiCad CLI 10.0.6. No centroid CSV was
hand-edited and no supplier preview/approval is claimed.

- Board: `hardware/big_modular.kicad_pcb`, SHA256
  `7d709a4fc313b13bddc7f1664f199313f482dd9ed0a82d3592a452cf92d35af3`
- Origin: KiCad drill/place origin; units mm; side **top** (single-side assembly).
- Command: `python3 -B opt/kicad-tools/jlcpcb/export.py hardware --board big_modular
  --schematic big_modular.kicad_sch --include-through-hole --side top
  --require-part-numbers -o <scratch>`
- Fitted purchased parts: **97** (99 design refs, 98 non-DNP incl. J7, 97 purchased).
  BOM 49 grouped rows / CPL 97 placements, identical reference sets, quantity sum 97.

## Explicit exclusions

| Ref | Reason |
|---|---|
| D10 | **DNP** (user-authorized). Physical footprint/pads and the *design* BOM record remain; not fitted and not purchased. Absent from this BOM and CPL. |
| J7 | Manual IDC wire landing, **not a purchased header**; excluded from position files and assembly purchasing. |

## Explicit inclusions (not silently filtered)

- **J1** – hybrid USB connector: SMT contacts plus plated through-hole shell slots.
  Included explicitly via `--include-through-hole`; shell soldering/process remains a
  supplier gate.
- **SW1** – TL3340AF160QG SMT reticle switch; its J-lead/case-paste process remains a
  supplier gate.

## Sourcing

All 97 fitted parts have a dated public JLCPCB observation of **Economy eligibility**
(45 unique C-codes, snapshots dated 2026-10-17; reused 035 lookups plus fresh
strict-live lookups for the changed codes). This is **not allocation, stock
reservation or order acceptance**. Fitted classification: 54 Basic / 43 Extended
instances; R/C only: 50 Basic / 29 Extended instances. The 29 explicit Extended
codes/refs and reasons are in `exceptions.json`; a generic strict Basic-only R/C
audit may honestly flag them — they are user-authorized exceptions, not Basic parts.
Per-code supplier URL/UTC/request/raw-SHA provenance ships as `sourcing-evidence.json`.

## Human order gates

1. Supplier BOM/CPL preview: rotation, pin 1/ polarity, placement on every ref.
2. J1 shell-slot soldering and SW1 J-lead/case-paste process review.
3. Current stock, attrition, minimum assembly quantity and order options.
4. Assembly/current/thermal/bench qualification and physical fit are still open.

The bare-PCB fabrication ZIP is separate: `../Big-Modular-LDO-R1-CARRIER-4L-STANDARD-VIAS-BARE-PCB.zip`.
Do not upload this directory as a PCB fabrication archive.
