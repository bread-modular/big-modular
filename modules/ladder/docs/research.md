# LADDER research notes (S5 schematic, P4 placement, R1 routing, fab-reviewed)

## 1. Goal

**S4 (user, 2026-11-15): "make this filter a MIDI less and pure analog one. We give audio & CV
inputs on the top and we get the output on the bottom. No VCA. We need a res & filter knobs.
These should be main pots. Need more space for that. We also can have a depth knob for the main
CV. Res CV doesn't need anything. I think we can make this a 6hp module. [...] No routing needed
for now."** And: **"I want a LED for the CV after the depth as well. [...] The default
brightness of LEDs placed in MCC is too bright. I had to do a firmware hack to make it lighter.
Try to do something electronically [...] it should cover whole CV and Depth range."**

- A classic 4-pole transistor ladder low-pass, analog from jack to jack: no MCU, no firmware.
- Knobs: **CUTOFF** and **RESONANCE** (the main knobs), **DEPTH** (attenuator of the CV input).
- Jacks: **IN**, **CV** (cutoff, through DEPTH), **RES CV** (no attenuator) on top; **OUT** at
  the bottom.
- **CV LEDs** after DEPTH, dim, linear over the whole CV x DEPTH range: one for positive, one
  for negative CV, brightness by solder jumpers (section 3.1).
- 6HP. Scope of this step: schematic, THT placement and panel. Not routed.

**S5 (user, 2026-11-15): "Can you add some solder jumpers to set the brightness level. Also add
another LED for the negative side too."** And: **"I don't mind using an OTA if that's a common
standard design which works out of the gate."** Read as: the resonance element. S5 swaps the
resonance vactrol for an LM13700 OTA (section 3.4), the usual way to voltage-control the
resonance of a transistor ladder; nothing else in the audio path changes.

