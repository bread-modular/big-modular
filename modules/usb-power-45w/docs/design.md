# usb-power-45w — S5 schematic

**Schematic design, not built or production-qualified.** S5 raises the input-current limit for board protection,
not a 45 W adapter budget, and upgrades the series reverse-blocking diode. All three converter power stages, feedback
values, frequencies and individual rail design targets are retained from S3.

## Architecture and source contract

```text
USB-C -> F1 5 A / 63 V -> VPD -> D10 SS1060 -> EF_IN -> U5 TPS16630 -> VIN
                        |                                  PGOOD -> EN_P -> U2/U3
                        +-> D1 SMBJ22A -> GND
                        +-> R23/Q2/Q3 current limiter -> VPD_U1 -> CH224A
                                                     |-> D9 SMAZ24 -> GND
VIN -> U2 TPS62933F, 1.2 MHz, 6.8 uH -> +12 V
VIN -> U3 TPS62933F, ~2 MHz, 3.3 uH  -> +5 V
VIN -> U4 LMR38020F inverting, ~790 kHz, 15 uH -> -12 V (Q1 enable from +12 V)
SW1 -> U5 SHDN; D8 indicates +5 V presence. J2/J3 are parallel 16-pin outputs.
```

**Policy: protect the board's input path; do not constrain it to a 45 W adapter.**
The design still requests 20 V without an MCU or PD NVM programming. For full
load, use a negotiated **20 V / 5 A contract and a 5 A e-marked cable**, typically
from a dedicated 100 W-capable USB-C port. A multiport charger's total label is
not enough. Confirm the actual contract/cable with a PD analyzer.

S5 sets a **4.186 A nominal main-path overload threshold**. It is fixed hardware,
not a power target and not an automatic available-current detector. The threshold
is based on the **5 A class of the board's USB connector/input path**, allowing
for tolerances, auxiliary current and a static guard, rather than protecting a
small adapter. A weaker source can droop, trip, renegotiate or cycle under excess
load; the board does not automatically reduce its demand or reject low-current
20 V contracts. A defective source/cable is not made safe by this change.

The module's historical `usb-power-45w` name is retained. The unchanged rail
**targets** total 54.5 W; this is not a measured output rating or a 100 W-output
module. S4's 1.98 A / 26–29 W planning restriction is superseded.

## Input protection

### Main eFuse and reverse-current blocking

U5 is **TPS16630PWPR**, JLCPCB **C1849461**, HTSSOP-20 with exposed pad. The part has
60 V operating input capability, programmable UVLO/OVP, a typical 31 mOhm power
path, dVdt startup control, current limiting, and PGOOD. It does **not** include
reverse-current blocking; D10 explicitly supplies that function. The USB source
must not be connected to the eFuse OUT through its body diode when unplugged.

D10 is now **ZHIDE SS1060, C2917888, 60 V / 10 A, SMC (DO-214AB)** instead
of the small SMA SS56. Its anode remains VPD; cathode remains EF_IN. Its larger
package offers more thermal layout area; the 10 A nameplate is **not** permission
to draw 10 A through the module. Treat its dissipation as a PCB design constraint:

- Use **0.75 V at 5 A** for screening, from the available ZHIDE manufacturer-sheet
  mirror, rather than the catalog's more optimistic 0.70 V at 10 A. Use a
  conservative **125 C junction ceiling**. The documents differ in surge and
  temperature figures; do not use the catalog's larger surge number for signoff.
- At 3.5 A, budget **2.63 W**; at the screened 4.698 A threshold, **3.53 W**.
  At 50 C ambient, target effective junction-to-ambient thermal resistance
  **<=20 C/W** (21.3 C/W is the calculated ceiling at 3.53 W). This is a board
  requirement to achieve and measure, not a claimed package free-air rating.
- The sheet's **2 C/W is junction-to-case**, not junction-to-ambient. Its
  16 x 16 mm copper reference must not be treated as proof that the actual board
  achieves the required cooling. Use generous connected copper on both sides
  with thermal vias outside the SMD solder lands, and verify temperature.
- Verify cold/hot forward drop, reverse leakage, hot-plug and fault pulses using
  the actual ordered revision. At cold temperatures the screening drop is not
  a guaranteed upper bound.

