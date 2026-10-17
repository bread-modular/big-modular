# 084 — HD-1 closed; source candidate only, NOT RELEASED

PCB SHA-256: `69a1e329e919ca0f8ddaaec38e30de119fa0d0639823c0017e1675554ff52adc`.
Exact parent 081: `4e4f19a16956be529fd3b08f75de34ff992bf712747fe9da94c303b5080a77db`.
Frozen PRO: `122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9`.

## Exactly two deletions, common tools only

- Delete /GND via `8e4785b7-9f30-5b83-8fb8-c7b164066610`, (130.9,81.8), 0.30 drill / 0.65 diameter.
- Delete redundant /GND B.Cu stub `b1dbe53d-475c-520a-9397-f12c9fdaa468`, (131.65,81.8) → (130.9,81.8), width 1.5 mm, length 0.75 mm.
- **(131.65,81.8) is already occupied** by unchanged /GND via `80dd5e8d-241d-5946-aa35-18f7831362a4`; do not relocate another via onto it. Deletion is the simpler authorized alternative. No new/relocated via, endpoint edit, footprint move, or native exception.

Shared inspect → plan → apply accepted; full native refill/save was performed by common apply. Common staging rebinds model resource paths: only those tokens were restored with shared `native.replace_paths` to hash-identical 075 assets before the final check. No shared-tool edits. The delivered PCB is **byte-for-byte EXACT081 with only the two native blocks deleted**, including unchanged fill caches, all fields/UUIDs, stack, outline, parts and other copper. See `before-after.patch` and `before-after-audit.json`.

## Actual verification

One fresh COMMON full ERC/DRC check on the final frozen closure: **0 errors, 0 warnings, 0 exclusions, 0 opens, 0 schematic parity issues**; source unchanged. Exact native/XML/PCB identity: **116 refs / 344 pins / 39 explicit NC + 39 markers / 1,110 non-system fields**. All 53 non-PCB closure files and 587 pre-existing tracked files unchanged; no ignored rules.

Native filled connectivity proves the deletion redundant. C78.2 → U14.13 → EP17 direct F.Cu path is unchanged. All four U14 EP vias remain in filled In1 GND; U12/U13 each retain exactly 9 EP + 8 external vias by UUID. Accepted F hot loop remains **15.42875 mm² / 18.11958 mm / 0 vias**. C78.1/.2 have zero via-hole intersections; nearest hole-edge gaps are 0.0500 / 0.302769 mm respectively (C78.1's existing gap is unchanged). No new SMD/paste intersections are possible: every surviving hole and every pad is exactly unchanged. Original authorized EP via-in-pad process remains untouched.

Raw `after-erc.json`, `after-drc.json` and actual commands/parity in `native-check-receipt.json`. Working audit/plan/logs remain in ignored `research/hd1-084*`; no render or fabrication files.

## Restore using existing 075 closure

From repository root; choose NEW names:

```sh
python3 -B modules/usb-power/docs/routing-progress-075/materialize_resume.py --output modules/usb-power/research/NEW-084-review
cp modules/usb-power/docs/routing-progress-084/usb-power.kicad_pcb modules/usb-power/research/NEW-084-review/usb-power.kicad_pcb
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power/research/NEW-084-review/candidate-profile.json --reports modules/usb-power/research/NEW-084-check --only both
```

Before trusting checks, use the hash assertions in [081 RESTORE](../routing-progress-081/RESTORE.md), substituting the **084 PCB SHA above**; PRO and all other 075 closure hashes stay exact. Do not use default/ignored-rule PRO bytes after native saves. No second dependency closure is packaged here.

**Release holds remain:** L1 5.40 vs 5.10 mm user height decision; inner-1-oz/plating/drill-tolerance/unfilled-in-pad PCBA service acceptance; thermal/EMI/startup/load/void/EP-joint bench qualification. No advisor, commit, canonical promotion, GUI, fabexport, upload or order. Supervisor's short Opus closure and source promotion remain separate.
