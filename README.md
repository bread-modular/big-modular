# Big Modular — autonomous 9 V V1

**V1 — unrouted / placement next**. Both native PCBs are updated and unrouted. USB/3mm power LED/retry form the top
cluster. All64 active footprints/nets are imported:4 fixed,60 staged off-board.

```
USB_VBUS -> F1 -> VIN9 -> TPS26600 UV/OV eFuse -> VPROT
                 CH224A fixed9V                 |-> TPS54302 -> MID -> TPS65131 +/-12V
                                               |-> TPS54302 -> final P5
J7 board output: -12V / GND / +12V / +5V; D10 red power LED on final P5 via 1k
SW1: press eFuse shutdown, release retry (UV/OV/current/thermal protections remain)
```

- No MCU, firmware, AUX regulator, PG permission transistor/jumper, sensing or debug header.
- Nominal voltage window: UV rising 7.878 V / OV rising 10.781 V, with hysteresis.
  This accepts a 9 V voltage, **not proof of a negotiated PD contract/current budget**.
- [Current schematic PDF](docs/schematic.pdf), [engineering decisions/sourcing](docs/engineering.md),
  [mechanical interface/pin map](docs/mechanics.md), [build/check instructions](docs/build.md).
- `tools/electrical_design.py` + `build_project.py` + `render_schematic.py` generate
  native sheets/libraries, `BOM.csv` and `docs/pin-net-audit.json`; BOM is not an order CSV.
- [Current assembly PDF](docs/assembly.pdf): unchanged outlines/M3 brackets; top USB
  axis Y33.5mm, red3mm LED Y43mm, retry Y49.5mm (panel-top coordinates).
  Cutbacks suit this bracket/M3 hardware, not all 90-degree face mounts; see [mounting](docs/mechanics.md#m3-bracket-face-mounting-and-current-cutbacks).
- V1 routing preparation only: place the60 staged components before routing.
  No routing, manufacturing exports, uploads or commits in this checkpoint.
