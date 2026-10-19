# midi contract (V1: S5/R6, V1.0 export; V2: S4/R4, V2.0 export)

There are two hardware versions. Each is a complete, independently checked KiCad
project with its own generators, shared-tool profile and fabrication export:

| | V1 | V2 |
|---|---|---|
| KiCad project | `hardware/v1/midi.kicad_{pro,sch,pcb}` | `hardware/v2/midi.kicad_{pro,sch,pcb}` |
| Generators, routing plan, profile | `tools/v1/` | `tools/v2/` |
| Placement contract | `docs/geometry.json` | `docs/v2/geometry.json` |
| Evidence | `docs/fit/`, `docs/midi-schematic.pdf`, `docs/schematic-symbols.json`, `docs/jlcpcb-audit-requirements.json` | the same names under `docs/v2/` |
| Fabrication export | `jlcpcb/v1/` | `jlcpcb/v2/` |
| B silk marking | `MIDI V1.0` | `MIDI V2.0` |

Shared by both: the panels (`panels/`), `docs/mechanics.md`, `docs/research.md`,
`docs/sourcing-candidates.json`, and `tools/{sexp.py,import_footprints.py,fit_assembly.*}`
(the last two take the version as an argument).

## Fixed by the brief (both versions)

- Input: one TRS MIDI jack, **QingPu WQP-PJ366ST** (same as Bread Modular).
- Outputs: eight TS jacks, **QingPu WQP-PJ301M-12** (PCB-soldered, panel-fixed with
  their own nut). Tip = per-channel MIDI, sleeve = GND. They drive another module's
  ATtiny1616 RX through **1 k** at **5 V**.
- Eight LEDs, hand-soldered 3 mm THT, **switched by a transistor, not driven by
  the MCU pin** (Bread Modular `gate_out`): GPIO -> 10 k -> MMBT3904 base (emitter
  GND); +5V -> LED -> 1 k -> collector. Q11-Q18, R31-R38 (base), LED resistors keep
  R4, R6, R8, R10, R13, R15, R17, R19. LEDs are rotated 270 (cathode up).
- Each output (series 1 k, TS jack, LED driver; V2 also its clamp) is one
  hierarchical sheet, `hardware/<v>/out.kicad_sch`, instanced eight times as
  CH1-CH8 (ports TX, LED, +5V, GND).
- MCU: ATtiny1616. Supply is Eurorack +12 V through a simple linear regulator;
  the logic rail is **5 V** (decision D1, HT7550-1).
- MIDI IN must accept 3.3 V and 5 V MIDI senders. **No optocoupler in V1 or V2.**
  The opto exists to break ground loops, and an opto that shares RX with a direct
  path can't do that, so it is deferred to a later version with an isolated,
  voltage-sensed input (`docs/research.md` §3.5).
- TRS Type A/B: **JP1, a 1x3 2.54 mm header on the back** (like the UPDI header),
  B silk `TRS`, `A` level with pin 1, `B` level with pin 3. Shunt 1-2 (covers A) = Type A, 2-3 (covers B) = Type B.
- Power: 10-pin header is fine, but a **16-pin IDC socket must also fit** (J10
  vertical, pin 1 at the bottom, unshrouded).
- UPDI on a **2-pin 2.54 mm THT header** (J11: UPDI, GND).
- JLCPCB assembly: Basic R/C wherever one exists (all except R20); R20 is a
  better 0.5 W part (Extended allowed). All SMD parts are on the back (one
  assembly side); jacks, LEDs and headers are hand-soldered.
- U3 heat sink: the regulator sits close to the power header, and the area
  around it is heat-sink copper on both layers (GND removed there), with heat
  vias.
- 4HP panel, in both a KiCad FR4 version and a FreeCAD printable version. **The
  panels are shared by V1 and V2 and are not changed for V2.**

### V1 only

- Input: Bread Modular **V1** direct input (not the BM V2 6N137). JP1 drives PB3
  directly, with no series resistor or pull-up, exactly as BM V1 (R21/R2 removed in
  S4). Firmware: no `PORT_INVEN`.
- Output protection = Bread Modular's (0603 1 k series), nothing more. A
  mis-patched ±12 V cable is a known V1 risk (`docs/research.md` D6, §7.1).

