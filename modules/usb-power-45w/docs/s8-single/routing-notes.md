# usb-power-45w single board S9.2 / P2.2: routing notes

> **Routing-ready. The items in this file are post-prototype acceptance tests, not design blockers.**
> Board: [`hardware/single/usb-power-45w-single.kicad_pcb`](../../hardware/single/usb-power-45w-single.kicad_pcb),
> P2.2, 175 references / 80 functional nets, every part on F.Cu, **unrouted** (0 tracks, 0 vias, 0 zones).
> Review document: [s8-single-board.md](../s8-single-board.md).

The owner cannot bench-build: prototypes come assembled from JLCPCB. So everything the analysis cannot prove is
listed in [section 2](#2-acceptance-tests-and-uncertainty-register) with the pad it is measured on, a procedure, a pass
limit and the cost of a failure (respin, or a BOM/divider change on the existing footprints).
[Section 1](#1-test-point-table) is the test-pad table the router must keep, and
[section 3](#3-routing-constraint-list) lists the routing constraints.

**Machine-readable half.** `placement.json` → `routing_contract` and `ground_connection` are generated from
[`tools/s92_contract.py`](../../tools/s92_contract.py). After a wording change, run
`python3 -B tools/place_s8.py --refresh-contract`; the board is not touched. `tools/check_s8_board.py` checks what the
unrouted board can show (`board-p1.json` → `routing_contract_screen`: pad nets, 16 pad anchors, four 2.54 mm pairs,
seven proximity rows, Kelvin pad nets and the ground split). All of these pass. It lists the 13 copper/via items it
cannot check yet as PENDING ([3.11](#311-post-routing-gate-before-any-cam-or-export)). If this file and the generated
contract disagree, fix the generator. Never hand-edit the JSON.

**Coordinates** are the native KiCad board frame in mm, with y pointing down. The outline spans x 49.73–150.28 and
y 54.25–102.30. The panel (front) edge is at y 102.3, the bottom of the KiCad view; J2/J3 sit at the rear edge,
y 54.25. Distances are pad centre to pad centre unless stated. Net `-12V` is the N12_VOUT node and `GND` is PGND.

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
| **TH-2** | D10 and U5 temperature at 3 A input | D10 SS1060: 0.75 V × 3 A = 2.25 W needs an effective RθJA ≤ 33.3 °C/W (Tj ≤ 125 °C at 50 °C) with the 3.8 D10 copper. U5 dissipates ≤ 0.48 W (53 mΩ max) | D10 overheating; U5 thermal shutdown | thermocouples on the D10 cathode tab and U5 top; TP1/TP3; TP7 | TP1 at 13.5 V; raise the loads until the input is 3.0 A; 30 min | D10 tab rise ≤ 70 °C; V(TP1−TP3) ≤ 0.75 V; U5 rise ≤ 50 °C (screen) | **BOM** (lower-VF Schottky on the same SMC land) or a documented input-rating change; **respin** if the copper was not met |
| **TH-3** | U4 LMR38020 temperature | EP on the −12 V copper (≥ 300 mm² on In2/B.Cu with the footprint thermal vias). S9.2 has no separate U4 loss model | U4 thermal shutdown at −12 V 0.8 A | thermocouple on U4 top; TP25 | VIN 13.5 V and 16.5 V, −12 V at 0.8 A, 30 min | U4 case rise ≤ 60 °C (screen) | rating change (−12 V current, documented) or **respin** (copper) |
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
| **S1–S4** | Start-up and fault behaviour with real PD sources | Netlist-derived plant: the published 33 W plus 0.44 mF per rail needs 4.649 A for 2.5 ms (14.25 V + 0.25 Ω source). A strict 3.00 A source latches FAULT at ARMED after 14 U5 drop-outs (fail-safe). Real adapters with brief overload headroom are expected to start it | A common ≥ 45 W adapter cannot start a full rack | TP1, TP26, TP19, TP10, TP9, TP5, TP7; current probe in the USB cable | The S1–S4 matrix in s8-single-board.md section 6 (cold start, PD hard reset, persistent short, repeated resets); log every attempt | S1: single attempt, rails good ≤ 250 ms after the first enable, ARMED ≤ 0.90 s, no V3V3/POR reset, no source restart. S2–S4 as in section 6. A strict-3 A fail-safe is recorded, never hidden | documented qualified-adapter list first; **respin** (rail sequencing) only if no common ≥ 45 W adapter starts the full load |
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
  - inside the U2 GND pour, the only other copper allowed is the single AGND_U2 link trace (3.3).
- **Board rules**:
  - copper to edge 1.0 mm (`min_copper_edge_clearance`, enforced by DRC);
  - courtyards ≥ 1.0 mm from Edge.Cuts, measured (closest now TP19, 1.28 mm);
  - every SMD pad ≥ 2.0 mm from the hand-soldered J1/D8/J2/J3 pads (closest now D8–Q6.3, 2.01 mm);
  - no via in an SMD pad (the only exception is the U4/U5 footprint exposed-pad thermal vias);
  - no zero-length, duplicate or dangling segments; track ends centred on pads and vias; 0.05/0.1 mm grid.

### 3.2 Net classes and widths

The project (`usb-power-45w-single.kicad_pro`) defines the classes below, all with 0.2 mm clearance and 0.6/0.3 mm
vias. The class width is KiCad's default for new tracks, not a DRC minimum. The contract minimums are measured after
routing (`min_widths`, PENDING).

| Class | Nets (project patterns) | Default width | Contract minimum (1 oz outer, ≤ 10 °C rise) | Notes |
| --- | --- | --- | --- | --- |
| Power | `GND`, `VPD`, `VBUS`, `MAIN_IN`, `VIN`, `P12_VOUT`, `+12V`, `-12V` | 1.0 mm | VBUS/VPD/MAIN_IN/VIN 2.5 mm (3 A, U5 limit 4.7 A); P12_VOUT/+12V 1.5 mm (2.95 A CC limit); −12V 0.8 mm (~1.5 A LMR38020 limit); pours preferred | ≤ 1 A per 0.3 mm via at layer changes: ≥ 4 vias on the input path and on P12_VOUT/+12V, ≥ 2 on −12V |
| Switch | U2 `SW1`, `SW2`; U4 `SW` | 1.0 mm | short F.Cu pours, no thin tracks, no vias | 3.4 / 3.5 |
| Sense | `P12_ISP`, `P12_ISN` | 0.2 mm (pair 0.2 / 0.2) | 0.2 mm coupled pair | 3.7 |
| Quiet | `AGND_U2`, U2 `FB`/`COMP`, `FB_N`, `EN_N`, `N_EN_*` | 0.3 mm | ≥ 0.25 mm | short, over solid In1, away from the switch nodes |
| Default | logic and status | 0.2 mm | 0.2 mm | never use it on a Power net |

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

- U4's ground pin and exposed pad are **`-12V`, not GND**. The footprint thermal vias land on the −12V area (In2 or
  B.Cu, ≥ 300 mm²); never put GND on the EP.
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
| U4 | LMR38020 EP = −12V | footprint thermal vias to a −12V area ≥ 300 mm² on In2 or B.Cu; no GND on the EP |
| U5 | TPS16630 EP = GND, ≤ 0.48 W | footprint thermal vias to In1 GND |

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

After every batch, check: DRC + parity, no via in an SMD pad, no track on In1, plane and area pieces, and a render of
the area.

### 3.11 Post-routing gate (before any CAM or export)

Measure and report the 13 PENDING items from `board-p1.json`:

- `thermal.U2.In1`
- `thermal.U2.PGND_vias`
- `thermal.U2.VIN_area`
- `thermal.U2.VOUT_area`
- `thermal.U2.B_Cu_GND`
- `thermal.R109.force_copper`
- `thermal.R109.sense_copper`
- `thermal.D10.copper`
- `thermal.U4.copper`
- `thermal.U5.copper`
- `kelvin.sense_routing`
- `ground.no_second_bridge_copper`
- `min_widths`

Also required: native DRC 0 / unconnected 0 / parity 0; no via in an SMD pad; In1 one piece with no tracks; every
In2/B.Cu area one piece; the 1 mm edge and 2 mm hand-solder distances measured. An item that is not met gets a routing
fix. If it cannot be fixed, report it as a rating change. It is never a silent pass.
