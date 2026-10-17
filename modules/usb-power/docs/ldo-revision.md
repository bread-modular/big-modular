# LDO-R1 quiet-rail prototype — current 043 capacitor closure

> Migration recovery: source/electrical content below is retained checkpoint evidence.
> `jlcpcb/` is a STALE recovered Git export snapshot, not a fresh migrated export.
> Run commands from `modules/usb-power`; shared `opt/` stays at repo root. See
> [migration-recovery.md](migration-recovery.md) for current checks and Astra handoff.

Canonical native source is the reviewed 040 basic-passive checkpoint, **not a
manufacturing release**. The 043 capacitor closure is implemented in the frozen
native source; its counts/fields are independently rechecked by the release tools.

Current 043 inventory: 107 electrical + 4 mechanical footprints, 585 tracks, 207
ordinary 0.300 mm plated through vias, 8 zones. All components are front-side;
there are no B.Cu electrical footprints and no B.Paste component apertures. The
fixed panel, USB/retry/red-LED/output interfaces and mechanical contract are
unchanged. Production/ldo-r1 is regenerated from this 043 source; historical
production/hro-r1 remains untouched.

## Approved setpoints and limits

Raw rails are +13.537080/-13.928806 V nominal. The positive divider is
R12+R75 = 1.5 M + 24 k over R13 = 150 k; the negative divider is
R14+R60 = 1.6 M + 150 k, R15+R76 = 150 k + 2.4 k. R12/R14 remain 0.1%, 25 ppm/K;
the substituted Basic resistors are 1%, 100 ppm/K. This is a mixed model, not a
blanket precision assumption. The final negative output is -12.02025 V before
negative FB current.

`tools/ldo_budget.py` computes independent corners, bias-current signs, a 100 mV
peak ripple/transient allocation and explicit conditional headroom. The ripple
allocation is not a bench result. MID/P5 nominal is 5.007547 V; the full
reference + 1%/100 ppm/K DC corner is 4.712887..5.318152 V, and the stated ripple
allocation gives 5.418152 V worst peak against the 5.5 V MID limit.

**Known prototype limitation, not waived:** negative minimum headroom is
0.178019 V at the full corner. The 0.8 V full-temperature 1 A negative
dropout/accuracy condition FAILS. No positive full-temperature or 1 A rail
guarantee is claimed.

U12 TPS7A4700RGWR/C114839: ANY-OUT 5/6/9/11 GND, 4/8/10/12 open; SENSE3=P12,
EN13=PRAW, EP21=GND. U13 TPS7A3301RGWR/C90082: IN15/16 and EN13=NRAW,
OUT1/20=N12, FB3=negative divider, GND7/EP21=GND. Both RGW packages are <=1 mm high.

## LDO capacitor banks — explicit prototype screening

All bank capacitors are exact Samsung CL31A226KAHNNNE/C12891, 22 uF ±10%, 25 V,
X5R, 1206, nonpolar, max 1.8 mm. The 17 LDO-bank parts are unchanged.

| Bank | References | Bias screen | Effective-C screen | Required |
|---|---|---:|---:|---:|
| IN+ | C48-50,C63 |15.0 V|12.359 uF|10 uF|
| OUT+ | C51-53,C64-66 |12.4 V|23.990 uF|20 uF accuracy|
| IN- | C54-56,C67 |15.0 V|12.359 uF|10 uF|
| OUT- | C57-59 |12.9 V|11.400 uF|10 uF|

Manufacturer typical bias curve x0.90 tolerance x0.85 temperature x0.95 aging
allowance; NOT guaranteed minima. Lot/AC-level/bias/temp interactions require
measurement before performance claims. Keep X5R bodies <=85 C.

## Implemented 043 local-capacitance plan

The Sol041 sizing and Astra043 implementation resolve the two 040 local-cap
blockers without changing the ICs or rail setpoints:

- C5/C18 become 22 uF C12891. New C68/C69 add one 22 uF per buck at VPROT/GND,
  giving 2 x 22 uF local screen 10.664 uF at 9.45 V per buck (>10 uF TI local
  recommendation).
