## Electrical prototype checkpoint (current)

The authorized electrical update supersedes the earlier unchanged-circuit checkpoint below.
See `docs/electrical-prototype.md`: new 7-child hierarchy, direct rails, always-on MCU diagnostics.
PCB mechanics/routing remain unchanged; no full schematic-PCB sync. Main power-up is blocked.

# Big Modular — PD-only power module / A4.2 two-board placement WIP

**INCOMPLETE / NON-OPERATIONAL / DO NOT FABRICATE OR CONNECT VALUABLE LOADS.**

This revision is a connected circuit proposal, not a working power module. Explicit 9 V PDO/current validation, input ESD/surge protection, four USB footprint clearances, exact mechanical hardware/actuator selection and the complete electrical PCB layout remain blocking. The A4.2 panel uses simple off-centre round rail holes on the common fixed-strip grid phase; sliding nuts are no longer required. A1 WIP was merged into main; its merge does not imply fabrication approval. This review does not commit or merge.

## Selected reset — restored SMT version

**E-Switch TL3340AF160QG** is restored to the active board with the earlier
hand-solder footprint and matching panel hole. The **2HP panel, 30 mm main-board
depth and plain M3 L brackets are retained**. D10/D11/D12 are manual red 3mm through-hole LEDs; R32 axial is retired.
The [TS-1166VW footprint](docs/ts1166-switch.md) is a retired, uninstalled
alternative; its fit blocker no longer holds up the selected SMT arrangement.
Physical fit/soldering and electrical reset integration still need validation.

## Deliverables

- `hardware/big_modular.kicad_sch`: **A4 navigation overview plus three A3 functional subsheets**: input/protection, power conversion, output rails. All 88 real components and their electrical connectivity are retained; local feedback/filter/protection branches now use visible wires.
- [`docs/schematic.pdf`](docs/schematic.pdf): **four navigable pages** (overview + three circuit pages), exported from the root hierarchy.
- [Sheet guide](docs/schematic-guide.md): page map, signal flow and manual-reading notes. [Component guide](docs/component-guide.md): what each main component/support network does, how and why. [Readability validation](reports/schematic-readability.md): unchanged connectivity and remaining check limitations.
- `hardware/big_modular.kicad_pcb`: **one perpendicular main PCB, 100.5 × 30 mm**. USB, three red 3mm formed-lead LEDs and the right-angle reset switch are here. LED resistors await the electrical brief (Basic SMD preferred). The native USB footprint is unchanged; its assembly plane moves right for M3 screw-head clearance.
- `hardware/front_panel.kicad_pcb`: **2HP, 9.8 × 128.5 × 1.6 mm**, corner rail holes, two M3 bracket holes, USB/LED/reset openings. No middle PCB or board-to-board UI headers remain.
- [Assembly drawing](docs/assembly.pdf) and [M3 bracket dimensions](docs/m3-brackets.pdf): **two identical plain L brackets, 9.2 × 10 × 18.4 mm, 3 mm walls**, M3×8 front screws, M3×8 90° countersunk side screws, four plain M3 nuts. No captive pockets or inserts. Loose nuts are held from the side; countersink only the printed bracket. Service out of rack; ABS fit trial required.
- `hardware/mechanics/corner_braces.scad`: print-prototype source for two identical parts; no tested STL/structural qualification. The previous 10mm spacers and M2 side bolts are no longer used.
- **SW1 TL3340AF160QG is SMT**, with three exposed signal lands, two solder anchors and two NPTH locator holes. Fine-tip component-side hand soldering is intended; trial a sample. D10/D11/D12 remain manual THT; R32 axial is retired. Reset is recessed behind a Ø3.2 hole at X6.4/Y91; no printed plunger or light pipe selected.
- **Eurorack output:** J7 numbered solder lands and strain-relief holes feed the existing off-board **J2 keyed male 16-pin IDC on a short flying lead**. No bulky PCB box header is falsely fitted inside 2HP. Use a full 16-to-16 female IDC cable for ±12V/GND/+5V. **OUTPUT ONLY: never parallel another powered rack PSU.**
- [Mechanical guide](docs/mechanics.md), [switch/connector/cable buying links](docs/parts-buying-guide.md), [manual placement inventory](docs/interface-placement.csv).
- [A4.2 validation](reports/stack-validation.md), original source-preservation hashes, current native reports in `reports/stack-a4-2-native/`. Prior A3 boards/drawings are retained in `docs/archive/a3-stack-superseded.zip`; earlier native reports remain historical.

