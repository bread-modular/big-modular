# Current layout — bounded review

**PASS: no required PCB correction established. Canonical hardware bytes are unchanged.**
This is a physical-layout/native-check result, not supplier release or bench/current/thermal qualification.

## Source and native checks

Reviewed only workspace `089`, branch `okbrain/big-modular/089-86776551`, starting HEAD/main `4403b021318021408c4438adfe9928fb42b02d5d` (includes owner setup `b7337ce`). No archived restoration or preliminary external review was used.

| Canonical source | SHA-256 |
|---|---|
| Carrier PCB | `937cba26feb2d0aba6c7add300378e405f82fae2901569460de81e96626c6b1a` |
| Panel PCB | `5e8b99ea3f9f178ea0030ab29d5c906e31b8a1ed722a0491b78efd74b32f4aab` |
| Carrier PRO | `122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9` |
| Panel PRO | `d8211fb9ceb1112ac893d16ada5df17ab439c3295ff61ca9fb112b4154045e52` |
| Root schematic | `4c3512d82c8a66903d2e7b917938ddf9b1f514697861766c53a8bb51eba13500` |

All twelve PCB/PRO/schematic hashes, including every child sheet, are in [source-sha256.txt](source-sha256.txt). No SaveBoard, rule/exclusion/part/placement/mechanical edits or candidate promotion occurred.

- **Carrier:** shared `kicad_tools.py check` using the actual project profile and KiCad CLI 10.0.6: all-severity **ERC 0; DRC 0; opens 0; native parity 0**, including exclusions and in-memory refill/all-track-errors. Exact shared ref/pin/net comparison is equal. [Raw ERC](carrier-check/erc.json), [raw DRC](carrier-check/drc.json), [commands/hash receipt](carrier-check/summary.json).
- **Panel:** native all-severity refill/DRC **0 violations, 0 opens**. [Raw panel DRC](panel-native-drc.json). The shared wrapper also returned clean DRC, but its compulsory comparison with the carrier schematic reports missing carrier refs: **inapplicable to this passive panel**, not an overall wrapper PASS. That limitation remains visible in [panel-check/summary.json](panel-check/summary.json); duplicate XML was omitted in favor of the identical carrier XML.
- **Independent identity check:** 116 electrical references, 344 unique pin/net identities (39 explicit NC), and 464 Value/Footprint/MPN/LCSC comparisons match. Literal auxiliary-field parity is not exact: 30 inherited differences on 15 IBB refs are absent schematic `JLCPCB Exclude`/`JLCPCB Audit Requirements` versus PCB `no`/`{}`. These remain disclosed, not silently repaired, in [independent-parity.json](independent-parity.json).
- Actual inventory: **116 electrical + 4 mechanical footprints, 721 tracks, 251 vias, 10 zones**; zero backside footprints/B.Paste pads. No unit/integration/regression tests, new framework, runtime installation, GUI, delegation, commits, merges, orders or manufacturing exports.

## Physical findings