The eFuse dissipates approximately **0.65 W at 3.5 A** or **1.17 W at 4.698 A**,
using the full-temperature 53 mOhm RON maximum, plus its supply consumption.
Its own thermal shutdown senses **U5**, not D10, F1 or the connector. Adequate
thermal-pad soldering, copper and external-part thermal qualification are required.

D1 is changed to **SMBJ22A, C10214**: 22 V stand-off, rated 35.5 V clamp at 16.9 A
for the specified 10/1000 us waveform. This provides input-voltage headroom for
the 60 V eFuse and avoids a 20 V stand-off device on a possible 21 V supply.
F1 is changed to **S1206-SD-5.0A, C553937**, 5 A / 63 V DC, 50 A interrupt rating.
It is backup fault protection, not an accurate 5 A electronic trip. Verify its
continuous-current derating, time/current curve and I2t against the actual board
ambient and fault pulses; a 5 A marking alone is not an all-temperature rating.

These are **not** declarations of a 60 V-rated module or IEC surge compliance.
The TVS is transient-rated; it cannot absorb arbitrary sustained high-voltage
sources. Cable/layout inductance, TVS pulse derating and U5's finite OVP response
must be validated. In particular, check the downstream TPS62933 VIN peak during
an already-powered surge; the eFuse's IN rating does not protect OUT by itself.

### Independently protected PD controller

CH224A sits ahead of U5 so it can negotiate before the main rails start. Its
VHV/VBUS limit is lower than D1's rated clamp, so both pins now connect to
**VPD_U1**, not directly to VPD.

- R23 = 33 ohm, Q2 = Nexperia BCX53-16,115, Q3 = MMBT3906LT1G form a simple
  two-PNP current-limited pass stage. Q3 senses the R23 drop and reduces Q2 drive.
  The current is approximately VBE/33, around 18–21 mA, **not precision regulated**.
- D11 (SS34) clamps VPD_U1 back to VPD on input collapse, preventing C1 from
  reverse-biasing the PNP base-emitter junctions. This small auxiliary-capacitor
  discharge path does not bypass D10 or backfeed the main bulk to USB.
- R27 = 10k / 250 mW pulls Q2's base down. It draws about 2 mA at 20 V and is
  sized for roughly 0.13 W at the main TVS's 35.5 V clamp.
- D9 = **SMAZ24-13-F, C155317**, shunts VPD_U1; C1 = 1 uF decouples it.
  The zener is 22.8–25.2 V at its 25 mA test current, not an ideal 24 V limiter.
  Its 1 W rating requires the datasheet PCB and thermal conditions; it is not
  a no-copper/free-air allowance.
- The active current limiter avoids forcing a large sustained current into D9
  from a low-value resistor during an overvoltage. For screening, 30 mA at 26 V
  is 0.78 W in D9 and approximately 0.3 W in Q2 at 35.5 V input. These are
  **assumed qualification points**, not guaranteed transistor current bounds.
- Give Q2 at least **1 cm2 collector-connected copper**, following Nexperia's
  thermal example. Its collector/tab is **VPD_U1, not GND**. Test a shorted U1
  supply at 21 V as well as overvoltage with an unloaded U1 branch. Target
  verification through 50 C ambient; do not claim a full-temperature system rating.
- Verify startup at the lowest supported attach voltage, 12 mA U1 load pulses,
  PD negotiation/voltage sensing with the pass-stage drop, hot-plug peak below
  **30 V at U1**, and absence of limiter oscillation with the actual C1.

**Manufacturer-specific pin map:** the pinned `BCX53_NXP` symbol uses the
Nexperia table-2 mapping **1=E, 2=C/tab, 3=B**. The installed KiCad `BCX53` symbol
points to an Infineon datasheet and uses **1=B, 2=C, 3=E**. They must not be
substituted by symbol name. The exact native symbol and physical pad map are
checked by `tools/verify_design.py`.

### Voltage window, ramp and fault behavior

UVLO uses R2 100k / R3 7.5k. OVP uses R28 10k + R4 120k over R24 6.8k.
Both sense VPD before D10. RESET no longer pulls the divider: it grounds the
separate, internally pulled-up SHDN pin.

