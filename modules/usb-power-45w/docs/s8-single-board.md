# usb-power-45w S8: single board, S8.2 schematic + P1.2 trial placement (review package)

> **Status (2026-11-01): S8.2 schematic (S8 final + the S8.1 review fixes + the S8.2 +5V crowbar, below) +
> P1.2 trial placement, NOT routed, not released.** 182 parts, every one on the F side of one 4-layer board,
> 100.5 x 48 mm (50 mm deep). Native ERC 0; DRC 0 violations / 0 warnings / 0 exclusions, schematic parity 0,
> 414 unconnected (nothing routed); shared `kicad_tools.py check` ref/pin/net parity equal; placement rules,
> mechanical contract and 3D collision screen clean; 30 module unit tests pass. The S7 system schematic and the
> routed R3 stack (BASE/TOP) are untouched. No fab export, no bench data, no current or power rating.

User directions (2026-11-01), in order: *"Design new schematics for a single board which remove all
these three eFuse but keep the LEDs for each rail [...] replace big caps with ceramic ones (only if
possible [...]). But do any pre-calculations etc."*, *"In this board add space for two IDC sockets."*,
then *"Remove each rail LEDs too. Also you can go upto 50mm depth for panel. Use single side for now.
Yeah. Don't route for now. But try to see the fit and etc. make them to the PCB, brackets and etc. So I
can get a review from someone else. Make the schematic final."*, then, after the external review
(conversation `a9d257b6`): *"Can you try to improve the board based on it's suggestion."*, then, on the
crowbar left open by S8.1 (*"A crowbar would short +5V to ground instead, so it stays near 1 V."*):
*"yeah. Do that"*.

## S8.2: +5V crowbar

Page 06, beside D21; 11 parts, 5 nets (`CROW_SENSE`, `CROW_TRIP_N`, `CROW_DRV`, `CROW_GATE`, `_CROW_LATCH`).

| Part | Role |
| --- | --- |
| **Q11 TS1220-600B-TR** (ST, 12 A sensitive SCR, DPAK) | Across +5V: anode = tab (`USBPOWER45:TO-252-2` pad 2), cathode pin 1 GND, gate pin 3 (ST DocID027645 Fig. 1). Once fired it holds +5V at Vt0 0.85 V + 30 mOhm x I until the energy behind it is gone, then drops out below IH (5 mA) |
| **U22 TLVH432BIDBZR** + R101/R102 37k/10k 0.1 % + C68 1n | Trigger, powered by +5V itself (no V3V3): sinks when +5V > 5.83 V nominal (**5.70-5.98 V** over all corners), the U20 +5V guard ratio and its ~8 us RC. 18 V cathode (the rail can reach ~10 V before the SCR fires; TLV431 is 7 V abs max). DBZ pins CATHODE 1, REF 2, ANODE 3 (SLVS555N): the stock KiCad TL431DBZ numbers, checked by `verify_s8.py` |
| **Q12 AO3401A** + R103 3.3k | Gate driver: U22 pulls the Q12 gate low, +5V drives the SCR gate through **R104 2.2k** (R105 1k gate-cathode): 1.4 mA at the lowest trip = 7 x IGT max at 25 C, 3.2 x at -40 C. VGS -8.7 V at a 10 V rail (limit -12 V) |
| **Q13 MMBT3904** + R106 10k | Latch link: pulls `OV_N` low (wired-AND with U20) whenever Q12 drives the gate, so FAULT is set and U5 opens even when the crowbar collapses +5V before the guard comparator sees it. R104/R105 keep `CROW_DRV` >= 0.95-1.89 V before the SCR can fire; Q13 conducts from 0.6-0.93 V |

Why its own trigger and not U20's spare comparator (as S8.1 review point 7 suggested): U20 runs from V3V3,
which can collapse before the rack's +5V at power-down, and a V3V3-fed trigger could then fire the SCR into
a healthy rail. U22 cannot conduct below its threshold and needs nothing but +5V. U20 comparator 4 stays
spare; D21 stays.

**Shorted U3 high side, time-domain screen** (`calcs.json` `crowbar.hs_short_time_domain`): VIN ceramics
46 uF at 20 V, U5 at its 4.7 A limit until it opens, L2, the low-corner +5V bank (52 uF), D21, the U3
low-side body diode, D3, the SCR behind 15 nH / 5 mOhm of copper, no load. Explicit-Euler screen, not a
converter model:

