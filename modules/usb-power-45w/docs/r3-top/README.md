# usb-power-45w R3: TOP board routing finished (prototype checkpoint, not a release)

> **Status (2026-10-31): TOP board fully routed. 0 unconnected, native DRC 0 violations / 0 warnings /
> 0 exclusions, schematic parity 0.** The BASE board is not part of this work: in this workspace it is
> unchanged (318 opens, routed by another worker), so the module as a whole is **not** complete.
> No fab export. No 45 W / 54.5 W rating, no thermal qualification, no connector-current
> qualification.

Batch log, placement refinements and gotchas: [NOTES.md](NOTES.md). M3 support keep-out repair
(seamed annulus, fixed 2026-10-31): [SUPPORT-KEEPOUT.md](SUPPORT-KEEPOUT.md). Images: `img/`. Raw reports:
`reports/` (copied from the ignored `research/r3-top/`).

## Final checks (board SHA-256 `922d34ab36596f123d9b7b7c67e7a22c116e14a0e083846d21c92b0f8b1a91eb`, after the support keep-out repair)

| Gate | Result |
| --- | --- |
| Native DRC, all severities, `--schematic-parity` (`reports/drc-top.json`) | 0 violations, 0 warnings, 0 excluded, 0 unconnected, parity 0 |
| Shared `kicad_tools.py check --config tools/kicad-project-top.json` (`reports/shared-check-summary.json`) | `no_findings_in_requested_checks`: ERC 0, DRC 0, unconnected 0, parity 0, source unchanged |
| `check_stack.py` (`reports/validation-stack.json`) | `problems: []` for the top board. ERC root/base/top 0. Aggregate base+top = S7 root: 216 refs, 145 nets incl. NC, exact (ref, pin) partition, no value/footprint/field mismatch. Header manifest OK. Stack mechanics unchanged (width 0.28 worst case, J2 1.50/2.93/5.19, 0 collisions) |
| 1 mm edge | copper rule 1.0 mm (DRC); courtyards: min 1.00 (R11), supports 1.004 |
| M3 support annulus r1.7..3.6, all Cu layers (`tools/check_support_copper.py`, `reports/support-copper-after.json`) | 0 copper items (tracks, vias, pads, stored and refilled fills); nearest 3.600999 mm; sector keep-outs cover the whole annulus |
| 2 mm hand-solder to the XT1/XT2 posts | min 2.00 (D12-XT1), then C33-XT2 2.02, C25 2.04, R44/R35-XT2 2.085, U7 2.10 |
| Vias in SMD pads / mask | 0 (check_stack gate is via radius + 0.05 mm; own audit requires >= 0.1 mm clearance) |
| Tracks on In1 / In2 | 0 / 0 |
| Zero-length / duplicate / dangling segments; vias not joining two layers | 0 / 0 / 0 / 0. The only track end not on a pad or via is the intended RUN T-junction at (92.02, 76.7) |
| Thermal pad nets | U4 EP9 = N12_RAW (never GND); U6 / U7 EP21 = GND |
| Supervisor pin tests (`tools/test_tps3808_pins.py`) | 6 passed |

The shared `docs/stack-r2/validation.json` was regenerated for verification and then restored, so it
is not part of this diff. The copy in `reports/` is the final run.

## Layer use and power paths (prototype sizing, not a current rating)

- **In1** = solid GND (2418 mm2 main piece). **In2** = VIN plane (2360 mm2 main piece). No tracks on
  either.
- Small plane pieces, reported separately: In1 GND 2.8 / 2.1 mm2 and In2 VIN 2.6 / 2.3 / 2.0 mm2.
  They sit in the XT1 post field between the VIN and GND posts and are tied to their posts by thermal
  spokes. B P12_RAW has a 10.2 mm2 piece west of U2, connected through via ps0 to R8.2.
- **XT1 posts**: the In1/In2 planes meet the posts with thermal spokes (0.50 mm). Solid F+B patches
  with a centre via tie the VIN posts (3-6) and each GND pair (1/2, 7/8, 13/14) together on F/B. On
  In2 the VIN centre via (94.56, 79.805) lands in the 2.59 mm2 centre fragment between posts 3-6,
  which reaches the posts by four spokes; the main In2 plane meets posts 3-6 through eight 0.50 mm
  spokes. The centre via does not bypass those spokes. The GND pair centre vias sit in the posts'
  thermal gaps on In1 (no In1 fill around them). This is a description, not an ampacity finding. +12V (9-12): F pour plus 4 vias to the B band. +5V (15-18): B pour.
  N12_RAW (19/20): two 0.4 mm B runs into the B N12_RAW pour.
- **VIN to the converters**: through the In2 plane. U2: C8/C7/C6 F pour + 4 vias. U3: C17/C15/C16
  F pour + 3 vias. U4: F pour + 3 vias + C24. C5: 2 vias. Pin stubs to U2/U3 pin 3 are 0.3 mm (the
  SOT-583 pad is 0.3 wide), U4 pin 3 is 0.6 mm.
- **+12V**: U6 pins 18-20, F pour, 3 vias, B pour (1.5 mm west leg, about 2.1 mm under U6, 1.8 mm band),
  4 vias, F pour on the posts. **+5V**: U7 pins 18-20, F bar, 3 vias, B band (1.55 mm), up-leg
  4.6 mm wide to the posts.
- **P12_RAW**: L1.2/C11-C14 F pour, 3 vias, B pour (450 mm2), 4 vias, F pour on U6 pins 1-3, plus a
  0.4 mm link to pin 6. **P5_RAW**: L2.2, 3 vias, B pour (387 mm2), 3 vias at U7 pins 1-3, plus a 0.25 mm
  link to pin 6. Output caps take one via each.
- **Switch nodes** are kept small: U2 SW 4.8 mm2, U3 SW 10.3 mm2 under L2, U4 SW 1.2 mm track (from R2).
  Every FB pad is >= 2.25 mm from SW copper (U4 FB divider 6.4-8.0 mm away). The FB_N divider
  references N12_RAW at the U4 IC ground (via n5 into the B N12_RAW pour under the pad); R14 goes to
  GND.
- **Heat**: U4 EP has the B N12_RAW pour (221 mm2) plus the F N12_RAW pour (106 mm2). U6 EP has its
  F/B pads with thermal vias to In1 plus a B GND pour (65 mm2) next to its B pad. U7 EP has its F/B
  pads with thermal vias to In1.
- Via current: 0.3 mm drill vias are used in groups of 3-4 on every power transfer. Per-via current,
  trace temperature rise and the pin/header current are **not qualified**. Prototype bench gates
  stay open: load, thermal, startup/overload and noise.

## Rebuild / check

```sh
python3 -B modules/usb-power-45w/tools/route_top_r3.py audit modules/usb-power-45w/research/r3-top/audit
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project-top.json --reports <new-dir>
python3 -B modules/usb-power-45w/tools/check_stack.py --scratch modules/usb-power-45w/research/r3-top/stack   # rewrites docs/stack-r2/validation.json
python3 -B modules/usb-power-45w/tools/route_top_r3.py view <png> 49 151 61.5 103 F.Cu,B.Cu
python3 -B modules/usb-power-45w/tools/check_support_copper.py top --refill   # M3 support annulus, all Cu layers
```

Routed copper is never regenerated. The batch tables in `tools/route_top_r3.py` are the record of
what was added, moved or ripped up, and in which order. Replaying them on a newer board is not
supported, because each batch is planned against the board state of its own time.
