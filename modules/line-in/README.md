# line-in — stereo line input to Eurorack level (4HP)

Brings a stereo consumer line source (phone, laptop, mixer) into the rack. One TRS
IN jack (tip L, ring R), a LEVEL knob per side, and three outputs: OUT L, OUT R and
MONO (L + R). Based on Bread Modular `line_in`, moved to ±12 V Eurorack levels
(`docs/research.md`).

**Status: S2 schematic + R1 manual routing + 4HP panels; JLCPCB export in
`jlcpcb/` (bottom Economic). Not supplier-accepted, nothing built.**
- Schematic: native ERC 0 (`docs/fit/schematic-erc.json`); nets drawn as wires; the
  generator checks that the native netlist equals its circuit table.
- Carrier: 19 x 110 mm, 2 layers, R1 routed by hand (all SMD on B). DRC 0,
  unconnected 0, parity 0 (`Code.md` R1).
- Export: `jlcpcb/README.md` (upload map, hand-soldered parts, audit, order gates).
  R7/R8/R12 (0.5 W 1206 1k) are Extended; every other part is Basic.
- Panels: FR4 (DRC 0) and FreeCAD printed panel (2.0 mm).

| Path | Contents |
|---|---|
| `hardware/line-in.kicad_{pro,sch,pcb}` | Schematic S2, carrier R1 (routed) |
| `jlcpcb/` | Gerbers, BOM/CPL, panel Gerbers, source manifest |
| `docs/jlcpcb-audit-requirements.json` | Circuit stress requirements for the assembly audit |
| `hardware/LineIn.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/LineIn.pretty`, `LineIn.3dshapes` | Pinned footprints, jack models, RV09 proxy (`PROVENANCE.json`) |
| `panels/front-pcb/line-in-panel.kicad_{pro,pcb}` | 4HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel generated from the panel PCB |
| `docs/research.md` | Brief, Bread Modular baseline, Eurorack changes, open points |
| `docs/geometry.json` | Placement, panel, labels, power header, SMD parking |
| `docs/line-in-schematic.pdf`, `docs/fit/` | Schematic PDF, ERC/DRC JSON, renders |
| `tools/` | Footprint import, schematic and layout generators, `kicad-project.json` |

Panel, top to bottom: `LINE IN`, IN, LEVEL L, LEVEL R, OUT L, OUT R, MONO.

Rebuild (from `modules/line-in`; `build_layout.py` rewrites an unrouted board, so
don't run it once routing has started):

```sh
python3 -B tools/import_footprints.py      # one-time library import (pcbnew)
python3 -B tools/build_schematic.py        # schematic + pinned symbols, netlist self-check
python3 -B tools/build_layout.py           # THT placement + parked SMD + panel PCB
~/Applications/FreeCAD_1.1.3.AppImage freecadcmd panels/front-cad/build_front_panel.py
```

Read [`Code.md`](Code.md) before changing hardware.
