# audio-out contract (S3 schematic, R4 routing)

## Fixed by the brief

- Pure analog Eurorack output module on ±12 V, based on the Bread Modular `base`
  headphone/line output, with better opamps and nothing major changed.
- Board structure as `modules/midi`: one carrier parallel to the panel, held only
  by the jack nuts; SMD on the back (JLCPCB); jacks, pots and headers
  hand-soldered.
- Inputs: two TS jacks, **QingPu WQP-PJ301M-12** (L, R).
- Line out: one stereo TRS jack, **QingPu WQP-PJ366ST**, at consumer line level:
  10 Vpp in -> 1.92 Vrms out, under the 2 Vrms consumer full scale
  (`docs/research.md` §3.3).
- Headphone out: one TRS jack (PJ366ST) with one volume pot per ear, the
  **Bread Modular RV09 50k** (footprint from BM `BreadModular_Pots`).
- **Stereo; IN R is normalled to IN L** through the IN R jack's TN switch
  contact (J2 TN = IN_L): with IN R empty, L feeds both sides of both outputs. No
  MONO jumper (dropped by the user, 2026-10-19).
- Panel order, top to bottom: IN L, IN R, LINE, VOL L, VOL R, PHONES (user,
  2026-10-19). The pot is the user's RV09 sample (no threaded bushing, 16 mm
  knurled shaft above the body); 50k is used.
- Power: **unshrouded 2x5 pin header, 10-pin cable** (J5 vertical, pin 1 at
  the bottom; the user's part is bare pins, not a box header). A 10-pin socket
  clears the PHONES leads; use a 10-to-16 cable on a 16-pin bus, because a
  16-pin socket would sit over them (user, 2026-10-19). Nothing keys the cable:
  red stripe at the bottom.
- JLCPCB assembly: Basic R/C/diodes everywhere; the two opamps are Extended by
  choice. All SMD parts are on the back.
- 4HP panel, in both a KiCad FR4 version and a FreeCAD printable version.

## S3/R4 state

- `tools/build_schematic.py` owns `hardware/audio-out.kicad_sch`,
  `AudioOut.kicad_sym` and `sym-lib-table`. It uses stock KiCad 10 symbols,
  flattened and pinned (`docs/schematic-symbols.json`). The dual opamps are
  placed as units A/B/power. Every pin has a stub and a local label. A built-in
  check fails the build if any stub touches another pin's stub, and
  `kicad-cli sch upgrade --force` writes the file natively. Its `SOURCING` table
  adds `LCSC`/`MPN`/`Manufacturer` to every assembled part.
- `tools/import_footprints.py` builds `hardware/AudioOut.pretty`
  (`PROVENANCE.json`): stock parts, the BM jacks (midi's edits), and the BM RV09
  pot (Value text to F.Fab, plus the generated proxy model from
  `tools/make_pot_model.py`).
- `docs/geometry.json` owns placement, the panel and the stack.
  `tools/build_layout.py` places from it and takes refs, values, fields, symbol
  links and pad nets **only** from the native netlist. It writes an **unrouted**
  board and the panel PCB.
- **The routed native PCB (R4) is the source of truth for copper.**
  `tools/route_plan.py` holds every segment, via and both GND pours as shared
  `pcb plan` ops v1. It reproduces R4 only on the matching placement, through
  plan -> apply (new candidate under `research/`) -> promote. Don't rerun either
  generator over the routed board, except as the full README rebuild followed by
  the full verification below. Both GND pours use thermal-relief pad connections
  (`pad_connection: thermal`, R4); every GND pad needs two resolved spokes (DRC). Route changes are explicit edits to
  `route_plan.py`; nothing is autorouted.
- PWR_FLAGs: `#FLG01` (GND at the entry), `#FLG02` (+12V) and `#FLG03` (-12V).
  The rails are fed only through D1/D2. No other flags.
- The FreeCAD panel is generated from the native panel PCB and asserts against
  `geometry.json`. Never hand-edit the `.step`/`.stl`/`.FCStd`.

## Verification (S3/R4)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- Native DRC `--severity-all --schematic-parity --refill-zones`: carrier 0
  violations, 0 unconnected, 0 parity (`docs/fit/carrier-drc.json`); panel 0/0
  (`docs/fit/panel-drc.json`).
- The shared `pcb apply` accepted the R4 candidate (ERC/DRC empty, parity equal,
  source unchanged). `pcb promote` re-bound every model token (0 external).
- `kicad_tools.py doctor` passes. `kicad_tools.py check` returns
  `no_findings_in_requested_checks`, with no exclusions and no ignored rules.
- Shared assembly audit (native, `--strict-live`, `--side bottom`, `--boards 5`,
  on an export kept in `research/`): codes, MPNs, Basic/Economy classification,
  derated ratings and stock pass. The human review gates stay open
  (`docs/research.md` §5).
- `tools/fit_assembly.sh`: 0 mm³ interference against both panels; the board is
  inside the rail gap and the panel width.
- Shared-exporter JLCPCB set in `jlcpcb/` with a matching `source-sha256.json`
  (`check` reports the manifest equal); the audit was rerun on its CPL.
- No bench, physical-fit, order-ready or supplier-acceptance claim.
