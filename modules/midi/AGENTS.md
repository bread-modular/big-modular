# midi agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

There are two hardware versions. Each has its own project, generators, profile and
export (table in `Code.md`).

- **V1** (`hardware/v1/`, V1.0 / S4/R5): the Bread Modular V1 circuit. The
  fabrication export is in `jlcpcb/v1/` (`jlcpcb/v1/README.md`); it is not a
  supplier-accepted order.
  - Schematic: S4 at 5 V logic, Bread Modular V1 direct input (R21/R2 removed),
    no opto, ERC 0.
  - Carrier: R5 (R4 copper; R5 only removed the B silk `JLCJLCJLCJLC` marker),
    fully routed on 2 layers, GND on both layers. The regulator group sits right of
    the power header J10 on VIN_LDO heat-sink copper on both layers, with the UPDI
    header J11 left of J10. B silk `MIDI V1.0`.
  - Moving it into `hardware/v1/` changed no source byte. The re-export differs from
    the old one only in the Gerber dates.
  - Mis-patching (input and outputs) is a known V1 risk (D6).
- **V2** (`hardware/v2/`, V2.0 / S3/R3): V1 plus mis-patch protection
  (`docs/research.md` §7). The fabrication export is in `jlcpcb/v2/`
  (`jlcpcb/v2/README.md`); it is not a supplier-accepted order.
  - NPN MIDI input (3.3 V and 5 V senders, ±12 V tolerant; firmware sets
    `PORT_INVEN` on PB3). JP2 solder jumper ships open (no copper bridge):
    solder 1-2 = protected, or 2-3 = the V1 direct path when debugging
    (firmware then without `PORT_INVEN`). Exactly one bridge.
  - BAT54SW clamps behind 0805 1 k outputs.
  - CJ431 +5V shunt clamp.
  - No opto. Same panels and mechanics as V1. B silk `MIDI V2.0`.
- Every assembled part carries `LCSC`, `MPN` and `Manufacturer` fields from
  `SOURCING` in `tools/<v>/build_schematic.py`. The routed native PCB owns copper;
  `tools/<v>/route_plan.py` records its explicit geometry for the shared
  plan/apply/promote flow (`Code.md`).
- 4HP FR4 panel and FreeCAD printed panel, shared by both versions and unchanged.
- The shared `check` with `tools/v1/kicad-project.json` and with
  `tools/v2/kicad-project.json` reports no findings: ERC 0, DRC 0, 0 unconnected,
  schematic parity 0, ref/pin/net parity equal, and the version's
  `jlcpcb/<v>/source-sha256.json` manifest equal.
- Open checks:
  - Bench items (`docs/research.md` §4): the U3 fault test (D2) and LED brightness
    (D5).
  - V2 bench items (§7.7): ±12 V mis-patch soak, U2 stability, 3.3 V/5 V senders
    with V2 firmware.
  - For the user: the per-part assembly review attestations (§5) and the
    `jlcpcb/<v>/README.md` order gates.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/<v>/kicad-project.json` for
doctor/check. Raw reports and caches go in the ignored `research/`. Any
hardware change after an export needs a new export of that version from the
shared exporter (the `check` fails on source drift); never hand-edit `jlcpcb/`.
Don't change the panels for one version only: they are shared. Bread Modular is
read-only. No merges, pushes, orders or uploads.
