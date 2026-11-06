# usb-power-45w — S9.3-10P / R1 routed

> **Current:** J2/J3 are 10-pin IDC; manual routing closed (2026-11-04, B223), In1 GND poured.
> ERC 0, DRC 0 violations / warnings / parity errors, **0 unconnected**. `tools/check_s8_board.py` copper/thermal
> screen still FAIL. Not fabrication-ready.
> [R1 checkpoint, native views and remaining layout work](routing/README.md).
> All S9.3/P2.3 analyses and review claims below are historical; no new startup/thermal qualification is implied.

# usb-power-45w S9.3 / P2.3: strict 3 A start, unrouted

> **Development schematic and placement. Not routed, not a manufacturing release and not bench-qualified.**
> ±12 V only; **15 V / 3 A USB PD** (CH224A R1 **56k**), TPS552892-Q1 positive converter, LMR38020 negative converter,
> S8.5 `STARTED` one-shot retained. **S9.3 adds FB-injection soft starts on both converters and sequences U4 after
> +12 V**, so a strict 3.00 A source starts the module in one attempt.
> Prototype targets: **+12 V 2.4 A / −12 V 0.8 A, ≤33 W combined**. They are conditional on the routing contract and
> on the post-prototype acceptance tests.
> **185 references / 84 functional nets**; an overview sheet plus five pages; all components on F.
> No PCB routing was performed: the only copper beyond the pads is the S9.2b thermal-via fields at U5, U4 and U9
> (26 standard vias, 26 spokes, 3 B.Cu landing pours), next to 15 rule areas. **No via-in-pad anywhere.**

## S9.3 / P2.3: strict 3 A start (2026-11-03)

All three reviews of S9.2b found that the module could not start from a strict 3.00 A PDO: at the published 33 W with
0.44 mF per rail the demand was **4.649 A for 2.5 ms**, U5 dropped out **14 times** and FAULT latched. U5's ILIM
(3.69–4.70 A) does not enforce a 3 A contract. S9.3 fixes it in hardware:

| Item | S9.3 change | Evidence |
| --- | --- | --- |
| +12 V soft start | Neither converter has a soft-start pin (TPS552892-Q1 tSS 2.5–5 ms internal), so U2 gets an **FB injection**: C84 220n X7R from +12V to SS_P12, D27 BAV199 (SS_P12 → FB_P12 injection diode and the PGND clamp that empties C84 when +12V collapses), R116 470k bleed. While D27 conducts the error amplifier holds FB at its reference, so +12V rises as an RC approach with **τ = R8 × C84 = 15 ms nominal (4.8–18.9 ms over tolerance, X7R bias and temperature)**; C84 current at 0 V is 0.43 A nominal (1.35 A at the fast corner), decaying | `calcs.json` → `startup_qualification.soft_start["+12V"]` |
| −12 V soft start | Same network on U4: C85 470n, D28 BAV199, R117 470k to the U4 IC ground: **τ = R14 × C85 = 47 ms nominal (15–59 ms)** instead of the 4 ms internal ramp | `soft_start["-12V"]` |
| U4 sequenced after +12 V | **Q16** (2N7002) tops the U4 enable sink chain; its gate is driven from the U18 delivered-rail monitor **P12_OK through R118 100k / C86 100n**, so U4 enables **3.4–18.3 ms after P12_OK** and drops out with it; **R119 220k** defines N_EN_MID. The TPS552892 PG pin cannot be used: the injection holds FB at the reference for the whole ramp, so PG reads good at ~1 V | `soft_start.sequencing`; `validation.json` → `enable_logic` (Q16/Q15/Q14 chain, R119 ≥ 150k rule) |
| Placement P2.3 | The ten new parts go into free pockets of the P2.2 floor plan; **no P2.2 part moved**: D27/C84/R116 and Q16/R118/C86 between the U2 VIN bank and U10/U12, D28/C85/R117 by C33, R119 under U11. **Interim:** the FB_P12 / FB_N injection links are 13–15 mm long from these pockets; the U2 sense-escape re-placement (open) pulls them to their dividers | `placement.json`, `board-p1.json` (placement pass, no courtyard overlap) |
| Net classes | FB_P12 is a labelled net now (it was `Net-(U2-FB)`); FB_P12, SS_P12 and SS_N12 join the QUIET class, and FB_P12 replaces `Net-(U2-FB)` in the U2 cell and AGND-island net lists | `s92_contract.py`, project, `.kicad_dru` |

**Start-up from a strict 3.00 A source** (netlist-derived plant, 14.25 V source + 0.25 Ω cable, fast corner unless
noted; `calcs.json` → `startup_qualification.demand_rows`):

| Case | Peak input | Time above 3 A | U5 drop-outs | `single_attempt_start` |
| --- | --- | --- | --- | --- |
| Published 33 W (2.4 A / 0.33 A), 0.44 mF per rail | 2.888 A | 0 ms | 0 | true |
| Split load (−12 V 0.8 A), 0.44 mF per rail | 2.955 A | 0 ms | 0 | true |
| Published 33 W, no rack capacitance | 2.874 A | 0 ms | 0 | true |
| No load, 0.44 mF per rail | 0.206 A | 0 ms | 0 | true |
| No load, no rack capacitance | 0.075 A | 0 ms | 0 | true |

The slow corner and a constant-current load model also start in one attempt (peak ≤ 2.941 A; rails good within
196 ms). Negative controls on a rewired netlist fail as they must: D27 open (+12 V start drives the source into its
3 A limit), D28 open (14 U5 drop-outs, FAULT), Q16 gate on V3V3 (−12 V enabled before +12 V is good). The
`verify_s8.py` strict-start check now also fails on any source current-limit event, as test S1 does.

Test S1 passes only with a single attempt, zero U5 drop-outs and no source current-limit event (input ≤ 3.00 A on a
current probe), both rail monitors good within 250 ms, U4 EN rising 3–18 ms after P12_OK, ARMED by 0.90 s, no FAULT.

Native checks: ERC 0; DRC **0 violations, 0 warnings, 0 exclusions, 411 routing opens** (unrouted); exact
ref/pin/net parity (185 refs). Sourcing: a fresh live audit (64 codes, 155 placements, 0 failures, 0 zero-stock or
unpriced codes); S9.3 codes in [s93-sourcing.json](design/s93-sourcing.json) (C21120 and C1623 Basic, C145516
BAV199 Extended, alternates C40919/C68971); partial quantity-1 parts subtotal $22.96. Record:
[review-s93.json](design/review-s93.json).

**Not done in S9.3** (open from the three reviews): per-class `track_width` rules and pour-neck screening, the U2
sense-escape re-placement, and the thermal/connector/no-via/OVP/input-range wording fixes.

## S9.2b changelog: enforceable DRC contract, no via-in-pad (2026-11-02)

