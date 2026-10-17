# USB-power migration recovery

## Provenance and scope

Recovered only from this repository's Git objects in isolated workspace 045, based
on main `e4524354cf803d41dba03c64e6bdb860b69d9b0a`. No other workspace, advisor,
GUI, commit, merge, push, upload or circuit/routing edit was used.

- `e452435` and migration commit `4c11418d26e5f70c0828252644b141c4627fe421`
  have the **same tree**: instructions/README and only BOM plus part of docs migrated.
  Root hardware/tools/tests, 13 docs and production were actually still tracked.
- Authoritative accepted design: `8f3c5000b88a09a22e3b49ce209ca87bbc9aeefe`,
  identical design tree to implementation `352437640d67ba1c431b54533f22374c9796b300`.
  Its routed baseline explicitly identifies **043 / Basic-capacitor closure**.
- The `043` branch ref points at older `b4d301d`; it is NOT the recovery baseline.
  Carrier SHA there is `7d709a4f…`, not accepted `7c4e5fbc…`.
- Git fsck also found migration autostash `41a18ddf0c6987ee63b6d56f8d82c378eb58cdaf`:
  tracked deletions without recovered module hardware/tools/tests. It is not an
  authoritative completed migration. No missing-output success claims were trusted.

## File disposition and no-circuit-change proof

All hardware, local libraries, mechanical sources, module tools/tests/instructions,
BOM and missing docs are under `modules/usb-power/`. Sources are
`hardware/usb-power.kicad_{pro,sch,pcb}` and `usb-power-panel.kicad_{pro,pcb}`.
Shared `opt/`, discovery links and repository-level instructions stay at root.

Both PCB files, all local libraries/mechanics and BOM are byte-identical to the
accepted Git snapshot. Seven native schematic files change ONLY the literal
`(project "big_modular"` identity token to `usb-power`; all wires, symbols, fields,
UUIDs, positions and formatting otherwise survive exactly. The two project JSON
files change only basename/project-name strings; rules and exclusions are unchanged.
Carrier SHA-256 remains:
`7c4e5fbc923ed376fee01d578f52644c276e3cb8a862d67e01b8ec7acaedfae9`.
Accepted routing remains **107 electrical + 4 mechanical footprints, 585 tracks,
207 ordinary vias, 8 zones**. LDOs, Basic/Economy contract and D10 DNP remain intact.

`migration-recovery-manifest.json` accounts for EVERY file in the original accepted
Git tree: source commit/blob/mode, old/new path, before/after SHA-256 and disposition.
`tools/migration_audit.py --frozen-recovery` is the ONE-TIME delivery acceptance
check of exact native transforms and index/content hashes. Its frozen receipt must
not be rewritten after later engineering changes. Default `migration_audit.py` and
normal regression tests verify layout plus immutable historical provenance only;
they do NOT pin current circuit/tool/BOM contents to recovery hashes. New regression tests also reject
native value/routing/rule mutations and the older branch-base PCB.

The 75 files in `production/ldo-r1/` were recovered byte-for-byte as the canonical
`jlcpcb/` shipping snapshot, preserving historical manifests, ZIPs, CAM and BOM/CPL.
Older release/integration/verification archives remain in Git only, with each blob
recorded; no active `production/` archive is restored. Historical fabrication tests
still verify their original Git objects and hashes, not deleted tests or weakened
assertions. Root duplicates are removed only after Git/copy verification.

## Verification and handoff

Before migration, shared native all-severity ERC/DRC/opens/parity check passed with
zero findings and unchanged sources. Post-migration checks and migrated regression
results are recorded alongside this document in `migration-verification.json`.
Raw native reports and final test logs are also tracked in `migration-evidence/`;
private working reports/earlier attempts stay in ignored `research/migration-recovery/`.

- **236 module files tracked**, including 213 recovered original files and recovery
  evidence. All 393 original tracked files accounted for: 213 module, 104 shared/root,
  76 retired Git-only archives. Both PCB hashes and all native semantic checks match.
- **106 tests run from BOTH repository root and module directory: 103 pass, 3 import
  errors**, zero assertion failures/skips. All 98 original methods retained; 8 new
  migration regression tests pass independently (8/8). Errors are the enabled CAM
  tests importing missing Gerbonara; pinned Shapely is also absent. No installation,
  dependency removal, test disablement or fake all-green claim.
- Pre/post carrier ERC/DRC/warnings/exclusions/opens/parity **zero**; native pre/post
  netlist comparison equal. Passive-panel all-severity DRC/opens zero. Independent
  checks pass for 107 components, 334 pins (43 explicit NCs), 642 PCB/BOM/schematic
  field comparisons and unchanged mechanics/routing.
- KiCad CLI/pcbnew 10.0.6 available. Doctor records inherited pcbnew `PROPERTY_ENUM`
  import diagnostics (`No enum choices defined`); checks still execute successfully.
- Inherited panel project has an unused missing-schematic placeholder and carrier
  project cached sheet list predates the quiet-rail sheet. Actual root hierarchy,
  local dependencies and explicit native-check profile are complete; cosmetic
  KiCad project-cache cleanup is deferred to Astra, not silently mixed into recovery.

Run from repository root:

```sh
python3 -B modules/usb-power/tools/migration_audit.py  # ongoing layout/provenance
# One-time recovery acceptance ONLY, before subsequent authorized engineering:
python3 -B modules/usb-power/tools/migration_audit.py --frozen-recovery
python3 -B -m unittest discover -s modules/usb-power/tests -v
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/usb-power/tools/kicad-project.json \
  --reports modules/usb-power/research/NEW-native
```

**Astra handoff:** no electrical/PCB repair or new fabrication/PDF/assembly export
was performed. `jlcpcb/` is explicitly **STALE for migrated inputs**, despite exact
PCB-byte identity; never rewrite historical hashes to call it fresh. See its README
for existing shared/native/CAM pipeline and separate promotion/sourcing gates.
System Python lacks `gerbonara==1.6.3` and `shapely==2.1.2`; keep dependency failures
visible and install only in an explicitly approved isolated environment. No rules or
valid tests were removed to bypass them. Existing full-temperature negative 1 A
dropout FAIL, bench/startup/reverse/thermal/noise qualification, historical document
numerical discrepancies and live Basic/Economy/order checks remain separate tasks.
