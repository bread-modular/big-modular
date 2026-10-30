# usb-power agent entry point

Read root `AGENTS.md`, then this module's `Code.md` and `README.md`. Module paths
are module-relative.

## Current state (preserve)

- Current native review is clean (ERC/DRC/parity 0); the manufacturing exports
  are regenerated; prototype bench performance is not claimed.
- SR2 schematic implemented: U3 TPS54302DDCR inverting buck-boost generates
  NRAW; U4/MID/TPS65131 and dormant-positive circuitry are removed.
- Routing is derived from the 084 baseline, with 695 track segments and 249
  through vias (2026-10-30: carrier deepened to 35 mm, J7 is a hand-soldered
  2x8 IDC box header in the new top strip, pin 1 (-12 V) toward the module
  bottom; merged cleanup: `/P5` loop removed; SW1 case tie deleted, so the
  two MP pads stay on their separate KiCad unconnected nets; pre-FAB pass: C7
  tightened at U3 and vias moved out of small SMD pads). The current
  carrier SHA and review status live only in `docs/current-review/REPORT.md`.
- `jlcpcb/` holds the complete regenerated carrier (4 Cu, mask/legend/edge,
  PTH/NPTH) and panel sets plus both ZIPs, assembly BOM/CPL and
  `source-sha256.json` (tool-written by the shared exporter; `check` re-hashes
  its sources and fails on drift); it is not supplier-accepted. Source identity
  lives there, not as a stale hash in prose.
- Native ERC/DRC must include warnings/exclusions/opens/parity plus independent
  exact ref/pin/net/NC/field parity and mechanics. No module unit tests.
- Standard four-layer JLC04161H-7628 stack (1 oz outer / 0.5 oz inner), HASL,
  ordinary 0.300 mm vias; no fill or planarization.
- Open holds: bench joint/void/thermal/EMI/startup/load qualification; loop and
  startup screens are not qualified. Via wicking on prototype assemblies is an
  inspection point, not a supplier guarantee.

## Preserve

Circuit values, native schematic presentation/UUIDs, accepted routing,
interfaces, outline, stack, brackets and sourcing identity. All components are
front-side; no B.Cu footprints or B.Paste apertures. Retain B.Cu
routing/mask/drill and ordinary unfilled/tented 0.300 mm vias; no special fill or
planarization. D10/C62/C93 DNP; R32 fitted. Keep these unless the user
explicitly authorizes a change.

## Boundaries

`jlcpcb/` is the sole export location. `production/` is retired; history lives in
Git. Shared tools/skills stay in `../../opt/`; read
`../../opt/kicad-tools/skills/kicad-workflow/SKILL.md` and, for sourcing/export,
`../../opt/kicad-tools/skills/jlcpcb-assembly/SKILL.md`. No advisor/delegation,
commit, merge, push, main writes, other-workspace access, GUI, orders or uploads;
supervisor reviews and merges. Bench/thermal/startup qualification is not
claimed; negative full-temperature 1 A dropout remains a disclosed limitation.