The DeepSeek audit of `main` found that the routing contract was prose: the board had no rule areas and the
`.kicad_dru` held only the two J1/SW1 edge allowances, so a router could break the AGND/PGND split, the Kelvin separation,
the TVS clearances or the buck-boost keep-outs and DRC would still say 0. The owner then decided **no via-in-pad anywhere,
standard JLCPCB vias only**. Details: [routing-notes 3.12 and 3.13](design/routing-notes.md#312-drc-rules-net-classes-and-rule-areas).

| Item | S9.2b change | Evidence |
| --- | --- | --- |
| Net classes | Eight contract classes in the project: VIN 2.5 mm, PWR_12V 1.5 mm, PWR_N12V 0.8 mm, GND 0.5 mm, SWITCH 1.0 mm (floor 0.5 mm), SENSE 0.2 mm (fixed), AGND_U2 0.25 mm, QUIET 0.25 mm, plus Default (six gate-drive/supply nodes). All keep the 0.2 mm board clearance; every class uses the 0.3/0.6 mm via | `board-p1.json` → `pre_routing_checklist.netclasses`; routing-notes 3.2 |
| `.kicad_dru` | 22 generated `S92_*` rules after the R1 edge allowances: In1 solid, width floors, SWITCH no vias, SENSE pair (F.Cu only, no via, no pour, ≥ 0.3 mm from force copper), AGND_U2 trace-only with ≥ 0.3 mm to PGND, quiet ≥ 0.5 mm from switch nodes, every D1/D24/D26 pad ≥ 0.4 mm from other nets, U2 cell/hot-loop/island net limits, solid TVS and hot-loop pad connections, and the via rules below | `pre_routing_checklist.drc_rules`; routing-notes 3.12 |
| Rule areas | 15 `RA_*` areas on the board (the board had none): U2 cell, hot loops, B.Cu under L1/SW, In2 under L1/L3, the three TVS lands, the AGND island, the sense escape, and five no-via areas on the U5/U4/U9/U1 exposed pads and the U2 bars | `pre_routing_checklist.rule_areas` |
| Post-routing screen | What DRC cannot express (TVS-to-bank proximity, thermal areas and via counts, Kelvin attach, AGND link, current-path widths) is a 17-item machine screen in `check_s8_board.py`, PENDING until routed | `post_routing_screen`; routing-notes 3.11 |
| **No via-in-pad; vias relocated** | U4, U5 and U9 move to hole-free copies of their lands (`*_NoViaInPad`, the drilled S7 originals untouched). The in-pad holes (U5 15 × 0.3 mm, U4 8 × 0.3 mm, U9 4 × 0.2 mm) become **beside-pad fields of standard vias: U5 10, U4 10, U9 6**, one row beyond each short end of each exposed pad, each via with its own 0.6 mm F.Cu spoke, plus B.Cu landing pours `TV_U5_B` (GND, 83.6 mm²), `TV_U4_B` (−12V, 65.4 mm²) and `TV_U9_B` (GND, 40.3 mm²). C2 and R24/C3 moved 0.45 mm, R13–R15 0.25 mm, to make room | `validation.json` → `no_via_in_pad`; `pre_routing_checklist.via_in_pad` / `thermal_vias` |
| Standard JLCPCB vias only | Every via is 0.3 mm drill / 0.6 mm pad, through, annular ring 0.15 mm, tented, unfilled; no POFV / resin fill, no 0.2 mm or laser microvia, no blind/buried via. DRC: `S92_via_standard`, `S92_via_hole_to_copper` (drill ≥ 0.3 mm from other-net copper), `S92_no_via_in_pad` (≥ 0.1 mm from every pad); the checker adds the board setup, per-via overrides and mask openings. The JLCPCB order is the default "Tented" option, no special order | routing-notes 3.13; `test_standard_vias_and_thermal_fields_on_board` (a via in the U5 pad, a 0.2 mm via and a blind via fail the checker and native DRC) |
| **Thermal penalty** | Beside-pad path model (upper bound): U5 RθJA 32.2 → **43.3 °C/W**, Tj **65.4 → 70.7 °C** at 50 °C and the rated 3 A input: **+5.3 °C at rated load**, limit 125 °C. U2 unchanged (no exposed pad, never drilled): **94.1 °C at 2.4 A, 108.4 °C at the 2.946 A CC limit**. U4 +0.4 °C/W, U9 +6.9 °C/W. **Published rating unchanged**: +12 V 2.4 A / −12 V 0.8 A, ≤ 33 W | `calcs.json` → `thermal_contract.via_change`; `test_via_change_thermal_consequence` |

## S9.2 / P2.2: routing-ready

**Routing-ready. The items in `routing-notes.md` are post-prototype acceptance tests, not design blockers.**

The owner cannot bench-build: prototypes come straight from JLCPCB. Every former "verify on the bench before layout"
item is now one of two things:

- a design change, listed below;
- a post-prototype acceptance test in **[routing-notes.md](design/routing-notes.md)**, with a dedicated test pad, a
  procedure, a pass limit and a failure disposition (respin, or a BOM/divider change).

routing-notes.md holds the test-point table, the uncertainty register and the routing constraint list the router must
honour. Its machine-readable half is `placement.json` → `routing_contract`, generated from `tools/s92_contract.py`.
S9.1 / P2.1 is preserved in git `5df64c7`, together with `review-s91.json` and the previous version of this document.
The S9.2 artefacts were regenerated in `4d7ef52`.

| Item | S9.2 change | Evidence |
| --- | --- | --- |
| 1: D24 → SMBJ20A + R24 9.1k OVP coordination | D24 SMBJ16A → **SMBJ20A** (Littelfuse, LCSC C151257). U5 OVP bottom resistor **R24 6.8k → 9.1k**: the OVP now trips rising at **17.30–19.44 V** (18.34 V nominal) and recovers at 16.03–18.27 V. That is below the D24 20 V stand-off and its 21.70 V breakdown minimum at 0 °C, so U5 removes a sustained overvoltage before D24 conducts. The divider variant was chosen (see the next section) | `calcs.json` → `vin_clamp` (4 TVS × 2 dividers); `validation.json` → `vin_clamp_coordination`; `test_d24_ovp_coordination` with negative controls (S9.1 divider, S9.1 TVS) |
| 2: PGND star fix | C82.2 (the VCC decoupling ground) moves from AGND_U2 to **PGND**. R113 turns so its pin 2 (PGND) lands on C82.2 (1.95 mm) and pin 1 feeds AGND_U2. R113 is the only part on both nets | netlist; `board-p1.json` ground split; `test_pgnd_star_at_c82` (C82.2 on AGND_U2 is a negative control); rule in routing-notes 3.3 |
| 3: Kelvin-split shunt | R109 becomes **TA-I RLM12FTCMR018, 18 mΩ, 1 %, 75 ppm, 1 W** (C393095) on a true 4-terminal split land, `R_Shunt_1206_KelvinSplit_RLM12`. Force pads 1/4 sit on P12_VOUT/+12V. Sense pads 2/3 sit on the new nets P12_ISP/P12_ISN, which go to U2 pins 12/13 only, and take the sense at the electrode next to the element. 0.2 % residual in the 2.615–2.946 A CC band | `tools/s92_parts.py`; `test_r109_true_kelvin_land`; Kelvin screen in `board-p1.json` |
| 4: netlist-derived tests + negative controls | The U4 enable truth table and the 3 A source timelines now derive from the native netlist (`tools/s92_netlist.py`): traced EN/PNP/NMOS-chain structure, tolerance bounds, and a physical 3 A plant with the netlist UVLO/OVP, CC limit, banks and enables. Negative controls rewire a copy of the netlist and must fail: Q1 emitter on +12V or VIN, a gate bypass, R16 to GND, R115 or R112 open, R115 < 50k, Q14 shorted, U5 SHDN or U2 EN off their nets, ISP tied to ISN, R114 open | `test_enable_truth_table_from_native_netlist`, `test_enable_negative_controls`, `test_three_amp_plant_from_native_netlist`, `test_three_amp_negative_controls` |
| 5: N_EN_RETURN default | **R115 100k** from N_EN_RETURN (Q14 drain / Q15 source) to PGND defines the off state. With RUN low and MAIN_LED_OK high, Q15 is a source follower (≤ 3.37 V) and Q1 VEB ≤ 0.18 V. Values below ~50k fail the derived check. Test pad TP30 | enable model and netlist test; EN-1 |
| 6: thermal basis moved into the routing contract | The U2/R109/D10/U4/U5 copper and via requirements are in `placement.json` → `routing_contract.thermal`. `calcs.json` → `thermal_contract` is labelled **CONDITIONAL** on them and on TH-1…TH-3. U2 needs an effective RθJA ≤ 55.8 °C/W at the CC limit (the model's 43.4 °C/W gives 108.4 °C at 50 °C) | `test_thermal_rating_conditional_on_contract`; 13 PENDING items in `board-p1.json` |
| Routing contract and docs | Ten 1.5 mm acceptance pads (TP20, TP22–TP30), project netclasses (Power/Switch/Sense/Quiet), D26 moved beside the R109 pad pairs, [routing-notes.md](design/routing-notes.md). The docs pass also made the contract feasible: the AGND island may use one via pair and one B.Cu AGND trace, because F.Cu alone cannot join U2.17 and U2.5 across the power fan-out; the U2 PGND via and D26/TP20 wording became routable; and the sense-pair escape at U2 is defined. The contract was refreshed with `place_s8.py --refresh-contract`; the board is unchanged | `test_acceptance_pads_and_netclasses`, `test_routing_notes_cover_contract`; `routing_contract_screen` passes |

### D24 / OVP coordination (item 1)

Three rules must hold together:

- (a) VR ≥ 1.15 × 16.5 V = 18.975 V.
- (b) VBR minimum at 0 °C > U5 OVP rising maximum, so the OVP acts first.
- (c) VC at IPP ≤ 42 V / 1.15 = 36.5 V (U2 absolute maximum with a 15 % ringing margin), and VC + 14.02 V < 50 V (C25/C26
  sit between VIN and −12V).

The figures are Littelfuse SMBJ datasheet values, with a VBR temperature coefficient of 0.091 %/°C.

| D24 | VR | VBR at 25 °C | VBR min at 0 °C | VC at IPP | (b) with R24 6.8k (S9.1 OVP max 25.60 V) | (b) with R24 9.1k (S9.2 OVP max 19.44 V) | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SMBJ16A (S9.1) | 16 V, fails (a) | 17.8–19.7 V | 17.43 V | 26.0 V at 23.1 A | fails (−8.17 V) | fails (−2.02 V) | fails (a), (b) |
| SMBJ18A | 18 V, fails (a) | 20.0–22.1 V | 19.56 V | 29.2 V at 20.6 A | fails (−6.04 V) | passes (+0.12 V) | fails (a) |
| **SMBJ20A** | **20 V** | 22.2–24.5 V | **21.69 V** | **32.4 V at 18.6 A** | fails (−3.90 V) | **passes (+2.25 V)** | **all three pass with R24 9.1k** |
| SMBJ24A | 24 V | 26.7–29.5 V | 26.09 V | 38.9 V at 15.5 A, fails (c) | passes (+0.49 V) | passes (+6.64 V) | fails (c): 38.9 V > 36.5 V and 52.9 V > 50 V |

**The divider variant was chosen.** Lowering the OVP from the 20 V-input setting (22.76–25.60 V) to the 15 V input is
a one-resistor change on the protection that is supposed to act first. It also coordinates D1 (SMBJ22A, VBR 23.84 V at
0 °C) for the first time, and it keeps the TVS clamp low. No SMBJ satisfies (b) with the S9.1 divider without failing
(c). In normal operation the 17.30 V OVP minimum sits 0.80 V above the 16.5 V input ceiling, and the 16.03 V recovery
minimum is above the 15.75 V PD source maximum.

**Pulse budget, re-derived for SMBJ20A:** 1 A × VC 32.4 V × 20 ms = **0.648 J**, i.e. 32.4 W for 20 ms (S9.1:
0.52 J / 26 W with SMBJ16A). Capability: mapping the 600 W 10/1000 µs rating onto a 20 ms rectangle with a √t thermal
impedance gives 87.2 W at 25 °C and **69.8 W** after the 50 °C derating, a margin of 2.15. The 1 A clamp is 24.92 V at
25 °C and 27.71 V at Tj 150 °C. No universal joule rating and no continuous claim. Accepted on the prototype by CL-1
(VIN ≤ 30.0 V including ringing at TP26).

### S9.2 verification

- Native **ERC 0**. **DRC: 0 violations, 0 warnings, 0 exclusions, 0 schematic-parity findings**; the **392 unconnected
  items** are the routing opens of the unrouted board (S9.2b: unchanged, with the 22 `S92_*` rules, the 15 rule areas and
  the thermal-via fields in place).
- Exact ref/pin/net parity holds: **175 components / 80 functional nets** (121 including NC nets) and 41 explicit NC
  pins.
- BOM parity: 62 lines with 148 references, plus 27 copper-only test pads, makes 175.
- Tests: **76 run, 76 passed, 0 skipped** from a clean clone (no `*.kicad_prl`, no `research/` logs). They include the netlist-derived
  truth-table and 3 A tests, their negative controls, the routing-notes coverage test and the three S9.2b tests (hole-free
  footprints; standard vias and thermal fields on the board, with a mutated copy that must fail the checker and native
  DRC; the via-change thermal consequence).
- Placement:
  - no courtyard overlaps;
  - edge rule and 2 mm hand-solder clearance pass (closest pair D8–Q6.3, 2.01 mm);
  - 18 local-loop rows with 0 violations;
  - the routing-contract screen passes: 16 pad anchors, four 2.54 mm pairs, seven proximity rows, Kelvin pad nets and
    the ground split;
  - the S9.2b pre-routing checklist passes (net classes, rules, rule areas, via policy, thermal fields, stack-up, test
    pads, placement);
  - 17 copper/via items stay PENDING until routed.
- Mechanics: 0 nominal 3D interferences (6 proxies), IDC strain-relief overshoot −0.4 mm, envelope margin 1.1 mm, case
  depth 5.7 mm.
- Logic: 0 arming/timeline violations, a 16-row enable truth table and 512 digital combinations.
- Sourcing for JLCPCB, from a live audit on 2026-11-02:
  - 60 codes and 145 placements; 0 missing codes, and 0 zero-stock or unpriced machine-assembled codes.
  - The Basic/Extended policy is applied: every R/C is Basic except R2, R3, R93, R94, R98, R99 and R109.
  - Alternates are recorded for D24, D26 and R109.
  - Owner-fitted manual parts: J2/J3 and D8. J2/J3 are Wurth 61201621621; their JLCPCB code C5364137 showed 0 stock,
    and the THT option C5454489 needs a footprint/height check.
  - The partial quantity-1 parts subtotal is $23.12, excluding setup fees, PCB, assembly and shipping. This is not an
    order approval.
- The S9.2 record review-s92.json (git `9cdb9bd`) hashed every tracked source and artefact, including
  `routing-notes.md` and this document.

### Open items: post-prototype acceptance tests, not design blockers

routing-notes.md section 2 defines each test with its test pad, procedure, pass limit and failure disposition:

- **CL-1**: D24 clamp and energy (T1-D). **T1**: bus backfeed. **T2/CL-2**: rail overvoltage and D26.
- **TH-1…TH-3**: thermal on the real copper (U2/R109, D10/U5, U4).
- **LS-1**: +12 V loop with the real rack capacitance. **EMI-1**: switch-node ringing, VIN/rail noise and beat tones.
- **IN-1**: input range with cable drop. **IN-2**: UVLO/OVP spread over temperature. **IN-3**: USB-C attach transient.
- **KS-1/CC-1**: Kelvin accuracy and the CC band. **GS-1/GS-2**: ground star. **EN-1**: N_EN_RETURN default.
- **S1–S4**: start-up with real PD sources (a strict 3.00 A source fails safe at full load plus rack). **POR-1**: replug
  race. **HDR-1**: header contact current.

Outside the module's own acceptance tests: the OV tolerance of downstream modules, crowbar vs eFuse (a deferred owner
decision), and the CAM/assembly review at order time (a separate authorised task). No fabrication export or order.

### Artifacts

- [Native project](../hardware/usb-power-45w.kicad_pro), [schematic PDF](usb-power-45w-schematic.pdf), [BOM](design/bom.csv).
- [Routing notes](design/routing-notes.md), [placement and routing contract](design/placement.json), [board checks](design/board-p1.json), [mechanics](design/mechanical.json).
- [Calculations](design/calcs.json), [validation](design/validation.json), [review-s93](design/review-s93.json).
- [Assembly PDF](design/assembly/usb-power-45w-placement.pdf), [STEP](design/assembly/usb-power-45w-assembly.step.zip), [collision screen](design/assembly/assembly-report.json).
- [S9.2 sourcing evidence](design/s92-sourcing.json) (live rows for every S9.2 code and alternate) and the [whole-design live audit](design/sourcing.json). The older s91/s90/s84/s83 snapshots remain dated evidence, not stock claims.

### Reproducibility

Use the existing generators; never hand-edit generated schematics, PCB or JSON:

```sh
python3 -B modules/usb-power-45w/tools/build_s8.py --output-root <candidate-module-root>
# Netlist changes: place_s8.sync_candidate(<board>, <candidate-root>), then inspect and promote the candidate.
# S9.2b native contract on the promoted board: net classes, .kicad_dru rules and RA_* areas, then the thermal-via fields.
python3 -B modules/usb-power-45w/tools/place_s8.py --apply-rules
python3 -B modules/usb-power-45w/tools/place_s8.py --apply-thermal-vias
# Contract wording only (board untouched):
python3 -B modules/usb-power-45w/tools/place_s8.py --refresh-contract
python3 -B opt/kicad-tools/kicad_tools.py check --config modules/usb-power-45w/tools/kicad-project.json --reports <new-check-directory>
python3 -B modules/usb-power-45w/tools/verify_s8.py --netlist <new-check-directory>/netlist.xml > modules/usb-power-45w/docs/design/validation.json
python3 -B modules/usb-power-45w/tools/s8_calcs.py --out modules/usb-power-45w/docs/design
python3 -B modules/usb-power-45w/tools/check_s8_board.py --out modules/usb-power-45w/docs/design/board-p1.json
kicad-cli sch export bom --fields "Reference,Value,Footprint,QUANTITY,LCSC,MPN,Manufacturer" \
  --labels "Refs,Value,Footprint,Qty,LCSC,MPN,Manufacturer" --group-by "Value,Footprint,LCSC,MPN,Manufacturer" \
  --ref-range-delimiter "" -o modules/usb-power-45w/docs/design/bom.csv modules/usb-power-45w/hardware/usb-power-45w.kicad_sch
kicad-cli sch export pdf -o modules/usb-power-45w/docs/usb-power-45w-schematic.pdf modules/usb-power-45w/hardware/usb-power-45w.kicad_sch
python3 -B modules/usb-power-45w/tools/render_s8.py modules/usb-power-45w/docs/design/img/board-p1.png --title "<title>"
python3 -B modules/usb-power-45w/tools/build_s8_panel.py
python3 -B modules/usb-power-45w/tools/mechanics_s8.py
python3 -B modules/usb-power-45w/tools/s8_mechanical.py
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
# Stage new files first: the record hashes tracked files only.
# Move the old record aside first: its own test skips without it.
python3 -B modules/usb-power-45w/tools/review_s8.py --check <new-check-directory> --tests-log <tests-log> --out modules/usb-power-45w/docs/design/review-s93.json
```

BOM and PDF use native `kicad-cli sch export`; the board image uses `render_s8.py`. `build_s8_panel.py` rewrites the
panel with fresh UUIDs; S9.2b kept the committed panel, whose outline, holes and texts the regeneration reproduced
unchanged. Raw reports and logs stay in the
ignored `research/s92/`; no `*.kicad_prl` file or research log enters the review hashes. Clean-clone testing needs the
repository's KiCad/pcbnew, ngspice, numpy and plotting dependencies. Mechanical regeneration additionally needs
FreeCAD/OpenSCAD. No test needs an ignored local report.

## 1. Own-input enable logic and clamps

```text
MAIN_LED_OK = MAIN_OK AND V20_OK
QUALIFY     = RUN AND MAIN_LED_OK
Q1 emitter  = VPD (own input upstream of D10, never VIN or +12 V)
Q1 base     = R112 to VPD; R16 through Q15 and Q14 to GND
N_EN_RETURN = Q14 drain / Q15 source; R115 100k to PGND (S9.2 default)

EN_relative = EN_N - V(-12V)
QUALIFY=1: EN_relative = (VPD - VCEsat - V(-12V)) * R18/(R17+R18)
QUALIFY=0: EN_relative <= Ileak * R18
```

R17/R18 remain 100k/20k. A live output bus can neither supply Q1's emitter nor qualify either NMOS gate. `RUN=0`, an
invalid `MAIN_OK` or an absent own input each prevents enable. R112 = 5.1k is the default-off base pull-up. R16 = 33k
supplies base current only through both sinks.

**S9.2 adds R115**, so the AND-gate mid-node has a defined DC default; before, it held only Q14.3 and Q15.2. With RUN
low and MAIN_LED_OK still high (≤ 13 ms PGOOD deglitch), Q15 is a source follower: the node stays ≤ 3.37 V and the sink
current ≤ 35 µA, so Q1 VEB ≤ 0.18 V and Q1 stays off. Below ~50k the follower current could bias Q1 on. The derived
check fails R115 = 47k and passes 1M.

The tolerance screen is now derived from the native netlist (`tools/s92_netlist.py`). It gives **1.936 V** minimum at
start, against U4's 1.4 V maximum enable threshold, and **5.52 V** at the running upper corner (VPD up to the 19.44 V
OVP maximum). The **5 µA off-leakage qualification bound** gives **0.102 V**, below the 0.95 V disable threshold. This
is a test/design bound, not an invented TI leakage maximum.

