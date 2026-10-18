> **Status: SR2 schematic + current carrier/panel sources. Current native review
> is clean (ERC/DRC/parity 0); manufacturing exports are complete and
> regenerated; NOT supplier-accepted or order-approved. Prototype bench
> performance is NOT claimed.** See the [current review](docs/current-review/REPORT.md).

# usb-power

USB-C PD Eurorack supply: 9 V PD input, protected 9 V rail, positive boost,
TPS54302 inverting buck-boost for the negative rail, TPS7A4700/TPS7A3301 quiet
±12 V, and an independent +5 V buck.

```
USB-C PD 9V -> TPS26600 eFuse -> 9V -> TPS55340 -> PRAW (+13.5V nom)
                                   -> U3 TPS54302 IBB -> NRAW (-14.08V nom)
PRAW -> TPS7A4700 -> +12V (P12)    NRAW -> TPS7A3301 -> -12V (N12)
9V    -> U5 TPS54302 buck -> +5V (P5)
```

Canonical sources: `hardware/usb-power.kicad_{pro,sch,pcb}`,
`hardware/usb-power-panel.kicad_{pro,pcb}`, seven hierarchical sheets and local
libraries. Routing is derived from the 084 review baseline and carries 681 track segments and
246 through vias; the current carrier SHA and review status are recorded only in
`docs/current-review/REPORT.md`.

- U4/MID/TPS65131 and the dormant-positive circuitry are removed; R15 is reused
  in the U3 feedback divider. U3 is a direct TPS54302DDCR inverting buck-boost.
- D30 (SS34) is the positive-NRAW startup mitigation; C93, C62 and D10 are DNP.
- L1: TAI-TECH TMPC1205HP-220MG-D, 22 uH, C357250. L4/L5: Sunltech
  SLO1040H6R8MTT, 6.8 uH, C207852.
- `jlcpcb/` is the sole manufacturing-output location; see `jlcpcb/README.md`
  for the actual source hash and completeness. Regenerate with the shared
  exporter after PCB changes.
- Verification is native ERC/DRC with exact ref/pin/net/NC/field parity. There
  is no module unit-test suite.
- Bare board is the standard four-layer JLC04161H-7628 stack (1 oz outer / 0.5 oz
  inner), HASL, with ordinary 0.300 mm plated through vias. Holds are bench
  joint/void/thermal/EMI/startup/load qualification; loop/phase and zero-bias
  startup screens remain unqualified. Ordinary via wicking on prototype
  assemblies is an inspection point, not a supplier guarantee.

Design detail and limits: `docs/sr2-schematic.md`; screening arithmetic:
`docs/sr2-schematic-budget.json`; engineering constraints: `docs/engineering.md`;
build/mechanics: `docs/build.md`, `docs/mechanics.md`, `docs/fabrication.md`.
