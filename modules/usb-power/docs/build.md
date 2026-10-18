# Build and checks

Canonical sources are `hardware/usb-power.kicad_{pro,sch,pcb}` and the panel
project. Native sheets: root plus `01_input_protection`, `02_hardgate`,
`03_bucks`, `04_bipolar`, `05_quiet_rails`, `06_positive_boost`,
`07_output_rails`. Builds use the saved SR2 native presentation; `--sr2-revision`
is a one-shot SR1-to-SR2 candidate edit, not a PCB synchronization command.

Public validation is the shared common check, run from `modules/usb-power`:

```sh
python3 -B ../../opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/fresh-native
```

The panel has no schematic, so it is checked standalone with KiCad's own DRC
(`kicad-cli pcb drc --severity-all --refill-zones`, with the panel project
loaded; inspect `--help` for report/output flags). There is no unit-test suite.
The common check retains all ERC/DRC severity categories, opens and parity. Module production tools and data remain
available for authorized work but are not part of mandatory validation.

Never regenerate accepted routing; the mechanical builder copies it. `jlcpcb/`
is the export location; regeneration is a separate authorized task.

`docs/assembly-geometry.json` is the fixed mechanical datum; its historical part
count does not define the current electrical inventory. Current inventory is
checked against `BOM.csv`, native schematic/PCB and `docs/routed-baseline.json`.
