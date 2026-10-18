# Electrical design and engineering limits

Current topology: 9 V PD input -> TPS26600 protection -> TPS55340 positive boost
(PRAW) and U3 TPS54302 inverting buck-boost (NRAW) -> TPS7A4700/TPS7A3301
±12 V, with U5 TPS54302 +5 V. The former U4/MID/TPS65131 negative path and
dormant-positive circuitry are retired. `jlcpcb/` is exported from this source.
No bench, noise, thermal or current qualification is claimed.

## Autonomous start and retry

TPS26600 SHDN7 has an internal bias (2.0..3.4 V unloaded, table 7.5) and a 400k
internal pullup (block 9.2). No external pullup or load is needed: SW1 to RTN8
holds shutdown while pressed; release restarts and clears the thermal latch
subject to UV/OV. SHDN sinks >=10 uA at 0.4 V; recommended 0..4 V; the -0.3..62 V
absolute SHDN-to-RTN range is not permission to operate at VIN 9 V. Q1, JP1 and
the bias networks are removed.

SHDN does not drive the buck EN pins. U3 EN is explicitly biased by R91 100k
with R92 20k + R93 2k to NRAW (22k). U5 EN is as drawn on `03_bucks` and must be
confirmed in native before any change. FLT14 is NC. RTN and EP17 stay separate
from GND9; eFuse bias parts and SW1 return to RTN.

R4/R5 = 562k/100k UV rising 7.8778 V (falling 7.282 V nominal); R6/R7 =
806k/100k OV rising 10.7814 V (recovery 9.966 V nominal). Tolerance and leakage
bounds are recorded in `docs/sr2-schematic-budget.json`. 5 V fallback and
12/15/20 V inputs are rejected. R8 = 6.04k sets nominal 1.987 A (not 3 A);
R36 = 402k selects active current limit with thermal latch-off. The button is
retry, not a protection bypass or instant rail discharge.

Primary sources: [TI TPS2660](https://www.ti.com/lit/ds/symlink/tps2660.pdf),
[TI TPS54302](https://www.ti.com/lit/ds/symlink/tps54302.pdf).

## CH224A and sensing choice

CH224A fixed 9 V uses CFG1 6.8k; CFG2/3 are unused with internal pullups and PG10
is NC. WCH V2 table 4-1 requires VBUS8 shorted to VHV1; application 6.1 and
replacement 7.2.1 agree, and rating 8.1.1 lists VBUS/PG as 32 V-capable. The
isolated 3.8 V statement in 7.1 contradicts those three places; this design
follows the pin-specific rating and explicit manufacturer application, treating
7.1 as a documentation typo. PG is not pulled to VIN and is not used as a
permission signal.

Independent voltage acceptance replaces PG+Q1: **9 V presence is not proof of a
PD contract or available negotiated current**. Use a suitable 9 V PD source.
VHV1/VBUS8 routing remains real fused VIN9.
[WCH datasheet mirror](https://done.land/assets/files/ch224a_datasheet.pdf).

All sensing, U11 TLV9002, clamps/dividers/filters and J8 are removed. Using P5
would not fix residual negative-rail input injection when P5 disappears, nor
clamp backfeed or external 3.3 V ADC limits.

## Footprints and bounded sourcing

All active parts have local footprint assignments and are imported into the
carrier. Current magnetics:

- **L1 = TAI-TECH TMPC1205HP-220MG-D**, 22 uH ±20%, C357250, 5.0 mm max body;
  the SR2 inverter inductor.
- **L4/L5 = Sunltech SLO1040H6R8MTT**, 6.8 uH ±20%, C207852, 4.0 mm max body.

Both are Extended exceptions. Mechanical budget: 0.60 mm panel/bracket shift and
2.40 mm max web give 5.44 mm worst available against 5.40 mm needed; the current
mechanical review is pending. Hot saturation and thermal behaviour remain
prototype gates, not guaranteed ratings.

D30 (MDD SS34, C8678, SMA) was added for positive-NRAW startup mitigation.
D10 is DNP and not purchased; C62 and C93 are DNP. J7 is a manual wire landing,
not a purchased header. Basic R/C use exact Basic parts; precision R9/R10/R15/
R72/R74/R86/R87 and inherited R6 are explicit Extended exceptions, as are
L1/L4/L5. No stock, allocation or order claim follows from catalog snapshots.

## Routing and validation

Current routed source: 721 track segments and 251 through vias, all components
front-side (no B.Cu electrical footprints, no B.Paste apertures). B.Cu
routing/mask/drill remains. Preserve short hot loops, Kelvin feedback/returns and
the independent RTN island.

Validate start/stop, unplug, short and retry; output load/ripple; capacitor
effective C/DC bias; inductor and IC thermal; loop stability including DCM and
pulse skip; input/fuse coordination; and residual rail discharge. The negative
path has no output disconnect, so negative energy can remain with VPROT at 0 V.
No guaranteed continuous simultaneous ±800 mA rating, full-temperature 1 A
operation or manufacturing readiness is claimed.

Bare PCB: four-layer JLC04161H-7628 (FR4 Tg155, 1 oz outer/0.5 oz inner), HASL,
ordinary 0.300 mm plated through vias. No IPC-4761 fill, planarization or copper
cap. Barrel/paste intersections are prototype assembly-inspection points, not a
reason to add a via process. Canonical stack and jobs are defined in
[fabrication.md](fabrication.md); no supplier acceptance or physical trial is
inferred.
