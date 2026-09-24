# Validation — A0, 2026-09-24

Run with the locally installed **KiCad 10.0.6**. These are prototype checks, not fabrication approval.

## Schematic

- Seven sheets, 85 BOM components (plus ten explicit power-source ERC flags).
- `kicad-cli sch erc --severity-all`: **0 errors, 0 warnings** after placing connection points on the 1.27 mm grid and leaving unused TPS62125 EN_hys open as the datasheet permits.
- No electrical-rule severity was disabled; no ERC exclusion was used.
- `kicad-cli sch export netlist`: native netlist generated. `tools/verify_project.py` independently compares all exported non-NC component pins with the intended connection audit and fails on differences. KiCad omits off-board J2 from a PCB netlist; its 12 connected pins and four NC pins are instead checked against the actual schematic pin → wire → global-label / NC geometry.
- `kicad-cli sch export pdf`: all seven pages exported to `docs/schematic.pdf`.
- ERC does not validate converter stability, ratings, pin names against a datasheet, host authorization, PSRR or thermal performance. See documented review blockers.

## Panel board

- **0 DRC violations; 0 unconnected items.** Valid closed external outline and rounded USB opening.
- Only four NPTH mounting footprints; no electrical component, route, via, copper graphic or zone.

## Carrier board

- **4 DRC clearance errors** remain, all at the *unmodified installed USB4105 footprint*: ground SMT pads versus its two locating NPTH holes. Actual clearance is **0.1944 mm**, below KiCad's default **0.2500 mm** rule. Duplicate A/B ground pads yield four reported instances.
- **6 unconnected-item errors** are expected because connector power/ground/shield pads are intentionally unrouted. These were not fixed with prohibited copper or hidden by severity changes.
- No invalid outline errors. Front shell pad-to-edge clearance is now **0.5000 mm** under the default 0.5000 mm rule. Mouth is consequently at nominal **Z=+0.800 mm**.
- **Do not fabricate yet:** ask the chosen fabricator to accept the datasheet/library locating-hole geometry or revise the footprint with a qualified land-pattern/tolerance analysis. The default hole rule has not been weakened just to obtain a green report.
- Schematic parity is intentionally not requested: 84 other circuit components are not placed. There is only one electrical footprint, J1, plus four mechanical NPTH holes.

## Programmatic invariants

`geometry-and-net-audit.json` records the pin check and board inventory. Both board files have **0 tracks, 0 vias, 0 zones, 0 copper graphics**. The nominal coordinate transform gives port `(X,Y,Z)=(4.900,64.250,0.800)` mm with insertion vector `(0,0,+1)` and a 90-degree angle to the front-panel plane. USB pad net assignments are compared with the schematic intent.

These geometry checks do not certify the still-unspecified bracket/cradle, output harness connector or worst-case mechanical tolerance stack. There was no completed electrical placement, copper routing, 3D assembly qualification or bench measurement.

## Repository hygiene

No commit or merge. No sibling repository access. Raw downloaded datasheets, extracted text and research screenshots are ignored under `/research/` and are not deliverables; only concise facts and source URLs are included. The schematic PDF is a generated design deliverable, not a raw source PDF.
