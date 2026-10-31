# Capacitor study: four electrolytics vs MLCC banks (research only)

> **LIMITATIONS / NOT A DESIGN APPROVAL.** Passive ladder networks, an averaged
> constant-power load and *imposed* converter current trajectories. No TPS62933F,
> LMR38020F, TPS16630 or LM5067 loop is modelled (compensators are internal and are not
> invented). Every capacitance/ESR/ESL is a bounded assumption, not manufacturer data for
> the fitted parts. Results rank options *under those assumptions only*; they are not a
> closed-loop forecast, a thermal/lifetime proof, a cost claim or a GO to route. No
> concern below is a demonstrated defect. No schematic, BOM, library, PCB or panel file was
> changed.

Repository HEAD when written: `4a7e0064ea2f73ce7780fadafed6cea07e74d0c7`. Reproduce (repo
root, numpy only; selftest < 1 s, full run ~70 s):

```sh
python3 -B modules/usb-power-45w/tools/capacitor-study/cap_study.py --selftest
python3 -B modules/usb-power-45w/tools/capacitor-study/cap_study.py --out <new-dir>
```

`generated/` holds the run used here (`results.json`, SVG charts). Datasheets and logs are
in the ignored `research/capacitor-study/`.

## Actual S6 values (native netlist, `circuit45.py`, `protection6.py`)

| Ref | Value / part | Net |
|---|---|---|
| C5 | 47u 50V SamYoung MVK, C165527, 6.3x7.7 can | VIN-GND, after U5 |
| C34 / C35 | 100u 35V MVK, C350012 | P12_RAW / P5_RAW - GND (before U6/U7) |
| C36 | 100u 35V MVK, C350012 | GND - N12_RAW (before LM5067/Q4) |
| C6 C7 C15 C16 C24 | 10u 50V X5R 1206 CL31A106KBHNNNE, C13585 | VIN-GND |
| C25 C26 (+C27 100n) | 10u 50V X5R 1206, C13585 | VIN-N12_RAW, ~32 V DC |
| C11-C14 / C20-C23 | 4 x 22u 25V X5R 1206 CL31A226KAHNNNE, C12891 | P12_RAW / P5_RAW |
| C29-C33 | 5 x 22u 25V X5R 1206, C12891 | N12_RAW |
| C38 C41 C45 | 1u 0603 | protected +12V/+5V/-12V |

U2 TPS62933F 12.194 V, 1.2 MHz, 6.8 uH; U3 4.985 V, ~1.98 MHz, 3.3 uH; U4 LMR38020F IBB
-11.989 V, ~790 kHz, 15 uH. No CFF on U2/U3.

## Known vs assumed

Known (datasheet/native): topology and values above; TPS62933F (SLUSEA4D) VFB 816 mV max
(-40..150 C), VIN abs max 32 V, min-COUT tables; LMR38020 (SNVSC40E) CIN >= 4.7 uF
effective, FB 1.015 V max; TPS16630 (SLVSET9G) OVPR 1.176 V min, dv/dt inrush; SMBJ22A Vc
35.5 V at rated Ipp; can listings 105 C / 1000 h, 120 Hz ripple 70 mA (C165527) / 52 mA
(C350012).

Assumed (not data for the fitted parts):
- MLCC DC-bias retention bands (`BIAS`): 22u/25V 0.55-0.80 at 5 V, 0.30-0.50 at 12 V;
  10u/50V 0.35-0.60 at 20 V, 0.20-0.40 at 32 V; low corner x0.9 tol x0.85 temp x0.93
  aging. Only anchor: TI quotes a TDK 1206 10u/50V X7R at 3.45 uF at 24 V.
- MLCC ESR 3-10 mohm, ESL 0.6-1.5 nH per part; route 0-3 nH; x2 sharing imbalance.
- Cans: C +-20 %, x0.85 cold, x0.85 EOL (low 0.578, high 1.2 of nominal, swept for C5 and
  C34-36); ESR 0.3/1.5/3.0 ohm (C34-36) and 0.5/2/4 ohm (C5) warm-low/warm-high/cold-high;
  ESL 5-15 nH; HF ripple multiplier 1.0-1.8 (SamYoung MVG proxy; MVK family 1.08 @ 100 kHz is inside
  this band but not confirmed for our variants, see addendum).
