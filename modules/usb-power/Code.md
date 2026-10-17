# usb-power circuit and repository contract

Read module `AGENTS.md`, `README.md`, `docs/ldo-handoff.md`, `docs/ldo-revision.md`,
and `docs/migration-recovery.md`. Root instructions also apply.

## Preserve the accepted design

Recover from this repository's accepted `8f3c500` tree (implementation `3524376`):
037 Basic-passive correction plus implemented 043 capacitor closure. Exact R4/R8/R36
series networks with R77-R82, C10 0402 4.5p, D10 DNP (pads retained; not a manual
purchased part). Never reuse retired D11/D12; R32 remains fitted.

Preserve 9 V PD/TPS26600 protection, autonomous retry, both TPS54302 bucks and final
P5 buck-only circuit, fixed connectors/UI/panel/outline/stack. TPS65131 raw rails
are +13.537080/-13.928806 V, followed by exact TPS7A4700RGWR/TPS7A3301RGWR.
The 043 local-cap closure is implemented (10.664 uF VPROT screens, 27.631 uF local
outputs, 39.164 kHz estimated P5 crossover); these are screening estimates, not
bench/thermal/startup qualification. LDO-R1 banks remain 4/6/4/3 exact C12891.
All components including C63-C67 are front-side. Retain B.Cu routing/mask/drills,
ordinary 0.300 mm unfilled/uncapped through vias and the narrow side/height/bracket/
access safety contract. No simultaneous 800 mA or full-temperature 1 A guarantee.

Every JLC-assembled R/C must remain actual JLCPCB **Basic AND independently evidenced
Economy eligible**; Preferred/Extended is not Basic. Keep native/BOM/PCB exact MPN,
LCSC, package, ratings and exclusion identity coherent. Cached catalog evidence is
historical, not fresh stock/allocation/service acceptance. No silent substitutions.

## Layout and tooling

- `hardware/`: `usb-power.kicad_{pro,sch,pcb}`, `usb-power-panel.kicad_{pro,pcb}`,
  six hierarchical sheets, local libraries and mechanical source.
- `docs/`, `tools/`, `tests/`, `BOM.csv`: module-local; execute tests from this module
  or use `python3 -B -m unittest discover -s modules/usb-power/tests -v` at repo root.
- `jlcpcb/`: canonical shipping-set location; recovered historical exports are STALE
  for the migrated tree until regenerated and fully verified. No active `production/`.
- `../../opt/`: shared tools; never duplicate under the module. Use
  `tools/kicad-project.json` for the carrier/hierarchical root. New candidates/raw
  reports belong in ignored `research/`, outside canonical hardware.

Read canonical shared skills and actual CLI help; common tools first. Reuse existing
`tools/release_hro.py`, common staging/native checks and CAM orchestration, not a new
exporter/router. Native schematic presentation owns placement/wires; accepted PCB
owns routing. Migration may change only filenames/project identity and path metadata.
Any circuit/PCB repair or fresh export is a separate explicit task for Astra.

Full native ERC/DRC must include warnings/exclusions/opens/parity. Independently
check exact ref/pin/net/NC/field parity and mechanics; preserve all regression tests.
No ignored rules, exclusions, fake power flags or weakened assertions. Historical
release SHA integrity stays pinned to historical Git objects; never rewrite a
historical manifest to claim it describes migrated inputs.

Work only in the assigned isolated workspace. No advisor/delegation, commits, merges,
pushes, main writes, other-workspace access, GUI, orders or uploads. Supervisor reviews
and merges verified work. Typical manufacturer data/prototype screening is not
qualified performance; source/sourcing and assembly gates remain distinct.
