# imix contract (S3 schematic, R3 routing, JLCPCB export)

## Fixed by the brief

- Four channels, each an input jack (**QingPu WQP-PJ301M-12**, as midi) plus a level
  pot, summed to one output jack (PJ301M-12). Tip = signal, sleeve = GND.
- Eurorack CV or audio: DC-coupled end to end, ±12 V supply.
- Pots: **Thonk Tall Trimmer B50K** (Song Huei R0904N, 9 mm snap-in, 6 mm insulated
  shaft 25 mm above the PCB, no bushing), the pots Bread Modular uses, on the **Bread
  Modular `Potentiometer_RV09`** footprint. 50k as on Bread Modular `imix`, B (linear)
  taper. Pin 3 (CW) = buffered input, pin 1 = GND, so volume rises clockwise.
  Hand-soldered.
- Bread Modular `imix` topology on ±12 V: per channel an inverting buffer (100k in,
  100k ∥ 20 pF feedback) for a fixed 100k Eurorack input impedance, 100R into the
  pot, 100k from the wiper into an inverting summer (100k ∥ 20 pF), 1k out. 100 nF at
  every op-amp supply pin. Jack TN grounds an unpatched input. Unity gain per
  channel at full CW, no mute/LEDs.
- 6HP: KiCad FR4 panel and FreeCAD printable panel, as midi. Panel title **IMIX**.
  Each channel's jack and pot share a row (jack left, knob right); the MIX jack sits
  at the bottom of the jack column.
- Power: 10-pin header, and a **16-pin IDC socket must also fit** (J10 vertical,
  pin 1 at the bottom, unshrouded; envelope as midi).
- JLCPCB assembly: every SMD part on the back (one side), all Basic. Jacks, pots and
  the header are hand-soldered.

## S3/R3 state

- `tools/build_schematic.py` owns `hardware/imix.kicad_sch`, `IMIX.kicad_sym` and
  `sym-lib-table`: stock KiCad 10 symbols, flattened and pinned
  (`docs/schematic-symbols.json`). The three TL072s are placed per unit (U1/U2:
  A and B are channel buffers, ch1 U1B, ch2 U1A, ch3 U2B, ch4 U2A; U3A summer, U3B
  unused grounded follower; C = power). Nets are drawn as wires (`wiring()`), one
  local label per signal net, and stock `GND`/`+12V`/`-12V` power symbols (global
  nets `GND`, `+12V`, `-12V`). The build exports the native netlist and fails unless it
  equals `circuit()`; `kicad-cli sch upgrade --force` writes it natively. `SOURCING` adds `LCSC`/`MPN`/`Manufacturer` to every
  assembled part; THT parts carry none.
- `tools/import_footprints.py` builds `hardware/IMIX.pretty` (`PROVENANCE.json`):
  stock footprints unchanged (R18 is a 1206 for its short-circuit dissipation); the
  PJ301M-12 with midi's edits plus removal of the F.SilkS body-outline segments; the RV09 with its Value text moved to F.Fab and the nominal 3D proxy from
  `tools/build_pot_model.py` attached.
- `docs/geometry.json` owns placement, panel, labels and stack.
  `tools/build_layout.py` places from it (pots by their shaft axis, the midpoint of
  the bracket pads) and takes references, values, fields, symbol links and pad nets
  **only** from the native netlist. It vendors models into
  `hardware/_kicad_models/<sha256>/` and writes an **unrouted** board plus the panel.
- **The routed native PCB is the source of truth for copper.**
  `tools/route_plan.py` holds the R3 geometry (buffer clusters U1/U2, inputs, pot
  drive, SUM bus, U3 group, rails, GND pours/stitching) as shared `pcb plan` ops v1.
  It reproduces R3 only on the
  matching placement, through plan -> apply (new candidate under `research/`) ->
  promote (README "Rebuild"). Route changes are explicit edits to `route_plan.py`,
  re-applied and inspected; nothing is autorouted.
- PWR_FLAGs: `#FLG01` (GND entry), `#FLG02` (+12V), `#FLG03` (-12V); the rails are
  fed only through D1/D2. No other flags.
- The FreeCAD panel is generated from the native panel PCB and asserts against
  `geometry.json`. Never hand-edit the `.step`/`.stl`/`.FCStd`.
- Circuit intent, decisions and open checks: `docs/research.md`.

## Verification (S3/R3)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier 0
  violations, 0 unconnected, 0 parity (`docs/fit/carrier-drc.json`); panel 0/0.
- The shared `pcb apply` accepted the R3 candidate (ERC/DRC findings empty, parity
  equal, source unchanged); `pcb promote` re-bound every model token by content.
- `kicad_tools.py doctor` passes. `kicad_tools.py check` returns
  `no_findings_in_requested_checks`: ref/pin/net parity `equal: true`, no
  exclusions, no ignored rules, and the `jlcpcb/source-sha256.json` manifest equal
  (5 sources, exports byte-identical).
- `tools/fit_assembly.sh`: nominal 3D check, 0 mm³ interference against both
  panels, board inside the rail gap and the panel width; pot shafts 13.4 mm (FR4) /
  13.0 mm (printed) proud. The pot model is a proxy from the Thonk drawing (M1).
- `jlcpcb/`: shared-exporter output and live strict assembly audit
  (`jlcpcb/README.md`). Every code/MPN/class/Economy/stock/rating check passes; the
  human review attestations and capacitor ESR/ESL/bias facts stay open.
- Not covered: footprint/pot fit (M1), bench (E1/E2), supplier preview and order
  gates (F1). No order-ready, physical-fit or performance claim.
