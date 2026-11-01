# usb-power-45w S8.4: +5 V series disconnect, review fixes, P1.4 fit placement

> **Development review, not a manufacturing release.** S8.4 applies the fixes from the three
> independent S8.3 reviews (C1, C2, M1–M9, changelog below) to the S8.3 design: **U23 TPS259470ARPWR**
> +5 V series disconnect, **U18/U20 on always-on VPD**. 190 references / 84 circuit nets, seven
> schematic pages; 100.5 × 48 mm four-layer board, 50 mm deep, all components on F. The board is
> **unrouted**. A conservative prototype rating is now published (**+12 V 2.5 A, +5 V 2.0 A, −12 V 0.9 A,
> ≤ 45 W delivered**); it is derived from datasheet minimum limits, not measured. A safe +5 V fault
> peak is **not** established. Original S7/R3 two-board hardware is unchanged.

S8.3 authorized: remove the crowbar and related circuitry, choose a less expensive, well-stocked
JLCPCB part, and fix U20's input-range issue. This does **not** restore the original three-rail
protection architecture: only +5 V has an output disconnect. MAIN remains the only LED.

## S8.4 changelog (2026-11-02, from the three S8.3 reviews)

| Item | Issue | Change | Files |
| --- | --- | --- | --- |
| **C1** | U23 `FLT` wire-ANDed onto `P5_OK`: reverse-current blocking (hot plug into a live +5 V bus, load release held downstream), overload or over-temperature latched every rail off | U23.4 off `P5_OK`: new net `P5_FLT_N` with its own pull-up **R108** 10k and test pad **TP21**, diagnostic only. `P5_OK` = U23 AUXOFF + U18, unchanged. Fault matrix below | `tools/circuit_s8.py`, `hierarchy_s8.py`, `verify_s8.py`, `test_s8.py`, schematic page 06, PCB |
| **C2** | The <6 V header peak is not guaranteed | Kept, stated plainly: the 3 µs case reaches **6.33 V and stays above 6 V for ~193 µs**; a **30 V / 1 Ω / 3 µs** stress case (6.52 V) was added. Neither D10 nor a bench-supply ceiling bounds the header | `tools/s8_calcs.py`, `calcs.json`, `validation.json`, this page |
| **M1** | Startup masking: `TIMER_GO = RUN AND V20_OK` while U2/U3 enable from `MAIN_OK`; a start between U5 turn-on and `V20_OK` never armed the latch | **`TIMER_GO = RUN AND MAIN_OK`** (U13 pin 10), the converter-enable net. R83 220k → **200k** re-centres `V20_OK` to 14.6–17.7 V, below the 18.25 V minimum loaded PD input | `circuit_s8.py`, `verify_s8.py`, `test_s8.py`, `s8_calcs.py` (`startup_window`), page 05/06 |
| **M2** | Load release could reach the OVLO and latch | **R11/R12 0.1 % / 25 ppm** (setpoint 4.856–5.114 V). `calcs.json` → `ovlo_release` (imposed-current model): a release from U23's highest current limit stays **0.109 V below the OVLO minimum** and 0.201 V below the U20 guard. OVLO **falling** threshold computed (5.079–5.336 V); the −35 mV reconnect corner stays open (fail-safe latch) | `circuit_s8.py`, `s8_calcs.py`, `verify_s8.py`, `test_s8.py` |
| **M3** | U20 on VPD after V3V3 collapses; stale "U20 unpowered" rationale | `calcs.json` → `v3v3_loss`: U20 may stay powered, but nothing can be enabled (R64 holds RUN low); node current ≤ 0.15 mA. D22 is **not** a guaranteed cold clamp. Rationale corrected | `s8_calcs.py`, `circuit_s8.py` (U20/D22 notes), `hierarchy_s8.py`, this page |
| **M4** | Protection loops: U23 IN→cap 6.6 mm, OUT→D23 22.7 mm, IN→D21 16.4 mm, U20 VCC→C65 7.4 mm | Local-loop contract `LOCAL_LOOPS` in `check_s8_board.py`, recorded in `board-p1.json`. U23 cell re-placed (P1.4): **3.0 / 3.0 / 5.75 / 5.78 mm, C65 2.3 mm**; every row passes | `check_s8_board.py`, `place_s8.py`, PCB, `board-p1.json`, `placement.json` |
| **M5** | No published continuous rating | **2.5 / 2.0 / 0.9 A**, ≤ 45 W delivered, for VPD ≥ 18.25 V (converter input ≥ 17.25 V after D10 + U5): 75 % of the minimum capability there, to the nearest 0.1 A (+5 V = 75.6 % of U23's minimum limit, 0.65 A headroom, ITIMER open) | `s8_calcs.py` (`rating`), `hierarchy_s8.py`, this page |
| **M6** | −12 V start-up allowance (0.40 mF) below the typical rack (0.44 mF) | Recomputed with the LMR38020 hiccup rule (hiccup only below 40 % after the blanking): model **1.08 mF** at the 15.23 V converter input of the U5 turn-on minimum, 1 A, half the typical blanking; **published allowance 0.846 mF**, capped by TI's ~1000 µF total-output-capacitance guidance. Covers the typical rack with 0.41 mF; acceptance test added | `s8_calcs.py` (`minus12_startup`), `test_s8.py` |
| **M7** | 0.1 mm solder-mask webs on U23 (an IN/OUT bridge silently bypasses the eFuse) | Copper-pad mask expansion 0.05 → **0.025 mm**: every web **0.15 mm**. TP18-to-+5 V no-short bring-up check in notes, validation and here | `s83_parts.py`, footprint, `place_s8.py` (pad refresh), PCB, `circuit_s8.py` (TP18 note), `verify_s8.py` |
| **M8** | Basic-only passive policy unresolved | **Decided:** Extended accepted for the ten 0.1 % dividers only; with 1 % Basic parts four screens fail (`basic_only_counterfactual`) | `s8_sourcing.py`, `sourcing.json`, `s84-sourcing.json`, `s83-sourcing.json` (pointer), `s8_calcs.py` |
| **M9** | Strain relief overshoots the panel by 0.4 mm; IDC envelope margin only 1.1 mm | Both recorded as explicit risks in `mechanical.json` → `risks` | `mechanics_s8.py`, `mechanical.json` |

Revision: schematic **S8.4**, board **S8.4-P1.4**. `review-s84.json` replaces `review-s83.json`
(the S8.3 record stays in git history, commit `a12edd3`).

## Open / review

| Item | File |
| --- | --- |
| Native project | [hardware/single/usb-power-45w-single.kicad_pro](../hardware/single/usb-power-45w-single.kicad_pro) |
| Schematic, overview + six pages | [PDF](usb-power-45w-single-schematic.pdf) |
| Native schematic BOM | [s8-single/bom.csv](s8-single/bom.csv), test pads excluded; D8/J2/J3 manual |
| Calculations | [calcs.json](s8-single/calcs.json) |
| Independent native pin/field/NC verification | [validation.json](s8-single/validation.json) |
| Final native checks, tests and source/artifact hashes | [review-s84.json](s8-single/review-s84.json) |
| Whole-design dated sourcing estimate + Basic-only decision | [sourcing.json](s8-single/sourcing.json) |
| Live selected/changed-part evidence | [s84-sourcing.json](s8-single/s84-sourcing.json) (S8.4), [s83-sourcing.json](s8-single/s83-sourcing.json) (S8.3) |
| Placement / mechanical contract | [board-p1.json](s8-single/board-p1.json), [placement.json](s8-single/placement.json), [mechanical.json](s8-single/mechanical.json) |
| Placement drawing | [PDF](s8-single/assembly/usb-power-45w-single-placement.pdf) |
| 3D assembly | [STEP ZIP](s8-single/assembly/usb-power-45w-single-assembly.step.zip), [collision report](s8-single/assembly/assembly-report.json) |
| Unchanged panel | [S8 panel](../panels/front-pcb/usb-power-45w-single-panel.kicad_pcb) |

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

### Fault matrix (S8.4)

`P5_OK` is the wire-AND of U23 **AUXOFF** (pin 3) and the U18 delivered-+5 V comparator, pulled up by
R44. U23 **FLT** (pin 4) only drives `P5_FLT_N` (R108 pull-up, TP21). TI's tables:
AUXOFF is low only for input UVP/UVLO, reverse polarity, OVLO and inrush, and stays high for every
load-side event (Table 7-4). FLT is low for over-temperature, persistent current limit, ILM pin
faults and reverse current (Table 7-3); it does **not** report OVLO. [source](https://www.ti.com/lit/ds/symlink/tps25947.pdf)

| Event | U23 response | AUXOFF | FLT (TP21) | U18 (+5 V delivered) | `P5_OK` | Common latch after ARMED |
| --- | --- | --- | --- | --- | --- | --- |
| Normal operation | on | H | H | good | H | — |
| Start-up inrush | dVdt ramp | L until done | H | low until > 4.22 V | L | masked by the startup window |
| Hot plug into a live +5 V bus / load release held downstream (reverse current) | reverse blocking | H | **L** | good (bus is up) | **H** | **no latch (S8.3: latched)** |
| Transient overload above ILIM | current limit | H | L while limiting | good unless +5 V sags below 4.22 V | H, or L if it sags | only if +5 V sags > ~1 ms |
| Persistent overload / short | (fast trip,) current limit, then TSD + auto-retry | H | L after the ITIMER interval | **bad** | L | **latched** (via U18) |
| Over-temperature | shutdown, auto-retry | H | L | **bad** | L | **latched** (via U18) |
| P5_RAW above OVLO (5.585–5.848 V) | off, auto-recover below 5.079–5.336 V | **L** | H | bad | L | latched if > ~1 ms; brief pulses or pre-ARMED events can recover |
| P5_RAW above the U20 +5 V guard (5.677–5.976 V) | off if the OVLO also tripped (bands overlap) | L if OVLO | H | — | — | **FAULT preset at once, also before ARMED** (U5 off) |
| U23 unpowered (P5_RAW 0 V) | off | no active pull-down | H (R108, not driven) | **bad** | L (U18 holds it) | latched / not started |

The last row is the dependency DeepSeek noted (TPS25947 §7.3.10): AUXOFF has no active pull-down
without input power, so `P5_OK` relies on U18's comparator in that state.

Do not wire AUXOFF directly to `OV_N`: it is normally low during startup and would prevent startup.
Do not put the buck feedback downstream: a disconnected output must not make the buck demand more voltage.

## Startup sequence and arming (M1)

```text
USB-C attach -> CH224A requests 20 V -> VPD -> U9 V3V3 -> U10 RESET_N low >= 12 ms (clears ARMED, FAULT)
RESET_N high -> RUN = RESET_N AND NOT_FAULT -> U5 SHDN released, U23 EN = RUN
VPD > U5 UVLO (16.23-18.23 V) -> U5 ramp ~12 ms -> PGOOD 8-13 ms -> MAIN_OK -> U2/U3 enabled (U4 via Q1)
TIMER_GO = RUN AND MAIN_OK -> U11 -> ARMED after 0.31-0.88 s (rails up within ~141 ms)
ARMED: any bad status (MAIN_LED_OK = MAIN_OK AND V20_OK, P12_OK, P5_OK, N12_OK) > ~1 ms -> FAULT -> all OFF
OV_N (U20) presets FAULT at any time, also before ARMED
```

The qualification window now starts from the same net that enables the converters, so ARMED cannot
stay masked while they run. `V20_OK` only qualifies `MAIN_LED_OK` (the MAIN LED and `ANY_BAD`).
R83 200k puts `V20_OK` at **16.12 V nominal, 14.62–17.73 V** over V3V3, resistor, offset and bias corners
(S8.3's 220k: 17.65 V nominal, up to ~19.4 V), below the 18.25 V assumed minimum loaded 20 V PD input
(19 V minus a 0.75 V cable allowance). U5's own turn-on maximum (18.23 V, leakage now referred through
R2) sits only 20 mV below that 18.25 V minimum, an unchanged S7 margin to watch on the bench. A marginal
input between U5 turn-on and `V20_OK` therefore runs the
converters, arms, and then **latches off** (fail-safe) instead of running unqualified. If `MAIN_OK` itself
chatters faster than the window, U5 cycles the converters off each time and the timer restarts; that
behavior at a sagging source is a bench test. `verify_s8.py` checks `TIMER_GO = RUN AND MAIN_OK` in
all 512 settled combinations; `test_s8.py` rejects a netlist with U13 pin 10 back on `V20_OK`.

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

Whole-design sourced-parts estimate: **$21.96** (S8.3 $21.88, S7 $27.12). New S8.4 codes: R11
**C705793** RT0603BRD0768KL ($0.035, 23,453 stock) and R12 **C861121** RT0603BRD0713KL ($0.0394,
24,301), both Extended and Economic eligible; R83 **C25811** 200k Basic; R108 reuses the Basic 10k
C25804. This total mixes reused dated rows with live S8.4 rows; it is **not an all-parts fresh quotation**.

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

| Setting | S8.4 result / scope |
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
- **Replug into a rack that holds −12 V:** the −12 V channel reads OV until REF_OV exceeds 1.09–1.15 V,
  8.2–10.7 ms after V3V3, against the ≥ 12 ms minimum RESET release: ~1 ms margin, a screen only.

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

## P1.4 fit placement, mask webs and mechanics

![S8.4 P1.4 fit placement](s8-single/img/board-p1.png)

The PCB is a **fit draft**, not a final power-loop layout. It keeps the mechanical anchors, outline,
stackup, rules and retained footprint UUIDs/models. P1.4 moves 24 retained parts and adds R108/TP21
(`placement.json`).

**Local-loop contract (M4):** `tools/check_s8_board.py` `LOCAL_LOOPS` measures the pad-centre
straight-line distance from each listed IC pin to the nearest pad of its bypass capacitor or clamp
on the same net, and fails the placement check above the limit (`board-p1.json` → `local_loops`):

| Loop | Limit | P1.3 | P1.4 |
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

Placement screens: all 190 parts on F, no parked parts, no courtyard overlaps, 1 mm edge rule holds
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

![S8.4 assembly](s8-single/assembly/iso-front.png)

## Reproducibility and verification

Generators remain derived from the untouched S7 circuit. The shared toolkit performs native checks;
its flat edit primitives cannot add the new parts or synchronize nets, so the S8 generator and
bounded `place_s8.sync_candidate()` perform those operations on a **separate candidate**, which is
checked and then copied into the module. The sync refuses routed boards, preserves retained
UUIDs/models, verifies the source placement against its recorded baseline, and (S8.4) copies only the
U23 copper-pad mask expansion from the pinned footprint. No rule/severity/exclusion is relaxed.

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
  --out modules/usb-power-45w/docs/s8-single/review-s84.json
```

The BOM is the native `kicad-cli sch export bom` with fields Reference/Value/Footprint/QUANTITY/LCSC/
MPN/Manufacturer grouped by Value, Footprint, LCSC, MPN and Manufacturer. For candidate tests, set
`S8_DESIGN_ROOT` to that candidate module root; mechanical generation accepts the same variable and
`S8_ASM_WORK`.

**S8.4 results** (`review-s84.json`): native ERC **0**; DRC **0 violations, 0 warnings, 0 exclusions,
schematic parity 0, 429 unconnected** (routing opens; S8.3 427: +2 on the new `P5_FLT_N` net, +1 for
R108 on V3V3, −1 on `P5_OK`); exact native ref/pin/net parity **equal**; **190 refs / 84 nets** (118
including NC pins, 34 NC pins); BOM 64 lines / **171 refs + 19 test pads = 190** (exact parity, field
match); `verify_s8.py` passes 512 settled latch combinations; the module suite passes (see
`review-s84.json` → `tests`). Tests include the C1 and M1 regressions (U23.4 on `P5_OK`, U13 pin 10
on `V20_OK`, FLT on any latch input), wrong pin roles, reversed/bypassed eFuse connections,
wrong-side feedback/capacitors/TVS, accidental 3.3 V comparator supply, reference/clamp errors, latch
behavior, the M2/M5/M6 calculation acceptances, the M4 loop contract, the M7 mask webs, the M9 risks
and the review-record hashes.

**Release gates remain open:** routing and routed loop areas, regulator stability, measured
capacitor behavior, fault-voltage and restart tests (<6 V is not established), startup/foldback/
thermal tests including −12 V into the real rack, the published rating's measurement, connector/cable
current and fit, VPD ringing / cold clamp / replug, fabrication/CAM and manual assembly preview. No
fabrication files, vendor upload or order are part of this change.
