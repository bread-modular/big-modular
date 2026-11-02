# usb-power-45w S9.1 / P2.1: review corrections, unrouted

> **Development schematic and fit placement, not a manufacturing release or bench qualification.**
> ±12 V only; **15 V / 3 A USB PD**, CH224A R1 **56k**, TPS552892-Q1 positive converter,
> LMR38020 negative converter and S8.5 `STARTED` one-shot retained. Prototype targets:
> **+12 V 2.4 A / −12 V 0.8 A, ≤33 W combined**, subject to the source/load qualification below.
> **164 references / 78 functional nets**, overview plus five pages; all components on F;
> **0 tracks, 0 vias, 0 zones**. No PCB routing was performed.

## S9.1 changes and S9.0 review disposition

S9.0/P2.0 is preserved in git `41992e8` / `d7d7219`, including `review-s90.json` and the
previous version of this document. Independent review conversations: Astra
`c092ee9e-4fd7-448d-9b10-b87ff022ad27`, DeepSeek
`2c480974-701a-4e6d-8f7d-f6f1416815d2`. Their common Critical is a **hardware defect**,
not an acceptable bench event or a procedure failure. This revision supersedes the old residuals.

| Item | S9.1 implementation | Verification / limits |
| --- | --- | --- |
| 1: self-enabling U4 / backfeed | Q1 emitter moved from +12 V to own VPD upstream of D10; Q14/Q15 series sink requires RUN and MAIN_LED_OK, R112 pulls Q1 off; D24 VIN TVS, D25 low-current negative clamp, D26 local +12 V transient backstop | Native pin checks, truth table and negative-control tests; finite-energy qualification below; no unrestricted hotplug or parallel-supply claim |
| 2: input minimum | R2/R3 precision 100k/10k plus R114 510 Ω | Loaded start guaranteed below 13.0 V under stated resistor/threshold screen; actual falling range disclosed |
| 3: current-limit thermal | R109 18 mΩ WSLP1206R0180FEA, 1 W, manufacturer-specific Kelvin footprint | ≤125 °C test replaces the old <130 °C assertion; sourcing C-code still open |
| 4: ground split | AGND_U2 distinct from GND/PGND; sole R113 0 Ω bridge at C82.2 | Native and board checks plus `placement.json.ground_connection` |
| 5: compensation | R111 6.8k / C83 100nF; exact complex loop calculation rather than above-zero shortcut | 13,824 sampled corners; bounded passive-load/cable/rack-capacitance envelope; real Bode gate remains |
| 6: startup qualification | 3 A limited source and full V3V3/POR collapse/re-arming cases; persistent faults and repeated autonomous resets retained across qualification epochs | Logic timelines plus current/energy screen and explicit bench matrix, not a guaranteed PD-source dynamic model |
| 7: preserved architecture | +5 V absent, 15 V PDO, TPS552892-Q1, S8.5 one-shot, no crowbar/eFuse; 20 V upgrade documented | No routing, no fabrication export/upload |

Also corrected: P5 header silk → NC, precision/current-shunt sourcing exceptions, mechanical revision,
spare-comparator descriptions and the old results placeholder. No rail fuse/crowbar was added.

## Artifacts

- [Native project](../hardware/single/usb-power-45w-single.kicad_pro), [schematic PDF](usb-power-45w-single-schematic.pdf), [BOM](s8-single/bom.csv).
- [Calculations](s8-single/calcs.json), [validation](s8-single/validation.json), [review-s91](s8-single/review-s91.json).
- [Placement](s8-single/placement.json), [board checks](s8-single/board-p1.json), [mechanics](s8-single/mechanical.json).
- [Assembly PDF](s8-single/assembly/usb-power-45w-single-placement.pdf), [STEP](s8-single/assembly/usb-power-45w-single-assembly.step.zip), [collision screen](s8-single/assembly/assembly-report.json).
- [S9.1 sourcing evidence/unknowns](s8-single/s91-sourcing.json), [whole-design partial snapshot](s8-single/sourcing.json); historical selected-part snapshots remain dated evidence, not current stock claims.

## 1. Own-input enable logic and clamps

```text
MAIN_LED_OK = MAIN_OK AND V20_OK
QUALIFY     = RUN AND MAIN_LED_OK
Q1 emitter  = VPD (own input upstream of D10, never VIN or +12 V)
Q1 base     = R112 to VPD; R16 through Q15 and Q14 to GND

EN_relative = EN_N - V(-12V)
QUALIFY=1: EN_relative = (VPD - VCEsat - V(-12V)) * R18/(R17+R18)
QUALIFY=0: EN_relative <= Ileak * R18
```

R17/R18 remain 100k/20k. A live output bus cannot supply Q1's emitter or qualify either
NMOS gate. `RUN=0`, invalid `MAIN_OK`, or absent own input each prevents enable.
R112=5.1k is the default-off base pull-up; R16=33k supplies base current only through both sinks.

The tolerance screen gives **1.928 V** minimum at start vs U4's 1.4 V
maximum enable threshold, **5.014 V** at the running upper corner.
The **5 µA off-leakage qualification bound** gives **0.102 V**, below the 0.95 V
disable threshold; this is a test/design bound, not an invented TI leakage maximum. All 16
own-input/RUN/status/live-bus combinations are checked. Negative controls restore the old +12 V
emitter or bypass either qualification condition and must fail native verification.