- Source: charger R/L with 0/10/100 uF bulk, cable 0.4-2 uH and 0.02-0.2 ohm, F1+D10
  0.02-0.06 ohm (D10 blocks reverse), U5 RON 19-53 mohm. C5 is never hit by an ideal 20 V
  step; inrush uses U5 dv/dt.
- Load: 72 W constant power at 17.2 V (-4.11 ohm), linearised; valid only below converter
  crossover.
- RAW release: imposed trajectory, converter current held N = 2/8/16 cycles then slewing at
  Vo/L, no sinking. N is an assumption, not TPS62933F/LMR38020F data.
- Ripple: ideal CCM waveforms, 80 harmonics; 2.5 A per buck (conservative), 1.143 A IBB.

| Bank (bounded effective) | uF lo-hi | Datasheet figure (basis as stated) |
|---|---|---|
| VIN ceramics x5 at 20 V | 12.5-33 | 10 uF + 0.1 uF per TPS62933 |
| P12_RAW 4 x 22u | 18.8-48.4 | 10 min / 15 typ (12 V row) |
| P5_RAW 4 x 22u | 34.4-77.4 | 10 min / 20 typ (5 V, 1.2 MHz row) |
| N12_RAW 5 x 22u | 23.5-60.5 | none for IBB; SNVSC40E Table 9-1 *buck* guide is RATED C (12 V/400 kHz 1x22u nom, 1x15u min; 12 V/1 MHz 2x10u nom, 1x10u min), not effective, not an IBB minimum |
| C25+C26 at 32 V | 2.85-8.8 | LMR38020 CIN >= 4.7 effective (separate requirement) |
| C34-36 / C5 cans | 57.8-120 / 27.2-56.4 | none required by TI |

## Results (assumed-model; `results.json` keys in brackets)

**VIN bus** [`vin_stability`, `rd_sweep`, `vin_transient`]: 1296 corners for A (C5 C low and
high swept), 216 per B option. No corner unstable.

| Option | Min zeta | Max abs(Zs) | Margin to 4.11 ohm |
|---|---:|---:|---:|
| A C5 can (worst: high C, cold ESR) | 0.074 | 1.62 ohm | 8.1 dB |
| B0 C5 removed | 0.025 | 2.68 ohm | 3.7 dB |
| 2 x 10u/50V, undamped | 0.046 | 1.97 ohm | 6.4 dB |
| 2 x 10u/50V + 1.0 ohm | 0.101 | 1.14 ohm | 11.1 dB |
| 4 x 10u/50V + 1.0 / 0.5 ohm | 0.101 | 0.84 / - ohm | 13.8 / 14.6 dB |

Damper 0.1 ohm: 7.4 dB (below A); 0.33-2 ohm: 9.3-11.1 dB. 20 -> 72 W step: VIN min
18.43-18.61 V; 72 -> 5 W release from 21 V: 21.26-21.47 V vs U5 OVP low 23.21 V. Inrush
0.26 A (A) / 0.10 A (B0).

**RAW release overshoot** [`raw_release`], imposed trajectory, ranges over corners:

| Rail | Static margin to OV low | N=2 | N=8 | N=16 |
|---|---:|---:|---:|---:|
| P12_RAW (A / B0 / +2x22u) | 1.177 V | <= 0.23 V | 0.25-0.73 / 0.31-0.78 / 0.21-0.53 V | up to 1.35 / 1.52 / 1.03 V |
| P5_RAW | 0.185 V (0.211 V TJ 0-85 C) | 0.04-0.09 / 0.04-0.09 / 0.03-0.06 V | 0.11-0.27 / 0.13-0.28 / 0.09-0.19 V | 0.20-0.51 / 0.24-0.53 / 0.16-0.36 V |
| N12_RAW | 1.856 V (nominal OV) | <= 0.09 V | <= 0.34 V | <= 0.67 V |

Passes at N=2; at N=8/16 several cases exceed the static budget. Outcome is set by the
imposed N, not predicted. Removing a can raises passive abs(Z) 1.9-2.75x at 10 kHz and
1.03-1.16x at 60-100 kHz; this does not show actual loop margin with or without cans.
IBB RHP zero 94-214 kHz [`ibb`].

**Switching-ripple split** [`ripple_*`, `can_ripple_screen`]. N12_RAW, C36 and C25/C26 come
from the coherent two-node U4 cell (`ripple_ibb_input`: both injections from one inductor
current). The single-node N12_RAW split in `ripple_outputs` is a diagnostic only and is not
added to it. C5 combines U2+U3 and U4 shares in quadrature (unsynchronised sources at
different frequencies).

