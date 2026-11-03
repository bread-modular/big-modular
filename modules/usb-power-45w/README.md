# usb-power-45w

## Open this main project

| Open in KiCad | What it is |
| --- | --- |
| **[`hardware/usb-power-45w.kicad_pro`](hardware/usb-power-45w.kicad_pro)** | **Main project = the routed BASE board** (`usb-power-45w.kicad_{pcb,sch,dru}`: USB/PD, main eFuse, negative protection, latch/RESET, LEDs, J2 output) |
| [`hardware/usb-power-45w-top.kicad_pro`](hardware/usb-power-45w-top.kicad_pro) | The routed TOP board (`usb-power-45w-top.kicad_{pcb,sch}`: the three converters, +12/+5 eFuses, cans) |
| [`hardware/usb-power-45w-system.kicad_pro`](hardware/usb-power-45w-system.kicad_pro) | Whole-circuit S7 schematic (`usb-power-45w-system.kicad_sch` + pages `01`..`07`, 216 refs / 145 nets); schematic only, no PCB |
| [`hardware/single/usb-power-45w-single.kicad_pro`](hardware/single/usb-power-45w-single.kicad_pro) | **S9.3 / P2.3 single board, ±12 V only, unrouted**: **S9.3: starts from a strict 3.00 A source in one attempt** (FB-injection soft starts C84/D27/R116 on U2, τ 15 ms nominal, and C85/D28/R117 on U4, τ 47 ms; U4 enabled 3.4–18.3 ms after P12_OK via Q16/R118/C86/R119; peak input 2.955 A, 0 U5 drop-outs in all five source/capacitance cases); the ten S9.3 parts sit in interim free pockets. S9.2b: **enforceable DRC contract** (8 net classes, 22 `S92_*` rules in the `.kicad_dru`, 15 rule areas, 17-item post-routing screen) and **no via-in-pad, standard JLCPCB vias only** (0.3/0.6 mm, tented, unfilled): U4/U5/U9 on hole-free lands with beside-pad thermal-via fields of **10 / 10 / 6** vias (were 8 / 15 / 4 in the pads), spokes and B.Cu landing pours; thermal penalty **+5.3 °C** at rated load (U5 Tj 70.7 °C at 50 °C and 3 A, U2 unchanged at 94.1 °C / 108.4 °C), rating unchanged; **15 V / 3 A USB PD input** (13.5–16.5 V at the module; needs a 15 V / 3 A, ≥ 45 W source); **+12 V = TPS552892-Q1 four-switch buck-boost** with an 18 mΩ Kelvin-sensed constant-current limit (2.615–2.946 A); −12 V LMR38020 enabled only from its own VPD AND RUN AND MAIN_LED_OK; **D24 SMBJ20A coordinated with the U5 OVP** (R24 9.1k, 17.30–19.44 V); AGND_U2 joins PGND only through R113 at C82.2; S8.5 one-shot arming; U20 guards +12 V / −12 V; **no reverse blocking and no rail fuse/crowbar (accepted residuals)**. 185 refs / 84 nets; ERC 0, DRC 0 violations / 0 warnings / 411 routing opens, exact parity; P2.3 placement, all on F, 50 mm deep, no routing (copper beyond the pads: only the 26 thermal vias, 26 spokes and 3 landing pours). Published prototype rating **+12 V 2.4 A / −12 V 0.8 A, ≤ 33 W together**, conditional on the routing contract and the post-prototype acceptance tests. [Review package](docs/s8-single-board.md), [routing notes](docs/s8-single/routing-notes.md) |

> **S9.3 / P2.3** (2026-11-03): FB-injection soft starts on both converters and U4 sequenced after +12 V, so a strict
> 3.00 A source starts the module in one attempt (peak 2.955 A, zero U5 drop-outs, published 33 W with 0.44 mF per
> rail). Startup table and open items: [docs/s8-single-board.md](docs/s8-single-board.md#s93--p23-strict-3-a-start-2026-11-03).
> Not done yet: per-class width rules and pour-neck screening, the U2 sense-escape re-placement, the wording fixes.
>
> **S9.2 / P2.2: routing-ready** (changelog, verification and the list of acceptance tests in
> [docs/s8-single-board.md](docs/s8-single-board.md)). Routing-ready. The items in
> [`routing-notes.md`](docs/s8-single/routing-notes.md) are post-prototype acceptance tests, not design blockers:
> the test-point table, the uncertainty register and the routing constraint list the router must honour. S9.2 changes:
>
> - **D24 and OVP:** D24 SMBJ16A → **SMBJ20A** with the U5 OVP divider R24 6.8k → **9.1k**. The OVP trips at
>   17.30–19.44 V, before D24 conducts.
> - **PGND star:** C82.2 sits on **PGND**, and R113 is the sole AGND_U2 bridge.
> - **Kelvin shunt:** R109 is a TA-I RLM12 18 mΩ on a **true 4-terminal Kelvin land** (P12_ISP/P12_ISN).
> - **Tests:** the U4 enable truth table and the 3 A source timelines are **derived from the native netlist**, with
>   negative controls.
> - **Default:** **R115 100k** defines `N_EN_RETURN`.
> - **Thermal:** the rating is **conditional on the copper/via routing contract**.
> - **Test pads:** ten 1.5 mm acceptance pads were added.
> - **S9.2b:** the routing contract is now native DRC (net classes, `S92_*` rules, `RA_*` rule areas), and via-in-pad is
>   prohibited: U4/U5/U9 thermal vias moved beside their pads (standard 0.3/0.6 mm tented vias only), thermal penalty
>   +5.3 °C at rated load, rating unchanged ([routing-notes 3.12/3.13](docs/s8-single/routing-notes.md)).
>
> S9.1 (own-input U4 enable, VIN clamps, precision UVLO, AGND_U2) and S9.0 (+5 V removed, 15 V PD, TPS552892-Q1) are
> unchanged otherwise; their records are in git history.
>
> S9.3: native ERC 0 and exact ref/pin/net parity (185 refs / 84 nets). DRC: **0 violations, 0 warnings, 411 routing
> opens** (unrouted).
> The placement, local-loop, routing-contract and nominal 3D screens pass, and the module suite passes from a clean
> clone ([review-s93.json](docs/s8-single/review-s93.json)). The original S7/R3 designs below are unchanged.

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
