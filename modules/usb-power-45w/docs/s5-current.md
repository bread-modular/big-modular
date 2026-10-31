# S5 — board-side current protection, not a 45 W adapter budget

## Decision and implemented delta

The user requested removal of the adapter-based 1.978 A restriction and selection
of the highest defensible board-side setting. **4.186 A nominal** is selected;
this is a schematic design setting, not a measured maximum-safe system rating.

- **R5:** 9.1k -> 3.3k, UNI-ROYAL 0603WAF3301T5E / C22978.
- **R29 added:** 1k, UNI-ROYAL 0603WAF1001T5E / C21190, in series below R5 to GND.
  R5 + R29 = 4.3k; I_LIM = 18 / 4.3 = 4.186 A.
- **D10:** MDD SS56 / SMA -> ZHIDE SS1060 / C2917888 / **SMC**. A higher-current
  reverse blocker with more thermal layout area replaces the small input diode.
  Electrical polarity is unchanged: pin 1 K = EF_IN, pin 2 A = VPD.
- **U5 retained:** TPS16630PWPR / C1849461, HTSSOP-20 exposed-pad package.
- TVS, backup fuse, separate CH224A protection, voltage thresholds, startup ramp,
  PGOOD gating, SHDN switch and auto-retry are unchanged.
- U2/U3/U4, inductors, compensation-related components, output capacitors, voltage
  dividers and rail current targets are unchanged. No PCB or panel was created.

A single 4.3k C23159 was checked but is **Preferred Extended**, not Basic. The
small two-resistor series network uses independently verified Basic/Economic
parts and preserves the equivalent resistance at full worst-case corners.
Do not short/bypass R29.

## Why stop here rather than set 5 A or 6 A?

The input connector is a **5 A-class** part. U5's own 6 A capability is not the
limit of the whole module. The selected setting screens to:

| Quantity | Result |
| --- | ---: |
| Nominal main-path limit | 4.186 A |
| Low threshold corner | 3.693 A |
| High threshold corner | 4.698 A |
| High threshold + 25 mA normal auxiliary reserve | 4.723 A |
| Guard against the 5 A input class | 0.277 A |

The screen includes +/-10% IC error and 1% resistor tolerance plus 100 ppm/K over
100 K. It is deliberately wider than TI's +/-7% near 4.5 A, but remains a
screening model to verify, not a new manufacturer guarantee. The constraint is
5 A minus at least 0.25 A static guard, not 45 W / 20 V. 4.3k is the highest-current
E24-equivalent choice satisfying it; 3.9k, 4.02k and a 3.3k-only path are rejected.

Short-circuit pulses can exceed this static ceiling: fast-trip is about 2x ILIM
with a finite response. The eFuse is shared input protection, not a substitute
for each converter's internal protection, output overvoltage protection or a
thermal sensor on the series diode/connector.

## Power and source expectations

The same three targets (+12 V/2.5 A, +5 V/2.5 A, -12 V/1 A) total **54.5 W** at
rounded rail voltages. Actual divider values total about 54.94 W. Estimated
converter input is **62.26 W**, using the unchanged, unmeasured efficiency
assumptions. Including a 0.75 V diode-drop screen, 53 mOhm eFuse RON, 50 mOhm other
input-path allowance and auxiliary current gives roughly **66–67 W at the USB
receptacle**; cable losses before that point are additional.

For full load use and verify **20 V / 5 A PD plus a 5 A e-marked cable**, typically
a 100 W-capable single port. The larger source gives headroom; it does not force
100 W into the board. No current-contract-reading MCU or new PD controller was
added. Smaller adapters may work at lower loads but can droop, trip or restart
at excess load; no automatic budget matching or low-current-contract rejection
is claimed. Do not assume an unknown/defective adapter or cable is safe.

The S4 26–29 W planning restriction is removed. Simultaneous full-load thermal,
startup and inverter-loop performance is still **unqualified**, not guaranteed
by the current-limit calculation or clean ERC.

## Input-diode and PCB thermal requirements

The selected ZHIDE sheet is available through a manufacturer-document mirror:
https://datasheet4u.com/pdf/942007/SS1060.pdf