| Threshold | Nominal | Screened range |
| --- | --- | --- |
| UVLO rising | 17.20 V | 16.23–18.23 V |
| UVLO falling | 16.08 V | 15.04–17.12 V |
| OVP rising | 24.14 V | 22.76–25.60 V |
| OVP falling | 22.57 V | 21.09–24.05 V |

The calculation includes threshold limits, +/-150 nA input leakage, 1% resistor
tolerance and 100 ppm/K over a 100 K temperature difference. The OVP **falling**
corner was checked as well: after a transient, even a valid 21 V input can
recover without needing a lower-voltage power cycle. A 15 V PDO's 15.75 V upper
corner cannot newly start the main rails; a valid 19–21 V input can.

C3 = 22 nF sets approximately 2.27 V/ms (2 uA x gain 25 / 22 nF), about 9 ms for
the protected input ramp. U5 PGOOD adds an 8–13 ms rising deglitch before releasing
EN_P. R6 100k / R7 10k keep EN_P within U2/U3 limits. MODE is tied to GND for
**auto-retry**, preserving that behavior from S3.

Overload causes active current limiting, then shutdown after the internal timer
(129–202 ms) or thermal shutdown. Auto-retry waits approximately 648 ms typical.
PGOOD is driven low when the FET is off, with **8–13 ms falling deglitch**; it is
not an instantaneous rail-voltage comparator. FLT is monitored at TP6, not wired
back to EN, avoiding immediate load-shedding/re-enabling chatter. C4, the old
external ITIMER capacitor, is removed. IMON at TP7 is approximately 0.558 V/A
with R26 = 20k; no bypass capacitor is fitted on IMON.

C1 + C2 total about 2 uF before the main eFuse, versus the nominal 10 uF attach
capacitance limit. C5 and all converter input bulk remain behind U5. Subsequent
output-rail/module-capacitor charging is still a separate startup-load test.

## Board-side current setting and output targets

R5 = **3.3k** and new R29 = **1k**, in series from ILIM to GND:

```text
R_ILIM = 3300 + 1000 = 4300 ohm
I_LIM_nominal = 18000 / 4300 = 4.186 A
```

Both are 1% Basic/Economic 0603 resistors. The single 4.3k candidate C23159 is
currently Preferred Extended, so it is not silently treated as Basic. R29 must
not be bypassed: 3.3k alone would permit an excessive current threshold.

| Quantity | Screened value |
| --- | --- |
| Main-path threshold, nominal | 4.186 A |
| Main-path threshold, minimum | 3.693 A |
| Main-path threshold, maximum | 4.698 A |
| Normal auxiliary-current reserve | 25 mA |
| Total static input at maximum limiting | 4.723 A |
| Board connector/input-path class | 5 A |
| Required static design guard below 5 A | >=0.25 A |
| IMON worst screened voltage at limiting | 2.84 V, below its 4 V operating ceiling |

Screening uses +/-10% for U5, plus each resistor's 1% tolerance and 100 ppm/K
over 100 K. This deliberately exceeds TI's +/-7% at the nearby 4.02k/4.5 A test
point; interpolation and the final current threshold still need prototype checks.
This is the highest E24-equivalent setting satisfying that stated 0.25 A guard:
4.3k passes; the next lower E24 value, 3.9k, does not. It is **not** a universal
"maximum safe" rating independent of layout and temperature. Setting a nominal
5 A or U5's 6 A maximum would exceed the board's 5 A class at tolerance corners.

An overload threshold is **not** a continuous operating target. The internal
fast-trip level is about twice the limiting threshold and short-circuit response
is finite; instantaneous current can exceed 5 A. Test current overshoot, input
inductance/TVS stress, fuse pulse tolerance and repeated auto-retry thermals.
The 25 mA reserve covers normal auxiliary consumption, not a zener fault.

Per-rail targets remain **+12 V 2.5 A, +5 V 2.5 A, -12 V 1 A**. S5 removes the
input-budget obstacle to attempting all three together; it does **not** increase
the converters' individual ratings or prove simultaneous thermal/stability
performance. The shared eFuse cannot impose an accurate independent limit on
each output. Their own cycle-current/thermal protection remains essential, and
an internally failed converter can still overvoltage its output. D2–D4 are
polarity clamps, not output overvoltage protection.

