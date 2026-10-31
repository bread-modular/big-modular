# R3 top-board routing - batch log (for review and for picking the work up again)

Scope: TOP board only (`hardware/top/usb-power-45w-top.kicad_pcb`). The base board belongs to another
worker and is untouched here (it still has 318 opens in this workspace).
Workspace HEAD at start: f722d0824c673e08bf238586100c8086cd2bb39e. At the start: 163 opens, DRC 0, parity 0.

Tool: `tools/route_top_r3.py`. Batches are written in NATIVE mm, use the route_r2 UUID scheme and go
through the unchanged `route_r2.apply` (shared `pcb plan` / `pcb apply`, /tmp backup, verified
write-back). `audit <dir>` runs native DRC/parity plus: vias >= 0.1 mm clear of SMD copper/mask,
tracks on In1/In2, zero-length/duplicate/dangling segments, zone-fill pieces, thermal nets.
`view <png> x0 x1 y0 y1 layers` renders the native frame with a mm grid.

Gotchas:
- The shared worker needs a byte-canonical KiCad 10 board. The R2 board was missing 4 default
  `(thickness 0.15)` font tokens on the hidden XT1/XT2 `MPN` and `Manufacturer` properties. I
  normalised it once with a native pcbnew load/save: a `diff` of pre/post snapshots shows only those
  4 inserted lines (no geometry, field value, net or copper change), and DRC/parity stayed the same.
  Shared tools were not changed. Backup: `/tmp/usb-power-45w-top-r3-pre-normalize.kicad_pcb`.
- A via joined only by zones gets renumbered to GND on native save/reload (it overlaps the In1 GND
  outline), and the shared apply then refuses it. Every via needs a track to a same-net pad or via.
- When a candidate has zero opens, the shared `promote` refuses the board's
  `${KICAD10_3DMODEL_DIR}` model tokens, because it only re-resolves staged `_kicad_models` copies.
  For those candidates the same verified write-back is used: footprints identical except the
  reviewed moves, earlier copper kept except the reviewed deletions, only that batch's items added.

## Batches

| Batch | Content | Opens after |
| --- | --- | --- |
| T2-U2-stage | U2: VIN/GND pins straight to C8; SW pour (pin 5 - L1.1 - C10); BOOT; SS; FB; RT pin = GND. F VIN pour C8/C7/C6 with In2 vias. F GND pour on the input caps plus the C11-C14 returns, with In1 vias. MAIN_OK via | 141 |
| T3-P12RAW-west | F P12_RAW pour on L1.2/C11-C14; B P12_RAW pour (west); D2/C34/D5/R19/R8; C39.1 via | 128 |
| T4-U3-stage | U3 stage (same pattern as U2); B P5_RAW pour fed from 3 vias at L2.2; D3 clamp; MAIN_OK U3 via | 105 |
| T5a-U6-input | moves R20; D6/R37/C37 turned 180 deg. F P12_RAW pour on U6 pins 1-3 from 4 B vias; pin 6 link; UV/OV dividers, DVDT, pin 9 to EP | 85 |
| T5b-U6-12V | +12V: F pour on pins 18-20 -> 3 vias -> B pour (west leg, under U6, band y84-85.8) -> 4 vias -> F pour on XT1 9-12; D12 | 73 |
| T6m-pullups | moves R35/R44 (beside XT2), R46 (R35's old spot, turned), R45 (on the +5V band); local XT2 links | 68 |
| T6-U7 | R41 turned 180 deg. +5V: F bar -> 3 vias -> B band y82.2-83.75 -> up to XT1 15-18. P5_RAW to U7 pins, R39/R41, output caps; all U7 pins; local GND vias | 28 |
| T7-logic | RUN (F above XT1, round the cutout corner, branch to U7.13), P12_OK (B), P5_OK (B -> F), MAIN_OK (later ripped up), ILIM, C5 | 15 |
| T8-U4-Q1 | rip-up of the T4/T7 MAIN_OK bottom-edge runs. New MAIN_OK: U2-U3 via B y86.9, and U2 -> bottom y101.15 -> XT2.2. P12_RAW sense to Q1 (bottom y100.7). FB_N, EN_N, Q1-B/C, D7, N12_RAW links, XT1 19/20 | 0 |
| T9-polish | F+B solid patches and centre vias on the XT1 VIN/GND posts; B GND heat pour at the U6 pad; 3rd U7 P5_RAW via; 2nd XT1-20 N12_RAW run | 0 |
| T10-via-margin | moved 8 same-net vias that sat only 0.05-0.07 mm off pad copper (flagged by the check_stack via-in-pad gate) | 1 (index slip) |
| T11-fix | removed the orphan L2.2 stub, restored R11.2 -> pr11 | 0 |

## Placement refinements (unrouted AI-placed SMD only; footprint, value and net unchanged)

| Ref | Was | Now | Why |
| --- | --- | --- | --- |
| R20 | (76.1, 82.875) | (72.6, 83.0) | its D6-A pad cut the only P12_RAW copper path to U6 pins 1-3 down to a 0.18 mm neck |
| D6, R37, C37, R41 | rot 0 | rot 180, same centre | pad order: D6-A faces R20; R37's RUN pad faces U6.13, so P12_OK can leave between its pads; C37's DVDT pad faces pin 10, so P12_OV can pass between its pads; R41's P5_RAW pad faces a free via spot |
| R35, R44 | north of U6 / west of U7 | (137.7, 69.865) rot 180, (137.7, 72.405) | V3V3 pull-ups next to XT2 (>= 2.085 mm from the posts); V3V3 no longer has to cross the board |
| R46 | (103.9, 97.3) rot 90 | (81.25, 73.075) rot 180 | the second RUN pull-down beside R37 (RUN was not reachable at the bottom edge) |
| R45 | (103.05, 99.7) | (107.4, 85.2) | +5V bleeder on the +5V band (+5V was not reachable at the bottom edge) |

All placement gates still pass after these moves: courtyard overlap (DRC), 1 mm edge, 2 mm hand-solder
and check_stack mechanics.
