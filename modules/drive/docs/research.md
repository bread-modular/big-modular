# DRIVE research notes (S1 schematic, P2 placement, R1 routing)

## 1. Goal

User brief (2026-11-15): "We don't have an overdrive / drive module in our setup. Build a
really nice overdrive with a mix knob too", plus "I would love to have some CV controls".

From the five approaches offered, the user picked **C, drive + wavefolder**, with these
directions:

- **Use OTAs** ("to test things out"). This replaces the vactrol CV of the proposal.
- **Simulate it** to see it works as intended, before anything else.
- **No CV on MIX.** Mono, single. **6HP** is enough.
- This step: **schematic + THT layout. No routing.**

Choices the user did not answer, taken as the recommended defaults: CV adds to the knob (no
attenuator knobs, they would not fit 6HP), knobs DRIVE / FOLD / TONE / MIX, no LEVEL knob (the
wet path saturates at the Eurorack level, section 3.6), module name `drive`.

## 2. Reference: Bread Modular DRIVE

Bread Modular `drive` 1.0.0 (read-only, `modules/drive`): MCP6002 on a single supply, inverting
input buffer (0.2.0: "non-inverting buffer picked up radio; inverting buffer and all is gone"),
gain stage with SS14 pairs + 500k pots in the feedback, antiparallel SS210 / SS14 on the "dirty"
output. Kept here: the **inverting input buffer**. The clipper itself is new: the user asked
for OTAs.

## 3. Circuit (S1)

Signal path: `IN -> U1A (-1) -> DRY -> VCA (U5 pins 1-5) -> U1B -> U -> 10u -> 1/11 -> X ->
five tanh cells -> U2A -> Y -> 10u -> TONE -> U2B -> WET -> MIX (with DRY) -> U3A -> U3B (-1)
-> 1k -> OUT`.

### 3.1 Why OTAs fit this job

An LM13700 half without its linearizing diodes is a **tanh cell**:
`I_out = I_ABC x tanh(V_d / 2 V_T)`, with 2 V_T = 52 mV. That gives two things at once:

- a smooth, symmetric soft clipper (the classic OTA / transistor saturation);
- an **amplitude that is a current**: `I_ABC` scales the cell, and currents of several cells
  add on one wire. A fold is "tanh minus a shifted tanh", so a wavefolder is just more cells
  with offset inputs, and its depth is one bias current. No vactrol, and it follows CV at
  audio rate.

### 3.2 DRIVE: linearized OTA VCA

The drive amount is the gain in front of the cells, so it needs a clean VCA: U5 (pins 1-5)
with its **linearizing diodes** (I_D = 1.05 mA through R7), signal current through R3 (15k):
`I_out = I_s x 2 I_ABC / I_D`, linear for |I_s| < I_D / 2 (±8 V at IN). U1B turns it into a
voltage (R8 120k): `U / IN = (120k / 15k) x 2 I_ABC / I_D`.

- R4 / R5 (1k) carry the diode current; R6 (15k) mirrors R3 on the other input, so the VCA has
  no systematic offset.
- C5 (10u) AC-couples U into the cell divider (7 Hz): the VCA offset times the drive gain never
  reaches the cells. Simulated with the LM13700's maximum 4 mV input offset: U moves 0.37 V at
  the highest gain, nothing at the output.
- R9 / R10 (2k / 200R) divide U by 11 and give the five cell inputs a 182R source, so their
  bias currents shift X by well under a millivolt.

### 3.3 DRIVE control: exponential converter

`I_ABC` comes from a PNP pair (Q1 / Q2, SS8550) with U4A holding Q1 at `I_ref` = 11.6 uA
(R34): `I_ABC = I_ref x exp(V(DVC) / V_T)`. V(DVC) = knob x 94 mV (R31) + CV x 19.4 mV / V
(R32), on R33 (2k). So the knob moves the gain in **even dB steps** and the CV is **6.5 dB / V**.

- Two discrete SS8550 instead of a matched pair: a drive control needs no precision (a few mV
  of V_BE mismatch = 1 dB at the bottom of the knob). Place them side by side.
- R35 (10k) limits `I_ABC` to about 0.95 mA (LM13700 maximum 2 mA). D4 keeps the emitters above
  -0.6 V. C12 (100p) compensates the loop: 42 us settling, no overshoot in simulation.
- Tolerances: the range scales with the +12 V rail (5 % = 1.6 dB at the top) and with
  temperature (0.33 % / K); the SS8550 Early voltage moves the bottom by about ±1.5 dB.

### 3.4 Cells: soft clip + two fold pairs