With actual divider setpoints and the existing **unmeasured** efficiencies:

```text
Pconverters = 12.194*Iplus12/0.91 + 4.985*Iplus5/0.86 + 11.989*Iminus12/0.84
VIN = V_USB_receptacle - VD10 - Iload*(RON + Rother)
I_USB ~= Pconverters/VIN + Iaux
```

At all three current targets the rounded nominal rails total **54.5 W**; the
actual divider values give approximately **54.94 W** and **62.26 W** converter
input. With VD10 = 0.75 V, RON = 53 mOhm, a 50 mOhm additional connector/fuse/PCB
allowance, and Iaux = 25 mA:

| Voltage at USB receptacle | Estimated total input | Estimated input power |
| --- | --- | --- |
| 18.5 V (after cable drop) | 3.61 A | 66.73 W |
| 19 V | 3.50 A | 66.59 W |
| 20 V | 3.32 A | 66.35 W |
| 21 V | 3.15 A | 66.14 W |

These are estimates, not guaranteed worst-case converter efficiency or a cable
loss model. The full-load main-path estimate at 18.5 V is 3.582 A, below the
3.693 A screened minimum threshold but with limited transient margin. If actual
efficiency, cable drop, startup load or thermal performance is worse, derate the
loads; do **not** simply raise ILIM further. Source-terminal voltage and receptacle
voltage are different. Use the actual measured full-load profile for signoff.

## Unchanged converter stages and remaining review issues

| Rail | Converter | Frequency / L | Nominal divider output |
| --- | --- | --- | --- |
| +12 V | TPS62933FDRLR | 1.2 MHz / 6.8 uH | 47k / 3.3k -> 12.194 V |
| +5 V | TPS62933FDRLR | ~2.0 MHz / 3.3 uH | 68k / 13k -> 4.985 V |
| -12 V | LMR38020FDDAR, IC ground = -12 V | ~790 kHz / 15 uH | 100k / 9.1k -> -11.989 V |

The positive buck thermal margins, exact DC-bias capacitor curves, inverter
loop stability and audio/EMI performance remain prototype work. Forced PWM is
retained; it is not a universal fixed-frequency/noise guarantee during startup,
faults or duty-cycle limits. The +12 V divider's high tolerance corner remains
an identified improvement outside this protection-only change.

Q1 is a level-shifted enable, not a precision rail-tracking supervisor. SW1
removes input power but does not guarantee that module capacitors have discharged
or that a brief press fully resets every module. D2–D4 are polarity clamps, not
rail-overvoltage protection. Use two qualified cables where required by the
header/cable current rating; parallel outputs do not actively balance current.

## Sourcing, verification and release boundaries

See [S5 changes/sourcing and qualification](s5-current.md) and the historical
[S4 protection record](s4-protection.md). R5/R29 are independently live-checked
Basic + Economic; D10 and the retained U5 are Extended + Economic.
**Inherited C5/C34/C35/C36 are Extended**, contrary to the old blanket Basic claim.
They are unchanged; their Basic-policy gate is unresolved, not silently waived.

Native ERC, XML/table/pad parity, source-preservation checks and drawing inspection
are schematic evidence only. No PCB, DRC, EMI, thermal qualification, supplier
upload, reservation, order or commit is implied. Raw evidence is in ignored
`research/s5-current/` (S4 history remains in `research/s4-protection/`); dated
sourcing evidence is retained in `docs/s5-sourcing.json`. The existing Basic-policy
blockers, shared 3D-model inspection blocker, F1/D1/J1 supplier-document and
prototype qualification gates are not cleared by a successful schematic check.

Primary references: [TI TPS1663](https://www.ti.com/lit/ds/symlink/tps1663.pdf),
[WCH CH224](https://done.land/assets/files/ch224aq_datasheet.pdf),
[Nexperia BCX53](https://assets.nexperia.com/documents/data-sheet/BCX53_SER.pdf),
[Diodes SMAZ24](https://www.diodes.com/assets/Datasheets/ds18015.pdf),
[ZHIDE SS1060 manufacturer-sheet mirror](https://datasheet4u.com/pdf/942007/SS1060.pdf).
