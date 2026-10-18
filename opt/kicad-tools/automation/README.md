# Offline PCB editing for agents

Standalone `inspect | plan | apply | promote` and importable `automation` API. Python stdlib
controller; **matching KiCad CLI + pcbnew 10.0.x** in a separate version-gated
interpreter. Tested on Linux with Python 3.14.4 / KiCad 10.0.6. No global installs.

```sh
python3 -B opt/kicad-tools/automation/run.py inspect --project-dir /path/design
python3 -B opt/kicad-tools/automation/run.py plan --project-dir /path/design \
  --ops /path/requests/ops.json > /path/plans/edit.json
python3 -B opt/kicad-tools/automation/run.py apply --plan /path/plans/edit.json \
  --output /path/candidates/new-design
python3 -B opt/kicad-tools/automation/run.py promote \
  --candidate /path/candidates/new-design --plan /path/plans/edit.json --dry-run
```

Put plans/requests/candidates in **separate directories outside the source and
all dependency directories**. `plan` itself writes nothing; redirection is your
choice. Explicit `--board`, `--schematic`, or `--config` also work. PCB/root
schematic must have the same stem and directory. `--pcbnew-python` and
`--kicad-cli` select existing executables, not installers.

Supported: absolute footprint move/rotate/native side flip, explicit local
footprint additions, same-net polylines/pad or branch endpoints, through-vias,
simple solid zones, edge lines/closed outlines, non-copper text, selected
UUID-based deletion of top-level straight tracks/vias/edge lines/text.

**Moving a footprint does not drag copper.** Plans are not DRC approval. Apply
creates only a NEW private candidate, refills/saves/reloads and checks ERC,
all-severity DRC, native schematic parity and XML ref/pad/net parity. It refuses
stale hashes, locked items/ancestors, aliases and unsupported inputs.

- `accepted` / exit **0**: no findings in these checks; not fabrication approval.
- `draft` / exit **1**: explicit `plan --allow-draft-opens`; connectivity/dangling
  findings only, never shorts, clearances, ERC or parity waivers.
- `rejected` / exit **1**, or operational failure / exit **2**: no completion marker.

Only `completion.json` indicates a finished candidate; its `accepted` flag is
false for a draft. Never consume a partial directory as accepted.

`promote` is the only command that writes a source. It copies an **accepted**
candidate board back onto its project board and first re-resolves every
`(model "${KIPRJMOD}/_kicad_models/<staged-hash>/…")` token against the
destination's own `_kicad_models` directories by content, because candidate
staging renames those directories by absolute source path. Unresolved tokens
abort with nothing written; `--dry-run` reports the rebindings only. With
`--plan` it also refuses when the source board changed after planning.

See [API/schema/examples](docs/api.md), [safety/limitations](docs/safety.md) and
[verification](VERIFICATION.md). Live GUI/IPC, push-and-shove, arcs, lock changes,
automatic placement/net inference, schematic editing and fabrication exports
are intentionally **not** implemented.
