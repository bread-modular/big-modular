# VCA-MIX module research

Status: **S6 schematic + P6 placement (8HP) + R3 manual routing, fab-reviewed and exported
for JLCPCB (2026-11-14)**. User
direction 2026-11-14: "change this to an 8HP board" and "add another potentiometer to change
the range: at 0 it's like with the 330R, a 50k pot adds resistance to the path, maybe with a
10k in parallel to reduce the range". S6 adds a RANGE pot per channel (section 3.2); P6 is
the 8HP layout with the VOL knobs alone in the right column (section 4); R2 is routed by
hand on a 4-layer carrier (section 4.1) and R3 adds the fab-review fixes (section 4.2):
ERC 0, 0 unconnected, parity 0, native DRC 0 active findings; the **15
vactrol-under-VOL-pot stacking items are user-approved per-item exclusions (D10,
2026-11-14)**. Both 8HP panels (FR4 and printed) are regenerated and the nominal 3D fit is
0 mm³. **`jlcpcb/` holds the S6 / P6 / R3 export** (shared exporter, bottom Economic, 88
parts / 17 rows): complete and matched, not supplier-accepted. Nothing is built or
bench-tested.

History (all review feedback): **S2** (2026-10-19) renamed IMIX to VCA-MIX, put the
volume after each VCA with OUT following it, replaced the V2CA LED drive with the
Bread Modular LOW/SVF vactrol driver and moved the vactrols to B on the unchanged BM
VTL5C footprint. **S3/P3** made each channel one panel row with its vactrol behind its
pot (BM SVF style). **S4/P4** (2026-10-20) buffers the audio input and the CV
(inverting, as modules/imix and modules/8bit), drives OUT and MIX through 1 W 2512 1k
resistors (modules/imix R18), moves to Basic TL072 duals (three per channel row, one
for the mix) and puts each VOL knob right **below** its IN/CV/OUT jacks. **R1** routes
P4 (section 4.1). **S5** (2026-11-13, user direction: "CV scaled down to 3.3 V, the same
setup as ACID; audio stays on ±12 V") replaces the ±12 V inverting CV buffer and
negative-referenced driver with the modules/acid CV pipeline on a new +3V3 rail
(divider, BAT54SW clamp, MCP6002 follower, 1M/1M, MCP6002 driver); schematic only. **S6/P5/R1**
(2026-11-14, user direction) adds the RANGE pot (the Bread Modular V2CA CURVE rheostat with
10k across it) in each sense leg, widens the module to 8HP and replaces the S4 TraceMaker
board (6HP, 2 layers, never updated to S5) with a hand-routed 4-layer one. **P6/R2**
(2026-11-14, user direction after the 3D view: "volume knobs are used all the time, we
rarely turn the range knob") moves each OUT jack under its CV jack and the MIX jack under
the last RANGE knob, so the three VOL knobs stand alone in the right column with no patched
cable over them; the board was placed and routed again by hand (the P5 / R1 board is gone).
**R3** (2026-11-14, user: "Those DRC issues are fine. Also fine for extended parts. Do the
JLC export and fab readiness") is the fab review of R2, the D10 exclusions and the export.

## 1. Goal

- 8HP Eurorack module (6HP until S5) with **three channels**. Each channel has a **vactrol VCA**
  (Bread Modular V2CA circuit) with three TS jacks: **IN** (audio), **CV** and
  **OUT**.
- S2..S5 had no CURVE knob; **S6 brings it back as RANGE** (section 3.2). At 0 the VCA has V2CA's **CURVE 0** response (the
  punchy one).
- A **volume pot after each VCA** sets the channel level. The per-channel **OUT**
  follows the pot, and all three post-volume channels sum into a **MIX** output
  (the Bread Modular imix mixer).
- The CV drives the vactrol LED through a **vactrol driver** (Bread Modular LOW /
  SVF), so the LED current follows the CV from 0 V with no LED-threshold dead zone.
- With no CV plugged in, a channel's VCA is fully open, so VCA-MIX also works as a
  plain 3-channel mixer.
- Audio inputs and CV inputs are buffered; OUT and MIX are driven through protected
  1 W series resistors, as on our imix and 8bit modules.
- Hand-soldered parts (jacks, pots, vactrols, power header) follow the MIDI module:
  QingPu PJ301M-12 jacks and the Bread Modular pots (Song Huei R0904N 50k tall
  trimmer, `Potentiometer_RV09` footprint) on F, the Chinese
  vactrols on B with the Bread Modular VTL5C footprint (as Bread Modular mounts
  them), all SMD on B for JLCPCB assembly.
- Eurorack ±12 V through a 10-pin header that also takes a 16-pin IDC cable.

## 2. Bread Modular baseline (read-only source)

Netlists were exported with `kicad-cli sch export netlist` into the ignored
`research/bm-ref/` from `~/data/projects/bread-modular/modules/{v2ca,imix,low,svf}`
(BM checkout `a960b19`, not modified).

### 2.1 V2CA 1.0.1: one channel

```
V_IN -> U5A follower -> VTL5C LDR (U1.4-U1.3) -> R3 10k -> U2A(-), R4 10k feedback, U2A(+) = 2.5 V
        U2A out -> R2 1k -> V_OUT                              (gain = -10k / (10k + R_LDR))
CV_IN -> U4A follower -> RV1 50k CURVE (rheostat, pins 1-2) -> R1 330R -> VTL5C LED (U1.2 -> U1.1 = GND)
```

- The supply is a single 5 V rail (MCP6002), with a 2.5 V mid-rail from R5/R6.
- **CURVE** is a rheostat in series with the LED. At **CURVE 0 (0 Ω)** only the
  330 R limits the LED current, which gives the fastest and strongest ("punchiest")
  response. VCA-MIX removes RV1. Its LED drive is the LOW/SVF driver (2.3) with the
  same 330 R as its sense resistor: about 4-4.5 mA at 5 V CV in S5 (V2CA: ~9 mA;
  S4: 7.7 mA), starting at 0 V instead of at the LED threshold.
- The V2CA output is inverted (one inverting stage).
- The footprint is `BreadModular_MISC:VTL5C`: LED pads at one end, LDR pads at the
  other, 12.7 mm apart.

### 2.2 imix 2.0.0: the mixer (BM's own imix, 4 channels)

```
IN_n -> 22k -> inverting buffer (22k || 100p) -> 100R -> RV 50k (pin 3; pin 1 = V_MID) -> wiper
wipers -> 22k each -> sum (22k || 100p) -> 1k -> MIXOUT
```

The BM CHANGELOG says this version brought inverting buffered inputs for less noise
pickup. VCA-MIX follows our ±12 V port of it (`modules/imix`): 100k inverting input
buffers, a 100k summer and a 1 W 2512 1k output resistor.

### 2.3 LOW and SVF: the vactrol driver

```
LOW: CV (1M pull-down) -> U5B follower -> R3/R4 1M/1M -> U5A(+)
     U5A out -> VAC_POS (LED anodes) ; VAC_NEG (LED cathodes) -> U5A(-) and RV1 50k rheostat + 330R -> GND
SVF: CV (100k pull-up normal) -> RV2 1M attenuator -> U5A follower -> R15/R16 1M/1M -> U5B(+)
     U5B out -> VACTROL_POS ; VACTROL_NEG -> U5B(-) and RV3 50k rheostat + R17 5.1k -> GND
```

The LED sits **inside the op amp's feedback loop**. The op amp raises its output
until the cathode node equals its + input, so I_LED = V(+) / R_sense whatever the
LED's forward voltage is. The current is proportional to CV from 0 V; V2CA's
~2 V dead zone (the LED threshold with a plain series resistor) disappears.
VCA-MIX uses this circuit with a fixed 330 R sense resistor (the rheostats are
trims/ranges on LOW/SVF and are not needed here). S4 fed it from an inverting ±12 V CV
buffer (gain -0.51) with the LED loop referenced to a negative voltage. **S5 uses the
BM SVF / modules/acid circuit as it is**, on +3V3 with the 1M/1M divider (section 3.2).

modules/acid (our 3.3 V port of BM SVF, the reference for S5):

```
CV jack -> R21 47k -> node (R22 100k || FREQ 1M to GND, D8 BAT54SW to GND / +3V3)   5 V -> 3.3 V
FREQ wiper -> U9A MCP6002 follower -> R35/R36 1M/1M -> U9B(+)                       <= 1.65 V
U9B out -> LED anodes ; LED cathodes -> U9B(-) and CURVE 50k + R37 5.1k -> GND
```

The BM boards mount the VTL5C vactrols on **B** (body behind the board, leads
soldered on F), beside the pots (V2CA U1/U3, LOW U1/U3, SVF U1/U2). All three
use the same `BreadModular_MISC:VTL5C` footprint with a 10.16 x 15.24 mm body
outline.

## 3. Circuit (S6)

### 3.1 What changed from Bread Modular, and why

| Item | Bread Modular | VCA-MIX | Why |
|---|---|---|---|
| Supply | 5 V single rail, 2.5 V reference | audio: ±12 V Eurorack, GND reference; **CV: +3V3** (HT7533-1 from +12 V) | Eurorack audio levels (±5 V); the CV runs on the modules/acid 3.3 V pipeline (S5) |
| Op amp | MCP6002 (6 V max) | audio: **TL072CDT** dual (±18 V), 7 per board; CV: **MCP6002** on +3V3, one per channel | ±12 V audio rails, TL072 Basic at JLCPCB; the CV op amp is the modules/acid part. Three duals per channel row keep each row self-contained |
| Audio input | follower (V2CA) / 22k inverting (imix) | **100k/100k inverting buffer** (∥ 20p) | 100k Eurorack input impedance (modules/imix); the inversion cancels the VCA stage's, so OUT has the input polarity |
| CV input | follower | **51k / 100k divider (5 V -> 3.31 V), BAT54SW clamp to GND / +3V3, MCP6002 follower** | S5: modules/acid R21/R22/D8/U9A. 151k input impedance; the clamp protects the 3.3 V op amp from ±12 V patching |
| CURVE | 50k rheostat + 330R | **back as RANGE n (S6)**: 330R + 50k rheostat ∥ 10k | user direction 2026-11-14: at 0 it is the punchy 330R response, the knob adds sense resistance; 10k across the pot limits it to 8.33k |
| LED drive | V2CA: follower -> 330R -> LED (dead zone below V_F ≈ 2 V) | **LOW/SVF vactrol driver on +3V3**: 1M/1M (CV / 2) -> MCP6002, LED in the loop, 330R + RANGE sense to GND | review: map the whole CV range onto the vactrol, no dead zone; S5: the modules/acid R35/R36/U9B circuit |
| Negative CV | not possible on 5 V | clamped to about -0.3 V by the BAT54SW: LED off | S5: the LED is never reverse-biased, so S4's anti-parallel 1N4148W is gone |
| CV unpatched | 0 V (VCA closed) | **TN normal to +12 V via 200k** (divider node 3.30 V = full scale, VCA open) | brief: works as a mixer with no CV |
| Volume | imix: before the mix only | **after the VCA, buffered; OUT follows it** | review: the pot sets the channel level |
| Outputs | 1k (imix) | **1k 1 W 2512** on every OUT and MIX | review: match modules/imix R18; survives a -12 V source patched into an output at +10.5 V (22.5 V² / 1k ≈ 0.51 W) |
| Mix out | sum stage only | 100k summer + **100k/100k inverter** | the channel signal is already non-inverted, so one extra inversion keeps MIX in phase |
| Power entry | 5 V header | 2x5 Eurorack header, B5819W series diode per rail | reverse-cable protection |

### 3.2 One channel (n = 1..3)

Three dual op amps per channel, all in the channel's row on the board (section 4):

| Op amp | Section A (pins 1-3) | Section B (pins 5-7) |
|---|---|---|
| Un01 TL072 | input buffer | VCA stage |
| Un02 **MCP6002** (+3V3 / GND) | vactrol driver | CV follower |
| Un03 TL072 | volume follower | spare (grounded follower) |

Un04 is the vactrol.

```
IN n  (J1/J4/J7 tip; TN = GND) -> Rn01 100k -> Un01A(-) ; Rn02 100k || Cn01 20p ; (+) = GND -> BUFn = -IN
BUFn -> LDR (Un04 pins 4-3) -> Rn03 10k -> Un01B(-) ; Rn04 10k feedback ; (+) = GND -> VCAn
VCAn -> Rn10 100R -> RVn pin 3 ; pin 1 = GND ; wiper VOLWn -> Un03A(+) ; Un03A(-) = out = CHOn
CHOn -> Rn05 1k 1 W 2512 -> OUT n (J3/J6/J9 tip)
CHOn -> Rn11 100k -> SUM
CV n (J2/J5/J8 tip) -> Rn08 51k -> CVDn ; Rn06 100k -> GND ; Dn01 BAT54SW: GND -|>- CVDn -|>- +3V3
TN (CVNn) -> Rn07 200k -> +12V                      (no plug: TN joins the tip, CV normalled to +12 V)
CVDn -> Un02B(+) ; Un02B(-) = out = CVBn             (follower)
CVBn -> Rn12 1M -> CVHn ; Rn13 1M -> GND ; CVHn -> Un02A(+)
Un02A out = VACPn -> LED anode (Un04 pin 2) ; LED cathode (pin 1) = VACNn -> Un02A(-) and Rn09 330R -> RNGn
RNGn -> Rn14 10k -> GND ; RNGn -> RV(n+3) pin 1 (CCW end) ; RV(n+3) wiper and pin 3 = GND    (RANGE n)
```

Pots: RV1-RV3 = VOL 1-3, RV4-RV6 = RANGE 1-3 (S6).

S5 has no Cn02, Cn06 or 1N4148W; Dn01 is now the BAT54SW; Rn12/Rn13 are new. The other
references keep their S4 numbers (Rn06/Rn07/Rn08 with new values and roles).

- **Gain** = 10k / (10k + R_LDR), with the input polarity (two inversions): ~0.9-1.0
  with the LED fully on, ~0 in the dark (VTL5C dark resistance is in the MΩ range).
  Then the volume pot scales it.
- **CV range: 0..5 V** (was 0..10 V in S4), the range modules/acid and modules/hats
  put out. CVD = CV x 100k / 151k: 5.0 V → 3.31 V. Above about 5.3 V the clamp holds
  CVD near 3.6 V, so a hotter CV does nothing more and does no harm.
- **CV law**: the driver holds VACN at CVH = CVD / 2, so I_LED = CV x 0.331 / R_sense, with
  R_sense = Rn09 + (RANGE ∥ Rn14). RANGE at 0: **1.0 mA per volt (330 R)**, from 0 V:
  1 V → 1.0 mA, 2.5 V → 2.5 mA. The current
  comes from +3V3 (the LDO, so from +12 V); the -12 V rail no longer carries LED current.
- **Driver headroom (not measured)**: the MCP6002 output can't go above +3V3, so the
  sense voltage tops out at 3.3 V - V_F - the output drop. With a red LED (V_F ≈ 1.7-1.9 V
  at a few mA) that is about 1.2-1.5 V: **I_LED flattens at about 3.6-4.5 mA, reached at
  a CV of about 3.6-4.5 V**, short of the 5.0 mA the law asks for at 5 V. modules/acid has
  the same ceiling (1.65 V asked for at 5 V); it only shows at the very top of the range.
  If the bench shows it, Rn13 1M → 680k (CVH = 1.34 V at 5 V) removes it; no layout change.
- **RANGE n (S6, D17)**: RV(n+3) is the Bread Modular V2CA CURVE pot, a 50k rheostat in the
  sense leg (pin 1 = CCW end on RNGn, wiper and pin 3 on GND), with Rn14 10k across it.
  Fully CCW it is 0 Ω, so the sense is Rn09 330 R alone: the S5 response. Fully CW it adds
  50k ∥ 10k = 8.33k: R_sense 8.66k, 26 x less LED current. The knob sets the current per
  volt and nothing else; the 10k keeps the VCA from closing completely at the knob maximum
  and is a value-only tuning part (no part = 330 R..50.3k; 4.7k = 330 R..4.6k).
  Modelled gain 10k / (10k + R_LDR) with R_LDR = R1 x (I / 1 mA)^-g, ceiling 1.3 V on the
  sense leg; "clone" = the modules/hats firmware guess (1.2k at 1 mA, g = 1), "real" =
  a VTL5C3 (25k at 1 mA, g = 0.85). A model, not a measurement:

  | RANGE (rotation) | R_sense | I_LED | CV 0.1 V clone / real | 0.5 V | 1 V | 2.5 V | 5 V and unpatched |
  |---|---|---|---|---|---|---|---|
  | 0 | 330 R | 1.00 mA/V | -6.8 / -25.4 dB | -1.9 / -14.8 dB | -1.0 / -10.9 dB | -0.4 / -6.6 dB | -0.3 / -5.0 dB |
  | 10 % | 3.66k | 0.090 mA/V | -23.1 / -42.8 dB | -11.3 / -31.1 dB | -7.3 / -26.1 dB | -3.7 / -19.9 dB | -2.5 / -16.9 dB |
  | 25 % | 5.89k | 0.056 mA/V | -27.0 / -46.2 dB | -14.4 / -34.5 dB | -9.9 / -29.5 dB | -5.4 / -23.1 dB | -3.8 / -20.0 dB |
  | 50 % | 7.47k | 0.044 mA/V | -29.0 / -48.0 dB | -16.1 / -36.2 dB | -11.4 / -31.2 dB | -6.4 / -24.7 dB | -4.6 / -21.6 dB |
  | 100 % | 8.66k | 0.038 mA/V | -30.2 / -49.1 dB | -17.2 / -37.3 dB | -12.3 / -32.3 dB | -7.1 / -25.8 dB | -5.1 / -22.6 dB |

  Two things to expect on the bench. **The knob is front-loaded**: a linear pot in parallel
  with 10k puts 3.3k of the 8.3k into the first tenth of the travel, and the LED current
  goes with 1 / R_sense, so about three quarters of the effect (in dB of current) happens
  in the first 10 % and the upper half of the travel does little. That is the price of
  "330 R at 0" with a 50k linear pot; a smaller Rn14 shortens the range but doesn't change
  the shape. **RANGE also lowers the level with no CV patched** (mixer mode sits at the 5 V
  column): turn it to 0 for a plain mixer. With real-VTL5C3-like parts 330 R is already too
  little current, so RANGE would stay at 0.
- **Negative CV**: the BAT54SW holds CVD at about -0.3 V, the follower and driver sit at
  0 V and the LED is off. It is never reverse-biased.
- **Mis-patch**: ±12 V on a CV jack puts at most 0.23 mA through Rn08 into the clamp.
- **Unpatched CV**: +11.6 V → 200k + 51k → 100k gives CVD = 11.6 V x 100k / 351k =
  3.30 V, full scale: the VCA is as open as the driver can make it.
- **Bandwidth**: input buffer 100k ∥ 20p ≈ 80 kHz. The audio path is DC-coupled
  throughout, as on Bread Modular, so the VCA also passes CV. The CV path is DC-coupled
  with a 1 MHz op amp; the vactrol (ms) sets its speed.
- **OUT n is post-volume** (D1). The follower leaves the pot unloaded, so the
  volume follows the pot's own (linear) law; at full CW OUT n is unity.

### 3.3 Mix bus

```
CHO1-3 -> R111/R211/R311 100k -> SUM -> U401A(-) ; R401 100k || C401 20p ; (+) = GND -> SUMO
SUMO -> R402 100k -> U401B(-) ; R403 100k || C402 20p -> MIXO -> R404 1k 1 W 2512 -> MIX (J11 tip)
```

Unity per channel at full volume, input polarity. Three full-level 10 Vpp inputs at
full volume clip at the TL072's ~±10 V swing; turn the volumes down for hot sums, as
on any unity mixer.

### 3.4 Power

```
J10 pins 9/10 +12V_IN -> D501 B5819W -> +12V (C501 10u; one 100n per TL072 pin 8)
J10 pins 1/2 -12V_IN  -> D502 B5819W -> -12V (C502 10u; one 100n per TL072 pin 4)
J10 pins 3-8 GND
+12V -> C503 1u -> U501 HT7533-1 (SOT-89) -> +3V3 (C504 10u; one 100n per MCP6002) -> Un02 pin 8, Dn01
```

The +3V3 rail (S5, modules/acid U1/C3/C4) feeds only the three MCP6002s and the three
clamps. It carries the LED currents: at most about 15 mA, so U501 drops
(11.6 - 3.3) V x 15 mA ≈ 0.12 W. The audio op amps stay on ±12 V.

- A reversed cable reverse-biases both diodes. Their drop leaves the rails at about
  ±11.6 V.
- PWR_FLAGs: `#FLG01` on GND at the Eurorack entry, and `#FLG02`/`#FLG03` on +12V
  and -12V, which are fed from the connector only through D501/D502 (passive pins
  ERC can't see through). These are the real supply entries, not silencers. +3V3 is
  driven by U501's output pin and needs no flag.

Screening current budget (datasheet typical/max, not measured):

| Load | +12 V typ | +12 V max | -12 V typ | -12 V max |
|---|---:|---:|---:|---:|
| 7 x TL072 (1.4 / 2.5 mA per amplifier, 14 amplifiers) | 20 mA | 35 mA | 20 mA | 35 mA |
| +3V3 rail through U501: 3 vactrol LEDs (about 4.5 mA each at full scale, 5 mA asked) + 3 x MCP6002 (0.2 / 0.34 mA) | 14 mA | 16 mA | 0 | 0 |
| CV normals (3 x 33 µA) | 0.1 mA | 0.1 mA | 0 | 0 |
| **Total** | **~34 mA** | **~51 mA** | **~20 mA** | **~35 mA** |

+5 V: 0 mA. "typ" is mixer mode (no CV patched, LEDs at full scale). Output loads add
their own current on top. (S4: ~106 mA max on each rail.)

## 4. Mechanics (P6 placement, 8HP, `geometry.json`)

| Item | Value |
|---|---|
| Panel | **8HP**, 40.3 x 128.5 mm, FR4 1.6 mm (`panels/front-pcb`) or printed 2.0 mm (`panels/front-cad`); four rail holes Ø3.2 at X12.58 / X32.9, Y3.0 / Y125.5 (as the modules/blank 8HP panel) |
| Carrier | 39.3 x 110.0 x 1.6 mm, **4 layers** (F signal / In1 GND / In2 +12V / B signal), X0.5..39.8, Y9.25..119.25; hangs on the 10 jack nuts only (the R0904N pots are snap-in with a plain shaft and take no nut). Copper-to-edge 1.0 mm in the project rules |
| Channel cells | One 31.0 mm cell per channel from its jack row Y0 = 17.0 / 48.0 / 79.0: **IN (X8.0, Y0) and CV (X20.15, Y0) jacks, OUT jack under CV (X20.15, Y0 + 15.0), RANGE under IN (shaft X8.0, Y0 + 14.5), VOL alone in the right column (shaft X32.3, Y0 + 7.5)**. No jack sits above a VOL knob (the nearest jack centres are 14.3 mm away, to the left), so a patched cable never hangs over it; VOL knobs are 31 mm apart, room for the 16 mm `mechanical/knobs` set. F courtyards: jack to the jack or pot below 0.86 / 1.5 mm, centre-column jacks to the VOL pot 0.9 mm in X |
| Jacks | PJ301M-12, unrotated, columns X8.0 (IN, MIX) and X20.15 (CV, OUT); **MIX** (8.0, 110.0) in the left column, 16.5 mm below the RANGE 3 shaft (user: under the last RANGE knob) |
| Vactrols U104/U204/U304 | **B side, right column, hanging under their VOL pot**, Bread Modular VTL5C footprint (courtyard and notes added), upright at (33.3, Y0 + 19.1): the LDR lead pair (3, 4) at Y0 + 12.75 sits between the pot's bracket row and pin row (under the pot body on F, 0.45 mm above the pin pads), the body covers the three pot pins on B and the LED pair (1, 2) at Y0 + 25.45 is clear of everything. Assembly order: vactrol first (the two upper leads soldered on F and trimmed flush), then the pot; the pot's three pins then come out on B under the vactrol body, so the vactrol stays a few mm off the board or the pins are soldered from F, where their pads lie just beyond the pot body outline (not tried). The B silk notes (`SOLDER FIRST`, `TRIM FLUSH`, `LED 5mA`; R3: 1.0 mm high, three lines across the body between the pot pins and the LED leads) and the `+` / `-` marks sit inside it |
| SMD (88 parts, all on B) | Per cell: Un02 (MCP6002) between the IN and CV jacks with the CV divider / clamp above it and the 1M / 1M pair below; Un03 (follower) right of the CV jack and Un01 (input buffer + VCA) in the right column above the VOL pot, the VCA parts under the VOL pot body; the 330 R sense and Rn14 between the IN jack and the RANGE pot; the 2512 OUT resistor right of the OUT jack. Bottom: U501 +3V3 and the -12 V rail diode right of the MIX jack above / left of the power header, U401 (mix) under the OUT3 jack with R404 (2512) and the +12 V rail diode on the right |
| Power header J10 | B side, horizontal along the **bottom edge** (as modules/hats), right of the MIX jack: pins X17.0..27.16, Y113.4 / 115.94; pins 1/2 (-12 V) at the left, B silk `-12V` beside them. A 16-pin cable overhangs to the right, over the board |
| Panel holes | jack Ø6.2, pot Ø7.2 (BM `PanelHole_Potentiometer_RV09`; 0.6 mm radial clearance around the Ø6.0 R0904N shaft), rail Ø3.2 |
| Pot stack (Z from F.Cu) | Song Huei R0904N, drawing R09N-003 v1.5, tall L = 25: body 6.8 + collar 0.8 → top Z7.6, 2.4 mm under the panel rear (Z10.0); Ø6.0 shaft to Z25.0; knurl Z18.0..25.0. Panel front Z11.6 (FR4) / Z12.0 (print), so the tip is 13.4 / 13.0 mm proud and the knurl starts 6.4 / 6.0 mm above the face |
| Labels | `VCA-MIX`; `INn` / `CVn` / `OUTn` above each jack row; `RANGE` and `VOL` above the knobs; `MIX`; `BIG MODULAR` |
| 3D fit (nominal) | `docs/fit/fit-report.json` (P6, 2026-11-14): 0 mm³ interference for all 10 jacks and the six pots (R0904N datasheet envelopes) against both panels; board inside the rail gap and panel width. Vactrols have no 3D model and are **not** in the check (D4) |

**Fit study before placement** (done for P5, `research/s6/fit/density.py`, method of
modules/usb-audio-max): 88 SMD courtyards, 887 mm², against the free B area after the 1 mm
edge keep-out and the 2 mm hand-solder ring around every jack and pot pad: about 2010 mm²
free on 8HP, 44 % density (10HP: 32 %). Not repeated for P6: the same parts and THT count
fit, placed by hand (88 of 88 SMD on the board, hand-solder ring and edge keep-out
measured, section 4.1).

**Vactrols under the VOL pots (D10, approved 2026-11-14).** Each vactrol hangs on B below
its VOL pot: the LDR lead pair between the pot's bracket pads and its pin row, the body
over the pin row. Nothing is electrically wrong (copper clearances pass), but native DRC
reports the overlap: per channel 5 `pth_inside_courtyard` (the two LDR leads inside the pot
courtyard, the pot's three pins inside the vactrol courtyard): **15 items, 5 per channel**,
no silk finding (the build notes are clear of the pot pins). The user approved them on
2026-11-14 ("Those DRC issues are fine"), as on modules/low, acid and hats.
`tools/d10_exclusions.py` wrote exactly those 15 as per-item exclusions into
`hardware/vca-mix.kicad_pro` (all matched at the pad position); the rule stays at `error`
and nothing else is excluded. The S4 approval (9 exclusions, 2026-10-20) was for a
placement that no longer exists. The assembly consequence (pot pins under the vactrol body)
is a bench check, not a tested fit.

### 4.1 Routing (R2, manual, 2026-11-14)

Placed and routed by hand, divide and conquer, straight on `hardware/vca-mix.kicad_pcb`
(root `AGENTS.md`; no autorouter). R1 was the P5 board of the same day; it went with the P5
placement. The S4 TraceMaker board (6HP, 2 layers, `tools/route_r1.json`, `route_plan.py`,
`promote_r1.py`) is gone with the 6HP outline; those three files are removed (git history
keeps them).

- Order: channel 1 as the reference cell (place, plane fan-outs, then its links in three
  batches), the same cell copied 31 mm down for channels 2 and 3, then the bottom group
  (mixer, +3V3, rail diodes), the trunks that cross the cells (+3V3 at X17.8, -12V at
  X22.2, SUM at X23.0 on B), the mixer and the power entry. Every coordinate is written by
  hand in `research/p6/route/build.py` (a one-link path helper suggested some cell links);
  each batch was written to the board and followed by native DRC + parity. Per-batch DRC
  reports and board backups: `research/p6/drc/`, `/tmp/vca-mix-p6/`.
- Layers: In1 GND and In2 +12V planes with thermal-relief pads; every GND and +12V SMD pad
  fans out with a short dogbone to a via beside the pad. -12V, +3V3 and SUM run as tracks
  on F/B. 0.25 mm signals, 0.4 mm rails (`Power` class), vias 0.6 / 0.3 mm. -12V leaves
  the header on B, crosses to the trunk on F (X15.55, then Y102.4). MIX runs on F from
  R404 along the bottom edge (Y117.7, below the header pins) to the MIX jack tip.
- Result of R2 (`research/p6/check1/`; R3 figures in section 4.2): ERC 0, **0 unconnected,
  parity 0**, DRC 0 apart from the 15 stacking findings above; 458 track segments, 85
  vias; no via in or touching an SMD pad (closest 0.29 mm); no tracks on In1 or In2; In2 one
  piece, In1 one piece plus five spoke-tied slivers (2.6 mm² x 2 between the J10 GND pins,
  1.0 mm² x 3 between each IN jack's TN / S pads); SMD pads >= 2.0 mm from every pot / jack
  pad (closest 2.015 mm: U401.4 to the OUT3 sleeve, then 2.025 mm: Cn08 to the CV jack
  switch pad); courtyards >= 1.0 mm from the edge (closest 1.025 mm: Cn04, R101).

### 4.2 Fab review and export (R3, 2026-11-14)

User direction: "Those DRC issues are fine. Also fine for extended parts. Do the JLC export
and fab readiness." The review measured the R2 board (`research/fab/review.py`: routed
pin-to-cap lengths, hand-solder distances, via / pad / edge distances, drill table, silk
sizes, saved fills against a fresh refill); the edits were written straight on the board by
hand (`research/fab/fab_r3.py`), each stage followed by native DRC + parity.

Fixed (R2 -> R3, no THT part moved):

- **Cn05 at Un02 pin 8.** The MCP6002 +3V3 100n sat 10.9 mm down the +3V3 trunk (the
  datasheet asks for the bypass within 2 mm). It now stands upright between Dn01 and the CV
  jack's 2 mm ring at (16.4, Y0 - 1.8), +3V3 pad on the pin 8 feed: routed 2.2 mm. Dn01's
  GND via was where the cap's GND pad is now, so Dn01 pin 1 joins that pad and they share
  one via 1.2 mm above it. Same edit on all three channels.
- **B silk legend 1.0 mm high, 0.15 mm stroke** (JLCPCB minimum; the vactrol notes were
  0.8 mm): `tools/import_footprints.py` now writes the three notes as horizontal lines in
  the pad-free block between the pot pins and the LED leads, and the board footprints equal
  the library; board texts `VCA-MIX S6/R3` and `-12V` at the same size.
- **Stackup recorded**: JLC04161H-7628 (1.6 mm, 1 oz outer / 0.5 oz inner), the block
  modules/ladder and modules/hats carry; zone fills saved, equal to a fresh refill.
- **D10 exclusions** written (section 4), title block revision `S6/R3`.

Judged and kept for the first prototype (not waived):

- +12V bypass caps of Un03 (9.0 mm) and U401 (8.1 mm) and the U501 input cap C503 (7.1 mm),
  all through the In2 plane; each TL072 has its -12V cap within 1.7 - 2.1 mm and U501 its
  output cap at 2.3 mm. Bench: check the outputs and +3V3 for oscillation.
- SMD pads closer than 2 mm to hand-soldered pins that are not pots or jacks: J10 (four,
  closest R402 1.29 mm from pin 7) and the vactrol leads (25, closest C403 1.09 mm from
  U304 pin 2). The 2 mm rule covers pots and jacks (closest 2.015 mm).
- Tented vias 0.35 mm from the U104 / U204 LED lead pads (GND) and 0.45 mm from the CV
  jack tip / switch pads (-12V trunk): DRC clearance holds, mind them when soldering.
- 129 track / via coordinates sit 1 nm off the 0.005 mm grid (float truncation, e.g.
  136.454999 mm): no fab effect, left alone.

Result (`docs/fit/carrier-drc.json`, `research/fab/check-post/`,
`research/fab/review-final.txt`): ERC 0, **0 unconnected, parity 0, 0 active DRC findings**
(15 excluded); 467 track segments (B 382, F 85), 82 vias; no via in or touching an SMD pad
(closest 0.29 mm); no tracks on In1 or In2; planes as R2; SMD pads >= 2.015 mm from every
pot / jack pad (then 2.025 mm Cn08, 2.063 mm Cn05, both to the CV jack); courtyards >=
1.025 mm and copper >= 1.33 mm (pads) / 1.43 mm (tracks) from the edge.

Export (`jlcpcb/`, shared exporter, 2026-11-14): 4-layer carrier Gerbers, bottom-side
Economic BOM / CPL (88 parts, 17 rows; the 20 THT refs excluded), 8HP panel Gerbers, source
manifest equal after the export. Drill, mask, paste, BOM / CPL and panel-hole checks are
listed in `jlcpcb/README.md`. Not done: JLCPCB placement preview and DFM, any build.

## 5. Decisions and open checks

| # | Item | State |
|---|---|---|
| D1 | Per-channel OUT is **after** the volume pot (buffered wiper); MIX sums the post-volume channels | Decided (review 2026-10-19) |
| D2 | Unpatched CV = VCA open (TN normal to +12 V; S5: via 200k → 3.30 V at the divider = full scale) | Decided (brief: works as a mixer without CV) |
| D3 | **Pot stack**: Song Huei R0904N tall trimmers, snap-in, plain knurled shaft, **no bushing or nut** | **Closed on the datasheet** (section 4). The panel is held by the jack nuts alone. The BM footprint is kept exactly (bracket legs 9.6 mm vs the drawing's 10.6 mm): the user confirmed (2026-10-19) these pots work well in it on their BM builds. Not a physical-fit claim for this board |
| D4 | **Vactrol part**: the Chinese vactrols that fit the Bread Modular VTL5C footprint. S4 LED current: 7.7 mA at 5 V CV, 11.9 mA unpatched, 18.5 mA at +12 V CV; **S5: at most 5 mA** (3.3 V driver), silk note `LED 5mA` (library and board, P5). LDR range and body height behind the board not modelled | **Handed to the builder (user, 2026-10-20)**: the VTL5C footprint carries B.SilkS notes inside the body box (`SOLDER FIRST`, `TRIM FLUSH`, `LED 18.5mA`); the user solders and checks the part accordingly. **LED rating confirmed by the user (2026-10-20): 40 mA**, so the 18.5 mA worst case keeps 330 R (R109/R209/R309). Not a bench claim |
| D5 | Routing | **R2 (2026-11-14): manual divide-and-conquer on the 8HP 4-layer carrier** (section 4.1; R1 was the P5 board); **R3** adds the fab-review fixes (section 4.2). The S4 TraceMaker route is retired |
| D6 | Pot taper: linear 50k as Bread Modular | Decided (brief: same pots; user prefers linear for audio too) |
| D7 | Op amp TL072CDT (C6961) is Basic; the 1 W 2512 1k (C54315) is Extended | Accepted (the same trade-off as modules/imix) |
| D8 | CV scaling: S4 inverting buffer gain -0.51, 330 R sense (1.55 mA/V, from 0 V) | **Replaced by D15 (S5)** |
| D9 | Vactrols on B behind a pot | Decided (review 2026-10-19); P6: under the VOL pot, upright in the right column (P5 had it behind the RANGE pot) |
| D10 | Vactrol / pot stacking DRC findings | **Approved by the user 2026-11-14 ("Those DRC issues are fine"): 15 items, 5 per channel** (section 4), written as per-item exclusions by `tools/d10_exclusions.py`; nothing else excluded, rule severity unchanged. (The 2026-10-20 approval covered the 9 items of the S4 placement, which no longer exists.) Bench: the assembly order under the VOL pot |
| D11 | Audio inputs, CV inputs buffered; OUT/MIX through 1k 1 W 2512 | Decided (review 2026-10-20, as modules/imix / 8bit) |
| D12 | Planes: In1 GND, In2 +12V, thermal-relief pad connection | P5 / R1, kept on P6 / R2 / R3 (2026-11-14), as modules/acid / hats / ladder; stackup JLC04161H-7628 recorded in R3. Replaces the S4 two-layer solid GND pours |
| D13 | Router | **None** (root `AGENTS.md`, 2026-10-21: no autorouters). The S4 board used TraceMaker 0.10.0; retired |
| D14 | Shared apply/`check` count excluded findings as findings | Accepted by the user for the S4 board (2026-10-20). Still true of the shared tool: on R3 `check` reports `order_ready: false` for the 15 excluded stacking items (KiCad's own DRC has 0 active findings); the export manifest is equal |

| D15 | **CV on the modules/acid 3.3 V pipeline** (51k / 100k, BAT54SW clamp, MCP6002 follower, 1M / 1M, MCP6002 driver with the LED in its loop, HT7533-1 +3V3); CV range 0..5 V; audio unchanged on ±12 V | **Decided 2026-11-13 (user).** The sense value question is answered by D17. Open: the driver ceiling near the top of the CV range (section 3.2), bench |
| D16 | MCP6002 (C7377, Preferred Extended) and BAT54SW (C78260, Extended) are not Basic | **Accepted by the user 2026-11-14** ("fine for extended parts"): the modules/acid parts, three of each per board |
| D17 | **RANGE pot per channel**: 50k rheostat ∥ Rn14 10k in series with Rn09 330 R (330 R at 0 .. 8.66k at max) | **Decided 2026-11-14 (user).** S6. Open for the bench: the Rn14 value (front-loaded knob, section 3.2) |
| D18 | **8HP**, 4-layer carrier | **Decided 2026-11-14 (user: 8HP).** Layers follow modules/acid / hats. Layout: D19 |
| D19 | **P6 layout**: OUT jack under CV, RANGE under IN, VOL alone in the right column, MIX jack under the last RANGE knob | **Decided 2026-11-14 (user, option B of three shown + MIX moved):** "we rarely turn the range knob, the volume knobs are used all the time". Replaces P5 (RANGE left / VOL right under each jack row, OUT jack above VOL) |

## 6. Sourcing (JLCPCB, dated observations 2026-10-19/20, S5 parts 2026-11-13, audit 2026-11-14)

From `kicad_tools.py assembly lookup --strict-live`. Full records for the S5 part set
are in [`sourcing-candidates.json`](sourcing-candidates.json) (updated from the saved
lookups by `research/s5/sourcing_doc.py`). Stock is transient and is not a reservation.

| Part | LCSC | MPN | Class |
|---|---|---|---|
| TL072 x7 | C6961 | ST TL072CDT (SO-8) | Basic |
| MCP6002 x3 (Un02) | C7377 | Microchip MCP6002T-I/SN (SOIC-8) | Preferred Extended (stock 69197 at lookup) |
| BAT54SW x3 (Dn01) | C78260 | onsemi BAT54SWT1G (SOT-323) | Extended (stock 168070 at lookup) |
| HT7533-1 (U501) | C14289 | Holtek HT7533-1 (SOT-89-3) | Basic |
| 1k 1 W 2512 x4 (OUT1-3, MIX) | C54315 | UNI-ROYAL 25121WF1001T4E | Extended |
| 1M / 200k / 100k / 51k / 10k / 330 / 100 (0603, 1 %) | C22935 / C25811 / C25803 / C23196 / C25804 / C23138 / C22775 | UNI-ROYAL 0603WAF… | Basic |
| 20p C0G 0603 | C1648 | Samsung CL10C200JB8NNNC | Basic |
| 100n X7R 0603 | C14663 | YAGEO CC0603KRX7R9BB104 | Basic |
| 10u 25 V X5R 0805 | C15850 | Samsung CL21A106KAYNNNE | Basic |
| 1u 50 V X7R 0805 (C503) | C28323 | Samsung CL21B105KBFNNNE | Basic |
| B5819W SOD-123 | C8598 | CJ B5819W SL | Basic |

**Audit of the exported BOM, 2026-11-14 13:07 UTC** (`assembly.py audit --strict-live`, 5
boards as a screening quantity; `research/fab/audit.json`): all 17 codes resolve to the
MPNs and packages above and are Economy-eligible; 14 Basic, C54315 Extended (stock 60,375),
C78260 Extended (168,051), C7377 Preferred Extended (67,081); lowest Basic stock TL072CDT
C6961 at 120,398. The audit is not order-ready: no `docs/jlcpcb-audit-requirements.json`
(per-part requirement / review rows `unknown`), and it flags the Extended 2512 resistor.
`sourcing-candidates.json` keeps the earlier per-part records and was not regenerated.

Hand-soldered, not JLCPCB-assembled: 10 x QingPu WQP-PJ301M-12, 6 x Song Huei
R0904N 50k linear tall-trimmer pots (3 VOL + 3 RANGE; L = 25, knurled), 3 x Chinese VTL5C-type vactrols
(Bread Modular footprint), 1 x 2x5 2.54 mm header.
