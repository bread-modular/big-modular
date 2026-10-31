# S6 — per-rail protection, common reset and status LEDs

## Status and scope

S6 is an **eight-page native KiCad schematic**, not a PCB or a production release.
It builds on committed S5 (`859b77b`). No new commit, push, order or vendor upload
is part of this task. S4/S5 records are historical; the active architecture is here
and in `design.md`.

The circuit uses the **current main eFuse, TPS16630PWPR**, for both positive
output rails as requested. It does **not** silently restore TPS259470 at the USB
input: the earlier input-transient qualification issue remains unresolved for
that lower-voltage substitute. U5 and D10 are retained.

Implemented:

- U6/U7 TPS16630 output eFuses, independently limiting +12 V and +5 V.
- U8 LM5067MM-2/NOPB plus Q4 FQD13N06LTM for the negative conductor. Ground is
  continuous; a positive eFuse has not been reversed or inserted into ground.
- Always-on logic supply, power-on/manual reset supervisor, startup timer, stored
  ARMED state and stored FAULT state. A persistent fault after qualification
  disables all outputs and the main input switch until RESET or power cycling.
- Three additional hand-soldered panel LEDs, D16 (+12), D17 (+5), D18 (-12).
  Existing D8 is now MAIN status, not merely a +5 V presence lamp.
- Real hierarchical subpages and connected main power, feedback, setting,
  controller, timing, optocoupler and LED paths. Labels remain for distributed
  power/control and named inter-sheet interfaces, rather than a single huge sheet.
- Converter ICs, feedback ratios, inductors and compensation/output capacitors
  remain unchanged. Their output nodes are renamed P12_RAW/P5_RAW/N12_RAW.

## Current protection settings

| Path | Parts / setting | Nominal | Screened static interval |
|---|---|---:|---:|
| Shared input | U5; R5 3.3k + R29 1k | 4.186 A | 3.693–4.698 A |
| +12 V | U6; R34 6.8k | 2.647 A | 2.335–2.971 A |
| +5 V | U7; R43 6.8k | 2.647 A | 2.335–2.971 A |
| -12 V | U8; R48/R49 = 0.1 ohm in parallel | 1.000 A | 0.863–1.143 A |

Positive/main screens use a deliberately conservative ±10% current-limit allowance
and 1% resistor tolerance plus 100 ppm/K over 100 K, multiplied at corners. The
negative screen uses TI's 44–56 mV current-limit range with the same resistor
corners. The negative input protection resistor adds a small sense-bias error:
6 uA typical through 33 ohm is about 0.2 mV / 4 mA equivalent. The headline
interval is not a bound on unspecified bias drift or transients.

**These are not precision trip points or guaranteed continuous current ratings.**
A protected output can begin limiting below its old 2.5 A / 1 A load target.
The selected positive setting keeps the screened upper threshold below the
converter's nominal 3 A class, at the expense of not promising 2.5 A minimum at
every corner. Before thermal qualification, plan below the screened minimum
(e.g. 2.2 A on each positive rail and 0.8 A negative), with the shared input
budget still applying. These are planning allowances, not new product ratings.

U6/U7 MODE is open for local latch-off. Their FLT flags are combined with PGOOD
and voltage detection; they need not wait for the full internal current-limit
timeout to request common shutdown. Their internal protection remains active
while startup qualification masks common fault latching.

## Negative-rail implementation

- N12_RAW -> R48 || R49 -> Q4 source; Q4 drain -> delivered -12V.
- U8 VEE is N12_RAW. The controller's 13 V shunt supply is resistor-fed from
  **VIN**, through two parallel 10k / 250 mW resistors, not simply from ground.
  This supplies the required headroom at a -12 V operating rail. At VIN=16 V and
  |NRAW|=10 V, even a 13.65 V shunt leaves about 2.42 mA at the high R corner.
- R56 22k programs approximately **3.10 W MOSFET power limiting**. C44 1u gives
  approximately **0.67 s insertion delay / 42 ms local fault timeout**. These are
  typical values; wide timer-current, capacitor and power-limit tolerances apply.
- Q4 is a 60 V DPAK N-MOSFET, G1/D2-tab/S3. Its manufacturer DC/pulse SOA plot
  was inspected. The selected power limit has substantial room under the 25 C
  case curves at the intended 12 V fault, but hot-case/repeated-fault testing and
  copper thermal design are still required. An SOA graph is not PCB qualification.
- R89 and D19 protect the SENSE input against reverse collapse; R90 and D20
  protect OUT. This follows the LM5067 series-resistor/Schottky concept. The
  30 V BAT54S clamps are selected for this **local 12 V circuit**, not a 100 V
  application. Validate pin voltages and currents on input removal/backfeed.
  R90's disabled-state bias can shift the sensed OUT voltage; it is not a
  precision voltage sensor. The separate delivered-voltage comparator remains.
