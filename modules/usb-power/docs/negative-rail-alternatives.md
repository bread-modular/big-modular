# Negative-rail alternatives — electrical feasibility only

**Observed UTC date: 2026-10-17. Decision: credible direct-9V alternatives exist.** The intermediate MID buck plus TPS65131 is **not the only way** to obtain our negative rail. Both **repurposing the MID TPS54302 as an inverting buck-boost (IBB)** and using a **TPS5430 asynchronous IBB** have explicit TI support. Either removes TPS65131 rather than feeding it 9V. With Sol's live sourcing relay, **TPS5430DDAR/C9864 is the leading Basic-IC/voltage-margin candidate**; TPS54302 remains the more compact reuse/efficiency candidate. Neither is a drop-in or an approved redesign.

**Recommendation after Sol's relay:** prefer an explicitly authorized direct-negative revision before routing, with **TPS5430 first for Basic sourcing and voltage margin**, provided its output-capacitor/ESR/loop requirements can be met. TPS54302 is the alternative if lower losses, compactness or ceramic-loop feasibility outweigh its tighter voltage envelope. Retain `0f5b49d` untouched until that ACK. For the unchanged shared input, **+400/-300mA is a conditional direct-stage objective**, not a new rating; TPS5430 has particularly thin adverse shared-power margin there. **-400 to -500mA is credible for either negative converter itself**, not an unconditional simultaneous-system promise. If avoiding another revision is more important than negative-current growth, keeping the existing 200–250mA objective remains reasonable.

## Scope and preserved contract

- Work is confined to assigned workspace 058, main-derived `1ced533`. Read the root/module instructions and focused main reviews. Candidate `0f5b49d` was **not checked out, copied, inspected in another workspace, or changed**; its setpoints/risks below come from `split-rail-opus-review.md` and the user's instructions.
- Preserve TPS7A3301 negative LDO, TPS7A4700 positive LDO, direct protected-9V TPS55340 positive stage, independent +5V/250mA reserve, 9V/2A source, and TPS26600 protection. Nominal current-limit setting remains `12000/6040 = 1.986755A`; **1.85A is an illustrative allocation, not a verified minimum trip current**.
- Comparison uses nominal PRAW +13.519V and NRAW -14.185V, with final rails approximately +/-12V. Existing negative objective stays 200–250mA (2.4–3W), 300mA conditional; positive objective stays 400mA sustained/600mA stretch until separately authorized and qualified.
- Only this report and `negative-rail-alternatives-arithmetic.json` are new deliverables, under the module's `docs/`. Manufacturer PDFs/text and working arithmetic are ignored `research/negative-rail-alternatives/` scratch. No schematic/PCB/library/generator/BOM/test/routing/export edits or hardware tests, advisor, delegation, commit, merge, push, GUI, order, vendor upload, main write, or other-workspace access.
- **Sourcing is attributed to Sol's user-relayed live observations below.** No catalog was requeried here. Electrical suitability, a catalog stock snapshot and acceptance of an actual assembly order remain separate gates.

## Relayed live JLC sourcing — no catalog requery

**User relay from Sol, UTC date 2026-10-17:** eight bounded strict live requests; every entry below was separately reported **Economic PCBA eligible, type 0**. Sol reports raw responses, timestamps and SHA verified. The raw receipts and individual request timestamps/hash values were **not provided in this relay**, so this report records attribution rather than claiming to have independently inspected them. The JSON records when the relay was incorporated, not a fabricated catalog-request time. Stock is a snapshot, **not an order/reservation or long-term availability guarantee**.

