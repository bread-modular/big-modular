# 3D-printed panel-to-carrier L bracket

Print **two** of `usb-power-bracket.stl` (already laid on the L profile, 10 mm
tall). `.step` (assembly orientation) and the editable `.FCStd` come from
`build_bracket.py` (see `../README.md`); dimensions are the `brackets` contract
in `docs/assembly-geometry.json`, identical to
`hardware/mechanics/corner_braces.scad`.

| Feature | mm |
|---|---|
| Foot (on panel rear) | 9.2 x 10 x 3.0 |
| Web (on carrier B.Cu) | 2.4 x 10 x 18.4 overall height |
| Panel hole, along Z | Ø3.2 at X6.3 (assembly X6.4), M3x8 pan/button + loose nut |
| Carrier hole, along X | Ø3.2 at Z13.4 (assembly Z15), M3x8 90° flat head |
| Countersink, outer X0 face | Ø5.0 x 0.9 deep; 1.5 mm material behind |

Mounted at panel Y22 and Y106.5. Measure the printed web: it must be
≤ 2.40 mm (L1 clearance budget in `docs/mechanics.md`); trim or reprint if
over. Plain nuts AF ≤ 5.5, ≤ 2.4 thick, no washers. No nut traps or inserts.
No physical-fit or strength qualification is claimed.
