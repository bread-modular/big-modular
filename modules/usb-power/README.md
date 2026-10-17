# usb-power — LDO-R1 prototype

USB-C PD Eurorack power module. KiCad project: `hardware/usb-power.kicad_pro`.

**Canonical PCB integration complete; capacitor-closure 043 current.**
Current source: 107 electrical+4 mechanical footprints,585 tracks,207 ordinary 0.300 mm plated through vias,
8 zones; unchanged passive panel and fixed USB/retry/redLED/output interfaces.

```
9V PD -> TPS26600 -> TPS54302 MID -> TPS65131 raw+13.537/-13.929V
                                        -> TPS7A4700/TPS7A3301 -> quiet +/-12V
                 -> independent TPS54302 -> final+5V (no LDO)
```

- [Schematic PDF](docs/schematic.pdf) · [layout/review images](docs/ldo-review/)
- [Recovered FAB snapshot + BOM/CPL](jlcpcb/) · [fabrication requirements](docs/fabrication.md)
- [Electrical/capacitor limits](docs/ldo-revision.md) · [build/check commands](docs/build.md)
- [Assembly geometry](docs/assembly-geometry.json) · [mechanical interfaces](docs/mechanics.md)
- LDO capacitor screen: IN+/OUT+/IN-/OUT- =12.359/23.990/12.359/11.400uF at
  15/12.4/15/12.9V; typical bias with tolerance/temp/aging allowances, NOT
  measured/guaranteed minima. The implemented 043 local plan adds 2x22u per VPROT
  buck (10.664uF screen), 3x22u local MID and P5 banks (27.631uF; 39.164kHz
  estimated crossover); bench/loop evidence remains pending.
- All components front-side (single-side assembly); C63-C67 on F.Cu. Bare-PCB fabrication
  plus a separate JLC assembly BOM/CPL; no assembly qualification, order/allocation approval,
  verified noise/PSRR/thermal/current or reverse/shutdown performance.
- Historical release archives were retired; shipping files live in `jlcpcb/`.
  Supervisor reviews/merges; no assistant commit/merge/push or vendor upload.

Current source/native checkpoint: [Basic passives + D10 DNP](docs/basic-swaps-checkpoint.md).
D10 is DNP: footprint/pads retained, not fitted or purchased; R32 remains fitted.
**Recovery status:** hardware, tools, tests, module instructions and missing docs are
recovered from this repository's accepted Git objects. Both PCBs are byte-identical;
only native filename/project identity metadata changed. `jlcpcb/` contains the intact
**STALE recovered 043 export snapshot**, not a fresh export of the migrated tree.
See [recovery provenance, comparisons and handoff](docs/migration-recovery.md).
No circuit, routing, current guarantee or assembly qualification changed.