**D24 SMBJ16A on VIN:** 16 V stand-off, 17.8–19.7 V breakdown, rated **26 V at 23.1 A**, **600 W
10/1000 µs** pulse rating. Engineering qualification budget is **1 A × 26 V × 20 ms = 0.52 J**,
26 W for that finite interval, initial temperature ≤50 °C, ≥200 s between pulses. The datasheet
pulse-duration curve screen is approximately 100 W at 20 ms after temperature derating; 600 W
is **not** a continuous or 20 ms rating. Protects U2 VIN/SW1 (42 V absolute / 36 V operating),
U5 OUT and VIN capacitors; C25/C26 then see at most 26+12.6=38.6 V in the rated-clamp screen.
The actual PCB acceptance bound is VIN≤28 V including ringing, not a claim that TVS nominal
breakdown is its clamp voltage. [source](https://www.littelfuse.com/assetdocs/tvs-diodes-smbj-series-datasheet?assetguid=ba555e99-a12d-4f72-a0b6-86b06c67171e)

**D25 BAT54SLT1G:** forward clamp for the *slew-limited, 25 °C* negative VIN test only
(≤0.24 V at 100 µA; ≤26.5 µA displacement current at 1 V/s). It does **not** guarantee
U2's −0.3 V minimum under fast/cold hotplug. **D26 SMBJ14A** at P12_VOUT is a finite-energy
local backstop (14 V stand-off, 15.6–17.2 V breakdown, 23.2 V rated clamp at 25.9 A,
600 W 10/1000 µs) for the 25 V U2 output/sense pins and local MLCCs. It is not protection
for ordinary 16 V downstream capacitors or a coordinated fuse/crowbar.

## 2. Input range, cable drop and UVLO

The published range remains **13.5–16.5 V at VPD on the module**, not at the adapter.
13.5 V = minimum 14.25 V source minus **0.75 V cable/connector drop at 3 A** (≤0.25 Ω loop).
Required source: fixed **15 V / 3 A PDO**, at least 45 W. U5's 3.69–4.70 A protection limit
still does not enforce the PD 3 A contract. 5 V-only or lower-power adapters are not qualified.

| Divider screen | Minimum | Nominal | Maximum |
| --- | --- | --- | --- |
| U5 rising | 12.263 V | 12.618 V | 12.976 V |
| U5 falling | 11.365 V | 11.798 V | 12.193 V |

R2/R3 are 0.1% / 25 ppm/°C; R114 is 1% / 100 ppm/°C; the calculation includes 100 °C
TCR span and 150 nA UVLO leakage. Loaded start margin **0.524 V**,
unloaded start margin **1.274 V**, running margin **1.307 V**.
The recommended **falling≥11.8 V is NOT guaranteed**: even ideal divider resistors cannot
simultaneously satisfy rising≤13.0 V and falling≥11.8 V with U5's full comparator limits
(divider factor≤13/1.224=10.621 versus ≥11.8/1.09=10.826). We retain the honestly disclosed
11.365 V minimum falling threshold rather than mislabel it 11.8 V. Neither voltage margin
nor the logic model alone guarantees startup against a current-limited source.

## 3. Current limit and thermal

R109=18 mΩ, 1%, 75 ppm/°C. `Ilimit = VSNS/R109`, stacking VSNS=48–52 mV, resistor
initial tolerance and 100 °C TCR span: **2.621–2.940 A**
(nominal 2.778 A). The retained 2.4 A prototype rating has **0.221 A**
minimum current-limit headroom; it no longer claims the previous 75% rule for +12 V.
The separate 33 W combined ceiling is unchanged (both per-rail maxima together would be 38.6 W).

| Load | IC loss screen | Tj at 50 °C ambient, 43.4 °C/W | R109 loss |
| --- | --- | --- | --- |
| 2.40A | 1.017 W | 94.1 °C | 0.106 W |
| 2.94A | 1.341 W | 108.2 °C | 0.158 W |

This closes the old 125.8 °C / <130 °C false pass: the regression limit is **125 °C**.
These are loss-model estimates with assumed switching times, not measured thermal guarantees.
966 kHz and L1 6.8 µH remain; R109's slow output-current loop is **not** a switch-current
limit and does not qualify transient stress. D10 may dissipate 2.25 W at 3 A and needs
its own routed-board thermal measurement. R109's supplier C-code is unknown: BOM keeps
the manufacturer identity and explicitly leaves procurement/PCBA approval open.

## 4. AGND/PGND routing contract

U2 pads **5 (DITH) and 17 (AGND)**, R9.2, R110.2, C83.2 and C82.2 are **AGND_U2**.
U2.9 and power capacitors are **GND (PGND)**. The **only bridge is R113, populated 0 Ω,
at the ground terminal of VCC capacitor C82**. `placement.json.ground_connection` specifies
this point and a ≤3 mm straight-line link; `check_s8_board.py` enforces the net identities
and proximity. Future routing must keep the quiet island separate and place 3–4 GND vias
at the C82 power return, with no second plane/via bridge. No routing has been performed.
This follows the manufacturer's single-point ground guidance. [source](https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf)

## 5. Compensation and restricted rack envelope

R111=**6.8k**, C83=**100nF**. `s91_analysis.loop` evaluates complex gain instead of using
an above-zero crossover shortcut outside its domain:

```text
Ypre = s*Cpre
Ypost = s*Cpost + (2/Rload in boost; 1/Rload in buck)
         + 1/(Rcable + s*Lcable + 1/(s*Crack))
Zfb = 1/(Ypre*(1 + R109*Ypost) + Ypost)
Plant = (1-D)/0.055 * Zfb * (1-s/wRHP in boost)
wRHP = Rload*(1-D)^2/L1
Comp = GEA * (1.2/Vout) * (R111 + 1/(s*C83))
Loop = Plant*Comp / (1+s/(2*pi*fSW/10)) * exp(-s/fSW)
```

The output bank is split 75% before / 25% after R109; cable/rack capacitance is a separate
branch. Zero capacitor ESR gives no optimistic ESR phase lead. R/C tolerance, ±30% GEA
sensitivity, a one-period delay and an inner-loop pole are explicit assumptions, **not
manufacturer-guaranteed small-signal bounds**. TI boost/buck expressions are the basis.
[source](https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf)

- **13,824 sampled corners**, minimum phase margin **59.73°**, minimum gain margin
  **12.37 dB**, crossover **387–13566 Hz**, COMP zero **234 Hz**;
  **0 screen violations**. The old 9.1k/10nF network fails the same regression envelope.
- Published positive-rail external capacitance is restricted to **0–440 µF**, onboard effective
  C **37.6–96.8 µF**, cable loop R **0.08–0.25 Ω**, L **0–0.5 µH**, passive resistive
  small-signal loads **0.05–2.4 A**. VIN corners include **10.37 V sag, 12.5, 16.5 and 21 V**.
- This sampled model does not prove all intervening corners or arbitrary active-rack negative
  impedance/no-load FPWM stability. Those configurations are **not advertised as qualified**.
  Release requires measured **PM>45°, GM>10 dB**, no sustained oscillation, and actual rack-impedance
  characterization. The old ~0.9 mF startup charge allowance is not a positive-rail stability allowance.

## 6. One-shot arming and startup qualification

```text
START_N  = NAND(MAIN_LED_OK, RUN, V3V3, V3V3)
STARTED  = U12A (PRE_N=START_N, CLR_N=RESET_N, CLK=GND, D=V3V3)
TIMER_GO = RUN AND STARTED
ARMED    = U11 delayed RESET output
ANY_BAD  = NAND(MAIN_LED_OK, P12_OK, N12_OK, V3V3)
FAULT    = U12B: CLK=ARMED AND BAD_FILTERED; PRE_N=OV_N; CLR_N=RESET_N
RUN      = RESET_N AND NOT_FAULT
```

The one-shot remains **0.31–0.88 s from the first qualified enable per powered epoch**, not
a restartable mask. Faults after ARMED latch until RESET; OV_N presets FAULT even before ARMED.
**STARTED and FAULT are volatile:** complete V3V3/POR collapse clears them. No nonvolatile
lockout was added and automatic power-cycling is not allowed to erase a failed qualification.

At worst simultaneous unconstrained charging demand the source screen is **4.25 A**;
positive charging alone can demand **3.055 A**. Thus moving R109 does not by itself
solve 3 A source startup. At 33 W, the energy-only lower-bound charge time is **116.5 ms**,
not a guaranteed completion time. The tests exercise a source-limited energy plant and full-reset
logic epochs; they do not reproduce every PD adapter's internal control loop.

| Case | Qualification condition | Pass criteria |
| --- | --- | --- |
| S1 | Cold start, 14.25 V source +0.25 ohm cable, exact 3.00 A constant-current limit; 0/0.44 mF external each rail; 0/15/25/33 W load; both delay corners; log all attempts | Single attempt: both rail monitors good within 250 ms of first enable; ARMED by 0.90 s; no V3V3/POR reset, no source restart, <=3.00 A steady input; no retry hidden from record |
| S2 | Same loads with a PD source hard-resetting on >3 A; include 5 V phase and V3V3 fully collapsed to 0 V | A single hard reset is counted and disqualifies that source/load combination for guaranteed start; no success by discarding earlier failed attempts |
| S3 | Persistent rail short, uninterrupted source, then manual RESET and separate full power removal/reapplication | Each power epoch with input held must fault within 0.90 s+2 ms of first enable, hold RUN low until explicit reset, and fault again with short present |
| S4 | Ten automatic input hard resets every 200 ms while short remains, V3V3 collapsed in each off interval | Qualification result must be FAIL_REPEATED_POWER_RESET, never a pass from a final successful cycle; fixture latches power OFF on the second autonomous reset |

All proposals above are **not bench-performed**. The fixture must count autonomous resets across
power epochs and stop on the second; a final good-looking cycle must not replace failed evidence.
The persistent-short timeline latches in both epochs after deliberate power removal/reapplication;
regressions reject a masked fault and ten autonomous resets followed by a nominal cycle.

## Accepted architectural residuals — not acceptance of the self-enable defect

There is still **no series reverse blocker or rail disconnect**. The self-enable defect is fixed;
continued claims of unrestricted live-bus survival would be false. Enabled forced PWM can still
sink external power if a powered unit is paralleled with a higher bus. The −0.9 A LMR38020 figure
is typical, not a worst-case bound. No finite-energy TVS can absorb an unlimited live bus.

Disabled +12 V injection still charges **2.98–7.68 mJ** into
its capacitors and feeds approximately **0.389 mA** divider/leakage load.
A fast −12.6 V step would produce an unclamped VIN displacement of **[-1.23, -5.43] V**;
D24/internal diode forward conduction can still allow approximately −1.4 V. D25 is not a
high-current/cold absolute-minimum guarantee. **Unrestricted hard hotplug remains unqualified.**
T1 intentionally qualifies a specified slow-ramp condition, rather than an acceptance test
that is expected to fail. Power down the bus before normal connection; never parallel running supplies.

### T1: bounded bus-injection/clamp qualification

- T1-A: no USB input, +/-12.0 and +/-12.6V external bus, 1A source limit, 0.44mF each rail; ramp <=1V/s at 25C, hold 10s; log EN_N relative to -12V, U4 SW, VIN and bus currents
- T1-B: same with USB present and FAULT latched/RUN low; verify off-state once MAIN_OK deglitch expires and capture the preceding <=20ms interval
- T1-C: only negative rail applied with same bounded slew; repeat rail order
- T1-D: inject a positive 1A, <=20ms pulse into VIN (compliance 28V, automatic disconnect), 25/50C, >=200s between pulses. This separately tests D24 energy/clamp; never assume the now-disabled U4 will generate this pulse

**Pass criteria:**

- T1-A/C: EN_N minus -12V <=0.11V settled (<=0.5V transient), zero U4 switching; VIN -0.3..1V after 100ms settled; each bus current <10mA after 100ms
- T1-B: same EN/switching/current criteria after 20ms; VIN may retain own-input charge, must remain -0.3..28V, not climb from bus power
- T1-D: VIN <=28V incl ringing, measured integral(V*I*dt)<=0.52J, clamp current ends by 20ms, no leakage increase >10uA after cooling; normal restart and regulation after RESET
- All: automatic overvoltage disconnect at VIN 28V, negative excursion abort at -0.3V (fast comparator, not human reaction). An abort is a FAIL, not a pass.

**Excluded:** Hard hotplug, temperatures below25C for D25 forward-drop guarantee, >1A or >20ms sustained injection, and powered parallel supplies require new protection/qualification.

### T2: rail overvoltage, source removal and stored energy

U20 trips at **+14.48–15.27 V / −13.27–14.02 V** and opens U5 through the FAULT latch.
It cannot disconnect an external source attached to a rail or instantly discharge a capacitor.
There is **no fuse/crowbar or rail eFuse**; that architecture decision remains **deferred/open**.
D26 is a transient backstop, not continuous shunt protection.

VIN bank energy screen is **5.919 mJ**. Without D26/loads, the energy-only
rail estimates are **+23.42 V / −23.59 V**;
with a typical 440 µF rack **+15.98 V / −14.8 V**.
These are **not guaranteed transient peaks**; U2's 24.5 V OVP is not modelled as an ideal clamp.
A failed-short power stage can still expose the bus to the input, and sub-threshold guard faults
can persist indefinitely. Ordinary 16 V downstream capacitors are not thereby qualified.

- T2-A: input16.5V; 0.44mF +0.5A/rail; externally ramp +12V from12 to16.5V at<=1V/ms, <=1A, total injection<=10ms (including ramp), hold<=1ms at16.5V; fixture removes injection automatically after trigger; scope>=100MS/s
- T2-B: R8 open at13.5/16.5V input, 3A source; no external C/no load, then0.44mF+0.5A; capture500ms with independent voltage/current abort
- T2-C: R14 open, same conditions; no assumed LMR38020 output OVP
- T2-D: RUN held low/logic powered, +14.0V and -13.0V external for10min; safely BELOW the minimum guard thresholds; no-trip only refers to OV_N, not RUN
- T2-E: at+15.2V / -13.9V a trip is ALLOWED (inside tolerance bands); repeat guaranteed trip at+15.8V / -14.5V with <=1V/ms slew, <=1A source and >=50us hold (record actual waveform)

**Pass criteria (this module):**

- With >=0.5V rail overdrive beyond each measured trip, OV_N low/FAULT set/RUN low <=20us; MAIN LED off. Keep FAULT latched10s after injection removed, reset explicitly only after fault repair
- Externally driven rail remains externally driven until fixture removal: NEVER require it off while injection remains. After removal connect1k/1W discharge load; both rails below1V within2s at <=0.44mF external C
- T2-B/C: observed positive rail peak<=24.0V and negative magnitude<=24.0V for the500ms capture; positive duration above16V<=100ms with specified1k discharge; D26 pulse energy<=0.10J; normal regulation after repair/RESET
- T2-D OV_N stays high. T2-E band points may trip or not; above-band points MUST trip. Automatic abort at+24V / -24V / VIN28V, source removed in<=2us; any abort fails qualification, no human-only protection

**Downstream qualification:** Without a separate rail protector, downstream modules must tolerate16.5V/10s and sub-threshold +15.3V/-14.1V continuously, and up to24V magnitude/100ms or their measured actual exposure if worse. Ordinary16V caps are NOT thereby qualified; incompatible modules excluded until crowbar/eFuse decision.

No claim is made that a rail turns off while an external source still drives it. The 15.2 V/
−13.9 V points lie inside the tolerance bands and **may trip**; below-band points are used for
no-trip tests, above-band points for required-trip tests. Waveforms, peaks, discharge intervals,
energy integrals and automatic aborts are numerical acceptance criteria, not human observation.

## 20 V support remains possible

The buck-boost topology, 50 V VIN capacitors and LMR38020 permit future retargeting. It is **no
longer just three resistors**: R1 56k→120k, R3 10k→7.5k precision, R114 510→0 Ω, R83
100k→120k; **D24 SMBJ16A→SMBJ22A**, and **D25 replaced by a ≥40 V negative clamp** with
forward-drop/footprint qualification. Recheck stand-off, clamp peaks, power, loop and source
qualification; update label/rating/docs. `calcs.json.retarget_20v` records this delta.
No 20 V source is authorized with the present 16 V TVS populated.

## Placement, sourcing and reproducibility

P2.1 adds D24–D26, Q14/Q15 and R112–R114. Only retained C33/C82 are moved; R109 gets the
manufacturer-specific Kelvin footprint. L1 and fixed interfaces remain in place. R113/C82 are
reserved as the sole analog/power ground junction. Placement checks find no courtyard overlaps,
unapproved edge-rule failures, hand-solder violations or nominal 3D interferences. Header pins
11–16 remain NC; +5 V is absent. The panel remains labelled PD 15V.

Sourcing is **not an order approval**: precision R2/R3 and guard resistors, and the 18 mΩ shunt,
are explicit exceptions to the Basic-passive target. R109 has no verified C-code. New-code
classification, Economic eligibility and price remain unknown after failed live catalog access;
`sourcing.json` is explicitly a **partial dated subtotal**, not a complete quotation.

Use existing generators (no hand-editing generated schematics/PCB):

```sh
python3 -B modules/usb-power-45w/tools/build_s8.py --output-root <candidate-module-root>
# Synchronize from the current unrouted board with place_s8.sync_candidate; inspect/promote candidate.
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project-single.json --reports <new-check-directory>
python3 -B modules/usb-power-45w/tools/verify_s8.py --netlist <new-check-directory>/netlist.xml > modules/usb-power-45w/docs/s8-single/validation.json
python3 -B modules/usb-power-45w/tools/s8_calcs.py --out modules/usb-power-45w/docs/s8-single
python3 -B modules/usb-power-45w/tools/check_s8_board.py --out modules/usb-power-45w/docs/s8-single/board-p1.json
python3 -B modules/usb-power-45w/tools/build_s8_panel.py
python3 -B modules/usb-power-45w/tools/mechanics_s8.py
python3 -B modules/usb-power-45w/tools/s8_mechanical.py
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
# Stage new files before producing the tracked-files-only review record.
python3 -B modules/usb-power-45w/tools/review_s8.py --check <new-check-directory> --tests-log <tests-log> --out modules/usb-power-45w/docs/s8-single/review-s91.json
```

BOM/PDF use native `kicad-cli sch export`; board image uses `render_s8.py`. Raw reports/logs
remain in ignored `research/s91/`; no `*.kicad_prl` or research log enters the review hashes.
Clean-clone testing needs the repository's KiCad/pcbnew, ngspice, numpy and plotting dependencies;
mechanical regeneration additionally needs FreeCAD/OpenSCAD. No test needs an ignored local report.

## S9.1 verification and remaining gates

Native **ERC 0**, **DRC 0 geometric violations / 380 unrouted connections / 0 parity findings**;
exact ref/pin/net parity; **164 components / 78 functional nets**, 41 explicit NC pins.
The full test counts and clean-clone evidence are in `review-s91.json`. Logic timing checks have
**0 timeline violations**. Geometry/logic checks do not make the board route- or manufacture-ready.

Remaining gates: routing/routed loops; bench loop and thermal measurements; real 3 A source/load
qualification; replug/POR nuisance race; hard-hotplug/cold clamp and sustained reverse-power
protection; downstream OV qualification; R109 procurement and PCBA eligibility; connector/current
and case fit; CAM/assembly approval; crowbar-vs-eFuse decision. No fabrication export or order.

---

# History: S8.5 / P1.5 and earlier (superseded by S9.1)

> Kept as the record of the S8.5 design (+5 V series disconnect, 20 V input, TPS62933F +12 V buck). Where
> anything below conflicts with S9.1 above, **S9.1 wins**. The S8.5 review record is `review-s85.json`
> in git `5a3a686`.

## S8.5 changelog (2026-11-02, from the three S8.4 reviews)

| Item | Issue | Change | Files |
| --- | --- | --- | --- |
| **B** arming | S8.4 `TIMER_GO = RUN AND MAIN_OK` (R83 200k, `V20_OK` 14.62–17.73 V): the qualification window restarted every time a fault cycled `MAIN_OK` (U5 overload auto-retry, a sagging source, a short RESET with PGOOD still high), so the board could run unarmed indefinitely; `MAIN_OK` floating high during the PD 5 V phase armed the board before 20 V arrived and then latched it off; `V20_OK` meant neither "input good" nor "status valid" | **One-shot latch:** U12 flip-flop A = **`STARTED`** (PRE_N = **`START_N` = NAND(`MAIN_LED_OK`, RUN)** on the spare U14 gate 2, CLR_N = RESET_N, CLK = GND); **`TIMER_GO = RUN AND STARTED`** (U13 pin 10); the **U11 output is `ARMED`** (R71 pull-up, U13 pin 4); **TP19 = `STARTED`**. **R83 200k → 120k**: `V20_OK` = **9.06–10.96 V**, a U5 status-validity floor; the input qualification is U5's own UVLO. Details, divider screen and timelines below | `tools/circuit_s8.py`, `hierarchy_s8.py`, `build_s8.py`, `place_s8.py`, `verify_s8.py` (timeline simulation), `s8_calcs.py` (`arming`), `test_s8.py`, pages 05/06, PCB (TP19) |
| **C1** hashes | `review-s84.json` hashed the git-ignored `*.kicad_prl` files; `test_s8.py` failed on any clean checkout | `review-s85.json` hashes only files a clean clone has (no `*.kicad_prl`, nothing under `research/`); the check directory and the tests log are local evidence, recorded by path only. `test_s8.py` asserts that no hashed path is git-ignored | `tools/review_s8.py`, `test_s8.py`, `review-s85.json` |
| **C2** status semantics | `MAIN_LED_OK` / `ANY_BAD` were described as "input valid", which the 200k `V20_OK` did not deliver | `MAIN_LED_OK = MAIN_OK AND V20_OK` now means **"U5 on with valid FLT/PGOOD"** (`V20_OK` only validates U5's status, it is high wherever U5 can be on); `ANY_BAD = NOT(MAIN_LED_OK AND P12_OK AND P5_OK AND N12_OK)` = "U5 not on with valid status, or a rail below its monitor threshold". Notes, page texts and the fault matrix say so; `test_s8.py` rejects the S8.4/S8.3 dividers | `circuit_s8.py` (R83, D8, U13, U14 notes), `hierarchy_s8.py`, `s8_calcs.py`, `test_s8.py` |
| **C3** replug / POR | Astra MAJOR-1: replug into a rack that holds −12 V can race the TPS3808 POR (`R100/C67/R98/R99`) | `calcs.json` → `replug_por`: REF_OV charges through R100 into C67 **while R98 draws current into the D22-clamped `MON_OVN` node**: 9.5 ms nominal, **13.75 ms worst corner vs the ≥ 12 ms POR release: margin −1.75 ms, NOT established — explicit OPEN item** (nuisance latch-off, RESET to recover). The S8.4 "~1 ms margin" (`v3v3_loss`) ignored the R98 load and is withdrawn | `s8_calcs.py`, `circuit_s8.py` (C67 note), `test_s8.py`, this page |
| **C4** consistency | Doc / README / record counts | Every count, refdes, net and price below re-derived from the regenerated artifacts: 191 refs / 85 nets, BOM 63 lines, 171 + 20 test pads, 430 routing opens | this page, `README.md`, root `AGENTS.md` |

**Not changed in S8.5** (owner decision 2026-11-02): U23 and its R108/TP21, OVLO, ILM and dVdt parts,
R11/R12 0.1 %, U18/U20 on VPD, the local-loop placement contract, the 2.0 A +5 V rating, the 0.15 mm
U23 mask webs, the −12 V start-up allowance, the Basic-only decision and the mechanical records.
**The crowbar-versus-eFuse question for +5 V stays open**; S8.5 neither restores the S8.2 crowbar nor
removes U23. Revision: schematic **S8.5**, board **S8.5-P1.5**; `review-s85.json` replaces
`review-s84.json` (the S8.4 record stays in git history, commit `0bc6f62`).

**Still open after S8.5:** the +5 V protection architecture decision (crowbar vs eFuse); the replug /
POR race (C3); <6 V at the header (C2 of S8.4, below); bench confirmation of the arming timelines; and
every release gate listed at the end of this page.

## S8.4 changelog (2026-11-02, from the three S8.3 reviews)

| Item | Issue | Change | Files |
| --- | --- | --- | --- |
| **C1** | U23 `FLT` wire-ANDed onto `P5_OK`: reverse-current blocking (hot plug into a live +5 V bus, load release held downstream), overload or over-temperature latched every rail off | U23.4 off `P5_OK`: new net `P5_FLT_N` with its own pull-up **R108** 10k and test pad **TP21**, diagnostic only. `P5_OK` = U23 AUXOFF + U18, unchanged. Fault matrix below | `tools/circuit_s8.py`, `hierarchy_s8.py`, `verify_s8.py`, `test_s8.py`, schematic page 06, PCB |
| **C2** | The <6 V header peak is not guaranteed | Kept, stated plainly: the 3 µs case reaches **6.33 V and stays above 6 V for ~193 µs**; a **30 V / 1 Ω / 3 µs** stress case (6.52 V) was added. Neither D10 nor a bench-supply ceiling bounds the header | `tools/s8_calcs.py`, `calcs.json`, `validation.json`, this page |
| **M1** | Startup masking: `TIMER_GO = RUN AND V20_OK` while U2/U3 enable from `MAIN_OK`; a start between U5 turn-on and `V20_OK` never armed the latch | **`TIMER_GO = RUN AND MAIN_OK`** (U13 pin 10), the converter-enable net. R83 220k → **200k** re-centres `V20_OK` to 14.6–17.7 V, below the 18.25 V minimum loaded PD input. **Superseded in S8.5 (B)**: restartable and armable in the PD 5 V phase | `circuit_s8.py`, `verify_s8.py`, `test_s8.py`, `s8_calcs.py` (`startup_window`), page 05/06 |
| **M2** | Load release could reach the OVLO and latch | **R11/R12 0.1 % / 25 ppm** (setpoint 4.856–5.114 V). `calcs.json` → `ovlo_release` (imposed-current model): a release from U23's highest current limit stays **0.109 V below the OVLO minimum** and 0.201 V below the U20 guard. OVLO **falling** threshold computed (5.079–5.336 V); the −35 mV reconnect corner stays open (fail-safe latch) | `circuit_s8.py`, `s8_calcs.py`, `verify_s8.py`, `test_s8.py` |
| **M3** | U20 on VPD after V3V3 collapses; stale "U20 unpowered" rationale | `calcs.json` → `v3v3_loss`: U20 may stay powered, but nothing can be enabled (R64 holds RUN low); node current ≤ 0.15 mA. D22 is **not** a guaranteed cold clamp. Rationale corrected | `s8_calcs.py`, `circuit_s8.py` (U20/D22 notes), `hierarchy_s8.py`, this page |
| **M4** | Protection loops: U23 IN→cap 6.6 mm, OUT→D23 22.7 mm, IN→D21 16.4 mm, U20 VCC→C65 7.4 mm | Local-loop contract `LOCAL_LOOPS` in `check_s8_board.py`, recorded in `board-p1.json`. U23 cell re-placed (P1.4): **3.0 / 3.0 / 5.75 / 5.78 mm, C65 2.3 mm**; every row passes | `check_s8_board.py`, `place_s8.py`, PCB, `board-p1.json`, `placement.json` |
| **M5** | No published continuous rating | **2.5 / 2.0 / 0.9 A**, ≤ 45 W delivered, for VPD ≥ 18.25 V (converter input ≥ 17.25 V after D10 + U5): 75 % of the minimum capability there, to the nearest 0.1 A (+5 V = 75.6 % of U23's minimum limit, 0.65 A headroom, ITIMER open) | `s8_calcs.py` (`rating`), `hierarchy_s8.py`, this page |
| **M6** | −12 V start-up allowance (0.40 mF) below the typical rack (0.44 mF) | Recomputed with the LMR38020 hiccup rule (hiccup only below 40 % after the blanking): model **1.08 mF** at the 15.23 V converter input of the U5 turn-on minimum, 1 A, half the typical blanking; **published allowance 0.846 mF**, capped by TI's ~1000 µF total-output-capacitance guidance. Covers the typical rack with 0.41 mF; acceptance test added | `s8_calcs.py` (`minus12_startup`), `test_s8.py` |
| **M7** | 0.1 mm solder-mask webs on U23 (an IN/OUT bridge silently bypasses the eFuse) | Copper-pad mask expansion 0.05 → **0.025 mm**: every web **0.15 mm**. TP18-to-+5 V no-short bring-up check in notes, validation and here | `s83_parts.py`, footprint, `place_s8.py` (pad refresh), PCB, `circuit_s8.py` (TP18 note), `verify_s8.py` |
| **M8** | Basic-only passive policy unresolved | **Decided:** Extended accepted for the ten 0.1 % dividers only; with 1 % Basic parts four screens fail (`basic_only_counterfactual`) | `s8_sourcing.py`, `sourcing.json`, `s84-sourcing.json`, `s83-sourcing.json` (pointer), `s8_calcs.py` |
| **M9** | Strain relief overshoots the panel by 0.4 mm; IDC envelope margin only 1.1 mm | Both recorded as explicit risks in `mechanical.json` → `risks` | `mechanics_s8.py`, `mechanical.json` |

S8.4 revision: schematic S8.4, board S8.4-P1.4; `review-s84.json` replaced `review-s83.json`
(the S8.3 record stays in git history, commit `a12edd3`).

## +5 V: disconnect rather than discharge the rack

```text
U3 buck / L2 -> P5_RAW ------------------ U23 IN -> OUT -------- +5V -> J2/J3
                   |                       |                     |
            feedback R11/R12        independent OVLO       C35/C60/C73/C74
            (0.1 %, S8.4)            R107+R101 / R102       D23 negative clamp
            C20-C23 + C69-C72        ILM R103+R104
            + C75/C76                C68 dVdt
            D3 negative clamp        EN = common RUN
            D21 transient TVS        FLT -> R108 / TP21 only (S8.4)
                   |
            U20 raw-OV guard -> OV_N -> common FAULT latch -> U5 input OFF

U23 AUXOFF + delivered-voltage comparator U18 -> P5_OK -> qualified fault latch
```

The buck's **feedback and mandatory local output capacitors remain upstream**. The header capacitors
are downstream; no component bypasses the disconnect. U23's back-to-back FETs also block reverse
current, but an external supply connected directly to the rack can still overvoltage the rack:
**this is not an external cross-rail miswiring clamp**.

Removed in S8.3: **Q11, Q12, Q13, U22, R105, R106**, all `CROW_*` nets, SCR-only symbols and the
old crowbar calculations. R101/R102 are reused for OVLO, R103/R104 for ILM, and C68 for dVdt.
S8.2's assertion that an overstressed SCR always fails short is withdrawn; the design does not depend on it.

### Fault matrix (S8.5)

U23 rows are unchanged from S8.4; the last column now follows the S8.5 one-shot arming (B): "inside the
window" means the 0.31–0.88 s after the **first** converter enable since RESET, which no fault can restart.

`P5_OK` is the wire-AND of U23 **AUXOFF** (pin 3) and the U18 delivered-+5 V comparator, pulled up by
R44. U23 **FLT** (pin 4) only drives `P5_FLT_N` (R108 pull-up, TP21). TI's tables:
AUXOFF is low only for input UVP/UVLO, reverse polarity, OVLO and inrush, and stays high for every
load-side event (Table 7-4). FLT is low for over-temperature, persistent current limit, ILM pin
faults and reverse current (Table 7-3); it does **not** report OVLO. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

| Event | U23 response | AUXOFF | FLT (TP21) | U18 (+5 V delivered) | `P5_OK` | Common latch (S8.5 one-shot arming) |
| --- | --- | --- | --- | --- | --- | --- |
| Normal operation | on | H | H | good | H | — |
| Start-up inrush | dVdt ramp | L until done | H | low until > 4.22 V | L | masked only inside the one-shot window (rail-up budget 141 ms vs ≥ 309 ms window) |
| Hot plug into a live +5 V bus / load release held downstream (reverse current) | reverse blocking | H | **L** | good (bus is up) | **H** | **no latch**, inside or after the window (timelines `hot_plug_live_bus`, `load_release_*`) |
| Transient overload above ILIM | current limit | H | L while limiting | good unless +5 V sags below 4.22 V | H, or L if it sags | only if +5 V sags > ~1 ms after ARMED |
| Persistent overload / short | (fast trip,) current limit, then TSD + auto-retry | H | L after the ITIMER interval | **bad** | L | **latched** (via U18); a short present from start-up latches at the window end (no restart) |
| Over-temperature | shutdown, auto-retry | H | L | **bad** | L | **latched** (via U18) |
| P5_RAW above OVLO (5.585–5.848 V) | off, auto-recover below 5.079–5.336 V | **L** | H | bad | L | latched if > ~1 ms after ARMED; brief pulses recover; an event inside the window that has not recovered by its end latches |
| P5_RAW above the U20 +5 V guard (5.677–5.976 V) | off if the OVLO also tripped (bands overlap) | L if OVLO | H | — | — | **FAULT preset at once, also before ARMED** (U5 off) |
| U23 unpowered (P5_RAW 0 V) | off | no active pull-down | H (R108, not driven) | **bad** | L (U18 holds it) | latched / not started |

Input-side events (S8.5; `MAIN_LED_OK` = U5 on with valid status, see the arming section):

| Event | STARTED / ARMED | Result (S8.5) | S8.4 (`TIMER_GO = RUN AND MAIN_OK`) |
| --- | --- | --- | --- |
| VPD brown-out below the U5 turn-off after ARMED | unchanged / held | rails and `MAIN_LED_OK` drop → **latched**, RESET to restart | latched (same) |
| Brown-out inside the window that recovers before its end | unchanged / ARMED at first enable + t_d | runs; a brown-out that has not recovered by then latches | **window restarted** (unarmed > t_d) |
| U5 overload / auto-retry chatter | set at the first enable / ARMED at t_d | **latched at the window end** | **restarted forever, never armed or latched** |
| PD 5 V phase with U5 status floating high | not set (`V20_OK` low) | waits for 20 V | **armed in the 5 V phase, then latched off** |
| RESET pulse (also with PGOOD still high) | cleared, set again at the next enable | new one-shot window | window restarted by the stale-PGOOD drop |

The last row is the dependency DeepSeek noted (TPS25947 §7.3.10): AUXOFF has no active pull-down
without input power, so `P5_OK` relies on U18's comparator in that state.

Do not wire AUXOFF directly to `OV_N`: it is normally low during startup and would prevent startup.
Do not put the buck feedback downstream: a disconnected output must not make the buck demand more voltage.

## Startup sequence and one-shot arming (S8.5, B)

**Required behaviour** (`calcs.json` → `arming.required`; checked by `verify_s8.py` on every timeline):

- **R1 bounded:** whenever the converters are enabled they are armed, except during one window of the U11
  delay (0.31–0.88 s) after the **first** converter enable since RESET; after that `ARMED` is held until
  RESET or a latched FAULT.
- **R2 not restartable:** nothing a fault can toggle (`MAIN_OK`, PGOOD, VPD, `V20_OK`, the rails) restarts or
  extends the window; only RESET (or a power-on reset) does.
- **R3 no early arming:** the window starts only at a genuine converter enable, i.e. U5 on through its own
  UVLO with valid FLT/PGOOD. No threshold below the converter enable point can start it (the PD 5 V phase
  and the `V20_OK` floor cannot).
- **R4 fail-safe:** after `ARMED` any bad status for > ~1 ms latches FAULT, FAULT holds RUN low until RESET,
  and `OV_N` (U20) presets FAULT at any time, also inside the window.

**Topology** (no new IC: the spare U14 gate and U12 flip-flop A are re-used; R83 changes value, TP19 is
copper only):

```text
START_N  = NAND(MAIN_LED_OK, RUN, V3V3, V3V3)      U14 gate 2 (spare in S8.4)
STARTED  = U12 A: PRE_N = START_N, CLR_N = RESET_N, CLK = GND, D = V3V3, Q -> TP19
TIMER_GO = RUN AND STARTED                         U13 gate 3 -> R69/R70 -> U11 SENSE
ARMED    = U11 RESET output (R71 pull-up)          held high because its input is latched
FAULT    = U12 B: CLK = ARMED AND BAD_FILTERED, PRE_N = OV_N, CLR_N = RESET_N   (unchanged)
RUN      = RESET_N AND NOT_FAULT                   (unchanged; U5 SHDN, U23 EN)
```

`START_N` is level-sensitive, so a `MAIN_OK` that is already high when RESET releases still starts the
window; RUN inside the gate keeps PRE_N high while RESET clears the latch (no PRE/CLR contention). Once
`STARTED` is set, a `MAIN_OK` drop no longer touches the timer: an input brown-out, an overload auto-retry or
a stale PGOOD cannot restart it. If the converters are still not good when `ARMED` rises, FAULT latches at
that moment (the `ARMED` edge clocks it; RUN then drops and takes `ARMED` with it).

**`V20_OK` divider** (`calcs.json` → `arming.V20_OK`, independent screen in `verify_s8.py`): R83 **120k**
(same Basic line C25808 as R75) over R84 10k against REF_GOOD (R73/R74 from V3V3), with V3V3 ±2 %,
R73/R74/R83/R84 at 1 % + 1 % TCR (100 °C), LM2901B 5.5 mV offset and 50 nA bias:

| R83 | `V20_OK` trip (VPD) | Above vSafe5V max (5.5 V) | Below U5 turn-off min (15.04 V) | Floor rule (≥ 2 V each) |
| --- | --- | --- | --- | --- |
| **120k (S8.5)** | **9.06 / 9.98 / 10.96 V** | **3.56 V** | **4.08 V** | **holds** |
| 200k (S8.4) | 14.62 / 16.12 / 17.73 V | 9.12 V | −2.69 V (inside the U5 band) | fails |
| 220k (S8.3) | 16.01 / 17.65 / 19.42 V | 10.51 V | −4.38 V (up to above the U5 turn-on band) | fails |

`V20_OK` is therefore a **U5 status-validity floor**, not an input-good threshold: below ~9 V (the PD 5 V
phase) U5's FLT/PGOOD may float high through R63 because U5 is under its 4.5 V operating minimum, and
`V20_OK` masks them; wherever U5 can be on (VPD ≥ its 15.04 V turn-off minimum) `V20_OK` is high, so
`MAIN_LED_OK` = `MAIN_OK` there and `V20_OK` can never be the first status to drop. The **input
qualification is U5's own UVLO** (R2/R3, leakage referred through R2): on **16.23–18.23 V**, off
**15.04–17.12 V**. A 20 V source at −5 % (19.0 V unloaded) turns U5 on with 0.77 V margin; at the 18.25 V
loaded minimum it keeps running with 1.13 V margin. (S8.4 compared the unloaded turn-on maximum with the
loaded minimum and quoted 20 mV; that comparison was wrong.)

```text
USB-C attach: VPD = vSafe5V; U9 -> V3V3; U10 holds RESET_N low >= 12 ms (clears STARTED, FAULT)
RESET_N high: RUN high (U5 SHDN released, U23 EN); U5 in UVLO; START_N high (V20_OK low in the 5 V phase)
PD contract: VPD -> 20 V; V20_OK high at 9.06-10.96 V (U5 status valid, PGOOD low)
VPD >= U5 turn-on: U5 ramp ~12 ms, PGOOD 11.5 ms -> MAIN_OK enables U2/U3 (U4 via Q1) -> START_N low -> STARTED
TIMER_GO = RUN AND STARTED -> U11 -> ARMED 0.31-0.88 s later (rails up within ~141 ms, ratio 2.2)
ARMED: any bad status (MAIN_LED_OK, P12_OK, P5_OK, N12_OK) > ~1 ms -> FAULT -> RUN low -> all off until RESET
OV_N (U20) presets FAULT at any time, also before ARMED
```

**Enabled / armed / fault timelines** (`validation.json` → `startup_arming.timelines`). `verify_s8.py`
builds the logic from the **native netlist** (HC08/HC20 gates, both HC74 flip-flops with asynchronous
PRE/CLR, the U11 delay, the R72/C51 + U15 filter) and drives it with a datasheet-timing plant: U5 UVLO at
its high corners, ~12 ms ramp + 11.5 ms PGOOD rising / 10 ms falling deglitch, rails good 120 ms after
`MAIN_OK` (converter soft starts + U23 dVdt ramp), U5 status floating high below VPD 4.95 V, the
`P5_FLT_N` pulses of U23. Every scenario runs at both U11 delay corners and both `V20_OK` band corners
(times in ms, t_d = 0.31 s / 0.88 s):

| Scenario | First enable | ARMED | FAULT | End state |
| --- | --- | --- | --- | --- |
| Cold start at the worst loaded 20 V minimum (19.0 V unloaded, U5 on at 18.23 V, 18.25 V loaded) | 351.9 | 661.9 / 1231.9 | — | running, armed |
| Slow PD contract (5 V phase 2.5 s, U5 status floating high) | 2551.9 | 2861.9 / 3431.9 | — | running, armed |
| Brown-out after ARMED (VPD 14 V for 50 ms at 1500 ms), RESET at 1900–1915 ms | 351.9, then 1938.6 | 661.9 / 1231.9, then 2248.6 / 2818.6 | 1501.8 | latched at the sag, running again only after RESET |
| Brown-out inside the window (14 V at 450–500 ms) | 351.9 | 661.9 / 1231.9 | — | running (window not restarted) |
| Input overload chatter (U5 on 30 ms / off 20 ms) | 351.9 | at the window end | 661.9 / 1231.9 | **latched** |
| Hot plug into a live bus (rails held from 0 ms, U23 FLT low 330–480 ms) | 351.9 | 661.9 / 1231.9 | — | running, armed |
| Load release after ARMED (U23 FLT low 5 ms at 1500 ms) | 351.9 | 661.9 / 1231.9 | — | running, armed |
| Load release inside the window (FLT low 5 ms at 520 ms) | 351.9 | 661.9 / 1231.9 | — | running, armed |
| U20 guard trip before ARMED (`OV_N` low 1 ms at 420 ms) | 351.9 | — | 420.0 | latched |
| 12 ms RESET while running, PGOOD still high at release | 351.9, then 1512.1 | 661.9 / 1231.9, then 1822.0 / 2392.0 | — | new one-shot window |

**Regression (`test_s8.py` → `test_b_s84_arming_wiring_fails`):** the exact S8.4 wiring rebuilt on this
netlist (U11 → `START_READY` → U12 A clock → `ARMED`, `TIMER_GO = RUN AND MAIN_OK`, U14 gate 2 unused)
fails the same timelines at either `V20_OK` band: armed at 322 / 892 ms in the PD 5 V phase and then
latched off (R3), the window restarted by a brown-out inside it and by the stale-PGOOD drop after a short
RESET (R1/R2), and an overload chatter that never arms and never latches. The S8.4 200k and S8.3 220k
dividers fail the floor rule (`test_c_main_led_ok_and_any_bad_semantics`). `verify_s8.py` also checks all
1024 settled combinations of the gate logic and the native pin roles (TPS3808 against TI's DBV table with
the S8.5 U11 output). These are logic timelines with datasheet timings, not an analog or bench proof.

## Selected part and cost

**TPS259470ARPWR / JLCPCB C3662799**, re-checked live on 2026-11-01 19:52 UTC: **2,525 in stock**,
$1.2943 at 1–9, $1.0696 at 10–29, $0.9465 at 30–99 and $0.8071 at 100–499 (the full ladder is now in
`s84-sourcing.json`). **Extended**, Economic eligible, not Basic. Prices exclude Extended/setup fees,
attrition, PCB, manual parts, shipping and taxes; stock is not reserved.
[source](https://jlcpcb.com/partdetail/TexasInstruments-TPS259470ARPWR/C3662799)

Why the **A** version: good stock at low cost, active current limit, and both AUXOFF and FLT outputs.
The compared TPS259470L listing had only 42 units; TPS259474L uses a different circuit-breaker/PG
interface. The pin-selectable clamp variant is **not** equivalent: its 5.7 V clamp option can reach 6.2 V.
[source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

Whole-design sourced-parts estimate: **$21.96** (S8.4 $21.96, S8.3 $21.88, S7 $27.12). New S8.4 codes: R11
**C705793** RT0603BRD0768KL ($0.035, 23,453 stock) and R12 **C861121** RT0603BRD0713KL ($0.0394,
24,301), both Extended and Economic eligible; R108 reuses the Basic 10k C25804. **S8.5 adds no code:**
R83 120k reuses the Basic **C25808** line of R75 ($0.0016 at quantity 1 in the dated snapshot; S8.4's 200k
C25811, $0.0021, leaves the BOM), so the S8 table has **61 LCSC codes** (S8.4: 62), the BOM **63 lines**
(S8.4: 64) and the total stays **$21.96** (−$0.0005); TP19 is copper only. This total mixes reused dated
rows with live S8.4 rows; it is **not an all-parts fresh quotation**.

### Basic-only passive policy: decided (M8)

**Extended is accepted for the ten 0.1 % / 25 ppm thin-film dividers only** (R93–R96, R98, R99,
R101, R102, and R11/R12 from S8.4; five codes). Every other passive stays Basic. These parts set
protection thresholds: the U20 guard bands, the U23 OVLO and the +5 V setpoint that the OVLO
release proof uses. `calcs.json` → `basic_only_counterfactual` reruns the screens with 1 % + 1 % TCR
Basic parts: **four fail** (the +5 V guard maximum reaches 6.13 V, the −12 V guard minimum falls below
the stacked peak, the OVLO maximum reaches 6.00 V, and the OVLO minimum falls 0.18 V below the
ILIM-maximum release peak). The searched catalog had no Basic 0.1 % 0603 resistor. Extended
per-unique-part fees apply and are not in the totals. Recorded in `sourcing.json` and
`s84-sourcing.json` (`basic_only_policy`). This is a design decision, not an order approval.

## Settings and limits

| Setting | S8.4 result / scope (unchanged in S8.5) |
| --- | --- |
| OVLO divider | R107 510 Ω in series with R101 37 kΩ; R102 10 kΩ; **no intentional filter capacitor** |
| OVLO trip (rising) | **5.701 V nominal; 5.585–5.848 V** tolerance screen |
| OVLO release (falling, new) | **5.179 V nominal; 5.079–5.336 V** (VOV(F) 1.076–1.116 V) |
| +5 V setpoint (U3, R11/R12 0.1 %) | **4.856–5.114 V** (S8.3 with 1 %: 4.724–5.259 V) |
| Current limit | R103 1 kΩ + R104 100 Ω: **3.031 A nominal; 2.647–3.367 A** from TI's tabulated limits (−10.9 / +8.9 %) plus resistor corners. A protection threshold, **not** a load rating |
| Published +5 V rating | **2.0 A** continuous (M5 below) |
| Inrush control | C68 10 nF / 50 V: approximately **0.2 V/ms**, 25 ms to 5 V, typical |
| Overcurrent blanking | ITIMER deliberately NC: fastest response, **no transient allowance above ILIM** |
| Conduction at 2.0 A | **0.113 W typical / 0.18 W** with 45 mΩ; ~13 °C rise at 74.5 °C/W (no vias) |
| Voltage capability | 2.7–23 V operating, 28 V absolute maximum; D21 protects P5_RAW against fault/ringing energy |
| OVP response | **1.2 µs typical only; no specified maximum**; recovery tSWOV 90 µs typical |

OVLO arithmetic includes the IC thresholds, ±0.1 µA input leakage, the 0.1 % / 25 ppm divider
parts and 1 % plus 1 % drift on the Basic trim. These are component-parameter screens, not a
qualification of the PCB. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

## Load release vs the OVLO (M2)

`calcs.json` → `ovlo_release` releases the load into **only the upstream bank at its low-C corner**
(86.1 µF), from the **maximum** 0.1 % setpoint, with 16 cycles of unchanged converter current then
−Vo/L (the S8.3 imposed model; no loop model, no downstream or rack credit):

| Released current | Rise | Peak | Margin to OVLO min 5.585 V | Margin to U20 guard min 5.677 V |
| --- | --- | --- | --- | --- |
| 2.0 A (published rating) | 0.204 V | 5.319 V | **0.266 V** | 0.358 V |
| 2.5 A (S7 target) | 0.260 V | 5.375 V | **0.210 V** (S8.3: 0.066 V) | 0.302 V |
| 3.367 A (U23 ILIM maximum) | 0.362 V | 5.476 V | **0.109 V** | 0.201 V |

No +5 V load can draw more than U23's current limit, so **in this imposed-current model** no
legitimate release reaches either threshold; the release that would just reach the OVLO minimum is
4.24 A. The model is not a TPS62933F loop model (larger output capacitance also slows the loop), so the
hardware claim waits for a real 2.5 A load-release and Bode test. An output short (U23 fast trip with up
to the U3 5.8 A peak limit in L2) is a fault and may trip either threshold; the result is a latched-off
supply (fail-safe).

**OVLO falling threshold:** after a genuine OVLO trip U23 reconnects only once P5_RAW falls below
5.079–5.336 V. Against the 0.1 % setpoint that is **0.194 V nominal margin**, but at stacked corners
the setpoint maximum (5.114 V) sits **35 mV above** the release minimum (S8.3 with 1 %: 179 mV). In
that corner U23 stays open after a genuine overvoltage, `P5_OK` stays low and the common latch holds
every rail off until RESET. This corner stays **open** (fail-safe, regression-tested in `test_s8.py`);
in the model above a load release does not reach it.

## Published conservative rating (M5)

| Rail | Published continuous | Minimum current-limited capability at 17.25 V converter input | Fraction / basis | Below the rated range (14.04 V) |
| --- | --- | --- | --- | --- |
| +12 V | **2.5 A** | 3.55 A (TPS62933F min(IHS+ILS)/2) | 70.4 %: the S7 target, below 75 % | 70.4 % |
| +5 V | **2.0 A** | **2.647 A** (U23 ILIM minimum; converter 3.55 A) | **75.6 %** (nearest 0.1 A); 0.65 A headroom with ITIMER open | 75.6 % |
| −12 V | **0.9 A** | 1.238 A (LMR38020 (ILS min + ripple/2)(1 − D)) | 72.7 % | **80.5 %** (1.118 A) |
| Total | **≤ 45 W delivered** | input 52.9 W / 2.64 A at 20 V for the worst-efficiency mix | needs a verified 20 V ≥ 3 A source; a 45 W (20 V / 2.25 A) adapter supports ~38 W delivered |

The rating is **specified for VPD ≥ 18.25 V** (a 20 V PD source at −5 % less a 0.75 V cable allowance).
R2/R3 sense VPD before D10, so the converters see **17.25 V** after the 1.0 V D10 + U5 drop screen
(0.75 V diode, 53 mΩ maximum RON at U5's 4.698 A high-corner limit; no steady input current can exceed
U5's actual limit, so this is a conservative drop). The rule is 75 % of the minimum
current-limited capability there, **rounded to the nearest 0.1 A** and capped at the S7 target
(`calcs.json` → `rating`), so +5 V lands at 75.6 %. U5 keeps the converters running down to its
turn-off minimum (VPD 15.04 V, converter input 14.04 V) when a source sags; there the rating is
**not specified** and the −12 V 0.9 A uses 80.5 % of its minimum capability. ITIMER is open, so the
+5 V headroom must also absorb load steps and hot-plugged modules' inrush. All three ratings at
once would be 51.2 W delivered (59.9 W / 3.0 A input), hence the 45 W total. The S7 target budget
(64.4 W / 3.22 A at 20 V) remains a planning figure, **not** a rating. Above ~2 A per rail use both
J2 and J3. This is a prototype rating from datasheet minimum limits and assumed efficiencies, not a
measured or thermally qualified one; **U23's 3.03 A nominal ILIM is never a load rating**.

## U20/U18 on VPD and V3V3 loss (M3)

U20 **and U18** retain the LM2901BIDR footprint and sourcing line. Their VCC pins and their **50 V
C65/C57 bypass capacitors** connect to **VPD**, before U5, after F1. All open-collector outputs still
pull up only to **V3V3**; no 20 V signal reaches the logic. At the conservative **15 V active-system
supply screen** the full-temperature common-mode ceiling is **13 V**, leaving **11.736 V** above
reference plus offset (S8.2's 3.3 V supply left −25 mV). [source](https://www.ti.com/lit/ds/symlink/lm2901b.pdf)

**When V3V3 collapses (or is not yet up) while VPD is present, U20 can stay powered.** The S8.3
rationale ("U20 is unpowered in this state") was wrong and is withdrawn. `calcs.json` → `v3v3_loss`:

- **No enable path:** U10–U15 are unpowered and every pull-up (R97 `OV_N`, R35/R44/R62, R63
  `MAIN_OK`) goes to the dead V3V3; **R64 holds RUN low**, so U5 SHDN, U23 EN and the U2/U3 enables
  stay low whatever U18/U20 output. Their open-collector outputs cannot back-power the logic.
- **Common mode:** REF_OV follows V3V3 to ~0 V; the positive-rail channels see taps ≥ 0 V.
  With the rack holding −12 V the `MON_OVN` node goes negative (−1.0 V open circuit at −12 V).
- **Clamp conduction:** D22 conducts 83–119 µA (−12 V to a −16 V fault) and holds U20 pin 9 near
  **−0.24 V at 25 °C only**. Cold (~+2 mV/°C) it can pass the LM2901B −0.3 V input limit (~−0.37 V
  screen at −40 °C). **R99 bounds the node current to ≤ 0.15 mA**, against the −50 mA input-current
  rating; TI notes the output may then be incorrect, which cannot enable anything here. D22 is
  therefore **not a guaranteed −0.3 V clamp**; the protection rests on the current bound and the
  absent enable path.
- **D1:** SMBJ22A (22 V stand-off) does not conduct in these states. Its 35.5 V rated clamp leaves
  only 0.5 V to the comparators' 36 V operating maximum (38 V absolute): measure VPD ringing at U18/U20.
- **Replug into a rack that holds −12 V (S8.5, item C3): OPEN.** The −12 V channel reads OV until REF_OV
  exceeds |V| × R98/R99 (1.09–1.16 V incl. offset and bias). REF_OV charges through R100 into C67 **while R98
  already draws current into the D22-clamped `MON_OVN` node** (Thevenin 2.66 V behind 1.80 kΩ), so
  `calcs.json` → `replug_por` gives **9.5 ms nominal (−12 V), 13.75 ms at the worst corner** (R100 +2 %,
  C67 +10 % × +15 % X5R, V3V3 −2 %, −12.624 V) against the **≥ 12 ms** TPS3808 POR release: margin
  **−1.75 ms, not established**. Consequence: when the bus is already held at −12 V at power-up (a second
  supply, or a quick replug while the rack capacitance holds charge), `OV_N` can still be low when RESET
  releases, FAULT is preset and MAIN stays off until RESET is pressed: a fail-safe nuisance latch, no damage.
  Candidate fixes, **not implemented in S8.5**: C67 4.7 µF (still right of the TLV431 instability region)
  roughly halves the settle time, or a CT capacitor on U10 lengthens the POR delay; both change the RESET
  timing and need their own review. The S8.4 "~1 ms margin" ignored the R98 load and is withdrawn.

The guard trips remain +14.88 V, **P5_RAW +5.83 V** (5.677–5.976 V) and −13.64 V nominal; U18 monitors
the **delivered** +5 V. Cold VF, leakage, residual −12 V, power-down and replug stay bench gates. The
guard reference's temperature range limits the threshold screen; the comparator's wider range is not
a whole-module temperature rating.

## Capacitance, normal transients and fault sensitivity

+5 V has **10 × 22 µF upstream** (C20–C23, C69–C72, C75/C76) and **4 × 22 µF downstream**
(C35/C60 at the headers, C73 at U23 OUT, C74 at the header strip since P1.4). All are the existing
25 V Basic part. Capacitor-study assumptions give **86.1–193.6 µF upstream** and **34.4–77.4 µF
downstream**: assumed bias/tolerance/temperature/aging screens, not measured manufacturer curves.

### Failed-high-side screen: <6 V at the header is NOT guaranteed (C2)

`calcs.json` → `disconnect.fault_delay_sensitivity` models a hard U3 high-side short, VIN energy,
L2, separate raw/output banks, U23 on-resistance, D21, U20 RC and U5 shutdown. It takes **no credit**
for U23 current-limit/fast-trip action and deliberately keeps the S8.3 5.259 V starting voltage.
U23 turn-off is idealized after a chosen delay; there is no transistor model or real layout.

| Case | Delay assumption | Header peak | Time above 6 V (200 µs window) | With 100 nH energy estimate |
| --- | --- | --- | --- | --- |
| L2 3.3 µH, 20 V input | 1.2 µs typical | 5.910 V | 0 | 5.923 V |
| L2 reduced to 1 µH | 1.2 µs typical | 5.981 V | 0 | **6.022 V** |
| L2 3.3 µH | **3 µs sensitivity** | **6.333 V** | **~193 µs** | 6.351 V |
| L2 1 µH | 3 µs sensitivity | **6.795 V** | ~196 µs | 6.859 V |
| **30 V source behind 1 Ω**, L2 3.3 µH (S8.4) | **3 µs** | **6.517 V** | **~195 µs** | 6.552 V |
| L2 1 µH | 5 µs sensitivity | **7.777 V** | ~196 µs | 7.824 V |
| Half assumed capacitance, 26 V input, L2 1 µH | 3 µs sensitivity | **8.041 V** | ~198 µs | 8.122 V |

**The design does not guarantee <6 V at the header.** TI specifies tOVLO as 1.2 µs *typical* with
no maximum, and nothing upstream bounds the result: **neither D10, U5's current limit, nor a
bench-supply ceiling (the 30 V / 1 Ω case) keeps the header below 6 V** once the delay reaches 3 µs.
In those cases the header stays above 6 V for the rest of the window: with U23 blocking reverse
current only R77–R79 (55 kΩ) or the connected modules discharge it. These exposed failures of the
6 V screen are **not hidden by the tests** (`test_s8.py` asserts they stay above 6 V). Before using
valuable modules, measure the maximum header peak against the modules' allowable voltage, including
failed regulator, feedback-open, startup, load-release, hot/cold and RESET sequences.

D21 is **upstream**, where its 6.4–7 V breakdown and approximately 9.2 V rated pulse clamp protect
U23 and absorb stored energy. It is neither a precision 5 V clamp nor rated for a continuously fed
failed converter; U20/U5 must stop the source. D23 and C73 address negative output transients;
verify U23 OUT's −0.3 V limit at the actual pins.

### Startup and thermal limitations (M6)

The converter soft-start capacitors are 100 nF. U23 adds a second ramp (13–75 ms sensitivity to
5 V); a conservative serial sum is about 141 ms against the 309 ms startup-window minimum.

**−12 V start-up:** the LMR38020 enters hiccup only if FB stays below **40 % of VREF** (|Vout| < 4.80 V)
while its low-side limit acts for 256 cycles, and hiccup is disabled for the first 18 ms (typical;
no minimum). The rail therefore has to pass 4.8 V inside the blanking time, not reach 12 V as the S8.3
screen assumed. `calcs.json` → `minus12_startup` integrates the current-limited output
((ILS min + ripple/2)(1 − D)) against a constant 1 A load from 0 V. The converters cannot start below
the U5 turn-on minimum (VPD 16.23 V, i.e. **15.23 V converter input** after the 1.0 V D10 + U5 drop
screen). There, with **half** the typical blanking (TI gives no minimum), the model allows **1.08 mF**
of rack (2.25 mF at the full 18 ms; 1.04 mF if the source sags to the U5 turn-off minimum, 14.04 V
converter input; S8.3 rule 0.40 mF). TI also advises limiting total output capacitance to ~10 × the design value or
1000 µF, whichever is smaller (SNVSC40E 9.2.2.5). With the rated 7 × 22 µF bank that caps the rack at
**0.846 mF, the published allowance**. The typical **0.44 mF rack fits with 0.41 mF margin** and reaches
12 V in well under 40 ms. `test_s8.py` makes this an acceptance test (published allowance ≤ the TI cap
and the model at every corner, ≥ typical rack + 0.3 mF). It is an analytic screen, not a guarantee:
hiccup-restart behaviour and the blanking minimum are not specified, and starting the real rack at the
lowest input stays a bench test.

**+5 V start-up:** at the 2.0 A rating the constant-current screen allows ~1.6 mF of extra rack
capacitance at the fastest dVdt corner (0.30 mF at 2.5 A). U23 folds current back below 1.9 V (limit
not specified), and a constant full-current load from zero volts dissipates several watts during the
ramp. Measure actual module load current versus voltage. D10's existing thermal issue is unchanged.

## P1.5 fit placement, mask webs and mechanics

(The S8.5 P1.5 placement image is in git `5a3a686`; the current one is in the S9.0 section.)

The PCB is a **fit draft**, not a final power-loop layout. It keeps the mechanical anchors, outline,
stackup, rules and retained footprint UUIDs/models. **P1.5 moves no part**: it only adds the copper-only
pad **TP19 (`STARTED`)** in the front logic test-pad row left of R64 (89.35, 100.0; courtyard 1.28 mm from
the edge), and the sync re-assigns the arming nets on the existing U11/U12/U13/U14/R71 pads
(`placement.json`: added TP19, moved none). P1.4 had moved 24 retained parts and added R108/TP21.

**Local-loop contract (M4):** `tools/check_s8_board.py` `LOCAL_LOOPS` measures the pad-centre
straight-line distance from each listed IC pin to the nearest pad of its bypass capacitor or clamp
on the same net, and fails the placement check above the limit (`board-p1.json` → `local_loops`):

| Loop | Limit | P1.3 | P1.4 = P1.5 |
| --- | --- | --- | --- |
| U23 IN (pad 5) → 22u (C69) | 3.5 mm | 6.63 mm | **3.01 mm** |
| U23 OUT (pad 6) → 22u (C73) | 3.5 mm | 4.80 mm | **3.01 mm** |
| U23 IN → D21 | 6.0 mm | 16.36 mm | **5.75 mm** |
| U23 OUT → D23 | 6.0 mm | 22.71 mm | **5.78 mm** |
| U20 VCC (VPD) → C65 | 4.5 mm | 7.36 mm | **2.31 mm** |
| U18 VCC → C57 | 4.5 mm | 3.53 mm | 2.92 mm |
| U12 V3V3 → 100n (C52) | 6.0 mm | 7.82 mm | **2.27 mm** |
| LDO, U5, CH224A, converter HF caps, TLV431, other logic | 4.5 / 6.0 mm | pass | pass |

U23 is turned 90° so its IN strip faces C69 + D21 and its OUT strip C73 + D23; R102/R101/R107 and
R108 form the row above, R103/R104/C68 the logic side; D23 left the header strip (C74 and TP18 take
that slot). These are straight-line screens: they do not prove routed loop area. Use copper pours
for the IN/OUT strips when routing.

**U23 mask webs (M7):** the RPW0010A copper gaps are all 0.20 mm. S8.4 sets the copper-pad solder-mask
expansion to **0.025 mm** (inside TI's 0.05 mm maximum), so every web, including the IN/OUT web, is
**0.15 mm** (was 0.10 mm). Confirm the fab's mask-web capability. **Bring-up check:** unpowered,
TP18 (P5_RAW) to J2/J3 pin 11/12 (+5 V) must **not read a short in either meter polarity**. Expect
roughly 18 kΩ / 55 kΩ plus a clamp-diode drop through the divider networks and GND, rising while the
banks charge (`calcs.json` → `bringup_tp18`). A near-0 Ω reading means an IN/OUT bridge that bypasses
the eFuse.

Placement screens (P1.5): all 191 parts on F, no parked parts, no courtyard overlaps, 1 mm edge rule holds
apart from the retained approved panel overhangs (closest D23 1.05 mm), the bracket nut/driver circles
are clear (closest C71 0.405 mm), and 2 mm hand-solder clearance around J1/D8/J2/J3 holds. SW1 (machine
placed) still has C75 at 0.925 mm, report-only. Courtyard fill is 67.5%. Native DRC reports the
intentional routing opens separately; it does not qualify current-path geometry.

- Board depth is Z2..50 from the panel front; 48.4 mm behind the panel rear.
- J2/J3 pin 1 stays at Y76/Y107, Z44. Both outputs share one supply/protection path.
- Existing two B-side printed L brackets, M3 bolts and tool envelopes remain unchanged.
- The regenerated nominal 3D interference screen has zero overlaps. U23 uses a **2.1 × 2.1 × 1.0 mm
  maximum-body proxy**, not a manufacturer STEP model; J1/SW1/L1–L3 also use proxies.

**Mechanical risks (M9), recorded in `mechanical.json` → `risks`:**

| Risk | Value | Status |
| --- | --- | --- |
| IDC strain relief | a clip-type strain relief (16.3 mm drawing worst case) reaches X20.4: **0.4 mm past the 4HP panel edge**, into the neighbouring module | **not approved**: use a socket without the tall strain relief, or measure a lower one |
| IDC envelope margin | the proposal mated plug/ribbon envelope ends at X18.9: **only 1.1 mm** inside 4HP | open: the cable/plug is not in the BOM and the drawing values were text-extracted; freeze the part and check the tolerance stack in the case |
| Case depth | the board reaches 5.7 mm deeper than the bus header tops in the 60 mm case | open: it cannot sit directly over a busboard header |
| 3D proxies | U23, J1, SW1, L1–L3 | open: nominal screen, not an assembly approval |

(The S8.5 assembly render is in git `5a3a686`.)

## Reproducibility and verification

Generators remain derived from the untouched S7 circuit. The shared toolkit performs native checks;
its flat edit primitives cannot add the new parts or synchronize nets, so the S8 generator and
bounded `place_s8.sync_candidate()` perform those operations on a **separate candidate**, which is
checked and then copied into the module. The sync refuses routed boards, preserves retained
UUIDs/models, verifies the source placement against its recorded baseline, and (S8.4) copies only the
U23 copper-pad mask expansion from the pinned footprint. No rule/severity/exclusion is relaxed. S8.5 was
synchronized from the committed S8.4 / P1.4 board and record; raw reports and the tests log stay in the
git-ignored `research/s85/` and are **not** hashed (a clean clone does not have them).

```sh
python3 -B modules/usb-power-45w/tools/build_s8.py --output-root <candidate-module-root>
python3 -B -c "import sys; sys.path.insert(0, 'modules/usb-power-45w/tools'); import place_s8; \
  place_s8.sync_candidate('modules/usb-power-45w/hardware/single/usb-power-45w-single.kicad_pcb', '<candidate-module-root>')"
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/usb-power-45w/tools/kicad-project-single.json \
  --reports modules/usb-power-45w/research/<new-check-directory>
python3 -B modules/usb-power-45w/tools/verify_s8.py --netlist <check-directory>/netlist.xml
python3 -B modules/usb-power-45w/tools/check_s8_board.py --out modules/usb-power-45w/docs/s8-single/board-p1.json
python3 -B modules/usb-power-45w/tools/s8_calcs.py --out modules/usb-power-45w/docs/s8-single
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
python3 -B modules/usb-power-45w/tools/review_s8.py --check <check-directory> --tests-log <log> \
  --out modules/usb-power-45w/docs/s8-single/review-s85.json
```

The review record hashes the test sources, so after any source change the old record is stale: delete
it, run the suite (the hash test skips), write the new record, then run the suite again (all tests,
including the hash check). The BOM is the native `kicad-cli sch export bom` with fields Reference/Value/Footprint/QUANTITY/LCSC/
MPN/Manufacturer grouped by Value, Footprint, LCSC, MPN and Manufacturer. For candidate tests, set
`S8_DESIGN_ROOT` to that candidate module root; mechanical generation accepts the same variable and
`S8_ASM_WORK`.

**S8.5 results** (`review-s85.json`): native ERC **0**; DRC **0 violations, 0 warnings, 0 exclusions,
schematic parity 0, 430 unconnected** (routing opens; S8.4 429: +1 = `STARTED` +2 and `START_N` +1 new,
`START_READY` −2 gone, `ARMED`/`MAIN_LED_OK`/`RUN`/V3V3 +1 each, `MAIN_OK` −1, GND −3); exact native
ref/pin/net parity **equal**; **191 refs / 85 nets** (118 including NC pins, 33 NC pins); BOM **63 lines /
171 refs + 20 test pads = 191** (exact parity, field match); `verify_s8.py` passes **1024** settled latch
combinations and every arming timeline (0 violations); the module suite passes, **50 tests, 0 skipped**
(41 in `test_s8.py`), also from a fresh clone. New tests: the S8.4 arming wiring and the S8.4/S8.3
`V20_OK` dividers rejected (regressions), nine broken-latch negative controls, the `STARTED`/`START_N`/
`ARMED` nets straight from the native netlist, the `MAIN_LED_OK`/`ANY_BAD` semantics, the replug/POR
race kept OPEN, the window budget, and a review record that hashes no git-ignored file. The S8.4 tests
(C1, M2–M9, C2 exposure, pin roles, bypass/feedback/TVS placement, loop contract, mask webs, risks) are
unchanged. The tests log and the raw check directory are local (`research/s85/`, git-ignored).

S8.4 results (history, `review-s84.json` in git `0bc6f62`): ERC 0; DRC 0 / parity 0 / 429 unconnected;
190 refs / 84 nets; BOM 64 lines, 171 + 19 test pads; 512 settled latch combinations; 45 tests.

**Release gates remain open:** the +5 V protection architecture decision (crowbar vs eFuse; S8.5 keeps
U23), the replug / POR race (C3), bench confirmation of the one-shot arming (window length, brown-out and
overload-chatter latching), routing and routed loop areas, regulator stability, measured capacitor
behavior, fault-voltage and restart tests (<6 V is not established), startup/foldback/thermal tests
including −12 V into the real rack, the published rating's measurement, connector/cable current and fit,
VPD ringing / cold clamp, fabrication/CAM and manual assembly preview. No fabrication files, vendor upload
or order are part of this change.
