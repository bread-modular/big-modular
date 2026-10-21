# 16bit contract (S3 schematic, R2 manual routing)

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
  opening), joined by a short dogbone track. This replaced the R1 POFV requirement (R2 landed
  2026-10-21). U1's exposed-pad thermal vias are part of the footprint and are
  the only exception.

## Fabrication (R2 manual routing, 2026-10-21)

- **Plain tented 4-layer board, no via-in-pad fill (POFV).** 145 vias, all 0.6/0.3 mm, none in
  or touching an SMD pad or its mask opening. U1's 9 exposed-pad thermal vias (0.25 mm, part of
  the footprint) are the only vias in a pad: tented on F, open inside the EP on B.
- `tools/build_layout.py` writes tenting front/back yes, filling no, capping no; the board setup
  matches.
- B silk: BOOT / RESET under SW2 / SW3, `D` / `P` beside JP1's pads, and a `MIDI JP1`,
  `P=PROT`, `D=DIRECT` legend right of R1 (JP1 ships open: bridge one side).
- The R1 POFV requirement (123 in-pad vias from the router) is retired with that copper.
- Copper widths (R2): signals 0.2-0.3 mm; ±12 V 0.5 mm; +5V, ±12V_F 0.3-0.5 mm; +3V3/+1V1
  0.2-0.5 mm; VREG_AVDD and VREG_LX 0.2 mm at the QFN (pads are 0.2 mm wide).
- R1 details, findings and counts: `docs/research.md` §7 (retired copper).

## Sources and generators

- `tools/build_schematic.py` owns `hardware/16bit.kicad_sch`, `16BIT.kicad_sym` and
  `sym-lib-table`. Blocks are drawn with wires (`drawing()`), power symbols and labels;
  remaining pins get stubs with labels/power symbols. The build asserts nothing dangles
  and that the native netlist equals `circuit()` (`_`-prefixed nets are unlabelled local links).
- `tools/build_layout.py` places from `docs/geometry.json` and takes values, fields,
  symbol links and pad nets only from the native netlist; writes the **unrouted** carrier
  and the panel. The routed PCB owns copper and placement: the R2 hand placement and copper
  live only in `hardware/16bit.kicad_pcb`, so do not rerun this script over it.
- `tools/route_r1.json` / `tools/route_plan.py` hold the retired R1 router copper (POFV); kept as
  history, not a way to rebuild R2.
- `tools/import_footprints.py` rebuilds `hardware/16BIT.pretty` / `16BIT.3dshapes`
  (provenance and every edit in `PROVENANCE.json`).

## Verification (R2 manual routing, 2026-10-21)

- Shared `kicad_tools.py check`: ERC 0, DRC 0 violations (all severities), unconnected 0,
  parity 0, 0 exclusions; source manifest equal after the export; `order_ready: false`.
- 145 vias (0.6/0.3 mm), 0 in SMD pads/mask openings; tracks 0.2-0.5 mm; no tracks on In1; 3
  short In2 hops, In2 +3V3 one piece; In1 GND one main piece + two spoke-tied 2.6 mm² pieces at
  J6; zones refilled and saved.
- JLCPCB export 2026-10-21 (`jlcpcb/README.md`): 86 bottom-side parts, live catalog audit,
  board fields synced from the schematic without touching copper (830 tracks/vias unchanged).
- Not done: supplier acceptance, 3D fit, bench (core regulator with the unmarked L1).

## Verification (R1 + rev1 review, 2026-10-20, retired copper)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity` (R1 + rev1 edits): carrier 0 violations, 0 parity,
  0 unconnected, 0 exclusions; panel 0/0 (`docs/fit/carrier-drc.json`, `panel-drc.json`).
- Shared `kicad_tools.py check`: ERC 0, DRC 0 violations, unconnected 0, parity 0;
  no source manifest (no export yet), `order_ready: false`.
- 251 vias (246 at 0.5/0.3 mm, 5 at 0.5/0.2 mm); In1 GND no tracks, one main piece + two 2.6 mm²
  spoke-tied pieces at J6; In2 +3V3 one piece.
- Not done: sourcing, JLCPCB export, 3D fit, bench.