| Branch, max over corners | A | B | Limit used |
|---|---:|---:|---|
| C34 / C35 | 4.5 / 3.1 mA | - | 52 mA x 1.0-1.8 |
| C36 (two-node; single-node diag. 23.6 mA) | 17.6 mA | - | 52 mA x 1.0-1.8 |
| C5 (29.7 bucks + 20.1 U4, quadrature) | 35.9 mA | - | 70 mA x 1.0-1.8 |
| 22u part on N12_RAW (x2 imbalance) | 0.29 A, 0.86 mW | 0.22 A, 0.46 mW | Samsung heating curve not obtained |
| 10u part on VIN (x2) | 0.64 A | 0.64 A | as above |
| Damper 1 ohm (bucks 24.5 + U4 10.5 mA) | - | 26.7 mA, 0.7 mW | pulse rating not verified |
| C25+C26 total | 0.38 A | 0.38 A | - |
| U4 input current closing via system GND | 0.73 A | 0.75 A | layout-dependent |

Can dissipation bound (max current x cold-high ESR, not a coincident corner): C5 5.1 mW,
C36 0.9 mW. Life heuristic 1000 h x 2^((105-T)/10) gives 16 kh at 65 C, 32 kh at 55 C; this
is a rule of thumb, not a SamYoung warranty, and can temperature was not modelled.

Ripple voltage is a synthesised band-limited waveform, not 2*sqrt(2)*RMS. With ideal current
edges the ESL term is an impulse, so ESL-inclusive Vpp depends on harmonic count; the
capacitive+ESR part converges. C25/C26: 0.058-0.062 V without ESL; 0.13-0.14 V with ESL at
80 harmonics (0.07 / 0.09 / 0.20 V at 80 / 160 / 320 at the check corner). U2 input: 0.047 V
without ESL, 0.27 V band-limited.

**Consistency check** [`ripple_checks`, also asserted in `--selftest`]: U4 injections give
mean output 1.143 A, input 0.797 / 0.569 A at 17.2 / 24.1 V, iL = in + out, power balance
13.704 / 13.703 W; nodal KCL residual < 1e-15 A; Parseval 99.7 / 99.9 % of time-domain AC
rms at 80 / 320 harmonics; C36 rms changes < 0.1 % from 80 to 320 harmonics.

## Concern classification [`screens`]

| Concern | Class | Pass condition |
|---|---|---|
| P5_RAW vs U7 OV (static 5.171 vs 5.356 V) | conditional, model-dependent | P5_RAW peak in 0 -> 2.2 A -> 0 steps (cold/hot, min/max VIN) < U7 trip, FLT never asserts |
| C25/C26 effective C | conditional (guessed bias band) | retention at 32 V >= 0.235 nominal, >= 0.33 with tol/temp/aging |
| C25/C26 voltage, 47.7 V only if VIN reached 35.5 V clamp | conditional (source surge + U5 dynamics unverified) | measured VIN-N12_RAW peak < 50 V in defined tests |
| VIN vs TPS62933F 32 V abs max | conditional, pre-existing, not capacitor-driven | measured VIN peak < 32 V in defined tests |
| Ceramic-only bank sufficiency | not established | Bode + load step per option kept |
| Can ripple/life | passes under assumptions | MVK HF ESR/multiplier data; can temperature |

## Options

- **A, retain cans (4HP):** feasible under the screens run; no schematic change. Gates:
  can HF ESR/ripple data, life at real temperature, two Extended codes. Panel lean.
- **B_min / B_full** (C5 -> 2 x C13585 + damper R; +2 x C12891 on P5_RAW only / on each
  RAW): candidates only. Higher parts cost on the quotes below; behaviour without cans not
  established; needs a new 0.33-2 ohm damper part whose pulse capability is unverified.
- **C, hybrid:** no evidence it beats A or B.

## Cost (parts only, USD, observed 2026-10-31 ~04:37 UTC, panel quotes, not re-verified)

C165527 $0.1267, C350012 $0.1173, C13585 $0.2115, C12891 $0.1180 (likely 5-piece step).
Excluded: damper R, Extended fees, setup, attrition, placement, MOQ remainder.

