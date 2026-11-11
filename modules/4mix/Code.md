# 4mix contract (S2 schematic, P6 placement + M3 standoffs, R1 routing)

## Fixed by the brief (user, 2026-10-22)

- Bread Modular `4mix` in Eurorack, **18HP**, every control a rotary RV09 pot (user stock
  50k B, Bread Modular RV09 footprint). **No overdrive section.**
- **Pure audio mixer: every input AC-coupled** (channels, returns, EXP IN; user 2026-10-22).
- Top area (user hand placement P3, 2026-10-22): SEND A, SEND B together at the top left,
  RETURN A and RETURN B each with its level knob right below the jack, then MAIN and OUT on
  the jack row.
- Channel strips below; each strip's input jack sits on top of it, then SEND A, SEND B, VOL.
  **Each channel VOL has room for a big knob** (same pot; panel keep-clear circle Ø18 mm,
  `docs/geometry.json` `big_knob`; VOL row spaced 22 mm below SEND B).
- Eurorack levels/impedances: ±12 V, 100k inputs, 1k outputs, unity gain at full CW.
- Expansion with no jacks: J6 EXP IN (top left) / J7 EXP OUT (top right) 2x3 headers on the
  back, opposite sides (MAIN, SEND A, SEND B, each beside a GND). Power J8 bottom right (user 2026-10-22).
- No jacks along the carrier bottom, so **two 10 mm M3 female-female hex standoffs** (user stock,
  2026-10-22; replace the P5 printed L brackets) hold it to the panel there: `MS1`/`MS2` between the
  CH1/CH2 and CH3/CH4 VOL pots at Y114, coaxial carrier/panel holes, `docs/geometry.json`
  `mount_standoffs`. M3x6 screws (not M3x8, which would meet inside the standoff).
- One channel drawn once as a sub-sheet (`channel.kicad_sch` x 4), nets wired.
- R1 (user 2026-10-22): 4-layer, manual divide-and-conquer routing on the native board (root
  `AGENTS.md`). F signal / In1 solid GND / In2 +12V plane / B signal; every SMD part on B.

## Sources and generators

- `tools/import_footprints.py` -> `hardware/4MIX.pretty` (+ `PROVENANCE.json`), `4MIX.3dshapes`.
- `tools/build_schematic.py` -> `4MIX.kicad_sym`, `sym-lib-table`, both sheets; exports the
  native netlist and fails unless it equals the drawn intent (named nets by name, unlabelled
  nets by membership) and the no-connect set.
- `tools/build_layout.py` -> carrier (THT from `docs/geometry.json`, SMD parked, nets from
  the native netlist, hierarchical footprint paths) and the panel. Asserts pot pin positions,
  J8 pin 1, the 1 mm courtyard edge keep-out of every placed part and no panel label, jack nut or
  small knob or standoff screw head under a big VOL knob, no two big knobs overlapping, standoff
  screw heads inside the rail gap, standoff length = the 10 mm carrier-to-panel stack.
- `tools/build_standoff.sh` (FreeCAD headless, as `mechanical/case/tools/build.sh`) runs `tools/build_standoff.py`
  -> `mechanical/standoff-m3x10.step` (carrier footprint 3D model only). Standoff footprints are
  board-only mechanical parts built in `build_layout.py`: empty Reference + `MechanicalID` MS1/MS2
  (as usb-power H1-H4), so the shared parity reports them as mechanical, not as extra refs.
