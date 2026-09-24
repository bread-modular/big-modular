# A1 validation summary — INCOMPLETE / NON-OPERATIONAL

KiCad 10.0.6, actual CLI exports. A1 WIP was subsequently merged into main; this is a validation report for an incomplete design, not a claim that A1 was never committed or merged. This independent review makes no commit or merge. No sibling repository was accessed during this review.

| Executed check | Result |
|---|---|
| Schematic sources / hierarchy | **1 source sheet**, no subsheet objects; six obsolete sources deleted |
| PDF page check | **1 page, A1**, exported from current root schematic |
| BOM | **88 components** plus 9 ERC power flags; existing refs preserved; Q1/R28..R31 added |
| Native KiCad ERC | **0 errors, 0 warnings**, text and JSON reports |
| Connected-pin audit | **260**: 248 native-netlist pins plus 12 off-board J2 pins traced in the schematic |
| Independent hardcoded pin/net checks | **65** including PG, PNP B/E/C, SHDN, UV/OV, negative rectifier/LDO and J2 |
| Wire-only interstage traversal | **21** connections; no labels used to prove these physical schematic paths |
| PG/RUN/window model | **28** structural logic cases; NOT PD simulation or hardware tests |
| Actual PCB geometry | **8 NPTH hole checks**, both outlines and unchanged J1 axis/position/orientation |
| Carrier DRC | **4 physical clearance violations + 6 intentional unrouted items** |
| Panel DRC | **0 violations, 0 unrouted items**; does NOT assess head encroachment/FR4 strength |
| Placement / routing | Carrier electrical footprint **J1 only**; both boards **0 tracks, 0 vias, 0 zones**, no copper graphics |
| git diff --check | Passed after LF-only BOM regeneration |

## Scope / source-preserving changes

The old 83-part circuit is retained except: R4 becomes 562k with its upper end tied directly to fused VBUS; U2 SHDN is now EF_ENABLE, not floating; JP1 is in series between PG_PERMIT and EF_ENABLE. Q1 and four resistors form PG inversion, base bias, default shutdown and output bleed. Native net names have the normal root-sheet '/' prefix after replacing global labels with local labels; pin/net checking normalizes that prefix. BOM `Block` replaces misleading old `Sheet` grouping. The schematic is one real connected circuit, not six pasted images. Converter/preregulator/output semantics remain unchanged.

The drawing and PCB now use the primary Doepfer x=7.5, y=3/125.5, diameter3.2 hole geometry. A 5mm slot cannot fit there. J1 aperture and port axis remain unchanged; carrier hole placements remain unchanged. Added drawing-layer outlines describe two custom machined right-angle mounting blocks.

## Deliberately NOT resolved

- **Strict PD contract/current proof:** WCH PG is generic active-low Power Good. Hardware now requires PG + voltage window + RUN, and rejects 5V even with RUN/PG active, but it does NOT independently prove a 9V fixed PDO at required current. A 9V non-PD input plus a false PG can pass. This is an explicit fabrication blocker, not a finished automatic PD-only authorization system.
- Threshold calculation bounds including 1% resistors and +/-100nA: UV rise **7.5921..8.3053V**, UV fall **6.9738..7.6320V**; OV rise **10.3337..11.3794V**, OV fall **9.5771..10.4571V**. These are static calculations, not transient/temperature/source-authorization proof. Gate startup, PG loading, leakage, precontract residual voltage, current-limit margin and loss-of-contract behavior remain untested.
- **Surge/ESD:** unsafe D1 remains absent; no qualified VBUS/CC TVS or coordinated fuse/hot-plug protection was selected.
- **J1 physical DRC:** four copper-pad-to-locating-NPTH clearances are **0.1944mm versus required 0.25mm**. Selected footprint unchanged; no rule suppression or fabricated land-pattern justification.
- **Rack mounting:** x=7.5 on a 9.8mm panel leaves **0.7mm FR4 web**; a 6mm M3 head extends **0.7mm beyond the panel**. Head/washer selection, adjacent-panel clearance and strength remain blocked despite clean panel DRC. Four low-head M2 screws for the dimensioned interposers are also not procurement-qualified.
- **No electrical board:** 87 of the 88 circuit parts are not electrically placed on the carrier (J2 is intentionally off-board); no routes, thermal copper, placement feasibility, EMI, stability, rail tracking, precision output OVP, hardware operation or cable/plug fit were tested. Only provisional ~40mA/rail simultaneous test loads at independently verified 9V are contemplated, not output ratings.

The full intended net audit shares its source with the generator; only the additional hand-authored spot checks and independent schematic traversal catch co-drift. A traversal caught and corrected a draft PNP wire passing through the wrong pin before this final export; ERC alone did not establish that geometry. The final native netlist and all independent checks pass.

KiCad PCB Python bindings emitted nonfatal `PROPERTY_ENUM`/duplicate image-handler diagnostics; commands completed and saved outputs were reopened and checked. No DRC exclusions were added. DRC ran without schematic parity or zone refill to preserve the connector-only boundary. ERC/DRC and calculations are not operational, thermal, USB compliance or fabrication approval.

Exact changed/new/deleted paths are in `reports/deliverable-files.txt`. Regeneration commands are in README; no third-party downloads are required. `docs/test-matrix.md` lists the UNEXECUTED hardware acceptance tests.
