# SR2 schematic — Opus independent review (read-only)

Two passes. Pass 1 reviewed `6219eddcb0564f3d4e32e45aaaecf92a3316cbd7`. Pass 2 is an
exact-delta review of `56ffdfcc699484aaed3a943f2e606517eb7bdb53`. Advisor OFF. No
circuit/generator/BOM/test/PCB edits by this reviewer. Only this note and
`sr2-opus-review-evidence.json` are added (`git add -N`). Not committed.

## Final verdict (56ffdfc): CONDITIONAL PROTOTYPE GO

No further mandatory schematic correction. The go is conditional on:

- explicit user ACK before any PCB work;
- bench gates G1–G4 and mechanical/thermal gate G5 below.

This is not a qualification, rating, measured-stability or release claim. PCB remains
deliberately old and unsynchronized; no PCB parity is claimed.

## Pass 2 — 56ffdfc delta review

### Input proof

- Before refresh: index equal to the 6219 tree (excluding these two notes); worktree equal to index.
- Refresh: `git diff --binary 6219… 56ff… -- modules/usb-power` applied with `git apply --index`.
  16 files, no conflicts, no paths outside the module, no collision with these notes.
- After refresh: index equal to the 56ff tree repo-wide (excluding these notes); worktree equal
  to index.
- `*.kicad_pcb/pro/dru/prl` changed 6219→56ff: 0.

### Independently checked (native netlist export of 56ff)

| Item | Result |
|---|---|
| Components | 116 (114 + D30 + C93) |
| Net nodes (real pins) | 344 |
| `(no_connect` occurrences | 39 (01:9, 02:5, 03:1, 05:20, 07:4) |
| D30 | SS34 40V, C8678, `D_SMA`; pin2 anode = NRAW, pin1 cathode = GND |
| C93 | `DNP CFF / TBD`, 0603, DNP; pin1 GND, pin2 NINV_FB → spans R9+R15+R84 (whole upper leg) |
| U3 / R9 / R10 | pins unchanged from pass 1 (GND=NRAW, VIN=VPROT, SW, FB, EN, BOOT) |
| BOM delta | only D30 and C93 rows added; no existing rows changed (see evidence JSON) |

### Read from candidate, NOT re-run by this reviewer

- Post-review ERC (`docs/sr2-post-review-erc.json`): 0 violations, no ignored checks.
- 54 focused tests + 11 frozen SR1 tests, deterministic generation/native parity,
  108 protected file hashes, 23 hierarchical ports, 350 total incl. 6 flags.

### Finding status

| ID | Pass 1 | Pass 2 (56ff) |
|---|---|---|
| F1 NRAW positive startup kick | must-fix | **Closed as mitigation.** D30 matches the requested fix. Still not a guaranteed ≤+0.3 V clamp → G1 |
| F2 loaded startup / eFuse vs 4 A | bench gate | Unchanged → G2 |
| F3 loop / CFF provision | recommended | **Closed.** C93 DNP across whole upper divider; screen now `NOT_QUALIFIED` → G3 |
| F4 span / EN / unplug | bench gate | Unchanged → G4 |
| F5 Basic/Extended reuse | info | **Closed.** D30 reuses Basic C8678; C93 metadata-only, DNP and BOM-excluded |
| F6 L1 height / Isat | PCB fit gate | Unchanged → G5 |

No new wiring or normal-case hard-limit issue found in the delta. D30 reverse voltage
is about 14.1–14.6 V against 40 V. Its leakage is now an explicit budget sensitivity, not a
datasheet hot maximum.

### Current budget disclosure (from candidate, checked for consistency)

- `rated_output_current = null`.
- +400/−400 mA adverse 2.028 A exceeds both the 1.85 A planning figure and the 1.987 A nominal eFuse limit.
- +600/−200 mA adverse 1.977 A exceeds planning but is below the nominal eFuse limit.
- Treat ±current combinations as targets only.

### Remaining gates (not schematic blockers)

- **G1** — Scope U13 IN/NR/FB/OUT and NRAW at plug-in and hot re-plug, with D30 fitted.
- **G2** — Loaded start at worst-case loads: eFuse trip, U3 current limit, rise time.
- **G3** — U3 loop: load-step, DCM/pulse-skip and phase at low line. Fit C93 only if data require it.
- **G4** — Unplug, reverse current, EN behaviour and VIN–NRAW span at 9.45 V input plus fault cases.
- **G5** — L1 5.0 mm max height against the 5.1 mm allowance, hot saturation and thermal.

## Pass 1 — 6219edd (historical)

- **Verdict:** HOLD for F1.
- **Reviewer-run checks:** ERC severity-all with 0 violations; 31 focused tests OK; 114 components; 340 net nodes.
- **Arithmetic:**
  - NRAW = 0.596 × (1 + 226.2k/10k) = 14.0775 V.
  - EN at the 28 V span = 5.05 V, or about 5.14 V with an assumed 5 µA bias.
  - Zero-bias kick ≈ 0.29–0.31 V; the candidate's own upper estimate is 0.545 V.
  - Constant-C 5 ms charge ≈ 0.74 A output, ≈ 2.1 A inductor average.
- **Source:** TI SNVA897 recommends a Schottky from −VOUT to ground. https://www.ti.com/lit/pdf/snva897

### Corrections to pass-1 statements

- "20 `(no_connect` markers" was wrong. It was a `grep -c` line count on single-line sheet
  files. The true occurrence count was 39 at 6219 and is still 39 at 56ff.
- "Brief's 23 NC not reproduced" is withdrawn. The 23 refers to hierarchical ports, per the
  candidate. This reviewer did not independently count ports.
- The 340 vs 346 node difference at 6219 matches real pins vs pins + flags; at 56ff it is 344 vs 350.

## Unknowns

- The TPS7A33 +0.3 V positive limit was taken from the candidate documents, not re-checked in the datasheet.
- SS34 hot leakage, TPS26600 ILIM tolerance at 6.04k and TPS54302 minimum soft-start time.
