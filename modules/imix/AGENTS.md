# imix agent entry point

Read root `AGENTS.md`, then this module's `Code.md`, `README.md` and
`docs/research.md`. Module paths are module-relative.

## Current state

- S3 schematic (`hardware/imix.kicad_sch`, ERC 0): 4-channel DC-coupled buffered
  mixer in the Bread Modular `imix` topology: per channel an inverting TL072 buffer
  (100k input impedance, 100k ∥ 20p) -> 100R -> Thonk Tall Trimmer B50K (Bread
  Modular RV09 footprint) -> 100k into a TL072 summer on ±12 V (B5819W per rail),
  100n at every op-amp, 1k 1206 output. Every assembled part carries
  `LCSC`, `MPN` and `Manufacturer` from `SOURCING` in `tools/build_schematic.py`
  (all JLCPCB Basic).
- R3 carrier (6HP): each channel's jack and pot share a row, MIX jack at the bottom;
  buffer TL072s U1/U2 between rows 1-2 and 3-4, summer U3 below row 4.
  Fully routed on 2 layers, GND on both layers, SMD on B. The routed native PCB owns
  copper; `tools/route_plan.py` records its explicit geometry for the shared
  plan/apply/promote flow (`Code.md`).
- 6HP FR4 panel and FreeCAD printed panel.
- The shared `check` reports no findings: ERC 0, DRC 0, 0 unconnected, parity equal,
  export manifest equal.
- `jlcpcb/`: shared-exporter output and live audit, not supplier-accepted. Open
  checks in `docs/research.md` §4: pot footprint/stack M1, knobs M2, bench E1/E2,
  order gates F1.

## Boundaries

Shared tools stay in `../../opt/`. Use `tools/kicad-project.json` for doctor/check.
Raw reports and candidates go in the ignored `research/`. Fabrication outputs, when
authorized, come from the shared exporter into `jlcpcb/`; never hand-edit them.
Bread Modular is read-only. No merges, pushes, orders or uploads.