| Exact MPN | C-code / catalog link | Classification | Relayed stock | Economic PCBA |
|---|---|---|---:|---|
| TPS5430DDAR | [C9864](https://jlcpcb.com/partdetail/C9864) | **Basic** | **204,384** | eligible, type 0 |
| TPS54302DDCR | [C311983](https://jlcpcb.com/partdetail/C311983) | Extended | 21,907 | eligible, type 0 |
| TPS54160DGQR | [C13530](https://jlcpcb.com/partdetail/C13530) | Extended | 6,722 | eligible, type 0 |
| LT8330ES6#TRPBF | [C673741](https://jlcpcb.com/partdetail/C673741) | Extended | 779 | eligible, type 0 |
| LT3580EDD#TRPBF | [C462624](https://jlcpcb.com/partdetail/C462624) | Extended | 23 | eligible, type 0 |
| LT8362EDD#TRPBF | [C673762](https://jlcpcb.com/partdetail/C673762) | Extended | 20 | eligible, type 0 |
| TPS65131RGER, baseline | [C87663](https://jlcpcb.com/partdetail/C87663) | Extended | 456 | eligible, type 0 |

This materially strengthens **TPS5430DDAR**: its IBB use is manufacturer-supported and its normal full-span voltage/current screen works at 9V/-14V. Its Basic classification does not make its required capacitors, diode, magnetics or precision feedback automatically Basic/Economy eligible. If its capacitor/ESR loop requirement cannot be closed within policy/space, prefer TPS54302's separately supported implementation rather than forcing an unstable all-ceramic TPS5430 circuit.

## 1. Reusing TPS54302 is manufacturer-supported, not a generic buck assumption

TI **SLVA933**, section 5, **p.23**, explicitly says the TPS54202 inverting application report also applies to **TPS54302 and TPS54202H**. Its demonstrated circuit is 8–16V input, -12V/0.8A, with component-selection and measured-loop discussion. This establishes topology applicability, **not** a measured 9V/-14.185V/500mA result on our board. [source](https://www.ti.com/lit/an/slva933/slva933.pdf#page=23)

The conceptual connection is VPROT to IC VIN, IC GND to NRAW, inductor from SW to **system ground**, output capacitance between system ground and NRAW, and the FB divider between system ground and NRAW. The LDO and system ground remain unchanged; **only the inverter IC's reference floats negative**. Existing MID passive values, enable wiring, footprint connections and routing cannot simply be retained. Keep the independent P5 buck entirely separate. See SLVA933 sections 1–2, pp.3–5. [source](https://www.ti.com/lit/an/slva933/slva933.pdf#page=3)

### Voltage, switch and fault-envelope gates

TPS54302 datasheet **SLVSDG6C**, sections 5.1–5.6, pp.4–5: recommended VIN/SW up to **28V relative to IC GND**, absolute maximum **30V**; EN/FB recommended up to **5.5V**, absolute **7V**; BOOT-SW has its own limits. High-side peak limit is **4/5/6A min/typ/max**; low-side valley limit **3.1/4/5.5A**. These are switch currents, not negative output amperes. [source](https://www.ti.com/lit/ds/symlink/tps54302.pdf#page=4)

```text
VIN_IC = VPROT - NRAW = VPROT + abs(NRAW)
nominal illustrative terminal voltage = 9 + 14.185 = 23.185V
normal high static screen = 9.45 + 14.979 = 24.429V
```

The SW node moves approximately from NRAW to VPROT relative to system ground: its span is the same sum, **not 9V**. Account separately for negative undershoot relative to IC GND, positive ringing, bootstrap differential, diode/body-diode conduction, load release and fault energy. A valid gate is `VPROT_max + |NRAW|_max + positive ringing < 28V`, with separate absolute-maximum survival checks. As an **example allocation only**, a 16V raw transient envelope plus 2V ringing leaves a 10V VPROT operating ceiling; the corresponding 30V absolute boundary is 12V, not an operating target. Neither allocation is a measured bound.

The current review did not establish the inherited TPS26600 OVP/divider/clamp worst case. **Do not use the 9V PD request as that bound:** include source tolerance, OVP threshold tolerance, turn-off delay, hot-plug overshoot and any real clamp voltage/current. A hypothetical 12V VPROT excursion plus 16V raw and 2V ringing reaches 30V and is unacceptable for TPS54302. Existing protection must not be silently retuned to make this candidate work.

TPS54302's approximately 108% FB-based output OVP turns off its high-side switch; it is **not** an independent VIN clamp, an energy sink, or protection against every open-divider fault. Its threshold description is not a guaranteed raw-peak bound. Verify divider-open behavior and possible raw clamp needs against the LDO/capacitor limits without assuming OVP fixes them (section 6.3.13, p.13). [source](https://www.ti.com/lit/ds/symlink/tps54302.pdf#page=13)

### Useful current calculation — same -14.185V raw target

Both worked candidates use an **illustrative 27uH**, not a selected/reused inductor. Nominal screen: ideal devices, 9V at converter terminals, 14.185V raw, TPS54302 400kHz/TPS5430 500kHz. Adverse illustrative screen: 7.9375V protected bus (`8.55 - 0.15 - 0.25*1.85`), 14.979V raw, 21.6uH (-20%); TPS54302 frequency `290kHz * 0.94 = 272.6kHz` (extra spread-spectrum allowance), TPS5430 400kHz. Include **7mA raw-current overhead**.

TPS54302 hot-loss assumptions: high-/low-side resistance 0.17/0.08ohm, inductor DCR 0.08ohm. TPS5430 screen: high-side 0.23ohm, DCR 0.08ohm, diode 0.5V. These deliberately explicit assumptions are **not complete guaranteed worst-case loss models**, and the power-budget efficiencies below are independent system assumptions.

```text
Iraw = Inegative_external + 0.007A
Dideal = |NRAW| / (VPROT + |NRAW|)
ILaverage = Iraw / (1-D)
lossy duty: VPROT*D - (|NRAW|+Vdiode)*(1-D)
            - ILaverage*(DCR + RHS*D + RLS*(1-D)) = 0
DeltaIL = (VPROT - ILaverage*(RHS+DCR))*D / (L*f)
Ipeak = ILaverage + DeltaIL/2
```

| Final -12V load | Useful negative W | TPS54302 peak A, nominal / adverse | TPS5430 peak A, nominal / adverse |
|---|---:|---:|---:|
| 200mA | 2.4 | 0.788 / 1.044 | 0.737 / 0.921 |
| 250mA | 3.0 | 0.917 / 1.193 | 0.866 / 1.074 |
| 300mA | 3.6 | 1.046 / 1.343 | 0.995 / 1.228 |
| 400mA | 4.8 | 1.303 / 1.647 | 1.252 / 1.541 |
| 500mA | 6.0 | 1.561 / 1.957 | 1.510 / 1.861 |

At 500mA TPS54302's ohmic-model adverse duty is 66.8%, average inductor current 1.529A and valley 1.100A: below the **4A high-side minimum** and **3.1A low-side minimum** by substantial screen margins. This supports **300–500mA stage feasibility**, not thermal/current certification. Inductor/diode fault selection must survive the **6A high-side maximum plus relevant propagation/overshoot**, not merely the normal ~2A peak. An eFuse limit on average input current does not cap individual switch pulses at 1.987A.

**Independent efficiency-consistent cross-check:** assign all negative-converter input power to the inductor path, so `ILaverage = Iraw + |NRAW|*Iraw/(VPROT*eta)`, and conservatively omit on-state drops from the ripple calculation. At 500mA and the adverse bus/raw values, assumed 80% TPS54302 efficiency gives **1.703A average / 2.176A peak / 70.2% duty**; assumed 75% TPS5430 efficiency gives **1.783A average / 2.111A peak / 71.6% duty**. These higher screens reconcile the switch check with the power assumptions and still leave substantial room below 4A. Neither simplified model is a guaranteed upper bound.

TPS54302 allows high duty while BOOT-SW remains charged; the normal duty here is far from that limit. At the upper frequency including jitter, nominal on-time is approximately 1.13us, well above the **110ns typical** minimum-on-time entry; off-time at the ohmic-model adverse duty is about 0.61us (about 0.55us in the efficiency cross-check). This is a steady-load screen, not proof of bootstrap recharge or recovery from a discharged/shorted output. TPS5430 specifies 87% minimum maximum-duty capability at 500kHz and 200ns maximum minimum-on pulse; the 67.7% ohmic-model / 71.6% efficiency-screen duties are likewise reasonable. [source](https://www.ti.com/lit/ds/symlink/tps54302.pdf#page=5) [source](https://www.ti.com/lit/ds/symlink/tps5430.pdf#page=5)

### Capacitance, loop, EMI and sequencing are real redesign work

- **Full-voltage bypass:** any VIN-to-IC-GND capacitor sees approximately **23–25V**, not 9V. Retain a separately considered VIN-to-system-GND input bank. Treat 35/50V ceramic classes as starting candidates for the full-span bypass; a 25V part has little static margin and potentially severe bias loss. Existing 25V X5R C12891 evidence at 9V or 14V cannot be extrapolated to 23V. SLVA933 section 3.4, p.16 distinguishes this bypass from the rail-input capacitors; SNVA856B section 5.2, p.10 gives the same full-span warning. [source](https://www.ti.com/lit/an/slva933/slva933.pdf#page=16) [source](https://www.ti.com/lit/pdf/snva856#page=10)
- At 500mA, pulsed input/output capacitor-current screening is about **0.72A RMS** for TPS54302 in the ohmic model, or **0.78A** in the efficiency cross-check, before inductor-ripple corrections and capacitor-network current sharing. With **30uF genuinely effective** local output capacitance, ideal capacitive ripple is ~41–44mVpp in those adverse screens, **excluding ESR, ESL and transients**. This does not prove a 100mV peak dip allocation. Check exact bias, temperature, aging, AC dependence, ESR heating and X5R body temperature; parallel Basic capacitors are preferable when their evidence closes these requirements.
- **Do not reuse the buck loop calculation.** IBB adds a right-half-plane zero. At 500mA, the first-order screen with 32.4uH (+20%) gives RHPZ about **23.9kHz** for TPS54302 in the ohmic model, falling to **18.3kHz** in the efficiency cross-check. A conservative RHPZ/5 screen therefore suggests crossover below roughly **3.7kHz** (TPS5430: about **3.3kHz**), not merely the original buck bandwidth. Internal compensation cannot simply be retuned. TI's TPS54202 example at 27uH/2x22uF measured only **42.21 degrees** phase margin, and other L/C choices were substantially worse (SLVA933 Table 2, p.17). It is not our loop result; model/measure across real capacitor corners and light-load pulse skipping after authorization. [source](https://www.ti.com/lit/an/slva933/slva933.pdf#page=17)
- **EN/FB/PG reference:** EN at system 0V would be about +14V relative to the running inverter's IC ground, beyond its limit. Use a correctly analyzed floating-domain enable/UVLO interface; do not wire the existing system-ground BI_EN directly. FB is near `NRAW + 0.596V`, with divider endpoints system ground/NRAW. **TPS54302 has no PG pin**; do not invent one. A TPS54160-family PG, if used, also needs appropriate level shifting and pull-up stress analysis. SLVA933 section 3.5, p.16; SNVA856B sections 7.1–7.2, pp.11–12. [source](https://www.ti.com/lit/an/slva933/slva933.pdf#page=16) [source](https://www.ti.com/lit/pdf/snva856#page=11)
- **Startup/discharged output:** initially NRAW=0, so the IC starts from the actual ~9V input; its ground then moves negative. The negative LDO can begin conducting before NRAW has reached regulation. The typical 5ms internal soft-start does not establish total inrush or loaded-start behavior; even 30uF charged through 14.185V in 5ms adds ~85mA raw charging demand before load current. Full-span bypass capacitance can initially kick NRAW positive. TI documents this generic IBB mechanism in SNVAA61 section 2.1, p.5; any proposed Schottky clamp must meet actual voltage/current limits, not just carry a diode label. [source](https://www.ti.com/lit/an/snvaa61/snvaa61.pdf#page=5)
- **Shutdown/short/retry:** with VPROT collapsed but NRAW still negative, VIN-to-IC-GND can remain above UVLO. Examine stored energy, the high-side body-diode/backfeed path and EN behavior; synchronous prebiased-start support is not universal reverse-current protection. Analyze NRAW short, N12 short through the LDO, precharged outputs, full-load startup and eFuse retries separately. Both LDOs and their existing discharge shunts retain their reverse/shutdown limitations; changing the inverter does not cure them. TPS7A3301 OUT/FB/NR-to-IN absolute minima of -0.3V remain important during collapse (p.5). [source](https://www.ti.com/lit/ds/symlink/tps7a33.pdf#page=5)
- Compact high-di/dt loops, SW-field containment, input filtering, local decoupling and separation from quiet-rail feedback are necessary; the spread-spectrum feature does not certify EMI or audio-noise performance. No board-area fit, layout, copper change or routing is performed here.

## 2. Basic-IC / voltage-margin lead: TPS5430; TPS54160 is not a free 1.5A output

**TPS5430** has a direct TI application reference, **SLVA257A**, sections 3–4, pp.3–6. It is rated for 5.5–36V input in buck operation, with VIN/PH absolute limits 40V, and 4/5/6A high-side peak current limit. At ~24.4V full-span stress it has considerably more voltage margin than TPS54302. Its external diode avoids an actively driven synchronous low side, but does **not** make shutdown, backdrive or LDO shorts automatically safe. Do not substitute the lower-voltage **TPS5431**: its 23V operating input is already below the nominal 23.185V full-span example. [source](https://www.ti.com/lit/an/slva257a/slva257a.pdf#page=3) [source](https://www.ti.com/lit/ds/symlink/tps5430.pdf#page=4)

The worked current screen above supports 300–500mA. Costs versus TPS54302 are a larger exposed-pad SOIC package, external rectifier, higher assumed losses, and a more awkward internal voltage-mode compensation/passive match. TI's demonstrated -5V circuit uses **220uF POSCAP/40mohm ESR**, not an all-ceramic drop-in network. A Basic ceramic bank with a deliberate series-R/damping branch is a **design possibility**, not evidence of stability or Basic/Economy eligibility. Sol's Basic-IC result makes TPS5430 the leading sourcing/voltage candidate, **not an automatic all-Basic-passive or board-area winner**. Its rectifier must withstand the full input-plus-negative span, ripple, fault current and heat; no exact diode is selected. **PH relative to IC GND is limited to -0.6V steady state, or -1.2V for transients shorter than 10ns:** the assumed 0.5V diode drop is not a verified worst-case clamp at fault current. Check diode Vf and ringing accordingly. The exposed **PowerPAD must connect to NRAW, not system ground**, with electrically isolated thermal copper as required by the floated topology. [source](https://www.ti.com/lit/an/slva257a/slva257a.pdf#page=4)

**TPS54160/TPS54160A:** 3.5–60V input, 65V VIN/PH absolute ratings, external compensation and soft-start make this family credible for a floated-ground IBB with more controllable dynamics. TI SLVA317B explains the peak-current-mode design method using TPS54060A and explicitly points to higher-current TPS54360 for more power; it is not a measured TPS54160 circuit at our load. TPS54160's **1.5A buck rating is inductor current**, and the listed 1.8A minimum current limit is conditioned at **12V/25C**. At -500mA our loss screen already needs about 1.5A average plus ripple: do not select it on the headline 1.5A or 2.7A typical switch limit. 200–300mA is credible, 400mA deserves detailed checking, and a 500mA objective favors a higher-current member with a fresh datasheet/part review. Not worked further in this bounded comparison. [source](https://www.ti.com/lit/ds/symlink/tps54160.pdf#page=7) [source](https://www.ti.com/lit/an/slva317b/slva317b.pdf#page=1)

## 3. Dedicated inverting/Cuk shortlist — alternatives, not a stock sweep

These converters keep IC ground at system ground and use a negative-feedback architecture, simplifying enable referencing relative to floated-buck IBBs. Their inverting implementations generally use **two inductors or a coupled winding pair, a transfer capacitor and a diode**, plus device-dependent compensation/soft-start parts. The Cuk transfer capacitor and switch/diode stress still involve approximately `VIN + |VOUT|`; a wide input-voltage headline does not remove that check. A conventional SEPIC output is positive: select the manufacturer's **inverting/Cuk configuration**, not its positive SEPIC schematic.

| Candidate | Fresh manufacturer evidence | Electrical disposition at 9V -> about -14V raw -> -12V |
|---|---|---|
| **LT8362** | 2.8–60V input, 2A/60V switch; ADI DC2517A/SCP inverting Cuk demonstrations | Best dedicated alternative to retain on the shortlist. 200–400mA is credible; 500mA needs exact minimum limit, summed winding-ripple and low-input checks. Do not translate a demo's “up to 1A, depending on input” into 1A at 9V. |
| **LT3580** | 2.5–32V input, 2A/42V switch; DC1144A-B demonstrates 5–12V to -12V/350mA | Credible same-load alternative and possible 300–400mA design. Changing raw output to -14.185V raises current/stress; 500mA remains a calculation/qualification task, not that demo's rating. |
| **LT8330** | 3–40V input, 1A/60V switch, 2MHz, inverting support | 200–250mA useful; 300mA is margin-sensitive. Not a sensible 400–500mA upgrade at this conversion ratio. |
| **LM2611A** | 2.7–14V operating supply; A-grade switch limit 1.0A minimum/1.2A typical at the electrical-table conditions | Plausible 200–250mA Cuk alternative; 300mA thin, 400–500mA not supported by the minimum switch-current budget. Avoid the weaker B grade (0.7A minimum/0.9A typical). |

LT8362/LT8330 facts above were available from **manufacturer search-index excerpts**, including the LT8330 datasheet cover; direct ADI PDF downloads and full-page extraction failed. LT3580's **full manufacturer product page** was readable, but its electrical-table PDF was not. Therefore no missing current-limit minima/maxima, compensation values or temperature guarantees have been invented. This access limitation is why the two fully worked options are TI IBBs. [source](https://www.analog.com/en/products/lt8362.html) [source](https://www.analog.com/en/products/LT8330.html) [source](https://www.analog.com/en/products/lt3580.html)

LM2611 datasheet sections 6.1–6.5, pp.3–4, verify its 36V switch absolute rating and actual 2.7–14V supply range; the product-page prose had a malformed “4V” upper limit, so that prose is **not** used. Its NFB bias is several microamps, not the nA-scale assumption of the existing divider; include the specified bias in setpoint design. Its tabulated switch-limit temperature conditions are -40 to +85C, not a blanket -40 to +125C guarantee. [source](https://www.ti.com/lit/ds/symlink/lm2611.pdf#page=4)

For a Cuk implementation the switch carries the **sum** of input- and output-inductor currents during on-time. An efficiency-based average-current screen is:

```text
Iswitch_on_average approximately Iraw + (|NRAW|*Iraw)/(VIN*eta)
```

At 9V, 14.185V raw and assumed 85% efficiency, -300/-400/-500mA external require approximately **0.876/1.162/1.447A before summed ripple**. At 7.9375V, 14.979V and 80%, they require **1.031/1.367/1.703A before ripple**. Thus a 1A-switch part is not a 500mA negative supply; even a nominal 2A switch needs real ripple and minimum-limit checks at 500mA. Coupling, frequency and inductance affect this significantly. Cuk's relatively continuous terminal currents can improve filtering, but additional magnetic/transfer-capacitor footprint and control-loop work can erase the IC-count advantage. No board-size result is claimed.

### Low-input converters and charge pumps do not solve this requirement

**TPS63700** supports 2.7–5.5V input and down to -15V output; it still needs an intermediate buck. Its **860mA minimum / 1A typical inverter switch limit** gives an ideal 5V-to-14.185V ceiling of only **217mA external**, including 7mA overhead, **before ripple/losses**. The advertised “up to 360mA” depends on conversion ratio. It is not a 250–500mA improvement or a direct-9V replacement. [source](https://www.ti.com/lit/ds/symlink/tps63700.pdf#page=5)

**LT1054**, a verified representative charge-pump option, is a 3.5–15V, **100mA** switched-capacitor converter. A simple inversion of +9V cannot create -14V headroom, and its current class is already below the target. Cascaded/doubling pump arrangements incur additional loss, capacitor RMS demand and regulation complexity; no adequate 200–500mA pump solution was evidenced in this shortlist. This is **not** a proof that every conceivable charge-pump/controller solution is impossible. [source](https://www.ti.com/lit/ds/symlink/lt1054.pdf#page=1)

## 4. LDO headroom and Basic passives — do not replace one tiny margin with another

Keep **TPS7A3301**. Its overall-accuracy condition requires at least 1V nominal input/output separation; the 800mV maximum dropout entry is at 1A and must not be linearly scaled down to claim a new guaranteed minimum at 300–500mA. Ripple, load-step recovery and frequency-dependent PSRR still matter at lower currents. Lowering no-load voltage with a resistor/diode is not regulated headroom under load. [source](https://www.ti.com/lit/ds/symlink/tps7a33.pdf#page=6)

The Opus review's **0.985mV negative accuracy reserve, 21mV NRAW range reserve and 13nF positive-capacitance reserve are not robust production guarantees**. Changing the negative stage removes the TPS65131-specific -15V ceiling and its feedback architecture, but does not automatically improve LDO output-divider accuracy or any positive-stage/capacitor margin.

Additional setpoint screens below retain the existing reviewed negative-output upper corner **12.386251V**, allocate 0.1V raw dip, and use TPS54302's 0.581/0.596/0.611V reference or TPS5430's 1.196/1.221/1.245V reference. Basic resistor factors are 0.9801/1.0201 (1% tolerance and 100ppm/K over 100K); precision sensitivity factors 0.9965025/1.0035025 (0.1%, 25ppm/K). **FB bias, line regulation, exact selected networks and correlated temperature behavior are not closed**; these are feasibility sensitivities only.

| Raw design sensitivity | DC magnitude range V | Reserve above 1V separation after 0.1V dip |
|---|---:|---:|
| TPS54302, nominal 14.185V, all-Basic ratio | 13.309–15.111 | **-0.178V: fails this screen** |
| TPS54302, nominal 14.185V, precision ratio sensitivity | 13.736–14.640 | +0.249V |
| TPS5430, nominal 14.185V, all-Basic ratio | 13.397–15.003 | **-0.090V: fails this screen** |
| TPS5430, nominal 14.185V, precision ratio sensitivity | 13.806–14.557 | +0.320V |
| TPS54302, hypothetical 14.5V, all-Basic ratio | 13.604–15.447 | +0.117V |
| TPS5430, hypothetical 14.5V, all-Basic ratio | 13.693–15.338 | +0.207V |

The hypothetical 14.5V rows illustrate an all-Basic avenue, **not a selected new setpoint**. They can peak above 15V, increase LDO loss and full-span stress, and are **outside the 14.979V upper-raw budget used below**. They need explicit approval and complete new power/stress closure. A limited additional power sensitivity is included in the JSON: with the hypothetical all-Basic 14.5V raw divider, +400/-300mA becomes **1.813A for TPS54302 / 1.860A for TPS5430** at low source/high raw. Thus the TPS5430 version **fails 1.85A** in that screen; +400/-250mA is **1.723A**. This is a real Basic-passive/headroom/power tradeoff, not permission to raise the eFuse limit. At unchanged 14.185V, narrowly justified precision divider parts are another option, not a silently granted sourcing exception. Basic series/parallel R/C networks are preferred where they actually meet the requirement; series resistors do not statistically average away worst-case tolerance or TCR.

Do not conflate **Extended ICs** with **Basic passive requirements**: a viable Extended converter might be acceptable while its compensation/bypass/feedback R/C must still satisfy separately evidenced Basic **and** Economy eligibility. No exact new passive eligibility is asserted; IC classifications/Economy observations are only those in Sol's relay. Larger-voltage bypass capacitors, the TPS5430 ESR requirement, and a Cuk transfer capacitor deserve particular attention in Sol's evidence.

## 5. Unchanged shared input budget — illustrative, not new protection settings

All rows reserve **+5V at 250mA**, and include 7mA overhead on **each** raw rail plus 0.15W auxiliary burden. The positive overhead is deliberately 7mA rather than the older feasibility document's 2mA, consistent with the later handoff's warning. No converter datasheet guarantees the efficiencies assumed here.

| Assumption | Nominal-source case | Low-source/high-raw sensitivity |
|---|---:|---:|
| Source before wiring | 9.00V | 8.55V |
| Wiring drop / eFuse resistance | 0.15V / 0.25ohm | same |
| PRAW / magnitude NRAW | 13.519 / 14.185V | 13.992 / 14.979V |
| P5 at 250mA | 5.000V | 5.418152V inherited upper screen |
| Positive boost / independent P5 buck efficiency | 90% / 90% | 85% / 85% |
| Existing MID buck times TPS65131 efficiency | 90% x 80% = 72% | 85% x 70% = 59.5% |
| Direct TPS54302 IBB efficiency | **90% assumed** | **80% assumed** |
| Direct TPS5430 IBB efficiency | **85% assumed** | **75% assumed** |

```text
Pbus = PRAW*(Ipositive+0.007)/eta_positive
     + abs(NRAW)*(Inegative+0.007)/eta_negative_path
     + V5*0.250/eta_5 + 0.15
VPROT = Vsource - 0.15 - 0.25*Iinput
Pbus = Iinput*VPROT        # solve lower-current quadratic root
```

This deliberately combined adverse sensitivity is not a guarantee that all selected parts have these simultaneous bounds. Its 14.979V raw assumption is retained from the reviewed baseline for comparability; a future selected alternative must replace it with its own justified upper bound. At the 1.85A allocation the bus has **15.517W nominal / 14.684W low-source** before conversion, LDO and auxiliary losses. The nominal 1.987A eFuse setting and the adapter's 2A do **not** authorize replacing the 1.85A allocation with a larger planning number.

| +12/-12 external mA | Useful total W including nominal +5V reserve | Existing cascade input A nominal / adverse | TPS54302 direct A nominal / adverse | TPS5430 direct A nominal / adverse |
|---|---:|---:|---:|---:|
| **400 / 200** | 8.45 | 1.379 / 1.713 | **1.280 / 1.537** | 1.303 / 1.571 |
| **400 / 300** | 9.65 | 1.623 / **2.050** | **1.473 / 1.784** | 1.508 / 1.835 |
| **400 / 400** | 10.85 | **1.870 / 2.396** | 1.668 / **2.036** | 1.715 / **2.105** |
| **600 / 200** | 10.85 | 1.752 / **2.156** | 1.650 / **1.975** | 1.674 / **2.009** |
| **400 / 500** | 12.05 | **2.120 / 2.750** | **1.866 / 2.291** | **1.926 / 2.379** |
| 0 / 500 | 7.25 | 1.367 / 1.842* | 1.124 / 1.411 | 1.181 / 1.493 |

**Bold failing currents exceed 1.85A**; bold load labels/direct recommended entries are emphasis, not an additional gate. *Cascade 500mA rows are **power-only counterfactuals**: TPS65131's existing negative-stage current screen does not support them, even where source power fits. Likewise its 300mA row is conditional and 400mA is not justified. No table row overrides converter, headroom or thermal limits.

At +400mA, direct-TPS54302 **power-only** negative ceilings are about **492mA nominal / 326mA adverse**; TPS5430's are **464 / 305mA**. These are arithmetic boundaries before transient/thermal margin, not recommended current labels. The 300mA direct objective therefore has useful extra capability but only ~66mA source-current reserve in the TPS54302 adverse case, and ~15mA for TPS5430. **+400/-400 and +600/-200 remain nominal-source stretches; +400/-500 fails even this nominal allocation.** Reducing the other rail can permit standalone -500mA without increasing input protection, subject to cooling.

### Heat remains an independent limiter

Using `Pnegative_LDO = (|NRAW|-12)*Inegative + |NRAW|*0.007`, nominal losses at 200/300/400/500mA are **0.536/0.755/0.973/1.192W**; at 14.979V raw they become **0.701/0.999/1.296/1.594W**. At -500mA with raw 14.979V and final magnitude 11.612V, the loss is **1.788W**. To stay below a 125C junction boundary at 50C ambient requires effective theta below **42C/W**, **before margin**. No existing copper/enclosure proves that result.

At -500mA, the negative converter's assumed loss itself is ~0.80W nominal/~1.90W adverse for TPS54302, or ~1.27/~2.53W for TPS5430, distributed among IC, diode and magnetics. Add eFuse, positive boost/LDO and neighboring heat. Retained TPS7A4700 thermal limits can still constrain +400/+600mA independently; the negative improvement does not establish a higher positive rating. No bench, noise, PSRR, startup or thermal qualification is claimed.

## Actionable comparison and ACK boundary

| Choice | Recommendation |
|---|---|
| Keep MID + TPS65131 | Lowest source-change risk; retain if the existing 200–250mA negative objective is sufficient. Its disclosed tiny margins remain unqualified. |
| Repurpose TPS54302 as direct IBB | **Efficient/compact alternative:** existing IC reuse, explicit TI support, more shared-budget margin and 400–500mA negative-stage potential. Sol reports Extended/Economy eligible. Must close the 28V operating envelope, input/clamp faults, Basic-capacitor/feedback needs and internal-loop stability. |
| TPS5430 direct IBB | **Lead after Sol relay: Basic C9864, independently Economy eligible, ample normal current/voltage margin.** Prefer this for an authorized revision if the Basic passive/ESR/loop solution fits. Diode loss, SOIC area and thin +400/-300mA adverse budget are real costs; an all-Basic 14.5V raw variant needs derating or better justified efficiency, not a protection increase. |
| LT8362 / LT3580 Cuk | Credible dedicated alternatives; Sol reports Extended/Economy-eligible entries but only 20/23 units respectively in the snapshot. Ground-referenced control is attractive, but magnetics/transfer capacitance and unclosed minimum-current evidence prevent promoting them over the worked TI options now. |

**Do not approve routing on a “no other way” conclusion. Credible alternatives exist.** Sol's sourcing relay is incorporated; await the user's topology decision before any schematic revision; any later PCB/routing authorization is a separate explicit ACK. This research does not apply a redesign or certify production margins.