| Cell | OTA | Input | Sign | Bias |
|---|---|---|---|---|
| B | U5 pins 12-16 | X | + | I_0 = 0.52 mA, fixed (R20 from GND) |
| C / D | U6 | X ∓ 198 mV (R12-R15) | − | f x I_0 |
| E / F | U7 | X ∓ 405 mV (R16-R19) | + | f x I_0 |

`Y / 5.2 V = -[tanh(x) - f (tanh(x - t) + tanh(x + t)) + f (tanh(x - 2t) + tanh(x + 2t))]`,
with x = X / 52 mV and t = 3.8.

- **f = 0**: plain tanh overdrive.
- **f = 1**: +1, −1, +1 as the signal grows: two folds per side.
- The outer level is `1 - 2f + 2f = 1` **for every f**: FOLD changes the shape, not the
  loudness. This is why there are two pairs. With one pair (first draft, simulated) the level
  collapsed at f = 0.5 and the signal came out inverted at f = 1.
- Cell currents add on `YS`; U2A (R21 10k) converts them: ±5.2 V at I_0.
- The LM13700 Darlington buffers and the diode pins of the five cells are unused and left open.

### 3.5 FOLD control: linear, limited

U4B / Q3: `I = (knob + CV) x (1 + R24 / R25)` = x42.7, split four ways through R27-R30 (9.1k).
Knob at max = 48 uA = f 1.0; CV 5 V = 50 uA = f 1.0.

- **Limit f = 1.06**: Q3 saturates when the 9.1k drops reach V(FE); cell B's bias comes from
  the same kind of drop (R20), so the limit is a resistor ratio, not a rail value. R26 (47k)
  in the base stops the bias from folding back when Q3 saturates (without it, simulated: knob at
  max + 5 V CV dropped f to 0.28).
- Negative sums switch the fold cells off; D3 keeps Q3's base-emitter out of reverse bias.

### 3.6 TONE, MIX, output, levels

- TONE: R36 (2k) + RV3 (50k rheostat) into C14 (4.7n), buffered by U2B: 17 kHz .. 650 Hz, on the
  wet path only. The linear rheostat crowds the bright end (0.75 = 2.3 kHz): a bench-tuning item.
- C13 (10u) AC-couples the wet path: the cell offset (it moves a few tens of mV with FOLD) does
  not reach the output.
- MIX: RV4 between DRY and WET, both inverted, U3A follows the wiper, U3B inverts: **OUT has
  the input polarity for dry and wet**, so mixing never cancels.
- No LEVEL knob: the wet path saturates at ±5.2 V, the Eurorack audio level. At DRIVE min the
  wet gain is x1 for small signals; a full 10 Vpp input is already gently saturated (7.4 Vpp).
- R40: 1k 1 W 2512, as modules/vca-mix (mis-patch protection).

### 3.7 CV inputs and protection

DRIVE CV and FOLD CV go through 100k into a 2k node and a virtual ground: ±12 V mis-patches are
harmless by construction (simulated: both converters stay at their limits or at zero). IN: 100k
into a virtual ground. No 3.3 V CV pipeline is needed here (no MCU, no vactrol LED).

### 3.8 Parts

4 x TL072, 3 x LM13700, 3 x SS8550, 2 x 1N4148W, 2 x B5819W, 40 R, 29 C: 83 SMD parts on B, plus
4 jacks, 4 pots and the power header by hand. Live JLCPCB lookups (2026-11-15,
`docs/sourcing-candidates.json`): all Basic except **LM13700MX/NOPB (C174050, Extended, 10,559
in stock)**, the **1 W 2512 1k (C54315, Extended)** and 240k (C4197, Preferred Extended, no
fee). MMBT3906 is Extended everywhere, so the PNP is the Basic SS8550 (C8542).

## 4. Simulation (ngspice, `tools/sim_drive.py`)

The deck is generated from `circuit()`, so it is the drawn circuit. **Models, not
measurements**: a transistor-level LM13700 half from the datasheet schematic with generic
transistors, a one-pole TL072, a generic SS8550. Rails ±11.77 V after the Schottkys.