- U16 optically pulls UVLO toward VEE when RUN is low. U17 level-shifts PGD;
  U19 provides a Schmitt input for the slow 100k collector pullup. Logic ground
  never connects directly to the negative controller's UVLO/PGD reference.
- Optocoupler CTR is only specified at its stated current/voltage/temperature.
  Current budgets are deliberately small, but temperature/aging/saturation and
  actual switching delay must be tested. This is a release gate, not a waiver.

No rail protection here supplies reverse-current blocking. Q4's body diode and
positive eFuse behavior can allow externally supplied/charged outputs to backfeed
raw rails. Do not parallel independent supplies. An internally failed-short
switch/converter or external overvoltage is not guaranteed safe by these limits.

## Fault/startup/reset behavior

```text
VPD (before main eFuse) -> TPS7A1633 -> always-on V3V3
V3V3 POR + SW1 -> RESET_N
RUN = RESET_N AND NOT_FAULT
RUN drives main and positive-eFuse SHDN; NOT_RUN drives negative disable opto

TIMER_GO = RUN AND V20_OK
qualified TIMER_GO -> START_READY -> ARMED latch
ANY_BAD = NOT (MAIN_LED_OK AND P12_OK AND P5_OK AND N12_OK)
10k/100n + Schmitt -> BAD_FILTERED
ARMED AND BAD_FILTERED -> FAULT latch -> RUN low
```

U10's logic POR is about **2.916 V nominal**, with a checked high screening corner
below the minimum 3.3 V output assumption. RESET remains low for about **20 ms**
after releasing the button. Holding RESET disables all switches and clears both
latches. The button does not directly short an output rail.

U11 has a **5.7 s typical startup qualification window**. This accommodates the
negative controller's wide insertion-delay corners and startup charging without
immediately latching off because all outputs begin at zero. The outputs are not
held off for that whole window: positive rails can rise first and the negative
rail later. **This is common reset/shutdown, not simultaneous zero-skew turn-on.**
Local eFuse/current/power protection works during this interval. A startup fault
that is still present when qualification ends latches all rails off.

Once ARMED, falling START_READY or loss of input voltage does **not** erase the
armed state. Thus later input sag, missing rail, or eFuse fault can set FAULT.
Restoring the rail or letting a local auto-retry timer expire cannot restart the
board; only RESET or loss/recovery of the always-on logic supply clears FAULT.

The 10k/100n filter adds approximately millisecond-scale status deglitching, not
a guaranteed exact delay. IC FLT/PGOOD deglitch and optocoupler delays also apply.
Rapid faults still use each protection IC's local limiting/trip mechanisms.

### TPS3808 pin-map correction (2026-10-31)