- Repo-root `mechanical/knobs/tools/build_knobs.sh` (FreeCAD headless) runs `build_knobs.py`
  there -> `mechanical/knobs/` (self-contained since 2026-11-12: it reads a snapshot of this module's `docs/geometry.json` and a copy of
  the RV09 3D model in `mechanical/knobs/tools/reference/`, not this module)
  (printable channel VOL knobs, STEP + STL in print orientation: four widths from `SIZES`, whose key
  is the output folder and file tag (`wide` Ø16, `slim` Ø13, `slimmer` Ø11.5, `slimmest` Ø10), each
  in the eight fits of `FITS` (`t1` deepest teeth), + a fit gauge per width (`gauge()`: that
  width's eight knobs in print orientation, joined by break-off links, `fit_notches()` cuts 1 .. 8
  notches into base-rim ridges; asserts no link reaches into a bore or pointer pocket) for
  the shared grip 4: a solid knob keyed to the shaft knurl: round blind bore `BORE_D`, the same in
  every fit, with `SPLINES` (20)
  triangular teeth in its top `SPLINE_L`, one for every second groove of the `KNURL_TEETH` (40)
  knurl, tooth tips closing in by `TIP_TAPER` toward the roof so they wedge into the grooves; a
  fit is the tooth tip diameter at the roof, `FIT_STEP` apart, so it sets the tooth depth only).
  Reads `docs/geometry.json` and `hardware/4MIX.3dshapes/RV09_proxy.step` (shaft stretched in the
  script to the user-measured `SHAFT_L` 18 mm above the body; the model file is not edited);
  asserts the shaft tip within 0.3 mm of the measured 13 mm above either panel front, each knob
  inside the Ø18 big-knob reserve, >= 1 mm to every neighbour and above the panel, solid wall
  >= 1.35 mm (`SHELL_WALL_MIN`, three printed lines) between the bore and a flute, a groove for every tooth and the teeth ending on the
  knurl, nothing but the shaft of the pot model touching a knob, and (geometry-only seat model,
  `KNURL_DEPTH` assumed) that `REF_FIT` printed to size seats on a 6.0 mm shaft with its
  teeth at least half a groove deep, the plain shaft free in every fit, the ladder evenly spaced
  and >= `TOOTH_GAP_MIN` of bore wall between two teeth of the deepest fit. `REF_FIT` (`t4`) is the
  first grip 4 gauge's `fit8`, the tile that locked in the user's print; the ladder runs three
  steps deeper and four shallower (comment at `FITS`). Same script: `puller/knob-puller`
  (spring tongs, `PULL_*`; bending-only beam model of the half tongs gives the closed leg position per
  knob width, `PULL_TIP_R` needs an entry per width); asserts the closed hooks clear every knob
  width, the pot and the panel (hook top >= 0.2 mm
  under the knob base on the FR4 and the 2.0 mm printed panel), >= 8 mm² of knob base over the hooks,
  free tongs >= 1.5 mm from every panel neighbour, strain <= 1.5 % with the tips squeezed together.
  The script does not delete outputs of a removed width or fit. Independent check of the gauges
  against the knob files (STEP sections): `mechanical/knobs/research/check/gauge_vs_knob.py` (ignored).
  Touches no KiCad source.
- `hardware/4mix.kicad_pro`: imix settings + `min_copper_edge_clearance` 1.0 mm + Power
  netclass (GND, ±12V, ±12V_IN). No exclusions, no ignored rules.

## Routed board (R1)

- `hardware/4mix.kicad_pcb` is the routing source now; `build_layout.py` must not be rerun on it.
- Groups: power entry at J8; channel strips CH1-CH4 (template cell); MAIN/SEND buses along the
  channel rows; U5 send summers + EXP OUT at the right; U4 (EXP SEND inverters) between J1/J2; U1
  (EXP MAIN inverter + MAIN summer) below U4; U2 return followers between J3/J4; U3 output stage
  between RV3 and RV1; the 1 W (2512) output resistors R20 (between RV1 and J5), R30 (right of U3)
  and R33 (between J2 and J3).
- Long runs on F (only THT on F): -12V lines y 85.8 / 95; MAIN_MIX y 89.2; SEND A out y 90.35 and up
  the left margin to J1; SEND B mix y 76.3 to R33; EXP send paths y 77.2 / 77.8.

## Verification (S2/R1)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity --refill-zones`: 0 violations, 0 unconnected,
  0 parity (`docs/fit/carrier-drc.json`). Panel: 0 / 0.
- `kicad_tools.py check`: ERC 0, DRC 0, ref/pin/net parity `equal: true`, no findings. Source
  manifest `jlcpcb/source-sha256.json` equal (6 sources).
- Per-batch checks (`research/route/chk.py`): 0 vias touching SMD pads (101 vias), closest SMD to
  pot/jack pad 2.27 mm (R106/R206/R306/R406 to the SEND A pot wiper), no courtyard within 1 mm of
  the edge, no tracks on In1, In1 GND and In2 +12V one main piece each (In1 has 8 small spoke-tied
  fragments between header pins, 1-3.3 mm2), no zero-length/dangling/off-grid segments.
- JLCPCB export 2026-10-23 (`jlcpcb/README.md`): bottom Economic PCBA, 120 parts / 13 rows, live
  audit: all Basic except R20/R30/R33 (C54315 1 W 2512, Extended, as vca-mix).
- Not covered: 3D/panel fit, bench (levels, crosstalk).
