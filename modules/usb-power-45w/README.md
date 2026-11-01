# usb-power-45w

## Open this main project

| Open in KiCad | What it is |
| --- | --- |
| **[`hardware/usb-power-45w.kicad_pro`](hardware/usb-power-45w.kicad_pro)** | **Main project = the routed BASE board** (`usb-power-45w.kicad_{pcb,sch,dru}`: USB/PD, main eFuse, negative protection, latch/RESET, LEDs, J2 output) |
| [`hardware/usb-power-45w-top.kicad_pro`](hardware/usb-power-45w-top.kicad_pro) | The routed TOP board (`usb-power-45w-top.kicad_{pcb,sch}`: the three converters, +12/+5 eFuses, cans) |
| [`hardware/usb-power-45w-system.kicad_pro`](hardware/usb-power-45w-system.kicad_pro) | Whole-circuit S7 schematic (`usb-power-45w-system.kicad_sch` + pages `01`..`07`, 216 refs / 145 nets); schematic only, no PCB |
| [`hardware/single/usb-power-45w-single.kicad_pro`](hardware/single/usb-power-45w-single.kicad_pro) | **S8 single board** (2026-11-01): **S8.2 schematic** (no per-rail eFuses, no rail LEDs, MAIN LED only, ceramic bulk, two IDC outputs J2 + J3, overvoltage guard with its own TLV431B reference + MON_OVN clamp after the external review, +5V SCR crowbar; 182 refs / 82 nets, ERC 0) + **P1.2 trial placement**, 100.5 x 48 mm (50 mm deep), every part on F, not routed (DRC 0 / parity 0). Panel `panels/front-pcb/usb-power-45w-single-panel.kicad_pcb`. Review package: [S8 record](docs/s8-single-board.md) |

> **S8 (2026-11-01): single board, final schematic + P1 trial placement (review package).** The three
> rail eFuses (U6/U7 and the LM5067 negative switch) and every rail LED are removed; U5 is the only switch
> and the fault latch still turns every rail off until RESET, so D8 MAIN (the only LED) off = not working.
> The four cans become ceramics (VIN: 1 ohm + 2 x 10u damper; rails: 22u at each header); two parallel
> 16-pin outputs J2 + J3; overvoltage guard (+12/+5/-12) on the latch preset plus a TVS on +5V. The board
> is 50 mm deep (Z2..50), all 171 parts placed on the F side, 64 % courtyard fill, not routed; brackets,
> panel and a 3D assembly (STEP, renders, collision screen: 0 overlaps) are in
> [docs/s8-single-board.md](docs/s8-single-board.md) with the points for the reviewer. Parts ~$19.32 vs
> $27.12. The S7 schematic and the routed R3 stack below are unchanged.
>
> **S8.1 (2026-11-01, external review fixes):** the guard has its own reference (U21 TLV431B, R100, C67,
> TP17), LM2901B comparators and 0.1 % dividers: trips +12V 14.88 V (14.48-15.27), +5V 5.83 V (5.68-5.98),
> -12V -13.64 V (13.27-14.02) instead of 16.6 / 6.5 / 15.1 V; the -12V sense no longer uses V3V3 and D22
> clamps it at GND. A shorted converter high side can still lift +5V into D21's clamp range (6.4-7 V breakdown, more at amps) when the rack holds
> less than ~0.6 mF on +5V; S8.2 adds the crowbar below. See the S8.1 section of the record.
>
> **S8.2 (2026-11-01, user: "Do that"): +5V crowbar.** Q11 (TS1220 SCR, DPAK) across +5V, fired by its own
> trigger powered by +5V itself (U22 TLVH432B, 0.1 % 37k/10k divider, Q12 gate driver): +5V above 5.83 V
> (5.70-5.98 V over all corners) shorts the rail, and Q13 pulls OV_N low at the same time so the fault latch
> opens U5. In the shorted-high-side screen +5V spends ~8 us above 6 V instead of 29-65 us; D21 still sets
> the 8-10 V peak of those first microseconds. Board P1.2: Q11 in the free front-right corner, 182 parts,
> 67 % fill, DRC 0, 3D screen 0 overlaps. Parts ~$21.50 (+$2.18; TS1220 and TLVH432B are new Extended codes).
> The SCR's dI/dt in the bank discharge exceeds its rating in the screen: survival is a bench gate.

