# Basic-passive native checkpoint — workspace037

**Source/native only; not a new fabrication or assembly release.** Base HEAD
`d0cc00212db695dacd7c6bc8952177468b4842c5`. The exact 72-path workspace034 transfer
(including two deletions) preceded this work. Its production outputs remain
PROVISIONAL/stale and were not regenerated. Historical `production/hro-r1` is untouched.

## Implemented and verified

- R4/R77/R78 = 470k + 82k + 10k; R8/R79/R80 = 5.6k + 220 + 220;
  R36/R81/R82 = 300k + 100k + 2k. All nine members Basic/Economy, 0603, 1%.
  Full independent-corner intervals remain 556380–567620, 5979.6–6100.4 and
  397980–406020 ohms. Internal nodes each have exactly two pins; RTN is not GND.
- Approved source selections implemented, including R10 C20165687 explicitly 0.1%,
  R6 exact806k Extended, precision dividers retained, Samsung C14860 X7R (not X5R),
  and all17 exact C12891 LDO capacitors unchanged in value/count/MPN/front pose.
- C10 = FH0402CG4R5C500NT/C501829, 4.5pF ±0.25pF/50V/C0G, authorized0402.
  Same anchor and endpoint nets; only four attached trace endpoints adjusted.
  Manufacturer-authored FH mirror confirms two-terminal nonpolar size/encoding.
  C11 =4.3pF±0.25pF; C14=4.7nF±5%, exact approved YAGEO codes.
- D10 is **DNP, not a manual purchased/fitted part**. Footprint/pads/circuit retained;
  R32 remains fitted1k. All-reference design BOM retains D10 with `DNP=yes`.
  This supersedes older manual-LED wording and mechanical-builder assumptions.
- J1/SW1 have source codes and no manual assembly exclusion. J1 must retain native
  through-hole classification because of its plated shell slots despite SMT contacts;
  later assembly export must explicitly include this hybrid connector. Shell soldering,
  SW1 J-lead/case-paste process and supplier preview remain release gates, not quote approvals.
- Canonical native ERC/DRC/warnings/exclusions/opens/parity: **all0**. Independent
  318-pin check includes43 NCs;792 fields,233 reviewed pins,59 visible-wire checks.
  Generator reproduces the native schematics, design BOM and pin audit exactly.
- 99 electrical-design refs +4 mechanical footprints;98 non-DNP design refs including
  J7 cable lands, **97 purchased fitted parts/board**. 99F/0B;0 B.Paste apertures;
  552 tracks,201 ordinary0.300mm unfilled/uncapped through vias,8 unchanged zones.
  Courtyard/access/connectivity checks pass. Original poses remain except R4; all
  converter power routing, panel/outline/brackets and LDO-bank placement are retained.

## Bounded engineering disposition

OVP disconnect does not clamp VIN9. UV-network resistor-only screens include9.45V,
21V erroneous-PDO,62V and70V fault/transient envelopes; maximum member stress is
58.731V/7.366mW, not a whole-board70V rating. ILIM uses TI1V typical and4V operating/
5V absolute pin screens (max3.877mW); MODE uses conservative5V (max0.047mW).
All are below75V/100mW at70°C and a conservative20mW derated design allowance;
actual local temperature/pulse qualification remains unmeasured. Pin-side ILIM routing
is unchanged; added settings parts are local to U2 and no switching nets were rerouted.

C10/C11 retain nominal feedforward time constants6.8544/7.525us across full upper
resistor legs; absolute capacitor tolerances and layout parasitics still require
prototype stability/transient checks. C14 retains TI's typical4.7nF CN role.
Samsung's exact C14860 reference sheet confirms X7R±15% temperature behavior and
warns about DC bias/aging; it does not establish an exact guaranteed effective-C curve.
C4 is eFuse output bulk; C5/C18 buck input decoupling; C16/C17 bipolar input decoupling.
Their unchanged10u nominal is not asserted to equal10u effective or prove TI's local
input-cap recommendation. Existing LDO-bank screening is unchanged, not requalified.
R12 CPF B/E encoding supports0.1%/25ppm; the older family resistance-range table does
not cover this exact1.5M/25ppm corner, so exact-MPN primary range confirmation remains
an explicit limitation rather than a fabricated approval.

## Release-worker boundary

`research/basic-passives/` holds canonical reports, native inspection, network stress,
front/back views and the all-files patch/path-SHA manifest. Fresh `docs/schematic.pdf`
is schematic-only. No CAM, releases, assembly CSV adaptation, commits or merges here.
The broad regression suite was deliberately not rerun/repaired after the user's cost
stop: old93-part/count/frozen-sheet expectations and the known stale production source
freeze need release-worker reconciliation. Keep all checks strict. Enforce **zero D10
in fitted purchasing BOM and CPL**, retain it in design BOM, and re-export from this
exact source only after supervisor inspection. Catalog evidence is dated, not allocation;
97 fitted purchased parts are Economy-observed, with50 Basic/29 Extended R/C instances.
