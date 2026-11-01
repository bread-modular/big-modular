# Archived: monolithic R1 carrier (superseded, read-only history)

Moved byte-identically on 2026-11-01 from `hardware/usb-power-45w.kicad_{pcb,pro,dru}` so that the
main entry point `hardware/usb-power-45w.kicad_pro` opens the routed BASE board (see the module
[README](../../README.md#open-this-main-project)).

| File | SHA-256 |
| --- | --- |
| `usb-power-45w-r1-monolithic.kicad_pcb` | `8d772aac8b8b843be957e30d96f36781b0a514820cc4fec2ac5c3a484428a9f9` |
| `usb-power-45w-r1-monolithic.kicad_pro` | `875416df0b051821967c9d1600ea499d3cda82375745cddfa67166fa450c9e48` |
| `usb-power-45w-r1-monolithic.kicad_dru` | `1f9ab0b4651170bee49442912ce96fdd5f165028e6ade0c4b6c29efbd404a4fa` |

The M1/R1 perpendicular carrier: unrouted, most SMD parked off-board, still carries the removed
J3 (S6 circuit), so it does not match the S7 system schematic. It has no schematic of its own here
(the circuit is `hardware/usb-power-45w-system.kicad_sch`); the `.kicad_pro` is kept as it was
(its stale schematic record is history). Footprints are embedded, so the board opens without the
module libraries.

Read-only inputs: `tools/check_stack.py` (fixed base interface positions), `check_mechanics.py`,
`render_preview.py`, `build_assembly.py` (M1 preview). `build_layout.py` (carrier) and
`pcb45.save` / `r1_prep.py` refuse to write it.