Each board project has its own matching flat schematic (its share of S7 + the board-to-board
headers XB*/XT*); `tools/check_stack.py` proves base + top joined through the headers equals the
system schematic. The three projects share `hardware/sym-lib-table`, `fp-lib-table`,
`USBPOWER45.kicad_sym` and `USBPOWER45.pretty`. Moved 2026-11-01 from `hardware/base/` and
`hardware/top/`: PCBs, schematics and rules byte-identical (BASE `b5f4e6b2...`, TOP `922d34ab...`),
only the BASE `.kicad_pro` file/sheet-name record follows the new name; the old S7 root
`usb-power-45w.kicad_sch` is now `usb-power-45w-system.kicad_sch` (same bytes) and the superseded
monolithic R1 carrier is [archived](archive/r1-monolithic/README.md). Older records below keep the old paths as history.

> **R3 routing finished (2026-11-01): S7 schematic + two canonical stacked boards (BASE = the main
> project above, TOP beside it), both fully routed.** ERC 0 (root, base, top); DRC 0 violations / 0 warnings /
> 0 exclusions / parity 0 and **0 unconnected on both boards**; aggregate base+top netlist == S7
> netlist (216 refs, 145 nets); support annuli, 9 unit tests and check_stack clean. BASE SHA-256
> `b5f4e6b2...`, TOP `922d34ab...`. Prototype routing checkpoint, **not factory-ready**: no fab
> export, no 45 W rating, header height/current, thermal bench and fab gates open. Records:
> [BASE final](docs/r3-base/final/README.md), [TOP](docs/r3-top/README.md), [R2 stack](docs/stack-r2.md).
> The monolithic carrier (now `archive/r1-monolithic/usb-power-45w-r1-monolithic.kicad_pcb`) and the
> R1 notes are **superseded** history (it still carries J3); the [fit study](docs/stacked-fit-study/README.md) is historical.

USB-C PD Eurorack supply with direct forced-PWM converters, independent output
protection and **common latched shutdown/reset**. The historical name is retained;
it does not promise 45 W output or a simultaneous 54.5 W rating.

- **Input:** verify a 20 V / 5 A contract and 5 A cable for full-load experiments.
  No automatic PD-current tracking. TPS16630 main limit remains 4.186 A nominal.
- **Positive rails:** the same TPS16630 IC on each output, 2.647 A nominal limits.
- **Negative rail:** LM5067 + external N-MOSFET and 50 mOhm sense network, 1 A nominal.
- **Output:** one protected 16-pin header J2 (S7 removed the parallel J3); a passive expander/cable
  comes later. One cable/contact pair per rail limits the usable load.
- **Faults:** after startup qualification, a persistent fault disables all rails
  until RESET/power cycle. Internal current protection also operates during startup.
- **Panel:** D8 MAIN plus three new LEDs: D16 +12, D17 +5, D18 -12. Each rail lamp
  follows its protected output/status. All four turn off on common latched shutdown.
- **Readability:** wired overview and seven functional subpages, following the
  existing `usb-power` module's style. Power, feedback, protection, timing and LED
  paths are connected; distributed power/control interfaces remain named.
- **Limits:** current settings have tolerances and can trip below old rail targets.
  Startup qualification is about 5.7 s typical; output ramps are not simultaneous.
  RESET disconnects, but does not actively discharge arbitrary rack capacitors.

## Open / read

