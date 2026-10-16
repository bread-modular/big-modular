# Reproduce / review

Run from this project root; no board sync or manufacturing exports:

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B tools/build_project.py --schematic-only --output research/new-candidate
# Review candidate; promote its .kicad_sch/.kicad_sym/pretty files, BOM and audit only.
python3 -B opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --only erc --reports research/new-check
python3 -B -m unittest discover -s tests -v
python3 -B tools/verify_project.py --netlist research/new-check/netlist.xml --output research/new-verification.json
kicad-cli sch export pdf hardware/big_modular.kicad_sch --draw-hop-over -o research/new-schematic.pdf
git diff --check
```

Current PDF pages: big_modular.kicad_sch overview; 01_input_protection.kicad_sch USB/PD;
02_hardgate.kicad_sch eFuse/SW1; 03_bucks.kicad_sch MID/P5;
04_bipolar.kicad_sch +/-12V; 07_output_rails.kicad_sch J7/D10.

Generator requires pinned electrical-catalog.json; pin-net-audit.json supports independent
connectivity/BOM/native checks. Mechanical JSON files retain current regression baselines.
Reports, datasheet copies and previews belong in ignored research/. Native `check` retains
unsynchronized PCB parity failure even with clean ERC; do not hide it or sync boards here.