**Both active boards retain zero tracks, vias and zones.** The existing circuit files and root BOM are not modified by this mechanical LED checkpoint. D10/D11/D12/SW1/J7 are PCB-only reservations needing deliberate
schematic integration. LED/reset nets are isolated; all converter circuitry is
still unplaced. Rear PCB edge is **30.4 mm behind the panel rear**, not a finished
module/cable depth. No fabrication or power-up approval.

## LED3 staged checkpoint

Three manual red 3mm LEDs now have matching Ø3.6 panel holes at X6.7,
Y38/46/54 (+12/−12/+5). Pads are 2.54 pitch, Ø0.9 PTH with K/A marks.
No holder or 5mm substitution; actual LED MPN/formed-lead fit remains unqualified.
R32 axial is removed; no guessed resistor/driver circuit is installed.
[Checkpoint evidence and pending electrical requirements](reports/led-mechanics-checkpoint.md).
The circuit below is the **unchanged baseline**, not the requested future topology;
CH224A/controller/converter changes await Sol’s electrical brief.

## Circuit and power permission

```
USB-C -> fuse -> TPS26600 HARD GATE -> TPS62160 4.016 V
                ^                       -> TPS65131 +/-13.95 V
 CH224K PG -> Q1 -> RUN                    -> +/-12 V LDOs
                AND UV/OV window           -> TPS62125 ~+6.5 V -> +5 V LDO
                                                               -> off-board 16-pin J2
```

CH224K requests 9 V with CFG1=6.8k; CFG2/3 float. Its DP/DM are shorted locally and isolated from USB data, selecting PD-only protocol use. **5 V VBUS is retained only for negotiation housekeeping; there is no 5 V-input rail-output mode.**

- R4/R5 now set nominal UV rising **7.878 V**; OVP remains **10.781 V**. Hardware rejects 5 V even with RUN closed and PG asserted; sustained 15/20 V is outside the window.
- Active-low PG drives PNP Q1, which supplies SHDN through **series** JP1 RUN. R30 pulls SHDN low by default. RUN cannot bypass the PG gate or window. R31 bleeds off-state VPROT leakage. All converter bulk is downstream of the eFuse; upstream C1/C2 are housekeeping bypass only.
- **PG + voltage qualification is NOT proven explicit-PD-contract/current qualification.** WCH's generic PG specification does not attest a 9 V fixed PDO or sufficient negotiated current. Under a compliant-source assumption this is a useful hard interlock, but the strict contract-qualified requirement remains an explicit fabrication blocker. A 9 V DC reading alone is insufficient; no cryptographic authentication is claimed.
- No loads until independent PD analysis verifies a fixed 9 V contract with at least 0.5 A authorization and the outstanding design blockers are cleared. Only provisional simultaneous **~40 mA on each rail** is proposed for initial tests; no continuous/peak output rating exists.

The eFuse setting is 0.2985 A **nominal**, not a guaranteed input bound at this low setting and not a rail rating. About 1.16 W output and 2.26 W converter input at the provisional loads are estimates; housekeeping/inrush and thermal margins are unverified. +5 V shares the positive boost budget. Approximately ±13.95/+6.5 V preregulation is retained, subject to dropout, ripple, stability and actual-part checks. U5's 6.52 V divider-selection target uses 0.800 V; its 0.808 V typical reference predicts about 6.585 V. U3 PG sequences normal startup but is high-impedance in shutdown/UVLO, not a guaranteed fault latch; see the component guide.

## Precedent, differences and limitations

Andreas Dorfner's **Powerline USB-C** is a published **3HP / 20 V** PD Eurorack design, licensed CERN-OHL-P v2. Its schematic leaves CH224K PG unconnected and feeds regulator VINs directly from VBUS; that startup approach was **not copied**. We use its front-entry/two-support-point assembly idea as a reference only, retain our perpendicular 2HP geometry, and add a PG/window gate. No third-party CAD/artwork/datasheets are delivered. This is not a claim that the 3HP design proves our 2HP fit or performance. [source](https://github.com/Andreas-Dorfner/Powerline-USB-C) [source](https://github.com/Andreas-Dorfner/Powerline-USB-C/blob/main/LICENSE.md)