The first S6 local `TPS3808G01` symbol numbered **SENSE = 3 and MR = 5**. For the
exact part, TPS3808G01DBVR (6-pin SOT-23 DBV), TI
[SBVS050N](https://www.ti.com/lit/ds/symlink/tps3808.pdf) Figure 5-1 / Table 5-1
gives **RESET = 1, GND = 2, MR = 3, CT = 4, SENSE = 5, VDD = 6** (same PDF SHA-256
as `s6-datasheet-sources.json`). As built, the analog POR/timer dividers drove the
real MR pins, so RESET could stay asserted and the board could never start.

Corrected (circuit table, local symbol, regenerated native library/sheets/PDF):

| Ref | Pin 3 (MR) | Pin 5 (SENSE) |
|---|---|---|
| U10 | RESET_BTN_N (was POR_SENSE) | POR_SENSE (was RESET_BTN_N) |
| U11 | RESET_N (was START_SENSE) | START_SENSE (was RESET_N) |

The symbol pins keep their drawing positions, so every wire, label and NC on page
06 is unchanged; only the pin numbers move. No other ref, net, field, value,
footprint or NC changed (native netlist compared against the previous commit).
The intended behaviour above is now what the pins do: SW1 and U10 RESET drive MR;
the 62k/10k and 33k/10k dividers drive SENSE.

`verify_design.py` now holds TI's DBV table separately from the circuit table,
the per-pin expectations and the symbol, and checks the native symbol pin names,
instance pin functions and pin roles (SENSE on the divider, MR on SW1 / U10 RESET)
against it. `tools/test_tps3808_pins.py` proves that the old self-consistent map
(symbol, circuit table and expectations all reverted, and the real pre-fix commit
`077905c` schematic) passes without that check and is rejected with it, as are the
mixed old-symbol/new-net and new-symbol/old-net cases.

This is a targeted repair, **not** a new full design review. No PCB, layout or
bench work exists; startup/reset behaviour still needs prototype testing.

## LED behavior

| Panel LED | Conditions to illuminate |
|---|---|
| D8 MAIN | RUN, V20_OK and main U5 FLT/PGOOD released |
| D16 +12 | RUN, delivered +12 voltage present, U6 FLT/PGOOD released |
| D17 +5 | RUN, delivered +5 voltage present, U7 FLT/PGOOD released |
| D18 -12 | RUN, delivered -12 voltage present, translated U8 PGD good |

Each has its own low-current driver and 1k resistor. Q10 gates the common LED
return with RUN: residual output capacitance cannot falsely keep a healthy lamp
on after common shutdown. All four use the always-on 3.3 V supply; the negative
LED does not borrow power from +12 V.

Typical voltage-presence thresholds are **+9.98 V, +4.22 V, -10.05 V**, and
**17.65 V for the 20-V-class input**. These are deliberately not precise
±5%-regulation indicators and are subject to the LDO/divider/comparator errors.
The main eFuse independently enforces its UVLO/OVP window. The detector is not
a PD protocol or available-current analyzer.

When a rail fails, its lamp goes out. Once the common fault latch trips,
**all three rail lamps and MAIN go out** because all switches were commanded off.
This is not a latched indication identifying the original faulty rail; diagnostic
pads expose individual status and the common latch. Original SMD D5/D6/D7 remain
on the **RAW** converter outputs for local debugging.

Output bleeders are present, but arbitrary external capacitors are not actively
discharged. No exact time-to-zero or complete module power-cycle pulse is claimed.

## Sourcing and cost

Fresh exact-code JLCPCB checks cover **57 codes / 195 sourced placements**;
raw timestamps and response hashes are in `s6-sourcing.json` and ignored research.
No stock is reserved and no authenticated supplier acceptance is claimed.

| Item | C-code | Observed stock | Quantity-1 catalog unit price |
|---|---|---:|---:|
| U5/U6/U7 TPS16630PWPR | C1849461 | 1,116 | $2.6926 each |
| U8 LM5067MM-2/NOPB | C181592 | 33 | $3.0793 |
| Q4 FQD13N06LTM | C236914 | 3,347 | $0.5163 |
| U9 TPS7A1633DGNR | C181239 | 474 | $2.6024 |

The main/positive eFuses meet the earlier sub-$3 IC target. **The selected negative
controller does not** at quantity 1 and has limited stock; it is a documented
procurement limitation, not advertised as equivalent stock/cost. The sourced
S6 parts total about **$27.24** on a quantity-1 quote basis, versus **$12.38** for
S5 using the same current prices: approximately **$14.86 added**. This excludes
manual LEDs/headers, setup, assembly, attrition, shipping and tax; it is not an
order quotation or an optimized production BOM.

New R/C choices are Basic and independently Economic eligible. The inherited
C5/C34/C35/C36 electrolytics remain Extended and an unresolved Basic-policy gate.
Other new ICs/opto/FETs may be Extended and incur feeder/setup fees. Manual parts
are J2/J3 and D8/D16/D17/D18. TP1–TP16 are copper only, excluded from BOM/placement.

## Verification and remaining gates

- Native root ERC: **0 errors, 0 warnings, no ignored checks** across all eight pages.
- Exact circuit-table/native ref, value, field, pin, NC and footprint pad-set parity.
- Exact flat-to-hierarchical electrical membership parity; only net paths change.
- Independent manufacturer-role checks for the eFuses, negative controller/FET,
  optocouplers, supervisors, dual flip-flop and voltage comparator. The TPS3808
  supervisors are also checked against TI's own pin table, and regression tests
  reject the earlier swapped SENSE/MR map (see the correction above).
- 256 settled digital combinations plus five persistent-fault/reset scenarios.
  These use native gate nets. They are **not** SPICE or physical timing proof.
- S5 preservation checks include 210 unchanged connections under explicit RAW
  net renames; converter power stages and footprints are unchanged.
- Shared inspect was attempted; unresolved `${KICAD10_3DMODEL_DIR}` remains its
  dependency blocker. Native CLI ERC/netlist/PDF gates are independent; the shared
  gate is not claimed passed. No PCB exists, so no PCB DRC/layout/EMI approval.

Before manufacture: verify exact footprint/package/courtyard and assembly choices,
qualified source/cable/PD contract, startup with actual rack capacitance/load,
all single-rail shorts and overloads, persistent/momentary rail loss, VPD sag,
reset while fault remains, repeated fault heating, reverse collapse/backfeed,
IC-pin transient limits, all four LED conditions, discharge and negative-loop
stability. Retain the S5 diode/connector/fuse supplier-document and thermal gates.
