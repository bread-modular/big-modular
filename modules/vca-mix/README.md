# vca-mix — 3 x vactrol VCA + 3-channel mixer (8HP)

Each channel is a Bread Modular V2CA vactrol VCA with IN, CV and OUT jacks, a RANGE
knob and a VOL knob. The CV (0..5 V) is scaled to 3.3 V and drives the vactrol through
the modules/acid CV pipeline (Bread Modular LOW/SVF vactrol driver on +3V3), so the
response follows the CV from 0 V with no dead zone. **RANGE** is the V2CA CURVE pot: at 0
the LED sense resistor is 330 R (the punchy, fully open response); turning it up adds up
to 8.33k (50k pot ∥ 10k), so the same CV gives less LED current and the VCA opens less.
A volume pot after each VCA sets the channel level: OUT follows it, and the three
channels sum into a MIX output (the Bread Modular imix mixer). With no CV plugged in and
RANGE at 0 the VCA is fully open, so VCA-MIX also works as a plain 3-channel mixer. Power
is Eurorack ±12 V (7 x TL072 for the audio, 3 x MCP6002 on a local +3V3 for the CV).
Inputs and CVs are buffered; OUT and MIX drive through 1 W 1k resistors.

**Status: S6 schematic + P6 8HP placement + R3 manual routing, fab-reviewed and exported
for JLCPCB (2026-11-14, `jlcpcb/`). Not supplier-accepted (no JLCPCB preview / DFM yet), not
built.**
- Schematic drawn with wired nets (native ERC 0).
- 8HP panels (FR4 + printed) generated: six pot holes, four rail holes.
- Carrier 39.3 x 110 mm, 4 layers (In1 GND, In2 +12V), all SMD on the back. Per channel:
  IN and CV jacks, OUT under CV, RANGE under IN, VOL alone in the right column (no cable
  over the knob you turn most); MIX jack under the last RANGE knob; vactrols on B under
  their VOL pot.
- Routed by hand, divide and conquer: 0 unconnected, parity 0, no vias in SMD pads,
  SMD >= 2 mm from pot / jack pads, 1 mm edge keep-out. Native DRC: 0 active findings; the
  15 vactrol-under-VOL-pot stacking items are user-approved exclusions.
- R3 fab review: MCP6002 bypass caps at their pins, 1.0 mm back silk, JLC04161H-7628
  stackup recorded.
- JLCPCB export in `jlcpcb/`: 4-layer carrier, bottom-side Economic assembly (88 parts, 17
  BOM rows), 8HP panel Gerbers. Jacks, pots, vactrols and the power header are
  hand-soldered (`jlcpcb/README.md`).
- Vactrol build notes are silk inside each vactrol outline on the back: `SOLDER FIRST`,
  `TRIM FLUSH`, `LED 5mA` (fit the vactrol before its VOL pot).
- Nominal 3D fit of jacks and pots against both panels checked.
- All SMD parts are JLCPCB-sourced: Basic except the four 1 W 2512 resistors, the
  MCP6002 and the BAT54SW (user-accepted; live-checked 2026-11-14).
- Nothing is bench-tested.

| Path | Contents |
|---|---|
| `hardware/vca-mix.kicad_sch` | Flat root schematic (S6); PDF in `docs/vca-mix-schematic.pdf` |
| `hardware/vca-mix.kicad_{pro,pcb}` | Carrier: 39.3 x 110 mm, 4 layers, P6 placement, R3 manual routing (467 tracks, 82 vias, In1 GND / In2 +12V planes) |
| `hardware/VCA_MIX.kicad_sym`, `sym-lib-table` | Pinned stock symbols (`docs/schematic-symbols.json`) |
| `hardware/VCA_MIX.pretty`, `VCA_MIX.3dshapes` | Pinned footprints and jack model (`PROVENANCE.json`) |
| `hardware/_kicad_models/` | Vendored 3D models (`<sha256>/<name>`), bound via `${KIPRJMOD}` |
| `panels/front-pcb/vca-mix-panel.kicad_{pro,pcb}` | 8HP FR4 front panel: NPTH only, silkscreen labels |
| `panels/front-cad/` | FreeCAD printable panel (`.FCStd`, `.step`, `.stl`) generated from the panel PCB |
| `docs/research.md` | BM baseline, circuit, power budget, mechanics, decisions, sourcing |
| `docs/geometry.json` | Placement, panel and stack contract |
| `docs/sourcing-candidates.json` | Dated JLCPCB part records |
| `docs/fit/` | Native ERC/DRC JSON, nominal 3D fit report, renders |
| `jlcpcb/` | JLCPCB upload set (S6 / P6 / R3): Gerber ZIPs, BOM / CPL, manifest, README |
| `tools/` | Footprint import, schematic and layout generators (`build_layout.py` writes the unrouted base and the panel), fit check, `d10_exclusions.py` (the 15 approved vactrol / VOL-pot DRC exclusions), `kicad-project.json` |

## Front panel

```
           VCA-MIX
  IN1      CV1                per channel: IN and CV jacks,
                    VOL       OUT under CV, RANGE under IN,
  RANGE    OUT1               VOL alone on the right
  IN2      CV2
                    VOL
  RANGE    OUT2
  IN3      CV3
                    VOL
  RANGE    OUT3
  MIX
```

Rebuild (from `modules/vca-mix`). The carrier is routed by hand, so the native PCB owns
the SMD placement and the copper: `build_layout.py` refuses to overwrite it. Run the full
sequence only to start a new board from the unrouted base.

```sh
python3 -B tools/import_footprints.py          # one-time library import (pcbnew)
python3 -B tools/build_schematic.py            # schematic + pinned symbols
python3 -B tools/build_layout.py --panel-only  # 8HP panel (without the flag: unrouted P6 base, refused on a routed board)
freecadcmd panels/front-cad/build_front_panel.py
tools/fit_assembly.sh                          # nominal panel/carrier 3D fit
(cd ../.. && python3 -B opt/kicad-tools/kicad_tools.py check --config modules/vca-mix/tools/kicad-project.json \
   --reports modules/vca-mix/research/check-NEW)
```

A rebuild is reproducible except for UUIDs that KiCad assigns itself (schematic
pin/wire items after `sch upgrade`, PCB items from pcbnew). Same nets, placement and
fields; review diffs by content, not by bytes.

Read [`Code.md`](Code.md) before changing hardware.
