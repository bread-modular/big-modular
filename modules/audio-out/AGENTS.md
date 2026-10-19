# audio-out agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

**S3 schematic + R4 routed carrier (2026-10-19), exported to `jlcpcb/` (not supplier-accepted), not built.** R4
(user request): both GND pours use thermal reliefs; C9 moved 0.5 mm left (+12 V
pad 1.05 mm from RV1 pin 1) and R9 0.65 mm right / 0.15 mm down so its GND pad gets
two spokes. S3/R3
(user request): J5 is a 10-pin power header on the 10-pin cable, so no 16-pin plug
overhangs the PHONES leads; PHONES moved up 2.5 mm, the pots and U2 group 1 mm, and
D1/C3/D2/C4 stand beside the header. J5 is the user's unshrouded 2x5 pin header
(footprint, 3D model and data only; same pads, copper unchanged). Earlier changes from S1/R1, at the user's request: panel order IN L, IN R, LINE, VOL L, VOL R,
PHONES (PHONES at the bottom for the panel fit); JP1 MONO removed, and the IN R
jack's switch contact (J2 TN) is normalled to IN_L; the pot model follows the
user's sample (no threaded bushing, 16 mm knurled shaft above the body).

- S3 schematic (`hardware/audio-out.kicad_sch`, ERC 0). Every assembled part
  carries `LCSC`, `MPN` and `Manufacturer` from `SOURCING` in
  `tools/build_schematic.py`.
- R4 carrier: placed from `docs/geometry.json`, copper from `tools/route_plan.py`
  through the shared plan/apply/promote. Shared `check`: ERC 0, DRC 0 at all
  severities, 0 unconnected, parity equal (`docs/fit/`). The R1, R2 and R3 boards are
  kept in the ignored `research/r1-backup/`, `research/r2-backup/` and `research/r3-backup/`.
- Strict-live assembly audit on the R4 `jlcpcb/` CPL (`research/review-r4/audit.json`): 24 Basic +
  2 Extended (U1/U2); only the human review gates are open, as midi.
- JLCPCB export in `jlcpcb/` (carrier, panel, BOM/CPL, `source-sha256.json`),
  made with the shared exporter; strict-live audit rerun on its CPL with the same
  result. Order gates are listed in `jlcpcb/README.md`.
- 4HP FR4 panel (DRC 0) and FreeCAD printed panel regenerated; nominal fit
  0 mm³ interference.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for
doctor/check. Raw reports, exports for audits and caches go in the ignored
`research/`. Bread Modular is read-only. No merges, pushes, orders or uploads.
