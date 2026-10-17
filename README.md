# Big Modular — LDO-R1 prototype

**Canonical PCB integration complete; capacitor-corrected prototype.**
99 electrical+4 mechanical footprints,552 tracks,201 ordinary 0.300 mm plated through vias,
8 zones; unchanged passive panel and fixed USB/retry/redLED/output interfaces.

```
9V PD -> TPS26600 -> TPS54302 MID -> TPS65131 raw+13.531/-13.921V
                                        -> TPS7A4700/TPS7A3301 -> quiet +/-12V
                 -> independent TPS54302 -> final+5V (no LDO)
```

- [Schematic PDF](docs/schematic.pdf) · [layout/review images](docs/ldo-review/)
- [Current release manifest — exact source/PCB SHA](production/ldo-r1/manifest.json) · [assembly BOM/CPL](production/ldo-r1/assembly/) · [fabrication requirements](docs/fabrication.md)
- [Electrical/capacitor limits](docs/ldo-revision.md) · [build/check commands](docs/build.md)
- [Assembly geometry](docs/assembly-geometry.json) · [mechanical interfaces](docs/mechanics.md)
- Capacitor screen: IN+/OUT+/IN-/OUT- =12.592/23.990/12.592/11.995uF;
  typical bias with tolerance/temp/aging allowances, NOT measured/guaranteed minima.
- All components front-side (single-side assembly); C63-C67 on F.Cu. Bare-PCB fabrication
  plus a separate JLC assembly BOM/CPL; no assembly qualification, order/allocation approval,
  verified noise/PSRR/thermal/current or reverse/shutdown performance.
- Historical production/hro-r1 is STALE for this circuit and untouched.
  Supervisor reviews/merges; no assistant commit/merge/push or vendor upload.

Current source/native checkpoint: [Basic passives + D10 DNP](docs/basic-passives-checkpoint.md).
D10 is DNP: footprint/pads retained, not fitted or purchased; R32 remains fitted.
Current production/ldo-r1 has been re-exported from this exact frozen source with
JLC assembly BOM/CPL; old-count regressions were reconciled without weakening checks.
