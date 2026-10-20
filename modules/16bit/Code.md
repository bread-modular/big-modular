# 16bit contract (S3 schematic, S5 placement, R1 routed)

| | |
|---|---|
| KiCad project | `hardware/16bit.kicad_{pro,sch,pcb}` |
| Panel | `panels/front-pcb/16bit-panel.kicad_{pro,pcb}` (FR4, NPTH only) |
| Generators, profile | `tools/` (`build_schematic.py`, `build_layout.py`, `import_footprints.py`, `sexp.py`, `kicad-project.json`) |
| Placement contract | `docs/geometry.json` |
| Circuit intent and decisions | `docs/research.md` |
| Evidence | `docs/fit/` (native ERC/DRC JSON, render), `docs/16bit-schematic.pdf`, `docs/schematic-symbols.json` |

## Fixed by the brief

- Bread Modular `16bit` (RP2350A, PT8211) as a Eurorack module, **6HP**, 4-layer carrier.
- Top: **MIDI in** (as modules/8bit: TS, NPN front end, JP1 bypass) and **two CV inputs**.
  Bottom: **two outputs**. **Four pots**. **Mode button** and a **mode LED** with PWM
  brightness. S2 (user, 2026-10-20): the mode button is the 8bit 6 x 6 mm THT tact switch
  and the LED is a 3 mm red one (replacing S1's BM SMD switch and 5 mm RGB LED).
- S3 (user, 2026-10-20): P1/P2 are attenuators for CV1/CV2 with the jacks normalled to
  +5V (unpatched = plain knob); P3/P4 are plain knobs; no mux. CV jacks + P1/P2 sit as a
  group, P3/P4 lower with a gap; USB-C stays on B but moves to the top edge, opening up.
- Schematic nets connected for readability; placement only, **no routing** in S1.

## Design rules kept from the repo

- BM 16bit GPIO map kept (PSRAM CS GPIO0, I2S GPIO1-3, MIDI RX GPIO5, button GPIO12,
  LED GPIO13, ADC0-3). No new GPIO functions (S3 dropped the GPIO6 mux select).
  BM's MIDI out (GPIO4) and gate outs (GPIO19/20) are left open.
- Jacks QingPu PJ301M-12 (BM AudioJacks, edited as 8bit); pots BM `Potentiometer_RV09`
  (user 50k stock, no bushing/nut); MODE = stock `SW_PUSH_6mm_H7.3mm` (6 x 6 x 7 mm THT,
  as 8bit SW1) on the F side with the 8bit one-piece printed cap; mode LED = stock
  `LED_D3.0mm` red (as 8bit D1). RUN/BOOT stay BM `K2-1808SN-A4SW-01` on B. Power header and IDC envelope as 8bit, centred.
- All SMD on B (one assembly side); jacks, pots, LED, header and SW1 hand-soldered.
- PWR_FLAGs only where ERC can't see a source: Eurorack entry (GND, +12V, -12V), behind
  D2/D3 (+12V_F, -12V_F), +1V1 (L1) and VREG_AVDD (R4).

## Sources and generators

- `tools/build_schematic.py` owns `hardware/16bit.kicad_sch`, `16BIT.kicad_sym` and
  `sym-lib-table`. Blocks are drawn with wires (`drawing()`), power symbols and labels;
  remaining pins get stubs with labels/power symbols. The build asserts nothing dangles
  and that the native netlist equals `circuit()` (`_`-prefixed nets are unlabelled local links).
- `tools/build_layout.py` places from `docs/geometry.json` and takes values, fields,
  symbol links and pad nets only from the native netlist; writes the **unrouted** carrier
  and the panel. The routed PCB owns copper: rerunning this script writes the unrouted
  board, after which the frozen R1 copper (`tools/route_r1.json`) must be re-applied through
  `tools/route_plan.py` stages and `pcb plan/apply/promote` (`docs/research.md` §6).
- `tools/route_r1.json` is frozen module data (vias + polylines from pad/via/tee to pad/via);
  `tools/route_plan.py` turns it into ≤256-op shared stages of whole nets (zones first).
- `tools/import_footprints.py` rebuilds `hardware/16BIT.pretty` / `16BIT.3dshapes`
  (provenance and every edit in `PROVENANCE.json`).

## Verification (S3, 2026-10-20)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity` (R1 routed): carrier 0 violations, 0 parity,
  0 unconnected, 0 exclusions; panel 0/0.
- Shared `kicad_tools.py check` (R1): ERC 0, DRC 0 violations, unconnected 0, parity 0;
  no source manifest (no export yet), `order_ready: false`.
- Not done: routing, sourcing, 3D fit, bench.
