# line-in agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md`,
`docs/research.md` and `docs/input-protection.md`. Paths are module-relative.

## Current state

- S3 schematic (ERC 0, nets wired): Bread Modular `line_in` on +/-12V: TRS IN ->
  50k LEVEL per side -> 1u / 1M bias -> 10k -> low-leakage BAV199 ground clamps ->
  TL072 follower -> x-19.6 inverting gain -> 1k -> OUT L / OUT R. U3A sums both
  gain outputs (-0.51 each) -> 1k -> MONO.
- R2 carrier, 4HP, P3 panel/THT geometry and all existing component positions
  unchanged. Six input-protection parts added on B and routed manually.
  DRC 0 / unconnected 0 / parity 0; no vias in SMD pads; hand-solder gap >=2.081mm,
  courtyard-to-edge >=1.075mm. Two-layer; FR4 and printed panels unchanged.
- JLCPCB export: bottom Economic selection, 36 parts / 13 rows, seven THT manual.
  R13/R14 Basic; D3-D6 BAV199 Extended (one new code), Economy-eligible.
  R7/R8/R12 ESR18 0.5W Extended retained by user decision after exact part matches
  in ACID/HATS/8bit/MCC. Review/fit concerns accepted as-is, not supplier approval.
- Protection is for powered input transients; powered-off immunity, audio THD
  and hardware fault behavior are not qualified. Not supplier-accepted or built.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check;
it explicitly checks `jlcpcb/source-sha256.json`. Raw reports and candidates go
in ignored `research/`. Do not run `build_layout.py` over the routed board.
Bread Modular is read-only. No commits without permission, merges, pushes,
orders or uploads.
