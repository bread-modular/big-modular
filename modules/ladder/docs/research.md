# LADDER research notes (S3 schematic, P2 placement)

## 1. Goal

User brief (2026-11-08): an **analog version of the modules/16bit polysynth ladder filter**
(`firmware/16bit/includes/audio/apps/polysynth/poly_filter.h`, `PolyFilter`), with the same
controls, using the classic transistor ladder.

- Knobs: **CUTOFF**, **RESONANCE**, **ENV TIME**, **DEPTH**, plus **CURVE** for the VCA.
- ENV TIME and DEPTH act on an envelope started by a **GATE** jack or a **MIDI** note; the
  envelope comes from the **ATtiny1616 DAC**.
- A **CV** jack fully bypasses the envelope.
- Audio comes in from outside (**AUDIO IN**); no oscillator.
- Two outputs: **FILTER OUT** (direct) and **VCA OUT** (through a vactrol VCA driven by the
  same envelope / CV).
- **RES CV** input modulates the resonance, no depth control.
- Scope of this step: **schematic only** (user, 2026-11-08). No placement, panel, routing,
  export or firmware yet.

Open choices from the proposal that the user did not answer; S1 took the recommended
defaults (section 6): LM13700 for the resonance CV, DEPTH also scales an external CV, no ENV
LED / ENV OUT, module name `ladder`.

**S2 (user, 2026-11-09): "Use a Vactrol for the resonance CV. It doesn't need to be
accurate."** The LM13700 OTA is replaced by a second vactrol (section 3.4).

**S3 / P1 (user, 2026-11-09): "Add THT components & placements. Get the maximum space on the
front panel. And give more space for the knobs. Our hats module is good example. BTW: Add env
automation recording features as well. Check ACID, Hat and other modules. Don't route yet."**
Envelope automation recording (REC button + LED, section 3.6) and the THT placement / 10HP
panel (section 7). Not routed.

## 2. What the 16bit PolyFilter does (the reference)

| 16bit (`PolyFilter`) | Value | Analog version |
|---|---|---|
| Cutoff | 55 Hz .. 17.6 kHz, exponential (8.32 octaves); the CC is inverted (CC 0 = open) | CUTOFF knob ~55 Hz .. ~17 kHz, **CW = open** (a panel knob should not be inverted) |
| Resonance | k = 0 .. 4.1, self-oscillates near the top | RES knob drives a vactrol: k = 0 .. ~7 (self-oscillation from ~k 4, near the top; the exact point depends on the vactrol) |
| Makeup | output x (1 + k): the passband stays at 0 dB at any resonance | Same transfer, done in the feedback path: H = (1 + k) L / (1 + k L) (section 3.4) |
| Envelope | one attack = release follower, 5 ms .. 2 s exponential, up while a note is held | ENV TIME knob read by the ATtiny1616, the same follower in firmware, out on the DAC |
| Depth | 0 .. +8.32 octaves over the cutoff | DEPTH knob 0 .. ~+8.1 octaves |
| Stages | 4 TPT one-poles, tanh on the input | Moog transistor ladder: 4 poles, the differential pair is the tanh |

## 3. Circuit (S2)

All analog parts run on +/-12 V (`+12V_F` / `-12V_F` behind B5819W series diodes); the
ATtiny1616, the TS5A23157 normal and the input pull-ups on +5V (HT7550-1).

### 3.1 Envelope and CV bypass

- **GATE** (J2): 100k / 47k into an MMBT3904 inverter (threshold ~2.2 V, 1N4148W clamp,
  22k pull-up) -> PB2 (the Bread Modular ENV gate pin), `PORT_INVEN` in firmware.
- **MIDI** (J1): the 8bit / ACID NPN front end with the JP1 protected/direct jumper, on +5V.
- **ENV TIME** (RV1, PA1) and **DEPTH** (RV2, PA7; S3: a knob read by the MCU, so REC can
  record it, section 3.6).
