# 4mix — 4-channel mixer with sends/returns (18HP)

Bread Modular `4mix` for Eurorack, without the overdrive. Audio only: every input is AC-coupled. Four channels, each with an
input jack on top of its strip and SEND A, SEND B and VOL knobs; two post-fader send
buses with their outs, two returns with level knobs, a MAIN knob and MAIN OUT. Each channel VOL has room
for a big knob. A 2x3 EXP IN (top left) / EXP OUT (top right) header pair on the back chains more channels
(another 4mix) into the MAIN and SEND buses without jacks.

**Status: S2 schematic + P6 placement + 2 M3 standoffs + R1 manual routing (4-layer, DRC 0 / unconnected 0 /
parity 0) + 18HP panel fit study + JLCPCB export (`jlcpcb/`, bottom Economic PCBA). Not supplier-accepted, not built.**

| Path | Contents |
|---|---|
| `hardware/4mix.kicad_sch` | Root sheet: power, summers, master, returns, output, expansion |
| `hardware/channel.kicad_sch` | Channel strip, instantiated CH1..CH4 (PDF: `docs/4mix-schematic.pdf`) |
| `hardware/4mix.kicad_{pro,pcb}` | 90 x 110 mm 4-layer carrier (In1 GND, In2 +12V): THT on F, SMD on B, routed (R1) |
| `panels/front-pcb/4mix-panel.kicad_{pro,pcb}` | 18HP (91.3 mm) FR4 panel: NPTH + silkscreen |
| `mechanical/standoff-m3x10.step` | 10 mm M3 F-F hex standoff (x2, user stock): carrier 3D model |
| `jlcpcb/` | Carrier and panel Gerber ZIPs, BOM/CPL, source manifest (`jlcpcb/README.md`) |
| `docs/geometry.json` | Placement, panel, labels, big-knob reserve, headers, parking |
| `docs/research.md` | Brief, Bread Modular baseline, circuit, decisions, open items |
| `tools/` | Footprint import, schematic and layout generators, shared-tool profile |

Panel (top to bottom): `4MIX`; top line SEND A, SEND B, RTN A, RTN B, MAIN, OUT with LVL A / LVL B
below their return jacks; channel numbers 1-4; rows IN, A, B, VOL (big-knob space).

Rebuild (from `modules/4mix`). The routed board is now the source of truth: do **not** rerun
`build_layout.py` (it would replace the routed carrier); the schematic generators stay valid:

```sh
python3 -B tools/import_footprints.py
python3 -B tools/build_schematic.py
tools/build_standoff.sh  # FreeCAD headless; before build_layout.py (3D model)
python3 -B tools/build_layout.py
```
