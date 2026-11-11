# Standard case side panels

These are the original, unchanged side panels for the current 42 HP case with
60 mm side-panel height. They were moved from `case/print/` into this folder.

- Print **one** `side-panel-left.3mf` (or `.stl`): includes the original 1 HP lip.
- Print **one** `side-panel-right.3mf` (or `.stl`).
- Matching `.step` files use the same supplied print orientation.
- Native full-case model: [assembly.FCStd](../../../cad/assembly.FCStd).

Preserve the supplied orientation and dimensions. Inspect rail notches, the lip,
hex pockets and any required supports in your slicer. The 3MF files contain
geometry only, not a material/printer profile.

For bolt-on angled plates use the [socketed side panels](../angle-joiner/README.md)
instead. For two cases side by side, see the [middle frame](../middle-frame/README.md).
See [all panel variants](../README.md).

Rebuild the standard case (including these panels) from the repository root:

```sh
case/tools/build.sh
```

Rails, bottom plate and the case assembly preview still export to `case/print/`;
only the standard side panels export to `case/print/side panels/standard/`.
