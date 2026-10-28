# busboard — 8 x 16-pin Eurorack bus for the case floor

Passive power bus board that lies on the case bottom plate under the modules
(`case/tools/build_case.py`, 42 HP default). Eight shrouded 16-pin IDC box
headers, every pin in parallel, Doepfer A-100 pinout:

| Pins | Net | Copper |
|---|---|---|
| 1, 2 | -12V (red stripe) | 1.5 mm, F.Cu + B.Cu |
| 3-8 | GND | 1.5 mm, F.Cu + B.Cu, plus GND pour on both layers |
| 9, 10 | +12V | 1.5 mm, F.Cu + B.Cu |
| 11, 12 | +5V | 1.5 mm, F.Cu + B.Cu |
| 13, 14 | CV | 0.5 mm, B.Cu (bussed only, not driven) |
| 15, 16 | GATE | 0.5 mm, B.Cu (bussed only, not driven) |

Feed it through any one header: the usb-power J7 16-pin harness or a rack PSU,
never both. The modules' 10-pin cables plug in at the pin 1 end (pins 1-10);
the shroud key and the board silk mark pin 1 / -12V at the top edge.

## Board

| Item | Value |
|---|---|
| Outline | 205 x 32 mm, 2-layer FR4 1.6 mm, no SMD parts; 1.5 mm from the header courtyards to the top and bottom edges |
| Headers J1-J8 | `IDC-Header_2x08_P2.54mm_Vertical` (shrouded box header, THT), 22.5 mm pitch, 12.6 mm finger gap between shrouds |
| Mounting | 4 x M3 NPTH (3.2 mm), two per end beside J1 / J8 within the header height: X 4.5 / 200.5, Y 5.5 / 26.5 (from the top-left corner), 196 x 21 mm pitch to match the case bottom plate |
| Edge keep-out | `min_copper_edge_clearance` 1.0 mm; closest courtyard 1.03 mm (holes), headers 1.48 mm (top/bottom) |

## Fit in the case (42 HP, 60 mm side panels)

- The board lies flat on the bottom plate top, centred between the side panels
  and the rails. Its ends sit on the plate's solid 20 mm frame at each side panel
  (3.7 mm from the inner socket walls); between them it spans the centre pocket
  on 7 printed ribs (4 mm, under the gaps between the headers), so the header pin
  tails hang into the 3.8 mm pocket.
- 4 x M3x8 socket head bolts from under the plate (counterbored holes, 196 x 21 mm,
  8.65 mm from the hole centres to the pocket edge, in `case/tools/build_case.py`
  `BUS_*`) into 4 x M3 nuts on the board top.
- Box header tops about 15.7 mm above the plate top; the clear height up to the rails is
  58.4 mm. Module depth and cable bend are not checked against this.

| Path | Contents |
|---|---|
| `hardware/busboard.kicad_{pro,sch,pcb}` | Native project: S1 schematic, R3 routed board |
| `hardware/Busboard.{kicad_sym,pretty}` | Pinned stock KiCad 10 symbol / footprints |
| `tools/build_schematic.py`, `tools/build_layout.py` | Generators (schematic; placement, straight bus tracks, GND pours) |
| `tools/kicad-project.json` | Shared check profile |
| `jlcpcb/busboard-gerbers.zip` | Gerber/drill ZIP (2 layers, 1.6 mm, no assembly: headers are hand-soldered) |

## Regenerate and check

From `modules/busboard`:

```sh
python3 -B tools/build_schematic.py
python3 -B tools/build_layout.py
python3 -B ../../opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json --reports research/<new-dir>
python3 -B ../../opt/kicad-tools/jlcpcb/export.py hardware --board busboard \
  --manifest jlcpcb/source-sha256.json --overwrite -o jlcpcb
```

R3 check: ERC 0, DRC 0 (warnings included, no exclusions), unconnected 0,
schematic parity 0, ref/pin/net parity equal; the four M3 holes are mechanical
footprints without a reference. Both GND pours are one piece each. Nominal
geometry only; not supplier-accepted, not built.
