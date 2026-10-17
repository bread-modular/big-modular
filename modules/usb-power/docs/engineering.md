# Current LDO-R1 prototype

> Migration recovery: source/electrical content below is retained checkpoint evidence.
> `jlcpcb/` is a STALE recovered Git export snapshot, not a fresh migrated export.
> Run commands from `modules/usb-power`; shared `opt/` stays at repo root. See
> [migration-recovery.md](migration-recovery.md) for current checks and Astra handoff.

See [LDO revision](ldo-revision.md) for the current 040 checkpoint
raw+13.537080/-13.928806V, mixed 0.1%/25ppm retained dividers with 1%/100ppm
Basic substitutions, corrected4/6/4/3 capacitor banks and conditional prototype
limits. The 043 local-cap delta is implemented; `jlcpcb/` is exported from this
source. The old HRO-R1 release archive was retired. No bench/noise/thermal/current qualification.
The following V1 decisions remain the unchanged upstream/interface baseline.

# V1 electrical decisions / remaining engineering limits

## Autonomous start and retry

TPS26600 SHDN7 has an internal bias: 2.0..3.4 V unloaded (table7.5), internal400k
pullup in block9.2. No external pullup or load is needed: direct SW1 to RTN8 holds
shutdown while pressed, release restarts and clears the thermal latch subject to
UV/OV. Supports >=10uA sink at0.4V; recommended SHDN0..4V; absolute SHDN-to-RTN
-0.3..62V is NOT permission to operate it at VIN9. Removed Q1, JP1 and bias networks.
SHDN never drives both buck EN pins: those use their own TI-approved floating-EN
internal pullups (TPS54302 sections5/7.3.4; EN absolute max7V). FLT14 is unused NC.
RTN and EP17 remain separate from GND9; all eFuse bias parts and SW1 return to RTN.

R4/R5=562k/100k UV rising7.8778V (falling7.282V nominal), R6/R7=806k/100k OV
rising10.7814V (recovery9.966V nominal). Exact tolerance/leakage bounds are calculated
by verify_project.py. 5V fallback rejected; 12/15/20V rejected. R8=6.04k sets nominal
1.987A (not3A); R36=402k selects active current limit with thermal latch-off. Button
is retry, not a protection bypass or instant rail discharge. No power-up inhibit.

