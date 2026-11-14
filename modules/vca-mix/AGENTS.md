# vca-mix agent entry point

Read the root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Paths here are relative to the module.

## Current state

- **S6 schematic** (2026-11-14, `hardware/vca-mix.kicad_sch`, ERC 0): 3 x Bread Modular
  V2CA vactrol VCA, buffered audio on ±12 V, post-VCA volume with OUT after the pot,
  imix-style mixer, 1k 1 W 2512 on OUT1-3 and MIX. The **CV runs on the modules/acid
  3.3 V pipeline**: 0..5 V -> 51k / 100k + BAT54SW clamp -> MCP6002 follower -> 1M / 1M ->
  MCP6002 driver with the vactrol LED in its loop; HT7533-1 +3V3. **S6: a RANGE pot per
  channel** (RV4-RV6, 50k rheostat ∥ Rn14 10k) in series with the 330R sense resistor:
  330R at 0, 8.66k at max (user direction). 7 x TL072 + 3 x MCP6002. Every assembled part
  carries `LCSC`, `MPN` and `Manufacturer` fields from `SOURCING` in
  `tools/build_schematic.py`.
- **P6 placement, 8HP** (user direction 2026-11-14; `docs/geometry.json`): carrier
  39.3 x 110 mm, 4 layers (F / In1 GND / In2 +12V / B), all SMD on B. Per channel: IN and
  CV jacks on the row, OUT jack under CV, RANGE knob under IN, **VOL knob alone in the
  right column** (no cable over it); **MIX jack under the last RANGE knob**; power header
  on B along the bottom edge, right of the MIX jack. Vactrols on B under their VOL pot
  (Bread Modular VTL5C footprint). Don't move jacks or pots without asking.
- **R3 routing: manual divide and conquer** (root `AGENTS.md`), 2026-11-14; R3 = R2 + the
  fab-review fixes of the same day (`docs/research.md` section 4.2): ERC 0, 0 unconnected,
  parity 0, 467 tracks / 82 vias, no vias in SMD pads, no tracks on In1 / In2, planes one
  piece (In1 plus five spoke-tied slivers), SMD >= 2 mm from pot / jack pads (closest
  2.015 mm), courtyards >= 1.025 mm from the edge, JLC04161H-7628 stackup recorded, fills
  saved. The native PCB owns the copper: `tools/build_layout.py` refuses to overwrite it
  (`--panel-only` for the panel).
- **D10: the 15 vactrol-under-VOL-pot stacking DRC items** (5 `pth_inside_courtyard` per
  channel) are **user-approved (2026-11-14)** per-item exclusions in
  `hardware/vca-mix.kicad_pro`, written by `tools/d10_exclusions.py` (it refuses unless the
  active findings are exactly those 15). KiCad DRC: 0 active findings. Nothing else is
  excluded; don't add exclusions without the user's approval. The shared `check` still
  counts the 15 and reports `order_ready: false` (D14).
- **`jlcpcb/` is the S6 / P6 / R3 export** (2026-11-14, shared exporter; bottom Economic,
  88 parts / 17 rows, 20 THT refs by hand, 8HP panel Gerbers), manifest equal. Not
  supplier-accepted, not built. Read `jlcpcb/README.md` before release work.
- Non-Basic parts, all user-accepted: 1k 1 W 2512 (D7), MCP6002 and BAT54SW (D16,
  2026-11-14). Open: Rn14 value on the bench (D17), vactrol fit and pot-pin soldering under
  the VOL pot, JLCPCB placement preview / DFM.
- 8HP FR4 panel and FreeCAD printed panel (six pot holes, four rail holes); nominal fit
  0 mm³ (`docs/fit/fit-report.json`).
- Pots: Song Huei R0904N on the unchanged Bread Modular RV09 footprint
  (user-confirmed in BM builds; use BM footprints when in doubt).
- Vactrol build notes (D4) are B.SilkS text inside the VTL5C body box (`SOLDER FIRST`,
  `TRIM FLUSH`, `LED 5mA`), added by `tools/import_footprints.py`.
- The placement / routing script, per-batch DRC and renders are in the ignored `research/p6/`
  (`route/build.py`, reproduces R2 only); the R3 fab-review edits, review script and reports
  are in `research/fab/` (`fab_r3.py`, `review.py`); the P5-era density study is in
  `research/s6/`.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and caches go in the ignored `research/`. `jlcpcb/` holds the shared-exporter
release set (2026-11-14, S6 / P6 / R3; `jlcpcb/README.md`). Never
hand-edit it: re-export after any source change, or `check` fails on the manifest.
Bread Modular is read-only. No merges, pushes, orders or uploads.
