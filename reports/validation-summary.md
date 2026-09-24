# Validation — focused A0 review, 2026-09-24

KiCad 10.0.6 CLI, regenerated from `tools/build_project.py`. **Review scaffold, not fabrication approval.** No copper routing was added. `docs/schematic.pdf` **was regenerated from the current seven KiCad sheets with `kicad-cli sch export pdf` and matches them** (7 pages, A3) — the export is a review document, not the source of truth and not fabrication approval. Both `reports/erc.rpt` and `reports/erc.json` are current KiCad ERC exports.

## Schematic

- Seven sheets, **83 BOM components** (unsafe input TVS D1 removed; former redundant input Schottky remains omitted), plus nine ERC power-source flags. D1 is absent from the input sheet, library, native netlist and BOM; other diode references D2 onward are preserved.
- `kicad-cli sch erc --severity-all`: **0 errors, 0 warnings**. KiCad's report lists four ignored check *types* (single global label, four-way junction, SPICE, footprint-filter mismatch); no project-level ERC exclusion or severity weakening was applied in this review.
- `kicad-cli sch export netlist`: updated native netlist. `tools/verify_project.py` checked **248 connected symbol pins**, including 12 off-board J2 pins checked from actual schematic label/wire geometry, and **42 manually reviewed critical pin/net spot-checks**; it also asserts D1 is absent from the BOM, schematic and netlist. Most intended nets and the generated schematic use the same generator; the full-net audit is **not independent datasheet verification**. Even the separate spot-checks do not establish analog correctness.
- Manufacturer TPS2660 datasheet specifies reverse-current blocking with back-to-back FETs, including output-leakage characterization with IN unpowered. Removing the redundant series diode improves 5 V headroom but **does not qualify** 5 V fallback, USB host authorization, backfeed under every fault, or the chosen 0.30 A limit at operating conditions. CH224K requests 9 V only if the source offers it; unpowered CC/dead-battery Rd and 5 V-only attachment require a bench test.

## Panel board

- `kicad-cli pcb drc --severity-all --format json`: **0 violations, 0 unconnected items**. Closed outer outline and rounded USB aperture. Four mechanical NPTH footprints only; no electrical component or copper artwork.

## Carrier board

- `kicad-cli pcb drc --severity-all --format json`: **4 hole-clearance violations**, all J1 A1/B12 and A12/B1 ground SMT pads versus the two locating NPTH holes of the **unmodified** installed USB4105 footprint. Measured **0.1944 mm < 0.2500 mm** default board rule. **6 unconnected items**, expected because J1 is intentionally unrouted. No outline violation.
- No arbitrary rule suppression or unsubstantiated land-pattern adjustment was made. Fabricator-approved, connector-drawing-confirmed footprint/hole/pad tolerance work is still required. Schematic parity was not requested: only J1 and four mechanical holes are placed. This board is not an electrically complete PCB.

## Safety-critical residual blockers

- **Do not fabricate:** D1 SMBJ12CA was **removed**, avoiding its continuous-conduction hazard at sustained 15/20 V. There is now **no qualified input ESD/hot-plug/surge clamp**; TPS26600's ~10.78 V typical OVP interrupts OUT, not upstream VBUS. The unselected 500 mA / 32 V F1 lacks time-current, interruption and pulse coordination. Same-family SMBJ24CA (24 V standoff, ≤1 µA leakage at 24 V/25°C, 26.7–29.5 V breakdown at 1 mA, 38.9 V max clamp only at 15.5 A 10/1000 µs, 600 W pulse) is *not fitted or sourced*: actual unknown pulse/repetition, fuse response and connector 48 V DC / eFuse 62 V absolute / 50 V MLCC / CC limits are unqualified. R1's 21 V **steady-state** calculation does not prove surge safety. Details and manufacturer citations: `docs/design-review.md`.
- The four physical J1 copper-to-NPTH DRC errors remain. No datasheet-confirmed footprint revision or fabrication clearance concession exists.
- No authorized generic USB-host fallback. Manufacturer CH224K v1F powered reference has no external Rd, but does **not** specify passive/unpowered CC Rd or guarantee a dead-battery 5 V attach; bench verification remains mandatory. Default RUN open, no USB enumeration/CC current decoding; a dedicated approved 5 V source, measured voltage under load, and startup/current/thermal/audio testing are needed before even the tentative 20 mA/rail test budget. On 9 V PD, the tentative 40 mA/rail budget is likewise not established. TPS62160 4.016 V at minimum 4.2 V eFuse input has narrow dropout room.
- TPS62125 operates *up to* 1 MHz and enters light-load PFM: strict always-MHz/audio-clean switching is **not met**. Do not claim stable/noiseless rails from ERC/DRC. Analog compensation, effective capacitance, current limit, LDO/headroom, output faults, mechanical brackets and ordinary plug fit remain unqualified.

## Geometry / provenance

`geometry-and-net-audit.json`: carrier `J1,H1–H4`, panel `H1–H4`; **both boards 0 tracks, 0 vias, 0 zones, 0 copper graphics**. Nominal port `(X,Y,Z)=(4.900,64.250,0.800) mm`, insertion normal to the panel, with faceplate aperture 4.2 × 9.8 mm. Nominal geometry is not a tolerance stack or a front-mating plug test. Original board files were restored byte-for-byte after generator run (no board UUID churn). No board can be fabricated into a functioning power supply. No commit or merge; no sibling-repository access.
