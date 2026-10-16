# Reproduce / review

Run from this project root; explicit NEW candidates, no routing or manufacturing exports:

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B tools/build_project.py --schematic-only --output research/new-candidate
# Review/promote schematic/library/BOM/audit candidate, then build a NEW native stack.
/usr/bin/python3 -B tools/build_stack.py --output research/new-stack
# Review/promote both .kicad_pcb files and assembly-geometry.json.
python3 -B opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/new-check
python3 -B -m unittest discover -s tests -v
/usr/bin/python3 -B tools/verify_project.py --netlist research/new-check/netlist.xml --output research/new-verification.json
kicad-cli sch export pdf hardware/big_modular.kicad_sch --draw-hop-over -o research/new-schematic.pdf
git diff --check
```

Current PDF pages: big_modular.kicad_sch overview; 01_input_protection.kicad_sch USB/PD;
02_hardgate.kicad_sch eFuse/SW1; 03_bucks.kicad_sch MID/P5;
04_bipolar.kicad_sch +/-12V; 07_output_rails.kicad_sch J7/D10.

Generator requires pinned electrical-catalog.json; pin-net-audit.json supports independent
connectivity/BOM/native checks. Mechanical JSON files retain current regression baselines.
Reports, datasheet copies and previews belong in ignored research/. Native `check` retains every DRC finding (including unrouted opens and J1 drill errors).
Native sheet presentation is preserved and pin/net validated by render_schematic.py;
it no longer replays the obsolete eight-sheet layout. Board importer uses native XML
in the existing project builder because common `pcb inspect` fails closed on retained
3D models and its edit subset cannot replace/delete these electrical footprints.
No common toolkit changes, rule suppression or parity waivers.
