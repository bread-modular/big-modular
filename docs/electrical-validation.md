# Functional checkpoint — single +5V LED / MCU-free debug

Base main2ef959a; isolated workspace012. Latest single-LED steering supersedes
all earlier external-permission / three-LED drafts. No commits/merges/orders/uploads.

- Native ERC: **0 findings**, no exclusions/rules changed.
- Regression tests: **55/55 PASS**, including focused electrical, mutation-negative,
  generator reproducibility, single-hole/land checks and mechanical preservation.
- Independent electrical checks:138 pin roles,39 local wired paths;124 assigned
  footprint numeric pin/pad maps. Native inventory381 real pins including NCs,
  356 connected; exact intended delta from main verified.
- Removed U10/C39/programming firmware, Q2/R39 external permit, D11/D12/R33/R34.
  J8 becomes keyed20-pin optional debug with six retained conditioned channels.
  Q1/PG + independent UV/OV retained; JP1 OPEN is qualification inhibit, not a
  debugging-controller requirement. R38/R40 provide local MID/2 bipolar enable.
- D10 alone: final P5 ->R32 1k ->red3mm LED ->GND. One original D10 hole/pad pair;
  D11/D12 and two holes removed. All other footprint geometry/setup/outlines,
  USB aperture, switch, power landing, brackets and holes preserved. No routing.
- Input, buck and complete six-channel sensing sheets byte-identical to main.
- Native schematic PDF8 pages and actual debug/LED/sense/assembly previews updated.

## Concrete blockers / handoff

Carrier DRC retains4 geometric violations,17 opens and174 native schematic-parity
findings; independent pin/net PCB parity fails (122 missing refs). Both boards
have0 tracks/vias/zones. J8, R32 and converter/sense circuitry remain unplaced;
no board synchronization or fabrication approval. JP1 stays OPEN.

All existing PD/current proof, WCH rating contradiction, fuse/magnetics/capacitors,
MID overshoot, startup/enable behavior, off-state clamp/injection, noise/thermal
and mechanical fit blockers persist. BAT54WS/TLV9002 retained; no qualified Basic
substitution or current Economy/stock/allocation guarantee was established.

The later presentation pass still needs full directional hierarchy ports and
coherent within-sheet wiring/spacing. This checkpoint does NOT claim that pass
complete; do not change circuit intent merely to improve presentation.

Raw attempts/native findings/deltas/logs are ignored under `research/mcu-free/`.
Durable small geometry contracts are `mechanical-preservation.json` and
`led-change-contract.json`; actual connector contract is `debug-interface.md`.
