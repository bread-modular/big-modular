# usb-power-45w

USB-C PD Eurorack supply, ±12 V only, on one 4-layer carrier behind a 4HP panel.

> **S9.3-10P / R1: routed, first-prototype fab export in [`jlcpcb/`](jlcpcb/README.md) (2026-11-06).** Not a
> supplier-accepted release and not bench-qualified. The copper/thermal screen (`tools/check_s8_board.py`) still lists
> contract items; each was reviewed and accepted for the first prototype ([fab review](docs/routing/README.md)).

## Open

| Open in KiCad | What it is |
| --- | --- |
| **[`hardware/usb-power-45w.kicad_pro`](hardware/usb-power-45w.kicad_pro)** | The module: schematic (`usb-power-45w.kicad_sch` + pages `01`..`05`) and the routed 4-layer PCB (`usb-power-45w.kicad_{pcb,dru}`) |
| [`panels/front-pcb/usb-power-45w-panel.kicad_pro`](panels/front-pcb/usb-power-45w-panel.kicad_pro) | 4HP FR4 front panel (USB-C aperture, MAIN LED, RESET, rail and bracket holes) |
| [`panels/bracket/`](panels/bracket/) | The two M3 L brackets (STEP/STL/FreeCAD) |

## Circuit

- **Input:** USB-C PD **15 V / 3 A** (CH224A, R1 56k). U5 TPS16630 main eFuse; precision UVLO (on 12.263–12.976 V,
  off 11.365–12.193 V) and OVP (R24 9.1k: 17.30–19.44 V) coordinated with the D24 SMBJ20A clamp.
- **+12 V:** TPS552892-Q1 buck-boost (U2), R109 18 mΩ RLM12 current sense on a 4-terminal Kelvin land.
- **−12 V:** LMR38020 inverting converter (U4) on its own input enable (Q1 on VPD, RUN and MAIN_LED_OK via Q14/Q15),
  sequenced after +12 V (Q16 gate = P12_OK via R118/C86).
- **Strict 3 A start (S9.3):** FB-injection soft starts on both converters (C84/D27/R116 on U2, τ 15 ms nominal;
  C85/D28/R117 on U4, τ 47 ms). Netlist plant: peak input 2.955 A, zero U5 drop-outs in all five cases.
- **Faults:** one-shot `STARTED` arming, always-on latch and RESET button; D8 MAIN is the only panel LED.
- **Output:** two 10-pin shrouded IDC headers J2/J3 (Wurth 61201021621; pins 1/2 −12 V, 3–8 GND, 9/10 +12 V).
  No series reverse blocking (owner decision).
- **Prototype targets:** +12 V 2.4 A / −12 V 0.8 A, ≤ 33 W combined, conditional on the routing contract and the
  post-prototype acceptance tests.

## Status

- Native ERC 0; DRC **0 violations, 0 warnings, 0 exclusions, 0 unconnected**; exact ref/pin/net parity
  (185 refs / 84 nets). Manual divide-and-conquer routing, In1 one-piece GND plane, two approved In2 hops.
- Routing contract enforced by native DRC: 8 net classes, 22 `S92_*` rules, 15 rule areas. **No via-in-pad**:
  U4/U5/U9 sit on hole-free lands with thermal-via fields beside the pads (standard 0.3/0.6 mm tented vias).
- All parts on F; test points on B with silkscreen labels. JLCPCB places 155 parts on the top (J1 included);
  J2/J3 (Wurth 61201021621) and D8 (3 mm LED) are hand-fitted.
- **Fab review (2026-11-06):** fixed the two DRC errors left by a KiCad 10 *Update PCB from Schematic* (the SW1
  case-pad link), added a third +12V output via at R109, a third D1 TVS ground via and a U2 PGND via, and moved
  J2/J3/D8 out of the CPL so J1 is machine-placed. D1 SMBJ22A was re-sourced to Littelfuse C224015 (1,947 in stock;
  RUILON C10214 had 59). Export: [`jlcpcb/`](jlcpcb/README.md).
- **Accepted for the first prototype, still listed by `check_s8_board.py`:** minimum widths (taps and short stubs
  only), U2/R109/D10 thermal copper (TH-1/TH-2 measure it), U12.14→C52.1 7.63 mm, D25↔D24 9.04 mm, TP22/TP23 pair
  8.25 mm, R116.1 pad edge inside RA_AGND_ISLAND; see the [fab review](docs/routing/README.md). The items in
  [routing-notes.md](docs/design/routing-notes.md) (test points, uncertainty register, routing constraints) are
  post-prototype acceptance tests, not design blockers.

## Read

- [Design and changelog](docs/design.md)
- [Manufacturing export](jlcpcb/README.md) · [Fab review and routing checkpoint](docs/routing/README.md) · [Routing log](docs/routing/continuation-238.md) · [Routing notes](docs/design/routing-notes.md)
- [Schematic PDF](docs/usb-power-45w-schematic.pdf) · [BOM](docs/design/bom.csv) · [Sourcing](docs/design/sourcing.json)
- [Calculations](docs/design/calcs.json) · [Validation](docs/design/validation.json) · [Review record](docs/design/review-s93.json)
- [Assembly PDF](docs/design/assembly/usb-power-45w-placement.pdf) · [STEP](docs/design/assembly/usb-power-45w-assembly.step.zip)
- [Capacitor study](docs/capacitor-study/README.md)

## Rebuild and check

Run from the repository root; raw reports go in the ignored `research/`. The full sequence is in
[docs/design.md](docs/design.md#reproducibility).

```sh
python3 -B modules/usb-power-45w/tools/build_s8.py --output-root <candidate-module-root>
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project.json --reports <new-dir>
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
```
