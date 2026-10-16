# Reproduce / review the canonical HRO source

The routed carrier is **hardware/big_modular.kicad_pcb**. The native passive panel is
**hardware/front_panel.kicad_pcb**. `build_stack.py` copies and validates accepted
routing; it does not regenerate/erase it. Its legacy placement function is nondefault
and refuses routed inputs. Every output directory/file below must be NEW.

```sh
set -e
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
research/hro-cam-venv/bin/python -B -m unittest discover -s tests -v -f
python3 -B opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/new-check
kicad-cli pcb drc --severity-all --all-track-errors --exit-code-violations --format json -o research/new-panel-drc.json hardware/front_panel.kicad_pcb
/usr/bin/python3 -B tools/verify_project.py --netlist research/new-check/netlist.xml --output research/new-verification.json
/usr/bin/python3 -B tools/build_stack.py --output research/new-stack-copy
python3 -B tools/build_project.py --schematic-only --output research/new-schematic
python3 -B tools/build_mechanics.py --output research/new-drawings
kicad-cli sch export pdf hardware/big_modular.kicad_sch --draw-hop-over -o research/new-schematic.pdf
git diff --check
```

Schematic source/generator determinism and full source preservation remain tested.
Native hierarchy: big_modular.kicad_sch; 01_input_protection.kicad_sch;
02_hardgate.kicad_sch; 03_bucks.kicad_sch; 04_bipolar.kicad_sch;
07_output_rails.kicad_sch. No retired eight-page regeneration. HRO symbol, local
footprint, schematic fields, BOM and pin audit agree. No non-USB pin intent changes.

Common checks stage private closure and run all-severity ERC/DRC/native parity plus
XML-to-PCB parity. The passive panel has no schematic/ERC by design, not a waived
carrier parity test. All project DRC and carrier ERC severity rules are enabled, no exclusions.

Drawings include two-page assembly.pdf, standalone usb-fit.pdf, SVG and labelled
SCAD envelope. `build_panel` is an isolated NEW-panel-only function: SaveBoard uses
skip-settings so KiCad cannot overwrite the copied strict project rules. Do not
mutate pcbnew's shared `LSET.AllCuMask()` object: AddLayer can contaminate native
serialization of unrelated pad masks. This task rejected that intermediate and
restarted from the clean prior board; exact non-USB pad preservation is proven.

Bare-PCB release requirements and narrow common-suite gaps: [fabrication.md](fabrication.md).
Final releasable assets are in tracked `production/hro-r1/`, not research candidates.
Install pinned CAM dependencies into a local venv as described there, then:

```sh
research/hro-cam-venv/bin/python -B -m unittest discover -s tests -v -f
research/hro-cam-venv/bin/python -B tools/release_hro.py --output research/new-release --reports research/new-release-native
```

The release command reuses common private checks/staging/CLI. It exports KiCad
artwork, validates the ACTUAL Gerbers/drills/IPC/ZIP contents, and produces independent
carrier/passive-panel archives, separate stencil-support artwork, CAM previews and
SHA manifests. All133 vias require TypeVII epoxy fill + copper cap;35 overlap SMD
copper/paste,7 additionally meet the boundary. No ordinary tenting substitute.
No assembly CSV, sourcing completion, bench/product or supplier approval is claimed.

## Dirty-main review overlay (never writes main)

`tools/hro_merge_overlay.py --input-hardware SAVED_COPY --output NEW_REVIEW_DIR`
combines canonical hardware/libs with narrow native field/pin/filter changes on a
saved user presentation. It preserves all non-J1 sheet-instance bytes and all wires except the five documented
four-way-to-two-T presentation repairs, and
validates non-USB connectivity before creating the NEW overlay. Run fresh common
checks on that overlay. Do not blindly overwrite the user's dirty sheets/project;
see the workspace handoff for the captured hashes and exact overlap paths.

The final seven overlapping files already live in canonical workspace hardware/, preserving saved main presentation/settings. No manual file integration is required; see [safe integration](hro-integration.md).