| Option | Added | Removed | Net/board |
|---|---:|---:|---:|
| A | $0 | $0 | $0 (cans $0.4786) |
| B_full | $1.1310 | $0.4786 | +$0.6524 + R |
| B_min | $0.6590 | $0.4786 | +$0.1804 + R |
| B_bare | $0.4230 | $0.4786 | -$0.0556 + R |

B removes two Extended codes, so it wins only for batches below 2 x fee / net delta;
with a hypothetical $1-3 fee: B_full 3-9 boards, B_min 11-33. No cost claim without quotes.

## Gates

**Before prototype layout (data/choice):** Samsung bias/aging curves for C13585 and C12891
at 5/12/20/32 V; exact-variant MVK 100 kHz ESR and ripple multiplier; TPS62933F max COUT; option choice
(A or a B variant) and, for B, a damper part with pulse data; Extended fee and damper
quotes; the surge/hot-plug test definition (source spec); U7 OV threshold decision;
mated-header height (mechanics, separate task).

**After fabrication (bench qualification, not a precondition for a prototype layout):**
Bode U2/U3/U4 (cold/hot, min/max load, with/without rack, each option built); load
step/release with U6/U7/LM5067 OV/FLT monitored; VIN step/release on 1-2 m 5 A cables
with several chargers; U4 input ripple, C25/C26 and can temperature; surge/hot-plug at
VPD/VIN; 0 C cold start; measured MLCC effective C.

## Sources

- TPS62933F SLUSEA4D: https://www.ti.com/lit/ds/symlink/tps62933f.pdf
- LMR38020 SNVSC40E: https://www.ti.com/lit/ds/symlink/lmr38020.pdf
- TPS1663 SLVSET9G: https://www.ti.com/lit/ds/symlink/tps1663.pdf
- SLUAAF1 (TPS62933 thermal, no max-COUT limit): https://www.ti.com/lit/an/sluaaf1/sluaaf1.pdf
- Samsung product pages (spec PDFs show a generic bias example only):
  https://product.samsungsem.com/mlcc/CL31A106KBHNNNE.do, .../CL31A226KAHNNNE.do
- Can listings (not a SamYoung datasheet): https://www.lcsc.com/product-detail/C165527.html,
  https://www.lcsc.com/product-detail/C350012.html
- Downloads (ignored) in `research/capacitor-study/dl/`; SHA-256 prefixes 16ec2eac43c7374e
  (SLUSEA4D), da2ed000a8525ec9 (SNVSC40E), 8f91a0db2daf2da3 (SLVSET9G).
- SamYoung MVK family datasheet: https://www.samyoung.co.kr/download/miniature/BDS(MVK).pdf

## Panel decision and source addendum (2026-10-31, archival)

**Opinions.** Opus (this study): B_min/B_full are conditional ceramic candidates only.
DeepSeek (cost/4HP geometry), Meta (electrical alternatives) and Astra Max: lean retain A.
**Supervisor: retain A** (mixed cans + existing ceramics) as the first 4HP prototype
direction, because B has no validated bank count and no demonstrated all-in saving, and 4HP
avoids a forced cap substitution. Conditional on exact-can data/sourcing and a populated fit
check. Not proof the baseline is qualified; not design, route, ordering or manufacturing
approval.

**Sourcing observation, 2026-10-31.** Original four cans consumed $0.4786/board; at the
5-piece minimum per code, 1-board cash is 5 x $0.1267 + 5 x $0.1173 = $1.22, before
attrition, Extended fees, setup and placement.

**Source clarifications.**
- LMR38020 SNVSC40E Table 9-1 columns are NOMINAL COUT / MINIMUM COUT, both *rated*
  capacitance, for the buck topology. They are not effective values and not an IBB minimum
  (`results.json` key renamed `datasheet_cap_figures_uF`). CIN >= 4.7 uF effective is a
  separate requirement.
- SamYoung BDS(MVK).pdf gives a 1.08 @ 100 kHz family ripple multiplier, but its table does
  not identify our 6.3x8 47u50V / 100u35V variants. Applicable as family context only; the
  model keeps the 1.0-1.8 proxy and exact-variant ESR/ripple stays a gate.
- Vendor models: TI TPS62933F model https://www.ti.com/lit/zip/SLUM859 exists, but no vendor
  closed-loop run was performed here. LMR38020F model https://www.ti.com/lit/zip/SNVMC78
  states grounds are tied to 0 internally and inverting topologies are not supported, so it
  cannot represent U4's IBB. Hence all results here are passive/analytical with imposed
  converter behaviour, not vendor-model simulations.