- New C70/C71 make three local 22 uF at MID/L1 with C6. Remote C37 is retained
  but is not counted as local.
- New C72 makes three local 22 uF at P5/L4 with C19/C38. Each 3 x 22 uF bank
  screens 27.631 uF at 5.5 V.
- Lowest Vout 4.712887 V with 27.631 uF gives TI Eq.14 fo = 39.164 kHz, below
  the <40 kHz no-feedforward guideline.
- C4/C16/C17 remain C13585; the 17 LDO caps are unchanged. The input nominal
  increase is +68 uF; inrush is reviewed by Astra, not qualified here.
- The 10 uF input and 40 kHz crossover figures are application recommendations,
  not absolute IC guarantees. Typical screens and bench/loop evidence remain
  pending. C8/C9 local 3.09 uF at 15 V give an approximate 44/49 mVpp screen at
  250 mA plus ESR/transients; this is a bench gate, not a stability guarantee,
  and the distant NRAW bank is not claimed as ideal AC decoupling.

## Startup, reverse current and shutdown — not qualified

- Neither LDO blocks reverse current. EN is tied to its own raw input. For the
  negative regulator EN<=-2 V enables it; ±0.4 V is off. EN/GND absolute range is
  -36..+10 V. Both LDO outputs are high impedance when disabled; existing 10 k
  final bleeders are unchanged. They are not an instantaneous discharge system.
- D27/D28 are **SS34 / C8678** discharge shunts: positive OUT anode->IN cathode;
  negative IN anode->OUT cathode. They provide an external current path, **not
  isolation**. No external active source or hot-parallel supply at J7 is allowed.
- SS34 forward drop does **not** prove negative OUT-IN >= -0.3 V. FB-IN and NR-IN
  also must remain >= -0.3 V; FB/NR relative GND must remain -2..+0.3 V. Abrupt
  raw collapse, shorts, external backdrive and stored NR/output charge remain
  unresolved.
- C62 can kick FB positive as N12 rapidly returns toward 0 V; this is the
  polarity counterpart of the shutdown issue in TI SBVA042 §2.3. 10 nF across an
  ideal 12 V step could transfer 120 nC; initial divider impedance is about 9 kΩ.
  A slow bleed is different from a forced short. No internal clamp capability,
  acceptable injection current or clamp Vf is assumed. Capture FB, NR, IN and OUT
  together during startup, retry, unplug, unequal rail collapse and shorts.
- Quiet-output intent is implemented, but no noise uVrms/PSRR guarantee at J7 is
  claimed.

## Dissipation and unchanged upstream capacity

This is **noise cleanup, not a capacity upgrade**. The 800 mA aspiration is not a
release gate and is not advertised as an achieved rating.

| Load per rail | Positive pass loss nominal / corner | Negative pass loss nominal / corner |
|---|---:|---:|
| 250 mA diagnostic starting point | 0.3843 / 0.6462 W | 0.4771 / 0.9053 W |
| 800 mA aspiration | 1.2297 / 2.0679 W | 1.5268 / 2.8971 W |
| 1 A IC rating, not supply rating | 1.5371 / 2.5849 W | 1.9086 / 3.6213 W |

Add |VIN| x IGND. Full-load worst-case IGND and this board's thermal resistance
are not established; do not apply JEDEC thetaJA as measured carrier performance.
See the exact reproducible budget for every assumption. No 1 A continuous claim.

The existing ~1.987 A nominal eFuse input limit at 9 V is 17.881 W, shared with
final P5 and conversion losses; two 12 V x 800 mA outputs alone are 19.2 W. The
TPS65131 switch peak current is not rail output current. An illustrative CCM
screen at MID 5 V, 4.7 uH -20%, 1.25 MHz, 0.5 V diode and 1.8 A peak gives only
~519 mA boost/~362 mA inverting before further losses. These are screening
estimates, not guaranteed output limits. Start bench characterization modestly
(e.g. 250 mA/rail) and record regulation/thermal limits.
