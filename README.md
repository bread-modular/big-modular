# Big Modular — PD-only power module / three-sheet circuit WIP

**INCOMPLETE / NON-OPERATIONAL / DO NOT FABRICATE OR CONNECT VALUABLE LOADS.**

This revision is a connected circuit proposal, not a working power module. Explicit 9 V PDO/current validation, input ESD/surge protection, four USB footprint clearances, rail-screw fit and the complete electrical PCB layout remain blocking. A1 WIP was merged into main; its merge does not imply fabrication approval. This review does not commit or merge.

## Deliverables

- `hardware/big_modular.kicad_sch`: **A4 navigation overview plus three A3 functional subsheets**: input/protection, power conversion, output rails. All 88 real components and their electrical connectivity are retained; local feedback/filter/protection branches now use visible wires.
- [`docs/schematic.pdf`](docs/schematic.pdf): **four navigable pages** (overview + three circuit pages), exported from the root hierarchy.
- [Sheet guide](docs/schematic-guide.md): page map, signal flow and manual-reading notes. [Component guide](docs/component-guide.md): what each main component/support network does, how and why. [Readability validation](reports/schematic-readability.md): unchanged connectivity and remaining check limitations.
- `hardware/big_modular.kicad_pcb`: perpendicular carrier, **J1 only** electrically; four mechanical NPTHs. J1 position, orientation and selected footprint are unchanged.
- `hardware/front_panel.kicad_pcb`: 9.8 × 128.5 × 1.6 mm FR4 panel. Rail holes corrected to **x=7.5, y=3/125.5, Ø3.2**. The old 5 mm slots cannot fit at x=7.5; ordinary screw heads and the 0.7 mm edge web remain mechanical blockers.
- [`docs/assembly.svg`](docs/assembly.svg) / [`assembly.pdf`](docs/assembly.pdf): original dimensioned FRONT/SIDE/TOP views, two machined right-angle interposers, screws, engagement, supports and harness envelope. See [`mechanics.md`](docs/mechanics.md).
- `BOM.csv`, `docs/pin-net-audit.json`, `reports/big_modular.net` and actual ERC/DRC/geometry reports. Historical A1 transition inventory (not the current worktree diff): `reports/deliverable-files.txt`.

**Both boards retain zero tracks, zero vias and zero zones.** Do not update either PCB from the schematic: connector-only electrical placement is intentional. These are not placement-complete, routable-by-assertion, operational or fabrication-ready boards.

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
parity is intentionally incomplete; do not synchronize or route either board to
make a generic check pass. Root `BOM.csv` is a design inventory, not the grouped
assembly BOM expected by the auditor. Optional routing controllers are included
**without runtimes**. Setup does not change hardware or establish release approval.

## Regeneration / checks

Installed engine used: KiCad 10.0.6. `tools/build_project.py` owns the circuit inventory; `tools/render_schematic.py` owns the three-subsheet hierarchy/layout; `tools/build_mechanics.py` owns the original assembly drawing. For schematic-only changes, generate a **new candidate** with pinned symbols; the unflagged legacy builder also regenerates both boards and is not appropriate for this workflow. No research download is needed to regenerate.

```sh
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

ERC cleanliness is not proof of function. DRC runs intentionally omit schematic parity/refill. The generated whole-net audit is not independent; the verifier additionally hardcodes 65 pin/net spot checks, traverses 20 wire/hierarchy interstage paths and 57 local wire paths, retains one documented named PRE_P continuation, and checks actual PCB geometry. A native before/after audit retains all 288 exported pin memberships, including no-connect/singleton nets. Private isolated ERC retains 68 pre-existing footprint-library configuration warnings; installed-environment ERC reports zero. No rules were suppressed. User rail continuous/peak targets are still required before any output rating can be designed.