### V2 only (`docs/research.md` §7)

- Mis-patch protection: a CV/gate cable of up to ±12 V on MIDI IN or any output,
  indefinitely.
- Input: NPN front end (Q1 MMBT3904, R1 10 k, D9 1N4148W B-E clamp, R2 22 k collector
  pull-up, R22 100 k idle pull-up). It is inverting: **firmware sets `PORT_INVEN` on
  PB3.**
- Input debug bypass: **JP2**, a 3-pad solder jumper on the back (copper only, not
  in BOM/CPL), **shipped open** (stock `Open` footprint, no copper bridge; PB3
  floats until one bridge is soldered by hand). Solder 1-2 = protected (Q1 collector
  RX_Q drives PB3). Solder 2-3 = MIDI_IN straight to PB3 as V1, unprotected,
  firmware without `PORT_INVEN`. Never both. B silk `P` (pin 1) / `D` (pin 3).
  R2 sits on RX_Q so the direct path has no pull-up on PB3, as V1
  (`docs/research.md` §7.2.1).
- Outputs: 1 k in **0805**, with a **BAT54SW** clamp (D11-D18) to +5V/GND on the
  GPIO side of each.
- +5V clamp: **U2 CJ431** shunt (R23 12 k / R24 10 k, 5.49 V nominal), so the
  clamp current can't pump +5V. CJ431 SOT-23 pinout is 1 REF, 2 K, 3 A: the
  schematic uses KiCad's `TL432DBZ` symbol, not `TL431DBZ`.
- Every V1 mechanical key (panel, jacks, LEDs, stack, power header) is unchanged.
  `tools/v2/build_layout.py` asserts that `docs/v2/geometry.json` equals
  `docs/geometry.json` except for `revision` and `back_side_parts`.

## Sources and generators (per version)

- `tools/<v>/build_schematic.py` owns `hardware/<v>/midi.kicad_sch`, `out.kicad_sch`,
  `MIDI.kicad_sym` and `sym-lib-table`: stock KiCad 10 symbols, flattened and pinned
  (recorded in the version's `schematic-symbols.json`; the only edit is
  footprint-filter patterns that drop the stock library names). Every pin has a
  stub and a local label; `kicad-cli sch upgrade --force` writes it natively. Its
  `SOURCING` table adds `LCSC`/`MPN`/`Manufacturer` to every assembled part (keyed
  by symbol, value and footprint); THT parts carry none.
- The version's `geometry.json` owns placement; `docs/geometry.json` also owns the
  panel and the stack. `tools/<v>/build_layout.py` places from it and takes
  references, values, fields, symbol links and pad nets **only** from the native
  netlist exported from the schematic, including each footprint's hierarchical sheet
  path. It vendors 3D models into
  `hardware/<v>/_kicad_models/<sha256>/` (the usb-power convention that `pcb promote`
  resolves) and writes an **unrouted** board. Only `tools/v1/build_layout.py` writes
  the panel.
- **The routed native PCB is the source of truth for copper** (root `AGENTS.md`).
  `tools/<v>/route_plan.py` holds its explicit geometry as shared `pcb plan` ops v1:
  - V1: R1 routing, two GND stitching vias from R2, the R3 regulator group beside J10
    on its VIN_LDO heat sink with reshaped GND pours, and the R4 direct RX track to
    JP1. R5 only dropped the B silk `JLCJLCJLCJLC` marker, which
    `tools/v1/build_layout.py` no longer writes (copper unchanged). R6 adds the LED
    driver clusters, the F.Cu +5V LED anode rail at x 118.6 and the moved RX/LED4
    lanes (`docs/research.md` §3.6).
  - V2: the V1 copper plus the clamps, the F.Cu +5V clamp rail and spine, the input
    stage, U2, the moved R10, (R2) JP2 with its RX/RX_Q/MIDI_IN tracks and (R3)
    JP2 as the open footprint, and (R4) the LED driver clusters with the turned
    clamps D11-D17 (`docs/research.md` §7.5). Its item UUIDs use the
    `big-modular/midi-v2/route/` uuid5 namespace (V1: `big-modular/midi/route/`).

  A plan reproduces its board only on the matching placement, through
  plan -> apply (new candidate under `research/`) -> promote. Don't rerun either
  generator over a routed board, except as the full README rebuild followed by the
  full verification below. Route changes are explicit edits to `route_plan.py`,
  re-applied and inspected; nothing is autorouted.
