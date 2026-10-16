# Big Modular — MCU-free 9 V PD electrical prototype

**INCOMPLETE / NON-OPERATIONAL / DO NOT POWER UP, FABRICATE OR CONNECT VALUABLE LOADS.**

The current circuit has127 components in seven functional child sheets plus a
navigation overview. This electrical revision removes the onboard ATtiny and UPDI,
retains all six conditioned voltage-sense channels, and exposes them through a
**keyed20-pin J8 DEBUG IDC**, alongside optional status/I2C/button monitoring. One ordinary red3mm LED is powered from final+5V through1k to GND; no blink or external LED control.

## Electrical architecture

```
USB-C -> F1 -> fused VBUS -> CH224A + AUX3V3 housekeeping/sensing
                        -> TPS26600 hardware UV/OV + PG/Q1 + JP1
                             -> TPS54302 MID -> TPS65131 direct +/-12 V
                             -> independent TPS54302 +5 V
                             -> J7 landing -- flying-lead harness -- J2 power OUT
J8 DEBUG ONLY: 6 protected senses + PG/FLT/I2C/button; no power-enable or LED-drive contacts
```

- [Electrical implementation and persistent blockers](docs/electrical-prototype.md).
- [J8 pin map, key/pin1, voltage ranges, current limits and no-backpower contract](docs/debug-interface.md).
- J8 is **20-pin DEBUG**, not the **16-pin Eurorack power output**. External3.3V
  controller inputs must be Hi-Z; outputs open-drain only, no external pullups or
  supply connection to AUX_MON. The interface is not galvanically isolated.
- Power/LED operation does NOT require J8 or a debugging MCU. Hardware PG and the
  independent7.878/10.781V nominal UV/OV window remain. JP1 stays OPEN only as an
  explicit prototype qualification inhibit; normal intended RUN is closed.
- R38/R40 give local MID/2 bipolar enable, not external/AUX-driven control. D10 is
  final P5 -> R32 1k ->red LED ->GND, showing+5V presence only, not all-rail health.
  D11/D12 and their two panel holes/PCB footprints are removed. SW1 stays an optional
  debug button, not a direct power bypass.
- Original BAT54WS and TLV9002 are retained. Bounded Basic candidates were not
  qualified substitutes; see the electrical note. No new broad sourcing or Economy
  eligibility/stock/allocation guarantee. Root `BOM.csv` is NOT an assembly/order CSV.

## Review deliverables

- [Native eight-page schematic PDF](docs/schematic.pdf), generated from
  `hardware/big_modular.kicad_sch`; [page guide](docs/schematic-guide.md).
- [Actual component index](docs/component-guide.md), `BOM.csv`,
  `docs/pin-net-audit.json`, and project-local symbol/footprint libraries.
- [Focused electrical checkpoint / verification](docs/electrical-validation.md).
- [Firmware retirement note](firmware/README.md): no target compiler/flashing needed.

## Mechanical state — single-lamp removal only

The existing2HP panel and100.5x30mm perpendicular carrier, plain M3 brackets,
USB/switch geometry, the original D10 3mm LED hole and J7 wire-landing geometry remain. The two obsolete LED holes/footprints alone are removed; other geometry is verified unchanged. Both PCBs have zero tracks/vias/zones. **No new component placement, full schematic-PCB synchronization, routing, Gerbers or CPL were performed.**
J8/new support parts are unplaced; debug connector fit/strain relief is unresolved.

J7 is carrier solder landing, not a purchased box header. J2 is the physically
separate off-board16-pin keyed male endpoint of that **one manual harness**, counted
once; not a duplicate active supply or duplicate JLC placement. Never connect
another active rack PSU. See [mechanics](docs/mechanics.md),
[assembly](docs/assembly.pdf), [M3 brackets](docs/m3-brackets.pdf),
[manual buying guide](docs/parts-buying-guide.md), and [interface reservations](docs/interface-placement.csv).
Prior mechanical reports/archives are historical; they do not certify this circuit.

## Sources / reproducible checks

Read `AGENTS.md`, `Code.md`, and the canonical local KiCad/JLC skills first.
Only this Big Modular workspace is modified. No commits, merges, vendor uploads,
orders, routing or external reference-checkout access are part of this task.

Authoritative sources: `tools/electrical_design.py`, `tools/build_project.py`,
`tools/render_schematic.py`, `tools/electrical_checks.py`.
The hierarchy now has directional ports attached to component wires, a wired power-flow
overview, local support/debug wiring and a pin-for-pin output harness. See
[layout verification](docs/schematic-layout-verification.md); electrical blockers remain unchanged.

```sh
python3 -B opt/kicad-tools/kicad_tools.py doctor --config tools/kicad-project.json
python3 -B tools/build_project.py --schematic-only --output research/new-candidate
# Verify a NEW candidate, then promote only approved schematics/libraries/BOM/audit.
python3 -B opt/kicad-tools/kicad_tools.py check --config tools/kicad-project.json \
  --only erc --reports research/new-native-check
python3 -B -m unittest discover -s tests -v
python3 -B tools/verify_project.py --netlist research/new-native-check/netlist.xml \
  --output research/new-verification.json
kicad-cli sch export pdf hardware/big_modular.kicad_sch --draw-hop-over -o research/new-schematic.pdf
git diff --check
```

Native checks retain real findings and explicit schematic-PCB parity failures; they
never synchronize the boards to make a check pass. ERC is not electrical safety,
noise qualification, a continuous output rating or fabrication approval.