The exact catalog and that sheet differ in some ratings. The design uses the
conservative envelope: **60 V blocking, 0.75 V at 5 A screening drop, 125 C
junction ceiling** and does not claim the larger catalog surge figure. The
manufacturer sheet's 150 A nonrepetitive surge is not a repetitive-pulse or
steady-state allowance. Obtain confirmation of the delivered revision for release.

- D10 loss screen: 2.63 W at 3.5 A, 3.53 W at 4.698 A. Target effective
  **junction-to-ambient <=20 C/W** at 50 C ambient. This must be achieved by the
  future copper/stackup and measured; the sheet's 2 C/W is **junction-to-case**.
- Do not equate nominal pad area or a package current rating to a proven cooling
  result. Start with large connected copper at least comparable to the sheet's
  16 x 16 mm reference, increase as necessary, and provide backside copper/vias.
  No ordinary via-in-SMD-pad shortcut; retain project assembly rules.
- U5 maximum-RON loss is approximately 0.65 W at 3.5 A or 1.17 W at 4.698 A,
  plus its supply current. Its PowerPAD must be soldered to effective GND copper.
- Inspect F1 thermal derating, current/time and pulse behavior at actual ambient;
  verify J1 contact temperature/drop and both cable orientations. The aggregate
  50 mOhm extra-path allowance is a qualification budget, not a measured resistance.
- Size main copper for normal current and fast-trip pulses; TI recommends power
  path traces capable of at least twice full-load current. Avoid narrow connector
  escape necks; connect every physical VBUS/GND contact represented by J1.
- Retest startup into attached module capacitance, each output short, main VIN
  short, brownout/retry and hot-unplug. Check D1 clamp overshoot and the downstream
  buck VIN peak, since a 60 V eFuse input rating alone does not protect a 30 V buck.

The existing KiCad `D_SMC` footprint was checked against the manufacturer's
DO-214AB outline: body up to 7.75 x 6.10 mm, total length 8.51 mm, lead width up
to 3.15 mm. Its pad centres are +/-3.4 mm; each physical land is 2.5 x 3.3 mm,
covering the terminal extent with toe/heel allowance. Pad 1 is the banded cathode.
The footprint is pinned locally without stripping its model resource. This is
not a supplier placement-preview or solder-joint production qualification.

## Sourcing observation

Fresh public JLCPCB lookups during this change:

| Part | C-code | Observed stock | Qty-1 unit price | Classification / service |
| --- | --- | ---: | ---: | --- |
| TPS16630PWPR (retained) | C1849461 | 1,116 | $2.6926 | Extended / Economic |
| ZHIDE SS1060 (D10) | C2917888 | 3,143 | $0.1951 | Extended / Economic |
| 3.3k R5 | C22978 | 5,219,565 | see JSON | Basic / Economic |
| 1k R29 | C21190 | 31,314,129 | see JSON | Basic / Economic |

The eFuse still meets the requested **under-$3 IC unit price**. Fees/assembly,
shipping/tax and quantities are separate. Stock is not reserved. Exact retrieval
UTC, request URLs and raw-response hashes are retained in `s5-sourcing.json`;
unchanged components retain explicitly labelled S4 evidence, not newly claimed
live results. Four inherited electrolytics C5/C34/C35/C36 remain an unresolved
Basic-policy gate. There is no assembly release or order-ready claim.

## Verification and remaining gates

Native staged/final checks and evidence are retained in `research/s5-current/`:
ERC, XML/table/field/pad parity, S3 converter preservation, strict S4/S5 delta,
native save/reload, deterministic rebuild, BOM ref/quantity/MPN parity,
negative validation tests and PDF inspection. The intended S4 electrical delta
is exactly R5 changed, R29 added in series, and D10 value/package changed.

Shared schematic dependency inspection still fails on the pre-existing unresolved
`${KICAD10_3DMODEL_DIR}`. No dependency, ERC rule or exclusion was removed to hide
that failure. Native CLI checks are independent and do not clear it. No PCB DRC,
thermal, electrical/USB qualification or supplier preview is possible from the
schematic alone. Full F1/D1/J1 supplier-document and pulse/thermal qualification,
D10 delivered-revision confirmation and the existing converter-review items
remain open. No commit, upload or order was made.