| Check | Result |
|---|---|
| DRIVE knob | wet gain −0.6 dB .. +31.3 dB, 3.8 .. 4.6 dB per eighth of a turn; I_ABC 15 .. 592 uA |
| DRIVE CV (knob at 0) | 6.5 dB / V; +31.9 dB at 5 V; limit +35.4 dB (0.96 mA); −5 V = −33 dB |
| FOLD knob | f = 0, 0.24, 0.47, 0.72, 1.00 at 0, ¼, ½, ¾, 1 |
| FOLD CV | 0.2 / V; limit 1.06 with any knob + CV up to +12 V; off for negative sums |
| Transfer, f = 1 | +4.7 V at U = 1.1 V, −4.7 V at 3.3 V, +5.1 V beyond 6 V; zero crossings at ±2.2 / ±4.5 V; peaks symmetric within 20 mV, −73 mV at the centre (AC-coupled out by C13) |
| 10 Vpp sine, FOLD 0 | DRIVE 0: 7.4 Vpp, 3rd harmonic −25 dB; DRIVE 1: ±5.07 V square-like |
| 10 Vpp sine, FOLD 1 | DRIVE 0.5: 3rd harmonic 2.5 x the fundamental; DRIVE 0.75: strong 9th; rms 3.5 .. 4.8 V |
| 2 Vpp sine | clean at DRIVE 0 (x0.93); soft clip from DRIVE 0.5, folds near DRIVE max |
| Polarity | OUT in phase with IN (±0.6°) at MIX dry, centre and wet |
| TONE | −3 dB at 615 Hz, 822 Hz, 1.2 kHz, 2.3 kHz, 16.8 kHz (knob 0, ¼, ½, ¾, 1) |
| Converter steps | DRIVE 42 us, FOLD 26 us to 90 %, no overshoot |
| Noise, wet, 20 Hz .. 20 kHz | 0.54 mV rms at DRIVE 0 (−76 dB re 10 Vpp), 5.7 mV at DRIVE 1 (31 dB of gain) |
| Supply | 15 / 14 mA idle, 20 / 22 mA with DRIVE and FOLD at max (+12 V / −12 V) |

Plots: `docs/sim/transfer.png` (shaper transfer for five FOLD settings),
`docs/sim/waves-10vpp.png` and `waves-2vpp.png` (DRIVE x FOLD waveform grid),
`docs/sim/controls.png` (DRIVE knob / CV, FOLD CV, TONE).

What the simulation does not settle (bench items):

- the real LM13700 cell shape near the folds and the match between the two halves of a chip;
- how the folds sound across DRIVE: with a 10 Vpp input the folding sits between DRIVE 0.25
  and 0.8; above that the output is a square with narrow edges;
- noise of the real VCA at low I_ABC, and TONE taper.

## 5. Placement (P2) and panel

P1 was the modules/hats 6HP grid (columns X7.75 / X22.25, knobs Y41 / Y75, jacks Y21 / Y102,
J10 lying along the bottom edge; pot courtyards 0.79 mm from the edge). The user then asked
(2026-11-15): "move the power socket to the side and use that space to move down the pots".

| Row | Left (X8) | Right (X22) |
|---|---|---|
| Y21 jacks | DRIVE CV (J2) | FOLD CV (J3) |
| Y45 knobs | DRIVE (RV1) | FOLD (RV2) |
| Y80 knobs | TONE (RV3) | MIX (RV4) |
| Y110.3 jacks | IN (J1) | OUT (J4) |

- J10 (2x5) upright at the right edge on B, X23.8 / X26.34, Y91.2..101.36, between the MIX
  pot pins and the OUT jack; pins 1/2 (-12 V) at the bottom. As modules/16bit P6, 8bit, 12bit.
- Knob rows 4 / 5 mm lower at 35 mm pitch, bottom jacks 8.3 mm lower. The CV jacks stay at Y21.
- Columns X8 / X22 (0.25 mm in): the pot courtyards are now 1.02 mm from the edge, inside the
  1 mm rule, so the P1 question is closed.
- A 16-pin cable overhangs upward from pin 1 over the RV4 pins: trim those leads to <= 2 mm
  (`docs/geometry.json`, `idc_note`). SMD under the socket is <= 1.75 mm tall.

Carrier 29 x 110 mm. Picture: `docs/tht-layout.png`.

## 6. Routing (R1, then R2 on 2 layers) and fab review

Manual divide and conquer on `hardware/drive.kicad_pcb`, one group per batch, native DRC +
parity after each (scripts and reports in the ignored `research/route/`). No autorouter; a
one-connection path finder proposed each path and every path was checked.

- **Layers:** F signal / In1 GND / In2 +12V / B signal. -12V runs as tracks: a B rail in the
  middle band and an F trunk from D2 to the top strip, 0.4-0.5 mm. No tracks on In1 / In2.
