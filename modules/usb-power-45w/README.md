# usb-power-45w

## Open this main project

| Open in KiCad | What it is |
| --- | --- |
| **[`hardware/usb-power-45w.kicad_pro`](hardware/usb-power-45w.kicad_pro)** | **Main project = the routed BASE board** (`usb-power-45w.kicad_{pcb,sch,dru}`: USB/PD, main eFuse, negative protection, latch/RESET, LEDs, J2 output) |
| [`hardware/usb-power-45w-top.kicad_pro`](hardware/usb-power-45w-top.kicad_pro) | The routed TOP board (`usb-power-45w-top.kicad_{pcb,sch}`: the three converters, +12/+5 eFuses, cans) |
| [`hardware/usb-power-45w-system.kicad_pro`](hardware/usb-power-45w-system.kicad_pro) | Whole-circuit S7 schematic (`usb-power-45w-system.kicad_sch` + pages `01`..`07`, 216 refs / 145 nets); schematic only, no PCB |
| [`hardware/single/usb-power-45w-single.kicad_pro`](hardware/single/usb-power-45w-single.kicad_pro) | **S9.0 single board, ±12 V only**: +5 V subsystem removed; **15 V USB PD input** (13.5–16.5 V; needs a 15 V / 3 A, ≥ 45 W source); **+12 V = TPS552892-Q1 four-switch buck-boost** (the S8 TPS62933F buck cannot regulate at 15 V: 0.995–1.053 duty vs 98 %); −12 V LMR38020 unchanged; S8.5 one-shot arming kept, `ANY_BAD` without `P5_OK`; U20 guards +12 V / −12 V; **no reverse blocking and no rail fuse/crowbar (accepted residuals, bench-test conditions in the review)**. 156 refs / 74 nets; P2.0 fit placement, all on F, 50 mm deep, **unrouted**. Published prototype rating **+12 V 2.4 A / −12 V 0.8 A, ≤ 33 W together**. [Review package](docs/s8-single-board.md) |

> **S9.0 development review** (major revision of the single board; changelog and accepted residuals in
> [docs/s8-single-board.md](docs/s8-single-board.md)): the **+5 V subsystem is removed** (U3, U23 and every
> +5 V-only part; J2/J3 pins 11/12 open), the input moves to **15 V USB PD** (R1 56k, U5 UVLO R3 10k:
> on 12.46–13.98 V, off 11.55–13.13 V; `V20_OK` R83 100k: 7.67–9.27 V), and the +12 V stage becomes a
> **TPS552892-Q1 four-switch buck-boost** (966 kHz, L1 6.8 µH, R109 15 mΩ constant-current limit
> 3.14–3.53 A) because the TPS62933F buck would need 0.995–1.053 duty at the 12.5 V low-line converter
> input (1.033 even unloaded) against its 98 % maximum; the buck-boost regulates from the 10.55 V U5 sag
> to 21 V. The S8.5 one-shot arming (`STARTED`, `ARMED`) is kept; `ANY_BAD = NOT(MAIN_LED_OK AND P12_OK AND
> N12_OK)`; the timelines pass at the 15 V source corners. **Owner decisions:** no reverse-current
> blocking and no voltage-triggered rail fuse/crowbar — both are **accepted residuals** with bench-test
> conditions and a downstream-qualification requirement; **never plug an unpowered or latched-off
> module into a live bus** (a live bus can enable and power the −12 V converter and pump VIN; a
> non-blocking mitigation is an open decision). Crowbar vs eFuse stays deferred/open. Published
> prototype rating **+12 V 2.4 A, −12 V 0.8 A, ≤ 33 W together** (3 A contract at 13.5 V); moving back
> to 20 V is a three-resistor change (R1, R3, R83). Panel label PD 15V.
>
> Native ERC 0, exact ref/pin/net parity; DRC **0 violations, 365 routing opens** (unrouted); placement,
> local-loop and nominal 3D screens pass; the module suite passes from a clean clone
> ([review-s90.json](docs/s8-single/review-s90.json)). Routing, the buck-boost loop with the real rack,
> thermal and every bench gate remain open. The original S7/R3 designs below are unchanged.

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
