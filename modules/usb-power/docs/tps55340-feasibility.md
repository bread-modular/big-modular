# TPS55340 positive / TPS65131 negative: feasibility only

**Decision: feasible, and direct protected-9V input is the useful improvement.** This is a future PCB redesign, not a drop-in replacement or a tested output rating. Baseline is main-based `e797bec7137b12b8ba958de5abe4ba7d5d2a3de3`; the paused passive implementation was not accessed. No circuit, layout, generator, BOM, test or fabrication source was changed.

## Architecture and disabled-channel handling

```text
9V PD -> unchanged TPS26600 -> VPROT -> TPS55340 -> +13.5–14V -> TPS7A4700 -> +12V
                                  -> TPS54302 MID ~5V -> TPS65131 negative -> ~-14V
                                                                         -> TPS7A3301 -> -12V
                                  -> separate TPS54302 -> +5V
```

TPS65131 supports **ENN enabled, ENP disabled**. Section 7.3.3 explicitly starts the circuitry needed for each individual converter; section 7.3.5 gives independent soft-start. No running/unloaded positive converter or positive-first startup is required. A shared undervoltage/thermal shutdown still affects both channels (sections 7.3.7–7.3.8). Disabling the positive channel reduces die heat and MID loading, **not** the negative channel's switch-current threshold. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf#page=9)

Conservative assessed unused-positive arrangement: split ENP from ENN and hold ENP at ground; disconnect the old positive output from the positive LDO/new TPS55340 output. Retain the old positive inductor/diode/output capacitor, feedback sensing and compensation on its separate unloaded node. The old diode/inductor path still passively precharges that node to roughly MID minus a diode drop; ENP is not an output-disconnect switch. Keep the node inaccessible to external loads/backdrive. BSW is only an optional positive-path PMOS gate control, not a negative-enable dependency. No active dummy load is required by the cited enable operation. The datasheet does not provide a complete component-stripped, negative-only unused-pin recipe: deleting those retained components or inventing floating/grounded analog-pin connections is **not** approved by this assessment. Residual passive/IC standby is included in the 0.15W auxiliary allowance, not claimed as a guaranteed separate-channel maximum. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf#page=9)

Keep system ground common, retain VREF bypass/negative feedback and AGND/PGND layout, and supply VIN/INN from MID only: recommended 2.7–5.5V. Enable logic must stay within the MID-referenced limits. Never feed U4 9V, lift its ground, or parallel the positive converters. Recommended negative magnitude is at most 15V; the inverting-switch absolute differential limit is 24V. MID plus negative magnitude plus diode/ringing stress must be checked: the illustrative static high-end sum is about 20.84V before ringing, not a 24V operating allowance. Existing MID peak screen is already 5.418V. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf#page=4)

J7's two positive pins share **one** +12V rail; its two negative pins share **one** -12V rail. All currents below are per rail, not per pin.

## Useful output targets

All rows reserve **+5V at 250mA = 1.25W**; an unloaded opposite rail retains its overhead allowance. Nominal and low cases use 14V raw magnitudes. These are estimates for a correctly engineered split-rail redesign, conditional on feedback/headroom, stability and cooling—not ratings for the unchanged PCB. “Target” means a useful sustained-design objective, not a bring-up-only load or maximum specification.

| Operating point | +12V mA / W | -12V mA / W | Total output W including +5V | Input A, nominal / low | Assessment |
|---|---:|---:|---:|---:|---|
| Positive only, target | 600 / 7.20 | 0 / 0 | 8.45 | 1.295 / 1.456 | Useful target; qualify positive-LDO cooling |
| Positive only, higher target | 750 / 9.00 | 0 / 0 | 10.25 | 1.582 / 1.782 | Narrower power/thermal margin; high-raw case fails 1.85A screen |
| Positive only, stretch | 850 / 10.20 | 0 / 0 | 11.45 | 1.776 / 2.002 | Nominal-source/efficient/cool operation only |
| Negative only, upper target | 0 / 0 | 250 / 3.00 | 4.25 | 0.758 / 0.943 | Limited by U4 peak/heat, not input power; 200mA has more margin |
| Negative only, stretch | 0 / 0 | 300 / 3.60 | 4.85 | 0.874 / 1.092 | Nominal conditions only; fails adverse peak-current screen |
| **Recommended simultaneous** | **400 / 4.80** | **200 / 2.40** | **8.45** | **1.390 / 1.641** | Best initial sustained-design objective across these power screens |
| Simultaneous stretch | 600 / 7.20 | 200 / 2.40 | 10.85 | 1.776 / 2.082 | Requires nominal source, good efficiency and cooling; not low-corner capable |
| Alternative simultaneous stretch | 500 / 6.00 | 250 / 3.00 | 10.25 | 1.703 / 2.018 | Same conditional status; less negative peak margin |

