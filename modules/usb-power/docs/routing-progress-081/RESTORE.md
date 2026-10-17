# Restore 081 for independent review — not a release/promotion command

Run from the repository root. Use an exclusively NEW research destination. This reuses the existing 075 dependency closure; do not copy a second 70-file closure into docs, regenerate schematics, or touch canonical hardware.

```sh
python3 -B modules/usb-power/docs/routing-progress-075/materialize_resume.py \
  --output modules/usb-power/research/NEW-081-review
cp modules/usb-power/docs/routing-progress-081/usb-power.kicad_pcb \
  modules/usb-power/research/NEW-081-review/usb-power.kicad_pcb
python3 -B - <<'PY'
import hashlib, json
from pathlib import Path
p = Path('modules/usb-power/research/NEW-081-review')
h = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
assert h(p/'usb-power.kicad_pcb') == '4e4f19a16956be529fd3b08f75de34ff992bf712747fe9da94c303b5080a77db'
assert h(p/'usb-power.kicad_pro') == '122b817bc0e58812a027ab4e422d35e668cf1d9a47c25dfaa715918484529de9'
for name, expected in json.loads((p/'RESTORE.json').read_text())['copied_files'].items():
    if name != 'usb-power.kicad_pcb':
        assert h(p/name) == expected, name
print('081 PCB and exact frozen dependency closure verified')
PY
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/usb-power/research/NEW-081-review/candidate-profile.json \
  --reports modules/usb-power/research/NEW-081-review-check --only both
```

The materializer's `RESTORE.json` describes its original 075 PCB, not the replacement. Both the candidate and every non-PCB closure file must match the assertions above. Expected reports: ERC and DRC errors/warnings/exclusions/opens/parity all zero; `source_unchanged: true`. Checks privately stage the complete hierarchy and local library tables; do not use a cwd-mismatched raw ERC run as evidence.

**Native-save trap:** standalone pcbnew `SaveBoard` can replace the companion `.kicad_pro` with defaults/ignored warnings. After any future native save, restore the exact bytes from `docs/routing-progress-075/usb-power.kicad_pro`, then assert the pinned hash **before every trusted check**. Recheck all other dependency hashes too. Never accept or copy default/rule/exclusion drift. Rerun checks after any restoration; a check under wrong project bytes is invalid.

075 closure hashes:

- `DEPENDENCIES.json`: `e056507eb0d7808f102186036c46688c69e8f2090e4831c2ea94ae9522b7bf6e`
- `CHECKPOINT.json`: `f64516722696030e1a8366876a8835df461580fd33e3e04fa95c08d9f2a65ae0`
- `candidate-profile.json`: `0fefa34ad1e5465432adf9da9ac734846318ab5f42e0f5ed6ce74c138afc1506`

The preserved 081 PCB already contains native refilled zones. Independent review must use the actual U14 pin map, explicit paths and geometry audit in `HANDOFF.md`, not the withdrawn first 080 report. Fresh independent Opus delta, L1 envelope decision, process/service acceptance and bench qualification are still open; no orders/uploads/exports/promotion follow automatically from a clean check.
