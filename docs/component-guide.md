# Component guide — how the power circuit works, and why

**Scope:** explains the existing 88-component circuit after its presentation-only split into three subsheets. Values are design selections, not measurements or production-qualified parts. Nothing here establishes a rail-current rating or permission to fabricate. See [sheet navigation](schematic-guide.md), [schematic PDF](schematic.pdf), [design review](design-review.md), and [remaining test requirements](test-matrix.md).

## The overall idea

```text
USB-C power
  -> negotiate a requested 9 V supply
  -> hardware permission / voltage-window gate
  -> efficient switching conversion to intermediate rails
  -> low-noise linear post-regulation
  -> +12 V, -12 V and +5 V on an off-board 16-pin harness
```

Switching converters perform the large voltage changes; the final LDOs are intended to reduce ripple and establish the output voltages. This trades extra parts and some heat for potentially cleaner rails. Actual output noise depends on operating mode, frequency, layout, capacitor behavior and LDO headroom, and has not been measured. TI describes the TPS7A49/TPS7A30 pair specifically for post-DC/DC filtering, but its published noise/PSRR figures must not be treated as measured performance of this module. [source](https://www.ti.com/lit/ds/symlink/tps7a49.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a30.pdf)

## 01 — Input and protection

### J1, F1 and U1: receiving and requesting power

**J1 — USB4105-GF-A** is the physical USB-C input. In this schematic its VBUS contacts join `VBUS_RAW`, CC1/CC2 go to U1, and ground/shield join GND. USB data and SBU contacts are intentionally unconnected. J1 remains the only electrical component actually placed on the carrier PCB.

**F1 — 500 mA / 32 V fuse requirement** sits between the connector and the rest of the input circuitry. Its intended role is a sacrificial series fault barrier, distinct from the resettable electronic limiting in U2. The exact part, interrupt capability, time-current curve and transient coordination are **not selected or qualified**. Its marked current is not USB current authorization.

**U1 — CH224K** negotiates with the USB source over CC1/CC2. R2 configures a request for 9 V. The DP/DM pins are shorted locally at U1 and disconnected from J1 data, following the PD-only arrangement; unused configuration and VBUS-sense pins remain NC. This is a hardware-configured receiver, not a microcontroller running application firmware. WCH describes PG as a generic active-low, open-drain power-good indication; that wording is not sufficient proof of a fixed 9 V PDO with an authorized current. [source](https://components101.com/sites/default/files/component_datasheet/WCH_CH224K_ENG.pdf)

| References | Existing selection | What they do and why |
| --- | --- | --- |
| R1 | 1 kΩ, 1%, at least 0.5 W | Feeds U1's shunt-regulated `PD_VDD` from `VBUS_FUSED` and limits supply current. The power requirement anticipates higher upstream voltages; it is not surge qualification. |
| C1 | 1 µF, 50 V X7R | Local U1 supply bypass; provides nearby charge while the negotiation circuitry operates. |
| R2 | 6.8 kΩ, 1% | CFG1-to-ground request-setting resistor: selects the 9 V request. It does not guarantee that the source offers or grants it. |
| R3 | 100 kΩ | Pulls the open-drain `PD_PG_N` node toward `PD_VDD` when U1 is not sinking it. |

The supply and request arrangements above follow the WCH reference circuit. R1's worst steady-state screening calculation at 21 V, 2.4 V on VDD and a 1%-low resistor is `(21 - 2.4)^2 / 990 = 0.3495 W`; a real part still needs enclosure-temperature and pulse derating. [source](https://components101.com/sites/default/files/component_datasheet/WCH_CH224K_ENG.pdf)

### Q1 and JP1: translating permission into an enable

**Q1 — MMBT3906 PNP transistor** is connected with emitter to `PD_VDD`, base to `PG_BASE`, and collector to `PG_PERMIT`. When U1 pulls PG low, base current through R28 is intended to turn Q1 on, sourcing a high level toward U2. This changes an active-low indication into a positive enable drive; it does **not** analyze PD messages.

**JP1 — RUN, default open** is in series between Q1's collector and U2 SHDN. It provides deliberate manual permission. It is not a bypass around either U1's PG path or U2's voltage window.

| References | Existing selection | What they do and why |
| --- | --- | --- |
| R28 | 22 kΩ, 1% | Limits Q1 base current demanded from U1 PG. |
| R29 | 100 kΩ, 1% | Pulls the PNP base back toward its emitter, encouraging the off state when PG is not actively low. |
| R30 | 10 kΩ, 1% | Pulls SHDN toward **RTN** when RUN is open or Q1 is off; avoids relying on a floating enable. |

U2 requires SHDN low for shutdown. Its specified pullup current used in the existing static screen is 10 µA, so R30 gives approximately `10 µA * 10 kΩ = 0.1 V`, below the specified 0.55 V minimum falling threshold. This explains the resistor's purpose, but does not qualify Q1 leakage, saturation, PG timing, reverse faults or startup behavior. [source](https://www.ti.com/lit/ds/symlink/tps2660.pdf)

### U2: the protected power gate

**U2 — TPS26600PWPR eFuse** places controlled, back-to-back internal MOSFETs between `VBUS_FUSED` and `VPROT`. It provides the hardware path for voltage-window gating, current limiting, controlled output slew and reverse-current protection. Its control pins use **RTN**, whereas GND connects to the system return; externally shorting RTN to GND defeats its reverse-input-polarity arrangement. [source](https://www.ti.com/lit/ds/symlink/tps2660.pdf)

| References | Existing selection | What they do and why |
| --- | --- | --- |
| R4, R5 | 562 kΩ / 100 kΩ, 1% | Divide VBUS into UVLO, referenced to RTN. Their nominal rising threshold excludes ordinary 5 V VBUS from rail generation. |
| R6, R7 | 806 kΩ / 100 kΩ, 1% | Divide VBUS into OVP, referenced to RTN. Their nominal threshold excludes sustained higher-voltage inputs such as 15 V or 20 V from VPROT. |
| R8 | 40.2 kΩ, 1% | Programs approximately 0.2985 A nominal current limit. This is neither a guaranteed limit at all corners nor a rating for any output rail. |
| C3 | 100 nF, 50 V | dVdT-to-RTN capacitor; slows the output ramp to control charging of downstream capacitance. |
| C2 | 100 nF, 50 V | Input bypass from fused VBUS to GND; not an ESD or surge clamp. |
| C4 | 10 µF, 25 V X7R | Protected-side reservoir/bypass, after the gate rather than directly on raw USB power. |
| R31 | 10 kΩ, 1% | Bleeds `VPROT` so off-state leakage has a discharge path. Does not guarantee zero volts or rapid shutdown. |

Using TI's typical 1.19 V rising sense thresholds and current-limit equation gives these **nominal** selections. [source](https://www.ti.com/lit/ds/symlink/tps2660.pdf)

```text
UV rising = 1.19 * (1 + 562k / 100k) = 7.8778 V
OV rising = 1.19 * (1 + 806k / 100k) = 10.7814 V
Current limit = 12 / 40.2 = 0.2985 A  (resistance in kΩ)
```

The resistor/threshold corner checks remain in `reports/pd-gate-check.json`. **D1 is deliberately absent:** no replacement TVS was selected by this task, and VBUS/CC ESD and hot-plug surge protection remain blockers. A voltage in the window, PG asserted and RUN closed still do not prove the requested PD contract/current authorization.

## 02 — Power conversion

### U3 and L1: making a suitable input for the bipolar converter

**U3 — TPS62160DSGR** is a synchronous buck converter. It switches the protected input into L1; L1 and C6 smooth the switching energy into the `V4` supply. R9/R10 set the feedback ratio, while VOS separately senses the output. The purpose of this intermediate stage is to keep U4's supply inside its 2.7–5.5 V operating range instead of applying the requested 9 V directly. [source](https://www.ti.com/lit/ds/symlink/tps62160.pdf) [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf)

| References | Existing selection | What they do and why |
| --- | --- | --- |
| L1 | 2.2 µH, Isat requirement ≥2 A | Buck energy-storage inductor. The actual DCR, saturation curve, ripple and transient margins still need a selected part. |
| C5, C7 | 10 µF / 100 nF, 25 V | Bulk and high-frequency input bypass for U3. |
| C6 | 22 µF, 10 V X7R | Buck output reservoir/filter; effective capacitance matters, not just its label. |
| R9, R10 | 40.2 kΩ / 10 kΩ, 0.1% | Sets `V4 = 0.8 * (1 + 40.2/10) = 4.016 V` nominal. |
| R11 | 100 kΩ | Pulls `MID_GOOD` toward V4 because U3 PG is open drain; both U4 enable pins use this signal. |

The 2.2 µH/22 µF combination is a datasheet starting point, not a bench result. U3 has a typical 2.25 MHz PWM operating frequency, but automatically enters power-save operation at light load. **PG is high-impedance during shutdown, UVLO and thermal shutdown**, rather than an unconditional active-low shutdown indicator. Therefore the visible PG-to-enable wiring expresses normal-startup intent only; decay, stored charge and fault behavior need testing. [source](https://www.ti.com/lit/ds/symlink/tps62160.pdf)

### U4, L2/L3 and D2/D3: generating positive and negative preregulation

**U4 — TPS65131RGER** contains independent boost and inverting control stages sharing a reference/clock. In the boost path, L2 stores energy while the internal switch conducts; when it releases, D2 rectifies energy into C8 and `PRE_P`. In the inverting path, U4, L3 and D3 transfer energy into a negative output stored by C9. Keeping both stages in one device is the existing compact split-rail architecture, not proof that the rails track during startup or faults. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf)

| References | Existing selection | What they do and why |
| --- | --- | --- |
| L2 | 4.7 µH, Isat requirement ≥3 A | Boost energy-storage element, between V4 and `BOOST_SW`. |
| D2 | Schottky requirement 1 A / 40 V | Boost rectifier: anode `BOOST_SW`, cathode `PRE_P`. |
| L3 | 4.7 µH, Isat requirement ≥3 A | Inverting-stage energy storage, between `INV_SW` and ground. |
| D3 | Schottky requirement 1 A / 40 V | Inverting rectifier: cathode `INV_SW`, anode `PRE_N`; not interchangeable in orientation with D2. |
| C8, C9 | 22 µF, 25 V X7R | Positive and negative output reservoirs. They are non-polar ceramic selections. |
| R12, R13 | 1.05 MΩ / 100 kΩ, 0.1% | Positive feedback divider from PRE_P through FBP to GND. |
| R14, R15 | 1.15 MΩ / 100 kΩ, 0.1% | Negative feedback divider from PRE_N through FBN to **BI_REF**, not ground. |
| C10, C11 | 6.8 pF, C0G, 50 V | Feedforward capacitors across the upper feedback resistors; affect dynamic response and noise coupling. |
| C12 | 220 nF, 10 V | Bypasses U4's reference output; provides the quiet reference used by R15. |
| C13 | 10 nF, 50 V | CP capacitor for the positive converter's internal feedforward/error-correction system. |
| C14 | 4.7 nF, C0G, 50 V | CN capacitor for the negative converter's corresponding control network. |
| R16, C15 | 100 Ω / 100 nF | Filters V4 into `ANA_V4`, the U4 control-supply pin, to reduce switching disturbance. |
| C16, C17 | 4.7 µF, 10 V X7R each | Local supply bypass for the two switching input loops. |

U4 regulates FBP near +1.213 V and FBN near 0 V, with VREF near +1.213 V. This is why the negative divider returns to VREF and uses a different equation. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf)

```text
PRE_P = 1.213 * (1 + 1.05M / 100k) = +13.9495 V nominal
PRE_N = -1.213 * (1.15M / 100k)    = -13.9495 V nominal
```

These voltages leave intended headroom above/below the final ±12 V rails. U4's PSP/PSN pins are grounded to disable its optional power-save mode. Its oscillator is specified at 1.25 MHz minimum and 1.38 MHz typical, not 1.25 MHz typical. **BSW is unused:** the positive inductor/diode path permits prebias once gated V4 exists; it is not a complete positive-output disconnect. Diodes, inductor saturation, effective capacitance, compensation, EMI and thermals still require actual-part and bench qualification. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf)

### U5 and L4: reducing dissipation in the +5 V LDO

**U5 — TPS62125DSGR** bucks `PRE_P` down to `PRE_5`, about 6.5 V. The rationale is to avoid dropping the whole approximately 14 V preregulator voltage across U8 while keeping some +5 V LDO headroom. Consequently, the +5 V branch draws from the **same positive boost power budget** as +12 V; it is not a free independent supply.

TPS62125 supports the required output range, whereas the TPS62160 recommended output range stops at 6 V. U5's custom project symbol deliberately identifies pin 4 as **EN_hys**, not AGND; leaving this unused pin open is permitted. VOS must sense PRE_5. [source](https://www.ti.com/lit/ds/symlink/tps62125.pdf) [source](https://www.ti.com/lit/ds/symlink/tps62160.pdf)

| References | Existing selection | What they do and why |
| --- | --- | --- |
| L4 | 10 µH, Isat requirement ≥1 A | Buck energy-storage element; part-specific magnetic and thermal behavior remains to be checked. |
| C18, C20 | 10 µF / 100 nF, 25 V | Local input supply filtering from PRE_P. |
| C19 | 22 µF, 16 V X7R | Output energy reservoir, used with L4 as the selected output filter. |
| R17, R18 | 71.5 kΩ / 10 kΩ, 0.1% | Set the output ratio; feedback now visibly joins both resistors and U5 FB. |

The datasheet recommends 0.800 V for divider selection, while specifying a typical internal reference of 0.808 V. The old “6.52 V” description is therefore a **selection target**, not an exact typical prediction. No resistor value was changed to correct that wording. The 10 µH/22 µF pair is within its recommended filter combinations; light-load PFM and an up-to-1 MHz switching frequency do not satisfy a strict always-MHz requirement. [source](https://www.ti.com/lit/ds/symlink/tps62125.pdf)

```text
Selection target: 0.800 * (1 + 71.5k/10k) = 6.5200 V
Typical-reference estimate: 0.808 * (1 + 71.5k/10k) = 6.5852 V
```

## 03 — Output rails

### U6, U7 and U8: final linear regulation

An LDO continuously adjusts a series pass element to keep its feedback pin near its internal feedback voltage. Unlike a switching converter it does not intentionally chop power through an inductor; the excess input-to-output voltage is dissipated mainly as heat. The selected positive/negative devices are intended for low-noise post-regulation, but their IC current capabilities are **not this module's rail ratings**. [source](https://www.ti.com/lit/ds/symlink/tps7a49.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a30.pdf)

| Main part | Input → output | Why it is present |
| --- | --- | --- |
| U6 — TPS7A4901DGNR | PRE_P → P12 | Establishes the positive approximately 12 V output and attenuates some preregulator ripple. |
| U7 — TPS7A3001DGNR | PRE_N → N12 | Negative counterpart for approximately -12 V. IN and EN connect to PRE_N; GND and EP stay at system zero. |
| U8 — TPS7A4901DGNR | PRE_5 → P5 | Establishes approximately +5 V after U5 has reduced the voltage drop and therefore the intended LDO heating. |

All three EN pins are tied to their own inputs, so there is **no added all-rail tracking/fault latch**. NC3 and DNC7 remain unconnected; DNC must not be grounded. U7's negative enable connection is intentional and supported by its dual-polarity enable input. [source](https://www.ti.com/lit/ds/symlink/tps7a49.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a30.pdf)

### The repeating LDO support networks

| Function | +12 V row | -12 V row | +5 V row | How it works and why |
| --- | --- | --- | --- | --- |
| Input bypass | C21, 10 µF | C25, 10 µF | C29, 10 µF | Local supply reservoir at each LDO input. All are 25 V X7R selections. |
| Output capacitor | C22, 10 µF | C26, 10 µF | C30, 10 µF | Part of stable regulation and transient response. All are 25 V X7R selections. |
| Upper feedback resistor | R19, 91.2 kΩ | R21, 92 kΩ | R23, 32.2 kΩ | Connects output to FB; sets the output ratio with the lower resistor. All 0.1%. |
| Lower feedback resistor | R20, 10 kΩ | R22, 10 kΩ | R24, 10 kΩ | FB to GND, providing the divider return/current. All 0.1%. |
| Noise reduction / soft start | C23, 10 nF | C27, 10 nF | C31, 10 nF | NR/SS to ground: filters the reference and changes startup rise time. All 50 V. |
| Feedforward capacitor | C24, 10 nF | C28, 10 nF | C32, 10 nF | Output to FB, in parallel with the upper resistor; shapes AC response/PSRR. All 50 V. |
| Reverse-differential diode | D4 | D6 | D8 | Provides an external input/output bypass path when the usual input/output ordering reverses. |
| Wrong-polarity clamp diode | D5 | D7 | D9 | Opposes an output being pulled past ground in the wrong direction. |
| Bleeder | R25, 100 kΩ | R26, 100 kΩ | R27, 47 kΩ | Small load/discharge path from output to GND; not a fast-discharge guarantee. |

The LDO datasheets call for at least 2.2 µF input and output capacitance and recommend 10 µF for AC performance. Actual selected MLCCs must retain the required effective capacitance at bias and temperature. The 10 nF NR/SS/feedforward selections follow the application guidance but still need overshoot and startup evaluation in this circuit. [source](https://www.ti.com/lit/ds/symlink/tps7a49.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a30.pdf)

Use the feedback voltage, not the slightly different NR/SS reference headline, for these nominal divider estimates. [source](https://www.ti.com/lit/ds/symlink/tps7a49.pdf) [source](https://www.ti.com/lit/ds/symlink/tps7a30.pdf)

```text
P12 = +1.185 * (1 + 91.2k/10k) = +11.9922 V
N12 = -1.176 * (1 + 92.0k/10k) = -11.9952 V
P5  = +1.185 * (1 + 32.2k/10k) =  +5.0007 V
```

These calculations omit reference/resistor tolerances, bias current, load and line effects. They are not promised output accuracy.

### D4–D9: follow the polarity, not the row shape

All six diodes remain **unselected 1 A / 40 V Schottky requirements**. Their exact current, leakage, forward drop and pulse behavior must be qualified.

| Diode | Anode → cathode in this schematic | Intended action |
| --- | --- | --- |
| D4 | P12 → PRE_P | Bypasses the positive LDO when output rises above input by a diode drop. |
| D6 | PRE_N → N12 | Negative-row counterpart when the input becomes less negative than the output. |
| D8 | P5 → PRE_5 | Same role as D4 for +5 V. |
| D5 | GND → P12 | Opposes a negative excursion of the +12 V output. |
| D7 | N12 → GND | Opposes a positive excursion of the -12 V output. |
| D9 | GND → P5 | Opposes a negative excursion of the +5 V output. |

This explanation follows the actual retained anode/cathode nets. A generic Schottky requirement does not guarantee that every transient will remain inside an LDO absolute maximum. These parts **do not clamp a positive rail precisely to +12/+5 V or a negative rail precisely to -12 V**. They are not a substitute for output precision OVP or an all-rail fault shutdown.

### J2: taking the rails off the board

**J2 — 16-pin IDC POWER OUT** represents the off-board harness, not a fitted PCB header. Pins 1/2 carry N12, 3–8 ground, 9/10 P12, and 11/12 P5. Pins 13–16 are intentionally NC. Keeping the +5 V supply on the 16-pin interface avoids inventing a +5 V position on a 10-pin power connection. The exact cable connector, strain relief and key orientation remain unselected; verify the physical mating-face pinout rather than trusting the red stripe alone.

## What to verify when reading the drawings

- Follow U2's configuration returns to **RTN** and its separate system pin to **GND**.
- Follow U4's negative lower feedback resistor to **BI_REF**, not to ground.
- Check U5 pin 4 is **EN_hys, NC**, and pin 6 is connected to the L4 output.
- Compare the negative LDO's input and diode polarities with the positive rows; do not copy them blindly.
- Follow each capacitor to both of its intended nodes. Feedforward capacitors return to FB, not ground; NR/SS capacitors return to ground.
- Treat PWR_FLAGs as ERC declarations, never as supplies or PCB pads.

## Design limits retained by this task

No explicit PDO/current validation, qualified USB ESD/surge network, precision output OVP, all-rail latch/tracking, guaranteed discharge, finished PCB layout, thermal/EMI qualification or connector-fit approval has been added. The proposed approximately 40 mA-per-rail simultaneous initial test load is not a continuous or peak rating and is not permission to connect loads before the existing blockers are resolved. This documentation and clean installed-environment ERC demonstrate readability/connectivity review, not electrical safety or operation.
