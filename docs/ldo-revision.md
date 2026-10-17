# LDO-R1 quiet-rail prototype

Canonical PCB integration is complete. The completed workspace028 placement was
retained: all88 original electrical footprints keep exact poses, sides, pads and nets.
Five parallel capacitors fix the demonstrated deficiency. Final inventory is93
electrical+4 mechanical footprints,536 tracks,196 filled/capped vias,8 zones.
No final+5V LDO was added; the independent buck circuit and fixed interfaces remain.

## Approved setpoints and limits

Raw rails are +13.530610667/-13.920584956V nominal. Positive divider
R12+R75=1.5M+23.2k over R13=150k; negative divider R14+R60=1.6M+150k,
R15+R76=150k+2.49k; 0.1%,<=25ppm/K requirements. Do not substitute old14.15V
setpoints. `tools/ldo_budget.py` retains explicit corners, bias-current signs,
100mV peak ripple/transient allocation and conditional dropout/headroom analysis.
The ripple allocation is not a bench result; no arbitrary extra rail reserve.

U12 TPS7A4700RGWR/C114839: ANY-OUT5/6/9/11 GND,4/8/10/12 open; SENSE3=P12,
EN13=PRAW, EP21=GND. U13 TPS7A3301RGWR/C90082: IN15/16 and EN13=NRAW,
OUT1/20=N12, FB3=negative divider, GND7/EP21=GND. Final outputs nominal
+12.000/-11.997925V before negative FB current. Both RGW packages are <=1mm high.

## Corrected capacitor banks — explicit prototype screening

All bank capacitors are exact Samsung CL31A226KAHNNNE/C12891,22uF±10%,25V,
X5R,1206,nonpolar,max1.8mm. Three positive-output parts were demonstrably
insufficient (16.675uF typical at12.3V BEFORE extra derating); that is rejected.

| Bank | References | Bias screen | Effective-C screen | Required |
|---|---|---:|---:|---:|
| IN+ | C48-50,C63 |14.8V|12.592uF|10uF|
| OUT+ | C51-53,C64-66 |12.4V|23.990uF|20uF accuracy|
| IN- | C54-56,C67 |14.8V|12.592uF|10uF|
| OUT- | C57-59 |12.4V|11.995uF|10uF|

Manufacturer typical bias curve x0.90 tolerance x0.85 temperature x0.95 aging
allowance; NOT guaranteed minima. The12.5V combined-temperature typical curve
also remains above the0.85 relative-temperature screen. Five-percent aging is an
explicit prototype allowance, not lifetime qualification. Lot/AC-level/bias/temp
interactions require measurement before performance claims. Keep X5R bodies<=85C.
Low-ESR ceramic matches both TI recommendations; individual typical ESR is not
assembled-bank impedance. No artificial series ESR or changed raw voltage.

C63-C66 are BACK; C67 is FRONT, keeping all U13 capacitors front-local as TI
recommends. U12 original three-per-bank remain front-local; back parts supplement
capacitance via short paths and existing returns. This departs from the preferred
all-same-side U12 layout: verify ringing/load-step stability, not just DC capacitance.
Only one oldP12 bottom segment was replaced; no P5/MID copper was changed from028.
Back body+solder+registration=2.05mm from fixedX3.1 datum leaves1.05mm insideX0.
Actual back courtyards clear brackets, mounting/tool volumes, THT tails, panel,
harness and the reserved strap corridor; see `ldo-evidence/backside-fit.json`.
No Economy PCBA qualification is claimed for this two-sided assembly.

C60 remains1uF/50V X7R positiveNR, C61 remains100nF/50V X7R negativeNR/SS,
and C62 remains10nF/50V X7R across the entire negative upper divider. No timing,
noise/PSRR, reverse/shutdown or current rating is inferred from these nominal values.

## Startup, reverse current and shutdown — not qualified

- Neither LDO blocks reverse current. EN is tied to its own raw input. For the
  negative regulator EN≤−2 V enables it; ±0.4 V is off. EN/GND absolute range is
  −36..+10 V. Both LDO outputs are high impedance when disabled; existing10k
  final bleeders are unchanged. They are not an instantaneous discharge system.
- D27/D28 are **SS34 / C8678** discharge shunts: positive OUT anode→IN cathode;
  negative IN anode→OUT cathode. They provide an external current path, **not
  isolation**. No external active source or hot-parallel supply at J7 is allowed.
- Crucially, SS34 forward drop does **not** prove negative OUT−IN≥−0.3 V.
  FB−IN and NR−IN also must remain≥−0.3 V; FB/NR relative GND must remain
  −2..+0.3 V. D28 alone does not protect all of these nodes. Abrupt raw collapse,
  shorts, external backdrive and stored NR/output charge remain unresolved.
- C62 can kick FB positive as N12 rapidly returns toward0 V. This is the polarity
  counterpart of the shutdown issue in [TI SBVA042 §2.3](https://www.ti.com/lit/an/sbva042/sbva042.pdf).
  10nF across an ideal12 V step could transfer120nC; initial divider impedance is
  about9kΩ. A slow bleed is different from a forced short. No internal clamp
  capability, acceptable injection current or clamp Vf is assumed. Capture FB,
  NR, IN and OUT together during startup, retry, unplug, unequal rail collapse
  and shorts; add a proven clamp/discharge solution if required. **Do not call
  this design reverse/short-transition qualified just because ERC passes.**
- Quiet-output intent is implemented, but no noise µVrms/PSRR guarantee at J7 is
  claimed. Relevant TI low-noise headline values use particular C, voltage/load
  and bandwidth conditions, not this unbuilt board automatically.

## Dissipation and unchanged upstream capacity

This is **noise cleanup, not a capacity upgrade**. The user's800mA aspiration is
not imposed as a release gate and is not advertised as an achieved rating.

| Load per rail | Positive pass loss nominal / corner | Negative pass loss nominal / corner |
|---|---:|---:|
| 250mA diagnostic starting point | 0.383 /0.591 W | 0.481 /0.758 W |
| 800mA aspiration | 1.224 /1.890 W | 1.538 /2.425 W |
| 1A IC rating, not supply rating | 1.531 /2.363 W | 1.923 /3.031 W |

Add |VIN| x IGND. Full-load worst-case IGND and this board's thermal resistance
are not established; do not apply JEDEC thetaJA as measured carrier performance.
See the exact reproducible budget for every assumption. No1A continuous claim.

The existing ~1.987A nominal eFuse input limit at9 V is17.881 W, shared with final
P5 and conversion losses; two12 V×800mA outputs alone are19.2 W. The TPS65131
switch peak current is not rail output current. An illustrative CCM screen at
MID5 V,4.7µH−20%,1.25MHz,0.5 V diode and1.8A peak gives only~519mA boost/~362mA
inverting before further losses. The1.8A table conditions differ from this operating
point, so these are screening estimates, not guaranteed output limits. Start bench
characterization modestly (e.g.250mA/rail), sweep independent and combined loads,
and record regulation/thermal limits. No converter/eFuse/P5 capacity changes were made.