- **DAC** PA6 (VREF 4.34 V) = envelope x DEPTH -> R8 1k / C6 100n (1.6 kHz) -> `ENV_DAC` ->
  U4A buffer -> `ENV_BUF` (0 .. 4.35 V) -> the cutoff summer. The DAC is 8-bit, so firmware
  dithers between neighbouring codes on slow sweeps; the RC leaves ~1 mV of dither, ~0.003
  octave at full DEPTH. Scaling in firmware keeps the step size in octaves the same at any
  DEPTH (one code = 8.1 / 255 octave).
- **VCA envelope** (S3): the envelope without DEPTH, as 8-bit PWM on PB0 (TCA0 WO0, 78 kHz at
  20 MHz) -> R52 4.7k / C36 100n -> R53 4.7k / C37 100n (two 340 Hz poles, ~0.1 mV ripple,
  ~1 ms lag, far below the vactrol's own) -> `ENV_VCA`. Firmware caps the duty at 87 %
  (4.35 V) so the VCA sees the same full scale as a 5 V CV. The VCA keeps opening fully at
  any DEPTH, as before.
- **CV bypass** (as modules/acid at 5 V): J3 -> R9 15k / R10 100k (5.0 V -> 4.35 V = the DAC
  full scale), BAT54SW clamp to GND / +5V; J3's TN switch + R11 1M pull-up = `CV_SENSE`.
  - VCA: TS5A23157 SPDT, unpatched `VCA_ENV` = `ENV_VCA` (PWM envelope), patched `VCA_ENV` = CV
    (analog, no MCU in the path).
  - Cutoff: the MCU reads `CV_SENSE` (PA3) and the scaled CV (`CVIN_DIV`, PA2 ADC); patched,
    the DAC outputs CV x DEPTH instead of envelope x DEPTH. DEPTH therefore still scales an
    external CV (S1 behaviour), but the CV now reaches the cutoff sampled (firmware loop,
    several kHz) and through the 1.6 kHz DAC filter: fine for envelopes / LFOs, no audio-rate
    cutoff FM (S1/S2 passed the CV analog).
  - Negative CV clips at 0 V (unipolar, as ACID).

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
- U9A: C23 1u AC coupling (drops the ladder offset), x20.6 -> R47 1k (1206) -> **FILTER OUT**
  = IN x 1.03 in the passband.

### 3.3 Cutoff (CUTOFF + DEPTH -> expo)

- U4B inverting summer, Rf 100k: CUTOFF (RV3 on +5V) via 82k, envelope x DEPTH (`ENV_BUF`,
  S3; S2 had the DEPTH pot wiper here) via 75k, offset from -12V_F via 200k. V_S = 5.8..6.0 V with both at 0, CUTOFF adds -6.1 V
  (8.5 octaves), full DEPTH -5.8 V (8.1 octaves).
- D6 in the feedback clamps V_S at -0.6 V: CUTOFF + full DEPTH stops at ~31 kHz (ladder
  current ~1 mA) instead of running away.
- R16 3.9k / R17 100R divide by 40 (0.717 V per octave at V_S = 17.9 mV at the base).
- Expo: Q3 DMMT3904W. Q3A is the reference, held at I_REF = 5 V / 9.1k = 0.55 mA by U5A
  (C9 100p compensation, D7 so U5A can never reverse-bias the emitters, R19 4.7k); Q3B (base
  at GND) sinks the ladder tail: I = I_REF x exp(-V_B / VT).
- No tempco resistor: the sweep scales ~0.3 %/K like any uncompensated expo. It is a filter,
  not a V/oct oscillator.

### 3.4 Resonance and the (1 + k) makeup (vactrol, S2)

- **Feedback summer** U11B (the spare TL072 half of S1): inverting, Rf R38 4.7k (C21 100p),
  `LAD_DIF` through R36 3.3k and `AIN_BUF` (= -IN) through R37 68k:
  `FB_O` = -1.42 x (`LAD_DIF` - 0.0485 x IN). In the passband `LAD_DIF` = 0.0498 x IN, so the
  two cancel: only the difference between the ladder output and its dry passband level is
  fed back.
- C20 10u AC couples `FB_O` (no ladder / summer DC into the feedback base; <= 16 Hz into
  1k + R_LDR), then the LDR of the **resonance vactrol U12** (Chinese VTL5C type, THT, as the
  VCA's U10) feeds it into the A (feedback) base node `LFB` (R27 1k to LB0).
- Loop: y = L x (IN + k (IN - y)) -> **H = (1 + k) L / (1 + k L)**, the 16bit makeup; the dry
  level holds at any resonance.
- **k = 10 x 1.42 x 1k / (1k + R_LDR) ~ 14.3 x 1k / (1k + R_LDR)**: dark LDR (MOhm) k ~ 0,
  self-oscillation (k = 4) at R_LDR ~2.5k, bounded at k ~14 for R_LDR -> 0. The bound keeps
  the oscillation amplitude sane (6.5 Vpp at FILTER OUT at 100 Ohm, section 4).
- **LED driver** U7B (was the I_ABC converter): RES knob (RV4 on +12V_F) through R40 100k and
  RES CV (J5) through R41 47k mix passively at `RES_X` = 0.32 x knob + 0.68 x CV (knob full
  3.84 V; +5 V CV 3.4 V; RES CV input ~160k). U7B holds `RES_X` across the sense resistor R39
  330R in the LED loop: **I_LED = V(RES_X) / 330R**, knob full 11.6 mA, +5 V CV alone 10.3 mA.
  R42 100R in the op-amp output caps the LED at ~20 mA when U7B saturates (big positive CV).
  D10 anti-parallel to the LED keeps the loop closed near 0 V (as D9 in the VCA); D8 holds
  `RES_X` >= -0.6 V when a negative CV outweighs the knob (LED off).
- Not accurate, by brief: the self-oscillation point on the knob depends on the vactrol's
  R vs I_LED (no trimmer), and the vactrol lags (ms attack, tens to hundreds of ms decay), so
  RES CV is slow modulation, not audio rate.

### 3.5 Vactrol VCA with CURVE

- Bread Modular V2CA with CURVE, on the LOW/SVF driver (as modules/vca-mix): U9B holds the
  LED cathode node at `VCA_ENV` (S3: the PWM envelope or the CV, section 3.1);
  I_LED = VCA_ENV / (470R + CURVE). CURVE (RV5 50k rheostat,
  pin 3 open): CCW = 9.2 mA at full envelope (punchy), CW = ~85 uA (soft, as V2CA's CURVE).
- D9 1N4148W anti-parallel to the LED keeps the loop closed near 0 V.
- Audio: FILTER (U9A output) -> LDR -> R49 10k -> U11A (R50 10k) -> R51 1k -> **VCA OUT**.
  Gain -10k / (10k + R_LDR): inverted, as V2CA.
- The VCA envelope never passes through DEPTH, so the VCA always opens fully whatever DEPTH is.

### 3.6 Envelope automation recording (S3)

The modules/acid REC feature (modules/8bit crash recorder, shared
`opt/attiny1616-tools/lib/CvRecorder`), on the envelope knobs:

- **SW1 REC** (6 x 6 mm THT tact, PC2 internal pull-up) + **D11 REC LED** (3 mm THT, PC3,
  R54 1k, ~3 mA): the ACID pins, parts and panel pattern (LED right of the button).
- Firmware behaviour to port (not written yet): click = record **ENV TIME + DEPTH** for 4
  bars on MIDI clock (LED blinks), then the take loops (LED solid); the knobs are ignored for
  the first looped pass, then shift the whole recorded curve; click again for live knobs;
  MIDI Start rewinds. RAM only (lost at power-off). The recorded DEPTH also applies to a
  bypass CV.
- This is why DEPTH moved into the MCU: an analog DEPTH pot (S1/S2) cannot be played back.
  The recorder needs a running MIDI clock (as ACID); with GATE only, REC does nothing unless
  the firmware later derives a clock from the gate (open option).

## 4. ngspice check (`tools/sim_ladder.py`, models only)

2N3904 SPICE model for the DMMT3904W pairs, ideal rail-limited op amps, the resonance LDR as
a fixed resistor (R_LDR swept; the LED side is not modelled). Decks and logs in the ignored
`research/sim/`.

| V_S | Ladder current | Pole fc (-3 dB / 0.435) | Passband |
|---|---|---|---|
| +6.0 V (both knobs 0) | 1.74 uA | 54 Hz | 0.95 |
| +4.0 V | 12.0 uA | 379 Hz | 1.01 |
| +2.0 V | 82.5 uA | 2.6 kHz | 0.99 |
| 0 V | 565 uA | 15.8 kHz | 0.93 |
| -0.098 V (CUTOFF full) | 620 uA | 17.1 kHz | 0.92 |

Resonance, passband / peak:

| R_LDR (k) | V_S 5 V | V_S 2 V | V_S 0 V |
|---|---|---|---|
| 1M (0.01) | 1.00 / none | 0.99 / none | 0.93 / none |
| 10k (1.3) | 1.01 / 1.50 at 100 Hz | 1.01 / 1.50 at 1.8 kHz | 0.98 / 1.40 at 12 kHz |
| 5k (2.4) | 1.00 / 2.98 at 126 Hz | 1.01 / 3.11 at 2.2 kHz | 0.99 / 2.76 at 15 kHz |
| 3.3k (3.3) | 1.00 / 7.05 at 136 Hz | 1.01 / 8.20 at 2.5 kHz | 1.00 / 6.22 at 16 kHz |
| 2.7k (3.9) | 1.00 / 16.7 at 141 Hz | 1.01 / 26.9 at 2.6 kHz | 1.00 / 13.5 at 18 kHz |

Self-oscillation (V_S 2 V, kick then no input, 140..160 ms): none at 2.7k; 2.2k (k 4.5)
3.2 Vpp at FILTER OUT; 1.5k 5.2 Vpp; 1k 5.9 Vpp; 470R 6.3 Vpp; 100R 6.5 Vpp. The passband
stays flat with resonance (the makeup works), and the C20 AC coupling leaves the bottom of
the sweep resonant.

The passband falls ~0.6 dB at the top of the sweep (driver loading, real hFE).
Model results, not measurements; the prototype has to confirm the top-end level, the
vactrol's self-oscillation point on the knob and the expo range.

## 5. Parts and sourcing (live lookups 2026-11-08; S2 and S3 add no new SMD part numbers)

Every SMD part has `LCSC` / `MPN` / `Manufacturer` fields (`SOURCING` in
`tools/build_schematic.py`); THT jacks, pots, the two vactrols (U10 VCA, U12 resonance), the
REC button / LED (S3, hand-soldered as modules/acid) and the headers have none. S3's new SMD
parts (R52 / R53 4.7k, R54 1k, C36 / C37 100n) reuse Basic codes already on the board.
Basic: all 0603 resistors, C0G 20p / 100p, X7R 100n, 1u / 4.7u / 10u, B5819W, 1N4148W,
MMBT3904, TL072CDT. Extended (stock at lookup): DMMT3904W C155305 (4,082; 6 per board),
47n NP0 1206 C20617849 (2,000; 4 per board), HT7550-1
C16106 (183,520), ATTINY1616-MF C5227638 (240), TS5A23157DGSR C11133 (4,988), BAT54SWT1G
C78260 (44,781), ROHM ESR18 1k 1206 C2074262 (99,719). Stock is a dated observation.

DMMT3904W uses the stock `MMDT3904` body, renamed, with its pins re-numbered to the
DMMT3904W pin-out (Diodes DS30311 Rev. 15 p. 1: 1 B2, 2 B1, 3 C1, 4 E1, 5 E2, 6 C2); the
edit is recorded in `docs/schematic-symbols.json`.

## 6. Decisions and open items

- Resonance CV by a **second vactrol** (user, S2 2026-11-09; S1 had an LM13700). Removed:
  U8 LM13700 + C21/C22 decoupling, Q9, R43; R36-R42 and C20 re-used with new values / roles;
  added U12 (vactrol) and D10.
- **DEPTH scales an external CV too**: S1/S2 by an analog pot after the bypass switch; S3 in
  the MCU (CV read on PA2), so it can be recorded. Trade-off: no audio-rate cutoff FM from CV.
- **REC** records ENV TIME + DEPTH (S3, section 3.6); needs MIDI clock.
- **No ENV LED, no ENV OUT.** Easy to add (spare PA4 / PA5 / PB1 / PB4 / PB5 / PC0 / PC1).
- No self-oscillation trimmer: RES full = 11.6 mA LED; self-oscillation needs R_LDR <~2.5k,
  which a VTL5C-type cell normally reaches well below that current. Where on the knob it
  starts depends on the vactrol (by brief, not accurate).
- RES CV input impedance ~160k; +5 V CV alone ~10 mA LED (about the knob's full range).
- CV bypass is unipolar (0..5 V; negative clips at 0 V), as ACID.
- VCA OUT is inverted relative to FILTER OUT (V2CA stage).
- Panel: 10HP (section 7), not the 8HP estimate: room for the knobs and for ~135 SMD parts
  on B.
- Firmware not written (envelope follower, MIDI note on/off + GATE, ENV TIME curve, DEPTH
  scaling + DAC dither, PWM VCA envelope, CV bypass via PA2 / PA3, REC recorder).
- Next steps when asked: routing (manual divide and conquer, SMD groups onto the board),
  then export, then firmware.

## 7. Placement and panel (P2, 2026-11-09)

P2 (user, 2026-11-09): "move the power sockets to a side and move the sockets a bit down. Bring
the cut off line a bit down. It's too close to sockets." J10 went upright to the right edge, the
bottom jacks down 8.3 mm to Y110.3 and the whole knob grid (plus REC, vactrols, J11) down 5 mm, so
CUTOFF/RES sit 20 mm below the top jacks instead of 15 mm.

`docs/geometry.json` is the placement contract; `tools/build_layout.py` (modules/hats's
builder with the LADDER library, 10HP rail holes as modules/acid, 4 copper layers) writes
`hardware/ladder.kicad_pcb` and `panels/front-pcb/ladder-panel.kicad_pcb` from it and from
the native netlist. `panels/front-cad/` holds the FreeCAD printable alternative.

- **10HP** (50.5 x 128.5 mm), carrier 49.5 x 110 mm, 4 layers (F / In1 GND / In2 power / B;
  planes come with the routing), every assembled SMD on B.
- **Knobs** on a 30 x 27 mm grid (outer columns X10.25 / X40.25 as modules/acid, rows Y37 /
  Y64 / Y91): CUTOFF + RES, ENV TIME + DEPTH, REC button + LED + CURVE. Up to ~25 mm knobs fit
  (modules/hats' "room for the knobs", HATS rows are 34 mm apart on 6HP).
- **Jacks**: top MIDI, GATE, CV, RES CV (control inputs, Y17); bottom AUDIO IN, FILTER OUT,
  VCA OUT (Y110.3, on the knob columns + centre, VCA OUT under CURVE).
- **REC** button X8.0 + LED X15.5 at Y91, under ENV TIME (the free grid slot).
- **Vactrols** on B in the middle column between the knobs, upright: U12 (resonance) at Y41,
  U10 (VCA) at Y85. Unlike modules/low / acid / hats they are not under a pot, so there are no
  stacking DRC findings and no exclusions.
- **J10** upright on B at the right edge (modules/12bit), rot 180, in the gap between the DEPTH and
  CURVE courtyards (pads Y73.37..85.23 vs Y72.70 / Y85.86), pin 1 (-12 V) at the bottom, courtyard
  1.35 mm from the edge. A 16-pin socket overhangs upward to Y62.79 over the RV2 right lug and
  pin 3 (trim those leads to <= 2 mm, as on modules/12bit); a 10-pin socket covers no pot pad. **J11** UPDI on B at the left edge between CUTOFF and ENV TIME.
- Every SMD part is parked on B off the right edge (X56+), for group-by-group placement with
  the routing.

P2 check (2026-11-09, `research/p2-check/`): shared `kicad_tools.py check`: ERC 0, DRC 0
violations, parity 0, 294 unconnected (unrouted, expected); panel DRC 0; FreeCAD print rebuilt.
Courtyard-to-edge >= 1.1 mm for every placed part (bottom jacks J4/J6/J7 1.105 mm, J11 1.185 mm). No courtyard overlaps. The 2 mm SMD hand-solder
clearance applies once SMD parts move onto the board.
