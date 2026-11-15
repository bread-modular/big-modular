# Case print files

Everything printable for the 42 HP / 60 mm skiff case, grouped by what it is. Each
printable part comes as **3MF, STL and STEP**; 3MF files are geometry only, not saved
slicer profiles. Do not print the assembly previews. Native models are in
`mechanical/case/cad/`, renders in `mechanical/case/renders/` (same folder names), and the
generators in `mechanical/case/tools/`.

## One case

| Folder | What it is | Print per case |
| --- | --- | --- |
| [side-panels](side-panels/README.md) | Left and right side panels, each with the four M3 spacer sockets the stand plates bolt onto | 1 left, 1 right |
| [rails](rails/) | Front/back rail (one part, either way round) | 2 |
| [bottom-plate](bottom-plate/) | Floor plate the side panels stand in | 1 |
| [covers](covers/) | Slide-in front/back covers, six patterns, any mix | 2 |

`assembly-preview.step` is the assembled single case (reference only).

## Case sets (several cases sharing panels)

| Folder | What it is | Print |
| --- | --- | --- |
| [double-case](double-case/README.md) | Two cases side by side: one shared middle frame replaces the two inner side panels | 1 middle frame; keep the two outer side panels |
| [quad-case](quad-case/README.md) | Four cases, 2 x 2 in one plane: side panels and middle frame fused end to end | 1 fused left, middle and right panel |

## Stands

| Folder | What it is | Print |
| --- | --- | --- |
| [stands/angle-joiner](stands/angle-joiner/README.md) | Side stand plates: lower row flat, upper row at 60 degrees; bolt onto the side panel sockets (or the quad-case set as the upper element) | 1 left, 1 right plate |
| [stands/tiered-stand](stands/tiered-stand/README.md) | Older slide-in stand, 2 or 3 tiers (0 / 40 / 70 degrees), single-width cases only | per tier, see its README |

## Accessories

| Folder | What it is | Print |
| --- | --- | --- |
| [accessories/top-brace](accessories/top-brace/README.md) | 6 HP brace across the top of a double case (or a quad-case row) | 1 |
| [accessories/cable-holder](accessories/cable-holder/README.md) | Slide-in cover with a clip-on patch cable comb, for a tilted case | 1 cover + 1 comb |

Each README says what was checked and what is still untested.

## Rebuild

In this order (each set reads the saved CAD of the ones before it):

```sh
mechanical/case/tools/build.sh                     # case: side-panels, rails, bottom-plate, covers
mechanical/case/tools/build_middle_frame.sh        # double-case
mechanical/case/tools/build_middle_brace.sh        # accessories/top-brace
python3 -B mechanical/case/tools/check_middle_brace.py
mechanical/case/tools/build_angle_joiner.sh        # stands/angle-joiner
python3 -B mechanical/case/tools/check_angle_joiner.py
mechanical/case/tools/build_quad_case.sh           # quad-case
python3 -B mechanical/case/tools/check_quad_case.py
mechanical/case/tools/build_stand.sh               # stands/tiered-stand
mechanical/case/tools/build_cable_holder.sh        # accessories/cable-holder
python3 -B mechanical/case/tools/check_cable_holder.py
```
