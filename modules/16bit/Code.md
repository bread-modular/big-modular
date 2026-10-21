# 16bit contract (S3 schematic, S5 placement, R1 routed, rev1 reviewed)

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

## Manual routing rule (2026-10-21)

- **No vias in SMD pads.** Every via sits clear of the pad copper (and its paste/mask
  opening), joined by a short dogbone track. This replaces the R1 POFV requirement below once
  the hand-routed copper lands. U1's exposed-pad thermal vias are part of the footprint and are
  the only exception.

## Fabrication requirement (rev1 review, R1 router copper, superseded by the manual re-route)

- **Via-in-pad fill is required.** 123 board vias sit in SMD pads (53 GND stitch, 27 +3V3
  stitch, 43 signal/other rail), plus U1's 9 exposed-pad thermal vias. Order **"via in pad: resin
  filled + copper capped (POFV, IPC-4761 type VII), all vias"** (JLCPCB: "Via Covering: Epoxy
  Filled & Capped"). Ordered as a plain tented 4-layer board, solder wicks into the barrels:
  expect starved joints and tombstoned 0402s.
- `tools/build_layout.py` writes the requirement into the board setup (tenting kept, filling yes,
  capping yes); keep it there.
- Fallback if POFV is not available: hand-apply paste and reflow with tented vias, then inspect
  and touch up every in-pad joint. Expect a higher defect rate.
- Copper widths: signals 0.2 mm; +5V, ±12 V, ±12V_F 0.4 mm; **+1V1, VREG_AVDD, VREG_LX and the
  local +3V3 stubs are 0.2 mm** (QFN pads are 0.2 mm; BM runs +1V1 at 0.15 mm).
- Details, findings and counts: `docs/research.md` §7.

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

## Verification (R1 + rev1 review, 2026-10-20)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity` (R1 + rev1 edits): carrier 0 violations, 0 parity,
  0 unconnected, 0 exclusions; panel 0/0 (`docs/fit/carrier-drc.json`, `panel-drc.json`).
- Shared `kicad_tools.py check`: ERC 0, DRC 0 violations, unconnected 0, parity 0;
  no source manifest (no export yet), `order_ready: false`.
- 251 vias (246 at 0.5/0.3 mm, 5 at 0.5/0.2 mm); In1 GND no tracks, one main piece + two 2.6 mm²
  spoke-tied pieces at J6; In2 +3V3 one piece.
- Not done: sourcing, JLCPCB export, 3D fit, bench.
