# usb-power fabrication / assembly shipping set

**STALE recovered snapshot — NOT a fresh export of the migrated tree.**

> The canonical routed source is now the accepted 084 PCB
> `69a1e329e919ca0f8ddaaec38e30de119fa0d0639823c0017e1675554ff52adc`
> (`../docs/routing-source-acceptance.md`). Nothing here was regenerated from it:
> these files remain stale historical 043 evidence, and there is **no fabrication or
> assembly release**.

This is the sole shipping-set location. All 75 original files from
`8f3c5000b88a09a22e3b49ce209ca87bbc9aeefe:production/ldo-r1/` were recovered
byte-for-byte from this repository's Git objects. The original `manifest.json`,
source SHA ledgers, reports, Gerbers, drills, ZIP members and assembly BOM/CPL remain
unchanged. Legacy `big_modular` / `front_panel` names inside generated outputs are
intentional provenance, not canonical source names; do not hand-edit them.

- `carrier/` and the carrier BARE-PCB ZIP: four-layer carrier fabrication snapshot.
- `passive-panel/` and the panel BARE-PCB ZIP: passive panel snapshot.
- `assembly/`: separate assembly BOM/CPL and historical sourcing/export evidence.
- `assembly-stencil-support-only/`: separate paste/stencil-support snapshot.
- `recovery-status.json`: explicit stale/recovery status, not supplier approval.

The PCB bytes still match the accepted 043 design, but project names, schematic
project identity, tool paths and instructions changed. Consequently the old source
manifest does NOT describe this exact migrated tree. No new Gerber/BOM/CPL/PDF export,
CAM signoff, live catalog verification, order, upload or assembly qualification was
performed during recovery. Older HRO releases/production backups remain in Git only;
there is no active `production/` archive.

## Astra handoff: regenerate into NEW review directories

Read [fabrication contract](../docs/fabrication.md),
[recovery evidence](../docs/migration-recovery.md) and
[build/check commands](../docs/build.md). Shared tooling is at repository-root `opt/`.
From `modules/usb-power`, after reading actual help and obtaining export authorization:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check \
  --config tools/kicad-project.json --reports research/NEW-native
python3 -B tools/release_hro.py \
  --output research/NEW-bare-pcb --reports research/NEW-release-native
python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-power.kicad_pcb --include-through-hole --require-part-numbers \
  -o research/NEW-assembly --overwrite
python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware \
  --board usb-power-panel.kicad_pcb --pcb-only \
  -o research/NEW-panel-export --overwrite
```

These are handoff commands, not actions taken or authorization to overwrite shipping
files. The shared export includes paste/assembly semantics; it does not replace the
project's bare-PCB/CAM gate. Complete native checks, independent field/net/NC/mechanics
parity, every copper/mask/drill/paste CAM inspection, source hashes, ZIP/member SHA,
BOM/CPL ref/side/datum/rotation checks and separate Basic/Economy/live sourcing gates
before manually promoting one coherent set here. Retain full findings/failures; do not
rewrite old source ledgers, relabel old output files or mix old/new snapshots.