These standalone upper currents cannot simply be added. The positive LDO's **1A / nominal 12W** is an IC ceiling, not available simultaneous system output. At 14V raw, +1A alone plus the +5V reserve calculates to 2.072A nominal input, already beyond the protection's nominal setting.

## Reproducible steady-state power budget

Explicit engineering assumptions, not guaranteed efficiencies:

| Parameter | Nominal source case | Low-source/loss case |
|---|---:|---:|
| PD voltage before wiring | 9.00V | 8.55V, assumed -5% |
| Wiring drop; hot eFuse resistance | 0.15V; 0.25ohm | 0.15V; 0.25ohm |
| Direct positive boost efficiency | 90% | 85% |
| MID and +5V buck efficiencies | 90% | 85% |
| Negative inverter efficiency | 80% | 70% |
| Positive / negative raw voltage | 14V / 14V | 14V / 14V |
| Positive / negative raw-current overhead | 2mA / 7mA | 2mA / 7mA |
| Other auxiliary/standby allocation | 0.15W | 0.15W |

The 7mA allowance includes the negative LDO/feedback load; its datasheet's 5mA ground-current entry at 500mA load is typical, not a full-temperature maximum. Opposite-rail overhead remains allocated even when its external load is zero. Disabled-positive residual burden is not added twice.

```text
Pbus = Vraw+ * (I+ + 0.002) / eta_boost
     + abs(Vraw-) * (I- + 0.007) / (eta_mid * eta_inv)
     + V5 * I5 / eta_5 + 0.15
VPROT = Vsource - 0.15 - 0.25 * Iinput
Pbus = Iinput * VPROT             # solve the lower-current quadratic root
```

R8+R79+R80 remains 6.04kohm: nominal limit = 12000/6040 = **1.986755A**. Retain **1.85A as an illustrative conservative allocation**, not a newly established guaranteed minimum at 9V/6.04kohm. The approximate 1.850228A derivation is `1.986755 * 0.95 / (1.01 * 1.01)`; it assumes a 5% IC factor and 1% resistance/two-sided temperature allowance. TI's table specifies nearby 8kohm and 5.36kohm conditions, not this exact setpoint, with a 24V table header. RON is 150mohm typical, 250mohm full-temperature maximum under the table conditions (pp.7–8; current-limit programming section). No fuse/current-limit increase is assumed. [source](https://www.ti.com/lit/ds/symlink/tps2660.pdf#page=7)

At 1.85A, protected-bus power is **15.517W at 9V**, or **14.684W at 8.55V**. This is before conversion losses, LDO losses and auxiliary demand. A genuine 9V contract with sufficient source current is required; a CH224A 9V request alone proves no adapter wattage.

Additional high-raw sensitivity uses +14.7V (an illustrative +5% power-cost allowance, not a selected feedback design), negative magnitude 14.917399V (accepted upper screen plus 0.1V), MID 4.612887V (accepted lower screen minus 0.1V), and P5 5.418152V. At +400/-200mA it requires **13.886W / 1.7435A**, leaving about 106mA below the illustrative allocation. It is a deliberately combined screen, not proof all these extremes are simultaneously attainable or guaranteed bounds. At +600/-200mA it needs 2.210A and fails.

Power-only +12V ceilings with the +5V reserve are approximately **888mA nominal / 781mA low / 736mA high-raw**, before thermal derating. With -12V at 200mA, these become **638 / 495 / 446mA**. They are limits of the stated arithmetic, not recommended operating points.

**Without the +5V load:** freeing its converter input demand adds about **89–92mA of positive-rail power budget** with other loads unchanged; it does not remove the negative switch limit. At -200mA, positive power-only ceilings become 727 / 585 / 538mA. Across the same three cases, positive-alone ceilings become 977 / 870 / 828mA. A 1A positive point can fit only under more favorable assumptions such as 13.5V raw, efficient nominal-9V operation, no +5V load and adequate cooling; it is not a rated result.