Primary sources: [TI TPS2660](https://www.ti.com/lit/ds/symlink/tps2660.pdf),
[TI TPS54302](https://www.ti.com/lit/ds/symlink/tps54302.pdf).

## CH224A and sensing choice

CH224A fixed9V uses CFG1 6.8k; CFG2/3 unused with internal pullups, PG10 NC. WCH
V2 table4-1 requires VBUS8 shorted to VHV1; app6.1 and replacement7.2.1 agree, and
rating8.1.1 explicitly lists VBUS/PG as32V-capable. The isolated3.8V statement in7.1
contradicts those three places; this design follows the pin-specific rating and
explicit manufacturer application, treats7.1 as a documentation typo, not a need for
an invented regulator. PG is not pulled to VIN or used as permission at all.
Independent voltage acceptance replaces PG+Q1: **9V presence is not proof of a PD
contract or available negotiated current**. Use a suitable9V PD source; no advertised
contract-current measurement/enforcement. VHV1/VBUS8 routing remains real fused VIN9.
[WCH manufacturer datasheet mirror](https://done.land/assets/files/ch224a_datasheet.pdf).

All sensing, U11 TLV9002, clamps/dividers/filters and J8 are removed. Using finalP5
would not by itself fix residual negative-rail input injection when P5 disappears,
or clamp backfeed and external3.3V ADC limits. Avoided extra isolation/supplies;
no5V-to3.3V-controller-safe claim, dead support nets, external controller or firmware.

## Footprints and bounded sourcing

All active parts have local footprint assignments and are imported into the carrier.
L1/L4 replaced the6.5mm Sunlord part, which cannot fit the5.1mm component-normal
allowance. KOHERelec MDA1040-6R8M C2847552:6.8uH +/-20%, body11+/-0.3 x10+/-0.3,
height3.8+/-0.2mm. Manufacturer A1 p1 visually checked: lands3.55 x3.5mm,
centres +/-4.475 (12.5 overall,5.4 inner gap). DCR22typ/24.5max mOhm.
Table labels are literally temperature-rise current Typ7.8/Max6.8A and saturation
Typ12.2/Max11A; lower numbers are conservative design values, NOT invented guaranteed
minimum ratings. Criteria: deltaT40C / L drop30%. Adequate nominal margin over3A;
V1 thermal/loop/current-limit testing remains required.
[Manufacturer PDF](https://datasheet.lcsc.com/datasheet/pdf/2d9718fdfc6265ae4f3f9130b857ccf7.pdf?productCode=C2847552).

L2/L3 CENKER CKCS6045-4.7uH/M C5291878,4.7uH±20% follows TI typical inductance;
Isat4.97A / rated3.30A; newer manufacturer maxDCR40.30mohm (31mohm is typical in
that table, despite old catalog max claim). Visually checked page1: F gap1.8mm,
G pad width2.4mm,H length5.7mm, centres±2.1mm;6.0±0.3mm body,4.7mm height max.
[Manufacturer datasheet](https://www.cenkersz.com/file/upload/product_series/SMD_Power_Inductor_CKCS6045_Series.pdf).
[TI TPS65131 application](https://www.ti.com/lit/ds/symlink/tps65131.pdf).

Exact sourcing evidence for all fitted purchased parts is recorded under
`research/assembly-evidence/` (dated public snapshots with URL/request/hash; the
previously sourced 035 lookups plus fresh strict-live lookups for the final changed
codes). C2847552/C5291878 remain Extended and Economy-observed; **none of this is
allocation, order or qualification**. D10 is DNP and is not purchased; J7 is a
manual wire landing, not a purchased header. Basic R/C use exact parts or the small
series networks R4/R77/R78, R8/R79/R80, R36/R81/R82, R10/R84, R18/R85 and
R72/R83/R73; retained precision R12/R14, R6 and the special feedforward capacitors
remain explicit Extended exceptions. Do not infer
all-part stock from catalog snapshots.

U4 footprint follows TI RGE0024B drawing4219013/A:24 lands0.60x0.25mm on0.5mm
pitch, opposing centres3.8mm; EP2.45mm square, four1.08mm paste apertures at±0.64mm.
Retired2.7mm-EP RGE0024H pattern is removed; current board footprint is synchronized.

## Routing / V1 validation

HRO USB-top UI and all64 footprints are placed/routed. Preserve short hot loops,
Kelvin feedback/returns and the independent RTN island. This task retained all
non-USB copper geometry and all197 non-USB native pin identities.
MID upper DC5.357V is below TPS65131
5.5V limit but does NOT prove transient headroom. Check startup/stop/short/fallback,
output load/ripple, capacitor effectiveC/DC bias, inductors/IC thermal, loop stability,
input/fuse coordination and residual rail discharge on the actual V1. No guaranteed
continuous simultaneous +/-800mA rating or manufacturing readiness is claimed.

### Source integrity (local review copies)
- tps2660.pdf: `b781cbce51984715771bde540df2b36404b4fae4b41e27166c84c19b6598e1de`
- tps54302.pdf: `1632b388d1ba3a46c8e8f090ddfec2114c0f538cfb8364ddcda583fee3fdbdc5`
- ch224a.pdf: `3961c67d7f277764ad3e095e2e83fc497ec1850bfc3d887e96198db312b1bfb8`
- tps65131.pdf: `e8360b9509047317416cfd9163a09d8cdf5c8accbd4e702ad6a43292ef48e0ed`
- sunlord-manufacturer.pdf: `f6add0cc224973d6a723875e6f68198874aa5c617d9c80b4641c7ee507afd41b`
- cenker-manufacturer.pdf: `10bd98836aa0fff546c424cba958d33f06c76d703ba7a35c897349fbf5b8992c`

## Historical HRO source checkpoint

Carrier421 segments,133 vias,4 zones. Exact HRO C165948 connector, native13-pin
paired-land symbol, BOM, local library and mechanical aperture are synchronized.
All other circuitry and physical poses remain unchanged; the strict preservation
report compares against the supplied e7e25d1a routed source. See
[HRO review](usb-hro-review.md) and [build/check commands](build.md).

All inherited optional DRC/ ERC ignores are now enabled. Five four-way junctions
become paired Ts with identical connectivity, not rule exceptions. J7/hole assembly courtyards and
exact selected-footprint filters close the resulting metadata warnings without
relaxing numerical constraints. Passive panel labels meet the existing0.8mm limit.
Full native/all-severity and regression evidence is retained in the workspace
handoff. Source verification is not an assembled/product safety qualification.

Bare-PCB release uses all201 through vias as ordinary 0.300 mm plated through vias
with solder-mask tenting where the artwork permits; no IPC-4761 fill, planarization
or copper cap is specified. Native shape and exported-CAM audits report93 actual
positive-area barrel intersections with exposed SMD copper and92 with paste, plus6
boundary/tangency cases. Those are prototype assembly inspection points, not a
reason to add a via process. Four-layer FR4 Tg170/35um copper/ENIG and separate
no-copper passive panel stacks, finished thickness and hole limits are explicit in
[fabrication.md](fabrication.md). Canonical native stacks and final jobs agree.
FAB/CAM evidence is in `jlcpcb/`; no supplier acceptance,
assembly/current/thermal/bench or physical trial qualification is inferred. No main
write/commit/merge/order occurred.
