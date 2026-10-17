# SR2 routing progress 075 — UNFINISHED / NOT FOR FABRICATION

Resume **this archive**, not canonical hardware. Stopped at supervisor cost boundary.
Candidate SHA-256: `5beca717f4c970b0d47963185425c8935afbc70c7d09db68706dddd7ed4ac130`.

## Verified result
- Native DRC: **290 errors / 35 warnings -> 88 errors / 18 warnings**.
- Before: 80 opens, 82 shorts, 80 mask bridges, 32 hole-clearance,
  9 clearance and 7 courtyard errors. After: **88 opens only**; zero shorts,
  clearance/hole/mask/courtyard/edge/parity errors. Opens rose by 8 after safe rip-up.
- Warnings remain: 9 dangling tracks, 2 dangling vias, 4 text-height,
  1 silk-over-copper, 1 silk overlap, 1 track-not-centered-on-via. No exclusions/ignores.
- ERC **0 errors / 0 warnings**. Exact **116 refs / 344 pins / 39 NC /
  1,110 schematic-owned fields** PASS. All components front; fixed J1/J7/SW1/D10,
  four mounts, outline, original zones, native schematic/library/rule bytes preserved.
- Removed all **129 obsolete-net copper objects** plus specifically audited conflicting/
  detached copper. Placement repairs clear the larger L1 courtyard; some decoupler and
  feedback placements still need optimization during critical routing.
- **16 NEW external thermal vias: U12=8, U13=8**, 0.30 mm drill / 0.65 mm diameter,
  0.175 mm nominal annular ring, front/back tented. Removed 18 LDO EP-in-pad vias
  plus 3 crowded old access vias. Four 0.30 mm front copper spokes per LDO join EP21
  to corner vias; existing full-connect F/B GND pours and new local In2 GND spreaders
  connect the array. Native filled-subpolygon evidence verifies all 16 reach a corner
  spoke through In2; new holes intersect no exposed/paste pads. U12 target 10 reduced
  to 8 to avoid existing P12/VPROT routes. No fill/cap process or thermal qualification.
- **No new converter routing claimed.** The only new tracks retained are eight EP
  thermal spokes. A later power-route trial failed collision screening and was never
  applied; do not replay it. Local banks, SW/BOOT/FB, rail distribution and returns remain.

## Release blockers (not waived)
**41 other existing vias** still have holes intersecting SMD exposed pads; exact UUID/
ref inventory is in evidence. Resolve ordinary-process solder-wicking risk before fab.
L1 mounted-envelope budget remains 5.00 + 0.15 solder + 0.10 assembly + 0.15 residual
= **5.40 mm vs 5.10 mm available: 0.30 mm shortfall**. Frozen part/stack unchanged.
Specify INNER 1 oz explicitly, not JLC default. Fab-doc drill 0.25..0.35 vs JLC typical
+0.13/-0.08 on 0.30 nominal, and 20 um minimum plating vs advertised 18 um average,
remain service/release-review mismatches. No tolerances weakened. SLO1040H pads remain
engineering-defined lands; terminal-axis/overlap preflight supplied by supervisor.
Use accepted SR2 U13 dissipation screen 0.723 W nominal / 1.026 W adverse, not the
conflicting preliminary preflight values. Bench thermal/startup/loop/current gates remain.

## Exact next action
From repo root:
```sh
python3 -B modules/usb-power/docs/routing-progress-075/materialize_resume.py \
  --output modules/usb-power/research/routing-resume-075-next
```
This restores all exact native dependencies and 14 hash-pinned preinstalled models.
Then inspect/plan explicit local PRAW/NRAW LDO banks and converter hot-loop/return
routing, using `evidence/after-drc.json` for opens. Preserve thermal paths and fixed
mechanics; audit/rehome the 41 residual exposed-pad holes. Common tools first;
no rule weakening, full-board autorouter, sync replay, exports, promotion or commits.

## Evidence / provenance
CHECKPOINT + DEPENDENCIES close the portable project; same-stem .pro/root .sch are
actually included. `evidence/STATUS.json` has immutable source/rule/tool hashes.
`cleanup03-audit` and `thermal05-audit` record full native before/after UUID deltas,
unchanged dependencies and zero save/reload semantic drift. `cleanup-03.ops` supersedes
trial placement coordinates in cleanup-02 reasons; those reasons retain deletion audit.
Common cleanup apply failed on native load reassignment of conflicting copper; the
14 affected original UUIDs were explicitly removed, never relabeled or admitted by
weakened gates. Native exception was user-authorized. Archive is staged, not committed.
