# R3 TOP: M3 support copper keep-out repair (2026-10-31)

Workspace HEAD at start: `562cb165259dd4a386abebda1934c81056ff8de2`. TOP board only; the BASE board is
not changed here (see "BASE handoff").

## Defect

The R2 seed (`tools/build_stack.py`) drew each support keep-out as one rule area with an outline
r3.6 and a hole r1.7. KiCad 10 saves a zone hole by appending its vertices to the outline (tested:
1 outline + 1 hole in memory -> 1 contour, 0 holes after save/reload). Each of the five keep-outs
therefore reloaded as ONE 72-vertex contour with a radial seam at +X. Zone fill entered the
r1.7..3.6 spacer annulus through that seam, and native DRC could not see it (the fill obeys the
seamed rule area):

| Support (native mm) | Copper inside r1.7..3.6 (before) |
| --- | --- |
| MHT1 (56.250, 67.575) | B.Cu P12_RAW, In1 GND, In2 VIN, nearest r1.851 |
| MHT2 (81.950, 67.575), MHT3 (124.750, 67.575), MHT4 (117.750, 96.975), MHT5 (144.950, 67.575) | In1 GND, In2 VIN, nearest r1.851 |

No track, via or pad was inside: the nearest was 3.975 mm (MHT1, F.Cu P12_RAW track).

## Repair

- `tools/build_stack.py`: `keepout_sectors()` / `add_support_keepout()` build each support keep-out as
  4 hole-free annular sector rule areas `MH<T|B><k>_copper_keepout_r3.6_s1..s4` (100 deg each, 10 deg
  overlap with each neighbour), all copper layers, no tracks / vias / pads / pours, footprints
  allowed. Outer edges are tangent to r3.601 (vertices at r3.6044); inner vertices at r1.699 (chords
  >= r1.697, clear of the r1.6 NPTH). The seed uses this for both boards. It still refuses any
  board that has copper (`test_seed_refuses_routed_top`), so it can never wipe a routed board.
- `tools/fix_support_keepouts.py top`: natively replaced the five seamed TOP rule areas with these
  sectors, refilled, saved. It asserts nothing else changed: footprints (incl. the five supports,
  their NPTH and r4.25 courtyards), tracks, vias, copper zone outlines/settings and drawings.
  Top-level s-expression diff: only the 5 old rule areas -> 20 sector rule areas, plus new fills on
  3 copper zones (In1 GND, In2 VIN, B P12_RAW). No routing patch was needed.
- Plane area lost to the restored annulus: In1 GND 2423.2 -> 2417.8 mm2, In2 VIN 2365.5 -> 2360.2 mm2,
  B P12_RAW 440.0 -> 438.9 mm2. Plane piece counts unchanged.

Board SHA-256: before `837c9711e771d78da257789676c32223c18a2dd25bc0fa09184608bc5c58d202`, after
`922d34ab36596f123d9b7b7c67e7a22c116e14a0e083846d21c92b0f8b1a91eb`.
Backup: `/tmp/usb-power-45w-top-pre-support-keepout-837c9711e771.kicad_pcb`.

## Validation (`tools/check_support_copper.py`, reusable for both boards)

Ideal exclusion: annulus r1.7..3.6 (`stack_r2.STANDOFF_CU_R`) around each support centre, on every
copper layer, independent of how the rule areas are drawn. Only the support's own NPTH (r1.6, no
copper) is excluded, matched by its stable pad UUID (one NPTH pad per support, drill/size 3.2,
at the centre, parent footprint UUID asserted; never Python `id()` of a SWIG wrapper). Every track, arc, via (pad size per layer), pad, zone fill (as stored, plus a
fresh native refill in memory) and copper graphic is checked: hit iff `d_min < 3.6 and d_max > 1.7`,
with **no tolerance**. Tracks, vias, round pads and fill polygons use exact float64 geometry on the
1 nm grid (error < 1e-9 mm); other pads and graphics use KiCad ERROR_OUTSIDE polygons (<= 0.005 mm
larger than the copper, so they can only add false alarms). It also checks that every keep-out is one
simple contour (no holes) on all copper layers with all four bans, that the union covers a
0.25 deg x 0.02 mm polar grid of the annulus incl. both circles, and that the NPTH stays outside.

| | Before | After |
| --- | --- | --- |
| Copper items in r1.7..3.6 (stored + refilled) | 22 (all 5 supports) | **0** |
| Nearest copper to any centre | 1.851 mm | 3.600999 mm (fill) / 3.975 mm (track) |
| Annulus grid points not covered by keep-outs | 5242-5244 of 138240 per support | 0 |

Reports: `reports/support-copper-before.json`, `reports/support-copper-after.json`. Image:
`img/support-MHT1-keepout-before-after.png` (native fills, all copper layers, ideal circles green).
Unit tests: `tools/test_support_keepout.py` (sectors round-trip clean; the old outline + hole
construction is caught; seed refuses the routed top).

Other gates after the repair (same as before): native DRC all severities 0 / unconnected 0 /
excluded 0 / parity 0; shared check ERC 0 / DRC 0 / parity 0; `check_stack.py` problems [] with
mechanics, header manifest and 216-ref / 145-net equivalence identical to the R3 report (only the
three plane areas above differ); vias 121, none within 0.1 mm of SMD pad copper / mask; tracks on
In1 / In2 0; no zero-length, duplicate or dangling segments; thermal pad nets unchanged.

## BASE handoff (for the BASE worker, in its own branch)

The BASE board in this workspace (SHA-256 `9beb2790...65eca3`) has the same five seamed keep-outs
MHB1..MHB5 (`reports/support-copper-base-readonly.json`: 5242-5244 uncovered grid points per support;
no copper hit yet because it has no fills there; nearest pad 3.905 mm, so the r3.6044 sectors fit).
After this branch is merged:

1. `python3 -B modules/usb-power-45w/tools/fix_support_keepouts.py base` (backs up to /tmp, replaces
   exactly MHB1..MHB5 with the sector rule areas, refills, saves, asserts nothing else changed;
   refuses if already repaired). Run it before or after routing; do not rerun `build_stack.py`.
2. `python3 -B modules/usb-power-45w/tools/check_support_copper.py base --refill` -> `problems: 0`.
3. Rerun native DRC / parity and `check_stack.py` as usual. If a later pour or track is pushed off
   the annulus, fix it locally; never shrink or delete the keep-outs.
