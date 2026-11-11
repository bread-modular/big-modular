# Side panels — all current case variants

All original and current side-panel print sets are collected here, grouped so
identically named left/right panels from different designs cannot overwrite one
another. Each printable part is provided as **3MF, STL and STEP**; 3MF files are
geometry only, not saved slicer profiles. Do not print the assembly previews.

| Folder | Use | Parts to print |
| --- | --- | --- |
| [standard](standard/README.md) | Original standalone case | One left and one right panel per case |
| [middle-frame](middle-frame/README.md) | Two cases joined side by side | One shared open frame; keep the two outer standard panels |
| [angle-joiner](angle-joiner/README.md) | Two cases, lower flat and upper at 60 degrees | One left and one right joiner plate; two left and two right socketed side panels |

The angle-joiner set includes rounded rear feet with enlarged flat lands for
12 x 12 mm adhesive rubber pads. Its spacer-fit coupons, assembly preview and
verification reports stay with that set. The middle frame's rail-fit coupon and
reports stay with its set too. **Physical fit and strength remain untested.**

The middle-frame set also offers a one-piece [top brace](middle-frame/top-brace/README.md)
that caps the frame, following its top shape, and bolts to all four rails with
three holes per rail on the 2HP grid. It occupies 6HP in each case and can be
added without reprinting the shared frame.

The standard panels retain their original geometry; they do **not** include the
angle-joiner attachment sockets. Do not substitute them for the socketed panels.

Unchanged rails and bottom plates remain in `mechanical/case/print/`; covers and the
separate tiered stand remain in their existing folders. Native models remain in
`mechanical/case/cad/`. Rebuild tools now export directly into the folders listed above:

```sh
mechanical/case/tools/build.sh
mechanical/case/tools/build_middle_frame.sh
mechanical/case/tools/build_angle_joiner.sh
python3 -B mechanical/case/tools/check_angle_joiner.py
```

The old root-level side-panel files and old `mechanical/case/print/middle-frame/` and
`mechanical/case/print/angle-joiner/` folders have been moved here, not retained as duplicate
print sets. Quote paths containing `side panels` in shell commands.
