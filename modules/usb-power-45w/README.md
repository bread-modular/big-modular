> **S6 schematic + M1 mechanical concept (user-approved) + R1 steps 0-2. Authorization gate cleared; placement/routing next; no copper.**
> Root ERC 0; carrier DRC 0 violations, 0 warnings, 0 exclusions, parity 0; 493 unconnected (nothing placed).
> All components on F only (user, 2026-10-31); B copper for routing/thermal only. Only user-authorised
> edge allowances: J1 front S1 lugs and SW1 MP pads, 0.55 mm (`hardware/usb-power-45w.kicad_dru`),
> plus documented J1/SW1/D8/D16-D18 courtyard overhangs — see [R1 record](docs/r1-routing.md);
> [mechanical preview](docs/mechanical-preview.md) is historical (pre-repair).

# usb-power-45w

USB-C PD Eurorack supply with direct forced-PWM converters, independent output
protection and **common latched shutdown/reset**. The historical name is retained;
it does not promise 45 W output or a simultaneous 54.5 W rating.

- **Input:** verify a 20 V / 5 A contract and 5 A cable for full-load experiments.
  No automatic PD-current tracking. TPS16630 main limit remains 4.186 A nominal.
- **Positive rails:** the same TPS16630 IC on each output, 2.647 A nominal limits.
- **Negative rail:** LM5067 + external N-MOSFET and 50 mOhm sense network, 1 A nominal.
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

- [KiCad hierarchy root](hardware/usb-power-45w.kicad_sch)
- [Eight-page schematic PDF](docs/usb-power-45w-schematic.pdf)
- [Current design](docs/design.md)
- [S6 protection, LED behavior, sourcing and qualification](docs/s6-rail-protection.md)
- [Native BOM](docs/bom.csv) · [Sourcing snapshots](docs/s6-sourcing.json)
- [M1 mechanical preview](docs/mechanical-preview.md): 4HP panel
  `panels/front-pcb/usb-power-45w-panel.kicad_pcb`, unrouted carrier
  `hardware/usb-power-45w.kicad_pcb` (SMD parked off-board), brackets, 3D assembly

The root contains USB input, +12 buck/eFuse, +5 buck/eFuse, negative converter,
negative protection, common fault/reset control, and output/status subpages.
Do not open a child as an independent root to assess overall ERC/connectivity.

## Rebuild and check

Run from the repository root. Keep review outputs in the ignored `research/`
area; copy the module hardware dependencies into the candidate first.

```sh
python3 -B modules/usb-power-45w/tools/build_schematic.py --output-root <candidate-module-root>
kicad-cli sch erc --severity-all --exit-code-violations -o <erc-report> <candidate-module-root>/hardware/usb-power-45w.kicad_sch
kicad-cli sch export netlist --format kicadxml -o <netlist.xml> <candidate-module-root>/hardware/usb-power-45w.kicad_sch
python3 -B modules/usb-power-45w/tools/verify_design.py --netlist <netlist.xml> --hardware <candidate-module-root>/hardware
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
```

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
