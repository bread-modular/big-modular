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

All64 active parts have local footprint assignments. Numeric pin/pad geometry is
checked independently. L1/L4 now Sunlord SWPA8065S6R8MT C334250,6.8uH±20%; Rev06
rates Isat min7.5A / Irms min4.5A, DCR max26mohm (catalog22mohm is typical).
Visually checked Fig4-1/table4-1: two2.2x7.5mm lands,3.8mm gap, centres±3.0mm;
body8.0±0.3mm, height6.5mm. [Manufacturer specification mirror](https://www.alfatec.de/fileadmin/productfiles/datasheets/sunlord_swpa8065s_series.pdf).

L2/L3 CENKER CKCS6045-4.7uH/M C5291878,4.7uH±20% follows TI typical inductance;
Isat4.97A / rated3.30A; newer manufacturer maxDCR40.30mohm (31mohm is typical in
that table, despite old catalog max claim). Visually checked page1: F gap1.8mm,
G pad width2.4mm,H length5.7mm, centres±2.1mm;6.0±0.3mm body,4.7mm height max.
[Manufacturer datasheet](https://www.cenkersz.com/file/upload/product_series/SMD_Power_Inductor_CKCS6045_Series.pdf).
[TI TPS65131 application](https://www.ti.com/lit/ds/symlink/tps65131.pdf).

Strict-live exact lookups captured10:30UTC: C334250 public654, C5291878 public2687,
both Extended / observed Economy eligible; **not allocation, order or qualification**.
Pinned catalog retains URL/time/request/hash. No broad sourcing/assembly pass claimed.
Remaining sourcing gaps: unresolved small capacitors/C1/C4/C5/C18 etc., R16 100ohm,
exact manual D10 and harness MPN, Basic/Economy exceptions on precise MID divider.
Do not infer all-part stock from these two checks or old snapshots.

U4 footprint follows TI RGE0024B drawing4219013/A:24 lands0.60x0.25mm on0.5mm
pitch, opposing centres3.8mm; EP2.45mm square, four1.08mm paste apertures at±0.64mm.
Retired2.7mm-EP RGE0024H pattern is removed; no PCB sync was performed.

## Routing / V1 validation

No PCB sync or placement: USB-top/button/LED mechanics are next. Keep hot loops short,
Kelvin feedback/returns and RTN island correct. MID upper DC5.357V is below TPS65131
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

## Verification checkpoint

58 project tests pass (0 failures/errors/skips); native ERC0 violations including
exclusions, full audit222 pins including NC,191 native connected component pins,
123 independent reviewed pins,31 local-wire checks,17 hierarchical ports and
64 numeric footprint maps. Generator determinism includes native libraries/BOM/audit.
Electrical delta:63 removed parts, no added parts, only26 documented pin changes
and pre-fuse/fused net renames. Both PCB SHA256 hashes unchanged;0 tracks/vias/zones.
Native PCB parity remains intentionally failing (unsynced carrier), not waived;
DRC not run in this ERC-only stage. Full evidence under research/v1/.
