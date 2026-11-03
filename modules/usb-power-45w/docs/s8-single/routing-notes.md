# usb-power-45w single board S9.2 / P2.2: routing notes

> **Routing-ready. The items in this file are post-prototype acceptance tests, not design blockers.**
> Board: [`hardware/single/usb-power-45w-single.kicad_pcb`](../../hardware/single/usb-power-45w-single.kicad_pcb),
> P2.2 (S9.2b), 175 references / 80 functional nets, every part on F.Cu, **unrouted** apart from the fixed S9.2b
> thermal-via fields (26 standard vias, 26 spokes, 3 B.Cu landing pours) and the 15 rule areas.
> Review document: [s8-single-board.md](../s8-single-board.md).

The owner cannot bench-build: prototypes come assembled from JLCPCB. So everything the analysis cannot prove is
listed in [section 2](#2-acceptance-tests-and-uncertainty-register) with the pad it is measured on, a procedure, a pass
limit and the cost of a failure (respin, or a BOM/divider change on the existing footprints).
[Section 1](#1-test-point-table) is the test-pad table the router must keep, and
[section 3](#3-routing-constraint-list) lists the routing constraints.

**Machine-readable half.** `placement.json` → `routing_contract` and `ground_connection` are generated from
[`tools/s92_contract.py`](../../tools/s92_contract.py). After a wording change, run
`python3 -B tools/place_s8.py --refresh-contract`; the board is not touched. The DRC-enforceable half lives in the native
files: `place_s8.py --apply-rules` writes the net classes (`.kicad_pro`), the `S92_*` rules (`.kicad_dru`) and the `RA_*`
rule areas (board), and `--apply-thermal-vias` writes the S9.2b thermal-via fields ([3.12](#312-drc-rules-net-classes-and-rule-areas), [3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b)).
`tools/check_s8_board.py` checks what the unrouted board can show (`board-p1.json` → `routing_contract_screen`: pad nets,
16 pad anchors, four 2.54 mm pairs, seven proximity rows, Kelvin pad nets and the ground split; `pre_routing_checklist`:
the eight items below). All of these pass. It lists the 17 copper/via items it cannot check yet as PENDING
([3.11](#311-post-routing-gate-before-any-cam-or-export)). If this file and the generated contract disagree, fix the
generator. Never hand-edit the JSON.

**Coordinates** are the native KiCad board frame in mm, with y pointing down. The outline spans x 49.73–150.28 and
y 54.25–102.30. The panel (front) edge is at y 102.3, the bottom of the KiCad view; J2/J3 sit at the rear edge,
y 54.25. Distances are pad centre to pad centre unless stated. Net `-12V` is the N12_VOUT node and `GND` is PGND.

## Pre-routing checklist

What must be true before routing starts. Each line is machine-checked by `tools/check_s8_board.py` (`board-p1.json` →
`pre_routing_checklist`, item ids in brackets); all eight pass on P2.2.

| Item | Must hold before routing | P2.2 |
| --- | --- | --- |
| Net classes (`netclasses`) | The eight contract classes VIN, PWR_12V, PWR_N12V, GND, SWITCH, SENSE, AGND_U2 and QUIET are in the project, and every functional net is in exactly one of them; six gate-drive/supply nodes stay in Default on purpose ([3.2](#32-net-classes-and-widths)) | present |
| DRC rules (`drc_rules`) | The `.kicad_dru` holds the two R1 J1/SW1 edge allowances plus the 22 generated `S92_*` rules ([3.12](#312-drc-rules-net-classes-and-rule-areas)) | present |
| Rule areas (`rule_areas`) | The 15 `RA_*` rule areas are on the board, each holding its listed parts and no other part's pad ([3.12](#312-drc-rules-net-classes-and-rule-areas)) | present |
| Via-in-pad decision (`via_in_pad`) | **Prohibited** (owner, 2026-11-02): no plated hole in any footprint pad, no via touching a pad or its mask opening, every via the standard 0.3/0.6 mm tented, unfilled through via ([3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b)) | decided, holds |
| Thermal-via fields (`thermal_vias`) | U5 10, U4 10 and U9 6 standard vias beside the exposed pads, one spoke each into the pad copper, one B.Cu landing pour per part, at the parts' actual positions ([3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b)) | placed |
| Stack-up and copper weight (`stackup`) | 4 layers, 1.6 mm, JLC04161H-7628: 35 / 15.2 / 15.2 / 35 µm copper (1 oz outer, 0.5 oz inner), 0.2104 / 1.065 / 0.2104 mm dielectric ([3.1](#31-process-layers-and-planes)) | chosen |
| Test pads (`test_pads`) | All 27 test pads are bare F.Cu with a mask opening and no paste ([section 1](#1-test-point-table)) | exposed |
| Placement (`placement`) | Placement, local-loop, ground-split and routing-contract screens pass | pass |

**Checked after routing**, never before: the 17 PENDING copper/via items of
[3.11](#311-post-routing-gate-before-any-cam-or-export) (thermal areas and via counts, TVS proximity, Kelvin routing, the
AGND link, current-path widths), plus native DRC 0 / unconnected 0 / parity 0, which keeps enforcing everything above.

## 1. Test-point table

**Pad standard.** Every acceptance pad added in S9.2 (TP20, TP22–TP30) is **`USBPOWER45:TestPoint_Pad_D1.5mm`**. It
is the stock KiCad pad copied unchanged: 1.5 mm round SMD copper on F.Cu, F.Mask opening, no paste, 2.5 mm courtyard
circle. The 17 pads kept from S7/S8 stay **`USBPOWER45:TestPoint_Pad_D1.0mm`** (1.0 mm round, same construction, 2.0 mm
courtyard circle). They are DC-meter and logic-analyser clip points only, and no test needs a ground spring on them.
All 27 pads are bare copper: no assembly part and no BOM line, and JLCPCB leaves them exposed. A 2.54 mm pair takes a
probe tip plus ground spring, or a differential probe.

Rules for every row:

- Keep the pad where it is placed. The placement is final, and the screen limits each pad's distance to its anchor.
- No via, other-net track or other exposed copper inside the pad's courtyard circle, so that a probe cannot bridge
  two nets. Tented vias outside the circle are fine.
- Signal pads take a ≥ 0.25 mm stub. Power-net pads tie into their pour with ≥ 0.8 mm copper.
- No pad carries load current, except TP26/TP27 during CL-1 (1 A for ≤ 20 ms; solder the injection leads there).
- GND pads (TP27, TP29) get one PGND via to In1 just outside the pad, never in it.

### 1.1 Acceptance pads (contract `TEST_POINTS`)

| TP | Net | Location (all F.Cu; x, y; anchor distance ≤ limit) | Pad | Connection / keep-out | Measured there (test) | Limit |
| --- | --- | --- | --- | --- | --- | --- |
| TP1 | `VPD` | 81.55, 78.10; Q3.2 4.05 ≤ 5.0 (input group, beside C1) | 1.0 mm round (S7) | ≥ 0.25 mm stub from the VPD pour; DC only, reference TP8 | VPD at the module: input range IN-1, UVLO/OVP thresholds IN-2, source sag S1–S4 | 13.5–16.5 V operating; U5 on 12.26–12.98 V rising, off 11.37–12.19 V; OVP trip 17.30–19.44 V rising, recovery 16.03–18.27 V |
| TP26 | `VIN` = D24 cathode = U2 pin 7 / U4 pin 3 (buck-boost input node) | 92.10, 85.50; D24.1 8.55 ≤ 9.0; 2.54 mm above TP27 | 1.5 mm round | VIN pour with ≥ 0.8 mm copper (CL-1 injection lead) | D24 clamp voltage and pulse energy CL-1 (T1-D); VIN ripple/ringing EMI-1; converter input IN-1; S1–S4 | CL-1 ≤ 30.0 V including ringing at 1 A / 20 ms, ∫V·I dt ≤ 0.648 J; EMI-1 ≤ 1.5 V p-p (20 MHz BW); IN-1 ≥ 12.5 V at VPD 13.5 V and 3 A input |
| TP27 | `GND` | 92.10, 88.04; D25.1 5.21 ≤ 6.0 | 1.5 mm round | one PGND via to In1 beside the pad; ≥ 0.8 mm to the GND pour (CL-1 return) | ground-spring reference and injection return for TP26 | – |
| TP20 | `P12_VOUT` (R109 force, converter side) | 121.99, 69.85; R109.1 9.22 ≤ 11.0; 2.54 mm east of TP24; D26.1 3.4 mm | 1.5 mm round | joins P12_VOUT with ≥ 1.0 mm copper or ≥ 2 vias from the B.Cu P12_VOUT area, never through +12V copper | force drop V(TP20−TP24) against sense V(TP22−TP23) KS-1; D26 clamp CL-2 (T2-B) | KS-1 V(TP20−TP24) ≥ V(TP22−TP23); CL-2 P12_VOUT ≤ 24.0 V (U2 VOUT 25 V abs) |
| TP24 | `+12V` (R109 force, rail side) | 119.45, 69.85; R109.4 3.67 ≤ 5.0 | 1.5 mm round | +12V pour, ≥ 0.8 mm | DC regulation IN-1; load-step and Bode output LS-1; CC-1 output (ripple is read at J2, 1.3) | 11.54–12.65 V DC; ≤ 60 mV p-p (20 MHz); LS-1 PM > 45°, GM > 10 dB |
| TP22 | `P12_ISP` (R109 sense +, U2 pin 12) | 121.99, 72.39; R109.2 8.84 ≤ 10.0; 2.54 mm east of TP23 | 1.5 mm round | 0.2 mm stub that branches from the sense pair after it leaves the R109 pads; no pour, no current | V(TP22−TP23) for KS-1 and CC-1 | VSNS 48–52 mV at the limit; I = V/18 mΩ within 2.62–2.95 A |
| TP23 | `P12_ISN` (R109 sense −, U2 pin 13) | 119.45, 72.39; R109.3 3.41 ≤ 5.0 | 1.5 mm round | as TP22 (the two stubs run as a pair) | Kelvin sense − (KS-1, CC-1) | see TP22 |
| TP25 | `-12V` (N12_VOUT at the converter) | 124.90, 74.50; U4.1 4.25 ≤ 6.0; ground spring on D4.1 (GND, 3.1 mm) | 1.5 mm round | −12V copper, ≥ 0.8 mm | −12 V regulation and ripple IN-1/TH-3; T1 bus tests; reference for U4 pin 2 (EN-1) | −11.38…−12.62 V DC; ≤ 60 mV p-p |
| TP28 | `AGND_U2` (R113 pin 1 side) | 99.00, 68.40; R113.1 4.07 ≤ 5.0; 2.54 mm east of TP29 | 1.5 mm round | 0.25 mm AGND_U2 trace from R113.1, part of the island: no pour, no via to any GND copper; C34.1 (+12V) 2.2 mm away | AGND island against PGND, GS-1; sole-bridge check with R113 lifted, GS-2 | GS-1 ≤ 5 mV DC either sign, ≤ 50 mV p-p (20 MHz); GS-2 > 10 Ω |
| TP29 | `GND` (PGND, R113 pin 2 / C82.2 side) | 96.46, 68.40; C82.2 8.64 ≤ 9.0 | 1.5 mm round | one PGND via to In1 beside the pad; no trace towards the AGND island | GS-1/GS-2 reference; probe ground for SW2 at L1 pad 2 (4.9 mm), EMI-1 | – |
| TP30 | `N_EN_RETURN` (Q14 drain / Q15 source) | 120.25, 97.60; Q15.2 3.33 ≤ 5.0 | 1.5 mm round | 0.25 mm stub (Quiet class) | AND-gate mid-node default, EN-1; T1 | MAIN_LED_OK low ≤ 0.1 V; RUN high ≤ 0.1 V; RUN low with MAIN_LED_OK high ≤ 3.37 V and U4 EN off |
| TP19 | `STARTED` | 89.35, 100.00; U12.5 24.72 ≤ 25.0 (front logic row) | 1.0 mm round (S8.5) | 0.2 mm stub | one-shot latch, S1–S4 (logic analyser ≥ 1 kHz) | high at the first enable; cleared only by RESET/POR |
| TP10 | `ARMED` | 96.90, 99.80; U11.1 31.81 ≤ 33.0 (front logic row) | 1.0 mm round (S8.5) | 0.2 mm stub | arming delay, S1–S4 | 0.31–0.88 s after the first enable; ≤ 0.90 s |
| TP9 | `RUN` | 94.60, 99.80; U13.3 3.37 ≤ 12.0 | 1.0 mm round (S7) | 0.2 mm stub | fault latch S3/S4; T2 trip response; EN-1 trigger | low within 20 µs of OV_N low |
| TP5 | `MAIN_OK` | 99.10, 99.80; R63.2 10.33 ≤ 12.0 | 1.0 mm round (S7) | 0.2 mm stub | U5 PGOOD/FLT: IN-2 OVP/UVLO response, S1/S2 | low within 14 µs + PGOOD deglitch of an OVP trip |
| TP6 | `OV_N` | 85.00, 56.60; U20.2 7.28 ≤ 10.0 | 1.0 mm round (S8) | 0.2 mm stub | rail-overvoltage guard, T2 | low ≤ 20 µs at ≥ 0.5 V overdrive |

### 1.2 Kept diagnostic pads (contract `kept_diagnostic_pads`)

| TP | Net | Location (F.Cu; x, y; next to) | Pad | Measured there | Limit / expected |
| --- | --- | --- | --- | --- | --- |
| TP2 | `VPD_U1` | 85.35, 78.45; C1.1 1.9 mm, U1.1 2.8 mm | 1.0 mm round | CH224A supply behind the Q2/Q3 limiter and the D9 zener (IN-2, IN-3) | ≤ 25.2 V (D9 SMAZ24, 24 V ±5 %) |
| TP3 | `MAIN_IN` | 62.80, 86.50; D10.1 3.4 mm, U5 IN | 1.0 mm round | D10 forward drop V(TP1−TP3) at 3 A (TH-2) | ≤ 0.75 V (screen value) |
| TP4 | `VIN` | 59.70, 56.60; R92.1 4.1 mm (VIN damper) | 1.0 mm round | VIN at the damper end, DC | as TP26 DC |
| TP7 | `MAIN_IMON` | 64.75, 74.80; R26.1 3.9 mm, U5 pin 14 | 1.0 mm round | U5 input-current monitor (R26 20k, 0.558 V/A typical): S1/S2, TH-2 | informational (typical scale), not a pass limit |
| TP8 | `GND` | 68.20, 74.10; D15.1 2.9 mm | 1.0 mm round | DC and logic ground for the 1.0 mm pads | – |
| TP11 | `FAULT_LATCH` | 65.00, 71.40 | 1.0 mm round | U12B fault latch (S3/S4, T2) | latched high until RESET |
| TP12 | `P12_OK` | 63.50, 56.60; R35.2 2.5 mm, U18 pin 1 | 1.0 mm round | +12 V monitor | high above ~9.98 V (nominal) |
| TP14 | `N12_OK` | 71.50, 56.60; U18 pin 14 2.6 mm | 1.0 mm round | −12 V monitor | high above ~10.05 V magnitude (nominal) |
| TP15 | `V20_OK` | 74.00, 56.60; R85.2 2.8 mm | 1.0 mm round | U5 status-validity floor on VPD | high above 7.67–9.27 V VPD |
| TP16 | `V3V3` | 67.30, 71.40; R80.1 3.3 mm | 1.0 mm round | always-on logic LDO U9 | 3.23–3.37 V (the ±2 % calcs corner) |
| TP17 | `REF_OV` | 80.00, 56.60; U20 pin 5 7.8 mm | 1.0 mm round | guard reference U21 (TLV431) | 1.22–1.26 V |

### 1.3 Probe points without a pad (no added copper)

- **J2/J3 rail pins**: B-side THT joints on a 2.54 mm pitch, the same pinout on both headers. Measure +12 V at pin 9/10
  with the ground spring on pin 7/8, and −12 V at pin 1/2 against pin 3/4. This is what the rack sees, and it is the
  reference point for ripple and LS-1.
- **L1 pads** (U2 switch nodes, EMI-1): SW1 is L1 pad 1 (93.89, 81.09), with the probe ground on D25 pin 1 (GND,
  4.0 mm away). SW2 is L1 pad 2 (93.89, 72.59), with the ground on TP29 (4.9 mm). Use tip-and-barrel or a ≤ 5 mm
  spring on a ≥ 500 MHz probe. The switch nodes deliberately have no pad.
- **D1 pads** (SMB, 4.3 mm apart): VPD attach transient, tip on D1.1 (VPD) and spring on D1.2 (GND) (IN-3).
- **U4 pin 2** (EN_N, SO-8 lead) against TP25 (−12V): EN relative to the U4 ground (T1, EN-1).
- **Thermocouples** (36 AWG, Kapton tape or thermal epoxy) on U2 top, the R109 body, the D10 cathode tab, U5 top and
  U4 top (TH-1…TH-3).
- **Fixture**: bench-supply tests go through a USB-C power-only breakout (VBUS/GND); loads through a 16-pin IDC
  breakout on J2 (and J3); the CL-1 injection leads are soldered to TP26/TP27.

## 2. Acceptance tests and uncertainty register

Each row is a quantity the analysis cannot prove. None blocks routing or the prototype order. Run them on assembled
JLCPCB prototypes in this order:

1. Power-up checks: IN-1, EN-1, GS-1, KS-1.
2. Limits: CC-1, IN-2.
3. Thermal: TH-1…TH-3.
4. Stability and EMI: LS-1, EMI-1.
5. Start-up: S1–S4.
6. Tests that risk damage, on a sacrificial unit: CL-1/T1, T2/CL-2, IN-3, POR-1, GS-2.

Record raw waveforms and logs. A failed or aborted step stays recorded as a FAIL; a later good run never replaces it.
In "Failure means", **BOM** is a value or part change on the existing footprints (no new copper) and **respin** is a new
PCB. Limits are numbers on a fixture, not human judgement. The T1/T2/S1–S4 detail matrices are in
[s8-single-board.md](../s8-single-board.md) (sections 6 and "Accepted architectural residuals"); this table is their
summary with the test pads.

| ID | Quantity (not provable analytically) | Assumption made | Risk if wrong | TP / probe | Measurement procedure | Pass limit | Failure means |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **CL-1** (T1-D) | D24 SMBJ20A clamp voltage and energy under the real surge, i.e. a finite bus-injection pulse into VIN | The rated clamp (VC 32.4 V at 18.6 A, 10/1000 µs) bounds the 1 A clamp: 24.92 V at 25 °C, 27.71 V at Tj 150 °C. The 600 W rating, mapped to a 20 ms rectangle (√t), gives 69.8 W at 50 °C against the 32.4 W budget (margin 2.15). A source overvoltage never reaches D24: U5 OVP (≤ 19.44 V) opens first | VIN above D25 (30 V) or U2 (42 V abs); D24 degraded (leakage) or shorted | TP26 tip + TP27 spring; current probe on the injection lead | No USB input (repeat with USB present and RUN low). Inject 1 A for ≤ 20 ms into TP26/TP27 from a current-limited pulse source, 33 V compliance with automatic disconnect. Start at 25 °C and at 50 °C, ≥ 200 s between pulses. Log V(TP26) and I, integrate V·I. Afterwards check VIN leakage at 16.5 V and a normal restart | VIN ≤ 30.0 V including ringing; ∫V·I dt ≤ 0.648 J; clamp current ends by 20 ms; leakage up by ≤ 10 µA after cooling; normal start after RESET; any abort = FAIL | **BOM**: D24 alternate (C364296 / C151922, same SMB land) if the clamp level is out. **Respin** only if layout ringing dominates (D24-to-bank loop) |
| **T1** (A–C) | Backfeed current in the field: module unpowered or latched off on a live ±12 V bus | The existing `modules/usb-power` works in the rack and survives being plugged into a live bus, so backfeed is not occurring in practice. The S9.1 mitigations stay exactly as they are (own-VPD Q1 emitter, Q14/Q15 AND sink, R112, R115 default, D24/D25/D26), and no further backfeed hardware is added. Analysis: U4 cannot enable without own VPD AND RUN AND MAIN_LED_OK (netlist-derived 16-row truth table); 0.389 mA DC bus load; 2.98–7.68 mJ capacitor charge | U4 enabled from the bus or VIN pumped; U2 VIN below −0.3 V on a fast or cold hot-plug | TP30, TP25, TP26, TP24; U4 pin 2 against TP25; fixture bus currents | T1-A: no USB, ±12.0/±12.6 V bus, 1 A limit, 0.44 mF per rail, ramp ≤ 1 V/s at 25 °C, hold 10 s. T1-B: same with USB present and FAULT latched (RUN low). T1-C: negative rail only, both rail orders | EN_N − V(−12V) ≤ 0.11 V settled (≤ 0.5 V transient); zero U4 switching; VIN −0.3…1 V after 100 ms (T1-B: −0.3…30 V, not climbing); each bus current < 10 mA after 100 ms | **Respin** only if U4 switches or EN rises while own input is absent (logic defect). Otherwise this is an accepted residual with a usage rule: power the bus down before plugging, never parallel running supplies. Hard hot-plug stays unqualified, and no backfeed hardware is added (owner). A D25 forward-drop miss is **BOM** (lower-VF SOT-23 pair) |
| **TH-1** | U2 junction and R109 temperature on the real copper | U2: TI JEDEC 2s2p RθJA 43.4 °C/W gives 108.4 °C at 50 °C ambient and the CC limit (1.345 W). That holds only if the [3.8](#38-thermal-copper-and-vias-the-board-behind-the-thermal-screens) copper is built; the effective RθJA allowed for 125 °C is 55.8 °C/W at the CC limit and 73.7 °C/W at 2.4 A. The loss model assumes the switching times and 1.5× hot RDS(on). R109: 0.159 W with the 300 mm² copper gives +13.5 °C | Thermal fold-back or Tj > 125 °C at 50 °C ambient; R109 drift | thermocouples on U2 top and the R109 body; TP24, TP20 | Bench supply with TP1 at 13.5 V and at 16.5 V. +12 V at the CC limit (raise the load until CC engages) and at 2.4 A; −12 V at 0.35 A. Still air, ambient recorded, 30 min to steady state | U2 case rise ≤ 70 °C over ambient at the CC limit (Tj ≤ 125 °C at 50 °C with a 5 °C case-to-junction allowance); R109 rise ≤ 30 °C | **Respin** (copper) if 3.8 was not met. If it was met: a rating change (+12 V current or ambient, documented) or **BOM** (R110 to a lower fSW, with the ripple and loop rechecked) |
| **TH-2** | D10 and U5 temperature at 3 A input | D10 SS1060: 0.75 V × 3 A = 2.25 W needs an effective RθJA ≤ 33.3 °C/W (Tj ≤ 125 °C at 50 °C) with the 3.8 D10 copper. U5 dissipates ≤ 0.48 W (53 mΩ max); with the S9.2b beside-pad field its RθJA bound is 43.3 °C/W, Tj ≤ 70.7 °C at 50 °C ([3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b)) | D10 overheating; U5 thermal shutdown | thermocouples on the D10 cathode tab and U5 top; TP1/TP3; TP7 | TP1 at 13.5 V; raise the loads until the input is 3.0 A; 30 min | D10 tab rise ≤ 70 °C; V(TP1−TP3) ≤ 0.75 V; U5 rise ≤ 50 °C (screen) | **BOM** (lower-VF Schottky on the same SMC land) or a documented input-rating change; **respin** if the copper was not met |
| **TH-3** | U4 LMR38020 temperature | EP on the −12 V copper (≥ 300 mm² on In2/B.Cu) through the S9.2b beside-pad field: 10 vias, no via in the pad, ΔR +0.4 °C/W against the old in-pad holes. S9.2 has no separate U4 loss model | U4 thermal shutdown at −12 V 0.8 A | thermocouple on U4 top; TP25 | VIN 13.5 V and 16.5 V, −12 V at 0.8 A, 30 min | U4 case rise ≤ 60 °C (screen) | rating change (−12 V current, documented) or **respin** (copper) |
| **LS-1** | +12 V loop stability with the real rack capacitance | Sampled complex-loop model: 13,824 corners, PM ≥ 59.73°, GM ≥ 12.37 dB, crossover 387–13,566 Hz. Covers passive rack C 0–440 µF, cable 0.08–0.25 Ω / 0–0.5 µH and loads 0.05–2.4 A. GEA ±30 % and the one-period delay are assumptions; active rack loads are not modelled | Oscillation or ringing on +12 V; audible artefacts; nuisance guard trips | TP24; J2 pin 9 / pin 7 (B side); Bode injection point by rework | (a) Load step 0.5↔2.0 A at ≥ 1 A/µs at J2, with 0 / 220 / 440 µF electrolytic at J2, VIN 13.5 V and 16.5 V. (b) Bode with an FRA: lift R8 pin 2 (+12V end) and fit a 10–20 Ω injection resistor (rework on one unit). (c) The owner's rack, at no load and at full load | Bode PM > 45°, GM > 10 dB. Load step: second excursion ≤ 25 % of the first (≈ PM ≥ 45°), settled ≤ 1 ms. No sustained oscillation at any corner, including no-load FPWM. Ripple ≤ 60 mV p-p | **BOM** (R111/C83 compensation, 0603) or a narrower published rack-capacitance envelope (documented). No respin |
| **IN-1** | Input range at the module with the real cable and connector drop | 13.5 V at VPD = 14.25 V source minimum − 0.75 V at 3 A (≤ 0.25 Ω loop). Converter VIN ≥ 12.5 V after D10 (0.75 V) and U5 (53 mΩ × 4.7 A) | Rails out of regulation at low line | TP1, TP26, TP24, TP25 | Bench supply set so TP1 reads 13.5 V, then 16.5 V, under 33 W (+12 V 2.4 A, −12 V 0.35 A), 10 min each. Repeat with the owner's 15 V / 3 A PD adapter and cable | TP24 11.54–12.65 V; TP25 −11.38…−12.62 V; no FAULT; input ≤ 3.0 A at 13.5 V | documented adapter/cable list; no BOM or respin expected |
| **IN-2** | UVLO and OVP threshold spread over temperature | TI full-temperature threshold limits, plus R2/R3 0.1 %/25 ppm and R114/R24/R28/R4 1 %/100 ppm stacked over a 100 °C TCR span with 150 nA pin leakage. Bands: on 12.26–12.98 V, off 11.37–12.19 V, OVP rise 17.30–19.44 V, OVP fall 16.03–18.27 V | No start at 13.5 V with cable drop (loaded start margin 0.52 V); nuisance OVP at 16.5 V (0.80 V margin) | TP1, TP5, TP26 | Bench supply through the USB-C power breakout, 0.5 A limit, no rail load. Ramp ≤ 0.1 V/s from 10 to 20 V and back, recording VPD at each MAIN_OK edge. Test at 25 °C and, where available, at 0 °C and 50 °C | inside all four bands at every temperature tested | **BOM/divider**: R3/R114 (UVLO), R24 (OVP). No respin |
| **IN-3** | VPD transient at USB-C attach (cable inductance against the ceramic input) | D1 SMBJ22A (VBR ≥ 24.4 V, VC 35.5 V at 16.9 A) and the small attach capacitance keep VPD below the LM2901B 36 V recommended maximum at U18/U20 (38 V abs) | U18/U20 or the U9/U5 inputs overstressed at hot-plug | D1.1 tip / D1.2 spring; TP2 | 20 hot-plugs each with the PD adapter and with a 15 V bench supply over 1 m and 2 m cables, unloaded and at 33 W; single-shot scope ≥ 100 MHz | VPD peak ≤ 36 V; VPD_U1 (TP2) ≤ 25.2 V | **BOM**: D1 to SMBJ20A on the same SMB land (VR 20 V ≥ 18.98 V; VBR at 0 °C 21.7 V > OVP maximum). **Respin** only for added input damping |
| **EMI-1** | Switch-node ringing and conducted noise at 966 kHz (U2) and ~790 kHz (U4) | The HotRod package with C8/C81 at the pins keeps both hot loops small, so no RC snubber is needed (none is fitted or footprinted). The two converters are only nominally separated; their tolerance bands can touch, which can produce a beat | Switch-node overshoot near the U2 ratings; HF noise or audio-band beat tones on the rails | L1 pad 1/2 with grounds on D25.1/TP29; TP26/TP27; J2 rail pins | ≥ 500 MHz tip-and-barrel at the L1 pads, full bandwidth, VIN 16.5 V, +12 V at 2.4 A and at 0.05 A. VIN ripple at TP26/TP27 (20 MHz BW). Rail ripple at J2, FFT over 20 Hz–20 kHz and 100 kHz–30 MHz | SW1 peak ≤ 30 V and SW2 peak ≤ 20 V (screens under 36 V VIN operating / 25 V VOUT abs); ringing decays within 3 cycles; VIN ≤ 1.5 V p-p (20 MHz); rail ripple ≤ 60 mV p-p (20 MHz); no discrete spur > 100 µV rms in 20 Hz–20 kHz | Ringing or VIN ripple: **respin** (loop layout, snubber footprints). Beat tones: **BOM** (R110 or the U4 RT resistor, to separate the frequencies) |
| **KS-1** | Kelvin sense accuracy of the split land on the real assembly | The sense potential is taken at the RLM12 electrode next to the element, with ≤ 0.2 % residual; the sense traces carry no current | CC limit shifted because the sense picks up force or solder drop | TP22/TP23 (sense), TP20/TP24 (force) | +12 V at 2.00 A DC, measured by a calibrated meter or load (≤ 0.5 %); differential readings with a 4½-digit DMM | R_eff = V(TP22−TP23)/I = 17.6–18.4 mΩ (1 % part, 0.2 % residual, TCR, ≤ 0.5 % meter); V(TP20−TP24) ≥ V(TP22−TP23) | Sense equal to force, or R_eff high: **respin** (sense routing). R_eff off with correct sense: **BOM** (R109 alternate) |
| **CC-1** | +12 V constant-current limit band | VSNS 48–52 mV over 18 mΩ ±1 %, 75 ppm × 100 °C and the 0.2 % Kelvin residual: 2.615–2.946 A. The 2.4 A rating keeps ≥ 0.215 A headroom | Rating not deliverable (low) or U2/L1/R109 overstress (high) | TP22/TP23, TP24 | Raise an electronic load slowly from 2.3 A until +12 V drops 5 %; read I and V(TP22−TP23); VIN 13.5 V and 16.5 V; cold and after the TH-1 warm-up | I_limit 2.62–2.95 A; VSNS 48–52 mV | **BOM** (R109 value or alternate) |
| **GS-1** | AGND_U2 island against PGND on the real copper | The single R113 bridge at C82.2; the island carries only the U2 analog return | FB/COMP corrupted by PGND noise: output jitter, loop shift | TP28/TP29 | VIN 16.5 V, +12 V at 2.4 A; DMM for DC and scope with ground spring (20 MHz) | ≤ 5 mV DC either sign; ≤ 50 mV p-p | **respin** (layout) |
| **GS-2** | Sole-bridge integrity | Gate before CAM: native DRC (a copper bridge is a short) plus exact parity (no second 0 Ω or net tie) and the `check_s8_board.py` ground split | A hidden second bridge | TP28/TP29 with R113 lifted (rework, one unit) | DMM resistance AGND_U2–PGND with R113 removed, then refit R113 | > 10 Ω | **respin** |
| **EN-1** | AND-gate mid-node default and the U4 off state | R115 100k to PGND defines N_EN_RETURN; Q15 as a source follower stays ≤ 3.37 V with RUN low; Q1 VEB ≤ 0.18 V; switch leakage ≤ 1 µA | U4 enable no longer gated by RUN | TP30; U4 pin 2 against TP25; TP9 trigger | (1) USB absent, MAIN_LED_OK low: DMM on TP30. (2) Running: TP30. (3) Press RESET (RUN low) and capture TP30, U4 EN and −12 V through the ≤ 13 ms MAIN_OK deglitch | (1) and (2) ≤ 0.1 V. (3) TP30 ≤ 3.37 V, EN_N − V(−12V) ≤ 0.11 V settled, U4 off | **BOM** (R115 within 50k–1M, R112); **respin** if the structure is wrong |
| **S1–S4** | Start-up and fault behaviour with real PD sources | S9.3 netlist-derived plant: with the FB-injection soft starts (+12 V τ 4.8–18.9 ms, −12 V τ 15–59 ms) and U4 enabled 3.4–18.3 ms after P12_OK, the published 33 W plus 0.44 mF per rail peaks at 2.888 A (split load 2.955 A) from a strict 3.00 A source at 14.25 V + 0.25 Ω: one attempt, zero U5 drop-outs, no source limit, rails good ≤ 196 ms (S9.2 needed 4.649 A for 2.5 ms and latched FAULT) | The real converters ramp faster than the injection model (BAV199 leakage, X7R bias) or a source limits below 3.00 A | TP1, TP26, TP19, TP10, TP9, TP5, TP7; current probe in the USB cable; +12V/−12V and U4 EN on a scope | The S1–S4 matrix in s8-single-board.md section 6 (cold start, PD hard reset, persistent short, repeated resets) with a strict 3.00 A source; log every attempt | S1: single attempt, ZERO U5 drop-outs and no source current-limit event (input ≤ 3.00 A on the probe), rails good ≤ 250 ms after the first enable, U4 EN 3–18 ms after P12_OK, ARMED ≤ 0.90 s, no V3V3/POR reset, no FAULT. S2–S4 as in section 6. Any drop-out or FAULT is a FAIL | **BOM**: larger C84/C85 (slower ramps) or C86 (later U4 enable); respin only if the ramp itself cannot be slowed |
| **T2** / **CL-2** | Rail overvoltage response and the D26 energy | U20 guard (+14.48–15.27 V / −13.27–14.02 V) sets FAULT and U5 opens. D26 SMBJ14A is a finite backstop. Energy-only peaks are +23.42 / −23.59 V without D26 or loads | Downstream modules exposed; U2 VOUT 25 V abs | TP24, TP25, TP20, TP6, TP11, TP9 | T2-A…E as in s8-single-board.md; R8/R14 open is rework on a sacrificial unit | OV_N/FAULT/RUN ≤ 20 µs at ≥ 0.5 V overdrive; peaks ≤ 24.0 V; D26 ≤ 0.10 J; < 1 V within 2 s on a 1k discharge; below-band points never trip, above-band points always trip | **BOM** (guard dividers). The crowbar/eFuse decision stays deferred (owner) |
| **POR-1** | Replug/POR nuisance race (REF_OV settling against RESET release) | REF_OV settles in 9.5–13.75 ms against a POR RESET release ≥ 12 ms: −1.75 ms margin at the worst corner, not established. The outcome is a fail-safe latch (MAIN off until RESET), not damage | Nuisance latch when replugging into a rack that still holds −12 V | TP17, TP6, TP11, TP16 | Hold −12 V on the bus (0.44 mF charged, or a second supply); cycle USB power off/on 20× with 0.2–2 s off time | No FAULT latch in 20 cycles (a latch is a documented nuisance, not damage) | **BOM** (C67 10 µF → 4.7 µF, same 0603, per calcs `replug_por`) |
| **HDR-1** | J2/J3 contact current | Typical 2.54 mm IDC contact ~1 A; +12 V at 2.4 A through one header is 1.2 A per contact | Contact heating and voltage drop | J2/J3 B-side joints (+12V pins 9/10, GND 3–8) | +12 V at 2.4 A through one header, then split over J2 + J3, 30 min; thermocouples on plug and header; drop from J2 pin 9 to the cable end | header/plug rise ≤ 30 °C; above ~2 A per rail use both headers (documented rule) | documented header rule; no respin |

## 3. Routing constraint list

### 3.1 Process, layers and planes

- Route by hand, divide and conquer ([AGENTS.md](../../../../AGENTS.md)): no autorouter. Write each batch to the board
  and run full native DRC plus parity after it; back up the board to `/tmp/` first. Raw reports go in `research/`.
- Use the board's 4-layer, 1.6 mm stack: F.Cu 35 µm (parts, power pours, signals), **In1 15.2 µm solid PGND (net
  `GND`)**, In2 15.2 µm power areas, B.Cu 35 µm (no parts).
- **In1**: no tracks, one piece. No slot or cut within 15 mm of the U2 centre (104.0, 76.84), only via antipads. It is
  solid under the AGND island, the U2/L1 cell and the R109 sense pair.
- **In2**:
  - a VIN area ≥ 300 mm² under the U2/U4 input banks, with ≥ 6 vias from the F.Cu VIN pour;
  - a −12V area ≥ 300 mm² under U4 (or on B.Cu);
  - keep In2 copper out from directly under the L1/L3 bodies;
  - every area one piece, counted from the filled polygons;
  - otherwise only short power hops.
- **B.Cu**:
  - a GND pour ≥ 600 mm² under U2/L1/the banks, stitched to In1 with ≥ 20 vias;
  - a P12_VOUT area ≥ 200 mm²;
  - D10 VPD and MAIN_IN areas ≥ 300 mm² each;
  - inside the U2 GND pour, the only other copper allowed is the single AGND_U2 link trace (3.3);
  - the S9.2b landing pours `TV_U5_B` (GND), `TV_U4_B` (−12V) and `TV_U9_B` (GND) under U5/U4/U9 stay: grow or merge
    them with same-net copper, never cut them.
- **Board rules**:
  - copper to edge 1.0 mm (`min_copper_edge_clearance`, enforced by DRC);
  - courtyards ≥ 1.0 mm from Edge.Cuts, measured (closest now TP19, 1.28 mm);
  - every SMD pad ≥ 2.0 mm from the hand-soldered J1/D8/J2/J3 pads (closest now D8–Q6.3, 2.01 mm);
  - **no via in or touching any pad** (any net, SMD or THT) and no plated hole in any footprint pad, with no exception
    (S9.2b); every via is the standard 0.3 mm drill / 0.6 mm pad tented through via ([3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b));
  - no zero-length, duplicate or dangling segments; track ends centred on pads and vias; 0.05/0.1 mm grid.

### 3.2 Net classes and widths

The project (`usb-power-45w-single.kicad_pro`) defines the classes below, generated from `s92_contract.NETCLASSES` by
`place_s8.py --apply-rules`. Every class keeps the 0.2 mm board clearance, because the TPS552892 RYQ and TPS16630 PWP
lands are 0.20–0.25 mm apart; the separations between classes are custom rules ([3.12](#312-drc-rules-net-classes-and-rule-areas)). Every class uses the
one standard via, 0.3 mm drill / 0.6 mm pad ([3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b)). The class width is KiCad's default for new tracks; the
DRC floor is an `S92_*` rule; the current-path minimums are measured after routing (`min_widths`, PENDING).

| Class | Nets (project patterns) | Default width | DRC floor / max | Contract minimum (1 oz outer, ≤ 10 °C rise) | Notes |
| --- | --- | --- | --- | --- | --- |
| VIN | `VBUS`, `VPD`, `MAIN_IN`, `VIN` | 2.5 mm | 0.25 mm | 2.5 mm on the 3 A path (U5 limit 4.7 A); pours preferred | ≤ 1 A per 0.3 mm via at layer changes: ≥ 4 vias on the input path |
| PWR_12V | `P12_VOUT`, `+12V` | 1.5 mm | 0.25 mm | 1.5 mm (2.95 A CC limit); pours preferred | ≥ 4 vias at layer changes |
| PWR_N12V | `-12V` | 0.8 mm | 0.25 mm | 0.8 mm (~1.5 A LMR38020 limit) | ≥ 2 vias at layer changes |
| GND | `GND` (PGND) | 0.5 mm | 0.25 mm | – | In1 plane, star at C82.2 |
| SWITCH | U2 `SW1`, `SW2`; U4 `SW` | 1.0 mm | 0.5 mm | short F.Cu pours, no thin tracks | no vias (DRC); 3.4 / 3.5 |
| SENSE | `P12_ISP`, `P12_ISN` | 0.2 mm | 0.2 / 0.2 mm | 0.2 mm coupled pair, gap 0.2–0.3 mm | F.Cu only, no via, no pour (DRC); 3.7 |
| AGND_U2 | `AGND_U2` | 0.25 mm | 0.25 mm | – | trace-only island, ≤ 2 vias, no pour (DRC); 3.3 |
| QUIET | U2 `FB`/`COMP`/`FSW` and the C83 node, `FB_N`, `EN_N`, `RT_U4`, `N_EN_*`, the Q1 collector, and every 3.3 V logic, monitor, eFuse-control and status net (60 nets) | 0.25 mm | 0.25 mm | ≥ 0.25 mm | ≥ 0.5 mm from switch-node copper (DRC); short, over solid In1 |
| Default | `EXTVCC`, `BOOT1`, `BOOT2`, U4 `BOOT`, `VPD_U1`, the R92/C5 damper node | 0.2 mm | board 0.2 mm | 0.2 mm | gate-drive and supply nodes; never a power path |

### 3.3 AGND/PGND contract (C82.2 star, R113 the sole bridge)

- **C82.2 is PGND.** R113 pin 2 (`GND`) lands on the C82.2 pad copper (pads 1.95 mm apart; the contract allows
  ≤ 3 mm), with 3–4 PGND vias to In1 at C82.2 (TI SLVSGT7 8.4.1 items 6/7). The router cannot re-break this: C82.2 and
  R113.2 are `GND` in the netlist, so tying C82.2 to AGND_U2 copper is a DRC short.
- **AGND_U2 members**: U2.5 (DITH), U2.17 (AGND), R9.2, R110.2, C83.2, R113.1 and TP28.1. They form a trace-only
  island fed only from R113 pin 1.
- **The fan-out splits the island.** The five U2 bars span the package on a 0.5–0.54 mm pitch: SW1/SW2 leave west,
  VIN/PGND/VOUT east. That separates the north members (U2.17, R113.1, C83.2, R9.2, TP28) from the south-east ones
  (U2.5, R110.2), and F.Cu cannot join them. Use **at most one AGND_U2 via pair and one ≤ 0.25 mm B.Cu AGND_U2 trace**
  over solid In1, for example from beside R110 north under the C8/C81 (east) side to beside C83.2/R9.2. It must not run
  under L1 or the switch nodes. The B.Cu GND pour keeps clearance around it and stays one piece.
- **Forbidden**: an AGND pour on any layer; any AGND_U2 via or copper touching In1/In2/B.Cu GND; a second 0 Ω, a net
  tie or any other bridge; AGND_U2 under SW1/SW2/L1.
- **Checks**: native DRC (any copper bridge is a short) and exact parity (no added 0 Ω or net tie); the
  `check_s8_board.py` ground split (only R113 is on both nets); GS-1/GS-2 on the prototype.

### 3.4 U2 buck-boost cell (TPS552892-Q1, 966 kHz, L1 6.8 µH)

- **Hot loops.** In buck mode the input loop is C8 (100 nF) → VIN bar (7) → HS1/LS1 → PGND bar (9) → C8.2. In boost
  mode the output loop is C81 (100 nF) → VOUT bar (11) → HS2/LS2 → PGND → C81.2. Keep both capacitors where they are
  (pin to pad 3.08 / 3.07 mm, limit 4.5 mm). Connect them on F.Cu with no via in either loop. The PGND copper from the
  bar's east end to C8.2 and C81.2 is one F.Cu area.
- **Fan-out.** Never widen two neighbouring bars at the same end.
  - VIN (7) goes east to C8.1 and the VIN pour.
  - VOUT (11) goes east to C81.1 and the P12_VOUT pour.
  - PGND (9) goes east between them, and west between SW1 and SW2.
  - SW1 (8) goes west to L1 pad 1 and C10.2.
  - SW2 (10) goes west to L1 pad 2 and C9.2.
- **Side-pin escape.** Pins 5/6 (DITH, FSW) sit between the VIN bar end and C8.1, and pins 12/13 (ISP, ISN) between the
  VOUT bar end and C81.1. Both channels west of the capacitors are 0.68 mm wide and take one trace each. Pin 5 leaves
  from its south edge and pin 6 runs east into the channel, then south, to R110. Pin 13 leaves from its north edge and
  pin 12 runs east into the channel, then north. Route these before the VIN/VOUT pours close.
- **Switch nodes.** Compact F.Cu pours from U2 to L1 (about 10 mm), with no vias and no test pad. BOOT capacitors C10
  (BOOT1–SW1) and C9 (BOOT2–SW2) connect with direct short traces. In1 is solid below. B.Cu under SW1/SW2/L1 carries
  the GND pour only, no signals.
- **VCC.** C82.1 joins pins 18/21/2 (VCC/EXTVCC/MODE, one node) with short traces; C82.2 is the star (3.3).
- **FB/COMP.** R8/R9 and R111/C83 sit on the north side at pins 14/15. Use ≤ 0.3 mm traces over In1, away from the
  switch nodes. R8 pin 2 is `+12V` after R109, so it senses the delivered rail.
- **No RC snubber** is fitted or footprinted in P2.2; EMI-1 decides. The VIN damper R92 + C5/C62 (rear left) is a DC-free
  branch: connect R92.1 to VIN with ≥ 0.5 mm copper (26.7 mA rms ripple), at any length.
- **Keep-out.** Inside the U2/L1 cell (U2, L1, C8, C9, C10, C81, C82, R110, R113, R9, R111, C83, R8), F.Cu and B.Cu
  carry no foreign-net tracks except the sense pair (3.7) and the AGND link (3.3). No foreign vias inside the hot loops.

### 3.5 U4 inverting buck-boost cell (LMR38020, −12 V)

- U4's ground pin and exposed pad are **`-12V`, not GND**. The exposed pad has **no via in it** (S9.2b): its 10
  thermal vias sit in two rows of five beyond the short ends of the pad copper, each with a 0.6 mm F.Cu spoke, and land on
  the `TV_U4_B` −12V pour. Grow that pour into the −12V area (In2 or B.Cu, ≥ 300 mm²); never put GND on the EP. R13–R15
  sit 0.25 mm further south to clear the south row ([3.13](#313-no-via-in-pad-standard-jlcpcb-vias-only-s92b)).
- The HF input capacitor C27 (100 nF, VIN to −12V) sits at U4 pins 3/1 (2.26 mm). C25/C26 (VIN to −12V, 50 V parts,
  they see VIN + 12 V) follow, and C24 (VIN to GND).
- SW (U4 pin 8) goes to L3 pad 1 as a compact F.Cu pour. L3 pad 2 is GND, with ≥ 3 vias. The output bank (−12V to GND)
  stays as placed.
- EN_N (R17/R18), FB_N and RT_U4 are quiet nets referenced to the −12V copper. Keep them away from the U4 switch node.

### 3.6 Clamps (D24/D25/D26; D1, D2, D4)

| Part | Net | Placement (screened) | Routing rule |
| --- | --- | --- | --- |
| D24 SMBJ20A | VIN TVS | cathode 8.03 mm to C6.1 (≤ 10) | cathode on the F.Cu VIN pour that joins the U2 bank; anode with ≥ 3 PGND vias at the pad edge; keep the D24 → In1 → bank-GND loop short; TP26/TP27 on the same copper |
| D25 BAT54S | VIN negative clamp | 4.78 mm from D24 (≤ 6) | pins 2/3 on VIN, pin 1 with one GND via |
| D26 SMBJ14A | P12_VOUT backstop | 9.99 mm to C14.1 (≤ 10) | cathode on P12_VOUT through ≥ 1.0 mm copper or ≥ 2 vias from the B.Cu P12_VOUT area, never through +12V copper; anode with ≥ 3 GND vias |
| D1 SMBJ22A | VPD TVS | input group, between J1/F1 and the VPD loads | cathode on the VPD pour; anode with ≥ 3 GND vias |
| D2 / D4 SS34 | +12V / −12V polarity | at the J2 rail pins | short to the header pins, where a rack-side reversal enters |

### 3.7 R109 Kelvin sense: force/sense separation and copper/via budget

- **Land.** `R_Shunt_1206_KelvinSplit_RLM12`. Force pads 1 (`P12_VOUT`) and 4 (`+12V`) are 1.7 × 1.1 mm on the −y
  (north) side. Sense pads 2 (`P12_ISP`) and 3 (`P12_ISN`) are 1.3 × 0.5 mm on the +y (south) side and start at the inner
  land edge, the element side. Copper gap 0.2 mm, mask web 0.15 mm.
- **Force.** Current flows only through pads 1/4: the P12_VOUT pour into pad 1, the +12V pour out of pad 4. Pours keep
  ≥ 0.3 mm from the sense pads, and no pour touches a sense pad.
- **Sense.** Leave pads 2/3 on their +y (south) edge within 0.6 mm of the inner end. Run a 0.2 mm coupled pair (≤ 0.3 mm
  gap; only the last ≤ 2 mm at U2 follow the pin escape of 3.4) on F.Cu to U2.12 (ISP) and U2.13 (ISN). The screened
  anchor distances are 8.19 mm (limit 12) and 10.88 mm (limit 13). The pair never touches force copper or the
  P12_VOUT/+12V pours, stays over solid In1 and uses no vias. TP22/TP23 branch from the pair after it leaves the pads,
  as a 0.2 mm stub pair.
- **Copper/via budget** (thermal, the 1 W rating basis). P12_VOUT (pad 1) and +12V (pad 4) each get ≥ 150 mm² of F.Cu
  copper within 10 mm (≥ 300 mm² together), each with ≥ 3 vias to a same-net B.Cu or In2 area. The sense pads take
  0.2 mm traces only.

### 3.8 Thermal copper and vias (the board behind the thermal screens)

The thermal screens assume this copper. The published rating is **conditional on it being met** by the routed board and
on TH-1…TH-3 (`calcs.json` → `thermal_contract`, status CONDITIONAL).

| Part | Model it supports | Required copper |
| --- | --- | --- |
| U2 | TI SLVSGT7 RθJA 43.4 °C/W (JEDEC 2s2p; EVM 27.5 °C/W); allowed effective 55.8 °C/W at the CC limit | In1 solid PGND (no slot within 15 mm). **≥ 10 PGND vias** 0.3/0.6 mm, centres ≤ 4 mm outside the package outline on the cell's PGND copper: at both PGND land ends where the fan-out leaves room, at C8.2 and C81.2 and on the PGND copper joining them; to In1 and the B.Cu GND pour; never in a pad. **VIN**: F.Cu pour ≥ 120 mm² joining U2.7, C8, C6, C7, C77, C78 and D24 K, with ≥ 6 vias to an In2 VIN area ≥ 300 mm². **VOUT**: F.Cu P12_VOUT pour ≥ 150 mm² joining U2.11, C81, C11–C14, C79, C80 and R109 pad 1, with ≥ 6 vias to a B.Cu P12_VOUT area ≥ 200 mm²; D26 K and TP20 join as in 3.6. **B.Cu GND** ≥ 600 mm² under U2/L1/banks, ≥ 20 stitching vias |
| R109 | TA-I RLM12: 1 W at 70 °C with 300 mm² of copper, derated to 0 at 155 °C | 3.7 copper/via budget |
| D10 | 2.25 W at 3 A needs RθJA ≤ 33.3 °C/W | VPD (anode) and MAIN_IN (cathode) F.Cu pours ≥ 400 mm² each, each with ≥ 8 vias to a same-net B.Cu area ≥ 300 mm² |
| U4 | LMR38020 EP = −12V; beside-pad field ΔR +0.4 °C/W (3.13) | the 10 field vias (no via in the pad) land in one −12V area ≥ 300 mm² on In2 or B.Cu, grown from `TV_U4_B`; no GND on the EP |
| U5 | TPS16630 EP = GND, 0.477 W at 3 A; RθJA 32.2 → 43.3 °C/W with the beside-pad field, Tj 70.7 °C at 50 °C (3.13) | the 10 field vias (no via in the pad) land in the In1 GND plane and the `TV_U5_B` B.Cu pour |
| U9 | TPS7A16 EP = GND (always-on logic LDO, small load); ΔR +6.9 °C/W (3.13) | the 6 field vias land in the In1 GND plane and the `TV_U9_B` B.Cu pour |

### 3.9 Test pads

Keep all 27 pads and follow the rules under [section 1](#1-test-point-table). Never route a power or switch net through
a pad's courtyard circle. Make the 2.54 mm pairs reachable from the top side without removing the panel bracket.

### 3.10 Order of work (divide and conquer)

1. Input group: J1, F1, D1, U1/Q2/Q3, D10, U5, VIN damper, U9.
2. U2 cell: fan-out, hot loops, switch nodes, AGND island and link, sense pair, R109 force pours, D24/D25/D26, TP20–TP29.
3. U4 cell.
4. Header strip: J2/J3, D2/D4 and the header capacitors.
5. Monitors and guard (U18, U20, U21), then the logic (U10–U15).
6. Cross-board links last: VIN, VPD, and ±12 V to the headers and monitors.

The S9.2b thermal-via fields at U5, U4 and U9 are fixed pre-routing copper: route to them, never move, resize or delete
them (`place_s8.py --apply-thermal-vias` rewrites them from the contract). After every batch, check: DRC + parity, no via
in any pad, no track on In1, plane and area pieces, and a render of the area.

### 3.11 Post-routing gate (before any CAM or export)

Measure and report the 17 PENDING items from `board-p1.json` (`tools/check_s8_board.py` measures each one once
the board carries copper beyond the thermal fields):

- `ground.agnd_link`
- `kelvin.sense_routing`
- `min_widths`
- `thermal.D10.copper`
- `thermal.R109.force_copper`
- `thermal.U2.B_Cu_GND`
- `thermal.U2.In1`
- `thermal.U2.PGND_vias`
- `thermal.U2.VIN_area`
- `thermal.U2.VOUT_area`
- `thermal.U4.copper`
- `thermal.U5.copper`
- `thermal.U9.copper`
- `tvs.D1`
- `tvs.D24`
- `tvs.D25`
- `tvs.D26`

Two former items are now native DRC rules ([3.12](#312-drc-rules-net-classes-and-rule-areas)):
`ground.no_second_bridge_copper` (`S92_AGND_U2_to_PGND`, `S92_AGND_U2_island`, `S92_AGND_U2_no_inner_copper`, plus the
short check and exact parity) and `thermal.R109.sense_copper` (`S92_SENSE_pair`, `S92_SENSE_F_Cu_only`,
`S92_SENSE_to_force`).

Also required: native DRC 0 / unconnected 0 / parity 0; no via in any pad and only standard 0.3/0.6 mm vias
(`pre_routing_checklist` keeps checking it); In1 one piece with no tracks; every In2/B.Cu area one piece; the 1 mm edge and
2 mm hand-solder distances measured. An item that is not met gets a routing fix. If it cannot be fixed, report it as a
rating change. It is never a silent pass.

### 3.12 DRC rules, net classes and rule areas

This is the DRC-enforceable half of the contract (DeepSeek audit Blocker 2): with it, native DRC fails a board that breaks
the AGND/PGND split, the Kelvin separation, the TVS clearances, the U2 cell keep-outs or the via policy. All three parts
are generated from `tools/s92_contract.py` by `tools/place_s8.py --apply-rules` (never edited in KiCad):

- **Net classes** in the project ([3.2](#32-net-classes-and-widths)).
- **Custom rules** in `usb-power-45w-single.kicad_dru`, after the two R1 J1/SW1 copper-edge allowances. KiCad evaluates
  the file last rule first and stops at the first rule that matches a pair for a constraint type, so of two overlapping
  clearance rules the stricter comes later; the via rules come first so that a later, more specific `disallow` still
  applies.
- **Rule areas** (`RA_*` zones with keepout flags) on the board. The flags stop every net, in DRC and in the interactive
  router; the net-scoped limits are rules that name the area.

| Rule | Layer | What it enforces |
| --- | --- | --- |
| `S92_via_standard` | all | S9.2b: every via is the plain JLCPCB 0.3/0.6 mm through via (annular ring 0.15 mm); no other size, no microvia, no blind or buried via |
| `S92_via_hole_to_copper` | all | S9.2b: via drill >= 0.3 mm from copper of any other net (JLCPCB standard DFM, no special order) |
| `S92_In1_solid_PGND` | In1.Cu | In1 is the solid PGND plane: no track of any net (3.1) |
| `S92_power_width_floor` | all | no logic-width track on a power net; the current-path minimums are POST_ROUTING min_widths |
| `S92_QUIET` | all | control and logic tracks >= 0.25 mm |
| `S92_SWITCH` | all | switch nodes: F.Cu pours, no vias, no thin tracks (3.4/3.5) |
| `S92_SENSE_pair` | all | Kelvin pair: 0.2 mm, coupled gap 0.2-0.3 mm, no via, no pour (3.7) |
| `S92_SENSE_F_Cu_only` | all | the sense pair runs on F.Cu only |
| `S92_AGND_U2_island` | all | AGND_U2: trace-only, at most one via pair, no pour on any layer (3.3) |
| `S92_AGND_U2_no_inner_copper` | inner | no AGND_U2 track on In1/In2 |
| `S92_AGND_U2_B_Cu_link` | B.Cu | the single B.Cu AGND_U2 link is 0.25 mm |
| `S92_AGND_U2_to_PGND` | all | AGND_U2 copper keeps 0.3 mm from every PGND item; the only bridge is the R113 body (pads 0.85 mm apart) |
| `S92_SENSE_to_force` | all | sense pair >= 0.3 mm from P12_VOUT/+12V force copper; exempt: the R109/U2 land gaps and the U2 pin escape |
| `S92_QUIET_to_SWITCH` | all | quiet nets >= 0.5 mm from switch-node copper (3.4/3.5) |
| `S92_TVS_pad_stress` | all | every D1/D24/D26 pad >= 0.4 mm from copper of any other net (the clamp voltage appears across these gaps) |
| `S92_U2_cell_own_nets` | all | no foreign-net track or via inside the U2/L1 cell (3.4) |
| `S92_U2_cell_B_Cu` | B.Cu | on B.Cu inside the cell only the PGND pour and the AGND_U2 link (3.1) |
| `S92_U2_hot_loop_vias` | all | only PGND vias inside the hot loops; C8/C81 connect on F.Cu (3.4) |
| `S92_AGND_island_nets` | all | only the island's own nets inside RA_AGND_ISLAND |
| `S92_no_via_in_pad` | all | S9.2b: no via in or touching any pad, any net, SMD or THT (owner: no via-in-pad anywhere); no footprint carries a plated hole in a pad either (tools/check_s8_board.py) |
| `S92_TVS_pads_solid` | all | TVS pads join their pours solid, no thermal spokes |
| `S92_hot_loop_pads_solid` | all | U2 VIN/SW/PGND/VOUT bars, C8, C81 and L1 join their pours solid |

| Rule area | Layers | Blocks | Why |
| --- | --- | --- | --- |
| `RA_U2_CELL` | F.Cu, B.Cu | nothing (named by rules) | U2/L1 buck-boost cell (3.4 keep-out): only the cell's own nets route or drop vias here; on B.Cu only PGND and the AGND_U2 link |
| `RA_U2_HOT_LOOP` | F.Cu | tracks | input (C8 - VIN bar - PGND bar) and output (C81 - VOUT bar - PGND bar) hot loops east of U2: pour-only copper, no track of any net, only PGND vias; the DITH/FSW and ISP/ISN side-pin channels stay outside |
| `RA_U2_SW_B` | B.Cu | tracks | B.Cu under L1, the SW1/SW2 pours and the U2 SW bars: the GND pour only, no signal or AGND track |
| `RA_L1_IN2` | In2.Cu | tracks, pours | no In2 copper directly under the L1 body (3.1) |
| `RA_L3_IN2` | In2.Cu | tracks, pours | no In2 copper directly under the L3 body (3.1) |
| `RA_TVS_D24` | F.Cu | tracks, vias | D24 land (VIN TVS): pads join the VIN pour and the PGND anode copper as solid pours; no track, no via in or under the land |
| `RA_TVS_D26` | F.Cu | tracks, vias | D26 land (P12_VOUT TVS): pour-only pad connections, no via in or under the land |
| `RA_TVS_D1` | F.Cu | tracks, vias | D1 land (VPD TVS): pour-only pad connections, no via in or under the land |
| `RA_AGND_ISLAND` | F.Cu | pours | AGND_U2 north island and corridor TP28 - R113.1 - C82 gap - U2.17 - C83.2/R9.2: no pour of any net (the island stays trace-only, PGND/P12_VOUT/+12V pours stop at its edge); only the island's own nets route here |
| `RA_U2_SENSE_ESCAPE` | F.Cu | nothing (named by rules) | the <= 2 mm pin escape of U2.12/U2.13 into the 0.68 mm channel west of C81.1: sense copper wholly inside keeps the 0.2 mm board clearance to force copper instead of 0.3 mm |
| `RA_NOVIA_U5_EP` | F.Cu | vias | U5 exposed pad: no via in the pad (its 10 thermal vias sit beside both short ends) |
| `RA_NOVIA_U4_EP` | F.Cu | vias | U4 exposed pad (-12V): no via in the pad (its 10 thermal vias sit beside both short ends) |
| `RA_NOVIA_U9_EP` | F.Cu | vias | U9 exposed pad: no via in the pad (its 6 thermal vias sit beside both short ends) |
| `RA_NOVIA_U1_EP` | F.Cu | vias | U1 (CH224A) exposed pad: no via in the pad; ground it beside the pad |
| `RA_NOVIA_U2_BARS` | F.Cu | vias | U2 VIN/SW1/PGND/SW2/VOUT bars: no via in a bar; the PGND vias sit beside the bar ends (thermal.U2.PGND_vias) |

DRC cannot express "this pad sits on that pour island" or "this many vias near that pad". Those items are the
post-routing screen of [3.11](#311-post-routing-gate-before-any-cam-or-export), measured by `tools/check_s8_board.py`
after routing: `tvs.D24`, `tvs.D26`, `tvs.D1`, `tvs.D25` (TVS proximity to the conductors they protect), the thermal
areas and via counts, the Kelvin attach and coupling, the AGND link and the current-path widths.

### 3.13 No via-in-pad, standard JLCPCB vias only (S9.2b)

**Rule: No via-in-pad anywhere on this board, standard JLCPCB vias only** (owner decisions, 2026-11-02). This replaces
the S9.2 audit round's proposal to keep the in-pad holes and order "Epoxy Filled & Capped" (POFV).

**Via spec** (`s92_contract.VIA_SPEC`; DRC rules `S92_via_standard`, `S92_via_hole_to_copper`, `S92_no_via_in_pad`;
`check_s8_board.py` checks the rest):

- every via is a **0.3 mm drill / 0.6 mm pad** through via (F.Cu–B.Cu), annular ring 0.15 mm; no other size, no 0.2 mm or
  laser microvia, no blind or buried via;
- tented on both sides by the board setup, not covered, plugged, filled or capped, and no via overrides that;
- via drill ≥ 0.3 mm from copper of any other net; via copper ≥ 0.1 mm from every pad (any net) and outside every
  solder-mask opening;
- thermal fields on a 0.6 mm pitch: 0.3 mm drill edge to drill edge (JLCPCB minimum 0.2 mm).

**Footprints.** U4, U5 and U9 use hole-free copies of their pinned land patterns, generated by
[`tools/s92_parts.py`](../../tools/s92_parts.py): `TI_SO-PowerPAD-8_NoViaInPad`,
`HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm_Mask2.96x2.96mm_NoViaInPad` and `TPS7A16_DGN0008C_NoViaInPad`. Each is the
pinned file with every plated hole and the B.Cu-only copy of the exposed pad removed; the lands, solder-mask window,
paste, courtyard and 3D model are unchanged. The drilled originals stay in the library, unchanged, for the routed S7
boards. No footprint on this board has a plated hole in a pad (`verify_s8.py` and `check_s8_board.py`).

**Thermal-via fields** (`s92_contract.THERMAL_VIA_FIELDS`, written by `place_s8.py --apply-thermal-vias`). Each exposed
pad gets one row of vias beyond each short end of its copper, ring 0.15 mm from the pad copper (DRC floor 0.1 mm), each
via with its own 0.6 mm F.Cu spoke that runs 0.3 mm into the pad copper, and a B.Cu landing pour of the pad net under the
part. The long sides have no room: the pin rows are 0.375 mm (U5), 0.45 mm (U4) and 0.5 mm (U9) from the pad copper.

| Part (exposed pad) | Before: in the pad | After: beside the pad (usable vias) | B.Cu landing pour | Moved to make room |
| --- | --- | --- | --- | --- |
| U5 TPS16630 PWP (pin 21, GND) | 15 × 0.3 mm | **10**: two rows of 5 at x 56.35 and 63.75, y 79.1–81.5 | `TV_U5_B`, GND, 83.6 mm² | C2 0.45 mm west, R24 and C3 0.45 mm east |
| U4 LMR38020 DDA (pin 9, −12V) | 8 × 0.3 mm | **10**: two rows of 5 at y 76.5 and 81.9, x 129.6–132.0 | `TV_U4_B`, −12V, 65.4 mm² | R13, R14, R15 0.25 mm south |
| U9 TPS7A16 DGN (pin 9, GND) | 4 × 0.2 mm (non-standard drill) | **6**: two rows of 3 at x 83.05 and 86.95, y 91.6–92.8 | `TV_U9_B`, GND, 40.3 mm² | – |

**Thermal penalty.** The model (`s92_contract.thermal_via_model`, `calcs.json` → `thermal_contract.via_change`) puts the
exposed-pad heat into the outer copper over the solder window and carries it to the landing plane through the vias (the
lateral 35 µm copper path to each row plus 18 µm-plated 0.3 mm barrels) in parallel with the prepreg under the pad copper.
It assumes all of the exposed-pad heat takes this path, so the ΔR it gives is an upper bound on the change of RθJA.

| | U5 (PWP, to In1) | U4 (DDA, to B.Cu) | U9 (DGN, to In1) |
| --- | --- | --- | --- |
| Pad → plane, holes in the pad | 3.14 K/W | 20.39 K/W | 13.21 K/W |
| Pad → plane, beside-pad field | 14.25 K/W | 20.83 K/W | 20.08 K/W |
| ΔRθJA (upper bound) | **+11.1 °C/W** | +0.4 °C/W | +6.9 °C/W |

- **U5** at the rated 3 A input dissipates 3.0² × 53 mΩ = 0.477 W. RθJA goes from TI's 32.2 °C/W (JEDEC, vias in the
  pad) to **43.3 °C/W**, so Tj at 50 °C ambient goes from 65.4 °C to **70.7 °C: a thermal penalty of +5.3 °C at rated
  load**, against the 125 °C limit (125 °C would need 157 °C/W).
- **U2** has no exposed pad and its lands were never drilled, so nothing moves: its ≥ 10 PGND vias were already standard
  0.3/0.6 mm vias beside the bar ends (`thermal.U2.PGND_vias`), and `RA_NOVIA_U2_BARS` now also keeps a router out of the
  bars. RθJA stays at the JEDEC 43.4 °C/W: Tj **94.1 °C at the 2.4 A rating** (1.017 W) and **108.4 °C at the 2.946 A CC
  limit** (1.345 W) at 50 °C, against 125 °C. Penalty 0 °C.
- **U4**: +0.4 °C/W. Its −12V vias run the full board thickness either way, so the barrels dominate, and the field has 10
  vias against 8. There is still no U4 loss model; TH-3 measures it.
- **U9**: +6.9 °C/W on a small always-on logic load.

**Rating: unchanged**, +12 V 2.4 A / −12 V 0.8 A, ≤ 33 W together: U5 and U2 stay below 125 °C at their rated currents.
`calcs.json` → `thermal_contract.via_change` and `validation.json` → `no_via_in_pad` carry the numbers. `s8_calcs.py`
asserts the U5 limit, so a change that pushed it over 125 °C would stop the build until a reduced rating is published.
TH-2 and TH-3 confirm U5 and U4 on the prototype.

**JLCPCB order.** A standard order, nothing exotic: Via Covering **"Tented"** (the default); no "Epoxy Filled & Capped" /
POFV option and no via-in-pad remark; every hole ≥ 0.3 mm, so no small-via surcharge; 4 layers, JLC04161H-7628, 1 oz outer
/ 0.5 oz inner. Pre-order checklist for the via-in-pad footprints:

1. U4, U5 and U9 are the `*_NoViaInPad` footprints and no footprint has a plated hole in a pad (`verify_s8.py`,
   `check_s8_board.py`).
2. The drill file has only 0.3 mm vias and no hole below 0.3 mm.
3. The board setup tents both sides and covers, plugs, fills and caps nothing, and no via overrides it.
4. Native DRC is 0 with `S92_via_standard`, `S92_via_hole_to_copper` and `S92_no_via_in_pad` in the rules file.
5. The order form says Via Covering "Tented" and carries no via-in-pad remark.

### 3.14 S9.3 soft starts and U4 sequencing

- **Behaviour.** U2 and U4 have no soft-start pin. Each gets an FB injection: Css from the rail (C84 220n from +12V;
  C85 470n from GND, the −12 V converter's output) into a node X (SS_P12 / SS_N12), a BAV199 pair (D27 / D28) from X
  into the FB node plus a clamp that empties Css when the rail collapses, and a 470k bleed (R116 / R117) that parks X
  at the divider ground after the ramp, so the diode ends reverse biased and the loop is untouched. +12 V ramps as an
  RC approach with τ = R8 × C84 (15 ms nominal), −12 V with τ = R14 × C85 (47 ms nominal). U4 starts only after
  +12 V is good: Q16 (gate N_EN_SEQ = P12_OK through R118/C86) tops the U4 enable sink chain, R119 sets N_EN_MID.
- **Routing.** SS_P12, SS_N12 and FB_P12 are QUIET nets (≥ 0.5 mm from switch-node copper). Keep the injection link
  short: D27.2 to the R8/R9 FB node and D28.2 to R14/R15. In P2.3 the S9.3 parts sit in interim pockets (D27/C84/R116
  and Q16/R118/C86 between the U2 VIN bank and U10/U12, D28/C85/R117 by C33, R119 under U11), 13–15 mm from their FB
  nodes; route FB_P12 and FB_N over the In1 GND plane, never beside SW1/SW2/SW copper, or pull the
  parts to their dividers with the U2 sense-escape re-placement first.
- **Bring-up.** Scope +12V, −12V, U4 EN (Q1 collector / EN_N) and the input current together; S1 above is the pass
  criterion. No new test pad: P12_OK is TP12, N12_OK TP14, and SS_P12 / SS_N12 are probed on the C84.2 / C85.1 pads.
