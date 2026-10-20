# vca-mix contract (S4 schematic, P4 placement, R1 routing)

## Fixed by the brief

- Module name **VCA-MIX** (directory `vca-mix`, KiCad library nickname `VCA_MIX`).
- 6HP, **three channels**. Each channel has a vactrol VCA (Bread Modular V2CA)
  with three TS jacks, **QingPu WQP-PJ301M-12**: IN (audio), CV, OUT.
- No CURVE knob: always the punchy response.
- The CV drives the vactrol LED through a **Bread Modular LOW/SVF vactrol driver**
  (LED inside the op amp loop, I_LED = CV / 2 / 330 R from 0 V, no dead zone).
- A volume pot per channel (Bread Modular pot: **Song Huei R0904N 50k** tall trimmer, `Potentiometer_RV09` footprint) sits **after the VCA**:
  OUT follows it (buffered wiper) and the three post-volume channels feed **MIX**.
- With no CV plugged in, the VCA is fully open, so the module is a 3-channel mixer.
- Audio inputs and CVs are buffered; OUT and MIX are driven through 1k 1 W 2512
  resistors (as modules/imix and modules/8bit).
- The hand-soldered parts follow the MIDI module: jacks and pots THT on F, the
  power header THT on B. The vactrols use the **unchanged Bread Modular VTL5C
  footprint** (wider Chinese vactrols) and mount on B as on Bread Modular. Every
  SMD part is on B for JLCPCB assembly.
- One row per channel: the VOL knob directly **below** its IN/CV/OUT jacks, and the
  vactrol on B behind its own pot (Bread Modular SVF style).

## S4/P4/R1 state

- `tools/build_schematic.py` owns `hardware/vca-mix.kicad_sch`, `VCA_MIX.kicad_sym` and
  `sym-lib-table`. It uses stock KiCad 10 symbols, flattened and pinned
  (`docs/schematic-symbols.json`). The only symbol edits are two footprint-filter
  patterns (`Conn_02x05_Odd_Even`; `VTL5C` also names the Bread Modular footprint).
  Ten TL072 duals are placed unit by unit (A, B, power unit C): per channel Un01
  (input buffer, VCA), Un02 (CV buffer, vactrol driver), Un03 (follower, spare); U401
  the mix. `wiring()` draws every net as wires between computed pin ends (as
  modules/imix), and the build fails unless the native netlist equals `circuit()`.
  `kicad-cli sch upgrade --force` writes the file natively. Its `SOURCING` table adds
  `LCSC`/`MPN`/`Manufacturer` to every assembled part; THT parts carry none.
- The `.kicad_pro` root-sheet UUID must equal the schematic's (`uid('root')`); the
  shared `pcb plan` rejects a mismatch.
- `docs/geometry.json` owns placement, the panel and the stack. `tools/build_layout.py`
  places from it and writes the **R1 base** (title R1, no copper). It takes
  references, values, fields, symbol links and pad nets **only** from the native
  netlist, and vendors 3D models into `hardware/_kicad_models/<sha256>/`.
- R1 copper: `tools/route_r1.json` (frozen TraceMaker route + cleanup, KiCad-frame mm)
  and `tools/route_plan.py`, which emits it plus the two solid GND zones as shared
  `pcb plan/apply` ops. Copper changes go through explicit edits of that data (or a new
  route revision) and the shared plan/apply/promote, never by hand in the board. Once
  a routed board is promoted, the native PCB owns the copper: don't rerun
  `build_layout.py` over it except to rebuild R1 from scratch (README sequence).
- D10 exclusions: the 9 vactrol/pot `pth_inside_courtyard` findings are user-approved
  per-item exclusions in `hardware/vca-mix.kicad_pro`, written only by
  `tools/d10_exclusions.py` (exact 9-pair assertion). No other exclusion, no rule
  severity change. Re-run it after every `build_layout.py`.
- R1 is **in `hardware/`** (user direction 2026-10-20, "don't worry about blockings").
  The shared apply candidate is `rejected` only because it counts the 9 excluded D10
  findings (D14), so `pcb promote` refuses it; `tools/promote_r1.py` copies the applied
  board with promote's content-hash model rebinding and refuses on any unresolved model.
  Use the shared `pcb promote` once D14 is resolved. Until then the user accepts D14
  and verifies the 9 D10 items manually (2026-10-20).
- PWR_FLAGs: `#FLG01` (GND at the Eurorack entry), `#FLG02`/`#FLG03` (+12V/-12V,
  fed only through D501/D502). No other flags.
- Local footprint edits: the jack edits are the same as MIDI's. The VTL5C keeps
  Bread Modular's pads, silk and text; a courtyard (silk box + 0.25 mm) is added so
  DRC sees the body, plus three 0.8 mm build-note silk lines inside the box
  (`SOLDER FIRST`, `TRIM FLUSH`, `LED 18.5mA`; D4) clear of the pot bracket pad. All are recorded in
  `hardware/VCA_MIX.pretty/PROVENANCE.json`.
- The FreeCAD panel is generated from the native panel PCB and asserts against
  `geometry.json`. Never hand-edit the `.step`/`.stl`/`.FCStd` files.
- Circuit intent, decisions and open checks are in `docs/research.md`.

## Verification (S4/P4/R1, 2026-10-20)

- Native ERC `--severity-all`: 0 (`docs/fit/schematic-erc.json`).
- `kicad_tools.py doctor` passes. `kicad_tools.py check` on `hardware/` (routed R1):
  ERC 0, parity equal, **0 unconnected**, DRC **9 `pth_inside_courtyard`** (the
  intended stacking, D10), so `order_ready` false (D14). Native DRC with
  `--refill-zones --all-track-errors --schematic-parity`: 9 excluded, nothing else
  (`docs/fit/carrier-drc.json`). Since D10 those 9 are
  native exclusions (`research/drc/d10-after.json`: 9 excluded, nothing else); no
  ignored rules. Panel DRC: 0 / 0.
- Shared `pcb plan/apply` of `tools/route_plan.py` (242 ops) on the R1 base: ERC 0,
  parity equal, **0 unconnected**, no added finding; DRC = the same 9, so status
  `rejected`. `kicad_tools.py check` on that candidate agrees. The candidate's copper
  equals `tools/route_r1.json` segment for segment (472 tracks, 40 vias).
- `tools/fit_assembly.sh` (nominal, P4): 0 mm³ interference for all jacks and the three
  pots against both panels, board inside the rail gap and the panel width. Vactrols are
  not modelled (D4; build notes on the footprint silk).
- JLCPCB export (2026-10-20, user direction, D14 accepted): `jlcpcb/` from the shared
  exporter, manifest equal in `check` (`jlcpcb/README.md`). Not supplier-accepted.
- No bench, physical-fit or order claim.