History: S1 (2026-11-08) was an analog version of the modules/16bit polysynth ladder filter
(`PolyFilter`) with an ATtiny1616 envelope (GATE / MIDI, ENV TIME, DEPTH), a CV bypass and a
vactrol VCA with CURVE. S2 (2026-11-09) replaced the LM13700 resonance CV by a vactrol ("It
doesn't need to be accurate"). S3 (2026-11-09) added REC automation recording and the 10HP
panel; it was routed (R2) and exported, not built. S4 removes the MCU, MIDI, GATE, the
envelope, REC and the VCA; the ladder core, the expo converter, the resonance path and the
output stage are S3's, unchanged. S5 (2026-11-15) went back to the LM13700 for the resonance
(S1's choice) and added the negative CV LED and the brightness jumpers. The S3 / R2 sources and
export are in git history (commit `b32225b` and before).

## 2. What the 16bit PolyFilter does (the reference)

| 16bit (`PolyFilter`) | Value | Analog version |
|---|---|---|
| Cutoff | 55 Hz .. 17.6 kHz, exponential (8.32 octaves); the CC is inverted (CC 0 = open) | CUTOFF knob ~55 Hz .. ~17 kHz, **CW = open** (a panel knob should not be inverted) |
| Resonance | k = 0 .. 4.1, self-oscillates near the top | RES knob sets an OTA's gain: k = 0 .. ~7.7 (self-oscillation from k 4, at about 60 % of the travel) |
| Makeup | output x (1 + k): the passband stays at 0 dB at any resonance | Same transfer, done in the feedback path: H = (1 + k) L / (1 + k L) (section 3.4) |
| Envelope | one attack = release follower, 5 ms .. 2 s exponential, up while a note is held | None since S4: patch an envelope or LFO into **CV** |
| Depth | 0 .. +8.32 octaves over the cutoff | DEPTH knob: 0 .. +8.3 octaves for a 5 V CV |
| Stages | 4 TPT one-poles, tanh on the input | Moog transistor ladder: 4 poles, the differential pair is the tanh |

## 3. Circuit (S5)

Everything runs on +/-12 V (`+12V_F` / `-12V_F` behind B5819W series diodes). The HT7550-1
stays as the +5V reference of the CUTOFF knob, the RES knob and the expo current (load
~0.8 mA), so cutoff and resonance do not follow the +12 V rail.

### 3.1 CV input, DEPTH and the CV LEDs (S4, S5)

- **CV** (J3, DC coupled, bipolar, unpatched = GND through the jack switch) -> R9 39k -> the
  **DEPTH** pot RV2 (50k to GND, a plain attenuator) -> wiper `CV_W` -> U4A.
- R9 scales the CV to 0.56 at full DEPTH (0.51 .. 0.61 over the pot's +/-20 %). Reason: U4A is
  non-inverting, and a TL072 reverses its output phase when an input goes below its
  common-mode range (guaranteed to V- + 4 V = -7.6 V here). With R9 a +/-12 V mis-patch reaches
  only +/-6.7 V (+/-7.3 V with a +20 % pot). R9 also limits the current into an unpowered
  module to 0.3 mA. Input impedance 89k.
- **U4A is a follower with the two panel LEDs anti-parallel in its feedback path**: output ->
  LED -> `CV_S` -> inverting input. `CV_S` therefore equals `CV_W`, at low impedance, and feeds
  the cutoff summer through R14 47k. Everything `CV_S` sources flows through **D11 (positive
  CV)**, everything it sinks through **D12 (negative CV, S5)**: **I_LED = |V(CV_S)| x (1 / R14
  + the jumpered loads)**, proportional to CV x DEPTH from 0 V up, the same on both sides. No
  forward-voltage dead band (a resistor + LED on the buffer output would stay dark below
  ~1.7 V, more than half of the range) and no saturation. D12 replaces S4's 1N4148W D5; each
  LED sees the other one's forward voltage in reverse (2 .. 3.3 V, under the usual 5 V rating).
- **Brightness (S5: solder jumpers)**: the modules/mcc bank LEDs run at ~3 mA (1k from 5 V) and
  were too bright; the `cpx4_mcc` firmware dims them to 1 % duty (~30 uA average). With all
  jumpers open only R14 loads `CV_S`: 21 uA per volt = **0.06 mA at 5 V CV / DEPTH full**
  (1/50 of the MCC default, 2x the dimmed MCC level). **JP1 / JP2 / JP3** (open as shipped, on
  B) each add a load to GND: R6 47k, R7 22k, R8 10k.

  | JP1 | JP2 | JP3 | uA per volt at `CV_S` | LED at +/-5 V CV, DEPTH full | at +/-12 V |
  |---|---|---|---|---|---|
  | open | open | open | 21 | 0.06 mA | 0.14 mA |
  | closed | open | open | 43 | 0.12 mA | 0.29 mA |
  | open | closed | open | 67 | 0.19 mA | 0.45 mA |
  | closed | closed | open | 88 | 0.25 mA | 0.59 mA |
  | open | open | closed | 121 | 0.34 mA | 0.82 mA |
  | closed | open | closed | 143 | 0.40 mA | 0.96 mA |
  | open | closed | closed | 167 | 0.47 mA | 1.12 mA |
  | closed | closed | closed | 188 | 0.53 mA | 1.27 mA |

  The floor is R14 (it is the signal path); S4's fixed R11 68k (0.10 mA) is gone. U4A's output
  stays inside its swing (8.5 V at a 12 V CV with every jumper closed). D11 is the red 3 mm
  THT LED of modules/hats / mcc; D12 takes a second colour of the user's choice on the same
  footprint. One set of jumpers serves both LEDs, so two colours of different efficiency will
  not look equally bright.
- U4A offset (<= 10 mV) is 0.03 octave at the summer and < 2 uA in an LED even with every
  jumper closed (dark).

### 3.2 Ladder core

- Classic Moog ladder: driver pair Q4 + rungs Q5..Q8, each a **DMMT3904W** matched pair
  (2 mV VBE, 2 % hFE; one die pair per rung), 4 x **47n NP0** across the stages. Unit 1 of
  each pair is the **B (input) side**, unit 2 the **A (feedback) side**.
- Pole frequency fc = I / (8 pi VT C) ~ 3.3 Hz per uA: 55 Hz at 1.7 uA, 17.6 kHz at 0.55 mA.
- Base bias chain (R20..R25): +12V_F -> 4.7k -> LB4 7.4 V, 1.5k steps -> LB0 1.48 V
  (0.98 mA), each node bypassed with 10u. Every rung transistor gets ~1.47 V VCE; rung 4
  collects on +12V_F.
- Input: AUDIO IN -> U5B x -1 -> 200k / 1k into the B base (+/-25 mV for 10 Vpp: warm,
  ~7 % compression, not clipped). The A base has the matching 1k to LB0 and 200k to GND, so
  both bases sit at the same DC.
- The base resistors are 1k, not higher: the driver's input resistance (2 r_pi, ~20 kOhm at
  0.5 mA and hFE 100) would otherwise pull the passband down at the top of the sweep
  (4.7k cost 30 % in the first simulation).
- Output: U6A / U6B JFET followers on the top nodes (`LAD_B3` / `LAD_A3`, ~6.7 V common
  mode; the nodes are up to ~30 kOhm at the lowest cutoff), U7A difference amp x10:
  `LAD_DIF` = 10 x (B3 - A3) = 0.050 x IN in the passband, in phase.
- U9A: C23 1u AC coupling (drops the ladder offset), x20.6 -> R47 1k (1206) -> **OUT**
  = IN x 1.03 in the passband.

### 3.3 Cutoff (CUTOFF + CV -> expo)

- U4B inverting summer, Rf 100k: CUTOFF (RV3 on +5V) via 82k, CV x DEPTH (`CV_S`) via R14 47k,
  offset from -12V_F via 200k. V_S = 5.8..6.0 V with CUTOFF at 0 and no CV, CUTOFF adds -6.1 V
  (8.5 octaves), a 5 V CV at full DEPTH (2.81 V at `CV_S`) -6.0 V (8.3 octaves). A negative CV
  raises V_S and closes the filter; U4B saturating high only turns the expo off.
- D6 in the feedback clamps V_S at -0.6 V: CUTOFF + a large CV stops at ~31 kHz (ladder
  current ~1 mA) instead of running away.
- R16 3.9k / R17 100R divide by 40 (0.717 V per octave at V_S = 17.9 mV at the base).
- Expo: Q3 DMMT3904W. Q3A is the reference, held at I_REF = 5 V / 9.1k = 0.55 mA by U5A
  (C9 100p compensation, D7 so U5A can never reverse-bias the emitters, R19 4.7k); Q3B (base
  at GND) sinks the ladder tail: I = I_REF x exp(-V_B / VT).
- No tempco resistor: the sweep scales ~0.3 %/K like any uncompensated expo. It is a filter,
  not a V/oct oscillator.

### 3.4 Resonance and the (1 + k) makeup (LM13700 OTA, S5)

- **Feedback summer** U9B: inverting, Rf R38 4.7k (C21 100p), `LAD_DIF` through R36 3.3k and
  `AIN_BUF` (= -IN) through R37 68k: `FB_O` = -1.42 x (`LAD_DIF` - 0.0485 x IN). In the
  passband `LAD_DIF` = 0.0498 x IN, so the two cancel: only the difference between the ladder
  output and its dry passband level is fed back.
- C20 10u AC couples `FB_O` (1.4 Hz), R39 10k / R42 1k divide it by 11 into the + input of
  **U8A, one half of an LM13700** (- input: R43 1k to GND, so the input bias currents cancel).
  The OTA output current goes through C22 10u into the A (feedback) base node `LFB` (R27 1k to
  LB0); R48 100k is its DC path. C22 keeps the OTA's offset current (gm x V_os) off the ladder
  base, so the driver pair stays balanced at any resonance.
- Loop: y = L x (IN + k (IN - y)) -> **H = (1 + k) L / (1 + k L)**, the 16bit makeup; the dry
  level holds at any resonance.
- **k = 10 x 1.42 / 11 x gm x 0.99k, gm = I_ABC / 2 VT = 19.3 mS per mA: k = 25 x I_ABC [mA]**.
  Self-oscillation (k = 4) at ~0.17 mA. No linearizing diodes: the OTA input is +/-12 .. 20 mV
  in self-oscillation, so the ladder limits the amplitude first, as with a plain feedback
  resistor (6 .. 6.7 Vpp at OUT, section 4, even at 1 mA).
- **Bias current** (U7B + Q9 MMBT5401): the RES knob (RV4, on +5V) through R40 100k and RES CV
  (J5) through R41 100k sum in U7B's virtual ground: I_in = 10 uA per volt each. Q9's emitter
  sits on the T-network node `RES_E` = -I_in x R49 47k, and R50 9.1k adds V(`RES_E`) / 9.1k:
  **I_ABC = 6.16 x I_in**. Knob full 0.31 mA (k ~ 7.7), +5 V RES CV alone the same, knob full
  + 12 V CV 1.04 mA (LM13700 limit 2 mA); with U7B railed, R50 still holds it at ~1.2 mA.
  A negative sum turns Q9 off through D8 (k = 0). C7 100p compensates the loop. RES CV input
  impedance 100k.
- **Tolerance**: gm is 6700 .. 13000 uS at 0.5 mA in the data sheet (9600 typical), so
  self-oscillation starts between ~45 % and ~90 % of the knob, ~60 % typical; the full knob
  always reaches it. Against the vactrol (S2..S4): defined by resistors and one data-sheet
  parameter, no hand-soldered part, and RES CV works at audio rate.
- **Known OTA trait**: a fast, full-range RES CV step couples the OTA offset into the output
  as a short thump, ~0.25 .. 0.5 V for the typical 0.4 mV offset (up to ten times that at the
  4 mV limit), gone in ~0.1 s. Turning the knob does not do it (too slow).
- The second LM13700 half and both Darlington buffers are unused (inputs to GND, bias pin
  open).

### 3.5 Removed in S4 / S5

The ATtiny1616 envelope (GATE / MIDI in, ENV TIME, DAC, PWM VCA envelope), the TS5A23157 CV
bypass, REC button + LED, UPDI header, and the vactrol VCA with CURVE (U10, U11A) are gone.
Six op amps became five: the resonance summer moved from U11B to U9B, U4A became the CV
buffer / LED driver. S5 removed the resonance vactrol U12 with its LED driver parts (R39 330R,
R42 100R, D10; U7B is now the bias-current converter) and S4's D5 and R11.

## 4. ngspice check (`tools/sim_ladder.py`, models only)

2N3904 SPICE model for the DMMT3904W pairs, ideal rail-limited op amps, the LM13700 half as a
plain differential pair with ideal mirrors (gm = I_ABC / 2 VT), 2N3906 for the MMBT5401. Decks
and logs in the ignored `research/sim/`.

| V_S | Ladder current | Pole fc (-3 dB / 0.435) | Passband |
|---|---|---|---|
| +6.0 V (CUTOFF 0, no CV) | 1.74 uA | 55 Hz | 0.95 |
| +4.0 V | 12.0 uA | 379 Hz | 1.01 |
| +2.0 V | 82.5 uA | 2.6 kHz | 1.00 |
| 0 V | 565 uA | 15.8 kHz | 0.93 |
| -0.098 V (CUTOFF full) | 620 uA | 17.1 kHz | 0.93 |

Resonance, passband / peak:

| I_ABC (k) | V_S 5 V | V_S 2 V | V_S 0 V |
|---|---|---|---|
| 0 | 1.01 / none | 1.00 / none | 0.93 / none |
| 50 uA (1.2) | 0.99 / 1.46 at 96 Hz | 0.99 / 1.45 at 1.8 kHz | 0.96 / 1.35 at 12 kHz |
| 100 uA (2.5) | 0.98 / 3.41 at 126 Hz | 0.98 / 3.32 at 2.2 kHz | 0.96 / 2.91 at 15 kHz |
| 130 uA (3.2) | 0.98 / 7.26 at 136 Hz | 0.98 / 6.86 at 2.4 kHz | 0.97 / 5.50 at 16 kHz |
| 150 uA (3.7) | 0.98 / 17.2 at 141 Hz | 0.98 / 14.8 at 2.5 kHz | 0.97 / 10.4 at 17 kHz |

Self-oscillation at OUT (kick, then no input):

| I_ABC | V_S 5 V | V_S 2 V | V_S 0 V |
|---|---|---|---|
| 150 uA | none | none | none |
| 170 uA | 1.3 Vpp | 1.8 Vpp | none |
| 200 uA | 4.2 Vpp | 4.2 Vpp | 3.6 Vpp |
| 310 uA (knob full) | 6.0 Vpp | 6.1 Vpp | 6.0 Vpp |
| 1.04 mA (knob full + 12 V CV) | 6.6 Vpp | 6.7 Vpp | 6.7 Vpp |

The passband stays within 2 % with resonance (the makeup works). The OTA input reaches
38 .. 42 mVpp in self-oscillation. An OTA input offset of 0.4 / 4 mV leaves `LAD_DIF` at 0 mV
(C22) and puts 0.12 / 1.2 V at the OTA output at the self-oscillation point.

RES knob / RES CV -> I_ABC (U7B + Q9):

| Knob | RES CV | I_ABC | k |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 25 % | 0 | 70 uA | 1.7 |
| 50 % | 0 | 137 uA | 3.4 |
| 75 % | 0 | 211 uA | 5.2 |
| full | 0 | 307 uA | 7.6 |
| 0 | +5 V | 307 uA | 7.6 |
| 0 | -5 V | 0 | 0 |
| full | -2.5 V | 154 uA | 3.8 |
| full | +5 V / +12 V | 0.61 / 1.04 mA | 15 / 26 |

The passband falls ~0.6 dB at the top of the sweep (driver loading, real hFE).
CV x DEPTH buffer with the LEDs in its loop (jumpers open; generic red LED model, 1.8 V at
2 mA, for both):

| DEPTH | CV | `CV_S` | D11 / D12 | Cutoff shift |
|---|---|---|---|---|
| full | +1 V | 0.562 V | 12 uA / 0 | +1.7 oct |
| full | +5 V | 2.809 V | 60 uA / 0 | +8.3 oct |
| full | +10 V / +12 V | 5.62 / 6.74 V | 120 / 143 uA / 0 | (clamped by D6) |
| full | -1 V / -5 V / -12 V | -0.56 / -2.81 / -6.74 V | 0 / 12 / 60 / 143 uA | -1.7 / -8.3 oct / closed |
| half | +5 V | 1.404 V | 30 uA / 0 | +4.2 oct |
| 10 % | +5 V | 0.281 V | 6 uA / 0 | +0.8 oct |

The jumper steps are the table in section 3.1 (same run).

Model results, not measurements; the prototype has to confirm the top-end level, the
self-oscillation point on the knob, the expo range and the LED brightness.

## 5. Parts and sourcing (live lookups 2026-11-08; 39k and the S5 parts 2026-11-15)

Every assembled SMD part has `LCSC` / `MPN` / `Manufacturer` fields (`SOURCING` in
`tools/build_schematic.py`); the THT jacks, pots, the two CV LEDs, the power header and the
three solder jumpers (copper only) have none. S5: 108 parts, 95 assembled SMD in 30 BOM rows.
New in S5 (live lookup 2026-11-15): **LM13700MX/NOPB C174050** (TI, SOIC-16, Extended,
10,559 in stock), **MMBT5401 C8326** (CJ, SOT-23, Basic, 618,212; there is no Basic
MMBT3906), 22k 0603 C31850 (Basic). Basic: all 0603 resistors, C0G 20p / 100p, X7R 100n, 1u /
10u, B5819W, 1N4148W, TL072CDT, MMBT5401. Extended (stock at the 2026-11-08 lookup unless
noted): DMMT3904W C155305 (4,082; 6 per board), 47n NP0 1206 C20617849 (2,000; 4 per board),
HT7550-1 C16106 (183,520), ROHM ESR18 1k 1206 C2074262 (99,719), LM13700 (above). No longer
used: ATtiny1616, TS5A23157, BAT54SW, MMBT3904, 330R, the VTL5C vactrol. Stock is a dated
observation.

DMMT3904W uses the stock `MMDT3904` body, renamed, with its pins re-numbered to the
DMMT3904W pin-out (Diodes DS30311 Rev. 15 p. 1: 1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2); the
edit is recorded in `docs/schematic-symbols.json`. LM13700, `Q_PNP_BEC` (MMBT5401: 1 B, 2 E,
3 C) and `SolderJumper_2_Open` are stock symbols, unedited.

## 6. Decisions and open items

- **CV is analog and bipolar** (S4): positive opens, negative closes; audio-rate cutoff FM
  works again (S3 sampled the CV in the MCU).
- **Two CV LEDs** (S5): D11 positive, D12 negative, one current law for both.
- **LED brightness by solder jumpers** (S5): shipped open = dimmest (0.06 mA at 5 V CV / DEPTH
  full); 8 steps up to 0.53 mA. The right step for the user's LEDs is a bench decision.
- **Resonance by OTA** (S5), read from "I don't mind using an OTA if that's a common standard
  design"; the user saw the S5 report with that reading stated and answered "this looks good.
  Do the routing too" (2026-11-15). The vactrol resonance block is S3's (commit `b32225b`;
  S4's uncommitted sources are copied in the ignored `research/s4-backup/`).
- **DEPTH is a passive attenuator before the buffer**; its full-scale gain follows the pot's
  +/-20 % tolerance (7.5 .. 9.0 octaves for 5 V).
- No self-oscillation trimmer: the knob's full range is 1.8x the typical self-oscillation
  current and 1.15x the worst case (minimum gm at the top of the sweep).
- No OTA offset trimmer: C22 keeps the offset off the ladder; fast RES CV steps thump
  (section 3.4).
- RES CV input impedance 100k; +5 V CV alone = the knob's full range.
- The +5V regulator stays for the CUTOFF / RES / expo reference (HT7550-1, Extended).
- Refs keep their S3 numbers (gaps where parts were removed); S5 reuses R39 / R42 / D8 in the
  resonance block and adds R6..R8, R43, R48..R50, C5..C7, C22, D12, JP1..JP3, Q9, U8.
- Layer count: **4 layers kept for R1** (In1 GND, In2 +12V_F). The parts are spread over the
  whole 110 mm between the jacks and pots, so eight nets cross the board; on F they run over a
  solid GND plane, shielded from the SMD side. 2 layers were not tried.
- Fab review done 2026-11-15 (section 9). Next steps when asked: JLCPCB export, bench test.

## 7. Placement and panel (P4, 2026-11-15)

`docs/geometry.json` is the placement contract; `tools/build_layout.py` (modules/hats's
builder with the LADDER library) writes `hardware/ladder.kicad_pcb` and
`panels/front-pcb/ladder-panel.kicad_pcb` from it and from the native netlist.
`panels/front-cad/` holds the FreeCAD printable alternative.

- **6HP** (30.0 x 128.5 mm, rail holes at X12.58 as modules/hats), carrier 29 x 110 mm, every
  assembled SMD on B. 6HP takes two jacks, or a jack and a pot, per row.
- **Row 1 (Y17.5)**: IN (X7.95), RES CV (X22.05).
- **Row 2 (Y35.0)**: CV jack (X7.95) with its **DEPTH** knob beside it (X22.05). The two **CV
  LEDs** sit under DEPTH at Y46.5, 5.5 mm apart around its column: D12 (negative) at X19.3,
  D11 (positive) at X24.8, marked `-` and `+` on the panel.
- **CUTOFF** (Y64.0) and **RES** (Y90.0) alone on the centre line X15.0, 26 mm apart: each
  takes a knob up to ~22 mm across. The nearer LED is 18.0 mm from the CUTOFF shaft.
- **OUT** on the centre line at Y110.4.
- No vactrol since S5: the 12.25 mm between the CUTOFF and RES pot courtyards is free on B.
- **J10** upright on B at the right edge beside OUT (as modules/8bit / 12bit), pin 1 (-12 V) at
  the bottom. A 16-pin socket overhangs upward to Y92.79 and covers no pot or jack pad.
- Every SMD part (95 assembled + the 3 solder jumpers) is parked on B off the right edge
  (X36+), for group-by-group placement with the routing. JP1..JP3 belong on B where an iron
  reaches them with the module in hand.

P4 check (2026-11-15, `research/p4-check/`, `research/s5/measure.py`): shared
`kicad_tools.py check`: ERC 0, DRC 0 violations, parity 0, 230 unconnected (unrouted,
expected); panel DRC 0, 11 holes; FreeCAD print rebuilt. Courtyard-to-edge >= 1.02 mm for every
placed part (RV2 1.02 mm right, J6 1.03 mm bottom). No courtyard overlaps (0.56 mm between the
two LED courtyards); closest THT pads of different parts: D11 to D12 1.16 mm, either LED to
the DEPTH pot pins 2.20 mm. The 2 mm SMD hand-solder clearance applies once SMD parts move onto
the board.

## 8. Routing (R1, 2026-11-15)

User: "Okay. Go this looks good. Do the routing too." Manual divide and conquer straight on
`hardware/ladder.kicad_pcb` (root `AGENTS.md`): no autorouter, explicit placements and
polylines per group, a single-connection path finder for two links (CV_O between the LEDs,
FILT_OUT to the jack), native DRC + parity after every stage. The stage scripts and the helper
with the exact clearance / via / edge checks are in the ignored `research/route/` (`lib.py`,
`s00_setup.py` .. `s08_silk.py`, snapshots in `snap/`, reports in `drc/`).

**Layers**: F signal, In1 solid GND, In2 +12V_F plane, B signal. Every SMD part and the three
solder jumpers are on B; F holds only the THT parts, so it carries the long north-south runs
above the GND plane. No tracks on In1 / In2. Vias 0.6 / 0.3 mm, none in or at an SMD pad.
Widths: 0.2 mm under the SOT-363 pairs (base and pole runs), 0.25 mm signals, 0.3 mm +5V,
0.4 mm rails and decoupling, 0.5 mm at the power entry.

**Groups, top to bottom** (panel-frame coordinates, B side):

| Group | Parts | Where |
|---|---|---|
| Input buffer + expo converter | U5, Q3, D7, R16..R19, R30, R31, C9, C19, C26, C27 | between the IN and RES CV jacks |
| CV in | R9 | above DEPTH |
| CV buffer + LEDs loop, cutoff summer | U4, R12..R15, C8, D6, C24, C25 | between the CV jack and the LEDs |
| Ladder core | Q4..Q8 in one row at Y57.4, 47n pole caps C10..C13 between the pairs, base chain R20..R24 + C15..C18 above, driver R25..R29 + C14 at the right | between the LEDs and CUTOFF |
| Top followers + difference amp | U6, U7 (half A), R32..R35, C28..C31 | left of CUTOFF |
| LED brightness steps | R6..R8, JP1..JP3 | right of CUTOFF |
| Resonance bias converter | U7 (half B), Q9, R40, R41, R49, R50, C7, D8 | between CUTOFF and RES |
| OTA | U8, R39, R42, R43, R48, C5, C6, C20, C22 | right, between the pots |
| +5 V reference | U1, C3, C4 | right of RES |
| Output stage + feedback summer | U9, R36..R38, R44..R47, C21, C23, C32, C33 | left of OUT |
| Power entry | D1, D2, C1, C2 | left of J10 |

**Cross-board links** (stage 7). F runs north-south, B bridges east-west where the pot and jack
zones are empty on B:

- **-12V_F** (200 mm of 0.4 mm track, 9 vias): D2 / C2 -> between the OUT jack tip and switch
  pads -> U9 -> up the left edge past U7 and U6 -> around the CV jack -> U5, with a branch
  between the CV jack and DEPTH down to U4; U8 over a B bridge above the RES pot (Y85.9).
  About 0.2 ohm end to end at 35 um, for a few mA per op-amp.
- **+5V** (0.3 mm): U1 -> RES pot -> CUTOFF pot -> R18, down the middle.
- **AIN_BUF** (130 mm): U5 -> between the DEPTH lugs -> right lane past the LEDs -> R28 ->
  right strip -> B bridge below the RES pot (Y99.7) -> R37.
- **LTAIL** (43 mm): expo pair Q3 -> between the DEPTH lugs -> right lane -> Q4. It runs beside
  AIN_BUF for 12 mm at 0.65 mm pitch over the GND plane; estimate (not measured) < 0.3 pF
  between them, about 80 nA into the tail node for 10 Vpp at 10 kHz, against 0.6 uA of tail
  current at a 20 Hz cutoff and 30 uA at 1 kHz. A bench check item, not a known fault.
- **RES_CV** (85 mm, 3 vias): jack -> right of the jack -> B bridge under DEPTH and below the
  CV jack (Y37.6 -> Y43.3) -> left strip -> R41.
- **CUT_S**, **LFB**, **FB_O**: one F run each (FB_O loops below the -12V_F via at C2).

**Changes to earlier stages during stage 7**, each re-run from its snapshot: R15 moved from the
left edge to under R14 (its -12V_F end joins U4.4), CV_TOP moved from B to F (frees the B
bridge under DEPTH), LFB on F shifted to X25.2 and the LTAIL via to above Q4.4 (frees the right
lane for two tracks), R39 / R42 0.3 mm left (room for the FB_O via beside C20), U1 / C3 / C4
0.1 mm down and C23 / R44 up (two courtyard overlaps and one 0.175 mm via-to-pad clearance
found by DRC after stage 6).

**B silk**: `LADDER R1`, `-12V` at J10, `LED` with `1` `2` `3` at JP1..JP3. No reference
designators (as the other modules).

**Checks (2026-11-15)**:

- Shared `kicad_tools.py check` (`research/r1-check/`): ERC 0; DRC 0 violations, 0 unconnected,
  parity 0; no exclusions, no ignored severities.
- Saved plane fills: the stage snapshots were filled without the project file (0.5 mm default
  edge pull-back), which DRC `--refill-zones` hides; stage 9 refilled the planes in place with
  the project's 1.0 mm rule. Native DRC on the saved fills (no refill): 0.
- Independent pad-net compare, board against the native netlist: 301 pins, 108 refs, 71 nets,
  0 differences (values and footprints too).
- `research/route/audit.py`: 521 tracks (107 F, 414 B; 644 mm / 613 mm) and 81 vias; no track
  on In1 / In2; no zero-length or duplicate segment; closest via to an SMD pad 0.16 mm (LFB
  via beside R29.1, same net), none in a pad; In2 one piece; In1 one piece plus 7 fragments of
  1..3.3 mm2 tied by spokes between the GND pads of J10 and of the IN / CV / RES CV jacks.
- SMD pad to pot / jack pad: closest 2.015 mm (R42.1 to the right RES lug); to the LED pads
  2.025 mm (R29.2 to D11).
- Courtyard to edge: closest RV2 1.015 mm incl. line width (the audit prints 0.995 because
  pcbnew's courtyard box is 0.02 mm larger and it measures to the edge centre line); every
  other part further in. Copper-edge rule 1.0 mm in native DRC.
- Fab review: section 9. Not done: JLCPCB export, bench test.

## 9. Fab review (R1, 2026-11-15)

User: "Yeah. Do the Fab review." The review measured the R1 board (`research/fab/review.py`:
board setup, silk sizes, drill table, routed pin-to-cap lengths, hand-solder distances, via /
pad / edge distances, mask and paste, footprint attributes, plane fills, track hygiene), read
the native netlist pin by pin (`research/fab/dump.py`) and ran a trial export into the ignored
`research/fab/export-trial/` (not the fabrication export). The two edits were written straight
on the board (`research/fab/fab_r1.py`), followed by the shared check.

Fixed (no copper, no placement change, so the board stays R1):

- **B silk texts 1.0 mm high, 0.15 mm stroke** (JLCPCB legend minimum; they were 0.8 mm):
  `LADDER R1`, `-12V`, `LED`, `1` `2` `3`. Closest pad 0.52 mm (`1` to R6), 1.4 mm to the edge.
- **Stackup recorded**: JLC04161H-7628 (1.6 mm, 1 oz outer / 0.5 oz inner), the block
  modules/hats carries. The S3 board had it; the S4 rebuild by `tools/build_layout.py` lost it.
- Title block: date, `fab-reviewed 2026-11-15` in the comment.

Checked, no finding:

- Shared check ERC 0, DRC 0, unconnected 0, parity 0, no exclusions, no ignored severities;
  native DRC on the saved fills (no refill) 0; saved plane fills equal a fresh refill.
- Pin-outs against the netlist: LM13700 (1 bias, 3 / 4 inputs, 5 output, 6 V-, 11 V+; unused
  half: inputs on GND, bias open), HT7550-1 SOT-89 (1 GND, 2 / tab VIN, 3 VOUT), MMBT5401
  (1 B, 2 E, 3 C), TL072, J10 (1 / 2 -12 V at the bottom, 3..8 GND, 9 / 10 +12 V), D1 / D2
  direction, D11 anode on the U4A output. **DMMT3904W re-read from the datasheet drawing**
  (DS30311 p. 1, top view: 1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2): equal to the symbol.
- Pots: pin 3 is the clockwise end on all three (CUTOFF and RES on +5V, DEPTH on the CV).
- Drills: vias 0.6 / 0.3 mm (81), LEDs 0.9, pins 1.0, jack slots 0.6 x 1.6, pot lug slots
  1.1 x 2.3; smallest annular ring 0.15 mm (vias), closest hole walls 0.38 mm; no NPTH.
- Vias tented, none within 0.6 mm of a hand-soldered pad; mask webs >= 0.18 mm; no paste on
  the solder jumpers or THT pads; JP1..JP3 out of BOM and CPL.
- Tracks: no dangling end (ten T-joints on a track centre line), three ends 0.05 mm off a pad
  centre, off-grid ends only at SOT-363 / SOT-23 pad centres. Copper >= 1.0 mm from the edge
  (closest SMD pad 1.30 mm, track 1.18 mm).
- Panel against the carrier: every hole coaxial with its part (jacks 6.2, pots 7.2, LEDs 3.2,
  rail holes 3.2 mm), `-` over D12 and `+` over D11, labels 1.2 mm high.
- Trial export: 95 placements in 30 BOM rows, all bottom side, every row with an LCSC code;
  the 9 THT refs and JP1..JP3 excluded; 4 copper layers, PTH drill file with 18 routed slots.

Judged and kept for the first prototype (not waived):

- U8 bypass caps C5 / C6: 5.9 mm routed from pins 11 / 6 (the TL072s: 1.9 .. 2.7 mm). The
  LM13700 is a 2 MHz part driven at audio rate.
- U1 input cap C3: 4.6 mm away, joined through the In2 plane (one via each); output cap C4
  2.5 mm routed.
- Nine SMD pads closer than 2 mm to J10 pins (closest C1 / C2 at 1.63 mm). J10 sits on B and is
  soldered on F, where there is no SMD part: no iron comes near them.
- Stock footprint silk outlines are 0.12 mm wide (JLCPCB asks 0.15 mm), as on every other
  module: cosmetic.
- The LFB via 0.16 mm beside R29 pad 1: same net, tented, clear of the pad and its mask.
- No test points: probe at the jacks and IC pins.

Sourcing (live `assembly.py lookup --strict-live`, 2026-11-15 13:31 UTC; stock is a dated
observation): all Economic-eligible. **DMMT3904W C155305: 684 in stock** (4,082 on
2026-11-08; 6 per board), 47n NP0 C20617849 1,661 (4 per board), LM13700MX C174050 10,529,
ESR18 1k C2074262 99,501: these four are plain Extended. HT7550-1 C16106 is Preferred Extended
(175,552), TL072CDT C6961 and MMBT5401 C8326 are Basic.

Result (`research/fab/check-post/`, `research/fab/review-final.txt`): ERC 0, DRC 0,
unconnected 0, parity 0; 521 tracks / 81 vias as R1. Not done: the JLCPCB export, JLCPCB's
placement preview and DFM, any build.
