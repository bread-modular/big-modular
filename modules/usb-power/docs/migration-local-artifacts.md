# Ignored local artifacts after migration

Legacy root directories need not disappear from a user's checkout: they may still
contain private, ignored history/cache. The ordinary migration audit and regression
tests make no changes to those files and inspect only their supplied repository
root, never a project base/Git common directory or symlink target.

The only permitted old-root files are **untracked and Git-ignored**:

- `hardware/.history/**` history snapshots (no symlinks).
- `hardware/*.kicad_prl` local KiCad state, directly under `hardware/`.
- `tools/__pycache__/*.pyc` Python bytecode, directly under that cache directory.

Git's `check-ignore --no-index -z --stdin` determines actual ignore status; a cache
name alone is insufficient. Tracked files under root `hardware/`, `tools/`, `tests/`,
`docs/`, `production/` or `BOM.csv` are always rejected. Active design/tool/release
files and other unknown files there are rejected even under a blanket ignore rule.
Non-ignored unknown files produce a path-specific diagnostic for manual review;
there is no automatic deletion, move or cleanup. Empty directories are harmless.

Both ongoing and one-time frozen audits use this local-artifact check. Required
tracked-file completeness, native identity proofs, source/recovery hashes and
frozen receipts are unchanged; the frozen acceptance mode is still not an ongoing
engineering-content gate. See [migration-recovery.md](migration-recovery.md).

`tests/test_migration_recovery.py` exercises real Git ignore/index behavior in
disposable relocated synthetic repositories: allowed caches remain byte-identical;
non-ignored caches, ignored real sources/releases, unknown files, tracked artifacts
and symlinks fail. No simulations touch the user's original checkout.

From the repository root:

```sh
python3 -B modules/usb-power/tools/migration_audit.py
python3 -B -m unittest discover -s modules/usb-power/tests -p 'test_migration_recovery.py' -v
```
