> **SR2 current schematic**: see `sr2-schematic.md`; normal deterministic builds use saved SR2 native presentation.
> `--sr2-revision` is a one-shot SR1-to-SR2 candidate edit, not a PCB synchronization command.

# Current SR1 schematic-only stage

Root plus `01_input_protection.kicad_sch`, `02_hardgate.kicad_sch`,
`03_bucks.kicad_sch`, `04_bipolar.kicad_sch`, `05_quiet_rails.kicad_sch`,
**`06_positive_boost.kicad_sch`**, `07_output_rails.kicad_sch`.
Use commands in [SR1 handoff](split-rail-schematic.md). PCB is intentionally
unsynchronized; no full integrated suite/parity/release claim. Separate Opus
review and explicit user ACK must precede PCB work. Instructions below describe
the historical integrated043 checkpoint, not a completed SR1 PCB.

---

# LDO-R1 build and checks

> Migration recovery: source/electrical content below is retained checkpoint evidence.
> `jlcpcb/` is a STALE recovered Git export snapshot, not a fresh migrated export.
> Run commands from `modules/usb-power`; shared `opt/` stays at repo root. See
> [migration-recovery.md](migration-recovery.md) for current checks and Astra handoff.

Canonical `hardware/` is the capacitor-corrected LDO board. Never regenerate its
routing; the mechanical builder copies it. Historical HRO-R1 is not the new circuit.
Use system KiCad CLI/pcbnew and a local venv with `tools/cam-requirements.txt`.
The historical CAM venv was not recovered. System Python currently lacks the pinned
CAM dependencies; see `tools/cam-requirements.txt`. Do not install or hide failures
as part of repository recovery.
No advisor, commit/merge/push, order or vendor upload. Supervisor merges.

Native hierarchy: `usb-power.kicad_sch` -> `01_input_protection.kicad_sch`,
`02_hardgate.kicad_sch`, `03_bucks.kicad_sch`, `04_bipolar.kicad_sch`,
`05_quiet_rails.kicad_sch`, `07_output_rails.kicad_sch` (seven PDF pages).

Run from this module directory (`modules/usb-power`); common tools stay at the
repository root under `opt/`. All output/report directories below must be NEW:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B tools/build_project.py --schematic-only --output research/rebuilt-source
python3 -B tools/ldo_budget.py
python3 -B ../../opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/fresh-native
/usr/bin/python3 -B tools/verify_ldo_source.py --reports research/fresh-native --output research/source-parity.json
/usr/bin/python3 -B tools/verify_project.py --netlist research/fresh-native/netlist.xml --output research/project.json
python3 -B -m unittest discover -s tests -v
python3 -B tools/release_hro.py --output research/reproduced-release --reports research/reproduced-native
```

Native checks retain ALL severity categories, opens and schematic parity. Independent
checks cover318 native pins including43 NCs,594 native/PCB/BOM field comparisons,
233 reviewed pins and59 visible-wire checks, mechanics, ordinary unfilled/tented vias,
connected ground and isolated eFuseRTN. Tests include
all-front identity mutation rejection: zero B.Cu electrical footprints and zero B.Paste apertures.

`--capacitor-revision` is a guarded one-shot migration from the former3x22u banks;
it refuses already-migrated native sources. Default generation preserves native
presentation and checks exact connectivity. The release uses unchanged common
staging and native exporters, with existing Gerbonara CAM inspection extended to
both sides. Common PCB-edit inspection fails closed on inherited3D dependencies;
the narrowly inspected native synchronization gap preserved all models/rules.

The old `assembly-geometry.json` is the fixed mechanical datum/baseline; its historical
64-part text does not define the current electrical inventory. Current inventory is
checked independently against BOM, native schematic/PCB and routed-baseline.json.

Reproduction identifies exact source SHA manifests plus the uncommitted revision;
base Git HEAD alone is NOT the new design. HRO-R1 tests validate its historical
source against c82ca1c and its immutable Git-object assets (no active archive), not current LDO inputs.
