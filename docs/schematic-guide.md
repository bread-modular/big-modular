# Current electrical hierarchy

Current `schematic.pdf`: eight pages,127 components, seven child sheets.
Read [electrical blockers](electrical-prototype.md) and [debug interface](debug-interface.md).

| Page | Native sheet | Function |
|---|---|---|
| 1 | `big_modular.kicad_sch` | Review navigation / cross-sheet connectivity |
| 2 | `01_input_protection.kicad_sch` | USB PD + always-on housekeeping |
| 3 | `02_hardgate.kicad_sch` | Independent UV/OV, PG and PG permission |
| 4 | `03_bucks.kicad_sch` | MID and independent +5V buck |
| 5 | `04_bipolar.kicad_sch` | Direct bipolar rails and local feedback |
| 6 | `05_diagnostics.kicad_sch` | Keyed20-pin J8 debug, optional status/button, one ordinary P5 power LED |
| 7 | `06_sensing.kicad_sch` | All six conditioned channels, TLV9002 and BAT54WS clamps |
| 8 | `07_output_rails.kicad_sch` | J7 carrier / cable boundary / off-board J2 power endpoint |

No MCU, UPDI or automatic indicator logic remains. Page6 defines actual components,
not a physical external-controller board. J8 is not Eurorack power. Local sensitive
feedback paths remain wired; full directional hierarchy/local-wire presentation is
deferred to a later pass. Schematics/BOM are current; mechanical PCBs are NOT synced.