- **Groups (all SMD on B):** fold threshold dividers R12-R19 / C6-C9 in the top strip between
  the CV jacks; converters U4, Q1 / Q2 (side by side, same orientation), Q3 in the top band;
  OTAs U5 / U6 / U7 with U1 in the middle band; U2 (cell sum + tone), U3 (mix + output),
  R40 and the power entry D1 / D2 / C1 / C2 in the bottom band beside J10.
- **Result:** 393 tracks / 79 vias; ERC 0, DRC 0 (no exclusions), unconnected 0, parity 0.
  No vias in SMD pads, SMD pads >= 2.025 mm from pot / jack pads, copper >= 1.1 mm and
  courtyards >= 1.02 mm from the edge, In2 one piece, In1 one piece + five spoke-tied
  fragments between GND pads (J10, J1-J3).

Fab review (2026-11-15):

| Item | Result |
|---|---|
| Stackup | was not recorded: JLC04161H-7628 (1.6 mm) written to the board. Fixed |
| B silk | `-12V` legend moved clear of R38; title `DRIVE S1/R1`. Fixed |
| Vias | 0.6 / 0.3 mm, tented both sides; mask Gerbers hold pad openings only |
| Paste | B only; F paste empty (THT side) |
| TL072 decoupling | 100n within 1.6-2.2 mm of every supply pin |
| LM13700 decoupling | 100n 3.6-6.1 mm from pins 6 / 11 (the SOIC-16 supply pins sit mid-body). Judged fine for a 2 MHz OTA on a +12V plane; not changed |
| J10 vs F-side bodies | header joints at Y90.35..102.2, between the RV4 courtyard (to Y88.69) and the J4 courtyard (from Y104.0) |
| Panel | 10 NPTH, every hole on its carrier part (X8 / X22; Y21, 45, 80, 110.3) |
| Export | hashes equal the sources, mirrors byte-identical, 83 placements all bottom |

### R2: 2 layers (2026-11-15)

User: "would it be possible to do a 2 layer routing for this", then "do it". Same conversion as
modules/12bit R2. The R1 signal copper was already on F / B only and is untouched.

- **Planes removed:** In1 GND and In2 +12V are gone; the board has 2 copper layers and no
  stackup record (plain 1.6 mm 2-layer).
- **GND:** one zone poured on F and B. The B pour is one 1759 mm2 piece plus two pad / via-tied
  pieces. The F pour is a 1713 mm2 main piece plus 12 pieces (5.9-83.7 mm2) cut off by the
  supply trunks; 16 stitching vias tie every one of them to the B pour, and four of those
  bring the pour back where the filler had left bare board.
- **+12V:** a 0.4-0.5 mm trunk, 187 mm on F and 44 mm on B, 7 new vias: D1 via -> U3 -> one B
  hop under the -12V branch at Y91 -> U1 -> U5 -> C24 -> one B hop under the -12V trunk -> U7,
  U6, RV1; from C24 to RV2 and up X18.1 / X17.6 to U4 and R12 / R16. U2 is fed from the D1 via
  with one B hop under the -12V branch at Y100.9. About 0.13 ohm to the far end: 3 mV at 22 mA
  (calculated).
- **Result:** 455 tracks / 102 vias; ERC 0, DRC 0 (no exclusions), unconnected 0, parity 0;
  house-rule distances as R1.

Fab review of R2:

| Item | Result |
|---|---|
| Layers | 2 in the board and in the Gerber set (no In1 / In2 files) |
| B silk | title `DRIVE S1/R2`. Fixed |
| Starved thermals | J2 S and RV2 pin 1 sat on isolated F islands after the trunks went in: stitched to the B pour. Fixed |
| Bare F areas | four islands without a GND pad were dropped by the filler: a GND via in each. Fixed |
| Mask / paste / assembly | mask and paste Gerbers unchanged, BOM and positions byte-identical to R1; 23 more via drills |
| Decoupling | same caps, same places (TL072 1.6-2.2 mm, LM13700 3.6-4.3 mm to the cap pad); the return is now pour + via instead of a plane. Judged fine at audio speed; not changed |
| Ground quality | F pour is cut into strips by the two supply trunks; the fold-cell inputs (±200-400 mV) run about 40 mm on F. Judged acceptable for the first prototype; bench item: hum / noise at high DRIVE against the simulation |

Pictures: `docs/routing.png` (R2).

## 7. Open

1. Extended parts: LM13700 (C174050, no alternative) and the 2512 1k (C54315).
2. JLCPCB preview (part matches, rotations) before ordering; bench test of the levels, the
   VCA noise at low DRIVE and the TONE taper.
3. Ideas not built: a LEVEL knob or a clip LED (need panel room), an asymmetry trim for even
   harmonics, a log-like TONE taper.
