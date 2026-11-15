# LADDER manufacturing export: none for S5 yet

The S5 / R1 board (6HP, pure analog, routed 2026-11-15) is **fab-reviewed (2026-11-15, `docs/research.md` section 9) but not exported
yet**, so there is no fabrication set here. The S3 / R2 / 10HP export that lived in this folder (exported 2026-11-10,
re-exported 2026-11-14, never supplier-accepted or built) described a board that no longer
matches the sources and was removed with the S4 redesign; it is in git history (commit
`b32225b` and before), together with its S3 sources.

A new export belongs to its own task, with the unchanged
shared `opt/kicad-tools/jlcpcb/export.py` (see `modules/usb-power/jlcpcb/README.md` for the
commands and promotion gates). Never hand-edit generated files.
