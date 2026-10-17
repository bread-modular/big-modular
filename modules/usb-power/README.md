> **Current schematic: SR2**, direct U3 TPS54302 IBB. [Review handoff](docs/sr2-schematic.md).
> PCB/project/export snapshots remain untouched and unsynchronized; dual reviews, corrections and explicit user ACK precede another PCB worker.

# usb-power — SR1 schematic review stage

**Schematics implemented; PCB intentionally OLD/UNSYNCHRONIZED. Not for fabrication.**

```
9V PD -> TPS26600 (~2A unchanged) -> TPS55340 -> PRAW -> TPS7A4700 -> P12
                                 -> TPS54302 MID -> TPS65131 negative -> TPS7A3301 -> N12
                                 -> independent TPS54302 -> P5
```

- Native root: `hardware/usb-power.kicad_sch`; new `06_positive_boost.kicad_sch`.
- [Exact implementation/review handoff](docs/split-rail-schematic.md), [corner/power/loop screens](docs/split-rail-schematic-budget.json), [source receipt](docs/split-rail-schematic-receipt.json), [bounded catalog evidence](docs/split-rail-catalog.json).
- Supervisor runs a separate Opus schematic review, shows images/findings to the user, then **waits for explicit user ACK before any PCB/synchronization/routing**. No delegation/review started here.
- 131 electrical references; same exact LDOs,9V/~2A protection, independent P5 and fixed interfaces. D10 and C62 DNP; R32 fitted; no D11/D12.
- Both PCBs/rules and four unaffected sheets remain byte-identical. Existing PCB has24 duplicate property UUIDs; no repair performed. New library-only RTE footprint resolves schematic ERC, not PCB acceptance.
- Historical [043 LDO handoff](docs/ldo-handoff.md), [recovery receipts](docs/migration-recovery.md) and `jlcpcb/` snapshot remain unchanged. **Exports are STALE**; no new fabrication/CAM/export work.
- DC/AC/loop/current/thermal/start-stop results are conditional screens, not bench qualification. See the tiny negative margin, transient and inherited non-Basic sourcing cautions in the handoff.
