# Current checkpoint override

The exact 037 basic-passive correction is accepted in canonical `hardware/`: exact
R4/R8/R36 series networks with R77-R82, C10 0402 4.5p, and D10 DNP (footprint/pads
retained, not fitted or purchased). D10 is not a manual purchased part.
Source/native ERC/DRC/warnings/exclusions/opens/parity are zero; production/ldo-r1
is re-exported from this frozen source, including the JLC assembly BOM/CPL.

# Big Modular instructions

Read AGENTS.md and README.md. Work only in this isolated workspace. No advisor,
delegation, commits, merges, pushes, main writes, orders/uploads or GUI interaction.
Supervisor reviews and merges verified work. Prior workspace028 and Bread Modular
are read-only. No external project changes.

## Current authorized circuit/release

Preserve9V PD/TPS26600 protection, autonomous retry, both TPS54302 bucks and finalP5
buck-only circuit, fixed connectors/UI/panel/outline/stack. TPS65131 raw rails are
+13.530610667/-13.920584956V, followed by exact TPS7A4700RGWR/TPS7A3301RGWR.
LDO-R1 capacitor fix uses4/6/4/3 parallel exactC12891 banks. All components are
front-side (single-side assembly); no B.Cu electrical footprints or B.Paste
component apertures, while B.Cu routing/mask/drill layers remain. C67 is front.
Keep the narrow side/height/bracket/access safety contract.
Never reuse retiredD11/D12. No simultaneous800mA guarantee or bench qualification.
Bare-PCB exports are explicitly authorized under production/ldo-r1; HRO-R1 is
historical, not current. No assembly/order/allocation approval is implied.

## Required workflow

Read canonical opt/kicad-tools skills and relevant CLI help; common tools first.
Use tools/kicad-project.json for the carrier and hierarchical root. New candidates
and raw reports go in research/; accepted outputs in production/. Reuse
release_hro.py/native KiCad/common staging/CAM pipeline, not a new exporter/router.
Keep generators/BOM/native fields coherent; native schematic presentation owns
placement/wires and accepted native PCB owns routing. Explicit candidate edits only.

Full native ERC/DRC includes warnings/exclusions/opens/parity; independent exact
ref/pin/net/NC/field parity and mechanics are mandatory. No ignored rules, exclusions,
fake power flags or weakened assertions. Update accepted routing baselines only for
independently inspected intentional changes; historical release SHA integrity remains.
Typical manufacturer data plus prototype screening is not guaranteed performance.
Source/sourcing and Basic/Economy gates remain distinct; no stock claims without evidence.