| Case | Without crowbar (S8.1): peak / time above 6 V | With Q11: fires at / peak / time above 6 V | SCR peak / i2t / drops out |
| --- | --- | --- | --- |
| L2 3.3 uH, D21 VBR 7.0 V | 9.1 V / 50 us | 10.6 us / 8.4 V / **8.2 us** | 166 A / 0.14 A2s / 93 us |
| L2 saturated (1 uH) | 10.2 V / 29 us | 8.3 us / 9.8 V / **7.9 us** | 197 A / 0.14 A2s / 40 us |
| L2 3.3 uH, D21 VBR 6.4 V | 8.6 V / 41 us | 10.9 us / 8.0 V / **8.3 us** | 156 A / 0.13 A2s / 93 us |
| + 0.47 mF rack on +5V | 8.4 V / 65 us | 10.9 us / 8.1 V / **8.2 us** | 157 A / 0.18 A2s / still on at 300 us (+5V 0.9 V) |

- The crowbar does **not** lower the peak of the first microseconds: the rail passes 6 V about 3-4 us after
  a hard short and D21 holds it at 8-10 V until the 8 us RC, the trigger and the SCR turn-on fire Q11. It cuts
  the time above 6 V from 29-65 us to about 8 us.
- Within ~1.5 us of firing +5V is under 5 V. The SCR then carries the VIN charge and the L2 current (50-75 A)
  at ~2.5-3.5 V, falling to ~1 V, and lets go after 40-95 us with +5V near 0 V; D3 holds the remaining ring
  above -0.4 V. The fault latch keeps every rail off until RESET.
- A slower +5V overvoltage (open feedback resistor, +12V reaching +5V through a bad cable or busboard) fires
  it the same way; Q13 sets FAULT, U5 opens, and the SCR holds +5V near 1 V meanwhile.

**SCR stress (limits, not hidden):**
- Energy is small: i2t <= 0.18 A2s against 60 A2s; ITSM 110 A at 10 ms.
- **dI/dt:** the onboard ceramic bank (at 8-10 V when Q11 fires) discharges into Q11 at up to ~500-600 A/us
  in the screen, about 10 x the TS1220's 50 A/us rating (60 Hz repetitive, 125 C, IG = 2 x IGT; it also
  bounds the short-pulse surge rating, Fig. 11: ~250 A at 10 us). The screen is an upper bound (it has no SCR
  turn-on time, which slows the real rise), the anode sits at <= 10 V instead of hundreds of volts and Q12
  drives 3-17 x IGT max, but survival over repeated firing is **not** covered by the datasheet: bench gate. A
  crowbar SCR that fails, fails short: the rack stays protected and Q11 must be replaced.
- Double fault (latch link and guard both dead inside the 0.57 s startup window): U5 feeds its 4.7 A limit
  into the SCR, ~4.7 W, Tj +~30 C over 0.5 s on a +5V tab pour.
- Not rated: a second supply that keeps feeding the bus +5V (misconnection). The SCR then carries that
  supply's current limit until it fails (short).

**False firing:** the band minimum (5.70 V) sits 0.09 V above the stacked converter setpoint + N=16 load
release (5.62 V), the maximum 0.02 V under 6.0 V (the same narrow window as the guard). Power-up and
power-down cannot fire it (no V3V3 dependence); R105 1k and Q12 off (IDSS 1 uA) hold the gate near 0 V; the
8 us filter ignores switching spikes and short ringing.