- Each GND pour is the complement polygon kept 0.3 mm off its VIN_LDO heat
  sink, because the shared `add_zone` has no zone priority and KiCad rejects
  intersecting zones (`docs/research.md` §3.6). V2 keeps the V1 heat sink intact:
  its +5V clamp rail is fed from the top, never across the heat sink.
- PWR_FLAGs: `#FLG01` (GND at the Eurorack entry) and `#FLG02` (VIN_LDO, fed only
  through D10/R20). No other flags.
- The FreeCAD panel is generated from the native panel PCB and asserts against
  `docs/geometry.json`. Never hand-edit the `.step`/`.stl`/`.FCStd`.
- Circuit intent and decisions: `docs/research.md` (V1 §1-6, V2 §7).
- JP2 uses the stock open footprint (no net tie, no copper between pads), so
  RX, RX_Q and MIDI_IN stay separate nets in copper; nothing needs an exclusion.
- Local footprint edits are limited to the two jack courtyards (resized to the
  model envelope), removal of two decorative jack silk arcs, and the documented
  U1 3D-model proxy. All are recorded in `hardware/<v>/MIDI.pretty/PROVENANCE.json`.
  V1's library adds the stock SOT-23 (S5, unedited). V2's library adds the stock
  SOT-23, SOT-323_SC-70, R_0805 and
  SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm footprints, unedited.

## Shared-tool profiles and manifests

`tools/<v>/kicad-project.json` selects the version's project and declares
`source_manifest: ../../jlcpcb/<v>/source-sha256.json`. The shared `check` then
re-hashes that version's export sources and fails on drift. Manifest keys are
relative to the module (the parent of `jlcpcb/`).

## Verification (both versions)

The two-version tree was rebuilt on 2026-10-19 after a merge lost the untracked V2,
`tools/v1|v2` and `jlcpcb/v1|v2` files. `docs/rebuild-status.md` records what was
recovered, how each version was verified against the evidence, and every deviation.
The checks below were rerun on the rebuilt tree.

- Native ERC `--severity-all`: 0 (V1 `docs/fit/schematic-erc.json`, V2
  `docs/v2/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier 0
  violations, 0 unconnected, 0 parity issues (V1 `docs/fit/carrier-drc.json`, V2
  `docs/v2/fit/carrier-drc.json`); panel 0/0 (`docs/fit/panel-drc.json`).
- The shared `pcb apply` accepted each routing candidate: ERC/DRC findings empty,
  parity equal, source unchanged. `pcb promote` re-bound every model token by
  content (0 external).
- `kicad_tools.py doctor` passes. `kicad_tools.py check --config tools/<v>/kicad-project.json`
  returns `no_findings_in_requested_checks` (exit 0) for both versions: ref/pin/net
  parity `equal: true`, no exclusions, no ignored rules, and the version's
  `jlcpcb/<v>/source-sha256.json` manifest equal.
- The shared assembly audit (native mode, `--strict-live`, `--side bottom`):
  catalog codes, MPNs, Economy and stock pass for both; the human review gates stay
  open (`docs/research.md` §5, §7.6). It was not rerun after the LED drivers
  (V1 S5/R6, V2 S4/R4).
- `tools/fit_assembly.sh v1|v2`: nominal 3D check, 0 mm³ interference against both
  panels, board inside the rail gap and the panel width. The two reports are
  identical.
- Not covered by DRC (different-side items): through-hole header pads on F were
  checked against F-side jack/LED courtyards (no overlap), and the 16-pin IDC
  socket envelope against the slot, the rail gap and B-side part heights
  (`docs/mechanics.md`). Since S5/R6 (V1) and S4/R4 (V2) the LED drivers put
  0603/SOT-23 parts under the envelope's top edge (V1 R38; V2 Q18, R38), all below
  the 2.5 mm socket floor.
- No bench, physical-fit, order-ready or supplier-acceptance claim. The
  remaining order gates are listed in `jlcpcb/<v>/README.md`.
