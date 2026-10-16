# Big Modular — autonomous 9 V V1

Electrical routing preparation, **not a fabrication release**. Both PCBs remain
unchanged and unrouted; full schematic/PCB sync and mechanics belong to the next pass.

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
- USB must move to panel top with SW1/D10 nearby in the **later** mechanical pass.
  This revision performs no PCB placement, sync, routing, manufacturing exports or uploads.
