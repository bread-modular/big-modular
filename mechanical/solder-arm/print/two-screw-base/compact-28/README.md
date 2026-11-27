# Compact two-screw solder-arm clamp — flat desks 5–28 mm

**[Print one compact base and two short hand screws](print-this.3mf)** if your desktop measures **5–28 mm** at both screw positions. For a thicker desk (over 28 to 52 mm) or a mount that moves between desks of unknown thickness, [keep the full-height version](../print-this.3mf). Do not scale either plate. Every part above the base is the same for both sizes.

| Same P2S, 0.4 mm nozzle, 0.20 mm PLA, 35% infill | Full 5–52 mm | Compact 5–28 mm |
|---|---:|---:|
| Height of clamp body as installed, including teeth | 80.44 mm | 56.44 mm |
| Upper jaw / lower threaded land | 12 / 13 mm | 12 / 13 mm |
| Width / screw spacing along the desk | 112 / 80 mm | 112 / 80 mm |
| Screw length including knob | 72 mm | 48 mm |
| Wall loops | 5 | **6** |
| Whole-plate slicer estimate | 183.59 g / 5 h 43 min | **163.78 g / 5 h 4 min** |

**Why shorten rather than thin?** Removing 24 mm of the straight back takes out 34.94 cm³ of CAD volume without changing either jaw, its corners, the thread or the swivel. The extra wall loop still leaves the whole print **19.81 g lighter**. Thinning only the centre of the full-height back from 13 to 8 mm saved just 4.53 g at the same five-wall settings, and the frame flexed more when twisted in both simulation meshes. It is not a recommended full-height replacement.

## Printing and fitting

- **Set 6 wall loops, 35% crosshatch infill**; the 3MF is geometry only. Keep the orientation on the plate: clamp on its side, knobs down. The [verified slice](slice.json) uses Generic PLA, textured PEI, no support or brim. Select the corresponding settings for your own printer.
- If you have two spare [cable-holder end-clip screws](../../../../desk-cable-holder/print/end-clips/parts/hand-screw.3mf), [print just the base](base.3mf). Those longer screws were CAD-checked on this compact body across its 5–28 mm range; they project further below the desk.
- Allow the same **74 mm clear on top, 27 mm below the edge, 112 mm along it**. Get the first joint bolt into its keyed pocket **before** sliding the clamp onto the desktop. Follow the [same mounting instructions](../README.md#print-and-fit). Finger-tighten the two screws alternately. With the iron off and the board removed, gently check the arm at full reach. If it rocks, slips or bows, unload it rather than tightening harder.

## Evidence, not a load rating

- [CAD checks](verification.json): the full upper jaw and the translated lower jaw each have zero measured volume difference against the released full-size clamp. Both screws contact the desk throughout the sampled travel, with at least 8.3 mm of full thread overlap. The upper parts clear the body in all six arm poses; the two shorter screws are the same thread, knob and tip. [Installed FreeCAD assembly](../../../cad/two-screw-base/compact-28/assembly.FCStd) and individual print-oriented STEP/STL files are provided.
- [Frame comparison](frame-comparison.json): compared at equal loads with 3 mm and 2 mm brick grids, then checked at 2 mm with half the layer-normal modulus and a less stiff core. The selected six-wall compact had less modelled motion and no higher stress indicator in **each of eight cases on all three runs**. The lower-wall candidate did not meet that criterion. On the nominal 2 mm grid, the largest frame motion under equal screw loading was 39% lower, and when twisting the swivel it was 50% lower. This is not a global optimum or a measurement of printed breaking strength.
- Fixtures: either restrain two 8 mm-radius pads on the desk side and apply 100 N at each screw ring, 100 N at one only, or preload both and add pitch/roll/yaw; or restrain both lower rings and apply those three arm loads alone. The arm cases use a 10 N force and 2 N·m moment at the yaw ring. These are **comparison inputs, not recommended loads**. A trilinear brick model represents the outer walls and horizontal skins, with an effective sparse core. Compare work, maximum motion, material strain converted to tensile/von Mises stress, layer-normal tension, and raw peaks as well as the hottest 300 mm³. Contacts are simplified and the temperature, actual individual toolpaths, friction, layer failure, thread stripping and long-term creep are not solved. Neither base has been physically load-tested.

### Reproduction (from repository root)

```sh
fc=${FREECAD:-freecadcmd}
t=mechanical/solder-arm/tools
"$fc" "$t/compact_base.py"  # require COMPACT_BASE_PASS in output
python3 -B "$t/slice_two_screw_base.py" --compact
STUDY_PROXIES=1 "$fc" "$t/compact_base.py"
export OPENBLAS_NUM_THREADS=1
for h in 3 2; do
  python3 -B "$t/compare_frames.py" --grid "$h" --walls 5 stock lean8 short28
  python3 -B "$t/compare_frames.py" --grid "$h" --walls 6 short28 short36
  python3 -B "$t/compare_frames.py" --grid "$h" --walls 7 waist8-28
done
python3 -B "$t/compare_frames.py" --grid 2 --layer-ratio .5 --core-power 2 --walls 5 stock
python3 -B "$t/compare_frames.py" --grid 2 --layer-ratio .5 --core-power 2 --walls 6 short28
python3 -B "$t/report_compact_study.py"
```
