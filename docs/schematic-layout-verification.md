# Schematic layout verification

Presentation-only review based on `ee8ece3`, isolated workspace013; no commit.
`tools/render_schematic.py` remains authoritative; inventory source untouched.

- Eight native pages and `schematic.pdf`: wired power-flow overview,59 matching
  directional/return/declaration ports attached to component wires, local regulator
  supports, six sense chains, J8 series/pullup wiring, one R32/D10 red power LED,
  and twelve pin-for-pin J7-to-off-board-J2 conductors with a cable boundary.
- Native CLI ERC: **0 errors,0 warnings,0 exclusions**, using unchanged project
  rules. Full local unittest discovery: **59 passed**, including deterministic
  candidate generation, directional ports and wire-only connectivity regressions.
- Before edits, captured native XML and native symbol/pin/NC records. Common-tool
  comparison: **no component, hierarchy or net delta**. Independent canonical
  native connected sets: **89 nets /381 component-pin nodes**, exactly identical.
  Native schematic comparison also preserves **389 pins including8 flags**, all
  **25 NC pins**, symbol/pin UUIDs, library IDs, every property and onboard status.
  This evidence is independent of the generated pin audit.
- Canonical native connected-set SHA-256, before = after:
  `5b8eddf25e564d44eae4df74f618dc1f8f67c35eefd85bdb995d156560445a49`.
  Definition: sorted list of sorted `(ref,pin)` pairs for every native XML net,
  serialized with JSON compact separators; includes singleton/NC nets.
- Both PCBs, BOM, pin audit, project rules and symbol/footprint libraries are
  byte-identical to the captured baseline. No routing, manufacturing exports,
  sourcing, external project access or circuit changes.
- Raw before/after native reports, XML, hashes, candidate history, test logs and
  readable page images remain ignored under `research/layout/`.

## Review limits

All eight pages are nonblank; root, debug, sensing and output pages were inspected
at readable resolution, with the other four also visually reviewed. PDF is vector
and retains hierarchy navigation. Shared GND/supplies, ERC declarations and long
control continuations intentionally remain labelled; tight two-row connector
symbols require nested harness wires, not a cable assembly drawing to scale.
No blanket label-only port banks remain. Root ports describe child-relative flow;
return and flag-only ports are passive, I2C is bidirectional.

Native schematic-to-PCB parity remains blocked by the existing unsynchronized,
unrouted boards. Existing engineering, power-up, harness/fit and procurement
blockers are unchanged. ERC0 is not permission to power, fabricate or order.