Cost: +$2.18 per board (TS1220 $0.86, TLVH432B $0.92, AO3401A and MMBT3904 Basic; R101/R102 reuse the 0.1 %
37k/10k lines of R95/R96), 2 new Extended codes.
[TS1220](https://www.st.com/resource/en/datasheet/ts1220.pdf) · [TLVH432](https://www.ti.com/lit/ds/symlink/tlvh431.pdf)

## S8.1: review findings and what changed

| Review finding | S8.1 change / answer |
| --- | --- |
| 1. U20 pin 9 (`MON_OVN`) has no negative clamp; with V3V3 gone and the rack holding -12V it is driven toward -1.65 V (TI: -0.3 V input limit) | **D22 BAT54S** (same part as D15, one diode used, the other shorted as S7 D19/D20) clamps `MON_OVN` at GND: about -1.0 V open circuit through 9.2k, ~83 uA, so pin 9 stays above -0.24 V at 25 C. The -12V channel also no longer uses V3V3 at all (below) |
| 2. Guard thresholds far above the S7 cut-offs (16.6 / 6.5 V nominal, corners up to 18.45 / 7.22 V); SMAJ5.0A is not a 5 V clamp | **Own reference + tighter parts**: `REF_OV` = **U21 TLV431B** (1.224-1.259 V, -40..85 C) with R100 2.2k and C67 10u; **U18/U20 LM2901B** (offset 5.5 mV instead of 15 mV, drop-in); divider resistors **0.1 % / 25 ppm**. New trips below; every corner sits above the stacked converter setpoint + load-release peak and at or below 16 V (+12/-12) and 6.0 V (+5). D21 stays as a transient clamp and is documented as such |
| 2b. Opening U5 does not stop energy already stored behind it (failed-short converter switch) | S8.1 quantified it (`hs_short` screen): a shorted +5V high side can still lift +5V past 6 V unless the rack holds about 0.6 mF on +5V (~1.3 mF for the undamped bound); D21 then clamps it (6.4-7.0 V breakdown at 1 mA, up to 9.2 V at 43.5 A). **S8.2 adds the Q11 crowbar** (section above) |
| 3. Overloads between the 2.5/2.5/1 A targets and the converter limits are not cut | Unchanged, accepted trade-off of S8 (no per-rail eFuses) |
| 4. Ceramic-only operation and the "0.49 mF" -12V start-up figure | Calculation now reports **total** capacitance and the **rack allowance** after the onboard bank: -12V 0.40 mF at full 1 A load (2.0 mF at no load), +12V 1.14 mF, +5V 2.99 mF. Start-up into the real rack stays a bench item |
| 5. D10 heat, 50 mm depth, MAIN is status not proof | Unchanged (routing/bench items, review points 1 and 3) |

| Guard (nominal, all-corner band) | S7 eFuse / LM5067 OV | S8 | **S8.1** |
| --- | --- | --- | --- |
| +12V | 14.4 V | 16.58 V (14.86-18.45) | **14.88 V (14.48-15.27)** |
| +5V | 5.55 V | 6.50 V (5.84-7.22) | **5.83 V (5.68-5.98)** |
| -12V magnitude | 14.25 V | 15.10 V (13.92-16.36) | **13.64 V (13.27-14.02)** |

Corners: TLV431BI 1.224-1.259 V at 10 mA and up to 3.6 mV lower at the ~1 mA used here, LM2901B 5.5 mV /
50 nA, resistors 0.1 % + 25 ppm/C over 100 C, all at once. Margins of the band minimum above the stacked
converter setpoint + N=16 load release (capacitor-study model): +12V 0.54 V, +5V 0.06 V, -12V 0.16 V; margins
of the band maximum below 16 / 6.0 / 16 V: 0.73 / 0.02 / 1.98 V. The +5V window is deliberately narrow: the
setpoint and release corners leave 5.62 V at the bottom, 5 V logic parts (e.g. ATmega 6.0 V absolute max)
set the top. Comparator inputs sit at ~1.24 V at a positive trip, inside the LM2901B common-mode range
((V+) - 1.5 V = 1.73 V at 25 C); the -12V channel now compares `MON_OVN` with GND:
`MON_OVN = (REF_OV x 110k + V x 10k) / 120k` = 0.14 V at -12 V, 0 V at -13.64 V. U21 runs at 0.71-0.98 mA
(TLV431 needs 0.1 mA); C67 10u keeps it right of the TLV431 oscillation region (SLVS139Z Fig. 5-18) and
REF_OV settles in about 9-12 ms, before any rail can start (POR alone holds RUN low for >= 12 ms, then U5 and the converters ramp). TP17 = `REF_OV` for the bench.
[TLV431](https://www.ti.com/lit/ds/symlink/tlv431.pdf) · [LM2901B](https://www.ti.com/lit/ds/symlink/lm2901b.pdf) ·
[BAT54SL](https://www.onsemi.com/pdf/datasheet/bat54slt1-d.pdf)

U21 uses the stock KiCad TL431DBZ drawing with the pins renumbered to the TI TLV431 **DBZ** package
(REF 1, CATHODE 2, ANODE 3; the TL431 DBZ order differs). `tools/build_s8.py` derives it and
`tools/verify_s8.py` checks it against TI's pin table. U18 keeps `REF_GOOD` and all its thresholds; only its
part number changed so both comparators are one BOM line.

## For the reviewer: what to open

| What | File |
| --- | --- |
| KiCad project (schematic + board) | [`hardware/single/usb-power-45w-single.kicad_pro`](../hardware/single/usb-power-45w-single.kicad_pro) |
| Schematic PDF (overview + 6 pages) | [`usb-power-45w-single-schematic.pdf`](usb-power-45w-single-schematic.pdf) |
| BOM (165 placements, test pads excluded) | [`s8-single/bom.csv`](s8-single/bom.csv) |
| Placement drawing (references, courtyards) | [`s8-single/assembly/usb-power-45w-single-placement.pdf`](s8-single/assembly/usb-power-45w-single-placement.pdf) |
| 3D assembly: panel + board + brackets + M3 + IDC plug/ribbon envelopes (STEP, zipped) | [`s8-single/assembly/usb-power-45w-single-assembly.step.zip`](s8-single/assembly/usb-power-45w-single-assembly.step.zip) |
| Front panel (S8: MAIN LED only) | [`panels/front-pcb/usb-power-45w-single-panel.kicad_pcb`](../panels/front-pcb/usb-power-45w-single-panel.kicad_pcb) |
| Brackets (2 x printed L, unchanged) | [`panels/bracket/usb-power-45w-bracket.step`](../panels/bracket/usb-power-45w-bracket.step) / `.stl` / `.FCStd` |
| Pre-calculations / sourcing / checks | [`s8-single/calcs.json`](s8-single/calcs.json), [`sourcing.json`](s8-single/sourcing.json), [`validation.json`](s8-single/validation.json), [`board-p1.json`](s8-single/board-p1.json), [`mechanical.json`](s8-single/mechanical.json), [`assembly/assembly-report.json`](s8-single/assembly/assembly-report.json) |

![S8 P1 board, KiCad 3D view](s8-single/assembly/board-top.jpg)

*KiCad 3D view of the native board, panel edge at the bottom, J2/J3 at the rear edge. L1-L3 are drawn
with a 10 x 10 mm KiCad proxy model in this render only (the pinned SLO1040 footprint has no model).*

![S8 assembly, front-right](s8-single/assembly/iso-front.png)

## Schematic: what S8 is (216 S7 refs -> 182, 145 -> 82 nets)

**Removed from S7 (69 refs + 2 power flags, every one listed with its reason in `tools/circuit_s8.py`
`S8_REMOVED`):** the U6/U7 TPS16630 rail eFuses and their setting parts; the whole negative switch (U8
LM5067, Q4, shunt, VCC feed, optocouplers U16/U17, Q5, clamps, timer) and the U19 Schmitt buffer; and,
in S8 final, **every rail LED**: the panel LEDs D16/D17/D18 with R86-R88 and drivers Q7-Q9, and the local
SMD LEDs D5/D6/D7 with R19-R21.

**D8 MAIN is the only status LED** (R22, Q6, RUN-gated return Q10 unchanged). It lights when the input
is valid, U5 reports FLT/PGOOD good and RUN is high. Any rail below its monitor threshold after the
~0.57 s startup window, or any overvoltage, latches every rail off until RESET, so **MAIN off = not
working**. The rail status signals P12_OK / P5_OK / N12_OK now feed only the fault logic and test pads
TP12-TP14 (handy on the bench to see which rail failed).

| Change vs S7 | Detail |
| --- | --- |
| Rails | Converter outputs are the delivered rails (P12_RAW -> +12V, P5_RAW -> +5V, N12_RAW -> -12V); U5 is the only switch |
| Status | P12_OK / P5_OK / N12_OK = U18 comparator outputs, R35/R44/R62 10k pull-ups |
| Bulk caps | C5 47u can -> **R92 1 ohm + C5/C62 2 x 10u/50V** damper; C34/C35/C36 100u cans -> **22u/25V at J2**, plus **C59/C60/C61 22u at J3** |
| Outputs | **J2 + J3**, Wurth 61201621621, same pinout, in parallel (pin 1 = -12V) |
| Soft start / window | C9/C18 22n -> **100n** (11-20 ms); C49 1u -> **100n** (0.57 s typical) |
| Overvoltage guard | **U20 LM2901BIDR** on its own reference **REF_OV = U21 TLV431B** (R100, C67, TP17), 0.1 % dividers (S8.1): +12V > 14.88 V, +5V > 5.83 V, -12V beyond -13.64 V (nominal) -> OV_N -> U12 preset -> FAULT -> RUN low -> U5 off, also inside the startup window; **D22** clamps `MON_OVN`; **D21 SMAJ5.0A** transient clamp on +5V |
| +5V crowbar (S8.2) | **Q11 TS1220** SCR across +5V, fired by **U22 TLVH432B** (own 0.1 % divider, powered by +5V) through **Q12 AO3401A**; **Q13** pulls OV_N low at the same time |
| Monitors | U18 unchanged (REF_GOOD, same thresholds); part number LM2901DR -> LM2901BIDR (S8.1, one comparator line) |
| LEDs | D8 MAIN only (rail LEDs removed, S8 final) |
| Logic | U14 gate 2 unused (inputs to GND, output open) |

How each rail is protected now: shorts/hard overloads by the converters' own limits (TPS62933F
4.2-5.8 A peak, hiccup; LMR38020F 2.6-3.8 A, hiccup) and then the common latch (a rail below its
monitor threshold for ~1 ms after the startup window turns all rails off). **Accepted trade-off:** an
overload between the 2.5 / 2.5 / 1 A targets and the converter limit is not cut until the converter
overheats (165 / 163 C) and its rail sags. A shorted high-side FET or an open feedback resistor is
caught by U20 within microseconds of crossing its threshold (RC 8-9 us, comparator ~1 us, U5 shutdown
0.8-1.5 us). That is a threshold time, not a peak-voltage guarantee: the VIN ceramics behind U5 can still
push a shorted rail higher after U5 opens (`calcs.json` `hs_short`, S8.1 table above). On +5V the Q11
crowbar (S8.2) then shorts the rail about 8 us after a hard short; +12V has no crowbar (~0.02 mF of rack
capacitance keeps it under 16 V).
[TPS62933F](https://www.ti.com/lit/ds/symlink/tps62933f.pdf) · [LMR38020](https://www.ti.com/lit/ds/symlink/lmr38020.pdf)

Housekeeping: title blocks `S8.2`; every assembled part has LCSC/MPN/Manufacturer except the three manual
parts (D8 3 mm LED from user stock; J2/J3 Wurth 61201621621, hand-soldered). The six guard divider resistors
carry `Tolerance 0.1%` and `TCR 25ppm` fields (their values read like the 1 % parts on the sheet).

## Board P1.2: 50 mm deep, one side, placed, not routed

![S8.2 P1.2 face view](s8-single/img/board-p1.png)

*Face view from the F side (panel at the top, Z = depth down). Blue circles: bracket nut + 8 mm driver
keep-out; yellow: 2 mm hand-solder rings around J1, D8, J2, J3; thin green line: 1 mm edge band.*

**Outline:** the R1/R3 carrier (Y14..114.5, same bracket cutbacks and M3 holes, 4 layers, 1.6 mm) with
the rear edge moved from Z42 to **Z50 from the panel front** (48.4 mm behind the panel's rear face), so
the 50 mm limit holds whichever face it is measured from. J2/J3 moved back with it (pin 1 at Z44, same
Y76/Y107). Board 100.5 x 48 mm; usable area inside the 1 mm edge rule 4324 mm2; part courtyards 2900 mm2
= **67 % fill** (the two routed R3 boards are 64 %).

**P1.1 (S8.1 parts):** U21 + C67 sit above U20 (toward the panel), next to U20 pins 5/7/10, with D22 beside
them over C66/R99; the six OV divider parts moved 3.6 mm toward Y14 and D15 to the free spot in front of
R80 to make room; R100 fills the free slot of the R98/R99 column (now V3V3 -> R100 -> REF_OV -> R98 ->
MON_OVN -> R99 -> -12V in one line, C66/R98/R99/U20 pin 9 on one MON_OVN row); TP17 (`REF_OV`) joins the
rear test-pad row. Nothing else moved. The cluster is tight (0.03 mm courtyard gaps); the 0603s may be
re-rotated while routing.

**P1.2 (S8.2 crowbar):** Q11 (DPAK) lies along the front edge in the free front-right corner, 1.08 mm from
the edge and left of the right bracket cutback, leads (K, G) toward the trigger and the anode tab toward the
cutback; the divider R101/R102/C68, U22 and Q12 sit behind it, R104/R105 at the SCR gate pin, Q13 with
R103/R106 next to the U12 `OV_N` corner. The U11 start-timer group (U11, C49, C50, C52, R69-R71) moved right
into the space above the DPAK to make room; nothing else moved. Routing note: the tab needs a +5V pour
(thermal and surge path) fed with wide copper from the C20-C23 bank about 25 mm away, and a short GND return
from pin 1.

**Floor plan** (`tools/place_s8.py`, one block per function, positions in one reviewed table):

| Region | Block | Notes |
| --- | --- | --- |
| Front-left, behind J1 | USB-C PD (CH224A + Q2/Q3/D9/D11), F1, D1 TVS, D10, U5 main eFuse + UV/OV/ILIM/IMON/dV/dt, MAIN LED driver, always-on LDO U9 | The routed R3 BASE input block, same coordinates |
| Middle, in front of J2 | +12V cell (U2/L1) and +5V cell (U3/L2) | The routed R3 TOP +12V block reused for both TPS62933F rails; the +12V output column sits right under the J2 +12V pins |
| Middle-right, in front of J3 | -12V cell (U4/L3) | New compact inverting layout: C27/C25/C26 (VIN to the IC ground -12V) at pins 3/1, BOOT C28 between U4 and L3, SW 2.5 mm to L3, output row C29-C32 + C61 behind L3 at the J3 -12V pins, FB/RT/EN parts on the side away from SW |
| Rear strip | Header caps C34/C35/C36 (J2), C59/C60/C61 (J3), clamps D2/D3, TVS D21 | One row 3.9 mm in front of the pins they serve |
| Rear-left | Monitors U18 + OV guard U20 with their dividers, REF divider, guard reference U21/C67/R100 and clamp D22 (S8.1), bad-status filter U14/U15, VIN damper | Each divider/pull-up in a column next to its pin; status test pads (TP17 = REF_OV) in the rear row |
| Front-right | Latch / reset / timer logic U10-U13 around SW1; +5V crowbar Q11/U22/Q12/Q13 (S8.2) in the corner left of the right cutback | U10 (POR + RESET) right behind SW1; U11 timer group above the DPAK; RUN/ARMED/FAULT/V3V3/MAIN_OK test pads at the front |

**Placement checks** (`tools/check_s8_board.py` -> [`board-p1.json`](s8-single/board-p1.json)):

| Rule | Result |
| --- | --- |
| Every part on the board, on F, nothing parked | 182 / 182, 0 on B |
| Courtyard overlaps | 0 |
| Courtyards >= 1.0 mm from Edge.Cuts (cutbacks included) | pass, closest 1.08 mm (Q11), 1.10 mm (R105); J1/SW1/D8 keep their R1-approved panel overhangs |
| SMD pads >= 2.0 mm from hand-soldered THT pads | J1 2.88 (R3), D8 2.01 (Q6), J2/J3 3.89; SW1 (report only) 2.05 |
| Bracket nut + 8 mm driver circles | no courtyard inside; closest TP3 0.77 mm (Y22), L3 0.83 mm (Y106.5) |
| THT tails under the B-side bracket webs | none |
| J2 / J3 pin 1 vs contract | exact |
| Native DRC (all severities) / parity | 0 / 0; 414 unconnected = unrouted |

**Mechanics and fit** (`tools/mechanics_s8.py`, `tools/s8_mechanical.py` -> [`assembly-report.json`](s8-single/assembly/assembly-report.json)):

- Width: tallest parts J2/J3 9.1 mm (X13.2), L1-L3 4.0 mm; mated IDC plug envelope to X18.9 (1.1 mm
  inside the 4HP edge). A clip-type strain relief (16.3 mm) would overhang the 4HP edge (inherited M1 rule:
  no strain relief unless measured <= 14.8 mm).
- Depth: board and every part end at Z50 (deepest part body Z47.4, the header box); the ribbon leaves the
  plug toward +Z and continues to the bus.
- Brackets: the two unchanged printed L brackets (Y22 / Y106.5) bolt to the board's B face; screws, nuts
  and the nut-driver / pliers paths clear every part. **3D collision screen: 0 overlaps** between part
  bodies, brackets, M3 hardware, tool paths, IDC plug/ribbon envelopes, panel and rails.
- Panel: [S8 panel](../panels/front-pcb/usb-power-45w-single-panel.kicad_pcb) = the R3 panel minus the
  three rail LED holes/labels (USB-C, MAIN, RESET; DRC 0).

![S8 assembly, rear-left with brackets](s8-single/assembly/iso-rear.png)

## Review points (please comment)

1. **Case depth:** in the 60 mm case (bus plate 58.4 mm behind the panel rear, bus header tops 15.7 mm
   above it) the board's last 5.7 mm reach past the bus header tops, so the module must sit beside a bus
   header, not over it (or use a deeper case).
2. **-12V cell:** new compact layout (the +12/+5 cells and the input block reuse routed R3 layouts).
3. **Routing plan (next step):** In1 solid GND; In2 VIN under the converters; the rails between J2 and J3
   (about 31 mm) on wide F/B copper; D10 (about 2.4 W at full load) and the converters need copper and
   thermal vias on both outer layers.
4. **Panel:** RESET stays at Y69 (its approved position). With the rail LEDs gone it could move back to
   Y49.5 next to MAIN; that is a panel/edge-rule change, not done.
5. **Ribbon insertion force** acts on the rear edge, about 30 mm behind the bracket screws: support the
   board when plugging (out of the rack).
6. **D8:** no MPN (manual part, 3 mm red from stock, ~1 mA).
7. **+5V crowbar (S8.2, added):** see the S8.2 section. Open: survival of the SCR in the bank discharge
   (dI/dt above its rating in the screen: bench gate) and routing the +5V pour to the Q11 tab. The trigger
   is its own TLVH432B, not U20's spare comparator, so it cannot fire when V3V3 collapses first.
8. **Extended parts (S8.1):** the guard adds 5 Extended codes (TLV431B, LM2901B, three 0.1 % resistors)
   and drops LM2901DR. If fees matter more than the tight +12V/-12V windows, those two dividers can go back to
   Basic 1 % parts (same corner model with 1 % + 1 % TCR: +12V 110k/10k 14.05-15.74 V; -12V 120k/10k
   14.00-15.80 V); +5V needs the 0.1 % pair. S8.2 adds two more Extended codes (TS1220, TLVH432B).

## Pre-calculations (`s8-single/calcs.json`; S8.1 adds `ov_reference`, `ov_clamp`, `hs_short`; S8.2 adds `crowbar`)

Screening only: MLCC DC-bias, ESR and source corners are the capacitor study's bounded assumptions
([capacitor study](capacitor-study/README.md)); no converter loop is modelled; nothing here is bench data.

| Rail | Ceramic bank (effective, low-high corner) | Switching ripple | Load step | TI reference |
| --- | --- | --- | --- | --- |
| +12V | 6 x 22u/25V: 28.2-72.6 uF | 2.2 + 0.5 mV | 1.5 A: <= 112 mV | typ 15 / min 10 uF effective |
| +5V | 6 x 22u/25V: 51.7-116 uF | 0.7 + 0.5 mV | 1.5 A: <= 70 mV | typ 20 / min 10 uF effective |
| -12V | 7 x 22u/25V: 32.9-84.7 uF | 13-16 + 1.4 mV at 1 A | 0.5 A: ~154 mV | total incl. rack <= ~1000 uF |

| Screen | Result |
| --- | --- |
| VIN damper (Middlebrook, 216 source corners) | R92 1R + 2 x 10u: margin **11.1 dB** (47u can 8.1 dB, ceramics alone 3.7 dB) |
| OV guard (S8.1) vs load release (N=16) | guard 14.48-15.27 / 5.68-5.98 / 13.27-14.02 V; minimum above the release peak by 0.77 / 0.15 / 0.39 V (study setpoint) and 0.54 / 0.06 / 0.16 V (stacked setpoint corner); maximum under 16 / 6.0 / 16 V by 0.73 / 0.02 / 1.98 V |
| Guard reference REF_OV | U21 0.71-0.98 mA (needs 0.1 mA; the minimum includes the -12V divider at -20 V); settles in 9-12 ms; C67 10u right of the TLV431 oscillation region |
| MON_OVN clamp (V3V3 lost, rack holds -12V) | -1.0 V open circuit through 9.2k: D22 takes ~83 uA, U20 pin 9 at <= -0.24 V (25 C); S8 had -1.65 V and no clamp |
| Shorted high side after U5 opens (`hs_short`, lossless bound without crowbar) | VIN ceramics 46 uF at 20 V. +5V reaches > 6 V unless the rack holds ~0.6 mF on +5V (~1.3 mF undamped bound): D21 then sets the peak (6.4-7.0 V breakdown, 9.2 V at 43.5 A); +12V stays < 16 V with ~0.02 mF of rack capacitance (~0.12 mF undamped) |
| +5V crowbar (S8.2, `crowbar`) | trip 5.70-5.98 V (5.83 nominal): 0.09 V above the stacked peak, 0.02 V under 6.0 V; gate 1.4 mA at the lowest trip (7 x IGT max; 3.2 x at -40 C); latch link leads the SCR by 0.35-0.96 V; time-domain hard short: fires at 8-11 us, time above 6 V ~8 us (29-65 us without), SCR 156-197 A peak, i2t <= 0.18 A2s (60), dI/dt up to ~600 A/us (bound; rating 50 A/us: bench gate) |
| Soft start into the rack at full load | **total** (onboard + rack) +12V 1.21 mF, +5V 3.1 mF, -12V 0.49 mF; **rack allowance** after the onboard bank 1.14 / 2.99 / **0.40 mF** (-12V tightest; 2.0 mF total at no load; bench item) |
| Startup window | 0.57 s typical (>= 0.31 s screened) vs a 66 ms worst-case rail-up budget |
| Input budget | 54.9 W out -> ~64 W in = **3.2 A at 20 V**, 0.48 A under U5's 3.69 A minimum |
| IDC contacts | one header at 2.5/2.5/1 A = 1.25/1.25/0.5 A per contact: **use both headers above ~2 A on a rail** |
| TVS D21 | above its 5.0 V stand-off only at the stacked worst-case setpoint (5.26 V); milliwatts. A transient clamp, not a 5 V limit; in a hard high-side short it carries 21-56 A (0.5-1.8 mJ) for the ~8 us before Q11 fires |

Monitor thresholds (nominal): +12V valid > 9.98 V, +5V > 4.22 V, -12V beyond -10.05 V, input > 17.65 V.

## Sourcing and cost (`s8-single/sourcing.json`)

62 LCSC codes / 162 placements; parts **~$21.50 vs $27.12** for S7 (quantity-1 prices, before Extended
fees, setup, manual parts, PCB and shipping); 30 Extended codes vs 28 (LM5067, FQD13N06L, LTV-354T and
both cans gone; SMAJ5.0A added; S8.1: TLV431BIDBZR, LM2901BIDR for LM2901DR, and three 0.1 % resistors
added, 10u 0603 and 2.2k are Basic; S8.2: TS1220-600B-TR and TLVH432BIDBZR added, AO3401A and MMBT3904 are
Basic, R101/R102 reuse the 0.1 % 37k/10k lines). S8.1 was ~$19.32 with 28 Extended codes, S8 final ~$18.37
with 24. Manual parts: D8, J2, J3. Prices and stock are fresh live JLCPCB catalog lookups of every code on
2026-11-01 (LM2901BIDR 1750, TS1220-600B-TR 1413, TLVH432BIDBZR 887 in stock, enough for prototypes);
observations, not reservations.

## Checks run on this revision

| Gate | Result |
| --- | --- |
| Native ERC, all severities, root of 7 sheets | 0 |
| Flat sheet == S8 table / flat == hierarchy | exact / exact (182 parts) |
| `verify_s8.py` | pass: fields/pads/pins/NC, removals (incl. every rail LED), banks, damper, TPS3808, LM2901 and TLV431 (DBZ) pin roles, REF_OV / MON_OVN memberships, D22 clamp, 0.1 % dividers, guard bands over all corners against the stacked converter peaks and the 16 / 6.0 / 16 V limits, U21 bias, S8.2 crowbar (maker pin tables for TS1220 DPAK / TLVH432 DBZ / AO3401A / MMBT3904, net memberships, trigger powered by +5V alone, latch link on OV_N, trip band over all corners, gate >= 2.5 x IGT max, latch link ahead of the SCR), 512 latch/LED combinations + 6 scenarios |
| Native DRC (all severities) + schematic parity | 0 violations, 0 warnings, 0 exclusions, parity 0, 414 unconnected (unrouted) |
| Shared `kicad_tools.py check` (`tools/kicad-project-single.json`) | ERC 0, DRC 0 + 414 unconnected, ref/pin/net parity equal |
| Placement rules / mechanical contract / 3D collision screen | pass / no problems / 0 overlaps |
| S8 panel DRC | 0 |
| Unit tests (module) | 30 pass (S8.1 adds guard/clamp/TLV431 pin checks and two negative controls; S8.2 adds crowbar topology, TLVH432 pin numbers, the crowbar time-domain screen and three negative controls) |
| S7 / R3 files | byte-identical (no tracked S7/R3 file modified) |

## Open gates (before ordering)

1. Review comments on this placement, then manual divide-and-conquer routing per the root `AGENTS.md`.
2. Bench: start-up into real rack capacitance at full load (especially -12V), load steps and Bode with
   ceramic-only outputs, VIN step/release on long cables with several chargers, OV guard trip points
   (REF_OV at TP17 1.22-1.26 V; each rail driven slowly past 14.9 / 5.83 / -13.64 V) and no false trips
   on load release and start-up, unplug with the rack holding -12V (U20 pin 9 >= -0.3 V), single-rail
   shorts and the latch/RESET truth table, thermal at full load.
   **+5V crowbar:** raise +5V slowly from a current-limited supply (board unpowered): Q11 fires at
   5.70-5.98 V and `OV_N` goes low; no firing on load release, power-up, power-down, unplug or module
   hot-plug; fire Q11 repeatedly into the charged onboard bank (e.g. 20 shots) and recheck its VTM and
   leakage; one simulated high-side short on the routed board (+5V waveform, SCR survival).
3. Measured MLCC effective capacitance, IDC contact current with the chosen cable/busboard, SMAJ5.0A
   leakage at the real +5V setpoint, IDC plug height (<= 14.8 mm above F.Cu).

## Rebuild (from the repository root)

```sh
python3 -B modules/usb-power-45w/tools/build_s8.py            # schematic + pages (deterministic)
python3 -B modules/usb-power-45w/tools/mechanics_s8.py        # contract -> docs/s8-single/mechanical.json
python3 -B modules/usb-power-45w/tools/place_s8.py --write    # seed + P1.2 placement (refuses copper or KiCad edits)
python3 -B modules/usb-power-45w/tools/check_s8_board.py --out modules/usb-power-45w/docs/s8-single/board-p1.json
python3 -B modules/usb-power-45w/tools/build_s8_panel.py      # S8 panel
python3 -B modules/usb-power-45w/tools/s8_mechanical.py       # FreeCAD assembly, collision screen, images, placement PDF
python3 -B modules/usb-power-45w/tools/render_s8.py modules/usb-power-45w/docs/s8-single/img/board-p1.png --title '<title>'
python3 -B modules/usb-power-45w/tools/s8_calcs.py --out modules/usb-power-45w/docs/s8-single
python3 -B modules/usb-power-45w/tools/s8_sourcing.py --out modules/usb-power-45w/docs/s8-single/sourcing.json   # live lookups
kicad-cli sch export bom --fields 'Reference,Value,Footprint,${QUANTITY},LCSC,MPN,Manufacturer' \
  --labels 'Refs,Value,Footprint,Qty,LCSC,MPN,Manufacturer' --group-by 'Value,Footprint,LCSC,MPN,Manufacturer' \
  --ref-range-delimiter '' -o modules/usb-power-45w/docs/s8-single/bom.csv modules/usb-power-45w/hardware/single/usb-power-45w-single.kicad_sch
kicad-cli sch export pdf -o modules/usb-power-45w/docs/usb-power-45w-single-schematic.pdf modules/usb-power-45w/hardware/single/usb-power-45w-single.kicad_sch
python3 -B modules/usb-power-45w/tools/verify_s8.py --netlist <kicad-cli kicadxml of the S8 root>   # -> docs/s8-single/validation.json
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project-single.json --reports <new-dir>
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
```

`build_s8_board.py` only writes a seed (refuses placed parts or copper); `place_s8.py --write` refuses a
board with copper and a board whose placement was changed in KiCad after its last write
([`placement.json`](s8-single/placement.json)). Once routing starts, the native board owns placement.