- **Boost:** U14 EP17=system GND, SW1/15/16, VIN2, EN3; L5=C207852 6.8 uH; D29 SS34→PRAW. D29/C78 retain the compact all-front commutation loop and direct front ground return. C77–80 are outputs; C82–84 are input bulk; C88 is the local VIN bypass. FB exits away from the main SW path. Four EP vias remain. The short 0.24 mm × 0.8 mm SW fan-out is retained: no demonstrated defect justifies speculative widening. These are the relevant loop/bypass/ground criteria, rather than DRC alone. [source](https://www.ti.com/lit/ds/symlink/tps55340.pdf)
- **IBB:** U3 GND=NRAW; L1=C357250 22 uH, SW→system GND. C89–92/C7 are VPROT–NRAW; C5/C68 are only VPROT–system GND. Seven NRAW output capacitors are present, but C71 is remote, not pin-local; C9 is closest to U3. SW is short/front and FB is on the opposite side. **C7.2→U3.1 was actually traced:** F.Cu `(129,98.925)→(129.7,98.925)→(130.9,99.625)→(130.5,99)`; via to In1, then `(130.65,96.3)→(130.8125,95)`; via to F.Cu, then U3.1 `(130.8125,96.15)`. This is approximately **8.0 mm planar copper plus two layer transitions**, not an ideal all-front bypass. It is a ringing/EMI bench observation, not an established failure requiring a rushed reroute. IC ground must not be confused with system GND. [source](https://www.ti.com/lit/an/slva933/slva933.pdf)
- **LDO/thermal:** U12/U13 EP21=system GND; direct front ground copper, nine EP vias each and at least eight nearby external ground vias, connected to inner/back heat-spreading copper. Local input/output banks remain on their corresponding sides; U13 FB is away from the switchers. U2 EP17 correctly remains **RTN**, not system GND.
- **0.5 oz inner rails:** actual stack is **35 um outer / 15.2 um inner**, Tg155 7628/core and HASL SnPb; passive panel Tg135. NRAW's inspected 86.176 mm trunk is mostly 1.5/1.0 mm wide, with only 1.8 mm at 0.75 mm: copper-only 20°C screen **73.8 mΩ** (59 mV/47 mW at illustrative 0.8 A). VPROT's 62.242 mm trunk is mostly 2.0 mm, with 0.8 mm at 0.8 mm: **36.0 mΩ** (72 mV/144 mW at illustrative 2 A). N12's 1.0 mm-wide In2 segments total 13.845 mm: approximately **15.7 mΩ**. No significant local rail bottleneck was established. Exact NRAW/VPROT segment UUIDs and assumptions: [inner-rail-screen.json](inner-rail-screen.json). These exclude via/pad resistance and temperature rise; **not ampacity, simultaneous-load or full-temperature guarantees**.

## Mechanical crosscheck

Meaningful datums: panel `X=x-50, Y=y-30`; carrier `Y=x-35.75, Z=104.275-y`, with component-specific axis offsets.

- `assembly-envelope.scad`: **13 lines, no L1 assertion formulas**. Bracket web **2.40 mm max**, origin **X0.10**; nominal carrier faces X2.50/X4.10.
- L1: `9.8-0.10-(0.10+2.40+1.76)=5.44 mm` available versus `5.0+0.15+0.10+0.15=5.40 mm` required: **0.04 mm extra margin** beyond the included residual allocation. Measure the printed web; no obsolete 5.1 mm hold.
- Native USB aperture **X3.30/Y28.10/W5.00/H10.80/R0.60** matches SCAD. J1's actual origin maps to shell axis **(5.73,33.50,0.80)** using the drawing-based shell height.
- D10's actual pad1 plus 1.27 mm axis offset matches panel **(6.10,43.00), Ø3.60**; it remains DNP. SW1's actual peg row and 1.70 mm axis height match **(5.80,49.50), Ø3.20**. Bracket/carrier mounts agree at shared datums.
- **No opening mismatch or enclosure change justified.** Physical cable/ABS/assembly qualification remains pending. [Measured crosscheck](mechanical-crosscheck.json).

## Handoff

One [current nonblack native copper render](current-layout.png), with four layers and boost/IBB/LDO insets; chat URL: `/uploads/6b5a6fd7-fce4-48f0-91a0-75b25ff9d71a.webp`. It is a review plot, not a manufacturing export.

Before budget-boundary steering, 203 obsolete routing files (12,572,738 bytes, including 22 native-source clones) were retired after exact tracked-blob verification; all remain recoverable in the starting Git commit. [Cleanup receipt](history-cleanup.json). Current status/README pointers were corrected; historical manifests were not rewritten. These uncommitted documentation/deletion changes are for the integrating worker to review.

**PCB is settled byte-for-byte for the separate export worker.** `jlcpcb/` was not touched or validated here; the separately reported incomplete manufacturing set must not be treated as released. No further optimization or export work is undertaken in this pass.
