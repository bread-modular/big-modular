# Big Modular — LDO-R1 prototype

**Canonical PCB integration complete; capacitor-corrected prototype.**
93 electrical+4 mechanical footprints,536 tracks,196 filled/capped through vias,
8 zones; unchanged passive panel and fixed USB/retry/redLED/output interfaces.

```
9V PD -> TPS26600 -> TPS54302 MID -> TPS65131 raw+13.531/-13.921V
                                        -> TPS7A4700/TPS7A3301 -> quiet +/-12V
                 -> independent TPS54302 -> final+5V (no LDO)
```

- [Schematic PDF](docs/schematic.pdf) · [layout/review images](docs/ldo-review/)
- [New prototype FAB release](production/ldo-r1/manifest.json) · [fabrication requirements](docs/fabrication.md)
- [Electrical/capacitor limits](docs/ldo-revision.md) · [build/check commands](docs/build.md)
- [Backside clearance](docs/ldo-evidence/backside-fit.json) · [mechanical interfaces](docs/mechanics.md)
- Capacitor screen: IN+/OUT+/IN-/OUT- =12.592/23.990/12.592/11.995uF;
  typical bias with tolerance/temp/aging allowances, NOT measured/guaranteed minima.
- C63-C66 back-side, C67 front-side. Bare-PCB FAB only; no assembly qualification,
  order/allocation approval, verified noise/PSRR/thermal/current or reverse/shutdown performance.
- Historical production/hro-r1 is STALE for this circuit and untouched.
  Supervisor reviews/merges; no assistant commit/merge/push or vendor upload.