Feeding TPS55340 from MID instead forfeits the main advantage: at +600mA, the extra buck would dissipate roughly another 1.04–1.75W under these efficiency assumptions. With -200mA also loaded, MID current would be about 2.60–2.98A instead of approximately 0.72–0.88A. Use direct VPROT input.

## Switching limits and actual redesign scope

**TPS55340:** 2.9–32V operating input; boost/SEPIC/flyback topology options; boost output cannot regulate below its input. The internal switch limit is **5.25A minimum / 6.6A typical / 7.75A maximum**, specified at maximum duty—not 5A of rail output. Frequency is adjustable 100kHz–1.2MHz. EN disables switching; a plain boost still has its inductor/rectifier pass-through path and needs separate shutdown/backfeed treatment. Soft-start limits switching demand, not every passive capacitor-charging path (pp.4–5, sections 7.3.2, 7.3.5, 7.3.7). [source](https://www.ti.com/lit/ds/symlink/tps55340.pdf#page=5)

An illustrative, **not selected**, 10uH/roughly-600kHz stage screens at 8uH minimum and 460kHz, 0.5V diode drop: at the low-source protected bus, boosting to 14V at 1A external output gives about 45% duty, 0.976App ripple and **2.57A peak**, well below the 5.25A switch limit. The switch-only output screen is about 2.29A raw, versus 2.57A at nominal source, ignoring thermal/upstream restrictions. That means ample boost-switch headroom; the actual system is constrained earlier by protection, the 1A LDO and heat. The assumed frequency floor corresponds to TI's 80kohm table example; resistor tolerance and the eventual frequency/inductor selection still need a fresh design check. [source](https://www.ti.com/lit/ds/symlink/tps55340.pdf#page=16)

A future design needs a new TPS55340 footprint, properly rated inductor, Schottky diode, local input/output capacitance, frequency/feedback/compensation/soft-start networks and thermal/EMI placement. Check inductor saturation through fault current—up to the 7.75A maximum switch limit unless otherwise constrained—not just normal 2.6A peaks. Do not assume the existing 4.97A-Isat part is adequate for that fault case. Diode average current must exceed raw output current, peak rating must cover inductor current, reverse rating must cover raw voltage plus spikes; 40V is a sensible starting class, not a released selection. TI sections 8.2.1.2.4–.6 and .10–.11 require ripple/current/compensation checks. Space, layout fit and the fixed mechanical envelope are unverified. [source](https://www.ti.com/lit/ds/symlink/tps55340.pdf#page=18)

**TPS65131 negative:** table limit is **1.8A minimum / 1.95A typical / 2.2A maximum at VIN=3.6V**, not a newly verified minimum at all our MID corners. TI p.13 Eq.4 estimates:

```text
Ipeak- = (VMID + abs(Vraw-)) * (Iexternal- + 0.007) / (VMID * 0.64)
```

The 0.64 belongs to TI's peak estimate; it is not applied as another efficiency in the power budget. Peaks are **1.229/1.369A at -200mA**, **1.526/1.700A at -250mA**, and **1.823/2.031A at -300mA**, nominal/high-raw respectively. Thus -250mA is plausible but margin-sensitive; -300mA is a typical/stretch possibility, not an adverse-corner target. -350mA already needs 2.120A by the nominal formula and is not supported. There is no negative 1.95A output promise, no doubling with ENP low, and no safe extrapolation to symmetric high-current rails. [source](https://www.ti.com/lit/ds/symlink/tps65131.pdf#page=13)

Independent lossy CCM check retains L3=4.7uH, tests 3.76uH minimum/1.25MHz, 0.5V diode drop, switch resistance 0.62ohm and hot inductor DCR 0.0403*1.4ohm. Solve `(Vin-Iavg*(Rsw+RL))*D=(Vneg+Vd+Iavg*RL)*(1-D)` with `Iavg=Iout/(1-D)`; add half the computed on-time current ripple. At -200/-250/-300mA, adverse peaks are **1.357/1.648/1.978A** at duty **79.8/80.7/81.7%**, versus 87.5% typical maximum duty. This cross-check also rejects treating -300mA as a corner-safe rating. The inductor's 4.97A saturation/3.30A RMS catalog values do not raise U4's switch limit; biased inductance and heating remain unqualified. At -250mA this loss model gives approximately **0.90W U4 conduction**, or **1.15W** after a separately unmeasured 0.25W switching allowance. Removing positive-channel dissipation helps materially but does not establish total die temperature.

## LDO and thermal qualification

Both retained LDOs specify 1A operating output. TPS7A4700's dropout table gives **450mV maximum at 1A**; TPS7A3301 gives **800mV maximum at 1A**, with its overall accuracy condition requiring 1V nominal input/output separation. These are specified test conditions, not interchangeable headroom/PSRR guarantees. **Do not scale the negative 800mV bound linearly with load.** Positive and negative specifications are on pp.5–6 of the respective PDFs. [source](https://www.ti.com/lit/ds/symlink/tps7a47.pdf#page=6) [source](https://www.ti.com/lit/ds/symlink/tps7a33.pdf#page=6)

Use `P_LDO=(Vraw-Vfinal)*Iexternal+Vraw*Ioverhead`, conservatively charging the entire overhead allowance to its die, and `Tj=Ta+P_LDO*theta_effective`. At 14V raw / 12V final:

| Rail/load | Dissipation W | Tj at 25C ambient, theta 40–80C/W | Tj at 50C ambient, theta 40–80C/W |
|---|---:|---:|---:|
| +12V 400mA | 0.828 | 58–91C | 83–116C |
| +12V 600mA | 1.228 | 74–123C | 99–148C |
| +12V 750mA | 1.528 | 86–147C | 111–172C |
| -12V 200mA | 0.498 | 45–65C | 70–90C |
| -12V 250mA | 0.598 | 49–73C | 74–98C |
| -12V 300mA | 0.698 | 53–81C | 78–106C |

Values above 125C reject that assumed operating point; they are not valid sustained temperatures to accept. At +400/-200mA, the additional high-raw/low-final sensitivity (+14.7V to +11.7V, -14.9174V to -11.2961V) produces **1.229/0.829W**, reaching **148/116C** at 50C ambient and 80C/W. The recommended point therefore still needs positive effective thermal resistance **below about 61C/W**, preferably materially lower, for this adverse screen. +600mA requires below about 61C/W at nominal raw and 41C/W in the adverse screen. Neither JEDEC thermal numbers nor existing copper prove these values. At 14V raw/50C/80C/W, positive thermal output is only about **455mA** at the 125C boundary, before margin.

At the recommended point the eFuse alone dissipates about 0.48–0.76W across the nominal/high-raw cases. Converter losses, nearby hot parts, enclosure heating and X5R's 85C body-temperature limit require separate checks; not all conversion loss is in the controller die. Raw +13.5V saves roughly 0.20W at +400mA versus 14V, but only if worst-case ripple/headroom/accuracy remain adequate.

## Remaining gates and exact scope

- A positive boost does **not** diagnose or cure the reported negative fluctuation. Current accepted screens still show negative worst headroom about 0.178V, an assumed—not guaranteed—50nA U4 feedback-current corner, and bias-derated local/LDO capacitance/loop concerns. Those remain explicit future repair/qualification items; simply raising NRAW is not a solution. See `electrical-investigation-046.md`.
- Steady-state budget does not qualify PD attach, capacitor precharge, both soft-starts, eFuse retry, asymmetric rails, output shorts, backdrive, shutdown or load transients. The recommended high-raw input margin is small enough that sequencing and transient tests matter.
- Prefer Basic/Economy capacitors and resistors where effective capacitance, current/temperature and feedback accuracy permit. Basic resistor networks do not become precision parts by averaging. A narrowly justified precision-feedback exception may be needed, subject to approval; no sourcing/stock sweep, substitutions or policy exception was made.
- A higher PD voltage/current or different protection could change output budgets, but would require a separate authorized protection/mechanics/thermal redesign. None is assumed here.
- Exact deliverables: this file and `tps55340-feasibility-arithmetic.json`. Fresh TI PDFs/text/provenance are ignored scratch in `research/tps55340-assessment/`, not fabrication or deliverables. Fresh existing-device PDF hashes match the saved 046 provenance; TPS55340 is the new source. Arithmetic JSON records source hashes, all assumptions and calculated cases. Only intent-to-add is permitted for diff visibility; no commit, merge, push, main write, GUI/native tests, export, advisor or delegation.