All 16 own-input/RUN/status/live-bus combinations come from the traced netlist structure: EN pin → divider → PNP →
base pull-ups → series NMOS sink chain → GND, with its chain-node defaults. They are not recomputed from an equation.
The negative controls of the S9.2 changelog must fail native verification.

**D24 SMBJ20A on VIN (S9.2):**

- **Ratings:** 20 V stand-off (≥ 1.15 × 16.5 V), **22.2–24.5 V breakdown** (21.70 V minimum at 0 °C), rated
  **32.4 V at 18.6 A**, **600 W 10/1000 µs**.
- **Coordination:** U5's OVP (R24 9.1k) trips at **17.30–19.44 V**, so U5 removes a sustained source overvoltage before
  D24 conducts. D24 only takes finite bus-injection pulses.
- **Engineering qualification budget:** **1 A × 32.4 V × 20 ms = 0.648 J** (32.4 W for that finite interval). Initial
  temperature ≤ 50 °C, ≥ 200 s between pulses. Capability for a 20 ms rectangle at 50 °C is 69.8 W, a margin of 2.15.
  The 600 W figure is **not** a continuous or a 20 ms rating.
- **Protects:** U2 VIN/SW1 (42 V absolute / 36 V operating), U5 OUT, D25 (30 V; VIN ≤ 27.7 V at the 1 A budget, hot)
  and the 50 V VIN capacitors. In the rated-clamp screen, C25/C26 see at most 32.4 + 14.02 = 46.4 V.
