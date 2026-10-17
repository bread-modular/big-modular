# Split-rail schematic review (Opus, pre-PCB)

Scope: schematic/BOM/generator review of Astra candidate `0f5b49d` staged with `cherry-pick --no-commit` in workspace 057. Candidate input files are unchanged (diff vs `0f5b49d` empty except the expected base-only module `AGENTS.md`/`test_migration_recovery.py`). The PCB is intentionally unsynchronized. No PCB, DRC, CAM or release claim is made here. **No PCB work until the user ACKs.**

## Verdict: CONDITIONAL (no P0 schematic blocker found)

The candidate may proceed to prototype PCB only after user ACK. It must carry the disclosed margins below as bench gates, not as guarantees. No mandatory source or passive correction was identified.

## Verified against source (netlist exported from candidate)

- **U14 TPS55340RTE pinout** matches TI Table 5-1:
  - SW 1/15/16 to PBOOST_SW; VIN2 and EN3 to VPROT; SS4; COMP7; FB8; FREQ9.
  - SYNC5 to GND (TI: tie to AGND if unused); NC 10/14 to GND (TI: "reserved pin that must be connected to ground").
  - PGND 11-13 and EP to GND (TI: PowerPAD to AGND). AGND/PGND star and thermal vias are PCB items.
- **L5/D29 polarity and limits:** L5 runs VPROT to SW; D29 A=SW, K=PRAW, which is correct. VIN/EN are about 9 V against a 32 V range (EN 0-32 V), and UVLO is 2.5-2.7 V falling.
- **U12 ANY-OUT:** 1.4 + 6.4 + 3.2 + 0.8 + 0.2 = 12.0 V. EN and IN are on PRAW (unchanged inherited topology).
- **U4 TPS65131:** ENP8 is GND and ENN10 is BI_EN. TI states the outputs "operate independently" with independent enables, so a negative-only rail is a supported mode. POS_DORMANT is isolated from PRAW/J7. VPOS sits at a passive MID-Vf level, well under its 17 V absolute maximum.
- **Independent re-run:** the 11 focused schematic tests passed. The ERC count is in the evidence JSON.

## Independent arithmetic

| Item | Result |
|---|---|
| PRAW | 1.229 x (1 + 100k/10k) = 13.519 V. DC corners ~13.24-13.80 V (ref 1.204-1.254) |
| FB bias | TI IFB max 20 nA @25 C gives 2 mV output error. The 100 nA screen (10 mV) is conservative |
| fsw | (57500/120k)^(1/1.03) = 400 kHz. TI 80k row spread is 460/577/740 kHz, so expect about +-20% |
| Duty / current | D = 0.334 at 9 V and 0.371 at 8.5 V. At 0.8 A PRAW, 85%: Iin 1.50 A, dI 1.16 App, peak ~2.1 A versus ILIM min 5.25 A |
| Fault current | ILIM max 7.75 A is below the L5 table Isat of 11 A. SS34 is 3 A / 40 V against 13.8 V reverse |
| RHPZ | ~156 kHz at 8.5 V / 0.8 A, consistent with the <14 kHz crossover screen |
| NRAW | 1.213 x 1415k/121k = 14.185 V |
| N12 | 1.175 x (1 + 92.1k/10k) = 11.99675 V |
| VREF load | 10.03 uA versus the 10 uA accuracy-test condition. This is an accuracy footnote, not a stress issue |

## Non-blocking prototype risks (bench gates, disclosed by Astra; confirmed real)

1. **Negative headroom:** the reserve over the TPS7A33 1 V accuracy-condition headroom is ~0.985 mV, and only under the unguaranteed +-100 nA FBN sensitivity. This is a spec-condition margin, not a dropout cliff at real loads. Bench gate: measure NRAW-N12 headroom hot and cold at full load.
2. **NRAW recommended range:** the modeled peak is 14.979 V versus the TPS65131 recommended -15 V (21 mV). This is a model screen, not a guarantee. Bench gate: measure NRAW at the corners.
3. **PRAW effective capacitance:** the screen passes by 13 nF only. It is sensitive to the DC-bias curve of the 25 V X5R 1206 parts. The positive loop phase is 41.5 deg in the model; measure the step response.
4. **Full-step transient:** an abrupt full-load step is not proven within the 100 mV dip allocation (model bound 1.179 V, which could briefly drop U12 out of regulation). Typical Eurorack loads do not step like this. Bench gate.
5. **Sequencing:** boost EN = VPROT, U12 EN = PRAW, with no PG sequencer and no output disconnect. +12 V passively follows VPROT minus Vf (~8 V) until the boost soft-start (~30 ms) completes. The negative rail is independent. This is accepted and documented; there is no rail-order promise.
6. **Inrush:** ~0.393 A is a typical value only and excludes running loads. Validate startup at full load, eFuse retry, unplug and short behaviour on the bench.
7. **FB-open overvoltage:** the TPS55340 has no output OVP. If R86 opens, PRAW can rise toward the SW limit, beyond the 25 V caps and U12 input. This needs an assembly defect, so it is not a P0. First power-up should use a current-limited source with PRAW monitored.

## Optional (not required; user decision, no edit made)

- A DNP PRAW clamp footprint and one spare DNP 1206 PRAW pad would add FB-open protection and capacitance margin.

## Unresolved (stated, not researched further)

- The TPS26600 dVdT equation was not re-verified (the TI fetch returned HTML).
- TPS65131 FBN bias maximum and VNEG absolute maximum were not re-extracted.
- The TPS55340 SW absolute maximum was not re-grepped; 13.8 V PRAW makes this low risk.
- Inherited R6/C10/C11 Extended classification and the TPS26600 OVP/UVLO divider were outside the delta scope.
