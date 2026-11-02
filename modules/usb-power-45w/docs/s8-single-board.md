# usb-power-45w S8.5: one-shot arming on the S8.4 +5 V series disconnect, P1.5 fit placement

> **Development review, not a manufacturing release.** S8.5 fixes the arming blocker that all three
> S8.4 reviews raised (item **B**: one-shot `STARTED` latch, `TIMER_GO = RUN AND STARTED`, `V20_OK`
> moved to a status-validity floor) and the remaining minor items (**C**), changelog below. The S8.4
> design is otherwise **unchanged**: **U23 TPS259470ARPWR** +5 V series disconnect (R108/TP21 `P5_FLT_N`,
> OVLO R107/R101/R102, ILM R103/R104, dVdt C68), **U18/U20 on always-on VPD**, the published rating and
> every other S8.4 decision. 191 references / 85 circuit nets, seven schematic pages; 100.5 × 48 mm
> four-layer board, 50 mm deep, all components on F. The board is **unrouted**. A conservative prototype
> rating is published (**+12 V 2.5 A, +5 V 2.0 A, −12 V 0.9 A, ≤ 45 W delivered**); it is derived from
> datasheet minimum limits, not measured. A safe +5 V fault peak is **not** established. Original S7/R3
> two-board hardware is unchanged.

S8.3 authorized: remove the crowbar and related circuitry, choose a less expensive, well-stocked
JLCPCB part, and fix U20's input-range issue. This does **not** restore the original three-rail
protection architecture: only +5 V has an output disconnect. MAIN remains the only LED.

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

## Open / review

| Item | File |
| --- | --- |
| Native project | [hardware/single/usb-power-45w-single.kicad_pro](../hardware/single/usb-power-45w-single.kicad_pro) |
| Schematic, overview + six pages | [PDF](usb-power-45w-single-schematic.pdf) |
| Native schematic BOM | [s8-single/bom.csv](s8-single/bom.csv), test pads excluded; D8/J2/J3 manual |
| Calculations | [calcs.json](s8-single/calcs.json) |
| Independent native pin/field/NC verification | [validation.json](s8-single/validation.json) |
| Final native checks, tests and source/artifact hashes | [review-s85.json](s8-single/review-s85.json) |
| Whole-design dated sourcing estimate + Basic-only decision | [sourcing.json](s8-single/sourcing.json) |
| Live selected/changed-part evidence | [s84-sourcing.json](s8-single/s84-sourcing.json) (S8.4; S8.5 adds no new code), [s83-sourcing.json](s8-single/s83-sourcing.json) (S8.3) |
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

![S8.5 P1.5 fit placement](s8-single/img/board-p1.png)

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

![S8.5 assembly](s8-single/assembly/iso-front.png)

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