- [KiCad hierarchy root (S7, whole system)](hardware/usb-power-45w-system.kicad_sch)
- **Boards:** [BASE = main](hardware/usb-power-45w.kicad_pcb), [TOP](hardware/usb-power-45w-top.kicad_pcb) (native per-board schematics beside them), [R2 record](docs/stack-r2.md)
- [Eight-page schematic PDF](docs/usb-power-45w-schematic.pdf)
- [Current design](docs/design.md)
- [S6 protection, LED behavior, sourcing and qualification](docs/s6-rail-protection.md)
- [Native BOM](docs/bom.csv) · [Sourcing snapshots](docs/s6-sourcing.json)
- [M1 mechanical preview](docs/mechanical-preview.md): 4HP panel
  `panels/front-pcb/usb-power-45w-panel.kicad_pcb`, unrouted carrier (archived:
  `archive/r1-monolithic/usb-power-45w-r1-monolithic.kicad_pcb`, SMD parked off-board), brackets, 3D assembly

The root contains USB input, +12 buck/eFuse, +5 buck/eFuse, negative converter,
negative protection, common fault/reset control, and output/status subpages.
Do not open a child as an independent root to assess overall ERC/connectivity.

## Rebuild and check

Run from the repository root. Keep review outputs in the ignored `research/`
area; copy the module hardware dependencies into the candidate first.

```sh
python3 -B modules/usb-power-45w/tools/build_schematic.py --output-root <candidate-module-root>
kicad-cli sch erc --severity-all --exit-code-violations -o <erc-report> <candidate-module-root>/hardware/usb-power-45w-system.kicad_sch
kicad-cli sch export netlist --format kicadxml -o <netlist.xml> <candidate-module-root>/hardware/usb-power-45w-system.kicad_sch
python3 -B modules/usb-power-45w/tools/verify_design.py --netlist <netlist.xml> --hardware <candidate-module-root>/hardware
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project.json --reports <new-dir>      # BASE (main)
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project-top.json --reports <new-dir>  # TOP
python3 -B modules/usb-power-45w/tools/check_stack.py --scratch modules/usb-power-45w/research/<new-dir>
```

`build_schematic.py` writes only the system schematic (`usb-power-45w-system.kicad_sch` + pages);
`board_schematics.py` writes the two board schematics. Board copper is owned by the native PCBs:
the seed (`build_stack.py`) refuses routed boards, and the old placement/route replays
(`stack_place.py apply`, `route_*.py apply`) and the R1 carrier writers (`build_layout.py`
carrier, `pcb45.save`) refuse to write.

The generator verifies a flat intermediate, builds the hierarchy and verifies
exact component/field/pin-membership preservation. `protection6.py` owns the added
circuit; `hierarchy6.py` owns page groups and explicit schematic connections.
`verify_design.py` checks the native result and a settled digital logic model;
it is not an analog simulator or a manufacturing signoff.

## Remaining gates

- **TPS3808 pin map corrected 2026-10-31** (U10/U11 MR = pin 3, SENSE = pin 5, per
  TI SBVS050N; [record](docs/s6-rail-protection.md#tps3808-pin-map-correction-2026-10-31)).
  A new independent full schematic review is still required before any PCB work.
- Thermal, startup with real rack capacitance/load, overload/short, reset,
  reverse-collapse/backfeed, pin-voltage transients, noise and loop validation.
- Exact manufacturing footprint/assembly review and inherited supplier-document gates.
- Four inherited electrolytics remain Extended, not Basic; no sourcing-policy waiver.
- LM5067 negative controller: only 33 units observed, about $3.08 at quantity 1.
  Main/positive TPS16630 remain under $3 each. S6 adds about $14.86 in sourced parts
  on a quantity-1 comparison, before manual parts, assembly/setup or shipping.
- M1 mechanical preview only: no routing, manufacturing release or vendor order.
- R1: [placement/routing record](docs/r1-routing.md) (steps 0-2 done; J1/SW1 allowances applied, authorization gate cleared, placement/routing next, no copper).

S4/S5 change records and sourcing files remain as clearly superseded history.