The unsafe D1 TVS stays absent: there is **no qualified VBUS/CC ESD or hot-plug surge solution**. No output precision OVP, all-rail fault latch, tracking, guaranteed discharge, thermal/EMI qualification or plug/cable fit certification exists. TPS62125 PFM/up-to-1MHz operation still does not meet an always-MHz requirement. See `docs/design-review.md` and `docs/test-matrix.md`.

## Shared KiCad tools and part sourcing

Use the local [portable KiCad toolkit](opt/kicad-tools/README.md) first for native
checks, candidate edits, exports, catalog lookup, BOM audits and passive sourcing.
It was copied independently from Bread Modular; no source checkout is needed at
runtime. [Project workflow and safety rules](Code.md) are also linked from
[AGENTS.md](AGENTS.md), and both workflow/sourcing skills are discoverable under
`.agents/skills/`.

```sh
python3 -B opt/kicad-tools/kicad_tools.py --help
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B opt/kicad-tools/kicad_tools.py assembly --help
python3 -B -m unittest discover -s tests -v
```

See [setup, provenance and exact sourcing/check commands](docs/kicad-tooling.md).
The explicit profile selects the carrier, not the mechanical panel. Full PCB
parity is intentionally incomplete; do not synchronize or route any board to
make a generic check pass. Use the A4.2 mechanical candidate builder only for an explicitly scoped placement change. Root `BOM.csv` is a design inventory, not the grouped
assembly BOM expected by the auditor. Optional routing controllers are included
**without runtimes**. Setup does not change hardware or establish release approval.

## Regeneration / checks

Installed engine used: KiCad 10.0.6. `tools/build_project.py` owns the circuit inventory; `tools/render_schematic.py` owns the three-subsheet hierarchy/layout; `tools/stack_geometry.py` and `tools/build_stack.py` own the A4.2 placement contract/candidate; `tools/build_mechanics.py` owns the original assembly drawing. Generate **new candidates** and validate before copying reviewed deliverables. The unflagged legacy full builder is disabled so it cannot restore the old deep boards. No research download is needed to regenerate.

```sh
# Mechanical/placement work (does not touch schematics or root BOM):
/usr/bin/python3 -B tools/build_stack.py --output research/new-stack-candidate
python3 -B tools/build_mechanics.py --output research/new-assembly-candidate
/usr/bin/python3 -B tools/verify_stack.py --hardware research/new-stack-candidate/hardware --geometry research/new-stack-candidate/assembly-geometry.json
# Review candidate drawings/native DRC, then copy only approved outputs.
# Separately, for schematic-only work:
python3 -B tools/build_project.py --schematic-only --output research/new-schematic-candidate
# Review/validate the candidate, then copy only its four schematic files into hardware/.
# The remaining commands validate/export the delivered hardware/ hierarchy.
kicad-cli sch erc hardware/big_modular.kicad_sch --severity-all -o reports/erc.rpt
kicad-cli sch erc hardware/big_modular.kicad_sch --severity-all --format json -o reports/erc.json
kicad-cli sch export pdf hardware/big_modular.kicad_sch --draw-hop-over -o docs/schematic.pdf
kicad-cli sch export netlist hardware/big_modular.kicad_sch -o reports/big_modular.net
kicad-cli pcb drc hardware/big_modular.kicad_pcb --severity-all --format json -o reports/carrier-drc.json
kicad-cli pcb drc hardware/front_panel.kicad_pcb --severity-all --format json -o reports/panel-drc.json
/usr/bin/python3 tools/verify_project.py
pdfinfo docs/schematic.pdf
git diff --check
```

ERC cleanliness is not proof of function. The separate per-board DRC reports omit schematic parity/refill; the A4.2 common-tool private check additionally retains full carrier schematic parity and refill-in-memory findings. The generated whole-net audit is not independent; the verifier additionally hardcodes 65 pin/net spot checks, traverses 20 wire/hierarchy interstage paths and 57 local wire paths, retains one documented named PRE_P continuation, and checks actual PCB geometry including twelve mechanical NPTHs, five switch SMT lands plus two NPTH locator holes, sixteen output landing pins and two M3 bracket/tool envelopes with obstruction-negative tests. A native before/after audit retains all 288 exported pin memberships, including no-connect/singleton nets. Private isolated ERC retains 68 pre-existing footprint-library configuration warnings; installed-environment ERC reports zero. No rules were suppressed. User rail continuous/peak targets are still required before any output rating can be designed.
