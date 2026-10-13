# Schematic guide — three functional subsheets

**Reading/layout revision only. The circuit remains an incomplete, non-operational proposal. Do not fabricate or connect valuable loads.** No component values, part numbers, pin assignments, no-connects, or PCB geometry were changed by this reorganization.

Open [the root schematic](../hardware/big_modular.kicad_sch) in the KiCad project, or read [the navigable schematic PDF](schematic.pdf). The root is an A4 overview; there are **three A3 circuit subsheets**, so the complete PDF has **four pages**, not four circuit blocks. The PDF's sheet boxes are hierarchical navigation links. In KiCad, enter a sheet from its box or the hierarchy navigator; return to the overview to follow the power connections.

## Page map

| PDF page | KiCad sheet | Main components | Purpose |
| --- | --- | --- | --- |
| 1 | `big_modular.kicad_sch` — Overview | Three sheet symbols; no duplicated components | Shows the full power flow and links to the three circuit pages. |
| 2 | [`01_input_protection.kicad_sch`](../hardware/01_input_protection.kicad_sch) — Input and protection | J1, F1, U1, U2, Q1, JP1; 22 real components | Requests USB PD power and gates the converter supply using PG, RUN and an independent voltage window. |
| 3 | [`02_power_conversion.kicad_sch`](../hardware/02_power_conversion.kicad_sch) — Power conversion | U3, U4, U5, L1–L4, D2/D3; 35 real components | Converts protected input power into the three preregulated supplies needed by the output LDOs. |
| 4 | [`03_output_rails.kicad_sch`](../hardware/03_output_rails.kicad_sch) — Output rails | U6, U7, U8, D4–D9, J2; 31 real components | Post-regulates the supplies, shows protection/bleed branches, and connects the three outputs to the off-board harness. |

The detailed **[component guide](component-guide.md)** explains what every main component and its supporting network does, how it works, why it is present, and what remains unverified. Existing [design review](design-review.md) and [test matrix](test-matrix.md) remain applicable.

## 01 — Input and protection

Read left to right along the upper power line:

```text
J1 USB-C -> F1 -> VBUS_FUSED -> U2 eFuse -> VPROT -> page 3
                    |
                    +-> R1 / C1 -> U1 CH224K negotiation housekeeping
```

The lower control path is drawn as a real wire chain:

```text
U1 PG (active low) -> R28 -> Q1 -> JP1 RUN -> U2 SHDN
                                      |
                              R30 defaults SHDN low
```

R4/R5 and R6/R7 are now visibly connected to U2's UVLO and OVP pins. R8 and C3 connect directly to ILIM and dVdT. Their returns use **RTN**, a separate eFuse control-reference net, not system GND. RUN cannot bypass the PG path or the UV/OV window.

**Boundary:** this sheet exports `VPROT` and shares `GND`. It does not export raw USB VBUS to the converter sheet. Five-volt VBUS is retained only for negotiation housekeeping. The intended input window is approximately 7.878–10.781 V on rising thresholds, not proof of a negotiated PD contract.

## 02 — Power conversion

The upper-left U3 buck makes `V4`, approximately 4.016 V. Its output sense, divider and PG pullup are wired directly. `MID_GOOD` visibly reaches both U4 enables.

The upper-right U4 section contains both energy paths:

```text
V4 -> L2 / U4 boost switch -> D2 -> PRE_P (about +13.95 V)
V4 -> U4 inverter switch / L3 -> D3 -> PRE_N (about -13.95 V)
```

Both feedback dividers, their feedforward capacitors, the analog supply filter, and compensation capacitors are drawn at the relevant pins. **R15 returns to U4 VREF (`BI_REF`), not GND**; the negative feedback connection is deliberately visible.

The lower-left U5 buck takes `PRE_P` and makes `PRE_5`, about 6.5 V, for the +5 V LDO. This one long-distance `PRE_P` continuation remains label-connected to avoid running a wire across the bipolar regulator's feedback network. The input label and the page description identify the source. Local U5 input capacitors, VOS and feedback divider are all directly wired.

