# SR2 schematic — independent DeepSeek review

**Status: CONDITIONAL PROTOTYPE GO on the schematic (delta-reviewed at `56ffdfcc`). HOLD on PCB
until the user gives an explicit ACK.**
Notes only. No circuit, generator, test, PCB, BOM or library edit was made in this review; the
candidate was staged read-only as `git cherry-pick --no-commit 6219eddc`.

## Scope and provenance checked

| Item | Result |
|---|---|
| Round 1 input | `6219eddcb0564f3d4e32e45aaaecf92a3316cbd7`, cherry-picked `--no-commit` into this isolated workspace |
| Round 2 delta input | `56ffdfcc699484aaed3a943f2e606517eb7bdb53` applied on top as `git diff 6219edd 56ffdfc -- modules/usb-power` + `git apply --index` (16 files), own notes preserved |
| Tree equality to 56ff | `git diff 56ffdfc -- modules/usb-power` shows **only this review note** — the electrical/audit/BOM/tool inputs are byte-identical to `56ffdfcc` |
| PCB in the delta | none — the 16 patched paths contain no PCB/pro/rules/panel file |
| Candidate file hashes | all **27/27** `candidate_sha256` entries in `docs/sr2-schematic-receipt.json` re-hashed: **0 mismatch** |
| Drift vs `6219eddc` | `git diff` over `hardware/`, `tools/`, `BOM.csv`, `docs/`: **empty** — the reviewed tree is the candidate tree |
| Electrical files inspected directly | `04_bipolar.kicad_sch`, `05_quiet_rails.kicad_sch`, `usb-power.kicad_sch`, `docs/pin-net-audit.json`, `sr2-native-erc.json`, `sr2-schematic-budget.json`, `sr2-component-audit.json`, `tools/sr2_design.py` |
| Not re-run by me | the 47 focused tests, the hash/protected-file checker, KiCad ERC/DRC, any PCB/CAM step. The ERC **report file** was read (0 violations on all 8 sheets, `ignored_checks: []`, `included_severities` includes `exclusion`) — that is evidence the candidate's ERC is clean, not proof that I reproduced it |
| Not done | no routing, no PCB/parity claim, no order, no vendor lookup, no other worktree, no commit/merge/push |

## Verdict

The SR2 topology, values and pin maps are **electrically correct as drawn**. I found no wiring,
pin, polarity, reference or NC defect, and the switched-node arithmetic reproduces independently.
**Verdict after the `56ffdfcc` delta: CONDITIONAL PROTOTYPE GO on the schematic.**
Every finding I raised against `6219eddc` is closed in `56ffdfcc`, and I re-checked the two
electrical change items from the artefacts rather than from the write-up: **D30 is fitted
(`dnp no`, in BOM, Basic C8678) and points the right way** — symbol pin 1 is named `K` and sits on
system GND, pin 2 named `A` sits on NRAW, so it conducts NRAW→GND and shunts a positive NRAW
excursion; **C93 is `dnp yes`** with value `DNP CFF / TBD` and connects system GND → NINV_FB, i.e.
across the **entire** R9+R15+R84 upper divider. Neither adds a new normal or hard limit. The
remaining open items are bench qualifications and the deliberately-unsynchronised PCB, not
schematic corrections.

## Findings

### F1 — MITIGATED IN 56ff (residual measured gate): positive NRAW kick vs TPS7A3301 limits
- **What happens.** C89–C92 + C7 (VPROT→NRAW) are charged when the eFuse output ramps. Before U3
  switches, NRAW is held only by the NRAW→system-GND bank, so the span caps form a capacitive
  divider and push NRAW **positive** by `9.45 V × C_span/(C_span + C_bank)`.
