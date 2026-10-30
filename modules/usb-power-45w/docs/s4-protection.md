> **Historical S4 record.** S5 supersedes its 1.978 A source policy and D10 choice; see [S5](s5-current.md) and [current design](design.md). S4 hashes/catalog observations describe that earlier snapshot, not current sources.

# S4 protection and power-budget change record

## Implemented scope

- Replaced U5 TPS259470ARPWR with **TPS16630PWPR / C1849461** and its HTSSOP-20
  exposed-pad footprint. All supply/output pins and EP are connected.
- Replaced D1 with a 22 V stand-off SMBJ22A; raised backup F1's DC voltage class
  to 63 V. Added D10 SS56 because TPS16630 does not itself block reverse current.
- Added a separate low-current protected CH224A supply: Q2/Q3/R23/R27 and D9, plus D11 for auxiliary-capacitor reverse discharge.
  The PD controller still negotiates before the main eFuse turns on.
- Changed R5 to 9.1k: 1.978 A nominal, with an explicit **qualified 20 V / >=2.25 A
  source policy**. This is fixed budgeting, not automatic PD-current tracking.
- Added independently calculated UVLO/OVP dividers, including OVP recovery at
  the highest valid input. C3 is now 22 nF; old C4/ITIMER is removed.
- Replaced AUXOFF gating with PGOOD gating. SW1 now operates the dedicated SHDN
  input. MODE retains automatic retry; FLT and IMON have diagnostic test pads.
- Added eight bare copper input/status pads, excluded from BOM/placement.
- Kept U2, U3 and U4 power-stage connectivity, values and footprints unchanged.
  A native S3/S4 comparison also verifies the unchanged output-side circuitry.
- Regenerated the native schematic, pinned symbols, native BOM and PDF.
  The sheet is A2 to keep the expanded protection section readable.

## eFuse cost and stock selection

Public JLCPCB lookup evidence was captured during this task. Exact UTC retrieval
instants, requests and raw-response SHA-256 values are in `s4-sourcing.json`.
These are dated observations, not reserved stock or an order quotation.

| Candidate | C-code | Observed stock | Unit price, quantity 1–9 | Decision |
| --- | --- | ---: | ---: | --- |
| TPS16630PWPR | C1849461 | 1,136 | **$2.6926** | Selected; below the requested $3 IC price ceiling |
| TPS26630RGER | C1850276 | 97 | $13.2479 | Earlier review suggestion rejected for cost/stock |
| TPS26600PWPR | C544399 | 1,904 | $1.5585 | Lower-current alternative, not selected |
| TPS259470ARPWR | C3662799 | 2,591 | $1.2930 | Original part; insufficient input-voltage headroom for the original TVS |

The selected IC has substantially better stock than the earlier **TPS26630**
recommendation, **not** more stock than the original TPS25947. Its quantity 10–29
unit price was $2.2403. JLC marks it **Extended** and independently **Economic
eligible**. Prices exclude feeder/setup, assembly, shipping and tax. Supporting
protection components add cost; $2.6926 is the eFuse IC, not the entire input stage.

## Important engineering details

- U5's symbol follows TI SLVSET9G table 5-1 and PWP0020T. Pins 18/19/20 are
  physically common OUT terminals: one `power_out` driver and two passive
  duplicate terminals model that bank without pretending there are three
  independent supplies. No ERC rule or exclusion is weakened.
- The footprint is the stock KiCad PWP0020T-compatible variant with 2.96 x 2.96 mm
  exposed mask aperture, 0.65 mm lead pitch and EP21. Its copper/paste/via pattern
  is retained. Lead land dimensions differ slightly from TI's example, as allowed
  by the IPC alternative-pattern note. Thermal-via tenting and paste behavior
  still need fabrication review; these are footprint-owned EP vias, not routing
  vias inserted into unrelated SMD pads.
- **Q2 is manufacturer-specific:** Nexperia BCX53-16 has E=1, C=2, B=3 in the
  cited datasheet. The installed KiCad symbol describes the differently numbered
  Infineon part. A distinct local `BCX53_NXP` symbol pins the correct mapping,
  including the simulation-pin metadata. Verify C47787, not another BCX53 variant.
- D10's cathode points toward U5 IN; it prevents protected bulk energy from
  feeding the USB input through U5's body diode. Its forward loss is included
  in the budget, not silently ignored.
- Q2/Q3 is an approximate small-current limiter, not a second precision eFuse.
  The design requires measured startup/current/temperature behavior; the 24 V
  shunt must not be treated as an ideal clamp. See `design.md` for thermal copper
  and fault-test requirements.
- PGOOD has an 8–13 ms falling deglitch. SW1 is input-disable/restart, not a
  guaranteed all-module discharge/reset supervisor.

## Verification performed

- Native KiCad full ERC, including warnings/exclusions: **0 errors, 0 warnings,
  no ignored checks** on the regenerated candidate and final source.
- Generator connectivity assertion plus independent `verify_design.py`:
  **98 components, 66 XML nets including NC, zero table/field/pad mismatches**.
- Independent critical pin checks for U5, D1/D9/D10, Q2/Q3, SW1 and U1; all
  footprint pad-number sets match the circuit, including U5 EP21.
- Comparison against the S3 native XML checks **65 unchanged components**,
  including all three converters and output circuitry, for values, footprints
  and pin-net identity. Deliberate input-stage changes are scoped separately.
- Resistor/IC/leakage/temperature-corner calculations are executable, not just
  nominal claims. OVP falling minimum is approximately 21.09 V; total screened
  normal-input current limit including the 25 mA auxiliary reserve is 2.245 A.
- Native save/reload, BOM/reference checks, and rendered schematic inspection
  are retained in `research/s4-protection/`.
- Shared native XML inspection was used. Shared schematic inspection remains
  blocked by unresolved `${KICAD10_3DMODEL_DIR}` in its dependency handling;
  shared project `check` requires a board. No models/dependencies/rules were
  removed to make those gates appear to pass.

## Sourcing and release blockers retained honestly

The final sourcing snapshot covers **39 exact codes / 87 sourced placements**.
All have positive observed stock and explicit Economic eligibility. No design
upload or supplier preview was performed. J2/J3/D8 remain hand-installed, and
TP1–TP8 are bare copper rather than fitted components.

**Four inherited electrolytics are Extended:** C5 (C165527), C34/C35/C36 (C350012).
The old blanket “all R/C Basic” statement was incorrect. They were not silently
replaced, marked manual, or declared an approved exception. The Basic-only policy
therefore remains an open assembly gate. All newly selected R/C meet Basic and
Economic independently.

F1/D1/D10 public catalog electrical ratings were checked. Their linked full
manufacturer PDFs could not be extracted in this environment (HTML/403/no content);
this is retained as a supplier-document/land-pattern/pulse-thermal release gate,
not claimed to be a completed manufacturer-document audit. TI, WCH, Diodes and
Nexperia documentation for the core active circuit was read successfully.

Still required: actual PCB/layout, converter and auxiliary-stage thermal tests,
PD analyzer tests of the selected source/cable, hot-plug and already-powered
surge peaks, startup into maximum real module capacitance, fault/short/recovery
behavior, negative-rail loop stability and audio/EMI measurements. In particular,
U1 must remain below 30 V and the positive buck VIN pins must stay within their
recommended/absolute limits over defined transients. No arbitrary sustained
60 V input, universal charger support, output-current guarantee or IEC compliance
is asserted. No commit, merge, order or supplier upload was made.
