# Prepared main integration — user controls merge

**No assistant commit, merge, stash, reset, main write or cleanup has occurred.**
The final desired carrier/panel AND the presentation-preserving seven overlap files
are already canonical in this workspace's `hardware/`. This is not a candidate-only
handoff and requires no manual integration of another overlay by the user.

## Exact dirty overlap

Main root: `/home/azero/data/projects/big-modular`; isolated work:025.
The saved-main snapshot was freshly copied, hashed before/after, and compared with024's
validated saved-input hashes. All seven still match that checkpoint. Final pre-merge
checking is mandatory because KiCad may subsequently save new content.

- `hardware/01_input_protection.kicad_sch`
- `hardware/02_hardgate.kicad_sch`
- `hardware/03_bucks.kicad_sch`
- `hardware/04_bipolar.kicad_sch`
- `hardware/07_output_rails.kicad_sch`
- `hardware/big_modular.kicad_sch`
- `hardware/big_modular.kicad_pro`

Unrelated dirty `hardware/.history` is NOT in the task delta, backup, patch or desired
file manifest. No history/GUI/lock files were read for content, copied, edited or removed.
No KiCad process was stopped. Any unsaved GUI state is outside a disk-hash guarantee.

`docs/hro-integration.json` records base, exact live-input/desired SHA256s, complete
scoped desired-file hashes/deletions, project delta, proof of preservation and backup hash.
`production/hro-integration/main-saved-overlap-backup.zip` preserves the original seven
saved files (not just a diff). It will travel with the reviewed workspace merge.
A full33-file scoped hardware snapshot additionally remains in
`research/hro-release-025/main-snapshot/` for local recovery; no ignored history was copied.
`production/hro-integration/main-presentation.patch` shows the precise task changes
relative to the user's saved files, not stale HEAD formatting.

The overlay preserves all non-J1 symbol-instance bytes and all other user presentation
except the scoped J1 identity/shared-pin fields, selected footprint filters, stage
wording, and five four-way-to-paired-T repairs. Native connectivity is unchanged
outside J1's honest13-pin local representation. The project retains ALL saved metadata/
settings; only nine inherited `ignore` severities become `warning`. Numerical rules
and all other project keys remain identical. Common all-severity checks run on the
final canonical version; source generator preserves the user's formatting byte-for-byte.

## Minimal overlap-stash plan — NOT executed, needs authorization

Before a user-controlled merge, save/close the design deliberately if needed, then run
this READ-ONLY guard from025:

```sh
python3 -B tools/hro_integration_guard.py --main /home/azero/data/projects/big-modular --phase before
```

If hashes changed, STOP integration. The assistant can freshly snapshot the new saved
closure, rerun `hro_merge_overlay.py` to a NEW directory, prove scoped preservation,
update canonical workspace files and rerun all checks. No human conflict-merging is
required. Never restore the stale snapshot over newer user edits.

If the workspace merge service requires clean OVERLAPPING paths, after explicit
approval stash **only these seven paths**, retaining the returned stash object ID:

```sh
git -C /home/azero/data/projects/big-modular stash push -m "HRO reviewed overlap backup" -- hardware/01_input_protection.kicad_sch hardware/02_hardgate.kicad_sch hardware/03_bucks.kicad_sch hardware/04_bipolar.kicad_sch hardware/07_output_rails.kicad_sch hardware/big_modular.kicad_sch hardware/big_modular.kicad_pro
```

The assistant would verify every stashed file against the saved SHA before proceeding;
verify index state first (the observed overlaps were unstaged). `.history` must remain
untouched/dirty. If the service insists on a wholly clean repository, do NOT expand
this stash to unrelated files; resolve that service constraint without erasing user work.
The USER performs the workspace merge, not the assistant.

**Do not blindly `stash pop` after merging.** The desired merged files already contain
that presentation/settings plus HRO changes; replaying old GCT edits is incorrect.
The logical restoration of the saved presentation is the prepared canonical overlay,
not a conflict-prone second application. If merge fails before changing main, restoring
that exact stash is a rollback only after hash/state verification and authorization.
Keep backup + stash until actual merged main is verified; no automatic stash drop.

## After user merge — still pending

Run the read-only `--phase after` guard against actual main, then fresh common checks,
full81-test suite, geometry/connectivity verification and deterministic CAM regeneration
from that actual main tree. Compare archive hashes and inspect results. Only after
proof of successful integration may the safely merged isolated workspace and any
redundant recovery stash be considered for cleanup under the user's authorization.
No claim that main has already been merged or validated is made here.