- **Evidence it is not covered.** TPS7A33 absolute maximum ratings (TI SBVS169C, p.2): **IN to GND
  −36 V / +0.3 V**, **OUT to GND −33 V / +0.3 V**, **FB to GND −2 V / +0.3 V**
  [source](https://strawberry-linux.com/pub/tps7a3301.pdf). The candidate's own budget already
  reports `positive_NRAW_charge_sharing_no_switch_upper_sensitivity_V = 0.5447` against
  `positive_NRAW_limit_V = 0.3`, and `off_is_disconnect = false`. So the exposure is admitted, and
  the only stated mitigation ("retained eFuse dVdt/active startup") is **not a clamp** — a
  capacitive divider ratio is independent of ramp rate, and slower dVdt lengthens the exposure.
- **What the numbers do and do not say.** The candidate's own no-switch charge-sharing screen is
  already **0.5447 V against a 0.3 V limit** — that is enough to establish a *potential* excursion
  above the absolute maximum. It is **not** a prediction of the real startup waveform. I explicitly
  do **not** transplant the 15 V DC-bias/aging derating factors into a 0 V-start transient: at t=0
  the NRAW bank sits at ~0 V bias, so those factors do not describe its starting capacitance, and a
  derated-capacitance recomputation would not be an honest "actual" value. Whether a real start
  crosses +0.3 V is therefore **unproven** and requires measurement.
- **Bound.** The TPS54302 low-side body diode should clamp NRAW at roughly +0.6…0.7 V in the worst
  case, so the excursion is probably bounded and non-destructive in a lab start — but it is still
  outside the LDO's +0.3 V absolute maximum, which the LDO sees on IN and (scaled) toward OUT/FB.
- **Recommended direction (not applied; no part selected).** A clamp **anode = NRAW, cathode = system
  GND** is the obvious mitigation and is reverse-biased in normal operation — but **a generic
  Schottky does not guarantee < +0.3 V**. Vf must be bounded at the actual clamp current *and over
  the temperature extremes*, so any part must be chosen on **max-Vf / forward-current / temperature**
  data. I make **no claim** that a Basic 0603/0805 Schottky is available or adequate; that requires
  exact part data this review did not gather. The alternative to evaluate against it is a deliberate
  reduction/redistribution of span capacitance (which trades directly against F2). Either way,
  **measure NRAW at a cold start** with the real eFuse ramp before closing the item.

### F2 — CLOSED as disclosure in 56ff (remains an analysis item): VIN–GND bypass vs TI's typical 10 uF
The only capacitance across VIN3–GND1 is 8.8 µF nominal, which the candidate itself screens to
**3.01 µF effective**. C5/C68 (44 µF) are VPROT→system GND and therefore input-to-output, **not**
VIN bypass. TI's TPS54302 **typical application** uses **10 µF on VIN** — that is a typical value,
**not an established minimum**, and I have not sourced it as one, so this is **not a hard fail**.
It is a needs-analysis item: either justify 3 µF effective against ripple/loop data, or raise the
span bank (after F1 is resolved, since more span C worsens F1). Note the same caps carry the ~0.5 A
RMS input ripple, which 4×1206 X7R handle comfortably — the open question is capacitance, not RMS.

### F3 — CLOSED in 56ff: planning allocation and nominal eFuse limit are now separate flags
- `rated_output_current` is **null** in `sr2-schematic-budget.json`. That is acceptable *before*
  bench work — a **conditional design objective** is the right form here, and I do not ask for a
  declared or measured "rating".
- Of the five `power.rows`, **two fail** `allocation_1p85A_pass`:
  +12/400 mA & −12/400 mA & +5/250 mA adverse → **2.0156 A** (above both the 1.85 A planning
  allocation **and** the 1.9868 A nominal eFuse ILIM); +12/600 & −12/200 adverse → **1.9644 A**
  (above the 1.85 A planning allocation, **below** the 1.9868 A nominal ILIM). Only the first row
  cannot be sustained at all.
- `sr2-schematic.md` quotes only the 400/300/250 row (1.4684 A nominal / 1.7693 A adverse) and says
  "below 1.85 A allocation", which reads as if all rows pass.
- This is probably **not** a design failure — `Code.md` says "no simultaneous 800 mA" guarantee,
  and both failing rows are 800 mA simultaneous. But the handoff must say so: **state the
  conditional design objective and that simultaneous 800 mA is outside contract and fails the
  planning allocation.**
- Related margin to state: the adverse 1.7693 A draw leaves only **4.6 %** to the 1.85 A allocation,
  and eFuse ILIM tolerance is not inside that allocation. If TPS26600 ILIM can come in low by
  >4.6 %, the adverse case current-limits. State the ILIM tolerance band, not the nominal.

### F4 — CLOSED in 56ff: the screen is now NOT_QUALIFIED, not a mixed-corner "pass"
`negative_loop.crossover_RHP5_screen = true` compares the global max crossover (8126 Hz) against
`min_RHP_Hz = 55.0 kHz` (→ 11.0 kHz limit, passes). The same object separately discloses
`efficiency_adverse_RHP_Hz = 37.87 kHz`, whose RHP/5 limit is **7.57 kHz — below the 8.13 kHz max
crossover**. I do **not** assert that those two unpaired extremes occur at the same corner; the
defect is that a global max is screened against a global min, so the "pass" is not a per-corner
statement. Recompute per corner and report the worst *paired* ratio (and say so if no corner
pairs them). Keep the phase-margin result as "not qualified" (18.4° model low end). A
feed-forward capacitor across R9 is the cheap contingency if measured phase is short — the
candidate correctly does not claim one today.

### F5 — CLOSED in 56ff: counts restated and now unambiguous
- `sr2-schematic.md` ("114 electrical references, 340 component pins including 39 NCs, plus 6 source
  flags") is self-consistent with `tests/test_sr2_schematic.py` L26, which asserts
  `(parts, pins_including_NC, hierarchical_ports) == (114, 346, 23)` — 340 real component pins + 6
  source flags = the 346 total.
- The checkpoint shorthand "346 pins / 23 NC" conflates two different numbers. **23 is the
  hierarchical port count**, not an NC count.
- **Correction to my own earlier figure:** the "20 explicit `(no_connect` markers" was a *line*
  count, not an occurrence count — `05_quiet_rails.kicad_sch` is minified onto one line and holds 20
  of them on that line. Recounted with `str.count('(no_connect')`: 9+5+1+0+20+0+4 = **39**, exactly
  the audit's 39 net-less pins. Every net-less pin does carry a marker; nothing is missing.
- Nothing electrical is wrong. Suggested restatement: 114 refs + 6 flags = 120 symbols, 346 pins,
  39 unconnected pins (each with a `(no_connect` marker), 23 hierarchical ports.

## Independently reproduced / verified good

- **U3 pin map is right.** 1 GND→NRAW, 2 SW→NINV_SW, 3 VIN→VPROT, 4 FB→NINV_FB, 5 EN→NINV_EN,
  6 BOOT→NINV_BOOT matches the TPS54302DDCR pinout; GND on the negative rail, L1 from SW to system
  GND, C35 BOOT→SW, no invented PG pin. `04_bipolar` carries **no** no-connect markers, i.e. no
  quietly dropped pin.
- **Feedback arithmetic checks.** 0.596 V × (1 + 226.2k/10k) = **14.08 V** vs the stated −14.0775 V;
  divider current 59.6 µA, above the ≥5 µA the TPS7A33 datasheet requires for no-load stability
  [source](https://strawberry-linux.com/pub/tps7a3301.pdf).
- **Switch screen reproduces by hand.** ΔIL = Vin·D/(L·f) = 7.9375 × 0.6963 / (17.6 µH × 272.6 kHz)
  = **1.152 A** = the reported 1.15195 A; peak 1.587 A, valley 0.435 A, RMS 1.064 A. Fault screen
  6 A + 1 A overshoot = 7 A against 10 A table Isat.
- **Negative LDO wiring is complete.** U13 IN = pins 13/15/16 all NRAW, OUT = 1/20 both N12,
  FB = 3, NR/SS = 14, EP 21 = GND. All three IN pins tied — a common IBB/negative-LDO miss.
- **No accidental NC on any power part**; the 39 net-less pins are NC-type pins on U1/U2/U13/J1 etc.
- **NRAW really crosses sheets**: hierarchical labels on `04_bipolar` and `05_quiet_rails` plus the
  root sheet, with ERC 0 and no exclusions ignored.
- **Removals are clean**: U4/L2/L3/D2/D3 and the compensation/BI_EN/VREF parts are gone, R15 is
  reused rather than orphaned, and the 7 new refs (U3, L1, C35, C89–C92) are matched by the 7
  surviving-sheet deltas the receipt describes.
- **Part-code claims are internally consistent** and the classification is honest: precision
  R9/R10/R15 (RT0603BRD07…) are labelled **Extended**, not Basic, and L1 is the only new Extended
  type vs SR1. C50254 = CL31B225KBHNNNE (2.2 µF/50 V X7R 1206), C12891 = CL31A226KAHNNNE,
  C14663 = CC0603KRX7R9BB104, C311983 = TPS54302DDCR, C1848803 = SRP1245A-220M.
  **Live JLC stock/eligibility was not re-queried and must not be claimed from this review.**

## Accepted gates (disclosed, not waived, not passes)

1. Loaded/cold start into 264 µF: 4.941 A constant-C screen above the 4 A HS minimum; eFuse retry
   interaction unmeasured.
2. Residual EN (2.804 V sensitivity) and L1/SW/high-side-body-diode backfeed into VPROT on unplug;
   SW1 disables the eFuse, not U3. No output disconnect.
3. 28 V span allocation: 27.671 V allocated, **0.329 V** to the 28 V recommended VIN/SW maximum,
   with all three transient allocations unmeasured; 30 V is the absolute maximum.
4. Loop/phase/DCM: 18.4° model low end, internal compensation, no CFF, no measured Bode.
5. Negative LDO thermal 0.723 W nominal / 1.026 W adverse — PCB-dependent.
6. L1 5.0 mm body vs 5.1 mm allowance (0.1 mm pre-solder), hot Isat not guaranteed, 16-piece stock.

## Bottom line

**Remaining work is qualification, not correction.** Bench gates that must be measured before any
rating is claimed: positive NRAW / U13 IN–NR–FB–OUT startup excursion with D30 fitted (D30 is a
**mitigation, not a guaranteed ≤ +0.3 V clamp**, and no Vf or hot-leakage bound was invented —
cached data is only 500 uA @40 V without temperature, with 0.5 mA/25 °C and 5 mA/125 °C carried as
explicit *assumptions*); loaded start, eFuse retry/short/unplug/backfeed; loop/phase/DCM/load steps
with C93 still DNP and no fitted CFF; hot magnet/eFuse/fault and thermal; magnet height 5.0 vs
5.1 mm and clearance. After that, a separate worker synchronises the old PCB, and the user ACK is
still required before any PCB start.

## Delta review `6219eddc` → `56ffdfcc` (read-only)

Scope: applied the authorised same-repo delta in this isolated workspace, confirmed tree equality to
`56ffdfcc`, then read `docs/sr2-review-resolution.md`, `docs/sr2-post-review-receipt.json`,
`docs/sr2-post-review-erc.json` and the 16 patched files. No source, native, BOM, generator, test or
PCB edit; no new research, no other worktree, no commit.

| Finding | Status | What I checked myself |
|---|---|---|
| F1 positive NRAW kick | **mitigated**, residual measured gate | D30 is `BigModular:Device_D_Schottky`, `dnp no`, pin 1 named `K` → system GND, pin 2 named `A` → NRAW (names read from `hardware/BigModular.kicad_sym`); BOM row `D30,SS34 40V,…,C8678,MDD,Basic`. Budget still carries `positive_NRAW_charge_sharing_no_switch_upper_sensitivity_V = 0.5447` against `positive_NRAW_limit_V = 0.3` and states D30 is mitigation only. **No ≤ +0.3 V guarantee is claimed, and I do not claim one.** |
| F2 VIN bypass | **disclosure closed**, still an analysis item | 8.8 µF nominal / 3.0096 µF screened unchanged; TI's 10 µF now labelled *typical*, not a specified minimum. |
| F3 power wording | **closed** | Each row now carries `allocation_1p85A_pass` **and** `below_nominal_eFuse_limit` separately. 400/400/250 → 2.028089 A, both false. 600/200 → 1.976765 A, planning false / nominal-ILIM true. `rated_output_current` still `null`. |
| F4 loop screen | **closed** | `crossover_RHP5_screen = "NOT_QUALIFIED"`, `paired_efficiency_adverse_crossover_Hz = null`, `measured_phase_margin_deg = null`, `min_RHP_Hz = 54.999 kHz`, `efficiency_adverse_RHP_Hz = 37.265 kHz`, and the note explicitly disclaims co-occurrence. No boolean pass survives. |
| F5 counts | **closed** | Audit 122 refs / 350 pins / 39 null; BOM 91 Basic + 21 Extended + 3 DNP + 1 Manual = 116 parts = 344 real pins + 6 flags; 39 `(no_connect` occurrences; 23 hierarchical ports. Matches the resolution doc. |
| Basic / max-Extended discipline | **maintained** | `new_Extended_types_vs_SR1` is still only `C1848803` (L1). D30 is Basic `C8678`, C93 is DNP `C57112`. The correction adds no new Extended class. |

### Relied on the candidate's receipt (not re-run here)

54 focused tests (0 fail/error/skip, 11 frozen SR1 + 7 new regressions, log hashed `f11d1595…`), native
XML parity, deterministic generation, 108 protected hashes (`protected_existing_bytes_unchanged=true`),
tree binding `d5c2544c…` / manifest `5724f659…`. **I did re-hash the 44 `candidate_sha256` entries
myself: 44/44 match, 0 mismatch.** I **read** the post-review ERC artefact myself —
8 sheets, 0 violations, `ignored_checks=[]`, severities error+warning+exclusion — but I did **not**
rerun the suites, ERC, hash checker or any generator, per the bounded scope.

### Residual risks that are bench/assembly gates, not schematic defects

D30 clamps only through its own temperature-dependent Vf, and without it (or with a high Vf) the
low-side body diode still bounds the excursion near +0.6…0.7 V — above the LDO's +0.3 V limit, hence
the measurement gate. Hot D30 leakage (5 mA assumed at 125 °C) is added converter load and is already
carried in the budget. C93's 0603 footprint must stay unfitted, so assembly must honour the `DNP` and
"not purchased" flags.

**Provenance:** old `6219eddcb0564f3d4e32e45aaaecf92a3316cbd7` (round 1) → new
`56ffdfcc699484aaed3a943f2e606517eb7bdb53` (this delta). No file other than this note was written in
this workspace.
