# line-in agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- S2 schematic (ERC 0, nets wired): Bread Modular `line_in` on ±12 V: TRS IN ->
  50k LEVEL per side -> 1u / 1M -> TL072 follower -> x-19.6 (~x20, Doepfer A-119) inverting gain -> 1k ->
  OUT L / OUT R; U3A sums both gain outputs (-0.51 each) -> 1k -> MONO.
- R1 carrier (4HP, P3 THT unchanged): SMD placed on B group by group and routed by
  hand, 2-layer (see `Code.md` R1). DRC 0 / unconnected 0 / parity 0. Panels FR4 +
  printed.
- JLCPCB export (2026-10-28) in `jlcpcb/`: bottom Economic, 30 parts / 11 rows, 7 THT
  hand-soldered; live audit: all Basic except R7/R8/R12 ESR18 0.5 W (Extended, user
  decision open). Not supplier-accepted, not built.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and candidates go in the ignored `research/`. Bread Modular is
read-only. No merges, pushes, orders or uploads.
