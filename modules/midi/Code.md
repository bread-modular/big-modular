# midi contract (S3 schematic, R3 routing, V1.0 export)

## Fixed by the brief

- Input: one TRS MIDI jack, **QingPu WQP-PJ366ST** (same as Bread Modular).
- Outputs: eight TS jacks, **QingPu WQP-PJ301M-12** (PCB-soldered, panel-fixed with
  their own nut). Tip = per-channel MIDI, sleeve = GND.
- Eight LEDs, hand-soldered 3 mm THT.
- MCU: ATtiny1616. Supply is Eurorack +12 V through a simple linear regulator;
  the logic rail is **5 V** (decision D1, HT7550-1) so outputs drive 5 V Bread
  Modular receivers.
- Input: Bread Modular **V1** direct input only (not the V2 6N137). It must
  accept 3.3 V and 5 V MIDI senders. **No optocoupler in this version.** The
  opto exists to break ground loops, and an opto that shares RX with the direct
  path can't do that, so it is deferred to **V2**, where an isolated input will
  be selected automatically by voltage sensing (`docs/research.md` §3.5).
- TRS Type A/B: **JP1, a 1x3 2.54 mm header on the back** (like the UPDI header),
  B silk `TRS`, `A` level with pin 1, `B` level with pin 3. Shunt 1-2 (covers A) = Type A, 2-3 (covers B) = Type B.
- Power: 10-pin header is fine, but a **16-pin IDC socket must also fit** (J10
  vertical, pin 1 at the bottom, unshrouded).
- UPDI on a **2-pin 2.54 mm THT header** (J11: UPDI, GND).
- Output protection = Bread Modular's (1 k series), nothing more.
- JLCPCB assembly: Basic R/C wherever one exists (all except R20); R20 is a
  better 0.5 W part (Extended allowed). All SMD parts are on the back (one
  assembly side); jacks, LEDs and headers are hand-soldered.
- U3 heat sink: the regulator sits close to the power header, and the area
  around it is heat-sink copper on both layers (GND removed there), with heat
  vias.
- 4HP panel, in both a KiCad FR4 version and a FreeCAD printable version.

## S3/R3 state

- `tools/build_schematic.py` owns `hardware/midi.kicad_sch`, `MIDI.kicad_sym` and
  `sym-lib-table`: stock KiCad 10 symbols, flattened and pinned (recorded in
  `docs/schematic-symbols.json`; the only edit is footprint-filter patterns
  that drop the stock library names). Every pin has a stub and a local label;
  `kicad-cli sch upgrade --force` writes it natively. Its `SOURCING` table adds
  `LCSC`/`MPN`/`Manufacturer` to every assembled part (keyed by symbol, value and
  footprint); THT parts carry none.
- `docs/geometry.json` owns placement, the panel and the stack.
  `tools/build_layout.py` places from it and takes references, values, fields,
  symbol links and pad nets **only** from the native netlist exported from the
  schematic, and vendors 3D models into `hardware/_kicad_models/<sha256>/` (the
  usb-power convention that `pcb promote` resolves). It writes an **unrouted**
  board.
- **The routed native PCB (R3) is the source of truth for copper** (root
  `AGENTS.md`). `tools/route_plan.py` holds R3's explicit geometry (R1 routing,
  two GND stitching vias from R2, and since R3 the regulator group beside J10 on
  its VIN_LDO heat sink with the reshaped GND pours), as shared `pcb plan` ops v1.
  It reproduces R3 only on the matching placement, through
  plan -> apply (new candidate under `research/`) -> promote. Don't rerun either
  generator over the routed board, except as the full README rebuild followed
  by the full verification below. Route changes are explicit edits to
  `route_plan.py`, re-applied and inspected; nothing is autorouted.
- Each GND pour is the complement polygon kept 0.3 mm off its VIN_LDO heat
  sink, because the shared `add_zone` has no zone priority and KiCad rejects
  intersecting zones (`docs/research.md` §3.6).
- PWR_FLAGs: `#FLG01` (GND at the Eurorack entry) and `#FLG02` (VIN_LDO, fed only
  through D10/R20). No other flags.
- The FreeCAD panel is generated from the native panel PCB and asserts against
  `geometry.json`. Never hand-edit the `.step`/`.stl`/`.FCStd`.
- Circuit intent and decisions: `docs/research.md` (D1 decided: 5 V; routing
  in §3.6).
- Local footprint edits are limited to the two jack courtyards (resized to the
  model envelope), removal of two decorative jack silk arcs, and the documented
  U1 3D-model proxy. All are recorded in `hardware/MIDI.pretty/PROVENANCE.json`.

## Verification (S3/R3)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier 0
  violations, 0 unconnected, 0 parity issues (`docs/fit/carrier-drc.json`);
  panel 0/0.
- The shared `pcb apply` accepted the R3 routing candidate: ERC/DRC findings
  empty, parity equal, source unchanged. `pcb promote` re-bound every model token
  by content (0 external).
- `kicad_tools.py doctor` passes. `kicad_tools.py check` returns
  `no_findings_in_requested_checks` (exit 0): ref/pin/net parity `equal: true`,
  no exclusions, no ignored rules, and the `jlcpcb/source-sha256.json` manifest
  equal (sources unchanged since the export).
- The shared assembly audit (native mode, `--strict-live`, `--side bottom`):
  catalog codes, MPNs, Economy and stock pass; the human review gates stay
  open (`docs/research.md` §5).
- `tools/fit_assembly.sh`: nominal 3D check, 0 mm³ interference against both
  panels, board inside the rail gap and the panel width.
- Not covered by DRC (different-side items): through-hole header pads on F were
  checked against F-side jack/LED courtyards (no overlap), and the 16-pin IDC
  socket envelope against the slot, the rail gap and B-side part heights
  (`docs/mechanics.md`).
- No bench, physical-fit, order-ready or supplier-acceptance claim. The
  remaining order gates are listed in `jlcpcb/README.md`.