- **Acceptance bound:** CL-1, VIN ≤ 30.0 V including ringing at TP26. That is a test limit, not a claim that the TVS
  breakdown is its clamp voltage.

[source](https://www.littelfuse.com/assetdocs/tvs-diodes-smbj-series-datasheet?assetguid=ba555e99-a12d-4f72-a0b6-86b06c67171e)

**D25 BAT54SLT1G:** a forward clamp for the *slew-limited, 25 °C* negative VIN test only (≤ 0.24 V at 100 µA; ≤ 26.5 µA
displacement current at 1 V/s). It does **not** guarantee U2's −0.3 V minimum under fast or cold hotplug.

**D26 SMBJ14A** at P12_VOUT is a finite-energy local backstop for the 25 V U2 output/sense pins and the local MLCCs:
14 V stand-off, 15.6–17.2 V breakdown, 23.2 V rated clamp at 25.9 A, 600 W 10/1000 µs. It does not protect ordinary
16 V downstream capacitors, and it is not a coordinated fuse/crowbar.

## 2. Input range, cable drop, UVLO and OVP

The published range remains **13.5–16.5 V at VPD on the module**, not at the adapter. 13.5 V is the 14.25 V source
minimum less a **0.75 V cable/connector drop at 3 A** (≤ 0.25 Ω loop). The required source is a fixed **15 V / 3 A PDO**
of at least 45 W. U5's 3.69–4.70 A protection limit still does not enforce the PD 3 A contract. 5 V-only or lower-power
adapters are not qualified.

| Divider screen | Minimum | Nominal | Maximum |
| --- | --- | --- | --- |
| U5 UVLO rising (on) | 12.263 V | 12.618 V | 12.976 V |
| U5 UVLO falling (off) | 11.365 V | 11.798 V | 12.193 V |
| U5 OVP rising (S9.2, R24 9.1k) | 17.297 V | 18.343 V | 19.443 V |
| U5 OVP falling (recovery) | 16.031 V | 17.151 V | 18.269 V |

R2/R3 are 0.1 % / 25 ppm/°C; R114, R24 and R28/R4 are 1 % / 100 ppm/°C. The calculation includes the 100 °C TCR span
and the 150 nA pin leakage.

- **UVLO margins:** loaded start **0.524 V**, unloaded start **1.274 V**, running **1.307 V**.
- **OVP margins:** the OVP starts 0.80 V above the 16.5 V ceiling, and the 16.03 V recovery minimum is above the 15.75 V
  PD source maximum.
- **The recommended falling ≥ 11.8 V is NOT guaranteed.** Even ideal divider resistors cannot meet both rising ≤ 13.0 V
  and falling ≥ 11.8 V with U5's full comparator limits: the divider factor would have to be ≤ 13/1.224 = 10.621 and
  ≥ 11.8/1.09 = 10.826 at once. We report the actual 11.365 V minimum falling threshold rather than mislabel it 11.8 V.
- Neither voltage margin nor the logic model alone guarantees startup against a current-limited source (section 6).
- IN-1/IN-2 check the bands on the prototype at TP1/TP5.

## 3. Current limit and thermal

R109 is the **18 mΩ TA-I RLM12FTCMR018**: 1 %, 75 ppm/°C, 1 W with 300 mm² of copper; LCSC C393095 (Extended), with
alternates C50314717, C49164939 and C845266. It sits on the 4-terminal Kelvin split land.

The limit is `Ilimit = VSNS/R109`. Stacking VSNS = 48–52 mV, the resistor's initial tolerance, a 100 °C TCR span and
the 0.2 % Kelvin residual gives **2.615–2.946 A** (nominal 2.778 A). The retained 2.4 A prototype rating keeps
**0.215 A** minimum current-limit headroom. The separate 33 W combined ceiling is unchanged; both per-rail maxima
together would be 38.6 W.

| Load | IC loss screen | Tj at 50 °C ambient, 43.4 °C/W | R109 loss |
| --- | --- | --- | --- |
| 2.40 A | 1.017 W | 94.1 °C | 0.106 W |
| 2.95 A | 1.345 W | 108.4 °C | 0.159 W |

**The thermal basis is conditional (S9.2 item 6).** The 43.4 °C/W figure is TI's JEDEC 2s2p board, while this board is
unrouted. S9.2b does not change it: U2 has no exposed pad and was never drilled (no via-in-pad; its PGND vias were always
beside the bars). The result holds only if the routed board meets the copper/via contract
(`placement.json` → `routing_contract.thermal`, [routing-notes 3.8](design/routing-notes.md#38-thermal-copper-and-vias-the-board-behind-the-thermal-screens)):

- solid In1 PGND;
- ≥ 10 PGND vias at U2;
- the VIN/VOUT pours with their inner and bottom areas;
- B.Cu GND ≥ 600 mm².

Tj ≤ 125 °C needs an effective RθJA ≤ **55.8 °C/W** at the CC limit (73.7 °C/W at 2.4 A). The published rating is
therefore labelled conditional on that contract and on TH-1…TH-3, and the 125 °C regression limit stays. These are
loss-model estimates with assumed switching times, not measured thermal guarantees.

966 kHz and L1 6.8 µH remain. R109's slow output-current loop is **not** a switch-current limit and does not qualify
transient stress. D10 may dissipate 2.25 W at 3 A and needs an effective RθJA ≤ 33.3 °C/W: ≥ 400 mm² per terminal on
F.Cu plus B.Cu areas (TH-2). U4's exposed pad sits on −12V copper (TH-3). S9.2b moved the U5/U4/U9 thermal vias out of
their pads: U5 reaches **70.7 °C** at 50 °C and the rated 3 A input (+5.3 °C, RθJA bound 43.3 °C/W), U4 +0.4 °C/W,
U9 +6.9 °C/W (routing-notes 3.13); the rating is unchanged.

## 4. AGND/PGND routing contract

These nets are fixed in the netlist:

- **AGND_U2:** U2 pads **5 (DITH) and 17 (AGND)**, R9.2, R110.2, C83.2, **R113.1 and TP28**.
- **PGND:** **C82.2**, together with U2.9 and the power capacitors. This is the S9.2 fix; in S9.1, C82.2 sat on
  AGND_U2.
- **The only bridge is R113, populated 0 Ω.** Its pin 2 lands on the C82.2 PGND terminal (1.95 mm apart, ≤ 3 mm) and
  pin 1 feeds the island.

Routing rules:

- Place 3–4 PGND vias at C82.2.
- The island is trace-only: F.Cu, plus at most one via pair and one B.Cu AGND_U2 trace where the U2 power fan-out
  separates U2.17 from U2.5/R110.
- No AGND pour, no second bridge.

The router cannot re-break the star unnoticed: a copper bridge is a native DRC short, and a second 0 Ω or net tie
would break exact parity. `check_s8_board.py` checks the net identities and the C82.2/R113 proximity, and GS-1/GS-2
measure the star on the prototype at TP28/TP29. The full rule list is in routing-notes 3.3. This follows the
manufacturer's single-point ground guidance. [source](https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf)

## 5. Compensation and restricted rack envelope

R111 = **6.8k**, C83 = **100 nF**. `s91_analysis.loop` evaluates the complex gain instead of using an above-zero
crossover shortcut outside its domain:

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

The output bank is split 75 % before and 25 % after R109; the cable/rack capacitance is a separate branch. Zero
capacitor ESR gives no optimistic ESR phase lead. R/C tolerance, ±30 % GEA sensitivity, a one-period delay and an
inner-loop pole are explicit assumptions, **not manufacturer-guaranteed small-signal bounds**. The basis is TI's boost
and buck expressions. [source](https://www.ti.com/lit/ds/symlink/tps552892-q1.pdf)

- **13,824 sampled corners**: minimum phase margin **59.73°**, minimum gain margin **12.37 dB**, crossover
  **387–13566 Hz**, COMP zero **234 Hz**, **0 screen violations**. The old 9.1k/10 nF network fails the same
  regression envelope.
- The published envelope for the positive rail:
  - external capacitance **0–440 µF**;
  - onboard effective C **37.6–96.8 µF**;
  - cable loop R **0.08–0.25 Ω**, L **0–0.5 µH**;
  - passive resistive small-signal loads **0.05–2.4 A**;
  - VIN corners **10.37 V sag, 12.5, 16.5 and 21 V**.
- This sampled model does not prove every intervening corner, nor stability with arbitrary active-rack negative
  impedance or no-load FPWM. Those configurations are **not advertised as qualified**.
- Acceptance test LS-1 requires measured **PM > 45°, GM > 10 dB** and no sustained oscillation with the real rack.
  Without an FRA, a load-step ring ratio ≤ 0.25 screens for the same. A failure is a BOM change (R111/C83), not a
  respin. The old ~0.9 mF startup charge allowance is not a positive-rail stability allowance.

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

The one-shot remains **0.31–0.88 s from the first qualified enable in each powered epoch**; it is not a restartable mask.
Faults after ARMED latch until RESET, and OV_N presets FAULT even before ARMED. **STARTED and FAULT are volatile:** a
complete V3V3/POR collapse clears them. No nonvolatile lockout was added, and automatic power-cycling is not allowed to
erase a failed qualification.

S9.2 derives the 3 A plant from the netlist: UVLO/OVP dividers, CC limit, banks and enables.

- **Demand:** with the published 33 W load and 0.44 mF per rail, a 14.25 V source behind 0.25 Ω must deliver
  **4.649 A for 2.5 ms** (fastest soft start, R109 CC maximum). U5's limit caps the plant at 4.7 A.
- **A strictly 3.00 A-limited source cannot do that.** U5 drops out 14 times and FAULT latches at ARMED. That is the
  fail-safe outcome (RUN low, input off, RESET needed), not a single-attempt start.
- **Without the rack capacitance and the load,** the module starts on 3 A.
- **Real PD adapters** with brief overload headroom are expected to start it. S1 decides per source, and the result
  restricts the qualified source list.
- The tests exercise this source-limited plant and full-reset logic epochs. They do not reproduce every PD adapter's
  internal control loop.

| Case | Qualification condition | Pass criteria |
| --- | --- | --- |
| S1 | Cold start, 14.25 V source +0.25 ohm cable, exact 3.00 A constant-current limit; 0/0.44 mF external each rail; 0/15/25/33 W load; both delay corners; log all attempts | Single attempt: both rail monitors good within 250 ms of first enable; ARMED by 0.90 s; no V3V3/POR reset, no source restart, <=3.00 A steady input; no retry hidden from record. A strict-3 A FAIL is recorded as the expected fail-safe (FAULT latched, input off) and restricts the qualified source list, it is not hidden |
| S2 | Same loads with a PD source hard-resetting on >3 A; include 5 V phase and V3V3 fully collapsed to 0 V | A single hard reset is counted and disqualifies that source/load combination for guaranteed start; no success by discarding earlier failed attempts |
| S3 | Persistent rail short, uninterrupted source, then manual RESET and separate full power removal/reapplication | Each power epoch with input held must fault within 0.90 s+2 ms of first enable, hold RUN low until explicit reset, and fault again with short present |
| S4 | Ten automatic input hard resets every 200 ms while short remains, V3V3 collapsed in each off interval | Qualification result must be FAIL_REPEATED_POWER_RESET, never a pass from a final successful cycle; fixture latches power OFF on the second autonomous reset |

These are post-prototype acceptance tests (routing-notes S1–S4, with TP1, TP26, TP19, TP10, TP9, TP5 and TP7). The
fixture must count autonomous resets across power epochs and stop on the second; a final good-looking cycle must not
replace failed evidence. The persistent-short timeline latches in both epochs after a deliberate power removal and
reapplication. Regressions reject a masked fault, and ten autonomous resets followed by a nominal cycle.

## Accepted architectural residuals: not acceptance of the self-enable defect

There is still **no series reverse blocker or rail disconnect**. The self-enable defect is fixed, but continued claims of
unrestricted live-bus survival would be false. Enabled forced PWM can still sink external power if a powered unit is
paralleled with a higher bus. The −0.9 A LMR38020 figure is typical, not a worst-case bound. No finite-energy TVS can
absorb an unlimited live bus.

The existing `modules/usb-power` works in the rack and can be plugged into a live bus without damage. That is empirical
evidence that the backfeed scenario is not occurring in practice. The S9.1 mitigations are kept exactly as they are,
and **no further backfeed complexity is added** (owner decision). T1 below measures the residual on the prototype.

The residual itself:

- Disabled +12 V injection still charges **2.98–7.68 mJ** into its capacitors and feeds a divider/leakage load of about
  **0.389 mA**.
- A fast −12.6 V step would produce an unclamped VIN displacement of **[-1.23, -5.43] V**; D24/internal diode forward
  conduction can still allow about −1.4 V.
- D25 is not a high-current or cold absolute-minimum guarantee. **Unrestricted hard hotplug remains unqualified.**

T1 deliberately qualifies a specified slow-ramp condition rather than defining an acceptance test that is expected to
fail. Power down the bus before normal connection, and never parallel running supplies.

### T1: bounded bus-injection/clamp qualification

- T1-A: no USB input, +/-12.0 and +/-12.6V external bus, 1A source limit, 0.44mF each rail; ramp <=1V/s at 25C, hold 10s; log EN_N relative to -12V, U4 SW, VIN and bus currents
- T1-B: same with USB present and FAULT latched/RUN low; verify off-state once MAIN_OK deglitch expires and capture the preceding <=20ms interval
- T1-C: only negative rail applied with same bounded slew; repeat rail order
- T1-D (= CL-1): inject a positive 1A, <=20ms pulse into VIN at TP26 (compliance 33V, automatic disconnect), 25/50C, >=200s between pulses. This separately tests D24 energy/clamp; never assume the now-disabled U4 will generate this pulse

**Pass criteria:**

- T1-A/C: EN_N minus -12V <=0.11V settled (<=0.5V transient), zero U4 switching; VIN -0.3..1V after 100ms settled; each bus current <10mA after 100ms
- T1-B: same EN/switching/current criteria after 20ms; VIN may retain own-input charge, must remain -0.3..30V, not climb from bus power
- T1-D: VIN <=30V incl ringing at TP26, measured integral(V*I*dt)<=0.648J, clamp current ends by 20ms, no leakage increase >10uA after cooling; normal restart and regulation after RESET
- All: automatic overvoltage disconnect at VIN 33V, negative excursion abort at -0.3V (fast comparator, not human reaction). An abort is a FAIL, not a pass.

**Excluded:** Hard hotplug, temperatures below25C for D25 forward-drop guarantee, >1A or >20ms sustained injection, and powered parallel supplies require new protection/qualification.

### T2: rail overvoltage, source removal and stored energy

U20 trips at **+14.48–15.27 V / −13.27–14.02 V** and opens U5 through the FAULT latch. It cannot disconnect an external
source attached to a rail, nor instantly discharge a capacitor. There is **no fuse/crowbar or rail eFuse**; that
architecture decision remains **deferred/open**. D26 is a transient backstop, not continuous shunt protection.

The VIN bank energy screen is **5.919 mJ**. Without D26 or loads, the energy-only rail estimates are
**+23.42 V / −23.59 V**; with a typical 440 µF rack they are **+15.98 V / −14.8 V**. These are **not guaranteed
transient peaks**: U2's 24.5 V OVP is not modelled as an ideal clamp. A failed-short power stage can still expose the
bus to the input, and sub-threshold guard faults can persist indefinitely. Ordinary 16 V downstream capacitors are not
thereby qualified.

- T2-A: input16.5V; 0.44mF +0.5A/rail; externally ramp +12V from12 to16.5V at<=1V/ms, <=1A, total injection<=10ms (including ramp), hold<=1ms at16.5V; fixture removes injection automatically after trigger; scope>=100MS/s
- T2-B: R8 open at13.5/16.5V input, 3A source; no external C/no load, then0.44mF+0.5A; capture500ms with independent voltage/current abort
- T2-C: R14 open, same conditions; no assumed LMR38020 output OVP
- T2-D: RUN held low/logic powered, +14.0V and -13.0V external for10min; safely BELOW the minimum guard thresholds; no-trip only refers to OV_N, not RUN
- T2-E: at+15.2V / -13.9V a trip is ALLOWED (inside tolerance bands); repeat guaranteed trip at+15.8V / -14.5V with <=1V/ms slew, <=1A source and >=50us hold (record actual waveform)

**Pass criteria (this module):**

- With >=0.5V rail overdrive beyond each measured trip, OV_N low/FAULT set/RUN low <=20us; MAIN LED off. Keep FAULT latched10s after injection removed, reset explicitly only after fault repair
- Externally driven rail remains externally driven until fixture removal: NEVER require it off while injection remains. After removal connect1k/1W discharge load; both rails below1V within2s at <=0.44mF external C
- T2-B/C: observed positive rail peak<=24.0V and negative magnitude<=24.0V for the500ms capture; positive duration above16V<=100ms with specified1k discharge; D26 pulse energy<=0.10J; normal regulation after repair/RESET
- T2-D OV_N stays high. T2-E band points may trip or not; above-band points MUST trip. Automatic abort at+24V / -24V / VIN33V, source removed in<=2us; any abort fails qualification, no human-only protection

**Downstream qualification:** Without a separate rail protector, downstream modules must tolerate16.5V/10s and sub-threshold +15.3V/-14.1V continuously, and up to24V magnitude/100ms or their measured actual exposure if worse. Ordinary16V caps are NOT thereby qualified; incompatible modules excluded until crowbar/eFuse decision.

No claim is made that a rail turns off while an external source still drives it. The +15.2 V / −13.9 V points lie
inside the tolerance bands and **may trip**: below-band points serve the no-trip tests and above-band points the
required-trip tests. Waveforms, peaks, discharge intervals, energy integrals and automatic aborts are numerical
acceptance criteria, not human observation.

## 20 V support remains possible

The buck-boost topology, the 50 V VIN capacitors and the LMR38020 permit a future retarget. It takes more than
resistors (`calcs.json` → `retarget_20v` records the delta):

- **Resistors:** R1 56k → 120k, R3 10k → 7.5k precision, R114 510 → 0 Ω, R83 100k → 120k, and **R24 9.1k → 6.8k**
  (OVP back to 22.76–25.60 V).
- **D24 must be re-selected.** At a 22 V maximum input the S9.2 rule needs VR ≥ 25.3 V, VBR at 0 °C above the 25.6 V OVP
  maximum, and VC < 42 V. No SMBJ meets all three (SMBJ26A has VC 42.1 V), so a lower-clamp TVS or a new coordination is
  required.
- **D25** must become a ≥ 40 V negative clamp, with forward-drop and footprint requalification.
- **Then recheck** stand-off, clamp peaks, power, loop and source qualification, and update the label, rating and docs.

**No 20 V source is authorized** while the 20 V TVS and the 15 V OVP are populated.

## Placement and sourcing (P2.2)

P2.2 keeps every P2.1 position except:

- R109 gets the Kelvin split land (an explicit footprint replacement);
- R113 turns so its PGND pad lands on C82.2;
- D26 moves right into free space, so the R109 force/sense pad pairs take its old spot;
- R115 sits at Q14;
- the ten 1.5 mm acceptance pads sit at the nodes they measure;
- S9.2b: U4, U5 and U9 take the hole-free `*_NoViaInPad` lands (footprint replacement, same positions), C2 moves
  0.45 mm west, R24 and C3 0.45 mm east and R13–R15 0.25 mm south, clear of the beside-pad thermal-via rows.

L1 and the fixed interfaces stay put. The placement checks find no courtyard overlaps, unapproved edge-rule failures,
hand-solder violations or nominal 3D interferences. Header pins 11–16 remain NC and +5 V is absent. The panel label
reads **PD 15V 3A** (silk only, no geometry change).

Sourcing is complete for JLCPCB assembly at the dated live audit (S9.2 verification above), but it is **not an order
approval**. Two kinds of exception to the Basic-passive target are explicit:

- the precision R2/R3 and guard resistors;
- the 18 mΩ shunt, for which no Basic part exists.

Extended setup fees, PCB, assembly and shipping are not included in the partial subtotal.

## S9.1 changes and S9.0 review disposition (history)

> The S9.1 record. Superseded in S9.2: D24 SMBJ16A in row 1 (now SMBJ20A with R24 9.1k), the WSLP1206 2-pad "Kelvin"
> footprint in row 3 (now RLM12 on a true 4-terminal land), and the C82.2-on-AGND star side in row 4 (now PGND).
> Independent review conversations: Astra `c092ee9e-4fd7-448d-9b10-b87ff022ad27`, DeepSeek
> `2c480974-701a-4e6d-8f7d-f6f1416815d2`. S9.0/P2.0 is preserved in git `41992e8` / `d7d7219`.

| Item | S9.1 implementation | Verification / limits |
| --- | --- | --- |
| 1: self-enabling U4 / backfeed | Q1 emitter moved from +12 V to own VPD upstream of D10; Q14/Q15 series sink requires RUN and MAIN_LED_OK, R112 pulls Q1 off; D24 VIN TVS, D25 low-current negative clamp, D26 local +12 V transient backstop | Native pin checks, truth table and negative-control tests; finite-energy qualification below; no unrestricted hotplug or parallel-supply claim |
| 2: input minimum | R2/R3 precision 100k/10k plus R114 510 Ω | Loaded start guaranteed below 13.0 V under stated resistor/threshold screen; actual falling range disclosed |
| 3: current-limit thermal | R109 18 mΩ WSLP1206R0180FEA, 1 W, manufacturer-specific Kelvin footprint | ≤125 °C test replaces the old <130 °C assertion; sourcing C-code still open |
| 4: ground split | AGND_U2 distinct from GND/PGND; sole R113 0 Ω bridge at C82.2 | Native and board checks plus `placement.json.ground_connection` |
| 5: compensation | R111 6.8k / C83 100nF; exact complex loop calculation rather than above-zero shortcut | 13,824 sampled corners; bounded passive-load/cable/rack-capacitance envelope; real Bode gate remains |
| 6: startup qualification | 3 A limited source and full V3V3/POR collapse/re-arming cases; persistent faults and repeated autonomous resets retained across qualification epochs | Logic timelines plus current/energy screen and explicit bench matrix, not a guaranteed PD-source dynamic model |
| 7: preserved architecture | +5 V absent, 15 V PDO, TPS552892-Q1, S8.5 one-shot, no crowbar/eFuse; 20 V upgrade documented | No routing, no fabrication export/upload |

S9.1 also corrected: P5 header silk → NC, the precision/current-shunt sourcing exceptions, the mechanical revision, the
spare-comparator descriptions and the old results placeholder. No rail fuse/crowbar was added.

---

# History: S8.5 / P1.5 and earlier (superseded by S9.2)

> Kept as the record of the S8.5 design (+5 V series disconnect, 20 V input, TPS62933F +12 V buck). Where
> anything below conflicts with S9.2 above, **S9.2 wins**. The S8.5 review record is `review-s85.json`
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
  place_s8.sync_candidate('modules/usb-power-45w/hardware/usb-power-45w.kicad_pcb', '<candidate-module-root>')"
python3 -B opt/kicad-tools/kicad_tools.py check \
  --config modules/usb-power-45w/tools/kicad-project.json \
  --reports modules/usb-power-45w/research/<new-check-directory>
python3 -B modules/usb-power-45w/tools/verify_s8.py --netlist <check-directory>/netlist.xml
python3 -B modules/usb-power-45w/tools/check_s8_board.py --out modules/usb-power-45w/docs/design/board-p1.json
python3 -B modules/usb-power-45w/tools/s8_calcs.py --out modules/usb-power-45w/docs/design
python3 -B -m unittest discover -s modules/usb-power-45w/tools -p 'test_*.py' -v
python3 -B modules/usb-power-45w/tools/review_s8.py --check <check-directory> --tests-log <log> \
  --out modules/usb-power-45w/docs/design/review-s85.json
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
