# midi agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- V1.0 / S4/R5: fabrication export in `jlcpcb/` (`jlcpcb/README.md`), not a
  supplier-accepted order.
- S4 schematic at 5 V logic (opto removed, deferred to V2; Bread Modular V1
  direct input, R21/R2 removed)
  (`hardware/midi.kicad_sch`, ERC 0). Every assembled part carries `LCSC`, `MPN`
  and `Manufacturer` fields from `SOURCING` in `tools/build_schematic.py`.
- R5 carrier (R4 copper; R5 only removed the B silk `JLCJLCJLCJLC` marker): fully routed on 2 layers, GND on both layers. The regulator group
  sits right of the power header J10 on VIN_LDO heat-sink copper on both layers
  (the UPDI header J11 is left of J10). The routed native PCB owns copper;
  `tools/route_plan.py` records its explicit geometry for the shared
  plan/apply/promote flow (`Code.md`).
- 4HP FR4 panel and FreeCAD printed panel.
- The shared `check` reports no findings: ERC 0, DRC 0, 0 unconnected,
  schematic parity 0, ref/pin/net parity equal, and the `jlcpcb/source-sha256.json`
  manifest equal.
- Open checks in `docs/research.md` §4: the U3 fault test (D2) and LED
  brightness (D5) are bench items. D6 is closed: no input resistors (exactly BM
  V1), the input is for 5 V / 3.3 V senders, mis-patching (input and outputs) is a known V1 risk, protection comes
  in V2. The
  per-part assembly review attestations (`docs/research.md` §5) and the
  `jlcpcb/README.md` order gates are for the user.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for
doctor/check. Raw reports and caches go in the ignored `research/`. Any
hardware change after this export needs a new export from the shared exporter
(the `check` fails on source drift); never hand-edit `jlcpcb/`. Bread Modular is
read-only. No merges, pushes, orders or uploads.