**Boundary:** input `VPROT`; outputs `PRE_P`, `PRE_N`, `PRE_5`; shared `GND`. None of these preregulated rails goes directly to the Eurorack connector.

**Important qualification:** U3 PG is intended for normal startup sequencing, not a guaranteed shutdown/fault latch. It becomes high-impedance in shutdown/UVLO, so stored charge on V4 and brownout behavior require separate evaluation. U5's 6.52 V designation is the divider-selection target using 0.800 V; its 0.808 V typical internal reference predicts approximately 6.585 V before tolerances. See the component guide for sources and calculations.

## 03 — Output rails

The three horizontal rows deliberately use the same arrangement:

```text
preregulated input -> LDO -> final rail -> J2
       input capacitor   output capacitor / feedback / clamp / bleed
       NR/SS capacitor   feedforward capacitor
       <---- reverse-differential diode above the LDO ---->
```

- U6: `PRE_P` to `P12` (approximately +12 V).
- U7: `PRE_N` to `N12` (approximately -12 V). IN and EN are negative; GND and the exposed pad stay at 0 V.
- U8: `PRE_5` to `P5` (approximately +5 V).

Input/output decoupling, NR/SS capacitors, feedback dividers, feedforward capacitors, both diode functions and bleeders are visible wire branches. J2's left-hand supply pins are wired from the three rows; short rail-name continuations identify the matching right-hand pins without loops around the connector. J2 is **off-board**, not a newly placed PCB footprint.

| J2 pins | Net | Meaning |
| --- | --- | --- |
| 1, 2 | `N12` | -12 V; red-stripe end |
| 3–8 | `GND` | System return |
| 9, 10 | `P12` | +12 V |
| 11, 12 | `P5` | +5 V |
| 13–16 | No connect | CV/Gate unused |

This is the project's unchanged pin assignment, not certification of a cable's physical keying. Continuity-test the actual harness; never parallel this output with another supply.

## Drawing conventions and manual review

- **Wires and junction dots** show local connections. A crossing without a junction is not a connection. A net name on a wire helps identify it; it is not a substitute for the now-visible feedback/filter branches.
- **Hierarchical ports** carry signals between pages through real wires on the overview. Ground is shared through the same explicit hierarchy rather than hidden global signal labels.
- **Short GND/RTN labels**, remote housekeeping supply continuity, the U5 `PRE_P` continuation and the duplicated J2 pins remain named where wiring them across the page would add clutter.
- **PWR_FLAG symbols** are ERC source declarations only, not extra physical components. The real inventory stays at 88 components; D1 is absent, not fitted/DNP.
- All original real symbol UUIDs and references are retained. Local native net names acquire sheet-path prefixes; the before/after audit checks exact pin membership rather than pretending that the full namespace is unchanged.

Useful manual traces are U1 CFG1→R2, U2 UVLO→R4/R5→RTN, U4 FBN→R14/R15→VREF, U5 VOS→L4 output, and each LDO FB→divider/feedforward capacitor. The regression verifier also requires 57 local paths to remain wire-connected, plus 20 original interstage paths through wires/hierarchical ports and one explicitly documented named continuation.

## Regeneration without touching the boards

The full legacy builder also regenerates PCBs. **Do not run it without flags for a schematic-only task.** Use the new separate-candidate mode:

```sh
python3 -B tools/build_project.py --schematic-only --output research/new-schematic-candidate
kicad-cli sch erc research/new-schematic-candidate/big_modular.kicad_sch --severity-all
kicad-cli sch export pdf research/new-schematic-candidate/big_modular.kicad_sch --draw-hop-over -o research/new-schematic-candidate/schematic.pdf
```

The destination must not already exist. This mode uses pinned project symbols, copies only the necessary project/library context, and never imports the board-building section or rewrites the BOM/audit. Review and validate the candidate before copying its four schematic files into the workspace's `hardware/` directory.

For the delivered source, run the common private checker and the project regression suite as described in [the validation report](../reports/schematic-readability.md). Native ERC/netlist checks do not establish analog stability, PD contract authorization, output protection, thermal suitability, mechanical fit or manufacturing readiness. Both PCB files remain byte-for-byte unchanged and unrouted.
